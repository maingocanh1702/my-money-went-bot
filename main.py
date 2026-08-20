"""
main.py — FastAPI entry point
Receives SePay webhooks and Telegram updates via a single /webhook endpoint.
"""
from fastapi import FastAPI, Request, BackgroundTasks, Query
from fastapi.responses import JSONResponse
import asyncio
import hmac
import uuid
from datetime import datetime
import pytz

from config import (
    CHAT_ID, TELEGRAM_WEBHOOK_SECRET, CRON_SECRET, TIMEZONE,
    TELEGRAM_ENABLED, ZALO_ENABLED, ZALO_INTERACTIVE, ZALO_WEBHOOK_SECRET, ZALO_USER_ID,
)
import notifier
import sheets as sh
import telegram_api as tg
import zalo_api as zalo
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
from handlers.cashback    import (
    cmd_cashback, handle_cashback_callback,
    handle_cashback_keyword_input, handle_cashback_pct_input,
    handle_cashback_limits_input, _save_rule,
)

app = FastAPI(title="Financial Tracking Bot")

# ─── Valid callback prefixes & their minimum part counts ──────
_CALLBACK_MIN_PARTS = {
    "p": 2, "s": 2, "al": 2, "recat": 2,
    "mg": 2, "kw": 2, "acc": 2, "asg": 2, "rpt": 2,
    "cb": 2,
}


@app.on_event("startup")
async def on_startup():
    import os
    print(f"[startup] running on port {os.environ.get('PORT', 8000)}")
    if TELEGRAM_ENABLED:
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

    # Telegram updates carry "update_id" — reject when Telegram is disabled or
    # when the webhook secret header is missing/wrong.
    if "update_id" in body:
        if not TELEGRAM_ENABLED:
            return JSONResponse({"ok": True})
        tg_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(tg_secret, TELEGRAM_WEBHOOK_SECRET):
            print("[webhook] rejected: invalid Telegram webhook secret")
            return JSONResponse({"ok": True})  # 200 to avoid Telegram retries

    bg.add_task(_process, body)
    return JSONResponse({"ok": True})          # ← 200 right away, no 302


# ─── Zalo webhook endpoint ────────────────────────────────────
@app.post("/zalo/webhook")
async def zalo_webhook(request: Request, bg: BackgroundTasks):
    """Receive Zalo Bot Platform webhook events.

    Security:
      - Validates X-Bot-Api-Secret-Token header against ZALO_WEBHOOK_SECRET
      - Only processes events when ZALO_ENABLED and ZALO_INTERACTIVE are True
      - Rejects messages from non-authorized users (ZALO_USER_ID)
    """
    if not (ZALO_ENABLED and ZALO_INTERACTIVE):
        return JSONResponse({"ok": True})

    if not ZALO_WEBHOOK_SECRET or not ZALO_USER_ID:
        print("[zalo-webhook] rejected: interactive mode missing secret or user id")
        return JSONResponse({"ok": True})

    zalo_secret = request.headers.get("x-bot-api-secret-token", "")
    if not hmac.compare_digest(zalo_secret, ZALO_WEBHOOK_SECRET):
        print("[zalo-webhook] rejected: invalid webhook secret")
        return JSONResponse({"ok": True})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    # Zalo webhook payload: { ok: true, result: { event_name, message } }
    result = body.get("result", body)  # tolerate both wrapped and flat
    event_name = result.get("event_name", "")

    if event_name != "message.text.received":
        return JSONResponse({"ok": True})  # ignore non-text events

    bg.add_task(_process_zalo, result)
    return JSONResponse({"ok": True})


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
            await notifier.send_text(f"⚠️ Bot gặp lỗi (ref: `{err_id}`). Check server logs.")
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
    elif prefix == "cb":
        await handle_cashback_callback(parts, message_id)


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
    elif step == "cashback_await_keyword":
        await handle_cashback_keyword_input(text, state)
    elif step == "cashback_await_pct":
        await handle_cashback_pct_input(text, state)
    elif step == "cashback_await_limits":
        await handle_cashback_limits_input(text, state)
    else:
        await tg.send_text(
            "🤖 *Financial Tracking Bot*\n\n"
            "Tự động ghi mọi giao dịch ngân hàng. Bạn chỉ cần phân loại — bot lo phần còn lại.\n\n"
            "/report    — chi tiêu theo account + category (tuần/tháng/quý/năm)\n"
            "/today     — hôm nay tiêu bao nhiêu?\n"
            "/accounts  — list account đã setup / add mới\n"
            "/manage    — sửa categories\n"
            "/keywords  — auto-phân loại theo keyword\n"
            "/cashback  — tracking cashback per thẻ\n"
            "/allocate  — (optional) đặt budget cho từng mục\n"
            "/recat     — re-categorize một giao dịch cũ theo số dòng"
        )


