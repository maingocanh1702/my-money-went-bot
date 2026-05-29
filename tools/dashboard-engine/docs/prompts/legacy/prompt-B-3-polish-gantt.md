Task: ops-dashboard B-3 — polish: CSS Gantt + readiness aggregation + staleness warnings
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/ops-dashboard-polish`, Codex 1× clean, STOP_AT_READY.

Risk tier: P2 mature

Context: Visual polish over B-2 tabs. CSS Gantt (no Chart.js dep), readiness bar, staleness colors. Depends on B-1 + B-2.

Scope: Gantt render + readiness compute + staleness CSS. NO JS libs. NO parser changes.

Required reading: plan §B-3, §B-2 layout (Gantt + readiness placement), `docs/dashboard.json` schema.

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current; git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check && pytest tests/ -v
grep -q 'data-tab=' docs/dashboard.html   # B-2 merged
python -c "import json; d=json.load(open('docs/dashboard.json')); assert d.get('phases')"   # B-1 merged
```

Anti-patterns: add Chart.js/D3/Plotly, hard-code phase dates, touch parsers, hide stale docs (color-warn only).

Step 1 — Branch
```bash
git checkout -b feat/ops-dashboard-polish
mkdir -p .autopilot/state/b-3/codex
```

Step 2 — TDD `tests/scripts/test_dashboard_polish.py`
- `test_gantt_renders_phase_bars`
- `test_gantt_bar_width_proportional_to_duration`
- `test_gantt_today_marker_present`
- `test_readiness_aggregates_features` (spec=done → spec_pct=100)
- `test_readiness_partial_counted_as_half`
- `test_staleness_yellow_at_8_days`
- `test_staleness_red_at_15_days`
- `test_staleness_current_no_class`

Tests fail first.

Step 3 — Implement
```python
def render_gantt(phases: list[dict], today: date) -> str:
    """CSS div bars, width % = duration / total span."""
    if not phases: return '<div class="gantt-empty">No phase data</div>'
    starts = [parse_iso(p["start_date"]) for p in phases if p.get("start_date")]
    ends = [parse_iso(p["target_date"]) for p in phases if p.get("target_date")]
    if not starts or not ends: return '<div class="gantt-empty">Missing dates</div>'
    project_start, project_end = min(starts), max(ends)
    total_days = max((project_end - project_start).days, 1)
    bars = []
    for p in phases:
        s, e = parse_iso(p["start_date"]), parse_iso(p["target_date"])
        left = (s - project_start).days / total_days * 100
        width = (e - s).days / total_days * 100
        bars.append(
            f'<div class="gantt-row"><div class="gantt-label">{escape_html(p["name"])}</div>'
            f'<div class="gantt-track"><div class="gantt-bar gantt-{p["status"]}" '
            f'style="left:{left:.1f}%;width:{width:.1f}%"></div></div></div>'
        )
    today_pct = (today - project_start).days / total_days * 100
    return f'<div class="gantt">{"".join(bars)}<div class="gantt-today" style="left:{today_pct:.1f}%"></div></div>'

def compute_readiness(features: list[dict]) -> dict:
    if not features: return {k: 0 for k in ["spec", "be_tech", "be_code", "bot_code"]}
    counts = {k: 0.0 for k in ["spec", "be_tech", "be_code", "bot_code"]}
    for f in features:
        for k in counts:
            v = f.get(k, "not_started")
            counts[k] += {"done": 1.0, "partial": 0.5}.get(v, 0.0)
    n = len(features)
    return {k: int(round(v / n * 100)) for k, v in counts.items()}

def staleness_class(days: int) -> str:
    if days >= 14: return "stale-red"
    if days >= 7: return "stale-yellow"
    return ""
```

CSS in HTML head:
```css
.gantt { position: relative; padding: 8px 0; }
.gantt-row { display: grid; grid-template-columns: 140px 1fr; gap: 8px; align-items: center; margin: 4px 0; }
.gantt-track { position: relative; height: 16px; background: #f3f3f3; border-radius: 3px; }
.gantt-bar { position: absolute; top: 0; bottom: 0; border-radius: 3px; }
.gantt-completed { background: #4caf50; }
.gantt-in_progress { background: #2196f3; }
.gantt-planned { background: #9e9e9e; }
.gantt-deferred { background: #ffc107; }
.gantt-today { position: absolute; top: 0; bottom: 0; width: 2px; background: #f44336; }
.readiness-bar { display: flex; gap: 16px; padding: 8px; background: #fafafa; border-radius: 4px; }
.stale-yellow { background: #fff3cd; }
.stale-red { background: #f8d7da; }
```

Tests pass.

Step 4 — Rebuild + verify
```bash
python scripts/build-dashboard.py
grep -c 'gantt-bar' docs/dashboard.html        # ≥ phases count
grep -c 'readiness-bar' docs/dashboard.html     # ≥1
```

Step 5 — Local verify
```bash
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
```

Commits:
```bash
git add tests/scripts/test_dashboard_polish.py
git commit -m "test(dashboard-polish): failing tests for Gantt + readiness + staleness"

git add scripts/
git commit -m "feat(dashboard): CSS Gantt + readiness aggregation + staleness warnings

No Chart.js dep, vanilla CSS div bars + today marker. Refs §B-3."

git add docs/dashboard.html docs/dashboard.md
git commit -m "build(dashboard): regenerated with polish"
```

Step 6 — Codex 1× clean
Attention: division by zero guards, null date handling, CSS class collisions, staleness threshold consistency.

Circuit breakers: standard + LIBRARY_INTRODUCED, ZERO_DIVISION.

Final report (READY).

Begin with Pre-flight, then Step 1.
