"""Unit tests for claude_codegen — primitive (_invoke_claude) and chunked driver.

Strategy: monkey-patch ``subprocess.run`` inside ``tools.autopilot.claude_codegen``
so the Claude CLI is never spawned, and exercise the orchestrator-side logic
(success calculation, log capture, fallback commit, chunk sequencing) against
a tmp git repo.

Per probe findings (`docs/operations/probes/claude-cli-2026-05-12.md`):
- Claude may exit 0 without committing, leaving a dirty tree.
- Orchestrator must commit-all in that case so progress is preserved.
- No multi-turn flag exists → run_codegen drives 4 sequential chunks
  (plan → skeleton → tests → verify) per Blocker #2 Option A.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tools.autopilot import claude_codegen
from tools.autopilot.config import Config


@dataclass
class _FakeCompleted:
    """Stand-in for subprocess.CompletedProcess returned by claude -p."""

    stdout: str
    stderr: str = ""
    returncode: int = 0


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(".autopilot/\n", encoding="utf-8")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--no-verify", "-m", "seed"],
        cwd=repo,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _init_git(tmp_path)
    return tmp_path


@pytest.fixture
def cfg(repo: Path) -> Config:
    return Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )


def _patch_claude(
    monkeypatch: pytest.MonkeyPatch,
    *,
    claude_bin: str,
    side_effect: Any,
) -> list[list[str]]:
    """Replace subprocess.run inside claude_codegen with a dispatching wrapper.

    Calls whose argv[0] matches ``claude_bin`` are intercepted by the fake.
    All other calls (e.g. git from git_ops) fall through to real subprocess.run.
    """
    calls: list[list[str]] = []
    real_run = subprocess.run

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        if argv and argv[0] == claude_bin:
            calls.append(list(argv))
            if callable(side_effect):
                return side_effect(argv, kwargs)
            return side_effect
        return real_run(argv, **kwargs)

    monkeypatch.setattr("tools.autopilot.claude_codegen.subprocess.run", fake_run)
    return calls


# --- _invoke_claude (single-chunk primitive) ---


def _invoke_with(
    cfg: Config,
    prompt: str = "ignored — fake intercepts",
    *,
    kind: str = "test-invoke",
) -> claude_codegen.CodegenResult:
    return claude_codegen._invoke_claude(
        cfg,
        prompt,
        feature_id="F99",
        invocation_kind=kind,
        fallback_commit_message="feat(F99): orchestrator-fallback commit (test)",
        timeout_seconds=60,
    )


def test_invoke_happy_path_claude_commits(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claude writes file AND commits; orchestrator must NOT fallback."""

    def claude_writes_and_commits(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        (repo / "feature.py").write_text("pass\n", encoding="utf-8")
        subprocess.run(["git", "add", "feature.py"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "--no-verify", "-m", "feat: claude self-commit"],
            cwd=repo,
            check=True,
        )
        return _FakeCompleted(stdout="AUTOPILOT_PHASE_A_COMPLETE\nDone.\n")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_writes_and_commits)

    result = _invoke_with(cfg)

    assert result.success is True
    assert result.commits_added == 1
    assert result.fallback_commit is False
    assert result.log_path is not None and result.log_path.exists()


