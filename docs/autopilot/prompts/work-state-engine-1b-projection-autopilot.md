# Autopilot Prompt — work-state engine Phase 1b' (projections/dashboard.py)

> **Status:** READY 2026-05-21 · gated by MYM-3 Phase 1b merge (✅ merged 3e654cf 2026-05-20).
> **Spec source:** `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 §10 + §11.1 + §13.
> **Operational snapshot:** `docs/operations/dashboard-engine/dashboard-architecture-snapshot.md` v1.0.1 §5.
> **Linear ticket:** [MYM-4](https://linear.app/maingocanh/issue/MYM-4) — Phase 1b' "Dashboard projection follow-up".
> **Predecessors:** Phase 1a prompt (MYM-1 shipped 5072e9e) · Phase 1b prompt (MYM-3 shipped 3e654cf).
> **Session handoff context:** `docs/operations/dashboard-engine/session-handoff-2026-05-20.md` v1.0.0.

---

## Scope reminder (vs 1a / 1b / 1c / 1d)

| Phase | Status | Operational milestone scope | This prompt? |
|---|---|---|---|
| 1a | ✅ Merged (MYM-1) | skeleton + fs + git collectors | NO (prerequisite) |
| 1b | ✅ Merged (MYM-3) | github + ci + railway collectors | NO (prerequisite) |
| **1b'** | **This prompt (MYM-4)** | **projections/dashboard.py — enrich docs/dashboard.json with `state` block, side-by-side rendering, `--no-network` mode** | **YES** |
| 1c | Future | multi-branch aggregation §4.1 + `.dashboard/` CI persistence + workflow triggers | NO (separate prompt) |
| 1d | Future | runtime urgency algorithm §9.4 | NO (separate prompt) |

> **Scope reconcile (2026-05-20):** Spec §10 canonical put projection in 1b. Operational milestone (snapshot v1.0.1 §5 + tracker + Linear) split projection to its own ticket MYM-4 (1b') for cleaner 1:1 prompt-milestone mapping. Decision: A+ option locked. Spec §10 carries cross-reference footnote acknowledging divergence.

---

```
Task: work-state-engine Phase 1b' — projections/dashboard.py (dashboard state block enrichment)
You are working in /Users/maingocanh/Projects/MyMoneyWent-engine-1b-proj on MyMoneyWent
(multi-tenant personal finance bot, dual-market VN+Global). NO prior conversation context.
This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-4-work-state-engine-1b-projection`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY on
circuit-breaker conditions (§Circuit breakers).

Risk tier:          P1 (additive — read-only consumer of engine output; no production behavior change)
Merge policy:       manual_only (per CLAUDE.md hard rule #6 + template §3.2 P1)
Autopilot maturity: pilot (third engine implementation run on MMW work-state spec)
Codex review:       2x_consecutive_clean required (P1 Standard Lane)

Prerequisite: Phase 1a (MYM-1) merged ✓ at 5072e9e + Phase 1b (MYM-3) merged ✓ at 3e654cf.
This prompt halts pre-flight if any of:
  scripts/work_state/{models,state_store}.py
  scripts/work_state/signal_collectors/{filesystem,git,github,ci,railway}.py
not all present, OR if Signals dataclass missing fields pr_state/ci_state/review_state/deploy_state.

Scope of this prompt — ONLY Phase 1b' per Linear ticket + spec §10 + §11.1:
  scripts/work_state/projections/__init__.py             # package marker
  scripts/work_state/projections/dashboard.py            # main module + CLI
  tests/unit/work_state/test_projections_dashboard.py    # unit coverage AC1g + AC5 + AC6 + AC10
  tests/integration/work_state/test_projection_e2e.py    # e2e: collectors → state_store → projection → dashboard.json

Do NOT touch:
  - scripts/work_state/{models,plan_reader,event_engine,status_machine,progress,state_store}.py — read-only baseline
  - scripts/work_state/signal_collectors/*.py — read-only baseline
  - scripts/build-dashboard.py — Phase 1c (workflow auto-wiring)
  - .github/workflows/dashboard.yml — Phase 1c
  - .dashboard/ runtime state — runtime only, gitignored
  - .importlinter — no boundary changes needed (projections/ is sibling of signal_collectors/)
  - docs/implementation-tracker.md — read-only input
  - Any markdown file under docs/ — read-only (NEVER delete per CLAUDE.md hard rule #2)

Out-of-scope-but-documented:
  - build-dashboard.py auto-wiring projection → Phase 1c (workflow phase)
  - Multi-branch state aggregation (MIN-progressed/UNION-overlays/MAX-urgency §4.1) → Phase 1c
  - Manual `status` field removal → Phase 3 (gated by Phase 2 confidence)
  - Promotion: computed → primary, manual → annotation → Phase 2

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-engine/dashboard-plan-state-split.md v1.2.1 — focus:
   - §10 Phase 1b note: "side-by-side rendering" — keep manual `status`, ADD `state` field
   - §10 Phase 2 note: future promotion plan — projection MUST NOT pre-empt Phase 2
   - §11.1 module placement: `scripts/work_state/projections/dashboard.py`
   - §11.2 model sketch — CurrentState shape (status, human_status, progress, overlays, signals, last_event_ts)
   - §13 AC1g (projection module exists, mypy strict clean)
   - §13 AC5 (dashboard JSON includes computed state/progress + signal drilldown)
   - §13 AC6 (manual status still rendered in shadow mode, computed visible side-by-side)
   - §13 AC10 (overlays from §8.2 canonical enum — propagate from CurrentState into state.overlays)
   - §13 AC11a (human_status field renders alongside machine state — 9 statuses)

2. docs/operations/dashboard-engine/dashboard-architecture-snapshot.md v1.0.1 — focus:
   - §5 phase breakdown row 1b — confirms operational scope
   - §6 target architecture diagram — projection sits between state layer + outputs

3. CLAUDE.md — focus hard rules #1 (1-session-per-.git), #2 (NEVER auto-delete docs), #3 (spec-first),
   #4 (tenant isolation N/A here — projection has no DB), #5 (different-model review P1),
   #6 (manual_only merge), #7 (single-phase scope OK — this prompt is one phase with 2 checkpoints),
   #8 (review cap 5 rounds Standard Lane).

4. Phase 1a + 1b deliverables (READ-ONLY for understanding inputs):
   - scripts/work_state/models.py — CurrentState/Signals/WorkItem dataclasses (consume via dataclasses.asdict round-trip)
   - scripts/work_state/state_store.py — read_current_state(dashboard_dir) → dict | None (existing reader)
   - scripts/work_state/status_machine.py — compute_status + human projection logic (already produces overlays + human_status)
   - Existing tests under tests/unit/work_state/ + tests/integration/work_state/ — pattern for new tests

5. docs/dashboard.json — current schema reference:
   - top-level keys: blockers, docs, features, generated_at, overall, phases, risks
   - features[] row shape: {be_code, be_tech, bot_code, id, name, phase, spec}
   - id field = feature_id (matches WorkItem.feature_id from plan_reader)
   - PROJECTION TARGET: add features[].state = { computed_status, human_status, pr_state, ci_state,
     review_state, deploy_state, overlays, last_event_ts } — DO NOT remove/rename existing fields.

6. docs/implementation-tracker.md — sample real rows for fixture data + dogfood input

Pre-flight gate (HARD — halt if any fails):

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-engine-1b-proj
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-4-work-state-engine-1b-projection
git fetch origin
git log --oneline origin/main..HEAD -5  # verify feat ahead/equal to origin/main
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat behind origin/main"; exit 1; }

# Phase 1a + 1b prerequisite — all modules + Signals fields must exist on main
for f in __init__.py models.py plan_reader.py event_engine.py status_machine.py \
         progress.py state_store.py \
         signal_collectors/__init__.py signal_collectors/filesystem.py \
         signal_collectors/git.py signal_collectors/github.py \
         signal_collectors/ci.py signal_collectors/railway.py; do
  test -f "scripts/work_state/$f" \
    || { echo "FAIL: prerequisite scripts/work_state/$f MISSING"; exit 1; }
done

# Signals dataclass must have Phase 1b fields (smoke check)
python -c "from scripts.work_state.models import Signals; \
  s = Signals.__dataclass_fields__; \
  assert 'pr_state' in s and 'ci_state' in s and 'review_state' in s and 'deploy_state' in s, \
    'FAIL: Signals missing 1b fields'; print('OK: Signals has 1b fields')"

# .dashboard/ gitignored
grep -q "^\.dashboard/$" .gitignore     || { echo "FAIL: .dashboard/ not in .gitignore"; exit 1; }

source .venv/bin/activate
which python                            # MUST resolve to .venv/bin/python
which codex                             # MUST resolve
which claude                            # MUST resolve

ruff check .
black --check .
mypy scripts/work_state/                # 1a + 1b baseline must still be clean
lint-imports                            # 5 contracts pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short  # 1a + 1b tests green (190)

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
* MODIFY any existing Phase 1a/1b module (read-only baseline — projection is pure consumer)
* Touch `scripts/build-dashboard.py` (Phase 1c)
* Touch `.github/workflows/dashboard.yml` (Phase 1c)
* Touch `.importlinter` (no new boundary needed — projections/ is sibling)
* Delete or rename existing `docs/dashboard.json` fields (additive only — `state` block APPEND)
* Skip TDD gate — every new function needs failing tests BEFORE implementation
* Mock state_store / collectors output without real fixtures — use cached real responses or factory builders
* Network calls in projection module — projection is PURE: input is `.dashboard/current_state.json` (already collected by engine driver), output is enriched `docs/dashboard.json`. `--no-network` is the only mode that matters for projection itself (the engine driver handles network).
* `xfail` to mask broken acceptance — only allowed for explicit deferred contracts per memory `feedback_pin_deferred_contracts.md`
* Skip Codex review rounds — P1 needs 2× consecutive clean per template §3.2
* Delete or move any `.md` file (CLAUDE.md hard rule #2 — NEVER auto-delete docs)

Numbered steps:

```bash
# ============================================================
# Phase A — Codegen (Steps 1-6)
# ============================================================

