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
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config

CLEAN_PHRASES = (
    "did not identify any discrete",
    "did not identify any actionable",
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
ARCH_KEYWORDS = (
    "schema",
    "design",
    "scope",
    "architecture",
    "refactor",
    "redesign",
    "contract",
    "interface change",
    "breaking change",
)
SECURITY_KEYWORDS = (
    "security",
    "auth",
    "credential",
    "token",
    "password",
    "secret",
    "hmac",
    "constant-time",
    "timing attack",
    "injection",
    "csrf",
    "xss",
)
CONCURRENCY_KEYWORDS = (
    "race",
    "concurrent",
    "deadlock",
    "lock",
    "atomic",
    "transaction",
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

    def matches_keywords(self, keywords: tuple[str, ...]) -> bool:
        haystack = (self.summary + " " + self.detail_text).lower()
        return any(kw in haystack for kw in keywords)


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
    return ReviewResult(
        clean=clean,
        findings=findings,
        raw_output=output,
        base=base,
        duration_seconds=duration,
    )


def parse_findings(output: str) -> tuple[list[Finding], bool]:
    """Parse Codex review stdout into structured Finding list + clean flag.

    Algorithm (verified against Wave 0 captured outputs):
    1. Locate ``codex`` marker line (start of review section).
    2. Detect clean by phrase match in review section.
    3. Extract severity-bullet lines + indented detail lines.
    4. Dedupe by (severity, file, line_start, summary[:80]).
    """
    lines = output.splitlines()
    codex_markers = [i for i, line in enumerate(lines) if line.strip() == "codex"]
    if not codex_markers:
        # No review section detected — defensive: treat as no findings,
        # but signal abnormal via empty list + clean=False (caller decides).
        return [], False

    review_lines = lines[codex_markers[0] :]
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
    return unique, len(unique) == 0


def save_review_artifact(
    cfg: Config,
    result: ReviewResult,
    feature_id: str,
    round_num: int,
) -> Path:
    """Persist raw Codex output for forensic / circuit-breaker reports."""
    artifacts_dir = cfg.state_dir / feature_id / "codex"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / f"round-{round_num:02d}.txt"
    out_path.write_text(result.raw_output, encoding="utf-8")
    return out_path
