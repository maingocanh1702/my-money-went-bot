"""Zalo OA messenger adapter."""

from __future__ import annotations

import html
import os
from typing import cast

import httpx

from core import db
from core.logging import get_logger

from .base import BaseSender, Button, Markup, SendPayload, register_sender
from .i18n import t

_ZALO_OPENAPI_BASE = "https://openapi.zalo.me"
_ZALO_OAUTH_BASE = "https://oauth.zaloapp.com"
_DEFAULT_TEXT_LIMIT = 2000

log = get_logger(__name__, component="zalo_sender")


class ZaloSender(BaseSender):
    """Posts text messages to the Zalo Official Account API."""

    channel_type = "zalo"

    def __init__(
        self,
        access_token: str,
        *,
        refresh_token: str = "",
        app_id: str = "",
        secret_key: str = "",
        http_client: httpx.AsyncClient | None = None,
        api_base: str = _ZALO_OPENAPI_BASE,
        oauth_base: str = _ZALO_OAUTH_BASE,
        text_limit: int = _DEFAULT_TEXT_LIMIT,
        auto_refresh: bool = False,
    ) -> None:
        if not access_token:
            raise ValueError("ZaloSender: access_token must be non-empty")
        if text_limit <= 0:
            raise ValueError("ZaloSender: text_limit must be positive")
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._app_id = app_id
        self._secret_key = secret_key
        self._api_base = api_base
        self._oauth_base = oauth_base
        self._text_limit = text_limit
        self._auto_refresh = auto_refresh
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send(self, user_id: int, payload: SendPayload) -> None:
        recipient_id = await self._resolve_recipient_id(user_id)
        locale = payload.get("locale", "vi")
        text = self._resolve_text(payload, locale)
        markup = payload.get("markup")
        if markup is not None:
            text = self._append_markup_text(text, markup, locale)
        if payload.get("parse_mode") in {"markdown", "html"}:
            text = self._plain_text(text)

        chunks = self._chunk_text(text)
        for chunk in chunks:
            await self._post_message(recipient_id, chunk)

    async def _post_message(self, recipient_id: str, text: str) -> None:
        response = await self._send_once(recipient_id, text)
        if response.status_code == 401 and self._auto_refresh:
            await self._refresh_access_token()
            response = await self._send_once(recipient_id, text)
        response.raise_for_status()
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if error not in (None, 0, "0"):
            raise RuntimeError(f"Zalo API rejected send message: {body!r}")

    async def _send_once(self, recipient_id: str, text: str) -> httpx.Response:
        return await self._client.post(
            f"{self._api_base}/v3.0/oa/message/cs",
            headers={"access_token": self._access_token},
            json={
                "recipient": {"user_id": recipient_id},
                "message": {"text": text},
            },
        )

    async def _refresh_access_token(self) -> None:
        if not (self._refresh_token and self._app_id and self._secret_key):
            raise RuntimeError("Zalo token refresh requires refresh_token, app_id, and secret_key")

        response = await self._client.post(
            f"{self._oauth_base}/v4/oa/access_token",
            headers={"secret_key": self._secret_key},
            data={
                "grant_type": "refresh_token",
                "app_id": self._app_id,
                "refresh_token": self._refresh_token,
            },
        )
        response.raise_for_status()
        body = response.json()
        access_token = str(body.get("access_token") or "")
        refresh_token = str(body.get("refresh_token") or self._refresh_token)
        if not access_token:
            raise RuntimeError(f"Zalo token refresh response missing access_token: {body!r}")
        if refresh_token != self._refresh_token:
            log.warning("zalo.refresh_token_rotated_without_persistence")
        self._access_token = access_token
        self._refresh_token = refresh_token

    async def _resolve_recipient_id(self, user_id: int) -> str:
        pool = db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT channel_chat_id, channel_user_id
                FROM users
                WHERE id = $1 AND channel_type = 'zalo';
                """,
                user_id,
            )
        if row is None:
            raise LookupError(f"zalo user_id={user_id} not found")
        recipient_id = row["channel_chat_id"] or row["channel_user_id"]
        if not recipient_id:
            raise LookupError(f"zalo user_id={user_id} has no recipient id")
        return cast(str, recipient_id)

    @staticmethod
    def _resolve_text(payload: SendPayload, locale: str) -> str:
        if "text_key" in payload and payload["text_key"]:
            params = payload.get("text_params") or {}
            return t(payload["text_key"], locale, **params)
        return payload["text"]

    @staticmethod
    def _button_label(btn: Button, locale: str) -> str:
        if btn.label_key is not None:
            return t(btn.label_key, locale)
        return cast(str, btn.label)

    @classmethod
    def _append_markup_text(cls, text: str, markup: Markup, locale: str) -> str:
        lines = [text.rstrip(), ""]
        index = 1
        for row in markup.rows:
            for btn in row:
                label = cls._button_label(btn, locale)
                if btn.url is not None:
                    lines.append(f"{label}: {btn.url}")
                else:
                    lines.append(f"{index}. {label}")
                    index += 1
        return "\n".join(lines).rstrip()

    @staticmethod
    def _plain_text(text: str) -> str:
        plain = html.unescape(text)
        for token in ("**", "__", "`", "*", "_"):
            plain = plain.replace(token, "")
        return plain

    def _chunk_text(self, text: str) -> list[str]:
        if len(text) <= self._text_limit:
            return [text]

        chunks: list[str] = []
        remaining = text
        while len(remaining) > self._text_limit:
            split_at = remaining.rfind("\n", 0, self._text_limit + 1)
            if split_at <= 0:
                split_at = self._text_limit
            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()
        if remaining:
            chunks.append(remaining)
        return chunks


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@register_sender("zalo")
def _zalo_factory() -> ZaloSender:
    text_limit = int(os.environ.get("ZALO_TEXT_LIMIT", str(_DEFAULT_TEXT_LIMIT)))
    return ZaloSender(
        access_token=os.environ.get("ZALO_OA_ACCESS_TOKEN", ""),
        refresh_token=os.environ.get("ZALO_OA_REFRESH_TOKEN", ""),
        app_id=os.environ.get("ZALO_APP_ID", ""),
        secret_key=os.environ.get("ZALO_OA_SECRET_KEY", ""),
        text_limit=text_limit,
        auto_refresh=_env_bool("ZALO_AUTO_REFRESH"),
    )
