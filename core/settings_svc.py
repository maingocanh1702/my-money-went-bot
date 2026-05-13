"""Settings service — pure DB operations for user-level config (F07).

Spec: docs/features/feature-settings.md (autopilot:gaps locked 2026-05-12).

Scope (per F07 plan, chunk I):
  - Read overview row (users + active webhook_tokens metadata) — PURE READ.
  - Validate + persist `users.timezone` (stdlib `zoneinfo`).
  - Toggle `users.daily_recap_enabled` (no scheduled_jobs writes — G6).
  - Persist `users.locale` (validated against i18n.SUPPORTED_LOCALES).
  - Compute plan-status display tuple from existing columns (G5).
  - `ensure_inbound_email` — idempotent backfill helper, called only from
    trusted callsites (migration 0003 / future auth gate). NOT invoked
    from `get_overview`. See spec G4 for the read/write split rationale.

Out of scope:
  - Webhook token mint/regen — lives in markets.vn.capture.webhook_tokens
    (core/ must NOT import markets/ per ADR-0001). Handler orchestrates.
  - scheduled_jobs writes (F09 owns recalculation on tz/recap change).
  - Channel UI dispatch — that's handlers/settings.py + core.messenger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal
from zoneinfo import ZoneInfo, available_timezones

from core import db
from core.logging import get_logger
from i18n import SUPPORTED_LOCALES

_log = get_logger(__name__)

_VALID_TZS: Final[frozenset[str]] = frozenset(available_timezones())
_MAX_TZ_LEN: Final[int] = 64  # matches users.timezone VARCHAR(64)
_INBOUND_EMAIL_DOMAIN: Final[str] = "in.mymoneywent.com"

PlanStatus = Literal["free", "trial", "active", "expired"]


@dataclass(frozen=True)
class SettingsOverview:
    """All values needed to render /settings — one round-trip from DB."""

    user_id: int
    locale: str
    timezone: str
    inbound_email: str | None
    daily_recap_enabled: bool
    plan: str
    plan_status: PlanStatus
    trial_days_left: int | None
    webhook_created_at: datetime | None
    webhook_display_suffix: str | None


@dataclass(frozen=True)
class PlanStatusInfo:
    """Plan-status decomposition for UI rendering (G5)."""

    status: PlanStatus
    days_left: int | None


def is_valid_timezone(raw: str) -> bool:
    """Pure check — no DB, no side effects, safe on adversarial input.

    Bounded length first so a 10KB string can't pump the hash lookup.
    Then membership against `zoneinfo.available_timezones()`. SQLi-shaped
    strings ("Asia/Ho_Chi_Minh'; DROP TABLE users; --") fall out at the
    membership check before any DB write.
    """
    if not raw or len(raw) > _MAX_TZ_LEN:
        return False
    if raw not in _VALID_TZS:
        return False
    # Belt-and-braces: zoneinfo.ZoneInfo will raise on malformed names that
    # somehow slip past the set membership (shouldn't, but cheap to verify).
    try:
        ZoneInfo(raw)
    except Exception:
        return False
    return True


def compute_plan_status(
    plan: str,
    trial_ends_at: datetime | None,
    plan_expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> PlanStatusInfo:
    """G5: status = trial > expired > active; free always returns ("free", None).

    `now` injectable for tests; defaults to UTC now.
    """
    now = now or datetime.now(UTC)
    if plan == "free":
        return PlanStatusInfo(status="free", days_left=None)
    if trial_ends_at is not None and trial_ends_at > now:
        # Round up partial days so "5d 1h" reads as "5 days left", not "4".
        delta = trial_ends_at - now
        days_left = max(1, (delta.days * 86_400 + delta.seconds + 86_399) // 86_400)
        return PlanStatusInfo(status="trial", days_left=days_left)
    if plan_expires_at is not None and plan_expires_at < now:
        return PlanStatusInfo(status="expired", days_left=None)
    return PlanStatusInfo(status="active", days_left=None)


def _coerce_locale(raw: str | None) -> str:
    """Tolerant fallback to default locale ('vi') for NULL/unknown values."""
    if raw is None or raw not in SUPPORTED_LOCALES:
        return "vi"
    return raw


async def get_overview(user_id: int) -> SettingsOverview:
    """PURE READ — single LEFT JOIN of users + active webhook_tokens row.

    No DB writes. `inbound_email` is returned as-is (possibly None for legacy
    rows that pre-date backfill migration 0003). Callers / UI must handle
    None by rendering the deterministic fallback `f"u{user_id}@<domain>"`.

    See spec G4 (revised 2026-05-13) for the read/write split rationale.
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                u.id,
                u.locale,
                u.timezone,
                u.inbound_email,
                u.daily_recap_enabled,
                u.plan,
                u.trial_ends_at,
                u.plan_expires_at,
                wt.created_at      AS webhook_created_at,
                wt.display_suffix  AS webhook_display_suffix
            FROM users u
            LEFT JOIN webhook_tokens wt
              ON wt.user_id = u.id
             AND wt.kind = 'sepay'
             AND wt.revoked_at IS NULL
            WHERE u.id = $1;
            """,
            user_id,
        )
    if row is None:
        raise LookupError(f"user_id={user_id} not found")

    plan_info = compute_plan_status(
        plan=row["plan"],
        trial_ends_at=row["trial_ends_at"],
        plan_expires_at=row["plan_expires_at"],
    )

    return SettingsOverview(
        user_id=row["id"],
        locale=_coerce_locale(row["locale"]),
        timezone=row["timezone"],
        inbound_email=row["inbound_email"],
        daily_recap_enabled=row["daily_recap_enabled"],
        plan=row["plan"],
        plan_status=plan_info.status,
        trial_days_left=plan_info.days_left,
        webhook_created_at=row["webhook_created_at"],
        webhook_display_suffix=row["webhook_display_suffix"],
    )


def fallback_inbound_email(user_id: int) -> str:
    """Deterministic display fallback for NULL inbound_email rows.

    Pure — no DB. Used by UI when `SettingsOverview.inbound_email is None`.
    Same formula as `ensure_inbound_email` so the displayed value matches
    what a future backfill would persist.
    """
    return f"u{user_id}@{_INBOUND_EMAIL_DOMAIN}"


async def get_locale(user_id: int) -> str:
    """Read-only locale fetch with no side effects (no inbound_email backfill).

    Used by handlers that must render an i18n error message on rejected input
    without mutating user state. Falls back to default locale on NULL/unknown.
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        raw = await conn.fetchval("SELECT locale FROM users WHERE id = $1;", user_id)
    return _coerce_locale(raw)


