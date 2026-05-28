# Autopilot — Zalo Z02 messenger sender

Task: Zalo Z02 — implement `core.messenger.zalo.ZaloSender` with tests.

You are working in `/Users/maingocanh/Projects/MyMoneyWent` on a multi-tenant Vietnamese personal finance bot. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `codex/zalo-z02-sender`, inline Codex review with ≤3 fix rounds, then auto squash-merge to local `main` only. Pause ONLY on circuit-breaker conditions. Do not push to origin.

```
Risk tier:          P1
Merge policy:       founder_override_auto_squash_local
Autopilot maturity: mature
Codex review:       2x_consecutive_clean
```

## Context (NOT for execution, just background)

Zalo must be a first-class `core.messenger` adapter, not a parallel `zalo_api.py` helper. This phase depends on Z01 being merged because sender routing reads `users.channel_chat_id`.

## Scope discipline

**Positive scope:**
- Add `core/messenger/zalo.py`.
- Register `ZaloSender` under `channel_type='zalo'`.
- Render `SendPayload` as plain text.
- Render callback markup as numbered text options.
- Render URL buttons as plain links.
- Add configurable chunk limit via `ZALO_TEXT_LIMIT`, default 2000.
- Implement optional 401 refresh behavior guarded by `ZALO_AUTO_REFRESH`.
- Add unit and contract tests.

**Negative scope:**
- Do not add `/zalo/webhook`.
- Do not add category state handling.
- Do not persist OAuth tokens in DB.
- Do not call real Zalo network in tests.
- Do not modify Telegram sender behavior except shared contract tests.

**Out-of-scope but documented:**
- Persistent token store and scheduled refresh are V2 tech debt.

## Required reading

1. `docs/implementation-plan-zalo-channel-core.md` — Verification Status and Key Changes §2.
2. `core/messenger/base.py` — `BaseSender`, `SendPayload`, `Markup`, validation.
3. `core/messenger/telegram.py` — adapter pattern and tests.
4. `core/messenger/__init__.py` — side-effect registration import pattern.
5. `core/messenger/send.py` — channel dispatch.
6. `tests/unit/test_messenger_telegram_mock.py` — unit style with mocked `httpx`.
7. `tests/contract/test_messenger_contract.py` — extend adapter contract list.
8. `docs/autopilot/prompts/zalo-channel-core-z01-db-user-autopilot.md` — dependency contract.

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

ALL must pass. Confirm Z01 is merged by checking that `users.channel_chat_id` appears in migrations and `core/services/user_svc.py`. If not, HALT with `DEPENDENCY_MISSING`.

## Anti-patterns (NEVER do)

* `git push --force`.
* Add `# type: ignore`.
* Push to origin/main — founder performs the final push after all Zalo phases pass.
* Hit real Zalo API from tests — use mocked `httpx.AsyncClient`.
* Store refreshed tokens only in memory and pretend production is solved — log operator action and keep V2 persistent store out of scope.
* Treat Markdown as supported in Zalo — Zalo v1 sender emits plain text.
* Hardcode 640 or 2000 without env override — use `ZALO_TEXT_LIMIT`.

## Numbered steps

### Step 1 — Branch + state

```bash
git checkout -b codex/zalo-z02-sender
git rev-parse HEAD > /tmp/zalo-z02-base-sha.txt
mkdir -p .autopilot/state/zalo-z02/codex
```

### Step 2 — Write failing tests (TDD)

Create `tests/unit/test_messenger_zalo_mock.py`:

- `test_send_calls_zalo_message_cs_with_plain_text`
- `test_send_resolves_channel_chat_id_before_channel_user_id`
- `test_markup_callback_buttons_render_numbered_options`
- `test_markup_url_buttons_render_plain_links_not_numbered`
- `test_chunks_text_using_configured_limit`
- `test_zalo_rejects_empty_access_token`
- `test_401_without_auto_refresh_logs_and_raises`
- `test_401_with_auto_refresh_calls_oauth_and_retries_once`

Extend `tests/contract/test_messenger_contract.py` to include Zalo sender with mocked transport.

Run:

```bash
pytest tests/unit/test_messenger_zalo_mock.py tests/contract/test_messenger_contract.py -v
```

Expected: new tests fail before implementation.

### Step 3 — Implement `core/messenger/zalo.py`

Implement:

- `ZaloSender(BaseSender)` with `channel_type = "zalo"`.
- Constructor reads explicit `access_token`, `refresh_token`, `app_id`, `secret_key`, optional `http_client`, `api_base`, `oauth_base`, `text_limit`, `auto_refresh`.
- Factory reads env vars.
- `_resolve_recipient(user_id: int) -> str` reads `channel_chat_id`, fallback `channel_user_id`.
- `_resolve_text()` mirrors Telegram text-key behavior via `core.messenger.i18n.t`.
- `_render_plain_text(payload)` strips simple Markdown markers and appends rendered markup.
- `_chunk_text(text)` splits by paragraph/line where possible.
- `send()` posts each chunk to `/v3.0/oa/message/cs` with header `access_token`.
- On 401 and `auto_refresh=True`, refresh once using form body to `/v4/oa/access_token`, retry once, and log critical operator action if new refresh token is returned.

Do not add DB token persistence.

### Step 4 — Register adapter

- Add side-effect import in `core/messenger/__init__.py`.
- Export `ZaloSender` only if local package pattern supports it; otherwise tests can import `core.messenger.zalo`.

### Step 5 — Local verification

```bash
ruff check core/ tests/
black --check core/ tests/
mypy core/
lint-imports
pytest tests/unit/test_messenger_zalo_mock.py tests/contract/test_messenger_contract.py -v
pytest tests/ -v
```

## TDD gate

Tests must fail before Step 3 and pass by Step 5. If tests pass before implementation, HALT.

## Atomic commit plan

```bash
git add tests/unit/test_messenger_zalo_mock.py tests/contract/test_messenger_contract.py
git commit -m "test(zalo): pin messenger sender behavior"

git add core/messenger/zalo.py core/messenger/__init__.py
git commit -m "feat(zalo): add core messenger sender"
```

## Inline Codex review

Run `codex review --base main` up to 3 rounds, storing outputs in `.autopilot/state/zalo-z02/codex/round-*.txt`. Require 2 consecutive clean rounds.

## Auto squash-merge gate

After local verification is green and Codex has 2 consecutive clean rounds, squash this branch into local `main`:

```bash
git branch --show-current                         # MUST be codex/zalo-z02-sender
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main
git merge --no-commit --no-ff codex/zalo-z02-sender
git merge --abort

git merge --squash codex/zalo-z02-sender
git commit -m "feat(zalo): add core messenger sender"
git branch -D codex/zalo-z02-sender

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
7. TOKEN_REFRESH_AMBIGUITY — implementation needs persistent token store to pass tests.
8. TYPE_IGNORE_PROPOSED.
9. RECURRING_FINDING.
10. MAX_ROUNDS.
11. Tool error twice.
12. POLICY_MISMATCH — any attempt to push remote or merge without 2× clean review.

## Halt report

Emit template §3.14.

## Final report

Emit COMPLETE-style report with local squash commit SHA, branch deletion, `Push origin/main: NOT RUN`, final verification counts, and Codex artifacts.

Begin with Pre-flight, then Step 1.
