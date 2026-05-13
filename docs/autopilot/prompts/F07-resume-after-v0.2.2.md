# Task: Resume F07 with v0.2.2 orchestrator → READY (founder squashes)

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT continuation — Phase B only of comprehensive plan.
v0.2.2 orchestrator already shipped to main (squash `533e9fd`). F07 still
in HALTED state from older session. Merge main into F07, reset state,
run orchestrator resume. End at READY (P1 manual squash by founder per
plan §6.5). Stop at READY.

**Context (NOT for execution, just background):**

v0.2.2 ("autopilot tooling hardening") shipped to main 2026-05-12 22:13.
Squash commit `533e9fd` includes:
- max_review_rounds 3→5; new `confirmation_rounds_after_last_fix=2` knob
- SECURITY_FINDING keyword tiering (severe vs soft)
- Resume syncs git checkout to feature_state.branch (incl. DETACHED_HEAD breaker)
- tracker.update_status no-op on feature branches
- state.load tolerates unknown fields
- codex.save_review_artifact non-clobber via -resumeN suffix
- codex.run_review logs warning on stale-blob SHA mismatch
- docs/autopilot/orchestrator-usage.md concurrency policy

F07 (Settings) is at HEAD `6ffe912` on `feat/F07-settings` with 23 commits
ahead of main. State HALTED with old SECURITY_FINDING reason from session
4 (i18n backtick fix). v0.2.1 fields (`last_active_phase=VERIFIED`)
already populated.

**Concurrency reminder:** 3 incidents during v0.2.2 work confirmed the
"one Claude Code session per repo" policy. **NO other agent may run on
this repo during this prompt's execution.**

## Required reading (READ FIRST, in order)

1. `.autopilot/state/F07/state.json` — current F07 state (HALTED).
2. `.autopilot/state/F07/halt-report.md` — most recent F07 halt context.
3. `.autopilot/state/F07/i18n-fix-halt-report.md` — session 4 halt report.
4. `tools/autopilot/loop.py` — confirm v0.2.2 features merged into main.
5. `docs/features/feature-settings.md` — F07 spec (G4 revised pure-read
   in refactor session 2).
6. `CHANGELOG.md` — v0.2.2 known-issues section + F07 entries.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent

# State validation
git branch --show-current               # MUST: main
git log -1 --oneline                    # MUST: 533e9fd or commit including v0.2.2
git status                              # MUST: clean
git pull --ff-only origin main          # confirm in sync

# F07 branch exists + has 23 commits ahead
git rev-parse --verify feat/F07-settings  # MUST resolve
git log main..feat/F07-settings --oneline | wc -l  # MUST: ~23

# v0.2.2 features verified on main
grep -q "last_active_phase" tools/autopilot/state.py
grep -q "PARSER_UNCERTAIN" tools/autopilot/loop.py
grep -q "confirmation_rounds_after_last_fix" tools/autopilot/loop.py
grep -q "DETACHED_HEAD" tools/autopilot/loop.py
grep -q "SECURITY_KEYWORDS_SEVERE" tools/autopilot/codex.py
# All 5 MUST succeed

