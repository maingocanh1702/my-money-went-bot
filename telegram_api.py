import httpx
from config import BOT_TOKEN, CHAT_ID

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

_client = httpx.AsyncClient(timeout=10)


async def _post_with_md_fallback(endpoint: str, payload: dict, label: str):
    """POST `payload` with Markdown parse_mode; if Telegram rejects with a
    parse error (400 'can't parse entities'), retry the SAME payload as plain
    text so the user still sees the message. Loud-prints failure either way.

    Markdown failures are the most common silent-drop mode for this bot:
    a slug containing `_` inside an italic-wrapped backtick segment, an
    unbalanced asterisk, etc. Retrying as plain text guarantees delivery
    even when formatting is malformed.
    """
    r = await _client.post(f"{BASE}/{endpoint}", json=payload)
    data = r.json()
    if data.get("ok"):
        return data

    desc = (data.get("description") or "").lower()
    is_parse_err = ("can't parse" in desc) or ("entities" in desc and "parse" in desc)
    if is_parse_err and payload.get("parse_mode"):
        # Retry as plain text — drop parse_mode entirely.
        retry_payload = {k: v for k, v in payload.items() if k != "parse_mode"}
        r2 = await _client.post(f"{BASE}/{endpoint}", json=retry_payload)
        data2 = r2.json()
        if data2.get("ok"):
            print(f"{label} recovered via plaintext fallback. Original error: {desc!r}")
            return data2
        print(f"{label} fallback ALSO failed:", data2)
        return data2

    print(f"{label} error:", data)
    return data


async def send_text(text: str, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    payload = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "Markdown",
    }
    return await _post_with_md_fallback("sendMessage", payload, "sendText")


async def send_with_buttons(text: str, inline_keyboard: list, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    payload = {
        "chat_id":      chat_id,
        "text":         text,
        "parse_mode":   "Markdown",
        "reply_markup": {"inline_keyboard": inline_keyboard},
    }
    return await _post_with_md_fallback("sendMessage", payload, "sendWithButtons")


async def edit_message(
    message_id: int,
    text: str,
    chat_id: str = None,
    inline_keyboard: list | None = None,
):
    """Edit an existing message in place. Optionally replace its inline
    keyboard at the same time — passing inline_keyboard=[] clears the buttons.
    """
    chat_id = chat_id or CHAT_ID
    payload = {
        "chat_id":    chat_id,
        "message_id": message_id,
        "text":       text,
        "parse_mode": "Markdown",
    }
    if inline_keyboard is not None:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
    return await _post_with_md_fallback("editMessageText", payload, "editMessage")


async def delete_message(message_id: int, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    await _client.post(f"{BASE}/deleteMessage", json={
        "chat_id":    chat_id,
        "message_id": message_id,
    })


async def answer_callback(callback_id: str):
    await _client.post(f"{BASE}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
    })


async def set_my_commands():
    commands = [
        {"command": "report",   "description": "📊 Chi tiêu theo account + category (tuần/tháng/quý/năm)"},
        {"command": "today",    "description": "🍜 Hôm nay tiêu bao nhiêu?"},
        {"command": "accounts", "description": "🏦 List accounts / add mới"},
        {"command": "manage",   "description": "⚙️ Sửa/xóa categories"},
        {"command": "keywords", "description": "🔑 Auto-phân loại theo keyword"},
        {"command": "allocate", "description": "💰 (Optional) đặt budget"},
        {"command": "recat",    "description": "↩️ Re-categorize một giao dịch cũ"},
    ]
    await _client.post(f"{BASE}/setMyCommands", json={"commands": commands})


async def drop_pending_updates():
    """Call once after setting webhook to flush stale updates."""
    r = await _client.get(f"{BASE}/getWebhookInfo")
    print("Webhook info:", r.json())


def build_bucket_buttons(buckets: list[dict], prefix: str, include_new: bool = False) -> list[list]:
    """2-column grid of bucket buttons.

    If `include_new=True`, append a full-width '➕ New category' button at the bottom
    (callback_data = f"{prefix}_new"). Used when categorizing a transaction so users
    can create a new bucket inline without going through /manage.
    """
    buttons = [
        {"text": b["name"], "callback_data": f"{prefix}_{b['id']}"}
        for b in buckets
    ]
    # Pair them into rows of 2
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if include_new:
        rows.append([{"text": "➕ New category", "callback_data": f"{prefix}_new"}])
    return rows


def build_sub_buttons(subs: list[dict], prefix: str) -> list[list]:
    buttons = [
        {"text": s["label"], "callback_data": f"{prefix}_{s['key']}"}
        for s in subs
    ]
    return [buttons[i:i+2] for i in range(0, len(buttons), 2)]
