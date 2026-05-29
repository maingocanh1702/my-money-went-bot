"""Progress profiles — milestone-weighted % per spec §9.1."""

from __future__ import annotations

from work_state.models import Signals


def _standard_feature_progress(s: Signals) -> int:
    if s.deploy_state == "deployed":
        return 100
    if s.pr_state == "merged":
        return 95
    if s.review_state == "approved":
        return 85
    if s.ci_state == "pass":
        return 75
    if s.pr_state in ("open", "draft"):
        return 60
    if s.commits_count > 0:
        return 45
    if s.branch_exists:
        return 30
    if s.tech_exists:
        return 20
    if s.spec_exists:
        return 10
    return 0


def compute_progress(signals: Signals, profile: str) -> int:
    if profile == "standard_feature":
        return _standard_feature_progress(signals)
    raise NotImplementedError(f"Progress profile '{profile}' not implemented in Phase 1a")
