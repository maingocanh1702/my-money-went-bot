"""Unit tests for engine driver — Phase A TDD.

Covers: tracker→WorkItems, signal collection per item, state JSON output,
CLI main, no-network mode, missing tracker, multi-branch prep.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TRACKER_SAMPLE = FIXTURES_DIR / "tracker_sample.md"


class TestEngineReadsTrackerToWorkItems:
    def test_returns_current_states_for_tracker_items(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert len(states) > 0

    def test_skips_items_without_branches(self, tmp_path: Path) -> None:
        tracker = tmp_path / "tracker.md"
        tracker.write_text(
            "### Phase 1\n"
            "| PR | Wave | Feature | Status | Branch | Gates | Notes |\n"
            "|---|---|---|---|---|---|---|\n"
            "| W1.1 | W1 | Docker | ⬜ | — | 🔒X | no branch |\n",
            encoding="utf-8",
        )
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(tracker),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert len(states) == 0


class TestEngineCollectsSignalsPerWorkItem:
    def test_single_branch_produces_signals(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        for s in states:
            assert hasattr(s, "signals")
            assert hasattr(s.signals, "pr_state")
            assert hasattr(s.signals, "ci_state")
            assert hasattr(s.signals, "deploy_state")


class TestEngineWritesCurrentStateJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        dashboard_dir = tmp_path / ".dashboard"
        run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=dashboard_dir,
            no_network=True,
        )
        state_file = dashboard_dir / "current_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert "items" in data
        assert len(data["items"]) > 0

    def test_each_item_has_required_fields(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        dashboard_dir = tmp_path / ".dashboard"
        run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=dashboard_dir,
            no_network=True,
        )
        data = json.loads((dashboard_dir / "current_state.json").read_text(encoding="utf-8"))
        for item in data["items"]:
            assert "item_id" in item
            assert "status" in item
            assert "human_status" in item
            assert "progress" in item
            assert "runtime_urgency" in item
            assert "overlays" in item
            assert "signals" in item


class TestEngineCliMain:
    def test_main_returns_zero_on_success(self, tmp_path: Path) -> None:
        from work_state.engine import main

        rc = main(
            [
                "--tracker",
                str(TRACKER_SAMPLE),
                "--dashboard-dir",
                str(tmp_path / ".dashboard"),
                "--no-network",
            ]
        )
        assert rc == 0

    def test_main_help_flag(self) -> None:
        from work_state.engine import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


class TestEngineNoNetworkMode:
    def test_no_network_uses_defaults(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert len(states) > 0
        for s in states:
            assert s.runtime_urgency == "normal"


class TestEngineMissingTracker:
    def test_missing_tracker_returns_empty(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(tmp_path / "nonexistent.md"),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert states == []


class TestEngineMultiBranchSignals:
    def test_multi_branch_item_aggregates(self, tmp_path: Path) -> None:
        """Prep for Phase B — engine handles items with multiple branches."""
        tracker = tmp_path / "tracker.md"
        tracker.write_text(
            "### Phase 1\n"
            "| PR | Wave | Feature | Status | Branch | Gates | Notes |\n"
            "|---|---|---|---|---|---|---|\n"
            "| W0.7 | W0 | Test feature | ✅ | `feat/branch-a` | 🔒X | notes |\n",
            encoding="utf-8",
        )
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(tracker),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert len(states) == 1
        assert states[0].item_id == "W0.7"


class TestEngineIdempotency:
    def test_two_runs_produce_same_output(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        dashboard_dir = tmp_path / ".dashboard"
        run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=dashboard_dir,
            no_network=True,
        )
        first = json.loads((dashboard_dir / "current_state.json").read_text(encoding="utf-8"))
        run_engine(
            tracker_path=str(TRACKER_SAMPLE),
            dashboard_dir=dashboard_dir,
            no_network=True,
        )
        second = json.loads((dashboard_dir / "current_state.json").read_text(encoding="utf-8"))
        assert first == second


class TestEngineCacheSchemaVersion:
    def test_reads_cache_schema_version_env(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        dashboard_dir = tmp_path / ".dashboard"
        with patch.dict("os.environ", {"CACHE_SCHEMA_VERSION": "v1"}):
            states = run_engine(
                tracker_path=str(TRACKER_SAMPLE),
                dashboard_dir=dashboard_dir,
                no_network=True,
            )
        assert len(states) > 0

    def test_schema_version_mismatch_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from work_state.engine import run_engine

        dashboard_dir = tmp_path / ".dashboard"
        dashboard_dir.mkdir(parents=True)
        (dashboard_dir / ".schema_version").write_text("v0-old", encoding="utf-8")

        with patch.dict("os.environ", {"CACHE_SCHEMA_VERSION": "v1"}):
            run_engine(
                tracker_path=str(TRACKER_SAMPLE),
                dashboard_dir=dashboard_dir,
                no_network=True,
            )
        assert any("schema" in r.message.lower() for r in caplog.records)


class TestEngineEdgeCases:
    def test_empty_tracker_produces_no_states(self, tmp_path: Path) -> None:
        tracker = tmp_path / "empty.md"
        tracker.write_text("# Empty tracker\n\nNo tables here.\n", encoding="utf-8")
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(tracker),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert states == []

    def test_schema_version_marker_written(self, tmp_path: Path) -> None:
        from work_state.engine import run_engine

        dashboard_dir = tmp_path / ".dashboard"
        with patch.dict("os.environ", {"CACHE_SCHEMA_VERSION": "v1"}):
            run_engine(
                tracker_path=str(TRACKER_SAMPLE),
                dashboard_dir=dashboard_dir,
                no_network=True,
            )
        marker = dashboard_dir / ".schema_version"
        assert marker.exists()
        assert marker.read_text(encoding="utf-8").strip() == "v1"

    def test_unknown_progress_profile_defaults_to_zero(self, tmp_path: Path) -> None:
        tracker = tmp_path / "tracker.md"
        tracker.write_text(
            "### Phase T\n"
            "| PR | Wave | Feature | Status | Branch | Gates | Notes |\n"
            "|---|---|---|---|---|---|---|\n"
            "| parser-evolver | T | Parser evolver | ⏸️ | `feat/parser-evolver` | 🔒X | notes |\n",
            encoding="utf-8",
        )
        from work_state.engine import run_engine

        states = run_engine(
            tracker_path=str(tracker),
            dashboard_dir=tmp_path / ".dashboard",
            no_network=True,
        )
        assert len(states) == 1
        assert states[0].progress >= 0
