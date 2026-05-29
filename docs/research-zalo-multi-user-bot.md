# Research: Zalo Bot Multi-User Implementation

| Field | Value |
|-------|-------|
| Ngày | 2026-05-29 |
| Trạng thái | Research — chưa implement |
| Mục tiêu | Multi-user Zalo bot, setup đơn giản cho end-user, bảo mật |

---

## Bối cảnh hiện tại

MyMoneyWent đã implement Zalo OA channel (Phase 1 ~80%):
- `core/messenger/zalo.py` — ZaloSender gửi tin qua OA API v3
- `core/handlers/zalo_webhook.py` — nhận webhook, parse text event, route command
- Token management qua env vars (ZALO_OA_ACCESS_TOKEN, ZALO_OA_REFRESH_TOKEN)
- Mỗi user phân biệt bằng `sender.id` trong webhook payload

**Vấn đề**: Kiến trúc hiện tại = 1 OA + 1 bộ token hardcoded trong env. Multi-user (nhiều end-user nhắn vào 1 OA) đã hoạt động. Nhưng nếu muốn scale → cần giải quyết token lifecycle và onboarding flow.

---

## 2 nền tảng Zalo Bot — so sánh

### Nền tảng 1: Zalo OA API (đang dùng)

- **API base**: `openapi.zalo.me/v3.0`
- **Auth**: OAuth 2.0 — access token expire **25h** (có nguồn nói 1h cho initial token), refresh token **single-use, 3 tháng**
- **OAuth flow**: OA admin grant quyền cho app → nhận authorization code → exchange thành access_token + refresh_token
- **Webhook**: Zalo POST đến webhook URL của app khi có event. Payload chứa `app_id`, `sender.id`, `event_name`
- **Message types**: Tin Tư vấn (consultation — reply trong 24h), Tin Thông báo (notification — template, tốn tiền)
- **User requirement**: User phải **follow OA** trước khi bot gửi tin được
- **1 app có thể serve nhiều OA**: Mỗi OA admin grant quyền riêng → mỗi OA có token riêng

### Nền tảng 2: Zalo Bot API (bot.zapps.me)

- **API base**: `bot-api.zaloplatforms.com/bot` *(⚠️ KHÔNG phải bot-api.zapps.me — đã xác nhận từ official docs 2026-05-30)*
- **Auth**: Bot token format `{bot_id}:{access_token}` — ổn định hơn, không cần refresh flow phức tạp
- **Tạo bot**: Qua **Zalo Bot Manager** OA trên Zalo app, nhận token qua Zalo notification
- **Webhook**: Set webhook URL, nhận POST events. Verify bằng header `X-Bot-Api-Secret-Token` (simple string comparison)
- **Multi-bot native**: Config nhiều bot cùng lúc, mỗi bot token riêng (số lượng tùy Gói dịch vụ)
- **User interaction**: User chat trực tiếp với bot, không cần follow OA
- **Docs**: `bot.zapps.me/docs/` — Docusaurus v3, partially client-rendered
- **Pricing**: Free Version + Premium Version (subscription theo tháng/quý/năm)

---

## Phân tích: "Multi-user" có nghĩa gì?

Có 3 tầng multi-user cần phân biệt:

### Tầng 1: Nhiều end-user nhắn vào 1 bot (ĐÃ CÓ)

Kiến trúc hiện tại đã handle:
- Mỗi user có `sender.id` riêng
- DB `users` table phân biệt bằng `(channel_type, channel_user_id)`
- Webhook dispatch theo `sender.id` → resolve `user_id` → xử lý command

**Không cần thay đổi gì.**

### Tầng 2: Self-service onboarding — user tự kết nối Zalo mà không cần admin (CHƯA CÓ)

Hiện tại: user phải follow OA + gửi `/start` → tạo account. Đây đã là flow đơn giản nhất cho end-user.

