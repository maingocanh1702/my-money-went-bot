"""Update implementation-tracker.md row status when an autopilot run progresses.

Tracker rows have format (markdown table):
| W0.7 | ... | F02 ... | 🟡 | `branch` | gates | notes |

The status emoji column (4th) is what we update. We DO NOT touch other
columns. Match by feature_id appearing in the PR column (1st).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config

STATUS_EMOJI = {
    "INIT": "🟡",  # in progress
    "CODEGEN": "🟡",
    "VERIFIED": "🟠",  # code done, in review
    "REVIEWING": "🟠",
    "READY": "🟢",  # review pass, ready to merge
    "MERGED": "✅",
    "HALTED": "❌",
}

# Match a tracker row whose first cell contains the feature_id token.
# Tracker rows look like:  | F02 | Wave 2 | F02 — ... | 🟡 | `branch` | gates | notes |
TABLE_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|", re.MULTILINE)


@dataclass
class TrackerUpdate:
    feature_id: str
    old_status: str | None
    new_status: str
    row_index: int
    success: bool
    note: str = ""


def update_status(
    cfg: Config,
    feature_id: str,
    phase: str,
) -> TrackerUpdate:
    """Find tracker row for feature_id and update its status emoji."""
    if not cfg.tracker_path.exists():
        return TrackerUpdate(
            feature_id=feature_id,
            old_status=None,
            new_status="",
            row_index=-1,
            success=False,
            note=f"tracker file missing: {cfg.tracker_path}",
        )
    new_emoji = STATUS_EMOJI.get(phase)
    if new_emoji is None:
        return TrackerUpdate(
            feature_id=feature_id,
            old_status=None,
            new_status="",
            row_index=-1,
            success=False,
            note=f"no emoji mapping for phase {phase!r}",
        )

    text = cfg.tracker_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    target_index = -1
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 4:
            continue
        # Match feature_id case-insensitively as token in first cell.
        first_cell = cells[0].lower()
        token = feature_id.lower()
        if token == first_cell or token in re.split(r"[\s.\-]+", first_cell):
            target_index = i
            break

    if target_index == -1:
        return TrackerUpdate(
            feature_id=feature_id,
            old_status=None,
            new_status=new_emoji,
            row_index=-1,
            success=False,
            note=f"no row found matching feature_id {feature_id!r}",
        )

    parts = lines[target_index].split("|")
    # parts: ['', ' PR ', ' Wave ', ' Feature ', ' status ', ...trailing, '']
    if len(parts) < 6:
        return TrackerUpdate(
            feature_id=feature_id,
            old_status=None,
            new_status=new_emoji,
            row_index=target_index,
            success=False,
            note="row has fewer columns than expected; aborting in-place edit",
        )
    old_status = parts[4].strip()
    parts[4] = f" {new_emoji} "
    lines[target_index] = "|".join(parts)
    cfg.tracker_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TrackerUpdate(
        feature_id=feature_id,
        old_status=old_status,
        new_status=new_emoji,
        row_index=target_index,
        success=True,
    )
