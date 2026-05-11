# Feature Spec — Multi-channel: Add Facebook Messenger

> **Version:** v1.1.1
> **Ngày tạo:** 2026-05-07
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase liên quan:** MVP Phase 1–6 (build song song Telegram, không defer Phase 2)
> **Tham chiếu:** [BRD v2.9.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md) §2.2 mục tiêu 4 + risk #2 · [PRD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md) §1.4, §2.1–2.3 · [TDD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) §1.4, §2.1, §3.1 · [Feature Spec Refactor v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-refactor-saas.md) §3.3 · [Feature Spec Payment v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-payment-bank-transfer.md) · [Impl Plan VietQR+Email v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md)

---

## 1. Mục tiêu & Non-goals

### 1.1. Mục tiêu

Thêm **Facebook Messenger** làm kênh thứ 2 song song Telegram, **code ship trong MVP** nhưng **public launch decoupled qua feature flag** sao cho:

- Code + foundation (schema multi-channel, channel adapter pattern, webhook endpoint, persistent menu) ship cùng MVP Phase 6.
- Public Messenger access flip ON khi Meta App Review approve — KHÔNG block MVP Telegram launch.
- Toàn bộ feature core (3-path onboarding, transaction capture, categorization, reports, pricing, payment) hoạt động identical trên cả 2 kênh — user không cảm thấy "bản Messenger thiếu feature so với Telegram".
- Architect cho phép thêm kênh thứ 3 (Zalo, WhatsApp, …) sau này không phải refactor handlers.

Quyết định bake-in từ thảo luận:

| Quyết định | Chọn | Lý do |
|---|---|---|
| Timing build | Code ship cùng MVP Phase 1–6 | Foundation work parallel với schema/adapter, không kéo dài timeline 16 tuần |
| Timing public launch | **Decoupled**: feature flag `ENABLE_MESSENGER_CHANNEL`, flip ON sau Meta App Review approve | Meta review không deterministic (3-14 ngày, có thể reject) — không cho phép block MVP launch. Telegram là primary launch channel. |
| Channel mode | Single-channel per user (chọn 1 trong 2 lúc onboarding) | Schema đơn giản, không phải sync state cross-channel, đủ cho 95% use case |
| Scope | Messenger only, Zalo defer | Zalo OA cần đăng ký doanh nghiệp + phí — defer Phase 2 sau khi đạt 100+ user |

### 1.2. Non-goals

- KHÔNG cho phép user link cả Telegram + Messenger vào 1 account — single channel duy nhất per user. Muốn đổi channel = tạo account mới hoặc support migration tay trong Phase 2.
- KHÔNG build Zalo OA / WhatsApp Business API trong scope này. Architect sẵn sàng (adapter pattern), implementation defer.
- KHÔNG support Messenger group chat — chỉ 1-on-1 với Page (group chat trên Messenger có policy phức tạp riêng, không phải use case).
- KHÔNG migrate user Telegram hiện có sang Messenger tự động. Founder beta user signup lại nếu muốn test Messenger.
- KHÔNG cross-post 1 message tới cả 2 kênh. Outbound đi đúng kênh user signup.

---

## 2. Diff: current → target

### 2.1. Architecture diff

| Layer | Current (Telegram only) | Target (Telegram + Messenger) |
|---|---|---|
| Identity | `users.telegram_id BIGINT NOT NULL UNIQUE` | `users.channel_type` + `users.channel_user_id` (UNIQUE pair) |
| Outbound resolution | Lookup `chat_id` từ `users.telegram_id` | Resolve `chat_id` + `channel_type`, dispatch tới đúng adapter |
| Webhook ingest | `POST /webhook` (Telegram only) | `POST /webhook/telegram` + `POST /webhook/messenger` (verify Meta signature) |
| Outbound sender | `services/messenger.py` → Telegram Bot API | `services/messenger.py` → adapter selector (`TelegramSender` / `MessengerSender`) |
| Bot ownership | 1 `BOT_TOKEN` Telegram | 1 `BOT_TOKEN` Telegram + 1 Facebook Page (`FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`) |
| Onboarding entry | `t.me/FinTrackBot` → `/start` | `t.me/FinTrackBot` HOẶC `m.me/FinTrackPage` (Page username) → "Get Started" |
| Webhook URL per user | `https://api.fintrack.app/hook/{user_token}` | Không thay đổi — webhook token là per-user, không tied vào channel |
| Inbound email | `u{user_id}@in.fintrack.app` | Không thay đổi — email forwarding dùng chung cho cả 2 channel |
| Out-of-band notification | Telegram channel `@FinTrackUpdates` | Telegram channel + Facebook Page post cho Messenger users |

### 2.2. Components mới cần thêm

**Code (mới):**
- `services/channels/__init__.py` — adapter registry
- `services/channels/base.py` — `BaseSender` interface (abstract)
- `services/channels/telegram.py` — di chuyển logic Telegram hiện tại vào đây
- `services/channels/messenger.py` — Meta Send API client
- `handlers/messenger_webhook.py` — verify signature + dispatch update tới command/callback handlers
- `parsers/messenger_payload.py` — normalize Messenger event → canonical `Update` dataclass (giống Telegram update format)

**Code (sửa):**
- `services/messenger.py` — `send(user_id, payload)` lookup `users.channel_type` → route tới adapter tương ứng
- `main.py` — thêm endpoint `/webhook/messenger` + endpoint verify GET (`hub.verify_token`)
- `handlers/onboarding.py` — flow detect channel context, chỉ xuất hiện 1 entry point per channel
- `db.py` — query helpers thay `telegram_id` lookup bằng `(channel_type, channel_user_id)` lookup
- `config.py` — thêm env vars Meta

**Code (giữ nguyên):**
- `handlers/sepay.py`, `handlers/transaction.py`, `handlers/manage.py`, `handlers/allocation.py`, `handlers/reports.py` — vì đã đi qua `messenger.send()` interface, không biết kênh nào. Đây là payback của foundation refactor.
- `parsers/` (email parsers) — channel-agnostic.
- Toàn bộ schema khác (`transactions`, `categories`, `bot_state`, …) — không thay đổi, vẫn scope theo `user_id`.

### 2.3. Code keep / rewrite / delete diff

| File | Action | Detail |
|---|---|---|
| `services/messenger.py` | Rewrite (~30 dòng) | Thêm channel resolution + adapter dispatch |
| `services/channels/telegram.py` | New | Di chuyển nội dung `telegram_api.py` hiện tại vào |
| `telegram_api.py` | Delete sau migration | Wrapper được `services/channels/telegram.py` thay |
| `handlers/messenger_webhook.py` | New | Meta verify + payload normalize |
| `parsers/messenger_payload.py` | New | Map Meta event format → internal Update |
| `db.py` | Edit | Helper `get_user_by_channel(channel_type, channel_user_id)` thay `get_user_by_telegram_id()` |
| `migrations/00X_add_channel_type.sql` | New | Schema migration |

