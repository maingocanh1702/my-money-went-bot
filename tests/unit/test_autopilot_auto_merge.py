"""Unit tests for Blocker #5 — --auto-merge opt-in flag and safe-default behavior.

Coverage:
- ``parse_risk_tier`` extracts risk_tier from autopilot:meta block.
- ``loop.run(auto_merge=False)`` stops at READY, writes ready-report, never
  invokes ``merge.attempt_merge``.
- ``loop.run(auto_merge=True)`` reaches the merge call.
- CLI without --auto-merge passes ``auto_merge=False`` to ``loop.run``.
- CLI with --auto-merge prompts via stdin; accepts 'y' for P2 feature.
- CLI with --auto-merge refuses (exit 4) for P0/P1 feature regardless of stdin.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from tools.autopilot import loop as loop_mod
from tools.autopilot import spec_lint
from tools.autopilot import state as state_mod
from tools.autopilot.__main__ import _gate_auto_merge
from tools.autopilot.__main__ import main as cli_run
from tools.autopilot.config import Config
from tools.autopilot.state import FeatureState

P2_META = """\
<!-- autopilot:meta
feature_id: F99
branch: feat/F99-x
phase: 2
wave: 1
risk_tier: P2
depends_on: []
-->
"""

P0_META = P2_META.replace("risk_tier: P2", "risk_tier: P0")
P1_META = P2_META.replace("risk_tier: P2", "risk_tier: P1")
NO_META = ""

MIN_SPEC_BODY = """\
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


def _write_specs(repo: Path, meta: str) -> Path:
    fe_dir = repo / "docs" / "features"
    be_dir = fe_dir / "BE"
    fe_dir.mkdir(parents=True, exist_ok=True)
    be_dir.mkdir(parents=True, exist_ok=True)
    fe = fe_dir / "feature-F99.md"
    fe.write_text(meta + "\n" + MIN_SPEC_BODY, encoding="utf-8")
    be = be_dir / "feature-F99-tech.md"
    be.write_text(
        "# BE\n\n## 1. Implementation Overview\n\n## 5. Testing Plan\n\n## Changelog\n",
        encoding="utf-8",
    )
    return fe


def _cfg(repo: Path) -> Config:
    return Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )


# --- parse_risk_tier ---


def test_parse_risk_tier_p2(tmp_path: Path) -> None:
    fe = _write_specs(tmp_path, P2_META)
    assert spec_lint.parse_risk_tier(fe) == "P2"


def test_parse_risk_tier_p0(tmp_path: Path) -> None:
    fe = _write_specs(tmp_path, P0_META)
    assert spec_lint.parse_risk_tier(fe) == "P0"


def test_parse_risk_tier_missing_meta_returns_none(tmp_path: Path) -> None:
    fe = _write_specs(tmp_path, NO_META)
    assert spec_lint.parse_risk_tier(fe) is None


def test_parse_risk_tier_missing_file_returns_none(tmp_path: Path) -> None:
    assert spec_lint.parse_risk_tier(tmp_path / "nope.md") is None


# --- loop ready-report writing ---


def _ready_state(repo: Path, feature_id: str = "F99") -> FeatureState:
    fe = repo / "docs" / "features" / f"feature-{feature_id}.md"
    return FeatureState(
        feature_id=feature_id,
        branch=f"feat/{feature_id}-x",
        base_branch="main",
        fe_spec=str(fe),
        be_spec=str(repo / "docs" / "features" / "BE" / f"feature-{feature_id}-tech.md"),
        phase="READY",
    )


def test_write_ready_report_creates_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_specs(tmp_path, P2_META)
    cfg = _cfg(tmp_path)
    s = _ready_state(tmp_path)

    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.commit_log",
        lambda _c, _b, _br: ["abc feat: one", "def feat: two"],
    )
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.diff_stat",
        lambda _c, _b, _br: " 2 files changed, 5 insertions(+)",
    )

    path = loop_mod._write_ready_report(cfg, s)
    body = Path(str(path)).read_text(encoding="utf-8")

    assert "Ready for manual merge — F99" in body
    assert "feat/F99-x" in body
    assert "Commits ahead: 2" in body
    assert "git merge --squash feat/F99-x" in body
    assert "smoke checklist" in body.lower()


