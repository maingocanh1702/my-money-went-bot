# Execution prompt — Wave 0 W0.2 → W0.6 (Claude Code)

> Paste the block between `===PROMPT START===` and `===PROMPT END===` into
> Claude Code (preferably from the `main` branch of the repo, with W0.1
> already merged). The executor has no prior conversation context — the
> prompt is self-contained.

> **Estimated effort:** 7-10 days of focused work (Claude Code may complete
> faster). 5 PRs sequential.
> **Mandatory pause points:** after each W0.x PR, executor STOPS and waits
> for user to run `/codex:review` and explicitly confirm before continuing.

---

```
===PROMPT START===

# Task: Execute Wave 0 PRs W0.2 → W0.6 sequentially

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo
founder's multi-tenant personal finance bot. You have no prior
conversation context. This prompt is self-contained.

## Pre-flight checks (run first, STOP if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                       # must be clean
git branch --show-current        # must be: main
git log --oneline -3             # latest must mention "F01: W0.1 repo skeleton"
ls pyproject.toml core/ markets/vn/ markets/global_/ .importlinter \
   .pre-commit-config.yaml .github/workflows/ci.yml 2>&1
```

If any check fails, STOP and report. Do not proceed.

Install dev environment (one-time setup):
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
pre-commit install
```

## Project context (1 paragraph)

MyMoneyWent: multi-tenant personal finance bot, two parallel markets — VN
("Tiền Về Nơi Đâu", SePay webhook + bank email parsing) and Global ("My
Money Went", Plaid/TrueLayer + e-commerce APIs). Solo founder.
Architecture per ADR-0001: monorepo with `core/ + markets/vn/ +
markets/global_/` adapter pattern. HARD invariant: `core/` MUST NOT import
from `markets/` (enforced by `import-linter`).

W0.1 (just merged) laid the foundation: pyproject.toml, tooling configs,
empty package skeletons, import-linter boundary, CI workflow. W0.2-W0.6
build on it.

## Reference docs (read BEFORE starting each PR — not all upfront)

- `docs/operations/development-workflow.md` — workflow §2 (10-step per PR),
  §4 (Wave 0 split + acceptance criteria per W0.x), §6 (anti-patterns)
- `docs/features/feature-saas-refactor.md` + `docs/features/BE/feature-
  saas-refactor-tech.md` — F-saas-refactor spec
- `docs/adr/0001-monorepo-not-split-repos.md` — boundary invariant
- `docs/tdd-vi.md` §2.1 — initial schema DDL for W0.2

## Locked gap decisions (DO NOT re-ask user)

These were decided 2026-05-11 in planning session. Apply verbatim.

### Gap 1 — `transactions.funding_source_id` from W0.2: YES
- W0.2 migration 0001 creates `funding_sources` table shell + adds
  `transactions.funding_source_id INTEGER NULL REFERENCES
  funding_sources(id) ON DELETE SET NULL`.
- F08 logic/service ships Wave 2. W0.2 only schema.

### Gap 2 — Email parser plugin: ABC + registry decorator
```python
class BankEmailParser(ABC):
    bank: str
    @abstractmethod
    def can_parse(self, email: InboundEmail) -> bool: ...
    @abstractmethod
    def parse(self, email: InboundEmail) -> CanonicalTx: ...

PARSERS: dict[str, type[BankEmailParser]] = {}

def register_parser(bank: str):
    def wrapper(cls):
        PARSERS[bank] = cls
        return cls
    return wrapper
```
HARD invariants:
- Parser output MUST be `CanonicalTx`
- Parser MUST NOT write DB
- Parser MUST NOT call messenger
- Parser only parses/normalizes

### Gap 3 — Webhook tokens: dedicated `webhook_tokens` table (hashed)
```sql
CREATE TABLE webhook_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('sepay', 'email_inbound')),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE(user_id, kind)
);
```
Store hash (SHA256 or similar), compare hash. Never store raw token.

### Gap 4 — `messenger.send()` payload schema
```python
class SendPayload(TypedDict, total=False):
    text_key: str           # i18n key (preferred for product messages)
    text_params: dict[str, Any]
    text: str               # raw text (escape hatch: debug/admin/temp only)
    locale: str
    markup: Markup | None
    parse_mode: Literal["markdown", "html", "plain"]

@dataclass
class Button:
    label_key: str | None = None
    label: str | None = None
    callback_data: str | None = None
    url: str | None = None

@dataclass
class Markup:
    rows: list[list[Button]]
