# Tiền Về Nơi Đâu — Technical Design Document (TDD)

> **Version:** v1.8.1
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-10
> **Trạng thái:** Draft
> **Tham chiếu:** [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.7.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [Feature: SaaS Refactor](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) · [Feature: Payment](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md) · [Feature: Messenger](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) · [Impl Plan VietQR+Email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) · [Feature: Admin Tools](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-admin-tools.md) · [DR Runbook](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md) · [Observability](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md)
>
> **🌐 SCOPE NOTE:** TDD này cover **shared technical foundation** (DB schema, FastAPI architecture, messenger interface, auth) + **VN-specific implementations** (SePay webhook, VN bank email parsers, VietQR payment). **Global market** có TDD riêng — [tdd-en.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-en.md) — với capture stack riêng (Plaid/TrueLayer/Tink + e-com OAuth + Stripe Checkout payment). Shared foundation sections (§1-2 architecture, §2 DB schema core tables, §5 deployment) apply cho cả 2 markets. Per [ADR-0001](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md), VN code lives at `markets/vn/`, shared foundation at `core/`.
>
> **Change v1.8.1 vs v1.8.0:** Renamed `tdd.md` → `tdd-vi.md`. Thêm SCOPE NOTE. Title "MyMoneyWent" → "Tiền Về Nơi Đâu" (VN branding). Header refs updated to sibling docs.

---

## 1. Tổng quan kiến trúc

### 1.1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ Telegram │  │Messenger │  │ SePay    │  │ Postmark     │    │
│  │ Bot API  │  │FB Page   │  │ Webhook  │  │ Inbound      │    │
│  └─────┬────┘  └─────┬────┘  └────┬─────┘  └──────┬───────┘    │
│        │             │            │               │             │
└────────┼─────────────┼────────────┼───────────────┼─────────────┘
         │             │            │               │
         ▼             ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                           │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │/webhook/ │ │/webhook/ │ │/hook/    │ │/inbound/{token}  │   │
│  │telegram  │ │messenger │ │{token}   │ │Email parser      │   │
│  └─────┬────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
│        │               │                       │                │
│        ▼               ▼                       ▼                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Router / Dispatcher                    │   │
│  │  • Per-user routing (token → user_id)                    │   │
│  │  • Tier limit checking                                   │   │
│  │  • Background task dispatch                              │   │
│  └─────────────────────┬────────────────────────────────────┘   │
│                        │                                        │
│        ┌───────────────┼───────────────┐                        │
│        ▼               ▼               ▼                        │
│  ┌───────────┐  ┌────────────┐  ┌──────────────┐               │
│  │ Handlers  │  │ Services   │  │ Schedulers   │               │
│  │ • sepay   │  │ • user_svc │  │ • APScheduler│               │
│  │ • email   │  │ • tx_svc   │  │ • Per-user   │               │
│  │ • manage  │  │ • cat_svc  │  │   timezone   │               │
│  │ • report  │  │ • plan_svc │  │              │               │
│  │ • alloc   │  │            │  │              │               │
│  └─────┬─────┘  └─────┬──────┘  └──────┬───────┘               │
│        │               │               │                        │
│        └───────────────┼───────────────┘                        │
│                        ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Data Access Layer                      │   │
│  │  • asyncpg connection pool                               │   │
│  │  • Query builder (raw SQL, no ORM)                       │   │
│  └─────────────────────┬────────────────────────────────────┘   │
│                        │                                        │
└────────────────────────┼────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   PostgreSQL     │
              │   (Railway)      │
              │   Multi-tenant   │
              └──────────────────┘
```

### 1.2. Key Design Decisions

| Decision | Choice | Lý do |
|----------|--------|-------|
| Database | PostgreSQL (thay Google Sheets) | Multi-tenant, ACID, query performance |
| ORM | Raw SQL (asyncpg) | Lightweight, full control, no magic |
| Email service | Postmark Inbound | Reliability, simple API, $10/mo tier |
| Background tasks | FastAPI BackgroundTasks + APScheduler | Simple, in-process, đủ cho 500 users |
| Auth | Per-user token in URL (webhook) + telegram_id (bot) | Stateless, simple |
| Migration | Google Sheets → PostgreSQL | Phase 1 milestone |
| Outbound messaging | `services/messenger.py` interface (`messenger.send(user_id, payload)`) routing tới `services/channels/{telegram,messenger,discord}.py` adapter | Handlers never call Telegram/Messenger/Discord directly; channel-agnostic interface enables multi-channel build + C9 queue + C8 bot pool without handler refactor |
| Multi-channel | `users.channel_type` + `users.channel_user_id`, single-channel per user (chọn 1 lúc onboarding) | Telegram + Messenger + Discord, schema cho phép thêm Zalo/WhatsApp Phase 3+ chỉ bằng cách thêm enum value |
| QR display | `services/qr_generator.py` compose vietqr.io public image URL | Image rendered server-side bởi vietqr.io (third-party hosted, free). Tradeoff: leak ref/account/amount privacy + uptime dependency. True self-host (EMVCo offline encoder) defer Phase 7+. Detail tradeoffs: [feature-spec-payment-bank-transfer §2.4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md) |
| Admin auth/audit | `ADMIN_TELEGRAM_IDS` + `admin_audit_log` | Admin tooling affects schema/auth from Phase 1, not a Phase 6 afterthought |

### 1.3. Migration Strategy (Google Sheets → PostgreSQL)

```
Phase 1 Legacy (current):
  sheets.py ──→ Google Sheets API ──→ Google Sheets

Phase 1 Target:
  db.py ──→ asyncpg ──→ PostgreSQL (Railway)

Migration steps:
  1. Create PostgreSQL schema (DDL)
  2. Create db.py with same interface as sheets.py
  3. Swap imports: `import db as sh` thay `import sheets as sh`
  4. Import founder's existing data (Apr-Sep 2026)
  5. Remove sheets.py dependency
```

---

### 1.4. Outbound Messaging Abstraction

All outbound messages MUST go through `services/messenger.py`:

```python
await messenger.send(user_id, {
    "type": "text" | "image" | "picker",
    "text": "...",            # for type=text
    "url": "...",             # for type=image (vietqr URL etc.)
    "caption": "...",         # for type=image
    "reply_markup": {...},    # optional, for type=text
    "tag": "ACCOUNT_UPDATE",  # optional, for Messenger MESSAGE_TAG outbound
})
```

**Rules:**
- Handlers/services MUST NOT import `services/channels/telegram.py` hoặc `services/channels/messenger.py` hoặc `services/channels/discord.py` directly. `services/messenger.py` resolve channel + dispatch tới đúng adapter.
- `Messenger.send()` lookup `users.channel_type` (`'telegram'` | `'messenger'` | `'discord'`) → route tới `TelegramSender`, `MessengerSender`, hoặc `DiscordSender`.
- Channel adapter pattern (`services/channels/`):
    - `base.py` — `BaseSender` ABC với `send_text()`, `send_image()`, `send_picker()`, `edit_message()`
    - `telegram.py` — `TelegramSender` qua Bot API (`sendMessage`, `sendPhoto`, ...)
    - `messenger.py` — `MessengerSender` qua Meta Send API (`/me/messages` với attachment/quick_replies)
    - `discord.py` — `DiscordSender` qua Discord API (Rich Embeds + Action Row buttons + file attachments, Ed25519 signature verify)
- Initial implementation direct-send. At 100-150 active users, C9 swaps internal implementation to queue-backed delivery (`outbound_messages`) without changing handlers.
- `tag` field: ignore by Telegram, dùng bởi Messenger cho `messaging_type=MESSAGE_TAG` outbound ngoài 24h window. Subscription-related outbound (match notification, expiry warning, recurring renewal) phải set `tag="ACCOUNT_UPDATE"`.
- Grep acceptance: handler/service files have 0 direct `await tg.send_*`, 0 direct Telegram/Meta/Discord HTTP calls outside `services/channels/`.

This is a Phase 1 foundation decision because retrofitting queue/bot-pool/multi-channel delivery later would otherwise require touching every handler. Channel adapter pattern cho phép thêm channel mới chỉ bằng cách thêm 1 file `services/channels/{name}.py` + 1 entry adapter dict.

> **Detail spec:** [feature-messenger-channel.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) cho Messenger adapter, [feature-discord-channel.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-discord-channel.md) cho Discord adapter (slash commands + embeds + Ed25519), [implementation-plan-payment-vietqr-email.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) cho `send_image()` extension + VietQR flow.

---

## 2. Database Schema

### 2.1. DDL

```sql
-- ═══════════════════════════════════════════════════════
-- Users
-- ═══════════════════════════════════════════════════════
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,

    -- Channel identity (multi-channel: Telegram + Messenger + Discord)
    channel_type    VARCHAR(16) NOT NULL,          -- 'telegram' | 'messenger' | 'discord'
    channel_user_id VARCHAR(64) NOT NULL,          -- Telegram telegram_id (str-cast) hoặc Messenger PSID hoặc Discord User ID (snowflake)
    chat_id         BIGINT,                         -- Telegram chat.id (NULL cho Messenger — PSID là chat identifier)
    last_user_message_at TIMESTAMPTZ,              -- last inbound message — needed cho Messenger 24h window check

    -- Legacy column — keep cho historic data + analytics, nullable sau multi-channel migration
    telegram_id     BIGINT,                         -- nullable; cho Messenger user = NULL

    username        VARCHAR(64),
    display_name    VARCHAR(128),

    -- Tokens
    webhook_token   VARCHAR(32) NOT NULL UNIQUE,   -- 24-char URL-safe
    inbound_email   VARCHAR(64) UNIQUE,            -- u{id}@in.tienvenoidau.com

    -- Plan & Trial
    plan            VARCHAR(16) NOT NULL DEFAULT 'free',  -- free/pro/business
    trial_ends_at   TIMESTAMPTZ,
    plan_expires_at TIMESTAMPTZ,                   -- for paid plans

    -- Settings
    timezone        VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    locale          VARCHAR(5) NOT NULL DEFAULT 'vi',  -- 'vi' | 'en'; auto-detected from Telegram language_code then user confirms
    daily_recap_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    onboard_path    VARCHAR(8),                    -- 'sepay_quick'/'sepay_wizard'/'email'

    -- Operational state
    invalid_channel BOOLEAN NOT NULL DEFAULT FALSE, -- set khi user block Page (Messenger error 10) hoặc bot suspended
    bot_id          INTEGER,                        -- foreign key tới bots(id) khi C8 bot pool live (Telegram only)

    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_plan CHECK (plan IN ('free', 'pro', 'business')),
    CONSTRAINT chk_channel_type CHECK (channel_type IN ('telegram', 'messenger', 'discord')),
    CONSTRAINT chk_locale CHECK (locale IN ('vi', 'en')),
    CONSTRAINT uniq_channel_user UNIQUE (channel_type, channel_user_id)
);

