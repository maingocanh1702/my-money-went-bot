# FinTrack — Product Requirements Document (PRD)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-05
> **Trạng thái:** Draft
> **Tham chiếu:** [fintrack-brd.md](file:///Users/maingocanh/Projects/Bot%20Finance/fintrack-brd.md) · [SAAS_PIVOT_PLAN.md](file:///Users/maingocanh/Projects/Bot%20Finance/SAAS_PIVOT_PLAN.md)

---

## 1. Tổng quan sản phẩm

### 1.1. Mô tả
FinTrack là Telegram bot tự động theo dõi tài chính cá nhân. Bot kết nối ngân hàng qua SePay, nhận mọi giao dịch real-time, hỏi user phân loại qua inline buttons, và tổng hợp báo cáo tự động.

### 1.2. Nguyên tắc thiết kế
| # | Nguyên tắc | Mô tả |
|---|-----------|-------|
| 1 | **Zero-config** | User không cần biết kỹ thuật. 2 bước setup, không cần deploy gì |
| 2 | **Conversational-first** | Mọi interaction qua chat. Không form, không web UI |
| 3 | **Track-first, budget-optional** | Tracking là default. Budget là opt-in cho ai muốn |
| 4 | **1-tap categorization** | Phân loại = bấm 1 nút. Không nhập text trừ khi tạo category mới |
| 5 | **Data isolation** | Mỗi user là universe riêng. Không bao giờ thấy data của user khác |

### 1.3. Tech stack
| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ · FastAPI · Uvicorn |
| Database | PostgreSQL (Railway managed) |
| Messaging | Telegram Bot API (shared bot) |
| Bank integration | SePay webhook |
| Hosting | Railway (app + DB) |
| Scheduling | APScheduler (in-process) |

---

## 2. User Flows

### 2.1. Onboarding Flow (2 bước)

```
User tìm @FinTrackBot trên Telegram
    │
    ▼
User gửi /start
    │
    ├── Bot tạo account (users table, keyed by telegram_id)
    ├── Bot tạo default categories (5 tracking categories)
    ├── Bot generate unique sepay_token
    │
    ▼
Bot gửi welcome message:
    "👋 Chào bạn! Tôi sẽ giúp bạn theo dõi chi tiêu tự động.
     
     📌 Bước duy nhất: kết nối ngân hàng qua SePay.
     
     1. Vào sepay.vn → Webhook
     2. Dán URL này: https://[domain]/hook/abc123xyz
     3. Done! Giao dịch sẽ tự về đây."
    │
    ▼
User dán webhook URL vào SePay dashboard
    │
    ▼
Giao dịch đầu tiên đến
    ├── Bot gửi: "💸 -50,000đ · Grab Food · Khoản này thuộc mục nào?"
    ├── Inline buttons: [🛒 Daily] [🏦 Saving] [💼 Work] [👗 Clothes] [📱 Sub]
    │
    ▼
User bấm category → Bot confirm
    ▼
✅ Setup hoàn tất — bot sẽ tự track mọi giao dịch tiếp theo
```

### 2.2. Transaction Flow (core loop)

```
SePay webhook → POST /hook/{user_token}
    │
    ├── Validate user_token → lookup user
    ├── Parse payload (amount, description, type, ref_code)
    ├── Dedup check (UNIQUE constraint on ref_code)
    ├── Stale check (reject tx > 10 min old)
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
    [⏭️ Bỏ qua]
    │
    ├── User bấm category
    │   ├── UPDATE transaction SET category_id, confirmed=TRUE
    │   ├── Bot hiển thị tracking info:
    │   │   - Tracking mode: "📊 Daily Spending: tổng tháng này 1,500,000đ"
    │   │   - Budget mode: "██████░░░░ 60% · 600k / 1tr · còn 400k"
    │   └── Kèm nút [🔄 Wrong category?]
    │
    ├── User bấm "➕ New category"
    │   ├── Bot hỏi tên category
    │   ├── User nhập text → tạo category mới (tracking mode)
    │   └── Auto-assign transaction vào category mới
    │
    └── User bấm "⏭️ Bỏ qua"
        └── Transaction giữ uncategorized, confirmed=FALSE
```

### 2.3. Incoming Transaction Flow (Tiền vào)

```
SePay webhook (transferType=in)
    │
    ▼
Bot gửi:
    "💚 +500,000đ vừa vào tài khoản!
     Nguyen Van A chuyen tien
     
     Khoản này thuộc mục nào? 🤔"
    
    [🛒 Daily] [🏦 Saving] ... [⏭️ Bỏ qua]
    │
    └── (Same flow as outgoing, nhưng count là income thay vì spent)
```

### 2.4. Commands

| Command | Mô tả | Availability |
|---------|-------|-------------|
| `/start` | Onboarding — tạo account + hiện webhook URL | All |
| `/status` | Tổng quan tháng: tất cả categories, spent/allocated | All |
| `/today` | Chi tiêu hôm nay vs daily cap (nếu có) | All |
| `/manage` | Quản lý categories: thêm/sửa/xóa/rename | All |
| `/allocate` | (Optional) đặt budget cho categories | All |
| `/weekly` | Báo cáo tuần (7 ngày gần nhất) | Pro |
| `/report` | Báo cáo tháng đầy đủ | Pro |
| `/settings` | Regenerate webhook URL, đổi timezone | All |
| `/export` | Xuất CSV | Pro |
| `/help` | Hướng dẫn sử dụng | All |

---

## 3. Feature Specifications

### 3.1. F01 — Zero-Config Onboarding

**Mô tả:** User gửi /start → bot tự động tạo account, categories, webhook URL. Không cần input gì ngoài dán URL vào SePay.

**Acceptance Criteria:**
- [ ] `/start` tạo user row trong DB với telegram_id unique
- [ ] Tự generate `sepay_token` (24-char URL-safe random string)
- [ ] Tự tạo 5 default categories (tracking mode, allocated=0)
- [ ] Welcome message chứa webhook URL copyable
- [ ] Gọi `/start` nhiều lần = idempotent (không tạo duplicate user)
- [ ] `/start` khi đã có account → hiện lại webhook URL + status tổng quan

**Default Categories:**

| slug | name | daily_cap |
|------|------|-----------|
| `daily_spending` | 🛒 Daily Spending | 100,000đ |
| `saving` | 🏦 Saving | null |
| `work_supplements` | 💼 Work Supplements | null |
| `clothes` | 👗 Clothes | null |
| `subscription` | 📱 Subscription | null |

---

### 3.2. F02 — Transaction Capture (SePay Webhook)

**Mô tả:** Nhận giao dịch từ SePay webhook, parse, dedup, lưu DB, gửi category picker.

**Webhook URL:** `POST /hook/{user_token}`

**Acceptance Criteria:**
- [ ] Parse SePay payload: `transferAmount`, `transferType`, `description`, `referenceCode`, `transactionDate`
- [ ] Field name fallbacks: `transferAmount` → `transfer_amount` → `amount`
- [ ] Dedup via `UNIQUE(user_id, ref_code)` — INSERT ON CONFLICT DO NOTHING
- [ ] Reject stale tx: `age > 10 minutes` (SePay replay protection)
- [ ] Phân biệt outgoing (Tiền ra) vs incoming (Tiền vào)
- [ ] Invalid/unknown `user_token` → return `{"ok": false}`, không crash
- [ ] Return 200 immediately, process in background

**Error Handling:**

| Case | Xử lý |
|------|-------|
| Invalid user_token | 200 OK + log, không crash |
| Missing amount field | Skip, log warning |
| Duplicate ref_code | Skip silently (dedup) |
| Stale transaction (>10min) | Skip, log |
| Unknown transfer type | Skip, log |

---

### 3.3. F03 — Transaction Categorization

**Mô tả:** User phân loại giao dịch qua inline buttons. Hỗ trợ sub-categories và tạo category mới inline.

**Acceptance Criteria:**
- [ ] Inline keyboard: 2 buttons per row, tất cả active categories
- [ ] Nút "➕ New category" ở cuối (tạo inline, không cần /manage)
- [ ] Nút "⏭️ Bỏ qua" cho incoming transactions
- [ ] Sub-category picker hiện sau parent (nếu có sub-categories)
- [ ] Custom sub-category: user nhập text tự do → auto-save
- [ ] Nút "🔄 Wrong category?" trên confirmation message → re-pick
- [ ] State machine: `await_parent` → `await_sub` → `done`
- [ ] State persist qua DB (bot_state table)

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
- [ ] Add: tạo category mới cho month_key hiện tại
- [ ] Budget = 0 → tracking mode. Budget > 0 → budgeted mode
- [ ] Free tier: tối đa 8 categories. Pro: unlimited

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

─────
Tổng budget: 1.4tr / 2tr (70%)
Tổng tracking: 470k
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

#### Daily Recap (tự động, 23h)
```
🌙 End of day — May 05

Daily spending: 180,000đ (72% of limit)
Còn 70,000đ chưa dùng.

Muốn note lại lý do? Reply để bot ghi nhận.
```

**Acceptance Criteria:**
- [ ] `/status` tách BUDGETED vs TRACKING sections
- [ ] `/status` total chỉ aggregate phần budgeted
- [ ] `/today` hiển thị progress bar nếu có daily_cap
- [ ] `/today` "chưa tiêu gì" nếu spent=0
- [ ] Daily recap fire lúc 23:00 **theo timezone của user**
- [ ] Daily recap chỉ fire nếu có ≥1 tx hôm đó (không spam empty days)

---

### 3.6. F06 — Budget Allocation (/allocate)

**Mô tả:** Optional feature để đặt spending limit cho categories.

**Acceptance Criteria:**
- [ ] `/allocate` hiển thị danh sách categories + options:
  - 📋 Keep last month (copy allocations)
  - ✏️ Enter fresh amounts
  - 🏷️ Track only (set all = 0)
  - ⏭️ Skip
- [ ] Nhập amount = 0 → tracking mode
- [ ] Monthly cron (1st of month) → soft check-in message, có nút Skip
- [ ] Summary hiển thị budgeted với amount, tracking với "🏷️ tracking"

---

### 3.7. F07 — Settings (/settings) — NEW

**Mô tả:** User quản lý cài đặt account.

**Options:**
| Setting | Mô tả | Default |
|---------|-------|---------|
| Webhook URL | Hiển thị + nút regenerate | Auto-generated |
| Timezone | Chọn timezone cho reports/recap | Asia/Ho_Chi_Minh |
| Daily recap | Bật/tắt | Bật |
| Plan info | Hiển thị plan hiện tại + upgrade link | Free |

**Acceptance Criteria:**
- [ ] Regenerate webhook URL → invalidate URL cũ ngay lập tức
- [ ] Timezone change → recalculate scheduled job times
- [ ] Toggle daily recap → update scheduled_jobs.enabled

---

### 3.8. F08 — Multi-User Data Isolation

**Mô tả:** Đảm bảo mỗi user chỉ thấy data của mình.

**Acceptance Criteria:**
- [ ] Mọi DB query scope `WHERE user_id = ?`
- [ ] SePay webhook chỉ write vào đúng user (validated by user_token)
- [ ] Bot state isolated per user
- [ ] Scheduled jobs isolated per user
- [ ] Không có API endpoint nào trả data cross-user
- [ ] Error messages không leak user info (không hiện user_id/telegram_id trong errors)

---

### 3.9. F09 — Scheduled Jobs

**Mô tả:** Per-user scheduled tasks thay thế crontab.

| Job | Schedule | Condition |
|-----|----------|-----------|
| `daily_recap` | 23:00 user timezone | enabled=TRUE, có ≥1 tx hôm đó |
| `weekly` | Sunday 14:00 | Pro only |
| `monthly_report` | Last day of month 14:00 | Pro only |
| `monthly_allocation` | 1st of month 08:00 | All |

**Acceptance Criteria:**
- [ ] APScheduler polls `scheduled_jobs` table mỗi 60s
- [ ] Timezone-aware: `next_run_utc` tính từ user's timezone
- [ ] Job failure không block jobs khác
- [ ] Newly created users auto-get `daily_recap` + `monthly_allocation` jobs

---

## 4. Data Model

### 4.1. Entity Relationship

```
users (1) ──── (N) transactions
  │                    │
  │                    └── category_id → categories.slug
  │
  ├──── (N) categories
  │         │
  │         └──── (N) sub_categories
  │
  ├──── (1) bot_state
  │
  └──── (N) scheduled_jobs
```

### 4.2. Tables

Xem chi tiết schema trong [SAAS_PIVOT_PLAN.md](file:///Users/maingocanh/Projects/Bot%20Finance/SAAS_PIVOT_PLAN.md) — Section "Database Schema (PostgreSQL)".

---

## 5. Non-Functional Requirements

### 5.1. Performance
| Metric | Target |
|--------|--------|
| Webhook response time | < 200ms (return 200, process async) |
| Bot reply latency | < 2s (từ webhook đến user nhận message) |
| DB query time | < 50ms (simple queries) |
| Concurrent users | ≥100 simultaneous |

### 5.2. Security
| Concern | Giải pháp |
|---------|----------|
| Webhook auth | Per-user token trong URL (24-char random) |
| Data minimization | Không lưu số tài khoản, chỉ amount + description |
| User isolation | Mọi query scope by user_id |
| Token regeneration | User có thể regenerate webhook URL bất cứ lúc nào |
| Transport | HTTPS only (Railway auto SSL) |
| Secrets | BOT_TOKEN trong env var, không commit |

### 5.3. Reliability
| Metric | Target |
|--------|--------|
| Uptime | ≥99% (Railway SLA) |
| Data durability | PostgreSQL WAL + daily backup |
| Webhook retry | SePay tự retry → dedup bảo vệ |
| Error recovery | Bot gửi "⚠️ Lỗi tạm thời" + log, không crash process |

### 5.4. Scalability
| Stage | Strategy |
|-------|----------|
| 0-100 users | Railway single instance, đủ |
| 100-500 | Tách DB sang Supabase Pro (Singapore) |
| 500+ | Evaluate Fly.io hoặc horizontal scale |

---

## 6. Analytics Events

| Event | Trigger | Properties |
|-------|---------|-----------|
| `user_signup_success` | /start tạo account mới | `telegram_id`, `source` |
| `user_sepay_connected` | Transaction đầu tiên từ SePay | `user_id`, `days_since_signup` |
| `tx_received` | Webhook nhận transaction | `user_id`, `tx_type`, `amount_tier` |
| `tx_categorized` | User bấm category button | `user_id`, `category`, `latency_sec` |
| `tx_skipped` | User bấm "Bỏ qua" | `user_id` |
| `tx_recategorized` | User bấm "Wrong category?" | `user_id` |
| `category_created` | Tạo category mới (inline hoặc /manage) | `user_id`, `method` |
| `command_used` | Bất kỳ slash command | `user_id`, `command` |
| `report_generated` | /status, /today, /weekly, /report | `user_id`, `report_type` |
| `plan_upgrade` | Free → Pro | `user_id`, `payment_method` |

---

## 7. Phụ lục

### 7.1. Glossary

| Thuật ngữ | Định nghĩa |
|-----------|-----------|
| **SePay** | Dịch vụ kết nối ngân hàng VN, cung cấp webhook khi có giao dịch |
| **Category** | Nhóm phân loại chi tiêu (vd: Daily Spending, Saving) |
| **Sub-category** | Phân loại chi tiết hơn trong 1 category (vd: Coffee, Lunch trong Daily) |
| **Tracking mode** | Category với allocated=0, chỉ theo dõi tổng, không có budget |
| **Budget mode** | Category với allocated>0, có progress bar và cảnh báo |
| **user_token** | Token random trong webhook URL, dùng để map SePay webhook → đúng user |
| **Daily cap** | Giới hạn chi tiêu/ngày cho 1 category (optional) |

### 7.2. References
- [SAAS_PIVOT_PLAN.md](file:///Users/maingocanh/Projects/Bot%20Finance/SAAS_PIVOT_PLAN.md) — Technical architecture & migration plan
- [fintrack-brd.md](file:///Users/maingocanh/Projects/Bot%20Finance/fintrack-brd.md) — Business Requirements Document
- [Telegram Bot API docs](https://core.telegram.org/bots/api)
- [SePay API docs](https://sepay.vn)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial PRD — MVP scope |
