# Task: Finish autopilot v0.2.2 — apply R6 P1 fix only (defer P2), run R7+R8 confirmation, ship

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT continuation — LAST extension of v0.2.2 budget.
Branch `chore/autopilot-v0.2.2` at HEAD `e9b65c1` (15 commits ahead of
main). Apply R6 P1 fix only (detached HEAD in `current_branch()` helper).
Defer R6 P2 (halt message diagnostic label) to v0.2.3 with explicit
backlog entry. Run R7+R8 as post-fix-confirm. If R8 surfaces ANY new
finding → ship-with-override + comprehensive v0.2.3 backlog doc. **No
more extensions after R8.**

**Context (NOT for execution, just background):**

v0.2.2 ran 6 codex rounds, each surfacing legitimate findings:

- R1 P1: post-fix-confirm gate persistence → fixed `1b516e3`
- R2 P1+P2: "rce" substring + MERGED sync skip → fixed `88c1f49`
- R3 P1: INIT sync skip → fixed `9a91c7c`
- R4 P1+P2: word-boundary regex + READY sync skip → fixed `661c5ba`
- R5 P2: Phase E merge gate alignment → fixed `e9b65c1`
- R6 P1: `current_branch()` returns "HEAD" on detached state (this prompt fixes)
- R6 P2: MAX_ROUNDS halt message references wrong gate label (deferred to v0.2.3)

