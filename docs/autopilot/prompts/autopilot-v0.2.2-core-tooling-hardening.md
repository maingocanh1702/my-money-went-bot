# Task: Autopilot v0.2.2 — Core tooling hardening (9 cumulative findings from F07 + v0.2.1 pilots)

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT — single-phase on new branch `chore/autopilot-v0.2.2`.
Apply 6 code fixes + 1 doc + 1 investigation report. Inline Codex review
with **extended budget (≤5 rounds, 2× consec clean)** because we're eating
our own dogfood: v0.2.2 raises max_rounds default from 3 to 5, so this
PR's own review uses the new budget. Squash + push to main.

**Context (NOT for execution, just background):**

4 sessions on F07 pilot + 3 sessions on v0.2.1 surfaced 9 cumulative
orchestrator tooling issues that block sustainable use of autopilot for
F02-F08+ pipeline:

1. **MAX_ROUNDS impossible math** — `max_review_rounds=3 +
   required_clean_rounds_before_merge=2 (consecutive)` cannot ship when
   adjacent micro-findings keep surfacing each round. v0.2.1 needed 8
   manual rounds, F07 ran 4 sessions, neither converged via orchestrator.
2. **SECURITY_FINDING keyword over-fire** — `"token"` mere mention auto-
   HALTs even when finding is benign Markdown rendering (F07 R1 from
   prior session 3).
3. **Resume doesn't checkout branch** — `loop.run(resume=True)` enters
   Phase C without ensuring current branch matches `feature_state.branch`.
   Led to empty-diff codex review on F07 (caller was on main).
4. **tracker.update_status writes on feature branch** — orchestrator's
   `tracker.update_status(cfg, feature_id, "REVIEWING")` mutates
   `docs/implementation-tracker.md` on whatever branch is currently
   checked out, polluting F07 branch with noise commits.
5. **State schema strict-load** — `state.load()` rejects state.json with
   unknown fields (e.g., when orchestrator code is older than state file
   schema). Halted F07 resume after v0.2.1 added `last_active_phase`.
6. **Codex artifact overwrite** — `codex.save_review_artifact()` writes
   `.autopilot/state/<feature>/codex/round-NN.txt`, clobbering prior-run
   artifacts on resume. Lost forensics.
7. **Codex stale blob** — Codex CLI sometimes reviews a stale git blob
   SHA instead of HEAD (seen on F07 i18n fix session 4). Verification
   gate not reliable. Investigation + workaround logging only here;
   true fix may be v0.2.3.
8. **Concurrent agent ref clobber** — running 2 Claude Code sessions on
   same repo trampled `feat/F07-settings` ref via shared `.git/`. Need
   isolation policy doc.
9. (i18n template audit was closed in F07 session 4 — informational
   only, no fix needed.)

This prompt addresses #1-6 in code + #7 with logging workaround + #8 in
docs. #9 noted as closed.

## Required reading (READ FIRST, in order)

1. `docs/autopilot/autopilot-implementation-plan.md` v0.2.0 §6.5 — risk
   tier policy. This change touches orchestrator core → P1.
2. `tools/autopilot/loop.py` — full. Focus on `run()` resume path, Phase
   C while-loop with max_review_rounds.
3. `tools/autopilot/codex.py` — `parse_findings` + `save_review_artifact`
   + `SECURITY_KEYWORDS`.
4. `tools/autopilot/circuit_breaker.py` — `evaluate()` security check.
5. `tools/autopilot/state.py` — `FeatureState` dataclass + `load()` /
   `save()`.
6. `tools/autopilot/config.py` — config dataclass for env knobs.
7. `tools/autopilot/tracker.py` — `update_status()` callers.
8. `tools/autopilot/git_ops.py` — checkout / branch helpers.
9. Recent F07 codex artifacts (NOT for parsing, just context):
   `.autopilot/state/F07/codex/round-*.txt`,
   `.autopilot/state/F07/codex/markdown-fix-round-01.txt`,
   `.autopilot/state/F07/codex/i18n-fix-round-01.txt`,
   `.autopilot/state/F07/codex/refactor-round-*.txt`.

## Pre-flight (HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean
git branch --show-current               # MUST: main
git pull --ff-only origin main
git log --oneline -3
# Top should be 81a18fb fix(docs)... or later commits (post-restructure)

