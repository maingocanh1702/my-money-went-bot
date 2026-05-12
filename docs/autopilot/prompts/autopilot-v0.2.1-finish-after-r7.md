# Task: Finish autopilot v0.2.1 — drive Codex rounds R8+ to 2× consecutive clean → squash + push

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT continuation — branch
`chore/autopilot-v0.2.1-codex-parser-fix` already exists with 11 commits;
Codex rounds 1-7 already run. R7 was clean against final diff but only 1
consecutive (R6 P2 found + fixed in 94775db, R7 clean). Drive R8+ to
2× consecutive clean per protocol, then squash + push + restore stashed
prep files. Pause ONLY on circuit-breaker conditions.

**Why this prompt exists:** Prior session HALTED at MAX_EXTRA_ROUNDS after
R5+R6+R7 budget exhausted. Founder analysis (this session): pattern of
"R_n clean → R_n+1 finds bug against same diff" (R3→R4, R5→R6) is
Codex stochasticity — exactly what the 2× consecutive clean rule was
designed to catch. R7 clean alone is insufficient evidence. Override
would set bad precedent. Strict protocol path: continue past prior
MAX_EXTRA_ROUNDS cap with new bound R8-R10 (3 more), HALT for founder
decision if not 2× clean by R10.

**Critical context:**
- HEAD = `94775db` (R6 fix). No commits should land between R7 and R8 —
  R8 reviews the **same diff** as R7. If R7+R8 both clean = 2× consec.
- R8 has empirical ~50% chance of finding something new (4 of 7 prior
  rounds found a real bug). Plan for either branch.
- If R8 finds → apply minimum-viable fix → R9 → R10. Up to total budget
  R8-R10 in this session. Beyond → HALT with meta-finding.

## Required reading (READ FIRST, in order)

1. `.autopilot/state/v0.2.1-fix/halt-report.md` — prior session final
   halt forensics, gives full R1-R7 sequence with finding descriptions.
2. `.autopilot/state/v0.2.1-fix/codex/round-07.txt` — R7 clean verdict
   (the "1 consecutive" anchor we need to extend).
3. `tools/autopilot/loop.py` + `tools/autopilot/codex.py` —
   confirm current state matches what halt-report says.
4. `tools/autopilot/tracker.py` — `update_status` signature (in case R8+
   findings touch loop.py near the resume block).

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean (stash holds prep)
git branch --show-current               # MUST: chore/autopilot-v0.2.1-codex-parser-fix
git log --oneline main..HEAD | wc -l    # MUST be 11
git log --oneline -1                    # MUST start with 94775db

git stash list | grep "v0.2.1-preflight-prep"  # MUST exist (untouched by prior session)

ls .autopilot/state/v0.2.1-fix/codex/round-0{1,2,3,4,5,6,7}.txt
# All 7 files MUST exist. No round-08.txt yet.

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling baseline green
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v                        # MUST be 233 pass
```

If branch/HEAD/stash/round-count/pytest count diverges → HALT and report.
Do not proceed.

## Anti-patterns (NEVER do)

- Add new orthogonal scope. Only fix what Codex flags directly. NO
  refactoring, NO opportunistic cleanup, NO doc improvements beyond
  what a finding requests.
- Force-push.
- Add `# type: ignore` (circuit breaker).
- Pop the stash before squash.
- Continue past R10. Hard cap this session.
- Auto-squash without 2× consecutive clean confirmation.
- Run codex with extra prompt args beyond `--base main` (we want same
  invocation as prior rounds for comparability).

---

