# Autopilot Orchestrator — Usage

> **Version:** v0.1.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active (initial release)
> **Owner:** Founder (dev)
> **Mục đích:** Single-command full-auto execution of one feature spec, từ code-gen → test → Codex review → fix loop → CHANGELOG → tracker → squash-merge vào main. Zero touch nếu spec đã lock + circuit breaker không trip.
> **Tham chiếu:**
> - [development-workflow.md](./development-workflow.md) — manual 10-step workflow (orchestrator codifies it)
> - [automation-state.md](./automation-state.md) — automation primitives inventory
> - [wave0-retrospective.md](./wave0-retrospective.md) — 7 lessons (orchestrator design embeds them)
> - [Level 3 template](../prompts/level3-autopilot-template.md) — paste-prompt predecessor

---

## TL;DR

```bash
# One feature, end-to-end, từ main → main:
python -m tools.autopilot lint F-i18n      # validate spec; close gaps if errors
python -m tools.autopilot preflight        # env + git checks
python -m tools.autopilot run  F-i18n      # walk away
```

If circuit breaker trips → read `.autopilot/state/F-i18n/halt-report.md`, fix manually or via Claude Code session, then:

```bash
python -m tools.autopilot resume F-i18n
```

## Mental model

The orchestrator is a Python harness around 3 external CLIs:

1. **`claude` CLI** — does code-generation and targeted fixes (Phase A + Phase C fix step).
2. **`codex` CLI** — cross-model review (Phase C review step).
3. **Local toolchain** — ruff, black, mypy, lint-imports, pytest (Phase B verify + Phase E pre-merge gate).

The orchestrator's job is the glue: state checkpoint, loop control, parsing, circuit breakers, tracker updates, merge gates.

```
spec → [LINT] → [PREFLIGHT] → [A: codegen] → [B: verify] → [C: review/fix loop] → [D: gates] → [E: merge to main]
                                  claude         pytest         codex+claude          all checks    git squash
```

## Phases (what the loop does)

| Phase | Module | Action | Exit on success |
|-------|--------|--------|-----------------|
| INIT  | `preflight` + `spec_lint` | Validate env, git on main + clean, spec linted, BE doc paired, gaps closed, test plan present | state.phase = INIT |
| A: CODEGEN | `claude_codegen.run_codegen` | `claude -p "<prompt>"` writes initial commits on `feat/<id>-<short>` branch | state.phase = CODEGEN |
| B: VERIFIED | `verify.run_all` | ruff + black + mypy + lint-imports + pytest. ALL must pass. | state.phase = VERIFIED |
| C: REVIEWING | `codex.run_review` → `circuit_breaker.evaluate` → `claude_codegen.run_fix` → `verify.run_all` | Loop up to `max_review_rounds` (default 3). On clean, count `consecutive_clean_rounds` until `required_clean_rounds_before_merge` (default 2). | state.phase = READY |
| D: READY | `merge.attempt_merge` (gate phase) | Verify all 5 steps green + 2 consecutive clean rounds + CHANGELOG entry exists + branch ahead of main + dry-run merge clean | (continues to E) |
| E: MERGED | `merge.attempt_merge` (action phase) | `git checkout main && git merge --squash <branch> && git commit -m "<id>: <title>"` + delete branch | state.phase = MERGED |

## CLI commands

```bash
python -m tools.autopilot lint <feature_id>
python -m tools.autopilot preflight
python -m tools.autopilot run <feature_id> [--auto-merge]
python -m tools.autopilot resume <feature_id> [--auto-merge]
python -m tools.autopilot status <feature_id>
python -m tools.autopilot abort <feature_id>
```

Exit codes: `0` success, `1` verify fail, `2` preflight fail, `3` circuit broken, `4` bad args (or `--auto-merge` mechanically refused for P0/P1 spec), `5` user declined `--auto-merge` confirmation prompt.

### `--auto-merge` flag (Blocker #5, plan v0.1.6 §2)

