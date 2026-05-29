"""Status state machine per spec §8.1, §8.0, §4.1, §9.4."""

from __future__ import annotations

from work_state.models import Signals

URGENCY_ORDER: dict[str, int] = {
    "normal": 0,
    "warning": 1,
    "elevated": 2,
    "critical": 3,
}

STATUS_RANK: dict[str, int] = {
    "not-started": 0,
    "spec-only": 1,
    "tech-ready": 2,
    "branch-created": 3,
    "in-progress": 4,
    "in-review": 5,
    "changes-requested": 6,
    "approved-pending-merge": 7,
    "merged": 8,
    "deploying": 9,
    "deployed": 10,
}

TERMINAL_STATUSES = {"deployed", "merged", "abandoned"}

CANONICAL_OVERLAYS: frozenset[str] = frozenset(
    {
        "blocked",
        "ci-failing",
        "deploy-failed",
        "unknown",
        "artifact-drift",
        "ambiguous-pr-mapping",
        "review-requested",
        "stale",
        "partial-progress",
        "multi-branch",
        "manual-override",
        "ci-running",
        "deploy-in-progress",
        "no-ci",
        "spec-modified",
        "tech-modified",
        "tracker-modified",
        "post-ship-doc-change",
        "stale-cache",
        "cache-warmup",
        "risk-tier-inferred",
    }
)


def compute_overlays(
    signals: Signals,
    base_status: str,
    *,
    prev_spec_hash: str | None = None,
    prev_tech_hash: str | None = None,
    prev_tracker_row_hash: str | None = None,
) -> list[str]:
    """Compute doc-change overlays per spec §8.2 Phase B rules."""
    overlays: list[str] = []

    spec_changed = (
        prev_spec_hash is not None
        and signals.spec_hash is not None
        and signals.spec_hash != prev_spec_hash
    )
    tech_changed = (
        prev_tech_hash is not None
        and signals.tech_hash is not None
        and signals.tech_hash != prev_tech_hash
    )
    tracker_changed = (
        prev_tracker_row_hash is not None
        and signals.tracker_row_hash is not None
        and signals.tracker_row_hash != prev_tracker_row_hash
    )

    if spec_changed:
        overlays.append("spec-modified")
    if tech_changed:
        overlays.append("tech-modified")
    if tracker_changed:
        overlays.append("tracker-modified")

    any_doc_change = spec_changed or tech_changed or tracker_changed
    if any_doc_change and base_status in TERMINAL_STATUSES:
        overlays.append("post-ship-doc-change")

    return sorted(overlays)


def compute_status(s: Signals) -> str:
    """First-match priority per spec §8.1."""
    if s.deploy_state == "deployed":
        return "deployed"
    if s.deploy_state == "deploying":
        return "deploying"
    if s.pr_state == "merged":
        return "merged"
    if s.pr_state == "closed":
        return "abandoned"

    if s.pr_state == "open":
        if s.review_state == "changes-requested":
            return "changes-requested"
        if s.review_state == "approved":
            return "approved-pending-merge"
        return "in-review"

    if s.pr_state == "draft":
        return "in-progress"

    if s.branch_exists and s.commits_count > 0:
        return "in-progress"

    if s.branch_exists:
        return "branch-created"

    if s.tech_exists:
        return "tech-ready"

    if s.spec_exists:
        return "spec-only"

    return "not-started"


def compute_human_status(
    base_status: str,
    overlays: list[str],
    deploy_state: str,
) -> str:
    """Human status projection per spec §8.0. Resolution precedence (first match)."""
    overlay_set = set(overlays)

    if "blocked" in overlay_set:
        return "BLOCKED"

    if "ci-failing" in overlay_set or "deploy-failed" in overlay_set:
        return "FAILING"

    if overlay_set & {"unknown", "artifact-drift", "ambiguous-pr-mapping"}:
        return "UNKNOWN"

    if "review-requested" in overlay_set or "stale" in overlay_set:
        return "WAITING"

    if base_status == "deploying":
        return "WAITING"

    if base_status == "merged":
        if deploy_state == "not-applicable":
            return "DONE"
        return "WAITING"

    if base_status == "deployed":
        return "DONE"

    if base_status == "abandoned":
        return "ABANDONED"

    if base_status == "not-started":
        return "BACKLOG"

    if base_status in {"spec-only", "tech-ready"}:
        return "TODO"

    if base_status in {
        "branch-created",
        "in-progress",
        "in-review",
        "changes-requested",
        "approved-pending-merge",
    }:
        return "IN_PROGRESS"

    return "UNKNOWN"


def aggregate_multi_branch_status(statuses: list[str]) -> str:
    """MIN-progressed non-abandoned status per spec §4.1.1."""
    non_abandoned = [s for s in statuses if s != "abandoned"]
    if not non_abandoned:
        return "abandoned"
    return min(non_abandoned, key=lambda s: STATUS_RANK.get(s, 999))


def aggregate_multi_branch_overlays(
    branch_data: list[tuple[str, list[str]]],
) -> list[str]:
    """Union overlays + partial-progress detection per spec §4.1.2."""
    all_overlays: set[str] = set()
    for _status, overlays in branch_data:
        all_overlays.update(overlays)

    statuses = [status for status, _ in branch_data]
    terminal = {s for s in statuses if s in TERMINAL_STATUSES}
    non_terminal = {s for s in statuses if s not in TERMINAL_STATUSES}

    needs_partial = (
        len(terminal) > 0
        and (len(non_terminal) > 0 or len(terminal) > 1)
        and not all(s == statuses[0] for s in statuses)
    )
    if needs_partial:
        all_overlays.add("partial-progress")

    return sorted(all_overlays)


def derive_urgency(
    base: str,
    overlays: list[str] | frozenset[str],
    priority: str,
    risk_tier: str,
) -> str:
    """Derive runtime_urgency per spec §9.4.1 — first-match-wins."""
    overlay_set = frozenset(overlays) if not isinstance(overlays, frozenset) else overlays

    if "deploy-failed" in overlay_set:
        return "critical"
    if base == "deployed" and "unknown" in overlay_set:
        if risk_tier in {"P0", "P1"}:
            return "critical"
    if "ci-failing" in overlay_set and base == "merged":
        return "critical"

    if "blocked" in overlay_set and priority in {"P0", "P1"}:
        return "elevated"
    if "ci-failing" in overlay_set:
        return "elevated"
    if base == "approved-pending-merge" and "stale" in overlay_set:
        return "elevated"
    if "ambiguous-pr-mapping" in overlay_set:
        return "elevated"

    if "blocked" in overlay_set:
        return "warning"
    if "stale" in overlay_set:
        return "warning"
    if "unknown" in overlay_set:
        return "warning"
    if "artifact-drift" in overlay_set:
        return "warning"
    if "cache-warmup" in overlay_set:
        return "warning"

    return "normal"


def aggregate_multi_branch_urgency(urgencies: list[str]) -> str:
    """MAX urgency per spec §9.4.2 — critical > elevated > warning > normal."""
    if not urgencies:
        return "normal"
    return max(urgencies, key=lambda u: URGENCY_ORDER.get(u, 0))
