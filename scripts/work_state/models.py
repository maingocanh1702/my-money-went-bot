"""Canonical dataclass models per spec §11.2.

Overlay names: kebab-case (UI-visible).
Warning codes: snake_case (machine detail).
Per spec §8.2.1 naming convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ManualOverride:
    status: str
    reason: str
    until: str  # ISO date


@dataclass(frozen=True)
class WorkItem:
    id: str
    linear_id: str | None
    feature_id: str
    title: str
    type: str
    phase: str
    priority: str
    risk_tier: str
    lane: str
    owner: str
    deadline: str | None
    specs: dict[str, str | None]
    branches: list[str]
    acceptance: list[str]
    dependencies: list[str]
    external_blockers: list[str]
    decision_needed: str | None
    progress_profile: str
    manual_state_override: ManualOverride | None = None


@dataclass
class Signals:
    spec_exists: bool
    tech_exists: bool
    branch_exists: bool
    commits_count: int
    last_commit_sha: str | None
    pr_state: str
    pr_number: int | None
    review_state: str
    ci_state: str
    deploy_state: str
    warnings: list[str] = field(default_factory=list)
    # Phase 1b APPEND-ONLY extensions
    pr_url: str | None = None
    ci_check_run_count: int = 0
    last_review_at: str | None = None
    last_deploy_at: str | None = None
    # Phase B APPEND-ONLY extensions (doc-change awareness)
    spec_hash: str | None = None
    spec_modified_at: str | None = None
    tech_hash: str | None = None
    tech_modified_at: str | None = None
    tracker_row_hash: str | None = None
    # Phase 1d APPEND-ONLY extensions (foundation_change milestone signals)
    foundation_codex_approved: bool | None = None
    foundation_founder_signoff: bool | None = None


@dataclass
class CurrentState:
    item_id: str
    status: str
    human_status: str
    progress: int
    runtime_urgency: str
    overlays: list[str]
    signals: Signals
    last_event_ts: str | None


@dataclass(frozen=True)
class Event:
    ts: str
    item: str
    event: str
    from_status: str | None
    to_status: str | None
    source: str
    artifact: str | None = None
    pr_number: int | None = None
    overlay: str | None = None
    # Phase B / MYM-8 APPEND-ONLY — doc-change events carry artifact content hash for hash-aware dedup
    content_hash: str | None = None