CREATE INDEX idx_users_webhook_token ON users(webhook_token);
CREATE INDEX idx_users_channel ON users(channel_type, channel_user_id);
CREATE INDEX idx_users_telegram_legacy ON users(telegram_id) WHERE telegram_id IS NOT NULL;

-- ═══════════════════════════════════════════════════════
-- Bank Connections (SePay + Email sources)
-- ═══════════════════════════════════════════════════════
CREATE TABLE bank_connections (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(16) NOT NULL,              -- 'sepay' / 'email'
    bank_name   VARCHAR(32),                       -- 'tcb', 'mb', 'vcb', etc.
    label       VARCHAR(64),                       -- user-friendly label
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_conn_type CHECK (type IN ('sepay', 'email'))
);

CREATE INDEX idx_bank_conn_user ON bank_connections(user_id);

-- ═══════════════════════════════════════════════════════
-- Categories
-- ═══════════════════════════════════════════════════════
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug        VARCHAR(64) NOT NULL,              -- machine-friendly ID
    name        VARCHAR(128) NOT NULL,             -- display name with emoji
    allocated   BIGINT NOT NULL DEFAULT 0,         -- VND integer; 0 = tracking mode
    daily_cap   BIGINT,                             -- VND integer; null = no daily limit
    month_key   VARCHAR(7) NOT NULL,               -- '2026-05'
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, slug, month_key)
);

CREATE INDEX idx_cat_user_month ON categories(user_id, month_key);

