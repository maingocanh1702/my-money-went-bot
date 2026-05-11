# Feature Spec — Payment via Bank Transfer (SePay + Email Auto-detect)

> **Version:** v1.3.0
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase liên quan:** BRD Phase 6 (tuần 10-11) — Payment integration + VietQR via vietqr.io public URL + email parallel; foundations infra reuse từ Phase 1-2 (SePay) + Phase 5 (Email parser plugin)
> **Tham chiếu:** [BRD v2.9.0 §5.2.4 Payment](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md) · [PRD v1.6.0 §F06 Pricing](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md) · [TDD v1.6.0 §5.2 env vars](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) · [Feature Spec Refactor SaaS](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-refactor-saas.md) · [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-messenger-channel.md) · [Impl Plan VietQR+Email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md)

---

## 1. Mục tiêu & non-goals

### 1.1. Mục tiêu

Cho phép user upgrade Free → Pro / Business qua **bank transfer VN** với detection **tự động ≤ 60 giây** (SePay primary) và **≤ 5 phút** (Email backup). Mục tiêu user không cần card, không tải app payment, chỉ chuyển khoản trong mobile banking quen thuộc với 1 ref string copy-paste.

Reuse infrastructure đã build cho user transaction tracking (SePay webhook + email parser plugin) — chỉ thêm 1 service `payment_matcher` để classify "đây là user transaction hay platform payment".

### 1.2. Non-goals

- KHÔNG support card (Visa/Master/JCB) trong MVP — defer sau khi MRR ≥ $200 + có nhu cầu international
- KHÔNG support PayPal / USDT trong MVP — flagged trong PRD §1.3 nhưng để Phase 2 (sau khi bank transfer chứng minh hoạt động)
- KHÔNG auto-debit recurring — user phải manually transfer mỗi cycle. Mitigation: annual plan + reminder.
- KHÔNG xây admin dashboard phức tạp — manual review qua CLI tool / Telegram admin chat đủ cho beta phase

---

## 2. Architecture overview

### 2.1. High-level flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ User                                                                │
│  └─ /upgrade pro_monthly trên bot                                   │
│        ↓                                                            │
│ Bot                                                                 │
│  ├─ Tạo pending_payment row, generate ref "PAY-{user_id}-PRO-M-{nonce4}"  │
│  └─ Show 2-3 bank account options của platform + ref               │
│        ↓                                                            │
│ User chuyển khoản trong mobile banking (description = ref)         │
│        ↓                                                            │
│ Money lands in platform's bank account                              │
│        ↓                                                            │
│  ┌──────────────────────┐         ┌──────────────────────────────┐ │
│  │ SePay (primary)      │   OR    │ Email notification (backup)  │ │
│  │ Webhook fire 5-30s   │         │ Forward → Postmark 1-5 min   │ │
│  └──────────┬───────────┘         └──────────────┬───────────────┘ │
│             ↓                                     ↓                 │
│             POST /hook/PLATFORM_TOKEN     POST /inbound/PLATFORM_TOKEN
│             ↓                                     ↓                 │
│             ↓                                     ↓                 │
│             ┌───────────────────────────┐                           │
│             │  payment_matcher service  │                           │
│             │  • Classify: user-tx hay  │                           │
│             │    platform-payment?      │                           │
│             │  • 4-layer fuzzy match    │                           │
│             │  • Dedup cross-source     │                           │
│             └───────────┬───────────────┘                           │
│                         ↓                                           │
│             ┌───────────────────────────┐                           │
│             │ Match found?              │                           │
│             ├─ YES → upgrade user.plan  │                           │
│             │        send confirmation  │                           │
│             ├─ NO + amount ~ pending →  │                           │
│             │   manual review queue     │                           │
│             └─ NO + amount unknown →    │                           │
│                 unmatched, alert admin  │                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2. Bank account setup của platform

> **Compliance note:** Account holder phải là **legal receiving entity** — registered hộ kinh doanh owner / công ty TNHH (xem §8). Mọi placeholder `<holder name>` trong spec/runbook là production = legal entity, KHÔNG phải founder personal account. Tránh ship instruction sai sau này.

Setup 2 bank account dedicated cho subscription (đã confirm có sẵn):

| Bank | SePay linked? | Email notification? | Vai trò |
|------|---------------|---------------------|---------|
| **VCB primary** (vd 9999 8888 7777) | ✅ Yes | ✅ Yes (redundancy) | Default option, fastest detection |
| **TCB / MB secondary** (1 tài khoản) | ❌ No (cost-saving SePay sub) | ✅ Yes | Cho user prefer bank khác / SePay outage |

**Why dual-bank approach:** SePay account có cost (~50-100k/tháng cho Pro plan của SePay). Platform owner chỉ link SePay với 1 bank chính. Banks khác chỉ dựa vào email — đủ cho low-volume (subscription = ~5-30 transfer/ngày ở 100 paying user).

**SePay platform token:** generate 1 token riêng `PLATFORM_TOKEN` cho payment webhook, KHÁC với user_token. Webhook URL: `/hook/{PLATFORM_TOKEN}` → routed to `payment_matcher` service thay vì user transaction pipeline.

### 2.3. Email backup logic

Với bank không link SePay:
- Platform owner setup forwarding rule trong Gmail/Outlook của owner: forward email từ `automail@tcb.com.vn` (etc.) → `payment@in.fintrack.app`
- Postmark Inbound endpoint `POST /inbound/{PLATFORM_TOKEN}` (cùng token với SePay path)
- Reuse email parser plugin pattern (đã spec trong feature-spec-refactor-saas.md §2.4)
- Output canonical tx → feed vào `payment_matcher`
- Implementation handler: `handlers/payment_inbound.py` route email → `parsers/email_platform_{bank}.py` → match qua cùng pipeline với SePay

> **Implementation detail:** [implementation-plan-payment-vietqr-email.md §4.5–4.6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md) cho parser code + handler dispatch logic.

### 2.4. VietQR via vietqr.io public image URL

Bot compose URL trỏ tới **vietqr.io public image service** (free, no API key) cho cả 2 bank account. Đây KHÔNG phải self-generate QR (image render bởi vietqr.io server-side, banking app fetch URL khi scan); true self-generation là Option B defer Phase 7+.

**Tradeoffs đã accept (Option A):**

