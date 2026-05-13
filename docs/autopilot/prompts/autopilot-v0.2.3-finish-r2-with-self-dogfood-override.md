# Task: Finish v0.2.3 — apply R2 plural fix + R3+R4 confirm with self-dogfood override

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT continuation — branch `chore/autopilot-v0.2.3` exists
with 4 commits at HEAD `097a3f6`. Apply R2 plural inflection fix
(SOFT + ARCH categories per halt report). Run R3 + R4 codex review with
**ONE-TIME founder-authorized self-dogfood override**: breaker triggers
on findings INSIDE `tools/autopilot/codex.py` keyword sections are
treated as advisory (log + continue + apply fix), NOT halt. Outside
keyword sections: normal strict breaker rules apply. Squash to main
LOCAL ONLY — founder pushes manually per Q3 policy.

**Why one-time override:** v0.2.3 PR's purpose IS keyword routing
refinement. Codex findings explain keyword routing → text naturally
contains keyword-trigger words → breakers self-trip. This is a
recursive paradox specific to keyword-work PRs. Founder authorizes
override FOR THIS PR ONLY. v0.2.4 backlog records the paradox; if
pattern recurs 3+ times, code-level relaxation rule revisited.

## Required reading (READ FIRST, in order)

1. `.autopilot/state/v0.2.3/halt-report.md` — full R2 halt context +
   recommended fix patches.
2. `.autopilot/state/v0.2.3/codex/round-02.txt` — R2 raw output (both
   findings).
3. `tools/autopilot/codex.py` — current keyword regex implementation
   (R1 fix applied, R2 fix needed).
4. `tests/unit/test_autopilot_keyword_matching.py` — 23 existing fixtures.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST clean
git branch --show-current               # MUST: chore/autopilot-v0.2.3
git log --oneline -1                    # MUST: 097a3f6 (R1 fix)
git log --oneline main..HEAD | wc -l    # MUST: 4

