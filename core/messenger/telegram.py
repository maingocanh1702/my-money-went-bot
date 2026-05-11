"""Telegram messenger adapter.

Translates abstract `SendPayload` + `Markup` to Telegram Bot API calls
via httpx. Wave 6 will add Discord and Messenger adapters; their job
is to make the same `SendPayload` arrive at their respective APIs.
"""

from __future__ import annotations

import os
from typing import Any, cast

import httpx

from core import db

from .base import (
    PARSER_MODE_HTML,
    PARSER_MODE_MARKDOWN,
    PARSER_MODE_PLAIN,
    BaseSender,
    Button,
    Markup,
    SendPayload,
    register_sender,
)
from .i18n import t

_TG_BASE = "https://api.telegram.org"
_TG_PARSE_MODE_MAP = {
    PARSER_MODE_MARKDOWN: "MarkdownV2",
    PARSER_MODE_HTML: "HTML",
    PARSER_MODE_PLAIN: None,
}


class TelegramSender(BaseSender):
    """Posts messages to the Telegram Bot API."""

    channel_type = "telegram"

    def __init__(
        self,
        bot_token: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        api_base: str = _TG_BASE,
    ) -> None:
        if not bot_token:
            raise ValueError("TelegramSender: bot_token must be non-empty")
        self._bot_token = bot_token
        self._api_base = api_base
        # Caller-supplied client (tests inject a mock); else we own a fresh one.
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send(self, user_id: int, payload: SendPayload) -> None:
        chat_id = await self._resolve_chat_id(user_id)
        locale = payload.get("locale", "vi")
        text = self._resolve_text(payload, locale)
        body: dict[str, Any] = {"chat_id": chat_id, "text": text}

        parse_mode_tg = _TG_PARSE_MODE_MAP.get(payload.get("parse_mode", "plain"))
        if parse_mode_tg is not None:
            body["parse_mode"] = parse_mode_tg

        markup = payload.get("markup")
        if markup is not None:
            body["reply_markup"] = self._markup_to_telegram(markup, locale)

        url = f"{self._api_base}/bot{self._bot_token}/sendMessage"
        resp = await self._client.post(url, json=body)
        # Telegram returns 200 with {"ok": true, ...} on success.
        # Non-2xx OR ok=false → raise so callers / Sentry catch it.
        resp.raise_for_status()
        body_json = resp.json()
        if not body_json.get("ok", False):
            raise RuntimeError(f"Telegram API rejected sendMessage: {body_json!r}")

    async def _resolve_chat_id(self, user_id: int) -> int:
        """Telegram chat_id is stored on users.chat_id (or falls back to
        the legacy users.telegram_id for users seeded before multi-channel)."""
        pool = db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT chat_id, telegram_id FROM users WHERE id = $1;", user_id
            )
        if row is None:
            raise LookupError(f"user_id={user_id} not found")
        chat_id = row["chat_id"] or row["telegram_id"]
        if chat_id is None:
            raise LookupError(
                f"user_id={user_id} has no chat_id/telegram_id — " "cannot send Telegram message"
            )
        return cast(int, chat_id)

    @staticmethod
    def _resolve_text(payload: SendPayload, locale: str) -> str:
        if "text_key" in payload and payload["text_key"]:
            params = payload.get("text_params") or {}
            return t(payload["text_key"], locale, **params)
        return payload["text"]

    @staticmethod
    def _markup_to_telegram(markup: Markup, locale: str) -> dict[str, Any]:
        """Abstract Markup → InlineKeyboardMarkup."""
        rows: list[list[dict[str, Any]]] = []
        for row in markup.rows:
            tg_row: list[dict[str, Any]] = []
            for btn in row:
                tg_btn: dict[str, Any] = {
                    "text": TelegramSender._button_label(btn, locale),
                }
                if btn.callback_data is not None:
                    tg_btn["callback_data"] = btn.callback_data
                else:
                    tg_btn["url"] = btn.url
                tg_row.append(tg_btn)
            rows.append(tg_row)
        return {"inline_keyboard": rows}

    @staticmethod
    def _button_label(btn: Button, locale: str) -> str:
        if btn.label_key is not None:
            return t(btn.label_key, locale)
        return cast(str, btn.label)


@register_sender("telegram")
def _telegram_factory() -> TelegramSender:
    """Factory used by `messenger.send()` — reads TELEGRAM_BOT_TOKEN env."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    return TelegramSender(bot_token=token)
