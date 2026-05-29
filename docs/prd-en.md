# My Money Went — Product Requirements Document (PRD)

> **Version:** v2.0.0
> **Created:** 2026-05-10
> **Last updated:** 2026-05-10
> **Status:** Draft
> **References:** [brd-en.md v4.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-en.md) · [tdd-en.md v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-en.md) · [market-strategy-overview.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/market-strategy-overview.md)
>
> **🌐 SCOPE NOTE:** This PRD is the **canonical product spec for the 🌍 Global market** (My Money Went — mymoneywent.com). Capture stack (Plaid + e-com OAuth + payout email parsing), single ICP (e-commerce solopreneur), pricing ($6 Pro / $12 Solopreneur), channels (Telegram + Discord + Messenger + read-only web dashboard), and payment (Stripe Checkout) are all **global-specific**. The **Vietnam market** has its own PRD — [prd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) (Tiền Về Nơi Đâu — tienvenoidau.com). Per [ADR-0001](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md), shared foundation specs (DB schema, messenger interface, auth) apply to both markets.
>
> **Change v2.0.0 vs v1.6.0 — MAJOR REWRITE:** Discarded VN-derived content (SePay, VN banks, Hùng+ persona, VND pricing). Rebuilt from brd-en.md v4.0.0: distinct capture stack, ICP, pricing, payment, web dashboard scope.

---

## 1. Product overview

### 1.1. Description
My Money Went is a **multi-platform finance tracking SaaS** for e-commerce solopreneurs. The product runs as a chat bot on **Telegram + Discord + Messenger** (MVP) plus a **read-only Next.js web dashboard** for depth views (P&L, charts, settings, integration setup). It consolidates income from Stripe, PayPal, Shopify, Etsy (and Phase 2: Amazon SP-API, TikTok Shop) + bank expenses via Plaid/TrueLayer/Tink into a single Personal-vs-Business P&L — without forcing the user to leave their messaging app for daily interactions.

3-tier pricing: **Free** / **Pro $6/mo** / **Solopreneur $12/mo** + 14-day Pro trial for all new users.

### 1.2. Design principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Zero-config** | OAuth-based integrations. No API keys, no manual CSV imports. 5-15 min onboarding. |
| 2 | **Chat-first, dashboard-second** | ~80% daily interactions via bot (categorization, quick views). ~20% monthly depth via web dashboard (P&L, charts, setup). |
| 3 | **Track-first, budget-optional** | Tracking is default. Budget is opt-in for those who want it. |
| 4 | **1-tap categorization** | Categorize = tap a button. No text input unless creating a new category. |
| 5 | **Personal vs Business as first-class** | Every tx tagged personal/business. Auto-default by source. Manual override anytime. |
| 6 | **3-path onboarding** | Plaid bank link (expenses) + e-com OAuth (income) + payout email forwarding (backup). Cover 100% ICP. |

### 1.3. Tech stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11+ · FastAPI · Uvicorn |
| Database | PostgreSQL (Railway managed) — multi-tenant |
| Messaging | Telegram Bot API + Discord Bot API + Messenger Send API — 1 shared bot per platform, platform-owned |
| Bank integration | Plaid (US/CA) + TrueLayer (UK) + Tink (EU) — read-only open banking |
| E-com integration | Stripe Connect OAuth + PayPal OAuth + Shopify App OAuth + Etsy OAuth |
| Income backup | Postmark Inbound email parsing — payout emails from Stripe/PayPal/Shopify/Etsy |
| Web dashboard | Next.js + Supabase Auth — read-only for transactions, full for settings/integrations |
| Hosting | Railway Hobby plan (app + DB) |
| Scheduling | APScheduler (in-process, per-user timezone-aware) |
| Payment | Stripe Checkout (credit card + Apple Pay + Google Pay) |
| Backup | Backblaze B2 daily with SSE-B2 encryption |
| Admin tools | Shared with VN track — Telegram commands restricted by `ADMIN_TELEGRAM_IDS` |
| Observability | Sentry + Railway metrics + UptimeRobot. Shared admin dashboards. |

### 1.4. Bot ownership model — Multi-platform

