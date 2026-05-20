"""Tests for state_store — .dashboard/ JSON IO per spec §7.3."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.work_state.models import CurrentState, Signals


def _make_state(item_id: str = "test-item") -> CurrentState:
    signals = Signals(
        spec_exists=True,
        tech_exists=False,
        branch_exists=True,
        commits_count=5,
        last_commit_sha="abc123",
        pr_state="open",
        pr_number=42,
        review_state="none",
        ci_state="none",
        deploy_state="unknown",
        warnings=["missing_tech_link"],
    )
    return CurrentState(
        item_id=item_id,
        status="in-review",
        human_status="IN_PROGRESS",
        progress=60,
        runtime_urgency="normal",
        overlays=[],
        signals=signals,
        last_event_ts="2026-05-19T08:00:00Z",
    )


class TestWriteCurrentState:
    def test_writes_json_file(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import write_current_state

        dashboard_dir = tmp_path / ".dashboard"
        states = [_make_state("item-1"), _make_state("item-2")]
        write_current_state(states, dashboard_dir)

        state_file = dashboard_dir / "current_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert len(data["items"]) == 2
        assert data["items"][0]["item_id"] == "item-1"

    def test_creates_directory(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import write_current_state

        dashboard_dir = tmp_path / ".dashboard" / "nested"
        write_current_state([_make_state()], dashboard_dir)
        assert (dashboard_dir / "current_state.json").exists()

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import write_current_state

        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state("old")], dashboard_dir)
        write_current_state([_make_state("new")], dashboard_dir)
        data = json.loads((dashboard_dir / "current_state.json").read_text())
        assert data["items"][0]["item_id"] == "new"


class TestReadCurrentState:
    def test_reads_written_state(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import read_current_state, write_current_state

        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state("test")], dashboard_dir)
        result = read_current_state(dashboard_dir)
        assert result is not None
        items = result["items"]
        assert isinstance(items, list)
        assert len(items) == 1

    def test_returns_none_missing_file(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import read_current_state

        result = read_current_state(tmp_path / ".dashboard")
        assert result is None

    def test_returns_none_empty_dir(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import read_current_state

        dashboard_dir = tmp_path / ".dashboard"
        dashboard_dir.mkdir()
        result = read_current_state(dashboard_dir)
        assert result is None


class TestDataclassSerialization:
    def test_signals_serialized(self, tmp_path: Path) -> None:
        from scripts.work_state.state_store import write_current_state

        dashboard_dir = tmp_path / ".dashboard"
        write_current_state([_make_state()], dashboard_dir)
        data = json.loads((dashboard_dir / "current_state.json").read_text())
        item_data = data["items"][0]
        assert "signals" in item_data
        assert item_data["signals"]["spec_exists"] is True
        assert item_data["signals"]["warnings"] == ["missing_tech_link"]
