# Level 3 Autopilot Template — Per-Feature Auto Code-Review-Fix Loop

> **Version:** v1.0.0 (draft)
> **Date:** 2026-05-11
> **Status:** Draft — pending `codex review --help` verification
> **Mode:** Level 3 (auto code + auto Codex review + auto-fix simple findings + circuit breakers; manual merge gate retained)
> **Prerequisites:** Codex CLI at `/Users/maingocanh/Library/Application Support/crawbot/nodejs/bin/codex` (verified 2026-05-11)
> **Use for:** Wave 1+ features (F-onboarding, F-admin-tools, F-i18n, F-settings). NOT recommended for foundation/security-critical PRs (use Mode 3 batch + manual review instead).

---

## Difference vs Wave 0 Mode 3 (batch review)

| Step | Mode 3 (Wave 0) | Level 3 (Wave 1+) |
|---|---|---|
| Code generation | Auto | Auto |
| Local verify (ruff/black/mypy/lint-imports/pytest) | Auto | Auto |
| Codex review invocation | Manual (founder paste slash command) | **Auto (`codex review` CLI)** |
| Parse findings | Manual (founder reads + assesses) | **Auto (regex/JSON parse)** |
| Auto-fix simple findings | Manual (founder + AI assist) | **Auto (agent applies targeted edits)** |
| Auto-fix architectural findings | Manual | **CIRCUIT BREAKER — pause for founder** |
| Re-review loop | Manual (mini-review per fix round) | **Auto (loop until clean OR breaker)** |
| Merge | Manual (squash + commit) | Manual (manual gate retained — safety) |

**Net effect:** founder intervention drops from ~5 interrupts per feature (Mode 3) to ~1 (start + final merge), unless circuit breaker trips.

---

## CLI invocation patterns

```bash
# Non-interactive review against base branch (CORE PATTERN)
codex review --base main

# Mini-review on specific commit (replaces "--base HEAD~1" pattern)
codex review --commit <SHA>

# Review uncommitted (staged + unstaged + untracked) — useful pre-commit
codex review --uncommitted

# Custom review instructions via PROMPT arg
codex review --base main "Focus on idempotency and tenant isolation"

# Read review instructions from stdin
echo "Custom instructions" | codex review --base main -

# Apply Codex's suggested diff (if agent produced one)
codex apply

# Non-interactive single-shot prompt execution
codex exec "<prompt>"
```

**Output parsing strategy (text-only — no JSON flag in CLI v current):**
- Regex on severity tags at line start: `[P0]`, `[P1]`, `[P2]`, `[P3]`, `HIGH`, `MEDIUM`, `LOW`.
- Each finding usually has: severity tag, summary line, file path (often `<file>:<line>` form), recommendation text below.
- Exit code: 0 if clean (no findings), non-zero if findings present. (Verify with first run.)
- Findings separated by blank line or `- ` bullet.

**Format observed across 8 Wave 0 Codex reviews:**

Findings case (`Verdict: needs-attention`):
```
# Codex Review

Target: branch diff against <base>
Verdict: needs-attention

<summary paragraph>

Findings:
- [<severity>] <summary line> — /abs/path/file.py:LL-LL
  <detail paragraph>
  Recommendation: <suggestion>

- [<severity>] <next>...

Next steps:
- <action>
```

Clean case:
```
# Codex Review

Target: branch diff against <base>

I did not identify any discrete, actionable bugs/regressions/defects ...
```

**Severity tag styles observed (parser must handle BOTH):**
- `[high]`, `[medium]`, `[low]` (W0.1 Round 1)
- `[P0]`, `[P1]`, `[P2]`, `[P3]` (W0.6 rounds + W0.1 Round 2)

**Parser pseudocode (verified against real CLI output 2026-05-11):**

Output anatomy:
1. Preamble (~10 lines): version header, metadata, separator
2. `user` section: prompt echo
3. `exec` blocks: bash commands Codex ran (1-many) — NOISE, skip
4. Diff dump (often 100-300 lines) — NOISE, skip
5. `codex` marker line → review verdict paragraph starts here
6. `Review comment:` or `Review comments:` header → findings list
7. Bullets `- [P1] <summary> — file:line-range` + indented detail
8. **WARNING:** review block appears TWICE in output (Codex CLI quirk). Dedupe by summary+file+line.