---

## 3. Schema changes

### 3.1. `users` table — thêm channel_type + channel_user_id

```sql
-- Migration: 00X_add_channel_type.sql

-- Thêm 2 column mới
ALTER TABLE users ADD COLUMN channel_type VARCHAR(16);
ALTER TABLE users ADD COLUMN channel_user_id VARCHAR(64);

-- Backfill: tất cả user hiện tại là Telegram
UPDATE users SET
    channel_type = 'telegram',
    channel_user_id = telegram_id::TEXT
WHERE channel_type IS NULL;

-- Set NOT NULL sau backfill
ALTER TABLE users ALTER COLUMN channel_type SET NOT NULL;
ALTER TABLE users ALTER COLUMN channel_user_id SET NOT NULL;

-- Constraint: channel_type valid
ALTER TABLE users ADD CONSTRAINT chk_channel_type
    CHECK (channel_type IN ('telegram', 'messenger'));

-- Unique pair (1 user duy nhất per channel ID)
ALTER TABLE users ADD CONSTRAINT uniq_channel_user
    UNIQUE (channel_type, channel_user_id);

-- Drop UNIQUE cũ trên telegram_id (vì giờ Messenger user sẽ có telegram_id NULL)
ALTER TABLE users DROP CONSTRAINT users_telegram_id_key;

-- Cho phép telegram_id NULL (Messenger user không có)
ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL;

-- Index cho lookup nhanh
CREATE INDEX idx_users_channel ON users(channel_type, channel_user_id);
```

**Diễn giải:**

- `channel_type`: enum-like `'telegram'` hoặc `'messenger'`. Phase sau thêm `'zalo'`, `'whatsapp'` chỉ cần update CHECK constraint.
- `channel_user_id`: ID user ở channel đó. Telegram = `telegram_id` (string-cast của bigint). Messenger = `psid` (Page-Scoped User ID, string ~16 digits).
- `telegram_id` cũ trở thành nullable + bỏ UNIQUE. Giữ column vì historic data + analytics. Insert mới chỉ qua `channel_user_id`.
- `chat_id` field trong users vẫn dùng cho Telegram. Messenger không có khái niệm chat_id riêng — `psid` chính là chat identifier. Code outbound sẽ branch theo `channel_type`.

**Alternative đã cân nhắc (loại):** tách bảng `user_channels(user_id, channel_type, channel_user_id)` — overkill vì single-channel per user.

### 3.2. Reserved channel ID prefix

Tránh collision PSID Messenger với telegram_id integer khi cast về string:

- Telegram telegram_id range thực tế: 9–10 digit (vd `123456789`)
- Messenger PSID: 15–17 digit số nguyên

Không có collision tự nhiên. Nhưng để defensive: validation insert phải kiểm tra `(channel_type, channel_user_id)` cặp đầy đủ, không lookup chỉ bằng `channel_user_id`.

### 3.3. Bot pool & messenger pool

`users.bot_id` (TDD §1.4 prep cho bot pool) chỉ apply cho Telegram. Messenger không có bot pool concept (mỗi Page = 1 outbound endpoint, scale bằng cách Meta tự throttle). Future: nếu cần multi-Page (vd Page riêng cho Pro tier) thêm `users.fb_page_id` riêng.

---

## 4. Endpoint design

### 4.1. Endpoint table mới

| Method | Path | Source | Mô tả |
|---|---|---|---|
| POST | `/webhook/telegram` | Telegram Bot API | Đổi tên từ `/webhook` cũ. Updates + callbacks. |
| GET | `/webhook/messenger` | Meta verification | Trả `hub.challenge` khi `hub.verify_token` match `FB_VERIFY_TOKEN` env. |
| POST | `/webhook/messenger` | Meta Page webhook | Messages + postbacks. Verify `X-Hub-Signature-256` header. |
| POST | `/hook/{user_token}` | SePay | Per-user webhook — không đổi |
| POST | `/inbound/{user_token}` | Postmark | Per-user email forwarding — không đổi |

### 4.2. Messenger webhook payload format

Meta gửi event format khác Telegram. Cần normalize:

```python
# Meta format (rút gọn)
{
    "object": "page",
    "entry": [{
        "id": "<PAGE_ID>",
        "time": 1748131200000,
        "messaging": [{
            "sender": {"id": "<PSID>"},
            "recipient": {"id": "<PAGE_ID>"},
            "timestamp": 1748131200000,
            "message": {"mid": "...", "text": "/start"}
            # OR "postback": {"title": "Get Started", "payload": "GET_STARTED"}
        }]
    }]
}
```

Normalize tới canonical `Update`:

```python
# parsers/messenger_payload.py
def parse_messenger_event(payload: dict) -> list[Update]:
    """
    1 webhook call có thể chứa nhiều entry × nhiều messaging events.
    Trả về list of internal Update objects, mỗi cái tương đương 1 Telegram update.
    """
    updates = []
    for entry in payload.get("entry", []):
        for ev in entry.get("messaging", []):
            psid = ev["sender"]["id"]
            if "message" in ev:
                text = ev["message"].get("text")
                quick_reply_payload = ev["message"].get("quick_reply", {}).get("payload")
                updates.append(Update(
                    channel_type="messenger",
                    channel_user_id=psid,
                    text=text,
                    callback_data=quick_reply_payload,  # giống Telegram callback
                    timestamp=ev["timestamp"],
                ))
            elif "postback" in ev:
                updates.append(Update(
                    channel_type="messenger",
                    channel_user_id=psid,
                    callback_data=ev["postback"]["payload"],
                    text=None,
                    timestamp=ev["timestamp"],
                ))
    return updates
```

### 4.3. Signature verification

```python
# handlers/messenger_webhook.py
import hmac, hashlib

def verify_meta_signature(raw_body: bytes, header: str, app_secret: str) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)
```

Mọi POST `/webhook/messenger` không pass verify → 200 OK + log warning (không leak info, giống pattern SePay invalid token).

---

## 5. `services/messenger.py` adapter pattern

Đây là phần đẹp nhất của architect — vì foundation refactor đã đặt sẵn `messenger.send(user_id, payload)` interface, handlers KHÔNG phải đổi gì.

### 5.1. Adapter base

```python
# services/channels/base.py
from abc import ABC, abstractmethod

class BaseSender(ABC):
    @abstractmethod
    async def send_text(self, user, text: str, reply_markup: dict | None = None) -> None: ...

    @abstractmethod
    async def send_picker(self, user, prompt: str, options: list[ButtonSpec]) -> None: ...

    @abstractmethod
    async def edit_message(self, user, message_id: str, text: str) -> None: ...
```

