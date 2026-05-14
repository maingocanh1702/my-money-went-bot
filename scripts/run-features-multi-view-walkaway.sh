#!/usr/bin/env bash
# Features multi-view walk-away — 3 view modes (Cards/Kanban/Table) + switcher.
#
# Usage:
#   ./scripts/run-features-multi-view-walkaway.sh
#
# Prereqs: clean working tree, claude CLI authed
# Effort: ~45-90min Opus session (multi-view is more code than single-bar mega #3)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PROMPT_FILE="docs/autopilot/ops-tracker-dashboard/features-multi-view-walkaway.md"
LOG_DIR=".autopilot"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/features-multi-view-walkaway-$(date +%s).log"

export AUTOPILOT_NO_VERIFY="${AUTOPILOT_NO_VERIFY:-1}"

echo "▶ Pre-flight..."
command -v claude >/dev/null || { echo "❌ claude CLI not installed"; exit 1; }
[ -f "$PROMPT_FILE" ] || { echo "❌ Prompt missing: $PROMPT_FILE"; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ Working tree not clean. Commit/stash first:"
  git status --short
  exit 1
fi

echo "▶ Spawning claude -p with features-multi-view-walkaway.md..."
echo "  Model: claude-opus-4-6"
echo "  Log:   $LOG_FILE"
echo "  Tail:  tail -f $LOG_FILE"
echo ""

osascript -e 'display notification "Features multi-view walk-away started" with title "Autopilot"' 2>/dev/null || true

cat "$PROMPT_FILE" | claude -p \
  --output-format text \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep" \
  --model claude-opus-4-6 \
  2>&1 | tee "$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  osascript -e 'display notification "Features multi-view COMPLETE" with title "Autopilot" subtitle "3 views shipped"' 2>/dev/null || true
  echo "✅ Walk-away completed. Log: $LOG_FILE"
else
  osascript -e 'display notification "Features multi-view HALT" with title "Autopilot"' 2>/dev/null || true
  echo "⛔ Halted (exit $EXIT_CODE). Triage: $LOG_FILE"
fi

exit $EXIT_CODE
