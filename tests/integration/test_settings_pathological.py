"""F07 — pathological-input tests.

Spec slice (autopilot:test_plan / pathological_inputs):

  - test_invalid_timezone_string_rejected
  - test_timezone_empty_string_rejected
  - test_timezone_sql_injection_shaped_input_rejected
  - test_settings_callback_other_user_id_blocked
  - test_extremely_long_timezone_string_rejected

Unit-level pure-function coverage for `is_valid_timezone` already lives
in tests/unit/test_settings_svc.py; these tests exercise the full
handler path (validation → no DB write → error message via messenger).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from handlers.settings import handle_settings_callback, handle_timezone_input
from tests.integration.conftest import seed_user


def _tz_invalid_sent(send_calls: list[dict[str, Any]]) -> bool:
    """True iff the captured send sequence contains a tz_invalid message."""
    return any(entry["payload"].get("text_key") == "settings.tz_invalid" for entry in send_calls)


async def test_invalid_timezone_string_rejected(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Unknown IANA name → False return + tz_invalid messenger reply + no DB write."""
    uid = await seed_user(
        settings_pool,
        "u-tz-bad",
        timezone="Asia/Ho_Chi_Minh",
        inbound_email="u-tz-bad@in.mymoneywent.com",
    )

    ok = await handle_timezone_input(uid, raw_tz="ABC", old_tz="Asia/Ho_Chi_Minh")
    assert ok is False
    assert _tz_invalid_sent(send_calls)

    async with settings_pool.acquire() as conn:
        tz = await conn.fetchval("SELECT timezone FROM users WHERE id = $1;", uid)
    assert tz == "Asia/Ho_Chi_Minh"  # untouched


async def test_timezone_empty_string_rejected(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    uid = await seed_user(
        settings_pool, "u-tz-empty", inbound_email="u-tz-empty@in.mymoneywent.com"
    )

    ok = await handle_timezone_input(uid, raw_tz="", old_tz="Asia/Ho_Chi_Minh")
    assert ok is False
    assert _tz_invalid_sent(send_calls)


async def test_timezone_sql_injection_shaped_input_rejected(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Membership check rejects SQLi-shaped strings before any DB call.

    Belt-and-braces: asyncpg parameterises queries, so even if validation
    were skipped the payload would land as a literal string in
    `users.timezone`. The point of this test is that validation rejects
    it *first* — no row mutation ever occurs.
    """
    uid = await seed_user(settings_pool, "u-tz-sqli", inbound_email="u-tz-sqli@in.mymoneywent.com")

    payload = "Asia/Ho_Chi_Minh'; DROP TABLE users; --"
    ok = await handle_timezone_input(uid, raw_tz=payload, old_tz="Asia/Ho_Chi_Minh")
    assert ok is False

    async with settings_pool.acquire() as conn:
        # Sanity: users table still exists, row unchanged.
        tz = await conn.fetchval("SELECT timezone FROM users WHERE id = $1;", uid)
        count = await conn.fetchval("SELECT COUNT(*) FROM users;")
    assert tz == "Asia/Ho_Chi_Minh"
    assert count == 1


async def test_extremely_long_timezone_string_rejected(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """10KB input falls out at the length gate; no DB write."""
    uid = await seed_user(settings_pool, "u-tz-long", inbound_email="u-tz-long@in.mymoneywent.com")

    ok = await handle_timezone_input(uid, raw_tz="X" * 10_000, old_tz="Asia/Ho_Chi_Minh")
    assert ok is False

    async with settings_pool.acquire() as conn:
        tz = await conn.fetchval("SELECT timezone FROM users WHERE id = $1;", uid)
    assert tz == "Asia/Ho_Chi_Minh"


async def test_settings_callback_other_user_id_blocked(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Forged callback data referencing another user is ignored.

    Two facts under test:
      1. The handler does NOT parse user_id from `data` — it always uses
         the authenticated `user_id` parameter. We prove this by sending
         crafted data of the form "settings:lang_set:en|user_id=B.id"
         while authed as A; the locale of A doesn't change (parser falls
         out at SUPPORTED_LOCALES membership), and B's locale is untouched.
      2. Any unknown sub-command (forged via injected fields) silently
         no-ops without raising — forward-compat clause in dispatcher.
    """
    a = await seed_user(
        settings_pool, "u-a-iso", locale="vi", inbound_email="u-a-iso@in.mymoneywent.com"
    )
    b = await seed_user(
        settings_pool, "u-b-iso", locale="vi", inbound_email="u-b-iso@in.mymoneywent.com"
    )

    forged = f"settings:lang_set:en|user_id={b}"
    await handle_settings_callback(a, forged)  # authed as A, data references B

    async with settings_pool.acquire() as conn:
        locale_a = await conn.fetchval("SELECT locale FROM users WHERE id = $1;", a)
        locale_b = await conn.fetchval("SELECT locale FROM users WHERE id = $1;", b)
    assert locale_a == "vi"  # malformed locale field rejected at membership
    assert locale_b == "vi"  # B never touched — handler scoped to authed A only

    # Unknown sub-command: silent no-op, no exception.
    await handle_settings_callback(a, "settings:nonsense_command_for_user_b")
    async with settings_pool.acquire() as conn:
        locale_a2 = await conn.fetchval("SELECT locale FROM users WHERE id = $1;", a)
    assert locale_a2 == "vi"
