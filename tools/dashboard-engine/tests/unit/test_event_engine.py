"""Tests for event_engine — signal diff + write-time dedup per spec §7.2.1."""

from __future__ import annotations

import json
from pathlib import Path

from work_state.models import Event


class TestEventDedup:
    def test_spec_created_dedup_by_artifact_path(self, tmp_path: Path) -> None:
        from work_state.event_engine import append_event, is_duplicate

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
        from work_state.event_engine import append_event, is_duplicate

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
        from work_state.event_engine import append_event, is_duplicate

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
        from work_state.event_engine import append_event, is_duplicate

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
        from work_state.event_engine import append_event, is_duplicate

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


class TestDocChangeHashDedup:
    """MYM-8: doc-change events (spec/tech/tracker_row_modified) dedup by content_hash."""

    def _make_event(
        self,
        event_type: str,
        artifact: str,
        content_hash: str | None,
        ts: str = "2026-05-21T09:00:00Z",
        item: str = "MYM-108",
    ) -> Event:
        return Event(
            ts=ts,
            item=item,
            event=event_type,
            from_status=None,
            to_status=None,
            source=f"filesystem.{event_type.split('_')[0]}",
            artifact=artifact,
            content_hash=content_hash,
        )

    def test_spec_modified_same_hash_dedupes(self, tmp_path: Path) -> None:
        from work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event_a = self._make_event(
            "spec_modified", "docs/features/feature-funding-sources.md", "hash_X"
        )
        append_event(event_a, events_file)

        event_b = self._make_event(
            "spec_modified",
            "docs/features/feature-funding-sources.md",
            "hash_X",
            ts="2026-05-21T10:00:00Z",
        )
        assert is_duplicate(event_b, events_file)

    def test_spec_modified_different_hash_reemits(self, tmp_path: Path) -> None:
        from work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event_a = self._make_event(
            "spec_modified", "docs/features/feature-funding-sources.md", "hash_X"
        )
        append_event(event_a, events_file)

        event_b = self._make_event(
            "spec_modified",
            "docs/features/feature-funding-sources.md",
            "hash_Y",
            ts="2026-05-21T10:00:00Z",
        )
        assert not is_duplicate(event_b, events_file)

    def test_tech_modified_hash_aware_dedup(self, tmp_path: Path) -> None:
        from work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event_a = self._make_event(
            "tech_modified", "docs/features/BE/feature-funding-sources-tech.md", "tech_hash_1"
        )
        append_event(event_a, events_file)

        same_hash = self._make_event(
            "tech_modified",
            "docs/features/BE/feature-funding-sources-tech.md",
            "tech_hash_1",
            ts="2026-05-21T11:00:00Z",
        )
        diff_hash = self._make_event(
            "tech_modified",
            "docs/features/BE/feature-funding-sources-tech.md",
            "tech_hash_2",
            ts="2026-05-21T11:00:00Z",
        )
        assert is_duplicate(same_hash, events_file)
        assert not is_duplicate(diff_hash, events_file)

    def test_tracker_row_modified_hash_aware_dedup(self, tmp_path: Path) -> None:
        from work_state.event_engine import append_event, is_duplicate

        events_file = tmp_path / "events.jsonl"
        event_a = self._make_event(
            "tracker_row_modified", "docs/implementation-tracker.md", "tracker_hash_1"
        )
        append_event(event_a, events_file)

        same_hash = self._make_event(
            "tracker_row_modified",
            "docs/implementation-tracker.md",
            "tracker_hash_1",
        )
        diff_hash = self._make_event(
            "tracker_row_modified",
            "docs/implementation-tracker.md",
            "tracker_hash_2",
        )
        assert is_duplicate(same_hash, events_file)
        assert not is_duplicate(diff_hash, events_file)

    def test_doc_change_dedup_key_includes_content_hash(self) -> None:
        from work_state.event_engine import _dedup_key

        event = self._make_event("spec_modified", "docs/x.md", "hash_X")
        key = _dedup_key(event)
        assert key == ("MYM-108", "spec_modified", "docs/x.md", "hash_X")

    def test_doc_change_event_missing_content_hash_treated_as_empty_string(
        self, tmp_path: Path
    ) -> None:
        """Legacy tail entries lacking content_hash field compared as empty string."""
        from work_state.event_engine import is_duplicate

        events_file = tmp_path / "events.jsonl"
        # Simulate legacy v1.3.0 entry — no content_hash field
        legacy = {
            "ts": "2026-05-20T08:00:00Z",
            "item": "MYM-108",
            "event": "spec_modified",
            "from_status": None,
            "to_status": None,
            "source": "filesystem.spec",
            "artifact": "docs/x.md",
        }
        with events_file.open("a") as f:
            f.write(json.dumps(legacy) + "\n")

        # New emission with explicit hash → different from "" → NOT dup
        new_event = self._make_event("spec_modified", "docs/x.md", "hash_X")
        assert not is_duplicate(new_event, events_file)

        # New emission with content_hash=None → maps to "" → matches legacy entry
        null_event = self._make_event("spec_modified", "docs/x.md", None)
        assert is_duplicate(null_event, events_file)


class TestTailBoundedRead:
    def test_reads_last_100_entries(self, tmp_path: Path) -> None:
        from work_state.event_engine import read_tail_events

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
        from work_state.event_engine import read_tail_events

        events_file = tmp_path / "events.jsonl"
        assert read_tail_events(events_file) == []

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        from work_state.event_engine import read_tail_events

        events_file = tmp_path / "nonexistent.jsonl"
        assert read_tail_events(events_file) == []


class TestAppendEvent:
    def test_append_creates_file(self, tmp_path: Path) -> None:
        from work_state.event_engine import append_event

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
        from work_state.event_engine import append_event

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
