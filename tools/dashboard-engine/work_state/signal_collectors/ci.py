"""CI check-runs signal collector per spec §6.6."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

CACHE_DIR = Path(".dashboard/cache")
CI_TTL_SECONDS = 30


class CiSignals(TypedDict):
    ci_state: str
    ci_check_run_count: int
    overlays: list[str]
    warnings: list[str]


def _read_cache(key: str, ttl: int) -> dict[str, object] | None:
    cache_file = CACHE_DIR / f"ci_{key}.json"
    if not cache_file.exists():
        return None
    try:
        mtime = cache_file.stat().st_mtime
        if time.time() - mtime > ttl:
            return None
        return json.loads(cache_file.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(key: str, data: object) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"ci_{key}.json"
    try:
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Failed to write CI cache: %s", cache_file)


def _gh_get_check_runs(
    commit_sha: str, repo: str, *, no_network: bool = False
) -> dict[str, object]:
    cache_key = f"checks_{commit_sha[:12]}"
    cached = _read_cache(cache_key, CI_TTL_SECONDS)
    if cached is not None:
        return cached
    if no_network:
        return {"total_count": 0, "check_runs": []}
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo}/commits/{commit_sha}/check-runs",
            "--method",
            "GET",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"gh check-runs failed: {result.stderr.strip()}")
    data: dict[str, object] = json.loads(result.stdout)
    _write_cache(cache_key, data)
    return data


def collect_ci_signals(
    commit_sha: str | None,
    repo: str,
    *,
    no_network: bool = False,
) -> CiSignals:
    """Collect CI check-runs signals. Unknown-safe on network failure."""
    if not commit_sha:
        return {
            "ci_state": "unknown",
            "ci_check_run_count": 0,
            "overlays": [],
            "warnings": ["ci_no_commit_sha"],
        }

    try:
        data = _gh_get_check_runs(commit_sha, repo, no_network=no_network)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        logger.warning("CI check-runs fetch failed: %s", exc)
        return {
            "ci_state": "unknown",
            "ci_check_run_count": 0,
            "overlays": [],
            "warnings": ["ci_unknown"],
        }

    raw_runs = data.get("check_runs", [])
    if not isinstance(raw_runs, list):
        raw_runs = []

    non_skipped = [r for r in raw_runs if isinstance(r, dict) and r.get("conclusion") != "skipped"]
    count = len(non_skipped)
    overlays: list[str] = []
    warnings: list[str] = []

    if count == 0:
        return {
            "ci_state": "unknown",
            "ci_check_run_count": 0,
            "overlays": overlays,
            "warnings": ["ci_no_checks"],
        }

    has_failure = any(
        r.get("conclusion") in ("failure", "cancelled", "timed_out") for r in non_skipped
    )
    has_in_progress = any(r.get("status") in ("queued", "in_progress") for r in non_skipped)

    if has_failure:
        ci_state = "failure"
        overlays.append("ci-failing")
    elif has_in_progress:
        ci_state = "pending"
        overlays.append("ci-running")
    else:
        ci_state = "success"

    return {
        "ci_state": ci_state,
        "ci_check_run_count": count,
        "overlays": overlays,
        "warnings": warnings,
    }