| Aspect | Pros | Cons |
|---|---|---|
| Cost | $0 (free public service) | — |
| Dev time | ~50 LOC, 1h build | — |
| Privacy | — | Leak `ref_code` + `account_number` + `amount` tới vietqr.io (third-party) |
| Reliability | vietqr.io reliable historically | Dependency on uptime của họ. Down → fallback text-only |
| Rate limit | — | ~30 req/min/IP, OK cho MVP volume <50 upgrade/day |
| Compliance | — | Cần document trong privacy policy: "QR generation routed qua vietqr.io" |

**API format:**
```
https://img.vietqr.io/image/{BANK_BIN}-{ACCOUNT}-{TEMPLATE}.png
  ?amount={amount}
  &addInfo={ref_code}
  &accountName={holder_name}
```

**Bank BIN mapping (NAPAS national IDs):**

| Bank | BIN |
|---|---|
| VCB (Vietcombank) | 970436 |
| TCB (Techcombank) | 970407 |
| MB Bank | 970422 |
| ACB | 970416 |
| STB (Sacombank) | 970403 |
| BIDV | 970418 |
| VTB (VietinBank) | 970415 |
| VPB (VPBank) | 970432 |
| TPB (TPBank) | 970423 |
| Cake (VPBank fintech) | 546034 |

**Implementation:** `services/qr_generator.py` wrap với function `vietqr_url(bank, account, amount, ref_code, holder)`. Đầu ra là URL string, embed vào outbound message qua `messenger.send(user_id, {"type": "image", "url": ..., "caption": ...})`.

**Adapter dispatch:**
- Telegram: `sendPhoto` với `photo=URL` + caption inline
- Messenger: `attachment.type=image` + `payload.url=URL` + caption gửi message kế tiếp (Messenger không support caption inline với image attachment)

**Fallback:** Nếu vietqr.io down hoặc render fail (image size 0 hoặc 404), bot detect → fallback text-only display (xem §5.1 fallback). Feature flag `ENABLE_VIETQR=false` cũng force fallback.

**Future migration (Option B, Phase 7+):** Self-host EMVCo encoder (NAPAS spec) bằng `qrcode` Python lib generate offline. Trigger: vol >500 paying users, hoặc privacy/compliance audit yêu cầu không leak ref code ra third-party service.

> **Detail spec:** [implementation-plan-payment-vietqr-email.md §4.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md) cho code + tests.

---

## 3. Data Model

### 3.1. New tables

```sql
-- Pending payments — user requested upgrade nhưng chưa transfer
CREATE TABLE pending_payments (
  id              SERIAL PRIMARY KEY,
  user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ref_code        VARCHAR(32) UNIQUE NOT NULL,       -- "PAY-{user_id}-PRO-M-{nonce4}"
  plan            VARCHAR(16) NOT NULL,              -- 'pro' | 'business'
  period          VARCHAR(8) NOT NULL,               -- 'monthly' | 'annual'
  expected_amount BIGINT NOT NULL,                   -- VND integer, vd 100000 cho Pro monthly
  status          VARCHAR(16) NOT NULL DEFAULT 'pending',
                                                     -- 'pending'|'matched'|'expired'|'cancelled'|'manual_review'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at      TIMESTAMPTZ NOT NULL,              -- created_at + 24h
  matched_at      TIMESTAMPTZ,
  -- NOTE: bỏ `matched_match_id` (was circular FK). Reverse query qua payment_matches.pending_payment_id

  CONSTRAINT chk_payment_status CHECK (status IN
    ('pending', 'matched', 'expired', 'cancelled', 'manual_review'))
);

CREATE INDEX idx_pending_user ON pending_payments(user_id, status);
CREATE INDEX idx_pending_expires ON pending_payments(expires_at)
  WHERE status = 'pending';

-- Payment matches — log mỗi lần matcher confirm transfer ↔ pending payment
CREATE TABLE payment_matches (
  id              SERIAL PRIMARY KEY,
  pending_payment_id INT REFERENCES pending_payments(id),
  source          VARCHAR(32) NOT NULL,              -- 'sepay'|'email_tcb'|'email_mb'|'manual'|'email_tcb_platform'|'email_mb_platform'
  source_ref_code VARCHAR(64),                       -- referenceCode từ SePay/email (nullable)
  dedup_key       VARCHAR(128) NOT NULL UNIQUE,      -- **same-source retry dedup** — sha256(source|source_ref_code or fallback)
                                                     -- NULL-safe replacement cho UNIQUE(source, source_ref_code).
                                                     -- KHÔNG dùng cho cross-source dedup (xem §4.1 + edge case #12).
  amount          BIGINT NOT NULL,
  raw_description TEXT NOT NULL,                     -- nguyên văn từ webhook
  match_layer     INT NOT NULL,                      -- 1=exact ref, 2=fuzzy token, 3=amount+window, 4=manual
  match_confidence VARCHAR(8) NOT NULL,              -- 'high'|'medium'|'low'
  status          VARCHAR(16) NOT NULL DEFAULT 'matched',
                                                     -- 'matched'|'refunded'|'credited'|'voided'
  matched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_by     VARCHAR(64),                       -- 'auto' | admin telegram_id nếu manual
  refunded_at     TIMESTAMPTZ,
  refund_notes    TEXT,

  CONSTRAINT chk_confidence CHECK (match_confidence IN ('high', 'medium', 'low')),
  CONSTRAINT chk_match_status CHECK (status IN ('matched', 'refunded', 'credited', 'voided'))
);

CREATE INDEX idx_matches_pending ON payment_matches(pending_payment_id);
CREATE INDEX idx_matches_status ON payment_matches(status) WHERE status != 'matched';

-- Unmatched payments — incoming transfer không khớp pending nào, cần admin review
CREATE TABLE unmatched_payments (
  id              SERIAL PRIMARY KEY,
  source          VARCHAR(32) NOT NULL,              -- 'sepay'|'email_tcb_platform'|'email_mb_platform'|'manual'
  source_ref_code VARCHAR(64),                       -- nullable
  dedup_key       VARCHAR(128) NOT NULL UNIQUE,      -- same formula as payment_matches.dedup_key (source-scoped)
  amount          BIGINT NOT NULL,
  raw_description TEXT NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL,
  status          VARCHAR(20) NOT NULL DEFAULT 'pending_review',
                                                     -- 'pending_review'|'matched_manually'|'refunded'|'kept_as_credit'
  resolved_by     VARCHAR(64),                       -- admin telegram_id
  resolved_at     TIMESTAMPTZ,
  notes           TEXT
);

CREATE INDEX idx_unmatched_pending ON unmatched_payments(status)
  WHERE status = 'pending_review';
```

