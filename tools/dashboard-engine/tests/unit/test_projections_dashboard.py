"""Tests for projections/dashboard.py — Phase 1b' per spec §10 + AC5/AC6/AC10/AC11a."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from work_state.models import CurrentState, Signals


def _make_signals(**overrides: object) -> Signals:
    defaults: dict[str, object] = {
        "spec_exists": True,
        "tech_exists": True,
        "branch_exists": True,
        "commits_count": 10,
        "last_commit_sha": "abc123",
        "pr_state": "open",
        "pr_number": 42,
        "review_state": "none",
        "ci_state": "pass",
        "deploy_state": "unknown",
        "warnings": [],
    }
    defaults.update(overrides)
    return Signals(**defaults)  # type: ignore[arg-type]


def _make_current_state(
    item_id: str = "onboarding-start",
    **overrides: object,
) -> CurrentState:
    defaults: dict[str, object] = {
        "item_id": item_id,
        "status": "in-review",
        "human_status": "IN_PROGRESS",
        "progress": 60,
        "runtime_urgency": "normal",
        "overlays": [],
        "signals": _make_signals(),
        "last_event_ts": "2026-05-19T08:00:00Z",
    }
    defaults.update(overrides)
    return CurrentState(**defaults)  # type: ignore[arg-type]


def _write_state_json(dashboard_dir: Path, states: list[CurrentState]) -> None:
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    state_file = dashboard_dir / "current_state.json"
    data = {"items": [asdict(s) for s in states]}
    state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _make_dashboard_json(feature_ids: list[str]) -> dict[str, object]:
    features = []
    for fid in feature_ids:
        features.append(
            {
                "be_code": "partial",
                "be_tech": "done",
                "bot_code": "not_started",
                "id": fid,
                "name": f"Feature {fid}",
                "phase": "1",
                "spec": "done",
            }
        )
    return {
        "features": features,
        "generated_at": "2026-05-20T10:00:00Z",
        "overall": {"progress": 50},
    }


class TestLoadState:
    def test_returns_none_when_dashboard_dir_missing(self, tmp_path: Path) -> None:
        from work_state.projections.dashboard import load_state

        result = load_state(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        from work_state.projections.dashboard import load_state

        dashboard_dir = tmp_path / ".dashboard"
        dashboard_dir.mkdir()
        result = load_state(dashboard_dir)
        assert result is None

    def test_returns_dict_when_valid(self, tmp_path: Path) -> None:
        from work_state.projections.dashboard import load_state

        dashboard_dir = tmp_path / ".dashboard"
        _write_state_json(dashboard_dir, [_make_current_state()])
        result = load_state(dashboard_dir)
        assert result is not None
        assert "items" in result

    def test_returns_none_on_malformed_json(self, tmp_path: Path) -> None:
        from work_state.projections.dashboard import load_state

        dashboard_dir = tmp_path / ".dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        (dashboard_dir / "current_state.json").write_text("{invalid json")
        result = load_state(dashboard_dir)
        assert result is None


class TestBuildStateBlock:
    def test_shape_matches_spec_ac5(self) -> None:
        from work_state.projections.dashboard import build_state_block

        state_item = asdict(_make_current_state())
        block = build_state_block(state_item)

        expected_keys = {
            "computed_status",
            "human_status",
            "pr_state",
            "ci_state",
            "review_state",
            "deploy_state",
            "overlays",
            "last_event_ts",
            "urgency",
            "urgency_emoji",
        }
        assert set(block.keys()) == expected_keys

    def test_values_propagated_correctly(self) -> None:
        from work_state.projections.dashboard import build_state_block

        state = _make_current_state(
            status="in-review",
            human_status="IN_PROGRESS",
            overlays=["stale", "ci-running"],
            last_event_ts="2026-05-20T12:00:00Z",
        )
        state_item = asdict(state)
        block = build_state_block(state_item)

        assert block["computed_status"] == "in-review"
        assert block["human_status"] == "IN_PROGRESS"
        assert block["pr_state"] == "open"
        assert block["ci_state"] == "pass"
        assert block["review_state"] == "none"
        assert block["deploy_state"] == "unknown"
        assert block["overlays"] == ["stale", "ci-running"]
        assert block["last_event_ts"] == "2026-05-20T12:00:00Z"

    def test_overlays_propagated_from_currentstate_ac10(self) -> None:
        from work_state.projections.dashboard import build_state_block

        overlays = ["blocked", "ci-failing", "stale"]
        state_item = asdict(_make_current_state(overlays=overlays))
        block = build_state_block(state_item)
        assert block["overlays"] == overlays

    def test_human_status_rendered_ac11a(self) -> None:
        from work_state.projections.dashboard import build_state_block

        for human in [
            "BACKLOG",
            "TODO",
            "IN_PROGRESS",
            "WAITING",
            "FAILING",
            "BLOCKED",
            "DONE",
            "ABANDONED",
            "UNKNOWN",
        ]:
            state_item = asdict(_make_current_state(human_status=human))
            block = build_state_block(state_item)
            assert block["human_status"] == human


class TestEnrichDashboard:
    def test_adds_state_block_per_feature_row(self) -> None:
        from work_state.projections.dashboard import enrich_dashboard

        dashboard = _make_dashboard_json(["onboarding-start"])
        state_data = {"items": [asdict(_make_current_state("onboarding-start"))]}
        result = enrich_dashboard(dashboard, state_data)

        features = result["features"]
        assert isinstance(features, list)
        assert "state" in features[0]

    def test_preserves_existing_fields_ac6(self) -> None:
        from work_state.projections.dashboard import enrich_dashboard

        dashboard = _make_dashboard_json(["onboarding-start"])
        features_list = dashboard["features"]
        assert isinstance(features_list, list)
        original_feature = dict(features_list[0])
        state_data = {"items": [asdict(_make_current_state("onboarding-start"))]}
        result = enrich_dashboard(dashboard, state_data)

        result_features = result["features"]
        assert isinstance(result_features, list)
        enriched_feature = result_features[0]
        for key in original_feature:
            assert enriched_feature[key] == original_feature[key]

    def test_skips_features_without_matching_state(self) -> None:
        from work_state.projections.dashboard import enrich_dashboard

        dashboard = _make_dashboard_json(["onboarding-start", "categorization"])
        state_data = {"items": [asdict(_make_current_state("onboarding-start"))]}
        result = enrich_dashboard(dashboard, state_data)

        features = result["features"]
        assert isinstance(features, list)
        assert "state" in features[0]
        assert "state" not in features[1]

    def test_returns_unchanged_when_state_none(self) -> None:
        from work_state.projections.dashboard import enrich_dashboard

        dashboard = _make_dashboard_json(["onboarding-start"])
        result = enrich_dashboard(dashboard, None)
        features = result["features"]
        assert isinstance(features, list)
        assert "state" not in features[0]

    def test_idempotent_run_twice(self, tmp_path: Path) -> None:
        from work_state.projections.dashboard import enrich_dashboard

        dashboard = _make_dashboard_json(["onboarding-start"])
        state_data = {"items": [asdict(_make_current_state("onboarding-start"))]}

        result1 = enrich_dashboard(dashboard, state_data)
        output1 = json.dumps(result1, indent=2, ensure_ascii=False)

        result2 = enrich_dashboard(json.loads(output1), state_data)
        output2 = json.dumps(result2, indent=2, ensure_ascii=False)

        assert output1 == output2

    def test_multiple_features_enriched(self) -> None:
        from work_state.projections.dashboard import enrich_dashboard

        dashboard = _make_dashboard_json(["feat-a", "feat-b"])
        states = [
            asdict(_make_current_state("feat-a", status="in-review")),
            asdict(_make_current_state("feat-b", status="merged")),
        ]
        state_data = {"items": states}
        result = enrich_dashboard(dashboard, state_data)

        features = result["features"]
        assert isinstance(features, list)
        assert features[0]["state"]["computed_status"] == "in-review"
        assert features[1]["state"]["computed_status"] == "merged"


class TestProjectionHandlesUnknownSignals:
    def test_unknown_ci_state_renders_as_unknown(self) -> None:
        from work_state.projections.dashboard import build_state_block

        state_item = asdict(_make_current_state(signals=_make_signals(ci_state="unknown_value")))
        block = build_state_block(state_item)
        assert block["ci_state"] == "unknown_value"

    def test_unknown_deploy_state_renders(self) -> None:
        from work_state.projections.dashboard import build_state_block

        state_item = asdict(_make_current_state(signals=_make_signals(deploy_state="unknown")))
        block = build_state_block(state_item)
        assert block["deploy_state"] == "unknown"


class TestNoNetworkMode:
    def test_uses_cached_state_only(self, tmp_path: Path) -> None:
        from work_state.projections.dashboard import load_state

        dashboard_dir = tmp_path / ".dashboard"
        _write_state_json(dashboard_dir, [_make_current_state()])
        result = load_state(dashboard_dir)
        assert result is not None
        items = result["items"]
        assert isinstance(items, list)
        assert len(items) == 1
