"""B-3: CSS Gantt bars + feature readiness aggregation.

No external dependencies (no Chart.js) — vanilla CSS div bars positioned
absolutely within a horizontal track. Today marker is a thin vertical line.

Readiness aggregation: per-column average of feature status (done=1.0,
partial=0.5, else=0.0) as integer percentage 0-100.
"""

from __future__ import annotations

import html
from datetime import date
from typing import Any

# Readiness scoring weights: done=full credit, partial=half, anything else=0.
_READINESS_WEIGHTS: dict[str, float] = {"done": 1.0, "partial": 0.5}

# Visible status slugs we know how to color in the Gantt bar.
_GANTT_STATUS_CLASSES = {"done", "partial", "not_started", "blocked", "deferred", "planned"}


def _parse_iso(value: str) -> date:
    parts = value.split("T", 1)[0].split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def render_gantt(phases: list[dict[str, Any]], today: date) -> str:
    """Render a CSS Gantt with one bar per phase + a 'today' vertical marker.

    Phases need ``name``, ``status``, ``start_date``, ``target_date``. Rows
    missing dates are skipped. Empty/missing input → an empty placeholder
    (never crashes on zero-day spans or empty lists — Phase 5 §B-3 guard).
    """
    rows = [p for p in phases if p.get("start_date") and p.get("target_date")]
    if not rows:
        return '<div class="gantt gantt-empty">No phase timeline data</div>'
    starts = [_parse_iso(p["start_date"]) for p in rows]
    ends = [_parse_iso(p["target_date"]) for p in rows]
    p_start = min(starts)
    p_end = max(ends)
    total = max((p_end - p_start).days, 1)  # avoid div-by-zero on same-day span
    bars: list[str] = []
    for p in rows:
        s = _parse_iso(p["start_date"])
        e = _parse_iso(p["target_date"])
        left_pct = (s - p_start).days / total * 100
        width_pct = max((e - s).days / total * 100, 0.5)
        status = p.get("status", "planned")
        if status not in _GANTT_STATUS_CLASSES:
            status = "planned"
        name = html.escape(str(p.get("name", "")), quote=True)
        bars.append(
            f'<div class="gantt-row">'
            f'<div class="gantt-label">{name}</div>'
            f'<div class="gantt-track">'
            f'<div class="gantt-bar gantt-{status}" '
            f'style="left:{left_pct:.1f}%;width:{width_pct:.1f}%"></div>'
            f"</div></div>"
        )
    today_pct = max(min((today - p_start).days / total * 100, 100), 0)
    return (
        f'<div class="gantt">{"".join(bars)}'
        f'<div class="gantt-today" style="left:{today_pct:.1f}%"></div></div>'
    )


def compute_readiness(features: list[dict[str, Any]]) -> dict[str, int]:
    """Per-column readiness % (spec/be_tech/be_code/bot_code).

    Empty input returns all zeros — no division by zero.
    """
    columns = ("spec", "be_tech", "be_code", "bot_code")
    if not features:
        return dict.fromkeys(columns, 0)
    n = len(features)
    out: dict[str, int] = {}
    for col in columns:
        total_score = 0.0
        for f in features:
            total_score += _READINESS_WEIGHTS.get(str(f.get(col, "")), 0.0)
        out[col] = int(round(total_score / n * 100))
    return out


def render_readiness_bar(readiness: dict[str, int]) -> str:
    """Inline readiness summary — sits above the features matrix."""
    cells = []
    for col, label in [
        ("spec", "Spec"),
        ("be_tech", "BE Tech"),
        ("be_code", "BE Code"),
        ("bot_code", "Bot Code"),
    ]:
        pct = readiness.get(col, 0)
        cells.append(
            f'<div class="readiness-cell">'
            f'<span class="readiness-label">{label}</span> '
            f'<span class="readiness-pct">{pct}%</span></div>'
        )
    return f'<div class="readiness-bar">{"".join(cells)}</div>'


# CSS additions for B-3 polish. Merged into dashboard.html alongside TAB_CSS.
POLISH_CSS = """
.gantt { position: relative; padding: 8px 0 16px; }
.gantt-empty { color: #888; font-style: italic; padding: 12px; }
.gantt-row { display: grid; grid-template-columns: 140px 1fr; gap: 8px; align-items: center; margin: 4px 0; }
.gantt-label { font-size: 12px; color: #444; }
.gantt-track { position: relative; height: 14px; background: #f3f3f3; border-radius: 3px; overflow: hidden; }
.gantt-bar { position: absolute; top: 0; bottom: 0; border-radius: 3px; }
.gantt-done { background: #4caf50; }
.gantt-partial { background: #2196f3; }
.gantt-not_started, .gantt-planned { background: #bdbdbd; }
.gantt-blocked { background: #f44336; }
.gantt-deferred { background: #ffc107; }
.gantt-today { position: absolute; top: 28px; bottom: 16px; width: 2px; background: #f44336; pointer-events: none; left: 0; margin-left: 148px; }
.readiness-bar { display: flex; gap: 16px; padding: 8px 12px; background: #fafafa; border-radius: 4px; margin: 8px 0; flex-wrap: wrap; }
.readiness-cell { font-size: 13px; color: #444; }
.readiness-label { color: #777; }
.readiness-pct { font-weight: 600; color: #1976d2; }
@media (max-width: 640px) {
  .gantt-row { grid-template-columns: 90px 1fr; }
  .gantt-today { margin-left: 98px; }
}
"""
