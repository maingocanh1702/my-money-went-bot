"""Filesystem signal collector per spec §6.1 + Phase B hash tracking."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from work_state.models import WorkItem

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


def _compute_file_hash(path: Path) -> str | None:
    """SHA256 hex of file content. None if file missing or unreadable."""
    try:
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        logger.warning("OSError hashing file: %s", path)
        return None


def _get_file_mtime(path: Path) -> str | None:
    """ISO datetime string of file mtime. None if file missing."""
    try:
        if not path.is_file():
            return None
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=UTC).isoformat()
    except OSError:
        return None


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace to single space, strip."""
    return re.sub(r"\s+", " ", text).strip()


def _compute_tracker_row_hash(item: WorkItem) -> str | None:
    """SHA256 of semantic fields only per spec §6.1 Phase B.

    Includes: branches, linear_id, feature_id, specs paths, acceptance.
    Excludes: status, notes, gates, changelog, formatting whitespace.
    """
    semantic_data = {
        "branches": sorted(item.branches),
        "linear_id": item.linear_id,
        "feature_id": item.feature_id,
        "specs": {k: v for k, v in sorted(item.specs.items())},
        "acceptance": [_normalize_whitespace(a) for a in item.acceptance],
    }
    canonical = json.dumps(semantic_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FilesystemSignals(TypedDict):
    spec_exists: bool
    tech_exists: bool
    warnings: list[str]
    spec_hash: str | None
    spec_modified_at: str | None
    tech_hash: str | None
    tech_modified_at: str | None
    tracker_row_hash: str | None


def collect_filesystem_signals(
    item: WorkItem,
    repo_root: Path,
) -> FilesystemSignals:
    """Collect filesystem signals for a work item."""
    warnings: list[str] = []

    product_path = item.specs.get("product")
    tech_path = item.specs.get("tech")

    spec_exists = False
    spec_hash: str | None = None
    spec_modified_at: str | None = None
    if product_path is None:
        warnings.append("missing_spec_link")
    else:
        full_spec_path = repo_root / product_path
        spec_exists = _safe_is_file(full_spec_path)
        if spec_exists:
            spec_hash = _compute_file_hash(full_spec_path)
            spec_modified_at = _get_file_mtime(full_spec_path)
        else:
            suggested = _check_spec_moved(item.feature_id, repo_root)
            if suggested is not None:
                warnings.append("possible_spec_moved")

    tech_exists = False
    tech_hash: str | None = None
    tech_modified_at: str | None = None
    if tech_path is None:
        warnings.append("missing_tech_link")
    else:
        full_tech_path = repo_root / tech_path
        tech_exists = _safe_is_file(full_tech_path)
        if tech_exists:
            tech_hash = _compute_file_hash(full_tech_path)
            tech_modified_at = _get_file_mtime(full_tech_path)

    tracker_row_hash = _compute_tracker_row_hash(item)

    return {
        "spec_exists": spec_exists,
        "tech_exists": tech_exists,
        "warnings": warnings,
        "spec_hash": spec_hash,
        "spec_modified_at": spec_modified_at,
        "tech_hash": tech_hash,
        "tech_modified_at": tech_modified_at,
        "tracker_row_hash": tracker_row_hash,
    }
