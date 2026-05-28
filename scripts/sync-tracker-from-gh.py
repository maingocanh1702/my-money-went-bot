#!/usr/bin/env python3
"""Sync docs/implementation-tracker.md status emojis with GitHub PR merge state.

For each tracker row whose Branch column matches a closed-merged PR's
`head.ref` on GitHub, flip the Status emoji to ✅ and append
`— Merged YYYY-MM-DD (#PR_num).` to the Notes column.

Idempotent: rows already marked ✅ or ⏸️ are skipped. Idempotent on Notes:
won't append if `Merged` substring is already present.

Designed to run in `.github/workflows/sync-tracker.yml` on
`pull_request: types: [closed]` events (filtered by `merged == true`).
Can also run locally with `gh auth login` for ad-hoc sync.

Usage:
    python scripts/sync-tracker-from-gh.py [--dry-run]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKER = ROOT / "docs" / "implementation-tracker.md"

# Emoji indicating "not yet merged" — only these get auto-flipped to ✅.
# ✅ already-merged and ⏸️ deferred are deliberately skipped.
FLIPPABLE_EMOJI = ("⬜", "🟡", "🟠", "🟢", "❌")


def fetch_merged_prs() -> list[dict]:
    """Get list of recently merged PRs from GitHub via `gh` CLI.

    Returns list of dicts with keys: number, headRefName, mergedAt, title.
    Empty list if `gh` is unavailable or returns no data.
    """
    try:
        out = subprocess.check_output(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "merged",
                "--limit",
                "200",
                "--json",
                "number,headRefName,mergedAt,title",
            ],
            text=True,
            cwd=ROOT,
            timeout=20,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(out) if out.strip() else []
        return data if isinstance(data, list) else []
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ):
        return []


def sync_tracker_text(text: str, prs: list[dict]) -> tuple[str, list[str]]:
    """Pure-function tracker sync: takes tracker text + PR list, returns (new_text, log).

    Separated from I/O so it's unit-testable without filesystem or network.
    """
    if not prs:
        return text, []

    pr_by_branch: dict[str, dict] = {p["headRefName"]: p for p in prs}
    log: list[str] = []

    lines = text.splitlines(keepends=False)
    new_lines: list[str] = []
    in_status_board = False

    for line in lines:
        # Section detect — only edit rows inside Status board (## 1.)
        if line.startswith("## 1. Status board"):
            in_status_board = True
        elif line.startswith("## ") and not line.startswith("## 1."):
            in_status_board = False

        if not in_status_board or not line.startswith("|"):
            new_lines.append(line)
            continue

        cells = line.split("|")
        # Expected: ['', pr_id, wave, feature, status, branch, gates, notes, '']
        if len(cells) < 9:
            new_lines.append(line)
            continue

        pr_id_cell = cells[1].strip()
        status_cell = cells[4]
        branch_cell = cells[5].strip().strip("`")
        notes_cell = cells[7]

        # Skip header + separator + empty rows
        if pr_id_cell in ("PR", "") or set(pr_id_cell) <= set("-: "):
            new_lines.append(line)
            continue

        # Skip terminal-state rows we don't want to override
        if "✅" in status_cell or "⏸️" in status_cell or "⏸" in status_cell:
            new_lines.append(line)
            continue

        pr_info = pr_by_branch.get(branch_cell)
        if pr_info is None:
            new_lines.append(line)
            continue

        # Find the first flippable emoji to replace
        old_emoji = next((e for e in FLIPPABLE_EMOJI if e in status_cell), None)
        if old_emoji is None:
            new_lines.append(line)
            continue

        merged_at = (pr_info.get("mergedAt") or "")[:10]  # YYYY-MM-DD
        pr_num = pr_info.get("number")
        if not merged_at or pr_num is None:
            new_lines.append(line)
            continue

        # Flip status emoji
        new_status_cell = status_cell.replace(old_emoji, "✅", 1)
        # Append merge note (idempotent — skip if already mentions Merged)
        if "Merged" in notes_cell:
            new_notes_cell = notes_cell
        else:
            stripped = notes_cell.rstrip(" \t")
            sep = " " if stripped.endswith(".") else ". "
            new_notes_cell = f"{stripped}{sep}Merged {merged_at} (#{pr_num}). "

        cells[4] = new_status_cell
        cells[7] = new_notes_cell
        new_lines.append("|".join(cells))

        log.append(
            f"{pr_id_cell:14s} {old_emoji}→✅  (#{pr_num}, merged {merged_at}, branch {branch_cell})"
        )

    new_text = "\n".join(new_lines)
    if text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, log


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if not TRACKER.exists():
        print(f"Tracker not found: {TRACKER}", file=sys.stderr)
        return 1

    text = TRACKER.read_text(encoding="utf-8")
    prs = fetch_merged_prs()
    if not prs:
        print("No merged PRs returned from `gh pr list` (or `gh` unavailable). Nothing to do.")
        return 0

    new_text, log = sync_tracker_text(text, prs)
    if not log:
        print("Tracker already in sync with GitHub merge state.")
        return 0

    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"{prefix}Updated {len(log)} tracker row{'s' if len(log) != 1 else ''}:")
    for entry in log:
        print(f"  {entry}")
    if not dry_run:
        TRACKER.write_text(new_text, encoding="utf-8")
        print(f"\nWrote {TRACKER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
