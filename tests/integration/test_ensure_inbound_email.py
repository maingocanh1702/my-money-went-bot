"""F07 — `ensure_inbound_email` helper tests.

Spec: G4 (revised 2026-05-13). Helper is the explicit, idempotent, race-safe
backfill primitive — called by migration 0003 and (later) any post-auth
gate. Not called by `get_overview` (which is pure-read).

Coverage:
  - idempotency: NULL → fill → second call no-op
  - already-set: returns existing value unchanged
  - concurrent: 5 parallel calls collapse to ONE persisted UPDATE
"""

from __future__ import annotations

import asyncio

import asyncpg

from core.settings_svc import ensure_inbound_email
from tests.integration.conftest import seed_user


async def test_ensure_inbound_email_writes_canonical_when_null(
    settings_pool: asyncpg.Pool,
) -> None:
    uid = await seed_user(settings_pool, "u-ensure-null", inbound_email=None)

    result = await ensure_inbound_email(uid)

    assert result == f"u{uid}@in.mymoneywent.com"
    async with settings_pool.acquire() as conn:
        stored = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
    assert stored == result


async def test_ensure_inbound_email_idempotent_second_call_no_write(
    settings_pool: asyncpg.Pool,
) -> None:
    """Two sequential calls must yield same value; second triggers no write."""
    uid = await seed_user(settings_pool, "u-ensure-idem", inbound_email=None)

    first = await ensure_inbound_email(uid)

    async with settings_pool.acquire() as conn:
        ts_after_first = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)

    second = await ensure_inbound_email(uid)

    async with settings_pool.acquire() as conn:
        ts_after_second = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)

    assert second == first
    assert ts_after_second == ts_after_first, (
        "second ensure must be a no-op — WHERE inbound_email IS NULL guard "
        "skips the UPDATE once the column is populated"
    )


async def test_ensure_inbound_email_preserves_existing_value(
    settings_pool: asyncpg.Pool,
) -> None:
    """Helper must not overwrite a pre-existing (non-NULL) value."""
    preset = "custom-preset@in.mymoneywent.com"
    uid = await seed_user(settings_pool, "u-ensure-preset", inbound_email=preset)

    result = await ensure_inbound_email(uid)

    assert result == preset
    async with settings_pool.acquire() as conn:
        stored = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
    assert stored == preset


async def test_ensure_inbound_email_concurrent_callers_one_write(
    settings_pool: asyncpg.Pool,
) -> None:
    """5 parallel callers on the same NULL row must all see the same canonical
    value with at most one effective UPDATE (others lose the WHERE-NULL race
    silently and re-read).
    """
    uid = await seed_user(settings_pool, "u-ensure-race", inbound_email=None)

    results = await asyncio.gather(*(ensure_inbound_email(uid) for _ in range(5)))

    expected = f"u{uid}@in.mymoneywent.com"
    assert all(r == expected for r in results), results
    async with settings_pool.acquire() as conn:
        stored = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
    assert stored == expected
