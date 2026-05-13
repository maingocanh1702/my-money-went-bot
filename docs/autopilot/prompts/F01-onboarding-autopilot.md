# Autopilot — F01 onboarding-start

> Generated 2026-05-13. Single-phase autopilot prompt per memory rules
> `feedback_autopilot_prompt_scope` (single-phase ăn chắc hơn multi-phase),
> `feedback_prefer_autopilot_prompts` (≥2-file change → autopilot, không manual),
> `feedback_autopilot_prompt_template` (đọc template trước khi reinvent).
>
> Lockdown source: `docs/operations/F01-F08-lockdown.md` §1.

---

Task: F01 onboarding-start — multi-channel `/start` + user create + 14d trial assign.

You are working in `~/Projects/MyMoneyWent-F01` (git worktree of MyMoneyWent, a Telegram/Discord bot SaaS for expense tracking, Phase 2 Wave 1). NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/F01-onboarding-start` (already checked out by worktree creation), Codex 2× consecutive clean (P1 always), then STOP_AT_READY. Pause ONLY on circuit-breaker conditions.

```
Risk tier:          P1
Merge policy:       manual_only
Autopilot maturity: mature (post-F07 6-session pilot validated v0.2.3 orchestrator)
Codex review:       2x_consecutive_clean
```

---

## Context (NOT for execution, just background)

F07 settings shipped 2026-05-13 (`f232b63`) unblocking F02 pipeline. F02 transaction-capture cutover needs user records in DB; user records come from `/start`. F01 is the bot's "front door" — without it, no user exists, no F08 funding source FK works, no F02 INSERT path works. This PR ships the minimal `/start` skeleton; Path A/B/C onboarding flows ship Phase 4 (F01b/c/d).

Legacy `main.py` + `handlers/*.py` is single-tenant founder-only. This PR introduces `core/handlers/` multi-tenant pattern (parallel to legacy until F02 strangler cutover deletes legacy).

## Scope discipline

**Positive scope:**
- `core/handlers/__init__.py` (new) + `core/handlers/start.py` (new) — multi-channel `/start` command handler
- User INSERT: `channel_type`, `channel_user_id`, `chat_id` (nullable), `webhook_token` via `markets.vn.capture.webhook_tokens.mint_token`, `inbound_email` = `u{id}@in.tienvenoidau.com`, `plan='free'`, `trial_ends_at=now()+14d`, `locale='vi'`, `language_code` from update
- Welcome message (locale-aware, via `i18n.t()`)
- Default categories auto-create (`daily_spending`, `saving`, `subscription`) per FE spec §4 domain model
- Wire to `main.py` dispatcher — new Telegram update routing for `/start` command
- New keys in `i18n/vi.py` AND `i18n/en.py` (parity test enforces both)
- 12 integration tests (5 positive + 3 edge + 2 error + 1 isolation + 1 contract)

**Negative scope (do NOT touch):**
- Path A/B/C onboarding flows — Phase 4 (F01b/c/d)
- Path D Family invite accept — ships with Family Plan
- Language confirm UI buttons — defer to F-i18n PR
- `bank_connections` INSERT — F08/F02 own
- `scheduled_jobs` INSERT — F09 owns (BE spec mentions but plan §1 defers)
- Legacy `handlers/*.py` files — F02 strangler cutover will delete; do not modify here
- Modify tracker `docs/implementation-tracker.md` — post-merge update is manual (per memory `feedback_template_distillation_checks`)
- Modify FE spec `docs/features/feature-onboarding.md` — out of scope; spec drift documented in lockdown doc §1.5

**Out-of-scope but documented:**
- EN locale strings polish — F-i18n PR. Add literal English equivalent to satisfy parity; F-i18n PR polishes wording.
- Auto-detect locale from Telegram `language_code` field — defer to F-i18n PR (needs confirm UI)

## Required reading (READ FIRST, in this order, before any code)

1. `docs/operations/F01-F08-lockdown.md` §1 — full lockdown decisions, scope, test plan, acceptance criteria
2. `docs/implementation-plans/phase-2-handlers.md` §1 — F-onboarding scope + 12-test plan baseline
3. `docs/features/feature-onboarding.md` §4 (domain model — default categories) + §6 (error codes) ONLY. Ignore Path A/B/C/D screens.
4. `docs/features/BE/feature-onboarding-tech.md` §2.2 (key queries — INSERT users idempotent) + §4.2 (token format)
5. `migrations/versions/0001_initial_schema.py` — users + categories + bot_state columns. Verify `channel_type`, `channel_user_id`, `chat_id`, `locale`, `language_code`, `webhook_token` storage assumption, `inbound_email`, `plan`, `trial_ends_at` all exist.
6. `core/settings_svc.py` (F07) — pattern reference for service module structure, pure-read separation, type hints, docstrings.
7. `handlers/settings.py` (F07) — pattern reference for handler structure (abstract via `core.messenger.SendPayload`, callback parsing, tenant safety via session-derived `user_id`).
8. `tests/integration/test_settings_happy.py` — fixture pattern reference for integration tests using real DB.
9. `tests/integration/conftest.py` — DB fixture setup pattern.
10. `markets/vn/capture/webhook_tokens.py` — `mint_token(user_id, kind)` signature; F01 calls `mint_token(user.id, 'sepay')` after user INSERT to populate `webhook_tokens` table.
11. `i18n/vi.py` + `i18n/en.py` — existing key conventions (`onboard.*`, `cat.*`, `btn.*`). Add new keys following conventions.
12. `tests/unit/test_i18n_parity.py` (if exists) — parity test. Verify keys added in `vi.py` mirror `en.py` to keep test green.
13. Memory: `project_dual_market_strategy`, `project_monorepo_decision`, `project_wave0_complete`, `feedback_f07_lessons`.

## Pre-flight gate

```bash
cd ~/Projects/MyMoneyWent-F01

git status                                                # MUST be clean
git branch --show-current                                 # MUST be: feat/F01-onboarding-start
git fetch origin && git pull --ff-only origin main || true  # OK if up-to-date or worktree just created
git log --oneline -3                                      # HEAD must include 0347efd (config tolerant env) or later

source .venv/bin/activate                                 # If not symlinked, run python -m venv .venv first
which python pytest pre-commit lint-imports codex         # All MUST resolve

ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v                                          # MUST be green (baseline expected ≥118 passed + 1 xfail)

python scripts/build-dashboard.py                         # MUST exit 0
```

ALL must pass. If any fails → HALT and report. Do not proceed.

Confirm baseline test count BEFORE Step 2 — record exact number for delta tracking in READY report.

## Anti-patterns (NEVER do)

* `git push --force`.
* Add `# type: ignore` — circuit breaker, founder approval needed.
* Auto-merge to main (P1 = `manual_only` per §3.2 risk header).
* Touch legacy `handlers/*.py` files (out-of-scope; F02 strangler owns).
* Touch tracker.md row content (post-merge update is manual).
* Modify FE spec `feature-onboarding.md` (spec drift documented in lockdown, no fix in F01).
* Skip TDD — Step 2 tests MUST be written and FAILING before Step 3 impl.
* Add EN keys without VI counterpart or vice versa — parity test will fail.
* Use synthetic fixtures for integration tests — use real DB fixture from `tests/integration/conftest.py`. Unit tests with mocked DB OK.
* Bypass `mint_token` and write directly to `webhook_tokens` — `mint_token` is the canonical mint path (Gap 3 hash-only invariant).
* Insert user without `inbound_email` populated — migration 0003 backfill_inbound_email (W0.7 contract) requires column non-NULL for new rows.

## Numbered steps

### Step 1 — Verify branch state + autopilot state dir

```bash
git rev-parse HEAD > /tmp/F01-base-sha.txt
mkdir -p .autopilot/state/F01/codex
git log --oneline main..HEAD                              # Should be empty initially
```

### Step 2 — Write failing integration tests (TDD)

Create `tests/integration/test_start_handler.py` with the 12-test plan from lockdown §1.6:

**Positive (5):**
- `test_telegram_start_creates_user` — TG update with `text='/start'`, `from.id=99999` → user row exists with `channel_type='telegram'`, `channel_user_id='99999'`, `plan='free'`, `trial_ends_at` within `[now+13d, now+15d]`
- `test_discord_start_creates_user` — Discord interaction with `member.user.id=42424242` → user row with `channel_type='discord'`
- `test_existing_user_restart_idempotent` — Second `/start` from same TG ID → no duplicate row, returns welcome-back message via `messenger.send`
- `test_default_categories_created_vi` — Post-`/start`, user's categories table has 3 rows: `daily_spending` (daily_cap=100000), `saving` (daily_cap=NULL), `subscription` (daily_cap=NULL), names in VI
- `test_welcome_message_contains_trial_expiry` — Sent message body contains rendered `trial_ends_at` date in user's TZ (default `Asia/Ho_Chi_Minh`)

**Edge (3):**
- `test_concurrent_starts_idempotent` — Two parallel `/start` calls same TG ID → exactly 1 user row (asyncio.gather)
- `test_trial_expired_user_no_reset` — Pre-seed user with `trial_ends_at = now() - 1d` → `/start` keeps `plan='free'`, does NOT reset trial
- `test_null_language_code_defaults_vi` — Update payload missing `language_code` → user.locale='vi'

**Error (2):**
- `test_db_down_graceful_error` — Patch `db.create_pool` to raise → handler logs error, sends friendly message, no traceback to user
- `test_webhook_token_collision_retries` — Patch `mint_token` to raise `IntegrityError` once then succeed → user gets unique token (assert no duplicate `token_hash` in webhook_tokens table)

**Isolation (1):**
- `test_user_a_start_does_not_affect_user_b` — User A `/start`, then User B `/start`, then assert User A's queries return only User A rows (categories, webhook_tokens, bot_state)

**Contract (1):**
- `test_messenger_send_called_with_correct_user_id` — Spy on `messenger.send`; assert called with `user_id=<created user id>`, not `chat_id` or `channel_user_id`

Also add unit tests `tests/unit/test_start_handler_unit.py`:
- Pure logic tests for trial date math, `inbound_email` format (`u{id}@in.tienvenoidau.com`), default category seed data shape

Run:

```bash
pytest tests/integration/test_start_handler.py tests/unit/test_start_handler_unit.py -v
# Expect: ALL FAIL (collection error or AttributeError — module not yet exists)
```

If any test passes on first run → TDD oracle violated. Investigate before Step 3.

### Step 3 — Implement `core/services/user_svc.py`

Create `core/services/__init__.py` (empty marker) + `core/services/user_svc.py`:

```python
"""User service — pure DB operations for /start + user lifecycle (F01).

Spec: docs/features/feature-onboarding.md (F01 minimal scope, Phase 2).
Plan: docs/implementation-plans/phase-2-handlers.md §1.

Scope:
  - create_or_get_user(channel_type, channel_user_id, ...) — idempotent INSERT
  - assign_trial(user_id, days=14) — set trial_ends_at
  - seed_default_categories(user_id, locale) — VI/EN bilingual seed
  - generate_inbound_email(user_id) — canonical format

Out of scope:
  - Onboard path tracking (Phase 4 F01b/c/d)
  - Family invite (Phase 4 family plan ship)
"""
from __future__ import annotations

# ... implementation following core/settings_svc.py pattern
```

Key design points:
- Use `core.db.get_pool()` — do NOT create new pool
- Idempotent INSERT via `ON CONFLICT (channel_type, channel_user_id) DO NOTHING RETURNING *` then SELECT if RETURNING empty (existing user)
- `assign_trial(days=14)` returns `trial_ends_at` UTC; handler renders in user TZ
- `seed_default_categories(user_id, locale='vi')` — bulk INSERT 3 rows; idempotent via `ON CONFLICT (user_id, slug) DO NOTHING`

### Step 4 — Implement `core/handlers/start.py`

Create `core/handlers/__init__.py` + `core/handlers/start.py`:

```python
"""/start handler — multi-channel user onboarding entry point (F01).

Pattern: follows handlers/settings.py (F07) — abstract via core.messenger,
business mutations live in core.services.user_svc.

Tenant safety: user_id is derived from session, never from message content.
"""
from __future__ import annotations

from core import messenger, services
from core.messenger import SendPayload
from i18n import t
from markets.vn.capture.webhook_tokens import mint_token


async def handle_start(update: dict, channel_type: str) -> None:
    """Entry point for /start across channels.

    Steps:
      1. Extract channel_user_id + chat_id + language_code from update
      2. user_svc.create_or_get_user(...) — idempotent
      3. If new user: mint webhook_token, seed categories, assign trial
      4. Send welcome message with trial expiry rendered in user TZ
    """
    # ... impl
```

Welcome message keys (add to `i18n/vi.py` AND `i18n/en.py`):
- `onboard.welcome_new` — "Chào mừng bạn đến với MyMoneyWent!\n\n🎁 Bạn được dùng Pro miễn phí đến {trial_end}.\n\n..."
- `onboard.welcome_back` — "Chào mừng quay lại, {name}!"
- `onboard.trial_expired_info` — "⏰ Trial Pro của bạn đã hết hạn. Đang ở Free tier."
- `cat.default.daily_spending` — "🛒 Chi tiêu hàng ngày"
- `cat.default.saving` — "🏦 Tiết kiệm"
- `cat.default.subscription` — "📱 Đăng ký dịch vụ"
- `error.onboard_create_fail` — "⚠️ Không tạo được tài khoản. Vui lòng thử lại."

EN equivalents (literal, F-i18n polishes):
- `onboard.welcome_new` — "Welcome to MyMoneyWent!\n\n🎁 You have free Pro until {trial_end}.\n\n..."
- `onboard.welcome_back` — "Welcome back, {name}!"
- (etc., 1:1 key parity)

### Step 5 — Wire to `main.py` dispatcher

Modify `main.py` to route `/start` text command to `core.handlers.start.handle_start`:

```python
# In _handle_message, add /start branch BEFORE legacy text dispatch
async def _handle_message(message: dict):
    text = message.get("text", "").strip()
    if text == "/start":
        from core.handlers.start import handle_start
        await handle_start({"message": message}, channel_type="telegram")
        return
    # ... legacy fallback continues
```

Lazy import inside the branch to avoid breaking legacy paths during transition.

### Step 6 — Run pytest, expect green

```bash
pytest tests/integration/test_start_handler.py tests/unit/test_start_handler_unit.py -v
# Expect: 12 passed (integration) + N unit passed

pytest tests/ -v
# Expect: baseline + 12 new = all green (xfail count unchanged: 1)
```

### Step 7 — Full local verify

```bash
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v
pre-commit run --all-files
```

All MUST be green. Any failure → fix before Codex.

### Step 8 — Inline Codex review (P1 → 2× consecutive clean)

```bash
codex review --base main 2>&1 | tee .autopilot/state/F01/codex/round-01.txt
```

Parse output:
* "No issues" / "clean" → 1× clean. Run round 02 for confirmation.
* Findings present → categorize:
  - P0/P1 → fix this round, re-run verify
  - P2 → fix opportunistically
  - Keywords `auth|token|secret|injection|timing` → SECURITY_FINDING → HALT
  - Keywords `schema|migration|breaking` → ARCH_FINDING → HALT
  - Same hash round NN + round NN+1 → RECURRING_FINDING → HALT

Then:
```bash
codex review --commit HEAD 2>&1 | tee .autopilot/state/F01/codex/round-02.txt
```

P1 requires 2 consecutive clean rounds. If round 02 has new findings → fix → run round 03. Max 5 rounds before MAX_ROUNDS breaker.

## Atomic commit plan

```bash
git add tests/integration/test_start_handler.py tests/unit/test_start_handler_unit.py
git commit -m "test(F01): cover /start handler — user create, trial, defaults, isolation"

git add core/services/__init__.py core/services/user_svc.py
git commit -m "feat(F01): user_svc — idempotent create_or_get_user + trial + default categories"

git add core/handlers/__init__.py core/handlers/start.py
git commit -m "feat(F01): /start handler — multi-channel entry point"

git add i18n/vi.py i18n/en.py
git commit -m "feat(F01): i18n keys for onboard welcome + default category names"

git add main.py
git commit -m "feat(F01): wire /start to core.handlers.start (lazy-import branch)"

# After Codex passes, if fix commits needed:
# git commit -m "fix(F01): address codex round 01 — <summary>"
# git commit -m "fix(F01): address codex round 02 — <summary>"
```

Rule: each commit atomic. Reviewer needs `git bisect` to work.

## Circuit breakers

1. **Pre-flight regression** — existing tests no longer pass on main.
2. **TDD oracle violated** — Step 2 tests pass on first run before impl exists.
3. **VERIFY_REGRESSION** — local verify fails twice consecutively.
4. **ARCH_FINDING** — Codex flags schema/breaking/architectural.
5. **SECURITY_FINDING** — Codex flags auth/token/timing/secret/injection.
6. **RECURRING_FINDING** — same hash in round N AND round N+1.
7. **TYPE_IGNORE_PROPOSED** — anywhere.
8. **MAX_ROUNDS** — 5 Codex rounds without achieving 2× consecutive clean.
9. **Tool error twice** in a row on git/codex/pytest.
10. **Context budget >70%** — pause + report.
11. **POLICY_MISMATCH** — auto-merge attempted (this prompt is `manual_only`).
12. **PARITY_BROKEN** — `tests/unit/test_i18n_parity.py` fails after i18n edits (keys mismatch between vi.py and en.py).
13. **F01_SPECIFIC: USERS_SCHEMA_MISMATCH** — migration 0001 schema lacks expected column (channel_type, locale, language_code, etc.). HALT for founder triage; do NOT add migration in this PR.
14. **F01_SPECIFIC: TOKEN_MINT_FAILURE** — `mint_token(user_id, 'sepay')` raises non-IntegrityError exception consistently. Suggests deeper webhook_tokens table issue. HALT.

## Halt report template

```
HALT — F01 onboarding-start circuit broken.

Step:    Step <N> <substep>
Trigger: <one of 14 conditions>
Branch:  feat/F01-onboarding-start
HEAD:    <SHA>

Detail:
<error output OR Codex finding excerpt>

State:
- Commits on branch since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/F01/codex/round-*.txt
- Last verify result: <pass | fail with offending check>
- Test count: baseline <N> → current <M> (delta +<D>)

Requesting founder input on:
<specific question>
```

## Final report — READY_FOR_MANUAL_MERGE (P1 default)

```
═══════════════════════════════════════════════════════
AUTOPILOT F01 onboarding-start — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════

Squash commit:    N/A — founder/manual merge pending
Branch feat/F01-onboarding-start:  still exists (intact, ready for review)
Push origin/main: NOT RUN

Files added:
  - tests/integration/test_start_handler.py  (~250 LOC, 11 tests)
  - tests/unit/test_start_handler_unit.py     (~50 LOC, N unit tests)
  - core/services/__init__.py
  - core/services/user_svc.py                  (~200 LOC)
  - core/handlers/__init__.py
  - core/handlers/start.py                     (~200 LOC)

Files modified:
  - main.py                                    (+ /start dispatch branch)
  - i18n/vi.py                                 (+ 7 keys)
  - i18n/en.py                                 (+ 7 keys, literal English)

Codex review:
  Round 01: <findings count | clean>
  Round 02: <findings count | clean>
  Final state: 2 consecutive clean rounds confirmed (P1 policy)
  Artifacts: .autopilot/state/F01/codex/round-*.txt

Local verification (final):
  ruff / black / mypy / lint-imports: clean
  pytest: <N> passed (baseline <baseline>, expected ≥<baseline+12>)
  pre-commit run --all-files: clean
  xfail count: 1 (W0.7 funding source resolve pin — unchanged, F02 owns)

Decisions made during execution requiring founder review:
  <list any non-obvious calls — e.g., default categories slug normalization,
   error message wording variations, trial date timezone rendering choice>

═══════════════════════════════════════════════════════

Suggested squash command (founder runs after review):

  git checkout main
  git pull --ff-only origin main
  git merge --squash feat/F01-onboarding-start
  git commit -m "feat(F01): /start handler — user create + 14d trial + default categories

  Multi-channel /start command handler (Telegram + Discord wired; Messenger
  ready). Creates user row idempotently, mints sepay webhook_token via
  markets.vn.capture.webhook_tokens.mint_token (Gap 3 hash-only), seeds 3
  default categories (daily_spending, saving, subscription), assigns 14-day
  Pro trial from signup time.

  Spec: docs/features/feature-onboarding.md (Phase 2 minimal scope — Path
  A/B/C/D ship Phase 4).

  Decisions locked 2026-05-13:
    - chat_id NULLABLE (Discord context delayed)
    - Trial 14d FROM signup (not first activity)
    - Locale default 'vi' (BRD VN-first)
    - i18n VI-only polish; EN literal placeholders (F-i18n PR polishes)

  Test plan (12): 5 positive + 3 edge + 2 error + 1 isolation + 1 contract.
  Total post-F01 test baseline: <N> passed, 1 xfail unchanged.

  Unblocks: F08 funding sources (FK chain), F02 transaction capture
  (user_id required for INSERT)."
  git branch -D feat/F01-onboarding-start
  git push origin main

Post-merge actions (founder):
  - Pull main in Cowork session repo + run `python scripts/build-dashboard.py`
    to verify tracker render
  - Update implementation-tracker.md F01 row ⬜→✅, bump changelog
  - Pre-commit hook auto-stages docs/dashboard.{html,md}

═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1.
