# Feature: Category Management — /manage (F04)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)

---

## 1. Mô tả

CRUD categories và sub-categories qua `/manage`. User có thể thêm/sửa/xóa/rename categories, đặt budget, và quản lý sub-categories. Soft delete để giữ nguyên transactions cũ.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | `/manage` | Hiện danh sách categories + tổng/category |
| 2 | User | Tap category → ✏️ Rename | Nhập tên mới → update |
| 3 | User | Tap category → 💰 Edit Budget | Nhập amount (0=tracking, >0=budgeted) |
| 4 | User | Tap category → 🗑️ Delete | Soft delete (active=FALSE) |
| 5 | User | ➕ Add Category | Nhập tên + budget → tạo mới |
| 6 | User | Tap category → Sub-categories | Hiện list sub + rename/delete |
| 7 | User | Rename sub-category | Update label |
| 8 | User | Delete sub-category | Soft delete sub |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | Free user đã 5 categories + Add | Block + upgrade prompt |
| 2 | Data Integrity | Delete category có transactions | Soft delete, tx cũ giữ nguyên |
| 3 | Data Integrity | Rename → slug trùng | Giữ slug cũ, chỉ đổi display name |
| 4 | Data Integrity | Budget = 0 | Chuyển sang tracking mode |
| 5 | Security | User sửa category của user khác | WHERE user_id = $1 enforce |
| 6 | Data Integrity | Tên chứa emoji 🎉 | Cho phép, truncate 128 chars |
| 7 | Cross-Feature | Delete category đang là default | Cho phép, user tạo mới hoặc dùng cái khác |
| 8 | Data Integrity | Add category tên trống | Reject "Tên không được để trống" |
| 9 | Concurrency | 2 session cùng rename | Last write wins |
| 10 | Data Integrity | Budget âm | Reject "Budget phải ≥ 0" |

---

## 3. Screens & States

### Category List
- **Loading:** "⏳ Đang tải danh mục..."
- **Ready:**
```
📋 Danh mục của bạn (3/5)

🛒 Daily Spending — 💰 1,000,000đ/tháng
🏦 Saving — 🏷️ tracking
📱 Subscription — 🏷️ tracking

[➕ Thêm danh mục]
```
- **Error:** "⚠️ Lỗi tải danh mục."
- **Empty:** "Chưa có danh mục nào." + [➕ Tạo mới]

### Category Actions
```
🛒 Daily Spending

[✏️ Đổi tên] [💰 Sửa budget]
[🗑️ Xóa]     [📂 Sub-categories]
[⬅️ Quay lại]
```

---

## 4. Domain Model

```sql
CREATE TABLE categories (
    id       SERIAL PRIMARY KEY,
    user_id  INTEGER NOT NULL REFERENCES users(id),
    slug     VARCHAR(64) NOT NULL,
    name     VARCHAR(128) NOT NULL,
    allocated BIGINT NOT NULL DEFAULT 0,  -- 0 = tracking
    daily_cap BIGINT,
    month_key VARCHAR(7) NOT NULL,
    active   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(user_id, slug, month_key)
);

CREATE TABLE sub_categories (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    key         VARCHAR(64) NOT NULL,
    label       VARCHAR(128) NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(category_id, key)
);
```

---

## 5. API Endpoints

Không có REST API riêng — xử lý qua Telegram command / Discord slash command `/manage` + callback_query/button interaction trong `/webhook/{channel}`.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 400 | `MANAGE_LIMIT` | "Đã đạt giới hạn {limit} danh mục. Upgrade để thêm." | Tier limit |
| 400 | `MANAGE_NAME_EMPTY` | "Tên danh mục không được để trống." | Input rỗng |
| 400 | `MANAGE_NAME_LONG` | "Tên tối đa 128 ký tự." | Quá dài |
| 400 | `MANAGE_BUDGET_INVALID` | "Budget phải là số ≥ 0." | Nhập sai format |
| 409 | `MANAGE_DUPLICATE` | "Danh mục '{name}' đã tồn tại." | Trùng slug |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `manage_opened` | `/manage` | `user_id`, `category_count` |
| `manage_category_created` | Tạo category | `user_id`, `name`, `budget` |
| `manage_category_renamed` | Rename | `user_id`, `old_name`, `new_name` |
| `manage_category_deleted` | Soft delete | `user_id`, `name` |
| `manage_budget_changed` | Đổi budget | `user_id`, `name`, `old`, `new` |
| `manage_sub_created` | Tạo sub | `user_id`, `parent`, `sub_name` |
| `manage_sub_deleted` | Xóa sub | `user_id`, `sub_name` |

---

## 8. State Machine

```
[/manage] → [manage_list] (hiện danh sách)
    ├── Tap category → [manage_actions] (✏️💰🗑️📂)
    │   ├── ✏️ Rename → [await_manage_rename] → [manage_list]
    │   ├── 💰 Budget → [await_manage_amount] → [manage_list]
    │   ├── 🗑️ Delete → confirm → [manage_list]
    │   └── 📂 Subs → [manage_subs] → [manage_list]
    └── ➕ Add → [await_add_cat_name] → [await_add_cat_amount] → [manage_list]
```

---

## 9. Caching Strategy

- **Category list:** Cache 5 phút per user (invalidate on CRUD operations)
- **Sub-category list:** Cache 5 phút per category

---

## 10. Acceptance Criteria

- [ ] `/manage` hiện list: category name + "🏷️ tracking" hoặc budget amount
- [ ] Rename: update tên, giữ slug
- [ ] Delete: soft delete (active=FALSE), tx cũ giữ nguyên
- [ ] Add: tạo category mới
- [ ] Budget = 0 → tracking mode. Budget > 0 → budgeted mode
- [ ] Tier limits: Free 5, Pro 20, Business unlimited
- [ ] Sub-categories CRUD hoạt động
- [ ] State machine persist qua bot_state

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.4 |
| v1.0.1 | 2026-05-08 | **i18n note:** All user-facing messages served via `t(user.locale, key)`. |
