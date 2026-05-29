"""Dashboard projection — enrich docs/dashboard.json with computed state block.

Pure consumer of .dashboard/current_state.json (written by engine driver).
No network calls. Per spec §10 + §11.1, AC1g/AC5/AC6/AC10/AC11a.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from work_state.state_store import read_current_state

logger = logging.getLogger(__name__)

URGENCY_EMOJI: dict[str, str] = {
    "critical": "🔥",
    "elevated": "⚠️",
    "warning": "👁",
    "normal": "✓",
}


def load_state(dashboard_dir: Path) -> dict[str, object] | None:
    """Load cached current_state.json. Returns None if missing/malformed."""
    return read_current_state(dashboard_dir)


def _str_field(container: dict[str, object], key: str, default: str) -> str:
    val = container.get(key, default)
    return val if isinstance(val, str) else default


def build_state_block(state_item: dict[str, object]) -> dict[str, object]:
    """Extract 8-field state block from a CurrentState dict per AC5."""
    signals = state_item.get("signals", {})
    if not isinstance(signals, dict):
        signals = {}

    overlays = state_item.get("overlays", [])
    if not isinstance(overlays, list):
        overlays = []

    urgency = _str_field(state_item, "runtime_urgency", "normal")

    return {
        "computed_status": _str_field(state_item, "status", "unknown"),
        "human_status": _str_field(state_item, "human_status", "UNKNOWN"),
        "pr_state": _str_field(signals, "pr_state", "unknown"),
        "ci_state": _str_field(signals, "ci_state", "unknown"),
        "review_state": _str_field(signals, "review_state", "unknown"),
        "deploy_state": _str_field(signals, "deploy_state", "unknown"),
        "overlays": overlays,
        "last_event_ts": state_item.get("last_event_ts"),
        "urgency": urgency,
        "urgency_emoji": URGENCY_EMOJI.get(urgency, "✓"),
    }


def enrich_dashboard(
    dashboard_json: dict[str, object],
    state_data: Mapping[str, object] | None,
) -> dict[str, object]:
    """Additive merge: append state block to each matching feature row.

    Existing fields untouched (AC6). Features without matching state skipped.
    """
    result = copy.deepcopy(dashboard_json)

    if state_data is None:
        logger.warning("No state data available — dashboard returned unchanged")
        return result

    items = state_data.get("items", [])
    if not isinstance(items, list):
        logger.warning("state_data['items'] is not a list — skipping enrichment")
        return result

    state_by_id: dict[str, dict[str, object]] = {}
    for item in items:
        if isinstance(item, dict):
            item_id = item.get("item_id")
            if isinstance(item_id, str):
                state_by_id[item_id] = item

    features = result.get("features", [])
    if not isinstance(features, list):
        return result

    for feature in features:
        if not isinstance(feature, dict):
            continue
        feature_id = feature.get("id")
        if isinstance(feature_id, str) and feature_id in state_by_id:
            feature["state"] = build_state_block(state_by_id[feature_id])

    return result


def _read_json_file(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enrich dashboard.json with computed state from work-state engine",
    )
    parser.add_argument(
        "--tracker",
        type=Path,
        default=Path("docs/implementation-tracker.md"),
        help="Path to tracker markdown (unused by projection — kept for CLI compat)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/dashboard.json"),
        help="Output path for enriched dashboard JSON",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        default=True,
        help="Use cached state only (default; projection never makes network calls)",
    )
    parser.add_argument(
        "--dashboard-dir",
        type=Path,
        default=Path(".dashboard"),
        help="Path to .dashboard/ directory with current_state.json",
    )

    args = parser.parse_args(argv)

    state_data = load_state(args.dashboard_dir)
    if state_data is None:
        logger.warning(
            "No current_state.json in %s — output will lack state blocks",
            args.dashboard_dir,
        )

    dashboard_json = _read_json_file(args.output)
    if dashboard_json is None:
        logger.error("Cannot read dashboard JSON at %s", args.output)
        return 1

    enriched = enrich_dashboard(dashboard_json, state_data)

    output_text = json.dumps(enriched, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        dir=args.output.parent,
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(output_text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(args.output)
    logger.info("Wrote enriched dashboard to %s", args.output)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
