# Task: Comprehensive v0.2.2 ship + F07 resume to READY (multi-phase autopilot)

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained and **multi-phase**. Read all of it before
starting.

**Mode:** AUTOPILOT mega-prompt. 3 sequential phases. Each phase has its
own checkpoint report. Cascade-tolerant codex review budgets. Founder
explicitly accepts long runtime.

**3 phases overview:**

| Phase | Goal | Branch | Hard limit | End state |
|---|---|---|---|---|
| A | Ship v0.2.2 to main | `chore/autopilot-v0.2.2` | 10 fix rounds + 2 confirm | Squash + push to main |
| B | Resume F07 with v0.2.2 tool to READY | `feat/F07-settings` | orchestrator's own (5 + 2) | F07 ready-report.md exists |
| C | Final tracker + report | main | n/a | Tracker pushed + final report |

**Critical:** F07 ships via founder manual squash AFTER this prompt
(per plan v0.2.0 §6.5 P1 manual-merge rule). This prompt ends at
F07 READY, not F07 merged.

**Context (NOT for execution, just background):**

v0.2.2 ("autopilot tooling hardening") is at HEAD `e9b65c1` on branch
`chore/autopilot-v0.2.2` with 15 commits. 6 codex rounds have run:

- R1 P1: post-fix-confirm gate persistence → fixed `1b516e3`
- R2 P1+P2: "rce" substring + MERGED sync skip → fixed `88c1f49`
- R3 P1: INIT sync skip → fixed `9a91c7c`
- R4 P1+P2: word-boundary regex + READY sync skip → fixed `661c5ba`
- R5 P2: Phase E merge gate alignment → fixed `e9b65c1`
- R6 P1+P2: detached HEAD in `current_branch()` (THIS prompt fixes);
  halt message label (DEFERRED to v0.2.3)

Cascade pattern is real and expected. v0.2.2 PR is structurally large;
each codex round surfaces 1-2 legitimate adjacent findings. This prompt
extends budget significantly: up to 10 fix rounds + 2 post-fix-confirm
rounds. If cascade still doesn't converge → escalate to founder.

F07 (Settings) is at HEAD `6ffe912` on `feat/F07-settings` with 12
codegen + 4 codex-driven fix commits + 2 v0.2.1-merge commits +
get_overview-pure-read refactor (6 commits) + markdown fix (2 commits)
+ i18n strip (2 commits). State is HALTED. Will resume in Phase B
after v0.2.2 ships and merges into F07 branch.

**3 concurrency incidents** during v0.2.2 work confirm the policy doc.
**ZERO other Claude Code sessions allowed during this prompt's execution.**

## Required reading (READ FIRST, in this order)

