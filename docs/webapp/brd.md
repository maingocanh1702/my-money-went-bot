# Web Dashboard — Business Requirements Document (BRD)

> **Version:** v2.1.0
> **Ngay tao:** 2026-05-13
> **Cap nhat:** 2026-05-30
> **Trang thai:** W1a scoped / W1b-W1c gated / W2 scoped (implementation deferred)
> **Parent BRD:** [Bot BRD-vi v3.3.0](../brd-vi.md) S4.3
> **Cross-refs:** [ADR-0003 Identity Model](../adr/0003-identity-model-accounts-channels.md) · [Zalo Bot API Research](../research-zalo-multi-user-bot.md)

---

## 1. Problem Statement

Bot-based finance tracking works well for quick interactions (categorize, view last few transactions). But users hit pain points when they need:

- **Desktop/mobile overview** of full transaction history with sorting/filtering
- **Visual charts** (spending trends, category breakdown) that chat can't render well
- **CSV export** for tax/accounting
- **P&L views** for Business tier shop owners
- **Cross-channel account management** — linking Telegram, Zalo, and web into one view

Chat history scrolling is a poor UX for data review. Users request a visual dashboard.

---

## 2. Product Definition

**Web Dashboard** follows a **progressive model**: W1 ships as a read-only
companion to bots, W2 evolves into a standalone entry point where users can sign
up, connect SePay, and receive realtime notifications without needing a bot
account first.

W1 is split into smaller launch gates:

- **W1a:** first companion MVP. Auth, shell, transaction list, category summary,
  basic plan/setting display, and upgrade gates.
- **W1b:** CSV export after auth/data-exfiltration controls are proven.
- **W1c:** Business P&L after Business-tier validation and Personal/Business
  tagging are ready.

### 2.1 What Dashboard IS

**W1 (companion):**
- Read-only view of transactions, categories, budgets, funding sources
- Charts and visualizations not possible in chat
- Mobile-first experience (responsive to desktop)
- Accessed via magic link from bot (no standalone registration in W1)
- Tier-gated features matching bot pricing
- If one user must see the same dashboard from both Telegram and Zalo, W1
  requires [ADR-0003](../adr/0003-identity-model-accounts-channels.md) Phase A
  first. Without Phase A, W1 can still ship as channel-scoped companion mode,
  but Telegram and Zalo users remain separate accounts.

**W2 (standalone, additive):**
- Also a standalone onboarding entry point (email signup → connect SePay → go)
- Also a channel management hub (connect/disconnect Telegram, Zalo, Discord)
- Also receives realtime transaction notifications via SSE first
- Also supports SePay webhook configuration directly from web UI

### 2.2 What Dashboard is NOT

- NOT a replacement for chat-based workflows (bot remains the quick-interaction UX)
- NOT a payment/subscription management tool in W1 (use bot; W2 may add)
- NOT a category/budget creation tool in W1 (use bot; W2 may add basic CRUD)

---

## 3. Target Users

Same personas as bot, but accessing dashboard for specific needs:

| Persona | Dashboard Need |
|---------|---------------|
| **Minh** (ca nhan) | Month-end review, category pie chart, export for tax |
| **Linh** (freelancer) | Income vs expense trend, multi-source view |
| **Hung+** (shop owner) | P&L report, source attribution, daily revenue tracking |
| **Web-first user** (W2) | Prefers web over chat, connects SePay on web, optionally links bot later |

---

## 4. Features

### W1a Features (companion MVP)

| # | Feature | Tier | Priority |
|---|---------|------|----------|
| WD-01 | Shell/Navigation | All | P0 |
| WD-02 | Auth Flow (magic link from bot) | All | P0 |
| WD-03 | Transaction List | All (30d Free, full Pro+) | P0 |
| WD-04 | Category Dashboard | All (basic Free, full Pro+) | P0 |
| WD-05 | Basic Charts/Trends | Pro+ | P1 |
| WD-06 | Settings (read-only) | All | P2 |
| WD-07 | Upgrade Gate | Free | P0 |

### W1b / W1c Features (gated after W1a)

| # | Feature | Tier | Priority | Gate |
|---|---------|------|----------|------|
| WD-14 | CSV export | Pro+ | P1 | Auth/session/data export controls stable |
| WD-15 | Business P&L view | Business | P1 | Business tier validated + Personal/Business tagging ready |
| WD-16 | Source attribution deep-dive | Business | P2 | Funding-source quality proven |

### W2 Features (standalone additive)

| # | Feature | Tier | Priority |
|---|---------|------|----------|
| WD-08 | Web signup (email magic link) | All | P0 |
| WD-09 | SePay connect on web (webhook URL + token display) | All | P0 |
| WD-10 | Channel management (connect/disconnect Telegram, Zalo) | All | P0 |
| WD-11 | Realtime transaction push (SSE first, WebSocket only if needed) | All | P1 |
| WD-12 | Scheduled export | Business | P2 |
| WD-13 | Web-based category picker (post-transaction) | All | P1 |

