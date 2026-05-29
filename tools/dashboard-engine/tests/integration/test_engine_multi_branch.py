"""Integration tests for AC11d — multi-branch aggregation matrix.

Tests spec §4.1.2 example matrix: MIN-progressed base + UNION overlays +
partial-progress detection per rules.
"""

from __future__ import annotations

from pathlib import Path

from work_state.models import Signals
from work_state.status_machine import (
    aggregate_multi_branch_overlays,
    aggregate_multi_branch_status,
    compute_human_status,
    compute_status,
)


def _make_signals(
    *,
    pr_state: str = "none",
    review_state: str = "none",
    ci_state: str = "unknown",
    deploy_state: str = "unknown",
) -> Signals:
    return Signals(
        spec_exists=True,
        tech_exists=True,
        branch_exists=True,
        commits_count=5,
        last_commit_sha="abc123",
        pr_state=pr_state,
        pr_number=1,
        review_state=review_state,
        ci_state=ci_state,
        deploy_state=deploy_state,
        warnings=[],
    )


class TestMultiBranchAggregationMatrix:
    """Spec §4.1.2 example matrix — 7 cases."""

    def test_deployed_plus_in_review_ci_failing(self) -> None:
        """deployed + (in-review + ci-failing) → base in-review, overlays {ci-failing, partial-progress}."""
        branch_a = _make_signals(deploy_state="deployed", pr_state="merged")
        branch_b = _make_signals(pr_state="open", review_state="none", ci_state="failure")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)
        assert status_a == "deployed"
        assert status_b == "in-review"

        data = [
            (status_a, []),
            (status_b, ["ci-failing"]),
        ]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "in-review"
        assert "ci-failing" in overlays
        assert "partial-progress" in overlays

    def test_merged_plus_changes_requested(self) -> None:
        """merged + changes-requested → base changes-requested, overlays {partial-progress}."""
        branch_a = _make_signals(pr_state="merged")
        branch_b = _make_signals(pr_state="open", review_state="changes-requested")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)
        assert status_a == "merged"
        assert status_b == "changes-requested"

        data: list[tuple[str, list[str]]] = [(status_a, []), (status_b, [])]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "changes-requested"
        assert "partial-progress" in overlays

    def test_deployed_plus_merged_deploy_failed(self) -> None:
        """deployed + (merged + deploy-failed) → base merged, overlays {deploy-failed, partial-progress}."""
        branch_a = _make_signals(deploy_state="deployed", pr_state="merged")
        branch_b = _make_signals(pr_state="merged", deploy_state="deploy-failed")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)
        assert status_a == "deployed"
        assert status_b == "merged"

        data = [
            (status_a, []),
            (status_b, ["deploy-failed"]),
        ]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "merged"
        assert "deploy-failed" in overlays
        assert "partial-progress" in overlays

    def test_blocked_in_progress_plus_merged(self) -> None:
        """(blocked + in-progress) + merged → base in-progress, overlays {blocked, partial-progress}."""
        branch_a_signals = _make_signals(pr_state="draft")
        branch_b_signals = _make_signals(pr_state="merged")

        status_a = compute_status(branch_a_signals)
        status_b = compute_status(branch_b_signals)
        assert status_a == "in-progress"
        assert status_b == "merged"

        data = [
            (status_a, ["blocked"]),
            (status_b, []),
        ]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "in-progress"
        assert "blocked" in overlays
        assert "partial-progress" in overlays

    def test_both_deployed_no_partial(self) -> None:
        """deployed + deployed → base deployed, no partial-progress."""
        branch_a = _make_signals(deploy_state="deployed", pr_state="merged")
        branch_b = _make_signals(deploy_state="deployed", pr_state="merged")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)
        assert status_a == "deployed"
        assert status_b == "deployed"

        data: list[tuple[str, list[str]]] = [(status_a, []), (status_b, [])]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "deployed"
        assert "partial-progress" not in overlays

    def test_both_in_progress_no_partial(self) -> None:
        """2 branches both in-progress → no partial-progress (active multi-branch)."""
        branch_a = _make_signals(pr_state="draft")
        branch_b = _make_signals(pr_state="draft")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)
        assert status_a == "in-progress"
        assert status_b == "in-progress"

        data: list[tuple[str, list[str]]] = [(status_a, []), (status_b, [])]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "in-progress"
        assert "partial-progress" not in overlays

    def test_abandoned_plus_in_progress_partial(self) -> None:
        """1 abandoned + 1 in-progress → partial-progress (asymmetric terminal)."""
        branch_a = _make_signals(pr_state="closed")
        branch_b = _make_signals(pr_state="draft")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)
        assert status_a == "abandoned"
        assert status_b == "in-progress"

        data: list[tuple[str, list[str]]] = [(status_a, []), (status_b, [])]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)

        assert base == "in-progress"
        assert "partial-progress" in overlays