```python
import re
import subprocess
import hashlib

result = subprocess.run(
    ["codex", "review", "--base", "main"],
    capture_output=True, text=True, timeout=600,
)
output = result.stdout  # exit code always 0; parse text

# 1. Find review section — starts after last "codex" marker line
codex_markers = [i for i, l in enumerate(output.splitlines()) if l.strip() == "codex"]
if not codex_markers:
    # No review section found — abnormal, treat as error
    raise RuntimeError("Codex output missing 'codex' marker section")

# Take everything after the FIRST codex marker (works even with duplicate blocks)
lines = output.splitlines()[codex_markers[0]:]
review_text = "\n".join(lines)

# 2. Clean detection — phrase match in review section
CLEAN_PHRASES = [
    "did not identify any discrete",
    "did not identify any actionable",
    "did not find any",
    "no actionable regressions",
    "no actionable defects",
]
if any(p in review_text.lower() for p in (s.lower() for s in CLEAN_PHRASES)):
    findings = []
else:
    # 3. Parse findings — severity bullets after "Review comment(s)" header
    SEVERITY_RE = re.compile(
        r"^\s*-\s*\[(?P<sev>P[0-3]|CRITICAL|HIGH|MEDIUM|LOW|"
        r"high|medium|low|p[0-3])\]\s*(?P<summary>.+)$",
    )
    FILE_RE = re.compile(r"(/[\w./-]+\.py):(\d+)(?:[-:](\d+))?")

    findings = []
    current = None
    for line in lines:
        m = SEVERITY_RE.match(line)
        if m:
            if current:
                findings.append(current)
            sev_raw = m.group("sev").upper()
            # Normalize P1 ↔ HIGH style
            sev_map = {"HIGH": "P1", "MEDIUM": "P2", "LOW": "P3", "CRITICAL": "P0"}
            current = {
                "severity": sev_map.get(sev_raw, sev_raw),
                "summary": m.group("summary").strip(),
                "detail": [],
                "file": None,
                "line_start": None,
                "line_end": None,
            }
        elif current:
            fm = FILE_RE.search(line)
            if fm and not current["file"]:
                current["file"] = fm.group(1)
                current["line_start"] = int(fm.group(2))
                current["line_end"] = int(fm.group(3)) if fm.group(3) else int(fm.group(2))
            current["detail"].append(line)
    if current:
        findings.append(current)

    # 4. Dedupe — Codex prints review twice in some runs (verified 2026-05-11)
    seen = set()
    unique = []
    for f in findings:
        key = (f["severity"], f["file"], f["line_start"], f["summary"][:80])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    findings = unique

# 5. Severity ranking for routing decisions
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
for f in findings:
    f["rank"] = SEVERITY_RANK.get(f["severity"], 99)
```

**Performance note:** 359 lines output for 1 commit review (verified). ~95% noise (preamble + diff dump), ~5% actual review. Codex CLI doesn't have a "review-only" output mode — agent must parse all of it. Acceptable since regex on text is fast.

**Exit code semantics (verified 2026-05-11):** `codex review` returns **0 ALWAYS**, regardless of findings. DO NOT rely on exit code to detect issues. Must parse stdout.

**Empty diff edge case:** if current branch == base (e.g. ran on main vs `--base main`), Codex returns quickly with no findings. Agent should verify `git rev-parse HEAD != git rev-parse main` before running review to avoid pointless invocations.

---

## PROMPT (paste-ready)

Paste the block between `===PROMPT START===` and `===PROMPT END===` into a fresh Claude Code session in `/Users/maingocanh/Projects/MyMoneyWent`.

```
===PROMPT START===

# Task: Level 3 autopilot — implement <FEATURE NAME> with auto code-review-fix loop

You are working in /Users/maingocanh/Projects/MyMoneyWent. No prior
conversation context. Codex CLI is available at
`/Users/maingocanh/Library/Application Support/crawbot/nodejs/bin/codex`
(in PATH after activating venv).

**Mode:** Level 3 — fully autonomous code → Codex review → auto-fix
loop. Pause ONLY on circuit breakers. Founder retains manual squash-
merge gate at end.

**Feature target:** <FEATURE NAME, e.g. "F-onboarding">
**Spec FE:** docs/features/feature-<name>.md
**Spec BE:** docs/features/BE/feature-<name>-tech.md

## Pre-flight (run first, HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                          # must be clean
git branch --show-current           # must be: main
git log --oneline -3                # latest must be Wave 0 W0.6 squash

source .venv/bin/activate
which codex                         # must resolve
codex --help | head -5              # verify CLI accessible

ruff check core/ markets/ tests/
black --check core/ markets/ tests/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
```

All checks must pass before starting. If anything fails, HALT and report.

## Locked decisions (DO NOT re-ask founder)

Read these memory notes via fresh search if you have memory access:
- project_wave0_complete.md — Wave 0 final state, available APIs
- project_wave0_gap_decisions.md — 5 locked decisions
- feedback_wave0_lessons.md — 7 lessons for Wave 1+

Anti-patterns (per development-workflow.md §6):
- No mock DB (use testcontainers)
- Atomic commits per §2.4
- No `if market == "vn"` in core/
- core/ ↛ markets/ (import-linter enforces)
- Tenant isolation test mandatory when DB involved
- CHANGELOG entry required pre-merge

