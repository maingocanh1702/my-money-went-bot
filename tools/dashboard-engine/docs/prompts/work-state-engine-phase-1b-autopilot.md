# Autopilot Prompt — work-state engine Phase 1b (github + ci + railway collectors)

> **Status:** READY 2026-05-20 · gated by MYM-1 Phase 1a merge (✅ merged 5072e9e).
> **Spec source:** `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 §6.3 + §6.4 + §6.5 + §6.7 + §7.4 + §8.1 + §13.
> **Phase 0 audit:** `docs/operations/dashboard-engine/phase-0-audit-report-2026-05-20.md` v1.0.0.
> **Linear ticket:** [MYM-3](https://linear.app/maingocanh/issue/MYM-3) — Phase 1b milestone "GitHub + CI + Railway collectors".
> **Companion:** Phase 1a prompt at `work-state-engine-phase-1a-autopilot.md` (✅ shipped MYM-1).
> **Follow-up:** MYM-4 Phase 1b' (projection) fires after this prompt merges.

---

## Scope reminder (vs 1a + 1b' + 1c)

| Phase | Status | Operational milestone scope | This prompt? |
|---|---|---|---|
| 1a | ✅ Merged (MYM-1) | skeleton + fs + git collectors | NO (prerequisite — merged 2026-05-20 SHA 5072e9e) |
| **1b** | **This prompt (MYM-3)** | **github.py + ci.py + railway.py + PR identity §6.3 + cache TTL** | **YES** |
| 1b' | Future (MYM-4) | projections/dashboard.py — enrich docs/dashboard.json with state block | NO (separate prompt, fires after 1b) |
| 1c | Future | multi-branch aggregation §4.1 + persistence + workflow triggers | NO (separate prompt) |
| 1d | Future | runtime urgency algorithm §9.4 | NO (separate prompt) |

> **Scope reconcile (2026-05-20):** Phase 1b scope matches Linear milestone "Phase 1b — GitHub + CI + Railway collectors" + tracker row + snapshot v1.0.1 §5 (operational consensus). Spec §10 canonical placed projection in 1b — that's split to MYM-4 (1b') for cleaner 1:1 prompt-milestone mapping. Decision rationale per A+ option lock.

---

```
Task: work-state-engine Phase 1b — GitHub + CI + Railway collectors
You are working in /Users/maingocanh/Projects/MyMoneyWent-engine-1b on MyMoneyWent (multi-tenant
personal finance bot, dual-market VN+Global). NO prior conversation context. This
prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-3-work-state-engine-1b`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY
on circuit-breaker conditions (§Circuit breakers).

Risk tier:          P1 (Phase 1b extends Phase 1a module, no production touch)
Merge policy:       manual_only (per CLAUDE.md hard rule #6 + template §3.2 P1)
Autopilot maturity: pilot (second engine implementation run on MMW work-state spec)
Codex review:       2x_consecutive_clean required (P1 Standard Lane)

Prerequisite: Phase 1a (MYM-1) merged to main ✓ at SHA 5072e9e (2026-05-20).
This prompt halts pre-flight if Phase 1a modules
(scripts/work_state/{models,plan_reader,event_engine,status_machine,progress,
state_store,signal_collectors/{__init__,filesystem,git}}.py) not all present.

Scope of this prompt: ONLY Phase 1b per Linear milestone + tracker + snapshot consensus:
  scripts/work_state/signal_collectors/github.py    # PR state + reviews + identity §6.3
  scripts/work_state/signal_collectors/ci.py        # GitHub check-runs §6.6
  scripts/work_state/signal_collectors/railway.py   # Deploy state §6.7 (heuristic OK)
  tests/unit/work_state/test_github.py
  tests/unit/work_state/test_ci.py
  tests/unit/work_state/test_railway.py
  tests/unit/work_state/test_pr_identity.py
  tests/integration/work_state/test_engine_e2e_phase1b.py  # extends 1a e2e với 3 new collectors

Do NOT touch:
  - scripts/work_state/projections/ — MYM-4 Phase 1b' follow-up ticket
  - .dashboard/ CI persistence — Phase 1c
  - .github/workflows/dashboard.yml — Phase 1c
  - scripts/build-dashboard.py — Phase 1c (projection wiring)
  - Existing Phase 1a modules — read-only EXCEPT Signals dataclass APPEND (Step 3)
  - .importlinter (no boundary changes needed)

Out-of-scope-but-documented:
  - Dashboard projection (`projections/dashboard.py`) → MYM-4 Phase 1b' separate ticket
  - .dashboard/ persistence via actions/cache → Phase 1c
  - Multi-branch aggregation (§4.1 lattice) → Phase 1c per snapshot
  - Runtime urgency algorithm (§9.4) → Phase 1d per snapshot
  - CI enforce Plan/State boundary → Phase 2

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-engine/dashboard-plan-state-split.md v1.2.1 — focus:
   - §6.3 PR identity resolution 5-step fallback
   - §6.4 GitHub PR state + review state mapping
   - §6.5 CI check-runs state mapping
   - §6.7 Railway deploy state collector (heuristic acceptable, `unknown` safe)
   - §7.4 Caching strategy (cache TTL, `--no-network` mode, cache-warmup overlay)
   - §8.1 status_machine consumers of pr_state + ci_state + review_state + deploy_state
   - §13 Acceptance criteria — AC1c (full subset for github+ci+railway), AC11a-c (overlays),
     AC11f (cache TTL + --no-network), AC19 (PR identity), AC20 (overlay propagation)

2. docs/operations/dashboard-engine/phase-0-audit-report-2026-05-20.md — focus:
   - §2.2 Default strategy table — extended for github + ci + railway unknowns
   - §3 Per-row audit summary — verify PR mapping for 46 rows still accurate post-1a merge

3. docs/operations/dashboard-engine/walkthrough-foundation-lane-example.md v1.0.1

4. CLAUDE.md — focus hard rules #1, #3, #4, #5, #7, #8

5. Phase 1a deliverable (read-only, merged at 5072e9e):
   - scripts/work_state/models.py — Signals dataclass to APPEND-ONLY extend (pr_state, ci_state, review_state, deploy_state)
   - scripts/work_state/signal_collectors/git.py — pattern for subprocess collectors
   - scripts/work_state/event_engine.py — event types for github_* + ci_* + railway_* events
   - scripts/work_state/status_machine.py — first-match priority chain (existing) — APPEND priorities for new signals

6. docs/implementation-tracker.md — sample 5-10 real rows for collector test fixtures

Pre-flight gate (HARD — halt if any fails):

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-engine-1b
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-3-work-state-engine-1b
git fetch origin
git log --oneline origin/main..HEAD -5  # verify feat ahead/equal to origin/main
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat behind origin/main"; exit 1; }

# Phase 1a prerequisite — ALL 1a modules must exist on main
for f in __init__.py models.py plan_reader.py event_engine.py status_machine.py \
         progress.py state_store.py signal_collectors/__init__.py \
         signal_collectors/filesystem.py signal_collectors/git.py; do
  test -f "scripts/work_state/$f" \
    || { echo "FAIL: Phase 1a prerequisite scripts/work_state/$f MISSING"; exit 1; }
done

source .venv/bin/activate
which python                            # MUST resolve to .venv/bin/python
which gh                                # REQUIRED — used by github + ci collectors
gh auth status                          # MUST be authenticated (not anonymous)
which railway 2>/dev/null \
  || echo "INFO: railway CLI not installed — railway collector will use heuristic mode (HTTP API + token from env)"
which codex                             # MUST resolve
which claude                            # MUST resolve

ruff check .
black --check .
mypy scripts/work_state/                # 1a baseline must still be clean
lint-imports                            # 5 contracts pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short  # 1a tests still green (127 + 6)

# .dashboard/ gitignored from Phase 0
grep -q "^\.dashboard/$" .gitignore     || { echo "FAIL: .dashboard/ not in .gitignore"; exit 1; }

# ===== PRE-FLIGHT CHECKPOINT — sentinel for claude self-anchor =====
echo ""
echo "✓✓✓ PRE-FLIGHT PASSED — proceeding to Phase A (Step 1)"
echo ""
```

