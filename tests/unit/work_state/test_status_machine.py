"""Tests for status state machine per spec §8.1, §8.0, §4.1."""

from __future__ import annotations

from scripts.work_state.models import Signals


def _make_signals(**overrides: object) -> Signals:
    defaults: dict[str, object] = {
        "spec_exists": False,
        "tech_exists": False,
        "branch_exists": False,
        "commits_count": 0,
        "last_commit_sha": None,
        "pr_state": "none",
        "pr_number": None,
        "review_state": "none",
        "ci_state": "none",
        "deploy_state": "unknown",
        "warnings": [],
    }
    defaults.update(overrides)
    return Signals(**defaults)  # type: ignore[arg-type]


class TestComputeStatus:
    """Per spec §8.1 first-match priority."""

    def test_deployed(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(deploy_state="deployed")
        assert compute_status(s) == "deployed"

    def test_deploying(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(deploy_state="deploying")
        assert compute_status(s) == "deploying"

    def test_merged_regardless_of_deploy_failed(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="merged", deploy_state="deploy-failed")
        assert compute_status(s) == "merged"

    def test_merged(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="merged")
        assert compute_status(s) == "merged"

    def test_abandoned_pr_closed(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="closed")
        assert compute_status(s) == "abandoned"

    def test_pr_open_changes_requested(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="open", review_state="changes-requested")
        assert compute_status(s) == "changes-requested"

    def test_pr_open_approved(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="open", review_state="approved")
        assert compute_status(s) == "approved-pending-merge"

    def test_pr_open_default(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="open")
        assert compute_status(s) == "in-review"

    def test_pr_draft(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="draft")
        assert compute_status(s) == "in-progress"

    def test_branch_with_commits(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(branch_exists=True, commits_count=3)
        assert compute_status(s) == "in-progress"

    def test_branch_only(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(branch_exists=True)
        assert compute_status(s) == "branch-created"

    def test_tech_exists(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(tech_exists=True)
        assert compute_status(s) == "tech-ready"

    def test_spec_only(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(spec_exists=True)
        assert compute_status(s) == "spec-only"

    def test_not_started(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals()
        assert compute_status(s) == "not-started"

    def test_deploy_takes_priority_over_pr_merged(self) -> None:
        from scripts.work_state.status_machine import compute_status

        s = _make_signals(pr_state="merged", deploy_state="deployed")
        assert compute_status(s) == "deployed"


class TestHumanStatus:
    """Per spec §8.0 human status projection — 9 buckets."""

    def test_backlog(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("not-started", [], "unknown") == "BACKLOG"

    def test_todo_spec_only(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("spec-only", [], "unknown") == "TODO"

    def test_todo_tech_ready(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("tech-ready", [], "unknown") == "TODO"

    def test_in_progress_branch_created(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("branch-created", [], "unknown") == "IN_PROGRESS"

    def test_in_progress_in_review(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("in-review", [], "unknown") == "IN_PROGRESS"

    def test_in_progress_changes_requested(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("changes-requested", [], "unknown") == "IN_PROGRESS"

    def test_waiting_review_requested_overlay(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("in-review", ["review-requested"], "unknown") == "WAITING"

    def test_waiting_stale_overlay(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("in-progress", ["stale"], "unknown") == "WAITING"

    def test_waiting_deploying(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("deploying", [], "unknown") == "WAITING"

    def test_waiting_merged_deploy_unknown(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("merged", [], "unknown") == "WAITING"

    def test_waiting_merged_not_deployed(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("merged", [], "not-deployed") == "WAITING"

    def test_failing_ci(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("in-review", ["ci-failing"], "unknown") == "FAILING"

    def test_failing_deploy_failed(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("merged", ["deploy-failed"], "unknown") == "FAILING"

    def test_blocked(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("in-progress", ["blocked"], "unknown") == "BLOCKED"

    def test_blocked_dominates_ci_failing(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("in-review", ["blocked", "ci-failing"], "unknown") == "BLOCKED"

    def test_done_deployed(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("deployed", [], "deployed") == "DONE"

    def test_done_merged_not_applicable(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("merged", [], "not-applicable") == "DONE"

    def test_abandoned(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("abandoned", [], "unknown") == "ABANDONED"

    def test_unknown_overlay(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert compute_human_status("not-started", ["unknown"], "unknown") == "UNKNOWN"

    def test_failing_dominates_waiting(self) -> None:
        from scripts.work_state.status_machine import compute_human_status

        assert (
            compute_human_status("in-review", ["ci-failing", "review-requested"], "unknown")
            == "FAILING"
        )


class TestMultiBranchAggregation:
    """Per spec §4.1.1 lattice + §4.1.2 overlay union."""

    def test_min_progressed_status(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_status

        statuses = ["deployed", "in-review"]
        assert aggregate_multi_branch_status(statuses) == "in-review"

    def test_all_same_status(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_status

        statuses = ["deployed", "deployed"]
        assert aggregate_multi_branch_status(statuses) == "deployed"

    def test_abandoned_excluded_from_min(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_status

        statuses = ["abandoned", "in-progress"]
        assert aggregate_multi_branch_status(statuses) == "in-progress"

    def test_all_abandoned(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_status

        statuses = ["abandoned", "abandoned"]
        assert aggregate_multi_branch_status(statuses) == "abandoned"

    def test_single_branch(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_status

        assert aggregate_multi_branch_status(["merged"]) == "merged"

    def test_overlay_union(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_overlays

        overlays_a = ["ci-failing"]
        overlays_b: list[str] = []
        result = aggregate_multi_branch_overlays(
            [("deployed", overlays_a), ("in-review", overlays_b)]
        )
        assert "ci-failing" in result
        assert "partial-progress" in result

    def test_no_partial_progress_both_active(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_overlays

        result = aggregate_multi_branch_overlays([("in-progress", []), ("in-progress", [])])
        assert "partial-progress" not in result

    def test_no_partial_progress_both_terminal_same(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_overlays

        result = aggregate_multi_branch_overlays([("deployed", []), ("deployed", [])])
        assert "partial-progress" not in result

    def test_partial_progress_mixed_terminal(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_overlays

        result = aggregate_multi_branch_overlays([("merged", []), ("deployed", [])])
        assert "partial-progress" in result

    def test_partial_progress_terminal_plus_active(self) -> None:
        from scripts.work_state.status_machine import aggregate_multi_branch_overlays

        result = aggregate_multi_branch_overlays([("deployed", []), ("in-progress", [])])
        assert "partial-progress" in result


class TestCanonicalOverlaysSpecParity:
    """MYM-11: enforce CANONICAL_OVERLAYS code ≡ spec §8.2 single source of truth.

    Per spec line 781: '§8.2 = single source of truth' — code must mirror spec list exactly.
    Spec v1.5.0 (2026-05-21) reconciled to 21 overlays (added multi-branch,
    deploy-in-progress, no-ci per Linear MYM-11 Option A). These 3 are declared in
    `CANONICAL_OVERLAYS` but emit logic is reserved for future wiring per §8.2 footer.
    """

    def test_canonical_overlays_count_matches_spec_8_2(self) -> None:
        """Spec v1.5.0 §8.2 table has 21 overlay rows. Code must match."""
        from scripts.work_state.status_machine import CANONICAL_OVERLAYS

        assert len(CANONICAL_OVERLAYS) == 21, (
            f"CANONICAL_OVERLAYS has {len(CANONICAL_OVERLAYS)} entries; "
            "spec v1.5.0 §8.2 declares exactly 21. Update spec OR code to maintain parity."
        )

    def test_canonical_overlays_exact_set_matches_spec(self) -> None:
        """Exhaustive set match against spec v1.5.0 §8.2 (21 rows)."""
        from scripts.work_state.status_machine import CANONICAL_OVERLAYS

        spec_8_2_overlays = frozenset(
            {
                "blocked",
                "stale",
                "ci-running",
                "ci-failing",
                "review-requested",
                "deploy-failed",
                "unknown",
                "artifact-drift",
                "ambiguous-pr-mapping",
                "partial-progress",
                "stale-cache",
                "cache-warmup",
                "risk-tier-inferred",
                "manual-override",
                "spec-modified",
                "tech-modified",
                "tracker-modified",
                "post-ship-doc-change",
                # v1.5.0 additions (MYM-11 Option A — emit logic reserved for future wiring)
                "multi-branch",
                "deploy-in-progress",
                "no-ci",
            }
        )
        assert CANONICAL_OVERLAYS == spec_8_2_overlays, (
            f"Drift detected. Only in code: {CANONICAL_OVERLAYS - spec_8_2_overlays}. "
            f"Only in spec: {spec_8_2_overlays - CANONICAL_OVERLAYS}. "
            "Reconcile per spec §8.2 = single source of truth."
        )

    def test_v1_5_0_legitimized_overlays_present(self) -> None:
        """Regression guard: 3 overlays legitimized by MYM-11 Option A must stay in CANONICAL_OVERLAYS.

        These were originally declared in code without spec backing. MYM-11 chose
        Option A (spec amendment) over Option B (code removal) because `multi-branch`
        is needed by projection to mark aggregated rows per Linear ticket. Removing
        them would break future projection work; spec amendment legitimizes the contract.
        """
        from scripts.work_state.status_machine import CANONICAL_OVERLAYS

        legitimized = {"multi-branch", "deploy-in-progress", "no-ci"}
        missing = legitimized - CANONICAL_OVERLAYS
        assert not missing, (
            f"v1.5.0 legitimized overlays missing from CANONICAL_OVERLAYS: {missing}. "
            "Per MYM-11 Option A, these are part of the 21-overlay canonical set. "
            "If removing intentionally, also remove from spec v1.5.0 §8.2 table + bump version."
        )
