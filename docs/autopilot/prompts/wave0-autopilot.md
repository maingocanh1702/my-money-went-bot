# Task: AUTOPILOT execute Wave 0 W0.2 → W0.6 as chained branches

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's multi-tenant personal finance bot. You have no prior conversation context. This prompt is self-contained.

**Mode:** AUTOPILOT — execute all 5 PRs sequentially without founder intervention. Each PR lands on its own branch chained from the previous. NO auto-merge. NO Codex review during run (founder runs Codex in batch after). Pause ONLY on circuit-breaker conditions (defined below).

## Pre-flight checks (run first, HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                          # must be clean
git branch --show-current           # must be: main
git log --oneline -3                # latest must mention "F01: W0.1 repo skeleton"
ls pyproject.toml core/ markets/vn/ markets/global_/ .importlinter \
   .pre-commit-config.yaml .github/workflows/ci.yml 2>&1
```

If any check fails, HALT and report. Do not proceed.

Install dev environment (one-time):
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
pre-commit install
```

Verify tooling works:
```bash
ruff check core/ markets/ tests/
black --check core/ markets/ tests/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
```

All 5 must pass. If any fails, HALT and report — env setup broken.

## Project context (1 paragraph)

MyMoneyWent: multi-tenant personal finance bot, two parallel markets — VN ("Tiền Về Nơi Đâu", SePay webhook + bank email parsing) and Global ("My Money Went", Plaid/TrueLayer + e-commerce APIs). Solo founder. Architecture per ADR-0001: monorepo with `core/ + markets/vn/ + markets/global_/` adapter pattern. HARD invariant: `core/` MUST NOT import from `markets/` (enforced by `import-linter`).

W0.1 (already merged into main) laid the foundation: pyproject.toml, tooling configs, empty package skeletons, import-linter boundary, CI workflow. W0.2-W0.6 build on it.

## Reference docs (read RELEVANT sections before each PR — not all upfront)

- `docs/operations/development-workflow.md` — §2 (10-step), §4 (Wave 0 W0.x scope + acceptance), §6 (anti-patterns)
- `docs/features/feature-saas-refactor.md` + `docs/features/BE/feature-saas-refactor-tech.md` — F-saas-refactor spec
- `docs/adr/0001-monorepo-not-split-repos.md` — boundary invariant
- `docs/tdd-vi.md` §2.1 — initial schema DDL for W0.2

## Locked gap decisions (DO NOT re-ask)

### Gap 1 — `transactions.funding_source_id` from W0.2: YES
- W0.2 migration 0001 creates `funding_sources` table shell + adds `transactions.funding_source_id INTEGER NULL REFERENCES funding_sources(id) ON DELETE SET NULL`
- F08 logic ships Wave 2. W0.2 only schema.

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
Invariants (HARD): parser output MUST be `CanonicalTx`; parser MUST NOT write DB; parser MUST NOT call messenger; parser only parses/normalizes.

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
Store hash (SHA256), compare hash. Never store raw token.

### Gap 4 — `messenger.send()` payload schema
```python
class SendPayload(TypedDict, total=False):
    text_key: str           # i18n key (preferred)
    text_params: dict[str, Any]
    text: str               # raw text (escape hatch only)
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
Rules: exactly ONE of `text_key` or `text`. Adapter maps abstract Markup to platform-specific (Telegram InlineKeyboard, Discord buttons, Messenger quick replies). Core handlers emit abstract; adapter owns platform format.

### Gap 5 — Founder seed (bootstrap only)
- `INSERT INTO users (id, role) VALUES (1, 'founder')`
- Runtime MUST NOT hardcode `if user_id == 1`. Document explicitly.
- Sheet → PG 1-1 mapping. Migration order: users → categories → funding_sources → transactions → audit.
- Verification: row counts match, sample fields match, no orphan user_id, tenant isolation smoke after migration.

## AUTOPILOT execution rules

### Branch chain pattern (CRITICAL)

PRs are NOT parallel. Each PR's branch is based on the PREVIOUS PR's branch — a stacked chain:

```
main
 └─ feat/F01-w02-migrations          ← branch from main
     └─ feat/F01-w03-db-tenant       ← branch from w02
         └─ feat/F01-w04-messenger   ← branch from w03
             └─ feat/F01-w05-observability  ← branch from w04
                 └─ feat/F01-w06-legacy-move  ← branch from w05
