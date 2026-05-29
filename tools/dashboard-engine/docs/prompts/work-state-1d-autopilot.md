# Autopilot Prompt — work-state engine Phase 1d (urgency + MAX agg + foundation_change + projection)

> **Status:** READY 2026-05-21 · gated by MYM-7 Phase B merge (✅ merged `39bb5fc` 2026-05-21).
> **Spec source:** `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.3.0 §9.4 + §4.1.3 + §9.1 (AC11b + AC11c + AC11d).
> **Vision:** `docs/operations/dashboard-engine/product-vision.md` v0.1.0.
> **Linear ticket:** [MYM-10](https://linear.app/maingocanh/issue/MYM-10) — Phase 1d mega-bundle (4 sub-phases A/B/C/D).
> **Predecessors:** MYM-1 (`5072e9e`) · MYM-3 (`3e654cf`) · MYM-4 (`2396107`) · MYM-5 (`fb7a587`) · MYM-6 (`bc8260f`) · MYM-7 (`39bb5fc`).

---

## Scope reminder (vs 1a/1b/1b'/1c/Phase A/Phase B)

| Phase | Status | Operational milestone scope | This prompt? |
|---|---|---|---|
| 1a | ✅ Merged (MYM-1) | skeleton + fs + git collectors | NO (prerequisite) |
| 1b | ✅ Merged (MYM-3) | github + ci + railway collectors | NO (prerequisite) |
| 1b' | ✅ Merged (MYM-4) | projections/dashboard.py | NO (prerequisite) |
| 1c | ✅ Merged (MYM-5) | driver + aggregation + persistence + workflow | NO (prerequisite) |
| Dashboard Live View A | ✅ Merged (MYM-6) | engine→build-dashboard.py wire | NO (prerequisite) |
| Dashboard Live View B | ✅ Merged (MYM-7) | doc-change overlays §8.2 → 18 | NO (prerequisite) |
| **1d** | **This prompt (MYM-10)** | **urgency derivation + MAX agg + foundation_change + projection** | **YES (bundle)** |
| 2 | Future | CI Plan/State boundary enforcement + computed-status-primary promotion | NO (gated by 7-day shadow) |

> **Scope reality:** `engine.py:234` hardcodes `runtime_urgency="normal"`. Spec §9.4.1 has full deterministic algorithm pseudocode — straight port. MAX aggregation §9.4.2 + §4.1.3 — small fn + wire. `foundation_change` AC11c signals not detected (audit 2026-05-20). Projection has zero urgency rendering. Bundle decision locked với anh 2026-05-21 (mega-bundle pattern per memory `feedback_megaprompt_with_checkpoints_works`).

---

```
Task: work-state-engine Phase 1d — urgency derivation + MAX aggregation + foundation_change milestone signals + projection rendering (mega-bundle scope)
You are working in /Users/maingocanh/Projects/MyMoneyWent-1d on MyMoneyWent
(multi-tenant personal finance bot, dual-market VN+Global). NO prior conversation context.
This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-10-work-state-1d-urgency-bundle`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY on
circuit-breaker conditions (§Circuit breakers).

Risk tier:          P1 Foundation Lane (touches engine + projection + new signal detection)
Merge policy:       manual_only (CLAUDE.md hard rule #6)
Autopilot maturity: pilot (seventh engine implementation run on MMW work-state spec)
Codex review:       2× consecutive clean required (P1 Foundation Lane)

Branch convention: LOWERCASE only per pr-validate.yml regex `^[a-z0-9-]+/MYM-...`.
DO NOT use uppercase Phase letters in branch name — pr-validate fails (memory
feedback_admin_squash_bypass_pr_validate_regex.md). Use `urgency-bundle` suffix.

Prerequisite: MYM-1 + MYM-3 + MYM-4 + MYM-5 + MYM-6 + MYM-7 all merged ✓ on main at
`39bb5fc` (or later).
Halts pre-flight if any of:
  scripts/work_state/{__init__,__main__,models,plan_reader,event_engine,
                      status_machine,progress,state_store,engine}.py
  scripts/work_state/signal_collectors/{filesystem,git,github,ci,railway}.py
  scripts/work_state/projections/dashboard.py
  scripts/build-dashboard.py (with engine wire)
not all present, OR Signals dataclass missing pr_state/ci_state/review_state/deploy_state/
spec_hash/tech_hash/tracker_row_hash, OR aggregate_multi_branch_status/overlays missing,
OR CANONICAL_OVERLAYS not yet 18 entries (spec-modified, tech-modified, tracker-modified,
post-ship-doc-change must be present from MYM-7).

Scope of this prompt — Phase 1d mega-bundle (4 sub-phases):
  Phase A — derive_urgency function (status_machine.py) — AC11b
  Phase B — MAX urgency aggregation wire (engine.py + status_machine.py) — AC11d
  Phase C — foundation_change milestone signals (signal_collectors/github.py) — AC11c
  Phase D — projection urgency badge rendering (projections/dashboard.py + build-dashboard.py)

Each sub-phase ends với MANDATORY CHECKPOINT (halt-if-skipped per memory
feedback_megaprompt_with_checkpoints_works.md). Do NOT skip checkpoints.

New files (Phase 1d additions):
  tests/unit/work_state/test_urgency.py                          # Phase A unit tests
  tests/integration/work_state/test_engine_urgency_e2e.py        # Phase B integration tests
  tests/unit/work_state/test_foundation_change_signals.py        # Phase C unit tests

Modified files (Phase 1d):
  scripts/work_state/status_machine.py     # Phase A — add derive_urgency() + URGENCY_ORDER constant
                                           # Phase B — add aggregate_multi_branch_urgency()
  scripts/work_state/engine.py             # Phase B — wire derive_urgency at line 234 + multi-branch
  scripts/work_state/models.py             # Phase C — Signals APPEND-ONLY +2 fields
  scripts/work_state/signal_collectors/github.py  # Phase C — detect codex-approved + founder sign-off
  scripts/work_state/projections/dashboard.py     # Phase D — render urgency badge in state block
  scripts/build-dashboard.py               # Phase D — pass urgency through to HTML/MD/JSON

Do NOT touch:
  - scripts/work_state/projections/__init__.py — read-only
  - scripts/work_state/signal_collectors/{filesystem,git,ci,railway}.py — read-only baseline
  - scripts/work_state/{plan_reader,event_engine,progress,state_store,__main__}.py — read-only
  - .importlinter — no boundary changes needed
  - .github/workflows/*.yml — Phase 1c/Phase B baseline
  - docs/implementation-tracker.md — read-only input (engine reads)
  - Any .md file under docs/ — read-only (NEVER delete per CLAUDE.md hard rule #2)

Out-of-scope-but-documented:
  - Progress profile `docs_only` / `dashboard_engine` refinement → separate ticket
  - 7-day shadow window validation → parallel, not blocking
  - Phase 2 promotion (computed → primary status) → requires 7-day shadow ≥95%
  - foundation_change progress milestone EVENT emission (Phase C surfaces signal only,
    profile derivation logic stays event-free)
  - Spec §9.4.4 overlay combinations validation table → covered by Phase A tests

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-engine/dashboard-plan-state-split.md v1.3.0 — focus:
   - §4.1.3 runtime_urgency interaction (MAX across branches)
   - §8.2 18-overlay enum canonical (verify post-MYM-7 state)
   - §9.1 Progress profiles (foundation_change profile signals per AC11c)
   - §9.4 Runtime urgency model (algorithm pseudocode §9.4.1 — straight port)
   - §9.4.2 Multi-branch MAX aggregation
   - §9.4.3 UI rendering (3-axis: priority + risk_tier + urgency)
   - §9.4.4 Overlay combinations examples
   - §13 AC11b + AC11c + AC11d

2. docs/operations/dashboard-engine/product-vision.md v0.1.0 — focus:
   - Validation gate (engine accuracy target ≥95%)
   - "What NOT to build" — engine stays event-free for foundation profile

3. CLAUDE.md — focus hard rules:
   - #1 (1-session per .git)
   - #2 (NEVER delete docs)
   - #3 (spec-first)
   - #5 (different-model review P1)
   - #6 (manual_only merge)
   - #7 (mega-prompt exception with checkpoints — this prompt)
   - #8 (review cap: Foundation Lane 8 rounds, founder approval after 5)

4. Phase 1a/1b/1b'/1c/A/B deliverables (READ-ONLY for understanding):
   - scripts/work_state/models.py — Signals dataclass (must have 18+ fields incl. doc hash)
   - scripts/work_state/status_machine.py — compute_overlays, aggregate_multi_branch_*
   - scripts/work_state/engine.py — driver pipeline (line 234 hardcoded urgency)
   - scripts/work_state/projections/dashboard.py — state block builder
   - scripts/build-dashboard.py — HTML/MD generator with engine wire
   - tests/unit/work_state/test_overlays_doc_changes.py — MYM-7 overlay patterns
   - tests/integration/work_state/test_doc_change_e2e.py — MYM-7 end-to-end

5. .autopilot/state/work-state-1c/ + .autopilot/state/work-state-1c/codex/ — baseline
   pattern + Codex round artifacts for reference

6. docs/implementation-tracker.md — sample real rows for engine dogfood

Pre-flight gate (HARD — halt if any fails):

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-1d
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-10-work-state-1d-urgency-bundle
git fetch origin
git log --oneline origin/main..HEAD -5  # verify feat ahead/equal to origin/main
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat behind origin/main"; exit 1; }

# Phase 1a/1b/1b'/1c/A/B prerequisite — all modules + engine.py + projection MUST exist
for f in __init__.py __main__.py models.py plan_reader.py event_engine.py status_machine.py \
         progress.py state_store.py engine.py \
         signal_collectors/__init__.py signal_collectors/filesystem.py \
         signal_collectors/git.py signal_collectors/github.py \
         signal_collectors/ci.py signal_collectors/railway.py \
         projections/__init__.py projections/dashboard.py; do
  test -f "scripts/work_state/$f" \
    || { echo "FAIL: prerequisite scripts/work_state/$f MISSING"; exit 1; }
done

# build-dashboard.py with engine wire (MYM-6)
grep -q "run_engine" scripts/build-dashboard.py \
  || { echo "FAIL: build-dashboard.py missing engine wire (MYM-6)"; exit 1; }

# Signals dataclass MUST have all prior extensions incl. MYM-7 doc-hash fields
python -c "from scripts.work_state.models import Signals; \
  s = Signals.__dataclass_fields__; \
  required = ['pr_state','ci_state','review_state','deploy_state', \
              'spec_hash','tech_hash','tracker_row_hash']; \
  missing = [f for f in required if f not in s]; \
  assert not missing, f'FAIL: Signals missing {missing}'; print('OK: Signals has all prior fields')"

# CANONICAL_OVERLAYS must be 18 entries (MYM-7)
python -c "from scripts.work_state.status_machine import CANONICAL_OVERLAYS; \
  required = {'spec-modified','tech-modified','tracker-modified','post-ship-doc-change'}; \
  missing = required - CANONICAL_OVERLAYS; \
  assert not missing, f'FAIL: overlays missing {missing}'; \
  assert len(CANONICAL_OVERLAYS) >= 18, f'FAIL: only {len(CANONICAL_OVERLAYS)} overlays'; \
  print(f'OK: {len(CANONICAL_OVERLAYS)} canonical overlays')"

# Engine.py has hardcoded urgency line (Phase A will replace)
grep -q 'runtime_urgency="normal"' scripts/work_state/engine.py \
  || { echo "FAIL: engine.py expected hardcode missing — was urgency wire-up already done?"; exit 1; }

# Aggregation functions exist
python -c "from scripts.work_state.status_machine import \
  aggregate_multi_branch_status, aggregate_multi_branch_overlays; \
  print('OK: aggregate fns present')"

source .venv/bin/activate
which python                            # MUST resolve to .venv/bin/python
which gh && gh auth status              # gh CLI authenticated
which codex                             # MUST resolve
which claude                            # MUST resolve

# FULL mypy strict scope per CLAUDE.md style + memory
# feedback_autopilot_preflight_must_include_tests_mypy.md (MYM-4 lesson)
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports                            # 5 contracts pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short  # ~270+ baseline

echo ""
echo "✓✓✓ PRE-FLIGHT PASSED — proceeding to Phase A (derive_urgency)"
echo ""
```

