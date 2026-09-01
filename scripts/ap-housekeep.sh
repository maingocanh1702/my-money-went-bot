#!/usr/bin/env bash
# ap-housekeep.sh — READ-ONLY inventory for Level 3 worktrees.
#
# Bulk mutation is intentionally retired. It used to remove worktrees/branches and release
# reservations from local ancestry alone, bypassing READY/gate/origin/disposition proofs.
# Every mutation now goes through:
#
#   scripts/ap-finish.sh <FEATURE_ID>
#   scripts/ap-finish.sh <FEATURE_ID> --squash-verified <ORIGIN_COMMIT>
#   scripts/ap-finish.sh <FEATURE_ID> --authorized-close --reason <TEXT>
#
# Usage:
#   bash scripts/ap-housekeep.sh
#   bash scripts/ap-housekeep.sh --help
set -euo pipefail

case "${1:-}" in
  "")
    ;;
  -h|--help)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  --apply|--force|--all)
    echo "HALT LEVEL3_BULK_CLEANUP_DISABLED: use verified scripts/ap-finish.sh per feature." >&2
    exit 2
    ;;
  *)
    echo "HALT: unknown argument: $1" >&2
    exit 2
    ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || { echo "HALT: not inside a git repo" >&2; exit 1; }
ROOT="$(cd "$(git rev-parse --git-common-dir)" && cd .. && pwd)"
INFLIGHT="$ROOT/.autopilot/INFLIGHT.md"

printf 'LEVEL3_HOUSEKEEP_MODE: READ_ONLY\n'
printf 'ROOT: %s\n' "$ROOT"
printf 'MUTATION: disabled; use scripts/ap-finish.sh per feature\n'
printf '\n%-36s %-12s %s\n' "FEATURE" "REGISTRY" "WORKTREE"

git -C "$ROOT" worktree list --porcelain | awk '
  /^worktree /{path=substr($0,10);branch="";next}
  /^branch refs\/heads\/feat\//{
    branch=$2
    sub(/^refs\/heads\/feat\//,"",branch)
    print branch "\t" path
  }
' | while IFS="$(printf '\t')" read -r feature worktree; do
  [ -n "$feature" ] || continue
  status="absent"
  if [ -f "$INFLIGHT" ]; then
    # No reset on the header line — see ap-finish.sh registry_status(). Accumulating one named feature
    # and clearing on every later header returns empty for anything that is not the LAST block, which
    # here meant the inventory silently reported live reservations as `absent`.
    status="$(awk -v me="$feature" '
      /^## feature:/{cur=$3}
      /^status:/{if(cur==me)st=$2}
      END{print st}
    ' "$INFLIGHT")"
    [ -n "$status" ] || status="absent"
  fi
  printf '%-36s %-12s %s\n' "$feature" "$status" "$worktree"
done

printf '\nNo worktree, branch or reservation was changed.\n'
