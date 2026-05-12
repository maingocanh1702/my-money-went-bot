# Task: Autopilot v0.2.1 — fix Codex parser + halt-writer + resume-from-HALTED

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT — single feature branch
`chore/autopilot-v0.2.1-codex-parser-fix`, inline Codex review with ≤3 fix
rounds, then squash-merge to main + push. Pause ONLY on circuit-breaker
conditions.

**Context (NOT for execution, just background):**
Pilot run of F07 (Settings) revealed 3 bugs in orchestrator v0.2.0:

1. **`codex.parse_findings` early-return:** Codex CLI v0.130 sometimes emits
   only the review verdict (~900 bytes) without preamble + diff + `codex`
   marker line. Parser at codex.py:178-182 returns `([], False)` when no
   `^codex$` line found. Loop then triggers fix with empty findings → 0
   commits → `FIX_FAILED` breaker. F07 was halted this way despite Codex
   round 1 actually finding a legitimate P2 bug.
2. **Halt-report writer is conditional:** `_halt` helper in loop.py:267-285
   transitions state to HALTED + saves state, but does NOT call
   `circuit_breaker.write_halt_report`. Only the breaker path inside Phase
   C writes the forensic file. All other halt reasons (CODEGEN_FAILED,
   VERIFY_FAIL, FIX_FAILED, VERIFY_REGRESSION, MAX_ROUNDS, MERGE_GATE_FAIL)
   leave `state.halt_artifact_path = null` — no forensic file written.
3. **Resume-from-HALTED is silent no-op:** loop.run() checks
   `phase in {INIT, CODEGEN, VERIFIED, REVIEWING, READY}`. When phase is
   HALTED, none of the branches fire → returns
   `"Already at <phase> — nothing to do"`. There's no way to resume after
   the bug is fixed without manually editing state.json.

**Scope of this prompt:** ONLY the v0.2.1 orchestrator fix. F07 resume is
done manually by founder AFTER v0.2.1 lands on main (instructions in the
final-report block below). Do NOT touch F07 branch in this run.

## Required reading (READ FIRST, in this order, before any code)

1. `tools/autopilot/codex.py` — full parser (242 lines). Focus on
   `parse_findings` (line 168), `CLEAN_PHRASES` (line 23), `SEVERITY_RE`
   (line 31), `FILE_RE` (line 35).
2. `tools/autopilot/loop.py` — full loop (395 lines). Focus on `_halt`
   helper (line 267), `run()`'s Phase C section (line 142), and the
   fall-through `return RunOutcome` at line 256.
3. `tools/autopilot/circuit_breaker.py` — find `write_halt_report`
   function (called from loop.py:169). Understand its current signature
   and output format.
4. `tools/autopilot/state.py` — `FeatureState` dataclass + transition +
   save logic. Need to add `last_active_phase` field.
5. `tests/unit/test_autopilot_codex.py` (if exists) — match test style.
   If module doesn't exist, look at `tests/unit/test_autopilot_state.py`
   or `tests/unit/test_autopilot_claude_codegen.py` for pattern.
6. **Real Codex outputs (fixtures source):**
   - `.autopilot/state/F07/codex/round-01.txt` — Codex finding P2 on
     `emit_analytics`. 893 bytes, no `codex` marker, no preamble.
   - `.autopilot/state/F07/codex/round-02.txt` — Codex clean verdict.
     273 bytes, no marker, no preamble.
   - `.autopilot/state/webhook-display-suffix/codex/round-01.txt` —
     14KB, has preamble + `codex` marker + clean verdict.
   - `.autopilot/state/webhook-display-suffix/codex/round-02.txt` —
     14KB, has preamble + `codex` marker + clean verdict.
   These are gold standard real-CLI outputs — DO NOT synthesize fake
   ones. Copy them into a tracked fixtures dir.
7. `docs/operations/autopilot-implementation-plan.md` v0.2.0 §6.5 — risk
   tier. This change is orchestrator P1 (manual merge after Codex audit).

## Pre-flight (run first, HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean
git branch --show-current               # MUST be: main
git fetch origin && git pull --ff-only origin main
git log --oneline -3                    # 9fda57f docs(prompts) at HEAD or later

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling green
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v                        # MUST be green (219 pass baseline)

