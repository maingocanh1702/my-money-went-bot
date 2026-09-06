# Task: Remediate re-audit findings (My Money Went Bot) — WRITE mode, TDD-first

You are working in `/Users/maingocanh/Projects/My Money Went Bot` on a personal-finance
Telegram bot: a FastAPI service that receives SePay bank webhooks + Telegram updates on a
single `/webhook` endpoint and records transactions into Google Sheets.

Mode: REMEDIATE — **WRITE**. Fix every actionable finding in:

`docs/audits/re-audit-2026-05-26.md`

Use TDD discipline: write the failing test first, confirm it fails for the bug, implement the
minimum fix, then verify all tests pass. Commit locally after each completed severity phase.
Do not push.

---

## Authority and limits

```
Authority:        WRITE  (source, tests, docs, remediation report, local git commits)
Scope:            Findings in docs/audits/re-audit-2026-05-26.md only
Network:          FORBIDDEN to real Google Sheets / Telegram / SePay services
Push/deploy:      FORBIDDEN
Deliverable:      Fixed code + tests + docs/audits/remediation-reaudit-2026-05-26.md
Exit condition:   STOP_AT_SUMMARY
```

This is targeted remediation, not feature work. Do not refactor broadly. If a finding suggests a
large design change, implement the smallest robust fix that closes the demonstrated bug, and record
any larger follow-up as deferred in the remediation report.

---

## Required reading

Read these first, in order:

1. `docs/audits/re-audit-2026-05-26.md`
2. `docs/audits/audit-2026-05-26-v1.md` if present, only for historical context
3. Current code at all locations cited by the re-audit
4. `tests/conftest.py`, `pytest.ini`, and relevant `tests/unit/*.py`
5. `README.md`, `README.vi.md`, `.env.example`, `.github/workflows/ci.yml`, and `ruff.toml` if a finding touches docs or quality gates

Treat the re-audit as the source of truth for this run.

---

## Pre-flight gate

Run before code changes:

```bash
cd "/Users/maingocanh/Projects/My Money Went Bot"
git status
git branch --show-current
git rev-parse HEAD
python -m pytest -q
```

Record branch, starting HEAD, working-tree state, and pytest baseline in the remediation report.

Unlike the older remediation prompt, this run may start from a dirty tree because the re-audit
explicitly reports local fixed files and untracked test/CI files. Do not discard or revert those
changes. Work with the current tree as-is. If unrelated uncommitted changes block a fix, halt and
explain exactly which file conflicts with which finding.

---

## Findings to fix

Fix in this order.

### Phase 1 — P0 money correctness

Fix:

`[P0] Durable ref reservation can permanently drop a real transaction after append failure`

Required behavior:

- A SePay ref in a `committed` state must be treated as already processed.
- A SePay ref in a recoverable non-committed state, such as `reserved`, `processing`, `failed`, or stale reservation, must not permanently suppress a retry.
- If transaction append fails after reservation, the ref must be marked recoverable, or the next retry must be able to process it.
- The fix must fail closed for sheet lookup/write errors that would make idempotency unknowable.
- Avoid live network calls. Use existing fake sheet/test infrastructure.

Expected tests:

- Add or update unit tests proving that a reservation followed by append failure does not cause the next delivery of the same ref to be skipped.
- Add or update tests proving that committed refs are still deduped.
- Add or update tests for any stale/failed reservation behavior introduced by the fix.

After Phase 1:

```bash
python -m pytest -q
git add -A
git commit -m "fix(money): recover SePay ref reservations after append failure"
```

### Phase 2 — P1/P2 remaining correctness and coverage gaps

Fix or explicitly defer with concrete justification:

- `P1 Transaction idempotency can fail open or race across workers` remaining partial issue.
- `P1 Currency amounts are parsed, stored, and summed as floats` if still open and feasible within a minimal bounded change.
- `P1 Callback parsing trusts underscore-split payloads before validation` remaining malformed callback `id` issue.
- `P2 Tests cover happy-path unit behavior but miss public-boundary and quality gates` remaining route-level Telegram auth and idempotency failure-path gaps.

Rules:

- For callback validation, handle missing callback `id` before accessing it and add a unit test for missing `id`.
- For Telegram webhook auth coverage, add a route-level test that posts to `/webhook` and verifies missing/wrong `X-Telegram-Bot-Api-Secret-Token` is rejected before processing.
- For float money handling, do not perform a risky whole-codebase numeric rewrite unless the test surface supports it. If a full `Decimal`/minor-unit migration is too broad, implement a minimal critical-path fix or document `PARTIAL_FIX` with exact remaining call sites.
- For worker-level atomic idempotency, if Google Sheets cannot provide true atomic uniqueness, implement the strongest recoverable behavior available in the current architecture and document residual race risk.

