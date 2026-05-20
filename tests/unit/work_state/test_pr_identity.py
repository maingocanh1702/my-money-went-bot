"""Tests for PR identity resolution per spec §6.3 5-step fallback."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from scripts.work_state.models import WorkItem

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


class TestResolvePrIdentity:
    """Per spec §6.3 5-step fallback chain."""

    def test_step1_linear_id_search(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr_list = json.loads((FIXTURES / "pr_list_search_mym108.json").read_text())
        item = _make_item(linear_id="MYM-108")

        with patch(
            "scripts.work_state.signal_collectors.github._gh_search_prs",
            return_value=pr_list,
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_number"] == 42
        assert result["pr_state"] == "open"
        assert "ambiguous_pr_mapping" not in result["warnings"]

    def test_step2_branch_match(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr_data = json.loads((FIXTURES / "pr_open.json").read_text())
        item = _make_item(linear_id=None, branches=["feat/funding-sources"])

        with (
            patch(
                "scripts.work_state.signal_collectors.github._gh_search_prs",
                return_value=[],
            ),
            patch(
                "scripts.work_state.signal_collectors.github._gh_list_prs_by_head",
                return_value=[pr_data],
            ),
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_number"] == 42

    def test_step3_feature_id_search(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr_data = json.loads((FIXTURES / "pr_open.json").read_text())
        item = _make_item(
            linear_id=None,
            branches=[],
            feature_id="funding-sources",
        )

        with (
            patch(
                "scripts.work_state.signal_collectors.github._gh_search_prs",
                return_value=[pr_data],
            ),
            patch(
                "scripts.work_state.signal_collectors.github._gh_list_prs_by_head",
                return_value=[],
            ),
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_number"] == 42

    def test_no_pr_exists(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        item = _make_item(linear_id=None, branches=["feat/nonexistent"])

        with (
            patch(
                "scripts.work_state.signal_collectors.github._gh_search_prs",
                return_value=[],
            ),
            patch(
                "scripts.work_state.signal_collectors.github._gh_list_prs_by_head",
                return_value=[],
            ),
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_number"] is None
        assert result["pr_state"] == "none"

    def test_multiple_prs_ambiguous(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr1 = json.loads((FIXTURES / "pr_open.json").read_text())
        pr2 = json.loads((FIXTURES / "pr_draft.json").read_text())
        item = _make_item(linear_id="MYM-108")

        with patch(
            "scripts.work_state.signal_collectors.github._gh_search_prs",
            return_value=[pr1, pr2],
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_number"] == 50  # picks most-recent updated open
        assert "ambiguous_pr_mapping" in result["warnings"]

    def test_pr_closed_not_merged(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr_data = json.loads((FIXTURES / "pr_closed_not_merged.json").read_text())
        item = _make_item(linear_id="MYM-999", branches=["feat/MYM-999-abandoned"])

        with patch(
            "scripts.work_state.signal_collectors.github._gh_search_prs",
            return_value=[pr_data],
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_state"] == "closed"
        assert result["pr_number"] == 99

    def test_draft_pr_state(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr_data = json.loads((FIXTURES / "pr_draft.json").read_text())
        item = _make_item(
            linear_id="MYM-105",
            branches=["feat/category-management"],
        )

        with patch(
            "scripts.work_state.signal_collectors.github._gh_search_prs",
            return_value=[pr_data],
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_state"] == "draft"

    def test_merged_pr_state(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        pr_data = json.loads((FIXTURES / "pr_merged.json").read_text())
        item = _make_item(
            linear_id="MYM-101",
            branches=["feat/F01-onboarding-start"],
        )

        with patch(
            "scripts.work_state.signal_collectors.github._gh_search_prs",
            return_value=[pr_data],
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_state"] == "merged"
        assert result["pr_number"] == 10

    def test_network_failure_returns_unknown(self) -> None:
        from scripts.work_state.signal_collectors.github import resolve_pr_identity

        item = _make_item(linear_id="MYM-108")

        with patch(
            "scripts.work_state.signal_collectors.github._gh_search_prs",
            side_effect=OSError("network down"),
        ):
            result = resolve_pr_identity(item, repo="maingocanh1702/MyMoneyWent")
        assert result["pr_state"] == "unknown"
        assert "github_unknown" in result["warnings"]
