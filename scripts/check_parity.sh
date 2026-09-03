#!/usr/bin/env bash
# Report feature drift between this repository and the private one it mirrors.
#
# "Full feature parity" is only true if somebody measures it. This prints the
# files that differ, so a real gap is visible instead of assumed. The three
# sanitization divergences are expected and are listed as such; anything else
# is drift worth explaining.
#
# Usage: scripts/check_parity.sh [path-to-private-checkout]
set -euo pipefail

PRIVATE="${1:-$HOME/Projects/Bot Finance}"
[ -d "$PRIVATE" ] || { echo "No private checkout at: $PRIVATE"; exit 2; }

EXPECTED_DIVERGENCE=(
  google_apps_script.js                 # placeholders here, real values in the deployed Apps Script
  handlers/email_parser.py              # docstring examples are synthetic here
  tests/test_email_parser_hangseng.py   # fixture is synthetic here
  requirements-dev.txt                  # storage/ drivers are public-only for now
)

echo "public : $(git rev-parse --short HEAD)"
echo "private: $(git -C "$PRIVATE" rev-parse --short HEAD)"
echo

diff -rq \
  --exclude=.git --exclude=__pycache__ --exclude=.venv --exclude=venv \
  --exclude=.autopilot --exclude=.pytest_cache --exclude=.ruff_cache \
  --exclude=knowledge --exclude=credentials.json --exclude=.env \
  --exclude=docs --exclude=.github --exclude=scripts --exclude=storage \
  --exclude='*.md' \
  "$PRIVATE" . 2>/dev/null | sed 's|^|  |' > /tmp/parity.$$ || true

unexplained=0
while IFS= read -r line; do
  keep=1
  for f in "${EXPECTED_DIVERGENCE[@]}"; do
    case "$line" in *"$f"*) keep=0 ;; esac
  done
  if [ "$keep" = 1 ]; then echo "DRIFT $line"; unexplained=$((unexplained+1)); fi
done < /tmp/parity.$$
rm -f /tmp/parity.$$

if [ "$unexplained" = 0 ]; then
  echo "Feature parity holds — only the expected sanitization divergences remain."
else
  echo
  echo "$unexplained difference(s) beyond the expected sanitization points."
fi
