"""Tests for event_engine — signal diff + write-time dedup per spec §7.2.1."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.work_state.models import Event


class TestEventDedup:
    def test_spec_created_dedup_by_artifact_path(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event = Event(
            ts="2026-05-19T06:12:00Z",
            item="MYM-108",
            event="spec_created",
            from_status="not-started",
            to_status="spec-only",
            source="filesystem",
            artifact="docs/features/feature-funding-sources.md",
        )
        append_event(event, events_file)
        assert is_duplicate(event, events_file)

    def test_spec_created_different_artifact_not_dup(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event1 = Event(
            ts="2026-05-19T06:12:00Z",
            item="MYM-108",
            event="spec_created",
            from_status="not-started",
            to_status="spec-only",
            source="filesystem",
            artifact="docs/features/feature-funding-sources.md",
        )
        append_event(event1, events_file)

        event2 = Event(
            ts="2026-05-19T07:00:00Z",
            item="MYM-108",
            event="spec_created",
            from_status=None,
            to_status=None,
            source="filesystem",
            artifact="docs/features/feature-funding-sources-v2.md",
        )
        assert not is_duplicate(event2, events_file)

    def test_ci_events_keyed_by_check_run_id(self, tmp_path: Path) -> None:
        """CI events re-emit per check_run_id per spec §7.2.1."""
        from scripts.work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event1 = Event(
            ts="2026-05-19T08:00:00Z",
            item="MYM-108",
            event="ci_failed",
            from_status=None,
            to_status=None,
            source="github",
            artifact="check_run_100",
            pr_number=42,
            overlay="ci-failing",
        )
        append_event(event1, events_file)
        assert is_duplicate(event1, events_file)

        event2 = Event(
            ts="2026-05-19T09:00:00Z",
            item="MYM-108",
            event="ci_failed",
            from_status=None,
            to_status=None,
            source="github",
            artifact="check_run_101",
            pr_number=42,
            overlay="ci-failing",
        )
        assert not is_duplicate(event2, events_file)

    def test_stale_detected_max_once_per_24h(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event1 = Event(
            ts="2026-05-19T06:00:00Z",
            item="MYM-108",
            event="stale_detected",
            from_status=None,
            to_status=None,
            source="event_engine",
            artifact="14",
        )
        append_event(event1, events_file)

        event2 = Event(
            ts="2026-05-19T12:00:00Z",
            item="MYM-108",
            event="stale_detected",
            from_status=None,
            to_status=None,
            source="event_engine",
            artifact="14",
        )
        assert is_duplicate(event2, events_file)

        event3 = Event(
            ts="2026-05-20T07:00:00Z",
            item="MYM-108",
            event="stale_detected",
            from_status=None,
            to_status=None,
            source="event_engine",
            artifact="14",
        )
        assert not is_duplicate(event3, events_file)

    def test_branch_created_dedup(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event = Event(
            ts="2026-05-19T06:00:00Z",
            item="MYM-108",
            event="branch_created",
            from_status=None,
            to_status=None,
            source="git",
            artifact="feat/funding-sources",
        )
        append_event(event, events_file)
        assert is_duplicate(event, events_file)


class TestTailBoundedRead:
    def test_reads_last_100_entries(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import read_tail_events

        events_file = tmp_path / "events.jsonl"
        for i in range(150):
            line = json.dumps(
                {
                    "ts": f"2026-05-19T{i:04d}",
                    "item": "test",
                    "event": "commit_added",
                    "artifact": f"sha_{i}",
                    "source": "git",
                }
            )
            with events_file.open("a") as f:
                f.write(line + "\n")

        tail = read_tail_events(events_file)
        assert len(tail) == 100

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import read_tail_events

        events_file = tmp_path / "events.jsonl"
        assert read_tail_events(events_file) == []

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import read_tail_events

        events_file = tmp_path / "nonexistent.jsonl"
        assert read_tail_events(events_file) == []


class TestAppendEvent:
    def test_append_creates_file(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import append_event

        events_file = tmp_path / "events.jsonl"
        event = Event(
            ts="2026-05-19T06:12:00Z",
            item="test",
            event="spec_created",
            from_status="not-started",
            to_status="spec-only",
            source="filesystem",
            artifact="test.md",
        )
        append_event(event, events_file)
        assert events_file.exists()
        lines = events_file.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["item"] == "test"
        assert data["event"] == "spec_created"

    def test_append_only_no_modify(self, tmp_path: Path) -> None:
        from scripts.work_state.event_engine import append_event

        events_file = tmp_path / "events.jsonl"
        for i in range(3):
            event = Event(
                ts=f"2026-05-19T0{i}:00:00Z",
                item="test",
                event="commit_added",
                from_status=None,
                to_status=None,
                source="git",
                artifact=f"sha_{i}",
            )
            append_event(event, events_file)
        lines = events_file.read_text().strip().splitlines()
        assert len(lines) == 3
