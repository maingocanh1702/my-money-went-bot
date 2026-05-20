# CLAUDE.md

Guidance for Claude Code sessions working in this repo. **Read top-to-bottom on every fresh session.** For deeper context, follow the pointers — don't duplicate them here.

## What this repo is

**MyMoneyWent** is a multi-tenant personal finance bot with a **dual-market strategy**:

- 🇻🇳 **VN (primary):** Tiền Về Nơi Đâu — SePay webhook + bank email parsing, Telegram/Discord/Messenger/Zalo channels.
- 🌐 **Global (parallel, validation phase):** My Money Went — Plaid/TrueLayer + e-commerce platform APIs.

FastAPI backend, Python 3.11+, Postgres (asyncpg + SQLAlchemy 2.x async), Alembic migrations. Deployed on Railway via nixpacks. Phase 1 ~75% complete; Wave 0 shipped (118 tests, 5 import-linter contracts).

**Read first:** [`docs/START_HERE.md`](docs/START_HERE.md) — current PR, source-of-truth rules, next tasks.

## Source of truth — DO NOT duplicate these

| What | Canonical file |
|------|----------------|
| Current PR / next task | `docs/implementation-tracker.md` |
| Phase timeline + % | `docs/mymoneywent-roadmap.md` |
| Per-feature plan | `docs/implementation-plans/phase-*.md` |
| Feature spec (FE) | `docs/features/feature-<name>.md` |
| Feature spec (BE) | `docs/features/BE/feature-<name>-tech.md` |
| **3-lane risk-based workflow** | `docs/operations/fast-quality-workflow.md` |
| 10-step per-feature workflow (Standard/Foundation) | `docs/operations/development-workflow.md` |
| **Manual fallback (Codex down / autopilot halt)** | `docs/operations/manual-fallback-playbook.md` |
| Autopilot orchestrator | `docs/autopilot/orchestrator-usage.md` |
| Autopilot prompt skeleton | `docs/autopilot/autopilot-prompt-template.md` |
| ADRs | `docs/adr/` |

Auto-generated views (never hand-edit, rebuild via `scripts/build-dashboard.py`): `docs/dashboard.{html,md,json}`.

## Layout

```
core/         # multi-tenant business logic (NEW code goes here)
markets/
  vn/         # VN-specific: capture/sepay_webhook, capture/webhook_tokens,
              #              email_parsers/{acb,bidv,cake,mb}.py
  global_/    # Global placeholder (Phase 2+)
handlers/     # ⚠️ LEGACY single-tenant — do NOT add new code here
i18n/         # pure language packs — no app imports
tools/
  autopilot/  # orchestrator (Mode 3/4 walkaway runner)
scripts/      # build-dashboard, sync-tracker-from-gh, autopilot_runner, …
migrations/   # Alembic
tests/        # pytest + testcontainers (real Postgres for integration)
```

**Legacy files at repo root** (`main.py`, `sheets.py`, `telegram_api.py`, `config.py`) and `handlers/*.py` are single-tenant remnants. **Don't extend them** — new code lives in `core/` + `markets/`. Legacy cutover is scheduled for Phase 2 F02.

## Common commands

```bash
# Setup (once per machine / .venv)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
pre-commit install

# Test
pytest tests/ -v --tb=short
pytest tests/path/test_x.py::test_name   # single test

# Lint / format (pre-commit runs all of these)
pre-commit run --all-files
ruff check .                 # lint + import sort
ruff check --fix .
black .
mypy core markets i18n tests

# Import boundary contracts (ADR-0001)
lint-imports

# Autopilot — single-feature walkaway runner
python -m tools.autopilot lint <feature-id>       # validate spec
python -m tools.autopilot preflight               # env + git
python -m tools.autopilot run <feature-id>        # walk away
python -m tools.autopilot resume <feature-id>     # after halt

# Dashboard (auto-rebuilt by pre-commit when tracker changes)
python scripts/build-dashboard.py
```

## Quality gates (CI-enforced, blocking)

`.github/workflows/ci.yml` runs on every PR + push to `main`:

1. **pre-commit** — ruff, black (with `force-exclude` for legacy), mypy strict on `core|markets|tests/`, detect-secrets (baseline `.secrets.baseline`), import-linter, dashboard auto-rebuild.
2. **`lint-imports`** — enforces ADR-0001 + 4 other contracts (see below).
3. **`pytest tests/`** — testcontainers spins up real Postgres; tenant isolation test is **mandatory** for any feature that touches DB.

`.github/workflows/pr-validate.yml`:

4. **Branch name** must match `^[a-z0-9-]+/MYM-[0-9]+-[a-z0-9-]+$` (e.g. `feat/MYM-123-funding-sources`). Exempt: `W0.*`, `Wave-*`, `hotfix/*`, `release/*`.
5. **PR body** must contain `Closes MYM-NNN`, `Fixes MYM-NNN`, `Ref MYM-NNN`, or `Linear: N/A`.

## Import boundary contracts (`.importlinter`)

These are the architectural guardrails — violating them fails CI even if tests pass:

- `core/` **MUST NOT** import from `markets/` (ADR-0001). One whitelisted exemption: `core.handlers.start → markets.vn.capture.webhook_tokens`.
- `markets/vn` ↮ `markets/global_` — no cross-market imports.
- `markets/vn/email_parsers/` **MUST be pure**: no `core.db`, no `core.messenger`. Parsers return data; orchestration lives in `markets/vn/capture/`.
- `i18n/` **MUST be pure data**: no imports from `core | markets | handlers`.

If you need to bridge `core ↔ markets`, the only legal place is `core/handlers/` (multi-tenant handler layer, strangler-fig replacement for legacy top-level `handlers/`). Add the new bridge as an `ignore_imports` line in `.importlinter` explicitly — no wildcards — so it surfaces in PR review.

