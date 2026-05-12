"""Unit tests for tools.autopilot.git_ops helpers.

Codex v0.2.2 R6 P1: ``current_branch()`` previously returned the literal
string ``"HEAD"`` when the repo was in detached-HEAD state. Callers in
``loop._sync_branch_to_state`` then routed that through branch_exists /
checkout, silently no-op'd, and let Phase C codex review run on
whatever tree was at the detached SHA — same wrong-diff hazard the
sync was introduced to prevent. Helper now returns ``None`` on
detached HEAD and caller halts with ``DETACHED_HEAD``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.autopilot import git_ops
from tools.autopilot.config import Config


def _init_git(repo: Path) -> str:
    """Initialise a tmp git repo on ``main`` with one seed commit. Returns seed SHA."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--no-verify", "-m", "seed"],
        cwd=repo,
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _cfg(repo: Path) -> Config:
    return Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )


def test_current_branch_returns_branch_name_when_on_main(tmp_path: Path) -> None:
    _init_git(tmp_path)
    cfg = _cfg(tmp_path)

    assert git_ops.current_branch(cfg) == "main"


def test_current_branch_returns_branch_name_when_on_feature(tmp_path: Path) -> None:
    _init_git(tmp_path)
    cfg = _cfg(tmp_path)
    subprocess.run(["git", "checkout", "-q", "-b", "feat/F99-x"], cwd=tmp_path, check=True)

    assert git_ops.current_branch(cfg) == "feat/F99-x"


def test_current_branch_returns_none_on_detached_head(tmp_path: Path) -> None:
    """Codex v0.2.2 R6 P1 regression guard.

    `git rev-parse --abbrev-ref HEAD` returns the literal string ``"HEAD"``
    when checked out at a SHA (no branch). Helper must surface that as
    ``None`` so callers can refuse to silently sync.
    """
    seed_sha = _init_git(tmp_path)
    cfg = _cfg(tmp_path)
    # Detach HEAD by checking out the seed SHA directly.
    subprocess.run(["git", "checkout", "-q", "--detach", seed_sha], cwd=tmp_path, check=True)

    # Sanity: raw git output is "HEAD" in this state.
    raw = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert raw == "HEAD"

    assert git_ops.current_branch(cfg) is None


@pytest.mark.parametrize("branch_name", ["feat/F99-x", "chore/wave-0", "main"])
def test_current_branch_handles_slashed_and_simple_names(tmp_path: Path, branch_name: str) -> None:
    _init_git(tmp_path)
    cfg = _cfg(tmp_path)
    if branch_name != "main":
        subprocess.run(["git", "checkout", "-q", "-b", branch_name], cwd=tmp_path, check=True)

    assert git_ops.current_branch(cfg) == branch_name
