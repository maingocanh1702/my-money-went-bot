# Task: Finish autopilot v0.2.2 — commit R5 fix + post-fix-confirm rounds R6+R7 + squash + push

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT continuation — branch `chore/autopilot-v0.2.2` already
exists with 12 commits (R1-R4 fixes applied). Uncommitted R5 fix in working
tree. **Reinterpret budget: total = max_fix_rounds (5 applied) +
confirmation_rounds_after_last_fix (2 needed) = 7 rounds.** Commit R5,
drive R6+R7 as confirmation. Squash + push to main.

**Context (NOT for execution, just background):**

v0.2.2 ("autopilot tooling hardening") hit MAX_ROUNDS at R5 because the
prompt's Step 12 budget was hard-capped at 5 rounds total, conflating
fix rounds with confirmation rounds. Each of R1-R5 surfaced legitimate
findings:

- R1 P1: `confirmation_rounds_after_last_fix` gate not persisted via
  state field → fixed `1b516e3`.
- R2 P1+P2: `"rce"` substring matches benign `"force"`; tracker.update_status
  on MERGED phase shouldn't fire → fixed `88c1f49`.
- R3 P1: tracker.update_status on INIT phase shouldn't fire → fixed `9a91c7c`.
- R4 P1+P2: SECURITY keyword matcher needs word-boundary regex; READY
  sync skip → fixed `661c5ba`.
- R5 P2: Phase E merge gate uses old `required_clean_rounds_before_merge`,
  should align with `confirmation_rounds_after_last_fix` → fix PREPARED
  in working tree (uncommitted: `tools/autopilot/merge.py` +
  `tests/unit/test_autopilot_max_rounds.py`).

Decision (founder, 2026-05-13): **Reinterpret budget semantics.** "Budget"
= 5 fix rounds + 2 post-fix-confirm rounds = 7 total. Commit R5, run R6+R7
as confirmation. If R6 surfaces NEW finding → halt + founder decides (do
NOT fix in this prompt — discipline boundary).

**Also:** 2 concurrency events occurred during the v0.2.2 run:
- A parallel session caused an early commit to land on main, recovered via
  `git update-ref` (no force-push, main reset to origin/main).
- R5 codex review was interrupted by a parallel session running
  `git stash + checkout main + pull` mid-flight; recovered via checkout.

Both confirm the concurrency policy v0.2.2 documented. **No other Claude
Code session may run on this repo during this prompt's execution.**

## Required reading (READ FIRST, in order)

1. `.autopilot/state/v0.2.2/halt-report.md` — full halt context from the
   prior v0.2.2 run.
2. `.autopilot/state/v0.2.2/codex/round-{01..05}.txt` — Codex R1-R5
   verdicts. Skim R5 specifically to confirm the uncommitted fix
   addresses the finding correctly.
3. Working tree uncommitted changes:

   ```bash
   git diff
   ```

   Should show changes in `tools/autopilot/merge.py` +
   `tests/unit/test_autopilot_max_rounds.py` only. If anything else
   modified → HALT and report.

4. `tools/autopilot/loop.py` — read the Phase C while-loop + new
   `confirmation_rounds_after_last_fix` logic (added by R1 fix). Verify
   merge.py's Phase E gate aligns.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git branch --show-current               # MUST: chore/autopilot-v0.2.2
git log --oneline -1                    # MUST: 661c5ba (R4 fix)
git log --oneline main..HEAD | wc -l    # MUST: 12

# Verify uncommitted R5 fix is in working tree
git diff --name-only
# MUST show ONLY:
#   tools/autopilot/merge.py
#   tests/unit/test_autopilot_max_rounds.py
# (May also show CHANGELOG.md if R5 fix touched it; that's OK.)

# Verify codex round 1-5 artifacts exist
ls .autopilot/state/v0.2.2/codex/round-{01..05}.txt

