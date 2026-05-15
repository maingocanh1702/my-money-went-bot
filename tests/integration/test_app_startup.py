"""Phase 1 (C1) — FastAPI lifespan wiring smoke test.

Asserts the app boots through the new lifespan: db pool initialised,
request_id middleware stamps `X-Request-ID`, health endpoint still 200.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import db


@pytest.fixture
async def app_with_pool(
    migrated_db: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    """Spin the FastAPI app with DATABASE_URL pointing at the migrated DB.

    The lifespan owns pool lifecycle, so we close any pre-existing pool
    from prior tests, then let `main:app` take over via its lifespan.
    """
    await db.close_pool()
    monkeypatch.setenv("DATABASE_URL", migrated_db)
    monkeypatch.setenv("APP_ENV", "test")

    # Import inside the fixture so the env var is set BEFORE main.py module
    # globals capture anything from os.environ. (config.py reads at import.)
    import importlib

    import main as main_module

    importlib.reload(main_module)
    yield main_module.app
    await db.close_pool()


def test_health_returns_200(app_with_pool: FastAPI) -> None:
    """GET / → 200 (Railway healthcheck contract)."""
    with TestClient(app_with_pool) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_response_has_request_id_header(app_with_pool: FastAPI) -> None:
    """Every response carries an X-Request-ID header (server-generated)."""
    with TestClient(app_with_pool) as client:
        resp = client.get("/")
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None and len(rid) >= 16, f"missing/short X-Request-ID: {rid!r}"


def test_request_id_propagates_from_inbound_header(app_with_pool: FastAPI) -> None:
    """Inbound X-Request-ID is honoured (client→server correlation)."""
    given = "abc123def4567890"  # pragma: allowlist secret  (fake request id)
    with TestClient(app_with_pool) as client:
        resp = client.get("/", headers={"X-Request-ID": given})
    assert resp.headers.get("X-Request-ID") == given


def test_db_pool_initialised_after_startup(app_with_pool: FastAPI) -> None:
    """`db.get_pool()` returns the live pool once lifespan startup ran."""
    with TestClient(app_with_pool):
        pool = db.get_pool()
        assert pool is not None
