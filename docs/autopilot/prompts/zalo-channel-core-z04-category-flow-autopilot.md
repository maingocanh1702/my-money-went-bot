# Autopilot — Zalo Z04 numbered category flow

Task: Zalo Z04 — DB-backed numbered parent-category flow for new SePay transactions.

You are working in `/Users/maingocanh/Projects/MyMoneyWent` on a multi-tenant Vietnamese personal finance bot. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `codex/zalo-z04-category-flow`, inline Codex review with ≤3 fix rounds, then auto squash-merge to local `main` only. Pause ONLY on circuit-breaker conditions. Do not push to origin.

```
Risk tier:          P1
Merge policy:       founder_override_auto_squash_local
Autopilot maturity: mature
Codex review:       2x_consecutive_clean
```

## Context (NOT for execution, just background)

Zalo v1 supports parent-category selection only. The core schema has `categories` and `transactions.category_id`; it does not have sub-categories. Legacy Telegram still uses Google Sheets state, while Zalo uses DB `bot_state`.

## Scope discipline

**Positive scope:**
- Add DB-backed bot-state helpers for Zalo category queue.
- Add `core/handlers/categorize.py`.
- Send numbered parent-category picker after a new SePay transaction is inserted.
- Resolve numeric replies from `/zalo/webhook` into `transactions.category_id` and `confirmed=true`.
- Support queueing multiple pending transactions.
- Add unit/integration tests for queue, expiry, isolation, and SePay wiring.

**Negative scope:**
- Do not add sub-category support.
- Do not modify legacy Telegram Sheets state.
- Do not rewrite SePay parsing beyond returning inserted transaction id.
- Do not call Zalo APIs directly; send via `core.messenger.send`.
- Do not make `/manage` work on Zalo.

**Out-of-scope but documented:**
- `bot_state` PK change to `(user_id, channel_type)` is V2.
- Core report builders remain separate work.

## Required reading

1. `docs/implementation-plan-zalo-channel-core.md` — Key Changes §4 and Test Plan.
2. `migrations/versions/0001_initial_schema.py` — `categories`, `transactions`, `bot_state`.
3. `markets/vn/capture/sepay_webhook.py` — `_persist` and `handle_sepay_webhook`.
4. `core/messenger/base.py` — `Markup` and `Button`.
5. `core/messenger/send.py` — send by `user_id`.
6. `core/handlers/zalo_webhook.py` from Z03 — numeric reply routing hook.
7. `tests/integration/test_sepay_webhook.py` — existing SePay persistence tests.
8. `tests/integration/test_tenant_isolation.py` — isolation test style.

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

ALL must pass. Confirm Z01-Z03 are merged. If Zalo sender or webhook route is missing, HALT with `DEPENDENCY_MISSING`.

## Anti-patterns (NEVER do)

* `git push --force`.
* Add `# type: ignore`.
* Push to origin/main — founder performs the final push after all Zalo phases pass.
* Add sub-category tables or columns — v1 parent category only.
* Modify legacy `sheets.py` state — Zalo uses `bot_state`.
* Finalize category without checking `transactions.user_id = user_id`.
* Ignore duplicate webhook inserts — only send picker for newly inserted tx rows.
* Send raw financial secrets in logs.

## Numbered steps

### Step 1 — Branch + state

```bash
git checkout -b codex/zalo-z04-category-flow
git rev-parse HEAD > /tmp/zalo-z04-base-sha.txt
mkdir -p .autopilot/state/zalo-z04/codex
```

### Step 2 — Write failing tests (TDD)

Create `tests/unit/test_zalo_category_queue.py`:

- `test_build_options_numbers_active_categories_in_order`
- `test_resolve_number_selects_active_queue_item`
- `test_invalid_number_reprompts`
- `test_expired_queue_rejected`
- `test_duplicate_tx_id_not_appended_twice`
- `test_shift_queue_after_confirm`

Create `tests/integration/test_zalo_category_flow.py`:

- `test_send_category_picker_creates_bot_state_queue`
- `test_reply_one_confirms_transaction_category`
- `test_reply_one_is_tenant_scoped`
- `test_two_transactions_queue_and_confirm_sequentially`
- `test_duplicate_sepay_retry_does_not_send_second_picker`
- `test_no_active_categories_sends_clear_message_and_does_not_crash`

Extend Z03 route tests:

- numeric reply delegates to category resolver when pending state exists.