async def _cmd_recat(text: str):
    """/recat <row_num> — re-categorize a past transaction via the bucket picker."""
    parts = text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await tg.send_text("Usage: `/recat <row_number>`\nVd: `/recat 125`")
        return
    row_num = int(parts[1])
    if row_num < 2:
        await tg.send_text(f"⚠️ Không tìm thấy transaction row {row_num}.")
        return
    row = sh.get_transaction_row(row_num)
    if not row:
        await tg.send_text(f"⚠️ Không tìm thấy transaction row {row_num}.")
        return
    direction = "in" if (row[6] if len(row) > 6 else "") == "Tiền vào" else "out"
    if direction == "in":
        await tg.send_text("ℹ️ Income hiện không cần category. Không recat.")
        return
    ledger_type = (row[17] if len(row) > 17 else "").strip().lower()
    if ledger_type in ("transfer", "cc_payment"):
        await tg.send_text("ℹ️ Giao dịch chuyển khoản / trả thẻ có ledger riêng — không recat.")
        return
    amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
    description = row[5] if len(row) > 5 else ""
    currency = sh.row_currency(row)
    row_month = row[14] if len(row) > 14 else ""
    month_key = row_month or sh.fmt_month(datetime.now(pytz.timezone(TIMEZONE)))
    buckets = sh.get_active_buckets(month_key)
    if not buckets:
        await tg.send_text(f"⚠️ Không có category active cho tháng {month_key}. Dùng /manage trước.")
        return
    sh.reset_transaction_row(row_num)
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": row_num,
        "amount": amount, "currency": currency, "description": description,
        "month_key": month_key,
        "tx_date": row[1] if len(row) > 1 else "",
    })
    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.send_with_buttons(
        f"↩️ *Re-categorize: -{sh.fmt_amount(amount, currency)}*\n"
        f"`{description}`\n\nKhoản này thuộc mục nào?",
        buttons,
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
    elif cmd == "/recat":
        await _cmd_recat(text)
    elif cmd == "/cashback":
        await cmd_cashback(text)
    else:
        await tg.send_text(
            "Unknown command. Try /today, /report, /accounts, /manage, "
            "/keywords, /cashback, /allocate, or /recat."
        )


# ─── Zalo dispatcher ──────────────────────────────────────────

# State key prefix for Zalo — ensures no collision with Telegram state
# (different chat_id values, but prefix makes intent explicit in logs)
_ZALO_STATE_PREFIX = "zalo_kw_"


async def _process_zalo(event: dict):
    """Process a Zalo text message event.

    Supports interactive commands (keywords) via text-based state machine
    since Zalo has no inline buttons.
    """
    try:
        message = event.get("message", {})
        sender = message.get("from", {})
        chat = message.get("chat", {})
        text = (message.get("text") or "").strip()
        chat_id = chat.get("id", "")

        # Reject bot echoes
        if sender.get("is_bot"):
            return

        # Validate sender identity
        sender_id = str(sender.get("id", ""))
        if ZALO_USER_ID and sender_id != ZALO_USER_ID:
            print(f"[zalo] rejected: sender_id={sender_id} != ZALO_USER_ID={ZALO_USER_ID}")
            return

        # Only handle private chats
        if chat.get("chat_type", "").upper() not in ("PRIVATE", ""):
            return

        if text.startswith("/"):
            # Guard: while picker is active only /cancel may run.
            # Any other command would clobber picker state and lose the pending row.
            state = sh.get_state(chat_id) or {}
            if state.get("step") == "zalo_tx_pick":
                if text.strip().lower().split()[0] == "/cancel":
                    sh.set_state(chat_id, {})
                    await zalo.send_text("Đã hủy.", chat_id)
                else:
                    buckets = state.get("buckets") or []
                    await zalo.send_text(
                        f"Đang chờ phân loại giao dịch này — reply số, hoặc /cancel.\n\n"
                        f"{_format_zalo_bucket_options(buckets)}",
                        chat_id,
                    )
                return
            await _handle_zalo_command(text, chat_id)
        else:
            # Check for active Zalo state machine (keywords interactive)
            await _handle_zalo_text(text, chat_id)
    except Exception:
        import traceback
        err_id = uuid.uuid4().hex[:8]
        print(f"ZALO ERROR [{err_id}]:", traceback.format_exc())
        try:
            await zalo.send_text(f"⚠️ Bot gặp lỗi (ref: {err_id}). Check server logs.", chat_id)
        except Exception:
            pass


async def _handle_zalo_text(text: str, chat_id: str):
    """Route non-command text through the Zalo state machine.

    If no active state, show help menu.
    """
    state = sh.get_state(chat_id) or {}
    step = state.get("step", "")

    # Keywords state machine
    if step == "zalo_kw_list":
        await _zalo_kw_handle_list_reply(text, chat_id, state)
    elif step == "zalo_kw_actions":
        await _zalo_kw_handle_action_reply(text, chat_id, state)
    elif step == "zalo_kw_confirm_del":
        await _zalo_kw_handle_confirm_del(text, chat_id, state)
    elif step == "zalo_kw_await_keyword":
        await _zalo_kw_handle_keyword_input(text, chat_id, state)
    elif step == "zalo_kw_pick_bucket":
        await _zalo_kw_handle_bucket_pick(text, chat_id, state)
    elif step == "zalo_kw_await_edit_keyword":
        await _zalo_kw_handle_edit_keyword(text, chat_id, state)
    elif step == "zalo_kw_pick_edit_bucket":
        await _zalo_kw_handle_edit_bucket_pick(text, chat_id, state)
    # Manage categories state machine
    elif step == "zalo_mg_list":
        await _zalo_mg_handle_list_reply(text, chat_id, state)
    elif step == "zalo_mg_actions":
        await _zalo_mg_handle_action_reply(text, chat_id, state)
    elif step == "zalo_mg_confirm_del":
        await _zalo_mg_handle_confirm_del(text, chat_id, state)
    elif step == "zalo_mg_await_rename":
        await _zalo_mg_handle_rename(text, chat_id, state)
    elif step == "zalo_mg_await_amount":
        await _zalo_mg_handle_amount(text, chat_id, state)
    elif step == "zalo_mg_await_add_name":
        await _zalo_mg_handle_add_name(text, chat_id, state)
    elif step == "zalo_mg_await_add_amount":
        await _zalo_mg_handle_add_amount(text, chat_id, state)
    elif step == "zalo_mg_subs":
        await _zalo_mg_handle_sub_reply(text, chat_id, state)
    elif step == "zalo_mg_sub_actions":
        await _zalo_mg_handle_sub_action(text, chat_id, state)
    elif step == "zalo_mg_await_sub_rename":
        await _zalo_mg_handle_sub_rename(text, chat_id, state)
    elif step == "zalo_mg_confirm_sub_del":
        await _zalo_mg_handle_confirm_sub_del(text, chat_id, state)
    # Allocate budget state machine
    elif step == "zalo_al_list":
        await _zalo_al_handle_list_reply(text, chat_id, state)
    elif step == "zalo_al_await_amount":
        await _zalo_al_handle_amount(text, chat_id, state)
    elif step == "zalo_tx_pick":
        await _zalo_handle_tx_pick(text, chat_id, state)
    else:
        # No active state — show help
        await zalo.send_text(
            "🤖 My Money Went Bot (Zalo)\n\n"
            "Commands:\n"
            "/today — hôm nay tiêu bao nhiêu?\n"
            "/report — chi tiêu tháng này\n"
            "/accounts — list accounts\n"
            "/keywords — quản lý keyword rules\n"
            "/manage — quản lý categories\n"
            "/allocate — set ngân sách tháng\n\n"
            "/cancel — Hủy thao tác",
            chat_id,
        )


async def _handle_zalo_command(text: str, chat_id: str):
    """Handle commands from Zalo."""
    from handlers.reports import _build_today_text
    from handlers.report import build_report_text, _PERIOD_ALIASES
    from handlers.accounts import _account_list_lines

    cmd_parts = text.strip().split()
    cmd = cmd_parts[0].lower()

    if cmd == "/cancel":
        sh.set_state(chat_id, {})
        await zalo.send_text("❌ Đã hủy.", chat_id)
        return

    if cmd == "/today":
        msg = _build_today_text()
        await zalo.send_text(msg, chat_id)

    elif cmd == "/report":
        # Parse optional period arg
        period_code = "m"
        if len(cmd_parts) >= 2:
            period_code = _PERIOD_ALIASES.get(cmd_parts[1].lower(), "m")
        msg = build_report_text(period_code)
        await zalo.send_text(msg, chat_id)

    elif cmd == "/accounts":
        lines = _account_list_lines()
        msg = "Accounts đã setup\n\n" + "\n\n".join(lines)
        await zalo.send_text(msg, chat_id)

    elif cmd == "/keywords":
        await _zalo_kw_show_list(chat_id)

    elif cmd == "/manage":
        await _zalo_mg_show_list(chat_id)

    elif cmd == "/allocate":
        await _zalo_al_show_list(chat_id)

    else:
        await zalo.send_text(
            "Commands hỗ trợ trên Zalo:\n"
            "/today — hôm nay tiêu bao nhiêu?\n"
            "/report — chi tiêu tháng này\n"
            "/report tuần — chi tiêu tuần này\n"
            "/accounts — list accounts\n"
            "/keywords — quản lý keyword rules\n"
            "/manage — quản lý categories\n"
            "/allocate — set ngân sách tháng\n\n"
            "/cancel — Hủy thao tác",
            chat_id,
        )


# ─── Zalo Keywords: text-based interactive flow ───────────────
# Since Zalo has no inline buttons, all interaction uses numbered menus
# and text replies. State is stored per Zalo chat_id.

async def _zalo_kw_show_list(chat_id: str):
    """Show all keyword rules as a numbered list + instructions."""
    from datetime import datetime as _dt
    import pytz

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(_dt.now(tz))

    rules = sh.get_keyword_rules(force_refresh=True)

    if not rules:
        sh.set_state(chat_id, {"step": "zalo_kw_list", "month_key": month_key})
        await zalo.send_text(
            "🔑 Keyword Rules\n\n"
            "Chưa có rule nào.\n\n"
            "Khi giao dịch có description chứa keyword, bot sẽ tự động "
            "phân loại vào category bạn cấu hình.\n\n"
            "VD: highland → ☕ Coffee, winmart → 🍜 Food\n\n"
            "Reply:\n"
            '- "add" để thêm rule mới\n'
            "- /cancel để thoát",
            chat_id,
        )
        return

    msg = "🔑 Keyword Rules\n\n"
    for i, r in enumerate(rules, 1):
        bucket_name = sh.bucket_label(r["bucket_id"])
        sub = f" · {r['sub_label']}" if r["sub_label"] else ""
        msg += f"{i}. {r['keyword']} → {bucket_name}{sub}\n"

    msg += (
        "\nReply:\n"
        '- "add" để thêm rule mới\n'
        '- Số (VD: "3") để sửa/xóa rule đó\n'
        "- /cancel để thoát"
    )

    sh.set_state(chat_id, {"step": "zalo_kw_list", "month_key": month_key})
    await zalo.send_text(msg, chat_id)


async def _zalo_kw_handle_list_reply(text: str, chat_id: str, state: dict):
    """Handle user reply when viewing the keyword list.

    Expected: 'add' to add new, a number to select a rule.
    """
    text_lower = text.strip().lower()

    if text_lower == "add":
        await _zalo_kw_prompt_add(chat_id, state)
        return

    # Try to parse as a number (rule index)
    if text.isdigit():
        idx = int(text)
        rules = sh.get_keyword_rules(force_refresh=True)
        if 1 <= idx <= len(rules):
            rule = rules[idx - 1]
            await _zalo_kw_show_actions(chat_id, state, rule, idx)
            return
        else:
            await zalo.send_text(
                f"⚠️ Số {idx} không hợp lệ. Có {len(rules)} rules.",
                chat_id,
            )
            return

    await zalo.send_text(
        '⚠️ Không hiểu. Reply "add" hoặc số thứ tự rule.',
        chat_id,
    )


async def _zalo_kw_show_actions(chat_id: str, state: dict, rule: dict, idx: int):
    """Show the action menu for a selected rule."""
    bucket_name = sh.bucket_label(rule["bucket_id"])
    sub = f" · {rule['sub_label']}" if rule["sub_label"] else ""

    msg = (
        f"🔑 Rule #{idx}: {rule['keyword']} → {bucket_name}{sub}\n\n"
        "Bạn muốn làm gì?\n\n"
        "Reply:\n"
        '- "edit" — Đổi keyword\n'
        '- "cat" — Đổi category\n'
        '- "del" — Xóa rule\n'
        '- "back" — Quay lại danh sách'
    )

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_kw_actions",
        "selected_row_num": rule["row_num"],
        "selected_idx": idx,
    })
    await zalo.send_text(msg, chat_id)