# --- loop.run integration: auto_merge=False stops at READY ---


def test_loop_run_auto_merge_false_writes_ready_report_and_skips_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When auto_merge=False, ``merge.attempt_merge`` MUST NOT be called and
    ``_write_ready_report`` MUST run.
    """
    fe = _write_specs(tmp_path, P2_META)
    cfg = _cfg(tmp_path)
    s = _ready_state(tmp_path)
    state_mod.save(cfg, s)

    monkeypatch.setattr(
        "tools.autopilot.spec_lint.lint",
        lambda _c, _f: spec_lint.LintReport(feature_id="F99", fe_path=fe, be_path=Path(s.be_spec)),
    )

    invoked: dict[str, bool] = {"merge": False}

    def fail_merge(*_a: Any, **_kw: Any) -> None:
        invoked["merge"] = True
        raise AssertionError("merge.attempt_merge must not run when auto_merge=False")

    monkeypatch.setattr("tools.autopilot.loop.merge.attempt_merge", fail_merge)
    monkeypatch.setattr(
        "tools.autopilot.loop.git_ops.commit_log",
        lambda _c, _b, _br: ["abc seed"],
    )
    monkeypatch.setattr("tools.autopilot.loop.git_ops.diff_stat", lambda _c, _b, _br: "")

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=False)

    assert outcome.final_phase == "READY"
    assert outcome.halted is False
    assert invoked["merge"] is False
    assert (cfg.state_dir / "F99" / "ready-report.md").exists()


def test_loop_run_auto_merge_true_calls_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With auto_merge=True the loop reaches ``merge.attempt_merge``."""
    fe = _write_specs(tmp_path, P2_META)
    cfg = _cfg(tmp_path)
    s = _ready_state(tmp_path)
    state_mod.save(cfg, s)

    monkeypatch.setattr(
        "tools.autopilot.spec_lint.lint",
        lambda _c, _f: spec_lint.LintReport(feature_id="F99", fe_path=fe, be_path=Path(s.be_spec)),
    )

    class _FakeMergeReport:
        ok = True
        merge_commit_sha = "deadbeef"
        gate_failures: list[str] = []

        def render(self) -> str:
            return "merge ok"

    invoked: dict[str, bool] = {"merge": False}

    def fake_merge(*_a: Any, **_kw: Any) -> _FakeMergeReport:
        invoked["merge"] = True
        return _FakeMergeReport()

    monkeypatch.setattr("tools.autopilot.loop.merge.attempt_merge", fake_merge)
    monkeypatch.setattr("tools.autopilot.loop.tracker.update_status", lambda *_a, **_kw: None)

    outcome = loop_mod.run(cfg, "F99", resume=True, auto_merge=True)

    assert invoked["merge"] is True
    assert outcome.final_phase == "MERGED"
    assert outcome.merge_sha == "deadbeef"


# --- CLI gate behavior ---


def test_cli_gate_auto_merge_refuses_p0(tmp_path: Path) -> None:
    _write_specs(tmp_path, P0_META)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("y\n"))
    assert rc == 4


def test_cli_gate_auto_merge_refuses_p1(tmp_path: Path) -> None:
    _write_specs(tmp_path, P1_META)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("y\n"))
    assert rc == 4


def test_cli_gate_auto_merge_refuses_missing_meta_defaulting_to_p1(
    tmp_path: Path,
) -> None:
    _write_specs(tmp_path, NO_META)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("y\n"))
    assert rc == 4


def test_cli_gate_auto_merge_prompts_p2_and_accepts_y(tmp_path: Path) -> None:
    _write_specs(tmp_path, P2_META)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("y\n"))
    assert rc is None