-- ═══════════════════════════════════════════════════════
-- Sub-categories
-- ═══════════════════════════════════════════════════════
CREATE TABLE sub_categories (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key         VARCHAR(64) NOT NULL,
    label       VARCHAR(128) NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE(category_id, key)
);

-- ═══════════════════════════════════════════════════════
-- Transactions
-- ═══════════════════════════════════════════════════════
CREATE TABLE transactions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tx_date         TIMESTAMPTZ NOT NULL,
    description     VARCHAR(512),
    direction       VARCHAR(4) NOT NULL,           -- 'in' / 'out'
    amount          BIGINT NOT NULL,                -- VND integer (no sub-unit cho VND)
    ref_code        VARCHAR(64),
    source          VARCHAR(32) NOT NULL DEFAULT 'sepay',  -- 'sepay'/'email_tcb'/etc.
    category_id     INTEGER REFERENCES categories(id),
    sub_category_id INTEGER REFERENCES sub_categories(id),
    confirmed       BOOLEAN NOT NULL DEFAULT FALSE,
    month_key       VARCHAR(7) NOT NULL,           -- '2026-05'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, ref_code),
    CONSTRAINT chk_direction CHECK (direction IN ('in', 'out'))
);

CREATE INDEX idx_tx_user_month ON transactions(user_id, month_key);
CREATE INDEX idx_tx_user_date ON transactions(user_id, tx_date);
CREATE INDEX idx_tx_dedup ON transactions(user_id, ref_code);

-- ═══════════════════════════════════════════════════════
-- Bot State (conversation state machine)
-- ═══════════════════════════════════════════════════════
CREATE TABLE bot_state (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    step        VARCHAR(48),                       -- 'await_parent'|'await_sub'|'await_freetext'|'await_alloc_amount'|'await_new_bucket_name'|'await_new_bucket_amount'|'await_daily_excuse'|'await_manage_amount'|'await_manage_rename'|'await_sub_rename'|'await_add_cat_name'|'await_add_cat_amount'|'await_inline_new_cat_name'|NULL (idle)
    payload     JSONB NOT NULL DEFAULT '{}',       -- per-step context: {parent_category_id, tx_id, ...}
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexable status cho monitoring "user nào đang stuck trong state X"
CREATE INDEX idx_bot_state_step ON bot_state(step) WHERE step IS NOT NULL;

-- ═══════════════════════════════════════════════════════
-- Scheduled Jobs (per-user)
-- ═══════════════════════════════════════════════════════
CREATE TABLE scheduled_jobs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type    VARCHAR(32) NOT NULL,              -- 'daily_recap'/'weekly'/etc.
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_utc TIMESTAMPTZ,
    last_run_utc TIMESTAMPTZ,
    config      JSONB DEFAULT '{}',

    UNIQUE(user_id, job_type)
);

CREATE INDEX idx_jobs_next_run ON scheduled_jobs(next_run_utc) WHERE enabled = TRUE;