async def _zalo_kw_handle_action_reply(text: str, chat_id: str, state: dict):
    """Handle action menu reply for a selected rule."""
    text_lower = text.strip().lower()
    row_num = state.get("selected_row_num")

    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)

    if not rule:
        await zalo.send_text("⚠️ Rule không còn tồn tại.", chat_id)
        await _zalo_kw_show_list(chat_id)
        return

    if text_lower == "del":
        bucket_name = sh.bucket_label(rule["bucket_id"])
        sh.set_state(chat_id, {
            **state,
            "step": "zalo_kw_confirm_del",
        })
        await zalo.send_text(
            f"⚠️ Xóa rule này?\n\n"
            f"{rule['keyword']} → {bucket_name}\n\n"
            'Reply "yes" để xác nhận, "no" để hủy.',
            chat_id,
        )

    elif text_lower == "edit":
        sh.set_state(chat_id, {
            **state,
            "step": "zalo_kw_await_edit_keyword",
        })
        await zalo.send_text(
            f"✏️ Keyword hiện tại: {rule['keyword']}\n\n"
            "Nhập keyword mới (1 keyword duy nhất).\n"
            "/cancel để hủy.",
            chat_id,
        )

    elif text_lower == "cat":
        await _zalo_kw_prompt_edit_bucket(chat_id, state, rule)

    elif text_lower == "back":
        await _zalo_kw_show_list(chat_id)

    else:
        await zalo.send_text(
            '⚠️ Không hiểu. Reply "edit", "cat", "del" hoặc "back".',
            chat_id,
        )


async def _zalo_kw_handle_confirm_del(text: str, chat_id: str, state: dict):
    """Handle delete confirmation reply."""
    text_lower = text.strip().lower()
    row_num = state.get("selected_row_num")

    if text_lower in ("yes", "y", "co", "có"):
        rules = sh.get_keyword_rules(force_refresh=True)
        rule = next((r for r in rules if r["row_num"] == row_num), None)

        sh.soft_delete_keyword_rule(row_num)

        if rule:
            bucket_name = sh.bucket_label(rule["bucket_id"])
            await zalo.send_text(
                f"🗑️ Đã xóa: {rule['keyword']} → {bucket_name}",
                chat_id,
            )
        else:
            await zalo.send_text("🗑️ Đã xóa rule.", chat_id)

        await _zalo_kw_show_list(chat_id)

    elif text_lower in ("no", "n", "khong", "không"):
        await zalo.send_text("← Đã hủy xóa.", chat_id)
        await _zalo_kw_show_list(chat_id)

    else:
        await zalo.send_text(
            '⚠️ Reply "yes" để xóa, "no" để hủy.',
            chat_id,
        )