Canonical feature-detail docs currently live under
[`web-dashboard/docs/features/`](../../web-dashboard/docs/features/). If webapp
implementation moves under `docs/webapp/`, migrate those feature docs instead of
maintaining two divergent copies.

---

## 5. Pricing / Tier Gating

Dashboard does NOT change pricing. It extends existing tier value:

| Feature | Free | Pro (99k) | Family (169k) | Business (299k) |
|---------|:----:|:---------:|:-------------:|:---------------:|
| Transaction list | 30 days | Full history | Full history | Full history |
| Category summary | Basic | Full | Full | Full |
| Charts/Trends | No | Yes | Yes | Yes |
| CSV export | No | W1b | W1b | W1b |
| P&L views | No | No | No | W1c |
| Source attribution | No | No | No | W1c |
| Scheduled export | No | No | No | W2 |
| Web signup | Yes | Yes | Yes | Yes |
| Channel management | Yes | Yes | Yes | Yes |
| Realtime push | Yes | Yes | Yes | Yes |

### Entitlement Model

```
WEB_DASHBOARD = {
  'access': 'none|basic|full',    # none = no account
  'history_days': 30 | None,      # None = unlimited
  'charts': bool,
  'export': bool,
  'pnl': bool,
}
```

---

## 6. Security Requirements (P0)

> **WARNING:** Dashboard read-only can still leak entire financial history if auth is wrong. Treat auth, session, and tenant isolation as P0 launch blockers.

### W1 Auth

| Requirement | Detail |
|------------|--------|
| Auth method | Magic link from bot (single-use, short TTL <=10min, raw token shown only once) |
| No standalone registration | Must have existing bot account |
| Session | JWT access 15min + refresh token rotation |
| Tenant isolation | Account A cannot see Account B data. Mandatory tests. |
| CORS | Strict configured origin allowlist, e.g. `WEB_APP_ORIGIN` |
| Rate limit | Magic link: max 3/hour per account. API: standard limits. |
| Audit | All auth events logged to analytics_events |
| Link security | 404 for invalid/expired links (no info leak) |

### Auth/session implementation requirements

| Requirement | Detail |
|------------|--------|
| Token storage | Store only SHA-256 hash of magic-link token; never store raw token. |
| Token exchange | Atomic consume: `used_at IS NULL AND expires_at > NOW()` in one transaction. |
| URL hygiene | After token exchange, redirect to dashboard route without token query string. |
| Logging hygiene | Never log raw magic tokens, refresh tokens, Authorization headers, or full magic-link URLs. |
| Refresh token | Rotate refresh token on every use; store server-side hash/revocation state. |
| Cookie mode | If cookies are used, set `HttpOnly`, `Secure`, `SameSite=Lax/Strict`, and add CSRF protection for write endpoints. |
| Export controls | CSV export remains W1b until auth/session controls and audit logging are verified. |

### W2 Auth (additive)

| Requirement | Detail |
|------------|--------|
| Web signup | Email magic link (no password in v1). Stored in `auth_identities` table per [ADR-0003](../adr/0003-identity-model-accounts-channels.md) |
| Email verification | Required before accessing financial data |
| Channel linking | Via link codes (10min TTL, hashed in DB). See ADR-0003 Flow 1 |
| Account merge | Explicit confirmation required when linking channel with existing data. Audit trail in `account_merge_events` |
| Session | Same JWT model as W1 |

---

## 7. Architecture Summary

### W1 (companion)

```
Bot (Telegram / Zalo / Discord)
  |
  | generates magic link
  v
User clicks link --> web-dashboard SPA (${WEB_APP_ORIGIN})
  |
  | JWT auth (via magic link token exchange)
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

If [ADR-0003](../adr/0003-identity-model-accounts-channels.md) Phase A is
complete, bot magic-link generation resolves the authenticated channel to
`channels.account_id`, and the JWT subject is that account id. If Phase A is not
complete, W1a may only ship as channel-scoped companion mode.

### W2 (standalone, additive)

```
Web signup (email magic link)
  |
  | creates accounts row + auth_identities row
  v
Web dashboard SPA
  |
  ├─ read/write API (FastAPI)
  │    ├─ SePay webhook config (display URL + token)
  │    ├─ Channel management (link/unlink Telegram, Zalo)
  │    └─ Category picker (post-transaction)
  │
  ├─ SSE connection
  │    └─ realtime transaction push (when SePay webhook fires)
  │
  v
PostgreSQL
  |
  identity model (ADR-0003):
  - accounts (identity + data ownership)
  - auth_identities (web/social login)
  - channels (bot delivery endpoints)
