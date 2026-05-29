# Implementation Plan: Zalo Bot API Migration

| Field | Value |
|-------|-------|
| Version | v0.1.0 |
| Ngày | 2026-05-29 |
| Trạng thái | Draft — pending founder review |
| Prerequisite | Bot đã tạo qua Bot Creator, confirmed working |
| Liên quan | [research-zalo-multi-user-bot.md](research-zalo-multi-user-bot.md), [implementation-plan-zalo-channel-core.md](implementation-plan-zalo-channel-core.md) |

---

## Tóm tắt

Thay thế Zalo OA API adapter (`ZaloSender`) bằng Zalo Bot API adapter (`ZaloBotSender`). Mục tiêu: đơn giản hoá token management (long-lived token, không cần OAuth refresh), hỗ trợ rich messages (buttons thay vì numbered text), và push notification không giới hạn thời gian.

**Scope**: Sender adapter + webhook handler + env vars. Không thay đổi DB schema, không thay đổi `categorize.py` business logic, không thay đổi `handle_start`.

---

## Phân tích codebase hiện tại

### Điểm mạnh — abstraction layer rất sạch

Kiến trúc `core/messenger/` đã thiết kế đúng cho multi-channel:

```
SendPayload (abstract)          → BaseSender.send()
  ├─ text / text_key + i18n     → adapter resolves text
  ├─ Markup(rows=[Button()])    → adapter renders to platform format
  └─ parse_mode                 → adapter maps or strips
```

**Quan trọng**: `categorize.py` đã emit `Markup` với `Button(callback_data=...)`. Hiện tại `ZaloSender` (OA API) phải degrade thành numbered text vì OA consultation messages không hỗ trợ buttons. **Bot API hỗ trợ buttons natively** → `_render_markup()` output sẽ được render đúng cách mà không cần thay đổi `categorize.py`.

### Các file cần thay đổi

| File | Thay đổi | Lý do |
|------|----------|-------|
| `core/messenger/zalo.py` | **Rewrite** — thay ZaloSender bằng ZaloBotSender | Khác API hoàn toàn |
| `core/handlers/zalo_webhook.py` | **Rewrite** — parse Bot API update format | Payload format khác |
| `core/messenger/__init__.py` | Không đổi | Side-effect import `zalo` vẫn đúng |
| `core/handlers/categorize.py` | **Không đổi** | Abstract Markup → buttons tự động |
| `core/handlers/start.py` | **Không đổi** | `handle_start(channel_type="zalo", ...)` vẫn đúng |
| `core/messenger/send.py` | **Không đổi** | Registry dispatch vẫn đúng |
| `main.py` | **Sửa nhỏ** — webhook route payload parsing | FastAPI route handler |
| `.env.example` | **Update** — new env vars | Document new config |
| Tests | **Update** | New payload format |

### Các file KHÔNG cần đổi (xác nhận)

- `core/messenger/base.py` — contract không đổi
- `core/messenger/telegram.py` — không liên quan
- `core/services/user_svc.py` — `create_or_get_user` vẫn nhận `channel_type="zalo"`
- `core/services/bot_state.py` — state management vẫn đúng
- `i18n/` — tất cả i18n keys vẫn đúng
- DB schema — `channel_type='zalo'` trong CHECK constraint vẫn đúng
- Migration `0004_add_zalo_channel.py` — không cần migration mới

---

## Implementation Chi Tiết

### 1. `core/messenger/zalo.py` — Rewrite

