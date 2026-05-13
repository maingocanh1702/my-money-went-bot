"""F01 — /start handler integration tests (12 tests).

Spec: docs/features/feature-onboarding.md §4 (domain model) + §6 (error codes).
Plan: docs/implementation-plans/phase-2-handlers.md §1.
Lockdown: docs/operations/F01-F08-lockdown.md §1.6 (5-category test plan).

Reuses `settings_pool` + `send_calls` fixtures from tests/integration/conftest.py.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import asyncpg
import pytest

from core.handlers.start import handle_start

TokenKind = Literal["sepay", "email_inbound"]


def _last_text(send_calls: list[dict[str, Any]]) -> str:
    for entry in reversed(send_calls):
        payload = entry["payload"]
        if "text" in payload:
            return str(payload["text"])
        if "text_key" in payload:
            return str(payload["text_key"])
    raise AssertionError("no send captured")


async def _fetch_user(
    pool: asyncpg.Pool, channel_type: str, channel_user_id: str
) -> asyncpg.Record:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE channel_type = $1 AND channel_user_id = $2;",
            channel_type,
            channel_user_id,
        )
    assert row is not None, f"expected user row for ({channel_type}, {channel_user_id})"
    return row


# ─── Positive (5) ────────────────────────────────────────────────────


async def test_telegram_start_creates_user(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """TG /start creates user with plan=free + 14d trial + inbound_email."""
    before = datetime.now(UTC)
    await handle_start(channel_type="telegram", channel_user_id="99999", chat_id=99999)
    after = datetime.now(UTC)

    row = await _fetch_user(settings_pool, "telegram", "99999")
    assert row["plan"] == "free"
    assert row["locale"] == "vi"
    assert row["channel_type"] == "telegram"
    assert row["chat_id"] == 99999
    trial = row["trial_ends_at"]
    assert trial is not None
    # Trial window ~14d, allow ±1d slack for test clock skew.
    assert before + timedelta(days=13) <= trial <= after + timedelta(days=15)
    assert row["inbound_email"] == f"u{row['id']}@in.mymoneywent.com"


async def test_discord_start_creates_user(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Discord /start: channel_type='discord', chat_id may be NULL."""
    await handle_start(channel_type="discord", channel_user_id="42424242")
    row = await _fetch_user(settings_pool, "discord", "42424242")
    assert row["channel_type"] == "discord"
    assert row["plan"] == "free"
    assert row["chat_id"] is None


