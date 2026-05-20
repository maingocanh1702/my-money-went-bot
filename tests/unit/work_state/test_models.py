"""Tests for work-state engine dataclass models per spec §11.2."""

from __future__ import annotations

import pytest


class TestWorkItem:
    def test_work_item_has_all_required_fields(self) -> None:
        from scripts.work_state.models import WorkItem

        item = WorkItem(
            id="funding-sources",
            linear_id="MYM-108",
            feature_id="funding-sources",
            title="Funding sources resolver + handlers",
            type="feature",
            phase="2",
            priority="P1",
            risk_tier="P1",
            lane="Standard",
            owner="founder",
            deadline=None,
            specs={"product": "docs/features/feature-funding-sources.md", "tech": None},
            branches=["feat/funding-sources"],
            acceptance=["FS resolved before any transaction INSERT"],
            dependencies=["W0.2"],
            external_blockers=[],
            decision_needed=None,
            progress_profile="standard_feature",
        )
        assert item.id == "funding-sources"
        assert item.linear_id == "MYM-108"
        assert item.feature_id == "funding-sources"
        assert item.type == "feature"
        assert item.phase == "2"
        assert item.priority == "P1"
        assert item.risk_tier == "P1"
        assert item.lane == "Standard"
        assert item.owner == "founder"
        assert item.deadline is None
        assert item.specs["product"] == "docs/features/feature-funding-sources.md"
        assert item.branches == ["feat/funding-sources"]
        assert item.acceptance == ["FS resolved before any transaction INSERT"]
        assert item.dependencies == ["W0.2"]
        assert item.external_blockers == []
        assert item.decision_needed is None
        assert item.progress_profile == "standard_feature"
        assert item.manual_state_override is None

    def test_work_item_frozen(self) -> None:
        from scripts.work_state.models import WorkItem

        item = WorkItem(
            id="W0.9",
            linear_id=None,
            feature_id="dashboard-realtime",
            title="Dashboard realtime",
            type="infra",
            phase="1",
            priority="P1",
            risk_tier="P1",
            lane="Standard",
            owner="founder",
            deadline=None,
            specs={"product": None, "tech": None},
            branches=["feat/dashboard-realtime"],
            acceptance=[],
            dependencies=[],
            external_blockers=[],
            decision_needed=None,
            progress_profile="foundation_change",
        )
        with pytest.raises(AttributeError):
            item.id = "changed"  # type: ignore[misc]

    def test_work_item_linear_id_optional(self) -> None:
        from scripts.work_state.models import WorkItem

        item = WorkItem(
            id="W0.9",
            linear_id=None,
            feature_id="dashboard-realtime",
            title="Dashboard realtime",
            type="infra",
            phase="1",
            priority="P1",
            risk_tier="P1",
            lane="Standard",
            owner="founder",
            deadline=None,
            specs={"product": None, "tech": None},
            branches=[],
            acceptance=[],
            dependencies=[],
            external_blockers=[],
            decision_needed=None,
            progress_profile="foundation_change",
        )
        assert item.linear_id is None

    def test_work_item_repr(self) -> None:
        from scripts.work_state.models import WorkItem

        item = WorkItem(
            id="test-item",
            linear_id=None,
            feature_id="test-item",
            title="Test",
            type="feature",
            phase="1",
            priority="P1",
            risk_tier="P1",
            lane="Standard",
            owner="founder",
            deadline=None,
            specs={"product": None, "tech": None},
            branches=[],
            acceptance=[],
            dependencies=[],
            external_blockers=[],
            decision_needed=None,
            progress_profile="standard_feature",
        )
        r = repr(item)
        assert "test-item" in r
        assert "WorkItem" in r

    def test_work_item_separate_id_and_linear_id(self) -> None:
        """Per spec §11.2 + Codex round 1 Finding 1: id and linear_id are separate."""
        from scripts.work_state.models import WorkItem

        item = WorkItem(
            id="funding-sources",
            linear_id="MYM-108",
            feature_id="funding-sources",
            title="Test",
            type="feature",
            phase="2",
            priority="P1",
            risk_tier="P1",
            lane="Standard",
            owner="founder",
            deadline=None,
            specs={"product": None, "tech": None},
            branches=[],
            acceptance=[],
            dependencies=[],
            external_blockers=[],
            decision_needed=None,
            progress_profile="standard_feature",
        )
        assert item.id != item.linear_id
        assert item.id == "funding-sources"
        assert item.linear_id == "MYM-108"


