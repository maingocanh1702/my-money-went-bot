"""DB pool lifecycle + sizing + exhaustion behaviour."""

from __future__ import annotations

import asyncio

import pytest

from core import db


@pytest.fixture
async def _pool_closed() -> None:
    """Ensure no leftover pool from prior test."""
    await db.close_pool()


@pytest.mark.usefixtures("_pool_closed")
async def test_create_get_close_roundtrip(pg_url_async: str) -> None:
    """Happy path: create_pool → get_pool returns it → close_pool nukes it."""
    pool = await db.create_pool(pg_url_async)
    assert pool is db.get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 AS one;")
        assert row is not None
        assert row["one"] == 1

    await db.close_pool()

    with pytest.raises(RuntimeError, match="not initialised"):
        db.get_pool()


@pytest.mark.usefixtures("_pool_closed")
async def test_double_init_raises(pg_url_async: str) -> None:
    """Calling create_pool twice without closing first must raise."""
    await db.create_pool(pg_url_async)
    with pytest.raises(RuntimeError, match="already initialised"):
        await db.create_pool(pg_url_async)
    await db.close_pool()


@pytest.mark.usefixtures("_pool_closed")
async def test_close_is_idempotent(pg_url_async: str) -> None:
    """close_pool() on already-closed pool is a no-op."""
    await db.create_pool(pg_url_async)
    await db.close_pool()
    await db.close_pool()  # must not raise


@pytest.mark.usefixtures("_pool_closed")
async def test_get_without_init_raises() -> None:
    """get_pool before create_pool raises RuntimeError, doesn't auto-create."""
    with pytest.raises(RuntimeError, match="not initialised"):
        db.get_pool()


@pytest.mark.usefixtures("_pool_closed")
async def test_pool_exhaustion_queues_does_not_crash(pg_url_async: str) -> None:
    """15 concurrent queries against a max_size=10 pool queue, don't crash.

    Proves asyncpg's built-in queueing works for us — we don't need a custom
    semaphore in app code.
    """
    pool = await db.create_pool(pg_url_async, min_size=2, max_size=10)

    async def one() -> int:
        async with pool.acquire() as conn:
            # tiny sleep so connections overlap and force queueing
            await asyncio.sleep(0.05)
            return int(await conn.fetchval("SELECT 1;"))

    results = await asyncio.gather(*(one() for _ in range(15)))
    assert results == [1] * 15
    assert pool.get_size() <= 10

    await db.close_pool()