# Step 1 — Confirm on feat branch + create state dir
git status
git branch --show-current
test -d .autopilot/state/work-state-1b-proj/codex \
  || { echo "FAIL: codex artifact dir missing — bootstrap step skipped"; exit 1; }

# Step 2 — TDD: write failing test_projections_dashboard.py FIRST
# Cover:
#   - test_load_state_returns_none_when_dashboard_dir_missing
#   - test_enrich_features_adds_state_block_per_feature_row
#   - test_enrich_features_preserves_existing_fields  (idempotency on existing data)
#   - test_enrich_features_skips_features_without_matching_currentstate  (graceful gap handling)
#   - test_state_block_shape_matches_spec_AC5  (computed_status + human_status + pr_state +
#     ci_state + review_state + deploy_state + overlays + last_event_ts)
#   - test_projection_is_idempotent  (run twice → identical output bytes)
#   - test_no_network_mode_uses_cached_state_only  (no Signals collection re-run)
#   - test_projection_handles_unknown_safe_signals  (unknown ci_state etc render as "unknown")
# Run pytest — all should FAIL (modules don't exist yet).
pytest tests/unit/work_state/test_projections_dashboard.py -q  # expected FAIL

# Step 3 — Implement scripts/work_state/projections/__init__.py (package marker, 1 line)
#        + scripts/work_state/projections/dashboard.py minimal:
#          - load_state(dashboard_dir: Path) → dict | None  (delegates to state_store.read_current_state)
#          - build_state_block(item: dict) → dict  (extract from CurrentState dict → 8-field state block)
#          - enrich_dashboard(dashboard_json: dict, state_data: dict | None) → dict  (additive merge)
#          - main(argv) CLI entry: --tracker / --output / --no-network / --dashboard-dir flags
# Type hints strict (mypy --strict clean). Pure functions where possible.
# Re-run unit tests; ≥80% should pass after this step.
pytest tests/unit/work_state/test_projections_dashboard.py -q

