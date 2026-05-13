"""F07 — missing-optional-fields tests.

Spec slice (autopilot:test_plan / missing_optional_fields):

  - test_settings_overview_with_free_plan_no_trial
  - test_get_overview_with_null_inbound_email_returns_none (pure-read; G4 2026-05-13)
  - test_get_overview_does_not_mutate_inbound_email_when_null (pure-read regression guard)
  - test_user_with_no_bank_connections_no_bank_row
  - test_settings_for_user_with_null_locale_falls_back
"""

from __future__ import annotations

from typing import Any

import asyncpg

from core.settings_svc import _coerce_locale, fallback_inbound_email, get_overview
from handlers.settings import handle_settings_command
from tests.integration.conftest import seed_user


def _last_text(send_calls: list[dict[str, Any]]) -> str:
    for entry in reversed(send_calls):
        if "text" in entry["payload"]:
            return str(entry["payload"]["text"])
    raise AssertionError("no overview send captured")


async def test_settings_overview_with_free_plan_no_trial(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Free plan + NULL trial/expiry → '📋 Plan: Free' alone (no suffix)."""
    uid = await seed_user(
        settings_pool,
        "u-free",
        locale="en",
        plan="free",
        trial_ends_at=None,
        plan_expires_at=None,
        inbound_email="u-free@in.mymoneywent.com",
    )
    await handle_settings_command(uid)
    text = _last_text(send_calls)
    assert "📋 Plan: Free" in text
    assert "trial" not in text.lower()
    assert "expired" not in text.lower()
    assert "days left" not in text.lower()


async def test_get_overview_with_null_inbound_email_returns_none(
    settings_pool: asyncpg.Pool,
) -> None:
    """Post-G4 refactor: get_overview is PURE READ.

    NULL inbound_email is returned as None (no implicit backfill). The UI
    layer renders the deterministic fallback string — verified by
    `test_get_overview_renders_fallback_for_null_inbound_email` below.
    """
    uid = await seed_user(settings_pool, "u-pure-read-null", inbound_email=None)

    overview = await get_overview(uid)

    assert overview.inbound_email is None


async def test_get_overview_does_not_mutate_inbound_email_when_null(
    settings_pool: asyncpg.Pool,
) -> None:
    """Pure-read regression guard — no write side-effect on NULL row.

    Prior to G4 refactor (R2/R3 root cause), `get_overview` backfilled
    `users.inbound_email` on read. This test pins the new contract:
    repeated calls leave the column NULL.
    """
    uid = await seed_user(settings_pool, "u-pure-read-noop", inbound_email=None)

    async with settings_pool.acquire() as conn:
        updated_before = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)

    # Two reads — would have generated two UPDATEs in the old code.
    await get_overview(uid)
    await get_overview(uid)

    async with settings_pool.acquire() as conn:
        email_after = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
        updated_after = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)
    assert email_after is None, "get_overview must NOT backfill inbound_email"
    assert updated_after == updated_before, "get_overview must NOT bump updated_at"


async def test_get_overview_renders_fallback_for_null_inbound_email(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """UI layer surfaces the deterministic fallback for NULL inbound_email."""
    uid = await seed_user(settings_pool, "u-render-fallback", inbound_email=None)

    await handle_settings_command(uid)

    text = _last_text(send_calls)
    assert fallback_inbound_email(uid) in text
    # Row stays NULL — UI fallback is display-only, no write.
    async with settings_pool.acquire() as conn:
        stored = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
    assert stored is None


async def test_user_with_no_bank_connections_no_bank_row(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """G8: bank-connections row is deferred from F07 pilot.

    Acceptance criteria do NOT require a bank row; the overview text
    must therefore not surface a bank-connections label.
    """
    uid = await seed_user(settings_pool, "u-no-bank", inbound_email="u-banks@in.mymoneywent.com")
    await handle_settings_command(uid)
    text = _last_text(send_calls)
    # Look for the bank-row labels we'd emit if G8 ever flipped: a vi/en
    # row prefix in the overview. Substring search on bare "bank" would
    # collide with the inbound email mailbox, so anchor on the row glyph.
    assert "🏦" not in text
    assert "Bank connection" not in text
    assert "Ngân hàng" not in text


async def test_settings_for_user_with_null_locale_falls_back() -> None:
    """users.locale has a NOT NULL CHECK constraint, so NULL is impossible
    via the DB; settings_svc still has a defensive fallback because asyncpg
    may return None if a row mutates between SELECT roundtrips. Pin the
    fallback path directly via the pure helper.
    """
    assert _coerce_locale(None) == "vi"
    assert _coerce_locale("zz") == "vi"  # unknown locale → default
    assert _coerce_locale("vi") == "vi"
    assert _coerce_locale("en") == "en"
