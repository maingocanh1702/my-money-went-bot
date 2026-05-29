# Walk-Away Mega-Prompt — Feature Progress Aggregation

You are an autopilot coding agent in `/Users/maingocanh/Projects/MyMoneyWent`. Add per-feature progress aggregation + visual bars to the dashboard Features tab. Single session, end-to-end.

## Mode + Risk

- Mode: AUTOPILOT FULL-AUTO — single feature branch, auto-squash + push at end
- Risk tier: P2 mature (dashboard build script class)
- Codex review: 1× clean

## Mandatory Checklist

After each phase, emit exact line:
```
✅ PHASE <N> COMPLETE — moving to PHASE <N+1>.
```

```
[ ] PHASE 0 — Bootstrap: verify clean tree
[ ] PHASE 1 — Feature progress: compute + render bars + summary header
```

---

## Global Pre-Flight

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null && echo "FAIL: stale locks" && exit 1
git status   # MUST clean
git branch --show-current   # MUST: main
git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
which python git ruff black pytest
test -f docs/dashboard.json
python -c "import json; d=json.load(open('docs/dashboard.json')); assert d.get('features'), 'no features in dashboard.json'"
BASELINE_PASS=$(pytest tests/ -q 2>&1 | tail -1)
echo "Baseline: $BASELINE_PASS"
```

Any fail → HALT.

---

# PHASE 0 — Bootstrap

```bash
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
[ "$DIRTY" -gt 0 ] && { echo "HALT: working tree not clean"; git status --short; exit 1; }
echo "✅ PHASE 0 COMPLETE — clean tree verified. Moving to PHASE 1."
```

---

# PHASE 1 — Feature Progress Aggregation + Render

## 1.1 Branch
```bash
git checkout -b feat/dashboard-feature-progress
mkdir -p .autopilot/state/feature-progress
```

## 1.2 Required reading (before code)
1. `scripts/build-dashboard.py` — locate Features tab render function (from B-2). Find existing `render_features_tab` or equivalent that builds the feature table.
2. `scripts/dashboard/parse_roadmap.py` (or wherever §2 parser lives from B-1) — confirm features list shape: each feature dict has keys `spec`, `be_tech`, `be_code`, `bot_code` with values `done`/`partial`/`not_started`/`deferred`.
3. `docs/dashboard.json` features array — verify shape matches expectations.

## 1.3 TDD — failing tests
Create or extend `tests/scripts/test_dashboard_polish.py` (or `test_dashboard_render.py` — pick whichever houses Features tab tests):

```python
import pytest

# Import the new functions (will fail until 1.4 implemented)
from scripts.build_dashboard import compute_feature_progress, compute_features_summary
# OR if split: from scripts.dashboard.render import ...

def test_feature_progress_all_done():
    f = {"spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done"}
    assert compute_feature_progress(f) == 100

def test_feature_progress_all_not_started():
    f = {"spec": "not_started", "be_tech": "not_started", "be_code": "not_started", "bot_code": "not_started"}
    assert compute_feature_progress(f) == 0

def test_feature_progress_mixed_F01_like():
    # F01: spec=done, be_tech=done, be_code=partial, bot_code=not_started → (1+1+0.5+0)/4 = 0.625 → 63%
    f = {"spec": "done", "be_tech": "done", "be_code": "partial", "bot_code": "not_started"}
    assert compute_feature_progress(f) == 63

def test_feature_progress_missing_axes_treated_as_not_started():
    f = {"spec": "done"}  # other axes missing
    assert compute_feature_progress(f) == 25

def test_feature_progress_deferred_counts_as_zero():
    f = {"spec": "deferred", "be_tech": "done", "be_code": "not_started", "bot_code": "not_started"}
    # deferred=0, done=1, rest=0 → 25%
    assert compute_feature_progress(f) == 25

def test_features_summary_empty():
    s = compute_features_summary([])
    assert s == {"overall": 0, "spec": 0, "be_tech": 0, "be_code": 0, "bot_code": 0, "count": 0}

