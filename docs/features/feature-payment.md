# Feature: Payment via Bank Transfer (SePay + Email)

> **Version:** v1.0.0 (refactored từ feature-spec-payment-bank-transfer v1.3.0)
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 6 (Tuần 10-12)
> **Tham chiếu:** [Original spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-payment-bank-transfer.md) · [Impl Plan VietQR+Email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md)

---

## 1. Mô tả

User upgrade Free → Pro/Business qua **bank transfer VN** với detection tự động ≤60s (SePay primary) và ≤5 phút (Email backup). Reuse SePay + email parser infrastructure. `payment_matcher` service dùng 4-layer fuzzy matching (exact ref → fuzzy ref → amount unique → manual review). VietQR via vietqr.io public URL. Dual-bank approach (VCB primary SePay-linked, TCB secondary email-only).

**Non-goals:** Không support card/PayPal/USDT trong MVP. Không auto-debit recurring.

> Chi tiết đầy đủ: [Original spec (archive)](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-payment-bank-transfer.md)

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | `/upgrade pro_monthly` | Bot tạo pending_payment + hiện 2 bank options + VietQR + ref |
| 2 | User | Chuyển khoản đúng ref | SePay webhook → matcher Layer 1 → upgrade ≤60s |
| 3 | User | Chuyển khoản qua TCB (no SePay) | Email parser → matcher → upgrade ≤5 phút |
| 4 | User | Copy ref bị typo 1-2 char | Layer 2 fuzzy match → upgrade + warning |
| 5 | User | Quên paste ref hoàn toàn | Layer 3 amount unique → match if single candidate |
| 6 | User | Chuyển sai amount | Layer 1 match ref nhưng flag amount_mismatch → manual review |
| 7 | Admin | Unmatched payment alert | Review → manual link/refund qua admin command |
| 8 | System | Pending 24h không transfer | Auto-expire, notify user |
| 9 | User | Bấm Cancel trong upgrade flow | Pending → cancelled |
| 10 | System | 3 ngày trước expiry | Reminder + ref mới cho recurring |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | SePay + Email cùng catch 1 transfer | Cross-source dedup qua `pending.status` state lock |
| 2 | Security | Anti-fraud: transfer <5,000đ | Reject, log spam |
| 3 | Data Integrity | Bank truncate ref trong description | Layer 3 fallback amount+window |
| 4 | Cross-Feature | User pay sau expires_at | Flag manual review, admin extend |
| 5 | Concurrency | 2 user cùng amount cùng plan cùng lúc | Layer 1 distinguish (ref khác), Layer 3 ambiguous → manual |
| 6 | Data Integrity | User pay 2 lần (network error) | First match → matched. Second → flag duplicate |
| 7 | Security | Webhook DDoS on PLATFORM_TOKEN | Rate limit 100/min |
| 8 | Cross-Feature | SePay outage 30 phút | Email parser fallback fire 1-5 phút |
| 9 | Data Integrity | Amount tolerance hard cap ±1,000 VND | PAYMENT_AMOUNT_TOLERANCE_VND env var |
| 10 | Cross-Feature | Messenger 24h rule cho payment notification | MESSAGE_TAG ACCOUNT_UPDATE |
| 11 | Cross-Feature | Discord payment notification | DM anytime (no window restriction) |
| 11 | Data Integrity | Ref code collision (2 users same nonce) | UNIQUE constraint, re-generate |
| 12 | Security | Platform bank compromise | Dedicated bank account, 2FA, monitor outflow |

---

## 3. Screens & States

### Upgrade Flow
- **Loading:** "⏳ Đang tạo mã thanh toán..."
- **Ready:** 5 messages: intro → VietQR primary → VietQR secondary → ref code → expiry + buttons
- **Error:** "⚠️ Lỗi tạo thanh toán."
- **Empty:** N/A

### Confirmation (Layer 1 match)
```
✅ Đã nhận 100,000đ — Pro active!
Hết hạn: 05/06/2026
```

### Fallback (VietQR down)
Text-only display: STK + holder name + ref code (feature flag `ENABLE_VIETQR`)

---

## 4. Domain Model

**Tables:** `pending_payments`, `payment_matches`, `unmatched_payments`

**Ref code format:** `PAY-{user_id}-{PLAN}-{M|A}-{nonce4}`

**4-Layer Matching:**
1. Exact ref code match (95% case)
2. Fuzzy ref — Levenshtein ≤2 on extracted token
3. Amount unique — ≤2h window, exact amount, single candidate
4. Unmatched → admin review queue

