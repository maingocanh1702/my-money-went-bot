# Autopilot — Zalo Z03 webhook route

Task: Zalo Z03 — add `/zalo/webhook` parser, auth gate, and `/start` command routing.

You are working in `/Users/maingocanh/Projects/MyMoneyWent` on a multi-tenant Vietnamese personal finance bot. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `codex/zalo-z03-webhook`, inline Codex review with ≤3 fix rounds, then auto squash-merge to local `main` only. Pause ONLY on circuit-breaker conditions. Do not push to origin.

```
Risk tier:          P1
Merge policy:       founder_override_auto_squash_local
Autopilot maturity: mature
Codex review:       2x_consecutive_clean
```

## Context (NOT for execution, just background)

The implementation plan requires webhook signature and payload behavior to be live-fixture-gated. This phase may implement route structure and tests, but must not claim production-ready signature validation unless a sanitized real webhook fixture exists and passes.

## Scope discipline

**Positive scope:**
- Add Zalo webhook parser helpers.
- Add `POST /zalo/webhook` route in `main.py`.
- Gate route with `ZALO_ENABLED` and `ZALO_INTERACTIVE`.
- Verify Zalo signature against sanitized real fixture if present.
- Route `/start` to `core.handlers.start.handle_start(channel_type="zalo", channel_user_id=sender.id, channel_chat_id=sender.id)`.
- Return Telegram-only fallback for `/today`, `/report`, `/accounts` if core builders do not exist.
- Route numeric replies to a placeholder function only if Z04 interface exists; otherwise return “Không có giao dịch nào cần phân loại”.

**Negative scope:**
- Do not implement category queue in this prompt.
- Do not call legacy report handlers.
- Do not add unofficial personal-account automation.
- Do not enable production interactive behavior without fixture-backed signature validation.
- Do not alter Telegram `/webhook` behavior except adding a separate `/zalo/webhook`.

**Out-of-scope but documented:**
- Full numbered category handling ships in Z04.
- Core report builders are future tech debt if absent.

## Required reading

1. `docs/implementation-plan-zalo-channel-core.md` — Verification Status and Key Changes §3.
2. `main.py` — FastAPI route style, background task pattern, startup lifecycle.
3. `core/handlers/start.py` — `/start` handler signature after Z01.
4. `core/messenger/send.py` and `core/messenger/zalo.py` — send fallback behavior after Z02.
5. `tests/integration/test_start_handler.py` and `tests/integration/test_app_startup.py`.
6. `tests/fixtures/` — fixture naming conventions.

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

ALL must pass. Confirm Z01 and Z02 are merged. If `core/messenger/zalo.py` or `channel_chat_id` support is missing, HALT with `DEPENDENCY_MISSING`.

## Anti-patterns (NEVER do)

* `git push --force`.
* Add `# type: ignore`.
* Push to origin/main — founder performs the final push after all Zalo phases pass.
* Invent a fake “real” signature fixture — if no real fixture exists, keep production signature behavior guarded and report fixture gap.
* Call deprecated `handlers/reports.py` or Google Sheets report builders from Zalo route.
* Accept group/non-text events.
* Fail open when `ZALO_ENABLED` or `ZALO_INTERACTIVE` is false.
* Log raw financial payloads or secrets.

## Numbered steps

### Step 1 — Branch + state

```bash
git checkout -b codex/zalo-z03-webhook
git rev-parse HEAD > /tmp/zalo-z03-base-sha.txt
mkdir -p .autopilot/state/zalo-z03/codex
```

### Step 2 — Fixture gate

Look for `tests/fixtures/zalo/user_send_text_webhook.json` and companion metadata documenting headers/signature. If missing:

- Continue implementing parser and route with synthetic unit fixtures only if signature verification remains disabled for production with a clear `LIVE_FIXTURE_REQUIRED` response/log when `ZALO_INTERACTIVE=true`.
- Add a test proving production interactive mode refuses to run without a real fixture-backed verifier.
- Add `LIVE_FIXTURE_MISSING` to final report decisions.

If fixture exists, use it for signature parser tests.

