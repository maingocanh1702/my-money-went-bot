"""/settings handler — assembles the overview, dispatches button callbacks.

Spec: docs/features/feature-settings.md (F07).

Architecture:
  - Renders via abstract `core.messenger.SendPayload` + `Markup`; no
    Telegram-specific structures here (ADR-0001 / W0.4 BaseSender).
  - Business mutations live in `core.settings_svc` (pure, no markets/ deps).
  - Webhook-token regen calls `markets.vn.capture.webhook_tokens.mint_token`
    — the handler layer is allowed to bridge core ↔ markets (the import
    boundary only forbids core → markets, not handlers → markets).

Callback data scheme — short, parseable, no payload trust:
  - "settings:open"               → re-render overview
  - "settings:regen"              → mint new sepay token, send raw once
  - "settings:tz_prompt"          → ask user to type a timezone
  - "settings:recap_toggle"       → flip flag, re-render
  - "settings:lang_pick"          → show lang chooser
  - "settings:lang_set:vi|en"     → write locale, re-render
  - "settings:upgrade"            → handed off to upgrade flow (stub here)

Tenant safety:
  - `user_id` ALWAYS comes from the authenticated session — NEVER from
    callback_data. Forged callbacks that name another user are ignored
    because the handler never reads a user_id field from `data`.
"""

from __future__ import annotations

from typing import Final

from core import messenger, settings_svc
from core.messenger import Button, Markup, SendPayload
from i18n import SUPPORTED_LOCALES
from markets.vn.capture.webhook_tokens import mint_token

# Callback data namespace — kept tiny to fit Telegram's 64-byte cap.
CB_OPEN: Final[str] = "settings:open"
CB_REGEN: Final[str] = "settings:regen"
CB_TZ_PROMPT: Final[str] = "settings:tz_prompt"
CB_RECAP_TOGGLE: Final[str] = "settings:recap_toggle"
CB_LANG_PICK: Final[str] = "settings:lang_pick"
CB_LANG_SET_PREFIX: Final[str] = "settings:lang_set:"
CB_UPGRADE: Final[str] = "settings:upgrade"


def _plan_row_key(status: settings_svc.PlanStatus) -> str:
    if status == "free":
        return "settings.row_plan_free"
    if status == "trial":
        return "settings.row_plan_trial"
    if status == "expired":
        return "settings.row_plan_expired"
    return "settings.row_plan_active"


def _webhook_row(
    overview: settings_svc.SettingsOverview,
) -> tuple[str, dict[str, object]]:
    """Return (text_key, params) for the webhook row — three states."""
    if overview.webhook_created_at is None:
        return "settings.row_webhook_missing", {}
    created = overview.webhook_created_at.date().isoformat()
    if overview.webhook_display_suffix:
        return (
            "settings.row_webhook_configured",
            {"created": created, "suffix": overview.webhook_display_suffix},
        )
    return "settings.row_webhook_configured_no_suffix", {"created": created}


def _render_overview_text(overview: settings_svc.SettingsOverview) -> str:
    """Compose the multi-line overview via i18n.t() — locale-correct."""
    from i18n import t

    locale = overview.locale
    lines: list[str] = [t(locale, "settings.overview_title"), ""]

    wh_key, wh_params = _webhook_row(overview)
    lines.append(t(locale, wh_key, **wh_params))
    # G4: get_overview is pure-read; render fallback when inbound_email is
    # still NULL (legacy row pre-migration 0003). Formula matches what a
    # subsequent backfill via ensure_inbound_email() would persist.
    email = overview.inbound_email or settings_svc.fallback_inbound_email(overview.user_id)
    lines.append(t(locale, "settings.row_email", email=email))
    lines.append(t(locale, "settings.row_timezone", tz=overview.timezone))
    lines.append(
        t(
            locale,
            "settings.row_recap_on" if overview.daily_recap_enabled else "settings.row_recap_off",
        )
    )

    plan_key = _plan_row_key(overview.plan_status)
    plan_params: dict[str, object] = {"plan": overview.plan.capitalize()}
    if overview.plan_status == "trial" and overview.trial_days_left is not None:
        plan_params["days"] = overview.trial_days_left
    lines.append(t(locale, plan_key, **plan_params))

    lines.append(
        t(
            locale,
            "settings.row_language_vi" if locale == "vi" else "settings.row_language_en",
        )
    )
    return "\n".join(lines)