> Schema SQL chi tiết: [Original spec §3](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-payment-bank-transfer.md)

---

## 5. API Endpoints

| Method | Path | Source | Mô tả |
|--------|------|--------|-------|
| POST | `/hook/{PLATFORM_TOKEN}` | SePay | Platform payment webhook → matcher |
| POST | `/inbound/{PLATFORM_TOKEN}` | Postmark | Platform email backup → parser → matcher |

**Token routing:** dispatcher check `PLATFORM_TOKEN` first → payment_matcher. Else → user pipeline.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 400 | `PAY_ALREADY_PENDING` | "Bạn đã có 1 thanh toán đang chờ." | Duplicate pending |
| 200 | `PAY_EXPIRED` | "⚠️ Mã thanh toán đã hết hạn." | pending > 24h |
| 200 | `PAY_AMOUNT_MISMATCH` | N/A (admin alert) | Amount lệch >1k |
| 200 | `PAY_DUPLICATE_TRANSFER` | N/A (flag admin) | Same user pay 2 lần |
| 200 | `PAY_SPAM_AMOUNT` | N/A (log only) | Amount <5k VND |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `payment_initiated` | `/upgrade` chọn plan | `user_id`, `plan`, `period` |
| `payment_matched` | Matcher confirm | `user_id`, `layer`, `confidence`, `source` |
| `payment_expired` | 24h timeout | `user_id`, `ref_code` |
| `payment_unmatched` | Layer 4 | `amount`, `source` |
| `payment_refunded` | Admin refund | `user_id`, `match_id` |
| `subscription_renewed` | Recurring match | `user_id`, `plan` |
| `subscription_expired_grace` | Grace period | `user_id` |
| `subscription_downgraded` | Grace end → Free | `user_id` |

---

## 8. State Machine

### pending_payment State Machine
```
[/upgrade] → [pending]
    ├── matcher confirms → [matched] → upgrade plan
    ├── 24h timeout → [expired] → notify user
    ├── user cancel → [cancelled]
    └── inconclusive → [manual_review]
            ├── admin confirm → [matched]
            └── admin reject → [cancelled]
```

### Scenarios by Status

| # | Status | Scenario | Actor | Kết quả |
|---|--------|----------|-------|---------|
| P1 | pending | Transfer đúng ref + amount | System | → matched, upgrade |
| P2 | pending | Transfer typo ref | System | Layer 2/3 → matched or manual_review |
| P3 | pending | 24h no transfer | System | → expired |
| P4 | pending | User bấm Cancel | User | → cancelled |
| M1 | manual_review | Admin confirm | Admin | → matched, upgrade |
| M2 | manual_review | Admin reject | Admin | → cancelled |
| MA1 | matched | User request refund | Admin | Plan revoke, refund transfer |

### Timeout Spec

| Variant | Timeout | Behavior |
|---------|---------|----------|
| Pending TTL | 24h (env: PAYMENT_PENDING_TTL_HOURS) | Auto-expire + notify |
| Renewal reminder (monthly) | 3 ngày trước expiry | 1 message |
| Renewal reminder (annual) | 14 + 3 + 1 ngày trước | 3 messages |
| Grace period | 7 ngày sau expiry | Pro features still active |
| Auto-downgrade | Grace end | → Free |

---

## 9. Caching Strategy

- **Pending payments lookup:** Không cache (state changes frequently)
- **VietQR URLs:** Generate on-demand (vietqr.io handles caching)
- **Tier limit check:** Cached per user (invalidate on plan change)

---

## 10. Acceptance Criteria

- [ ] `/upgrade` → 2 bank options + VietQR + ref + copy button
- [ ] Pending expires after 24h
- [ ] Layer 1 match ≥95% success rate (100 mock transfers)
- [ ] Layer 2 fuzzy ≥80% (50 mock typos)
- [ ] Cross-source dedup: SePay + Email → 1 match only
- [ ] Recurring reminder fire đúng schedule
- [ ] Grace period 7 ngày hoạt động
- [ ] Admin tools: list unmatched, manual link, refund
- [ ] Hộ kinh doanh đã đăng ký trước deploy
- [ ] Anti-fraud: <5k VND rejected
- [ ] End-to-end test với real bank transfer

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Refactor từ feature-spec-payment-bank-transfer v1.3.0 → chuẩn 10-section |
| v1.0.1 | 2026-05-08 | **i18n note:** Payment status messages, QR instructions, match confirmations served via `t(user.locale, key)`. |