python -m tools.autopilot preflight     # ALL 8 PASS
```

ALL must pass. If any fails → HALT and report. Do not proceed.

**Important:** F07 state file at `.autopilot/state/F07/state.json` shows
`phase: HALTED`. Leave it alone — that's intentional. Founder resumes F07
manually after v0.2.1 ships.

## Anti-patterns (NEVER do)

- `git push --force`.
- Synthesize fake Codex outputs for fixtures — use the 4 real files listed
  above. The whole point is that synthetic fixtures hid these bugs.
- Add a `# type: ignore` (circuit breaker — founder approval needed).
- Touch F07 branch or `.autopilot/state/F07/state.json` in this run.
- Modify `resolve_token` or any other unrelated production code.
- Auto-merge without Codex 2× clean (P1 change).
- Use sandbox/Cowork session — YOU are the Mac terminal authority.

---

## Step 1 — Branch + capture base SHA

```bash
git checkout -b chore/autopilot-v0.2.1-codex-parser-fix
git rev-parse HEAD > /tmp/v021-base-sha.txt
mkdir -p .autopilot/state/v0.2.1-fix/codex
```

## Step 2 — Copy real Codex outputs as test fixtures

```bash
mkdir -p tests/fixtures/codex
cp .autopilot/state/F07/codex/round-01.txt \
   tests/fixtures/codex/f07-round-01-p2-no-marker.txt
cp .autopilot/state/F07/codex/round-02.txt \
   tests/fixtures/codex/f07-round-02-clean-no-marker.txt
cp .autopilot/state/webhook-display-suffix/codex/round-01.txt \
   tests/fixtures/codex/w08-round-01-clean-with-marker.txt
cp .autopilot/state/webhook-display-suffix/codex/round-02.txt \
   tests/fixtures/codex/w08-round-02-clean-with-marker.txt
```

These fixtures ARE tracked in git. They cover both observed CLI output
formats. Future parser tests build on this gold-standard set.

## Step 3 — Write FAILING tests first (TDD)

**File:** `tests/unit/test_autopilot_codex.py` — either extend if exists
or create new.

Add the following test functions (use `pytest.fixture` for fixture loader):

```python
from pathlib import Path
from tools.autopilot.codex import parse_findings

FIXTURES = Path(__file__).parent.parent / "fixtures" / "codex"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_findings_no_marker_extracts_p2_finding() -> None:
    """F07 round 1: real Codex output, no `codex` marker line, has P2 finding.

    Current parser early-returns ([], False) — this is bug #1 in v0.2.1.
    After fix, parser must fall through to severity-regex extraction even
    when marker is absent.
    """
    findings, clean = parse_findings(_read("f07-round-01-p2-no-marker.txt"))
    assert clean is False
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "P2"
    assert "analytics insert" in f.summary.lower()
    assert f.file is not None and f.file.endswith("settings_svc.py")
    assert f.line_start == 270
    assert f.line_end == 279


def test_parse_findings_no_marker_detects_clean() -> None:
    """F07 round 2: real Codex output, no marker, clean verdict.

    Phrase "did not find any concrete, actionable regressions" must match
    CLEAN_PHRASES even without the marker.
    """
    findings, clean = parse_findings(_read("f07-round-02-clean-no-marker.txt"))
    assert clean is True
    assert findings == []


def test_parse_findings_with_marker_still_clean() -> None:
    """W0.8 round 1: real Codex output WITH preamble + marker, clean verdict.

    Regression guard — fixing bug #1 must not break the existing marker
    path. Phrase "did not identify any actionable bugs" matches.
    """
    findings, clean = parse_findings(_read("w08-round-01-clean-with-marker.txt"))
    assert clean is True
    assert findings == []


def test_parse_findings_with_marker_round_02() -> None:
    """W0.8 round 2: marker + alternative clean phrasing.

    Phrase: "I did not identify any introduced defects" — must match.
    May require expanding CLEAN_PHRASES; that's allowed and expected.
    """
    findings, clean = parse_findings(_read("w08-round-02-clean-with-marker.txt"))
    assert clean is True
    assert findings == []


def test_parse_findings_truly_malformed_returns_uncertain() -> None:
    """Defensive: garbage input → findings=[], clean=False (uncertain).

    Loop will halt via PARSER_UNCERTAIN breaker rather than fix-loop blindly.
    """
    findings, clean = parse_findings("this is not a codex review at all")
    assert findings == []
    assert clean is False
```

