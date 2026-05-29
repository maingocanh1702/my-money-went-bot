# Dashboard Engine — Side Project Index

> **Status:** Complete (7/7 PRs merged)
> **Scope:** Realtime ops tracker dashboard that auto-rebuilds from implementation-tracker.md + git/GitHub/CI/Railway signals.

---

## What this is

A self-contained tooling side project within MyMoneyWent. It powers the auto-generated `docs/dashboard.{html,md,json}` files that visualize project progress in realtime.

**Not part of the product.** This is developer tooling — it does not affect `core/`, `markets/`, bot functionality, or any user-facing feature.

## Directory Layout

```
tools/dashboard-engine/
├── INDEX.md                          # this file
├── build_dashboard.py                # main builder script (66KB)
├── work_state/                       # engine modules
│   ├── engine.py                     # driver + aggregation
│   ├── event_engine.py               # event emission + dedup
│   ├── models.py                     # Signals, CurrentState dataclasses
│   ├── plan_reader.py                # parse implementation-tracker.md
│   ├── progress.py                   # progress % computation
│   ├── state_store.py                # JSON persistence
│   ├── status_machine.py             # status resolution
│   ├── projections/dashboard.py      # state → dashboard projection
│   └── signal_collectors/            # git, github, ci, railway, filesystem
├── tests/
│   ├── unit/                         # 21 test files
│   └── integration/                  # 6 test files
├── docs/
│   ├── specs/                        # architecture, plans, vision
│   ├── prompts/                      # autopilot prompts for each phase
│   └── migration/                    # v1 migration docs
└── .state/                           # runtime cache (gitignored)
```

## Files that remain outside this folder

| File | Location | Reason |
|------|----------|--------|
| `docs/dashboard.html` | Project root docs/ | Auto-generated output, consumed by GH Pages |
| `docs/dashboard.md` | Project root docs/ | Auto-generated output |
| `docs/dashboard.json` | Project root docs/ | Auto-generated output |
| `.github/workflows/dashboard.yml` | GH Actions | CI workflow (references this folder) |

## PRs (all merged)

1. **work-state-engine-1a** — skeleton + filesystem + git collectors
2. **work-state-engine-1b** — github + ci + railway collectors
3. **work-state-engine-1b'** — dashboard projection
4. **work-state-engine-1c** — driver + aggregation + persistence + workflow
5. **dashboard-live-view-A** — engine→build wire
6. **dashboard-live-view-B** — doc-change awareness
7. **doc-change-hash-dedup** — MYM-8, hash-aware dedup + emission wire

## How to run

```bash
# Run engine (collect signals + update state)
python -m tools.dashboard-engine.work_state

# Rebuild dashboard from tracker + state
python tools/dashboard-engine/build_dashboard.py

# Run tests
pytest tools/dashboard-engine/tests/ -v
```