# Step 4 — Polish unit suite green:
#   - Handle missing current_state.json (return dashboard.json unchanged + warning log line)
#   - Handle features[].id not in state items (skip enrichment, no error)
#   - Handle malformed current_state.json (return None + warning, don't crash)
#   - Idempotency: deterministic JSON serialization (sort_keys=False to preserve order BUT
#     ensure repeat runs produce identical bytes — same input → same output, including
#     features[].state field ordering)
# Run full unit suite: pytest tests/unit/work_state/ -q  → 100% pass.

# Step 5 — Integration test tests/integration/work_state/test_projection_e2e.py:
#   - Spin up tmp_path with fake tracker.md (2-3 real-shape rows)
#   - Run plan_reader + filesystem + git collectors (skip github/ci/railway — use cached
#     fixtures or mock-returns; this test is for projection wiring not collector network)
#   - Persist via state_store.write_current_state to tmp .dashboard/
#   - Build minimal dashboard.json input dict
#   - Invoke projection main() with --no-network --dashboard-dir <tmp>
#   - Assert: output dashboard.json features[*].state block populated with non-None values
#     for ≥1 feature, idempotent on re-run.
pytest tests/integration/work_state/test_projection_e2e.py -q

# Step 6 — Dogfood locally: run engine + projection on REAL tracker, inspect output diff
#   - Run engine driver (existing CLI from Phase 1a/1b — re-use whatever entrypoint exists,
#     OR if no top-level driver yet, run the projection step alone with `--no-network` using
#     the .dashboard/current_state.json that engine has already written during local Phase 1b
#     development. Goal: validate that projection works against real CurrentState shape.)
#   - python -m scripts.work_state.projections.dashboard \
#       --tracker docs/implementation-tracker.md \
#       --output /tmp/dashboard.json.dogfood \
#       --no-network \
#       --dashboard-dir .dashboard
#   - diff /tmp/dashboard.json.dogfood docs/dashboard.json  (expect only `state` field additions
#     OR full features[*].state populated if .dashboard/current_state.json present locally)
#   - Run twice → bit-identical output (idempotency check).
#   - Capture any warnings → log to .autopilot/state/work-state-1b-proj/dogfood-notes.md
```

### ✅ CHECKPOINT A — Phase A Codegen complete (MANDATORY gate)

Halt and run all of these. ALL must pass before Phase B:

```bash
# 1. New module files present
test -f scripts/work_state/projections/__init__.py
test -f scripts/work_state/projections/dashboard.py

