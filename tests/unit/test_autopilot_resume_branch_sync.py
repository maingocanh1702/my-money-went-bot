"""Unit tests for v0.2.2 resume git-checkout sync (fix #3).

When ``loop.run(resume=True)`` re-enters Phase C, the current git branch
must match ``feature_state.branch``. Without this, a founder who runs
``autopilot resume F07`` from ``main`` would have Phase C codex review
an empty diff (main..main) → false-clean halt or wasted Codex round.

Observed on F07 i18n fix session: caller was on main; orchestrator never
checked out the feature branch before invoking Codex.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.autopilot import loop as loop_mod
from tools.autopilot import spec_lint
from tools.autopilot import state as state_mod
from tools.autopilot.codex import ReviewResult
from tools.autopilot.config import Config
from tools.autopilot.state import FeatureState

MIN_FE = """\
<!-- autopilot:meta
feature_id: F99
branch: feat/F99-x
phase: 2
wave: 1
risk_tier: P2
depends_on: []
-->

# Feature F99

## 1. Mô tả

x

## 2. Use Cases

UC1.

## 10. Acceptance Criteria

- [ ] one
- [ ] two
- [ ] three

## Changelog

v0.
"""

MIN_BE = "# BE\n\n## 1. Implementation Overview\n\n## 5. Testing Plan\n\n## Changelog\n"


def _write_specs(repo: Path) -> tuple[Path, Path]:
    fe_dir = repo / "docs" / "features"
    be_dir = fe_dir / "BE"
    fe_dir.mkdir(parents=True, exist_ok=True)
    be_dir.mkdir(parents=True, exist_ok=True)
    fe = fe_dir / "feature-F99.md"
    fe.write_text(MIN_FE, encoding="utf-8")
    be = be_dir / "feature-F99-tech.md"
    be.write_text(MIN_BE, encoding="utf-8")
    return fe, be


def _cfg(repo: Path) -> Config:
    return Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )


def _state(fe: Path, be: Path, *, phase: str = "VERIFIED") -> FeatureState:
    return FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec=str(fe),
        be_spec=str(be),
        phase=phase,
        current_round=0,
        consecutive_clean_rounds=0,
    )


def _stub_lint(monkeypatch: pytest.MonkeyPatch, fe: Path, be: Path) -> None:
    monkeypatch.setattr(
        "tools.autopilot.spec_lint.lint",
        lambda _c, _f: spec_lint.LintReport(feature_id="F99", fe_path=fe, be_path=be),
    )


def _stub_phase_c_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "tools.autopilot.loop.codex.run_review",
        lambda _c: ReviewResult(
            clean=True,
            findings=[],
            raw_output="codex\nno actionable defects",
            base="main",
            duration_seconds=0.1,
        ),
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.codex.save_review_artifact",
        lambda _c, _r, _f, _n: tmp_path / "stub-artifact",
    )
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)
    monkeypatch.setattr("tools.autopilot.loop.git_ops.commit_log", lambda _c, _b, _br: ["abc seed"])
    monkeypatch.setattr("tools.autopilot.loop.git_ops.diff_stat", lambda _c, _b, _br: "")


def test_resume_checks_out_feature_branch_when_on_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caller on main + state.branch=feat/F99-x → orchestrator checks out feat/F99-x."""
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _state(fe, be)
    state_mod.save(cfg, s)
    _stub_lint(monkeypatch, fe, be)
    _stub_phase_c_clean(monkeypatch, tmp_path)

    # Simulate caller on main.
    current = {"branch": "main"}

    monkeypatch.setattr("tools.autopilot.loop.git_ops.current_branch", lambda _c: current["branch"])
    monkeypatch.setattr("tools.autopilot.loop.git_ops.branch_exists", lambda _c, _b: True)

    checkouts: list[str] = []

    def fake_checkout(_c: Config, name: str) -> None:
        checkouts.append(name)
        current["branch"] = name

    monkeypatch.setattr("tools.autopilot.loop.git_ops.checkout", fake_checkout)

    loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert "feat/F99-x" in checkouts, "sync must call git_ops.checkout(feature_branch)"


