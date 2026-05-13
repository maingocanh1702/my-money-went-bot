"""v0.2.3 keyword word-boundary regression suite.

All 4 keyword categories now ship as compiled regex with `\\b` boundaries.
This file guards the substring-match hazards that the legacy
tuple-of-strings layout exposed — most prominently the F07 phase B halt
where ``"lock"`` matched inside ``"block"`` / ``"guarded block"``.

Coverage: 1 positive + 1 negative case per category (minimum), plus
extras for the special compound-`lock` pattern and the
back-compat SECURITY_KEYWORDS alias used by callers of
``Finding.matches_keywords``.
"""

from __future__ import annotations

import re

from tools.autopilot.codex import (
    ARCH_KEYWORDS,
    CONCURRENCY_KEYWORDS,
    SECURITY_KEYWORDS,
    SECURITY_KEYWORDS_SOFT,
    Finding,
    has_severe_security_match,
)


def _f(summary: str, detail: list[str] | None = None, severity: str = "P2") -> Finding:
    return Finding(severity=severity, summary=summary, detail=detail or [])


# --- CONCURRENCY_KEYWORDS — compound `lock` pattern -------------------------


def test_concurrency_lock_does_not_match_block() -> None:
    """v0.2.3 r1 P1: ``"lock"`` substring inside ``"block"`` must NOT trigger
    CONCURRENCY_FINDING. Caught by F07 phase B halt 2026-05-13 — Codex
    finding "Move serialization inside the guarded block" tripped the
    legacy substring matcher.
    """
    f = _f(
        "Move serialization inside the guarded block",
        ["text with 'blocking' and 'blocker' words"],
    )
    assert not f.matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_lock_matches_deadlock() -> None:
    """Deadlock IS a concurrency concern."""
    assert _f("Potential deadlock between mutexes").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_lock_matches_livelock() -> None:
    """Livelock variant covered by the compound pattern."""
    assert _f("scheduler shows livelock under contention").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_lock_matches_standalone() -> None:
    """Plain ``"lock contention"`` is a concurrency concern."""
    assert _f("lock contention on shared cache").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_lock_matches_morphology() -> None:
    """``"locking"`` / ``"locked"`` / ``"locks"`` all match."""
    assert _f("locking the row before update").matches_keywords(CONCURRENCY_KEYWORDS)
    assert _f("once locked, the resource is freed").matches_keywords(CONCURRENCY_KEYWORDS)
    assert _f("the worker locks the queue").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_lock_does_not_match_padlock_or_lockstep() -> None:
    """``"padlock"``, ``"lockstep"``, ``"wedlock"`` are not concurrency."""
    assert not _f("padlock metaphor in error message").matches_keywords(CONCURRENCY_KEYWORDS)
    assert not _f("the workers move in lockstep").matches_keywords(CONCURRENCY_KEYWORDS)
    assert not _f("till death or wedlock do us part").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_atomic_word_boundary() -> None:
    """``"atomic"`` must word-boundary; ``"subatomic"`` / ``"diatomic"`` skip."""
    assert _f("atomic compare-and-swap missing").matches_keywords(CONCURRENCY_KEYWORDS)
    assert not _f("diatomic gas analogy in docs").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_transaction_word_boundary() -> None:
    """``"transaction"`` matches standalone."""
    assert _f("DB transaction not committed").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_race_does_not_match_embraced() -> None:
    """``"race"`` substring should not match ``"embraced"`` / ``"traced"``."""
    assert not _f("the new pattern is embraced upstream").matches_keywords(CONCURRENCY_KEYWORDS)
    assert _f("classic TOCTOU race on the inbound_email column").matches_keywords(
        CONCURRENCY_KEYWORDS
    )


def test_concurrency_concurrent_matches_morphology() -> None:
    """Codex v0.2.3 R1 P2 regression guard: ``concurrent`` /
    ``concurrently`` / ``concurrency`` ALL match — legacy substring
    matcher caught all three forms. The naive ``\\bconcurrent\\b``
    pattern alone would miss ``concurrency`` (no word boundary between
    ``t`` and ``y``).
    """
    assert _f("concurrent writes risk lost updates").matches_keywords(CONCURRENCY_KEYWORDS)
    assert _f("concurrently invoked handlers").matches_keywords(CONCURRENCY_KEYWORDS)
    assert _f("concurrency hazard on shared cache").matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_concurrent_does_not_match_concur_or_recur() -> None:
    """``concur`` / ``recurrent`` / ``incurrent`` are unrelated."""
    assert not _f("the reviewers concur on the merge").matches_keywords(CONCURRENCY_KEYWORDS)
    assert not _f("recurrent invoice schedule").matches_keywords(CONCURRENCY_KEYWORDS)


# --- ARCH_KEYWORDS — morphology-friendly refactor / redesign ---------------


def test_arch_scope_does_not_match_telescope() -> None:
    """``"scope"`` must word-boundary; ``"telescope"`` should not match."""
    assert not _f("telescope-shaped backoff strategy").matches_keywords(ARCH_KEYWORDS)


def test_arch_scope_matches_scope_creep() -> None:
    """Standalone ``"scope"`` is an arch flag."""
    assert _f("out-of-scope changes to settings_svc").matches_keywords(ARCH_KEYWORDS)


def test_arch_refactor_matches_morphology() -> None:
    """``"refactoring"`` / ``"refactored"`` / ``"refactors"`` all match."""
    assert _f("refactoring opportunity in module X").matches_keywords(ARCH_KEYWORDS)
    assert _f("the handler was refactored last week").matches_keywords(ARCH_KEYWORDS)


