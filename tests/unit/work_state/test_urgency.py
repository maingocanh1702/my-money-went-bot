"""Tests for derive_urgency per spec §9.4.1 — first-match-wins algorithm.

Each tier has ≥3 cases: positive, boundary, negative.
Doc-change overlays (MYM-7) don't promote urgency by themselves.
"""

from __future__ import annotations

from scripts.work_state.status_machine import (
    URGENCY_ORDER,
    aggregate_multi_branch_urgency,
    derive_urgency,
)


class TestUrgencyOrder:
    def test_order_values(self) -> None:
        assert URGENCY_ORDER == {
            "normal": 0,
            "warning": 1,
            "elevated": 2,
            "critical": 3,
        }


class TestCriticalTier:
    def test_critical_when_deploy_failed(self) -> None:
        assert derive_urgency("deployed", ["deploy-failed"], "P2", "P2") == "critical"

    def test_critical_when_deployed_plus_unknown_plus_p0_risk(self) -> None:
        assert derive_urgency("deployed", ["unknown"], "P2", "P0") == "critical"

    def test_critical_when_deployed_plus_unknown_plus_p1_risk(self) -> None:
        assert derive_urgency("deployed", ["unknown"], "P2", "P1") == "critical"

    def test_not_critical_when_deployed_plus_unknown_plus_p2_risk(self) -> None:
        result = derive_urgency("deployed", ["unknown"], "P2", "P2")
        assert result != "critical"
        assert result == "warning"

    def test_critical_when_merged_plus_ci_failing(self) -> None:
        assert derive_urgency("merged", ["ci-failing"], "P1", "P1") == "critical"


class TestElevatedTier:
    def test_elevated_when_blocked_plus_p0(self) -> None:
        assert derive_urgency("in-progress", ["blocked"], "P0", "P0") == "elevated"

    def test_elevated_when_blocked_plus_p1(self) -> None:
        assert derive_urgency("in-progress", ["blocked"], "P1", "P1") == "elevated"

    def test_not_elevated_when_blocked_plus_p2(self) -> None:
        result = derive_urgency("in-progress", ["blocked"], "P2", "P2")
        assert result != "elevated"
        assert result == "warning"

    def test_elevated_when_ci_failing_in_review(self) -> None:
        assert derive_urgency("in-review", ["ci-failing"], "P1", "P1") == "elevated"

    def test_elevated_when_approved_pending_merge_plus_stale(self) -> None:
        assert derive_urgency("approved-pending-merge", ["stale"], "P1", "P1") == "elevated"

    def test_elevated_when_ambiguous_pr_mapping(self) -> None:
        assert derive_urgency("in-progress", ["ambiguous-pr-mapping"], "P2", "P2") == "elevated"


class TestWarningTier:
    def test_warning_when_blocked_plus_p2(self) -> None:
        assert derive_urgency("in-progress", ["blocked"], "P2", "P2") == "warning"

    def test_warning_when_stale_alone(self) -> None:
        assert derive_urgency("in-progress", ["stale"], "P2", "P2") == "warning"

    def test_warning_when_unknown_alone(self) -> None:
        assert derive_urgency("in-progress", ["unknown"], "P2", "P2") == "warning"

    def test_warning_when_artifact_drift(self) -> None:
        assert derive_urgency("in-progress", ["artifact-drift"], "P2", "P2") == "warning"

    def test_warning_when_cache_warmup(self) -> None:
        assert derive_urgency("branch-created", ["cache-warmup"], "P2", "P2") == "warning"


class TestNormalTier:
    def test_normal_when_no_overlays(self) -> None:
        assert derive_urgency("in-progress", [], "P2", "P2") == "normal"

    def test_normal_when_only_review_requested(self) -> None:
        assert derive_urgency("in-review", ["review-requested"], "P2", "P2") == "normal"

    def test_normal_when_in_progress_clean(self) -> None:
        assert derive_urgency("in-progress", [], "P1", "P0") == "normal"


class TestDocChangeOverlaysNoPromotion:
    """Doc-change overlays (MYM-7) do NOT trigger urgency promotion by themselves."""

    def test_normal_when_only_spec_modified(self) -> None:
        assert derive_urgency("in-progress", ["spec-modified"], "P1", "P1") == "normal"

    def test_normal_when_only_tech_modified(self) -> None:
        assert derive_urgency("in-progress", ["tech-modified"], "P2", "P2") == "normal"

    def test_normal_when_only_tracker_modified(self) -> None:
        assert derive_urgency("in-progress", ["tracker-modified"], "P1", "P1") == "normal"

    def test_normal_when_post_ship_doc_change_alone(self) -> None:
        assert derive_urgency("deployed", ["post-ship-doc-change"], "P1", "P1") == "normal"


class TestFrozensetInput:
    """derive_urgency accepts both list[str] and frozenset[str]."""

    def test_frozenset_overlays(self) -> None:
        assert derive_urgency("deployed", frozenset(["deploy-failed"]), "P2", "P2") == "critical"

    def test_empty_frozenset(self) -> None:
        assert derive_urgency("in-progress", frozenset(), "P2", "P2") == "normal"


class TestAggregateMultiBranchUrgency:
    def test_empty_list(self) -> None:
        assert aggregate_multi_branch_urgency([]) == "normal"

    def test_single_normal(self) -> None:
        assert aggregate_multi_branch_urgency(["normal"]) == "normal"

    def test_normal_and_critical(self) -> None:
        assert aggregate_multi_branch_urgency(["normal", "critical"]) == "critical"

    def test_elevated_and_warning(self) -> None:
        assert aggregate_multi_branch_urgency(["elevated", "warning"]) == "elevated"

    def test_multiple_warnings(self) -> None:
        assert aggregate_multi_branch_urgency(["warning", "warning", "normal"]) == "warning"
