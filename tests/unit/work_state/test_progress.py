"""Tests for progress profiles per spec §9.1."""

from __future__ import annotations

import pytest

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


class TestStandardFeatureProfile:
    """Per spec §9.1 standard_feature weights table."""

    def test_no_artifacts_0_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals()
        assert compute_progress(s, "standard_feature") == 0

    def test_spec_exists_10_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(spec_exists=True)
        assert compute_progress(s, "standard_feature") == 10

    def test_tech_exists_20_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(spec_exists=True, tech_exists=True)
        assert compute_progress(s, "standard_feature") == 20

    def test_branch_exists_30_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(spec_exists=True, tech_exists=True, branch_exists=True)
        assert compute_progress(s, "standard_feature") == 30

    def test_commits_exist_45_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(spec_exists=True, tech_exists=True, branch_exists=True, commits_count=3)
        assert compute_progress(s, "standard_feature") == 45

    def test_pr_open_60_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=3,
            pr_state="open",
        )
        assert compute_progress(s, "standard_feature") == 60

    def test_ci_pass_75_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=3,
            pr_state="open",
            ci_state="pass",
        )
        assert compute_progress(s, "standard_feature") == 75

    def test_approved_85_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=3,
            pr_state="open",
            ci_state="pass",
            review_state="approved",
        )
        assert compute_progress(s, "standard_feature") == 85

    def test_merged_95_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=3,
            pr_state="merged",
            ci_state="pass",
            review_state="approved",
        )
        assert compute_progress(s, "standard_feature") == 95

    def test_deployed_100_percent(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=3,
            pr_state="merged",
            ci_state="pass",
            review_state="approved",
            deploy_state="deployed",
        )
        assert compute_progress(s, "standard_feature") == 100

    def test_partial_milestones(self) -> None:
        """Branch with commits but no PR → 45%."""
        from scripts.work_state.progress import compute_progress

        s = _make_signals(branch_exists=True, commits_count=5)
        assert compute_progress(s, "standard_feature") == 45


class TestOtherProfiles:
    def test_foundation_change_raises(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals()
        with pytest.raises(NotImplementedError):
            compute_progress(s, "foundation_change")

    def test_docs_only_raises(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals()
        with pytest.raises(NotImplementedError):
            compute_progress(s, "docs_only")

    def test_dashboard_engine_raises(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals()
        with pytest.raises(NotImplementedError):
            compute_progress(s, "dashboard_engine")

    def test_unknown_profile_raises(self) -> None:
        from scripts.work_state.progress import compute_progress

        s = _make_signals()
        with pytest.raises(NotImplementedError):
            compute_progress(s, "unknown_profile")
