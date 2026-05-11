"""2-user tenant isolation — the HARD invariant for SaaS-multi-tenant code.

This is THE test that every subsequent feature wave will lean on. If a
query forgets to filter by user_id, this test catches the leak.

Scenario:
  1. Seed user A + user B, each with 2 transactions.
  2. Run a "list my transactions" query filtered by user_id.
  3. Assert user A sees ONLY user A rows, user B sees ONLY user B rows.
  4. Use the assert_tenant_isolated() helper from conftest.

Bonus: also tests that ON DELETE CASCADE actually severs cross-tenant
references via the users → transactions FK chain (not a leak per se,
but a sanity check on the schema).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import asyncpg
import pytest

from core import db, tenant_context
from tests.conftest import assert_tenant_isolated


@pytest.fixture
async def pool(pg_url_async: str, migrated_db: str) -> AsyncIterator[asyncpg.Pool]:
    """Init an asyncpg pool against the migrated DB, tear down after."""
    _ = migrated_db  # ensure alembic upgrade ran
    await db.close_pool()
    pool = await db.create_pool(pg_url_async, min_size=2, max_size=5)
    yield pool
    await db.close_pool()


async def _seed_user(pool: asyncpg.Pool, channel_user_id: str, display_name: str) -> int:
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                """
                INSERT INTO users (channel_type, channel_user_id, display_name)
                VALUES ('telegram', $1, $2)
                RETURNING id;
                """,
                channel_user_id,
                display_name,
            )
        )


async def _seed_tx(pool: asyncpg.Pool, user_id: int, amount: int, ref: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transactions
                (user_id, tx_date, direction, amount, ref_code, source, month_key)
            VALUES ($1, NOW(), 'out', $2, $3, 'sepay', '2026-05');
            """,
            user_id,
            amount,
            ref,
        )


async def _clean(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")


async def test_user_a_query_returns_only_user_a_rows(pool: asyncpg.Pool) -> None:
    """The core isolation rule: a user-scoped SELECT never leaks rows."""
    await _clean(pool)
    a = await _seed_user(pool, "a-100", "Alice")
    b = await _seed_user(pool, "b-200", "Bob")
    await _seed_tx(pool, a, 10_000, "A-1")
    await _seed_tx(pool, a, 20_000, "A-2")
    await _seed_tx(pool, b, 50_000, "B-1")
    await _seed_tx(pool, b, 70_000, "B-2")

    # Simulate request entering as user A
    tenant_context.set_tenant(a)
    user_id = tenant_context.get_user_id()
    assert user_id == a

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_id, amount, ref_code FROM transactions WHERE user_id = $1;",
            user_id,
        )

    rows_dict = [dict(r) for r in rows]
    assert len(rows_dict) == 2
    assert_tenant_isolated(rows_dict, expected_user_id=a)
    amounts = sorted(r["amount"] for r in rows_dict)
    assert amounts == [10_000, 20_000]

    tenant_context.clear_tenant()


async def test_user_b_query_returns_only_user_b_rows(pool: asyncpg.Pool) -> None:
    """Mirror of the above — flipping tenant context returns the other set."""
    await _clean(pool)
    a = await _seed_user(pool, "a-101", "Alice")
    b = await _seed_user(pool, "b-201", "Bob")
    await _seed_tx(pool, a, 10_000, "A-1")
    await _seed_tx(pool, b, 50_000, "B-1")
    await _seed_tx(pool, b, 70_000, "B-2")

    tenant_context.set_tenant(b)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_id, amount FROM transactions WHERE user_id = $1;",
            tenant_context.get_user_id(),
        )

    rows_dict = [dict(r) for r in rows]
    assert len(rows_dict) == 2
    assert_tenant_isolated(rows_dict, expected_user_id=b)
    tenant_context.clear_tenant()


async def test_tenant_context_isolation_under_concurrent_tasks(
    pool: asyncpg.Pool,
) -> None:
    """ContextVar must isolate values per asyncio task — no cross-task leak.

    This proves we can run handlers for many users concurrently without
    a request leaking another user's tenant context.
    """
    await _clean(pool)
    a = await _seed_user(pool, "a-c1", "Alice")
    b = await _seed_user(pool, "b-c2", "Bob")
    await _seed_tx(pool, a, 11_111, "A-x")
    await _seed_tx(pool, b, 22_222, "B-x")

    async def query_as(user_id: int) -> list[int]:
        tenant_context.set_tenant(user_id)
        async with pool.acquire() as conn:
            # Re-read tenant context AFTER the await — proves it survived.
            await asyncio.sleep(0.01)
            rows = await conn.fetch(
                "SELECT amount FROM transactions WHERE user_id = $1;",
                tenant_context.get_user_id(),
            )
        return [int(r["amount"]) for r in rows]

    results = await asyncio.gather(query_as(a), query_as(b), query_as(a))
    assert results[0] == [11_111]
    assert results[1] == [22_222]
    assert results[2] == [11_111]


async def test_get_user_id_raises_when_unset() -> None:
    """Hard fail on missing tenant context — never default silently."""
    tenant_context.clear_tenant()
    with pytest.raises(LookupError, match="user_id not set"):
        tenant_context.get_user_id()


async def test_set_tenant_returns_request_id_and_generates_uuid() -> None:
    """set_tenant returns the request_id; generates UUID4 hex if None."""
    tenant_context.clear_tenant()
    rid = tenant_context.set_tenant(42)
    assert len(rid) == 32  # uuid4 hex
    assert tenant_context.get_request_id() == rid

    tenant_context.clear_tenant()
    rid2 = tenant_context.set_tenant(42, request_id="my-correlation-id")
    assert rid2 == "my-correlation-id"
    assert tenant_context.get_request_id() == "my-correlation-id"

    tenant_context.clear_tenant()


async def test_set_tenant_rejects_invalid_user_id() -> None:
    """user_id must be positive — zero/negative is a programming error."""
    with pytest.raises(ValueError):
        tenant_context.set_tenant(0)
    with pytest.raises(ValueError):
        tenant_context.set_tenant(-1)


async def test_delete_user_cascades_transactions(pool: asyncpg.Pool) -> None:
    """Sanity check: ON DELETE CASCADE on users(id) actually clears tx."""
    await _clean(pool)
    a = await _seed_user(pool, "a-del", "Alice")
    b = await _seed_user(pool, "b-del", "Bob")
    await _seed_tx(pool, a, 1, "A-del")
    await _seed_tx(pool, b, 2, "B-del")

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1;", a)
        remaining = await conn.fetch("SELECT user_id FROM transactions;")

    rows_dict = [dict(r) for r in remaining]
    assert_tenant_isolated(rows_dict, expected_user_id=b)