## Step 1 — Codex round 8

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-08.txt
```

**Parse R8 output:**

CLEAN signal — output contains any of:
- `did not identify any`
- `did not find any`
- `no actionable regressions`
- `no actionable defects`
- `did not identify any introduced defects`
- `appear internally consistent`
- No severity-bracket line (`[P0]`, `[P1]`, `[P2]`, `[P3]`) anywhere

FINDING signal — output contains line matching pattern:
```
- [P0|P1|P2|P3] <summary> — <path>:<line-range>
```

**Critical extraction for R8 findings (used in checks below):**
- Severity (P0/P1/P2/P3)
- File path
- Summary text (first 80 chars for hash comparison)
- Same-finding-as-prior-round check: compare against R1, R2, R4, R6
  finding summaries in halt-report. If summary matches → `RECURRING_FINDING`.

### Branch A — R8 CLEAN

2× consecutive clean confirmed (R7 + R8). Proceed directly to Step 4
(squash + push). Do NOT run R9.

### Branch B — R8 FINDING

Apply circuit-breaker checks BEFORE attempting fix:

| Check | Action |
|---|---|
| Severity P0 | HALT `P0_FOUND` — founder review mandatory |
| Keywords `schema design`, `breaking change`, `architectural`, `re-think`, `migration cannot be reversed` | HALT `ARCH_FINDING` |
| Keywords `auth`, `token leak`, `timing`, `secret`, `injection`, `csrf`, `xss` | HALT `SECURITY_FINDING` |
| Same finding summary[:80] as R1/R2/R4/R6 (case-insensitive) | HALT `RECURRING_FINDING` |
| Fix requires `# type: ignore` or scope expansion to >2 files | HALT `SCOPE_CREEP` |
| Otherwise | Proceed to Step 2 |

## Step 2 — Apply R8 fix (only if Branch B passed circuit-breaker checks)

**Constraint:** minimum-viable fix. ≤2 files modified. No new dependencies.
No new public API surface. The fix MUST be confined to addressing the
specific finding text.

Implement, then local verify:

```bash
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v                        # MUST be ≥233 pass
```

If verify fails → up to 2 retries to fix root cause. After 2 retries →
HALT `VERIFY_REGRESSION`.

If a regression test for the fix is appropriate, add it to the same
test module the v0.2.1 work already extended (e.g.
`tests/unit/test_autopilot_resume.py` for loop.py changes,
`tests/unit/test_autopilot_codex_parser.py` for codex.py changes). Use
existing fixture style.

**Atomic commit:**

```bash
git add <files>
git commit -m "fix(autopilot): address codex round 08 — <one-line summary>"
```

## Step 3 — Codex round 9 (and possibly round 10)

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-09.txt
```

Parse with same rules as R8.

### R9 CLEAN

R8 had a finding (we fixed it), R9 reviewed post-fix state and is clean.
This is **1 consecutive clean** (R9 alone — R8 is not counted because it
had a finding). Need 1 more to hit 2× consecutive.

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-10.txt
```

- **R10 CLEAN** → 2× consecutive (R9+R10) → proceed to Step 4 squash.
- **R10 FINDING** → run circuit-breaker checks. If pass: apply
  minimum-viable fix. HALT `MAX_EXTRA_ROUNDS_SESSION_2` after R10 fix
  attempt — we hit session budget, founder decides whether to continue
  in another session or escalate to override.

### R9 FINDING

R8 had a finding, R9 also has a finding (against post-R8-fix state) —
fix cycle continuing. Run circuit-breaker checks on R9 finding. If pass:
apply minimum-viable fix.

Then R10:

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.1-fix/codex/round-10.txt
```

- **R10 CLEAN** → only 1 consecutive (R10 alone). HALT
  `MAX_EXTRA_ROUNDS_SESSION_2` — need 1 more clean but session budget
  exhausted.
- **R10 FINDING** → HALT `MAX_EXTRA_ROUNDS_SESSION_2`. Founder reviews
  pattern.

## Step 4 — Squash + push (ONLY when 2× consecutive clean confirmed)

```bash
# Final local sanity
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main

# Dry-run merge — confirm no conflicts
git merge --no-commit --no-ff chore/autopilot-v0.2.1-codex-parser-fix
git merge --abort                       # discard dry-run

# Real squash
git merge --squash chore/autopilot-v0.2.1-codex-parser-fix
```

Compose squash commit message. Use the template below; fill in
`<R_FINAL_CLEAN_PAIR>` based on which rounds produced 2× consec.

```
fix(autopilot): v0.2.1 — Codex parser + halt forensics + resume-from-HALTED

