"""B-3: Gantt + readiness aggregation + staleness color classes."""

from __future__ import annotations

from datetime import date
from typing import Any

from scripts.dashboard.polish import (
    compute_feature_progress,
    compute_features_summary,
    compute_readiness,
    render_gantt,
)
from scripts.dashboard.render import _staleness_class


def _phases() -> list[dict[str, Any]]:
    return [
        {
            "name": "Phase 1",
            "status": "partial",
            "start_date": "2026-05-05",
            "target_date": "2026-05-22",
        },
        {
            "name": "Phase 2",
            "status": "not_started",
            "start_date": "2026-05-22",
            "target_date": "2026-06-15",
        },
    ]


def test_gantt_renders_phase_bars() -> None:
    html = render_gantt(_phases(), date(2026, 5, 14))
    assert html.count("gantt-bar") == 2
    assert "Phase 1" in html
    assert "Phase 2" in html


def test_gantt_bar_width_proportional() -> None:
    # Phase 1 = 17 days, Phase 2 = 24 days, total = 41 days.
    html = render_gantt(_phases(), date(2026, 5, 14))
    # Phase 1 width = 17/41 ≈ 41.5%
    assert "width:41.5%" in html or "width:41.4%" in html or "width:41.46%" in html
    # Phase 2 width = 24/41 ≈ 58.5%
    assert "width:58.5%" in html or "width:58.6%" in html


def test_gantt_today_marker_present() -> None:
    html = render_gantt(_phases(), date(2026, 5, 14))
    assert "gantt-today" in html


def test_gantt_empty_phases_no_crash() -> None:
    html = render_gantt([], date(2026, 5, 14))
    assert "gantt-empty" in html


def test_readiness_aggregates_features() -> None:
    features = [
        {"spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done"},
        {"spec": "done", "be_tech": "partial", "be_code": "not_started", "bot_code": "not_started"},
    ]
    out = compute_readiness(features)
    assert out["spec"] == 100  # 2/2 done
    assert out["be_tech"] == 75  # 1.5/2 = 75
    assert out["be_code"] == 50  # 1/2 = 50
    assert out["bot_code"] == 50  # 1/2 = 50


def test_readiness_empty_features_no_zero_div() -> None:
    out = compute_readiness([])
    for key in ("spec", "be_tech", "be_code", "bot_code"):
        assert out[key] == 0


def test_staleness_yellow_at_8_days() -> None:
    assert _staleness_class(8) == "stale-yellow"


def test_staleness_red_at_15_days() -> None:
    assert _staleness_class(15) == "stale-red"


def test_staleness_current_no_color() -> None:
    assert _staleness_class(0) == "stale-current"
    assert _staleness_class(6) == "stale-current"


def test_readiness_bar_lives_inside_features_panel() -> None:
    """Regression for B-3 Codex round 1: readiness must be inside .tab-panel.

    Placing it outside leaks the bar into every other tab.
    """
    from scripts.dashboard.render import render_features_tab

    features = [{"spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done"}]
    readiness = compute_readiness(features)
    from scripts.dashboard.polish import render_readiness_bar

    html = render_features_tab(features, prefix_html=render_readiness_bar(readiness))
    panel_open = html.index('id="tab-features"')
    panel_close = html.rindex("</section>")
    readiness_pos = html.index("readiness-bar")
    assert panel_open < readiness_pos < panel_close, "readiness must be inside tab-features panel"


def test_feature_progress_all_done() -> None:
    f = {"spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done"}
    assert compute_feature_progress(f) == 100


def test_feature_progress_all_not_started() -> None:
    f = {
        "spec": "not_started",
        "be_tech": "not_started",
        "be_code": "not_started",
        "bot_code": "not_started",
    }
    assert compute_feature_progress(f) == 0


def test_feature_progress_mixed_f01_like() -> None:
    # F01: spec=done, be_tech=done, be_code=partial, bot_code=not_started
    # → (1 + 1 + 0.5 + 0) / 4 = 0.625 → 63%
    f = {"spec": "done", "be_tech": "done", "be_code": "partial", "bot_code": "not_started"}
    assert compute_feature_progress(f) == 63


def test_feature_progress_missing_axes_treated_as_not_started() -> None:
    f = {"spec": "done"}  # other axes missing → 25%
    assert compute_feature_progress(f) == 25


def test_feature_progress_deferred_counts_as_zero() -> None:
    f = {"spec": "deferred", "be_tech": "done", "be_code": "not_started", "bot_code": "not_started"}
    # deferred=0, done=1, rest=0 → 25%
    assert compute_feature_progress(f) == 25


def test_features_summary_empty() -> None:
    s = compute_features_summary([])
    assert s == {"overall": 0, "spec": 0, "be_tech": 0, "be_code": 0, "bot_code": 0, "count": 0}


def test_features_summary_aggregates_per_axis() -> None:
    fs = [
        {"spec": "done", "be_tech": "done", "be_code": "done", "bot_code": "done"},  # 100
        {
            "spec": "done",
            "be_tech": "done",
            "be_code": "partial",
            "bot_code": "not_started",
        },  # 63
        {
            "spec": "not_started",
            "be_tech": "not_started",
            "be_code": "not_started",
            "bot_code": "not_started",
        },  # 0
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


def test_division_by_zero_guarded() -> None:
    # Same-day phase (start == end) should not crash.
    phases = [
        {
            "name": "Empty",
            "status": "planned",
            "start_date": "2026-05-14",
            "target_date": "2026-05-14",
        }
    ]
    html = render_gantt(phases, date(2026, 5, 14))
    assert "gantt-bar" in html
