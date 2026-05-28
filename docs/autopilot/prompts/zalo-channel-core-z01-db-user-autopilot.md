# Autopilot — Zalo Z01 DB + user service channel support

Task: Zalo Z01 — add core DB/user-service support for Zalo channel routing.

You are working in `/Users/maingocanh/Projects/MyMoneyWent` on a multi-tenant Vietnamese personal finance bot. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `codex/zalo-z01-db-user`, inline Codex review with ≤3 fix rounds, then auto squash-merge to local `main` only. Pause ONLY on circuit-breaker conditions. Do not push to origin.

```
Risk tier:          P1
Merge policy:       founder_override_auto_squash_local
Autopilot maturity: mature
Codex review:       2x_consecutive_clean
```

## Context (NOT for execution, just background)

The Zalo implementation plan v0.3.0 chooses the core path: use PostgreSQL + `core.messenger`, not deprecated Google Sheets legacy state. Existing schema only allows `telegram`, `messenger`, and `discord`; Zalo needs a schema-safe channel type and a string chat/routing id because Zalo IDs can exceed BIGINT.

## Scope discipline

**Positive scope:**
- Add Alembic migration `0004_add_zalo_channel.py`.
- Allow `users.channel_type='zalo'`.
- Add nullable `users.channel_chat_id TEXT` + partial index.
- Update `core.services.user_svc.create_or_get_user()` with optional `channel_chat_id`.
- Update `core.handlers.start.handle_start()` to pass `channel_chat_id`.
- Add/extend tests for migration, user service, and start handler.

**Negative scope:**
- Do not implement Zalo send API.
- Do not add `/zalo/webhook`.
- Do not touch deprecated `sheets.py` or legacy `handlers/*`.
- Do not change Telegram `chat_id BIGINT` behavior.
- Do not add sub-category schema.

**Out-of-scope but documented:**
- Token storage, webhook signature verification, numbered category replies, and report builders are later Zalo prompts.

## Required reading (READ FIRST, in this order, before any code)

1. `docs/implementation-plan-zalo-channel-core.md` — Summary, Verification Status, Key Changes §1.
2. `migrations/versions/0001_initial_schema.py` — `users` table and `chk_channel_type`.
3. `migrations/versions/0002_webhook_display_suffix.py` and `0003_backfill_inbound_email.py` — local migration style.
4. `core/services/user_svc.py` — `User`, `_row_to_user`, `create_or_get_user`.
5. `core/handlers/start.py` — `handle_start` signature and pass-through pattern.
6. `tests/integration/test_migrations.py` — migration smoke-test style.
7. `tests/integration/test_start_handler.py` — existing `/start` tests to extend.

## Pre-flight gate

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status
git branch --show-current
git fetch origin && git pull --ff-only origin main

source .venv/bin/activate
which python pytest codex

ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v
```

ALL must pass. If any fails, HALT and report. Record baseline test count.

## Anti-patterns (NEVER do)

* `git push --force` — preserves forensic branch history.
* Add `# type: ignore` — founder approval required.
* Push to origin/main — founder performs the final push after all Zalo phases pass.
* Change `chat_id BIGINT` to TEXT — breaks Telegram assumptions.
* Rewrite existing migrations — create `0004`, do not edit historical revisions.
* Touch legacy `sheets.py` or `handlers/*` — Zalo core path only.
* Skip TDD — tests must fail before implementation.

## Numbered steps

### Step 1 — Branch + state

```bash
git checkout -b codex/zalo-z01-db-user
git rev-parse HEAD > /tmp/zalo-z01-base-sha.txt
mkdir -p .autopilot/state/zalo-z01/codex
git log --oneline main..HEAD
```

### Step 2 — Write failing tests (TDD)

Add/extend tests:

- `tests/integration/test_migrations.py`
  - `test_users_channel_type_accepts_zalo`
  - `test_users_channel_chat_id_column_exists_and_accepts_long_string`
  - `test_users_channel_chat_id_index_exists`
- `tests/integration/test_start_handler.py`
  - `test_zalo_start_creates_user_with_channel_chat_id`
  - `test_zalo_restart_backfills_missing_channel_chat_id`