After Phase 2:

```bash
python -m pytest -q
git add -A
git commit -m "fix: remediate remaining re-audit findings"
```

### Phase 3 — Documentation

Fix:

`[P2] Security documentation is stale and contradicts the fixed behavior`

Required behavior:

- Update `README.md` and `README.vi.md` so they no longer claim webhook auth is optional or that missing `SEPAY_SECRET` defaults open.
- Document mandatory `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, and `CRON_SECRET` production requirements.
- Document Telegram webhook secret header setup at an operator level.
- Ensure `.env.example` is consistent with the mandatory secret model.

After Phase 3:

```bash
python -m pytest -q
git add -A
git commit -m "docs: update webhook secret deployment guidance"
```

---

## Test discipline

For each code fix:

1. Write the test that demonstrates the current bug.
2. Run the focused test and confirm it fails.
3. Implement the fix.
4. Run the focused test and confirm it passes.
5. Run `python -m pytest -q`.

If a test cannot be made red first because the current tree is already partially fixed, record
`ALREADY_FIXED` with evidence in the remediation report.

Do not call live external services. Use fakes, monkeypatching, and local FastAPI test clients.

---

## Remediation report

Write:

`docs/audits/remediation-reaudit-2026-05-26.md`

Use this structure:

```markdown
# Re-audit Remediation Report — 2026-05-26

## Header
- **Re-audit remediated:** `docs/audits/re-audit-2026-05-26.md`
- **Starting HEAD:** `<sha>`
- **Ending HEAD:** `<sha after final commit>`
- **Starting working tree:** `<clean/dirty summary>`
- **Starting tests:** `<pytest baseline>`
- **Ending tests:** `<pytest final>`

## Findings Summary

| Severity | Finding | Status | Test / Evidence |
|---|---|---|---|
| P0 | Durable ref reservation can permanently drop a real transaction after append failure | FIXED / PARTIAL_FIX / DEFERRED | `tests/...::test_...` |
| P1 | Transaction idempotency remaining race risk | FIXED / PARTIAL_FIX / DEFERRED | ... |
| P1 | Currency floats | FIXED / PARTIAL_FIX / DEFERRED | ... |
| P1 | Callback malformed id | FIXED / PARTIAL_FIX / DEFERRED | ... |
| P2 | Public-boundary and quality-gate test gaps | FIXED / PARTIAL_FIX / DEFERRED | ... |
| P2 | Stale security docs | FIXED | README evidence |

## Changes By Phase

### Phase 1 — P0
- **Status:** ...
- **What changed:** ...
- **Tests:** ...
- **Residual risk:** ...

### Phase 2 — P1/P2 Correctness And Coverage
- ...

### Phase 3 — Documentation
- ...

## Deferred Items

| Finding | Reason | Follow-up |
|---|---|---|

## Deployment Checklist
- [ ] Ensure `SEPAY_SECRET` is set in Railway.
- [ ] Ensure `TELEGRAM_WEBHOOK_SECRET` is set in Railway.
- [ ] Ensure Telegram webhook is registered with the same secret token.
- [ ] Ensure `CRON_SECRET` is set and cron callers include it.
```

---

## Circuit breakers

Halt and report instead of guessing if any of these occur:

- Existing tests fail before changes and the failure is unrelated to the re-audit findings.
- A fix requires choosing a product policy not specified by the audit.
- More than three unrelated existing tests fail after a change.
- A step would call live Google Sheets, Telegram, or SePay.
- A step would require `git push`, force push, reset, or deleting user changes.
- The same command/tool error repeats twice.

---

## Final summary

On success, print:

```
RE-AUDIT REMEDIATION COMPLETE

Re-audit:      docs/audits/re-audit-2026-05-26.md
Report:        docs/audits/remediation-reaudit-2026-05-26.md
Starting HEAD: <sha>
Ending HEAD:   <sha>
Tests:         <pytest result>
Commits:       <list commits created>
Deferred:      <count and titles, or none>

Deployment actions:
1. Set/verify production secrets in Railway.
2. Re-register Telegram webhook with the configured secret token if needed.
3. Deploy only after reviewing the remediation report and commits.
```

Begin with pre-flight, then Phase 1.