def test_invoke_fallback_commit_when_claude_leaves_dirty_tree(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claude writes file but exits without committing; orchestrator fallback."""

    def claude_writes_but_no_commit(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        (repo / "feature.py").write_text("pass\n", encoding="utf-8")
        return _FakeCompleted(stdout="I added the file. Should I commit? (y/N)")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_writes_but_no_commit)

    result = _invoke_with(cfg)

    assert result.success is True, "fallback commit should mark codegen successful"
    assert result.commits_added == 1
    assert result.fallback_commit is True

    log = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "orchestrator-fallback commit" in log.stdout


def test_invoke_fallback_commit_bypasses_failing_pre_commit_hook(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex v0.2.0 r4 P1 regression: fallback commit must succeed even when
    the repo has a failing pre-commit hook (which is one of the primary
    target cases — Claude bails BECAUSE the hook failed, so the fallback
    needs to bypass hooks to actually recover progress).

    Install a hook that always rejects. Without ``--no-verify`` in
    ``commit_all``, the fallback commit would fail and the orchestrator
    would halt with CODEGEN_FAILED even though valid edits exist.
    """
    # Install a pre-commit hook that always fails.
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'pre-commit always fails for this test' >&2\nexit 1\n")
    hook.chmod(0o755)

    def claude_writes_but_no_commit(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        (repo / "feature.py").write_text("pass\n", encoding="utf-8")
        return _FakeCompleted(stdout="I wrote it. (Pre-commit will fail on my side.)")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_writes_but_no_commit)

    result = _invoke_with(cfg)

    assert result.success is True, "fallback must bypass hooks to recover progress"
    assert result.commits_added == 1
    assert result.fallback_commit is True


def test_invoke_halt_marker_prevents_fallback(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If Claude printed AUTOPILOT_HALT, dirty tree is NOT auto-committed."""

    def claude_halts_dirty(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        (repo / "partial.py").write_text("# partial\n", encoding="utf-8")
        return _FakeCompleted(stdout="AUTOPILOT_HALT: gap discovered\n")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_halts_dirty)

    result = _invoke_with(cfg)

    assert result.success is False
    assert result.commits_added == 0
    assert result.fallback_commit is False


def test_invoke_nonzero_exit_prevents_fallback(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex v0.2.0 r2 P1 regression: if Claude exits non-zero (timeout, CLI
    error, interrupted), DO NOT auto-commit dirty tree even though working
    tree has changes. Partial/broken edits must NOT be persisted as commits
    — leaves recovery state inspectable for the founder.
    """

    def claude_writes_then_errors(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        (repo / "partial.py").write_text("# half-written, claude crashed\n", encoding="utf-8")
        return _FakeCompleted(
            stdout="Working on it...\n[Error: connection lost mid-edit]",
            stderr="claude: timeout exceeded",
            returncode=124,  # standard timeout exit
        )

    _patch_claude(
        monkeypatch,
        claude_bin=cfg.claude_bin,
        side_effect=claude_writes_then_errors,
    )

    result = _invoke_with(cfg)

    assert result.success is False
    assert result.return_code == 124
    assert result.commits_added == 0, "non-zero claude exit must not trigger fallback commit"
    assert result.fallback_commit is False, "partial edits must stay uncommitted for inspection"


def test_invoke_failure_when_nothing_changed(cfg: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Claude exits 0 with no writes and no done marker → not success."""

    def claude_does_nothing(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        return _FakeCompleted(stdout="I read the spec. Awaiting confirmation.")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_does_nothing)

    result = _invoke_with(cfg)

    assert result.success is False
    assert result.commits_added == 0
    assert result.fallback_commit is False


def test_invoke_failure_when_done_marker_but_no_diff(
    cfg: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex v0.2.0 P1 regression: Claude prints a DONE marker but commits
    nothing and leaves a clean tree → marker alone must NOT count as success.

    Bug scenario: in a Phase C fix round, Claude reports
    ``AUTOPILOT_PHASE_C_FIX_COMPLETE`` but the fix didn't land (pre-commit
    bailed, Claude judged no change needed, etc.). Pre-fix, success was
    ``commits_added > 0 or done_marker_present``, which let unresolved
    review findings pass through Phase C as if they were fixed.
    """

    def claude_marker_only(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        return _FakeCompleted(
            stdout=("I reviewed the findings.\n" "AUTOPILOT_PHASE_C_FIX_COMPLETE\n"),
        )

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_marker_only)

    result = _invoke_with(cfg)

    assert result.success is False, "marker without diff must NOT count as progress"
    assert result.commits_added == 0
    assert result.fallback_commit is False


def test_invoke_log_capture_is_monotonic_per_kind(
    cfg: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated invocations produce <kind>-01.log, <kind>-02.log, ..."""

    def claude_minimal(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        return _FakeCompleted(stdout="AUTOPILOT_PHASE_A_COMPLETE\n")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=claude_minimal)

    for _ in range(3):
        _invoke_with(cfg, kind="probe")

    logs = sorted((cfg.state_dir / "F99").glob("probe-*.log"))
    assert [p.name for p in logs] == ["probe-01.log", "probe-02.log", "probe-03.log"]
    body = logs[0].read_text(encoding="utf-8")
    assert "STDOUT" in body
    assert "STDERR" in body


# --- run_codegen chunked driver (Blocker #2 Option A) ---


def _make_chunked_runner(repo: Path, claude_bin: str) -> Any:
    """Build a side_effect that simulates a well-behaved 4-chunk Claude.

    Each invocation writes a unique file, commits it, and emits the chunk-
    specific done marker derived from the prompt argv.
    """
    counter = {"n": 0}
    markers = (
        claude_codegen.CHUNK_PLAN_DONE,
        claude_codegen.CHUNK_SKELETON_DONE,
        claude_codegen.CHUNK_TESTS_DONE,
        claude_codegen.CHUNK_VERIFY_DONE,
    )

    def runner(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        n = counter["n"]
        prompt = argv[-1]
        marker = next((m for m in markers if m in prompt), markers[n])
        path = repo / f"chunk-{n}.txt"
        path.write_text(f"chunk {n}\n", encoding="utf-8")
        subprocess.run(["git", "add", path.name], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "--no-verify", "-m", f"chunk {n}"],
            cwd=repo,
            check=True,
        )
        counter["n"] += 1
        return _FakeCompleted(stdout=f"work done\n{marker}\n")

    assert claude_bin  # silence unused
    return runner


def test_run_codegen_drives_all_four_chunks_in_sequence(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _make_chunked_runner(repo, cfg.claude_bin)
    calls = _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=runner)

    result = claude_codegen.run_codegen(
        cfg,
        feature_id="F99",
        branch="feat/F99-test",
        fe_spec=repo / "fe.md",
        be_spec=repo / "be.md",
    )

    assert result.success is True
    assert result.commits_added == 4, "one commit per chunk"
    assert result.chunks is not None
    assert [c.name for c in result.chunks] == ["plan", "skeleton", "tests", "verify"]
    assert all(c.success for c in result.chunks)
    assert all(c.done_marker_seen for c in result.chunks)
    assert len(calls) == 4, "claude -p invoked exactly 4 times"


def test_run_codegen_halts_when_chunk_missing_done_marker(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunk II returns commits but no done marker — chain halts at chunk II."""
    counter = {"n": 0}

    def runner(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        n = counter["n"]
        path = repo / f"chunk-{n}.txt"
        path.write_text(f"{n}\n", encoding="utf-8")
        subprocess.run(["git", "add", path.name], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "--no-verify", "-m", f"chunk {n}"],
            cwd=repo,
            check=True,
        )
        counter["n"] += 1
        if n == 0:
            return _FakeCompleted(stdout=f"{claude_codegen.CHUNK_PLAN_DONE}\n")
        # chunk II: NO done marker
        return _FakeCompleted(stdout="I did some work but forgot to print marker.\n")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=runner)

    result = claude_codegen.run_codegen(
        cfg,
        feature_id="F99",
        branch="feat/F99-test",
        fe_spec=repo / "fe.md",
        be_spec=repo / "be.md",
    )

    assert result.success is False
    assert result.chunks is not None
    assert len(result.chunks) == 2, "halted after chunk II; chunk III/IV not invoked"
    assert result.chunks[0].success is True
    assert result.chunks[1].success is False
    assert result.chunks[1].done_marker_seen is False


def test_run_codegen_halts_when_chunk_produces_zero_commits(
    cfg: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunk I prints done marker but writes nothing → halt (zero commits)."""

    def runner(argv: list[str], _kwargs: Any) -> _FakeCompleted:
        return _FakeCompleted(stdout=f"{claude_codegen.CHUNK_PLAN_DONE}\n")

    _patch_claude(monkeypatch, claude_bin=cfg.claude_bin, side_effect=runner)

    result = claude_codegen.run_codegen(
        cfg,
        feature_id="F99",
        branch="feat/F99-test",
        fe_spec=repo / "fe.md",
        be_spec=repo / "be.md",
    )

    assert result.success is False
    assert result.chunks is not None
    assert len(result.chunks) == 1, "halted after chunk I produced no commits"
    assert result.chunks[0].done_marker_seen is True
    assert result.chunks[0].commits_added == 0
    assert result.chunks[0].success is False
