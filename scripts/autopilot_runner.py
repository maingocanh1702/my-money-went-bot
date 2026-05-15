#!/usr/bin/env python3
"""Autopilot orchestrator for ops-tracker-dashboard batch (11 prompts + manual items).

Per project_ops_tracker_full_auto_exception memory (2026-05-13): this batch
overrides global P1 manual_only policy.

Workflow per item:
  manual_item → automator if scriptable, else founder runbook prompt
  autopilot   → spawn `claude -p` (Claude Max via OAuth) → parse Final Report
                → auto-squash + push to main → next

Usage:
  python scripts/autopilot_runner.py --status
  python scripts/autopilot_runner.py --next
  python scripts/autopilot_runner.py --resume
  python scripts/autopilot_runner.py --reset
  python scripts/autopilot_runner.py --skip <ITEM_ID>

Env:
  AUTOPILOT_SDK=1                  → SDK mode (Claude Code -p); else paste
  AUTOPILOT_AUTOMATE_MANUAL=1      → try automators for "manual" items
  AUTOPILOT_MODEL                  → override default claude-sonnet-4-6
  AUTOPILOT_NO_VERIFY=1            → pass --no-verify on squash commit (default 0)
  LINEAR_API_KEY, LINEAR_TEAM_NAME → automator credentials
  GITHUB_TOKEN, GH_REPO            → automator credentials
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "docs" / "autopilot" / "ops-tracker-dashboard"
INDEX_PATH = PROMPTS_DIR / "INDEX.md"
STATE_PATH = REPO_ROOT / "scripts" / ".autopilot_runner_state.json"
EVENT_LOG_PATH = REPO_ROOT / ".autopilot" / "events.log"


# ───────────────────────────────────────────────────────────────────
# Execution plan
# ───────────────────────────────────────────────────────────────────


@dataclass
class Item:
    id: str
    kind: str  # "manual" | "autopilot"
    title: str
    risk_tier: str | None = None
    prompt_file: str | None = None
    runbook_md: str | None = None
    depends_on: list[str] = field(default_factory=list)


EXECUTION_ORDER: list[Item] = [
    Item(
        id="C-3.0",
        kind="manual",
        title="Linear free-tier capability verification",
        runbook_md="Log into Linear → Settings → Plan. Check: custom fields, cycles, templates, integrations. Document gaps in §C-3.0. Reply 'done' to proceed.",
    ),
    Item(
        id="C-2",
        kind="manual",
        title="Linear projects + labels setup (auto via automator)",
        depends_on=["C-3.0"],
        runbook_md="Auto: 10 phase projects + 8 labels created via Linear GraphQL. Idempotent. Falls back to manual if API blocked.",
    ),
    Item(
        id="A-P0",
        kind="autopilot",
        title="Adaptive polling rate limit + rename + cross-refs",
        risk_tier="P2 mature",
        prompt_file="prompt-A-P0-rate-limit-and-rename.md",
    ),
    Item(
        id="A-P1-4",
        kind="autopilot",
        title="Script-safe DOM swap",
        risk_tier="P2 mature",
        prompt_file="prompt-A-P1-dom-swap.md",
    ),
    Item(
        id="D-3",
        kind="autopilot",
        title="Branch + PR convention + pre-push hook",
        risk_tier="P2 pilot",
        prompt_file="prompt-D-3-branch-pr-convention.md",
        depends_on=["C-2"],
    ),
    Item(
        id="C-3",
        kind="autopilot",
        title="Linear migration script",
        risk_tier="P1",
        prompt_file="prompt-C-3-migration-script.md",
        depends_on=["D-3"],
    ),
    Item(
        id="C-3-execute",
        kind="manual",
        title="Run linear_migrate.py (auto via automator)",
        depends_on=["C-3"],
        runbook_md="Auto: --dry-run then --execute --confirm. Or manual: python scripts/linear_migrate.py --dry-run.",
    ),
    Item(
        id="D-2.1",
        kind="manual",
        title="Verify Linear progress renders in dashboard",
        depends_on=["C-3-execute"],
        runbook_md="Open dashboard. Verify phase progress bars show Linear data. Reply 'done'.",
    ),
    Item(
        id="C-4",
        kind="autopilot",
        title="Railway /ops-dashboard.json endpoint",
        risk_tier="P1",
        prompt_file="prompt-C-4-railway-backend.md",
        depends_on=["D-2.1"],
    ),
    Item(
        id="C-4-deploy",
        kind="manual",
        title="Deploy ops_api/ to Railway (auto via automator)",
        depends_on=["C-4"],
        runbook_md="Auto: railway up + healthz smoke. Or manual via Railway dashboard.",
    ),
    Item(
        id="D-6",
        kind="autopilot",
        title="Linear status sync workflow + branch protection",
        risk_tier="P1",
        prompt_file="prompt-D-6-linear-status-sync.md",
        depends_on=["C-4-deploy"],
    ),
    Item(
        id="D-6-protect",
        kind="manual",
        title="Apply GitHub branch protection (auto via gh api)",
        depends_on=["D-6"],
        runbook_md="Auto: gh api PUT /branches/main/protection. Or manual via GitHub Settings → Branches.",
    ),
    Item(
        id="B-1",
        kind="autopilot",
        title="Multi-source parser",
        risk_tier="P2 mature",
        prompt_file="prompt-B-1-multi-source-parse.md",
        depends_on=["D-6-protect"],
    ),
    Item(
        id="B-2",
        kind="autopilot",
        title="5-tab UI rendering",
        risk_tier="P2 mature",
        prompt_file="prompt-B-2-tab-ui.md",
        depends_on=["B-1", "A-P1-4"],
    ),
    Item(
        id="B-3",
        kind="autopilot",
        title="Polish: Gantt + readiness + staleness",
        risk_tier="P2 mature",
        prompt_file="prompt-B-3-polish-gantt.md",
        depends_on=["B-2"],
    ),
    Item(
        id="D-4",
        kind="autopilot",
        title="Multi-dev playbook + CODEOWNERS + standup",
        risk_tier="P2 pilot",
        prompt_file="prompt-D-4-multidev-playbook.md",
    ),
    Item(
        id="D-5",
        kind="autopilot",
        title="Dev onboarding doc + Linear template specs",
        risk_tier="P2 mature",
        prompt_file="prompt-D-5-onboarding-doc.md",
        depends_on=["D-4"],
    ),
    Item(
        id="D-5-templates",
        kind="manual",
        title="Paste Linear issue templates (auto via API)",
        depends_on=["D-5"],
        runbook_md="Auto: issueTemplateCreate via Linear API. Falls back to manual UI paste if API unsupported.",
    ),
    Item(
        id="C-5.3",
        kind="manual",
        title="Archive implementation-tracker.md (founder only — memory lock)",
        depends_on=["D-5-templates"],
        runbook_md="PRECONDITION: 7-day drift-free window. git mv docs/implementation-tracker.md docs/archive/. PR + merge.",
    ),
]


# ───────────────────────────────────────────────────────────────────
# State
# ───────────────────────────────────────────────────────────────────


@dataclass
class ItemState:
    id: str
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    branch: str | None = None
    squash_sha: str | None = None
    codex_rounds: int | None = None
    notes: str | None = None


@dataclass
class RunnerState:
    batch_name: str = "ops-tracker-dashboard"
    started_at: str | None = None
    last_updated: str | None = None
    webhook_url: str | None = None
    items: dict[str, ItemState] = field(default_factory=dict)

    @classmethod
    def load(cls) -> RunnerState:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text())
            return cls(
                batch_name=data.get("batch_name", "ops-tracker-dashboard"),
                started_at=data.get("started_at"),
                last_updated=data.get("last_updated"),
                webhook_url=data.get("webhook_url"),
                items={k: ItemState(**v) for k, v in data.get("items", {}).items()},
            )
        return cls()

    def save(self) -> None:
        self.last_updated = now_iso()
        STATE_PATH.write_text(
            json.dumps(
                {
                    "batch_name": self.batch_name,
                    "started_at": self.started_at,
                    "last_updated": self.last_updated,
                    "webhook_url": self.webhook_url,
                    "items": {k: asdict(v) for k, v in self.items.items()},
                },
                indent=2,
            )
        )


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sh(cmd: list[str], cwd: Path = REPO_ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)  # noqa: S603


def preflight_concurrency() -> None:
    locks = list((REPO_ROOT / ".git").glob("*.lock"))
    if locks:
        print(f"⚠ FAIL: stale git locks: {locks}")
        sys.exit(2)


def notify(state: RunnerState, message: str) -> None:
    """Append-only event log + macOS notification + optional webhook."""
    try:
        EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EVENT_LOG_PATH.open("a") as f:
            f.write(f"{now_iso()}  {message}\n")
    except OSError as e:
        print(f"⚠ Event log write failed: {e}")

    try:
        msg_escaped = message.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(  # noqa: S603,S607
            [
                "osascript",
                "-e",
                f'display notification "{msg_escaped}" with title "Autopilot" subtitle "{state.batch_name}"',
            ],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if state.webhook_url:
        try:
            req = urllib.request.Request(
                state.webhook_url,
                data=json.dumps({"content": message}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)  # noqa: S310
        except urllib.error.URLError as e:
            print(f"⚠ Webhook notify failed: {e}")


def deps_ready(item: Item, state: RunnerState) -> bool:
    return all(state.items.get(d, ItemState(d)).status == "completed" for d in item.depends_on)


def next_pending(state: RunnerState) -> Item | None:
    for item in EXECUTION_ORDER:
        s = state.items.get(item.id, ItemState(item.id))
        if s.status in ("completed", "skipped"):
            continue
        if not deps_ready(item, state):
            continue
        return item
    return None


# ───────────────────────────────────────────────────────────────────
# Report parsing
# ───────────────────────────────────────────────────────────────────

BRANCH_RE = re.compile(r"Branch\s+([\w/\-.]+):", re.IGNORECASE)
COMPLETE_RE = re.compile(r"AUTOPILOT.*?(COMPLETE|READY_FOR_MANUAL_MERGE)", re.IGNORECASE)
HALT_RE = re.compile(r"HALT\s+—\s+([\w\-./ ]+?)\s+circuit broken", re.IGNORECASE)
SQUASH_BLOCK_RE = re.compile(
    r"Suggested squash command.*?:\s*\n(.*?)(?:═══|$)", re.DOTALL | re.IGNORECASE
)
ROUNDS_RE = re.compile(r"Round\s+\d+", re.IGNORECASE)


def parse_report(report: str) -> dict:
    out: dict = {"status": "unknown"}
    halt = HALT_RE.search(report)
    if halt:
        out["status"] = "halted"
        out["halt_detail"] = halt.group(1).strip()
        return out
    completion = COMPLETE_RE.search(report)
    if completion:
        out["status"] = "completed" if completion.group(1).upper() == "COMPLETE" else "ready"
    branch_m = BRANCH_RE.search(report)
    if branch_m:
        out["branch"] = branch_m.group(1)
    rounds = ROUNDS_RE.findall(report)
    out["codex_rounds"] = len(rounds)
    squash = SQUASH_BLOCK_RE.search(report)
    if squash:
        out["suggested_squash"] = squash.group(1).strip()
    return out


# ───────────────────────────────────────────────────────────────────
# Auto-squash + push (robust: handles remote-ahead via pull --rebase)
# ───────────────────────────────────────────────────────────────────


def auto_squash(branch: str, commit_msg: str) -> str:
    preflight_concurrency()
    no_verify = ["--no-verify"] if os.environ.get("AUTOPILOT_NO_VERIFY") == "1" else []
    print("  → git checkout main")
    sh(["git", "checkout", "main"])
    print("  → git fetch + pull --rebase (handle remote-ahead)")
    sh(["git", "fetch", "origin", "main"])
    pull = sh(["git", "pull", "--rebase", "origin", "main"], check=False)
    if pull.returncode != 0:
        raise RuntimeError(f"pull --rebase failed: {pull.stderr}")
    print(f"  → git merge --squash {branch}")
    sh(["git", "merge", "--squash", branch])
    print("  → git commit" + (" --no-verify" if no_verify else ""))
    sh(["git", "commit", *no_verify, "-m", commit_msg])
    sha = sh(["git", "rev-parse", "HEAD"]).stdout.strip()
    print("  → git push origin main")
    sh(["git", "push", "origin", "main"])
    print(f"  → delete branch {branch}")
    sh(["git", "branch", "-D", branch], check=False)
    sh(["git", "push", "origin", "--delete", branch], check=False)
    return sha


def extract_squash_commit_msg(suggested: str) -> str:
    m = re.search(r'git commit -m\s+"([^"]+)"', suggested, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"git commit -m\s+'([^']+)'", suggested, re.DOTALL)
    return m.group(1).strip() if m else "merge: autopilot squash"


# ───────────────────────────────────────────────────────────────────
# Item handlers
# ───────────────────────────────────────────────────────────────────


def handle_manual(item: Item, state: RunnerState) -> str:
    print("\n" + "─" * 70)
    print(f"📋 MANUAL ITEM: {item.id} — {item.title}")
    print("─" * 70)

    auto_enabled = os.environ.get("AUTOPILOT_AUTOMATE_MANUAL") == "1"
    if auto_enabled:
        try:
            from autopilot_manual_automators import MUST_BE_FOUNDER, can_automate, run_automator
        except ImportError:
            sys.path.insert(0, str(REPO_ROOT / "scripts"))
            from autopilot_manual_automators import (  # type: ignore
                MUST_BE_FOUNDER,
                can_automate,
                run_automator,
            )

        if item.id in MUST_BE_FOUNDER:
            print(f"  ⚠ {item.id} requires founder (memory lock). Manual prompt.")
        elif can_automate(item.id):
            result = run_automator(item.id)
            print(f"  Result: {result['status']} — {result['detail']}")
            if result["status"] == "completed":
                return "completed"
            print("  ⚠ Automator halted — falling back to manual prompt")

    print(textwrap.indent(item.runbook_md or "(no runbook)", "  "))
    print("\nAction: done | skip | halt")
    while True:
        reply = input("\nFounder reply > ").strip().lower()
        if reply in ("done", "skip", "halt"):
            return {"done": "completed", "skip": "skipped", "halt": "halted"}[reply]
        print("  invalid; type: done | skip | halt")


def handle_autopilot(item: Item, state: RunnerState) -> dict:
    print("\n" + "─" * 70)
    print(f"🤖 AUTOPILOT ITEM: {item.id} — {item.title}")
    print(f"   Risk tier: {item.risk_tier}")
    print(f"   Prompt:    {item.prompt_file}")
    print("─" * 70)

    prompt_path = PROMPTS_DIR / item.prompt_file
    if not prompt_path.exists():
        return {"status": "halted", "halt_detail": "prompt file not found"}

    if os.environ.get("AUTOPILOT_SDK") == "1":
        return _run_via_sdk(item, prompt_path)
    return _run_via_paste(item, prompt_path)


def _run_via_sdk(item: Item, prompt_path: Path) -> dict:
    try:
        from autopilot_agent import run_autopilot_session
    except ImportError:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from autopilot_agent import run_autopilot_session  # type: ignore

    print("  Mode: SDK (Claude Code -p via Max sub) — zero-touch")
    prompt_content = prompt_path.read_text()

    def progress(_id, _it, text):
        first_line = text.strip().splitlines()[0] if text.strip() else ""
        if first_line:
            print(f"    · {first_line[:160]}", flush=True)

    result = run_autopilot_session(prompt_content, item.id, on_progress=progress)
    print(
        f"\n  ⤷ status={result.status}, iter={result.iterations}, "
        f"tokens={result.input_tokens}in/{result.output_tokens}out, "
        f"cost=${result.cost_usd:.4f}, duration={result.duration_ms/1000:.1f}s"
    )
    if result.error:
        print(f"  ⤷ Error: {result.error}")

    parsed = parse_report(result.final_text)
    parsed["report_raw"] = result.final_text
    parsed["sdk_log"] = str(result.log_path) if result.log_path else None
    if result.status == "halted" and parsed.get("status") != "halted":
        parsed["status"] = "halted"
        parsed["halt_detail"] = parsed.get("halt_detail") or "sentinel HALT"
    if result.status == "error":
        parsed["status"] = "halted"
        parsed["halt_detail"] = result.error or "SDK error"
    return parsed


def _run_via_paste(item: Item, prompt_path: Path) -> dict:
    print("  Mode: PASTE (set AUTOPILOT_SDK=1 for zero-touch)")
    print(f"\n  1. Open: {prompt_path}")
    print("  2. Run in new Claude Code session, paste prompt body")
    print("  3. Copy Final Report back here, type END\n")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    report = "\n".join(lines)
    parsed = parse_report(report)
    parsed["report_raw"] = report
    return parsed


# ───────────────────────────────────────────────────────────────────
# Genealogy
# ───────────────────────────────────────────────────────────────────


def update_genealogy(item: Item, s: ItemState) -> None:
    if not INDEX_PATH.exists():
        return
    content = INDEX_PATH.read_text()
    row = (
        f"| {item.id} | {item.risk_tier or 'manual'} | {s.codex_rounds or '—'} | "
        f"{(s.squash_sha or '')[:7]} | {(s.completed_at or '')[:10]} | {s.status} |"
    )
    table_re = re.compile(
        r"(\| Prompt \| Risk \| Codex rounds \| Merge SHA \| Date \| Outcome \|\s*\n\|[^\n]+\n)",
        re.IGNORECASE,
    )
    if table_re.search(content):
        content = table_re.sub(r"\1" + row + "\n", content, count=1)
        INDEX_PATH.write_text(content)


# ───────────────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────────────


def cmd_status(state: RunnerState) -> None:
    done = sum(1 for s in state.items.values() if s.status == "completed")
    halted = sum(1 for s in state.items.values() if s.status == "halted")
    skipped = sum(1 for s in state.items.values() if s.status == "skipped")
    total = len(EXECUTION_ORDER)
    print(f"\nBatch: {state.batch_name}")
    print(f"Progress: {done}/{total} completed, {halted} halted, {skipped} skipped\n")
    for item in EXECUTION_ORDER:
        s = state.items.get(item.id, ItemState(item.id))
        icon = {
            "completed": "✅",
            "halted": "⛔",
            "skipped": "⏭",
            "in_progress": "🟡",
            "pending": "⏳",
        }.get(s.status, "?")
        tag = "[manual]" if item.kind == "manual" else f"[{item.risk_tier}]"
        print(f"  {icon} {item.id:<14} {tag:<14} {item.title}")
    nxt = next_pending(state)
    print(f"\nNext: {nxt.id if nxt else '(all done)'}\n")


def cmd_next(state: RunnerState) -> int:
    preflight_concurrency()
    item = next_pending(state)
    if not item:
        print("✅ All items complete.")
        return 0

    s = state.items.setdefault(item.id, ItemState(item.id))
    s.status = "in_progress"
    s.started_at = now_iso()
    if not state.started_at:
        state.started_at = now_iso()
    state.save()
    notify(state, f"🚀 Starting {item.id} — {item.title}")

    if item.kind == "manual":
        result = handle_manual(item, state)
        s.status = result
        s.completed_at = now_iso()
        state.save()
        update_genealogy(item, s)
        notify(state, f"{'✅' if result == 'completed' else '⛔'} {item.id} → {result}")
        return 0 if result != "halted" else 3

    parsed = handle_autopilot(item, state)
    if parsed.get("status") == "halted":
        s.status = "halted"
        s.notes = f"HALT: {parsed.get('halt_detail')}"
        s.completed_at = now_iso()
        state.save()
        update_genealogy(item, s)
        notify(state, f"⛔ {item.id} HALTED: {parsed.get('halt_detail')}")
        print(f"\n⛔ Halted. Triage required. Log: {parsed.get('sdk_log')}")
        return 3

    if parsed.get("status") not in ("ready", "completed"):
        s.status = "halted"
        s.notes = "unparseable report"
        state.save()
        notify(state, f"⛔ {item.id} unparseable report")
        return 3

    s.branch = parsed.get("branch")
    s.codex_rounds = parsed.get("codex_rounds")

    if parsed.get("status") == "ready" and s.branch and parsed.get("suggested_squash"):
        print("\n🔧 Auto-merging per full-auto exception policy...")
        try:
            commit_msg = extract_squash_commit_msg(parsed["suggested_squash"])
            sha = auto_squash(s.branch, commit_msg)
            s.squash_sha = sha
            s.status = "completed"
            print(f"  ✅ Merged: {sha[:7]}")
        except (subprocess.CalledProcessError, RuntimeError) as e:
            s.status = "halted"
            s.notes = f"auto-squash failed: {e}"
            state.save()
            notify(state, f"⛔ {item.id} squash FAIL: {s.notes}")
            print(f"\n⛔ Squash failed: {e}")
            return 3
    elif parsed.get("status") == "completed":
        s.status = "completed"

    s.completed_at = now_iso()
    state.save()
    update_genealogy(item, s)
    notify(
        state, f"✅ {item.id} merged (rounds: {s.codex_rounds}, sha: {(s.squash_sha or '')[:7]})"
    )
    print(f"\n✅ {item.id} complete.")
    return 0


def cmd_resume(state: RunnerState) -> int:
    while True:
        item = next_pending(state)
        if not item:
            print("✅ All items complete.")
            return 0
        rc = cmd_next(state)
        if rc != 0:
            return rc


def cmd_skip(state: RunnerState, item_id: str) -> int:
    found = next((i for i in EXECUTION_ORDER if i.id == item_id), None)
    if not found:
        print(f"Unknown item: {item_id}")
        return 1
    s = state.items.setdefault(item_id, ItemState(item_id))
    s.status = "skipped"
    s.completed_at = now_iso()
    state.save()
    update_genealogy(found, s)
    print(f"⏭ {item_id} skipped.")
    return 0


def cmd_reset(state: RunnerState) -> int:
    print("⚠ Wipes all runner state.")
    if input("Type 'RESET' to confirm: ").strip() == "RESET":
        STATE_PATH.unlink(missing_ok=True)
        print("✅ State wiped.")
        return 0
    print("Cancelled.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--next", action="store_true")
    group.add_argument("--resume", action="store_true")
    group.add_argument("--reset", action="store_true")
    group.add_argument("--skip", metavar="ITEM_ID")
    parser.add_argument("--notify-webhook", metavar="URL")
    args = parser.parse_args()

    state = RunnerState.load()
    if args.notify_webhook:
        state.webhook_url = args.notify_webhook
        state.save()

    if args.status:
        cmd_status(state)
        return 0
    if args.next:
        return cmd_next(state)
    if args.resume:
        return cmd_resume(state)
    if args.skip:
        return cmd_skip(state, args.skip)
    if args.reset:
        return cmd_reset(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