## Per-feature execution flow (Level 3)

### Phase A: Prep (5-category test plan)

1. Read feature spec FE + BE thoroughly.
2. Draft test plan with 5 categories before any code:
   - Happy path
   - Retry/idempotency (if state-modifying)
   - Missing optional fields
   - Pathological inputs (overflow, malformed, injection)
   - Concurrent access (if multi-user state)
3. Plan 10-line: files, migration, tests, integration points, risks.
4. Create branch `feat/<feature-name>`.

### Phase B: Implementation

5. Code + write tests for all 5 categories.
6. Run local verify:
   ```bash
   ruff check core/ markets/ tests/
   black --check core/ markets/ tests/
   mypy core/ markets/ tests/
   lint-imports
   pytest tests/ -v
   ```
7. ALL must pass. If any fail, iterate locally up to 2 rounds. If still
   failing after 2, trigger circuit breaker.
8. Commit atomically (multiple commits per PR per workflow §2.4).

### Phase C: Auto-review-fix loop (Level 3 core)

```pseudo
round = 0
max_rounds = 3
fixed_finding_hashes = set()

while round < max_rounds:
    round += 1
    
    # Invoke Codex non-interactively
    output = bash("codex review --base main")
    findings = parse_findings(output)
    
    if not findings:
        log("Round %d: clean" % round)
        break
    
    # Categorise findings
    architectural = [f for f in findings if matches_arch_keywords(f)]
    auto_fixable = [f for f in findings if not architectural and severity in {P2, P3, LOW, MEDIUM}]
    blocking = [f for f in findings if severity in {P0, P1, HIGH, CRITICAL} and not architectural]
    
    # Circuit breakers
    if architectural:
        TRIGGER_CIRCUIT_BREAKER("architectural finding requires founder review")
    if any(hash(f) in fixed_finding_hashes for f in findings):
        TRIGGER_CIRCUIT_BREAKER("same finding recurring — fix attempted twice")
    
    # Apply fixes
    for f in blocking + auto_fixable:
        if can_auto_fix_safely(f):
            apply_fix(f)
            fixed_finding_hashes.add(hash(f))
        else:
            TRIGGER_CIRCUIT_BREAKER("finding not safely auto-fixable: %s" % f.summary)
    
    # Re-verify after fixes
    local_verify_all()  # ruff + black + mypy + lint-imports + pytest
    
    # Commit fixes atomically
    git_commit("fix(<feature>): %s" % summarize_fixes())

if round == max_rounds:
    TRIGGER_CIRCUIT_BREAKER("max %d Codex rounds reached without clean state" % max_rounds)
```

### Phase D: Final state report

When Phase C exits cleanly, output:

```
═══════════════════════════════════════════════════════
FEATURE COMPLETE: <FEATURE NAME>
═══════════════════════════════════════════════════════

Branch: feat/<feature-name>
Commits: <count> (incl. <N> fix commits from Codex rounds)
Files changed: <count> (+<X>/-<Y>)

Codex review rounds: <N>
- Round 1: <N findings> → <fixed all|N P0/P1 fixed>
- Round 2: <N findings> → <fixed all>
- Round 3: clean

Local verification: ALL PASS
- ruff: clean
- black: clean
- mypy: clean
- lint-imports: 4 contracts kept
- pytest: <count> passed, <skipped> skipped

Test coverage (5 categories):
- Happy path: <count> tests
- Retry/idempotency: <count> tests (or N/A if no state)
- Missing optional fields: <count> tests
- Pathological inputs: <count> tests
- Concurrent access: <count> tests (or N/A)

Decisions during execution requiring founder note:
- <list any non-obvious choices>

To merge:
  git checkout main
  git merge --squash feat/<feature-name>
  git commit -m "F<XX>: <feature title>"
  git branch -D feat/<feature-name>

End of Level 3 autopilot.
═══════════════════════════════════════════════════════
```

Then STOP. Founder reviews + merges manually.

## Circuit breakers (HALT and report)

PAUSE immediately and write report to `/tmp/level3-circuit-break.md` if:

1. **Architectural finding** (Codex output contains any keyword):
   schema | design | scope | architecture | refactor | redesign |
   contract | interface change | breaking change

2. **Security/auth finding** (keywords):
   security | auth | credential | token | password | secret | hmac |
   constant-time | timing attack | injection | csrf | xss