```python
"""Zalo Bot API messenger adapter (bot-api.zapps.me)."""

from __future__ import annotations

import os
from typing import Any, cast

import httpx

from core import db
from core.logging import get_logger

from .base import BaseSender, Button, Markup, SendPayload, register_sender
from .i18n import t

_ZALO_BOT_API_BASE = "https://bot-api.zapps.me"

log = get_logger(__name__, component="zalo_bot_sender")


class ZaloBotSender(BaseSender):
    """Sends messages via the Zalo Bot API (Telegram-like)."""

    channel_type = "zalo"

    def __init__(
        self,
        bot_token: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        api_base: str = _ZALO_BOT_API_BASE,
    ) -> None:
        if not bot_token or ":" not in bot_token:
            raise ValueError(
                "ZaloBotSender: bot_token must be non-empty and contain ':' "
                "(format: {bot_id}:{access_token})"
            )
        self._bot_token = bot_token
        self._api_base = f"{api_base}/bot{bot_token}"
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ── Public send ───────────────────────────────────────────────

    async def send(self, user_id: int, payload: SendPayload) -> None:
        chat_id = await self._resolve_chat_id(user_id)
        locale = payload.get("locale", "vi")
        text = self._resolve_text(payload, locale)
        markup = payload.get("markup")

        if markup is not None and self._has_postback_buttons(markup):
            await self._send_structured(chat_id, text, markup, locale)
        else:
            if markup is not None:
                text = self._append_url_buttons(text, markup, locale)
            await self._send_text(chat_id, text)

    # ── API calls ─────────────────────────────────────────────────

    async def _send_text(self, chat_id: str, text: str) -> None:
        """POST /sendMessage — plain text."""
        resp = await self._client.post(
            f"{self._api_base}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        self._check_response(resp)

    async def _send_structured(
        self, chat_id: str, text: str, markup: Markup, locale: str
    ) -> None:
        """POST /sendTemplate — buttons via structured message."""
        buttons = self._markup_to_buttons(markup, locale)
        resp = await self._client.post(
            f"{self._api_base}/sendTemplate",
            json={
                "chat_id": chat_id,
                "structured_message": {
                    "type": "button",
                    "elements": [{"title": text, "buttons": buttons}],
                },
            },
        )
        self._check_response(resp)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _check_response(resp: httpx.Response) -> None:
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and not body.get("ok", True):
            raise RuntimeError(f"Zalo Bot API error: {body!r}")

    async def _resolve_chat_id(self, user_id: int) -> str:
        """Resolve DB user_id → Zalo chat_id string."""
        pool = db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT channel_chat_id, channel_user_id
                FROM users
                WHERE id = $1 AND channel_type = 'zalo';
                """,
                user_id,
            )
        if row is None:
            raise LookupError(f"zalo user_id={user_id} not found")
        chat_id = row["channel_chat_id"] or row["channel_user_id"]
        if not chat_id:
            raise LookupError(f"zalo user_id={user_id} has no chat_id")
        return cast(str, chat_id)

    @staticmethod
    def _resolve_text(payload: SendPayload, locale: str) -> str:
        if "text_key" in payload and payload["text_key"]:
            params = payload.get("text_params") or {}
            return t(payload["text_key"], locale, **params)
        return payload["text"]

    @staticmethod
    def _button_label(btn: Button, locale: str) -> str:
        if btn.label_key is not None:
            return t(btn.label_key, locale)
        return cast(str, btn.label)

    @staticmethod
    def _has_postback_buttons(markup: Markup) -> bool:
        """True if any button uses callback_data (interactive)."""
        return any(
            btn.callback_data is not None
            for row in markup.rows
            for btn in row
        )

    @classmethod
    def _markup_to_buttons(cls, markup: Markup, locale: str) -> list[dict[str, Any]]:
        """Convert abstract Markup → Zalo Bot API button array."""
        buttons: list[dict[str, Any]] = []
        for row in markup.rows:
            for btn in row:
                label = cls._button_label(btn, locale)
                if btn.callback_data is not None:
                    buttons.append({
                        "type": "postback",
                        "title": label,
                        "payload": btn.callback_data,
                    })
                elif btn.url is not None:
                    buttons.append({
                        "type": "web_url",
                        "title": label,
                        "url": btn.url,
                    })
        return buttons

    @classmethod
    def _append_url_buttons(cls, text: str, markup: Markup, locale: str) -> str:
        """Fallback: append URL buttons as plain text links."""
        lines = [text.rstrip(), ""]
        for row in markup.rows:
            for btn in row:
                label = cls._button_label(btn, locale)
                if btn.url is not None:
                    lines.append(f"{label}: {btn.url}")
        return "\n".join(lines).rstrip()


@register_sender("zalo")
def _zalo_factory() -> ZaloBotSender:
    return ZaloBotSender(
        bot_token=os.environ.get("ZALO_BOT_TOKEN", ""),
    )
```

