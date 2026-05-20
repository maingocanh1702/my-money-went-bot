# Autopilot Prompt — work-state engine Phase 1c (driver + aggregation + persistence + workflow)

> **Status:** READY 2026-05-21 · gated by MYM-4 Phase 1b' merge (✅ merged 2396107 2026-05-21).
> **Spec source:** `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 §4.1 + §7.4 + §11.4 + §13 (AC11d + AC13 + AC17).
> **Operational snapshot:** `docs/operations/dashboard-engine/dashboard-architecture-snapshot.md` v1.0.1 §5.
> **Linear ticket:** [MYM-5](https://linear.app/maingocanh/issue/MYM-5) — Phase 1c bundle scope.
> **Predecessors:** MYM-1 (`5072e9e`) · MYM-3 (`3e654cf`) · MYM-4 (`2396107`).

---

## Scope reminder (vs 1a / 1b / 1b' / 1d)

| Phase | Status | Operational milestone scope | This prompt? |
|---|---|---|---|
| 1a | ✅ Merged (MYM-1) | skeleton + fs + git collectors | NO (prerequisite) |
| 1b | ✅ Merged (MYM-3) | github + ci + railway collectors | NO (prerequisite) |
| 1b' | ✅ Merged (MYM-4) | projections/dashboard.py | NO (prerequisite) |
| **1c** | **This prompt (MYM-5)** | **driver + aggregation + persistence + workflow** | **YES (bundle)** |
| 1d | Future | runtime urgency §9.4 + MAX urgency aggregation §4.1.3 | NO (separate prompt) |
| 2 | Future | CI Plan/State boundary enforcement | NO (separate prompt) |

> **Scope reality (locked 2026-05-21):** Linear milestone "Phase 1c" description = "multi-branch aggregation matrix" only. But engine has NO production driver — `aggregate_multi_branch_*` functions exist (Phase 1a baseline) but never called outside test fixtures. Aggregation cannot be "implemented" without driver. Persistence + workflow grouped here per spec §10 original Phase 1c (railway already shipped MYM-3). Bundle scope decision locked với anh 2026-05-21 (Option γ).

---

```
Task: work-state-engine Phase 1c — driver + aggregation + persistence + workflow (bundle scope)
You are working in /Users/maingocanh/Projects/MyMoneyWent-engine-1c on MyMoneyWent
(multi-tenant personal finance bot, dual-market VN+Global). NO prior conversation context.
This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-5-work-state-engine-1c`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY on
circuit-breaker conditions (§Circuit breakers).

Risk tier:          P1 Foundation Lane (touches new module + workflow YAML + CI cache)
Merge policy:       manual_only (CLAUDE.md hard rule #6)
Autopilot maturity: pilot (fourth engine implementation run on MMW work-state spec)
Codex review:       2× consecutive clean required (P1 Foundation Lane)

Prerequisite: MYM-1 + MYM-3 + MYM-4 all merged ✓ on main at `2396107` (or later).
Halts pre-flight if any of:
  scripts/work_state/{models,plan_reader,event_engine,status_machine,progress,state_store}.py
  scripts/work_state/signal_collectors/{filesystem,git,github,ci,railway}.py
  scripts/work_state/projections/dashboard.py
not all present, OR Signals dataclass missing pr_state/ci_state/review_state/deploy_state,
OR aggregate_multi_branch_status/aggregate_multi_branch_overlays missing.

Scope of this prompt — Phase 1c bundle (4 sub-phases):
  Phase A — Engine driver / CLI orchestrator
  Phase B — Multi-branch aggregation wired (AC11d)
  Phase C — .dashboard/ CI persistence (AC17)
  Phase D — Workflow triggers extension (AC13)

Each sub-phase ends với MANDATORY CHECKPOINT (halt-if-skipped per memory
feedback_megaprompt_with_checkpoints_works). Do NOT skip checkpoints.

New files (Phase 1c additions):
  scripts/work_state/engine.py                              # Phase A — production driver + CLI
  tests/unit/work_state/test_engine.py                      # Phase A unit tests
  tests/integration/work_state/test_engine_multi_branch.py  # Phase B integration tests for AC11d

Modified files (Phase 1c):
  .github/workflows/dashboard.yml                           # Phase C + Phase D (cache + triggers)
  scripts/work_state/models.py                              # Phase A optional — add branch_states metadata to CurrentState
  scripts/work_state/status_machine.py                      # Phase B — no behavior change; if any refactor needed for aggregation hook
  scripts/work_state/__init__.py                            # Phase A — export engine CLI

Do NOT touch:
  - scripts/work_state/projections/dashboard.py — MYM-4 baseline, read-only
  - scripts/work_state/signal_collectors/*.py — read-only baseline
  - scripts/work_state/plan_reader.py — read-only baseline (engine consumes its output)
  - scripts/build-dashboard.py — Phase 2 (legacy v2.2 generator, separate from engine)
  - .importlinter — no boundary changes needed (engine.py in scripts/work_state/ sibling)
  - docs/implementation-tracker.md — read-only input (engine reads it as tracker)
  - Any .md file under docs/ — read-only (NEVER delete per CLAUDE.md hard rule #2)

Out-of-scope-but-documented:
  - MAX urgency aggregation §4.1.3 → Phase 1d (gated by runtime_urgency algorithm)
  - Phase 2 promotion (computed → primary status) → requires 7-day shadow ≥95%
  - foundation_change progress milestones AC11c → post-shadow ticket
  - compute_overlays full implementation → Phase 1d combined với urgency
  - build-dashboard.py engine integration → Phase 2 cutover

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-engine/dashboard-plan-state-split.md v1.2.1 — focus:
   - §4.1 Multi-branch aggregation rules (MIN + UNION + partial-progress §4.1.1/4.1.2)
   - §4.1.3 MAX urgency aggregation (DEFERRED to Phase 1d — DO NOT IMPLEMENT)
   - §7.4 Persistence strategy (actions/cache key strategy, cache-warmup, CACHE_SCHEMA_VERSION)
   - §7.5 State cache invalidation
   - §11.1 Module placement (engine.py NEW)
   - §11.2 Model sketch (Signals, CurrentState, BranchState mentioned but optional Phase 1c)
   - §11.4 Dashboard workflow triggers (full event list + anti-loop)
   - §13 AC11d + AC13 + AC17

2. docs/operations/dashboard-engine/dashboard-architecture-snapshot.md v1.0.1 §5 — Phase 1c row

3. CLAUDE.md — focus hard rules:
   - #1 (1-session per .git)
   - #2 (NEVER delete docs)
   - #3 (spec-first)
   - #5 (different-model review P1)
   - #6 (manual_only merge)
   - #7 (single-phase default — exception for mega-prompts với explicit checkpoints, this prompt)
   - #8 (review cap: Foundation Lane 8 rounds, founder approval after 5)

4. Phase 1a/1b/1b' deliverables (READ-ONLY for understanding):
   - scripts/work_state/models.py — WorkItem, Signals, CurrentState dataclasses
   - scripts/work_state/plan_reader.py — tracker → WorkItems pipeline
   - scripts/work_state/status_machine.py — compute_status + aggregate_multi_branch_* functions
   - scripts/work_state/state_store.py — write/read current_state.json
   - scripts/work_state/signal_collectors/*.py — 5 collectors operational
   - scripts/work_state/projections/dashboard.py — projection that READS .dashboard/current_state.json
   - tests/integration/work_state/test_engine_e2e_phase1b.py — current manual e2e wire-up pattern
   - tests/unit/work_state/test_status_machine.py — existing aggregation unit tests

5. .github/workflows/dashboard.yml — current state (push/schedule/workflow_dispatch only)
   .github/workflows/ci.yml — CI workflow naming convention for workflow_run trigger

6. docs/implementation-tracker.md — sample real rows for end-to-end driver dogfood

Pre-flight gate (HARD — halt if any fails):

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-engine-1c
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-5-work-state-engine-1c
git fetch origin
git log --oneline origin/main..HEAD -5  # verify feat ahead/equal to origin/main
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat behind origin/main"; exit 1; }

# Phase 1a + 1b + 1b' prerequisite — all modules must exist on main
for f in __init__.py models.py plan_reader.py event_engine.py status_machine.py \
         progress.py state_store.py \
         signal_collectors/__init__.py signal_collectors/filesystem.py \
         signal_collectors/git.py signal_collectors/github.py \
         signal_collectors/ci.py signal_collectors/railway.py \
         projections/__init__.py projections/dashboard.py; do
  test -f "scripts/work_state/$f" \
    || { echo "FAIL: prerequisite scripts/work_state/$f MISSING"; exit 1; }
done

# Signals dataclass must have 1b extensions
python -c "from scripts.work_state.models import Signals; \
  s = Signals.__dataclass_fields__; \
  assert all(f in s for f in ['pr_state','ci_state','review_state','deploy_state']), \
    'FAIL: Signals missing 1b fields'; print('OK: Signals has 1b fields')"

# Aggregation functions must exist
python -c "from scripts.work_state.status_machine import aggregate_multi_branch_status, aggregate_multi_branch_overlays; \
  print('OK: aggregate functions present')"

# Projection must exist
python -c "from scripts.work_state.projections.dashboard import enrich_dashboard; print('OK: projection wired')"

# .dashboard/ gitignored
grep -q "^\.dashboard/$" .gitignore     || { echo "FAIL: .dashboard/ not in .gitignore"; exit 1; }

source .venv/bin/activate
which python                            # MUST resolve to .venv/bin/python
which gh && gh auth status              # gh CLI authenticated
which codex                             # MUST resolve
which claude                            # MUST resolve

# FULL mypy strict scope per CLAUDE.md style section + memory
# feedback_autopilot_preflight_must_include_tests_mypy.md
# (MYM-4 forced CI-fix because pre-flight only checked scripts/work_state/)
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports                            # 5 contracts pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short  # 213 baseline

# ===== PRE-FLIGHT CHECKPOINT — sentinel for claude self-anchor =====
echo ""
echo "✓✓✓ PRE-FLIGHT PASSED — proceeding to Phase A (Driver/CLI)"
echo ""
```

