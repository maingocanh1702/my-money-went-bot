"""webhook_tokens lookup helpers (Gap 3).

Raw tokens are NEVER stored — we hash with SHA-256 and compare hashes.
Constant-time comparison via `hmac.compare_digest` to dodge timing
attacks on the hex string (defence in depth — even on a hashed value).

Public surface:
  - `hash_token(raw)` — produce the storage hash for a raw token.
  - `mint_token(user_id, kind)` — generate a fresh URL-safe token,
    insert its hash, return the RAW token (returned ONCE — caller is
    responsible for displaying it; we never reconstruct it).
  - `resolve_token(raw, kind)` — return owning user_id if the token
    hash exists and is not revoked; None otherwise.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Literal, cast

from core import db

TokenKind = Literal["sepay", "email_inbound"]


def hash_token(raw: str) -> str:
    """SHA-256 hex digest of the raw token bytes."""
    if not raw:
        raise ValueError("hash_token: empty token rejected")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def mint_token(user_id: int, kind: TokenKind) -> str:
    """Mint a fresh token for (user_id, kind); persist its hash; return raw.

    The UNIQUE(user_id, kind) constraint on `webhook_tokens` means at
    most one active token per user per kind — repeat calls REVOKE the
    prior token by ON CONFLICT updating its hash (the new hash takes
    effect, the old one stops resolving).
    """
    raw = secrets.token_urlsafe(24)  # ~32 chars URL-safe
    token_hash = hash_token(raw)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webhook_tokens (user_id, kind, token_hash)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, kind) DO UPDATE
                SET token_hash = EXCLUDED.token_hash,
                    revoked_at = NULL,
                    created_at = NOW();
            """,
            user_id,
            kind,
            token_hash,
        )
    return raw


async def resolve_token(raw: str, kind: TokenKind) -> int | None:
    """Return owning user_id if the token resolves to an active row of
    `kind`; None otherwise. No info leak — same return shape for bad
    token, wrong kind, and revoked token.

    Lookup goes through the UNIQUE index on `token_hash` so cost is
    O(log n) regardless of input. We still compare the returned hash
    against the candidate via `hmac.compare_digest` as belt-and-braces
    against any future schema relaxation (e.g. dropping UNIQUE).
    """
    if not raw:
        return None
    candidate = hash_token(raw)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_id, token_hash
            FROM webhook_tokens
            WHERE token_hash = $1 AND kind = $2 AND revoked_at IS NULL;
            """,
            candidate,
            kind,
        )
    if row is None:
        return None
    if not hmac.compare_digest(row["token_hash"], candidate):
        return None
    return cast(int, row["user_id"])
