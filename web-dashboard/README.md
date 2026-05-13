# Web Dashboard — Tiền Về Nơi Đâu

> **Version:** v0.1.0
> **Status:** Scope locked / implementation deferred
> **Parent project:** [MyMoneyWent](../README.md)
> **Phase:** W (post-launch, trigger-based)

---

## Overview

Read-only companion web dashboard for **Tiền Về Nơi Đâu** (tienvenoidau.com). Visualizes transaction data captured via bot channels (Telegram/Discord/Messenger).

**This is NOT a primary interaction channel.** It does not replace chat-based workflows. Users still manage transactions, categories, and settings via the bot.

### What it does

- View transaction history with filters (date, category, funding source)
- Category spending breakdown (pie chart, spending cards)
- Monthly trend charts (Pro+)
- Budget progress visualization
- CSV export (Pro+)
- P&L style views (Business)

### What it does NOT do

- No manual transaction entry
- No category/budget CRUD
- No onboarding (onboarding stays in bot)
- No payment/plan management
- No admin tools

---

## Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Framework | Vite + React | SPA, no SSR needed |
| Styling | Vanilla CSS + CSS variables | Per project rules |
| Charts | TBD (Chart.js or Recharts) | |
| Auth | Magic link from bot + JWT | No standalone registration |
| API | FastAPI REST (shared with bot) | Read-only endpoints |
| Hosting | TBD (Vercel / Railway) | |

---

## Project Structure

```
web-dashboard/
├── README.md              ← This file
├── CHANGELOG.md
├── package.json           ← Created when Phase W starts
├── docs/
│   ├── brd.md             ← Dashboard-specific BRD
│   ├── prd.md             ← Dashboard-specific PRD
│   ├── design-tokens.md   ← Color, typography, spacing tokens
│   └── features/          ← Per-feature design handoff docs
│       ├── wd-shell-navigation.md
│       ├── wd-auth-flow.md
│       ├── wd-transaction-list.md
│       ├── wd-category-dashboard.md
│       ├── wd-charts-trends.md
│       ├── wd-settings.md
│       └── wd-upgrade-gate.md
├── designs/
│   └── web-dashboard.pen  ← Design file (created by designer)
└── src/                   ← Source code (created when Phase W starts)
```

---

## Implementation Triggers

Do NOT start implementation until one or more:

1. >=30% active users request web/history/export
2. >=10 Pro/Business users ask for desktop reporting
3. Chat history UX becomes support burden
4. Dashboard expected to improve Pro conversion

---

## Cross-references

- [Feature spec (functional)](../docs/features/feature-web-dashboard.md)
- [Resource assessment](../docs/research/webapp-resource-assessment.md)
- [Bot BRD v3.3.0](../docs/brd-vi.md)
- [Bot PRD v1.8.0](../docs/prd-vi.md)
- [Roadmap Phase W](../docs/mymoneywent-roadmap.md)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v0.1.0 | 2026-05-13 | Initial scaffold. Docs structure + 7 feature design specs. No code yet. |
