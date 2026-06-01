# Zalo Phase 3: Numbered Category Picker — Implementation Plan

| Field | Value |
|-------|-------|
| Version | v1.0.0 |
| Tạo ngày | 2026-05-28 |
| Tác giả | Review & rewrite based on actual codebase |
| Trạng thái | 📝 Draft — chờ approve trước khi implement |
| Liên quan | [docs/ZALO_CHANNEL_PLAN.md](../docs/ZALO_CHANNEL_PLAN.md) (Phase 1 ✅, Phase 2 ✅) |

---

## Current State (đã có trong codebase)

### Phase 1 ✅ Notification Fan-out
- `zalo_api.py` — Zalo Bot Platform client (`bot-api.zaloplatforms.com`), `send_text`, `chunk_text`, `strip_markdown`
- `notifier.py` — dual fan-out (Telegram always + Zalo if enabled)
- `config.py` — `ZALO_ENABLED`, `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID`

### Phase 2 ✅ Read-only Commands
- `/zalo/webhook` endpoint in `main.py` — validates `X-Bot-Api-Secret-Token`
- `_process_zalo()` + `_handle_zalo_command()` — handles `/today`, `/report`, `/accounts`
- `config.py` — `ZALO_INTERACTIVE`, `ZALO_WEBHOOK_SECRET`, `ZALO_USER_ID`
- Report text builders extracted: `_build_today_text()`, `build_report_text()`

### Architecture (actual, verified)

```
my-money-went-bot/
├── main.py              # FastAPI: /webhook (Telegram), /zalo/webhook (Zalo)
├── telegram_api.py      # httpx → api.telegram.org
├── zalo_api.py          # httpx → bot-api.zaloplatforms.com (notification-only)
├── notifier.py          # Dual fan-out: tg.send_text + zalo.send_text
├── sheets.py            # gspread — Google Sheets as database + state
├── config.py            # All env vars
├── handlers/
│   ├── sepay.py         # SePay webhook → append Google Sheets → category picker
│   ├── transaction.py   # handle_parent_selected, handle_sub_selected, _finalize
│   ├── allocation.py    # Budget allocation wizard
│   ├── reports.py       # /today, daily recap
│   ├── report.py        # /report with period buttons
│   ├── manage.py        # Category CRUD
│   ├── keywords.py      # Auto-categorization rules
│   ├── accounts.py      # Bank account management
│   └── account_resolver.py
└── requirements.txt     # fastapi, gspread, httpx, google-auth (NO PostgreSQL/SQLAlchemy)
```

**Data layer**: Google Sheets (`gspread`). Tất cả state lưu trong tab "Bot State" qua `sh.get_state(CHAT_ID)` / `sh.set_state(CHAT_ID, {...})`.

**Telegram coupling**: Handlers gọi trực tiếp `tg.send_with_buttons()`, `tg.edit_message()`, `tg.build_bucket_buttons()`. State keyed by `CHAT_ID` (Telegram chat ID, single value).

---

## Phase 3 Goal

Zalo user có thể **phân loại giao dịch** khi SePay expense webhook arrives — chọn category bằng numbered text reply thay vì Telegram inline buttons.

### In scope
- SePay expense → Zalo nhận numbered category list
- User reply "1", "2"... → transaction phân loại đúng
- Sub-category flow (numbered list nếu category có subs)
- Queue khi nhiều giao dịch đến liên tiếp
- Telegram vẫn hoạt động bình thường (không break)

### Out of scope (Phase 4+)
- `/manage`, `/keywords`, `/allocate` trên Zalo (heavy multi-step wizards)
- Recategorize ("Sai mục?") trên Zalo
- Multi-user support
- Migration off Google Sheets

---

## Key Changes

### 1. Channel-aware State Keys (`sheets.py`)

**Problem**: `sh.get_state(CHAT_ID)` / `sh.set_state(CHAT_ID, {...})` dùng single Telegram `CHAT_ID`. Nếu Zalo interactive + Telegram cùng active, state đè nhau.

**Solution**: Prefix state keys by channel. Backward-compatible.

```python
# sheets.py — new helper
def state_key(channel: str, chat_id: str) -> str:
    """Build channel-scoped state key. E.g. 'telegram:123456', 'zalo:abc123'."""
    return f"{channel}:{chat_id}"
```