### 5.2. Adapter selector

```python
# services/messenger.py (rewritten)
from services.channels.telegram import TelegramSender
from services.channels.messenger import MessengerSender

_SENDERS = {
    "telegram": TelegramSender(),
    "messenger": MessengerSender(),
}

async def send(user_id: int, payload: dict) -> None:
    user = await db.get_user(user_id)
    sender = _SENDERS[user.channel_type]
    if payload["type"] == "text":
        await sender.send_text(user, payload["text"], payload.get("reply_markup"))
    elif payload["type"] == "picker":
        await sender.send_picker(user, payload["prompt"], payload["options"])
    # ...
```

### 5.3. Telegram adapter (move existing)

Code hiện tại trong `telegram_api.py` di chuyển vào `services/channels/telegram.py`, wrap thành `TelegramSender` class. No logic change.

### 5.4. Messenger adapter (new)

```python
# services/channels/messenger.py
import httpx

class MessengerSender(BaseSender):
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.page_token = os.environ["FB_PAGE_ACCESS_TOKEN"]

    async def send_text(self, user, text: str, reply_markup=None) -> None:
        body = {
            "recipient": {"id": user.channel_user_id},  # PSID
            "messaging_type": "RESPONSE",  # within 24h window
            "message": {"text": text}
        }
        if reply_markup:
            body["message"]["quick_replies"] = self._to_quick_replies(reply_markup)

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.BASE_URL}/me/messages",
                params={"access_token": self.page_token},
                json=body,
                timeout=10.0,
            )
            r.raise_for_status()

    def _to_quick_replies(self, telegram_inline_keyboard):
        """Convert Telegram inline_keyboard format → Messenger quick_replies format."""
        # Telegram: list of list of {text, callback_data}
        # Messenger: list of {content_type, title, payload}
        # Messenger limit: max 13 quick replies per message, title ≤ 20 chars
        flat = [btn for row in telegram_inline_keyboard for btn in row]
        return [
            {
                "content_type": "text",
                "title": btn["text"][:20],  # Messenger truncate hard
                "payload": btn["callback_data"],
            }
            for btn in flat[:13]
        ]
```

### 5.5. Quirks đã biết phải handle

| Telegram | Messenger | Mitigation |
|---|---|---|
| `inline_keyboard` 2D grid, không giới hạn rows | `quick_replies` flat list, max 13, title ≤ 20 chars | Flatten + truncate, nếu >13 button → split thành 2 message |
| `sendMessage` tới chat bất kỳ lúc nào | Meta 24-hour rule + message tag | Branch send strategy theo `last_user_message_at` (xem §6) |
| Edit message với `editMessageText` | Không edit được — chỉ gửi mới hoặc dùng "messages" with reference | Gửi message mới + delete cũ qua Send API delete |
| Markdown / HTML format | Plain text only (link tự render) | Strip Markdown khi adapter là Messenger |
| Callback data unlimited | Postback payload max 1000 chars | Đã thoải mái — không phải concern |

---

## 6. Meta-specific constraints

### 6.1. 24-hour rule

Meta chỉ cho gửi message `RESPONSE` trong 24 giờ kể từ user message gần nhất. Ngoài cửa sổ này phải dùng **Message Tag**.

Lưu trạng thái:

```sql
ALTER TABLE users ADD COLUMN last_user_message_at TIMESTAMPTZ;
```

Update mỗi khi nhận inbound từ Messenger. Logic outbound:

```python
async def send_text(self, user, text, reply_markup=None):
    in_window = (
        user.last_user_message_at and
        (datetime.utcnow() - user.last_user_message_at).total_seconds() < 24 * 3600
    )
    body = {
        "recipient": {"id": user.channel_user_id},
        "message": {"text": text},
    }
    if in_window:
        body["messaging_type"] = "RESPONSE"
    else:
        # Out of window — must use message tag
        body["messaging_type"] = "MESSAGE_TAG"
        body["tag"] = "ACCOUNT_UPDATE"  # see §6.2
    # POST
```

### 6.2. Message Tags

Sử dụng có thẩm quyền:

| Outbound type | Tag | Use case |
|---|---|---|
| Transaction notification | `ACCOUNT_UPDATE` | "💸 -120,000đ — chọn category" — đây là update tài chính của user, hợp |
| Daily recap (23:00) | `ACCOUNT_UPDATE` | Recap chi tiêu hôm nay — financial update |
| Trial expiring reminder | `ACCOUNT_UPDATE` | Account state change — hợp |
| Marketing / cross-sell | KHÔNG được — Messenger cấm | Phải gửi qua Telegram channel hoặc email |
| Payment reminder | `ACCOUNT_UPDATE` | Hợp |

**Risk:** Meta có thể audit và banh use case nếu thấy ACCOUNT_UPDATE bị abuse. Mitigation: log mọi outbound `tag` vào `analytics_events` để có audit trail; tự audit hàng tháng.

### 6.3. App Review prerequisites

Trước khi launch public, Facebook App phải pass review:

| Permission | Cần cho | Review difficulty |
|---|---|---|
| `pages_messaging` | Gửi message tới user → Page | Standard, ~3–7 ngày |
| `pages_messaging_subscriptions` | Gửi outside 24h window với MESSAGE_TAG | Standard, cần video demo use case |
| `pages_show_list` | List Pages user own (không cần cho bot này) | N/A |

**Lead time:** ~2 tuần buffer cho review back-and-forth. Phải submit Phase 5 cuối / Phase 6 đầu để kịp launch.

**Required cho submission:**
- Privacy policy URL (đã có target `/help` PRD §6.3)
- App icon (1024x1024)
- Screencast demo flow: user message Page → bot reply category picker → user pick → confirm
- Use case writeup giải thích tại sao cần `pages_messaging_subscriptions`

### 6.4. Rate limits

| Limit | Value | Notes |
|---|---|---|
| Calls per app per hour | 200 × số Page user | Rất rộng cho 1 page small. Không phải concern ở MVP. |
| Messages per second per page | ~25/s suggested | Tương đương Telegram 30/s. Cùng rate limiter logic apply. |
| Messages per recipient per second | 1/s | Cùng limit Telegram. |

`services/channels/messenger.py` dùng cùng token bucket rate limiter (C9 outbound queue) — chỉ tạo bucket riêng cho Messenger.

### 6.5. Ad-hoc errors phải handle

| Code | Meaning | Action |
|---|---|---|
| 10 | Permission denied (user blocked Page) | Mark user inactive, không retry |
| 100 | Invalid PSID | Log + mark user invalid_channel |
| 200 | Permission denied (24h window violation) | Add MESSAGE_TAG + retry |
| 613 | Calls per second limit | Backoff 1s |