ls .git/*.lock 2>/dev/null               # MUST empty

source .venv/bin/activate
which claude codex                      # both MUST resolve
which lint-imports

ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # MUST: 323 pass per halt report
```

If anything diverges → HALT and report.

## Anti-patterns

- Touch any file beyond `tools/autopilot/codex.py` and
  `tests/unit/test_autopilot_keyword_matching.py`.
- Apply plural to `design`, `scope`, `architecture`, `refactor`,
  `redesign`, `security`, `hmac`, `auth`, `schema design`,
  `migration cannot be reversed`. Founder explicit Q1 NO — singular
  dominates for these.
- Push to origin from this prompt — local commit only per Q3.
- Override breaker for findings OUTSIDE keyword sections. Self-dogfood
  exception is path-restricted to `tools/autopilot/codex.py` keyword
  patterns + adjacent tests.
- Run other Claude Code sessions on this repo.
- More than 2 codex rounds in this prompt's continuation (R3 + R4).
  R5+ → escalate to founder.

---

## Step 1 — Apply R2 plural inflection fix

**File:** `tools/autopilot/codex.py`

Modify only these patterns (preserve all others):

**SECURITY_KEYWORDS_SOFT** — add `(?:s)?` suffix to 4 countable nouns:

```python
SECURITY_KEYWORDS_SOFT = [
    re.compile(r"\btoken(?:s)?\b", re.IGNORECASE),       # changed from \btoken\b
    re.compile(r"\bsecret(?:s)?\b", re.IGNORECASE),      # changed from \bsecret\b
    re.compile(r"\bpassword(?:s)?\b", re.IGNORECASE),    # changed
    re.compile(r"\bcredential(?:s)?\b", re.IGNORECASE),  # changed
    re.compile(r"\bhmac\b", re.IGNORECASE),              # KEEP singular (acronym)
    re.compile(r"\bauth\b", re.IGNORECASE),              # KEEP singular (verb-like prefix)
    # Note: \bsecurity\b NOT in SOFT — that's a SEVERE/general check; if present
    # and tripping the dogfood paradox, halt-report says it appears in
    # "security escalation" finding text. Verify if currently in SOFT list.
    # If yes, KEEP singular per Q1 NO.
]
```

**ARCH_KEYWORDS** — add plural inflections to 2 phrase patterns:

```python
ARCH_KEYWORDS = [
    re.compile(r"\bschema design\b", re.IGNORECASE),                   # KEEP singular
    re.compile(r"\bbreaking change(?:s)?\b", re.IGNORECASE),           # changed
    re.compile(r"\binterface change(?:s)?\b", re.IGNORECASE),          # changed
    re.compile(r"\barchitectural\b", re.IGNORECASE),                   # KEEP
    re.compile(r"\barchitecture\b", re.IGNORECASE),                    # KEEP per Q1
    re.compile(r"\brefactor\b", re.IGNORECASE),                        # KEEP per Q1
    re.compile(r"\bredesign\b", re.IGNORECASE),                        # KEEP per Q1
    re.compile(r"\bcontract change(?:s)?\b", re.IGNORECASE),           # changed (defensive)
    re.compile(r"\bmigration cannot be reversed\b", re.IGNORECASE),    # KEEP
    # Note: \bdesign\b, \bscope\b NOT plural'd per Q1
]
```

(Adapt to actual current keyword list — preserve every entry not
explicitly listed above.)

## Step 2 — Add regression tests for plural matches

**File:** `tests/unit/test_autopilot_keyword_matching.py`

Append (don't break existing 23 tests):

```python
def test_security_soft_keyword_tokens_plural_matches() -> None:
    """v0.2.3 r2 P1: 'tokens'/'credentials' plural must match SOFT keywords."""
    f = Finding(severity="P2", summary="multiple tokens cached without expiry")
    assert f.matches_keywords(SECURITY_KEYWORDS_SOFT)

    f2 = Finding(severity="P2", summary="user credentials stored unencrypted")
    assert f2.matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_security_soft_keyword_passwords_secrets_plural_matches() -> None:
    f = Finding(severity="P2", summary="passwords and secrets logged")
    assert f.matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_arch_keyword_changes_plural_matches() -> None:
    """v0.2.3 r2 P2: 'breaking changes'/'interface changes' plural must match."""
    f = Finding(severity="P1", summary="multiple breaking changes in PR")
    assert f.matches_keywords(ARCH_KEYWORDS)

    f2 = Finding(severity="P1", summary="interface changes break consumers")
    assert f2.matches_keywords(ARCH_KEYWORDS)


def test_security_soft_keyword_hmac_singular_only() -> None:
    """Q1: hmac is acronym, no plural form. Sanity counter-test."""
    f = Finding(severity="P2", summary="hmac validation missing")
    assert f.matches_keywords(SECURITY_KEYWORDS_SOFT)

    # 'hmacs' is non-standard; should still match via word boundary if present
    # (verifying we didn't break anything)
    f2 = Finding(severity="P2", summary="HMAC verification step skipped")
    assert f2.matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_arch_keyword_design_singular_dominant() -> None:
    """Q1 NO plural for 'design' — singular dominates Codex output."""
    f = Finding(severity="P1", summary="schema design must be revisited")
    assert f.matches_keywords(ARCH_KEYWORDS)
```

(Adapt fixture style + constructor to repo conventions.)

## Step 3 — Local verify + atomic commit

```bash
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/unit/test_autopilot_keyword_matching.py -v
pytest tests/ -v
```

ALL must pass. Test count: 323 + ~5 new = ~328.

If verify fails → up to 2 retries to fix. After 2 retries → HALT
`VERIFY_REGRESSION`.

```bash
git add tools/autopilot/codex.py tests/unit/test_autopilot_keyword_matching.py
git commit -m "fix(autopilot): R2 — preserve plural inflections in SOFT + ARCH (codex v0.2.3 r2)

Per halt report recommendations:
- SOFT keywords: token/credential/password/secret get \\b...(?:s)?\\b
  to match plurals. hmac/auth kept singular (acronym + verb-prefix).
- ARCH keywords: breaking change(s)/interface change(s)/contract change(s)
  get plural suffix. design/scope/architecture/refactor/redesign kept
  singular per founder Q1 (singular dominates Codex output).

Codex review's own findings about keyword routing tripped the keyword
breakers (recursive self-dogfood paradox). Founder authorized one-time
override for THIS PR. v0.2.4 backlog records pattern; code-level
relaxation revisited if recurrence ≥3 times."
```

## Step 4 — Codex round 3 (with self-dogfood override)

**Concurrency check:**

```bash
ls .git/*.lock 2>/dev/null               # MUST empty
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.3/codex/round-03.txt
```

**Parse R3 output:**

CLEAN — usual phrases (`did not identify any`, `did not find any`,
`no actionable`, `appear internally consistent`, no severity bracket).

FINDING — `- [P0|P1|P2|P3] <summary> — <file>:<lines>`.

### Circuit-breaker checks WITH self-dogfood override:

For each finding, determine target file path:

**If finding is INSIDE `tools/autopilot/codex.py` keyword section** (paths
match `tools/autopilot/codex.py:<line>` AND surrounding context is
keyword regex declarations OR `matches_keywords` function) OR is in
`tests/unit/test_autopilot_keyword_matching.py`:

→ **Apply self-dogfood override**: log finding to halt-report's
`v0.2.4-paradox-log` section but DO NOT halt. Apply minimum-viable fix
(if real bug) OR mark as "advisory only — defer to v0.2.4" if cosmetic.
Continue to next round.

**If finding is OUTSIDE keyword sections** (any other file or any other
`codex.py` location):

→ Normal strict breaker rules apply:

| Check | Action |
|---|---|
| P0 | HALT P0_FOUND |
| Severe security keyword (real, with v0.2.3 word-boundary) | HALT SECURITY_FINDING |
| Soft security keyword + P0/P1 | HALT SECURITY_FINDING |
| Concurrency keyword (real) | HALT CONCURRENCY_FINDING |
| Arch keyword (real) | HALT ARCH_FINDING |
| Same finding hash across rounds | HALT RECURRING_FINDING |
| Otherwise | apply minimum-viable fix, atomic commit |

### Loop logic:

```
After R3:
- ALL findings (if any) are INSIDE keyword section → override applied,
  fixes committed → run R4 confirmation.
- Some findings OUTSIDE keyword section → normal breaker rules → if
  HALT, halt; if fix-able, apply fix + run R4.
- CLEAN → confirms = 1; need R4 for confirms = 2.

After R4:
- CLEAN → confirms = 2 → proceed to Step 5 squash.
- Any finding (any location) → HALT MAX_ROUNDS_THIS_PROMPT.
  Founder decides: ship as-is with documented residual,
  or write follow-up.
```

Track per-round in commit messages:
- `fix(autopilot): address codex round NN keyword section — <summary> (self-dogfood override)`
- For non-keyword fixes: `fix(autopilot): address codex round NN — <summary>`

## Step 5 — Squash to main LOCAL ONLY (when 2× post-fix-confirm OR R4 clean override)

```bash
# Final sanity verify
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v

git checkout main
git pull --ff-only origin main          # critical: dashboard scheduler may have pushed

# Dry-run merge — confirm no conflicts
git merge --no-commit --no-ff chore/autopilot-v0.2.3
git merge --abort

# Real squash
git merge --squash chore/autopilot-v0.2.3
git commit -m "fix(autopilot): v0.2.3 — keyword word-boundary fix (unblock F07)

Mirrors SECURITY_KEYWORDS_SEVERE word-boundary pattern from v0.2.2 R4
across the remaining 3 keyword categories (CONCURRENCY/ARCH/SOFT).
F07 phase B halted on a real P2 finding misclassified as
CONCURRENCY_FINDING because 'lock' substring matched 'block' in
'guarded block'.

Special cases:
- 'lock' compound regex: \\b(?:dead|live)?lock(?:s|ing|ed)?\\b
  catches lock/deadlock/livelock without false-matching block/padlock/
  lockstep.
- 'concurrent' morphology (R1 fix): \\bconcurren(?:t(?:ly)?|cy)\\b
  catches concurrent/concurrently/concurrency.
- SOFT countables (R2 fix): token(s)/credential(s)/password(s)/secret(s)
  get \\b...(?:s)?\\b suffix.
- ARCH phrases (R2 fix): breaking change(s)/interface change(s)/
  contract change(s) get plural suffix.

Singular kept per founder Q1: design/scope/architecture/refactor/
redesign/hmac/auth — singular dominates Codex output.

Codex review (inline, max=5 budget): R1 P2 → fix; R2 P1+P2 → fix;
R3 <result>; R4 <result>. Self-dogfood paradox observed (Codex
explanations of keyword routing trip keyword breakers); founder
authorized one-time override for paths inside
tools/autopilot/codex.py keyword sections.

<final test count> tests pass.

v0.2.4 backlog (cumulative + this release):
- R6 P2 halt-message label diagnostic
- Budget semantics knob split
- Halt-report -resume{N} naming
- Codex stale-blob true fix
- File lock for concurrent-session safety
- Dashboard auto-rebuild push race
- Self-dogfood paradox: keyword-work PRs trip own keyword breakers.
  Manual override OK for now (rare). Revisit if recurrence ≥3 times.

F07 resume unblocked NEXT SESSION."

git branch -D chore/autopilot-v0.2.3
```

**DO NOT push from autopilot.** Per Q3 policy:
- v0.2.3 squash sits as local commit on main.
- Founder reviews + pushes manually:
  ```bash
  git log -1 --format=%B            # review squash message
  git diff origin/main..main        # review diff
  git push origin main
  # If reject (auto-rebuild race): git pull --rebase origin main && git push origin main
  ```

## Step 6 — Final report

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.3 — Keyword word-boundary fix — LOCAL READY
═══════════════════════════════════════════════════════

Local squash commit: <SHA> on main (NOT pushed — founder pushes per Q3)
Branch chore/autopilot-v0.2.3: DELETED

Codex review sequence (cumulative across 2 sessions):
  R1: P2 → fix 097a3f6 ('concurrent' morphology)
  R2: P1+P2 → fix <SHA this session> (SOFT plurals + ARCH plurals)
  R3: <CLEAN | finding details>
    <if finding inside keyword section: self-dogfood override applied,
     fix SHA: <SHA>>
    <if finding outside: HALT or fix per rules>
  R4: <CLEAN | finding details>
  Final state: 2× post-fix-confirm clean (or override-equivalent) at R<X>+R<Y>
  Artifacts: .autopilot/state/v0.2.3/codex/round-{01..04}.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean
  lint-imports: clean
  pytest:       <count> passed

Files modified:
  - tools/autopilot/codex.py
  - tests/unit/test_autopilot_keyword_matching.py
  - CHANGELOG.md (from R1 commit)

Self-dogfood paradox events:
  <list any R3/R4 findings that triggered override + fix applied>

═══════════════════════════════════════════════════════

Founder next steps:

1. Push v0.2.3 to origin/main (per Q3 manual-push policy):
     git log -1 --format=%B
     git diff origin/main..main | head -100
     git push origin main
     # Reject case: git pull --rebase origin main && git push origin main

2. Resume F07 with v0.2.3 orchestrator:
     git checkout feat/F07-settings
     git merge main -m "merge: v0.2.3 (keyword word-boundary) into feat/F07-settings"
     # Resolve conflicts if any

     python3 -c "import json; from pathlib import Path; p = Path('.autopilot/state/F07/state.json'); s = json.loads(p.read_text()); s.update({'phase': 'VERIFIED', 'current_round': 0, 'consecutive_clean_rounds': 0, 'halt_reason': None, 'halt_artifact_path': None, 'fixed_finding_hashes': []}); p.write_text(json.dumps(s, indent=4) + '\\n'); print('reset')"

     source .venv/bin/activate
     python -m tools.autopilot resume F07

3. v0.2.4 backlog (per CHANGELOG known-issues + this run's additions).

End of autopilot v0.2.3.
═══════════════════════════════════════════════════════
```

Then STOP.

---

## Circuit breakers (with self-dogfood override path-restricted)

Write `.autopilot/state/v0.2.3/halt-report.md` if ANY trigger fires:

1. Pre-flight regression.
2. VERIFY_REGRESSION (verify fails 2× consecutively).
3. P0_FOUND (any location — override does NOT extend to P0).
4. SECURITY_FINDING (severe, real, OUTSIDE keyword section).
5. CONCURRENCY_FINDING (real, OUTSIDE keyword section).
6. ARCH_FINDING (real, OUTSIDE keyword section).
7. RECURRING_FINDING.
8. MAX_ROUNDS_THIS_PROMPT (R4 done without 2× clean — strict in this
   continuation).
9. TYPE_IGNORE_PROPOSED.
10. SCOPE_CREEP (modifications outside expected file list).
11. CONCURRENT_AGENT_DETECTED.
12. Tool error 2× in a row.
13. Context budget >70%.

### Halt report template

```
HALT — autopilot v0.2.3 finish-r2 circuit broken.

Step:    <step + description>
Trigger: <one of 13>
Branch:  chore/autopilot-v0.2.3
HEAD:    <SHA>

Detail:
<error / finding excerpt>

Codex sequence (cumulative):
  R1: <result>
  R2: <result>
  R3: <result>
  R4: <result if reached>

Self-dogfood overrides applied: <list any>
Files modified this session: <list>

Continuation hint:
<sketch of next prompt or manual fix>

Founder action requested:
<specific question>
```

---

## Global rules

1. READ FIRST — halt-report's "Recommended fix" + R2 codex output.
2. SCOPE STRICT: only `codex.py` keyword patterns + test file.
3. NEVER force-push.
4. NEVER `# type: ignore`.
5. NEVER push from this prompt — local commit only per Q3.
6. Atomic commits per logical change.
7. Verify before claiming done.
8. Tool error 2× → circuit breaker.
9. Context budget >70% → pause + halt.
10. Self-dogfood override is PATH-RESTRICTED to `tools/autopilot/codex.py`
    keyword sections + test file. Findings elsewhere use normal strict
    breaker rules.
11. P0 findings ALWAYS halt regardless of location (P0 > self-dogfood
    override).
12. Hard limit: R3 + R4 only. R5 → HALT MAX_ROUNDS_THIS_PROMPT.

Begin with Pre-flight, then Step 1. Execute through Step 6.
