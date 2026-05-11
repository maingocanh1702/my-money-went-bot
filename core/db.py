"""asyncpg connection pool — global singleton + lifecycle.

Pool sizing (per docs/operations/development-workflow.md §4 W0.3 acceptance):
  - min_size=2 — keep warm to absorb burst traffic without cold-start latency
  - max_size=10 — caps Postgres connections per app instance
  - command_timeout=30s — fail fast on stuck queries
  - statement_cache_size=100 — asyncpg prepared-statement cache

Single global pool. Call `create_pool(dsn)` once at app startup,
`close_pool()` once at shutdown. `get_pool()` returns the live pool or
raises RuntimeError if not initialised — callers must not auto-create.

Why not a per-request pool: asyncpg pools own their connections; creating
multiple pools wastes connections + breaks pgbouncer-style accounting.
"""

from __future__ import annotations

import asyncpg

_pool: asyncpg.Pool | None = None


async def create_pool(
    dsn: str,
    *,
    min_size: int = 2,
    max_size: int = 10,
    command_timeout: float = 30.0,
    statement_cache_size: int = 100,
) -> asyncpg.Pool:
    """Initialise the global asyncpg pool. Idempotent on the same DSN.

    Raises RuntimeError if called twice with different DSNs — that's almost
    certainly a config bug (e.g. two configs racing at startup).
    """
    global _pool
    if _pool is not None:
        # Allow re-init only if the prior pool was already closed.
        if not getattr(_pool, "_closed", False):
            raise RuntimeError("asyncpg pool already initialised — call close_pool() first")
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        statement_cache_size=statement_cache_size,
    )
    if _pool is None:  # asyncpg returns None on failure in some versions
        raise RuntimeError(f"asyncpg.create_pool returned None for dsn={dsn!r}")
    return _pool


def get_pool() -> asyncpg.Pool:
    """Return the live pool. Raises if `create_pool` wasn't called yet."""
    if _pool is None:
        raise RuntimeError("asyncpg pool not initialised — call create_pool(dsn) first")
    return _pool


async def close_pool() -> None:
    """Close the global pool. Idempotent — safe to call multiple times."""
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None
