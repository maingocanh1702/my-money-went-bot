#!/usr/bin/env bash
# KIT_VERSION: 3
# Repo-agnostic pinned Codex wrapper for Level 3 independent review.
# v3 (2026-08-04) — the pinned `codex exec --ephemeral` call (the --base adapter path below) now
# redirects stdin from /dev/null. Per `codex exec --help`: "[PROMPT] ... If not provided as an
# argument (or if `-` is used), instructions are read from stdin. If stdin is piped and a prompt is
# ALSO provided, stdin is appended as a `<stdin>` block" -- `codex exec` consults stdin even when a
# full prompt is already supplied as a CLI argument, exactly this wrapper's usage. A caller that
# leaves stdin open/unredirected (e.g. backgrounding this wrapper with `&` from an interactive
# terminal, or any standalone invocation during iterative fix rounds) previously hung the process
# forever waiting for an EOF nothing would ever send. Root-caused 2026-08-03 (see
# docs/autopilot-backlog.md task codex-review-pin-stdin-hang and docs/autopilot-LESSONS.md L18
# "Nguyên nhân 2" in the Bestminton Club Payment check bot consumer): two hung rounds sat at PIDs
# alive for 3 days, ~1:40 accumulated CPU time each, output frozen at exactly 39 bytes -- the ENTIRE
# file content being only "Reading additional input from stdin...". That banner line alone is NOT
# evidence of a hang -- codex prints it as routine startup noise on every invocation, including large
# completed reviews. The corpse signature is that banner being the WHOLE file, not one line among
# hundreds of KB of real review output.
# Deliberately NOT redirected: the native `review "$@"` passthrough two lines below, and the generic
# catch-all at the bottom (`exec "$REAL_BIN" "$@"`, used for `codex login`/`codex logout` among other
# native subcommands). `codex review --help` documents a NARROWER, opt-in contract than `exec`:
# "[PROMPT] ... If `-` is used, read from stdin" -- no "append if piped" behavior, and no reading at
# all unless the prompt is exactly `-`. An earlier version of this fix (KIT_VERSION 3, first cut)
# blanket-redirected the native passthrough too and broke that `-` convention outright (a real caller
# piping a prompt via `review -` would have silently gotten an empty one instead) -- caught by a real
# review round on this exact diff, not by inspection. Both documented incidents' `ps aux` evidence
# also specifically shows the adapter's `exec --sandbox read-only --ephemeral <prompt>` invocation
# shape, never the native passthrough. `codex login`/`codex logout` additionally have their own
# legitimate stdin uses (`--with-api-key`/`--with-access-token` read credentials from stdin by
# design; this repo's own L18 auth-death remediation is `"$CODEX" logout && "$CODEX" login`, which
# needs a real interactive session) -- the generic catch-all must stay untouched for that reason too.
set -euo pipefail

REAL_BIN="${AUTOPILOT_CODEX_REAL_BIN:-$HOME/.npm-global/bin/codex}"
REVIEW_MODEL="${AUTOPILOT_CODEX_REVIEW_MODEL:-gpt-5.6-sol}"
REVIEW_EFFORT="${AUTOPILOT_CODEX_REVIEW_EFFORT:-xhigh}"
REVIEW_TIER="${AUTOPILOT_CODEX_REVIEW_TIER:-priority}"

[ -x "$REAL_BIN" ] || {
  echo "CODEX_UNAVAILABLE: set AUTOPILOT_CODEX_REAL_BIN to an executable Codex CLI" >&2
  exit 1
}

PIN_FLAGS=(
  -m "$REVIEW_MODEL"
  -c "model_reasoning_effort=\"$REVIEW_EFFORT\""
  -c "service_tier=\"$REVIEW_TIER\""
  -c "mcp_servers={}"
)

if [ "${1:-}" = "review" ]; then
  shift
  # Codex CLI 0.144.5 exposes a [PROMPT] in `review --help` but rejects a custom prompt when
  # --base/--commit/--uncommitted is also present. The Level 3 gate needs both an immutable base
  # and exact verdict markers, so adapt that one stable contract to a read-only ephemeral exec.
  # Other review invocations retain the native subcommand.
  if [ "${1:-}" = "--base" ] && [ "$#" -eq 3 ]; then
    REVIEW_BASE="$2"
    MARKER_PROMPT="$3"
    case "$REVIEW_BASE" in
      ""|*[!0-9a-fA-F]*)
        echo "CODEX_REVIEW_CONTRACT_INVALID: --base must be a full commit SHA" >&2
        exit 2
        ;;
    esac
    case "${#REVIEW_BASE}" in
      40|64) ;;
      *)
        echo "CODEX_REVIEW_CONTRACT_INVALID: --base must be a full commit SHA" >&2
        exit 2
        ;;
    esac
    case "$REVIEW_BASE" in
      *[1-9a-fA-F]*) ;;
      *)
        echo "CODEX_REVIEW_CONTRACT_INVALID: --base must be a real nonzero commit SHA" >&2
        exit 2
        ;;
    esac
    PINNED_REVIEW_PROMPT="$(
      printf '%s\n' \
        "Act as the independent code reviewer for the current repository." \
        "Review only the non-empty change set from: git diff $REVIEW_BASE...HEAD" \
        "Treat $REVIEW_BASE as the immutable review base. Do not edit files or mutate repository state." \
        "Inspect live source and run read-only verification needed to support the verdict." \
        "An ACTIONABLE finding must be closable by editing the change set itself. Repo-wide staleness," \
        "pre-existing defects and work belonging to other slices are real and worth reporting, but they" \
        "are NOT actionable here: list them under a heading 'ADVISORY (outside change set)' and exclude" \
        "them from the verdict. A writer cannot edit files outside its registered scope, so a verdict" \
        "gated on those findings can never be satisfied and the slice loops until a breaker fires." \
        "" \
        "$MARKER_PROMPT"
    )"
    exec "$REAL_BIN" "${PIN_FLAGS[@]}" exec --sandbox read-only --ephemeral "$PINNED_REVIEW_PROMPT" < /dev/null
  fi
  exec "$REAL_BIN" "${PIN_FLAGS[@]}" review "$@"
fi

exec "$REAL_BIN" "$@"