# Confirm no other lock files
ls .git/*.lock 2>/dev/null
# MUST be empty / not exist

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Verify all tests pass at current state (BEFORE committing R5)
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
# Expected: 293 pass (per halt report) at HEAD 661c5ba; the uncommitted
# R5 fix may add 1 more test → 294 pass.
```

If anything diverges → HALT and report. Do not proceed.

## Anti-patterns

- Modify ANYTHING outside `merge.py` + the R5 test file. R5 fix must stay
  bounded — no scope creep.
- Apply NEW fixes in R6/R7 if Codex finds something. DISCIPLINE: this
  prompt is confirmation only. R6/R7 finding → HALT, founder decides.
- `git push --force`.
- `# type: ignore`.
- Run other Claude Code sessions on this repo.
- Skip the R5 commit message rationale referencing R5 codex finding text.

---

## Step 1 — Verify R5 fix correctness

```bash
git diff tools/autopilot/merge.py
git diff tests/unit/test_autopilot_max_rounds.py
```

The diff should:
1. Update `merge.attempt_merge` (or the pre-merge gate logic) to use
   `cfg.confirmation_rounds_after_last_fix` instead of
   `cfg.required_clean_rounds_before_merge` for the consecutive-clean
   threshold check (OR both as fallback for backward compat).
2. Add a unit test asserting Phase E gate uses the new knob.

Read R5 codex output (`.autopilot/state/v0.2.2/codex/round-05.txt`) and
confirm the diff addresses the finding's described concern. If the
diff seems unrelated to the R5 finding → HALT `R5_FIX_MISMATCH`.

## Step 2 — Run R5 fix verify locally

```bash
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
```

ALL must pass. If new test in `test_autopilot_max_rounds.py` is included,
pytest count = 294. If verify fails → up to 2 retries to fix root cause
of the R5 fix (e.g., test assertion off, missing import). After 2 retries
→ HALT `VERIFY_REGRESSION`.

## Step 3 — Commit R5 fix

```bash
git add tools/autopilot/merge.py tests/unit/test_autopilot_max_rounds.py
git commit -m "fix(autopilot): Phase E merge gate uses confirmation_rounds_after_last_fix (codex r5 P2)

Phase E pre-merge gate previously checked required_clean_rounds_before_merge
for the consecutive-clean threshold. After v0.2.2 introduces
confirmation_rounds_after_last_fix as the canonical knob, Phase E was the
last untouched call-site — left it inconsistent with Phase C's READY
transition.

Aligns merge.attempt_merge to read confirmation_rounds_after_last_fix
(falling back to required_clean_rounds_before_merge if not set, for
backward compat with older state files / configs).

Caught by Codex round 5 of v0.2.2 inline review. Last fix in this PR;
remainder of budget (rounds 6 + 7) are post-fix-confirm rounds only —
this commit completes the v0.2.2 fix set."
```

## Step 4 — Codex round 6 (post-fix-confirm 1 of 2)

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.2/codex/round-06.txt
```

**Parse output:**

CLEAN — any of: `did not identify any`, `did not find any`, `no actionable`,
`appear internally consistent`, NO severity-bracket line.

FINDING — `- [P0|P1|P2|P3] <summary> — <file>:<lines>`.

### Circuit-breaker checks (strict — no fix-loop in this prompt):

| Check | Action |
|---|---|
| Severity P0 | HALT `P0_FOUND` |
| Same finding as R1-R5 | HALT `RECURRING_FINDING` (fix didn't take) |
| Keywords schema/breaking-change | HALT `ARCH_FINDING` |
| Severe security keyword (auth bypass, injection, csrf, real not "rce"-in-"force") | HALT `SECURITY_FINDING` |
| ANY new P1/P2/P3 finding | HALT `NEW_FINDING_OUT_OF_SCOPE` — founder decides v0.2.3 deferral |
| CLEAN | Proceed to Step 5 |

This prompt's scope = post-fix-confirm only. NO fixes applied here.
Single-finding tolerance is zero.

## Step 5 — Codex round 7 (post-fix-confirm 2 of 2)

Only reachable if Step 4 CLEAN.

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.2/codex/round-07.txt
```

Same parse + circuit-breaker rules as Step 4.

If CLEAN → 2× post-fix-confirm achieved → Step 6 squash.
If FINDING → HALT (any severity).

## Step 6 — Squash + push (ONLY when R6 + R7 both CLEAN)

```bash
# Final sanity verify
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main

# Dry-run merge — confirm no conflicts
git merge --no-commit --no-ff chore/autopilot-v0.2.2
git merge --abort

# Real squash
git merge --squash chore/autopilot-v0.2.2
git commit -m "fix(autopilot): v0.2.2 — tooling hardening from F07 + v0.2.1 cumulative pilot signal

Resolves 6 code-level orchestrator issues + 1 diagnostic workaround + 1
policy doc surfaced across F07 (4 sessions) and v0.2.1 (3 sessions) pilots:

1. max_review_rounds 3→5; new confirmation_rounds_after_last_fix=2 knob,
   persisted via state to support resume. Empirical pattern: adjacent
   micro-findings cascade per fix commit; old math (max=3 + clean=2 consec)
   couldn't ship. New decouples post-fix confirmation from total budget.
2. SECURITY_FINDING keyword tiering (codex r2+r4 refined): severe (auth
   bypass / injection / csrf / xss) always HALT; soft (token / secret /
   hmac) need P0/P1. Word-boundary regex matching (\\brce\\b not 'force'
   substring). Stops false-positive halts on benign Markdown rendering.
3. Resume syncs git checkout to feature_state.branch regardless of phase.
4. tracker.update_status no-op on feature branches + skip on INIT/MERGED/
   READY phases (codex r2/r3/r4 refinements).
5. state.load tolerates unknown fields with warning.
6. codex.save_review_artifact non-clobber via -resumeN suffix.
7. Phase E merge gate aligned with Phase C's confirmation_rounds_after_last_fix
   (codex r5).

Plus:
- codex.run_review logs warning when output references SHA != HEAD
  (stale-blob detection — true fix v0.2.3 backlog).
- docs/autopilot/orchestrator-usage.md: concurrency policy (one Claude
  Code session per repo; git worktree for parallel work). Validated 2×
  during this PR's own run when parallel sessions trampled refs.

Codex review (inline, EXTENDED budget: 5 fix rounds + 2 post-fix-confirm):
- R1: P1 → fixed 1b516e3
- R2: P1+P2 → fixed 88c1f49
- R3: P1 → fixed 9a91c7c
- R4: P1+P2 → fixed 661c5ba
- R5: P2 → fixed <R5 SHA>
- R6: CLEAN (post-fix-confirm 1 of 2)
- R7: CLEAN (post-fix-confirm 2 of 2)

<final test count> tests pass.

v0.2.3 BACKLOG (from this PR's own run):
- Budget semantics clarification: 'max_fix_rounds + confirmation_rounds'
  not 'max_review_rounds total'. Current code conflates; needs split.
- Codex CLI stale-blob true fix (pin explicit SHA pair).
- tracker sync command / sidecar (replace no-op-on-feature-branch with
  explicit founder workflow).
- File lock for concurrent-session safety (was 2× hazard during this run).

F07 resume unblocked NEXT SESSION: founder runs
\`python -m tools.autopilot resume F07\` with orchestrator v0.2.2 active."

git branch -D chore/autopilot-v0.2.2
git push origin main
```

If push rejected → HALT. Do NOT force-push.

---

## Circuit breakers (HALT and overwrite halt-report)

PAUSE immediately and write `.autopilot/state/v0.2.2/halt-report.md`
(overwriting prior) if ANY trigger fires:

1. Pre-flight regression (branch/HEAD/commit count/file diff mismatch).
2. R5_FIX_MISMATCH — diff doesn't address R5 finding.
3. VERIFY_REGRESSION — verify fails 2× after fix attempt.
4. Push rejected.
5. P0_FOUND — R6/R7 surfaces P0.
6. RECURRING_FINDING — R6/R7 surfaces same R1-R5 issue.
7. ARCH_FINDING / SECURITY_FINDING — real (not keyword false positive).
8. NEW_FINDING_OUT_OF_SCOPE — R6/R7 surfaces any new P1/P2/P3.
9. TYPE_IGNORE_PROPOSED.
10. Tool error 2× in a row.
11. Context budget >70%.
12. Lock file detected mid-flight (`ls .git/*.lock` non-empty) — concurrent
    agent intrusion → HALT immediately, report, founder cleans up.

### Halt report template

```
HALT — autopilot v0.2.2 finish-r5-r6-r7 circuit broken.

Step:    <e.g. Step 4 R6>
Trigger: <one of 12>
Branch:  chore/autopilot-v0.2.2
HEAD:    <SHA>

Detail:
<error output OR finding excerpt>

Codex sequence (cumulative):
  R1: P1 → fix 1b516e3
  R2: P1+P2 → fix 88c1f49
  R3: P1 → fix 9a91c7c
  R4: P1+P2 → fix 661c5ba
  R5: P2 → fix <committed/skipped this session>
  R6: <result>
  R7: <result if reached>

Files modified this session: <list>

Requesting founder input on:
<specific question>
```

---

## Final report (when Step 6 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.2 — Tooling hardening — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA> on main
Branch chore/autopilot-v0.2.2: DELETED
Push origin/main: OK

Codex review sequence (7 rounds total, 5 fix + 2 confirm):
  R1: P1 — confirmation_rounds_after_last_fix persistence → fixed 1b516e3
  R2: P1+P2 — "rce" substring + MERGED sync skip → fixed 88c1f49
  R3: P1 — INIT sync skip → fixed 9a91c7c
  R4: P1+P2 — word-boundary + READY sync skip → fixed 661c5ba
  R5: P2 — Phase E merge gate alignment → fixed <SHA>
  R6: CLEAN (post-fix-confirm 1 of 2)
  R7: CLEAN (post-fix-confirm 2 of 2)
  Final state: 2× post-fix-confirm clean confirmed
  Artifacts: .autopilot/state/v0.2.2/codex/round-{01..07}.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean (no new errors in v0.2.2 scope)
  lint-imports: clean
  pytest:       <count> passed

═══════════════════════════════════════════════════════

Next steps (NOT in this prompt's scope — founder runs):

1. Resume F07 pilot with v0.2.2 orchestrator:

   cd /Users/maingocanh/Projects/MyMoneyWent
   git checkout feat/F07-settings
   git merge main -m "merge: v0.2.2 into feat/F07-settings"
   # Resolve conflicts if any (likely CHANGELOG)

   # Reset F07 state
   python3 -c "import json; from pathlib import Path; p = Path('.autopilot/state/F07/state.json'); s = json.loads(p.read_text()); s.update({'phase': 'VERIFIED', 'current_round': 0, 'consecutive_clean_rounds': 0, 'halt_reason': None, 'halt_artifact_path': None, 'fixed_finding_hashes': []}); p.write_text(json.dumps(s, indent=4) + '\\n'); print('reset')"

   source .venv/bin/activate
   python -m tools.autopilot resume F07

   Expected: orchestrator runs codex with new max=5 + post-fix-confirm=2
   budget. Cascade pattern (if still present) has 7-round headroom (5
   fix + 2 confirm). SECURITY keyword tiering won't false-positive on
   Markdown bugs. Resume syncs branch correctly. Should converge.

2. After F07 READY → manual squash F07 to main per ready-report.md.

3. v0.2.3 backlog:
   - Budget semantics clarification (max_fix_rounds + confirmation_rounds).
   - Codex CLI stale-blob true fix (pin explicit SHA pair).
   - tracker sync command / sidecar.
   - File lock for concurrent-session safety.

End of autopilot v0.2.2.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles F07 resume.

---

## Global rules

1. READ FIRST. R5 codex finding + uncommitted diff before committing.
2. SCOPE: commit R5 fix only. Then post-fix-confirm rounds. NO new fixes
   in this prompt — discipline.
3. NEVER force-push.
4. NEVER `# type: ignore`.
5. Atomic commits — R5 fix in one. Squash at end.
6. Verify before claiming done.
7. Tool error 2× → circuit breaker.
8. Context budget >70% → pause + halt.
9. ZERO tolerance for new findings in R6/R7. Single P1/P2/P3 → halt,
   founder decides v0.2.3 deferral.
10. Concurrency check before EACH Codex round: `ls .git/*.lock` → if
    non-empty, halt with `CONCURRENT_AGENT_DETECTED`. Eat-own-dogfood
    on the concurrency policy this PR is documenting.

Begin with Pre-flight, then Step 1. Execute through Step 6.
