# My Money Went — Technical Design Document (TDD)

> **Version:** v1.0.0
> **Created:** 2026-05-10
> **Last updated:** 2026-05-10
> **Status:** Draft
> **References:** [BRD-en v4.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-en.md) · [PRD-en v2.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-en.md) · [TDD-vi v1.8.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) (shared foundation) · [ADR-0001](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md)
>
> **🌐 SCOPE NOTE:** This TDD specifies the **🌍 Global market technical architecture**. It shares foundation sections with [tdd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) (messenger interface, auth framework, admin tools, deployment). Global-specific sections: Plaid/TrueLayer/Tink bank integration, Stripe/PayPal/Shopify/Etsy OAuth, payout email parsers, web dashboard (Next.js), Stripe Checkout payment, `integrations` + `auto_cat_rules` tables. Per [ADR-0001](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md), Global code lives at `markets/global/`, shared foundation at `core/`.

---

## 1. Architecture overview

### 1.1. Architecture diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Telegram │ │ Discord  │ │Messenger │ │  Plaid   │ │ Postmark │  │
│  │ Bot API  │ │ Bot API  │ │ Send API │ │ Webhooks │ │ Inbound  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       │            │            │             │             │         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                             │
│  │ Stripe   │ │ PayPal   │ │Shopify/  │                             │
│  │ Connect  │ │ OAuth    │ │Etsy OAuth│                             │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                             │
└───────┼────────────┼────────────┼─────────────┼─────────────┼───────┘
        │            │            │             │             │
        ▼            ▼            ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │                   Router / Dispatcher                      │      │
│  │  • Per-user routing (token → user_id)                     │      │
│  │  • Tier limit checking                                    │      │
│  │  • Background task dispatch                               │      │
│  └─────────────────────┬──────────────────────────────────────┘      │
│                        │                                             │
│        ┌───────────────┼───────────────┐                             │
│        ▼               ▼               ▼                             │
│  ┌───────────┐  ┌────────────┐  ┌──────────────┐                    │
│  │ Handlers  │  │ Services   │  │ Integrations │                    │
│  │ • bot cmd │  │ • user_svc │  │ • plaid_svc  │                    │
│  │ • email   │  │ • tx_svc   │  │ • stripe_svc │                    │
│  │ • manage  │  │ • cat_svc  │  │ • paypal_svc │                    │
│  │ • report  │  │ • plan_svc │  │ • shopify_svc│                    │
│  └─────┬─────┘  └─────┬──────┘  │ • etsy_svc   │                    │
│        │               │         │ • email_parse│                    │
│        └───────────────┤         └──────┬───────┘                    │
│                        │                │                             │
│                        ▼                ▼                             │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │                  Data Access Layer (asyncpg)                │      │
│  └─────────────────────┬──────────────────────────────────────┘      │
│                        │                                             │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │            services/messenger.py (outbound)                │      │
│  │  → services/channels/{telegram,discord,messenger}.py       │      │
│  └────────────────────────────────────────────────────────────┘      │
└────────────────────────┼─────────────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼                           ▼
┌──────────────────┐        ┌──────────────────┐
│   PostgreSQL     │        │  Next.js Web     │
│   (Railway)      │        │  Dashboard       │
│   Multi-tenant   │        │  (Supabase Auth) │
└──────────────────┘        └──────────────────┘
```

### 1.2. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | PostgreSQL (shared with VN track) | Multi-tenant, ACID, shared foundation |
| ORM | Raw SQL (asyncpg) | Lightweight, full control |
| Bank data | Plaid (US/CA) + TrueLayer (UK) + Tink (EU) | Read-only, never stores credentials |
| E-com data | OAuth integrations (Stripe/PayPal/Shopify/Etsy) | Free APIs, no per-user cost |
| Income backup | Postmark Inbound (payout email parsing) | Covers long tail of platforms |
| Web dashboard | Next.js + Supabase Auth | SSR, React ecosystem, auth via magic link from bot |
| Payment | Stripe Checkout | Global coverage, Apple/Google Pay, recurring billing |
| Outbound | `services/messenger.py` interface | Same as VN track — shared foundation |
| Auto-categorization | Rule engine (pattern → category) | System defaults + user custom rules |

### 1.3. Shared vs Global-Specific

| Component | Location | Shared? |
|-----------|----------|---------|
| `messenger.send()` interface | `core/services/messenger.py` | ✅ Shared |
| Channel adapters (Telegram/Discord/Messenger) | `core/services/channels/` | ✅ Shared |
| Auth framework | `core/services/auth.py` | ✅ Shared |
| Admin tools | `core/services/admin.py` | ✅ Shared |
| DB schema (users, categories, bot_state, scheduled_jobs) | `core/db/` | ✅ Shared |
| Plaid integration | `markets/global/integrations/plaid.py` | ❌ Global only |
| TrueLayer/Tink integration | `markets/global/integrations/truelayer.py`, `tink.py` | ❌ Global only |
| Stripe/PayPal/Shopify/Etsy OAuth | `markets/global/integrations/` | ❌ Global only |
| Payout email parsers | `markets/global/parsers/` | ❌ Global only |
| Web dashboard | `markets/global/web/` | ❌ Global only |
| Stripe Checkout payment | `markets/global/payment/` | ❌ Global only |
| Auto-cat rules engine | `markets/global/services/rules.py` | ❌ Global only |
| SePay integration | `markets/vn/integrations/sepay.py` | ❌ VN only |
| VN bank email parsers | `markets/vn/parsers/` | ❌ VN only |
| VietQR payment | `markets/vn/payment/` | ❌ VN only |

---

## 2. Database Schema (Global-specific tables)

> **Note:** Core tables (`users`, `categories`, `sub_categories`, `transactions`, `bot_state`, `scheduled_jobs`, `admin_audit_log`, `analytics_events`) are defined in [tdd-vi.md §2.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) and shared across both markets. Below are **Global-specific additions.**

### 2.1. Global-specific DDL

```sql
-- ═══════════════════════════════════════════════════════
-- Integrations (Plaid + OAuth + email sources)
-- Replaces VN's bank_connections table for global track
-- ═══════════════════════════════════════════════════════
CREATE TABLE integrations (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(16) NOT NULL,              -- 'plaid' / 'stripe' / 'paypal' / 'shopify' / 'etsy' / 'email'
    provider        VARCHAR(32),                       -- specific provider: 'plaid_us', 'truelayer_uk', 'tink_eu'
    label           VARCHAR(128),                      -- user-friendly label ("Chase Checking", "My Shopify Store")
    
    -- OAuth tokens (encrypted at rest)
    access_token    TEXT,                               -- encrypted
    refresh_token   TEXT,                               -- encrypted
    token_expires_at TIMESTAMPTZ,
    
    -- Plaid-specific
    plaid_item_id   VARCHAR(64),                       -- Plaid Item ID
    plaid_cursor    TEXT,                               -- /transactions/sync cursor
    
    -- Status
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at    TIMESTAMPTZ,
    last_error      TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_integration_type CHECK (type IN ('plaid', 'stripe', 'paypal', 'shopify', 'etsy', 'email'))
);

