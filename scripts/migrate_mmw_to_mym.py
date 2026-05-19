#!/usr/bin/env python3
"""Migrate Linear team key MMW → MYM across MMW project files.

Per dashboard-plan-state-split.md v1.2.1 §10 (Phase 0 complete), Linear team
URL changed from `maingocanh1702/MMW` → `maingocanh/MYM`. This script migrates
Linear ticket references (MMW-NNN pattern) and convention refs ("project key MMW",
"Linear MMW") to the new team key.

CRITICAL distinction:
  - `MMW-<number>` = Linear ticket ID → migrate to MYM-<number>
  - `MMW` standalone = "MyMoneyWent" project abbreviation → KEEP

Usage:
    python scripts/migrate_mmw_to_mym.py --dry-run          # preview changes
    python scripts/migrate_mmw_to_mym.py --apply            # write changes
    python scripts/migrate_mmw_to_mym.py --apply --files docs/operations/  # scope

After successful run:
    git diff --stat   # review files changed
    git diff          # review actual changes
    git add -p        # stage selectively if needed
    git commit -m "refactor: migrate Linear team key MMW → MYM"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ============================================================================
# CONFIG
# ============================================================================

# Patterns to replace. Order matters — more specific patterns first.
# Each tuple: (regex_pattern, replacement, description)
REPLACEMENTS: list[tuple[str, str, str]] = [
    # Linear ticket IDs: MMW-108, MMW-203, MMW-NNN, MMW-XXX placeholders
    (r"\bMMW-(\d+)\b", r"MYM-\1", "Linear ticket ID (numeric)"),
    (r"\bMMW-NNN\b", r"MYM-NNN", "Linear ticket placeholder NNN"),
    (r"\bMMW-XXX\b", r"MYM-XXX", "Linear ticket placeholder XXX"),
    (r"MMW-<id>", r"MYM-<id>", "Linear ticket placeholder template"),
    (r"MMW-<NNN>", r"MYM-<NNN>", "Linear ticket placeholder NNN template"),
    # Convention references — "project key MMW", "Linear MMW issue"
    (r"\bproject key MMW\b", r"project key MYM", "Linear project key reference"),
    (r"\bLinear MMW issue\b", r"Linear MYM issue", "Linear issue convention reference"),
    (r"\bLinear key MMW\b", r"Linear key MYM", "Linear key reference"),
    (r"\bteam MMW\b", r"team MYM", "Linear team reference"),
    # URL references
    (r"linear\.app/maingocanh1702/MMW", r"linear.app/maingocanh/team/MYM", "Linear workspace URL"),
    (
        r"linear\.app/maingocanh/MMW",
        r"linear.app/maingocanh/team/MYM",
        "Linear workspace URL variant",
    ),
]

# Files to ALWAYS skip — these use MMW as project name abbreviation, not Linear key
SKIP_PATHS: list[str] = [
    "scripts/migrate_mmw_to_mym.py",  # self
    ".git/",
    ".venv/",
    "venv/",
    "env/",
    "node_modules/",
    "__pycache__/",
    ".dashboard/",
    ".autopilot/",
    "docs/research/",  # MMW = MyMoneyWent project abbreviation in research docs
    "docs/marketing/",  # marketing copy uses MMW = brand
]

# File extensions to process
INCLUDE_EXTENSIONS: tuple[str, ...] = (".md", ".yml", ".yaml", ".py", ".sql", ".toml")

# ============================================================================
# CORE LOGIC
# ============================================================================


def should_skip(path: Path, repo_root: Path) -> bool:
    """Check if file matches any skip pattern."""
    rel = path.relative_to(repo_root).as_posix()
    return any(rel.startswith(skip) or skip.rstrip("/") in rel.split("/") for skip in SKIP_PATHS)


def find_target_files(repo_root: Path, scope: Path | None = None) -> list[Path]:
    """Find candidate files within scope (or whole repo)."""
    base = scope if scope else repo_root
    files = []
    for ext in INCLUDE_EXTENSIONS:
        for p in base.rglob(f"*{ext}"):
            if p.is_file() and not should_skip(p, repo_root):
                files.append(p)
    return sorted(files)


def replace_in_text(text: str) -> tuple[str, list[tuple[str, int]]]:
    """Apply all replacements. Return (new_text, [(description, count), ...])."""
    stats = []
    for pattern, replacement, description in REPLACEMENTS:
        new_text, count = re.subn(pattern, replacement, text)
        if count > 0:
            stats.append((description, count))
            text = new_text
    return text, stats


def process_file(path: Path, dry_run: bool) -> tuple[int, list[tuple[str, int]]]:
    """Process single file. Return (total_changes, stats)."""
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"  SKIP (read error): {path} — {e}", file=sys.stderr)
        return 0, []

    new_text, stats = replace_in_text(original)
    total = sum(c for _, c in stats)

    if total == 0:
        return 0, []

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return total, stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    group.add_argument("--apply", action="store_true", help="Write changes to files")
    parser.add_argument(
        "--files", default=".", help="Scope: directory or single file (default: whole repo)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-file changes")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    scope = repo_root / args.files if args.files != "." else None
    if scope and not scope.exists():
        print(f"ERROR: scope path not found: {scope}", file=sys.stderr)
        return 1

    files = find_target_files(repo_root, scope)
    mode = "DRY-RUN" if args.dry_run else "APPLY"

    print(f"=== Linear team migration: MMW → MYM ({mode}) ===")
    print(f"Repo root: {repo_root}")
    print(f"Scope: {scope.relative_to(repo_root) if scope else '(whole repo)'}")
    print(f"Files scanned: {len(files)}")
    print(f"Skip patterns: {len(SKIP_PATHS)}")
    print()

    total_changes = 0
    files_changed = 0
    aggregate_stats: dict[str, int] = {}

    for f in files:
        count, stats = process_file(f, dry_run=args.dry_run)
        if count > 0:
            files_changed += 1
            total_changes += count
            for desc, n in stats:
                aggregate_stats[desc] = aggregate_stats.get(desc, 0) + n
            if args.verbose:
                rel = f.relative_to(repo_root)
                details = ", ".join(f"{desc}={n}" for desc, n in stats)
                print(f"  {rel}: {count} changes ({details})")

    print()
    print("=== Summary ===")
    print(f"Files changed: {files_changed}")
    print(f"Total replacements: {total_changes}")
    print()
    print("By pattern:")
    for desc, count in sorted(aggregate_stats.items(), key=lambda x: -x[1]):
        print(f"  {count:>5}  {desc}")

    if args.dry_run:
        print()
        print("DRY-RUN — no files modified. Run with --apply to write changes.")
    else:
        print()
        print("Applied. Next steps:")
        print("  git diff --stat   # review files changed")
        print("  git diff          # review actual changes")
        print("  git add -p        # stage selectively if needed")
        print("  git commit -m 'refactor: migrate Linear team key MMW → MYM'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
