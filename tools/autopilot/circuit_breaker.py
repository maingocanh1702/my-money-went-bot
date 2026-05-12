"""Circuit breaker conditions — 10 halt triggers per Level 3 template.

When a breaker fires, the loop writes a forensic report at
``.autopilot/state/<feature>/halt-report.md`` and stops. Founder reads,
decides path forward, runs ``autopilot resume <feature>`` after fixing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .codex import (
    ARCH_KEYWORDS,
    CONCURRENCY_KEYWORDS,
    SECURITY_KEYWORDS,
    Finding,
    ReviewResult,
)
from .config import Config
from .state import FeatureState


@dataclass
class BreakerTrigger:
    code: str  # short symbolic code, e.g. "ARCH_FINDING"
    description: str
    detail: str = ""


def evaluate(
    review: ReviewResult,
    state: FeatureState,
    cfg: Config,
) -> BreakerTrigger | None:
    """Check all 10 conditions. Return the first triggered (None if clear)."""
    # 5: max rounds reached.
    if state.current_round >= cfg.max_review_rounds and review.findings:
        return BreakerTrigger(
            "MAX_ROUNDS",
            f"reached {cfg.max_review_rounds} Codex rounds without clean state",
            detail=f"open findings: {len(review.findings)}",
        )

    for f in review.findings:
        # 1: architectural finding.
        if f.matches_keywords(ARCH_KEYWORDS):
            return BreakerTrigger(
                "ARCH_FINDING",
                "architectural finding requires founder review",
                detail=_format_finding(f),
            )
        # 2: security/auth finding.
        if f.matches_keywords(SECURITY_KEYWORDS):
            return BreakerTrigger(
                "SECURITY_FINDING",
                "security/auth finding — founder audit before auto-fix",
                detail=_format_finding(f),
            )
        # 3: concurrency finding (allow if just retry/idempotency, but flag others).
        if f.matches_keywords(CONCURRENCY_KEYWORDS):
            haystack = (f.summary + " " + f.detail_text).lower()
            if "idempot" not in haystack and "retry" not in haystack:
                return BreakerTrigger(
                    "CONCURRENCY_FINDING",
                    "concurrency/race finding — founder review recommended",
                    detail=_format_finding(f),
                )
        # 4: same finding recurring (fix attempted, Codex re-flagged).
        if f.hash in set(state.fixed_finding_hashes):
            return BreakerTrigger(
                "RECURRING_FINDING",
                "same finding recurring after fix attempt",
                detail=_format_finding(f),
            )
        # 10: mypy `# type: ignore` proposed.
        if "type: ignore" in f.detail_text or "type:ignore" in f.detail_text:
            return BreakerTrigger(
                "TYPE_IGNORE_PROPOSED",
                "Codex proposed a type: ignore — founder OK required",
                detail=_format_finding(f),
            )
        # 9: detect-secrets new finding (heuristic: keyword in finding).
        if "detect-secrets" in f.detail_text.lower() or "secret leak" in f.detail_text.lower():
            return BreakerTrigger(
                "SECRETS_FINDING",
                "possible secret leak — founder audit",
                detail=_format_finding(f),
            )

    return None


def write_halt_report(
    cfg: Config,
    state: FeatureState,
    trigger: BreakerTrigger,
    review: ReviewResult | None = None,
) -> Path:
    artifacts_dir = cfg.state_dir / state.feature_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifacts_dir / "halt-report.md"

    lines = [
        f"# HALT — Level 3 autopilot circuit broken: {trigger.code}",
        "",
        f"**Feature:** {state.feature_id}",
        f"**Branch:** {state.branch}",
        f"**Phase:** {state.phase}",
        f"**Round:** {state.current_round} / {cfg.max_review_rounds}",
        f"**Trigger:** {trigger.code} — {trigger.description}",
        "",
        "## Trigger detail",
        "",
        trigger.detail or "(no detail)",
        "",
    ]
    if review is not None:
        lines += [
            "## Codex round summary",
            "",
            f"- Findings: {len(review.findings)}",
            f"- Duration: {review.duration_seconds:.1f}s",
            f"- Raw output: {cfg.state_dir / state.feature_id / 'codex' / f'round-{state.current_round:02d}.txt'}",
            "",
            "## All findings this round",
            "",
        ]
        for f in review.findings:
            lines.append(f"- [{f.severity}] {f.summary} (hash {f.hash})")
            if f.file:
                lines.append(f"  Location: {f.file}:{f.line_start}")
    lines += [
        "",
        "## Resume instructions",
        "",
        "1. Read this report + Codex raw output.",
        "2. Make founder decision (accept finding's recommendation, override, defer).",
        "3. Apply fixes manually if needed; commit.",
        "4. Run `python -m tools.autopilot resume {feature}` to continue from current phase.",
        f"   (Replace {{feature}} with `{state.feature_id}`.)",
        "",
        "## State preserved",
        "",
        f"- Branch HEAD: see `git log -1 {state.branch}`",
        f"- State JSON: {cfg.state_dir / state.feature_id / 'state.json'}",
        f"- Fixed finding hashes so far: {state.fixed_finding_hashes}",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _format_finding(f: Finding) -> str:
    loc = f"{f.file}:{f.line_start}" if f.file else "<no file>"
    return (
        f"[{f.severity}] {f.summary}\n"
        f"Location: {loc}\n"
        f"Detail (truncated):\n{f.detail_text[:400]}"
    )