## Git & commit policy

- **Branch:** `<type>/MYM-<id>-<slug>` per `pr-validate.yml`.
- **1 feature = 1 branch = 1 PR.** Squash-merge into `main`.
- **Conventional Commits** subject style (no enforced commitlint here, but kept by convention).
- **Don't bump spec version on in-session review iterations** — see memory `feedback_spec_versioning.md`.
- **Pre-push hook:** `make install-hooks` symlinks `scripts/git-hooks/pre-push.sh` into `.git/hooks/`. Run once after clone.

## Hard rules — read every session

1. **STRICT 1 Claude Code session per `.git/` directory.** F07 saga had 3 ref-clobber incidents. Tool-level enforcement: `tools/autopilot/lock.py` acquires `.autopilot/locks/<repo-hash>.lock` at `run`/`resume`; conflict returns exit code 6. Pre-flight check: `ls .git/*.lock` must be empty. For parallel feature work, use `git worktree add ../MyMoneyWent-<slug> <branch>` — each worktree gets its own checkout AND its own lock.
2. **NEVER auto-delete `.md` files.** Any destructive op on docs (`git checkout --theirs/ours`, `stash drop`, `restore`, `rm`) → PAUSE and ask founder first. Founder runs multiple sessions in parallel; each may be editing docs concurrently. See memory `feedback_never_auto_delete_docs.md`.
3. **Spec-first.** No code before reading FE spec + BE tech spec. If you find a spec gap, **stop and update the spec** — don't code on assumption. Foundation Lane only; Fast Lane may skip full spec (see [fast-quality-workflow.md §3 Lane 1](docs/operations/fast-quality-workflow.md#lane-1--fast-lane)).
4. **Tenant isolation test is mandatory** for any feature touching the DB. No test → no merge. Applies to all lanes.
5. **Different-model review is mandatory for P1/P0 (Standard/Foundation Lane).** Claude Code writes → Codex reviews. Fast Lane allows tactical self-review ONLY for docs/generated/cosmetic/obvious low-risk changes per the 8-item checklist in [fast-quality-workflow.md §3 Lane 1](docs/operations/fast-quality-workflow.md#lane-1--fast-lane). Self-review code = not allowed for Standard/Foundation.
6. **Auto-merge is opt-in, not default.** P0 forbidden for codegen; P1 manual_only; P2 pilot manual_only; P2 mature opt-in `--auto-merge`. Foundation Lane never auto-merges — founder approval = manual squash + sign-off in PR body confirming acceptance criteria / blast radius / gates / known tradeoffs. See memory `project_autopilot_risk_tier_policy.md`.
7. **Autopilot prompts: single-phase scope is the default.** Mega-prompts (5-6 phases) only with mandatory per-phase checkpoint + halt-if-skipped. See memory `feedback_autopilot_prompt_scope.md` + `feedback_megaprompt_with_checkpoints_works.md`.
8. **Review cap by lane.** Fast: max 2 rounds. Standard: max 5. Foundation: max 8 (founder approval sau 5). Vượt cap → split / manual review / revisit foundation. Không loop vô hạn.
9. **When autopilot/Codex blocked** → follow [manual-fallback-playbook.md](docs/operations/manual-fallback-playbook.md). Don't silently retry; don't bypass quality gates.

## Local environment notes

- **Python 3.11** required (`pyproject.toml`).
- **Postgres** for integration tests — `testcontainers` auto-spins one; needs Docker running locally.
- **`.env`** holds secrets — NEVER commit. Template at `.env.example`.
- **Pre-commit hook installs:** `pip install -e ".[dev]" && pre-commit install` (auto-bootstrapped on first commit otherwise).
- **Tooling pins** (`ruff==0.4.10`, `black==24.4.2`, `mypy==1.10.0`) match pre-commit hook versions exactly — drift causes false-positive `would reformat` locally vs CI.

## Style

- Line length **100** (black + ruff agree).
- mypy **strict** on `core|markets|i18n|tests` only. `tools/autopilot/*` is pragmatic-typed (overrides in `pyproject.toml`).
- Legacy files are listed in both `[tool.ruff].extend-exclude` and `[tool.black].extend-exclude` + `.force-exclude`. **Black needs `force-exclude` separately** because pre-commit passes file paths explicitly, which bypasses `extend-exclude`. See memory `feedback_black_force_exclude_for_precommit.md` if touching this config.
- Naming: `kebab-case` for docs files, `snake_case` for Python.

## External system pointers

- **Linear:** project key `MYM` (workspace `maingocanh`). Tickets `MYM-NNN`. Branch + PR must reference. URL: https://linear.app/maingocanh/team/MYM/all
- **Railway:** prod deploy via `railway.toml` + nixpacks (so runtime deps live in `requirements.txt`, NOT `pyproject.toml`).
- **Sentry, GitHub Actions:** wired via `.github/workflows/*.yml`.

## Memory system

The founder maintains an auto-memory at `~/Library/Application Support/Claude/.../memory/MEMORY.md`. It stores cross-conversation context (Wave 0 decisions, F08 funding-source model, F07 retro, family plan tiers, autopilot lessons, feedback rules). **Check it before re-asking questions the founder has already answered** — it's loaded into Cowork sessions automatically. Don't duplicate memory content into this file; link by memory filename so future-you can look it up.

## When unsure — ask the founder

- Multi-step changes that span more than 2 files or 2 commits → propose plan first (don't `--auto-merge`).
- Anything that touches `docs/adr/`, `.importlinter`, `pyproject.toml` `[tool.*]`, or CI workflows → ask first.
- If you find a docs file that conflicts with what's in your task description → don't resolve unilaterally. The founder may have a parallel session editing it.