**1 shared bot per platform, owned by the platform** — users do NOT bring their own bot. Same architectural decision as VN track.

**Platforms (MVP):**
- **Telegram** (`@MyMoneyWentBot`) — primary, bot ecosystem mature
- **Discord** (`My Money Went#1234`) — co-primary, strong US/UK solopreneur overlap
- **Messenger** (`m.me/MyMoneyWentPage`) — co-primary, reaches Meta-surface sellers

**Registration flow (all platforms):**
1. User finds bot → taps "Start" / "Get Started" / uses slash command
2. Bot receives platform-specific user ID (Telegram `chat_id`, Discord `user_id`, Messenger PSID)
3. Backend: `INSERT INTO users (channel_type, channel_user_id, ...) ON CONFLICT DO NOTHING`
4. Bot replies via platform-specific adapter through `messenger.send()` interface

**Operational implications:**
- Tokens (`TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `MESSENGER_PAGE_TOKEN`) stored in Railway env, managed by platform owner.
- All outbound messages route through `services/messenger.py` → `services/channels/{telegram,discord,messenger}.py` adapters.
- Per-platform SPOF: one platform down ≠ all users down. Multi-platform reduces risk.

---

## 2. User flows

### 2.1. Onboarding flow — Path A: Plaid bank link (5-8 min)

```
User finds @MyMoneyWentBot on Telegram / Discord / Messenger
    │
    ▼
User sends /start (or taps "Get Started")
    ├── Bot creates account (users table)
    ├── Bot creates 3 default categories
    ├── Bot assigns 14-day Pro trial
    │
    ▼
Bot sends welcome + path selector:
    "👋 Welcome! I'll help you track your finances automatically.

     How would you like to connect?"

    [🏦 Link Bank]  [🛒 Connect Store]  [📧 Forward Emails]
    │
    ├── User taps "Link Bank"
    │   ├── Bot sends Plaid Link URL (opens in browser/webview)
    │   ├── User authenticates with their bank via Plaid
    │   ├── Plaid callback → bot confirms: "✅ Bank linked!"
    │   └── Bot pulls recent transactions → first category picker
    │
    ▼
First transaction → category picker → ✅ Setup complete
```

### 2.2. Onboarding flow — Path B: E-com OAuth (5-10 min)

```
User taps "Connect Store"
    │
    ▼
Bot shows integration picker:
    [Stripe]  [PayPal]  [Shopify]  [Etsy]
    │
    ├── User taps "Stripe" (or any platform)
    │   ├── Bot sends OAuth authorization URL
    │   ├── User authorizes in browser → redirect back
    │   ├── Bot confirms: "✅ Stripe connected! Pulling recent payouts..."
    │   └── Bot pulls recent payouts → first category picker
    │
    ▼
First transaction → category picker → ✅ Setup complete
```

### 2.3. Onboarding flow — Path C: Payout email forwarding (5-10 min)

```
User taps "Forward Emails"
    │
    ▼
Bot sends:
    "📧 Email Forwarding Setup

     Your unique inbound address:
     u{user_id}@in.mymoneywent.com

     Forward payout notification emails from Stripe, PayPal,
     Shopify, or Etsy to this address."

    [📱 I use Gmail] [💻 I use Outlook] [❓ Other]
    │
    ├── Gmail: guide to Settings → Forwarding → Add address
    ├── Outlook: guide to Settings → Rules → Forward
    │
    ▼
First email arrives → parse → category picker → ✅ Setup complete
```

### 2.4. Transaction flow (core loop)

```
Plaid sync → new transactions detected
  or
E-com OAuth → new payout/transaction via API
  or
Email → Postmark inbound → POST /inbound/{token}
  or
Manual → /add 50 coffee personal
    │
    ├── Validate source → lookup user
    ├── Check tier limits (Free: 60 tx/month)
    ├── Parse → canonical transaction schema
    ├── Auto-tag personal/business (by source: Plaid → personal, e-com → business)
    ├── Auto-categorize (rule-based: STRIPE FEE → "Platform Fees", etc.)
    ├── Dedup check
    ├── INSERT into transactions table
    │
    ▼
Bot sends category picker (if not auto-categorized):
    "💸 -$14.99
     ADOBE CREATIVE CLOUD

     Category? 🤔"

    [📱 Subscriptions] [💼 Business Tools]
    [🛒 Shopping]      [➕ New category]
    [⏭️ Skip]          [👤/💼 Toggle P/B]
    │
    ├── User taps category → finalize
    │   ├── Tracking: "📊 Subscriptions: $245 this month"
    │   ├── Budget: "██████░░░░ 60% · $60 / $100 · $40 left"
    │   └── [🔄 Wrong?] button
    │
    └── User taps "Toggle P/B" → switch personal↔business tag
```

### 2.5. Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/start` | Onboarding — create account + 3-path setup | All |
| `/today` | Today's spending summary | All |
| `/balance` | Month overview: categories, P&L split | All |
| `/add` | Manual log: `/add 50 coffee personal` | All |
| `/manage` | CRUD categories | All |
| `/weekly` | 7-day breakdown | Pro+ |
| `/report` | Full monthly P&L report | Pro+ |
| `/settings` | Account settings, integrations, plan | All |
| `/export` | CSV/PDF export | Pro+ |
| `/help` | Usage guide | All |

---

## 3. Feature specifications

### 3.1. F01 — 3-Path Onboarding

**Acceptance Criteria:**
- [ ] `/start` creates user row in `users` table (multi-tenant, keyed by `channel_type + channel_user_id`)
- [ ] Generate `inbound_email` = `u{user_id}@in.mymoneywent.com`
- [ ] Create 3 default categories (tracking mode)
- [ ] Assign 14-day Pro trial (`trial_ends_at = now + 14d`)
- [ ] Welcome message + 3-path selector (Bank Link / Connect Store / Forward Emails)
- [ ] Path A: Plaid Link integration URL, callback handler, transaction pull
- [ ] Path B: OAuth authorization URLs for Stripe/PayPal/Shopify/Etsy
- [ ] Path C: inbound email + forwarding guide (Gmail/Outlook)
- [ ] `/start` idempotent — multiple calls don't create duplicates
- [ ] `/start` with existing account → show status + settings

**Default Categories:**

| id | name | type |
|----|------|------|
| `shopping` | 🛒 Shopping | tracking |
| `subscriptions` | 📱 Subscriptions | tracking |
| `platform_fees` | 💰 Platform Fees | tracking |

### 3.2. F02 — Transaction Capture (Plaid + E-com OAuth + Email)

**Sources:**
- **Plaid:** Daily sync of bank transactions (expenses primarily)
- **E-com OAuth:** Real-time or periodic pull of payouts + fees
- **Email:** Postmark inbound webhook at `POST /inbound/{token}`
- **Manual:** `/add` command or web dashboard entry

**Canonical Transaction Schema:**

| Field | Type | Source: Plaid | Source: OAuth | Source: Email |
|-------|------|--------------|---------------|---------------|
| amount | decimal | amount | payout/fee amount | parsed |
| direction | enum(in/out) | derived | derived | parsed |
| description | string | name/merchant | payout description | parsed |
| ref_code | string | transaction_id | payout_id | hash |
| tx_date | datetime | date | arrival_date | parsed |
| source | string | "plaid" | "stripe"/"shopify"/etc. | "email_stripe"/etc. |
| biz_tag | enum | "personal" (default) | "business" (default) | inferred |

**Acceptance Criteria:**
- [ ] Plaid: daily sync via `/transactions/sync` endpoint, handle pagination
- [ ] Plaid: graceful degradation when Plaid API down
- [ ] E-com OAuth: Stripe payouts + balance transactions, PayPal transactions, Shopify orders + payouts, Etsy receipts + deposits
- [ ] Email: parse Stripe, PayPal, Shopify, Etsy payout notification emails
- [ ] Email: fallback "unparsed" notification for unsupported format
- [ ] Dedup: `UNIQUE(user_id, source, ref_code)` — INSERT ON CONFLICT DO NOTHING
- [ ] Free tier: reject if user hit 60 tx/month + send upgrade prompt
- [ ] Auto-tag personal/business by source
- [ ] Auto-categorize by rule engine (system defaults + user custom rules)

**Email Parser Requirements (MVP):**

| Platform | Email sender patterns | Parser status |
|----------|----------------------|---------------|
| Stripe | receipts@stripe.com, notifications@stripe.com | 🔲 MVP |
| PayPal | service@paypal.com | 🔲 MVP |
| Shopify | no-reply@shopify.com | 🔲 MVP |
| Etsy | transaction@etsy.com | 🔲 MVP |

### 3.3. F03 — Transaction Categorization

**Acceptance Criteria:**
- [ ] Inline buttons / slash command options / quick replies: all active categories
- [ ] "➕ New category" at end (create inline)
- [ ] "⏭️ Skip" for auto-captured transactions
- [ ] "👤/💼 Toggle P/B" — switch personal↔business tag
- [ ] "🔄 Wrong category?" on confirmation → re-pick
- [ ] Auto-categorization rules engine: system defaults (UBER → Transport, STRIPE FEE → Platform Fees) + user custom rules
- [ ] Free: system defaults only. Pro: +15 custom rules. Solopreneur: unlimited.
- [ ] State machine: `await_category` → `await_sub` → `done`

### 3.4. F04 — Category Management (/manage)

Same as VN track — CRUD categories/sub-categories. Tier limits: Free 5, Pro 20, Solopreneur unlimited.

### 3.5. F05 — Reports & P&L

#### /balance — Monthly P&L Overview
```
📊 My Money Went — May 2026

💼 BUSINESS:
  Income:    +$4,250 (Stripe $2,800 · Shopify $1,200 · Etsy $250)
  Expenses:  -$890 (Platform Fees $340 · Ads $400 · Supplies $150)
  ─────
  Net:       +$3,360

👤 PERSONAL:
  Expenses:  -$2,100 (Rent $1,500 · Food $400 · Transport $200)

═════
Combined:   +$1,260
```

#### /today — Daily Overview
```
🍜 Today — May 10

Spent: $45.50 (3 tx)
Business: $12.99 (Canva Pro)
Personal: $32.51 (groceries, coffee)
```

#### Daily Recap (auto, 21:00 user timezone)
```
🌙 End of day — May 10

Business income: +$180 (2 Stripe payouts)
Business expenses: -$12.99
Personal expenses: -$32.51
Net today: +$134.50
```

**Acceptance Criteria:**
- [ ] `/balance` separates Business vs Personal with income/expense breakdown
- [ ] `/today` shows daily summary
- [ ] Daily recap fires at user timezone (±5 min jitter)
- [ ] `/weekly` (Pro+): 7-day P&L breakdown
- [ ] `/report` (Pro+): full monthly P&L
- [ ] CSV/PDF export (Pro+): `/export`

### 3.6. F06 — Pricing, Tier Limits & Trial

**Pricing:**

| Plan | Monthly | Annual (≈20% off) |
|------|---------|-------------------|
| Free | $0 | $0 |
| Pro | $6/mo | $58/yr ($4.83/mo) |
| Solopreneur | $12/mo | $115/yr ($9.58/mo) |

**Tier Limits:**

| Limit | Free | Pro | Solopreneur |
|-------|------|-----|-------------|
| Transactions/month | 60 | Unlimited | Unlimited |
| Plaid bank links | 1 | 3 | Unlimited |
| E-com integrations | 1 (Stripe or PayPal only) | 3 (all platforms) | Unlimited |
| Email sources | 1 | 3 | Unlimited |
| Transaction history | 30 days | Unlimited | Unlimited |
| Personal/Business split | Personal only | ✅ Both | ✅ Both |
| P&L view | ❌ | ✅ | ✅ |
| Categories | 5 | 20 | Unlimited |
| Auto-cat rules | System defaults only | +15 custom | Unlimited |
| Web dashboard | Basic (read-only) | Full | Full |
| Weekly/monthly reports | ❌ | ✅ | ✅ |
| CSV/PDF export | ❌ | ✅ | ✅ |
| Google Sheets sync | ❌ | ❌ | ✅ |

**Trial Logic:**
- [ ] New user → 14-day Pro trial, auto-assigned
- [ ] Day 12: reminder "Trial ends in 2 days..."
- [ ] Day 14: auto-downgrade to Free, data preserved
- [ ] Upgrade triggers: max 1 message/week/user (per BRD §5.2.3)

**Payment (Stripe Checkout):**
- [ ] User `/upgrade` → bot sends Stripe Checkout link
- [ ] Stripe handles credit card + Apple Pay + Google Pay
- [ ] Webhook confirms payment → upgrade plan
- [ ] Monthly: reminder 3 days before renewal, 7-day grace after failed charge
- [ ] Annual: reminders 30 + 7 + 1 days before renewal
- [ ] 14-day money-back refund, no questions asked

### 3.7. F07 — Web Dashboard (read-only for transactions)

**Stack:** Next.js + Supabase Auth (cross-platform auth via bot-generated magic link)

**Pages:**
| Page | Description | Tier |
|------|-------------|------|
| `/dashboard` | P&L overview, monthly/quarterly charts | All (Free = Personal only) |
| `/transactions` | Transaction list (read-only, filterable) | All |
| `/integrations` | Connect/disconnect Plaid, Stripe, PayPal, Shopify, Etsy | All |
| `/categories` | Manage categories + auto-cat rules | All |
| `/settings` | Timezone, notifications, plan, billing | All |
| `/export` | CSV/PDF download | Pro+ |

**Acceptance Criteria:**
- [ ] Auth: bot sends magic link → user clicks → authenticated session
- [ ] P&L chart: Personal vs Business income/expense by month
- [ ] Transaction list: filter by source, category, date, personal/business
- [ ] Integration setup: OAuth flow initiation for each platform
- [ ] Read-only for transactions — all edits (categorize, retag P/B) via bot
- [ ] Responsive: mobile-first, works on 375px-1440px

### 3.8. F08 — Multi-User Data Isolation

Same as VN track — all queries scoped by `user_id`, webhook validated by token, bot state isolated per user.

### 3.9. F09 — Scheduled Jobs (per-user)

| Job | Schedule | Condition |
|-----|----------|-----------|
| `daily_recap` | 21:00 user timezone ±5 min jitter | enabled=TRUE, ≥1 tx today |
| `plaid_sync` | Every 6 hours | Plaid connected |
| `ecom_sync` | Every 4 hours | ≥1 OAuth integration connected |
| `trial_reminder` | Day 12 of trial | trial active |
| `trial_downgrade` | Day 14 of trial | trial active |
| `weekly` | Sunday 10:00 ±5 min jitter | Pro+ only |
| `monthly_report` | Last day of month 10:00 ±5 min jitter | Pro+ only |

---

## 4. Data model

### 4.1. Entity Relationship

```
users (1) ──── (N) transactions
  │                    │
  │                    └── category_id FK → categories.id
  │
  ├──── (N) categories
  │         └──── (N) sub_categories
  │
  ├──── (N) integrations (Plaid + OAuth + email sources)
  │
  ├──── (N) auto_cat_rules (user custom categorization rules)
  │
  ├──── (1) bot_state
  │
  └──── (N) scheduled_jobs
```

### 4.2. Key Tables (see tdd-en.md for full DDL)

| Table | Description |
|-------|-------------|
| `users` | Account, plan, trial, timezone, channel identity |
| `transactions` | Canonical tx data, category, biz_tag, confirmed |
| `categories` | Per-user categories, budget, active flag |
| `integrations` | Plaid links + OAuth connections + email sources |
| `auto_cat_rules` | Rule-based auto-categorization (merchant pattern → category) |
| `bot_state` | Conversation state machine per user |
| `scheduled_jobs` | Per-user scheduled tasks |

---

## 5. Non-functional requirements

### 5.1. Performance

| Metric | Target |
|--------|--------|
| Bot reply latency | < 2s |
| Plaid sync time | < 30s per account |
| Dashboard page load | < 3s |
| DB query time | < 50ms (simple queries) |

### 5.2. Security

| Concern | Solution |
|---------|----------|
| Bank credentials | Never stored — Plaid handles all bank auth |
| OAuth tokens | Encrypted at rest, per-user isolation |
| Data minimization | No bank account numbers, only amounts + descriptions |
| Transport | HTTPS everywhere (Railway auto SSL) |
| GDPR/CCPA | Privacy policy, data deletion UX, DPAs with Plaid/Stripe/Postmark |

### 5.3. Reliability

| Metric | Target |
|--------|--------|
| Uptime | ≥99% |
| Email parser accuracy | ≥85% per platform |
| Plaid graceful degradation | Manual mode + email parsing fallback when Plaid down |
| Backup | Daily B2 + PostgreSQL WAL |

---

## 6. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `user_signup_success` | /start creates account | channel_type, platform |
| `user_onboard_path_selected` | Choose path A/B/C | user_id, path |
| `user_onboard_completed` | First tx received | user_id, path, duration_min |
| `integration_connected` | Plaid/Stripe/PayPal/Shopify/Etsy linked | user_id, platform |
| `tx_received` | Any source captures tx | user_id, source, biz_tag |
| `tx_categorized` | User taps category | user_id, category, auto_or_manual |
| `tx_biz_tagged` | User toggles personal/business | user_id, from, to |
| `tx_limit_hit` | Free user hits 60 tx | user_id |
| `dashboard_visited` | User opens web dashboard | user_id, page |
| `plan_trial_started` | New signup | user_id |
| `plan_trial_expired` | Day 14 downgrade | user_id |
| `plan_upgrade_success` | Free → Pro/Solopreneur | user_id, tier, method |
| `email_parse_success` | Email parsed OK | user_id, platform |
| `email_parse_fail` | Email parse failed | user_id, platform, reason |

---

## 7. Appendix

### 7.1. Glossary

| Term | Definition |
|------|------------|
| **Plaid** | Open banking aggregator (US/CA). Read-only bank link for expenses. |
| **TrueLayer** | Open banking aggregator (UK). PSD2-based. |
| **Tink** | Open banking aggregator (EU). PSD2-based. |
| **OAuth** | Authorization protocol for connecting Stripe/PayPal/Shopify/Etsy without sharing passwords |
| **Payout email** | Notification email from e-com platforms when funds are deposited |
| **Canonical transaction** | Internal normalized schema for all sources |
| **P/B tag** | Personal vs Business classification on each transaction |
| **Auto-cat rule** | Pattern-based rule: merchant name matches → auto-assign category |

### 7.2. References
- [BRD-en v4.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-en.md)
- [TDD-en v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-en.md)
- [Market Strategy Overview](file:///Users/maingocanh/Projects/MyMoneyWent/docs/market-strategy-overview.md)
- [ADR-0001: Monorepo](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md)
- [PRD-vi (VN market)](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)
- [Plaid API docs](https://plaid.com/docs/)
- [Stripe Connect docs](https://docs.stripe.com/connect)
- [Shopify App API docs](https://shopify.dev/docs/api)
- [Etsy Open API docs](https://developers.etsy.com/documentation/)

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| v1.0.0-v1.6.0 | 2026-05-05 to 2026-05-07 | VN-derived content (SePay, VN banks, Hùng+ TAM). **DEPRECATED — superseded by v2.0.0.** |
| v2.0.0 | 2026-05-10 | **MAJOR REWRITE — Global market PRD:** Discarded all VN-derived content. Rebuilt from brd-en.md v4.0.0. (1) ICP: e-commerce solopreneur ($2K-50K/mo, multi-platform). (2) Capture: Plaid bank linking + Stripe/PayPal/Shopify/Etsy OAuth + payout email parsing. (3) Pricing: Free / Pro $6 / Solopreneur $12 + annual plans. (4) Web dashboard: Next.js read-only for transactions, full for settings/integrations. (5) Payment: Stripe Checkout (credit card + Apple Pay + Google Pay). (6) Channels: Telegram + Discord + Messenger (all 3 in MVP). (7) Commands: `/balance` and `/add` (new), no `/allocate`. (8) Auto-categorization rule engine (system defaults + user custom). (9) Personal/Business tag as first-class on every transaction. |

---

**End of Document**