```

Why chained: W0.3 needs W0.2's schema for tenant isolation tests. W0.4 needs W0.3's DB layer. Etc. Each branch's local verify passes only with prior PRs' changes present.

**Branch creation sequence:**
```bash
# After completing W0.2 commits, before starting W0.3:
git checkout feat/F01-w02-migrations
git checkout -b feat/F01-w03-db-tenant   # branches from w02 HEAD
```

### Per-PR workflow (10-step from development-workflow.md §2)

For each W0.x:

1. Read relevant spec section (don't re-read everything)
2. Draft test plan (write in head, no doc needed)
3. Plan 10-line: files, migration, tests, integration points, risks
4. Create branch chained from previous (or main for W0.2)
5. Code + write tests SAME phase
6. Run local verification:
   ```bash
   source .venv/bin/activate
   ruff check core/ markets/ tests/
   black --check core/ markets/ tests/
   mypy core/ markets/ tests/
   lint-imports
   pytest tests/ -v
   ```
   ALL 5 must pass.
7. Commit atomically (multiple commits per PR per workflow §2.4)
8. **NO Codex review.** Founder runs Codex in batch after all 5 PRs done.
9. **NO merge.** Branch stays. Proceed to next W0.x.
10. Update internal tracker: PR done, moving to next.

### Commit message pattern
- `chore(W0.X): <what>` for setup/config
- `feat(W0.X): <what>` for new functional code
- `test(W0.X): <what>` for tests
- `docs(W0.X): <what>` for docs

### Circuit breakers (HALT and report to founder)

PAUSE immediately and output a status report if ANY of these happen:

1. **Local verify fails twice in a row** for the same PR (after 2 self-fix attempts). Don't loop forever — surface to founder.
2. **Test failure** that requires architectural decision not covered in gap decisions or spec.
3. **Scope ambiguity** — spec doesn't tell you what to do. Don't guess on architectural decisions during Wave 0 foundation.
4. **Import-linter violation** introduced by your own code that you can't resolve without restructuring.
5. **detect-secrets** flags a NEW finding (real or false positive) that needs founder audit.
6. **Cumulative context concern:** if you sense your context window is filling up (>70% used), pause and report. Founder will resume in fresh session.
7. **mypy --strict** error that requires changing a public API or adding a type ignore (type ignores need founder approval).
8. **Tool errors** twice in a row on the same operation. Don't retry blindly.

### Circuit breaker report template

```
HALT — Circuit breaker triggered.

PR in progress: W0.X
Branch: feat/F01-w0X-...
Last successful step: <step name>
Failing step: <step name>
Reason: <one of the 8 circuit breaker conditions>

Detail:
<copy-paste of error output, relevant code, or decision needed>

State:
- Branches created so far: <list>
- Commits on current branch: <list>

Requesting founder input on: <specific question>
```

Save this report at `/tmp/wave0-circuit-break.md` for founder pickup.

### Anti-patterns (NEVER do)

- Code before reading spec
- Skip 10-step workflow
- Mock Postgres in integration tests (use testcontainers)
- One monster commit (split atomic)
- Skip tenant isolation test when DB involved (MANDATORY)
- Bump spec version in-session iteration
- Skip CHANGELOG entry
- Code into legacy structure (only `core/` + `markets/{vn,global_}/`)
- `if market == "vn"` in `core/`
- `core/` importing from `markets/`
- More than 2 active branches simultaneously
- **Auto-merge any PR** (Mode 3 forbids — founder merges in batch)
- **Invoke Codex** (Mode 3 forbids — founder runs in batch)

---

# W0.2 — Migration framework + initial schema

**Base branch:** main
**New branch:** `feat/F01-w02-migrations`

## Scope

Alembic migrations + initial schema 0001 (10 tables). testcontainers-python in `tests/conftest.py` with tenant isolation helper.

## Files

- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`
- `migrations/versions/0001_initial_schema.py` — 10 tables per TDD §2.1 + `funding_sources` (Gap 1) + `webhook_tokens` (Gap 3) + `transactions.funding_source_id` FK NULL (Gap 1)
- `tests/conftest.py` — testcontainers Postgres fixture, alembic upgrade/downgrade helper, tenant isolation assertion helper
- `tests/integration/__init__.py`
- `tests/integration/test_migrations.py` — upgrade head + downgrade base + smoke INSERT/SELECT
- Add to `requirements.txt`: `asyncpg`, `sqlalchemy[asyncio]`
- Add to pyproject `[project.optional-dependencies.dev]`: `testcontainers[postgresql]`, `alembic`

## Schema

Read `docs/tdd-vi.md` §2.1 for full DDL — that's source of truth.

10 tables: users, categories, funding_sources, transactions, webhook_tokens, bot_state, bank_connections, scheduled_jobs, monthly_reports, analytics_events, admin_audit_log.

## Acceptance (must pass before chaining to W0.3)

- `alembic upgrade head` creates all tables; `alembic downgrade base` drops them cleanly (test in tests/integration/test_migrations.py)
- testcontainers Postgres 16 spins in <30s
- `funding_sources` table + `transactions.funding_source_id` FK exist
- `webhook_tokens` with hashed token + kind check exists
- pre-commit pass; lint-imports 3 contracts kept
- CHANGELOG entry added
- Atomic commits (5-8 expected)

