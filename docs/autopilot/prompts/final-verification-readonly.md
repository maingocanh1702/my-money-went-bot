# Task: Final verification pass (My Money Went Bot) — READ-ONLY, GO / NO-GO verdict

You are working in `/Users/maingocanh/Projects/My Money Went Bot` on a personal-finance
Telegram bot: a FastAPI service that receives SePay bank webhooks + Telegram updates on a single
`/webhook` endpoint and records every transaction into Google Sheets (gspread), deployed on
Railway. NO prior conversation context. This prompt is self-contained.

Mode: FINAL VERIFICATION — **READ-ONLY**. Fixes have already been applied (likely uncommitted in
the working tree). Your job is the last gate before commit/deploy: run the project's quality
gate, independently re-review the codebase, and emit a single **GO / NO-GO** verdict report. Then
STOP_AT_REPORT. Pause ONLY on a circuit-breaker condition.

---

## Authority header (REQUIRED — read before anything else)

```
Authority:        READ_ONLY + RUN_TESTS
                  (read any file; run pytest + ruff; write ONLY the report file)
Source mutation:  FORBIDDEN  (no edits, no commits, no merges, no pushes)
Network:          FORBIDDEN to real services (no live Google Sheets / Telegram / SePay calls)
Deliverable:      docs/audits/final-verification-<YYYY-MM-DD>.md  (verdict + remaining issues)
Exit condition:   STOP_AT_REPORT  (report written + final report emitted)
Verdict values:   GO | GO-WITH-CAVEATS | NO-GO
Remediation:      OUT OF SCOPE — if NO-GO, fixing is a separate authorized run
```

Rule: you may **read any file**, **run the test suite + linter** (read-only, uses an in-memory
gspread fake — no network), and **write the single report file** named above (creating
`docs/audits/` if missing; if a same-day file exists, suffix `-v2`, `-v3`, …). You have NO
authority to modify, create (other than the report), rename, or delete any source/test/config
file, to run any mutating git command, or to execute the bot against real credentials. When in
doubt → default to the lower authority: record it in the report and move on. Do NOT "fix while
you're in there" — that corrupts both the verdict and the eventual fix diff.

---

## Context (NOT for execution, just background)

- The founder has already fixed/updated code against prior audits. Reports may exist under
  `docs/audits/` (e.g. an initial audit + a re-audit). The working tree is **expected to be
  dirty** (uncommitted fixes) — that is normal for this pass; you are verifying the working tree
  as-is, before it gets committed.
- The repo now HAS a quality gate that did not exist originally: `.github/workflows/ci.yml` runs
  `ruff check .` then `python -m pytest -q`, with secrets injected as env vars. `ruff.toml`
  selects rule sets `E, F, I, UP` (line-length 120, several ignores). Replicating this gate
  locally IS the core "final test."
- `config.py` now exits at non-test startup if `SEPAY_SECRET` / `TELEGRAM_WEBHOOK_SECRET` /
  `CRON_SECRET` are missing. Tests run in test-mode and don't need them; running the bot does.
- This is single-tenant: one owner = `CHAT_ID`. Money loss / silent data corruption is the
  worst-case outcome, so the verdict bar for money correctness + webhook auth is strict.

Do not infer "why" from code alone. Verify against the working tree at this moment; mark
inferences as inferences.

---

## Scope of this verification

**Positive scope:**

1. **Run the gate** — replicate CI locally: `ruff check .` and `python -m pytest -q`. Record exact
   results (counts, any failures, warnings).
