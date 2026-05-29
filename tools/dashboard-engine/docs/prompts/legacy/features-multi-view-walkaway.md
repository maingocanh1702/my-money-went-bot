# Walk-Away Mega-Prompt — Features Tab Multi-View (Cards / Kanban / Table)

You are an autopilot coding agent in `/Users/maingocanh/Projects/MyMoneyWent`. Redesign the Features tab with 3 view modes (Cards / Kanban / Table) + view switcher + localStorage persistence. Single session, end-to-end.

## Mode + Risk

- Mode: AUTOPILOT FULL-AUTO — single feature branch, auto-squash + push at end
- Risk tier: P2 mature (dashboard render class)
- Codex review: 1× clean

## Mandatory Checklist

After each phase emit:
```
✅ PHASE <N> COMPLETE — moving to PHASE <N+1>.
```

```
[ ] PHASE 0 — Bootstrap: verify clean tree + deps
[ ] PHASE 1 — Implement 3 views + switcher + tests + Codex + squash
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
python -c "import json; d=json.load(open('docs/dashboard.json')); assert d.get('features')"
# Verify mega-prompt #3 functions exist (compute_feature_progress, compute_features_summary)
python -c "
import sys; sys.path.insert(0, 'scripts')
try:
    from build_dashboard import compute_feature_progress, compute_features_summary
    print('mega-prompt #3 functions present')
except ImportError as e:
    # Try package layout
    try:
        from dashboard.render import compute_feature_progress, compute_features_summary
        print('mega-prompt #3 functions present (package layout)')
    except ImportError:
        print(f'HALT: compute_feature_progress missing — mega-prompt #3 not shipped? Error: {e}')
        sys.exit(1)
"
BASELINE_PASS=$(pytest tests/ -q 2>&1 | tail -1)
echo "Baseline: $BASELINE_PASS"
```

Any fail → HALT.

---

# PHASE 0 — Bootstrap

```bash
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
[ "$DIRTY" -gt 0 ] && { echo "HALT: tree not clean"; git status --short; exit 1; }
echo "✅ PHASE 0 COMPLETE — clean tree. Moving to PHASE 1."
```

---

# PHASE 1 — 3 View Modes + Switcher

## 1.1 Branch
```bash
git checkout -b feat/features-multi-view
mkdir -p .autopilot/state/features-multi-view
```