After W0.2 complete + local verify passes → checkout new branch `feat/F01-w03-db-tenant` from `feat/F01-w02-migrations` HEAD. Proceed.

---

# W0.3 — DB access layer + tenant_context

**Base branch:** `feat/F01-w02-migrations`
**New branch:** `feat/F01-w03-db-tenant`

## Scope

asyncpg pool factory + tenant context via contextvars + cross-tenant assertion helper.

## Files

- `core/db.py` — `create_pool()`, `get_pool()`, `close_pool()`. asyncpg min=2, max=10, command_timeout=30, statement_cache_size=100.
- `core/tenant_context.py` — ContextVar for user_id + request_id; `set_tenant(user_id, request_id)`, `get_user_id()`, `get_request_id()`, `clear_tenant()`.
- `tests/integration/test_db_pool.py`
- `tests/integration/test_tenant_isolation.py` — 2 users, insert tx each, assert query for user 1 only returns user 1 data.

## Acceptance

- Pool init/close happy path
- 2-user tenant isolation test PASSES (this is THE rule W0.6 will lean on)
- Pool exhaustion: 15 concurrent queries queue, don't crash
- mypy --strict clean

Chain to W0.4.

---

# W0.4 — Messenger adapter interface

**Base branch:** `feat/F01-w03-db-tenant`
**New branch:** `feat/F01-w04-messenger`

## Scope

`messenger.send()` abstract + `BaseSender` ABC + TelegramSender impl. Use Gap 4 schema verbatim. Discord/Messenger adapters ship in Wave 6.

## Files

- `core/messenger/__init__.py` — `send(user_id, payload)` entry
- `core/messenger/base.py` — `BaseSender` ABC + `SendPayload` + `Button` + `Markup` (Gap 4 verbatim)
- `core/messenger/telegram.py` — `TelegramSender(BaseSender)`. httpx wrap Telegram Bot API. Maps abstract Markup → InlineKeyboardMarkup. Handles text_key → i18n.
- `core/messenger/i18n.py` — minimal `t(key, locale, **params)` stub. Loads `core/messenger/locales/{vi,en}.json`.
- `core/messenger/locales/vi.json` + `en.json` — minimal strings for tests
- `tests/unit/test_messenger_payload.py`
- `tests/unit/test_messenger_telegram_mock.py` — mock httpx, verify TelegramSender calls right API + reply_markup
- `tests/contract/test_messenger_contract.py` — parametrize over adapter

## Acceptance

- Payload accepts text_key XOR text (exactly one)
- TelegramSender mock test passes
- i18n stub returns localized string
- Contract test passes for TelegramSender
- mypy --strict clean

Chain to W0.5.

---

# W0.5 — Logging + health + Sentry

**Base branch:** `feat/F01-w04-messenger`
**New branch:** `feat/F01-w05-observability`

## Scope

structlog with context binding + Sentry init + /health endpoints + request ID middleware.

## Files

- `core/logging.py` — structlog config. Bind user_id + request_id from tenant_context. JSON in prod, console in dev.
- `core/observability.py` — `init_sentry(dsn)`, `health_app` FastAPI sub-app with `/health` (200 OK) + `/health/detailed` (pool state, DB ping, build info), `request_id_middleware` (UUID per request).
- Add to `requirements.txt`: `structlog`, `sentry-sdk[fastapi]`
- `tests/unit/test_logging.py`
- `tests/unit/test_sentry.py` — mock Sentry, verify user_id tag
- `tests/integration/test_health.py`

## Acceptance

- Log line includes user_id + request_id when tenant context set
- Sentry receives exception with user_id tag (mock)
- /health → 200 always; /health/detailed → 503 when DB down
- Request ID middleware: every request gets UUID, propagated to logs
- mypy --strict clean

Chain to W0.6.

---

# W0.6 — Legacy code move + data migration (BIGGEST PR)

**Base branch:** `feat/F01-w05-observability`
**New branch:** `feat/F01-w06-legacy-move`

## Scope

Eliminate legacy single-tenant code. Move `handlers/*` → `core/handlers/*` + `markets/vn/`. Refactor email_parser to plugin (Gap 2). Wire SePay handler to token lookup (Gap 3). Migrate founder data (Gap 5).

## Files (move + rewrite)