def test_cli_gate_auto_merge_p2_rejects_no_answer(tmp_path: Path) -> None:
    """Codex v0.2.0 r3 P1: declining the prompt must return non-zero so
    scripted/non-interactive runs can distinguish cancellation from success.
    Exit code 5 = user declined --auto-merge confirmation (distinct from
    4 = P0/P1 mechanical refusal).
    """
    _write_specs(tmp_path, P2_META)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("\n"))
    assert rc == 5


def test_cli_gate_auto_merge_p2_rejects_explicit_n(tmp_path: Path) -> None:
    """Explicit 'n' (not just empty) also returns 5."""
    _write_specs(tmp_path, P2_META)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("n\n"))
    assert rc == 5


def test_cli_gate_auto_merge_refuses_malformed_tier(tmp_path: Path) -> None:
    """Codex v0.2.0 r4 P1 regression: any tier value other than exactly 'P2'
    must fail closed. Malformed labels like 'p2-lite', 'HIGH', custom strings
    must not pass through the P0/P1 deny-list into the confirm path.
    """
    malformed = P2_META.replace("risk_tier: P2", "risk_tier: p2-lite")
    _write_specs(tmp_path, malformed)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("y\n"))
    assert rc == 4, "malformed risk_tier must fail closed, not fall through to confirm"


def test_cli_gate_auto_merge_refuses_unknown_tier(tmp_path: Path) -> None:
    """Custom/future tier labels (e.g. 'HIGH', 'P3') also fail closed."""
    custom = P2_META.replace("risk_tier: P2", "risk_tier: HIGH")
    _write_specs(tmp_path, custom)
    cfg = _cfg(tmp_path)
    rc = _gate_auto_merge(cfg, "F99", stdin=io.StringIO("y\n"))
    assert rc == 4


# --- CLI argparse plumbing ---


class _FakeOutcome:
    def __init__(self, final_phase: str) -> None:
        self.final_phase = final_phase
        self.halted = False
        self.summary = ""


class _FakePreflight:
    ok = True

    def render(self) -> str:
        return "pre ok"


def _stub_config() -> Config:
    return Config(
        repo_root=Path("/tmp"),  # noqa: S108
        codex_bin="c",
        claude_bin="cl",
        state_dir=Path("/tmp/.autopilot"),  # noqa: S108
    )


def test_cli_run_without_flag_passes_auto_merge_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {"auto_merge": None}

    def fake_loop_run(_cfg: Config, _fid: str, *, resume: bool, auto_merge: bool) -> _FakeOutcome:
        captured["auto_merge"] = auto_merge
        return _FakeOutcome("READY")

    monkeypatch.setattr("tools.autopilot.__main__.loop.run", fake_loop_run)
    monkeypatch.setattr("tools.autopilot.__main__.preflight.run", lambda _c: _FakePreflight())
    monkeypatch.setattr(
        "tools.autopilot.__main__.Config.load", classmethod(lambda _cls: _stub_config())
    )

    rc = cli_run(["run", "F99"])
    assert rc == 0
    assert captured["auto_merge"] is False


def test_cli_run_with_flag_passes_auto_merge_true_after_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {"auto_merge": None}

    def fake_loop_run(_cfg: Config, _fid: str, *, resume: bool, auto_merge: bool) -> _FakeOutcome:
        captured["auto_merge"] = auto_merge
        return _FakeOutcome("MERGED")

    monkeypatch.setattr("tools.autopilot.__main__.loop.run", fake_loop_run)
    monkeypatch.setattr("tools.autopilot.__main__.preflight.run", lambda _c: _FakePreflight())
    monkeypatch.setattr(
        "tools.autopilot.__main__.Config.load", classmethod(lambda _cls: _stub_config())
    )
    monkeypatch.setattr("tools.autopilot.__main__._gate_auto_merge", lambda _c, _f: None)

    rc = cli_run(["run", "F99", "--auto-merge"])
    assert rc == 0
    assert captured["auto_merge"] is True
