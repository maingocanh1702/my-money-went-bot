"""Tests for scripts/build-dashboard.py — parser + git-state + reconcile."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bd():
    """Load build-dashboard.py as a module (script has hyphen, so importlib)."""
    spec = importlib.util.spec_from_file_location(
        "build_dashboard", ROOT / "scripts" / "build-dashboard.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_dashboard"] = module  # register before exec so @dataclass resolves
    spec.loader.exec_module(module)
    return module


# ─── Parser tests ────────────────────────────────────────────────────────────

def test_parse_phase_block_extracts_status_emoji(bd):
    text = """### Phase 1: Foundation
| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| W0.7 | Wave 0 | request_id | ✅ | `chore/W0.7` | 🔒X | done |
| W1.1 | Wave 0 | Docker | ⬜ | `infra/W1.1` | 🔒X | next |
"""
    prs = bd.parse_prs(text)
    assert len(prs) == 2
    assert prs[0].pr_id == "W0.7" and prs[0].status_slug == "merged"
    assert prs[1].pr_id == "W1.1" and prs[1].status_slug == "not-started"


def test_parse_handles_in_review_and_blocked_emojis(bd):
    text = """### Phase 2: Handlers
| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| F07 | W1 | Settings | 🟠 | `feat/F07-settings` | 🔒T 🔒X | review |
| F-i18n | W1 | i18n | ❌ | `feat/F-i18n` | 🔒X | blocked |
"""
    prs = bd.parse_prs(text)
    statuses = {p.pr_id: p.status_slug for p in prs}
    assert statuses == {"F07": "in-review", "F-i18n": "blocked"}


# ─── detect_local_state / detect_remote_state / detect_sync ──────────────────

def _make_git_stub(refs_present: set[str], counts: dict[tuple[str, str], int],
                   fix_present: set[tuple[str, str]] | None = None):
    """Build a fake _git callable. refs_present = set of refs that 'exist'.
    counts maps (base, ref) → int. fix_present = same key, marks fix() commits found.
    """
    fix_present = fix_present or set()
    def fake_git(*args):
        if "rev-parse" in args and "--verify" in args:
            ref = args[-1]
            return (0 if ref in refs_present else 1, "abc" if ref in refs_present else "")
        if "rev-list" in args and "--count" in args:
            spec = args[-1]  # "base..ref"
            base, _, ref = spec.partition("..")
            n = counts.get((base, ref), 0)
            return (0, str(n))
        if "log" in args and any(a.startswith("--grep=^fix") for a in args):
            spec = args[-1]
            base, _, ref = spec.partition("..")
            return (0, "abc fix(...): foo" if (base, ref) in fix_present else "")
        return (1, "")
    return fake_git


def test_detect_local_state_no_branch_returns_none(bd):
    with patch.object(bd, "_git", side_effect=_make_git_stub(set(), {})):
        assert bd.detect_local_state("feat/missing", "F99") == (None, "")


def test_detect_local_state_branch_with_commits_in_progress(bd):
    stub = _make_git_stub(
        refs_present={"feat/F99", "main"},
        counts={("main", "feat/F99"): 2},
    )
    with patch.object(bd, "_git", side_effect=stub):
        slug, reason = bd.detect_local_state("feat/F99", "F99")
        assert slug == "in-progress"
        assert "2 commits" in reason


def test_detect_local_state_branch_with_fix_in_review(bd):
    stub = _make_git_stub(
        refs_present={"feat/F07", "main"},
        counts={("main", "feat/F07"): 5},
        fix_present={("main", "feat/F07")},
    )
    with patch.object(bd, "_git", side_effect=stub):
        slug, _ = bd.detect_local_state("feat/F07", "F07")
        assert slug == "in-review"


def test_detect_remote_state_uses_origin_branch_and_origin_main(bd):
    """Remote detection compares origin/<branch> to origin/main, not main."""
    stub = _make_git_stub(
        refs_present={"origin/feat/F99", "origin/main"},
        counts={("origin/main", "origin/feat/F99"): 3},
    )
    with patch.object(bd, "_git", side_effect=stub):
        slug, reason = bd.detect_remote_state("feat/F99", "F99")
        assert slug == "in-progress"


def test_detect_remote_state_returns_none_if_not_pushed(bd):
    """Branch only local, never pushed → remote state is (None, '')."""
    stub = _make_git_stub(refs_present={"feat/F99", "main"}, counts={})
    with patch.object(bd, "_git", side_effect=stub):
        assert bd.detect_remote_state("feat/F99", "F99") == (None, "")


def test_detect_sync_local_only_branch_all_unpushed(bd):
    """Branch exists locally but not on origin → all commits unpushed."""
    stub = _make_git_stub(
        refs_present={"feat/F99", "main"},
        counts={("main", "feat/F99"): 5},
    )
    with patch.object(bd, "_git", side_effect=stub):
        unpushed, unpulled = bd.detect_sync("feat/F99")
        assert (unpushed, unpulled) == (5, 0)


def test_detect_sync_remote_only_branch_all_unpulled(bd):
    """Branch on origin but never checked out locally → all commits unpulled."""
    stub = _make_git_stub(
        refs_present={"origin/feat/F99", "origin/main"},
        counts={("origin/main", "origin/feat/F99"): 3},
    )
    with patch.object(bd, "_git", side_effect=stub):
        unpushed, unpulled = bd.detect_sync("feat/F99")
        assert (unpushed, unpulled) == (0, 3)


def test_detect_sync_both_exist_diverged(bd):
    """Both refs exist; sync counts commits diverged either way."""
    stub = _make_git_stub(
        refs_present={"feat/F07", "origin/feat/F07", "main", "origin/main"},
        counts={
            ("origin/feat/F07", "feat/F07"): 2,  # unpushed
            ("feat/F07", "origin/feat/F07"): 1,  # unpulled
        },
    )
    with patch.object(bd, "_git", side_effect=stub):
        unpushed, unpulled = bd.detect_sync("feat/F07")
        assert (unpushed, unpulled) == (2, 1)


def test_detect_sync_empty_branch(bd):
    assert bd.detect_sync("") == (0, 0)


# ─── Combined detect_git_state still works (back-compat) ─────────────────────

def test_detect_git_state_picks_higher_local_or_remote(bd):
    """Combined detect_git_state returns max of local/remote rank."""
    stub = _make_git_stub(
        refs_present={"feat/F07", "origin/feat/F07", "main", "origin/main"},
        counts={
            ("main", "feat/F07"): 5,
            ("origin/main", "origin/feat/F07"): 2,
        },
        fix_present={("main", "feat/F07")},  # local has fix() → in-review
    )
    with patch.object(bd, "_git", side_effect=stub):
        slug, reason = bd.detect_git_state("feat/F07", "F07")
        # Local in-review beats remote in-progress
        assert slug == "in-review"
        assert "local:" in reason


def test_detect_git_state_empty_branch_returns_none(bd):
    assert bd.detect_git_state("", "F99") == (None, "")


# ─── reconcile_status tests ──────────────────────────────────────────────────

@pytest.mark.parametrize("terminal", ["merged", "deferred", "blocked", "ready"])
def test_reconcile_terminal_tracker_states_always_win(bd, terminal):
    """Terminal tracker states never overridden by git inference."""
    for git_slug in ["in-progress", "in-review", "not-started", "merged", None]:
        assert bd.reconcile_status(terminal, git_slug) == terminal, (
            f"{terminal} must not be overridden by git={git_slug}"
        )


def test_reconcile_git_wins_when_tracker_is_unstarted(bd):
    """⬜ Not started + git shows commits → use git's slug (reality wins)."""
    assert bd.reconcile_status("not-started", "in-progress") == "in-progress"
    assert bd.reconcile_status("not-started", "in-review") == "in-review"


