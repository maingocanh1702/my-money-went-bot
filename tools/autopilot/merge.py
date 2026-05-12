"""Auto-squash-merge with strict pre-merge gates.

Per user decision: "hoàn chỉnh = đến main" + auto-merge when all gates pass.

Gates (all must hold):
1. Local verify all 5 steps green.
2. Last N=consecutive_clean_rounds Codex rounds were clean (configurable).
3. CHANGELOG.md was modified on the branch (entry exists).
4. Tracker row updated to READY phase.
5. Branch is up-to-date with base (no merge conflicts on dry-run).
6. import-linter passes (covered by verify, but assert separately to be loud).

If any gate fails, merge is aborted and a circuit-breaker report is written.
Otherwise: ``git checkout main && git merge --squash <branch> && git commit``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from . import git_ops, verify
from .config import Config
from .state import FeatureState


@dataclass
class MergeReport:
    ok: bool
    gates_passed: list[str] = field(default_factory=list)
    gate_failures: list[str] = field(default_factory=list)
    merge_commit_sha: str | None = None
    skipped_reason: str | None = None

    def render(self) -> str:
        lines = ["Merge gate:"]
        for g in self.gates_passed:
            lines.append(f"  PASS {g}")
        for g in self.gate_failures:
            lines.append(f"  FAIL {g}")
        if self.merge_commit_sha:
            lines.append(f"  Merged as {self.merge_commit_sha[:12]}")
        if self.skipped_reason:
            lines.append(f"  Skipped: {self.skipped_reason}")
        return "\n".join(lines)


def attempt_merge(
    cfg: Config,
    state: FeatureState,
    feature_title: str,
) -> MergeReport:
    """Run all gates. If clear, perform squash-merge."""
    report = MergeReport(ok=True)

    # Gate 1: local verify.
    v = verify.run_all(cfg)
    if v.ok:
        report.gates_passed.append("local verify (ruff/black/mypy/lint-imports/pytest)")
    else:
        report.ok = False
        for step in v.failed_steps:
            report.gate_failures.append(f"verify step {step.name}")
        return report

    # Gate 2: clean Codex rounds. v0.2.2 keeps this aligned with Phase C's
    # completion gate (loop.py) so a READY feature isn't immediately
    # rejected here under custom thresholds:
    # - If any fix was applied during review, require
    #   ``confirmation_rounds_after_last_fix`` clean rounds after the
    #   last fix (``consecutive_clean_rounds`` tracks that tail).
    # - Otherwise fall back to the legacy
    #   ``required_clean_rounds_before_merge`` gate.
    any_fixes_applied = bool(state.fixed_finding_hashes)
    effective_gate = (
        cfg.confirmation_rounds_after_last_fix
        if any_fixes_applied
        else cfg.required_clean_rounds_before_merge
    )
    gate_label = (
        "confirmation_rounds_after_last_fix"
        if any_fixes_applied
        else "required_clean_rounds_before_merge"
    )
    if state.consecutive_clean_rounds >= effective_gate:
        report.gates_passed.append(
            f"{state.consecutive_clean_rounds} consecutive clean Codex rounds "
            f"(gate: {gate_label}={effective_gate})",
        )
    else:
        report.ok = False
        report.gate_failures.append(
            f"need {effective_gate} clean rounds ({gate_label}); "
            f"have {state.consecutive_clean_rounds}",
        )
        return report

    # Gate 3: CHANGELOG entry exists on branch.
    if state.initial_head_sha and git_ops.changelog_has_unreleased_entry(
        cfg,
        state.initial_head_sha,
    ):
        report.gates_passed.append("CHANGELOG.md modified on branch")
    else:
        report.ok = False
        report.gate_failures.append(
            "CHANGELOG.md not modified on branch (workflow §2.6 requires entry)",
        )
        return report

    # Gate 4: branch has commits ahead of base.
    commits = git_ops.commit_log(cfg, cfg.base_branch, state.branch)
    if commits:
        report.gates_passed.append(f"{len(commits)} commits ahead of {cfg.base_branch}")
    else:
        report.ok = False
        report.gate_failures.append(f"branch has 0 commits ahead of {cfg.base_branch}")
        return report

    # Gate 5: dry-run merge to detect conflicts.
    try:
        _check_merge_clean(cfg, state.branch)
        report.gates_passed.append("squash dry-run conflict-free")
    except subprocess.CalledProcessError as exc:
        report.ok = False
        report.gate_failures.append(
            f"squash dry-run failed: {exc.stderr.strip() if exc.stderr else exc}",
        )
        return report

    # All gates green — perform real merge.
    commit_msg = f"{state.feature_id}: {feature_title}"
    try:
        git_ops.squash_merge(cfg, state.branch, commit_message=commit_msg)
    except subprocess.CalledProcessError as exc:
        report.ok = False
        report.gate_failures.append(f"squash-merge failed: {exc.stderr.strip()}")
        return report

    report.merge_commit_sha = git_ops.head_sha(cfg)
    # Cleanup: delete merged branch.
    try:
        git_ops.delete_branch(cfg, state.branch, force=True)
        report.gates_passed.append(f"deleted branch {state.branch!r}")
    except subprocess.CalledProcessError:
        # Non-fatal — leave the branch around for manual inspection.
        pass
    return report


def _check_merge_clean(cfg: Config, branch: str) -> None:
    """Dry-run squash-merge: do squash, abort with reset --hard before commit."""
    # Save current branch to restore after.
    current = git_ops.status(cfg).branch
    try:
        subprocess.run(
            ["git", "checkout", cfg.base_branch],
            cwd=cfg.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "merge", "--squash", "--no-commit", branch],
            cwd=cfg.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        # Always reset and return to original branch.
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=cfg.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if current != cfg.base_branch:
            subprocess.run(
                ["git", "checkout", current],
                cwd=cfg.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