2. **Independently re-review all four lenses** against the CURRENT working tree (do NOT trust prior
   "FIXED" labels — re-derive them):
   - **Security & secrets** — is the public `/webhook` authenticated for BOTH payload shapes
     (Telegram secret header + sender == `CHAT_ID`; SePay secret mandatory)? Are the
     `/trigger/*` endpoints protected? Does callback parsing survive hostile input before it
     touches `cb["id"]`/`parts`? Any secret values printed/leaked? Any error path that echoes
     internals to the user?
   - **Money correctness** — is webhook idempotency durable + recoverable (what happens if a ref
     is reserved but the transaction append then fails — can a real retry be permanently dropped?
     can two workers both reserve?)? Is currency still handled as `float` anywhere (parse / store /
     sum / ledger)? Rounding consistent between write and report? Period-boundary off-by-one
     (timezone `Asia/Ho_Chi_Minh`)?
   - **Code health & architecture** — `sheets.py` monolith + module-level mutable caches; handlers
     reaching private sheet APIs; dead/legacy code; error-handling consistency.
   - **Tests & CI gaps** — do tests cover the public boundary by actually POSTing to `/webhook`
     (not calling `_process` directly)? Are there tests for concurrent duplicate delivery,
     reservation-after-append-failure, and sheet-lookup-failure paths? Does the CI lint gate
     actually pass locally?
3. **Cross-check (LAST, after forming an independent view)** — read the most recent prior report
   under `docs/audits/` and confirm every previously-OPEN or PARTIAL item is either now closed
   (with evidence) or still listed in your verdict. This catches anything that slipped; it does
   NOT replace your independent pass.
4. **Emit a GO / NO-GO verdict** per the rubric below.

**Negative scope — do NOT:**

- Modify, create (except the one report file), rename, or delete any source/test/config file.
- Run any mutating git op (`add`, `commit`, `push`, `merge`, `checkout -b`, `stash`, `restore`).
- Execute the bot against real Google/Telegram/SePay, or make outbound calls to them. Never read
  or print `.env` / `credentials.json` contents.
- Install/upgrade/pin dependencies or edit `requirements.txt` / `ruff.toml` / `ci.yml`. (If `ruff`
  or `pytest` is missing locally, record that as a finding — do not install it to "make it work.")

**Out-of-scope-but-documented:** if the verdict is NO-GO, the actual fixes are a separate
authorized run. List them as findings with recommended fixes; do not implement here.

---

## Required reading (READ FIRST, in this order, before writing findings)

Read the CURRENT working-tree versions (post-fix), not git history.

1. `.github/workflows/ci.yml` + `ruff.toml` — the gate you must replicate + the lint rule set.
2. `config.py` — secret/env surface; mandatory-secret startup guard.
3. `main.py` — `/webhook` auth for both shapes, `/trigger/*` protection, callback validation
   (and the order relative to `cb["id"]`), sender == `CHAT_ID` checks, the error path.
4. `handlers/sepay.py` — SePay secret check, amount parsing, ref reserve→append→commit sequence.
5. `sheets.py` — idempotency/reservation logic (`_processed_refs` + durable ref rows, the
   reserve/commit/fail states), money parse/round helpers, ledger/balance writes.
6. `handlers/` (transaction, allocation, accounts, manage, keywords, report, reports,
   account_resolver) — money math + private-API reach-through.
7. `telegram_api.py` — outbound wrapper / token use.
8. `tests/conftest.py` + `tests/unit/*.py` (including any new `test_webhook_auth.py` /
   `test_callback_validation.py`) — confirm WHAT is actually asserted, and whether boundary tests
   hit `/webhook` vs internal functions.
9. **Last:** the most recent report in `docs/audits/` — cross-check open/partial items.

---

## Pre-flight + gate (run before re-review; record everything)

```bash
cd "/Users/maingocanh/Projects/My Money Went Bot"
git rev-parse HEAD               # RECORD — verdict is pinned to this commit + working tree
git status --short               # RECORD dirty/clean; list modified/untracked files
git diff --stat                  # RECORD what the uncommitted fixes touch

# The quality gate (replicate CI locally):
ruff check .                     # RECORD: clean? else list violations  (skip+note if ruff absent)
python -m pytest -q 2>&1 | tail -25   # RECORD pass/fail/skip counts + any failures/warnings
```

`Run all of the above. If pytest cannot even collect/run (import error, missing dep) → that is a
TEST_INFRA_BROKEN halt, not a finding. If ruff is not installed locally, note it and continue
(the CI gate still applies remotely).`

---

## Anti-patterns (NEVER do)

- Any mutating git command, or editing source to "quickly fix." **Why:** this is a verification
  gate; a fix mixed into it makes the verdict meaningless and pollutes the next fix diff.
