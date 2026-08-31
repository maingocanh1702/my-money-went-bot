"""
messenger.py — Thin multi-channel messaging abstraction for Bot Finance.

Wraps telegram_api.py for Telegram and adds Zalo Bot Platform support.
Zalo renders inline keyboard buttons as numbered plain-text options since
Zalo Bot API only supports plain text messages.

Zalo Bot Platform docs: https://bot.zapps.me/docs/
API pattern: POST https://bot-api.zaloplatforms.com/bot{TOKEN}/sendMessage
             body: {"chat_id": "...", "text": "..."}

Usage:
    from messenger import send_text, send_with_buttons

    # Telegram (default — backwards compatible)
    await send_text("Hello!")

    # Zalo
    await send_text("Hello!", channel="zalo", recipient_id="246845883529197922")
"""

import html

import httpx

from config import ZALO_BOT_TOKEN, ZALO_INLINE_KEYBOARD, ZALO_TEXT_LIMIT

import telegram_api as tg

_ZALO_API_BASE = "https://bot-api.zaloplatforms.com"
_zalo_client = httpx.AsyncClient(timeout=10)


# ─── Public API ────────────────────────────────────────────────


async def send_text(
    text: str,
    channel: str = "telegram",
    recipient_id: str | None = None,
    chat_id: str | None = None,
):
    """Send plain text to the appropriate channel.

    Telegram: delegates to telegram_api.send_text (supports Markdown).
    Zalo: strips Markdown and sends plain text via Zalo Bot API.
    """
    if channel == "zalo" and recipient_id:
        await _zalo_send_text(recipient_id, text)
    else:
        await tg.send_text(text, chat_id=chat_id)


async def send_with_buttons(
    text: str,
    buttons: list[list],
    channel: str = "telegram",
    recipient_id: str | None = None,
    chat_id: str | None = None,
):
    """Send text + buttons.

    Zalo: ALWAYS embeds a numbered category list in the message body so
    the user can see options regardless of whether inline keyboard renders.
    Still tries inline keyboard on top of that (if it works, user has both).

    `buttons` uses Telegram InlineKeyboardMarkup format:
        [[{"text": "Label", "callback_data": "..."}, ...], ...]
    """
    if channel == "zalo" and recipient_id:
        numbered = _buttons_to_numbered_text(buttons)
        full_text = _strip_markdown(text) + "\n\n" + numbered + "\n\nReply số để chọn"
        # Try inline keyboard — but text already has the numbered list as safety net
        if await _zalo_try_inline_keyboard(recipient_id, full_text, buttons):
            return
        # Inline rejected/disabled — send plain text (already has numbered list)
        await _zalo_send_text(recipient_id, full_text)
    else:
        await tg.send_with_buttons(text, buttons, chat_id=chat_id)


# ─── Button → numbered text conversion ────────────────────────


def _buttons_to_numbered_text(buttons: list[list]) -> str:
    """Convert Telegram inline keyboard to numbered plain text.

    Input:  [[{"text": "🛒 Daily", "callback_data": "p_5_daily"}, ...], ...]
    Output: "1. 🛒 Daily\\n2. ...\\n0. ➕ New"

    The "new category" button (callback ending in _new) gets number 0 instead
    of the last sequential number — easier to remember and visually distinct.
    URL buttons are rendered as plain links (not numbered, not selectable).
    """
    numbered: list[str] = []
    new_btn_text: str | None = None
    idx = 1
    for row in buttons:
        for btn in row:
            if "url" in btn:
                numbered.append(f"{btn['text']}: {btn['url']}")
            elif _is_new_category_button(btn):
                new_btn_text = btn["text"]
            else:
                numbered.append(f"{idx}. {btn['text']}")
                idx += 1
    if new_btn_text:
        numbered.append(f"0. {new_btn_text}")
    return "\n".join(numbered)


def buttons_to_bucket_map(buttons: list[list]) -> list[dict]:
    """Extract ordered list of selectable buckets from Telegram buttons.

    Returns: [{"id": "daily_spending", "name": "🛒 Daily Spending"}, ...]
    Only includes callback_data buttons (skips url buttons).
    The "new" category button is EXCLUDED — it's handled separately via
    number 0 on Zalo, so it shouldn't occupy a numbered slot.
    """
    result: list[dict] = []
    for row in buttons:
        for btn in row:
            cb = btn.get("callback_data", "")
            if not cb or "url" in btn:
                continue
            if _is_new_category_button(btn):
                continue
            # callback_data format: "p_{rowNum}_{bucketId}"
            # Example: "p_5_daily_spending" → bucket_id = "daily_spending"
            parts = cb.split("_", 2)
            if len(parts) < 3:
                continue
            bucket_id = parts[2]
            result.append({"id": bucket_id, "name": btn["text"]})
    return result


