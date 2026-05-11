# Tiền Về Nơi Đâu — Product Requirements Document (PRD)

> **Version:** v1.7.1
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-10
> **Trạng thái:** Draft
> **Tham chiếu:** [brd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) v3.1.0 · [tdd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) v1.8.1 · [feature-spec-messenger-channel](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) v1.1.1 · [impl plan VietQR+email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) v1.0.0
>
> **🌐 SCOPE NOTE:** PRD này là **canonical product spec cho 🇻🇳 thị trường Việt Nam** (Tiền Về Nơi Đâu — tienvenoidau.com). Transaction capture (SePay + VN bank email parsing), 3 personas (Minh/Linh/Hùng+), pricing (79k/199k VND) đều VN-specific. **Global market** có PRD riêng — [prd-en.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-en.md) (My Money Went — mymoneywent.com). Per [ADR-0001](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md), shared foundation specs (DB schema, messenger interface, auth) apply cho cả 2 markets.
>
> **Change v1.7.1 vs v1.7.0:** Renamed `prd.md` → `prd-vi.md`. Thêm SCOPE NOTE. Update header refs (BRD v2.9.0 → brd-vi.md v3.1.0, tdd.md → tdd-vi.md v1.8.1). Title "MyMoneyWent" → "Tiền Về Nơi Đâu" (VN branding).

---

## 1. Tổng quan sản phẩm

### 1.1. Mô tả
MyMoneyWent (Tiền Về Nơi Đâu) là **multi-channel SaaS bot** (Telegram + Discord + Messenger) tự động theo dõi tài chính cá nhân và shop nhỏ. **Telegram** (`@FinTrackBot`) là channel primary launch tại MVP. **Facebook Messenger** (Facebook Page) — code + foundation ship cùng MVP nhưng public access **gated bởi feature flag `ENABLE_MESSENGER_CHANNEL`**, chỉ flip ON sau khi Meta App Review approve (3-14 ngày, parallel với dev). User chọn 1 trong 2 channel lúc onboarding khi cả 2 đã live (single-channel per user). Bot kết nối ngân hàng qua **3 entry path** (SePay quick connect, SePay wizard, Email forwarding), nhận giao dịch real-time, hỏi user phân loại qua inline buttons (Telegram) hoặc quick replies (Messenger), và tổng hợp báo cáo tự động. Cấu trúc 3-tier pricing (Free / Pro $4 / Business $9).

### 1.2. Nguyên tắc thiết kế

| # | Nguyên tắc | Mô tả |
|---|-----------|-------|
| 1 | **Zero-config** | User không cần biết kỹ thuật. 2-5 phút (SePay quick) / 10-15 phút (SePay wizard) / 5-10 phút (email forwarding) |
| 2 | **Conversational-first** | Mọi interaction qua Telegram chat. Không form, không web UI |
| 3 | **Track-first, budget-optional** | Tracking là default. Budget là opt-in cho ai muốn |
| 4 | **1-tap categorization** | Phân loại = bấm 1 nút. Không nhập text trừ khi tạo category mới |
| 5 | **Data isolation** | Multi-tenant: mỗi user là universe riêng, zero cross-contamination |
| 6 | **3-path onboarding** | Cover 100% Hùng+ TAM: SePay quick, SePay wizard, Email forwarding |

### 1.3. Tech stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ · FastAPI · Uvicorn |
| Database | PostgreSQL (Railway managed) — multi-tenant |
| Messaging | Telegram Bot API — **1 shared bot platform-owned**, per-user routing via `telegram_id` (xem 1.4) |
| Bank integration | SePay webhook (path A+B) · Postmark Inbound email (path C) |
| Hosting | Railway Hobby plan (app + DB) |
| Scheduling | APScheduler (in-process, per-user timezone-aware) |
| Payment | **Bank transfer + auto-detect** qua SePay primary + Email backup (xem [feature-spec-payment-bank-transfer.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md)) · PayPal/USDT defer Phase 2 |
| Backup | Backblaze B2 daily với SSE-B2 server-side encryption + `pg_dumpall --globals-only` cho roles |
| Admin tools | Telegram commands restricted bằng `ADMIN_TELEGRAM_IDS` (comma-separated, multi-admin), rate limit `ADMIN_RATE_LIMIT_PER_MIN=30` default. `/admin_help` hybrid auto-generated từ `@admin_only` registry. Detail: [feature-spec-admin-tools v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-admin-tools.md) |
| Observability | Sentry + Railway metrics + UptimeRobot. Founder daily dashboard `/admin_stats`, cost dashboard `/admin_cost`, per-user troubleshooter `/admin_user`. Error budget 0.1% policy. Detail: [observability-plan v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md) |
| Disaster recovery | 8 scenarios documented + quarterly drill. RTO 2-4h, RPO 24h. `BOT_TOKEN_BACKUP` ready, `@FinTrackUpdates` channel for out-of-band notification. Detail: [DR runbook v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md) |

### 1.4. Bot ownership model — Multi-channel (Telegram + Discord + Messenger)

**3 channel implemented in MVP (Telegram + Discord co-primary, Messenger feature-flagged); Telegram public launch primary; Messenger public access feature-flagged after Meta App Review.** Single-channel per user (khi cả 2 đã live, user chọn 1 lúc onboarding):

1. **Telegram channel:** 1 shared bot duy nhất do platform sở hữu (`@FinTrackBot`). `BOT_TOKEN` là 1 env var Railway. **Public launch theo BRD timeline 16 tuần — không phụ thuộc bất kỳ external approval nào.**
2. **Messenger channel:** 1 Facebook Page do platform sở hữu (`m.me/FinTrackPage`). `FB_PAGE_ACCESS_TOKEN` + `FB_APP_SECRET` là 2 env var Railway. **Code + foundation ship Phase 6, public access gated bởi `ENABLE_MESSENGER_CHANNEL` flag — flip ON sau khi Meta App Review approve `pages_messaging` + `pages_messaging_subscriptions`.** Nếu review pending/reject tại MVP launch → Telegram-only operation, Messenger flip ON post-launch.

User KHÔNG cần tạo bot/Page riêng, không cần biết tokens, không cần lookup channel ID của mình.

**Flow đăng ký Telegram:**

