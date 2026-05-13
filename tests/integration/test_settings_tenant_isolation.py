"""F07 — tenant-isolation tests (MANDATORY per dev-workflow §2.4).

Spec slice (autopilot:test_plan / tenant_isolation):

  - test_user_a_cannot_read_user_b_settings
  - test_user_a_cannot_regenerate_user_b_webhook_token

Both tests rely on the handler contract: `user_id` is the authenticated
session user, ALWAYS — never read from callback `data`. If a future
refactor ever introduces a user_id parse out of `data`, these tests
should break loudly.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from core.settings_svc import get_overview, set_locale, set_timezone, toggle_recap
from handlers.settings import handle_settings_callback
from tests.integration.conftest import seed_user


async def test_user_a_cannot_read_user_b_settings(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """get_overview is scoped WHERE u.id = $1; cross-tenant read returns
    only the authed user's row, regardless of what `data` claims."""
    a = await seed_user(
        settings_pool,
        "u-iso-a",
        locale="vi",
        timezone="Asia/Ho_Chi_Minh",
        inbound_email="u-iso-a@in.mymoneywent.com",
    )
    b = await seed_user(
        settings_pool,
        "u-iso-b",
        locale="en",
        timezone="Europe/London",
        inbound_email="u-iso-b@in.mymoneywent.com",
    )

    ov_a = await get_overview(a)
    ov_b = await get_overview(b)

    assert ov_a.user_id == a
    assert ov_a.locale == "vi"
    assert ov_a.timezone == "Asia/Ho_Chi_Minh"
    assert ov_a.inbound_email == "u-iso-a@in.mymoneywent.com"

    assert ov_b.user_id == b
    assert ov_b.locale == "en"
    assert ov_b.timezone == "Europe/London"
    assert ov_b.inbound_email == "u-iso-b@in.mymoneywent.com"

    # Crafted callback authed as A — overview rendered for A only.
    send_calls.clear()
    await handle_settings_callback(a, "settings:open")
    rendered = [e for e in send_calls if "text" in e["payload"]]
    assert all(e["user_id"] == a for e in rendered)
    text = rendered[-1]["payload"]["text"]
    assert "u-iso-a@in.mymoneywent.com" in text
    assert "u-iso-b@in.mymoneywent.com" not in text


async def test_user_a_cannot_regenerate_user_b_webhook_token(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """settings:regen on a session authed as A mints only A's token.

    Even if the callback `data` were "settings:regen?user_id=B", the
    handler parses neither field nor branches on data beyond the
    namespace prefix. mint_token receives A's id from the authed
    parameter, so B's token row is untouched.
    """
    a = await seed_user(settings_pool, "u-iso-rg-a", inbound_email="u-iso-rg-a@in.mymoneywent.com")
    b = await seed_user(settings_pool, "u-iso-rg-b", inbound_email="u-iso-rg-b@in.mymoneywent.com")

    # Pre-seed B with a token; capture its hash to detect mutation.
    await handle_settings_callback(b, "settings:regen")
    async with settings_pool.acquire() as conn:
        b_hash_before = await conn.fetchval(
            "SELECT token_hash FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            b,
        )
    assert b_hash_before is not None

    # A regenerates (authed as A; even crafted data referencing B has no effect).
    await handle_settings_callback(a, "settings:regen")

    async with settings_pool.acquire() as conn:
        a_hash = await conn.fetchval(
            "SELECT token_hash FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            a,
        )
        b_hash_after = await conn.fetchval(
            "SELECT token_hash FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            b,
        )
    assert a_hash is not None
    assert a_hash != b_hash_after  # A and B never collide
    assert b_hash_after == b_hash_before  # B's token untouched

    # webhook_tokens rows: exactly one per user, no cross-contamination.
    async with settings_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM webhook_tokens WHERE kind = 'sepay' ORDER BY user_id;"
        )
    assert sorted(r["user_id"] for r in rows) == sorted([a, b])


async def test_settings_svc_mutators_scope_writes_by_user_id(
    settings_pool: asyncpg.Pool,
) -> None:
    """Direct settings_svc mutator calls (set_timezone, toggle_recap,
    set_locale) update ONLY the user_id passed — a parallel B user's row
    must stay byte-identical."""
    a = await seed_user(
        settings_pool,
        "u-iso-mut-a",
        locale="vi",
        timezone="Asia/Ho_Chi_Minh",
        daily_recap_enabled=True,
        inbound_email="u-iso-mut-a@in.mymoneywent.com",
    )
    b = await seed_user(
        settings_pool,
        "u-iso-mut-b",
        locale="vi",
        timezone="Asia/Ho_Chi_Minh",
        daily_recap_enabled=True,
        inbound_email="u-iso-mut-b@in.mymoneywent.com",
    )

    async with settings_pool.acquire() as conn:
        b_before = dict(
            await conn.fetchrow(
                "SELECT locale, timezone, daily_recap_enabled FROM users WHERE id = $1;",
                b,
            )
        )

    assert await set_timezone(a, "Europe/London") is True
    assert await set_locale(a, "en") is True
    new_recap = await toggle_recap(a)
    assert new_recap is False

    async with settings_pool.acquire() as conn:
        b_after = dict(
            await conn.fetchrow(
                "SELECT locale, timezone, daily_recap_enabled FROM users WHERE id = $1;",
                b,
            )
        )
        a_after = dict(
            await conn.fetchrow(
                "SELECT locale, timezone, daily_recap_enabled FROM users WHERE id = $1;",
                a,
            )
        )

    assert b_after == b_before, "User B's row must not be touched by writes scoped to A"
    assert a_after == {"locale": "en", "timezone": "Europe/London", "daily_recap_enabled": False}