# Concurrency check
ls .git/*.lock 2>/dev/null
# MUST be empty

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling baseline green on main
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # capture baseline count
```

If anything diverges → HALT and report.

## Anti-patterns

- Auto-merge F07 to main. F07 is P1 per plan §6.5 — founder squashes
  manually. This prompt ENDS at READY.
- `git push --force`.
- `# type: ignore` (circuit breaker).
- Run other Claude Code sessions on this repo.
- Modify F07 source code outside merge conflict resolution.
- Skip the orchestrator resume step — that's the validation point.
- Apply codex fixes manually IF orchestrator finds them; let orchestrator
  drive its own fix-loop.

---

## Step 1 — Switch to F07 branch

```bash
git checkout feat/F07-settings
git status                              # MUST clean
git log --oneline -3
# Top should be 6ffe912 test(F07): assert regen message contains no literal backticks
```

## Step 2 — Merge main into F07 branch

```bash
git merge main
```

**Outcomes:**

- **Auto-merged clean** → proceed to Step 3.
- **Conflict** (likely on `CHANGELOG.md` and possibly `docs/implementation-tracker.md`,
  `.secrets.baseline`) → resolve per Step 3.
- **"Already up to date"** → main fully merged in earlier; HALT
  `MERGE_NOOP` and investigate. Should not happen.

## Step 3 — Resolve conflicts (if any)

```bash
git status                              # show unmerged files
```

For each conflict:

**`CHANGELOG.md`**: keep both entries (F07 cleanup + v0.2.2 sections concat
under `## [Unreleased]`).

```bash
nano CHANGELOG.md
# Find <<<<<<< / ======= / >>>>>>> markers
# Manually merge keeping all subsections
git add CHANGELOG.md
```

**`docs/implementation-tracker.md`**: keep main's version (post-restructure,
W0.7+W0.8 ✅ marked):

```bash
git checkout --theirs docs/implementation-tracker.md
git add docs/implementation-tracker.md
```

**`.secrets.baseline`** (if conflict): keep main's:

```bash
git checkout --theirs .secrets.baseline
git add .secrets.baseline
```

**Any other unexpected conflict**: HALT `UNEXPECTED_MERGE_CONFLICT` for
founder decision. Don't auto-resolve.

```bash
git status                              # MUST: "All conflicts fixed but you are still merging"
git commit -m "merge: main (v0.2.2 orchestrator + cumulative docs) into feat/F07-settings"
```

## Step 4 — Verify orchestrator code on F07 branch

```bash
# v0.2.1 + v0.2.2 features all present on F07 branch post-merge
grep -q "last_active_phase" tools/autopilot/state.py
grep -q "PARSER_UNCERTAIN" tools/autopilot/loop.py
grep -q "confirmation_rounds_after_last_fix" tools/autopilot/loop.py
grep -q "DETACHED_HEAD" tools/autopilot/loop.py
grep -q "SECURITY_KEYWORDS_SEVERE" tools/autopilot/codex.py
# All 5 MUST succeed

# Tooling green on F07 + v0.2.2 cumulative
source .venv/bin/activate
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
# Expected: F07 baseline (~287 from session 4) + v0.2.2 tests (~10) = ~297 pass
```

If grep fails → HALT `MERGE_INCOMPLETE` (v0.2.2 features missing on F07
after merge — possible bad conflict resolution).

If verify fails → HALT `MERGE_VERIFY_REGRESSION` (likely test from one
side breaks under merged code).

## Step 5 — Reset F07 state.json + run orchestrator resume

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
# v0.2.2 may have added rounds_since_last_fix tracking — reset if present
if "rounds_since_last_fix" in s:
    s["rounds_since_last_fix"] = 0
p.write_text(json.dumps(s, indent=4) + "\n")
print("F07 state reset to VERIFIED")
PY

cat .autopilot/state/F07/state.json | python -m json.tool | head -15

# Concurrency final check
ls .git/*.lock 2>/dev/null               # MUST empty

# RUN
python -m tools.autopilot resume F07
```

**Wait for orchestrator to complete.** Watch output.

**Possible outcomes:**

- **READY** → orchestrator wrote `.autopilot/state/F07/ready-report.md`,
  exit 0. Proceed to Step 6.
- **HALT MAX_ROUNDS** → cascade exceeded even with v0.2.2 expanded budget
  (max=5 fix + 2 confirm). Step 7 escalation.
- **HALT PARSER_UNCERTAIN** → codex parser still confused. Step 7.
- **HALT P0_FOUND / SECURITY_FINDING / ARCH_FINDING** → real critical
  finding. Step 7.
- **HALT DETACHED_HEAD / BRANCH_MISSING** → setup bug. Step 7.
- **HALT VERIFY_REGRESSION** → orchestrator's fix broke verify. Step 7.
- **HALT other** → unexpected. Step 7.

## Step 6 — F07 READY: prepare for founder squash

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

DO NOT squash F07 to main yourself — F07 is P1 per plan §6.5.

Proceed to Step 8 final report.

## Step 7 — Phase B HALT escalation

If orchestrator halted in Step 5, write halt-report context here. DO NOT
auto-fix. The escalation paths:

**Case A: HALT MAX_ROUNDS or cascade pattern**

- Read halt-report.md to see codex findings.
- Categorize findings by severity (P0/P1/P2/P3).
- Categorize by recurring vs new.
- If findings are all P2/P3 cosmetic → log as v0.2.4 backlog candidate
  in halt summary. Founder decides ship-with-override or follow-up
  prompt.
- If any P0/P1 → escalate to founder for fix-or-prompt decision.

**Case B: HALT P0_FOUND / SECURITY_FINDING / ARCH_FINDING**

Critical bug in code or in our setup. Halt-report has details. Founder
must review.

**Case C: HALT VERIFY_REGRESSION**

Orchestrator's fix broke verify. Halt-report explains which step.
Founder may apply manual fix or write follow-up prompt.

**Case D: HALT DETACHED_HEAD / BRANCH_MISSING**

Bug in our setup state. Don't try to recover automatically — risk
compounding. Founder investigates.

In all cases proceed to Step 8 final report with halt details.

## Step 8 — Final report (output verbatim)

```
═══════════════════════════════════════════════════════
F07 RESUME (Phase B) — END
═══════════════════════════════════════════════════════

Outcome: <READY | HALTED-cascade | HALTED-critical>

Pre-flight: PASS
Merge main into F07: <clean | conflict resolved>
Conflicts resolved (if any): <list>
v0.2.2 features verified on F07: PASS
Local verify post-merge: <count> passed

Orchestrator resume:
  Started phase: VERIFIED
  Current_round at end: <N>
  Consecutive_clean_rounds: <N>
  Codex rounds executed in this resume: <N>
  Codex artifacts: .autopilot/state/F07/codex/round-{NN}.txt[-resumeN]

If READY:
  ready-report path: .autopilot/state/F07/ready-report.md
  Commits ahead of main: <count>
  Diffstat summary: <files +/->
  Codex final state: 2× post-fix-confirm at R<X>+R<Y>

If HALTED:
  halt-report path: <path>
  Halt reason: <code + detail>
  Findings (if codex-related):
    - [P_] <summary> at <file>:<line>
  Recommendation: <ship-with-override | iterate | escalate>

═══════════════════════════════════════════════════════

Founder next steps:

1. <if READY:> Squash F07 to main per ready-report:
     git checkout main
     git pull --ff-only origin main
     git merge --squash feat/F07-settings
     git commit -m "feat(F07): settings /settings — locale + TZ + daily recap"
     git branch -D feat/F07-settings
     git push origin main

   Then update tracker F07 row to ✅ merged.

2. <if HALTED:> Read halt-report. Decide path:
     - Override squash (rare; only for cosmetic findings)
     - Manual fix + re-resume
     - Author follow-up autopilot prompt for residual

3. v0.2.3+ backlog (cumulative):
   <list any new findings deferred this session, plus carry-forward
    from CHANGELOG known-issues>

End of F07 resume.
═══════════════════════════════════════════════════════
```

Then STOP.

---

## Circuit breakers

PAUSE immediately and write `.autopilot/state/F07/phase-b-halt-report.md`
if ANY trigger fires:

1. Pre-flight regression.
2. UNEXPECTED_MERGE_CONFLICT (Step 3 file not in expected list).
3. MERGE_INCOMPLETE (Step 4 grep fails).
4. MERGE_VERIFY_REGRESSION (Step 4 verify fails).
5. MERGE_NOOP (Step 2 returns "Already up to date").
6. P0_FOUND in orchestrator codex round.
7. SECURITY_FINDING (severe).
8. ARCH_FINDING.
9. RECURRING_FINDING.
10. PARSER_UNCERTAIN.
11. VERIFY_REGRESSION (orchestrator's fix broke verify).
12. DETACHED_HEAD / BRANCH_MISSING.
13. CONCURRENT_AGENT_DETECTED (`.git/*.lock` mid-flight).
14. Tool error 2× in a row.
15. Context budget >70%.

### Halt report template

```
HALT — F07 resume Phase B circuit broken.

Step:    <step + description>
Trigger: <one of 15>
Branch:  feat/F07-settings (or main if pre-flight failed)
HEAD:    <SHA>

Detail:
<error / finding excerpt>

Pre-flight: <pass | which check failed>
Merge: <not started | clean | conflict | resolved>
Local verify post-merge: <not run | pass | fail>
Orchestrator resume: <not started | started | halted>
  if started: phase = <X>, round = <N>

Files modified this session: <list>

Founder action requested:
<specific question>
```

---

## Global rules

1. READ FIRST. State.json + halt-reports + spec G4 before any action.
2. SCOPE: Phase B only. Don't touch v0.2.2 work; don't squash F07.
3. NEVER force-push.
4. NEVER `# type: ignore`.
5. Atomic commits — merge commit only (Step 3). No other commits in this
   prompt scope (orchestrator handles its own).
6. Verify after merge (Step 4) before resume.
7. Tool error 2× → circuit breaker.
8. Context budget >70% → pause + halt with continuation hint.
9. Concurrency check before resume (Step 5) — `.git/*.lock` MUST empty.
10. F07 P1 manual-merge — Phase B ends at READY, founder squashes.

Begin with Pre-flight, then Step 1. Execute through Step 8.
