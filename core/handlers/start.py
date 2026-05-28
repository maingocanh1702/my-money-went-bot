"""/start handler — multi-channel user onboarding entry point (F01).

Pattern: follows handlers/settings.py (F07) — renders via abstract
`core.messenger.SendPayload`; business mutations live in
`core.services.user_svc`.

Tenant safety: `user_id` is derived from the freshly-created (or
freshly-fetched) `users.id`, NEVER from update payload fields. The
channel_user_id parsed off the update is only the lookup key.

Scope (lockdown §1.2):
  - Telegram + Discord wired; Messenger postback comes later.
  - Onboarding paths A/B/C ship in Phase 4 (F01b/c/d).
  - Language confirm UI ships in F-i18n (we default locale='vi' here).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import asyncpg

from core import messenger
from core.logging import get_logger
from core.services import user_svc
from markets.vn.capture.webhook_tokens import mint_token

_log = get_logger(__name__)

# One retry on hash collision is enough: SHA-256 of `secrets.token_urlsafe(24)`
# has ~256-bit entropy. A second collision would point at an RNG bug, not bad
# luck — better to surface than to spin.
_TOKEN_MINT_ATTEMPTS = 2


def _format_trial_date(trial_ends_at: datetime, timezone: str) -> str:
    """Render trial end as `YYYY-MM-DD` in the user's timezone."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("Asia/Ho_Chi_Minh")
    return trial_ends_at.astimezone(tz).strftime("%Y-%m-%d")


async def _safe_send(user_id: int, payload: dict[str, object]) -> None:
    """Best-effort welcome dispatch.

    The user row is already committed by the time we reach the send; if the
    channel adapter is missing (e.g. Discord sender not yet registered) or
    the network is flaky, the right call is to log and continue, NOT to
    propagate the failure. The user can `/start` again or use `/settings`
    later — onboarding state on disk is intact.
    """
    try:
        await messenger.send(user_id, payload)  # type: ignore[arg-type]
    except KeyError as exc:
        # Raised by `messenger.send` when no adapter is registered for the
        # user's channel. Surface as a structured warning so we notice the
        # missing adapter, but never crash /start.
        _log.warning("onboard.send_no_adapter", user_id=user_id, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — best-effort: see docstring
        _log.error("onboard.send_failed", user_id=user_id, error=str(exc))


async def _mint_with_retry(user_id: int) -> str | None:
    """Mint a sepay webhook_token; retry once on UniqueViolation.

    Returns the raw token (caller responsible for display) or None if every
    attempt failed. None means the user is created but cannot receive SePay
    webhooks until /settings → regenerate; we log loudly so on-call notices.

    Any other failure (transient DB error, network hiccup, …) also degrades
    gracefully — onboarding continues with category seeding + welcome, and
    the user can recover via `/settings` later. Re-raising here would abort
    `/start` after the user row has already committed, leaving them in an
    "exists but never welcomed" state.
    """
    last_exc: Exception | None = None
    for attempt in range(_TOKEN_MINT_ATTEMPTS):
        try:
            return await mint_token(user_id, kind="sepay")
        except asyncpg.UniqueViolationError as exc:
            last_exc = exc
            _log.warning(
                "onboard.mint_token_collision",
                user_id=user_id,
                attempt=attempt + 1,
            )
            continue
        except Exception as exc:  # noqa: BLE001 — best-effort: see docstring
            _log.error(
                "onboard.mint_token_error",
                user_id=user_id,
                attempt=attempt + 1,
                error=str(exc),
            )
            return None
    _log.error(
        "onboard.mint_token_failed",
        user_id=user_id,
        error=str(last_exc) if last_exc else "unknown",
    )
    return None


async def handle_start(
    *,
    channel_type: str,
    channel_user_id: str,
    chat_id: int | None = None,
    channel_chat_id: str | None = None,
    language_code: str | None = None,
    display_name: str | None = None,
) -> None:
    """Entry point for `/start` across channels.

    On first call: creates user, mints sepay token, seeds default categories,
    sends welcome-new with rendered trial expiry. On re-call: idempotent —
    welcome-back message only.

    `language_code` is accepted but ignored in F01 (F-i18n owns the confirm
    UI). Plumbed through so callers don't need to change later.
    """
    _ = language_code  # F-i18n PR consumes; kept in signature for stability
    try:
        user, created = await user_svc.create_or_get_user(
            channel_type=channel_type,
            channel_user_id=channel_user_id,
            chat_id=chat_id,
            channel_chat_id=channel_chat_id,
            locale="vi",
        )
    except Exception as exc:
        # DB unavailable / migration not run / connection torn down — best
        # we can do is log loudly. We can't `messenger.send` without a user
        # row (channel resolution itself needs a DB lookup).
        _log.error(
            "onboard.create_fail",
            channel_type=channel_type,
            channel_user_id=channel_user_id,
            error=str(exc),
        )
        return

    locale = user.locale
    if not created:
        _ = display_name  # reserved for F-i18n; kept in signature for stability
        await _safe_send(
            user.id,
            {
                "text_key": "onboard.welcome_back",
                "locale": locale,
                "parse_mode": "plain",
            },
        )
        return

    await _mint_with_retry(user.id)
    await user_svc.seed_default_categories(user.id, locale=locale)

    trial_str = (
        _format_trial_date(user.trial_ends_at, user.timezone)
        if user.trial_ends_at is not None
        else ""
    )
    await _safe_send(
        user.id,
        {
            "text_key": "onboard.welcome_new",
            "text_params": {"trial_end": trial_str},
            "locale": locale,
            "parse_mode": "plain",
        },
    )


__all__ = ["handle_start"]
