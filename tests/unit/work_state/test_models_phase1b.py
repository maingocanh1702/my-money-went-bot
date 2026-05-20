"""Tests for Phase 1b Signals field extensions per spec §11.2."""

from __future__ import annotations


class TestSignalsPhase1bFields:
    def test_pr_url_default_none(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=False,
            tech_exists=False,
            branch_exists=False,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
        )
        assert s.pr_url is None

    def test_pr_url_set(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=5,
            last_commit_sha="abc",
            pr_state="open",
            pr_number=42,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            pr_url="https://github.com/org/repo/pull/42",
        )
        assert s.pr_url == "https://github.com/org/repo/pull/42"

    def test_ci_check_run_count_default_zero(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=False,
            tech_exists=False,
            branch_exists=False,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
        )
        assert s.ci_check_run_count == 0

    def test_ci_check_run_count_set(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=5,
            last_commit_sha="abc",
            pr_state="open",
            pr_number=42,
            review_state="none",
            ci_state="pass",
            deploy_state="unknown",
            ci_check_run_count=7,
        )
        assert s.ci_check_run_count == 7

    def test_last_review_at_default_none(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=False,
            tech_exists=False,
            branch_exists=False,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
        )
        assert s.last_review_at is None

    def test_last_review_at_set(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=5,
            last_commit_sha="abc",
            pr_state="open",
            pr_number=42,
            review_state="approved",
            ci_state="pass",
            deploy_state="unknown",
            last_review_at="2026-05-20T10:00:00Z",
        )
        assert s.last_review_at == "2026-05-20T10:00:00Z"

    def test_last_deploy_at_default_none(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=False,
            tech_exists=False,
            branch_exists=False,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
        )
        assert s.last_deploy_at is None

    def test_last_deploy_at_set(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=10,
            last_commit_sha="def",
            pr_state="merged",
            pr_number=99,
            review_state="approved",
            ci_state="pass",
            deploy_state="deployed",
            last_deploy_at="2026-05-20T12:00:00Z",
        )
        assert s.last_deploy_at == "2026-05-20T12:00:00Z"

    def test_phase1a_fields_unaffected(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=True,
            tech_exists=False,
            branch_exists=True,
            commits_count=3,
            last_commit_sha="abc",
            pr_state="open",
            pr_number=10,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            warnings=["test_warn"],
        )
        assert s.spec_exists is True
        assert s.tech_exists is False
        assert s.branch_exists is True
        assert s.commits_count == 3
        assert s.last_commit_sha == "abc"
        assert s.pr_state == "open"
        assert s.pr_number == 10
        assert s.review_state == "none"
        assert s.ci_state == "none"
        assert s.deploy_state == "unknown"
        assert s.warnings == ["test_warn"]

    def test_all_new_fields_together(self) -> None:
        from scripts.work_state.models import Signals

        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=10,
            last_commit_sha="fff",
            pr_state="merged",
            pr_number=55,
            review_state="approved",
            ci_state="pass",
            deploy_state="deployed",
            pr_url="https://github.com/org/repo/pull/55",
            ci_check_run_count=4,
            last_review_at="2026-05-19T08:00:00Z",
            last_deploy_at="2026-05-20T14:00:00Z",
        )
        assert s.pr_url == "https://github.com/org/repo/pull/55"
        assert s.ci_check_run_count == 4
        assert s.last_review_at == "2026-05-19T08:00:00Z"
        assert s.last_deploy_at == "2026-05-20T14:00:00Z"
