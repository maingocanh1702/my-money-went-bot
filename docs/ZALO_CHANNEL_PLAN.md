# Zalo Channel Implementation Plan

> Mục tiêu: Zalo Bot hoạt động song song với Telegram — cùng codebase, cùng Google Sheet, mỗi channel có UX phù hợp.

This plan uses only the official **Zalo Bot Platform API**. No `zalo-personal` / personal-account automation.

## Target Outcome

Users can run My Money Went Bot with:

- **Telegram only**: current behavior (default).
- **Telegram + Zalo notifications**: Zalo receives transaction/report notifications.
- **Zalo interactive mode**: Zalo handles simple commands (`/today`, `/report`) and category selection with numbered text replies.

## Non-goals

- Do not replace Telegram inline buttons — Zalo uses numbered text replies instead.
- Do not support Zalo group chats.
- Do not support unofficial Zalo personal account login.
- Do not make Zalo the only supported channel until channel state is fully isolated.
- Do not send sensitive financial data to Zalo unless `ZALO_ENABLED=true`.

## Architecture

```
Current coupling:
  handlers/* → import telegram_api as tg → Telegram Bot API

Target (Phase 3+):
  handlers/* → BotChannel facade → Telegram or Zalo implementation
```

Full architecture diagram:

```
                    ┌─────────────────────────────────────────┐
                    │              FastAPI App                 │
                    │                                         │
  SePay webhook ──► │  /webhook (Telegram)                    │
                    │  /zalo/webhook (Zalo)                   │
                    │         │                               │
                    │    ┌────▼────┐                          │
                    │    │ _process│ ← dispatcher             │
                    │    └────┬────┘                          │
                    │         │                               │
                    │  ┌──────▼──────┐    ┌───────────────┐   │
                    │  │ _handle_msg │    │ _handle_zalo  │   │
                    │  │ (Telegram)  │    │  (Zalo)       │   │
                    │  └──────┬──────┘    └───────┬───────┘   │
                    │         │                   │           │
                    │    ┌────▼───────────────────▼────┐      │
                    │    │     handlers/*              │      │
                    │    │  (channel-aware dispatch)   │      │
                    │    └────────────┬────────────────┘      │
                    │                │                        │
                    │    ┌───────────▼───────────┐            │
                    │    │   BotChannel facade    │            │
                    │    │  ┌─────┐  ┌──────┐    │            │
                    │    │  │ TG  │  │ Zalo │    │            │
                    │    │  └─────┘  └──────┘    │            │
                    │    └───────────────────────┘            │
                    └─────────────────────────────────────────┘
```

---

## Phase 1: Notification Fan-out ✅ DONE

Zalo receives transaction notifications alongside Telegram.

### Files implemented

| File | Purpose |
|------|---------|
| `config.py` | `ZALO_ENABLED`, `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID` |
| `zalo_api.py` | `send_text`, `chunk_text` (2000 chars), `strip_markdown` |
| `notifier.py` | Dual fan-out (Telegram always + Zalo if enabled) |
| `handlers/sepay.py` | income/welcome/auto-cat notifications → cả 2 channels |
| `scripts/zalo_get_updates.py` | Discovery script for `ZALO_CHAT_ID` |
| `docs/ZALO_BOT_SETUP.md` | User-facing setup guide |

### Env vars

```env
ZALO_ENABLED=false
ZALO_BOT_TOKEN=
ZALO_CHAT_ID=
```

### Behavior

- If `ZALO_ENABLED=false`, all Zalo calls are no-op.
- `strip_markdown()` converts Telegram Markdown to readable plain text.
- Messages > 2000 chars are auto-chunked at paragraph/line boundaries.
- Zalo API failures are logged but never raise — SePay ingestion is never blocked.

---

## Phase 2: Zalo Webhook + Read-only Commands ✅ DONE

User can send `/today`, `/report`, `/accounts` from Zalo and receive plain text responses.

### Additional env vars

```env
ZALO_WEBHOOK_SECRET=       # validates incoming webhook header
ZALO_USER_ID=              # authorized sender (reject all others)
ZALO_INTERACTIVE=false     # must be true before /zalo/webhook processes commands
```

### Endpoint: `/zalo/webhook`

Added to `main.py`:

```python
@app.post("/zalo/webhook")
async def zalo_webhook(request: Request, bg: BackgroundTasks):
    # 1. Require ZALO_ENABLED=true and ZALO_INTERACTIVE=true
    # 2. Require configured ZALO_WEBHOOK_SECRET and ZALO_USER_ID
    # 3. Validate header X-Bot-Api-Secret-Token == ZALO_WEBHOOK_SECRET
    # 4. Parse body: { ok, result: { event_name, message } }
    # 5. Reject if not "message.text.received"
    # 6. Reject if message.from.is_bot == true
    # 7. Reject if message.from.id != ZALO_USER_ID
    # 8. Reject if chat.chat_type != "PRIVATE"
    # 9. bg.add_task(_process_zalo, event)
    # 10. Return 200
```

### Supported commands (read-only)

| Command | Behavior |
|---------|----------|
| `/today` | Daily spending snapshot (plain text, stripped Markdown) |
| `/report` | Monthly category report (default) |
| `/report tuần` | Weekly report |
| `/report quý` / `/report năm` | Quarterly / yearly report |
| `/accounts` | List configured accounts |
| anything else | Help message with available commands |

### Key refactorings

- `handlers/reports.py`: extracted `_build_today_text()` — returns text without sending.
- `handlers/report.py`: added `build_report_text(period, lens)` — returns text without sending.
- Both Telegram and Zalo callers reuse these builders. Telegram adds buttons; Zalo sends plain text.

### Files changed

| File | Change |
|------|--------|
| `config.py` | Added `ZALO_INTERACTIVE`, `ZALO_WEBHOOK_SECRET`, `ZALO_USER_ID` |
| `zalo_api.py` | Added `set_webhook`, `delete_webhook`, `get_webhook_info`, `send_text_raw` |
| `main.py` | Added `/zalo/webhook` endpoint + `_process_zalo` + `_handle_zalo_command` |
| `handlers/reports.py` | Extracted `_build_today_text()` |
| `handlers/report.py` | Added `build_report_text(period, lens)` |
| `.env.example` | Added webhook vars |

> **Phase 2 KHÔNG hỗ trợ**: `/manage`, `/keywords`, `/allocate`, category picker, hoặc bất kỳ flow nào cần inline buttons hay multi-step state. Những flows này vẫn chỉ dùng Telegram.

---

## Phase 3: Channel Abstraction + Numbered Replies

**Mục tiêu**: Zalo user có thể phân loại giao dịch (chọn category) bằng text-based numbered replies.

### Channel-aware State Keys

**Vấn đề hiện tại**: State keyed by `CHAT_ID` (Telegram chat ID). Nếu Zalo + Telegram cùng chạy, state sẽ đè nhau.

**Refactor `sheets.py`**:

```python
# TRƯỚC: get_state(CHAT_ID), set_state(CHAT_ID, {...})
# SAU:   get_state("telegram:123456"), set_state("zalo:6ede9afa66b88fe6d6a9", {...})

def state_key(channel: str, user_id: str) -> str:
    return f"{channel}:{user_id}"
```

**Migration strategy** (backward-compatible):
- Telegram: đọc key `telegram:{CHAT_ID}`, fallback sang legacy key `{CHAT_ID}`
- Zalo: luôn dùng key `zalo:{ZALO_CHAT_ID}`
- Migrate on first write: nếu legacy key exists, copy sang prefixed key

### BotChannel Protocol

New file `bot_channel.py`:

```python
from typing import Protocol

class Option:
    text: str       # Display label
    key: str        # Callback identifier (VD: bucket_id)

class BotChannel(Protocol):
    channel_name: str   # "telegram" | "zalo"
    chat_id: str

    async def send_text(self, text: str) -> dict | None: ...
    async def send_options(self, text: str, options: list[Option]) -> dict | None: ...
    async def edit_or_send(self, message_id: str | int | None, text: str) -> dict | None: ...
    async def delete_message(self, message_id: str | int) -> None: ...
```

**TelegramChannel**: wraps `tg.send_with_buttons()`, `tg.edit_message()`.

**ZaloChannel**: builds numbered text list, stores option map in state for reply resolution. No edit — always sends new message.

### Numbered Reply Resolver

New file `handlers/zalo_adapter.py`:

```python
def resolve_numbered_reply(text: str, state: dict) -> str | None:
    """Convert "1" → option key from pending_options in state."""
    pending = state.get("pending_options", [])
    try:
        idx = int(text.strip()) - 1
        if 0 <= idx < len(pending):
            return pending[idx]["key"]
    except ValueError:
        pass
    return None
```

### Handler Refactoring Priority