**Key design decisions:**

1. **`_has_postback_buttons`** — nếu Markup chỉ có URL buttons, fallback to plain text (giống OA adapter cũ). Nếu có callback_data → dùng `sendTemplate` với real buttons.

2. **`_resolve_chat_id`** — vẫn dùng `channel_chat_id` / `channel_user_id` từ DB, giống OA adapter. Không cần thay đổi DB schema.

3. **Không cần OAuth refresh** — bot token embedded trực tiếp, không expire.

4. **Structured message limit** — Zalo Bot API giới hạn tối đa buttons per element (cần test thực tế, dự đoán 3-5 buttons). Nếu categories > limit, fallback to multiple elements hoặc pagination.

### 2. `core/handlers/zalo_webhook.py` — Rewrite

```python
"""Zalo Bot API webhook parsing and dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any

from core import db, messenger
from core.handlers.categorize import handle_numbered_category_reply
from core.handlers.start import handle_start
from core.logging import get_logger
from i18n import t

log = get_logger(__name__, component="zalo_bot_webhook")


@dataclass(frozen=True)
class ZaloBotUpdate:
    """Parsed Zalo Bot API update."""
    chat_id: str
    text: str
    callback_data: str | None = None  # from postback button


def is_zalo_enabled() -> bool:
    return _env_bool("ZALO_ENABLED")


def verify_signature(raw_body: bytes, headers: dict[str, str]) -> bool:
    """Verify X-Zalo-Signature HMAC-SHA256."""
    secret = os.environ.get("ZALO_WEBHOOK_SECRET", "")
    if not secret:
        # Dev mode: no secret = skip verification
        app_env = os.environ.get("APP_ENV", "dev").lower()
        if app_env in {"prod", "production", "staging"}:
            return False
        return True

    signature = headers.get("x-zalo-signature", "")
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def parse_update(body: dict[str, Any]) -> ZaloBotUpdate | None:
    """Parse a Zalo Bot API update (Telegram-like format).

    Two event types we handle:
    1. Text message: body.message.text + body.message.from.id
    2. Postback: body.callback_query.data + body.callback_query.from.id
    """
    # Postback (button click)
    callback = body.get("callback_query")
    if isinstance(callback, dict):
        from_user = callback.get("from") or {}
        chat_id = str(from_user.get("id") or "")
        data = str(callback.get("data") or "")
        if chat_id and data:
            return ZaloBotUpdate(chat_id=chat_id, text="", callback_data=data)

    # Text message
    message = body.get("message")
    if not isinstance(message, dict):
        return None
    from_user = message.get("from") or {}
    chat_id = str(from_user.get("id") or "")
    text = str(message.get("text") or "").strip()
    if not chat_id or not text:
        return None
    return ZaloBotUpdate(chat_id=chat_id, text=text)


async def handle_update(update: ZaloBotUpdate) -> None:
    """Route a parsed update to the appropriate handler."""

    # Postback button (e.g. "cat:123:5" from category picker)
    if update.callback_data:
        await _handle_callback(update)
        return

    # /start command
    if update.text.lower() == "/start":
        await handle_start(
            channel_type="zalo",
            channel_user_id=update.chat_id,
            channel_chat_id=update.chat_id,
        )
        return

    # Resolve existing user
    user_id = await _resolve_user_id(update.chat_id)
    if user_id is None:
        # Auto-onboard: user hasn't /start'd yet
        await handle_start(
            channel_type="zalo",
            channel_user_id=update.chat_id,
            channel_chat_id=update.chat_id,
        )
        return

    # Numbered category reply (backward compat with text-based flow)
    if await handle_numbered_category_reply(user_id, update.text):
        return

    # Fallback help
    locale = await _resolve_locale(user_id)
    await messenger.send(
        user_id,
        {
            "text": t(locale, "categorize.help_fallback"),
            "parse_mode": "plain",
        },
    )


async def _handle_callback(update: ZaloBotUpdate) -> None:
    """Handle postback button clicks.

    Category picker emits callback_data as "cat:{tx_id}:{category_id}".
    This bypasses the numbered-text flow entirely — direct category assignment.
    """
    data = update.callback_data or ""
    if not data.startswith("cat:"):
        log.warning("zalo_bot.unknown_callback", data=data)
        return

    parts = data.split(":")
    if len(parts) != 3:
        return

    _, tx_id_str, category_id_str = parts
    try:
        tx_id = int(tx_id_str)
        category_id = int(category_id_str)
    except ValueError:
        return

    user_id = await _resolve_user_id(update.chat_id)
    if user_id is None:
        return

    pool = db.get_pool()
    async with pool.acquire() as conn:
        # Verify tx belongs to user
        row = await conn.fetchrow(
            "SELECT id FROM transactions WHERE id = $1 AND user_id = $2;",
            tx_id, user_id,
        )
        if row is None:
            return

        # Verify category belongs to user
        cat_row = await conn.fetchrow(
            "SELECT name FROM categories WHERE id = $1 AND user_id = $2;",
            category_id, user_id,
        )
        if cat_row is None:
            return

        await conn.execute(
            "UPDATE transactions SET category_id = $1 WHERE id = $2 AND user_id = $3;",
            category_id, tx_id, user_id,
        )

    locale = await _resolve_locale(user_id)
    await messenger.send(
        user_id,
        {
            "text": t(locale, "categorize.confirmed", name=cat_row["name"]),
            "parse_mode": "plain",
        },
    )

    # Advance queue (shift to next pending tx if any)
    from core.services import bot_state
    step, payload = await bot_state.get_state(user_id)
    if step == "await_category":
        queue = list(payload.get("queue") or [])
        # Remove the tx we just categorized
        queue = [item for item in queue if int(item.get("tx_id", 0)) != tx_id]
        if queue:
            await bot_state.set_state(user_id, "await_category", {
                "queue": queue,
                "expires_at": payload.get("expires_at", ""),
            })
            # Send next picker
            from core.handlers.categorize import _send_active_picker
            await _send_active_picker(user_id, queue[0], locale)
        else:
            await bot_state.clear_state(user_id)


async def _resolve_user_id(chat_id: str) -> int | None:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM users
            WHERE channel_type = 'zalo'
              AND (channel_user_id = $1 OR channel_chat_id = $1)
            ORDER BY id LIMIT 1;
            """,
            chat_id,
        )
    return int(row["id"]) if row else None


async def _resolve_locale(user_id: int) -> str:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT locale FROM users WHERE id = $1;", user_id)
    return str(row["locale"]) if row else "vi"


def loads_body(raw_body: bytes) -> dict[str, Any] | None:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


__all__ = [
    "ZaloBotUpdate",
    "handle_update",
    "is_zalo_enabled",
    "loads_body",
    "parse_update",
    "verify_signature",
]
```

