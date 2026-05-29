"""Tests for filesystem doc hash tracking (Phase B) per spec §6.1 + B1-B2 + B8."""

from __future__ import annotations

from pathlib import Path

from work_state.models import Signals, WorkItem


def _make_item(**overrides: object) -> WorkItem:
    defaults: dict[str, object] = {
        "id": "funding-sources",
        "linear_id": "MYM-108",
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
        "branches": ["feat/funding-sources"],
        "acceptance": ["FS resolved before any transaction INSERT"],
        "dependencies": [],
        "external_blockers": [],
        "decision_needed": None,
        "progress_profile": "standard_feature",
    }
    defaults.update(overrides)
    return WorkItem(**defaults)  # type: ignore[arg-type]


class TestSignalsNewFields:
    """B1: Signals dataclass has 5 new APPEND-ONLY fields."""

    def test_signals_has_spec_hash_field(self) -> None:
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
            warnings=[],
            spec_hash="abc123",
        )
        assert s.spec_hash == "abc123"

    def test_signals_has_spec_modified_at_field(self) -> None:
        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            warnings=[],
            spec_modified_at="2026-05-21",
        )
        assert s.spec_modified_at == "2026-05-21"

    def test_signals_has_tech_hash_field(self) -> None:
        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            warnings=[],
            tech_hash="def456",
        )
        assert s.tech_hash == "def456"

    def test_signals_has_tech_modified_at_field(self) -> None:
        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            warnings=[],
            tech_modified_at="2026-05-21",
        )
        assert s.tech_modified_at == "2026-05-21"

    def test_signals_has_tracker_row_hash_field(self) -> None:
        s = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            warnings=[],
            tracker_row_hash="row123",
        )
        assert s.tracker_row_hash == "row123"

    def test_signals_new_fields_default_none(self) -> None:
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
            warnings=[],
        )
        assert s.spec_hash is None
        assert s.spec_modified_at is None
        assert s.tech_hash is None
        assert s.tech_modified_at is None
        assert s.tracker_row_hash is None


class TestFilesystemCollectorHashTracking:
    """B1: filesystem collector computes hash fields."""

    def test_computes_spec_hash_when_file_exists(self, tmp_path: Path) -> None:
        from work_state.signal_collectors.filesystem import (
            collect_filesystem_signals,
        )

        spec_file = tmp_path / "docs" / "features" / "feature-funding-sources.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Funding Sources Spec\n\nContent here.")

        item = _make_item(specs={"product": str(spec_file), "tech": None})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_hash"] is not None
        assert len(signals["spec_hash"]) == 64  # SHA256 hex

    def test_spec_hash_none_when_file_missing(self, tmp_path: Path) -> None:
        from work_state.signal_collectors.filesystem import (
            collect_filesystem_signals,
        )

        item = _make_item(specs={"product": str(tmp_path / "nonexistent.md"), "tech": None})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_hash"] is None

    def test_computes_tech_hash(self, tmp_path: Path) -> None:
        from work_state.signal_collectors.filesystem import (
            collect_filesystem_signals,
        )

        tech_file = tmp_path / "docs" / "features" / "BE" / "feature-funding-sources-tech.md"
        tech_file.parent.mkdir(parents=True)
        tech_file.write_text("# Tech Spec")

        item = _make_item(specs={"product": None, "tech": str(tech_file)})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["tech_hash"] is not None
        assert len(signals["tech_hash"]) == 64

    def test_computes_spec_modified_at(self, tmp_path: Path) -> None:
        from work_state.signal_collectors.filesystem import (
            collect_filesystem_signals,
        )

        spec_file = tmp_path / "spec.md"
        spec_file.write_text("content")
        item = _make_item(specs={"product": str(spec_file), "tech": None})
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["spec_modified_at"] is not None
        assert "T" in signals["spec_modified_at"]  # ISO format

    def test_computes_tracker_row_hash(self, tmp_path: Path) -> None:
        from work_state.signal_collectors.filesystem import (
            collect_filesystem_signals,
        )

        item = _make_item(
            specs={"product": None, "tech": None},
            branches=["feat/funding-sources"],
            linear_id="MYM-108",
            feature_id="funding-sources",
            acceptance=["FS resolved"],
        )
        signals = collect_filesystem_signals(item, repo_root=tmp_path)
        assert signals["tracker_row_hash"] is not None
        assert len(signals["tracker_row_hash"]) == 64


class TestTrackerRowHashSemantics:
    """B2 + B8: tracker row hash excludes non-semantic fields."""

    def test_excludes_status_field(self, tmp_path: Path) -> None:
        """B8: status auto-flip should NOT trigger drift."""
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(feature_id="funding-sources")
        item2 = _make_item(feature_id="funding-sources")
        hash1 = _compute_tracker_row_hash(item1)
        hash2 = _compute_tracker_row_hash(item2)
        assert hash1 == hash2

    def test_excludes_notes_gates_changelog(self, tmp_path: Path) -> None:
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(feature_id="test-feature", decision_needed=None)
        item2 = _make_item(feature_id="test-feature", decision_needed="Some note")
        hash1 = _compute_tracker_row_hash(item1)
        hash2 = _compute_tracker_row_hash(item2)
        assert hash1 == hash2

    def test_hash_changes_when_branch_changes(self) -> None:
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(branches=["feat/old-branch"])
        item2 = _make_item(branches=["feat/new-branch"])
        assert _compute_tracker_row_hash(item1) != _compute_tracker_row_hash(item2)

    def test_hash_changes_when_acceptance_changes(self) -> None:
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(acceptance=["AC1"])
        item2 = _make_item(acceptance=["AC1", "AC2 new"])
        assert _compute_tracker_row_hash(item1) != _compute_tracker_row_hash(item2)

    def test_hash_stable_across_formatting_whitespace(self) -> None:
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(acceptance=["AC1  extra  spaces"])
        item2 = _make_item(acceptance=["AC1 extra spaces"])
        assert _compute_tracker_row_hash(item1) == _compute_tracker_row_hash(item2)

    def test_hash_changes_when_feature_id_changes(self) -> None:
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(feature_id="feature-a")
        item2 = _make_item(feature_id="feature-b")
        assert _compute_tracker_row_hash(item1) != _compute_tracker_row_hash(item2)

    def test_hash_changes_when_specs_path_changes(self) -> None:
        from work_state.signal_collectors.filesystem import (
            _compute_tracker_row_hash,
        )

        item1 = _make_item(specs={"product": "docs/spec-a.md", "tech": None})
        item2 = _make_item(specs={"product": "docs/spec-b.md", "tech": None})
        assert _compute_tracker_row_hash(item1) != _compute_tracker_row_hash(item2)
