# BE Tech Doc: Messenger Channel

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_messenger_channel.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md)
> **Impl plan:** [implementation_plan_messenger.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation_plan_messenger.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Adapter | `services/channels/messenger.py` | MessengerSender (Meta Send API) |

> **Discord adapter:** Xem [feature_discord_channel_tech.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature_discord_channel_tech.md) cho Discord channel implementation (slash commands + embeds + Ed25519).
| Webhook | `handlers/messenger_webhook.py` | Signature verify + dispatch |
| Parser | `parsers/messenger_payload.py` | Meta event → internal Update |
| Menu Script | `scripts/setup_messenger_persistent_menu.py` | One-shot persistent menu |
| Copy | `copy/` | Channel-specific message templates |

---

## 2. Database Schema

### 2.1. Schema (already shipped Phase 1)

```sql
-- users table additions (multi-channel)
channel_type VARCHAR(16) NOT NULL,        -- 'telegram' | 'messenger'
channel_user_id VARCHAR(64) NOT NULL,     -- telegram_id (str) | PSID
last_user_message_at TIMESTAMPTZ,         -- 24h window tracking
invalid_channel BOOLEAN DEFAULT FALSE,    -- blocked Page
UNIQUE (channel_type, channel_user_id)
```

### 2.2. Key Queries

```sql
-- Create Messenger user
INSERT INTO users (channel_type, channel_user_id, webhook_token, plan, trial_ends_at)
VALUES ('messenger', $1, $2, 'free', NOW() + INTERVAL '14 days')
ON CONFLICT (channel_type, channel_user_id) DO NOTHING RETURNING *;

-- Update last message timestamp
UPDATE users SET last_user_message_at = NOW() WHERE id = $1;

-- Check 24h window
SELECT last_user_message_at FROM users WHERE id = $1;

-- Mark invalid channel
UPDATE users SET invalid_channel = TRUE WHERE channel_type = 'messenger' AND channel_user_id = $1;
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | >13 quick replies | Multi-message split |
| 2 | Data Integrity | User blocked Page | Error 10 → invalid_channel |
| 3 | Security | Signature verify fail | 200 OK + log warning |
| 4 | Cross-Feature | No inline code | Ref as standalone message |
| 5 | Cross-Feature | Markdown in text | Strip → plain text |
| 6 | Cross-Feature | Edit not supported | Send new + optional delete old |
| 7 | Data Integrity | Quick reply disappears | Resend on re-prompt |
| 8 | Cross-Feature | Image attachment | type=image + URL |
| 9 | Security | PSID collision | (channel_type, channel_user_id) UNIQUE |
| 10 | Cross-Feature | Feature flag OFF | 200 + "channel disabled" |
| 11 | Data Integrity | Delivery/read receipt | Skip silent |
| 12 | Concurrency | Webhook retry (Meta) | Idempotent processing |
| 13 | Cross-Feature | 24h window expired | MESSAGE_TAG ACCOUNT_UPDATE |
| 14 | Data Integrity | Multi-entry webhook | Process each entry |

---

## 3. API Contract

### 3.1. Endpoints

```python
# GET /webhook/messenger — verification
@app.get("/webhook/messenger")
async def messenger_verify(hub_mode, hub_verify_token, hub_challenge):
    if hub_mode == "subscribe" and hub_verify_token == FB_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    return Response(status_code=403)

# POST /webhook/messenger — events
@app.post("/webhook/messenger")
async def messenger_webhook(request: Request):
    if not verify_signature(request):
        return Response(status_code=200)  # Don't leak info
    payload = await request.json()
    for entry in payload.get('entry', []):
        for event in entry.get('messaging', []):
            await dispatch_messenger_event(event)
    return Response(status_code=200)
```

### 3.2. Signature Verification

```python
import hmac, hashlib
def verify_signature(request: Request) -> bool:
    signature = request.headers.get('X-Hub-Signature-256', '')
    if not signature.startswith('sha256='):
        return False
    body = await request.body()
    expected = 'sha256=' + hmac.new(FB_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

---

## 4. Implementation Details

### 4.1. 24h Window Logic

```python
def is_in_24h_window(user) -> bool:
    if not user.last_user_message_at:
        return False
    return (datetime.utcnow() - user.last_user_message_at).total_seconds() < 86400

def get_messaging_type(user, explicit_tag=None) -> tuple[str, str|None]:
    if explicit_tag:
        return 'MESSAGE_TAG', explicit_tag
    if is_in_24h_window(user):
        return 'RESPONSE', None
    return 'MESSAGE_TAG', 'ACCOUNT_UPDATE'
```

### 4.2. Quick Reply Multi-split

```python
MAX_QUICK_REPLIES = 13
def split_quick_replies(options, prompt):
    if len(options) <= MAX_QUICK_REPLIES:
        return [(prompt, options)]
    pages = []
    for i in range(0, len(options), MAX_QUICK_REPLIES - 1):
        chunk = options[i:i + MAX_QUICK_REPLIES - 1]
        if i + MAX_QUICK_REPLIES - 1 < len(options):
            chunk.append({"title": "Tiếp →", "payload": f"page:{i//12+2}"})
        pages.append((f"{prompt} ({i//12+1}/{-(-len(options)//(MAX_QUICK_REPLIES-1))})", chunk))
    return pages
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | GET verify valid | Correct token | 200 + challenge |
| 2 | GET verify invalid | Wrong token | 403 |
| 3 | POST valid signature | HMAC match | Events processed |
| 4 | POST invalid signature | HMAC mismatch | 200, events skipped |
| 5 | POST missing signature | No header | 200, events skipped |
| 6 | Parse text message | {message: {text: "hi"}} | Update(type=text) |
| 7 | Parse postback | {postback: {payload: "GET_STARTED"}} | Update(type=postback) |
| 8 | Parse quick reply | {message: {quick_reply: {}}} | Update(type=quick_reply) |
| 9 | Parse delivery receipt | {delivery: {}} | Skipped |
| 10 | Parse multi-entry | 2 entries | Both processed |
| 11 | send_text plain | "Hello" | Meta API called |
| 12 | send_text + replies | 5 quick replies | Correct format |
| 13 | send_text + 14 replies | 14 items | 2 messages |
| 14 | send_image | URL + caption | 2 messages (image + text) |
| 15 | 24h window in | Last msg 1h ago | messaging_type=RESPONSE |
| 16 | 24h window out | Last msg 30h ago | messaging_type=MESSAGE_TAG |
| 17 | 24h window never | NULL | MESSAGE_TAG |
| 18 | Error 10 blocked | Meta error 10 | invalid_channel=TRUE |
| 19 | Error 200 window | Window violation | Retry with TAG |
| 20 | Error 613 rate | Rate limited | Backoff 1s |
| 21 | Feature flag OFF | ENABLE_MESSENGER=false | 200 + log |
| 22 | Persistent menu | Setup script | 5 items configured |
| 23 | PSID uniqueness | Same PSID twice | ON CONFLICT skip |
| 24 | Markdown strip | "**bold** text" | "bold text" |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
