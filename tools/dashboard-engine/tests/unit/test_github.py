"""Tests for GitHub signal collector per spec §6.3 + §6.4 + §6.5."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from work_state.models import WorkItem

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "github"


def _make_item(**overrides: object) -> WorkItem:
    defaults: dict[str, object] = {
        "id": "funding-sources",
        "linear_id": "MYM-108",
        "feature_id": "funding-sources",
        "title": "Funding sources",
        "type": "feature",
        "phase": "2",
        "priority": "P1",
        "risk_tier": "P1",
        "lane": "Standard",
        "owner": "founder",
        "deadline": None,
        "specs": {"product": None, "tech": None},
        "branches": ["feat/funding-sources"],
        "acceptance": [],
        "dependencies": [],
        "external_blockers": [],
        "decision_needed": None,
        "progress_profile": "standard_feature",
    }
    defaults.update(overrides)
    return WorkItem(**defaults)  # type: ignore[arg-type]


class TestCollectGithubSignals:
    def test_open_pr_with_review_approved(self) -> None:
        from work_state.signal_collectors.github import collect_github_signals

        pr_data = json.loads((FIXTURES / "pr_open.json").read_text())
        reviews = json.loads((FIXTURES / "reviews_approved.json").read_text())
        item = _make_item()

        with (
            patch(
                "work_state.signal_collectors.github.resolve_pr_identity",
                return_value={
                    "pr_number": 42,
                    "pr_state": "open",
                    "pr_url": pr_data["html_url"],
                    "head_sha": "abc123",
                    "warnings": [],
                },
            ),
            patch(
                "work_state.signal_collectors.github._gh_get_reviews",
                return_value=reviews,
            ),
        ):
            result = collect_github_signals(item, repo="maingocanh1702/MyMoneyWent")

        assert result["pr_state"] == "open"
        assert result["pr_number"] == 42
        assert result["pr_url"] == pr_data["html_url"]
        assert result["review_state"] == "approved"
        assert result["last_review_at"] == "2026-05-19T12:00:00Z"

    def test_open_pr_with_changes_requested(self) -> None:
        from work_state.signal_collectors.github import collect_github_signals

        reviews = json.loads((FIXTURES / "reviews_changes_requested.json").read_text())
        item = _make_item()

        with (
            patch(
                "work_state.signal_collectors.github.resolve_pr_identity",
                return_value={
                    "pr_number": 42,
                    "pr_state": "open",
                    "pr_url": "https://github.com/org/repo/pull/42",
                    "head_sha": "abc123",
                    "warnings": [],
                },
            ),
            patch(
                "work_state.signal_collectors.github._gh_get_reviews",
                return_value=reviews,
            ),
        ):
            result = collect_github_signals(item, repo="maingocanh1702/MyMoneyWent")

        assert result["review_state"] == "changes-requested"

    def test_no_reviews(self) -> None:
        from work_state.signal_collectors.github import collect_github_signals

        item = _make_item()

        with (
            patch(
                "work_state.signal_collectors.github.resolve_pr_identity",
                return_value={
                    "pr_number": 42,
                    "pr_state": "open",
                    "pr_url": "https://github.com/org/repo/pull/42",
                    "head_sha": "abc123",
                    "warnings": [],
                },
            ),
            patch(
                "work_state.signal_collectors.github._gh_get_reviews",
                return_value=[],
            ),
        ):
            result = collect_github_signals(item, repo="maingocanh1702/MyMoneyWent")

        assert result["review_state"] == "none"
        assert result["last_review_at"] is None

    def test_no_pr_found(self) -> None:
        from work_state.signal_collectors.github import collect_github_signals

        item = _make_item(linear_id=None, branches=["feat/nonexistent"])

        with patch(
            "work_state.signal_collectors.github.resolve_pr_identity",
            return_value={
                "pr_number": None,
                "pr_state": "none",
                "pr_url": None,
                "head_sha": None,
                "warnings": [],
            },
        ):
            result = collect_github_signals(item, repo="maingocanh1702/MyMoneyWent")

        assert result["pr_state"] == "none"
        assert result["pr_number"] is None
        assert result["review_state"] == "none"

    def test_merged_pr_skips_review_fetch(self) -> None:
        from work_state.signal_collectors.github import collect_github_signals

        item = _make_item()

        with patch(
            "work_state.signal_collectors.github.resolve_pr_identity",
            return_value={
                "pr_number": 10,
                "pr_state": "merged",
                "pr_url": "https://github.com/org/repo/pull/10",
                "head_sha": "9f07c57aaa",
                "warnings": [],
            },
        ):
            result = collect_github_signals(item, repo="maingocanh1702/MyMoneyWent")

        assert result["pr_state"] == "merged"
        assert result["review_state"] == "none"

    def test_network_failure_unknown_safe(self) -> None:
        from work_state.signal_collectors.github import collect_github_signals

        item = _make_item()

        with patch(
            "work_state.signal_collectors.github.resolve_pr_identity",
            side_effect=OSError("network down"),
        ):
            result = collect_github_signals(item, repo="maingocanh1702/MyMoneyWent")

        assert result["pr_state"] == "unknown"
        assert "github_unknown" in result["warnings"]