ALL must pass. If any fails → HALT and report. Do not proceed.

Anti-patterns (NEVER do):

* `git push --force`
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed)
* Auto-merge ngoài STOP_AT_READY (P1 manual_only per §3.2)
* Touch out-of-scope modules (projections/, build-dashboard.py, workflows/, dashboard.yml)
* MODIFY existing Phase 1a modules — extend Signals dataclass via APPEND-ONLY field additions; status_machine via APPEND-ONLY priority insertions. No rewrites.
* Skip TDD gate — every new function needs failing tests BEFORE implementation
* Mock github/railway API output without real fixtures — use cached real responses as fixtures
* Hardcode PR identity assumptions — plan_reader's existing fallback chain must drive identity §6.3
* Skip cache TTL — every github + ci + railway network call MUST honor cache + `--no-network` mode
* Railway HARD-fail on unreachable — MUST return Signals with deploy_state=`unknown` + warning `railway_unknown` (per spec §6.7)
* Skip Codex review rounds — P1 needs 2× consecutive clean per template §3.2

Numbered steps:

```bash
# Step 1 — Confirm on feat branch + state dir
# Branch pre-created during kickoff (parallel to 1a pattern).
git checkout feat/MYM-3-work-state-engine-1b
git rev-parse HEAD > /tmp/work-state-1b-base-sha.txt
mkdir -p .autopilot/state/work-state-1b/codex
```

