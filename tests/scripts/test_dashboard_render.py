"""B-2: 5-tab UI rendering tests — Overview/Features/PRs/Risks/Docs.

Each test compiles a fragment via the renderer and asserts shape +
XSS-safe interpolation.
"""

from __future__ import annotations

from typing import Any

from scripts.dashboard.render import (
    TAB_DEFS,
    TAB_SWITCHER_JS,
    render_docs_tab,
    render_features_tab,
    render_overview_tab,
    render_prs_tab,
    render_risks_tab,
    render_tab_bar,
)
from scripts.dashboard.render_features_multi_view import (
    _segment_class,
    group_features_by_phase,
    render_features_cards,
    render_features_kanban,
    render_features_table_view,
)


def test_render_tab_bar_5_tabs() -> None:
    html = render_tab_bar()
    for slug, label in TAB_DEFS:
        assert f'data-tab="{slug}"' in html
        assert label in html
    assert html.count("data-tab=") == 5


def test_render_overview_progress_bars() -> None:
    overall = {"overall_progress": 30, "mvp_percent": 17}
    phases = [
        {"name": "Phase 0", "status": "done", "progress": 100},
        {"name": "Phase 1", "status": "partial", "progress": 75},
        {"name": "Phase 2", "status": "not_started", "progress": 0},
    ]
    html = render_overview_tab(overall, phases)
    assert html.count("phase-row") == 3
    assert "Phase 0" in html
    assert "75%" in html
    assert 'id="tab-overview"' in html


def test_render_features_multi_view_contains_all_features() -> None:
    features = [
        {
            "id": "F01",
            "name": "Onboarding",
            "spec": "done",
            "be_tech": "done",
            "be_code": "partial",
            "bot_code": "not_started",
            "phase": "1,4",
        },
        {
            "id": "F02",
            "name": "Tx Capture",
            "spec": "done",
            "be_tech": "done",
            "be_code": "partial",
            "bot_code": "not_started",
            "phase": "1,5",
        },
    ]
    html = render_features_tab(features)
    assert "F01" in html
    assert "F02" in html
    assert "Onboarding" in html
    assert "features-view-cards" in html
    assert "features-view-kanban" in html
    assert "features-view-table" in html


def test_render_prs_tab_wraps_legacy_markup() -> None:
    # Legacy toolbar already has working filter buttons + search; the PRs
    # tab is a thin wrapper to avoid duplicating filter/search controls
    # that would desynchronize global state (B-2 Codex round 1).
    legacy = '<div class="legacy-toolbar"><button data-filter="all" class="filter-btn">All</button></div><div class="board">rows</div>'
    html = render_prs_tab(legacy)
    assert 'id="tab-prs"' in html
    assert "legacy-toolbar" in html
    assert "rows" in html
    # No duplicate controls in the wrapper itself.
    assert 'class="prs-controls"' not in html


def test_render_risks_impact_class_is_slug_whitelisted() -> None:
    """Regression for B-2 Codex round 3: never concat raw impact into class."""
    risks = [
        {
            "name": "Hostile risk",
            "phase": "9",
            "impact": 'High" onclick="alert(1)',
            "mitigation": "n/a",
        }
    ]
    html = render_risks_tab(risks)
    assert "risk-high" not in html  # raw "High..." would slug to nothing
    # Fallback for unknown impact → medium
    assert "risk-medium" in html
    # Escaped visible text contains the payload but cannot break out.
    assert "onclick" in html  # but escaped
    assert "&quot;" in html


def test_render_risks_severity_class() -> None:
    risks = [
        {"name": "Low risk", "phase": "9", "impact": "Low", "mitigation": "Monitor"},
        {"name": "Mid risk", "phase": "8", "impact": "Medium", "mitigation": "Adjust"},
        {"name": "High risk", "phase": "9", "impact": "High", "mitigation": "Pivot"},
    ]
    html = render_risks_tab(risks)
    assert "risk-low" in html
    assert "risk-medium" in html
    assert "risk-high" in html


def test_render_docs_staleness_class() -> None:
    docs = [
        {"name": "fresh.md", "version": "v1.0", "updated": "2026-05-13", "stale_days": 1},
        {"name": "yellow.md", "version": "v1.0", "updated": "2026-05-04", "stale_days": 10},
        {"name": "red.md", "version": "v1.0", "updated": "2026-04-28", "stale_days": 16},
    ]
    html = render_docs_tab(docs)
    assert "stale-current" in html
    assert "stale-yellow" in html
    assert "stale-red" in html


def test_no_xss_in_feature_name() -> None:
    features: list[dict[str, Any]] = [
        {
            "id": "F00",
            "name": '<script>alert("xss")</script>',
            "spec": "done",
            "be_tech": "done",
            "be_code": "done",
            "bot_code": "done",
            "phase": "1",
        }
    ]
    html = render_features_tab(features)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_render_features_tab_includes_progress_display() -> None:
    """Each feature should show a progress value in the multi-view cards."""
    html = render_features_tab(
        [
            {
                "id": "F01",
                "name": "Test",
                "spec": "done",
                "be_tech": "done",
                "be_code": "partial",
                "bot_code": "not_started",
                "phase": "1",
            }
        ]
    )
    assert "63%" in html


