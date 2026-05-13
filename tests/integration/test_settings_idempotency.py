"""F07 — retry / idempotency tests.

Spec slice (autopilot:test_plan / retry_idempotency).

  - test_recap_toggle_idempotent_on_same_value: N/A — F07 handler exposes
    a toggle (flip), not a set-to-value endpoint. There is no "ON→ON"
    surface to be idempotent over; flipping twice is by definition a
    round-trip back to the starting value. The spec test was written
    assuming a `set_recap(value)` endpoint that the pilot does not ship.

  - test_locale_change_idempotent_same_locale: pinned below.
  - test_regen_is_not_idempotent_by_design: pinned below.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from handlers.settings import handle_settings_callback
from tests.integration.conftest import count_analytics_events, seed_user


async def test_recap_toggle_round_trip_double_flip_back_to_origin(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Two toggles → original value; each toggle emits one analytics event.

    Replaces the spec's `test_recap_toggle_idempotent_on_same_value` —
    documents real toggle semantics so any future "set" refactor does
    not silently change behaviour.
    """
    uid = await seed_user(settings_pool, "u-recap-idem", daily_recap_enabled=True)

    await handle_settings_callback(uid, "settings:recap_toggle")
    await handle_settings_callback(uid, "settings:recap_toggle")

    async with settings_pool.acquire() as conn:
        final = await conn.fetchval("SELECT daily_recap_enabled FROM users WHERE id = $1;", uid)
    assert final is True  # back to origin
    assert await count_analytics_events(settings_pool, uid, "settings_recap_toggled") == 2


async def test_locale_change_idempotent_same_locale(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Picking the already-active locale: no DB write, no analytics event."""
    # Seed with inbound_email pre-set so get_overview doesn't backfill
    # (backfill itself advances updated_at — a separate, expected effect).
    uid = await seed_user(
        settings_pool,
        "u-lang-idem",
        locale="vi",
        inbound_email="u-lang-idem@in.mymoneywent.com",
    )

    async with settings_pool.acquire() as conn:
        ts_before = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)

    await handle_settings_callback(uid, "settings:lang_set:vi")

    async with settings_pool.acquire() as conn:
        locale_after = await conn.fetchval("SELECT locale FROM users WHERE id = $1;", uid)
        ts_after = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)

    assert locale_after == "vi"
    # No-op semantics: updated_at must not advance.
    assert ts_after == ts_before
    # Zero language-change analytics events.
    assert await count_analytics_events(settings_pool, uid, "settings_language_changed") == 0


async def test_regen_is_not_idempotent_by_design(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Two regen calls → two distinct token_hash values.

    Pins G2: regenerate is intentionally non-idempotent. A future
    "idempotent regen" refactor (e.g. returning the same token twice in
    a window) must break this test loudly — old plaintext would still
    be live, which is the whole bug we are avoiding.
    """
    uid = await seed_user(settings_pool, "u-regen-idem")

    await handle_settings_callback(uid, "settings:regen")
    async with settings_pool.acquire() as conn:
        hash1 = await conn.fetchval(
            "SELECT token_hash FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )

    await handle_settings_callback(uid, "settings:regen")
    async with settings_pool.acquire() as conn:
        hash2 = await conn.fetchval(
            "SELECT token_hash FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert hash1 != hash2
    # Two emitted analytics events — one per regen, never deduped.
    assert (await count_analytics_events(settings_pool, uid, "settings_webhook_regenerated")) == 2