class TestManualOverride:
    def test_manual_override_fields(self) -> None:
        from scripts.work_state.models import ManualOverride

        override = ManualOverride(
            status="in-monitoring",
            reason="production monitoring for first 7 days",
            until="2026-05-26",
        )
        assert override.status == "in-monitoring"
        assert override.reason == "production monitoring for first 7 days"
        assert override.until == "2026-05-26"

    def test_manual_override_frozen(self) -> None:
        from scripts.work_state.models import ManualOverride

        override = ManualOverride(status="in-monitoring", reason="test", until="2026-05-26")
        with pytest.raises(AttributeError):
            override.status = "changed"  # type: ignore[misc]


class TestSignals:
    def test_signals_mutable(self) -> None:
        from scripts.work_state.models import Signals

        signals = Signals(
            spec_exists=True,
            tech_exists=False,
            branch_exists=True,
            commits_count=5,
            last_commit_sha="abc123",
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="none",
            deploy_state="unknown",
            warnings=[],
        )
        signals.warnings.append("missing_tech_link")
        assert "missing_tech_link" in signals.warnings
        signals.spec_exists = False
        assert signals.spec_exists is False

    def test_signals_warnings_list(self) -> None:
        from scripts.work_state.models import Signals

        signals = Signals(
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
            warnings=["missing_spec_link", "git_unknown"],
        )
        assert len(signals.warnings) == 2


class TestCurrentState:
    def test_current_state_fields(self) -> None:
        from scripts.work_state.models import CurrentState, Signals

        signals = Signals(
            spec_exists=True,
            tech_exists=True,
            branch_exists=True,
            commits_count=10,
            last_commit_sha="def456",
            pr_state="open",
            pr_number=42,
            review_state="approved",
            ci_state="pass",
            deploy_state="unknown",
            warnings=[],
        )
        state = CurrentState(
            item_id="funding-sources",
            status="approved-pending-merge",
            human_status="IN_PROGRESS",
            progress=85,
            runtime_urgency="normal",
            overlays=[],
            signals=signals,
            last_event_ts="2026-05-19T08:10:00Z",
        )
        assert state.item_id == "funding-sources"
        assert state.status == "approved-pending-merge"
        assert state.human_status == "IN_PROGRESS"
        assert state.progress == 85
        assert state.runtime_urgency == "normal"
        assert state.overlays == []
        assert state.last_event_ts == "2026-05-19T08:10:00Z"

    def test_current_state_overlays_list(self) -> None:
        from scripts.work_state.models import CurrentState, Signals

        signals = Signals(
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
            warnings=["git_unknown"],
        )
        state = CurrentState(
            item_id="test",
            status="not-started",
            human_status="UNKNOWN",
            progress=0,
            runtime_urgency="warning",
            overlays=["unknown", "artifact-drift"],
            signals=signals,
            last_event_ts=None,
        )
        assert "unknown" in state.overlays
        assert "artifact-drift" in state.overlays


class TestEvent:
    def test_event_jsonl_shape(self) -> None:
        from scripts.work_state.models import Event

        event = Event(
            ts="2026-05-19T06:12:00Z",
            item="MYM-108",
            event="spec_created",
            from_status="not-started",
            to_status="spec-only",
            source="filesystem",
            artifact="docs/features/feature-funding-sources.md",
        )
        assert event.ts == "2026-05-19T06:12:00Z"
        assert event.item == "MYM-108"
        assert event.event == "spec_created"
        assert event.from_status == "not-started"
        assert event.to_status == "spec-only"
        assert event.source == "filesystem"
        assert event.artifact == "docs/features/feature-funding-sources.md"

    def test_event_optional_fields(self) -> None:
        from scripts.work_state.models import Event

        event = Event(
            ts="2026-05-19T08:10:00Z",
            item="MYM-108",
            event="ci_failed",
            from_status=None,
            to_status=None,
            source="github",
            artifact=None,
            pr_number=42,
            overlay="ci-failing",
        )
        assert event.pr_number == 42
        assert event.overlay == "ci-failing"
        assert event.from_status is None
        assert event.artifact is None

    def test_event_frozen(self) -> None:
        from scripts.work_state.models import Event

        event = Event(
            ts="2026-05-19T06:12:00Z",
            item="test",
            event="spec_created",
            from_status="not-started",
            to_status="spec-only",
            source="filesystem",
        )
        with pytest.raises(AttributeError):
            event.item = "changed"  # type: ignore[misc]