CREATE INDEX idx_integration_user ON integrations(user_id, type);
CREATE INDEX idx_integration_sync ON integrations(last_sync_at) WHERE active = TRUE;

-- ═══════════════════════════════════════════════════════
-- Auto-categorization Rules (user custom + system defaults)
-- ═══════════════════════════════════════════════════════
CREATE TABLE auto_cat_rules (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE, -- NULL = system default rule
    pattern         VARCHAR(256) NOT NULL,             -- merchant name pattern (case-insensitive contains)
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    biz_tag         VARCHAR(16) DEFAULT 'unknown',     -- 'personal' / 'business' / 'unknown'
    priority        INTEGER NOT NULL DEFAULT 0,         -- higher = checked first
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,    -- system defaults not deletable by user
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_biz_tag CHECK (biz_tag IN ('personal', 'business', 'unknown'))
);

CREATE INDEX idx_rules_user ON auto_cat_rules(user_id) WHERE active = TRUE;

-- ═══════════════════════════════════════════════════════
-- Transactions additions (Global-specific columns)
-- ═══════════════════════════════════════════════════════
-- These columns extend the shared transactions table:
-- ALTER TABLE transactions ADD COLUMN biz_tag VARCHAR(16) DEFAULT 'unknown';
-- ALTER TABLE transactions ADD COLUMN currency VARCHAR(3) DEFAULT 'USD';
-- ALTER TABLE transactions ADD COLUMN platform_fee BIGINT; -- fee extracted from platform
-- ALTER TABLE transactions ADD CONSTRAINT chk_biz_tag CHECK (biz_tag IN ('personal', 'business', 'unknown'));
```

### 2.2. Key Queries (Global-specific)

```sql
-- P&L: Business income vs expense this month
SELECT 
    direction,
    SUM(amount) as total,
    COUNT(*) as tx_count