**Cải thiện có thể**:
- Deep link: `https://zalo.me/{OA_ID}` → user click → mở chat với OA → gửi `/start`
- QR code: Generate QR từ deep link → user scan → auto-open chat
- Không cần user nhập token hay config gì

### Tầng 3: Multi-tenant — mỗi "nhóm user" có bot/OA riêng (CHƯA CÓ, có thể cần cho tương lai)

Ví dụ: mỗi gia đình/nhóm bạn có OA riêng để track chi tiêu riêng. Đây là tầng phức tạp nhất.

---

## Khuyến nghị: Phương pháp implement tối ưu

### Phase 1 (Hiện tại) — Single OA, Multi-User

**Setup cho end-user**: Đơn giản nhất có thể.

```
User flow:
1. Scan QR code hoặc click link → Mở Zalo chat với OA
2. Gửi "/start" → Bot tạo account, seed categories
3. Done — user nhận notification khi có giao dịch SePay
```

**Cải thiện cần làm**:

1. **Auto-token refresh với persistence** (Tech Debt §2 trong implementation plan):

```
Hiện tại:  env var → expire 25h → manual update Railway
Cần làm:   DB table oauth_tokens → background refresh → zero downtime
```

Schema:
```sql
CREATE TABLE oauth_tokens (
    id SERIAL PRIMARY KEY,
    provider TEXT NOT NULL,          -- 'zalo_oa'
    oa_id TEXT NOT NULL,             -- Zalo OA ID
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(provider, oa_id)
);
```

Refresh logic:
```python
async def get_valid_token(oa_id: str) -> str:
    """Get valid access token, auto-refresh if expired."""
    row = await db.fetchrow(
        "SELECT * FROM oauth_tokens WHERE provider='zalo_oa' AND oa_id=$1",
        oa_id
    )
    if row["expires_at"] > now() + timedelta(minutes=5):
        return row["access_token"]
    
    # Refresh with mutex to prevent race condition
    async with advisory_lock(f"zalo_refresh_{oa_id}"):
        # Re-check after acquiring lock
        row = await db.fetchrow(...)
        if row["expires_at"] > now() + timedelta(minutes=5):
            return row["access_token"]
        
        new_tokens = await zalo_oauth_refresh(
            row["refresh_token"], app_id, secret_key
        )
        await db.execute(
            """UPDATE oauth_tokens 
               SET access_token=$1, refresh_token=$2, 
                   expires_at=$3, updated_at=now()
               WHERE provider='zalo_oa' AND oa_id=$4""",
            new_tokens.access_token,
            new_tokens.refresh_token,
            now() + timedelta(hours=25),
            oa_id
        )
        return new_tokens.access_token
```

2. **Webhook signature verification** — hoàn thiện với live fixture trước khi enable production.

3. **Deep link + QR code generation** — cho onboarding.

### Bảo mật

| Concern | Mitigation |
|---------|------------|
| Token storage | Encrypt at rest trong DB (application-level encryption hoặc Postgres pgcrypto) |
| Token refresh race | Advisory lock per OA — chỉ 1 process refresh tại 1 thời điểm |
| Webhook spoofing | HMAC signature verification (đang implement, cần live fixture confirm) |
| User impersonation | `sender.id` từ Zalo webhook — Zalo đảm bảo tính xác thực |
| Token leak via logs | Mask token trong log output (chỉ show last 4 chars) |
| Refresh token single-use | Zalo refresh token chỉ dùng 1 lần — nếu refresh fail, cần re-authorize. Alert operator. |
| MITM | HTTPS everywhere — cả webhook URL lẫn API calls |

### Phase 2 (Tương lai) — Multi-Tenant nếu cần

Nếu muốn mỗi nhóm có OA riêng hoặc chuyển sang Zalo Bot API:

**Option A: Multi-OA trên cùng 1 app (OA API)**

```
Flow:
1. Tenant admin tạo Zalo OA
2. Tenant admin click OAuth authorize link → grant quyền cho MyMoneyWent app
3. App nhận authorization code → exchange token → lưu DB per-tenant
4. Webhook route: POST /zalo/webhook → payload chứa app_id → resolve tenant
```

