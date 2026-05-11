# Feature: Transaction Capture — SePay + Email (F02)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 1-5 (Tuần 1-10, 48 days — Telegram + Discord co-primary)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)

---

## 1. Mô tả

Nhận giao dịch từ **SePay webhook** HOẶC **email parser** (Postmark Inbound), normalize thành canonical schema, dedup, lưu DB, gửi category picker cho user. Đây là core loop — mọi tracking bắt đầu từ đây.

> **i18n:** Transaction notification messages served via `t(user.locale, key)`. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).
>
> **Cross-feature:** Mỗi tx được attach FK vào một **funding source** (TK ngân hàng / thẻ / ví) sau khi parse — xem [feature-funding-sources.md (F08)](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md). Pipeline insert FK trước category picker.

**Canonical Transaction Schema:**

| Field | Type | Source: SePay | Source: Email |
|-------|------|--------------|---------------|
| amount | integer | transferAmount | parsed from body |
| direction | enum(in/out) | transferType | parsed from body |
| description | string | description | parsed from body |
| ref_code | string | referenceCode | hash(amount\|desc\|date) |
| tx_date | datetime | transactionDate | parsed from body |
| source | string | "sepay" | "email_{bank}" |

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | SePay | Gửi webhook khi user có giao dịch | Bot parse → lưu DB → gửi category picker |
| 2 | Email | Forward email bank → Postmark | Parser extract → lưu DB → category picker |
| 3 | System | Nhận tx trùng ref_code | Skip silent (dedup exact) |
| 4 | System | Nhận tx cùng amount/type trong 3 phút | Skip silent (fuzzy dedup cross-source) |
| 5 | System | SePay webhook > 10 phút tuổi | Skip (stale protection) |
| 6 | System | Email > 24h tuổi | Skip (stale protection) |
| 7 | User Free | Giao dịch thứ 46 trong tháng | Reject + upgrade prompt |
| 8 | System | Bank chưa support email parsing | Fallback "unparsed" notification |
| 9 | SePay | Field name khác format | Fallback: transferAmount → transfer_amount → amount |
| 10 | System | Invalid webhook token | Return 200 OK, log warning |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | SePay + Email cùng 1 giao dịch | Fuzzy dedup: same amount + type within 3 min = skip |
| 2 | Data Integrity | ref_code NULL từ email | Generate hash(amount\|desc\|date) |
| 3 | Security | Invalid token trong URL | 200 OK + log, không crash |
| 4 | Data Integrity | Amount = 0 hoặc negative | Reject, log warning |
| 5 | Cross-Feature | Free user hit 45 tx limit | Reject + event `tx_limit_hit` |
| 6 | Data Integrity | Email parse fail | Fallback notification → user manual entry |
| 7 | Concurrency | Webhook retry (SePay/Postmark) | UNIQUE(user_id, ref_code) skip |
| 8 | Data Integrity | Bank đổi format email | Versioned parsers + fallback chain |
| 9 | Security | Webhook DDoS attempt | Rate limit per token |
| 10 | Cross-Feature | Email source limit (Free=1, Pro=3) | Enforce ở bank_connections table |
| 11 | Data Integrity | Description chứa ký tự đặc biệt | Sanitize trước lưu DB |
| 12 | Concurrency | Nhiều webhook cùng lúc cho 1 user | Transaction-level isolation |

---

## 3. Screens & States

### Category Picker (sau khi nhận tx)
- **Loading:** N/A (async processing)
- **Ready:**
```
💸 -120,000đ
Pho 24 Nguyen Hue

Khoản này thuộc mục nào? 🤔

[🛒 Daily Spending] [🏦 Saving]
[💼 Work]           [👗 Clothes]
[📱 Subscription]   [➕ New category]
[⏭️ Bỏ qua]
```
- **Error:** "⚠️ Có lỗi khi xử lý giao dịch."
- **Empty:** N/A

### Tier Limit Hit
```
⚠️ Đã hết 45/45 giao dịch tháng này.
Giao dịch mới sẽ không được track.

[⬆️ Upgrade Pro — Unlimited]
```

---

## 4. Domain Model

**Tables:** `transactions`, `bank_connections`, `users`

```sql
CREATE TABLE transactions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount      BIGINT NOT NULL,
    direction   VARCHAR(4) NOT NULL,  -- 'in'/'out'
    description VARCHAR(512),
    ref_code    VARCHAR(64),
    tx_date     TIMESTAMPTZ NOT NULL,
    source      VARCHAR(32) NOT NULL DEFAULT 'sepay',
    category_id INTEGER REFERENCES categories(id),
    confirmed   BOOLEAN NOT NULL DEFAULT FALSE,
    month_key   VARCHAR(7) NOT NULL,
    -- F08 schema extension (owned by feature-funding-sources.md):
    funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL,
    UNIQUE(user_id, ref_code)
);
```

> **F08 ownership:** column `funding_source_id` được F08 add qua `ALTER TABLE` (xem [feature-funding-sources.md §4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md)). F02 runtime PHẢI populate column này — null chỉ acceptable khi resolve fail (xem §10 acceptance criteria). FK `ON DELETE SET NULL` đảm bảo tx không bị xoá khi funding source bị xoá.