ALL must pass. If any fails → HALT and report. Do not proceed.

Anti-patterns (NEVER do):

* `git push --force`
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed)
* Auto-merge ngoài STOP_AT_READY (P1 manual_only)
* MODIFY existing Phase 1a/1b/1b' baseline modules beyond minimal exports (engine.py imports from them, doesn't rewrite them)
* Touch `scripts/build-dashboard.py` (Phase 2 cutover)
* Touch `.importlinter` (engine.py is sibling of signal_collectors/, no new boundary)
* Delete or rename existing `.dashboard/current_state.json` schema fields (CurrentState additions OK, removals NOT OK — projection MYM-4 reads schema)
* Skip TDD gate — every Phase A/B step needs failing tests BEFORE implementation
* Mock signal collectors output in driver tests without using existing fixtures (`tests/fixtures/github/`, `tests/fixtures/railway/`)
* Implement MAX urgency aggregation §4.1.3 — DEFERRED to Phase 1d, must NOT slip into Phase 1c
* Implement `runtime_urgency` field computation — Phase 1d. CurrentState.runtime_urgency stays default (`"normal"`) until Phase 1d
* Implement `compute_overlays` full enum (14 overlays) — Phase 1d. Phase 1c only propagates overlays through aggregation, doesn't introduce new overlays
* `xfail` to mask broken AC — only allowed for explicit deferred contracts per memory `feedback_pin_deferred_contracts`
* Skip Codex review rounds — P1 Foundation needs 2× consecutive clean
* Delete or move any `.md` file (CLAUDE.md hard rule #2)
* Skip checkpoint commits between phases — each Phase A/B/C/D must have explicit halt + checkpoint pass before proceeding
* Bundle multiple phases into single commit — atomic step-commits required (≥1 commit per Step)

Numbered steps:

```bash
# ============================================================
# Phase A — Engine Driver / CLI (Steps 1-4)
# Goal: Production-runnable engine that orchestrates WorkItems → Signals → status → state file
# ============================================================

# Step 1 — Confirm on feat branch + create state dir
git status
git branch --show-current
test -d .autopilot/state/work-state-1c/codex \
  || { echo "FAIL: codex artifact dir missing — bootstrap step skipped"; exit 1; }

# Step 2 — TDD: write failing test_engine.py FIRST
# Cover Phase A AC:
#   - test_engine_reads_tracker_to_workitems
#   - test_engine_collects_signals_per_workitem  (single-branch case)
#   - test_engine_writes_current_state_json
#   - test_engine_cli_main_returns_zero_on_success
#   - test_engine_no_network_mode_uses_cached_fixtures
#   - test_engine_handles_missing_tracker_gracefully
#   - test_engine_collects_multi_branch_signals  (multi-branch case, prep for Phase B)
# Run pytest — all should FAIL (engine.py doesn't exist yet).
pytest tests/unit/work_state/test_engine.py -q  # expected FAIL

# Step 3 — Implement scripts/work_state/engine.py:
#   - main(argv) CLI: --tracker PATH (default docs/implementation-tracker.md),
#     --dashboard-dir PATH (default .dashboard/), --no-network flag
#   - run_engine(tracker_path, dashboard_dir, no_network) → list[CurrentState]:
#     * plan_reader.read_tracker(tracker_path) → list[ParsedWorkItem]
#     * For each WorkItem:
#       - If len(workitem.branches) == 0: skip (no branch yet — pre-spec/spec-only)
#       - For each branch in workitem.branches:
#         + Call filesystem + git + github + ci + railway collectors
#         + Build Signals instance
#         + compute_status(signals) → per-branch status
#       - If len(branches) == 1: use that status directly
#       - If len(branches) > 1: aggregate_multi_branch_status + aggregate_multi_branch_overlays
#       - compute_human_status(base_status, overlays, deploy_state)
#       - Build CurrentState with multi-branch detection
#   - state_store.write_current_state(states, dashboard_dir)
# Tests should be ≥70% pass after this step.
pytest tests/unit/work_state/test_engine.py -q

# Step 4 — Polish driver edge cases + CLI integration:
#   - Handle WorkItem.branches[] empty → skip with warning
#   - Handle collectors returning unknown → propagate as unknown (per spec)
#   - Handle network errors gracefully (per --no-network mode)
#   - Ensure idempotency — running twice produces same output
#   - Add __main__.py OR engine.py main() registration so `python -m scripts.work_state.engine` works
# Run unit suite + integration baseline:
pytest tests/unit/work_state/ -q  # should pass 100%
pytest tests/integration/work_state/test_engine_e2e_phase1b.py -q  # regression check
```

### ✅ CHECKPOINT A — Phase A Driver complete (MANDATORY gate)

```bash
# 1. New module files present
test -f scripts/work_state/engine.py
test -f tests/unit/work_state/test_engine.py

# 2. CLI is invokable (smoke test — no need for real tracker)
python -m scripts.work_state.engine --help 2>&1 | grep -qE "tracker|dashboard-dir|no-network" \
  || { echo "FAIL: CLI missing required flags"; exit 1; }

# 3. NO touch to out-of-scope baseline
git diff origin/main --name-only | grep -E '^(scripts/work_state/(plan_reader|event_engine|progress|state_store|signal_collectors/)|scripts/work_state/projections/dashboard\.py|scripts/build-dashboard\.py|\.importlinter)$' \
  && { echo "FAIL: touched out-of-scope baseline"; exit 1; } \
  || echo "OK: scope respected"

# 4. All tests pass (baseline + Phase A new)
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 5. mypy + lint clean (FULL scope per memory)
mypy core markets i18n tests scripts/work_state
lint-imports

# 6. Branch ahead ≥4 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 4 \
  || { echo "FAIL: too few commits"; exit 1; }

# 7. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "FAIL: dirty tree"; exit 1; }

# 8. NO docs deleted
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs deleted"; exit 1; } \
  || echo "OK: no docs deleted"

echo ""
echo "✓✓✓ CHECKPOINT A PASSED — proceeding to Phase B (Aggregation wired)"
echo ""
```

If ANY fails → HALT. Do NOT proceed to Phase B.

```bash
# ============================================================
# Phase B — Multi-branch aggregation wired (Steps 5-7)
# Goal: AC11d implemented end-to-end. aggregate_multi_branch_* called from driver.
# ============================================================

# Step 5 — TDD: integration tests for AC11d matrix
# tests/integration/work_state/test_engine_multi_branch.py
# Cover spec §4.1.2 example matrix (5+ cases):
#   - deployed + (in-review + ci-failing) → base in-review, overlays {ci-failing, partial-progress}
#   - merged + changes-requested → base changes-requested, overlays {partial-progress}
#   - deployed + (merged + deploy-failed) → base merged, overlays {deploy-failed, partial-progress}
#   - (blocked + in-progress) + merged → base in-progress, overlays {blocked, partial-progress}
#   - deployed + deployed → base deployed, no partial-progress
#   - 2 branches both in-progress → no partial-progress (active multi-branch)
#   - 1 abandoned + 1 in-progress → partial-progress (asymmetric terminal)
# Tests fail initially — driver from Phase A doesn't wire aggregation yet OR aggregation produces wrong output.
pytest tests/integration/work_state/test_engine_multi_branch.py -q  # expected FAIL

# Step 6 — Wire aggregate_multi_branch_* into driver
# Modify scripts/work_state/engine.py run_engine():
#   - For WorkItem with len(branches) > 1:
#     * Compute per-branch (status, overlays_for_branch) tuples
#     * branch_data = [(status, overlays_for_branch), ...] for aggregate_multi_branch_overlays
#     * statuses = [s for s, _ in branch_data]
#     * base_status = aggregate_multi_branch_status(statuses)
#     * overlays = aggregate_multi_branch_overlays(branch_data)
#   - For single-branch: keep direct status + overlays from compute_status
# Run integration tests — should pass.
pytest tests/integration/work_state/test_engine_multi_branch.py -q

# Step 7 — Polish: edge cases + dogfood multi-branch
#   - All-abandoned case: aggregate returns "abandoned"
#   - Single-branch with overlays case still works
#   - Multi-branch + unknown signals (railway unknown) → overlay propagates
# Run full test suite + integration matrix:
pytest tests/unit/work_state/ tests/integration/work_state/ -q
```

### ✅ CHECKPOINT B — Phase B Aggregation wired complete

```bash
# 1. Multi-branch integration tests pass
pytest tests/integration/work_state/test_engine_multi_branch.py -q --tb=short

# 2. aggregate_multi_branch_* called in engine.py
grep -q "aggregate_multi_branch" scripts/work_state/engine.py \
  || { echo "FAIL: aggregation not wired in driver"; exit 1; }

# 3. Phase A regressions zero
pytest tests/unit/work_state/test_engine.py tests/integration/work_state/test_engine_e2e_phase1b.py -q

# 4. mypy + lint clean
mypy core markets i18n tests scripts/work_state
lint-imports

# 5. Branch ahead ≥7 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 7

# 6. Working tree clean
test -z "$(git status --porcelain)"

# 7. NO MAX urgency / runtime_urgency / compute_overlays creep
git diff origin/main scripts/work_state/engine.py | grep -E '(MAX\s+urgency|runtime_urgency|compute_overlays)' \
  && { echo "FAIL: Phase 1d scope creep detected"; exit 1; } \
  || echo "OK: Phase 1d scope respected"

echo ""
echo "✓✓✓ CHECKPOINT B PASSED — proceeding to Phase C (CI persistence)"
echo ""
```

```bash
# ============================================================
# Phase C — .dashboard/ CI persistence (Steps 8-9)
# Goal: AC17 actions/cache wired in dashboard.yml. CACHE_SCHEMA_VERSION honored.
# ============================================================

# Step 8 — Update .github/workflows/dashboard.yml:
#   - Add actions/cache@v4 step BEFORE Build dashboard step:
#     - Primary key: dashboard-state-v${CACHE_SCHEMA_VERSION}-main (use env var)
#     - Restore keys: dashboard-state-v${V}-main, dashboard-state-v${V}-
#     - Path: .dashboard/
#   - PR builds (if pull_request event): write-only ephemeral key
#     dashboard-state-v${V}-pr-${PR_NUMBER}
#   - Pin to full commit SHA (per supply-chain best practice — same pattern as actions/checkout)
# Use SHA: actions/cache@d4323d4df104b026a6aa633fdb11d772146be0bf  # v4.2.0 (verify current pinning conventions in workflow)

# Step 9 — CACHE_SCHEMA_VERSION env var handling:
#   - Add env CACHE_SCHEMA_VERSION: "v1" at workflow level (or job level)
#   - Engine.py reads CACHE_SCHEMA_VERSION from env, validates against .dashboard/.schema_version marker file
#   - If marker mismatch → ignore cached .dashboard/, treat as cold start, log warning (cache-warmup overlay candidate)
# This sets foundation for Phase 2 promotion gate (cache-warmup <5% across 100 builds).
```

### ✅ CHECKPOINT C — Phase C CI persistence complete

```bash
# 1. dashboard.yml has actions/cache step
grep -q "actions/cache" .github/workflows/dashboard.yml \
  || { echo "FAIL: actions/cache missing"; exit 1; }

# 2. Primary key references CACHE_SCHEMA_VERSION
grep -qE "dashboard-state-v.+-main" .github/workflows/dashboard.yml \
  || { echo "FAIL: cache key pattern missing"; exit 1; }

# 3. SHA pinning convention preserved
grep -E "actions/cache@[a-f0-9]{40}" .github/workflows/dashboard.yml \
  || { echo "FAIL: actions/cache not SHA-pinned"; exit 1; }

# 4. Engine.py honors CACHE_SCHEMA_VERSION (smoke check)
grep -q "CACHE_SCHEMA_VERSION" scripts/work_state/engine.py \
  || { echo "FAIL: CACHE_SCHEMA_VERSION not honored"; exit 1; }

# 5. NO regression on existing workflow gates
yamllint .github/workflows/dashboard.yml || echo "INFO: yamllint not installed — skip"

# 6. mypy clean
mypy core markets i18n tests scripts/work_state

# 7. Branch ahead ≥9 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 9

# 8. Working tree clean
test -z "$(git status --porcelain)"

echo ""
echo "✓✓✓ CHECKPOINT C PASSED — proceeding to Phase D (Workflow triggers)"
echo ""
```

```bash
# ============================================================
# Phase D — Workflow triggers extension (Steps 10-11)
# Goal: AC13 dashboard.yml triggers on PR, review, CI completion, push, schedule, dispatch.
# ============================================================

# Step 10 — Extend .github/workflows/dashboard.yml on: section per spec §11.4:
#   on:
#     push:
#       branches: [main]
#     pull_request:
#       types: [opened, closed, reopened, synchronize, ready_for_review, converted_to_draft, review_requested, labeled, unlabeled]
#     pull_request_review:
#       types: [submitted, dismissed]
#     workflow_run:
#       workflows: [CI]
#       types: [completed]
#     schedule:
#       - cron: '0 6 * * *'
#     workflow_dispatch:
#
# Step 11 — Anti-loop guard preservation:
#   - Existing `if: github.event_name == 'schedule' || ... || !contains(head_commit.message, 'auto-rebuild')`
#   - Extend `if:` condition to handle pull_request, pull_request_review, workflow_run events
#     (these don't have head_commit.message — guard via event name explicit allow)
#   - Concurrency group preserved (group: dashboard-rebuild, cancel-in-progress: true)
# Test locally via act if available, OR just yamllint + manual review.
```

### ✅ CHECKPOINT D — Phase D Workflow triggers complete

```bash
# 1. All 6 trigger types present in dashboard.yml
for trigger in "push" "pull_request:" "pull_request_review" "workflow_run" "schedule" "workflow_dispatch"; do
  grep -q "$trigger" .github/workflows/dashboard.yml \
    || { echo "FAIL: trigger $trigger missing"; exit 1; }
done

# 2. Anti-loop guard preserved
grep -qE "(auto-rebuild|event_name)" .github/workflows/dashboard.yml \
  || { echo "FAIL: anti-loop guard missing"; exit 1; }

# 3. Concurrency group preserved
grep -q "dashboard-rebuild" .github/workflows/dashboard.yml \
  || { echo "FAIL: concurrency group missing"; exit 1; }

# 4. YAML syntactically valid
python -c "import yaml; yaml.safe_load(open('.github/workflows/dashboard.yml'))" \
  || { echo "FAIL: dashboard.yml YAML invalid"; exit 1; }

# 5. All tests still pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q

# 6. Branch ahead ≥11 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 11

# 7. Working tree clean
test -z "$(git status --porcelain)"

echo ""
echo "✓✓✓ CHECKPOINT D PASSED — Phase D complete. Proceeding to Step 12 (Dogfood)"
echo ""
```

```bash
# ============================================================
# Step 12 — Dogfood end-to-end (engine runs against real tracker)
# ============================================================

# Run engine locally with real tracker + .dashboard/ cache:
mkdir -p /tmp/mym5-dogfood/.dashboard
python -m scripts.work_state.engine \
  --tracker docs/implementation-tracker.md \
  --dashboard-dir /tmp/mym5-dogfood/.dashboard \
  --no-network \
  2>&1 | tee .autopilot/state/work-state-1c/dogfood-run-1.log

# Verify output
ls -la /tmp/mym5-dogfood/.dashboard/current_state.json
python -c "
import json
d = json.load(open('/tmp/mym5-dogfood/.dashboard/current_state.json'))
items = d.get('items', [])
print(f'Engine produced {len(items)} CurrentState entries')
multi_branch = [i for i in items if isinstance(i.get('signals'), dict)]
print(f'Items with signals: {len(multi_branch)}')
"

# Run a SECOND time — verify idempotency (output should be bit-identical
# AFTER stripping last_event_ts which may include monotonic timestamp)
python -m scripts.work_state.engine \
  --tracker docs/implementation-tracker.md \
  --dashboard-dir /tmp/mym5-dogfood/.dashboard \
  --no-network \
  2>&1 | tee .autopilot/state/work-state-1c/dogfood-run-2.log

# Save notes to audit trail
cat > .autopilot/state/work-state-1c/dogfood-notes.md <<EOF
# Phase 1c Dogfood Run

- Date: $(date -Iseconds)
- Tracker: docs/implementation-tracker.md (current state)
- Items produced: $(python -c "import json; print(len(json.load(open('/tmp/mym5-dogfood/.dashboard/current_state.json'))['items']))")
- Multi-branch items: TBD (count items where original WorkItem.branches > 1)
- Notes: idempotency verified by re-running

EOF
```

### ✅ CHECKPOINT E — Phase A/B/C/D codegen + dogfood complete (final Phase A gate)

```bash
# 1. All checkpoints A/B/C/D passed (implicit — we're here)

# 2. Dogfood artifact present
test -f .autopilot/state/work-state-1c/dogfood-notes.md

# 3. Branch ahead ≥12 commits (≥1 per Step + checkpoints)
test "$(git rev-list --count origin/main..HEAD)" -ge 12

# 4. Final test suite green
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 5. mypy strict full scope
mypy core markets i18n tests scripts/work_state

# 6. lint-imports + ruff + black
ruff check .
black --check .
lint-imports

# 7. Working tree clean
test -z "$(git status --porcelain)"

# 8. NO docs deleted
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs deleted"; exit 1; } \
  || echo "OK"

# 9. NO scope creep on Phase 1d/Phase 2 features
git diff origin/main scripts/work_state/engine.py 2>&1 | grep -E '(runtime_urgency|MAX|compute_overlays.*14|primary.*status)' \
  && { echo "FAIL: Phase 1d/2 scope creep"; exit 1; } \
  || echo "OK"

echo ""
echo "✓✓✓ CHECKPOINT E PASSED — Phase A codegen complete. Proceeding to Phase B (Codex review)"
echo ""
```

```bash
# ============================================================
# Step 13 — Codex Review rounds (Foundation Lane: max 8 rounds; founder approval after 5)
# ============================================================

# Round 1: full review of Phase A driver + Phase B aggregation + Phase C cache + Phase D triggers
# Save artifact: .autopilot/state/work-state-1c/codex/round-1-review.md
# Apply fixes if P0/P1/P2 findings exist. Commit fixes per finding (atomic).

# Round 2: full re-review. Goal: CLEAN.
# If Round 2 clean → STOP. P1 Foundation needs 2× consecutive clean.
# If Round 2 has new findings → fix + Round 3. Repeat to max 8 (founder approval after 5).

# Halts:
#   - Same finding flagged ≥2 rounds after fix → RECURRING_FINDING circuit breaker
#   - Round 5 reached without 2× consecutive clean → HALT, founder approval required to continue
```

### ✅ CHECKPOINT F — Phase B Codex Review complete

```bash
# 1. ≥2 codex round artifacts
ls -1 .autopilot/state/work-state-1c/codex/round-*-review.md | wc -l  # ≥2

# 2. Last 2 rounds both clean
for n in $(ls -1 .autopilot/state/work-state-1c/codex/round-*-review.md | sort | tail -2); do
  grep -qE '(^|\s)(P0|P1|P2):' "$n" && { echo "FAIL: round $n has open P-finding"; exit 1; }
done

# 3. Tests + lint still green
pytest tests/unit/work_state/ tests/integration/work_state/ -q
mypy core markets i18n tests scripts/work_state
lint-imports

# 4. No new # type: ignore
git diff origin/main -- scripts/work_state/engine.py | grep -E '^\+.*#\s*type:\s*ignore' \
  && { echo "FAIL: # type: ignore introduced"; exit 1; }

# 5. Working tree clean
test -z "$(git status --porcelain)"

echo ""
echo "✓✓✓ CHECKPOINT F PASSED — ready to emit READY report"
echo ""
```

```bash
# ============================================================
# READY report (emit to stdout + final commit message in audit trail)
# ============================================================

cat <<'EOF'
READY — MYM-5 Phase 1c bundle complete

Branch:    feat/MYM-5-work-state-engine-1c
Commits:   <count>
Tests:     <unit+integration count> passing
Lint:      ruff clean, black clean, mypy strict full-scope clean, lint-imports 5/5
Codex:     <round count> rounds, last 2 clean
Dogfood:   <pass/fail> — see .autopilot/state/work-state-1c/dogfood-notes.md
Phase 1c sub-phases:
  - Phase A Driver/CLI ✓
  - Phase B Aggregation wired (AC11d MIN+UNION+partial-progress) ✓
  - Phase C .dashboard/ CI persistence (AC17) ✓
  - Phase D Workflow triggers extension (AC13) ✓
Out-of-scope confirmed deferred:
  - MAX urgency aggregation §4.1.3 → Phase 1d
  - runtime_urgency derivation → Phase 1d
  - Phase 2 promotion (computed → primary) → Phase 2 (7-day shadow gate)

Next step (founder action — manual squash per P1 manual_only):
  1. Review PR diff (focus: engine.py + dashboard.yml + new tests)
  2. Confirm AC11d + AC13 + AC17 in code
  3. Verify dashboard.yml YAML syntax + cache key pattern + trigger list
  4. Squash-merge with founder sign-off in PR body
  5. Update Linear MYM-5 → Done
  6. Phase 1d queued: runtime_urgency 4-level algorithm + MAX urgency aggregation
EOF

# Save final summary
cat > .autopilot/state/work-state-1c/final-summary.md <<'EOF'
# Phase 1c Final Summary
... (auto-populate based on actual results)
EOF
```

## Circuit breakers (HALT immediately, escalate to founder)

1. **Pre-flight failure** — any prerequisite missing (1a/1b/1b' module, Signals field, aggregation function, venv, gh auth, codex/claude binary).
2. **Out-of-scope touch** — any commit modifying baseline 1a/1b/1b' module beyond minimal exports, OR build-dashboard.py, OR .importlinter.
3. **Phase 1d/Phase 2 scope creep** — `runtime_urgency`, MAX urgency, `compute_overlays` 14-enum, computed-status-as-primary changes. These are FUTURE phases.
4. **Docs deletion** — any `.md` file deleted (CLAUDE.md hard rule #2).
5. **`# type: ignore` introduced** — strict-mode escape hatch needs founder approval.
6. **Recurring Codex finding** — same finding flagged ≥2 rounds after fix attempts.
7. **Review cap reached** — Round 5 without 2× consecutive clean → founder approval required to continue (Foundation Lane max 8).
8. **Test regression** — any 1a/1b/1b' existing test starts failing.
9. **Working tree dirty after step commit** — atomic commit discipline broken.
10. **Branch behind origin/main** — rebase needed; pause for founder.
11. **CHECKPOINT skip** — proceeding to Phase B without CHECKPOINT A pass, etc.
12. **xfail used to mask broken AC** — only for documented deferred contracts.
13. **Sandbox vs host git lock conflict** — `.git/index.lock` present → halt.
14. **YAML parse error in dashboard.yml** — workflow syntax broken.
15. **CACHE_SCHEMA_VERSION misspelled or unhandled** — engine cache invalidation broken.

## Acceptance criteria (mapped to spec §13)

- [ ] **AC11d** — Multi-branch aggregation matrix (§4.1.1, 4.1.2) implemented: MIN-progressed base + UNION overlays + partial-progress per rules. MAX urgency §4.1.3 DEFERRED to Phase 1d.
- [ ] **AC13** — `.github/workflows/dashboard.yml` triggers on PR (multiple types), review (submitted/dismissed), CI completion (workflow_run), main push, schedule, manual_dispatch. Anti-loop guard preserved.
- [ ] **AC17** — CI restores/saves `.dashboard/` via `actions/cache@v4` per §7.4.1. Primary key `dashboard-state-v${V}-main`, PR builds ephemeral key. CACHE_SCHEMA_VERSION honored. Phase 2 promotion gate locked behind cache-warmup <5% across 100 builds.
- [ ] **Engine driver** — `python -m scripts.work_state.engine` produces valid `.dashboard/current_state.json` end-to-end with real tracker. Idempotent re-run produces same output.
- [ ] **Integration tests** — multi-branch aggregation matrix ≥5 cases per §4.1.2 examples table.
- [ ] **Quality gates** — ruff + black + mypy strict (core|markets|i18n|tests|scripts/work_state) + lint-imports 5/5 + pytest no regressions.
- [ ] **Codex** — 2× consecutive clean (P1 Foundation Lane per CLAUDE.md hard rule #5).
- [ ] **No scope creep** — Phase 1d/Phase 2 features absent from diff.

## References

- Linear: [MYM-5](https://linear.app/maingocanh/issue/MYM-5)
- Spec: `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 §4.1 + §7.4 + §11.4 + §13
- Snapshot: `docs/operations/dashboard-engine/dashboard-architecture-snapshot.md` v1.0.1 §5
- Predecessor prompts (read-only reference for patterns):
  - `docs/autopilot/prompts/work-state-engine-phase-1a-autopilot.md`
  - `docs/autopilot/prompts/work-state-engine-phase-1b-autopilot.md`
  - `docs/autopilot/prompts/work-state-engine-1b-projection-autopilot.md`
- CLAUDE.md hard rules: #1, #2, #3, #5, #6, #7, #8
- Memory rules:
  - `feedback_autopilot_preflight_must_include_tests_mypy` — pre-flight gate full scope (MYM-4 lesson)
  - `feedback_megaprompt_with_checkpoints_works` — 4-phase mega-prompt rigor
  - `feedback_claude_p_text_mode_buffering` — monitor via git log poll
  - `feedback_sandbox_git_lock_leak` — sandbox git writes leak locks
  - `feedback_concurrency_one_session` — STRICT 1 session per .git/
  - `feedback_never_auto_delete_docs` — never delete .md files
  - `feedback_pin_deferred_contracts` — xfail only for explicit deferred contracts
  - `feedback_cowork_artifact_bash_400` — monitor via terminal while-loop, NOT Cowork artifact

## How to use this prompt (founder)

```bash
# 1. Commit this prompt + tracker row update to main first (bootstrap)
cd /Users/maingocanh/Projects/MyMoneyWent
git checkout main
git add docs/autopilot/prompts/work-state-engine-1c-autopilot.md \
        docs/implementation-tracker.md
git commit -m "docs(work-state-engine): bootstrap MYM-5 Phase 1c autopilot prompt + tracker row

Ref MYM-5"
git push origin main

# 2. Create worktree
cd /Users/maingocanh/Projects/MyMoneyWent
git worktree add ../MyMoneyWent-engine-1c -b feat/MYM-5-work-state-engine-1c main
cd ../MyMoneyWent-engine-1c
ln -s /Users/maingocanh/Projects/MyMoneyWent/.venv .venv
source .venv/bin/activate
mkdir -p .autopilot/state/work-state-1c/codex

# 3. Fire (background — tee log for audit)
claude -p "$(cat docs/autopilot/prompts/work-state-engine-1c-autopilot.md)" \
  2>&1 | tee .autopilot/state/work-state-1c/run-$(date +%s).log

# 4. Monitor via git log poll (per memory feedback_claude_p_text_mode_buffering)
# Open separate terminal:
cd /Users/maingocanh/Projects/MyMoneyWent-engine-1c
while true; do
  clear
  echo "=== $(date) ==="
  git log --oneline -15
  echo ""
  echo "=== Codex artifacts ==="
  ls -1 .autopilot/state/work-state-1c/codex/ 2>/dev/null || echo "(none yet)"
  echo ""
  echo "=== Process ==="
  ps aux | grep -E "tee.*work-state-1c" | grep -v grep | head -1 || echo "(claude exited)"
  sleep 30
done

# 5. After READY emitted:
#    - gh pr create với founder sign-off body
#    - gh pr checks <num> --watch (CI lint + tests + linear-sync + pr-validate)
#    - On all green: gh pr merge --squash --delete-branch
#    - Update Linear MYM-5 → Done
#    - Phase 1d queued
```

## Estimated effort

- **Codegen Phase A-D (Steps 1-12):** ~90-150 min wallclock
- **Codex Phase B (Step 13):** ~30-60 min (Foundation Lane, expect 3-5 rounds for 4-phase scope)
- **Founder squash + Linear close:** ~10 min
- **CI fix cycle (if any):** ~10-15 min (per MYM-4 lesson, mypy tests/ + isinstance gaps possible)
- **Total wallclock to READY:** ~2.5-4 hours

Compare to predecessors:
- MYM-1 Phase 1a: ~1.5h wallclock (10 modules, 127 tests)
- MYM-3 Phase 1b: ~50min wallclock (3 collectors, 63 tests)
- MYM-4 Phase 1b': ~1h autopilot + 10min CI fix (1 module, 23 tests)
- **MYM-5 Phase 1c: BIGGEST** — 4 sub-phases, ~15-20 tests new, workflow YAML changes, multi-branch orchestration