- Marking a prior finding "FIXED" because the report said so. **Why:** the founder asked for an
  INDEPENDENT re-review — re-derive each conclusion from the current working tree with a
  `file:line` to prove it. Stale "FIXED" labels are how regressions ship.
- Returning **GO** while any test fails, `ruff check .` fails, or any P0/P1 remains open. **Why:**
  GO means "safe to commit + deploy"; for a money bot, a single open P0/P1 or red gate is a
  NO-GO by definition.
- Reporting a finding without a `file:line` + quoted excerpt + impact + specific fix. **Why:** an
  un-anchored claim isn't actionable; demote it to "Hypotheses / needs follow-up."
- Printing or copying any real secret value. Refer to secrets by location only (e.g.
  "`SEPAY_SECRET` read at `config.py:NN`"). A leaked secret in the report is itself a P0.
- Running the bot against live Google/Telegram/SePay, or installing tools to force the gate green.

---

## Numbered steps

Append to the report as you go; don't hold everything to the end.

**Step 1 — Initialize the report + run the gate.** Create the report file with a header:
project, `HEAD` SHA, date, working-tree state (dirty/clean + file list), `ruff` result, `pytest`
result (counts + any failures/warnings), the four lenses, and the severity + verdict rubrics.
Sanity check: if the gate is RED (ruff fails or any test fails), the verdict is already trending
NO-GO — keep reviewing to produce the full issue list, but do not later flip to GO.

**Step 2 — Security & secrets re-review.** Verify both `/webhook` payload shapes are
authenticated, `/trigger/*` are protected, callback parsing is safe before `cb["id"]`/`parts`,
no internal leak in error paths. Record findings with severity.

**Step 3 — Money correctness re-review.** Trace SePay payload → ref reserve → append → commit.
Specifically answer: can a reserved-but-not-committed ref cause a real retry to be silently
dropped (money loss)? Can concurrent workers both reserve the same ref? Is currency `float`
anywhere on the parse/store/sum/ledger path? Record findings (idempotency/money bugs are P0/P1).

**Step 4 — Code health re-review.** `sheets.py` monolith, module-level caches, private-API
reach-through from handlers, dead/legacy code, error-handling consistency. Mostly P2.

**Step 5 — Tests & CI re-review.** Confirm boundary tests actually POST to `/webhook`; check for
concurrent-duplicate / reservation-after-append-failure / sheet-lookup-failure tests; confirm the
lint gate passes locally (or note ruff absence). Record gaps.

**Step 6 — Cross-check prior report.** Read the most recent `docs/audits/*` report. For each item
it marked OPEN / PARTIAL / STILL_OPEN, confirm against the working tree whether it's now closed
(cite evidence) or still open (carry into your verdict). Note any NEW finding it raised that you
must confirm or refute.

**Step 7 — Verdict.** Apply the verdict rubric. Re-read your own ranked findings (self-verification
oracle): each must have a valid `file:line` and a severity matching the rubric; demote anything
you can't substantiate. Then write the verdict + executive summary + remediation checklist.

---

## Evidence gate (correctness oracle)

A finding is a finding only if it has: (1) a concrete `path:line` that exists in the current
working tree, (2) a quoted excerpt (secrets redacted), (3) a concrete impact (what/when/blast
radius), (4) a specific recommended fix. If you catch yourself writing "this might…" / "probably…"
→ it goes under **Hypotheses / needs follow-up**, never into ranked findings or the verdict math.

---

## Finding block format (verbatim for every ranked finding)

```
### [<P0|P1|P2>] <short title>

- **Lens:** Security | Money | Health | Tests
- **Location:** `path/to/file.py:LL` (or `LL-LL`)
- **Status vs prior report:** new | confirmed-still-open | regressed | (n/a)
- **Evidence:**
  ```python
  <quoted excerpt, secrets redacted as <REDACTED>>
  ```
- **Impact:** <what breaks, trigger, blast radius>
- **Recommended fix:** <specific change, where, why it closes the gap>
- **Effort:** <S | M | L>
```

**Severity rubric (calibrate; do not inflate):**

