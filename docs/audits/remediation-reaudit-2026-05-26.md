# Re-audit Remediation Report — 2026-05-26

## Header
- **Re-audit remediated:** `docs/audits/re-audit-2026-05-26.md`
- **Starting HEAD:** `c867419fe2ae26553d8328b47b06cf45a89dbf23`
- **Ending HEAD:** `c867419fe2ae26553d8328b47b06cf45a89dbf23`
- **Starting working tree:** dirty. Modified: `.env.example`, `config.py`, `handlers/accounts.py`, `handlers/sepay.py`, `main.py`, `sheets.py`, `tests/conftest.py`, `tests/unit/test_phase1_sepay_flow.py`, `tests/unit/test_sepay_income_no_picker.py`. Untracked: `.github/`, `handlers/experimental.py`, `ruff.toml`, `tests/unit/test_callback_validation.py`, `tests/unit/test_webhook_auth.py`.
- **Starting tests:** `113 passed in 0.59s` (`python -m pytest -q`)
- **Ending tests:** `120 passed in 0.90s` (`python -m pytest -q`)
- **Commit status:** blocked by local `.git` write permissions. `git add -A && git commit -m "fix(money): recover SePay ref reservations after append failure"` failed with `fatal: Unable to create .../.git/index.lock: Operation not permitted`; `touch .git/codex-write-test` also failed with `Operation not permitted`.

## Findings Summary

| Severity | Finding | Status | Test / Evidence |
|---|---|---|---|
| P0 | Durable ref reservation can permanently drop a real transaction after append failure | FIXED | `tests/unit/test_phase1_sepay_flow.py::test_sepay_retry_after_append_failure_processes_ref` |
| P1 | Transaction idempotency remaining race risk | PARTIAL_FIX | `tests/unit/test_webhook_auth.py::test_tx_exists_fails_closed_when_transaction_lookup_errors`; residual Google Sheets non-atomic race documented below |
| P1 | Currency floats | PARTIAL_FIX | `tests/unit/test_phase1_sepay_flow.py::test_sepay_vnd_amount_preserves_integer_precision`; broader report/account float aggregation deferred |
| P1 | Callback malformed id | FIXED | `tests/unit/test_callback_validation.py::test_no_callback_id_no_crash` |
| P2 | Public-boundary and quality-gate test gaps | FIXED | `tests/unit/test_webhook_auth.py::test_webhook_rejects_missing_or_wrong_tg_secret_before_processing`; CI/Ruff files present, but local Ruff unavailable |
| P2 | Stale security docs | FIXED | `README.md`, `README.vi.md`, `.env.example` now describe mandatory secrets and Telegram `secret_token` setup |

## Changes By Phase

### Phase 1 — P0
- **Status:** FIXED
- **What changed:** `Processed Refs` now treats only `committed` refs as duplicates. Recoverable states (`processing`, `reserved`, `failed`) are reclaimed for retry instead of permanently suppressing the ref. SePay append now marks refs `failed` when `append_transaction()` raises after reservation and marks them `committed` only after a successful transaction write.
- **Tests:** Added a red-first append-failure retry regression, committed-ref dedupe coverage, and failed-ref recovery coverage. Focused tests and full suite passed.
- **Residual risk:** Google Sheets still cannot provide true cross-worker atomic uniqueness. The current state machine prevents permanent loss after append failure and fails closed on unknown idempotency state, but two concurrent workers can still race in the read-then-write reservation window.

### Phase 2 — P1/P2 Correctness And Coverage
- **Status:** PARTIAL_FIX for idempotency and currency; FIXED for callback malformed id and public-boundary coverage.
- **What changed:** Missing callback `id` is rejected before `answer_callback`. Route-level Telegram webhook-secret coverage now posts to `/webhook` and proves missing/wrong headers do not invoke `_process`. Idempotency lookup failure coverage proves sheet read errors fail closed. SePay VND amounts parse via `Decimal` and are written as exact integer units on the webhook critical path.
- **Tests:** `test_no_callback_id_no_crash`, `test_webhook_rejects_missing_or_wrong_tg_secret_before_processing`, `test_tx_exists_fails_closed_when_transaction_lookup_errors`, `test_sepay_vnd_amount_preserves_integer_precision`.
- **Residual risk:** Reporting, account balance parsing, ledger writes, and foreign-currency paths still use `float` in several call sites. A full `Decimal`/minor-unit migration is deferred because it is a broader data-model change than the bounded re-audit fix.

### Phase 3 — Documentation
- **Status:** FIXED
- **What changed:** English and Vietnamese READMEs no longer describe webhook auth as optional. Deployment instructions now require `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, and `CRON_SECRET`, and Telegram webhook registration includes `secret_token`. `.env.example` was already consistent with the mandatory secret model.
- **Tests:** `python -m pytest -q` passed after docs updates.
- **Residual risk:** None for the stale security-doc finding.

## Deferred Items

| Finding | Reason | Follow-up |
|---|---|---|
| Transaction idempotency remaining race risk | Google Sheets does not offer an atomic unique insert primitive for `Processed Refs`; current remediation uses the strongest recoverable state behavior available in the existing architecture. | Move idempotency keys to a store with uniqueness/transaction semantics, or add an external lock/queue so only one worker processes a SePay ref at a time. |
| Currency floats outside SePay VND critical path | Whole-codebase numeric migration would touch reports, account caches, ledger balances, and sheet schema/display behavior. | Introduce canonical minor units or `Decimal` by currency, migrate read/write helpers first, then update reports/accounts/ledger call sites under dedicated coverage. |

## Deployment Checklist
- [ ] Ensure `SEPAY_SECRET` is set in Railway.
- [ ] Ensure `TELEGRAM_WEBHOOK_SECRET` is set in Railway.
- [ ] Ensure Telegram webhook is registered with the same secret token.
- [ ] Ensure `CRON_SECRET` is set and cron callers include it.