Step 2 — TDD: extend Signals dataclass tests (file: tests/unit/work_state/test_models_phase1b.py)

Tests cover NEW Signals fields:
- `pr_state` (enum: draft/open/closed/merged/none)
- `pr_number` (int|None)
- `pr_url` (str|None)
- `ci_state` (enum: pending/success/failure/skipped/unknown)
- `ci_check_run_count` (int)
- `review_state` (enum: none/requested/approved/changes-requested)
- `last_review_at` (datetime|None)
- `deploy_state` (enum: deployed/deploying/deploy-failed/unknown/none) — NEW for Phase 1b railway
- `last_deploy_at` (datetime|None) — NEW for Phase 1b railway

All optional/Unknown-safe defaults. APPEND-ONLY per spec §11.2 invariant.

If Signals extension requires breaking change → HALT ARCH_FINDING circuit.

Run pytest — these MUST FAIL on main.

Step 3 — Extend scripts/work_state/models.py Signals dataclass per spec §11.2.

APPEND fields with `field(default=None)` or appropriate Unknown enum defaults. DO NOT rewrite or reorder existing 1a fields.

```bash
git add tests/unit/work_state/test_models_phase1b.py
git commit -m "test(work-state): extend Signals dataclass +9 fields for pr/ci/review/deploy"

git add scripts/work_state/models.py
git commit -m "feat(work-state): Signals dataclass APPEND pr/ci/review/deploy fields per spec §11.2"
```

Step 4 — TDD: PR identity resolution (file: tests/unit/work_state/test_pr_identity.py)

Cover §6.3 5-step fallback:
1. Tracker row's `linear_id` → search PR via `gh pr list --search "MYM-N"`
2. Tracker row's `branches` field → match PR head branch
3. Tracker row's `id` (feature_id) → search PR title/body
4. Branch name match — exact `feat/MYM-N-<slug>`
5. Fallback: unknown — emit `ambiguous-pr-mapping` overlay warning

Edge cases:
- No PR exists → pr_state = `none`, pr_number = None, NOT halt
- Multiple PRs match → emit `ambiguous-pr-mapping` warning, pick most-recent open
- PR closed but not merged → pr_state = `closed`, distinct from `merged`
- Draft PR → pr_state = `draft` (not `open`)

Use real `gh api repos/$REPO/pulls/$N` fixtures (committed to tests/fixtures/github/).
DO NOT mock subprocess directly — wrap via testable helper.

Step 5 — Implement scripts/work_state/signal_collectors/github.py per §6.3 + §6.4.

Cache TTL: 5 minutes for PR list, 1 minute for individual PR detail.
`--no-network` mode: load from `.dashboard/cache/github_*.json`, emit `stale-cache` overlay
if cache older than TTL × 2. Network unreachable: emit `github_unknown` warning, return
Signals with pr_state=`unknown`.

