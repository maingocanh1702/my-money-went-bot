# Wave 0 Batch Review Playbook (W0.2 → W0.6)

> Copy each block in order. Run from `/Users/maingocanh/Projects/MyMoneyWent`.
> 1-2h block of focused time recommended. Don't interleave with other work —
> rebase chain is brittle if intermediate state drifts.

---

## Pre-flight (run once at session start)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
source .venv/bin/activate

git status                                    # must be clean
git branch                                    # expect: main + 5 feat/F01-w0{2..6}-*
git log --oneline -3                          # latest = W0.1 squash on main

# Verify all 5 branches exist
for b in w02-migrations w03-db-tenant w04-messenger w05-observability w06-legacy-move; do
  git rev-parse --verify feat/F01-$b > /dev/null && echo "✓ feat/F01-$b" || echo "✗ MISSING feat/F01-$b"
done
```

If any branch missing → HALT. Re-run autopilot or check Claude Code session state.

---

## W0.2 — Migration framework + initial schema

### 1. Checkout + inspect
```bash
git checkout feat/F01-w02-migrations
git log --oneline main..HEAD                  # expect 6 commits
git diff main..HEAD --stat | tail -20         # scope check
```

### 2. Run Codex review
```
/codex:review --scope branch --base main
```

### 3a. IF Codex clean → squash-merge

```bash
git checkout main
git merge --squash feat/F01-w02-migrations
git commit -m "F01: W0.2 migration framework + initial schema

Alembic + initial schema 0001 (11 tables per TDD §2.1).
Includes funding_sources + transactions.funding_source_id NULL FK
(Gap 1), webhook_tokens hashed table (Gap 3 option 2),
users.role enum with founder/user/admin CHECK constraint.
testcontainers Postgres 16 + tenant isolation helper in conftest.

3 Codex review rounds: clean."

git branch -D feat/F01-w02-migrations
git log --oneline -4                          # expect new commit on top
```

### 3b. IF Codex has findings

Stay on branch, fix per finding atomically:
```bash
# Make fixes... commit atomic per finding:
git add <files>
git commit -m "fix(W0.2): <what finding>"

# Mini-review on fix diff:
/codex:review --base HEAD~<fix-commit-count>

# Loop until clean. Then go to 3a.
```

### 4. Rebase W0.3 onto new main
```bash
git checkout feat/F01-w03-db-tenant
git rebase main                               # picks up W0.2 squash
# Conflicts? Should be minimal — W0.3 doesn't touch migration files.
# If conflict: resolve, git add, git rebase --continue
# After rebase clean:
source .venv/bin/activate
pytest tests/ -v                              # smoke after rebase
```

If tests fail after rebase → STOP. Check conflict resolution carefully.

---

## W0.3 — DB access + tenant_context

### 1. Inspect
```bash
git checkout feat/F01-w03-db-tenant
git log --oneline main..HEAD                  # expect 3 commits
git diff main..HEAD --stat
```

### 2. Codex review
```
/codex:review --scope branch --base main
```

**Focus risks to verify in findings:**
- Tenant isolation test có thật sự bypass-able không? (vd query missing WHERE user_id)
- ContextVar leak across async tasks? (asyncio.create_task có copy context không)
- Pool exhaustion behavior — queue vs crash

### 3a. Clean → merge
```bash
git checkout main
git merge --squash feat/F01-w03-db-tenant
git commit -m "F01: W0.3 DB access layer + tenant_context

asyncpg pool factory (min=2, max=10, command_timeout=30,
statement_cache_size=100). ContextVar-based tenant scoping
for user_id + request_id. Cross-tenant assertion helper.

2-user tenant isolation test: PASS — User A query returns
only A's data, User B query returns only B's. This is THE
rule downstream PRs lean on."

git branch -D feat/F01-w03-db-tenant
```

### 3b. Issues → fix loop (same pattern as W0.2)

### 4. Rebase W0.4
```bash
git checkout feat/F01-w04-messenger
git rebase main
source .venv/bin/activate
pytest tests/ -v
```

---

## W0.4 — Messenger adapter interface

### 1. Inspect
```bash
git checkout feat/F01-w04-messenger
git log --oneline main..HEAD                  # expect 4 commits
git diff main..HEAD --stat
```

### 2. Codex review
```
/codex:review --scope branch --base main
```

**Focus risks:**
- SendPayload "exactly ONE of text_key/text" enforced at runtime (not just doc)?
- Markup → InlineKeyboardMarkup mapping covers: empty rows, URL+callback_data conflict, special characters in label
- i18n stub locale fallback: locale=`vi` missing key → fallback to `en`?

### 3a. Merge
```bash
git checkout main
git merge --squash feat/F01-w04-messenger
git commit -m "F01: W0.4 messenger adapter interface

core/messenger/ — BaseSender ABC + TelegramSender impl.
SendPayload TypedDict (Gap 4 verbatim): exactly one of
text_key/text, abstract Markup with Button dataclass.
TelegramSender maps Markup → InlineKeyboardMarkup.
i18n stub (full F-i18n ships Wave 1).

Discord + Messenger adapters ship Wave 6."

