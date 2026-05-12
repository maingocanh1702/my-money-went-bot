# Execution prompt — Autopilot blockers v0.2.0 (Mode 3 batch)

> **Purpose:** Paste into a fresh Claude Code session in `/Users/maingocanh/Projects/MyMoneyWent`.
> Claude Code will resolve all 5 pre-pilot blockers from `docs/operations/autopilot-implementation-plan.md` v0.1.6 on a **single chained branch** without merging to main.
> Founder runs Codex review + manual squash-merge after Claude Code reports complete.
>
> **Estimated runtime:** 2-4 hours of Claude Code execution.
> **Founder intervention during run:** only if circuit breaker trips.
> **Founder workload after:** 1 batch session (~30-60 min) for Codex review + squash-merge.

---

```
===PROMPT START===

# Task: Resolve all 5 autopilot pre-pilot blockers per implementation plan v0.1.6

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant personal finance bot. NO prior conversation context. This prompt
is self-contained.

**Mode:** AUTOPILOT — execute all 5 blocker fixes sequentially on a single
chained branch. NO merge to main. NO Codex review during run (founder runs
Codex + squash-merge after). Pause ONLY on circuit-breaker conditions.

## Required reading (READ FIRST, in this order, before writing any code)

1. `docs/operations/autopilot-implementation-plan.md` — your spec. Read in full.
   The 5 blockers are in §2. Acceptance criteria, severity, and effort for each
   are documented there. Treat that doc as source of truth; this prompt
   summarizes execution order only.
2. `docs/operations/development-workflow.md` §2 (10-step), §6 (anti-patterns).
3. `docs/operations/wave0-retrospective.md` §1 (sandbox-vs-terminal git is real),
   §3 (Codex required for foundation), §4 (5-category test plan upfront).
4. `tools/autopilot/{claude_codegen,state,merge,loop,__main__,git_ops}.py` —
   current implementation you'll modify.
5. `docs/operations/orchestrator-usage.md` — current CLI surface.
6. `docs/features/feature-settings.md` + `docs/features/BE/feature-settings-tech.md`
   — the F07 spec you'll migrate (Blocker #3).

## Pre-flight checks (run first, HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean
git branch --show-current               # MUST be: main
git log --oneline -3                    # 12d8fb5 docs(autopilot)... or later

source .venv/bin/activate
which claude codex                      # both MUST resolve
claude --version                        # capture for probe step
codex --version                         # capture

ruff check tools/ tests/unit/test_autopilot_*.py
black --check tools/ tests/unit/test_autopilot_*.py
mypy tests/unit/test_autopilot_*.py
lint-imports
pytest tests/unit/test_autopilot_*.py -v
```

ALL must pass. If any fails, HALT and report. Do not proceed.

## Branch creation (single chain for all 5 blockers)

```bash
git checkout -b chore/autopilot-blockers-v0.2.0
```

All commits land on this branch. NO merge during run.

## Anti-patterns (NEVER do)

