# BE Tech Doc: Transaction Categorization (F03)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-categorization.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-categorization.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/transaction.py` | Callback/quick_reply → categorize |
| Service | `services/cat_svc.py` | Category lookup, inline create |
| State | `services/state_svc.py` | bot_state CRUD |
| DB | `db.py` | `update_tx_category()`, `create_category_inline()` |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Assign category
UPDATE transactions SET category_id = $1, sub_category_id = $2, confirmed = TRUE
WHERE id = $3 AND user_id = $4;

-- Get active categories
SELECT * FROM categories WHERE user_id = $1 AND month_key = $2 AND active = TRUE ORDER BY created_at;

-- Get sub-categories
SELECT * FROM sub_categories WHERE category_id = $1 AND active = TRUE;

-- Create inline category
INSERT INTO categories (user_id, slug, name, allocated, month_key)
VALUES ($1, $2, $3, 0, $4)
RETURNING *;

-- Recategorize
UPDATE transactions SET category_id = $1, sub_category_id = NULL WHERE id = $2 AND user_id = $3;
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | Stale callback (tx already categorized) | Re-check tx.confirmed → re-prompt if needed |
| 2 | Concurrency | 2 tx picker cùng lúc | Queue: process sequentially per user via bot_state |
| 3 | Cross-Feature | Free user at 5 categories + inline create | Count check → reject + upgrade prompt |
| 4 | Data Integrity | Deleted category in callback | Re-fetch active list → re-prompt |
| 5 | Security | Callback data tampering | Validate tx_id belongs to user_id |
| 6 | Data Integrity | Slug collision inline create | Append `-2` suffix |
| 7 | Concurrency | Recategorize while another tx pending | bot_state lock per user |
| 8 | Cross-Feature | Category list >13 (Messenger) | Multi-message split |
| 8b | Cross-Feature | Category list >25 (Discord) | Paginate with Prev/Next buttons |
| 9 | Data Integrity | Custom sub name >128 chars | Truncate |
| 10 | Cross-Feature | Skip for incoming tx only | Check direction='in' |
| 11 | Data Integrity | bot_state orphaned (no matching tx) | Cleanup on next interaction |
| 12 | Concurrency | Double-tap same button | Idempotent: check if already confirmed |

---

## 3. API Contract

### 3.1. Callback Data Format

```python
# Telegram callback_data / Discord button custom_id / Messenger quick_reply payload
f"cat:{tx_id}:{category_id}"           # Parent select
f"sub:{tx_id}:{sub_category_id}"       # Sub select
f"skip:{tx_id}"                        # Skip
f"wrong:{tx_id}"                       # Recategorize
f"new_cat:{tx_id}"                     # Inline create
```

---

## 4. Implementation Details

### 4.1. State Machine

```python
async def handle_category_callback(user, tx_id, category_id):
    tx = await db.get_tx(tx_id, user.id)
    if not tx: return
    
    subs = await db.get_sub_categories(category_id)
    if subs:
        await set_state(user.id, 'await_sub', {'tx_id': tx_id, 'parent_id': category_id})
        await messenger.send(user.id, sub_picker(subs))
    else:
        await db.update_tx_category(tx_id, user.id, category_id)
        await clear_state(user.id)
        await send_confirmation(user, tx, category_id)
```

### 4.2. Confirmation Message

- **Tracking mode:** "📊 {name}: tổng tháng này {sum}đ"
- **Budget mode:** Progress bar + remaining + [🔄 Wrong?]

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Select parent (no subs) | cat:1:5 | tx confirmed, confirmation sent |
| 2 | Select parent (has subs) | cat:1:5 | State → await_sub, sub picker shown |
| 3 | Select sub | sub:1:10 | tx confirmed with sub |
| 4 | Skip tx | skip:1 | tx stays unconfirmed |
| 5 | Wrong → recategorize | wrong:1 | Category picker re-shown |
| 6 | Inline create category | new_cat:1 → "Food" | Category created, tx assigned |
| 7 | Inline create limit | 5th category (Free) | Rejected |
| 8 | Stale callback | tx already confirmed | Re-prompt with current state |
| 9 | Invalid tx_id | cat:999:5 | Silent ignore |
| 10 | tx belongs to other user | cat:1:5, wrong user | Reject |
| 11 | Deleted category in callback | cat:1:deleted_id | Re-fetch, re-prompt |
| 12 | Double-tap same button | cat:1:5 twice | Idempotent, same result |
| 13 | Custom sub-category | text "Grab Taxi" | Sub created, assigned |
| 14 | Sub name too long | 200 chars | Truncated to 128 |
| 15 | Slug collision | "Food" exists | "food-2" slug |
| 16 | Tracking mode confirmation | Budget=0 | "📊 total this month" |
| 17 | Budget mode confirmation | Budget=1000000 | Progress bar |
| 18 | Queue 2 tx | tx1 pending, tx2 arrives | tx2 queued |
| 19 | Messenger >13 categories | 15 categories | 2 messages split |
| 19b | Discord >25 categories | 30 categories | Paginated with nav buttons |
| 20 | State cleanup on /start | Orphaned await_sub | State cleared |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
