#!/bin/bash
# ─── Run autopilot audit via Codex CLI ────────────────────────
# Usage:
#   ./docs/autopilot/run-audit.sh
#   ./docs/autopilot/run-audit.sh -m o3
#
# Prerequisites:
#   - codex CLI installed (npm i -g @openai/codex)
#   - OPENAI_API_KEY set in env
#
# The prompt is self-contained. Codex will:
#   1. Read the codebase (read-only)
#   2. Run pre-flight checks (git status, pytest)
#   3. Write a single report: docs/audits/audit-<date>.md
#   4. Stop
# ──────────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")/../.."  # cd to project root

PROMPT_FILE="docs/autopilot/prompts/audit-fullproject-readonly.md"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE"
  exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "  AUDIT — My Money Went Bot — Codex Autopilot"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Prompt:   $PROMPT_FILE"
echo "  Mode:     READ-ONLY audit"
echo "  Output:   docs/audits/audit-$(date +%Y-%m-%d).md"
echo "  HEAD:     $(git rev-parse --short HEAD)"
echo ""
echo "═══════════════════════════════════════════════════════"
echo ""

# -s read-only = sandbox chỉ cho đọc file + chạy command read-only
# Pass extra flags through (e.g. -m o3 để chọn model)
codex exec \
  -s read-only \
  "$@" \
  "$(cat "$PROMPT_FILE")"
