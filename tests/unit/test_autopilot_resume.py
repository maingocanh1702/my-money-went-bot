"""Unit tests for resume-from-HALTED + unconditional halt-report (v0.2.1).

Coverage:
- ``loop.run(resume=True)`` on HALTED state with ``last_active_phase`` set
  re-enters at that phase with Phase-C round counters reset.
- HALTED state with ``last_active_phase=None`` (legacy / pre-v0.2.1) halts
  with RESUME_AMBIGUOUS so the founder knows to edit state.json.
- Every halt path writes ``halt-report.md`` (previously only the Codex
  circuit-breaker path did).
- PARSER_UNCERTAIN fires when parse_findings returns ([], False).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

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

Test.

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


def _seed_halted_state(
    repo: Path,
    fe: Path,
    be: Path,
    *,
    last_active_phase: str | None,
) -> FeatureState:
    return FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec=str(fe),
        be_spec=str(be),
        phase="HALTED",
        current_round=2,
        consecutive_clean_rounds=0,
        halt_reason="FIX_FAILED: stale",
        last_active_phase=last_active_phase,
    )


def _stub_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.commit_log",
        lambda _c, _b, _br: ["abc seed"],
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.diff_stat",
        lambda _c, _b, _br: "",
    )


def _stub_lint(monkeypatch: pytest.MonkeyPatch, fe: Path, be: Path) -> None:
    monkeypatch.setattr(
        "tools.autopilot.spec_lint.lint",
        lambda _c, _f: spec_lint.LintReport(feature_id="F99", fe_path=fe, be_path=be),
    )


# --- resume-from-HALTED ----------------------------------------------------


def test_resume_from_halted_reenters_at_last_active_phase_and_resets_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HALTED + last_active_phase=VERIFIED → re-enter Phase C with round=0."""
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _seed_halted_state(tmp_path, fe, be, last_active_phase="VERIFIED")
    state_mod.save(cfg, s)

    _stub_lint(monkeypatch, fe, be)
    _stub_git(monkeypatch)

    # Stub Codex to return clean review so the loop doesn't actually run
    # the fix path — we just want to observe the re-entry.
    clean = ReviewResult(
        clean=True, findings=[], raw_output="codex\nno findings", base="main", duration_seconds=0.1
    )
    monkeypatch.setattr("tools.autopilot.loop.codex.run_review", lambda _c: clean)
    monkeypatch.setattr(
        "tools.autopilot.loop.codex.save_review_artifact",
        lambda _c, _r, _f, _n: tmp_path / "stub-artifact",
    )
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)
    # Config is frozen — replace to require only 1 clean round so the test
    # observes re-entry without needing two stub iterations.
    cfg = dataclasses.replace(cfg, required_clean_rounds_before_merge=1)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    # Loop should have re-entered Phase C, found clean, transitioned to READY.
    # round was reset to 0 before re-entry, then incremented to 1 by the loop.
    assert outcome.halted is False
    reloaded = state_mod.load(cfg, "F99")
    assert reloaded is not None
    assert reloaded.phase == "READY"
    assert reloaded.current_round == 1
    assert reloaded.halt_reason is None
    assert reloaded.halt_artifact_path is None


def test_resume_from_halted_without_last_active_phase_halts_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy state (no last_active_phase) → RESUME_AMBIGUOUS halt."""
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _seed_halted_state(tmp_path, fe, be, last_active_phase=None)
    state_mod.save(cfg, s)

    _stub_lint(monkeypatch, fe, be)
    _stub_git(monkeypatch)
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)
    assert outcome.halted is True
    assert outcome.halt_reason is not None
    assert "RESUME_AMBIGUOUS" in outcome.halt_reason


# --- halt-report always written -------------------------------------------


def test_halt_writes_report_for_non_breaker_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct call to ``_halt`` (non-breaker path) must produce halt-report.md.

    Pre-v0.2.1 only the Codex circuit-breaker path wrote a forensic file —
    CODEGEN_FAILED, FIX_FAILED, MERGE_GATE_FAIL etc. all left
    halt_artifact_path null.
    """
    cfg = _cfg(tmp_path)
    s = FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec="docs/features/feature-F99.md",
        be_spec="docs/features/BE/feature-F99-tech.md",
        phase="CODEGEN",
    )

    _stub_git(monkeypatch)
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)

    outcome = loop_mod._halt(cfg, s, "CODEGEN_FAILED", "return_code=1 commits_added=0")

    report = cfg.state_dir / "F99" / "halt-report.md"
    assert report.exists(), "halt-report.md must be written for every halt"
    body = report.read_text(encoding="utf-8")
    assert "CODEGEN_FAILED" in body
    assert "Phase at halt (last_active_phase): CODEGEN" in body
    assert "## Diffstat vs base" in body
    assert "## State snapshot" in body
    # Snapshot must reflect the halted in-memory state (post-transition),
    # not whatever stale phase was on disk. Codex round-01 P2 finding.
    assert '"phase": "HALTED"' in body
    assert "CODEGEN_FAILED" in body  # halt_reason serialized into snapshot too

    # halt_artifact_path on state must point at the written report.
    assert s.halt_artifact_path is not None
    assert s.halt_artifact_path.endswith("halt-report.md")
    assert outcome.halted is True


