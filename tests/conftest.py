"""Test fixtures for integration tests.

Provides:
  - `pg_container`: session-scoped Postgres 16 testcontainer
  - `pg_url`: sync DSN (postgresql://...) for alembic + asyncpg-compat callers
  - `pg_url_async`: asyncpg DSN (postgresql+asyncpg://...)
  - `migrated_db`: spins container, runs `alembic upgrade head`, yields DSN;
    downgrades + drops on teardown
  - `assert_tenant_isolated`: assertion helper for cross-tenant smoke

Container lifetime is session-scoped — spin once, reuse across tests.
Per-test isolation via explicit DELETE in test setup or via test transactions.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _has_docker() -> bool:
    """Cheap check — `docker info` succeeds if daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def pg_container() -> Iterator[Any]:
    """Session-scoped Postgres 16 testcontainer."""
    if not _has_docker():
        pytest.skip("Docker daemon not available — integration tests skipped")

    # Import inside fixture so missing testcontainers dep doesn't break collection.
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine", driver=None)
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def pg_url(pg_container: Any) -> str:
    """Sync DSN — `postgresql://user:pass@host:port/db`."""
    url: str = pg_container.get_connection_url()
    # testcontainers may return `postgresql+psycopg2://`; normalise to bare scheme.
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


@pytest.fixture(scope="session")
def pg_url_async(pg_url: str) -> str:
    """Asyncpg DSN — `postgresql+asyncpg://...`."""
    return pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _alembic(cmd: list[str], db_url: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    return subprocess.run(
        ["alembic", *cmd],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture(scope="session")
def migrated_db(pg_url: str) -> Iterator[str]:
    """Run `alembic upgrade head` once per session, yield DSN."""
    result = _alembic(["upgrade", "head"], pg_url)
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\n" f"STDOUT:\n{result.stdout}\n" f"STDERR:\n{result.stderr}"
    )
    yield pg_url
    # Best-effort downgrade for clean teardown; container is destroyed anyway.
    _alembic(["downgrade", "base"], pg_url)


def assert_tenant_isolated(
    rows: list[dict[str, Any]],
    expected_user_id: int,
    user_id_col: str = "user_id",
) -> None:
    """Assert every row belongs to `expected_user_id`.

    Use after any tenant-scoped query to prove cross-tenant rows didn't leak.
    """
    leaked = [r for r in rows if r.get(user_id_col) != expected_user_id]
    leaked_ids: set[int] = {int(r[user_id_col]) for r in leaked if r.get(user_id_col) is not None}
    assert not leaked, (
        f"Tenant isolation breach: expected only user_id={expected_user_id}, "
        f"got rows for user_ids={sorted(leaked_ids)}"
    )
