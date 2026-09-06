# Task: Remediate audit findings (My Money Went Bot) — WRITE mode, TDD-first, phased

You are working in `/Users/maingocanh/Projects/My Money Went Bot` on a personal-finance
Telegram bot: a FastAPI service that receives SePay bank webhooks + Telegram updates on a
single `/webhook` endpoint and records every transaction into Google Sheets (gspread),
deployed on Railway. NO prior conversation context. This prompt is self-contained.

Mode: REMEDIATE — **WRITE**. You will fix audit findings in severity order (P0 first),
using TDD-first discipline: write the failing test, then the fix, then verify green. Work in
phases. Commit after each phase passes. Then STOP_AT_SUMMARY.

---

## Remediation risk header (REQUIRED — read before anything else)

```
Authority:        WRITE  (create/modify source + test files, run git commit)
Source mutation:  PERMITTED within scope (fix findings only — no feature work)
Network:          FORBIDDEN to real services (no live Google Sheets / Telegram / SePay calls)
Input:            docs/audits/audit-<YYYY-MM-DD>.md  (the audit to remediate)
Deliverable:      Fixed code + tests + docs/audits/remediation-<YYYY-MM-DD>.md
Exit condition:   STOP_AT_SUMMARY  (all phases done + summary emitted)
Feature work:     OUT OF SCOPE — this is bug/security fix only
```

Rule: this is a targeted remediation, not a feature sprint. You have authority to modify source
and test files **only to fix findings documented in the audit report**. You have NO authority to
add new features, refactor beyond what's needed for the fix, or make "while I'm here" improvements.
When a finding requires a large refactor (e.g. "split sheets.py"), implement the **minimum viable
fix** that closes the security/correctness gap, and leave a `# TODO(audit): ...` comment for the
full refactor.

---

## Context

- Single-tenant bot: one owner identified by `CHAT_ID`. All money data lives in one Google
  Sheet (tabs defined in `config.py` → `class SHEETS`).
- `/webhook` is **public** (Railway URL) and multiplexes two payload shapes: Telegram updates
  (`"update_id"` present) and SePay bank webhooks (everything else).
- Tests are pytest unit tests using an in-memory gspread fake (`tests/conftest.py`).
- The audit report (`docs/audits/audit-<YYYY-MM-DD>.md`) contains prioritized findings with
  `file:line` anchors, code excerpts, and recommended fixes. Those are your work items.

---

## Required reading (READ FIRST, in this order)

1. **The audit report** — `docs/audits/audit-<YYYY-MM-DD>.md` (use the most recent one).
   Extract the full list of P0/P1/P2 findings and their recommended fixes. This is your
   backlog. Each finding has a `[P0|P1|P2]` severity, location, evidence, impact, and
   recommended fix.

2. **The existing test infrastructure** — `tests/conftest.py`, `pytest.ini`, and scan
   `tests/unit/*.py` to understand the `FakeSpreadsheet` / `FakeWorksheet` pattern, how
   Telegram calls are stubbed, and what env vars are required.

3. **The files cited in each finding** — read the actual current code at the cited locations
   (line numbers may have shifted if prior remediation already occurred). Verify each finding
   is still valid before fixing it. If a finding has already been fixed, note it as
   `ALREADY_FIXED` in the remediation report and skip.

4. **config.py** — the env var surface. Understand what secrets exist and how they're loaded.

5. **.env.example** — document any new env vars you add here.

---

## Pre-flight gate (run before any code changes; all must pass)

```bash
cd "/Users/maingocanh/Projects/My Money Went Bot"
git status                       # MUST be clean — do NOT remediate on a dirty tree
git branch --show-current        # expected: main
git rev-parse HEAD               # RECORD this SHA — remediation starts from here
python -m pytest -q 2>&1 | tail -20   # RECORD the baseline — ALL must pass before you begin
```

**Hard gates:**
- If the working tree is dirty → HALT. Do not start remediation on uncommitted changes.
- If any existing test fails → HALT. Baseline must be green before remediation begins.
- If `git` or `pytest` is unavailable → HALT and report.
- RECORD the `HEAD` SHA, the test baseline count, and the audit report filename in the
  remediation report header.

---

## Anti-patterns (NEVER do)

- **Feature work disguised as a fix.** If a finding says "add HMAC validation", add HMAC
  validation — don't also refactor the entire webhook dispatcher "while you're there."
- **Fixing without a test.** Every fix MUST have a corresponding test that would have FAILED
  before the fix and PASSES after. The only exception is pure config/docs changes (e.g.
  updating `.env.example`).
- **Breaking existing tests.** If your fix causes an existing test to fail, you MUST update
  that test to work with the new behavior — but verify the test was testing the OLD (insecure/
  broken) behavior, not a legitimate contract. If unsure → add a `# NOTE(audit):` comment
  explaining the change.