- **P0** — money loss/corruption, unauthenticated control of the bot, secret exposure, or silent
  data integrity failure.
- **P1** — exploitable-but-bounded, correctness bug under realistic conditions, or a structural
  issue that will cause a P0 soon.
- **P2** — maintainability, missing tests, code smells, non-exploitable hardening.

**Verdict rubric:**

- **GO** — `ruff check .` clean (or ruff-absent-locally noted AND no obvious lint issues) AND
  `pytest` fully green AND **zero P0 AND zero P1** open. Safe to commit + deploy.
- **GO-WITH-CAVEATS** — gate green AND zero P0 AND zero P1, but P2 items remain that the founder
  should consciously accept. List them explicitly.
- **NO-GO** — any test fails, OR `ruff check .` fails, OR **any P0/P1 remains open**. Blockers
  listed first, each with its fix.

---

## Circuit breakers (HALT + write a halt report; do not push through)

1. **TEST_INFRA_BROKEN** — `pytest` can't collect/run (import error, missing dep). HALT with the
   error; this blocks the verdict.
2. **SECRET_EXPOSURE** — a real secret value appears committed (not `.env.example` placeholders).
   Record location + P0, do NOT print the value, then surface it at the top of the report.
3. **SCOPE_DRIFT** — about to edit/commit a source file to "just fix" something. STOP; the only
   permitted write is the report.
4. **DESTRUCTIVE_OR_NETWORK_ACTION** — any step would mutate git, the filesystem (beyond the
   report), or call a live Google/Telegram/SePay endpoint. HALT.
5. **TOOL_ERROR_TWICE** — same `git`/`pytest`/`ruff`/read tool fails twice in a row. HALT.
6. **AMBIGUOUS_SEVERITY** — a finding's severity genuinely needs founder context to calibrate.
   Record under Hypotheses with the specific question; do not guess P0.
7. **CONTEXT_BUDGET >70%** — flush the in-progress report to disk and emit a halt report noting
   which lenses + the gate are done, so a fresh session resumes the rest.

---

## Halt report template

```
HALT — final verification circuit broken.

Step:    <e.g. Step 3 money re-review / pre-flight gate>
Trigger: <one of the 7 breakers>
HEAD:    <SHA>   Working tree: <dirty | clean>

Detail:
<error output OR condition, secrets redacted>

State:
- Report file: docs/audits/final-verification-<date>.md
- Gate: ruff <clean|fail|absent> | pytest <counts or "could not run">
- Lenses complete: <list>   remaining: <list>

Requesting founder input on:
<specific question>
```

---

## Final report (emit verbatim on success)

```
═══════════════════════════════════════════════════════
FINAL VERIFICATION — My Money Went Bot — <GO | GO-WITH-CAVEATS | NO-GO>
═══════════════════════════════════════════════════════

Report file:   docs/audits/final-verification-<YYYY-MM-DD>.md
HEAD:          <SHA>   Working tree: <dirty (files…) | clean>
Source files modified: NONE  (read-only verification)
Git operations: NONE

Quality gate:
  ruff check .:  <clean | N violations | not installed locally>
  pytest -q:     <N passed / M failed / K skipped>  (warnings: <…>)

Open findings (independently verified):
  P0: <count>   P1: <count>   P2: <count>
  Hypotheses / needs follow-up: <count>

Verdict: <GO | GO-WITH-CAVEATS | NO-GO>
Reason:  <one line — e.g. "1 P0 (ref-reservation drop) + float money P1 still open">

Blockers to GO (if any), in fix order:
  1. <title> — <path:line>
  2. <title> — <path:line>

Cross-check vs prior report (<filename>):
  Previously open/partial items now CLOSED: <count>
  Still open: <list>   Regressed: <list>

Lenses covered: Security ✓  Money ✓  Health ✓  Tests/CI ✓

Next step (separate authorized run, only if NO-GO): remediate blockers,
each as its own TDD-first fix; then re-run this verification.
═══════════════════════════════════════════════════════
```

The report file is gitignored under the existing `docs/` rule, so it stays local and is never
accidentally committed — consistent with this run's read-only intent.

Begin with the Pre-flight + gate, then Step 1.