1. User search `@FinTrackBot` trên Telegram → bấm "Start"
2. Bot nhận `update.message.from.id` = user's `telegram_id`
3. Backend: `INSERT INTO users (channel_type='telegram', channel_user_id=<telegram_id>, ...) ON CONFLICT DO NOTHING`
4. Bot reply về đúng `chat_id` của user đó (lấy từ `update.message.chat.id`, lưu trong `users.chat_id`)

**Flow đăng ký Messenger:**

1. User truy cập `m.me/FinTrackPage` → bấm "Get Started" (Meta-managed button)
2. Meta gửi postback `{"payload": "GET_STARTED"}` với `sender.id` = user's PSID (Page-Scoped User ID)
3. Backend: `INSERT INTO users (channel_type='messenger', channel_user_id=<psid>, ...) ON CONFLICT DO NOTHING`
4. Bot reply qua Send API với `recipient.id=<psid>`, lưu `last_user_message_at` cho 24h window check

**Rationale:** Multi-tenant SaaS UX phải chuẩn "thêm bạn → dùng ngay". Bắt user tự tạo bot qua @BotFather = mất 30-60 phút setup, defeat 2-15 phút onboarding promise của 3-path flow. Multi-channel giảm risk Telegram block ở VN (BRD §risk #2) + tăng TAM (user prefer Messenger thay vì Telegram).

**Channel-specific UX:** Telegram dùng slash commands (`/start`, `/status`) + inline keyboard 2D grid. Messenger dùng persistent menu (5 item) + quick replies flat list (max 13/message). Feature parity 100%, UX divergent intentional theo native pattern. Detail: [feature-spec-messenger-channel §7.5 UX parity matrix](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md).

**Operational implications:**
- `BOT_TOKEN` + `FB_PAGE_ACCESS_TOKEN` + `FB_APP_SECRET` chỉ tồn tại trong Railway env vars, do platform owner quản lý + rotate khi cần.
- `chat_id` (Telegram) hoặc `channel_user_id=<psid>` (Messenger) luôn lookup từ DB qua `users` table, **KHÔNG hardcode** trong code/env.
- Outbound message MUST go through `services/messenger.py` → `services/channels/{telegram,messenger}.py` adapter. Handlers KHÔNG call channel API trực tiếp.
- Single point of failure mỗi channel: Telegram suspend → toàn Telegram user offline; FB Page suspend → toàn Messenger user offline. Mitigation: `BOT_TOKEN_BACKUP` cho Telegram emergency switchover < 5 phút; FB Page recovery via Meta admin process. Cross-channel migration scripted nếu 1 channel die hoàn toàn (move toàn user sang channel kia).

**Acceptance Criteria liên quan (cross-ref F01, F08):**
- [ ] `BOT_TOKEN`, `FB_PAGE_ACCESS_TOKEN`, `FB_APP_SECRET` chỉ tồn tại trong Railway env vars, không commit code
- [ ] Mọi outbound channel call phải resolve qua `users.channel_type` + `users.channel_user_id`, không có hardcoded fallback
- [ ] `UNIQUE (channel_type, channel_user_id)` constraint — 1 channel account = 1 user row
- [ ] `users.last_user_message_at` cập nhật mỗi inbound message (Messenger 24h window check)
- [ ] Bot suspended scenario có runbook cho cả Telegram (rotate `BOT_TOKEN`) + Messenger (Meta admin process)
- [ ] Channel adapter pattern grep AC: handler/service files có 0 hit `await tg.send_*` hoặc `httpx.*graph.facebook.com` ngoài `services/channels/`

---

## 2. User Flows

> **Multi-channel note:** Tất cả flow dưới đây mô tả Telegram (channel "default" trong examples). Messenger flow **identical** về mặt logic — chỉ khác UX rendering: persistent menu thay slash commands, quick replies thay inline keyboard, image attachment thay sendPhoto. Detail diff: [feature-spec-messenger-channel §7.5 UX parity matrix](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md). Entry point Messenger: user truy cập `m.me/FinTrackPage` → tap "Get Started" thay vì gõ `/start`.

> **UI strategy decision:** Onboarding chat-only — KHÔNG có web form/wizard cho user nhập setup info. Lý do + trade-off + triggers revisit: [decision-onboarding-ui-strategy.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md). Pre-launch web chỉ là landing page tĩnh + privacy/terms (~3 ngày dev), KHÔNG thay thế chat onboarding.

### 2.1. Onboarding Flow — Path A: SePay Quick Connect (2-5 phút)

```
User tìm @FinTrackBot trên Telegram
    │
    ▼
User gửi /start
    ├── Bot tạo account (users table, keyed by telegram_id)
    ├── Bot tạo default categories (3 tracking categories suggested)
    ├── Bot generate unique webhook_token (24-char URL-safe)
    ├── Bot assign 14-day Pro trial
    │
    ▼
Bot gửi welcome + chọn path:
    "👋 Chào bạn! Tôi sẽ giúp bạn theo dõi chi tiêu tự động.

     Bạn muốn kết nối bằng cách nào?"

    [🔗 Đã có SePay]  [📋 Chưa có SePay]  [📧 Dùng Email]
    │
    ├── User chọn "Đã có SePay"
    │   ├── Bot hiện webhook URL: https://api.tienvenoidau.com/hook/{token}
    │   ├── Hướng dẫn: "Vào sepay.vn → Webhook → dán URL"
    │   └── Done! Chờ giao dịch đầu tiên
    │
    ▼
Giao dịch đầu tiên đến → category picker → ✅ Setup hoàn tất
```

### 2.2. Onboarding Flow — Path B: SePay Setup Wizard (10-15 phút)

```
User chọn "📋 Chưa có SePay"
    │
    ▼
Bot gửi step-by-step wizard:
    Step 1: "Truy cập sepay.vn → Đăng ký tài khoản miễn phí"
            [✅ Đã đăng ký] [❓ Cần hỗ trợ]
    │
    Step 2: "Kết nối tài khoản ngân hàng trong SePay"
            [✅ Đã kết nối] [❓ Cần hỗ trợ]
    │
    Step 3: "Vào phần Webhook → dán URL này: https://api.tienvenoidau.com/hook/{token}"
            [✅ Đã dán] [❓ Cần hỗ trợ]
    │
    ▼
Bot gửi: "🎉 Setup hoàn tất! Chờ giao dịch đầu tiên."
```

### 2.3. Onboarding Flow — Path C: Email Forwarding (5-10 phút)

```
User chọn "📧 Dùng Email"
    │
    ▼
Bot gửi:
    "📧 Setup Email Forwarding

     Bot sẽ cấp cho bạn 1 email riêng:
     u{user_id}@in.tienvenoidau.com

     Bạn chỉ cần setup forwarding rule trong Gmail/Outlook:
     → Forward email từ ngân hàng tới địa chỉ trên."

    [📱 Tôi dùng Gmail] [💻 Tôi dùng Outlook] [❓ Khác]
    │
    ├── Gmail: hướng dẫn Settings → Forwarding → Add address
    ├── Outlook: hướng dẫn Settings → Rules → Forward
    │
    ▼
Bot gửi: "✅ Đã tạo email u{id}@in.tienvenoidau.com
          Hãy setup forwarding rule, rồi thử gửi 1 email test!"
    │
    ▼
Email đầu tiên đến → parse → category picker → ✅ Setup hoàn tất
```

### 2.4. Transaction Flow (core loop)

```
SePay webhook → POST /hook/{user_token}
  hoặc
Email → Postmark inbound → POST /inbound/{user_token}
    │
    ├── Validate user_token → lookup user
    ├── Check tier limits (Free: 45 tx/tháng)
    ├── Parse payload → canonical transaction schema
    ├── Dedup check (ref_code unique + fuzzy cross-source)
    ├── Stale check (SePay: 10min, Email: 24h)
    ├── INSERT vào transactions table
    │
    ▼
Bot gửi category picker tới user's telegram_id:
    "💸 -120,000đ
     Pho 24 Nguyen Hue

     Khoản này thuộc mục nào? 🤔"

    [🛒 Daily Spending] [🏦 Saving]
    [💼 Work]           [👗 Clothes]
    [📱 Subscription]   [➕ New category]
    [⏭️ Bỏ qua]  ← chỉ hiện cho incoming tx
    │
    ├── User bấm category → finalize transaction
    │   ├── Tracking mode: "📊 Daily Spending: tổng tháng này 1,500,000đ"
    │   ├── Budget mode: "██████░░░░ 60% · 600k / 1tr · còn 400k"
    │   └── Kèm [🔄 Wrong category?]
    │
    ├── User bấm "➕ New category" → tạo inline
    └── User bấm "⏭️ Bỏ qua" → uncategorized
```

### 2.5. Commands

| Command | Mô tả | Tier |
|---------|-------|------|
| `/start` | Onboarding — tạo account + 3-path setup | All |
| `/status` | Tổng quan tháng: categories, spent/allocated | All |
| `/today` | Chi tiêu hôm nay vs daily cap | All |
| `/manage` | Quản lý categories: thêm/sửa/xóa/rename | All |
| `/allocate` | (Optional) đặt budget cho categories | All |
| `/weekly` | Báo cáo tuần (7 ngày gần nhất) | Pro+ |
| `/report` | Báo cáo tháng đầy đủ | Pro+ |
| `/settings` | Account settings: webhook, timezone, plan | All |
| `/export` | Xuất CSV | Pro+ |
| `/help` | Hướng dẫn sử dụng | All |

---

## 3. Feature Specifications

### 3.1. F01 — 3-Path Onboarding

**Mô tả:** User gửi /start → chọn 1 trong 3 path → bot guide step-by-step → done.

**Acceptance Criteria:**
- [ ] `/start` tạo user row trong `users` table (PostgreSQL, keyed by telegram_id)
- [ ] Generate `webhook_token` (24-char URL-safe random)
- [ ] Generate `inbound_email` = `u{user_id}@in.tienvenoidau.com`
- [ ] Tự tạo 3 default categories (tracking mode) — user có thể add/customize/delete
- [ ] Assign 14-day Pro trial (trial_ends_at = now + 14d)
- [ ] Welcome message + 3 path selector buttons
- [ ] Path A: hiện webhook URL copyable
- [ ] Path B: step-by-step wizard (3 steps, mỗi step có ✅/❓)
- [ ] Path C: hiện inbound email + guide forwarding rule (Gmail/Outlook)
- [ ] `/start` idempotent — gọi nhiều lần không tạo duplicate
- [ ] `/start` khi đã có account → hiện status + settings

**Default Categories (auto-create on signup):**

| id | name | daily_cap |
|----|------|-----------|
| `daily_spending` | 🛒 Daily Spending | 100,000đ |
| `saving` | 🏦 Saving | null |
| `subscription` | 📱 Subscription | null |

> **Note:** Free tier max 5 categories total — user có thể add 2 custom thêm hoặc rename/delete defaults. Pro: 20. Business: unlimited.

---

### 3.2. F02 — Transaction Capture (SePay + Email)

**Mô tả:** Nhận giao dịch từ SePay webhook HOẶC email parser, normalize thành canonical schema, dedup, lưu DB, gửi category picker.

**Endpoints:**
- SePay: `POST /hook/{user_token}`
- Email: `POST /inbound/{user_token}` (Postmark inbound webhook)

**Canonical Transaction Schema:**

| Field | Type | Source: SePay | Source: Email |
|-------|------|--------------|---------------|
| amount | float | transferAmount | parsed from body |
| direction | enum(in/out) | transferType | parsed from body |
| description | string | description | parsed from body |
| ref_code | string | referenceCode | hash(amount\|desc\|date) |
| tx_date | datetime | transactionDate | parsed from body |
| source | string | "sepay" | "email_{bank}" |

**Acceptance Criteria:**
- [ ] SePay: parse payload (transferAmount, transferType, description, referenceCode)
- [ ] SePay: field name fallbacks (transferAmount → transfer_amount → amount)
- [ ] Email: parse 6 MVP banks (TCB, Cake, ACB, STB/Sacombank, BIDV, MB); VCB deferred to Phase 2 pending email-notification verification
- [ ] Email: fallback "unparsed" notification nếu bank chưa support
- [ ] Dedup: UNIQUE(user_id, ref_code) — INSERT ON CONFLICT DO NOTHING
- [ ] Fuzzy dedup cross-source: same amount + type within 3 minutes = skip
- [ ] Stale protection: SePay >10min old = skip, Email >24h old = skip
- [ ] Free tier: reject nếu user đã 45 tx/tháng + gửi upgrade prompt (áp dụng cho cả SePay + email source)
- [ ] Email source: Free 1 / Pro 3 / Business unlimited — enforce ở `bank_connections` table
- [ ] Invalid token → return 200 OK, log, không crash
- [ ] Return 200 immediately, process async

**Email Parser Requirements:**

| Bank | Sender domains | Parser status |
|------|---------------|---------------|
| TCB (Techcombank) | techcombank.com.vn | ✅ Existing |
| Cake (VPBank) | cake.vn | ✅ Existing |
| ACB | acb.com.vn | 🔲 MVP |
| STB (Sacombank) | sacombank.com.vn | 🔲 MVP |
| BIDV | bidv.com.vn | 🔲 MVP |
| MB Bank | mbbank.com.vn | 🔲 MVP |

**Tier 2 — Phase 2 (top banks, needs email sample collection + verification):**

| Bank | Sender domains | Parser status |
|------|---------------|---------------|
| VCB (Vietcombank) | vietcombank.com.vn | 🔲 Phase 2 |
| VietinBank | vietinbank.vn | 🔲 Phase 2 |
| TPBank | tpb.vn | 🔲 Phase 2 |
| VPBank | vpbank.com.vn | 🔲 Phase 2 |
| HDBank | hdbank.com.vn | 🔲 Phase 2 |
| Agribank | agribank.com.vn | 🔲 Phase 2 |

**Tier 3 — On-demand (add based on user requests):**
SHB, MSB (Maritime), SeABank, VIB, Eximbank, OCB, LienVietPostBank, Nam A Bank, KienlongBank, TNEX, Timo

---

### 3.3. F03 — Transaction Categorization

**Mô tả:** User phân loại giao dịch qua inline buttons. Hỗ trợ sub-categories và tạo category mới inline.

**Acceptance Criteria:**
- [ ] Inline keyboard: 2 buttons per row, tất cả active categories
- [ ] "➕ New category" ở cuối (tạo inline, không cần /manage)
- [ ] "⏭️ Bỏ qua" cho incoming transactions
- [ ] Sub-category picker hiện sau parent (nếu có)
- [ ] Custom sub-category: user nhập text → auto-save
- [ ] "🔄 Wrong category?" trên confirmation → re-pick
- [ ] State machine: `await_parent` → `await_sub` → `done`
- [ ] State persist qua DB (bot_state table, per user)
- [ ] Free tier: max 5 categories total (3 default auto-create + user add/customize tới max 5). Pro: 20. Business: unlimited
- [ ] Email source limits enforced: Free 1 / Pro 3 / Business unlimited

---

### 3.4. F04 — Category Management (/manage)

**Mô tả:** CRUD categories và sub-categories.

**Flows:**
```
/manage
    ├── Hiển thị danh sách categories + tổng mỗi category
    ├── Tap category → actions:
    │   ├── ✏️ Rename
    │   ├── 💰 Edit Budget (amount=0 → tracking, >0 → budgeted)
    │   ├── 🗑️ Delete (soft delete: active=FALSE)
    │   └── Sub-categories:
    │       ├── Rename sub
    │       └── Delete sub
    └── ➕ Add Category
        ├── Nhập tên
        └── Nhập budget (0 = tracking-only)
```

**Acceptance Criteria:**
- [ ] List hiển thị: category name + "🏷️ tracking" hoặc budget amount
- [ ] Rename: update tên, giữ slug không đổi
- [ ] Delete: soft delete (active=FALSE), transactions cũ giữ nguyên
- [ ] Add: tạo category mới
- [ ] Budget = 0 → tracking mode. Budget > 0 → budgeted mode
- [ ] Tier limits enforced: Free 5, Pro 20, Business unlimited

---

### 3.5. F05 — Reports

#### /status — Monthly Overview
```
📊 Tracking — 2026-05

BUDGETED:
✅ Daily Spending  ████████░░ 80%  800k / 1tr · còn 200k
🟡 Saving          ██████░░░░ 60%  600k / 1tr · còn 400k

TRACKING:
📊 Clothes         đã tiêu 350k tháng này
📊 Subscription    đã tiêu 120k tháng này

INCOME:
💚 Saving          nhận 5,000k tháng này

─────
Tổng budget: 1.4tr / 2tr (70%)
Tổng tracking: 470k
Tổng income: 5,000k
```

#### /today — Daily Overview
```
🍜 Today — May 05

Hôm nay: 180,000đ (3 tx)
███████░░░ 72% of 250k cap
Còn 70,000đ hôm nay

Còn 26 ngày trong tháng
Monthly còn 400,000đ
```

#### Daily Recap (tự động, 23h user timezone)
```
🌙 End of day — May 05

Daily spending: 180,000đ (72% of limit)
Còn 70,000đ chưa dùng.

Muốn note lại lý do? Reply để bot ghi nhận.
```

**Acceptance Criteria:**
- [ ] `/status` tách BUDGETED vs TRACKING vs INCOME sections
- [ ] `/today` hiển thị progress bar nếu có daily_cap
- [ ] Daily recap fire lúc 23:00 **theo timezone của user**
- [ ] Daily recap chỉ fire nếu có ≥1 tx hôm đó
- [ ] `/weekly` (Pro+): 7-day breakdown
- [ ] `/report` (Pro+): full monthly report
- [ ] CSV export (Pro+): `/export` → file gửi qua Telegram

---

### 3.6. F06 — Pricing, Tier Limits & Trial

**Mô tả:** Enforce tier-based feature gating + **4-tier pricing** với annual discount.

**Pricing (post Family launch 2026-Q3+):**

| Plan | VN Monthly | VN Annual (15% off, exact) | Global Monthly |
|------|-----------|---------------------------|----------------|
| Free | 0 | 0 | $0 |
| Pro | **99k VND** | **1.010k/năm** | $4/mo |
| **Family** 🆕 | **169k VND** | **1.724k/năm** | TBD Phase 2 |
| Business | **299k VND** | **3.050k/năm** | $9/mo |

> **Pricing bump:** Pro 79k→99k, Business 199k→299k ship cùng Family launch. Grandfather 6 tháng giá cũ cho existing subscriber. Xem BRD §5.1 + [feature-family-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/drafts/feature-family-plan.md).
>
> **Family annual exact = 1.724k** (169k × 12 × 0.85). Marketing rounding nếu có phải document explicit.

**Tier Limits:**

| Limit | Free | Pro | Family (per member) | Business |
|-------|------|-----|---------------------|----------|
| Transactions/tháng | 45 | Unlimited | Unlimited | Unlimited |
| Bank accounts | 1 | 3 | 3 | 5 |
| Transaction history | 30 ngày | Unlimited | Unlimited | Unlimited |
| Categories | 5 | 20 | 20 | Unlimited |
| Email sources | 1 | 3 | 3 | Unlimited |
| Weekly/Monthly report | ❌ | ✅ | ✅ | ✅ |
| CSV export | ❌ | ✅ | ✅ | ✅ |
| **Family seats** | — | — | **2 parent + 4 child (flat)** | — |
| **Multi-member dashboard** | — | — | ✅ | — |
| **Budget limits per member/category** | — | — | ✅ | — |
| **Real-time budget alerts** | — | — | ✅ | — |

> **Lưu ý SePay:** User tự trả gói SePay (mọi tier).

> **Family Plan scope:** Target phụ huynh quản lý chi tiêu con **13-17 tuổi**. Co-parent ngang quyền owner trừ billing. Consent disclosure mandatory. Permission: View + Set Budget + Alerts (KHÔNG approve-before-spend). Spec đầy đủ: [feature-family-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/drafts/feature-family-plan.md).

**Trial Logic:**
- [ ] New user → 14-day Pro trial, auto-assigned
- [ ] Day 12: reminder
- [ ] Day 14: auto-downgrade Free, data preserved
- [ ] Pro user upgrade Family → trial reset 14 ngày (1 lần, track `users.family_trial_used_at`)
- [ ] Upgrade triggers: max 1/tuần/user
- [ ] Annual plan: hiển thị "tiết kiệm 15% khi trả năm"

**Cross-feature contracts (Family-driven):**
- **F02 worker** MUST call `can_ingest_transaction(user_id, fs)` entitlement service trước insert tx (FAM §4.5).
- **F09 scheduled jobs** thêm `close_stale_memberships` daily cron (FAM §4.6).
- **F08 funding sources**: KHÔNG thêm column nào. Family visibility qua membership join.
- **F01 onboarding** extend với Path D (Family invite-accept flow + disclosure).

**Payment flow:** Detail spec ở [feature-spec-payment-bank-transfer v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md) + [implementation-plan-payment-vietqr-email v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md). Tóm tắt:
- User `/upgrade` → bot tạo `pending_payment` với ref `PAY-{user_id}-{plan}-{period}-{nonce4}`
- Bot generate **2 VietQR code** (qua vietqr.io public API) cho cả primary VCB + secondary TCB, gửi như image attachment + ref code standalone message (long-press copy trên Messenger)
- User scan QR bằng app banking → app pre-fill account + amount + ref → confirm
- Tiền vào 1 trong 2 platform bank account:
    - **VCB primary** (SePay-linked): SePay webhook → auto-detect ≤ 60s p95
    - **TCB secondary** (email-only): TCB email founder → forwarding rule → Postmark `/inbound/{PLATFORM_TOKEN}` → email parser → auto-detect ≤ 5min p95
- 4-layer fuzzy match (exact ref → typo tolerance ≤2 → amount unique → manual review)
- Cross-source dedup qua `pending_payments.status` state machine (SePay + email cùng fire → chỉ 1 upgrade)
- Recurring monthly: reminder 3 ngày trước expiry + grace 7 ngày sau expiry
- Recurring annual: reminder 14+3+1 ngày trước expiry
- Messenger user: outbound proactive subscription notification (match success, expiry, reminder) tag `ACCOUNT_UPDATE` cho Meta 24h window compliance

---

### 3.7. F07 — Settings (/settings)

| Setting | Mô tả | Default |
|---------|-------|---------|
| Webhook URL | Hiển thị + regenerate | Auto-generated |
| Inbound Email | Hiển thị `u{id}@in.tienvenoidau.com` | Auto-generated |
| Timezone | Chọn timezone cho reports/recap | Asia/Ho_Chi_Minh |
| Daily recap | Bật/tắt | Bật |
| Plan info | Plan hiện tại + trial status + upgrade | Free (or trial) |

**Acceptance Criteria:**
- [ ] Regenerate webhook URL → invalidate URL cũ ngay lập tức
- [ ] Timezone change → recalculate scheduled jobs
- [ ] Toggle daily recap → update scheduled_jobs

---

### 3.8. F08 — Multi-User Data Isolation

**Acceptance Criteria:**
- [ ] Mọi DB query scope `WHERE user_id = $1`
- [ ] Webhook chỉ write vào đúng user (validated by token)
- [ ] Bot state isolated per user
- [ ] Scheduled jobs isolated per user
- [ ] Error messages không leak user info

---

### 3.9. F09 — Scheduled Jobs (per-user)

| Job | Schedule | Condition |
|-----|----------|-----------|
| `daily_recap` | 23:00 user timezone **±5 phút jitter** (deterministic theo user_id) | enabled=TRUE, có ≥1 tx |
| `trial_reminder` | Day 12 of trial | trial active |
| `trial_downgrade` | Day 14 of trial | trial active |
| `weekly` | Sunday 14:00 ±5 phút jitter | Pro+ only |
| `monthly_report` | Last day of month 14:00 ±5 phút jitter | Pro+ only |
| `monthly_allocation` | 1st of month 08:00 ±5 phút jitter | All |

**Acceptance Criteria:**
- [ ] APScheduler polls `scheduled_jobs` table per user
- [ ] Timezone-aware: `next_run_utc` tính từ user timezone
- [ ] Job failure không block jobs khác
- [ ] New users auto-get `daily_recap` + `monthly_allocation`
- [ ] **Jitter ±5 phút deterministic**: `offset_min = hash(user_id) % 11 - 5` để spread 23:00 fire window thành 22:55-23:05 — tránh burst > 30 msg/s lên Telegram khi ≥500 user fire cùng lúc (xem 5.4.2)

---

## 4. Data Model

### 4.1. Entity Relationship

```
users (1) ──── (N) transactions
  │                    │
  │                    └── category_id FK → categories.id
  │
  ├──── (N) categories
  │         │
  │         └──── (N) sub_categories
  │
  ├──── (N) bank_connections (SePay + email sources)
  │
  ├──── (1) bot_state
  │
  ├──── (N) scheduled_jobs
  │
  ├──── (N) funding_sources                    [F08]
  │
  ├──── (1) family_accounts (as owner)         [FAM]
  │         ├──── (N) family_members (user_id)
  │         ├──── (N) family_budgets
  │         └──── (N) family_invites
  │
  └──── (N) family_members (as parent/child member)
```

### 4.2. Key Tables (xem chi tiết trong TDD)

| Table | Mô tả |
|-------|-------|
| `users` | Account, plan, trial, timezone, tokens |
| `transactions` | Canonical tx data, category, confirmed |
| `categories` | Per-user categories, budget, active flag |
| `sub_categories` | Nested under categories |
| `bank_connections` | SePay webhook + email sources per user |
| `bot_state` | Conversation state machine per user (`step` + `payload`) |
| `scheduled_jobs` | Per-user scheduled tasks |
| `pending_payments` | User upgrade requests pending transfer (24h TTL) |
| `payment_matches` | Confirmed transfer ↔ pending matches with refund tracking |
| `unmatched_payments` | Admin review queue cho unmatched transfers |
| `admin_audit_log` | Append-only log mọi admin command execution (auth foundation) |
| `analytics_events` | Product/ops events cho funnel + observability |

---

## 5. Non-Functional Requirements

### 5.1. Performance

| Metric | Target |
|--------|--------|
| Webhook response time | < 200ms (return 200, process async) |
| Bot reply latency | < 2s (webhook → user nhận message) |
| DB query time | < 50ms (simple queries) |
| Concurrent users | ≥100 simultaneous (target ở 0-500 user scale; ≥500 cần benchmark + có thể migrate Hetzner) |
| Email parse time | < 500ms per email |

### 5.2. Security

| Concern | Giải pháp |
|---------|----------|
| Webhook auth | Per-user token trong URL (24-char random) |
| Email auth | Per-user inbound address (unique prefix) |
| Data minimization | Không lưu số tài khoản, chỉ amount + description |
| User isolation | Mọi query scope by user_id |
| Token regeneration | User có thể regenerate webhook URL |
| Transport | HTTPS only (Railway auto SSL) |
| Secrets | ENV vars, không commit |
| PDPA compliance | Privacy policy, data retention, breach response |

### 5.3. Reliability

| Metric | Target |
|--------|--------|
| Uptime | ≥99% (Railway SLA) |
| Data durability | PostgreSQL WAL + daily B2 backup (incl. `pg_dumpall --globals-only`) + SSE-B2 encryption |
| Backup recovery | Tested: full restore vào staging. Quarterly drill (DR runbook §11) |
| Email parser accuracy | ≥85% per bank |
| Webhook retry | SePay + Postmark tự retry → dedup bảo vệ (cross-source dedup qua `pending_payments.status` state machine, payment spec §3) |
| **Error budget** | ≤0.1% error rate rolling 30-day window. Policy 3-tier (>50% remain → ship features / 0-50% → slow down / <0% → freeze). Detail: [observability §4b](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md) |
| **Disaster recovery** | RTO ≤2h (DB corruption), ≤4h (Railway outage), ≤5min (BOT_TOKEN compromise). 8 scenarios documented: [DR runbook](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md) |
| **Out-of-band notification** | `@FinTrackUpdates` Telegram channel (created pre-launch) for bot suspension scenarios |

### 5.4. Scalability

#### 5.4.1. Compute / DB scaling

| Stage | Strategy |
|-------|----------|
| 0-100 users | Railway single instance |
| 100-500 | Optimize queries, connection pooling, read replicas nếu cần |
| 500+ | Evaluate Hetzner Singapore migration, horizontal scaling app tier |

#### 5.4.2. Telegram Bot scaling — quan trọng cho shared bot model

Vì PRD section 1.4 dùng **1 shared bot** cho mọi user, có Telegram-imposed limit cần plan trước:

**Telegram Bot API rate limits (per bot):**
- ~30 messages/giây toàn bot (global)
- 1 message/giây tới cùng 1 chat
- 20 messages/phút tới group chat
- Per-method burst: ~30/s `sendMessage`, ~30/s `editMessage`

| Stage | Concurrency profile | Strategy |
|-------|---------------------|----------|
| 0-100 active users | Spike ~5-10 msg/s (cuối tháng nhiều `/status`) | 1 bot đủ — không cần làm gì |
| 100-500 active users | Spike ~15-25 msg/s | 1 bot vẫn đủ. Add **outbound queue** (Postgres-based hoặc Redis) + worker drain với rate limiter để tránh burst > 30/s |
| 500-2000 active users | Spike ~30-60 msg/s | **Bot pool 2-5 bots** — sticky route mỗi user tới 1 bot qua `users.bot_id`. Thêm cột `bots(bot_id, token_encrypted, active)` |
| 2000+ active users | Spike > 60 msg/s | Self-host **Local Bot API server** (telegram-bot-api binary trên Hetzner) → bypass Telegram-imposed rate limit, chỉ còn server limit |

**Acceptance Criteria (deferred — chưa cần MVP):**
- [ ] Outbound queue table `outbound_messages(id, user_id, payload, status, retries, next_attempt_at)` — implement khi >100 active users
- [ ] Rate limiter middleware: token bucket 25/s (buffer dưới 30 limit) — implement cùng outbound queue
- [ ] Bot pool migration plan: cột `users.bot_id` thêm khi reach 400 users, sticky bằng `user_id % len(active_bots)` để stable

**Risk:** spike trong giờ kết toán cuối ngày (23:00 daily recap fire đồng thời cho ≥500 users theo timezone) — nếu APScheduler không stagger, sẽ burst > 30/s ngay. **Mitigation MVP:** spread daily recap fire trong window 22:55-23:05 (jitter ±5 phút per user, deterministic theo `user_id`) thay vì fire chính xác 23:00.

#### 5.4.3. Postmark email scaling

| Stage | Volume estimate | Tier cost |
|-------|-----------------|-----------|
| 0-100 users | <10k email/mo | $10/mo (Postmark Inbound starter) |
| 100-500 users | 10-50k email/mo | $15-30/mo |
| 500+ users | 50k+/mo | Negotiate volume tier hoặc self-host Postfix + parser |

---

## 6. Analytics Events

| Event | Trigger | Properties |
|-------|---------|-----------|
| `user_signup_success` | /start tạo account mới | telegram_id, source |
| `user_onboard_path_selected` | Chọn path A/B/C | user_id, path |
| `user_onboard_completed` | First tx received | user_id, path, duration_min |
| `user_sepay_connected` | SePay tx đầu tiên | user_id, days_since_signup |
| `user_email_connected` | Email tx đầu tiên | user_id, bank |
| `tx_received` | Webhook nhận tx | user_id, source, tx_type, amount_tier |
| `tx_categorized` | User bấm category | user_id, category, latency_sec |
| `tx_skipped` | User bấm "Bỏ qua" | user_id |
| `tx_recategorized` | User bấm "Wrong?" | user_id |
| `tx_limit_hit` | Free user chạm 45 tx | user_id |
| `category_created` | Tạo category mới | user_id, method(inline/manage) |
| `command_used` | Slash command | user_id, command |
| `report_generated` | /status /today /weekly /report | user_id, report_type |
| `plan_trial_started` | New signup | user_id |
| `plan_trial_reminder` | Day 12 reminder | user_id |
| `plan_trial_expired` | Day 14 downgrade | user_id |
| `plan_upgrade_success` | Free → Pro/Business | user_id, tier, payment_method |
| `email_parse_success` | Email parsed OK | user_id, bank |
| `email_parse_fail` | Email parse failed | user_id, bank, reason |
| `payment_initiated` | User `/upgrade` chọn plan | user_id, plan, period |
| `payment_matched` | Matcher confirm transfer = pending | user_id, layer(1-4), confidence, source(sepay/email) |
| `payment_expired` | Pending hết 24h chưa transfer | user_id, plan, period |
| `payment_unmatched` | Incoming không match nào | source, amount, reason |
| `payment_refunded` | Admin refund | user_id, match_id, amount |
| `subscription_renewed` | Recurring transfer match | user_id, plan, period, cycles_total |
| `subscription_expired_grace` | Vào grace period 7 ngày | user_id, plan |
| `subscription_downgraded` | Sau grace auto-Free | user_id, prev_plan |
| `admin_command_executed` | Admin command success | admin_telegram_id, command, target_user_id |
| `admin_command_denied` | Non-admin attempt hoặc rate limit hit | admin_telegram_id, command, reason |
| `admin_manual_payment_resolved` | `/admin_resolve` link unmatched → pending | admin_telegram_id, unmatched_id, pending_id |

---

## 7. Phụ lục

### 7.1. Glossary

| Thuật ngữ | Định nghĩa |
|-----------|-----------|
| **SePay** | Dịch vụ kết nối ngân hàng VN, cung cấp webhook khi có giao dịch |
| **Postmark Inbound** | Email parsing service — nhận email forwarded, gửi webhook |
| **Category** | Nhóm phân loại chi tiêu (vd: Daily Spending, Saving) |
| **Sub-category** | Phân loại chi tiết hơn trong 1 category |
| **Tracking mode** | Category không có budget, chỉ theo dõi tổng |
| **Budget mode** | Category có spending limit, có progress bar |
| **webhook_token** | Token random trong webhook URL, map webhook → đúng user |
| **inbound_email** | Email address dạng u{id}@in.tienvenoidau.com cho email forwarding |
| **Canonical transaction** | Schema chuẩn hoá internal cho mọi source (SePay/email) |
| **Fuzzy dedup** | Chặn duplicate cross-source (SePay + email) cùng amount/type/3min |

### 7.2. References
- [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md)
- [TDD-vi v1.8.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)
- [Feature spec: Personal vs Business toggle](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-personal-business-toggle.md)
- [Feature spec: Refactor personal → SaaS multi-tenant](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md)
- [Feature spec: Payment via bank transfer v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md)
- [Feature spec: Family Plan v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/drafts/feature-family-plan.md)
- [Feature spec: Funding Sources v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md)
- [Feature spec: Pricing tiers v1.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md)
- [Feature spec: Multi-channel Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)
- [Decision: Onboarding UI strategy v1.0.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md)
- [Feature spec: Admin tools & audit](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-admin-tools.md)
- [Implementation plan: VietQR + email parallel](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md)
- [Implementation plan: scale to 500 users and more](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-500-users-and-more.md)
- [Runbook: Disaster recovery](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md)
- [Observability plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md)
- [Telegram Bot API docs](https://core.telegram.org/bots/api)
- [Telegram Bot API rate limits](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this)
- [Meta Messenger Platform docs](https://developers.facebook.com/docs/messenger-platform/)
- [SePay API docs](https://sepay.vn)
- [Postmark Inbound docs](https://postmarkapp.com/developer/webhooks/inbound-webhook)
- [VietQR.io API docs](https://www.vietqr.io/danh-sach-api/)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial PRD — MVP scope aligned with BRD v2.3.1 at the time. 3-path onboarding, 3-tier pricing, email parsing in MVP, multi-tenant PostgreSQL. Superseded by later BRD/PRD syncs. |
| v1.1.0 | 2026-05-05 | **Alignment fixes vs BRD v2.3.1 + product decisions:** (1) Section 1.2 nguyên tắc 1 — list đủ time estimate cho cả 3 path (2-5 / 10-15 / 5-10 phút). (2) F02 email parser table — đổi "Phase 5" → "Build trong MVP" for then-current bank scope; superseded by v1.2. (3) Categories tier limits — Free max **5 total** (3 default auto-create + user customize), Pro max 20, Business unlimited. Default categories rút từ 5 → 3 (Daily Spending, Saving, Subscription). (4) F06 thêm Pricing sub-section — annual plan **20% off** cho cả Pro ($38.40/yr) và Business ($86.40/yr). (5) Email forwarding mở cho **cả 3 tier**; Pro source count superseded by v1.2 = 3. (6) Section 5.1 Performance — anchor "≥100 concurrent" vào scale 0-500, ≥500 cần benchmark. |
| v1.2.0 | 2026-05-05 | **Sync BRD v2.5.0:** (1) Pro email sources: 1 → **3**. (2) Thêm **SePay cost disclaimer** — user tự trả gói SePay. (3) Email parser banks: expanded to **3-tier system** — MVP 6 banks (TCB, Cake, ACB, STB, BIDV, MB), Phase 2 6 banks (VCB, VietinBank, TPBank, VPBank, HDBank, Agribank), Tier 3 11 banks on-demand. (4) Payment: PayOS+Stripe → **Bank transfer + PayPal + USDT**. (5) F03: thêm email source limit enforcement acceptance criteria. |
| v1.3.0 | 2026-05-05 | **Bot architecture spec + scalability:** (1) Section 1.4 mới — **Bot ownership model**: 1 shared bot platform-owned, user không tạo bot riêng. Spec rõ flow đăng ký, operational implications (BOT_TOKEN env var, chat_id lookup từ DB, backup token). (2) Section 5.4 Scalability tách thành 3 sub: compute/DB, **Telegram bot rate limit + bot pool roadmap** (1 bot → outbound queue ở 100+ → bot pool ở 500+ → Local Bot API server ở 2000+), Postmark email scaling. (3) Daily recap jitter ±5 phút để tránh burst > 30 msg/s ở 23:00. Cross-ref tới feature spec refactor mới. |
| v1.4.0 | 2026-05-05 | **Payment auto-detect spec:** (1) §1.3 tech stack — Bank transfer + auto-detect via SePay primary + Email backup, link tới feature-spec-payment-bank-transfer.md. (2) F06 thêm Payment flow subsection — tóm tắt 4-layer matching, recurring monthly/annual reminder cadence. (3) §6 Analytics — thêm 8 payment events: `payment_initiated`, `payment_matched`, `payment_expired`, `payment_unmatched`, `payment_refunded`, `subscription_renewed`, `subscription_expired_grace`, `subscription_downgraded`. (4) Cross-ref feature spec mới. |
| v1.5.0 | 2026-05-06 | **Sync với 3 spec mới + BRD v2.8.0:** (1) §1.3 tech stack thêm 3 row: **Admin tools** (env `ADMIN_TELEGRAM_IDS`, `ADMIN_RATE_LIMIT_PER_MIN=30`, `/admin_help` registry hybrid), **Observability** (Sentry + Railway, error budget 0.1%, dashboards `/admin_stats` `/admin_cost` `/admin_user`), **Disaster recovery** (8 scenarios, RTO 2-4h, BOT_TOKEN_BACKUP, `@FinTrackUpdates` channel). Backup row clarify SSE-B2 + `pg_dumpall --globals-only`. (2) §4.2 Key Tables thêm 5 row: `pending_payments`, `payment_matches`, `unmatched_payments`, `admin_audit_log`, `analytics_events`. (3) §5.3 Reliability NFR thêm 3 metric: error budget, disaster recovery RTO, out-of-band notification channel. Backup row clarify globals + SSE-B2. Webhook retry clarify cross-source dedup state machine. (4) §6 Analytics thêm 3 admin events: `admin_command_executed`, `admin_command_denied`, `admin_manual_payment_resolved`. (5) §7.2 References thêm 4 cross-doc link (admin tools, DR runbook, observability, implementation plan). |
| v1.6.0 | 2026-05-07 | **Multi-channel foundation MVP + VietQR + email parallel (sync BRD v2.9.0 + feature-spec-messenger-channel v1.1.1 + impl plan VietQR+email v1.0.0):** (1) **§1.1 mô tả**: từ "Telegram bot SaaS" → "**multi-channel SaaS bot**, Telegram primary launch, Messenger feature-flagged sau Meta App Review approve". (2) **§1.4 Bot ownership rewrite**: dual-channel ownership model — `@FinTrackBot` (Telegram public launch theo timeline) + `m.me/FinTrackPage` (Messenger code + foundation ship Phase 6, public access gated bởi `ENABLE_MESSENGER_CHANNEL` flag flip ON sau App Review approve). 2 flow đăng ký separate (slash command vs Get Started postback). UNIQUE constraint changed `users.telegram_id` → `(channel_type, channel_user_id)`. AC liên quan thêm 6 entry mới (env vars Meta, channel adapter grep). (3) **§2 user flows**: thêm note multi-channel — flow logic identical, UX rendering divergent (persistent menu vs slash, quick replies vs inline keyboard). Cross-link tới UX parity matrix Messenger spec. (4) **§3.6 F06 payment flow rewrite**: thêm VietQR via vietqr.io public image URL, 2 QR (VCB primary + TCB secondary) gửi như image attachment, ref code standalone message. Detection latency: VCB ≤60s, TCB ≤5min. Cross-source dedup state machine. Messenger MESSAGE_TAG ACCOUNT_UPDATE cho subscription outbound. (5) §7.2 references thêm Messenger spec, Impl Plan VietQR, Meta docs, vietqr.io API. (6) Header BRD ref bumped v2.8.0 → v2.9.0. |
| v1.7.0 | 2026-05-11 | **Family Plan tier mới (sync BRD v3.2.0 + feature-family-plan v1.0.0):** (1) **§3.6 F06 rewrite**: 4-tier pricing (Free / Pro 99k / Family 169k / Business 299k). Pricing bump Pro 79→99 + Business 199→299 với grandfather 6 tháng. Family-specific limits row (seats, multi-member dashboard, budget limits, real-time alerts). Annual exact math (Pro 1.010k, Family 1.724k, Business 3.050k). Pro→Family trial reset 14d. (2) Cross-feature contracts: F02 `can_ingest_transaction()`, F09 `close_stale_memberships` cron, F08 no schema change, F01 invite-accept flow extension. (3) **§4.1 ER diagram** thêm `family_accounts`, `family_members`, `family_budgets`, `family_invites`. (4) **§7.2 references** thêm Family Plan, Funding Sources, Pricing tiers specs. |