```
Rules:
- Exactly ONE of `text_key` or `text` per payload
- Adapter dispatches abstract `Markup` to platform-specific (Telegram
  inline keyboard, Discord buttons, Messenger quick replies)
- Core handlers emit abstract payload; channel adapter owns platform formatting

### Gap 5 — Founder seed (bootstrap only, not runtime assumption)
- Migration script seeds `INSERT INTO users (id, role) VALUES (1, 'founder')`
- DOCUMENT explicitly: `user_id=1 = founder` is bootstrap-only. Runtime
  MUST NOT hardcode `if user_id == 1`.
- Sheet → PG mapping is 1-1 (no business meaning transform).
- Migration order: users → categories/settings/connections →
  funding_sources → transactions → audit/log tables.
- Verification: row counts match, sample tx amount/date/category match,
  no orphan user_id, tenant isolation smoke after migration.

## Workflow rules (per docs/operations/development-workflow.md §2)

For EACH W0.x PR, follow 10-step strictly:

1. Read spec (F-saas-refactor FE + BE tech doc, relevant sections)
2. Draft test plan (smoke tests + tenant isolation if DB involved)
3. Plan 10-line: files, migration, tests, integration points, risks
4. Create branch `feat/F01-w0X-short-name`
5. Code + write tests SAME session
6. Run local verification: ruff + black + mypy + lint-imports + pytest
7. Commit atomically (multiple commits per PR per §2.4)
8. STOP — request user to run `/codex:review --scope branch --base main`
9. If Codex finds issues: fix → commit → request mini-review `--base HEAD~N`
   (where N = number of fix commits). Loop until clean.
10. After 2 consecutive clean Codex rounds: instruct user to squash-merge,
    then proceed to next W0.x.

### Branch naming
- `feat/F01-w02-migrations`
- `feat/F01-w03-db-tenant`
- `feat/F01-w04-messenger`
- `feat/F01-w05-observability`
- `feat/F01-w06-legacy-move`

### Commit message pattern
- `chore(W0.X): <what>` for setup/config
- `feat(W0.X): <what>` for new functional code
- `test(W0.X): <what>` for tests
- `docs(W0.X): <what>` for docs/README/CHANGELOG
- `fix(W0.X): <what>` for Codex-finding fixes

### Squash-merge commit message
`F01: W0.X <feature name>` — e.g. `F01: W0.2 migration framework + initial schema`

## Anti-patterns (do NOT do)

Per workflow doc §6:
- Code before reading spec — STOP and read spec first
- Mock Postgres in integration tests — use testcontainers always
- One monster commit — split atomic
- Skip tenant isolation test when DB is involved — MANDATORY
- Bump spec version every iteration in-session — only bump if external consumer
- Merge without CHANGELOG entry — required
- Code into legacy structure — only into core/ + markets/{vn,global_}/
- `if market == "vn"` in core/ — banned (use adapter pattern)
- `core/` importing from `markets/` — banned (import-linter enforces)
- More than 2 active branches as solo dev — finish current before next

---

# W0.2 — Migration framework + initial schema

## Scope

Set up Alembic migrations + initial schema 0001 with 10 tables. Set up
testcontainers-python in `tests/conftest.py` with tenant isolation
helper. No DB access layer yet (that's W0.3) — just the schema and the
ability to migrate it.

## Files to create

- `alembic.ini` — Alembic config
- `migrations/env.py` — async SQLAlchemy env for Alembic
- `migrations/script.py.mako` — template
- `migrations/versions/0001_initial_schema.py` — 10 tables (see schema below)
- `tests/conftest.py` — pytest fixtures: testcontainers Postgres, alembic
  upgrade/downgrade helper, tenant isolation assertion helper
- `tests/integration/__init__.py`
- `tests/integration/test_migrations.py` — alembic upgrade head + downgrade
  base + smoke INSERT/SELECT
- Add to `requirements.txt` (runtime): `asyncpg`, `sqlalchemy[asyncio]`
- Add to `pyproject.toml` `[project.optional-dependencies.dev]`:
  `testcontainers[postgresql]`, `alembic`

## Schema (migration 0001) — 10 tables

Read `docs/tdd-vi.md` §2.1 for full DDL. Tables:

1. `users` — id PK, channel_type, channel_user_id, locale, role, created_at, locked_at
2. `categories` — id, user_id FK, name, month_key, parent_id, active, ...
3. `funding_sources` (Gap 1) — id, user_id FK, kind, bank, last4, display_id,
   nickname, first_seen_at, last_tx_at, status, archived_at;
   UNIQUE(user_id, kind, bank, last4)
4. `transactions` — id, user_id FK, ts, amount, currency, description,
   bank_account, category_id FK,
   `funding_source_id INTEGER NULL REFERENCES funding_sources(id) ON DELETE SET NULL`
5. `webhook_tokens` (Gap 3) — id, user_id FK, kind enum check, token_hash UNIQUE,
   created_at, revoked_at; UNIQUE(user_id, kind)
6. `bot_state` — user_id FK, key, value JSONB, updated_at; PK(user_id, key)
7. `bank_connections` — id, user_id FK, bank, kind, status, ...
8. `scheduled_jobs` — id, user_id FK, kind, schedule, next_run_at, ...
9. `monthly_reports` — id, user_id FK, month_key, generated_at, payload JSONB
10. `analytics_events` — id, user_id FK NULL, event, properties JSONB, ts
11. `admin_audit_log` — id, admin_user_id FK, action, target, payload JSONB, ts

(If TDD §2.1 disagrees, follow TDD — it's source of truth.)

## Acceptance criteria

- `alembic upgrade head` creates all tables; `alembic downgrade base` drops them cleanly
- testcontainers spins Postgres 16 in <30s
- 1 integration test passes: INSERT a row, query, assert
- `funding_sources` table exists; `transactions.funding_source_id` FK present
- `webhook_tokens` table exists with hashed token + kind check constraint
- tenant isolation helper available for downstream W0.3+ tests
- `pre-commit run --all-files` passes
- `lint-imports` passes (3 contracts kept)
- CHANGELOG entry added

## STOP point after W0.2

Commit all atomic chunks, push branch, then output:

```
W0.2 complete. Branch feat/F01-w02-migrations pushed.
Files: <count>. Commits: <count>.
Local verification:
- ruff: <result>
- black: <result>
- mypy: <result>
- lint-imports: <result>
- pytest: <count> passed
- alembic upgrade head + downgrade base: <result>