def test_arch_design_does_not_match_redesign_morpheme() -> None:
    """``"\\bdesign\\b"`` should NOT match inside ``"redesign"``; ``"redesign"``
    is a separate keyword and is the one that should fire.
    """
    f = _f("redesign of the inbound_email column")
    # Matches via redesign keyword, NOT via design keyword inside redesign.
    assert f.matches_keywords(ARCH_KEYWORDS)


def test_arch_schema_word_boundary() -> None:
    """``"schema"`` matches standalone (e.g. ``"schema migration"``)."""
    assert _f("schema migration risk").matches_keywords(ARCH_KEYWORDS)


# --- SECURITY_KEYWORDS_SOFT — tokenize false-positive guard ----------------


def test_security_soft_token_does_not_match_tokenize() -> None:
    """v0.2.3 r1: ``"token"`` must word-boundary; ``"tokenizer"`` should not match."""
    assert not _f("tokenizer normalization missing").matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_security_soft_token_matches_standalone() -> None:
    assert _f("webhook token logged in plain text").matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_security_soft_auth_does_not_match_author() -> None:
    """``"auth"`` short token — must not match inside ``"author"`` / ``"authority"``."""
    assert not _f("the author of the commit needs review").matches_keywords(SECURITY_KEYWORDS_SOFT)
    assert _f("auth flow has a TOCTOU window").matches_keywords(SECURITY_KEYWORDS_SOFT)


# --- SECURITY_KEYWORDS_SEVERE — preserved v0.2.2 R4 behaviour --------------


def test_security_severe_rce_does_not_match_force() -> None:
    """Regression guard for v0.2.2 R4: ``"rce"`` substring in ``"force"`` must not fire."""
    assert not has_severe_security_match(_f("force-push from main is forbidden"))


def test_security_severe_rce_matches_acronym() -> None:
    assert has_severe_security_match(_f("Potential RCE via deserialization"))


def test_security_severe_constant_time_matches() -> None:
    """Hyphenated multi-word pattern still works."""
    assert has_severe_security_match(_f("constant-time HMAC compare needed"))


# --- Combined alias still works -------------------------------------------


def test_security_keywords_combined_alias_is_iterable_patterns() -> None:
    """``SECURITY_KEYWORDS = SECURITY_KEYWORDS_SEVERE + SECURITY_KEYWORDS_SOFT``
    must remain a tuple of compiled regex patterns so existing callers
    of ``Finding.matches_keywords(SECURITY_KEYWORDS)`` keep working.
    """
    assert isinstance(SECURITY_KEYWORDS, tuple)
    assert all(isinstance(p, re.Pattern) for p in SECURITY_KEYWORDS)
    assert _f("Potential timing attack in compare").matches_keywords(SECURITY_KEYWORDS)
    # Author should not falsely match auth via the combined alias.
    assert not _f("the author of the commit needs review").matches_keywords(SECURITY_KEYWORDS)


# --- v0.2.3 R2 — plural inflections for SOFT + ARCH phrase keywords --------


def test_security_soft_tokens_plural_matches() -> None:
    """Codex v0.2.3 R2 P1: ``tokens`` / ``credentials`` plural must match SOFT."""
    assert _f("multiple tokens cached without expiry").matches_keywords(SECURITY_KEYWORDS_SOFT)
    assert _f("user credentials stored unencrypted").matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_security_soft_passwords_secrets_plural_matches() -> None:
    """``passwords`` and ``secrets`` plural variants must match SOFT."""
    assert _f("passwords and secrets logged").matches_keywords(SECURITY_KEYWORDS_SOFT)
    assert _f("rotate old passwords on signup").matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_security_soft_plural_still_not_match_tokenize_or_credentialed() -> None:
    """Plural extension must not enable suffix-class false positives."""
    assert not _f("tokenizer normalization missing").matches_keywords(SECURITY_KEYWORDS_SOFT)
    assert not _f("tokenization step optional").matches_keywords(SECURITY_KEYWORDS_SOFT)
    # `credentialed` would be `\bcredential\b` substring inside word — boundary blocks
    assert not _f("credentialed user roles audit").matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_arch_breaking_changes_plural_matches() -> None:
    """Codex v0.2.3 R2 P2: ``breaking changes`` plural phrase must match ARCH."""
    assert _f("multiple breaking changes in PR").matches_keywords(ARCH_KEYWORDS)
    assert _f("breaking change introduced by refactor").matches_keywords(ARCH_KEYWORDS)


def test_arch_interface_changes_plural_matches() -> None:
    """``interface changes`` plural phrase must match ARCH."""
    assert _f("interface changes break consumers").matches_keywords(ARCH_KEYWORDS)
    assert _f("the interface change is backward-compatible").matches_keywords(ARCH_KEYWORDS)


def test_security_soft_hmac_singular_only_no_regression() -> None:
    """Q1 NO plural for ``hmac`` (acronym) — singular still matches; ``hmacs`` is
    non-standard and we accept it not matching."""
    assert _f("HMAC verification step skipped").matches_keywords(SECURITY_KEYWORDS_SOFT)
    assert _f("hmac validation missing on webhook").matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_arch_design_scope_architecture_singular_no_regression() -> None:
    """Q1 NO plural for design/scope/architecture — singular dominates Codex prose."""
    assert _f("schema design must be revisited").matches_keywords(ARCH_KEYWORDS)
    assert _f("scope creep on settings_svc").matches_keywords(ARCH_KEYWORDS)
    assert _f("the overall architecture is sound").matches_keywords(ARCH_KEYWORDS)
    # Plural forms remain unmatched — by design.
    assert not _f("designs of the auth subsystem").matches_keywords(ARCH_KEYWORDS)
    assert not _f("scopes are nested too deeply").matches_keywords(ARCH_KEYWORDS)
