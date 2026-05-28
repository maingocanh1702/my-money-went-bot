"""User service — DB operations for /start + user lifecycle (F01).

Spec:  docs/features/feature-onboarding.md  (Phase 2 minimal scope).
Plan:  docs/implementation-plans/phase-2-handlers.md §1.
Lockdown: docs/operations/F01-F08-lockdown.md §1.

Scope:
  - `create_or_get_user(channel_type, channel_user_id, ...)` — idempotent
    INSERT, returns `(User, created: bool)`.
  - `seed_default_categories(user_id, locale)` — VI/EN bilingual seed of
    3 starter categories for the current month_key (idempotent via the
    `(user_id, slug, month_key)` UNIQUE constraint).
  - Pure helpers: `generate_inbound_email`, `compute_trial_end`,
    `current_month_key`.

Out of scope (Phase 4 / F09 / F-i18n):
  - Onboard path tracking (`users.onboard_path`).
  - Auto-creating `scheduled_jobs` rows — F09 owns recalculation.
  - Bilingual EN category names — VI default; F-i18n PR polishes EN
    wording (literal English placeholders ship here to satisfy parity).
  - Locale auto-detect from update `language_code` — F-i18n owns the
    confirm UI; F01 defaults locale='vi'.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from core import db
from core.logging import get_logger
from i18n import t

_log = get_logger(__name__)

# Matches migration 0003 backfill + core.settings_svc fallback so display
# and persisted values agree (W0.7 invariant). Lockdown §1.2 mentions
# `in.tienvenoidau.com`; that is doc drift — the codebase ships
# `in.mymoneywent.com` and F01 holds the line.
_INBOUND_EMAIL_DOMAIN: Final[str] = "in.mymoneywent.com"
_DEFAULT_TRIAL_DAYS: Final[int] = 14

DEFAULT_CATEGORIES: Final[list[dict[str, Any]]] = [
    {
        "slug": "daily_spending",
        "daily_cap": 100_000,
        "i18n_key": "cat.default.daily_spending",
    },
    {"slug": "saving", "daily_cap": None, "i18n_key": "cat.default.saving"},
    {
        "slug": "subscription",
        "daily_cap": None,
        "i18n_key": "cat.default.subscription",
    },
]


@dataclass(frozen=True)
class User:
    """Minimal user projection returned by `create_or_get_user`.

    Fields cover everything the /start handler needs to render the welcome
    message + dispatch downstream side effects (mint token, seed cats).
    """

    id: int
    channel_type: str
    channel_user_id: str
    chat_id: int | None
    channel_chat_id: str | None
    locale: str
    timezone: str
    plan: str
    trial_ends_at: datetime | None
    inbound_email: str | None


def generate_inbound_email(user_id: int) -> str:
    """Deterministic mapping `id → u{id}@<domain>`. Pure — no DB."""
    return f"u{user_id}@{_INBOUND_EMAIL_DOMAIN}"


def compute_trial_end(*, days: int = _DEFAULT_TRIAL_DAYS, now: datetime | None = None) -> datetime:
    """Return UTC `trial_ends_at = now + days`. `now` injectable for tests."""
    now = now or datetime.now(UTC)
    return now + timedelta(days=days)


def current_month_key(*, now: datetime | None = None) -> str:
    """Return current month key in `YYYY-MM` format (UTC)."""
    now = now or datetime.now(UTC)
    return now.strftime("%Y-%m")


def _row_to_user(row: Any) -> User:
    return User(
        id=int(row["id"]),
        channel_type=str(row["channel_type"]),
        channel_user_id=str(row["channel_user_id"]),
        chat_id=row["chat_id"],
        channel_chat_id=row["channel_chat_id"],
        locale=str(row["locale"]),
        timezone=str(row["timezone"]),
        plan=str(row["plan"]),
        trial_ends_at=row["trial_ends_at"],
        inbound_email=row["inbound_email"],
    )


async def create_or_get_user(
    *,
    channel_type: str,
    channel_user_id: str,
    chat_id: int | None = None,
    channel_chat_id: str | None = None,
    locale: str = "vi",
) -> tuple[User, bool]:
    """Idempotent user creation.

    Returns `(user, created)` where `created=True` only for the call that
    inserted the row. The handler uses `created` to gate one-shot side
    effects (mint webhook_token, seed categories, welcome-new message).

    Race semantics: two concurrent calls each attempt the INSERT;
    `ON CONFLICT (channel_type, channel_user_id) DO NOTHING` makes exactly
    one win, the other re-SELECTs the existing row.

    `inbound_email` is populated atomically post-INSERT within the same
    transaction so no row is ever observable with a NULL value — keeps the
    F07 / migration 0003 contract intact.
    """
    pool = db.get_pool()
    trial_end = compute_trial_end()
    async with pool.acquire() as conn:
        async with conn.transaction():
            inserted = await conn.fetchrow(
                """
                INSERT INTO users (
                    channel_type, channel_user_id, chat_id, channel_chat_id,
                    plan, trial_ends_at, locale
                )
                VALUES ($1, $2, $3, $4, 'free', $5, $6)
                ON CONFLICT (channel_type, channel_user_id) DO NOTHING
                RETURNING id;
                """,
                channel_type,
                channel_user_id,
                chat_id,
                channel_chat_id,
                trial_end,
                locale,
            )
            if inserted is None:
                existing = await conn.fetchrow(
                    "SELECT * FROM users WHERE channel_type = $1 AND channel_user_id = $2;",
                    channel_type,
                    channel_user_id,
                )
                if existing is None:
                    # ON CONFLICT consumed the row mid-flight (extremely unlikely:
                    # would require a DELETE between our INSERT attempt and the
                    # SELECT). Surface as a clear error rather than a None deref.
                    raise RuntimeError(
                        f"create_or_get_user: row vanished for "
                        f"({channel_type}, {channel_user_id})"
                    )
                # Self-heal: if a previous /start landed without a routable
                # `chat_id` (e.g. originated outside a private chat) and the
                # current call carries one, backfill it. Never overwrite a
                # populated `chat_id` — that would clobber a user who legitimately
                # changed their DM context.
                if chat_id is not None and existing["chat_id"] is None:
                    refreshed = await conn.fetchrow(
                        """
                        UPDATE users
                        SET chat_id = $2, updated_at = NOW()
                        WHERE id = $1 AND chat_id IS NULL
                        RETURNING *;
                        """,
                        existing["id"],
                        chat_id,
                    )
                    if refreshed is not None:
                        existing = refreshed
                # Same self-heal pattern for string channel routing IDs used
                # by non-Telegram platforms. Preserve any existing value.
                if channel_chat_id is not None and existing["channel_chat_id"] is None:
                    refreshed = await conn.fetchrow(
                        """
                        UPDATE users
                        SET channel_chat_id = $2, updated_at = NOW()
                        WHERE id = $1 AND channel_chat_id IS NULL
                        RETURNING *;
                        """,
                        existing["id"],
                        channel_chat_id,
                    )
                    if refreshed is not None:
                        existing = refreshed
                return _row_to_user(existing), False

            inbound = generate_inbound_email(int(inserted["id"]))
            row = await conn.fetchrow(
                """
                UPDATE users
                SET inbound_email = $2, updated_at = NOW()
                WHERE id = $1
                RETURNING *;
                """,
                inserted["id"],
                inbound,
            )
            assert row is not None  # we just inserted id, UPDATE must hit
    return _row_to_user(row), True


async def seed_default_categories(
    user_id: int, *, locale: str = "vi", now: datetime | None = None
) -> None:
    """Seed 3 starter categories for `user_id` in the current month.

    Idempotent via `UNIQUE(user_id, slug, month_key)` → re-runs no-op.
    Names render via `i18n.t(locale, key)`; missing keys fall back to
    `[MISSING: key]` so the column is never NULL (categories.name NOT NULL).
    """
    month_key = current_month_key(now=now)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for cat in DEFAULT_CATEGORIES:
                name = t(locale, str(cat["i18n_key"]))
                await conn.execute(
                    """
                    INSERT INTO categories (
                        user_id, slug, name, daily_cap, month_key, active
                    )
                    VALUES ($1, $2, $3, $4, $5, TRUE)
                    ON CONFLICT (user_id, slug, month_key) DO NOTHING;
                    """,
                    user_id,
                    cat["slug"],
                    name,
                    cat["daily_cap"],
                    month_key,
                )


__all__ = [
    "DEFAULT_CATEGORIES",
    "User",
    "compute_trial_end",
    "create_or_get_user",
    "current_month_key",
    "generate_inbound_email",
    "seed_default_categories",
]