**Default behavior (NO `--auto-merge` flag) is safe-by-default.** The orchestrator stops at the `READY` phase, writes `.autopilot/state/<feature>/ready-report.md`, and exits 0. Founder reviews the diff and squash-merges manually per the report's "Suggested merge" block. Phase E is never invoked.

Pass `--auto-merge` to enable Phase E auto squash-merge. The CLI:

1. Looks up the feature's `risk_tier` in its `<!-- autopilot:meta -->` block.
2. If `risk_tier ∈ {P0, P1}` (or meta block missing — treated as P1) → prints an error and exits with code 4. Plan §6.5 forbids auto-merge for P0/P1 regardless of pilot maturity.
3. If `risk_tier == P2` → prints a warning and prompts for `y/N` confirmation on stdin. Aborts on anything other than `y`/`yes`.
4. Only after that gate does the loop reach `merge.attempt_merge`.

**For the first 3 pilots (F07 included): NEVER pass `--auto-merge`.** The READY behavior is the validated pilot path.

## Spec requirements (what `lint` checks)

**Required (errors block autopilot):**

- FE spec at `docs/features/feature-<name>.md` with sections: 1.Mô tả, 2.Use Cases, 10.Acceptance Criteria, Changelog.
- BE tech doc at `docs/features/BE/feature-<name>-tech.md` with sections: 1.Implementation Overview, 5.Testing Plan, Changelog.
- Acceptance Criteria has ≥3 testable items.
- No TODO|TBD|FIXME|XXX|??? in Acceptance Criteria, Use Cases, API, or Domain Model sections.
- If `<!-- autopilot:gaps -->` block present → 0 OPEN gaps (all CLOSED or DEFERRED:<location>).
- If `<!-- autopilot:test_plan -->` block present → all 5 categories listed (each populated or `N/A — <reason>`).

**Optional (warnings only):**