### 6.6. Subscription payment flow — Messenger-specific concerns

> ⚠️ **Scope clarification:** Section này CHỈ apply cho **subscription payment** (user upgrade Free → Pro/Business hoặc renew). Đây là flow trigger bởi command `/upgrade`, không phải core transaction tracking flow.
>
> Core transaction tracking (SePay webhook + email parser categorize chi tiêu của user) **không có ref code, không có VietQR, không có concerns này** — bot hoàn toàn passive: nhận webhook → parse → gửi quick reply category picker → user chọn → done. Phần đó adapter Messenger không cần xử lý gì khác Telegram ngoài quick reply format (đã cover §5.5).
>
> Tách biệt rạch ròi trong code:
>
> | Flow | Trigger | Endpoint | Service | Bảng DB |
> |---|---|---|---|---|
> | **Transaction tracking** (mọi user) | Bank → SePay/email auto | `/hook/{user_token}` + `/inbound/{user_token}` | `tx_service` | `transactions` |
> | **Subscription payment** (chỉ user upgrade) | User gõ `/upgrade` | `/hook/{PLATFORM_TOKEN}` | `payment_matcher` | `pending_payments` + `payment_matches` |

Reference: [Feature Spec Payment v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-payment-bank-transfer.md). Ref code format `PAY-{user_id}-{plan}-{period}-{nonce4}` không thay đổi — không tied vào channel. Nhưng 4 chỗ trong UX subscription upgrade cần adapter Messenger xử lý riêng:

**1. Ref code display (không có code block)**

Telegram render `` `PAY-42-pro-monthly-x9k3` `` thành block monospace có nút tap-to-copy native. Messenger không support code block — plain text only. User mobile phải long-press → Copy menu, dễ chọn nhầm.

Adapter pattern:

```
Telegram:
    "Mã chuyển khoản: `PAY-42-pro-monthly-x9k3`
     Tap để copy."

Messenger (gửi 2 message liên tiếp):
    msg1: "Mã chuyển khoản (long-press tin nhắn dưới để copy):"
    msg2: "PAY-42-pro-monthly-x9k3"
```

Bằng cách isolate ref code thành 1 message độc lập, user long-press dễ select toàn bộ.

**2. VietQR image delivery**

VietQR là feature payment cốt lõi — encode (account + amount + ref) thành QR, user scan trong banking app thay vì gõ tay.

| Channel | API | Implementation |
|---|---|---|
| Telegram | `sendPhoto` với caption | Direct upload bytes hoặc URL |
| Messenger | `attachment.type=image` với `payload.url` | Cần URL public (host trên CDN/static endpoint), hoặc upload-via-attachment_id để reuse |

`BaseSender` thêm method abstract:

```python
@abstractmethod
async def send_image(self, user, image_url: str, caption: str | None = None) -> None: ...
```

Có thể dùng SePay generated VietQR URL sẵn (`https://qr.sepay.vn/img?bank=...&acc=...&amount=...&des=...`) — không phải tự generate QR.

**3. Banking deeplink**

VietQR URL có thể wrap deeplink scheme (`vietqr://...` hoặc HTTPS với fallback) mà nhiều bank app handle để pre-fill số tiền + ref.

Telegram tap link → mở app native OK. Messenger trên mobile có in-app browser intercept → user phải tap "Open in browser" → chain redirect → bank app. Thêm 1 step UX.

Mitigation: caption rõ ràng kèm fallback gõ tay:

```
Messenger caption:
"💳 Quét QR bằng app ngân hàng
 hoặc tap link → 'Open in browser' để mở app banking trực tiếp.
 Nếu không scan được, gõ tay ref: PAY-42-pro-monthly-x9k3"
```

**4. Match notification ngoài 24h window**

Edge case duy nhất bị Meta 24h-rule:

- User `/upgrade` 8h sáng Thứ 2 → bot reply pending payment (in window)
- User chuyển tiền 9h sáng Thứ 3 (25h sau) → SePay match → bot notify
- Notification fire **25h+ kể từ user message gần nhất → outside 24h window**

Phải dùng `messaging_type=MESSAGE_TAG` + tag `ACCOUNT_UPDATE`. Hợp policy vì là financial account update.

Tương tự, tất cả các **subscription**-related outbound proactive đều cần tag:

| Outbound type | Window status | Tag |
|---|---|---|
| Pending payment confirmation (right after `/upgrade`) | In window | `RESPONSE` |
| Match success notification | Có thể outside | `ACCOUNT_UPDATE` |
| Pending payment expire warning (24h trước expire) | Outside | `ACCOUNT_UPDATE` |
| Annual reminder (14+3+1 ngày trước expire) | Outside | `ACCOUNT_UPDATE` |
| Recurring renewal success | Có thể outside | `ACCOUNT_UPDATE` |
| Grace period entry warning | Outside | `ACCOUNT_UPDATE` |
| Auto-downgrade notification | Outside | `ACCOUNT_UPDATE` |
| Refund notification (admin trigger) | Có thể outside | `ACCOUNT_UPDATE` |

Implementation: trong `MessengerSender.send_text()`, subscription-related payload cần explicit `tag` field — caller (`payment_matcher` / `subscription_service`) set `tag="ACCOUNT_UPDATE"` cho mọi outbound proactive thuộc subscription domain.

```python
# Caller pattern (subscription service)
await messenger.send(user_id, {
    "type": "text",
    "text": "✅ Thanh toán thành công, plan Pro active đến ...",
    "tag": "ACCOUNT_UPDATE",  # explicit tag for subscription outbound
})
```

**Lưu ý:** transaction tracking outbound (category picker khi nhận tx, daily recap, status report) **không phải** subscription domain. Tag default cho các flow đó là `ACCOUNT_UPDATE` cũng hợp policy (financial account state change của user) hoặc `RESPONSE` nếu trong window. Adapter tự handle window detection cho non-subscription path.

`TelegramSender` ignore field `tag`, `MessengerSender` dùng nó (nếu thiếu thì auto-detect window).

### 6.7. Privacy policy update — required

**Question 2 trả lời: Yes, cần update privacy policy.**

Lý do: Meta yêu cầu Page có privacy policy URL accessible từ App Settings + Page About. Privacy policy phải mention rõ:

