"""SePay webhook + webhook_tokens lookup tests (Gap 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest

from core import db, tenant_context
from markets.vn.capture.sepay_webhook import handle_sepay_webhook
from markets.vn.capture.webhook_tokens import (
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


def test_hash_token_is_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    # SHA-256 hex is 64 chars
    assert len(hash_token("x")) == 64


def test_hash_token_rejects_empty() -> None:
    with pytest.raises(ValueError):
        hash_token("")


async def test_mint_then_resolve_returns_user(pool: asyncpg.Pool) -> None:
    await _clean(pool)
    uid = await _seed_user(pool, "user-1")
    raw = await mint_token(uid, kind="sepay")
    resolved = await resolve_token(raw, kind="sepay")
    assert resolved == uid


async def test_resolve_unknown_token_returns_none(pool: asyncpg.Pool) -> None:
    await _clean(pool)
    # No tokens minted at all — any raw value resolves to None.
    assert await resolve_token("doesnotexist", kind="sepay") is None


async def test_resolve_wrong_kind_returns_none(pool: asyncpg.Pool) -> None:
    await _clean(pool)
    uid = await _seed_user(pool, "user-1")
    raw = await mint_token(uid, kind="sepay")
    assert await resolve_token(raw, kind="email_inbound") is None


async def test_remint_overwrites_old_token(pool: asyncpg.Pool) -> None:
    """UNIQUE(user_id, kind) + ON CONFLICT UPDATE — second mint
    invalidates the first."""
    await _clean(pool)
    uid = await _seed_user(pool, "user-1")
    old_raw = await mint_token(uid, kind="sepay")
    new_raw = await mint_token(uid, kind="sepay")
    assert old_raw != new_raw
    assert await resolve_token(old_raw, kind="sepay") is None
    assert await resolve_token(new_raw, kind="sepay") == uid


async def test_webhook_persists_tx_on_valid_token(pool: asyncpg.Pool) -> None:
    """Valid token → CanonicalTx → row in transactions scoped to user."""
    await _clean(pool)
    uid = await _seed_user(pool, "sepay-user")
    raw = await mint_token(uid, kind="sepay")

    payload = {
        "id": 12345,
        "gateway": "TCB",
        "transactionDate": "2026-05-11 09:42:13",
        "accountNumber": "0123456789",
        "transferType": "in",
        "transferAmount": 50000,
        "content": "NAP TIEN",
        "referenceCode": "FT26-001",
    }
    resp = await handle_sepay_webhook(raw, payload)
    assert resp == {"ok": True}

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, amount, direction, ref_code, source, month_key "
            "FROM transactions WHERE user_id = $1;",
            uid,
        )
    assert len(rows) == 1
    row = rows[0]
    assert row["amount"] == 50000
    assert row["direction"] == "in"
    assert row["ref_code"] == "FT26-001"
    assert row["source"] == "sepay"
    assert row["month_key"] == "2026-05"


async def test_webhook_silent_200_on_bad_token(pool: asyncpg.Pool) -> None:
    """No info leak — invalid token returns 200 ok without inserting."""
    await _clean(pool)
    uid = await _seed_user(pool, "sepay-user")
    # mint a valid token but DON'T use it
    await mint_token(uid, kind="sepay")

    payload = {
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "in",
        "transferAmount": 50000,
        "gateway": "TCB",
        "referenceCode": "BAD-REF",
    }
    resp = await handle_sepay_webhook("definitely-not-a-real-token", payload)
    assert resp == {"ok": True}

    async with pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM transactions;")
    assert cnt == 0


async def test_webhook_silent_200_on_bad_payload(pool: asyncpg.Pool) -> None:
    """Valid token + unparseable payload → no insert, still 200."""
    await _clean(pool)
    uid = await _seed_user(pool, "sepay-user")
    raw = await mint_token(uid, kind="sepay")

    # transferType missing → _to_canonical raises, we log + return ok.
    resp = await handle_sepay_webhook(raw, {"transferAmount": 50000})
    assert resp == {"ok": True}

    async with pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM transactions WHERE user_id = $1;", uid)
    assert cnt == 0


async def test_webhook_sets_tenant_context(pool: asyncpg.Pool) -> None:
    """After processing, tenant context is set to the resolved user_id."""
    tenant_context.clear_tenant()
    await _clean(pool)
    uid = await _seed_user(pool, "sepay-tenant")
    raw = await mint_token(uid, kind="sepay")

    payload = {
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "out",
        "transferAmount": 12345,
        "gateway": "MB",
        "referenceCode": "X1",
    }
    await handle_sepay_webhook(raw, payload)
    assert tenant_context.get_user_id() == uid
    tenant_context.clear_tenant()


async def test_dedupe_via_ref_code_unique(pool: asyncpg.Pool) -> None:
    """Replays of the same SePay event don't double-insert thanks to
    UNIQUE(user_id, ref_code) + ON CONFLICT DO NOTHING."""
    await _clean(pool)
    uid = await _seed_user(pool, "dedupe-user")
    raw = await mint_token(uid, kind="sepay")

    payload = {
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "in",
        "transferAmount": 1000,
        "gateway": "TCB",
        "referenceCode": "DUP-1",
    }
    await handle_sepay_webhook(raw, payload)
    await handle_sepay_webhook(raw, payload)
    async with pool.acquire() as conn:
        cnt = await conn.fetchval(
            "SELECT COUNT(*) FROM transactions WHERE user_id=$1 AND ref_code='DUP-1';",
            uid,
        )
    assert cnt == 1


async def test_empty_ref_code_falls_back_to_provider_event_id(pool: asyncpg.Pool) -> None:
    """No referenceCode but SePay `id` present → ref_code = sepay-id-{hash}.

    Codex P1 round 1: NULL ref_code broke dedupe (NULL != NULL in UNIQUE).
    Codex P2 round 3: provider id hashed to fixed length so the resulting
    ref_code always fits the `transactions.ref_code VARCHAR(64)` column
    bound, regardless of upstream payload anomalies.
    Retries of the same event share the same SePay id → same hash → dedupe.
    """
    await _clean(pool)
    uid = await _seed_user(pool, "ref-fallback-providerid")
    raw = await mint_token(uid, kind="sepay")

    payload = {
        "id": 99001,
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "in",
        "transferAmount": 50000,
        "gateway": "TCB",
        "accountNumber": "0123456789",
        # NO referenceCode — SePay id carries the dedupe key
    }
    await handle_sepay_webhook(raw, payload)
    await handle_sepay_webhook(raw, payload)  # retry

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT ref_code FROM transactions WHERE user_id = $1;",
            uid,
        )
    assert len(rows) == 1, "Retry must dedupe via provider event id"
    rc = rows[0]["ref_code"]
    # Form: `sepay-id-` (9 chars) + 24 hex digest = 33 chars total
    assert rc.startswith("sepay-id-"), f"Expected sepay-id- prefix, got {rc!r}"
    assert len(rc) == 33, f"Provider-id fallback should be fixed length 33, got {len(rc)}"
    assert len(rc) <= 64, "ref_code must fit transactions.ref_code VARCHAR(64) bound"


async def test_distinct_provider_event_ids_with_same_content_not_deduped(
    pool: asyncpg.Pool,
) -> None:
    """Codex P1 round 2 guard: two SePay events with IDENTICAL content
    (same user/date/amount/direction/bank/last4) but DIFFERENT `id` values
    must NOT collide — they are distinct events from SePay's POV.

    Pre-fix synthetic hash collapsed both into one row (silent transaction
    loss); fix uses provider event id when present.
    """
    await _clean(pool)
    uid = await _seed_user(pool, "distinct-providerid")
    raw = await mint_token(uid, kind="sepay")

    base = {
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "in",
        "transferAmount": 50000,
        "gateway": "TCB",
        "accountNumber": "0123456789",
        # NO referenceCode — same content for both events
    }
    await handle_sepay_webhook(raw, {**base, "id": 11111})
    await handle_sepay_webhook(raw, {**base, "id": 22222})  # distinct event

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT ref_code FROM transactions WHERE user_id = $1 ORDER BY ref_code;",
            uid,
        )
    assert len(rows) == 2, (
        "Two distinct SePay events with different `id` must produce two rows "
        "even when all other fields are identical"
    )
    refs = {row["ref_code"] for row in rows}
    assert len(refs) == 2, "Distinct provider ids must hash to distinct ref_codes"
    assert all(
        rc.startswith("sepay-id-") and len(rc) == 33 for rc in refs
    ), f"All ref_codes must be `sepay-id-{{24-hex}}` form, got {refs}"


async def test_no_ref_code_and_no_provider_id_falls_back_to_content_hash(
    pool: asyncpg.Pool,
) -> None:
    """Defensive last-resort fallback when both referenceCode AND SePay `id`
    are missing. Content hash carries collision risk between two same-amount
    events in the same second — acceptable only because real SePay always
    provides at least one identifier. Retries of the same payload must still
    dedupe.
    """
    await _clean(pool)
    uid = await _seed_user(pool, "last-resort-hash")
    raw = await mint_token(uid, kind="sepay")

    payload = {
        # NO id, NO referenceCode — pathological provider payload
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "in",
        "transferAmount": 50000,
        "gateway": "TCB",
        "accountNumber": "0123456789",
    }
    await handle_sepay_webhook(raw, payload)
    await handle_sepay_webhook(raw, payload)  # retry

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT ref_code FROM transactions WHERE user_id = $1;",
            uid,
        )
    assert len(rows) == 1, "Retry must dedupe via content hash"
    assert rows[0]["ref_code"].startswith(
        "hash-"
    ), f"Expected content-hash prefix, got {rows[0]['ref_code']!r}"


async def test_long_provider_event_id_fits_schema_bound(pool: asyncpg.Pool) -> None:
    """Codex P2 round 3 guard: pathological provider id (e.g. 200-char string)
    must NOT overflow `transactions.ref_code VARCHAR(64)`. Hashing the
    provider id to fixed length keeps inserts safe regardless of upstream
    payload anomalies. Without this guard, the INSERT would raise
    'value too long for type character varying(64)' and webhook retries
    would error repeatedly instead of deduping.
    """
    await _clean(pool)
    uid = await _seed_user(pool, "long-providerid")
    raw = await mint_token(uid, kind="sepay")

    payload = {
        "id": "X" * 200,  # pathological — 200-char provider id
        "transactionDate": "2026-05-11 09:42:13",
        "transferType": "in",
        "transferAmount": 50000,
        "gateway": "TCB",
        "accountNumber": "0123456789",
    }
    # Must not raise: pre-fix code would have failed VARCHAR(64) on INSERT.
    await handle_sepay_webhook(raw, payload)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT ref_code FROM transactions WHERE user_id = $1;",
            uid,
        )
    assert len(rows) == 1, "Long provider id must persist exactly one row"
    rc = rows[0]["ref_code"]
    assert len(rc) <= 64, f"ref_code must fit VARCHAR(64), got len={len(rc)}"
    assert rc.startswith("sepay-id-"), f"Expected sepay-id- prefix, got {rc!r}"