3. **State/concurrency finding** (keywords):
   race | concurrent | deadlock | lock | atomic | transaction
   (allow if just retry/idempotency — that's auto-fixable)

4. **Same finding recurring** — fix attempted but Codex re-flags same
   issue. Don't loop on bad fix.

5. **Max rounds reached** — 3 Codex rounds without clean state.

6. **Local verify regression** — after fix commit, ruff/black/mypy/
   lint-imports/pytest starts failing. Don't push known-broken code.

7. **Context budget concern** — if context >70% used, dump state.

8. **Tool error twice in row** — codex/bash/pytest errors consistently.

9. **detect-secrets new finding** — possible secret leak. Founder audit.

10. **mypy `# type: ignore` proposed** — type bypasses need founder OK.

## Circuit breaker report template

```
HALT — Level 3 autopilot circuit broken.

Feature: <FEATURE NAME>
Branch: feat/<feature-name>
Round: <N>/3
Trigger: <one of 10 conditions>

Codex finding that triggered:
<paste finding text verbatim with severity + file:line>

Why this needs founder:
<one paragraph: the architectural / security / scope reason>

State preserved:
- Branch: <branch name> with <count> commits
- Last local verify: <pass|fail with details>
- Codex output: /tmp/codex-output-round-<N>.txt

Requesting founder decision:
<specific question, e.g. "Accept Codex suggestion to change schema?">

Resume instructions:
1. Founder makes decision
2. Edit files as needed (or instruct agent)
3. Re-run: codex review --base main
4. If clean: continue Phase D; else continue Phase C loop
```

## Founder interaction points

| When | What |
|---|---|
| Start | Paste this prompt with FEATURE NAME |
| Pre-flight fails | Inspect error, fix env, restart |
| Circuit breaker tripped | Read /tmp/level3-circuit-break.md, decide, resume agent OR continue manually |
| Final report received | Run Codex one final time as audit (optional), then squash-merge |

Estimated founder time per feature: 5-10 min start + 10-15 min merge = 15-25 min total (vs ~1h in Mode 3).

## Anti-patterns (NEVER do at Level 3)

- Skip Phase A test plan
- Auto-fix architectural findings without pause
- Loop on same finding more than once
- Merge without local verify clean
- Commit Codex's diff suggestion without reading it
- Override circuit breaker without explicit founder instruction
- Use `codex apply` blindly without inspecting the diff

## Failure recovery

If Level 3 autopilot leaves branch in broken state:

```bash
# Inspect what was done
git log --oneline main..HEAD
git diff main..HEAD --stat

# Option A: reset to last known good commit
git log --grep="fix(" --oneline   # find last fix commit
git reset --hard <good-sha>

# Option B: abandon branch, restart fresh
git checkout main
git branch -D feat/<feature-name>

# Option C: continue manually from current state
source .venv/bin/activate
codex review --base main
# Apply fixes by hand, commit, merge
```

===PROMPT END===
```

---

## Worked example: F-i18n (Wave 1 feature, low risk, ideal for Level 3)

**Why F-i18n is ideal Level 3 candidate:**
- Low architectural surface (string tables + lookup function)
- Limited security surface (no auth, no tokens, no state)
- Test categories naturally fit:
  - Happy path: t('key', locale='vi') returns expected
  - Missing optional fields: missing locale → fallback
  - Pathological inputs: empty key, very long key, special chars
  - (Retry/idempotency N/A — pure function)
  - (Concurrent N/A — read-only)

**Expected Codex rounds:** 0-1 (clean first try OR 1 minor P3 like "consider caching").

**Expected founder time:** 5 min start + 10 min merge = 15 min total.

## Risks of Level 3

1. **Codex auto-fix introduces subtle bugs** — agent's fix passes Codex
   round 2 but breaks runtime behaviour. Mitigation: tests for all 5
   categories + local verify after each fix.

2. **Codex doesn't catch what tests don't cover** — auto-fix only helps
   for what Codex flags. Garbage in, garbage out. Mitigation: Phase A
   strong test plan.

3. **Founder loses architecture visibility** — if agent silently fixes
   3 rounds without circuit breaker, founder doesn't see the iteration.
   Mitigation: final report enumerates all rounds + decisions.

4. **CLI behaviour drift** — `codex review` CLI changes between
   versions. Mitigation: pin Codex CLI version in dev env; circuit
   break on unexpected output format.

## When NOT to use Level 3

| Don't use for | Why |
|---|---|
| Wave 0-style foundation work | Architectural decisions need founder |
| Security-critical (F-payment, auth) | Codex P1 surface too risky to auto-fix |
| Schema-changing (migrations, FK) | Schema choices have downstream impact |
| New cross-market integration | Adapter pattern decisions need founder |
| First time using new tool/library | Unknown unknowns benefit from human eyes |

## Cross-references

- [development-workflow.md](../operations/development-workflow.md) — workflow rules
- [wave0-retrospective.md](../operations/wave0-retrospective.md) — 7 lessons
- [execution-prompt-wave0-autopilot.md](../operations/execution-prompt-wave0-autopilot.md) — Mode 3 (Wave 0 foundation)
