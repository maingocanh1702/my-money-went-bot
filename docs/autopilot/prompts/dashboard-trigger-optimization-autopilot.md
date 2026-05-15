# Task: Dashboard workflow trigger optimization — reduce CI minutes

You are working in `/Users/maingocanh/Projects/MyMoneyWent` on MyMoneyWent — VN-first personal finance tracker. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single branch `chore/dashboard-trigger-optimization`, P2 pilot manual_only, STOP_AT_READY. Pause ONLY on circuit-breaker conditions.

```
Risk tier:          P2
Merge policy:       manual_only (P2 pilot — first run on workflow-yaml-edit class)
Autopilot maturity: pilot
Codex review:       1x_clean
```

---

## Context (NOT for execution, just background)

Hôm nay 2026-05-15 founder phát hiện 1 workflow run (Rebuild dashboard #100, commit `203e02e`) bị stuck 21+ phút IN_PROGRESS do GitHub Actions free-tier queue starvation. Pattern observed: 5 feature merges trong cascade → workflow fired ~30 lần/ngày → CI minutes saturate. Skip-if-no-diff logic đã có sẵn (dòng 60-72 của dashboard.yml) — không tạo empty commits, nhưng vẫn tốn CI minutes mỗi lần fire.

Documented in `docs/operations/c1-cascade-retrospective.md` §5.6 (Dashboard auto-rebuild noise) + memory `project_dashboard_auto_gen`.

---

## Scope of this prompt: ONLY edit .github/workflows/dashboard.yml triggers

### Positive scope

1. Edit `.github/workflows/dashboard.yml`:
   - **Drop branch push triggers** (keep only `main`):
     - Remove `'feat/**'`, `'infra/**'`, `'chore/**'`, `'fix/**'` from `on.push.branches` list.
   - **Change schedule from hourly to daily 6 AM UTC:**
     - `cron: '0 * * * *'` → `cron: '0 6 * * *'`
     - Add inline comment: `# daily 6 AM UTC (1 PM Vietnam time), down from hourly`
2. Single atomic commit on branch `chore/dashboard-trigger-optimization`.
3. Verify locally: yaml syntax valid via Python parser.
4. Codex 1× clean review.
5. STOP_AT_READY — founder squash + push + merge manually.

### Negative scope (do NOT touch)

- **Skip-if-no-diff logic** (lines 57-73 of dashboard.yml) — already correct, leave verbatim.
- **Job permissions, concurrency group, checkout pinning** — all stay as-is.
- **Other workflow files** (`ci.yml`, `linear-status-sync.yml`, `pr-validate.yml`) — out of scope.
- **Production code, tests, docs** — none of these change.
- **scripts/build-dashboard.py** — generator script untouched.

### Out-of-scope but documented

- Pre-commit hook on local that auto-rebuilds dashboard (separate concern, not changed here).
- Dashboard parser brittleness re: kebab-case feature IDs — already fixed in earlier PR (`13654c8`).

---

## Required reading (READ FIRST, in this order, before any code)

1. `.github/workflows/dashboard.yml` (full file, 73 lines) — note current trigger config + existing skip-if-no-diff logic at lines 57-73.
2. `docs/operations/c1-cascade-retrospective.md` §5.6 — context why optimizing.
3. Memory references (do NOT edit):
   - `project_dashboard_auto_gen` — dashboard auto-gen invariants
   - `feedback_activate_venv_before_commit` — pre-commit hook needs venv
   - `feedback_autopilot_prompt_template` — template rules

---

## Pre-flight gate

```bash
cd /Users/maingocanh/Projects/MyMoneyWent

# Clean state checks
git status                                  # MUST be clean
git branch --show-current                   # MUST be: main
git fetch origin
git pull --ff-only origin main              # MUST succeed

# Venv + tools
source .venv/bin/activate
which lint-imports                          # MUST resolve (memory: feedback_activate_venv_before_commit)
which python                                # MUST resolve

# No other Claude Code session writing refs
ls .git/*.lock 2>/dev/null                  # MUST be empty

# Verify branch doesn't already exist (handle prior cleanup state)
git branch -a | grep chore/dashboard-trigger-optimization && echo "BRANCH EXISTS — investigate" || echo "ready to create"

# Verify current workflow file is at known state (sanity check)
grep -n "cron: '0 \* \* \* \*'" .github/workflows/dashboard.yml
                                            # MUST find exactly 1 match on line 12
grep -nE "'feat/\*\*'|'infra/\*\*'|'chore/\*\*'|'fix/\*\*'" .github/workflows/dashboard.yml
                                            # MUST find 4 matches (one per branch glob)

# gh CLI auth
gh auth status                              # MUST be authenticated
```

ALL must pass. If any fails → HALT and report. Do not proceed.

---

## Anti-patterns (NEVER do)

* `git push --force` / `--force-with-lease`. Reason: rewrites history (memory `feedback_concurrency_one_session`).
* Touch any file other than `.github/workflows/dashboard.yml`. Reason: scope discipline.
* Modify skip-if-no-diff logic (lines 57-73). Reason: already correct, out-of-scope.
* Change job `runs-on`, `permissions`, `concurrency`, or `checkout` pinning. Reason: out of scope; supply-chain best practice.
* Add `# type: ignore` anywhere. Reason: circuit breaker — founder approval needed.
* Auto-merge (P2 pilot = manual_only). Reason: opt-in policy not granted.
* Bundle commit + push + cleanup in same shell block. Reason: memory `feedback_activate_venv_before_commit` — verify HEAD advanced before cleanup.
* Use sed/awk on yaml file. Reason: indent breakage risk; use targeted edits via text editor.

---

## Step 1 — Branch + state setup

```bash
git checkout -b chore/dashboard-trigger-optimization
git rev-parse HEAD > /tmp/dashboard-optimization-base-sha.txt
mkdir -p .autopilot/state/dashboard-optimization/codex
```

## Step 2 — Edit `.github/workflows/dashboard.yml`

Apply 2 changes (use text editor, NOT sed/awk):

**Change 1: Replace push.branches block + cron schedule**

Find this exact block (lines 3-13):

```yaml
on:
  push:
    branches:
      - main
      - 'feat/**'
      - 'infra/**'
      - 'chore/**'
      - 'fix/**'
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:
```

Replace with:

```yaml
on:
  push:
    branches:
      - main
  schedule:
    - cron: '0 6 * * *'   # daily 6 AM UTC (1 PM Vietnam time), down from hourly
  workflow_dispatch:
```

Verify:
```bash
cat .github/workflows/dashboard.yml | head -15
# Should show:
#   on:
#     push:
#       branches:
#         - main
#     schedule:
#       - cron: '0 6 * * *'   # daily 6 AM UTC (1 PM Vietnam time), down from hourly
#     workflow_dispatch:

grep -c "feat/\*\*\|infra/\*\*\|chore/\*\*\|fix/\*\*" .github/workflows/dashboard.yml
# MUST output: 0  (no branch globs remain)

grep "cron:" .github/workflows/dashboard.yml
# MUST output: '0 6 * * *' only (no hourly)
```

If any verify check fails → HALT, report what file actually contains.

## Step 3 — Yaml syntax validation

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/dashboard.yml'))"
# MUST exit 0 (no exception)
```

If yaml parse fails → HALT, fix indentation. Common pitfall: cron value must stay quoted with single quotes.

## Step 4 — Atomic commit

```bash
git add .github/workflows/dashboard.yml
git status                                  # verify only this file staged
git diff --cached                           # review diff

git commit -m "ci(dashboard): reduce trigger scope to main + daily schedule

Optimization to reduce GH Actions CI minutes consumption.

Changes:
- Drop push triggers on feat/**, infra/**, chore/**, fix/** branches.
  Feature branch pushes don't need to rebuild main's dashboard.
  Workflow still fires on main pushes (where real dashboard changes happen).
- Change schedule from hourly (0 * * * *) to daily 6 AM UTC (0 6 * * *).
  Hourly runs mostly skip-commit (skip-if-no-diff already in place at
  lines 57-73), but still consume CI minutes. Daily is sufficient safety
  net for manual tracker edits that don't go through push.

Net effect:
- Before: ~30 CI runs/day (24 hourly + ~6 push)
- After:  ~7 CI runs/day (1 daily + ~6 push)
- Commit noise unchanged (already filtered by skip-if-no-diff)

Skip-if-no-diff logic preserved verbatim. No production code touched.
Related observation: docs/operations/c1-cascade-retrospective.md §5.6
(Dashboard auto-rebuild noise)."

# Verify commit landed before cleanup
git log -1 --format='%h %s'
# Should show new commit with optimization message
```

Pre-commit hook should pass (no Python files changed → lint-imports skips).

## Step 5 — Push branch + verify

```bash
git push -u origin chore/dashboard-trigger-optimization

# Verify workflow file still parseable by GH
gh workflow list | grep -i dashboard
# Should show "Rebuild dashboard" entry

# Note: workflow_dispatch on branch uses workflow file FROM default branch,
# not from this branch. To verify new triggers actually work, must merge
# first OR open GH UI and select this branch in Run workflow dropdown.
# Don't attempt remote trigger from CLI — just verify locally + Codex review.
```

## Step 6 — Local verify final

```bash
# Confirm no other files dirty
git status                                  # MUST be clean

# Verify yaml syntax + commit history
python -c "import yaml; yaml.safe_load(open('.github/workflows/dashboard.yml'))" && echo "YAML OK"
git log --oneline main..HEAD
# Should show exactly 1 commit on branch

# Verify branch pushed
git ls-remote origin chore/dashboard-trigger-optimization
# MUST return SHA matching HEAD
```

## Step 7 — Codex inline review (P2 pilot = 1× clean target)

```bash
codex review --base main 2>&1 | tee .autopilot/state/dashboard-optimization/codex/round-01.txt
```

Parse output:
- Clean → proceed to READY report.
- Findings:
  - P0/P1 → fix this round.
  - P2 → fix opportunistically; defer to follow-up if scope creep.
  - ARCH_FINDING / SECURITY_FINDING keywords → HALT (unexpected for yaml edit — investigate).
  - RECURRING_FINDING → HALT.

Fix round (if needed): minimum-viable fix, re-run verify, commit atomically:
```bash
git commit -m "fix(ci): address codex round NN — <summary>"
```

Re-run Codex. Target: 1 clean round.

Max 3 rounds. If exhausted without clean → MAX_ROUNDS breaker → HALT.

---

## Circuit breakers

1. **Pre-flight regression** — current workflow file diverges from expected state (line counts, cron value, branch globs).
2. **BRANCH_EXISTS** — `chore/dashboard-trigger-optimization` already exists locally or in worktree. Founder must clean up before retry.
3. **VERIFY_REGRESSION** — yaml parser fails after edit.
4. **WRONG_GLOB_COUNT** — Step 2 grep finds branch globs remaining (incomplete delete).
5. **ARCH_FINDING / SECURITY_FINDING** — Codex flags unexpected concern.
6. **RECURRING_FINDING** — same finding in round N+1.
7. **TYPE_IGNORE_PROPOSED** — anywhere.
8. **MAX_ROUNDS** — 3 Codex rounds without clean.
9. **PUSH_REJECTED** — push to feature branch fails. Do NOT retry with `--force`.
10. **OUT_OF_SCOPE_EDIT** — any file other than `.github/workflows/dashboard.yml` modified.
11. **POLICY_MISMATCH** — anyone attempts auto-merge on this P2 pilot.
12. **CONCURRENCY_DETECTED** — `.git/*.lock` exists during run.
13. **YAML_PARSE_FAIL** — python yaml.safe_load raises exception after edit.

---

## Halt report template

```
HALT — dashboard-trigger-optimization circuit broken.

Step:        <step name>
Trigger:     <one of 13 conditions>
Branch:      chore/dashboard-trigger-optimization
HEAD:        <SHA>

Detail:
<error output OR Codex finding excerpt OR yaml parse error>

State:
- Commits on branch: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/dashboard-optimization/codex/round-*.txt
- Last verify: <pass | fail with check>

Requesting founder input on:
<specific question>
```

---

## Final report — READY (P2 pilot manual_only)

```
═══════════════════════════════════════════════════════
AUTOPILOT dashboard-trigger-optimization — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════

Squash commit:    N/A — founder/manual merge pending
Branch chore/dashboard-trigger-optimization: pushed to origin
Push origin/main: NOT RUN

File modified: .github/workflows/dashboard.yml (only)
Changes:
  - on.push.branches: [main, feat/**, infra/**, chore/**, fix/**] → [main]
  - schedule.cron: '0 * * * *' → '0 6 * * *' (with inline comment)
  - Skip-if-no-diff logic (lines 57-73): UNCHANGED

YAML validation: passed (python yaml.safe_load OK)
Local diff: minimal (~7 line delta)

Codex review:
  Round 01: <findings count | clean>
  Final state: 1 clean round confirmed (P2 pilot policy)
  Artifacts: .autopilot/state/dashboard-optimization/codex/round-*.txt

Decisions made requiring founder review:
  <any non-obvious calls — e.g., codex P2 deferral>

═══════════════════════════════════════════════════════

Suggested squash command (founder runs after review):

  cd /Users/maingocanh/Projects/MyMoneyWent
  git fetch origin
  git checkout main
  git pull --ff-only origin main
  git merge --squash chore/dashboard-trigger-optimization
  git commit -m "ci(dashboard): reduce trigger scope to main + daily schedule

  Drop feat/**, infra/**, chore/**, fix/** push triggers (only main now).
  Change schedule from hourly to daily 6 AM UTC.

  Expected: ~75% reduction in CI run count (~30/day → ~7/day).
  Commit noise unchanged (already filtered by skip-if-no-diff at line 60).

  Related: docs/operations/c1-cascade-retrospective.md §5.6"

  git branch -D chore/dashboard-trigger-optimization
  git push origin main

  # Post-merge verification
  gh workflow run dashboard.yml
  sleep 30
  gh run list --workflow=dashboard.yml --limit 2
  # Latest should be workflow_dispatch + complete in <1min

═══════════════════════════════════════════════════════
```

---

Begin with Pre-flight, then Step 1.