# ─── Zalo Keywords: Add flow ──────────────────────────────────

async def _zalo_kw_prompt_add(chat_id: str, state: dict):
    """Ask user to type keyword(s) for a new rule."""
    sh.set_state(chat_id, {**state, "step": "zalo_kw_await_keyword"})
    await zalo.send_text(
        "✍️ Nhập keyword\n\n"
        "- 1 keyword: highland\n"
        "- Nhiều keyword cách nhau dấu phẩy → tất cả map cùng 1 category:\n"
        "  highland, tch, the coffee house, revi\n\n"
        "Bot match khi description giao dịch chứa keyword "
        "(không phân biệt hoa/thường, dấu).\n\n"
        "/cancel để hủy.",
        chat_id,
    )


async def _zalo_kw_handle_keyword_input(text: str, chat_id: str, state: dict):
    """User typed keyword(s). Validate, then show bucket picker."""
    import re as _re
    from datetime import datetime as _dt
    import pytz

    raw = text.strip()
    if not raw:
        await zalo.send_text("⚠️ Keyword rỗng. Thử lại hoặc /cancel để hủy.", chat_id)
        return

    tokens = [t.strip() for t in _re.split(r"[,;]+", raw)]
    keywords = []
    for t in tokens:
        if not t:
            continue
        if len(t) > 60:
            await zalo.send_text(
                f"⚠️ Keyword quá dài (>60 ký tự): {t}\nThử lại.",
                chat_id,
            )
            return
        norm = sh._normalize_for_match(t)
        if norm and norm not in keywords:
            keywords.append(norm)

    if not keywords:
        await zalo.send_text("⚠️ Không có keyword hợp lệ. Thử lại.", chat_id)
        return

    tz = pytz.timezone(TIMEZONE)
    month_key = state.get("month_key") or sh.fmt_month(_dt.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        await zalo.send_text(
            "⚠️ Chưa có category nào. Dùng /manage trên Telegram để tạo category trước, "
            "rồi quay lại /keywords.",
            chat_id,
        )
        sh.set_state(chat_id, {})
        return

    # Show numbered bucket list for selection
    preview = ", ".join(keywords)
    count_label = "" if len(keywords) == 1 else f" ({len(keywords)} keywords)"
    msg = f"🔑 Keyword{count_label}: {preview}\n\nMatch vào category nào?\n\n"
    for i, b in enumerate(buckets, 1):
        msg += f"{i}. {b['name']}\n"
    msg += "\nReply số thứ tự category.\n/cancel để hủy."

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_kw_pick_bucket",
        "pending_keywords": keywords,
        "month_key": month_key,
    })
    await zalo.send_text(msg, chat_id)


async def _zalo_kw_handle_bucket_pick(text: str, chat_id: str, state: dict):
    """User picked a bucket number for the new keyword(s)."""
    from datetime import datetime as _dt
    import pytz

    if not text.strip().isdigit():
        await zalo.send_text("⚠️ Reply số thứ tự category.", chat_id)
        return

    idx = int(text.strip())
    tz = pytz.timezone(TIMEZONE)
    month_key = state.get("month_key") or sh.fmt_month(_dt.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not (1 <= idx <= len(buckets)):
        await zalo.send_text(
            f"⚠️ Số {idx} không hợp lệ. Có {len(buckets)} categories.",
            chat_id,
        )
        return

    bucket = buckets[idx - 1]
    keywords = state.get("pending_keywords") or []
    if not keywords:
        await zalo.send_text("⚠️ Hết phiên. Thử /keywords lại.", chat_id)
        sh.set_state(chat_id, {})
        return

    added = []
    skipped = []
    for kw in keywords:
        if sh.add_keyword_rule(kw, bucket["id"], sub_label=""):
            added.append(kw)
        else:
            skipped.append(kw)

    sections = []
    if added:
        added_block = ", ".join(added)
        sections.append(f"✅ Đã thêm {len(added)} rule → {bucket['name']}:\n  {added_block}")
    if skipped:
        skipped_block = ", ".join(skipped)
        sections.append(f"⚠️ {len(skipped)} rule đã tồn tại:\n  {skipped_block}")

    await zalo.send_text("\n\n".join(sections), chat_id)
    await _zalo_kw_show_list(chat_id)


# ─── Zalo Keywords: Edit keyword flow ─────────────────────────

async def _zalo_kw_handle_edit_keyword(text: str, chat_id: str, state: dict):
    """User typed a new keyword for an existing rule."""
    import re as _re

    raw = text.strip()
    if not raw:
        await zalo.send_text("⚠️ Keyword rỗng. Thử lại hoặc /cancel để hủy.", chat_id)
        return

    if _re.search(r"[,;]", raw):
        await zalo.send_text(
            "⚠️ Chỉ nhận 1 keyword khi sửa.\n"
            "Muốn add nhiều keyword → xóa rule này và dùng add.",
            chat_id,
        )
        return

    if len(raw) > 60:
        await zalo.send_text("⚠️ Keyword quá dài (>60 ký tự). Thử lại.", chat_id)
        return

    new_norm = sh._normalize_for_match(raw)
    if not new_norm:
        await zalo.send_text("⚠️ Keyword không hợp lệ. Thử lại.", chat_id)
        return

    row_num = state.get("selected_row_num")
    if not row_num:
        await zalo.send_text("⚠️ Hết phiên. Thử /keywords lại.", chat_id)
        sh.set_state(chat_id, {})
        return

    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await zalo.send_text("⚠️ Rule không còn tồn tại.", chat_id)
        await _zalo_kw_show_list(chat_id)
        return

    old_keyword = rule["keyword"]
    if new_norm == old_keyword:
        await zalo.send_text("ℹ️ Keyword không đổi.", chat_id)
        await _zalo_kw_show_list(chat_id)
        return

    ok = sh.update_keyword_rule(row_num, keyword=new_norm)
    if ok:
        bucket_name = sh.bucket_label(rule["bucket_id"])
        await zalo.send_text(
            f"✅ Đã đổi: {old_keyword} → {new_norm}\n(category: {bucket_name})",
            chat_id,
        )
    else:
        await zalo.send_text("⚠️ Lỗi khi cập nhật rule. Thử lại.", chat_id)
    await _zalo_kw_show_list(chat_id)


# ─── Zalo Keywords: Change category flow ──────────────────────

async def _zalo_kw_prompt_edit_bucket(chat_id: str, state: dict, rule: dict):
    """Show numbered bucket list so user can pick a new category."""
    from datetime import datetime as _dt
    import pytz

    tz = pytz.timezone(TIMEZONE)
    month_key = state.get("month_key") or sh.fmt_month(_dt.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        await zalo.send_text(
            "⚠️ Chưa có category nào. Dùng /manage trên Telegram.",
            chat_id,
        )
        return

    current_bucket = sh.bucket_label(rule["bucket_id"])
    msg = (
        f"🔑 {rule['keyword']}\n"
        f"Hiện tại: {current_bucket}\n\n"
        f"Đổi sang category nào?\n\n"
    )
    for i, b in enumerate(buckets, 1):
        msg += f"{i}. {b['name']}\n"
    msg += "\nReply số thứ tự category.\n/cancel để hủy."

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_kw_pick_edit_bucket",
        "month_key": month_key,
    })
    await zalo.send_text(msg, chat_id)


