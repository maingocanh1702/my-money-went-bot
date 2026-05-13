#!/usr/bin/env bash
# Walk-away mega-prompt runner — single command, full-auto end-to-end.
#
# Usage:
#   ./scripts/run-walkaway.sh
#
# Requires:
#   - claude CLI authed (claude login → Max sub)
#   - gh CLI authed
#   - LINEAR_API_KEY env var set
#   - LINEAR_TEAM_NAME env var (default: MyMoneyWent)
#   - python + httpx available
#
# Output log: .autopilot/walkaway-<timestamp>.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PROMPT_FILE="docs/autopilot/ops-tracker-dashboard/walk-away-prompt.md"
LOG_DIR=".autopilot"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/walkaway-$(date +%s).log"

# Defaults
export LINEAR_TEAM_NAME="${LINEAR_TEAM_NAME:-MyMoneyWent}"
export AUTOPILOT_NO_VERIFY="${AUTOPILOT_NO_VERIFY:-1}"

# Verify
echo "▶ Pre-flight..."
[ -z "${LINEAR_API_KEY:-}" ] && { echo "❌ LINEAR_API_KEY not set"; exit 1; }
command -v claude >/dev/null || { echo "❌ claude CLI not installed (npm i -g @anthropic-ai/claude-code)"; exit 1; }
command -v gh >/dev/null || { echo "❌ gh CLI not installed (brew install gh)"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "❌ gh not authed (run: gh auth login)"; exit 1; }
[ -f "$PROMPT_FILE" ] || { echo "❌ Prompt missing: $PROMPT_FILE"; exit 1; }

echo "▶ Spawning claude -p with walk-away-prompt.md..."
echo "  Model:     claude-opus-4-6"
echo "  Tools:     Bash,Read,Edit,Write,Glob,Grep"
echo "  Log:       $LOG_FILE"
echo "  Timeout:   none (let it run)"
echo ""
echo "ℹ macOS notification + .autopilot/events.log are NOT used by mega-prompt."
echo "  Tail log live in another terminal: tail -f $LOG_FILE"
echo ""

# Show notification on start
osascript -e 'display notification "Walk-away started" with title "Autopilot" subtitle "Mega-prompt running"' 2>/dev/null || true

# Run — pipe prompt to claude -p, capture stdout to log + show on screen
cat "$PROMPT_FILE" | claude -p \
  --output-format text \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep" \
  --model claude-opus-4-6 \
  2>&1 | tee "$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  osascript -e 'display notification "ALL PHASES COMPLETE — multi-dev infrastructure live" with title "Autopilot" subtitle "Walk-away done"' 2>/dev/null || true
  echo ""
  echo "✅ Walk-away completed. Full log: $LOG_FILE"
else
  osascript -e 'display notification "HALT or error — check log" with title "Autopilot" subtitle "Walk-away stopped"' 2>/dev/null || true
  echo ""
  echo "⛔ Walk-away halted (exit $EXIT_CODE). Triage: $LOG_FILE"
fi

exit $EXIT_CODE
