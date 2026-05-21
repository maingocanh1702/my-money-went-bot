# Autopilot Prompt — MYM-8 Doc-change hash-aware dedup + emission wire

> **Status:** READY 2026-05-21 (post MYM-10 squash merge) · single-phase Scope B (dedup + emission).
> **Plan source:** `docs/operations/dashboard-engine/dashboard-plan-state-split.md` v1.3.0 §7.2.1 (dedup table gap) + §7.1 line 432 (emit-on-hash-change promise).
> **Linear ticket:** [MYM-8](https://linear.app/maingocanh/issue/MYM-8) — Hash-aware doc-change event dedup.
> **Predecessors:** MYM-1+3+4+5+6+7+10 all merged on main.
> **Scope decision:** Founder picked Scope B 2026-05-21 (project-benefit max, 5/6 axis win).

---

## Scope reminder

| Concern | In-scope? | Notes |
|---|---|---|
| Event model `+content_hash` field (APPEND-ONLY) | ✅ | End of dataclass |
| `_dedup_key()` hash-aware for `_DOC_CHANGE_EVENTS` | ✅ | Include `event.content_hash or ""` |
| `is_duplicate()` matching: read content_hash from tail | ✅ | Existing entry tuple gains 4th element |
| Spec §7.2.1 dedup table: add doc-change row | ✅ | + version bump v1.3.0 → v1.4.0 |
| `engine.py` emission wire (3 event types when hash changes vs prev) | ✅ | Skip emit if prev_hash is None (bootstrap noise prevention) |
| Unit tests `test_event_engine.py` extended | ✅ | Hash-aware dedup behavior |
| Integration test `test_doc_change_e2e.py` extended | ✅ | Engine 2-run emission proof |
| **`last_event_ts` populating** | ❌ | Out of scope — preserve None to avoid shadow noise |
| **Phase C event feed UI** | ❌ | SPA-blocked |
| Phase D client polling upgrade | ❌ | Separate ticket |
| `state-cache.json` migration | ❌ | Not needed |

---

```
Task: MYM-8 doc-change hash-aware dedup + emission wire (Event APPEND-ONLY +content_hash + dedup logic + engine.py emission + spec v1.4.0)
You are working in /Users/maingocanh/Projects/MyMoneyWent-MYM-8 on MyMoneyWent
(multi-tenant personal finance bot, dual-market VN+Global). NO prior conversation context.
This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/MYM-8-doc-change-hash-dedup`,
manual_only merge policy, STOP_AT_READY (founder does manual squash). Pause ONLY on
circuit-breaker conditions (§Circuit breakers).

Risk tier:          P2 Standard Lane (additive logic + Event APPEND-ONLY)
Merge policy:       manual_only (CLAUDE.md hard rule #6)
Autopilot maturity: post-MYM-10 (8th engine-related autopilot run)
Codex review:       2× consecutive clean required (P2 Standard)
Review cap:         5 rounds max (per CLAUDE.md hard rule #8)
Branch regex:       lowercase only (MYM-9 fix landed b382048)

Prerequisite: main contains MYM-1 + MYM-3 + MYM-4 + MYM-5 + MYM-6 + MYM-7 + MYM-10 squash (PR #32).

Scope of this prompt — Scope B (dedup logic + emission wire):
  MODIFY:
    scripts/work_state/models.py                          # Event APPEND-ONLY +content_hash
    scripts/work_state/event_engine.py                    # _dedup_key + is_duplicate hash-aware for _DOC_CHANGE_EVENTS
    scripts/work_state/engine.py                          # emit doc-change events when hash changes vs prev (skip first run)
    docs/operations/dashboard-engine/dashboard-plan-state-split.md  # v1.3.0 → v1.4.0 (§7.2.1 dedup table row)
    tests/unit/work_state/test_event_engine.py            # extend with hash-aware dedup tests
    tests/integration/work_state/test_doc_change_e2e.py   # extend with engine 2-run emission proof

Do NOT touch:
  - Signals dataclass field signatures (APPEND-ONLY discipline — only Event gets +1 field this PR)
  - status_machine.py (overlay computation unchanged)
  - signal_collectors/*.py (hash signal collection unchanged)
  - projections/dashboard.py (read-only consumer)
  - build-dashboard.py (no rendering change)
  - state_store.py (no CurrentState shape change — last_event_ts stays None this PR)
  - .github/workflows/* (no CI change)
  - .importlinter (no boundary change)
  - docs/dashboard.{html,md,json} (auto-generated)
  - Any other .md file beyond the spec (NEVER delete per CLAUDE.md hard rule #2)

Out-of-scope-but-documented:
  - last_event_ts population — preserve None to keep dashboard.html bytes-identical → shadow window safety (~2026-05-27 expires)
  - Phase C event feed UI → SPA decision blocked
  - Phase D client polling upgrade → separate ticket
  - state-cache.json migration → not needed
  - Cross-event dedup beyond doc-change → separate ticket if demanded
  - Phase 2 promotion (computed → primary) → post-shadow gated

Required reading (READ FIRST, in this order, before any code):

1. docs/operations/dashboard-engine/dashboard-plan-state-split.md v1.3.0 — focus:
   - §7.1 line 432 ("Hash change between engine runs → emit `spec_modified` / `tech_modified` event")
   - §7.1 line 587-589 (filesystem → spec_modified/tech_modified/tracker_row_modified → overlay table)
   - §7.2.1 dedup table (lines 597-607) — **GAP**: doc-change events not listed
   - §7.3 `.dashboard/events.jsonl` runtime location
   - §8.2 canonical overlay enum 21 entries (DO NOT modify — last touched MYM-10)
   - §11.2 Event dataclass model sketch

2. CLAUDE.md — focus hard rules: #1, #2, #3 (spec patch), #5, #6, #7, #8

3. Phase 1a–1d engine modules (READ-ONLY baseline):
   - scripts/work_state/models.py — Event dataclass current (lines 84-94, extend APPEND-ONLY)
   - scripts/work_state/event_engine.py — full file (~130 LOC, dedup logic to extend)
   - scripts/work_state/engine.py — `run_engine` function, focus `_load_prev_hashes` + `compute_overlays` invocation (lines 127-155 + 192-229)
   - scripts/work_state/status_machine.py — `compute_overlays` precedent for hash diff pattern (lines 57-95)
   - tests/unit/work_state/test_event_engine.py — current dedup test patterns to extend
   - tests/integration/work_state/test_doc_change_e2e.py — current emission test patterns to extend

4. Memories (auto-loaded — verify if any apply):
   - feedback_autopilot_preflight_must_include_tests_mypy.md — full mypy scope
   - feedback_activate_venv_before_commit.md — venv before git commit (3 prior incidents)
   - feedback_codex_p1_representative_branch.md — multi-branch picking pattern
   - project_work_state_engine_progress.md — engine end-to-end state

Pre-flight gate (HARD — halt if any fails):

```bash
cd /Users/maingocanh/Projects/MyMoneyWent-MYM-8
git status                              # MUST be clean
git branch --show-current               # MUST be: feat/MYM-8-doc-change-hash-dedup
git fetch origin
git log --oneline origin/main..HEAD -5
git merge-base --is-ancestor origin/main HEAD || { echo "FAIL: feat behind origin/main"; exit 1; }

# All Phase 1a–1d + MYM-7 modules importable
python -c "from scripts.work_state.engine import run_engine; print('OK: engine')"
python -c "from scripts.work_state.event_engine import append_event, is_duplicate, read_tail_events; print('OK: event_engine')"
python -c "from scripts.work_state.models import Event, Signals, CurrentState; print('OK: models')"
python -c "from scripts.work_state.status_machine import compute_overlays; print('OK: status_machine')"

# Spec at v1.3.0 baseline (MYM-7 set this)
grep -q "^version: v1.3.0" docs/operations/dashboard-engine/dashboard-plan-state-split.md \
  || { echo "FAIL: spec not at v1.3.0 baseline"; exit 1; }

# .dashboard/ gitignored
grep -q "^\.dashboard/$" .gitignore     || { echo "FAIL: .dashboard/ not in .gitignore"; exit 1; }

# venv MUST be active (memory feedback_activate_venv_before_commit)
source .venv/bin/activate
which python && which lint-imports && which codex && which claude && which gh

# FULL mypy strict scope (memory feedback_autopilot_preflight_must_include_tests_mypy)
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports                            # 5 contracts pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short   # baseline 328+ tests pass

# Codex artifact dir present
mkdir -p .autopilot/state/MYM-8/codex

# ===== PRE-FLIGHT CHECKPOINT =====
echo ""
echo "✓✓✓ PRE-FLIGHT PASSED — proceeding to MYM-8 codegen"
echo ""
```

Anti-patterns (NEVER do):

* `git push --force`
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed)
* Auto-merge ngoài STOP_AT_READY (P2 manual_only per CLAUDE.md #6)
* MODIFY existing Event field signatures (APPEND-ONLY — content_hash is +1 at end)
* MODIFY existing Signals field signatures (untouched in this PR)
* Populate `last_event_ts` on CurrentState (out-of-scope; shadow window safety)
* Touch out-of-scope modules (status_machine, collectors, projections, build-dashboard, state_store, workflows)
* Change `CANONICAL_OVERLAYS` set (21 entries locked by MYM-10)
* Wire emission to write last_event_ts (shadow noise)
* Emit doc-change events on FIRST engine run (prev_hash is None → skip — bootstrap noise)
* Skip spec v1.4.0 bump (§7.2.1 row addition requires version bump per memory feedback_spec_versioning ≠ in-session iteration)
* Bump spec to v2.0.0 (additive change is MINOR bump v1.3.0 → v1.4.0)
* Skip TDD gate
* `xfail` to mask broken AC
* Loop ≥5 Codex rounds without founder check-in (CLAUDE.md #8 review cap)
* Forget to activate venv before `git commit` (memory feedback_activate_venv_before_commit, 3 prior incidents)

Numbered steps:

```bash
# ============================================================
# MYM-8 codegen (Steps 1-6)
# ============================================================

# Step 1 — Confirm branch + state dir
git status
git branch --show-current
test -d .autopilot/state/MYM-8/codex \
  || { echo "FAIL: codex artifact dir missing"; exit 1; }

# Step 2 — Bump spec v1.3.0 → v1.4.0 (§7.2.1 doc-change dedup row + Event +content_hash)
# Edit docs/operations/dashboard-engine/dashboard-plan-state-split.md:
#   - Frontmatter: version v1.3.0 → v1.4.0, updated 2026-05-21
#   - §7.2.1 dedup table (lines 597-607): INSERT row after `spec_created/tech_created` row:
#       | `spec_modified` / `tech_modified` / `tracker_row_modified` | `(item, event, artifact, content_hash)` | Re-emit khi content_hash khác — same hash treated duplicate |
#   - §11.2 Event dataclass model sketch: append `content_hash: str | None = None`
#   - Add note under §7.2.1 explaining: "doc-change events carry the new content_hash; dedup matches against prior tail entries with identical hash — different hash = legitimate drift, re-emit."
#   - Changelog: add v1.4.0 entry documenting additive §7.2.1 row + Event APPEND-ONLY +content_hash
# Commit: "docs(spec): bump v1.4.0 — §7.2.1 doc-change dedup row + Event +content_hash (MYM-8)"

# Step 3 — TDD: extend failing tests FIRST
# tests/unit/work_state/test_event_engine.py — ADD test class TestDocChangeHashDedup:
#   - test_spec_modified_same_hash_dedupes  (emit event A hash=X, emit event B hash=X same item+artifact → is_duplicate=True)
#   - test_spec_modified_different_hash_reemits  (emit event A hash=X, emit event B hash=Y → is_duplicate=False)
#   - test_tech_modified_hash_aware_dedup  (same pattern for tech)
#   - test_tracker_row_modified_hash_aware_dedup
#   - test_doc_change_dedup_key_includes_content_hash  (unit-level: _dedup_key returns 4-tuple incl content_hash)
#   - test_doc_change_event_missing_content_hash_treated_as_empty_string  (backward compat for legacy tail entries)
#
# tests/integration/work_state/test_doc_change_e2e.py — ADD test class TestEngineEmitsDocChangeOnHashDrift:
#   - test_engine_first_run_no_emission  (no prev → no doc-change events emitted; engine output state still correct)
#   - test_engine_second_run_emits_spec_modified_on_hash_change  (run 1 establishes prev, run 2 with new hash emits 1 event)
#   - test_engine_second_run_no_emission_when_hash_unchanged
#   - test_engine_emits_all_three_event_types_for_combined_drift  (spec+tech+tracker all change → 3 events)
#   - test_engine_emission_idempotent_third_run_same_hash  (run 3 with same hash as run 2 → 0 new events; existing dedup'd)
#   - test_engine_does_not_populate_last_event_ts  (CurrentState.last_event_ts is None despite events.jsonl populated)
pytest tests/unit/work_state/test_event_engine.py::TestDocChangeHashDedup \
       tests/integration/work_state/test_doc_change_e2e.py::TestEngineEmitsDocChangeOnHashDrift \
       -q  # expect FAIL

# Step 4 — Extend Event dataclass (APPEND-ONLY +content_hash)
# scripts/work_state/models.py — Event class (lines 84-94):
#   Append at end (after `overlay: str | None = None`):
#     content_hash: str | None = None  # Phase B/MYM-8 APPEND-ONLY — hash of artifact content at emission time
# Run baseline model tests to verify APPEND-ONLY safe.
pytest tests/unit/work_state/test_models.py -q

# Step 5 — Implement event_engine.py hash-aware dedup
# scripts/work_state/event_engine.py:
#   - _dedup_key() for event.event in _DOC_CHANGE_EVENTS:
#       return (event.item, event.event, event.artifact or "", event.content_hash or "")
#   - is_duplicate() doc-change branch: read content_hash from tail entry:
#       existing_content_hash = str(entry.get("content_hash", ""))
#       existing_key = (existing_item, existing_event_type, existing_artifact, existing_content_hash)
#   - Backward-compat: tail entries lacking content_hash field treated as "" — older logs match new emissions with content_hash="" (legacy no-hash dedup) but new emissions with content_hash != "" never match legacy "" entries → legitimate re-emit
# Run unit tests; should now pass.
pytest tests/unit/work_state/test_event_engine.py -q

# Step 6 — Wire emission in engine.py (run_engine)
# scripts/work_state/engine.py:
#   - After `prev_hashes = _load_prev_hashes(dashboard_dir)` block (line 170):
#     Define events_file = dashboard_dir / "events.jsonl"
#   - After single-branch `compute_overlays` invocation (line 192-199), AND after multi-branch `compute_overlays` invocation (line 223-229):
#     For each hash field (spec, tech, tracker_row):
#       if (prev_X_h is not None and signals.X_hash is not None and signals.X_hash != prev_X_h):
#         event = Event(
#             ts=<iso utcnow>,
#             item=item.id,
#             event="spec_modified" | "tech_modified" | "tracker_row_modified",
#             from_status=None,
#             to_status=None,
#             source="filesystem.spec" | "filesystem.tech" | "filesystem.tracker",
#             artifact=<spec_path or tech_path or tracker_path>,
#             content_hash=signals.X_hash,
#         )
#         if not is_duplicate(event, events_file):
#             append_event(event, events_file)
#   - DO NOT populate state.last_event_ts (stays None per scope)
#   - Single-branch + multi-branch use SAME emission helper (extract `_emit_doc_change_events` private fn to avoid duplication)
# Run integration tests.
pytest tests/integration/work_state/test_doc_change_e2e.py -q
```

```bash
# Step 7 — Dogfood + verify side-by-side
mkdir -p /tmp/mym-8-dogfood
rm -rf /tmp/mym-8-dogfood/.dashboard
mkdir -p /tmp/mym-8-dogfood/.dashboard

# Run 1: bootstrap (no prev_hashes → no doc-change events)
python -m scripts.work_state.engine \
  --tracker docs/implementation-tracker.md \
  --dashboard-dir /tmp/mym-8-dogfood/.dashboard \
  --no-network \
  2>&1 | tee .autopilot/state/MYM-8/dogfood-run-1.log

# Run 2: replay (prev_hashes loaded; same hash → 0 events)
python -m scripts.work_state.engine \
  --tracker docs/implementation-tracker.md \
  --dashboard-dir /tmp/mym-8-dogfood/.dashboard \
  --no-network \
  2>&1 | tee .autopilot/state/MYM-8/dogfood-run-2.log

# Verify events.jsonl empty (both runs) — no false-positive emissions
test ! -s /tmp/mym-8-dogfood/.dashboard/events.jsonl \
  && echo "OK: no false-positive emission on idempotent re-run" \
  || cat /tmp/mym-8-dogfood/.dashboard/events.jsonl

# Run 3: simulate spec drift by touching a tracked spec file via timestamp + small inline change
# (Use a sentinel file that won't break the codebase — e.g., create tmp spec then point tracker to it… 
#  ACTUALLY: simpler — modify state-cache content for one item then re-run engine. See test_doc_change_e2e.py for fixture pattern.)
# Document this manual drift exercise in dogfood-notes.md.

cat > .autopilot/state/MYM-8/dogfood-notes.md <<EOF
# MYM-8 Dogfood Run
- Date: $(date -Iseconds)
- Tracker: docs/implementation-tracker.md
- Run 1 (bootstrap): events.jsonl size = $(stat -f%z /tmp/mym-8-dogfood/.dashboard/events.jsonl 2>/dev/null || echo 0)
- Run 2 (idempotent replay): events.jsonl size = same as Run 1 (0 emission expected)
- Simulated drift: TBD (manual exercise documented in test_doc_change_e2e.py)
- Conclusion: emission gates correctly on (prev_hash is not None AND hash changed)
EOF
```

### ✅ CHECKPOINT A — MYM-8 Codegen complete

```bash
# 1. New + modified files present
git diff --name-only origin/main | grep -E '^(scripts/work_state/models\.py|scripts/work_state/event_engine\.py|scripts/work_state/engine\.py|docs/operations/dashboard-engine/dashboard-plan-state-split\.md|tests/unit/work_state/test_event_engine\.py|tests/integration/work_state/test_doc_change_e2e\.py)$' \
  || { echo "FAIL: expected file changes missing"; exit 1; }

# 2. NO out-of-scope touch
git diff --name-only origin/main | grep -E '^(scripts/work_state/(signal_collectors|projections|status_machine|state_store|plan_reader|progress)|scripts/build-dashboard\.py|\.github/workflows/|\.importlinter|docs/dashboard\.)' \
  && { echo "FAIL: touched out-of-scope module"; exit 1; } \
  || echo "OK: scope respected"

# 3. Event APPEND-ONLY verified (only field additions, no signature changes)
git diff origin/main scripts/work_state/models.py | grep -E '^-\s+(ts|item|event|from_status|to_status|source|artifact|pr_number|overlay):' \
  && { echo "FAIL: Event field removed/modified (must be APPEND-ONLY)"; exit 1; } \
  || echo "OK: Event APPEND-ONLY safe"

# 4. CANONICAL_OVERLAYS untouched (MYM-10 lock)
git diff origin/main scripts/work_state/status_machine.py \
  && { echo "FAIL: status_machine.py touched (out of scope)"; exit 1; } \
  || echo "OK: CANONICAL_OVERLAYS untouched"

# 5. last_event_ts NOT populated (shadow safety)
git diff origin/main scripts/work_state/engine.py | grep -E '^\+.*last_event_ts\s*=\s*[^N]' \
  && { echo "FAIL: last_event_ts populated (shadow noise)"; exit 1; } \
  || echo "OK: last_event_ts preserved as None"

# 6. All tests pass
pytest tests/unit/work_state/ tests/integration/work_state/ -q --tb=short

# 7. mypy + lint clean FULL SCOPE
mypy core markets i18n tests scripts/work_state
ruff check .
black --check .
lint-imports

# 8. Branch ahead by ≥5 atomic step-commits (1 per Step)
test "$(git rev-list --count origin/main..HEAD)" -ge 5

# 9. Working tree clean
test -z "$(git status --porcelain)"

# 10. NO docs deleted
git diff origin/main --diff-filter=D --name-only | grep '\.md$' \
  && { echo "FAIL: docs deleted"; exit 1; } \
  || echo "OK"

# 11. Dogfood artifact present
test -f .autopilot/state/MYM-8/dogfood-notes.md

# 12. Spec v1.4.0 frontmatter
grep -q "^version: v1.4.0" docs/operations/dashboard-engine/dashboard-plan-state-split.md \
  || { echo "FAIL: spec not bumped to v1.4.0"; exit 1; }

# 13. NO scope creep keywords
git diff origin/main scripts/ 2>&1 | grep -E '(last_event_ts\s*=\s*event\.ts|spa\b|client.*poll|new overlay|CANONICAL_OVERLAYS.add)' \
  && { echo "FAIL: out-of-scope feature detected"; exit 1; } \
  || echo "OK"

echo ""
echo "✓✓✓ CHECKPOINT A PASSED — proceeding to MYM-8 Codex review"
echo ""
```

```bash
# ============================================================
# Step 8 — Codex Review rounds (Standard Lane: max 5 rounds per CLAUDE.md #8)
# ============================================================

# Round 1: full review including spec v1.4.0 §7.2.1 + Event APPEND-ONLY + dedup logic + engine emission
# Save artifact: .autopilot/state/MYM-8/codex/round-1-review.md
# Apply fixes if P0/P1/P2 findings.

# Round 2: full re-review. Goal: CLEAN. 
# If R2 clean → STOP. Need 2× consecutive clean.
# Repeat to max 5 (HARD cap — CLAUDE.md hard rule #8). 
# Beyond 5 → halt, escalate to founder (split / manual review / revisit foundation).

# Use TTY pattern (memory feedback_codex_cli_can_apply_fixes):
#   script -q .autopilot/state/MYM-8/codex/round-N.log codex "<prompt>"
# NOT: codex "..." | tee log (codex needs TTY)
```

### ✅ CHECKPOINT B — Codex Review complete

```bash
# 1. ≥2 codex round artifacts
ls -1 .autopilot/state/MYM-8/codex/round-*-review.md | wc -l

# 2. Last 2 rounds both clean
for n in $(ls -1 .autopilot/state/MYM-8/codex/round-*-review.md | sort | tail -2); do
  grep -qE '(^|\s)(P0|P1|P2):' "$n" && { echo "FAIL: round $n has open P-finding"; exit 1; }
done

# 3. Round count within cap
test "$(ls -1 .autopilot/state/MYM-8/codex/round-*-review.md | wc -l)" -le 5

# 4. Tests + lint green
pytest tests/unit/work_state/ tests/integration/work_state/ -q
mypy core markets i18n tests scripts/work_state
lint-imports

# 5. No new # type: ignore
git diff origin/main | grep -E '^\+.*#\s*type:\s*ignore' && exit 1

# 6. Working tree clean
test -z "$(git status --porcelain)"

echo "✓✓✓ CHECKPOINT B PASSED — emit READY"
```

```bash
# ============================================================
# READY report
# ============================================================
cat <<'EOF'
READY — MYM-8 doc-change hash-aware dedup + emission wire complete

Branch:    feat/MYM-8-doc-change-hash-dedup
Commits:   <count>
Tests:     <unit+integration count> passing (328+ baseline + N new)
Lint:      ruff/black/mypy strict full-scope/lint-imports 5/5 clean
Codex:     <round count> rounds, last 2 clean
Dogfood:   <pass/fail> — see .autopilot/state/MYM-8/dogfood-notes.md

MYM-8 deliverables:
  - Event APPEND-ONLY +content_hash field (models.py)
  - _dedup_key + is_duplicate hash-aware for _DOC_CHANGE_EVENTS (event_engine.py)
  - Engine emits spec_modified/tech_modified/tracker_row_modified when hash changes vs prev (engine.py)
  - First-run bootstrap noise prevention (prev_hash is None → skip emit)
  - Idempotent re-runs (same hash → dedup'd by is_duplicate)
  - Spec v1.4.0 §7.2.1 doc-change dedup row + Event model sketch update + changelog
  - Shadow window safety: last_event_ts preserved None → dashboard.html bytes-identical

Out-of-scope confirmed deferred:
  - last_event_ts population → post-shadow ticket
  - Phase C event feed UI → SPA decision blocked
  - Phase D client polling upgrade → separate ticket
  - state-cache.json migration → not needed
  - Phase 2 promotion (computed → primary) → 7-day shadow gate

Next step (founder action — manual squash per P2 Standard manual_only):
  1. Review PR diff (focus: Event APPEND-ONLY + dedup key tuple shape + engine emission guard)
  2. Verify .dashboard/events.jsonl behavior in 2-run dogfood logs
  3. Confirm CurrentState.last_event_ts still None in dashboard output (shadow safety)
  4. gh pr create + squash-merge với founder sign-off
  5. Linear MYM-8 → Done
  6. Continue with 7-day shadow validation (~2026-05-27 expires) or pick MYM-11 next
EOF
```

## Circuit breakers (HALT immediately, escalate to founder)

1. **Pre-flight failure** — any baseline module missing or spec not at v1.3.0
2. **Out-of-scope touch** — status_machine, collectors, projections, build-dashboard, state_store, workflows
3. **Event NOT APPEND-ONLY** — existing field signatures modified/removed
4. **Signals touched** — out of scope this PR (only Event gains +1 field)
5. **CANONICAL_OVERLAYS modified** — MYM-10 locked 21 entries
6. **last_event_ts populated** — shadow window safety violation
7. **First-run emission** — `prev_hash is None` should skip emit (bootstrap noise)
8. **Spec NOT bumped** — v1.3.0 unchanged (§7.2.1 row addition requires v1.4.0)
9. **Spec bumped to v2.0.0** — additive change is MINOR not MAJOR
10. **Docs deletion** — any `.md` deleted (CLAUDE.md hard rule #2)
11. **`# type: ignore` introduced** — founder approval needed
12. **Codex review cap exceeded** — >5 rounds without founder check-in (CLAUDE.md #8)
13. **`# type: ignore` to suppress mypy** — founder approval
14. **`xfail` strict=False added** — mask broken AC
15. **venv NOT active before git commit** — memory feedback_activate_venv_before_commit (3 prior incidents)

When any circuit breaker trips → emit `HALT: <reason>` to .autopilot/state/MYM-8/halt.md → exit 6.
```

---

## Bootstrap commands (paste-prompt pattern, NOT `tools/autopilot` CLI)

> **Note:** Engine work (MYM-1/3/4/5/6/7/10) uses paste-prompt pattern — paste body vào claude-code session trực tiếp. KHÔNG dùng `python -m tools.autopilot run` (orchestrator require `docs/features/feature-MYM-8.md` FE+BE spec, engine không có).

```bash
# 0. Commit prompt vào main TRƯỚC (chore commit riêng)
cd /Users/maingocanh/Projects/MyMoneyWent
source .venv/bin/activate
git fetch origin && git pull origin main
git log --oneline -3   # capture MYM-10 squash SHA
cp "/Users/maingocanh/Library/Application Support/Claude/local-agent-mode-sessions/<UUID>/local_<UUID>/outputs/MYM-8-doc-change-hash-dedup-autopilot.md" \
   docs/autopilot/prompts/MYM-8-doc-change-hash-dedup-autopilot.md
git add docs/autopilot/prompts/MYM-8-doc-change-hash-dedup-autopilot.md
git commit -m "docs(autopilot): MYM-8 prompt — Scope B (dedup + emission)

Ref MYM-8"
git push origin main

# 1. Create worktree (per CLAUDE.md hard rule #1)
git worktree add ../MyMoneyWent-MYM-8 -b feat/MYM-8-doc-change-hash-dedup origin/main

# 2. Setup venv in worktree (symlink main's venv — same Python interpreter)
cd ../MyMoneyWent-MYM-8
ln -s /Users/maingocanh/Projects/MyMoneyWent/.venv .venv
source .venv/bin/activate
which lint-imports && which codex && which claude   # verify all available

# 3. Verify branch + clean
git status                   # clean
git branch --show-current    # feat/MYM-8-doc-change-hash-dedup
git log --oneline origin/main..HEAD -5   # should be empty (branch = main)

# 4. Launch claude-code session in worktree + paste prompt body
claude
# Paste body của docs/autopilot/prompts/MYM-8-doc-change-hash-dedup-autopilot.md
# From "Task: MYM-8 doc-change hash-aware dedup..." through "...exit 6.")
# Claude executes Steps 1-7 + Checkpoint A + Codex Steps + Checkpoint B
# Emits READY artifact at .autopilot/state/MYM-8/READY.md

# Post-READY (anh):
# - Review diff: `git diff origin/main`
# - Verify dogfood: `cat .autopilot/state/MYM-8/dogfood-notes.md`
# - gh pr create + manual squash-merge với founder sign-off body
# - Linear MYM-8 → Done
# - cd /Users/maingocanh/Projects/MyMoneyWent && git worktree remove ../MyMoneyWent-MYM-8
```
