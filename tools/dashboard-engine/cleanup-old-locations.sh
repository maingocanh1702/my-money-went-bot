#!/bin/bash
# Run this from the repo root: bash tools/dashboard-engine/cleanup-old-locations.sh
# This removes the OLD locations after files have been copied to tools/dashboard-engine/
#
# VERIFY FIRST: ensure tools/dashboard-engine/ has all files before running.
#   find tools/dashboard-engine -type f -not -path '*__pycache__*' | wc -l
#   (should be ~80+ files)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "=== Removing old source code ==="
rm -rf scripts/work_state/
rm -f scripts/build-dashboard.py

echo "=== Removing old tests ==="
rm -rf tests/unit/work_state/
rm -rf tests/integration/work_state/

echo "=== Removing old docs ==="
rm -rf docs/operations/dashboard-engine/
rm -rf docs/autopilot/ops-tracker-dashboard/
rm -f docs/autopilot/prompts/dashboard-live-view-A-autopilot.md
rm -f docs/autopilot/prompts/dashboard-live-view-B-autopilot.md
rm -f docs/autopilot/prompts/dashboard-realtime-autopilot.md
rm -f docs/autopilot/prompts/dashboard-trigger-optimization-autopilot.md
rm -f docs/autopilot/prompts/work-state-1d-autopilot.md
rm -f docs/autopilot/prompts/work-state-engine-1b-projection-autopilot.md
rm -f docs/autopilot/prompts/work-state-engine-1c-autopilot.md
rm -f docs/autopilot/prompts/work-state-engine-phase-1a-autopilot.md
rm -f docs/autopilot/prompts/work-state-engine-phase-1b-autopilot.md
rm -f docs/autopilot/prompts/MYM-8-doc-change-hash-dedup-autopilot.md

echo "=== Removing old migration docs ==="
rm -rf .migration/

echo "=== Removing old .dashboard state ==="
rm -rf .dashboard/

echo "=== KEEPING (not removed) ==="
echo "  docs/dashboard.html  (auto-generated output)"
echo "  docs/dashboard.md    (auto-generated output)"
echo "  docs/dashboard.json  (auto-generated output)"
echo "  .github/workflows/dashboard.yml (CI — needs path update)"

echo ""
echo "=== Done. Now update these config files ==="
echo "  1. .github/workflows/dashboard.yml  — update script paths"
echo "  2. .pre-commit-config.yaml          — update build-dashboard.py path"
echo "  3. CLAUDE.md                         — update references"
echo "  4. pyproject.toml                    — update mypy/ruff excludes if needed"
