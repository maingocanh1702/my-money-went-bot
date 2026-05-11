# Unified Plan: Multi-Tenant Multi-Platform SaaS

> Merge của `REFACTOR_MULTIPLATFORM.md` + `SAAS_PLAN.md` + fixes từ cả 2 bản đánh giá.
> 2 file gốc giữ nguyên để reference.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                                 │
│        Vite + vanilla JS (signup · wizard · dashboard)          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼─────────────────────────────────────┐
│                     FASTAPI APPLICATION                          │
│  /api/auth/*          — signup, login, JWT                      │
│  /api/tenants/*       — CRUD credentials, dashboard             │
│  /webhook/{tid}/{src} — SePay · Telegram · Zalo · Viber ...    │
│  /trigger/*           — per-tenant scheduled jobs (APScheduler) │
└───────┬──────────────────┬──────────────────┬───────────────────┘
        │                  │                  │
   ┌────▼────┐      ┌──────▼──────┐    ┌──────▼──────┐
   │Dispatcher│      │  fan_out()  │    │ APScheduler │
   │→1 platf. │      │→ all platf. │    │ per-tenant  │
   └────┬────┘      └──────┬──────┘    └──────┬──────┘
        │                  │                  │
   ┌────▼──────────────────▼──────────────────▼───────┐
   │              handlers/ (core logic)               │
   │    sepay · transaction · allocation · reports     │
   │         ALL receive ctx: BotContext               │
   └────┬──────────────────────────┬──────────────────┘
        │                          │
   ┌────▼──────────┐     ┌────────▼──────────────────┐
   │  sheets.py    │     │   Adapter Layer            │
   │ (per-tenant   │     │  Telegram·Zalo·Viber·...  │
   │  credentials) │     └───────────────────────────┘
   └───────────────┘
        │
   ┌────▼──────────────────────────────────────────────┐
   │                  STORAGE LAYER                     │
   │  PostgreSQL — tenants, credentials, webhook configs│
   │  Redis      — bot state (24h TTL), session cache   │
   └────────────────────────────────────────────────────┘
```

**Key decisions (resolved conflicts):**
- ~~Celery~~ → **APScheduler** in-process (đủ cho <100 tenants, upgrade sau)
- ~~Next.js~~ → **Vite + vanilla JS** (ship nhanh hơn 2 weeks)
- ~~2 context objects~~ → **1 unified BotContext** (merge TenantContext + BotContext)
- ~~Bot State in Sheets~~ → **Redis** (giảm 40% Sheets API calls)
- ~~UserRegistry in Sheets~~ → **PostgreSQL tenants table**

---

## 2. Directory Structure

```
bot-finance-saas/
├── app/
│   ├── main.py                    # FastAPI entry + routers
│   ├── core/
│   │   ├── config.py              # DATABASE_URL, REDIS_URL, FERNET_KEY
│   │   ├── encryption.py          # Fernet encrypt/decrypt
│   │   ├── dependencies.py        # resolve_tenant FastAPI dependency
│   │   ├── context.py             # BotContext (unified)
│   │   ├── dispatcher.py          # parse → route → handler
│   │   ├── fanout.py              # broadcast to all platforms
│   │   ├── buttons.py             # platform-agnostic button builders
│   │   └── scheduler.py           # APScheduler per-tenant jobs
│   ├── models/
│   │   ├── db.py                  # SQLAlchemy: tenants, credentials, webhooks
│   │   └── update.py              # IncomingUpdate, OutgoingMessage, Button
│   ├── adapters/
│   │   ├── base.py                # MessengerAdapter ABC
│   │   ├── __init__.py            # ADAPTER_REGISTRY
│   │   ├── telegram.py            # wrap telegram_api.py
│   │   ├── zalo.py                # Zalo OA REST
│   │   └── ...
│   ├── routers/
│   │   ├── auth.py                # /api/auth/*
│   │   ├── tenants.py             # /api/tenants/*
│   │   └── webhooks.py            # /webhook/{tid}/{src}
│   ├── services/
│   │   ├── webhook_registrar.py   # auto setWebhook
│   │   ├── sheet_setup.py         # auto-create Sheet tabs + headers
│   │   └── sheet_verifier.py      # validate Sheet access
│   ├── handlers/                  # ALL receive ctx: BotContext
│   │   ├── sepay.py
│   │   ├── transaction.py
│   │   ├── allocation.py
│   │   └── reports.py
│   ├── sheets.py                  # per-tenant, TTLCache, batched API calls
│   └── telegram_api.py            # GIỮA NGUYÊN — adapter wraps
├── frontend/                      # Vite + vanilla JS
│   ├── index.html
│   ├── pages/ (signup, wizard, dashboard)
│   └── ...
├── migrations/                    # Alembic
├── docker-compose.yml             # app + postgres + redis
└── requirements.txt
```

---

## 3. Unified BotContext

**Resolves conflict**: `BotContext` (multiplatform) vs `TenantContext` (SaaS) → 1 object.

```python
@dataclass
class BotContext:
    # ── Tenant-level (from SaaS plan) ──
    tenant_id:            str
    timezone:             str
    plan:                 str        # free | pro | team
    sheet_id:             str        # decrypted
    service_account_json: dict       # decrypted
    daily_bucket_id:      str

    # ── Request-level (from multiplatform plan) ──
    update:               IncomingUpdate
    adapter:              MessengerAdapter

    # ── Injected services ──
    _redis:               Redis      # for state ops
    _sheet_client:        gspread.Spreadsheet  # pre-initialized

    async def send(self, msg: OutgoingMessage) -> dict:
        return await self.adapter.send(self.update.platform_user_id, msg)

    async def get_state(self) -> dict | None:
        key = f"bot_state:{self.tenant_id}:{self.update.platform_user_id}"
        data = await self._redis.get(key)
        return json.loads(data) if data else None

    async def set_state(self, data: dict):
        key = f"bot_state:{self.tenant_id}:{self.update.platform_user_id}"
        await self._redis.setex(key, 86400, json.dumps(data))

    async def clear_state(self):
        await self.set_state({})

    def sheet(self, tab_name: str):
        return self._sheet_client.worksheet(tab_name)
```

Handlers chỉ cần `ctx: BotContext` — không import globals, không biết platform.

---

## 4. Normalized Data Models

Giữ nguyên từ `REFACTOR_MULTIPLATFORM.md` Section "Normalized Data Models", **bổ sung media**:

```python
@dataclass
class OutgoingMessage:
    text:              str
    buttons:           list[list[Button]] = field(default_factory=list)
    edit_message_id:   str | None = None
    delete_message_id: str | None = None
    image_url:         str | None = None   # NEW — for chart images
    parse_mode:        str = "markdown"
```

`IncomingUpdate`, `Button` → giữ nguyên từ `REFACTOR_MULTIPLATFORM.md`.

---

## 5. Platform-Agnostic Button Builders

**Fix từ multiplatform eval** — chuyển ra khỏi `telegram_api.py`:

```python
# core/buttons.py
from models.update import Button

def bucket_buttons(buckets: list[dict], prefix: str) -> list[list[Button]]:
    btns = [Button(label=b["name"], callback_data=f"{prefix}_{b['id']}") for b in buckets]
    return [btns[i:i+2] for i in range(0, len(btns), 2)]

def sub_buttons(subs: list[dict], prefix: str) -> list[list[Button]]:
    btns = [Button(label=s["label"], callback_data=f"{prefix}_{s['key']}") for s in subs]
    return [btns[i:i+2] for i in range(0, len(btns), 2)]
```

---

## 6. Adapter Layer + Dispatcher + Fan-out

Giữ nguyên design từ `REFACTOR_MULTIPLATFORM.md`:
- `MessengerAdapter` ABC (xem Section "Abstract Adapter Interface")
- `TelegramAdapter` wraps `telegram_api.py` (xem Section "TelegramAdapter")
- `Dispatcher` (xem Section "Dispatcher")
- `fan_out()` (xem Section "Fan-Out Engine")

**Bổ sung error handling trong Dispatcher** (fix từ multiplatform eval):

```python
# core/dispatcher.py — thêm vào dispatch()
try:
    # ... existing dispatch logic
except Exception as e:
    import traceback
    print(f"[dispatch] ERROR: {traceback.format_exc()}")
    try:
        await adapter.send(update.platform_user_id,
            OutgoingMessage(text=f"⚠️ Bot gặp lỗi: `{e}`"))
    except Exception:
        pass
```

**Thay đổi so với multiplatform plan:**
- `telegram_api.py` functions nhận `bot_token: str` param thay vì global `BOT_TOKEN`
- `TelegramAdapter.__init__(self, bot_token: str)` — instantiated per-tenant
- Adapter KHÔNG cached globally — created per webhook request (lightweight)

---

## 7. Database Schema

Giữ nguyên 4 tables từ `SAAS_PLAN.md` Section "Database Schema":
- `tenants` — email, password_hash, timezone, plan, status
- `tenant_credentials` — encrypted bot_token, chat_id, sheet_id, service_account
- `webhook_configs` — path_token, secret_token per source
- `scheduled_jobs` — per-tenant job scheduling

**Bổ sung**: `tenant_platforms` table (thay thế UserRegistry Sheets tab):

```sql
CREATE TABLE tenant_platforms (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    display_name    TEXT,
    is_primary      BOOLEAN DEFAULT FALSE,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, platform)
);
```

---

## 8. Webhook Routing

```python
@app.post("/webhook/{tenant_id}/{source}")
async def webhook_router(
    tenant_id: str, source: str,
    request: Request, bg: BackgroundTasks,
    ctx: TenantContext = Depends(resolve_tenant)  # validates path_token
):
    body = await request.json()
    if source == "sepay":
        bg.add_task(process_sepay, body, ctx)
    elif source in ADAPTER_REGISTRY:
        adapter = ADAPTER_REGISTRY[source](ctx.bot_token)  # per-tenant instance
        bg.add_task(Dispatcher.dispatch, adapter, body, ctx)
    return JSONResponse({"ok": True})
```

`resolve_tenant` → validates `path_token` query param + loads/decrypts credentials.
Xem `SAAS_PLAN.md` Section "Tenant Resolution" cho full implementation.

---

## 9. Scheduled Jobs — APScheduler (simplified)

**Thay thế Celery** — đủ cho <100 tenants:

```python
# core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(poll_due_jobs, "interval", seconds=60)
    scheduler.start()

async def poll_due_jobs():
    jobs = await db.query("""
        SELECT sj.*, t.timezone FROM scheduled_jobs sj
        JOIN tenants t ON t.id = sj.tenant_id
        WHERE sj.enabled = true AND sj.next_run_utc <= NOW()
        AND t.status = 'active'
    """)
    for job in jobs:
        ctx = await build_tenant_context(job.tenant_id)
        asyncio.create_task(run_scheduled_job(job, ctx))
        await db.update_next_run(job.id, compute_next_run(job))

async def run_scheduled_job(job, ctx):
    if   job.job_type == "daily_recap":       await send_daily_recap(ctx)
    elif job.job_type == "weekly":            await run_weekly_summary(ctx)
    elif job.job_type == "monthly_report":    await run_monthly_report(ctx)
    elif job.job_type == "monthly_allocation":await start_monthly_allocation(ctx)
```

Trigger endpoints cũng refactored — nhận `tenant_id`, build context:

```python
@app.post("/trigger/{tenant_id}/daily-recap")
async def trigger_daily_recap(tenant_id: str):
    ctx = await build_tenant_context(tenant_id)
    asyncio.create_task(send_daily_recap(ctx))  # fan_out inside
    return {"ok": True}
```

---

## 10. Sheets.py Refactor

**3 critical changes:**

### 10a. TTLCache thay lru_cache (fix stale credentials)
```python
from cachetools import TTLCache
_sheets_cache = TTLCache(maxsize=100, ttl=1800)  # 30 min

def _get_spreadsheet(ctx: BotContext):
    if ctx.tenant_id in _sheets_cache:
        return _sheets_cache[ctx.tenant_id]
    creds = Credentials.from_service_account_info(ctx.service_account_json, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(ctx.sheet_id)
    _sheets_cache[ctx.tenant_id] = ss
    return ss
```

### 10b. Batch API calls (fix rate limits)
```python
# BEFORE: 4 API calls
ws.update_cell(row_num, 11, parent_category)
ws.update_cell(row_num, 12, sub_label)
ws.update_cell(row_num, 13, is_daily)
ws.update_cell(row_num, 14, "TRUE")

# AFTER: 1 API call
ws.update(f"K{row_num}:N{row_num}", [[parent_category, sub_label, is_daily, "TRUE"]])
```

### 10c. Mọi function nhận ctx
```python
# BEFORE
def get_active_buckets(month_key: str) -> list[dict]:
    ws = _sheet(S.BUDGET_CONFIG)  # global spreadsheet

# AFTER
def get_active_buckets(ctx: BotContext, month_key: str) -> list[dict]:
    ws = ctx.sheet(S.BUDGET_CONFIG)  # tenant-scoped
```

---

## 11. Auto Sheet Setup (fix onboarding friction)

User chỉ cần: tạo blank Google Sheet → share với service account → paste ID.
Platform tự tạo tabs + headers:

```python
# services/sheet_setup.py
SHEET_STRUCTURE = {
    "Đầu ra": ["ID","Ngày giao dịch","","","","Nội dung","Loại","Số tiền",
               "Mã tham chiếu","Lũy kế","Parent Category","Sub-category",
               "Is Daily Spending","Confirmed","Month"],
    "Budget Config": ["Month","Bucket ID","Name","Allocated","Daily Cap","Active","Source","Notes"],
    "Sub-category Config": ["Bucket ID","Key","Label","Active"],
    "Monthly Reports": ["Month","Bucket","Allocated","Spent","Remaining","Pct","Generated At"],
}

async def initialize_sheet(ctx):
    ss = _get_spreadsheet(ctx)
    for tab_name, headers in SHEET_STRUCTURE.items():
        try:
            ws = ss.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(tab_name, rows=1000, cols=len(headers))
        ws.update("A1", [headers])
```

---

## 12. Onboarding Wizard — 5 Steps (simplified)

```
Step 1 — Tạo Telegram Bot
  User: @BotFather → /newbot → paste token
  Platform: getMe validate → hiện bot username
  Platform: Auto-register webhook

Step 2 — Lấy Chat ID (SIMPLIFIED — bỏ SSE)
  Platform: Bot đã active → user gửi /start cho bot
  Bot auto-reply: "👋 Your Chat ID is: `123456789`. Copy this!"
  User: Paste chat_id vào form
  Platform: Validate chat_id bằng sendMessage test

Step 3 — Google Sheet
  User: Tạo blank Google Sheet
  Platform: Hiển thị service account email → user bấm Share
  User: Paste Sheet ID
  Platform: Verify access → AUTO-CREATE tabs + headers

Step 4 — SePay
  Platform: Hiển thị webhook URL + nút Copy
  User: Dán vào SePay dashboard
  Platform: Đợi transaction đầu tiên confirm

Step 5 — Initial Budget
  Platform: Trigger /allocate qua Telegram
  UI: "Bot sẵn sàng 🎉"
```

---

## 13. Security

Giữ nguyên từ `SAAS_PLAN.md` Section "Security" — không thay đổi.

---

## 14. Encryption

Giữ nguyên từ `SAAS_PLAN.md` Section "Credential Encryption" — không thay đổi.

---

## 15. Handler Changes Summary

Mọi handler thay đổi giống nhau:

| Before | After |
|--------|-------|
| `from config import CHAT_ID` | Xóa |
| `import telegram_api as tg` | Xóa |
| `async def func():` | `async def func(ctx: BotContext):` |
| `sh.get_state(CHAT_ID)` | `await ctx.get_state()` |
| `sh.set_state(CHAT_ID, data)` | `await ctx.set_state(data)` |
| `tg.send_text(msg)` | `await ctx.send(OutgoingMessage(text=msg))` |
| `tg.send_with_buttons(msg, btns)` | `await ctx.send(OutgoingMessage(text=msg, buttons=btns))` |
| `tg.edit_message(id, text)` | `await ctx.send(OutgoingMessage(text=text, edit_message_id=str(id)))` |
| `tg.delete_message(id)` | `await ctx.send(OutgoingMessage(text="", delete_message_id=str(id)))` |
| `tg.build_bucket_buttons(b, p)` | `buttons.bucket_buttons(b, p)` |
| `sh.get_active_buckets(mk)` | `sh.get_active_buckets(ctx, mk)` |

Xem `REFACTOR_MULTIPLATFORM.md` Section "Thay đổi trong từng Handler" cho chi tiết per-file.

---

## 16. Pricing

| Feature | Free | Pro (~$4/mo) | Team (~$10/mo) |
|---------|------|-------------|----------------|
| Transaction categorization | ✅ | ✅ | ✅ |
| /status, /today, /allocate | ✅ | ✅ | ✅ |
| **Daily recap tự động** | **✅** | ✅ | ✅ |
| Weekly + Monthly report | ❌ | ✅ | ✅ |
| Multi-platform | ❌ | ✅ | ✅ |
| Auto-categorize (AI) | ❌ | ❌ | ✅ |
| Số tài khoản | 1 | 1 | 3 |

> Daily recap cho Free tier (thay đổi vs SAAS_PLAN) — đây là hook giữ user quay lại hàng ngày.

---

## 17. Platform Support Matrix

Giữ nguyên từ `REFACTOR_MULTIPLATFORM.md` Section "Platform Support Matrix".

**Platform-specific gotchas cần address:**

| Platform | Gotcha | Solution |
|----------|--------|----------|
| Zalo OA | Token expires 1h | Refresh cron trong adapter.setup() |
| WhatsApp | Max 3 buttons | Paginate bucket list nếu >3 |
| WhatsApp | 24h reply window | Detect + use template messages |
| Discord | Interaction token 15min | Warn user nếu allocation flow chậm |

---

## 18. Migration Plan — 6 Weeks

### Week 1-2: Foundation (zero risk to current bot)

- [ ] PostgreSQL schema + Alembic migrations
- [ ] `core/config.py` — DATABASE_URL, REDIS_URL, FERNET_KEY
- [ ] `core/encryption.py` — Fernet helpers
- [ ] `models/update.py` — IncomingUpdate, OutgoingMessage, Button
- [ ] `adapters/base.py` + `adapters/telegram.py` (wrap telegram_api.py)
- [ ] `core/context.py` — unified BotContext
- [ ] `core/dispatcher.py` — with error handling
- [ ] `core/fanout.py`
- [ ] `core/buttons.py` — platform-agnostic builders
- [ ] Redis setup → bot state migration (get_state/set_state → Redis)
- [ ] `sheets.py` refactor — TTLCache, batch API, ctx param
- [ ] Seed migration script: `.env` values → first tenant row
- [ ] **Telegram bot continues running on current code** — no disruption

### Week 3-4: Self-Service + Handler Refactor

- [ ] Auth endpoints (signup, login, JWT)
- [ ] `core/dependencies.py` — resolve_tenant
- [ ] Webhook routing `/webhook/{tid}/{src}`
- [ ] `services/sheet_setup.py` — auto-create tabs
- [ ] `services/webhook_registrar.py` — auto setWebhook
- [ ] Onboarding API (5-step validation flow)
- [ ] Refactor `handlers/reports.py` → ctx param → smoke test
- [ ] Refactor `handlers/allocation.py` → ctx param → smoke test
- [ ] Refactor `handlers/transaction.py` → ctx param → smoke test
- [ ] Refactor `handlers/sepay.py` → ctx param → smoke test
- [ ] `core/scheduler.py` — APScheduler per-tenant
- [ ] Run parallel: old `/webhook` + new `/webhook/{tid}/telegram`
- [ ] When OK → remove old routes

### Week 5-6: Frontend + Launch

- [ ] Vite frontend: signup → 5-step wizard → dashboard
- [ ] Plan gates in handlers (`if ctx.plan == "free": skip weekly`)
- [ ] Sentry error tracking + structlog
- [ ] PayOS/Stripe integration
- [ ] Landing page
- [ ] Docker Compose (app + postgres + redis)
- [ ] Beta launch with 5-10 users

### Month 2+: Growth

- [ ] Zalo OA adapter
- [ ] Viber, WhatsApp adapters
- [ ] Auto-categorize (AI)
- [ ] Team plan (multi-account)
- [ ] Analytics dashboard
- [ ] Upgrade to Celery if >100 tenants

---

## 19. Key Design Decisions

**Tại sao 1 BotContext thay vì TenantContext + BotContext riêng?**
Handlers cần cả tenant info (sheet_id, timezone) và request info (update, adapter). 2 objects = phải pass 2 params everywhere. 1 merged object = clean API, dễ test.

**Tại sao APScheduler thay vì Celery?**
Celery cần Redis broker + separate worker processes + celery-redbeat + monitoring (Flower). APScheduler chạy in-process, zero extra infra. Migrate lên Celery khi >100 tenants.

**Tại sao Vite thay vì Next.js?**
Onboarding wizard + dashboard = ~5 pages. Không cần SSR, không cần API routes, không cần React hydration. Vite + vanilla JS ship trong 1 week thay vì 2-3.

**Tại sao mỗi tenant phải upload own service account?**
Google Sheets API limit: 60 req/min/service account. Shared service account → 10 tenants = 6 req/min/tenant = chết. Each tenant's own service account = isolated quota.

**Tại sao giữ nguyên telegram_api.py?**
Module đã test 100%, TelegramAdapter delegate vào nó. Chỉ thêm `bot_token` param thay vì global. Zero regression risk.

---

## 20. Testing Plan

| Phase | Type | What |
|-------|------|------|
| Week 1 | Unit | `TelegramAdapter.parse_incoming()` — message, callback, bot echo, empty |
| Week 1 | Unit | `BotContext.send()` → adapter delegation |
| Week 1 | Unit | `encryption.encrypt/decrypt` roundtrip |
| Week 2 | Integration | Webhook → Dispatcher → handler → response (mock tg API) |
| Week 3 | Regression | Each handler: same input → same output as before refactor |
| Week 3 | Integration | Onboarding flow: signup → validate token → register webhook |
| Week 4 | E2E | Mock SePay → fan_out → both adapters receive |
| Week 5 | E2E | Full signup → onboarding → first transaction → categorize |

---

## 21. Checklist trước khi code

- [ ] Chọn domain name cho SaaS platform
- [ ] Setup PostgreSQL + Redis (local Docker hoặc managed)
- [ ] Tạo `FERNET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Quyết định: user upload own service account (recommended) hay platform cung cấp managed?
- [ ] Setup Sentry project
- [ ] Setup Stripe/PayOS account
