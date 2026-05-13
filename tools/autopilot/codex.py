"""Codex CLI wrapper + findings parser.

Reference: docs/prompts/level3-autopilot-template.md (parser pseudocode
verified against real Codex output 2026-05-11).

Critical quirks documented in source:
- ``codex review`` exit code is **always 0** — must parse stdout.
- Review block appears TWICE in output — must dedupe by (sev, file, line, summary[:80]).
- Two severity styles: ``[P0..P3]`` and ``[high|medium|low]``.
- ~95% of stdout is preamble + diff dump; ~5% review.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import git_ops
from .config import Config

log = logging.getLogger(__name__)

# Match a 7-40 char hex token surrounded by word boundaries; used by the
# stale-blob detector to compare Codex's output SHA(s) against current HEAD.
_SHA_PATTERN = re.compile(r"\b([0-9a-f]{7,40})\b")

CLEAN_PHRASES = (
    "did not identify any discrete",
    "did not identify any actionable",
    "did not identify any introduced defects",
    "did not find any",
    "no actionable regressions",
    "no actionable defects",
)

SEVERITY_RE = re.compile(
    r"^\s*-\s*\[(?P<sev>P[0-3]|CRITICAL|HIGH|MEDIUM|LOW|"
    r"high|medium|low|p[0-3])\]\s*(?P<summary>.+)$",
)
FILE_RE = re.compile(r"(/[\w./-]+\.py):(\d+)(?:[-:](\d+))?")
SEVERITY_NORMALIZE = {
    "HIGH": "P1",
    "MEDIUM": "P2",
    "LOW": "P3",
    "CRITICAL": "P0",
}
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# Keywords used by circuit_breaker.py to flag arch / security findings.
#
# v0.2.3: ALL keyword categories now use compiled regex with `\b` word
# boundaries, mirroring the v0.2.2 R4 SECURITY_KEYWORDS_SEVERE pattern
# (which previously did `re.search(r"\b" + re.escape(kw) + r"\b", …)` at
# match time). Substring matching in the legacy tuple-of-strings layout
# caused F07 phase B halt 2026-05-13: the substring "lock" matched
# inside "block" / "guarded block", tripping CONCURRENCY_FINDING on a
# P2 finding that should have routed through normal fix flow.
#
# The "lock" keyword is a known compound: catch lock/locks/locking/
# locked/deadlock/livelock variants WITHOUT false-matching
# block/padlock/lockstep/wedlock. Morphology-friendly ARCH keywords
# (refactor, redesign) use a non-capturing suffix group so "refactoring"
# / "redesigned" / etc. still match (preserves the substring-era
# behaviour those words relied on; the false-positive risk for these
# is negligible compared to short tokens like "lock" or "rce").
ARCH_KEYWORDS = (
    re.compile(r"\bschema\b", re.IGNORECASE),
    re.compile(r"\bdesign\b", re.IGNORECASE),
    re.compile(r"\bscope\b", re.IGNORECASE),
    re.compile(r"\barchitecture\b", re.IGNORECASE),
    re.compile(r"\brefactor(?:s|ing|ed|ation)?\b", re.IGNORECASE),
    re.compile(r"\bredesign(?:s|ing|ed)?\b", re.IGNORECASE),
    re.compile(r"\bcontract\b", re.IGNORECASE),
    # Codex v0.2.3 R2 P2: phrase keywords need plural suffix — legacy
    # substring matcher caught "interface changes" / "breaking changes";
    # bare `\bphrase\b` regex did not.
    re.compile(r"\binterface change(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bbreaking change(?:s)?\b", re.IGNORECASE),
)
# Severe — auto-HALT regardless of severity rating (P0..P3). These phrases
# name concrete security vulnerability categories.
SECURITY_KEYWORDS_SEVERE = (
    re.compile(r"\bauth bypass\b", re.IGNORECASE),
    re.compile(r"\btoken leak\b", re.IGNORECASE),
    re.compile(r"\bcredential leak\b", re.IGNORECASE),
    re.compile(r"\bsecret leak\b", re.IGNORECASE),
    re.compile(r"\bpassword leak\b", re.IGNORECASE),
    re.compile(r"\btiming attack\b", re.IGNORECASE),
    re.compile(r"\bconstant-time\b", re.IGNORECASE),
    re.compile(r"\binjection\b", re.IGNORECASE),
    re.compile(r"\bcsrf\b", re.IGNORECASE),
    re.compile(r"\bxss\b", re.IGNORECASE),
    re.compile(r"\bssrf\b", re.IGNORECASE),
    re.compile(r"\brce\b", re.IGNORECASE),
    re.compile(r"\bremote code execution\b", re.IGNORECASE),
)


def has_severe_security_match(finding: Finding) -> bool:
    """Word-boundary check against SECURITY_KEYWORDS_SEVERE."""
    haystack = finding.summary + " " + finding.detail_text
    return any(pat.search(haystack) for pat in SECURITY_KEYWORDS_SEVERE)


# Soft — bare mentions of security-adjacent vocabulary that don't
# necessarily indicate risk. F07 R1 in v0.2.1 was a markdown-rendering
# bug auto-halted only because the finding mentioned "token". Soft
# keywords now require P0/P1 severity to escalate to HALT — P2/P3
# soft-keyword findings fall through to normal fix flow.
SECURITY_KEYWORDS_SOFT = (
    re.compile(r"\bsecurity\b", re.IGNORECASE),
    # `auth` and `hmac` kept singular per founder Q1 — `hmac` is an
    # acronym (no plural form), `auth` is a verb-like prefix that
    # rarely takes `-s` in finding prose.
    re.compile(r"\bauth\b", re.IGNORECASE),
    # Countables — add optional `(?:s)?` to match plural forms.
    # Codex v0.2.3 R2 P1: legacy substring matcher caught `tokens` /
    # `credentials` / `passwords` / `secrets` (e.g. "credentials
    # exposed"); the bare `\bword\b` regex did not. Closes the
    # SOFT+P0/P1 escalation gap.
    re.compile(r"\bcredential(?:s)?\b", re.IGNORECASE),
    re.compile(r"\btoken(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bpassword(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsecret(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bhmac\b", re.IGNORECASE),
)
# Back-compat alias for any external callers. The combined tuple keeps
# the original public name working; the circuit breaker uses the tier
# constants directly.
SECURITY_KEYWORDS = SECURITY_KEYWORDS_SEVERE + SECURITY_KEYWORDS_SOFT
CONCURRENCY_KEYWORDS = (
    re.compile(r"\brace\b", re.IGNORECASE),
    # Matches "concurrent" / "concurrently" / "concurrency" — the legacy
    # substring matcher caught all three. Codex v0.2.3 R1 P2 regression
    # guard: `\bconcurrent\b` alone misses "concurrency" (word boundary
    # between `t` and `y` does not fire — both are word chars).
    re.compile(r"\bconcurren(?:t(?:ly)?|cy)\b", re.IGNORECASE),
    # Compound `lock`: catches lock / locks / locking / locked /
    # deadlock / livelock variants but NOT block / padlock / lockstep /
    # wedlock. Closes F07 phase B halt (Codex finding "Move
    # serialization inside the guarded block" had "lock" substring
    # inside "block", tripping CONCURRENCY_FINDING).
    re.compile(r"\b(?:dead|live)?lock(?:s|ing|ed)?\b", re.IGNORECASE),
    re.compile(r"\batomic\b", re.IGNORECASE),
    re.compile(r"\btransaction\b", re.IGNORECASE),
)


@dataclass
class Finding:
    severity: str  # Normalized: P0|P1|P2|P3
    summary: str
    detail: list[str] = field(default_factory=list)
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None

    @property
    def rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 99)

    @property
    def hash(self) -> str:
        key = f"{self.severity}|{self.file}|{self.line_start}|{self.summary[:80]}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

    @property
    def detail_text(self) -> str:
        return "\n".join(self.detail)

    def matches_keywords(self, keywords: tuple[re.Pattern[str], ...]) -> bool:
        """True if any compiled keyword pattern matches summary + detail.

        v0.2.3: keyword categories now ship as compiled regex with `\b`
        word boundaries (mirrors v0.2.2 R4 SECURITY_KEYWORDS_SEVERE
        pattern). Stops short-token substring false positives — the
        F07 phase B halt where "lock" inside "block" tripped
        CONCURRENCY_FINDING. Each pattern carries its own
        re.IGNORECASE flag.
        """
        haystack = self.summary + " " + self.detail_text
        return any(pat.search(haystack) for pat in keywords)


@dataclass
class ReviewResult:
    clean: bool
    findings: list[Finding]
    raw_output: str
    base: str
    duration_seconds: float

    @property
    def blocking_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in ("P0", "P1")]

    @property
    def auto_fixable_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in ("P2", "P3")]


def run_review(
    cfg: Config,
    *,
    base: str | None = None,
    extra_prompt: str | None = None,
    timeout_seconds: int = 600,
) -> ReviewResult:
    """Invoke ``codex review --base <base>`` and parse findings.

    Returns ``ReviewResult``. Raises on subprocess failure (rare — Codex
    returns 0 even with findings).
    """
    base = base or cfg.base_branch
    cmd = [cfg.codex_bin, "review", "--base", base]
    if extra_prompt:
        cmd.append(extra_prompt)
    import time

    start = time.time()
    completed = subprocess.run(
        cmd,
        cwd=cfg.repo_root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    duration = time.time() - start
    output = completed.stdout
    if not output and completed.stderr:
        # Codex normally prints to stdout; stderr-only output is abnormal.
        raise RuntimeError(
            f"codex review produced no stdout. stderr:\n{completed.stderr}",
        )
    findings, clean = parse_findings(output)
    _warn_if_stale_blob(cfg, output)
    return ReviewResult(
        clean=clean,
        findings=findings,
        raw_output=output,
        base=base,
        duration_seconds=duration,
    )


def _warn_if_stale_blob(cfg: Config, output: str) -> None:
    """Log a warning if Codex output mentions a SHA that doesn't match HEAD.

    v0.2.2 workaround for issue #7 (codex stale-blob): Codex CLI has
    been observed reviewing a stale git blob SHA instead of HEAD (F07
    i18n fix session 4). True fix needs Codex CLI integration audit
    (v0.2.3 backlog). For now we surface the discrepancy so the operator
    can manually verify findings against the current state.
    """
    try:
        head = git_ops.head_sha(cfg)
    except Exception as exc:  # noqa: BLE001 — best-effort diagnostic
        log.debug("stale-blob check skipped: head_sha failed (%s)", exc)
        return
    matches = {s.lower() for s in _SHA_PATTERN.findall(output)}
    if not matches:
        return
    head_prefix = head[:7].lower()
    if any(m.startswith(head_prefix) or head_prefix.startswith(m) for m in matches):
        return
    log.warning(
        "codex review: output references SHA(s) %s but current HEAD is %s. "
        "Possible stale-blob issue — verify findings against current state "
        "before acting on them (v0.2.3 backlog: pin explicit SHA).",
        sorted(matches)[:3],
        head_prefix,
    )


def parse_findings(output: str) -> tuple[list[Finding], bool]:
    """Parse Codex review stdout into structured Finding list + clean flag.

    Algorithm (verified against Wave 0 + F07/W0.8 pilot outputs):
    1. If ``codex`` marker line present, slice review section starting there
       (skips preamble + diff dump). Otherwise treat entire output as the
       review section — Codex CLI v0.130 in subprocess context sometimes
       emits only the verdict (~900 bytes, no marker, no preamble).
    2. Detect clean by phrase match in review section.
    3. Extract severity-bullet lines + indented detail lines.
    4. Dedupe by (severity, file, line_start, summary[:80]).

    Returns ``(findings, clean)``:
    - findings non-empty → fix-loop with those findings.
    - clean True (empty findings) → clean round.
    - Both empty (findings=[] AND clean=False) → uncertain; caller should
      halt via PARSER_UNCERTAIN breaker rather than fix-loop blindly.
    """
    lines = output.splitlines()
    codex_markers = [i for i, line in enumerate(lines) if line.strip() == "codex"]
    if codex_markers:
        review_lines = lines[codex_markers[0] :]
    else:
        # Marker absent — Codex CLI v0.130 sometimes emits just the verdict
        # text without preamble or marker. Fall back to whole-output parsing.
        review_lines = lines

    review_text = "\n".join(review_lines).lower()

    if any(phrase in review_text for phrase in CLEAN_PHRASES):
        return [], True

    findings: list[Finding] = []
    current: Finding | None = None
    for line in review_lines:
        m = SEVERITY_RE.match(line)
        if m:
            if current is not None:
                findings.append(current)
            sev_raw = m.group("sev").upper()
            sev_normalized = SEVERITY_NORMALIZE.get(sev_raw, sev_raw)
            current = Finding(
                severity=sev_normalized,
                summary=m.group("summary").strip(),
            )
            # Line containing severity bullet may also contain file:line.
            fm = FILE_RE.search(line)
            if fm:
                current.file = fm.group(1)
                current.line_start = int(fm.group(2))
                current.line_end = int(fm.group(3)) if fm.group(3) else current.line_start
        elif current is not None:
            fm = FILE_RE.search(line)
            if fm and current.file is None:
                current.file = fm.group(1)
                current.line_start = int(fm.group(2))
                current.line_end = int(fm.group(3)) if fm.group(3) else current.line_start
            current.detail.append(line)
    if current is not None:
        findings.append(current)

    # Dedupe — Codex prints review block twice (CLI quirk verified 2026-05-11).
    seen: set[tuple[str, str | None, int | None, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.severity, f.file, f.line_start, f.summary[:80])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    # If we extracted findings, clean=False. If we extracted nothing AND
    # no CLEAN_PHRASE matched (checked above), output is uncertain — caller
    # should halt via PARSER_UNCERTAIN rather than fix-loop blindly.
    return unique, False


def save_review_artifact(
    cfg: Config,
    result: ReviewResult,
    feature_id: str,
    round_num: int,
) -> Path:
    """Persist raw Codex output for forensic / circuit-breaker reports.

    v0.2.2 fix #6: on resume, the loop replays Phase C from round 1 (per
    v0.2.1 round-counter reset). Writing to ``round-NN.txt`` would clobber
    the prior-run artifact, losing forensics that explain why the earlier
    attempt halted. Detect a collision and suffix ``-resumeN`` instead.
    """
    artifacts_dir = cfg.state_dir / feature_id / "codex"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"round-{round_num:02d}"
    out_path = artifacts_dir / f"{base_name}.txt"
    if out_path.exists():
        n = 1
        while True:
            candidate = artifacts_dir / f"{base_name}-resume{n}.txt"
            if not candidate.exists():
                out_path = candidate
                break
            n += 1
            if n > 99:
                raise RuntimeError(
                    f"Too many resume artifacts for {feature_id} round "
                    f"{round_num} — manual cleanup needed in {artifacts_dir}.",
                )
    out_path.write_text(result.raw_output, encoding="utf-8")
    return out_path
