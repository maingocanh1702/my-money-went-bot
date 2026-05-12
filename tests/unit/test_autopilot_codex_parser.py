"""Unit tests for the Codex output parser.

Fixtures based on real Wave 0 W0.1/W0.6 review output shapes documented in
docs/prompts/level3-autopilot-template.md (parser pseudocode).
"""

from __future__ import annotations

from tools.autopilot.codex import parse_findings

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


def test_no_codex_marker_returns_empty_not_clean() -> None:
    # If output doesn't have a 'codex' marker, treat as abnormal -> not clean.
    findings, clean = parse_findings("just preamble\nno marker here")
    assert findings == []
    assert clean is False


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