**`dedup_key` formula (same-source retry dedup):**

```python
def compute_dedup_key(tx: CanonicalTx) -> str:
    """
    Same-source retry dedup. Goal: nếu SePay/Postmark retry webhook (network error)
    cùng 1 transfer → INSERT ON CONFLICT skip silent.

    KHÔNG dùng key này để cross-source dedup vì `tx.source` khác giữa SePay vs Email.
    Cross-source dedup handled qua pending_payments.status state machine (xem §4.1).
    """
    # Prefer source_ref_code nếu có (SePay luôn có referenceCode)
    if tx.source_ref_code:
        raw = f"{tx.source}|{tx.source_ref_code}"
    else:
        # Fallback: hash amount + minute-rounded time + normalized desc
        minute = tx.received_at.replace(second=0, microsecond=0).isoformat()
        normalized_desc = re.sub(r'\s+', ' ', tx.description.strip()).lower()[:200]
        raw = f"{tx.source}|{tx.amount}|{minute}|{normalized_desc}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Cross-source dedup — separate mechanism:**

Khi SePay và Email cùng catch 1 transfer, hai records có `dedup_key` khác nhau (vì source khác). Cross-source dedup được enforce qua **`pending_payments.status` state machine**:

```python
async def confirm_match(pending: PendingPayment, tx: CanonicalTx, layer: int, ...):
    # Re-fetch pending with row lock to prevent race condition
    async with db.transaction():
        fresh = await db.fetch_pending_for_update(pending.id)
        if fresh.status != 'pending':
            # Already matched bởi source nhanh hơn (vd SePay matched 5s trước, giờ Email mới đến)
            log.info(f"[matcher] cross-source skip: pending {pending.id} already {fresh.status}")
            return MatchResult(matched=False, reason='cross_source_already_matched')

        # Atomic: insert match + update pending.status
        match = await db.insert_payment_match(pending.id, tx, layer, ...)
        await db.update_pending_status(pending.id, 'matched', match.id)
        await upgrade_user_plan(pending.user_id, pending.plan, pending.period)
        return MatchResult(matched=True, match_id=match.id)
```

→ Source thứ 2 đến muộn → check `pending.status` đã 'matched' → skip silent. Match record của source thứ 2 KHÔNG được insert (avoid duplicate).

**Trade-off:** không log trace của source thứ 2 cho audit. Nếu cần audit trail của cả 2 source: insert match record với `status='voided'` thay vì skip — rare case nên có thể defer.

**Schema rationale changes:**
1. **Drop `pending_payments.matched_match_id`**: circular FK weak. Reverse query đơn giản: `SELECT * FROM payment_matches WHERE pending_payment_id = $1 AND status = 'matched' LIMIT 1`. One pending → one matched record → query reverse đủ.
2. **Add `payment_matches.status`**: track refund/credited/voided (refund spec §11 nói "Track trong payment_matches.status" nhưng schema cũ thiếu column — bug fix).
3. **Add `dedup_key` cho cả `payment_matches` + `unmatched_payments`**: replace `UNIQUE(source, source_ref_code)` không hoạt động với NULL. **Source-scoped only** — không tự dedup cross-source.
4. **Cross-source dedup**: enforce qua `pending_payments.status` state transition + row lock, không qua `dedup_key`.

### 3.2. Update existing tables

```sql
-- Add columns to users table (nếu chưa có từ Phase 3 pricing logic)
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_grace_until TIMESTAMPTZ;
                                                     -- 7-day grace period sau expiry
ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_period VARCHAR(8);
                                                     -- 'monthly' | 'annual' — current cycle
```

---

## 4. Matching Algorithm — 4-layer fuzzy

> **Amount matching rule (áp dụng mọi layer):** Bank transfer VND nội địa luôn exact tới integer. Auto-confirm chỉ khi `actual == expected` (or tolerance ≤ 1,000 VND để cover edge case rounding hiếm). Lệch > 1,000 VND → flag manual review, KHÔNG auto-confirm. Lý do: ±5% trên Pro 100k = 95k vẫn match là quá rộng, dễ match nhầm.

```python
def amount_matches(actual: int, expected: int) -> bool:
    """Exact match cho bank transfer VND. ±1k tolerance là hard cap."""
    return abs(actual - expected) <= 1000


def extract_pay_tokens(description: str) -> list[str]:
    """
    Extract candidate ref tokens từ bank description (full text).
    Bank thường gửi: "NGUYEN VAN A chuyen tien PAY-123-PRO-M-X9K2 tu Vietcombank"
    → trả về ['PAY-123-PRO-M-X9K2']
    """
    # Match strict format trước
    strict = re.findall(r'PAY-\d+-[A-Z]+-[MA]-[A-Z0-9]{4}', description, re.IGNORECASE)
    if strict:
        return strict
    # Fallback: token bắt đầu PAY-, có ít nhất 3 dash sections (catch typo)
    loose = re.findall(r'PAY-[\w-]{6,30}', description, re.IGNORECASE)
    return loose