# Ensure no other claude code session active on this repo
ls .git/*.lock 2>/dev/null
# MUST be empty (no in-progress git operations from another agent)

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling green
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v                        # capture baseline count
```

Capture pytest baseline count. v0.2.1 main baseline was 233. After v0.2.2
adds new tests, expect baseline + ~10-15.

If any pre-flight fails → HALT, no proceed.

## Anti-patterns (NEVER do)

- Touch F07 branch or `feat/F07-settings` files. F07 resume is next
  session's job, after v0.2.2 lands on main.
- `git push --force`.
- Add `# type: ignore` (circuit breaker).
- Skip any of 6 code fix steps. If one blocks, HALT — don't quietly drop.
- Run other Claude Code sessions on this repo while this prompt is active.
- Auto-merge anything. Squash + push to main is OK (P1 merge after Codex
  2× clean), but no `--auto-merge` flag.

---

## Step 1 — Branch creation + capture baseline

```bash
git checkout -b chore/autopilot-v0.2.2
git rev-parse HEAD > /tmp/v022-base-sha.txt
mkdir -p .autopilot/state/v0.2.2/codex
```

## Step 2 — Fix #1: max_rounds default + confirmation_rounds_after_last_fix knob

**File:** `tools/autopilot/config.py`

Add to `Config` dataclass:

```python
@dataclass
class Config:
    # ... existing fields ...
    max_review_rounds: int = 5                       # was 3 — raised per v0.2.2 meta-bug
    required_clean_rounds_before_merge: int = 2      # legacy name, semantics unchanged
    confirmation_rounds_after_last_fix: int = 2      # NEW: minimum clean rounds AFTER the
                                                     # last fix commit before declaring READY.
                                                     # Decouples "consecutive cleans needed"
                                                     # from "max total rounds allowed".
```

**Reasoning to embed in docstring:**

> Empirical pattern from F07 + v0.2.1 pilots: each fix commit grows the
> diff, Codex's next review may surface an adjacent micro-finding in the
> new code. With max=3 + clean=2, ship is impossible when rounds 1+2 both
> find. New defaults: max=5 + post-fix-confirm=2 → up to 3 fix rounds
> with 2 confirmation rounds tail. If still doesn't converge, the issue
> is real not stochastic.

**File:** `tools/autopilot/loop.py`

Update Phase C while-loop to use the new knob. Rough shape:

```python
# --- Phase C: REVIEWING ---
if feature_state.phase in ("VERIFIED", "REVIEWING"):
    rounds_since_last_fix = 0
    while feature_state.current_round < cfg.max_review_rounds:
        feature_state.current_round += 1
        # ... existing codex.run_review + parse ...

        if review.clean:
            feature_state.consecutive_clean_rounds += 1
            rounds_since_last_fix += 1
            state.save(cfg, feature_state)
            # NEW termination condition: need post-fix-confirm clean rounds
            # AFTER the last fix (or zero fixes total if cleanly converged).
            if rounds_since_last_fix >= cfg.confirmation_rounds_after_last_fix:
                break
            continue

        feature_state.consecutive_clean_rounds = 0
        rounds_since_last_fix = 0  # reset confirmation counter

        # ... existing breaker checks + fix flow ...
    else:
        return _halt(cfg, feature_state, "MAX_ROUNDS",
                     f"hit {cfg.max_review_rounds} rounds without "
                     f"{cfg.confirmation_rounds_after_last_fix} confirmation "
                     f"rounds after last fix")
```

(Adapt to actual loop structure; preserve existing fix-loop semantics.)

**Unit test:** `tests/unit/test_autopilot_max_rounds.py` (new):

```python
def test_loop_uses_post_fix_confirmation_knob(...) -> None:
    """Codex pattern: clean → finding → clean × 2 → READY (not MAX_ROUNDS).

    Scenario: R1 clean (1 confirmation), R2 finding + fix, R3 clean
    (1 confirmation after fix), R4 clean (2 confirmation after fix) → READY.
    With old logic (consecutive=2), R3+R4 satisfies. With new logic
    (post-fix-confirm=2), same. But new logic ALSO handles:
    R1 finding + fix, R2 clean (1 conf), R3 clean (2 conf) → READY,
    where old logic would also pass. Add test that R1 finding, R2 clean,
    R3 finding + fix, R4 clean, R5 clean → READY (was MAX_ROUNDS=3 fail).
    """
    # Mock codex.run_review to yield: finding, clean, finding, clean, clean
    # Mock claude_codegen.run_fix as no-op success
    # Run loop.run(resume=True) on synthetic state
    # Assert final_phase == "READY", not HALTED
```

**Commit:** `feat(autopilot): max_rounds default 5; confirmation_rounds_after_last_fix knob (v0.2.2 meta-bug)`

## Step 3 — Fix #2: SECURITY_FINDING keyword refinement

**File:** `tools/autopilot/codex.py`

Split SECURITY_KEYWORDS into two tiers:

```python
# Severe — auto-HALT regardless of severity rating.
SECURITY_KEYWORDS_SEVERE = (
    "auth bypass",
    "token leak",
    "credential leak",
    "secret leak",
    "password leak",
    "timing attack",
    "injection",
    "csrf",
    "xss",
    "ssrf",
    "rce",
)

# Soft — bare mentions (token / hmac / secret) that don't necessarily
# indicate security risk. F07 R1 markdown-rendering bug was flagged
# only because finding mentioned "token". Soft keywords no longer
# auto-HALT — they require P0/P1 severity to escalate.
SECURITY_KEYWORDS_SOFT = (
    "token",
    "secret",
    "hmac",
    "password",
    "credential",
    "auth",
)
```

**File:** `tools/autopilot/circuit_breaker.py`

Update `evaluate()` security check:

```python
def _has_severe_security_keyword(finding: Finding) -> bool:
    return finding.matches_keywords(SECURITY_KEYWORDS_SEVERE)

def _has_soft_security_keyword(finding: Finding) -> bool:
    return finding.matches_keywords(SECURITY_KEYWORDS_SOFT)

# In evaluate():
for f in findings:
    if _has_severe_security_keyword(f):
        return Trigger("SECURITY_FINDING", ...)  # always HALT
    if _has_soft_security_keyword(f) and f.severity in ("P0", "P1"):
        return Trigger("SECURITY_FINDING", ...)  # HALT only if high severity
    # P2/P3 soft-keyword findings fall through to normal fix flow.
```

**Unit test:** `tests/unit/test_autopilot_security_keywords.py` (new):

```python
def test_severe_keyword_always_halts() -> None:
    f = Finding(severity="P3", summary="potential SQL injection in handler", ...)
    assert circuit_breaker.evaluate([f], ...).code == "SECURITY_FINDING"

def test_soft_keyword_p2_does_not_halt() -> None:
    f = Finding(severity="P2", summary="webhook token uses markdown parse_mode", ...)
    trigger = circuit_breaker.evaluate([f], ...)
    assert trigger is None or trigger.code != "SECURITY_FINDING"

def test_soft_keyword_p1_halts() -> None:
    f = Finding(severity="P1", summary="token rendering causes XSS", ...)
    # Has both soft (token) AND severe (xss) — severe wins.
    assert circuit_breaker.evaluate([f], ...).code == "SECURITY_FINDING"
```

**Commit:** `feat(autopilot): tiered security keywords — soft keywords (token/secret) require P0/P1 to HALT`

## Step 4 — Fix #3: Resume must checkout feature branch

**File:** `tools/autopilot/loop.py`

In `run()`, immediately after `existing = state.load(...)` (whether resume
or not), ensure current branch matches `feature_state.branch`:

```python
# v0.2.2: ensure git checkout matches feature_state.branch regardless
# of which phase resume re-enters. Without this, Phase C codex review
# runs on whatever branch was checked out when founder invoked the CLI
# (often `main`), causing empty-diff false negatives.
current_branch = git_ops.current_branch(cfg)
if current_branch != feature_state.branch:
    if not git_ops.branch_exists(cfg, feature_state.branch):
        # Branch missing — can't proceed. Halt with clear reason.
        return _halt(
            cfg, feature_state, "BRANCH_MISSING",
            f"feature_state.branch={feature_state.branch!r} not found; "
            f"manual recovery needed before resume.",
        )
    print(
        f"Syncing branch checkout: {current_branch} → {feature_state.branch}"
    )
    git_ops.checkout(cfg, feature_state.branch)
```

Add `current_branch(cfg)` helper to `tools/autopilot/git_ops.py` if not
already exists:

```python
def current_branch(cfg: Config) -> str:
    return _run(cfg, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
```

**Unit test:** `tests/unit/test_autopilot_resume_branch_sync.py` (new):

```python
def test_resume_checks_out_feature_branch_if_on_main(...) -> None:
    """Setup: state.branch = feat/F99-foo, but caller is on main.
    Resume must switch to feat/F99-foo before Phase C entry.
    """
    # Use tmp git repo fixture, create feat/F99-foo branch, checkout main.
    # Call loop.run(resume=True). Mock codex/claude/verify.
    # Assert current branch == feat/F99-foo after resume.
```

**Commit:** `fix(autopilot): resume always syncs git checkout to feature_state.branch (F07 v0.2.2 bug)`

## Step 5 — Fix #4: tracker.update_status no-op on feature branch

**File:** `tools/autopilot/tracker.py`

Make `update_status()` a no-op when current branch is not main:

```python
def update_status(cfg: Config, feature_id: str, new_status: str) -> None:
    """Update tracker status for feature_id.

    v0.2.2: NO-OP when current branch is not main. Previously the
    function wrote docs/implementation-tracker.md on whatever branch
    was checked out, which polluted feature branches with status update
    noise and caused fallback commits during fix flow. Tracker updates
    are now founder's manual responsibility post-squash, OR a future
    v0.2.3 may centralize via a sidecar state file.
    """
    current = git_ops.current_branch(cfg)
    if current != cfg.base_branch:
        # Silently no-op on feature branches. Log for forensics.
        log.debug(
            "tracker.update_status: no-op (current branch %r != base %r)",
            current, cfg.base_branch,
        )
        return
    # ... existing tracker file mutation logic ...
```

**Note:** this means `loop.py`'s `tracker.update_status(...)` calls
during Phase A/B/C transitions become no-ops on feature branches. State
JSON still records phase transitions. Founder updates tracker.md
manually after squash (or via a separate `python -m tools.autopilot
sync-tracker` command — out of scope for v0.2.2).

**Unit test:** `tests/unit/test_autopilot_tracker_update.py` (new or
extend existing):

```python
def test_tracker_noop_on_feature_branch(tmp_path, ...) -> None:
    """tracker.update_status should not modify file when on feature branch."""
    # Setup tmp git repo with main + feat branch.
    # Checkout feat branch.
    # Capture tracker.md mtime / hash.
    # Call tracker.update_status(cfg, "F99", "REVIEWING").
    # Assert tracker.md unchanged.

def test_tracker_writes_on_main(tmp_path, ...) -> None:
    # Same setup, but on main.
    # Call tracker.update_status(cfg, "F99", "MERGED").
    # Assert tracker.md updated.
```

**Commit:** `fix(autopilot): tracker.update_status no-op on feature branches (F07 v0.2.2 bug)`

## Step 6 — Fix #5: State schema tolerance

**File:** `tools/autopilot/state.py`

Update `load()` to filter unknown fields before passing to dataclass:

```python
def load(cfg: Config, feature_id: str) -> FeatureState | None:
    path = cfg.state_dir / feature_id / "state.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))

    # v0.2.2: schema tolerance. Filter unknown fields with warning to
    # support cross-version state files (e.g., state written by newer
    # orchestrator loaded by older code during partial deploys, or
    # state predating a field addition).
    known_fields = {f.name for f in dataclasses.fields(FeatureState)}
    unknown = set(raw.keys()) - known_fields
    if unknown:
        log.warning(
            "state.load: ignoring unknown fields in %s: %s "
            "(orchestrator version may be older than state file schema)",
            path, sorted(unknown),
        )
        raw = {k: v for k, v in raw.items() if k in known_fields}
    return FeatureState(**raw)
```

**Unit test:** `tests/unit/test_autopilot_state.py` (extend):

```python
def test_load_filters_unknown_fields(tmp_path, caplog) -> None:
    """state.json with extra keys loads cleanly with warning."""
    cfg = make_test_config(tmp_path)
    state_path = tmp_path / "F99" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({
        # Known fields
        "feature_id": "F99",
        "branch": "feat/F99-foo",
        "base_branch": "main",
        # ... other required known fields ...
        # Unknown future field
        "future_field_v0_3": "some value",
    }))
    with caplog.at_level("WARNING"):
        state = load(cfg, "F99")
    assert state is not None
    assert state.feature_id == "F99"
    assert "future_field_v0_3" in caplog.text
    assert "ignoring unknown fields" in caplog.text
```

**Commit:** `fix(autopilot): state.load tolerates unknown fields (cross-version safety)`

## Step 7 — Fix #6: Codex artifact non-clobber

**File:** `tools/autopilot/codex.py`

Update `save_review_artifact()` to detect existing artifact + use suffix:

```python
def save_review_artifact(
    cfg: Config,
    result: ReviewResult,
    feature_id: str,
    round_num: int,
) -> Path:
    artifacts_dir = cfg.state_dir / feature_id / "codex"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"round-{round_num:02d}"
    out_path = artifacts_dir / f"{base_name}.txt"

    # v0.2.2: don't clobber prior-run artifacts on resume. If a file with
    # the canonical name exists, find next available `-resumeN` suffix.
    if out_path.exists():
        n = 1
        while True:
            candidate = artifacts_dir / f"{base_name}-resume{n}.txt"
            if not candidate.exists():
                out_path = candidate
                break
            n += 1
            if n > 99:
                raise RuntimeError(
                    f"Too many resume artifacts for {feature_id} round "
                    f"{round_num} — manual cleanup needed."
                )

    out_path.write_text(result.raw_output, encoding="utf-8")
    return out_path
```

**Unit test:** extend `tests/unit/test_autopilot_codex.py`:

```python
def test_save_review_artifact_non_clobber(tmp_path) -> None:
    """Second save of same round goes to round-NN-resume1.txt, not clobber."""
    cfg = make_test_config(tmp_path)
    result = make_dummy_review_result()

    p1 = save_review_artifact(cfg, result, "F99", 1)
    assert p1.name == "round-01.txt"
    assert p1.exists()

    p2 = save_review_artifact(cfg, result, "F99", 1)
    assert p2.name == "round-01-resume1.txt"
    assert p2.exists()
    assert p1.exists()  # original preserved
    assert p1 != p2
```

**Commit:** `fix(autopilot): codex artifact non-clobber on resume (preserve forensics)`

## Step 8 — Workaround #7: Codex stale blob detection (log + warn)

True fix needs investigation of Codex CLI internals — possibly v0.2.3.
For v0.2.2, add a sanity check: after codex review, if the raw output
mentions a specific git blob/commit SHA that doesn't match current HEAD,
log a warning. Operator can decide if review is trustworthy.

**File:** `tools/autopilot/codex.py`

In `run_review()`, after parsing:

```python
def run_review(...) -> ReviewResult:
    # ... existing subprocess invocation ...

    # v0.2.2 workaround: detect stale-blob symptom. If codex's preamble
    # mentions a git SHA that's not current HEAD, log warning. True fix
    # is v0.2.3 codex CLI integration audit.
    head_sha = git_ops.head_sha(cfg)
    sha_pattern = re.compile(r"\b([0-9a-f]{7,40})\b")
    output_shas = set(sha_pattern.findall(output))
    if output_shas and head_sha[:7] not in {s[:7] for s in output_shas}:
        log.warning(
            "codex review: output mentions SHA(s) %s but current HEAD is %s. "
            "Possible stale-blob issue — verify findings against current state.",
            sorted(output_shas)[:3], head_sha[:7],
        )

    findings, clean = parse_findings(output)
    # ... existing return ...
```

**Unit test:** synthetic codex output with stale SHA:

```python
def test_run_review_warns_on_stale_sha(monkeypatch, caplog) -> None:
    """If codex output references a SHA not matching HEAD → warning logged."""
    # Mock subprocess to return canned output mentioning SHA abc1234.
    # Mock head_sha to return def5678.
    # Run run_review.
    # Assert warning in caplog text mentioning both SHAs.
```

**Commit:** `feat(autopilot): codex run_review logs warning on stale-blob SHA mismatch`

## Step 9 — Doc #8: Concurrent agent isolation policy

**File:** `docs/autopilot/orchestrator-usage.md`

Add a new section near the top (or after the existing "Mental model"):

```markdown
## Concurrency

The orchestrator is NOT safe to run with another git-writing agent on the
same repository. Specifically:

- Running 2+ Claude Code sessions (or any Mode 3/4 autopilot) that share
  the same `.git/` directory CAN trample each other's branch refs.
  Observed 2026-05-13 in F07 pilot: a `feat/dashboard-realtime` session
  reset `feat/F07-settings` ref via shared `.git/`. Recovery required
  `git reflog` + manual `git update-ref`.
- The orchestrator does NOT acquire a file lock. There is no current
  mechanism preventing concurrent writes; that's a v0.2.3+ feature.

**Operational policy (until lock mechanism lands):**

1. Run AT MOST one Claude Code session at a time per repository.
2. If 2 features must be worked in parallel, use `git worktree`:

```bash
   git worktree add /Users/.../MyMoneyWent-F07 feat/F07-settings
   git worktree add /Users/.../MyMoneyWent-dashboard feat/dashboard-realtime
```

   Then run each session in its own worktree dir (each has independent
   `.git/` linked back via worktree pointer, but checkouts/refs are
   isolated).
3. Before starting any autopilot session, verify no `.git/*.lock` files
   exist in the target repo.
```

**Commit:** `docs(autopilot): document concurrent agent isolation policy (no parallel sessions)`

## Step 10 — Update CHANGELOG + plan changelog

**File:** `CHANGELOG.md`

Append to `## [Unreleased]`:

```markdown
### Fixed — Autopilot orchestrator v0.2.2 (tooling hardening)

- **max_review_rounds 3 → 5; new `confirmation_rounds_after_last_fix=2`
  knob** — F07 + v0.2.1 pilots showed the math `max=3 + clean=2 consec`
  is unable to ship when adjacent micro-findings cascade. New logic
  requires N clean rounds AFTER the last fix commit, decoupled from max.
- **SECURITY_FINDING keyword tiering** — severe keywords (`auth bypass`,
  `token leak`, `injection`, `csrf`, etc.) always HALT. Soft keywords
  (`token`, `secret`, `hmac`) require P0/P1 severity to HALT. Stops
  benign Markdown-rendering findings from auto-tripping security halt.
- **Resume now syncs branch checkout** — `loop.run(resume=True)` ensures
  current git branch matches `feature_state.branch` before Phase C entry.
  Previous: caller on `main` → codex review saw empty diff.
- **tracker.update_status no-op on feature branches** — orchestrator
  no longer mutates `docs/implementation-tracker.md` while on a feature
  branch. Updates are founder's post-squash responsibility (or v0.2.3
  may centralize via sidecar state).
- **state.load tolerates unknown fields** — JSON state files with
  extra keys load cleanly with a warning. Supports cross-version safety
  when orchestrator code lags state-file schema.
- **codex artifact non-clobber** — resume rounds write to
  `round-NN-resume1.txt` instead of overwriting `round-NN.txt`. Forensics
  preserved across resume cycles.

### Added — Autopilot diagnostic + policy

- **codex stale-blob detection** — `run_review()` logs a warning when
  Codex output mentions a SHA not matching HEAD. Operator must verify
  findings against current state. True fix (codex CLI integration audit)
  deferred to v0.2.3.
- **Concurrency policy doc** — orchestrator-usage.md now documents the
  "one session per repo" rule and `git worktree` workaround.

### Notes — v0.2.3 backlog

- Codex CLI stale-blob true fix (pin explicit SHA, verify resolved blob).
- Tracker update sidecar / explicit `sync-tracker` CLI command.
- Acquire/release file lock for concurrent-session safety.
```

**File:** `docs/autopilot/autopilot-implementation-plan.md`

Update header + append changelog row:

```markdown
> **Version:** v0.2.2 (current; see changelog for revision history)
> **Trạng thái:** Active — pre-pilot blockers resolved (v0.2.0 squash 5a35dcb);
> tooling hardening v0.2.2 lands cumulative fixes from F07 + v0.2.1 pilot signal
```

```markdown
| v0.2.2 | 2026-05-13 | 6 code fixes + 1 doc + 1 diagnostic workaround from
F07 + v0.2.1 cumulative pilot signal. max_rounds 3→5 with new
`confirmation_rounds_after_last_fix=2`; SECURITY keyword tiering (severe vs
soft); resume syncs branch checkout; tracker.update_status no-op on feature
branches; state.load tolerates unknown fields; codex artifact non-clobber;
codex stale-blob detection (log only); concurrent agent isolation policy
documented. F07 resume unblocked next session. |
```

**Commit:** `docs: changelog + plan v0.2.2 — tooling hardening from F07 + v0.2.1 pilot signal`

## Step 11 — Local verify

```bash
ruff check tools/ tests/ core/ markets/ handlers/ migrations/
black --check tools/ tests/ core/ markets/ handlers/ migrations/
mypy tools/ core/ markets/ tests/ handlers/
lint-imports
pytest tests/ -v
```

ALL must pass. Expected test count delta: baseline + ~10 new tests
(2 max_rounds + 3 security keywords + 1 resume branch sync + 2 tracker
update + 1 state load + 1 codex artifact + 1 stale-blob warning).

If verify fails → up to 2 retries to fix root cause. After 2 retries
→ HALT `VERIFY_REGRESSION`.

## Step 12 — Inline Codex review (EXTENDED BUDGET: ≤5 rounds, 2× consec clean)

This PR raises max_review_rounds default to 5, so we eat our own dogfood
on the inline review.

**Round N (1, 2, 3, 4, 5):**

```bash
codex review --base main 2>&1 \
  | tee .autopilot/state/v0.2.2/codex/round-NN.txt
```

**Parse output:**

CLEAN — any of: `did not identify any`, `did not find any`, `no actionable`,
`appear internally consistent`, NO severity-bracket line.

FINDING — `- [P0|P1|P2|P3] <summary> — <file>:<lines>`.

**Circuit-breaker checks (same as prior prompts, with v0.2.2 SECURITY
keyword tiering now in effect — soft keywords require P0/P1 to HALT):**

| Check | Action |
|---|---|
| Severity P0 | HALT `P0_FOUND` |
| Severe security keyword (auth bypass, injection, csrf, etc.) | HALT `SECURITY_FINDING` |
| Soft security keyword + P0/P1 severity | HALT `SECURITY_FINDING` |
| Soft security keyword + P2/P3 severity | proceed to fix |
| Arch/schema/breaking-change keyword | HALT `ARCH_FINDING` |
| Same finding hash across rounds | HALT `RECURRING_FINDING` |
| Otherwise | apply minimum-viable fix, atomic commit |

**Loop logic (eat-own-dogfood):**

- Track `rounds_since_last_fix`.
- After each round:
  - If CLEAN → `rounds_since_last_fix += 1`. If ≥2 → 2× post-fix-confirm
    achieved → proceed to Step 13.
  - If FINDING → apply fix, atomic commit, reset `rounds_since_last_fix = 0`.
- If round 5 done without 2× post-fix-confirm → HALT `MAX_ROUNDS`.

**Fix commit pattern:** `fix(autopilot): address codex round NN — <summary>`.

## Step 13 — Squash + push (ONLY when 2× post-fix-confirm clean confirmed)

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

1. max_review_rounds 3→5; new confirmation_rounds_after_last_fix=2 knob.
   Empirical pattern: adjacent micro-findings cascade per fix commit.
   Old math (max=3 + clean=2 consec) couldn't ship. New decouples
   post-fix confirmation from total budget.
2. SECURITY_FINDING keyword tiering: severe (auth bypass / injection /
   csrf / xss) always HALT; soft (token / secret / hmac) need P0/P1.
   Stops false-positive halts on benign Markdown rendering bugs.
3. Resume syncs git checkout to feature_state.branch regardless of phase.
   Was: empty-diff codex review if caller on main.
4. tracker.update_status no-op on feature branches. Was: polluted feature
   branches with status update fallback commits.
5. state.load tolerates unknown fields with warning. Was: TypeError when
   schema added field (e.g., last_active_phase in v0.2.1).
6. codex.save_review_artifact non-clobber via -resumeN suffix. Was:
   resume rounds clobbered prior-run forensics.

Plus:
- codex.run_review logs warning when output references SHA != HEAD
  (stale-blob detection — true fix v0.2.3 backlog).
- docs/autopilot/orchestrator-usage.md: concurrency policy (one Claude
  Code session per repo; git worktree for parallel work).

Codex review (inline, eats own dogfood with new max=5): R1 <...> + R2
<...> + ... + final 2× post-fix-confirm clean at R<X>+R<X+1>.

<count> tests pass.

F07 resume unblocked NEXT SESSION: founder runs
`python -m tools.autopilot resume F07` with orchestrator v0.2.2 active."

git branch -D chore/autopilot-v0.2.2
git push origin main
```

If push rejected → HALT. Do NOT force-push.

---

## Circuit breakers (HALT and write report)

PAUSE immediately and write `.autopilot/state/v0.2.2/halt-report.md` if
ANY trigger fires:

1. Pre-flight regression.
2. Push rejected.
3. VERIFY_REGRESSION (verify fails 2× consecutively).
4. P0_FOUND.
5. SECURITY_FINDING (severe keyword OR soft+P0/P1).
6. ARCH_FINDING / breaking-change keyword.
7. RECURRING_FINDING (same hash across 2 rounds).
8. TYPE_IGNORE_PROPOSED.
9. SCOPE_CREEP — fix requires >2 files beyond Step's scope.
10. MAX_ROUNDS — 5 rounds without 2× post-fix-confirm.
11. Tool error 2× in a row.
12. Context budget >70%.

### Halt report template

```
HALT — autopilot v0.2.2 circuit broken.

Step:    <Step number + description>
Trigger: <one of 12>
Branch:  chore/autopilot-v0.2.2
HEAD:    <SHA>

Detail:
<error output OR finding excerpt>

Codex sequence so far:
  R1: <result>
  R2: <result>
  ...

State:
- Commits on branch: <list>
- Files changed: <list>
- Codex artifacts: .autopilot/state/v0.2.2/codex/round-*.txt

Requesting founder input on:
<specific question>
```

---

## Final report (when Step 13 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
AUTOPILOT v0.2.2 — Tooling hardening — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA> on main
Branch chore/autopilot-v0.2.2: DELETED
Push origin/main: OK

Codex review sequence (inline, eats own dogfood max=5):
  R1: <CLEAN | finding details + fix SHA>
  R2: <...>
  R3: <... if reached>
  R4: <... if reached>
  R5: <... if reached>
  Final state: 2× post-fix-confirm clean at R<X>+R<X+1>
  Artifacts: .autopilot/state/v0.2.2/codex/round-*.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean (no new errors in v0.2.2 scope)
  lint-imports: clean
  pytest:       <count> passed (baseline + ~10 new tests)

Files added:
  - tests/unit/test_autopilot_max_rounds.py
  - tests/unit/test_autopilot_security_keywords.py
  - tests/unit/test_autopilot_resume_branch_sync.py
  - tests/unit/test_autopilot_tracker_update.py (or extended)
  - tests/unit/test_autopilot_state.py (extended)
  - tests/unit/test_autopilot_codex.py (extended)

Files modified:
  - tools/autopilot/config.py
  - tools/autopilot/loop.py
  - tools/autopilot/codex.py
  - tools/autopilot/circuit_breaker.py
  - tools/autopilot/state.py
  - tools/autopilot/tracker.py
  - tools/autopilot/git_ops.py (if current_branch helper added)
  - docs/autopilot/orchestrator-usage.md
  - docs/autopilot/autopilot-implementation-plan.md
  - CHANGELOG.md

═══════════════════════════════════════════════════════

Next steps (NOT in this prompt's scope — founder runs):

1. Resume F07 pilot with v0.2.2 orchestrator:

   cd /Users/maingocanh/Projects/MyMoneyWent
   git checkout feat/F07-settings
   git merge main -m "merge: v0.2.2 into feat/F07-settings"
   # Resolve conflicts if any (likely CHANGELOG)

   # Reset F07 state
   python3 -c "import json; from pathlib import Path; p = Path('.autopilot/state/F07/state.json'); s = json.loads(p.read_text()); s.update({'phase': 'VERIFIED', 'current_round': 0, 'consecutive_clean_rounds': 0, 'halt_reason': None, 'halt_artifact_path': None, 'fixed_finding_hashes': []}); p.write_text(json.dumps(s, indent=4) + '\n'); print('reset')"

   source .venv/bin/activate
   python -m tools.autopilot resume F07

   Expected: orchestrator runs codex with new max=5 budget. Cascade
   pattern (if still present) has 5-round headroom. SECURITY_FINDING
   keyword tiering won't false-positive on Markdown bugs. Resume syncs
   branch correctly. Should converge to READY or surface a real
   unresolved issue (not adjacent micro-finding).

2. After F07 READY → manual squash F07 to main per ready-report.md.

3. v0.2.3 backlog (track when authoring later):
   - Codex CLI stale-blob true fix (pin explicit SHA pair).
   - tracker sync command / sidecar.
   - File lock for concurrent-session safety.

End of autopilot v0.2.2.
═══════════════════════════════════════════════════════
```

Then STOP. Founder handles F07 resume.

---

## Global rules

1. READ FIRST. Especially loop.py, codex.py, circuit_breaker.py — fixes
   must integrate with current structure, not assume.
2. NEVER touch F07 branch / files in this session.
3. NEVER force-push.
4. NEVER add `# type: ignore`.
5. Atomic commits per fix step. Each step is independent — if one blocks,
   HALT cleanly with halt-report; don't quietly skip.
6. Verify before claiming done — re-run pytest after "tests pass" message.
7. Tool error 2× → circuit breaker.
8. Context budget >70% → pause + halt-report. Branch state intact for
   continuation prompt.
9. Eat-own-dogfood inline review: use new max=5 budget. Don't manual-loop
   past 5.
10. If Step 12 cascade pattern persists past R5 → HALT MAX_ROUNDS, founder
    decides override (rare) or further v0.2.3 backlog.

Begin with Pre-flight, then Step 1. Execute through Step 13 final report.
