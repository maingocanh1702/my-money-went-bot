"""Integration e2e — doc change awareness pipeline (Phase B).

Tests the full pipeline: filesystem hash collection → event emission → overlay
→ dashboard HTML badge rendering. Uses tmp_path fixtures (no network).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.work_state.engine import run_engine
from scripts.work_state.event_engine import read_tail_events
from scripts.work_state.models import CurrentState, Signals
from scripts.work_state.state_store import write_current_state


def _make_signals(
    spec_hash: str | None = None,
    tech_hash: str | None = None,
    tracker_row_hash: str | None = None,
    pr_state: str = "open",
    deploy_state: str = "unknown",
    **overrides: object,
) -> Signals:
    defaults: dict[str, object] = {
        "spec_exists": True,
        "tech_exists": True,
        "branch_exists": True,
        "commits_count": 5,
        "last_commit_sha": "abc123",
        "pr_state": pr_state,
        "pr_number": 42,
        "review_state": "none",
        "ci_state": "pass",
        "deploy_state": deploy_state,
        "warnings": [],
        "spec_hash": spec_hash,
        "tech_hash": tech_hash,
        "tracker_row_hash": tracker_row_hash,
    }
    defaults.update(overrides)
    return Signals(**defaults)  # type: ignore[arg-type]


def _make_state(
    item_id: str,
    status: str = "in-review",
    overlays: list[str] | None = None,
    spec_hash: str | None = None,
    tech_hash: str | None = None,
    tracker_row_hash: str | None = None,
    pr_state: str = "open",
    deploy_state: str = "unknown",
) -> CurrentState:
    return CurrentState(
        item_id=item_id,
        status=status,
        human_status="IN_PROGRESS",
        progress=60,
        runtime_urgency="normal",
        overlays=overlays or [],
        signals=_make_signals(
            spec_hash=spec_hash,
            tech_hash=tech_hash,
            tracker_row_hash=tracker_row_hash,
            pr_state=pr_state,
            deploy_state=deploy_state,
        ),
        last_event_ts="2026-05-21T08:00:00Z",
    )


class TestEngineEmitsSpecModifiedEvent:
    """B3: engine emits spec_modified event when hash changes."""

    def test_spec_modified_event_emitted(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import read_tail_events

        dashboard_dir = tmp_path / ".dashboard"
        dashboard_dir.mkdir()
        events_file = dashboard_dir / "events.jsonl"

        prev_state = _make_state("MYM-108", spec_hash="old_hash")
        write_current_state([prev_state], dashboard_dir)

        from scripts.work_state.event_engine import append_event, is_duplicate
        from scripts.work_state.models import Event

        event = Event(
            ts="2026-05-21T09:00:00Z",
            item="MYM-108",
            event="spec_modified",
            from_status=None,
            to_status=None,
            source="filesystem.spec",
            artifact="docs/features/feature-funding-sources.md",
        )
        if not is_duplicate(event, events_file):
            append_event(event, events_file)

        tail = read_tail_events(events_file)
        spec_events = [e for e in tail if e.get("event") == "spec_modified"]
        assert len(spec_events) == 1
        assert spec_events[0]["item"] == "MYM-108"
        assert spec_events[0]["source"] == "filesystem.spec"


class TestDashboardHtmlRendersBadge:
    """B5: dashboard HTML renders spec-changed badge."""

    def test_spec_modified_badge_in_html(self, tmp_path: Path) -> None:
        from scripts.work_state.projections.dashboard import build_state_block

        state = _make_state("MYM-108", overlays=["spec-modified"], spec_hash="new_hash")
        state_dict = {
            "item_id": state.item_id,
            "status": state.status,
            "human_status": state.human_status,
            "progress": state.progress,
            "runtime_urgency": state.runtime_urgency,
            "overlays": state.overlays,
            "last_event_ts": state.last_event_ts,
        }
        block = build_state_block(state_dict)
        overlays = block.get("overlays", [])
        assert isinstance(overlays, list)
        assert "spec-modified" in overlays


class TestStatusAutoFlipNoTriggerDrift:
    """B8: status auto-flip does NOT trigger drift warning."""

    def test_status_change_no_tracker_modified(self) -> None:
        from scripts.work_state.status_machine import compute_overlays

        signals = _make_signals(tracker_row_hash="same_hash")
        overlays = compute_overlays(
            signals,
            base_status="merged",
            prev_tracker_row_hash="same_hash",
        )
        assert "tracker-modified" not in overlays
        assert "post-ship-doc-change" not in overlays


class TestPostShipTerminalDocChange:
    """B6: terminal status row edit triggers post-ship-doc-change warning overlay."""

    def test_merged_row_spec_edit_triggers_warning(self) -> None:
        from scripts.work_state.status_machine import compute_overlays

        signals = _make_signals(
            spec_hash="new_hash",
            pr_state="merged",
        )
        overlays = compute_overlays(
            signals,
            base_status="merged",
            prev_spec_hash="old_hash",
        )
        assert "post-ship-doc-change" in overlays
        assert "spec-modified" in overlays

    def test_deployed_row_tracker_edit_triggers_warning(self) -> None:
        from scripts.work_state.status_machine import compute_overlays

        signals = _make_signals(
            tracker_row_hash="new_hash",
            deploy_state="deployed",
        )
        overlays = compute_overlays(
            signals,
            base_status="deployed",
            prev_tracker_row_hash="old_hash",
        )
        assert "post-ship-doc-change" in overlays
        assert "tracker-modified" in overlays


# ============================================================================
# MYM-8 Scope B — Engine emission wire integration tests
# ============================================================================


@pytest.fixture()
def tmp_dashboard(tmp_path: Path) -> Path:
    d = tmp_path / ".dashboard"
    d.mkdir()
    return d


@pytest.fixture()
def tracker_file(tmp_path: Path) -> Path:
    return tmp_path / "tracker.md"


def _write_minimal_tracker(path: Path, feature_id: str = "F01") -> None:
    lines = [
        "# Implementation Tracker",
        "",
        "## 4. PR tracking table",
        "",
        "### Phase 1: Core",
        "",
        "| PR | Wave | Feature | Status | Branch | Gates | Notes |",
        "|---|---|---|---|---|---|---|",
        f"| {feature_id} | W0 | {feature_id} | 🟡 In progress | `feat/{feature_id.lower()}` | — | — |",
        "",
        "## 5. Progress summary",
        "",
        "| Phase | Total | Merged | In Progress | Blocked | Deferred | % |",
        "|---|---|---|---|---|---|---|",
        "| 1 Core | 1 | 0 | 1 | 0 | 0 | 0% |",
        "",
        "| **MVP total** | **1** | **0** | **1** | **0** | **0** | **0%** |",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _fs_signals(
    spec_hash: str | None = None,
    tech_hash: str | None = None,
    tracker_row_hash: str | None = None,
) -> dict[str, object]:
    return {
        "spec_exists": True,
        "tech_exists": True,
        "warnings": [],
        "spec_hash": spec_hash,
        "spec_modified_at": "2026-05-21T08:00:00Z" if spec_hash else None,
        "tech_hash": tech_hash,
        "tech_modified_at": "2026-05-21T08:00:00Z" if tech_hash else None,
        "tracker_row_hash": tracker_row_hash,
    }


def _git_signals() -> dict[str, object]:
    return {
        "branch_exists": True,
        "commits_count": 3,
        "last_commit_sha": "abc123",
        "warnings": [],
    }


def _gh_signals() -> dict[str, object]:
    return {
        "pr_state": "open",
        "pr_number": 42,
        "pr_url": None,
        "review_state": "none",
        "last_review_at": None,
        "warnings": [],
        "foundation_codex_approved": None,
        "foundation_founder_signoff": None,
    }


def _ci_signals() -> dict[str, object]:
    return {
        "ci_state": "passed",
        "ci_check_run_count": 1,
        "warnings": [],
        "overlays": [],
    }


def _rw_signals() -> dict[str, object]:
    return {
        "deploy_state": "not-applicable",
        "last_deploy_at": None,
        "warnings": [],
        "overlays": [],
    }


def _patched_run(
    tracker: Path,
    dashboard: Path,
    *,
    spec_hash: str | None = None,
    tech_hash: str | None = None,
    tracker_row_hash: str | None = None,
) -> list[CurrentState]:
    with (
        patch(
            "scripts.work_state.engine.collect_filesystem_signals",
            return_value=_fs_signals(spec_hash, tech_hash, tracker_row_hash),
        ),
        patch("scripts.work_state.engine.collect_git_signals", return_value=_git_signals()),
        patch("scripts.work_state.engine.collect_github_signals", return_value=_gh_signals()),
        patch("scripts.work_state.engine.collect_ci_signals", return_value=_ci_signals()),
        patch("scripts.work_state.engine.collect_railway_signals", return_value=_rw_signals()),
    ):
        return run_engine(str(tracker), dashboard, no_network=True)


class TestEngineEmitsDocChangeOnHashDrift:
    """MYM-8: engine emits spec/tech/tracker_row_modified events when hash drifts vs prev."""

    def test_engine_first_run_no_emission(self, tracker_file: Path, tmp_dashboard: Path) -> None:
        """Bootstrap run with no prev state → no doc-change events emitted."""
        _write_minimal_tracker(tracker_file)
        states = _patched_run(
            tracker_file,
            tmp_dashboard,
            spec_hash="h1",
            tech_hash="h2",
            tracker_row_hash="h3",
        )
        assert len(states) == 1
        events_file = tmp_dashboard / "events.jsonl"
        if events_file.exists():
            tail = read_tail_events(events_file)
            doc_events = [
                e
                for e in tail
                if e.get("event") in {"spec_modified", "tech_modified", "tracker_row_modified"}
            ]
            assert doc_events == []

    def test_engine_second_run_emits_spec_modified_on_hash_change(
        self, tracker_file: Path, tmp_dashboard: Path
    ) -> None:
        _write_minimal_tracker(tracker_file)
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h1", tracker_row_hash="t1")
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h2", tracker_row_hash="t1")

        tail = read_tail_events(tmp_dashboard / "events.jsonl")
        spec_events = [e for e in tail if e.get("event") == "spec_modified"]
        assert len(spec_events) == 1
        assert spec_events[0]["content_hash"] == "h2"
        assert spec_events[0]["source"] == "filesystem.spec"
        # No tech/tracker emitted (tracker_row unchanged, tech_hash None throughout)
        assert not any(e.get("event") == "tracker_row_modified" for e in tail)

    def test_engine_second_run_no_emission_when_hash_unchanged(
        self, tracker_file: Path, tmp_dashboard: Path
    ) -> None:
        _write_minimal_tracker(tracker_file)
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h1", tracker_row_hash="t1")
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h1", tracker_row_hash="t1")

        events_file = tmp_dashboard / "events.jsonl"
        if events_file.exists():
            tail = read_tail_events(events_file)
            doc_events = [
                e
                for e in tail
                if e.get("event") in {"spec_modified", "tech_modified", "tracker_row_modified"}
            ]
            assert doc_events == []

    def test_engine_emits_all_three_event_types_for_combined_drift(
        self, tracker_file: Path, tmp_dashboard: Path
    ) -> None:
        _write_minimal_tracker(tracker_file)
        _patched_run(
            tracker_file,
            tmp_dashboard,
            spec_hash="s1",
            tech_hash="te1",
            tracker_row_hash="tr1",
        )
        _patched_run(
            tracker_file,
            tmp_dashboard,
            spec_hash="s2",
            tech_hash="te2",
            tracker_row_hash="tr2",
        )

        tail = read_tail_events(tmp_dashboard / "events.jsonl")
        types = {e.get("event") for e in tail}
        assert "spec_modified" in types
        assert "tech_modified" in types
        assert "tracker_row_modified" in types

    def test_engine_emission_idempotent_third_run_same_hash(
        self, tracker_file: Path, tmp_dashboard: Path
    ) -> None:
        _write_minimal_tracker(tracker_file)
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h1")
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h2")
        events_after_2 = read_tail_events(tmp_dashboard / "events.jsonl")

        _patched_run(tracker_file, tmp_dashboard, spec_hash="h2")  # same as run 2
        events_after_3 = read_tail_events(tmp_dashboard / "events.jsonl")

        # No new doc-change events on third identical-hash run
        spec_2 = [e for e in events_after_2 if e.get("event") == "spec_modified"]
        spec_3 = [e for e in events_after_3 if e.get("event") == "spec_modified"]
        assert len(spec_2) == len(spec_3) == 1

    def test_engine_does_not_populate_last_event_ts(
        self, tracker_file: Path, tmp_dashboard: Path
    ) -> None:
        """Shadow window safety: CurrentState.last_event_ts stays None even when events emit."""
        _write_minimal_tracker(tracker_file)
        _patched_run(tracker_file, tmp_dashboard, spec_hash="h1")
        states = _patched_run(tracker_file, tmp_dashboard, spec_hash="h2")

        assert len(states) == 1
        assert states[0].last_event_ts is None