def _overview_markup(overview: settings_svc.SettingsOverview) -> Markup:
    recap_btn_key = (
        "settings.btn_recap_off" if overview.daily_recap_enabled else "settings.btn_recap_on"
    )
    return Markup(
        rows=[
            [
                Button(label_key="settings.btn_regen", callback_data=CB_REGEN),
                Button(label_key="settings.btn_tz", callback_data=CB_TZ_PROMPT),
            ],
            [
                Button(label_key=recap_btn_key, callback_data=CB_RECAP_TOGGLE),
                Button(label_key="settings.btn_upgrade", callback_data=CB_UPGRADE),
            ],
            [Button(label_key="settings.btn_lang", callback_data=CB_LANG_PICK)],
        ]
    )


async def _send_overview(user_id: int, overview: settings_svc.SettingsOverview) -> None:
    payload: SendPayload = {
        "text": _render_overview_text(overview),
        "locale": overview.locale,
        "markup": _overview_markup(overview),
        "parse_mode": "plain",
    }
    await messenger.send(user_id, payload)


async def handle_settings_command(user_id: int) -> None:
    """`/settings` entry point — render overview, emit settings_opened."""
    overview = await settings_svc.get_overview(user_id)
    await _send_overview(user_id, overview)
    await settings_svc.emit_analytics(user_id, "settings_opened")


async def _handle_regen(user_id: int, locale: str) -> None:
    try:
        raw = await mint_token(user_id, kind="sepay")
    except Exception:
        await messenger.send(
            user_id,
            {
                "text_key": "settings.regen_fail",
                "locale": locale,
                "parse_mode": "plain",
            },
        )
        return
    # Codex R1 P2 2026-05-13: webhook tokens from secrets.token_urlsafe()
    # can contain `_` which Telegram's classic Markdown parser mangles even
    # inside backticks. Send as plain so the raw token is delivered exactly
    # — the user copy/pastes it verbatim into SePay.
    await messenger.send(
        user_id,
        {
            "text_key": "settings.regen_success",
            "text_params": {"token": raw},
            "locale": locale,
            "parse_mode": "plain",
        },
    )
    await settings_svc.emit_analytics(user_id, "settings_webhook_regenerated")
    overview = await settings_svc.get_overview(user_id)
    await _send_overview(user_id, overview)


async def _handle_recap_toggle(user_id: int, locale: str) -> None:
    new_value = await settings_svc.toggle_recap(user_id)
    await messenger.send(
        user_id,
        {
            "text_key": (
                "settings.recap_toggled_on" if new_value else "settings.recap_toggled_off"
            ),
            "locale": locale,
            "parse_mode": "plain",
        },
    )
    await settings_svc.emit_analytics(user_id, "settings_recap_toggled", {"enabled": new_value})
    overview = await settings_svc.get_overview(user_id)
    await _send_overview(user_id, overview)


async def _handle_lang_pick(user_id: int, locale: str) -> None:
    markup = Markup(
        rows=[
            [
                Button(label_key="btn.lang_vi", callback_data=f"{CB_LANG_SET_PREFIX}vi"),
                Button(label_key="btn.lang_en", callback_data=f"{CB_LANG_SET_PREFIX}en"),
            ]
        ]
    )
    await messenger.send(
        user_id,
        {
            "text_key": "settings.lang_pick_prompt",
            "locale": locale,
            "markup": markup,
            "parse_mode": "plain",
        },
    )


async def _handle_lang_set(user_id: int, new_locale: str, old_locale: str) -> None:
    if new_locale not in SUPPORTED_LOCALES:
        return
    if new_locale == old_locale:
        # Idempotent — no DB write, no analytics event (per test_plan).
        overview = await settings_svc.get_overview(user_id)
        await _send_overview(user_id, overview)
        return
    ok = await settings_svc.set_locale(user_id, new_locale)
    if not ok:
        return
    await settings_svc.emit_analytics(
        user_id,
        "settings_language_changed",
        {"old_locale": old_locale, "new_locale": new_locale},
    )
    overview = await settings_svc.get_overview(user_id)
    await _send_overview(user_id, overview)


