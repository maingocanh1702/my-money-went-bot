"""Unit tests for state.save atomic write (Blocker #4).

The save path must produce either the previous good state OR the new one,
never a truncated file, even if a crash interrupts the write.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.autopilot import state as state_mod
from tools.autopilot.config import Config
from tools.autopilot.state import FeatureState


def _cfg(repo: Path) -> Config:
    return Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )


def _seed_state(feature_id: str) -> FeatureState:
    return FeatureState(
        feature_id=feature_id,
        branch=f"feat/{feature_id}-x",
        base_branch="main",
        fe_spec="docs/features/x.md",
        be_spec="docs/features/BE/x-tech.md",
    )


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    s = _seed_state("F99")
    state_mod.save(cfg, s)
    loaded = state_mod.load(cfg, "F99")
    assert loaded is not None
    assert loaded.feature_id == "F99"
    assert loaded.branch == "feat/F99-x"


def test_save_is_atomic_pre_existing_truncated_tmp_does_not_block(
    tmp_path: Path,
) -> None:
    """Simulate prior crash: a stale truncated state.json.tmp sits next to
    the real file. New save must succeed and produce the new state. Load
    returns the new state, not the truncated tmp.
    """
    cfg = _cfg(tmp_path)
    s1 = _seed_state("F99")
    state_mod.save(cfg, s1)

    path = state_mod.state_path(cfg, "F99")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text("{", encoding="utf-8")  # truncated garbage

    s2 = _seed_state("F99")
    s2.phase = "VERIFIED"
    state_mod.save(cfg, s2)

    loaded = state_mod.load(cfg, "F99")
    assert loaded is not None
    assert loaded.phase == "VERIFIED"
    assert not tmp.exists(), "save must clean up its tmp file"


def test_save_failure_leaves_previous_state_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the .tmp write succeeds but rename fails (simulated), the
    previous state.json must NOT be clobbered. Load returns the old value.
    """
    cfg = _cfg(tmp_path)
    s1 = _seed_state("F99")
    state_mod.save(cfg, s1)
    path = state_mod.state_path(cfg, "F99")
    original_text = path.read_text(encoding="utf-8")

    real_replace = Path.replace

    def failing_replace(self: Path, target: Path) -> Path:
        if str(self).endswith(".json.tmp"):
            raise OSError("simulated crash mid-rename")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)

    s2 = _seed_state("F99")
    s2.phase = "VERIFIED"
    with pytest.raises(OSError):
        state_mod.save(cfg, s2)

    assert path.read_text(encoding="utf-8") == original_text
    tmp = path.with_suffix(".json.tmp")
    assert not tmp.exists(), "failed save must clean up its tmp file"


# --- last_active_phase / resume-from-HALTED (v0.2.1) ---------------------


def test_transition_to_halted_records_last_active_phase() -> None:
    """Going to HALTED captures the phase we left so resume can re-enter."""
    s = _seed_state("F99")
    s.phase = "REVIEWING"
    state_mod.transition(s, "HALTED")
    assert s.phase == "HALTED"
    assert s.last_active_phase == "REVIEWING"


def test_transition_non_halted_leaves_last_active_phase_alone() -> None:
    """Normal forward transitions don't touch last_active_phase."""
    s = _seed_state("F99")
    s.phase = "INIT"
    assert s.last_active_phase is None
    state_mod.transition(s, "CODEGEN")
    assert s.phase == "CODEGEN"
    assert s.last_active_phase is None


def test_transition_halted_twice_preserves_first_active_phase() -> None:
    """Repeated HALTED transitions must not overwrite the originally
    captured phase (which would lose the resume target)."""
    s = _seed_state("F99")
    s.phase = "VERIFIED"
    state_mod.transition(s, "HALTED")
    assert s.last_active_phase == "VERIFIED"
    state_mod.transition(s, "HALTED")  # idempotent
    assert s.last_active_phase == "VERIFIED"


def test_load_state_predating_v0_2_1_defaults_last_active_phase_to_none(
    tmp_path: Path,
) -> None:
    """State files written before v0.2.1 lack last_active_phase. Load must
    succeed and default the field to None.
    """
    cfg = _cfg(tmp_path)
    path = state_mod.state_path(cfg, "F99")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Hand-written legacy state.json shape (no last_active_phase key).
    legacy = """{
        "feature_id": "F99",
        "branch": "feat/F99-x",
        "base_branch": "main",
        "fe_spec": "docs/features/x.md",
        "be_spec": "docs/features/BE/x-tech.md",
        "phase": "HALTED",
        "current_round": 1,
        "consecutive_clean_rounds": 0,
        "fixed_finding_hashes": [],
        "halt_reason": "FIX_FAILED: ...",
        "halt_artifact_path": null,
        "started_at": "2026-05-12T00:00:00+00:00",
        "last_updated_at": "2026-05-12T00:10:00+00:00",
        "initial_head_sha": "abc"
    }"""
    path.write_text(legacy, encoding="utf-8")
    loaded = state_mod.load(cfg, "F99")
    assert loaded is not None
    assert loaded.phase == "HALTED"
    assert loaded.last_active_phase is None
