# Phase 01 — Startup wiring (DB pool + Sentry + structlog + request_id)

## Context Links

- Finding: `plans/reports/code-review-260514-full-codebase-deep.md` § C1
- Files: `main.py`, `core/db.py`, `core/observability.py`, `core/logging.py`
- Reference: `tests/integration/conftest.py:36` (existing pool init pattern)

## Overview

- **Priority:** P0 (blocks Phase 2)
- **Status:** Not Started
- **Description:** App boots without DB pool, Sentry, structlog config, or request_id middleware. Phase 2 route needs all four. Wire them via FastAPI `lifespan` context manager (modern, replaces deprecated `@app.on_event`).

## Key Insights

- Startup-time errors crash the bot — must fail fast on missing `DATABASE_URL` only when env is prod, else degrade.
- `tg.set_my_commands()` already in legacy `@app.on_event("startup")` — preserve.
- `init_sentry()` no-ops on empty DSN — safe for local/preview envs.
- `configure_logging` is idempotent — call early so even startup logs render structured.
- `request_id_middleware` is async function → use `app.middleware("http")` decorator pattern.

## Requirements

### Functional
- On startup: `configure_logging(env=APP_ENV)`, `await create_pool(DATABASE_URL)`, `init_sentry(SENTRY_DSN)`, register `request_id_middleware`.
- On shutdown: `await close_pool()`.
- Health endpoint `GET /` still returns 200 (Railway healthcheck).
- Legacy `/webhook` path unchanged in behavior.

### Non-functional
- Boot time ≤ 5s (Railway healthcheck timeout = 30s, headroom).
- If `DATABASE_URL` missing AND `APP_ENV in {prod,production,staging}` → raise at startup (fail-fast, no silent multi-tenant break).
- If `DATABASE_URL` missing AND env = dev/local → log warning, continue (legacy mode still works).

## Architecture

Sequence:
```
uvicorn boot
  → FastAPI lifespan() enter
    → configure_logging(env)
    → init_sentry(dsn)             # no-op if dsn empty
    → if DATABASE_URL: await create_pool(dsn)
    → tg.set_my_commands()         # preserved
  → app accepts requests
  → every request → request_id_middleware stamps X-Request-ID
  → FastAPI lifespan() exit
    → await close_pool()
```

## Related Code Files

### Modify
- `main.py` — replace `@app.on_event("startup")` with `lifespan`; register middleware.

### Create
- `tests/integration/test_app_startup.py` — boot the FastAPI app via TestClient, assert `/` returns 200, assert `X-Request-ID` header present on response, assert DB pool initialised (call `db.get_pool()` post-startup).

### Delete
- None (`@app.on_event("startup")` block replaced in-place).

## Implementation Steps

1. Add `from contextlib import asynccontextmanager` and `import os` (if not already) at top of `main.py`.
2. Add imports: `from core import db`, `from core.logging import configure_logging`, `from core.observability import init_sentry, request_id_middleware`.
3. Define `@asynccontextmanager async def lifespan(app)`:
   - `configure_logging(env=os.environ.get("APP_ENV"))`.
   - `init_sentry(os.environ.get("SENTRY_DSN"))`.
   - `dsn = os.environ.get("DATABASE_URL", "")`.
   - If `dsn`: `await db.create_pool(dsn)`.
   - Elif `APP_ENV in {prod,production,staging}`: `raise RuntimeError("DATABASE_URL required in prod")`.
   - Else: `print("[startup] DATABASE_URL not set — legacy single-tenant mode only")`.
   - Try `await tg.set_my_commands()` (existing best-effort).
   - `yield`.
   - `await db.close_pool()` (idempotent).
4. Replace `app = FastAPI(title="Financial Tracking Bot")` with `app = FastAPI(title="Financial Tracking Bot", lifespan=lifespan)`.
5. Delete the existing `@app.on_event("startup") async def on_startup()` block.
6. Register middleware: `app.middleware("http")(request_id_middleware)` immediately after `app = FastAPI(...)`.
7. Run pytest. Confirm no regression.
8. Manual smoke: `uvicorn main:app --host 0.0.0.0 --port 8000` against test Postgres → `curl localhost:8000/` returns 200 with `X-Request-ID` header.

## Todo List

- [ ] Refactor `main.py` startup → `lifespan` context manager
- [ ] Register `request_id_middleware`
- [ ] Add `DATABASE_URL` strict-prod check
- [ ] Write `tests/integration/test_app_startup.py`
- [ ] Verify full test suite passes (458+ tests, 0 new failures)
- [ ] Manual smoke locally
- [ ] Update `.env.example` to document `APP_ENV`, `SENTRY_DSN`, `DATABASE_URL`
- [ ] Open PR; merge to main; observe Railway deploy logs

## Success Criteria

- All existing 458+ tests pass.
- New `test_app_startup.py` asserts: app boots, `/` returns 200, response has `X-Request-ID` header, `db.get_pool()` callable after startup.
- Railway deploy logs show structured JSON (one line per log event).
- `/` returns 200 within 5s of boot.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lifespan migration changes startup error semantics | Med | High (bot crashes) | Manual smoke before merge; keep legacy `set_my_commands` best-effort |
| `DATABASE_URL` missing on Railway prod | Low | High | Strict-prod check raises early with clear message; verify env in Railway dashboard pre-deploy |
| Middleware ordering breaks existing routes | Low | Med | `request_id_middleware` only adds header + ContextVar; no body mutation |
| Sentry DSN leak via env dump | Low | Med | DSN already env-only; no change |

## Security Considerations

- No new attack surface (no new routes).
- Sentry `before_send` already redacts PII (`send_default_pii=False`).
- `request_id` is server-generated UUID4 (or honored from client header) — no auth bypass.

## Rollback

- `git revert <sha>` → Railway picks up prior commit on next push (or manual Railway Dashboard → Redeploy previous).
- No data side-effects (pool initialised but no schema change, no writes).

## Next Steps / Dependencies

- Phase 2 mounts the per-tenant route — depends on pool being initialised.
- Phase 3 telemetry uses `get_logger()` — needs `configure_logging` from this phase.
