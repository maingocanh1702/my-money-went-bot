# Implementation Plan — VietQR via Public Image URL + Email-Based Parallel Payment Path

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Mục đích:** Add 2 enhancement vào subscription payment flow MVP — (1) VietQR QR code generation **qua vietqr.io public image URL** (third-party hosted, free) cho UX scan-to-pay, (2) Email-based parallel payment path qua TCB/MB secondary bank account (giảm phụ thuộc SePay, tăng redundancy + bank choice).
>
> **Wording note:** Plan này KHÔNG phải "self-host" hay "self-generate" QR — thực chất chỉ là embed image URL trỏ tới `vietqr.io` (public service). True self-generation (encode EMVCo TLV + render PNG offline) là Option B defer Phase 7+. Tradeoff: $0 cost + 0 dev time, nhưng leak ref code/account/amount tới vietqr.io + dependency lên uptime của họ.
> **Phase liên quan:** MVP Phase 6 Tuần 11 (build payment) — thêm **3–5 ngày dev** (không phải 2 — integration/test surface lớn: QR + 2 channel adapter + Messenger image quirks + email parser + Postmark routing + cross-source dedup E2E + reconciliation edge cases). Fit Tuần 11 với ngày deploy đẩy sang Tuần 12, không kéo dài timeline 16 tuần MVP.
> **Tham chiếu:** [BRD v2.9.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) §5.2.4 · [PRD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md) §3.6 F06 · [TDD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) §3.1 endpoint routing + §5.2 env vars · [Feature Spec Payment v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_payment.md) §2.4 + §5.1 · [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md) §6.6 · [Implementation Plan 500 users v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-500-users-and-more.md)

---

## 1. Executive Summary

### 1.1. Problem statement

Spec payment hiện tại có 2 gap:

**Gap 1 — Không có QR scan-to-pay.** `feature_payment.md` §5.1 hiện chỉ display text plain (số tài khoản + ref code), user gõ tay/copy paste vào mobile banking. Mỗi khâu copy-paste = 1 chỗ user có thể nhầm → tăng manual review queue, giảm conversion upgrade.

**Gap 2 — Email-based parallel path chưa implemented.** Spec §2.2 + §2.3 đã design dual-bank approach (VCB primary qua SePay + TCB/MB secondary qua email parsing) nhưng code chưa build. Hệ quả: user chỉ có 1 lựa chọn chuyển khoản (VCB), 100% phụ thuộc SePay account uptime.

### 1.2. Solution overview

Build cùng lúc trong Phase 6 Tuần 11:

1. **VietQR via vietqr.io public image URL** (Option A) — gọi `https://img.vietqr.io/image/{BIN}-{account}-compact2.png?...` để có URL trỏ tới image render bởi vietqr.io. Bot embed URL này vào outbound message qua `send_image()` adapter — banking app scan QR rồi pre-fill account + amount + ref. KHÔNG self-host, KHÔNG self-encode EMVCo. Tradeoff bake-in §11 risk #1 + #2.
2. **Email-based parallel path** qua TCB/MB secondary bank — owner setup forwarding rule → Postmark `/inbound/{PLATFORM_TOKEN}` → email parser plugin → feed vào `payment_matcher` (cùng service xử lý SePay).

User experience kết quả: Bot upgrade gửi 2 QR side-by-side, user scan QR nào cũng được, match auto upgrade tương ứng (SePay ≤60s, email ≤5min).

### 1.3. Why now (build trong MVP Phase 6)

