"""Tests for foundation_change milestone signal detection (AC11c).

Covers: codex-approved label + founder sign-off comment marker detection
in signal_collectors/github.py.
"""

from __future__ import annotations

from work_state.models import Signals
from work_state.signal_collectors.github import (
    _detect_foundation_change_signals,
)


def _make_pr(
    *,
    labels: list[dict[str, str]] | None = None,
    state: str = "open",
    merged_at: str | None = None,
) -> dict[str, object]:
    pr: dict[str, object] = {"state": state}
    if labels is not None:
        pr["labels"] = labels
    if merged_at is not None:
        pr["merged_at"] = merged_at
    return pr


def _make_comment(author: str, body: str) -> dict[str, object]:
    return {"user": {"login": author}, "body": body}


class TestDetectFoundationChangeSignals:
    def test_both_present(self) -> None:
        pr = _make_pr(labels=[{"name": "codex-approved"}])
        comments = [_make_comment("maingocanh", "founder sign-off")]
        codex, signoff = _detect_foundation_change_signals(pr, comments, "maingocanh")
        assert codex is True
        assert signoff is True

    def test_codex_label_only(self) -> None:
        pr = _make_pr(labels=[{"name": "codex-approved"}])
        codex, signoff = _detect_foundation_change_signals(pr, [], "maingocanh")
        assert codex is True
        assert signoff is False

    def test_founder_signoff_only(self) -> None:
        pr = _make_pr(labels=[])
        comments = [_make_comment("maingocanh", "✅ ship")]
        codex, signoff = _detect_foundation_change_signals(pr, comments, "maingocanh")
        assert codex is False
        assert signoff is True

    def test_neither_present(self) -> None:
        pr = _make_pr(labels=[{"name": "bug"}])
        comments = [_make_comment("maingocanh", "looks good")]
        codex, signoff = _detect_foundation_change_signals(pr, comments, "maingocanh")
        assert codex is False
        assert signoff is False

    def test_non_founder_comment_does_not_count(self) -> None:
        pr = _make_pr(labels=[])
        comments = [_make_comment("someone_else", "founder sign-off")]
        codex, signoff = _detect_foundation_change_signals(pr, comments, "maingocanh")
        assert codex is False
        assert signoff is False

    def test_pr_none_returns_none(self) -> None:
        codex, signoff = _detect_foundation_change_signals(None, [], "maingocanh")
        assert codex is None
        assert signoff is None

    def test_pr_unknown_state_returns_none(self) -> None:
        pr: dict[str, object] = {"state": "something_weird"}
        codex, signoff = _detect_foundation_change_signals(pr, [], "maingocanh")
        assert codex is None
        assert signoff is None

    def test_case_insensitive_label(self) -> None:
        pr = _make_pr(labels=[{"name": "Codex-Approved"}])
        codex, signoff = _detect_foundation_change_signals(pr, [], "maingocanh")
        assert codex is True
        assert signoff is False

    def test_founder_signoff_text_variant(self) -> None:
        pr = _make_pr(labels=[])
        comments = [_make_comment("maingocanh", "This has Founder Sign-Off confirmed")]
        codex, signoff = _detect_foundation_change_signals(pr, comments, "maingocanh")
        assert codex is False
        assert signoff is True

    def test_case_insensitive_founder_login(self) -> None:
        pr = _make_pr(labels=[])
        comments = [_make_comment("MainGoCaNh", "founder sign-off")]
        codex, signoff = _detect_foundation_change_signals(pr, comments, "maingocanh")
        assert codex is False
        assert signoff is True


class TestSignalsNewFields:
    def test_default_values(self) -> None:
        s = Signals(
            spec_exists=False,
            tech_exists=False,
            branch_exists=False,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="unknown",
            deploy_state="unknown",
        )
        assert s.foundation_codex_approved is None
        assert s.foundation_founder_signoff is None

    def test_explicit_values(self) -> None:
        s = Signals(
            spec_exists=False,
            tech_exists=False,
            branch_exists=False,
            commits_count=0,
            last_commit_sha=None,
            pr_state="none",
            pr_number=None,
            review_state="none",
            ci_state="unknown",
            deploy_state="unknown",
            foundation_codex_approved=True,
            foundation_founder_signoff=False,
        )
        assert s.foundation_codex_approved is True
        assert s.foundation_founder_signoff is False
