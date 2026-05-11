"""Per-request tenant context via ContextVar.

Why ContextVar (not threading.local or globals):
  - asyncio-safe: each task sees its own value, no cross-task leakage
  - propagates across `await` boundaries automatically
  - works with `asyncio.gather`, `TaskGroup`, etc.

The tenant context holds two values per request/task:
  - user_id: the tenant ID that owns this request's data
  - request_id: a UUID4 for log correlation across the request lifecycle

Set ONCE at request entry (webhook handler / message handler), read
EVERYWHERE downstream (DB layer, messenger, logging). NEVER hardcode
user_id in business logic — it's a foot-gun for tenant isolation.

Tenant isolation rule (HARD invariant, see W0.3 acceptance):
  Every query that reads/writes tenant-scoped tables MUST filter by
  `user_id = get_user_id()`. The DB enforces nothing here — the
  application owns multi-tenancy. Cross-tenant leakage is the #1 SaaS
  security incident category, so the 2-user isolation integration test
  in tests/integration/test_tenant_isolation.py is non-negotiable.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_user_id: ContextVar[int | None] = ContextVar("mmw_user_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("mmw_request_id", default=None)


def set_tenant(user_id: int, request_id: str | None = None) -> str:
    """Set the tenant context for the current task. Returns the request_id.

    If `request_id` is None, generates a fresh UUID4 hex (32 chars).
    """
    if user_id <= 0:
        raise ValueError(f"user_id must be a positive integer, got {user_id!r}")
    rid = request_id if request_id else uuid.uuid4().hex
    _user_id.set(user_id)
    _request_id.set(rid)
    return rid


def get_user_id() -> int:
    """Return the tenant user_id. Raises if not set — fail loud, never default."""
    uid = _user_id.get()
    if uid is None:
        raise LookupError(
            "tenant_context: user_id not set in current task — "
            "call set_tenant(user_id) at request entry before any DB access"
        )
    return uid


def get_user_id_or_none() -> int | None:
    """Return the tenant user_id, or None if unset. For optional contexts only
    (logging fallback, health checks). NEVER use this in tenant-scoped queries."""
    return _user_id.get()


def get_request_id() -> str | None:
    """Return the current request_id, or None if unset."""
    return _request_id.get()


def clear_tenant() -> None:
    """Clear the tenant context. Call at request exit (or rely on task scope)."""
    _user_id.set(None)
    _request_id.set(None)