async def _zalo_kw_handle_edit_bucket_pick(text: str, chat_id: str, state: dict):
    """User picked a new category number for an existing rule."""
    from datetime import datetime as _dt
    import pytz

    if not text.strip().isdigit():
        await zalo.send_text("⚠️ Reply số thứ tự category.", chat_id)
        return

    idx = int(text.strip())
    tz = pytz.timezone(TIMEZONE)
    month_key = state.get("month_key") or sh.fmt_month(_dt.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not (1 <= idx <= len(buckets)):
        await zalo.send_text(
            f"⚠️ Số {idx} không hợp lệ. Có {len(buckets)} categories.",
            chat_id,
        )
        return

    row_num = state.get("selected_row_num")
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await zalo.send_text("⚠️ Rule không còn tồn tại.", chat_id)
        await _zalo_kw_show_list(chat_id)
        return

    new_bucket = buckets[idx - 1]
    if rule["bucket_id"] == new_bucket["id"]:
        await zalo.send_text("ℹ️ Category không đổi.", chat_id)
        await _zalo_kw_show_list(chat_id)
        return

    ok = sh.update_keyword_rule(row_num, bucket_id=new_bucket["id"])
    if ok:
        old_name = sh.bucket_label(rule["bucket_id"])
        await zalo.send_text(
            f"✅ Đã đổi category cho {rule['keyword']}:\n"
            f"{old_name} → {new_bucket['name']}",
            chat_id,
        )
    else:
        await zalo.send_text("⚠️ Lỗi khi cập nhật rule.", chat_id)
    await _zalo_kw_show_list(chat_id)


# ─── Zalo Manage: text-based interactive flow ─────────────────
# Port of /manage (handlers/manage.py) to Zalo text-only interface.

async def _zalo_mg_show_list(chat_id: str):
    """Show all active buckets as a numbered list + action instructions."""
    from datetime import datetime as _dt
    import pytz

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(_dt.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        # Bootstrap defaults if none exist
        async with sh.bootstrap_lock:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_default_categories(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)

    msg = f"⚙️ Manage Categories — {month_key}\n\n"
    total = 0
    for i, b in enumerate(buckets, 1):
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{i}. {b['name']}   {sh.fmt_amount(alloc)}\n"
            total += alloc
        else:
            msg += f"{i}. {b['name']}   🏷️ tracking\n"
    msg += (
        f"─────────────────────\n"
        f"Total budgeted   {sh.fmt_amount(total)}\n\n"
        "Reply:\n"
        '- Số (VD: \"3\") để sửa/xóa category đó\n'
        '- \"add\" để thêm category mới\n'
        "- /cancel để thoát"
    )

    sh.set_state(chat_id, {"step": "zalo_mg_list", "month_key": month_key})
    await zalo.send_text(msg, chat_id)


async def _zalo_mg_handle_list_reply(text: str, chat_id: str, state: dict):
    """Handle user reply when viewing the category list."""
    text_lower = text.strip().lower()

    if text_lower == "add":
        sh.set_state(chat_id, {**state, "step": "zalo_mg_await_add_name"})
        await zalo.send_text(
            "➕ Add New Category\n\n"
            "Nhập tên category mới:\n"
            "(VD: 🎮 Gaming, ✈️ Travel, 🍕 Food)\n\n"
            "/cancel để hủy.",
            chat_id,
        )
        return

    if text.strip().isdigit():
        idx = int(text.strip())
        month_key = state.get("month_key", "")
        buckets = sh.get_active_buckets(month_key)
        if 1 <= idx <= len(buckets):
            bucket = buckets[idx - 1]
            await _zalo_mg_show_actions(chat_id, state, bucket, idx)
            return
        else:
            await zalo.send_text(
                f"⚠️ Số {idx} không hợp lệ. Có {len(buckets)} categories.",
                chat_id,
            )
            return

    await zalo.send_text(
        '⚠️ Không hiểu. Reply "add" hoặc số thứ tự category.',
        chat_id,
    )


async def _zalo_mg_show_actions(chat_id: str, state: dict, bucket: dict, idx: int):
    """Show the action menu for a selected bucket."""
    month_key = state.get("month_key", "")
    bkt_status = sh.get_bucket_status(bucket["id"], month_key)
    subs = sh.get_sub_categories(bucket["id"])

    if bkt_status["allocated"] > 0:
        pct = sh.calc_pct(bkt_status["spent"], bkt_status["allocated"])
        msg = (
            f"⚙️ {bucket['name']}\n"
            f"Mode: 💰 Budgeted\n"
            f"Allocated: {sh.fmt_amount(bkt_status['allocated'])}\n"
            f"Spent: {sh.fmt_amount(bkt_status['spent'])} ({pct}%)\n"
            f"Sub-categories: {len(subs)} active\n\n"
        )
    else:
        msg = (
            f"⚙️ {bucket['name']}\n"
            f"Mode: 🏷️ Tracking-only\n"
            f"Spent: {sh.fmt_amount(bkt_status['spent'])} tháng này\n"
            f"Sub-categories: {len(subs)} active\n\n"
        )

    msg += (
        "Bạn muốn làm gì?\n\n"
        "Reply:\n"
        '"amount" — Sửa budget amount\n'
        '"rename" — Đổi tên category\n'
        '"subs" — Xem sub-categories\n'
        '"del" — Xóa category\n'
        '"back" — Quay lại danh sách'
    )

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_mg_actions",
        "selected_bucket_id": bucket["id"],
        "selected_idx": idx,
    })
    await zalo.send_text(msg, chat_id)


