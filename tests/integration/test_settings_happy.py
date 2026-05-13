"""F07 — happy-path integration tests.

Spec slice (autopilot:test_plan / happy_path):
  - test_settings_overview_renders_all_rows (+ en variant)
  - test_regen_webhook_token_replaces_row
  - test_change_timezone_valid
  - test_toggle_recap_on_off_on
  - test_change_language_vi_to_en_rerenders

Fixtures `settings_pool` + `send_calls` come from tests/integration/conftest.py.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from handlers.settings import (
    handle_settings_callback,
    handle_settings_command,
    handle_timezone_input,
)
from tests.integration.conftest import seed_user


def _last_text(send_calls: list[dict[str, Any]]) -> str:
    """Return the text body of the most recent overview send (one with `text`)."""
    for entry in reversed(send_calls):
        if "text" in entry["payload"]:
            return str(entry["payload"]["text"])
    raise AssertionError("no overview send captured")


async def test_settings_overview_renders_all_rows(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """/settings renders webhook/email/timezone/recap/plan/locale in vi."""
    uid = await seed_user(
        settings_pool,
        "u-overview-vi",
        locale="vi",
        timezone="Asia/Ho_Chi_Minh",
        daily_recap_enabled=True,
        plan="free",
    )
    await handle_settings_command(uid)
    text = _last_text(send_calls)
    assert "⚙️ Cài đặt" in text
    assert "🔗 Webhook: chưa thiết lập" in text
    assert "📧 Email: u" in text and "@in.mymoneywent.com" in text
    assert "🌐 Timezone: Asia/Ho_Chi_Minh" in text
    assert "🌙 Tóm tắt ngày: ✅ Bật" in text
    assert "📋 Gói: Free" in text
    assert "🌐 Ngôn ngữ: 🇻🇳" in text


async def test_settings_overview_renders_en_locale(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Same overview keys render in English for locale=en users."""
    uid = await seed_user(settings_pool, "u-overview-en", locale="en", plan="free")
    await handle_settings_command(uid)
    text = _last_text(send_calls)
    assert "⚙️ Settings" in text
    assert "📋 Plan: Free" in text
    assert "🌐 Language: 🇬🇧 English" in text


async def test_regen_webhook_token_replaces_row(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """settings:regen mints a fresh token; UNIQUE(user_id, kind) keeps 1 row."""
    uid = await seed_user(settings_pool, "u-regen", locale="vi")

    await handle_settings_callback(uid, "settings:regen")
    async with settings_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT token_hash, display_suffix FROM webhook_tokens "
            "WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert len(rows) == 1
    first_hash = rows[0]["token_hash"]
    first_suffix = rows[0]["display_suffix"]
    assert first_hash and first_suffix

    await handle_settings_callback(uid, "settings:regen")
    async with settings_pool.acquire() as conn:
        rows2 = await conn.fetch(
            "SELECT token_hash, display_suffix FROM webhook_tokens "
            "WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert len(rows2) == 1
    assert rows2[0]["token_hash"] != first_hash
    assert rows2[0]["display_suffix"] != first_suffix


async def test_change_timezone_valid(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """handle_timezone_input with a valid IANA tz persists + re-renders."""
    uid = await seed_user(settings_pool, "u-tz", timezone="Asia/Ho_Chi_Minh", locale="en")
    ok = await handle_timezone_input(uid, raw_tz="Asia/Tokyo", old_tz="Asia/Ho_Chi_Minh")
    assert ok is True

    async with settings_pool.acquire() as conn:
        tz = await conn.fetchval("SELECT timezone FROM users WHERE id = $1;", uid)
    assert tz == "Asia/Tokyo"
    text = _last_text(send_calls)
    assert "Asia/Tokyo" in text


async def test_toggle_recap_on_off_on(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """recap toggle flips on each call: ON → OFF → ON."""
    uid = await seed_user(settings_pool, "u-recap", daily_recap_enabled=True)

    async def current() -> bool:
        async with settings_pool.acquire() as conn:
            return bool(
                await conn.fetchval("SELECT daily_recap_enabled FROM users WHERE id = $1;", uid)
            )

    await handle_settings_callback(uid, "settings:recap_toggle")
    assert await current() is False
    await handle_settings_callback(uid, "settings:recap_toggle")
    assert await current() is True


async def test_change_language_vi_to_en_rerenders(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """settings:lang_set:en updates users.locale; overview re-renders in en."""
    uid = await seed_user(settings_pool, "u-lang", locale="vi")
    await handle_settings_callback(uid, "settings:lang_set:en")

    async with settings_pool.acquire() as conn:
        locale = await conn.fetchval("SELECT locale FROM users WHERE id = $1;", uid)
    assert locale == "en"

    text = _last_text(send_calls)
    assert "⚙️ Settings" in text
    assert "🌐 Language: 🇬🇧 English" in text