```

**Key architectural principles:**

1. Dashboard API shares the same `core/services/` query layer as bot. Bot formats as chat text, API returns JSON. No logic duplication.
2. Web is NOT a `channels` row — it's an `auth_identities` row. Web users don't receive bot-style messages; they get SSE pushes or in-app notifications.
3. SePay webhook handler doesn't change — `_persist()` writes to `transactions`, then notification fan-out happens via `messenger.send()` (bot channels) and SSE broadcast (web sessions) in parallel.
4. `accounts.id` is the data ownership anchor. Whether user signed up via Telegram, Zalo, or web, all transactions/categories belong to the same `accounts.id`.
5. Domain names are configuration, not constants. VN deployment may use
   `app.tienvenoidau.com` / `api.tienvenoidau.com`; global deployment may use
   `app.mymoneywent.com` / `api.mymoneywent.com`.
6. Realtime starts with SSE. Upgrade to WebSocket only if bidirectional
   realtime interaction is needed.

### 7.1 API Contract (W1a minimum)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/magic/exchange` | POST | Exchange one-time magic token for account-scoped session |
| `/api/v1/auth/refresh` | POST | Rotate refresh token and issue new access token |
| `/api/v1/auth/logout` | POST | Revoke current refresh token/session |
| `/api/v1/me` | GET | Current account, locale, timezone, plan, entitlements |
| `/api/v1/transactions` | GET | Paginated transaction list with filters |
| `/api/v1/categories/summary` | GET | Monthly category totals and budget status |
| `/api/v1/funding-sources` | GET | Read-only funding source list |
| `/api/v1/entitlements` | GET | Effective dashboard feature gates |

W1b adds:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/exports/transactions.csv` | GET | Audited CSV export for Pro+ |

W2 adds:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/email/request` | POST | Request email magic link |
| `/api/v1/channels/link-codes` | POST | Generate channel link code |
| `/api/v1/channels` | GET | List connected bot channels |
| `/api/v1/channels/{id}` | DELETE | Disconnect/deactivate a channel |
| `/api/v1/realtime/events` | GET | SSE stream for active web session |

---

## 8. Success Metrics

### W1a

| Metric | Target |
|--------|--------|
| Dashboard MAU / Bot MAU | >=20% |
| Session duration | >=3 min |
| Pro conversion lift from dashboard | >=5% improvement |

### W1b / W1c

| Metric | Target |
|--------|--------|
| CSV export usage (Pro+) | >=10% of Pro users |
| P&L view usage (Business) | >=30% of Business users after Business launch |

### W2 (additive)

| Metric | Target |
|--------|--------|
| Web-only signups / total signups | >=15% |
| Web → bot channel link rate | >=30% of web-only users |
| Realtime push engagement | >=40% of web users with active session during transaction |
| Web category picker usage | >=50% of web users categorize on web (vs ignoring) |

---

## 9. Timeline Estimate

| Phase | Duration | Scope |
|-------|----------|-------|
| W1a | 12-18 days | Companion MVP (WD-01 to WD-07). Read-only, magic link auth, no CSV/P&L |
| W1b | 4-7 days | CSV export (WD-14) after auth/export controls pass |
| W1c | TBD | Business P&L/source attribution after Business validation |
| W2 | TBD | Standalone entry (WD-08 to WD-13). Web signup, SePay connect, channel management, realtime push. Requires [ADR-0003](../adr/0003-identity-model-accounts-channels.md) Phase A complete |

**Trigger-based start.** See [implementation triggers](../research/webapp-resource-assessment.md).

**Identity dependency:** ADR-0003 Phase A (channels table added, backfill
complete) is required before any web release that promises unified Telegram +
Zalo identity. W1a can ship before Phase A only if explicitly positioned as
channel-scoped companion mode. W2 always requires Phase A.

---

## 10. W1 → W2 Migration Notes

W1 design decisions that must NOT block W2:

| Decision | W1 | W2 Requirement | How to not block |
|----------|-----|----------------|-----------------|
| Auth | Magic link only | Email magic link | JWT structure must be account-scoped. Use `account_id` as JWT subject from day 1; if Phase A is not done, document channel-scoped limitation |
| DB queries | `WHERE user_id = $1` | `WHERE account_id = $1` | After ADR-0003 Phase A, `user_id` column IS the account_id. No query changes needed if FKs point to same table |
| API endpoints | `/api/v1/transactions?...` | Same endpoints + write endpoints | Use versioned API. Read endpoints stay the same. Add write endpoints in W2 |
| Frontend | Read-only components | Add forms/inputs for SePay config, category picker | Component architecture must support both read and interactive modes |
| Realtime | None | SSE first | Design read API so it can be refreshed by SSE events later. Do not require WebSocket unless bidirectional realtime becomes necessary |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-05-13 | Initial BRD. 7 features, tier gating, security P1, architecture, success metrics. |
| v2.0.0 | 2026-05-30 | Progressive model (companion → standalone). Added W2 features (WD-08 to WD-13). Added Zalo to architecture. Switched to mobile-first. Added ADR-0003 cross-ref for identity model. Added W2 auth (email magic link, auth_identities). Added W1→W2 migration notes. Added W2 success metrics. Clarified web is auth_identity not channel. |
| v2.1.0 | 2026-05-30 | Split W1 into W1a/W1b/W1c to reduce first-build scope. Moved CSV export and Business P&L behind gates. Upgraded dashboard auth/session/tenant isolation to P0. Clarified ADR-0003 Phase A dependency for unified Telegram+Zalo identity. Switched realtime default to SSE. Added API contract, domain configuration rule, token hygiene, and canonical feature-doc location. |