def test_render_features_tab_summary_header() -> None:
    """Summary header should render overall % + per-axis % + feature count."""
    html = render_features_tab(
        [
            {
                "id": "F01",
                "name": "A",
                "spec": "done",
                "be_tech": "done",
                "be_code": "done",
                "bot_code": "done",
                "phase": "1",
            }
        ]
    )
    assert "features-summary" in html
    assert "Overall 100%" in html
    assert "(1 features)" in html


def test_render_features_tab_has_view_switcher_buttons() -> None:
    html = render_features_tab([])
    assert 'data-view="cards"' in html
    assert 'data-view="kanban"' in html
    assert 'data-view="table"' in html


def test_localstorage_tab_init_js_present() -> None:
    assert "localStorage" in TAB_SWITCHER_JS
    assert "activeTab" in TAB_SWITCHER_JS
    # Ensure ES5 friendly (no arrow functions in the switcher body).
    assert "=>" not in TAB_SWITCHER_JS


def test_tab_switcher_lives_inside_container_in_dashboard_html() -> None:
    """Regression guard for B-2 Codex round 2.

    refreshDashboardDOM() (A-P1-4) replaces only .container — scripts
    outside it never re-execute. If the tab-switcher escapes the
    container, tab clicks die after the first auto-refresh.
    """
    from pathlib import Path

    html = (Path(__file__).resolve().parents[2] / "docs" / "dashboard.html").read_text(
        encoding="utf-8"
    )
    c_open = html.index('<div class="container">')
    c_close = html.rindex("</div>\n<script")
    sw = html.index('class="tab-switcher"')
    assert c_open < sw < c_close, "tab-switcher script must live inside .container"


# ---------- Multi-view Features tests (mega-prompt #4) ----------


SAMPLE_FEATURES_MV = [
    {
        "id": "F01",
        "name": "3-Path Onboarding",
        "spec": "done",
        "be_tech": "done",
        "be_code": "partial",
        "bot_code": "not_started",
        "phase": "1,4",
    },
    {
        "id": "F12",
        "name": "Multi-User Data Isolation",
        "spec": "done",
        "be_tech": "not_started",
        "be_code": "done",
        "bot_code": "not_started",
        "phase": "1",
    },
    {
        "id": "F16",
        "name": "P&L View",
        "spec": "not_started",
        "be_tech": "not_started",
        "be_code": "not_started",
        "bot_code": "not_started",
        "phase": "9",
    },
]


def test_group_features_by_phase_uses_first_phase() -> None:
    grouped = group_features_by_phase(SAMPLE_FEATURES_MV)
    assert 1 in grouped and 9 in grouped
    assert len(grouped[1]) == 2
    assert len(grouped[9]) == 1
    assert list(grouped.keys()) == sorted(grouped.keys())


def test_group_features_by_phase_handles_missing_phase() -> None:
    fs = [
        {
            "id": "FX",
            "name": "x",
            "spec": "done",
            "be_tech": "done",
            "be_code": "done",
            "bot_code": "done",
            "phase": "",
        }
    ]
    grouped = group_features_by_phase(fs)
    assert len(grouped) >= 1


def test_render_features_cards_includes_progress_ring() -> None:
    import html as html_mod

    rendered = render_features_cards(SAMPLE_FEATURES_MV)
    assert "<svg" in rendered
    assert "stroke-dasharray" in rendered
    for f in SAMPLE_FEATURES_MV:
        assert f["id"] in rendered
        assert html_mod.escape(f["name"]) in rendered


def test_render_features_cards_escapes_xss() -> None:
    fs: list[dict[str, Any]] = [
        {
            "id": "FXSS",
            "name": "<script>alert(1)</script>",
            "spec": "done",
            "be_tech": "done",
            "be_code": "done",
            "bot_code": "done",
            "phase": "1",
        }
    ]
    html = render_features_cards(fs)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_features_kanban_groups_by_phase() -> None:
    html = render_features_kanban(SAMPLE_FEATURES_MV)
    assert "Phase 1" in html
    assert "Phase 9" in html
    assert "F01" in html and "F12" in html and "F16" in html
    assert "kanban-bar-fill" in html


def test_render_features_table_view_has_4_segment_bar() -> None:
    html = render_features_table_view(SAMPLE_FEATURES_MV)
    assert "seg-spec" in html
    assert "seg-be_tech" in html or "seg-be-tech" in html
    assert "seg-be_code" in html or "seg-be-code" in html
    assert "seg-bot_code" in html or "seg-bot-code" in html
    for f in SAMPLE_FEATURES_MV:
        assert f["id"] in html


def test_render_features_tab_includes_view_switcher() -> None:
    html = render_features_tab(SAMPLE_FEATURES_MV)
    assert 'data-view="cards"' in html
    assert 'data-view="kanban"' in html
    assert 'data-view="table"' in html
    assert "featuresView" in html
    assert "localStorage" in html


def test_render_features_tab_renders_all_3_panels() -> None:
    html = render_features_tab(SAMPLE_FEATURES_MV)
    assert "features-view-cards" in html
    assert "features-view-kanban" in html
    assert "features-view-table" in html


def test_segment_color_class_done_partial_not_started() -> None:
    assert _segment_class("done") == "seg-done"
    assert _segment_class("partial") == "seg-partial"
    assert _segment_class("not_started") == "seg-none"
    assert _segment_class("deferred") == "seg-none"
    assert _segment_class("unknown") == "seg-none"