async def set_timezone(user_id: int, tz: str) -> bool:
    """Validate `tz`, write to users.timezone scoped to `user_id`.

    Returns True on success, False if tz invalid (caller renders error).
    Tenant isolation: WHERE id = $1 — payload `user_id` MUST be the
    authenticated session user, NEVER from callback_data (handler's job).
    """
    if not is_valid_timezone(tz):
        return False
    pool = db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET timezone = $2, updated_at = NOW() WHERE id = $1;",
            user_id,
            tz,
        )
    # asyncpg returns "UPDATE <n>"; n=0 means user vanished mid-call.
    return bool(result.endswith(" 1"))


async def toggle_recap(user_id: int) -> bool:
    """Flip users.daily_recap_enabled; return the NEW value.

    Single UPDATE ... RETURNING avoids the read-modify-write race.
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        new_value = await conn.fetchval(
            """
            UPDATE users
            SET daily_recap_enabled = NOT daily_recap_enabled,
                updated_at = NOW()
            WHERE id = $1
            RETURNING daily_recap_enabled;
            """,
            user_id,
        )
    if new_value is None:
        raise LookupError(f"user_id={user_id} not found")
    return bool(new_value)


async def set_locale(user_id: int, locale: str) -> bool:
    """Persist users.locale. Validates against i18n.SUPPORTED_LOCALES.

    Idempotent at the DB layer (write still runs but the value is the same);
    the handler is responsible for short-circuiting no-op analytics events
    per test_locale_change_idempotent_same_locale.
    """
    if locale not in SUPPORTED_LOCALES:
        return False
    pool = db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET locale = $2, updated_at = NOW() WHERE id = $1;",
            user_id,
            locale,
        )
    return bool(result.endswith(" 1"))


async def ensure_inbound_email(user_id: int) -> str:
    """Idempotent backfill of users.inbound_email when NULL.

    Trusted callsites only — invoke from migration / onboarding / a future
    post-auth gate. NOT called from `get_overview` (spec G4, revised
    2026-05-13: get_overview is pure-read).

    Idempotent + race-safe: `UPDATE ... WHERE inbound_email IS NULL` only
    writes when the column is still NULL; a concurrent backfill loses the
    race silently. The trailing `SELECT` re-reads so we always return the
    canonical value, whether we wrote it or someone else did.
    """
    canonical = f"u{user_id}@{_INBOUND_EMAIL_DOMAIN}"
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET inbound_email = $2, updated_at = NOW()
            WHERE id = $1 AND inbound_email IS NULL;
            """,
            user_id,
            canonical,
        )
        current = await conn.fetchval(
            "SELECT inbound_email FROM users WHERE id = $1;",
            user_id,
        )
    if current is None:
        raise LookupError(f"user_id={user_id} not found")
    return str(current)


async def emit_analytics(
    user_id: int,
    event_name: str,
    properties: dict[str, object] | None = None,
) -> None:
    """Append-only insert into analytics_events. Never raises on caller path.

    F07 events: settings_opened, settings_webhook_regenerated,
    settings_timezone_changed, settings_recap_toggled, settings_language_changed.
    """
    import json

    pool = db.get_pool()
    payload = json.dumps(properties or {})
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analytics_events (user_id, event_name, properties)
                VALUES ($1, $2, $3::jsonb);
                """,
                user_id,
                event_name,
                payload,
            )
    except Exception as exc:  # noqa: BLE001 — best-effort: never raise on caller path
        _log.warning(
            "analytics.emit_failed",
            event_name=event_name,
            user_id=user_id,
            error=str(exc),
        )


__all__ = [
    "PlanStatus",
    "PlanStatusInfo",
    "SettingsOverview",
    "compute_plan_status",
    "emit_analytics",
    "ensure_inbound_email",
    "fallback_inbound_email",
    "get_locale",
    "get_overview",
    "is_valid_timezone",
    "set_locale",
    "set_timezone",
    "toggle_recap",
]
