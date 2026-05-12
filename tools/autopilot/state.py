"""JSON checkpoint state per feature, for resume on circuit-break or crash.

State file: ``.autopilot/state/<feature_id>/state.json``.

Phases (write checkpoint after each transition):
- INIT       → preflight passed
- CODEGEN    → Phase A complete (initial commits exist)
- VERIFIED   → Phase B local verify green
- REVIEWING  → Phase C in progress (current_round set)
- READY      → Phase D pre-merge gates passed
- MERGED     → Phase E done
- HALTED     → circuit broken (stays here until founder action)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Config

PHASE_ORDER = ("INIT", "CODEGEN", "VERIFIED", "REVIEWING", "READY", "MERGED", "HALTED")


@dataclass
class FeatureState:
    feature_id: str
    branch: str
    base_branch: str
    fe_spec: str
    be_spec: str
    phase: str = "INIT"
    current_round: int = 0
    consecutive_clean_rounds: int = 0
    fixed_finding_hashes: list[str] = field(default_factory=list)
    halt_reason: str | None = None
    halt_artifact_path: str | None = None
    started_at: str = ""
    last_updated_at: str = ""
    initial_head_sha: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def state_path(cfg: Config, feature_id: str) -> Path:
    return cfg.state_dir / feature_id / "state.json"


def save(cfg: Config, state: FeatureState) -> Path:
    """Atomic write: serialize to .tmp then rename. POSIX rename is atomic,
    so a crash mid-write leaves either the previous good state or the new
    one — never a truncated file (Blocker #4).
    """
    import datetime as _dt

    state.last_updated_at = _dt.datetime.now(_dt.UTC).isoformat()
    path = state_path(cfg, state.feature_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(state.to_json(), encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return path


def load(cfg: Config, feature_id: str) -> FeatureState | None:
    path = state_path(cfg, feature_id)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FeatureState(**raw)


def transition(state: FeatureState, new_phase: str) -> None:
    if new_phase not in PHASE_ORDER:
        raise ValueError(f"unknown phase {new_phase!r}")
    state.phase = new_phase