# 2. No touch to out-of-scope modules
git diff origin/main --name-only | grep -E '^(scripts/work_state/(models|plan_reader|event_engine|status_machine|progress|state_store)\.py|scripts/work_state/signal_collectors/|scripts/build-dashboard\.py|\.github/workflows/dashboard\.yml|\.importlinter)$' \
  && { echo "FAIL: touched out-of-scope module"; exit 1; } \
  || echo "OK: scope respected"

# 3. All tests pass (190 from 1a+1b + new from 1b')
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 4. mypy strict + lint-imports clean
mypy scripts/work_state/
lint-imports

# 5. Branch ahead by realistic count (≥6 atomic step-commits)
test "$(git rev-list --count origin/main..HEAD)" -ge 6 \
  || { echo "FAIL: too few commits — atomic step commits missing"; exit 1; }

# 6. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "FAIL: dirty working tree"; exit 1; }

# 7. NO docs files deleted (CLAUDE.md hard rule #2)
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs file deleted — circuit breaker"; exit 1; } \
  || echo "OK: no docs deleted"

echo ""
echo "✓✓✓ CHECKPOINT A PASSED — proceeding to Phase B (Codex review)"
echo ""
```

If ANY fails → HALT and report. Do NOT proceed to Codex review.

```bash
# ============================================================
# Phase B — Codex Review (Step 7)
# ============================================================

# Step 7 — Codex review rounds, max 5 (CLAUDE.md hard rule #8 Standard Lane).
#   Round 1: full review of new module + tests. Save artifact to
#     .autopilot/state/work-state-1b-proj/codex/round-1-review.md
#   Apply fixes if P1/P2 findings exist. Commit fixes as separate commits.
#   Round 2: full re-review. Goal: CLEAN (no P1/P2 findings).
#   If Round 2 clean → STOP. Need 2× consecutive clean for P1 per template §3.2.
#   If Round 2 has new findings → fix + run Round 3. Repeat to max 5.
#   If max 5 reached without 2× consecutive clean → HALT, escalate to founder.
```

### ✅ CHECKPOINT B — Phase B Codex Review complete (MANDATORY gate)

```bash
# 1. ≥2 codex round artifacts present
ls -1 .autopilot/state/work-state-1b-proj/codex/round-*-review.md | wc -l  # ≥2

# 2. Last 2 rounds both clean (grep for P1/P2 findings absence)
for n in $(ls -1 .autopilot/state/work-state-1b-proj/codex/round-*-review.md | sort | tail -2); do
  grep -qE '(^|\s)(P0|P1|P2):' "$n" && { echo "FAIL: round $n has open P-finding"; exit 1; }
