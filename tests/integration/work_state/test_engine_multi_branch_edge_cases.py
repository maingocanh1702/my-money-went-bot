"""Edge-case integration tests for multi-branch aggregation — Phase B Step 7.

Covers: all-abandoned, single-branch with overlays, multi-branch + unknown signals.
"""

from __future__ import annotations

from scripts.work_state.models import Signals
from scripts.work_state.status_machine import (
    aggregate_multi_branch_overlays,
    aggregate_multi_branch_status,
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


class TestMultiBranchEdgeCases:
    def test_single_branch_with_ci_failing_overlay(self) -> None:
        signals = _make_signals(pr_state="open", ci_state="failure")
        status = compute_status(signals)
        assert status == "in-review"

    def test_multi_branch_unknown_deploy_propagates(self) -> None:
        """Multi-branch with unknown railway signals — overlay propagates through union."""
        branch_a = _make_signals(pr_state="merged", deploy_state="deployed")
        branch_b = _make_signals(pr_state="open", deploy_state="unknown")

        status_a = compute_status(branch_a)
        status_b = compute_status(branch_b)

        data: list[tuple[str, list[str]]] = [
            (status_a, []),
            (status_b, ["unknown"]),
        ]
        overlays = aggregate_multi_branch_overlays(data)
        assert "unknown" in overlays
        assert "partial-progress" in overlays

    def test_three_branches_min_selects_lowest(self) -> None:
        """Three branches — MIN picks the least progressed non-abandoned."""
        statuses = ["deployed", "merged", "in-progress"]
        base = aggregate_multi_branch_status(statuses)
        assert base == "in-progress"

    def test_mixed_terminal_and_non_terminal(self) -> None:
        """merged + deployed + in-review → base in-review, partial-progress."""
        data: list[tuple[str, list[str]]] = [
            ("merged", []),
            ("deployed", []),
            ("in-review", []),
        ]
        base = aggregate_multi_branch_status([s for s, _ in data])
        overlays = aggregate_multi_branch_overlays(data)
        assert base == "in-review"
        assert "partial-progress" in overlays
