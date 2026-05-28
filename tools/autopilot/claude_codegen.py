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

CHUNK_PLAN_DONE = "AUTOPILOT_CHUNK_I_PLAN_DONE"
CHUNK_SKELETON_DONE = "AUTOPILOT_CHUNK_II_SKELETON_DONE"
CHUNK_TESTS_DONE = "AUTOPILOT_CHUNK_III_TESTS_DONE"
CHUNK_VERIFY_DONE = "AUTOPILOT_CHUNK_IV_VERIFIED_DONE"

DONE_MARKERS = (
    "AUTOPILOT_PHASE_A_COMPLETE",
    "AUTOPILOT_PHASE_C_FIX_COMPLETE",
    CHUNK_PLAN_DONE,
    CHUNK_SKELETON_DONE,
    CHUNK_TESTS_DONE,
    CHUNK_VERIFY_DONE,
)


@dataclass
class CodegenResult:
    success: bool
    commits_added: int
    stdout: str
    stderr: str
    return_code: int
    log_path: Path | None = None
    fallback_commit: bool = False
    chunks: list[ChunkResult] | None = None


@dataclass
class ChunkResult:
    name: str
    success: bool
    commits_added: int
    done_marker_seen: bool
    log_path: Path | None


CHUNK_HEADER = """\
# Autopilot codegen — Chunk {chunk_label}: {chunk_title}

You are running inside the autopilot orchestrator. NO prior conversation context.
Repo: {repo_root}. Current branch: {branch}. Feature: {feature_id}.

This is chunk {chunk_label} of 4 sequential chunks (plan → skeleton → tests →
verify). Per probe findings 2026-05-12, `claude -p` is single-shot and has no
multi-turn flag — the orchestrator drives the chain via git commit context.
Read prior chunks' commits with `git log --oneline` if you need them.

## Spec sources of truth

- FE spec: {fe_spec}
- BE tech doc: {be_spec}
- Required: docs/operations/development-workflow.md §2 (10-step), §6 (anti-patterns).
- Required: the `autopilot:gaps` and `autopilot:test_plan` blocks in the FE spec.
"""

CHUNK_FOOTER_RULES = """\
## Halt conditions (output "AUTOPILOT_HALT" and stop)

- Spec gap not pre-locked in autopilot:gaps.
- Architectural decision required that is not pre-locked.
- mypy --strict requires `# type: ignore` (founder approval needed).
- This chunk's instructions cannot be completed safely.

## Project invariants

- core/ must NOT import markets/ (import-linter).
- markets/vn/email_parsers/ must be pure (no DB / no messenger).
- NO mock DB — use testcontainers for integration tests.
- Tenant isolation test if DB involved (MANDATORY).
"""

CHUNK_I_PROMPT = CHUNK_HEADER + """\

## Your task (chunk I — plan)

1. Read FE + BE specs IN FULL.
2. Write a 10-line implementation plan to `.autopilot/state/{feature_id}/plan.md`.
   Plan must list: files to create, files to modify, migrations, test files,
   integration points, risks. Keep under 25 lines.
3. Stage + commit just that plan file with message
   `chore({feature_id}): autopilot plan (chunk I)`.

When done, output the literal line: {done_marker}

""" + CHUNK_FOOTER_RULES

CHUNK_II_PROMPT = CHUNK_HEADER + """\

## Your task (chunk II — code skeleton)

Prior chunks visible via `git log --oneline -5`. The plan is at
`.autopilot/state/{feature_id}/plan.md` — read it first.

1. Implement the production code per the plan: files, classes, functions,
   migrations. NO tests yet (chunk III).
2. Local verify before commit:
   ```
   ruff check core/ markets/ tests/
   black --check core/ markets/ tests/
   mypy core/ markets/ tests/
   lint-imports
   ```
3. Commit atomically per logical change with messages like
   `feat({feature_id}): <what>`.

When done, output the literal line: {done_marker}

""" + CHUNK_FOOTER_RULES

CHUNK_III_PROMPT = CHUNK_HEADER + """\

## Your task (chunk III — tests)

Prior chunks visible via `git log --oneline -10`. Skeleton code is on the
branch already; now write tests against it.

1. Read the FE spec's `autopilot:test_plan` block. Implement tests for ALL 5
   categories listed there: happy, retry/idempotency, missing-optional,
   pathological, concurrent. If a category is marked `N/A` in the spec, skip
   with a one-line `# N/A — <reason from spec>` placeholder.
2. Tenant isolation test if the feature touches DB (mandatory; no exceptions).
3. Commit atomically: `test({feature_id}): <category>`.

When done, output the literal line: {done_marker}

""" + CHUNK_FOOTER_RULES

