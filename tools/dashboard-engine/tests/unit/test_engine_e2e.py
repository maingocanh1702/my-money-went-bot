"""End-to-end integration: tracker → signals → status → state_store."""

from __future__ import annotations

import json
from pathlib import Path

from work_state.models import CurrentState, Signals
from work_state.plan_reader import read_tracker
from work_state.progress import compute_progress
from work_state.state_store import read_current_state, write_current_state
from work_state.status_machine import compute_human_status, compute_status


def _collect_signals_stub(item_id: str) -> Signals:
    """Stub collector returning deterministic signals per item pattern."""
    if item_id.startswith("W"):
        return Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=10,
            last_commit_sha="aaa111",
            pr_state="merged",
            pr_number=1,
            review_state="approved",
            ci_state="pass",
            deploy_state="deployed",
            warnings=[],
        )
    return Signals(
        spec_exists=True,
        tech_exists=True,
        branch_exists=True,
        commits_count=3,
        last_commit_sha="bbb222",
        pr_state="open",
        pr_number=42,
        review_state="none",
        ci_state="none",
        deploy_state="unknown",
        warnings=["type_inferred"],
    )


def _run_engine(tracker_path: str, dashboard_dir: Path) -> list[CurrentState]:
    items = read_tracker(tracker_path)
    states: list[CurrentState] = []
    for parsed in items:
        signals = _collect_signals_stub(parsed.item.id)
        status = compute_status(signals)
        overlays: list[str] = []
        human = compute_human_status(status, overlays, signals.deploy_state)
        profile = parsed.item.progress_profile
        try:
            progress = compute_progress(signals, profile)
        except NotImplementedError:
            progress = 0
        state = CurrentState(
            item_id=parsed.item.id,
            status=status,
            human_status=human,
            progress=progress,
            runtime_urgency="normal",
            overlays=overlays,
            signals=signals,
            last_event_ts=None,
        )
        states.append(state)
    write_current_state(states, dashboard_dir)
    return states


class TestEngineE2E:
    def test_tracker_to_state_store(self, tmp_path: Path) -> None:
        fixture = Path(__file__).parent / "fixtures" / "tracker_sample.md"
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine(str(fixture), dashboard_dir)
        assert len(states) > 0

        stored = read_current_state(dashboard_dir)
        assert stored is not None
        items = stored["items"]
        assert isinstance(items, list)
        assert len(items) == len(states)

    def test_infra_items_deployed(self, tmp_path: Path) -> None:
        fixture = Path(__file__).parent / "fixtures" / "tracker_sample.md"
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine(str(fixture), dashboard_dir)
        infra = [s for s in states if s.item_id.startswith("W")]
        for s in infra:
            assert s.status == "deployed"
            assert s.human_status == "DONE"

    def test_feature_items_in_review(self, tmp_path: Path) -> None:
        fixture = Path(__file__).parent / "fixtures" / "tracker_sample.md"
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine(str(fixture), dashboard_dir)
        features = [s for s in states if not s.item_id.startswith("W")]
        for s in features:
            assert s.status == "in-review"
            assert s.human_status == "IN_PROGRESS"
            assert s.progress == 60

    def test_state_json_roundtrip(self, tmp_path: Path) -> None:
        fixture = Path(__file__).parent / "fixtures" / "tracker_sample.md"
        dashboard_dir = tmp_path / ".dashboard"

        _run_engine(str(fixture), dashboard_dir)
        raw = json.loads((dashboard_dir / "current_state.json").read_text())
        for item in raw["items"]:
            assert "item_id" in item
            assert "status" in item
            assert "signals" in item
            assert isinstance(item["signals"]["warnings"], list)

    def test_progress_computed_for_standard_feature(self, tmp_path: Path) -> None:
        fixture = Path(__file__).parent / "fixtures" / "tracker_sample.md"
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine(str(fixture), dashboard_dir)
        features = [s for s in states if not s.item_id.startswith("W")]
        assert all(s.progress == 60 for s in features)

    def test_foundation_profile_defaults_to_zero(self, tmp_path: Path) -> None:
        """Items with foundation_change profile get progress=0 (NotImplementedError)."""
        fixture = Path(__file__).parent / "fixtures" / "tracker_sample.md"
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine(str(fixture), dashboard_dir)
        infra = [s for s in states if s.item_id.startswith("W")]
        for s in infra:
            assert s.progress == 0
