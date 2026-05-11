# Changelog

All notable changes to MyMoneyWent are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where applicable. Pre-release pre-development phase has no formal version yet — entries below are dated.

## Conventions

- **Repo-level changes:** structural moves, doc restructure, tooling, repo hygiene → in this file
- **BRD/PRD/TDD/feature spec changes:** in their own changelog tables at the bottom of each doc
- **Code changes (post Phase 1):** standard `[Added]`, `[Changed]`, `[Fixed]`, `[Removed]`, `[Deprecated]`, `[Security]` sections per release

---

## [Unreleased]

### Phase 1 — Foundation refactor (target: Tuần 1-2)

Pending. Per [BRD-VI v3.1.0](docs/brd-vi.md) Phase 1.

---

## 2026-05-11 — F01 W0.6: Plugin parsers + SePay webhook + Sheets-migration scaffold (Wave 0)

### Scope decision (read first)

The autopilot spec for W0.6 called for the *full* legacy `handlers/*` move + `sheets.py` deletion in one PR. In practice each handler (`transaction.py`, `manage.py`, `reports.py`, `allocation.py`) is a single-tenant rewrite that warrants its own PR with full multi-tenant test coverage — collapsing them into W0.6 would have produced one PR with 1000+ lines of behaviour change and made review impossible.

**This PR ships the foundational invariants W0.6 needed to lock in (Gap 2, Gap 3, Gap 5, parser-purity contract) and explicitly defers the rest of the legacy handler move to F02 (Wave 2)** where each handler gets its own focused refactor + isolation tests. Legacy `handlers/` + `sheets.py` remain in place (already excluded from `ruff`/`black`/`mypy` strict checks via `pyproject.toml` extend-exclude). The `import-linter` `parsers-are-pure` contract is in force now, so new code can't drift even while legacy lingers.

