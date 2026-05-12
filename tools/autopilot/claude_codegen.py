"""Claude CLI wrapper for code-generation and targeted-fix prompts.

Drives ``claude -p "<prompt>"`` non-interactively. The prompt embeds:
- Spec paths (FE + BE) so Claude reads them itself.
- Workflow rules (10-step, anti-patterns) by reference.
- Locked gap decisions by reference (memory + autopilot:gaps block).
- Test plan reference.
- Branch state.
- For fixes: structured Codex finding list.

Code generation happens INSIDE Claude — orchestrator only invokes + verifies
that commits were created on the expected branch.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .codex import Finding
from .config import Config


@dataclass
class CodegenResult:
    success: bool
    commits_added: int
    stdout: str
    stderr: str
    return_code: int


CODEGEN_PROMPT_TEMPLATE = """\
# Task: Implement feature {feature_id} per spec — Level 3 autopilot phase A

You are running inside the autopilot orchestrator. NO prior conversation context.
Repo: {repo_root}. Current branch: {branch}.

## Spec sources of truth (READ BEFORE CODING)

- FE spec: {fe_spec}
- BE tech doc: {be_spec}

## Required reading (project conventions)

- docs/operations/development-workflow.md §2 (10-step), §6 (anti-patterns)
- docs/operations/wave0-retrospective.md (7 lessons)
- The autopilot:gaps and autopilot:test_plan blocks inside the FE spec

## Mandatory rules

1. Spec-first: read both spec files in full before writing any code.
2. 5-category test plan: implement tests for happy / retry / missing-optional /
   pathological / concurrent (each marked N/A in spec → skip with comment).
3. Tenant isolation test if DB involved (MANDATORY, no exceptions).
4. Atomic commits (multiple commits per branch is fine; one logical change each).
5. NO mock DB — use testcontainers. NO `if market == "vn"` in core/.
6. core/ must NOT import markets/ (import-linter enforces).
7. Update CHANGELOG.md with an entry under "## [Unreleased]" (or create that
   section at top if missing). Format: `### Added/Changed/Fixed` then bullets.
8. Run local verify before each commit:
   ```
   ruff check core/ markets/ tests/
   black --check core/ markets/ tests/
   mypy core/ markets/ tests/
   lint-imports
   pytest tests/ -v
   ```
9. If any verification fails, fix and re-run. Don't commit broken state.

## Halt conditions (output "AUTOPILOT_HALT" line and stop)

- Spec gap discovered that requires founder decision.
- Architectural choice not pre-locked in autopilot:gaps.
- Test fails after 2 fix attempts.
- mypy --strict requires `# type: ignore` (need founder OK).

## Done condition

When acceptance criteria items are all implemented + local verify passes,
output the literal line "AUTOPILOT_PHASE_A_COMPLETE" followed by:
- Commits added (count)
- Files touched (list)
- Test count by category

Begin now. Read specs first.
"""

FIX_PROMPT_TEMPLATE = """\
# Task: Apply Codex review fixes — Level 3 autopilot phase C round {round_num}

Repo: {repo_root}. Branch: {branch}. Feature: {feature_id}.

## Codex findings to address ({finding_count} total, sorted by severity)

{findings_block}

## Rules

1. For EACH finding, apply the minimal targeted fix at the cited file:line.
2. Do NOT refactor unrelated code.
3. After each finding's fix, run local verify (ruff/black/mypy/lint-imports/pytest).
4. If a fix causes a test regression, revert and output AUTOPILOT_HALT with the
   regressing test name.
5. Commit per logical fix: `fix({feature_id}): <summary of what was fixed>`.

## Halt conditions (output AUTOPILOT_HALT and stop)

- A finding requires architectural redesign (schema change, contract break).
- A finding's fix introduces a regression you cannot resolve in 1 attempt.
- A finding's fix would require disabling a static-enforcement contract.

## Done

Output AUTOPILOT_PHASE_C_FIX_COMPLETE plus commits added (count).
"""


def run_codegen(
    cfg: Config,
    *,
    feature_id: str,
    branch: str,
    fe_spec: Path,
    be_spec: Path,
    timeout_seconds: int = 1800,
) -> CodegenResult:
    """Drive Claude to implement the feature on the current branch."""
    prompt = CODEGEN_PROMPT_TEMPLATE.format(
        feature_id=feature_id,
        repo_root=cfg.repo_root,
        branch=branch,
        fe_spec=fe_spec,
        be_spec=be_spec,
    )
    return _invoke_claude(cfg, prompt, timeout_seconds=timeout_seconds)


def run_fix(
    cfg: Config,
    *,
    feature_id: str,
    branch: str,
    findings: list[Finding],
    round_num: int,
    timeout_seconds: int = 900,
) -> CodegenResult:
    """Drive Claude to apply targeted fixes for a Codex findings batch."""
    findings_block = _format_findings(findings)
    prompt = FIX_PROMPT_TEMPLATE.format(
        feature_id=feature_id,
        repo_root=cfg.repo_root,
        branch=branch,
        round_num=round_num,
        finding_count=len(findings),
        findings_block=findings_block,
    )
    return _invoke_claude(cfg, prompt, timeout_seconds=timeout_seconds)


def _format_findings(findings: list[Finding]) -> str:
    sorted_findings = sorted(findings, key=lambda f: f.rank)
    blocks: list[str] = []
    for i, f in enumerate(sorted_findings, start=1):
        loc = f"{f.file}:{f.line_start}" if f.file else "<no file>"
        if f.line_end and f.line_end != f.line_start:
            loc = f"{f.file}:{f.line_start}-{f.line_end}"
        blocks.append(
            f"### Finding {i} [{f.severity}] (hash {f.hash})\n"
            f"Location: {loc}\n"
            f"Summary: {f.summary}\n"
            f"Detail:\n```\n{f.detail_text}\n```",
        )
    return "\n\n".join(blocks)


def _invoke_claude(
    cfg: Config,
    prompt: str,
    *,
    timeout_seconds: int,
) -> CodegenResult:
    """Run claude CLI non-interactive. Capture output. Detect commit delta."""
    from . import git_ops

    head_before = git_ops.head_sha(cfg)
    completed = subprocess.run(
        [cfg.claude_bin, "-p", prompt],
        cwd=cfg.repo_root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    head_after = git_ops.head_sha(cfg)
    commits_added = git_ops.count_commits_between(cfg, head_before, head_after)
    halted = "AUTOPILOT_HALT" in completed.stdout
    success = completed.returncode == 0 and not halted and commits_added > 0
    return CodegenResult(
        success=success,
        commits_added=commits_added,
        stdout=completed.stdout,
        stderr=completed.stderr,
        return_code=completed.returncode,
    )
