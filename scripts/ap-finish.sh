#!/usr/bin/env bash
# ap-finish.sh <feature-id> [--squash-verified <origin-commit>|--authorized-close --reason <text>] [--no-archive]
# Remove a Level 3 worktree/reservation only after landing or an explicit durable disposition.
set -euo pipefail

SLUG="${1:?usage: ap-finish.sh <feature-id> [--squash-verified <origin-commit>|--authorized-close --reason <text>] [--no-archive]}"
shift
MODE="ancestor"
MODE_FLAGS=0
PROOF_SHA=""
REASON=""
NO_ARCHIVE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --squash-verified)
      [ $# -ge 2 ] || { echo "HALT: --squash-verified needs the exact origin commit SHA" >&2; exit 2; }
      MODE="squash"
      MODE_FLAGS=$((MODE_FLAGS + 1))
      PROOF_SHA="$2"
      shift 2
      ;;
    --authorized-close)
      MODE="close"
      MODE_FLAGS=$((MODE_FLAGS + 1))
      shift
      ;;
    --reason)
      [ $# -ge 2 ] || { echo "HALT: --reason needs non-empty text" >&2; exit 2; }
      REASON="$2"
      shift 2
      ;;
    --no-archive)
      NO_ARCHIVE=1
      shift
      ;;
    *)
      echo "HALT: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

[ "$MODE_FLAGS" -le 1 ] || { echo "HALT: choose only one finish mode" >&2; exit 2; }
case "$SLUG" in
  ""|*[!a-z0-9._-]*) echo "HALT: invalid feature id: $SLUG" >&2; exit 2 ;;
esac
if [ "$MODE" = "close" ] && [ -z "$REASON" ]; then
  echo "HALT: --authorized-close requires --reason <durable disposition>" >&2
  exit 2
fi
if [ "$MODE" != "close" ] && [ -n "$REASON" ]; then
  echo "HALT: --reason is valid only with --authorized-close" >&2
  exit 2
fi

git rev-parse --git-dir >/dev/null 2>&1 || { echo "HALT: not inside a git repo" >&2; exit 1; }
ROOT="$(cd "$(git rev-parse --git-common-dir)" && cd .. && pwd)"
cd "$ROOT"
WT="$ROOT/.autopilot/worktrees/$SLUG"
BR="feat/$SLUG"
STATE="$WT/.autopilot/state/$SLUG"
INFLIGHT="$ROOT/.autopilot/INFLIGHT.md"
SCOPE_GATE="$ROOT/scripts/autopilot-scope-gate"

[ -x "$SCOPE_GATE" ] || { echo "HALT: cleanup gate is missing or not executable: $SCOPE_GATE" >&2; exit 1; }

registry_status() {
  [ -f "$INFLIGHT" ] || return 0
  # No reset on the header line: this accumulates ONE named feature and prints at END, so clearing on
  # every later header erases the answer unless me is the LAST block in the registry. With the reset,
  # `ap-finish.sh --squash-verified` refused every feature that was not last — the registry plainly read
  # `ready` while this function returned empty, so the failure claimed the status was wrong rather than
  # that the lookup was. Same defect fixed in autopilot-scope-gate at v20; it lived in four copies across
  # three files, and v20 only reached the two inside that one file.
  awk -v me="$SLUG" '
    /^## feature:/{cur=$3}
    /^status:/{if(cur==me)st=$2}
    END{print st}
  ' "$INFLIGHT"
}

if [ -d "$WT" ]; then
  dirty="$(git -C "$WT" --no-optional-locks status --porcelain 2>/dev/null)"
  if [ -n "$dirty" ]; then
    echo "HALT WORKTREE_DIRTY: '$SLUG' has uncommitted changes; nothing was removed." >&2
    printf '%s\n' "$dirty" | head >&2
    exit 1
  fi
elif [ "$MODE" != "close" ]; then
  echo "HALT: expected Level 3 worktree is absent: $WT" >&2
  exit 1
fi