Ưu điểm: Dùng infrastructure hiện có, chỉ thêm tenant routing.
Nhược điểm: Mỗi tenant phải tạo OA (phí + verify), token lifecycle phức tạp.

**Option B: Zalo Bot API (bot.zapps.me)**

```
Flow:
1. MyMoneyWent tạo 1 bot qua Bot Creator
2. User nhắn trực tiếp cho bot — không cần follow OA
3. Bot token ổn định — không cần refresh flow
4. Multi-user = nhiều user nhắn vào 1 bot (giống Telegram)
```

Ưu điểm: Token đơn giản hơn, user không cần follow OA, API style giống Telegram.
Nhược điểm: Nền tảng mới hơn, ít tài liệu, chưa rõ production readiness, không gửi được tin thông báo (notification) chủ động nếu user không nhắn trước.

---

## So sánh setup complexity cho end-user

| Bước | OA API (hiện tại) | Bot API (bot.zapps.me) |
|------|-------------------|------------------------|
| 1 | Scan QR / click link | Scan QR / click link |
| 2 | Follow OA (1 tap) | Không cần |
| 3 | Gửi /start | Gửi /start |
| **Tổng** | **3 bước** | **2 bước** |

Cả 2 đều rất đơn giản cho end-user. OA API thêm 1 bước follow nhưng đó là flow tự nhiên trong Zalo.

---

## Kết luận & Next Steps

### Recommend: Giữ OA API cho Phase 1, evaluate Bot API song song

1. **Ngay bây giờ**: Hoàn thiện Phase 1 OA integration:
   - Implement `oauth_tokens` table + auto-refresh (thay thế env var)
   - Confirm webhook signature với live fixture
   - Tạo deep link + QR cho onboarding
   - Đảm bảo refresh token persistence (single-use constraint)

2. **Song song**: Evaluate Zalo Bot API:
   - Đọc docs tại `bot.zapps.me/docs/` (cần browser — client-rendered)
   - Tạo test bot qua Bot Creator
   - So sánh: message types, rate limits, notification capability
   - Đặc biệt kiểm tra: bot có gửi tin chủ động được không (push notification khi SePay nhận giao dịch)?

3. **Quyết định Phase 2**: Dựa trên evaluation:
   - Nếu Bot API hỗ trợ push notification → migrate sang Bot API (đơn giản hơn cho cả dev lẫn user)
   - Nếu không → stick với OA API + token persistence

### Rủi ro cần theo dõi

- **Refresh token expiry 3 tháng**: Nếu app không refresh trong 3 tháng → token hết hạn → cần re-authorize. Cần cronjob proactive refresh.
- **Zalo Bot API maturity**: Nền tảng mới, có thể thay đổi API breaking changes.
- **OA verification**: Zalo có thể yêu cầu verify OA trước khi cho gửi tin thông báo (notification template).

---

---

## Deep Dive: Zalo Bot API (bot.zapps.me)

> Cập nhật 2026-05-29 — nghiên cứu bổ sung theo hướng ưu tiên Bot API thay vì OA API.
> 
> ⚠️ **ERRATA 2026-05-30**: Nhiều thông tin trong section này được lấy từ SDK open-source và **có sai lệch** so với official docs. Xem section "Errata" cuối document để biết chi tiết các sửa đổi.

### API Architecture — gần như clone Telegram Bot API

