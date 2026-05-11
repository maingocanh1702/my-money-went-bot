# SaaS Plan: spend-less-bot → Multi-Tenant Platform

> Mục tiêu: User đăng ký, nhập credentials (Telegram token, Sheet ID, v.v.) qua UI — platform tự handle toàn bộ còn lại: đăng ký webhook, chạy bot, gửi báo cáo theo lịch, multi-platform fan-out.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                │
│           Next.js Web UI (signup · onboarding wizard · dashboard)   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────────────┐
│                          EDGE LAYER                                  │
│         Nginx/Caddy — TLS termination · rate limiting per tenant    │
│                  webhook token pre-validation                        │
└──────┬─────────────────────┬────────────────────────────────────────┘
       │ API calls            │ Webhooks
┌──────▼──────────────────────▼──────────────────────────────────────┐
│                      FASTAPI APPLICATION                            │
│   /api/auth/*           — signup, login, JWT                       │
│   /api/tenants/*        — CRUD credentials, dashboard data         │
│   /webhook/{tid}/{src}  — SePay · Telegram · Zalo · Viber ...     │
│   /api/internal/*       — health, metrics                          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ enqueue tasks
┌──────────────────────────▼──────────────────────────────────────────┐
│                       CELERY WORKERS                                 │
│   transaction_processor  — categorize + write to user's Sheet       │
│   report_generator       — daily recap · weekly · monthly          │
│   webhook_registrar      — auto-register Telegram setWebhook        │
│   scheduler_beat         — per-tenant cron (timezone-aware)        │
└──────┬──────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                                 │
│   PostgreSQL  — tenants · credentials · webhook configs · jobs      │
│   Redis       — Celery broker · ephemeral bot state (24h TTL)      │
└──────┬──────────────────────────────────────────────────────────────┘
       │ per-tenant credentials (decrypted at runtime)
┌──────▼──────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES                              │
│   Telegram Bot API · Google Sheets API · SePay · Zalo OA · Viber  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Cấu trúc thư mục mới

```
bot-finance-saas/
├── app/
│   ├── core/
│   │   ├── config.py             # MOD — thêm DATABASE_URL, REDIS_URL, FERNET_KEY
│   │   ├── tenant_context.py     # NEW — TenantContext dataclass
│   │   ├── encryption.py         # NEW — Fernet encrypt/decrypt helpers
│   │   └── dependencies.py       # NEW — FastAPI resolve_tenant dependency
│   ├── models/                   # NEW — SQLAlchemy models
│   │   ├── tenant.py
│   │   ├── credentials.py
│   │   ├── webhook_config.py
│   │   └── scheduled_job.py
│   ├── routers/
│   │   ├── auth.py               # NEW — /api/auth/*
│   │   ├── tenants.py            # NEW — /api/tenants/*
│   │   └── webhooks.py           # NEW — /webhook/{tenant_id}/{source}
│   ├── workers/
│   │   ├── celery_app.py         # NEW — Celery init + Redis broker
│   │   ├── tasks.py              # NEW — Celery task definitions
│   │   └── scheduler.py          # NEW — per-tenant Beat schedule
│   ├── services/
│   │   ├── webhook_registrar.py  # NEW — auto setWebhook logic
│   │   └── sheet_verifier.py     # NEW — validate Google Sheet access
│   ├── handlers/                 # MOD — thêm ctx param, bỏ tg.*/config.* hardcode
│   │   ├── sepay.py
│   │   ├── transaction.py
│   │   ├── allocation.py
│   │   └── reports.py
│   ├── adapters/                 # từ multi-platform refactor
│   │   ├── base.py
│   │   ├── telegram.py
│   │   └── ...
│   ├── sheets.py                 # MOD — mọi function nhận ctx: TenantContext
│   ├── telegram_api.py           # MOD — build từ ctx thay vì global config
│   └── main.py                   # MOD — thêm routers mới
├── frontend/                     # NEW — Next.js 14
│   ├── pages/
│   │   ├── signup.tsx
│   │   ├── onboarding/
│   │   │   ├── telegram.tsx
│   │   │   ├── google.tsx
│   │   │   └── sepay.tsx
│   │   └── dashboard/index.tsx
│   └── ...
├── migrations/                   # NEW — Alembic
├── docker-compose.yml            # NEW — app + postgres + redis + celery
└── requirements.txt              # MOD — extend existing
```

---

## Database Schema

### `tenants`
```sql
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    timezone    TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    plan        TEXT NOT NULL DEFAULT 'free',  -- free | pro | team
    status      TEXT NOT NULL DEFAULT 'pending', -- pending | active | suspended
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### `tenant_credentials`
```sql
CREATE TABLE tenant_credentials (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL,   -- 'telegram' | 'zalo' | 'google'
    -- encrypted fields (Fernet bytes stored as TEXT)
    bot_token_enc        TEXT,   -- Telegram bot token
    chat_id_enc          TEXT,   -- Telegram chat ID
    sheet_id_enc         TEXT,   -- Google Sheet ID
    service_account_enc  TEXT,   -- Google service account JSON
    extra_enc            TEXT,   -- JSON blob cho platform khác (Zalo OA token, v.v.)
    verified    BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    UNIQUE(tenant_id, platform)
);
```