class TestMultiBranchAllAbandoned:
    def test_all_abandoned_returns_abandoned(self) -> None:
        data: list[tuple[str, list[str]]] = [("abandoned", []), ("abandoned", [])]
        base = aggregate_multi_branch_status([s for s, _ in data])
        assert base == "abandoned"


class TestMultiBranchHumanStatus:
    def test_partial_progress_with_ci_failing_is_failing(self) -> None:
        overlays = ["ci-failing", "partial-progress"]
        human = compute_human_status("in-review", overlays, "unknown")
        assert human == "FAILING"

    def test_partial_progress_alone_is_in_progress(self) -> None:
        overlays = ["partial-progress"]
        human = compute_human_status("in-progress", overlays, "unknown")
        assert human == "IN_PROGRESS"


class TestMultiBranchViaEngine:
    """End-to-end: engine processes work items from tracker."""

    def test_engine_single_branch_from_tracker(self, tmp_path: Path) -> None:
        tracker = tmp_path / "tracker.md"
        tracker.write_text(
            "### Phase 2\n"
            "| PR | Wave | Feature | Status | Branch | Gates | Notes |\n"
            "|---|---|---|---|---|---|---|\n"
            "| W0.7 | W0 | Test merged | ✅ | `feat/branch-a` | 🔒X | merged |\n"
            "| W0.8 | W0 | Test open | 🟡 | `feat/branch-b` | 🔒X | open |\n",
            encoding="utf-8",
        )
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(tracker),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert len(states) == 2
        assert all(s.item_id in {"W0.7", "W0.8"} for s in states)

    def test_engine_multi_branch_path_via_mock(self, tmp_path: Path) -> None:
        """Verify engine's multi-branch aggregation path fires with >1 branch."""
        from unittest.mock import patch as mock_patch

        from work_state.engine import run_engine
        from work_state.models import WorkItem
        from work_state.plan_reader import ParsedWorkItem

        multi_branch_item = WorkItem(
            id="test-multi",
            linear_id=None,
            feature_id="test-multi",
            title="Multi-branch test",
            type="feature",
            phase="2",
            priority="P1",
            risk_tier="P1",
            lane="Standard",
            owner="founder",
            deadline=None,
            specs={"product": None, "tech": None},
            branches=["feat/branch-a", "feat/branch-b"],
            acceptance=[],
            dependencies=[],
            external_blockers=[],
            decision_needed=None,
            progress_profile="standard_feature",
        )

        fake_tracker = tmp_path / "tracker.md"
        fake_tracker.write_text("# placeholder", encoding="utf-8")

        with mock_patch(
            "work_state.engine.read_tracker",
            return_value=[ParsedWorkItem(item=multi_branch_item)],
        ):
            states = run_engine(
                tracker_path=str(fake_tracker),
                dashboard_dir=tmp_path / ".dashboard",
                no_network=True,
            )

        assert len(states) == 1
        assert states[0].item_id == "test-multi"
        assert isinstance(states[0].overlays, list)
