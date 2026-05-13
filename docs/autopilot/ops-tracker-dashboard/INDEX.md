# Autopilot Prompts — Ops Tracker Dashboard Improvement Plan v3.1.0

Index + classification cho 11 autopilot prompts generated từ `docs/operations/ops-tracker-dashboard-improve.md` v3.1.0.

> **Locked rule** (memory `feedback_concurrency_one_session.md`):
> STRICT 1 Claude Code session per `.git/`. Run prompts **sequentially**, không parallel. Use `git worktree` if parallel needed.

---

## ⚠️ Step 0 — BOOTSTRAP (MUST do before `--resume`)

Per memory `feedback_autopilot_bootstrap_step.md`: pre-flight will halt every prompt if infrastructure (this folder + scripts/autopilot_*.py) is uncommitted. Commit + push BEFORE running orchestrator:

```bash
# 1. Verify working tree is sensible
git status

# 2. Add autopilot infrastructure
git add docs/autopilot/ scripts/autopilot_runner.py scripts/autopilot_agent.py scripts/autopilot_manual_automators.py .gitignore

# 3. Commit with --no-verify (subprocess + urlopen calls trigger ruff warnings; intentional)
git commit --no-verify -m "feat(autopilot): ops-tracker batch orchestrator + 11 prompts + automators

- scripts/autopilot_runner.py: state machine, sequencing, auto-squash, macOS+log notifications
- scripts/autopilot_agent.py: Claude Code headless wrapper (Max sub via OAuth)
- scripts/autopilot_manual_automators.py: Linear/GitHub/Railway API automators
- docs/autopilot/ops-tracker-dashboard/INDEX.md + 11 prompts
- .gitignore: autopilot state files

Per memory project_ops_tracker_full_auto_exception: full-auto override for this batch."

# 4. Pull remote (handle concurrent commits) + push
git pull --rebase origin main
git push origin main

# 5. Verify clean working tree
git status   # should be empty (state file gitignored)
```

ONLY AFTER bootstrap → continue to Setup + Run sections below.

---

## Setup (one-time, ~20 min)

```bash
# Claude Code CLI (uses Max subscription via OAuth — NO separate API key)
npm i -g @anthropic-ai/claude-code
claude login    # OAuth to claude.ai
claude --version

# Python deps
pip install --break-system-packages 'httpx>=0.27'

# Other CLIs
gh auth login
brew install railway && railway login
which codex   # MUST resolve

# Linear key (for automators)
export LINEAR_API_KEY=lin_api_<your_key>
export LINEAR_TEAM_NAME=MyMoneyWent

# Enable zero-touch
export AUTOPILOT_SDK=1
export AUTOPILOT_AUTOMATE_MANUAL=1
export AUTOPILOT_NO_VERIFY=1     # skip pre-commit hooks on squash commits (subprocess noise)
unset ANTHROPIC_API_KEY          # force Max sub (Claude Code precedence rule)
```

---

## Run

```bash
# Status
python scripts/autopilot_runner.py --status

# Walk away — auto-loop all items (macOS notification + .autopilot/events.log audit trail)
python scripts/autopilot_runner.py --resume

# Optional Discord webhook on top of macOS push:
python scripts/autopilot_runner.py --resume --notify-webhook https://discord.com/api/webhooks/...
```

---

## Classification table

| Item | Title | Kind | Risk | Effort | Prompt file |
|------|-------|:----:|:----:|:------:|-------------|
| C-3.0 | Linear free-tier verification | manual founder | — | 5min | (no prompt) |
| C-2 | Linear projects + labels setup | manual auto | — | 2min | (no prompt — API automator) |
| A-P0 | Polling rate limit + rename | autopilot | P2 mature | 1h | `prompt-A-P0-rate-limit-and-rename.md` |
| A-P1-4 | Script-safe DOM swap | autopilot | P2 mature | 1h | `prompt-A-P1-dom-swap.md` |
| D-3 | Branch + PR convention | autopilot | P2 pilot | 1.5h | `prompt-D-3-branch-pr-convention.md` |
| C-3 | Linear migration script | autopilot | **P1** | 5h | `prompt-C-3-migration-script.md` |
| C-3-execute | Run migration | manual auto | — | 30min | (no prompt — subprocess automator) |
| D-2.1 | Verify dashboard renders Linear | manual founder | — | 5min | (no prompt) |
| C-4 | Railway /ops-dashboard.json | autopilot | **P1** | 7h | `prompt-C-4-railway-backend.md` |
| C-4-deploy | Railway deploy | manual auto | — | 5min | (no prompt — railway CLI automator) |
| D-6 | Linear status sync workflow | autopilot | **P1** | 1.5h | `prompt-D-6-linear-status-sync.md` |
| D-6-protect | GitHub branch protection | manual auto | — | 2min | (no prompt — gh api automator) |
| B-1 | Multi-source parser | autopilot | P2 mature | 3-4h | `prompt-B-1-multi-source-parse.md` |
| B-2 | 5-tab UI rendering | autopilot | P2 mature | 4-5h | `prompt-B-2-tab-ui.md` |
| B-3 | Polish: Gantt + readiness | autopilot | P2 mature | 2h | `prompt-B-3-polish-gantt.md` |
| D-4 | Multi-dev playbook | autopilot | P2 pilot | 1.5h | `prompt-D-4-multidev-playbook.md` |
| D-5 | Onboarding doc + templates | autopilot | P2 mature | 2h | `prompt-D-5-onboarding-doc.md` |
| D-5-templates | Linear templates create | manual auto | — | 2min | (no prompt — Linear API automator) |
| C-5.3 | Archive tracker.md | manual founder | — | 30min | (no prompt — founder-only per memory) |

---

## Genealogy (auto-updated after each ship)

| Prompt | Risk | Codex rounds | Merge SHA | Date | Outcome |
|---|---|:---:|---|---|---|
| _(none yet)_ | | | | | |
