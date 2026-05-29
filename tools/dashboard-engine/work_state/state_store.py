"""State store — .dashboard/ JSON IO per spec §7.3."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from work_state.models import CurrentState


def write_current_state(states: list[CurrentState], dashboard_dir: Path) -> None:
    """Write current_state.json to .dashboard/ directory."""
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    state_file = dashboard_dir / "current_state.json"
    data = {"items": [asdict(s) for s in states]}
    state_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_current_state(dashboard_dir: Path) -> dict[str, object] | None:
    """Read current_state.json. Returns None if file missing (first run)."""
    state_file = dashboard_dir / "current_state.json"
    if not state_file.exists():
        return None
    try:
        text = state_file.read_text(encoding="utf-8")
        return json.loads(text)  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError):
        return None