Run pytest — these 5 tests MUST FAIL on current main (well, 3 of 5 — the
W0.8 marker tests may already pass). The 2 F07-no-marker tests MUST fail.

```bash
pytest tests/unit/test_autopilot_codex.py -v
```

If F07 tests pass on first run → something's off. Investigate before
proceeding (maybe parser was already fixed in a way you missed).

## Step 4 — Fix `codex.parse_findings`

**File:** `tools/autopilot/codex.py`

**Change 1 — Make `codex` marker optional:**

```python
def parse_findings(output: str) -> tuple[list[Finding], bool]:
    lines = output.splitlines()
    codex_markers = [i for i, line in enumerate(lines) if line.strip() == "codex"]

    # If marker absent, treat the entire output as the review section.
    # Codex CLI v0.130+ in subprocess context sometimes emits just the
    # verdict text (no preamble, no diff dump, no `codex` line).
    # Marker-based path is preferred when available (separates review from
    # the diff dump), but fall back to whole-output parsing otherwise.
    if codex_markers:
        review_lines = lines[codex_markers[0]:]
    else:
        review_lines = lines

    review_text = "\n".join(review_lines).lower()

    if any(phrase in review_text for phrase in CLEAN_PHRASES):
        return [], True

    # ... rest of finding extraction unchanged ...
```

**Change 2 — Expand `CLEAN_PHRASES`:**

```python
CLEAN_PHRASES = (
    "did not identify any discrete",
    "did not identify any actionable",
    "did not identify any introduced defects",  # ← new (W0.8 r2)
    "did not find any",
    "no actionable regressions",
    "no actionable defects",
    "appear internally consistent",              # ← new (W0.8 r2 alt phrase)
)
```

Verify CLEAN_PHRASES expansion against actual fixtures — open each
`tests/fixtures/codex/*.txt` and confirm at least one phrase from
CLEAN_PHRASES literally appears (case-insensitive). If a fixture lacks
any phrase, add a new phrase OR confirm that file genuinely has findings.

## Step 5 — Add `PARSER_UNCERTAIN` circuit breaker