async def test_existing_user_restart_idempotent(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Second /start from same TG ID → no duplicate row + welcome-back."""
    await handle_start(channel_type="telegram", channel_user_id="55555", chat_id=55555)
    send_calls.clear()
    await handle_start(channel_type="telegram", channel_user_id="55555", chat_id=55555)

    async with settings_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE channel_type = 'telegram' AND channel_user_id = '55555';"
        )
    assert count == 1
    last = _last_text(send_calls)
    assert "welcome_back" in last or "quay lại" in last


async def test_default_categories_created_vi(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """3 default categories seeded post-/start (daily_spending, saving, subscription)."""
    await handle_start(channel_type="telegram", channel_user_id="123", chat_id=123)
    row = await _fetch_user(settings_pool, "telegram", "123")
    async with settings_pool.acquire() as conn:
        cats = await conn.fetch(
            "SELECT slug, name, daily_cap FROM categories WHERE user_id = $1 ORDER BY slug;",
            row["id"],
        )
    by_slug = {c["slug"]: c for c in cats}
    assert set(by_slug) == {"daily_spending", "saving", "subscription"}
    assert by_slug["daily_spending"]["daily_cap"] == 100_000
    assert by_slug["saving"]["daily_cap"] is None
    assert by_slug["subscription"]["daily_cap"] is None
    # VI names — emoji from i18n pack should appear.
    assert "Chi tiêu" in by_slug["daily_spending"]["name"]
    assert "Tiết kiệm" in by_slug["saving"]["name"]


async def test_welcome_message_contains_trial_expiry(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Welcome payload includes the rendered trial_ends_at date."""
    await handle_start(channel_type="telegram", channel_user_id="trial-show", chat_id=1)
    row = await _fetch_user(settings_pool, "telegram", "trial-show")
    trial = row["trial_ends_at"]
    assert trial is not None
    payload = send_calls[-1]["payload"]
    params = payload.get("text_params") or {}
    rendered = str(params.get("trial_end", ""))
    # ISO date prefix YYYY-MM-DD in user TZ (default Asia/Ho_Chi_Minh).
    from zoneinfo import ZoneInfo

    expected = trial.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")
    assert rendered == expected


# ─── Edge (3) ────────────────────────────────────────────────────────


async def test_concurrent_starts_idempotent(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Two parallel /start same TG ID → exactly 1 user row, no exceptions."""
    await asyncio.gather(
        handle_start(channel_type="telegram", channel_user_id="race", chat_id=7),
        handle_start(channel_type="telegram", channel_user_id="race", chat_id=7),
    )
    async with settings_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE channel_type = 'telegram' AND channel_user_id = 'race';"
        )
    assert count == 1


async def test_trial_expired_user_no_reset(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """Trial-expired user /start → plan stays free, trial_ends_at NOT reset."""
    past = datetime.now(UTC) - timedelta(days=1)
    async with settings_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (channel_type, channel_user_id, plan, trial_ends_at, locale, inbound_email)
            VALUES ('telegram', 'expired', 'free', $1, 'vi', 'u-expired@in.mymoneywent.com');
            """,
            past,
        )
    await handle_start(channel_type="telegram", channel_user_id="expired", chat_id=1)
    row = await _fetch_user(settings_pool, "telegram", "expired")
    assert row["plan"] == "free"
    # Compare with second precision — DB round-trips can shave microseconds.
    assert abs((row["trial_ends_at"] - past).total_seconds()) < 1


async def test_null_language_code_defaults_vi(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """No language_code on update → user.locale='vi'."""
    await handle_start(
        channel_type="telegram",
        channel_user_id="no-lang",
        chat_id=1,
        language_code=None,
    )
    row = await _fetch_user(settings_pool, "telegram", "no-lang")
    assert row["locale"] == "vi"


# ─── Error (2) ───────────────────────────────────────────────────────


async def test_db_down_graceful_error(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """DB pool unavailable → handler logs + does NOT raise."""

    def boom() -> Any:
        raise RuntimeError("DB unavailable (simulated)")

    monkeypatch.setattr("core.services.user_svc.db.get_pool", boom)
    # Must not raise. structlog renders to stdout — assert via capsys, not caplog.
    await handle_start(channel_type="telegram", channel_user_id="db-down", chat_id=1)
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "onboard.create_fail" in combined
    # No `messenger.send` should have fired — we have no user row yet.
    assert not send_calls


async def test_webhook_token_collision_retries(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mint_token raising UniqueViolationError once then succeeding → retry path mints token."""
    calls = {"n": 0}

    async def flaky_mint(user_id: int, kind: TokenKind) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise asyncpg.UniqueViolationError("token_hash collision (simulated)")
        # 2nd call: actually mint a token via real path.
        from markets.vn.capture.webhook_tokens import mint_token as real_mint

        return await real_mint(user_id, kind)

    monkeypatch.setattr("core.handlers.start.mint_token", flaky_mint)
    await handle_start(channel_type="telegram", channel_user_id="token-collide", chat_id=1)
    row = await _fetch_user(settings_pool, "telegram", "token-collide")
    async with settings_pool.acquire() as conn:
        token_count = await conn.fetchval(
            "SELECT COUNT(*) FROM webhook_tokens WHERE user_id = $1 AND kind = 'sepay';",
            row["id"],
        )
    assert token_count == 1
    assert calls["n"] == 2  # one failure + one success


# ─── Isolation (1) ───────────────────────────────────────────────────


async def test_user_a_start_does_not_affect_user_b(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """A /start, B /start → A's categories + tokens are A-only."""
    await handle_start(channel_type="telegram", channel_user_id="a", chat_id=1)
    await handle_start(channel_type="telegram", channel_user_id="b", chat_id=2)
    a = await _fetch_user(settings_pool, "telegram", "a")
    b = await _fetch_user(settings_pool, "telegram", "b")
    assert a["id"] != b["id"]
    async with settings_pool.acquire() as conn:
        a_cats = await conn.fetch("SELECT user_id FROM categories WHERE user_id = $1;", a["id"])
        b_cats = await conn.fetch("SELECT user_id FROM categories WHERE user_id = $1;", b["id"])
        a_tokens = await conn.fetch(
            "SELECT user_id FROM webhook_tokens WHERE user_id = $1;", a["id"]
        )
        b_tokens = await conn.fetch(
            "SELECT user_id FROM webhook_tokens WHERE user_id = $1;", b["id"]
        )
    assert all(r["user_id"] == a["id"] for r in a_cats)
    assert all(r["user_id"] == b["id"] for r in b_cats)
    assert all(r["user_id"] == a["id"] for r in a_tokens)
    assert all(r["user_id"] == b["id"] for r in b_tokens)
    assert len(a_cats) == 3 and len(b_cats) == 3


# ─── Contract (1) ────────────────────────────────────────────────────


async def test_messenger_send_called_with_correct_user_id(
    settings_pool: asyncpg.Pool,
    send_calls: list[dict[str, Any]],
) -> None:
    """`messenger.send` receives the freshly-created user_id, not chat_id/channel_user_id."""
    await handle_start(channel_type="telegram", channel_user_id="contract", chat_id=987654)
    row = await _fetch_user(settings_pool, "telegram", "contract")
    # At least one send call was made with the new user's id.
    user_ids = [c["user_id"] for c in send_calls]
    assert row["id"] in user_ids
    # And the chat_id / channel_user_id values are NOT passed as user_id.
    assert 987654 not in user_ids
