#!/usr/bin/env bash
set -e
while read local_ref local_sha remote_ref remote_sha; do
  # Skip non-branch refs (tags, notes, etc.)
  case "$local_ref" in
    refs/heads/*) ;;
    *) continue ;;
  esac
  branch=${local_ref#refs/heads/}
  case "$branch" in
    main|master|develop|W0.*|Wave-*|hotfix/*|release/*) continue ;;
  esac
  if ! echo "$branch" | grep -Eq '^[a-z0-9-]+/MMW-[0-9]+-[a-z0-9-]+$'; then
    echo "❌ Branch '$branch' must match <dev>/MMW-<id>-<slug>"
    echo "   Bypass: git push --no-verify"
    exit 1
  fi
done
exit 0
