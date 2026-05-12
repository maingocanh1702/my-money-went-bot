"""Git subprocess wrappers.

Per Wave 0 lesson #1: all git ops MUST run on Mac terminal (not sandbox).
This module assumes the orchestrator process IS the terminal authority.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .config import Config


@dataclass
class GitStatus:
    branch: str
    clean: bool
    untracked: list[str]
    modified: list[str]


def _run(cfg: Config, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cfg.repo_root,
        capture_output=True,
        text=True,
        check=check,
    )


def status(cfg: Config) -> GitStatus:
    branch = _run(cfg, "branch", "--show-current").stdout.strip()
    porcelain = _run(cfg, "status", "--porcelain").stdout
    untracked: list[str] = []
    modified: list[str] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        flag, path = line[:2], line[3:]
        if flag == "??":
            untracked.append(path)
        else:
            modified.append(path)
    return GitStatus(
        branch=branch,
        clean=not porcelain.strip(),
        untracked=untracked,
        modified=modified,
    )


def head_sha(cfg: Config) -> str:
    return _run(cfg, "rev-parse", "HEAD").stdout.strip()


def working_tree_dirty(cfg: Config) -> bool:
    """True if there are modified, staged, or untracked files."""
    porcelain = _run(cfg, "status", "--porcelain").stdout
    return bool(porcelain.strip())


def commit_all(cfg: Config, message: str) -> bool:
    """Stage everything and commit. Returns True if a commit was created.

    Used as orchestrator-side fallback when Claude writes code but fails to
    commit (e.g. asked a clarifying question and exited, hit a pre-commit
    failure it couldn't resolve, etc.). Per probe findings 2026-05-12, this
    pattern is common enough that the orchestrator must own commit fallback.

    Codex v0.2.0 r4 P1: passes ``--no-verify`` so the fallback succeeds even
    when pre-commit hooks themselves were the reason Claude bailed in the
    first place. Trade-off: this can commit code that fails ruff/black/mypy,
    BUT Phase B (verify.run_all) is the safety net — it runs AFTER codegen and
    will halt the loop with VERIFY_FAIL if the committed state is broken.
    Saving the partial state to git makes founder inspection / resume tractable;
    leaving it as uncommitted working-tree state does not.
    detect-secrets is also bypassed; this is acceptable here because Claude
    operates on spec-driven feature code (no secret material expected) and the
    repository's `.secrets.baseline` covers known false positives. Founder
    review of the squash diff is the final guard before main.
    """
    if not working_tree_dirty(cfg):
        return False
    _run(cfg, "add", "-A")
    result = _run(cfg, "commit", "--no-verify", "-m", message, check=False)
    return result.returncode == 0


def count_commits_between(cfg: Config, old_sha: str, new_sha: str) -> int:
    if old_sha == new_sha:
        return 0
    out = _run(cfg, "rev-list", "--count", f"{old_sha}..{new_sha}")
    return int(out.stdout.strip() or "0")


def create_branch(cfg: Config, name: str, *, base: str | None = None) -> None:
    base = base or cfg.base_branch
    _run(cfg, "checkout", base)
    _run(cfg, "checkout", "-b", name)


def checkout(cfg: Config, name: str) -> None:
    _run(cfg, "checkout", name)


def branch_exists(cfg: Config, name: str) -> bool:
    result = _run(cfg, "rev-parse", "--verify", name, check=False)
    return result.returncode == 0


def commit_log(cfg: Config, base: str, branch: str) -> list[str]:
    out = _run(cfg, "log", "--oneline", f"{base}..{branch}")
    return [line for line in out.stdout.splitlines() if line.strip()]


def diff_stat(cfg: Config, base: str, branch: str) -> str:
    return _run(cfg, "diff", "--stat", f"{base}..{branch}").stdout


def squash_merge(
    cfg: Config,
    branch: str,
    *,
    commit_message: str,
) -> None:
    """Perform a squash-merge into the configured base branch.

    Steps:
    1. Checkout base.
    2. ``git merge --squash <branch>``.
    3. ``git commit -m <message>``.

    Raises ``subprocess.CalledProcessError`` on conflict; caller decides
    whether to abort + circuit-break.
    """
    _run(cfg, "checkout", cfg.base_branch)
    _run(cfg, "merge", "--squash", branch)
    _run(cfg, "commit", "-m", commit_message)


def delete_branch(cfg: Config, name: str, *, force: bool = True) -> None:
    flag = "-D" if force else "-d"
    _run(cfg, "branch", flag, name)


def changelog_has_unreleased_entry(cfg: Config, since_sha: str) -> bool:
    """True if CHANGELOG.md was modified between since_sha and HEAD."""
    if not cfg.changelog_path.exists():
        return False
    out = _run(
        cfg,
        "diff",
        "--name-only",
        f"{since_sha}..HEAD",
    )
    return cfg.changelog_path.name in out.stdout