def test_features_summary_aggregates_per_axis():
    fs = [
        {"spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done"},  # 100
        {"spec": "done", "be_tech": "done", "be_code": "partial", "bot_code": "not_started"},  # 63
        {"spec": "not_started", "be_tech": "not_started", "be_code": "not_started", "bot_code": "not_started"},  # 0
    ]
    s = compute_features_summary(fs)
    assert s["count"] == 3
    # Spec: (1+1+0)/3 = 67%
    assert s["spec"] == 67
    # BE Tech: (1+1+0)/3 = 67%
    assert s["be_tech"] == 67
    # BE Code: (1+0.5+0)/3 = 50%
    assert s["be_code"] == 50
    # Bot Code: (1+0+0)/3 = 33%
    assert s["bot_code"] == 33
    # Overall: avg of feature-level percentages = (100+63+0)/3 = 54%
    assert s["overall"] == 54

def test_render_features_tab_includes_progress_column():
    # Smoke: rendered HTML contains progress bar markup for each feature
    from scripts.build_dashboard import render_features_tab  # or wherever it lives
    html = render_features_tab(
        features=[{"id": "F01", "name": "Test", "spec": "done", "be_tech": "done",
                   "be_code": "partial", "bot_code": "not_started", "phase": [1]}]
    )
    assert 'class="progress-bar"' in html or 'progress-fill' in html
    assert '63%' in html or '63' in html  # progress value rendered

def test_render_features_tab_summary_header():
    from scripts.build_dashboard import render_features_tab
    html = render_features_tab(features=[
        {"id": "F01", "name": "A", "spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done", "phase": [1]},
    ])
    # Summary should show 100% overall
    assert "100%" in html
```

Adjust import paths to actual module location. Run tests — MUST FAIL (functions don't exist yet):
```bash
pytest tests/scripts/test_dashboard_*.py -v -k "feature_progress or features_summary or features_tab_includes" 2>&1 | tail -20
```
Any pass → TDD oracle violated → HALT.

## 1.4 Implement
In `scripts/build-dashboard.py` (or `scripts/dashboard/render.py` if package split exists):

```python
def compute_feature_progress(feature: dict) -> int:
    """Aggregate spec/be_tech/be_code/bot_code into 0-100% progress per feature.

    Scoring: done=1.0, partial=0.5, else (not_started/deferred/unknown)=0.0
    Output: integer 0-100, equal-weighted average across 4 axes.
    """
    weights = {"done": 1.0, "partial": 0.5}
    axes = ["spec", "be_tech", "be_code", "bot_code"]
    score = sum(weights.get(feature.get(a, "not_started"), 0.0) for a in axes)
    return int(round(score / len(axes) * 100))


def compute_features_summary(features: list[dict]) -> dict:
    """Aggregate across all features: overall % + per-axis % + count.

    overall: average of compute_feature_progress() across all features
    per-axis: average of axis score across features (also 0-100)
    """
    axes = ["spec", "be_tech", "be_code", "bot_code"]
    if not features:
        return {"overall": 0, **{a: 0 for a in axes}, "count": 0}
    weights = {"done": 1.0, "partial": 0.5}
    per_axis = {a: 0.0 for a in axes}
    overall = 0.0
    for f in features:
        feat_score = 0.0
        for a in axes:
            s = weights.get(f.get(a, "not_started"), 0.0)
            per_axis[a] += s
            feat_score += s
        overall += feat_score / len(axes)
    n = len(features)
    return {
        "overall": int(round(overall / n * 100)),
        **{a: int(round(v / n * 100)) for a, v in per_axis.items()},
        "count": n,
    }
```

Update `render_features_tab` (or equivalent). Goal: keep existing 4 axis columns + summary header bar + ADD a new "Progress" column right after Feature name. The progress column shows a CSS bar with % overlay and color-coded based on completion.

Add helper:
```python
def _progress_class(pct: int) -> str:
    if pct >= 100: return "done"
    if pct >= 80:  return "high"
    if pct >= 40:  return "mid"
    if pct > 0:    return "low"
    return "none"