- **Skipping a P0.** All P0 findings MUST be addressed in Phase 1. If a P0 fix is genuinely
  impossible without founder input → circuit-break with AMBIGUOUS_FIX.
- **`git push`** — commit locally only. Do not push. The founder reviews before push.
- **Running the bot against live services.** No Google Sheets / Telegram / SePay calls.
- **Large refactors.** If a finding requires splitting a 1800-line file, do the MINIMUM fix
  that closes the gap (e.g. add validation at the entry point) and leave a
  `# TODO(audit): full refactor — see remediation-<date>.md` comment.

---

## Phased execution plan

### Phase 1 — P0 fixes (security-critical)

For each P0 finding in the audit:

1. **Verify** the finding is still present at the cited location (code may have shifted).
2. **Write the failing test(s)** that demonstrate the vulnerability:
   - For auth bypass: test that unauthenticated/wrong-auth requests are rejected.
   - For data corruption: test that the corrupt scenario no longer produces bad data.
3. **Implement the fix** per the audit's recommended fix.
4. **Run `python -m pytest -q`** — all tests (old + new) must pass.
5. **Record** the finding as FIXED in the remediation report with the test file:line reference.

After ALL P0 findings are fixed and green:
```bash
git add -A
git commit -m "fix(security): remediate P0 audit findings

What changed:
<list each P0 finding title + file changed>

Why:
Security audit dated <YYYY-MM-DD> identified these as P0 (money loss,
unauthenticated control, or secret exposure).

Tracking: audit-<YYYY-MM-DD>.md
"
```

### Phase 2 — P1 fixes (correctness / bounded exploits)

Same TDD workflow as Phase 1, but for P1 findings.

**Special handling for money-related P1 fixes:**
- If the fix involves changing `float` → `Decimal`/`int` across 50+ call sites, implement
  ONLY the critical path (the write + immediate read) and leave a `# TODO(audit): propagate
  Decimal to remaining N call sites` comment. Document this as PARTIAL_FIX.
- Idempotency fixes: if the audit recommends durable dedup, implement the minimum viable
  version (e.g. a dedicated sheet tab) rather than an external database.

After ALL P1 findings are fixed and green:
```bash
git add -A
git commit -m "fix(money): remediate P1 audit findings

What changed:
<list each P1 finding title + file changed>

Why:
Security audit dated <YYYY-MM-DD> identified these as P1 (correctness bug
or structural issue approaching P0).

Tracking: audit-<YYYY-MM-DD>.md
"
```

### Phase 3 — P2 fixes (maintainability / hardening)

Same TDD workflow. P2 fixes are lower priority but still valuable.

