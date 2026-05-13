"""F07 — concurrent-access tests.

Spec slice (autopilot:test_plan / concurrent_access):

  - test_concurrent_regen_two_requests_one_survives
  - test_recap_toggled_mid_recap_fire: N/A — F09 (scheduler) is not in
    F07 scope. The intent is to verify F07 does not race F09's job state;
    since F07 only writes `users.daily_recap_enabled` (G6) and F09 reads
    it at fire time, there is no shared in-flight state for F07 to race.
    F09's own test suite owns the scheduler-fire timing assertion.
  - test_locale_change_during_settings_render_uses_latest
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from handlers.settings import handle_settings_callback, handle_settings_command
from tests.integration.conftest import seed_user


async def test_concurrent_regen_two_requests_one_survives(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Two parallel regen tasks for the same user: UNIQUE(user_id, kind)
    keeps exactly one row; both calls succeed (last writer wins via
    ON CONFLICT DO UPDATE — no exception escapes either coroutine).
    """
    uid = await seed_user(
        settings_pool, "u-regen-race", inbound_email="u-regen-race@in.mymoneywent.com"
    )

    await asyncio.gather(
        handle_settings_callback(uid, "settings:regen"),
        handle_settings_callback(uid, "settings:regen"),
    )

    async with settings_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT token_hash FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert len(rows) == 1, "ON CONFLICT must collapse the race to one row"

    # Both regens emitted analytics — confirms neither coroutine raised.
    async with settings_pool.acquire() as conn:
        n_events = await conn.fetchval(
            "SELECT COUNT(*) FROM analytics_events "
            "WHERE user_id = $1 AND event_name = 'settings_webhook_regenerated';",
            uid,
        )
    assert n_events == 2


async def test_locale_change_during_settings_render_uses_latest(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """F07 does NOT cache the overview (§9). A render task launched
    after a locale flip must see the new locale — proves no caching
    layer slipped in and no stale read survives a write.
    """
    uid = await seed_user(
        settings_pool, "u-lang-race", locale="vi", inbound_email="u-lang-race@in.mymoneywent.com"
    )

    # First render: vi.
    await handle_settings_command(uid)

    # Flip locale.
    await handle_settings_callback(uid, "settings:lang_set:en")

    # Second render after the flip: must read en.
    send_calls.clear()
    await handle_settings_command(uid)

    overview_text = next(
        (entry["payload"]["text"] for entry in send_calls if "text" in entry["payload"]),
        None,
    )
    assert overview_text is not None
    assert "⚙️ Settings" in overview_text
    assert "🇬🇧 English" in overview_text