FROM transactions
WHERE user_id = $1 AND month_key = $2 AND biz_tag = 'business' AND confirmed = TRUE
GROUP BY direction;

-- Integration status for user
SELECT type, label, active, last_sync_at, last_error
FROM integrations
WHERE user_id = $1 AND active = TRUE
ORDER BY type;

-- Auto-categorize: find matching rule for merchant
SELECT r.category_id, r.biz_tag
FROM auto_cat_rules r
WHERE (r.user_id = $1 OR r.is_system = TRUE) AND r.active = TRUE
  AND $2 ILIKE '%' || r.pattern || '%'
ORDER BY r.priority DESC, r.is_system ASC
LIMIT 1;
```

---

## 3. API Design

### 3.1. Endpoints

| Method | Path | Source | Description |
|--------|------|--------|-------------|
| POST | `/webhook/telegram` | Telegram Bot API | Telegram updates |
| GET/POST | `/webhook/messenger` | Meta | Messenger webhook (verify + messages) |
| POST | `/webhook/discord` | Discord | Interaction endpoint (Ed25519 verify) |
| POST | `/inbound/{token}` | Postmark | Per-user payout email forwarding |
| POST | `/plaid/webhook` | Plaid | Plaid transaction updates, item status |
| GET | `/plaid/link-token` | Web dashboard | Generate Plaid Link token for frontend |
| POST | `/plaid/exchange` | Web dashboard | Exchange Plaid public_token → access_token |
| GET | `/oauth/{platform}/authorize` | Web dashboard | Initiate OAuth for Stripe/PayPal/Shopify/Etsy |
| GET | `/oauth/{platform}/callback` | Browser redirect | OAuth callback handler |
| POST | `/stripe/webhook` | Stripe | Payment webhook (checkout.session.completed) |
| POST | `/trigger/{job_type}` | Internal/Cron | Manual job trigger |
| GET | `/` | Health check | Status OK |
| GET | `/health` | Monitoring | Detailed health (DB, Plaid, integrations) |

### 3.2. Web Dashboard API (Next.js → FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/me` | Current user profile + plan |
| GET | `/api/v1/transactions` | List transactions (paginated, filterable) |
| GET | `/api/v1/categories` | List categories |
| GET | `/api/v1/integrations` | List connected integrations |
| GET | `/api/v1/pnl` | P&L summary (monthly/quarterly) |
| GET | `/api/v1/rules` | Auto-categorization rules |
| POST | `/api/v1/rules` | Create custom rule (Pro+) |
| DELETE | `/api/v1/rules/{id}` | Delete custom rule |
| GET | `/api/v1/export` | CSV/PDF export (Pro+) |

---

## 4. Module Structure (Target)

```
MyMoneyWent/
├── core/                            # Shared foundation
│   ├── db.py                        # asyncpg pool + shared queries
│   ├── models.py                    # Pydantic schemas
│   ├── config.py                    # Environment config
│   ├── services/
│   │   ├── messenger.py             # Outbound abstraction
│   │   ├── channels/
│   │   │   ├── base.py              # BaseSender ABC
│   │   │   ├── telegram.py          # TelegramSender
│   │   │   ├── discord.py           # DiscordSender
│   │   │   └── messenger.py         # MessengerSender
│   │   ├── user_service.py          # User CRUD
│   │   ├── category_service.py      # Category CRUD
│   │   ├── plan_service.py          # Tier limits, trial
│   │   ├── scheduler_service.py     # Per-user jobs
│   │   └── admin.py                 # Admin auth + audit
│   └── handlers/
│       ├── manage.py                # /manage CRUD
│       ├── reports.py               # /today, /balance, /weekly
│       └── settings.py              # /settings
│
├── markets/
│   ├── global/                      # Global-specific
│   │   ├── integrations/
│   │   │   ├── plaid.py             # Plaid Link + /transactions/sync
│   │   │   ├── truelayer.py         # TrueLayer (UK)
│   │   │   ├── tink.py              # Tink (EU)
│   │   │   ├── stripe_connect.py    # Stripe Connect OAuth
│   │   │   ├── paypal.py            # PayPal OAuth
│   │   │   ├── shopify.py           # Shopify App OAuth
│   │   │   └── etsy.py              # Etsy OAuth
│   │   ├── parsers/
│   │   │   ├── base.py              # Base payout email parser
│   │   │   ├── stripe_email.py      # Stripe payout emails
│   │   │   ├── paypal_email.py      # PayPal payout emails
│   │   │   ├── shopify_email.py     # Shopify payout emails
│   │   │   └── etsy_email.py        # Etsy payout emails
│   │   ├── services/
│   │   │   ├── rules.py             # Auto-categorization engine
│   │   │   └── pnl_service.py       # P&L calculation
│   │   ├── payment/
│   │   │   └── stripe_checkout.py   # Stripe Checkout billing
│   │   ├── web/                     # Next.js dashboard
│   │   │   ├── package.json
│   │   │   ├── pages/
│   │   │   └── components/
│   │   └── handlers/
│   │       ├── onboarding.py        # 3-path (Plaid/OAuth/Email)
│   │       └── transaction.py       # Category + P/B tagging
│   │
│   └── vn/                          # VN-specific (see tdd-vi.md)
│       ├── integrations/sepay.py
│       ├── parsers/                  # VN bank email parsers
│       ├── payment/vietqr.py
│       └── handlers/onboarding.py
│
├── main.py                          # FastAPI app, route registration
├── migrations/
├── tests/
├── docs/
├── requirements.txt
├── railway.toml
└── .env.example
```

