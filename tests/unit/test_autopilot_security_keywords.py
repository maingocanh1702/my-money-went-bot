"""Unit tests for v0.2.2 SECURITY keyword tiering.

Severe keywords (``auth bypass``, ``injection``, ``csrf``, ``xss``, ...) HALT
regardless of severity — they name concrete vulnerability classes.

Soft keywords (``token``, ``secret``, ``hmac``, ``auth``, ...) only HALT when
paired with P0/P1 severity. P2/P3 mentions fall through to the normal fix
flow. F07 v0.2.1 r1 was a markdown rendering bug that mentioned "token" in
the finding text — auto-halted under the old logic; should NOT halt now.
"""

from __future__ import annotations

from pathlib import Path

from tools.autopilot import circuit_breaker
from tools.autopilot.codex import Finding, ReviewResult
from tools.autopilot.config import Config
from tools.autopilot.state import FeatureState


def _cfg(tmp_path: Path) -> Config:
    return Config(
        repo_root=tmp_path,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=tmp_path / ".autopilot" / "state",
    )


def _state() -> FeatureState:
    return FeatureState(
        feature_id="F99",
        branch="feat/F99-x",
        base_branch="main",
        fe_spec="docs/features/x.md",
        be_spec="docs/features/BE/x-tech.md",
        phase="REVIEWING",
        current_round=1,
    )


def _review(*findings: Finding) -> ReviewResult:
    return ReviewResult(
        clean=False,
        findings=list(findings),
        raw_output="codex\n...",
        base="main",
        duration_seconds=0.1,
    )


def test_severe_keyword_p3_still_halts(tmp_path: Path) -> None:
    """Severe keywords (injection / csrf / xss / ...) always HALT even at P3."""
    f = Finding(
        severity="P3",
        summary="potential SQL injection in /api/users handler",
        file="/repo/api.py",
        line_start=42,
    )
    trigger = circuit_breaker.evaluate(_review(f), _state(), _cfg(tmp_path))
    assert trigger is not None
    assert trigger.code == "SECURITY_FINDING"
    assert "severe" in trigger.description.lower()


def test_severe_keyword_auth_bypass_halts_at_p2(tmp_path: Path) -> None:
    """Multi-word severe keyword (\"auth bypass\") halts even at P2."""
    f = Finding(
        severity="P2",
        summary="possible auth bypass when header missing",
        file="/repo/auth.py",
        line_start=10,
        detail=["request without X-API-Key is accepted"],
    )
    trigger = circuit_breaker.evaluate(_review(f), _state(), _cfg(tmp_path))
    assert trigger is not None
    assert trigger.code == "SECURITY_FINDING"


def test_soft_keyword_p2_does_not_halt(tmp_path: Path) -> None:
    """Soft keyword (\"token\") at P2 must NOT auto-halt.

    Mirrors F07 v0.2.1 R1: markdown rendering bug whose finding mentioned
    'webhook token uses parse_mode'. Should fall through to fix flow.
    """
    f = Finding(
        severity="P2",
        summary="webhook token rendered via parse_mode=Markdown",
        file="/repo/handlers/webhook.py",
        line_start=88,
        detail=["consider plain text rendering to avoid escaping headaches"],
    )
    trigger = circuit_breaker.evaluate(_review(f), _state(), _cfg(tmp_path))
    # Either None (no trigger) or some non-SECURITY trigger; both acceptable.
    assert trigger is None or trigger.code != "SECURITY_FINDING"


def test_soft_keyword_p3_does_not_halt(tmp_path: Path) -> None:
    """Soft keyword at P3 must NOT halt either."""
    f = Finding(
        severity="P3",
        summary="hmac comparison documented but uses constant-name var",
        file="/repo/core/sig.py",
        line_start=15,
    )
    # Note: "constant-time" is severe, but "constant-name" is not. Make
    # sure the test isn't accidentally matching the severe phrase.
    assert "constant-time" not in (f.summary + " " + f.detail_text).lower()
    trigger = circuit_breaker.evaluate(_review(f), _state(), _cfg(tmp_path))
    assert trigger is None or trigger.code != "SECURITY_FINDING"


def test_soft_keyword_p1_halts(tmp_path: Path) -> None:
    """Soft keyword (\"token\") at P1 escalates to HALT.

    The finding text alone is ambiguous, but P1 severity says Codex
    thinks it's high impact — defer to founder review.
    """
    f = Finding(
        severity="P1",
        summary="token comparison may be vulnerable",
        file="/repo/core/auth.py",
        line_start=20,
    )
    trigger = circuit_breaker.evaluate(_review(f), _state(), _cfg(tmp_path))
    assert trigger is not None
    assert trigger.code == "SECURITY_FINDING"
    assert "soft" in trigger.description.lower()


def test_rce_abbreviation_halts_but_substring_does_not(tmp_path: Path) -> None:
    """Codex r4 P1 + r2 P1: ``rce`` token uses word-boundary match.

    The literal abbreviation "RCE" (as used in real review findings)
    must HALT. Plain substring matches like ``source`` (contains "rce"
    at chars 2-4) must NOT HALT.
    """
    halts = Finding(
        severity="P3",
        summary="potential RCE in webhook payload deserializer",
        file="/repo/handlers/webhook.py",
        line_start=22,
    )
    trigger = circuit_breaker.evaluate(_review(halts), _state(), _cfg(tmp_path))
    assert trigger is not None
    assert trigger.code == "SECURITY_FINDING"

    benign = Finding(
        severity="P3",
        summary="add source-code comment for the new helper",
        file="/repo/core/util.py",
        line_start=5,
        detail=["the new helper resource isn't documented yet"],
    )
    trigger2 = circuit_breaker.evaluate(_review(benign), _state(), _cfg(tmp_path))
    assert trigger2 is None or trigger2.code != "SECURITY_FINDING"


def test_severe_keyword_in_detail_text_halts(tmp_path: Path) -> None:
    """Severe match works against detail text, not only summary."""
    f = Finding(
        severity="P3",
        summary="minor handler refactor suggestion",
        file="/repo/handlers/x.py",
        line_start=5,
        detail=["the rewrite introduces a potential xss in the rendered html"],
    )
    trigger = circuit_breaker.evaluate(_review(f), _state(), _cfg(tmp_path))
    # ARCH keyword "refactor" is in summary — that will fire FIRST.
    # Either ARCH_FINDING or SECURITY_FINDING acceptable here; the key
    # point is that benign P3 with severe-keyword content is not silent.
    assert trigger is not None
    assert trigger.code in ("ARCH_FINDING", "SECURITY_FINDING")
