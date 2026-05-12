# Task: Finish autopilot v0.2.1 — apply Codex round 4 P2 fix → 2× clean → squash + push

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT continuation — branch
`chore/autopilot-v0.2.1-codex-parser-fix` already exists with 9 commits;
Codex rounds 1-4 already run. Round 4 surfaced a P2. Apply fix, drive
Codex review to 2× consecutive clean, squash + push, restore stashed
prep files. Pause ONLY on circuit-breaker conditions.

**Context (NOT for execution, just background):**
A prior Claude Code session ran the v0.2.1 fix (parser + halt forensics +
resume-from-HALTED). 4 Codex rounds completed:

- R1: P2 — stale state snapshot in halt report → fixed `f667ad4`
- R2: P1 — overly broad CLEAN_PHRASE `"appear internally consistent"` →
  fixed `0ffacab`
- R3: CLEAN
- R4: P2 — tracker not synced on resume-from-HALTED at READY → **NOT YET FIXED**

R4 verdict (must read before coding):
> When a halted feature is resumed with `last_active_phase == "READY"`,
> the code restores `feature_state.phase` and returns from the READY
> branch without ever calling `tracker.update_status(...)`. Since `_halt`
> previously set tracker status to HALTED, the tracker can remain stale
> (HALTED) even though the run is now READY again, which can mislead
> operational dashboards and follow-up automation that keys off tracker
> state.

Prior session HALTED at MAX_ROUNDS (max_review_rounds=3 budget exhausted
after R1+R2 found legitimate issues). This continuation drives the loop
manually outside the orchestrator's budget — we still respect the
**2× consecutive clean** rule but allow up to 3 MORE rounds (R5, R6, R7).
If not 2× clean by R7, HALT with meta-bug for v0.2.2 backlog.

## Required reading (READ FIRST, in order, before any code)

1. `.autopilot/state/v0.2.1-fix/codex/round-04.txt` — Codex R4 verdict
   with the P2 finding. Read in full.
2. `tools/autopilot/loop.py` — focus on the resume-from-HALTED block (the
   block agent added near the top of `run()`, after
   `existing = state.load(...)`). That's where the tracker.update_status
   call is missing.
3. `tools/autopilot/tracker.py` — confirm `update_status` signature so the
   fix uses correct args.
4. `tests/unit/test_autopilot_resume.py` — new file added by prior session.
   Match style + fixture pattern for the new regression test.
5. `.autopilot/state/v0.2.1-fix/halt-report.md` — prior session halt
   forensics. Useful context.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean (stash holds prep)
git branch --show-current               # MUST be: chore/autopilot-v0.2.1-codex-parser-fix
git log --oneline main..HEAD | wc -l    # MUST be 9
git log --oneline -1                    # MUST start with 0ffacab

git stash list | grep "v0.2.1-preflight-prep"  # MUST exist

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling baseline green
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v                        # MUST be 232 pass (baseline 219 + 13 v0.2.1 new)
```

If branch/commit/stash/pytest count diverges → HALT and report. Do not
proceed.

## Anti-patterns (NEVER do)

- Touch any file outside `tools/autopilot/loop.py` and
  `tests/unit/test_autopilot_resume.py` for the R4 fix.
- `git push --force`.
- Add `# type: ignore` (circuit breaker).
- Pop the stash before squash — it's prep files for AFTER main updates.
- Run more than 3 additional Codex rounds (R5, R6, R7). If not 2× clean
  by R7 → HALT with meta-finding.
- Auto-merge to main without 2× consecutive clean.

---

## Step 1 — Apply R4 P2 fix

**File:** `tools/autopilot/loop.py`

Locate the resume-from-HALTED block in `run()` (added by prior session).
At the END of the HALTED restoration path — AFTER `state.save(...)` but
BEFORE the closing of the `if feature_state.phase == "HALTED":` block —
add a `tracker.update_status` call:

```python
if resume and existing is not None:
    feature_state = existing
    if feature_state.phase == "HALTED":
        if feature_state.last_active_phase is None:
            return _halt(
                cfg,
                feature_state,
                "RESUME_AMBIGUOUS",
                "state.phase=HALTED but last_active_phase is unset. "
                "Edit state.json manually to set phase=VERIFIED (or "
                "appropriate re-entry phase) and current_round=0, then "
                "re-run.",
            )
        print(
            f"Resuming {feature_id} from HALTED — re-entering at "
            f"{feature_state.last_active_phase}"
        )
        feature_state.phase = feature_state.last_active_phase
        feature_state.halt_reason = None
        feature_state.halt_artifact_path = None
        if feature_state.phase in ("VERIFIED", "REVIEWING"):
            feature_state.current_round = 0
            feature_state.consecutive_clean_rounds = 0
        state.save(cfg, feature_state)
        # Codex v0.2.1 r4 P2: _halt set tracker to HALTED on the way down;
        # restoration must propagate to tracker too. Without this, any
        # operational dashboard or follow-up automation keying off tracker
        # state stays stale at HALTED even though the run is now active
        # again. Most user-visible when last_active_phase=READY (Phase D
        # branch never calls tracker.update_status itself).
        tracker.update_status(cfg, feature_id, feature_state.phase)
    else:
        print(f"Resuming {feature_id} from phase {feature_state.phase}")
```

