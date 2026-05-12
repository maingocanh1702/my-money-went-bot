"""Validate a feature spec (FE + BE pair) before autopilot consumes it.

Why this exists: per Wave 0 lesson #2, gap discovery mid-autopilot kills
architectural control. The linter pushes the discovery moment to BEFORE
the autopilot starts, where the founder is in the loop.

What it checks:
1. FE spec file exists for ``feature_id``.
2. BE tech doc paired (auto-derived path).
3. Required sections present (1.Mô tả, 2.Use Cases, 10.Acceptance Criteria,
   Changelog).
4. Acceptance Criteria has >=3 testable items.
5. No TODO|TBD|FIXME|XXX|??? in Acceptance / Use Cases / API sections.
6. ``autopilot:gaps`` block, if present, has 0 OPEN gaps.
7. ``autopilot:test_plan`` block, if present, has all 5 categories
   (each either populated or explicitly marked N/A with reason).
8. ``autopilot:meta`` block, if present, has feature_id matching filename.

Returns ``LintReport`` with errors (block autopilot) and warnings (advisory).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config

# Required FE sections — match by header substring (lenient to accommodate
# slight wording variations in existing specs).
REQUIRED_FE_SECTIONS = (
    ("Mô tả", "1. Mô tả"),
    ("Use Cases", "2. Use Cases"),
    ("Acceptance Criteria", "10. Acceptance Criteria"),
    ("Changelog", "Changelog"),
)

# Required BE sections.
REQUIRED_BE_SECTIONS = (
    ("Implementation Overview", "1. Implementation Overview"),
    ("Testing Plan", "5. Testing Plan"),
    ("Changelog", "Changelog"),
)

CRITICAL_SECTIONS_FOR_TODO_SCAN = (
    "Acceptance Criteria",
    "Use Cases",
    "API",
    "Domain Model",
)

TODO_PATTERN = re.compile(r"\b(TODO|TBD|FIXME|XXX|\?\?\?)\b", re.IGNORECASE)
ACCEPTANCE_ITEM_PATTERN = re.compile(r"^\s*-\s*\[[ x]\]\s+\S", re.MULTILINE)
META_BLOCK_PATTERN = re.compile(
    r"<!--\s*autopilot:meta\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)
GAPS_BLOCK_PATTERN = re.compile(
    r"<!--\s*autopilot:gaps\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)
TEST_PLAN_BLOCK_PATTERN = re.compile(
    r"<!--\s*autopilot:test_plan\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)
GAP_STATUS_PATTERN = re.compile(r"^\s*status:\s*(\w+)", re.IGNORECASE | re.MULTILINE)
TEST_PLAN_CATEGORIES = (
    "happy_path",
    "retry_idempotency",
    "missing_optional_fields",
    "pathological_inputs",
    "concurrent_access",
)


@dataclass
class LintReport:
    feature_id: str
    fe_path: Path | None = None
    be_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"Spec lint for {self.feature_id}:"]
        lines.append(f"  FE: {self.fe_path or '<not found>'}")
        lines.append(f"  BE: {self.be_path or '<not found>'}")
        if self.errors:
            lines.append(f"  ERRORS ({len(self.errors)}):")
            lines.extend(f"    - {e}" for e in self.errors)
        if self.warnings:
            lines.append(f"  WARNINGS ({len(self.warnings)}):")
            lines.extend(f"    - {w}" for w in self.warnings)
        if self.ok and not self.warnings:
            lines.append("  OK — spec ready for autopilot.")
        return "\n".join(lines)


def resolve_spec_paths(cfg: Config, feature_id: str) -> tuple[Path | None, Path | None]:
    """Best-effort match feature_id to FE + BE files.

    Strategy:
    1. Exact match: feature-<id>.md (id with or without F## prefix).
    2. Substring match: any feature-*.md whose stem contains the id (case-insensitive).
    """
    fe_dir = cfg.features_dir
    be_dir = cfg.be_features_dir
    fe = _find_spec_file(fe_dir, feature_id, suffix=".md", be=False)
    be = _find_spec_file(be_dir, feature_id, suffix="-tech.md", be=True)
    # If FE found, derive expected BE path even if not present yet.
    if fe and not be:
        derived_be = be_dir / f"{fe.stem}-tech.md"
        if derived_be.exists():
            be = derived_be
    return fe, be


def _find_spec_file(
    directory: Path,
    feature_id: str,
    *,
    suffix: str,
    be: bool,
) -> Path | None:
    if not directory.exists():
        return None
    needle = feature_id.lower().lstrip("f").lstrip("-").lstrip("0")
    candidates = sorted(directory.glob(f"feature-*{suffix}"))
    # 1. Exact match by stem ending or stem token.
    for path in candidates:
        stem = path.stem.lower()
        if stem.endswith(feature_id.lower()) or feature_id.lower() in stem.split("-"):
            return path
    # 2. Substring match on stem (looser; works for human aliases).
    for path in candidates:
        if needle and needle in path.stem.lower():
            return path
    # 3. Match via autopilot:meta block declared feature_id (FE only — BE
    #    derives from FE filename).
    if not be:
        for path in candidates:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m = META_BLOCK_PATTERN.search(content)
            if not m:
                continue
            decl = re.search(r"^\s*feature_id:\s*(\S+)", m.group(1), re.MULTILINE)
            if decl and decl.group(1).strip().lower() == feature_id.lower():
                return path
    return None


def lint(cfg: Config, feature_id: str) -> LintReport:
    """Run all lint rules. Returns ``LintReport`` (call ``.ok`` for boolean)."""
    report = LintReport(feature_id=feature_id)
    fe_path, be_path = resolve_spec_paths(cfg, feature_id)
    report.fe_path = fe_path
    report.be_path = be_path

    if fe_path is None:
        report.errors.append(
            f"FE spec not found for feature_id={feature_id!r} in {cfg.features_dir}",
        )
        return report

    fe_text = fe_path.read_text(encoding="utf-8")
    _check_sections(report, fe_text, REQUIRED_FE_SECTIONS, where="FE")
    _check_acceptance_count(report, fe_text)
    _check_no_open_todos(report, fe_text, where="FE")
    _check_meta_block(report, fe_text, fe_path, feature_id)
    _check_gaps_block(report, fe_text)
    _check_test_plan_block(report, fe_text)

    if be_path is None or not be_path.exists():
        report.errors.append(
            f"BE tech doc not found. Expected at {cfg.be_features_dir}/" f"{fe_path.stem}-tech.md",
        )
    else:
        be_text = be_path.read_text(encoding="utf-8")
        _check_sections(report, be_text, REQUIRED_BE_SECTIONS, where="BE")
        _check_no_open_todos(report, be_text, where="BE")

    return report


def _check_sections(
    report: LintReport,
    text: str,
    required: tuple[tuple[str, str], ...],
    *,
    where: str,
) -> None:
    headers = re.findall(r"^##\s+.+$", text, re.MULTILINE)
    headers_blob = "\n".join(headers)
    for needle, pretty in required:
        if needle.lower() not in headers_blob.lower():
            report.errors.append(f"{where}: missing required section {pretty!r}")


def _check_acceptance_count(report: LintReport, text: str) -> None:
    # Locate Acceptance Criteria section body.
    match = re.search(
        r"^##\s+(?:\d+\.\s*)?Acceptance Criteria\s*$(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return  # Section-missing error already raised by _check_sections.
    body = match.group(1)
    items = ACCEPTANCE_ITEM_PATTERN.findall(body)
    if len(items) < 3:
        report.errors.append(
            f"FE: Acceptance Criteria has {len(items)} items; require >=3",
        )


def _check_no_open_todos(report: LintReport, text: str, *, where: str) -> None:
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)
    for section in sections:
        first_line = section.split("\n", 1)[0]
        if not any(
            critical.lower() in first_line.lower() for critical in CRITICAL_SECTIONS_FOR_TODO_SCAN
        ):
            continue
        for marker in TODO_PATTERN.findall(section):
            report.errors.append(
                f"{where}: open marker {marker!r} found in section " f"{first_line.strip()!r}",
            )


def _check_meta_block(
    report: LintReport,
    text: str,
    path: Path,
    feature_id: str,
) -> None:
    match = META_BLOCK_PATTERN.search(text)
    if not match:
        report.warnings.append(
            "FE: no <!-- autopilot:meta --> block (optional but recommended; "
            "lets autopilot auto-derive branch + dependencies)",
        )
        return
    body = match.group(1)
    feature_id_match = re.search(r"^\s*feature_id:\s*(\S+)", body, re.MULTILINE)
    if feature_id_match:
        declared = feature_id_match.group(1).strip()
        if declared.lower() != feature_id.lower():
            report.warnings.append(
                f"FE: meta feature_id={declared!r} differs from CLI arg "
                f"feature_id={feature_id!r}",
            )


def _check_gaps_block(report: LintReport, text: str) -> None:
    match = GAPS_BLOCK_PATTERN.search(text)
    if not match:
        report.warnings.append(
            "FE: no <!-- autopilot:gaps --> block. Per Wave 0 lesson #2, "
            "lock all gap decisions BEFORE running autopilot.",
        )
        return
    body = match.group(1)
    statuses = [s.upper() for s in GAP_STATUS_PATTERN.findall(body)]
    open_count = sum(1 for s in statuses if s == "OPEN")
    if open_count:
        report.errors.append(
            f"FE: {open_count} OPEN gap(s) in autopilot:gaps block. "
            "Close (CLOSED) or DEFERRED before autopilot.",
        )


def _check_test_plan_block(report: LintReport, text: str) -> None:
    match = TEST_PLAN_BLOCK_PATTERN.search(text)
    if not match:
        report.warnings.append(
            "FE: no <!-- autopilot:test_plan --> block. Per Wave 0 lesson #4, "
            "5-category test plan upfront avoids Codex re-rounds.",
        )
        return
    body = match.group(1)
    for category in TEST_PLAN_CATEGORIES:
        if not re.search(rf"^\s*{re.escape(category)}\s*:", body, re.MULTILINE):
            report.errors.append(
                f"FE: test_plan missing category {category!r} (mark N/A with "
                "reason if not applicable)",
            )