done

# 3. Tests still green after any fixes
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 4. No new # type: ignore introduced
git diff origin/main -- scripts/work_state/projections/ | grep -E '^\+.*#\s*type:\s*ignore' \
  && { echo "FAIL: # type: ignore introduced — circuit breaker"; exit 1; } \
  || echo "OK: no type ignores"

# 5. Working tree clean
test -z "$(git status --porcelain)" \
  || { echo "FAIL: dirty working tree"; exit 1; }

echo ""
echo "✓✓✓ CHECKPOINT B PASSED — ready to emit READY report"
echo ""
```

```bash
# ============================================================
# READY report (emit to stdout + final commit message in audit trail)
# ============================================================

# Emit final summary block to stdout:
cat <<'EOF'
READY — MYM-4 Phase 1b' projections/dashboard.py complete

Branch:    feat/MYM-4-work-state-engine-1b-projection
Commits:   <count>
Tests:     <unit+integration count> passing
Lint:      ruff clean, black clean, mypy strict clean, lint-imports 5/5
Codex:     <round count> rounds, last 2 clean
Dogfood:   <pass/fail> — see .autopilot/state/work-state-1b-proj/dogfood-notes.md

Next step (founder action — manual squash per P1 manual_only policy):
  1. Review PR diff
  2. Confirm AC1g + AC5 + AC6 + AC10 + AC11a in code
  3. Squash-merge with founder sign-off in PR body confirming acceptance criteria
  4. Update tracker: dashboard projection row 1b' → done (commit SHA)
  5. Update Linear MYM-4 → Done
  6. Phase 1c queued: multi-branch aggregation + persistence + workflow triggers
EOF