### Step 3 — Write failing tests (TDD)

Create `tests/unit/test_zalo_webhook_parser.py`:

- `test_parse_user_send_text_extracts_sender_and_text`
- `test_parse_ignores_non_text_event`
- `test_verify_signature_with_real_fixture_or_blocks_without_fixture`
- `test_missing_sender_rejected`

Create `tests/integration/test_zalo_webhook_route.py`:

- `test_zalo_webhook_disabled_returns_ok_without_processing`
- `test_zalo_webhook_bad_signature_rejected_or_fixture_required`
- `test_zalo_start_creates_user`
- `test_zalo_report_commands_return_core_or_telegram_only_fallback`
- `test_zalo_numeric_reply_without_pending_state_returns_no_pending_message`
- `test_zalo_webhook_does_not_accept_group_or_non_text_event`

Run:

```bash
pytest tests/unit/test_zalo_webhook_parser.py tests/integration/test_zalo_webhook_route.py -v
```

Expected: new tests fail before implementation.

### Step 4 — Implement parser helpers

Prefer a small module if `main.py` would become noisy, e.g. `core/handlers/zalo_webhook.py`:

- `parse_zalo_event(body: dict) -> ParsedZaloEvent | None`
- `verify_zalo_signature(raw_body: bytes, headers: Mapping[str, str], settings) -> bool`
- `is_zalo_interactive_enabled() -> bool`
- `handle_zalo_text_event(event) -> None`

Signature formula must be fixture-driven. If no real fixture, implement verifier as explicit “unverified” blocker for production mode rather than accepting all signatures.

### Step 5 — Wire FastAPI route

Add `POST /zalo/webhook` in `main.py`:

- Read raw body before JSON parse for signature verification.
- Return 200 with `{"ok": true}` for disabled mode and ignored event types.
- Reject invalid signature with 401 only when verifier is fixture-backed.
- For `/start`, call `handle_start(...)`.
- Send help/fallback via `core.messenger.send`.

### Step 6 — Local verification

```bash
ruff check main.py core/ tests/
black --check main.py core/ tests/
mypy core/
lint-imports
pytest tests/unit/test_zalo_webhook_parser.py tests/integration/test_zalo_webhook_route.py -v
pytest tests/ -v
```

## TDD gate

Tests must fail before Step 4 and pass by Step 6. Do not skip tests because fixture is missing; encode the missing fixture as explicit safe behavior.

## Atomic commit plan

```bash
git add tests/unit/test_zalo_webhook_parser.py tests/integration/test_zalo_webhook_route.py tests/fixtures/zalo/
git commit -m "test(zalo): pin webhook parsing and route gates"

git add core/handlers/zalo_webhook.py main.py
git commit -m "feat(zalo): add guarded webhook route"
```

## Inline Codex review

Run `codex review --base main` up to 3 rounds, save `.autopilot/state/zalo-z03/codex/round-*.txt`, require 2 consecutive clean rounds.

## Auto squash-merge gate

After local verification is green and Codex has 2 consecutive clean rounds, squash this branch into local `main`:

```bash
git branch --show-current                         # MUST be codex/zalo-z03-webhook
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main
git merge --no-commit --no-ff codex/zalo-z03-webhook
git merge --abort

git merge --squash codex/zalo-z03-webhook
git commit -m "feat(zalo): add guarded webhook route"
git branch -D codex/zalo-z03-webhook

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
4. LIVE_FIXTURE_CONTRADICTION — real fixture disproves planned payload/signature assumptions.
5. SECURITY_FINDING.
6. ARCH_FINDING.
7. VERIFY_REGRESSION.
8. TYPE_IGNORE_PROPOSED.
9. RECURRING_FINDING.
10. MAX_ROUNDS.
11. Tool error twice.
12. POLICY_MISMATCH — any attempt to push remote or merge without 2× clean review.

## Halt report

Emit template §3.14.

## Final report

Emit COMPLETE-style report with local squash commit SHA, branch deletion, `Push origin/main: NOT RUN`, final verification counts, Codex artifacts, and whether live fixture was present.

Begin with Pre-flight, then Step 1.