```bash
git add tests/unit/work_state/test_pr_identity.py tests/fixtures/github/
git commit -m "test(work-state): PR identity 5-step fallback per spec §6.3"

git add scripts/work_state/signal_collectors/github.py
git commit -m "feat(work-state): github collector — PR state + reviews + identity §6.3 + cache TTL"
```

Step 6 — TDD: CI check-runs collector (file: tests/unit/work_state/test_ci.py)

Cover §6.5: ci_state derivation from check-runs aggregate. First-match priority:
- Any check-run failure → ci_state = `failure`
- Any check-run in-progress → ci_state = `pending` + overlay `ci-running`
- All check-runs success → ci_state = `success`
- No check-runs found → ci_state = `unknown` + warning `ci_no_checks`
- Network unreachable → ci_state = `unknown` + warning `ci_unknown`

`ci_check_run_count` = total non-skipped check-runs (skipped excluded from aggregate).

Use real `gh api repos/$REPO/commits/$SHA/check-runs` fixtures.

Step 7 — Implement scripts/work_state/signal_collectors/ci.py per §6.5.

Cache TTL: 30 seconds (CI state changes fast). `--no-network` mode: same pattern as github.py.

```bash
git add tests/unit/work_state/test_ci.py tests/fixtures/github/check-runs/
git commit -m "test(work-state): CI check-runs collector aggregation rules per spec §6.5"

git add scripts/work_state/signal_collectors/ci.py
git commit -m "feat(work-state): ci collector — check-runs aggregate + cache + --no-network"
```

Step 8 — TDD: Railway deploy collector (file: tests/unit/work_state/test_railway.py)

Cover §6.7: deploy_state derivation. Heuristic OK, `unknown` acceptable.

First-match priority:
- Railway API responds + latest deployment status=`SUCCESS` → deploy_state = `deployed`
- Status=`BUILDING` or `DEPLOYING` → deploy_state = `deploying`
- Status=`FAILED` or `CRASHED` → deploy_state = `deploy-failed`
- API unreachable / no token → deploy_state = `unknown` + warning `railway_unknown`
- Project not found → deploy_state = `none` + warning `railway_no_project`

`last_deploy_at` = ISO timestamp of latest deployment attempt (regardless of state).

Edge cases:
- Multi-environment project (staging + prod) → use prod environment only for V1; warning if config doesn't specify
- HTTP timeout (default 5s) → unknown-safe, no exception leakage
- Railway token missing → unknown + warning, NOT halt

Use real Railway GraphQL response fixtures (committed to tests/fixtures/railway/).

Step 9 — Implement scripts/work_state/signal_collectors/railway.py per §6.7.

Cache TTL: 1 minute (deploy state changes slowly). HTTP API approach via `requests` (or stdlib `urllib`) — avoid subprocess to `railway` CLI for portability.

`RAILWAY_TOKEN` env var required for authenticated calls. Token absent → return unknown immediately, no warning suppression.

```bash
git add tests/unit/work_state/test_railway.py tests/fixtures/railway/
git commit -m "test(work-state): railway collector — deploy state + token-missing + timeout safe"

git add scripts/work_state/signal_collectors/railway.py
git commit -m "feat(work-state): railway collector — deploy state §6.7 + unknown-safe + cache"
```

Step 10 — TDD: status_machine extension (file: tests/unit/work_state/test_status_machine_phase1b.py)

Extend Phase 1a's compute_status() to consume pr_state + ci_state + review_state + deploy_state. Per §8.1 first-match priority addition (insert at TOP, highest priority for deploy/PR signals):

- deploy_state==deployed → 'deployed' (HIGHEST)
- deploy_state==deploying → 'deploying'
- deploy_state==deploy-failed → existing status + overlay `deploy-failed`
- pr_state==merged → 'merged'
- pr_state==closed → 'abandoned'
- pr_state==open + ci_state==failure → 'in-review' + overlay `ci-failing`
- pr_state==open + review_state==changes-requested → 'changes-requested'
- pr_state==open + review_state==approved → 'approved-pending-merge'
- pr_state==open default → 'in-review'
- pr_state==draft → 'in-progress'

Phase 1a's pre-PR statuses (`branch-created`, `tech-ready`, `spec-only`, `not-started`) unchanged at lower priority.

Step 11 — Update scripts/work_state/status_machine.py — APPEND priority cases.

