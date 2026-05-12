"""Unit tests for v0.2.2 tracker.update_status branch-aware no-op (fix #4).

Previously ``update_status`` mutated ``docs/implementation-tracker.md`` on
whatever branch was currently checked out. During Phase C fix rounds the
orchestrator runs on the feature branch, so the call polluted the feature
branch with tracker-state noise commits (via ``git_ops.commit_all``
fallback) that interfered with squash diffs.

v0.2.2 makes the call a no-op on any non-base branch. Founder updates
the tracker manually after squash-merging.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.autopilot import tracker
from tools.autopilot.config import Config

SAMPLE_TRACKER = """\
# Implementation Tracker

| PR | Wave | Feature | Status | Branch | Gates | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| F02 | W2 | F02 — webhook | 🟡 | `feat/F02-webhook` | tests | seed |
| F99 | W2 | F99 — example | 🟡 | `feat/F99-x` | tests | seed |
"""


def _cfg(repo: Path) -> Config:
    return Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )


def _seed_tracker(tmp_path: Path) -> Config:
    cfg = _cfg(tmp_path)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    cfg.tracker_path.write_text(SAMPLE_TRACKER, encoding="utf-8")
    return cfg


def test_update_status_noop_on_feature_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When current branch != base_branch, tracker file is NOT written."""
    cfg = _seed_tracker(tmp_path)
    monkeypatch.setattr("tools.autopilot.tracker.git_ops.current_branch", lambda _c: "feat/F99-x")
    before = cfg.tracker_path.read_text(encoding="utf-8")

    result = tracker.update_status(cfg, "F99", "REVIEWING")

    assert result.success is False
    assert "no-op" in result.note
    assert cfg.tracker_path.read_text(encoding="utf-8") == before


def test_update_status_writes_on_base_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When current branch == base_branch, tracker is updated normally."""
    cfg = _seed_tracker(tmp_path)
    monkeypatch.setattr(
        "tools.autopilot.tracker.git_ops.current_branch", lambda _c: cfg.base_branch
    )

    result = tracker.update_status(cfg, "F99", "MERGED")

    assert result.success is True
    body = cfg.tracker_path.read_text(encoding="utf-8")
    # MERGED emoji is ✅ per tracker.STATUS_EMOJI; F99 row should now carry it.
    assert "✅" in body
    # F02 row (untouched) still has 🟡.
    f02_line = next(line for line in body.splitlines() if line.startswith("| F02 "))
    assert "🟡" in f02_line


def test_update_status_falls_through_when_branch_lookup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If git_ops.current_branch raises (e.g. detached HEAD, no git repo),
    the update proceeds as if on base_branch — best-effort, never blocks."""
    cfg = _seed_tracker(tmp_path)

    def boom(_c: Config) -> str:
        raise RuntimeError("simulated git failure")

    monkeypatch.setattr("tools.autopilot.tracker.git_ops.current_branch", boom)

    result = tracker.update_status(cfg, "F99", "VERIFIED")
    assert result.success is True
