#!/usr/bin/env bash
# Feature-progress walk-away — single command, full-auto for dashboard Features tab progress bars.
#
# Usage:
#   ./scripts/run-feature-progress-walkaway.sh
#
# Phases: 0 (bootstrap) → 1 (compute_feature_progress + render bars + summary header)
# Effort: ~30-60min Opus session
# Output log: .autopilot/feature-progress-walkaway-<timestamp>.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PROMPT_FILE="docs/autopilot/ops-tracker-dashboard/feature-progress-walkaway.md"
LOG_DIR=".autopilot"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/feature-progress-walkaway-$(date +%s).log"

export AUTOPILOT_NO_VERIFY="${AUTOPILOT_NO_VERIFY:-1}"

echo "▶ Pre-flight..."
command -v claude >/dev/null || { echo "❌ claude CLI not installed"; exit 1; }
[ -f "$PROMPT_FILE" ] || { echo "❌ Prompt missing: $PROMPT_FILE"; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ Working tree not clean — bootstrap halt. Commit/stash first:"
  git status --short
  exit 1
fi

echo "▶ Spawning claude -p with feature-progress-walkaway.md..."
echo "  Model: claude-opus-4-6"
echo "  Log:   $LOG_FILE"
echo "  Tail:  tail -f $LOG_FILE"
echo ""

osascript -e 'display notification "Feature-progress walk-away started" with title "Autopilot"' 2>/dev/null || true

cat "$PROMPT_FILE" | claude -p \
  --output-format text \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep" \
  --model claude-opus-4-6 \
  2>&1 | tee "$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  osascript -e 'display notification "Feature-progress COMPLETE" with title "Autopilot" subtitle "Dashboard updated"' 2>/dev/null || true
  echo "✅ Walk-away completed. Log: $LOG_FILE"
else
  osascript -e 'display notification "Feature-progress HALT — check log" with title "Autopilot"' 2>/dev/null || true
  echo "⛔ Halted (exit $EXIT_CODE). Triage: $LOG_FILE"
fi

exit $EXIT_CODE
