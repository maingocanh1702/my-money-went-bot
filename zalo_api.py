"""
zalo_api.py — Zalo Bot Platform API client (notification-only mode)

Mirrors telegram_api.py's interface but adapted for Zalo Bot constraints:
- Plain text only (no Markdown, no HTML)
- 2000 character limit per message
- No inline buttons, no edit_message, no delete_message
- All calls are no-ops when ZALO_ENABLED is False

API docs: https://bot.zapps.me/docs/call-api/
"""
import re
import httpx
from config import ZALO_ENABLED, ZALO_BOT_TOKEN, ZALO_CHAT_ID

BASE = f"https://bot-api.zaloplatforms.com/bot{ZALO_BOT_TOKEN}" if ZALO_BOT_TOKEN else ""

_client = httpx.AsyncClient(timeout=10)


# ─── Markdown stripping ──────────────────────────────────────
def strip_markdown(text: str) -> str:
    """Convert Telegram Markdown to readable plain text for Zalo.

    Removes formatting markers while keeping the content readable:
    - *bold* → bold
    - _italic_ → italic
    - `code` → code
    - ```code blocks``` → code blocks
    """
    if not text:
        return text

    # Remove code blocks (```...```)
    result = re.sub(r'```[\s\S]*?```', lambda m: m.group(0)[3:-3].strip(), text)
    # Remove inline code (`...`)
    result = re.sub(r'`([^`]+)`', r'\1', result)
    # Remove bold (*...*) — but not bullet points (* at line start)
    result = re.sub(r'(?<!\n)\*([^*\n]+)\*', r'\1', result)
    # Remove italic (_..._)
    result = re.sub(r'_([^_\n]+)_', r'\1', result)
    return result


# ─── Text chunking ───────────────────────────────────────────
def chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    """Split text into chunks of max_chars, breaking at paragraph or line boundaries."""
    if not text:
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) <= max_chars:
        return [normalized]

    chunks = []
    remaining = normalized
    while len(remaining) > max_chars:
        # Try to break at paragraph boundary first
        break_at = remaining.rfind("\n\n", 0, max_chars)
        if break_at > max_chars // 2:
            chunks.append(remaining[:break_at])
            remaining = remaining[break_at + 2:]  # skip the \n\n
        else:
            # Fall back to line boundary
            break_at = remaining.rfind("\n", 0, max_chars)
            if break_at > max_chars // 2:
                chunks.append(remaining[:break_at])
                remaining = remaining[break_at + 1:]
            else:
                # Hard break at max_chars
                chunks.append(remaining[:max_chars])
                remaining = remaining[max_chars:]

    if remaining:
        chunks.append(remaining)
    return chunks


# ─── API calls ───────────────────────────────────────────────
async def _post(method: str, payload: dict, label: str = "") -> dict | None:
    """POST to Zalo Bot API. Returns response dict or None on failure.

    Never raises — Zalo failures should not break SePay transaction processing.
    """
    if not ZALO_ENABLED or not BASE:
        return None

    try:
        r = await _client.post(f"{BASE}/{method}", json=payload)
        data = r.json()
        if not data.get("ok"):
            print(f"[zalo] {label or method} error: {data}")
        return data
    except Exception as e:
        print(f"[zalo] {label or method} exception: {e}")
        return None


async def send_text(text: str, chat_id: str = None) -> dict | None:
    """Send plain text message to Zalo. Auto-strips Markdown and chunks long messages.

    Returns the response from the last chunk, or None if disabled/failed.
    """
    if not ZALO_ENABLED:
        return None

    chat_id = chat_id or ZALO_CHAT_ID
    plain_text = strip_markdown(text)
    chunks = chunk_text(plain_text)

    last_response = None
    for chunk in chunks:
        last_response = await _post("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
        }, "sendText")

    return last_response


async def get_me() -> dict | None:
    """Get bot information. Useful for verifying token is valid."""
    if not ZALO_ENABLED:
        return None
    return await _post("getMe", {}, "getMe")


async def get_updates(offset: int = 0, timeout: int = 30) -> dict | None:
    """Long-poll for updates. Used by scripts/zalo_get_updates.py to discover chat_id."""
    if not ZALO_BOT_TOKEN:
        return None

    payload = {"timeout": str(timeout)}
    if offset:
        payload["offset"] = offset

    try:
        r = await _client.post(
            f"{BASE}/getUpdates",
            json=payload,
            timeout=timeout + 5,
        )
        return r.json()
    except Exception as e:
        print(f"[zalo] getUpdates exception: {e}")
        return None


# ─── Webhook management ──────────────────────────────────────
async def set_webhook(url: str, secret_token: str = "") -> dict | None:
    """Register webhook URL with Zalo Bot API."""
    payload = {"url": url}
    if secret_token:
        payload["secret_token"] = secret_token
    return await _post("setWebhook", payload, "setWebhook")


async def delete_webhook() -> dict | None:
    """Remove webhook URL."""
    return await _post("deleteWebhook", {}, "deleteWebhook")


async def get_webhook_info() -> dict | None:
    """Get current webhook configuration."""
    if not ZALO_ENABLED or not BASE:
        return None
    try:
        r = await _client.post(f"{BASE}/getWebhookInfo")
        return r.json()
    except Exception as e:
        print(f"[zalo] getWebhookInfo exception: {e}")
        return None


# ─── Plain text send (no Markdown stripping) ─────────────────
async def send_text_raw(text: str, chat_id: str = None) -> dict | None:
    """Send already-formatted plain text to Zalo. Skips Markdown stripping.
    Used when the caller has already built Zalo-friendly text (e.g. from
    report builders that generate plain text directly).
    """
    if not ZALO_ENABLED:
        return None

    chat_id = chat_id or ZALO_CHAT_ID
    chunks = chunk_text(text)

    last_response = None
    for chunk in chunks:
        last_response = await _post("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
        }, "sendTextRaw")

    return last_response
