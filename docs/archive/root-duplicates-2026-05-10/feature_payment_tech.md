# BE Tech Doc: Payment via Bank Transfer

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_payment.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_payment.md)
> **Original spec (full algorithm):** [archive/feature-spec-payment-bank-transfer.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-payment-bank-transfer.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/upgrade.py` | `/upgrade` command, plan selection |
| Matcher | `services/payment_matcher.py` | 4-layer fuzzy matching |
| QR | `services/qr_generator.py` | VietQR URL composition |
| Handler | `handlers/payment_inbound.py` | Platform payment webhook routing |
| DB | `db.py` | pending_payments, payment_matches, unmatched CRUD |

---

## 2. Database Schema

> Full DDL: [TDD v1.6.0 §2.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) — `pending_payments`, `payment_matches`, `unmatched_payments`

### 2.1. Key Queries

```sql
-- Create pending payment
INSERT INTO pending_payments (user_id, ref_code, plan, period, expected_amount, expires_at)
VALUES ($1, $2, $3, $4, $5, NOW() + INTERVAL '24 hours') RETURNING *;

-- Fetch pending by ref (Layer 1)
SELECT * FROM pending_payments WHERE ref_code = $1 AND status = 'pending';

-- Fetch pending for update (cross-source lock)
SELECT * FROM pending_payments WHERE id = $1 FOR UPDATE;

-- Fetch pending 24h (Layer 2 fuzzy)
SELECT * FROM pending_payments WHERE status = 'pending' AND created_at > NOW() - INTERVAL '24 hours';

-- Fetch pending 2h (Layer 3 amount)
SELECT * FROM pending_payments WHERE status = 'pending' AND created_at > NOW() - INTERVAL '2 hours';

-- Insert match (dedup via dedup_key)
INSERT INTO payment_matches (pending_payment_id, source, source_ref_code, dedup_key, amount, raw_description, match_layer, match_confidence, reviewed_by)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'auto')
ON CONFLICT (dedup_key) DO NOTHING RETURNING *;

-- Update pending status
UPDATE pending_payments SET status = $1, matched_at = NOW() WHERE id = $2;

-- Expire stale pending
UPDATE pending_payments SET status = 'expired' WHERE status = 'pending' AND expires_at < NOW();
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | SePay + Email same transfer | Row lock on pending via FOR UPDATE |
| 2 | Security | Transfer <5,000đ | Reject as spam |
| 3 | Data Integrity | Ref truncated by bank | Layer 3 fallback |
| 4 | Cross-Feature | Pay after expired | Flag manual_review |
| 5 | Concurrency | 2 users same amount same time | Layer 1 distinguishes by ref |
| 6 | Data Integrity | Double payment | Second → flag duplicate |
| 7 | Security | DDoS on PLATFORM_TOKEN | Rate limit 100/min |
| 8 | Cross-Feature | SePay outage | Email backup 1-5min |
| 9 | Data Integrity | Amount ±1,000 VND | Tolerance via env var |
| 10 | Data Integrity | Levenshtein on full desc | Extract token first, compare token-to-token |
| 11 | Concurrency | confirm_match race | Transaction + row lock |
| 12 | Data Integrity | dedup_key collision | SHA256 hash = extremely unlikely |
| 13 | Cross-Feature | Refund flow | Revoke plan + mark match refunded |
| 14 | Data Integrity | Ref code UNIQUE collision | Retry with new nonce |

---

## 3. API Contract

### 3.1. Platform Webhook Routing

```python
# Token dispatch (in main.py)
async def hook_handler(token: str, request: Request):
    if token == PLATFORM_TOKEN:
        return await payment_inbound_handler(request)  # → payment_matcher
    user = await db.get_user_by_token(token)
    if user:
        return await sepay_handler(user, request)       # → tx pipeline
    return Response(status_code=200)                    # Unknown token
```

### 3.2. Ref Code Format

```python
def generate_ref_code(user_id: int, plan: str, period: str) -> str:
    nonce = secrets.token_hex(2).upper()  # 4 hex chars
    p = 'PRO' if plan == 'pro' else 'BIZ'
    m = 'M' if period == 'monthly' else 'A'
    return f"PAY-{user_id}-{p}-{m}-{nonce}"
```

---

## 4. Implementation Details

### 4.1. 4-Layer Matching (summary)

| Layer | Condition | Confidence | Auto-confirm? |
|-------|-----------|------------|---------------|
| 1 | Exact ref + amount ±1k | high | ✅ |
| 2 | Fuzzy ref (Levenshtein ≤2 on token) + amount ±1k | medium | ✅ + warning |
| 3 | Amount exact + ≤2h window + single candidate | low | ✅ + admin notify |
| 4 | No match | — | ❌ admin review |

> Full algorithm with code: [archive spec §4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-payment-bank-transfer.md)

### 4.2. VietQR URL Builder

```python
def vietqr_url(bank_bin: str, account: str, amount: int, ref: str, holder: str) -> str:
    return (f"https://img.vietqr.io/image/{bank_bin}-{account}-compact2.png"
            f"?amount={amount}&addInfo={ref}&accountName={urllib.parse.quote(holder)}")
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Create pending | /upgrade pro monthly | Row created, ref_code valid |
| 2 | Ref code format | user 42, pro, monthly | PAY-42-PRO-M-XXXX |
| 3 | Layer 1 exact match | Exact ref + exact amount | Matched, plan upgraded |
| 4 | Layer 1 amount ±1k | Ref match, amount off 500 | Matched |
| 5 | Layer 1 amount >1k off | Ref match, amount off 5k | Manual review |
| 6 | Layer 2 fuzzy 1 char | 1 char typo in token | Matched medium |
| 7 | Layer 2 fuzzy 2 chars | 2 char typo | Matched medium |
| 8 | Layer 2 fuzzy 3 chars | 3 char typo | No match → Layer 3 |
| 9 | Layer 3 single candidate | Same amount, 1 pending ≤2h | Matched low |
| 10 | Layer 3 ambiguous | Same amount, 2 pending | Manual review |
| 11 | Layer 4 unmatched | No pending matches | Admin alert |
| 12 | Cross-source dedup | SePay then Email | Only 1 match |
| 13 | Same-source retry | SePay webhook retry | dedup_key skip |
| 14 | Expired pending | Pay after 24h | Manual review |
| 15 | Cancel pending | User cancel button | Status = cancelled |
| 16 | Anti-spam | Amount = 100 VND | Rejected |
| 17 | VietQR URL valid | VCB, 100k | URL resolves to image |
| 18 | VietQR fallback | ENABLE_VIETQR=false | Text-only display |
| 19 | Expire stale job | 5 pending >24h | All expired |
| 20 | Concurrent confirm | 2 sources same time | 1 match only |
| 21 | Refund flow | admin_refund | Plan revoked, match refunded |
| 22 | Grace period start | Expiry reached | grace_until = +7d |
| 23 | Recurring ref code | Renewal | New ref_code generated |
| 24 | Rate limit platform | 150 req/min | Blocked after 100 |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