def render_progress_bar(pct: int) -> str:
    """Inline HTML for CSS progress bar. Used in features table + can be reused for phases."""
    cls = _progress_class(pct)
    return (
        f'<div class="progress-bar"><div class="progress-fill progress-{cls}" '
        f'style="width:{pct}%"></div><span class="progress-label">{pct}%</span></div>'
    )
```

Modify Features tab render to:

1. Build summary header (REPLACE existing Spec/BE Tech/BE Code/Bot Code text-only header):
```python
summary = compute_features_summary(features)
header_html = f'''
<div class="features-summary">
  <div class="features-summary-overall">
    <strong>Overall {summary["overall"]}%</strong>
    <span class="features-count">({summary["count"]} features)</span>
  </div>
  <div class="features-summary-axes">
    <span>Spec <strong>{summary["spec"]}%</strong></span>
    <span>BE Tech <strong>{summary["be_tech"]}%</strong></span>
    <span>BE Code <strong>{summary["be_code"]}%</strong></span>
    <span>Bot Code <strong>{summary["bot_code"]}%</strong></span>
  </div>
</div>
'''
```

2. Table header: add new `<th>Progress</th>` between Feature and Spec columns.

3. For each feature row: compute progress + render bar in new column.
```python
for f in features:
    pct = compute_feature_progress(f)
    bar = render_progress_bar(pct)
    # Row HTML: <td>{f["id"]}</td><td>{escape_html(f["name"])}</td><td class="progress-cell">{bar}</td><td>{f["spec"]}</td>...