async def match_incoming_payment(tx: CanonicalTx) -> MatchResult:
    """
    Input: canonical tx từ SePay hoặc email parser, source='sepay_platform'|'email_*_platform'
    Output: match đúng pending_payment, hoặc enqueue vào unmatched

    Cross-source dedup handled inside confirm_match():
      - confirm_match() takes row lock on pending_payments + checks status=='pending'
      - Source thứ 2 đến muộn hơn (sau khi source 1 đã set status='matched') → skip silent
    Same-source retry dedup handled bởi UNIQUE(dedup_key) constraint:
      - INSERT ON CONFLICT DO NOTHING khi insert payment_match
    """

    # ═══ Layer 1: EXACT ref code match ═══
    # 95% case rơi vào đây nếu user copy-paste đúng
    tokens = extract_pay_tokens(tx.description)
    for token in tokens:
        pending = await db.fetch_pending_by_ref(token)
        if pending and pending.status == 'pending':
            if amount_matches(tx.amount, pending.expected_amount):
                return await confirm_match(pending, tx, layer=1, confidence='high')
            else:
                # Ref đúng nhưng amount lệch > 1k → manual review (không auto)
                return await flag_review(pending, tx, reason='amount_mismatch',
                                         note=f'expected={pending.expected_amount}, got={tx.amount}')

    # ═══ Layer 2: FUZZY ref (typo tolerance ≤ 2 chars TRÊN TOKEN, không phải full description) ═══
    # User typo: "PAY-123-PRO-M-X9K2" → "PAY-12-PRO-M-X9K2"
    if not tokens:
        # Không tìm được candidate token nào → skip Layer 2
        pass
    else:
        pending_24h = await db.fetch_pending_payments_last_24h()
        for p in pending_24h:
            for token in tokens:
                if levenshtein(p.ref_code, token) <= 2 \
                   and amount_matches(tx.amount, p.expected_amount):
                    return await confirm_match(p, tx, layer=2, confidence='medium',
                                               note=f'fuzzy match: token={token} vs ref={p.ref_code}')

    # ═══ Layer 3: AMOUNT + SHORT TIME WINDOW + STRICT UNIQUENESS ═══
    # Tightened: pending age ≤ 2h, exact amount, single candidate, source = platform bank
    pending_2h = await db.fetch_pending_payments_recent(hours=2)
    candidates = [
        p for p in pending_2h
        if tx.amount == p.expected_amount   # EXACT, no tolerance trong Layer 3
    ]
    # Extra safety: kiểm tra không có unmatched_payment cùng amount trong cửa sổ gần
    nearby_unmatched = await db.count_unmatched_recent(amount=tx.amount, hours=2)
    if len(candidates) == 1 and nearby_unmatched == 0:
        # Single pending + no recent unmatched same amount → match low-medium confidence
        # Notify admin để review post-hoc (vẫn auto-upgrade nhưng admin biết)
        result = await confirm_match(candidates[0], tx, layer=3, confidence='low')
        await notify_admin(f"ℹ️ Layer 3 match (amount-only): {tx.amount}đ → user {candidates[0].user_id}. Review nếu cần."
                          )
        return result
    elif len(candidates) >= 1:
        # Ambiguous (≥2 same amount) hoặc unmatched gần đó → manual review
        return await flag_review(candidates, tx, reason='ambiguous_or_risky')

    # ═══ Layer 4: UNMATCHED → admin review queue ═══
    await db.insert_unmatched_payment(tx)
    await notify_admin(
        f"⚠️ Unmatched payment: {tx.amount}đ from {tx.source}\n"
        f"Description: {tx.description}\n"
        f"/admin_resolve {tx.id}"
    )
    return MatchResult(matched=False, reason='no_match')
```

**Rule rationale (revised):**
- **Amount EXACT** (or ±1,000 VND hard cap): bank transfer VND luôn integer, không có FX/rounding ở mức %. ±5% là sai bản chất.
- **Layer 2 token extraction**: `levenshtein(p.ref_code, full_description)` luôn lớn vì description có nhiều text khác. Phải extract candidate token (regex `PAY-...`) trước, rồi compare token-with-token.
- **Layer 3 tightened constraints**:
  - pending age ≤ 2h (was 24h) — giảm cửa sổ đủ rộng cho user transfer chậm nhưng tránh ambiguity
  - exact amount only (no tolerance) — Layer 3 có rủi ro match nhầm cao, không cho slack
  - source = platform subscription bank only — đã handled ở routing (`/hook/{PLATFORM_TOKEN}`)
  - no other unmatched same amount in 2h — safety check tránh upgrade nhầm khi có 2 transfer cùng amount
  - confidence='low' + admin notification — admin có thể reverse trong vài phút nếu sai
- **Levenshtein ≤ 2 trên token** (not full string): 1-2 char typo acceptable, 3+ là rủi ro. Token max 24 chars nên Levenshtein meaningful.

---

## 5. User Flow & UX

### 5.1. Upgrade flow

```
User: /upgrade

Bot:
  💎 Upgrade plan
  
  Plan hiện tại: Free
  
  [✨ Pro $4/mo]  [✨ Pro $38.40/yr — 20% off]
  [💼 Business $9/mo]  [💼 Business $86.40/yr — 20% off]
  [❌ Cancel]

User chọn "Pro $4/mo"

Bot tạo pending_payment:
  ref_code = "PAY-{user_id}-PRO-M-{nonce4}"
  expected_amount = 100,000
  expires_at = NOW() + 24h

Bot generate 2 VietQR URLs qua vietqr.io API (services/qr_generator.py):
  primary_qr   = vietqr_url("VCB", "9999888877", 100000, ref, holder)
  secondary_qr = vietqr_url("TCB", "1234567890", 100000, ref, holder)

Bot gửi 5 message liên tiếp:

  Message 1 (text):
    💳 Pro Monthly — 100,000đ
    Quét QR dưới đây bằng app banking. Xác nhận tự động ≤ 1–5 phút.

  Message 2 (image attachment):
    [QR-VCB image]
    🟢 Lựa chọn 1: VCB 9999 8888 7777 (xác nhận ≤ 60s)

  Message 3 (image attachment):
    [QR-TCB image]
    🟡 Lựa chọn 2: TCB 1234 5678 9012 (xác nhận ≤ 5 phút)

  Message 4 (text — ref code standalone, long-press copy on Messenger):
    📋 Ref code (long-press để copy):
    PAY-123-PRO-M-X9K2

  Message 5 (text + buttons):
    ⏱ Hết hạn sau 24h.
    [🔄 Đổi plan]  [❌ Hủy]

> **Channel-specific rendering:** Telegram dùng `sendPhoto` với caption inline. Messenger dùng `attachment.image` + caption gửi message kế tiếp ([Messenger spec §6.6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-messenger-channel.md)). Cả 2 dùng cùng `messenger.send(user_id, {"type": "image", "url": ..., "caption": ...})` interface.

> **Fallback nếu vietqr.io down hoặc `ENABLE_VIETQR=false`:** Bot fallback text-only display (legacy version) — user vẫn upgrade được qua copy-paste, chỉ mất scan-to-pay UX:
>
> ```
> 💳 Pro Monthly — 100,000đ
>
> Chuyển khoản tới 1 trong 2 tài khoản:
>
> ┌─ Lựa chọn 1: VCB ────────┐
> │ STK: 9999 8888 7777      │
> │ Tên: <holder name>       │
> └──────────────────────────┘
>
> ┌─ Lựa chọn 2: TCB ────────┐
> │ STK: 1234 5678 9012      │
> │ Tên: <holder name>       │
> └──────────────────────────┘
>
> 📋 NỘI DUNG CHUYỂN KHOẢN: PAY-123-PRO-M-X9K2
>
> [📋 Copy ref] [🔄 Đổi plan] [❌ Hủy]
> ⏱ Hết hạn sau 24h.
> ```

