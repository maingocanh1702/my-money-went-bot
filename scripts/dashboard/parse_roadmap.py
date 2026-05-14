"""Parse roadmap §1 overall progress, §2 features, §6 blockers, §7 risks.

Pure-read: never mutates source text. Tolerates whitespace variation.
"""

from __future__ import annotations

import re
from typing import Any

# Emoji → canonical status slug.
_EMOJI_STATUS = {
    "✅": "done",
    "🟢": "done",
    "🟡": "partial",
    "🟠": "partial",
    "⬜": "not_started",
    "🔲": "not_started",
    "❌": "blocked",
    "⏸️": "deferred",
    "⏸": "deferred",
}


def _status_from_emoji(cell: str) -> str:
    if not cell or cell.strip() == "—":
        return "not_started"
    for emoji, slug in _EMOJI_STATUS.items():
        if emoji in cell:
            return slug
    return "not_started"


def _first_int(cell: str) -> int | None:
    m = re.search(r"\d+", cell)
    return int(m.group(0)) if m else None


def _split_row(line: str) -> list[str] | None:
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip("|").split("|")]
    if not cells or all(set(c) <= set("-: ") for c in cells):
        return None
    return cells


def parse_roadmap_overall_progress(text: str) -> dict[str, Any]:
    """Returns {overall_progress: int, phases: [{name, status, progress, tasks}]}."""
    overall = 0
    m = re.search(r"Tổng tiến độ:\s*\**(\d+)%", text)
    if m:
        overall = int(m.group(1))
    phases: list[dict[str, Any]] = []
    for line in text.splitlines():
        cells = _split_row(line)
        if not cells or len(cells) < 4:
            continue
        if cells[0].lower() in ("phase", ""):
            continue
        # Filter to rows that look like phase rows (name contains "Phase")
        if "phase" not in cells[0].lower():
            continue
        progress = _first_int(cells[2]) or 0
        phases.append(
            {
                "name": cells[0],
                "status": _status_from_emoji(cells[1]),
                "status_label": cells[1],
                "progress": progress,
                "tasks": cells[3] if len(cells) > 3 else "",
            }
        )
    return {"overall_progress": overall, "phases": phases}


def parse_roadmap_features(text: str) -> list[dict[str, Any]]:
    """Returns [{id, name, spec, be_tech, be_code, bot_code, phase}]."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        cells = _split_row(line)
        if not cells or len(cells) < 7:
            continue
        # Header / divider filter
        if cells[0].lower() in ("module", ""):
            continue
        # Feature row: first cell is module id. Accepts:
        # - Legacy F-codes: F01, FAM, F-i18n (pre-2026-05-15 convention)
        # - Kebab-case feature names (single or multi-segment):
        #   `settings`, `reports`, `transaction-capture`, `funding-sources` (post-2026-05-15)
        if not re.match(r"^(F[-\w]+|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$", cells[0]):
            continue
        out.append(
            {
                "id": cells[0],
                "name": cells[1],
                "spec": _status_from_emoji(cells[2]),
                "be_tech": _status_from_emoji(cells[3]),
                "be_code": _status_from_emoji(cells[4]),
                "bot_code": _status_from_emoji(cells[5]),
                "phase": cells[6],
            }
        )
    return out


def parse_roadmap_blockers(text: str) -> list[dict[str, Any]]:
    """Returns [{name, affects, status, notes}]."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        cells = _split_row(line)
        if not cells or len(cells) < 4:
            continue
        if cells[0].lower() in ("blocker", ""):
            continue
        out.append(
            {
                "name": cells[0],
                "affects": cells[1],
                "status": cells[2],
                "status_slug": _status_from_emoji(cells[2]),
                "notes": cells[3],
            }
        )
    return out


def parse_roadmap_risks(text: str) -> list[dict[str, Any]]:
    """Returns [{name, phase, impact, mitigation}]."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        cells = _split_row(line)
        if not cells or len(cells) < 4:
            continue
        if cells[0].lower() in ("risk", ""):
            continue
        impact = re.sub(r"\([^)]*\)", "", cells[2]).strip()
        out.append(
            {
                "name": cells[0],
                "phase": cells[1],
                "impact": impact,
                "mitigation": cells[3],
            }
        )
    return out
