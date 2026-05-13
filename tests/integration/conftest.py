"""Integration-scope fixtures + helpers shared by F07 settings tests.

Lives in conftest.py so pytest auto-discovers fixtures without imports
(side-stepping ruff F811 "redefinition" warnings on the standard pytest
pattern of `def test_x(fixture_name): ...`).

Fixtures:
  - `settings_pool` — asyncpg pool against the migrated DB; truncates
    users+webhook_tokens+analytics_events before each test (CASCADE).
  - `send_calls` — list capturing monkeypatched `core.messenger.send`
    calls; each entry is `{"user_id": int, "payload": dict}`.

Helpers (imported by test modules, not fixtures):
  - `seed_user`, `count_analytics_events`.

Why not in tests/conftest.py: keeps F07-specific test plumbing out of
unit-test collection paths.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from core import db


@pytest.fixture
async def settings_pool(pg_url_async: str, migrated_db: str) -> AsyncIterator[asyncpg.Pool]:
    """Migrated DB pool with all user-scoped tables cleaned between tests."""
    _ = migrated_db
    await db.close_pool()
    pool = await db.create_pool(pg_url_async, min_size=2, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")
        await conn.execute("TRUNCATE analytics_events RESTART IDENTITY;")
    yield pool
    await db.close_pool()


@pytest.fixture
def send_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture `core.messenger.send` without dispatching to a real adapter."""
    captured: list[dict[str, Any]] = []

    async def _fake_send(user_id: int, payload: Any) -> None:
        captured.append({"user_id": user_id, "payload": dict(payload)})

    monkeypatch.setattr("core.messenger.send", _fake_send)
    return captured


async def seed_user(
    pool: asyncpg.Pool,
    channel_user_id: str,
    *,
    locale: str = "vi",
    timezone: str = "Asia/Ho_Chi_Minh",
    daily_recap_enabled: bool = True,
    plan: str = "free",
    trial_ends_at: Any = None,
    plan_expires_at: Any = None,
    inbound_email: str | None = None,
) -> int:
    """Seed a users row; return its id."""
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                """
                INSERT INTO users (
                    channel_type, channel_user_id, display_name,
                    plan, trial_ends_at, plan_expires_at,
                    timezone, locale, daily_recap_enabled, inbound_email
                )
                VALUES ('telegram', $1, 'T', $2, $3, $4, $5, $6, $7, $8)
                RETURNING id;
                """,
                channel_user_id,
                plan,
                trial_ends_at,
                plan_expires_at,
                timezone,
                locale,
                daily_recap_enabled,
                inbound_email,
            )
        )


async def count_analytics_events(
    pool: asyncpg.Pool,
    user_id: int,
    event_name: str | None = None,
) -> int:
    async with pool.acquire() as conn:
        if event_name is None:
            return int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM analytics_events WHERE user_id = $1;",
                    user_id,
                )
            )
        return int(
            await conn.fetchval(
                "SELECT COUNT(*) FROM analytics_events WHERE user_id = $1 AND event_name = $2;",
                user_id,
                event_name,
            )
        )
