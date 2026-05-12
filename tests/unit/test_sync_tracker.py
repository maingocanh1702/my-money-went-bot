"""Tests for scripts/sync-tracker-from-gh.py — pure-function tracker sync."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def sync() -> Any:
    """Load sync-tracker-from-gh.py as a module (hyphenated path)."""
    spec = importlib.util.spec_from_file_location(
        "sync_tracker_from_gh", ROOT / "scripts" / "sync-tracker-from-gh.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_tracker_from_gh"] = module
    spec.loader.exec_module(module)
    return module


TRACKER_HEADER = """# Implementation Tracker — MyMoneyWent

## 0. How to use this tracker

(intro text — not edited)

## 1. Status board — Phase 1 → 6

### Phase 1: Foundation

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
"""

TRACKER_FOOTER = """
**Phase 1 exit criteria:** Docker compose, etc.

## 2. Other section

| PR | something | else |
|----|-----------|------|
| Z | should not | be touched |
"""


def _make_tracker(*rows: str) -> str:
    return TRACKER_HEADER + "\n".join(rows) + TRACKER_FOOTER


# ─── Core flip logic ─────────────────────────────────────────────────────────


def test_sync_flips_not_started_to_merged_on_match(sync: Any) -> None:
    """⬜ + matching merged PR → ✅ status + merge note appended."""
    tracker = _make_tracker(
        "| W1.1 | Wave 0 | Docker Compose | ⬜ | `infra/W1.1-docker` | 🔒X | Postgres + bot |",
    )
    prs = [
        {
            "number": 42,
            "headRefName": "infra/W1.1-docker",
            "mergedAt": "2026-05-14T10:30:00Z",
            "title": "infra: docker compose",
        }
    ]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert len(log) == 1
    assert "⬜→✅" in log[0]
    assert "#42" in log[0]
    assert "| ✅ |" in new
    assert "Merged 2026-05-14 (#42)" in new
    assert "| ⬜ |" not in new


def test_sync_flips_in_review_to_merged(sync: Any) -> None:
    """🟠 in-review + merged PR → ✅."""
    tracker = _make_tracker(
        "| F07 | W1 | Settings | 🟠 | `feat/F07-settings` | 🔒T 🔒X | In Codex review |",
    )
    prs = [{"number": 9, "headRefName": "feat/F07-settings", "mergedAt": "2026-05-15T08:00:00Z"}]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert len(log) == 1
    assert "🟠→✅" in log[0]
    assert "| ✅ |" in new


# ─── Idempotency ─────────────────────────────────────────────────────────────


def test_sync_skips_already_merged_rows(sync: Any) -> None:
    """If row already ✅, no change even if matching PR exists."""
    tracker = _make_tracker(
        "| W0.7 | Wave 0 | request_id | ✅ | `chore/W0.7` | 🔒X | Merged 2026-05-12 (#5). |",
    )
    prs = [{"number": 5, "headRefName": "chore/W0.7", "mergedAt": "2026-05-12T10:00:00Z"}]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert log == []
    assert new == tracker


def test_sync_skips_deferred_rows(sync: Any) -> None:
    """⏸️ deferred rows are not auto-flipped (intentional decision)."""
    tracker = _make_tracker(
        "| P-ACB | Phase 5b | ACB parser | ⏸️ | `feat/parser-acb` | 🔒X | Deferred post-MVP |",
    )
    # Even if hypothetically a PR was merged on that branch
    prs = [{"number": 99, "headRefName": "feat/parser-acb", "mergedAt": "2026-05-14T08:00:00Z"}]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert log == []
    assert new == tracker


def test_sync_idempotent_on_notes_when_merged_already_mentioned(sync: Any) -> None:
    """If Notes already contain 'Merged', don't append duplicate."""
    tracker = _make_tracker(
        "| W0.8 | Wave 0 | display_suffix | 🟠 | `feat/W0.8` | 🔒X | Merged manually noted. |",
    )
    prs = [{"number": 7, "headRefName": "feat/W0.8", "mergedAt": "2026-05-12T08:00:00Z"}]
    new, log = sync.sync_tracker_text(tracker, prs)
    # Status still flips, but no second "Merged..." injection
    assert "| ✅ |" in new
    assert new.count("Merged") == 1  # only the pre-existing mention


# ─── Match / scope safety ────────────────────────────────────────────────────


def test_sync_no_match_no_change(sync: Any) -> None:
    """PR branch doesn't match any tracker row → no change."""
    tracker = _make_tracker(
        "| F08 | W2 | Funding | ⬜ | `feat/F08-funding` | 🔒X | Pending |",
    )
    prs = [
        {"number": 11, "headRefName": "feat/some-other-branch", "mergedAt": "2026-05-14T00:00:00Z"}
    ]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert log == []
    assert new == tracker


def test_sync_only_edits_section_1_rows(sync: Any) -> None:
    """Rows outside `## 1. Status board` section must not be touched."""
    tracker = _make_tracker(
        "| F08 | W2 | Funding | ⬜ | `feat/F08-funding` | 🔒X | Pending |",
    )
    # Section 2 has a row that matches by branch — but it's outside scope.
    prs = [
        {"number": 99, "headRefName": "should-not-be-touched", "mergedAt": "2026-05-14T00:00:00Z"}
    ]
    new, log = sync.sync_tracker_text(tracker, prs)
    # Section 2 unchanged
    assert "| Z | should not | be touched |" in new
    assert log == []


def test_sync_empty_pr_list_noop(sync: Any) -> None:
    """No merged PRs returned → no changes."""
    tracker = _make_tracker(
        "| F08 | W2 | Funding | ⬜ | `feat/F08-funding` | 🔒X | Pending |",
    )
    new, log = sync.sync_tracker_text(tracker, [])
    assert log == []
    assert new == tracker


# ─── Robustness ──────────────────────────────────────────────────────────────


def test_sync_handles_multiple_rows_one_match(sync: Any) -> None:
    """In tracker with N rows, only the matching one is flipped."""
    tracker = _make_tracker(
        "| W1.1 | W0 | Docker | ⬜ | `infra/W1.1-docker` | 🔒X | Pending |",
        "| W1.2 | W6 | Discord | ⬜ | `feat/W1.2-discord` | 🔒X | Pending |",
        "| W1.3 | n/a | Smoke | ⬜ | `chore/W1.3-smoke` | 🔒X | Pending |",
    )
    prs = [{"number": 12, "headRefName": "feat/W1.2-discord", "mergedAt": "2026-05-14T00:00:00Z"}]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert len(log) == 1
    assert "W1.2" in log[0]
    # W1.1 and W1.3 unchanged
    assert "| W1.1 | W0 | Docker | ⬜ |" in new
    assert "| W1.3 | n/a | Smoke | ⬜ |" in new


def test_sync_handles_missing_merged_at_gracefully(sync: Any) -> None:
    """PR with missing mergedAt is skipped (defensive)."""
    tracker = _make_tracker(
        "| F08 | W2 | Funding | ⬜ | `feat/F08-funding` | 🔒X | Pending |",
    )
    prs = [{"number": 11, "headRefName": "feat/F08-funding", "mergedAt": None}]
    new, log = sync.sync_tracker_text(tracker, prs)
    assert log == []
    assert new == tracker