---

## 5. Deployment & Infrastructure

### 5.1. Environment Variables (Global-specific)

```bash
# === Plaid ===
PLAID_CLIENT_ID=<plaid client id>
PLAID_SECRET=<plaid secret>
PLAID_ENV=sandbox|development|production
PLAID_WEBHOOK_URL=https://api.mymoneywent.com/plaid/webhook

# === E-com OAuth ===
STRIPE_CLIENT_ID=<stripe connect client id>
STRIPE_CLIENT_SECRET=<stripe connect secret>
PAYPAL_CLIENT_ID=<paypal client id>
PAYPAL_CLIENT_SECRET=<paypal secret>
SHOPIFY_API_KEY=<shopify app api key>
SHOPIFY_API_SECRET=<shopify app secret>
ETSY_API_KEY=<etsy api key>

# === Stripe Checkout (billing) ===
STRIPE_PUBLISHABLE_KEY=<stripe pk>
STRIPE_SECRET_KEY=<stripe sk>
STRIPE_WEBHOOK_SECRET=<stripe webhook signing secret>
STRIPE_PRICE_PRO_MONTHLY=price_xxx
STRIPE_PRICE_PRO_ANNUAL=price_xxx
STRIPE_PRICE_SOLO_MONTHLY=price_xxx
STRIPE_PRICE_SOLO_ANNUAL=price_xxx

# === Web Dashboard ===
NEXT_PUBLIC_API_URL=https://api.mymoneywent.com
SUPABASE_URL=<supabase url>
SUPABASE_ANON_KEY=<supabase anon key>
SUPABASE_SERVICE_KEY=<supabase service key>

# === Postmark (payout email parsing) ===
POSTMARK_INBOUND_DOMAIN=in.mymoneywent.com
POSTMARK_SERVER_TOKEN=<postmark token>

# === Shared (see tdd-vi.md §5.2 for full list) ===
TELEGRAM_BOT_TOKEN=<telegram bot token>
DISCORD_BOT_TOKEN=<discord bot token>
DISCORD_PUBLIC_KEY=<ed25519 public key>
FB_PAGE_ACCESS_TOKEN=<messenger token>
FB_APP_SECRET=<facebook app secret>
DATABASE_URL=postgresql://...
WEBHOOK_BASE_URL=https://api.mymoneywent.com
ADMIN_TELEGRAM_IDS=<comma-separated>
SENTRY_DSN=<sentry dsn>
```

### 5.2. Cost Profile (Global-specific)

| Item | 10 users | 100 users | 500 users |
|------|----------|-----------|-----------|
| Railway (app + Postgres) | $5 | $15-25 | $40-80 |
| **Plaid** (~$1.50-3/user blended) | $15-30 | **$150-300** | **$750-1500** |
| Postmark | $10 | $10 | $35 |
| Supabase (dashboard auth) | $0 (free tier) | $25 | $25 |
| Backblaze B2 | $1 | $1 | $2 |
| Domain + SSL | $1 | $1 | $1 |
| **Total** | **~$32-47** | **~$202-362** | **~$853-1643** |

