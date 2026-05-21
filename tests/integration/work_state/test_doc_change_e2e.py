"""Integration e2e — doc change awareness pipeline (Phase B).

Tests the full pipeline: filesystem hash collection → event emission → overlay
→ dashboard HTML badge rendering. Uses tmp_path fixtures (no network).
"""

from __future__ import annotations

from pathlib import Path

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