**Migration strategy**:
- `get_state(key)`: try prefixed key first, fallback to legacy key (bare `CHAT_ID`)
- `set_state(key, data)`: always write with prefix
- First write migrates: if legacy key exists, read from it, then write to prefixed key
- Telegram callers: `sh.get_state(state_key("telegram", CHAT_ID))`
- Zalo callers: `sh.get_state(state_key("zalo", ZALO_CHAT_ID))`

**Impact on existing handlers**: All `sh.get_state(CHAT_ID)` / `sh.set_state(CHAT_ID, ...)` calls in `handlers/*.py` and `main.py` need to pass `state_key("telegram", CHAT_ID)` instead of bare `CHAT_ID`. This is a bulk find-replace but each call site must be verified.

Files affected:
- `sheets.py` — add `state_key()`, update `get_state()`/`set_state()` fallback logic
- `handlers/transaction.py` — 6 call sites
- `handlers/sepay.py` — 2 call sites
- `handlers/allocation.py` — multiple call sites
- `handlers/reports.py` — 1 call site
- `handlers/manage.py` — multiple call sites
- `handlers/keywords.py` — multiple call sites
- `handlers/accounts.py` — multiple call sites
- `main.py` — `_handle_message` reads state

### 2. BotChannel Protocol (`bot_channel.py`) — NEW

Thin abstraction so handlers can send messages without knowing if target is Telegram or Zalo.

```python
# bot_channel.py
from dataclasses import dataclass
from typing import Protocol

@dataclass
class Option:
    text: str       # Display label (e.g. "🍜 Daily Spending")
    key: str        # Callback identifier (e.g. "daily_spending")

class BotChannel(Protocol):
    channel_name: str   # "telegram" | "zalo"
    chat_id: str

    async def send_text(self, text: str) -> dict | None: ...
    async def send_options(self, prompt: str, options: list[Option],
                           include_new: bool = False) -> dict | None: ...
    async def edit_or_send(self, message_id: int | str | None, text: str) -> dict | None: ...
    async def delete_message(self, message_id: int | str) -> None: ...
```

**TelegramChannel** — wraps existing `telegram_api.py`:
```python
class TelegramChannel:
    channel_name = "telegram"

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    async def send_text(self, text: str):
        return await tg.send_text(text, self.chat_id)

    async def send_options(self, prompt: str, options: list[Option],
                           include_new: bool = False):
        # Convert Options → inline_keyboard buttons
        buttons = [
            {"text": opt.text, "callback_data": opt.key}
            for opt in options
        ]
        rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        if include_new:
            rows.append([{"text": "➕ New category", "callback_data": "new"}])
        return await tg.send_with_buttons(prompt, rows, self.chat_id)

    async def edit_or_send(self, message_id, text):
        if message_id:
            return await tg.edit_message(message_id, text, self.chat_id)
        return await tg.send_text(text, self.chat_id)

    async def delete_message(self, message_id):
        await tg.delete_message(message_id, self.chat_id)
```

**ZaloChannel** — wraps existing `zalo_api.py`:
```python
class ZaloChannel:
    channel_name = "zalo"

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    async def send_text(self, text: str):
        return await zalo.send_text(text, self.chat_id)

    async def send_options(self, prompt: str, options: list[Option],
                           include_new: bool = False):
        # Build numbered text list
        lines = [strip_markdown(prompt), ""]
        for i, opt in enumerate(options, 1):
            lines.append(f"{i}. {strip_markdown(opt.text)}")
        if include_new:
            lines.append(f"{len(options) + 1}. ➕ New category")
        lines.append("")
        lines.append("Reply số để chọn:")
        return await zalo.send_text("\n".join(lines), self.chat_id)

    async def edit_or_send(self, message_id, text):
        # Zalo has no edit_message — always send new
        return await zalo.send_text(strip_markdown(text), self.chat_id)

    async def delete_message(self, message_id):
        pass  # Zalo has no delete — no-op
```

### 3. Numbered Reply Resolver (`handlers/zalo_reply.py`) — NEW

Resolves "1", "2", etc. from Zalo text into category selection.

```python
# handlers/zalo_reply.py

def resolve_numbered_reply(text: str, state: dict) -> str | None:
    """Convert '1' → option key from pending_options stored in state.

    State shape:
      { "step": "await_parent" | "await_sub",
        "pending_options": [{"key": "daily_spending", "text": "🍜 Daily Spending"}, ...],
        ... }

    Returns the option key, or None if text is not a valid number.
    """
    pending = state.get("pending_options", [])
    if not pending:
        return None
    try:
        idx = int(text.strip()) - 1
        if 0 <= idx < len(pending):
            return pending[idx]["key"]
    except (ValueError, IndexError):
        pass
    return None
```