### `webhook_configs`
```sql
CREATE TABLE webhook_configs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,   -- 'sepay' | 'telegram' | 'zalo'
    path_token  TEXT NOT NULL UNIQUE,  -- random 32-char token trong URL
    secret_token TEXT,           -- X-Telegram-Bot-Api-Secret-Token header
    last_received_at TIMESTAMPTZ,
    UNIQUE(tenant_id, source)
);
-- Webhook URL: /webhook/{tenant_id}/{source}?token={path_token}
```

### `scheduled_jobs`
```sql
CREATE TABLE scheduled_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    job_type    TEXT NOT NULL,   -- 'daily_recap' | 'weekly' | 'monthly_report' | 'monthly_allocation'
    enabled     BOOLEAN DEFAULT TRUE,
    next_run_utc TIMESTAMPTZ NOT NULL,
    last_run_utc TIMESTAMPTZ,
    UNIQUE(tenant_id, job_type)
);
```

---

## TenantContext — `app/core/tenant_context.py`

```python
from dataclasses import dataclass

@dataclass
class TenantContext:
    tenant_id:            str
    bot_token:            str    # decrypted
    chat_id:              str    # decrypted
    sheet_id:             str    # decrypted
    service_account_json: dict   # decrypted, parsed
    timezone:             str
    daily_bucket_id:      str
    plan:                 str
```

Đây là thứ thay thế toàn bộ `config.py` globals. Mọi handler, mọi Sheets call, mọi Telegram call đều nhận `ctx: TenantContext` thay vì đọc biến global.

---

## Credential Encryption — `app/core/encryption.py`

```python
from cryptography.fernet import Fernet
import os

_fernet = Fernet(os.environ["FERNET_KEY"].encode())

def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
```

- `FERNET_KEY` chỉ tồn tại trong environment variable — không bao giờ vào DB hay git
- Tất cả field `*_enc` trong DB đều là Fernet-encrypted string
- Decrypt xảy ra trong Celery worker, không phải trong HTTP request handler
- Service account JSON không bao giờ xuất hiện trong API response — chỉ hiện masked summary (project_id + client_email)

---

## Tenant Resolution — `app/core/dependencies.py`

```python
from fastapi import Request, HTTPException
import jwt

async def resolve_tenant(
    tenant_id: str,
    source: str,
    request: Request,
    token: str = Query(...)
) -> TenantContext:
    # 1. Validate path token
    config = await db.get_webhook_config(tenant_id, source)
    if not config or config.path_token != token:
        raise HTTPException(401)

    # 2. Load and decrypt credentials
    creds = await db.get_credentials(tenant_id, "telegram")
    tenant = await db.get_tenant(tenant_id)
    if tenant.status != "active":
        raise HTTPException(403, "Tenant inactive")

    return TenantContext(
        tenant_id=tenant_id,
        bot_token=decrypt(creds.bot_token_enc),
        chat_id=decrypt(creds.chat_id_enc),
        sheet_id=decrypt(creds.sheet_id_enc),
        service_account_json=json.loads(decrypt(creds.service_account_enc)),
        timezone=tenant.timezone,
        daily_bucket_id="daily_spending",
        plan=tenant.plan,
    )
```

