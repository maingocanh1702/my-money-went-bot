# Task: Autopilot v0.2.3 — Keyword word-boundary fix (unblock F07)

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT — single-phase on new branch `chore/autopilot-v0.2.3`.
SOLO scope: word-boundary regex match for `CONCURRENCY_KEYWORDS`,
`ARCH_KEYWORDS`, `SECURITY_KEYWORDS_SOFT` — mirror the
`SECURITY_KEYWORDS_SEVERE` pattern v0.2.2 R2/R4 already established.
Inline Codex review ≤3 rounds with v0.2.2's expanded budget (max=5
fix + 2 post-fix-confirm). Squash + push to main.

**Out of scope (deferred to v0.2.4 batch when items surface as friction):**
- R6 P2 halt-message label diagnostic
- Budget semantics knob split (max_fix_rounds + post_fix_confirm)
- Halt-report `-resume{N}` naming
- Codex stale-blob true fix
- File lock for concurrency

**Context (NOT for execution, just background):**

F07 resume Phase B halted on R2 because Codex flagged a real P2
(`emit_analytics()` `json.dumps(...)` outside `try` block) but the
orchestrator misclassified as CONCURRENCY_FINDING. Root cause: the
finding text contained "guarded block" — `CONCURRENCY_KEYWORDS` includes
`"lock"` which matched the substring inside `"block"`.

Same class as v0.2.2 R2 ("rce" in "force"). v0.2.2 fixed
`SECURITY_KEYWORDS_SEVERE` with word-boundary regex but did NOT propagate
to the other 3 keyword categories. This prompt closes that gap.

**Critical:** "lock" specifically needs a stricter pattern than just
`\block\b` because compounds matter:
- Should match: `lock`, `locks`, `locking`, `locked`, `deadlock`,
  `livelock` (+ variants)
- Should NOT match: `block`, `blocking`, `blocker`, `padlock`,
  `lockstep`, `lockable`, `wedlock`

Recommended regex: `\b(?:dead|live)?lock(?:s|ing|ed)?\b`

Verify match table (in regression tests):

| Word | Should match? |
|---|---|
| `lock` | ✓ |
| `locks` / `locking` / `locked` | ✓ |
| `deadlock` / `deadlocks` / `deadlocked` | ✓ |
| `livelock` / variants | ✓ |
| `block` / `blocking` / `blocker` | ✗ |
| `padlock` / `lockstep` / `lockable` | ✗ |

For other keywords, simple `\b<keyword>\b` boundary is sufficient.

## Required reading (READ FIRST, in order)

1. `tools/autopilot/codex.py` — read current implementation of
   `SECURITY_KEYWORDS_SEVERE`, `SECURITY_KEYWORDS_SOFT`, `ARCH_KEYWORDS`,
   `CONCURRENCY_KEYWORDS`. Note exactly how SEVERE keyword matching
   works post-v0.2.2 R4 (regex-based, word-boundary). Mirror the same
   pattern for the other 3 categories.
2. `tools/autopilot/circuit_breaker.py` — `evaluate()` security check.
   Confirm matching logic still works after keyword type change.
3. `.autopilot/state/F07/phase-b-halt-report.md` — context on why this
   prompt exists.