def _is_new_category_button(btn: dict) -> bool:
    cb = btn.get("callback_data", "")
    parts = cb.split("_", 2)
    return len(parts) >= 3 and parts[2] == "new"


# ─── Markdown stripping ───────────────────────────────────────


def _strip_markdown(text: str) -> str:
    """Strip Markdown formatting tokens for plain-text channels.

    Handles the common tokens used by telegram_api.py:
    bold (*text* or **text**), italic (_text_), monospace (`text`).
    """
    plain = html.unescape(text)
    # Order matters: strip ** before * to avoid partial matches
    for token in ("**", "__", "`", "*", "_"):
        plain = plain.replace(token, "")
    return plain


# ─── Zalo inline keyboard (experimental) ─────────────────────

# Zalo Bot Platform mirrors the Telegram Bot API. If the server supports
# reply_markup → users tap real buttons instead of typing numbers.
# When the API rejects or ignores reply_markup, we silently fall back to
# the numbered-text menu.  Set ZALO_INLINE_KEYBOARD=false to skip the
# attempt entirely.

_zalo_inline_supported: bool | None = None  # tri-state cache: None=untested


async def _zalo_try_inline_keyboard(
    recipient_id: str, text: str, buttons: list[list]
) -> bool:
    """Try sending with reply_markup. Returns True if the API accepted it."""
    global _zalo_inline_supported

    if not ZALO_INLINE_KEYBOARD or not ZALO_BOT_TOKEN:
        return False

    # Once we know it doesn't work, skip the attempt.
    if _zalo_inline_supported is False:
        return False

    plain = _strip_markdown(text)
    reply_markup = {"inline_keyboard": buttons}
    body: dict = {
        "chat_id": recipient_id,
        "text": plain[:ZALO_TEXT_LIMIT],
        "reply_markup": reply_markup,
    }

    try:
        resp = await _zalo_client.post(
            f"{_ZALO_API_BASE}/bot{ZALO_BOT_TOKEN}/sendMessage",
            json=body,
        )
        result = resp.json() if resp.status_code == 200 else {}
        if isinstance(result, dict) and result.get("ok"):
            if _zalo_inline_supported is None:
                _zalo_inline_supported = True
                print("[zalo] inline_keyboard supported — using real buttons")
            return True
        # API returned ok=false or non-200 → not supported
        if _zalo_inline_supported is None:
            _zalo_inline_supported = False
            print("[zalo] inline_keyboard not supported — falling back to numbered text")
        return False
    except Exception as exc:
        if _zalo_inline_supported is None:
            _zalo_inline_supported = False
            print(f"[zalo] inline_keyboard probe failed ({exc}) — falling back to numbered text")
        return False


def reset_zalo_inline_cache() -> None:
    """Reset the inline keyboard support cache (for testing)."""
    global _zalo_inline_supported
    _zalo_inline_supported = None


# ─── Zalo Bot Platform send ──────────────────────────────────


async def _zalo_send_text(recipient_id: str, text: str) -> None:
    """Send plain text to a Zalo user via Zalo Bot Platform API.

    API: POST https://bot-api.zaloplatforms.com/bot{TOKEN}/sendMessage
    Body: {"chat_id": "...", "text": "..."}
    Response: {"ok": true, "result": {"message_id": "...", "date": 123}}

    Strips Markdown, chunks if over ZALO_TEXT_LIMIT.
    """
    if not ZALO_BOT_TOKEN:
        print("[zalo] send skipped — ZALO_BOT_TOKEN not configured")
        return

    plain = _strip_markdown(text)
    chunks = _chunk_text(plain)
    for chunk in chunks:
        resp = await _zalo_client.post(
            f"{_ZALO_API_BASE}/bot{ZALO_BOT_TOKEN}/sendMessage",
            json={"chat_id": recipient_id, "text": chunk},
        )
        resp.raise_for_status()
        body = resp.json()
        if not (isinstance(body, dict) and body.get("ok")):
            print(f"[zalo] send error: {body}")
            raise RuntimeError(f"Zalo Bot API rejected send: {body!r}")


def _chunk_text(text: str) -> list[str]:
    """Split text into chunks of at most ZALO_TEXT_LIMIT characters.

    Prefers splitting at newline boundaries to avoid breaking mid-sentence.
    """
    if len(text) <= ZALO_TEXT_LIMIT:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > ZALO_TEXT_LIMIT:
        split_at = remaining.rfind("\n", 0, ZALO_TEXT_LIMIT + 1)
        if split_at <= 0:
            split_at = ZALO_TEXT_LIMIT
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
