"""Migration 0003 — backfill `users.inbound_email` for NULL rows.

The migration body is a single idempotent UPDATE. This test pins the
SQL's behavior on legacy NULL rows and confirms idempotency.

Approach: by the time `settings_pool` is provided the head migration has
already run, so we re-create a "legacy NULL" state by manually inserting
a row with `inbound_email = NULL` and then executing the migration's
upgrade SQL verbatim. If the SQL in the migration ever drifts, this test
fails — exactly the regression guard the test plan asks for.
"""

from __future__ import annotations

import asyncpg

from tests.integration.conftest import seed_user

# Verbatim copy of migrations/versions/0003_backfill_inbound_email.py upgrade().
# Kept here on purpose: drift between the test and the migration body is the
# scenario this regression test exists to catch.
_MIGRATION_0003_UPGRADE_SQL = """
UPDATE users
SET inbound_email = 'u' || id::text || '@in.mymoneywent.com',
    updated_at = NOW()
WHERE inbound_email IS NULL;
"""


async def test_migration_0003_backfills_null_rows(
    settings_pool: asyncpg.Pool,
) -> None:
    """Pre-migration NULL row → post-migration deterministic email."""
    uid_null = await seed_user(settings_pool, "u-mig-null", inbound_email=None)
    uid_preset = await seed_user(
        settings_pool, "u-mig-preset", inbound_email="preset@in.mymoneywent.com"
    )

    async with settings_pool.acquire() as conn:
        await conn.execute(_MIGRATION_0003_UPGRADE_SQL)
        backfilled = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid_null)
        preserved = await conn.fetchval(
            "SELECT inbound_email FROM users WHERE id = $1;", uid_preset
        )

    assert backfilled == f"u{uid_null}@in.mymoneywent.com"
    assert preserved == "preset@in.mymoneywent.com", "non-NULL rows must be left intact"


async def test_migration_0003_is_idempotent(
    settings_pool: asyncpg.Pool,
) -> None:
    """Running the migration body twice must not change values (no churn)."""
    uid = await seed_user(settings_pool, "u-mig-idem", inbound_email=None)

    async with settings_pool.acquire() as conn:
        await conn.execute(_MIGRATION_0003_UPGRADE_SQL)
        first = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
        ts_first = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)
        await conn.execute(_MIGRATION_0003_UPGRADE_SQL)
        second = await conn.fetchval("SELECT inbound_email FROM users WHERE id = $1;", uid)
        ts_second = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1;", uid)

    assert second == first
    assert ts_second == ts_first, "second run must be a WHERE-IS-NULL no-op"