**Why:** if parser returns `findings=[], clean=False` (truly malformed
Codex output, or new format we haven't seen), the loop should halt with
a meaningful reason instead of triggering empty-fix → FIX_FAILED.

**File:** `tools/autopilot/circuit_breaker.py`

Add a new trigger class / code `PARSER_UNCERTAIN`. The evaluation that
already runs after `parse_findings` should fire this trigger when:
- `review.findings` is empty list
- `review.clean` is False

If `circuit_breaker.evaluate(review, ...)` does not currently see the
review object, the cleanest place to detect this is at the top of Phase C
in `loop.py` between `codex.run_review` and the existing
`if review.clean:` check.

**File:** `tools/autopilot/loop.py` — modify Phase C section
(around line 155 after `print(f"  findings: ..."`):

```python
# Defensive: parser returned uncertain state — halt with explicit reason
# rather than entering fix-loop with empty findings (which would 0-commit
# and trip FIX_FAILED with misleading wording).
if not review.clean and not review.findings:
    return _halt(
        cfg,
        feature_state,
        "PARSER_UNCERTAIN",
        f"Codex output round {feature_state.current_round} was not "
        f"recognized as clean and no findings were extracted. Inspect "
        f"{artifact} and either expand CLEAN_PHRASES / SEVERITY_RE in "
        f"codex.py or fix Codex output manually.",
    )
```

After Step 4 fix, this branch should rarely fire — but it's the
correct safety net.

## Step 6 — Fix `_halt` to always write halt-report.md

**File:** `tools/autopilot/loop.py`

Modify the `_halt` helper (lines 267-285) to write halt-report.md
unconditionally. The current breaker-path manually calls
`circuit_breaker.write_halt_report` before `_halt` — that's wasteful
duplication AND it's the reason non-breaker halts have no forensic file.

**Refactor approach:**

1. Add a parameter `extra_context: dict | None = None` to `_halt` for
   passing review-specific data (findings, etc.) when available.
2. Inside `_halt`, build a generic forensic report (state snapshot +
   halt_reason + recent commits + diffstat) and write to
   `.autopilot/state/<feature>/halt-report.md`.
3. Set `feature_state.halt_artifact_path` to the report path.
4. Update Phase C breaker path (line 167-176) to use the new `_halt`
   signature, passing the review as `extra_context`. Remove the manual
   `circuit_breaker.write_halt_report` call.

**Report contents (minimum):**

```markdown
# HALT — {feature_id}

- Trigger: {halt_reason}
- Phase at halt: {last_active_phase}
- Branch: {branch}
- Initial HEAD: {initial_head_sha}
- Halt time: {last_updated_at}

## State snapshot

\```json
{full state.json content}
\```

## Recent commits on branch

\```
{git log --oneline base..branch output}
\```

## Diffstat vs base

\```
{git diff --stat base..branch output}
\```

## Review context (if Phase C halt)

(Findings + raw output paths if applicable)

## Next steps

1. Inspect output above + state.json
2. Fix root cause (code, spec, or orchestrator)
3. To resume: see `docs/operations/orchestrator-usage.md`
```

## Step 7 — Add `last_active_phase` to state for resume-from-HALTED

**File:** `tools/autopilot/state.py`

Add field `last_active_phase: str | None = None` to `FeatureState`.

In `state.transition(s, new_phase)`:
- If `new_phase == "HALTED"`: set `s.last_active_phase = s.phase` BEFORE
  changing `s.phase`.
- Otherwise: leave `last_active_phase` alone.

**File:** `tools/autopilot/loop.py`

In `run()`, after `existing = state.load(...)`, add resume-from-HALTED
support:

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
        # If re-entering Phase C, reset round so the (now-fixed) parser
        # gets a clean run rather than skipping based on stale round count.
        if feature_state.phase in ("VERIFIED", "REVIEWING"):
            feature_state.current_round = 0
            feature_state.consecutive_clean_rounds = 0
        state.save(cfg, feature_state)
    else:
        print(f"Resuming {feature_id} from phase {feature_state.phase}")
```

Add unit test in `tests/unit/test_autopilot_state.py`:

```python
def test_transition_to_halted_records_last_active_phase() -> None:
    s = FeatureState(feature_id="F99", branch="feat/F99-foo", ...)
    s.phase = "REVIEWING"
    transition(s, "HALTED")
    assert s.phase == "HALTED"
    assert s.last_active_phase == "REVIEWING"


def test_transition_non_halted_leaves_last_active_phase_alone() -> None:
    s = FeatureState(...)
    s.phase = "INIT"
    s.last_active_phase = None
    transition(s, "CODEGEN")
    assert s.last_active_phase is None
```

Add loop-level resume test in `tests/unit/test_autopilot_resume.py`
(new file or extend existing) — mock codex/claude/verify, build a
HALTED state with `last_active_phase="VERIFIED"`, call
`loop.run(..., resume=True)`, assert it re-enters Phase C.

## Step 8 — Update `orchestrator-usage.md`

**File:** `docs/operations/orchestrator-usage.md`

Add a section on resume-from-HALTED behavior. Example:

```markdown
### Resume from HALTED

After fixing the cause of a halt, run:

\```bash
python -m tools.autopilot resume <feature_id>
\```

The loop reads `state.json`, sees `phase=HALTED`, and re-enters at
`last_active_phase` (Phase C halt → re-enters at VERIFIED, etc.). If the
halt was in Phase C, `current_round` and `consecutive_clean_rounds` are
reset to 0 so the (now-fixed) parser gets a clean Codex review cycle.

If `state.json` shows `phase=HALTED` but `last_active_phase` is null
(state file predates v0.2.1), edit state.json manually:

\```json
{
  "phase": "VERIFIED",        // or appropriate re-entry phase
  "current_round": 0,
  "consecutive_clean_rounds": 0,
  "halt_reason": null,
  "halt_artifact_path": null
}
\```

Then run `resume` as above.
```

## Step 9 — Update CHANGELOG

Open `CHANGELOG.md`. Append a sub-section to `## [Unreleased]`:

```markdown
### Fixed — Autopilot v0.2.1 (Codex parser + halt forensics)

- **Codex parser early-return:** `codex.parse_findings` no longer requires
  a `^codex$` marker line. Codex CLI v0.130 in subprocess context sometimes
  emits just the verdict (~900 bytes); parser now falls back to whole-output
  parsing. Caught by F07 pilot 2026-05-12 — round 1 verdict had a real P2
  finding that the old parser missed entirely.
- **Halt-report writer:** `_halt` helper now always writes
  `.autopilot/state/<feature>/halt-report.md` with state snapshot + commits
  + diffstat + review context. Previously only the Codex circuit-breaker
  path wrote the file; other halts (CODEGEN_FAILED, FIX_FAILED,
  VERIFY_REGRESSION, MERGE_GATE_FAIL) left no forensic trail.
- **Resume from HALTED:** `state.transition` records `last_active_phase`
  before going HALTED. `loop.run(..., resume=True)` re-enters at that phase
  with round counters reset (Phase C). Previously the loop returned a
  silent no-op when phase=HALTED.

### Added — Autopilot test fixtures

- `tests/fixtures/codex/` directory with 4 real Codex CLI outputs from F07
  and W0.8 pilot runs (P2 finding case + multiple clean verdict styles).
  All future parser tests build on this gold-standard set.

### Added — Autopilot circuit breaker

- `PARSER_UNCERTAIN` trigger: fires when `parse_findings` returns
  `findings=[], clean=False`. Defensive net — primary fix above should make
  this rarely fire, but if Codex output format changes again, we halt with
  a meaningful reason instead of empty-fix → FIX_FAILED.
```

## Step 10 — Local verify + atomic commits

```bash
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
```

ALL must pass. The 5 new tests in test_autopilot_codex.py + new state +
resume tests MUST appear in output and PASS.

Baseline was 219 tests; after fix should be at least 224-227.

If any fails → up to 2 retries to fix root cause. After 2 retries → HALT
with `VERIFY_REGRESSION`.

**Commit (atomic):**

```bash
git add tests/fixtures/codex/
git commit -m "test(autopilot): real Codex output fixtures (F07 P2 + W0.8 clean)"

git add tests/unit/test_autopilot_codex.py
git commit -m "test(autopilot): parser tests against real Codex outputs (v0.2.1 fixes)"

git add tools/autopilot/codex.py
git commit -m "fix(autopilot): parse_findings handles missing 'codex' marker; expand CLEAN_PHRASES"

git add tools/autopilot/state.py
git add tests/unit/test_autopilot_state.py  # if extended
git commit -m "feat(autopilot): state.last_active_phase for resume-from-HALTED"

git add tools/autopilot/circuit_breaker.py tools/autopilot/loop.py
git add tests/unit/  # any new loop/resume tests
git commit -m "feat(autopilot): PARSER_UNCERTAIN breaker + unconditional halt-report writer + resume-from-HALTED"

git add docs/operations/orchestrator-usage.md
git commit -m "docs(autopilot): resume-from-HALTED workflow"

git add CHANGELOG.md
git commit -m "docs: changelog — autopilot v0.2.1 parser + halt forensics fixes"
```

## Step 11 — Inline Codex review with ≤3 fix rounds

**Why inline:** orchestrator changes are P1 per plan §6.5; Wave 0 lesson
#3 mandates cross-model review for foundation. This PR fixes the very
parser that the orchestrator uses — meta-review is essential.

**Round N (1, 2, 3):**

```bash
codex review --base main 2>&1 | tee .autopilot/state/v0.2.1-fix/codex/round-NN.txt
```

**Parse Codex output:**

- Output contains `did not identify`, `did not find any`, `no actionable`,
  `appear internally consistent` → clean (apply same logic as you just
  wrote in CLEAN_PHRASES).
- Otherwise extract findings:
  - Severity P0/P1 → MUST fix this round.
  - Severity P2 → fix opportunistically; defer to follow-up if scope creep.
  - Keywords `schema design`, `breaking change`, `architectural` →
    `ARCH_FINDING` breaker → HALT.
  - Keywords `auth`, `token leak`, `timing`, `secret`, `injection` →
    `SECURITY_FINDING` breaker → HALT.
  - Same finding hash in N and N+1 → `RECURRING_FINDING` breaker → HALT.

**Fix round:**
- Apply minimum-viable fix.
- Re-run local verify (Step 10). MUST be green before next Codex round.
- Commit atomically: `fix(autopilot): address codex round NN — <summary>`.

**Clean signal handling:**
- Need 2 consecutive clean rounds before squash.
- Round 1 clean → run round 2 anyway. If round 2 also clean → squash.
- If round 3 not 2× clean → `MAX_ROUNDS` breaker → HALT.

## Step 12 — Squash-merge to main + push

Only reachable if Step 11 produced 2 consecutive clean Codex rounds.

```bash
git checkout main
git pull --ff-only origin main

# Dry-run merge
git merge --no-commit --no-ff chore/autopilot-v0.2.1-codex-parser-fix
git merge --abort

git merge --squash chore/autopilot-v0.2.1-codex-parser-fix
git commit -m "fix(autopilot): v0.2.1 — Codex parser + halt forensics + resume-from-HALTED

Resolves 3 bugs surfaced by F07 pilot 2026-05-12:

1. parse_findings early-returned ([], False) when Codex CLI output lacked
   a 'codex' marker line. CLI v0.130 in subprocess context sometimes emits
   only the verdict (~900 bytes, no preamble). Parser now treats missing
   marker as 'use whole output'. Caught the real P2 finding F07 round 1
   had reported but parser ignored.

2. _halt helper now writes halt-report.md unconditionally. Previously only
   the Codex circuit-breaker path wrote a forensic file; other halts left
   halt_artifact_path null.

3. state.transition to HALTED records last_active_phase. loop.run(resume=True)
   re-enters at that phase with Phase-C round counters reset. Previously
   resume on HALTED state returned a silent no-op.

Plus: 4 real Codex outputs added as tracked fixtures
(tests/fixtures/codex/), PARSER_UNCERTAIN breaker for defensive halt on
truly malformed output, expanded CLEAN_PHRASES with two new phrases
observed in W0.8 round 2 output.

Validated by inline Codex review (2 consecutive clean rounds). 224+ tests
pass, all hooks green.

Next: founder resumes F07 pilot — \`python -m tools.autopilot resume F07\`
will pick up at Phase C with round 0 and the now-fixed parser. See
docs/operations/orchestrator-usage.md § Resume from HALTED."

git branch -D chore/autopilot-v0.2.1-codex-parser-fix
git push origin main
```

If push rejected → HALT. Do NOT force-push.

---

## Circuit breakers (HALT and write report)

PAUSE immediately and write
`.autopilot/state/v0.2.1-fix/halt-report.md` if ANY trigger fires:

1. **Pre-flight regression** — existing 219 tests no longer pass on main.
2. **Push rejected** (remote moved).
3. **Initial TDD step shows tests pass on current main** — investigate
   before continuing (Step 3 expects 2-of-5 to fail).
4. **VERIFY_REGRESSION** — local verify fails twice consecutively after
   fix attempts.
5. **ARCH_FINDING** — Codex flags `schema design`, `breaking change`,
   `architectural`, `re-think`.
6. **SECURITY_FINDING** — Codex flags auth/token/timing/secret/injection.
7. **RECURRING_FINDING** — same Codex finding hash in round N AND N+1.
8. **TYPE_IGNORE_PROPOSED** — Codex or you reach for `# type: ignore`.
9. **MAX_ROUNDS** — 3 Codex rounds without 2 consecutive clean.
10. **Tool error twice in a row** on `git`, `codex`, `pytest`.
11. **Context budget** — if context >70%, pause + report. Founder
    will resume in fresh session.

### Halt report template

```
HALT — Autopilot v0.2.1 fix circuit broken.

Step:    <e.g. Step 11 round 2>
Trigger: <one of 11 conditions>
Branch:  chore/autopilot-v0.2.1-codex-parser-fix
HEAD:    <SHA>

Detail:
<error output OR Codex finding excerpt OR rejected push reason>

State:
- Commits on branch since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/v0.2.1-fix/codex/round-*.txt
- Last verify result: <pass | fail with offending check>

Requesting founder input on:
<specific question>
```

---

## Final report (when Step 12 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.1 — Codex parser + halt forensics — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA>  fix(autopilot): v0.2.1 — Codex parser + halt forensics + resume-from-HALTED
Branch chore/autopilot-v0.2.1-codex-parser-fix: DELETED
Push origin/main: OK

Files added:
  - tests/fixtures/codex/f07-round-01-p2-no-marker.txt
  - tests/fixtures/codex/f07-round-02-clean-no-marker.txt
  - tests/fixtures/codex/w08-round-01-clean-with-marker.txt
  - tests/fixtures/codex/w08-round-02-clean-with-marker.txt
  - tests/unit/test_autopilot_codex.py (or extended)

Files modified:
  - tools/autopilot/codex.py        (parse_findings + CLEAN_PHRASES)
  - tools/autopilot/circuit_breaker.py (PARSER_UNCERTAIN trigger)
  - tools/autopilot/loop.py         (PARSER_UNCERTAIN gate + _halt unconditional report + resume-from-HALTED)
  - tools/autopilot/state.py        (last_active_phase field)
  - tests/unit/test_autopilot_state.py (transition tests)
  - docs/operations/orchestrator-usage.md (resume-from-HALTED doc)
  - CHANGELOG.md

Codex review:
  Round 01: <findings count | clean>
  Round 02: <findings count | clean>
  Round 03: <run? Y/N — only if first two not both clean>
  Final state: 2 consecutive clean rounds confirmed
  Artifacts: .autopilot/state/v0.2.1-fix/codex/round-*.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean
  lint-imports: clean
  pytest:       <count> passed (baseline 219, expected ≥224 with v0.2.1 tests)

Decisions made during execution requiring founder review:
  <list any non-obvious calls>

═══════════════════════════════════════════════════════

Next steps (NOT in this prompt's scope — founder runs):

1. Resume F07 pilot with fixed parser:

   # Inspect F07 state — should still show phase=HALTED
   cat .autopilot/state/F07/state.json | python -m json.tool

   # state.last_active_phase will be null (state predates v0.2.1).
   # Edit state.json manually:
   #   "phase": "VERIFIED"
   #   "current_round": 0
   #   "consecutive_clean_rounds": 0
   #   "halt_reason": null
   #   "halt_artifact_path": null
   # (Branch feat/F07-settings is intact — codegen commits preserved.)

   python -m tools.autopilot resume F07

   Expected behavior:
   - Phase C round 1: Codex finds P2 (emit_analytics try/except missing).
     Parser now extracts it. Claude fix adds try/except. Verify green.
   - Phase C round 2: Codex reviews fix → clean.
   - Loop needs 2x clean — round 2 clean = 1x, run round 3.
   - Phase C round 3: clean (no new changes) → 2x clean → READY.
   - ready-report.md written. Exit 0.

2. Read .autopilot/state/F07/ready-report.md → review squash commands.

3. Manual squash F07 to main (NOT --auto-merge — F07 is P1):

   git checkout main
   git pull --ff-only origin main
   git merge --squash feat/F07-settings
   git commit -m "feat(F07): settings /settings — ..."  # per ready-report
   git branch -D feat/F07-settings
   git push origin main

End of autopilot v0.2.1 fix.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles F07 resume + squash.

---

## Global rules (apply throughout)

1. READ FIRST. Don't write code blind.
2. NEVER skip 10-step workflow.
3. NEVER force-push.
4. NEVER touch F07 branch or state in this run.
5. NEVER add `# type: ignore`.
6. NEVER auto-skip Codex rounds — orchestrator P1 mandates 2× clean.
7. Atomic commits — one per logical change.
8. Use TDD: write failing tests in Step 3, then fix to green. This is the
   first time we have real CLI fixtures — TDD locks them in.
9. If unsure on architecture, trigger circuit breaker. Do not guess.
10. Verify before claiming done — re-run pytest after "tests pass" message.
11. Tool error twice → circuit breaker, don't retry blindly.
12. Context budget — if >70% used, pause + halt. Branch state must be
    intact for resume.
13. Auto-push on success. No further confirmation needed.

Begin with Pre-flight, then Step 1. Execute through Step 12 final report.
