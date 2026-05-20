"""Filesystem signal collector per spec §6.1."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

from scripts.work_state.models import WorkItem

logger = logging.getLogger(__name__)


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        logger.warning("OSError checking path: %s", path)
        return False


def _check_spec_moved(
    feature_id: str,
    repo_root: Path,
) -> str | None:
    """Glob for possible renamed spec file per spec §6.1 drift detection."""
    features_dir = repo_root / "docs" / "features"
    if not features_dir.is_dir():
        return None
    try:
        candidates = list(features_dir.glob(f"*{feature_id}*.md"))
    except OSError:
        return None
    if candidates:
        return str(candidates[0])
    return None


class FilesystemSignals(TypedDict):
    spec_exists: bool
    tech_exists: bool
    warnings: list[str]


def collect_filesystem_signals(
    item: WorkItem,
    repo_root: Path,
) -> FilesystemSignals:
    """Collect filesystem signals for a work item."""
    warnings: list[str] = []

    product_path = item.specs.get("product")
    tech_path = item.specs.get("tech")

    spec_exists = False
    if product_path is None:
        warnings.append("missing_spec_link")
    else:
        spec_exists = _safe_is_file(repo_root / product_path)
        if not spec_exists:
            suggested = _check_spec_moved(item.feature_id, repo_root)
            if suggested is not None:
                warnings.append("possible_spec_moved")

    tech_exists = False
    if tech_path is None:
        warnings.append("missing_tech_link")
    else:
        tech_exists = _safe_is_file(repo_root / tech_path)

    return {
        "spec_exists": spec_exists,
        "tech_exists": tech_exists,
        "warnings": warnings,
    }