4. `.autopilot/state/F07/codex/round-02-resume1.txt` — the F07 R2
   finding text that triggered the false-positive (contains "guarded
   block" / "block" substrings).
5. `CHANGELOG.md` — v0.2.2 known-issues subsection (where the
   word-boundary item is listed).

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean
git branch --show-current               # MUST: main
git pull --ff-only origin main
git log --oneline -3
# Top should include c788a64 (F07 prompt) or later if more pushed

# v0.2.2 features confirmed on main
grep -q "SECURITY_KEYWORDS_SEVERE" tools/autopilot/codex.py
grep -q "confirmation_rounds_after_last_fix" tools/autopilot/loop.py
# Both MUST succeed

# Concurrency check
ls .git/*.lock 2>/dev/null
# MUST be empty

# Verify no other agent active
ls -la .git/HEAD.lock .git/index.lock 2>/dev/null
# MUST be empty

source .venv/bin/activate
which claude codex                      # both MUST resolve
which lint-imports                      # MUST resolve

# Tooling baseline green
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # capture baseline count (~290)
```

If any pre-flight fails → HALT, no proceed.

## Anti-patterns (NEVER do)

- Touch any file beyond `tools/autopilot/codex.py`,
  `tools/autopilot/circuit_breaker.py` (if needed),
  `tests/unit/test_autopilot_codex.py` (or new test file),
  `CHANGELOG.md`.
- Apply other v0.2.4 backlog items (R6 P2, budget split, etc.). SOLO
  scope here.
- `git push --force`.
- Add `# type: ignore` (circuit breaker).
- Run other Claude Code sessions on this repo.
- Auto-merge with `--auto-merge` flag.
- Push to origin/main without final inspection. Founder may want to
  push manually if classifier blocks (Phase C lesson).

---

## Step 1 — Branch creation

```bash
git checkout -b chore/autopilot-v0.2.3
mkdir -p .autopilot/state/v0.2.3/codex
```

## Step 2 — Inspect current keyword implementation

```bash
sed -n '1,80p' tools/autopilot/codex.py
```

Locate the 4 keyword groups + the matching function. Confirm v0.2.2 made
`SECURITY_KEYWORDS_SEVERE` use compiled regex with `\b` boundary, while
`CONCURRENCY_KEYWORDS`, `ARCH_KEYWORDS`, `SECURITY_KEYWORDS_SOFT`
remained as plain string lists matched via substring `in` operator.

If the code structure differs from this assumption → adapt fix
accordingly, but core principle is: convert ALL 4 keyword categories
to regex with word-boundary matching.

## Step 3 — Implement word-boundary regex for 3 remaining categories

**File:** `tools/autopilot/codex.py`

Convert `CONCURRENCY_KEYWORDS`, `ARCH_KEYWORDS`, `SECURITY_KEYWORDS_SOFT`
from string tuples to compiled regex patterns. Mirror the
`SECURITY_KEYWORDS_SEVERE` style.

Special case for `"lock"`: use the compound regex
`\b(?:dead|live)?lock(?:s|ing|ed)?\b` so that `block`/`padlock`/
`lockstep` etc. do NOT match.

Other keywords use simple `\b<keyword>\b` (case-insensitive).

Sketch (adapt to actual current structure):

```python
import re

# SECURITY_KEYWORDS_SEVERE — already regex per v0.2.2 R4
# SECURITY_KEYWORDS_SEVERE = [
#     re.compile(r"\bauth bypass\b", re.IGNORECASE),
#     ...
# ]

# v0.2.3: mirror pattern for the other 3 categories.

CONCURRENCY_KEYWORDS = [
    re.compile(r"\brace\b", re.IGNORECASE),
    re.compile(r"\brace condition\b", re.IGNORECASE),
    re.compile(r"\bdata race\b", re.IGNORECASE),
    re.compile(r"\bconcurrent\b", re.IGNORECASE),
    re.compile(r"\b(?:dead|live)?lock(?:s|ing|ed)?\b", re.IGNORECASE),
    re.compile(r"\batomic\b", re.IGNORECASE),
    re.compile(r"\btransaction\b", re.IGNORECASE),
]

ARCH_KEYWORDS = [
    re.compile(r"\bschema design\b", re.IGNORECASE),
    re.compile(r"\bbreaking change\b", re.IGNORECASE),
    re.compile(r"\barchitectural\b", re.IGNORECASE),
    re.compile(r"\barchitecture\b", re.IGNORECASE),
    re.compile(r"\brefactor\b", re.IGNORECASE),
    re.compile(r"\bredesign\b", re.IGNORECASE),
    re.compile(r"\binterface change\b", re.IGNORECASE),
    re.compile(r"\bcontract change\b", re.IGNORECASE),
    re.compile(r"\bmigration cannot be reversed\b", re.IGNORECASE),
]

SECURITY_KEYWORDS_SOFT = [
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bhmac\b", re.IGNORECASE),
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bcredential\b", re.IGNORECASE),
    re.compile(r"\bauth\b", re.IGNORECASE),
]
```

(Adapt list contents to whatever's currently there. Some items above are
inferred from typical autopilot keyword lists — if current code has
different items, preserve them. The important change is the matcher
semantics, not the list contents.)

**Update matching function** (likely in `Finding.matches_keywords()` or
similar):

```python
def matches_keywords(self, keywords: list[re.Pattern[str]] | tuple[str, ...]) -> bool:
    """Match if any keyword pattern is found in this finding's text.

    v0.2.3: keywords param now accepts list of compiled regex patterns
    OR legacy tuple of strings (backward-compat for SEVERE keywords if
    unchanged). Word-boundary regex prevents substring false positives
    (e.g., "lock" in "block" — F07 v0.2.3 r1 P1).
    """
    text = (self.summary + " " + self.detail_text)
    for kw in keywords:
        if isinstance(kw, re.Pattern):
            if kw.search(text):
                return True
        else:
            # legacy string fallback (deprecated; remove in v0.3.0)
            if kw.lower() in text.lower():
                return True
    return False
```

(Adapt to actual function signature.)

**Update `circuit_breaker.py`** if it does keyword check directly rather
than via `Finding.matches_keywords()`. Verify the call sites still work
with the new regex-list type.

## Step 4 — Add regression tests

**File:** `tests/unit/test_autopilot_codex.py` (extend existing) or
`tests/unit/test_autopilot_keyword_matching.py` (new — adapt to repo
convention).

Add tests for each of the 3 categories. Critical fixtures:

```python
def test_concurrency_keyword_lock_does_not_match_block() -> None:
    """v0.2.3 r1 P1: 'lock' substring inside 'block' must NOT trigger
    CONCURRENCY_FINDING. Caught by F07 phase B halt 2026-05-13."""
    f = Finding(
        severity="P2",
        summary="Move serialization inside the guarded block",
        detail=["text with 'blocking' and 'blocker' words"],
    )
    assert not f.matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_keyword_lock_matches_deadlock() -> None:
    """Deadlock IS a concurrency concern."""
    f = Finding(severity="P1", summary="Potential deadlock between mutexes")
    assert f.matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_keyword_lock_matches_standalone() -> None:
    """Plain 'lock contention' is a concurrency concern."""
    f = Finding(severity="P2", summary="lock contention on shared cache")
    assert f.matches_keywords(CONCURRENCY_KEYWORDS)


def test_concurrency_keyword_padlock_does_not_match() -> None:
    """'padlock' is not concurrency."""
    f = Finding(severity="P3", summary="padlock metaphor in error message")
    assert not f.matches_keywords(CONCURRENCY_KEYWORDS)


def test_arch_keyword_scope_does_not_match_telescope() -> None:
    """'scope' must word-boundary; telescope/microscope etc. should not match."""
    f = Finding(severity="P3", summary="telescope-shaped backoff strategy")
    assert not f.matches_keywords(ARCH_KEYWORDS)


def test_security_soft_keyword_token_word_boundary() -> None:
    """'token' must word-boundary; 'tokenize' should not match."""
    f = Finding(severity="P3", summary="tokenizer normalization missing")
    assert not f.matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_security_soft_keyword_token_matches_standalone() -> None:
    f = Finding(severity="P2", summary="webhook token logged in plain text")
    assert f.matches_keywords(SECURITY_KEYWORDS_SOFT)


def test_concurrency_keyword_atomic_word_boundary() -> None:
    """'atomic' must word-boundary; 'subatomic'/'diatomic' should not match."""
    f = Finding(severity="P3", summary="diatomic gas analogy in docs")
    assert not f.matches_keywords(CONCURRENCY_KEYWORDS)


def test_arch_keyword_refactor_word_boundary() -> None:
    """'refactor' must word-boundary."""
    f = Finding(severity="P2", summary="refactoring opportunity in module X")
    assert f.matches_keywords(ARCH_KEYWORDS)


def test_concurrency_keyword_transaction_word_boundary() -> None:
    """'transaction' must match standalone, not 'transactional' if list
    only has bare word — but matches if pattern is liberal. Verify."""
    f = Finding(severity="P2", summary="DB transaction not committed")
    assert f.matches_keywords(CONCURRENCY_KEYWORDS)
```

(Adapt fixture names + locations + Finding constructor to actual repo
patterns.)

Add at least 2 tests per keyword category (1 positive, 1 negative
substring) for total ~10 tests.

## Step 5 — CHANGELOG entry

**File:** `CHANGELOG.md`

Under `## [Unreleased]`, add subsection:

```markdown
### Fixed — Autopilot v0.2.3 (keyword word-boundary)

- `CONCURRENCY_KEYWORDS`, `ARCH_KEYWORDS`, `SECURITY_KEYWORDS_SOFT` now
  use compiled regex with `\b` word boundary, mirroring
  `SECURITY_KEYWORDS_SEVERE` pattern from v0.2.2 R4. Closes the gap
  that caused F07 phase B halt — Codex finding "Move serialization
  inside the guarded block" had "lock" substring inside "block",
  triggering false CONCURRENCY_FINDING circuit breaker.
- `"lock"` keyword uses compound regex
  `\b(?:dead|live)?lock(?:s|ing|ed)?\b` to match `lock`/`deadlock`/
  `livelock` variants without false-matching `block`/`padlock`/
  `lockstep`.

### Notes — v0.2.4 backlog (deferred items from v0.2.2/v0.2.3 cumulative)

- R6 P2 halt-message label diagnostic (cosmetic only).
- Budget semantics knob split: max_fix_rounds + confirmation_rounds.
- Halt-report `-resume{N}` naming consistency.
- Codex CLI stale-blob true fix (currently logs warning only).
- File lock for concurrent-session safety (currently doc-only policy).
- Dashboard auto-rebuild scheduler races with founder pushes (cyclic
  rebase observed during v0.2.2 + v0.2.3 ship).
```

## Step 6 — Local verify + atomic commits

```bash
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
```

ALL must pass. Test count: baseline + ~10 new tests.

If verify fails → up to 2 retries. After 2 retries → HALT
`VERIFY_REGRESSION`.

```bash
git add tools/autopilot/codex.py
git add tools/autopilot/circuit_breaker.py  # only if modified
git commit -m "fix(autopilot): word-boundary regex for CONCURRENCY/ARCH/SOFT keyword categories (v0.2.3 r1)

Mirrors SECURITY_KEYWORDS_SEVERE pattern from v0.2.2 R4 (already regex
with \\b boundary). Substring-match in legacy keyword tuples caused
false-positive halt during F07 phase B: Codex finding 'Move
serialization inside the guarded block' triggered CONCURRENCY_FINDING
because 'lock' substring matched 'block'.

'lock' specifically uses compound regex
\\b(?:dead|live)?lock(?:s|ing|ed)?\\b
to catch lock/deadlock/livelock variants without false-matching
block/padlock/lockstep/wedlock."

git add tests/unit/test_autopilot_codex.py
git commit -m "test(autopilot): keyword word-boundary regression suite

10 fixtures covering substring hazards (lock-in-block, scope-in-telescope,
token-in-tokenize, atomic-in-diatomic, etc.) plus positive matches
(deadlock, lock contention, refactor, transaction)."

git add CHANGELOG.md
git commit -m "docs: changelog v0.2.3 — keyword word-boundary fix + v0.2.4 backlog"
```

## Step 7 — Inline Codex review (max=5 budget, post-fix-confirm=2)

Use v0.2.2's expanded budget. Up to 5 fix rounds + need 2 post-fix-confirm
clean rounds.

**Round N (1-5):**

```bash
ls .git/*.lock 2>/dev/null               # MUST empty
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.3/codex/round-NN.txt
```

**Parse output** + circuit-breaker checks (same pattern as prior
prompts; use v0.2.3's own new word-boundary logic — eat-own-dogfood):

| Check | Action |
|---|---|
| P0 | HALT P0_FOUND |
| Severe security keyword (real, with new word-boundary) | HALT SECURITY_FINDING |
| Soft security keyword + P0/P1 (with word-boundary) | HALT SECURITY_FINDING |
| Concurrency keyword (with new word-boundary, no more "lock" false positive) | HALT CONCURRENCY_FINDING |
| Arch keyword (with new word-boundary) | HALT ARCH_FINDING |
| Same finding hash across rounds | HALT RECURRING_FINDING |
| Otherwise | apply minimum-viable fix, atomic commit |

**Loop logic:**

```
fixes_applied = 0
confirms = 0
round_n = 0

while True:
    round_n += 1
    if round_n > 5:
        HALT MAX_FIX_BUDGET_EXHAUSTED
    
    run codex round; parse
    
    if CLEAN:
        confirms += 1
        if confirms >= 2:
            break
        continue
    
    if any breaker triggers:
        HALT
    
    apply fix; atomic commit; fixes_applied += 1
    confirms = 0
    local verify MUST pass; if fails 2x → HALT VERIFY_REGRESSION
```

## Step 8 — Squash to main + LOCAL push (founder pushes)

When 2× post-fix-confirm achieved:

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

'lock' specifically uses compound regex
\\b(?:dead|live)?lock(?:s|ing|ed)?\\b — catches lock/deadlock/livelock
variants without false-matching block/padlock/lockstep.

Codex review (inline): R1 <result> + R2 <result> + ... 2× post-fix-
confirm clean confirmed at R<X>+R<Y>.

<final test count> tests pass.

v0.2.4 backlog (deferred from v0.2.2 + this release):
- R6 P2 halt-message label diagnostic
- Budget semantics knob split
- Halt-report -resume{N} naming
- Codex stale-blob true fix
- File lock for concurrent-session safety
- Dashboard auto-rebuild push race

F07 resume unblocked NEXT SESSION: founder runs
\`python -m tools.autopilot resume F07\` after merging main into F07."

git branch -D chore/autopilot-v0.2.3
```

**DO NOT push from autopilot.** Per Q3 founder decision:
- v0.2.3 squash sits as local commit on main.
- Founder reviews + pushes manually:
  ```bash
  git log -1 --format=%B            # review the squash message
  git diff origin/main..main        # review the diff
  git push origin main
  ```

If dashboard auto-rebuild caused new commits between squash and founder
push → founder rebases manually:
  ```bash
  git pull --rebase origin main
  git push origin main
  ```

## Step 9 — Final report

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.3 — Keyword word-boundary fix — LOCAL READY
═══════════════════════════════════════════════════════

Local squash commit: <SHA> on main (NOT pushed — founder pushes per Q3)
Branch chore/autopilot-v0.2.3: DELETED

Codex review sequence (inline, max=5 budget):
  R1: <CLEAN | finding details + fix SHA>
  R2: <...>
  R3: <... if reached>
  R4: <... if reached>
  R5: <... if reached>
  Final state: 2× post-fix-confirm clean at R<X>+R<Y>
  Artifacts: .autopilot/state/v0.2.3/codex/round-*.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean (no new errors)
  lint-imports: clean
  pytest:       <count> passed (baseline + ~10 new tests)

Files modified:
  - tools/autopilot/codex.py
  - tools/autopilot/circuit_breaker.py (if needed)
  - tests/unit/test_autopilot_codex.py
  - CHANGELOG.md

═══════════════════════════════════════════════════════

Founder next steps:

1. Push v0.2.3 to origin/main (per Q3 manual-push policy):
     git log -1 --format=%B
     git diff origin/main..main | head -100
     git push origin main
     # If reject (auto-rebuild race): git pull --rebase origin main && git push origin main

2. Resume F07 with v0.2.3 orchestrator:
     git checkout feat/F07-settings
     git merge main -m "merge: v0.2.3 (keyword word-boundary) into feat/F07-settings"
     # Resolve conflicts if any (likely CHANGELOG)

     python3 -c "import json; from pathlib import Path; p = Path('.autopilot/state/F07/state.json'); s = json.loads(p.read_text()); s.update({'phase': 'VERIFIED', 'current_round': 0, 'consecutive_clean_rounds': 0, 'halt_reason': None, 'halt_artifact_path': None, 'fixed_finding_hashes': []}); p.write_text(json.dumps(s, indent=4) + '\\n'); print('reset')"

     source .venv/bin/activate
     python -m tools.autopilot resume F07

   Expected: orchestrator routes the F07 R2 emit_analytics finding
   through Phase C fix flow (not CONCURRENCY_FINDING halt). Either
   auto-fixes via claude_codegen + 2× post-fix-confirm → READY,
   OR halts on a different real issue (escalation case).

3. v0.2.4 backlog: stale items + new items from v0.2.3 own review (if any).

End of autopilot v0.2.3.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles push + F07 resume.

---

## Circuit breakers

Write `.autopilot/state/v0.2.3/halt-report.md` if ANY trigger fires:

1. Pre-flight regression.
2. VERIFY_REGRESSION (verify fails 2× consecutively).
3. P0_FOUND.
4. SECURITY_FINDING (severe, real with v0.2.3 word-boundary).
5. CONCURRENCY_FINDING (real with v0.2.3 word-boundary — eat own dogfood).
6. ARCH_FINDING (real with v0.2.3 word-boundary).
7. RECURRING_FINDING.
8. MAX_FIX_BUDGET_EXHAUSTED (R5 done without 2× confirm).
9. TYPE_IGNORE_PROPOSED.
10. SCOPE_CREEP (modifications outside expected file list).
11. CONCURRENT_AGENT_DETECTED (`.git/*.lock` mid-flight).
12. Tool error 2× in a row.
13. Context budget >70%.

### Halt report template

```
HALT — autopilot v0.2.3 circuit broken.

Step:    <step number + description>
Trigger: <one of 13>
Branch:  chore/autopilot-v0.2.3
HEAD:    <SHA>

Detail:
<error / finding excerpt>

Codex sequence so far:
  R1: <result>
  R2: <result>
  ...

Files modified this session: <list>

Continuation hint:
<specific follow-up prompt sketch>

Founder action requested:
<specific question or decision>
```

---

## Global rules

1. READ FIRST. codex.py current implementation before mirroring pattern.
2. SCOPE STRICT: only the 4 keyword categories + tests + CHANGELOG.
   NO v0.2.4 backlog items in this prompt.
3. NEVER force-push.
4. NEVER `# type: ignore`.
5. NEVER push to origin from this prompt — local commit only, founder
   pushes per Q3 policy.
6. Atomic commits per logical change (keyword fix, tests, changelog
   each separate).
7. Verify before claiming done — re-run pytest after every fix.
8. Tool error 2× → circuit breaker.
9. Context budget >70% → pause + halt.
10. Concurrency check (`ls .git/*.lock`) before EACH Codex round.
11. v0.2.4 items mentioned in halt-report or final-report only — do NOT
    fix in this prompt.

Begin with Pre-flight, then Step 1. Execute through Step 9.
