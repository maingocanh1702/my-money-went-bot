"""
main.py — FastAPI entry point
Receives SePay webhooks and Telegram updates via a single /webhook endpoint.
"""
from fastapi import FastAPI, Request, BackgroundTasks, Query
from fastapi.responses import JSONResponse
import asyncio
import hmac
import uuid

from config import CHAT_ID, TELEGRAM_WEBHOOK_SECRET, CRON_SECRET
import sheets as sh
import telegram_api as tg
from handlers.sepay        import handle_sepay_webhook
from handlers.transaction import handle_parent_selected, handle_sub_selected, handle_freetext_sub, handle_recategorize, handle_inline_new_cat_name
from handlers.allocation  import (
    start_monthly_allocation, handle_alloc_callback,
    handle_alloc_amount_input, handle_new_bucket_name, handle_new_bucket_amount,
    handle_edit_bucket_amount,
)
from handlers.reports     import send_today_status, send_daily_recap, handle_daily_excuse
from handlers.manage      import (
    start_manage, handle_manage_callback,
    handle_manage_amount, handle_manage_rename, handle_sub_rename,
    handle_add_cat_name, handle_add_cat_amount,
)
from handlers.keywords    import (
    start_keywords, handle_keywords_callback,
    handle_keyword_input, handle_edit_keyword_input,
)
from handlers.accounts    import (
    handle_accounts_callback, handle_assign_callback,
    handle_new_account_name, handle_new_account_balance,
    cmd_accounts,
)
from handlers.report      import cmd_report, handle_report_callback

app = FastAPI(title="Financial Tracking Bot")

# ─── Valid callback prefixes & their minimum part counts ──────
_CALLBACK_MIN_PARTS = {
    "p": 2, "s": 2, "al": 2, "recat": 2,
    "mg": 2, "kw": 2, "acc": 2, "asg": 2, "rpt": 2,
}


@app.on_event("startup")
async def on_startup():
    import os
    print(f"[startup] running on port {os.environ.get('PORT', 8000)}")
    try:
        await tg.set_my_commands()
    except Exception as e:
        print(f"[startup] set_my_commands failed (no internet?): {e}")


# ─── Webhook endpoint ─────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    """
    Single endpoint handling both SePay and Telegram payloads.
    Returns 200 immediately — processing runs in background.

    Security:
      - Telegram updates: validated via X-Telegram-Bot-Api-Secret-Token header
      - SePay webhooks: validated inside handle_sepay_webhook via SEPAY_SECRET
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    # Telegram updates carry "update_id" — require webhook secret header
    if "update_id" in body:
        tg_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(tg_secret, TELEGRAM_WEBHOOK_SECRET):
            print("[webhook] rejected: invalid Telegram webhook secret")
            return JSONResponse({"ok": True})  # 200 to avoid Telegram retries

    bg.add_task(_process, body)
    return JSONResponse({"ok": True})          # ← 200 right away, no 302


# ─── Scheduled triggers (call via cron on VPS) ───────────────
# Phase 2 removed run_weekly_summary + run_monthly_report (consolidated
# into unified /report with period buttons). Cron-driven weekly/monthly
# reports no longer make sense — /report is interactive, user opens it
# when they want. Kept: daily recap + monthly-allocation prompt.
@app.post("/trigger/monthly-allocation")
async def trigger_monthly_allocation(secret: str = Query(default="")):
    if not hmac.compare_digest(secret, CRON_SECRET):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(start_monthly_allocation())
    return {"ok": True}


@app.post("/trigger/daily-recap")
async def trigger_daily_recap(secret: str = Query(default="")):
    if not hmac.compare_digest(secret, CRON_SECRET):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(send_daily_recap())
    return {"ok": True}


# ─── Health check ─────────────────────────────────────────────
@app.get("/")
async def health():
    return {"status": "ok", "bot": "Financial Tracking Bot"}


# ─── Main dispatcher ──────────────────────────────────────────
async def _process(body: dict):
    try:
        # --- Telegram update ---
        if "update_id" in body:
            if "callback_query" in body:
                await _handle_callback(body["callback_query"])
            elif "message" in body:
                await _handle_message(body["message"])
        # --- SePay webhook ---
        else:
            await handle_sepay_webhook(body)
    except Exception:
        import traceback
        err_id = uuid.uuid4().hex[:8]
        print(f"ERROR [{err_id}]:", traceback.format_exc())
        try:
            await tg.send_text(f"⚠️ Bot gặp lỗi (ref: `{err_id}`). Check server logs.")
        except Exception:
            pass  # don't let notification failure mask the original error