-- ═══════════════════════════════════════════════════════
-- Monthly Reports (archived)
-- ═══════════════════════════════════════════════════════
CREATE TABLE monthly_reports (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month_key   VARCHAR(7) NOT NULL,
    category_name VARCHAR(128),
    allocated   BIGINT,                            -- VND integer
    spent       BIGINT,
    remaining   BIGINT,
    pct         INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════
-- Payment — Pending Payments (user requested upgrade)
-- See docs/features/feature-payment.md for full schema rationale
-- ═══════════════════════════════════════════════════════
CREATE TABLE pending_payments (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ref_code        VARCHAR(32) UNIQUE NOT NULL,        -- PAY-{user_id}-{plan}-{period}-{nonce4}
    plan            VARCHAR(16) NOT NULL,               -- 'pro'|'business'
    period          VARCHAR(8) NOT NULL,                -- 'monthly'|'annual'
    expected_amount BIGINT NOT NULL,                    -- VND integer
    status          VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,               -- created_at + 24h
    matched_at      TIMESTAMPTZ,
    -- NOTE: bỏ matched_match_id (was circular FK). Reverse query qua payment_matches.pending_payment_id

    CONSTRAINT chk_payment_status CHECK (status IN
        ('pending', 'matched', 'expired', 'cancelled', 'manual_review'))
);

CREATE INDEX idx_pending_user ON pending_payments(user_id, status);
CREATE INDEX idx_pending_expires ON pending_payments(expires_at)
    WHERE status = 'pending';

-- ═══════════════════════════════════════════════════════
-- Payment — Match log (each confirmed transfer ↔ pending)
-- ═══════════════════════════════════════════════════════
CREATE TABLE payment_matches (
    id              SERIAL PRIMARY KEY,
    pending_payment_id INTEGER REFERENCES pending_payments(id),
    source          VARCHAR(32) NOT NULL,               -- 'sepay'|'email_tcb'|'email_mb'|'manual'|'email_tcb_platform'|'email_mb_platform'
    source_ref_code VARCHAR(64),                        -- referenceCode từ webhook (nullable)
    dedup_key       VARCHAR(128) NOT NULL UNIQUE,       -- source-scoped retry dedup (see payment spec §3.1); cross-source handled by pending status lock
    amount          BIGINT NOT NULL,
    raw_description TEXT NOT NULL,
    match_layer     INTEGER NOT NULL,                   -- 1=exact ref, 2=fuzzy token, 3=amount-unique, 4=manual
    match_confidence VARCHAR(8) NOT NULL,               -- 'high'|'medium'|'low'
    status          VARCHAR(16) NOT NULL DEFAULT 'matched',
                                                        -- 'matched'|'refunded'|'credited'|'voided'
    matched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by     VARCHAR(64),                        -- 'auto' | admin telegram_id
    refunded_at     TIMESTAMPTZ,
    refund_notes    TEXT,

    CONSTRAINT chk_confidence CHECK (match_confidence IN ('high', 'medium', 'low')),
    CONSTRAINT chk_match_status CHECK (status IN ('matched', 'refunded', 'credited', 'voided'))
);

CREATE INDEX idx_matches_pending ON payment_matches(pending_payment_id);
CREATE INDEX idx_matches_status ON payment_matches(status) WHERE status != 'matched';

-- ═══════════════════════════════════════════════════════
-- Payment — Unmatched (admin review queue)
-- ═══════════════════════════════════════════════════════
CREATE TABLE unmatched_payments (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(32) NOT NULL,               -- 'sepay'|'email_tcb_platform'|'email_mb_platform'|'manual'
    source_ref_code VARCHAR(64),                        -- nullable
    dedup_key       VARCHAR(128) NOT NULL UNIQUE,       -- same source-scoped formula as payment_matches.dedup_key
    amount          BIGINT NOT NULL,
    raw_description TEXT NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending_review',
    resolved_by     VARCHAR(64),
    resolved_at     TIMESTAMPTZ,
    notes           TEXT
);

CREATE INDEX idx_unmatched_pending ON unmatched_payments(status)
    WHERE status = 'pending_review';

-- ═══════════════════════════════════════════════════════
-- Update users for plan tracking (added by Phase 6 payment work)
-- ═══════════════════════════════════════════════════════
-- ALTER TABLE users ADD COLUMN plan_grace_until TIMESTAMPTZ;  -- 7-day grace
-- ALTER TABLE users ADD COLUMN billing_period VARCHAR(8);      -- 'monthly'|'annual'
-- (plan_expires_at đã có từ Phase 3 pricing logic)

-- ═══════════════════════════════════════════════════════
-- Admin Audit Log (Phase 1 foundation)
-- Detail spec: docs/features/feature-admin-tools.md (write before Phase 1 dev)
-- ═══════════════════════════════════════════════════════
CREATE TABLE admin_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    admin_telegram_id BIGINT NOT NULL,
    command         VARCHAR(64) NOT NULL,
    target_user_id  INTEGER REFERENCES users(id),
    payload         JSONB,
    result          VARCHAR(16),                    -- 'success'|'fail'|'denied'
    error_message   TEXT,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_admin_audit_admin ON admin_audit_log(admin_telegram_id, executed_at DESC);
CREATE INDEX idx_admin_audit_target ON admin_audit_log(target_user_id, executed_at DESC);

-- ═══════════════════════════════════════════════════════
-- Analytics Events
-- ═══════════════════════════════════════════════════════
CREATE TABLE analytics_events (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER,
    event_name  VARCHAR(64) NOT NULL,
    properties  JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analytics_event ON analytics_events(event_name, created_at);
```

### 2.2. Key Queries

```sql
-- Get active categories for user + month
SELECT * FROM categories
WHERE user_id = $1 AND month_key = $2 AND active = TRUE
ORDER BY created_at;

-- Get monthly spending per category (outgoing only)
SELECT c.id, c.name, c.allocated, c.daily_cap,
       COALESCE(SUM(t.amount), 0) as spent
FROM categories c
LEFT JOIN transactions t ON t.category_id = c.id
    AND t.direction = 'out' AND t.confirmed = TRUE
WHERE c.user_id = $1 AND c.month_key = $2 AND c.active = TRUE
GROUP BY c.id ORDER BY c.created_at;

-- Fuzzy dedup check (cross-source, 3-minute window)
SELECT EXISTS(
    SELECT 1 FROM transactions
    WHERE user_id = $1
      AND amount = $2
      AND direction = $3
      AND ABS(EXTRACT(EPOCH FROM (tx_date - $4::timestamptz))) < 180
) as is_duplicate;

-- Count transactions this month (for Free tier limit)
SELECT COUNT(*) FROM transactions
WHERE user_id = $1 AND month_key = $2;

-- Jobs ready to run
SELECT sj.*, u.telegram_id, u.timezone
FROM scheduled_jobs sj
JOIN users u ON u.id = sj.user_id
WHERE sj.enabled = TRUE AND sj.next_run_utc <= NOW();
```

---

## 3. API Design

### 3.1. Endpoints

| Method | Path | Source | Mô tả |
|--------|------|--------|-------|
| POST | `/webhook/telegram` | Telegram Bot API | Telegram updates (commands + callbacks). Renamed từ `/webhook` cũ. |
| GET | `/webhook/messenger` | Meta verification | Trả `hub.challenge` khi `hub.verify_token` match `FB_VERIFY_TOKEN` env. |
| POST | `/webhook/messenger` | Meta Page webhook | Messages + postbacks. Verify `X-Hub-Signature-256` header với `FB_APP_SECRET`. |
| POST | `/webhook/discord` | Discord Interaction endpoint | Slash commands + button clicks. Verify `X-Signature-Ed25519` header với `DISCORD_PUBLIC_KEY`. |
| POST | `/hook/{token}` | SePay | **Per-user** bank transaction webhooks (token = `users.webhook_token`) |
| POST | `/hook/{PLATFORM_TOKEN}` | SePay | **Platform** payment webhooks — routed to `payment_matcher` thay vì user pipeline |
| POST | `/inbound/{token}` | Postmark | Per-user email forwarding inbound |
| POST | `/inbound/{PLATFORM_TOKEN}` | Postmark | Platform payment email backup — TCB/MB secondary bank email parser → `payment_matcher` |
| POST | `/trigger/{job_type}` | Internal/Cron | Manual job trigger |
| GET | `/` | Health check | Status OK |
| GET | `/health` | Monitoring | Detailed health (DB, uptime) |

> **Token routing logic:** dispatcher first checks if token matches `PLATFORM_TOKEN` env var → routes to payment_matcher. Else lookup `users` table by `webhook_token` → user pipeline. Else 200 + log warning (no info leak).

> **Messenger signature verification:** mọi POST `/webhook/messenger` phải pass HMAC-SHA256 verify với `FB_APP_SECRET`. Fail → 200 + log warning (không leak info). Spec implementation: [feature-spec-messenger-channel.md §4.3](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md).

### 3.2. Webhook Processing Pipeline

```python
# Pseudocode cho transaction processing pipeline

async def process_transaction(user: User, raw_data: dict, source: str):
    """Unified pipeline cho cả SePay và Email sources."""

    # 1. Parse → canonical schema
    tx = normalize_payload(raw_data, source)

    # 2. Tier limit check
    if user.plan == 'free':
        count = await db.count_monthly_tx(user.id, current_month())
        if count >= 45:
            await notify_limit_reached(user)
            return

    # 3. Dedup — exact ref_code
    if await db.tx_exists(user.id, tx.ref_code):
        return  # silent skip

    # 4. Dedup — fuzzy cross-source (3-min window)
    if await db.find_fuzzy_duplicate(user.id, tx.amount, tx.direction, tx.date):
        return  # silent skip

    # 5. Stale check
    max_age = 1440 if source.startswith('email') else 10  # minutes
    if tx.age_minutes > max_age:
        return  # silent skip

    # 6. Insert transaction
    tx_id = await db.insert_transaction(user.id, tx)

    # 7. Ensure categories exist (bootstrap defaults if first tx)
    categories = await db.get_active_categories(user.id, tx.month_key)
    if not categories:
        categories = await bootstrap_defaults(user.id, tx.month_key)

    # 8. Send category picker via Telegram
    await send_category_picker(user.telegram_id, tx_id, tx, categories)
```

### 3.3. Email Inbound Processing

```python
async def process_inbound_email(user: User, postmark_payload: dict):
    """Postmark inbound webhook → parse → transaction pipeline."""

    from_addr = postmark_payload['FromFull']['Email']
    subject = postmark_payload['Subject']
    body = postmark_payload.get('TextBody') or postmark_payload.get('HtmlBody', '')
    date = postmark_payload.get('Date', '')

    # Parse email → canonical dict (or None if unsupported)
    parsed = parse_email(from_addr, subject, body, date)

    if parsed is None:
        # Unsupported bank → notify user
        await notify_unparsed_email(user, from_addr, subject)
        return

    # Feed into unified pipeline
    await process_transaction(user, parsed, source=parsed['_source'])
```

---

## 4. Module Structure (Target)

```
MyMoneyWent/
├── main.py                      # FastAPI app, routes, startup
├── config.py                    # Environment config
├── db.py                        # Database connection + queries (replaces sheets.py)
├── models.py                    # Pydantic models / dataclasses
├── telegram_api.py              # Telegram Bot API wrapper
│
├── handlers/
│   ├── __init__.py
│   ├── onboarding.py            # [NEW] 3-path onboarding flow
│   ├── sepay.py                 # SePay webhook handler (refactored)
│   ├── email_parser.py          # Email parsing (expanded: 6 MVP banks)
│   ├── transaction.py           # Category selection state machine
│   ├── manage.py                # /manage CRUD
│   ├── allocation.py            # /allocate budget
│   ├── reports.py               # /status, /today, /weekly, /report
│   └── settings.py              # [NEW] /settings handler
│
├── services/
│   ├── __init__.py
│   ├── user_service.py          # [NEW] User CRUD, plan management
│   ├── tx_service.py            # [NEW] Transaction pipeline
│   ├── category_service.py      # [NEW] Category CRUD
│   ├── plan_service.py          # [NEW] Tier limits, trial logic
│   └── scheduler_service.py     # [NEW] Per-user scheduled jobs
│
├── migrations/
│   ├── 001_initial_schema.sql
│   └── ...
│
├── parsers/                     # [NEW] Bank-specific email parsers
│   ├── __init__.py
│   ├── base.py                  # Base parser interface
│   ├── tcb.py                   # Techcombank (MVP ✅)
│   ├── cake.py                  # Cake by VPBank (MVP ✅)
│   ├── acb.py                   # ACB (MVP)
│   ├── stb.py                   # Sacombank (MVP)
│   ├── bidv.py                  # BIDV (MVP)
│   └── mb.py                    # MB Bank (MVP)
│
├── tests/
│   ├── test_parsers/            # Email parser unit tests (50+ samples/bank)
│   ├── test_services/
│   └── test_handlers/
│
├── docs/
│   ├── brd.md
│   ├── prd.md
│   └── tdd.md                   # This file
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml           # Local dev
├── railway.toml
└── .env.example
```

---

## 5. Deployment & Infrastructure

### 5.1. Railway Setup

```yaml
# railway.toml
[build]
builder = "DOCKERFILE"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[service]
internalPort = 8000
```

### 5.2. Environment Variables

```bash
# === Required ===
BOT_TOKEN=<telegram bot token>
BOT_TOKEN_BACKUP=<emergency switchover token>     # rotate khi BOT_TOKEN suspended
DATABASE_URL=postgresql://user:pass@host:5432/fintrack
WEBHOOK_BASE_URL=https://api.tienvenoidau.com

# === Messenger Channel (MVP — Phase 6 Tuần 10-11) ===
FB_PAGE_ID=<facebook page id>                     # Page hosting bot
FB_PAGE_ACCESS_TOKEN=<page access token>          # OAuth token long-lived for Page
FB_VERIFY_TOKEN=<random string for webhook verify> # Meta GET verify check
FB_APP_SECRET=<facebook app secret>                # HMAC-SHA256 signature verify cho POST webhook
ENABLE_MESSENGER_CHANNEL=true                      # feature flag để soft-disable Messenger entry

# === Discord (Phase 2-3) ===
DISCORD_BOT_TOKEN=<discord bot token>               # Bot token from Discord Developer Portal
DISCORD_APPLICATION_ID=<application id>             # Application ID for slash command registration
DISCORD_PUBLIC_KEY=<ed25519 public key>             # Ed25519 public key for interaction signature verify
ENABLE_DISCORD_CHANNEL=true                         # feature flag to soft-disable Discord entry

# === Email (Phase 5) ===
POSTMARK_INBOUND_DOMAIN=in.tienvenoidau.com
POSTMARK_SERVER_TOKEN=<postmark token>

# === Payment (Phase 6) — Bank transfer auto-detect ===
# Primary: SePay webhook on platform's bank account
# Backup: Email forwarding from platform's bank notification → Postmark inbound
PLATFORM_TOKEN=<24-char URL-safe>             # webhook routing distinguish from user_token

# Bank account 1 — Primary (SePay-linked, fastest detection ≤60s)
PLATFORM_BANK_PRIMARY_CODE=<vd "VCB">                       # bank code in BANK_BIN dict (services/qr_generator.py)
PLATFORM_BANK_PRIMARY_ACCOUNT_NUMBER=<vd "9999888877">       # digits only, no spaces
PLATFORM_BANK_PRIMARY_HOLDER_NAME=<vd "NGUYEN VAN A">        # legal entity name (hộ kinh doanh / công ty)

# Bank account 2 — Secondary (email-only, detection ≤5min — cost saving SePay sub)
PLATFORM_BANK_SECONDARY_CODE=<vd "TCB">
PLATFORM_BANK_SECONDARY_ACCOUNT_NUMBER=<vd "1234567890">
PLATFORM_BANK_SECONDARY_HOLDER_NAME=<vd "NGUYEN VAN A">      # có thể khác primary holder nếu cần

PAYMENT_REF_PREFIX=PAY                          # ref format: {prefix}-{user_id}-{plan}-{period}-{nonce4}
PAYMENT_PENDING_TTL_HOURS=24                    # pending payment expires after
PAYMENT_GRACE_PERIOD_DAYS=7                     # post-expiry grace before downgrade
PAYMENT_AMOUNT_TOLERANCE_VND=1000               # hard cap ±1,000 VND (NOT percent — bank transfer VND luôn integer exact). Set 0 cho strict exact match.

# NOTE: Bank BIN không phải env var — auto-lookup từ `BANK_BIN` dict trong services/qr_generator.py
# theo `PLATFORM_BANK_*_CODE`. Mapping bao gồm VCB/TCB/MB/ACB/STB/BIDV/VTB/VPB/TPB/Cake.

# Feature flags — VietQR + Email parallel path (xem implementation-plan-payment-vietqr-email.md)
ENABLE_VIETQR=true                              # disable → fallback text-only display
ENABLE_EMAIL_PARALLEL=true                      # disable → endpoint /inbound/{PLATFORM_TOKEN} no-op

ADMIN_TELEGRAM_IDS=<founder_id,trusted_contact_id>  # comma-separated, plural — multi-admin support; for unmatched payment alerts + admin commands

# Phase 2 secondary (defer):
# PAYPAL_CLIENT_ID=<paypal client id>
# PAYPAL_CLIENT_SECRET=<paypal secret>
# USDT_WALLET_ADDRESS=<usdt trc20/erc20 wallet>

# === Optional ===
BACKUP_B2_KEY_ID=<b2 key>
BACKUP_B2_APP_KEY=<b2 app key>
BACKUP_B2_BUCKET=fintrack-backups
SENTRY_DSN=<sentry dsn>
```

### 5.3. Backup Strategy

| What | How | Frequency | Retention |
|------|-----|-----------|-----------|
| PostgreSQL full dump | `pg_dump` → B2 | Daily 03:00 UTC | 30 ngày |
| PostgreSQL WAL | Railway managed | Continuous | 7 ngày |
| Recovery test | Restore to staging | Monthly | — |

### 5.4. Monitoring

| Metric | Tool | Alert threshold |
|--------|------|----------------|
| Uptime | Railway built-in | < 99% weekly |
| Error rate | Sentry | > 10 errors/hour |
| Response time | Railway metrics | p95 > 2s |
| DB connections | pg_stat_activity | > 80% pool |
| Email parser accuracy | Custom analytics | < 85% per bank |

---

## 6. Security

### 6.1. Data Flow Security

```
SePay ──HTTPS──→ /hook/{token} ──validate token──→ process
                                     │
                                     ├── token invalid → 200 OK + log (no info leak)
                                     └── token valid → INSERT scoped by user_id

Postmark ──HTTPS──→ /inbound/{token} ──validate token──→ parse ──→ process
                                           │
                                           └── same pattern as SePay

Telegram ──HTTPS──→ /webhook ──validate telegram_id──→ route to user
```

### 6.2. Data Minimization

| Data | Lưu? | Lý do |
|------|------|-------|
| Số tài khoản ngân hàng | ❌ | Không cần, high risk |
| Tên chủ tài khoản | ❌ | Không cần |
| Số tiền giao dịch | ✅ | Core feature |
| Nội dung chuyển khoản | ✅ | Categorization context |
| Mã tham chiếu | ✅ | Dedup |
| Telegram chat_id | ✅ | User identity |

### 6.3. PDPA Compliance (Nghị định 13/2023)

- [ ] Privacy policy rõ ràng, accessible qua /help
- [ ] Data retention policy: Free user inactive 90 ngày → archive data
- [ ] User có thể request data export (/export)
- [ ] User có thể request account deletion
- [ ] Breach response plan documented
- [ ] No data sharing với third party

---

## 7. Testing Strategy

### 7.1. Unit Tests

| Module | Test focus | Min coverage |
|--------|-----------|-------------|
| Email parsers (6 MVP banks) | 50+ email samples/bank, edge cases | 90% |
| Transaction pipeline | Dedup, stale check, tier limits | 85% |
| Category service | CRUD, tier limits, bootstrap | 80% |
| Plan service | Trial logic, upgrade/downgrade | 90% |

### 7.2. Integration Tests

| Flow | Steps |
|------|-------|
| Onboarding → first tx | /start → webhook → category pick → confirm |
| Email → categorize | Postmark webhook → parse → pick → confirm |
| Free limit hit | 45 tx → reject #46 → upgrade prompt |
| Trial expiry | Create user → fast-forward 14d → verify downgrade |

### 7.3. Email Parser Validation

```
tests/test_parsers/
├── samples/                # MVP 6 banks
│   ├── tcb/          # 50+ real email samples (existing)
│   ├── cake/         # 50+ samples (existing)
│   ├── acb/          # 50+ samples
│   ├── stb/          # 50+ samples
│   ├── bidv/         # 50+ samples
│   └── mb/           # 50+ samples
├── test_tcb.py
├── test_cake.py
├── test_acb.py
├── test_stb.py
├── test_bidv.py
└── test_mb.py
# VCB defer Phase 2 — pending email-notification verification
```

Target: **≥85% accuracy per bank** (BRD success criteria).

---

## 8. Performance Considerations

### 8.1. Connection Pooling

```python
# asyncpg pool config
pool = asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=10,           # Railway Hobby: limit connections
    max_inactive_connection_lifetime=300,
)
```

### 8.2. Caching Strategy

| Data | Cache | TTL | Invalidation |
|------|-------|-----|-------------|
| User by webhook_token | In-memory dict | 5 min | On token regenerate |
| Active categories | In-memory dict per user | 5 min | On /manage change |
| Monthly tx count (Free tier) | In-memory counter | 1 min | On new tx |

### 8.3. Async Processing

- Webhook → return 200 immediately → `BackgroundTasks.add_task()`
- Telegram messages → same pattern
- Heavy operations (reports, exports) → background task

---

## 9. Migration Path (Phase-by-Phase)

### Phase 1: Foundation (Tuần 1-2)

- [ ] PostgreSQL schema (DDL above), including `admin_audit_log`
- [ ] `db.py` — asyncpg connection pool + query functions
- [ ] `models.py` — Pydantic schemas
- [ ] `services/user_service.py` — user CRUD
- [ ] `services/messenger.py` — outbound abstraction, initial direct-send implementation
- [ ] `services/admin.py` — `ADMIN_TELEGRAM_IDS` parsing, `@admin_only`, audit logger
- [ ] Docker Compose for local dev
- [ ] Import founder's existing data

### Phase 2: Handlers Refactor (Tuần 3-4)

- [ ] Refactor all handlers: `CHAT_ID` → per-user routing
- [ ] `sheets.py` → `db.py` swap (same interface)
- [ ] Auth flow: telegram_id → user lookup
- [ ] Bot state: per-user isolation
- [ ] Remove Google Sheets dependency

### Phase 3: Pricing Logic (Tuần 5)

- [ ] `services/plan_service.py` — tier limits
- [ ] Trial logic (14-day, auto-downgrade)
- [ ] Upgrade trigger messages
- [ ] Category limits enforcement
- [ ] Transaction count limits

### Phase 4: SePay Onboarding (Tuần 6)

- [ ] `handlers/onboarding.py` — 3-path flow
- [ ] Path A: quick connect
- [ ] Path B: wizard (3-step state machine)
- [ ] `/settings` handler

### Phase 5: Email Parsing (Tuần 7-9)

- [ ] Postmark Inbound setup + DNS
- [ ] `/inbound/{token}` endpoint
- [ ] Bank parsers: ACB, STB, BIDV, MB (TCB + Cake existing) — 6 banks MVP total
- [ ] Unparsed email notification flow
- [ ] Parser accuracy tests (50+ samples/bank)
- [ ] Path C onboarding flow

### Phase 6: Polish + Deploy (Tuần 10-12)

- [ ] APScheduler per-user timezone
- [ ] Payment integration: **bank transfer auto-detect** via SePay primary + Email backup, 4-layer fuzzy matching, manual review fallback. PayPal/USDT defer Phase 2. Detail: [feature-spec-payment-bank-transfer.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md)
- [ ] Admin tools commands (Telegram admin chat): pending/unmatched payments, manual resolve, refund, force plan, logs/stats; all actions audit to `admin_audit_log`. Detail: [feature-spec-admin-tools.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-admin-tools.md)
- [ ] Observability dashboard + critical alerts (Sentry/Railway/admin Telegram): errors, queue depth, payment unmatched queue, parser accuracy, backup failure. Detail: [observability-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md)
- [ ] Railway production deploy
- [ ] Domain + SSL + Telegram webhook setup
- [ ] Backup automation (B2). Recovery procedure: [runbooks/disaster-recovery.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md)
- [ ] Sentry error tracking

### Phase 7-8: Beta + Soft Launch (Tuần 13-16)

- [ ] Beta 5-10 users → validate
- [ ] Backup recovery test
- [ ] Cost validation (≤ $25/mo)
- [ ] Soft launch 20-30 users

---

### 9.1. Operational Specs

- [Feature spec: Admin tools & audit](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-admin-tools.md)
- [Runbook: Disaster recovery](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md)
- [Observability plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial TDD — multi-tenant PostgreSQL architecture, 3-path onboarding, email parsing pipeline, tier-based limits, per-user scheduling. Aligned with BRD v2.3.1 + PRD v1.0.0 at the time; superseded by v1.4.0 current spec. |
| v1.1.0 | 2026-05-05 | **Sync with BRD v2.4.0 + PRD v1.1.0:** Version references updated. Note: default categories reduced from 5 → 3 (Daily Spending, Saving, Subscription), Free tier category cap = 5 total, annual pricing = 20% off, email forwarding open cho Free tier (1 source). Schema + module structure unchanged — these are product-level changes that affect `bootstrap_defaults()` logic and `plan_service.py` limits, not DB schema. |
| v1.2.0 | 2026-05-05 | **Sync BRD v2.5.0 + PRD v1.2.0:** (1) Payment env vars: PayOS → Bank transfer + PayPal + USDT. (2) Parser modules: VCB removed from MVP (moved to Phase 2), BIDV added. MVP = 6 parsers (TCB, Cake, ACB, STB, BIDV, MB). (3) Phase 5 bank list updated. (4) Phase 6 payment integration updated. |
| v1.3.0 | 2026-05-05 | **Sync BRD v2.6.0 + PRD v1.3.0 + Feature Spec Refactor:** (1) Thêm `chat_id BIGINT NOT NULL` vào `users` table — cần cho outbound messages, `telegram_id ≠ chat_id` trong group context. Align với feature spec §4.1. (2) Version references updated. (3) Thêm link tới feature-spec-refactor-saas.md. |
| v1.4.0 | 2026-05-05 | **Schema decisions resolved (align với feature spec):** (1) **`amount` type → BIGINT** (was NUMERIC(15,2)) — VND không có sub-unit, integer arithmetic faster + smaller, không có float precision bug. Áp dụng cho `categories.allocated`, `categories.daily_cap`, `transactions.amount`, `monthly_reports.allocated/spent/remaining`. Multi-currency Phase 2+ sẽ revisit (BRD §4.4 #3 confirm VND-only MVP). (2) **`bot_state` schema → `step VARCHAR(48) + payload JSONB`** (was single `state JSONB`) — explicit columns cho indexability + monitoring. State machine có ~13 step fixed (enum-like), tách column cho phép `WHERE step = 'await_sub'` query nhanh + add B-tree index. `payload` JSONB giữ flexibility cho per-step context. Thêm partial index `idx_bot_state_step WHERE step IS NOT NULL`. |
| v1.5.0 | 2026-05-05 | **Payment auto-detect schema + endpoints (sync feature-spec-payment-bank-transfer.md):** (1) §2.1 thêm 3 table: `pending_payments` (user upgrade requests, ref_code UNIQUE, 24h TTL), `payment_matches` (each confirmed transfer ↔ pending, UNIQUE(source, source_ref_code) cross-source dedup), `unmatched_payments` (admin review queue). (2) §3.1 endpoint table thêm distinguish `/hook/{PLATFORM_TOKEN}` + `/inbound/{PLATFORM_TOKEN}` cho platform payment vs user transaction. (3) §5.2 env vars expanded: `PLATFORM_TOKEN`, 4 platform bank account vars, `PAYMENT_*` config (TTL, grace, tolerance, ref prefix), `ADMIN_TELEGRAM_ID`. PayPal/USDT vars defer comment. |
| v1.5.1 | 2026-05-05 | **Schema + parser fixture fixes (sync feature-spec-payment-bank-transfer.md v1.1.0):** (1) Drop `pending_payments.matched_match_id` (circular FK weak — reverse query qua `payment_matches.pending_payment_id`). (2) `payment_matches`: thêm `status` column ('matched'|'refunded'|'credited'|'voided') + `refunded_at` + `refund_notes` cho refund tracking. (3) Replace `UNIQUE(source, source_ref_code)` (NULL-unsafe) bằng `dedup_key VARCHAR(128) NOT NULL UNIQUE` (sha256 hash). Áp dụng cả `payment_matches` + `unmatched_payments`. (4) §7.3 parser fixtures: bỏ VCB (defer Phase 2), thêm Cake + BIDV. MVP fixtures = TCB, Cake, ACB, STB, BIDV, MB. (5) Phase 5 + Phase 6 wording sync với BRD v2.7.0: bank transfer auto-detect + manual review fallback (no more "manual verification MVP" wording). |
| v1.5.2 | 2026-05-06 | **Foundation sync with BRD v2.7.2 + implementation plan v1.1.0:** (1) Header BRD ref bumped v2.7.1 → v2.7.2. (2) `PAYMENT_AMOUNT_TOLERANCE=0.05` (percent — sai bản chất bank transfer VND) → **`PAYMENT_AMOUNT_TOLERANCE_VND=1000`** hard cap đồng. (3) Add outbound messaging abstraction `services/messenger.py` (`messenger.send(user_id, payload)`) so C9 queue/C8 bot pool can swap internals later. (4) Add `admin_audit_log` DDL + `ADMIN_TELEGRAM_IDS` admin framework foundation. (5) Phase 6 timeline/scope updated to tuần 10-12 with payment + admin tools + observability dashboard/alerts. |
| v1.5.3 | 2026-05-06 | **Cross-ref sync with BRD v2.8.0 + PRD v1.5.0 + 3 new specs (admin-tools, DR runbook, observability):** (1) Header references bumped v2.7.2 → v2.8.0, v1.4.0 → v1.5.0. (2) Header thêm 3 spec ref: Admin Tools, DR Runbook, Observability. (3) No DDL/schema change — pure cross-doc consolidation. |
| v1.6.0 | 2026-05-07 | **Multi-channel + VietQR foundation (sync feature-spec-messenger-channel v1.1.1 + impl plan VietQR+email):** (1) §1.1 architecture diagram thêm Messenger client + `/webhook/messenger` endpoint. (2) §1.2 thêm 3 design decisions: multi-channel via `users.channel_type`, channel adapter pattern `services/channels/`, QR generation via vietqr.io. (3) §1.4 outbound abstraction expand — `services/messenger.py` route to adapter `services/channels/{telegram,messenger}.py`, payload type thêm `image`, payload `tag` field cho Messenger MESSAGE_TAG. (4) §2.1 schema users — thêm `channel_type` NOT NULL, `channel_user_id` NOT NULL, `last_user_message_at` (24h window), `invalid_channel`, `bot_id`. `telegram_id` từ NOT NULL UNIQUE → nullable (cho Messenger user = NULL). UNIQUE constraint `(channel_type, channel_user_id)`. CHECK `channel_type IN ('telegram', 'messenger')`. (5) §3.1 endpoint table — `/webhook` → `/webhook/telegram`, thêm GET+POST `/webhook/messenger`, document signature verify. (6) §5.2 env vars — thêm 5 Messenger vars (FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, FB_VERIFY_TOKEN, FB_APP_SECRET, ENABLE_MESSENGER_CHANNEL), thêm 3 platform bank BIN vars cho VietQR (PLATFORM_BANK_*_BIN, PLATFORM_BANK_HOLDER_NAME), thêm BOT_TOKEN_BACKUP, ENABLE_VIETQR, ENABLE_EMAIL_PARALLEL flags. (7) Header refs bumped BRD v2.8.0 → v2.9.0, PRD v1.5.0 → v1.6.0, thêm Messenger Spec + Impl Plan VietQR refs. |
| v1.7.0 | 2026-05-08 | **i18n multilingual support:** (1) §2.1 users table — thêm `locale VARCHAR(5) NOT NULL DEFAULT 'vi'` + `CHECK locale IN ('vi', 'en')`. Auto-detect from Telegram `language_code` / Messenger profile, user confirms during onboarding. (2) Onboarding flow mới: `/start` → auto-detect locale → language confirm buttons → path select. (3) `/settings` thêm language change option. (4) All user-facing messages served via `i18n/` module (`t(locale, key)` pattern). Admin messages (`/admin_*`) hardcoded English. (5) Default categories bilingual: vi = "Chi tiêu hàng ngày / Tiết kiệm / Đăng ký dịch vụ", en = "Daily Spending / Saving / Subscription". |
| v1.8.0 | 2026-05-08 | **Discord channel support:** (1) §1.2 design decisions — multi-channel expanded: Telegram + Messenger + Discord. Outbound routing adds `DiscordSender`. (2) §1.4 channel adapter — thêm `discord.py` (Rich Embeds, Action Row buttons, Ed25519 signature verify). Grep acceptance includes Discord. (3) §2.1 users — `channel_type CHECK` expanded: `('telegram', 'messenger', 'discord')`. `channel_user_id` comment updated cho Discord snowflake ID. (4) Feature doc ref thêm `feature-discord-channel.md`. Discord dùng cho cả VN + Global market. DM-first, slash commands, no approval process (khác Messenger). |