## 1.2 Required reading (before code)
1. `scripts/build-dashboard.py` (or `scripts/dashboard/render.py` if split): find existing `render_features_tab`, `compute_feature_progress`, `compute_features_summary` (from mega-prompts #2 + #3).
2. Existing tab switcher JS (from B-2) — same pattern works for view-within-tab switching.
3. `docs/dashboard.json` features array shape: each feature has `id`, `name`, `spec`, `be_tech`, `be_code`, `bot_code`, `phase` (list of phase ints).

## 1.3 TDD — failing tests
Add to `tests/scripts/test_dashboard_render.py` (or wherever Features tab tests live):

```python
import pytest

# Adapt imports to actual module location:
try:
    from scripts.build_dashboard import (
        compute_feature_progress, compute_features_summary,
        render_features_tab, group_features_by_phase,
        render_features_cards, render_features_kanban, render_features_table_view,
    )
except ImportError:
    from scripts.dashboard.render import (
        compute_feature_progress, compute_features_summary,
        render_features_tab, group_features_by_phase,
        render_features_cards, render_features_kanban, render_features_table_view,
    )


SAMPLE_FEATURES = [
    {"id": "F01", "name": "3-Path Onboarding", "spec": "done", "be_tech": "done",
     "be_code": "partial", "bot_code": "not_started", "phase": [1, 4]},
    {"id": "F12", "name": "Multi-User Data Isolation", "spec": "done", "be_tech": "not_started",
     "be_code": "done", "bot_code": "not_started", "phase": [1]},
    {"id": "F16", "name": "P&L View", "spec": "not_started", "be_tech": "not_started",
     "be_code": "not_started", "bot_code": "not_started", "phase": [9]},
]


def test_group_features_by_phase_uses_first_phase():
    grouped = group_features_by_phase(SAMPLE_FEATURES)
    assert 1 in grouped and 9 in grouped
    assert len(grouped[1]) == 2  # F01, F12
    assert len(grouped[9]) == 1  # F16
    # phase ordering deterministic
    assert list(grouped.keys()) == sorted(grouped.keys())


def test_group_features_by_phase_handles_missing_phase():
    fs = [{"id": "FX", "name": "x", "spec": "done", "be_tech": "done",
           "be_code": "done", "bot_code": "done", "phase": []}]
    grouped = group_features_by_phase(fs)
    # Empty phase → bucketed under 0 or last sentinel; just must not crash
    assert len(grouped) >= 1


def test_render_features_cards_includes_progress_ring():
    html = render_features_cards(SAMPLE_FEATURES)
    # SVG ring with progress
    assert '<svg' in html
    assert 'stroke-dasharray' in html
    # Each feature represented
    for f in SAMPLE_FEATURES:
        assert f["id"] in html
        assert f["name"] in html


def test_render_features_cards_escapes_xss():
    fs = [{"id": "FXSS", "name": "<script>alert(1)</script>", "spec": "done",
           "be_tech": "done", "be_code": "done", "bot_code": "done", "phase": [1]}]
    html = render_features_cards(fs)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html or 'alert' not in html


def test_render_features_kanban_groups_by_phase():
    html = render_features_kanban(SAMPLE_FEATURES)
    # Phase headers visible
    assert 'Phase 1' in html
    assert 'Phase 9' in html
    # Each feature in its phase column
    assert 'F01' in html and 'F12' in html and 'F16' in html
    # Mini progress bar markup present
    assert 'progress-fill' in html or 'kanban-bar' in html


def test_render_features_table_view_has_4_segment_bar():
    html = render_features_table_view(SAMPLE_FEATURES)
    # 4 segments per feature row
    assert 'segment-spec' in html or 'seg-spec' in html
    assert 'segment-be_tech' in html or 'seg-be_tech' in html or 'seg-be-tech' in html
    assert 'segment-be_code' in html or 'seg-be_code' in html or 'seg-be-code' in html
    assert 'segment-bot_code' in html or 'seg-bot_code' in html or 'seg-bot-code' in html
    # Each feature has a row
    for f in SAMPLE_FEATURES:
        assert f["id"] in html


def test_render_features_tab_includes_view_switcher():
    html = render_features_tab(SAMPLE_FEATURES)
    # 3 view buttons
    assert 'data-view="cards"' in html
    assert 'data-view="kanban"' in html
    assert 'data-view="table"' in html
    # localStorage persistence in inline JS
    assert 'featuresView' in html  # localStorage key
    assert 'localStorage' in html


def test_render_features_tab_renders_all_3_panels():
    html = render_features_tab(SAMPLE_FEATURES)
    # All 3 view panels in DOM (JS toggles visibility, none hidden at render time)
    assert 'features-view-cards' in html
    assert 'features-view-kanban' in html
    assert 'features-view-table' in html


def test_segment_color_class_done_partial_not_started():
    # Test the helper used inside table view
    try:
        from scripts.build_dashboard import _segment_class
    except ImportError:
        from scripts.dashboard.render import _segment_class
    assert _segment_class("done") == "seg-done"
    assert _segment_class("partial") == "seg-partial"
    assert _segment_class("not_started") == "seg-none"
    assert _segment_class("deferred") == "seg-none"
    assert _segment_class("unknown") == "seg-none"
```

Run — MUST fail (functions don't exist yet):
```bash
pytest tests/scripts/test_dashboard_render.py -v -k "group_features_by_phase or render_features_cards or render_features_kanban or render_features_table_view or render_features_tab_includes or render_features_tab_renders or segment_color" 2>&1 | tail -25
```
Any pass → TDD oracle violated → HALT.

## 1.4 Implement helpers

Add to `scripts/build-dashboard.py` (or `scripts/dashboard/render.py` if package split):

```python
def group_features_by_phase(features: list[dict]) -> dict[int, list[dict]]:
    """Group features by their first phase int. Features with empty phase → bucket 0."""
    grouped: dict[int, list[dict]] = {}
    for f in features:
        phases = f.get("phase") or [0]
        primary = phases[0] if phases else 0
        grouped.setdefault(primary, []).append(f)
    # Sort keys ascending
    return {k: grouped[k] for k in sorted(grouped.keys())}


def _segment_class(status: str) -> str:
    """Map status to CSS class for 4-segment bar."""
    return {"done": "seg-done", "partial": "seg-partial"}.get(status, "seg-none")


def _phase_name(phase_num: int) -> str:
    """Friendly phase name. Adjust to roadmap labels."""
    names = {
        0: "Unphased",
        1: "Foundation",
        2: "Handlers",
        3: "Pricing",
        4: "SePay",
        5: "Email Parsers",
        6: "Deploy + Polish",
        7: "Closed Beta",
        8: "Soft Launch",
        9: "Business",
        10: "Growth",
        11: "Family Plan",
    }
    return names.get(phase_num, f"Phase {phase_num}")
```

## 1.5 Implement render_features_cards (Linear Project view)

```python
def render_features_cards(features: list[dict]) -> str:
    """Card grid with SVG progress ring + 4 axis icons. Linear-Project-inspired."""
    if not features:
        return '<div class="features-empty">No features</div>'
    cards = []
    for f in features:
        pct = compute_feature_progress(f)
        # SVG ring math: circumference = 2 * pi * r (r=15) ≈ 94.2
        circ = 94.2
        dash = circ * pct / 100
        phase_str = ",".join(str(p) for p in f.get("phase", []))
        ring_color = "var(--color-text-success)" if pct >= 100 else (
            "var(--color-text-info)" if pct > 0 else "var(--color-border-tertiary)"
        )
        axis_icons = []
        for axis_key, axis_label in [
            ("spec", "Spec"), ("be_tech", "Tech"),
            ("be_code", "Code"), ("bot_code", "Bot"),
        ]:
            v = f.get(axis_key, "not_started")
            if v == "done":
                icon = '<i class="ti ti-check" style="color:#2e7d32;font-size:14px;"></i>'
            elif v == "partial":
                icon = '<i class="ti ti-progress" style="color:#1565c0;font-size:14px;"></i>'
            else:
                icon = '<i class="ti ti-circle" style="color:#999;font-size:14px;"></i>'
            axis_icons.append(
                f'<div style="text-align:center;font-size:10px;color:#777;">{icon}<div>{axis_label}</div></div>'
            )
        cards.append(
            f'<div class="feature-card">'
            f'  <div class="feature-card-head">'
            f'    <svg width="40" height="40" viewBox="0 0 36 36">'
            f'      <circle cx="18" cy="18" r="15" fill="none" stroke="#e0e0e0" stroke-width="3"/>'
            f'      <circle cx="18" cy="18" r="15" fill="none" stroke="{ring_color}" stroke-width="3" '
            f'              stroke-dasharray="{dash:.1f} {circ:.1f}" transform="rotate(-90 18 18)" stroke-linecap="round"/>'
            f'      <text x="18" y="22" text-anchor="middle" font-size="11" font-weight="600">{pct}%</text>'
            f'    </svg>'
            f'    <div class="feature-card-meta">'
            f'      <div class="feature-card-id">{escape_html(f["id"])} · Phase {escape_html(phase_str)}</div>'
            f'      <div class="feature-card-name">{escape_html(f["name"])}</div>'
            f'    </div>'
            f'  </div>'
            f'  <div class="feature-card-axes">{"".join(axis_icons)}</div>'
            f'</div>'
        )
    return f'<div class="features-cards-grid">{"".join(cards)}</div>'
```

## 1.6 Implement render_features_kanban (phase swimlanes)

```python
def render_features_kanban(features: list[dict]) -> str:
    """Phase-grouped swimlanes with mini progress bars."""
    grouped = group_features_by_phase(features)
    if not grouped:
        return '<div class="features-empty">No features</div>'
    cols = []
    for phase_num, items in grouped.items():
        phase_label = _phase_name(phase_num)
        items_html = []
        for f in items:
            pct = compute_feature_progress(f)
            fill_color = "var(--color-text-success)" if pct >= 100 else (
                "var(--color-text-info)" if pct > 0 else "var(--color-border-tertiary)"
            )
            items_html.append(
                f'<div class="kanban-card">'
                f'  <div class="kanban-card-row">'
                f'    <span class="kanban-card-id">{escape_html(f["id"])}</span>'
                f'    <span class="kanban-card-pct">{pct}%</span>'
                f'  </div>'
                f'  <div class="kanban-card-name">{escape_html(f["name"])}</div>'
                f'  <div class="kanban-bar-track">'
                f'    <div class="kanban-bar-fill" style="width:{pct}%;background:{fill_color};"></div>'
                f'  </div>'
                f'</div>'
            )
        cols.append(
            f'<div class="kanban-col">'
            f'  <div class="kanban-col-head">'
            f'    <span class="kanban-col-title">Phase {phase_num} · {escape_html(phase_label)}</span>'
            f'    <span class="kanban-col-count">{len(items)}</span>'
            f'  </div>'
            f'  <div class="kanban-col-body">{"".join(items_html)}</div>'
            f'</div>'
        )
    return f'<div class="features-kanban-grid">{"".join(cols)}</div>'
```

## 1.7 Implement render_features_table_view (4-segment bar table)

```python
def render_features_table_view(features: list[dict]) -> str:
    """Dense table with 4-segment progress bar per feature row."""
    if not features:
        return '<div class="features-empty">No features</div>'
    rows = []
    for f in features:
        pct = compute_feature_progress(f)
        phase_str = ",".join(str(p) for p in f.get("phase", []))
        segments_html = "".join(
            f'<div class="features-seg seg-{axis_key} {_segment_class(f.get(axis_key, "not_started"))}" '
            f'title="{axis_label}: {f.get(axis_key, "not_started")}"></div>'
            for axis_key, axis_label in [
                ("spec", "Spec"), ("be_tech", "BE Tech"),
                ("be_code", "BE Code"), ("bot_code", "Bot Code"),
            ]
        )
        rows.append(
            f'<div class="features-row">'
            f'  <div class="features-row-head">'
            f'    <span class="features-row-id">{escape_html(f["id"])}</span>'
            f'    <span class="features-row-name">{escape_html(f["name"])}</span>'
            f'    <span class="features-row-meta"><strong>{pct}%</strong> · Phase {escape_html(phase_str)}</span>'
            f'  </div>'
            f'  <div class="features-row-bar">{segments_html}</div>'
            f'</div>'
        )
    legend = (
        '<div class="features-table-legend">'
        '  <span><span class="legend-dot legend-done"></span>Done</span>'
        '  <span><span class="legend-dot legend-partial"></span>Partial</span>'
        '  <span><span class="legend-dot legend-none"></span>Not started</span>'
        '  <span class="legend-axes">Axes left-to-right: Spec · BE Tech · BE Code · Bot Code</span>'
        '</div>'
    )
    return f'<div class="features-table-list">{"".join(rows)}</div>{legend}'
```

## 1.8 Implement render_features_tab (orchestrates switcher + 3 panels)

Replace existing `render_features_tab` with:

```python
def render_features_tab(features: list[dict]) -> str:
    summary = compute_features_summary(features)
    summary_html = f'''
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
    switcher_html = '''
<div class="features-view-switcher" role="tablist" aria-label="Features view">
  <button type="button" data-view="cards" class="features-view-btn" role="tab">Cards</button>
  <button type="button" data-view="kanban" class="features-view-btn" role="tab">Kanban</button>
  <button type="button" data-view="table" class="features-view-btn" role="tab">Table</button>
</div>
'''
    cards_html = render_features_cards(features)
    kanban_html = render_features_kanban(features)
    table_html = render_features_table_view(features)

    switcher_js = '''
<script>
(function() {
  var btns = document.querySelectorAll('.features-view-btn');
  var panels = {
    cards: document.getElementById('features-view-cards'),
    kanban: document.getElementById('features-view-kanban'),
    table: document.getElementById('features-view-table'),
  };
  function activate(view) {
    btns.forEach(function(b) { b.classList.toggle('active', b.dataset.view === view); });
    Object.keys(panels).forEach(function(k) {
      if (panels[k]) panels[k].style.display = (k === view) ? '' : 'none';
    });
    try { localStorage.setItem('featuresView', view); } catch(e) {}
  }
  btns.forEach(function(b) { b.addEventListener('click', function() { activate(b.dataset.view); }); });
  var saved; try { saved = localStorage.getItem('featuresView'); } catch(e) {}
  activate(saved || 'cards');
})();
</script>
'''
    return (
        f'{summary_html}'
        f'{switcher_html}'
        f'<div id="features-view-cards" class="features-view-panel">{cards_html}</div>'
        f'<div id="features-view-kanban" class="features-view-panel">{kanban_html}</div>'
        f'<div id="features-view-table" class="features-view-panel">{table_html}</div>'
        f'{switcher_js}'
    )
```

## 1.9 CSS — add to inline `<style>` block in dashboard HTML head

```css
/* View switcher */
.features-view-switcher { display: inline-flex; gap: 4px; margin: 12px 0; background: #f0f0f0; border-radius: 8px; padding: 3px; }
.features-view-btn { border: 0; background: transparent; padding: 5px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; color: #555; transition: background 0.15s; }
.features-view-btn:hover { background: rgba(255,255,255,0.5); }
.features-view-btn.active { background: #fff; color: #111; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }

/* Cards view */
.features-cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 12px 0; }
.feature-card { background: #fff; border: 1px solid #e8e8e8; border-radius: 10px; padding: 12px; }
.feature-card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.feature-card-meta { min-width: 0; flex: 1; }
.feature-card-id { font-size: 11px; color: #999; line-height: 1.2; }
.feature-card-name { font-size: 13px; font-weight: 500; line-height: 1.3; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feature-card-axes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }

/* Kanban view */
.features-kanban-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 12px 0; }
.kanban-col { background: #f7f7f7; border-radius: 8px; padding: 10px 12px; }
.kanban-col-head { display: flex; justify-content: space-between; font-size: 12px; color: #555; margin-bottom: 8px; }
.kanban-col-title { font-weight: 500; color: #222; }
.kanban-col-count { font-size: 11px; color: #888; }
.kanban-col-body { display: flex; flex-direction: column; gap: 6px; }
.kanban-card { background: #fff; border: 1px solid #e8e8e8; border-radius: 6px; padding: 6px 8px; }
.kanban-card-row { display: flex; justify-content: space-between; font-size: 12px; }
.kanban-card-id { font-weight: 500; color: #222; }
.kanban-card-pct { color: #555; }
.kanban-card-name { font-size: 11px; color: #666; margin: 2px 0 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kanban-bar-track { height: 4px; background: #eee; border-radius: 2px; overflow: hidden; }
.kanban-bar-fill { height: 100%; transition: width 0.3s; }

/* Table view (4-segment bars) */
.features-table-list { display: flex; flex-direction: column; gap: 10px; margin: 12px 0; }
.features-row { background: #fff; border: 1px solid #e8e8e8; border-radius: 6px; padding: 10px 14px; }
.features-row-head { display: flex; justify-content: space-between; font-size: 13px; align-items: center; }
.features-row-id { color: #999; margin-right: 8px; font-size: 11px; }
.features-row-name { flex: 1; font-weight: 500; color: #222; }
.features-row-meta { color: #555; }
.features-row-meta strong { color: #111; }
.features-row-bar { display: flex; gap: 2px; margin-top: 6px; height: 8px; border-radius: 4px; overflow: hidden; }
.features-seg { flex: 1; }
.seg-done { background: #2e7d32; }
.seg-partial { background: #1565c0; }
.seg-none { background: #e0e0e0; }
.features-table-legend { display: flex; gap: 14px; font-size: 11px; color: #777; margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.legend-done { background: #2e7d32; }
.legend-partial { background: #1565c0; }
.legend-none { background: #e0e0e0; }
.legend-axes { margin-left: auto; }

/* Responsive */
@media (max-width: 640px) {
  .features-summary { flex-direction: column; align-items: flex-start; }
  .features-summary-axes { flex-wrap: wrap; gap: 8px 16px; }
  .features-cards-grid { grid-template-columns: 1fr; }
  .features-kanban-grid { grid-template-columns: 1fr; }
}
```

## 1.10 Verify tests pass
```bash
pytest tests/scripts/test_dashboard_render.py -v -k "group_features_by_phase or render_features_cards or render_features_kanban or render_features_table_view or render_features_tab_includes or render_features_tab_renders or segment_color" 2>&1 | tail -30
```
All MUST pass. If any fail → fix implementation (NOT tests).

## 1.11 Rebuild + verify markup
```bash
python scripts/build-dashboard.py
[ $(grep -c 'data-view="cards"' docs/dashboard.html) -ge 1 ] || { echo "HALT: cards switcher missing"; exit 1; }
[ $(grep -c 'data-view="kanban"' docs/dashboard.html) -ge 1 ] || { echo "HALT: kanban switcher missing"; exit 1; }
[ $(grep -c 'data-view="table"' docs/dashboard.html) -ge 1 ] || { echo "HALT: table switcher missing"; exit 1; }
grep -q 'featuresView' docs/dashboard.html || { echo "HALT: localStorage key missing"; exit 1; }
[ $(grep -c 'feature-card' docs/dashboard.html) -ge 1 ] || { echo "HALT: cards rendered empty"; exit 1; }
[ $(grep -c 'kanban-col' docs/dashboard.html) -ge 1 ] || { echo "HALT: kanban rendered empty"; exit 1; }
[ $(grep -c 'features-seg' docs/dashboard.html) -ge 1 ] || { echo "HALT: segments rendered empty"; exit 1; }
```

## 1.12 Local verify
```bash
ruff check scripts/ && black --check scripts/
NEW_PASS=$(pytest tests/ -q 2>&1 | tail -1)
echo "After: $NEW_PASS"
# Should be baseline + ~9 new tests
```

## 1.13 Commits
```bash
git add tests/scripts/test_dashboard_render.py
git commit -m "test(dashboard): failing tests for 3-view Features tab (cards/kanban/table)"

git add scripts/
git commit -m "feat(dashboard): Features tab multi-view (Cards / Kanban / Table)

- group_features_by_phase: bucket features by primary phase int
- render_features_cards: SVG progress ring + 4 axis icons (Linear Project style)
- render_features_kanban: phase swimlanes + mini progress bar (Roadmap style)
- render_features_table_view: 4-segment stacked bar table (dense scan)
- render_features_tab: orchestrates view switcher + 3 panels + inline JS
- localStorage persists active view (key: featuresView), default = cards
- All views XSS-safe via escape_html"

git add docs/dashboard.html docs/dashboard.md docs/dashboard.json 2>/dev/null
git commit -m "build(dashboard): regenerated with multi-view Features tab"
```

## 1.14 Codex 1× clean
```bash
if command -v codex >/dev/null 2>&1; then
  codex review --base main 2>&1 | tee .autopilot/state/features-multi-view/codex-01.txt
  grep -qiE "schema|breaking|architectural|auth|token|injection|xss" .autopilot/state/features-multi-view/codex-01.txt && {
    echo "HALT: Codex flagged"
    exit 1
  }
fi
```

If Codex finds P0/P1 → fix this round, re-run verify, commit `fix(dashboard): address codex round NN — <summary>`, re-run Codex (MAX 3 rounds).

## 1.15 Squash + push
```bash
BRANCH=feat/features-multi-view
git checkout main && git pull --rebase origin main || { echo "HALT: pull"; exit 1; }
git merge --squash $BRANCH
NO_VERIFY=""; [ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "feat(ops-dashboard): Features tab 3-view design (Cards/Kanban/Table)

3 view modes with localStorage-persisted switcher:
- Cards: Linear Project-inspired with SVG progress ring + 4 axis icons
- Kanban: phase swimlanes with mini progress bars (Roadmap feel)
- Table: 4-segment stacked bar per feature (dense scan, axis-detail)

Default = Cards. Switcher pill row above panels. All panels in DOM,
JS-toggled display. Mobile responsive: single-column on <640px.

Reuses compute_feature_progress + compute_features_summary from prior batch.
+9 tests (group_by_phase + 3 render functions + switcher markup + segment helper)."
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push"; exit 1; }
git branch -D $BRANCH
echo "✅ PHASE 1 COMPLETE — features-multi-view merged as $SHA."
```

---

## Halt Rules

1. Pre-flight fails (no clean tree, missing #3 functions) → HALT
2. TDD oracle violated → HALT
3. Existing test regression → HALT
4. Codex flags `schema|breaking|architectural|auth|token|injection|xss` → HALT
5. `# type: ignore` proposed → HALT
6. `git push --force` ever → HALT
7. Tool error 2× → HALT
8. Skip checkpoint output → HALT
9. View switcher localStorage missing → HALT (key UX feature)

## Halt Report

```
═══════════════════════════════════════════════════════
FEATURES-MULTI-VIEW WALK-AWAY — HALTED
═══════════════════════════════════════════════════════
Halted at:   PHASE <N> step <X.Y>
Trigger:     <halt rule #>
Detail:      <error / Codex finding>
Branch:      <feature or main>
Recovery:    founder reviews + reruns after fix
═══════════════════════════════════════════════════════
```

## Final Report

```
═══════════════════════════════════════════════════════
FEATURES-MULTI-VIEW WALK-AWAY — COMPLETE
═══════════════════════════════════════════════════════
Phase 0 — Bootstrap: clean tree
Phase 1 — Multi-view: <SHA>

Files modified:
  - scripts/build-dashboard.py (or scripts/dashboard/render.py)
  - tests/scripts/test_dashboard_render.py
  - docs/dashboard.{html,md,json}

Tests added: <N>
Codex review: <N> round(s)

Features tab now has 3 view modes (switcher persists via localStorage):
  - Cards (default): SVG ring + axis icons
  - Kanban: phase swimlanes
  - Table: 4-segment stacked bars

Visual check: open docs/dashboard.html → Features tab → click between Cards/Kanban/Table
═══════════════════════════════════════════════════════
```

Begin with Global Pre-Flight, then PHASE 0 → 1. Emit checkpoint after each.