**Email Parser Banks (MVP):** TCB, Cake, ACB, STB, BIDV, MB
**Phase 2:** VCB, VietinBank, TPBank, VPBank, HDBank, Agribank

---

## 5. API Endpoints

| Method | Path | Source | Mô tả |
|--------|------|--------|-------|
| POST | `/hook/{user_token}` | SePay | Per-user bank transaction webhook |
| POST | `/inbound/{user_token}` | Postmark | Per-user email forwarding |

Response luôn 200 OK (process async).

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 200 | `TX_DUPLICATE` | N/A (silent skip) | Duplicate ref_code |
| 200 | `TX_STALE` | N/A (silent skip) | SePay >10min, Email >24h |
| 200 | `TX_LIMIT_REACHED` | "⚠️ Hết quota 45 tx/tháng." | Free tier cap |
| 200 | `TX_INVALID_TOKEN` | N/A (log only) | Token không hợp lệ |
| 200 | `TX_PARSE_FAIL` | "📧 Nhận email nhưng không đọc được." | Bank không support |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `tx_received` | Webhook nhận tx | `user_id`, `source`, `tx_type`, `amount_tier` |
| `tx_categorized` | User chọn category | `user_id`, `category`, `latency_sec` |
| `tx_skipped` | User bấm "Bỏ qua" | `user_id` |
| `tx_recategorized` | User bấm "Wrong?" | `user_id` |
| `tx_limit_hit` | Free user chạm 45 | `user_id` |
| `email_parse_success` | Parse OK | `user_id`, `bank` |
| `email_parse_fail` | Parse failed | `user_id`, `bank`, `reason` |

---

## 8. State Machine

Transaction processing là pipeline, không có state machine phức tạp:

```
Webhook/Email → Parse → Dedup → Stale Check → Tier Check
                                                  ↓
                              Resolve Funding Source (F08)
                                                  ↓
                                       INSERT tx (with FK)
                                                  ↓
                                  Category Picker (+ discovery header embed nếu was_discovered)
                                                  ↓
                              (delayed 1.5s) Resurrect notif nếu was_resurrected
```

**Resolve failure handling:** nếu `funding_sources.resolve_funding_source(...)` raise exception, pipeline log + tiếp tục với `funding_source_id=NULL`. Tx không bị mất; user vẫn nhận picker bình thường. Xem [feature-funding-sources-tech.md §4.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-funding-sources-tech.md).

### Timeout Spec

| Variant | Timeout | Behavior khi timeout |
|---------|---------|---------------------|
| SePay webhook stale | 10 phút | Silent skip |
| Email stale | 24 giờ | Silent skip |
| Category picker (uncategorized) | Vô thời hạn | Tx lưu confirmed=FALSE |

---

## 9. Caching Strategy

- **Tier limit count:** Cache monthly tx count per user (invalidate on INSERT)
- **Bank parser registry:** In-memory dict, lazy load
- **User lookup by token:** Cache 5 phút (LRU, max 1000 entries)

---

## 10. Acceptance Criteria

**Parsing & dedup:**
- [ ] SePay parse payload đúng (transferAmount, transferType, description, referenceCode)
- [ ] SePay field name fallbacks hoạt động
- [ ] Email parse 6 MVP banks (TCB, Cake, ACB, STB, BIDV, MB)
- [ ] Email fallback "unparsed" notification
- [ ] Dedup: UNIQUE(user_id, ref_code)
- [ ] Fuzzy dedup cross-source: same amount + type within 3 min = skip
- [ ] Stale protection: SePay >10min = skip, Email >24h = skip
- [ ] Free tier: reject khi >45 tx/tháng
- [ ] Invalid token → 200 OK, log
- [ ] Return 200 immediately, process async
- [ ] Email parser accuracy ≥85% per bank

**Funding source integration ([F08](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md)):**
- [ ] `funding_sources.resolve_funding_source(...)` chạy TRƯỚC `insert_transaction()` — tx luôn có cơ hội nhận FK đúng
- [ ] `transactions.funding_source_id` được populate khi resolve thành công
- [ ] Discovery failure fallback: nếu resolve raise exception, tx VẪN lưu được với `funding_source_id=NULL` (log + alert, không crash pipeline)
- [ ] Discovery message (lần đầu tiên detect TK) embed vào category picker — KHÔNG gửi 2 message liên tiếp
- [ ] Column P (`bank_account` string trong Sheets) tiếp tục được write song song với FK, đảm bảo backward compat trong giai đoạn migration

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.2 |
| v1.0.1 | 2026-05-08 | **i18n note:** Transaction notifications served via `t(user.locale, key)`. |
| v1.1.0 | 2026-05-11 | **F08 integration:** funding_source resolve PHẢI chạy trước tx INSERT, FK `funding_source_id` populated, fallback `funding_source_id=NULL` khi resolve fail. Discovery message embed làm header trong category picker (1 message, không 2 ping). §4 schema bổ sung column `funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL` (F08 extension) + ownership note. Pipeline diagram + acceptance criteria + cross-feature note updated. Xem [F08](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md). |
