# SaaS Pivot: Zero-Config Financial Tracking Bot

## Bối cảnh

Bot hiện tại yêu cầu user setup ~8 bước thủ công (tạo Telegram bot, Google Cloud project, service account, Google Sheet, deploy script, grant permissions, cấu hình SePay webhook...). Pivot sang SaaS với mục tiêu: **user chỉ cần 2 bước** để bắt đầu track tài chính.

## Core Insight: Shared Bot, Not Per-User Bot

Thay vì mỗi user tạo bot riêng → **platform chạy 1 bot duy nhất** phục vụ tất cả users. Đây là mô hình chuẩn của mọi Telegram SaaS (Wallet Bot, Track Bot, etc).

```
HIỆN TẠI (per-user):                    SAU PIVOT (shared bot):
User tạo bot → lấy token              User mở @FinTrackBot → /start
User tạo Sheet → lấy ID               Bot tạo account tự động
User tạo GCloud project                Bot cấp webhook URL
User tạo service account               User dán URL vào SePay
User share Sheet                       ✅ Done
User cấu hình SePay webhook
User deploy code
8 bước                                 2 bước
```

## User Onboarding Flow (Target: 2 bước)

```
Bước 1: User gửi /start cho @FinTrackBot trên Telegram
  → Bot tự tạo account (keyed by chat_id)
  → Bot tự tạo default categories
  → Bot trả lời: "Chào bạn! Để bắt đầu track, kết nối ngân hàng qua SePay."
  → Bot gửi link: "Đây là webhook URL của bạn: https://api.fintrack.vn/hook/abc123xyz"
  → Bot gửi hướng dẫn 3 dòng: vào SePay → Webhook → dán URL

Bước 2: User dán webhook URL vào SePay dashboard
  → SePay gửi transaction đầu tiên
  → Bot nhận, gửi category picker
  → ✅ Hoàn tất setup
```

**Không cần:** bot token, Sheet ID, service account, Google Cloud, credentials.json, deploy code.

## Proposed Architecture

```
┌─────────────────────────────────────────────────────┐
│              MESSAGING PLATFORMS                     │
│   Telegram Bot (shared)  ·  Messenger (future)      │
│   Zalo OA (future)       ·  Viber (future)          │
└──────────┬──────────────────────┬───────────────────┘
           │ Webhook              │ Webhook
┌──────────▼──────────────────────▼───────────────────┐
│                  FASTAPI SERVER                      │
│  POST /tg/webhook          — Telegram updates        │
│  POST /hook/{user_token}   — SePay per-user          │
│  POST /hook/email/{token}  — Email per-user           │
│  GET  /export/{token}.csv  — Data export             │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│              CORE LOGIC (reuse handlers/)            │
│  sepay.py · transaction.py · reports.py · manage.py │
│  allocation.py  — ALL receive user_id param          │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│                 STORAGE LAYER                        │
│  PostgreSQL — users, transactions, categories,       │
│               bot_state, scheduled_jobs              │
│  (Google Sheets = REMOVED from critical path)        │
└─────────────────────────────────────────────────────┘
```

> **Không có Google Sheets trong critical path.** PostgreSQL là sole database. Optional CSV export cho users muốn spreadsheet.

## Database Schema (PostgreSQL)

```sql
-- Users: auto-created khi /start
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    telegram_id   BIGINT UNIQUE NOT NULL,
    display_name  TEXT,
    timezone      TEXT DEFAULT 'Asia/Ho_Chi_Minh',
    sepay_token   TEXT UNIQUE,          -- random token cho webhook URL
    email_token   TEXT UNIQUE,          -- random token cho email webhook
    plan          TEXT DEFAULT 'free',  -- free | pro
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Transactions: thay thế Google Sheets "Đầu ra" tab
CREATE TABLE transactions (
    id            SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(id),
    amount        NUMERIC(15,2) NOT NULL,
    tx_type       TEXT NOT NULL,        -- 'out' | 'in'
    description   TEXT,
    ref_code      TEXT,
    category_id   TEXT,                 -- FK tới categories.slug
    sub_category  TEXT,
    confirmed     BOOLEAN DEFAULT FALSE,
    tx_date       TIMESTAMPTZ NOT NULL,
    month_key     TEXT NOT NULL,        -- '2026-05'
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ref_code)           -- dedup built-in
);

-- Categories: thay thế "Budget Config" tab
CREATE TABLE categories (
    id            SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(id),
    slug          TEXT NOT NULL,        -- 'daily_spending'
    name          TEXT NOT NULL,        -- '🛒 Daily Spending'
    allocated     NUMERIC(15,2) DEFAULT 0,  -- 0 = tracking-only
    daily_cap     NUMERIC(15,2),
    month_key     TEXT NOT NULL,
    active        BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, slug, month_key)
);

-- Sub-categories: thay thế "Sub-category Config" tab
CREATE TABLE sub_categories (
    id            SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(id),
    category_slug TEXT NOT NULL,
    key           TEXT NOT NULL,
    label         TEXT NOT NULL,
    active        BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, category_slug, key)
);

-- Bot state: thay thế "Bot State" tab (hoặc dùng Redis)
CREATE TABLE bot_state (
    user_id       INT PRIMARY KEY REFERENCES users(id),
    state_json    JSONB DEFAULT '{}',
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Scheduled jobs: thay thế crontab
CREATE TABLE scheduled_jobs (
    id            SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(id),
    job_type      TEXT NOT NULL,       -- 'daily_recap' | 'weekly' | 'monthly'
    enabled       BOOLEAN DEFAULT TRUE,
    next_run_utc  TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id, job_type)
);
```

