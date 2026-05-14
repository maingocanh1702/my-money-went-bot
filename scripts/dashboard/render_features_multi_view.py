"""Features tab multi-view renderers: Cards / Kanban / Table.

Three view modes with a localStorage-persisted switcher. All data
interpolation goes through ``escape_html`` from render.py.
"""

from __future__ import annotations

import html as _html
from typing import Any


def escape_html(text: Any) -> str:
    if text is None:
        return ""
    return _html.escape(str(text), quote=True)


def _segment_class(status: str) -> str:
    return {"done": "seg-done", "partial": "seg-partial"}.get(status, "seg-none")


_PHASE_NAMES = {
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


def _parse_phase_str(phase_val: Any) -> list[int]:
    if isinstance(phase_val, list):
        return [int(p) for p in phase_val if str(p).strip()]
    s = str(phase_val or "").strip()
    if not s:
        return []
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def group_features_by_phase(
    features: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for f in features:
        phases = _parse_phase_str(f.get("phase"))
        primary = phases[0] if phases else 0
        grouped.setdefault(primary, []).append(f)
    return {k: grouped[k] for k in sorted(grouped.keys())}


def render_features_cards(features: list[dict[str, Any]]) -> str:
    from scripts.dashboard.polish import compute_feature_progress

    if not features:
        return '<div class="features-empty">No features</div>'
    cards = []
    for f in features:
        pct = compute_feature_progress(f)
        circ = 94.2
        dash = circ * pct / 100
        phase_str = escape_html(str(f.get("phase", "")))
        ring_color = (
            "var(--color-text-success)"
            if pct >= 100
            else "var(--color-text-info)" if pct > 0 else "var(--color-border-tertiary)"
        )
        axis_icons = []
        for axis_key, axis_label in [
            ("spec", "Spec"),
            ("be_tech", "Tech"),
            ("be_code", "Code"),
            ("bot_code", "Bot"),
        ]:
            v = f.get(axis_key, "not_started")
            if v == "done":
                icon = '<i class="ti ti-check" style="color:#2e7d32;font-size:14px;"></i>'
            elif v == "partial":
                icon = '<i class="ti ti-progress" style="color:#1565c0;font-size:14px;"></i>'
            else:
                icon = '<i class="ti ti-circle" style="color:#999;font-size:14px;"></i>'
            axis_icons.append(
                f'<div style="text-align:center;font-size:10px;color:#777;">'
                f"{icon}<div>{axis_label}</div></div>"
            )
        cards.append(
            f'<div class="feature-card">'
            f'<div class="feature-card-head">'
            f'<svg width="40" height="40" viewBox="0 0 36 36">'
            f'<circle cx="18" cy="18" r="15" fill="none" stroke="#e0e0e0" stroke-width="3"/>'
            f'<circle cx="18" cy="18" r="15" fill="none" stroke="{ring_color}" stroke-width="3" '
            f'stroke-dasharray="{dash:.1f} {circ:.1f}" transform="rotate(-90 18 18)" '
            f'stroke-linecap="round"/>'
            f'<text x="18" y="22" text-anchor="middle" font-size="11" '
            f'font-weight="600">{pct}%</text>'
            f"</svg>"
            f'<div class="feature-card-meta">'
            f'<div class="feature-card-id">{escape_html(f.get("id", ""))} · Phase {phase_str}</div>'
            f'<div class="feature-card-name">{escape_html(f.get("name", ""))}</div>'
            f"</div></div>"
            f'<div class="feature-card-axes">{"".join(axis_icons)}</div>'
            f"</div>"
        )
    return f'<div class="features-cards-grid">{"".join(cards)}</div>'


def render_features_kanban(features: list[dict[str, Any]]) -> str:
    from scripts.dashboard.polish import compute_feature_progress

    grouped = group_features_by_phase(features)
    if not grouped:
        return '<div class="features-empty">No features</div>'
    cols = []
    for phase_num, items in grouped.items():
        phase_label = _PHASE_NAMES.get(phase_num, f"Phase {phase_num}")
        items_html = []
        for f in items:
            pct = compute_feature_progress(f)
            fill_color = (
                "var(--color-text-success)"
                if pct >= 100
                else "var(--color-text-info)" if pct > 0 else "var(--color-border-tertiary)"
            )
            items_html.append(
                f'<div class="kanban-card">'
                f'<div class="kanban-card-row">'
                f'<span class="kanban-card-id">{escape_html(f.get("id", ""))}</span>'
                f'<span class="kanban-card-pct">{pct}%</span>'
                f"</div>"
                f'<div class="kanban-card-name">{escape_html(f.get("name", ""))}</div>'
                f'<div class="kanban-bar-track">'
                f'<div class="kanban-bar-fill" style="width:{pct}%;background:{fill_color};"></div>'
                f"</div></div>"
            )
        cols.append(
            f'<div class="kanban-col">'
            f'<div class="kanban-col-head">'
            f'<span class="kanban-col-title">Phase {phase_num} · {escape_html(phase_label)}</span>'
            f'<span class="kanban-col-count">{len(items)}</span>'
            f"</div>"
            f'<div class="kanban-col-body">{"".join(items_html)}</div>'
            f"</div>"
        )
    return f'<div class="features-kanban-grid">{"".join(cols)}</div>'


def render_features_table_view(features: list[dict[str, Any]]) -> str:
    from scripts.dashboard.polish import compute_feature_progress

    if not features:
        return '<div class="features-empty">No features</div>'
    rows = []
    for f in features:
        pct = compute_feature_progress(f)
        phase_str = escape_html(str(f.get("phase", "")))
        segments_html = "".join(
            f'<div class="features-seg seg-{axis_key} '
            f'{_segment_class(f.get(axis_key, "not_started"))}" '
            f'title="{axis_label}: {escape_html(f.get(axis_key, "not_started"))}"></div>'
            for axis_key, axis_label in [
                ("spec", "Spec"),
                ("be_tech", "BE Tech"),
                ("be_code", "BE Code"),
                ("bot_code", "Bot Code"),
            ]
        )
        rows.append(
            f'<div class="features-row">'
            f'<div class="features-row-head">'
            f'<span class="features-row-id">{escape_html(f.get("id", ""))}</span>'
            f'<span class="features-row-name">{escape_html(f.get("name", ""))}</span>'
            f'<span class="features-row-meta"><strong>{pct}%</strong> · '
            f"Phase {phase_str}</span>"
            f"</div>"
            f'<div class="features-row-bar">{segments_html}</div>'
            f"</div>"
        )
    legend = (
        '<div class="features-table-legend">'
        '<span><span class="legend-dot legend-done"></span>Done</span>'
        '<span><span class="legend-dot legend-partial"></span>Partial</span>'
        '<span><span class="legend-dot legend-none"></span>Not started</span>'
        '<span class="legend-axes">Axes left-to-right: Spec · BE Tech · BE Code · Bot Code</span>'
        "</div>"
    )
    return f'<div class="features-table-list">{"".join(rows)}</div>{legend}'


FEATURES_VIEW_SWITCHER_JS = (
    "(function() {\n"
    "  var btns = document.querySelectorAll('.features-view-btn');\n"
    "  var panels = {\n"
    "    cards: document.getElementById('features-view-cards'),\n"
    "    kanban: document.getElementById('features-view-kanban'),\n"
    "    table: document.getElementById('features-view-table'),\n"
    "  };\n"
    "  function activate(view) {\n"
    "    btns.forEach(function(b) { b.classList.toggle('active', b.dataset.view === view); });\n"
    "    Object.keys(panels).forEach(function(k) {\n"
    "      if (panels[k]) panels[k].style.display = (k === view) ? '' : 'none';\n"
    "    });\n"
    "    try { localStorage.setItem('featuresView', view); } catch(e) {}\n"
    "  }\n"
    "  btns.forEach(function(b) { b.addEventListener('click', function() { activate(b.dataset.view); }); });\n"
    "  var saved; try { saved = localStorage.getItem('featuresView'); } catch(e) {}\n"
    "  activate(saved || 'cards');\n"
    "})();\n"
)


MULTI_VIEW_CSS = """
.features-view-switcher { display: inline-flex; gap: 4px; margin: 12px 0; background: #f0f0f0; border-radius: 8px; padding: 3px; }
.features-view-btn { border: 0; background: transparent; padding: 5px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; color: #555; transition: background 0.15s; }
.features-view-btn:hover { background: rgba(255,255,255,0.5); }
.features-view-btn.active { background: #fff; color: #111; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }
.features-cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 12px 0; }
.feature-card { background: #fff; border: 1px solid #e8e8e8; border-radius: 10px; padding: 12px; }
.feature-card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.feature-card-meta { min-width: 0; flex: 1; }
.feature-card-id { font-size: 11px; color: #999; line-height: 1.2; }
.feature-card-name { font-size: 13px; font-weight: 500; line-height: 1.3; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feature-card-axes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
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
@media (max-width: 640px) {
  .features-cards-grid { grid-template-columns: 1fr; }
  .features-kanban-grid { grid-template-columns: 1fr; }
}
"""
