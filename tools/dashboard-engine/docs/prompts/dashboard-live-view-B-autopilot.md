# Autopilot Prompt — Dashboard Live View Phase B (doc-change awareness)

> **Status:** READY 2026-05-21 · gated by MYM-6 Phase A merge (✅ merged `bc8260f` 2026-05-21).
> **Plan source:** `docs/operations/dashboard-engine/dashboard-live-view-plan.md` v0.2.1 §3 Phase B.
> **Vision context:** `docs/operations/dashboard-engine/product-vision.md` v0.1.0.
> **Linear ticket:** [MYM-7](https://linear.app/maingocanh/issue/MYM-7) — Phase B doc-change awareness.
> **Predecessors:** MYM-1 `5072e9e` · MYM-3 `3e654cf` · MYM-4 `2396107` · MYM-5 `fb7a587` · MYM-6 `bc8260f`.

---

## Scope reminder (vs other live-view phases)

| Phase | Status | Scope | This prompt? |
|---|---|---|---|
| A | ✅ Merged (MYM-6) | engine → build-dashboard wire | NO (prerequisite) |
| **B** | **This prompt (MYM-7)** | **doc-change awareness — filesystem.py extension + Signals APPEND-ONLY + 4 overlays + spec v1.3.0** | **YES** |
| C | Future, BLOCKED by SPA decision | Per-feature event activity feed | NO |
| D | Future | Upgrade client-side polling (HTML-SHA → JSON state-aware diff) | NO |
| E | Future, OPTIONAL | Latency tuning (cron + quick mode), gated by measured staleness >5% | NO |

> **Why Phase B now:** Phase A merged → engine state visible trong dashboard. Phase B adds critical doc-change tracking để founder không miss spec edits post-ship. Engine-side extension, no SPA dependency (Phase C blocked by SPA).

---

```
Task: Dashboard Live View Phase B — doc-change awareness (filesystem.py extension + Signals APPEND-ONLY + 4 overlays + spec v1.3.0 bump)
You are working in /Users/maingocanh/Projects/MyMoneyWent-live-view-B on MyMoneyWent
(multi-tenant personal finance bot, dual-market VN+Global). NO prior conversation context.
This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-7-dashboard-live-view-B`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY on
circuit-breaker conditions (§Circuit breakers).

Risk tier:          P1 Foundation Lane (Signals dataclass APPEND-ONLY + spec bump)
Merge policy:       manual_only (CLAUDE.md hard rule #6)
Autopilot maturity: pilot (sixth engine-related implementation run; first doc-change tracking)
Codex review:       2× consecutive clean required (P1 Foundation Lane)

Prerequisite: MYM-1 + MYM-3 + MYM-4 + MYM-5 + MYM-6 all merged ✓ on main at bc8260f or later.

Scope of this prompt — ONLY Phase B:
  MODIFY:
    scripts/work_state/signal_collectors/filesystem.py    # ADD spec/tech/tracker hash tracking
    scripts/work_state/models.py                          # APPEND-ONLY 5 fields to Signals
    scripts/work_state/event_engine.py                    # ADD 3 event types
    scripts/work_state/status_machine.py                  # ADD overlay emission rules
    scripts/build-dashboard.py                            # ADD HTML badge rendering per overlay (Phase A wired already)
    docs/operations/dashboard-engine/dashboard-plan-state-split.md  # v1.2.1 → v1.3.0 (§8.2 enum 14→18)
  NEW:
    tests/unit/work_state/test_signals_doc_hash.py        # filesystem.py hash tests
    tests/unit/work_state/test_overlays_doc_changes.py    # status_machine overlay tests
    tests/integration/work_state/test_doc_change_e2e.py   # e2e doc change → overlay → dashboard render

Do NOT touch:
  - scripts/work_state/{plan_reader,event_engine,progress,state_store,engine}.py beyond minimal additions
  - scripts/work_state/signal_collectors/{git,github,ci,railway}.py — read-only baseline
  - scripts/work_state/projections/dashboard.py — read-only consumer (MYM-4)
  - .github/workflows/dashboard.yml — Phase C/E territory
  - .importlinter — no boundary changes needed
  - Any other .md file under docs/ — read-only (NEVER delete per CLAUDE.md hard rule #2)
  - docs/dashboard.{html,md,json} — auto-generated, do not edit manually

Out-of-scope-but-documented:
  - Event activity feed UI → Phase C (blocked by SPA decision per product-vision §92)
  - Client-side polling upgrade → Phase D
  - Cron / latency tuning → Phase E (optional, deferred)
  - MAX urgency aggregation §4.1.3 → Phase 1d
  - runtime_urgency derivation → Phase 1d
  - Phase 2 promotion (computed → primary status) → 7-day shadow + validation gate

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-engine/dashboard-live-view-plan.md v0.2.1 §3 Phase B — focus:
   - Scope spec (5 new fields, 3 events, 4 overlays)
   - **Semantic hash specification** — include (branch, linear_id, feature_id, specs, acceptance) ONLY
   - **Exclude** status/notes/gates/changelog/formatting (avoid false-positive drift on auto-flip)
   - ACs B1-B10

2. docs/operations/dashboard-engine/product-vision.md v0.1.0 — focus:
   - Decisions §92 (Frontend tách SPA trước Phase C — Phase B independent của SPA)
   - "What NOT to build until validated" list

3. docs/operations/dashboard-engine/dashboard-plan-state-split.md v1.2.1 — focus:
   - §8.2 Overlay enum (canonical 14 — extending to 18 in this phase)
   - §6.1 Filesystem signals (current spec_exists boolean — extending)
   - §11.2 Signals dataclass model sketch
   - §7.1 Event log format (new event types)
   - §13 AC10 (overlays per canonical §8.2) + §13 new ACs B1-B10

4. CLAUDE.md — focus hard rules: #1, #2, #3 (spec bump v1.3.0), #5, #6, #7, #8

5. Phase 1a-1c + 1b' + Phase A deliverables (READ-ONLY):
   - scripts/work_state/signal_collectors/filesystem.py — current implementation pattern
   - scripts/work_state/models.py — Signals dataclass current state (extend APPEND-ONLY)
   - scripts/work_state/event_engine.py — event types pattern (extend)
   - scripts/work_state/status_machine.py — overlay emission pattern (extend)
   - scripts/build-dashboard.py — Phase A's engine invocation + HTML rendering (extend with overlay badges)
   - tests/integration/work_state/test_engine_e2e_phase1b.py — e2e wiring test pattern

6. docs/implementation-tracker.md — sample real rows for tracker_row_hash testing

Pre-flight gate (HARD — halt if any fails):

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-live-view-B
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-7-dashboard-live-view-B
git fetch origin
git log --oneline origin/main..HEAD -5
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat behind origin/main"; exit 1; }

# Phase A + 1c + 1b + 1a + 1b' prerequisite — all modules importable
python -c "from scripts.work_state.engine import run_engine; print('OK: engine')"
python -c "from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals; print('OK: filesystem')"
python -c "from scripts.work_state.models import Signals; print('OK: Signals')"
python -c "from scripts.work_state.event_engine import emit_event; print('OK: event_engine')" 2>/dev/null || \
  python -c "import scripts.work_state.event_engine; print('OK: event_engine module')"
python -c "from scripts.work_state.status_machine import compute_status; print('OK: status_machine')"

# .dashboard/ gitignored
grep -q "^\.dashboard/$" .gitignore     || { echo "FAIL: .dashboard/ not in .gitignore"; exit 1; }

source .venv/bin/activate
which python && which gh && gh auth status && which codex && which claude

# FULL mypy strict scope per CLAUDE.md style + memory feedback_autopilot_preflight_must_include_tests_mypy
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports                            # 5 contracts pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short  # baseline 245+ tests pass

# ===== PRE-FLIGHT CHECKPOINT =====
echo ""
echo "✓✓✓ PRE-FLIGHT PASSED — proceeding to Phase B codegen"
echo ""
```

Anti-patterns (NEVER do):

* `git push --force`
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed)
* Auto-merge ngoài STOP_AT_READY (P1 manual_only)
* MODIFY Signals dataclass field signatures (APPEND-ONLY — add 5 new fields, never edit existing)
* Touch out-of-scope modules (railway/github/ci collectors, projections/, workflow YAML, importlinter, dashboard.{html,md,json})
* Implement Phase C/D/E features — explicit out-of-scope creep
* Include status/notes/gates/changelog trong tracker_row_hash — violates B2 + B8 (auto-flip false positives)
* Overload existing `artifact-drift` overlay (reserved for PR/branch mapping mismatch per §6.8)
* Use new overlay names ngoài 4 declared (`spec-modified`, `tech-modified`, `tracker-modified`, `post-ship-doc-change`)
* Skip spec v1.3.0 bump (B7 requires spec sign-off Codex re-review §8.2)
* Skip TDD gate
* `xfail` to mask broken AC

Numbered steps:

```bash
# ============================================================
# Phase B codegen (Steps 1-8)
# ============================================================

# Step 1 — Confirm branch + state dir
git status
git branch --show-current
test -d .autopilot/state/dashboard-live-view-B/codex \
  || { echo "FAIL: codex artifact dir missing"; exit 1; }

# Step 2 — Bump spec to v1.3.0 (PR §8.2 enum extension)
# Edit docs/operations/dashboard-engine/dashboard-plan-state-split.md:
#   - Frontmatter: version v1.2.1 → v1.3.0, updated 2026-05-21
#   - §8.2 canonical overlay enum: 14 → 18 (add spec-modified, tech-modified, tracker-modified, post-ship-doc-change)
#   - §6.1 Filesystem signals: extend description with hash tracking
#   - §7.1 Event log: add 3 new event types (spec_modified, tech_modified, tracker_row_modified)
#   - Changelog: add v1.3.0 entry documenting additive enum extension + filesystem hash tracking
# Commit: "docs(spec): bump v1.3.0 — extend §8.2 overlay enum + §6.1 filesystem hash tracking for Phase B doc-change awareness"

# Step 3 — TDD: write failing tests FIRST
# tests/unit/work_state/test_signals_doc_hash.py — APPEND-ONLY field tests:
#   - test_signals_has_5_new_fields  (spec_hash, spec_modified_at, tech_hash, tech_modified_at, tracker_row_hash)
#   - test_filesystem_collector_computes_spec_hash_when_file_exists
#   - test_filesystem_collector_computes_tech_hash
#   - test_filesystem_collector_computes_tracker_row_hash_for_semantic_fields_only
#   - test_tracker_row_hash_excludes_status_field  (B8 — auto-flip doesn't trigger drift)
#   - test_tracker_row_hash_excludes_notes_gates_changelog
#   - test_tracker_row_hash_stable_across_formatting_whitespace
#
# tests/unit/work_state/test_overlays_doc_changes.py — overlay emission:
#   - test_spec_modified_overlay_when_hash_changes  (B3 + B4)
#   - test_tech_modified_overlay_when_hash_changes
#   - test_tracker_modified_overlay_when_semantic_hash_changes
#   - test_post_ship_doc_change_overlay_when_terminal_state_row_edited  (B6)
#   - test_4_new_overlays_in_canonical_enum  (B4)
#
# tests/integration/work_state/test_doc_change_e2e.py — full pipeline:
#   - test_engine_emits_spec_modified_event  (B3)
#   - test_dashboard_html_renders_spec_changed_badge  (B5)
#   - test_status_auto_flip_does_NOT_trigger_drift_warning  (B8)
#   - test_post_ship_terminal_status_row_edit_triggers_warning_overlay  (B6)
pytest tests/unit/work_state/test_signals_doc_hash.py tests/unit/work_state/test_overlays_doc_changes.py tests/integration/work_state/test_doc_change_e2e.py -q  # expect FAIL

# Step 4 — Extend models.py Signals dataclass APPEND-ONLY (+5 fields):
#   spec_hash: str | None = None
#   spec_modified_at: str | None = None  # ISO date
#   tech_hash: str | None = None
#   tech_modified_at: str | None = None
#   tracker_row_hash: str | None = None
# Run baseline tests to verify APPEND-ONLY safe (no regression).
pytest tests/unit/work_state/test_models.py -q

# Step 5 — Implement filesystem.py extension:
#   - Add _compute_file_hash(path: Path) → str | None  (SHA256 hex, None if missing)
#   - Add _get_file_mtime(path: Path) → str | None  (ISO date string)
#   - Add _compute_tracker_row_hash(item: WorkItem) → str | None
#       Use ONLY (branch, linear_id, feature_id, specs path, acceptance criteria)
#       SHA256 over canonical serialization (sorted dict / tuple)
#   - Extend collect_filesystem_signals to populate 5 new Signals fields
# Run unit tests; should pass ≥80%.
pytest tests/unit/work_state/test_signals_doc_hash.py -q

# Step 6 — Implement event_engine.py + status_machine.py extensions:
#   event_engine: add 3 event types:
#     - spec_modified (item_id, from_hash, to_hash, source: 'filesystem.spec')
#     - tech_modified (item_id, from_hash, to_hash, source: 'filesystem.tech')
#     - tracker_row_modified (item_id, from_hash, to_hash, source: 'filesystem.tracker')
#   status_machine: add overlay emission rules:
#     - spec_modified event → 'spec-modified' overlay (annotation)
#     - tech_modified event → 'tech-modified' overlay (annotation)
#     - tracker_row_modified event → 'tracker-modified' overlay (annotation)
#     - PLUS: if item status terminal (merged/deployed/abandoned) AND any doc-change event → 'post-ship-doc-change' overlay (warning, stronger)
# Run overlay unit tests.
pytest tests/unit/work_state/test_overlays_doc_changes.py -q

# Step 7 — Wire build-dashboard.py HTML badge rendering:
#   Add CSS classes + HTML badge per new overlay:
#     - .badge-spec-modified (annotation, blue/info color)
#     - .badge-tech-modified (annotation)
#     - .badge-tracker-modified (annotation)
#     - .badge-post-ship-doc-change (WARNING, distinct color e.g., amber/red)
#   Render badges side-by-side với existing state column từ Phase A.
#   Verify no regression on Phase A state.human_status + .state cells.
pytest tests/unit/test_build_dashboard.py -q  # smoke Phase A regression
pytest tests/integration/work_state/test_doc_change_e2e.py -q

# Step 8 — Dogfood + verify side-by-side:
mkdir -p /tmp/live-view-B-dogfood
python scripts/build-dashboard.py \
  --tracker docs/implementation-tracker.md \
  --output-html /tmp/live-view-B-dogfood/dashboard.html \
  --output-md /tmp/live-view-B-dogfood/dashboard.md \
  --output-json /tmp/live-view-B-dogfood/dashboard.json \
  --no-network \
  --dashboard-dir .dashboard \
  2>&1 | tee .autopilot/state/dashboard-live-view-B/dogfood-run-1.log

# Verify badges render:
grep -c "spec-modified\|tech-modified\|tracker-modified\|post-ship-doc-change" \
  /tmp/live-view-B-dogfood/dashboard.html

# Idempotency
python scripts/build-dashboard.py \
  --tracker docs/implementation-tracker.md \
  --output-html /tmp/live-view-B-dogfood/dashboard.html \
  --no-network \
  2>&1 | tee .autopilot/state/dashboard-live-view-B/dogfood-run-2.log

cat > .autopilot/state/dashboard-live-view-B/dogfood-notes.md <<EOF
# Phase B Dogfood Run
- Date: $(date -Iseconds)
- Tracker: docs/implementation-tracker.md
- Doc-change overlays detected: TBD
- post-ship-doc-change warnings: TBD (count terminal rows edited)
- Idempotency: TBD
EOF
```

### ✅ CHECKPOINT A — Phase B Codegen complete

```bash
# 1. New + modified files present
git diff --name-only origin/main | grep -E '^(scripts/work_state/signal_collectors/filesystem\.py|scripts/work_state/models\.py|scripts/work_state/event_engine\.py|scripts/work_state/status_machine\.py|scripts/build-dashboard\.py|docs/operations/dashboard-engine/dashboard-plan-state-split\.md|tests/unit/work_state/test_signals_doc_hash\.py|tests/unit/work_state/test_overlays_doc_changes\.py|tests/integration/work_state/test_doc_change_e2e\.py)$' \
  || { echo "FAIL: expected file changes missing"; exit 1; }

# 2. NO out-of-scope touch
git diff --name-only origin/main | grep -E '^(scripts/work_state/signal_collectors/(git|github|ci|railway)\.py|scripts/work_state/projections/|scripts/work_state/plan_reader\.py|scripts/work_state/state_store\.py|\.github/workflows/|\.importlinter)$' \
  && { echo "FAIL: touched out-of-scope module"; exit 1; } \
  || echo "OK: scope respected"

# 3. Signals APPEND-ONLY verified (only field additions, no signature changes)
git diff origin/main scripts/work_state/models.py | grep -E '^-\s+\w+:' \
  && { echo "FAIL: Signals field removed/modified (must be APPEND-ONLY)"; exit 1; } \
  || echo "OK: Signals APPEND-ONLY safe"

# 4. All tests pass
pytest tests/unit/work_state/ tests/integration/work_state/ tests/unit/test_build_dashboard.py -q --tb=short

# 5. mypy + lint clean FULL SCOPE
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports

# 6. Branch ahead by ≥7 atomic step-commits (1 per Step)
test "$(git rev-list --count origin/main..HEAD)" -ge 7

# 7. Working tree clean
test -z "$(git status --porcelain)"

# 8. NO docs deleted
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs deleted"; exit 1; } \
  || echo "OK"

# 9. NO scope creep
git diff origin/main scripts/ 2>&1 | grep -E '(runtime_urgency|MAX urgency|compute_overlays.*14.*remove|client.*poll.*json|primary.*status)' \
  && { echo "FAIL: out-of-scope feature detected"; exit 1; } \
  || echo "OK"

# 10. Dogfood artifact present
test -f .autopilot/state/dashboard-live-view-B/dogfood-notes.md

# 11. Spec v1.3.0 frontmatter
grep -q "^version: v1.3.0" docs/operations/dashboard-engine/dashboard-plan-state-split.md \
  || { echo "FAIL: spec not bumped to v1.3.0"; exit 1; }

echo ""
echo "✓✓✓ CHECKPOINT A PASSED — proceeding to Phase B Codex review"
echo ""
```

```bash
# ============================================================
# Step 9 — Codex Review rounds (Foundation Lane: max 8 rounds, founder approval after 5)
# ============================================================

# Round 1: full review including spec v1.3.0 §8.2 changes + filesystem extension + Signals + overlays + HTML
# Save artifact: .autopilot/state/dashboard-live-view-B/codex/round-1-review.md
# Apply fixes if P0/P1/P2 findings.

# Round 2: full re-review. Goal: CLEAN. 
# If R2 clean → STOP. Need 2× consecutive clean.
# Repeat to max 8 (founder approval after 5).
```

### ✅ CHECKPOINT B — Codex Review complete

```bash
# 1. ≥2 codex round artifacts
ls -1 .autopilot/state/dashboard-live-view-B/codex/round-*-review.md | wc -l

# 2. Last 2 rounds both clean
for n in $(ls -1 .autopilot/state/dashboard-live-view-B/codex/round-*-review.md | sort | tail -2); do
  grep -qE '(^|\s)(P0|P1|P2):' "$n" && { echo "FAIL: round $n has open P-finding"; exit 1; }
done

# 3. Tests + lint green
pytest tests/unit/work_state/ tests/integration/work_state/ tests/unit/test_build_dashboard.py -q
mypy core markets i18n tests scripts/work_state
lint-imports

# 4. No new # type: ignore
git diff origin/main | grep -E '^\+.*#\s*type:\s*ignore' && exit 1

# 5. Working tree clean
test -z "$(git status --porcelain)"

echo "✓✓✓ CHECKPOINT B PASSED — emit READY"
```

```bash
# ============================================================
# READY report
# ============================================================
cat <<'EOF'
READY — MYM-7 Dashboard Live View Phase B complete

Branch:    feat/MYM-7-dashboard-live-view-B
Commits:   <count>
Tests:     <unit+integration count> passing (245+ baseline + N new)
Lint:      ruff/black/mypy strict full-scope/lint-imports 5/5 clean
Codex:     <round count> rounds, last 2 clean
Dogfood:   <pass/fail> — see .autopilot/state/dashboard-live-view-B/dogfood-notes.md

Phase B deliverables:
  - filesystem.py extended với spec/tech/tracker_row hash tracking (B1)
  - Signals APPEND-ONLY +5 fields (spec_hash, spec_modified_at, tech_hash, tech_modified_at, tracker_row_hash)
  - 3 new events (spec_modified, tech_modified, tracker_row_modified) (B3)
  - 4 new overlays in §8.2 (spec-modified, tech-modified, tracker-modified, post-ship-doc-change) (B4)
  - Tracker row semantic hash excludes status/notes/gates/changelog (B2 + B8)
  - Dashboard HTML badge rendering (B5 annotation, B6 warning)
  - Spec v1.3.0 bump §8.2 enum extension (B7)

Out-of-scope confirmed deferred:
  - Phase C event activity feed (SPA decision blocked)
  - Phase D client polling upgrade
  - Phase E latency tuning (optional)
  - Phase 1d runtime urgency
  - Phase 2 promotion (computed → primary, 7-day shadow gate)

Next step (founder action — manual squash per P1 manual_only):
  1. Review PR diff (focus: Signals APPEND-ONLY + overlay enum + spec v1.3.0)
  2. Verify status auto-flip không trigger drift (B8 self-test)
  3. Confirm ACs B1-B10 in code
  4. gh pr create + squash-merge với founder sign-off
  5. Linear MYM-7 → Done
  6. Phase 1d urgency parallel, Phase D upgrade client polling next
EOF
```

## Circuit breakers (HALT immediately, escalate to founder)

1. **Pre-flight failure** — any baseline module missing
2. **Out-of-scope touch** — collectors except filesystem.py, projections, workflow YAML, importlinter, dashboard outputs
3. **Signals NOT APPEND-ONLY** — existing field signatures modified/removed
4. **Spec NOT bumped** — v1.2.1 unchanged
5. **Phase C/D/E scope creep** — event feed UI, client polling, cron tuning
6. **Phase 1d scope creep** — runtime_urgency, MAX urgency
7. **Phase 2 scope creep** — computed → primary status
8. **Docs deletion** — any `.md` deleted (CLAUDE.md hard rule #2)
9. **`# type: ignore` introduced**
10. **Status field included in tracker_row_hash** — violates B2 + B8 (auto-flip false positive)
11. **Existing artifact-drift overlay reused for doc changes** — semantic overload
12. **Recurring Codex finding** — same flagged ≥2 rounds after fix
13. **Review cap reached** — Round 5 without 2× clean → founder approval
14. **Test regression** — baseline test fails
15. **Working tree dirty after step commit**
16. **CHECKPOINT skip**
17. **Sandbox vs host git lock conflict**

## Acceptance criteria (mapped to plan v0.2.1 §3 Phase B)

- [ ] **B1** — Engine collects spec_hash + spec_modified_at per WorkItem
- [ ] **B2** — Tracker row semantic hash excludes non-semantic fields per spec list
- [ ] **B3** — Hash change detection emits 3 new events in events.jsonl
- [ ] **B4** — 4 new overlays added to canonical enum §8.2 (18 total)
- [ ] **B5** — Dashboard HTML shows "Spec changed Xh ago" badge for affected features (annotation severity)
- [ ] **B6** — `post-ship-doc-change` overlay surfaces strongly (warning severity, distinct visual)
- [ ] **B7** — Spec v1.3.0 sign-off (Codex re-review §8.2 enum extension)
- [ ] **B8** — Status auto-flip workflow does NOT trigger drift warning
- [ ] **B9** — All Phase 1b/1c/Phase A tests still pass (APPEND-ONLY safe)
- [ ] **B10** — Quality gates 5/5

## References

- Linear: [MYM-7](https://linear.app/maingocanh/issue/MYM-7)
- Plan: `docs/operations/dashboard-engine/dashboard-live-view-plan.md` v0.2.1 §3 Phase B
- Vision: `docs/operations/dashboard-engine/product-vision.md` v0.1.0
- Spec to bump: `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 → v1.3.0
- Predecessor prompts:
  - `docs/autopilot/prompts/work-state-engine-phase-1b-autopilot.md` (MYM-3 collectors extension pattern)
  - `docs/autopilot/prompts/dashboard-live-view-A-autopilot.md` (MYM-6 — Phase A wire)
- Memory rules:
  - `feedback_autopilot_preflight_must_include_tests_mypy` — pre-flight gate full scope
  - `feedback_verify_current_source_before_claiming_gap` — read source before claiming behavior
  - `feedback_claude_p_text_mode_buffering` — monitor via git log poll
  - `feedback_sandbox_git_lock_leak` — sandbox git writes leak locks
  - `feedback_never_auto_delete_docs` — never delete .md files
  - `feedback_pin_deferred_contracts` — xfail only for explicit deferred contracts
  - `feedback_cowork_artifact_bash_400` — terminal while-loop monitor, NOT Cowork widget

## How to use this prompt (founder)

```bash
# 1. Bootstrap commit
cd /Users/maingocanh/Projects/MyMoneyWent
source .venv/bin/activate
rm -f .git/index.lock
git add docs/autopilot/prompts/dashboard-live-view-B-autopilot.md \
        docs/implementation-tracker.md
git commit -m "docs(dashboard-live-view): bootstrap Phase B autopilot prompt + tracker row

Ref MYM-7"
git push origin main

# 2. Create worktree
git worktree add ../MyMoneyWent-live-view-B -b feat/MYM-7-dashboard-live-view-B main
cd ../MyMoneyWent-live-view-B
ln -s /Users/maingocanh/Projects/MyMoneyWent/.venv .venv
source .venv/bin/activate
mkdir -p .autopilot/state/dashboard-live-view-B/codex

# 3. Pre-flight sanity
which python && which gh && gh auth status && which codex && which claude
git branch --show-current

# 4. Fire (~1.5-2h wallclock expected, slightly bigger than Phase A)
claude -p "$(cat docs/autopilot/prompts/dashboard-live-view-B-autopilot.md)" \
  2>&1 | tee .autopilot/state/dashboard-live-view-B/run-$(date +%s).log

# 5. Monitor (terminal while-loop — NOT Cowork widget per memory)
cd /Users/maingocanh/Projects/MyMoneyWent-live-view-B
while true; do
  clear; date
  echo "=== Commits ahead: $(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0) ==="
  git log --oneline -15
  echo "=== Codex artifacts ==="
  ls -1 .autopilot/state/dashboard-live-view-B/codex/ 2>/dev/null
  echo ""
  ps aux | grep "tee.*dashboard-live-view-B" | grep -v grep | head -1 || echo "(claude exited)"
  sleep 30
done

# 6. After READY:
#    - gh pr create với sign-off body
#    - gh pr checks --watch
#    - gh pr merge --squash --delete-branch (PREFER squash this time, không UI conflict)
```

## Estimated effort

- **Codegen Steps 1-8:** ~50-90 min wallclock (more files than Phase A, but each smaller)
- **Codex Phase B (Step 9):** ~30-60 min (3-5 rounds expected — spec v1.3.0 + overlay enum extension scrutiny)
- **Founder squash + Linear close:** ~5 min
- **CI fix cycle (if any):** ~10 min (pre-flight applied MYM-4 lesson)
- **Total wallclock to READY:** ~1.5-3 hours

Compare to predecessors:
- MYM-1 Phase 1a: ~1.5h
- MYM-3 Phase 1b: ~50min
- MYM-4 Phase 1b': ~1h + 10min CI
- MYM-5 Phase 1c: ~2h (bundle)
- MYM-6 Phase A: ~2h
- **MYM-7 Phase B: ~1.5-3h** (bigger than Phase A — touches more modules + spec bump)