**Prioritize within P2:**
1. Fixes that add test coverage for previously untested security boundaries.
2. CI/lint/type-check setup (`.github/workflows/ci.yml`, `ruff.toml`).
3. Dead code isolation (move, don't delete — create `handlers/experimental.py`).
4. Naming/documentation improvements.

After ALL P2 findings are fixed and green:
```bash
git add -A
git commit -m "chore(quality): remediate P2 audit findings

What changed:
<list each P2 finding title + file changed>

Why:
Security audit dated <YYYY-MM-DD> identified these as P2 (maintainability,
missing tests, code smells).

Tracking: audit-<YYYY-MM-DD>.md
"
```

---

## Test discipline

Every fix MUST follow this cycle:

```
1. Write test(s) that FAIL demonstrating the bug/vulnerability
2. Run pytest → confirm the new test(s) FAIL (red)
3. Implement the fix
4. Run pytest → confirm ALL tests pass (green), including new ones
5. If any OLD test fails → investigate:
   a. Was it testing insecure/broken behavior? → Update the test + add NOTE comment
   b. Was it testing a legitimate contract you broke? → Fix YOUR code, not the test
```

**Test naming convention:**
- Security tests: `tests/unit/test_webhook_auth.py`, `tests/unit/test_callback_validation.py`
- Money tests: `tests/unit/test_idempotency_durable.py`
- Use descriptive names: `test_tg_update_without_secret_is_rejected`

**Env vars in tests:** Any new env var MUST be added to `tests/conftest.py`'s
`os.environ.setdefault()` block with a test-mode dummy value. The pattern:
```python
os.environ.setdefault("NEW_SECRET", "test_dummy_value")
```

---

## Config & env var changes

When adding new required env vars:

1. Add to `config.py` with a clear comment and startup validation.
2. Add to `.env.example` with setup instructions.
3. Add to `tests/conftest.py` env defaults.
4. Add to `.github/workflows/ci.yml` env block (if CI exists).
5. **Use "test:" prefix detection** for test-mode bypass:
   ```python
   if not BOT_TOKEN.startswith("test:"):
       # production validation — fail if secret is empty
   ```

---

## Evidence gate (the remediation's correctness oracle)

A fix is only complete if ALL of these hold:

1. The finding's vulnerability/bug is **no longer reproducible** (verified by a test).
2. The fix is **minimal** — no unrelated changes bundled in.
3. All tests pass — both old baseline AND new tests.
4. The fix is documented in the remediation report with test references.
5. Any env var changes are documented in `.env.example`.

---

## Remediation report format

Write `docs/audits/remediation-<YYYY-MM-DD>.md` with this structure:

```markdown
# Remediation Report — <YYYY-MM-DD>

## Header
- **Audit remediated:** `docs/audits/audit-<YYYY-MM-DD>.md`
- **Starting HEAD:** `<SHA>`
- **Ending HEAD:** `<SHA after final commit>`
- **Starting test baseline:** `<N> passed`
- **Ending test count:** `<N> passed`

## Findings Summary

| # | Severity | Title | Status | Test Reference |
|---|----------|-------|--------|----------------|
| 1 | P0 | <title> | FIXED / ALREADY_FIXED / PARTIAL_FIX / DEFERRED | `tests/unit/test_xxx.py:LL` |
| ... | ... | ... | ... | ... |

## Phase 1 — P0 Fixes
### <Finding title>
- **Status:** FIXED
- **What changed:** <files modified, what was added/removed>
- **Test:** `tests/unit/test_xxx.py::test_name` (was RED before fix, GREEN after)
- **Notes:** <any caveats, env var changes needed>

## Phase 2 — P1 Fixes
### ...

## Phase 3 — P2 Fixes
### ...

## Deferred Items
| Finding | Reason | TODO Location |
|---------|--------|---------------|
| <title> | <why deferred> | `file.py:LL # TODO(audit): ...` |

## Deployment Checklist
- [ ] Set `NEW_ENV_VAR` in Railway dashboard
- [ ] Re-register Telegram webhook with secret_token
- [ ] Update cron job URLs
- [ ] ...
```

---

## Circuit breakers (HALT and write a halt report; do not push through)

1. **TEST_REGRESSION** — a fix causes 3+ unrelated existing tests to fail and you can't
   determine if they tested insecure behavior or a legitimate contract. HALT and ask.
2. **AMBIGUOUS_FIX** — the audit's recommended fix is genuinely ambiguous or requires founder
   input on a design decision (e.g. "should we block or just log?"). Record as DEFERRED with
   the specific question.
3. **SCOPE_CREEP** — you are about to modify a file not cited in any finding, or add a feature
   not in the audit. STOP. If the modification is genuinely necessary for the fix, add a
   `# NOTE(audit): required for finding #N` comment and proceed. Otherwise, HALT.
4. **DESTRUCTIVE_NETWORK_ACTION** — any step would call a live Google/Telegram/SePay endpoint,
   or `git push`. HALT.
5. **TOOL_ERROR_TWICE** — same tool fails twice in a row. HALT with the error.
6. **CONTEXT_BUDGET >70%** — flush all in-progress work, commit what's green, and emit a halt
   report noting which phases are complete.

---

## Halt report template

```
HALT — remediation circuit broken.

Phase:   <e.g. Phase 1 P0 fixes>
Finding: <the finding being worked on>
Trigger: <one of the 6 breakers>
HEAD:    <SHA>

Detail:
<error output OR the condition>

State:
- Report file: docs/audits/remediation-<date>.md
- Phases complete: <list>
- Phases remaining: <list>
- Tests: <N passed, M failed>

Requesting founder input on:
<specific question>
```

---

## Final summary (emit verbatim on success)

```
═══════════════════════════════════════════════════════
REMEDIATION — My Money Went Bot — COMPLETE
═══════════════════════════════════════════════════════

Audit remediated:  docs/audits/audit-<YYYY-MM-DD>.md
Starting HEAD:     <SHA>
Ending HEAD:       <SHA after final commit>
Source files modified: <count>
Test files added/modified: <count>

Tests:
  Before: <N> passed
  After:  <M> passed (+<delta> new)

Findings:
  FIXED: <count>   PARTIAL_FIX: <count>   DEFERRED: <count>
  ALREADY_FIXED: <count>

Commits:
  1. fix(security): remediate P0 audit findings
  2. fix(money): remediate P1 audit findings
  3. chore(quality): remediate P2 audit findings

Deployment actions required:
  1. <env var to set>
  2. <webhook to re-register>
  3. <cron URLs to update>

Next step: founder reviews commits, pushes to main, deploys to Railway,
and performs the deployment checklist above.
═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then read the audit report, then Phase 1.
