"""Tests for git signal collector per spec §6.2."""

from __future__ import annotations

from unittest.mock import patch


class TestBranchExists:
    def test_branch_exists_true(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            return_value="abc123\trefs/heads/feat/funding-sources",
        ):
            signals = collect_git_signals("feat/funding-sources", "origin")
        assert signals["branch_exists"] is True

    def test_branch_exists_false(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            return_value="",
        ):
            signals = collect_git_signals("feat/funding-sources", "origin")
        assert signals["branch_exists"] is False

    def test_branch_exists_no_branch_name(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        signals = collect_git_signals("", "origin")
        assert signals["branch_exists"] is False
        assert signals["commits_count"] == 0


class TestCommitsCount:
    def test_commits_count(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        def mock_run(cmd: list[str], timeout: int = 30) -> str:
            if "ls-remote" in cmd:
                return "abc123\trefs/heads/feat/funding-sources"
            if "rev-list" in cmd:
                return "5"
            if "rev-parse" in cmd:
                return "deadbeef0000"  # pragma: allowlist secret
            return ""

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            side_effect=mock_run,
        ):
            signals = collect_git_signals("feat/funding-sources", "origin")
        assert signals["commits_count"] == 5

    def test_commits_count_zero_when_no_branch(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            return_value="",
        ):
            signals = collect_git_signals("feat/nonexistent", "origin")
        assert signals["commits_count"] == 0


class TestLastCommitSha:
    def test_last_commit_sha(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        def mock_run(cmd: list[str], timeout: int = 30) -> str:
            if "ls-remote" in cmd:
                return "abc123def456\trefs/heads/feat/test"
            if "rev-list" in cmd:
                return "3"
            if "rev-parse" in cmd:
                return "deadbeef0000"  # pragma: allowlist secret
            return ""

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            side_effect=mock_run,
        ):
            signals = collect_git_signals("feat/test", "origin")
        assert signals["last_commit_sha"] == "deadbeef0000"  # pragma: allowlist secret

    def test_last_commit_sha_none_no_branch(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            return_value="",
        ):
            signals = collect_git_signals("feat/nonexistent", "origin")
        assert signals["last_commit_sha"] is None


class TestNetworkTimeout:
    def test_git_unknown_on_timeout(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            side_effect=TimeoutError("network timeout"),
        ):
            signals = collect_git_signals("feat/test", "origin")
        assert signals["branch_exists"] is False
        assert signals["commits_count"] == 0
        assert signals["last_commit_sha"] is None
        assert "git_unknown" in signals["warnings"]

    def test_git_unknown_on_oserror(self) -> None:
        from work_state.signal_collectors.git import collect_git_signals

        with patch(
            "work_state.signal_collectors.git._run_git_command",
            side_effect=OSError("git not found"),
        ):
            signals = collect_git_signals("feat/test", "origin")
        assert "git_unknown" in signals["warnings"]
