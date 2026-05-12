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