### 4. Modify `handlers/sepay.py` — Category Picker Fan-out

Currently (line 241-256), SePay expense only sends Telegram inline buttons:
```python
# CURRENT — Telegram only
buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
await tg.send_with_buttons(prompt, buttons)
```

**Change to**: Send to both channels. Telegram gets inline buttons (unchanged). Zalo gets numbered list + stores pending_options in state.

```python
# NEW — dual channel
prompt = (
    f"💸 *-{sh.fmt_amount(amount, currency)}*\n"
    f"`{description}`\n\n"
    f"Khoản này thuộc mục nào? 🤔"
)

# Telegram: inline buttons (unchanged behavior)
buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
await tg.send_with_buttons(prompt, buttons)

# Zalo: numbered list (if enabled + interactive)
if ZALO_ENABLED and ZALO_INTERACTIVE:
    from bot_channel import ZaloChannel, Option
    zalo_ch = ZaloChannel(ZALO_CHAT_ID)
    options = [Option(text=b["name"], key=b["id"]) for b in buckets]
    await zalo_ch.send_options(
        f"💸 -{sh.fmt_amount(amount, currency)}\n{description}\n\nKhoản này thuộc mục nào?",
        options,
        include_new=True,
    )
    # Store pending options in Zalo state for numbered reply resolution
    zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
    zalo_options = [{"key": b["id"], "text": b["name"]} for b in buckets]
    if include_new_opt := True:
        zalo_options.append({"key": "__new__", "text": "New category"})
    sh.set_state(zalo_key, {
        "step": "await_parent",
        "row_num": row_num,
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": "out",
        "pending_options": zalo_options,
    })
```

### 5. Modify `main.py` — Zalo Numbered Reply Dispatch

Currently `_process_zalo` sends "phân loại → dùng Telegram" for non-command text. Change to route numbered replies through the category flow.

```python
async def _process_zalo(event: dict):
    # ... existing sender/chat validation ...

    if text.startswith("/"):
        await _handle_zalo_command(text, chat_id)
        return

    # NEW: Check for numbered reply against pending state
    zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
    state = sh.get_state(zalo_key) or {}
    step = state.get("step")

    if step in ("await_parent", "await_sub") and text.strip().isdigit():
        from handlers.zalo_reply import resolve_numbered_reply
        selected_key = resolve_numbered_reply(text, state)
        if selected_key is None:
            await zalo.send_text(
                f"Số không hợp lệ. Chọn từ 1-{len(state.get('pending_options', []))}.",
                chat_id,
            )
            return
        await _handle_zalo_category_selection(selected_key, state, chat_id)
        return

    if step == "await_freetext":
        await _handle_zalo_freetext(text, state, chat_id)
        return

    # Default: help message
    await zalo.send_text(
        "🤖 My Money Went Bot (Zalo)\n\n"
        "Commands:\n"
        "/today — hôm nay tiêu bao nhiêu?\n"
        "/report — chi tiêu tháng này\n"
        "/accounts — list accounts\n\n"
        "Nếu có giao dịch cần phân loại, reply số thứ tự.",
        chat_id,
    )
```

### 6. New handler: `_handle_zalo_category_selection` (in `main.py`)

