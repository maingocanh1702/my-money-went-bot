# Feature: Reports (F05)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD v1.5.0 §3.5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-en.md)

---

## 1. Mô tả

Hệ thống báo cáo tài chính: `/status` (tổng quan tháng), `/today` (hôm nay), daily recap (tự động 23h), `/weekly` (Pro+), `/report` (Pro+), `/export` CSV (Pro+). Tách rõ BUDGETED vs TRACKING vs INCOME sections.

> **i18n:** All report text, headers, labels, section names served via `t(user.locale, key)`. Number format: vi → `1.500.000đ`, en → `1,500,000 VND`. Xem [feature_i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_i18n.md).

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | `/status` | Tổng quan tháng: categories, spent/allocated |
| 2 | User | `/today` | Chi tiêu hôm nay vs daily cap |
| 3 | System | 23:00 local timezone | Daily recap tự động (nếu có ≥1 tx) |
| 4 | Pro User | `/weekly` | 7-day breakdown |
| 5 | Pro User | `/report` | Full monthly report |
| 6 | Pro User | `/export` | Gửi file CSV qua Telegram |
| 7 | User | Reply daily recap | Bot ghi nhận note |
| 8 | Free User | `/weekly` | "Tính năng Pro. Upgrade?" |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | Không có tx nào tháng này | Empty state: "Chưa có giao dịch tháng này" |
| 2 | Cross-Feature | Daily recap nhưng 0 tx hôm đó | Không gửi recap |
| 3 | Data Integrity | Category bị delete giữa tháng | Tx cũ vẫn hiện trong report |
| 4 | Cross-Feature | Free user gọi `/export` | Upgrade prompt |
| 5 | Data Integrity | Timezone thay đổi giữa tháng | Recalculate report boundaries |
| 6 | Concurrency | User gọi `/status` khi có tx đang process | Show data đã committed |
| 7 | Data Integrity | Amount overflow (số rất lớn) | Format safe với locale |
| 8 | Cross-Feature | 30-day history limit (Free) | Chỉ query within 30 ngày |
| 9 | Data Integrity | CSV export với ký tự đặc biệt | Escape properly |
| 10 | Cross-Feature | Daily recap cho Messenger user ngoài 24h | Dùng MESSAGE_TAG ACCOUNT_UPDATE |
| 11 | Cross-Feature | Daily recap cho Discord user | DM anytime (no window restriction) |

---

## 3. Screens & States

### /status
- **Loading:** "⏳ Đang tính toán..."
- **Ready:**
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
- **Error:** "⚠️ Lỗi tạo báo cáo."
- **Empty:** "📭 Chưa có giao dịch tháng này. Kết nối bank để bắt đầu!"

### /today
- **Ready:**
```
🍜 Today — May 05

Hôm nay: 180,000đ (3 tx)
███████░░░ 72% of 250k cap
Còn 70,000đ hôm nay

Còn 26 ngày trong tháng
Monthly còn 400,000đ
```

### Daily Recap (23:00)
```
🌙 End of day — May 05

Daily spending: 180,000đ (72% of limit)
Còn 70,000đ chưa dùng.

Muốn note lại lý do? Reply để bot ghi nhận.
```

---

## 4. Domain Model

**Tables:** `transactions`, `categories`, `monthly_reports`

**Key query:** Aggregate `SUM(amount)` GROUP BY category, filtered by `user_id`, `month_key`, `direction`.

---

## 5. API Endpoints

Xử lý qua Telegram commands / Discord slash commands / Messenger persistent menu trong `/webhook/{channel}`.

| Command | Tier | Mô tả |
|---------|------|-------|
| `/status` | All | Monthly overview |
| `/today` | All | Daily overview |
| `/weekly` | Pro+ | 7-day breakdown |
| `/report` | Pro+ | Full monthly |
| `/export` | Pro+ | CSV file |

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 403 | `REPORT_PRO_ONLY` | "📊 Tính năng này cần Pro. /upgrade" | Free user gọi Pro feature |
| 500 | `REPORT_CALC_FAIL` | "⚠️ Lỗi tính toán báo cáo." | DB error |
| 400 | `REPORT_INVALID_RANGE` | "Khoảng thời gian không hợp lệ." | Date range sai |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `report_status_viewed` | `/status` | `user_id`, `month_key`, `category_count` |
| `report_today_viewed` | `/today` | `user_id`, `tx_count_today` |
| `report_weekly_viewed` | `/weekly` | `user_id` |
| `report_monthly_viewed` | `/report` | `user_id` |
| `report_exported` | `/export` | `user_id`, `row_count` |
| `report_daily_recap_sent` | Daily recap fire | `user_id`, `tx_count` |
| `report_daily_note_added` | Reply daily recap | `user_id` |

---

## 8. State Machine

Reports không có state machine phức tạp — mỗi command là 1 request-response.

### Timeout Spec

| Variant | Trigger | Behavior |
|---------|---------|----------|
| Daily recap | 23:00 ±5min jitter (per user timezone) | Chỉ gửi nếu ≥1 tx hôm đó |
| Weekly report | Sunday 14:00 ±5min jitter | Pro+ only |
| Monthly report | Last day of month 14:00 ±5min jitter | Pro+ only |

---

## 9. Caching Strategy

- **Status data:** Không cache (realtime query)
- **Monthly report archive:** Lưu vào `monthly_reports` table cuối tháng
- **CSV export:** Generate on-demand, không cache

---

## 10. Acceptance Criteria

- [ ] `/status` tách BUDGETED vs TRACKING vs INCOME
- [ ] `/today` hiển thị progress bar nếu có daily_cap
- [ ] Daily recap fire 23:00 theo timezone user ±5min jitter
- [ ] Daily recap chỉ fire nếu có ≥1 tx
- [ ] `/weekly` (Pro+): 7-day breakdown
- [ ] `/report` (Pro+): full monthly
- [ ] `/export` (Pro+): CSV file gửi qua Telegram
- [ ] Free user gọi Pro feature → upgrade prompt

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.5 |
| v1.0.1 | 2026-05-08 | **i18n note:** All report text, headers, section names served via `t(user.locale, key)`. Currency formatting bilingual. |