> **Implementation detail:** [implementation-plan-payment-vietqr-email.md §4.7](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md) cho `handlers/upgrade.py` modify code.
```

### 5.2. Confirmation flow

**Happy path (Layer 1 match, ~95% case):**
```
User chuyển khoản 100,000đ với ND "PAY-123-PRO-M-X9K2"
[5-30 giây sau]
Bot:
  ✅ Đã nhận 100,000đ — Pro active!
  
  Hết hạn: 05/06/2026
  
  Tính năng mở khóa:
  • Unlimited transactions
  • 3 bank accounts
  • Unlimited history
  • /weekly + /report + /export
  
  Bot sẽ nhắc bạn 3 ngày trước khi hết hạn.
```

**Layer 2/3 match (medium confidence):**
```
Bot:
  ✅ Đã nhận 100,000đ — Pro active!
  
  Hết hạn: 05/06/2026
  
  💡 Lưu ý: ref bạn nhập có vài ký tự lệch ("PAY-12-PRO-M-X9K2"
  thay vì "PAY-123-PRO-M-X9K2"). Lần sau copy chính xác để xác
  nhận nhanh hơn.
```

**Layer 4 fail (unmatched):**
User không nhận confirmation tự động. Self-help flow:
```
User: /payment_help

Bot:
  Bạn vừa chuyển khoản nhưng chưa thấy bot xác nhận?
  
  Gửi screenshot biên lai chuyển khoản (chụp rõ amount + ND + ngày giờ).
  
  Founder sẽ review trong 24h.
  
  [📸 Gửi screenshot]
```
Admin review qua Telegram admin chat hoặc CLI tool, manually link unmatched_payment → user pending.

### 5.3. Recurring billing — Monthly

```
[3 ngày trước expiry]
Bot:
  ⏰ Pro của bạn hết hạn 05/06/2026 (3 ngày nữa).
  
  Để tiếp tục, chuyển khoản 100,000đ với nội dung:
  
     PAY-123-PRO-M-Y7L4
  
  Tới VCB · 9999 8888 7777 hoặc TCB · 1234 5678 9012.
  
  [📋 Copy ref]  [⬆️ Upgrade Annual (rẻ 20%)]  [⬇️ Downgrade Free]

[Day of expiry — nếu chưa pay]
Bot:
  ⚠️ Pro của bạn vừa hết hạn.
  
  Bạn vẫn dùng được Pro features trong 7 ngày grace period.
  Sau 12/06/2026 sẽ tự động về Free.
  
  Chuyển khoản giờ để tránh gián đoạn:
  
     PAY-123-PRO-M-Y7L4
  
  [📋 Copy ref]

[Day 7 sau expiry, vẫn chưa pay]
Bot:
  ↘ Plan đã downgrade về Free. Data đầy đủ giữ nguyên.
  
  Upgrade lại bất kỳ lúc nào: /upgrade
```

### 5.4. Recurring billing — Annual

Annual smoother nhiều — 1 transfer/năm, reminder 14 ngày trước expiry. Bot push annual ở mọi monthly upgrade message để giảm friction recurring.

---

## 6. State machine — pending_payment

```
              [user /upgrade]
                    │
                    ↓
              ┌─────────────┐
              │   pending   │
              └──────┬──────┘
                     │
        ┌────────────┼────────────┬─────────────┐
        ↓            ↓            ↓             ↓
   matcher      24h passed    user cancel   manual review
   confirms     no transfer                  inconclusive
        │            │            │             │
        ↓            ↓            ↓             ↓
   ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐
   │ matched │ │ expired │ │cancelled │ │manual_review│
   └─────────┘ └─────────┘ └──────────┘ └──────┬──────┘
                                                │
                                    ┌───────────┴──────────┐
                                    ↓                      ↓
                              admin confirms        admin rejects
                                    │                      │
                                    ↓                      ↓
                              ┌─────────┐            ┌─────────┐
                              │ matched │            │cancelled│
                              └─────────┘            └─────────┘
