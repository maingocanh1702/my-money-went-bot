"""Paths, constants, env-overridable settings for the autopilot.

All paths are derived from REPO_ROOT (auto-detected from git or env override).
Codex / Claude CLI paths can be overridden via env vars to support different
machines / sandboxes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _detect_repo_root() -> Path:
    """Find git repo root from CWD, fallback to env override."""
    override = os.environ.get("AUTOPILOT_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        return Path(out.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            "Cannot detect repo root. Run from inside the repo or set " "AUTOPILOT_REPO_ROOT.",
        ) from exc


def _resolve_cli(name: str, env_var: str, fallback_paths: list[str]) -> str:
    """Find a CLI binary via env var, $PATH, or known fallback paths."""
    override = os.environ.get(env_var)
    if override and Path(override).exists():
        return override
    found = shutil.which(name)
    if found:
        return found
    for candidate in fallback_paths:
        if Path(candidate).exists():
            return candidate
    # Return name as-is; subprocess will fail with a clear error at call site.
    return name


@dataclass(frozen=True)
class Config:
    """Runtime configuration. Build via ``Config.load()``."""

    repo_root: Path
    codex_bin: str
    claude_bin: str
    state_dir: Path
    base_branch: str = "main"
    max_review_rounds: int = 3
    max_local_verify_retries: int = 2
    required_clean_rounds_before_merge: int = 2
    context_budget_warn_pct: int = 70
    # Severity classification used by circuit breaker / auto-fix routing.
    blocking_severities: tuple[str, ...] = ("P0", "P1", "CRITICAL", "HIGH")
    auto_fixable_severities: tuple[str, ...] = ("P2", "P3", "MEDIUM", "LOW")

    @classmethod
    def load(cls) -> Config:
        repo_root = _detect_repo_root()
        codex = _resolve_cli(
            "codex",
            "AUTOPILOT_CODEX_BIN",
            [
                # Documented Mac install path per automation-state.md.
                str(
                    Path.home() / "Library/Application Support/crawbot/nodejs/bin/codex",
                ),
            ],
        )
        claude = _resolve_cli(
            "claude",
            "AUTOPILOT_CLAUDE_BIN",
            ["/usr/local/bin/claude"],
        )
        state_dir = repo_root / ".autopilot" / "state"
        return cls(
            repo_root=repo_root,
            codex_bin=codex,
            claude_bin=claude,
            state_dir=state_dir,
        )

    @property
    def features_dir(self) -> Path:
        return self.repo_root / "docs" / "features"

    @property
    def be_features_dir(self) -> Path:
        return self.repo_root / "docs" / "features" / "BE"

    @property
    def changelog_path(self) -> Path:
        return self.repo_root / "CHANGELOG.md"

    @property
    def tracker_path(self) -> Path:
        return self.repo_root / "docs" / "implementation-tracker.md"
