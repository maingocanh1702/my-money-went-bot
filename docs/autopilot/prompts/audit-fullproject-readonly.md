# Task: Full-project code audit (My Money Went Bot) — READ-ONLY, prioritized findings report

You are working in `/Users/maingocanh/Projects/My Money Went Bot` on a personal-finance
Telegram bot: a FastAPI service that receives SePay bank webhooks + Telegram updates on a
single `/webhook` endpoint and records every transaction into Google Sheets (gspread),
deployed on Railway. NO prior conversation context. This prompt is self-contained.

Mode: AUDIT — **READ-ONLY**. Single pass, no feature branch, no code mutation.
You will read the codebase, gather verifiable findings, and write ONE markdown audit
report. Then STOP_AT_REPORT. Pause ONLY on a circuit-breaker condition.

---

## Audit risk header (REQUIRED — read before anything else)

```
Authority:        READ_ONLY  (analyze + write report file only)
Source mutation:  FORBIDDEN  (no edits, no commits, no merges, no pushes)
Network:          FORBIDDEN to real services (no live Google Sheets / Telegram / SePay calls)
Deliverable:      docs/audits/audit-<YYYY-MM-DD>.md  (prioritized P0/P1/P2 findings)
Exit condition:   STOP_AT_REPORT  (report written + final report emitted)
Remediation:      OUT OF SCOPE — fixes happen in a separate, future autopilot run
```

Rule: this is an audit, not a codegen task. You have authority to **read any file** and to
**write the single report file** named above (creating `docs/audits/` if missing). You have
NO authority to modify, create, rename, or delete any other file, to run `git add/commit/
push/merge`, or to execute the bot against real credentials. When in doubt → default to the
lower authority: record an observation in the report and move on. Do not "fix while you're in
there."

---

## Context (NOT for execution, just background)

- Single-tenant bot: one owner identified by `CHAT_ID`. All money data lives in one Google
  Sheet (tabs defined in `config.py` → `class SHEETS`).
- `/webhook` is **public** (Railway URL) and multiplexes two payload shapes: Telegram updates
  (`"update_id"` present) and SePay bank webhooks (everything else). It returns `200` instantly
  and processes in a FastAPI `BackgroundTask`.
- There is currently **no CI, no pre-commit, no linter, no type-checker, no import-linter** in
  this repo. Tests are pytest unit tests using an in-memory gspread fake (`tests/conftest.py`).
- The audit exists to produce a single, founder-readable risk map before further feature work
  and before/after the planned OSS publish (`scripts/publish_oss_v1.sh`).

Do not infer "why" the code is shaped the way it is from the code alone — record what you can
verify, and mark inferences explicitly as inferences.

---

## Scope of this audit

**Positive scope — analyze ALL four lenses across the whole repo:**

1. **Security & secrets** — webhook authentication (SePay secret is optional; Telegram sender
   not verified?), secret handling/exposure, input validation on callback/command parsing,
   SSRF/injection surface, error messages that leak internals, dependency risk.
2. **Money correctness** — ledger/allocation/balance math, `float` use for currency, rounding,
   idempotency & dedup of webhook-driven transactions (in-memory cache survives restarts? multi-
   worker?), double-counting, off-by-one in period reports.
3. **Code health & architecture** — the `sheets.py` monolith (~1.8k LOC), handler coupling,
   the confusingly similar `report.py` / `reports.py` naming (verify whether responsibilities
   actually overlap before claiming duplication), dead/legacy code, error-handling
   consistency, module boundaries, naming.
4. **Tests & CI gaps** — coverage holes by handler, missing edge-case categories (idempotency,
   concurrent, pathological input, auth-bypass), the empty `tests/integration/`, and the total
   absence of lint/type/CI gates.

**Negative scope — do NOT:**

- Modify, create (except the one report file), rename, or delete any source/test/config file.
- Run `git add`, `git commit`, `git push`, `git merge`, `git checkout -b`, or any mutating git op.
- Execute the bot against real Google/Telegram/SePay credentials, or make any outbound network
  call to those services. Reading `.env.example` is fine; **never read or print `.env` /
  `credentials.json` contents** even if present.
- Install, upgrade, or pin dependencies; do not touch `requirements.txt`.

**Out-of-scope-but-documented:** actual fixes, refactors, and adding CI/lint tooling are
deliberately deferred to a later remediation run. Capture them as findings with recommended
fixes; do not implement them here.

---

## Required reading (READ FIRST, in this order, before writing any finding)

1. `config.py` — secret/env surface; `SEPAY_SECRET` default `""`; `class SHEETS` tab names.
2. `main.py` — entry + dispatcher. Focus: `_process` (line ~90), `_handle_callback`
   (`data.split("_")` prefix routing, lines ~107-111), `_handle_message` sender filter — note it
   only checks `is_bot` (line ~135), not identity against `CHAT_ID` — and the broad `except` that
   echoes `{e}` to Telegram (line ~104).
3. `handlers/sepay.py` — webhook ingest. Focus: optional-secret check (lines ~37-47),
   referenceCode handling + cross-source dedup (lines ~83-124).