HEAD_SHA=""
BASE_SHA=""
DIFF_BASE_SHA=""
DIFF_SHA256=""
if [ "$MODE" != "close" ]; then
  [ "$(registry_status)" = "ready" ] \
    || { echo "HALT: registry status must be ready before landing cleanup" >&2; exit 1; }
  [ -s "$STATE/READY.txt" ] \
    || { echo "HALT: READY signal is missing: $STATE/READY.txt" >&2; exit 1; }
  [ -s "$STATE/gate-result.json" ] \
    || { echo "HALT: machine gate result is missing: $STATE/gate-result.json" >&2; exit 1; }
  if find "$STATE" -maxdepth 1 -type f \( -name 'HALT-*' -o -name 'AWAIT-FOUNDER-*' \) | grep -q .; then
    echo "HALT: an AWAIT/HALT signal is still active under $STATE" >&2
    exit 1
  fi
  [ ! -e "$STATE/pending-review-finding.json" ] \
    || { echo "HALT: unresolved review finding is still active under $STATE" >&2; exit 1; }
  command -v node >/dev/null 2>&1 || { echo "HALT: node is required to verify gate-result.json" >&2; exit 1; }
  # kit v34, founder review of item 1 (2026-08-31): gate-result.json's scope_expanded fields are
  # gitignored and never appear in a PR diff -- printed here to STDERR (never captured by the
  # $(...) below, so it always reaches whoever is running this interactively) as a second,
  # landing-time surface alongside `ready`'s own terminal banner. Absent on a gate-result.json from
  # before this field existed -- Array.isArray guards that as "nothing to report", not an error.
  gate_values="$(node - "$STATE/gate-result.json" "$SLUG" <<'NODE'
const fs = require("fs");
const [file, feature] = process.argv.slice(2);
const value = JSON.parse(fs.readFileSync(file, "utf8"));
const commitShaPattern = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i;
const isRealCommitSha = (candidate) =>
  commitShaPattern.test(candidate || "") && !/^0+$/.test(candidate);