(Block above is illustrative — preserve whatever else prior session put
there; only ADD the new `tracker.update_status(...)` line + its comment.
Don't reformat surrounding lines.)

## Step 2 — Add regression test

**File:** `tests/unit/test_autopilot_resume.py`

Add a new test alongside the existing resume tests. Match their fixture
+ mocking pattern verbatim. Skeleton:

```python
def test_resume_from_halted_at_ready_syncs_tracker(
    tmp_path, monkeypatch
) -> None:
    """Codex v0.2.1 r4 P2 regression — resume from HALTED must propagate
    the restored phase to tracker.

    Setup: state.json on disk with:
      phase=HALTED
      last_active_phase=READY
      halt_reason set (non-None)
      branch + commits assumed intact (Phase D needs them, but for this
      unit test we mock Phase D internals out)

    Mock:
      - tracker.update_status to collect call args
      - any Phase D side-effects (_write_ready_report, git_ops.commit_log,
        etc.) so Phase D returns cleanly without touching real git

    Action: loop.run(cfg, feature_id, resume=True, auto_merge=False)

    Assert:
      - tracker.update_status was called with (cfg, feature_id, "READY")
        as part of the HALTED-restoration block (i.e. before Phase D
        executes). Order matters — capture the call list.
    """
    # ... implementation matching test_autopilot_resume.py style ...
```

Reuse existing helpers/fixtures from the file. If the file has no helper
for "write a state.json to a tmp path", look at how other resume tests
build FeatureState and adapt.

## Step 3 — Local verify

```bash
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
```

ALL pass. Expected count: 233 (232 baseline + 1 new). If any fails → up
to 2 retries to fix root cause. After 2 retries → HALT with
`VERIFY_REGRESSION`.

## Step 4 — Commit R4 fix

```bash
git add tools/autopilot/loop.py tests/unit/test_autopilot_resume.py
git commit -m "fix(autopilot): sync tracker on resume-from-HALTED at READY (Codex r4 P2)

Resume-from-HALTED restored feature_state.phase but did NOT propagate to
tracker. _halt had set tracker='HALTED' on the way down; resume left it
stale. Most visible when last_active_phase=READY — Phase D branch
returns without ever calling tracker.update_status itself.

Caught by Codex round 4 of v0.2.1 review — exactly the case
required_clean_rounds_before_merge=2 exists to surface."
```

## Step 5 — Codex round 5 (post-fix confirmation)

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-05.txt
```

**Parse output:**

- Phrase match `"did not identify any"`, `"did not find any"`,
  `"no actionable"`, or no severity-bracket lines → **CLEAN**.
- Severity-bracket line(s) `[P0|P1|P2|P3]` → findings:
  - Same finding text as round 4 → `RECURRING_FINDING` breaker → HALT.
  - `[P0|P1]` → MUST fix.
  - `[P2|P3]` → fix opportunistically.
  - Keywords `schema design`, `breaking change`, `architectural` →
    `ARCH_FINDING` breaker → HALT.
  - Keywords `auth`, `token leak`, `timing`, `secret`, `injection` →
    `SECURITY_FINDING` breaker → HALT.

**Branching after R5:**

### Branch A — R5 CLEAN

Run R6 directly:

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-06.txt
```

Parse same way.

- **R6 CLEAN** → 2× consecutive clean (R5+R6) confirmed → proceed to Step 6.
- **R6 found something** → fix it (atomic commit
  `fix(autopilot): address codex round 06 — <summary>`), local verify,
  then run R7:

  ```bash
  codex review --base main 2>&1 \
    | tee .autopilot/state/v0.2.1-fix/codex/round-07.txt
  ```

  R7 CLEAN → only 1 consecutive clean (R7 alone) → need 1 more BUT we're
  at R7 budget cap. HALT with `MAX_EXTRA_ROUNDS` and note for v0.2.2
  meta-bug. Document the protocol gap in halt report.

  R7 found something → HALT same way.

### Branch B — R5 found something

Apply minimum-viable fix. Local verify. Commit atomically. Run R6:

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-06.txt
```

- **R6 CLEAN** → 1 consecutive clean. Run R7:

  ```bash
  codex review --base main 2>&1 \
    | tee .autopilot/state/v0.2.1-fix/codex/round-07.txt
  ```

  R7 CLEAN → 2× consecutive (R6+R7) → Step 6.
  R7 found something → HALT (`MAX_EXTRA_ROUNDS`).

- **R6 found something** → HALT (`MAX_EXTRA_ROUNDS`, only 2 budget rounds
  left and we'd need 2 more clean after another fix).

**Budget hard cap: 3 additional rounds (R5, R6, R7).** If R7 ends without
2× consecutive clean → HALT and write halt-report with full sequence.

## Step 6 — Squash + push (only if 2× consecutive clean confirmed)

```bash
# Final local sanity
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v

# Update main pointer
git checkout main
git pull --ff-only origin main

# Dry-run merge — confirm no conflicts
git merge --no-commit --no-ff chore/autopilot-v0.2.1-codex-parser-fix
git merge --abort

# Real squash
git merge --squash chore/autopilot-v0.2.1-codex-parser-fix
git commit -m "fix(autopilot): v0.2.1 — Codex parser + halt forensics + resume-from-HALTED

Resolves 3 bugs surfaced by F07 pilot 2026-05-12:

1. parse_findings early-returned ([], False) when Codex CLI output lacked
   a 'codex' marker line. CLI v0.130 in subprocess context sometimes emits
   only the verdict (~900 bytes); parser now falls back to whole-output
   parsing. Caught the real P2 finding F07 round 1 reported but parser
   ignored.

2. _halt helper now writes halt-report.md unconditionally with state
   snapshot + commits + diffstat + review context. Previously only the
   Codex circuit-breaker path wrote a forensic file.

3. state.transition to HALTED records last_active_phase; loop.run on
   resume re-enters at that phase with Phase-C round counters reset.
   tracker.update_status is propagated on restoration (Codex r4 P2).

Plus: 4 real Codex outputs as tracked fixtures (tests/fixtures/codex/),
PARSER_UNCERTAIN defensive breaker, expanded CLEAN_PHRASES with
phrases observed in W0.8 round 2 output.

Codex review (inline): R1 P2 + R2 P1 + R3 clean + R4 P2 + R5+R6 (or R6+R7)
both clean. All findings were legitimate — Codex caught real bugs in the
v0.2.1 PR itself. ~233 tests pass, all hooks green.

Meta-finding for v0.2.2: max_review_rounds=3 +
required_clean_rounds_before_merge=2 (consecutive) is mathematically
unable to ship when rounds 1+2 both find issues. Need either default
max_rounds=4-5 OR explicit 'confirmation rounds after last fix' config.
Workaround this run: manual rounds outside orchestrator."

git branch -D chore/autopilot-v0.2.1-codex-parser-fix
git push origin main
```

If push rejected → HALT. Do NOT force-push.

## Step 7 — Pop stash + commit prep files

After squash + push to origin/main:

```bash
git stash list                          # confirm "v0.2.1-preflight-prep" exists
git stash pop stash@{0}                 # or by name; choose the prep stash

git status                              # inspect what came back
# Expected files (prior session description):
#   docs/implementation-tracker.md      ← may already match main, may have edits
#   docs/prompts/autopilot-v0.2.1-codex-parser-fix.md   ← this prompt's source

# For each file:
#   - If already on main (no diff) → drop the file (`git checkout -- <path>`).
#   - If has new content → add + commit.

git diff --stat                         # see exactly what differs
```

For each file with new content, commit individually:

```bash
# If docs/implementation-tracker.md has new content not yet on main:
git add docs/implementation-tracker.md
git commit -m "docs(tracker): <describe edit>"

# If the prompt file is uncommitted:
git add docs/prompts/autopilot-v0.2.1-codex-parser-fix.md
git commit -m "docs(prompts): autopilot v0.2.1 fix prompt (consumed in this run)"

# Also commit THIS continuation prompt for archival:
git add docs/prompts/autopilot-v0.2.1-finish-after-r4.md
git commit -m "docs(prompts): autopilot v0.2.1 finish-after-r4 continuation prompt"
```

(Adjust file list based on what's actually in the stash — `git diff
--stat` is authoritative.)

```bash
git push origin main
```

---

## Circuit breakers (HALT and write report)

PAUSE immediately and write
`.autopilot/state/v0.2.1-fix/halt-report.md` (overwrite prior halt-report)
if ANY trigger fires:

1. **Pre-flight regression** — branch state / commit count / stash / 232
   test count mismatch.
2. **Push rejected** (remote moved).
3. **VERIFY_REGRESSION** — local verify fails twice consecutively after
   fix attempts.
4. **RECURRING_FINDING** — R5+ surfaces a finding with same severity +
   summary as a prior round.
5. **ARCH_FINDING** — Codex flags `schema design`, `breaking change`,
   `architectural`.
6. **SECURITY_FINDING** — Codex flags auth/token/timing/secret/injection.
7. **TYPE_IGNORE_PROPOSED** — Codex or you reach for `# type: ignore`.
8. **MAX_EXTRA_ROUNDS** — R7 done without 2× consecutive clean.
9. **Tool error twice in a row** on `git` / `codex` / `pytest`.
10. **Context budget** — if context >70%, pause + report. Founder resumes
    in fresh session with branch state intact.

### Halt report template

```
HALT — Autopilot v0.2.1 continuation circuit broken.

Step:    <e.g. Step 5 R6>
Trigger: <one of 10 conditions>
Branch:  chore/autopilot-v0.2.1-codex-parser-fix
HEAD:    <SHA>

Detail:
<error output OR Codex finding excerpt OR rejected push reason>

Sequence summary:
- R1: <result>
- R2: <result>
- R3: <result>
- R4: <result>
- R5: <result>
- R6: <result if reached>
- R7: <result if reached>

Files changed since last halt:
<list>

Requesting founder input on:
<specific question>
```

---

## Final report (when Step 7 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.1 — Codex parser + halt forensics + resume-from-HALTED — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA> on main
Branch chore/autopilot-v0.2.1-codex-parser-fix: DELETED
Push origin/main: OK

Codex review sequence (across both sessions):
  R1: P2 — stale state snapshot                        → fixed
  R2: P1 — overly broad CLEAN_PHRASE                   → fixed
  R3: CLEAN
  R4: P2 — tracker not synced on resume-from-HALTED    → fixed (this session)
  R5: <CLEAN | finding>
  R6: <CLEAN | finding> ← 2× clean confirmed here OR rounds continue
  R7: <CLEAN | not run | finding>
  Final state: 2 consecutive clean rounds at R<N>+R<N+1>
  Artifacts: .autopilot/state/v0.2.1-fix/codex/round-{01..07}.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean
  lint-imports: clean
  pytest:       <count> passed (baseline 219 + 14 v0.2.1 = ~233)

Stash restored + prep files committed:
  - docs/prompts/autopilot-v0.2.1-codex-parser-fix.md
  - docs/prompts/autopilot-v0.2.1-finish-after-r4.md
  - <other files from stash if any>

═══════════════════════════════════════════════════════

Next steps (NOT in this prompt's scope — founder runs):

1. Resume F07 pilot with fixed parser + tracker sync:

   cat .autopilot/state/F07/state.json | python -m json.tool

   # state.last_active_phase is null (state predates v0.2.1).
   # Edit .autopilot/state/F07/state.json:
   #   "phase": "VERIFIED"
   #   "current_round": 0
   #   "consecutive_clean_rounds": 0
   #   "halt_reason": null
   #   "halt_artifact_path": null
   nano .autopilot/state/F07/state.json

   python -m tools.autopilot resume F07

   Expected: Phase C R1 finds the P2 emit_analytics issue (now extractable
   by fixed parser), Claude fix, R2 clean, R3 clean, READY. Read
   .autopilot/state/F07/ready-report.md then squash F07 manually.

2. Backlog v0.2.2 (meta-bug observed this run):
   max_review_rounds=3 + required_clean_rounds_before_merge=2 is
   mathematically unable to ship when R1+R2 both find issues. Default
   max_rounds should be 4-5 OR add explicit "post-fix confirmation
   rounds" config knob.

End of autopilot v0.2.1 continuation.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles F07 resume.

---

## Global rules

1. READ FIRST — round-04.txt before writing the fix.
2. Don't modify anything outside loop.py + test_autopilot_resume.py for
   the R4 fix.
3. NEVER force-push.
4. NEVER add `# type: ignore`.
5. NEVER pop the stash before squash.
6. Atomic commits — one per logical change.
7. Verify before claiming done — re-run pytest after "tests pass" message.
8. Tool error twice → circuit breaker, don't retry blindly.
9. Context budget — if >70% used, pause + halt. Branch state intact.
10. Auto-push on success. No further confirmation needed.

Begin with Pre-flight, then Step 1. Execute through Step 7 final report.
