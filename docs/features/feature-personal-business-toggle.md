# Feature: Personal vs Business Toggle

> **Version:** v1.0.0 (refactored từ feature-spec-personal-vs-business-toggle v1.0.0)
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Product
> **Phase:** Phase 2 — Business tier launch (~tháng 9-10/2026)
> **Tham chiếu:** [Original spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-personal-vs-business-toggle.md)

---

## 1. Mô tả

Foundation feature cho Business tier. Mỗi transaction tag `personal` / `business` / `unknown` — auto-detect theo bank account mapping + manual 1-tap override + bulk re-tag rules. Unblock P&L view, income source attribution, Google Sheets sync.

**Non-goals V1:** Multi-business (Shop A vs B), split transaction (30%/70%), ML auto-rule learning.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | Upgrade Business → onboarding wizard | Tag accounts: Personal/Business/Mixed |
| 2 | System | Giao dịch mới từ MB (tagged Business) | Auto-tag `entity_type=business` |
| 3 | User | Override tag (bấm 🏠 Personal) | Update entity_type + audit log |
| 4 | User | `/rule` tạo auto-tag rule | Rule apply cho future + optional backfill 30 ngày |
| 5 | User | `/pnl` | P&L tách Personal vs Business |
| 6 | User | Upgrade từ Pro → Business | Migration wizard: "Tag 200 giao dịch cũ?" |
| 7 | User | Skip migration wizard | Start fresh từ ngày upgrade |
| 8 | User | `/rules` | Xem + manage auto-tag rules |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | Internal transfer (shop → personal account) | Detect matching amount within 5 min → tag `internal_transfer` |
| 2 | Data Integrity | Account "Mixed" → giao dịch mới | Default `unknown`, prompt user |
| 3 | Cross-Feature | User edit tag sau 24h | Cho phép qua `/edit {tx_id}`, audit log |
| 4 | Data Integrity | Rule false positive | "Rule X applied to N tx. Undo?" trong 1h |
| 5 | Cross-Feature | Xóa bank account có mapping | Soft-delete mapping, tx cũ giữ tag |
| 6 | Data Integrity | 2 rule conflict (cùng match 1 tx) | Rule mới nhất thắng, warning trong `/rules` |
| 7 | Cross-Feature | Downgrade Business → Pro | Giữ data entity_type, ẩn UI |
| 8 | Data Integrity | Unknown source (manual entry, CSV) | Default `unknown`, prompt |
| 9 | Concurrency | Override tag đồng thời 2 device | Last write wins + audit log |
| 10 | Data Integrity | Max 20 rules/user V1 | Block + message "Đã đạt giới hạn 20 rules" |

---

## 3. Screens & States

### Transaction Notification (post-tag)
- **Ready:**
```
🔔 Giao dịch mới
💰 -250,000đ · Shopee Ads · MB ****5678
🏪 Business (auto)  [🏠 Personal] [❓ Other]
```

### P&L View (`/pnl`)
- **Ready:**
```
📊 P&L Tháng 5/2026
🏪 BUSINESS: Revenue +120.5tr · Expense -85.2tr · Net +35.3tr ✅
🏠 PERSONAL: Income +35tr · Expense -28tr · Net +7tr ✅
❓ UNCATEGORIZED: 3 tx (1.2tr) [Tag now]
```
- **Empty:** "Chưa có dữ liệu tháng này."

---

## 4. Domain Model

```sql
-- Columns mới trên transactions
ALTER TABLE transactions ADD COLUMN entity_type ENUM('personal','business','unknown') DEFAULT 'unknown';
ALTER TABLE transactions ADD COLUMN entity_set_by ENUM('auto_account','auto_rule','manual','migration') DEFAULT 'auto_account';

-- Bank account → entity mapping
CREATE TABLE bank_account_entity_default (
    user_id UUID, bank_account_id UUID,
    default_entity ENUM('personal','business','unknown'),
    PRIMARY KEY (user_id, bank_account_id)
);

-- Auto-tagging rules
CREATE TABLE entity_rules (
    id UUID PRIMARY KEY, user_id UUID,
    match_pattern TEXT, match_field ENUM('description','merchant','amount_range'),
    target_entity ENUM('personal','business'),
    is_active BOOLEAN DEFAULT TRUE, applied_count INTEGER DEFAULT 0
);
```

---

## 5. API Endpoints

Xử lý qua Telegram commands / Discord slash commands: `/pnl`, `/rule`, `/rules`, `/edit {tx_id}`, inline buttons / Action Row buttons.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 403 | `PB_BUSINESS_ONLY` | "Tính năng này cần Business tier." | Non-Business user |
| 400 | `PB_RULE_LIMIT` | "Đã đạt giới hạn 20 rules." | Max rules |
| 400 | `PB_RULE_CONFLICT` | "Rule mâu thuẫn với rule #{id}." | Conflict |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `pb_account_mapped` | Setup account mapping | `user_id`, `account_id`, `entity_type` |
| `pb_override_manual` | Manual tag change | `user_id`, `tx_id`, `old`, `new` |
| `pb_rule_created` | Tạo rule | `user_id`, `pattern`, `target` |
| `pb_rule_applied` | Rule auto-apply | `user_id`, `rule_id`, `tx_count` |
| `pb_pnl_viewed` | `/pnl` | `user_id`, `month` |
| `pb_migration_completed` | Migration wizard done | `user_id`, `tagged_count` |

---

## 8. State Machine

### Entity Tagging Flow
```
[tx_received] → check bank_account_entity_default
    ├── Account = Personal → entity_type = 'personal'
    ├── Account = Business → entity_type = 'business'
    ├── Account = Mixed → entity_type = 'unknown' → prompt user
    └── No mapping → check entity_rules
            ├── Rule match → apply target_entity
            └── No rule → entity_type = 'unknown'
```

### Override window: 24h inline button → sau 24h cần `/edit`

---

## 9. Caching Strategy

- **Bank account mappings:** Cache per user (invalidate on change)
- **Entity rules:** Cache per user (invalidate on CRUD)
- **P&L aggregation:** Compute on-demand (no cache)

---

## 10. Acceptance Criteria

- [ ] Onboarding wizard: tag accounts Personal/Business/Mixed
- [ ] Auto-tag theo bank account mapping
- [ ] Manual override 1-tap inline button
- [ ] Override log: audit trail entity_change_log
- [ ] Rules: CRUD via `/rule`, `/rules`
- [ ] Backfill optional (30 ngày)
- [ ] `/pnl` tách Personal vs Business vs Uncategorized
- [ ] Migration wizard khi upgrade → Business
- [ ] Downgrade: giữ data, ẩn UI
- [ ] Internal transfer detection (matching amount within 5 min)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Refactor từ feature-spec-personal-vs-business-toggle → 10-section |
| v1.0.1 | 2026-05-08 | **i18n note:** Toggle confirmation messages served via `t(user.locale, key)`. |