**Key upgrade: Callback queries (postback buttons)**

OA API chỉ có text → user gõ số "1", "2" → `handle_numbered_category_reply` parse.

Bot API có postback → user nhấn button → `callback_query.data = "cat:123:5"` → direct category assignment. **Không cần numbered text hack, không cần bot_state queue cho active picker matching.**

Tuy nhiên, `handle_numbered_category_reply` vẫn giữ làm fallback nếu user gõ số thay vì nhấn button.

### 3. FastAPI Route — `main.py` changes

Minimal change — replace import + adjust parsing:

```python
# Before (OA API):
from core.handlers.zalo_webhook import (
    is_zalo_enabled, verify_zalo_signature,
    parse_zalo_text_event, handle_zalo_text_event, loads_body,
)

# After (Bot API):
from core.handlers.zalo_webhook import (
    is_zalo_enabled, verify_signature,
    parse_update, handle_update, loads_body,
)

@app.post("/zalo/webhook")
async def zalo_webhook(request: Request):
    if not is_zalo_enabled():
        return {"status": "disabled"}

    raw_body = await request.body()
    headers = dict(request.headers)

    if not verify_signature(raw_body, headers):
        return JSONResponse(status_code=401, content={"error": "invalid signature"})

    body = loads_body(raw_body)
    if body is None:
        return {"status": "bad_request"}

    update = parse_update(body)
    if update is not None:
        await handle_update(update)

    return {"status": "ok"}
```