Run:

```bash
pytest tests/unit/test_zalo_category_queue.py tests/integration/test_zalo_category_flow.py tests/integration/test_zalo_webhook_route.py -v
```

Expected: new tests fail before implementation.

### Step 3 — Add bot-state helper

Add a focused service module if none exists, e.g. `core/services/bot_state.py`:

- `get_state(user_id) -> dict | None`
- `set_state(user_id, step, payload) -> None`
- `clear_state(user_id) -> None`
- Use `INSERT ... ON CONFLICT (user_id) DO UPDATE`.
- Keep JSON serializable payloads only.

### Step 4 — Implement category handler

Create `core/handlers/categorize.py`:

- `send_category_picker(user_id: int, tx_id: int) -> None`
- `handle_numbered_category_reply(user_id: int, text: str) -> None`
- Query active categories for transaction month and user.
- Build `Markup` rows from parent categories.
- Store queue in `bot_state.payload`.
- Confirm with `UPDATE transactions SET category_id=$1, confirmed=TRUE WHERE id=$2 AND user_id=$3`.
- Shift queue and send next picker if present.

TTL: 30 minutes from first item; renew on append. Expired state is handled lazily on reply.

### Step 5 — Wire SePay persistence

Modify `markets/vn/capture/sepay_webhook.py` minimally:

- Make `_persist(...)` return inserted transaction id or `None` on duplicate conflict.
- After `_persist`, if tx id is not `None`, call `send_category_picker(user_id, tx_id)`.
- Preserve current silent-200 behavior for bad token and parse failures.

### Step 6 — Wire webhook numeric reply

Update Z03 handler module:

- If text is numeric, call `handle_numbered_category_reply(user_id, text)`.
- If no pending queue, send “Không có giao dịch nào cần phân loại.”

### Step 7 — Local verification

```bash
ruff check core/ markets/ tests/
black --check core/ markets/ tests/
mypy core/ markets/
lint-imports
pytest tests/unit/test_zalo_category_queue.py tests/integration/test_zalo_category_flow.py tests/integration/test_sepay_webhook.py tests/integration/test_zalo_webhook_route.py -v
pytest tests/ -v
```

## TDD gate

Tests must fail before Step 3 and pass by Step 7. Do not skip integration tests.

## Atomic commit plan

```bash
git add tests/unit/test_zalo_category_queue.py tests/integration/test_zalo_category_flow.py tests/integration/test_zalo_webhook_route.py
git commit -m "test(zalo): pin numbered category flow"

git add core/services/bot_state.py core/handlers/categorize.py
git commit -m "feat(zalo): add category queue handler"

git add markets/vn/capture/sepay_webhook.py core/handlers/zalo_webhook.py
git commit -m "feat(zalo): wire sepay transactions to category replies"
```

## Inline Codex review

Run `codex review --base main` up to 3 rounds, save `.autopilot/state/zalo-z04/codex/round-*.txt`, require 2 consecutive clean rounds.

## Auto squash-merge gate

After local verification is green and Codex has 2 consecutive clean rounds, squash this branch into local `main`:

```bash
git branch --show-current                         # MUST be codex/zalo-z04-category-flow
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main
git merge --no-commit --no-ff codex/zalo-z04-category-flow
git merge --abort

git merge --squash codex/zalo-z04-category-flow
git commit -m "feat(zalo): add numbered category flow"
git branch -D codex/zalo-z04-category-flow

ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v
```

If any command fails, HALT and preserve branch state. Do not push to origin.

## Circuit breakers

1. Pre-flight regression.
2. DEPENDENCY_MISSING.
3. TDD_ORACLE_VIOLATED.
4. VERIFY_REGRESSION.
5. ARCH_FINDING.
6. SECURITY_FINDING.
7. TENANT_LEAK — any path can update another user's transaction.
8. DUPLICATE_PICKER — duplicate SePay retry sends duplicate picker.
9. TYPE_IGNORE_PROPOSED.
10. RECURRING_FINDING.
11. MAX_ROUNDS.
12. POLICY_MISMATCH — any attempt to push remote or merge without 2× clean review.

## Halt report

Emit template §3.14.

## Final report

Emit COMPLETE-style report with local squash commit SHA, branch deletion, `Push origin/main: NOT RUN`, final verification counts, and Codex artifacts.

Begin with Pre-flight, then Step 1.
