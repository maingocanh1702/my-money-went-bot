"""Build dashboard.json — aggregate tracker + roadmap + doc versions.

Schema (deterministic key order via sort_keys=True at emit-time):
  generated_at: ISO8601 UTC
  overall: {overall_progress, mvp_percent, mvp_total, mvp_merged}
  phases:  [{name, status, progress, tasks}]
  features: [{id, name, spec, be_tech, be_code, bot_code, phase}]
  blockers: [{name, affects, status, status_slug, notes}]
  risks:    [{name, phase, impact, mitigation}]
  docs:     [{name, version, updated, stale_days}]
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_dashboard_json(
    tracker_data: dict[str, Any],
    roadmap_data: dict[str, Any],
    doc_versions: list[dict[str, Any]],
) -> dict[str, Any]:
    overall_progress = (roadmap_data.get("overall") or {}).get("overall_progress", 0)
    mvp = tracker_data.get("mvp") or {}
    overall = {
        "overall_progress": overall_progress,
        "mvp_percent": mvp.get("percent", 0),
        "mvp_total": mvp.get("total", 0),
        "mvp_merged": mvp.get("merged", 0),
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "overall": overall,
        "phases": (roadmap_data.get("overall") or {}).get("phases", []),
        "features": roadmap_data.get("features", []),
        "blockers": roadmap_data.get("blockers", []),
        "risks": roadmap_data.get("risks", []),
        "docs": doc_versions,
    }
