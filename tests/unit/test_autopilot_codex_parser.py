"""Unit tests for the Codex output parser.

Fixtures based on real Wave 0 W0.1/W0.6 review output shapes documented in
docs/prompts/level3-autopilot-template.md (parser pseudocode).

Real-CLI fixtures live in ``tests/fixtures/codex/`` — captured from F07
(Settings) and W0.8 (webhook display_suffix) pilot runs against Codex CLI
v0.130. These cover both observed output shapes (with and without
``codex`` marker line).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.autopilot.codex import ReviewResult, parse_findings
from tools.autopilot.config import Config

FIXTURES = Path(__file__).parent.parent / "fixtures" / "codex"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


CLEAN_OUTPUT = """\
preamble line
metadata
---

user

(prompt echo)

exec
exec command output blah

codex

# Codex Review

Target: branch diff against main

I did not identify any discrete, actionable bugs/regressions/defects in this
diff. The change is small and contained.
"""

FINDINGS_OUTPUT_P_STYLE = """\
preamble
---

user
exec
exec output

codex

# Codex Review

Target: branch diff against main
Verdict: needs-attention

The diff introduces 2 issues worth flagging.

Findings:
- [P1] NULL ref_code breaks UNIQUE — /repo/markets/vn/sepay.py:42-50
  Detail: PostgreSQL treats NULL != NULL so the constraint won't fire.
  Recommendation: add a partial unique index excluding NULL.

- [P2] Missing test for missing optional field — /repo/tests/test_sepay.py:120
  Detail: covers only happy path.
  Recommendation: parametrize over None inputs.

Next steps:
- address P1 before merge.
"""

FINDINGS_OUTPUT_HML_STYLE = """\
preamble
codex

# Codex Review

- [HIGH] Token compared in non-constant time — /repo/core/auth.py:33
  Detail: timing attack risk.
  Recommendation: use hmac.compare_digest.
- [LOW] Consider caching i18n table — /repo/core/i18n.py:12
  Detail: nice-to-have.
"""

DUPLICATE_OUTPUT = """\
codex

# Codex Review
- [P1] Race in webhook handler — /repo/markets/vn/webhook.py:55
  Detail: unguarded counter increment.

# Codex Review
- [P1] Race in webhook handler — /repo/markets/vn/webhook.py:55
  Detail: unguarded counter increment.