def test_resume_noop_when_already_on_feature_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Already on the feature branch → no checkout call."""
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _state(fe, be)
    state_mod.save(cfg, s)
    _stub_lint(monkeypatch, fe, be)
    _stub_phase_c_clean(monkeypatch, tmp_path)

    monkeypatch.setattr("tools.autopilot.loop.git_ops.current_branch", lambda _c: "feat/F99-x")
    monkeypatch.setattr("tools.autopilot.loop.git_ops.branch_exists", lambda _c, _b: True)

    checkouts: list[str] = []
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.checkout",
        lambda _c, name: checkouts.append(name),
    )

    loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert checkouts == [], "no checkout when already on feature branch"


def test_resume_skips_sync_for_init_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex r3 P1 regression: resume from INIT must NOT call branch sync.

    Phase A is responsible for creating the branch. If a crash happens
    between writing state.json and Phase A's create_branch call, the
    feature branch legitimately doesn't exist yet — sync would HALT
    with BRANCH_MISSING and block recovery.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _state(fe, be, phase="INIT")
    state_mod.save(cfg, s)
    _stub_lint(monkeypatch, fe, be)

    def boom_current(_c: Config) -> str:
        raise AssertionError("current_branch must not be called for INIT resume")

    monkeypatch.setattr("tools.autopilot.loop.git_ops.current_branch", boom_current)
    # Phase A will call branch_exists (legitimately): return False so it
    # routes to create_branch, which we hook below as the success signal.
    monkeypatch.setattr("tools.autopilot.loop.git_ops.branch_exists", lambda _c, _b: False)

    def reached_phase_a(_c: Config, _name: str) -> None:
        raise StopIteration("phase A reached")

    monkeypatch.setattr("tools.autopilot.loop.git_ops.create_branch", reached_phase_a)

    # Reaching Phase A's create_branch is the success signal — sync was skipped.
    import pytest as _pt

    with _pt.raises(StopIteration, match="phase A reached"):
        loop_mod.run(cfg, "F99", resume=True, auto_merge=False)


def test_resume_skips_sync_for_merged_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex r2 P2 regression: resume on terminal MERGED phase must NOT
    call branch sync. Post-merge the feature branch is typically deleted;
    if sync ran it would HALT with BRANCH_MISSING and clobber the benign
    "already at MERGED" outcome.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _state(fe, be, phase="MERGED")
    state_mod.save(cfg, s)
    _stub_lint(monkeypatch, fe, be)
    # commit_log / diff_stat / etc. are only used downstream; not relevant here.

    def boom_current(_c: Config) -> str:
        raise AssertionError("current_branch must not be called for MERGED resume")

    def boom_exists(_c: Config, _b: str) -> bool:
        raise AssertionError("branch_exists must not be called for MERGED resume")

    monkeypatch.setattr("tools.autopilot.loop.git_ops.current_branch", boom_current)
    monkeypatch.setattr("tools.autopilot.loop.git_ops.branch_exists", boom_exists)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is False
    assert outcome.final_phase == "MERGED"


def test_resume_halts_detached_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex v0.2.2 R6 P1: detached-HEAD state on resume → HALT DETACHED_HEAD.

    Scenario: founder ran ``git checkout <some-sha>`` to inspect a commit,
    then triggered ``autopilot resume``. ``current_branch`` returns None
    (helper-side fix); sync must refuse rather than silently overlay the
    feature branch onto the inspected SHA.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _state(fe, be)
    state_mod.save(cfg, s)
    _stub_lint(monkeypatch, fe, be)
    _stub_phase_c_clean(monkeypatch, tmp_path)

    monkeypatch.setattr("tools.autopilot.loop.git_ops.current_branch", lambda _c: None)

    def _no_checkout(_c: Config, _name: str) -> None:
        pytest.fail("checkout must not be called when HEAD is detached")

    def _no_branch_exists(_c: Config, _b: str) -> bool:
        pytest.fail("branch_exists must not be called when HEAD is detached")

    monkeypatch.setattr("tools.autopilot.loop.git_ops.checkout", _no_checkout)
    monkeypatch.setattr("tools.autopilot.loop.git_ops.branch_exists", _no_branch_exists)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is True
    assert outcome.halt_reason is not None
    assert "DETACHED_HEAD" in outcome.halt_reason


def test_resume_halts_branch_missing_when_branch_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """state.branch missing from repo → HALT with BRANCH_MISSING.

    Scenario: a concurrent agent (or stale state) left state.branch
    referencing a branch that no longer exists. Recovery requires
    founder intervention; do not silently fall through.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _state(fe, be)
    state_mod.save(cfg, s)
    _stub_lint(monkeypatch, fe, be)
    _stub_phase_c_clean(monkeypatch, tmp_path)

    monkeypatch.setattr("tools.autopilot.loop.git_ops.current_branch", lambda _c: "main")
    monkeypatch.setattr("tools.autopilot.loop.git_ops.branch_exists", lambda _c, _b: False)
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.checkout",
        lambda _c, _name: pytest.fail("checkout must not be called when branch missing"),
    )

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is True
    assert outcome.halt_reason is not None
    assert "BRANCH_MISSING" in outcome.halt_reason
