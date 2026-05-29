# BE Tech Doc: Transaction Capture — SePay + Email (F02)

> **Version:** v1.2.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-transaction-capture.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-transaction-capture.md)
> **TDD ref:** [TDD-vi v1.9.0 §2.1 transactions, §3.2 pipeline](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| SePay Handler | `handlers/sepay.py` | Parse SePay webhook payload |
| Email Handler | `handlers/email_inbound.py` | Parse Postmark inbound → bank parser |
| Pipeline | `services/tx_pipeline.py` | Normalize → dedup → stale check → tier check → INSERT → picker |
| Parsers | `parsers/tcb.py`, `parsers/cake.py`, ... | Bank-specific email parsing |
| DB | `db.py` | `insert_transaction()`, `check_dedup()`, `count_monthly_tx()` |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Insert transaction (idempotent via ref_code).
-- IMPORTANT: funding_source_id MUST be populated từ funding_sources.resolve_funding_source(...)
-- chạy trước, hoặc NULL nếu resolve fail. Xem F08 §4.1.
INSERT INTO transactions (
    user_id, tx_date, description, direction, amount,
    ref_code, source, month_key, funding_source_id
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (user_id, ref_code) DO NOTHING
RETURNING *;

-- Exact dedup check
SELECT EXISTS(SELECT 1 FROM transactions WHERE user_id=$1 AND ref_code=$2);

-- Fuzzy dedup (cross-source, 3-min window)
SELECT EXISTS(
    SELECT 1 FROM transactions
    WHERE user_id = $1 AND amount = $2 AND direction = $3
    AND ABS(EXTRACT(EPOCH FROM (tx_date - $4::timestamptz))) < 180
);

-- Monthly tx count (tier limit)
SELECT COUNT(*) FROM transactions WHERE user_id = $1 AND month_key = $2;

-- Stale check
-- SePay: tx_date > NOW() - INTERVAL '10 minutes'
-- Email: tx_date > NOW() - INTERVAL '24 hours'
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | SePay + Email cùng 1 tx | Fuzzy dedup: amount + direction + 3min window |
| 2 | Data Integrity | ref_code NULL từ email | Generate hash(amount\|desc\|date) |
| 3 | Security | Invalid webhook token | 200 OK + log warning |
| 4 | Data Integrity | Amount = 0 hoặc negative | Reject, log |
| 5 | Cross-Feature | Free user >45 tx | Reject + `tx_limit_hit` event |
| 6 | Data Integrity | Email parse fail | Log + fallback notification |
| 7 | Concurrency | Webhook retry | ON CONFLICT DO NOTHING |
| 8 | Data Integrity | Bank đổi email format | Versioned parsers + fallback chain |
| 9 | Security | Webhook DDoS | Rate limit per token: 60/min |
| 10 | Data Integrity | Description chứa SQL injection | Parameterized queries (asyncpg) |
| 11 | Concurrency | 50 webhooks cùng lúc cho 1 user | Connection pool handles, dedup catch |
| 12 | Cross-Feature | Stale SePay webhook (>10min) | Skip silent |
| 13 | Data Integrity | SePay field name variants | Fallback: transferAmount → transfer_amount |
| 14 | Cross-Feature | Email source limit enforce | Count WHERE user_id AND type='email' |

---

## 3. API Contract

### 3.1. SePay Webhook

```
POST /hook/{user_token}
Content-Type: application/json

{
  "transferAmount": 120000,
  "transferType": "out",
  "description": "Pho 24 Nguyen Hue",
  "referenceCode": "FT26050812345",
  "transactionDate": "2026-05-08T12:00:00"
}
```

**Response:** Always `200 OK` (process async via BackgroundTasks)

### 3.2. Postmark Inbound

```
POST /inbound/{user_token}
Content-Type: application/json

{
  "From": "automail@tcb.com.vn",
  "Subject": "Thông báo giao dịch",
  "HtmlBody": "<html>...<td>-120,000</td>...</html>",
  "TextBody": "..."
}
```

### 3.3. Canonical Transaction Schema

```python
@dataclass
class CanonicalTx:
    amount: int           # VND integer
    direction: str        # 'in' | 'out'
    description: str
    ref_code: str         # SePay referenceCode | hash for email
    tx_date: datetime
    source: str           # 'sepay' | 'email_tcb' | 'email_cake' | ...
```

---

## 4. Implementation Details

### 4.1. Pipeline Flow

```python
async def process_transaction(user: User, raw_data: dict, source: str):
    tx = normalize_payload(raw_data, source)       # 1. Parse
    if await check_dedup(user.id, tx):             # 2. Dedup
        return
    if is_stale(tx, source):                       # 3. Stale check
        return
    if not await check_tier_limit(user):           # 4. Tier check
        await notify_limit_reached(user)
        return

    # 5. Resolve funding source (F08) — MUST run before INSERT
    try:
        fs_result = await funding_sources.resolve_funding_source(
            user_id=user.id, raw_payload=raw_data, source=source, tx_date=tx.tx_date)
        fs_id = fs_result.funding_source_id
    except Exception:
        logger.exception("fs resolve failed; tx will save with NULL FK")
        fs_result = ResolveResult(None, False, False)
        fs_id = None

    # 6. INSERT tx with FK (or NULL on resolve failure)
    tx_id = await db.insert_transaction(user.id, tx, funding_source_id=fs_id)

    # 7. Category picker — prepend discovery header if was_discovered
    header = render_discovery_header(user.locale, fs_id) if fs_result.was_discovered else None
    await send_category_picker(user, tx_id, tx, prepend=header)

    # 8. Resurrect notif — delayed, separate message
    if fs_result.was_resurrected:
        await asyncio.sleep(1.5)
        await notify_funding_source_resurrected(user, fs_id)
```

Xem [feature-funding-sources-tech.md §4.1, §4.2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-funding-sources-tech.md) cho chi tiết F08 integration.

### 4.2. Email Parser Plugin Pattern

```python
PARSERS = {
    'tcb': TCBParser,
    'cake': CakeParser,
    'acb': ACBParser,
    'stb': STBParser,
    'bidv': BIDVParser,
    'mb': MBParser,
}

def detect_bank(from_email: str) -> str | None:
    BANK_DOMAINS = {
        'automail@tcb.com.vn': 'tcb',
        'notification@cake.vn': 'cake',
        ...
    }
    return BANK_DOMAINS.get(from_email.lower())
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | SePay parse valid | Full payload | CanonicalTx correct |
| 2 | SePay field fallback | transferAmount missing, transfer_amount present | Parse success |
| 3 | SePay missing ref | referenceCode NULL | Hash generated |
| 4 | Email parse TCB | TCB email fixture | CanonicalTx correct |
| 5 | Email parse Cake | Cake email fixture | CanonicalTx correct |
| 6 | Email unknown bank | Unknown from address | Fallback notification |
| 7 | Exact dedup | Same ref_code twice | Second skipped |
| 8 | Fuzzy dedup | Same amount/direction within 3min | Second skipped |
| 9 | No fuzzy dedup | Same amount, 5min apart | Both inserted |
| 10 | Stale SePay | tx_date > 10min ago | Skipped |
| 11 | Fresh SePay | tx_date 30s ago | Processed |
| 12 | Stale email | tx_date > 24h ago | Skipped |
| 13 | Free tier limit 44 | 44th tx | Accepted |
| 14 | Free tier limit 45 | 45th tx | Accepted (cap is 45) |
| 15 | Free tier limit 46 | 46th tx | Rejected + event |
| 16 | Pro tier unlimited | 100th tx | Accepted |
| 17 | Invalid token | Unknown token | 200 OK, log warning |
| 18 | Amount zero | amount=0 | Rejected |
| 19 | Amount negative | amount=-100 | Rejected |
| 20 | Description sanitize | SQL injection attempt | Parameterized, safe |
| 21 | Concurrent webhooks | 5 parallel same user | All deduped correctly |
| 22 | Pipeline async | Valid tx | 200 returned immediately |
| 23 | Category picker sent | After INSERT | messenger.send called |
| 24 | Month key calculation | tx_date Jan 31 23:59 | month_key='2026-01' |
| 25 | FS resolve before INSERT | Valid payload | resolve_funding_source called first, tx INSERT có FK populated |
| 26 | FS resolve failure fallback | resolve raises | Tx vẫn INSERT với funding_source_id=NULL, log error, no crash |
| 27 | Discovery header embed | First tx of new fs | Single message với prepend header, không 2 message |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
| v1.1.0 | 2026-05-11 | **F08 integration:** `process_transaction()` rewrite — resolve funding_source trước INSERT, populate FK, try/except fallback NULL. Discovery header prepend vào picker (1 message). Resurrect notification delayed 1.5s sau picker. §2.1 INSERT query thêm `funding_source_id` column ($9). Test plan thêm cases 25-27. Xem [F08 BE](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-funding-sources-tech.md). |
| v1.2.0 | 2026-05-30 | **Docs sync:** TDD ref v1.8.1→v1.9.0. Note: `_persist()` in `sepay_webhook.py` now returns `int | None` (tx_id or None for dupes) — enables SePay handler to distinguish new inserts vs duplicate retries, driving conditional category picker dispatch. `insert_transaction()` in §2.1 already used `RETURNING *` — no query change needed, behavioral clarification only. Zalo categorize handler uses this to gate numbered-text picker on new rows only. |