---

## Webhook URL Design

```
POST /webhook/{tenant_id}/sepay?token={path_token}
POST /webhook/{tenant_id}/telegram?token={path_token}
POST /webhook/{tenant_id}/zalo?token={path_token}
```

- `tenant_id` = UUID v4 (không dùng sequential int — tránh enumeration)
- `path_token` = 32-char cryptographically random string
- Telegram thêm `X-Telegram-Bot-Api-Secret-Token` header (set khi gọi `setWebhook`)
- Token có thể regenerate từ dashboard → invalidate token cũ ngay lập tức

```python
@app.post("/webhook/{tenant_id}/{source}")
async def webhook_router(
    tenant_id: str,
    source: str,
    request: Request,
    bg: BackgroundTasks,
    ctx: TenantContext = Depends(resolve_tenant)
):
    body = await request.json()
    if source == "sepay":
        bg.add_task(process_sepay, body, ctx)
    elif source in ADAPTER_REGISTRY:
        bg.add_task(process_platform_update, source, body, ctx)
    return JSONResponse({"ok": True})
```

---

## Auto-Registration — Telegram setWebhook

```python
async def register_telegram_webhook(ctx: TenantContext, base_url: str):
    path_token   = secrets.token_urlsafe(32)
    secret_token = secrets.token_urlsafe(32)
    webhook_url  = f"{base_url}/webhook/{ctx.tenant_id}/telegram"

    resp = await httpx.post(
        f"https://api.telegram.org/bot{ctx.bot_token}/setWebhook",
        json={
            "url": f"{webhook_url}?token={path_token}",
            "secret_token": secret_token,
            "allowed_updates": ["message", "callback_query"],
        }
    )
    if not resp.json().get("ok"):
        raise WebhookRegistrationError(resp.json()["description"])

    # Lưu vào webhook_configs
    await db.upsert_webhook_config(
        tenant_id=ctx.tenant_id,
        source="telegram",
        path_token=path_token,
        secret_token=secret_token,
    )
```

Gọi tự động khi user save bot token lần đầu và khi user regenerate webhook token.

---

## Onboarding Wizard — 6 bước

```
Bước 1 — Tạo Telegram Bot
  User: Vào @BotFather → /newbot → copy token
  User: Paste token vào input
  Platform: Gọi Telegram getMe để validate → hiện bot username
  Platform: Auto-gọi setWebhook với URL platform

Bước 2 — Lấy Chat ID
  User: Nhắn bất kỳ message cho bot vừa tạo
  Platform: Nhận /webhook/{tid}/telegram → detect chat_id → hiện lên UI (SSE)
  User: Confirm chat_id đúng

Bước 3 — Kết nối Google Sheet
  User: Tạo Sheet với các tab đúng tên (hướng dẫn có sẵn)
  User: Share Sheet với email service account
  User: Paste Sheet ID
  Platform: Gọi Sheets API để verify quyền đọc/ghi → xanh/đỏ

Bước 4 — Upload Service Account
  User: Upload credentials.json
  Platform: Validate format + scopes → encrypt + lưu
  Platform: KHÔNG bao giờ trả file này về trong bất kỳ API response nào

Bước 5 — Cấu hình SePay
  Platform: Hiển thị URL webhook đã tạo sẵn + nút Copy
  User: Vào SePay dashboard → dán URL vào webhook settings
  User: Tắt SePay's built-in Google Sheets integration (nếu đang bật)
  Platform: Đợi transaction đầu tiên để confirm SePay hoạt động

Bước 6 — Set up Budget
  Platform: Gửi lệnh /allocate qua Telegram → user setup budget ngay trên bot
  UI hiển thị: "Bot của bạn đã sẵn sàng 🎉"
```

Verification xảy ra bất đồng bộ với SSE feedback — không cần polling từ phía UI.

---