# Save FINAL summary to .autopilot/state/work-state-1b-proj/final-summary.md
```

## Circuit breakers (HALT immediately, escalate to founder)

1. **Pre-flight failure** — any prerequisite missing (1a/1b module, Signals field, venv, gh auth, codex/claude binary).
2. **Out-of-scope touch** — any commit modifying a baseline 1a/1b module or build-dashboard.py / workflow / importlinter / dashboard.yml.
3. **Docs deletion** — any `.md` file deleted from working tree (CLAUDE.md hard rule #2).
4. **`# type: ignore` introduced** — strict-mode escape hatch needs founder approval.
5. **Recurring finding** — Codex flags same finding ≥2 rounds after fix attempts (template §3.2 hard rule).
6. **Review cap reached** — 5 Codex rounds without 2× consecutive clean (CLAUDE.md hard rule #8).
7. **Test regression** — any 1a/1b existing test starts failing.
8. **Working tree dirty after step commit** — atomic commit discipline broken.
9. **Branch behind origin/main** — rebase needed; pause for founder.
10. **Network call in projection module** — projection must be pure consumer of cached state (see Anti-patterns).
11. **xfail used to mask broken AC** — only allowed for deferred contracts per memory rule; new ACs cannot be xfailed.
12. **Sandbox vs host git lock conflict** — `.git/index.lock` present → halt and report (memory rule `feedback_sandbox_git_lock_leak`).

## Acceptance criteria (mapped to spec §13)

- [ ] **AC1g** — `scripts/work_state/projections/dashboard.py` exists, mypy strict clean
- [ ] **AC5** — Output `docs/dashboard.json` features[*].state block includes: computed_status, human_status, pr_state, ci_state, review_state, deploy_state, overlays (list), last_event_ts
- [ ] **AC6** — Manual `status` / existing fields (be_code/be_tech/bot_code/spec/etc) UNCHANGED — side-by-side rendering preserved
- [ ] **AC10** — Overlays propagated from CurrentState.overlays into state.overlays per §8.2 canonical enum (no overlay invention)
- [ ] **AC11a** — `human_status` field rendered in state block (9 statuses per §8.0 mapping table)
- [ ] **Idempotency** — running projection twice on same input produces bit-identical output
- [ ] **--no-network** — CLI flag honored: projection uses ONLY cached `.dashboard/current_state.json`, no collector re-run
- [ ] **Unit + integration tests green** — new tests + 190 baseline tests pass
- [ ] **Codex 2× consecutive clean** — P1 review gate per CLAUDE.md hard rule #5

## Deferred / out-of-scope (do NOT implement)

- **AC11b** runtime_urgency — Phase 1d separate ticket. If CurrentState already has the field (from 1a/1b), projection MAY pass through but MUST NOT compute it.
- **AC11c** foundation_change progress milestones — deferred per Phase 1a Q1 resolution (post-shadow ticket).
- **AC11d** multi-branch aggregation — Phase 1c separate ticket.
- **build-dashboard.py wiring** — Phase 1c (workflow phase). Projection is invokable via CLI only; no auto-trigger from existing build pipeline.
- **Phase 2 promotion** — computed → primary status promotion is Phase 2 work, post 7-day shadow window.

## References

- Linear: [MYM-4](https://linear.app/maingocanh/issue/MYM-4)
- Spec: `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.2.1 §10 + §11.1 + §13
- Snapshot: `docs/operations/dashboard-engine/dashboard-architecture-snapshot.md` v1.0.1 §5 + §6
- Predecessor prompts:
  - `docs/autopilot/prompts/work-state-engine-phase-1a-autopilot.md`
  - `docs/autopilot/prompts/work-state-engine-phase-1b-autopilot.md`
- Session handoff: `docs/operations/dashboard-engine/session-handoff-2026-05-20.md`
- CLAUDE.md hard rules: #1 (1-session), #2 (no docs delete), #3 (spec-first), #5 (different-model review), #6 (manual_only), #7 (single-phase OK), #8 (review cap 5)
- Template: `docs/autopilot/autopilot-prompt-template.md`
- Memory rules:
  - `feedback_claude_p_text_mode_buffering.md` — monitor via git log poll, not tee tail
  - `feedback_sandbox_git_lock_leak.md` — sandbox git writes leave stale locks
  - `feedback_megaprompt_with_checkpoints_works.md` — checkpoints + halt-if-skipped enforce phase boundaries
  - `feedback_pin_deferred_contracts.md` — xfail only for explicitly deferred contracts
  - `feedback_never_auto_delete_docs.md` — never delete `.md` files

## How to use this prompt (founder)

```bash
# 1. Commit this prompt + any tracker row update to main first
#    (bootstrap step per memory feedback_autopilot_bootstrap_step)
cd /Users/maingocanh/Projects/MyMoneyWent
git checkout main
git add docs/autopilot/prompts/work-state-engine-1b-projection-autopilot.md
# (optionally) git add docs/implementation-tracker.md  — if you want a tracker row stage update
git commit -m "docs(work-state-engine): add Phase 1b' projection autopilot prompt + tracker row"
git push origin main

# 2. Create worktree
cd /Users/maingocanh/Projects/MyMoneyWent
git worktree add ../MyMoneyWent-engine-1b-proj -b feat/MYM-4-work-state-engine-1b-projection main
cd ../MyMoneyWent-engine-1b-proj
ln -s /Users/maingocanh/Projects/MyMoneyWent/.venv .venv
source .venv/bin/activate
mkdir -p .autopilot/state/work-state-1b-proj/codex

# 3. Fire
claude -p "$(cat docs/autopilot/prompts/work-state-engine-1b-projection-autopilot.md)" \
  2>&1 | tee .autopilot/state/work-state-1b-proj/run-$(date +%s).log

# 4. Monitor via git log poll (claude -p text mode buffers stdout):
watch -n 30 'git -C /Users/maingocanh/Projects/MyMoneyWent-engine-1b-proj log --oneline -10'

# 5. After READY emitted:
#    - Review PR diff manually
#    - Squash-merge to main with founder sign-off in PR body
#    - Update Linear MYM-4 → Done
#    - Phase 1c is next
```

## Estimated effort

- **Codegen (Steps 1-6):** ~30-50 min claude wallclock
- **Codex review (Step 7):** ~10-20 min (2-3 rounds expected for additive single-module work)
- **Founder squash + Linear close:** ~5 min
- **Total wallclock to READY:** ~45-70 min

Compare to:
- MYM-1 Phase 1a: ~2 hours wallclock (10 modules, 127 tests, 6 codex findings)
- MYM-3 Phase 1b: ~2-3 hours wallclock (3 collectors + Signals extension, 63 new tests, 4 codex rounds)
- MYM-4 Phase 1b': **Smaller** — 1 module, ~6-10 unit + 1-2 integration tests, pure read-only consumer.