async def _zalo_mg_handle_action_reply(text: str, chat_id: str, state: dict):
    """Handle action menu reply for a selected bucket."""
    text_lower = text.strip().lower()
    bucket_id = state.get("selected_bucket_id")
    month_key = state.get("month_key", "")

    if text_lower == "amount":
        buckets = sh.get_active_buckets(month_key)
        bucket = next((b for b in buckets if b["id"] == bucket_id), None)
        if not bucket:
            await zalo.send_text("⚠️ Category không còn tồn tại.", chat_id)
            await _zalo_mg_show_list(chat_id)
            return

        current = sh.fmt_amount(bucket.get("allocated", 0)) if bucket.get("allocated", 0) > 0 else "🏷️ tracking-only"
        sh.set_state(chat_id, {**state, "step": "zalo_mg_await_amount"})
        await zalo.send_text(
            f"💰 {bucket['name']} — hiện tại: {current}\n"
            "Nhập số tiền mới (0 = chuyển sang tracking-only):\n\n"
            "/cancel để hủy.",
            chat_id,
        )

    elif text_lower == "rename":
        name = sh.bucket_label(bucket_id)
        sh.set_state(chat_id, {**state, "step": "zalo_mg_await_rename"})
        await zalo.send_text(
            f"✏️ Tên hiện tại: {name}\nNhập tên mới:\n\n/cancel để hủy.",
            chat_id,
        )

    elif text_lower == "subs":
        await _zalo_mg_show_subs(chat_id, state, bucket_id)

    elif text_lower == "del":
        name = sh.bucket_label(bucket_id)
        tx_count = sh.count_bucket_transactions(bucket_id, month_key)
        sh.set_state(chat_id, {**state, "step": "zalo_mg_confirm_del"})
        await zalo.send_text(
            f"⚠️ Xóa {name}?\n\n"
            f"Bucket này có {tx_count} transactions trong tháng.\n"
            "Transactions đã categorize sẽ KHÔNG bị ảnh hưởng.\n\n"
            'Reply "yes" để xác nhận, "no" để hủy.',
            chat_id,
        )

    elif text_lower == "back":
        await _zalo_mg_show_list(chat_id)

    else:
        await zalo.send_text(
            '⚠️ Không hiểu. Reply "amount", "rename", "subs", "del" hoặc "back".',
            chat_id,
        )


async def _zalo_mg_handle_rename(text: str, chat_id: str, state: dict):
    """Handle freetext input for new bucket name."""
    new_name = text.strip()
    if not new_name:
        await zalo.send_text("⚠️ Tên không được để trống. Thử lại:", chat_id)
        return

    bucket_id = state.get("selected_bucket_id")
    month_key = state.get("month_key", "")
    old_name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"name": new_name})
    await zalo.send_text(f"✅ Renamed: {old_name} → {new_name}", chat_id)
    await _zalo_mg_show_list(chat_id)


async def _zalo_mg_handle_amount(text: str, chat_id: str, state: dict):
    """Handle freetext input for new allocation amount."""
    try:
        digits = "".join(c for c in text if c.isdigit())
        amount = int(digits) if digits else -1
        assert amount >= 0
    except Exception:
        await zalo.send_text("⚠️ Số tiền không hợp lệ. Thử lại (VD: 3000000 hoặc 0).", chat_id)
        return

    bucket_id = state.get("selected_bucket_id")
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"allocated": amount})
    if amount > 0:
        await zalo.send_text(f"✅ Updated: {name} → {sh.fmt_amount(amount)}", chat_id)
    else:
        await zalo.send_text(f"✅ Updated: {name} → 🏷️ tracking-only", chat_id)
    await _zalo_mg_show_list(chat_id)


async def _zalo_mg_handle_confirm_del(text: str, chat_id: str, state: dict):
    """Handle delete confirmation reply."""
    text_lower = text.strip().lower()
    bucket_id = state.get("selected_bucket_id")
    month_key = state.get("month_key", "")

    if text_lower in ("yes", "y", "co", "có"):
        name = sh.bucket_label(bucket_id)
        sh.soft_delete_bucket(month_key, bucket_id)
        await zalo.send_text(f"🗑️ Deleted: {name}", chat_id)
        await _zalo_mg_show_list(chat_id)

    elif text_lower in ("no", "n", "khong", "không"):
        await zalo.send_text("← Đã hủy xóa.", chat_id)
        await _zalo_mg_show_list(chat_id)

    else:
        await zalo.send_text('⚠️ Reply "yes" để xóa, "no" để hủy.', chat_id)


async def _zalo_mg_handle_add_name(text: str, chat_id: str, state: dict):
    """Handle freetext input for new category name."""
    import unicodedata
    import re

    name = text.strip()
    if not name:
        await zalo.send_text("⚠️ Tên không được để trống. Thử lại:", chat_id)
        return

    # Generate a slug-style ID from the name
    nid = unicodedata.normalize("NFD", name.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)  # strip diacritics
    nid = re.sub(r"[^\w\s]", "", nid)            # strip emoji/symbols
    nid = re.sub(r"\s+", "_", nid.strip())
    nid = re.sub(r"[^a-z0-9_]", "", nid)
    if not nid:
        nid = "custom"

    month_key = state.get("month_key", "")
    existing = sh.get_active_buckets(month_key, force_refresh=True)
    if any(b["id"] == nid for b in existing):
        await zalo.send_text(
            f"⚠️ Category {name} đã tồn tại rồi!\n"
            "Nhập tên khác hoặc /cancel để hủy.",
            chat_id,
        )
        return

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_mg_await_add_amount",
        "new_cat_name": name,
        "new_cat_id": nid,
    })
    await zalo.send_text(
        f"💰 {name}\n\n"
        "Nhập budget amount (VD: 2000000)\n"
        '- Nhập 0 hoặc "track" để tracking-only\n\n'
        "/cancel để hủy.",
        chat_id,
    )


async def _zalo_mg_handle_add_amount(text: str, chat_id: str, state: dict):
    """Handle freetext input for new category amount."""
    text_lower = text.strip().lower()

    if text_lower == "track":
        amount = 0
    else:
        try:
            digits = "".join(c for c in text if c.isdigit())
            amount = int(digits) if digits else -1
            assert amount >= 0
        except Exception:
            await zalo.send_text(
                '⚠️ Số tiền không hợp lệ. Thử lại (VD: 2000000 hoặc "track").',
                chat_id,
            )
            return

    month_key = state.get("month_key", "")
    name = state["new_cat_name"]
    nid = state["new_cat_id"]

    new_bucket = {
        "id": nid,
        "name": name,
        "allocated": amount,
        "daily_cap": None,
    }
    sh.write_budget_row(month_key, new_bucket)
    sh.invalidate_buckets_cache()

    if amount > 0:
        await zalo.send_text(f"✅ Đã thêm: {name} — {sh.fmt_amount(amount)}", chat_id)
    else:
        await zalo.send_text(f"✅ Đã thêm: {name} — 🏷️ tracking-only", chat_id)
    await _zalo_mg_show_list(chat_id)


