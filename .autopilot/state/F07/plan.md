# F07 Settings — autopilot plan (chunk I)

## Files to create
- `handlers/settings.py` — `/settings` command + callbacks (regen, tz, recap, lang, upgrade). Renders via `core.locale_svc.t()`, dispatches through `core.messenger`. Telegram path only (G9).
- `core/settings_svc.py` — pure service: get_settings, regen_webhook_token (DELETE+INSERT in tx, returns plaintext + display_suffix), set_timezone (zoneinfo validate), toggle_recap, set_locale, compute_plan_status, backfill_inbound_email.
- `tests/unit/test_settings_svc.py` — service unit tests (timezone validation, plan status logic, locale fallback).
- `tests/integration/test_settings_handler.py` — handler + DB integration tests (testcontainers), incl. tenant isolation + concurrent regen.

## Files to modify
- `core/locale_svc.py` — add settings.* keys (vi/en) for overview rows, button labels, errors (`SETTINGS_TZ_INVALID`, `SETTINGS_REGEN_FAIL`), plan_status strings.
- `handlers/__init__.py` — register settings handler.
- `core/db.py` — add minimal helpers if not present (read users row, update single column, webhook_tokens DELETE+INSERT tx). Reuse existing where possible.

## Migrations
- NONE (G1 closed; `display_suffix` landed in 0002_webhook_display_suffix.py W0.8).

## Integration points
- `webhook_tokens` table (kind='sepay', token_hash=SHA256, display_suffix populated on mint) — G2/G3.
- `users.daily_recap_enabled` flag only; F09 owns next_run_utc (G6).
- `core.messenger.send()` BaseSender contract (no channel branching in core/) — G9.
- Analytics: emit `settings_opened`, `settings_webhook_regenerated`, `settings_timezone_changed`, `settings_recap_toggled`, `settings_language_changed`.

## Risks
- Concurrent regen relies on UNIQUE(user_id, kind); test must assert exactly one survivor.
- zoneinfo membership check before any DB write (SQLi-shape input safety).
- inbound_email backfill must be idempotent + race-safe (use INSERT ... ON CONFLICT or UPDATE WHERE inbound_email IS NULL).
- Bank connections row deferred (G8) — do NOT render.
- BE tech doc is stale (mentions users.webhook_token, pytz, direct scheduled_jobs writes) — FOLLOW FE gaps block, not BE doc §2/§4.