### 4. Env Vars

```bash
# .env.example — SIMPLIFIED
ZALO_ENABLED=true
ZALO_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ZALO_WEBHOOK_SECRET=optional-hmac-secret

# REMOVED (no longer needed):
# ZALO_INTERACTIVE=...     (merged into ZALO_ENABLED)
# ZALO_APP_ID=...          (not needed for Bot API)
# ZALO_OA_SECRET_KEY=...   (replaced by ZALO_WEBHOOK_SECRET)
# ZALO_OA_ACCESS_TOKEN=... (replaced by ZALO_BOT_TOKEN)
# ZALO_OA_REFRESH_TOKEN=.. (not needed — token doesn't expire)
# ZALO_AUTO_REFRESH=...    (not needed)
# ZALO_TEXT_LIMIT=...      (test and hardcode; default 2000 likely fine)
```

---

## Không cần thay đổi — xác nhận chi tiết

### `categorize.py` — tại sao không cần đổi

`_render_markup()` ở line 240-250 đã emit:
```python
Button(label=str(option["name"]), callback_data=f"cat:{entry['tx_id']}:{option['category_id']}")
```

Với OA adapter cũ: `ZaloSender._append_markup_text()` degrade thành `"1. Ăn uống\n2. Nhà ở"`.

Với Bot API adapter mới: `ZaloBotSender._send_structured()` render thành real postback buttons.

**Zero code change in categorize.py. Tự động upgrade UX.**

### `handle_start` — tại sao không cần đổi

```python
handle_start(channel_type="zalo", channel_user_id=chat_id, channel_chat_id=chat_id)
```

Vẫn đúng — Bot API `from.id` dùng cho cả `channel_user_id` và `channel_chat_id`.

### DB schema — tại sao không cần migration

- `channel_type = 'zalo'` — vẫn đúng (không phải `'zalo_bot'`)
- `channel_chat_id TEXT` — Bot API chat_id là string → compatible
- `channel_user_id TEXT` — tương tự
- `bot_state` table — vẫn đúng, key by `user_id`

---

## Test Plan

### Unit Tests

| Test | Mô tả |
|------|-------|
| `test_zalo_bot_sender_send_text` | sendMessage plain text |
| `test_zalo_bot_sender_send_structured` | sendTemplate with postback buttons |
| `test_zalo_bot_sender_url_fallback` | URL buttons → plain text append |
| `test_zalo_bot_sender_resolve_chat_id` | DB lookup channel_chat_id |
| `test_zalo_bot_sender_invalid_token` | Reject token without `:` |
| `test_parse_update_text` | Parse text message update |
| `test_parse_update_callback` | Parse postback callback_query |
| `test_parse_update_missing_fields` | Graceful None on bad input |
| `test_verify_signature_valid` | HMAC matches |
| `test_verify_signature_invalid` | HMAC mismatch → False |
| `test_verify_signature_no_secret_dev` | No secret in dev → True |
| `test_verify_signature_no_secret_prod` | No secret in prod → False |
| `test_handle_callback_category` | `cat:123:5` → UPDATE transactions |
| `test_handle_callback_invalid` | Unknown callback → log + ignore |
| `test_handle_callback_wrong_user` | tx belongs to other user → reject |

### Integration Tests

