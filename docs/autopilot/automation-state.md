# Automation State — Current Capabilities

> **Date:** 2026-05-12 (snapshot after Wave 0 + W0.7 + Wave 1 phase plans)
> **Status:** Active reference — update each wave end
> **Scope:** Inventory of every automation primitive available right now, when to use which, and what's still manual.
> **Cross-refs:**
> - [development-workflow.md](../operations/development-workflow.md) — 10-step + Wave structure
> - [wave0-retrospective.md](../operations/wave0-retrospective.md) — 7 lessons from Wave 0
> - [execution-prompt-wave0-autopilot.md](./prompts/execution-prompt-wave0-autopilot.md) — Mode 3 batch prompt
> - [level3-autopilot-template.md](./prompts/level3-autopilot-template.md) — Level 3 auto-Codex template

---

## 1. Execution modes (3 available)

| Mode | File | Use case | Founder touch points |
|---|---|---|---|
| **Mode 3 — Batch autopilot** | `docs/autopilot/prompts/execution-prompt-wave0-autopilot.md` | Foundation / chained dependent PRs (proven on Wave 0) | 1 batch review session at end |
| **Mode 4 — Per-PR strict** | `docs/operations/development-workflow.md` §2 (10-step) | Any single PR, manual control | 1 per PR (review + merge) |
| **Level 3 — Auto Codex loop** | `docs/autopilot/prompts/level3-autopilot-template.md` | Independent features (Wave 1+) | ~1 start + 1 merge per feature |

Level 3 is **production-ready but untested**. Parser regex verified against real Codex CLI output 2026-05-11. Recommend F-i18n as first test bed (lowest risk Wave 1 feature).

## 2. Static enforcement (code-as-law)

Cannot be bypassed by accident — failures block commit or CI.