# ─── Zalo Manage: Sub-categories ──────────────────────────────

async def _zalo_mg_show_subs(chat_id: str, state: dict, bucket_id: str):
    """Show all active sub-categories for a bucket as numbered list."""
    name = sh.bucket_label(bucket_id)
    subs = sh.get_sub_categories(bucket_id)

    if not subs:
        sh.set_state(chat_id, {**state, "step": "zalo_mg_list"})
        await zalo.send_text(
            f"📂 {name} — no sub-categories yet.\n"
            "They'll be created automatically when you categorize transactions.\n\n"
            "Reply số thứ tự category khác hoặc /cancel để thoát.",
            chat_id,
        )
        return

    msg = f"📂 Sub-categories of {name}\n\n"
    for i, s in enumerate(subs, 1):
        msg += f"{i}. {s['label']}\n"
    msg += (
        "\nReply:\n"
        '- Số để sửa/xóa sub-category\n'
        '"back" — quay lại category list\n'
        "/cancel để thoát"
    )

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_mg_subs",
        "selected_bucket_id": bucket_id,
    })
    await zalo.send_text(msg, chat_id)


async def _zalo_mg_handle_sub_reply(text: str, chat_id: str, state: dict):
    """Handle user reply when viewing sub-categories."""
    text_lower = text.strip().lower()
    bucket_id = state.get("selected_bucket_id")

    if text_lower == "back":
        await _zalo_mg_show_list(chat_id)
        return

    if text.strip().isdigit():
        idx = int(text.strip())
        subs = sh.get_sub_categories(bucket_id)
        if 1 <= idx <= len(subs):
            sub = subs[idx - 1]
            name = sh.bucket_label(bucket_id)
            sh.set_state(chat_id, {
                **state,
                "step": "zalo_mg_sub_actions",
                "selected_sub_key": sub["key"],
            })
            await zalo.send_text(
                f"⚙️ {sub['label']}\n(sub of {name})\n\n"
                "Reply:\n"
                '"rename" — Đổi tên\n'
                '"del" — Xóa sub-category\n'
                '"back" — Quay lại danh sách subs',
                chat_id,
            )
            return
        else:
            await zalo.send_text(
                f"⚠️ Số {idx} không hợp lệ. Có {len(subs)} sub-categories.",
                chat_id,
            )
            return

    await zalo.send_text('⚠️ Reply số thứ tự hoặc "back".', chat_id)


async def _zalo_mg_handle_sub_action(text: str, chat_id: str, state: dict):
    """Handle action for a selected sub-category."""
    text_lower = text.strip().lower()
    bucket_id = state.get("selected_bucket_id")
    sub_key = state.get("selected_sub_key")

    if text_lower == "rename":
        sub_label = sh.get_sub_label(bucket_id, sub_key)
        sh.set_state(chat_id, {**state, "step": "zalo_mg_await_sub_rename"})
        await zalo.send_text(
            f"✏️ Tên hiện tại: {sub_label}\nNhập tên mới:\n\n/cancel để hủy.",
            chat_id,
        )

    elif text_lower == "del":
        sub_label = sh.get_sub_label(bucket_id, sub_key)
        sh.set_state(chat_id, {**state, "step": "zalo_mg_confirm_sub_del"})
        await zalo.send_text(
            f"⚠️ Xóa sub-category: {sub_label}?\n\n"
            'Reply "yes" để xác nhận, "no" để hủy.',
            chat_id,
        )

    elif text_lower == "back":
        await _zalo_mg_show_subs(chat_id, state, bucket_id)

    else:
        await zalo.send_text(
            '⚠️ Reply "rename", "del" hoặc "back".',
            chat_id,
        )


async def _zalo_mg_handle_sub_rename(text: str, chat_id: str, state: dict):
    """Handle freetext input for new sub-category name."""
    new_name = text.strip()
    if not new_name:
        await zalo.send_text("⚠️ Tên không được để trống. Thử lại:", chat_id)
        return

    bucket_id = state.get("selected_bucket_id")
    sub_key = state.get("selected_sub_key")
    old_label = sh.get_sub_label(bucket_id, sub_key)

    sh.update_sub_category(bucket_id, sub_key, new_name)
    await zalo.send_text(f"✅ Renamed: {old_label} → {new_name}", chat_id)
    await _zalo_mg_show_subs(chat_id, state, bucket_id)


async def _zalo_mg_handle_confirm_sub_del(text: str, chat_id: str, state: dict):
    """Handle delete confirmation for sub-category."""
    text_lower = text.strip().lower()
    bucket_id = state.get("selected_bucket_id")
    sub_key = state.get("selected_sub_key")

    if text_lower in ("yes", "y", "co", "có"):
        sub_label = sh.get_sub_label(bucket_id, sub_key)
        sh.soft_delete_sub_category(bucket_id, sub_key)
        await zalo.send_text(f"🗑️ Deleted: {sub_label}", chat_id)
        await _zalo_mg_show_subs(chat_id, state, bucket_id)

    elif text_lower in ("no", "n", "khong", "không"):
        await zalo.send_text("← Đã hủy xóa.", chat_id)
        await _zalo_mg_show_subs(chat_id, state, bucket_id)

    else:
        await zalo.send_text('⚠️ Reply "yes" để xóa, "no" để hủy.', chat_id)


# ─── Zalo Allocate: text-based budget allocation ──────────────
# Port of /allocate edit mode (handlers/allocation.py) to Zalo.
# Only supports edit mode (buckets already exist). First-time setup
# is complex (wizard) and is best done on Telegram.

async def _zalo_al_show_list(chat_id: str):
    """Show budget summary as numbered list + edit instructions."""
    from datetime import datetime as _dt
    import pytz

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(_dt.now(tz))
    buckets = sh.get_active_buckets(month_key, force_refresh=True)

    if not buckets:
        await zalo.send_text(
            f"💰 Budget — {month_key}\n\n"
            "Chưa có category nào.\n"
            "Dùng /manage để tạo categories trước, rồi quay lại /allocate.",
            chat_id,
        )
        return

    msg = f"💰 Budget — {month_key}\n\n"
    total = 0
    for i, b in enumerate(buckets, 1):
        alloc = b.get("allocated", 0) or 0
        if alloc > 0:
            msg += f"{i}. {b['name']}   {sh.fmt_amount(alloc)}\n"
            total += alloc
        else:
            msg += f"{i}. {b['name']}   🏷️ tracking\n"
    msg += (
        f"─────────────────────\n"
        f"Total: {sh.fmt_amount(total)}\n\n"
        "Reply:\n"
        '- Số (VD: "2") để sửa limit cho bucket đó\n'
        "- /cancel để thoát"
    )

    sh.set_state(chat_id, {"step": "zalo_al_list", "month_key": month_key})
    await zalo.send_text(msg, chat_id)