### So sánh Sheets vs PostgreSQL cho từng concern:

| Concern | Google Sheets (hiện tại) | PostgreSQL (mới) |
|---------|------------------------|------------------|
| Dedup | In-memory dict + fuzzy scan 50 rows | `UNIQUE(user_id, ref_code)` — 1 line |
| Query spent/month | `get_all_values()` → loop toàn bộ | `SELECT SUM(amount) WHERE month_key=? AND user_id=?` |
| Bot state | Read/write 3 API calls | 1 query, sub-ms |
| Multi-user | Không thể (global Sheet) | `WHERE user_id = ?` mọi query |
| Rate limit | 60 req/min/service account | Không có |
| ACID | Không | ✅ Transactions |

## Refactor Strategy: `db.py` thay thế `sheets.py`

Tạo `db.py` mới với **cùng interface** như `sheets.py`, nhưng backed by PostgreSQL. Handlers chỉ cần đổi import:

```python
# BEFORE (mọi handler):
import sheets as sh
sh.get_active_buckets(month_key)
sh.append_transaction(...)
sh.get_state(CHAT_ID)

# AFTER:
import db
db.get_active_buckets(user_id, month_key)
db.append_transaction(user_id, ...)
db.get_state(user_id)
```

**Thay đổi duy nhất trong handlers:** thêm `user_id` param vào mọi function call. Logic business giữ nguyên 100%.

### `db.py` — key functions (thay thế sheets.py):

```python
# db.py — PostgreSQL replacement cho sheets.py
import asyncpg

pool: asyncpg.Pool = None

async def init_pool(dsn: str):
    global pool
    pool = await asyncpg.create_pool(dsn)

# ── User management ──
async def get_or_create_user(telegram_id: int, display_name: str = "") -> dict:
    """Auto-create user on /start. Returns user dict."""
    ...

# ── Transactions (replaces append_transaction, finalize_transaction) ──
async def append_transaction(user_id, tx_date, description, amount, 
                              ref_code, month_key, tx_type="out") -> int:
    """INSERT ... ON CONFLICT (user_id, ref_code) DO NOTHING. Dedup built-in."""
    ...

async def finalize_transaction(user_id, tx_id, category_slug, sub_label):
    """UPDATE transactions SET category_id=?, confirmed=TRUE ..."""
    ...

# ── Categories (replaces get_active_buckets, write_budget_row) ──
async def get_active_buckets(user_id, month_key) -> list[dict]:
    """SELECT * FROM categories WHERE user_id=? AND month_key=? AND active=TRUE"""
    ...

async def bootstrap_defaults(user_id, month_key) -> int:
    """INSERT default categories ON CONFLICT DO NOTHING. Inherently idempotent."""
    ...

# ── Reports (replaces get_bucket_status — no more full-sheet scan) ──
async def get_bucket_status(user_id, bucket_slug, month_key) -> dict:
    """SELECT SUM(amount) FROM transactions WHERE ... — milliseconds, not seconds."""
    ...

# ── Bot State (replaces get_state/set_state) ──
async def get_state(user_id) -> dict | None:
    """SELECT state_json FROM bot_state WHERE user_id=?"""
    ...

async def set_state(user_id, state: dict):
    """INSERT ... ON CONFLICT UPDATE state_json=?"""
    ...
```

## `telegram_api.py` Refactor — Remove Globals

```python
# BEFORE: module-level globals
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def send_text(text, chat_id=None):
    chat_id = chat_id or CHAT_ID  # ← hardcoded default
    ...

# AFTER: bot_token từ env, chat_id luôn explicit
BOT_TOKEN = os.environ["BOT_TOKEN"]  # Platform's single bot token
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def send_text(text, chat_id: str):  # ← chat_id bắt buộc
    ...
```

**Key change:** `CHAT_ID` không còn là global config — mỗi user có `telegram_id` riêng trong DB. `chat_id` trở thành required param.

## `main.py` Refactor — Multi-User Routing