| Tool | Enforces | Configured in |
|---|---|---|
| `import-linter` | 4 boundary contracts (see below) | `.importlinter` |
| `pre-commit` framework | ruff + black + mypy --strict + detect-secrets + import-linter | `.pre-commit-config.yaml` |
| `pytest --strict-markers` + `xfail(strict=True)` | Forces future PR to remove deferred-contract markers | `pyproject.toml` |
| GitHub Actions CI | Re-runs pre-commit + tests on every push/PR | `.github/workflows/ci.yml` |
| `alembic` migrations | Schema constraints (CHECK, UNIQUE, FK) | `migrations/versions/*.py` |
| Dependabot | Auto-bumps deps weekly (currently 7 PRs ❌ — don't merge majors that conflict with pinned pre-commit hooks) | `.github/dependabot.yml` |

**5 active import-linter contracts:**

1. `core` MUST NOT import from `markets` (ADR-0001 strict)
2. `markets.vn` MUST NOT import from `markets.global_`
3. `markets.global_` MUST NOT import from `markets.vn`
4. `markets.vn.email_parsers` MUST NOT import `core.db` or `core.messenger` (Gap 2 parser-purity)
5. `i18n` MUST NOT import `core` / `markets` / `handlers` (i18n purity)

## 3. Codex automation tier

**Verified working 2026-05-11.**

| Capability | Status |
|---|---|
| Codex CLI binary | ✅ `/Users/maingocanh/Library/Application Support/crawbot/nodejs/bin/codex` |
| Non-interactive review | ✅ `codex review --base main` |
| Per-commit review | ✅ `codex review --commit <SHA>` |
| Uncommitted review (pre-commit) | ✅ `codex review --uncommitted` |
| Custom prompt arg | ✅ `codex review --base main "Focus on idempotency"` |
| Auto-apply diff | ✅ `codex apply` (untested) |
| Single-shot prompt | ✅ `codex exec "<prompt>"` |
| Model | `gpt-5.3-codex` (GPT-5 class — strong cross-model coverage) |
| Sandbox | read-only (won't modify files) |
| Approval mode | `never` (non-interactive) |
| Exit code | **0 always** — must parse stdout text |
| Output format | Plain text (no `--json` flag), ~95% noise (preamble + diff dump), ~5% review |
| Parser markers | `codex` line → review verdict → `Review comment(s):` → bullets `- [P1] ... — file:LL-LL` |
| Dedupe needed | ✅ Codex prints review block twice (CLI quirk) |

## 4. Test enforcement automation

| Item | Status |
|---|---|
| 5-category test plan upfront | Process rule (manual but checklisted) — happy / retry / missing-optional / pathological / concurrent |
| testcontainers Postgres | Auto-spin per integration test session (<30s boot) |
| Tenant isolation helper | `tests/conftest.py` — `make_user`, cross-tenant assertion fixtures |
| Deferred-contract pin | `xfail(strict=True)` pattern — F02 funding-source contract pinned now |
| Current test count | 118 passed, 1 skipped, 1 xfail (post-Wave-0 + W0.7) |
| Test layers | Unit (no DB) + Integration (real Postgres via testcontainers) + Contract (parametrized adapter tests) |

## 5. Memory + knowledge automation

| Item | Count / Status |
|---|---|
| Memory notes | 13 (decisions, lessons, scope splits, conventions) |
| Auto-load index | `MEMORY.md` — loaded every future session |
| Workflow doc | `docs/operations/development-workflow.md` — living, updated 4× during Wave 0 |
| Retrospective | `docs/operations/wave0-retrospective.md` — 7 lessons |
| Phase plans | 6 Wave 1 phase plans drafted (PR #10 merged) |
| L3 template | `docs/autopilot/prompts/level3-autopilot-template.md` — ready |
| Implementation tracker | `docs/implementation-tracker.md` — 3-level (roadmap → wave → feature) |

## 6. Decision tree — pick the right mode

```
Feature has security / idempotency / auth surface?
├─ YES → Mode 3 (foundation pattern) OR Mode 4 strict
│        Codex review mandatory every round
│        5-category test plan mandatory
│
└─ NO → simple / UI / copy feature
        └─ Level 3 autopilot acceptable
           Test plan: still 5 categories where applicable
           Codex review still recommended (cheap insurance ~$0.50/review)
```

**Threshold for "needs Codex":** PR touches schema / auth / token compare / idempotency / concurrency / cross-tenant / external integration.

## 7. Productivity gains observed

| Wave | Manual baseline | With current automation | Delta |
|---|---|---|---|
| Wave 0 (foundation, 6 PRs) | ~3-4 days | ~1 day (Mode 3 batch + Codex 4 rounds on W0.6) | ~3-4× |
| W0.7 (cleanup PR) | ~2-3h | ~30 min (Mode 4 + xfail pattern) | ~5× |
| Wave 1 (4 features parallel) — estimated | ~2-3 days | ~3-4h (Level 3 untested) | ~5-6× |
| Wave 2 (F02 + F08, security-critical) — estimated | ~4-5 days | ~1.5-2 days Mode 3 batch | ~2-3× |

**Net:** ~3-5× speedup without sacrificing quality. Codex review = defense layer; static enforcement = continuous safety; xfail pin = mechanical reminder for future PRs.

## 8. Gaps — NOT yet automated (by design or pending)

| Gap | Why | Status |
|---|---|---|
| Auto-fix architectural findings | Architectural decisions need human judgment | **By design — circuit breaker** |
| Auto-merge to main | Final safety gate | **By design — manual retained** |
| Cross-feature dependency tracking | Wave 0 had implicit chain; complex graphs need design | Manual via `implementation-tracker.md` + workflow §4 |
| Test plan generation | `engineering:testing-strategy` skill exists, doesn't auto-invoke | Manual (process rule) |
| Spec gap detection | Founder reads spec, lists gaps | Manual (lesson #2 from Wave 0) |
| Sandbox-Terminal git sync | Different worktrees, unfixable from agent side | Workaround: all git on terminal (lesson #1) |
| Codex JSON output | CLI doesn't support `--json` flag | Text parsing only (works, verified) |
| Multi-feature parallel orchestration | Solo dev cognitive limit = 2 branches | **By design — 2 max recommended** |

## 9. When to update this doc

- End of each Wave → revisit + bump date stamp
- New automation tool/CLI integrated → add to relevant section
- New static-enforcement contract → add to §2
- New mode prompt drafted → add to §1
- New gap identified → add to §8 (or close one)

## 10. Quick reference for new sessions

If a fresh Claude / Codex / human session asks "how do we work here?":

1. **Read `MEMORY.md` index** — 13 memory notes auto-loaded
2. **Read this doc + `development-workflow.md`** — process rules
3. **Read `wave0-retrospective.md`** — 7 lessons
4. **Pick mode** (Mode 3 / 4 / Level 3) based on feature risk
5. **Lock gap decisions BEFORE coding** — save to `project_<feature>_gap_decisions.md` memory
6. **Write 5-category test plan** before code
7. **Run automation per chosen mode**
8. **Manual merge gate retained** — founder reviews final state

---

## Changelog

| Date | Change |
|---|---|
| 2026-05-12 | Initial snapshot post-Wave-0 + W0.7 + Wave 1 phase plans + L3 template |