## Scheduled Job Architecture

Celery Beat + **celery-redbeat** (Redis-backed, không cần DB polling).

### Per-tenant, timezone-aware scheduling

```python
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

def next_run_utc(hour: int, minute: int, timezone_str: str) -> datetime:
    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.astimezone(ZoneInfo("UTC"))

# Daily recap lúc 23:00 theo timezone của user
next_run = next_run_utc(23, 0, ctx.timezone)
```

### Beat loop (mỗi 60 giây)

```python
# scheduler.py
due_jobs = db.query("""
    SELECT * FROM scheduled_jobs
    WHERE enabled = true AND next_run_utc <= NOW()
""")
for job in due_jobs:
    celery.send_task(f"tasks.{job.job_type}", args=[job.tenant_id])
    db.update_next_run(job.id, compute_next_run(job))
```

### Bot State → Redis (thay thế Sheets)

```python
# Thay thế get_state/set_state/clear_state trong sheets.py
import redis.asyncio as redis

async def get_state(tenant_id: str, chat_id: str) -> dict | None:
    key = f"bot_state:{tenant_id}:{chat_id}"
    data = await redis_client.get(key)
    return json.loads(data) if data else None

async def set_state(tenant_id: str, chat_id: str, state: dict):
    key = f"bot_state:{tenant_id}:{chat_id}"
    await redis_client.setex(key, 86400, json.dumps(state))  # TTL 24h
```

Loại bỏ hoàn toàn "Bot State" tab trong Google Sheet → giảm ~4 Sheets API calls mỗi interaction.

---

## Những thay đổi trong code hiện có

### Nguyên tắc chung
Tất cả function trong `handlers/`, `sheets.py`, `telegram_api.py` hiện đang đọc từ `config.py` globals. Refactor thành nhận `ctx: TenantContext` như tham số đầu tiên.

```python
# BEFORE
from config import BOT_TOKEN, CHAT_ID, SHEET_ID
async def send_monthly_status():
    ...

# AFTER
async def send_monthly_status(ctx: TenantContext):
    ...
```

### `sheets.py` — critical fix

`_get_spreadsheet()` hiện cache `_gc` và `_ss` ở module level — **phải sửa** để tránh tenant A dùng credentials của tenant B:

```python
# BEFORE (dangerous for multi-tenant)
_gc = None
_ss = None
def _get_spreadsheet():
    global _gc, _ss
    if _ss is None:
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        ...

# AFTER
from functools import lru_cache

@lru_cache(maxsize=50)  # cached per tenant, evicted after time
def _get_spreadsheet(tenant_id: str, service_account_json_str: str):
    creds = Credentials.from_service_account_info(
        json.loads(service_account_json_str), scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(sheet_id)  # sheet_id từ ctx
```

---

## Tech Stack

| Concern | Hiện tại | Thêm cho SaaS |
|---|---|---|
| Database | Google Sheets | **PostgreSQL + SQLAlchemy 2 + asyncpg** |
| Task queue | VPS cron | **Celery 5 + Redis + celery-redbeat** |
| Bot state | Google Sheets | **Redis** (24h TTL, thay Sheets hoàn toàn) |
| Auth | Không có | **FastAPI-Users + python-jose (JWT) + bcrypt** |
| Encryption | Không có | **cryptography (Fernet)** |
| Frontend | Không có | **Next.js 14 + Tailwind CSS** |
| Secrets management | `.env` file | **Doppler** hoặc server env vars |
| Error tracking | `print()` | **Sentry + structlog** |
| Payments | Không có | **Stripe** hoặc **PayOS** (cho VN users) |
| Deployment | Python trực tiếp | **Docker Compose** (app + postgres + redis + celery) |

---

## Pricing Tiers

| Feature | Free | Pro (~$4/tháng) | Team (~$10/tháng) |
|---|---|---|---|
| Transaction categorization | ✅ | ✅ | ✅ |
| /status, /today, /allocate | ✅ | ✅ | ✅ |
| Daily recap tự động | ❌ | ✅ | ✅ |
| Weekly + Monthly report | ❌ | ✅ | ✅ |
| Multi-platform (Zalo, Viber…) | ❌ | ✅ | ✅ |
| Auto-categorize (AI) | ❌ | ❌ | ✅ |
| Số tài khoản | 1 | 1 | Đến 3 |