Resolves 3 bugs surfaced by F07 pilot 2026-05-12:

1. parse_findings early-returned ([], False) when Codex CLI output lacked
   a 'codex' marker line. Parser now falls back to whole-output parsing.
2. _halt helper writes halt-report.md unconditionally.
3. state.transition to HALTED records last_active_phase; loop.run on
   resume re-enters at that phase with Phase-C round counters reset and
   tracker propagated.

Plus: 4 real Codex outputs as tracked fixtures, PARSER_UNCERTAIN
defensive breaker, expanded CLEAN_PHRASES, halt-report git ctx
base_branch fix (Codex r6 P2), plus any R8-R10 findings addressed.

Codex review (inline, <N> rounds across 3 sessions): R1 P2 + R2 P1 + R3
clean + R4 P2 + R5 clean + R6 P2 + R7 clean + R8 <...> + R9 <...> + R10
<... if reached>. Final 2× consecutive clean at <R_FINAL_CLEAN_PAIR>.
All findings legitimate Codex catches in this PR itself. <count> tests
pass.

Meta-bug for v0.2.2 backlog: max_review_rounds=3 +
required_clean_rounds_before_merge=2 (consecutive) is mathematically
unable to ship when fix commits introduce adjacent micro-findings. This
PR drove rounds outside orchestrator manual-mode. v0.2.2 should raise
default max_rounds to 5 OR add explicit 'confirmation_rounds_after_last_fix'
config knob. Logged in CHANGELOG.md notes section.
```

(If you produced an R8 fix, mention it. If no R8 fix happened — Branch A
above — mention "R8 clean = 2× consec with R7" and skip mentions of
R9/R10.)

```bash
git commit -m "$(cat <<EOF
<message above with placeholders filled>
EOF
)"

git branch -D chore/autopilot-v0.2.1-codex-parser-fix
git push origin main
```

If push rejected → HALT. Do NOT force-push.

## Step 5 — Pop stash + commit prep files

```bash
git stash list                          # confirm v0.2.1-preflight-prep exists
git stash pop stash@{0}                 # restore prep files

git status                              # inspect what came back
git diff --stat                         # see exactly what differs vs main
```

For each file in the popped stash, decide:

- File matches main (no diff) → `git checkout -- <path>` to discard.
- File has new content → `git add` + commit atomically.

Likely files (verify with `git diff --stat`):

```bash
# Both prompt files used in v0.2.1 fix
git add docs/prompts/autopilot-v0.2.1-codex-parser-fix.md \
        docs/prompts/autopilot-v0.2.1-finish-after-r4.md \
        docs/prompts/autopilot-v0.2.1-finish-after-r7.md
git commit -m "docs(prompts): autopilot v0.2.1 fix prompts (initial + 2 continuations)"

# If implementation-tracker.md has new content vs main:
# git add docs/implementation-tracker.md
# git commit -m "docs(tracker): <whatever the diff shows>"

git push origin main
```

---

## Circuit breakers (HALT and overwrite halt-report)

PAUSE immediately and write
`.autopilot/state/v0.2.1-fix/halt-report.md` (overwriting prior) if ANY
trigger fires:

1. **Pre-flight regression** — branch/HEAD/stash/round count mismatch.
2. **Push rejected** (remote moved).
3. **VERIFY_REGRESSION** — local verify fails twice after fix attempt.
4. **P0_FOUND** — R8+ surfaces a P0 finding.
5. **ARCH_FINDING** — schema/architecture/breaking-change keywords.
6. **SECURITY_FINDING** — auth/token/timing/secret/injection keywords.
7. **RECURRING_FINDING** — R8+ finding matches R1/R2/R4/R6 by
   summary[:80] (case-insensitive).
8. **SCOPE_CREEP** — fix would need `# type: ignore` or >2 file edits.
9. **MAX_EXTRA_ROUNDS_SESSION_2** — R10 done without 2× consec clean.
10. **Tool error twice in a row** on `git`/`codex`/`pytest`.
11. **Context budget** — context >70% used.