4. `sheets.py` — the data layer (~1841 LOC). Focus: idempotency cache `_processed_refs`
   (lines ~478-508, in-memory dict + 300s TTL), money parsing/rounding helpers (lines ~90-161),
   ledger/balance writes (lines ~1380-1530). Skim the rest for structure; you are NOT expected
   to read every line — sample representative functions and note the monolith risk.
5. `handlers/transaction.py`, `handlers/allocation.py`, `handlers/accounts.py` (850 LOC),
   `handlers/manage.py`, `handlers/keywords.py`, `handlers/report.py`, `handlers/reports.py`,
   `handlers/account_resolver.py` — responsibilities, coupling, duplicated logic.
6. `telegram_api.py` — outbound API wrapper; how the token is used; error handling.
7. `tests/conftest.py` + `tests/unit/*.py` — what IS covered, so gaps are evidence-based.
   Note `tests/integration/` is empty.
8. `README.md`, `crontab.txt`, `railway.toml`, `.gitignore` — deployment + secret-ignore model.

---

## Pre-flight gate (run before reading code; all must pass)

```bash
cd "/Users/maingocanh/Projects/My Money Went Bot"
git status                       # note clean vs dirty (audit reads working tree as-is)
git branch --show-current        # expected: main
git rev-parse HEAD               # RECORD this SHA — the report is pinned to this commit
python -m pytest -q 2>&1 | tail -20   # RECORD the baseline (pass/fail/skip counts)
```

Record `HEAD` SHA and the pytest baseline in the report header. You are NOT required to be on a
clean tree to audit, but if the tree is dirty, **note it** so findings are attributable to a
known state. If `git` or `pytest` is unavailable → HALT and report (tool-availability breaker).

`ALL informational checks must complete. If a tool is missing → HALT and report. Do not proceed
by guessing repo state.`

---

## Anti-patterns (NEVER do)

- `git push --force`, or **any** mutating git command. This is read-only.
- Editing source to "quickly fix" a finding. **Why:** the audit's value is an honest, complete
  risk map; a half-fix mixed into a read-only pass corrupts both the diff and the report. Fixes
  are a separate authorized run.
- Reporting a finding without a `file:line` anchor and a quoted code excerpt. **Why:** an audit
  that can't point at the line is a vibe, not a finding — and the founder can't act on it.
  Anything you only suspect goes under a clearly labeled "Hypotheses / needs follow-up" section,
  never mixed into ranked findings.
- Inventing severity to inflate the report. **Why:** P0 must mean "money loss, data corruption,
  or unauthenticated control." If everything is P0, nothing is. Calibrate against the rubric below.
- Printing or copying any real secret value (token, key, credential). **Why:** the report may be
  shared; a leaked secret in the report is itself a P0. Refer to secrets by location, e.g.
  "`BOT_TOKEN` read from env at `config.py:6`", never by value.
- Running the bot against live Google/Telegram/SePay, or hitting their network endpoints.
  **Why:** could mutate real financial data or spam the owner's chat.
- Adding `# type: ignore`, touching `requirements.txt`, or installing tools. Out of scope.

---

## Numbered audit steps

Each step is read-then-record. Append findings to the in-progress report as you go (don't hold
everything in memory to the end). Every finding uses the **finding block format** in the next
section.