**Upgrade trigger**: sau 7 ngày free dùng bot không có scheduled recap → bot tự gửi 1 message upgrade duy nhất.

---

## Security

| Concern | Giải pháp |
|---|---|
| Credential at rest | Fernet encryption, key chỉ trong env var |
| Service account JSON | Không bao giờ trả về trong API response, chỉ hiện masked summary |
| Webhook auth | UUID path + separate path_token + Telegram secret header |
| Tenant isolation | Mọi DB query scope theo tenant_id; JWT claims validate tenant_id |
| Cross-tenant Sheets | `_get_spreadsheet()` cache keyed by tenant_id, không dùng global |
| Rate limiting | Nginx limit_req_zone keyed on tenant_id: 60 req/min default |
| Bot state | Redis keyed `bot_state:{tenant_id}:{chat_id}` — không thể cross-tenant |
| Data minimization | 0 transaction data lưu trong platform DB; bot state TTL 24h |
| Account deletion | Xóa credentials + deregister Telegram webhook + purge Redis keys |

---

## Migration Path

### Day 1 — Migration script (không downtime)
```python
# Chạy 1 lần để seed tenant từ .env hiện tại
tenant_id = "a1b2c3d4-..."  # fixed UUID
db.insert_tenant(id=tenant_id, email="owner@email.com", status="active")
db.insert_credentials(tenant_id, platform="telegram",
    bot_token_enc=encrypt(os.getenv("BOT_TOKEN")),
    chat_id_enc=encrypt(os.getenv("CHAT_ID")),
    sheet_id_enc=encrypt(os.getenv("SHEET_ID")),
    service_account_enc=encrypt(open("credentials.json").read())
)
# Bot tiếp tục chạy bình thường, dùng tenant_id cố định này
```

### Tháng 1 — Infra & Core refactor
- [ ] Setup PostgreSQL + Redis + Docker Compose
- [ ] Implement `TenantContext`, `encryption.py`, `dependencies.py`
- [ ] Refactor `sheets.py` — fix cross-tenant cache bug (critical)
- [ ] Refactor `telegram_api.py` — nhận `ctx` param
- [ ] Refactor `handlers/` — nhận `ctx` param
- [ ] Migrate bot state từ Sheets → Redis
- [ ] Webhook routing `/webhook/{tenant_id}/{source}`
- [ ] Celery workers thay thế cron

### Tháng 2 — Auth & Onboarding
- [ ] FastAPI auth endpoints (signup, login, JWT refresh)
- [ ] Onboarding wizard API (validate token, register webhook, verify sheet)
- [ ] Next.js frontend cơ bản (signup + 6-step wizard)
- [ ] Tenant dashboard (status, webhook URLs, regenerate token)

### Tháng 3 — Launch & Monetize
- [ ] Tích hợp Stripe/PayOS
- [ ] Plan gates trong handlers (kiểm tra `ctx.plan` trước scheduled reports)
- [ ] Sentry error tracking
- [ ] Landing page + SEO
- [ ] Beta launch với 10 users đầu tiên

### Tháng 4+ — Growth
- [ ] Multi-platform (Zalo OA adapter)
- [ ] Auto-categorize dựa trên lịch sử
- [ ] Team plan (multi-account, shared sheet)
- [ ] Analytics dashboard trong UI

---

## Điểm quan trọng nhất khi bắt đầu

**Bước đầu tiên và quan trọng nhất** là wrap globals thành `TenantContext`. Hiện tại `config.py` export `BOT_TOKEN`, `CHAT_ID`, `SHEET_ID` dưới dạng module-level constants và handlers import trực tiếp — điều này khiến multi-tenancy về mặt kiến trúc là không thể nếu không refactor.

`TenantContext` dataclass được truyền qua function parameter (không phải global hay threadlocal) là foundation mà toàn bộ kiến trúc SaaS build lên trên.
