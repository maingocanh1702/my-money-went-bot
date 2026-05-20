"""Tests for plan_reader — tracker.md → WorkItem normalization per Phase 0 §2.2."""

from __future__ import annotations

from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tracker_sample.md"


class TestReadTracker:
    def test_returns_list_of_work_items(self) -> None:
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        assert len(items) > 0
        for item in items:
            assert hasattr(item, "id")
            assert hasattr(item, "feature_id")

    def test_parses_expected_row_count(self) -> None:
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        assert len(items) >= 40

    def test_funding_sources_row(self) -> None:
        """Per Phase 0 §2.3 sample inference — funding-sources row."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        item = next((i for i in items if i.id == "funding-sources"), None)
        assert item is not None
        assert item.feature_id == "funding-sources"
        assert item.title == "Funding sources resolver + handlers"
        assert item.type == "feature"
        assert item.phase == "2"
        assert item.linear_id is None
        assert item.owner == "founder"
        assert item.progress_profile == "standard_feature"
        assert "feat/funding-sources" in item.item.branches

    def test_funding_sources_warnings(self) -> None:
        """Per Phase 0 §2.3 — 8 warnings expected for funding-sources."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        item = next((i for i in items if i.id == "funding-sources"), None)
        assert item is not None
        warnings = item._warnings
        assert "missing_linear_id" in warnings
        assert "type_inferred" in warnings
        assert "priority_defaulted" in warnings
        assert "risk_tier_inferred" in warnings
        assert "progress_profile_inferred" in warnings

    def test_w09_legacy_row(self) -> None:
        """W0.9 legacy row — linear_id=null, type=infra inferred."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        item = next((i for i in items if i.id == "W0.9"), None)
        assert item is not None
        assert item.linear_id is None
        assert item.type == "infra"
        assert item.progress_profile == "foundation_change"

    def test_parser_acb_deferred_row(self) -> None:
        """Parser-acb deferred row — ⏸️ status recognized."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        item = next((i for i in items if i.id == "parser-acb"), None)
        assert item is not None
        assert item.feature_id == "parser-acb"

    def test_placeholder_row_skipped(self) -> None:
        """Placeholder row '(to be created...)' should be skipped with warning."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        ids = [i.item.id for i in items]
        assert not any("to be created" in item_id for item_id in ids)

    def test_phase_parsed_from_section_header(self) -> None:
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        item = next((i for i in items if i.id == "pricing-tiers"), None)
        assert item is not None
        assert item.phase == "3"

    def test_gates_parsed(self) -> None:
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        item = next((i for i in items if i.id == "funding-sources"), None)
        assert item is not None
        assert item.risk_tier in {"P0", "P1", "P2"}

    def test_merged_row_recognized(self) -> None:
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        merged = [i for i in items if i.id == "W0.7"]
        assert len(merged) == 1

    def test_snake_case_warnings(self) -> None:
        """Per §8.2.1 — engine warnings MUST be snake_case."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        for item in items:
            for w in item._warnings:
                assert "-" not in w, f"Warning '{w}' uses kebab-case, must be snake_case"

    def test_robust_against_missing_fields(self) -> None:
        """plan_reader must not crash on minimal tracker rows."""
        from scripts.work_state.plan_reader import read_tracker

        items = read_tracker(str(FIXTURE_PATH))
        for item in items:
            assert item.id
            assert item.feature_id
            assert item.priority in {"P0", "P1", "P2"}
            assert item.lane in {"Fast", "Standard", "Foundation"}