> **Critical:** Plaid dominates cost. Per BRD §5.4, Free tier should NOT include Plaid (e-com + email + manual only) to control cost.

---

## 6. Integration Specs

### 6.1. Plaid Integration

```python
# Pseudocode: Plaid transaction sync
async def sync_plaid_transactions(user_id: int, integration_id: int):
    integration = await db.get_integration(integration_id)
    
    # Use /transactions/sync with cursor for incremental updates
    response = plaid_client.transactions_sync(
        access_token=decrypt(integration.access_token),
        cursor=integration.plaid_cursor,
    )
    
    for tx in response.added:
        canonical = normalize_plaid_tx(tx)
        canonical.biz_tag = 'personal'  # default for bank tx
        canonical = await apply_auto_cat_rules(user_id, canonical)
        await process_transaction(user_id, canonical, source='plaid')
    
    # Update cursor
    await db.update_integration(integration_id, plaid_cursor=response.next_cursor)
```

### 6.2. E-com OAuth Flow

```
User clicks "Connect Stripe" in bot or dashboard
    │
    ▼
GET /oauth/stripe/authorize → redirect to Stripe OAuth page
    │
    ▼
User authorizes → Stripe redirects to /oauth/stripe/callback?code=xxx
    │
    ▼
Exchange code → access_token + refresh_token
    │
    ▼
Store encrypted tokens in integrations table
    │
    ▼
Pull initial payouts/transactions → canonical schema → pipeline
```

### 6.3. Payout Email Parsing

Same architecture as VN bank email parsing but different parsers:

| Platform | Key parsed fields | Example subject line |
|----------|-------------------|---------------------|
| Stripe | payout amount, arrival date, fee | "Your Stripe payout of $1,234.56 is on the way" |
| PayPal | payout amount, transaction ID | "You've got money: $500.00" |
| Shopify | payout amount, order count | "Shopify payout: $890.00 deposited" |
| Etsy | deposit amount, listing fees | "Your Etsy deposit of $345.67" |

---

## 7. Testing Strategy

### 7.1. Unit Tests

| Module | Test focus | Min coverage |
|--------|-----------|-------------|
| Plaid integration | Webhook handling, sync, error recovery | 85% |
| OAuth integrations (4 platforms) | Token exchange, refresh, data pull | 80% |
| Payout email parsers (4 platforms) | 50+ samples/platform, edge cases | 90% |
| Auto-cat rules engine | Pattern matching, priority, tier limits | 85% |
| P&L calculation | Business/Personal split, multi-source aggregation | 90% |
| Stripe Checkout | Webhook verify, plan upgrade/downgrade | 90% |

### 7.2. Integration Tests

| Flow | Steps |
|------|-------|
| Plaid onboarding → first sync | Link token → connect → sync → categorize |
| Stripe OAuth → first payout | Authorize → pull → categorize → P&L |
| Email → categorize | Postmark webhook → parse → categorize |
| Free limit → upgrade | 60 tx → reject #61 → Stripe Checkout → upgrade |
| Dashboard auth | Bot magic link → dashboard session → view P&L |

---

## 8. Web Dashboard Architecture

### 8.1. Auth Flow

```
User types /dashboard in bot
    │
    ▼
Bot generates time-limited magic link (JWT, 15 min TTL)
    │
    ▼
User clicks link → Next.js app → exchange JWT for Supabase session
    │
    ▼
Supabase session cookie → authenticated API requests to FastAPI backend
```

### 8.2. Pages

| Route | Component | Data source |
|-------|-----------|-------------|
| `/` | Dashboard (P&L overview, charts) | `GET /api/v1/pnl` |
| `/transactions` | Transaction list (read-only) | `GET /api/v1/transactions` |
| `/integrations` | Connect/manage integrations | `GET /api/v1/integrations` |
| `/categories` | Category + rules management | `GET /api/v1/categories`, `/rules` |
| `/settings` | Plan, billing, timezone, notifications | `GET /api/v1/me` |

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| v1.0.0 | 2026-05-10 | **Initial Global TDD:** Architecture for Plaid + e-com OAuth + payout email capture stack. Global-specific tables (integrations, auto_cat_rules). Module structure with `core/` + `markets/global/` separation. Web dashboard (Next.js + Supabase). Stripe Checkout payment. Plaid cost profile. Env vars. Integration specs. Testing strategy. |

---

**End of Document**
