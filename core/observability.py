"""Sentry init + /health endpoints + request_id middleware.

`init_sentry(dsn)`: initialises the Sentry SDK with FastAPI integration
and a `before_send` hook that adds `user_id` + `request_id` tags from
the tenant context — every captured exception gets the tenant context
automatically.

`health_app`: standalone FastAPI sub-app with:
  - `GET /health`        → always 200 (liveness; never blocks)
  - `GET /health/detailed` → checks DB pool reachability + reports
                             build info; returns 503 when DB is down

`request_id_middleware`: FastAPI middleware that stamps a UUID4 hex
on every request, propagates it into the tenant context, and echoes
it back in the `X-Request-ID` response header. Honours an inbound
`X-Request-ID` header if the client supplies one (for client→server
correlation).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.requests import Request
from starlette.responses import Response

from core import db, tenant_context

BUILD_INFO = {
    "service": "mymoneywent",
    "version": os.environ.get("APP_VERSION", "0.0.1-dev"),
    "commit": os.environ.get("APP_COMMIT", "unknown"),
}


# ─── Sentry ────────────────────────────────────────────────────────────


def _sentry_before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Add tenant context tags + user.id to every event."""
    uid = tenant_context.get_user_id_or_none()
    rid = tenant_context.get_request_id()
    if uid is not None:
        event.setdefault("tags", {})["user_id"] = uid
        event.setdefault("user", {})["id"] = uid
    if rid is not None:
        event.setdefault("tags", {})["request_id"] = rid
    return event


def init_sentry(
    dsn: str | None = None,
    *,
    environment: str | None = None,
    release: str | None = None,
    traces_sample_rate: float = 0.0,
) -> bool:
    """Initialise Sentry. Returns True if configured, False if no DSN.

    No-op when `dsn` is falsy — lets local dev run without a Sentry
    project. Production must pass a non-empty DSN.
    """
    dsn = dsn or os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return False
    # sentry_sdk's `before_send` is typed against its own internal Event
    # TypedDict (alias of dict). Cast through Any so our concrete dict
    # signature lines up without dragging Sentry types into our hot path.
    sentry_sdk.init(
        dsn=dsn,
        environment=environment or os.environ.get("APP_ENV", "dev"),
        release=release or BUILD_INFO["version"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=traces_sample_rate,
        before_send=_sentry_before_send,  # type: ignore[arg-type]
        send_default_pii=False,
    )
    return True


# ─── Request ID middleware ────────────────────────────────────────────


REQUEST_ID_HEADER = "X-Request-ID"


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Stamp a request_id on every request, propagate to tenant_context,
    echo in response header.

    Honours an inbound X-Request-ID header if the client supplies one,
    so we can correlate a trace across services without re-generating.
    The tenant_context user_id is NOT set here — handlers do that after
    authenticating the user. Middleware only seeds request_id.
    """
    rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    request.state.request_id = rid
    token = tenant_context._request_id.set(rid)  # noqa: SLF001 — internal token
    try:
        response = await call_next(request)
    finally:
        tenant_context._request_id.reset(token)  # noqa: SLF001
    response.headers[REQUEST_ID_HEADER] = rid
    return response


# ─── Health endpoints ─────────────────────────────────────────────────


health_app = FastAPI(title="MyMoneyWent — health")


@health_app.get("/health")
async def health() -> dict[str, str]:
    """Liveness — always 200. Used by Railway healthchecks. Never blocks
    on dependencies; a 200 here means 'the process is up', nothing more."""
    return {"status": "ok"}


@health_app.get("/health/detailed")
async def health_detailed() -> JSONResponse:
    """Readiness — checks DB pool reachability. 503 if DB is down."""
    db_ok = False
    db_error: str | None = None
    pool_size: int | None = None
    try:
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        db_ok = True
        pool_size = pool.get_size()
    except RuntimeError as exc:
        # Pool not initialised — health probe before app startup.
        db_error = f"pool-not-initialised: {exc}"
    except Exception as exc:  # noqa: BLE001 — health endpoint catches all
        db_error = f"{type(exc).__name__}: {exc}"

    body = {
        "status": "ok" if db_ok else "degraded",
        "build": BUILD_INFO,
        "checks": {
            "db": {
                "ok": db_ok,
                "pool_size": pool_size,
                "error": db_error,
            },
        },
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)