Pattern (now confirmed across 6 rounds): each fix surfaces 1-2 adjacent
findings in the cumulative diff. v0.2.2 PR is structurally large enough
that strict 2× clean tail may never naturally occur. Founder decision
2026-05-13:
- Fix R6 P1 (critical — same class of wrong-diff bug as the very issue
  v0.2.2 fix #3 addresses).
- Defer R6 P2 (cosmetic — diagnostic message label).
- Run R7+R8 strict zero-tolerance.
- If R8 finds anything → ship-with-override; document all uncaught
  findings as v0.2.3 batch.
- This is the LAST budget extension.

**Concurrency reminder:** 3 incidents during v0.2.2 work. NO other Claude
Code session may run on this repo during this prompt's execution.

## Required reading (READ FIRST, in order)

1. `.autopilot/state/v0.2.2/halt-report.md` — full halt context from
   prior session including R6 finding text.
2. `.autopilot/state/v0.2.2/codex/round-06.txt` — R6 raw output.
3. `tools/autopilot/git_ops.py` — find `current_branch()` helper added
   by v0.2.2 Step 4 (Fix #3). Understand current implementation.
4. `tools/autopilot/loop.py` — find the `current_branch()` callsite
   in `run()` resume sync logic. Understand what behavior is expected
   when detached.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git branch --show-current               # MUST: chore/autopilot-v0.2.2
git log --oneline -1                    # MUST: e9b65c1 (R5 fix)
git log --oneline main..HEAD | wc -l    # MUST: 15

# Working tree MUST be clean — R5 fix already committed last session
git status                              # MUST: nothing to commit, working tree clean

# Verify codex round 1-6 artifacts exist
ls .autopilot/state/v0.2.2/codex/round-{01..06}.txt

# Concurrency check
ls .git/*.lock 2>/dev/null
# MUST be empty / not exist

source .venv/bin/activate
which claude codex

# Verify all tests pass at HEAD e9b65c1
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # MUST: 293 pass (per prior halt report)
```

If anything diverges → HALT and report.

## Anti-patterns

- Touch ANY file beyond `tools/autopilot/git_ops.py` (the fix),
  `tests/unit/test_autopilot_resume_branch_sync.py` or
  `tests/unit/test_autopilot_git_ops.py` (regression test), and
  CHANGELOG.md (v0.2.3 backlog entry for R6 P2).
- Fix R6 P2 (halt message label) — that's deferred to v0.2.3.
- Apply NEW fixes in R7/R8. ZERO tolerance per prompt scope.
- More than 8 codex rounds. R7+R8 is final budget.
- `git push --force`.
- `# type: ignore`.
- Run other Claude Code sessions on this repo.

---

## Step 1 — Verify R6 P1 finding scope

Read `.autopilot/state/v0.2.2/codex/round-06.txt`. Confirm the P1 finding
text matches the summary above (detached-HEAD in `current_branch()` returns
literal "HEAD" string, causing sync silent no-op on wrong tree).

If finding describes something else → HALT `R6_P1_INTERPRETATION_MISMATCH`.

Inspect current `current_branch()` implementation:

```bash
sed -n '50,75p' tools/autopilot/git_ops.py
```

Confirm it does `git rev-parse --abbrev-ref HEAD` (or equivalent) which
returns literal "HEAD" on detached state.

## Step 2 — Apply R6 P1 fix (bounded to git_ops.py)

**File:** `tools/autopilot/git_ops.py`

Modify `current_branch()` to detect detached-HEAD and signal explicitly:

```python
def current_branch(cfg: Config) -> str | None:
    """Return the currently checked-out branch name, or None if detached HEAD.

    `git rev-parse --abbrev-ref HEAD` returns the literal string "HEAD" when
    in detached-HEAD state (after `git checkout <sha>`, mid-reflog recovery,
    or during certain rebase steps). Returning that string would cause the
    resume-branch-sync logic in loop.py to silently no-op (it compares
    `current_branch()` against `feature_state.branch`; "HEAD" != "feat/F07"
    → trigger checkout; but if loop.py's check is `if current != feature.branch:
    checkout(...)`, "HEAD" string matches no branch and proceeds wrong).

    Codex v0.2.2 R6 P1 (2026-05-13). Return None on detached-HEAD so callers
    can handle explicitly (likely: HALT with helpful error pointing to
    manual git checkout).
    """
    out = _run(cfg, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    return None if out == "HEAD" else out
```

**File:** `tools/autopilot/loop.py`

Update the resume-branch-sync callsite (introduced by v0.2.2 Fix #3) to
handle None:

```python
current_branch = git_ops.current_branch(cfg)
if current_branch is None:
    return _halt(
        cfg, feature_state, "DETACHED_HEAD",
        "Repository is in detached-HEAD state; cannot safely sync to "
        f"feature_state.branch={feature_state.branch!r}. Run "
        f"`git checkout {feature_state.branch}` manually then re-resume.",
    )
if current_branch != feature_state.branch:
    if not git_ops.branch_exists(cfg, feature_state.branch):
        return _halt(...)  # existing BRANCH_MISSING handling
    print(
        f"Syncing branch checkout: {current_branch} → {feature_state.branch}"
    )
    git_ops.checkout(cfg, feature_state.branch)
```

## Step 3 — Add regression test

**File:** `tests/unit/test_autopilot_git_ops.py` (new or extend if exists).

Add:

```python
def test_current_branch_returns_none_on_detached_head(tmp_path) -> None:
    """Codex v0.2.2 R6 P1: current_branch() must return None on detached HEAD,
    not the literal string "HEAD".

    Without this, loop.py's resume sync silently no-ops (string "HEAD" matches
    no branch name) and Codex review runs on whatever tree happens to be at
    that SHA — same wrong-diff bug v0.2.2 Fix #3 was supposed to prevent.
    """
    # Setup tmp git repo:
    #   - init
    #   - commit a file
    #   - capture SHA, checkout SHA directly (detached state)
    # Call current_branch(cfg).
    # Assert returns None (not "HEAD").

def test_current_branch_returns_name_on_normal_checkout(tmp_path) -> None:
    """Sanity counter-test."""
    # Setup repo, on main.
    # Call current_branch(cfg).
    # Assert returns "main".
```

Adapt to repo's fixture conventions for tmp git setup. Look at existing
`tests/unit/test_autopilot_*.py` files for the pattern.

If a resume-branch-sync test already exists from v0.2.2 Fix #3, extend it
to assert DETACHED_HEAD halt path.

## Step 4 — Document R6 P2 as v0.2.3 backlog

**File:** `CHANGELOG.md`

Find the v0.2.2 `## [Unreleased]` section (added by Step 10 of v0.2.2
mega prompt). Add a "Known issues" subsection at the end of the v0.2.2
block:

```markdown
### Known issues — deferred to v0.2.3

- `loop.py:316-319` MAX_ROUNDS halt message always cites
  `confirmation_rounds_after_last_fix` even when the legacy
  `required_clean_rounds_before_merge` gate was active. Diagnostic-only;
  may mislead recovery decisions but no functional impact. Codex v0.2.2
  R6 P2.
- Budget semantics clarification: current logic conflates "max review
  rounds total" with "max fix rounds + post-fix-confirm rounds". Should
  be split into explicit knobs.
- Codex CLI stale-blob true fix (currently logs warning only).
- tracker sync command / sidecar (currently no-op on feature branches).
- File lock for concurrent-session safety (currently doc-only policy;
  3 incidents during v0.2.2 work confirmed hazard).
```

## Step 5 — Local verify

```bash
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
```

ALL must pass. Expected pytest: 293 + 2 (new git_ops tests) = 295.

If verify fails → up to 2 retries to fix root cause. After 2 retries
→ HALT `VERIFY_REGRESSION`.

## Step 6 — Atomic commits

```bash
git add tools/autopilot/git_ops.py tools/autopilot/loop.py
git commit -m "fix(autopilot): current_branch returns None on detached HEAD (codex v0.2.2 r6 P1)

current_branch() previously returned literal string 'HEAD' on detached-HEAD
state (after `git checkout <sha>`, reflog recovery, etc.). loop.py's
resume-branch-sync compared this string against feature_state.branch,
silently no-op'd, and let Codex review run on whatever tree was at the
detached SHA — same wrong-diff bug v0.2.2 Fix #3 was supposed to prevent.

Now returns None on detached state. Caller in loop.py treats None as
DETACHED_HEAD circuit breaker, halting with helpful 'git checkout' hint.

Caught by Codex round 6 of v0.2.2 inline review."

git add tests/unit/test_autopilot_git_ops.py
git commit -m "test(autopilot): current_branch detached-HEAD regression guard"

git add CHANGELOG.md
git commit -m "docs(autopilot): v0.2.3 known-issues backlog from v0.2.2 R6 P2 + cumulative findings"
```

## Step 7 — Codex round 7 (post-fix-confirm 1 of 2)

**Concurrency check first:**

```bash
ls .git/*.lock 2>/dev/null
# MUST empty
```

If lock present → HALT `CONCURRENT_AGENT_DETECTED`.

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.2/codex/round-07.txt
```

**Parse output:**

CLEAN — any of: `did not identify any`, `did not find any`, `no actionable`,
`appear internally consistent`, NO severity-bracket line.

FINDING — `- [P0|P1|P2|P3] <summary> — <file>:<lines>`.

### Circuit-breaker checks (zero tolerance):

| Check | Action |
|---|---|
| Severity P0 | HALT `P0_FOUND` |
| Same finding as R6 P1 just fixed | HALT `RECURRING_FINDING` (fix didn't take) |
| Same finding as R6 P2 (we deferred) | log "deferred", treat as CLEAN for gate purpose (it's known v0.2.3) |
| Any other new finding (P1/P2/P3) | HALT `NEW_FINDING_R7` — see Step 9 final-call logic |
| CLEAN | Proceed to Step 8 |

Special handling for "same as R6 P2" (deferred): if R7 surfaces the
same halt-message-label finding, treat as CLEAN since we've already
documented it as v0.2.3 backlog. Note in log.

## Step 8 — Codex round 8 (post-fix-confirm 2 of 2)

Only reachable if Step 7 CLEAN (or only-R6-P2-deferred).

```bash
ls .git/*.lock 2>/dev/null
# MUST empty

codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.2/codex/round-08.txt
```

Same parse + circuit-breaker rules as Step 7.

If CLEAN (or only-R6-P2-deferred) → 2× post-fix-confirm satisfied →
Step 10 ship.

If NEW FINDING → Step 9 final-call logic.

## Step 9 — Final-call ship-with-override logic

If R7 OR R8 surfaces a NEW finding (other than the deferred R6 P2):

This is THE last extension. No R9 in this prompt's scope. Two sub-options
the agent autonomously chooses based on finding severity:

**Sub-option A: NEW finding is P2/P3 (cosmetic/minor)**

- Document the new finding in CHANGELOG v0.2.3 known-issues subsection
  (add to the list).
- Proceed to Step 10 ship with override note in squash commit:
  > "Codex R7/R8 surfaced additional <P2|P3> findings (<brief list>);
  > documented as v0.2.3 known issues. v0.2.2 ships with documented
  > residual after 8-round inline review."

**Sub-option B: NEW finding is P0/P1 (real bug)**

HALT `R7_OR_R8_HIGH_SEVERITY_FINDING`. Founder decides:
- Apply fix manually + re-resume manually outside this prompt.
- OR override (rare — only if finding is genuinely cosmetic mis-classified
  as P1).

Do NOT auto-ship a P0/P1 in this branch.

## Step 10 — Squash + push (when 2× post-fix-confirm OR Sub-option A override)

```bash
# Final sanity
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main

# Dry-run merge
git merge --no-commit --no-ff chore/autopilot-v0.2.2
git merge --abort

# Real squash
git merge --squash chore/autopilot-v0.2.2
git commit -m "fix(autopilot): v0.2.2 — tooling hardening from F07 + v0.2.1 cumulative pilot signal

Resolves 7 code-level orchestrator issues + 1 diagnostic workaround + 1
policy doc surfaced across F07 (4 sessions) and v0.2.1 (3 sessions) pilots.

Core fixes:
1. max_review_rounds 3→5; new confirmation_rounds_after_last_fix=2 knob
   persisted via state. Cascading-adjacent micro-finding pattern made old
   math (max=3 + clean=2 consec) unable to ship.
2. SECURITY_FINDING keyword tiering: severe (auth bypass / injection /
   csrf / xss) always HALT; soft (token / secret / hmac) need P0/P1.
   Word-boundary regex matching (\\brce\\b not 'force' substring).
3. Resume syncs git checkout to feature_state.branch regardless of phase.
   current_branch() returns None on detached HEAD; caller halts with
   DETACHED_HEAD breaker instead of silent wrong-diff.
4. tracker.update_status no-op on feature branches + skip INIT/MERGED/READY
   phases.
5. state.load tolerates unknown fields with warning.
6. codex.save_review_artifact non-clobber via -resumeN suffix.
7. Phase E merge gate aligned with Phase C's confirmation_rounds_after_last_fix.

Plus:
- codex.run_review logs warning on stale-blob SHA mismatch.
- docs/autopilot/orchestrator-usage.md: concurrency policy (one Claude
  Code session per repo; git worktree for parallel work). Validated 3×
  during this PR's own run when parallel sessions trampled refs.

Codex review (inline, 8 rounds total = 5 fix + 1 R5 + 1 R6 P1 + 2 post-fix-confirm):
- R1: P1 → fixed 1b516e3
- R2: P1+P2 → fixed 88c1f49
- R3: P1 → fixed 9a91c7c
- R4: P1+P2 → fixed 661c5ba
- R5: P2 → fixed e9b65c1
- R6: P1 → fixed <SHA this session>; P2 deferred to v0.2.3
- R7: CLEAN (post-fix-confirm 1 of 2)
- R8: CLEAN (post-fix-confirm 2 of 2)

<final test count> tests pass.

v0.2.3 KNOWN-ISSUES BACKLOG (documented in CHANGELOG):
- MAX_ROUNDS halt message diagnostic label (R6 P2 deferred).
- Budget semantics clarification (split max_fix + post_fix knobs).
- Codex CLI stale-blob true fix.
- tracker sync command / sidecar.
- File lock for concurrent-session safety.

F07 resume unblocked NEXT SESSION: founder runs
\`python -m tools.autopilot resume F07\` with orchestrator v0.2.2 active."

git branch -D chore/autopilot-v0.2.2
git push origin main
```

If push rejected → HALT. NEVER force-push.

---

## Circuit breakers

PAUSE immediately and overwrite `.autopilot/state/v0.2.2/halt-report.md`
if ANY trigger fires:

1. Pre-flight regression.
2. R6_P1_INTERPRETATION_MISMATCH — R6 finding doesn't match expected.
3. VERIFY_REGRESSION (verify fails 2× consecutively).
4. Push rejected.
5. P0_FOUND — R7 or R8 surfaces P0.
6. RECURRING_FINDING — R7/R8 surfaces same R6 P1 (fix didn't take).
7. ARCH_FINDING / SECURITY_FINDING (real, not keyword false positive).
8. R7_OR_R8_HIGH_SEVERITY_FINDING — NEW P0/P1 (per Sub-option B Step 9).
9. CONCURRENT_AGENT_DETECTED — `.git/*.lock` present mid-flight.
10. DETACHED_HEAD halt during pre-flight if working tree is detached.
11. TYPE_IGNORE_PROPOSED.
12. SCOPE_CREEP — fix touches files beyond scope.
13. Tool error 2× in a row.
14. Context budget >70%.

### Halt report template

```
HALT — autopilot v0.2.2 finish-r6-p1 circuit broken.

Step:    <e.g. Step 7 R7>
Trigger: <one of 14>
Branch:  chore/autopilot-v0.2.2
HEAD:    <SHA>

Detail:
<error output OR finding excerpt>

Codex sequence (cumulative across 3 sessions):
  R1: P1 → fix 1b516e3
  R2: P1+P2 → fix 88c1f49
  R3: P1 → fix 9a91c7c
  R4: P1+P2 → fix 661c5ba
  R5: P2 → fix e9b65c1
  R6: P1 → fix <SHA>; P2 deferred
  R7: <result>
  R8: <result if reached>

Files modified this session: <list>

Requesting founder input on:
<specific question>
```

---

## Final report (when Step 10 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.2 — Tooling hardening — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA> on main
Branch chore/autopilot-v0.2.2: DELETED
Push origin/main: OK

Codex review sequence (8 rounds total, 6 fix + 2 confirm):
  R1: P1 → fix 1b516e3
  R2: P1+P2 → fix 88c1f49
  R3: P1 → fix 9a91c7c
  R4: P1+P2 → fix 661c5ba
  R5: P2 → fix e9b65c1
  R6: P1 → fix <SHA this session>; P2 deferred to v0.2.3 (documented)
  R7: <CLEAN | finding details if Sub-option A taken>
  R8: <CLEAN | finding details if Sub-option A taken>
  Final state: 2× post-fix-confirm clean (or 1× clean + 1× R6-P2-deferred-equivalent)
  Artifacts: .autopilot/state/v0.2.2/codex/round-{01..08}.txt

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

   python3 -c "import json; from pathlib import Path; p = Path('.autopilot/state/F07/state.json'); s = json.loads(p.read_text()); s.update({'phase': 'VERIFIED', 'current_round': 0, 'consecutive_clean_rounds': 0, 'halt_reason': None, 'halt_artifact_path': None, 'fixed_finding_hashes': []}); p.write_text(json.dumps(s, indent=4) + '\\n'); print('reset')"

   source .venv/bin/activate
   python -m tools.autopilot resume F07

   Expected: orchestrator runs codex with new max=5 + post-fix-confirm=2
   budget. Cascade pattern has 7-round headroom. SECURITY keyword tiering
   won't false-positive on Markdown bugs. Resume syncs branch correctly,
   halts with helpful error on detached HEAD. Should converge.

2. After F07 READY → manual squash F07 to main.

3. v0.2.3 backlog (per CHANGELOG known-issues):
   - MAX_ROUNDS halt message diagnostic label
   - Budget semantics clarification
   - Codex stale-blob true fix
   - tracker sync command
   - File lock for concurrency

End of autopilot v0.2.2.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles F07 resume.

---

## Global rules

1. READ FIRST. R6 finding + git_ops.current_branch implementation
   before fixing.
2. SCOPE STRICT: only `git_ops.py` + `loop.py` resume callsite + 1 test
   file + CHANGELOG. NO other files. NO new fixes in R7/R8.
3. R6 P2 (halt message label) STAYS DEFERRED. Do not fix.
4. NEVER force-push.
5. NEVER `# type: ignore`.
6. Atomic commits — fix in one, test in another, CHANGELOG in another.
7. Verify before claiming done.
8. Tool error 2× → circuit breaker.
9. Context budget >70% → pause + halt.
10. THIS IS THE LAST EXTENSION. After Step 8 (R8), ship or HALT.
    No further budget grants from this prompt.
11. Concurrency check before EACH Codex round — `ls .git/*.lock`.

Begin with Pre-flight, then Step 1. Execute through Step 10.
