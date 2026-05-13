"""Parse Version/Updated header from canonical docs (BRD/PRD/TDD)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

_VERSION_RE = re.compile(r"\*\*Version:\*\*\s*([^\s<>]+)")
_UPDATED_RE = re.compile(r"\*\*Cập nhật lần cuối:\*\*\s*(\d{4}-\d{2}-\d{2})")
_CREATED_RE = re.compile(r"\*\*Ngày tạo:\*\*\s*(\d{4}-\d{2}-\d{2})")


def compute_staleness(updated_iso: str, today: date) -> int:
    """Days between today and updated_iso. Negative means future date → clamp to 0."""
    parts = updated_iso.split("-")
    updated = date(int(parts[0]), int(parts[1]), int(parts[2]))
    delta = (today - updated).days
    return max(delta, 0)


def parse_doc_version_header(path: Path, today: date | None = None) -> dict[str, Any]:
    """Read first ~30 lines, extract version+updated, compute stale_days.

    Returns {name, version, updated, stale_days}. Missing fields → None
    for version/updated, 0 for stale_days.
    """
    head = ""
    try:
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                head += line
                if i >= 40:
                    break
    except OSError:
        return {"name": path.name, "version": None, "updated": None, "stale_days": 0}

    v = _VERSION_RE.search(head)
    u = _UPDATED_RE.search(head) or _CREATED_RE.search(head)
    version = v.group(1) if v else None
    updated = u.group(1) if u else None
    today = today or date.today()
    stale = compute_staleness(updated, today) if updated else 0
    return {
        "name": path.name,
        "version": version,
        "updated": updated,
        "stale_days": stale,
    }
