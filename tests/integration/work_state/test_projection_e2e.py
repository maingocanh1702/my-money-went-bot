"""Integration e2e — projection pipeline: collectors → state_store → projection → dashboard.json.

Uses cached fixtures (no network). Validates AC5 (state block in output),
AC6 (existing fields preserved), idempotency on re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.work_state.models import CurrentState, Signals
from scripts.work_state.projections.dashboard import enrich_dashboard, load_state, main
from scripts.work_state.state_store import write_current_state


def _make_signals(pr_state: str = "open", ci_state: str = "pass") -> Signals:
    return Signals(
        spec_exists=True,
        tech_exists=True,
        branch_exists=True,
        commits_count=5,
        last_commit_sha="abc123",
        pr_state=pr_state,
        pr_number=42,
        review_state="none",
        ci_state=ci_state,
        deploy_state="unknown",
        warnings=[],
    )


def _make_state(item_id: str, status: str = "in-review") -> CurrentState:
    return CurrentState(
        item_id=item_id,
        status=status,
        human_status="IN_PROGRESS",
        progress=60,
        runtime_urgency="normal",
        overlays=[],
        signals=_make_signals(),
        last_event_ts="2026-05-20T08:00:00Z",
    )


def _make_dashboard(feature_ids: list[str]) -> dict[str, object]:
    features = [
        {
            "be_code": "partial",
            "be_tech": "done",
            "bot_code": "not_started",
            "id": fid,
            "name": f"Feature {fid}",
            "phase": "1",
            "spec": "done",
        }
        for fid in feature_ids
    ]
    return {
        "features": features,
        "generated_at": "2026-05-20T10:00:00Z",
        "overall": {"progress": 50},
    }


class TestProjectionE2EPipeline:
    def test_collectors_to_state_to_projection(self, tmp_path: Path) -> None:
        dashboard_dir = tmp_path / ".dashboard"
        states = [
            _make_state("onboarding-start", "in-review"),
            _make_state("transaction-capture", "merged"),
        ]
        write_current_state(states, dashboard_dir)

        state_data = load_state(dashboard_dir)
        assert state_data is not None

        dashboard = _make_dashboard(["onboarding-start", "transaction-capture"])
        result = enrich_dashboard(dashboard, state_data)

        features = result["features"]
        assert isinstance(features, list)
        assert len(features) == 2

        for feat in features:
            assert isinstance(feat, dict)
            assert "state" in feat
            block = feat["state"]
            assert isinstance(block, dict)
            assert "computed_status" in block
            assert "human_status" in block
            assert "overlays" in block

        assert features[0]["state"]["computed_status"] == "in-review"
        assert features[1]["state"]["computed_status"] == "merged"

    def test_idempotent_on_rerun(self, tmp_path: Path) -> None:
        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state("feat-a")], dashboard_dir)
        state_data = load_state(dashboard_dir)

        dashboard = _make_dashboard(["feat-a"])
        result1 = enrich_dashboard(dashboard, state_data)
        out1 = json.dumps(result1, indent=2, ensure_ascii=False)

        result2 = enrich_dashboard(json.loads(out1), state_data)
        out2 = json.dumps(result2, indent=2, ensure_ascii=False)

        assert out1 == out2

    def test_existing_fields_preserved(self, tmp_path: Path) -> None:
        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state("onboarding-start")], dashboard_dir)
        state_data = load_state(dashboard_dir)

        dashboard = _make_dashboard(["onboarding-start"])
        result = enrich_dashboard(dashboard, state_data)

        features = result["features"]
        assert isinstance(features, list)
        feat = features[0]
        assert isinstance(feat, dict)
        assert feat["be_code"] == "partial"
        assert feat["be_tech"] == "done"
        assert feat["id"] == "onboarding-start"
        assert "state" in feat


class TestProjectionCLI:
    def test_main_cli_enriches_output(self, tmp_path: Path) -> None:
        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state("onboarding-start")], dashboard_dir)

        output_path = tmp_path / "dashboard.json"
        dashboard = _make_dashboard(["onboarding-start"])
        output_path.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")

        rc = main(
            [
                "--output",
                str(output_path),
                "--dashboard-dir",
                str(dashboard_dir),
                "--no-network",
            ]
        )
        assert rc == 0

        result = json.loads(output_path.read_text())
        features = result["features"]
        assert "state" in features[0]

    def test_main_cli_no_state_still_succeeds(self, tmp_path: Path) -> None:
        output_path = tmp_path / "dashboard.json"
        dashboard = _make_dashboard(["onboarding-start"])
        output_path.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")

        rc = main(
            [
                "--output",
                str(output_path),
                "--dashboard-dir",
                str(tmp_path / "empty"),
                "--no-network",
            ]
        )
        assert rc == 0

        result = json.loads(output_path.read_text())
        assert "state" not in result["features"][0]

    def test_main_cli_idempotent_output(self, tmp_path: Path) -> None:
        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state("feat-a")], dashboard_dir)

        output_path = tmp_path / "dashboard.json"
        dashboard = _make_dashboard(["feat-a"])
        output_path.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")

        main(["--output", str(output_path), "--dashboard-dir", str(dashboard_dir)])
        content1 = output_path.read_text()

        main(["--output", str(output_path), "--dashboard-dir", str(dashboard_dir)])
        content2 = output_path.read_text()

        assert content1 == content2