```

**Transitions:**
- `pending → matched`: matcher Layer 1-3 success → upgrade user.plan, set plan_expires_at
- `pending → expired`: APScheduler job mỗi giờ scan `WHERE expires_at < NOW() AND status = 'pending'`
- `pending → cancelled`: user bấm Cancel button trong upgrade flow
- `pending → manual_review`: matcher Layer 4 hoặc amount mismatch
- `manual_review → matched | cancelled`: admin command qua Telegram

---

## 7. Edge cases & failure modes

| # | Case | Handling |
|---|------|----------|
| 1 | User typo ref 1-2 char | Layer 2 fuzzy match (Levenshtein ≤ 2) → confirm + warn |
| 2 | User typo ref >2 char | Layer 3 amount-uniqueness fallback. Nếu vẫn không match → Layer 4 manual review |
| 3 | User chuyển nhầm amount nhỏ (vd 100,001 thay vì 100,000) | Hard-cap tolerance ≤ 1,000 VND → vẫn match Layer 1. Nếu env `PAYMENT_AMOUNT_TOLERANCE_VND=0` (strict) thì manual review |
| 4 | User chuyển amount lệch > 1,000 VND (vd 95,000 thay vì 100,000) | Layer 1 match ref nhưng flag amount_mismatch → manual review. Admin có thể credit chênh lệch hoặc refund |
| 5 | User chuyển 200,000đ cho Pro 100,000đ pending | Tương tự #4 (lệch > 1k). Admin có thể: (a) confirm Pro + 1 tháng credit, hoặc (b) refund chênh 100k |
| 6 | Bank truncate description (vd ref bị cắt còn "PAY-123") | Layer 1 fail. Layer 3 amount + recent pending → match nếu unique |
| 7 | 2 user cùng amount cùng plan trong 24h | Layer 1 vẫn distinguish (ref khác). Nếu cả 2 đều typo + amount giống → Layer 3 ambiguous → manual review |
| 8 | SePay outage 30 phút | Email parser fallback fire 1-5 phút sau (cùng webhook target). Có thể detect duplicate (cùng amount + thời gian gần) → dedup |
| 9 | User pay 2 lần trùng (network error tưởng failed → bấm pay lại) | First match → pending → matched. Second incoming có cùng ref → match.matched_at tồn tại → flag duplicate, refund hoặc credit cycle tiếp theo |
| 10 | User pay sau khi expires_at (>24h) | Pending status = 'expired'. Layer 1 match ref nhưng status invalid → flag manual review. Admin extend hoặc create new cycle |
| 11 | Refund request | Admin command `/refund {match_id}` → revoke plan, transfer back manually, mark match as refunded |
| 12 | Cross-source dedup (SePay + Email cùng catch 1 transfer) | **Same-source retry**: `dedup_key` UNIQUE skip silent. **Cross-source** (SePay + Email): handled bởi `pending_payments.status` state machine — source nhanh hơn confirm match → set status='matched'. Source thứ 2 đến muộn hơn check status, nếu != 'pending' thì skip silent (đã matched bởi source khác). Xem §4.1 cross-source dedup logic chi tiết. |
| 13 | Anti-fraud: kẻ xấu transfer 1đ với ref sai để probe | Amount < 5,000đ → reject, log spam |
| 14 | Bank account của platform bị compromise / phishing | Mitigation: dedicated bank cho subscription, monitor unusual outflow, 2FA on bank login |

---

## 8. Tax / Compliance — pre-launch blockers

> ⚠️ **CRITICAL:** Founder hiện chưa đăng ký hộ kinh doanh. Đây là **pre-launch blocker** cho Phase 6 deploy. Phải hoàn tất trước paying user đầu tiên.

### 8.1. Hộ kinh doanh registration

Lý do bắt buộc trước paying user đầu:
- Cá nhân nhận tiền subscription qua bank account → thu nhập từ kinh doanh
- Không đăng ký = vi phạm Luật Doanh nghiệp + Luật Quản lý thuế
- Nếu cơ quan thuế phát hiện: phạt + truy thu thuế ngược

**Action items (founder, ước 1-2 tuần lead time):**
- [ ] Đăng ký hộ kinh doanh tại UBND quận (hoặc online qua Cổng Dịch vụ Công)
- [ ] Mã ngành: 6201 (Lập trình máy tính) hoặc 6312 (Cổng thông tin) — chọn theo guide kế toán
- [ ] Đăng ký mã số thuế hộ kinh doanh
- [ ] Mở tài khoản bank dưới tên hộ kinh doanh (hoặc dùng tài khoản cá nhân với tax declaration)
- [ ] Setup khai thuế khoán hoặc thuế thực tế (consult kế toán dịch vụ ~500k-1tr/tháng)

### 8.2. VAT invoice obligation

Hộ kinh doanh có doanh thu < 100tr/năm → **không bắt buộc** xuất hóa đơn GTGT, có thể dùng hóa đơn bán lẻ. Doanh thu > 100tr/năm → bắt buộc đăng ký hóa đơn điện tử (VAT 10% hoặc thuế khoán).

MRR target $300-450 ≈ 7-11tr VND/tháng = 84-132tr/năm → **gần ngưỡng**. Cần plan transition lên hóa đơn điện tử khi đạt 100tr/năm.

**Action items (post-launch, khi MRR ổn định 50tr/năm):**
- [ ] Đăng ký dịch vụ hóa đơn điện tử (Misa, Viettel, FPT eInvoice...)
- [ ] Auto-generate hóa đơn cho mỗi paying user mỗi cycle (script)
- [ ] Email hóa đơn về user inbound email

### 8.3. PDPA + financial data

BRD §7 Risk #9 đã flag PDPA (Nghị định 13/2023). Payment data thêm tầng nhạy cảm:
- KHÔNG lưu số tài khoản user (ngay cả khi parse được từ description) — chỉ lưu amount + ref + dedup
- Audit log mọi truy cập `payment_matches` table
- User có thể request data export bao gồm payment history

### 8.4. Refund policy

PRD/BRD đã commit "7 ngày money-back, no questions asked" — phải honored. Refund:
- Manual transfer back từ platform's bank → user's bank
- Yêu cầu user cung cấp số tài khoản nhận refund (qua DM bot, không lưu DB)
- Track trong `payment_matches.status = 'refunded'`
- Reverse plan: set `users.plan = 'free'`, `plan_expires_at = NULL`

---

## 9. Acceptance Criteria

### 9.1. Functional

- [ ] User `/upgrade` → bot show 2 bank options + ref + copy button
- [ ] Pending payment created với ref unique (regex match `PAY-\d+-(PRO|BIZ)-(M|A)-[A-Z0-9]{4}`)
- [ ] Expires after 24h nếu chưa transfer (state → 'expired', user notified)
- [ ] User cancel button → state → 'cancelled' immediately
- [ ] SePay webhook hit `/hook/{PLATFORM_TOKEN}` → matcher confirms Layer 1 match → upgrade trong < 60 giây p95
- [ ] Email-detected payment (qua Postmark inbound) → match trong < 5 phút p95
- [ ] Annual upgrade flow giống monthly nhưng amount = 12 × price × 0.8

### 9.2. Matching robustness

- [ ] Layer 1 (exact ref) success rate ≥ 95% trong test với 100 mock transfer
- [ ] Layer 2 (fuzzy ≤ 2 char typo) success rate ≥ 80% trong test với 50 mock typo
- [ ] Layer 3 (amount unique) success rate ≥ 70% khi user quên ref hoàn toàn
- [ ] Layer 4 (manual review) ≤ 5% tổng transfer trong production
- [ ] Cross-source dedup: SePay + email cùng catch → chỉ 1 match record
- [ ] Amount mismatch >5% → flag, không auto-confirm
- [ ] Anti-fraud: transfer < 5,000đ rejected

### 9.3. Recurring billing

- [ ] Reminder fire 3 ngày trước `plan_expires_at` cho monthly user
- [ ] Reminder fire 14 ngày trước expiry cho annual user
- [ ] Grace period 7 ngày sau expiry — user vẫn dùng Pro features
- [ ] Auto-downgrade Free sau grace period
- [ ] Reminder message luôn include pre-filled ref + push annual upsell

### 9.4. Compliance

- [ ] Hộ kinh doanh đã đăng ký trước Phase 6 deploy
- [ ] Bank account dedicated cho subscription (không trộn với personal)
- [ ] PDPA: không lưu số TK user, audit log access `payment_matches`
- [ ] Refund flow tested với 1 mock case
- [ ] Tax obligation tracking (monthly revenue log)

### 9.5. Admin tools

- [ ] CLI hoặc Telegram admin command để:
  - List unmatched_payments pending review
  - Manually link unmatched_payment → pending_payment
  - Refund (revoke plan + log)
  - Extend pending payment expiry
  - Search payment by user_id or ref

### 9.6. Observability

- [ ] Analytics events thêm vào (PRD §6):
  - `payment_initiated` — user `/upgrade` chọn plan
  - `payment_matched` — matcher confirm, props: layer, confidence, source
  - `payment_expired` — pending hết 24h chưa transfer
  - `payment_unmatched` — incoming không match nào
  - `payment_refunded` — admin refund
  - `subscription_renewed` — recurring transfer match
  - `subscription_expired_grace` — vào grace period
  - `subscription_downgraded` — sau grace period auto-Free

---

## 10. Sub-tasks & effort estimate

| # | Task | Effort | Phase |
|---|------|--------|-------|
| 10.1 | DB migration: `pending_payments`, `payment_matches`, `unmatched_payments` + ALTER `users` | 0.5 ngày | Phase 6.1 |
| 10.2 | `services/payment_matcher.py` — 4-layer fuzzy algorithm | 2-3 ngày | Phase 6.1 |
| 10.3 | `handlers/upgrade.py` — bot `/upgrade` UX, pending creation, payment instructions | 1-2 ngày | Phase 6.2 |
| 10.4 | Webhook routing distinguish: `/hook/{user_token}` vs `/hook/{PLATFORM_TOKEN}` | 0.5 ngày | Phase 6.1 |
| 10.5 | Email backup setup: forwarding rule trong owner Gmail → Postmark `/inbound/{PLATFORM_TOKEN}` | 0.5 ngày + DNS time | Phase 6.1 |
| 10.6 | Scheduled jobs: expire pending (mỗi giờ), reminder 3 days monthly + 14 days annual, grace period downgrade | 1 ngày | Phase 6.2 |
| 10.7 | Admin CLI / Telegram commands cho manual review + refund | 1-2 ngày | Phase 6.2 |
| 10.8 | End-to-end test với real bank transfer (founder's 2 banks) | 1-2 ngày | Phase 6.3 |
| 10.9 | Documentation: runbook cho admin (manual review workflow, refund process) | 0.5 ngày | Phase 6.3 |
| 10.10 | Tax/compliance: hộ kinh doanh registration | **1-2 tuần lead time, parallel** | Pre-Phase 6 |
| 10.11 | **VietQR URL builder + 2-channel `send_image()`** — `services/qr_generator.py` compose URL string + `BaseSender.send_image()` extension + `TelegramSender` (sendPhoto) + `MessengerSender` (attachment.image với quirks: no inline caption, MESSAGE_TAG branching) + modify `handlers/upgrade.py` render 5-message structure | **2 ngày** | Phase 6.2 |
| 10.12 | **Email parallel path implementation** — `parsers/email_platform_tcb.py` (reuse `parsers/tcb.py` + account filter) + `handlers/payment_inbound.py` + Postmark routing + Gmail forwarding rule + 5+ TCB email fixture tests + cross-source dedup race E2E + edge cases (wrong account, typo ref, fallback feature flag) + real-bank E2E | **2-3 ngày** | Phase 6.2 |

**Tổng dev effort: ~12-16 ngày** (Phase 6 timeline tuần 10-12 = 14-20 ngày work, fits với buffer).

> **Detail breakdown 10.11 + 10.12 (4 nominal day + 1 buffer = 3-5 day range):** [implementation-plan-payment-vietqr-email.md §5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md). Effort range phản ánh integration/test surface — code chính ngắn nhưng cross-source dedup race + Messenger attachment quirks + Postmark first-time setup tốn 3-5 ngày thực tế.


**Critical path: hộ kinh doanh registration** — nếu chưa start, blocker pre-launch tháng 9/2026. Đề xuất start ngay sau khi sign off feature spec này.

---

## 11. Risks & Mitigation

| # | Risk | Mức độ | Mitigation |
|---|------|--------|-----------|
| 1 | **Hộ kinh doanh không kịp đăng ký** trước launch | **Cao** | Start ngay tuần này. Có alternative: ủy quyền cho người thân đã có hộ kinh doanh nhận hộ trong giai đoạn đầu, sau đó chuyển sang khi founder hoàn tất đăng ký |
| 2 | Layer 1 match rate < 95% target | Trung bình | Iterative regex tuning sau 100 real payments. Add fixture-based test khi có data |
| 3 | Banks truncate description tới mức ref bị cắt | Trung bình | Test với 2 platform banks (VCB + TCB) trước launch để xem truncation behavior. Nếu critical → shorten ref format |
| 4 | User confused vì 2 bank options + ref string | Trung bình | UX test với 5-10 beta user. Nếu confusion cao → default 1 bank, advanced toggle xem option 2 |
| 5 | Recurring monthly churn cao do friction | **Cao** | Push annual mạnh ở mọi upgrade message. Reminder 3 ngày + grace 7 ngày. Track monthly renewal rate, nếu < 60% → consider PayOS Phase 2 |
| 6 | Spam/fraud transfer (kẻ xấu chuyển 1đ với ref sai để DDoS matcher) | Thấp | Min amount 5,000đ. Rate limit incoming `/hook/PLATFORM_TOKEN` 100/min |
| 7 | SePay account của platform bị suspend (vi phạm ToS) | Thấp | Email backup đã có. Đảm bảo platform's SePay usage compliant |
| 8 | Tax audit phát hiện chưa kê khai đầy đủ | Trung bình | Hire kế toán dịch vụ từ tháng đầu tiên có paying user. Lưu mọi receipt/invoice |
| 9 | Bank của platform thay đổi format email notification | Trung bình | Email parser cho payment dùng cùng plugin pattern, chỉ cần update regex (không touch core) |
| 10 | Admin (founder) overload manual review queue | Trung bình | Layer 1-3 phải >95% auto-resolve. Nếu Layer 4 > 10/ngày → algorithm cần tune. Beta phase OK 1-5/ngày solo founder handle |

---

## 12. Definition of Done

- [ ] Tất cả AC §9 pass
- [ ] DB migration applied to staging + production
- [ ] Hộ kinh doanh đã đăng ký, mã số thuế active
- [ ] 2 bank account dedicated setup, SePay linked với 1 bank, email forwarding linked với cả 2
- [ ] End-to-end test: founder transfer thử 5 lần với mỗi layer (exact, fuzzy, amount-only, mismatch, expired) — tất cả handle đúng
- [ ] Admin runbook documented (cách handle unmatched, refund, manual link)
- [ ] PRD §F06 + BRD §5.2.4 + TDD §3 cross-ref tới spec này
- [ ] Beta 5-10 user completes upgrade flow without manual intervention
- [ ] First real paying user successful end-to-end (founder hoặc bạn bè test)

---

## 13. Cross-doc updates needed

Spec này standalone nhưng cần thêm references vào:

| Doc | Section | Thay đổi |
|-----|---------|----------|
| BRD §5.2.4 Payment | Add detail | Bank transfer detection mechanism = SePay primary + Email backup, link tới spec này |
| PRD §F06 Pricing | Add subsection | Payment flow UX summary, link tới spec |
| PRD §6 Analytics | Add events | 8 payment events từ §9.6 |
| TDD §3 Endpoints | Add row | `POST /hook/{PLATFORM_TOKEN}` distinguishable |
| TDD §2.1 DDL | Add tables | `pending_payments`, `payment_matches`, `unmatched_payments` |
| Feature spec refactor §3.3 | Add AC | Webhook routing distinguish PLATFORM_TOKEN |
| README Quick links | Add line | Link tới spec này |

---

## 14. Open questions (cần resolve trước implement)

1. **Ref nonce length**: 4 char ([A-Z0-9] = 36^4 ≈ 1.6M combinations) — collision unlikely nhưng có thể collision trong 24h pending window nếu nhiều user. Đề xuất: enforce UNIQUE constraint, regenerate nếu collision (rare).
2. **Bank account display order**: random, by user preference, hay alphabet? Đề xuất: VCB primary first (highest detection speed), TCB second. Có thể A/B test sau.
3. **Pending payment timeout**: 24h. Đủ cho user nhưng nếu user transfer thứ 7 đêm, ngân hàng delay tới Mon → có thể miss window. Đề xuất: 48h thay 24h cho safety, accept slight risk admin overhead.
4. **Annual reminder cadence**: 14 ngày trước OK hay cần reminder ở 7 + 3 + 1 ngày? Đề xuất: 14 + 3 + 1 (3 lần) — user có lead time mà không spam.
5. **Refund policy 7 ngày tính từ payment hay subscription start**: BRD chưa rõ. Đề xuất: từ payment_matches.matched_at để clear.

---

## 15. References

- [BRD v2.9.0 §5.2.4 Payment options](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md)
- [PRD v1.6.0 §F06 Pricing](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md)
- [TDD v1.6.0 §3 API Design + §5.2 env vars](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)
- [Feature Spec Refactor SaaS §2.4 Email parser plugin](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-refactor-saas.md)
- [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-messenger-channel.md)
- [Implementation Plan VietQR + Email Parallel](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md)
- [SePay docs](https://sepay.vn) — webhook payload structure
- [Postmark Inbound docs](https://postmarkapp.com/developer/webhooks/inbound-webhook)
- [VietQR.io API docs](https://www.vietqr.io/danh-sach-api/)
- Cổng Dịch vụ Công (đăng ký hộ kinh doanh online)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial spec — payment via bank transfer + auto-detect via SePay primary + Email backup. Cover: 4-layer matching algorithm, recurring billing (monthly + annual), tax/compliance pre-launch checklist, 14 edge cases. Effort estimate 8-12 ngày dev (Phase 6) + 1-2 tuần parallel cho hộ kinh doanh registration. |
| v1.1.0 | 2026-05-05 | **Foundation fixes from review:** (1) **Amount tolerance**: bỏ ±5% (sai bản chất bank transfer VND) → exact match (or ±1,000 VND hard cap). Lệch >1k → manual review, không auto-confirm. (2) **Layer 2 fuzzy**: extract PAY-like token từ description trước (`extract_pay_tokens`), rồi Levenshtein token-vs-token. Trước đó so full description vs ref → luôn fail. (3) **Layer 3 tightened**: pending age 24h → 2h, exact amount only (no tolerance), require no nearby unmatched same amount, confidence='low' + admin notification. (4) **Schema fixes**: drop `pending_payments.matched_match_id` (circular FK weak); add `payment_matches.status` ('matched'|'refunded'|'credited'|'voided') + `refunded_at` + `refund_notes`; replace `UNIQUE(source, source_ref_code)` (NULL-unsafe) bằng `dedup_key VARCHAR(128) UNIQUE` = sha256 hash. (5) **Compliance**: thêm note placeholder `<holder name>` = legal entity, không hardcode personal name in docs. (6) Sync version refs lên BRD v2.7.0 / PRD v1.5.0 / TDD v1.5.0. |
| v1.2.0 | 2026-05-05 | **Round-2 fixes from review:** (1) **`dedup_key` semantics correct**: clarify same-source retry dedup ONLY (KHÔNG cross-source), update formula prefer `source_ref_code` thay vì hash amount+desc (more deterministic for SePay retry). (2) **Cross-source dedup mechanism documented**: handled qua `pending_payments.status` state machine + row lock trong `confirm_match()`. Source thứ 2 đến muộn check status != 'pending' → skip silent. (3) **Edge cases #3, #4, #5, #12 rewritten** consistent với hard-cap ±1k VND + new dedup design. (4) **Sync stale refs**: BRD v2.7.0 → v2.7.1, TDD v1.5.0 → v1.5.1 ở header + bottom References. |
| v1.3.0 | 2026-05-07 | **VietQR via vietqr.io public image URL + email parallel path implementation:** (1) §2.4 mới — VietQR via vietqr.io **public image URL** (KHÔNG self-host, KHÔNG self-generate — image rendered server-side bởi vietqr.io, banking app fetch URL khi scan), BANK_BIN mapping cho top 10 banks VN, tradeoff matrix (privacy/dependency/rate limit), fallback nếu service down, future migration tới true self-host EMVCo encoder defer Phase 7+. (2) §2.3 expand — link tới impl plan §4.5–4.6 cho parser/handler code. (3) §5.1 upgrade flow — replace text-only display bằng 5-message structure (header text + 2 QR images + ref code standalone + action buttons). Thêm channel-specific rendering note + fallback text-only mode. (4) §10 sub-tasks thêm 10.11 (VietQR URL builder + 2-channel `send_image()`, 2 ngày) + 10.12 (email parallel implementation + cross-source dedup E2E + edge cases, 2-3 ngày). Tổng effort 8-12 → **12-16 ngày** (range phản ánh integration/test surface — không phải 10-14). Schema `payment_matches.source` + `unmatched_payments.source` widen `VARCHAR(16)` → `VARCHAR(32)` cần migration vì `'email_tcb_platform'` 18 chars. (5) §15 references thêm Messenger Spec, Impl Plan VietQR, vietqr.io API docs. (6) Header refs bumped BRD v2.8.0 → v2.9.0, PRD v1.5.0 → v1.6.0, TDD v1.5.2 → v1.6.0. |