- Unit-level pure check if useful:
  - `_row_to_user` projection includes `channel_chat_id` if `User` dataclass is extended.

Run:

```bash
pytest tests/integration/test_migrations.py tests/integration/test_start_handler.py -v
```

Expected: new tests fail on current main. If they pass before code changes, HALT with `TDD_ORACLE_VIOLATED`.

### Step 3 — Implement migration

Create `migrations/versions/0004_add_zalo_channel.py`:

- `upgrade()`:
  - `ALTER TABLE users DROP CONSTRAINT chk_channel_type;`
  - `ALTER TABLE users ADD CONSTRAINT chk_channel_type CHECK (channel_type IN ('telegram', 'messenger', 'discord', 'zalo'));`
  - `ALTER TABLE users ADD COLUMN channel_chat_id TEXT;`
  - Create partial index on `channel_chat_id IS NOT NULL`.
- `downgrade()`:
  - Drop index.
  - Drop `channel_chat_id`.
  - Restore old `chk_channel_type` without `zalo`.

Sanity check: downgrade is only valid if no `zalo` rows exist; document that in migration docstring.

### Step 4 — Update user service + start handler

- Extend `User` with `channel_chat_id: str | None`.
- Update `_row_to_user`.
- Add optional `channel_chat_id: str | None = None` to `create_or_get_user`.
- Insert and self-heal backfill `channel_chat_id` without overwriting populated values.
- Add optional `channel_chat_id` to `handle_start` and pass through.
- Preserve all existing Telegram tests and behavior.

### Step 5 — Local verification

```bash
ruff check core/ tests/ migrations/
black --check core/ tests/ migrations/
mypy core/
lint-imports
pytest tests/integration/test_migrations.py tests/integration/test_start_handler.py -v
pytest tests/ -v
```

All must pass. If verification fails twice consecutively, HALT with `VERIFY_REGRESSION`.

## TDD gate

Tests in Step 2 must fail before implementation and pass after Step 4. Do not mark tests xfail or skip.

## Atomic commit plan

```bash
git add tests/integration/test_migrations.py tests/integration/test_start_handler.py
git commit -m "test(zalo): pin channel schema and start handler routing"

git add migrations/versions/0004_add_zalo_channel.py
git commit -m "feat(zalo): add channel schema support"

git add core/services/user_svc.py core/handlers/start.py
git commit -m "feat(zalo): store channel chat id during start"
```

## Inline Codex review

Run up to 3 rounds:

```bash
codex review --base main 2>&1 | tee .autopilot/state/zalo-z01/codex/round-01.txt
```

Fix P0/P1 findings. Fix P2 only if scoped and low-risk. Re-run local verification before each next round. Require 2 consecutive clean rounds. Save round files as `round-02.txt`, `round-03.txt`.

## Auto squash-merge gate

After local verification is green and Codex has 2 consecutive clean rounds, squash this branch into local `main`:

```bash
git branch --show-current                         # MUST be codex/zalo-z01-db-user
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main
git merge --no-commit --no-ff codex/zalo-z01-db-user
git merge --abort

git merge --squash codex/zalo-z01-db-user
git commit -m "feat(zalo): add channel schema and start routing"
git branch -D codex/zalo-z01-db-user

ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v
```

If any command fails, HALT and preserve branch state. Do not push to origin.

## Circuit breakers

1. Pre-flight regression.
2. TDD_ORACLE_VIOLATED.
3. VERIFY_REGRESSION.
4. ARCH_FINDING.
5. SECURITY_FINDING.
6. RECURRING_FINDING.
7. TYPE_IGNORE_PROPOSED.
8. MAX_ROUNDS.
9. Tool error twice in a row.
10. Context budget >70%.
11. POLICY_MISMATCH — any attempt to push remote or merge without 2× clean review.
12. MIGRATION_DRIFT — migration edits historical revisions or downgrade is unsafe without documentation.

## Halt report

Emit the halt report format from `docs/autopilot/autopilot-prompt-template.md` §3.14.

## Final report

Emit COMPLETE-style report with:

- Squash commit SHA on local `main`.
- Branch deleted.
- Push origin/main: NOT RUN.
- Final verification counts.
- Codex review artifacts.

Begin with Pre-flight, then Step 1.