DO NOT rewrite existing 1a logic. Insert new cases at correct priority position. Verify Phase 1a tests still pass after extension (regression check).

```bash
git add tests/unit/work_state/test_status_machine_phase1b.py
git commit -m "test(work-state): status_machine consumes pr_state + ci_state + review_state + deploy_state"

git add scripts/work_state/status_machine.py
git commit -m "feat(work-state): status_machine APPEND PR + CI + review + deploy priority cases per §8.1"
```

Step 12 — Integration test: full Phase 1b engine run

File: tests/integration/work_state/test_engine_e2e_phase1b.py

Extend Phase 1a e2e: tracker → plan_reader → 5 collectors (filesystem + git + github + ci + railway, network mocked) → event_engine → state_store → assert current_state.json contains pr_state + ci_state + deploy_state for ≥3 work items with real PR mappings.

Use `--no-network` mode + cached fixtures for deterministic test.

```bash
git add tests/integration/work_state/test_engine_e2e_phase1b.py tests/fixtures/github/ tests/fixtures/railway/
git commit -m "test(work-state): integration e2e Phase 1b — 5 collectors fully wired"
```

---

### ✅ CHECKPOINT A — Phase A Codegen complete (MANDATORY gate)

**Do NOT proceed to Step 13 unless ALL 6 checks below pass.**

```bash
echo "=== CHECKPOINT A — Phase 1b Codegen complete ==="

# 1. All 3 new collector module files present
for f in signal_collectors/github.py signal_collectors/ci.py signal_collectors/railway.py; do
  test -f "scripts/work_state/$f" \
    || { echo "HALT CHECKPOINT_A: scripts/work_state/$f MISSING"; exit 1; }
done
echo "✓ all 3 new collector module files present"

# 2. Phase 1a modules still present (regression check)
for f in models.py plan_reader.py event_engine.py status_machine.py state_store.py \
         progress.py signal_collectors/filesystem.py signal_collectors/git.py; do
  test -f "scripts/work_state/$f" \
    || { echo "HALT CHECKPOINT_A: Phase 1a module $f REMOVED"; exit 1; }
done
echo "✓ Phase 1a modules intact"

# 3. NO touch to out-of-scope projections/
test ! -d "scripts/work_state/projections" \
  || { echo "HALT CHECKPOINT_A: projections/ created (out of scope — MYM-4 Phase 1b')"; exit 1; }
echo "✓ projections/ NOT created (correct — out of scope)"

# 4. All tests (1a + 1b) pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short \
  || { echo "HALT CHECKPOINT_A: pytest FAILED"; exit 1; }
echo "✓ pytest unit + integration passed (1a + 1b)"

# 5. mypy strict + lint-imports clean
mypy scripts/work_state/ && lint-imports \
  || { echo "HALT CHECKPOINT_A: mypy/lint-imports FAILED"; exit 1; }
echo "✓ mypy strict + lint-imports clean"

# 6. Branch ahead by realistic count (≥10 commits — ~1 per Step × 11 atomic step-commits)
COMMITS_AHEAD=$(git rev-list --count "$(cat /tmp/work-state-1b-base-sha.txt)..HEAD")
test "$COMMITS_AHEAD" -ge 10 \
  || { echo "HALT CHECKPOINT_A: only $COMMITS_AHEAD commits, expected ≥10"; exit 1; }
echo "✓ $COMMITS_AHEAD commits ahead of base"

# 7. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "HALT CHECKPOINT_A: working tree DIRTY"; git status --short; exit 1; }
echo "✓ working tree clean"

echo ""
echo "✓✓✓ CHECKPOINT A PASSED — proceeding to Phase B (Codex Review)"
echo ""
```

---

