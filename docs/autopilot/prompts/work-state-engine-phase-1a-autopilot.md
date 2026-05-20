# Autopilot Prompt — work-state engine Phase 1a (core + filesystem + git collectors)

> Spec source: `docs/operations/dashboard-plan-state-split.md` v1.2.1 Accepted (founder sign-off 2026-05-20)
> Phase 0 audit: `docs/operations/phase-0-audit-report-2026-05-20.md` v1.0.0
> Linear ticket: [MYM-1](https://linear.app/maingocanh/team/MYM/issue/MYM-1) (created 2026-05-20, project Work-State Engine, milestone Phase 1a). Placeholders below already substituted with `MYM-1`.

---

```
Task: work-state-engine Phase 1a — Core engine modules + filesystem & git collectors
You are working in /Users/maingocanh/Projects/MyMoneyWent on MyMoneyWent (multi-tenant
personal finance bot, dual-market VN+Global). NO prior conversation context. This
prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-1-work-state-engine-1a`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY
on circuit-breaker conditions (§14).

Risk tier:          P1 (Phase 1a deliverable scope = new module, no production touch)
Merge policy:       manual_only (per CLAUDE.md hard rule #6 + template §3.2 P1)
Autopilot maturity: pilot (first engine implementation run on MMW work-state spec)
Codex review:       2x_consecutive_clean required (P1 Standard Lane)

Context (NOT for execution, just background):
- Spec dashboard-plan-state-split.md v1.2.1 Accepted 2026-05-20 sau Codex 3 rounds (23 findings resolved) + founder sign-off Foundation Lane gate.
- Phase 0 audit done — tracker schema gap mapped, defaults strategy locked, .gitignore ready.
- Phase 1a = bootstrap engine core + 2 simplest collectors. Foundation cho Phase 1b (github/ci) + 1c (railway/persistence) sau.
- Overall spec is P0/Foundation; Phase 1a sub-classified P1 because module is new (no breaking change to existing code).

Scope of this prompt: ONLY Phase 1a per spec §10:
  scripts/work_state/__init__.py
  scripts/work_state/models.py            # WorkItem, Signals, CurrentState, Event dataclasses
  scripts/work_state/plan_reader.py       # tracker.md → WorkItem with defaults strategy from Phase 0 §2.2
  scripts/work_state/event_engine.py      # signal diff → event with write-time dedup per spec §7.2.1
  scripts/work_state/status_machine.py    # compute_status(signals) → Status per spec §8.1
  scripts/work_state/progress.py          # progress profiles per spec §9.1 (standard_feature only this phase)
  scripts/work_state/state_store.py       # .dashboard/ JSON IO (current_state.json + events.jsonl)
  scripts/work_state/signal_collectors/__init__.py
  scripts/work_state/signal_collectors/filesystem.py  # spec_exists, tech_exists, possible_spec_moved per §6.1
  scripts/work_state/signal_collectors/git.py         # branch_exists, commits_count, last_commit_sha per §6.2
  tests/unit/work_state/                  # 5-category coverage per Wave 0 lessons

Do NOT touch:
  - signal_collectors/github.py (Phase 1b)
  - signal_collectors/ci.py (Phase 1b)
  - signal_collectors/railway.py (Phase 1c)
  - projections/dashboard.py (Phase 1b)
  - scripts/build-dashboard.py (Phase 1b refactor)
  - .github/workflows/dashboard.yml (Phase 1c persistence + triggers)
  - docs/implementation-tracker.md schema (Phase 3 cutover)
  - .importlinter (no boundary changes needed for new module)

Out-of-scope-but-documented:
  - github + ci collectors → Phase 1b autopilot prompt (separate, after this merges)
  - Railway deploy signal → Phase 1c autopilot prompt
  - Foundation milestone marker detection (codex-approved label, founder sign-off marker) → Phase 1b GitHub collector responsibility
  - Dashboard projection wiring → Phase 1b
  - Tracker schema migration → Phase 3 cutover (gated by Phase 2 confidence window)

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-plan-state-split.md v1.2.1 — focus:
   - §3 Manual vs derived field boundary (19-field table)
   - §4 + §4.1 Work item schema + multi-branch aggregation matrix (lattice §4.1.1, overlay union §4.1.2, urgency §4.1.3)
   - §6.1 Filesystem signals (spec_exists, tech_exists, possible_spec_moved)
   - §6.2 Git signals (branch_exists, commits_count, last_commit_sha, main_contains_merge)
   - §7.1 Event log format + §7.2 trigger/event/transition map + §7.2.1 per-event-type dedup keys
   - §7.3 State store (.dashboard/current_state.json + events.jsonl)
   - §8.0 Human status projection + §8.1 compute_status() base + §8.2 canonical overlay enum + §8.2.1 naming convention (kebab overlay vs snake warning)
   - §9.1 standard_feature progress profile
   - §11.1 module structure + §11.2 dataclass sketches (WorkItem, Signals, CurrentState)
   - §13 Acceptance criteria — AC1a, AC1b, AC1c (fs+git subset), AC1d, AC1e, AC1f, AC11d, AC11e, AC19, AC24 are in scope

2. docs/operations/phase-0-audit-report-2026-05-20.md — focus:
   - §2.2 Default strategy table (10+ fields engine must infer from tracker)
   - §2.3 Sample inference run for `funding-sources` row
   - §3 Per-row audit summary (46 rows, 7 merged, 32 not-started, 5 deferred, 2 active)
   - §4 Decisions locked (tracker schema NOT migrated pre-Phase 1)

3. docs/operations/walkthrough-foundation-lane-example.md v1.0.1 — focus:
   - §5 Differences vs Standard Lane (test categories, sign-off marker conventions)
   - §6 Failure modes (CI fail, scope creep)

4. CLAUDE.md — focus hard rules #1, #3, #4, #5, #7, #8

5. docs/implementation-tracker.md — sample 5-10 real rows for plan_reader test fixtures (DO NOT modify — read-only)

Pre-flight gate (HARD — halt if any fails):

> **2026-05-20 adjustment:** Pre-flight rewritten to assume engine-1a worktree as cwd + branch
> `feat/MYM-1-work-state-engine-1a` already created (points to main's HEAD post-rebase). The
> original "start from main + checkout -b" assumption no longer matches reality: kickoff commit
> ac1873e (tracker row + this prompt file + dashboard regen) is already on main.

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-engine-1a
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-1-work-state-engine-1a (branch exists, pointing to main's HEAD post-rebase)
git fetch origin
git log --oneline origin/main..HEAD -5  # verify feat branch ahead of (or equal to) origin/main — no rebase debt
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat branch behind origin/main — rebase before proceeding"; exit 1; }
git log --oneline -3                    # 7b705cf or later (post-dashboard auto-rebuild)

source .venv/bin/activate
which python                            # MUST resolve to .venv/bin/python
python --version                        # 3.11.x
which gh                                # MUST resolve (used by future collectors)

ruff check .
black --check .
mypy scripts/                            # baseline must be clean
lint-imports                            # 4-5 contracts pass
pytest tests/ -v --tb=short             # ALL existing tests MUST pass

# Phase 0 prereqs
grep -q "^\.dashboard/$" .gitignore     # MUST find — .gitignore entry from Phase 0 commit
test -f docs/operations/dashboard-plan-state-split.md
head -5 docs/operations/dashboard-plan-state-split.md | grep "v1.2.1"  # spec at correct version

# Linear ticket: MYM-1 (substituted into branch + PR refs throughout prompt)
grep -q "feat/MYM-1-work-state-engine-1a" "$0" 2>/dev/null  # sanity check (best-effort)

# python -m tools.autopilot preflight   # SKIPPED 2026-05-20: known to fail branch-check
                                         # (expects main, we run from feat). Branch
                                         # creation handled by Step 1 below; orchestrator
                                         # lock check not needed for claude-p-headless mode.
```

ALL must pass. If any fails → HALT and report. Do not proceed.

Anti-patterns (NEVER do):

* `git push --force`
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed; mypy strict on `scripts/`)
* Auto-merge ngoài STOP_AT_READY (P1 manual_only per §3.2)
* Touch out-of-scope modules/branches (signal_collectors/github.py, /ci.py, /railway.py, build-dashboard.py, workflows/)
* Skip TDD gate — every new function needs failing tests BEFORE implementation
* Use synthetic mock for plan_reader tests — MUST use real rows from docs/implementation-tracker.md as fixtures (mirrored read-only). Reason: synthetic fixtures would hide tracker schema bugs.
* Hardcode tracker schema assumptions — plan_reader phải robust against missing fields per Phase 0 §2.2 defaults strategy
* Modify existing scripts/build-dashboard.py — Phase 1b scope
* Skip Codex review rounds — P1 needs 2× consecutive clean per template §3.2

Numbered steps:

```bash
# Step 1 — Confirm on feat branch + state dir
# Branch was pre-created during kickoff (ac1873e on main: tracker row + this prompt + dashboard).
# In engine-1a worktree we're already on the branch; idempotent checkout (no -b) is safe.
git checkout feat/MYM-1-work-state-engine-1a
git rev-parse HEAD > /tmp/work-state-1a-base-sha.txt
mkdir -p .autopilot/state/work-state-1a/codex
```

Step 2 — TDD: write models tests FIRST (file: tests/unit/work_state/test_models.py)

Tests cover: WorkItem dataclass with all 18 fields + linear_id optional + frozen + repr;
Signals dataclass mutable + warnings list; CurrentState includes human_status + runtime_urgency
+ overlays list + last_event_ts; Event dataclass for events.jsonl shape per §7.1.

Run pytest tests/unit/work_state/test_models.py — these MUST FAIL on current main.
If tests pass on first run → something's off. Investigate before proceeding.

Step 3 — Implement scripts/work_state/models.py per spec §11.2.

Per spec §11.2 + Codex round 1 Finding 1 fix: WorkItem MUST have separate `id` and `linear_id`
fields (linear_id Optional). Per §8.2.1 naming convention: overlays kebab-case, warning codes
snake_case — encode as typed enums if practical.

Re-run tests → green.

Atomic commit:
```bash
git add tests/unit/work_state/test_models.py
git commit -m "test(work-state): WorkItem + Signals + CurrentState + Event dataclass shape"

git add scripts/work_state/__init__.py scripts/work_state/models.py
git commit -m "feat(work-state): canonical dataclass models per spec §11.2"
```

Step 4 — TDD: status_machine tests (file: tests/unit/work_state/test_status_machine.py)

Cover: compute_status first-match priority per §8.1 — deploy_state==deployed → 'deployed';
deploy_state==deploying → 'deploying'; pr_state==merged → 'merged' (regardless of deploy-failed
overlay per §8.1 note); pr_state==closed → 'abandoned'; pr_state==open + review approved →
'approved-pending-merge'; pr_state==open + review changes-requested → 'changes-requested';
pr_state==open default → 'in-review'; pr_state==draft → 'in-progress'; branch_exists +
commits_count>0 → 'in-progress'; branch_exists only → 'branch-created'; tech_exists →
'tech-ready'; spec_exists → 'spec-only'; else → 'not-started'.

Plus human_status projection per §8.0 — 9 buckets (BACKLOG/TODO/IN_PROGRESS/WAITING/FAILING/
BLOCKED/DONE/ABANDONED/UNKNOWN) with resolution precedence (overlay > base).

Plus multi-branch aggregation per §4.1.1 lattice + §4.1.2 union examples.

Run pytest — MUST fail.

Step 5 — Implement scripts/work_state/status_machine.py.

```bash
git add tests/unit/work_state/test_status_machine.py
git commit -m "test(work-state): compute_status first-match priority + human projection + multi-branch aggregation"

git add scripts/work_state/status_machine.py
git commit -m "feat(work-state): status state machine per spec §8.1 + §8.0 + §4.1"
```

Step 6 — TDD: filesystem collector (file: tests/unit/work_state/test_filesystem.py)

Cover: spec_exists True khi file at canonical path; spec_exists False khi missing;
possible_spec_moved warning khi canonical missing nhưng glob `docs/features/*{feature_id}*.md`
finds candidate; tech_exists similar; missing_spec_link warning for null spec.product;
unknown-safe (no crash on OSError, return False + log warning).

Use real spec docs as fixtures (docs/features/feature-funding-sources.md exists per spec example).

Step 7 — Implement scripts/work_state/signal_collectors/__init__.py + filesystem.py per §6.1.

```bash
git add tests/unit/work_state/test_filesystem.py
git commit -m "test(work-state): filesystem collector — spec_exists, possible_spec_moved, missing warnings"

git add scripts/work_state/signal_collectors/__init__.py scripts/work_state/signal_collectors/filesystem.py
git commit -m "feat(work-state): filesystem signal collector per spec §6.1"
```

Step 8 — TDD + impl: git collector (signal_collectors/git.py per §6.2)

Cover: branch_exists via `git ls-remote --heads origin <branch>` (mocked via subprocess);
commits_count via `git rev-list --count origin/main..origin/<branch>`; last_commit_sha
(head SHA); git_unknown warning khi network timeout; main_contains_merge skipped this phase
(deferred — phụ thuộc github_pr signal trong Phase 1b).

```bash
git add tests/unit/work_state/test_git.py
git commit -m "test(work-state): git collector — branch_exists, commits_count, unknown-safe network"

git add scripts/work_state/signal_collectors/git.py
git commit -m "feat(work-state): git signal collector per spec §6.2"
```

Step 9 — TDD + impl: plan_reader.py per Phase 0 §2.2 defaults strategy

Tests cover real tracker rows từ docs/implementation-tracker.md (mirror-read fixtures into
tests/unit/work_state/fixtures/tracker_sample.md):
- `funding-sources` row → 8 warnings expected (5 *_inferred + acceptance_unstructured + dependencies_unstructured + missing_linear_id)
- `W0.9` legacy row → linear_id=null, type=infra inferred, progress_profile=foundation_change
- `parser-acb` deferred row → engine handles `⏸️` status, renders as ABANDONED
- placeholder row `(to be created...)` → skipped với warning placeholder_row

Engine warnings list MUST be snake_case per §8.2.1.

Implement plan_reader.py per spec §11.2 model + Phase 0 §2.2 defaults table.

```bash
mkdir -p tests/unit/work_state/fixtures
cp docs/implementation-tracker.md tests/unit/work_state/fixtures/tracker_sample.md  # snapshot
git add tests/unit/work_state/fixtures/tracker_sample.md tests/unit/work_state/test_plan_reader.py
git commit -m "test(work-state): plan_reader real tracker fixture + defaults strategy per Phase 0 §2.2"

git add scripts/work_state/plan_reader.py
git commit -m "feat(work-state): plan_reader tracker normalization with defaults + warnings"
```

Step 10 — TDD + impl: event_engine.py per §7.2.1 dedup table

Tests cover dedup keys per event type table: spec_created keyed by (item, artifact_path);
ci_running/ci_failed/ci_passed keyed by (item, pr_number, check_run_id, conclusion) — re-emit
per check_run_id; deploy events keyed by (item, deployment_id, status); stale_detected max
1× per 24h per (item, threshold_days); tail-bounded read last 100 entries before append.

Append-only JSONL format per §7.1 example.

```bash
git add tests/unit/work_state/test_event_engine.py
git commit -m "test(work-state): event_engine dedup per type table + tail-bounded read"

git add scripts/work_state/event_engine.py
git commit -m "feat(work-state): event engine signal diff + write-time dedup per spec §7.2.1"
```

Step 11 — Implement scripts/work_state/state_store.py (.dashboard/ JSON IO)

Per §7.3: write `.dashboard/current_state.json` + `.dashboard/events.jsonl`. JSON encoder
handles dataclass via dataclasses.asdict. Reader returns None if file missing (first run).

```bash
git add tests/unit/work_state/test_state_store.py
git commit -m "test(work-state): state_store JSON IO + missing-file safe"

git add scripts/work_state/state_store.py
git commit -m "feat(work-state): state store persistence for .dashboard/ runtime state"
```

Step 12 — Implement scripts/work_state/progress.py (standard_feature profile only)

Per §9.1 standard_feature weights table. Other profiles (docs_only, foundation_change,
dashboard_engine) → raise NotImplementedError for Phase 1a (caller fallback). Phase 1b
sẽ extend.

```bash
git add tests/unit/work_state/test_progress.py
git commit -m "test(work-state): progress standard_feature profile per spec §9.1"

git add scripts/work_state/progress.py
git commit -m "feat(work-state): progress.py standard_feature profile (others NotImplemented Phase 1b)"
```

Step 13 — Integration test: end-to-end engine run on real tracker

File: tests/integration/work_state/test_engine_e2e.py

Read real tracker.md → plan_reader normalize → 2 collectors (filesystem + git, mocked git
subprocess) → event_engine diff → state_store write → assert current_state.json contains
46 work items với correct base status + warnings.

```bash
git add tests/integration/work_state/test_engine_e2e.py
git commit -m "test(work-state): integration e2e — tracker → engine → current_state.json"
```

Step 14 — Inline Codex review with ≤5 fix rounds (P1 Standard Lane max 5 per CLAUDE.md hard rule #8)

Round 1:
```bash
codex review --base main 2>&1 | tee .autopilot/state/work-state-1a/codex/round-01.txt
```

Parse Codex output:
* Clean phrases ("LGTM", "no issues found", "approve") → clean
* Otherwise extract findings:
  - P0/P1 → MUST fix this round
  - P2 → fix opportunistically; defer if scope creep
  - Keywords <schema|breaking|architectural> → ARCH_FINDING circuit → HALT
  - Keywords <auth|token|timing|secret|injection> → SECURITY_FINDING circuit → HALT
  - Same finding hash in round N and N+1 → RECURRING_FINDING circuit → HALT

Fix round:
* Apply minimum-viable fix per finding
* Re-run pytest tests/unit/work_state/ + tests/integration/work_state/ — MUST be green
* Commit atomically: fix(work-state): address codex round NN — <summary>

Round 2: repeat. MUST be clean for P1 manual_only merge gate.

If round 5 hit without 2× consecutive clean → MAX_ROUNDS circuit → HALT.

Step 15 — Final verification + STOP_AT_READY

```bash
pytest tests/unit/work_state/ tests/integration/work_state/ -v
ruff check scripts/work_state/ tests/unit/work_state/ tests/integration/work_state/
black --check scripts/work_state/ tests/unit/work_state/ tests/integration/work_state/
mypy scripts/work_state/
lint-imports                            # no boundary violations from new module

# Dogfood: run engine once locally and inspect output
python -c "from scripts.work_state.plan_reader import read_tracker; print(read_tracker('docs/implementation-tracker.md')[:3])"

git push -u origin feat/MYM-1-work-state-engine-1a
```

Report READY_FOR_MANUAL_MERGE — founder reviews + squash-merges manually per CLAUDE.md hard
rule #6. Do NOT auto-merge.

Circuit breakers (named halt conditions):

* ARCH_FINDING — Codex flagged schema/breaking/architectural concern → HALT, escalate to founder
* SECURITY_FINDING — auth/token/secret/timing/injection finding → HALT
* RECURRING_FINDING — same finding hash 2 consecutive rounds → HALT (loop signal)
* TEST_FAIL_BASELINE — existing pytest baseline regresses (393 tests must stay passing) → HALT
* OUT_OF_SCOPE_TOUCH — diff touches files in Negative scope list → HALT, revert
* PRE_FLIGHT_FAIL — any pre-flight step fails → HALT
* MAX_ROUNDS — 5 Codex rounds without 2× consecutive clean → HALT, escalate (P1 Standard cap per CLAUDE.md hard rule #8)
* TYPE_IGNORE_ADDED — any `# type: ignore` added → HALT (founder approval needed)
* LOCK_LOST — `.autopilot/locks/<repo-hash>.lock` released unexpectedly → HALT (per CLAUDE.md hard rule #1)

Halt report shape (if circuit breaks):
```
HALT: <CIRCUIT_NAME>
Round/Step: <N>
Finding/Cause: <short description + file:line>
State: tests <pass/fail count>, last commit <SHA>, branch <name>
Recovery options: <2-3 concrete next actions for founder>
```

Final report shape (READY_FOR_MANUAL_MERGE):
```
READY_FOR_MANUAL_MERGE — work-state engine Phase 1a complete

Branch: feat/MYM-1-work-state-engine-1a
Base SHA: <from /tmp/work-state-1a-base-sha.txt>
HEAD SHA: <current>
Commits: <N> atomic commits

Modules added: scripts/work_state/{__init__.py, models.py, plan_reader.py,
  event_engine.py, status_machine.py, progress.py, state_store.py,
  signal_collectors/__init__.py, signal_collectors/filesystem.py,
  signal_collectors/git.py}

Test coverage: <unit count>/<integration count>, all green.
mypy strict: clean.
ruff + black + import-linter: clean.

Codex review:
- Round 1: <clean | N findings, all addressed>
- Round 2: <clean — MUST be clean for P1 gate>

AC progress (per spec §13):
- AC1a (models.py): ✓
- AC1b (plan_reader.py with defaults): ✓
- AC1c (filesystem + git collectors, unknown-safe): ✓ (Phase 1a subset)
- AC1d (event_engine signal diff + write-time dedup): ✓
- AC1e (status_machine compute_status): ✓
- AC1f (progress.py standard_feature profile): ✓ (other profiles Phase 1b)
- AC11d (multi-branch aggregation matrix): ✓
- AC11e (event dedup per event type): ✓
- AC19 (linear_id separated from id): ✓
- AC24 (possible_spec_moved detection): ✓

Remaining ACs (Phase 1b+): AC1c github+ci+railway subset, AC1g projection,
AC2-AC10, AC11a-c, AC12-AC18, AC20-AC23, AC25.

Phase 1a engine warnings on real tracker run: <count> warnings (expected ~370 for
46 rows × ~8 warnings/row per Phase 0 audit §2.3 estimate).

Founder action: review diff, squash-merge per Foundation Lane gate (CLAUDE.md hard
rule #6). After merge, open Phase 1b autopilot prompt for github+ci collectors +
dashboard projection.
```

Begin with Pre-flight, then Step 1.
```

---

## How to use this prompt (founder)

1. **Linear ticket created** — [MYM-1](https://linear.app/maingocanh/team/MYM/issue/MYM-1):
   - Title: "[Foundation] Work-State Engine — Phase 1a (skeleton + filesystem + git)"
   - Workspace: maingocanh · Team: MyMoneyWent (MYM) · Project: Work-State Engine · Milestone: Phase 1a
   - Priority: High · Status: Todo · Labels: foundation + infrastructure + dashboard
   - Linked spec: `docs/operations/dashboard-plan-state-split.md` v1.2.1
   - Effort: 2 days work + 5 days shadow monitoring buffer
   - Risk tier: P1 manual_only (sub-phase implementation of P0 Foundation spec)

2. **Placeholders already substituted** — `MYM-1` is wired throughout this prompt (branch name + worktree command). No manual edit needed before paste.

3. **Open new Claude Code session** trong project root (worktree pattern recommended per CLAUDE.md hard rule #1 nếu chạy parallel với research branch hiện tại):
   ```bash
   cd /Users/maingocanh/Projects/MyMoneyWent
   git worktree add ../MyMoneyWent-engine-1a -b feat/MYM-1-work-state-engine-1a main
   cd ../MyMoneyWent-engine-1a
   ```

4. **Paste prompt** (everything between the triple-backtick ```...``` markers above) vào fresh Claude Code session.

5. **Walk away** for ~2 hours estimated. Autopilot sẽ STOP_AT_READY và return final report.

6. **Manual review + squash-merge** per Foundation Lane gate. Add founder sign-off comment in PR body per `walkthrough-foundation-lane-example.md` §6 template. PR body MUST contain `Closes MYM-1`.

7. **After merge**: shadow mode 7 days monitoring per spec §10 Phase 1 exit criteria. Then open Phase 1b autopilot prompt cho github+ci collectors + dashboard projection (Linear milestone `Phase 1b — GitHub + CI + Railway collectors`).

## References

- Spec: `docs/operations/dashboard-plan-state-split.md` v1.2.1 §10 Phase 1a + §11.1 modules + §11.2 dataclass
- Phase 0 audit: `docs/operations/phase-0-audit-report-2026-05-20.md`
- Foundation Lane workflow: `docs/operations/walkthrough-foundation-lane-example.md`
- Hard rules: `CLAUDE.md`
- Autopilot template: `docs/autopilot/autopilot-prompt-template.md`
