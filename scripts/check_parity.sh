#!/usr/bin/env bash
# Report feature drift between this repository and the private one it mirrors.
# An entry below without a slash matches a "Only in <dir>: <name>" line too.
#
# "Full feature parity" is only true if somebody measures it. This prints the
# files that differ, so a real gap is visible instead of assumed. Expected
# divergences are listed below with a reason; anything else is drift worth
# explaining.
#
# Two kinds of divergence are expected. Sanitization: the same feature, with
# synthetic values here. Deliberate: the private bot reads notification mail
# from its owner's banks (Techcombank, Hang Seng); this repository ships only
# the Cake parser as the worked example, so the mail-specific files differ by
# intent, not by drift.
#
# Usage: scripts/check_parity.sh [path-to-private-checkout]
set -euo pipefail

PRIVATE="${1:-$HOME/Projects/Bot Finance}"
[ -d "$PRIVATE" ] || { echo "No private checkout at: $PRIVATE"; exit 2; }

EXPECTED_DIVERGENCE=(
  google_apps_script.js                 # placeholders here; private lists its owner's bank senders
  handlers/email_parser.py              # Cake only here; private also parses Techcombank + Hang Seng
  test_email_parser_hangseng.py         # private-only: no Hang Seng parser to test here
  tests/unit/test_security_boundaries.py  # same guarantees, exercised through the Cake parser
  tests/unit/test_phase1_resolver.py    # asserts the generic email source instead of a named bank
  tests/unit/test_card_templates.py     # loads example_visa here, techcombank_visa there
  techcombank_visa.yaml                 # private-only: unverifiable card terms
  example_visa.yaml                     # public-only: generic stand-in for it
  test_postgres_direct_creator.py       # public-only: the Postgres source-of-truth work
  requirements-dev.txt                  # storage/ drivers are public-only for now
)

echo "public : $(git rev-parse --short HEAD)"
echo "private: $(git -C "$PRIVATE" rev-parse --short HEAD)"
echo

diff -rq \
  --exclude=.git --exclude=__pycache__ --exclude=.venv --exclude=venv \
  --exclude=.autopilot --exclude=.pytest_cache --exclude=.ruff_cache \
  --exclude=knowledge --exclude=credentials.json --exclude=.env \
  --exclude=.DS_Store \
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