Step 13 — Inline Codex review with ≤5 fix rounds (P1 Standard Lane max 5 per CLAUDE.md hard rule #8)

Round 1:
```bash
codex review --base main 2>&1 | tee .autopilot/state/work-state-1b/codex/round-01.txt
```

Parse Codex output (same logic as Phase 1a):
* Clean phrases ("LGTM", "no issues found", "approve", "no recommendations") → clean
* Otherwise extract findings:
  - P0/P1 → MUST fix this round
  - P2 → fix opportunistically; defer if scope creep
  - Keywords <schema|breaking|architectural> → ARCH_FINDING circuit → HALT
  - Keywords <auth|token|timing|secret|injection> → SECURITY_FINDING circuit → HALT
  - Keywords <race|lock|transaction> (not idempotent/retry) → CONCURRENCY_FINDING circuit → HALT
  - Same finding hash in round N and N+1 → RECURRING_FINDING circuit → HALT
  - Keyword <cache|TTL|invalidation> regression → CACHE_REGRESSION circuit → HALT (1b specific)
  - Keyword <PR identity|ambiguous> regression → IDENTITY_REGRESSION circuit → HALT (1b specific)
  - Keyword <railway|deploy|unknown-safe> regression → RAILWAY_REGRESSION circuit → HALT (1b specific)

Fix round:
* Apply minimum-viable fix per finding
* Re-run pytest tests/unit/work_state/ + tests/integration/work_state/ — MUST be green
* Commit atomically: fix(work-state): address codex round NN — <summary>

Round 2: repeat. MUST be clean for P1 manual_only merge gate.

If round 5 hit without 2× consecutive clean → MAX_ROUNDS circuit → HALT.

---

### ✅ CHECKPOINT B — Phase B Codex Review complete (MANDATORY gate)

```bash
echo "=== CHECKPOINT B — Codex Review complete ==="

# 1. ≥2 codex round artifacts
ROUND_COUNT=$(ls .autopilot/state/work-state-1b/codex/round-*.txt 2>/dev/null | wc -l | tr -d ' ')
test "$ROUND_COUNT" -ge 2 \
  || { echo "HALT CHECKPOINT_B: only $ROUND_COUNT codex round artifacts"; exit 1; }
echo "✓ $ROUND_COUNT codex round artifacts captured"

# 2. Last 2 rounds both clean
LAST_ROUND=$(ls -1 .autopilot/state/work-state-1b/codex/round-*.txt | tail -1)
PREV_ROUND=$(ls -1 .autopilot/state/work-state-1b/codex/round-*.txt | tail -2 | head -1)
for r in "$LAST_ROUND" "$PREV_ROUND"; do
  if grep -qiE "(P0|P1)[: ]|finding|issue" "$r" \
     && ! grep -qiE "lgtm|no issues|approve|no recommendations|clean" "$r"; then
    echo "HALT CHECKPOINT_B: round $r appears to have UNRESOLVED findings"
    exit 1
  fi
done
echo "✓ last 2 rounds both clean"

# 3. Tests still green after fixes
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short \
  || { echo "HALT CHECKPOINT_B: pytest REGRESSED"; exit 1; }
echo "✓ pytest still green"

# 4. No new `# type: ignore` introduced
NEW_IGNORES=$(git diff "$(cat /tmp/work-state-1b-base-sha.txt)..HEAD" -- scripts/ tests/ \
  | grep -c "^+.*type: ignore" || true)
test "$NEW_IGNORES" -eq 0 \
  || { echo "HALT CHECKPOINT_B: $NEW_IGNORES new # type: ignore"; exit 1; }
echo "✓ no new # type: ignore"

# 5. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "HALT CHECKPOINT_B: working tree DIRTY"; git status --short; exit 1; }
echo "✓ working tree clean"

echo ""
echo "✓✓✓ CHECKPOINT B PASSED — proceeding to Phase C (Final Verify + Push)"
echo ""
```

---

Step 14 — Final verification + STOP_AT_READY

```bash
pytest tests/unit/work_state/ tests/integration/work_state/ -v
ruff check scripts/work_state/ tests/unit/work_state/ tests/integration/work_state/
black --check scripts/work_state/ tests/unit/work_state/ tests/integration/work_state/
mypy scripts/work_state/
lint-imports

# Dogfood: run engine once locally + inspect output
python -c "
from scripts.work_state.plan_reader import read_tracker
from scripts.work_state.signal_collectors.filesystem import FilesystemCollector
from scripts.work_state.signal_collectors.git import GitCollector
from scripts.work_state.signal_collectors.github import GithubCollector
from scripts.work_state.signal_collectors.ci import CiCollector
from scripts.work_state.signal_collectors.railway import RailwayCollector
print('engine 5 collectors importable + chain runnable')
"

git push -u origin feat/MYM-3-work-state-engine-1b
```

---

### ✅ CHECKPOINT C — Final state verified (MANDATORY gate before READY report)

```bash
echo "=== CHECKPOINT C — Final state verified ==="

# 1. Local SHA matches origin
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git rev-parse "origin/feat/MYM-3-work-state-engine-1b" 2>/dev/null) \
  || { echo "HALT CHECKPOINT_C: origin branch missing"; exit 1; }
