"""Phase 2 (C1) — `POST /webhooks/sepay/{token}` route + tenant isolation.

Asserts:
  - Valid token routes payload to correct user_id.
  - Two distinct users don't leak across each other.
  - Bad token returns 200 with no insert (no info leak).
  - Bad JSON body returns 200 with no insert.

Test strategy: bypass main's lifespan (which would create its own pool
and conflict with our fixture-managed pool). Use httpx.AsyncClient over
ASGITransport with lifespan disabled — the pool is owned by the test
fixture and `db.get_pool()` resolves to it inside the route handler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest

from core import db
from markets.vn.capture.webhook_tokens import mint_token


@pytest.fixture
async def pool(pg_url_async: str, migrated_db: str) -> AsyncIterator[asyncpg.Pool]:
    """Migrated DB pool, cleared between tests."""
    _ = migrated_db
    await db.close_pool()
    pool = await db.create_pool(pg_url_async, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")
        await conn.execute("TRUNCATE webhook_tokens RESTART IDENTITY CASCADE;")
    yield pool
    await db.close_pool()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """httpx client wired to main.app via ASGI transport, lifespan disabled.

    Lifespan is disabled because the pool fixture above owns pool lifecycle —
    if we let main's lifespan run, it would call `create_pool` again on the
    already-initialised pool and raise.
    """
    import main as main_module

    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_user(pool: asyncpg.Pool, channel_user_id: str) -> int:
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                """
                INSERT INTO users (channel_type, channel_user_id, display_name)
                VALUES ('telegram', $1, 'T') RETURNING id;
                """,
                channel_user_id,
            )
        )


def _payload(ref: str) -> dict[str, object]:
    return {
        "id": 1,
        "gateway": "TCB",
        "transactionDate": "2026-05-11 09:42:13",
        "accountNumber": "0123456789",
        "transferType": "in",
        "transferAmount": 50000,
        "content": "NAP TIEN",
        "referenceCode": ref,
    }


async def test_valid_token_routes_to_correct_user(
    pool: asyncpg.Pool, client: httpx.AsyncClient
) -> None:
    uid_a = await _seed_user(pool, "route-user-A")
    token_a = await mint_token(uid_a, kind="sepay")

    resp = await client.post(f"/webhooks/sepay/{token_a}", json=_payload("RT-A1"))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, ref_code FROM transactions WHERE user_id = $1;",
            uid_a,
        )
    assert len(rows) == 1
    assert rows[0]["ref_code"] == "RT-A1"
    assert rows[0]["user_id"] == uid_a


async def test_two_users_do_not_leak_across_each_other(
    pool: asyncpg.Pool, client: httpx.AsyncClient
) -> None:
    """Tenant isolation — the whole reason C1 exists."""
    uid_a = await _seed_user(pool, "iso-A")
    uid_b = await _seed_user(pool, "iso-B")
    token_a = await mint_token(uid_a, kind="sepay")
    token_b = await mint_token(uid_b, kind="sepay")

    await client.post(f"/webhooks/sepay/{token_a}", json=_payload("ISO-A"))
    await client.post(f"/webhooks/sepay/{token_b}", json=_payload("ISO-B"))

    async with pool.acquire() as conn:
        rows_a = await conn.fetch("SELECT ref_code FROM transactions WHERE user_id = $1;", uid_a)
        rows_b = await conn.fetch("SELECT ref_code FROM transactions WHERE user_id = $1;", uid_b)
    assert {r["ref_code"] for r in rows_a} == {"ISO-A"}
    assert {r["ref_code"] for r in rows_b} == {"ISO-B"}


async def test_bad_token_returns_200_no_insert(
    pool: asyncpg.Pool, client: httpx.AsyncClient
) -> None:
    """Invalid token → silent 200 (no info leak), no row inserted."""
    uid = await _seed_user(pool, "bad-token-user")
    await mint_token(uid, kind="sepay")  # mint, but don't use

    resp = await client.post(
        "/webhooks/sepay/definitely-not-a-real-token",
        json=_payload("BAD-TKN"),
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    async with pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM transactions;")
    assert cnt == 0


async def test_bad_json_body_returns_200_no_insert(
    pool: asyncpg.Pool, client: httpx.AsyncClient
) -> None:
    """Malformed JSON → silent 200 (preserves SePay retry budget)."""
    uid = await _seed_user(pool, "bad-body-user")
    token = await mint_token(uid, kind="sepay")

    resp = await client.post(
        f"/webhooks/sepay/{token}",
        content=b"not-json{{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    async with pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM transactions;")
    assert cnt == 0
