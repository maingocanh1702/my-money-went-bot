# Feature Spec — Refactor: Personal Bot → SaaS Multi-tenant

> **Version:** v1.3.0
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase liên quan:** BRD Phase 1-2 (tuần 1-4) + ảnh hưởng Phase 3-6 (Messenger build Tuần 10-11 reuse foundation này)
> **Tham chiếu:** [PRD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md) section 1.4, 4, 5.4 · [BRD v2.9.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md) section 1.6, 2.2, 8 · [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-messenger-channel.md)

---

## 1. Mục tiêu & non-goals

### 1.1. Mục tiêu

Refactor codebase từ **personal single-tenant bot** (1 user duy nhất, hardcoded `CHAT_ID`, Google Sheets storage, Apps Script email ingest) sang **SaaS multi-tenant** (shared bot, Postgres, Postmark) — sao cho 100+ user có thể signup/dùng đồng thời mà không cần deploy riêng.

Đây là **prerequisite** cho mọi feature trong Phase 3-8 của BRD. Không refactor xong không thể build pricing/onboarding/email parsing đa user.

### 1.2. Non-goals

- KHÔNG add feature mới trong refactor này (ngoài infra). Pricing, 3-path onboarding, parser ACB/STB/BIDV/MB nằm ở Phase 3-5.
- KHÔNG migrate data từ personal bot hiện tại sang SaaS DB (founder sẽ là beta user #1, signup lại như user thường).
- KHÔNG support Google Sheets làm storage cho user (founder có thể tự dùng cho personal data — không phải phần SaaS).

---

## 2. Diff: current → target

### 2.1. Architecture diff

| Layer | Current | Target |
|-------|---------|--------|
| Bot model | 1 user, hardcoded `CHAT_ID` env | **2 channel** (Telegram bot + Messenger Page) shared, lookup channel_user_id từ DB |
| Identity | `os.environ["CHAT_ID"]` | `users.channel_type` + `users.channel_user_id` (UNIQUE pair). Telegram + Messenger live MVP, single-channel per user |
| Storage | Google Sheets (single sheet) | PostgreSQL (multi-tenant, scoped by `user_id`) |
| Webhook routing | Single `/webhook` xử lý cả Telegram + SePay | Tách 4 endpoint: `/webhook/telegram`, `/webhook/messenger` (GET verify + POST), `/hook/{user_token}`, `/inbound/{user_token}` |
| Email ingest | Google Apps Script + secret | Postmark Inbound + per-user `u{id}@in.fintrack.app` |
| State machine | `sh.get_state(CHAT_ID)` (Sheets) | `db.get_state(user_id)` (Postgres), channel-agnostic |
| Scheduling | `crontab.txt` ngoài app | APScheduler in-process, per-user timezone |
| Categories | Hardcoded buckets trong Sheets | `categories` table, per-user CRUD |
| Outbound | Direct Telegram API call từ handler | `services/messenger.py` route to `services/channels/{telegram,messenger}.py` adapter via `BaseSender` interface |

### 2.2. Code keep / rewrite / delete

**Keep (~30%):**
- Email parser logic TCB + Cake regex patterns (nhưng wrap vào plugin pattern — xem section 5)
- Categorization state machine `await_parent` → `await_sub` → `done` (logic giữ, storage đổi)
- Report formatting (text template cho `/status`, `/today`, daily recap)
- Date/timezone helpers
- Amount parsing helpers (`_parse_amount_str`, `_find_ref_code`)

**Rewrite (~50%):**
- `main.py` — endpoint structure, dispatcher, command handler
- `telegram_api.py` — bỏ default `CHAT_ID`, **migrate logic vào `services/channels/telegram.py`** (handlers KHÔNG call telegram API directly — go through `messenger.send(user_id, payload)` interface). Initial impl direct-send, swap sang queue-backed sau không refactor handlers. File `telegram_api.py` cũ delete sau migration.
- `services/messenger.py` — **NEW**: single point of outbound message dispatch. Resolve `channel_type` + `channel_user_id` + `bot_id` từ `users` table, dispatch tới appropriate channel adapter. Foundation cho C9 outbound queue + C8 bot pool + Messenger MVP build.
- `services/channels/base.py` — **NEW**: `BaseSender` ABC với `send_text()`, `send_image()`, `send_picker()`, `edit_message()` abstract methods.
- `services/channels/telegram.py` — **NEW**: `TelegramSender` class implement `BaseSender`, di chuyển code từ `telegram_api.py`.
- `services/channels/messenger.py` — **NEW (Phase 6 Tuần 10-11)**: `MessengerSender` class implement `BaseSender` qua Meta Send API. Detail: [feature-spec-messenger-channel §5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-messenger-channel.md).
- `handlers/sepay.py` — accept `user_id` context
- `handlers/transaction.py` — DB-backed state thay vì Sheets
- `handlers/manage.py` — DB CRUD thay vì Sheets row manipulation
- `handlers/reports.py` — query Postgres, scope `user_id`
- `handlers/allocation.py` — DB-backed budget
- `config.py` — bỏ `CHAT_ID`, `SHEET_ID`; thêm `DATABASE_URL`, `POSTMARK_TOKEN`, `BOT_TOKEN_BACKUP`

**Delete (~20%):**
- `sheets.py` — toàn bộ (thay bằng `db.py` với asyncpg/SQLAlchemy)
- `google_apps_script.js` — bỏ (Postmark thay thế)
- `crontab.txt` — bỏ (APScheduler thay thế)
- `setup.sh` — single-deploy script, không cần
- `credentials.json` (Google Sheets API creds) — không cần
- `BOT_TOKEN`/`CHAT_ID`/`SHEET_ID` env vars — replace với multi-tenant equivalents

---

## 3. Acceptance Criteria

### 3.1. Functional

- [ ] 2 user khác nhau cùng signup, mỗi người có data hoàn toàn isolated (test: user A `/status` không bao giờ thấy tx của user B, kể cả sau race condition)
- [ ] User A regenerate webhook URL → user B's URL không bị ảnh hưởng
- [ ] Bot reply về đúng `chat_id` cho mỗi user (test: 2 user gửi `/today` đồng thời, mỗi người nhận đúng data của mình)
- [ ] State machine isolated: user A đang `await_sub`, user B `/start` → state A không bị clear
- [ ] Scheduled job per user fire đúng timezone (test: user A timezone Asia/Ho_Chi_Minh, user B timezone Asia/Tokyo, daily recap fire 23:00 local cho từng người)

### 3.2. Multi-tenant data isolation

- [ ] Mọi SQL query trong code có `WHERE user_id = $1` — verify bằng grep `SELECT|UPDATE|DELETE` không match nào thiếu scope
- [ ] DB constraint: `transactions.user_id NOT NULL`, FK vào `users.id` ON DELETE CASCADE
- [ ] Webhook `/hook/{user_token}` invalid token → 200 + log warning, không leak existence của other tokens
- [ ] Error message gửi cho user không chứa user_id/email/token của user khác
- [ ] Test: insert tx với `user_id=A`, query với `user_id=B` → không thấy

### 3.3. Bot ownership + Webhook routing + Messenger interface

- [ ] `BOT_TOKEN` chỉ ở Railway env vars, grep code không có hardcoded string `bot{token}`
- [ ] `chat_id` resolved qua `users` table cho mọi outbound message (no hardcoded fallback)
- [ ] `users.telegram_id` UNIQUE constraint enforced
- [ ] `BOT_TOKEN_BACKUP` env var documented, runbook switchover < 5 phút
- [ ] **Messenger interface enforce**: tất cả outbound message từ handlers/services đi qua `messenger.send(user_id, payload)`. Grep `await tg.send_*` hoặc direct `httpx.post` tới Telegram API ở handler files → 0 hits (chỉ allowed trong `services/messenger.py`)
- [ ] Messenger initial impl direct-send. Architecture cho phép swap sang queue-backed (C9) **không refactor handlers** — only swap internal implementation của `Messenger.send()`
- [ ] **Admin command auth framework**: env `ADMIN_TELEGRAM_IDS` (comma-separated), decorator `@admin_only` available, every admin invocation auto-logged vào `admin_audit_log`
- [ ] **Webhook routing checks `PLATFORM_TOKEN` BEFORE user token lookup**: `/hook/{PLATFORM_TOKEN}` và `/inbound/{PLATFORM_TOKEN}` route tới `payment_matcher` service, KHÔNG BAO GIỜ tới user transaction pipeline. Áp dụng cho cả Phase 1-2 (placeholder) + Phase 6 (real implementation). Xem [feature-spec-payment-bank-transfer.md §2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-payment-bank-transfer.md).
- [ ] **`PLATFORM_TOKEN` không collide với bất kỳ `users.webhook_token`**: enforce ở user creation thời điểm — `INSERT ... WHERE webhook_token != $PLATFORM_TOKEN`. Hoặc reserve range/prefix cho platform token (vd start với `_PLT_`).
- [ ] Test: `POST /hook/{PLATFORM_TOKEN}` không bao giờ INSERT vào `transactions` table (chỉ vào `payment_matches` / `unmatched_payments`)
- [ ] Test: `POST /hook/{user_token}` không bao giờ INSERT vào `payment_matches` (chỉ vào `transactions`)

### 3.4. Migration safety

- [ ] Founder's personal bot tiếp tục chạy trong suốt refactor (không downtime)
- [ ] SaaS deploy ở subdomain riêng (`app.fintrack.app` hoặc `bot-staging.fintrack.app`) trước khi point production
- [ ] DB migration script có rollback path
- [ ] Postmark inbound parsing test với 5+ email mẫu của TCB + Cake trước khi cutover

### 3.5. Performance regression check

- [ ] Bot reply latency < 2s (target NFR PRD 5.1) — đo trong staging với 10 concurrent user
- [ ] DB query < 50ms cho `/status` của user có 100 tx — index trên `(user_id, tx_date)` bắt buộc
- [ ] Memory footprint app instance < 256MB ở 0 traffic (Railway baseline)

---

## 4. Data Model migration

### 4.1. New tables (target schema, simplified)

```sql
CREATE TABLE users (
  id              SERIAL PRIMARY KEY,
  telegram_id     BIGINT UNIQUE NOT NULL,
  chat_id         BIGINT NOT NULL,
  username        TEXT,
  webhook_token   TEXT UNIQUE NOT NULL,         -- 24-char URL-safe
  inbound_email   TEXT UNIQUE NOT NULL,         -- u{id}@in.fintrack.app
  timezone        TEXT DEFAULT 'Asia/Ho_Chi_Minh',
  plan            TEXT DEFAULT 'free',           -- 'free'|'pro'|'business'
  trial_ends_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE categories (
  id              SERIAL PRIMARY KEY,
  user_id         INT REFERENCES users(id) ON DELETE CASCADE,
  slug            TEXT NOT NULL,
  name            TEXT NOT NULL,
  daily_cap       BIGINT,
  monthly_budget  BIGINT,
  active          BOOLEAN DEFAULT TRUE,
  UNIQUE(user_id, slug)
);

CREATE TABLE transactions (
  id              BIGSERIAL PRIMARY KEY,
  user_id         INT REFERENCES users(id) ON DELETE CASCADE,
  category_id     INT REFERENCES categories(id),
  amount          BIGINT NOT NULL,
  direction       TEXT NOT NULL,                 -- 'in'|'out'
  description     TEXT,
  ref_code        TEXT,
  tx_date         TIMESTAMPTZ NOT NULL,
  source          TEXT,                          -- 'sepay'|'email_tcb'|...
  confirmed       BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, ref_code)
);
CREATE INDEX idx_tx_user_date ON transactions(user_id, tx_date DESC);

CREATE TABLE bot_state (
  user_id         INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  step            TEXT,                          -- 'await_parent'|'await_sub'|...
  payload         JSONB,
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scheduled_jobs (
  id              SERIAL PRIMARY KEY,
  user_id         INT REFERENCES users(id) ON DELETE CASCADE,
  job_type        TEXT NOT NULL,                 -- 'daily_recap'|...
  next_run_utc    TIMESTAMPTZ NOT NULL,
  enabled         BOOLEAN DEFAULT TRUE,
  last_run_at     TIMESTAMPTZ,
  UNIQUE(user_id, job_type)
);
CREATE INDEX idx_jobs_next_run ON scheduled_jobs(next_run_utc) WHERE enabled = TRUE;

CREATE TABLE bank_connections (
  id              SERIAL PRIMARY KEY,
  user_id         INT REFERENCES users(id) ON DELETE CASCADE,
  source_type     TEXT NOT NULL,                 -- 'sepay'|'email'
  bank_id         TEXT,                          -- 'tcb'|'mb'|...
  email_address   TEXT,                          -- forwarded source email user setup
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Admin audit log — required từ Phase 1 vì admin actions affect schema/auth pattern
-- Detail spec: docs/feature-spec-admin-tools.md (write trước Phase 1 dev)
CREATE TABLE admin_audit_log (
  id              BIGSERIAL PRIMARY KEY,
  admin_telegram_id BIGINT NOT NULL,
  command         VARCHAR(64) NOT NULL,
  target_user_id  INT REFERENCES users(id),
  payload         JSONB,
  result          VARCHAR(16),                   -- 'success'|'fail'|'denied'
  error_message   TEXT,
  executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admin_audit_admin ON admin_audit_log(admin_telegram_id, executed_at DESC);
CREATE INDEX idx_admin_audit_target ON admin_audit_log(target_user_id, executed_at DESC);
```

> **Note:** Schema đầy đủ + migration scripts thuộc TDD, không phải feature spec. File này chỉ đảm bảo data model align với multi-tenant requirement.

### 4.2. No data migration from current

Founder personal bot data ở Google Sheets sẽ KHÔNG migrate. Founder signup lại như user beta #1 từ tháng 9/2026. Lý do:

- Schema khác hoàn toàn (Sheets row → relational rows)
- Personal data có những hack/inconsistency tích lũy 1 năm → dirty data
- Migration effort 1-2 tuần không đáng cho 1 user

---

## 5. Refactor sub-tasks (estimate effort)

### Phase 1.1 — DB foundation (3-4 ngày)

- [ ] Setup PostgreSQL ở Railway (managed addon)
- [ ] Viết `db.py` — asyncpg connection pool + transaction context manager
- [ ] Tạo migration tool (Alembic hoặc raw SQL files với version)
- [ ] Implement schema section 4.1 + seed data cho 3 default categories
- [ ] Unit test: connection pool, query helpers, isolation per `user_id`

### Phase 1.2 — User model + Telegram routing + Messenger interface (4-5 ngày)

- [ ] `handlers/users.py` — `get_or_create_user(telegram_id, chat_id, username)`
- [ ] Generate `webhook_token` (secrets.token_urlsafe(18) ≈ 24-char) + `inbound_email`
- [ ] `services/messenger.py` **NEW** — single point outbound dispatch. Interface `send(user_id, payload)`. Initial direct-send impl, ready cho queue swap C9.
- [ ] `telegram_api.py` refactor: bỏ default `CHAT_ID`, **wrap thành internal of Messenger** (handlers KHÔNG import telegram_api directly)
- [ ] `main.py` Telegram endpoint: extract `from.id` → resolve user → dispatch
- [ ] **Admin auth framework**: `services/admin.py` với `@admin_only` decorator + audit logger; env `ADMIN_TELEGRAM_IDS` parsing
- [ ] Test: 2 mock user, verify isolation
- [ ] Test: grep handlers cho direct telegram API call → 0 hits (chỉ messenger)

### Phase 2.1 — State machine + handlers refactor (5-7 ngày)

- [ ] Migrate `bot_state` từ Sheets → Postgres `bot_state` table
- [ ] Refactor `handlers/transaction.py` — accept `user_id` context, query/insert scoped
- [ ] Refactor `handlers/manage.py` — categories CRUD via DB
- [ ] Refactor `handlers/reports.py` — `/status`, `/today` query DB scoped
- [ ] Refactor `handlers/allocation.py` — budget CRUD via DB
- [ ] Refactor `handlers/sepay.py` — accept `user_token` from URL, lookup user, scope writes

### Phase 2.2 — Webhook routing (2-3 ngày)

- [ ] `POST /telegram/webhook` — receive Telegram updates
- [ ] `POST /hook/{user_token}` — SePay per-user, validate token
- [ ] `POST /inbound/{user_token}` — Postmark per-user (placeholder until Phase 5)
- [ ] Set Telegram webhook qua API: `setWebhook` URL = `/telegram/webhook`
- [ ] Test: invalid token returns 200 + log, không leak

### Phase 2.3 — Scheduling (3-4 ngày)

- [ ] APScheduler setup, replace `crontab.txt`
- [ ] `scheduled_jobs` table + per-user fire logic
- [ ] Timezone-aware `next_run_utc` calculation
- [ ] Jitter ±5 phút deterministic theo `user_id` (PRD 5.4.2 mitigation)
- [ ] Job: daily_recap, weekly, monthly_report, monthly_allocation
- [ ] Job failure isolation — 1 job error không block others

### Phase 2.4 — Email parser plugin pattern (2-3 ngày, prep cho Phase 5)

- [ ] Refactor `handlers/email_parser.py` thành package `handlers/email_parser/`
- [ ] `base.py` — `BaseParser` ABC: `sender_match()`, `parse() → CanonicalTx | None`
- [ ] Move TCB + Cake parsers thành `tcb.py`, `cake.py`
- [ ] Registry pattern — add bank = thêm 1 file + register, không touch dispatcher
- [ ] Test fixtures `tests/fixtures/email/{bank}/*.eml`
- [ ] (Postmark integration thực tế làm Phase 5)

### Phase 2.5 — Smoke test + cutover (2-3 ngày)

- [ ] Deploy SaaS app lên Railway staging subdomain
- [ ] Founder signup làm beta user #1
- [ ] Verify 3-path onboarding skeleton (path A wired, B+C placeholder)
- [ ] 1 SePay tx → categorize → DB store → `/status` show đúng
- [ ] 1 email từ Apps Script (tạm giữ) → parser → DB store → `/status` show
- [ ] Performance: 10 mock user concurrent, < 2s reply
- [ ] Promote staging → production domain

**Tổng effort estimate: 20-28 ngày dev** (BRD ước Phase 1-2 = 4 tuần = 20 ngày work) → realistic, có 0-8 ngày buffer.

---

## 6. Risks & Mitigation

| # | Risk | Mức độ | Mitigation |
|---|------|--------|-----------|
| 1 | Founder personal bot down trong refactor | Trung bình | Refactor trên branch riêng, deploy SaaS ở subdomain khác. Personal bot env vars tách biệt. |
| 2 | DB migration sai → data corruption | Trung bình | No data migration (section 4.2), founder signup lại. |
| 3 | Estimate sai > 30% | Cao | Buffer 1 tuần đã include trong BRD timeline tuần 16. Phase 2.1 risky nhất (state machine refactor). |
| 4 | Multi-tenant query thiếu `WHERE user_id` | **Cao** | (a) DB-level: dùng RLS (Row Level Security) làm safety net. (b) Code review checklist: every SQL phải scope. (c) Integration test: 2 user, assert no cross-leak. |
| 5 | Bot rate limit hit ở beta (10 user) | Thấp | 10 user × ~10 msg/ngày = 100 msg/ngày, < 1 msg/s avg — không gần limit. Bot pool defer. |
| 6 | APScheduler in-process — single instance | Trung bình | OK ở MVP. Khi multi-instance, migrate sang Postgres-based job queue (xem PRD 5.4.2 outbound queue). |
| 7 | Postmark cutover chưa sẵn sàng cuối Phase 2 | Trung bình | Phase 2.4 chỉ refactor parser, KHÔNG migrate ingest. Apps Script tạm giữ tới Phase 5 có Postmark. |

---

## 7. Definition of Done

- [ ] Toàn bộ acceptance criteria section 3 pass
- [ ] Code review qua 1 pair (founder + AI pair acceptable)
- [ ] Test coverage cho `db.py`, `users.py`, mọi handler ≥70%
- [ ] Documentation: README.md update với new env vars, new endpoints, migration runbook
- [ ] Founder dùng được SaaS bot làm beta user #1 ≥3 ngày không bug critical
- [ ] PRD section 4 Data Model + section 5.4 Scalability không có inconsistency với code thực tế

---

## 8. References

- [PRD v1.6.0 §1.4 Bot ownership](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md)
- [PRD v1.6.0 §5.4 Scalability](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md)
- [BRD v2.9.0 §1.6 Bot ownership decision](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md)
- [BRD v2.9.0 §8 Timeline Phase 1-2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md)
- [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-messenger-channel.md)
- Current code: `main.py`, `config.py`, `telegram_api.py`, `sheets.py`, `handlers/*`

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial spec — refactor work cho Phase 1-2 BRD timeline. Diff current → target, sub-tasks với effort estimate (20-28 ngày), acceptance criteria multi-tenant isolation. |
| v1.1.0 | 2026-05-05 | **PLATFORM_TOKEN routing AC added (sync feature-spec-payment-bank-transfer.md):** §3.3 Bot ownership renamed thành "Bot ownership + Webhook routing", thêm 4 AC mới: (1) routing checks PLATFORM_TOKEN BEFORE user token lookup, (2) PLATFORM_TOKEN không collide với users.webhook_token (enforce qua reserved prefix hoặc INSERT guard), (3) test: `/hook/{PLATFORM_TOKEN}` không INSERT vào `transactions`, (4) test: `/hook/{user_token}` không INSERT vào `payment_matches`. Sync version refs lên BRD v2.8.0 / PRD v1.5.0. |
| v1.2.0 | 2026-05-06 | **Foundation interfaces from implementation plan v1.1.0:** (1) **Messenger interface abstraction**: §2.2 + §3.3 + §Phase 1.2 yêu cầu mọi outbound message đi qua `services/messenger.py` `send(user_id, payload)`. Handlers KHÔNG call telegram_api directly. Foundation cho C9 outbound queue swap (no handler refactor sau). (2) **Admin auth framework Phase 1-2**: env `ADMIN_TELEGRAM_IDS` (comma-separated), `@admin_only` decorator, auto-log to `admin_audit_log` table. (3) §4.1 schema thêm `admin_audit_log` table — required từ Phase 1 vì admin actions affect schema/permissions. (4) §Phase 1.2 expanded 3-4 ngày → 4-5 ngày để cover messenger + admin framework. |
| v1.3.0 | 2026-05-07 | **Multi-channel foundation (sync feature-spec-messenger-channel v1.1.1 + BRD v2.9.0):** (1) **§2.1 architecture diff updated**: Bot model 1 channel → 2 channel (Telegram + Messenger). Identity từ `users.telegram_id UNIQUE` → `users.channel_type + channel_user_id UNIQUE pair`. Webhook routing 3 endpoint → 4 endpoint (thêm `/webhook/messenger` GET+POST). Outbound row mới: `services/channels/{telegram,messenger}.py` adapter pattern. (2) **§2.2 code rewrite list expanded**: `telegram_api.py` không "wrap internal of services/messenger.py" mà "migrate logic vào `services/channels/telegram.py`" — file cũ delete sau migration. Thêm 3 file NEW: `services/channels/base.py` (BaseSender ABC), `services/channels/telegram.py`, `services/channels/messenger.py` (Phase 6 Tuần 10-11). (3) Header refs bumped BRD v2.8.0 → v2.9.0, PRD v1.5.0 → v1.6.0. (4) Phase liên quan mở rộng từ "Phase 1-2 + ảnh hưởng Phase 3-5" → "Phase 1-2 + ảnh hưởng Phase 3-6 (Messenger build Tuần 10-11 reuse foundation này)". |
