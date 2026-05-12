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
  - `get_display_suffix(user_id, kind)` — return the cosmetic tail of
    the active token (W0.8 / G3 option b) for UI display. May be None
    for legacy rows minted before migration 0002.
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


def _display_suffix(raw: str) -> str:
    """Tail 6 chars of the raw token — shown in UI, NEVER used for auth.

    Auth still goes through token_hash. The suffix is purely cosmetic —
    helps users visually confirm the URL they pasted matches the one
    rendered in /settings. Length 6 is short enough to display in a
    bot reply without wrapping; entropy loss is irrelevant (we leak 6/32
    chars of a random URL-safe string only to the user who owns the token).
    """
    if len(raw) < 6:
        # Defensive: secrets.token_urlsafe(24) always returns >>6 chars,
        # but if a caller ever shortens the generator, fall back to the
        # full string rather than raise — column tolerates any <= 8 chars.
        return raw
    return raw[-6:]


async def mint_token(user_id: int, kind: TokenKind) -> str:
    """Mint a fresh token for (user_id, kind); persist its hash; return raw.

    The UNIQUE(user_id, kind) constraint on `webhook_tokens` means at
    most one active token per user per kind — repeat calls REVOKE the
    prior token by ON CONFLICT updating its hash (the new hash takes
    effect, the old one stops resolving).
    """
    raw = secrets.token_urlsafe(24)  # ~32 chars URL-safe
    token_hash = hash_token(raw)
    display_suffix = _display_suffix(raw)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webhook_tokens (user_id, kind, token_hash, display_suffix)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, kind) DO UPDATE
                SET token_hash = EXCLUDED.token_hash,
                    display_suffix = EXCLUDED.display_suffix,
                    revoked_at = NULL,
                    created_at = NOW();
            """,
            user_id,
            kind,
            token_hash,
            display_suffix,
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


async def get_display_suffix(user_id: int, kind: TokenKind) -> str | None:
    """Return the active token's display_suffix for (user_id, kind), or
    None if no active row exists (or row predates this migration → NULL)."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT display_suffix
            FROM webhook_tokens
            WHERE user_id = $1 AND kind = $2 AND revoked_at IS NULL;
            """,
            user_id,
            kind,
        )
    if row is None:
        return None
    return cast(str | None, row["display_suffix"])
