"""B-2: render the 5-tab dashboard UI (Overview / Features / PRs / Risks / Docs).

All data interpolation goes through ``escape_html`` to prevent XSS — never
fold raw user-supplied strings (feature names, blocker notes, risk
mitigations) into HTML without escaping.
"""

from __future__ import annotations

import html
from typing import Any

from scripts.dashboard.render_features_multi_view import (
    render_features_cards,
    render_features_kanban,
    render_features_table_view,
)

TAB_DEFS = [
    ("overview", "Overview"),
    ("features", "Features"),
    ("prs", "PRs"),
    ("risks", "Risks"),
    ("docs", "Docs"),
]

# Staleness thresholds (days) → CSS class. Phase 5 (B-3) tightens this with
# explicit yellow/red styling; B-2 just emits the class hooks.
_STALENESS_YELLOW = 7
_STALENESS_RED = 14


def escape_html(text: Any) -> str:
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def render_tab_bar() -> str:
    btns = []
    for slug, label in TAB_DEFS:
        btns.append(
            f'<button type="button" class="tab-btn" data-tab="{slug}">{escape_html(label)}</button>'
        )
    return '<nav class="tab-bar" role="tablist">' + "".join(btns) + "</nav>"


def render_overview_tab(
    overall: dict[str, Any], phases: list[dict[str, Any]], inner_html: str = ""
) -> str:
    progress = int(overall.get("overall_progress", 0) or 0)
    mvp_pct = int(overall.get("mvp_percent", 0) or 0)
    bars: list[str] = []
    for p in phases:
        name = escape_html(p.get("name", ""))
        pct = int(p.get("progress", 0) or 0)
        status = escape_html(p.get("status", "not_started"))
        bars.append(
            f'<div class="phase-row" data-status="{status}">'
            f'<div class="phase-label">{name}</div>'
            f'<div class="phase-track"><div class="phase-fill phase-{status}" '
            f'style="width:{pct}%"></div></div>'
            f'<div class="phase-pct">{pct}%</div></div>'
        )
    return (
        f'<section id="tab-overview" class="tab-panel" role="tabpanel">'
        f'<div class="overview-summary">'
        f'<div class="kpi"><div class="kpi-label">Overall</div>'
        f'<div class="kpi-value">{progress}%</div></div>'
        f'<div class="kpi"><div class="kpi-label">MVP</div>'
        f'<div class="kpi-value">{mvp_pct}%</div></div>'
        f"</div>"
        f'<div class="phase-bars">{"".join(bars)}</div>'
        f"{inner_html}"
        f"</section>"
    )


def render_features_tab(features: list[dict[str, Any]], prefix_html: str = "") -> str:
    from scripts.dashboard.polish import (
        compute_features_summary,
        render_features_summary_header,
    )
    from scripts.dashboard.render_features_multi_view import FEATURES_VIEW_SWITCHER_JS

    summary_html = render_features_summary_header(compute_features_summary(features))
    switcher_html = (
        '<div class="features-view-switcher" role="tablist" aria-label="Features view">'
        '<button type="button" data-view="cards" class="features-view-btn" role="tab">Cards</button>'
        '<button type="button" data-view="kanban" class="features-view-btn" role="tab">Kanban</button>'
        '<button type="button" data-view="table" class="features-view-btn" role="tab">Table</button>'
        "</div>"
    )
    cards_html = render_features_cards(features)
    kanban_html = render_features_kanban(features)
    table_html = render_features_table_view(features)
    switcher_js = f"<script>\n{FEATURES_VIEW_SWITCHER_JS}</script>"
    return (
        '<section id="tab-features" class="tab-panel" role="tabpanel">'
        f"{prefix_html}"
        f"{summary_html}"
        f"{switcher_html}"
        f'<div id="features-view-cards" class="features-view-panel">{cards_html}</div>'
        f'<div id="features-view-kanban" class="features-view-panel">{kanban_html}</div>'
        f'<div id="features-view-table" class="features-view-panel">{table_html}</div>'
        f"{switcher_js}"
        "</section>"
    )


def render_prs_tab(prs_html: str) -> str:
    """PRs tab: wraps the legacy toolbar + board markup.

    ``prs_html`` is the pre-rendered toolbar (with filter buttons + search
    input already wired to the legacy filter JS) + board HTML. We do not
    add a second control row here because legacy `.filter-btn` /
    `#dashboard-search` handlers are global — duplicating them would
    desynchronize state (see B-2 Codex round 1).
    """
    return (
        '<section id="tab-prs" class="tab-panel" role="tabpanel">'
        f'<div class="prs-body">{prs_html}</div>'
        "</section>"
    )


_RISK_SLUGS = {"low": "low", "medium": "medium", "high": "high"}


