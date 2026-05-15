# C1 diagnosis confirmation (2026-05-14)

Verified by direct file inspection. No hidden alternate entry points exist.

## FastAPI route inventory

Only `main.py` registers routes against the live `app`:

| Method | Path | Handler | Tenant-safe? |
|--------|------|---------|--------------|
| POST | `/webhook` | `_process` → legacy `handle_sepay_webhook` (else arm) | ❌ writes to global Sheet by `CHAT_ID` |
| POST | `/webhook/email` | `_process_email` → legacy `handle_sepay_webhook` | ❌ same |
| POST | `/trigger/weekly` | `run_weekly_summary` | ❌ single-tenant |
| POST | `/trigger/monthly-report` | `run_monthly_report` | ❌ single-tenant |
| POST | `/trigger/monthly-allocation` | `start_monthly_allocation` | ❌ single-tenant |
| POST | `/trigger/daily-recap` | `send_daily_recap` | ❌ single-tenant |
| GET | `/` | health | n/a |
| GET | `/dashboard` | dashboard html | n/a |
| GET | `/dashboard.md` | dashboard markdown | n/a |

`core/observability.py:121` defines `health_app = FastAPI(...)` — separate sub-app, NOT mounted anywhere. So `/health` and `/health/detailed` are NOT served in prod. (Phase 1 may optionally mount it — out of scope.)

## Startup hook inventory

`main.py:39-46` — only `tg.set_my_commands()` is called. No `create_pool`, `init_sentry`, `configure_logging`, no middleware registration.

## Pipeline modules (ready, unwired)

- `markets/vn/capture/sepay_webhook.py` — `handle_sepay_webhook(token, payload)` returns `{"ok": True}` always; uses `resolve_token` + `tenant_context.set_tenant` correctly.
- `markets/vn/capture/webhook_tokens.py` — SHA-256 hash storage, `hmac.compare_digest` lookup, ON CONFLICT UPDATE remint.
- `core/db.py` — singleton asyncpg pool; `create_pool` / `get_pool` / `close_pool`.
- `core/observability.py` — `init_sentry`, `request_id_middleware`, `health_app`.
- `core/logging.py` — `configure_logging` (idempotent), structlog JSON in prod.
- `core/tenant_context.py` — ContextVar for `user_id` + `request_id` binding.

## F01 `/start` wiring

`main.py:217-249` — wired. On `/start`:
- Calls `core.handlers.start.handle_start` which calls `user_svc.create_or_get_user` + `mint_token(user_id, kind="sepay")`.
- Welcome message rendered via `messenger.send`.
- Token minting succeeds but downstream consumer (the route) is missing → C1.

## Env vars expected

- `DATABASE_URL` — used by tests via `pg_url_async` fixture; `core/db.py` does not read env directly. **Phase 1 must add the read.**
- `SENTRY_DSN` — `init_sentry` reads from env default.
- `APP_ENV` — `configure_logging` reads from env; switches JSON vs console renderer.
- `CHAT_ID` — legacy single-tenant key; still used by `_handle_message:state = sh.get_state(CHAT_ID)`. Phase 5 only removes SePay dispatch; CHAT_ID removal blocked on F02.
- `BOT_TOKEN` — Telegram API.

## No hidden entry points

`grep -rn "app.post\|app.get\|FastAPI("` shows only `main.py` and `core/observability.py:121` (unmounted). Diagnosis intact.
