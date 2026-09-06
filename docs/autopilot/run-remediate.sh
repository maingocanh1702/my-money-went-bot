#!/bin/bash
# ─── Run audit remediation via Codex CLI ──────────────────────
# Usage:
#   ./docs/autopilot/run-remediate.sh
#   ./docs/autopilot/run-remediate.sh -m o3
#
# Prerequisites:
#   - codex CLI installed (npm i -g @openai/codex)
#   - OPENAI_API_KEY set in env
#   - An existing audit report in docs/audits/audit-*.md
#
# The prompt is self-contained. Codex will:
#   1. Read the most recent audit report
#   2. Fix findings in P0 → P1 → P2 order (TDD-first)
#   3. Commit after each phase
#   4. Write: docs/audits/remediation-<date>.md
#   5. Stop
# ──────────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")/../.."  # cd to project root

PROMPT_FILE="docs/autopilot/prompts/remediate-audit-findings.md"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE"
  exit 1
fi

# Find the most recent audit report
LATEST_AUDIT=$(ls -t docs/audits/audit-*.md 2>/dev/null | head -1)
if [ -z "$LATEST_AUDIT" ]; then
  echo "ERROR: No audit report found in docs/audits/"
  echo "Run ./docs/autopilot/run-audit.sh first."
  exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "  REMEDIATE — My Money Went Bot — Codex Autopilot"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Prompt:   $PROMPT_FILE"
echo "  Audit:    $LATEST_AUDIT"
echo "  Mode:     WRITE (fix findings, TDD-first)"
echo "  Output:   docs/audits/remediation-$(date +%Y-%m-%d).md"
echo "  HEAD:     $(git rev-parse --short HEAD)"
echo ""
echo "═══════════════════════════════════════════════════════"
echo ""

# -s workspace-write = sandbox cho phép ghi file trong project
codex exec \
  -s workspace-write \
  "$@" \
  "$(cat "$PROMPT_FILE")"
