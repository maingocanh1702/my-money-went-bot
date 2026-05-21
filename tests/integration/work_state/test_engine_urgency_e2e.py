"""Integration tests for urgency derivation + MAX aggregation wired into engine.

Covers spec §9.4.2 + §4.1.3: per-branch urgency computed then MAX-aggregated.
Engine output CurrentState.runtime_urgency must reflect derived value, not hardcoded "normal".
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.work_state.engine import run_engine
from scripts.work_state.models import WorkItem
from scripts.work_state.plan_reader import ParsedWorkItem


@pytest.fixture()
def tmp_dashboard(tmp_path: Path) -> Path:
    dashboard_dir = tmp_path / ".dashboard"
    dashboard_dir.mkdir()
    return dashboard_dir


@pytest.fixture()
def tracker_path(tmp_path: Path) -> Path:
    return tmp_path / "tracker.md"


def _write_tracker(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a minimal tracker with given feature rows."""
    lines = [
        "# Implementation Tracker",
        "",
        "## 4. PR tracking table",
        "",
        "### Phase 1: Core",
        "",
        "| PR | Wave | Feature | Status | Branch | Gates | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | W0 | {r.get('feature', r['id'])} "
            f"| {r.get('status', '🟡 In progress')} "
            f"| `{r['branch']}` | — | — |"
        )
    lines.extend(
        [
            "",
            "## 5. Progress summary",
            "",
            "| Phase | Total | Merged | In Progress | Blocked | Deferred | % |",
            "|---|---|---|---|---|---|---|",
            f"| 1 Core | {len(rows)} | 0 | {len(rows)} | 0 | 0 | 0% |",
            "",
            "| **MVP total** | **{0}** | **0** | **{0}** | **0** | **0** | **0%** |".format(
                len(rows)
            ),
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _mock_signals_normal() -> dict[str, object]:
    return {
        "spec_exists": True,
        "tech_exists": True,
        "branch_exists": True,
        "commits_count": 5,
        "last_commit_sha": "abc123",
        "warnings": [],
        "spec_hash": None,
        "spec_modified_at": None,
        "tech_hash": None,
        "tech_modified_at": None,
        "tracker_row_hash": None,
    }


def _mock_gh_signals(
    pr_state: str = "open",
    review_state: str = "none",
) -> dict[str, object]:
    return {
        "pr_state": pr_state,
        "pr_number": 1,
        "pr_url": None,
        "review_state": review_state,
        "last_review_at": None,
        "warnings": [],
        "foundation_codex_approved": None,
        "foundation_founder_signoff": None,
    }


def _mock_ci_signals(
    ci_state: str = "passed",
) -> dict[str, object]:
    return {
        "ci_state": ci_state,
        "ci_check_run_count": 1,
        "warnings": [],
        "overlays": [],
    }


def _mock_ci_failing() -> dict[str, object]:
    return {
        "ci_state": "failing",
        "ci_check_run_count": 1,
        "warnings": [],
        "overlays": ["ci-failing"],
    }


def _mock_railway(
    deploy_state: str = "not-applicable",
) -> dict[str, object]:
    return {
        "deploy_state": deploy_state,
        "last_deploy_at": None,
        "warnings": [],
        "overlays": [],
    }


def _mock_railway_failed() -> dict[str, object]:
    return {
        "deploy_state": "failed",
        "last_deploy_at": None,
        "warnings": [],
        "overlays": ["deploy-failed"],
    }


class TestSingleBranchUrgency:
    def test_normal_no_overlays(self, tracker_path: Path, tmp_dashboard: Path) -> None:
        _write_tracker(tracker_path, [{"id": "F01", "branch": "feat/f01"}])
        with (
            patch(
                "scripts.work_state.engine.collect_filesystem_signals",
                return_value=_mock_signals_normal(),
            ),
            patch(
                "scripts.work_state.engine.collect_git_signals",
                return_value={
                    **_mock_signals_normal(),
                    "branch_exists": True,
                    "commits_count": 5,
                    "last_commit_sha": "abc",
                    "warnings": [],
                },
            ),
            patch(
                "scripts.work_state.engine.collect_github_signals", return_value=_mock_gh_signals()
            ),
            patch("scripts.work_state.engine.collect_ci_signals", return_value=_mock_ci_signals()),
            patch(
                "scripts.work_state.engine.collect_railway_signals", return_value=_mock_railway()
            ),
        ):
            states = run_engine(str(tracker_path), tmp_dashboard, no_network=True)
        assert len(states) == 1
        assert states[0].runtime_urgency == "normal"

    def test_critical_deploy_failed(self, tracker_path: Path, tmp_dashboard: Path) -> None:
        _write_tracker(tracker_path, [{"id": "F01", "branch": "feat/f01"}])
        with (
            patch(
                "scripts.work_state.engine.collect_filesystem_signals",
                return_value=_mock_signals_normal(),
            ),
            patch(
                "scripts.work_state.engine.collect_git_signals",
                return_value={
                    **_mock_signals_normal(),
                    "branch_exists": True,
                    "commits_count": 5,
                    "last_commit_sha": "abc",
                    "warnings": [],
                },
            ),
            patch(
                "scripts.work_state.engine.collect_github_signals",
                return_value=_mock_gh_signals(pr_state="merged"),
            ),
            patch("scripts.work_state.engine.collect_ci_signals", return_value=_mock_ci_signals()),
            patch(
                "scripts.work_state.engine.collect_railway_signals",
                return_value=_mock_railway_failed(),
            ),
        ):
            states = run_engine(str(tracker_path), tmp_dashboard, no_network=True)
        assert len(states) == 1
        assert states[0].runtime_urgency == "critical"


def _make_multi_branch_item() -> WorkItem:
    return WorkItem(
        id="F01",
        linear_id=None,
        feature_id="F01",
        title="Multi-branch feature",
        type="feature",
        phase="Phase 1",
        priority="P1",
        risk_tier="P1",
        lane="standard",
        owner="founder",
        deadline=None,
        specs={"fe": None, "be": None},
        branches=["feat/f01-a", "feat/f01-b"],
        acceptance=[],
        dependencies=[],
        external_blockers=[],
        decision_needed=None,
        progress_profile="standard",
    )


class TestMultiBranchUrgencyAggregation:
    def test_max_normal_and_elevated(self, tracker_path: Path, tmp_dashboard: Path) -> None:
        _write_tracker(tracker_path, [{"id": "F01", "branch": "feat/f01-a"}])
        multi_item = _make_multi_branch_item()
        call_count = {"n": 0}

        def mock_ci_side_effect(*args: object, **kwargs: object) -> dict[str, object]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _mock_ci_signals()
            return _mock_ci_failing()

        with (
            patch(
                "scripts.work_state.engine.read_tracker",
                return_value=[ParsedWorkItem(item=multi_item)],
            ),
            patch(
                "scripts.work_state.engine.collect_filesystem_signals",
                return_value=_mock_signals_normal(),
            ),
            patch(
                "scripts.work_state.engine.collect_git_signals",
                return_value={
                    **_mock_signals_normal(),
                    "branch_exists": True,
                    "commits_count": 5,
                    "last_commit_sha": "abc",
                    "warnings": [],
                },
            ),
            patch(
                "scripts.work_state.engine.collect_github_signals", return_value=_mock_gh_signals()
            ),
            patch("scripts.work_state.engine.collect_ci_signals", side_effect=mock_ci_side_effect),
            patch(
                "scripts.work_state.engine.collect_railway_signals", return_value=_mock_railway()
            ),
        ):
            states = run_engine(str(tracker_path), tmp_dashboard, no_network=True)
        assert len(states) == 1
        assert states[0].runtime_urgency == "elevated"

    def test_all_branches_normal(self, tracker_path: Path, tmp_dashboard: Path) -> None:
        _write_tracker(tracker_path, [{"id": "F01", "branch": "feat/f01-a"}])
        multi_item = _make_multi_branch_item()

        with (
            patch(
                "scripts.work_state.engine.read_tracker",
                return_value=[ParsedWorkItem(item=multi_item)],
            ),
            patch(
                "scripts.work_state.engine.collect_filesystem_signals",
                return_value=_mock_signals_normal(),
            ),
            patch(
                "scripts.work_state.engine.collect_git_signals",
                return_value={
                    **_mock_signals_normal(),
                    "branch_exists": True,
                    "commits_count": 5,
                    "last_commit_sha": "abc",
                    "warnings": [],
                },
            ),
            patch(
                "scripts.work_state.engine.collect_github_signals", return_value=_mock_gh_signals()
            ),
            patch("scripts.work_state.engine.collect_ci_signals", return_value=_mock_ci_signals()),
            patch(
                "scripts.work_state.engine.collect_railway_signals", return_value=_mock_railway()
            ),
        ):
            states = run_engine(str(tracker_path), tmp_dashboard, no_network=True)
        assert len(states) == 1
        assert states[0].runtime_urgency == "normal"
