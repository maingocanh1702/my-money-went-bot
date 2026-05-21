"""Tests for doc-change overlay emission (Phase B) per spec §8.2 + B3-B6."""

from __future__ import annotations

from scripts.work_state.models import Signals
from scripts.work_state.status_machine import compute_overlays


def _make_signals(**overrides: object) -> Signals:
    defaults: dict[str, object] = {
        "spec_exists": True,
        "tech_exists": True,
        "branch_exists": True,
        "commits_count": 5,
        "last_commit_sha": "abc123",
        "pr_state": "open",
        "pr_number": 42,
        "review_state": "none",
        "ci_state": "pass",
        "deploy_state": "unknown",
        "warnings": [],
    }
    defaults.update(overrides)
    return Signals(**defaults)  # type: ignore[arg-type]


class TestSpecModifiedOverlay:
    """B3 + B4: spec-modified overlay when hash changes."""

    def test_spec_modified_overlay_when_hash_differs(self) -> None:
        signals = _make_signals(spec_hash="new_hash")
        prev_spec_hash = "old_hash"
        overlays = compute_overlays(signals, base_status="in-review", prev_spec_hash=prev_spec_hash)
        assert "spec-modified" in overlays

    def test_no_spec_modified_when_hash_same(self) -> None:
        signals = _make_signals(spec_hash="same_hash")
        overlays = compute_overlays(signals, base_status="in-review", prev_spec_hash="same_hash")
        assert "spec-modified" not in overlays

    def test_no_spec_modified_when_no_prev_hash(self) -> None:
        signals = _make_signals(spec_hash="new_hash")
        overlays = compute_overlays(signals, base_status="in-review", prev_spec_hash=None)
        assert "spec-modified" not in overlays


class TestTechModifiedOverlay:
    """B3 + B4: tech-modified overlay when hash changes."""

    def test_tech_modified_overlay_when_hash_differs(self) -> None:
        signals = _make_signals(tech_hash="new_hash")
        overlays = compute_overlays(signals, base_status="in-review", prev_tech_hash="old_hash")
        assert "tech-modified" in overlays

    def test_no_tech_modified_when_hash_same(self) -> None:
        signals = _make_signals(tech_hash="same_hash")
        overlays = compute_overlays(signals, base_status="in-review", prev_tech_hash="same_hash")
        assert "tech-modified" not in overlays


class TestTrackerModifiedOverlay:
    """B3 + B4: tracker-modified overlay when semantic hash changes."""

    def test_tracker_modified_overlay_when_hash_differs(self) -> None:
        signals = _make_signals(tracker_row_hash="new_hash")
        overlays = compute_overlays(
            signals, base_status="in-review", prev_tracker_row_hash="old_hash"
        )
        assert "tracker-modified" in overlays

    def test_no_tracker_modified_when_hash_same(self) -> None:
        signals = _make_signals(tracker_row_hash="same_hash")
        overlays = compute_overlays(
            signals, base_status="in-review", prev_tracker_row_hash="same_hash"
        )
        assert "tracker-modified" not in overlays


class TestPostShipDocChange:
    """B6: post-ship-doc-change overlay on terminal state rows."""

    def test_post_ship_doc_change_when_merged_and_spec_modified(self) -> None:
        signals = _make_signals(
            spec_hash="new_hash",
            pr_state="merged",
            deploy_state="unknown",
        )
        overlays = compute_overlays(signals, base_status="merged", prev_spec_hash="old_hash")
        assert "post-ship-doc-change" in overlays

    def test_post_ship_doc_change_when_deployed_and_tech_modified(self) -> None:
        signals = _make_signals(
            tech_hash="new_hash",
            deploy_state="deployed",
        )
        overlays = compute_overlays(signals, base_status="deployed", prev_tech_hash="old_hash")
        assert "post-ship-doc-change" in overlays

    def test_post_ship_doc_change_when_abandoned_and_tracker_modified(self) -> None:
        signals = _make_signals(
            tracker_row_hash="new_hash",
            pr_state="closed",
        )
        overlays = compute_overlays(
            signals, base_status="abandoned", prev_tracker_row_hash="old_hash"
        )
        assert "post-ship-doc-change" in overlays

    def test_no_post_ship_when_active_and_spec_modified(self) -> None:
        signals = _make_signals(spec_hash="new_hash")
        overlays = compute_overlays(signals, base_status="in-review", prev_spec_hash="old_hash")
        assert "spec-modified" in overlays
        assert "post-ship-doc-change" not in overlays


class TestCanonicalOverlayEnum:
    """B4: 4 new overlays exist in canonical enum (18 total)."""

    def test_4_new_overlays_recognized(self) -> None:
        from scripts.work_state.status_machine import CANONICAL_OVERLAYS

        new_overlays = {
            "spec-modified",
            "tech-modified",
            "tracker-modified",
            "post-ship-doc-change",
        }
        assert new_overlays.issubset(CANONICAL_OVERLAYS)

    def test_canonical_enum_has_18_entries(self) -> None:
        from scripts.work_state.status_machine import CANONICAL_OVERLAYS

        assert len(CANONICAL_OVERLAYS) == 18
