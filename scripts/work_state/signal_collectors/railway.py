"""Railway deploy signal collector per spec §6.7. HTTP API, unknown-safe."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

CACHE_DIR = Path(".dashboard/cache")
RAILWAY_TTL_SECONDS = 60
RAILWAY_TIMEOUT_SECONDS = 5
RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"

_DEPLOYMENTS_QUERY = """
query($projectId: String!) {
  deployments(
    input: { projectId: $projectId }
    first: 1
  ) {
    edges {
      node {
        id
        status
        createdAt
        updatedAt
      }
    }
  }
}
"""

_STATUS_MAP: dict[str, str] = {
    "SUCCESS": "deployed",
    "BUILDING": "deploying",
    "DEPLOYING": "deploying",
    "INITIALIZING": "deploying",
    "FAILED": "deploy-failed",
    "CRASHED": "deploy-failed",
    "REMOVED": "none",
}


class RailwaySignals(TypedDict):
    deploy_state: str
    last_deploy_at: str | None
    overlays: list[str]
    warnings: list[str]


def _read_cache(key: str, ttl: int) -> dict[str, object] | None:
    cache_file = CACHE_DIR / f"railway_{key}.json"
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
    cache_file = CACHE_DIR / f"railway_{key}.json"
    try:
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Failed to write Railway cache: %s", cache_file)


def _railway_query(
    project_id: str,
    token: str,
    *,
    no_network: bool = False,
) -> dict[str, object]:
    cache_key = f"deploy_{project_id}"
    cached = _read_cache(cache_key, RAILWAY_TTL_SECONDS)
    if cached is not None:
        return cached
    if no_network:
        return {"data": {"deployments": {"edges": []}}}

    payload = json.dumps(
        {
            "query": _DEPLOYMENTS_QUERY,
            "variables": {"projectId": project_id},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        RAILWAY_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=RAILWAY_TIMEOUT_SECONDS) as resp:
        data: dict[str, object] = json.loads(resp.read().decode("utf-8"))

    _write_cache(cache_key, data)
    return data


def collect_railway_signals(
    project_id: str,
    token: str | None,
    *,
    no_network: bool = False,
) -> RailwaySignals:
    """Collect Railway deploy signals. Unknown-safe on missing token or network failure."""
    if not token:
        return {
            "deploy_state": "unknown",
            "last_deploy_at": None,
            "overlays": [],
            "warnings": ["railway_unknown"],
        }

    try:
        data = _railway_query(project_id, token, no_network=no_network)
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        logger.warning("Railway API failed: %s", exc)
        return {
            "deploy_state": "unknown",
            "last_deploy_at": None,
            "overlays": [],
            "warnings": ["railway_unknown"],
        }

    deployments_data = data.get("data", {})
    if not isinstance(deployments_data, dict):
        deployments_data = {}
    deployments_obj = deployments_data.get("deployments", {})
    if not isinstance(deployments_obj, dict):
        deployments_obj = {}
    edges = deployments_obj.get("edges", [])
    if not isinstance(edges, list) or not edges:
        return {
            "deploy_state": "none",
            "last_deploy_at": None,
            "overlays": [],
            "warnings": ["railway_no_project"],
        }

    latest = edges[0]
    if not isinstance(latest, dict):
        return {
            "deploy_state": "unknown",
            "last_deploy_at": None,
            "overlays": [],
            "warnings": ["railway_unknown"],
        }

    node = latest.get("node", {})
    if not isinstance(node, dict):
        return {
            "deploy_state": "unknown",
            "last_deploy_at": None,
            "overlays": [],
            "warnings": ["railway_unknown"],
        }

    raw_status = str(node.get("status", ""))
    deploy_state = _STATUS_MAP.get(raw_status, "unknown")
    created_at = node.get("createdAt")
    last_deploy_at = str(created_at) if created_at else None

    warnings: list[str] = []
    overlays: list[str] = []
    if deploy_state == "unknown":
        warnings.append("railway_unknown")
    elif deploy_state == "deploy-failed":
        overlays.append("deploy-failed")

    return {
        "deploy_state": deploy_state,
        "last_deploy_at": last_deploy_at,
        "overlays": overlays,
        "warnings": warnings,
    }