- Probe `claude -p` behavior in real repo (use git worktree — Blocker #1).
- Skip 10-step workflow (read spec first, plan, code+tests, atomic commits).
- Mock Postgres in any new test (use testcontainers if DB involved — N/A here).
- Auto-merge any PR (Mode 3 strict).
- Invoke Codex during run (founder runs in batch).
- More than 2 active branches (you only need 1: chore/autopilot-blockers-v0.2.0).
- `# type: ignore` without circuit-breaker (founder approval required).
- Skip CHANGELOG entry (workflow §2.6 mandatory).
- Use sandbox/Cowork session for git ops — this prompt assumes you ARE the
  Mac terminal authority.

## Execution order (5 blockers — DO IN THIS ORDER)

The order is chosen so cheap independent fixes ship first, and Blocker #1's
probe outcome decides Blocker #2's implementation path.

### Step 1 — Blocker #1: Probe `claude -p` behavior + fix codegen success detection

**Why first:** Blocker #2 decision depends on probe outcome. Also de-risks the
biggest unknown.

**Probe in throwaway worktree (NEVER on real repo):**

```bash
git worktree add /tmp/mmw-claude-probe main
cd /tmp/mmw-claude-probe

# Probe 0: capture available flags
claude --help 2>&1 | tee /tmp/claude-help.txt
grep -iE "max-turns|turns|iterate|continue|headless|print" /tmp/claude-help.txt

# Probe 1: read + bash invocation (read-only, safe)
claude -p "Read README.md, output its line count, then run \`git status\` and report" \
  2>&1 | tee /tmp/claude-probe-1.txt

# Probe 2: file write + commit behavior (worktree throwaway)
claude -p "Add a comment line '# probe' to top of CHANGELOG.md, then git commit it with message 'probe: claude cli test'. Report what you did." \
  2>&1 | tee /tmp/claude-probe-2.txt

# Inspect what Claude actually did
git log --oneline -3
git status
git diff HEAD~1 2>/dev/null || true

# Cleanup — worktree never touched real repo
cd /Users/maingocanh/Projects/MyMoneyWent
git worktree remove /tmp/mmw-claude-probe --force
```

**Document probe findings** in `.autopilot/probes/claude-cli-2026-05-12.md`
(create dir if missing). Capture:
- Does `claude -p` execute bash tools? (Y/N + evidence)
- Does `claude -p` auto-commit when asked? (Y/N + evidence)
- Does `claude -p` support `--max-turns` or equivalent multi-turn flag?
  (flag name + behavior, OR "single-shot only")
- Output format observations (preamble length, structured markers, exit code).

**Fix `tools/autopilot/claude_codegen.py` based on probe outcome:**

- **Common:** save `claude_codegen` stdout/stderr to
  `.autopilot/state/<feature>/codegen-N.log` per invocation (folds NTH-2 into
  this Blocker per plan §4).
- **If probe shows Claude commits:** add fallback orchestrator-side commit
  ONLY when `commits_added == 0 AND working_tree_dirty`. Use commit message
  `feat({feature_id}): autopilot codegen output (orchestrator-fallback commit)`.
- **If probe shows Claude doesn't commit:** after `_invoke_claude` completes,
  always check working tree; if dirty, run
  `git add -A && git commit -m "feat({feature_id}): autopilot codegen output"`.
  Update `success` calculation: `success = (returncode==0 AND not halted AND
  (commits_added > 0 OR working_tree_was_dirty))`.

**Add unit tests** for new fallback commit path (use a tmp git repo fixture).

**Commit (atomic):**
- `chore(autopilot): probe claude -p behavior; capture findings` (the probe
  notes file + .autopilot/probes/ dir if needed)
- `fix(autopilot): codegen fallback commit + log capture (Blocker #1, NTH-2)`

### Step 2 — Blocker #4: Atomic state.json write (independent, quick)

**Action:** in `tools/autopilot/state.py`'s `save()`:

```python
tmp = path.with_suffix(".json.tmp")
tmp.write_text(state.to_json(), encoding="utf-8")
tmp.replace(path)  # atomic on POSIX
```

Ensure tmp cleanup on exception (use try/finally if needed).

**Add unit test** simulating mid-write crash: write 1 byte to .tmp, ensure
load() still succeeds with previous good state.

**Commit:** `fix(autopilot): atomic state.json write (Blocker #4)`

### Step 3 — Blocker #5: Implement `--auto-merge` opt-in flag

**Default behavior MUST become safe (no merge unless explicit opt-in).**

In `tools/autopilot/__main__.py`:
- Add `--auto-merge` flag to `run` and `resume` subparsers (action='store_true',
  default=False).
- Pass `auto_merge=args.auto_merge` to `loop.run`.
- Print warning + interactive prompt when `--auto-merge` is passed:
  ```
  WARNING: --auto-merge enabled. Per implementation-plan §6.5, only P2 features
  qualify for auto-merge. Continue? (y/N)
  ```
  Read stdin; abort if not 'y'/'Y'.
- Refuse `--auto-merge` if spec's `risk_tier` (parsed from autopilot:meta block)
  is P0 or P1. Print error and exit code 4.

In `tools/autopilot/loop.py`:
- Add `auto_merge: bool = False` keyword arg to `run()`.
- In Phase D/E section: if `not auto_merge`, after Phase C transitions to READY,
  call new `_write_ready_report(cfg, feature_state)` and return RunOutcome with
  `final_phase="READY"`, `halted=False`, summary mentioning manual merge needed.
- If `auto_merge=True`, behavior unchanged (calls `merge.attempt_merge`).

In `tools/autopilot/loop.py` add helper:
```python
def _write_ready_report(cfg: Config, state_obj: FeatureState) -> Path:
    """Write .autopilot/state/<feature>/ready-report.md with branch info,
    commits ahead, dry-run merge result, suggested squash command, smoke
    checklist."""
    ...
```

**Risk-tier parsing:** parse `risk_tier:` from spec's `<!-- autopilot:meta -->`
block. If meta block missing or no risk_tier field, treat as P1 (refuse
auto-merge). Add helper to `spec_lint.py` (or new `spec_meta.py`) since lint
already parses meta block.

**Add unit tests:**
1. `loop.run(..., auto_merge=False)` does NOT call `merge.attempt_merge`; DOES
   write ready-report; final_phase == "READY".
2. `loop.run(..., auto_merge=True)` does call `merge.attempt_merge` (mock it).
3. CLI without `--auto-merge` → loop receives `auto_merge=False`.
4. CLI with `--auto-merge` → confirmation prompt appears (mock stdin 'y');
   loop receives `auto_merge=True`.
5. CLI with `--auto-merge` on P0/P1 risk_tier spec → exit code 4 without prompt.

**Update `docs/operations/orchestrator-usage.md`** §"CLI commands" to document
the new flag + safe-default behavior.

**Commit (atomic, multiple OK):**
- `feat(autopilot): risk-tier parser from autopilot:meta block (Blocker #5 prep)`
- `feat(autopilot): --auto-merge opt-in flag with safe-default off (Blocker #5)`
- `feat(autopilot): ready-report writer for manual-merge pilot (Blocker #5)`
- `test(autopilot): coverage for auto_merge=False/True paths`
- `docs(autopilot): orchestrator-usage --auto-merge flag`

### Step 4 — Blocker #2: Multi-turn vs chunked codegen (depends on Step 1 probe)

**If Step 1 probe found multi-turn flag (e.g. `--max-turns N`):**
- In `claude_codegen.py`, add the flag to the subprocess call with a sane
  default (e.g. `--max-turns 30`).
- Add config field `Config.claude_max_turns: int = 30`.
- Update unit tests to assert flag is passed.
- ETA: 15 min. Skip the rest of this step.

**If Step 1 probe found single-shot only (Option A — DEFAULT per plan):**
- Refactor `run_codegen` into 4 sequential `_invoke_claude` calls (chunks).
  Each chunk has a focused prompt + done marker:
  - Chunk i: read FE+BE spec, output 10-line plan to `.autopilot/state/<feature>/plan.md`. Done marker: `AUTOPILOT_CHUNK_I_PLAN_DONE`.
  - Chunk ii: write code skeleton + import structure, commit. Done marker: `AUTOPILOT_CHUNK_II_SKELETON_DONE`.
  - Chunk iii: write tests for all 5 categories per autopilot:test_plan, commit. Done marker: `AUTOPILOT_CHUNK_III_TESTS_DONE`.
  - Chunk iv: run local verify + fix until green, commit. Done marker: `AUTOPILOT_CHUNK_IV_VERIFIED_DONE`.
- Each chunk's prompt MUST reference the prior chunk's commit so context flows
  through git rather than through claude session memory.
- Halt if any chunk's done marker is missing or the chunk produces zero commits.
- Add unit test asserting all 4 chunks invoked in sequence.

**Commit:**
- `feat(autopilot): chunked codegen driver (Blocker #2 Option A)` OR
- `feat(autopilot): claude --max-turns wiring (Blocker #2 multi-turn)`

### Step 5 — Blocker #3: Migrate F07 (Settings) spec to template format

**Read first:**
- `docs/features/feature-settings.md`
- `docs/features/BE/feature-settings-tech.md`
- `docs/operations/spec-template.md` (template you'll match)
- Memory note `project_phase4_phase5_decisions.md` if it mentions F07
- `docs/implementation-tracker.md` row F07 (for branch name + phase + wave)

**Then add 3 blocks to `docs/features/feature-settings.md`:**

1. `<!-- autopilot:meta -->` with:
   ```
   feature_id: F07
   branch: feat/F07-settings
   phase: 2
   wave: 1
   risk_tier: P1
   depends_on: []
   be_doc: docs/features/BE/feature-settings-tech.md
   ```

2. `<!-- autopilot:gaps -->` — list every unknown you find while reading the
   spec. Each gap MUST be CLOSED with a locked decision + rationale, OR
   DEFERRED:<location>. If you cannot lock a decision because it requires
   founder judgment (e.g. tier-based limits, defaults), HALT with circuit
   breaker — do not invent decisions.

3. `<!-- autopilot:test_plan -->` with all 5 categories filled per spec
   acceptance criteria. Mark categories N/A only if spec genuinely doesn't have
   that surface (e.g. retry/idempotency for pure CRUD reads).

**Verify:** `python -m tools.autopilot lint F07` MUST report 0 warnings AND 0
errors. If any open gap remains → HALT.

**Commit:** `docs(F07): migrate settings spec to autopilot template format (Blocker #3)`

### Step 6 — Final verification

```bash
ruff check tools/ tests/
black --check tools/ tests/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
python -m tools.autopilot lint F07          # MUST be 0 warnings
python -m tools.autopilot preflight         # ALL 6 checks PASS
```

ALL must pass. Update CHANGELOG.md with single combined entry under
`## [Unreleased]`:

```markdown
### Added
- Autopilot orchestrator v0.2.0: --auto-merge opt-in flag, atomic state write,
  chunked-codegen driver (or multi-turn wiring per probe), claude-CLI fallback
  commit, F07 spec migrated to autopilot template format.

### Changed
- Default `python -m tools.autopilot run <feature>` behavior: stops at READY
  (no auto-merge). Pass `--auto-merge` explicitly to enable, only for P2
  features per implementation-plan §6.5.

### Notes
- Resolves Blockers #1-#5 from docs/operations/autopilot-implementation-plan.md
  v0.1.6. F07 pilot now unblocked.
```

Commit: `chore: changelog for autopilot blockers v0.2.0`

## Circuit breakers (HALT and report)

PAUSE immediately and write report to
`.autopilot/state/blockers-v0.2.0/halt-report.md` if ANY of these happen:

1. **Probe Step 1 reveals Claude CLI is fundamentally incompatible** with our
   assumptions (e.g. `-p` flag doesn't exist, no bash tool access, requires
   interactive auth).
2. **Spec gap discovered during F07 migration** that requires founder design
   decision (don't invent defaults for tier limits, schema changes, UX flow).
3. **mypy --strict requires `# type: ignore`** in any new code (founder
   approval needed).
4. **Local verify fails 3 times in a row** for the same blocker (don't loop
   forever).
5. **Test failure in EXISTING tests** caused by your changes (regression).
6. **detect-secrets flags a NEW finding** (real or false positive).
7. **import-linter contract broken** by new code (architecture violation).
8. **You're about to disable a circuit breaker, lower a verify gate, or skip
   tenant isolation test** to "make things pass" (NEVER do this).
9. **Cumulative context concern:** if context >70% used, pause + report.
   Founder will resume in fresh session.
10. **Tool errors** twice in a row on the same operation. Don't retry blindly.

### Halt report template

```
HALT — Autopilot blockers run circuit broken.

Branch: chore/autopilot-blockers-v0.2.0
Last completed step: <Blocker # / sub-step>
Failing step: <Blocker # / sub-step>
Trigger: <one of 10 conditions>

Detail:
<error output, decision needed, evidence>

State:
- Commits on branch so far: <list with SHAs>
- Files changed: <list>
- Probe findings: .autopilot/probes/claude-cli-*.md (if Step 1 done)
- Last verify result: <pass|fail with details>

Requesting founder input on:
<specific question, e.g. "F07 spec doesn't define default tz; what to use?">
```

## Final report (when all 6 steps complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT BLOCKERS v0.2.0 COMPLETE — Ready for batch review
═══════════════════════════════════════════════════════

Branch: chore/autopilot-blockers-v0.2.0
Total commits: <count>
Files changed: <count> (+<X>/-<Y>)

Blockers resolved:
1. Blocker #1 (claude -p probe + codegen fallback): <commits>
2. Blocker #4 (atomic state write): <commits>
3. Blocker #5 (--auto-merge opt-in flag): <commits>
4. Blocker #2 (<multi-turn flag | chunked Option A>): <commits>
5. Blocker #3 (F07 spec migration): <commits>

Local verification: ALL PASS
- ruff: clean
- black: clean
- mypy: clean
- lint-imports: 4 contracts kept
- pytest: <count> passed, <count> skipped, <count> xfail
- autopilot lint F07: 0 warnings
- autopilot preflight: all 6 PASS

Probe findings (Blocker #1):
- claude -p multi-turn flag: <name | not found>
- Claude auto-commits: <Y | N>
- Bash tool available: <Y | N>
- Output format quirks: <list>
- Decision: <multi-turn used | chunked Option A used>

Decisions made during execution requiring founder review:
- <list any non-obvious choices>

Anti-patterns encountered but resolved:
- <list any near-misses>

To merge:
  git checkout main
  codex review --base main                # cross-model audit (recommended)
  # If clean OR findings addressed:
  git merge --squash chore/autopilot-blockers-v0.2.0
  git commit -m "chore: autopilot v0.2.0 — pre-pilot blockers resolved"
  git branch -D chore/autopilot-blockers-v0.2.0
  git push origin main

After merge:
  Update docs/operations/autopilot-implementation-plan.md changelog with
  v0.2.0 entry: blockers resolved, ready for F07 pilot.

End of autopilot blockers run.
═══════════════════════════════════════════════════════
```

Then STOP. Founder reviews + Codex audits + manually merges.

## Global rules (apply throughout)

1. READ SPEC FIRST for each blocker. Don't write code blind.
2. NEVER skip 10-step workflow.
3. NEVER mutate real `core/` for tests (use tmp_path or worktree).
4. NEVER commit secrets (detect-secrets blocks).
5. NEVER auto-merge anything (Mode 3 strict).
6. NEVER invoke Codex during run (founder runs after).
7. NEVER use sandbox/Cowork — you ARE the Mac terminal authority.
8. If unsure on architecture, trigger circuit breaker. Do not guess.
9. Use TodoWrite tool to track sub-steps per blocker.
10. Memory hygiene: if you make a non-obvious decision, save brief memory note
    via the auto-memory system for future sessions.
11. Verify before claiming done: re-run tests after "tests pass" message.
12. Tool errors twice in row → circuit breaker, don't retry blindly.
13. Context budget: if >70% context used, trigger circuit breaker so founder
    can resume in fresh session with state intact.
14. Atomic commits per blocker (multiple commits per blocker is fine; one
    monster commit is not).

Begin with Pre-flight, then Step 1. No further confirmation needed — execute
through Step 6 final report.

===PROMPT END===
```

---

## How to use

1. Confirm `main` clean: `git status`, `git log --oneline -1` shows `12d8fb5` or later.
2. Open fresh Claude Code session in `/Users/maingocanh/Projects/MyMoneyWent`.
3. Paste everything between `===PROMPT START===` and `===PROMPT END===`.
4. Walk away (~2-4h).

## What to expect

**Happy path (no circuit breaker):**

- Claude Code outputs progress for each blocker (probe results, files changed, commits, local verify pass).
- Final report after Step 6.
- Branch `chore/autopilot-blockers-v0.2.0` ready for founder review.

**Circuit breaker tripped:**

- Claude Code outputs HALT report at `.autopilot/state/blockers-v0.2.0/halt-report.md`.
- Founder reads, decides path forward, sends Claude Code an unblock message; execution resumes.

## Batch review session (after autopilot completes)

```bash
git checkout chore/autopilot-blockers-v0.2.0
codex review --base main                              # cross-model audit
# Address P0/P1 findings on the branch (manually or via Claude Code interactive)
# Re-run codex if fixes applied:
codex review --base main

# When clean:
git checkout main
git merge --squash chore/autopilot-blockers-v0.2.0
git commit -m "chore: autopilot v0.2.0 — pre-pilot blockers resolved"
git branch -D chore/autopilot-blockers-v0.2.0
git push origin main
```

## Recovery if Claude Code goes off-script

If Claude Code violates Mode 3 rules (auto-merges, invokes Codex during run, skips tests):

```bash
git checkout main
git branch -D chore/autopilot-blockers-v0.2.0
rm -rf .autopilot/state/blockers-v0.2.0/
# Re-paste prompt with note: "Previous run violated rule [X]. Restart from Step Y."
```

## Budget warning

5 blockers + ~2-4h of Claude Code execution = significant token consumption. Monitor context. If Claude Code pauses with "context budget" circuit breaker, that's working as designed — resume in fresh session.

---

## Cross-references

- [Implementation plan v0.1.6](../autopilot-implementation-plan.md) — source of truth for what each blocker means
- [Wave 0 autopilot prompt](./wave0-autopilot.md) — Mode 3 batch pattern this prompt follows
- [Level 3 template](./level3-autopilot-template.md) — per-feature autopilot pattern (different mode)
- [Development workflow](../../operations/development-workflow.md) §2 — 10-step per-feature
- [Wave 0 retrospective](../../operations/wave0-retrospective.md) — 7 lessons embedded in this prompt
