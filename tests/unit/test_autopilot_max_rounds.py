"""Unit tests for v0.2.2 max_rounds + confirmation_rounds_after_last_fix knob.

Background: F07 + v0.2.1 pilots showed `max_review_rounds=3 +
required_clean_rounds_before_merge=2 (consecutive)` cannot ship when
adjacent micro-findings cascade — each fix grows the diff and Codex's
next pass often surfaces a new micro-finding in the new code.

v0.2.2 logic:
- max_review_rounds default raised 3 → 5.
- New ``confirmation_rounds_after_last_fix`` (default 2) decouples
  "consecutive cleans needed" from "max total rounds".
- After ANY fix, the loop needs N clean rounds AFTER that fix.
- If no fix is ever applied, fall back to legacy
  ``required_clean_rounds_before_merge`` gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.autopilot import loop as loop_mod
from tools.autopilot import spec_lint
from tools.autopilot import state as state_mod
from tools.autopilot.claude_codegen import CodegenResult
from tools.autopilot.codex import Finding, ReviewResult
from tools.autopilot.config import Config
from tools.autopilot.state import FeatureState
from tools.autopilot.verify import StepResult, VerifyResult

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


def _seed_verified_state(fe: Path, be: Path) -> FeatureState:
    return FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec=str(fe),
        be_spec=str(be),
        phase="VERIFIED",
        current_round=0,
        consecutive_clean_rounds=0,
    )


def _clean_review() -> ReviewResult:
    return ReviewResult(
        clean=True,
        findings=[],
        raw_output="codex\nno actionable defects",
        base="main",
        duration_seconds=0.1,
    )


def _finding_review(severity: str = "P2", summary: str = "minor style nit") -> ReviewResult:
    return ReviewResult(
        clean=False,
        findings=[
            Finding(
                severity=severity,
                summary=summary,
                file="/repo/core/x.py",
                line_start=10,
                line_end=10,
            )
        ],
        raw_output=f"codex\n- [{severity}] {summary}",
        base="main",
        duration_seconds=0.1,
    )


def _ok_verify() -> VerifyResult:
    return VerifyResult(
        steps=[
            StepResult(name="ruff", ok=True, duration_seconds=0.1, stdout_tail="", stderr_tail="")
        ]
    )


def _stub_common(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fe: Path,
    be: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "tools.autopilot.spec_lint.lint",
        lambda _c, _f: spec_lint.LintReport(feature_id="F99", fe_path=fe, be_path=be),
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.commit_log",
        lambda _c, _b, _br: ["abc seed"],
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.diff_stat",
        lambda _c, _b, _br: "",
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.current_branch",
        lambda _c: "feat/F99-x",
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.branch_exists",
        lambda _c, _b: True,
    )
    monkeypatch.setattr("tools.autopilot.loop.git_ops.checkout", lambda _c, _b: None)
    monkeypatch.setattr(
        "tools.autopilot.loop.codex.save_review_artifact",
        lambda _c, _r, _f, n: tmp_path / f"stub-round-{n:02d}.txt",
    )
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_k: None)
    monkeypatch.setattr("tools.autopilot.loop.verify.run_all", lambda _c: _ok_verify())
    monkeypatch.setattr(
        "tools.autopilot.loop.claude_codegen.run_fix",
        lambda *_a, **_k: CodegenResult(
            success=True,
            commits_added=1,
            stdout="",
            stderr="",
            return_code=0,
        ),
    )


def test_cascade_pattern_converges_under_v0_2_2_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cascade pattern that broke max=3: finding, clean, finding, clean, clean.

    Under old logic (max=3 + consec=2): round 1 finding+fix, round 2 clean,
    round 3 finding+fix → MAX_ROUNDS halt.

    Under v0.2.2 logic (max=5 + post-fix-confirm=2): same first three rounds
    plus round 4 clean (1 confirmation after last fix) + round 5 clean
    (2 confirmations after last fix) → READY.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _seed_verified_state(fe, be)
    state_mod.save(cfg, s)
    _stub_common(monkeypatch, fe=fe, be=be, tmp_path=tmp_path)

    reviews = iter(
        [
            _finding_review(severity="P2", summary="first nit"),
            _clean_review(),
            _finding_review(severity="P3", summary="adjacent nit in new code"),
            _clean_review(),
            _clean_review(),
        ]
    )
    monkeypatch.setattr("tools.autopilot.loop.codex.run_review", lambda _c: next(reviews))

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is False, f"expected READY, got halt={outcome.halt_reason}"
    assert outcome.final_phase == "READY"
    assert outcome.rounds == 5


def test_zero_fixes_uses_legacy_required_clean_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no fix is ever applied, fall back to required_clean_rounds_before_merge.

    Two consecutive clean rounds with no findings at all → READY at round 2.
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _seed_verified_state(fe, be)
    state_mod.save(cfg, s)
    _stub_common(monkeypatch, fe=fe, be=be, tmp_path=tmp_path)

    reviews = iter([_clean_review(), _clean_review()])
    monkeypatch.setattr("tools.autopilot.loop.codex.run_review", lambda _c: next(reviews))

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is False
    assert outcome.final_phase == "READY"
    assert outcome.rounds == 2


def test_resume_after_prior_fix_uses_post_fix_confirm_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex r1 P1 regression: a resume run AFTER a prior fix must still
    use the post-fix-confirm gate, not the legacy 2-clean-rounds gate.

    Setup: seed state with non-empty ``fixed_finding_hashes`` (proxy for
    "a fix landed during a prior run"). Resume + 2 clean rounds → READY
    only because confirmation_rounds_after_last_fix=2 happens to equal
    required_clean_rounds_before_merge=2 by default. Cover the gate
    selection explicitly: set the legacy gate to 1 to verify the loop
    does NOT short-circuit at round 1.
    """
    import dataclasses

    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    # Distinct gates so we can tell which one fired.
    cfg = dataclasses.replace(
        cfg, required_clean_rounds_before_merge=1, confirmation_rounds_after_last_fix=2
    )
    s = _seed_verified_state(fe, be)
    s.fixed_finding_hashes = ["a" * 12]  # proxy: a prior fix landed
    state_mod.save(cfg, s)
    _stub_common(monkeypatch, fe=fe, be=be, tmp_path=tmp_path)

    reviews = iter([_clean_review(), _clean_review()])
    monkeypatch.setattr("tools.autopilot.loop.codex.run_review", lambda _c: next(reviews))

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is False
    assert outcome.final_phase == "READY"
    # Must have run 2 rounds, NOT 1 (which would mean it fell back to the
    # legacy gate when fixes had already been applied in a prior run).
    assert outcome.rounds == 2