- `<!-- autopilot:meta -->` block (recommended for branch derivation).
- `<!-- autopilot:gaps -->` block (recommended; mandatory in spirit per Wave 0 lesson #2).
- `<!-- autopilot:test_plan -->` block (recommended; mandatory in spirit per Wave 0 lesson #4).

See `docs/operations/spec-template.md` for the canonical template.

## Circuit breakers (10 conditions that halt autopilot)

| # | Code | Trigger |
|---|------|---------|
| 1 | `ARCH_FINDING` | Codex finding contains arch keyword (schema, design, refactor, contract, breaking change) |
| 2 | `SECURITY_FINDING` | Codex finding contains security keyword (auth, token, hmac, injection, etc.) |
| 3 | `CONCURRENCY_FINDING` | Codex finding contains race/lock/transaction (allowed if just retry/idempotency) |
| 4 | `RECURRING_FINDING` | Same finding hash flagged after a fix attempt (lesson #4: don't loop on bad fix) |
| 5 | `MAX_ROUNDS` | Hit `max_review_rounds` (default 3) without 2 consecutive clean rounds |
| 6 | `VERIFY_REGRESSION` | Local verify fails after a fix commit (don't push known-broken code) |
| 7 | `TYPE_IGNORE_PROPOSED` | Codex suggests `# type: ignore` (founder OK required) |
| 8 | `SECRETS_FINDING` | detect-secrets keyword in Codex output |
| 9 | `CODEGEN_FAILED` | claude CLI returned non-zero or zero new commits |
| 10 | `MERGE_GATE_FAIL` | Pre-merge gate failed (verify/CHANGELOG/conflict) |

When a breaker fires:
- State JSON saved at `.autopilot/state/<feature>/state.json` with phase = `HALTED`.
- Forensic report at `.autopilot/state/<feature>/halt-report.md`.
- Codex round artifacts at `.autopilot/state/<feature>/codex/round-NN.txt`.
- Tracker row updated to ❌ blocked.
- Process exits with code 3.

## Resume flow

```bash
# After founder fixes the halt cause (manually or via interactive Claude Code):
git status                                  # confirm fix is committed
python -m tools.autopilot resume F-i18n     # continues from saved phase
```

`resume` reads `state.json`, skips already-completed phases, and re-enters the loop at the next pending phase. Branch state must be intact.

## Pre-merge gate detail (Phase D)

Auto-merge will NOT proceed unless ALL of these hold:

1. `verify.run_all()` returns `ok=True` (5/5 steps green).
2. `state.consecutive_clean_rounds >= cfg.required_clean_rounds_before_merge` (default 2).
3. `CHANGELOG.md` was modified between `state.initial_head_sha` and current HEAD.
4. Branch has ≥1 commit ahead of `main`.
5. Dry-run `git merge --squash --no-commit <branch>` against `main` succeeds (no conflicts).

If any fail → `MERGE_GATE_FAIL` halt with the specific gate listed.

## State + artifacts directory layout

```
.autopilot/state/
└─ F-i18n/
   ├─ state.json                # phase, round, hashes, branch
   ├─ halt-report.md            # iff phase == HALTED
   └─ codex/
      ├─ round-01.txt           # raw Codex stdout (for forensics)
      ├─ round-02.txt
      └─ round-03.txt
```

This dir is gitignored (`.autopilot/`). Safe to delete to start a feature fresh.

## Configuration via env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `AUTOPILOT_REPO_ROOT` | git rev-parse --show-toplevel | Override repo root |
| `AUTOPILOT_CODEX_BIN` | $(which codex) or known Mac install path | Override Codex CLI path |
| `AUTOPILOT_CLAUDE_BIN` | $(which claude) | Override Claude CLI path |

Tunable knobs (in `Config` dataclass — currently no env override; edit if needed):
- `max_review_rounds = 3`
- `required_clean_rounds_before_merge = 2`
- `max_local_verify_retries = 2`

## When NOT to use

Per Level 3 template § "When NOT to use Level 3" — orchestrator inherits same constraints:

- **Wave 0-style foundation** → use Mode 3 batch (manual founder review every PR).
- **Security-critical features** (F10 payment, F11 admin auth) → use Mode 4 per-PR strict.
- **Schema-changing migrations** with backfill → manual.
- **First time using a new tool/library** → manual exploration first.

The orchestrator's `risk_tier: high` field in `<!-- autopilot:meta -->` SHOULD be respected by future versions to refuse autopilot — currently advisory.

## Anti-patterns (NEVER do)

- Run `autopilot run` without first running `autopilot lint` (waste cycles).
- Run while another branch is checked out (preflight catches but worth knowing).
- Merge halt state manually then re-run `autopilot run` (wipes state) — use `resume` or `abort` first.
- Disable circuit breakers to "save time" (lesson #4 — bug fix introduces new bugs).
- Run on Wave 0-style foundation features (lesson #3 — same-model self-review blind spots).

## Failure recovery

If autopilot leaves the branch in a broken state (e.g. crash mid-fix):

```bash
# Inspect what was done
git log --oneline main..feat/<feature>
git diff --stat main..feat/<feature>

# Option A: continue manually from current state (recommended)
git checkout feat/<feature>
# fix things by hand or use claude code interactively
git commit -m "fix: ..."
python -m tools.autopilot resume <feature>

# Option B: abandon branch + restart from main
git checkout main
git branch -D feat/<feature>
rm -rf .autopilot/state/<feature>/
python -m tools.autopilot run <feature>
```

## Cross-references

- Spec template: [spec-template.md](./spec-template.md), [spec-template-be.md](./spec-template-be.md)
- Manual workflow (when not using autopilot): [development-workflow.md](./development-workflow.md)
- Wave 0 lessons (codified into orchestrator): [wave0-retrospective.md](./wave0-retrospective.md)
- Level 3 paste-prompt predecessor: [../prompts/level3-autopilot-template.md](../prompts/level3-autopilot-template.md)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v0.1.0 | 2026-05-12 | Initial release. Python orchestrator (`tools/autopilot/`), spec template + linter, 10 circuit breakers, auto-merge with strict pre-merge gates per "hoàn chỉnh = đến main" decision. |