Please run:
  /codex:review --scope branch --base main

Then paste output back. I will wait.
```

DO NOT proceed to W0.3 without user confirmation that W0.2 is merged.

---

# W0.3 — DB access layer + tenant_context

## Scope (depends on W0.2 merged)

asyncpg connection pool factory + tenant context propagation via
`contextvars`. Cross-tenant assertion helper.

## Files to create

- `core/db.py` — `create_pool()`, `get_pool()`, `close_pool()` functions.
  asyncpg pool with min=2, max=10, command_timeout=30.
- `core/tenant_context.py` — `ContextVar` for `user_id` + `request_id`;
  `set_tenant(user_id, request_id)`, `get_user_id()`, `get_request_id()`,
  `clear_tenant()`. Optional: helper to enforce "every query has user_id".
- `tests/integration/test_db_pool.py` — pool creates, query works, pool
  closes cleanly.
- `tests/integration/test_tenant_isolation.py` — 2 users (id=1, id=2),
  insert tx for each, query user 1 → only sees own data, query user 2 →
  only sees own.

## Acceptance criteria

- Pool init/close happy path
- 2-user tenant isolation test passes (MANDATORY — this is THE rule)
- Pool exhaustion under 15 concurrent queries: queue, don't crash
- `WHERE user_id = $1` discipline visible in test code
- mypy --strict clean on core/db.py + core/tenant_context.py

## STOP point — same pattern as W0.2

Output report + request `/codex:review --scope branch --base main`. Wait.

---

# W0.4 — Messenger adapter interface

## Scope (depends on W0.3 merged)

Abstract messenger interface so handlers don't know about Telegram-specific
APIs. Only Telegram adapter implemented in W0.4 (Discord/Messenger ship
Wave 6 per development-workflow.md).

## Files to create

- `core/messenger/__init__.py` — public `send(user_id, payload)` entry
- `core/messenger/base.py` — `BaseSender` ABC + `SendPayload` TypedDict +
  `Button`/`Markup` dataclasses (use Gap 4 schema verbatim)
- `core/messenger/telegram.py` — `TelegramSender(BaseSender)` impl. Wraps
  Telegram Bot API send (httpx). Handles `text_key` → i18n lookup → text.
  Maps abstract `Markup` to Telegram InlineKeyboardMarkup.
- `core/messenger/i18n.py` — minimal `t(key, locale, **params)` stub.
  Loads JSON files from `core/messenger/locales/{vi,en}.json`. (Full i18n
  comes in F-i18n Wave 1; W0.4 just needs working stub.)
- `core/messenger/locales/vi.json` + `en.json` — minimal strings for tests
- `tests/unit/test_messenger_payload.py` — payload schema validation
- `tests/unit/test_messenger_telegram_mock.py` — mock httpx, verify
  TelegramSender calls right API with right payload structure
- `tests/contract/test_messenger_contract.py` — parametrized over adapter
  (only TelegramSender exists now; Discord/Messenger ship later).

## Acceptance criteria

- Payload schema accepts text_key + text_params OR text (exactly one)
- TelegramSender mock test: send_text payload → httpx POST with
  parse_mode + reply_markup correctly mapped
- i18n: `t('welcome', locale='vi')` returns Vietnamese string
- Contract test passes for TelegramSender
- mypy --strict clean

## STOP point — same pattern

---

# W0.5 — Logging + health + Sentry

## Scope (depends on W0.4 merged)

Production-ready instrumentation. structlog with context binding, Sentry
init, `/health` endpoints, request ID middleware.

## Files to create

- `core/logging.py` — structlog config. Bind `user_id` + `request_id` from
  tenant_context contextvars. JSON output in prod, console in dev.
- `core/observability.py` — `init_sentry(dsn)`, `health_app` FastAPI
  sub-app with `/health` (simple OK) + `/health/detailed` (pool state, DB
  ping, build info), `request_id_middleware` to generate UUID per request.
- Add to `requirements.txt`: `structlog`, `sentry-sdk[fastapi]`
- `tests/unit/test_logging.py` — log entry has user_id field from context
- `tests/unit/test_sentry.py` — sample exception captured with user_id tag
- `tests/integration/test_health.py` — /health returns 200; /health/detailed
  returns pool state when DB up, degraded when DB down

## Acceptance criteria

- Structured log line includes `user_id` + `request_id` when tenant
  context is set
- Sentry receives exception with `user_id` tag (mock Sentry client)
- `/health` always returns 200
- `/health/detailed` returns 503 when DB unreachable
- Request ID middleware: every request gets unique UUID, propagated to logs
- mypy --strict clean

## STOP point — same pattern

---

# W0.6 — Legacy code move + data migration

## Scope (depends on W0.5 merged) — BIGGEST PR

Eliminate legacy single-tenant code. Move `handlers/*` → `core/handlers/*`
+ market-specific phần → `markets/vn/`. Refactor `email_parser.py` into
plugin pattern (Gap 2). Wire SePay handler to token-based user lookup
(Gap 3). Migrate founder's Google Sheets data to PostgreSQL (Gap 5).

## Files to create/modify

### Move
- `handlers/transaction.py` → `core/handlers/transaction.py` (multi-tenant)
- `handlers/manage.py` → `core/handlers/manage.py` (multi-tenant)
- `handlers/reports.py` → `core/handlers/reports.py`
- `handlers/allocation.py` → `core/handlers/allocation.py`
- `handlers/sepay.py` → `markets/vn/capture/sepay_webhook.py` (uses
  webhook_tokens lookup)
- `handlers/email_parser.py` → split into plugin pattern under
  `markets/vn/email_parsers/`:
  - `markets/vn/email_parsers/__init__.py` — register parsers
  - `markets/vn/email_parsers/base.py` — `BankEmailParser` ABC + `PARSERS`
    registry + `register_parser` decorator (Gap 2)
  - `markets/vn/email_parsers/{tcb,cake,acb,sacombank,bidv,mb}.py` —
    1 parser per bank. Each registers via `@register_parser('TCB')` etc.
- `telegram_api.py` → merge into `core/messenger/telegram.py` (Telegram
  Bot API wrapping)
- `sheets.py` → DELETE (Postgres takes over)
- `main.py` → refactor entrypoint to use new structure

### New
- `scripts/migrate_sheets.py` — Gap 5: one-time migrate founder's
  Google Sheets data to Postgres. Migration order strict:
  users → categories → funding_sources (parsed from col P) → transactions
  → audit. Includes verification: row count match, sample fields match,
  no orphan user_id.
- `core/handlers/__init__.py`
- `markets/vn/capture/__init__.py`
- `markets/vn/capture/sepay_webhook.py` — SePay handler. Looks up user by
  webhook token hash via webhook_tokens table.

### Tests
- `tests/integration/test_email_parser_plugins.py` — each registered
  parser passes contract: can_parse + parse → CanonicalTx
- `tests/integration/test_sepay_webhook.py` — token-based user lookup,
  webhook payload → tx in DB
- `tests/integration/test_e2e_smoke.py` — happy path: webhook → tx
  inserted with user_id scoped → reports query returns it
- `tests/scripts/test_migrate_sheets.py` — mock sheets, verify migration
  + verification logic

## Acceptance criteria — MOST STRINGENT

- `sheets.py` deleted from repo
- `handlers/` directory empty or removed
- All legacy code paths migrated to new structure
- import-linter still passes (3 contracts)
- email parser plugin invariants enforced: no DB write, no messenger call
  from parser code (verify by code search)
- Token lookup uses hash compare (not raw token); webhook returns 200
  silently when token invalid
- founder data migrated, row counts match, sample fields verified
- Documentation: `user_id=1 = founder` bootstrap note in
  `scripts/migrate_sheets.py` docstring AND in README
- ALL anti-patterns checked: no `if market == "vn"` in core/, no `core/`
  importing markets/, no mocks for DB in integration tests
- mypy --strict clean on entire `core/` + `markets/`
- CHANGELOG entry comprehensive

## STOP point — final Wave 0 review

After W0.6 merges, output:

```
WAVE 0 COMPLETE.

All 6 PRs (W0.1-W0.6) merged into main.
Repo state: multi-tenant foundation ready for Wave 1 features.

Next: Wave 1 features (per development-workflow.md §4) — F-onboarding,
F-admin-tools, F-i18n, F-settings. These can run in parallel.

Founder, please decide which Wave 1 feature to start first.
```

---

## Global rules for the executor (read again before each PR)

1. **READ SPEC FIRST.** Open `docs/features/feature-saas-refactor.md` and
   `docs/features/BE/feature-saas-refactor-tech.md` and relevant TDD/PRD
   sections BEFORE writing code. Confirm scope matches.

2. **NEVER skip the 10-step workflow.** Workflow exists to prevent the
   classes of bugs Codex catches. Skipping = wasted Codex cycles.

3. **NEVER mutate real `core/` for tests.** Use tmp_path. (W0.1 lesson.)

4. **NEVER commit secrets.** detect-secrets blocks new secrets.

5. **NEVER pin Actions to floating tags.** Pin to SHA + Dependabot.

6. **NEVER skip tenant isolation test** when DB is involved.

7. **NEVER proceed to next W0.x without explicit user OK** after merge.

8. **If unsure about scope/design**, STOP and ask user. Don't guess on
   architectural decisions — Wave 0 sets foundation for everything.

9. **Batch tool calls** when reading multiple files. Parallel Read.

10. **Use TaskList** to track sub-steps within a PR. Mark `in_progress`
    when starting, `completed` when done.

11. **Memory hygiene:** if you make a non-obvious decision during
    execution (e.g. picked one library over another), save a brief note
    in your memory under `project_wave0_<topic>.md` so future sessions
    have context.

12. **Verify before claiming done.** After each "tests pass" claim,
    actually re-run the test and paste output. Trust but verify yourself.

13. **Defensive against agent flakiness:** if a tool errors twice in a
    row on the same operation, STOP and report. Don't retry blindly.

Begin with W0.2.

===PROMPT END===
```

---

## How to use

1. After merging W0.1 into main, ensure clean state: `git status` clean,
   `git checkout main`, `git pull` (if remote exists).
2. Open Claude Code in `/Users/maingocanh/Projects/MyMoneyWent`.
3. Paste everything between `===PROMPT START===` and `===PROMPT END===`.
4. Claude Code will execute W0.2 first, stop at the STOP point, request
   `/codex:review`. You run review, paste output. If clean, tell Claude
   Code "merged W0.2, proceed to W0.3". Repeat through W0.6.

## Per-PR rhythm (what to expect)

For each W0.x:

| Step | Who | What |
|---|---|---|
| 1-7 | Claude Code | Read spec, plan, code, test, commit atomic, local verify |
| 8 | Claude Code → user | Output STOP report, request Codex review |
| 9 | User | Run `/codex:review --scope branch --base main`, paste output |
| 10 | Claude Code | If findings: fix + mini-review request. If clean: instruct user to squash-merge. |
| 11 | User | `git checkout main && git merge --squash feat/F01-w0X-* && git commit -m "F01: W0.X ..."` |
| 12 | User → Claude Code | Confirm merge done. Claude Code proceeds to next W0.x. |

## Budget warning

Wave 0 W0.2-W0.6 is substantial work. Expect Claude Code to consume
significant tokens. Consider running each W0.x in a fresh Claude Code
session (paste prompt fresh, point to specific W0.x section) to avoid
context bloat. If running all 5 in one session, monitor context window.

## Recovery if Claude Code deviates

If Claude Code goes off-script (skips a step, makes a wrong assumption,
introduces a new pattern not in the prompt): interrupt, point to the
specific rule in the prompt, ask to redo. Foundation PRs MUST be tight.
