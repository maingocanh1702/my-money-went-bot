"""Test /dashboard + /dashboard.md FastAPI routes (Phase 3 deployment).

Verifies the routes serve docs/dashboard.html + docs/dashboard.md with
proper headers, and gracefully 404 when the files are missing. Routes are
defined in `main.py` so the live-poll JS in dashboard.html can run from a
real https origin (Railway), where CORS to api.github.com works (unlike
file:// where Chrome blocks cross-origin fetch).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Skip the entire module if `main` can't import — keeps the test discoverable
# but harmless in environments where the FastAPI app's transitive deps
# (telegram_api, sheets, handlers) aren't satisfied.
main = pytest.importorskip("main")


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


def test_dashboard_html_returns_200_with_live_poll_js(client: TestClient) -> None:
    """GET /dashboard returns dashboard.html with live-poll JS embedded."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.headers.get("cache-control") == "public, max-age=30"
    # Spot-check JS markers — confirms the build script's live-poll injection
    # made it into the served HTML (regression guard if rendering changes).
    assert "live-indicator" in resp.text
    assert "fetchLatestSha" in resp.text


def test_dashboard_md_returns_200(client: TestClient) -> None:
    """GET /dashboard.md returns dashboard.md with markdown content-type."""
    resp = client.get("/dashboard.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.headers.get("cache-control") == "public, max-age=30"


def test_dashboard_html_404_when_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If dashboard.html is absent, return JSON 404 instead of crashing."""
    monkeypatch.setattr(main, "DASHBOARD_HTML", tmp_path / "nonexistent.html")
    resp = client.get("/dashboard")
    assert resp.status_code == 404
    assert "dashboard.html not found" in resp.json()["error"]


def test_dashboard_md_404_when_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If dashboard.md is absent, return JSON 404 instead of crashing."""
    monkeypatch.setattr(main, "DASHBOARD_MD", tmp_path / "nonexistent.md")
    resp = client.get("/dashboard.md")
    assert resp.status_code == 404
    assert "dashboard.md not found" in resp.json()["error"]
