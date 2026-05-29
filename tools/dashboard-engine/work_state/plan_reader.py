"""Tracker.md → WorkItem normalization per spec §11.2 + Phase 0 §2.2 defaults."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from work_state.models import WorkItem

_PHASE_HEADER_RE = re.compile(r"###\s+Phase\s+(\w+)")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
_STATUS_EMOJIS = {"⬜", "🟡", "🟠", "🟢", "✅", "❌", "⏸️"}
_GATE_FLAGS = {"🔒T", "🔒I", "🔒M", "🔒X"}


@dataclass
class ParsedWorkItem:
    item: WorkItem
    _warnings: list[str] = field(default_factory=list)

    def __getattr__(self, name: str) -> object:
        return getattr(self.item, name)


def _strip_cell(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _is_placeholder_row(pr_id: str) -> bool:
    lower = pr_id.lower()
    return "to be created" in lower or "tbd" in lower or pr_id.startswith("(")


def _infer_type(pr_id: str) -> tuple[str, bool]:
    """Infer type from id pattern. Returns (type, was_inferred)."""
    if re.match(r"^W\d+\.\d+$", pr_id):
        return "infra", True
    return "feature", True


def _infer_risk_tier(gates_str: str) -> tuple[str, bool]:
    """Infer risk tier from gate flags per Phase 0 §2.2."""
    gates = set(re.findall(r"🔒[TIMX]", gates_str))
    if gates >= {"🔒T", "🔒I", "🔒M", "🔒X"}:
        return "P0", True
    if gates >= {"🔒T", "🔒X"}:
        return "P1", True
    if "🔒X" in gates:
        return "P1", True
    return "P1", True


def _infer_lane(risk_tier: str) -> str:
    if risk_tier == "P0":
        return "Foundation"
    if risk_tier == "P1":
        return "Standard"
    return "Fast"


def _infer_progress_profile(pr_id: str, item_type: str) -> tuple[str, bool]:
    if re.match(r"^W\d+\.\d+$", pr_id):
        return "foundation_change", True
    if item_type == "feature":
        return "standard_feature", True
    return "standard_feature", True


def _extract_branch(branch_cell: str) -> list[str]:
    branch = _strip_cell(branch_cell)
    if not branch or branch == "—":
        return []
    return [branch]


def _parse_status_emoji(status_cell: str) -> str:
    cell = status_cell.strip()
    for emoji in _STATUS_EMOJIS:
        if emoji in cell:
            return emoji
    return "⬜"


def read_tracker(tracker_path: str) -> list[ParsedWorkItem]:
    """Read implementation-tracker.md and normalize rows into WorkItems."""
    path = Path(tracker_path)
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    current_phase = "0"
    items: list[ParsedWorkItem] = []
    in_table = False
    header_seen = False

    for line in lines:
        phase_match = _PHASE_HEADER_RE.search(line)
        if phase_match:
            raw_phase = phase_match.group(1)
            if raw_phase.isdigit():
                current_phase = raw_phase
            elif raw_phase in {"W", "T"}:
                current_phase = raw_phase
            else:
                current_phase = raw_phase
            in_table = False
            header_seen = False
            continue

        row_match = _TABLE_ROW_RE.match(line.strip())
        if not row_match:
            if in_table:
                in_table = False
                header_seen = False
            continue

        cells = [c.strip() for c in row_match.group(1).split("|")]

        if not in_table:
            if any(c.lower() in {"pr", "status", "feature"} for c in cells):
                in_table = True
                header_seen = False
                continue
            continue

        if not header_seen:
            if all(c.strip().replace("-", "").replace(":", "") == "" for c in cells):
                header_seen = True
                continue
            continue

        if len(cells) < 4:
            continue

        pr_id = _strip_cell(cells[0])
        if not pr_id or _is_placeholder_row(pr_id):
            continue

        feature_title = _strip_cell(cells[2]) if len(cells) > 2 else ""
        branch_cell = cells[4] if len(cells) > 4 else ""
        gates_cell = cells[5] if len(cells) > 5 else ""
        notes_cell = cells[6] if len(cells) > 6 else ""

        warnings: list[str] = []

        item_type, type_inferred = _infer_type(pr_id)
        if type_inferred:
            warnings.append("type_inferred")

        risk_tier, risk_inferred = _infer_risk_tier(gates_cell)
        if risk_inferred:
            warnings.append("risk_tier_inferred")

        lane = _infer_lane(risk_tier)

        progress_profile, profile_inferred = _infer_progress_profile(pr_id, item_type)
        if profile_inferred:
            warnings.append("progress_profile_inferred")

        warnings.append("priority_defaulted")

        branches = _extract_branch(branch_cell)
        has_branches = len(branches) > 0
        linear_id: str | None = None
        if has_branches and linear_id is None:
            warnings.append("missing_linear_id")

        acceptance: list[str] = []
        if notes_cell.strip():
            acceptance.append(notes_cell.strip())
            warnings.append("acceptance_unstructured")

        dependencies: list[str] = []
        dep_match = re.search(
            r"(?:depends on|blocks|unblock|DDL landed)\s+([\w.]+)", notes_cell, re.I
        )
        if dep_match:
            dependencies.append(dep_match.group(1))
        if notes_cell.strip() and not dep_match:
            pass
        if notes_cell.strip():
            warnings.append("dependencies_unstructured")

        specs: dict[str, str | None] = {"product": None, "tech": None}

        work_item = WorkItem(
            id=pr_id,
            linear_id=linear_id,
            feature_id=pr_id,
            title=feature_title if feature_title else pr_id,
            type=item_type,
            phase=current_phase,
            priority="P1",
            risk_tier=risk_tier,
            lane=lane,
            owner="founder",
            deadline=None,
            specs=specs,
            branches=branches,
            acceptance=acceptance,
            dependencies=dependencies,
            external_blockers=[],
            decision_needed=None,
            progress_profile=progress_profile,
        )

        items.append(ParsedWorkItem(item=work_item, _warnings=warnings))

    return items