CHUNK_IV_PROMPT = CHUNK_HEADER + """\

## Your task (chunk IV — verify + CHANGELOG)

Prior chunks visible via `git log --oneline -15`. Code + tests are on the
branch. Make verify green.

1. Run local verify:
   ```
   ruff check core/ markets/ tests/
   black --check core/ markets/ tests/
   mypy core/ markets/ tests/
   lint-imports
   pytest tests/ -v
   ```
2. If anything fails, fix minimally and re-run. Cap at 2 fix attempts per
   failure — beyond that, AUTOPILOT_HALT.
3. Append a CHANGELOG.md entry under `## [Unreleased]` (create section at
   top if missing) summarizing the feature.
4. Commit verify fixes + CHANGELOG atomically.

When done, output the literal line: {done_marker}

""" + CHUNK_FOOTER_RULES


@dataclass
class _ChunkSpec:
    name: str
    label: str
    title: str
    prompt_template: str
    done_marker: str
    timeout_seconds: int


CODEGEN_CHUNKS: tuple[_ChunkSpec, ...] = (
    _ChunkSpec(
        name="plan",
        label="I",
        title="read specs + write plan.md",
        prompt_template=CHUNK_I_PROMPT,
        done_marker=CHUNK_PLAN_DONE,
        timeout_seconds=600,
    ),
    _ChunkSpec(
        name="skeleton",
        label="II",
        title="implement production code",
        prompt_template=CHUNK_II_PROMPT,
        done_marker=CHUNK_SKELETON_DONE,
        timeout_seconds=1800,
    ),
    _ChunkSpec(
        name="tests",
        label="III",
        title="write 5-category test suite",
        prompt_template=CHUNK_III_PROMPT,
        done_marker=CHUNK_TESTS_DONE,
        timeout_seconds=1500,
    ),
    _ChunkSpec(
        name="verify",
        label="IV",
        title="green verify + CHANGELOG",
        prompt_template=CHUNK_IV_PROMPT,
        done_marker=CHUNK_VERIFY_DONE,
        timeout_seconds=1200,
    ),
)

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
    timeout_seconds: int = 1800,  # noqa: ARG001  # retained for API compatibility
) -> CodegenResult:
    """Drive Claude to implement the feature via 4 sequential chunks.

    Per Blocker #2 Option A (locked by 2026-05-12 probe — no multi-turn flag
    in claude CLI): plan → skeleton → tests → verify, each a single-shot
    `claude -p` invocation. Context flows through git commits rather than
    session memory; each chunk reads `git log --oneline` to see prior work.

    The chain halts on the first chunk that either:
    - fails the generic _invoke_claude success check (return code, halt
      marker, zero progress);
    - produces zero new commits (no forward motion);
    - does not emit its own done marker.

    Aggregate ``CodegenResult.commits_added`` is the sum across chunks.
    """
    chunk_results: list[ChunkResult] = []
    aggregate_commits = 0
    last_stdout = ""
    last_stderr = ""
    last_return_code = 0
    last_log_path: Path | None = None

    for chunk in CODEGEN_CHUNKS:
        prompt = chunk.prompt_template.format(
            chunk_label=chunk.label,
            chunk_title=chunk.title,
            feature_id=feature_id,
            repo_root=cfg.repo_root,
            branch=branch,
            fe_spec=fe_spec,
            be_spec=be_spec,
            done_marker=chunk.done_marker,
        )
        result = _invoke_claude(
            cfg,
            prompt,
            feature_id=feature_id,
            invocation_kind=f"codegen-{chunk.name}",
            fallback_commit_message=f"feat({feature_id}): autopilot codegen chunk {chunk.label} ({chunk.name})",
            timeout_seconds=chunk.timeout_seconds,
        )

        marker_seen = chunk.done_marker in result.stdout
        chunk_success = result.success and marker_seen and result.commits_added > 0

        chunk_results.append(
            ChunkResult(
                name=chunk.name,
                success=chunk_success,
                commits_added=result.commits_added,
                done_marker_seen=marker_seen,
                log_path=result.log_path,
            )
        )
        aggregate_commits += result.commits_added
        last_stdout = result.stdout
        last_stderr = result.stderr
        last_return_code = result.return_code
        last_log_path = result.log_path

        if not chunk_success:
            return CodegenResult(
                success=False,
                commits_added=aggregate_commits,
                stdout=last_stdout,
                stderr=last_stderr,
                return_code=last_return_code,
                log_path=last_log_path,
                fallback_commit=result.fallback_commit,
                chunks=chunk_results,
            )

    return CodegenResult(
        success=True,
        commits_added=aggregate_commits,
        stdout=last_stdout,
        stderr=last_stderr,
        return_code=last_return_code,
        log_path=last_log_path,
        fallback_commit=False,
        chunks=chunk_results,
    )


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
    return _invoke_claude(
        cfg,
        prompt,
        feature_id=feature_id,
        invocation_kind=f"fix-round-{round_num}",
        fallback_commit_message=f"fix({feature_id}): autopilot fix output round {round_num} (orchestrator-fallback commit)",
        timeout_seconds=timeout_seconds,
    )


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
    feature_id: str,
    invocation_kind: str,
    fallback_commit_message: str,
    timeout_seconds: int,
) -> CodegenResult:
    """Run claude CLI non-interactive. Capture output, log, fall back to commit.

    Per probe 2026-05-12 (`docs/operations/probes/claude-cli-2026-05-12.md`):
    - Claude in `-p` mode may write files but not commit (asks a question,
      hits pre-commit hook, etc.) and still return exit 0.
    - Returncode + commits_added alone is insufficient.

    Success rules:
    1. returncode == 0
    2. AUTOPILOT_HALT not in stdout
    3. Either commits_added > 0, a done marker is present in stdout, OR the
       working tree was dirty (in which case we fall back to an orchestrator
       commit so progress is not lost).
    """
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
    log_path = _write_log(cfg, feature_id, invocation_kind, prompt, completed)

    head_after = git_ops.head_sha(cfg)
    commits_added = git_ops.count_commits_between(cfg, head_before, head_after)
    halted = "AUTOPILOT_HALT" in completed.stdout

    # Fallback commit ONLY when Claude exited cleanly. If `claude -p` failed
    # (timeout, CLI error, interrupted), the working tree may hold partial or
    # broken edits — committing them would persist error-state artifacts and
    # make resume/manual recovery unreliable. Codex v0.2.0 r2 P1.
    fallback_commit = False
    if (
        completed.returncode == 0
        and not halted
        and commits_added == 0
        and git_ops.working_tree_dirty(cfg)
    ):
        if git_ops.commit_all(cfg, fallback_commit_message):
            fallback_commit = True
            head_after = git_ops.head_sha(cfg)
            commits_added = git_ops.count_commits_between(cfg, head_before, head_after)

    # Done marker is advisory only — fix-phase invocations may print the marker
    # without committing if pre-commit fails or Claude judges no change needed.
    # Codex v0.2.0 P1: require a real diff (commit OR fallback-committed dirty
    # tree) so unresolved review findings can't pass through Phase C as fixed.
    progress_made = commits_added > 0  # marker alone is insufficient

    success = completed.returncode == 0 and not halted and progress_made
    return CodegenResult(
        success=success,
        commits_added=commits_added,
        stdout=completed.stdout,
        stderr=completed.stderr,
        return_code=completed.returncode,
        log_path=log_path,
        fallback_commit=fallback_commit,
    )


def _write_log(
    cfg: Config,
    feature_id: str,
    invocation_kind: str,
    prompt: str,
    completed: subprocess.CompletedProcess[str],
) -> Path:
    """Persist stdout/stderr to .autopilot/state/<feature>/codegen-N.log.

    Per Blocker #1 (NTH-2 folded in): forensic record of each Claude
    invocation. Naming: <kind>-NN.log where NN is monotonic per kind.
    """
    log_dir = cfg.state_dir / feature_id
    log_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(log_dir.glob(f"{invocation_kind}-*.log"))
    next_n = len(existing) + 1
    log_path = log_dir / f"{invocation_kind}-{next_n:02d}.log"
    body = (
        f"# autopilot codegen invocation\n"
        f"# kind: {invocation_kind}\n"
        f"# return_code: {completed.returncode}\n"
        f"# prompt_length: {len(prompt)} chars\n"
        f"\n--- STDOUT ---\n{completed.stdout}\n"
        f"\n--- STDERR ---\n{completed.stderr}\n"
    )
    log_path.write_text(body, encoding="utf-8")
    return log_path
