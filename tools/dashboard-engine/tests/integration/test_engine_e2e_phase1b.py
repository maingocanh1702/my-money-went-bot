"""Integration e2e Phase 1b — 5 collectors (filesystem + git + github + ci + railway) fully wired.

Uses --no-network mode + cached fixtures for deterministic test.
Extends Phase 1a e2e pattern: tracker → plan_reader → collectors → status_machine → state_store.
"""

from __future__ import annotations

import json
from pathlib import Path

from work_state.models import CurrentState, Signals
from work_state.plan_reader import read_tracker
from work_state.progress import compute_progress
from work_state.signal_collectors.ci import CiSignals
from work_state.signal_collectors.github import GithubSignals
from work_state.signal_collectors.railway import RailwaySignals
from work_state.state_store import read_current_state, write_current_state
from work_state.status_machine import compute_human_status, compute_status

GITHUB_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "github"
RAILWAY_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "railway"


def _github_signals_for_item(item_id: str) -> GithubSignals:
    """Deterministic GitHub signals per item pattern."""
    if item_id.startswith("W"):
        return {
            "pr_state": "merged",
            "pr_number": 10,
            "pr_url": "https://github.com/org/repo/pull/10",
            "review_state": "approved",
            "last_review_at": "2026-05-13T08:00:00Z",
            "warnings": [],
            "foundation_codex_approved": None,
            "foundation_founder_signoff": None,
        }
    return {
        "pr_state": "open",
        "pr_number": 42,
        "pr_url": "https://github.com/org/repo/pull/42",
        "review_state": "none",
        "last_review_at": None,
        "warnings": [],
        "foundation_codex_approved": None,
        "foundation_founder_signoff": None,
    }


def _ci_signals_for_item(item_id: str) -> CiSignals:
    """Deterministic CI signals per item pattern."""
    if item_id.startswith("W"):
        return {
            "ci_state": "success",
            "ci_check_run_count": 3,
            "overlays": [],
            "warnings": [],
        }
    return {
        "ci_state": "pending",
        "ci_check_run_count": 2,
        "overlays": ["ci-running"],
        "warnings": [],
    }


def _railway_signals_for_item(item_id: str) -> RailwaySignals:
    """Deterministic Railway signals per item pattern."""
    if item_id.startswith("W"):
        return {
            "deploy_state": "deployed",
            "last_deploy_at": "2026-05-13T09:00:00Z",
            "overlays": [],
            "warnings": [],
        }
    return {
        "deploy_state": "unknown",
        "last_deploy_at": None,
        "overlays": [],
        "warnings": ["railway_unknown"],
    }


def _run_engine_phase1b(tracker_path: str, dashboard_dir: Path) -> list[CurrentState]:
    items = read_tracker(tracker_path)
    states: list[CurrentState] = []

    for parsed in items:
        item = parsed.item
        gh = _github_signals_for_item(item.id)
        ci = _ci_signals_for_item(item.id)
        rw = _railway_signals_for_item(item.id)

        all_warnings = list(gh["warnings"]) + list(ci["warnings"]) + list(rw["warnings"])
        overlays = list(ci["overlays"]) + list(rw["overlays"])

        signals = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=5,
            last_commit_sha="abc123",
            pr_state=gh["pr_state"],
            pr_number=gh["pr_number"],
            review_state=gh["review_state"],
            ci_state=ci["ci_state"],
            deploy_state=rw["deploy_state"],
            warnings=all_warnings,
            pr_url=gh["pr_url"],
            ci_check_run_count=ci["ci_check_run_count"],
            last_review_at=gh["last_review_at"],
            last_deploy_at=rw["last_deploy_at"],
        )

        status = compute_status(signals)
        human = compute_human_status(status, overlays, signals.deploy_state)

        try:
            progress = compute_progress(signals, item.progress_profile)
        except NotImplementedError:
            progress = 0

        state = CurrentState(
            item_id=item.id,
            status=status,
            human_status=human,
            progress=progress,
            runtime_urgency="normal",
            overlays=overlays,
            signals=signals,
            last_event_ts=None,
        )
        states.append(state)

    write_current_state(states, dashboard_dir)
    return states


class TestEngineE2EPhase1b:
    def test_five_collectors_wired(self, tmp_path: Path) -> None:
        fixture = (
            Path(__file__).parent.parent.parent
            / "unit"
            / "work_state"
            / "fixtures"
            / "tracker_sample.md"
        )
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine_phase1b(str(fixture), dashboard_dir)
        assert len(states) > 0

        stored = read_current_state(dashboard_dir)
        assert stored is not None
        items = stored["items"]
        assert isinstance(items, list)
        assert len(items) == len(states)

    def test_infra_items_deployed_with_pr_merged(self, tmp_path: Path) -> None:
        fixture = (
            Path(__file__).parent.parent.parent
            / "unit"
            / "work_state"
            / "fixtures"
            / "tracker_sample.md"
        )
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine_phase1b(str(fixture), dashboard_dir)
        infra = [s for s in states if s.item_id.startswith("W")]
        for s in infra:
            assert s.status == "deployed"
            assert s.human_status == "DONE"
            assert s.signals.pr_state == "merged"
            assert s.signals.pr_number == 10
            assert s.signals.deploy_state == "deployed"
            assert s.signals.last_deploy_at == "2026-05-13T09:00:00Z"
            assert s.signals.ci_check_run_count == 3

    def test_feature_items_in_review_with_ci_running(self, tmp_path: Path) -> None:
        fixture = (
            Path(__file__).parent.parent.parent
            / "unit"
            / "work_state"
            / "fixtures"
            / "tracker_sample.md"
        )
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine_phase1b(str(fixture), dashboard_dir)
        features = [s for s in states if not s.item_id.startswith("W")]
        for s in features:
            assert s.status == "in-review"
            assert s.signals.pr_state == "open"
            assert s.signals.pr_number == 42
            assert s.signals.pr_url == "https://github.com/org/repo/pull/42"
            assert s.signals.ci_state == "pending"
            assert s.signals.ci_check_run_count == 2
            assert "ci-running" in s.overlays

    def test_state_json_contains_phase1b_fields(self, tmp_path: Path) -> None:
        fixture = (
            Path(__file__).parent.parent.parent
            / "unit"
            / "work_state"
            / "fixtures"
            / "tracker_sample.md"
        )
        dashboard_dir = tmp_path / ".dashboard"

        _run_engine_phase1b(str(fixture), dashboard_dir)
        raw = json.loads((dashboard_dir / "current_state.json").read_text())
        for item in raw["items"]:
            signals = item["signals"]
            assert "pr_state" in signals
            assert "pr_url" in signals
            assert "ci_state" in signals
            assert "ci_check_run_count" in signals
            assert "deploy_state" in signals
            assert "last_deploy_at" in signals
            assert "last_review_at" in signals

    def test_warnings_aggregated_from_all_collectors(self, tmp_path: Path) -> None:
        fixture = (
            Path(__file__).parent.parent.parent
            / "unit"
            / "work_state"
            / "fixtures"
            / "tracker_sample.md"
        )
        dashboard_dir = tmp_path / ".dashboard"

        states = _run_engine_phase1b(str(fixture), dashboard_dir)
        features = [s for s in states if not s.item_id.startswith("W")]
        for s in features:
            assert "railway_unknown" in s.signals.warnings
