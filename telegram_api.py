import httpx
from config import BOT_TOKEN, CHAT_ID

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

_client = httpx.AsyncClient(timeout=10)


async def send_text(text: str, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    r = await _client.post(f"{BASE}/sendMessage", json={
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "Markdown",
    })
    data = r.json()
    if not data.get("ok"):
        print("sendText error:", data)
    return data


async def send_with_buttons(text: str, inline_keyboard: list, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    r = await _client.post(f"{BASE}/sendMessage", json={
        "chat_id":      chat_id,
        "text":         text,
        "parse_mode":   "Markdown",
        "reply_markup": {"inline_keyboard": inline_keyboard},
    })
    data = r.json()
    if not data.get("ok"):
        print("sendWithButtons error:", data)
    return data


async def edit_message(message_id: int, text: str, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    await _client.post(f"{BASE}/editMessageText", json={
        "chat_id":    chat_id,
        "message_id": message_id,
        "text":       text,
        "parse_mode": "Markdown",
    })


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
        {"command": "status",   "description": "📊 Tổng quan tháng này"},
        {"command": "today",    "description": "🍜 Hôm nay tiêu bao nhiêu?"},
        {"command": "banks",    "description": "🏦 Chi tiêu theo từng bank account"},
        {"command": "manage",   "description": "⚙️ Sửa/xóa categories"},
        {"command": "allocate", "description": "💰 (Optional) đặt budget"},
        {"command": "weekly",   "description": "📈 Tổng kết tuần"},
        {"command": "report",   "description": "📅 Báo cáo tháng đầy đủ"},
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
