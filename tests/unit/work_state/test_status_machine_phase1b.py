"""Tests for status_machine Phase 1b — verify PR/CI/review/deploy priority cases per spec §8.1.

Phase 1a already implemented the full priority chain. These tests verify
the specific Phase 1b signal combinations work correctly with the new
Signals fields (pr_url, ci_check_run_count, last_review_at, last_deploy_at).
"""

from __future__ import annotations

from scripts.work_state.models import Signals
from scripts.work_state.status_machine import compute_human_status, compute_status


def _make_signals(**overrides: object) -> Signals:
    defaults: dict[str, object] = {
        "spec_exists": True,
        "tech_exists": True,
        "branch_exists": True,
        "commits_count": 5,
        "last_commit_sha": "abc123",
        "pr_state": "none",
        "pr_number": None,
        "review_state": "none",
        "ci_state": "none",
        "deploy_state": "unknown",
        "warnings": [],
        "pr_url": None,
        "ci_check_run_count": 0,
        "last_review_at": None,
        "last_deploy_at": None,
    }
    defaults.update(overrides)
    return Signals(**defaults)  # type: ignore[arg-type]


class TestPhase1bStatusWithNewFields:
    """Verify status computation works with Phase 1b extended Signals."""

    def test_deployed_with_last_deploy_at(self) -> None:
        s = _make_signals(
            deploy_state="deployed",
            pr_state="merged",
            last_deploy_at="2026-05-20T12:00:00Z",
        )
        assert compute_status(s) == "deployed"

    def test_deploying_with_last_deploy_at(self) -> None:
        s = _make_signals(
            deploy_state="deploying",
            last_deploy_at="2026-05-20T14:00:00Z",
        )
        assert compute_status(s) == "deploying"

    def test_deploy_failed_overlay_with_merged(self) -> None:
        s = _make_signals(
            deploy_state="deploy-failed",
            pr_state="merged",
        )
        assert compute_status(s) == "merged"
        human = compute_human_status("merged", ["deploy-failed"], "deploy-failed")
        assert human == "FAILING"

    def test_open_pr_ci_failing_overlay(self) -> None:
        s = _make_signals(
            pr_state="open",
            pr_number=42,
            pr_url="https://github.com/org/repo/pull/42",
            ci_state="failure",
            ci_check_run_count=3,
        )
        assert compute_status(s) == "in-review"
        human = compute_human_status("in-review", ["ci-failing"], s.deploy_state)
        assert human == "FAILING"

    def test_open_pr_approved_with_review_at(self) -> None:
        s = _make_signals(
            pr_state="open",
            pr_number=42,
            review_state="approved",
            last_review_at="2026-05-19T12:00:00Z",
        )
        assert compute_status(s) == "approved-pending-merge"

    def test_open_pr_changes_requested_with_review_at(self) -> None:
        s = _make_signals(
            pr_state="open",
            pr_number=42,
            review_state="changes-requested",
            last_review_at="2026-05-19T10:00:00Z",
        )
        assert compute_status(s) == "changes-requested"

    def test_draft_pr_with_url(self) -> None:
        s = _make_signals(
            pr_state="draft",
            pr_number=50,
            pr_url="https://github.com/org/repo/pull/50",
        )
        assert compute_status(s) == "in-progress"

    def test_merged_pr_with_url(self) -> None:
        s = _make_signals(
            pr_state="merged",
            pr_number=10,
            pr_url="https://github.com/org/repo/pull/10",
        )
        assert compute_status(s) == "merged"

    def test_closed_pr_abandoned(self) -> None:
        s = _make_signals(
            pr_state="closed",
            pr_number=99,
            pr_url="https://github.com/org/repo/pull/99",
        )
        assert compute_status(s) == "abandoned"

    def test_ci_success_with_check_count(self) -> None:
        s = _make_signals(
            pr_state="open",
            ci_state="pass",
            ci_check_run_count=4,
            review_state="none",
        )
        assert compute_status(s) == "in-review"

    def test_unknown_pr_state(self) -> None:
        s = _make_signals(pr_state="unknown")
        assert compute_status(s) == "in-progress"

    def test_ambiguous_pr_mapping_overlay(self) -> None:
        s = _make_signals(
            pr_state="unknown",
            warnings=["ambiguous_pr_mapping"],
        )
        human = compute_human_status(compute_status(s), ["ambiguous-pr-mapping"], s.deploy_state)
        assert human == "UNKNOWN"


class TestPhase1bHumanStatusCombinations:
    """Edge cases for Phase 1b human status with deploy/CI overlays."""

    def test_merged_deploy_unknown_is_waiting(self) -> None:
        assert compute_human_status("merged", [], "unknown") == "WAITING"

    def test_merged_deploy_not_applicable_is_done(self) -> None:
        assert compute_human_status("merged", [], "not-applicable") == "DONE"

    def test_deployed_is_done(self) -> None:
        assert compute_human_status("deployed", [], "deployed") == "DONE"

    def test_ci_failing_dominates_review_requested(self) -> None:
        result = compute_human_status("in-review", ["ci-failing", "review-requested"], "unknown")
        assert result == "FAILING"

    def test_blocked_dominates_deploy_failed(self) -> None:
        result = compute_human_status("merged", ["blocked", "deploy-failed"], "deploy-failed")
        assert result == "BLOCKED"
