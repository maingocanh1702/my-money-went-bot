"""Tests for CI check-runs collector per spec §6.6."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "github" / "check-runs"


class TestCollectCiSignals:
    def test_all_success(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        data = json.loads((FIXTURES / "all_success.json").read_text())

        with patch(
            "work_state.signal_collectors.ci._gh_get_check_runs",
            return_value=data,
        ):
            result = collect_ci_signals(commit_sha="abc123", repo="org/repo")

        assert result["ci_state"] == "success"
        assert result["ci_check_run_count"] == 3
        assert "ci_unknown" not in result["warnings"]

    def test_one_failure(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        data = json.loads((FIXTURES / "one_failure.json").read_text())

        with patch(
            "work_state.signal_collectors.ci._gh_get_check_runs",
            return_value=data,
        ):
            result = collect_ci_signals(commit_sha="abc123", repo="org/repo")

        assert result["ci_state"] == "failure"
        assert result["ci_check_run_count"] == 3
        assert "ci-failing" in result["overlays"]

    def test_in_progress(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        data = json.loads((FIXTURES / "in_progress.json").read_text())

        with patch(
            "work_state.signal_collectors.ci._gh_get_check_runs",
            return_value=data,
        ):
            result = collect_ci_signals(commit_sha="abc123", repo="org/repo")

        assert result["ci_state"] == "pending"
        assert "ci-running" in result["overlays"]

    def test_empty_no_checks(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        data = json.loads((FIXTURES / "empty.json").read_text())

        with patch(
            "work_state.signal_collectors.ci._gh_get_check_runs",
            return_value=data,
        ):
            result = collect_ci_signals(commit_sha="abc123", repo="org/repo")

        assert result["ci_state"] == "unknown"
        assert "ci_no_checks" in result["warnings"]
        assert result["ci_check_run_count"] == 0

    def test_skipped_excluded_from_count(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        data = json.loads((FIXTURES / "with_skipped.json").read_text())

        with patch(
            "work_state.signal_collectors.ci._gh_get_check_runs",
            return_value=data,
        ):
            result = collect_ci_signals(commit_sha="abc123", repo="org/repo")

        assert result["ci_state"] == "success"
        assert result["ci_check_run_count"] == 2  # skipped excluded

    def test_network_failure_unknown_safe(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        with patch(
            "work_state.signal_collectors.ci._gh_get_check_runs",
            side_effect=OSError("network down"),
        ):
            result = collect_ci_signals(commit_sha="abc123", repo="org/repo")

        assert result["ci_state"] == "unknown"
        assert "ci_unknown" in result["warnings"]

    def test_no_commit_sha_returns_unknown(self) -> None:
        from work_state.signal_collectors.ci import collect_ci_signals

        result = collect_ci_signals(commit_sha=None, repo="org/repo")

        assert result["ci_state"] == "unknown"
        assert result["ci_check_run_count"] == 0