if (
  value.gate_schema_version !== "level3-readiness-v2"
  || value.result !== "pass"
  || value.feature !== feature
  || !isRealCommitSha(value.base_sha)
  || !isRealCommitSha(value.diff_base_sha)
  || !isRealCommitSha(value.head_sha)
  || !/^[0-9a-f]{64}$/i.test(value.diff_sha256 || "")
  || !Number.isInteger(value.attempt)
  || value.attempt < 1
) process.exit(1);
if (Array.isArray(value.scope_expanded_files) && value.scope_expanded_files.length) {
  process.stderr.write(
    [
      "",
      "################################################################################",
      "# LANDING A FEATURE WHOSE DIFF EXPANDED BEYOND ITS DECLARED SCOPE             #",
      "################################################################################",
      `also touched, never declared (${value.scope_expanded_files.length}): ${value.scope_expanded_files.join(", ")}`,
      "Confirm this was reviewed before finishing the merge/close.",
      "################################################################################",
      "",
    ].join("\n"),
  );
}
process.stdout.write(
  [value.base_sha, value.diff_base_sha, value.head_sha, value.diff_sha256, value.attempt].join("\n"),
);
NODE
)" || { echo "HALT: gate-result.json is invalid or stale-schema" >&2; exit 1; }
  BASE_SHA="$(printf '%s\n' "$gate_values" | sed -n '1p')"
  DIFF_BASE_SHA="$(printf '%s\n' "$gate_values" | sed -n '2p')"
  HEAD_SHA="$(printf '%s\n' "$gate_values" | sed -n '3p')"
  DIFF_SHA256="$(printf '%s\n' "$gate_values" | sed -n '4p')"
  GATE_ATTEMPT="$(printf '%s\n' "$gate_values" | sed -n '5p')"
  [ -s "$STATE/gate-attempt-count.txt" ] \
    || { echo "HALT: gate attempt counter is missing" >&2; exit 1; }
  [ "$(tr -d '[:space:]' < "$STATE/gate-attempt-count.txt")" = "$GATE_ATTEMPT" ] \
    || { echo "HALT: gate result is not from the latest readiness attempt" >&2; exit 1; }
  [ "$(git -C "$ROOT" rev-parse "$BR^{commit}")" = "$HEAD_SHA" ] \
    || { echo "HALT: branch tip advanced after READY; rerun the readiness gate" >&2; exit 1; }
  # base_sha is the pinned LEGITIMACY base, not the diff window — it is right that it is still an
  # ancestor of HEAD, but the window this diff is measured from is diff_base_sha, the live base_ref
  # tip the gate actually used (autopilot-review-readiness.mjs liveDiffState()). Recomputing from
  # base_sha instead reproduces the exact bug this field exists to fix: once anything lands on
  # base_ref, base_sha...HEAD spans commits the gate never reviewed. No fallback to base_sha — a
  # fallback is a second source of truth, which is the defect.
  live_diff_hash="$(git -C "$ROOT" diff --binary "$DIFF_BASE_SHA...$HEAD_SHA" | shasum -a 256 | awk '{print $1}')"
  [ "$live_diff_hash" = "$DIFF_SHA256" ] \
    || { echo "HALT: feature diff no longer matches the gate result" >&2; exit 1; }

  git -C "$ROOT" remote get-url origin >/dev/null 2>&1 \
    || { echo "HALT: origin remote is required to prove landing" >&2; exit 1; }
  DEFAULT_BRANCH="$(git -C "$ROOT" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null \
    | sed 's#^origin/##' || true)"
  if [ -z "$DEFAULT_BRANCH" ]; then
    if git -C "$ROOT" show-ref --verify --quiet refs/remotes/origin/main; then DEFAULT_BRANCH="main"
    elif git -C "$ROOT" show-ref --verify --quiet refs/remotes/origin/master; then DEFAULT_BRANCH="master"
    else echo "HALT: cannot resolve origin default branch" >&2; exit 1
    fi
  fi
  git -C "$ROOT" fetch --quiet origin "$DEFAULT_BRANCH"
  ORIGIN_REF="origin/$DEFAULT_BRANCH"

  if [ "$MODE" = "ancestor" ]; then
    git -C "$ROOT" merge-base --is-ancestor "$HEAD_SHA" "$ORIGIN_REF" \
      || {
        echo "HALT NOT_LANDED: $BR is not an ancestor of $ORIGIN_REF." >&2
        echo "  → for an exact squash, use --squash-verified <origin-commit>." >&2
        echo "  → to abandon explicitly, use --authorized-close --reason <text>." >&2
        exit 1
      }
    PROOF_SHA="$HEAD_SHA"
  else
    git -C "$ROOT" rev-parse --verify --quiet "$PROOF_SHA^{commit}" >/dev/null \
      || { echo "HALT: squash proof commit not found: $PROOF_SHA" >&2; exit 1; }
    git -C "$ROOT" merge-base --is-ancestor "$PROOF_SHA" "$ORIGIN_REF" \
      || { echo "HALT: squash proof $PROOF_SHA is not on $ORIGIN_REF" >&2; exit 1; }
    parent_line="$(git -C "$ROOT" rev-list --parents -n 1 "$PROOF_SHA")"
    parent_count="$(printf '%s\n' "$parent_line" | awk '{print NF-1}')"
    [ "$parent_count" = "1" ] \
      || { echo "HALT: squash proof must be a one-parent commit" >&2; exit 1; }
    PROOF_PARENT="$(printf '%s\n' "$parent_line" | awk '{print $2}')"
    # Three-dot, from DIFF_BASE_SHA — same window the gate computed diff_files from, and the same
    # reasoning as the live_diff_hash recompute above: BASE_SHA is the pinned legitimacy base, not the
    # diff window.
    feature_files="$(git -C "$ROOT" diff --name-only --no-renames "$DIFF_BASE_SHA...$HEAD_SHA" | sort)"
    proof_files="$(git -C "$ROOT" diff --name-only --no-renames "$PROOF_PARENT" "$PROOF_SHA" | sort)"
    [ -n "$feature_files" ] && [ "$feature_files" = "$proof_files" ] \
      || { echo "HALT: squash proof file set does not equal the READY feature file set" >&2; exit 1; }
    proof_diff_hash="$(git -C "$ROOT" diff --binary "$PROOF_PARENT" "$PROOF_SHA" | shasum -a 256 | awk '{print $1}')"
    [ "$proof_diff_hash" = "$DIFF_SHA256" ] \
      || { echo "HALT: squash proof binary diff does not exactly equal the READY diff" >&2; exit 1; }
  fi
