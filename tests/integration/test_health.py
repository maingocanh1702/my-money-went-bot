"""Health endpoints — liveness always 200; detailed 200/503 based on DB."""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from core import db
from core.observability import REQUEST_ID_HEADER, health_app, request_id_middleware


@pytest.fixture
async def asgi_client() -> AsyncIterator[AsyncClient]:
    """Wrap health_app + request_id middleware in an in-process ASGI client."""
    app = FastAPI()
    app.mount("/", health_app)
    app.add_middleware(BaseHTTPMiddleware, dispatch=request_id_middleware)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def pool_open(pg_url_async: str, migrated_db: str) -> AsyncIterator[asyncpg.Pool]:
    _ = migrated_db
    await db.close_pool()
    pool = await db.create_pool(pg_url_async, min_size=1, max_size=3)
    yield pool
    await db.close_pool()


async def _pool_closed_fixture() -> None:
    await db.close_pool()


async def test_health_liveness_always_200(asgi_client: AsyncClient) -> None:
    """Liveness must not depend on the DB — even before pool init it's 200."""
    await _pool_closed_fixture()
    resp = await asgi_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_detailed_503_when_db_down(asgi_client: AsyncClient) -> None:
    """Detailed health → 503 when the pool isn't initialised."""
    await _pool_closed_fixture()
    resp = await asgi_client.get("/health/detailed")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db"]["ok"] is False
    assert "pool-not-initialised" in body["checks"]["db"]["error"]


async def test_health_detailed_200_when_db_up(
    asgi_client: AsyncClient, pool_open: asyncpg.Pool
) -> None:
    _ = pool_open
    resp = await asgi_client.get("/health/detailed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["db"]["pool_size"] is not None
    assert body["build"]["service"] == "mymoneywent"


async def test_request_id_middleware_generates_and_echoes(asgi_client: AsyncClient) -> None:
    resp = await asgi_client.get("/health")
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid is not None
    assert len(rid) == 32  # uuid4 hex


async def test_request_id_middleware_honours_inbound_header(
    asgi_client: AsyncClient,
) -> None:
    resp = await asgi_client.get("/health", headers={REQUEST_ID_HEADER: "client-supplied-id"})
    assert resp.headers[REQUEST_ID_HEADER] == "client-supplied-id"
