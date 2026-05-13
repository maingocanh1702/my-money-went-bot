#!/usr/bin/env python3
"""Build dashboard.html and dashboard.md from docs/implementation-tracker.md.

Source of truth is the tracker — this script just renders. Run after each
PR merge to refresh the dashboard views (per development-workflow.md §2.7
Post-merge updates).

Usage:
    python scripts/build-dashboard.py

Outputs:
    docs/dashboard.html  — visual HTML dashboard, open in browser
    docs/dashboard.md    — markdown view with Mermaid Gantt, renders on GitHub
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

# Allow running as a script (python scripts/build-dashboard.py) AND as a
# module under pytest: prepend repo root so `scripts.dashboard.*` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dashboard.build_json import build_dashboard_json  # noqa: E402
from scripts.dashboard.parse_docs import parse_doc_version_header  # noqa: E402
from scripts.dashboard.parse_roadmap import (  # noqa: E402
    parse_roadmap_blockers,
    parse_roadmap_features,
    parse_roadmap_overall_progress,
    parse_roadmap_risks,
)
from scripts.dashboard.render import (  # noqa: E402
    TAB_CSS,
    TAB_SWITCHER_JS,
    render_docs_tab,
    render_features_tab,
    render_overview_tab,
    render_prs_tab,
    render_risks_tab,
    render_tab_bar,
)

ROOT = Path(__file__).resolve().parents[1]
TRACKER = ROOT / "docs" / "implementation-tracker.md"
ROADMAP = ROOT / "docs" / "mymoneywent-roadmap.md"
HTML_OUT = ROOT / "docs" / "dashboard.html"
MD_OUT = ROOT / "docs" / "dashboard.md"
JSON_OUT = ROOT / "docs" / "dashboard.json"

# Canonical docs whose Version/Updated headers feed the staleness widget.
TRACKED_DOCS = [
    ROOT / "docs" / "brd-vi.md",
    ROOT / "docs" / "prd-vi.md",
    ROOT / "docs" / "tdd-vi.md",
    ROOT / "docs" / "mymoneywent-roadmap.md",
]


# Status emoji → (label, css/slug)
STATUS_MAP = {
    "✅": ("Merged", "merged"),
    "🟢": ("Ready to merge", "ready"),
    "🟠": ("In review", "in-review"),
    "🟡": ("In progress", "in-progress"),
    "❌": ("Blocked", "blocked"),
    "⏸️": ("Deferred", "deferred"),
    "⏸": ("Deferred", "deferred"),
    "⬜": ("Not started", "not-started"),
}

IN_FLIGHT_STATUSES = {"in-review", "in-progress", "ready"}
ACTIVE_STATUSES = IN_FLIGHT_STATUSES | {"blocked"}

# Approx phase windows for Mermaid Gantt (mirror roadmap §3 timeline)
PHASE_DATES = {
    "Phase 1": ("2026-05-05", "2026-05-22"),
    "Phase 2": ("2026-05-22", "2026-06-15"),
    "Phase 3": ("2026-06-15", "2026-06-25"),
    "Phase 4": ("2026-06-25", "2026-07-10"),
    "Phase 5": ("2026-07-10", "2026-08-10"),
    "Phase 6": ("2026-08-10", "2026-09-15"),
}


@dataclass
class PR:
    pr_id: str
    wave: str
    feature: str
    status_emoji: str
    status_label: str
    status_slug: str
    branch: str
    gates: str
    notes: str
    phase: str
    # Populated by enrich_with_git_state — None means git couldn't determine.
    local_slug: str | None = None
    remote_slug: str | None = None
    unpushed: int = 0  # commits on local branch not on origin/<branch>
    unpulled: int = 0  # commits on origin/<branch> not in local branch


@dataclass
class PhaseStats:
    key: str  # "Phase 1"
    label: str  # raw label from table
    total: int
    merged: int
    in_progress: int
    blocked: int
    deferred: int
    percent: int


# ---------- parsing ----------


def parse_prs(text: str) -> list[PR]:
    out: list[PR] = []
    phase_re = re.compile(r"^### (Phase \d+):", re.MULTILINE)
    matches = list(phase_re.finditer(text))
    for i, m in enumerate(matches):
        phase = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.extend(_parse_phase_block(phase, text[start:end]))
    return out


def _parse_phase_block(phase: str, block: str) -> list[PR]:
    rows: list[PR] = []
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        if cells[0] in ("PR", ""):
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        emoji = _find_emoji(cells[3])
        if not emoji:
            continue
        label, slug = STATUS_MAP[emoji]
        rows.append(
            PR(
                pr_id=cells[0],
                wave=cells[1],
                feature=cells[2],
                status_emoji=emoji,
                status_label=label,
                status_slug=slug,
                branch=cells[4].strip("`"),
                gates=cells[5],
                notes=cells[6] if len(cells) > 6 else "",
                phase=phase,
            )
        )
    return rows


def _find_emoji(cell: str) -> str | None:
    for e in STATUS_MAP:
        if e in cell:
            return e
    return None


def _strip_id_prefix(feature: str, pr_id: str) -> str:
    """Strip `F07 — ` or `F07 -` prefix from feature when it duplicates pr_id."""
    for sep in (" — ", " - ", "—", "-"):
        candidate = f"{pr_id}{sep}"
        if feature.startswith(candidate):
            return feature[len(candidate) :].strip()
    return feature


def parse_summary(text: str) -> list[PhaseStats]:
    out: list[PhaseStats] = []
    m = re.search(r"^##\s+5\.\s*Progress summary", text, re.MULTILINE)
    if not m:
        return out
    rest = text[m.end() :]
    end = re.search(r"^##\s+", rest, re.MULTILINE)
    block = rest[: end.start()] if end else rest
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7 or cells[0].lower() == "phase":
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        label = cells[0].replace("**", "").strip()
        if "mvp total" in label.lower():
            continue
        try:
            total = _first_int(cells[1])
            merged = _first_int(cells[2])
            in_prog = _first_int(cells[3])
            blocked = _first_int(cells[4])
            deferred = _first_int(cells[5])
            pct = _first_int(cells[6])
        except ValueError:
            continue
        if total == 0 and merged == 0 and pct == 0:
            # Skip meta-rows like "5b (post-launch)" which use "—" placeholders.
            continue
        key = f"Phase {label.split()[0]}"
        out.append(
            PhaseStats(
                key=key,
                label=label,
                total=total,
                merged=merged,
                in_progress=in_prog,
                blocked=blocked,
                deferred=deferred,
                percent=pct,
            )
        )
    return out


def parse_mvp_total(text: str) -> dict | None:
    for line in text.splitlines():
        if "MVP total" in line and line.startswith("|"):
            cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
            try:
                return {
                    "total": _first_int(cells[1]),
                    "merged": _first_int(cells[2]),
                    "in_progress": _first_int(cells[3]),
                    "blocked": _first_int(cells[4]),
                    "deferred": _first_int(cells[5]),
                    "percent": _first_int(cells[6]),
                }
            except (ValueError, IndexError):
                return None
    return None


def _first_int(cell: str) -> int:
    m = re.search(r"\d+", cell)
    if not m:
        if "—" in cell or cell.lower() in ("n/a", "—", ""):
            return 0
        raise ValueError(cell)
    return int(m.group(0))


def current_branch() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out or None
    except Exception:
        return None


# ---------- git-state detection (local + remote tracked separately) ----------

_TERMINAL_TRACKER_STATES = {"merged", "deferred", "blocked", "ready"}
_GIT_RANK = {"not-started": 0, "in-progress": 1, "in-review": 2}


def _detect_repo_slug() -> str | None:
    """Parse `git remote get-url origin` → `owner/repo` slug.

    Returns None if not a git repo, no origin, or non-GitHub URL. Used by the
    live-poll JS to know which repo to query against the GitHub API.
    """
    rc, out = _git("remote", "get-url", "origin")
    if rc != 0 or not out:
        return None
    # Handle both SSH (git@github.com:owner/repo.git) and HTTPS (https://github.com/owner/repo[.git])
    url = out.strip()
    if url.startswith("git@github.com:"):
        slug = url.split(":", 1)[1]
    elif "github.com/" in url:
        slug = url.split("github.com/", 1)[1]
    else:
        return None
    if slug.endswith(".git"):
        slug = slug[:-4]
    # Sanity check shape `owner/repo`
    parts = slug.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return slug


def _git(*args: str) -> tuple[int, str]:
    """Run git command, return (returncode, stdout). Never raises."""
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode, r.stdout.strip()
    except Exception:
        return 1, ""


def _branch_exists(ref: str) -> bool:
    rc, _ = _git("rev-parse", "--verify", "--quiet", ref)
    return rc == 0


def _status_from_commits(ahead: int, has_fix: bool) -> str:
    """Map (commit count, has fix commits) → status slug."""
    if ahead == 0:
        return "not-started"
    if ahead >= 3 and has_fix:
        return "in-review"
    return "in-progress"


def _detect_from_ref(ref: str, base: str) -> tuple[str | None, str]:
    """Infer status from commits on `ref` ahead of `base`. Both must exist."""
    if not _branch_exists(ref) or not _branch_exists(base):
        return None, ""
    rc, count_str = _git("rev-list", "--count", f"{base}..{ref}")
    ahead = int(count_str) if count_str.isdigit() else 0
    rc, fix_out = _git("log", "--oneline", "--grep=^fix", f"{base}..{ref}")
    has_fix = bool(fix_out) and rc == 0
    slug = _status_from_commits(ahead, has_fix)
    label_fix = " + fix() commits (Codex round)" if has_fix and ahead >= 3 else ""
    reason = f"{ahead} commits ahead{label_fix}" if ahead else "branch present, 0 commits"
    return slug, reason


def detect_local_state(branch: str, pr_id: str) -> tuple[str | None, str]:
    """Status inferred from local branch refs only. (None, '') if branch missing locally."""
    if not branch or not _branch_exists(branch):
        return None, ""
    return _detect_from_ref(branch, "main")


def detect_remote_state(branch: str, pr_id: str) -> tuple[str | None, str]:
    """Status inferred from origin/* refs only. (None, '') if not pushed.

    Uses origin/main as base — what's actually on remote, not what user has locally.
    """
    if not branch or not _branch_exists(f"origin/{branch}"):
        return None, ""
    base = "origin/main" if _branch_exists("origin/main") else "main"
    return _detect_from_ref(f"origin/{branch}", base)


def detect_sync(branch: str) -> tuple[int, int]:
    """Return (unpushed_commits, unpulled_commits) for branch.

    - unpushed = commits on local branch not yet on origin/<branch>
    - unpulled = commits on origin/<branch> not yet in local branch
    - If only one side exists, count all commits on that side relative to main.
    - If neither side exists → (0, 0).
    """
    if not branch:
        return 0, 0
    local = _branch_exists(branch)
    remote = _branch_exists(f"origin/{branch}")
    if not local and not remote:
        return 0, 0
    if local and not remote:
        # All local commits are unpushed
        rc, c = _git("rev-list", "--count", f"main..{branch}")
        return (int(c) if c.isdigit() else 0, 0)
    if remote and not local:
        # All remote commits are "unpulled" (nothing local to compare)
        base = "origin/main" if _branch_exists("origin/main") else "main"
        rc, c = _git("rev-list", "--count", f"{base}..origin/{branch}")
        return (0, int(c) if c.isdigit() else 0)
    # Both exist
    rc, c1 = _git("rev-list", "--count", f"origin/{branch}..{branch}")
    rc, c2 = _git("rev-list", "--count", f"{branch}..origin/{branch}")
    return (
        int(c1) if c1.isdigit() else 0,
        int(c2) if c2.isdigit() else 0,
    )


def _pick_higher(slug_a: str | None, slug_b: str | None) -> str | None:
    """Pick whichever slug ranks higher in _GIT_RANK; None falls through."""
    if slug_a is None:
        return slug_b
    if slug_b is None:
        return slug_a
    return slug_a if _GIT_RANK.get(slug_a, 0) >= _GIT_RANK.get(slug_b, 0) else slug_b


def detect_git_state(branch: str, pr_id: str) -> tuple[str | None, str]:
    """Combined local+remote detection — kept for backward compat with tests.

    Returns the higher-ranked of local vs remote, with reason indicating source.
    """
    l_slug, l_reason = detect_local_state(branch, pr_id)
    r_slug, r_reason = detect_remote_state(branch, pr_id)
    picked = _pick_higher(l_slug, r_slug)
    if picked is None:
        return None, ""
    if picked == l_slug and l_slug == r_slug:
        return picked, f"local+remote: {l_reason}"
    if picked == l_slug:
        return picked, f"local: {l_reason}"
    return picked, f"remote: {r_reason}"


def reconcile_status(tracker_slug: str, git_slug: str | None) -> str:
    """Pick the slug that best reflects reality.

    Rules:
      - Tracker terminal states (merged / deferred / blocked / ready) always win
        — these are founder-set decisions, git cannot override them.
      - If git can't determine state → keep tracker.
      - Otherwise: pick the higher-ranked slug in _GIT_RANK (in-review > in-progress
        > not-started). Tracker wins ties — founder-set in-review beats git's
        in-progress heuristic.
    """
    if tracker_slug in _TERMINAL_TRACKER_STATES:
        return tracker_slug
    if git_slug is None:
        return tracker_slug
    t_rank = _GIT_RANK.get(tracker_slug, 0)
    g_rank = _GIT_RANK.get(git_slug, 0)
    return tracker_slug if t_rank >= g_rank else git_slug


def enrich_with_git_state(prs: list[PR]) -> list[tuple[str, str, str, str]]:
    """Mutate prs to reflect git reality. Return drift report rows.

    Each PR gets local_slug, remote_slug, unpushed, unpulled populated.
    Primary status_slug = reconcile(tracker, max(local, remote)).

    Drift row: (pr_id, old_slug, new_slug, reason).
    """
    drift: list[tuple[str, str, str, str]] = []
    label_lookup = {slug: label for label, slug in STATUS_MAP.values()}
    for pr in prs:
        l_slug, l_reason = detect_local_state(pr.branch, pr.pr_id)
        r_slug, r_reason = detect_remote_state(pr.branch, pr.pr_id)
        pr.local_slug = l_slug
        pr.remote_slug = r_slug
        pr.unpushed, pr.unpulled = detect_sync(pr.branch)

        # Pick whichever git side ranks higher for the reconcile input.
        git_slug = _pick_higher(l_slug, r_slug)
        new_slug = reconcile_status(pr.status_slug, git_slug)
        if new_slug != pr.status_slug:
            if git_slug == l_slug == r_slug:
                source = f"both: {l_reason}"
            elif git_slug == l_slug:
                source = f"local: {l_reason}"
            else:
                source = f"remote: {r_reason}"
            drift.append((pr.pr_id, pr.status_slug, new_slug, source))
            pr.status_slug = new_slug
            pr.status_label = label_lookup.get(new_slug, pr.status_label)
            # status_emoji stays as tracker's emoji — single source of truth
            # for emoji is the tracker file. Drift is surfaced via printed report.
    return drift


# ---------- rendering: HTML ----------

HTML_CSS = """
:root {
  --bg-page: #f6f4ef;
  --bg-surface: #ffffff;
  --bg-secondary: #f1efe8;
  --bg-hover: rgba(0,0,0,0.025);
  --bg-warning: #faeeda;
  --bg-info: #e6f1fb;
  --bg-success: #eaf3de;
  --bg-danger: #fcebeb;
  --text-primary: #1a1915;
  --text-secondary: #5f5e5a;
  --text-tertiary: #888780;
  --text-warning: #854f0b;
  --text-info: #185fa5;
  --text-success: #3b6d11;
  --text-danger: #a32d2d;
  --border-tertiary: rgba(0,0,0,0.10);
  --border-secondary: rgba(0,0,0,0.18);
  --radius-md: 8px;
  --radius-lg: 12px;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg-page: #1a1915;
    --bg-surface: #25241f;
    --bg-secondary: #2c2c2a;
    --bg-hover: rgba(255,255,255,0.04);
    --bg-warning: #412402;
    --bg-info: #042c53;
    --bg-success: #173404;
    --bg-danger: #501313;
    --text-primary: #f1efe8;
    --text-secondary: #b4b2a9;
    --text-tertiary: #888780;
    --text-warning: #faeeda;
    --text-info: #e6f1fb;
    --text-success: #eaf3de;
    --text-danger: #fcebeb;
    --border-tertiary: rgba(255,255,255,0.10);
    --border-secondary: rgba(255,255,255,0.22);
  }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 1.25rem 1rem 2rem; font-family: var(--font-sans); background: var(--bg-page); color: var(--text-primary); line-height: 1.4; }
.container { max-width: 1080px; margin: 0 auto; }
.page-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; margin-bottom: 1rem; }
h1 { font-size: 18px; font-weight: 500; margin: 0; }
.meta { font-size: 11px; color: var(--text-tertiary); margin: 0; font-family: var(--font-mono); }
.meta code { font-family: var(--font-mono); }
.head-meta { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.live-indicator { font-size: 11px; font-family: var(--font-mono); cursor: pointer; padding: 3px 9px; border-radius: 12px; user-select: none; border: 1px solid transparent; transition: filter 0.15s ease; }
.live-indicator.init { background: var(--bg-secondary); color: var(--text-tertiary); }
.live-indicator.ok { background: var(--bg-success); color: var(--text-success); border-color: rgba(59,109,17,0.2); }
.live-indicator.syncing { background: var(--bg-info); color: var(--text-info); border-color: rgba(24,95,165,0.2); }
.live-indicator.err { background: var(--bg-danger); color: var(--text-danger); border-color: rgba(163,45,45,0.2); }
.live-indicator.warn { background: var(--bg-warning); color: var(--text-warning); border-color: rgba(133,79,11,0.2); }
.live-indicator.paused { background: var(--bg-secondary); color: var(--text-secondary); }
.live-indicator:hover { filter: brightness(0.95); }
@keyframes live-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
.live-indicator.ok::before { content: "●"; margin-right: 4px; color: #3b6d11; animation: live-pulse 2s ease-in-out infinite; }

/* Status dots — shared visual language */
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; box-sizing: border-box; }
.dot.merged { background: #3b6d11; }
.dot.ready { background: #639922; }
.dot.in-review { background: #185fa5; }
.dot.in-progress { background: #ba7517; }
.dot.blocked { background: #a32d2d; }
.dot.deferred { background: var(--text-tertiary); opacity: 0.45; }
.dot.not-started { background: transparent; border: 1.5px solid var(--border-secondary); }

/* Hero strip — current PR + KPIs side by side */
.hero { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 2fr); gap: 10px; margin-bottom: 10px; }
.hero-current { background: var(--bg-surface); border: 0.5px solid var(--border-tertiary); border-radius: var(--radius-lg); padding: 12px 14px; display: flex; gap: 12px; align-items: center; min-height: 76px; }
.hero-current .dot { width: 14px; height: 14px; }
.hero-current .hero-text { min-width: 0; flex: 1; }
.hero-current .hero-label { font-size: 10px; color: var(--text-tertiary); margin: 0 0 3px; text-transform: uppercase; letter-spacing: 0.06em; }
.hero-current .hero-title { font-size: 15px; font-weight: 500; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hero-current .hero-sub { font-size: 11px; color: var(--text-secondary); margin: 3px 0 0; font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hero-current.empty .hero-title { color: var(--text-tertiary); }

.hero-kpis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; }
.kpi { background: var(--bg-surface); border: 0.5px solid var(--border-tertiary); border-radius: var(--radius-md); padding: 10px 8px; text-align: center; display: flex; flex-direction: column; justify-content: center; }
.kpi.alert { background: var(--bg-danger); border-color: var(--bg-danger); }
.kpi.alert .kpi-val { color: var(--text-danger); }
.kpi.alert .kpi-lbl { color: var(--text-danger); }
.kpi-val { font-size: 20px; font-weight: 500; margin: 0; line-height: 1.1; font-variant-numeric: tabular-nums; }
.kpi-lbl { font-size: 10px; color: var(--text-secondary); margin: 3px 0 0; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-sub { font-size: 10px; color: var(--text-tertiary); margin: 1px 0 0; }

/* Next-up chips strip */
.next-strip { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 14px; padding: 8px 12px; background: var(--bg-secondary); border-radius: var(--radius-md); }
.next-label { font-size: 10px; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; margin-right: 4px; }
.next-chip { background: var(--bg-surface); border: 0.5px solid var(--border-tertiary); border-radius: var(--radius-md); padding: 4px 10px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px; color: var(--text-primary); }
.next-chip .pr-id { font-family: var(--font-mono); color: var(--text-secondary); font-size: 11px; }

/* Phase kanban board */
.board { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.phase-card { background: var(--bg-surface); border: 0.5px solid var(--border-tertiary); border-radius: var(--radius-lg); padding: 12px 14px; display: flex; flex-direction: column; min-height: 0; }
.phase-card.active { border-color: var(--border-secondary); }
.phase-card-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.phase-card-name { font-size: 13px; font-weight: 500; margin: 0; }
.phase-card-meta { font-size: 11px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.phase-card-bar { background: var(--bg-secondary); height: 4px; border-radius: 999px; overflow: hidden; margin-bottom: 10px; }
.phase-card-bar > div { background: var(--text-info); height: 100%; transition: width 0.3s; }
.phase-card-bar > div.zero { background: var(--border-tertiary); width: 100% !important; opacity: 0.35; }
.phase-prs { display: flex; flex-direction: column; gap: 2px; }
.pr-row { display: grid; grid-template-columns: 12px 64px minmax(0, 1fr); gap: 8px; align-items: center; padding: 4px 6px; border-radius: 5px; font-size: 12px; line-height: 1.3; transition: background 0.1s; }
.pr-row:hover { background: var(--bg-hover); }
.pr-row.current { background: var(--bg-info); }
.pr-row.current .pr-id, .pr-row.current .pr-name { color: var(--text-info); }
.pr-row .pr-id { font-family: var(--font-mono); color: var(--text-secondary); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-row .pr-name { color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 5px; min-width: 0; }
.pr-row .pr-name-text { overflow: hidden; text-overflow: ellipsis; min-width: 0; flex: 1; }
.pr-row.deferred .pr-name, .pr-row.deferred .pr-id { color: var(--text-tertiary); }
.sync-badge { font-size: 10px; font-family: var(--font-mono); padding: 1px 5px; border-radius: 999px; flex-shrink: 0; line-height: 1.3; }
.sync-badge.unpushed { background: var(--bg-warning); color: var(--text-warning); }
.sync-badge.unpulled { background: var(--bg-info); color: var(--text-info); }

/* Risk callout */
.callout { padding: 10px 14px; border-radius: var(--radius-md); display: flex; gap: 10px; align-items: flex-start; font-size: 12px; margin-top: 14px; }
.callout.warn { background: var(--bg-warning); color: var(--text-warning); }
.callout strong { display: block; margin-bottom: 2px; font-weight: 500; }

/* Legend */
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 11px; color: var(--text-secondary); margin-top: 1rem; padding-top: 0.75rem; border-top: 0.5px solid var(--border-tertiary); align-items: center; }
.legend .item { display: inline-flex; align-items: center; gap: 5px; }

@media (max-width: 760px) {
  .hero { grid-template-columns: 1fr; }
  .hero-kpis { grid-template-columns: repeat(6, 1fr); }
}
@media (max-width: 540px) {
  .hero-kpis { grid-template-columns: repeat(3, 1fr); }
  .kpi-val { font-size: 18px; }
  .pr-row { grid-template-columns: 12px 56px minmax(0, 1fr); gap: 6px; }
  .sync-badge { font-size: 9px; padding: 1px 4px; }
}

/* === v3: animations + filter/search + chart === */
@keyframes fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
@keyframes ring-pulse {
  0% { box-shadow: 0 0 0 0 rgba(24, 95, 165, 0.4); }
  100% { box-shadow: 0 0 0 8px rgba(24, 95, 165, 0); }
}
.phase-card { animation: fade-in 0.3s ease-out; }
.phase-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06); transition: transform 0.2s, box-shadow 0.2s; }
.pr-row { cursor: pointer; transition: background 0.15s, transform 0.1s; }
.pr-row:hover { transform: translateX(2px); }
.pr-row.hidden { display: none; }
.sync-badge { animation: pulse 2s infinite; }
.dot.in-review { animation: ring-pulse 2s infinite; }
.toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.search-input {
  flex: 1; min-width: 180px; padding: 6px 10px; font-size: 13px;
  border: 0.5px solid var(--border-tertiary); border-radius: var(--radius-md);
  background: var(--bg-surface); color: var(--text-primary); font-family: var(--font-sans);
}
.search-input:focus { outline: none; border-color: var(--text-info); }
.filter-btn {
  padding: 5px 12px; font-size: 12px; cursor: pointer;
  border: 0.5px solid var(--border-tertiary); border-radius: var(--radius-md);
  background: var(--bg-surface); color: var(--text-secondary); font-family: var(--font-sans);
}
.filter-btn:hover { background: var(--bg-hover); }
.filter-btn.active { background: var(--text-info); color: white; border-color: var(--text-info); }
.chart-section {
  background: var(--bg-surface); border: 0.5px solid var(--border-tertiary);
  border-radius: var(--radius-lg); padding: 14px 16px; margin-bottom: 14px;
}
.chart-title { font-size: 11px; color: var(--text-tertiary); margin: 0 0 10px;
  text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;
}
.chart-section canvas { max-height: 140px; }
"""


# Phase 3 dashboard live-poll — browser-side JS that polls GitHub API every 30s for
# new commits affecting tracker/dashboard, then re-fetches docs/dashboard.html from
# raw.githubusercontent and swaps .container innerHTML (preserves scroll position).
# Click the live-indicator to force-refresh. Optional PAT in localStorage key
# `github_pat` for 5000/hr rate limit (vs 60/hr unauth).
HTML_LIVE_JS = """
(function() {
  var REPO = '__REPO__';
  var PAT = null;
  try { PAT = localStorage.getItem('github_pat'); } catch (e) { /* SecurityError in some sandboxes */ }
  var POLL_INTERVAL_MS = PAT ? 30000 : 120000;  // 30s authed (5000/hr), 2min unauth (30 req/hr, under 60/hr limit)
  // Polling docs/dashboard.html alone catches all updates: tracker.md changes
  // are downstream via the pre-commit build-dashboard hook (regen + auto-stage)
  // and the GH Action dashboard.yml workflow. Polling both paths would double
  // API calls (240/hr) and exceed the 60/hr unauth rate limit at 30s interval.
  // Edge case: tracker committed with `--no-verify` bypasses the hook and would
  // be missed — but that's user error, not a feature target.
  var TRACK_PATH = 'docs/dashboard.html';

  var lastKnownSha = null;
  var lastSyncAt = Date.now();
  var lastError = null;
  var paused = false;

  function getIndicator() { return document.getElementById('live-indicator'); }

  function fmtAge(ms) {
    var s = Math.floor(ms / 1000);
    if (s < 60) return s + 's';
    var m = Math.floor(s / 60);
    if (m < 60) return m + 'm';
    return Math.floor(m / 60) + 'h';
  }

  function setIndicator(state, message) {
    var el = getIndicator();
    if (!el) return;
    var age = fmtAge(Date.now() - lastSyncAt);
    if (state === 'live') {
      el.textContent = 'Live · last sync ' + age + ' ago';
      el.className = 'live-indicator ok';
      el.title = 'Polls GitHub every ' + (POLL_INTERVAL_MS/1000) + 's. Click to refresh now. Pause: Esc.';
    } else if (state === 'syncing') {
      el.textContent = '🔵 Syncing…';
      el.className = 'live-indicator syncing';
    } else if (state === 'error') {
      el.textContent = '🔴 ' + (message || 'sync error');
      el.className = 'live-indicator err';
      el.title = message || '';
    } else if (state === 'rate-limit') {
      el.textContent = '🟡 Rate limit · waiting (set localStorage.github_pat for 5000/hr)';
      el.className = 'live-indicator warn';
    } else if (state === 'paused') {
      el.textContent = '⏸ Paused (click to resume)';
      el.className = 'live-indicator paused';
    } else if (state === 'init') {
      el.textContent = '⚪ initializing…';
      el.className = 'live-indicator init';
    }
  }

  function authHeaders() {
    var h = { 'Accept': 'application/vnd.github.v3+json' };
    try {
      var pat = localStorage.getItem('github_pat');
      if (pat) h['Authorization'] = 'Bearer ' + pat;
    } catch (e) { /* SecurityError in some sandboxes */ }
    return h;
  }

  function fetchLatestSha() {
    var url = 'https://api.github.com/repos/' + REPO + '/commits?path=' + TRACK_PATH + '&per_page=1';
    return fetch(url, { headers: authHeaders() }).then(function(resp) {
      if (resp.status === 403) {
        var remaining = resp.headers.get('X-RateLimit-Remaining');
        if (remaining === '0') {
          setIndicator('rate-limit');
          return null;
        }
      }
      if (!resp.ok) throw new Error('GitHub API ' + resp.status);
      return resp.json();
    }).then(function(data) {
      if (!data || !data.length) return null;
      return data[0].sha;
    });
  }

  function refreshDashboardDOM() {
    setIndicator('syncing');
    var url = 'https://raw.githubusercontent.com/' + REPO + '/main/docs/dashboard.html?_t=' + Date.now();
    return fetch(url, { cache: 'no-store' }).then(function(resp) {
      if (!resp.ok) throw new Error('Fetch raw ' + resp.status);
      return resp.text();
    }).then(function(text) {
      var parser = new DOMParser();
      var newDoc = parser.parseFromString(text, 'text/html');
      var newContainer = newDoc.querySelector('.container');
      var oldContainer = document.querySelector('.container');
      if (newContainer && oldContainer) {
        var scrollY = window.scrollY;
        // Preserve our live-indicator element (template doesn't have current state)
        var indicator = oldContainer.querySelector('#live-indicator');
        var indicatorHtml = indicator ? indicator.outerHTML : '';
        // Script-safe swap: replaceChild + manual <script> re-execution.
        // Plain innerHTML drops <script> tags silently (browsers refuse to run
        // them when set via innerHTML), so any inline scripts shipped by v2
        // (tab switcher, charts) would not re-run after refresh. We deep-clone
        // the new container, replace the old one in-place, then re-create each
        // <script> element so the browser executes it.
        var clone = document.importNode(newContainer, true);
        oldContainer.parentNode.replaceChild(clone, oldContainer);
        var scripts = clone.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
          var oldScript = scripts[i];
          var newScript = document.createElement('script');
          for (var j = 0; j < oldScript.attributes.length; j++) {
            var attr = oldScript.attributes[j];
            newScript.setAttribute(attr.name, attr.value);
          }
          newScript.textContent = oldScript.textContent;
          oldScript.parentNode.replaceChild(newScript, oldScript);
        }
        // Re-inject indicator if new content doesn't already have it
        if (indicatorHtml && !clone.querySelector('#live-indicator')) {
          var meta = clone.querySelector('.head-meta') || clone.querySelector('.page-head');
          if (meta) meta.insertAdjacentHTML('afterbegin', indicatorHtml);
        }
        window.scrollTo(0, scrollY);
      }
    });
  }

  function check() {
    if (paused) return;
    fetchLatestSha().then(function(latestSha) {
      // null = fetchLatestSha already set a non-live state (rate-limit, etc).
      // Thread a sentinel through the promise chain so the next .then() does
      // NOT overwrite the warning with 'live'.
      if (latestSha === null) return 'skipped';
      if (lastKnownSha === null) {
        lastKnownSha = latestSha;
      } else if (latestSha !== lastKnownSha) {
        return refreshDashboardDOM().then(function() {
          lastKnownSha = latestSha;
        });
      }
    }).then(function(outcome) {
      if (outcome === 'skipped') return;  // preserve rate-limit indicator
      lastSyncAt = Date.now();
      lastError = null;
      if (!paused) setIndicator('live');
    }).catch(function(e) {
      lastError = e.message;
      setIndicator('error', e.message);
    });
  }


  // Update age text every second
  setInterval(function() {
    if (paused) { setIndicator('paused'); return; }
    if (lastError) setIndicator('error', lastError);
    else if (lastKnownSha !== null) setIndicator('live');
  }, 1000);

  // Poll loop
  setInterval(check, POLL_INTERVAL_MS);

  // Click indicator → toggle pause OR force refresh
  document.addEventListener('click', function(e) {
    var t = e.target.closest && e.target.closest('#live-indicator');
    if (!t) return;
    if (paused) { paused = false; check(); }
    else { check(); }
  });

  // Esc → toggle pause
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { paused = !paused; setIndicator(paused ? 'paused' : 'live'); }
  });

  // Initial state + first check
  setIndicator('init');
  check();
})();
"""


def render_html(
    prs,
    stats,
    mvp,
    active,
    in_flight,
    upcoming,
    branch,
    roadmap_data=None,
    doc_versions=None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    branch_tag = f" · <code>{html.escape(branch)}</code>" if branch else ""
    # Bind repo slug for live-poll JS. Detect via `git remote get-url origin` fallback to default.
    repo_slug = _detect_repo_slug() or "maingocanh1702/MyMoneyWent"
    live_js = HTML_LIVE_JS.replace("__REPO__", repo_slug)

    phase1 = next((s for s in stats if s.label.startswith("1")), None)
    p1_pct = phase1.percent if phase1 else 0
    mvp_pct = mvp["percent"] if mvp else 0
    mvp_merged = mvp["merged"] if mvp else 0
    mvp_total = mvp["total"] if mvp else 0
    blocked_count = sum(1 for p in prs if p.status_slug == "blocked")
    unpushed_prs = sum(1 for p in prs if p.unpushed > 0)
    unpulled_prs = sum(1 for p in prs if p.unpulled > 0)
    total_unpushed = sum(p.unpushed for p in prs)
    total_unpulled = sum(p.unpulled for p in prs)

    # --- Hero: current PR ---
    if in_flight:
        primary = in_flight[0]  # take the first in-flight (in-review > in-progress > ready)
        title = _strip_id_prefix(primary.feature, primary.pr_id)
        title = f"{primary.pr_id} · {title}"
        sub = f"{primary.status_label} · {primary.branch}"
        hero_current = f"""<div class="hero-current">
  <span class="dot {primary.status_slug}"></span>
  <div class="hero-text">
    <p class="hero-label">Đang làm</p>
    <p class="hero-title">{html.escape(title)}</p>
    <p class="hero-sub">{html.escape(sub)}</p>
  </div>
</div>"""
    else:
        hero_current = """<div class="hero-current empty">
  <span class="dot not-started"></span>
  <div class="hero-text">
    <p class="hero-label">Đang làm</p>
    <p class="hero-title">Không có PR active</p>
    <p class="hero-sub">Pick task từ Next strip phía dưới</p>
  </div>
</div>"""

    # --- Hero: 6 KPIs (MVP, Phase 1, In flight, Blocked, Unpushed, Unpulled) ---
    blocked_kpi_cls = "kpi alert" if blocked_count > 0 else "kpi"
    unpushed_kpi_cls = "kpi alert" if unpushed_prs > 0 else "kpi"
    hero_kpis = f"""<div class="hero-kpis">
  <div class="kpi"><p class="kpi-val">{mvp_pct}%</p><p class="kpi-lbl">MVP</p><p class="kpi-sub">{mvp_merged}/{mvp_total}</p></div>
  <div class="kpi"><p class="kpi-val">{p1_pct}%</p><p class="kpi-lbl">Phase 1</p><p class="kpi-sub">{phase1.merged if phase1 else 0}/{phase1.total if phase1 else 0}</p></div>
  <div class="kpi"><p class="kpi-val">{len(in_flight)}</p><p class="kpi-lbl">In flight</p></div>
  <div class="{blocked_kpi_cls}"><p class="kpi-val">{blocked_count}</p><p class="kpi-lbl">Blocked</p></div>
  <div class="{unpushed_kpi_cls}"><p class="kpi-val">↑{total_unpushed}</p><p class="kpi-lbl">Unpushed</p><p class="kpi-sub">{unpushed_prs} PR</p></div>
  <div class="kpi"><p class="kpi-val">↓{total_unpulled}</p><p class="kpi-lbl">Unpulled</p><p class="kpi-sub">{unpulled_prs} PR</p></div>
</div>"""

    # --- Next-up chips strip ---
    chips = []
    for pr in upcoming[:4]:
        feat = _strip_id_prefix(pr.feature, pr.pr_id)
        # truncate name to ~40 chars
        feat_short = feat if len(feat) <= 40 else feat[:38] + "…"
        chips.append(
            f"""<span class="next-chip">
  <span class="dot not-started"></span>
  <span class="pr-id">{html.escape(pr.pr_id)}</span>
  {html.escape(feat_short)}
</span>"""
        )
    next_strip = f"""<div class="next-strip">
  <span class="next-label">Next</span>
  {''.join(chips) if chips else '<span style="font-size:12px;color:var(--text-tertiary);">Hết PR not-started.</span>'}
</div>"""

    # --- Phase kanban board ---
    by_phase: dict[str, list[PR]] = {}
    for p in prs:
        by_phase.setdefault(p.phase, []).append(p)

    # Sort PRs within each phase: active first, then not-started, then deferred, then merged
    sort_order = {
        "in-review": 0,
        "in-progress": 1,
        "ready": 2,
        "blocked": 3,
        "not-started": 4,
        "deferred": 5,
        "merged": 6,
    }

    phase_cards = []
    for s in stats:
        phase_prs = sorted(
            by_phase.get(s.key, []),
            key=lambda p: (sort_order.get(p.status_slug, 99), p.pr_id),
        )
        has_active = any(p.status_slug in ACTIVE_STATUSES for p in phase_prs)
        active_cls = " active" if has_active else ""
        zero_class = "zero" if s.percent == 0 else ""
        width = f"{min(s.percent, 100)}%"

        pr_rows = []
        for pr in phase_prs:
            feat = _strip_id_prefix(pr.feature, pr.pr_id)
            on_branch = branch and pr.branch == branch
            row_cls = f"pr-row {pr.status_slug}"
            if on_branch:
                row_cls += " current"

            sync_badges = ""
            if pr.unpushed > 0:
                sync_badges += f'<span class="sync-badge unpushed" title="{pr.unpushed} commits chưa push lên origin">↑{pr.unpushed}</span>'
            if pr.unpulled > 0:
                sync_badges += f'<span class="sync-badge unpulled" title="{pr.unpulled} commits trên origin chưa pull về local">↓{pr.unpulled}</span>'

            tooltip_parts = [pr.status_label, pr.branch]
            if pr.local_slug:
                tooltip_parts.append(f"local: {pr.local_slug}")
            if pr.remote_slug:
                tooltip_parts.append(f"remote: {pr.remote_slug}")
            tooltip = " · ".join(tooltip_parts)

            pr_rows.append(
                f"""<div class="{row_cls}" title="{html.escape(tooltip)}">
  <span class="dot {pr.status_slug}"></span>
  <span class="pr-id">{html.escape(pr.pr_id)}</span>
  <span class="pr-name"><span class="pr-name-text">{html.escape(feat)}</span>{sync_badges}</span>
</div>"""
            )
        rows_html = (
            "".join(pr_rows)
            if pr_rows
            else '<div style="font-size:11px;color:var(--text-tertiary);padding:4px 6px;">(no PRs)</div>'
        )

        phase_cards.append(
            f"""<div class="phase-card{active_cls}">
  <div class="phase-card-head">
    <p class="phase-card-name">{html.escape(s.key)}</p>
    <span class="phase-card-meta">{s.merged}/{s.total} · {s.percent}%</span>
  </div>
  <div class="phase-card-bar"><div class="{zero_class}" style="width:{width};"></div></div>
  <div class="phase-prs">{rows_html}</div>
</div>"""
        )

    board_html = f'<div class="board">\n{"".join(phase_cards)}\n</div>'

    # --- v3: Chart data ---
    import datetime as _dt

    phase_start = _dt.date(2026, 5, 5)
    phase_launch = _dt.date(2026, 9, 15)
    today = _dt.date.today()
    days_total = (phase_launch - phase_start).days
    days_elapsed = max(0, min(days_total, (today - phase_start).days))
    target_pct = round(days_elapsed / days_total * 100, 1) if days_total > 0 else 0.0
    actual_pct_chart = mvp_pct

    chart_section = f"""<div class="chart-section">
  <p class="chart-title">MVP progress vs target ({days_elapsed}/{days_total} days elapsed · launch T9/2026)</p>
  <canvas id="burndown" role="img" aria-label="Line chart comparing actual MVP completion to target trajectory"></canvas>
</div>"""

    # --- v3: Filter + search toolbar ---
    toolbar_html = """<div class="toolbar">
  <input type="search" id="dashboard-search" class="search-input" placeholder="🔍 Search PR by ID or name...">
  <button class="filter-btn active" data-filter="all">All</button>
  <button class="filter-btn" data-filter="in-review">In review</button>
  <button class="filter-btn" data-filter="in-progress">In progress</button>
  <button class="filter-btn" data-filter="blocked">Blocked</button>
  <button class="filter-btn" data-filter="not-started">Not started</button>
</div>"""

    # --- v3: JS — Chart.js + filter/search + click-through ---
    js_snippet = f"""<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
<script>
const REPO = "maingocanh1702/MyMoneyWent";

// Burndown chart
const ctx = document.getElementById("burndown");
if (ctx && window.Chart) {{
  new Chart(ctx, {{
    type: "line",
    data: {{
      labels: ["Start", "Today", "Launch"],
      datasets: [
        {{
          label: "Actual",
          data: [0, {actual_pct_chart}, null],
          borderColor: "#185fa5",
          backgroundColor: "rgba(24,95,165,0.1)",
          tension: 0.3,
          pointRadius: 5,
          fill: false,
        }},
        {{
          label: "Target",
          data: [0, {target_pct}, 100],
          borderColor: "#888780",
          borderDash: [5, 5],
          tension: 0,
          pointRadius: 3,
          fill: false,
        }},
      ],
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      scales: {{
        y: {{ beginAtZero: true, max: 100, ticks: {{ callback: v => v + "%", font: {{ size: 10 }} }} }},
        x: {{ ticks: {{ font: {{ size: 10 }} }} }},
      }},
      plugins: {{
        legend: {{ position: "bottom", labels: {{ font: {{ size: 11 }}, boxWidth: 12, padding: 8 }} }},
      }},
    }},
  }});
}}

// Filter + search
let activeFilter = "all";
let searchQuery = "";
const searchInput = document.getElementById("dashboard-search");
const filterBtns = document.querySelectorAll(".filter-btn");

function applyFilters() {{
  document.querySelectorAll(".pr-row").forEach(row => {{
    const matchesFilter = activeFilter === "all" || row.classList.contains(activeFilter);
    const matchesSearch = !searchQuery || row.textContent.toLowerCase().includes(searchQuery);
    row.classList.toggle("hidden", !(matchesFilter && matchesSearch));
  }});
  document.querySelectorAll(".phase-card").forEach(card => {{
    const visiblePRs = card.querySelectorAll(".pr-row:not(.hidden)").length;
    card.style.display = visiblePRs === 0 && (activeFilter !== "all" || searchQuery) ? "none" : "";
  }});
}}

if (searchInput) {{
  searchInput.addEventListener("input", e => {{ searchQuery = e.target.value.toLowerCase(); applyFilters(); }});
}}
filterBtns.forEach(btn => btn.addEventListener("click", () => {{
  filterBtns.forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  activeFilter = btn.dataset.filter;
  applyFilters();
}}));

// Click PR → open GitHub branch
document.querySelectorAll(".pr-row").forEach(row => {{
  const m = row.title.match(/(?:feat|infra|chore|fix)\\/[\\w.-]+/);
  if (m) {{
    row.addEventListener("click", () => window.open(`https://github.com/${{REPO}}/tree/${{m[0]}}`, "_blank"));
  }}
}});
document.querySelectorAll(".next-chip").forEach(chip => {{
  chip.style.cursor = "pointer";
  chip.addEventListener("click", () => {{
    const id = chip.querySelector(".pr-id")?.textContent;
    if (id) window.open(`https://github.com/${{REPO}}/issues?q=${{id}}`, "_blank");
  }});
}});
</script>"""

    # B-2: 5-tab UI. Overview wraps the legacy hero+chart+next strip; PRs
    # wraps the legacy toolbar+board; Features/Risks/Docs are new and draw
    # from B-1 roadmap parser output.
    rd = roadmap_data or {
        "overall": {"overall_progress": 0, "mvp_percent": mvp_pct, "phases": []},
        "features": [],
        "risks": [],
    }
    overall = rd.get("overall") or {}
    # Backfill mvp_percent so the Overview KPI matches the legacy hero.
    overall = {**overall, "mvp_percent": mvp_pct}
    legacy_overview_inner = f"""<div class="hero">
{hero_current}
{hero_kpis}
</div>
{chart_section}
{next_strip}"""
    overview_tab = render_overview_tab(overall, overall.get("phases", []), legacy_overview_inner)
    features_tab = render_features_tab(rd.get("features", []))
    prs_tab = render_prs_tab(f"{toolbar_html}\n{board_html}")
    risks_tab = render_risks_tab(rd.get("risks", []))
    docs_tab = render_docs_tab(doc_versions or [])
    tab_bar = render_tab_bar()

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>MyMoneyWent — progress dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<style>{HTML_CSS}
{TAB_CSS}</style>
</head>
<body>
<div class="container">

<div class="page-head">
  <h1>MyMoneyWent — progress dashboard</h1>
  <div class="head-meta">
    <span id="live-indicator" class="live-indicator init">⚪ initializing…</span>
    <p class="meta">Updated {now}{branch_tag} · auto-refresh 60s</p>
  </div>
</div>

{tab_bar}

{overview_tab}
{features_tab}
{prs_tab}
{risks_tab}
{docs_tab}

<div class="callout warn">
  <div>
    <strong>Risk còn active</strong>
    Legacy handler migration drag (F02 strangler fig) · F06 Family Plan addendum chờ merge · Meta App Review pages_messaging (F13 flip ON pending)
  </div>
</div>

<div class="legend">
  <span class="item"><span class="dot merged"></span> Merged</span>
  <span class="item"><span class="dot in-review"></span> In review</span>
  <span class="item"><span class="dot in-progress"></span> In progress</span>
  <span class="item"><span class="dot blocked"></span> Blocked</span>
  <span class="item"><span class="dot not-started"></span> Not started</span>
  <span class="item"><span class="dot deferred"></span> Deferred</span>
  <span class="item" style="margin-left:auto;color:var(--text-tertiary);">Click PR → GitHub · Rebuild: <code>python scripts/build-dashboard.py</code></span>
</div>

<!-- B-2: tab switcher INSIDE .container so refreshDashboardDOM() re-runs it
     after live refresh. A-P1-4 re-creates <script> nodes within the
     replaced container; scripts outside it would be orphaned after the
     first auto-refresh (Codex round 2). -->
<script class="tab-switcher">{TAB_SWITCHER_JS}</script>

</div>
<script>{live_js}</script>
{js_snippet}
</body>
</html>
"""


# ---------- rendering: Markdown ----------


def render_md(prs, stats, mvp, active, in_flight, upcoming, branch) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        "# MyMoneyWent — Progress Dashboard",
        "",
        "> **Auto-generated** từ [`implementation-tracker.md`](implementation-tracker.md) bằng `scripts/build-dashboard.py`.",
        "> KHÔNG edit trực tiếp — sửa tracker rồi rebuild.",
        f"> **Cập nhật:** {now}" + (f" · **Branch hiện tại:** `{branch}`" if branch else ""),
        "",
        "Để xem dashboard HTML đẹp hơn: mở [`dashboard.html`](dashboard.html) bằng browser.",
        "",
        "---",
        "",
        "## Tổng quan",
        "",
    ]
    if mvp:
        lines += [
            f"- **MVP progress:** **{mvp['percent']}%** ({mvp['merged']}/{mvp['total']} PR merged)",
            f"- **In flight:** {len(in_flight)} PR · **Blocked:** {mvp['blocked']} · **Deferred:** {mvp['deferred']}",
            "- **Target launch:** Tháng 9/2026 (~16 weeks runway)",
            "",
        ]

    # Phase summary table với ASCII bar
    lines += [
        "## Phase progress",
        "",
        "| Phase | Merged / Total | % | Progress |",
        "|-------|:--------------:|:-:|:---------|",
    ]
    for s in stats:
        filled = s.percent // 10
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"| {s.key} | {s.merged} / {s.total} | {s.percent}% | `{bar}` |")
    lines.append("")

    # Per-phase breakdown — each phase with its PRs
    lines += ["## Phase breakdown — features & tasks", ""]
    by_phase: dict[str, list[PR]] = {}
    for p in prs:
        by_phase.setdefault(p.phase, []).append(p)
    for s in stats:
        phase_prs = by_phase.get(s.key, [])
        filled = s.percent // 10
        bar = "█" * filled + "░" * (10 - filled)
        lines += [
            f"### {s.key} — {s.merged}/{s.total} · {s.percent}% `{bar}`",
            "",
        ]
        if not phase_prs:
            lines += ["_(no PRs in this phase)_", ""]
            continue
        lines += [
            "| PR | Feature | Status | Branch |",
            "|----|---------|:------:|--------|",
        ]
        for pr in phase_prs:
            feat = _strip_id_prefix(pr.feature, pr.pr_id)
            branch_cell = f"`{pr.branch}`" if pr.branch else "—"
            lines.append(
                f"| `{pr.pr_id}` | {feat} | {pr.status_emoji} {pr.status_label} | {branch_cell} |"
            )
        lines.append("")

    # Mermaid Gantt
    lines += [
        "## Timeline",
        "",
        "```mermaid",
        "gantt",
        "    title MyMoneyWent roadmap",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %b",
    ]
    for phase, (start, end) in PHASE_DATES.items():
        s_obj = next((s for s in stats if s.key == phase), None)
        if not s_obj:
            continue
        if s_obj.percent >= 100:
            tag = "done, "
        elif s_obj.merged > 0 or any(
            p.status_slug in ACTIVE_STATUSES for p in prs if p.phase == phase
        ):
            tag = "active, "
        else:
            tag = ""
        label = phase.replace("Phase ", "P")
        lines.append(f"    section {phase}")
        lines.append(f"    {label} ({s_obj.percent}%) : {tag}{start}, {end}")
    lines += ["```", ""]

    # Current focus
    lines += ["## Đang làm", ""]
    if active:
        for pr in active:
            on_branch = branch and pr.branch == branch
            marker = " · 🌿 đang trên branch này" if on_branch else ""
            title = pr.feature if pr.feature.startswith(pr.pr_id) else f"{pr.pr_id} — {pr.feature}"
            lines += [
                f"### {title}",
                "",
                f"- **Status:** {pr.status_emoji} {pr.status_label}{marker}",
                f"- **Branch:** `{pr.branch}`",
                f"- **Wave:** {pr.wave}",
                f"- **Gates:** {pr.gates}",
                f"- **Phase:** {pr.phase}",
                f"- **Notes:** {pr.notes}",
                "",
            ]
    else:
        lines += ["_Không có PR active._", ""]

    # Up next
    lines += [
        "## Up next",
        "",
        "| PR | Feature | Phase | Status |",
        "|----|---------|-------|--------|",
    ]
    for pr in upcoming:
        lines.append(
            f"| `{pr.pr_id}` | {pr.feature} | {pr.phase} | {pr.status_emoji} {pr.status_label} |"
        )
    lines.append("")

    lines += [
        "---",
        "",
        "**Rebuild:** chạy `python scripts/build-dashboard.py` sau mỗi PR merge (theo Step 10 của [development-workflow.md](operations/development-workflow.md) §2.7 Post-merge updates).",
        "",
    ]
    return "\n".join(lines)


# ---------- main ----------


def _collect_roadmap_data() -> dict:
    """Parse roadmap §1/§2/§6/§7 — empty defaults if file missing."""
    if not ROADMAP.exists():
        return {
            "overall": {"overall_progress": 0, "phases": []},
            "features": [],
            "blockers": [],
            "risks": [],
        }
    text = ROADMAP.read_text(encoding="utf-8")
    sec1 = _extract_section(text, r"^##\s+1\.\s", r"^##\s+2\.\s")
    sec2 = _extract_section(text, r"^##\s+2\.\s", r"^##\s+3\.\s")
    sec6 = _extract_section(text, r"^##\s+6\.\s", r"^##\s+7\.\s")
    sec7 = _extract_section(text, r"^##\s+7\.\s", r"^##\s+8\.\s")
    return {
        "overall": parse_roadmap_overall_progress(sec1),
        "features": parse_roadmap_features(sec2),
        "blockers": parse_roadmap_blockers(sec6),
        "risks": parse_roadmap_risks(sec7),
    }


def _extract_section(text: str, start_pat: str, end_pat: str) -> str:
    s = re.search(start_pat, text, re.MULTILINE)
    if not s:
        return ""
    rest = text[s.start() :]
    e = re.search(end_pat, rest[1:], re.MULTILINE)
    return rest if not e else rest[: e.start() + 1]


def _collect_doc_versions() -> list[dict]:
    today = date.today()
    return [parse_doc_version_header(p, today) for p in TRACKED_DOCS if p.exists()]


def main() -> None:
    if not TRACKER.exists():
        raise SystemExit(f"Tracker not found: {TRACKER}")
    text = TRACKER.read_text(encoding="utf-8")

    prs = parse_prs(text)
    stats = parse_summary(text)
    mvp = parse_mvp_total(text)
    branch = current_branch()

    if not prs:
        raise SystemExit(
            "No PRs parsed — check tracker structure (### Phase N: headings + status emoji)."
        )
    if not stats:
        print("Warning: no phase summary stats parsed (§5 table missing or shape changed).")

    # Enrich PR status from git reality. Tracker remains source-of-truth for
    # terminal states (merged/deferred/blocked); git wins for ⬜→active transitions.
    drift = enrich_with_git_state(prs)

    in_flight = [p for p in prs if p.status_slug in IN_FLIGHT_STATUSES]
    active = [p for p in prs if p.status_slug in ACTIVE_STATUSES]
    upcoming = [p for p in prs if p.status_slug == "not-started"][:5]

    # B-1: collect roadmap + doc data (read-only) — feeds both HTML render and JSON emit.
    roadmap_data = _collect_roadmap_data()
    doc_versions = _collect_doc_versions()

    HTML_OUT.write_text(
        render_html(
            prs,
            stats,
            mvp,
            active,
            in_flight,
            upcoming,
            branch,
            roadmap_data=roadmap_data,
            doc_versions=doc_versions,
        ),
        encoding="utf-8",
    )
    MD_OUT.write_text(
        render_md(prs, stats, mvp, active, in_flight, upcoming, branch),
        encoding="utf-8",
    )
    tracker_data = {"mvp": mvp or {}, "phases": [s.__dict__ for s in stats]}
    payload = build_dashboard_json(tracker_data, roadmap_data, doc_versions)
    JSON_OUT.write_text(
        json.dumps(payload, indent=2, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"✓ {HTML_OUT.relative_to(ROOT)}  ({len(prs)} PRs, {len(stats)} phases)")
    print(f"✓ {MD_OUT.relative_to(ROOT)}")
    print(
        f"✓ {JSON_OUT.relative_to(ROOT)}  ({len(roadmap_data['features'])} features, {len(doc_versions)} docs)"
    )
    if mvp:
        print(
            f"  MVP: {mvp['percent']}% ({mvp['merged']}/{mvp['total']})  ·  In flight: {len(in_flight)}  ·  Active: {len(active)}"
        )
    if drift:
        print(f"\n  Git drift detected ({len(drift)} row{'s' if len(drift) != 1 else ''}):")
        for pr_id, old, new, reason in drift:
            print(f"    {pr_id:14s} {old:14s} → {new:14s}  ({reason})")
        print("  → Tracker emoji left as-is; dashboard shows reconciled status.")
        print("  → Update tracker if drift is real (e.g., founder forgot to flip ⬜→🟡).")

    sync_lines = []
    for p in prs:
        if p.unpushed > 0:
            sync_lines.append(f"    ↑{p.unpushed:2d} unpushed  {p.pr_id:14s} ({p.branch})")
        if p.unpulled > 0:
            sync_lines.append(f"    ↓{p.unpulled:2d} unpulled  {p.pr_id:14s} ({p.branch})")
    if sync_lines:
        print(f"\n  Local↔origin sync ({len(sync_lines)} entries):")
        for line in sync_lines:
            print(line)


if __name__ == "__main__":
    main()
