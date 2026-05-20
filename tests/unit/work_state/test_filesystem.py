"""Tests for filesystem signal collector per spec §6.1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts.work_state.models import WorkItem


def _make_item(**overrides: object) -> WorkItem:
    defaults: dict[str, object] = {
        "id": "funding-sources",
        "linear_id": None,
        "feature_id": "funding-sources",
        "title": "Test",
        "type": "feature",
        "phase": "2",
        "priority": "P1",
        "risk_tier": "P1",
        "lane": "Standard",
        "owner": "founder",
        "deadline": None,
        "specs": {"product": None, "tech": None},
        "branches": [],
        "acceptance": [],
        "dependencies": [],
        "external_blockers": [],
        "decision_needed": None,
        "progress_profile": "standard_feature",
    }
    defaults.update(overrides)
    return WorkItem(**defaults)  # type: ignore[arg-type]


class TestSpecExists:
    def test_spec_exists_true(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        spec_file = tmp_path / "docs" / "features" / "feature-funding-sources.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Spec")
        item = _make_item(
            specs={"product": str(spec_file), "tech": None},
        )
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_exists"] is True

    def test_spec_exists_false(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        item = _make_item(
            specs={"product": str(tmp_path / "nonexistent.md"), "tech": None},
        )
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_exists"] is False

    def test_spec_none_path(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        item = _make_item(specs={"product": None, "tech": None})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_exists"] is False
        assert "missing_spec_link" in signals["warnings"]


class TestTechExists:
    def test_tech_exists_true(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        tech_file = tmp_path / "docs" / "features" / "BE" / "feature-funding-sources-tech.md"
        tech_file.parent.mkdir(parents=True)
        tech_file.write_text("# Tech")
        item = _make_item(
            specs={"product": None, "tech": str(tech_file)},
        )
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["tech_exists"] is True

    def test_tech_exists_false(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        item = _make_item(
            specs={"product": None, "tech": str(tmp_path / "nonexistent.md")},
        )
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["tech_exists"] is False

    def test_missing_tech_link_warning(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        item = _make_item(specs={"product": None, "tech": None})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert "missing_tech_link" in signals["warnings"]


class TestPossibleSpecMoved:
    def test_possible_spec_moved_detected(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        features_dir = tmp_path / "docs" / "features"
        features_dir.mkdir(parents=True)
        (features_dir / "feature-funding-sources-v2.md").write_text("# Renamed")

        item = _make_item(
            specs={
                "product": str(features_dir / "feature-funding-sources.md"),
                "tech": None,
            },
        )
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_exists"] is False
        assert "possible_spec_moved" in signals["warnings"]

    def test_no_false_positive_when_spec_exists(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        features_dir = tmp_path / "docs" / "features"
        features_dir.mkdir(parents=True)
        spec_file = features_dir / "feature-funding-sources.md"
        spec_file.write_text("# Spec")

        item = _make_item(specs={"product": str(spec_file), "tech": None})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert "possible_spec_moved" not in signals["warnings"]


class TestUnknownSafe:
    def test_no_crash_on_oserror(self, tmp_path: Path) -> None:
        from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals

        item = _make_item(
            specs={"product": "/nonexistent/path/spec.md", "tech": None},
        )
        with patch("pathlib.Path.is_file", side_effect=OSError("Permission denied")):
            signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_exists"] is False
        assert signals["tech_exists"] is False
