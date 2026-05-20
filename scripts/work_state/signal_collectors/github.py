"""GitHub signal collector — PR identity §6.3 + PR/review state §6.4/§6.5 + cache TTL."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TypedDict

from scripts.work_state.models import WorkItem

logger = logging.getLogger(__name__)

CACHE_DIR = Path(".dashboard/cache")
PR_LIST_TTL_SECONDS = 300
PR_DETAIL_TTL_SECONDS = 60


class PrIdentityResult(TypedDict):
    pr_number: int | None
    pr_state: str
    pr_url: str | None
    head_sha: str | None
    warnings: list[str]


class GithubSignals(TypedDict):
    pr_state: str
    pr_number: int | None
    pr_url: str | None
    review_state: str
    last_review_at: str | None
    warnings: list[str]


def _run_gh(args: list[str], timeout: int = 15) -> str:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"gh command failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _read_cache(key: str, ttl: int) -> list[dict[str, object]] | None:
    cache_file = CACHE_DIR / f"github_{key}.json"
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
    cache_file = CACHE_DIR / f"github_{key}.json"
    try:
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Failed to write cache: %s", cache_file)


def _gh_search_prs(repo: str, query: str, *, no_network: bool = False) -> list[dict[str, object]]:
    cache_key = f"search_{query.replace(' ', '_')}"
    cached = _read_cache(cache_key, PR_LIST_TTL_SECONDS)
    if cached is not None:
        return cached
    if no_network:
        return []
    raw = _run_gh(
        [
            "api",
            "search/issues",
            "--method",
            "GET",
            "-f",
            f"q={query} repo:{repo} type:pr",
            "-f",
            "per_page=10",
        ]
    )
    search_result: dict[str, object] = json.loads(raw)
    items = search_result.get("items", [])
    if not isinstance(items, list):
        items = []
    pr_numbers = [int(str(it.get("number", 0))) for it in items if isinstance(it, dict)]
    matches: list[dict[str, object]] = []
    for num in pr_numbers:
        if num == 0:
            continue
        pr_raw = _run_gh(["api", f"repos/{repo}/pulls/{num}", "--method", "GET"])
        matches.append(json.loads(pr_raw))
    _write_cache(cache_key, matches)
    return matches


def _gh_list_prs_by_head(
    repo: str, head_branch: str, *, no_network: bool = False
) -> list[dict[str, object]]:
    cache_key = f"head_{head_branch}"
    cached = _read_cache(cache_key, PR_LIST_TTL_SECONDS)
    if cached is not None:
        return cached
    if no_network:
        return []
    raw = _run_gh(
        [
            "api",
            f"repos/{repo}/pulls",
            "--method",
            "GET",
            "-f",
            "state=all",
            "-f",
            f"head={repo.split('/')[0]}:{head_branch}",
            "-f",
            "per_page=5",
        ]
    )
    result: list[dict[str, object]] = json.loads(raw)
    _write_cache(cache_key, result)
    return result


def _gh_get_reviews(
    repo: str, pr_number: int, *, no_network: bool = False
) -> list[dict[str, object]]:
    cache_key = f"reviews_{pr_number}"
    cached = _read_cache(cache_key, PR_DETAIL_TTL_SECONDS)
    if cached is not None:
        return cached
    if no_network:
        return []
    raw = _run_gh(
        [
            "api",
            f"repos/{repo}/pulls/{pr_number}/reviews",
            "--method",
            "GET",
        ]
    )
    result: list[dict[str, object]] = json.loads(raw)
    _write_cache(cache_key, result)
    return result


def _derive_pr_state(pr: dict[str, object]) -> str:
    if pr.get("merged_at") is not None:
        return "merged"
    if pr.get("state") == "closed":
        return "closed"
    if pr.get("draft"):
        return "draft"
    if pr.get("state") == "open":
        return "open"
    return "unknown"


def _pick_best_pr(prs: list[dict[str, object]]) -> dict[str, object]:
    """Pick most-recent open PR, or most-recent overall."""
    open_prs = [p for p in prs if p.get("state") == "open"]
    if open_prs:
        return max(open_prs, key=lambda p: str(p.get("updated_at", "")))
    return max(prs, key=lambda p: str(p.get("updated_at", "")))


def _derive_review_state(
    reviews: list[dict[str, object]],
) -> tuple[str, str | None]:
    if not reviews:
        return "none", None

    latest_by_user: dict[str, dict[str, object]] = {}
    for review in reviews:
        user_obj = review.get("user")
        user = str(user_obj.get("login", "")) if isinstance(user_obj, dict) else ""
        if user:
            existing = latest_by_user.get(user)
            if existing is None or str(review.get("submitted_at", "")) > str(
                existing.get("submitted_at", "")
            ):
                latest_by_user[user] = review

    states = {str(r.get("state", "")) for r in latest_by_user.values()}
    last_ts = max(
        (str(r.get("submitted_at", "")) for r in latest_by_user.values()),
        default=None,
    )

    if "CHANGES_REQUESTED" in states:
        return "changes-requested", last_ts
    if "APPROVED" in states:
        return "approved", last_ts
    if states - {"COMMENTED", "DISMISSED", ""}:
        return "review-requested", last_ts
    return "none", last_ts


def resolve_pr_identity(
    item: WorkItem,
    repo: str,
    *,
    no_network: bool = False,
) -> PrIdentityResult:
    """5-step PR identity fallback per spec §6.3."""
    warnings: list[str] = []
    try:
        # Step 1: search by linear_id
        if item.linear_id:
            prs = _gh_search_prs(repo, item.linear_id, no_network=no_network)
            if prs:
                if len(prs) > 1:
                    warnings.append("ambiguous_pr_mapping")
                pr = _pick_best_pr(prs)
                return _build_identity(pr, warnings)

        # Step 2: search by branch name
        for branch in item.branches:
            prs = _gh_list_prs_by_head(repo, branch, no_network=no_network)
            if prs:
                if len(prs) > 1:
                    warnings.append("ambiguous_pr_mapping")
                pr = _pick_best_pr(prs)
                return _build_identity(pr, warnings)

        # Step 3: search by feature_id
        if item.feature_id:
            prs = _gh_search_prs(repo, item.feature_id, no_network=no_network)
            if prs:
                if len(prs) > 1:
                    warnings.append("ambiguous_pr_mapping")
                pr = _pick_best_pr(prs)
                return _build_identity(pr, warnings)

        # Step 5: fallback — no PR found
        return {
            "pr_number": None,
            "pr_state": "none",
            "pr_url": None,
            "head_sha": None,
            "warnings": warnings,
        }
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        logger.warning("GitHub PR identity resolution failed: %s", exc)
        warnings.append("github_unknown")
        return {
            "pr_number": None,
            "pr_state": "unknown",
            "pr_url": None,
            "head_sha": None,
            "warnings": warnings,
        }


def _build_identity(pr: dict[str, object], warnings: list[str]) -> PrIdentityResult:
    head = pr.get("head", {})
    head_sha = str(head.get("sha", "")) if isinstance(head, dict) else None
    return {
        "pr_number": int(str(pr.get("number", 0))),
        "pr_state": _derive_pr_state(pr),
        "pr_url": str(pr.get("html_url", "")) or None,
        "head_sha": head_sha or None,
        "warnings": warnings,
    }


def collect_github_signals(
    item: WorkItem,
    repo: str,
    *,
    no_network: bool = False,
) -> GithubSignals:
    """Collect GitHub PR + review signals. Unknown-safe on network failure."""
    try:
        identity = resolve_pr_identity(item, repo, no_network=no_network)
    except Exception as exc:
        logger.warning("GitHub signals collection failed: %s", exc)
        return {
            "pr_state": "unknown",
            "pr_number": None,
            "pr_url": None,
            "review_state": "none",
            "last_review_at": None,
            "warnings": ["github_unknown"],
        }

    pr_number = identity["pr_number"]
    pr_state = identity["pr_state"]
    warnings = list(identity["warnings"])

    if pr_number is None or pr_state in ("none", "unknown", "merged", "closed"):
        return {
            "pr_state": pr_state,
            "pr_number": pr_number,
            "pr_url": identity["pr_url"],
            "review_state": "none",
            "last_review_at": None,
            "warnings": warnings,
        }

    try:
        reviews = _gh_get_reviews(repo, pr_number, no_network=no_network)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        logger.warning("Failed to fetch reviews for PR #%d: %s", pr_number, exc)
        reviews = []

    review_state, last_review_at = _derive_review_state(reviews)

    return {
        "pr_state": pr_state,
        "pr_number": pr_number,
        "pr_url": identity["pr_url"],
        "review_state": review_state,
        "last_review_at": last_review_at,
        "warnings": warnings,
    }
