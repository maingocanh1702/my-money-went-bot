# Autopilot Orchestrator — Implementation Plan & Status

> **Version:** v0.2.2 (current; see changelog for revision history)
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active — pre-pilot blockers resolved (squash `5a35dcb`); tooling hardening v0.2.2 lands cumulative fixes from F07 + v0.2.1 pilot signal; F07 resume unblocked next session
> **Owner:** Founder (dev)
> **Mục đích:** Single-page tracker cho hành trình orchestrator từ scaffold (DONE) → first end-to-end auto flow (BLOCKED) → multi-feature production use (FUTURE).
> **Tham chiếu:**
> - [orchestrator-usage.md](./orchestrator-usage.md) — usage doc (the "what")
> - [development-workflow.md](../operations/development-workflow.md) — manual 10-step workflow (orchestrator codifies)
> - [wave0-retrospective.md](../operations/wave0-retrospective.md) — 7 lessons (embedded in design)
> - [Level 3 template](prompts/level3-autopilot-template.md) — paste-prompt predecessor

---

## TL;DR

- **Scaffold v0.1.0 SHIPPED** (commit `839cb24`, 2026-05-12) but orchestrator is **NOT pilot-proven**. End-to-end auto flow has zero real-world runs.
- **First pilot allowed only after** (a) Claude CLI behavior probe in a throwaway worktree, (b) F07 (Settings) spec migration to template format, (c) Blocker #5 implementation (`--auto-merge` opt-in flag with safe-default off).
- **Auto-merge is OFF by default in v0.1.x** (safe-by-default per Blocker #5). First 3 pilots never pass `--auto-merge`. Auto-merge unlocks only via explicit flag AND only for P2 features (per §6.5).
- **F07 (Settings) is the first pilot target** because it's isolated. But if it touches schema it's classified **P1-lite, not pure low-risk** (see §6.5 risk class policy).
- **Goal of first pilot is to validate Phase A→D + READY mechanics, not maximize speed or automation.** Manual diff review + post-merge smoke checklist mandatory.
- **ETA to first run:** half a day to a full day for first manual-merge pilot after Blockers #1–#5 are resolved.

---

## 1. Status snapshot — what's done vs what's not

### 1.1. Shipped (live on `main`)

| Component | Module / file | LOC | Notes |
|-----------|---------------|-----|-------|
| CLI entry | `tools/autopilot/__main__.py` | 100 | 6 commands: lint, preflight, run, resume, status, abort |
| Spec linter | `tools/autopilot/spec_lint.py` | 297 | 8 rules + meta-block fallback resolver |
| Codex wrapper + parser | `tools/autopilot/codex.py` | 241 | Parser shaped from Wave 0 output observations; tested against synthetic fixtures only (see §1.2) |
| Claude code-gen wrapper | `tools/autopilot/claude_codegen.py` | 210 | **Unverified against real `claude -p` behavior** (BLOCKER #1) |
| Verify runner | `tools/autopilot/verify.py` | 85 | ruff/black/mypy/lint-imports/pytest |
| Git ops | `tools/autopilot/git_ops.py` | 125 | branch/commit/squash/dry-run-merge wrappers |
| Preflight | `tools/autopilot/preflight.py` | 97 | env + git + CLI binary checks |
| State checkpoint | `tools/autopilot/state.py` | 72 | JSON per feature, resume-friendly |
| Circuit breaker | `tools/autopilot/circuit_breaker.py` | 159 | 10 halt conditions per Level 3 template |
| Tracker updater | `tools/autopilot/tracker.py` | 115 | Updates implementation-tracker.md row status |
| Auto-merge | `tools/autopilot/merge.py` | 166 | 5 pre-merge gates + squash-merge |
| Main loop | `tools/autopilot/loop.py` | 274 | Phase A→E orchestration with resume |
| Config | `tools/autopilot/config.py` | 111 | Path + env override resolver |
| Spec template (FE) | `docs/operations/spec-template.md` | 146 | 10 sections + 3 autopilot blocks |
| Spec template (BE) | `docs/operations/spec-template-be.md` | 94 | 5 sections + invariants block |
| Usage doc | `docs/operations/orchestrator-usage.md` | 215 | CLI commands, gates, breakers, anti-patterns |
| Unit tests | `tests/unit/test_autopilot_*.py` | 340 | 15 tests, all pass |

**Static enforcement applied:**

- Ruff per-file-ignore for `tools/autopilot/*.py` (S603/S607 — trusted CLI subprocess).
- mypy strict NOT scoped to `tools/` (orchestrator is pragmatic-typed; test files in `tests/unit/` ARE scoped strict and pass with `-> None` return annotations).
- `.gitignore` excludes `.autopilot/` (per-feature state checkpoints).

### 1.2. Validated

- All 15 unit tests for orchestrator + spec lint pass — **unit scope only**, full repo suite state at scaffold merge not measured (TODO: capture once F-i18n stabilizes).
- ruff + black + mypy(tests) + import-linter all clean on the orchestrator + tests.
- Linter runs cleanly on existing 17 specs (3 warnings each — missing optional autopilot blocks, expected).
- `python -m tools.autopilot lint i18n` resolves correct FE+BE paths.
- `python -m tools.autopilot preflight` correctly blocks dirty trees (verified during scaffold commit).
- **Codex parser tested only against synthetic fixtures embedded in `tests/unit/test_autopilot_codex_parser.py`.** Real Wave 0 outputs were referenced when writing the parser but were NOT committed as fixture files — this means parser robustness on future Codex output drift is unaudited. Saving raw Codex stdout to `.autopilot/state/<f>/codex/round-NN.txt` per round mitigates by giving forensics on first parse failure.

### 1.3. NOT validated (because no end-to-end run yet)

- `claude -p "<prompt>"` actually executes long codegen tasks non-interactively.
- Claude in non-interactive mode auto-commits via bash tool (or doesn't — see blocker #1).
- `codex review --base main` parser handles every real-world output shape (only synthetic fixtures so far).
- Resume from each phase actually picks up correctly. First pilot exercises the happy path `INIT → READY`; resume from `HALTED` remains untested until the first real circuit-breaker fires.
- Auto-merge gate sequencing under realistic conditions (no real branch yet).
- Tracker row update against real implementation-tracker.md row format (only synthetic test).

---

## 2. Blockers to first end-to-end run

### Blocker #1 — Verify `claude -p` behavior + fix codegen success detection

**Problem:** `claude_codegen.py` assumes Claude CLI in non-interactive mode (`claude -p "<prompt>"`):
- Reads spec files via Read tool ✓ (Claude has it)
- Runs bash to execute pytest, git ✓ (Claude has Bash tool)
- **Auto-commits** atomic commits ← unverified
- Outputs `AUTOPILOT_PHASE_A_COMPLETE` literal string ← unverified
- Stays within context budget for a 1-2h codegen task ← unverified

Current success check (`claude_codegen.py` line ~199):

```python
success = (
    completed.returncode == 0
    and not halted
    and commits_added > 0     # ← brittle
)
```

If Claude writes files but doesn't commit, `commits_added == 0` → halt with `CODEGEN_FAILED` even though code was written.

**Severity:** P0 — blocks first run.

**Action — probe in throwaway worktree (NEVER on real branch / main):**

```bash
# Create isolated worktree so probe leaves zero residue on real repo
git worktree add /tmp/mmw-claude-probe main
cd /tmp/mmw-claude-probe

# Probe 1: read + bash invocation (read-only, safe anywhere)
claude -p "Read README.md, tell me line count, then run \`git status\` and report"

# Probe 2: file write + commit behavior (safe — worktree is throwaway)
claude -p "Add a comment line '# probe' to top of CHANGELOG.md, then git commit it with message 'probe: claude cli test'. Report what you did."

# Inspect what Claude actually did in the worktree
git log --oneline -3
git status

# Cleanup — worktree never touched real repo
cd /Users/maingocanh/Projects/MyMoneyWent
git worktree remove /tmp/mmw-claude-probe --force
```

**Then update `claude_codegen.py` based on observation:**

- If Claude commits: keep current logic, but add fallback orchestrator-side commit if `commits_added == 0 AND working_tree_dirty`.
- If Claude doesn't commit: in `run_codegen`, after `_invoke_claude` completes, run `git add -A && git commit -m "feat({feature_id}): autopilot codegen output"` IF working tree changed.
- Add log capture: write `claude_codegen.stdout/stderr` to `.autopilot/state/<feature>/codegen-N.log` for forensics.

**Estimated effort:** 30-60 min (worktree setup 2 min, probe 10 min, fix 30 min, retest in throwaway worktree 15 min).

**Foundation rule:** probe tool behavior must NEVER leave commits / artifacts in the real repo. Use git worktree or scratch clone.

### Blocker #2 — Decide single-shot vs multi-turn for long codegen

**Problem:** `claude -p` is single-shot. A "build F07 (Settings) from spec" task realistically needs multiple turns (read spec → outline → write code → write tests → run tests → fix → commit). If `claude -p` cannot iterate, single-shot will run out of context or produce incomplete code.

**Severity:** P1 — may block first run depending on Claude CLI behavior.

**Decision rule (locked, do not deliberate during pilot prep):**

1. Probe (Blocker #1) checks `claude --help` for `--max-turns N` or equivalent multi-turn flag.
2. If **multi-turn flag exists** → use it. Done. ETA 15 min.
3. If **single-shot only** → **Option A is the default** (chunked prompts, orchestrator drives). Implement 4 chunks: (i) read spec + plan, (ii) write code skeleton + commit, (iii) write tests + commit, (iv) run verify + fix. ETA ~2h.
4. **Option C (SDK rewrite) is deferred to NTH-X** even if more elegant. Pilot uses Option A as fallback. Don't burn pilot prep time on SDK research.

**Estimated effort:** 15 min (if multi-turn works) OR 2h (chunked Option A — locked default if probe shows single-shot).

### Blocker #3 — Migrate F07 (Settings) spec to autopilot template format

**Problem:** No existing spec has the 3 autopilot blocks (`autopilot:meta`, `autopilot:gaps`, `autopilot:test_plan`). Linter accepts existing specs (warnings only) but autopilot's `loop.py` doesn't strictly require them — yet quality of codegen output depends on them being filled.

**Severity:** P1 — pilot won't fail without it, but result will be lower quality.

**Action:**

1. Pick F07 (Settings) as first pilot (rationale below in §3).
2. Manual edit `docs/features/feature-settings.md` (filename stays — matches existing convention):
   - Add `<!-- autopilot:meta ... -->` with `feature_id: F07`, `branch: feat/F07-settings`, `phase: 2`, `wave: 1`, `risk_tier: P1`, `depends_on: []`.
   - Add `<!-- autopilot:gaps ... -->` with all unknowns CLOSED + locked decisions.
   - Add `<!-- autopilot:test_plan ... -->` with 5 categories filled (or `N/A — <reason>`).
3. Verify: `python -m tools.autopilot lint F07` → 0 warnings (resolver finds spec via meta block `feature_id: F07`).
4. Commit as `docs(F07): migrate settings spec to autopilot template format`.

**Estimated effort:** 15-30 min (depends on how locked the design currently is).

### Blocker #4 — Atomic state.json write (promoted from NTH)

**Problem:** `state.save()` writes JSON via `path.write_text(...)` directly. If the orchestrator process crashes mid-write (Ctrl+C, OOM, power), `state.json` may be truncated → corrupt → `state.load()` raises → resume impossible without manual cleanup.

**Severity:** Low likelihood, Medium impact, **15 min fix** — promoted from NTH-4 to Blocker because cost vs benefit is overwhelming.

**Action:**

```python
# In tools/autopilot/state.py save():
tmp = path.with_suffix(".json.tmp")
tmp.write_text(state.to_json(), encoding="utf-8")
tmp.replace(path)  # atomic on POSIX
```

**Estimated effort:** 15 min (5 min code + 5 min test + 5 min verify).

### Blocker #5 — Implement `--auto-merge` opt-in flag before first pilot

**Problem:** Pilot policy in §5 says first 3 pilots MUST run with manual merge. But the `run` command currently executes Phase E (auto squash + commit + delete branch) unconditionally — there's no way to stop at READY. Relying on "founder remembers to ctrl+C before merge" is the WRONG kind of mitigation; pilot policy must be enforced mechanically by the code path, not by founder discipline.

**Severity:** P0 — without safe-default merge control, pilot policy is unenforceable. The CLI must default to no merge; explicit `--auto-merge` is allowed only after pilot maturity and only for P2 features.

**Action:**

1. Add `--auto-merge` flag (opt-in) to `tools/autopilot/__main__.py` for the `run` and `resume` commands. **No flag = no merge** (safe default).
2. Plumb through `loop.run(cfg, feature_id, *, resume=False, auto_merge=False)` parameter.
3. In Phase D/E section of `loop.run`, if `auto_merge is False` (the default): stop after Phase D, write a "READY for manual merge" report to `.autopilot/state/<feature>/ready-report.md` with: branch name, commits ahead, dry-run merge result, suggested squash command, post-merge smoke checklist. Set state.phase = `READY` and exit code 0.
4. **Default value: `auto_merge=False`** (safe-by-default). To unlock auto-merge after pilot maturity, founder must explicitly pass `--auto-merge` AND the feature must be classified P2 (per §6.5). The CLI prints a warning when `--auto-merge` is used: "WARNING: auto-merge enabled. Per §6.5 only P2 features qualify. Continue? (y/N)".
5. Add unit tests:
   - `loop.run(..., auto_merge=False)` does NOT call `merge.attempt_merge` and DOES write ready-report.
   - `loop.run(..., auto_merge=True)` does call `merge.attempt_merge`.
   - CLI without `--auto-merge` flag → loop receives `auto_merge=False`.
   - CLI with `--auto-merge` flag → loop receives `auto_merge=True`.

**Estimated effort:** 45-60 min (CLI flag + loop param + report writer + 1 unit test).

**Why P0 not NTH:** §5 Decision #1 is load-bearing for risk policy. If flag doesn't exist, founder may forget OR `python -m tools.autopilot run F07` accidentally runs to merge. Pilot policy without code enforcement is documentation theater.

### Total ETA to first run

- Blocker #1: 30-60 min
- Blocker #2: 15 min OR 2h (decision-locked above)
- Blocker #3: 15-30 min
- Blocker #4: 15 min
- Blocker #5: 45-60 min
- First end-to-end pilot run: 1-2h (Codex review + auto-fix loop is unbounded)

**Realistic:** half a day to a full day for first manual-merge pilot (Codex round count unpredictable; pilot exits at READY phase, founder reviews + manually squashes).

### Estimated cost for first pilot

- Claude codegen (Phase A) — 1 run: ~$1-3 (depending on chunked vs single-shot, output token count)
- Codex review (Phase C) — 2-3 rounds: ~$0.50-1 per round = ~$1-2 total
- Claude fixes (Phase C) — 1-2 rounds: ~$0.50-1 each
- **Estimated total: $2-5 per pilot feature.** Cost cap (NTH-3) not blocking for first pilot but should land before parallel multi-feature runs.

---

## 3. First pilot target: F07 (Settings) (not F-i18n)

| Criterion | F07 (Settings) | F-i18n | F-onboarding |
|-----------|:----------:|:------:|:------------:|
| Already started outside orchestrator | No ✓ | YES ✗ | No ✓ |
| Architectural surface | Medium-low (`users` table extension) | Medium (lookup pattern) | Medium (state machine) |
| Security surface | None | None | Token in start payload |
| Test categories applicable | 4/5 (retry/idempotency N/A — pure CRUD; **concurrent applies** to settings updated mid-recap-fire) | 3/5 (no retry, no concurrent) | 5/5 |
| Estimated codegen effort | Low | Low | Medium |
| Codex round risk | P3 only likely | P3 only likely | P1 possible (auth surface) |
| Suitable for Level 3 (per template) | YES (P1-lite per §6.5) | YES (but already started) | Borderline |

**Decision:** F07 (Settings). Clean state, no in-flight code, isolated user-prefs change.

**Risk classification:** **P1-lite, NOT pure low-risk.** F07 (Settings) extends `users` table (locale + tz + recap toggle). Schema change ≠ pure low-risk even if no money/auth/tenant-sensitive logic.

**F07 (Settings) test requirements (mandatory before merge):**

- Migration upgrade + downgrade both tested (testcontainers).
- Default behavior for **existing users** with NULL settings (backward compat).
- **Tenant isolation** — settings are per-user-scoped, must verify user A cannot read/write user B's settings.
- Fallback for missing settings keys (no crash).
- 4/5 test categories applicable: happy / missing-optional / pathological / concurrent (settings updated mid-recap-fire). Retry/idempotency N/A — pure CRUD.

If first pilot **skips tenant isolation test** because "feature feels small", the orchestrator is violating Wave 0 lesson #4 + workflow §2.4 mandatory rule. Halt manually if Codex doesn't catch.

**Order after F07 (Settings):**

1. **F07 (Settings)** — first pilot, validate Phase A→D + READY report; founder performs manual squash merge.
2. **F-i18n cleanup** — finish whatever's left manually OR run autopilot in `--skip-codegen` mode (when implemented as nice-to-have #1).
3. **F-onboarding** — if F07 (Settings) clean, try moderate complexity. Still default no-merge; do not pass `--auto-merge`.
4. **F02 / F08** — DO NOT autopilot. Per Wave 0 lesson #3, foundation/security-critical needs Mode 4 manual.

---

## 4. Nice-to-have improvements (post-first-pilot)

Not blockers; add after validating loop with at least one successful merge.

| # | Improvement | Why | Effort |
|---|-------------|-----|--------|
| NTH-1 | `--skip-codegen` flag for `run` | Lets autopilot pick up where manual codegen stopped (e.g. F-i18n). Enters Phase B directly. | 30 min |
| ~~NTH-2~~ | ~~Persistent claude_codegen log to `.autopilot/state/<f>/codegen-N.log`~~ | **FOLDED INTO Blocker #1** (log capture is mandatory for Claude probe/codegen forensics) | — |
| NTH-3 | Cost tracking — count Codex + Claude invocations per run, dump $$ estimate to state.json | Cap runaway spend; budget visibility. | 1h |
| ~~NTH-4~~ | ~~Atomic state.json write~~ | **PROMOTED to Blocker #4** (15 min, ship before pilot) | — |
| NTH-5 | Auto-cleanup branch on Phase A halt | Right now founder must `git branch -D` manually. Policy: only auto-cleanup if branch has 0 commits ahead of base. | 30 min |
| NTH-6 | Test plan compliance check | Parse pytest output, count tests per category, verify against spec's `autopilot:test_plan`. Today: trust Codex. | 1-2h |
| NTH-7 | Tracker row auto-create if missing | Currently warns + skips. For new features not yet in tracker. | 30 min |
| NTH-8 | Cross-feature parallel orchestration | Wrap orchestrator in shell loop or add `autopilot run --parallel` for ≤2 concurrent features. | 1-2h |
| NTH-9 | mypy strict extension to `tools/autopilot/` | Type discipline on orchestrator itself. Currently 0 enforcement. | 1-2h |
| NTH-10 | Spec migration helper — `autopilot migrate-spec <feature>` adds template blocks via prompted Claude | Speed up migration of remaining 16 specs. | 1-2h |

---

## 5. Known design decisions (locked, do not re-debate)

These were decided during scaffold; each is documented at the relevant module / memory note.

1. **Auto-merge is OFF by default. Opt-in via explicit `--auto-merge` flag, only after pilot maturity.**
   - v0.1.x default: `auto_merge=False` (safe-by-default, per Blocker #5 implementation).
   - First 3 successful pilots: never pass `--auto-merge`. Orchestrator stops at READY phase, founder manually squashes.
   - After 3 clean pilots, founder MAY pass `--auto-merge` — but only for **P2 low-risk features** (see §6.5 risk class policy).
   - **NEVER** auto-merge P0/P1 risk features regardless of pilot maturity. CLI should warn (and refuse if risk_tier in spec is P0/P1) when `--auto-merge` is passed.
   - Original "hoàn chỉnh = đến main" intent is preserved as the eventual goal; safe default + opt-in is the correct pattern for an unproven tool.
2. **All mutating git operations must happen in the local terminal-controlled repo.**
   - No sandbox / Cowork session may run autopilot or perform merge operations.
   - The orchestrator may perform git ops only from this local terminal context.
   - Per Wave 0 lesson #1: sandbox + terminal git authorities don't mix. The orchestrator IS the terminal authority for autopilot runs.
3. **Codex for review only, Claude for codegen** (per Wave 0 lesson #3). Same-model self-review has blind spots — cross-model review is non-negotiable.
4. **Single-feature serial by default**. Cross-feature parallel deferred (NTH-8).
5. **Manual circuit-breaker resolution.** When breaker fires, founder reads halt-report.md, decides, runs `autopilot resume`. No auto-recover.
6. **Spec gap = block, not warn.** OPEN gaps in `autopilot:gaps` block fail lint. Forces lock-before-autopilot per Wave 0 lesson #2.

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| `claude -p` doesn't auto-commit | High | High (blocker #1) | Probe early in worktree; orchestrator-side fallback commit |
| `claude -p` is single-shot, can't do long task | Medium | High (blocker #2) | Verify `claude --help` for `--max-turns` flag in probe; if absent → Option A chunked prompts (decision-locked, see Blocker #2); SDK rewrite deferred to NTH |
| Codex review parser misses new output shape | Medium | Medium | Save raw to artifact; manual inspect on parse-empty |
| Claude codegen hits Anthropic rate limit | Low | Medium | Retry with backoff (not yet implemented) |
| Auto-merge lands semantically wrong but test-green code | **Medium** | **Critical** | (1) first 3 pilots use default no-merge behavior; never pass `--auto-merge`; (2) manual diff review; (3) no auto-merge for P0/P1 risk classes; (4) post-merge smoke checklist; (5) revert command pre-documented (see §7.5). Verify gate G1 only catches syntax/test failure, NOT wrong product behavior. |
| State file corruption mid-run | Low | Medium | **Blocker #4** (promoted from NTH-4) — atomic temp+rename write |
| Codex flags hallucinated arch issue → false halt | Low | Low | Founder reviews halt-report; resume after dismiss |
| Cost runaway (Codex $$$) | Very Low for first pilot (single feature, ~3 rounds = ~$2-5); Medium when parallel multi-feature runs | Low | NTH-3 cost cap (defer until parallel) |

## 6.5. Risk class policy (which features can use what)

This table defines what a feature is allowed to do under the orchestrator. Founder classifies each feature in its `autopilot:meta` block (`risk_tier: P0|P1|P2`) before linting.

| Class | Examples | Autopilot codegen? | Auto-merge? |
|-------|----------|:------------------:|:-----------:|
| **P0** — forbidden for autopilot | F02 transaction capture, F08 funding sources resolver, F06 pricing/billing, F10 payment, F11 admin auth, anything touching auth/token/security/tenant-foundation/consent/privacy | ❌ Mode 4 manual only | ❌ Never |
| **P1** — autopilot allowed, auto-merge disabled | F-onboarding, F07 (Settings) (touches schema), F09 scheduled jobs, F-categorization (state machines, external integrations, DB-backed feature logic) | ✅ With circuit breakers | ❌ Manual merge only |
| **P2** — autopilot allowed, auto-merge after pilot maturity | F-i18n (after cleanup), F-admin-tools (read-only), copy/UX strings, report formatting, docs-assisted code | ✅ | ✅ Only after ≥3 successful P1 pilots |

**Mapping for current Wave 1+ features:**

- F07 (Settings) (first pilot): **P1-lite** — touches `users` table extension. Autopilot allowed, manual merge required.
- F-i18n: **P2** when cleaned up. But first pilot of orchestrator on it (if chosen) treated as P1.
- F-onboarding: **P1** — token in `/start` payload, state machine.
- F-admin-tools (F11a auth framework): **P0** — auth surface.
- F02 / F08 / F06 / F10 / F11b: **P0** — never autopilot.

If a feature's risk_tier doesn't match its actual surface (e.g. someone tags F02 as P2 to bypass), spec lint should reject (NTH: add risk-tier sanity check that flags features touching `auth/token/billing/transactions/funding_sources` modules in `BE/feature-X-tech.md` if marked < P0).

---

## 7. Test bed plan for first pilot

### 7.0. Success criteria — define BEFORE running

Apply this 3-tier classification AFTER pilot ends. Don't redefine mid-flight.

| Tier | Definition | Action after |
|------|------------|--------------|
| **FULL** | Phase A→D completed without halt (orchestrator stops at READY because `--auto-merge` is not passed per Decision #1); branch reaches `READY_FOR_MANUAL_MERGE`; ≥2 consecutive clean Codex rounds; verify all 5 steps green; CHANGELOG entry exists; founder manually reviews diff, manually runs `git merge --squash` + commit; post-merge tests pass; smoke checklist (§7 step 8) all checked. | Document run as "successful pilot 1/3" toward auto-merge unlock criteria. |
| **PARTIAL** | Phase A→C reached but halted at D gate (e.g. CHANGELOG missing), OR halted mid-C with founder-resolvable finding (manual fix → continue manually). Code is usable; just couldn't reach READY automatically. | Document what halted; do NOT count toward unlock. Identify pattern (gate too strict? Codex finding type unhandled?). |
| **FAIL** | Halted Phase A (codegen unusable), OR halted Phase B (verify fail with un-fixable code), OR Codex flagged P0 architectural finding requiring redesign, OR same finding recurred 2+ times. | Document halt-report; revert any branch; revisit Blocker #1/#2 assumptions. |

**Note:** Phase E (auto-merge) does NOT execute during pilot per Decision #1 + Blocker #5. Even FULL tier ends with founder manually squash-merging — that's by design, not a partial.

When Blockers #1–#5 are resolved, run F07 (Settings) pilot in this sequence:

```bash
# 0. Confirm clean state
cd /Users/maingocanh/Projects/MyMoneyWent
git status                                  # clean
git log --oneline -1                        # 839cb24 or later

# 1. Lint (must be 0 warnings post-migration)
python -m tools.autopilot lint F07

# 2. Preflight (all 6 checks PASS)
python -m tools.autopilot preflight

# 3. Smoke run with eyes-on observation (NOT walk away)
python -m tools.autopilot run F07 2>&1 | tee /tmp/autopilot-pilot-1.log
# Default behavior: NO auto-merge (safe by default per Blocker #5).
# `--auto-merge` is opt-in only after pilot maturity AND feature is P2 (per §6.5).
# For first 3 pilots: never pass --auto-merge.

# Watch for:
# - Phase A: claude codegen starts? produces commits?
# - Phase B: verify all 5 steps pass?
# - Phase C round 1: Codex finds issues? auto-fix loop runs?
# - Phase D: pre-merge gates evaluated correctly?
# - READY: orchestrator stops before merge and writes ready-report.md?
#   (Phase E does NOT execute — `--auto-merge` must NOT be passed during pilot.)

# 4. If halted at any phase:
cat .autopilot/state/F07/halt-report.md
cat .autopilot/state/F07/codex/round-*.txt
# Diagnose, fix, decide: resume vs abort

# 5. PILOT: orchestrator MUST stop at READY phase.
# Default no-merge behavior is mechanically enforced via Blocker #5 implementation.
# If orchestrator attempts Phase E during pilot → ABORT immediately:
# Blocker #5 implementation is wrong; do not proceed with pilot.

# 5a. Manually inspect tracker diff (NTH-7 not yet built)
git diff docs/implementation-tracker.md

# 5b. Manually verify branch state
git log --oneline main..feat/F07-settings
git diff --stat main..feat/F07-settings

# 5c. Run Codex one final audit round (cheap insurance)
codex review --base main

# 6. If founder approves merge:
git checkout main
git merge --squash feat/F07-settings
git commit -m "F07: Settings — locale + tz + recap toggle"
git branch -D feat/F07-settings

# 7. Verify on main
git log --oneline -3
git diff HEAD~1                             # changes look right
pytest tests/                               # all green

# 8. Post-merge smoke checklist (mandatory for first 3 pilots)
#    - [ ] App boots with new schema (alembic upgrade head locally)
#    - [ ] /settings command responds in TG (manual smoke)
#    - [ ] User locale change actually changes message language
#    - [ ] No regression on /status, /today, /weekly
#    - [ ] Sentry dashboard clean for 1h IF deployed; otherwise N/A with reason in summary.md
```

Document EVERY anomaly observed during pilot. Update this plan + `wave0-retrospective.md` post-pilot lessons section.

## 7.5. Rollback / revert protocol (mandatory if pilot ships bad code)

```bash
# If pilot merges code that breaks something post-merge:
git checkout main
git pull
git revert <merge_sha>                     # produces revert commit
pytest tests/                              # verify revert is clean
git push

# If revert itself conflicts (e.g. follow-up commits depend on revert target):
git revert --no-commit <merge_sha>
# resolve conflicts manually
git commit -m "revert: F07 due to <reason>"
git push
```

**Required state artifacts retained per pilot run** (so revert decisions are forensic-grade):

- `feature_id`
- `branch` name
- `merge_commit_sha`
- `pre_merge_head_sha` (= state.initial_head_sha; reference point for "what was main before")
- All Codex round artifacts (`.autopilot/state/<feature>/codex/round-NN.txt`)
- Verification logs (`.autopilot/state/<feature>/verify-N.log` once verify logging is implemented; Claude codegen logs are mandatory via Blocker #1)
- Halt report if any (`halt-report.md`)

**Preservation policy** (resolves the `.gitignore`-vs-"committed" tension):

- `.autopilot/` IS gitignored (per §1.1) — raw state stays out of git history.
- After each pilot run, founder runs:

  ```bash
  mkdir -p docs/operations/pilot-runs/F07-2026-05-14
  cp .autopilot/state/F07/state.json    docs/operations/pilot-runs/F07-2026-05-14/
  cp -r .autopilot/state/F07/codex/     docs/operations/pilot-runs/F07-2026-05-14/codex/
  [ -f .autopilot/state/F07/halt-report.md ] && \
    cp .autopilot/state/F07/halt-report.md docs/operations/pilot-runs/F07-2026-05-14/
  # Then write a 1-page summary.md (founder-authored, what happened + lessons)
  $EDITOR docs/operations/pilot-runs/F07-2026-05-14/summary.md
  git add docs/operations/pilot-runs/F07-2026-05-14/
  git commit -m "docs(pilot): F07 run 2026-05-14 forensic snapshot"
  ```

- **Do NOT commit** raw secrets / `.env` / verify logs containing credentials. Strip before snapshot if necessary.
- Snapshot retained ≥30 days post-merge in git. `.autopilot/state/F07/` itself can be deleted anytime after snapshot.

**Without rollback protocol, auto-merge policy is incomplete.** Even with default no-merge discipline for first 3 pilots, founder must know how to revert manually.

---

## 8. What this plan replaces

Before this doc, the orchestrator status was scattered across:

- `automation-state.md` §3 (Codex tier — still authoritative)
- `wave0-retrospective.md` (Wave 0 lessons — still authoritative)
- `Level 3 template` (paste-prompt predecessor — superseded by orchestrator for normal use)
- Memory note `project_wave0_complete.md` (Wave 0 final state)

This plan is the **single source of truth for orchestrator status** going forward. Update at end of each pilot run + when blockers resolve.

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v0.1.0 | 2026-05-12 | Initial plan post-scaffold-merge (commit 839cb24). 2 P0/P1 blockers + 1 spec-migration blocker identified before first pilot. F07 (Settings) selected as first pilot target. 10 nice-to-have improvements deferred. |
| v0.1.1 | 2026-05-12 | Critical revisions per founder review: (a) auto-merge default downgraded — first 3 pilots must run `--no-auto-merge`; (b) auto-merge risk likelihood corrected from "Very low" to Medium with semantic-wrong wording + 5 mitigations; (c) F07 (Settings) reclassified P1-lite (schema change ≠ pure low-risk) + tenant isolation test mandatory; (d) Blocker #1 probe rewritten to use throwaway worktree (never on real repo); (e) decision #2 wording clarified (mutating git ops on local terminal only); (f) added §6.5 risk class policy (P0/P1/P2 with feature mapping); (g) added §7.5 rollback / revert protocol with required state artifacts; (h) §1.2 noted unit-scope-only test validation + Codex parser fixture audit gap. |
| v0.1.2 | 2026-05-12 | Round 2 revisions: (A) added §7.0 success criteria FULL/PARTIAL/FAIL 3-tier definition; (B) Blocker #2 decision-locked — Option A (chunked prompts) is default if probe shows single-shot, Option C SDK rewrite deferred to NTH; (D) added cost estimate ~$2-5 per pilot under "Total ETA"; (E,F,G) naming consistency F07 (Settings) throughout; CLI examples use `lint F07` (resolves via meta block once Blocker #3 done); promoted state.json atomic write from NTH-4 to **Blocker #4** (15 min mandatory pre-pilot); cost-runaway risk likelihood downgraded to Very Low for first pilot, Medium for parallel runs; added `claude --max-turns` flag check to Claude CLI risk mitigation (typo from prior draft). |
| v0.1.3 | 2026-05-12 | Round 3 revisions enforcing pilot policy mechanically: (1) **Blocker #5 added P0** — implement `--no-auto-merge` flag (45-60 min) before first pilot; without it, Decision #1's "no auto-merge for first 3 pilots" is unenforceable. (2) §7.0 FULL tier rewritten — Phase A→D + manual squash by founder, NOT A→E (Phase E auto-merge does not run during pilot). (3) §3 F07 table fixed contradiction — Architectural surface "Medium-low (users table extension)" + concurrent test category applies (settings updated mid-recap-fire). (4) §7.5 artifact preservation policy clarified — `.autopilot/` stays gitignored, founder snapshots to `docs/operations/pilot-runs/F07-YYYY-MM-DD/` after each pilot for ≥30d retention. Polish: ETA wording "auto-merge attempt" → "manual-merge pilot"; smoke checklist Sentry "if deployed otherwise N/A"; v0.1.2 typo "Codex CLI" → "Claude CLI". |
| v0.1.4 | 2026-05-12 | Round 4 consistency tightening: (1) §7 watch list "Phase E: squash-merge succeeds?" → "READY: orchestrator stops before merge?" (Phase E does not run in pilot). (2) §7 step 5 "for now manual confirmation" → "orchestrator MUST stop at READY; if Phase E attempted → ABORT, Blocker #5 wrong" (no more "for now" since Blocker #5 now P0). (3) **Inverted CLI flag default** — was `--no-auto-merge` opt-out with `auto_merge=True` default, now `--auto-merge` opt-in with `auto_merge=False` default (safer for unproven tool). Decision #1 + Blocker #5 + TL;DR + §7 example all aligned. CLI prints warning + refuses if `--auto-merge` passed for P0/P1 risk_tier feature. |
| v0.1.5 | 2026-05-12 | Round 5 terminology cleanup after safe-default merge inversion: current sections now consistently describe `--auto-merge` as opt-in, default no-merge behavior for pilots, Blockers #1–#5 as pre-pilot requirements, and Phase A→D + READY as the pilot validation target. Historical changelog rows retain prior `--no-auto-merge` wording only as history. |
| v0.1.6 | 2026-05-12 | Consistency cleanup: header version bumped from v0.1.0 to v0.1.6 current marker; §1.1 Codex parser wording aligned with §1.2 synthetic-fixture-only validation; TL;DR ETA updated to half-day/full-day after Blockers #1–#5; NTH-2 folded into Blocker #1; §1.3 resume wording clarified (happy-path INIT→READY first, HALTED resume still untested). |
| v0.2.0 | 2026-05-12 | Pre-pilot Blockers #1-#5 resolved via Mode 3 batch autopilot run (squash commit `5a35dcb` on main). 4 rounds of Codex cross-model P1 fixes integrated as regression tests (r1: returncode-guard fallback commit, r2: `--no-verify` so pre-commit-blocked fallback succeeds, r3: exit code 5 for declined `--auto-merge` confirm, r4: P2-only allow-list — malformed/missing risk_tier fails closed). G3 closed to option (b): `display_suffix VARCHAR(8)` column ships in separate `feat/webhook-display-suffix-migration` PR (W0.8) before F07 pilot. 215 tests pass; all hooks green. F07 pilot unblocked once W0.8 migration lands. |
| v0.2.2 | 2026-05-13 | Tooling hardening: 6 code fixes + 1 doc + 1 diagnostic workaround surfaced across F07 (4 sessions) and v0.2.1 (3 sessions) cumulative pilot signal. (1) `max_review_rounds` 3 → 5 with new `confirmation_rounds_after_last_fix=2` knob — decouples post-fix confirmation tail from total budget; old math `max=3 + clean=2 consecutive` couldn't ship when adjacent micro-findings cascade. (2) `SECURITY_FINDING` keyword tiering — severe keywords (`auth bypass`, `injection`, `csrf`, `xss`, `ssrf`, `rce`, `timing attack`, `*-leak`) always HALT; soft keywords (`token`, `secret`, `hmac`, `auth`, ...) require P0/P1 severity. Stops benign Markdown-rendering findings from auto-tripping security halt (F07 v0.2.1 R1 false-positive). (3) Resume syncs git checkout to `feature_state.branch` regardless of phase — fixes empty-diff codex review when caller is on `main`. (4) `tracker.update_status` no-op on feature branches — eliminates noise commits during Phase C fix flow. (5) `state.load` tolerates unknown fields with warning — cross-version safety, fixes brick on `last_active_phase` schema add. (6) `codex.save_review_artifact` non-clobber via `-resume{N}` suffix — preserves forensics across resume cycles. Plus: `codex.run_review` logs warning when output references SHA ≠ HEAD (stale-blob detection; true fix v0.2.3 backlog). `docs/autopilot/orchestrator-usage.md` documents the one-session-per-repo policy (validated during v0.2.2 work itself when a parallel session hijacked HEAD mid-commit). 277 tests pass; all hooks green. F07 resume unblocked next session. |