else
  HEAD_SHA="$(git -C "$ROOT" rev-parse --verify "$BR^{commit}" 2>/dev/null || true)"
  echo "AUTHORIZED_CLOSE: no merge claim; branch history will be retained."
fi

record_root="$ROOT/.autopilot"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
operator="${USER:-unknown}"
if [ "$MODE" = "close" ]; then
  record_dir="$record_root/dispositions"
  record_file="$record_dir/$SLUG.json"
  record_status="authorized_close"
else
  record_dir="$record_root/landings"
  record_file="$record_dir/$SLUG.json"
  record_status="landed"
fi
mkdir -p "$record_dir"
command -v node >/dev/null 2>&1 || { echo "HALT: node is required to write the durable record" >&2; exit 1; }
node - "$record_file" "$SLUG" "$record_status" "$MODE" "$REASON" "$BASE_SHA" "$HEAD_SHA" "$PROOF_SHA" "$timestamp" "$operator" <<'NODE'
const fs = require("fs");
const [
  file, feature, status, mode, reason, baseSha, headSha, proofSha, timestamp, operator,
] = process.argv.slice(2);
fs.writeFileSync(file, `${JSON.stringify({
  schema_version: "level3-disposition-v1",
  feature,
  status,
  mode,
  reason: reason || null,
  base_sha: baseSha || null,
  head_sha: headSha || null,
  origin_proof_sha: proofSha || null,
  recorded_at: timestamp,
  recorded_by: operator,
}, null, 2)}\n`);
NODE

if [ -d "$WT" ]; then
  # STATE lives nested inside the worktree (.autopilot/worktrees/<slug>/.autopilot/state/<slug>/),
  # gitignored, uncommitted -- design-probe.md, HALT/AWAIT history, every gate-attempt/codex-review
  # artifact. `git worktree remove` deletes it unconditionally along with everything else. Archive it
  # OUTSIDE the worktree first, by default, so the design reasoning and review evidence survive
  # disposal the same way the code already does via git. See docs/autopilot-LESSONS.md L67 for the
  # same byte/mtime-identical quality bar applied to the narrower single-HALT-file case this generalizes.
  if [ "$NO_ARCHIVE" -eq 1 ]; then
    echo "SKIPPED archive: --no-archive requested for $SLUG."
  elif [ -d "$STATE" ]; then
    archive_timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    archive_dir="$ROOT/.autopilot/state-archive/${SLUG}-${archive_timestamp}"
    if [ -e "$archive_dir" ]; then
      echo "HALT: archive destination already exists: $archive_dir" >&2
      exit 1
    fi
    mkdir -p "$archive_dir"
    cp -Rp "$STATE" "$archive_dir/state"
    echo "archived: $STATE -> $archive_dir/state"
  else
    echo "no state directory to archive for $SLUG (nothing under $STATE)."
  fi
  git -C "$ROOT" worktree remove "$WT"
  echo "worktree removed: $SLUG"
else
  echo "worktree already absent: $SLUG"
fi

"$SCOPE_GATE" cleanup --feature "$SLUG"

if [ "$MODE" = "ancestor" ] && git -C "$ROOT" rev-parse --verify --quiet "$BR" >/dev/null 2>&1; then
  if git -C "$ROOT" branch -D "$BR" >/dev/null 2>&1; then
    echo "origin-verified branch deleted: $BR"
  else
    echo "WARN: landing/reservation cleanup succeeded, but local branch remains: $BR" >&2
  fi
elif git -C "$ROOT" rev-parse --verify --quiet "$BR" >/dev/null 2>&1; then
  echo "branch retained for forensic/manual deletion: $BR"
fi

if [ -x "$ROOT/scripts/autopilot-backlog-reconcile" ]; then
  echo "backlog reconciliation is intentionally not committed or pushed by ap-finish."
  echo "run the project-authorized reconcile/commit flow separately."
fi

case "$MODE" in
  ancestor) echo "DONE: origin merge and READY-bound feature tip verified; cleanup recorded." ;;
  squash) echo "DONE: origin squash patch equals the READY feature diff; cleanup recorded." ;;
  close) echo "DONE: explicit unmerged disposition saved at $record_file; branch retained." ;;
esac
