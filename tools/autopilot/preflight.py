"""Pre-flight checks before autopilot starts.

All checks must pass before any branch is created or code is generated.
Failures are NOT auto-recoverable — they require founder intervention.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import git_ops
from .config import Config


@dataclass
class PreflightReport:
    ok: bool = True
    checks_passed: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def passed(self, name: str) -> None:
        self.checks_passed.append(name)

    def failed(self, name: str, detail: str) -> None:
        self.ok = False
        self.failures.append(f"{name}: {detail}")

    def render(self) -> str:
        lines = ["Preflight:"]
        for name in self.checks_passed:
            lines.append(f"  PASS {name}")
        for failure in self.failures:
            lines.append(f"  FAIL {failure}")
        return "\n".join(lines)


def run(cfg: Config) -> PreflightReport:
    """Run all pre-flight checks. Returns report; check ``.ok``."""
    report = PreflightReport()

    # 1. CLI binaries.
    for label, path in (("codex", cfg.codex_bin), ("claude", cfg.claude_bin)):
        if shutil.which(path) or Path(path).exists():
            report.passed(f"CLI binary {label!r} resolved at {path}")
        else:
            report.failed(
                f"CLI binary {label!r}",
                f"not found (set AUTOPILOT_{label.upper()}_BIN env var)",
            )

    # 2. Git state: must be on base branch + clean tree.
    try:
        status = git_ops.status(cfg)
    except subprocess.CalledProcessError as exc:
        report.failed("git status", f"failed: {exc.stderr.strip()}")
        return report

    if status.branch != cfg.base_branch:
        report.failed(
            "branch check",
            f"on {status.branch!r}, must start from {cfg.base_branch!r}",
        )
    else:
        report.passed(f"on base branch {cfg.base_branch!r}")

    if not status.clean:
        report.failed(
            "clean tree",
            f"working tree dirty ({len(status.modified)} modified, "
            f"{len(status.untracked)} untracked). Commit or stash first.",
        )
    else:
        report.passed("working tree clean")

    # 3. Critical config files exist.
    required_files = [
        cfg.repo_root / "pyproject.toml",
        cfg.repo_root / ".importlinter",
        cfg.repo_root / ".pre-commit-config.yaml",
    ]
    for path in required_files:
        if path.exists():
            report.passed(f"{path.name} present")
        else:
            report.failed(f"{path.name}", "missing — repo not initialized?")

    # 4. State dir creatable.
    try:
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        report.passed(f"state dir writable at {cfg.state_dir}")
    except OSError as exc:
        report.failed("state dir", f"cannot create {cfg.state_dir}: {exc}")

    return report