test "$LOCAL_SHA" = "$REMOTE_SHA" \
  || { echo "HALT CHECKPOINT_C: local $LOCAL_SHA ≠ origin $REMOTE_SHA"; exit 1; }
echo "✓ local & origin both at $LOCAL_SHA"

# 2. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "HALT CHECKPOINT_C: working tree DIRTY"; git status --short; exit 1; }
echo "✓ working tree clean"

# 3. Branch ahead by ≥10 commits
COMMITS_AHEAD=$(git rev-list --count "$(cat /tmp/work-state-1b-base-sha.txt)..HEAD")
test "$COMMITS_AHEAD" -ge 10 \
  || { echo "HALT CHECKPOINT_C: only $COMMITS_AHEAD commits"; exit 1; }
echo "✓ $COMMITS_AHEAD commits ahead of base"

# 4. 5 collectors importable (smoke test)
python -c "
from scripts.work_state.signal_collectors import filesystem, git, github, ci, railway
print('5 collectors import OK')
" || { echo "HALT CHECKPOINT_C: collector import FAILED"; exit 1; }
echo "✓ 5 collectors importable"

# 5. Final 5-tool sweep
ruff check scripts/work_state/ tests/unit/work_state/ tests/integration/work_state/ \
  && black --check scripts/work_state/ tests/unit/work_state/ tests/integration/work_state/ \
  && mypy scripts/work_state/ \
  && lint-imports \
  && pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short \
  || { echo "HALT CHECKPOINT_C: final verify sweep FAILED"; exit 1; }
echo "✓ ruff + black + mypy + lint-imports + pytest all green"

echo ""
echo "✓✓✓ CHECKPOINT C PASSED — emitting READY_FOR_MANUAL_MERGE report"
echo ""
```

---

Report READY_FOR_MANUAL_MERGE — founder reviews + squash-merges manually per CLAUDE.md hard
rule #6. Do NOT auto-merge.

Circuit breakers (named halt conditions — 1b adds 3 to 1a's 9):

* ARCH_FINDING — Codex flagged schema/breaking/architectural concern → HALT
* SECURITY_FINDING — auth/token/secret/timing/injection finding → HALT
* CONCURRENCY_FINDING — race/lock/transaction (not retry/idempotency) → HALT
* RECURRING_FINDING — same finding hash 2 consecutive rounds → HALT
* CACHE_REGRESSION — codex flagged cache TTL/invalidation broken → HALT (1b specific)
* IDENTITY_REGRESSION — codex flagged PR identity fallback broken → HALT (1b specific)
* RAILWAY_REGRESSION — codex flagged railway not unknown-safe (token missing or timeout → exception leak) → HALT (1b specific)
* TEST_FAIL_BASELINE — existing pytest baseline regresses (1a + 1b combined) → HALT
* OUT_OF_SCOPE_TOUCH — diff touches Negative scope (projections/, build-dashboard.py, etc.) → HALT
* PRE_FLIGHT_FAIL — any pre-flight step fails → HALT
* MAX_ROUNDS — 5 Codex rounds without 2× consecutive clean → HALT
* TYPE_IGNORE_ADDED — any `# type: ignore` added → HALT
* PHASE_1A_PREREQUISITE_MISSING — Phase 1a module not on main → HALT (1b specific)

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
READY_FOR_MANUAL_MERGE — work-state engine Phase 1b complete

Branch: feat/MYM-3-work-state-engine-1b
Base SHA: <from /tmp/work-state-1b-base-sha.txt>
HEAD SHA: <current>
Commits: <N> atomic commits

Modules added: scripts/work_state/signal_collectors/{
  github.py, ci.py, railway.py
}
Modules extended (APPEND-ONLY): models.py (+9 Signals fields), status_machine.py (+~10 priority cases)

