# Web Dashboard — Business Requirements Document (BRD)

> **Version:** v1.0.0
> **Ngay tao:** 2026-05-13
> **Trang thai:** Scope locked / implementation deferred
> **Parent BRD:** [Bot BRD-vi v3.3.0](../../docs/brd-vi.md) S4.3

---

## 1. Problem Statement

Bot-based finance tracking works well for quick interactions (categorize, view last few transactions). But users hit pain points when they need:

- **Desktop overview** of full transaction history with sorting/filtering
- **Visual charts** (spending trends, category breakdown) that chat can't render well
- **CSV export** for tax/accounting
- **P&L views** for Business tier shop owners

Chat history scrolling is a poor UX for data review. Users request a visual dashboard.

---

## 2. Product Definition

**Web Dashboard** is a **read-only companion UI** that visualizes data already captured via bot. It is NOT a standalone product and NOT a replacement for chat-based workflows.

### 2.1 What Dashboard IS
- Read-only view of transactions, categories, budgets, funding sources
- Charts and visualizations not possible in chat
- Desktop-first experience (responsive to mobile)
- Accessed via magic link from bot (no standalone registration)
- Tier-gated features matching bot pricing

### 2.2 What Dashboard is NOT
- NOT a transaction entry point (use bot)
- NOT a category/budget management tool (use bot)
- NOT an onboarding flow (use bot)
- NOT a payment/subscription management tool (use bot)
- NOT a standalone app (requires bot account)

---

## 3. Target Users

Same personas as bot, but accessing dashboard for specific needs:

| Persona | Dashboard Need |
|---------|---------------|
| **Minh** (ca nhan) | Month-end review, category pie chart, export for tax |
| **Linh** (freelancer) | Income vs expense trend, multi-source view |
| **Hung+** (shop owner) | P&L report, source attribution, daily revenue tracking |

---

## 4. Features (7 Feature Areas)

| # | Feature | Tier | Priority |
|---|---------|------|----------|
| WD-01 | Shell/Navigation | All | P0 |
| WD-02 | Auth Flow (magic link) | All | P0 |
| WD-03 | Transaction List | All (30d Free, full Pro+) | P0 |
| WD-04 | Category Dashboard | All (basic Free, full Pro+) | P0 |
| WD-05 | Charts/Trends | Pro+ | P1 |
| WD-06 | Settings (read-only) | All | P2 |
| WD-07 | Upgrade Gate | Free | P0 |

Detail per feature: see [docs/features/](features/)

---

## 5. Pricing / Tier Gating

Dashboard does NOT change pricing. It extends existing tier value:

| Feature | Free | Pro (99k) | Family (169k) | Business (299k) |
|---------|:----:|:---------:|:-------------:|:---------------:|
| Transaction list | 30 days | Full history | Full history | Full history |
| Category summary | Basic | Full | Full | Full |
| Charts/Trends | No | Yes | Yes | Yes |
| CSV export | No | Yes | Yes | Yes |
| P&L views | No | No | No | Yes |
| Source attribution | No | No | No | Yes |
| Scheduled export | No | No | No | Phase W2 |

### Entitlement Model

```
WEB_DASHBOARD = {
  'access': 'none|basic|full',    # none = no bot account
  'history_days': 30 | None,      # None = unlimited
  'charts': bool,
  'export': bool,
  'pnl': bool,
}
```

---

## 6. Security Requirements (P1)

> **WARNING:** Dashboard read-only can still leak entire financial history if auth is wrong. Treat as P1 security surface.

| Requirement | Detail |
|------------|--------|
| Auth method | Magic link from bot (single-use, short TTL <=10min) |
| No standalone registration | Must have existing bot user_id |
| Session | JWT access 15min + refresh token rotation |
| Tenant isolation | User A cannot see User B data. Mandatory tests. |
| CORS | Strict origin: app.tienvenoidau.com only |
| Rate limit | Magic link: max 3/hour per user. API: standard limits. |
| Audit | All auth events logged to analytics_events |
| Link security | 404 for invalid/expired links (no info leak) |

---

## 7. Architecture Summary

```
Bot (Telegram/Discord/Messenger)
  |
  | generates magic link
  v
User clicks link --> web-dashboard SPA (app.tienvenoidau.com)
  |
  | JWT auth
  v
Dashboard API (FastAPI, shared with bot)
  |
  | read-only queries
  v
PostgreSQL (same DB as bot)
  |
  shared query layer:
  - core/services/transactions_query.py
  - core/services/reports_query.py
```

**Key:** Dashboard API is a thin read-only wrapper around the same query layer the bot uses. Bot formats results as chat text, API returns JSON.

---

## 8. Success Metrics

| Metric | Target |
|--------|--------|
| Dashboard MAU / Bot MAU | >=20% |
| Session duration | >=3 min |
| Pro conversion lift from dashboard | >=5% improvement |
| CSV export usage (Pro+) | >=10% of Pro users |
| P&L view usage (Business) | >=30% of Business users |

---

## 9. Timeline Estimate

| Phase | Duration | Scope |
|-------|----------|-------|
| W1 | 19-29 days | Core dashboard (all 7 features) |
| W2 | TBD | Scheduled export, notifications, realtime |

**Trigger-based start.** See [implementation triggers](../../docs/research/webapp-resource-assessment.md).

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-05-13 | Initial BRD. 7 features, tier gating, security P1, architecture, success metrics. |