- `handlers/transaction.py` → `core/handlers/transaction.py` (multi-tenant)
- `handlers/manage.py` → `core/handlers/manage.py`
- `handlers/reports.py` → `core/handlers/reports.py`
- `handlers/allocation.py` → `core/handlers/allocation.py`
- `handlers/sepay.py` → `markets/vn/capture/sepay_webhook.py` (uses webhook_tokens lookup with hash compare)
- `handlers/email_parser.py` → split into plugin pattern under `markets/vn/email_parsers/`:
  - `__init__.py` (auto-imports all parser modules to trigger registration)
  - `base.py` — `BankEmailParser` ABC + `PARSERS` registry + `register_parser` decorator (Gap 2)
  - `tcb.py`, `cake.py`, `acb.py`, `sacombank.py`, `bidv.py`, `mb.py` — one parser per bank, `@register_parser('TCB')` etc.
- `telegram_api.py` → merge into `core/messenger/telegram.py`
- `sheets.py` → DELETE (Postgres takes over)
- `main.py` → refactor entrypoint to new structure
- `scripts/migrate_sheets.py` — Gap 5 one-time migration. Order strict: users → categories → funding_sources (parse from col P) → transactions → audit. Verification: row counts, sample fields, no orphan user_id.

## Tests

- `tests/integration/test_email_parser_plugins.py` — each registered parser passes can_parse + parse → CanonicalTx contract
- `tests/integration/test_sepay_webhook.py` — token hash lookup, payload → tx in DB with user_id scope
- `tests/integration/test_e2e_smoke.py` — webhook → tx inserted scoped → reports query returns it
- `tests/scripts/test_migrate_sheets.py` — mock sheets, verify migration + verification logic
- Test the email parser INVARIANTS: parsers must not import db, must not import messenger (use `import-linter` contract or grep-based test).

## Acceptance — MOST STRINGENT

- `sheets.py` deleted; `handlers/` empty or removed
- All legacy paths migrated to new structure
- import-linter still passes (3 contracts) — may need to update root_packages to remove `handlers`
- Email parser invariants enforced (no DB/messenger calls from parser code)
- Token lookup uses hash compare; webhook returns 200 silently when token invalid (no info leak)
- Founder data migrated; row counts match; sample fields verified
- Document `user_id=1 = founder` bootstrap-only in `scripts/migrate_sheets.py` docstring AND README
- mypy --strict clean entire `core/` + `markets/`
- CHANGELOG entry comprehensive

---

# Final report (after W0.6 complete)

When all 5 PRs are done and on their branches, output:

```
═══════════════════════════════════════════════════════
WAVE 0 AUTOPILOT COMPLETE — Ready for batch review
═══════════════════════════════════════════════════════

Branches created (chained):
1. feat/F01-w02-migrations         <commit count> commits
2. feat/F01-w03-db-tenant          <commit count> commits
3. feat/F01-w04-messenger          <commit count> commits
4. feat/F01-w05-observability      <commit count> commits
5. feat/F01-w06-legacy-move        <commit count> commits

Total: <X> files changed, <Y> insertions, <Z> deletions

Local verification (all branches): ALL PASS
- ruff: <count> errors across 5 branches
- black: <count>
- mypy: <count>
- lint-imports: <count>
- pytest: <count> tests passed across all branches

Suggested batch review order:
1. Checkout main, then for each branch in order:
   git checkout feat/F01-w02-migrations
   /codex:review --scope branch --base main
   <fix any findings>
   git checkout main && git merge --squash feat/F01-w02-migrations
   git commit -m "F01: W0.2 ..."
2. For W0.3: needs rebase onto new main first
   git checkout feat/F01-w03-db-tenant
   git rebase main      # bring in W0.2 squash
   /codex:review --scope branch --base main
   ...merge as W0.3...
3. Repeat for W0.4, W0.5, W0.6.

Estimated batch review time: 1-2 hours.

Decisions I made during execution that need founder confirmation:
- <list any non-obvious choices, e.g. library version pins, naming conventions for new modules>

Anti-patterns I encountered but resolved:
- <list any near-misses or fixes during execution>

End of autopilot run.
═══════════════════════════════════════════════════════
```

## Global executor rules

1. **READ SPEC FIRST** for each W0.x. Don't write code blind.
2. **NEVER skip 10-step workflow.**
3. **NEVER mutate real `core/` for tests** (use tmp_path — W0.1 lesson).
4. **NEVER commit secrets** (detect-secrets blocks).
5. **NEVER auto-merge** (Mode 3 strict).
6. **NEVER invoke Codex** during run (Mode 3 strict).
7. **NEVER skip tenant isolation test** when DB involved.
8. **If unsure on architecture**, trigger circuit breaker.
9. **Batch tool calls** for parallel reads.
10. **Use TaskList** to track sub-steps per PR.
11. **Memory hygiene:** if you make a non-obvious decision, save brief memory note for future sessions.
12. **Verify before claiming done:** re-run tests after "tests pass".
13. **Tool errors twice in row → circuit breaker**, don't retry blindly.
14. **Context budget:** if >70% context used, trigger circuit breaker so founder can resume in fresh session with state intact.

Begin with W0.2. No further confirmation needed — execute through W0.6.
