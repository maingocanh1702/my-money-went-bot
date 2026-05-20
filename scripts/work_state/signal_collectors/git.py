"""Git signal collector per spec §6.2."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import TypedDict

logger = logging.getLogger(__name__)

_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")


class GitSignals(TypedDict):
    branch_exists: bool
    commits_count: int
    last_commit_sha: str | None
    warnings: list[str]


def _run_git_command(cmd: list[str], timeout: int = 30) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.stdout.strip()


def collect_git_signals(
    branch: str,
    remote: str = "origin",
) -> GitSignals:
    """Collect git signals for a branch. Unknown-safe on network failure."""
    warnings: list[str] = []

    if not branch or not _BRANCH_NAME_RE.match(branch):
        return {
            "branch_exists": False,
            "commits_count": 0,
            "last_commit_sha": None,
            "warnings": warnings,
        }

    try:
        ls_output = _run_git_command(["git", "ls-remote", "--heads", remote, "--", branch])
        branch_exists = bool(ls_output.strip())

        commits_count = 0
        last_commit_sha: str | None = None

        if branch_exists:
            count_output = _run_git_command(
                ["git", "rev-list", "--count", f"{remote}/main..{remote}/{branch}"]
            )
            try:
                commits_count = int(count_output)
            except ValueError:
                commits_count = 0

            sha_output = _run_git_command(["git", "rev-parse", f"{remote}/{branch}"])
            if sha_output:
                last_commit_sha = sha_output

    except (TimeoutError, OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Git command failed: %s", exc)
        warnings.append("git_unknown")
        return {
            "branch_exists": False,
            "commits_count": 0,
            "last_commit_sha": None,
            "warnings": warnings,
        }

    return {
        "branch_exists": branch_exists,
        "commits_count": commits_count,
        "last_commit_sha": last_commit_sha,
        "warnings": warnings,
    }