```

## 1.5 CSS — add to inline `<style>` block in dashboard HTML head

```css
.features-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 6px;
  margin: 12px 0;
  flex-wrap: wrap;
  gap: 12px;
}
.features-summary-overall strong { font-size: 18px; color: #1976d2; }
.features-summary-overall .features-count { font-size: 13px; color: #666; margin-left: 8px; }
.features-summary-axes { display: flex; gap: 20px; font-size: 14px; }
.features-summary-axes strong { color: #333; }

.progress-cell { min-width: 120px; padding: 6px 8px; }
.progress-bar {
  position: relative;
  height: 18px;
  background: #f0f0f0;
  border-radius: 9px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  transition: width 0.3s;
}
.progress-done { background: #4caf50; }
.progress-high { background: #66bb6a; }
.progress-mid  { background: #2196f3; }
.progress-low  { background: #ff9800; }
.progress-none { background: #e0e0e0; }
.progress-label {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 11px;
  font-weight: 600;
  color: #333;
  pointer-events: none;
}

@media (max-width: 640px) {
  .features-summary { flex-direction: column; align-items: flex-start; }
  .features-summary-axes { flex-wrap: wrap; gap: 8px 16px; }
  .progress-cell { min-width: 80px; }
}
```

## 1.6 Verify tests pass
```bash
pytest tests/scripts/test_dashboard_*.py -v -k "feature_progress or features_summary or features_tab" 2>&1 | tail -30
```
All MUST pass. If any fail → fix implementation (NOT tests).

## 1.7 Rebuild dashboard
```bash
python scripts/build-dashboard.py
[ $(grep -c 'progress-bar' docs/dashboard.html) -ge 1 ] || { echo "HALT: no progress bars in HTML"; exit 1; }
[ $(grep -c 'features-summary' docs/dashboard.html) -ge 1 ] || { echo "HALT: no features summary header"; exit 1; }
# Spot-check: F01 should render around 50-75% range (done, done, partial, not_started)
grep -o 'F01.*progress-fill[^<]*' docs/dashboard.html | head -1 || true
```

## 1.8 Local verify
```bash
ruff check scripts/ && black --check scripts/
NEW_PASS=$(pytest tests/ -q 2>&1 | tail -1)
echo "After: $NEW_PASS"
# Should be baseline + ~8 new tests
```

## 1.9 Commits
```bash
git add tests/scripts/test_dashboard_polish.py tests/scripts/test_dashboard_render.py 2>/dev/null || true
git commit -m "test(dashboard): failing tests for compute_feature_progress + summary + render"

git add scripts/
git commit -m "feat(dashboard): per-feature progress aggregation + visual bars in Features tab

- compute_feature_progress(): equal-weighted avg across spec/be_tech/be_code/bot_code (done=1.0, partial=0.5)
- compute_features_summary(): overall + per-axis % across all features
- render_progress_bar(): reusable CSS bar (color-coded done/high/mid/low/none)
- Features tab: summary header bar + new Progress column
- Existing 4 axis columns retained for per-axis detail
Follows Overview tab phase-bar pattern from B-3."

git add docs/dashboard.html docs/dashboard.md docs/dashboard.json 2>/dev/null
git commit -m "build(dashboard): regenerated with feature progress bars"
```

## 1.10 Codex 1× clean
```bash
if command -v codex >/dev/null 2>&1; then
  codex review --base main 2>&1 | tee .autopilot/state/feature-progress/codex-01.txt
  grep -qiE "schema|breaking|architectural|auth|token|injection|xss" .autopilot/state/feature-progress/codex-01.txt && {
    echo "HALT: Codex flagged"
    exit 1
  }
fi
```

If Codex finds P0/P1 (non-arch/security) → fix this round, re-run verify, atomic commit, re-run Codex (MAX 3 rounds).

## 1.11 Squash + push
```bash
BRANCH=feat/dashboard-feature-progress
git checkout main && git pull --rebase origin main || { echo "HALT: pull"; exit 1; }
git merge --squash $BRANCH
NO_VERIFY=""; [ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "feat(ops-dashboard): feature progress aggregation + visual bars

Mirrors Overview tab phase-bar pattern. Summary header shows overall %
+ per-axis Spec/BE Tech/BE Code/Bot Code aggregates. Each feature row has
color-coded progress bar (done/high/mid/low/none).

Equal-weighted scoring: done=1.0, partial=0.5, else=0.0 across 4 axes."
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push"; exit 1; }
git branch -D $BRANCH
echo "✅ PHASE 1 COMPLETE — feature progress merged as $SHA."
```

---

## Halt Rules

1. Pre-flight fails → HALT before PHASE 1
2. TDD oracle violated (tests pass before implementation) → HALT
3. New test regression on existing tests → HALT
4. Codex flags `schema|breaking|architectural|auth|token|injection|xss` → HALT
5. `# type: ignore` proposed → HALT
6. `git push --force` ever → HALT
7. Tool error 2× in a row → HALT
8. Skip checkpoint output → HALT

## Halt Report Template

```
═══════════════════════════════════════════════════════
FEATURE-PROGRESS WALK-AWAY — HALTED
═══════════════════════════════════════════════════════
Halted at:   PHASE <N> step <X.Y>
Trigger:     <halt rule #>
Detail:      <error / Codex finding>
Branch:      <feature or main>
Recovery:    founder reviews + reruns after fix
═══════════════════════════════════════════════════════
```

## Final Report (complete)

```
═══════════════════════════════════════════════════════
FEATURE-PROGRESS WALK-AWAY — COMPLETE
═══════════════════════════════════════════════════════
Phase 0 — Bootstrap: clean tree
Phase 1 — Feature progress: <SHA>

Files modified:
  - scripts/build-dashboard.py (or scripts/dashboard/render.py)
  - tests/scripts/test_dashboard_*.py
  - docs/dashboard.{html,md,json}

Tests added: <N> (compute_feature_progress + summary + render)
Codex review: <N> round(s), final clean

Dashboard state:
  - Features tab summary header: Overall X% · Spec X% · BE Tech X% · BE Code X% · Bot Code X% (N features)
  - Each feature row has color-coded progress bar (Progress column)
  - Existing 4 axis status columns retained

Visual check (optional): open docs/dashboard.html → Features tab → confirm bars render + color thresholds match
═══════════════════════════════════════════════════════
```

Begin with Global Pre-Flight, then PHASE 0 → 1. Emit checkpoint after each. Do not skip.