def test_halt_report_includes_review_context_when_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase-C halts pass review + trigger via extra_context — report
    must include the findings list."""
    from tools.autopilot.circuit_breaker import BreakerTrigger
    from tools.autopilot.codex import Finding

    cfg = _cfg(tmp_path)
    s = FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec="docs/features/feature-F99.md",
        be_spec="docs/features/BE/feature-F99-tech.md",
        phase="REVIEWING",
        current_round=1,
    )

    _stub_git(monkeypatch)
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)

    finding = Finding(
        severity="P1",
        summary="security regression in token compare",
        file="/repo/core/auth.py",
        line_start=33,
        line_end=33,
        detail=["timing attack risk"],
    )
    review = ReviewResult(
        clean=False, findings=[finding], raw_output="codex\n...", base="main", duration_seconds=2.5
    )
    trigger = BreakerTrigger(
        code="SECURITY_FINDING",
        description="security/auth finding — founder audit before auto-fix",
        detail="[P1] security regression",
    )

    loop_mod._halt(
        cfg,
        s,
        trigger.code,
        trigger.description,
        extra_context={"review": review, "trigger": trigger},
    )

    body = (cfg.state_dir / "F99" / "halt-report.md").read_text(encoding="utf-8")
    assert "SECURITY_FINDING" in body
    assert "security regression in token compare" in body
    assert "/repo/core/auth.py:33" in body
    assert "Findings: 1" in body


# --- PARSER_UNCERTAIN gate -------------------------------------------------


def test_parser_uncertain_halts_when_no_findings_and_not_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase C: if parser returns ([], False), loop must halt with
    PARSER_UNCERTAIN — NOT enter fix-loop with empty findings.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec=str(fe),
        be_spec=str(be),
        phase="VERIFIED",
    )
    state_mod.save(cfg, s)

    _stub_lint(monkeypatch, fe, be)
    _stub_git(monkeypatch)
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)

    uncertain = ReviewResult(
        clean=False,
        findings=[],
        raw_output="garbage that no parser knows",
        base="main",
        duration_seconds=0.1,
    )
    monkeypatch.setattr("tools.autopilot.loop.codex.run_review", lambda _c: uncertain)
    monkeypatch.setattr(
        "tools.autopilot.loop.codex.save_review_artifact",
        lambda _c, _r, _f, _n: tmp_path / "stub-artifact",
    )

    # Guard: claude fix path must NOT be hit.
    def fail_fix(*_a: Any, **_kw: Any) -> None:
        raise AssertionError("fix must not run when PARSER_UNCERTAIN")

    monkeypatch.setattr("tools.autopilot.loop.claude_codegen.run_fix", fail_fix)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)
    assert outcome.halted is True
    assert outcome.halt_reason is not None
    assert "PARSER_UNCERTAIN" in outcome.halt_reason

    body = (cfg.state_dir / "F99" / "halt-report.md").read_text(encoding="utf-8")
    assert "PARSER_UNCERTAIN" in body


# --- tracker sync on resume-from-HALTED (Codex v0.2.1 r4 P2) --------------


def test_resume_from_halted_at_ready_syncs_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex v0.2.1 r4 P2 regression — resume from HALTED must propagate
    the restored phase to tracker.

    Setup: a halted state with last_active_phase=READY. _halt previously
    set tracker='HALTED' on the way down; resume must call
    tracker.update_status with the restored phase ('READY') BEFORE the
    Phase D branch executes (Phase D itself never calls update_status
    when auto_merge=False — it just writes ready-report and returns).
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _seed_halted_state(tmp_path, fe, be, last_active_phase="READY")
    state_mod.save(cfg, s)

    _stub_lint(monkeypatch, fe, be)
    _stub_git(monkeypatch)

    calls: list[tuple[str, str]] = []

    def record_update(_cfg: Any, fid: str, phase: str) -> None:
        calls.append((fid, phase))

    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", record_update)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is False
    assert outcome.final_phase == "READY"

    # Tracker must have been told the run is back at READY. Order matters:
    # this call originates from the HALTED-restoration block and must
    # precede any Phase D side-effects. Phase D itself doesn't call
    # update_status in this path, so the only expected call this run is
    # the restoration one.
    assert ("F99", "READY") in calls, (
        f"resume from HALTED at READY must call tracker.update_status(READY); " f"got calls={calls}"
    )