def _validate_callback(cb: dict) -> tuple[str, list[str], int] | None:
    """Validate callback_query shape and return (prefix, parts, message_id).

    Returns None if the callback is malformed — caller should bail.
    """
    data = cb.get("data") or ""
    message = cb.get("message")
    if not data or not message or "message_id" not in message:
        return None

    parts = data.split("_")
    prefix = parts[0]

    if prefix not in _CALLBACK_MIN_PARTS:
        return None

    if len(parts) < _CALLBACK_MIN_PARTS[prefix]:
        return None

    return prefix, parts, message["message_id"]


async def _handle_callback(cb: dict):
    callback_id = cb.get("id")
    if not callback_id:
        print("[callback] rejected: missing callback id")
        return

    await tg.answer_callback(callback_id)

    # Validate sender identity
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    if str(chat_id) != str(CHAT_ID):
        print(f"[callback] rejected: chat_id={chat_id} != CHAT_ID={CHAT_ID}")
        return

    validated = _validate_callback(cb)
    if validated is None:
        print(f"[callback] rejected: invalid shape, data={cb.get('data')!r}")
        return

    prefix, parts, message_id = validated

    if prefix == "p":
        await handle_parent_selected(parts, message_id)
    elif prefix == "s":
        await handle_sub_selected(parts, message_id)
    elif prefix == "al":
        await handle_alloc_callback(parts, message_id)
    elif prefix == "recat":
        await handle_recategorize(parts, message_id)
    elif prefix == "mg":
        await handle_manage_callback(parts, message_id)
    elif prefix == "kw":
        await handle_keywords_callback(parts, message_id)
    elif prefix == "acc":
        await handle_accounts_callback(parts, message_id)
    elif prefix == "asg":
        await handle_assign_callback(parts, message_id)
    elif prefix == "rpt":
        await handle_report_callback(parts, message_id)


async def _handle_message(message: dict):
    # Validate sender identity
    chat_id = message.get("chat", {}).get("id")
    if str(chat_id) != str(CHAT_ID):
        print(f"[message] rejected: chat_id={chat_id} != CHAT_ID={CHAT_ID}")
        return

    if message.get("from", {}).get("is_bot"):
        return                                  # ignore bot echoes

    text  = (message.get("text") or "").strip()
    state = sh.get_state(CHAT_ID) or {}

    # Commands take priority
    if text.startswith("/"):
        await _handle_command(text)
        return

    # Multi-step state machine
    step = state.get("step")
    if step == "await_freetext":
        await handle_freetext_sub(text, state)
    elif step == "await_alloc_amount":
        await handle_alloc_amount_input(text, state)
    elif step == "await_edit_bucket_amount":
        await handle_edit_bucket_amount(text, state)
    elif step == "await_new_bucket_name":
        await handle_new_bucket_name(text, state)
    elif step == "await_new_bucket_amount":
        await handle_new_bucket_amount(text, state)
    elif step == "await_daily_excuse":
        await handle_daily_excuse(text, state)
    elif step == "await_manage_amount":
        await handle_manage_amount(text, state)
    elif step == "await_manage_rename":
        await handle_manage_rename(text, state)
    elif step == "await_sub_rename":
        await handle_sub_rename(text, state)
    elif step == "await_add_cat_name":
        await handle_add_cat_name(text, state)
    elif step == "await_add_cat_amount":
        await handle_add_cat_amount(text, state)
    elif step == "await_inline_new_cat_name":
        await handle_inline_new_cat_name(text, state)
    elif step == "await_keyword_input":
        await handle_keyword_input(text, state)
    elif step == "await_edit_keyword":
        await handle_edit_keyword_input(text, state)
    elif step == "await_new_account_name":
        await handle_new_account_name(text, state)
    elif step == "await_new_account_balance":
        # Legacy: kept so wizards started before the simplification can finish.
        await handle_new_account_balance(text, state)
    else:
        await tg.send_text(
            "🤖 *Financial Tracking Bot*\n\n"
            "Tự động ghi mọi giao dịch ngân hàng. Bạn chỉ cần phân loại — bot lo phần còn lại.\n\n"
            "/report   — chi tiêu theo account + category (tuần/tháng/quý/năm)\n"
            "/today    — hôm nay tiêu bao nhiêu?\n"
            "/accounts — list account đã setup / add mới\n"
            "/manage   — sửa categories\n"
            "/keywords — auto-phân loại theo keyword\n"
            "/allocate — (optional) đặt budget cho từng mục"
        )


async def _handle_command(text: str):
    cmd = text.split()[0].lower()
    if cmd == "/today":
        await send_today_status()
    elif cmd == "/report":
        await cmd_report(text)
    elif cmd == "/accounts":
        await cmd_accounts(text)
    elif cmd == "/manage":
        await start_manage()
    elif cmd == "/keywords":
        await start_keywords()
    elif cmd == "/allocate":
        await start_monthly_allocation()
    else:
        await tg.send_text(
            "Unknown command. Try /today, /report, /accounts, /manage, "
            "/keywords, or /allocate."
        )