| Test | Mô tả |
|------|-------|
| `test_zalo_webhook_route_text` | POST /zalo/webhook with text message |
| `test_zalo_webhook_route_callback` | POST /zalo/webhook with postback |
| `test_zalo_webhook_route_disabled` | ZALO_ENABLED=false → 200 disabled |
| `test_zalo_webhook_route_bad_sig` | Invalid signature → 401 |
| `test_zalo_start_creates_user` | /start → user created with channel_type=zalo |
| `test_zalo_category_button_flow` | SePay → picker buttons → callback → categorized |
| `test_zalo_category_text_fallback` | SePay → picker → user types "1" → categorized |

### Manual Verification

1. Gửi `/start` từ Zalo → xác nhận user row created
2. Trigger SePay transaction → xác nhận nhận được button picker (không phải numbered text)
3. Nhấn button → xác nhận transaction categorized
4. Gõ số "1" thay vì nhấn button → xác nhận vẫn hoạt động
5. Gửi 2 SePay transactions liên tiếp → xác nhận queue + button flow
6. Kiểm tra `sendMessage` proactive (không cần user nhắn trước)

---

## Migration Steps (Ordered)

```
Step 1: Backup & Branch
  git checkout -b feat/MYM-XX-zalo-bot-api-migration

Step 2: Rewrite core/messenger/zalo.py
  - Replace ZaloSender with ZaloBotSender
  - Keep @register_sender("zalo") — same channel_type
  - Unit tests cho sender

Step 3: Rewrite core/handlers/zalo_webhook.py
  - New parse_update() for Bot API format
  - Add _handle_callback() for postback buttons
  - Keep handle_numbered_category_reply as fallback
  - Unit tests cho parser + callback handler

Step 4: Update main.py webhook route
  - New imports
  - Minimal handler changes

Step 5: Update .env.example + Railway secrets
  - ZALO_BOT_TOKEN (new)
  - ZALO_WEBHOOK_SECRET (new, optional)
  - Remove old OA vars

Step 6: Integration tests
  - Webhook route tests
  - Full flow: /start → SePay → button pick → confirm

Step 7: Set webhook URL in Zalo Bot settings
  POST bot-api.zapps.me/bot{TOKEN}/setWebhook
  body: {"url": "https://your-domain.railway.app/zalo/webhook"}

Step 8: Manual verification
  - Test all flows from step "Manual Verification" above
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bot API payload format differs from SDK assumptions | Webhook parsing fails | Capture first real webhook → add as fixture test |
| Button limit per structured message | Category picker truncated | Test with 10+ categories; implement pagination if needed |
| Bot API rate limits unknown | Message delivery delayed | Implement exponential backoff; test burst scenarios |
| Bot API downtime / breaking changes | Service outage | Keep OA adapter code in git history; can revert if needed |
| Existing Zalo users (OA) need re-onboard | User disruption | If any exist: migrate by updating DB; user sends /start to new bot |
| `_send_active_picker` import in webhook handler | Circular import risk | Already done in current code (categorize.py); same pattern |

---

## Removed Complexity (What we no longer need)

1. **OAuth token refresh flow** — entire `_refresh_access_token()` method + retry-on-401 logic
2. **Token persistence table** — `oauth_tokens` table (was planned for Tech Debt §2, now unnecessary)
3. **ZALO_AUTO_REFRESH flag** — entire conditional refresh behavior
4. **8 env vars → 3 env vars**
5. **Numbered text markup hack** — `_append_markup_text()` replaced by native buttons
6. **24h consultation window constraint** — can send anytime now
7. **ZNS template approval** — not needed for push notifications

---

## Mở rộng tương lai (Out of scope, ghi nhận)

1. **Quick replies** — category picker dùng quick replies thay vì persistent buttons (UX experiment)
2. **Image/file messages** — Bot API supports sendPhoto, sendFile
3. **Typing indicator** — `sendChatAction(chat_id, "typing")` trước khi xử lý
4. **User profile** — `getUserProfile(chat_id)` để lấy tên hiển thị khi onboard
5. **Long polling mode** — alternative to webhook cho dev/testing
