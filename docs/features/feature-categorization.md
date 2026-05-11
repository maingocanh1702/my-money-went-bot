# Feature: Transaction Categorization (F03)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.3](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)

---

## 1. Mô tả

User phân loại giao dịch qua **inline buttons** trong Telegram / Action Row buttons trên Discord / quick replies trên Messenger. Hỗ trợ sub-categories, tạo category mới inline, và sửa lại category đã chọn. State machine: `await_parent` → `await_sub` → `done`.

> **i18n:** All user-facing messages (picker prompt, confirmation, error) served via `t(user.locale, key)`. Button labels bilingual. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | Bấm category button | Finalize tx, hiện confirmation + tổng tháng |
| 2 | User | Bấm "➕ New category" | Nhập tên → tạo category mới → assign tx |
| 3 | User | Bấm "⏭️ Bỏ qua" | Tx lưu uncategorized |
| 4 | User | Bấm "🔄 Wrong category?" | Re-pick category |
| 5 | User | Chọn parent có sub-categories | Hiện sub-category picker |
| 6 | User | Nhập custom sub-category text | Auto-save sub → assign tx |
| 7 | User | Bấm category cho tx tracking mode | Hiện "📊 {name}: tổng tháng này {amount}" |
| 8 | User | Bấm category cho tx budget mode | Hiện "██████░░░░ 60% · 600k / 1tr · còn 400k" |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | User bấm button cũ (stale callback) | Check tx_id still valid, re-prompt nếu không |
| 2 | Concurrency | 2 tx đến cùng lúc, user đang pick cho tx1 | Queue tx2, pick cho tx1 xong mới hiện tx2 |
| 3 | Cross-Feature | Free user đã có 5 categories + bấm "➕ New" | Block + upgrade prompt |
| 4 | Data Integrity | Category đã bị soft-delete nhưng button vẫn hiện | Re-fetch active categories, re-prompt |
| 5 | Security | Callback data tampered | Validate tx_id belongs to user |
| 6 | Cross-Feature | Incoming tx → "⏭️ Bỏ qua" cho phép | Chỉ hiện cho incoming (direction='in') |
| 7 | Data Integrity | Tên category mới trùng slug | Append suffix, notify user |
| 8 | Concurrency | User pick category đồng thời trên 2 device | Last write wins |
| 9 | Cross-Feature | Category list > 13 (Messenger limit) | Split thành multi-message |
| 11 | Cross-Feature | Category list > 25 (Discord limit) | Paginate với Prev/Next buttons |
| 10 | Data Integrity | User nhập tên category dài > 128 chars | Truncate + notify |

---

## 3. Screens & States

### Category Picker
- **Loading:** N/A (inline với tx notification)
- **Ready:** Grid buttons 2 per row + "➕ New" + "⏭️ Bỏ qua"
- **Error:** "⚠️ Không load được danh mục."
- **Empty:** "Chưa có category nào. Tạo mới?" + [➕ Tạo]

### Confirmation
- **Tracking mode:** "📊 Daily Spending: tổng tháng này 1,500,000đ"
- **Budget mode:** "██████░░░░ 60% · 600k / 1tr · còn 400k" + [🔄 Wrong?]

---

## 4. Domain Model

**Tables:** `transactions`, `categories`, `sub_categories`, `bot_state`

State machine qua `bot_state`:
- `step = 'await_parent'`: chờ user chọn parent category
- `step = 'await_sub'`: chờ user chọn sub-category
- `payload`: `{tx_id, parent_category_id, ...}`

---

## 5. API Endpoints

Không có API riêng — xử lý qua Telegram callback_query / Discord button interaction / Messenger quick_reply postback trong `/webhook/{channel}`.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 400 | `CAT_LIMIT_REACHED` | "Đã đạt giới hạn {limit} danh mục." | Free=5, Pro=20 |
| 404 | `CAT_NOT_FOUND` | "Danh mục không tồn tại." | Deleted category |
| 400 | `CAT_NAME_TOO_LONG` | "Tên quá dài, tối đa 128 ký tự." | Input validation |
| 409 | `CAT_DUPLICATE_SLUG` | "Danh mục '{name}' đã tồn tại." | Trùng slug |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `categorize_parent_selected` | Chọn parent category | `user_id`, `category_id`, `latency_sec` |
| `categorize_sub_selected` | Chọn sub-category | `user_id`, `sub_id` |
| `categorize_skipped` | Bấm "Bỏ qua" | `user_id`, `tx_id` |
| `categorize_recategorized` | Bấm "Wrong?" | `user_id`, `tx_id`, `old_cat`, `new_cat` |
| `categorize_inline_created` | Tạo category inline | `user_id`, `name` |

---

## 8. State Machine

```
[tx_received] → [await_parent]
    ├── User chọn parent (có sub) → [await_sub]
    │       ├── User chọn sub → [done] → confirmation
    │       └── User nhập custom sub → [done]
    ├── User chọn parent (không sub) → [done] → confirmation
    ├── User bấm "➕ New" → [await_inline_new_cat_name] → [done]
    └── User bấm "⏭️ Bỏ qua" → [done] (uncategorized)
```

### Scenarios by Status

| # | Status | Scenario | Actor | Kết quả |
|---|--------|----------|-------|---------|
| P1 | await_parent | Chọn category | User | → done hoặc → await_sub |
| P2 | await_parent | Bấm Skip | User | → done (uncategorized) |
| P3 | await_parent | Bấm New | User | → await_inline_new_cat_name |
| S1 | await_sub | Chọn sub | User | → done |
| S2 | await_sub | Nhập custom text | User | → done (auto-create sub) |

---

## 9. Caching Strategy

- **Active categories per user:** Cache 5 phút (invalidate on CRUD)
- **Sub-categories per category:** Cache 5 phút

---

## 10. Acceptance Criteria

- [ ] Inline keyboard: 2 buttons per row, tất cả active categories
- [ ] "➕ New category" ở cuối
- [ ] "⏭️ Bỏ qua" cho incoming tx
- [ ] Sub-category picker hiện sau parent
- [ ] Custom sub-category: user nhập text → auto-save
- [ ] "🔄 Wrong category?" trên confirmation → re-pick
- [ ] State machine: `await_parent` → `await_sub` → `done`
- [ ] State persist qua DB (bot_state table)
- [ ] Free: max 5 categories. Pro: 20. Business: unlimited

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.3 |
| v1.0.1 | 2026-05-08 | **i18n note:** All user-facing messages (picker prompt, confirmation, errors, button labels) served via `t(user.locale, key)`. No structural change — only rendering layer wraps `t()`. |
