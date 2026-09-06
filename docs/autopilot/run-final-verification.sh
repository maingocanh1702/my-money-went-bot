#!/usr/bin/env bash
# run-final-verification.sh — run the READ-ONLY final verification pass on "My Money Went Bot"
# through Claude Code, headless (no copy-paste needed).
#
# Read-only is enforced at TWO layers:
#   1) the prompt itself (docs/autopilot/prompts/final-verification-readonly.md), and
#   2) the CLI permission flags below — mutating git ops, source edits (Edit/MultiEdit),
#      deletions (rm/mv), and dependency installs (pip) are DENIED. Claude Code applies deny
#      rules with precedence over allow rules, so these cannot be overridden by the model.
#
# The run still RUNS the quality gate (ruff + pytest) and WRITES one report file —
# docs/audits/final-verification-<YYYY-MM-DD>.md — both of which are allowed.
#
# Usage:
#   bash docs/autopilot/run-final-verification.sh                # recommended: headless + guarded
#   MODE=yolo bash docs/autopilot/run-final-verification.sh      # skip ALL permission checks (prompt is the only guard)
#   CLAUDE_MODEL=opus bash docs/autopilot/run-final-verification.sh   # pin a model
#   MAX_TURNS=160 bash docs/autopilot/run-final-verification.sh       # raise the turn budget
#
# Prereqs on YOUR machine: the `claude` CLI on PATH, a `.venv` with pytest installed
# (and ideally `ruff` — the prompt notes it gracefully if ruff is absent).

set -euo pipefail

# --- Resolve repo root from this script's location (docs/autopilot/ -> repo root) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

PROMPT_FILE="docs/autopilot/prompts/final-verification-readonly.md"
[ -f "$PROMPT_FILE" ] || { echo "ERROR: prompt not found: $PROMPT_FILE" >&2; exit 1; }
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' CLI not found on PATH." >&2; exit 1; }

# --- Activate a venv if present so the agent's pytest/ruff resolve (claude's Bash inherits env) ---
ACTIVATED=""
for vdir in .venv venv env; do
  if [ -f "$vdir/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$vdir/bin/activate"
    ACTIVATED="$vdir"
    echo "[runner] activated $vdir"
    break
  fi
done
if [ -z "$ACTIVATED" ]; then
  if command -v pytest >/dev/null 2>&1 || python3 -c "import pytest" >/dev/null 2>&1; then
    echo "[runner] no venv dir found — using pytest already on PATH"
  else
    echo "[runner] WARNING: no venv and pytest not found on PATH — the test gate may fail" >&2
  fi
fi

PROMPT="$(cat "$PROMPT_FILE")"
mkdir -p docs/audits
LOG="docs/audits/final-verification-$(date +%F).log"

MODEL_ARG=()
[ -n "${CLAUDE_MODEL:-}" ] && MODEL_ARG=(--model "$CLAUDE_MODEL")
MAX_TURNS="${MAX_TURNS:-120}"

echo "[runner] repo:   $REPO_ROOT"
echo "[runner] prompt: $PROMPT_FILE"
echo "[runner] mode:   ${MODE:-guarded}    max-turns: $MAX_TURNS"
echo "[runner] log:    $LOG"
echo

if [ "${MODE:-guarded}" = "yolo" ]; then
  # Unattended, NO permission checks. The prompt is the ONLY guard. Use only if you trust the run.
  claude -p "$PROMPT" ${MODEL_ARG[@]+"${MODEL_ARG[@]}"} \
    --dangerously-skip-permissions \
    --max-turns "$MAX_TURNS" \
    2>&1 | tee "$LOG"
else
  # Headless + read-only enforced at the CLI permission layer.
  # Allow: file reads + search + Write (for the one report) + Bash (for ruff/pytest/git-read).
  # Deny:  every mutating git op, source edits, deletions, and pip installs (deny > allow).
  claude -p "$PROMPT" ${MODEL_ARG[@]+"${MODEL_ARG[@]}"} \
    --allowedTools "Read" "Glob" "Grep" "Write" "Bash" \
    --disallowedTools \
      "Edit" "MultiEdit" "NotebookEdit" \
      "Bash(git add:*)" "Bash(git commit:*)" "Bash(git push:*)" "Bash(git merge:*)" \
      "Bash(git checkout:*)" "Bash(git switch:*)" "Bash(git restore:*)" "Bash(git reset:*)" \
      "Bash(git stash:*)" "Bash(git rebase:*)" "Bash(git cherry-pick:*)" "Bash(git clean:*)" \
      "Bash(git rm:*)" "Bash(rm:*)" "Bash(mv:*)" "Bash(pip:*)" "Bash(pip3:*)" \
    --max-turns "$MAX_TURNS" \
    2>&1 | tee "$LOG"
fi

echo
echo "[runner] done."
echo "[runner] report (if the run reached the report step): docs/audits/final-verification-$(date +%F).md"
echo "[runner] full transcript: $LOG"