def test_reconcile_tracker_wins_when_more_specific(bd):
    """🟠 In review (founder-set) NOT downgraded by git's heuristic in-progress."""
    assert bd.reconcile_status("in-review", "in-progress") == "in-review"


def test_reconcile_none_git_keeps_tracker(bd):
    """If git can't determine state → keep tracker untouched."""
    for tracker in ["not-started", "in-progress", "in-review", "merged"]:
        assert bd.reconcile_status(tracker, None) == tracker


def test_reconcile_unknown_merged_does_not_demote_not_started(bd):
    """Git false-positive 'merged' on ⬜ tracker → stays ⬜ (rank 0 == rank 0)."""
    # `merged` is not in _GIT_RANK so falls back to 0; tracker `not-started` is also 0.
    # Tie → tracker wins per implementation.
    assert bd.reconcile_status("not-started", "merged") == "not-started"


# ─── enrich_with_git_state integration ───────────────────────────────────────

def test_enrich_with_git_state_no_drift_when_synced(bd):
    """If git-state matches tracker, no drift rows produced."""
    pr = bd.PR(
        pr_id="F07", wave="W1", feature="Settings",
        status_emoji="🟠", status_label="In review", status_slug="in-review",
        branch="feat/F07", gates="🔒X", notes="", phase="Phase 2",
    )
    with patch.object(bd, "detect_local_state", return_value=("in-review", "5 commits")), \
         patch.object(bd, "detect_remote_state", return_value=("in-review", "5 commits")), \
         patch.object(bd, "detect_sync", return_value=(0, 0)):
        drift = bd.enrich_with_git_state([pr])
    assert drift == []
    assert pr.status_slug == "in-review"
    assert pr.local_slug == "in-review"
    assert pr.remote_slug == "in-review"