### Halt report template

```
HALT — Autopilot v0.2.1 session 2 continuation circuit broken.

Step:    <e.g. Step 3 R10>
Trigger: <one of 11 conditions>
Branch:  chore/autopilot-v0.2.1-codex-parser-fix
HEAD:    <SHA>

Codex sequence (cumulative across 3 sessions):
  R1: P2 — stale state snapshot          → fixed f667ad4
  R2: P1 — overly broad CLEAN_PHRASE     → fixed 0ffacab
  R3: CLEAN
  R4: P2 — tracker not synced on resume  → fixed cf58b7a
  R5: CLEAN
  R6: P2 — halt report git ctx           → fixed 94775db
  R7: CLEAN
  R8: <result>
  R9: <result if reached>
  R10: <result if reached>

Detail:
<error output OR finding excerpt OR rejected push reason>

Files changed since branch start (full cumulative diff):
<list>

Requesting founder input on:
<specific question>
```

---

## Final report (when Step 5 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.1 — Codex parser + halt forensics + resume-from-HALTED — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA> on main
Branch chore/autopilot-v0.2.1-codex-parser-fix: DELETED
Push origin/main: OK
Stash v0.2.1-preflight-prep: restored + prep files committed

Codex review sequence (3 sessions, R1-R<N>):
  R1: P2 — stale state snapshot                              → fixed f667ad4
  R2: P1 — overly broad CLEAN_PHRASE                         → fixed 0ffacab
  R3: CLEAN
  R4: P2 — tracker not synced on resume-from-HALTED at READY → fixed cf58b7a
  R5: CLEAN
  R6: P2 — halt report git ctx wrong base_branch             → fixed 94775db
  R7: CLEAN
  R8: <CLEAN | P_ — <one-line> → fixed <SHA>>
  R9: <CLEAN | P_ — <one-line> → fixed <SHA> | not run>
  R10: <CLEAN | P_ — <one-line> → fixed <SHA> | not run>
  Final state: 2× consecutive clean at R<X>+R<X+1>
  Artifacts: .autopilot/state/v0.2.1-fix/codex/round-{01..10}.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean
  lint-imports: clean
  pytest:       <count> passed (baseline 219 + <delta> v0.2.1 = <total>)

Prep files committed to main:
  - docs/prompts/autopilot-v0.2.1-codex-parser-fix.md
  - docs/prompts/autopilot-v0.2.1-finish-after-r4.md
  - docs/prompts/autopilot-v0.2.1-finish-after-r7.md
  - <other files if any from stash diff>

═══════════════════════════════════════════════════════

Next steps (NOT in this prompt's scope — founder runs):

1. Resume F07 pilot with fully-fixed orchestrator:

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

   Expected: Phase C R1 finds the P2 emit_analytics issue (parser now
   extracts it). Claude fix. R2 clean. R3 clean → READY. Read
   .autopilot/state/F07/ready-report.md then squash F07 manually.

2. Backlog v0.2.2 (meta-bug observed across 10 rounds of v0.2.1 review):
   max_review_rounds=3 + required_clean_rounds_before_merge=2 cannot
   ship a PR when adjacent micro-findings keep surfacing. Default
   max_rounds should be 5 OR add 'confirmation_rounds_after_last_fix=2'
   knob. v0.2.1 ran 10 rounds outside orchestrator to land — this is
   not sustainable for F02-F08 pilots.

End of autopilot v0.2.1.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles F07 resume.

---

## Global rules

1. READ FIRST — round-07.txt and halt-report.md before R8.
2. NEVER orthogonal scope. Only fix what Codex flags. No "while we're at
   it" improvements.
3. NEVER force-push.
4. NEVER add `# type: ignore`.
5. NEVER pop stash before squash.
6. Atomic commits — one per fix round.
7. Verify before claiming done.
8. Tool error twice → circuit breaker.
9. Context budget — if >70% used, pause + halt. Branch state intact.
10. Auto-push on success.

Begin with Pre-flight, then Step 1. Execute through Step 5 final report.