```python
async def _handle_zalo_category_selection(selected_key: str, state: dict, chat_id: str):
    """Process a Zalo numbered reply for category/sub-category selection."""
    from handlers.transaction import _finalize, _apply_ledger_for_row
    from bot_channel import ZaloChannel, Option

    zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
    row_num = state["row_num"]
    step = state["step"]
    zalo_ch = ZaloChannel(chat_id)

    if step == "await_parent":
        # Handle "new category" selection
        if selected_key == "__new__":
            sh.set_state(zalo_key, {
                **state,
                "step": "await_freetext",
                "freetext_purpose": "new_category",
            })
            await zalo.send_text("📝 Tên category mới? (VD: Gaming)", chat_id)
            return

        bucket_id = selected_key
        sh.finalize_transaction(row_num, bucket_id, "")

        # Check for sub-categories
        subs = sh.get_sub_categories(bucket_id)
        if subs:
            sub_options = [{"key": s["key"], "text": s["label"]} for s in subs]
            sub_options.append({"key": "__other__", "text": "📦 Other"})
            sh.set_state(zalo_key, {
                **state,
                "step": "await_sub",
                "parent_category": bucket_id,
                "pending_options": sub_options,
            })
            options = [Option(text=s["label"], key=s["key"]) for s in subs]
            options.append(Option(text="📦 Other", key="__other__"))
            await zalo_ch.send_options(
                f"✏️ {sh.bucket_label(bucket_id)} — chi tiết?",
                options,
            )
            return

        # No subs — finalize directly
        await _zalo_finalize(row_num, bucket_id, "", state, chat_id)

    elif step == "await_sub":
        parent = state.get("parent_category", "")
        if selected_key == "__other__":
            sh.set_state(zalo_key, {
                **state,
                "step": "await_freetext",
                "freetext_purpose": "sub_label",
            })
            await zalo.send_text("📝 Nhập chi tiết (VD: grab, cafe...):", chat_id)
            return

        sub_display = sh.get_sub_label(parent, selected_key)
        await _zalo_finalize(row_num, parent, sub_display, state, chat_id)


async def _handle_zalo_freetext(text: str, state: dict, chat_id: str):
    """Handle freetext input from Zalo (sub-category label or new category name)."""
    zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
    row_num = state["row_num"]
    purpose = state.get("freetext_purpose", "sub_label")

    if purpose == "new_category":
        # Same logic as handle_inline_new_cat_name but for Zalo
        import unicodedata, re
        name = text.strip()
        if not name or len(name) > 40:
            await zalo.send_text("⚠️ Tên không hợp lệ (1-40 ký tự). Thử lại.", chat_id)
            return
        nid = unicodedata.normalize("NFD", name.lower())
        nid = re.sub(r"[̀-ͯ]", "", nid)
        nid = re.sub(r"[^\w\s]", "", nid)
        nid = re.sub(r"\s+", "_", nid.strip())
        nid = re.sub(r"[^a-z0-9_]", "", nid) or "custom"
        if nid in ("new", "skip", "__new__", "__other__"):
            await zalo.send_text(f"⚠️ Tên '{name}' trùng từ khóa hệ thống. Nhập tên khác.", chat_id)
            return
        tz = pytz.timezone(TIMEZONE)
        month_key = sh.fmt_month(datetime.now(tz))
        existing = sh.get_active_buckets(month_key, force_refresh=True)
        if any(b["id"] == nid for b in existing):
            await zalo.send_text(f"⚠️ '{name}' đã tồn tại. Nhập tên khác.", chat_id)
            return
        sh.write_budget_row(month_key, {"id": nid, "name": name, "allocated": 0, "daily_cap": None})
        sh.invalidate_buckets_cache()
        await _zalo_finalize(row_num, nid, "", state, chat_id)
    else:
        # Sub-category freetext
        parent = state.get("parent_category", "")
        sh.save_custom_sub(parent, text)
        await _zalo_finalize(row_num, parent, f"📦 {text}", state, chat_id)


async def _zalo_finalize(row_num: int, parent_category: str, sub_label: str,
                         state: dict, chat_id: str):
    """Finalize a Zalo-categorized transaction. Mirrors transaction._finalize logic
    but uses plain text instead of Telegram Markdown + buttons."""
    from handlers.transaction import _apply_ledger_for_row

    sh.finalize_transaction(row_num, parent_category, sub_label)

    try:
        _apply_ledger_for_row(row_num)
    except Exception as e:
        print(f"[zalo] ledger write error row={row_num}: {e}")

    zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
    sh.clear_state(zalo_key)

    # Build confirmation (plain text — no Markdown)
    amount = state.get("amount") or 0
    currency = state.get("currency") or "VND"
    parent_name = sh.bucket_label(parent_category)
    sub_disp = f" · {sub_label}" if sub_label else ""

    tz = pytz.timezone(TIMEZONE)
    tx_date_str = state.get("tx_date")
    tx_date = datetime.fromisoformat(tx_date_str) if tx_date_str else datetime.now(tz)
    month_key = sh.fmt_month(tx_date)
    bkt = sh.get_bucket_status(parent_category, month_key)

    msg = f"✅ Logged: {parent_name}{sub_disp}\n💸 -{sh.fmt_amount(amount, currency)}\n\n"

    if bkt["allocated"] > 0:
        pct = sh.calc_pct(bkt["spent"], bkt["allocated"])
        msg += f"{parent_name}: {sh.fmt_amount(bkt['spent'])} / {sh.fmt_amount(bkt['allocated'])} ({pct}%)\n"
        msg += f"Remaining: {sh.fmt_amount(bkt['remaining'])}"
    else:
        msg += f"{parent_name}: tổng tháng này {sh.fmt_amount(bkt['spent'])}"

    await zalo.send_text(msg, chat_id)

    # Check queue for next pending transaction
    await _zalo_process_queue(chat_id)
```

