"""Production engine driver — orchestrates WorkItems → Signals → status → state file.

CLI: python -m scripts.work_state.engine --tracker PATH --dashboard-dir PATH [--no-network]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from scripts.work_state.models import CurrentState, Signals, WorkItem
from scripts.work_state.plan_reader import read_tracker
from scripts.work_state.progress import compute_progress
from scripts.work_state.signal_collectors.ci import collect_ci_signals
from scripts.work_state.signal_collectors.filesystem import collect_filesystem_signals
from scripts.work_state.signal_collectors.git import GitSignals, collect_git_signals
from scripts.work_state.signal_collectors.github import collect_github_signals
from scripts.work_state.signal_collectors.railway import collect_railway_signals
from scripts.work_state.state_store import read_current_state, write_current_state
from scripts.work_state.status_machine import (
    aggregate_multi_branch_overlays,
    aggregate_multi_branch_status,
    compute_human_status,
    compute_overlays,
    compute_status,
)

logger = logging.getLogger(__name__)

REPO = os.environ.get("GITHUB_REPOSITORY", "maingocanh1702/MyMoneyWent")
RAILWAY_PROJECT_ID = os.environ.get("RAILWAY_PROJECT_ID", "")
RAILWAY_TOKEN = os.environ.get("RAILWAY_API_TOKEN")
DEFAULT_CACHE_SCHEMA_VERSION = "v1"


def _validate_cache_schema(dashboard_dir: Path) -> None:
    """Check .schema_version marker against CACHE_SCHEMA_VERSION env var."""
    expected = os.environ.get("CACHE_SCHEMA_VERSION", DEFAULT_CACHE_SCHEMA_VERSION)
    marker_file = dashboard_dir / ".schema_version"

    if marker_file.exists():
        stored = marker_file.read_text(encoding="utf-8").strip()
        if stored != expected:
            logger.warning(
                "Cache schema mismatch: stored=%s, expected=%s — treating as cold start",
                stored,
                expected,
            )

    marker_file.parent.mkdir(parents=True, exist_ok=True)
    marker_file.write_text(expected, encoding="utf-8")


def _collect_branch_signals(
    branch: str,
    item: WorkItem,
    repo_root: Path,
    *,
    no_network: bool,
) -> tuple[Signals, list[str]]:
    """Collect all signals for a single branch. Returns (Signals, overlays)."""
    fs = collect_filesystem_signals(item, repo_root)
    git = collect_git_signals(branch) if not no_network else _git_no_network(branch)
    gh = collect_github_signals(item, REPO, no_network=no_network)
    ci = collect_ci_signals(git["last_commit_sha"], REPO, no_network=no_network)
    rw = collect_railway_signals(RAILWAY_PROJECT_ID, RAILWAY_TOKEN, no_network=no_network)

    all_warnings = (
        list(fs["warnings"])
        + list(git["warnings"])
        + list(gh["warnings"])
        + list(ci["warnings"])
        + list(rw["warnings"])
    )
    overlays = list(ci["overlays"]) + list(rw["overlays"])

    signals = Signals(
        spec_exists=fs["spec_exists"],
        tech_exists=fs["tech_exists"],
        branch_exists=git["branch_exists"],
        commits_count=git["commits_count"],
        last_commit_sha=git["last_commit_sha"],
        pr_state=gh["pr_state"],
        pr_number=gh["pr_number"],
        review_state=gh["review_state"],
        ci_state=ci["ci_state"],
        deploy_state=rw["deploy_state"],
        warnings=all_warnings,
        pr_url=gh["pr_url"],
        ci_check_run_count=ci["ci_check_run_count"],
        last_review_at=gh["last_review_at"],
        last_deploy_at=rw["last_deploy_at"],
        spec_hash=fs["spec_hash"],
        spec_modified_at=fs["spec_modified_at"],
        tech_hash=fs["tech_hash"],
        tech_modified_at=fs["tech_modified_at"],
        tracker_row_hash=fs["tracker_row_hash"],
    )
    return signals, overlays


def _git_no_network(branch: str) -> GitSignals:
    """Fallback git signals when --no-network is set."""
    return {
        "branch_exists": bool(branch),
        "commits_count": 0,
        "last_commit_sha": None,
        "warnings": [],
    }


def _pick_representative_branch(statuses: list[str], aggregated: str) -> int:
    """Pick the branch index whose status matches the aggregated base status."""
    for i, s in enumerate(statuses):
        if s == aggregated:
            return i
    return 0


def _load_prev_hashes(
    dashboard_dir: Path,
) -> dict[str, tuple[str | None, str | None, str | None]]:
    """Load previous spec_hash, tech_hash, tracker_row_hash per item_id."""
    prev = read_current_state(dashboard_dir)
    if prev is None:
        return {}
    items = prev.get("items", [])
    if not isinstance(items, list):
        return {}
    result: dict[str, tuple[str | None, str | None, str | None]] = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("item_id")
        if not isinstance(item_id, str):
            continue
        signals = entry.get("signals", {})
        if not isinstance(signals, dict):
            signals = {}
        spec_h = signals.get("spec_hash")
        tech_h = signals.get("tech_hash")
        tracker_h = signals.get("tracker_row_hash")
        result[item_id] = (
            spec_h if isinstance(spec_h, str) else None,
            tech_h if isinstance(tech_h, str) else None,
            tracker_h if isinstance(tracker_h, str) else None,
        )
    return result


def run_engine(
    tracker_path: str,
    dashboard_dir: Path,
    no_network: bool = False,
) -> list[CurrentState]:
    """Main engine: tracker → WorkItems → Signals → status → state file."""
    tracker = Path(tracker_path)
    if not tracker.exists():
        logger.warning("Tracker not found: %s — returning empty", tracker_path)
        return []

    _validate_cache_schema(dashboard_dir)
    prev_hashes = _load_prev_hashes(dashboard_dir)

    parsed_items = read_tracker(tracker_path)
    repo_root = Path.cwd()
    states: list[CurrentState] = []

    for parsed in parsed_items:
        item = parsed.item
        if not item.branches:
            logger.info("Skipping %s — no branches", item.id)
            continue

        prev_spec_h, prev_tech_h, prev_tracker_h = prev_hashes.get(item.id, (None, None, None))

        if len(item.branches) == 1:
            signals, overlays = _collect_branch_signals(
                item.branches[0], item, repo_root, no_network=no_network
            )
            status = compute_status(signals)
            doc_overlays = compute_overlays(
                signals,
                status,
                prev_spec_hash=prev_spec_h,
                prev_tech_hash=prev_tech_h,
                prev_tracker_row_hash=prev_tracker_h,
            )
            overlays = sorted(set(overlays) | set(doc_overlays))
            human = compute_human_status(status, overlays, signals.deploy_state)
            try:
                progress = compute_progress(signals, item.progress_profile)
            except NotImplementedError:
                progress = 0
        else:
            branch_data: list[tuple[str, list[str]]] = []
            branch_signals_list: list[Signals] = []

            for branch in item.branches:
                signals, overlays = _collect_branch_signals(
                    branch, item, repo_root, no_network=no_network
                )
                branch_status = compute_status(signals)
                branch_data.append((branch_status, overlays))
                branch_signals_list.append(signals)

            statuses = [s for s, _ in branch_data]
            status = aggregate_multi_branch_status(statuses)
            overlays = aggregate_multi_branch_overlays(branch_data)
            representative_idx = _pick_representative_branch(statuses, status)
            signals = branch_signals_list[representative_idx]
            doc_overlays = compute_overlays(
                signals,
                status,
                prev_spec_hash=prev_spec_h,
                prev_tech_hash=prev_tech_h,
                prev_tracker_row_hash=prev_tracker_h,
            )
            overlays = sorted(set(overlays) | set(doc_overlays))
            human = compute_human_status(status, overlays, signals.deploy_state)
            try:
                progress = compute_progress(signals, item.progress_profile)
            except NotImplementedError:
                progress = 0

        state = CurrentState(
            item_id=item.id,
            status=status,
            human_status=human,
            progress=progress,
            runtime_urgency="normal",
            overlays=overlays,
            signals=signals,
            last_event_ts=None,
        )
        states.append(state)

    write_current_state(states, dashboard_dir)
    return states


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Work-state engine — artifact-derived authoritative state"
    )
    parser.add_argument(
        "--tracker",
        default="docs/implementation-tracker.md",
        help="Path to tracker markdown file",
    )
    parser.add_argument(
        "--dashboard-dir",
        default=".dashboard/",
        help="Path to .dashboard/ output directory",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Skip network calls (use cached/default signals)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    states = run_engine(
        tracker_path=args.tracker,
        dashboard_dir=Path(args.dashboard_dir),
        no_network=args.no_network,
    )
    logger.info("Engine produced %d CurrentState entries", len(states))
    return 0


if __name__ == "__main__":
    sys.exit(main())