def test_enrich_with_git_state_records_drift_on_upgrade(bd):
    """Tracker ⬜ + git shows in-progress → status upgraded + drift recorded."""
    pr = bd.PR(
        pr_id="F99", wave="W1", feature="New feature",
        status_emoji="⬜", status_label="Not started", status_slug="not-started",
        branch="feat/F99", gates="🔒X", notes="", phase="Phase 2",
    )
    with patch.object(bd, "detect_local_state", return_value=("in-progress", "3 commits")), \
         patch.object(bd, "detect_remote_state", return_value=(None, "")), \
         patch.object(bd, "detect_sync", return_value=(3, 0)):
        drift = bd.enrich_with_git_state([pr])
    assert len(drift) == 1
    pr_id, old, new, reason = drift[0]
    assert (pr_id, old, new) == ("F99", "not-started", "in-progress")
    assert "local:" in reason
    assert pr.status_slug == "in-progress"
    assert pr.status_label == "In progress"
    assert pr.status_emoji == "⬜"  # tracker emoji untouched
    assert pr.unpushed == 3
    assert pr.unpulled == 0


def test_enrich_populates_split_slugs_when_local_and_remote_diverge(bd):
    """Local and remote can have different inferences (e.g., local has fix() commits,
    remote doesn't because they haven't been pushed yet)."""
    pr = bd.PR(
        pr_id="F88", wave="W1", feature="Diverged",
        status_emoji="⬜", status_label="Not started", status_slug="not-started",
        branch="feat/F88", gates="🔒X", notes="", phase="Phase 2",
    )
    with patch.object(bd, "detect_local_state", return_value=("in-review", "5 commits + fix")), \
         patch.object(bd, "detect_remote_state", return_value=("in-progress", "2 commits")), \
         patch.object(bd, "detect_sync", return_value=(3, 0)):
        bd.enrich_with_git_state([pr])
    assert pr.local_slug == "in-review"
    assert pr.remote_slug == "in-progress"
    assert pr.status_slug == "in-review"   # higher rank wins for primary
    assert pr.unpushed == 3