git branch -D feat/F01-w04-messenger
```

### 4. Rebase W0.5
```bash
git checkout feat/F01-w05-observability
git rebase main
source .venv/bin/activate
pytest tests/ -v
```

---

## W0.5 — Logging + health + Sentry

### 1. Inspect
```bash
git checkout feat/F01-w05-observability
git log --oneline main..HEAD                  # expect 3 commits
git diff main..HEAD --stat
```

### 2. Codex review
```
/codex:review --scope branch --base main
```

**Focus risks:**
- Sentry `user_id` tag scrubbing — PII (email, name) trong context không leak?
- structured logs có log raw token / password / DSN không?
- `/health/detailed` có expose internal state nhạy cảm (pool stats có OK, schema version OK; raw DSN với password thì KHÔNG)?
- Request ID middleware: UUID truly unique per request, không reuse across requests?
- Jinja2 runtime dep thực sự cần (decision #7 từ autopilot) hay có thể init Sentry không StarletteIntegration?

### 3a. Merge
```bash
git checkout main
git merge --squash feat/F01-w05-observability
git commit -m "F01: W0.5 logging + health + Sentry

structlog with user_id + request_id context binding from
tenant_context. JSON in prod, console in dev.
core/observability.py: Sentry init with AsyncioIntegration,
/health (200 always), /health/detailed (pool state, DB ping),
request_id_middleware (UUID per request).

Jinja2 added to runtime requirements (sentry-sdk Starlette
integration footgun — see autopilot decision #7)."

git branch -D feat/F01-w05-observability
```

### 4. Rebase W0.6
```bash
git checkout feat/F01-w06-legacy-move
git rebase main
source .venv/bin/activate
pytest tests/ -v
```

---

## W0.6 — Foundation invariants (legacy cutover → F02)

### 1. Inspect
```bash
git checkout feat/F01-w06-legacy-move
git log --oneline main..HEAD                  # expect 6 commits
git diff main..HEAD --stat                    # biggest PR
```

### 2. Codex review
```
/codex:review --scope branch --base main
```

**Focus risks (highest among 5 PRs):**
- Parser purity contract: import-linter catches `core.db` / `core.messenger` import — verify with grep `from core.db` và `from core.messenger` trong `markets/vn/email_parsers/` returns 0 matches
- Webhook token hash compare: dùng `hmac.compare_digest()` không phải `==` (timing attack)?
- SHA-256 hash đúng — không phải plain hash với short length
- SePay webhook returns 200 silently on bad token — không leak "user not found" message
- Founder seed migration: `INSERT ... ON CONFLICT DO NOTHING` để re-run idempotent?
- `migrate_sheets.py` script verification logic: row count match check có chạy không, hay chỉ commit silently
- W0.6 actual shipped scope vs spec — Codex có flag scope split không (founder đã accept, không phải bug)

### 3a. Merge
```bash
git checkout main
git merge --squash feat/F01-w06-legacy-move
git commit -m "F01: W0.6 foundation invariants (legacy cutover → F02)

REVISED SCOPE (founder accepted 2026-05-11): ship foundational
invariants only, legacy handlers rewrite + sheets.py delete
deferred to F02 Wave 2.

Shipped:
- markets/vn/email_parsers/ plugin pattern (Gap 2: ABC +
  registry decorator + invariants)
- 4th import-linter contract 'parsers-are-pure'
  (parsers ↛ core.db / core.messenger)
- webhook_tokens hashed table (Gap 3: SHA-256, hmac.compare_digest,
  silent 200 on bad tokens)
- markets/vn/capture/sepay_webhook.py (token hash lookup)
- Founder seed scaffold (Gap 5: user_id=1, role='founder',
  bootstrap-only documented)
- scripts/migrate_sheets.py ready (NOT executed)

Deferred to F02:
- handlers/{transaction,manage,reports,allocation}.py multi-tenant rewrite
- sheets.py delete (Postgres take over)
- main.py refactor entrypoint
- Actual founder data migration run
- Remove 'handlers' from import-linter root_packages

See project_w06_scope_split.md memory + docs/operations/
development-workflow.md §4 W0.6 row + Wave 2 F02 EXPANDED scope row."

git branch -D feat/F01-w06-legacy-move
```

---

## Final state verification

```bash
git checkout main
git log --oneline -7                          # expect: 5 W0.x + W0.1 + baseline
git branch                                    # expect: * main (only)

source .venv/bin/activate
ruff check core/ markets/ tests/
black --check core/ markets/ tests/
mypy core/ markets/ tests/
lint-imports                                  # 4 contracts kept
pytest tests/ -v                              # 112+ tests pass
```

Expected `git log`:
```
<sha7> F01: W0.6 foundation invariants (legacy cutover → F02)
<sha6> F01: W0.5 logging + health + Sentry
<sha5> F01: W0.4 messenger adapter interface
<sha4> F01: W0.3 DB access layer + tenant_context
<sha3> F01: W0.2 migration framework + initial schema
c32ee69 F01: W0.1 repo skeleton + lint boundary
ffdb413 chore: initial commit (pre-Wave 0 baseline)
```

If all checks pass → **Wave 0 complete**. Multi-tenant foundation ready for Wave 1 (F-onboarding, F-admin-tools, F-i18n, F-settings — these can run parallel).

---

## Recovery scenarios

### Codex finds Critical/High in middle of chain
Fix on current branch, mini-review, then continue chain. The subsequent branches will rebase onto the updated main anyway.

### Rebase conflict
Most likely in W0.6 (legacy paths). Resolve manually, `pytest tests/` after to verify functional integrity, then `git rebase --continue`.

### Tests fail after rebase
The rebase brought changes that broke something. Don't blindly commit. Investigate root cause:
```bash
git rebase --abort   # back to pre-rebase state
git log feat/F01-w0X-... main..HEAD
# Identify which W0.(X-1) change broke W0.X — likely a shared API change
# Either fix W0.X to match new API, or revisit W0.(X-1) decision
```

### Founder needs to abort
Worst case rollback:
```bash
git checkout main
git reset --hard <pre-batch-review-sha>      # find via reflog
# All squash-merges undone. Branches still exist (not deleted yet) or
# need to be recreated from autopilot session.
```