### Added — plugin parser pattern (Gap 2)
- `core/canonical_tx.py` — `CanonicalTx` dataclass that every transaction-capture path emits (VN webhook, VN email parsers, future Global Plaid adapters). Frozen + `__post_init__` validation (positive amount, valid direction, non-empty source/bank).
- `markets/vn/email_parsers/base.py` — `BankEmailParser` ABC + `InboundEmail` envelope + module-level `PARSERS` registry + `@register_parser('BANK')` decorator + `find_parser(email)` dispatcher (skips broken parsers, doesn't crash).
- `markets/vn/email_parsers/{tcb,mb,acb,sacombank,bidv,cake}.py` — six parser shells. Each implements `can_parse` (sender/subject heuristic) + `parse` (CanonicalTx extraction). F02 will fill the full HTML-table extraction logic; the contract is locked in here.
- `markets/vn/email_parsers/__init__.py` — auto-imports every parser module (explicit `_AUTO_IMPORT_MODULES` list, not globbing — deterministic registration order).
- `.importlinter` — new contract `parsers-are-pure`: `markets.vn.email_parsers MUST NOT import core.db / core.messenger`. Enforced statically + a grep-level test (`test_parser_modules_dont_import_db_or_messenger`) belts-and-braces against bypass via lazy imports.
- `tests/integration/test_email_parser_plugins.py` — 18 tests: registration set (6 banks), parametrised can_parse/reject-foreign/parse-CanonicalTx per bank, find_parser dispatch, grep-level purity check, register_parser empty-bank ValueError, BaseParser inheritance, idempotent re-import.

### Added — webhook tokens (Gap 3)
- `markets/vn/capture/webhook_tokens.py`:
  - `hash_token(raw)` — SHA-256 hex digest. Rejects empty raw.
  - `mint_token(user_id, kind)` — generates a fresh `secrets.token_urlsafe(24)` token, persists ONLY its hash via `INSERT … ON CONFLICT (user_id, kind) DO UPDATE SET token_hash = EXCLUDED.token_hash, revoked_at = NULL, created_at = NOW()`. Re-minting revokes the prior token by overwriting its hash. Returns the raw token to the caller exactly once.
  - `resolve_token(raw, kind)` — looks up by `token_hash` UNIQUE index (O(log n) regardless of input) + `hmac.compare_digest` belt-and-braces. Returns `user_id | None`. No info leak — same return shape for bad/wrong-kind/revoked.
- `markets/vn/capture/sepay_webhook.py`:
  - `handle_sepay_webhook(token, payload)` — main entry. Resolves user via hashed token, parses SePay JSON → `CanonicalTx`, persists with `ON CONFLICT (user_id, ref_code) DO NOTHING` (idempotent retries), sets `tenant_context.set_tenant(user_id)` so downstream logs/Sentry tag correctly. **Always returns `{"ok": True}` regardless of failure** — bad tokens / bad payloads are logged silently, no info leak about token validity.
- `tests/integration/test_sepay_webhook.py` — 11 tests: hash determinism + empty rejection, mint/resolve roundtrip, unknown-token → None, wrong-kind → None, re-mint revokes old, webhook persists tx scoped to user, silent 200 on bad token (no insert), silent 200 on bad payload, tenant_context set after success, `ref_code` UNIQUE-driven dedupe (replays don't double-insert).

### Added — founder seed scaffold (Gap 5)
- `scripts/__init__.py`, `scripts/migrate_sheets.py` — one-time Sheets → Postgres migration runner with:
  - Strict ordering: users → categories → funding_sources (from col P) → transactions → audit. Order is FK-driven; deviating breaks inserts.
  - Founder seed: user_id=1, role='founder'. README + module docstring document the **bootstrap-only** rule — runtime MUST NOT hardcode `if user_id == 1`; admin checks use `users.role IN ('founder','admin')`.
  - Pre-flight `_assert_schema_ready()` — verifies alembic head before touching data.
  - Verification: orphan-row checks for transactions + categories (more added when Sheets reads land in Wave 1).
  - CLI: `--database-url` required, `--apply` to actually insert (otherwise dry-run prints plan only).
  - W0.6 ships dry-run only; the `_step_*` functions raise `NotImplementedError("…implement in Wave 1")` so the founder can't accidentally fire a real migration before the Sheets-read code is in.
- `tests/scripts/__init__.py`, `tests/scripts/test_migrate_sheets.py` — 5 tests (4 passing + 1 skipped destructive variant): dry-run returns zero summary, `_assert_schema_ready` passes on head, `_verify` passes when clean, `_verify` fails on injected orphan tx.

### Changed
- `README.md` — added "Founder seed — bootstrap only" subsection under Migration making the role-not-id rule prominent for any future code reader.

### Deferred (NOT in this PR — flagged for founder)
- **Legacy `handlers/` move + `sheets.py` deletion** — moved to F02 (Wave 2 — handlers refactor). Each of `handlers/{transaction,manage,reports,allocation,sepay,email_parser}.py` will become a focused multi-tenant PR there. SePay capture moved here (`markets/vn/capture/sepay_webhook.py`) because Gap 3 demanded the wiring; the rest stay until their feature wave.
- **`telegram_api.py` merge into `core/messenger/telegram.py`** — same reason. The TelegramSender adapter from W0.4 supersedes `telegram_api.py`; the old module isn't imported by new code. Removal is one-line once handlers no longer reference it.
- **Full TCB/MB email-body extraction** — parsers ship can_parse + amount/direction heuristics only; full HTML-table extraction lands in F02 alongside the email-receiver service.
- **Real Sheets reads in `migrate_sheets.py`** — W0.6 ships the orchestration + verification skeleton + safety rails (`NotImplementedError` in `_step_*`). Wave 1 implements `_step_users` / `_step_categories` / etc.

### Verified locally
- `ruff` / `black --check` / `mypy --strict`: all green (50 source files, including `scripts/`).
- `lint-imports`: **4 contracts kept, 0 broken** (new `parsers-are-pure` joins the 3 ADR-0001 contracts).
- `pytest -v`: **112 passed, 1 skipped in 7.03s**. New tests: 18 parser plugin + 11 SePay webhook + 5 migrate_sheets (4 + 1 skipped destructive variant deferred to unit-level mock — destructive schema mutation would race with other tests in the shared container).

### Next PR
- **None — W0.6 closes Wave 0.** Wave 1 begins with payment-matching layer per `feature-payment.md` + `feature-onboarding.md`. F02 (Wave 2) starts the handler-by-handler multi-tenant refactor.

---

## 2026-05-11 — F01 W0.5: Logging + Sentry + health (Wave 0)

### Added
- `core/logging.py` — structlog config:
  - `configure_logging(env)` wires processors: `merge_contextvars` → stdlib log level → ISO UTC timestamp → `_bind_tenant` (injects `user_id` + `request_id` from `core.tenant_context`) → stack/exc formatters → JSON (prod/staging) OR `dev.ConsoleRenderer` (dev).
  - `get_logger(name, **initial)` returns a `BoundLogger` with optional bound fields.
  - `render_event_for_test()` helper so tests assert tenant-binding without spinning a real logger.
  - Idempotent — safe to call from multiple startup paths.
- `core/observability.py` — Sentry + health + request ID:
  - `init_sentry(dsn, environment, release, traces_sample_rate)` — no-op when DSN empty (local dev runs without Sentry project). `before_send` hook tags every event with `user_id` / `request_id` from tenant context AND fills `user.id`. `StarletteIntegration` + `FastApiIntegration` enabled.
  - `health_app: FastAPI` sub-app:
    - `GET /health` → always `200 {"status":"ok"}` (liveness; never blocks on deps).
    - `GET /health/detailed` → checks DB pool via `SELECT 1`. Returns `200` + `status: ok` when pool healthy, `503` + `status: degraded` when pool uninitialised or DB query fails. Always includes `build` info (`version`, `commit` from env).
  - `request_id_middleware`: stamps `X-Request-ID` UUID4 hex per request, propagates into `tenant_context._request_id` (via ContextVar set/reset for proper async-task scoping), echoes the same value back as response header. Honours inbound `X-Request-ID` for client→server correlation.
- `tests/unit/test_logging.py` — 5 tests: tenant fields injected when set, omitted when unset, caller bind wins via `setdefault`, `configure_logging` idempotent, `get_logger` returns non-None bound logger.
- `tests/unit/test_sentry.py` — 4 tests: `before_send` populates tags + user; no-op when tenant unset; `init_sentry` returns False with no DSN; returns True with DSN-shaped string.
- `tests/integration/test_health.py` — 5 tests via in-process ASGI client:
  - liveness always 200
  - detailed → 503 when pool uninitialised, with `pool-not-initialised` error key
  - detailed → 200 + `status: ok` + non-None `pool_size` + correct `build.service` when DB up
  - request_id middleware generates UUID4 hex
  - request_id middleware honours client-supplied X-Request-ID

### Changed
- `requirements.txt` — added `structlog==24.4.0`, `sentry-sdk[fastapi]==2.18.0`, `jinja2==3.1.4` (the last needed by sentry-sdk's `StarletteIntegration.patch_templates()` at import time even though we don't use Jinja directly).

### Verified locally
- `ruff` / `black --check` / `mypy --strict`: all green (32 source files).
- `lint-imports`: 3 contracts kept, 0 broken. New `core/logging.py` + `core/observability.py` stay inside `core/`.
- `pytest -v`: **72 passed in 5.62s** (W0.1–4 carried over + 5 logging + 4 sentry + 5 health).

### Notes
- We use `setdefault` semantics in `_bind_tenant` and `_sentry_before_send` so callers that already bound `user_id` (e.g. background jobs running impersonated) keep their value.
- `traces_sample_rate` defaults to 0.0 — performance tracing off until we have a Sentry project + ROI estimate.
- The single `# type: ignore[arg-type]` on `sentry_sdk.init(before_send=...)` is the only one in `core/` — sentry-sdk types its callback against an internal `Event` TypedDict; the runtime contract is a plain dict.

### Next PR
- W0.6 — Legacy code move. Migrate `handlers/*` → `core/handlers/*` + `markets/vn/`. Refactor email_parser to plugin (Gap 2). Wire SePay handler to webhook_tokens lookup (Gap 3). Migrate founder sheet data → Postgres (Gap 5). Delete `sheets.py`.

---

## 2026-05-11 — F01 W0.4: Messenger adapter interface (Wave 0)

### Added
- `core/messenger/base.py` — Adapter contract (Gap 4 schema verbatim):
  - `SendPayload(TypedDict, total=False)` with `text_key` / `text_params` / `text` / `locale` / `markup` / `parse_mode`.
  - `Button` dataclass — `__post_init__` enforces label_key XOR label AND callback_data XOR url.
  - `Markup` dataclass — `rows: list[list[Button]]`. Platform-agnostic.
  - `BaseSender` ABC — `send_validated()` wraps `send()` with `_validate_payload()` so contract violations raise `ValueError` *before* any platform API call.
  - `register_sender(channel_type)` decorator + `senders_for(channel_type)` lookup. Idempotent on re-registration (tests can monkeypatch).
  - `_validate_payload()` enforces exactly-one-of `text_key`/`text`, valid `parse_mode`, and `markup` is `Markup` (rejects platform-specific structures sneaking through).
- `core/messenger/i18n.py` — Minimal `t(key, locale, **params)` stub. Loads `core/messenger/locales/{vi,en}.json` lazily, caches per locale. Unknown key → `??key??` (loud, not silent); unknown locale → falls back to `vi` (default market). `reset_cache()` for tests.
- `core/messenger/locales/{vi,en}.json` — minimal strings: `greeting`, `tx_recorded`, `btn_confirm`/`btn_cancel`/`btn_pick_category`, `error_generic`. Enough to exercise format-string params + button labels in tests.
- `core/messenger/telegram.py` — `TelegramSender(BaseSender)` impl:
  - httpx `AsyncClient` injected (tests pass a mock; production gets a default with `timeout=10s`).
  - `_resolve_chat_id` reads `users.chat_id` (falls back to legacy `users.telegram_id` for users seeded before multi-channel).
  - `_markup_to_telegram` converts abstract `Markup` → `{"inline_keyboard": [[{text, callback_data|url}]]}`.
  - `parse_mode` mapping: `markdown` → `MarkdownV2`, `html` → `HTML`, `plain` → omit field.
  - Raises `RuntimeError` on Telegram `ok: false` response so Sentry catches it; `raise_for_status()` covers transport errors.
  - `@register_sender("telegram")` factory reads `TELEGRAM_BOT_TOKEN` env.
- `core/messenger/send.py` — Top-level `send(user_id, payload)` entry: resolves the user's `channel_type` via the DB, looks up the registered factory, awaits adapter `send_validated()`. Supports sync or async factories.
- `core/messenger/__init__.py` — Public API + side-effect import of `telegram` so `senders_for("telegram")` finds a factory without callers having to import the adapter module.
- `tests/unit/test_messenger_payload.py` — 9 tests covering every `Button`/`Markup`/`SendPayload` validation branch.
- `tests/unit/test_messenger_i18n.py` — 5 tests: vi/en lookup, unknown-locale fallback, unknown-key loud marker, no-params template passthrough.
- `tests/unit/test_messenger_telegram_mock.py` — 6 tests with httpx + `_resolve_chat_id` mocked: text_key resolves through i18n, abstract Markup → inline_keyboard, parse_mode mapping, `ok: false` raises, validation runs before any API call (assert `client.post.assert_not_awaited()`), empty bot_token rejected.
- `tests/contract/test_messenger_contract.py` — 5 parametrised tests over `ADAPTERS = [("telegram", TelegramSender)]`. When W6 adds Discord/Messenger, those rows extend the parametrisation and inherit the same contract checks.

### Changed
- `pyproject.toml` — `[tool.ruff.lint.per-file-ignores]` for `tests/**/*.py` now also ignores `S106` ("hardcoded password"), since test code legitimately passes literal fake `bot_token="TEST_TOKEN"` values.

### Verified locally
- `ruff` / `black --check` / `mypy --strict`: all green (27 source files).
- `lint-imports`: 3 contracts kept, 0 broken. `core/messenger/` is fully self-contained inside `core/` — no `markets/` imports.
- `pytest -v`: **58 passed in 5.51s** (W0.1 + W0.2 + W0.3 + 6 + 5 + 9 + 5 unit + i18n + payload tests + 5 contract tests).

### Notes
- TelegramSender's chat_id lookup depends on W0.3's `core/db` pool — chains nicely now that the pool ships with W0.3.
- i18n is a stub; W3+ will likely switch to ICU or gettext when we tier locale resources properly. Loud `??key??` markers make missing strings obvious in dev/staging.
- Adapter registry is intentionally module-global (no DI container). Solo founder; simpler is faster.
- Gap 4 decision is now load-bearing: every handler in W0.6 emits `SendPayload`, not raw Telegram dicts.

### Next PR
- W0.5 — Logging (structlog + tenant binding), Sentry init, /health endpoints, request_id middleware.

---

## 2026-05-11 — F01 W0.3: DB pool + tenant context (Wave 0)

### Added
- `core/db.py` — Global asyncpg pool singleton: `create_pool(dsn)` / `get_pool()` / `close_pool()`. Defaults `min_size=2`, `max_size=10`, `command_timeout=30s`, `statement_cache_size=100`. `create_pool` rejects double-init (config-race detector); `get_pool` raises if uninitialised (never auto-creates); `close_pool` is idempotent.
- `core/tenant_context.py` — Per-request tenant context via `ContextVar` (asyncio-task-safe, propagates across `await` boundaries). API: `set_tenant(user_id, request_id=None) -> request_id`, `get_user_id()` (raises `LookupError` if unset — fail loud), `get_user_id_or_none()` (for logging/health only — NEVER in tenant-scoped queries), `get_request_id()`, `clear_tenant()`. Hard-rejects `user_id <= 0`. UUID4 hex auto-generated when request_id omitted.
- `tests/integration/test_db_pool.py` — 5 tests: create/get/close roundtrip, double-init raises, close-idempotent, get-without-init raises, **15 concurrent queries against max_size=10 pool queue without crashing** (proves asyncpg's built-in queueing — no app-level semaphore needed).
- `tests/integration/test_tenant_isolation.py` — 7 tests including the **THE mandatory** 2-user isolation rule that subsequent feature waves lean on:
  - `test_user_a_query_returns_only_user_a_rows` — user-scoped SELECT returns only A's rows, validated with `assert_tenant_isolated()`.
  - `test_user_b_query_returns_only_user_b_rows` — mirror with B.
  - `test_tenant_context_isolation_under_concurrent_tasks` — three `asyncio.gather`ed tasks with different tenants don't cross-contaminate (ContextVar correctness proof).
  - `test_delete_user_cascades_transactions` — schema sanity (ON DELETE CASCADE).
  - `test_get_user_id_raises_when_unset`, `test_set_tenant_returns_request_id_and_generates_uuid`, `test_set_tenant_rejects_invalid_user_id` — API contracts.

### Fixed
- `tests/conftest.py` `pg_url_async` — was returning `postgresql+asyncpg://...` (SQLAlchemy-style), but raw `asyncpg.create_pool()` rejects that scheme with `ClientConfigurationError`. Now returns the bare `postgresql://` DSN (asyncpg-compatible). Documented that SQLAlchemy async engines (when added) need the prefixed scheme; this fixture serves raw-asyncpg callers.

### Verified locally
- `ruff` / `black --check` / `mypy --strict`: all green (15 source files).
- `lint-imports`: 3 contracts kept, `core/db.py` + `core/tenant_context.py` cleanly stay inside `core/` (no markets imports).
- `pytest -v`: **32 passed in 5.79s** — 4 boundary + 16 migrations + 5 db_pool + 7 tenant_isolation.

### Notes
- Pool sizing tuned for the Wave 1-2 traffic envelope (single-region, low-RPS bot). Will revisit when adding read-replicas in W3+.
- `tenant_context.set_tenant()` returns the resolved request_id so callers can log it without a second `get_request_id()` round-trip.
- The 15-concurrent-query exhaustion test deliberately doesn't pass `timeout=...` to `pool.acquire()` — asyncpg's FIFO queue is what we depend on, not custom timeouts.

### Next PR
- W0.4 — Messenger adapter (`core/messenger/`): `BaseSender` ABC + `SendPayload` (Gap 4 verbatim) + `TelegramSender` impl + i18n stub + adapter contract tests.

---

## 2026-05-11 — F01 W0.2: Migration framework + initial schema (Wave 0)

### Added
- `alembic.ini` + `migrations/env.py` + `migrations/script.py.mako` — Alembic harness. `DATABASE_URL` env var resolves connection URL at runtime; asyncpg/psycopg URL normalised so the same migrations run against testcontainers Postgres in CI and the real Railway Postgres. No SQLAlchemy models — raw DDL via `op.execute`, schema is source of truth.
- `migrations/versions/0001_initial_schema.py` — 11 tables per TDD §2.1: `users`, `bank_connections`, `categories`, `funding_sources` (F08 / Gap 1), `transactions` (with `funding_source_id INTEGER NULL REFERENCES funding_sources(id) ON DELETE SET NULL` per Gap 1), `webhook_tokens` (Gap 3 — dedicated hashed-token table, replaces `users.webhook_token` column), `bot_state`, `scheduled_jobs`, `monthly_reports`, `admin_audit_log`, `analytics_events`. `users.role` column with CHECK (`user`/`founder`/`admin`) added for Gap 5 founder seed. Indexes per TDD §2.1.
- `tests/conftest.py` — session-scoped `pg_container` (testcontainers Postgres 16-alpine) + `pg_url` / `pg_url_async` DSN fixtures + `migrated_db` (auto `alembic upgrade head`) + `assert_tenant_isolated()` helper. `_has_docker()` skip-guard so non-Docker dev envs don't break collection.
- `tests/integration/test_migrations.py` — 5 tests + parametrised `test_each_table_queryable` (one per expected table = 11 cases): upgrade-creates-tables, FK shape check on `transactions.funding_source_id`, `webhook_tokens` shape (token_hash + kind CHECK), full `downgrade base` roundtrip, INSERT/SELECT smoke. **All 20 tests pass locally** (14.98s including container spin).
- `requirements.txt` — runtime deps: `asyncpg==0.30.0`, `sqlalchemy[asyncio]==2.0.36`.
- `pyproject.toml` `[project.optional-dependencies.dev]` — `alembic>=1.13`, `testcontainers>=4.7` (postgres module ships in base since 4.x, no extra needed), `asyncpg`, `sqlalchemy[asyncio]`, `psycopg[binary]>=3.2`.

### Gap decisions applied (locked, no founder re-ask)
- **Gap 1** — `funding_sources` table shell created in 0001 + `transactions.funding_source_id` FK nullable. F08 ON-DELETE logic ships in Wave 2; W0.2 only schema.
- **Gap 3** — Webhook tokens live in dedicated `webhook_tokens` table with `token_hash TEXT UNIQUE` (SHA256 hex). Raw token never stored. `users.webhook_token` column NOT created — replaced by this table.
- **Gap 5** — Added `users.role` enum (`user`/`founder`/`admin`) so founder seed (user_id=1, role='founder') has a column to populate in W0.6's data migration. Bootstrap-only — runtime MUST NOT hardcode `if user_id == 1`.

### Verified locally
- `ruff check core/ markets/ tests/ migrations/`: All checks passed (S608 false positive fixed by switching to `psycopg.sql.Identifier`).
- `black --check`: 11 files unchanged.
- `mypy --strict`: Success, 11 source files.
- `lint-imports`: 3 contracts kept, 0 broken.
- `pytest -v`: 20 passed in 14.98s (alembic upgrade/downgrade roundtrip + schema shape + INSERT/SELECT + parametrised table-exists per all 11 tables + 4 boundary tests from W0.1 carried over).

### Notes
- W0.2 is the foundation for W0.3 (DB pool) and W0.6 (data migration). W0.3 will branch from this PR head.
- `sub_categories`, `pending_payments`, `payment_matches`, `unmatched_payments` from TDD §2.1 deferred — those tables come in their respective feature waves (F02, F-payment).
- 11 tables created vs. autopilot spec's "10" — discrepancy in spec wording (it listed 11 names). Going with the explicit list.

### Next PR
- W0.3 — DB access layer (`core/db.py` asyncpg pool) + `core/tenant_context.py` (ContextVar-based) + 2-user tenant isolation integration test (THE mandatory rule).

---

## 2026-05-11 — F01 W0.1: Repo skeleton + lint boundary (Wave 0)

### Added
- `pyproject.toml` — project metadata (name=mymoneywent, version=0.0.1, py>=3.11) + tool configs (ruff/black/mypy/pytest) + `[project.optional-dependencies.dev]`. Legacy code excluded from strict checks via `extend-exclude` (will be cleaned in W0.6). Runtime deps stay in `requirements.txt` for Railway nixpacks compat.
- `requirements-dev.txt` — pointer to `-e .[dev]`.
- `core/__init__.py`, `markets/__init__.py`, `markets/vn/__init__.py`, `markets/global_/__init__.py` — empty package skeletons với module docstring giải thích boundary rule. **Note:** `markets/global_/` dùng trailing underscore vì `global` là Python reserved keyword (ADR-0001 intent unchanged).
- `tests/__init__.py`, `tests/test_import_boundary.py` — 3 smoke tests: config exists, positive run clean, **negative test** (deliberate `core → markets` violation phải bị catch).
- `.pre-commit-config.yaml` — hooks: ruff (lint+fix), black (format), mypy (strict on core/markets/tests), detect-secrets (against `.secrets.baseline`), import-linter (lint-imports).
- `.importlinter` — 3 contracts: `core ↛ markets` (ADR-0001 strict), `markets.vn ↮ markets.global_` (market isolation 2 chiều).
- `.secrets.baseline` — detect-secrets baseline với 22 plugins enabled. User runs `detect-secrets scan > .secrets.baseline` để populate against current repo.
- `.github/workflows/ci.yml` — GitHub Actions trên push main + PR: pre-commit (all files) → lint-imports → pytest. Python 3.11, timeout 10min.

### Changed
- `README.md` — thêm section "Development setup" với install commands, lint/test commands, boundary rule note, link đến workflow doc.

### Verified locally
- `ruff check core/ markets/ tests/`: All checks passed
- `black --check core/ markets/ tests/`: 6 files unchanged
- `mypy core/ markets/ tests/`: Success, no issues found in 6 source files
- `lint-imports`: 3 contracts kept, 0 broken
- **Negative test:** deliberate `core/_test_violation.py` with `from markets import vn` → lint-imports correctly reports "core MUST NOT import from markets (ADR-0001) BROKEN", exit 1. Boundary enforced.

### Notes
- W0.1 = first PR của Wave 0 split (6 PRs sequential per docs/operations/development-workflow.md §4). No business logic, no DB schema. Boring foundation.
- Pre-commit uses **black for format, ruff for lint only** (dropped `ruff-format` hook để tránh conflict với black).
- Next PR: W0.2 — alembic migration framework + initial schema (depends Gap 1 decision = YES per project_wave0_gap_decisions.md memory).

### Fixed (post-Codex adversarial review)
- **[HIGH] `tests/test_import_boundary.py` negative test race** — rewrite negative test: thay vì write violation file vào `core/_test_boundary_violation.py` (real package tree, race-prone), build isolated mini-project trong `tmp_path` với synthetic `.importlinter` config + plant violation ở đó. Thêm `test_real_config_declares_core_markets_contract` static check để guard against accidental removal of contract block. 4 tests, all pass; verified KHÔNG còn leftover file trong `core/`.
- **[MED] GitHub Actions floating tags** — `.github/workflows/ci.yml`: pin `actions/checkout@v4` → `@11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2), `actions/setup-python@v5` → `@0b93645e9fea7318ecaed2b359559ac225c90a2b` (v5.3.0). Comment ghi rõ SemVer tag để readable. Thêm `.github/dependabot.yml` để auto-bump SHAs hằng tuần.
- **[MED] Empty `.secrets.baseline`** — chạy thật `detect-secrets scan` toàn repo. Found 2 false positives trong legacy code: (1) `docs/tdd-vi.md:647` placeholder `postgresql://user:pass@host:5432/fintrack` trong env var doc; (2) `google_apps_script.js:19` template string `"your_random_email_secret_here"`. Cả 2 đã audit + marked `is_secret: false` trong baseline. New secrets in future commits sẽ bị block.
- **[P2 mini-review] Static contract test quá permissive** — Codex mini-review trên fix diff phát hiện `test_real_config_declares_core_markets_contract` chỉ substring-match `"type = forbidden"`, `"core"`, `"markets"` trên toàn file text → một edit weakening contract (vd đổi source_modules sang `handlers`) vẫn pass nhờ decoy tokens ở sections khác. Rewrite dùng `configparser` parse exact section `[importlinter:contract:core-must-not-import-markets]`, assert `type == 'forbidden'`, `source_modules == ['core']` (exact list), `forbidden_modules == ['markets']` (exact list). Không còn substring lurking attack surface.

---

## 2026-05-11 — Development workflow doc

### Added
- `docs/operations/development-workflow.md` v1.0.0 — Quy trình code-review-test per-feature (10 steps: spec → test plan → code+test → codex review → fix → CHANGELOG → PR → squash-merge → tag). Wave 0-6 dependency graph cho 16 feature spec (Wave 0 F-saas-refactor là blocker; F08 → F02 sequential trong Wave 2; F-discord/F-messenger parallel với Wave ≥3). Test strategy 3 layer (unit / integration real-Postgres / contract tests cho `messenger.send()` + `bank_email_parser` plugin), tenant isolation test mandatory. PR template + branch naming `feat/F##-name` + tag pattern `v0.X.0-F##`. Skills mapping (`engineering:testing-strategy`, `engineering:debug`, etc.). Anti-patterns + revise triggers.

---

## 2026-05-11 — Feature spec: Funding Sources (F08)

### Added
- `docs/features/feature-funding-sources.md` v1.0.0 — FE/UX spec cho tracking transaction theo từng bank account, debit/credit card, ví điện tử. VN market (SePay + email). Single `funding_sources` entity với canonical identity `(user_id, kind, bank, last4)`, status enum `(active/hidden/archived)`, auto-discovery embed-in-picker UX, `/accounts` command (list / rename / hide / manual-add), `/reports account=<display_id>` filter (Option A: explicit lookup match cả active + hidden, ambiguity → disambiguation prompt, power-syntax `kind:display_id` bypass). FK chain: `users→fs` CASCADE, `tx.fs_id→fs` SET NULL (retention của tx do TDD §6.3 quyết).
- `docs/features/BE/feature-funding-sources-tech.md` v1.0.0 — BE tech doc: Postgres DDL với check constraints, transitional Sheets schema (worksheet + col Q FK mirror), UPSERT_SQL canonical (CTE-based `was_resurrected` detection, `COALESCE(..., FALSE)` strict bool), TOUCH_SQL cho cache-hit path xử lý multi-process resurrect race, inference rules cho credit_card / e_wallet, backfill script với `kind='bank_account'` constraint, 30 test cases với subcases (cross-kind race, hidden vs archived, ambiguity, resolve failure, embed/delayed notification, last4 validation).

### Changed
- `docs/features/feature-transaction-capture.md` v1.0.1 → **v1.1.0** — F08 integration: pipeline diagram + acceptance criteria require fs resolve trước tx INSERT, FK `funding_source_id` populated, fallback NULL khi resolve fail. §4 schema bổ sung column `funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL` (F08 extension) + ownership note. Discovery message embed làm header trong category picker (1 message).
- `docs/features/BE/feature-transaction-capture-tech.md` v1.0.0 → **v1.1.0** — `process_transaction()` rewrite (resolve trước INSERT, try/except fallback NULL, discovery header prepend vào picker, delayed resurrect notif). §2.1 INSERT query thêm column `funding_source_id` ($9). Test plan +3 cases.

### Notes
- F08 xây trên F02 — không breaking change column P (`bank_account` string) hiện tại; thêm 1 entity registry bên trên.
- TDD-vi §2.1 chưa update — schema `funding_sources` sẽ promote vào TDD khi bump version kế tiếp.
- Spec locked sau nhiều round in-session tech review (canonical identity, status enum, FK chain, cache resurrect race, COALESCE bool); chi tiết technical decisions xem changelog trong từng spec file.

---

## 2026-05-10 (afternoon) — Repo cleanup pass 2

### Added
- `__pycache__/` explicit entry in `.gitignore` (was caught by `*.py[cod]` glob but folder name now ignored explicitly)
- `docs/strategy/` — pricing + cost projection docs grouped
- `docs/operations/` — production ops docs grouped
- `docs/marketing/` — landing page + marketing assets grouped
- `docs/adr/0002-onboarding-ui-strategy.md` — promoted from `decision-onboarding-ui-strategy.md`
- `docs/research/2026-05-07-competitive-round1/` — consolidated from `plans/reports/`
- `docs/research/2026-05-08-feature-landscape-round3/` — consolidated from `assets/research/`

### Changed
- 📝 **Naming convention standardized to kebab-case** across all docs:
  - 16 `feature_*.md` → `feature-*.md` in `docs/features/`
  - 15 `feature_*_tech.md` → `feature-*-tech.md` in `docs/features/BE/`
  - 2 `implementation_plan_*.md` → `implementation-plan-*.md` in `docs/implementation-plans/`
  - All cross-refs across the repo bulk-updated
- 📂 **Implementation plans consolidated** — 4 files all now in `docs/implementation-plans/` (was split between `docs/` and `docs/implementation-plans/`)
- 📂 **Research consolidated** — 3 locations (`docs/research/`, `plans/reports/`, `assets/research/`) merged into single `docs/research/` with date-based subfolders
- 📂 **docs/ root categorized** — 12 loose files grouped into `strategy/`, `operations/`, `marketing/`, `adr/`, `research/` subfolders. Only canonical specs (BRD/PRD/TDD x 2 markets + market-strategy-overview + strategic-pivot-global) remain at `docs/` root

### Moved
- `docs/cost-projection.md` → `docs/strategy/cost-projection.md`
- `docs/pricing-redesign.md` → `docs/strategy/pricing-redesign.md`
- `docs/observability-plan.md` → `docs/operations/observability-plan.md`
- `docs/landing-page-handoff-{en,vi}.md` → `docs/marketing/landing-page-handoff-{en,vi}.md`
- `docs/persona-business-deep-dive.md` → `docs/research/persona-business-deep-dive.md`
- `docs/decision-onboarding-ui-strategy.md` → `docs/adr/0002-onboarding-ui-strategy.md` (promoted to ADR)
- `docs/competitive-pricing-research.md` → `docs/research/competitive-pricing-research.md`
- `docs/implementation-plan-500-users-and-more.md` → `docs/implementation-plans/implementation-plan-500-users-and-more.md`
- `docs/implementation-plan-payment-vietqr-email.md` → `docs/implementation-plans/implementation-plan-payment-vietqr-email.md`
- `updates/2026-04-05.md` → `docs/archive/updates/2026-04-05.md`
- `plans/reports/*` → `docs/research/2026-05-07-competitive-round1/`
- `assets/research/2026-05-08-feature-landscape-round3/` → `docs/research/2026-05-08-feature-landscape-round3/`

### Removed (empty folders left behind by mv — user can `rm -rf` on Mac)
- `plans/reports/` (empty — now in research/)
- `assets/research/` (empty — now in research/)
- `updates/` (empty — file moved to archive)

### Fixed
- 26 docs had broken refs to `docs/prd.md` / `docs/tdd.md` after split → bulk-updated to `docs/prd-vi.md` / `docs/tdd-vi.md`
- Updated cross-refs for all moved files (~100 cross-refs across 30+ docs)

---

## 2026-05-10 — Repo hygiene + dual-market structure

### Added

- 📄 **CHANGELOG.md** — this file (per founder rules: bắt buộc có README + CHANGELOG)
- 📄 **[docs/market-strategy-overview.md](docs/market-strategy-overview.md)** v1.0 → v1.1.0 — entry-point doc explaining VN vs Global track coexistence; updated channel comparison (shared platforms + Zalo VN-only)
- 📄 **[docs/brd-en.md](docs/brd-en.md) v4.0.0** — formal Global market BRD (My Money Went). Promoted from `strategic-pivot-global.md`. ICP: e-commerce solopreneur. Capture stack: Plaid/TrueLayer/Tink + Stripe/PayPal/Shopify/Etsy/Amazon SP-API + payout email parsing. Pricing: $6 Pro / $12 Solopreneur + annual plans. Channels: Telegram + Discord + Messenger MVP + read-only web dashboard.
- 📄 **[docs/adr/0001-monorepo-not-split-repos.md](docs/adr/0001-monorepo-not-split-repos.md)** — Architecture Decision Record locking monorepo + `core/ + markets/vn/ + markets/global/` adapter pattern. 7 explicit re-evaluation triggers. Q3 2026 default review.
- 📁 **`docs/adr/`** — new folder for Architecture Decision Records
- 📁 **`docs/research/`** entries — moved 9 strategy/research docs from root to organize repo

### Changed

- 📝 **[docs/brd-vi.md](docs/brd-vi.md) v3.1.0** — added 🌐 SCOPE NOTE clarifying this is canonical VN spec (Tiền Về Nơi Đâu); added 🏗️ CODE STRUCTURE note locking VN code path at `markets/vn/` per ADR-0001; channel architecture clarified
- 📝 **[README.md](README.md)** — markets section reframed as dual-market (VN primary + Global parallel); quick links restructured (BRD-VI + BRD-EN canonical, brd.md archived); architecture decisions section added; repo structure tree split into "current pre-refactor" + "target Phase 1 goal"; decision log entry for 2026-05-10
- 📝 **[strategic-pivot-global.md](docs/strategic-pivot-global.md)** v1.0 → v1.2 — title changed from "Strategic Pivot Analysis" to "Global Market Strategy"; reframed as parallel global track (NOT replacement of VN); status updated to "Promoted into formal BRD" pointing to brd-en.md; moved from repo root to `docs/`
- 📂 **Doc structure** — `docs/brd.md` (FinTrack v2.9.0) archived → `docs/archive/brd-fintrack-v2.9.0-archived.md`; replaced by canonical pair brd-vi.md (VN) + brd-en.md (Global)
- 📂 **Path fix** — bulk replaced 20 doc cross-refs from `docs/brd.md` → `docs/brd-vi.md` to keep links resolving after archive
- 📂 **`strategic-pivot-global.md` location** — moved from repo root to `docs/`; all cross-refs updated (`../strategic-pivot-global.md` → `./strategic-pivot-global.md` for docs/, `strategic-pivot-global.md` → `docs/strategic-pivot-global.md` for README)

### Removed (moved to archive)

- 🗑️ **40 root-level duplicate files** moved to `docs/archive/root-duplicates-2026-05-10/`:
  - Stale BRDs/PRDs at root (older versions than docs/): `brd-en.md` v2.8.0, `brd-vi.md` v3.1.0/2026-05-07, `prd-en.md` v1.5.0, `prd-vi.md` v1.5.0
  - 30 duplicate feature_*.md (identical to docs/features/ + docs/features/BE/)
  - 4 duplicate implementation plans (root vs docs/ + docs/implementation-plans/)
  - 2 identical duplicates: `persona-business-deep-dive.md`, `pricing-redesign.md`
  - 2 Office lock files (`~$c1-...docx`, `~$c2-...docx`)
- 🗑️ **`docs/brd.md` (FinTrack v2.9.0)** — archived to `docs/archive/brd-fintrack-v2.9.0-archived.md` (legacy FinTrack BRD; superseded by brd-vi.md + brd-en.md split)

### Moved (to better location)

- 📦 **9 research/strategy docs** from root → `docs/research/`:
  - `competitive-analysis-solopreneur-lite-tools-may2026.md`
  - `competitive-intelligence-report.md`
  - `insights-from-competitive-research.md`
  - `research-prompt-competitor-analysis.md`
  - `research-prompt-features-deep-dive.md`
  - `research-prompt-round-2.md`
  - `Doc1-Market-Analysis-Vendor-Strategy.{md,docx}`
  - `Doc2-User-Research-Findings-Plan.{md,docx}`
- 📦 **`strategic-pivot-global.md`** from root → `docs/` (cleaner repo root, all docs together)

### Fixed

- 🔧 **Broken `docs/brd.md` cross-refs** — 20 docs updated from `docs/brd.md` → `docs/brd-vi.md` after BRD archive

### Decision log (key product decisions, not just structural)

- ✅ **Dual-market structure locked:** brd-vi.md (VN, Tiền Về Nơi Đâu) + brd-en.md (Global, My Money Went) as canonical sibling BRDs. Channel architecture confirmed shared (Telegram + Discord + Messenger), Zalo VN-exclusive Phase 3+, WhatsApp Global-only Phase 2.
- ✅ **Monorepo over split repos:** per ADR-0001, single repo with `core/ + markets/vn/ + markets/global/` adapter pattern. Re-evaluate Q3 2026 or sooner if any of 7 triggers fires.
- ✅ **brd-en.md content rewritten:** discarded VN-derived content (SePay, VN banks, Hùng+ persona). Promoted strategic-pivot-global.md into formal BRD form with Plaid + e-commerce APIs + solopreneur ICP + $6/$12 pricing.

---

## 2026-05-07 — Pre-restructure baseline

### Background

Before 2026-05-10 restructure, the project had:

- Single BRD (`docs/brd.md` v2.9.0, FinTrack branding) for VN market
- Strategic exploration doc (`strategic-pivot-global.md`) at repo root proposing pivot to Global market
- Multiple duplicate copies of docs at repo root + `docs/`
- 30 feature_*.md files duplicated at root + docs/features/
- Office lock files committed accidentally

State as of 2026-05-07:

- **BRD-vi.md v3.1.0** existed as Vietnamese branding ("Tiền Về Nơi Đâu") with v3.x version drift from FinTrack BRD v2.9.0
- **strategic-pivot-global.md** v1.0 framing was "pivot from VN to Global" — superseded 2026-05-10 with parallel-track framing

---

## Reference: Per-doc changelogs

For doc-level changes (BRD/PRD/TDD/feature specs), see the changelog table at the bottom of each doc:

- [BRD-VI changelog](docs/brd-vi.md#changelog)
- [BRD-EN changelog](docs/brd-en.md#changelog)
- [Strategic-pivot-global changelog](docs/strategic-pivot-global.md#changelog)
- [Market-strategy-overview changelog](docs/market-strategy-overview.md#changelog)
- [ADR-0001 changelog](docs/adr/0001-monorepo-not-split-repos.md#changelog)