### 7. Transaction Queue for Concurrent SePay Events

When multiple SePay transactions arrive before user replies, they queue up.

**State structure** (in Zalo state — Google Sheets "Bot State" tab):
```json
{
  "step": "await_parent",
  "row_num": 123,
  "amount": 50000,
  "currency": "VND",
  "description": "CAFE ABC",
  "tx_direction": "out",
  "pending_options": [...],
  "queue": [
    {"row_num": 124, "amount": 100000, "currency": "VND", "description": "GRAB XYZ", "tx_direction": "out"}
  ]
}
```

**In `handlers/sepay.py`** — when writing Zalo state, check if there's already an active picker:
```python
# When about to send Zalo category picker:
zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
existing_state = sh.get_state(zalo_key) or {}

if existing_state.get("step") in ("await_parent", "await_sub", "await_freetext"):
    # Active picker exists — queue this transaction
    queue = existing_state.get("queue", [])
    queue.append({
        "row_num": row_num,
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": "out",
    })
    sh.set_state(zalo_key, {**existing_state, "queue": queue})
    await zalo.send_text(
        f"💸 +1 giao dịch mới ({sh.fmt_amount(amount, currency)}). "
        f"Hoàn tất cái hiện tại trước nhé — còn {len(queue)} chờ phân loại.",
        ZALO_CHAT_ID,
    )
else:
    # No active picker — send picker as normal
    # ... (code from section 4 above)
```

**`_zalo_process_queue()`** — after finalizing, pop next from queue:
```python
async def _zalo_process_queue(chat_id: str):
    """After finalizing, check queue and send next picker if any."""
    zalo_key = sh.state_key("zalo", ZALO_CHAT_ID)
    state = sh.get_state(zalo_key) or {}
    queue = state.get("queue", [])

    if not queue:
        return

    next_tx = queue.pop(0)
    # Send picker for next transaction
    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    from bot_channel import ZaloChannel, Option
    zalo_ch = ZaloChannel(chat_id)
    options = [Option(text=b["name"], key=b["id"]) for b in buckets]

    remaining_msg = f" (còn {len(queue)} chờ)" if queue else ""
    await zalo_ch.send_options(
        f"💸 -{sh.fmt_amount(next_tx['amount'], next_tx['currency'])}\n"
        f"{next_tx['description']}\n\n"
        f"Khoản này thuộc mục nào?{remaining_msg}",
        options,
        include_new=True,
    )

    zalo_options = [{"key": b["id"], "text": b["name"]} for b in buckets]
    zalo_options.append({"key": "__new__", "text": "New category"})
    sh.set_state(zalo_key, {
        "step": "await_parent",
        "row_num": next_tx["row_num"],
        "amount": next_tx["amount"],
        "currency": next_tx["currency"],
        "description": next_tx["description"],
        "tx_direction": next_tx["tx_direction"],
        "pending_options": zalo_options,
        "queue": queue,
    })
```

---

## Env Vars (no new vars needed)

Phase 3 uses the same env vars already defined in Phase 1+2:

| Var | Phase | Already exists |
|-----|-------|----------------|
| `ZALO_ENABLED` | 1 | ✅ |
| `ZALO_BOT_TOKEN` | 1 | ✅ |
| `ZALO_CHAT_ID` | 1 | ✅ |
| `ZALO_INTERACTIVE` | 2 | ✅ |
| `ZALO_WEBHOOK_SECRET` | 2 | ✅ |
| `ZALO_USER_ID` | 2 | ✅ |

---

## Files Changed Summary

