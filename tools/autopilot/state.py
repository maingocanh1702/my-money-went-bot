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

import dataclasses
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)

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
    # Phase the loop was in when transitioning to HALTED, so ``resume`` can
    # re-enter at the same phase rather than returning a silent no-op.
    # Set by ``transition`` when new_phase == "HALTED".
    last_active_phase: str | None = None

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
    """Read state.json and instantiate FeatureState.

    v0.2.2: schema tolerance. Filter unknown fields (with a warning) so
    state files written by a newer orchestrator schema can be loaded by
    older code during partial deploys, and so a stale field added by an
    abandoned branch doesn't permanently brick resume. Previously
    ``FeatureState(**raw)`` raised ``TypeError`` on the first unknown
    key, halting F07 resume after v0.2.1 added ``last_active_phase``.
    """
    path = state_path(cfg, feature_id)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    known_fields = {f.name for f in dataclasses.fields(FeatureState)}
    unknown = set(raw.keys()) - known_fields
    if unknown:
        log.warning(
            "state.load: ignoring unknown fields in %s: %s "
            "(orchestrator version may be older than state file schema)",
            path,
            sorted(unknown),
        )
        raw = {k: v for k, v in raw.items() if k in known_fields}
    return FeatureState(**raw)


def transition(state: FeatureState, new_phase: str) -> None:
    if new_phase not in PHASE_ORDER:
        raise ValueError(f"unknown phase {new_phase!r}")
    # Capture the phase we're leaving when going to HALTED so resume can
    # re-enter at the right place. Don't overwrite when already HALTED.
    if new_phase == "HALTED" and state.phase != "HALTED":
        state.last_active_phase = state.phase
    state.phase = new_phase