**Step 1 — Initialize the report.** Create `docs/audits/audit-<YYYY-MM-DD>.md` (today's date)
with the header: project name, audited `HEAD` SHA, date, pytest baseline, working-tree state
(clean/dirty), the four lenses, and the severity rubric. Leave section stubs for each lens.
Sanity check: if `docs/audits/` cannot be created, that's the only write you're permitted — HALT
and report rather than writing elsewhere.

**Step 2 — Security & secrets pass.** Walk `config.py` → `main.py` → `handlers/sepay.py` →
`telegram_api.py`. For each, ask: Is the request authenticated? Can an attacker who knows the
public `/webhook` URL forge a Telegram update or a SePay transaction? Is the Telegram sender
verified against `CHAT_ID`? Does `data.split("_")` survive hostile callback data (IndexError,
unexpected prefixes)? Does the `except … {e}` path leak internals? Are secrets only ever read
from env and properly gitignored? Record each as a finding with severity.

**Step 3 — Money correctness pass.** Walk the money path: SePay payload → dedup
(`_processed_refs`) → sheet write → balance/ledger update → report aggregation. Ask: Is
idempotency durable across restart/redeploy and across multiple uvicorn workers, or only within
one in-memory process for 300s? Can a retried webhook double-count? Is currency stored/added as
`float` (precision risk)? Are rounding rules consistent between write and report? Any off-by-one
in week/month/quarter/year period boundaries (timezone is `Asia/Ho_Chi_Minh`)? Record findings.

**Step 4 — Code health & architecture pass.** Assess `sheets.py` as a monolith (size, mixed
responsibilities, module-level mutable caches), handler coupling, the `report.py` / `reports.py`
naming overlap (confirm scope before calling it duplication — they may be complementary: daily
recap vs unified period report), legacy/dead code (e.g. `handle_new_account_balance` marked
"Legacy" in `main.py`),
inconsistent error handling, and naming. Record findings (mostly P2, occasionally P1 if a
structural issue causes correctness/security risk).

**Step 5 — Tests & CI gaps pass.** Cross-reference `tests/unit/*` against the handlers. List
which handlers/branches have NO test, which edge-case categories are absent (idempotency,
concurrent delivery, auth-bypass, pathological input), the empty `tests/integration/`, and the
absence of any lint/type/CI gate. Record findings + a recommended minimal CI/quality-gate setup.

**Step 6 — Synthesize, prune, prioritize.** Re-read your own findings (self-verification oracle):
for each, confirm the `file:line` still supports the claim and the severity matches the rubric.
Demote anything you can't fully substantiate to "Hypotheses / needs follow-up." Then build the
executive summary, the severity-ordered findings list, and the remediation checklist.

---

## Evidence gate (the audit's correctness oracle)

A finding is only a finding if ALL of these hold; otherwise it is a hypothesis:

1. It cites a concrete `path:line` (or line range) that exists at the audited `HEAD`.
2. It quotes the relevant code excerpt (a few lines, secrets redacted).
3. It states a concrete **impact** (what goes wrong, for whom, under what trigger).
4. It proposes a **specific** recommended fix (not "improve error handling" — say what and where).

If you find yourself writing "this might…", "probably…", or "I'd need to check…" → it belongs in
**Hypotheses / needs follow-up**, not in the ranked findings. Honest uncertainty is a feature.

---

## Finding block format (use verbatim for every ranked finding)

```
### [<P0|P1|P2>] <short title>

- **Lens:** Security | Money | Health | Tests
- **Location:** `path/to/file.py:LL` (or `LL-LL`)
- **Evidence:**
  ```python
  <quoted excerpt, secrets redacted as <REDACTED>>
  ```
- **Impact:** <what breaks, trigger, blast radius>
- **Recommended fix:** <specific change, where, and why it closes the gap>
- **Effort:** <S | M | L>
```

**Severity rubric (calibrate against this — do not inflate):**

- **P0** — money loss/corruption, unauthenticated control of the bot, secret exposure, or silent
  data integrity failure. Acer-on-fire.
- **P1** — exploitable-but-bounded, correctness bug under realistic conditions, or a structural
  issue that will cause a P0 soon. Fix before next release.
- **P2** — maintainability, missing tests, code smells, non-exploitable hardening. Backlog.

---

## Circuit breakers (HALT and write a halt report; do not push through)

1. **SECRET_EXPOSURE** — a real secret value appears committed in the repo (not `.env.example`
   placeholders). Record location + severity P0, **do NOT print the value**, finish the security
   section if safe, then HALT and surface it at the top of the report.
2. **SCOPE_DRIFT** — you are about to edit/commit a source file to "just fix" something. STOP;
   the only permitted write is the report.
3. **DESTRUCTIVE_OR_NETWORK_ACTION** — any step would mutate git, the filesystem (beyond the
   report), or call a live Google/Telegram/SePay endpoint. HALT.
4. **TOOL_ERROR_TWICE** — same `git`/`pytest`/read tool fails twice in a row. HALT with the error.
5. **AMBIGUOUS_SEVERITY** — a finding's severity genuinely can't be calibrated without founder
   context (e.g. "is this webhook ever exposed publicly?"). Record it under Hypotheses with the
   specific question; do not guess P0.
6. **CONTEXT_BUDGET >70%** — pause, flush the in-progress report to disk, and emit a halt report
   noting which lenses are complete so a fresh session can resume from the remaining steps.

---

## Halt report template

```
HALT — audit circuit broken.

Step:    <e.g. Step 3 money pass>
Trigger: <one of the 6 breakers>
HEAD:    <SHA>

Detail:
<error output OR the condition, secrets redacted>

State:
- Report file: docs/audits/audit-<date>.md (lenses complete: <list>)
- Lenses remaining: <list>

Requesting founder input on:
<specific question>
```

---

## Final report (emit verbatim on success)

```
═══════════════════════════════════════════════════════
AUDIT — My Money Went Bot — COMPLETE (READ-ONLY)
═══════════════════════════════════════════════════════

Report file:   docs/audits/audit-<YYYY-MM-DD>.md
Audited HEAD:  <SHA>
Working tree:  <clean | dirty (noted in report)>
Source files modified: NONE  (read-only audit)
Git operations: NONE

Findings:
  P0: <count>   P1: <count>   P2: <count>
  Hypotheses / needs follow-up: <count>

Top 3 risks (by severity then blast radius):
  1. <title> — <path:line>
  2. <title> — <path:line>
  3. <title> — <path:line>

Lenses covered: Security ✓  Money ✓  Health ✓  Tests/CI ✓
Pytest baseline at audit time: <N passed / M failed / K skipped>

Next step (separate authorized run): remediation of P0/P1 findings,
each as its own TDD-first fix per the autopilot prompt template.
═══════════════════════════════════════════════════════
```

The report file itself is gitignored under the existing `docs/` rule in `.gitignore`, so it
stays local and is never accidentally committed — consistent with this run's read-only intent.

Begin with Pre-flight, then Step 1.