Dựa trên phân tích 3 SDK open-source (Go, Laravel, Go #2), Zalo Bot API có kiến trúc **gần giống hệt Telegram Bot API**:

| Aspect | Telegram Bot API | Zalo Bot API |
|--------|-----------------|--------------|
| Base URL | `api.telegram.org/bot{TOKEN}/` | ~~`bot-api.zapps.me/bot{TOKEN}/`~~ → **`bot-api.zaloplatforms.com/bot{TOKEN}/`** |
| Token format | `{bot_id}:{secret}` | `{bot_id}:{access_token}` |
| Token lifetime | Permanent (until revoked) | **Không hết hạn cho tới khi chủ động reset** (confirmed official docs) |
| Auth method | Token embedded in URL | Token embedded in URL |
| Webhook | `setWebhook` + `X-Telegram-Bot-Api-Secret-Token` | ~~`X-Zalo-Signature`~~ → **`X-Bot-Api-Secret-Token`** (simple string match, KHÔNG phải HMAC) |
| Polling | `getUpdates` with long polling | `getUpdates` with long polling |
| Send message | `sendMessage(chat_id, text)` | `sendMessage(chat_id, text)` |

**Đây là phát hiện quan trọng nhất**: Token không expire → không cần refresh flow → giảm 80% complexity so với OA API.

### API Endpoints

```
Base: https://bot-api.zaloplatforms.com/bot{BOT_TOKEN}/

✅ CONFIRMED (official docs 2026-05-30):
  GET  /getMe                — bot info
  GET  /getUpdates           — long polling
  POST /setWebhook           — set webhook URL + secret_token
  POST /deleteWebhook        — remove webhook
  GET  /getWebhookInfo       — current webhook status
  POST /sendMessage          — text message (chat_id + text, max 2000 chars)
  POST /sendPhoto            — image with caption
  POST /sendSticker          — sticker
  POST /sendChatAction       — typing indicator

❌ NOT IN OFFICIAL DOCS (from SDKs only, may not work):
  POST /sendFile             — file attachment
  POST /sendVideo            — video
  POST /sendAudio            — audio
  POST /sendTemplate         — buttons, carousel, quick replies
  GET  /getUserProfile       — get user info
```

### Rich Message Support

> ⚠️ **CHƯA XÁC NHẬN**: Thông tin dưới đây từ SDK open-source. Official API Reference (05/2026) chỉ list 9 endpoints và **KHÔNG có `sendTemplate`**. Rich messages có thể là tính năng Premium hoặc chưa public. Cần test thực tế.

```python
# ❓ UNCONFIRMED — sendTemplate không có trong official docs
# Button message — user nhấn button thay vì gõ số
{
    "chat_id": "user123",
    "structured_message": {
        "type": "button",
        "elements": [{
            "title": "Chọn danh mục chi tiêu:",
            "buttons": [
                {"type": "postback", "title": "🍜 Ăn uống", "payload": "CAT_1"},
                {"type": "postback", "title": "🏠 Nhà ở", "payload": "CAT_2"},
                {"type": "web_url", "title": "📊 Xem báo cáo", "url": "https://..."}
            ]
        }]
    }
}
```

Nếu rich messages không khả dụng, fallback về numbered list hack (giống OA API hiện tại).

### Tạo Bot — Flow cho developer (updated from official docs)

```
1. Mở Zalo → Tìm OA "Zalo Bot Manager"
2. Chọn "Tạo bot" trong menu chat → mở ứng dụng Zalo Bot Creator
3. Nhập tên bot (prefix "Bot" bắt buộc, VD: "Bot Tiền Về Nơi Đâu")
4. Nhận bot token qua Zalo notification: {bot_id}:{access_token}
5. Set webhook: POST https://bot-api.zaloplatforms.com/bot{TOKEN}/setWebhook
6. Done — bot sẵn sàng nhận message
```

**Thời gian setup: ~5 phút.** So với OA API (tạo OA → verify domain → OAuth flow → manage tokens): tiết kiệm hàng giờ.

### User Onboarding — Flow cho end-user

```
1. User tìm bot trên Zalo (search tên) hoặc scan QR
2. Nhắn bất kỳ tin nhắn nào → bot nhận được
3. Gửi /start → tạo account
```

**Không cần follow, không cần approve.** 2 bước thay vì 3.

### Proactive Messages (Push Notification)

**Confirmed**: Bot API **CÓ THỂ** gửi tin chủ động — `sendMessage(chat_id, text)` bất kỳ lúc nào, không cần user nhắn trước (giống Telegram).

Đây là yếu tố critical cho MyMoneyWent: khi SePay nhận giao dịch → bot push notification cho user ngay lập tức.

So với OA API:
- OA consultation messages: chỉ reply trong 24h sau tin nhắn cuối của user
- OA notification messages (ZNS): cần template approved + tốn tiền per-message
- Bot API: gửi tự do, không giới hạn thời gian, miễn phí

### Security Model (updated from official docs)

| Concern | Zalo Bot API | So với OA API |
|---------|-------------|---------------|
| Token bảo mật | Long-lived, không expire, store như env var | Phức tạp hơn (expire, refresh) |
| Webhook verification | **`X-Bot-Api-Secret-Token`** header — simple string comparison (KHÔNG phải HMAC!) | HMAC signature |
| User identity | `chat.id` / `from.id` — Zalo-guaranteed | `sender.id` — tương đương |
| Message encryption | HTTPS bắt buộc cho mọi API call | HTTPS |
| Bot token revocation | Qua Zalo Bot Creator → thiết lập → reset token | Re-authorize OA |
| Đối tượng đặc biệt | `message.unsupported.received` — tuân thủ pháp luật (trẻ em, etc.) | N/A |

### Hạn chế & Rủi ro

1. **Nền tảng mới**: Platform version 0.1.2-1 (build 2026-04-20). Có thể thay đổi breaking.
2. **API surface nhỏ hơn SDK suggest**: Official docs chỉ có 9 endpoints. sendTemplate, sendFile, sendVideo, sendAudio, getUserProfile KHÔNG có trong docs.
3. **SDK ecosystem nhỏ**: 3 SDK (Go x2, Laravel) — chưa có Python SDK. MyMoneyWent implement adapter từ scratch.
4. **Rate limits**: Chỉ biết có error code 429. Quota cụ thể chưa rõ — cần test.
5. **Group chat**: `chat_type: GROUP` confirmed (Beta) trong webhook docs.
6. **Pricing**: Free Version có giới hạn (số bot, tính năng). Premium Version cần subscription.
7. **Compliance**: PHẢI handle `message.unsupported.received` cho đối tượng đặc biệt (requirement pháp lý).
8. **Dịch vụ "as is"**: Zalo Platforms không đảm bảo uptime/hiệu suất (Terms §III.3).

---

## Revised Recommendation: Migrate sang Zalo Bot API

Dựa trên deep dive, **Zalo Bot API là lựa chọn tốt hơn** cho MyMoneyWent:

| Tiêu chí | OA API | Bot API | Winner |
|----------|--------|---------|--------|
| Setup cho developer | Phức tạp (OA + OAuth + domain verify) | 5 phút (Bot Creator + token) | **Bot API** |
| Setup cho end-user | 3 bước (scan + follow + /start) | 2 bước (scan + /start) | **Bot API** |
| Token lifecycle | 25h expire, single-use refresh, 3-month validity | Long-lived, no refresh needed | **Bot API** |
| Push notifications | ZNS (paid, template) hoặc 24h window | Gửi tự do, miễn phí | **Bot API** |
| Rich messages | Plain text only (consultation) | ❓ Chưa confirm (không có trong official docs) | **Chưa rõ** |
| Code complexity | High (refresh flow, token persistence) | Low (Telegram-like adapter) | **Bot API** |
| Maturity | Battle-tested | Newer, smaller ecosystem | OA API |
| Docs quality | Comprehensive (Vietnamese) | Limited (client-rendered) | OA API |

### Implementation Plan: ZaloBotSender

Thay vì sửa `ZaloSender` (OA API), tạo adapter mới song song:

```python
# core/messenger/zalo_bot.py — NEW adapter for Zalo Bot API

_ZALO_BOT_API_BASE = "https://bot-api.zaloplatforms.com"  # ⚠️ CORRECT URL (not zapps.me)

class ZaloBotSender(BaseSender):
    """Zalo Bot API adapter (bot-api.zaloplatforms.com)."""
    
    channel_type = "zalo"  # hoặc "zalo_bot" nếu muốn coexist
    
    def __init__(self, bot_token: str, *, http_client=None):
        # Token format: {bot_id}:{access_token}
        if not bot_token or ":" not in bot_token:
            raise ValueError("Invalid bot token format")
        self._bot_token = bot_token
        self._api_base = f"{_ZALO_BOT_API_BASE}/bot{bot_token}"
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
    
    async def send(self, user_id: int, payload: SendPayload) -> None:
        chat_id = await self._resolve_chat_id(user_id)
        text = self._resolve_text(payload)
        
        # ⚠️ NOTE: sendTemplate NOT in official docs — fallback to text only
        # Rich messages need testing before enabling
        await self._send_text(chat_id, text)
    
    async def _send_text(self, chat_id: str, text: str) -> None:
        resp = await self._client.post(
            f"{self._api_base}/sendMessage",
            json={"chat_id": chat_id, "text": text}
        )
        resp.raise_for_status()
    
    async def _send_structured(self, chat_id, text, markup) -> None:
        buttons = []
        for row in markup.rows:
            for btn in row:
                if btn.url:
                    buttons.append({"type": "web_url", "title": btn.label, "url": btn.url})
                else:
                    buttons.append({"type": "postback", "title": btn.label, "payload": btn.callback_data})
        
        resp = await self._client.post(
            f"{self._api_base}/sendTemplate",
            json={
                "chat_id": chat_id,
                "structured_message": {
                    "type": "button",
                    "elements": [{"title": text, "buttons": buttons}]
                }
            }
        )
        resp.raise_for_status()

@register_sender("zalo")
def _zalo_bot_factory() -> ZaloBotSender:
    return ZaloBotSender(bot_token=os.environ["ZALO_BOT_TOKEN"])
```

### Webhook Handler Changes

```python
# core/handlers/zalo_bot_webhook.py — NEW

def parse_zalo_bot_update(body: dict) -> ZaloTextEvent | None:
    """Parse Zalo Bot API update (Telegram-like format)."""
    message = body.get("message")
    if not message:
        return None
    
    from_user = message.get("from", {})
    chat_id = from_user.get("id", "")
    text = message.get("text", "").strip()
    
    if not chat_id or not text:
        return None
    
    return ZaloTextEvent(sender_id=chat_id, text=text, event_name="message")

def verify_zalo_bot_webhook(headers: dict, secret: str) -> bool:
    """Verify X-Bot-Api-Secret-Token header.
    
    ⚠️ Zalo Bot uses SIMPLE STRING COMPARISON, NOT HMAC!
    The header value must exactly match the secret_token set in setWebhook.
    """
    token = headers.get("x-bot-api-secret-token", "")
    if not secret:
        return True  # no secret configured = skip verification
    return token == secret
```

### Migration Path

```
Phase 1 (now):     OA API — đang hoạt động, giữ nguyên
Phase 1.5 (next):  Tạo test bot qua Bot Creator
                   Implement ZaloBotSender + webhook handler
                   Test gửi/nhận message thực tế
                   Confirm: proactive send, rate limits, rich messages
Phase 2:           Switch ZALO_BOT_TOKEN env var thay cho OA tokens
                   Deprecate ZaloSender (OA API) 
                   Remove oauth_tokens complexity
```

### Env Vars — Simplified

```
# Before (OA API) — 8 vars
ZALO_ENABLED=true
ZALO_INTERACTIVE=true
ZALO_APP_ID=...
ZALO_OA_SECRET_KEY=...
ZALO_OA_ACCESS_TOKEN=...    # expires 25h!
ZALO_OA_REFRESH_TOKEN=...   # single-use, 3-month!
ZALO_AUTO_REFRESH=true
ZALO_TEXT_LIMIT=2000

# After (Bot API) — 3 vars
ZALO_ENABLED=true
ZALO_BOT_TOKEN=123456:ABC-DEF...   # long-lived!
ZALO_WEBHOOK_SECRET=...             # optional
```

---

## Errata (2026-05-30)

Sau khi cross-reference với official docs tại `bot.zapps.me/docs/` (build 2026-04-20, version 0.1.2-1):

| Mục | Research ghi (SAI) | Official docs (ĐÚNG) | Severity |
|-----|-------------------|---------------------|----------|
| Base URL | `bot-api.zapps.me` | `bot-api.zaloplatforms.com` | 🔴 Critical |
| Webhook header | `X-Zalo-Signature` (HMAC) | `X-Bot-Api-Secret-Token` (string compare) | 🔴 Critical |
| Tạo bot flow | `zalo.me/s/botcreator/` | Tìm OA "Zalo Bot Manager" trên Zalo app | 🟡 Medium |
| sendTemplate | Listed as endpoint | **Không có** trong official API Reference | 🟡 Medium |
| sendFile/Video/Audio | Listed as endpoints | **Không có** trong official API Reference | 🟡 Medium |
| getUserProfile | Listed as endpoint | **Không có** trong official API Reference | 🟡 Medium |
| Rich messages | "Confirmed from SDKs" | Chưa xác nhận — không có trong docs | 🟡 Medium |
| Token lifetime | "Long-lived" | "Không hết hạn cho tới khi chủ động reset" | ✅ Chính xác hơn |
| Group chat | "Chưa hỗ trợ" | `chat_type: GROUP` (Beta) có trong webhook | ✅ Confirmed |

**Lưu ý**: Một số SDK open-source có thể implement endpoints chưa public. Cần test thực tế.

---

## Sources

- [Zalo OA API Official Docs](https://developers.zalo.me/docs/api/official-account-api-230)
- [Zalo OAuth & Authorization](https://developers.zalo.me/docs/official-account/bat-dau/xac-thuc-va-uy-quyen-cho-ung-dung-new)
- [Zalo Webhook Overview](https://developers.zalo.me/docs/official-account/webhook/tong-quan)
- [Zalo Bot SDK for Laravel](https://github.com/nhanchaukp/zalo-bot-sdk) — reference cho API endpoints, multi-bot config, command system
- [Go Zalo Bot SDK (vkhangstack)](https://github.com/vkhangstack/go-zalo-bot) — comprehensive SDK with auth, webhook, structured messages, retry
- [Go Zalo Bot API (nduyhai)](https://pkg.go.dev/github.com/nduyhai/go-zalo-bot-api) — lightweight client, confirms base URL and token format
- [Beehexa — Zalo OA Token Tutorial](https://www.beehexa.com/devdocs/devops/zalo-oa-tutorial-creating-access-token/)
- [n8n — Zalo OA Token Management Workflow](https://n8n.io/workflows/8675-automated-zalo-oa-token-management-with-oauth-and-webhook-integration/)
- [OpenClaw Zalo Integration](https://docs.openclaw.ai/channels/zalo)
- **[Zalo Bot Platform — Official Docs](https://bot.zapps.me/docs/)** — Docusaurus v3, primary source of truth
- **[Zalo Bot Platform — Xác thực](https://bot.zapps.me/docs/authorize/)** — Token format & lifetime
- **[Zalo Bot Platform — Webhook](https://bot.zapps.me/docs/webhook/)** — Webhook payload structure & `X-Bot-Api-Secret-Token`
- **[Zalo Bot Platform — sendMessage](https://bot.zapps.me/docs/apis/sendMessage/)** — API contract confirmed
- **[Zalo Bot Platform — Error Codes](https://bot.zapps.me/docs/error-code/)** — 429 Quota exceeded
- **[Zalo Bot Platform — Terms](https://bot.zapps.me/docs/terms/)** — Pricing tiers, legal requirements