- Loại data Meta forward tới platform: PSID, message content, profile info (nếu request)
- Mục đích sử dụng: tracking transaction, categorization, reports
- Data retention policy giống Telegram (Free user inactive 90 ngày → archive)
- User rights: data export, account deletion (qua command tương đương `/export`, `/delete`)
- Meta-specific: link tới [Meta Data Policy](https://www.facebook.com/about/privacy/) cho data Meta xử lý ở phía họ

**Action items trước launch Messenger:**

- [ ] Thêm section "Facebook Messenger users" vào privacy policy hiện có
- [ ] List explicit: PSID, message content, Page interaction events được lưu
- [ ] List opt-out: user block Page → ngừng outbound, data archive sau 90 ngày
- [ ] URL accessible HTTPS: `https://fintrack.app/privacy` (hoặc tương đương) — Meta App Review require
- [ ] Linked trong:
    - Page About section
    - Persistent menu "❓ Help" → "Privacy"
    - Welcome message khi user "Get Started" lần đầu

**Vietnamese PDPA cross-check (Nghị định 13/2023):** privacy policy phải có bản tiếng Việt. Reuse template Telegram + add Messenger paragraph. PDPA yêu cầu giữ nguyên cho cả 2 channel: data minimization (không lưu số tài khoản), user consent, breach notification.

---

## 7. Onboarding flow on Messenger

> **UI strategy:** Onboarding **chat-only** trên Messenger (giống Telegram), KHÔNG có web form/wizard. Quyết định + trade-off analysis: [decision-onboarding-ui-strategy.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/decision-onboarding-ui-strategy.md). Pre-launch landing page tĩnh + privacy policy + terms (~3 ngày dev) là content khác, không phải onboarding form.

### 7.1. Entry point

User truy cập `m.me/FinTrackPage` (Page username) → Page render "Get Started" button (Meta-managed). Click "Get Started" → Meta gửi postback:

```json
{"postback": {"payload": "GET_STARTED"}}
```

Bot nhận → tạo user row với `channel_type='messenger', channel_user_id=<psid>` (atomically + idempotent).

### 7.2. Tương đương `/start`

Vì Messenger không có command paradigm, không có slash commands ngoài quick replies. Map:

| Telegram | Messenger |
|---|---|
| `/start` | Postback `GET_STARTED` (auto từ Get Started button) |
| `/status` | Persistent menu item "📊 Status" (Meta supports persistent menu max 5 items) |
| `/today` | Persistent menu "🍜 Today" |
| `/manage` | Persistent menu "⚙️ Manage" |
| `/help` | Persistent menu "❓ Help" |
| `/settings` | Persistent menu "⚙️ Settings" |
| `/weekly`, `/report`, `/export`, `/allocate` | Truy cập qua sub-menu trong "Manage" hoặc text shortcut "weekly", "report", … |

Persistent menu set 1 lần qua API:

```python
# Setup script — chạy 1 lần khi deploy
await fb_api.set_persistent_menu([
    {"type": "postback", "title": "📊 Status", "payload": "MENU_STATUS"},
    {"type": "postback", "title": "🍜 Today", "payload": "MENU_TODAY"},
    {"type": "postback", "title": "⚙️ Manage", "payload": "MENU_MANAGE"},
    {"type": "postback", "title": "⚙️ Settings", "payload": "MENU_SETTINGS"},
    {"type": "postback", "title": "❓ Help", "payload": "MENU_HELP"},
])
```

### 7.3. Path A/B/C onboarding

Identical với Telegram — chỉ thay inline keyboard bằng quick replies:

```
[🔗 Đã có SePay] [📋 Chưa có SePay] [📧 Dùng Email]
```

3 path render thành 3 quick replies (max 13/message, ta dùng 3 → ok). Click quick reply → postback payload `ONBOARD_PATH_A` / `ONBOARD_PATH_B` / `ONBOARD_PATH_C`.

Path C đặc biệt: user vẫn nhận `u{user_id}@in.fintrack.app` (đồng bộ với Telegram), forwarding rule không khác.

### 7.4. Bot state machine

`bot_state` table không đổi schema — `step` + `payload` đủ. State machine logic chia sẻ giữa channel.

Quick reply quirk: Messenger render quick replies dưới message gần nhất, message mới gửi sẽ làm quick replies cũ biến mất. Code phải resend quick replies khi cần re-prompt (vd user nhập text linh tinh thay vì click).

### 7.5. UX parity matrix — channel-specific differences

**Question 3 trả lời: Yes, cần phân biệt UX giữa platforms.**

Mục tiêu base: feature parity 100% (cùng feature ở cả 2 channel). Mục tiêu UX: adapt từng channel theo native pattern thay vì force Telegram UX lên Messenger. Ma trận sau định nghĩa rõ chỗ nào identical và chỗ nào divergent intentional:

| Aspect | Telegram pattern | Messenger pattern | Reason |
|---|---|---|---|
| Entry point | `/start` command typed | "Get Started" button (Meta UI) | Messenger không có command paradigm |
| Command access | Slash commands `/status`, `/today`, … typed | Persistent menu (5 item max) + text shortcut "status", "today" | Messenger persistent menu = native discovery |
| Button format | Inline keyboard 2D grid, unlimited rows | Quick replies flat list max 13, title ≤ 20 chars | Meta API constraint |
| Long category list (>13) | Single message với inline keyboard | Multi-message split: "Categories (1/2)" → "Categories (2/2) + ➕ New" | Quick reply cap 13 |
| Text formatting | Markdown (`*bold*`, `` `code` ``, ```pre```) | Plain text only — emoji + line breaks for hierarchy | Messenger không render Markdown |
| Ref code copy | Code block tap-to-copy | Standalone message, instruct long-press | Không có code block |
| Image (VietQR, charts) | `sendPhoto` direct | `attachment.type=image` với public URL | API shape khác |
| Edit message | `editMessageText` | Send new + (optional) delete old | Messenger không edit được |
| Confirmation dialog | "[✅ Yes] [❌ No]" inline keyboard | Quick reply 2 button hoặc text "yes/no" | OK ở quick reply |
| Daily recap timing | 23:00 local timezone — sendMessage anytime | 23:00 local — `MESSAGE_TAG` ngoài 24h window | Meta 24h-rule |
| Welcome message | 1 message với inline keyboard 3 path | Welcome screen + Get Started → 1 message với quick replies 3 path | Welcome screen Meta-managed |
| Help / Settings access | `/help`, `/settings` commands | Persistent menu items | Native pattern |
| Error message style | "⚠️ Lỗi: {detail}" | Identical (chỉ khác encoding) | OK identical |
| Notification volume | 1 message per event | Identical | OK identical |
| Onboarding 3-path | 3 inline buttons | 3 quick replies (≤13 fit easy) | OK identical structure |

**Copy/wording differences cần tay viết riêng:**

| Telegram copy | Messenger copy |
|---|---|
| "Bấm `/help` để xem hướng dẫn." | "Bấm menu ❓ Help dưới đây để xem hướng dẫn." |
| "Tap để copy: \`PAY-XX\`" | "Long-press tin nhắn dưới để copy:" |
| "Bấm /status xem tổng quan" | "Bấm 📊 Status trong menu để xem tổng quan" |
| "Reply 'có' hoặc 'không'" | "Tap nút 'Có' hoặc 'Không' dưới đây" |

**Implementation pattern:** copy templates trong code phải có 2 variant. Tổ chức:

```python
# copy/onboarding.py
WELCOME = {
    "telegram": "👋 Chào bạn! Bấm /start để bắt đầu...",
    "messenger": "👋 Chào bạn! Tap 'Get Started' để bắt đầu...",
}

# Caller
template = WELCOME[user.channel_type]
await messenger.send(user_id, {"type": "text", "text": template})
```

Hoặc dùng template helper:

```python
def t(template_key: str, channel_type: str, **kwargs) -> str:
    """Lookup channel-specific copy template + format."""
    return COPY[template_key][channel_type].format(**kwargs)
```

**Acceptance criteria UX parity:**

- [ ] Mọi user-facing copy có ít nhất 2 variant trong `copy/` module (Telegram + Messenger)
- [ ] Test snapshot: render mỗi flow trên cả 2 channel → diff manual review
- [ ] Persistent menu Messenger cover 5 most-used commands (Status, Today, Manage, Settings, Help)
- [ ] Multi-message split logic: list >13 button auto split với "(1/N)" indicator
- [ ] No Markdown leak vào Messenger (test: gửi message có `*bold*` qua TelegramSender → render bold; qua MessengerSender → strip ra plain "bold")

---

## 8. Phased implementation plan

Fit vào timeline BRD §8 hiện tại (Phase 1–6 = Tuần 1–12):

### Phase 1: Foundation (Tuần 1–2) — NO CHANGE in spec impact

Schema migration `00X_add_channel_type.sql` ship cùng schema initial — vì nếu để sau thì backfill phức tạp hơn. Code không phải build adapter trong phase này nhưng schema đã sẵn.

**Acceptance criteria:**
- [ ] DDL multi-channel ship trong Phase 1 (cùng `users` table initial)
- [ ] `services/messenger.py` foundation đã thiết kế adapter-ready (channel resolution logic placeholder, mặc định route Telegram)

### Phase 2: Handlers Refactor (Tuần 3–4)

Refactor handlers chuyển hết outbound qua `messenger.send()` — đây đã có trong refactor spec. Thêm gì:

- [ ] `db.get_user_by_channel(channel_type, channel_user_id)` helper — call site mới thay `get_user_by_telegram_id()`
- [ ] Telegram dispatcher gọi `db.get_user_by_channel('telegram', telegram_id)`
- [ ] Adapter base class `BaseSender` tạo, `TelegramSender` migrate code từ `telegram_api.py`

### Phase 3: Pricing Logic (Tuần 5) — NO CHANGE

Tier limits không liên quan channel.

### Phase 4: SePay Onboarding (Tuần 6) — NO CHANGE

Webhook URL + tokens không tied vào channel.

### Phase 5: Email Parsing (Tuần 7–9) — NO CHANGE

Email parser channel-agnostic.

### Phase 6: Messenger Channel Build (Tuần 10–11) — **NEW SCOPE**

Đây là phase chính của spec này. 2 tuần dev:

**Tuần 10:**
- [ ] Tạo Facebook Page + Facebook Developer App (1 ngày setup)
- [ ] Implement `services/channels/messenger.py` (`MessengerSender`)
- [ ] Implement `handlers/messenger_webhook.py` (verify signature + parse payload)
- [ ] Implement `parsers/messenger_payload.py` (Update normalization)
- [ ] Endpoint `/webhook/messenger` GET + POST
- [ ] Setup persistent menu script + Get Started button
- [ ] Submit App Review (`pages_messaging` + `pages_messaging_subscriptions`)

**Tuần 11:**
- [ ] Onboarding flow Messenger (3-path identical Telegram)
- [ ] Quick replies adapter cho transaction picker
- [ ] 24h window + message tag logic
- [ ] **Subscription payment Messenger adapter** (§6.6, scope: `/upgrade` flow only): ref code as standalone message, `send_image()` cho VietQR, `tag="ACCOUNT_UPDATE"` cho subscription outbound
- [ ] **Channel-specific copy templates** (§7.5): module `copy/` với Telegram + Messenger variant
- [ ] **Privacy policy update** (§6.7): thêm Messenger section, deploy ở `https://fintrack.app/privacy`, link trong Page About + persistent menu
- [ ] Internal test: founder signup Messenger account, full E2E (signup → SePay/email → categorize → reports → `/upgrade` → subscription payment match)
- [ ] Polish: persistent menu, welcome screen, error handling
- [ ] App Review feedback iteration

**Buffer Tuần 12:** Phase 6 cũ (deploy + payment + admin tools) — không thêm work cho Messenger ngoài "deploy production cho cả 2 channel".

### Phase 7: Beta (Tuần 13–14)

Beta 5–10 user, ít nhất 2 user signup qua Messenger (validate flow).

---

## 9. Acceptance Criteria

### 9.1. Functional

- [ ] User signup qua `m.me/FinTrackPage` → tạo row với `channel_type='messenger'` + `channel_user_id=<psid>`
- [ ] User signup qua `t.me/FinTrackBot` → tạo row với `channel_type='telegram'` + `channel_user_id=<telegram_id>`
- [ ] 1 PSID không thể tạo 2 account (`UNIQUE(channel_type, channel_user_id)`)
- [ ] User Messenger nhận transaction notification, click quick reply category → categorized đúng → reflect trong `/status`
- [ ] User Messenger gọi `/status` qua persistent menu → reply text format identical Telegram
- [ ] Daily recap fire 23:00 local cho cả Telegram + Messenger user
- [ ] Path A/B/C onboarding work identical 2 channel

### 9.2. Multi-channel data isolation

- [ ] User Telegram A và user Messenger B có data hoàn toàn isolated
- [ ] User block Messenger Page → bot detect error code 10 → set `users.invalid_channel=true`, ngừng outbound
- [ ] User unsubscribe Page rồi resubscribe → vẫn nhận message (cùng PSID)

### 9.3. Meta compliance

- [ ] Meta App Review pass `pages_messaging` + `pages_messaging_subscriptions`
- [ ] Outbound trong 24h window dùng `messaging_type=RESPONSE`
- [ ] Outbound ngoài 24h dùng `messaging_type=MESSAGE_TAG` + tag `ACCOUNT_UPDATE` (hoặc tương đương)
- [ ] Signature `X-Hub-Signature-256` verify cho mọi POST `/webhook/messenger`
- [ ] Privacy policy URL accessible + linked trong Page About + persistent menu Help

### 9.4. Adapter pattern

- [ ] Grep handler/service files: 0 hit `requests.post.*graph.facebook.com` hoặc `httpx.*graph.facebook.com` ngoài `services/channels/messenger.py`
- [ ] Grep: 0 hit `tg.send_*` hoặc `bot{token}` ngoài `services/channels/telegram.py`
- [ ] Add channel mới (vd Zalo) chỉ cần thêm 1 file `services/channels/zalo.py` + 1 entry `_SENDERS` dict + 1 enum value `chk_channel_type` — KHÔNG đụng handlers

### 9.5. Performance

- [ ] Messenger reply latency < 2s p95 (cùng target Telegram)
- [ ] App memory không tăng quá 50MB so với Telegram-only baseline (adapter pattern lightweight)

---

## 10. Testing strategy

### 10.1. Unit tests

| Module | Test focus |
|---|---|
| `parsers/messenger_payload.py` | Parse 20+ payload mẫu Meta (message text, postback, quick reply, attachment, multi-event entry) |
| `services/channels/messenger.py` | Adapter quick reply flatten/truncate, 24h window logic, retry on rate limit |
| `services/messenger.py` | Channel routing (Telegram user → TelegramSender, Messenger user → MessengerSender) |
| `handlers/messenger_webhook.py` | Signature verify (valid + invalid + missing header) |

### 10.2. Integration tests

| Flow | Steps |
|---|---|
| Messenger signup | Postback `GET_STARTED` → user row created → welcome message gửi đúng PSID |
| Messenger Path A onboarding | Path picker → Path A → webhook URL displayed |
| Messenger transaction | Mock SePay webhook cho user channel='messenger' → bot gửi quick reply picker tới PSID → click → categorized |
| Out-of-24h window | Mock `last_user_message_at = NOW() - 30h` → outbound dùng MESSAGE_TAG |
| Block user | Mock Send API trả error 10 → `users.invalid_channel=true` |

### 10.3. End-to-end manual

- [ ] Founder beta account qua Messenger: signup → connect SePay → 5 transactions over 1 week → daily recap fire correctly → upgrade flow → reset
- [ ] Same flow trên Telegram, compare UX parity

### 10.4. App Review walkthrough video

Quay 2–3 phút screencast: user "Get Started" → bot welcome → onboard Path A → mock transaction → category picker → confirmation. Submit kèm app review.

---

## 11. Risks & mitigations

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | App Review reject hoặc kéo dài >2 tuần | Trung bình | **KHÔNG block MVP launch** vì decoupled qua `ENABLE_MESSENGER_CHANNEL` flag (xem §13.2 ramp stages). Telegram primary launch theo timeline 16 tuần BRD. Messenger code ship ở Phase 6 với flag `false`, flip ON khi App Review approve (có thể Phase 7, Phase 8, hoặc post-launch). Submit sớm Tuần 10 đầu để review chạy parallel với dev. Reject case: iterate feedback, resubmit; worst case extreme: Messenger defer Phase 2, Zalo accelerate. |
| 2 | Meta thay đổi 24h rule / message tag policy | Thấp | Outbound proactive (recap, reminder) bị limit | Theo dõi Meta changelog quarterly. Email + Telegram là fallback notification channel cho Messenger user nếu cần. |
| 3 | User block Page → silent failure | Trung bình | User không nhận tx noti, churn | Detect error code 10 → bot tự gửi email recovery link tới `inbound_email` của user (nếu có) hoặc mark `invalid_channel=true` cho admin tool follow-up |
| 4 | PSID-to-channel-user collision với Telegram telegram_id | Rất thấp | DB constraint conflict | UNIQUE pair `(channel_type, channel_user_id)` — collision impossible at DB level |
| 5 | Quick reply UX nghèo hơn Telegram inline keyboard (max 13 button, 20 char title) | Cao | Một số category list dài bị cắt | Implement multi-message split khi >13 button. Truncate name +... với confirmation dialog. |
| 6 | Messenger bot bị Meta suspend (similar Telegram suspension risk) | Thấp | Toàn user Messenger offline | Out-of-band notification qua Telegram channel `@FinTrackUpdates` + email Postmark gửi tới `inbound_email`. Plan B: tăng tốc launch Zalo Phase 2. |
| 7 | Founder mất ownership Facebook Page (account hijack) | Rất thấp | Loss of channel | Page ownership multiple admin (founder + 1 trusted contact). 2FA + recovery codes documented in DR runbook. |
| 8 | Việc xử lý gửi đa kênh tăng complexity test surface 2x | Cao | Bug đặc thù 1 channel slip qua | Test matrix mỗi feature × 2 channel (parity AC §10.3). CI run cả 2 adapter mock. |

---

## 12. Cost impact

| Item | Cost | Note |
|---|---|---|
| Facebook Page + Developer App | $0 | Free |
| Meta App Review | $0 | Free, chỉ tốn time |
| Outbound message Send API | $0 | Free trong policy compliance |
| App icon design | $0–50 | Có thể tự design hoặc thuê Fiverr |
| Privacy policy review | $0 | Reuse từ Telegram launch |
| Engineer time | +2 tuần dev (Tuần 10–11) | Trong scope MVP timeline 12 tuần |
| Ongoing ops | $0/mo | Không có managed service phí |

**Tổng ảnh hưởng monthly cost:** $0. Đây là lý do build Messenger song song MVP cost-effective — phí duy nhất là time.

---

## 13. Rollout plan

### 13.1. Feature flag — Messenger public launch decoupled từ MVP

```python
# config.py
ENABLE_MESSENGER_CHANNEL = os.getenv("ENABLE_MESSENGER_CHANNEL", "false").lower() == "true"
```

**Critical principle:** Messenger **code ship trong Phase 6 MVP**, nhưng **public access flip ON sau khi Meta App Review approve**, KHÔNG block MVP launch. Telegram là primary launch channel.

Flag `false` behavior:
- Onboarding flow đầu vào kiểm tra flag → Messenger Page hiện "Coming soon" message thay vì proceed signup
- Webhook endpoint `/webhook/messenger` vẫn deployed (nhận Meta verify GET) nhưng POST events return 200 + log "channel disabled"
- Existing user `channel_type='messenger'` (vd founder dogfood admin) vẫn nhận outbound bình thường nếu listed trong `ADMIN_TELEGRAM_IDS` whitelist

### 13.2. Ramp stages (Telegram + Messenger độc lập)

| Stage | Trigger | Action — Telegram | Action — Messenger |
|---|---|---|---|
| 0 — Code ship | Tuần 11 cuối Phase 6 | Code complete | Code complete, `ENABLE_MESSENGER_CHANNEL=false`, App Review submitted Tuần 10 |
| 1 — Closed beta | Phase 7 Tuần 13–14 | Public beta 5–10 user qua `t.me/FinTrackBot` | Founder + admin whitelist only (flag false toàn bộ user). Continue App Review iteration nếu reject |
| 2 — MVP soft launch | Phase 8 Tuần 15–16 | Public 20–30 user trên Telegram | **If App Review approved at this point:** flip flag ON, beta 5 user Messenger để validate parity. **If still pending:** continue Telegram-only soft launch, không delay. |
| 3 — Messenger soft launch | Post-MVP, sau App Review approve + 1 tuần beta validation | Continue | Public Page link, marketing mention Messenger as alternative |
| 4 — Both channel GA | Stable cả 2 channel >2 tuần | Continue | Marketing equally giới thiệu cả 2 channel |

**Decoupling guarantee:** Telegram launch theo BRD timeline 16 tuần. Bất kể Meta App Review status (pending, reject, approve), Telegram public launch không bị ảnh hưởng. Nếu App Review reject hoàn toàn → Messenger defer Phase 2, accelerate Zalo evaluation.

### 13.3. Rollback plan

Nếu Messenger gặp incident nghiêm trọng (vd app review revoke, Meta policy change):

1. Set `ENABLE_MESSENGER_CHANNEL=false` → block new signup
2. Existing Messenger user nhận pinned message giải thích + offer migrate sang Telegram (manual support)
3. Telegram-only operation continue, không ảnh hưởng

DB không phải rollback vì `channel_type` column có thể giữ data lịch sử cho user Messenger inactive.

---

## 14. Open questions

| # | Question | Status | Note |
|---|---|---|---|
| 1 | Tên Facebook Page chính thức? Cùng `@FinTrackBot` hay khác (vd `FinTrack`)? | ⏸️ Deferred | Quyết định trước Tuần 10 (lúc tạo Page). Không block design code. |
| 2 | Privacy policy có cần update để mention Meta data processing không? | ✅ Yes | Resolved §6.7 — required cho App Review. Action items listed. |
| 3 | Có cần phân biệt UX Telegram vs Messenger trong copywriting? | ✅ Yes | Resolved §7.5 — UX parity matrix định nghĩa rõ chỗ identical/divergent + copy template pattern 2 variant. |
| 4 | Marketing acquisition channel cho Messenger users? Facebook Ads vào Page link? | ⏸️ Deferred | Phase 7 post-launch decision. Không block MVP build. |
| 5 | Có nên gửi same upgrade email tới user Messenger qua Postmark (nếu họ provide email) không? | ⏸️ Deferred | Phase 6/7 — pending cân nhắc UX. Hiện tại Messenger user không có email collected; nếu cần gửi email phải prompt user nhập trong onboarding. |
| 6 | Khi user Messenger `/upgrade` (subscription payment), ref code có vấn đề gì khác không? | ✅ Resolved §6.6 | Scope: CHỈ subscription payment flow, không phải transaction tracking. 4 chỗ cần adapter Messenger riêng: ref code display, VietQR image, deeplink, MESSAGE_TAG ngoài window. Ref format không thay đổi. Transaction tracking flow không có ref code/VietQR — bot hoàn toàn passive nhận webhook từ SePay/email. |

---

## 15. References

- [BRD v2.9.0 §2.2 mục tiêu 4 + risk #2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md)
- [PRD v1.6.0 §1.4 Bot ownership + §2.1–2.3 onboarding](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md)
- [TDD v1.6.0 §1.4 Outbound abstraction + §2.1 schema](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)
- [Feature Spec Refactor v1.3.0 §3.3 messenger interface AC](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-refactor-saas.md)
- [Feature Spec Payment v1.3.0 §2.4 VietQR + §5.1 upgrade flow](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-payment-bank-transfer.md)
- [Impl Plan VietQR+Email v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md)
- [Implementation Plan 500+ §C8 bot pool + §C9 outbound queue + §C10 channel adapter](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-500-users-and-more.md)
- [Meta Messenger Platform docs](https://developers.facebook.com/docs/messenger-platform/)
- [Meta Send API reference](https://developers.facebook.com/docs/messenger-platform/send-messages)
- [Meta Message Tags policy](https://developers.facebook.com/docs/messenger-platform/send-messages/message-tags)
- [Meta App Review](https://developers.facebook.com/docs/app-review/)

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-07 | Initial spec — Messenger build song song MVP Phase 1–6, single-channel per user, schema dùng `channel_type` + `channel_user_id`, adapter pattern qua `services/channels/`, Meta App Review trong Tuần 10. |
| v1.1.0 | 2026-05-07 | **Resolve open questions Q2/Q3/Q6 + thêm 3 section detail:** (1) §6.6 Payment flow Messenger-specific — ref code display standalone message, `send_image()` cho VietQR, banking deeplink fallback, MESSAGE_TAG `ACCOUNT_UPDATE` cho mọi payment outbound proactive (match notification, expiry warning, annual reminder, recurring renewal, grace warning, downgrade, refund). (2) §6.7 Privacy policy update required cho App Review — section riêng cho Messenger users, list PSID/message data, link Page About + persistent menu, PDPA cross-check tiếng Việt. (3) §7.5 UX parity matrix — 16 aspects định nghĩa rõ chỗ identical/divergent giữa 2 channel, copy template pattern 2 variant (`COPY[key][channel_type]`), AC parity. (4) §8 Phase 6 Tuần 11 thêm 3 task: payment Messenger adapter, channel-specific copy module, privacy policy deploy. (5) §14 mark Q2/Q3/Q6 ✅ resolved, Q1/Q4/Q5 ⏸️ deferred (không block build). (6) Header thêm cross-ref tới Feature Spec Payment v1.1.0. |
| v1.1.1 | 2026-05-07 | **Clarify §6.6 scope = subscription payment only:** rename §6.6 "Payment flow" → "Subscription payment flow" + thêm disclaimer block đầu section phân biệt rõ 2 flow tách biệt: (a) **Transaction tracking** (core, mọi user, bot passive nhận SePay/email webhook → categorize, không có ref code/VietQR) qua endpoint `/hook/{user_token}` → `tx_service` → `transactions` table; (b) **Subscription payment** (chỉ khi user `/upgrade`, có ref code + VietQR + MESSAGE_TAG concerns) qua endpoint `/hook/{PLATFORM_TOKEN}` → `payment_matcher` → `pending_payments`. Wording trong §6.6 thay "payment-related" → "subscription-related". §14 Q6 thêm clarification scope. Phase 6 Tuần 11 task rename "Payment Messenger adapter" → "Subscription payment Messenger adapter". |
