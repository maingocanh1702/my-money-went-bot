# Probe: `claude -p` behavior — 2026-05-12

> Blocker #1 prerequisite probe per `docs/operations/autopilot-implementation-plan.md` v0.1.6 §2.
> Executed in throwaway worktree `/tmp/mmw-claude-probe` (now removed). Real repo untouched.

## Environment

- `claude --version`: `2.1.138 (Claude Code)` (aliased to `claude --model claude-opus-4-6`)
- `codex --version`: `codex-cli 0.130.0`
- Probe date: 2026-05-12

## Findings

### F1 — Multi-turn flag

**NOT FOUND.** `claude --help` lists no `--max-turns`, `--turns`, `--iterate`, or `--continue`-style flag suitable for orchestrator-driven multi-turn execution within a single `-p` invocation.

Relevant flags present: `-p/--print` (single-shot non-interactive), `-c/--continue` (interactive resume only), `-r/--resume` (interactive resume only), `--session-id` (specify session). None enable autonomous multi-turn in print mode.

**Decision impact (Blocker #2):** Option A (chunked prompts, orchestrator drives) is the locked path. Multi-turn flag wiring is not viable.

### F2 — File read

**WORKS.** `claude -p "Read README.md..."` returned correct line count (265). Read tool invocations succeeded silently in `-p` mode.

### F3 — Bash invocation

**WORKS.** Same prompt issued `git status` via Bash and returned correct working-tree state. Bash tool is available in `-p` mode by default (no flag needed).

### F4 — File write

**WORKS.** Probe 2 asked Claude to add `# probe` to top of CHANGELOG.md. Inspection post-run showed CHANGELOG.md modified with the comment line at top, `.secrets.baseline` also touched (auto-updated by pre-commit hook).

### F5 — Auto-commit behavior

**PARTIAL / UNRELIABLE.** Probe 2 asked Claude to also `git add` + `git commit`. Result:

- Claude staged files (`git status` showed `Changes to be committed`).
- Claude attempted commit but pre-commit hook (`lint-imports`) failed because the throwaway worktree had no `.venv`.
- Claude DID NOT auto-resolve — instead it printed a question to the user ("Skip hooks? Create venv? Abort?") and exited.
- In `-p` mode there is no way for Claude to receive the answer → effectively single-shot stop.
- Working tree was left dirty + staged on exit.

**Implication:** The current `claude_codegen.py` success check `commits_added > 0` is brittle. Claude may:

1. Commit cleanly (happy path) — `commits_added > 0`.
2. Stage but fail commit (e.g. pre-commit hook fail, ambiguous prompt) — `commits_added == 0`, working tree dirty.
3. Halt with question — `commits_added == 0`, working tree dirty.

The orchestrator MUST fall back: if Claude returns with no new commits AND working tree is dirty, attempt orchestrator-side `git add -A && git commit -m "..."` so progress is preserved on the branch. Otherwise the codegen artifact is lost and resume cannot proceed.

### F6 — Output format

- Default stdout is human-prose markdown — no structured markers in our probe.
- Done-markers like `AUTOPILOT_PHASE_A_COMPLETE` are achievable only by explicitly instructing Claude to print them (the current prompt template does this).
- Exit code: 0 on both probes (even when Claude asked a question rather than completing the commit task).

**Implication:** Returncode is NOT a reliable success signal alone. Must combine with: done-marker presence, halt-marker absence, and commit/working-tree state.

### F7 — Permission prompts in -p mode

In default `-p` (no `--permission-mode`), Claude proceeded with Read/Bash/Edit on a worktree without interactive prompts blocking it. This matches existing assumption in `claude_codegen.py`. (We did NOT test `--permission-mode bypassPermissions` because the parent harness refuses to spawn child claude with that flag — but that flag is NOT needed for default behavior to function.)

## Probe summary table

| Question | Answer | Evidence |
|----------|--------|----------|
| `claude -p` runs Read tool? | YES | Probe 1 returned correct line count |
| `claude -p` runs Bash tool? | YES | Probe 1 returned `git status` output |
| `claude -p` writes files? | YES | Probe 2 modified CHANGELOG.md |
| `claude -p` auto-commits when asked? | UNRELIABLE | Probe 2 staged but hit pre-commit fail; left dirty tree, asked user a question |
| `claude --max-turns N` or equivalent? | NO | `claude --help` shows no multi-turn flag for `-p` |
| Exit code reliable for success? | NO | Probe 2 returned 0 despite incomplete task |
| Done-marker in default output? | NO | Must be explicitly prompted |

## Required code changes (drives the Blocker #1 fix)

1. Capture stdout/stderr to `.autopilot/state/<feature>/codegen-N.log` per invocation (subsumes NTH-2 per plan §4).
2. Replace brittle `success = commits_added > 0` with composite check:
   - `return_code == 0`
   - `AUTOPILOT_HALT` not in stdout
   - Done marker present OR `commits_added > 0`
   - If `commits_added == 0` AND working tree dirty → orchestrator-side fallback commit, then `success = True`.
3. Fallback commit message: `feat({feature_id}): autopilot codegen output (orchestrator-fallback commit)`.

## Notes / open observations

- The pre-commit hook block in probe 2 is environment-specific (throwaway worktree without `.venv`). In a real autopilot run the project venv is active and pre-commit will function. Still, hook failures during real runs (test regression, mypy fail) will produce the same dirty-tree-no-commit pattern → fallback logic still needed.
- For chunked codegen (Blocker #2 Option A), each chunk invocation will hit the same fallback path independently. That's fine — each chunk's output is preserved via the fallback commit.