- **Cost saving:** SePay charge ~50–100k/tháng cho gói Pro. Dual-bank với 1 bank email-only tiết kiệm ~600k–1.2tr/năm.
- **Redundancy:** Nếu SePay account suspend (BRD risk #2 in payment spec), email path vẫn work — không lose subscription revenue.
- **Bank coverage:** User không có VCB (vd dùng MB/TCB chính) vẫn pay được mà không phải mở account mới.
- **Conversion:** VietQR scan-to-pay giảm friction copy-paste — 1 thao tác thay vì 3 (copy STK + amount + ref).
- **Effort:** **3–5 ngày dev** — code chính ngắn (~250 LOC) nhưng integration/test surface lớn: 2 channel adapter `send_image()` với Messenger quirks (no inline caption, attachment shape khác), email parser cho founder bank (account filter), Postmark routing, cross-source dedup race test, real-bank E2E. Fit vào Phase 6 Tuần 11 (đẩy 1-2 ngày deploy/admin tools sang Tuần 12) không impact timeline 16 tuần.

### 1.4. Scope summary

| Item | In scope | Out of scope |
|---|---|---|
| vietqr.io URL embed (Option A) | ✅ | — |
| Self-host VietQR EMVCo encoder (Option B) | — | Defer Phase 7+ nếu volume >500 hoặc privacy concern |
| Email parser cho founder bank (TCB/MB) | ✅ | — |
| Multi-tenant founder bank (>1 platform) | — | Single-tenant SaaS, 1 platform = 1 founder |
| User-facing QR display Telegram + Messenger | ✅ | — |
| Generate QR cho user transaction tracking | ❌ | Đây là subscription payment only |
| Reuse user-facing email parser (TCB/Cake) cho founder context | ✅ | — |

---

## 2. Architecture Diff

### 2.1. Current state (post Phase 6 base build)

```
User /upgrade Pro
    │
    ▼
Bot create pending_payments (ref = PAY-...)
    │
    ▼
Bot reply text:
    "STK VCB: 9999...  /  TCB: 1234...
     Tên: <holder>
     ND: PAY-..."
    │
    ▼
User mở app banking → gõ tay STK + amount + ref → confirm
    │
    ▼
Tiền vào VCB (SePay-linked)
    │
    ▼
SePay webhook /hook/{PLATFORM_TOKEN}
    │
    ▼
payment_matcher Layer 1 → upgrade ≤60s
```

**Limitation:** TCB không có path implemented. User chuyển TCB → email founder → silent fail (chưa parse). Force user dùng VCB only.

### 2.2. Target state (after this plan)

```
User /upgrade Pro
    │
    ▼
Bot create pending_payments (ref = PAY-...)
    │
    ▼
Bot generate 2 VietQR URLs (qua vietqr.io)
    │
    ▼
Bot send 3 message:
    1. Image attachment QR-VCB + caption "Lựa chọn 1: VCB (≤60s)"
    2. Image attachment QR-TCB + caption "Lựa chọn 2: TCB (≤5 phút)"
    3. Text "Ref code (long-press để copy): PAY-..."
    │
    ├── User scan QR-VCB ──→ tiền vào VCB ──→ SePay webhook ──→ Layer 1 match ──→ ≤60s
    │
    └── User scan QR-TCB ──→ tiền vào TCB ──→ TCB email founder
                                              │
                                              ▼
                                    Forwarding rule: payment@in.fintrack.app
                                              │
                                              ▼
                                    Postmark /inbound/{PLATFORM_TOKEN}
                                              │
                                              ▼
                                    parsers/email_platform_tcb.py
                                              │
                                              ▼
                                    payment_matcher Layer 1 → ≤5 phút
```

Hai path **share cùng `pending_payments`** + cùng `payment_matcher` service. Dedup tự động qua `pending_payments.status` state machine.

### 2.3. Components diff

| Layer | Current | Target | Change |
|---|---|---|---|
| `pending_payments` schema | Đã có | Đã có | No change |
| `payment_matches` schema | `source VARCHAR(16)`, enum: `'sepay'` | `source VARCHAR(32)`, enum: `'sepay' \| 'email_tcb_platform' \| 'email_mb_platform'` | **Requires DDL widen to VARCHAR(32)** — see §3. `'email_tcb_platform'` = 18 chars > 16. Same fix cho `unmatched_payments.source`. |
| `services/qr_generator.py` | None | New file ~50 LOC | NEW |
| `services/channels/base.py` | `send_text`, `send_picker` | `+ send_image(user, url, caption)` | EXTEND |
| `services/channels/telegram.py` | sendMessage | `+ sendPhoto` impl | EXTEND |
| `services/channels/messenger.py` | message text | `+ attachment.image` impl | EXTEND |
| `parsers/email_platform_tcb.py` | None | New file ~30 LOC (reuse `parsers/tcb.py`) | NEW |
| `parsers/email_platform_mb.py` | None | New file ~30 LOC | NEW (optional, MVP có thể chỉ TCB trước) |
| `handlers/upgrade.py` | Display text only | + generate 2 QR + send images | MODIFY |
| `handlers/payment_inbound.py` | Stub for `/inbound/{PLATFORM_TOKEN}` | Implement: dispatch to email_platform_* parsers | IMPLEMENT |
| `payment_matcher` service | Handle source `sepay` | Handle additional `email_tcb_platform`, `email_mb_platform` | EXTEND (logic identical, just new source label) |
| `config.py` env | Packed string `PLATFORM_BANK_PRIMARY_ACCOUNT="VCB 9999888877"` + `*_HOLDER` | **Tách atomic per bank**: `*_CODE` + `*_ACCOUNT_NUMBER` + `*_HOLDER_NAME` (3 vars × 2 bank = 6 vars total). Bank BIN không phải env — lookup từ `BANK_BIN` dict trong `services/qr_generator.py`. | REFACTOR |

---

## 3. Schema impact

**1 DDL change required** — width của `source` column quá ngắn cho new source labels:

```sql
-- Migration: 00X_widen_payment_source.sql
ALTER TABLE payment_matches    ALTER COLUMN source TYPE VARCHAR(32);
ALTER TABLE unmatched_payments ALTER COLUMN source TYPE VARCHAR(32);
```

Lý do: `'email_tcb_platform'` = 18 chars, `'email_mb_platform'` = 17 chars, vượt VARCHAR(16) limit ban đầu của payment spec → INSERT fail hoặc truncate silent.

Other tables không thay đổi:
- `pending_payments` — ref_code unique, expires_at, status — đủ cover cả 2 path
- Cấu trúc `payment_matches` + `unmatched_payments` còn lại — không thay đổi

**Migration timing:** Ship cùng schema initial Phase 1 nếu chưa apply, hoặc trước Day 2 task 10.12 (email parallel implementation). Backfill: None (Phase 6 fresh build).

---

## 4. Code Structure

### 4.1. `services/qr_generator.py` — NEW

```python
"""
VietQR public image URL builder.

This module does NOT self-generate QR — it composes a URL pointing to
vietqr.io's free public image service. The QR PNG is rendered server-side
by vietqr.io and fetched by the user's banking app when scanning.

Tradeoffs vs true self-host (Option B, defer Phase 7+):
  - Pros: $0 cost, 0 dev time for EMVCo encoder, reliable rendering
  - Cons: leaks ref_code/account/amount to vietqr.io (third-party privacy),
    dependency on vietqr.io uptime, rate limit (~30 req/min/IP)

Bank BIN reference: NAPAS national IDs.
Spec: https://www.vietqr.io/danh-sach-api/
"""
from urllib.parse import quote

# NAPAS bank BIN — top 6 banks Vietnam (MVP)
BANK_BIN = {
    "VCB":  "970436",  # Vietcombank
    "TCB":  "970407",  # Techcombank
    "MB":   "970422",  # MB Bank
    "ACB":  "970416",  # ACB
    "STB":  "970403",  # Sacombank
    "BIDV": "970418",  # BIDV
    "VTB":  "970415",  # VietinBank
    "VPB":  "970432",  # VPBank
    "TPB":  "970423",  # TPBank
    "CAKE": "546034",  # Cake (VPBank fintech)
}

VIETQR_TEMPLATE = "compact2"  # other: "qr_only", "compact", "print"


def vietqr_url(
    bank: str,
    account: str,
    amount: int,
    ref_code: str,
    holder: str,
) -> str:
    """
    Generate vietqr.io image URL.

    Args:
        bank: Bank code, must be in BANK_BIN. Raises KeyError otherwise.
        account: Account number (digits only, no spaces).
        amount: VND integer (no decimal).
        ref_code: Transfer description / payment ref code.
        holder: Account holder name (uppercase, no diacritics recommended).

    Returns:
        URL string. Embed via send_image(url=..., caption=...).

    Example:
        >>> vietqr_url("VCB", "9999888877", 96000, "PAY-42-PRO-M-X9K2", "NGUYEN VAN A")
        'https://img.vietqr.io/image/970436-9999888877-compact2.png?amount=96000&addInfo=PAY-42-PRO-M-X9K2&accountName=NGUYEN%20VAN%20A'
    """
    if bank not in BANK_BIN:
        raise KeyError(f"Unsupported bank: {bank!r}. Add to BANK_BIN.")

    bin_code = BANK_BIN[bank]
    base = f"https://img.vietqr.io/image/{bin_code}-{account}-{VIETQR_TEMPLATE}.png"
    params = (
        f"?amount={amount}"
        f"&addInfo={quote(ref_code, safe='')}"
        f"&accountName={quote(holder, safe='')}"
    )
    return base + params
```

### 4.2. `services/channels/base.py` — EXTEND

```python
class BaseSender(ABC):
    @abstractmethod
    async def send_text(self, user, text: str, reply_markup=None, tag=None) -> None: ...

    @abstractmethod
    async def send_picker(self, user, prompt: str, options) -> None: ...

    @abstractmethod
    async def send_image(self, user, image_url: str, caption: str | None = None, tag=None) -> None:
        """
        Send remote image. Both adapters must support.

        Telegram impl: sendPhoto with photo=URL
        Messenger impl: attachment.type=image with payload.url=URL
        """
        ...
```

### 4.3. `services/channels/telegram.py` — EXTEND

```python
class TelegramSender(BaseSender):
    async def send_image(self, user, image_url: str, caption=None, tag=None):
        await self._call_api("sendPhoto", {
            "chat_id": user.chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "Markdown",
        })
```

### 4.4. `services/channels/messenger.py` — EXTEND

```python
class MessengerSender(BaseSender):
    async def send_image(self, user, image_url: str, caption=None, tag=None):
        # Send image first (Messenger doesn't support caption with image attachment)
        await self._send_attachment(user, "image", image_url, tag=tag)
        if caption:
            await self.send_text(user, caption, tag=tag)

    async def _send_attachment(self, user, attach_type, url, tag=None):
        body = {
            "recipient": {"id": user.channel_user_id},
            "message": {
                "attachment": {
                    "type": attach_type,
                    "payload": {"url": url, "is_reusable": False},
                }
            },
        }
        if tag:
            body["messaging_type"] = "MESSAGE_TAG"
            body["tag"] = tag
        else:
            body["messaging_type"] = "RESPONSE"
        # POST graph.facebook.com/me/messages
```

### 4.5. `parsers/email_platform_tcb.py` — NEW

```python
"""
Email parser cho founder's TCB platform bank account.
Reuse logic từ parsers/tcb.py (vốn build cho user transaction parsing).

Differences:
- Sender domain whitelist same (`automail@techcombank.com.vn`, etc.)
- Output `_source = 'email_tcb_platform'` thay vì `email_tcb`
- Account number filter: chỉ parse email cho founder's account number (env PLATFORM_BANK_SECONDARY_ACCOUNT)
  → tránh parse nhầm nếu founder có >1 TCB account.
"""
from parsers.tcb import _parse_tcb as _parse_user_tcb
import os


def parse_platform_tcb_email(from_addr, subject, body, date) -> dict | None:
    parsed = _parse_user_tcb(subject, body, date)
    if parsed is None:
        return None

    # Verify account number matches platform's secondary
    expected_acc = os.environ["PLATFORM_BANK_SECONDARY_ACCOUNT"].split()[-1]  # "TCB 1234..."
    parsed_acc = parsed.get("account_last_4") or ""

    if expected_acc and not expected_acc.endswith(parsed_acc):
        # Email không phải tài khoản platform — skip silent
        return None

    parsed["_source"] = "email_tcb_platform"
    return parsed
```

### 4.6. `handlers/payment_inbound.py` — IMPLEMENT

```python
"""
Handler cho POST /inbound/{PLATFORM_TOKEN} — email backup path cho subscription payment.

Routes email từ founder's bank → email_platform_* parser → payment_matcher.
"""
from parsers.email_platform_tcb import parse_platform_tcb_email
# from parsers.email_platform_mb import parse_platform_mb_email   # Phase 7+


SENDER_TO_PARSER = {
    "automail@techcombank.com.vn": parse_platform_tcb_email,
    "ebank@techcombank.com.vn": parse_platform_tcb_email,
    # "automail@mbbank.com.vn": parse_platform_mb_email,   # Phase 7+ if MB added
}


async def handle_platform_inbound(payload: dict):
    from_addr = payload["FromFull"]["Email"].lower()
    subject = payload["Subject"]
    body = payload.get("TextBody") or payload.get("HtmlBody", "")
    date = payload.get("Date", "")

    parser = SENDER_TO_PARSER.get(from_addr)
    if parser is None:
        # Domain match fallback
        domain = from_addr.split("@")[-1]
        if "techcombank" in domain:
            parser = parse_platform_tcb_email

    if parser is None:
        log.warning(f"[platform_inbound] unknown sender: {from_addr}")
        return

    parsed = parser(from_addr, subject, body, date)
    if parsed is None:
        log.info(f"[platform_inbound] non-transaction or wrong account: {subject!r}")
        return

    # Feed vào payment_matcher (cùng service handle SePay)
    await payment_matcher.match(parsed)
```

### 4.7. `handlers/upgrade.py` — MODIFY

```python
async def show_payment_instructions(user, pending: PendingPayment):
    # Env vars tách rạch ròi per bank — KHÔNG packed string + .split()
    # vì holder name có space (vd "NGUYEN VAN A") sẽ break.
    primary_code         = os.environ["PLATFORM_BANK_PRIMARY_CODE"]            # "VCB"
    primary_account      = os.environ["PLATFORM_BANK_PRIMARY_ACCOUNT_NUMBER"]  # "9999888877"
    primary_holder       = os.environ["PLATFORM_BANK_PRIMARY_HOLDER_NAME"]     # "NGUYEN VAN A"
    secondary_code       = os.environ["PLATFORM_BANK_SECONDARY_CODE"]
    secondary_account    = os.environ["PLATFORM_BANK_SECONDARY_ACCOUNT_NUMBER"]
    secondary_holder     = os.environ["PLATFORM_BANK_SECONDARY_HOLDER_NAME"]

    primary_qr = vietqr_url(
        bank=primary_code,
        account=primary_account,
        amount=pending.expected_amount,
        ref_code=pending.ref_code,
        holder=primary_holder,
    )
    secondary_qr = vietqr_url(
        bank=secondary_code,
        account=secondary_account,
        amount=pending.expected_amount,
        ref_code=pending.ref_code,
        holder=secondary_holder,
    )

    plan_label = f"{pending.plan.title()} {pending.period.title()}"
    amount_vnd = f"{pending.expected_amount:,}đ"
    primary_label   = f"{primary_code} {primary_account}"
    secondary_label = f"{secondary_code} {secondary_account}"

    # 1. Header text
    await messenger.send(user.id, {
        "type": "text",
        "text": f"💳 *{plan_label}* — {amount_vnd}\n\nQuét QR dưới đây bằng app banking. Xác nhận tự động ≤ 1–5 phút sau khi tiền về.",
    })

    # 2. Primary QR
    await messenger.send(user.id, {
        "type": "image",
        "url": primary_qr,
        "caption": f"🟢 *Lựa chọn 1: {primary_label}* (xác nhận ≤ 60s)",
    })

    # 3. Secondary QR
    await messenger.send(user.id, {
        "type": "image",
        "url": secondary_qr,
        "caption": f"🟡 *Lựa chọn 2: {secondary_label}* (xác nhận ≤ 5 phút)",
    })

    # 4. Ref code as standalone (for long-press copy on Messenger)
    await messenger.send(user.id, {
        "type": "text",
        "text": f"📋 Ref code (long-press để copy):\n\n`{pending.ref_code}`",
    })

    # 5. Action buttons
    await messenger.send(user.id, {
        "type": "picker",
        "prompt": "⏱ Hết hạn sau 24h",
        "options": [
            {"label": "🔄 Đổi plan", "callback_data": "upgrade_change_plan"},
            {"label": "❌ Hủy", "callback_data": f"upgrade_cancel:{pending.id}"},
        ],
    })
```

### 4.8. `config.py` env vars — EXTEND

```python
# config.py — atomic env vars per bank, no packed strings.
# Holder name có space (vd "NGUYEN VAN A") nên KHÔNG dùng "VCB 9999888877" rồi .split().

# Primary bank (SePay-linked)
PLATFORM_BANK_PRIMARY_CODE           = os.environ["PLATFORM_BANK_PRIMARY_CODE"]             # "VCB"
PLATFORM_BANK_PRIMARY_ACCOUNT_NUMBER = os.environ["PLATFORM_BANK_PRIMARY_ACCOUNT_NUMBER"]   # "9999888877"
PLATFORM_BANK_PRIMARY_HOLDER_NAME    = os.environ["PLATFORM_BANK_PRIMARY_HOLDER_NAME"]      # "NGUYEN VAN A"

# Secondary bank (email-only)
PLATFORM_BANK_SECONDARY_CODE           = os.environ["PLATFORM_BANK_SECONDARY_CODE"]           # "TCB"
PLATFORM_BANK_SECONDARY_ACCOUNT_NUMBER = os.environ["PLATFORM_BANK_SECONDARY_ACCOUNT_NUMBER"] # "1234567890"
PLATFORM_BANK_SECONDARY_HOLDER_NAME    = os.environ["PLATFORM_BANK_SECONDARY_HOLDER_NAME"]    # "NGUYEN VAN A" (có thể khác)

# Bank BIN không phải env var — auto-lookup từ BANK_BIN dict trong services/qr_generator.py
# theo `*_CODE` value. Tránh duplicate state giữa env và code, single source of truth ở dict.
```

---

## 5. Day-by-day breakdown — Phase 6 Tuần 11

Plan ship cùng Phase 6 base payment build. **Effort: 3–5 ngày dev** (4 ngày nominal + 1 ngày buffer). Lý do không phải 2 ngày: code chính ~250 LOC nhưng integration/test surface lớn — `send_image()` cho cả 2 channel với Messenger quirks (no inline caption, attachment payload shape), email platform parser với account filter logic, Postmark routing, cross-source dedup race condition E2E test, real-bank fixture validation.

### Day 0 — Prerequisites (< 1h founder action, không tính vào dev)

- [ ] Verify founder có 2 bank account: 1 VCB linked SePay + 1 TCB chưa link
- [ ] Confirm legal entity holder name (hộ kinh doanh — xem [Payment Spec §8](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_payment.md))
- [ ] Test transfer 10k giữa 2 account để verify TCB receive email notification working
- [ ] Migration `00X_widen_payment_source.sql` ready (xem §3)

### Day 1 — VietQR URL builder + Telegram adapter (~6h)

**Morning (3h):**
- [ ] Tạo `services/qr_generator.py` (1h) — implement `vietqr_url()` + `BANK_BIN` dict (10 banks NAPAS)
- [ ] Unit test `test_qr_generator.py` (1.5h) — URL format, encoding edge cases (Unicode holder, accented chars, large amount, special chars trong ref)
- [ ] Extend `BaseSender.send_image(user, url, caption, tag)` abstract method (15m)
- [ ] Doc commit + push (15m)

**Afternoon (3h):**
- [ ] Implement `TelegramSender.send_image()` qua `sendPhoto` API (1h) — caption inline, parse_mode Markdown
- [ ] Unit test với mock Telegram API (1h) — verify request shape, error handling
- [ ] Manual smoke test: gửi QR tới Telegram cá nhân founder, scan bằng VCB app → verify pre-fill account+amount+ref đúng (1h)

### Day 2 — Messenger adapter `send_image` + upgrade handler refactor (~7h)

**Morning (4h):**
- [ ] Implement `MessengerSender.send_image()` (2h) — attachment.type=image, payload.url, MESSAGE_TAG branching cho out-of-window
- [ ] Handle Messenger quirk: no inline caption với attachment → split thành 2 message (image + caption)
- [ ] Unit test với mock Meta Send API (1h) — verify request body shape, signature (no auto-quotes ref)
- [ ] Manual smoke test Messenger: send QR tới Page test, scan bằng TCB app → verify pre-fill (1h)

**Afternoon (3h):**
- [ ] Modify `handlers/upgrade.py` — replace text-only display với 5-message structure (header + 2 QR + ref + buttons) (2h)
- [ ] E2E test cả 2 channel: `/upgrade Pro Monthly` → verify message ordering + render đúng + button callback (1h)

### Day 3 — Email parallel path (~6h)

**Morning (3h):**
- [ ] Setup forwarding rule trong founder's Gmail (15m, manual): from TCB sender → `payment@in.fintrack.app`
- [ ] Postmark Inbound config: route `payment@in.fintrack.app` → POST `/inbound/{PLATFORM_TOKEN}` (15m + DNS propagation buffer)
- [ ] Tạo `parsers/email_platform_tcb.py` (1.5h) — wrap reuse `parsers/tcb.py` logic + **account filter** (skip nếu account khác PLATFORM_BANK_SECONDARY_ACCOUNT_NUMBER)
- [ ] Unit test `test_email_platform_tcb.py` (1h) — 5 TCB email fixtures, verify account filter logic, source label correct

**Afternoon (3h):**
- [ ] Implement `handlers/payment_inbound.py` (1.5h) — sender→parser dispatch, fallback domain match, error handling
- [ ] Verify endpoint routing AC: `POST /inbound/{PLATFORM_TOKEN}` → `handle_platform_inbound`, NOT user `tx_service` (1h)
- [ ] Update `payment_matcher` accept new source labels (`email_tcb_platform`, `email_mb_platform`) (30m)

### Day 4 — Cross-source dedup E2E + edge cases + buffer (~6h)

**Morning (3h):**
- [ ] E2E test happy path real bank:
    - Founder /upgrade Pro Monthly trên test account → pending row created (15m)
    - Real transfer 10k tới TCB secondary với ref đúng (30m wait)
    - Verify email arrive Gmail → forward → Postmark webhook fire → match → upgrade ≤5 phút (full path, ~30m wait time)
- [ ] E2E test edge case 1 — wrong account TCB email (vd founder có 2 TCB acc) → verify silent skip (30m)
- [ ] E2E test edge case 2 — typo ref code (Layer 2 fuzzy match) → verify upgrade với confidence='medium' (30m)

**Afternoon (3h):**
- [ ] E2E test cross-source dedup race — concurrent SePay + email webhook fire → verify chỉ 1 `payment_matches` row + 1 upgrade (1.5h race simulation với deliberate timing)
- [ ] E2E test fallback nếu vietqr.io down (mock 503) → verify fallback text-only display (30m)
- [ ] E2E test feature flag: `ENABLE_VIETQR=false` → verify text-only path; `ENABLE_EMAIL_PARALLEL=false` → verify endpoint no-op (30m)
- [ ] Documentation: env vars README + runbook entry trong DR scenario I (Gmail forwarding disabled) (30m)

### Day 5 — Buffer / iteration / polish (~4h, có thể compress nếu Day 1-4 smooth)

- [ ] Bug fix từ E2E discovery
- [ ] Polish error messages user-facing (vd "vietqr.io tạm offline, bạn vẫn copy số tài khoản dưới đây")
- [ ] Add monitoring task: daily email forward health check (alert nếu 0 email past 24h + có unmatched SePay)
- [ ] Code review self + retro
- [ ] Commit final + merge

> **Compression option:** Nếu Day 1-3 smooth + experienced với Postmark/Telegram API trước → có thể merge Day 4+5 thành 1 day, tổng 4 days. **Nếu lần đầu setup Postmark Inbound + Meta App Review chưa approve (Messenger test phải mock)** → cần đủ 5 days. Estimate range 3-5 phản ánh uncertainty này.

---

## 6. Acceptance Criteria

### 6.1. VietQR URL builder (vietqr.io public image)

- [ ] `vietqr_url()` return URL match format vietqr.io spec
- [ ] BANK_BIN cover top 6 MVP banks (VCB, TCB, MB, ACB, STB, BIDV) — Phase 7+ thêm Tier 2
- [ ] Unicode holder name encode đúng (vd "NGUYỄN VĂN A" → URL-safe)
- [ ] Amount integer (no decimal)
- [ ] Add `addInfo` parameter chứa exact ref_code (không truncate, không transform)

### 6.2. Adapter `send_image()`

- [ ] `BaseSender.send_image(user, image_url, caption, tag)` abstract method defined
- [ ] `TelegramSender.send_image()` dùng sendPhoto, render image + caption trong 1 message
- [ ] `MessengerSender.send_image()` dùng attachment.image + caption gửi message kế tiếp
- [ ] Cả 2 sender support `tag` field (Telegram ignore, Messenger map MESSAGE_TAG)
- [ ] Test: gửi cùng QR URL qua cả 2 channel → render visible + scannable

### 6.3. Upgrade flow UX

- [ ] `/upgrade {plan}` render 4 message:
    1. Header text "💳 Pro Monthly — 96,000đ + instructions"
    2. Image QR1 (primary VCB) + caption "🟢 Lựa chọn 1: VCB"
    3. Image QR2 (secondary TCB) + caption "🟡 Lựa chọn 2: TCB"
    4. Text ref code standalone "📋 PAY-..."
- [ ] Action buttons (Đổi plan, Hủy) ở message cuối
- [ ] Test scan QR1 bằng VCB app → app pre-fill account 9999888877 + amount 96000 + ref đúng
- [ ] Test scan QR2 bằng TCB app → app pre-fill TCB account + amount + ref đúng
- [ ] Render đúng cho cả Telegram + Messenger user

### 6.4. Email-based parallel path

- [ ] Forwarding rule active trong founder Gmail, verify forward latency <30s
- [ ] Postmark route `payment@in.fintrack.app` → POST /inbound/{PLATFORM_TOKEN} working
- [ ] `parsers/email_platform_tcb.py` parse 5+ TCB email mẫu, return canonical tx
- [ ] Account filter: parser skip nếu email cho TCB account khác (founder có >1 TCB)
- [ ] `_source = 'email_tcb_platform'` set đúng, payment_matcher accept
- [ ] E2E: real transfer TCB → upgrade ≤5 phút p95
- [ ] Cross-source dedup: SePay fire trước, email fire sau → email skip silent (status='matched')
- [ ] Cross-source dedup: email fire trước, SePay fire sau → SePay skip silent

### 6.5. Failure modes

- [ ] vietqr.io down → QR image fail render, bot detect (200 nhưng image fail load) → fallback text-only message với hướng dẫn copy ref
- [ ] Founder Gmail forwarding disabled accidentally → monitoring task daily detect 0 email → admin alert
- [ ] Postmark webhook fail → email parser không fire → SePay path vẫn primary, không revenue loss
- [ ] Founder TCB email format change → parser fail → unmatched_payments queue → admin manual resolve

---

## 7. Testing Strategy

### 7.1. Unit tests

| Module | Test focus | Min coverage |
|---|---|---|
| `services/qr_generator.py` | URL format, BANK_BIN keys, Unicode, large amounts | 100% (small file) |
| `parsers/email_platform_tcb.py` | 10+ email mẫu, account filter, source label | 90% |
| `services/channels/telegram.py:send_image` | sendPhoto API call shape, error handling | 80% |
| `services/channels/messenger.py:send_image` | attachment payload, MESSAGE_TAG branching | 85% |
| `handlers/payment_inbound.py` | Dispatch logic, unknown sender fallback | 85% |
| `handlers/upgrade.py:show_payment_instructions` | Message order, content correctness | 85% |

### 7.2. Integration tests

| Flow | Steps |
|---|---|
| QR generate → render Telegram | Generate URL → send via TelegramSender → verify image rendered in test chat |
| QR generate → render Messenger | Generate URL → send via MessengerSender → verify in Page test |
| Email path happy | Mock Postmark webhook payload (real TCB email JSON) → verify parser → payment_matcher fire → upgrade |
| Cross-source race | Inject SePay webhook + Postmark webhook within 100ms → verify only 1 `payment_matches` row inserted |
| Wrong account skip | Email for TCB account != platform account → verify parser return None |

### 7.3. E2E manual

- [ ] Real transfer 10k tới VCB → SePay path verify 60s notification
- [ ] Real transfer 10k tới TCB → email path verify 5min notification
- [ ] Real transfer 10k tới TCB với typo ref → verify Layer 2 fuzzy match
- [ ] Real transfer wrong amount → verify unmatched_payments queue + admin alert

### 7.4. Load test (defer Phase 7)

Vol thấp (subscription = ~5–30/ngày) không cần load test MVP. Phase 7 nếu MRR >$200/mo (>50 paying user) thì add.

---

## 8. Risks & Mitigations

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | vietqr.io API down hoặc thay đổi URL format | Thấp | QR image fail render | Fallback text-only message giữ nguyên (legacy spec §5.1). Bot detect render fail (image too small/error placeholder) qua periodic health check. Phase 7+ migrate Option B self-host nếu critical. |
| 2 | vietqr.io rate limit (~30 req/phút/IP) | Rất thấp ở MVP | QR fail cho 1 user | Cache QR PNG local 24h theo `(bank, amount, ref)`. Không bao giờ regenerate cùng (bank, amount, ref) trong 24h. |
| 3 | Founder Gmail forwarding rule bị disable accidentally | Trung bình | Email path silent fail, user TCB transfer không upgrade | Daily monitoring task: count emails received vào `payment@in.fintrack.app` past 24h. Nếu 0 email + có >1 unmatched SePay → alert admin Telegram. Runbook trong DR runbook. |
| 4 | TCB thay đổi email format → parser fail | Thấp | TCB transfers go to unmatched | Versioned parser tests (5+ samples), CI run hàng tuần. Admin manual resolve trong khi update parser. |
| 5 | Cross-source dedup race condition | Thấp | Double upgrade (chấp nhận credit user đầy đủ, không phải bug nghiêm trọng) | `SELECT ... FOR UPDATE` row pending khi match attempt. Atomic UPDATE pending_payments.status. Idempotent payment_matcher. |
| 6 | Founder lose access TCB email (account compromise) | Rất thấp | Email path lost | Recovery: rotate email, update forwarding rule, password reset Gmail. Documented trong DR runbook. SePay vẫn live khi recover. |
| 7 | User scan QR → app banking deeplink intercept (Messenger in-app browser) | Trung bình | UX confusion, user phải tap "Open in browser" | Caption hướng dẫn rõ ràng + fallback gõ tay. Đã cover trong Messenger spec §6.6. |
| 8 | QR encode Unicode holder name không đúng (vd "NGUYỄN" → "NGUY%E1%BB%84N" mojibake) | Thấp | Bank app reject hoặc display sai tên | Test với 10+ tên có dấu, encode UTF-8 + URL-encode đúng. Backup: dùng tên không dấu nếu fail (`NGUYEN` thay `NGUYỄN`). |

---

## 9. Rollout Plan

### 9.1. Feature flag

```python
# config.py
ENABLE_VIETQR = os.getenv("ENABLE_VIETQR", "true").lower() == "true"
ENABLE_EMAIL_PARALLEL = os.getenv("ENABLE_EMAIL_PARALLEL", "true").lower() == "true"
```

Nếu false:
- VIETQR off → fallback text-only display (như spec hiện tại)
- EMAIL_PARALLEL off → endpoint `/inbound/{PLATFORM_TOKEN}` return 200 + log (no parser fire)

Cho phép disable nhanh khi incident mà không phải redeploy.

### 9.2. Ramp stages

| Stage | Trigger | Action |
|---|---|---|
| 0 — Code deployed | Day 2 cuối Tuần 11 | Both flag `false`. Code path tested in staging. |
| 1 — Founder dogfood | Tuần 11 cuối | Flag `true` cho founder telegram_id only (whitelist). Founder test 1 ngày. |
| 2 — Beta open | Tuần 13 (Phase 7) | Flag `true` toàn bộ. 5–10 beta user thử upgrade qua cả 2 path. |
| 3 — Soft launch | Phase 8 sau beta validation 1 tuần | GA. Marketing mention "VietQR scan-to-pay" trong landing |
| 4 — Optimize | 100+ paying user | Add Option B self-host VietQR nếu cost/privacy yêu cầu. Add MB/ACB platform email parsers. |

### 9.3. Rollback

Nếu incident:
1. Set `ENABLE_VIETQR=false` → bot fallback text-only display, user vẫn upgrade được qua copy-paste
2. Set `ENABLE_EMAIL_PARALLEL=false` → bot chỉ display VCB QR, hide TCB
3. Both fallback paths không lose subscription revenue
4. Existing pending_payments unaffected (đã có ref code, chỉ mất QR display)

DB không rollback — `payment_matches` rows với source `email_tcb_platform` giữ làm history nếu rollback flag.

---

## 10. Cost Impact

| Item | Cost monthly | Note |
|---|---|---|
| vietqr.io public API | $0 | Free, public |
| Postmark Inbound additional volume | +$0–2 | ~30 emails/mo additional cho subscription, dưới starter tier |
| Founder TCB account | $0 | Account giữ existing, không charge fee |
| Engineer time | **3–5 ngày dev** | Trong Phase 6 Tuần 11. Day-by-day §5. |
| Ongoing ops | $0 | Forwarding rule once-set |
| **Net monthly** | **$0** | — |

**Cost saving:** ~50–100k/tháng (~600k–1.2tr/năm) so với link cả 2 bank vào SePay.

---

## 11. Cross-doc updates needed

Sau khi ship plan này cần update:

| Doc | Section | Change |
|---|---|---|
| `feature_payment.md` | §5.1 Upgrade flow | Replace text-only display với 4-message structure (text + 2 QR + ref code) |
| `feature_payment.md` | §2.4 thêm | "VietQR via vietqr.io public image URL" + tradeoff note |
| `feature_payment.md` | §10 Phase plan | Tuần 11 thêm 3-5 ngày VietQR + email parallel (sub-tasks 10.11 + 10.12) |
| `feature_messenger_channel.md` | §6.6 | Cross-link tới spec này, confirm `send_image()` adapter pattern aligned |
| `tdd.md` | §3.1 endpoint table | Confirm `/inbound/{PLATFORM_TOKEN}` implementation status |
| `tdd.md` | §5.2 env vars | Thêm `PLATFORM_BANK_*_BIN` + `PLATFORM_BANK_HOLDER_NAME` |
| `implementation-plan-500-users-and-more.md` | §C7 tax | Cross-link section "secondary bank parallel path" |
| `runbooks/disaster-recovery.md` | New scenario | "Founder Gmail forwarding rule disabled" — recovery steps |

---

## 12. Open questions

| # | Question | Status | Note |
|---|---|---|---|
| 1 | MB Bank platform parser ship cùng MVP hay defer Phase 7? | ⏸️ Deferred | TCB đủ cho redundancy MVP. MB add nếu founder có account MB. |
| 2 | Cache QR PNG local hay luôn fetch vietqr.io? | ⏸️ Deferred | Defer Phase 7 nếu volume rate limit hit. MVP fetch realtime OK. |
| 3 | Self-host EMVCo encoder (Option B) khi nào trigger? | ⏸️ Deferred | Trigger: vol >500 paying users HOẶC privacy audit yêu cầu. |
| 4 | Holder name có dấu hay không dấu trong VietQR? | ⏸️ Open | Test cả 2, dùng cái app banking VN render đúng nhất. Có thể default no-dấu cho safety. |
| 5 | Có nên expose flag `prefer_bank` trong user settings? (vd user mặc định prefer TCB) | ⏸️ Deferred | Phase 7 nếu user feedback. MVP show cả 2 ngang nhau. |

---

## 13. References

- [Feature Spec Payment v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_payment.md)
- [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md)
- [Feature Spec Refactor SaaS v1.2.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_saas_refactor.md)
- [TDD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)
- [Implementation Plan 500 users](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-500-users-and-more.md)
- [VietQR.io API docs](https://www.vietqr.io/danh-sach-api/)
- [VietQR.io image generator examples](https://img.vietqr.io/)
- [NAPAS Bank BIN list](https://www.napas.com.vn/)
- [Postmark Inbound webhook docs](https://postmarkapp.com/developer/webhooks/inbound-webhook)

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-07 | Initial implementation plan — VietQR via vietqr.io public image URL + email-based parallel payment path qua TCB/MB secondary bank. Effort: 3–5 ngày dev (4 nominal + 1 buffer) trong Phase 6 Tuần 11 — không phải 2 ngày vì integration/test surface lớn (2 channel `send_image()` adapter + Messenger image quirks + email parser account filter + Postmark routing + cross-source dedup E2E + real-bank fixture). Schema migration `ALTER COLUMN source TYPE VARCHAR(32)` required (`'email_tcb_platform'` 18 chars > 16). Cost saving: ~50–100k/tháng. Ship cùng base payment build, không kéo dài MVP timeline 16 tuần. |