| Priority | Flow | Telegram | Zalo |
|----------|------|----------|------|
| 🔴 P0 | Category picker (expense) | Inline buttons | Numbered list → reply số |
| 🔴 P0 | Sub-category picker | Inline buttons | Numbered list → reply số |
| 🟡 P1 | Income notification | `tg.send_text` | ✅ Done (Phase 1) |
| 🟡 P1 | Auto-categorize confirm | `tg.send_text` | ✅ Done (Phase 1) |
| 🟢 P2 | Recategorize ("Sai mục?") | Inline button | Text command "sai" hoặc skip |
| ⚪ P3 | `/manage`, `/keywords`, `/allocate` | Heavy callback | Telegram only |

### Files to change

| Action | File | Change |
|--------|------|--------|
| NEW | `bot_channel.py` | `BotChannel` protocol + `TelegramChannel` + `ZaloChannel` |
| NEW | `handlers/zalo_adapter.py` | Numbered reply resolver + option state management |
| MODIFY | `sheets.py` | `state_key()` helper, channel-prefixed state keys |
| MODIFY | `main.py` | Zalo dispatcher handles numbered replies |
| MODIFY | `handlers/sepay.py` | Category picker → use `BotChannel.send_options()` |
| MODIFY | `handlers/transaction.py` | `handle_parent_selected` + `_finalize` channel-aware |
| MODIFY | Multiple handlers | `sh.set_state(CHAT_ID, ...)` → `sh.set_state(state_key, ...)` |

### Acceptance criteria

- [ ] SePay expense → Zalo nhận numbered category list
- [ ] User reply "1" → transaction phân loại đúng category
- [ ] Sub-category picker hoạt động (nếu category có subs)
- [ ] Telegram inline buttons vẫn hoạt động bình thường
- [ ] State Telegram và Zalo KHÔNG đè nhau (channel-prefixed keys)
- [ ] 120+ tests pass + new tests cho numbered-reply

---

## Phase 4: Full Multi-channel Mode (Later)

- [ ] Per-channel owner IDs (multi-user support)
- [ ] `/manage`, `/keywords`, `/allocate` hoạt động trên Zalo
- [ ] Daily recap gửi đến Zalo
- [ ] Configurable primary channel
- [ ] Migration docs cho switch Telegram → Zalo
- [ ] Update `README.md`, `README.vi.md`, `docs/AI_SETUP.md`, `docs/QUICK_INTRO.md`

Setup modes to document:

| Mode | Best for |
|------|----------|
| Telegram only | Easiest and most complete |
| Telegram + Zalo notifications | Receive alerts in both places |
| Zalo interactive | Use Zalo for basic commands + category replies |

---

## Risks

- **Message length**: Zalo limit is 2000 chars; reports may need chunking or simplification. → Mitigated by `chunk_text()`.
- **Formatting**: Zalo is plain text; Telegram Markdown looks noisy without `strip_markdown()`. → Mitigated in Phase 1.
- **Inline callback refactor**: The main cost of Phases 3+. Heavy callback flows (`/manage`, `/keywords`, `/allocate`) are deferred.
- **State collision**: If both channels are interactive before state isolation, user state can corrupt. → Phase 3 must ship state key refactor BEFORE enabling interactive Zalo.
- **SePay sensitivity**: Finance notifications are sensitive; fan-out must be explicit (`ZALO_ENABLED=true`).

## Suggested PR Breakdown

1. ✅ Docs-only research and plan.
2. ✅ Add `zalo_api.py`, env vars, tests.
3. ✅ Add notification fan-out for SePay notifications.
4. ✅ Add `scripts/zalo_get_updates.py` and setup docs.
5. ✅ Add `/zalo/webhook` + `/today`, `/report`, `/accounts`.
6. Add channel-aware state keys (`state_key()` refactor).
7. Add numbered option flow for Zalo category picker.

## Test Plan

### Unit tests

- ✅ Zalo API chunking (under/over 2000 chars)
- ✅ Zalo disabled → no-op
- ✅ Payload uses `chat_id` and `text`
- ✅ Zalo webhook auth rejects invalid secret
- ✅ Zalo webhook auth rejects invalid user
- ✅ Zalo event parser handles webhook `result` wrapper
- ✅ Zalo event parser ignores stickers/unsupported
- Numbered reply maps `"1"` → expected bucket callback

### Integration

- ✅ SePay outgoing tx writes exactly one row
- ✅ Telegram notification still sends when Zalo fails
- ✅ With Zalo enabled, Zalo notification attempted once
- Zalo numbered reply maps to correct category

### Manual verification

1. Create Zalo Bot + get `ZALO_CHAT_ID`
2. Enable Zalo notification mode on Railway
3. Trigger one small bank transaction → confirm both channels receive notification
4. Set webhook → send `/today` from Zalo → verify response
5. (Phase 3) SePay expense → Zalo numbered picker → reply "1" → verify Sheet
