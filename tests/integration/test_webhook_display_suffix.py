"""W0.8 — `display_suffix` column on `webhook_tokens` (G3 option b).

5-category coverage matrix:

  1. Happy path        — test_mint_token_populates_display_suffix
  2. Happy path (idem) — test_regenerate_updates_display_suffix
  3. Missing-optional  — test_legacy_row_with_null_display_suffix
  4. Pathological      — test_short_raw_token_does_not_overflow_column

# Category 4 (retry/idempotency): N/A — mint_token's idempotency is
# already covered by test_regenerate_updates_display_suffix (Category 2);
# there is no retry surface that the suffix changes.

# Category 5 (concurrent): N/A — UNIQUE(user_id, kind) constraint makes
# concurrent mint a serialization concern owned by the existing
# webhook_tokens table tests in test_migrations.py, not specific to the
# display_suffix column.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest

from core import db
from markets.vn.capture.webhook_tokens import (
    get_display_suffix,
    hash_token,
    mint_token,
    resolve_token,
)


@pytest.fixture
async def pool(pg_url_async: str, migrated_db: str) -> AsyncIterator[asyncpg.Pool]:
    _ = migrated_db
    await db.close_pool()
    pool = await db.create_pool(pg_url_async, min_size=1, max_size=3)
    yield pool
    await db.close_pool()


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


async def _clean(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")
        await conn.execute("TRUNCATE webhook_tokens RESTART IDENTITY CASCADE;")


# ── Category 1: Happy path ────────────────────────────────────────────


async def test_mint_token_populates_display_suffix(pool: asyncpg.Pool) -> None:
    """Happy path: mint_token writes raw[-6:] to display_suffix; reader returns it."""
    await _clean(pool)
    uid = await _seed_user(pool, "u-suffix-1")

    raw = await mint_token(uid, kind="sepay")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT display_suffix FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert row is not None
    assert row["display_suffix"] == raw[-6:]

    assert await get_display_suffix(uid, kind="sepay") == raw[-6:]


# ── Category 2: Happy path — regenerate (idempotency / ON CONFLICT) ──


async def test_regenerate_updates_display_suffix(pool: asyncpg.Pool) -> None:
    """Re-minting (user, kind) overwrites display_suffix and keeps single row."""
    await _clean(pool)
    uid = await _seed_user(pool, "u-suffix-2")

    raw1 = await mint_token(uid, kind="sepay")
    suffix1 = raw1[-6:]
    assert await get_display_suffix(uid, kind="sepay") == suffix1

    raw2 = await mint_token(uid, kind="sepay")
    suffix2 = raw2[-6:]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT display_suffix FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert len(rows) == 1, "ON CONFLICT must keep exactly one row per (user, kind)"
    assert rows[0]["display_suffix"] == suffix2
    # token_urlsafe(24) collisions on tail-6 are astronomically unlikely.
    assert suffix1 != suffix2

    # Old raw token must no longer auth; new one must.
    assert await resolve_token(raw1, kind="sepay") is None
    assert await resolve_token(raw2, kind="sepay") == uid


# ── Category 3: Missing-optional — legacy NULL row ────────────────────


async def test_legacy_row_with_null_display_suffix(pool: asyncpg.Pool) -> None:
    """Pre-migration rows have display_suffix NULL; auth works, reader returns None."""
    await _clean(pool)
    uid = await _seed_user(pool, "u-suffix-3")

    # Simulate a pre-migration row: token_hash present, display_suffix NULL.
    raw = "legacy-token-pre-migration-0002-xyz"
    token_hash = hash_token(raw)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webhook_tokens (user_id, kind, token_hash, display_suffix)
            VALUES ($1, 'sepay', $2, NULL);
            """,
            uid,
            token_hash,
        )

    # Auth path is unaffected.
    assert await resolve_token(raw, kind="sepay") == uid
    # F07 reader must tolerate NULL and return None.
    assert await get_display_suffix(uid, kind="sepay") is None


# ── Pathological — short raw token does not overflow VARCHAR(8) ──────


async def test_short_raw_token_does_not_overflow_column(
    pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a future caller shortens the generator, _display_suffix falls back
    to the full raw; VARCHAR(8) tolerates it; mint succeeds."""
    await _clean(pool)
    uid = await _seed_user(pool, "u-suffix-4")

    # Force the raw token to be shorter than 6 chars.
    short_raw = "abcd"  # 4 chars
    monkeypatch.setattr(
        "markets.vn.capture.webhook_tokens.secrets.token_urlsafe",
        lambda _n: short_raw,
    )

    raw = await mint_token(uid, kind="sepay")
    assert raw == short_raw

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT display_suffix FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert row is not None
    # Fallback: full raw string when len < 6 (defensive branch in _display_suffix).
    assert row["display_suffix"] == short_raw

    # Second mint in rapid succession (ON CONFLICT path) — still safe.
    raw2 = await mint_token(uid, kind="sepay")
    assert raw2 == short_raw
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT display_suffix FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            uid,
        )
    assert len(rows) == 1
    assert rows[0]["display_suffix"] == short_raw