| Action | File | Change |
|--------|------|--------|
| **NEW** | `bot_channel.py` | `BotChannel` protocol + `TelegramChannel` + `ZaloChannel` |
| **NEW** | `handlers/zalo_reply.py` | `resolve_numbered_reply()` |
| **MODIFY** | `sheets.py` | Add `state_key()`, update `get_state`/`set_state` with prefix fallback |
| **MODIFY** | `main.py` | `_process_zalo` routes numbered replies; add `_handle_zalo_category_selection`, `_handle_zalo_freetext`, `_zalo_finalize`, `_zalo_process_queue` |
| **MODIFY** | `handlers/sepay.py` | Add Zalo picker fan-out + queue logic after line 241 |
| **MODIFY** | `handlers/transaction.py` | `sh.get_state(CHAT_ID)` → `sh.get_state(state_key("telegram", CHAT_ID))` (6 sites) |
| **MODIFY** | `handlers/allocation.py` | State key migration (multiple sites) |
| **MODIFY** | `handlers/reports.py` | State key migration (1 site) |
| **MODIFY** | `handlers/manage.py` | State key migration (multiple sites) |
| **MODIFY** | `handlers/keywords.py` | State key migration (multiple sites) |
| **MODIFY** | `handlers/accounts.py` | State key migration (multiple sites) |
| **MODIFY** | `config.py` | No changes needed |

---

## Test Plan

### Unit tests

- `state_key("telegram", "123")` → `"telegram:123"`
- `get_state("telegram:123")` returns data; `get_state("123")` still works (backward compat)
- `set_state("telegram:123", data)` writes prefixed key
- `resolve_numbered_reply("1", state_with_3_options)` → first option key
- `resolve_numbered_reply("0", ...)` → None
- `resolve_numbered_reply("abc", ...)` → None
- `resolve_numbered_reply("4", state_with_3_options)` → None
- `ZaloChannel.send_options()` builds correct numbered text
- `TelegramChannel.send_options()` builds correct inline keyboard
- Queue: append to existing state, pop from queue, empty queue returns None
- Duplicate tx_id in queue is skipped

### Integration tests

- SePay outgoing tx → Telegram gets inline buttons AND Zalo gets numbered list
- Zalo reply "1" → correct category assigned in Sheet
- Zalo reply "2" → sub-category picker sent (if subs exist)
- Zalo reply then second tx auto-shows next picker from queue
- Invalid number → error message + re-show options
- Telegram callback still works unchanged (all 120+ existing tests pass)
- State key migration: old tests still pass with prefixed keys

### Manual verification

1. Enable `ZALO_INTERACTIVE=true` on Railway
2. Trigger SePay expense → confirm Zalo receives numbered category list
3. Reply "1" from Zalo → verify Sheet has correct category
4. Trigger 2 rapid SePay expenses → confirm queue behavior
5. Reply to first, then second → both categorized correctly
6. Simultaneously test Telegram — inline buttons still work
7. State isolation: Telegram categorize + Zalo categorize at same time don't conflict

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Invalid number reply | "Số không hợp lệ, chọn từ 1-N" + re-show |
| Non-numeric text when awaiting number | Route to help message |
| No pending state but user sends "1" | Standard help text |
| Queue with 5+ transactions | Show count "còn N chờ", process FIFO |
| Zalo disabled mid-conversation | Pending state stays in Sheet, harmless; expires on next write |
| Telegram user categorizes same tx | First-write wins (Sheet row already finalized), second channel sees already-done |

---

## PR Breakdown (suggested)

1. **PR 6**: `sheets.py` state key refactor + bulk migration of all handler call sites + tests
2. **PR 7**: `bot_channel.py` protocol + `TelegramChannel` + `ZaloChannel` + `handlers/zalo_reply.py` + tests
3. **PR 8**: `handlers/sepay.py` dual fan-out + `main.py` numbered reply dispatch + queue logic + integration tests

---

## Tech Debt (Document for Phase 4)

1. **Duplicated finalize logic**: `_zalo_finalize()` in `main.py` partially duplicates `transaction._finalize()`. Future refactor: make `_finalize` channel-aware and call from both paths.
2. **New category name validation**: Duplicated between `handle_inline_new_cat_name` (Telegram) and `_handle_zalo_freetext` (Zalo). Extract to shared helper.
3. **State TTL**: No expiry on Zalo pending state. If user never replies, stale state sits in Sheet. Add lazy expiry check (e.g. 30 min from created_at).
4. **Heavy wizards**: `/manage`, `/keywords`, `/allocate` remain Telegram-only. Port to Zalo requires significant adapter work.
5. **`notifier.py` scope**: Currently only wraps `send_text`. Phase 3 adds direct `zalo.send_text` calls in sepay. Consider expanding notifier to cover category pickers too.