"""


def test_clean_output_returns_no_findings() -> None:
    findings, clean = parse_findings(CLEAN_OUTPUT)
    assert clean is True
    assert findings == []


def test_p_style_findings_parsed_with_severity_and_file() -> None:
    findings, clean = parse_findings(FINDINGS_OUTPUT_P_STYLE)
    assert clean is False
    assert len(findings) == 2

    f1 = findings[0]
    assert f1.severity == "P1"
    assert "NULL ref_code" in f1.summary
    assert f1.file == "/repo/markets/vn/sepay.py"
    assert f1.line_start == 42
    assert f1.line_end == 50

    f2 = findings[1]
    assert f2.severity == "P2"
    assert f2.file == "/repo/tests/test_sepay.py"
    assert f2.line_start == 120


def test_high_medium_low_normalized_to_p_scale() -> None:
    findings, _ = parse_findings(FINDINGS_OUTPUT_HML_STYLE)
    severities = [f.severity for f in findings]
    assert severities == ["P1", "P3"]


def test_duplicate_blocks_deduped() -> None:
    findings, clean = parse_findings(DUPLICATE_OUTPUT)
    assert clean is False
    assert len(findings) == 1
    assert findings[0].severity == "P1"


def test_truly_malformed_returns_uncertain() -> None:
    """Defensive: garbage input → findings=[], clean=False (uncertain).

    Loop halts via PARSER_UNCERTAIN breaker rather than entering fix-loop
    with empty findings. Pre-v0.2.1 the parser used the same return value
    for both "no marker present" and "truly garbage" — now only the latter
    yields this state.
    """
    findings, clean = parse_findings("this is not a codex review at all")
    assert findings == []
    assert clean is False


# --- Real-CLI fixture tests (v0.2.1 parser fixes) -------------------------


def test_parse_findings_no_marker_extracts_p2_finding() -> None:
    """F07 round 1: real Codex output, no ``codex`` marker, P2 finding.

    Pre-v0.2.1 the parser early-returned ([], False) and the loop tried
    to fix-loop with empty findings → 0 commits → FIX_FAILED breaker.
    Now the parser falls back to whole-output parsing.
    """
    findings, clean = parse_findings(
        _read_fixture("f07-round-01-p2-no-marker.txt"),
    )
    assert clean is False
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "P2"
    assert "analytics insert" in f.summary.lower()
    assert f.file is not None and f.file.endswith("settings_svc.py")
    assert f.line_start == 270
    assert f.line_end == 279


def test_parse_findings_no_marker_detects_clean() -> None:
    """F07 round 2: real Codex output, no marker, clean verdict.

    Phrase "did not find any concrete, actionable regressions" matches
    CLEAN_PHRASES even without the marker.
    """
    findings, clean = parse_findings(
        _read_fixture("f07-round-02-clean-no-marker.txt"),
    )
    assert clean is True
    assert findings == []


def test_parse_findings_with_marker_still_clean_round_01() -> None:
    """W0.8 round 1: real Codex output WITH preamble + marker, clean.

    Regression guard — fixing the no-marker bug must not break the
    existing marker path. Phrase "did not identify any actionable bugs"
    matches CLEAN_PHRASES.
    """
    findings, clean = parse_findings(
        _read_fixture("w08-round-01-clean-with-marker.txt"),
    )
    assert clean is True
    assert findings == []


def test_parse_findings_with_marker_clean_round_02() -> None:
    """W0.8 round 2: marker + alternative clean phrasing.

    Phrase "did not identify any introduced defects" — newly added to
    CLEAN_PHRASES in v0.2.1.
    """
    findings, clean = parse_findings(
        _read_fixture("w08-round-02-clean-with-marker.txt"),
    )
    assert clean is True
    assert findings == []


def test_finding_hash_is_stable_and_short() -> None:
    findings, _ = parse_findings(FINDINGS_OUTPUT_P_STYLE)
    assert all(len(f.hash) == 12 for f in findings)
    assert findings[0].hash != findings[1].hash


def test_keyword_matchers() -> None:
    findings, _ = parse_findings(FINDINGS_OUTPUT_HML_STYLE)
    from tools.autopilot.codex import ARCH_KEYWORDS, SECURITY_KEYWORDS

    # First finding mentions "timing attack" → security match.
    assert findings[0].matches_keywords(SECURITY_KEYWORDS) is True
    # Neither should match arch keywords.
    assert findings[0].matches_keywords(ARCH_KEYWORDS) is False
    assert findings[1].matches_keywords(SECURITY_KEYWORDS) is False


# --- save_review_artifact non-clobber (v0.2.2 fix #6) ----------------------


def _stub_review_result(text: str) -> ReviewResult:
    return ReviewResult(clean=True, findings=[], raw_output=text, base="main", duration_seconds=0.1)


def test_save_review_artifact_first_write_uses_canonical_name(tmp_path: Path) -> None:
    """First save lands at round-NN.txt."""
    from tools.autopilot.codex import save_review_artifact

    cfg = _codex_cfg(tmp_path)
    result = _stub_review_result("first-run output")
    out = save_review_artifact(cfg, result, "F99", 1)
    assert out.name == "round-01.txt"
    assert out.read_text(encoding="utf-8") == "first-run output"


def test_save_review_artifact_second_write_does_not_clobber(tmp_path: Path) -> None:
    """Second save of the same round lands at round-NN-resume1.txt.

    Resume cycles per v0.2.1 reset Phase C round counter back to 1; this
    test pins the non-clobber behavior so resume forensics persist.
    """
    from tools.autopilot.codex import save_review_artifact

    cfg = _codex_cfg(tmp_path)
    first = _stub_review_result("first-run output")
    p1 = save_review_artifact(cfg, first, "F99", 1)
    assert p1.name == "round-01.txt"
    second = _stub_review_result("resumed-run output")
    p2 = save_review_artifact(cfg, second, "F99", 1)
    assert p2.name == "round-01-resume1.txt"
    # Both files coexist, contents preserved.
    assert p1.exists()
    assert p1.read_text(encoding="utf-8") == "first-run output"
    assert p2.read_text(encoding="utf-8") == "resumed-run output"

    # Third save → -resume2 suffix.
    third = _stub_review_result("third pass")
    p3 = save_review_artifact(cfg, third, "F99", 1)
    assert p3.name == "round-01-resume2.txt"


# --- stale-blob detection (v0.2.2 workaround #7) ---------------------------


def _codex_cfg(tmp_path: Path) -> Config:
    return Config(
        repo_root=tmp_path,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=tmp_path / ".autopilot" / "state",
    )


def test_warn_if_stale_blob_no_warning_when_head_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Codex output mentioning current HEAD prefix → no warning."""
    from tools.autopilot import codex as codex_mod

    cfg = _codex_cfg(tmp_path)
    monkeypatch.setattr(
        "tools.autopilot.codex.git_ops.head_sha",
        lambda _c: "abc1234deadbeef",  # pragma: allowlist secret
    )
    with caplog.at_level("WARNING", logger="tools.autopilot.codex"):
        codex_mod._warn_if_stale_blob(cfg, "review references abc1234 (good)")
    assert "stale-blob" not in caplog.text.lower()


def test_warn_if_stale_blob_warns_on_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Codex output mentioning a SHA prefix unrelated to HEAD → warning."""
    from tools.autopilot import codex as codex_mod

    cfg = _codex_cfg(tmp_path)
    monkeypatch.setattr("tools.autopilot.codex.git_ops.head_sha", lambda _c: "def5678" + "0" * 33)
    with caplog.at_level("WARNING", logger="tools.autopilot.codex"):
        codex_mod._warn_if_stale_blob(cfg, "review base sha was abc1234, reviewed blob aaaaaaa")
    body = caplog.text.lower()
    assert "stale-blob" in body
    assert "def5678" in body


def test_warn_if_stale_blob_silent_when_no_sha_in_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """No SHA-looking tokens → nothing to compare → no warning."""
    from tools.autopilot import codex as codex_mod

    cfg = _codex_cfg(tmp_path)
    monkeypatch.setattr("tools.autopilot.codex.git_ops.head_sha", lambda _c: "deadbeef")
    with caplog.at_level("WARNING", logger="tools.autopilot.codex"):
        codex_mod._warn_if_stale_blob(cfg, "plain prose without any sha tokens")
    assert "stale-blob" not in caplog.text.lower()
