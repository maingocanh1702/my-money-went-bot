"""Event engine — signal diff → event emission with write-time dedup per spec §7.2.1."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from work_state.models import Event

TAIL_READ_LIMIT = 100

_ONE_SHOT_EVENTS = {
    "spec_created",
    "tech_created",
    "branch_created",
    "pr_opened",
    "pr_draft",
    "merged",
    "closed",
}

_DOC_CHANGE_EVENTS = {"spec_modified", "tech_modified", "tracker_row_modified"}

_TIME_WINDOWED_EVENTS = {"stale_detected"}

_CI_EVENTS = {"ci_running", "ci_failed", "ci_passed"}
_DEPLOY_EVENTS = {"deploy_started", "deployed", "deploy_failed"}


def _dedup_key(event: Event) -> tuple[str, ...]:
    """Per-event-type dedup identity per spec §7.2.1."""
    if event.event in _ONE_SHOT_EVENTS:
        return (event.item, event.event, event.artifact or "")
    if event.event in _DOC_CHANGE_EVENTS:
        # MYM-8: hash-aware — same artifact + same content_hash = duplicate; new hash = legitimate re-emit
        return (event.item, event.event, event.artifact or "", event.content_hash or "")
    if event.event in _CI_EVENTS:
        return (event.item, event.event, event.artifact or "", str(event.pr_number))
    if event.event in _DEPLOY_EVENTS:
        return (event.item, event.event, event.artifact or "")
    if event.event in _TIME_WINDOWED_EVENTS:
        return (event.item, event.event, event.artifact or "")
    return (event.item, event.event, event.artifact or "", event.source)


def read_tail_events(events_file: Path) -> list[dict[str, object]]:
    """Read last TAIL_READ_LIMIT entries from events.jsonl."""
    if not events_file.exists():
        return []
    try:
        lines = events_file.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    if not lines:
        return []
    tail_lines = lines[-TAIL_READ_LIMIT:]
    result: list[dict[str, object]] = []
    for line in tail_lines:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def is_duplicate(
    event: Event,
    events_file: Path,
    *,
    tail: list[dict[str, object]] | None = None,
) -> bool:
    """Check if event is duplicate per write-time dedup table."""
    if tail is None:
        tail = read_tail_events(events_file)
    key = _dedup_key(event)

    for entry in tail:
        existing_event_type = str(entry.get("event", ""))
        existing_item = str(entry.get("item", ""))
        existing_artifact = str(entry.get("artifact", ""))
        existing_pr = str(entry.get("pr_number", ""))

        existing_key: tuple[str, ...]
        if event.event in _ONE_SHOT_EVENTS:
            existing_key = (existing_item, existing_event_type, existing_artifact)
        elif event.event in _DOC_CHANGE_EVENTS:
            # MYM-8: read content_hash from tail entry; legacy entries lacking field → ""
            existing_content_hash = str(entry.get("content_hash") or "")
            existing_key = (
                existing_item,
                existing_event_type,
                existing_artifact,
                existing_content_hash,
            )
        elif event.event in _CI_EVENTS:
            existing_key = (
                existing_item,
                existing_event_type,
                existing_artifact,
                existing_pr,
            )
        elif event.event in _DEPLOY_EVENTS:
            existing_key = (existing_item, existing_event_type, existing_artifact)
        elif event.event in _TIME_WINDOWED_EVENTS:
            existing_key = (existing_item, existing_event_type, existing_artifact)
            if existing_key == key:
                existing_ts = str(entry.get("ts", ""))
                try:
                    existing_dt = datetime.fromisoformat(existing_ts.replace("Z", "+00:00"))
                    event_dt = datetime.fromisoformat(event.ts.replace("Z", "+00:00"))
                    if event_dt - existing_dt < timedelta(hours=24):
                        return True
                except (ValueError, TypeError):
                    pass
            continue
        else:
            existing_key = (
                existing_item,
                existing_event_type,
                existing_artifact,
                str(entry.get("source", "")),
            )

        if existing_key == key:
            return True

    return False


def append_event(event: Event, events_file: Path) -> None:
    """Append event to JSONL file. Append-only — never modify past events."""
    events_file.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(event)
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