async def _handle_tz_prompt(user_id: int, locale: str) -> None:
    """Phase 1 stub: prompt user to type a timezone.

    Multi-step state (await_settings_tz → handle_timezone_input) is wired
    by the channel-specific message dispatcher; F07's contract here is the
    prompt + the `handle_timezone_input` entry below.
    """
    await messenger.send(
        user_id,
        {
            "text_key": "settings.tz_prompt",
            "locale": locale,
            "parse_mode": "plain",
        },
    )


async def handle_timezone_input(user_id: int, raw_tz: str, old_tz: str) -> bool:
    """Called by the channel message dispatcher when user is in
    `await_settings_tz` state. Returns True on success."""
    # Cheap short-circuit on invalid input — saves a `set_timezone` DB
    # roundtrip. (Side-effect concern from earlier R2 fix is now moot:
    # `get_overview` is pure-read post-G4 refactor.)
    if not settings_svc.is_valid_timezone(raw_tz):
        await messenger.send(
            user_id,
            {
                "text_key": "settings.tz_invalid",
                "locale": await settings_svc.get_locale(user_id),
                "parse_mode": "plain",
            },
        )
        return False
    if not await settings_svc.set_timezone(user_id, raw_tz):
        # Race: user row vanished mid-call. Surface as invalid to caller.
        await messenger.send(
            user_id,
            {
                "text_key": "settings.tz_invalid",
                "locale": await settings_svc.get_locale(user_id),
                "parse_mode": "plain",
            },
        )
        return False
    overview = await settings_svc.get_overview(user_id)
    await messenger.send(
        user_id,
        {
            "text_key": "settings.tz_changed",
            "text_params": {"tz": raw_tz},
            "locale": overview.locale,
            "parse_mode": "plain",
        },
    )
    await settings_svc.emit_analytics(
        user_id,
        "settings_timezone_changed",
        {"old_tz": old_tz, "new_tz": raw_tz},
    )
    await _send_overview(user_id, overview)
    return True


async def _handle_upgrade(user_id: int, locale: str) -> None:
    """Stub: real upgrade flow ships in F-pricing/F-upgrade (Wave later)."""
    await messenger.send(
        user_id,
        {
            "text_key": "upgrade.cta",
            "locale": locale,
            "parse_mode": "plain",
        },
    )


async def handle_settings_callback(user_id: int, data: str) -> None:
    """Dispatch a `settings:*` callback. user_id MUST be authenticated."""
    if not data.startswith("settings:"):
        return
    # Always read fresh state — never trust payload for user attrs.
    # get_overview is pure-read (G4, 2026-05-13), so calling it before
    # sub-command dispatch is safe — unknown callbacks fall through to the
    # silent-ignore tail without side-effects.
    overview = await settings_svc.get_overview(user_id)
    locale = overview.locale

    if data == CB_OPEN:
        await _send_overview(user_id, overview)
        return
    if data == CB_REGEN:
        await _handle_regen(user_id, locale)
        return
    if data == CB_TZ_PROMPT:
        await _handle_tz_prompt(user_id, locale)
        return
    if data == CB_RECAP_TOGGLE:
        await _handle_recap_toggle(user_id, locale)
        return
    if data == CB_LANG_PICK:
        await _handle_lang_pick(user_id, locale)
        return
    if data.startswith(CB_LANG_SET_PREFIX):
        new_locale = data[len(CB_LANG_SET_PREFIX) :]
        await _handle_lang_set(user_id, new_locale, locale)
        return
    if data == CB_UPGRADE:
        await _handle_upgrade(user_id, locale)
        return
    # Unknown sub-command: ignore silently (forward-compat).


__all__ = [
    "CB_LANG_PICK",
    "CB_LANG_SET_PREFIX",
    "CB_OPEN",
    "CB_RECAP_TOGGLE",
    "CB_REGEN",
    "CB_TZ_PROMPT",
    "CB_UPGRADE",
    "handle_settings_callback",
    "handle_settings_command",
    "handle_timezone_input",
]