1. `.autopilot/state/v0.2.2/halt-report.md` — full v0.2.2 R6 halt context.
2. `.autopilot/state/v0.2.2/codex/round-{01..06}.txt` — R1-R6 verdicts.
3. `tools/autopilot/git_ops.py` — `current_branch()` helper added v0.2.2
   Step 4 (Fix #3). Understand current implementation that returns
   literal "HEAD" on detached state.
4. `tools/autopilot/loop.py` — Phase C while-loop with new
   `confirmation_rounds_after_last_fix` logic, plus the resume-branch-sync
   block.
5. `tools/autopilot/codex.py` — `parse_findings`, `CLEAN_PHRASES`,
   `SECURITY_KEYWORDS_*`.
6. `tools/autopilot/circuit_breaker.py` — `evaluate()` security check.
7. `docs/features/feature-settings.md` — F07 spec (especially gap G4
   recently revised to pure-read).
8. `.autopilot/state/F07/state.json` — current F07 state (HALTED).
9. `.autopilot/state/F07/halt-report.md` — most recent F07 halt context.
10. `docs/autopilot/autopilot-implementation-plan.md` §6.5 — risk tier
    policy. F07 is P1 manual-merge.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent

# Branch state
git branch --show-current               # MUST: chore/autopilot-v0.2.2
git log --oneline -1                    # MUST: e9b65c1
git log --oneline main..HEAD | wc -l    # MUST: 15
git status                              # MUST: clean

# F07 branch exists
git rev-parse --verify feat/F07-settings  # MUST resolve to a SHA

# F07 state present
test -f .autopilot/state/F07/state.json
cat .autopilot/state/F07/state.json | python -m json.tool | head -5
# MUST show phase: HALTED

# Codex artifacts present
ls .autopilot/state/v0.2.2/codex/round-{01..06}.txt
ls .autopilot/state/F07/codex/round-*.txt 2>/dev/null | head -3

# Concurrency check
ls .git/*.lock 2>/dev/null
# MUST be empty

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling green at current HEAD
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # MUST: 293 pass

# Origin/main reachable
git fetch origin main
git log --oneline origin/main -1
```

If anything diverges → HALT and report. Do not proceed.

## Anti-patterns (apply throughout all phases)

- `git push --force` (ever, anywhere).
- Add `# type: ignore` (circuit breaker).
- Run other Claude Code sessions on this repo during this prompt.
- Modify F07 branch during Phase A.
- Auto-merge F07 to main (P1 — founder squashes manually).
- Skip a phase. Each phase has explicit checkpoint report — output
  verbatim before moving to next.
- Apply fixes during Phase A R8/R9/R10 confirmation tail OR Phase B
  orchestrator resume rounds without explicit reasoning in commit
  message linking to the codex finding.
- Defer multiple findings silently. Every deferred finding goes to
  CHANGELOG v0.2.3 known-issues subsection.

---

# PHASE A — Ship v0.2.2 to main

## Step A.1 — Apply R6 P1 fix (defer R6 P2)

Read `.autopilot/state/v0.2.2/codex/round-06.txt`. Confirm R6 P1
finding text matches: `current_branch()` returns literal "HEAD" on
detached state, causing silent wrong-tree sync.

**File:** `tools/autopilot/git_ops.py`

Modify `current_branch()`:

```python
def current_branch(cfg: Config) -> str | None:
    """Return current branch name, or None if detached HEAD.

    `git rev-parse --abbrev-ref HEAD` returns the literal string "HEAD"
    when in detached-HEAD state. Returning that to loop.py's resume sync
    would silently no-op (string "HEAD" matches no branch name) and let
    Codex review run on whatever tree is at the detached SHA — same
    wrong-diff bug v0.2.2 Fix #3 was supposed to prevent.

    Codex v0.2.2 R6 P1.
    """
    out = _run(cfg, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    return None if out == "HEAD" else out
```

**File:** `tools/autopilot/loop.py`

Update resume-sync callsite to handle None:

```python
current_branch = git_ops.current_branch(cfg)
if current_branch is None:
    return _halt(
        cfg, feature_state, "DETACHED_HEAD",
        "Repository is in detached-HEAD state; cannot safely sync to "
        f"feature_state.branch={feature_state.branch!r}. Run "
        f"`git checkout {feature_state.branch}` manually then re-resume.",
    )
if current_branch != feature_state.branch:
    if not git_ops.branch_exists(cfg, feature_state.branch):
        return _halt(...)  # existing BRANCH_MISSING
    print(f"Syncing branch checkout: {current_branch} → {feature_state.branch}")
    git_ops.checkout(cfg, feature_state.branch)
```

## Step A.2 — Add regression test

**File:** `tests/unit/test_autopilot_git_ops.py` (new or extend).

Add tests for `current_branch()` returning None on detached HEAD,
plus a counter-test for normal branch checkout. Use repo's existing
tmp_path git fixture pattern (look at `tests/unit/test_autopilot_*.py`).

Also extend the existing resume-branch-sync test (added by v0.2.2 Fix #3)
to assert the DETACHED_HEAD halt path fires.

## Step A.3 — Document R6 P2 in v0.2.3 backlog

**File:** `CHANGELOG.md`

Find the v0.2.2 `## [Unreleased]` section. Add (or extend if exists)
a "Known issues — deferred to v0.2.3" subsection at the end of the
v0.2.2 block:

```markdown
### Known issues — deferred to v0.2.3

- `loop.py` MAX_ROUNDS halt message always cites
  `confirmation_rounds_after_last_fix` even when the legacy
  `required_clean_rounds_before_merge` gate was active. Diagnostic-only
  (no functional impact). Codex v0.2.2 R6 P2.
- Budget semantics clarification: current logic conflates "max review
  rounds total" with "max fix rounds + post-fix-confirm rounds". Should
  be split into explicit knobs.
- Codex CLI stale-blob true fix (currently logs warning only).
- tracker sync command / sidecar (currently no-op on feature branches).
- File lock for concurrent-session safety (currently doc-only policy;
  3 incidents during v0.2.2 work confirmed hazard).
```

(Add additional R7+ findings here as they're encountered + deferred.)

## Step A.4 — Local verify + atomic commits

```bash
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # expected: 293 + 2 new = 295
```

ALL must pass. If verify fails → up to 2 retries. After 2 retries
→ HALT `VERIFY_REGRESSION` with continuation hint.

```bash
git add tools/autopilot/git_ops.py tools/autopilot/loop.py
git commit -m "fix(autopilot): current_branch returns None on detached HEAD (codex v0.2.2 r6 P1)

Detached HEAD made current_branch() return literal 'HEAD'. loop.py's
resume sync compared against feature_state.branch, silently no-op'd,
and let codex run on wrong tree. Now returns None; caller halts with
DETACHED_HEAD breaker."

git add tests/unit/test_autopilot_git_ops.py
git commit -m "test(autopilot): current_branch detached HEAD regression guard"

git add CHANGELOG.md
git commit -m "docs(autopilot): v0.2.3 known-issues backlog (R6 P2 + cumulative findings)"
```

## Step A.5 — Codex review LOOP (cascade-tolerant)

**Budget:** Up to **10 fix rounds total** (across this and prior sessions
— R1-R6 already used 6, so 4 more budget) + 2 post-fix-confirm rounds.
If 10 fix rounds done without 2× confirm → HALT `MAX_FIX_BUDGET_EXHAUSTED`.

**Loop logic:**

```
fixes_applied = 6  # R1-R6 P1 (just committed)
confirms = 0
round_n = 6

while True:
    round_n += 1

    # Concurrency check
    if .git/*.lock exists → HALT CONCURRENT_AGENT_DETECTED

    codex review --base main 2>&1 | tee .autopilot/state/v0.2.2/codex/round-NN.txt

    parse output

    if CLEAN:
        confirms += 1
        if confirms >= 2:
            break  # 2× post-fix-confirm achieved → ship
        continue

    # FINDING — circuit-breaker checks
    if P0 or severe security keyword (real, not "rce"-in-"force"):
        HALT P0_FOUND or SECURITY_FINDING_REAL
    if same finding hash as any prior round:
        HALT RECURRING_FINDING
    if arch keyword (schema/breaking-change):
        HALT ARCH_FINDING

    # Soft security keyword + P0/P1: HALT (severity-based, not keyword-based)
    # Soft security keyword + P2/P3: proceed to fix
    # Other findings: proceed to fix

    if fixes_applied >= 10:
        HALT MAX_FIX_BUDGET_EXHAUSTED
        # founder decides: ship-with-override + comprehensive backlog

    # Apply MINIMUM-VIABLE fix
    # Atomic commit: "fix(autopilot): address codex round NN — <summary>"
    fixes_applied += 1
    confirms = 0  # reset

    local verify (ruff/black/mypy/pytest) MUST pass
    if verify fails 2x → HALT VERIFY_REGRESSION
```

**Defer-vs-fix rule (for new findings during cascade):**

- Severity P0 → always fix (or HALT P0_FOUND for founder review).
- Severity P1 → fix unless cascade is at fix-round 9-10 (then defer
  to v0.2.3 with explicit justification in CHANGELOG).
- Severity P2 → fix unless cascade is at fix-round 7+ (then defer
  to v0.2.3).
- Severity P3 → defer to v0.2.3 in any cascade round ≥7.

(Goal: still address critical issues; reduce cascade tail by deferring
cosmetic items.)

**Per-round output:**

After each round, print:

```
=== Codex round NN ===
  raw: .autopilot/state/v0.2.2/codex/round-NN.txt
  finding count: <N>
  classification: <CLEAN | DEFER (logged to CHANGELOG) | FIX (commit <SHA>)>
  fixes_applied: <count>
  confirms: <0 | 1 | 2>
```

## Step A.6 — Squash + push v0.2.2 (when 2× post-fix-confirm achieved)

```bash
# Final sanity verify
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main

# Dry-run merge
git merge --no-commit --no-ff chore/autopilot-v0.2.2
git merge --abort

# Real squash
git merge --squash chore/autopilot-v0.2.2
git commit -m "fix(autopilot): v0.2.2 — tooling hardening from F07 + v0.2.1 cumulative pilot signal

<COMPOSE FULL MESSAGE: list all v0.2.2 fixes + final codex round count
+ deferred-to-v0.2.3 list. Use template from earlier prompt versions
as reference (autopilot-v0.2.2-finish-r5-r6-r7.md). Adapt to actual
final round sequence executed.>

F07 resume IN PROGRESS in Phase B of this same session."

git branch -D chore/autopilot-v0.2.2
git push origin main
```

If push rejected → HALT. Do NOT force-push.

## Step A.7 — PHASE A CHECKPOINT REPORT (output verbatim)

```
═══════════════════════════════════════════════════════
PHASE A CHECKPOINT — v0.2.2 SHIPPED to main
═══════════════════════════════════════════════════════

Squash commit: <SHA> on main
Branch chore/autopilot-v0.2.2: DELETED
Push origin/main: OK

Codex review sequence (cumulative across sessions):
  R1: P1 → fix 1b516e3
  R2: P1+P2 → fix 88c1f49
  R3: P1 → fix 9a91c7c
  R4: P1+P2 → fix 661c5ba
  R5: P2 → fix e9b65c1
  R6: P1 → fix <THIS SESSION SHA>; P2 deferred
  R7: <result>
  R8: <result>
  ... (up to R12 if cascade continued)
  Final state: 2× post-fix-confirm at R<X>+R<X+1>
  Total fix rounds: <count> (budget 10)

v0.2.3 backlog (from CHANGELOG known-issues):
  - R6 P2 halt message label (deferred at session start)
  - <list any R7-R10 deferred findings>
  - Budget semantics clarification
  - Codex stale-blob true fix
  - tracker sync command
  - File lock for concurrency

Local verification (final):
  ruff/black/mypy/lint-imports: clean
  pytest: <count> passed

Proceeding to PHASE B (F07 resume with v0.2.2 orchestrator).
═══════════════════════════════════════════════════════
```

---

# PHASE B — F07 resume with v0.2.2 orchestrator

## Step B.1 — Switch to F07 branch

```bash
git checkout feat/F07-settings
git status                              # MUST clean
git log --oneline -3
# Top should be 6ffe912 or later (i18n backtick fix)
```

## Step B.2 — Merge main (with v0.2.2) into F07 branch

```bash
git merge main
```

**Outcomes:**

- **Auto-merged clean** → proceed to Step B.3.
- **Conflict** (likely on CHANGELOG.md, possibly docs/implementation-tracker.md
  or .secrets.baseline) → resolve per Step B.3.

## Step B.3 — Resolve conflicts (if any)

```bash
git status                              # show unmerged files
```

For each conflict:

- **CHANGELOG.md**: keep both entries (F07 + v0.2.2 sections concat under
  `[Unreleased]`). Edit manually if needed:

  ```bash
  nano CHANGELOG.md
  # Find <<<<<<< / ======= / >>>>>>> markers
  # Manually merge keeping all subsections
  git add CHANGELOG.md
  ```

- **docs/implementation-tracker.md**: keep main's version (post-v0.2.2
  state):

  ```bash
  git checkout --theirs docs/implementation-tracker.md
  git add docs/implementation-tracker.md
  ```

- **.secrets.baseline** (if conflict): keep main's:

  ```bash
  git checkout --theirs .secrets.baseline
  git add .secrets.baseline
  ```

- Any other conflict: HALT `UNEXPECTED_MERGE_CONFLICT` for founder
  decision.

```bash
git status                              # MUST: "All conflicts fixed but you are still merging"
git commit -m "merge: main (v0.2.2 orchestrator + cumulative docs) into feat/F07-settings"
```

## Step B.4 — Verify orchestrator code on F07 branch

```bash
# Confirm v0.2.1 + v0.2.2 features all present on F07 branch
grep -q "last_active_phase" tools/autopilot/state.py        # v0.2.1
grep -q "PARSER_UNCERTAIN" tools/autopilot/loop.py          # v0.2.1
grep -q "confirmation_rounds_after_last_fix" tools/autopilot/loop.py  # v0.2.2
grep -q "DETACHED_HEAD" tools/autopilot/loop.py             # v0.2.2 R6 P1
grep -q "SECURITY_KEYWORDS_SEVERE" tools/autopilot/codex.py # v0.2.2

# Sanity test
source .venv/bin/activate
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
# Expected: F07 baseline (~287) + v0.2.2 tests (~10) = ~297 pass
```

If any grep fails → HALT `MERGE_INCOMPLETE` (v0.2.2 features missing
on F07 branch after merge).

## Step B.5 — Reset F07 state.json + run orchestrator resume

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path(".autopilot/state/F07/state.json")
s = json.loads(p.read_text())
s["phase"] = "VERIFIED"
s["current_round"] = 0
s["consecutive_clean_rounds"] = 0
s["halt_reason"] = None
s["halt_artifact_path"] = None
s["fixed_finding_hashes"] = []
# v0.2.2 added confirmation_rounds_after_last_fix tracking; reset if exists
if "rounds_since_last_fix" in s:
    s["rounds_since_last_fix"] = 0
p.write_text(json.dumps(s, indent=4) + "\n")
print("F07 state reset to VERIFIED, round counters zeroed")
PY

# Confirm reset
cat .autopilot/state/F07/state.json | python -m json.tool | head -15

# Concurrency check
ls .git/*.lock 2>/dev/null
# MUST empty

# RUN
python -m tools.autopilot resume F07
```

**Wait for orchestrator to complete.** Watch output. Outcomes:

- **READY** → orchestrator wrote `.autopilot/state/F07/ready-report.md`,
  exit 0. Proceed to Step B.7.
- **HALT MAX_ROUNDS** → v0.2.2 budget extension worked but cascade still
  exceeded. Read halt-report. Step B.6 escalation.
- **HALT PARSER_UNCERTAIN** → codex parser still confused. Step B.6
  escalation.
- **HALT P0_FOUND / SECURITY_FINDING / ARCH_FINDING** → real critical
  finding. Step B.6 escalation.
- **HALT DETACHED_HEAD** → v0.2.2 R6 P1 fix triggered. Should not happen
  if pre-flight Step B.1 confirmed branch checkout. Investigate.
- **HALT VERIFY_REGRESSION** → orchestrator's fix attempt broke verify.
  Step B.6 escalation.

## Step B.6 — Phase B HALT escalation logic

If orchestrator halted in Step B.5, decision tree:

**Case 1: HALT MAX_ROUNDS or another cascade pattern**

- Read halt-report.md to see codex findings.
- If findings are all P2/P3 (cosmetic) → log as v0.2.4 backlog (next
  release), HALT this prompt with founder-decision request:
  > "F07 orchestrator hit MAX_ROUNDS with P2/P3 cascade after N rounds.
  > Findings deferred to v0.2.4. Founder decides: ship F07 with override
  > + documented residuals OR write follow-up prompt to address."
- If any P0/P1 → fix manually (limited scope: 1-2 files), commit on
  F07 branch, reset state, re-resume orchestrator. ONE retry max from
  this prompt; if cascade continues → escalate to founder.

**Case 2: HALT P0_FOUND / SECURITY_FINDING / ARCH_FINDING**

- Read halt-report. Critical bug → HALT this prompt with founder-decision
  request. Do NOT auto-fix.

**Case 3: HALT VERIFY_REGRESSION**

- Inspect failing verify step. If small fix possible → fix, retry resume.
  If complex → HALT for founder.

**Case 4: HALT DETACHED_HEAD or BRANCH_MISSING**

- Bug in our setup. HALT for founder investigation. Don't try to recover
  automatically (might compound issue).

In all cases, write `.autopilot/state/F07/phase-b-halt-report.md` with:
- Halt reason
- Codex findings (if applicable)
- Recommended action (ship-with-override vs continue iterating)
- Continuation prompt sketch (what next prompt should do)

## Step B.7 — F07 READY: prepare for founder squash

When orchestrator exits with READY:

```bash
cat .autopilot/state/F07/ready-report.md
```

Verify report contains:
- Branch info
- Commits ahead of main
- Diffstat
- Suggested squash command
- Smoke checklist

DO NOT squash F07 to main yourself. F07 is P1 per plan §6.5 — manual
merge by founder. Just prepare report visibility.

## Step B.8 — PHASE B CHECKPOINT REPORT (output verbatim)

```
═══════════════════════════════════════════════════════
PHASE B CHECKPOINT — F07 RESUME RESULT
═══════════════════════════════════════════════════════

Outcome: <READY | HALTED-cascade | HALTED-critical>

If READY:
  ready-report: .autopilot/state/F07/ready-report.md
  Commits ahead of main: <count>
  Diffstat summary: <files +/->
  Codex rounds in this resume: <count>
  Final state: 2× post-fix-confirm achieved at R<X>+R<Y>

If HALTED:
  halt-report: .autopilot/state/F07/phase-b-halt-report.md
  Halt reason: <code>
  Findings (if codex-related): <list>
  Recommendation: <ship-with-override | iterate | escalate>
  Continuation prompt sketch: <brief>

F07 branch: feat/F07-settings (NOT squashed — P1 manual-merge per §6.5)

Proceeding to PHASE C (housekeeping).
═══════════════════════════════════════════════════════
```

---

# PHASE C — Housekeeping + final report

## Step C.1 — Switch back to main

```bash
git checkout main
git status                              # clean
```

## Step C.2 — Tracker update (manual since v0.2.2 made update_status no-op on feature branches)

Update `docs/implementation-tracker.md` rows:

- W0.7 → ✅ merged (if not already)
- W0.8 → ✅ merged (already done in dashboard restructure session — verify)
- F07 → status reflects current state:
  - If Phase B READY → 🟢 (review pass, ready to merge)
  - If Phase B HALTED → ❌ blocked + Notes describing why

Also update progress totals at bottom of tracker if any cells need
recompute.

```bash
# Inspect tracker first
sed -n '1,80p' docs/implementation-tracker.md

# Edit
nano docs/implementation-tracker.md   # OR python script if scripted

# Add changelog entry at bottom
# | v1.X.X | 2026-05-13 | Post-v0.2.2 ship + F07 phase B status update |

git add docs/implementation-tracker.md
git commit -m "docs(tracker): post v0.2.2 + F07 phase B status update"
git push origin main
```

## Step C.3 — FINAL REPORT (output verbatim)

```
═══════════════════════════════════════════════════════
COMPREHENSIVE v0.2.2 + F07 RESUME — END
═══════════════════════════════════════════════════════

PHASE A: v0.2.2 SHIPPED
  Squash commit: <SHA> on main
  Codex rounds total: <count>
  v0.2.3 backlog items: <count>

PHASE B: F07 RESUME
  Outcome: <READY | HALTED>
  <if READY>: ready-report.md exists; founder squashes manually
  <if HALTED>: phase-b-halt-report.md exists; founder decides path

PHASE C: HOUSEKEEPING
  Tracker updated + pushed

═══════════════════════════════════════════════════════

Founder next steps:

1. <if F07 READY>: Squash F07 to main per ready-report:
     git checkout main
     git pull --ff-only origin main
     git merge --squash feat/F07-settings
     git commit -m "feat(F07): settings /settings — locale + TZ + daily recap"
     git branch -D feat/F07-settings
     git push origin main

   <if F07 HALTED>: Read phase-b-halt-report, decide path forward.

2. After F07 squashed (if applicable):
   - Update tracker.md F07 row to ✅ merged
   - Push tracker update
   - Plan F02 pilot next

3. v0.2.3 backlog (cumulative):
   <list from CHANGELOG known-issues subsection>

End of comprehensive prompt.
═══════════════════════════════════════════════════════
```

Then STOP.

---

## Circuit breakers (apply across all 3 phases)

PAUSE immediately and write halt-report (per phase, named distinctly:
`phase-A-halt.md`, `phase-B-halt.md`, etc.) if ANY trigger fires:

1. Pre-flight regression at any phase boundary.
2. VERIFY_REGRESSION (verify fails 2× consecutively).
3. Push rejected.
4. P0_FOUND in any codex round.
5. SECURITY_FINDING (severe keyword OR soft+P0/P1).
6. ARCH_FINDING (schema/breaking change).
7. RECURRING_FINDING.
8. MAX_FIX_BUDGET_EXHAUSTED (Phase A: 10 fix rounds done without 2× confirm).
9. UNEXPECTED_MERGE_CONFLICT (Phase B: file conflict not in expected list).
10. MERGE_INCOMPLETE (v0.2.2 features missing on F07 after merge).
11. PHASE_B_ORCHESTRATOR_HALT_CRITICAL (Phase B: orchestrator halts with
    P0/P1/security/arch — not auto-fixable).
12. CONCURRENT_AGENT_DETECTED (`.git/*.lock` present mid-flight).
13. DETACHED_HEAD detected unexpectedly (mid-phase).
14. TYPE_IGNORE_PROPOSED.
15. SCOPE_CREEP (modifications outside expected file list per step).
16. Tool error 2× in a row.
17. Context budget >70% — pause + halt with clear continuation hint
    indicating which phase + step was active.

### Halt report template (per-phase)

```
HALT — Comprehensive prompt — Phase <A|B|C>.

Step:    <step number + description>
Trigger: <one of 17>
Branch:  <current>
HEAD:    <SHA>

Phase A status: <not started | in progress (rounds R1-RN) | shipped to main>
Phase B status: <not started | in progress | READY | HALTED>
Phase C status: <not started | tracker updated | done>

Detail:
<error / finding excerpt / continuation hint>

Codex sequence (Phase A):
  R1: ... → fix ...
  R2: ...
  ... (cumulative)

Files modified this session: <list>

Continuation hint:
<specific next-prompt sketch>

Founder action requested:
<specific question or decision needed>
```

---

## Global rules

1. READ FIRST. All required reading before writing any code.
2. Each phase's pre-flight + checkpoint report is MANDATORY. Do not skip.
3. Single Claude Code session on this repo. ZERO concurrency tolerance.
4. Atomic commits — one logical change per commit.
5. Cascade-tolerant Phase A: up to 10 fix rounds + 2 confirm.
6. Cascade-tolerant Phase B: orchestrator's own (5+2) budget; ONE retry
   from this prompt if cascade halts mid-Phase B.
7. P1 manual-merge for F07 — Phase B ends at READY, not at squash.
8. Defer cosmetic findings (P2/P3) to CHANGELOG v0.2.3 known-issues
   if cascade tail is long (round ≥7 in Phase A).
9. Verify before claiming done — re-run pytest after every fix.
10. Tool error 2× → circuit breaker, don't retry blindly.
11. Context budget >70% → halt with clear continuation hint.
12. NEVER force-push.
13. NEVER `# type: ignore`.

Begin with Pre-flight, then Phase A Step A.1. Execute through Phase C
Step C.3 final report. Output checkpoint reports verbatim at end of each
phase before proceeding.
