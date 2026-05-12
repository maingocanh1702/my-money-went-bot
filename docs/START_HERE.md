# Start Here

> **Cập nhật:** 2026-05-13 (post Wave 0 + W0.7 + W0.8 merged)

---

## If implementing code

1. **[Implementation Tracker](implementation-tracker.md)** — PR-level status board, current next PR
2. **[Development Workflow](operations/development-workflow.md)** — 10-step per-feature process
3. **Relevant feature spec:** `features/feature-<name>.md` (FE) + `features/BE/feature-<name>-tech.md` (BE)
4. **[Autopilot Template](autopilot/prompts/level3-autopilot-template.md)** — if using Level 3 autopilot

## If planning roadmap

1. **[Roadmap](mymoneywent-roadmap.md)** — phase overview + progress %
2. **[Implementation Tracker](implementation-tracker.md)** — PR-level detail

## Current next tasks

- [ ] **F07** — Settings `/settings` pilot — branch `feat/F07-settings` (unblocked after W0.8 merge)
- [ ] **W1.1** — Docker Compose dev + prod
- [ ] **W1.2** — Discord adapter
- [ ] **W1.3** — Phase 1 integration smoke E2E

After Phase 1 → Phase 2: Handlers Refactor → [plan](implementation-plans/phase-2-handlers.md)

## Source of truth rules

| What | Source of truth | NOT source of truth |
|------|----------------|---------------------|
| Current PR status / next action | `implementation-tracker.md` | roadmap (summary only) |
| Phase timeline + overall % | `mymoneywent-roadmap.md` | — |
| PR detail (scope, tests, AC) | `implementation-plans/phase-*.md` | — |
| Feature spec (what to build) | `features/feature-*.md` + `features/BE/*-tech.md` | — |
| Execution method | `operations/development-workflow.md` | — |
| Automation tooling | `docs/autopilot/` folder | — |

## Legacy code warning

Files in root (`main.py`, `sheets.py`, `telegram_api.py`, `handlers/`) are **legacy single-tenant**.
Do NOT build new features on these. New code goes in `core/` + `markets/`.
Legacy cutover: Phase 2 F02 PR. See [implementation plan](implementation-plans/phase-2-handlers.md#6--f02-transaction-capture-expanded-legacy-cutover).

---

> **Update rule:** Update "Current next tasks" section after each PR merge (per [development-workflow.md](operations/development-workflow.md) Step 10).