```python
# ── Telegram webhook (1 endpoint cho tất cả users) ──
@app.post("/tg/webhook")
async def tg_webhook(request: Request, bg: BackgroundTasks):
    body = await request.json()
    bg.add_task(_process_telegram, body)
    return {"ok": True}

# ── SePay webhook (per-user token URL) ──
@app.post("/hook/{user_token}")
async def sepay_hook(user_token: str, request: Request, bg: BackgroundTasks):
    user = await db.get_user_by_sepay_token(user_token)
    if not user:
        return {"ok": False}
    body = await request.json()
    bg.add_task(handle_sepay_webhook, body, user["id"], user["telegram_id"])
    return {"ok": True}

# ── Dispatcher: extract user from Telegram update ──
async def _process_telegram(body: dict):
    if "callback_query" in body:
        chat_id = body["callback_query"]["from"]["id"]
    elif "message" in body:
        chat_id = body["message"]["from"]["id"]
    else:
        return
    
    user = await db.get_or_create_user(telegram_id=chat_id)
    # Pass user_id to all handlers
    ...
```

## Webhook URL Design

```
SePay:  POST https://api.fintrack.vn/hook/{user_token}
Email:  POST https://api.fintrack.vn/hook/email/{user_token}
```

- `user_token` = 24-char cryptographically random string (URL-safe)
- Generated on `/start`, stored in `users.sepay_token`
- User chỉ cần copy 1 URL, dán vào SePay → done
- Token regenerable via `/settings` command

## Scheduled Jobs — APScheduler In-Process

```python
# Thay thế crontab trên VPS
scheduler = AsyncIOScheduler()

async def poll_due_jobs():
    """Mỗi 60s, check scheduled_jobs table, fire due jobs."""
    jobs = await db.get_due_jobs()
    for job in jobs:
        user = await db.get_user(job["user_id"])
        if job["job_type"] == "daily_recap":
            asyncio.create_task(send_daily_recap(user["id"], user["telegram_id"]))
        ...
        await db.update_next_run(job["id"])
```

## Pricing (Simple)

| Feature | Free | Pro (~$3/mo) |
|---------|------|-------------|
| Transaction tracking | ✅ | ✅ |
| /status, /today, /manage | ✅ | ✅ |
| Daily recap | ✅ | ✅ |
| Weekly + Monthly report | ❌ | ✅ |
| CSV export | ❌ | ✅ |
| Multiple bank accounts | ❌ | ✅ |
| Email transaction parsing | ❌ | ✅ |

## Decisions (Resolved)

| # | Question | Decision |
|---|----------|----------|
| Q1 | Domain name | TBD — quyết định sau |
| Q2 | Hosting | **Railway** (app + PostgreSQL). Scale lên → tách DB sang Supabase Pro Singapore |
| Q3 | Repo strategy | **Repo mới** — bot cũ vẫn chạy cho personal use |
| Q4 | Platform #2 | **Messenger** (sau Telegram) |

## Migration Plan — 4 Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Tạo repo mới
- [ ] PostgreSQL schema + migrations (Alembic)
- [ ] `db.py` — implement tất cả functions thay thế `sheets.py`
- [ ] `telegram_api.py` — remove `CHAT_ID` global, `chat_id` thành required param
- [ ] `main.py` — multi-user routing, `/start` auto-create user
- [ ] Webhook URL generation + SePay routing `/hook/{token}`

### Phase 2: Handler Refactor (Week 2-3)
- [ ] `handlers/sepay.py` — nhận `user_id` + `chat_id` params, gọi `db.*`
- [ ] `handlers/transaction.py` — same
- [ ] `handlers/reports.py` — same
- [ ] `handlers/allocation.py` — same
- [ ] `handlers/manage.py` — same
- [ ] Smoke test mỗi handler sau refactor

### Phase 3: Scheduling + Polish (Week 3-4)
- [ ] APScheduler — per-user scheduled jobs
- [ ] `/settings` command — regenerate webhook URL, timezone
- [ ] CSV export endpoint
- [ ] Onboarding flow polish (/start → welcome → SePay instructions)
- [ ] Deploy lên Railway + PostgreSQL

### Phase 4: Launch (Week 4-5)
- [ ] Domain setup + SSL
- [ ] Register Telegram webhook cho shared bot
- [ ] Migrate data cá nhân sang DB mới
- [ ] Beta test với 5-10 users
- [ ] Payment integration (PayOS) nếu cần

## Verification Plan

### Automated Tests
- Unit test cho `db.py` — mọi function có test
- Integration test: mock SePay payload → DB write → category pick → confirm → verify DB state
- Dedup test: gửi 2 webhook cùng ref_code → chỉ 1 row trong DB

### Manual Verification
- End-to-end: `/start` → nhận webhook URL → trigger test transaction → categorize → `/status`
- Multi-user: 2 Telegram accounts cùng dùng bot, data isolated
- Scheduled jobs: verify daily recap fire đúng timezone
