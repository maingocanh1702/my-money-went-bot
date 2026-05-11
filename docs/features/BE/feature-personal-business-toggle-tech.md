# BE Tech Doc: Personal vs Business Toggle

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-personal-business-toggle.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-personal-business-toggle.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/pnl.py` | `/pnl`, `/rule`, `/rules`, inline override |
| Service | `services/entity_svc.py` | Auto-tag, rule engine, P&L calc |
| DB | `db.py` | entity queries, rule CRUD |

---

## 2. Database Schema

### 2.1. New Tables

```sql
-- Bank account → entity mapping
CREATE TABLE bank_account_entity_default (
    user_id INTEGER NOT NULL REFERENCES users(id),
    bank_account_id INTEGER NOT NULL REFERENCES bank_connections(id),
    default_entity VARCHAR(16) NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (user_id, bank_account_id),
    CONSTRAINT chk_entity CHECK (default_entity IN ('personal', 'business', 'unknown'))
);

-- Auto-tagging rules
CREATE TABLE entity_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    match_pattern VARCHAR(256) NOT NULL,
    match_field VARCHAR(16) NOT NULL,
    target_entity VARCHAR(16) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    applied_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_match_field CHECK (match_field IN ('description', 'merchant', 'amount_range')),
    CONSTRAINT chk_target CHECK (target_entity IN ('personal', 'business'))
);
CREATE INDEX idx_rules_user ON entity_rules(user_id) WHERE is_active = TRUE;

-- Transactions additions
ALTER TABLE transactions ADD COLUMN entity_type VARCHAR(16) DEFAULT 'unknown';
ALTER TABLE transactions ADD COLUMN entity_set_by VARCHAR(16) DEFAULT 'auto_account';
```

### 2.2. Key Queries

```sql
-- Auto-tag by bank account
SELECT default_entity FROM bank_account_entity_default
WHERE user_id = $1 AND bank_account_id = $2;

-- Apply rules
SELECT * FROM entity_rules WHERE user_id = $1 AND is_active = TRUE ORDER BY created_at;

-- P&L aggregation
SELECT entity_type, direction, SUM(amount) as total
FROM transactions
WHERE user_id = $1 AND month_key = $2 AND confirmed = TRUE
GROUP BY entity_type, direction;

-- Manual override
UPDATE transactions SET entity_type = $1, entity_set_by = 'manual' WHERE id = $2 AND user_id = $3;
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | Internal transfer detection | Match amount within 5 min window |
| 2 | Data Integrity | Mixed account → default unknown | Prompt user |
| 3 | Cross-Feature | Override after 24h | Allowed via `/edit {tx_id}` |
| 4 | Data Integrity | Rule false positive | Undo within 1h |
| 5 | Cross-Feature | Delete bank mapping | Soft-delete, tx keep tag |
| 6 | Data Integrity | 2 rules conflict | Newest wins + warning |
| 7 | Cross-Feature | Downgrade Business→Pro | Data kept, UI hidden |
| 8 | Data Integrity | Unknown source | Default unknown |
| 9 | Concurrency | Override concurrent | Last write wins |
| 10 | Data Integrity | Max 20 rules | Count check |
| 11 | Cross-Feature | Backfill 30 days | Batch UPDATE with rule |
| 12 | Data Integrity | Rule pattern injection | Sanitize pattern |

---

## 3. API Contract

### 3.1. Entity Tag Flow

```python
async def auto_tag_entity(user_id, tx, bank_connection_id):
    mapping = await db.get_entity_default(user_id, bank_connection_id)
    if mapping and mapping != 'unknown':
        return mapping, 'auto_account'
    rules = await db.get_active_rules(user_id)
    for rule in rules:
        if rule_matches(rule, tx):
            await db.increment_rule_count(rule.id)
            return rule.target_entity, 'auto_rule'
    return 'unknown', 'auto_account'
```

---

## 4. Implementation Details

### 4.1. Rule Matching

```python
def rule_matches(rule, tx) -> bool:
    if rule.match_field == 'description':
        return rule.match_pattern.lower() in tx.description.lower()
    elif rule.match_field == 'amount_range':
        lo, hi = map(int, rule.match_pattern.split('-'))
        return lo <= tx.amount <= hi
    return False
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Auto-tag personal account | Bank mapped personal | entity_type=personal |
| 2 | Auto-tag business account | Bank mapped business | entity_type=business |
| 3 | Auto-tag mixed | Bank mapped mixed | entity_type=unknown |
| 4 | Rule match description | "Shopee" pattern | entity_type=business |
| 5 | Rule match amount range | "100000-500000" | Matched |
| 6 | Rule no match | Pattern not found | unknown |
| 7 | Manual override | Override to personal | entity_type=personal, set_by=manual |
| 8 | P&L aggregation | Mix of types | Grouped correctly |
| 9 | P&L empty month | 0 tx | Empty state |
| 10 | Internal transfer detect | -500k + +500k within 5min | Tagged internal |
| 11 | Rule limit 20 | 21st rule | Rejected |
| 12 | Rule conflict | 2 rules match | Newest applied |
| 13 | Backfill 30 days | Apply rule backward | Batch updated |
| 14 | Undo backfill | Within 1h | Reverted |
| 15 | Business only access | Free user /pnl | Rejected |
| 16 | Downgrade preserve | Business→Pro | Data intact |
| 17 | Delete mapping | Remove bank | Soft-delete |
| 18 | Rule create | /rule "Shopee" business | Rule active |
| 19 | Rule delete | /rules → delete | is_active=FALSE |
| 20 | Unknown source | Manual entry tx | entity=unknown |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