def render_risks_tab(risks: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for r in risks:
        impact_raw = (r.get("impact") or "Medium").strip()
        # Slug whitelist — never concatenate raw roadmap content into a
        # class attribute (Codex B-2 round 3: prevents attribute injection
        # via quotes / whitespace payloads in upstream markdown).
        slug = _RISK_SLUGS.get(impact_raw.lower(), "medium")
        cls = "risk-" + slug
        rows.append(
            "<tr>"
            f'<td class="risk-name">{escape_html(r.get("name", ""))}</td>'
            f'<td class="risk-phase">{escape_html(r.get("phase", ""))}</td>'
            f'<td class="risk-impact {cls}">{escape_html(impact_raw)}</td>'
            f'<td class="risk-mitigation">{escape_html(r.get("mitigation", ""))}</td>'
            "</tr>"
        )
    return (
        '<section id="tab-risks" class="tab-panel" role="tabpanel">'
        '<table class="risks-table">'
        "<thead><tr>"
        "<th>Risk</th><th>Phase</th><th>Impact</th><th>Mitigation</th>"
        "</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody>'
        "</table>"
        "</section>"
    )


def _staleness_class(days: int) -> str:
    if days >= _STALENESS_RED:
        return "stale-red"
    if days >= _STALENESS_YELLOW:
        return "stale-yellow"
    return "stale-current"


def render_docs_tab(docs: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for d in docs:
        days = int(d.get("stale_days", 0) or 0)
        cls = _staleness_class(days)
        rows.append(
            f'<tr class="{cls}">'
            f'<td class="doc-name">{escape_html(d.get("name", ""))}</td>'
            f'<td class="doc-version">{escape_html(d.get("version", ""))}</td>'
            f'<td class="doc-updated">{escape_html(d.get("updated", ""))}</td>'
            f'<td class="doc-stale">{days}d</td>'
            "</tr>"
        )
    return (
        '<section id="tab-docs" class="tab-panel" role="tabpanel">'
        '<table class="docs-table">'
        "<thead><tr>"
        "<th>Document</th><th>Version</th><th>Last Updated</th><th>Staleness</th>"
        "</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody>'
        "</table>"
        "</section>"
    )


# Vanilla ES5 — keep compatible with refreshDashboardDOM re-execution path.
TAB_SWITCHER_JS = """
(function() {
  var tabs = document.querySelectorAll('.tab-bar [data-tab]');
  var panels = document.querySelectorAll('.tab-panel');
  function activate(name) {
    var found = false;
    tabs.forEach(function(t) {
      var active = t.dataset.tab === name;
      t.classList.toggle('active', active);
      if (active) found = true;
    });
    panels.forEach(function(p) { p.classList.toggle('active', p.id === 'tab-' + name); });
    if (found) {
      try { localStorage.setItem('activeTab', name); } catch (e) { /* noop */ }
    }
  }
  tabs.forEach(function(t) {
    t.addEventListener('click', function() { activate(t.dataset.tab); });
  });
  var saved = null;
  try { saved = localStorage.getItem('activeTab'); } catch (e) { /* noop */ }
  activate(saved || 'overview');
})();
"""

# Tab UI CSS. Kept inline to avoid extra HTTP fetch and to survive the
# script-safe DOM swap path from A-P1-4 (everything ships in dashboard.html).
TAB_CSS = """
.tab-bar { display: flex; gap: 4px; border-bottom: 1px solid #e0e0e0; margin: 16px 0 12px; flex-wrap: wrap; }
.tab-btn { background: none; border: none; padding: 8px 14px; cursor: pointer; font-size: 14px; color: #555; border-bottom: 2px solid transparent; }
.tab-btn.active { color: #1976d2; border-bottom-color: #1976d2; font-weight: 600; }
.tab-btn:hover { background: #f5f5f5; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.overview-summary { display: flex; gap: 24px; padding: 12px 0; }
.kpi { display: flex; flex-direction: column; }
.kpi-label { font-size: 12px; color: #777; }
.kpi-value { font-size: 28px; font-weight: 700; color: #1976d2; }
.phase-bars { display: flex; flex-direction: column; gap: 4px; padding: 8px 0; }
.phase-row { display: grid; grid-template-columns: 200px 1fr 50px; gap: 8px; align-items: center; }
.phase-label { font-size: 13px; }
.phase-track { height: 12px; background: #f3f3f3; border-radius: 3px; overflow: hidden; }
.phase-fill { height: 100%; border-radius: 3px; transition: width 200ms; }
.phase-fill.phase-done { background: #4caf50; }
.phase-fill.phase-partial { background: #2196f3; }
.phase-fill.phase-not_started { background: #bdbdbd; }
.phase-fill.phase-blocked { background: #f44336; }
.phase-fill.phase-deferred { background: #ffc107; }
.phase-pct { text-align: right; font-size: 12px; color: #555; }
.features-matrix, .risks-table, .docs-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
.features-matrix th, .risks-table th, .docs-table th { text-align: left; padding: 6px 8px; background: #fafafa; border-bottom: 1px solid #e0e0e0; }
.features-matrix td, .risks-table td, .docs-table td { padding: 6px 8px; border-bottom: 1px solid #f0f0f0; }
.status-cell { text-align: center; font-weight: 500; }
.status-done { color: #2e7d32; }
.status-partial { color: #1976d2; }
.status-not_started { color: #9e9e9e; }
.status-blocked { color: #c62828; }
.status-deferred { color: #f57c00; }
.risk-low { color: #2e7d32; font-weight: 500; }
.risk-medium { color: #f57c00; font-weight: 500; }
.risk-high { color: #c62828; font-weight: 600; }
.stale-yellow { background: #fff8e1; }
.stale-red { background: #ffebee; }
.prs-controls { display: flex; gap: 8px; padding: 8px 0; align-items: center; flex-wrap: wrap; }
.filter-btn { background: #fff; border: 1px solid #e0e0e0; padding: 4px 10px; cursor: pointer; border-radius: 4px; font-size: 12px; }
.filter-btn.active { background: #1976d2; color: #fff; border-color: #1976d2; }
.pr-search { flex: 1; min-width: 160px; padding: 4px 8px; border: 1px solid #e0e0e0; border-radius: 4px; }
@media (max-width: 640px) {
  .tab-bar { overflow-x: auto; flex-wrap: nowrap; }
  .phase-row { grid-template-columns: 110px 1fr 40px; }
  .overview-summary { gap: 12px; }
  .features-matrix, .risks-table, .docs-table { font-size: 11px; }
}
"""