def test_merge_gate_aligned_with_phase_c_post_fix_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex r5 P2 regression: Phase E merge gate must use the same
    clean-round rule as Phase C completion. Otherwise a READY feature
    with custom knob values fails merge gates immediately despite
    satisfying Phase C.

    Setup: state where a fix happened (``fixed_finding_hashes`` non-empty)
    and the post-fix confirmation tail is shorter than the legacy gate
    (``consecutive_clean_rounds=2``; legacy=5; new=2). Phase E should
    accept this just like Phase C did.
    """
    import dataclasses

    from tools.autopilot import merge as merge_mod
    from tools.autopilot.state import FeatureState

    cfg = _cfg(tmp_path)
    cfg = dataclasses.replace(
        cfg, required_clean_rounds_before_merge=5, confirmation_rounds_after_last_fix=2
    )
    s = FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec="docs/features/feature-F99.md",
        be_spec="docs/features/BE/feature-F99-tech.md",
        phase="READY",
        current_round=4,
        consecutive_clean_rounds=2,
        fixed_finding_hashes=["a" * 12],
        initial_head_sha="deadbeef",
    )

    monkeypatch.setattr("tools.autopilot.merge.verify.run_all", lambda _c: _ok_verify())
    monkeypatch.setattr(
        "tools.autopilot.merge.git_ops.changelog_has_unreleased_entry",
        lambda _c, _sha: True,
    )
    monkeypatch.setattr(
        "tools.autopilot.merge.git_ops.commit_log",
        lambda _c, _b, _br: ["abc commit"],
    )
    monkeypatch.setattr(
        "tools.autopilot.merge.git_ops.diff_stat",
        lambda _c, _b, _br: "1 file changed",
    )
    monkeypatch.setattr(
        "tools.autopilot.merge.git_ops.squash_merge",
        lambda _c, _b, **_k: None,
    )
    monkeypatch.setattr("tools.autopilot.merge.git_ops.head_sha", lambda _c: "feedface")
    monkeypatch.setattr("tools.autopilot.merge.git_ops.delete_branch", lambda _c, _b: None)

    report = merge_mod.attempt_merge(cfg, s, "F99 — example")

    # Gate 2 (clean rounds) must pass via post-fix-confirm, NOT fail under
    # legacy gate. If it failed under legacy, gate_failures would say
    # "need 5 clean rounds".
    for f in report.gate_failures:
        assert (
            "need 5 clean rounds" not in f
        ), f"Phase E gate must align with Phase C; got failures: {report.gate_failures}"


def test_insufficient_confirmation_tail_halts_with_new_wording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sequence: fix, fix, fix, fix, clean — only 1 confirmation round
    after the last fix (need 2). Falls out of while-loop into the new
    MAX_ROUNDS else-branch with confirmation wording.

    Distinct from circuit_breaker MAX_ROUNDS (which preempts on round N
    where N >= max_review_rounds AND findings present).
    """
    fe, be = _write_specs(tmp_path)
    cfg = _cfg(tmp_path)
    s = _seed_verified_state(fe, be)
    state_mod.save(cfg, s)
    _stub_common(monkeypatch, fe=fe, be=be, tmp_path=tmp_path)

    reviews = iter(
        [
            _finding_review(severity="P3", summary="r1 nit"),
            _finding_review(severity="P3", summary="r2 nit"),
            _finding_review(severity="P3", summary="r3 nit"),
            _finding_review(severity="P3", summary="r4 nit"),
            _clean_review(),
        ]
    )
    monkeypatch.setattr("tools.autopilot.loop.codex.run_review", lambda _c: next(reviews))

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.halted is True
    assert outcome.halt_reason is not None
    # New wording mentions confirmation-rounds-after-last-fix terminology.
    assert "confirmation" in outcome.halt_reason.lower()
    assert outcome.rounds == cfg.max_review_rounds