async def _zalo_al_handle_list_reply(text: str, chat_id: str, state: dict):
    """Handle user reply when viewing the budget list."""
    if not text.strip().isdigit():
        await zalo.send_text("⚠️ Reply số thứ tự bucket.", chat_id)
        return

    idx = int(text.strip())
    month_key = state.get("month_key", "")
    buckets = sh.get_active_buckets(month_key)

    if not (1 <= idx <= len(buckets)):
        await zalo.send_text(
            f"⚠️ Số {idx} không hợp lệ. Có {len(buckets)} buckets.",
            chat_id,
        )
        return

    bucket = buckets[idx - 1]
    current_alloc = bucket.get("allocated", 0) or 0
    current = sh.fmt_amount(current_alloc) if current_alloc > 0 else "🏷️ tracking-only"

    sh.set_state(chat_id, {
        **state,
        "step": "zalo_al_await_amount",
        "edit_bucket_id": bucket["id"],
        "edit_bucket_name": bucket["name"],
    })
    await zalo.send_text(
        f"✏️ {bucket['name']} (hiện: {current})\n\n"
        f"Nhập limit mới cho {month_key}:\n"
        "(số, vd 3000000, hoặc 0 để track-only)\n\n"
        "/cancel để hủy.",
        chat_id,
    )


async def _zalo_al_handle_amount(text: str, chat_id: str, state: dict):
    """Handle freetext input for new bucket allocation amount."""
    raw = "".join(c for c in text if c.isdigit())
    if not raw:
        await zalo.send_text(
            "⚠️ Số không hợp lệ. Thử lại (vd 3000000 hoặc 0).",
            chat_id,
        )
        return
    try:
        amount = int(raw)
    except ValueError:
        await zalo.send_text("⚠️ Số không hợp lệ.", chat_id)
        return
    if amount < 0:
        await zalo.send_text("⚠️ Số phải ≥ 0. 0 = track-only.", chat_id)
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    bucket_name = state.get("edit_bucket_name", bucket_id)

    if not month_key or not bucket_id:
        await zalo.send_text("⚠️ State đã hết hạn. Chạy /allocate lại.", chat_id)
        sh.set_state(chat_id, {})
        return

    buckets = sh.get_active_buckets(month_key)
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if not bucket:
        await zalo.send_text(f"⚠️ Bucket {bucket_name} đã biến mất.", chat_id)
        sh.set_state(chat_id, {})
        return

    bucket["allocated"] = amount
    sh.write_budget_row(month_key, bucket)
    sh.invalidate_buckets_cache()

    suffix = " (track-only)" if amount == 0 else ""
    await zalo.send_text(
        f"✅ Đã update {bucket_name} → {sh.fmt_amount(amount)}{suffix}",
        chat_id,
    )
    await _zalo_al_show_list(chat_id)


# ─── Zalo Tx Picker: categorize uncategorized outgoing expense ─

def _format_zalo_bucket_options(buckets: list[dict]) -> str:
    return "\n".join(f"{i + 1}. {b['name']}" for i, b in enumerate(buckets))


async def _zalo_handle_tx_pick(text: str, chat_id: str, state: dict):
    """Handle numbered reply to the category picker menu.

    Valid pick → _zalo_finalize_tx. Invalid / out-of-range → reprompt.
    """
    buckets = state.get("buckets") or []

    if not text.strip().isdigit():
        await zalo.send_text(
            f"⚠️ Reply số thứ tự (1–{len(buckets)}).\n\n{_format_zalo_bucket_options(buckets)}",
            chat_id,
        )
        return

    idx = int(text.strip())
    if not (1 <= idx <= len(buckets)):
        await zalo.send_text(
            f"⚠️ Số {idx} không hợp lệ. Có {len(buckets)} mục.\n\n{_format_zalo_bucket_options(buckets)}",
            chat_id,
        )
        return

    bucket_id = buckets[idx - 1]["id"]
    await _zalo_finalize_tx(chat_id, state, bucket_id)


async def _zalo_finalize_tx(chat_id: str, state: dict, bucket_id: str):
    """Finalize the pending tx, apply ledger, send summary, promote queue if any."""
    from handlers.transaction import _apply_ledger_for_row
    from handlers.zalo_render import render_zalo_logged_summary

    row_num = state["row_num"]
    amount = state.get("amount", 0)
    currency = state.get("currency", "VND")
    tx_direction = state.get("tx_direction", "out")
    queue = state.get("queue") if isinstance(state.get("queue"), list) else []

    sh.finalize_transaction(row_num, bucket_id, "")
    try:
        _apply_ledger_for_row(row_num)
    except Exception as e:
        print(f"[zalo-picker] ledger write error row={row_num}: {e}")

    # Build summary using the actual tx date (not now(), not first-of-month).
    # Daily-bucket summaries call get_daily_status(tx_date) — wrong day = wrong stats.
    from datetime import datetime as _dt
    import pytz as _pytz
    tx_date_str = state.get("tx_date", "")
    try:
        tx_date = _dt.fromisoformat(tx_date_str) if tx_date_str else _dt.now(_pytz.timezone(TIMEZONE))
    except (ValueError, TypeError):
        tx_date = _dt.now(_pytz.timezone(TIMEZONE))

    summary = render_zalo_logged_summary(
        row_num=row_num,
        bucket_id=bucket_id,
        sub_label="",
        amount=amount,
        tx_date=tx_date,
        tx_direction=tx_direction,
        currency=currency,
    )

    if queue:
        # Promote next queued item
        next_item = queue[0]
        remaining_queue = queue[1:]
        sh.set_state(chat_id, {
            "step": "zalo_tx_pick",
            **next_item,
            "queue": remaining_queue,
        })
        next_buckets = next_item.get("buckets") or []
        next_menu = (
            f"-{sh.fmt_amount(next_item.get('amount', 0), next_item.get('currency', 'VND'))}\n"
            f"{next_item.get('description', '')}\n\n"
            f"Khoản này thuộc mục nào?\n\n{_format_zalo_bucket_options(next_buckets)}"
        )
        await zalo.send_text(summary + "\n\n" + next_menu, chat_id)
    else:
        sh.clear_state(chat_id)
        await zalo.send_text(summary, chat_id)

