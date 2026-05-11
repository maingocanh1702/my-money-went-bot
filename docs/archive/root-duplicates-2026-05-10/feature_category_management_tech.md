# BE Tech Doc: Category Management — /manage (F04)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_category_management.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_category_management.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/manage.py` | `/manage` command + callbacks |
| Service | `services/cat_svc.py` | CRUD categories + sub-categories |
| DB | `db.py` | Category/sub CRUD queries |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- List active categories with spend
SELECT c.*, COALESCE(SUM(t.amount), 0) as spent
FROM categories c
LEFT JOIN transactions t ON t.category_id = c.id AND t.direction = 'out' AND t.confirmed = TRUE
WHERE c.user_id = $1 AND c.month_key = $2 AND c.active = TRUE
GROUP BY c.id ORDER BY c.created_at;

-- Count categories (tier limit)
SELECT COUNT(*) FROM categories WHERE user_id = $1 AND active = TRUE;

-- Rename category
UPDATE categories SET name = $1, updated_at = NOW() WHERE id = $2 AND user_id = $3;

-- Soft delete category
UPDATE categories SET active = FALSE WHERE id = $1 AND user_id = $2;

-- Update budget
UPDATE categories SET allocated = $1 WHERE id = $2 AND user_id = $3;

-- Add category
INSERT INTO categories (user_id, slug, name, allocated, month_key) VALUES ($1, $2, $3, $4, $5) RETURNING *;

-- Soft delete sub-category
UPDATE sub_categories SET active = FALSE WHERE id = $1 AND user_id = $2;
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | Tier limit check | Count active categories WHERE user_id |
| 2 | Data Integrity | Soft delete preserves tx | active=FALSE, FK intact |
| 3 | Data Integrity | Rename → slug unchanged | Only update name column |
| 4 | Data Integrity | Budget = 0 → tracking | allocated=0 means tracking mode |
| 5 | Security | user_id scope | WHERE user_id = $1 on all queries |
| 6 | Data Integrity | Empty name input | Reject, validate length > 0 |
| 7 | Data Integrity | Name > 128 chars | Truncate |
| 8 | Data Integrity | Budget negative | Reject, validate >= 0 |
| 9 | Concurrency | 2 renames same category | Last write wins |
| 10 | Data Integrity | Duplicate slug on add | ON CONFLICT → append suffix |
| 11 | Cross-Feature | Delete → sub-categories | Cascade soft delete subs |
| 12 | Data Integrity | Emoji in name | Allowed, VARCHAR supports UTF-8 |

---

## 3. API Contract

### 3.1. Callback Data

```python
f"manage:list"                      # Show list
f"manage:cat:{category_id}"         # Show actions
f"manage:rename:{category_id}"      # Start rename
f"manage:budget:{category_id}"      # Start budget edit
f"manage:delete:{category_id}"      # Confirm delete
f"manage:delete_confirm:{id}"       # Execute delete
f"manage:subs:{category_id}"        # Show sub-categories
f"manage:add"                       # Start add flow
```

---

## 4. Implementation Details

### 4.1. Slug Generation

```python
import re, unicodedata
def slugify(name: str) -> str:
    name = unicodedata.normalize('NFKD', name)
    name = re.sub(r'[^\w\s-]', '', name.lower())
    return re.sub(r'[-\s]+', '-', name).strip('-')[:64]
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | List categories | `/manage` | Active categories with spend |
| 2 | Empty list | No categories | Empty state message |
| 3 | Rename category | "New Name" | name updated, slug unchanged |
| 4 | Rename empty | "" | Rejected |
| 5 | Delete category | manage:delete_confirm:5 | active=FALSE |
| 6 | Delete preserves tx | Delete cat with 10 tx | tx.category_id still valid |
| 7 | Add category | "Transport", 500000 | Category created |
| 8 | Add at tier limit | 6th category (Free) | Rejected |
| 9 | Budget update to 0 | Budget = 0 | Tracking mode |
| 10 | Budget update positive | Budget = 1000000 | Budgeted mode |
| 11 | Budget negative | Budget = -100 | Rejected |
| 12 | Name too long | 200 chars | Truncated to 128 |
| 13 | Emoji in name | "🍜 Food" | Accepted |
| 14 | Slug collision | "Food" exists | "food-2" |
| 15 | Sub-category list | manage:subs:5 | Active subs shown |
| 16 | Sub rename | "New Sub" | label updated |
| 17 | Sub delete | Soft delete | active=FALSE |
| 18 | Tier limits Pro | 20 categories | At limit |
| 19 | Tier limits Business | Unlimited | Accepted |
| 20 | user_id scope | Different user's cat | Rejected |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