ALL must pass. If any fails → HALT and report. Do not proceed.

Anti-patterns (NEVER do):

* `git push --force`
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed)
* Auto-merge ngoài STOP_AT_READY (P1 manual_only)
* MODIFY baseline modules beyond explicit scope:
  - status_machine.py — only ADD derive_urgency + aggregate_multi_branch_urgency + URGENCY_ORDER. DO NOT touch compute_overlays, aggregate_multi_branch_status, aggregate_multi_branch_overlays.
  - engine.py — only replace line 234 + add multi-branch urgency aggregation call. DO NOT refactor run_engine pipeline structure.
  - models.py — APPEND-ONLY +2 Signals fields (foundation_codex_approved, foundation_founder_signoff). DO NOT remove/rename existing fields.
  - signal_collectors/github.py — only ADD detection logic for codex-approved label + founder sign-off comment. DO NOT change PR identity resolution / rate limit / pagination.
  - projections/dashboard.py — only ADD urgency to state block dict + emoji map. DO NOT change atomic write or signal extraction.
  - build-dashboard.py — only thread urgency through HTML/MD rendering. DO NOT change engine invocation / strict-engine flag / warning banner.
* Touch baseline modules outside above scope (filesystem.py, git.py, ci.py, railway.py, plan_reader.py, event_engine.py, progress.py, state_store.py)
* Touch .github/workflows/*.yml (Phase 1c/Phase B baseline)
* Touch .importlinter (no boundary changes)
* Delete or rename existing Signals fields (APPEND-ONLY rule — memory feedback_append_only_signals)
* Implement progress profile `docs_only` / `dashboard_engine` refinement (out of scope)
* Implement `foundation_change` PROGRESS MILESTONE EVENT emission — Phase C surfaces signal only, not event
* `xfail` to mask broken AC — only for explicit deferred contracts per memory `feedback_pin_deferred_contracts`
* Skip Codex review rounds — P1 Foundation needs 2× consecutive clean
* Delete or move any `.md` file (CLAUDE.md hard rule #2)
* Skip checkpoint commits between phases — each Phase A/B/C/D must have explicit halt + checkpoint pass before proceeding
* Bundle multiple phases into single commit — atomic step-commits required (≥1 commit per Step)
* Touch uppercase letters trong branch name (pr-validate regex fails, MYM-9 not yet shipped)

Numbered steps:

```bash
# ============================================================
# Phase A — derive_urgency function (Steps 1-3)
# Goal: AC11b — 4-level deterministic urgency derivation per spec §9.4.1
# ============================================================

# Step 1 — Confirm on feat branch + create state dir + read spec §9.4.1
git status
git branch --show-current
test -d .autopilot/state/work-state-1d/codex \
  || { echo "FAIL: codex artifact dir missing — bootstrap step skipped"; exit 1; }

# Read spec §9.4 algorithm pseudocode (must be present before code):
grep -A 50 "### 9.4.1 Derivation algorithm" docs/operations/dashboard-engine/dashboard-plan-state-split.md | head -50

# Step 2 — TDD: write failing tests/unit/work_state/test_urgency.py FIRST
# Cover spec §9.4.1 algorithm — each tier ≥3 cases (positive + boundary + negative):
#   CRITICAL tier:
#     - test_critical_when_deploy_failed
#     - test_critical_when_deployed_plus_unknown_plus_p0_risk
#     - test_critical_when_deployed_plus_unknown_plus_p1_risk
#     - test_NOT_critical_when_deployed_plus_unknown_plus_p2_risk  (boundary)
#     - test_critical_when_merged_plus_ci_failing  (main broken)
#   ELEVATED tier:
#     - test_elevated_when_blocked_plus_p0
#     - test_elevated_when_blocked_plus_p1
#     - test_NOT_elevated_when_blocked_plus_p2  (drops to warning)
#     - test_elevated_when_ci_failing_in_review
#     - test_elevated_when_approved_pending_merge_plus_stale
#     - test_elevated_when_ambiguous_pr_mapping
#   WARNING tier:
#     - test_warning_when_blocked_plus_p2  (drops from elevated)
#     - test_warning_when_stale_alone
#     - test_warning_when_unknown_alone
#     - test_warning_when_artifact_drift
#     - test_warning_when_cache_warmup
#   NORMAL tier:
#     - test_normal_when_no_overlays
#     - test_normal_when_only_review_requested  (no concerning overlays)
#     - test_normal_when_in_progress_clean
#   Doc-change overlays (post MYM-7) — do NOT trigger urgency promotion by themselves
#     (spec §9.4.1 doesn't elevate for spec-modified/tech-modified/tracker-modified):
#     - test_normal_when_only_spec_modified
#     - test_normal_when_only_tech_modified
#     - test_normal_when_only_tracker_modified
#     - test_warning_when_post_ship_doc_change  (only if terminal + doc-change combo;
#       decide based on spec re-read — if spec doesn't promote, normal is correct)
#
# Run pytest — all should FAIL (derive_urgency doesn't exist yet).
pytest tests/unit/work_state/test_urgency.py -q  # expected FAIL

# Step 3 — Implement derive_urgency in scripts/work_state/status_machine.py:
#   - Add module-level constant: URGENCY_ORDER = {"normal": 0, "warning": 1, "elevated": 2, "critical": 3}
#   - Add function:
#     def derive_urgency(
#         base: str,
#         overlays: list[str] | frozenset[str],
#         priority: str,         # "P0" | "P1" | "P2" | "P3" | etc.
#         risk_tier: str,        # "P0" | "P1" | "P2" | etc.
#     ) -> str:
#         """Derive runtime_urgency per spec §9.4.1 — first-match-wins."""
#         overlay_set = frozenset(overlays) if not isinstance(overlays, frozenset) else overlays
#         # 1. CRITICAL — production / data integrity at risk
#         if "deploy-failed" in overlay_set:
#             return "critical"
#         if base == "deployed" and "unknown" in overlay_set:
#             if risk_tier in {"P0", "P1"}:
#                 return "critical"
#         if "ci-failing" in overlay_set and base == "merged":
#             return "critical"
#         # 2. ELEVATED — active work with required attention
#         if "blocked" in overlay_set and priority in {"P0", "P1"}:
#             return "elevated"
#         if "ci-failing" in overlay_set:
#             return "elevated"
#         if base == "approved-pending-merge" and "stale" in overlay_set:
#             return "elevated"
#         if "ambiguous-pr-mapping" in overlay_set:
#             return "elevated"
#         # 3. WARNING — degraded signal or attention soon
#         if "blocked" in overlay_set:
#             return "warning"
#         if "stale" in overlay_set:
#             return "warning"
#         if "unknown" in overlay_set:
#             return "warning"
#         if "artifact-drift" in overlay_set:
#             return "warning"
#         if "cache-warmup" in overlay_set:
#             return "warning"
#         # 4. NORMAL — no active concerns
#         return "normal"
#   - mypy strict — args + return all str (or Literal type if convenient)
#   - Tests should be 100% pass after this step.
pytest tests/unit/work_state/test_urgency.py -q
```

### ✅ CHECKPOINT A — Phase A derive_urgency complete (MANDATORY gate)

```bash
# 1. New test file present
test -f tests/unit/work_state/test_urgency.py

# 2. derive_urgency callable
python -c "from scripts.work_state.status_machine import derive_urgency, URGENCY_ORDER; \
  assert derive_urgency('merged', ['ci-failing'], 'P1', 'P1') == 'critical'; \
  assert derive_urgency('in-progress', [], 'P2', 'P2') == 'normal'; \
  assert URGENCY_ORDER == {'normal': 0, 'warning': 1, 'elevated': 2, 'critical': 3}; \
  print('OK: derive_urgency + URGENCY_ORDER')"

# 3. NO touch to out-of-scope baseline
git diff origin/main --name-only | grep -E '^scripts/work_state/(plan_reader|event_engine|progress|state_store|__main__|engine|models|projections|signal_collectors/[a-z]+)\.py$' \
  | grep -v 'engine.py$' \
  | grep -v 'models.py$' \
  | grep -v 'signal_collectors/github.py$' \
  | grep -v 'projections/dashboard.py$' \
  && { echo "FAIL: touched out-of-scope baseline"; exit 1; } \
  || echo "OK: scope respected (only status_machine.py edited in Phase A)"

# 4. Tests pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 5. mypy + lint clean (FULL scope per memory)
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports

# 6. Branch ahead ≥2 commits (1 test commit + 1 impl commit minimum)
test "$(git rev-list --count origin/main..HEAD)" -ge 2 \
  || { echo "FAIL: too few commits"; exit 1; }

# 7. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "FAIL: dirty tree"; exit 1; }

# 8. NO docs deleted
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs deleted"; exit 1; } \
  || echo "OK: no docs deleted"

echo ""
echo "✓✓✓ CHECKPOINT A PASSED — proceeding to Phase B (MAX urgency aggregation)"
echo ""
```

If ANY fails → HALT. Do NOT proceed to Phase B.

```bash
# ============================================================
# Phase B — MAX urgency aggregation wire (Steps 4-5)
# Goal: AC11d MAX urgency across branches + wire derive_urgency into engine
# ============================================================

# Step 4 — TDD: integration tests for AC11d urgency
# tests/integration/work_state/test_engine_urgency_e2e.py
# Cover spec §9.4.2 + §4.1.3 scenarios:
#   - Single-branch, no overlay → normal
#   - Single-branch, deploy-failed → critical
#   - Multi-branch: A normal + B elevated → MAX = elevated
#   - Multi-branch: A normal + B critical (deploy-failed on B) → MAX = critical
#   - Multi-branch: A elevated + B warning → MAX = elevated
#   - Multi-branch: all branches normal → normal
#   - Engine output: CurrentState.runtime_urgency = derived value (not hardcoded "normal")
# Tests fail initially — engine.py:234 hardcoded.
pytest tests/integration/work_state/test_engine_urgency_e2e.py -q  # expected FAIL

# Step 5a — Add aggregate_multi_branch_urgency to status_machine.py:
#   def aggregate_multi_branch_urgency(urgencies: list[str]) -> str:
#       """MAX urgency per spec §9.4.2 — critical > elevated > warning > normal."""
#       if not urgencies:
#           return "normal"
#       return max(urgencies, key=lambda u: URGENCY_ORDER.get(u, 0))
#   Unit tests under test_urgency.py:
#     - aggregate_multi_branch_urgency([]) == "normal"
#     - aggregate_multi_branch_urgency(["normal"]) == "normal"
#     - aggregate_multi_branch_urgency(["normal", "critical"]) == "critical"
#     - aggregate_multi_branch_urgency(["elevated", "warning"]) == "elevated"
#     - aggregate_multi_branch_urgency(["warning", "warning", "normal"]) == "warning"

# Step 5b — Wire urgency into engine.py run_engine():
#   - For each WorkItem:
#     * If len(branches) == 1:
#         per_branch_urgency = derive_urgency(base, overlays, priority, risk_tier)
#         runtime_urgency = per_branch_urgency
#     * If len(branches) > 1:
#         per_branch_urgencies = []
#         for each branch:
#             # branch base + overlays already computed in Phase 1c
#             u = derive_urgency(branch_base, branch_overlays, priority, risk_tier)
#             per_branch_urgencies.append(u)
#         runtime_urgency = aggregate_multi_branch_urgency(per_branch_urgencies)
#   - REPLACE line 234 `runtime_urgency="normal"` with `runtime_urgency=runtime_urgency`
#   - Priority + risk_tier come from WorkItem (plan_reader output)
#   - If WorkItem.priority is None or "" → default to "P2" (per spec implicit)
#   - If WorkItem.risk_tier is None or "" → default to "P2"

# Run integration tests — should pass.
pytest tests/integration/work_state/test_engine_urgency_e2e.py -q
pytest tests/unit/work_state/ -q
```

### ✅ CHECKPOINT B — Phase B MAX aggregation + wire complete

```bash
# 1. New integration test pass
pytest tests/integration/work_state/test_engine_urgency_e2e.py -q --tb=short

# 2. aggregate_multi_branch_urgency callable
python -c "from scripts.work_state.status_machine import aggregate_multi_branch_urgency; \
  assert aggregate_multi_branch_urgency(['normal','critical']) == 'critical'; \
  assert aggregate_multi_branch_urgency([]) == 'normal'; \
  print('OK')"

# 3. engine.py NO longer hardcodes "normal" — must call derive_urgency
grep -q 'runtime_urgency="normal"' scripts/work_state/engine.py \
  && { echo "FAIL: hardcoded urgency still present"; exit 1; } \
  || echo "OK: hardcode removed"

grep -q "derive_urgency" scripts/work_state/engine.py \
  || { echo "FAIL: derive_urgency not wired"; exit 1; }

# 4. mypy + lint + tests clean
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports
pytest tests/unit/work_state/ tests/integration/work_state/ -q

# 5. Branch ahead ≥4 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 4

# 6. Working tree clean
test -z "$(git status --porcelain)"

# 7. NO Phase 2 scope creep
git diff origin/main scripts/work_state/engine.py | grep -E '(primary.*status|computed-as-primary)' \
  && { echo "FAIL: Phase 2 scope creep"; exit 1; } \
  || echo "OK: Phase 2 scope respected"

echo ""
echo "✓✓✓ CHECKPOINT B PASSED — proceeding to Phase C (foundation_change signals)"
echo ""
```

```bash
# ============================================================
# Phase C — foundation_change milestone signals (Steps 6-8)
# Goal: AC11c — Detect codex-approved label + founder sign-off in signal_collectors/github.py
# ============================================================

# Step 6 — Models extension (APPEND-ONLY)
# Modify scripts/work_state/models.py Signals dataclass:
#   Add 2 NEW fields AT THE END (APPEND-ONLY rule):
#     foundation_codex_approved: bool | None = None
#     foundation_founder_signoff: bool | None = None
#   DO NOT touch other fields. Order preserved.
# Add unit test tests/unit/work_state/test_foundation_change_signals.py:
#   - Default Signals() has foundation_codex_approved=None and foundation_founder_signoff=None
#   - Construction with explicit values works
#   - Round-trip dataclass → dict → Signals preserves fields

# Step 7 — Detection logic in signal_collectors/github.py
# Add helper function (private):
#   def _detect_foundation_change_signals(pr: GitHubPR, founder_login: str) -> tuple[bool|None, bool|None]:
#       """Detect codex-approved label + founder sign-off comment marker."""
#       if pr is None or pr.state == "unknown":
#           return None, None
#       codex_approved = any(
#           label.lower() == "codex-approved"
#           for label in (pr.labels or [])
#       )
#       founder_signoff = False
#       for comment in (pr.comments or []):
#           if comment.author.lower() != founder_login.lower():
#               continue
#           body = comment.body or ""
#           if "founder sign-off" in body.lower() or "✅ ship" in body:
#               founder_signoff = True
#               break
#       return codex_approved, founder_signoff
#
# Wire into existing github.py collect_github_signals(...) call site:
#   - Compute via _detect_foundation_change_signals
#   - Populate signals.foundation_codex_approved + signals.foundation_founder_signoff
#   - founder_login: configurable via env GITHUB_FOUNDER_LOGIN, default "maingocanh"
#   - On API failure (PR not found, rate-limited): keep both fields None (per Signals convention)
#
# DO NOT change identity resolution / pagination / rate limiting.
# Add unit tests in test_foundation_change_signals.py:
#   - PR with codex-approved label + founder comment "founder sign-off"
#   - PR with codex-approved label only (no founder comment)
#   - PR with founder ✅ ship comment only (no codex label)
#   - PR with neither
#   - PR with non-founder commenter saying "founder sign-off" — does NOT count
#   - PR is None / state=unknown → both None
#   - Case-insensitive label match ("Codex-Approved" still matches)

# Step 8 — Run unit + integration suite
pytest tests/unit/work_state/test_foundation_change_signals.py -q
pytest tests/unit/work_state/ tests/integration/work_state/ -q
```

### ✅ CHECKPOINT C — Phase C foundation_change signals complete

```bash
# 1. Signals has 2 new fields
python -c "from scripts.work_state.models import Signals; \
  s = Signals.__dataclass_fields__; \
  assert 'foundation_codex_approved' in s; \
  assert 'foundation_founder_signoff' in s; \
  default = Signals(); \
  assert default.foundation_codex_approved is None; \
  assert default.foundation_founder_signoff is None; \
  print('OK: 2 new fields')"

# 2. github.py has detection helper
grep -q "_detect_foundation_change_signals\|foundation_codex_approved" scripts/work_state/signal_collectors/github.py \
  || { echo "FAIL: detection logic not wired in github.py"; exit 1; }

# 3. New unit tests file present
test -f tests/unit/work_state/test_foundation_change_signals.py

# 4. APPEND-ONLY: verify existing Signals fields not renamed/removed
python -c "from scripts.work_state.models import Signals; \
  s = Signals.__dataclass_fields__; \
  must_have = {'pr_state','ci_state','review_state','deploy_state', \
               'spec_hash','spec_modified_at','tech_hash','tech_modified_at', \
               'tracker_row_hash'}; \
  missing = must_have - set(s.keys()); \
  assert not missing, f'FAIL: lost fields {missing}'; \
  print('OK: APPEND-ONLY preserved')"

# 5. mypy + lint + tests clean
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports
pytest tests/unit/work_state/ tests/integration/work_state/ -q

# 6. Branch ahead ≥6 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 6

# 7. Working tree clean
test -z "$(git status --porcelain)"

echo ""
echo "✓✓✓ CHECKPOINT C PASSED — proceeding to Phase D (projection rendering)"
echo ""
```

```bash
# ============================================================
# Phase D — Projection urgency badge rendering (Steps 9-10)
# Goal: HTML 🔥/⚠️/👁/✓ + MD column + JSON urgency field in state block
# ============================================================

# Step 9 — Update scripts/work_state/projections/dashboard.py
# In build_state_block(work_item, current_state, ...) helper:
#   - Add `urgency` key to returned dict (alongside `base_status`, `overlays`, etc.)
#   - urgency value = current_state.runtime_urgency
# In emoji_for_state helper (or add new emoji_for_urgency):
#   URGENCY_EMOJI = {
#       "critical": "🔥",
#       "elevated": "⚠️",
#       "warning": "👁",
#       "normal": "✓",
#   }
# Single-read pattern preserved (Codex MYM-6 R1 H1 lesson — read state file once)

# Step 10 — Update scripts/build-dashboard.py
# Thread urgency through HTML + MD renderers:
#   HTML: state badge cell renders `{emoji} {urgency}` after base_status badge
#   MD column "Computed": include urgency in same cell as base_status
#     Format: "in-progress 🔥 critical" or "merged ✓ normal"
#   JSON: state block dict already has urgency from projection (no extra work)
#
# Verify uniform across HTML/MD (Codex MYM-6 M4 lesson):
#   - Both formats show same urgency for same item
#   - Both fallback to "normal ✓" if engine soft-fail
#
# Run regression on existing build-dashboard tests:
pytest tests/unit/ tests/integration/ -q -k "build_dashboard or projection"
```

### ✅ CHECKPOINT D — Phase D projection rendering complete

```bash
# 1. projections/dashboard.py adds urgency key
grep -q "urgency" scripts/work_state/projections/dashboard.py \
  || { echo "FAIL: projection missing urgency"; exit 1; }

# 2. URGENCY_EMOJI present somewhere (projection or build-dashboard)
grep -qE "URGENCY_EMOJI|critical.*🔥|🔥.*critical" \
  scripts/work_state/projections/dashboard.py scripts/build-dashboard.py \
  || { echo "FAIL: URGENCY_EMOJI map missing"; exit 1; }

# 3. build-dashboard.py threads urgency
grep -qE "urgency" scripts/build-dashboard.py \
  || { echo "FAIL: build-dashboard not threading urgency"; exit 1; }

# 4. mypy + lint + tests clean
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports
pytest tests/unit/work_state/ tests/integration/work_state/ -q

# 5. Branch ahead ≥8 commits
test "$(git rev-list --count origin/main..HEAD)" -ge 8

# 6. Working tree clean
test -z "$(git status --porcelain)"

echo ""
echo "✓✓✓ CHECKPOINT D PASSED — proceeding to Step 11 (Dogfood)"
echo ""
```

```bash
# ============================================================
# Step 11 — Dogfood end-to-end
# ============================================================

# Run engine + build-dashboard against real tracker
python scripts/build-dashboard.py 2>&1 | tee .autopilot/state/work-state-1d/dogfood-run-1.log

# Verify HTML has urgency badges
grep -cE "(🔥|⚠️|👁|✓)" docs/dashboard.html
# Expected: ≥1 per state row (current main has ~46 state badges, expect similar count
# of urgency emojis — at least most rows should render urgency now)

# Verify MD has urgency in Computed column
grep -cE "(critical|elevated|warning|normal)" docs/dashboard.md
# Expected: at least 1 per state-aware row

# Verify JSON has urgency field
python -c "
import json
d = json.load(open('docs/dashboard.json'))
features = d.get('features', d.get('items', []))
with_urgency = [f for f in features if isinstance(f.get('state'), dict) and 'urgency' in f.get('state', {})]
print(f'Features with state.urgency: {len(with_urgency)} / {len(features)}')
assert len(with_urgency) > 0, 'FAIL: no features have urgency'
"

# Save dogfood notes
cat > .autopilot/state/work-state-1d/dogfood-notes.md <<EOF
# Phase 1d Dogfood Run

- Date: $(date -Iseconds)
- HTML urgency emoji count: $(grep -cE "(🔥|⚠️|👁|✓)" docs/dashboard.html)
- MD urgency level mentions: $(grep -cE "(critical|elevated|warning|normal)" docs/dashboard.md)
- JSON features with state.urgency: see python output above

EOF
```

### ✅ CHECKPOINT E — Phase A/B/C/D codegen + dogfood complete

```bash
# 1. Dogfood artifact present
test -f .autopilot/state/work-state-1d/dogfood-notes.md

# 2. Branch ahead ≥9 commits (≥1 per Step + checkpoint commits)
test "$(git rev-list --count origin/main..HEAD)" -ge 9

# 3. Final test suite green
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 4. mypy strict full scope
mypy core markets i18n tests scripts/work_state

# 5. lint-imports + ruff + black
ruff check .
black --check .
lint-imports

# 6. Working tree clean
test -z "$(git status --porcelain)"

# 7. NO docs deleted
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs deleted"; exit 1; } \
  || echo "OK"

# 8. NO scope creep on Phase 2 features
git diff origin/main scripts/work_state/engine.py 2>&1 | grep -E '(primary.*status|computed-as-primary)' \
  && { echo "FAIL: Phase 2 scope creep"; exit 1; } \
  || echo "OK"

echo ""
echo "✓✓✓ CHECKPOINT E PASSED — codegen complete. Proceeding to Step 12 (Codex review)"
echo ""
```

```bash
# ============================================================
# Step 12 — Codex Review rounds (Foundation Lane: max 8 rounds; founder approval after 5)
# ============================================================

# Round 1: full review of derive_urgency + MAX agg + foundation_change signals + projection
# Save artifact: .autopilot/state/work-state-1d/codex/round-1-review.md
# Apply fixes if P0/P1/P2 findings exist. Commit fixes per finding (atomic).

# Round 2: full re-review. Goal: CLEAN.
# If Round 2 clean → STOP. P1 Foundation needs 2× consecutive clean.
# If Round 2 has new findings → fix + Round 3. Repeat to max 8.

# Halts:
#   - Same finding flagged ≥2 rounds after fix → RECURRING_FINDING circuit breaker
#   - Round 5 reached without 2× consecutive clean → HALT, founder approval required
```

### ✅ CHECKPOINT F — Codex Review complete

```bash
# 1. ≥2 codex round artifacts
ls -1 .autopilot/state/work-state-1d/codex/round-*-review.md | wc -l  # ≥2

# 2. Last 2 rounds both clean
for n in $(ls -1 .autopilot/state/work-state-1d/codex/round-*-review.md | sort | tail -2); do
  grep -qE '(^|\s)(P0|P1|P2):' "$n" && { echo "FAIL: round $n has open P-finding"; exit 1; }
done

# 3. Tests + lint still green
pytest tests/unit/work_state/ tests/integration/work_state/ -q
mypy core markets i18n tests scripts/work_state
lint-imports

# 4. No new # type: ignore
git diff origin/main -- scripts/work_state/ | grep -E '^\+.*#\s*type:\s*ignore' \
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
READY — MYM-10 Phase 1d mega-bundle complete

Branch:    feat/MYM-10-work-state-1d-urgency-bundle
Commits:   <count>
Tests:     <unit+integration count> passing
Lint:      ruff clean, black clean, mypy strict full-scope clean, lint-imports 5/5
Codex:     <round count> rounds, last 2 clean
Dogfood:   <pass/fail> — see .autopilot/state/work-state-1d/dogfood-notes.md
Phase 1d sub-phases:
  - Phase A derive_urgency (AC11b) ✓
  - Phase B MAX urgency aggregation wired (AC11d) ✓
  - Phase C foundation_change milestone signals (AC11c) ✓
  - Phase D projection urgency badge rendering ✓
Out-of-scope confirmed deferred:
  - Progress profile docs_only/dashboard_engine refinement → separate ticket
  - 7-day shadow validation → parallel (not blocking)
  - Phase 2 promotion (computed → primary) → post-shadow gate
  - foundation_change progress milestone EVENT emission → separate scope

Next step (founder action — manual squash per P1 manual_only):
  1. Review PR diff (focus: status_machine.py + engine.py + projection + github.py)
  2. Confirm AC11b + AC11c + AC11d in code
  3. Verify dashboard.html/.md/.json render urgency badges correctly
  4. Squash-merge with founder sign-off in PR body
  5. Update Linear MYM-10 → Done
  6. Phase 2 promotion gate: 7-day shadow window expires ~2026-05-27
EOF
```

## Circuit breakers (HALT immediately, escalate to founder)

1. **Pre-flight failure** — any prerequisite missing (1a/1b/1b'/1c/A/B module, Signals fields, overlays enum 18, engine.py hardcode, aggregation function, venv, gh auth, codex/claude binary).
2. **Out-of-scope touch** — modifications outside Phase 1d scope (filesystem.py, git.py, ci.py, railway.py, plan_reader.py, event_engine.py, progress.py, state_store.py, workflows/*.yml, .importlinter).
3. **Phase 2 scope creep** — computed-status-as-primary changes. Phase 1d stays side-by-side shadow.
4. **Docs deletion** — any `.md` file deleted (CLAUDE.md hard rule #2).
5. **`# type: ignore` introduced** — strict-mode escape hatch needs founder approval.
6. **Recurring Codex finding** — same finding flagged ≥2 rounds after fix attempts.
7. **Review cap reached** — Round 5 without 2× consecutive clean → founder approval required to continue.
8. **Test regression** — any prior phase existing test starts failing.
9. **Working tree dirty after step commit** — atomic commit discipline broken.
10. **Branch behind origin/main** — rebase needed; pause for founder.
11. **CHECKPOINT skip** — proceeding to Phase B without CHECKPOINT A pass, etc.
12. **xfail used to mask broken AC** — only for documented deferred contracts.
13. **Sandbox vs host git lock conflict** — `.git/index.lock` present → halt.
14. **Signals field reordering/removal** — APPEND-ONLY rule broken.
15. **Uppercase letter in branch name** — pr-validate regex fails (MYM-9 not shipped yet).

## Acceptance criteria (mapped to spec §13)

- [ ] **AC11b** — `derive_urgency(base, overlays, priority, risk_tier) → "normal"|"warning"|"elevated"|"critical"` per spec §9.4.1 first-match-wins. Module-level `URGENCY_ORDER` constant defined. ≥18 unit tests covering each tier ≥3 cases.
- [ ] **AC11c** — `signal_collectors/github.py` detects `codex-approved` label + founder sign-off comment marker. Signals APPEND-ONLY +2 fields (`foundation_codex_approved`, `foundation_founder_signoff`). Configurable founder login via env.
- [ ] **AC11d** — `aggregate_multi_branch_urgency(urgencies)` returns MAX per spec §9.4.2. Wired into engine.py: per-branch urgency computed, then aggregated for multi-branch items. Engine output `CurrentState.runtime_urgency` is derived (not hardcoded).
- [ ] **Projection rendering** — `projections/dashboard.py` state block has `urgency` key. `build-dashboard.py` renders 🔥/⚠️/👁/✓ in HTML, level in MD Computed column, urgency field in JSON.
- [ ] **Quality gates** — ruff + black + mypy strict (core|markets|i18n|tests|scripts/work_state) + lint-imports 5/5 + pytest no regressions.
- [ ] **Codex** — 2× consecutive clean (P1 Foundation Lane per CLAUDE.md hard rule #5).
- [ ] **Dogfood** — dashboard.html post-rebuild has urgency badges ≥1 per state row (verify against actual real tracker).
- [ ] **No scope creep** — Phase 2 features absent from diff.

## References

- Linear: [MYM-10](https://linear.app/maingocanh/issue/MYM-10)
- Spec: `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.3.0 §9.4 + §4.1.3 + §9.1
- Vision: `docs/operations/dashboard-engine/product-vision.md` v0.1.0
- Predecessor prompts (read-only reference for patterns):
  - `docs/autopilot/prompts/work-state-engine-1c-autopilot.md` (mega-bundle MYM-5)
  - `docs/autopilot/prompts/dashboard-live-view-B-autopilot.md` (MYM-7 doc-change)
- CLAUDE.md hard rules: #1, #2, #3, #5, #6, #7, #8
- Memory rules:
  - `feedback_autopilot_preflight_must_include_tests_mypy` — pre-flight full mypy scope (MYM-4 lesson)
  - `feedback_megaprompt_with_checkpoints_works` — 4-phase mega-prompt rigor
  - `feedback_admin_squash_bypass_pr_validate_regex` — lowercase branch convention (until MYM-9)
  - `feedback_claude_p_text_mode_buffering` — monitor via git log poll
  - `feedback_sandbox_git_lock_leak` — sandbox git writes leak locks
  - `feedback_concurrency_one_session` — STRICT 1 session per .git/
  - `feedback_never_auto_delete_docs` — never delete .md files
  - `feedback_pin_deferred_contracts` — xfail only for explicit deferred contracts
  - `feedback_cowork_artifact_bash_400` — monitor via terminal while-loop

## How to use this prompt (founder)

```bash
# 1. Commit this prompt + tracker row update to main first (bootstrap)
cd /Users/maingocanh/Projects/MyMoneyWent
git checkout main
git add docs/autopilot/prompts/work-state-1d-autopilot.md \
        docs/implementation-tracker.md
git commit -m "docs(work-state-engine): bootstrap MYM-10 Phase 1d autopilot prompt + tracker row

Ref MYM-10"
git push origin main

# 2. Create worktree
cd /Users/maingocanh/Projects/MyMoneyWent
git worktree add ../MyMoneyWent-1d -b feat/MYM-10-work-state-1d-urgency-bundle main
cd ../MyMoneyWent-1d
ln -s /Users/maingocanh/Projects/MyMoneyWent/.venv .venv
source .venv/bin/activate
mkdir -p .autopilot/state/work-state-1d/codex

# 3. Fire (background — tee log for audit)
claude -p "$(cat docs/autopilot/prompts/work-state-1d-autopilot.md)" \
  2>&1 | tee .autopilot/state/work-state-1d/run-$(date +%s).log

# 4. Monitor via git log poll (per memory feedback_claude_p_text_mode_buffering)
# Open separate terminal:
cd /Users/maingocanh/Projects/MyMoneyWent-1d
while true; do
  clear
  echo "=== $(date) ==="
  git log --oneline -15
  echo ""
  echo "=== Codex artifacts ==="
  ls -1 .autopilot/state/work-state-1d/codex/ 2>/dev/null || echo "(none yet)"
  echo ""
  echo "=== Process ==="
  ps aux | grep -E "tee.*work-state-1d" | grep -v grep | head -1 || echo "(claude exited)"
  sleep 30
done

# 5. After READY emitted:
#    - gh pr create với founder sign-off body
#    - gh pr checks <num> --watch (CI lint + tests + linear-sync + pr-validate)
#    - On all green: gh pr merge --squash --delete-branch
#    - Update Linear MYM-10 → Done
#    - Phase 2 promotion gate: 7-day shadow window
```

## Estimated effort

- **Codegen Phase A-D (Steps 1-11):** ~150-240 min wallclock (4 sub-phases, ~30-60 min each)
- **Codex review (Step 12):** ~30-90 min (Foundation Lane, expect 2-4 rounds for 4-phase scope)
- **Founder squash + Linear close:** ~10 min
- **CI fix cycle (if any):** ~10-15 min (per MYM-4 lesson)
- **Total wallclock to READY:** ~3-5 hours (slightly less than MYM-5's 2.5-4h because Phase 1d has fewer new files but same number of sub-phases)

Compare to predecessors:
- MYM-1 Phase 1a: ~1.5h (10 modules, 127 tests)
- MYM-3 Phase 1b: ~50min (3 collectors, 63 tests)
- MYM-4 Phase 1b': ~1h + 10min CI fix (1 module, 23 tests)
- MYM-5 Phase 1c: ~2h (mega-bundle 4 sub-phases, 32 tests)
- MYM-6 Phase A: ~2h (1 module, 369 LOC new tests)
- MYM-7 Phase B: ~2h (3 collectors extended, ~30 new tests)
- **MYM-10 Phase 1d: similar profile to MYM-5/7** — 4 sub-phases, ~25-35 tests new, no new modules but baseline modifications across 5 files
