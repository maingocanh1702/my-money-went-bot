"""Zalo webhook parsing and dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any

from core import db, messenger
from core.handlers.categorize import handle_numbered_category_reply
from core.handlers.start import handle_start
from core.logging import get_logger
from i18n import t

log = get_logger(__name__, component="zalo_webhook")


@dataclass(frozen=True)
class ZaloTextEvent:
    sender_id: str
    text: str
    event_name: str


def is_zalo_enabled() -> bool:
    return _env_bool("ZALO_ENABLED") or _env_bool("ZALO_INTERACTIVE")


def verify_zalo_signature(raw_body: bytes, headers: dict[str, str]) -> bool:
    """Verify a conservative HMAC signature when a secret is configured.

    Zalo fixture validation is still required before production rollout.
    Until then, prod/staging must either provide a secret that matches this
    candidate check or explicitly opt into `ZALO_ALLOW_UNVERIFIED_WEBHOOK`.
    """
    secret = os.environ.get("ZALO_OA_SECRET_KEY", "")
    if not secret:
        app_env = os.environ.get("APP_ENV", "dev").lower()
        if app_env in {"prod", "production", "staging"}:
            return _env_bool("ZALO_ALLOW_UNVERIFIED_WEBHOOK")
        return True

    signature = headers.get("x-zevent-signature") or headers.get("x-zalo-signature") or ""
    if not signature:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    normalized = signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(normalized, digest)


def parse_zalo_text_event(body: dict[str, Any]) -> ZaloTextEvent | None:
    event_name = str(body.get("event_name") or "")
    if event_name != "user_send_text":
        return None

    sender = body.get("sender")
    message = body.get("message")
    if not isinstance(sender, dict) or not isinstance(message, dict):
        return None

    sender_id = str(sender.get("id") or "")
    text = str(message.get("text") or "").strip()
    if not sender_id or not text:
        return None
    return ZaloTextEvent(sender_id=sender_id, text=text, event_name=event_name)


async def handle_zalo_text_event(event: ZaloTextEvent) -> None:
    if event.text.strip().lower() == "/start":
        await handle_start(
            channel_type="zalo",
            channel_user_id=event.sender_id,
            channel_chat_id=event.sender_id,
        )
        return

    user_id = await _resolve_user_id(event.sender_id)
    if user_id is None:
        await handle_start(
            channel_type="zalo",
            channel_user_id=event.sender_id,
            channel_chat_id=event.sender_id,
        )
        return

    if await handle_numbered_category_reply(user_id, event.text):
        return

    locale = await _resolve_locale(user_id)
    await messenger.send(
        user_id,
        {
            "text": t(locale, "categorize.help_fallback"),
            "parse_mode": "plain",
        },
    )


async def _resolve_user_id(sender_id: str) -> int | None:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM users
            WHERE channel_type = 'zalo'
              AND (channel_user_id = $1 OR channel_chat_id = $1)
            ORDER BY id
            LIMIT 1;
            """,
            sender_id,
        )
    if row is None:
        return None
    return int(row["id"])


def loads_body(raw_body: bytes) -> dict[str, Any] | None:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


async def _resolve_locale(user_id: int) -> str:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT locale FROM users WHERE id = $1;", user_id)
    return str(row["locale"]) if row else "vi"


__all__ = [
    "ZaloTextEvent",
    "handle_zalo_text_event",
    "is_zalo_enabled",
    "loads_body",
    "parse_zalo_text_event",
    "verify_zalo_signature",
]
