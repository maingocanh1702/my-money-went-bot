# Refactor Plan: Multi-Platform Bot

> Mục tiêu: tất cả platform dùng chung database (Google Sheets) và backend logic. Chỉ khác nhau ở adapter layer. Khi có feature mới, tất cả platform tự động nhận — không cần sửa handlers.

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Server                        │
│   /webhook/sepay   /webhook/{platform}   /trigger/*         │
└───────────────┬──────────────────┬──────────────────────────┘
                │                  │
     SePay event│         Platform │update (Telegram/Zalo/...)
                │                  │
         ┌──────▼──────┐    ┌──────▼──────┐
         │  fan_out()  │    │ Dispatcher  │
         │ → all plat. │    │ → 1 platform│
         └──────┬──────┘    └──────┬──────┘
                │                  │
         ┌──────▼──────────────────▼──────┐
         │         handlers/ (core logic)  │
         │  sepay · transaction · reports  │
         │  allocation  (platform-agnostic)│
         └──────┬──────────────────┬───────┘
                │                  │
    ┌───────────▼───┐      ┌───────▼──────────────────────┐
    │  sheets.py    │      │    MessengerAdapter layer     │
    │ (shared DB)   │      │  Telegram · Zalo · Viber ...  │
    └───────────────┘      └───────────────────────────────┘
```

---

## Cấu trúc thư mục mới

```
Bot Finance/
├── main.py                    # MOD — route /webhook/{platform} + /webhook/sepay
├── config.py                  # MOD — thêm token từng platform
├── sheets.py                  # MOD nhỏ — state key đổi sang user_id
├── telegram_api.py            # GIỮ NGUYÊN — TelegramAdapter dùng lại
│
├── models/
│   └── update.py              # NEW — IncomingUpdate, OutgoingMessage, Button
│
├── adapters/
│   ├── base.py                # NEW — MessengerAdapter ABC
│   ├── __init__.py            # NEW — ADAPTER_REGISTRY dict
│   ├── telegram.py            # NEW — wrap telegram_api.py
│   ├── zalo.py                # NEW — Zalo OA REST
│   ├── viber.py               # NEW — Viber REST
│   ├── whatsapp.py            # NEW — Meta Cloud API
│   ├── discord.py             # NEW — Discord REST
│   └── slack.py               # NEW — Slack Bolt
│
├── core/
│   ├── context.py             # NEW — BotContext (adapter + user_id + state)
│   ├── dispatcher.py          # NEW — parse update → gọi đúng handler
│   ├── fanout.py              # NEW — broadcast đến tất cả platform của user
│   └── registry.py            # NEW — map platform_user_id ↔ canonical user_id
│
└── handlers/                  # MOD — nhận ctx: BotContext thay vì hardcode tg.*
    ├── sepay.py
    ├── transaction.py
    ├── allocation.py
    └── reports.py
```

---

## Normalized Data Models — `models/update.py`

```python
from dataclasses import dataclass, field
from typing import Any, Literal

Platform = Literal["telegram", "zalo", "viber", "whatsapp", "discord", "slack"]

@dataclass
class Button:
    label: str
    callback_data: str          # platform-agnostic action string
    url: str | None = None      # for link-buttons where supported

@dataclass
class IncomingUpdate:
    platform:          Platform
    platform_user_id:  str      # raw ID từ platform (e.g. Telegram chat_id)
    user_id:           str      # canonical ID từ registry
    text:              str      # raw message text (empty string nếu là callback)
    command:           str | None  # "/status", "/allocate", etc.
    callback_data:     str | None  # decoded payload nếu button được bấm
    message_id:        str | None  # platform-specific message ID (để edit/delete)
    raw:               dict     # original platform payload

@dataclass
class OutgoingMessage:
    text:              str
    buttons:           list[list[Button]] = field(default_factory=list)
    edit_message_id:   str | None = None   # nếu set → adapter EDIT thay vì gửi mới
    delete_message_id: str | None = None   # nếu set → adapter xóa message này trước
    parse_mode:        str = "markdown"
    metadata:          dict = field(default_factory=dict)
```

---

## Abstract Adapter Interface — `adapters/base.py`

```python
from abc import ABC, abstractmethod
from models.update import IncomingUpdate, OutgoingMessage

class MessengerAdapter(ABC):

    platform: str  # class-level constant, e.g. "telegram"

    @abstractmethod
    async def parse_incoming(self, raw_body: dict) -> IncomingUpdate | None:
        """
        Parse raw platform webhook payload → IncomingUpdate.
        Return None nếu payload nên được bỏ qua
        (e.g. bot echo, unsupported event, incoming bank transfer).
        """

    @abstractmethod
    async def send(self, user_id: str, message: OutgoingMessage) -> dict:
        """
        Deliver OutgoingMessage đến platform user.
        Nếu message.edit_message_id được set → EDIT nếu platform hỗ trợ,
        không thì fallback send + delete message cũ.
        """

    @abstractmethod
    async def answer_callback(self, callback_id: str) -> None:
        """
        Acknowledge button press (e.g. Telegram answerCallbackQuery).
        Platform không cần explicit ACK thì no-op.
        """

    @abstractmethod
    async def setup(self) -> None:
        """
        Gọi 1 lần lúc startup. Register commands, set webhook URL, v.v.
        """

    # Capability flags — override trong subclass nếu khác
    supports_edit:    bool = False   # Telegram: True; Zalo/Viber/WhatsApp: False
    supports_buttons: bool = True
    max_message_len:  int  = 4096
```

---

## BotContext — `core/context.py`

```python
from dataclasses import dataclass
from adapters.base import MessengerAdapter
from models.update import IncomingUpdate
import sheets as sh

@dataclass
class BotContext:
    update:  IncomingUpdate
    adapter: MessengerAdapter
    user_id: str

    async def send(self, msg) -> dict:
        return await self.adapter.send(self.update.platform_user_id, msg)

    def get_state(self) -> dict:
        return sh.get_state(self.user_id) or {}

    def set_state(self, data: dict):
        sh.set_state(self.user_id, data)

    def clear_state(self):
        sh.clear_state(self.user_id)
```

Handlers chỉ cần biết `ctx` — không cần import `tg` hay biết đang chạy platform nào.

---

## Fan-Out Engine — `core/fanout.py`

```python
import asyncio
from core.registry import UserRegistry
from adapters import get_adapter
from models.update import OutgoingMessage

registry = UserRegistry()

async def fan_out(user_id: str, message: OutgoingMessage) -> None:
    """
    Gửi OutgoingMessage đến TẤT CẢ platform đã kết nối của user_id, song song.
    Lỗi ở 1 platform không block các platform còn lại.
    """
    connections = registry.get_all_platform_connections(user_id)
    tasks = []
    for conn in connections:
        adapter = get_adapter(conn["platform"])
        if adapter is None:
            continue
        tasks.append(_safe_send(adapter, conn["platform_user_id"], message))
    await asyncio.gather(*tasks)

async def _safe_send(adapter, platform_user_id: str, message: OutgoingMessage):
    try:
        await adapter.send(platform_user_id, message)
    except Exception as e:
        print(f"[fanout] failed on {adapter.platform}/{platform_user_id}: {e}")
```

**Quy tắc:**
- **SePay webhook + cron reports** → dùng `fan_out()` → tất cả platform nhận đồng thời
- **User reply / button callback** → dùng `ctx.send()` → chỉ platform đang dùng nhận

---

## User Registry — `core/registry.py`

### Google Sheets tab "Users" (tab mới cần tạo)

| user_id | platform | platform_user_id | display_name | created_at | active |
|---|---|---|---|---|---|
| `u_main` | telegram | `12345678` | Maddy | 2024-01-01 | TRUE |
| `u_main` | zalo | `zalo_uid_xyz` | Maddy | 2024-02-01 | TRUE |
| `u_main` | viber | `viber_uid_abc` | Maddy | 2024-03-01 | TRUE |

Một user → nhiều dòng (một dòng per platform). `fan_out` đọc tất cả dòng rồi gửi song song.

```python
class UserRegistry:
    def get_or_create_user(self, platform: str, platform_user_id: str) -> str:
        """Lookup user_id. Nếu chưa có → tạo mới (uuid4)."""

    def get_all_platform_connections(self, user_id: str) -> list[dict]:
        """Trả về tất cả platform đã kết nối của user_id."""
        # [{"platform": "telegram", "platform_user_id": "12345678"}, ...]

    def link_platform(self, user_id: str, platform: str, platform_user_id: str):
        """Kết nối thêm 1 platform cho user (e.g. user gửi /connect từ Zalo)."""
```

---

## Platform Routing — `main.py` (target)

```python
@app.post("/webhook/sepay")
async def webhook_sepay(request: Request, bg: BackgroundTasks):
    body = await request.json()
    bg.add_task(handle_sepay_webhook, body)   # fan-out bên trong handler
    return JSONResponse({"ok": True})

@app.post("/webhook/{platform}")
async def webhook_platform(platform: str, request: Request, bg: BackgroundTasks):
    adapter = ADAPTER_REGISTRY.get(platform)
    if not adapter:
        return JSONResponse({"ok": True})
    body = await request.json()
    bg.add_task(Dispatcher.dispatch, adapter, body)
    return JSONResponse({"ok": True})

@app.on_event("startup")
async def on_startup():
    for adapter in ADAPTER_REGISTRY.values():
        await adapter.setup()
```

---

## Dispatcher — `core/dispatcher.py`

```python
class Dispatcher:

    @staticmethod
    async def dispatch(adapter: MessengerAdapter, raw_body: dict):
        update = await adapter.parse_incoming(raw_body)
        if update is None:
            return

        user_id = registry.get_or_create_user(update.platform, update.platform_user_id)
        state   = sh.get_state(user_id) or {}
        ctx     = BotContext(update=update, adapter=adapter, user_id=user_id, state=state)

        if update.callback_data:
            await adapter.answer_callback(update.raw.get("callback_id", ""))
            await Dispatcher._handle_callback(ctx)
        elif update.command:
            await Dispatcher._handle_command(ctx)
        else:
            await Dispatcher._handle_text(ctx)

    @staticmethod
    async def _handle_callback(ctx):
        parts  = (ctx.update.callback_data or "").split("_")
        prefix = parts[0]
        msg_id = ctx.update.message_id
        if   prefix == "p":     await handle_parent_selected(ctx, parts, msg_id)
        elif prefix == "s":     await handle_sub_selected(ctx, parts, msg_id)
        elif prefix == "al":    await handle_alloc_callback(ctx, parts, msg_id)
        elif prefix == "recat": await handle_recategorize(ctx, parts, msg_id)

    @staticmethod
    async def _handle_command(ctx):
        cmd = ctx.update.command
        if   cmd == "/status":   await send_monthly_status(ctx)
        elif cmd == "/today":    await send_today_status(ctx)
        elif cmd == "/allocate": await start_monthly_allocation(ctx)
        elif cmd == "/weekly":   await run_weekly_summary(ctx)
        elif cmd == "/report":   await run_monthly_report(ctx)

    @staticmethod
    async def _handle_text(ctx):
        step = ctx.get_state().get("step")
        if   step == "await_freetext":         await handle_freetext_sub(ctx)
        elif step == "await_alloc_amount":     await handle_alloc_amount_input(ctx)
        elif step == "await_new_bucket_name":  await handle_new_bucket_name(ctx)
        elif step == "await_new_bucket_amount":await handle_new_bucket_amount(ctx)
        elif step == "await_daily_excuse":     await handle_daily_excuse(ctx)
        else:
            await ctx.send(OutgoingMessage(
                text="🤖 Try /status, /today, /allocate, /weekly, or /report"
            ))
```

---

## Thay đổi trong từng Handler

### `handlers/sepay.py`
- Bỏ import `tg`, bỏ hardcode `CHAT_ID`
- `sh.set_state(CHAT_ID, ...)` → `sh.set_state(user_id, ...)`
- `tg.build_bucket_buttons(...)` → build `list[list[Button]]` inline
- `await tg.send_text(...)` / `await tg.send_with_buttons(...)` → `await fan_out(user_id, OutgoingMessage(...))`

### `handlers/transaction.py`
- Mỗi function thêm `ctx: BotContext` làm tham số đầu
- `sh.get_state(CHAT_ID)` → `ctx.get_state()`
- `tg.edit_message(id, text)` → `await ctx.send(OutgoingMessage(text=text, edit_message_id=id))`
- `tg.send_with_buttons(msg, btns)` → `await ctx.send(OutgoingMessage(text=msg, buttons=btns))`
- `tg.delete_message(id)` → `await ctx.send(OutgoingMessage(text="", delete_message_id=id))`

### `handlers/allocation.py`
- Mỗi function thêm `ctx: BotContext`
- Thay `CHAT_ID` → `ctx.user_id`
- Thay tất cả `tg.*` → `await ctx.send(OutgoingMessage(...))`
- Buttons build thành `list[list[Button]]`

### `handlers/reports.py`
- Commands (`/status`, `/today`, v.v.) nhận `ctx: BotContext` → dùng `ctx.send()`
- Cron functions (`send_daily_recap`, `run_weekly_summary`, v.v.) nhận `user_id: str` → dùng `fan_out()`

### `sheets.py`
- State key đổi từ Telegram `chat_id` → canonical `user_id`
- Signatures `get_state(key)`, `set_state(key, data)` giữ nguyên — chỉ callers thay giá trị truyền vào
- Thêm logic đọc/ghi tab "Users" vào `UserRegistry`

---

## TelegramAdapter — `adapters/telegram.py`

```python
class TelegramAdapter(MessengerAdapter):
    platform      = "telegram"
    supports_edit = True

    async def parse_incoming(self, raw_body: dict) -> IncomingUpdate | None:
        if "update_id" not in raw_body:
            return None
        if raw_body.get("message", {}).get("from", {}).get("is_bot"):
            return None
        if "callback_query" in raw_body:
            cb = raw_body["callback_query"]
            return IncomingUpdate(
                platform="telegram",
                platform_user_id=str(cb["from"]["id"]),
                user_id="",
                text="",
                command=None,
                callback_data=cb.get("data"),
                message_id=str(cb["message"]["message_id"]),
                raw={"callback_id": cb["id"], **raw_body},
            )
        elif "message" in raw_body:
            msg  = raw_body["message"]
            text = (msg.get("text") or "").strip()
            return IncomingUpdate(
                platform="telegram",
                platform_user_id=str(msg["from"]["id"]),
                user_id="",
                text=text,
                command=text.split()[0].lower() if text.startswith("/") else None,
                callback_data=None,
                message_id=str(msg["message_id"]),
                raw=raw_body,
            )
        return None

    async def send(self, platform_user_id: str, message: OutgoingMessage) -> dict:
        if message.delete_message_id:
            await tg.delete_message(int(message.delete_message_id))
        if message.edit_message_id and self.supports_edit:
            await tg.edit_message(int(message.edit_message_id), message.text)
            return {}
        if message.buttons:
            inline_kb = self._render_buttons(message.buttons)
            return await tg.send_with_buttons(message.text, inline_kb)
        return await tg.send_text(message.text)

    def _render_buttons(self, buttons: list[list[Button]]) -> list[list[dict]]:
        return [
            [{"text": b.label, "callback_data": b.callback_data} for b in row]
            for row in buttons
        ]

    async def answer_callback(self, callback_id: str) -> None:
        if callback_id:
            await tg.answer_callback(callback_id)

    async def setup(self) -> None:
        await tg.set_my_commands()
```

`telegram_api.py` giữ nguyên 100% — adapter chỉ wrap lại.

---

## `adapters/__init__.py`

```python
from adapters.telegram import TelegramAdapter
# from adapters.zalo import ZaloAdapter      # uncomment khi ready
# from adapters.viber import ViberAdapter
# from adapters.whatsapp import WhatsAppAdapter

ADAPTER_REGISTRY: dict[str, MessengerAdapter] = {
    "telegram": TelegramAdapter(),
    # "zalo": ZaloAdapter(),
}

def get_adapter(platform: str) -> MessengerAdapter | None:
    return ADAPTER_REGISTRY.get(platform)
```

Thêm platform mới = uncomment 2 dòng. Không cần sửa gì khác.

---

## `config.py` bổ sung

```python
# Existing
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]

# New — thêm từng cái khi enable platform tương ứng
ZALO_ACCESS_TOKEN  = os.environ.get("ZALO_ACCESS_TOKEN", "")
ZALO_OA_ID         = os.environ.get("ZALO_OA_ID", "")
VIBER_TOKEN        = os.environ.get("VIBER_TOKEN", "")
WHATSAPP_TOKEN     = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID  = os.environ.get("WHATSAPP_PHONE_ID", "")
DISCORD_BOT_TOKEN  = os.environ.get("DISCORD_BOT_TOKEN", "")
SLACK_BOT_TOKEN    = os.environ.get("SLACK_BOT_TOKEN", "")

class SHEETS:
    TRANSACTIONS    = "Đầu ra"
    BUDGET_CONFIG   = "Budget Config"
    SUBCATEGORY     = "Sub-category Config"
    MONTHLY_REPORTS = "Monthly Reports"
    BOT_STATE       = "Bot State"
    USERS           = "Users"           # NEW
```

---

## Migration Plan (Zero-Downtime)

### Phase 0 — Chuẩn bị (không đụng code)
- [ ] Tạo tab "Users" trong Google Sheet (các cột: `user_id | platform | platform_user_id | display_name | created_at | active`)
- [ ] Thêm 1 dòng: `u_main | telegram | {CHAT_ID} | Maddy | today | TRUE`
- [ ] Thêm `USER_ID_DEFAULT = "u_main"` vào `config.py`
- [ ] Telegram vẫn chạy bình thường

### Phase 1 — Tạo infrastructure (không break gì)
- [ ] Tạo `models/update.py`
- [ ] Tạo `adapters/base.py`
- [ ] Tạo `adapters/telegram.py` (wrap `telegram_api.py`)
- [ ] Tạo `adapters/__init__.py`
- [ ] Tạo `core/registry.py`
- [ ] Tạo `core/context.py`
- [ ] Tạo `core/fanout.py`

### Phase 2 — Wire dispatcher song song
- [ ] Tạo `core/dispatcher.py`
- [ ] Thêm route `/webhook/telegram` vào `main.py` — **giữ nguyên `/webhook` cũ**
- [ ] Test đầy đủ: tất cả commands + button flows
- [ ] Khi OK → xóa route `/webhook` cũ và các hàm `_process`, `_handle_*` trong `main.py`

### Phase 3 — Refactor handlers (từng file, ít rủi ro nhất trước)
- [ ] `handlers/reports.py` — chỉ send, không state machine → smoke test `/status`, `/today`, `/weekly`, `/report`
- [ ] `handlers/allocation.py` → smoke test `/allocate` full flow
- [ ] `handlers/transaction.py` → smoke test category selection flow
- [ ] `handlers/sepay.py` → smoke test mock SePay webhook end-to-end

### Phase 4 — Thêm platform đầu tiên (Zalo OA)
- [ ] Implement `adapters/zalo.py`
- [ ] Uncomment trong `ADAPTER_REGISTRY`
- [ ] Thêm Zalo token vào `.env`
- [ ] Đăng ký Zalo OA webhook tại `/webhook/zalo`
- [ ] Thêm dòng vào Users sheet: `u_main | zalo | {ZALO_UID} | Maddy | today | TRUE`
- [ ] Test: mock SePay webhook → cả Telegram lẫn Zalo đều nhận đồng thời
- [ ] Lặp lại cho Viber, WhatsApp, Discord, Slack

### Phase 5 — Multi-user (nếu cần mở rộng)
- [ ] Bỏ `USER_ID_DEFAULT` khỏi config
- [ ] Registry tự tạo user mới cho bất kỳ `platform_user_id` chưa biết
- [ ] Cron endpoints iterate qua tất cả `user_id` active trong Users sheet

---

## Platform Support Matrix

| Platform | Webhook | Buttons | Edit Message | Đăng ký | Ghi chú |
|---|---|---|---|---|---|
| **Telegram** | ✅ | ✅ Inline keyboard | ✅ | BotFather (tức thì) | Đang dùng |
| **Zalo OA** | ✅ | ✅ | ❌ | Zalo OA + duyệt | Tốt nhất cho VN |
| **Viber** | ✅ | ✅ Keyboard | ❌ | Viber Bot (tức thì) | API giống Telegram nhất |
| **WhatsApp** | ✅ | ⚠️ Tối đa 3 nút | ❌ | Meta Business verify | 1000 conv/tháng free |
| **Facebook Messenger** | ✅ | ✅ | ❌ | Facebook Page | Meta đang giảm priority |
| **Discord** | ✅ | ✅ Components | ✅ | Discord Dev Portal | Tốt cho tech/team |
| **Slack** | ✅ | ✅ Block Kit | ✅ | Slack App | Tốt cho B2B/công sở |

---

## Key Design Decisions

**Tại sao `OutgoingMessage.edit_message_id` thay vì method `edit()` riêng?**
Handlers khai báo intent (gửi text này, optionally thay message X), không chọn code path. Adapter quyết định edit có khả thi không. Zalo adapter: nếu `edit_message_id` được set nhưng `supports_edit=False` → gửi message mới + xóa message cũ.

**Tại sao `fan_out` tách biệt với `ctx.send()`?**
Commands và interactive flows là single-platform (user đang dùng 1 platform cụ thể). SePay events và cron reports là broadcast events — phải đến tất cả platform. Tách biệt là explicit, tránh coupling.

**Tại sao `telegram_api.py` giữ nguyên?**
TelegramAdapter delegate trực tiếp vào nó. Module đã test 100% giữ nguyên, rủi ro migration về zero. Nếu có bug, chỉ isolated trong Telegram adapter.

**Tại sao dùng Google Sheets cho User Registry thay vì database?**
Nhất quán với design principle của project (Sheets là single source of truth). Ổn với single-digit users. `UserRegistry` class abstract storage → có thể swap sang SQLite/Postgres sau mà không cần sửa file nào khác.