Test coverage: <unit count>/<integration count>, all green.
mypy strict: clean.
ruff + black + import-linter: clean.

Codex review:
- Round 1: <clean | N findings, all addressed>
- Round 2: <clean — MUST be clean for P1 gate>

AC progress (per spec §13):
- AC1c (github + ci + railway collectors full subset): ✓
- AC11a/b/c (overlay propagation: blocked/stale/ci-running/deploy-failed/etc.): ✓
- AC11f (cache TTL + --no-network for all 3 network collectors): ✓
- AC19 (PR identity §6.3 5-step fallback): ✓
- AC20 (overlay propagation github_unknown/ci_unknown/railway_unknown/ambiguous-pr-mapping): ✓

Remaining ACs (Phase 1b' + 1c+):
- AC1g (projection enriches dashboard.json) → MYM-4 Phase 1b'
- AC11d (multi-branch agg) → Phase 1c per snapshot
- AC11e (event dedup extension for new event types) → covered by existing event_engine, may need test
- AC12-AC18 (workflow + persistence) → Phase 1c
- AC21-AC23 (urgency) → Phase 1d
- AC25 (CI persistence) → Phase 1c

Dogfood engine on real tracker: <N> rows, <M> with pr_state mapped, <K> with ci_state,
<L> with deploy_state. Overlays observed: <list>.

Founder action: review diff, squash-merge per Foundation Lane gate. After merge:
1. 7-day shadow monitoring window per spec §10 exit criteria
2. Fire MYM-4 Phase 1b' projection prompt (separate, smaller scope)
3. Plan Phase 1c (multi-branch agg + persistence + workflow) after 1b stable
```

Begin with Pre-flight, then Step 1.
```

---

## How to use this prompt (founder)

1. **Phase 1a (MYM-1) merged to main** ✓ (2026-05-20 SHA 5072e9e). Pre-flight halt-on-missing-prereq passes.

2. **Linear ticket MYM-3 created** ✓ (https://linear.app/maingocanh/issue/MYM-3). Placeholder `MYM-3` already substituted throughout this prompt.

3. **Create engine-1b worktree:**
   ```bash
   cd /Users/maingocanh/Projects/MyMoneyWent
   git worktree add ../MyMoneyWent-engine-1b -b feat/MYM-3-work-state-engine-1b main
   cd ../MyMoneyWent-engine-1b
   ln -s /Users/maingocanh/Projects/MyMoneyWent/.venv .venv
   source .venv/bin/activate
   ```

4. **Add tracker row for Phase 1b** (similar to MYM-1 row pattern). Commit + push to main first so engine-1b can read tracker.

5. **Fire claude -p:**
   ```bash
   claude -p "$(cat docs/autopilot/prompts/work-state-engine-phase-1b-autopilot.md)" \
     2>&1 | tee .autopilot/state/work-state-1b/run-$(date +%s).log
   ```

6. **Walk away** for ~2-3 hours estimated (slightly more than 1a due to 3 network-dependent collectors + cache logic + Signals extension regression risk).

7. **Manual review + squash-merge** per Foundation Lane gate. PR body MUST contain `Closes MYM-3`.

8. **After merge**: 7-day shadow window, then fire MYM-4 (Phase 1b' projection) prompt.

## References

- Spec: `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 §6.3 + §6.4 + §6.5 + §6.7 + §7.4 + §8.1 + §13
- Phase 0 audit: `docs/operations/dashboard-engine/phase-0-audit-report-2026-05-20.md`
- Foundation Lane workflow: `docs/operations/dashboard-engine/walkthrough-foundation-lane-example.md`
- Hard rules: `CLAUDE.md`
- Autopilot template: `docs/autopilot/autopilot-prompt-template.md`
- Phase 1a prompt (prerequisite): `docs/autopilot/prompts/work-state-engine-phase-1a-autopilot.md` ✅ shipped
- Architecture snapshot: `docs/operations/dashboard-engine/dashboard-architecture-snapshot.md` v1.0.1
- Scope reconcile rationale: A+ option locked 2026-05-20 (snapshot §5 + Linear milestone over spec §10 canonical)
