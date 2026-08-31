"""
main.py — FastAPI entry point
Receives SePay webhooks, Telegram updates, and Zalo Bot events.
"""
import hmac as hmac_mod
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
import asyncio

ROOT = Path(__file__).resolve().parent
DASHBOARD_HTML = ROOT / "docs" / "dashboard.html"
DASHBOARD_MD = ROOT / "docs" / "dashboard.md"


from config import (
    CHAT_ID,
    CRON_SECRET,
    EMAIL_SECRET,
    SEPAY_SECRET,
    TELEGRAM_WEBHOOK_SECRET,
    ZALO_ALLOW_UNVERIFIED_WEBHOOK,
    ZALO_CHAT_ID,
    ZALO_ENABLED,
    ZALO_SECRET_TOKEN,
    TIMEZONE,
)
from utils import parse_money as _utils_parse_money, parse_budget_amount
import messenger
import sheets as sh
import telegram_api as tg
from handlers.sepay        import handle_sepay_webhook
from handlers.email_parser import parse_email
from handlers.transaction import handle_parent_selected, handle_sub_selected, handle_freetext_sub, handle_recategorize, handle_inline_new_cat_name, handle_learn_rule
from handlers.allocation  import (
    start_monthly_allocation, handle_alloc_callback,
    handle_alloc_amount_input, handle_new_bucket_name, handle_new_bucket_amount,
    handle_edit_bucket_amount,
)
from handlers.reports     import send_today_status, send_daily_recap, handle_daily_excuse
from handlers.manage      import (
    start_manage, handle_manage_callback,
    handle_manage_amount, handle_manage_daily_cap,
    handle_manage_rename, handle_sub_rename,
    handle_add_cat_name, handle_add_cat_amount,
)
from handlers.keywords    import (
    start_keywords, handle_keywords_callback,
    handle_keyword_input, handle_edit_keyword_input,
)
from handlers.accounts    import (
    handle_accounts_callback, handle_assign_callback,
    handle_new_account_name, handle_new_account_balance,
    handle_credit_limit, handle_credit_outstanding,
    handle_credit_statement, handle_credit_due,
    parse_billing_day, _credit_statement_prompt, _credit_due_prompt,
    cmd_accounts,
)
from handlers.report      import cmd_report, handle_report_callback
from handlers.lang        import cmd_lang, handle_lang_callback
from handlers.zalo_render import render_zalo_logged_summary
from handlers import zalo_queue as zq

# SaaS layer (MyMoneyWent additions) — optional, graceful degradation
try:
    from core import db
    from core.logging import configure_logging, get_logger
    from core.observability import init_sentry, request_id_middleware
    from markets.vn.capture.sepay_webhook import handle_sepay_webhook as handle_sepay_v2
    _SAAS_AVAILABLE = True
except ImportError:
    _SAAS_AVAILABLE = False

_PROD_ENVS = {"prod", "production", "staging"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown wiring."""
    app_env = os.environ.get("APP_ENV", "dev")

    if _SAAS_AVAILABLE:
        configure_logging(env=app_env)
        log = get_logger("main", component="startup")
        init_sentry(os.environ.get("SENTRY_DSN"), environment=app_env)
        dsn = os.environ.get("DATABASE_URL", "")
        if dsn:
            await db.create_pool(dsn)
            log.info("startup.db_pool_ready")
        elif app_env.lower() in _PROD_ENVS:
            raise RuntimeError("DATABASE_URL is required in prod/staging")
        else:
            log.warning("startup.db_pool_skipped", reason="DATABASE_URL not set (legacy mode)")
    else:
        log = None

    port = os.environ.get("PORT", 8000)
    print(f"[startup] running on port {port}")

    # Security posture nudge
    _unset = [name for name, val in (
        ("SEPAY_SECRET", SEPAY_SECRET),
        ("TELEGRAM_WEBHOOK_SECRET", TELEGRAM_WEBHOOK_SECRET),
        ("CRON_SECRET", CRON_SECRET),
        ("EMAIL_SECRET", EMAIL_SECRET),
    ) if not val]
    if _unset:
        print(f"[startup] ⚠️ SECURITY: unset secrets: {', '.join(_unset)} — "
              f"the matching endpoints accept unauthenticated requests. "
              f"See .env.example for how to enable them.")

    try:
        await tg.set_my_commands()
    except Exception as exc:
        print(f"[startup] set_my_commands failed (no internet?): {exc}")

    if _SAAS_AVAILABLE and log:
        log.info("startup.ready", port=port)

    yield

    if _SAAS_AVAILABLE:
        await db.close_pool()
        if log:
            log.info("shutdown.db_pool_closed")


app = FastAPI(title="Financial Tracking Bot", lifespan=lifespan)
if _SAAS_AVAILABLE:
    app.middleware("http")(request_id_middleware)


# ─── Webhook endpoint ─────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    """
    Single endpoint handling both SePay and Telegram payloads.
    Returns 200 immediately — processing runs in background.

    Security:
      - Telegram updates ("update_id" in body): when TELEGRAM_WEBHOOK_SECRET is
        set, the X-Telegram-Bot-Api-Secret-Token header must match (register
        the webhook with the same secret_token — see .env.example). Unset →
        legacy open behavior, warned at startup.
      - SePay payloads: validated inside handle_sepay_webhook via SEPAY_SECRET.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    if "update_id" in body and TELEGRAM_WEBHOOK_SECRET:
        tg_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac_mod.compare_digest(tg_secret, TELEGRAM_WEBHOOK_SECRET):
            print("[webhook] rejected: invalid Telegram webhook secret")
            return JSONResponse({"ok": True})  # 200 to avoid Telegram retries

    bg.add_task(_process, body)
    return JSONResponse({"ok": True})          # ← 200 right away, no 302


# ─── Email webhook (Google Apps Script → bot) ────────────────
@app.post("/webhook/email")
async def webhook_email(request: Request, bg: BackgroundTasks):
    """
    Nhận email payload từ Google Apps Script.
    Payload: { secret, from, subject, body, date }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    # Validate secret
    if EMAIL_SECRET and body.get("secret") != EMAIL_SECRET:
        print(f"[email webhook] rejected: invalid secret")
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    bg.add_task(_process_email, body)
    return JSONResponse({"ok": True})


async def _process_email(payload: dict):
    try:
        parsed = parse_email(
            from_addr=payload.get("from", ""),
            subject=payload.get("subject", ""),
            body=payload.get("body", ""),
            date=payload.get("date", ""),
        )
        if parsed is None:
            print(f"[email] skipped — not a transaction email or unknown format")
            return
        print(f"[email] parsed: {parsed.get('_source')} amount={parsed.get('transferAmount')} type={parsed.get('transferType')}")
        await handle_sepay_webhook(parsed)
    except Exception as e:
        import traceback
        print("ERROR [email]:", traceback.format_exc())


# ─── Zalo Bot Platform webhook ────────────────────────────────
def _verify_zalo_webhook(headers: dict) -> bool:
    """Verify Zalo Bot webhook via X-Bot-Api-Secret-Token header.

    In production, ZALO_SECRET_TOKEN must be set. Local/dev tests can explicitly
    opt into unsigned webhooks with ZALO_ALLOW_UNVERIFIED_WEBHOOK=true.
    """
    if not ZALO_SECRET_TOKEN:
        return ZALO_ALLOW_UNVERIFIED_WEBHOOK
    header_token = headers.get("x-bot-api-secret-token", "")
    return hmac_mod.compare_digest(header_token, ZALO_SECRET_TOKEN)


@app.post("/zalo/webhook")
async def webhook_zalo(request: Request, bg: BackgroundTasks):
    """Receive Zalo Bot Platform webhook updates.

    Docs: https://bot.zapps.me/docs/webhook/
    Body format mirrors Telegram: {message: {from, chat, text, ...}}
    """
    if not ZALO_ENABLED:
        return JSONResponse({"ok": True})
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not _verify_zalo_webhook(headers):
        print("[zalo] webhook rejected: invalid secret token")
        return JSONResponse({"ok": False}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True})
    update = _extract_zalo_update(body)

    # ── callback_query (inline keyboard button tap) ──
    cb = update.get("callback_query")
    if isinstance(cb, dict) and cb.get("data"):
        bg.add_task(_handle_zalo_callback, cb)
        return JSONResponse({"ok": True})

    # ── text message ──
    message = update.get("message")
    if (
        update.get("event_name") == "message.text.received"
        and isinstance(message, dict)
        and message.get("text")
    ):
        bg.add_task(_handle_zalo_text, update)
    return JSONResponse({"ok": True})


async def _handle_zalo_text(body: dict):
    """Handle incoming text messages from Zalo Bot Platform.

    Supports: /start, /keywords, numeric category reply, and help fallback.
    State is stored in Google Sheets with 'zalo:<chat_id>' key.

    Normalized body format:
        {"event_name": "message.text.received", "message": {"chat": {"id": 123}, "text": "..."}}
    """
    message = body.get("message", {})
    chat_id = str(message.get("chat", {}).get("id") or "")
    text = str(message.get("text") or "").strip()
    if not chat_id or not text:
        return

    zalo_state_key = f"zalo:{chat_id}"

    # ── Admin-only access ──
    # Only the configured admin (ZALO_CHAT_ID) can interact with this bot.
    # Other users get a polite message. If ZALO_CHAT_ID is not set,
    # log the sender's chat_id so the admin can configure it.
    if not ZALO_CHAT_ID:
        print(f"[zalo] ZALO_CHAT_ID not set. Sender chat_id: {chat_id}")
        await messenger.send_text(
            "Bot chưa được cấu hình. Vui lòng liên hệ admin.",
            channel="zalo",
            recipient_id=chat_id,
        )
        return
    if chat_id != ZALO_CHAT_ID:
        print(f"[zalo] rejected non-admin: {chat_id}")
        await messenger.send_text(
            "Bot này chỉ dành cho admin. Bạn không có quyền truy cập.",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    try:
        # /start + /help — command list
        if text.lower() in ("/start", "/help"):
            # Park an abandoned picker before wiping state so its tx aren't lost.
            prev = sh.get_state(zalo_state_key) or {}
            zq.park_active_picker(chat_id, prev)
            sh.clear_state(zalo_state_key)
            msg = (
                "Chào bạn! Đây là Financial Tracking Bot.\n\n"
                "Bot tự động nhận giao dịch qua SePay/email và gửi thông báo tới đây.\n"
                "Khi nhận được giao dịch, bạn chọn category bằng cách reply số.\n\n"
                "Lệnh hỗ trợ:\n"
                "- /today — Chi tiêu hôm nay\n"
                "- /report — Báo cáo chi tiêu\n"
                "- /accounts — Xem tài khoản\n"
                "- /transfer — Ghi nhận chuyển tiền nội bộ\n"
                "- /cc pay — Ghi nhận trả thẻ tín dụng\n"
                "- /manage — Quản lý category\n"
                "- /allocate — Đặt budget\n"
                "- /keywords — Quản lý keyword auto-category\n"
                "- /recat — Phân loại lại giao dịch\n"
                "- /pending — Phân loại giao dịch đang chờ\n"
                "- /lang — Đổi ngôn ngữ vi/en\n"
                "- /cancel — Hủy thao tác\n\n"
                "Mẹo: nhập số tiền có thể viết tắt — 500k, 3tr, 3tr5, 1m2."
            )
            parked = zq.parked_count(chat_id)
            if parked:
                msg += f"\n\nCòn {parked} giao dịch chờ phân loại — gửi /pending."
            await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)
            return

        cmd = text.lower().split()[0] if text.startswith("/") else ""

        # Clear pending state when user starts a new slash command (mirrors
        # Telegram fix). Plain "setup"/"skip" onboarding replies are not slash
        # commands, so they remain continuations of the onboarding prompt.
        # An abandoned category picker is PARKED first (Zalo pickers die with
        # their state — numbers stop working once state changes), so the tx
        # stay reachable via /pending instead of silently dropping out of flow.
        if cmd and cmd not in ("/cancel",):
            state = sh.get_state(zalo_state_key) or {}
            step = state.get("step", "")
            # Don't clear if it's a non-command (cmd="") or cancel (has its own clear)
            if step:
                zq.park_active_picker(chat_id, state)
                sh.clear_state(zalo_state_key)

        # Zalo text equivalents for Telegram account onboarding callbacks.
        # Prompt format comes from handlers.accounts.prompt_zalo_new_account.
        onboarding_parts = text.strip().split()
        onboarding_action = onboarding_parts[0].lower().lstrip("/") if onboarding_parts else ""
        if onboarding_action in ("setup", "skip") and len(onboarding_parts) >= 2:
            await _zalo_handle_account_setup_action(
                chat_id,
                onboarding_action,
                onboarding_parts[1].strip(),
                zalo_state_key,
            )
            return

        # /today command
        if cmd == "/today":
            await _zalo_cmd_today(chat_id)
            return

        # /report command
        if cmd == "/report":
            await _zalo_cmd_report(chat_id, text, zalo_state_key)
            return

        # /accounts command
        if cmd == "/accounts":
            await _zalo_cmd_accounts(chat_id, text, zalo_state_key)
            return

        # /transfer command
        if cmd == "/transfer":
            await _zalo_cmd_transfer(chat_id, text)
            return

        # /cc pay command
        if cmd == "/cc":
            await _zalo_cmd_cc_pay(chat_id, text)
            return

        # /recat command
        if cmd == "/recat":
            await _zalo_cmd_recat(chat_id, text, zalo_state_key)
            return

        # /pending command — drain transactions parked while user was mid-flow
        if cmd == "/pending":
            await _zalo_cmd_pending(chat_id, zalo_state_key)
            return

        # /manage command
        if cmd == "/manage":
            await _zalo_cmd_manage(chat_id, zalo_state_key)
            return

        # /allocate command
        if cmd == "/allocate":
            await _zalo_cmd_allocate(chat_id, zalo_state_key)
            return

        # /keywords command
        if cmd == "/keywords":
            await _zalo_kw_show_list(chat_id, zalo_state_key)
            return

            return

        # /lang command
        if cmd == "/lang":
            await _zalo_cmd_lang(chat_id, text)
            return

        # /cancel — reset any pending state (an active picker is parked so
        # its transactions stay reachable via /pending)
        if cmd == "/cancel":
            state = sh.get_state(zalo_state_key) or {}
            zq.park_active_picker(chat_id, state)
            sh.clear_state(zalo_state_key)
            msg = "Đã hủy. Gửi /help để xem danh sách lệnh."
            parked = zq.parked_count(chat_id)
            if parked:
                msg += f"\n\nCòn {parked} giao dịch chờ phân loại — gửi /pending."
            await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)
            return

        # Check current state for multi-step flows
        state = sh.get_state(zalo_state_key)
        step = state.get("step") if state else None

        # ── Manage states ──
        if step == "zalo_manage":
            await _zalo_manage_handle_menu(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_bucket_menu":
            await _zalo_manage_handle_bucket_menu(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_edit_amount":
            await _zalo_manage_handle_edit_amount(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_edit_daily_cap":
            await _zalo_manage_handle_edit_daily_cap(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_rename":
            await _zalo_manage_handle_rename(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_confirm_delete":
            await _zalo_manage_handle_confirm_delete(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_add_name":
            await _zalo_manage_handle_add_name(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_add_amount":
            await _zalo_manage_handle_add_amount(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_subs":
            await _zalo_manage_handle_subs(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_sub_menu":
            await _zalo_manage_handle_sub_menu(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_manage_sub_rename":
            await _zalo_manage_handle_sub_rename(chat_id, text, state, zalo_state_key)
            return

        # ── Allocate states ──
        if step == "zalo_allocate_menu":
            await _zalo_allocate_handle_menu(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_allocate_edit_amount":
            await _zalo_allocate_handle_edit_amount(chat_id, text, state, zalo_state_key)
            return

        # ── Accounts states ──
        if step == "zalo_accounts_name":
            await _zalo_accounts_handle_name(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_accounts_type":
            await _zalo_accounts_handle_type(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_accounts_credit_limit":
            await _zalo_accounts_handle_credit_limit(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_accounts_credit_outstanding":
            await _zalo_accounts_handle_credit_outstanding(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_accounts_credit_statement":
            await _zalo_accounts_handle_credit_statement(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_accounts_credit_due":
            await _zalo_accounts_handle_credit_due(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_accounts_assign_confirm":
            await _zalo_accounts_handle_assign_confirm(chat_id, text, state, zalo_state_key)
            return

        # ── Report states ──
        if step == "zalo_report_menu":
            await _zalo_report_handle_menu(chat_id, text, state, zalo_state_key)
            return

        # ── Recat picker (no-arg /recat) ──
        if step == "zalo_recat_pick":
            await _zalo_recat_handle_pick(chat_id, text, state, zalo_state_key)
            return

        # ── Keyword management states ──
        if step == "zalo_keywords":
            await _zalo_kw_handle_menu(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_kw_add_keyword":
            await _zalo_kw_handle_add_keyword(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_kw_add_pick_cat":
            await _zalo_kw_handle_add_pick_cat(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_kw_edit_menu":
            await _zalo_kw_handle_edit_menu(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_kw_edit_keyword":
            await _zalo_kw_handle_edit_keyword(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_kw_edit_cat":
            await _zalo_kw_handle_edit_cat(chat_id, text, state, zalo_state_key)
            return
        if step == "zalo_kw_confirm_delete":
            await _zalo_kw_handle_confirm_delete(chat_id, text, state, zalo_state_key)
            return

            return

        # ── Keyword learn suggestion (from manual category pick) ──
        if step == "await_zalo_kw_learn":
            await _zalo_handle_kw_learn(chat_id, text, state, zalo_state_key)
            return

        # ── Daily excuse (end-of-day recap overspend note) ──
        if step == "await_zalo_daily_excuse":
            overspent = state.get("overspent", 0)
            sh.clear_state(zalo_state_key)
            await _zalo_send(
                chat_id,
                f"Đã ghi nhận. Vượt {sh.fmt_amount(overspent)} hôm nay.\n"
                "Mai là một ngày mới."
            )
            return

        # ── Transaction category selection ──
        if step == "await_zalo_parent":
            if text.isdigit():
                await _handle_zalo_category_reply(
                    chat_id, int(text), state, zalo_state_key
                )
                return
            else:
                await messenger.send_text(
                    "Số không hợp lệ. Vui lòng reply bằng số tương ứng với category.",
                    channel="zalo",
                    recipient_id=chat_id,
                )
                return
        if step == "await_zalo_sub":
            await _handle_zalo_sub_reply(chat_id, text, state, zalo_state_key)
            return
        if step == "await_zalo_freetext_sub":
            await _handle_zalo_freetext_sub(chat_id, text, state, zalo_state_key)
            return
        if step == "await_zalo_new_cat_name":
            await _handle_zalo_new_cat_name(chat_id, text, state, zalo_state_key)
            return

        # Default help
        await messenger.send_text(
            "Gửi /help để xem danh sách lệnh.",
            channel="zalo",
            recipient_id=chat_id,
        )
    except Exception as e:
        import traceback
        print(f"ERROR [zalo text]: {traceback.format_exc()}")


async def _handle_zalo_callback(cb: dict):
    """Handle Zalo inline keyboard callback_query — mirrors Telegram _handle_callback.

    When Zalo Bot API supports inline_keyboard, button taps arrive as
    callback_query events with the same callback_data format as Telegram.
    We reuse the existing Telegram callback handlers directly.

    Expected cb format: {"id": "...", "data": "p_5_daily", "message": {"chat": {"id": "..."}, "message_id": "..."}}
    """
    try:
        data = cb.get("data", "")
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
        message_id = cb.get("message", {}).get("message_id")

        # Admin check
        if ZALO_CHAT_ID and chat_id != ZALO_CHAT_ID:
            print(f"[zalo] callback rejected non-admin: {chat_id}")
            return

        # Answer callback (best-effort, ignore errors)
        try:
            await _zalo_answer_callback(cb.get("id", ""))
        except Exception:
            pass

        parts = data.split("_")
        prefix = parts[0]

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
        elif prefix == "lang":
            await handle_lang_callback(parts, message_id)
        elif prefix == "lr":
            await handle_learn_rule(parts, message_id)
    except Exception:
        import traceback
        print(f"ERROR [zalo callback]: {traceback.format_exc()}")


async def _zalo_answer_callback(callback_query_id: str) -> None:
    """Acknowledge Zalo callback_query (mirrors Telegram answerCallbackQuery)."""
    if not callback_query_id:
        return
    from config import ZALO_BOT_TOKEN as token
    if not token:
        return
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"https://bot-api.zaloplatforms.com/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id},
        )


def _extract_zalo_update(body: dict) -> dict:
    """Normalize Zalo Bot webhook payloads to {event_name, message}.

    Current Bot Platform webhooks wrap event data under result, but accepting a
    top-level fallback keeps local fixture tests easy and harmless.
    """
    if not isinstance(body, dict):
        return {}
    result = body.get("result")
    if isinstance(result, dict):
        return result
    return body


async def _zalo_send(chat_id: str, text: str):
    await messenger.send_text(text, channel="zalo", recipient_id=chat_id)


def _parse_money(text: str) -> float | None:
    """Parse money input. Delegates to utils.parse_money — supports plain
    numbers with separators/decimals (1.000.000, 100.50, 1,5) AND Vietnamese
    shorthand (500k, 3tr, 3tr5, 1m2, 2 triệu)."""
    return _utils_parse_money(text)


def _parse_zalo_money(text: str) -> float | None:
    """Parse money from Zalo text input. Alias for _parse_money."""
    return _parse_money(text)


def _zalo_now_for_tx() -> tuple[str, str, str]:
    import time
    from datetime import datetime
    import pytz

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return now.isoformat(timespec="seconds"), sh.fmt_month(now), str(int(time.time()))


def _zalo_slugify_label(name: str) -> str:
    import unicodedata

    nid = unicodedata.normalize("NFD", name.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)
    nid = re.sub(r"[^\w\s]", "", nid)
    nid = re.sub(r"\s+", "_", nid.strip())
    return re.sub(r"[^a-z0-9_]", "", nid) or "custom"


async def _handle_zalo_category_reply(
    sender_id: str, number: int, state: dict, state_key: str
):
    """Process numbered category reply from Zalo user."""
    buckets = state.get("buckets", [])
    row_num = state.get("row_num")
    amount = state.get("amount", 0)
    currency = state.get("currency", "VND")

    if not row_num or not buckets:
        sh.clear_state(state_key)
        await messenger.send_text(
            "Không có giao dịch nào cần phân loại.",
            channel="zalo",
            recipient_id=sender_id,
        )
        return

    try:
        row_num = int(row_num)
    except (TypeError, ValueError):
        sh.clear_state(state_key)
        await messenger.send_text(
            "Không đọc được giao dịch cần phân loại. Mình đã reset lựa chọn Zalo.",
            channel="zalo",
            recipient_id=sender_id,
        )
        return

    row = sh.get_transaction_row(row_num)
    if len(row) > 13 and str(row[13]).upper() == "TRUE":
        parent = row[10] if len(row) > 10 else ""
        parent_label = sh.bucket_label(parent) if parent else "đã có category"
        promoted = await _promote_next_zalo_queue_item(
            sender_id,
            state,
            state_key,
            prefix=(
                f"Giao dịch này đã được phân loại rồi: {parent_label}.\n"
                "Mình chuyển sang giao dịch tiếp theo."
            ),
        )
        if not promoted:
            sh.clear_state(state_key)
            await messenger.send_text(
                f"Giao dịch này đã được phân loại rồi: {parent_label}.\n"
                "Mình đã bỏ lựa chọn cũ trên Zalo.",
                channel="zalo",
                recipient_id=sender_id,
            )
        return

    # 0 = create new category
    if number == 0:
        sh.set_state(state_key, {**state, "step": "await_zalo_new_cat_name"})
        await _zalo_send(sender_id, "Tên category mới? (VD: Gaming, Travel)")
        return

    if number < 1 or number > len(buckets):
        await messenger.send_text(
            f"Số không hợp lệ (1-{len(buckets)} hoặc 0 = tạo mới). Chọn lại:\n\n"
            f"{_format_zalo_bucket_options(buckets)}",
            channel="zalo",
            recipient_id=sender_id,
        )
        return

    selected = buckets[number - 1]
    bucket_id = selected["id"]

    # Backwards compat: stale state from previous version may still have
    # {"id": "new"} in the buckets list. Route to new-category flow.
    if bucket_id == "new":
        sh.set_state(state_key, {**state, "step": "await_zalo_new_cat_name"})
        await _zalo_send(sender_id, "Tên category mới? (VD: Gaming, Travel)")
        return

    subs = sh.get_sub_categories(bucket_id)
    if subs:
        sub_options = [{"key": s["key"], "label": s["label"]} for s in subs]
        sub_options.append({"key": "other", "label": "Other"})
        sh.set_state(state_key, {
            **state,
            "step": "await_zalo_sub",
            "parent_category": bucket_id,
            "sub_options": sub_options,
        })
        lines = [f"{selected['name']} — chọn sub-category:"]
        for i, sub in enumerate(sub_options, 1):
            lines.append(f"{i}. {sub['label']}")
        await _zalo_send(sender_id, "\n".join(lines))
        return

    await _zalo_finalize_transaction(
        sender_id,
        row_num,
        bucket_id,
        "",
        state,
        state_key,
    )


async def _handle_zalo_sub_reply(
    sender_id: str, text: str, state: dict, state_key: str
):
    sub_options = state.get("sub_options") if isinstance(state.get("sub_options"), list) else []
    if not text.isdigit():
        await _zalo_send(sender_id, f"Reply bằng số (1-{len(sub_options)}).")
        return
    idx = int(text) - 1
    if idx < 0 or idx >= len(sub_options):
        await _zalo_send(sender_id, f"Số không hợp lệ (1-{len(sub_options)}).")
        return

    selected = sub_options[idx]
    if selected["key"] == "other":
        sh.set_state(state_key, {**state, "step": "await_zalo_freetext_sub"})
        await _zalo_send(sender_id, "Sub-category này là gì? Gõ tên ngắn gọn.")
        return

    row_num = int(state["row_num"])
    parent = state.get("parent_category") or sh.get_parent_from_sheet(row_num)
    parent_label = sh.bucket_label(parent)
    await _zalo_finalize_transaction(
        sender_id,
        row_num,
        parent,
        selected["label"],
        state,
        state_key,
    )


async def _handle_zalo_freetext_sub(
    sender_id: str, text: str, state: dict, state_key: str
):
    label = text.strip()
    if not label:
        await _zalo_send(sender_id, "Tên sub-category không được trống.")
        return
    row_num = int(state["row_num"])
    parent = state.get("parent_category") or sh.get_parent_from_sheet(row_num)
    sh.save_custom_sub(parent, label)
    parent_label = sh.bucket_label(parent)
    await _zalo_finalize_transaction(
        sender_id,
        row_num,
        parent,
        f"📦 {label}",
        state,
        state_key,
    )


async def _handle_zalo_new_cat_name(
    sender_id: str, text: str, state: dict, state_key: str
):
    name = text.strip()
    if not name or len(name) > 40:
        await _zalo_send(sender_id, "Tên category không hợp lệ (1-40 ký tự).")
        return
    bucket_id = _zalo_slugify_label(name)
    if bucket_id in ("new", "skip"):
        await _zalo_send(sender_id, "Tên này trùng từ khóa hệ thống. Nhập tên khác.")
        return

    from datetime import datetime
    import pytz

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    existing = sh.get_active_buckets(month_key, force_refresh=True)
    if any(b["id"] == bucket_id for b in existing):
        await _zalo_send(sender_id, f"{name} đã tồn tại. Nhập tên khác.")
        return

    sh.write_budget_row(month_key, {"id": bucket_id, "name": name, "allocated": 0, "daily_cap": None})
    sh.invalidate_buckets_cache()
    await _zalo_finalize_transaction(
        sender_id,
        int(state["row_num"]),
        bucket_id,
        "",
        state,
        state_key,
    )


async def _zalo_finalize_transaction(
    sender_id: str,
    row_num: int,
    parent_category: str,
    sub_label: str,
    state: dict,
    state_key: str,
):
    amount = state.get("amount", 0)
    currency = state.get("currency", "VND")
    sh.finalize_transaction(row_num, parent_category, sub_label)

    # Apply ledger if applicable (same pattern as handlers/transaction.py)
    try:
        from handlers.transaction import _apply_ledger_for_row
        _apply_ledger_for_row(row_num)
    except Exception as e:
        print(f"[zalo] ledger error: {e}")

    # the zalo /recat path) — mirrors transaction._finalize.

    tx_direction = state.get("tx_direction", "out")
    summary = render_zalo_logged_summary(
        row_num=row_num,
        bucket_id=parent_category,
        sub_label=sub_label,
        amount=amount,
        tx_date=state.get("tx_date"),
        tx_direction=tx_direction,
        currency=currency,
    )

    queue = state.get("queue") if isinstance(state.get("queue"), list) else []
    if queue:
        promoted = await _promote_next_zalo_queue_item(
            sender_id,
            state,
            state_key,
            prefix=summary,
        )
        if promoted:
            return

    sh.clear_state(state_key)
    # Remind about transactions parked while the user was mid-flow (they are
    # stored under a separate state key, so they survived this whole flow).
    parked = zq.parked_count(sender_id)
    if parked:
        summary += f"\n\n📌 Còn {parked} giao dịch chờ phân loại — gửi /pending."
    await _zalo_send(sender_id, summary)

    # ── Keyword learn suggestion (mirrors Telegram transaction._finalize) ──
    # Only for manual category picks (not recat, not auto-cat).
    description = state.get("description", "")
    if description and tx_direction == "out":
        try:
            from handlers.transaction import _extract_keyword
            existing_rule = sh.match_keyword_rule(description)

            if is_recat and existing_rule and existing_rule["bucket_id"] != parent_category:
                # Recat: old rule → wrong category → offer UPDATE
                old_cat = sh.bucket_label(existing_rule["bucket_id"]) or existing_rule["bucket_id"]
                new_cat = sh.bucket_label(parent_category) or parent_category
                sub_info = f" · {sub_label}" if sub_label else ""
                await _zalo_send(
                    sender_id,
                    f"Rule '{existing_rule['keyword']}' hiện trỏ → {old_cat}.\n"
                    f"Đổi thành → {new_cat}{sub_info}?\n"
                    "Reply Y để đổi, bất kỳ để giữ."
                )
                sh.set_state(state_key, {
                    "step": "await_zalo_kw_learn",
                    "row_num": row_num,
                    "keyword": existing_rule["keyword"],
                    "bucket_id": parent_category,
                    "sub_label": sub_label,
                    "action": "update",
                })
            elif not is_recat and not existing_rule:
                # Manual pick, no existing rule → offer CREATE
                suggested_kw = _extract_keyword(description)
                if suggested_kw and len(suggested_kw) >= 3:
                    cat_name = sh.bucket_label(parent_category) or parent_category
                    sub_info = f" · {sub_label}" if sub_label else ""
                    await _zalo_send(
                        sender_id,
                        f"Tạo rule '{suggested_kw}' → {cat_name}{sub_info} cho lần sau?\n"
                        "Reply Y để tạo, bất kỳ để bỏ qua."
                    )
                    sh.set_state(state_key, {
                        "step": "await_zalo_kw_learn",
                        "row_num": row_num,
                        "keyword": suggested_kw,
                        "bucket_id": parent_category,
                        "sub_label": sub_label,
                        "action": "create",
                    })
        except Exception as e:
            print(f"[zalo] keyword learn suggestion error: {e}")


async def _promote_next_zalo_queue_item(
    sender_id: str,
    state: dict,
    state_key: str,
    prefix: str,
) -> bool:
    queue = state.get("queue") if isinstance(state.get("queue"), list) else []

    while queue:
        next_item = queue.pop(0)
        row_num = next_item.get("row_num") if isinstance(next_item, dict) else None
        buckets = next_item.get("buckets") if isinstance(next_item, dict) else None
        if not row_num or not buckets:
            continue
        try:
            next_row = sh.get_transaction_row(int(row_num))
        except Exception as e:
            print(f"[zalo] queued row read error row={row_num}: {e}")
            continue
        if len(next_row) > 13 and str(next_row[13]).upper() == "TRUE":
            continue

        sh.set_state(state_key, {
            "step": "await_zalo_parent",
            **next_item,
            "queue": queue,
        })
        next_amount = next_item.get("amount", 0)
        next_currency = next_item.get("currency", "VND")
        next_description = next_item.get("description", "")
        next_buckets = next_item.get("buckets", [])
        await messenger.send_text(
            f"{prefix}\n\n"
            f"Giao dịch tiếp theo:\n"
            f"💸 -{sh.fmt_amount(next_amount, next_currency)}\n"
            f"{next_description}\n\n"
            f"Khoản này thuộc mục nào?\n\n"
            f"{_format_zalo_bucket_options(next_buckets)}",
            channel="zalo",
            recipient_id=sender_id,
        )
        return True

    return False


def _format_zalo_bucket_options(buckets: list[dict]) -> str:
    lines = [f"{i + 1}. {b['name']}" for i, b in enumerate(buckets)]
    lines.append("0. Tạo mục mới")
    return "\n".join(lines)

# ─── Zalo: keyword learn suggestion ──────────────────────────


async def _zalo_handle_kw_learn(chat_id: str, text: str, state: dict, state_key: str):
    """Handle Y/N reply for keyword rule creation suggestion.

    State contains: row_num, keyword, bucket_id, sub_label, action (create/update).
    """
    answer = text.strip().lower()
    row_num = state.get("row_num")
    keyword = state.get("keyword", "")
    bucket_id = state.get("bucket_id", "")
    sub_label = state.get("sub_label", "")
    action = state.get("action", "create")

    sh.clear_state(state_key)

    if answer not in ("y", "yes", "1", "có", "ok"):
        await _zalo_send(chat_id, "OK, giữ nguyên.")
        return

    try:
        cat_name = sh.bucket_label(bucket_id) or bucket_id
        sub_info = f" · {sub_label}" if sub_label else ""

        if action == "update":
            existing = sh.match_keyword_rule(
                sh.get_transaction_row(row_num)[5] if sh.get_transaction_row(row_num) and len(sh.get_transaction_row(row_num)) > 5 else ""
            )
            if existing and existing.get("row_num"):
                sh.update_keyword_rule(existing["row_num"], bucket_id=bucket_id, sub_label=sub_label)
                await _zalo_send(chat_id, f"Rule '{existing['keyword']}' đã đổi → {cat_name}{sub_info}")
            else:
                await _zalo_send(chat_id, "Không tìm thấy rule cũ.")
        else:
            added = sh.add_keyword_rule(keyword, bucket_id, sub_label)
            if added:
                await _zalo_send(chat_id, f"Rule mới: '{keyword}' → {cat_name}{sub_info}")
            else:
                await _zalo_send(chat_id, f"Rule '{keyword}' → {cat_name} đã tồn tại.")
    except Exception as e:
        print(f"[zalo] kw learn error: {e}")
        await _zalo_send(chat_id, f"Lỗi: {e}")


# ─── Zalo: /lang ──────────────────────────────────────────────


async def _zalo_cmd_lang(chat_id: str, text: str):
    """Switch bot language via Zalo: /lang vi | /lang en."""
    from i18n.core import get_lang, set_lang

    parts = text.strip().split()
    lang_names = {"vi": "Tiếng Việt", "en": "English"}

    if len(parts) >= 2 and parts[1].lower() in ("vi", "en"):
        lang = parts[1].lower()
        set_lang(lang)
        await _zalo_send(chat_id, f"Đã chuyển sang {lang_names[lang]}.")
    else:
        current = get_lang()
        await _zalo_send(
            chat_id,
            f"Ngôn ngữ hiện tại: {lang_names.get(current, current)}\n\n"
            "Đổi: /lang vi hoặc /lang en"
        )


# ─── Zalo: /today ─────────────────────────────────────────────


async def _zalo_cmd_today(chat_id: str):
    """Send today's spending status via Zalo (plain text)."""
    from datetime import datetime
    import pytz
    from config import TIMEZONE, DAILY_BUCKET_ID

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)

    buckets = sh.get_active_buckets(month_key)
    daily_bkt = next((b for b in buckets if b["id"] == DAILY_BUCKET_ID), None)

    day = sh.get_daily_status(now)

    if not daily_bkt or not daily_bkt.get("daily_cap"):
        msg = (
            f"Daily spending — {now.strftime('%b %d')}\n\n"
            f"Đã tiêu: {sh.fmt_amount(day['spent'])}\n\n"
            "Chưa set daily limit. Bật: /manage → Daily Spending → 5 (Daily cap)."
        )
    else:
        pct = sh.calc_pct(day["spent"], day["cap"])
        msg = (
            f"Daily spending — {now.strftime('%b %d')}\n\n"
            f"{sh.make_bar(pct)} {pct}%\n"
            f"Đã tiêu: {sh.fmt_amount(day['spent'])} / {sh.fmt_amount(day['cap'])}\n"
            f"Còn lại: {sh.fmt_amount(day['remaining'])}\n"
        )
        if pct >= 100:
            msg += "\nVượt giới hạn ngày."
        elif pct >= 80:
            msg += f"\nCòn {sh.fmt_amount(day['remaining'])} hôm nay."
        elif day["spent"] == 0:
            msg += "\nHôm nay chưa tiêu gì."

    await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)


# ─── Zalo: /report ────────────────────────────────────────────


async def _zalo_cmd_report(chat_id: str, text: str, state_key: str):
    """Send spending report via Zalo with period selection menu."""
    from handlers.report import (
        _scan_period, _render_account_lens, _render_category_lens,
        _PERIOD_ALIASES,
    )

    parts = text.strip().split()
    period_code = "m"
    if len(parts) >= 2:
        period_code = _PERIOD_ALIASES.get(parts[1].lower(), "m")

    data = _scan_period(period_code)
    # Default: category lens (both-channel parity)
    msg = messenger._strip_markdown(_render_category_lens(data))

    msg += (
        "\n\nĐổi kỳ: reply số\n"
        "1. Tuần\n"
        "2. Tháng\n"
        "3. Quý\n"
        "4. Năm\n"
        "5. Xem theo Account\n"
        "- /cancel để thoát"
    )

    sh.set_state(state_key, {"step": "zalo_report_menu", "period": period_code, "lens": "c"})
    await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)


async def _zalo_report_handle_menu(chat_id: str, text: str, state: dict, state_key: str):
    """Handle report period/lens switching."""
    from handlers.report import (
        _scan_period, _render_account_lens, _render_category_lens,

    )

    period_map = {"1": "w", "2": "m", "3": "q", "4": "y"}
    current_period = state.get("period", "m")
    current_lens = state.get("lens", "c")

    if text in period_map:
        current_period = period_map[text]
    elif text == "5":
        # Toggle lens
        current_lens = "a" if current_lens == "c" else "c"
    else:
        await messenger.send_text("Reply 1-5 hoặc /cancel.", channel="zalo", recipient_id=chat_id)
        return

    data = _scan_period(current_period)
    if current_lens == "a":
        msg = messenger._strip_markdown(_render_account_lens(data))
    else:
        msg = messenger._strip_markdown(_render_category_lens(data))

    lens_label = "Account" if current_lens == "a" else "Category"
    toggle_label = "Category" if current_lens == "a" else "Account"
    msg += (
        "\n\nĐổi kỳ: reply số\n"
        "1. Tuần\n"
        "2. Tháng\n"
        "3. Quý\n"
        "4. Năm\n"
        f"5. Xem theo {toggle_label}\n"
        "- /cancel để thoát"
    )

    sh.set_state(state_key, {"step": "zalo_report_menu", "period": current_period, "lens": current_lens})
    await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)


# ─── Zalo: /accounts ──────────────────────────────────────────


async def _zalo_handle_account_setup_action(
    chat_id: str,
    action: str,
    setup_key: str,
    state_key: str,
):
    if not setup_key:
        await _zalo_send(chat_id, "Thiếu setup key. Reply dạng: setup <key> hoặc skip <key>.")
        return

    entry = sh.get_pending_by_setup_key(setup_key)
    if not entry:
        await _zalo_send(chat_id, "Phiên setup đã hết hạn hoặc đã hoàn tất. Đợi tx mới hoặc dùng /accounts add.")
        return

    if action == "skip":
        sh.mark_pending_skipped(setup_key)
        sh.clear_state(state_key)
        await _zalo_send(chat_id, "Đã skip. Giao dịch vẫn được ghi nhưng không gắn account/card.")
        return

    sh.set_state(state_key, {
        "step": "zalo_accounts_name",
        "pending_setup_key": setup_key,
        "pending_source_key": entry["source_key"],
        "pending_identifier": entry["identifier"],
        "new_acct_row_num": entry["tx_row_num"] or 0,
        "pending_account": {},
    })
    await _zalo_send(
        chat_id,
        f"Setup account/card mới — {entry['identifier']}\n\n"
        "Nhập tên hiển thị:\n"
        "(VD: TCB Tiêu dùng, Cake Visa 8421)",
    )


async def _zalo_cmd_accounts(chat_id: str, text: str, state_key: str):
    """List accounts or start add wizard.

    Subcommands:
      /accounts       → list (default)
      /accounts add   → start manual add wizard
    """
    from handlers.accounts import _account_list_lines

    parts = text.strip().split()
    sub = parts[1].lower() if len(parts) >= 2 else ""

    if sub in ("add", "new", "create"):
        sh.set_state(state_key, {
            "step": "zalo_accounts_name",
            "pending_source_key": "",
            "pending_setup_key": "",
            "pending_identifier": "",
            "new_acct_row_num": 0,
            "pending_account": {},
        })
        await messenger.send_text(
            "Setup account mới\n\n"
            "Nhập tên hiển thị:\n"
            "(VD: TCB Tiêu dùng, Cake Visa 8421)",
            channel="zalo", recipient_id=chat_id,
        )
        return

    if sub == "assign":
        slug = parts[2].strip() if len(parts) >= 3 else ""
        await _zalo_cmd_accounts_assign(chat_id, slug, state_key)
        return

    # Default: list
    lines = _account_list_lines()
    msg = "Accounts đã setup\n\n" + "\n\n".join(lines)
    msg = messenger._strip_markdown(msg)
    msg += "\n\nDùng /accounts add để thêm account mới."
    msg += "\nDùng /accounts assign <slug> để gán tx lịch sử chưa map."
    await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)


async def _zalo_accounts_handle_name(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Step 1: receive account name, ask for type."""
    from handlers.accounts import _slugify

    name = text.strip()
    if not (1 <= len(name) <= 60):
        await messenger.send_text(
            "Tên 1-60 ký tự. Thử lại.",
            channel="zalo", recipient_id=chat_id,
        )
        return

    slug = _slugify(name)

    # Check slug collision
    existing = sh.find_account_by_id(slug)
    if existing and not state.get("pending_source_key"):
        await messenger.send_text(
            f"Account {slug} đã tồn tại! Thử tên khác.",
            channel="zalo", recipient_id=chat_id,
        )
        return

    sh.set_state(state_key, {
        **state,
        "step": "zalo_accounts_type",
        "acc_name": name,
        "acc_slug": slug,
        "pending_account": {"name": name, "id": slug},
    })
    await messenger.send_text(
        f"Tên: {name} (slug: {slug})\n\n"
        "Chọn loại tài khoản:\n"
        "1. Bank\n"
        "2. Debit\n"
        "3. Cash\n"
        "4. Credit card",
        channel="zalo", recipient_id=chat_id,
    )


async def _zalo_accounts_handle_type(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Step 2: receive type, commit account."""
    type_map = {"1": "bank", "2": "debit", "3": "cash", "4": "credit"}
    acc_type = type_map.get(text.strip())
    if not acc_type:
        await messenger.send_text(
            "Reply 1, 2, 3 hoặc 4.",
            channel="zalo", recipient_id=chat_id,
        )
        return

    pending = dict(state.get("pending_account") or {})
    pending.update({
        "name": state.get("acc_name", ""),
        "id": state.get("acc_slug", ""),
        "type": acc_type,
        "currency": "VND",
    })

    if acc_type == "credit":
        sh.set_state(state_key, {
            **state,
            "step": "zalo_accounts_credit_limit",
            "pending_account": pending,
        })
        await _zalo_send(
            chat_id,
            "Hạn mức thẻ tín dụng (VND)?\n"
            "Vd: 30000000",
        )
        return

    pending["starting_balance"] = 0
    pending["credit_limit"] = 0
    pending["starting_outstanding"] = 0
    await _zalo_commit_account_setup(chat_id, {**state, "pending_account": pending}, state_key)


async def _zalo_accounts_handle_credit_limit(
    chat_id: str, text: str, state: dict, state_key: str
):
    val = _parse_zalo_money(text)
    if val is None or val <= 0:
        await _zalo_send(chat_id, "Hạn mức phải là số dương. Thử lại.")
        return
    pending = dict(state.get("pending_account") or {})
    pending["credit_limit"] = val
    sh.set_state(state_key, {
        **state,
        "step": "zalo_accounts_credit_outstanding",
        "pending_account": pending,
    })
    await _zalo_send(
        chat_id,
        "Dư nợ hiện tại trên thẻ (VND)?\n"
        "Nhập 0 nếu chưa dùng hoặc đã trả hết.",
    )


async def _zalo_accounts_handle_credit_outstanding(
    chat_id: str, text: str, state: dict, state_key: str
):
    val = _parse_zalo_money(text)
    if val is None or val < 0:
        await _zalo_send(chat_id, "Dư nợ phải >= 0. Thử lại.")
        return
    pending = dict(state.get("pending_account") or {})
    limit = float(pending.get("credit_limit") or 0)
    if val > limit:
        await _zalo_send(
            chat_id,
            f"Dư nợ {sh.fmt_amount(val)} lớn hơn hạn mức {sh.fmt_amount(limit)}. Kiểm tra lại.",
        )
        return
    pending["starting_outstanding"] = val
    pending["starting_balance"] = 0
    sh.set_state(state_key, {
        **state,
        "step": "zalo_accounts_credit_statement",
        "pending_account": pending,
    })
    await _zalo_send(chat_id, _credit_statement_prompt())


async def _zalo_accounts_handle_credit_statement(
    chat_id: str, text: str, state: dict, state_key: str
):
    day, ok, err = parse_billing_day(text)
    if not ok:
        await _zalo_send(chat_id, err)
        return
    pending = dict(state.get("pending_account") or {})
    pending["statement_day"] = day
    sh.set_state(state_key, {
        **state,
        "step": "zalo_accounts_credit_due",
        "pending_account": pending,
    })
    await _zalo_send(chat_id, _credit_due_prompt())


async def _zalo_accounts_handle_credit_due(
    chat_id: str, text: str, state: dict, state_key: str
):
    day, ok, err = parse_billing_day(text)
    if not ok:
        await _zalo_send(chat_id, err)
        return
    pending = dict(state.get("pending_account") or {})
    pending["due_day"] = day
    await _zalo_commit_account_setup(chat_id, {**state, "pending_account": pending}, state_key)


async def _zalo_commit_account_setup(chat_id: str, state: dict, state_key: str):
    pending = state.get("pending_account") or {}
    source_key = (state.get("pending_source_key") or "").strip().lower()
    trigger_row = state.get("new_acct_row_num")

    if not pending.get("id") or not pending.get("type") or not pending.get("currency"):
        sh.clear_state(state_key)
        await _zalo_send(chat_id, "Thiếu dữ liệu setup. Gửi /accounts add để thử lại.")
        return

    bind_message: str | None = None
    account_id = pending["id"]
    async with sh.account_lock:
        existing_by_source = sh.find_account_by_source_key(source_key) if source_key else None
        if existing_by_source:
            account_id = existing_by_source["id"]
            bind_message = f"Account {account_id} đã có sẵn theo source này — dùng account cũ."
        else:
            ok = sh.add_account(
                account_id=pending["id"],
                name=pending["name"],
                acc_type=pending["type"],
                currency=pending["currency"],
                source_keys=[source_key] if source_key else [],
                starting_balance=float(pending.get("starting_balance") or 0),
                credit_limit=float(pending.get("credit_limit") or 0),
                starting_outstanding=float(pending.get("starting_outstanding") or 0),
                statement_day=pending.get("statement_day"),
                due_day=pending.get("due_day"),
            )
            if ok:
                account_id = pending["id"]
            else:
                slug_match = sh.find_account_by_id(pending["id"])
                if slug_match and source_key:
                    sh.add_source_key_to_account(slug_match["id"], source_key)
                    account_id = slug_match["id"]
                    bind_message = f"Đã link source {source_key} vào account có sẵn {account_id}."
                else:
                    sh.clear_state(state_key)
                    await _zalo_send(
                        chat_id,
                        f"Slug {pending['id']} đã tồn tại. Hủy setup, thử lại với tên khác.",
                    )
                    return

    backfilled = _zalo_backfill_account(account_id, source_key, trigger_row)
    setup_key = state.get("pending_setup_key") or ""
    if setup_key:
        sh.mark_pending_completed(setup_key)

    sh.clear_state(state_key)
    if bind_message:
        msg = bind_message
    else:
        msg = (
            f"Account {pending['name']} đã setup\n"
            f"slug: {account_id}\n"
            f"type: {pending['type']} · {pending['currency']}"
        )
        if source_key:
            msg += f"\nsource: {source_key}"
    if backfilled:
        msg += f"\nĐã backfill {backfilled} tx gần đây."
    await _zalo_send(chat_id, msg)


def _zalo_backfill_account(account_id: str, source_key: str, trigger_row: int | None) -> int:
    count = 0
    if trigger_row:
        try:
            row_num = int(trigger_row)
            sh.set_tx_account(row_num, account_id)
            row = sh.get_transaction_row(row_num)
            confirmed = len(row) > 13 and str(row[13]).upper() == "TRUE"
            if confirmed and not sh.is_ledger_applied(row_num):
                from handlers.transaction import _apply_ledger_for_row
                _apply_ledger_for_row(row_num)
            count += 1
        except Exception as e:
            print(f"[zalo accounts] backfill trigger error row={trigger_row}: {e}")
    try:
        count += sh.backfill_account_id_by_source_key(account_id, source_key)
    except Exception as e:
        print(f"[zalo accounts] source-key backfill error source={source_key!r}: {e}")
    return count


async def _zalo_cmd_accounts_assign(chat_id: str, slug: str, state_key: str):
    if not slug:
        await _zalo_send(
            chat_id,
            "Usage: /accounts assign <slug>\n"
            "Vd: /accounts assign tpb_2601\n\n"
            "Gán tất cả tx cùng currency chưa map account vào account này.",
        )
        return

    acc = sh.find_account_by_id(slug)
    if not acc:
        await _zalo_send(chat_id, f"Account {slug} không tồn tại. Gửi /accounts để xem list.")
        return

    ws = sh._sheet(sh.S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]
    candidate_rows: list[int] = []
    total_out = total_in = 0.0
    out_count = in_count = 0
    for i, row in enumerate(rows):
        if len(row) < 8:
            continue
        if (row[16] if len(row) > 16 else "").strip():
            continue
        if sh.row_currency(row) != acc["currency"]:
            continue
        tx_type = row[6] if len(row) > 6 else ""
        if tx_type not in ("Tiền ra", "Tiền vào"):
            continue
        amount = sh._parse_amount(row[7]) or 0.0
        if amount <= 0:
            continue
        candidate_rows.append(i + 2)
        if tx_type == "Tiền ra":
            total_out += amount
            out_count += 1
        else:
            total_in += amount
            in_count += 1

    if not candidate_rows:
        await _zalo_send(chat_id, f"Không có tx {acc['currency']} nào chưa map account cho {slug}.")
        return

    sh.set_state(state_key, {
        "step": "zalo_accounts_assign_confirm",
        "assign_slug": slug,
        "assign_rows": candidate_rows,
    })
    await _zalo_send(
        chat_id,
        f"Bulk assign — {slug} ({acc['currency']}, {acc['type']})\n\n"
        f"Tx chưa map:\n"
        f"Vào: +{sh.fmt_amount(total_in, acc['currency'])} ({in_count} tx)\n"
        f"Ra: -{sh.fmt_amount(total_out, acc['currency'])} ({out_count} tx)\n\n"
        f"Tổng: {len(candidate_rows)} tx → gán hết vào {slug}?\n"
        'Reply "yes" để xác nhận, hoặc bất kỳ để hủy.',
    )


async def _zalo_accounts_handle_assign_confirm(
    chat_id: str, text: str, state: dict, state_key: str
):
    if text.lower() not in ("yes", "y", "co", "có"):
        sh.clear_state(state_key)
        await _zalo_send(chat_id, "Đã hủy bulk assign.")
        return

    rows: list[int] = state.get("assign_rows") or []
    slug = state.get("assign_slug") or ""
    if not rows or not slug:
        sh.clear_state(state_key)
        await _zalo_send(chat_id, "State đã hết hạn. Chạy /accounts assign <slug> lại.")
        return

    ws = sh._sheet(sh.S.TRANSACTIONS)
    ws.batch_update([{"range": f"Q{rn}:Q{rn}", "values": [[slug]]} for rn in rows])
    sh.clear_state(state_key)
    await _zalo_send(chat_id, f"Đã assign {len(rows)} tx → {slug}. Gửi /report để kiểm tra.")


async def _zalo_cmd_transfer(chat_id: str, text: str):
    parts = text.strip().split()
    if len(parts) < 4:
        await _zalo_send(chat_id, "Usage: /transfer <amount> <from> <to>\nVd: /transfer 1000000 tcb_main cake_main")
        return
    amount = _parse_zalo_money(parts[1])
    if amount is None or amount <= 0:
        await _zalo_send(chat_id, "Số tiền không hợp lệ.")
        return
    from_id, to_id = parts[2].strip(), parts[3].strip()
    if from_id == to_id:
        await _zalo_send(chat_id, "from và to phải khác account.")
        return

    from_acc = sh.find_account_by_id(from_id)
    to_acc = sh.find_account_by_id(to_id)
    if not from_acc:
        await _zalo_send(chat_id, f"Account {from_id} không tồn tại. Gửi /accounts để xem list.")
        return
    if not to_acc:
        await _zalo_send(chat_id, f"Account {to_id} không tồn tại.")
        return
    if from_acc["currency"] != to_acc["currency"]:
        await _zalo_send(chat_id, f"Currency mismatch: {from_acc['currency']} → {to_acc['currency']}.")
        return

    iso, month_key, ts = _zalo_now_for_tx()
    row_num, status = sh.append_transfer(
        from_account_id=from_id,
        to_account_id=to_id,
        amount=amount,
        currency=from_acc["currency"],
        description=f"transfer {from_id} → {to_id}",
        tx_date=iso,
        ref_code=f"TRANSFER_{from_id}_{to_id}_{ts}",
        month_key=month_key,
    )
    if status != "ok":
        await _zalo_send(chat_id, status)
        return

    sh.invalidate_accounts_cache()
    from_after = sh.find_account_by_id(from_id)
    to_after = sh.find_account_by_id(to_id)
    cur = from_acc["currency"]
    await _zalo_send(
        chat_id,
        f"Transfer ghi nhận\n"
        f"{from_acc['name']} → {to_acc['name']}\n"
        f"Số tiền: {sh.fmt_amount(amount, cur)}\n\n"
        f"Số dư mới:\n"
        f"{from_acc['name']}: {sh.fmt_amount(from_after['running_balance'], cur)}\n"
        f"{to_acc['name']}: {sh.fmt_amount(to_after['running_balance'], cur)}",
    )


async def _zalo_cmd_cc_pay(chat_id: str, text: str):
    parts = text.strip().split()
    if len(parts) not in (4, 5) or parts[1].lower() != "pay":
        await _zalo_send(
            chat_id,
            "Usage:\n"
            "/cc pay <amount> <cc_id> — trả từ nguồn ngoài\n"
            "/cc pay <amount> <bank_id> <cc_id> — trả từ bank account đã onboard",
        )
        return
    amount = _parse_zalo_money(parts[2])
    if amount is None or amount <= 0:
        await _zalo_send(chat_id, "Số tiền không hợp lệ.")
        return

    iso, month_key, ts = _zalo_now_for_tx()
    if len(parts) == 4:
        cc_id = parts[3].strip()
        cc_acc = sh.find_account_by_id(cc_id)
        if not cc_acc:
            await _zalo_send(chat_id, f"CC {cc_id} không tồn tại.")
            return
        if cc_acc["type"] != "credit":
            await _zalo_send(chat_id, f"{cc_id} không phải credit card (type={cc_acc['type']}).")
            return

        row_num, status = sh.append_cc_payment_external(
            cc_account_id=cc_id,
            amount=amount,
            currency=cc_acc["currency"],
            description=f"cc payment external → {cc_id}",
            tx_date=iso,
            ref_code=f"CCPAYEXT_{cc_id}_{ts}",
            month_key=month_key,
        )
        if status != "ok":
            await _zalo_send(chat_id, status)
            return
        sh.invalidate_accounts_cache()
        cc_after = sh.find_account_by_id(cc_id)
        cur = cc_acc["currency"]
        await _zalo_send(
            chat_id,
            f"CC payment ghi nhận (external)\n"
            f"→ {cc_acc['name']}\n"
            f"Số tiền: {sh.fmt_amount(amount, cur)}\n\n"
            f"{cc_acc['name']} dư nợ: {sh.fmt_amount(cc_after['outstanding_balance'], cur)}",
        )
        return

    bank_id, cc_id = parts[3].strip(), parts[4].strip()
    bank_acc = sh.find_account_by_id(bank_id)
    cc_acc = sh.find_account_by_id(cc_id)
    if not bank_acc:
        await _zalo_send(chat_id, f"Bank {bank_id} không tồn tại.")
        return
    if not cc_acc:
        await _zalo_send(chat_id, f"CC {cc_id} không tồn tại.")
        return
    if cc_acc["type"] != "credit":
        await _zalo_send(chat_id, f"{cc_id} không phải credit card (type={cc_acc['type']}).")
        return

    row_num, status = sh.append_cc_payment(
        bank_account_id=bank_id,
        cc_account_id=cc_id,
        amount=amount,
        currency=bank_acc["currency"],
        description=f"cc payment {bank_id} → {cc_id}",
        tx_date=iso,
        ref_code=f"CCPAY_{bank_id}_{cc_id}_{ts}",
        month_key=month_key,
    )
    if status != "ok":
        await _zalo_send(chat_id, status)
        return

    sh.invalidate_accounts_cache()
    bank_after = sh.find_account_by_id(bank_id)
    cc_after = sh.find_account_by_id(cc_id)
    cur = bank_acc["currency"]
    await _zalo_send(
        chat_id,
        f"CC payment ghi nhận\n"
        f"{bank_acc['name']} → {cc_acc['name']}\n"
        f"Số tiền: {sh.fmt_amount(amount, cur)}\n\n"
        f"{bank_acc['name']}: {sh.fmt_amount(bank_after['running_balance'], cur)}\n"
        f"{cc_acc['name']} dư nợ: {sh.fmt_amount(cc_after['outstanding_balance'], cur)}",
    )


async def _zalo_cmd_recat(chat_id: str, text: str, state_key: str):
    """Zalo /recat — mirror the Telegram command:

    /recat            → numbered picker of the 8 most recent outgoing tx
    /recat <row_num>  → target a sheet row directly (power-user mode)
    """
    parts = text.strip().split()
    if len(parts) >= 2 and parts[1].isdigit():
        await _zalo_recat_row(chat_id, int(parts[1]), state_key)
        return

    recent = sh.get_recent_transactions(limit=8)
    if not recent:
        await _zalo_send(chat_id, "Không có giao dịch nào trong tháng này.")
        return

    lines = ["Re-categorize — chọn giao dịch muốn sửa (reply số):", ""]
    rows: list[int] = []
    for i, tx in enumerate(recent, 1):
        desc = tx["description"][:30] + "…" if len(tx["description"]) > 30 else tx["description"]
        status = f"→ {tx['bucket_name']}" if tx["bucket_name"] else "(chưa phân loại)"
        lines.append(f"{i}. -{sh.fmt_amount(tx['amount'], tx['currency'])} {desc} {status}")
        rows.append(tx["row_num"])
    lines.append("")
    lines.append("- /cancel để thoát")

    sh.set_state(state_key, {"step": "zalo_recat_pick", "recat_rows": rows})
    await _zalo_send(chat_id, "\n".join(lines))


async def _zalo_recat_handle_pick(chat_id: str, text: str, state: dict, state_key: str):
    rows = state.get("recat_rows") or []
    if not text.isdigit():
        await _zalo_send(chat_id, f"Reply bằng số (1-{len(rows)}) hoặc /cancel.")
        return
    idx = int(text) - 1
    if idx < 0 or idx >= len(rows):
        await _zalo_send(chat_id, f"Số không hợp lệ (1-{len(rows)}).")
        return
    await _zalo_recat_row(chat_id, int(rows[idx]), state_key)


async def _zalo_recat_row(chat_id: str, row_num: int, state_key: str):
    """Re-categorize one sheet row via the Zalo numbered picker."""
    if row_num < 2:
        await _zalo_send(chat_id, f"Không tìm thấy transaction row {row_num}.")
        return
    row = sh.get_transaction_row(row_num)
    if not row:
        await _zalo_send(chat_id, f"Không tìm thấy transaction row {row_num}.")
        return

    amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
    description = row[5] if len(row) > 5 else ""
    currency = sh.row_currency(row)
    tx_direction = "in" if (row[6] if len(row) > 6 else "") == "Tiền vào" else "out"
    if tx_direction == "in":
        await _zalo_send(chat_id, "Income hiện không cần category. Không recat.")
        return

    # Transfers & cc payments have their own 2-leg ledger — recategorizing
    # one as a bucket expense would corrupt account balances (mirrors the
    # Telegram guard).
    ledger_type = (row[17] if len(row) > 17 else "").strip().lower()
    if ledger_type in ("transfer", "cc_payment"):
        await _zalo_send(chat_id, "Giao dịch chuyển khoản / trả thẻ có ledger riêng — không recat.")
        return

    from datetime import datetime
    import pytz

    tz = pytz.timezone(TIMEZONE)
    # Historical tx keep their own month — cross-month recat must not use
    # "now" (mirrors the Telegram fix): summaries + bucket lists follow the
    # month the tx belongs to.
    row_month = row[14] if len(row) > 14 else ""
    month_key = row_month or sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key, force_refresh=True)
    if not buckets:
        await _zalo_send(chat_id, f"Không có category active cho tháng {month_key}. Dùng /manage trước.")
        return

    sh.reset_transaction_row(row_num)

    bucket_map = [{"id": b["id"], "name": b["name"]} for b in buckets]
    sh.set_state(state_key, {
        "step": "await_zalo_parent",
        "row_num": row_num,
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": tx_direction,
        "tx_date": row[1] if len(row) > 1 else "",
        "buckets": bucket_map,
        "queue": [],
    })
    await _zalo_send(
        chat_id,
        f"Re-categorize: -{sh.fmt_amount(amount, currency)}\n"
        f"{description}\n\n"
        f"Khoản này thuộc mục nào?\n\n"
        f"{_format_zalo_bucket_options(bucket_map)}",
    )


async def _zalo_cmd_pending(chat_id: str, state_key: str):
    """Zalo /pending — categorize transactions parked while the user was
    mid-flow (mirrors the Telegram /pending command)."""
    from datetime import datetime
    import pytz

    item = zq.pop_next_unconfirmed(chat_id)
    if not item:
        await _zalo_send(chat_id, "Không có giao dịch nào chờ phân loại.")
        return

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key, force_refresh=True)
    if not buckets:
        # Put the item back so it isn't lost, then point at /manage.
        zq.park(chat_id, item)
        await _zalo_send(chat_id, "Chưa có category nào. Dùng /manage trước.")
        return

    bucket_map = [{"id": b["id"], "name": b["name"]} for b in buckets]
    remaining = zq.parked_count(chat_id)
    remaining_note = f"\n📌 Còn {remaining} giao dịch chờ sau giao dịch này.\n" if remaining else ""

    sh.set_state(state_key, {
        "step": "await_zalo_parent",
        "row_num": item["row_num"],
        "amount": item.get("amount", 0),
        "currency": item.get("currency", "VND"),
        "description": item.get("description", ""),
        "tx_direction": item.get("tx_direction", "out"),
        "tx_date": item.get("tx_date", ""),
        "buckets": bucket_map,
        "queue": [],
    })
    await _zalo_send(
        chat_id,
        f"💸 -{sh.fmt_amount(item.get('amount', 0), item.get('currency', 'VND'))}\n"
        f"{item.get('description', '')}\n{remaining_note}\n"
        f"Khoản này thuộc mục nào?\n\n"
        f"{_format_zalo_bucket_options(bucket_map)}",
    )


# ─── Zalo: /manage ────────────────────────────────────────────


async def _zalo_cmd_manage(chat_id: str, state_key: str):
    """Show category list with numbered menu for manage actions."""
    from datetime import datetime
    import pytz
    from config import TIMEZONE

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key, force_refresh=True)

    if not buckets:
        async with sh.bootstrap_lock:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_buckets_from_previous_month(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_default_categories(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)

    lines = [f"Manage Categories — {month_key}\n"]
    total = 0
    for i, b in enumerate(buckets, 1):
        alloc = b.get("allocated", 0)
        if alloc > 0:
            lines.append(f"{i}. {b['name']}   {sh.fmt_amount(alloc)}")
            total += alloc
        else:
            lines.append(f"{i}. {b['name']}   tracking")
    lines.append(f"─────────────────────\nTotal: {sh.fmt_amount(total)}")
    lines.append("\nReply:")
    lines.append('- Số (VD: "3") để sửa category đó')
    lines.append('- "add" để thêm category mới')
    lines.append("- /cancel để thoát")

    sh.set_state(state_key, {"step": "zalo_manage", "month_key": month_key})
    await messenger.send_text("\n".join(lines), channel="zalo", recipient_id=chat_id)


async def _zalo_manage_handle_menu(chat_id: str, text: str, state: dict, state_key: str):
    """Handle manage menu: pick category by number or add."""
    month_key = state.get("month_key", "")

    if text.lower() == "add":
        sh.set_state(state_key, {**state, "step": "zalo_manage_add_name"})
        await messenger.send_text(
            "Nhập tên category mới:\n(VD: Gaming, Travel, Food)",
            channel="zalo", recipient_id=chat_id,
        )
        return

    if text.isdigit():
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        idx = int(text) - 1
        if 0 <= idx < len(buckets):
            bucket = buckets[idx]
            bkt_status = sh.get_bucket_status(bucket["id"], month_key)
            name = bucket["name"]

            if bkt_status["allocated"] > 0:
                pct = sh.calc_pct(bkt_status["spent"], bkt_status["allocated"])
                info = (
                    f"{name}\n"
                    f"Mode: Budgeted\n"
                    f"Allocated: {sh.fmt_amount(bkt_status['allocated'])}\n"
                    f"Spent: {sh.fmt_amount(bkt_status['spent'])} ({pct}%)"
                )
            else:
                info = (
                    f"{name}\n"
                    f"Mode: Tracking-only\n"
                    f"Spent: {sh.fmt_amount(bkt_status['spent'])} tháng này"
                )

            from config import DAILY_BUCKET_ID
            is_daily = bucket["id"] == DAILY_BUCKET_ID
            if is_daily:
                cap = bucket.get("daily_cap")
                info += f"\nDaily cap: {sh.fmt_amount(cap) + '/ngày' if cap else 'chưa đặt'}"

            sh.set_state(state_key, {
                **state,
                "step": "zalo_manage_bucket_menu",
                "edit_bucket_id": bucket["id"],
                "edit_bucket_name": name,
            })
            menu = (
                f"{info}\n\nReply:\n"
                "1. Sửa budget amount\n"
                "2. Đổi tên\n"
                "3. Sub-categories\n"
                "4. Xóa category\n"
            )
            if is_daily:
                menu += "5. Daily cap (giới hạn mỗi ngày cho /today)\n"
            menu += "- /cancel để thoát"
            await messenger.send_text(menu, channel="zalo", recipient_id=chat_id)
            return
        else:
            await messenger.send_text(
                f"Số không hợp lệ (1-{len(buckets)}).",
                channel="zalo", recipient_id=chat_id,
            )
            return

    await messenger.send_text(
        'Reply "add" hoặc số thứ tự category.',
        channel="zalo", recipient_id=chat_id,
    )


async def _zalo_manage_handle_bucket_menu(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle per-bucket action menu."""
    bucket_id = state.get("edit_bucket_id", "")
    month_key = state.get("month_key", "")

    if text == "1":  # Edit amount
        bkt_status = sh.get_bucket_status(bucket_id, month_key)
        current = sh.fmt_amount(bkt_status["allocated"]) if bkt_status["allocated"] > 0 else "tracking"
        sh.set_state(state_key, {**state, "step": "zalo_manage_edit_amount"})
        await messenger.send_text(
            f"{state.get('edit_bucket_name', '?')} — hiện tại: {current}\n"
            "Nhập số tiền mới (0 = tracking-only):",
            channel="zalo", recipient_id=chat_id,
        )
    elif text == "2":  # Rename
        sh.set_state(state_key, {**state, "step": "zalo_manage_rename"})
        await messenger.send_text(
            f"Tên hiện tại: {state.get('edit_bucket_name', '?')}\nNhập tên mới:",
            channel="zalo", recipient_id=chat_id,
        )
    elif text == "3":  # Sub-categories
        await _zalo_manage_show_subs(chat_id, state, state_key)
    elif text == "4":  # Delete
        name = state.get("edit_bucket_name", "?")
        tx_count = sh.count_bucket_transactions(bucket_id, month_key)
        sh.set_state(state_key, {**state, "step": "zalo_manage_confirm_delete"})
        await messenger.send_text(
            f"Xóa {name}?\n"
            f"Bucket này có {tx_count} transactions.\n"
            f'Reply "yes" để xác nhận, hoặc bất kỳ để hủy.',
            channel="zalo", recipient_id=chat_id,
        )
    elif text == "5":  # Daily cap (daily_spending bucket only)
        from config import DAILY_BUCKET_ID
        if bucket_id != DAILY_BUCKET_ID:
            await messenger.send_text("Reply 1, 2, 3 hoặc 4.", channel="zalo", recipient_id=chat_id)
            return
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        bucket = next((b for b in buckets if b["id"] == bucket_id), None)
        cap = (bucket or {}).get("daily_cap")
        current = f"{sh.fmt_amount(cap)}/ngày" if cap else "chưa đặt"
        sh.set_state(state_key, {**state, "step": "zalo_manage_edit_daily_cap"})
        await messenger.send_text(
            f"{state.get('edit_bucket_name', '?')} — daily cap hiện tại: {current}\n"
            "Nhập cap mới cho MỖI NGÀY (vd 100k, 150000 — 0 để tắt):",
            channel="zalo", recipient_id=chat_id,
        )
    else:
        await messenger.send_text("Reply 1, 2, 3, 4 hoặc 5.", channel="zalo", recipient_id=chat_id)


async def _zalo_manage_show_subs(chat_id: str, state: dict, state_key: str):
    bucket_id = state.get("edit_bucket_id", "")
    name = state.get("edit_bucket_name") or sh.bucket_label(bucket_id)
    subs = sh.get_sub_categories(bucket_id)
    sh.set_state(state_key, {
        **state,
        "step": "zalo_manage_subs",
        "sub_options": [{"key": s["key"], "label": s["label"]} for s in subs],
    })
    if not subs:
        await _zalo_send(
            chat_id,
            f"{name} chưa có sub-category.\n"
            "Sub-category sẽ được tạo khi phân loại transaction với lựa chọn Other.\n\n"
            'Reply "back" để quay lại.',
        )
        return
    lines = [f"Sub-categories of {name}\n"]
    for i, sub in enumerate(subs, 1):
        lines.append(f"{i}. {sub['label']}")
    lines.append('\nReply số để sửa/xóa, hoặc "back" để quay lại.')
    await _zalo_send(chat_id, "\n".join(lines))


async def _zalo_manage_handle_subs(chat_id: str, text: str, state: dict, state_key: str):
    if text.lower() == "back":
        sh.set_state(state_key, {**state, "step": "zalo_manage_bucket_menu"})
        await _zalo_send(
            chat_id,
            f"{state.get('edit_bucket_name', '?')}\n\n"
            "Reply:\n"
            "1. Sửa budget amount\n"
            "2. Đổi tên\n"
            "3. Sub-categories\n"
            "4. Xóa category\n"
            "- /cancel để thoát",
        )
        return

    subs = state.get("sub_options") if isinstance(state.get("sub_options"), list) else []
    if not text.isdigit():
        await _zalo_send(chat_id, 'Reply số sub-category hoặc "back".')
        return
    idx = int(text) - 1
    if idx < 0 or idx >= len(subs):
        await _zalo_send(chat_id, f"Số không hợp lệ (1-{len(subs)}).")
        return
    sub = subs[idx]
    sh.set_state(state_key, {
        **state,
        "step": "zalo_manage_sub_menu",
        "edit_sub_key": sub["key"],
        "edit_sub_label": sub["label"],
    })
    await _zalo_send(
        chat_id,
        f"{sub['label']}\n"
        f"(sub of {state.get('edit_bucket_name', '?')})\n\n"
        "Reply:\n"
        "1. Đổi tên\n"
        "2. Xóa\n"
        '3. Back',
    )


async def _zalo_manage_handle_sub_menu(chat_id: str, text: str, state: dict, state_key: str):
    if text == "1":
        sh.set_state(state_key, {**state, "step": "zalo_manage_sub_rename"})
        await _zalo_send(chat_id, f"Tên hiện tại: {state.get('edit_sub_label', '?')}\nNhập tên mới:")
        return
    if text == "2":
        bucket_id = state.get("edit_bucket_id", "")
        sub_key = state.get("edit_sub_key", "")
        old_label = state.get("edit_sub_label", sub_key)
        if sh.soft_delete_sub_category(bucket_id, sub_key):
            await _zalo_send(chat_id, f"Đã xóa sub-category: {old_label}")
        else:
            await _zalo_send(chat_id, "Sub-category không tồn tại.")
        await _zalo_manage_show_subs(chat_id, state, state_key)
        return
    if text == "3":
        await _zalo_manage_show_subs(chat_id, state, state_key)
        return
    await _zalo_send(chat_id, "Reply 1, 2 hoặc 3.")


async def _zalo_manage_handle_sub_rename(chat_id: str, text: str, state: dict, state_key: str):
    new_label = text.strip()
    if not new_label:
        await _zalo_send(chat_id, "Tên sub-category không được trống.")
        return
    bucket_id = state.get("edit_bucket_id", "")
    sub_key = state.get("edit_sub_key", "")
    old_label = state.get("edit_sub_label", sub_key)
    if sh.update_sub_category(bucket_id, sub_key, new_label):
        await _zalo_send(chat_id, f"Đã đổi tên: {old_label} → {new_label}")
    else:
        await _zalo_send(chat_id, "Sub-category không tồn tại.")
    await _zalo_manage_show_subs(chat_id, state, state_key)


async def _zalo_manage_handle_edit_amount(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle budget amount edit."""
    amount = parse_budget_amount(text)
    if amount is None:
        await messenger.send_text("Số không hợp lệ. Thử lại (vd 3000000, 3tr, 500k hoặc 0).", channel="zalo", recipient_id=chat_id)
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    name = state.get("edit_bucket_name", "?")

    sh.update_bucket(month_key, bucket_id, {"allocated": amount})
    label = sh.fmt_amount(amount) if amount > 0 else "tracking-only"
    await messenger.send_text(
        f"Đã update: {name} → {label}",
        channel="zalo", recipient_id=chat_id,
    )
    await _zalo_cmd_manage(chat_id, state_key)


async def _zalo_manage_handle_edit_daily_cap(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle daily-cap edit for the Daily Spending bucket (Zalo).

    0 = turn the cap off (/today switches to tracking mode, recap stops)."""
    amount = parse_budget_amount(text)
    if amount is None:
        await messenger.send_text(
            "Số không hợp lệ. Thử lại (vd 100k, 150000 hoặc 0 để tắt).",
            channel="zalo", recipient_id=chat_id,
        )
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    name = state.get("edit_bucket_name", "?")

    sh.update_bucket(month_key, bucket_id, {"daily_cap": amount or None})
    if amount > 0:
        msg = f"Daily cap: {name} → {sh.fmt_amount(amount)}/ngày.\n/today sẽ so với cap này."
    else:
        msg = f"Đã tắt daily cap cho {name}. /today chỉ hiển thị tổng đã tiêu."
    await messenger.send_text(msg, channel="zalo", recipient_id=chat_id)
    await _zalo_cmd_manage(chat_id, state_key)


async def _zalo_manage_handle_rename(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle category rename."""
    new_name = text.strip()
    if not new_name:
        await messenger.send_text("Tên không được trống.", channel="zalo", recipient_id=chat_id)
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    old_name = state.get("edit_bucket_name", "?")

    sh.update_bucket(month_key, bucket_id, {"name": new_name})
    await messenger.send_text(
        f"Đã đổi tên: {old_name} → {new_name}",
        channel="zalo", recipient_id=chat_id,
    )
    await _zalo_cmd_manage(chat_id, state_key)


async def _zalo_manage_handle_confirm_delete(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle delete confirmation."""
    if text.lower() in ("yes", "y", "có", "co"):
        month_key = state.get("month_key", "")
        bucket_id = state.get("edit_bucket_id", "")
        name = state.get("edit_bucket_name", "?")
        sh.soft_delete_bucket(month_key, bucket_id)
        await messenger.send_text(f"Đã xóa: {name}", channel="zalo", recipient_id=chat_id)
        await _zalo_cmd_manage(chat_id, state_key)
    else:
        await messenger.send_text("Đã hủy.", channel="zalo", recipient_id=chat_id)
        await _zalo_cmd_manage(chat_id, state_key)


async def _zalo_manage_handle_add_name(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle new category name input."""
    import unicodedata
    name = text.strip()
    if not name:
        await messenger.send_text("Tên không được trống.", channel="zalo", recipient_id=chat_id)
        return

    nid = unicodedata.normalize("NFD", name.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)
    nid = re.sub(r"[^\w\s]", "", nid)
    nid = re.sub(r"\s+", "_", nid.strip())
    nid = re.sub(r"[^a-z0-9_]", "", nid)
    if not nid:
        nid = "custom"

    month_key = state.get("month_key", "")
    existing = sh.get_active_buckets(month_key, force_refresh=True)
    if any(b["id"] == nid for b in existing):
        await messenger.send_text(
            f"Category {name} đã tồn tại! Nhập tên khác.",
            channel="zalo", recipient_id=chat_id,
        )
        return

    sh.set_state(state_key, {
        **state,
        "step": "zalo_manage_add_amount",
        "new_cat_name": name,
        "new_cat_id": nid,
    })
    await messenger.send_text(
        f"{name} — Nhập budget (số tiền):\n"
        "(0 = tracking-only, không đặt budget)",
        channel="zalo", recipient_id=chat_id,
    )


async def _zalo_manage_handle_add_amount(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle new category amount input. Invalid input is rejected —
    previously garbage silently became 0 (tracking-only)."""
    amount = parse_budget_amount(text)
    if amount is None:
        await messenger.send_text("Số không hợp lệ. Thử lại (vd 2000000, 2tr, 500k hoặc 0).", channel="zalo", recipient_id=chat_id)
        return

    month_key = state.get("month_key", "")
    name = state.get("new_cat_name", "")
    nid = state.get("new_cat_id", "")

    new_bucket = {"id": nid, "name": name, "allocated": amount, "daily_cap": None}
    sh.write_budget_row(month_key, new_bucket)
    sh.invalidate_buckets_cache()

    label = sh.fmt_amount(amount) if amount > 0 else "tracking-only"
    await messenger.send_text(
        f"Đã thêm: {name} — {label}",
        channel="zalo", recipient_id=chat_id,
    )
    await _zalo_cmd_manage(chat_id, state_key)


# ─── Zalo: /allocate ──────────────────────────────────────────


async def _zalo_cmd_allocate(chat_id: str, state_key: str):
    """Show budget summary with per-bucket edit options."""
    from datetime import datetime
    import pytz
    from config import TIMEZONE

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key, force_refresh=True)

    if not buckets:
        async with sh.bootstrap_lock:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_buckets_from_previous_month(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_default_categories(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)

    lines = [f"Budget — {month_key}\n"]
    total = 0
    for i, b in enumerate(buckets, 1):
        alloc = b.get("allocated", 0)
        if alloc > 0:
            lines.append(f"{i}. {b['name']}   {sh.fmt_amount(alloc)}")
            total += alloc
        else:
            lines.append(f"{i}. {b['name']}   tracking")
    lines.append(f"─────────────────────\nTotal: {sh.fmt_amount(total)}")
    lines.append("\nReply số để sửa budget category đó:")
    lines.append("- /cancel để thoát")

    sh.set_state(state_key, {"step": "zalo_allocate_menu", "month_key": month_key})
    await messenger.send_text("\n".join(lines), channel="zalo", recipient_id=chat_id)


async def _zalo_allocate_handle_menu(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle allocate menu: pick bucket by number to edit."""
    month_key = state.get("month_key", "")

    if not text.isdigit():
        await messenger.send_text("Reply số thứ tự category.", channel="zalo", recipient_id=chat_id)
        return

    buckets = sh.get_active_buckets(month_key, force_refresh=True)
    idx = int(text) - 1
    if idx < 0 or idx >= len(buckets):
        await messenger.send_text(
            f"Số không hợp lệ (1-{len(buckets)}).",
            channel="zalo", recipient_id=chat_id,
        )
        return

    bucket = buckets[idx]
    current = sh.fmt_amount(bucket.get("allocated", 0)) if bucket.get("allocated", 0) > 0 else "tracking"
    sh.set_state(state_key, {
        **state,
        "step": "zalo_allocate_edit_amount",
        "edit_bucket_id": bucket["id"],
        "edit_bucket_name": bucket["name"],
    })
    await messenger.send_text(
        f"{bucket['name']} — hiện tại: {current}\n"
        f"Nhập limit mới cho {month_key}:\n"
        "(0 = tracking-only)",
        channel="zalo", recipient_id=chat_id,
    )


async def _zalo_allocate_handle_edit_amount(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle budget amount edit from allocate flow."""
    amount = parse_budget_amount(text)
    if amount is None:
        await messenger.send_text("Số không hợp lệ. Thử lại (vd 3000000, 3tr, 500k hoặc 0).", channel="zalo", recipient_id=chat_id)
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    name = state.get("edit_bucket_name", "?")

    # Find bucket and update
    buckets = sh.get_active_buckets(month_key)
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if not bucket:
        await messenger.send_text("Bucket không tồn tại.", channel="zalo", recipient_id=chat_id)
        sh.clear_state(state_key)
        return

    bucket["allocated"] = amount
    sh.write_budget_row(month_key, bucket)
    sh.invalidate_buckets_cache()

    label = sh.fmt_amount(amount) if amount > 0 else "tracking-only"
    await messenger.send_text(
        f"Đã update: {name} → {label}",
        channel="zalo", recipient_id=chat_id,
    )
    await _zalo_cmd_allocate(chat_id, state_key)


# ─── Zalo keyword management ─────────────────────────────────


async def _zalo_kw_show_list(chat_id: str, state_key: str):
    """Show keyword rules list with numbered menu options."""
    rules = sh.get_keyword_rules(force_refresh=True)

    if not rules:
        sh.set_state(state_key, {"step": "zalo_keywords"})
        await messenger.send_text(
            "🔑 Keyword Rules\n\n"
            "Chưa có rule nào.\n\n"
            "Khi giao dịch có description chứa keyword, "
            "bot sẽ tự động phân loại.\n\n"
            "VD: highland → Coffee, winmart → Food\n\n"
            "Reply:\n"
            "- \"add\" để thêm rule mới\n"
            "- /cancel để thoát",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    lines = ["🔑 Keyword Rules\n"]
    for i, r in enumerate(rules, 1):
        bucket_name = sh.bucket_label(r["bucket_id"])
        sub = f" · {r['sub_label']}" if r.get("sub_label") else ""
        lines.append(f"{i}. {r['keyword']} → {bucket_name}{sub}")

    lines.append("\nReply:")
    lines.append('- "add" để thêm rule mới')
    lines.append('- Số (VD: "3") để sửa/xóa rule đó')
    lines.append("- /cancel để thoát")

    sh.set_state(state_key, {"step": "zalo_keywords"})
    await messenger.send_text(
        "\n".join(lines),
        channel="zalo",
        recipient_id=chat_id,
    )


async def _zalo_kw_handle_menu(chat_id: str, text: str, state: dict, state_key: str):
    """Handle input from the keyword list menu."""
    if text.lower() == "add":
        sh.set_state(state_key, {**state, "step": "zalo_kw_add_keyword"})
        await messenger.send_text(
            "Nhập keyword (hoặc nhiều keyword cách nhau dấu phẩy):\n\n"
            "VD: highland\n"
            "VD: grab, gojek, baemin",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    if text.isdigit():
        rules = sh.get_keyword_rules(force_refresh=True)
        idx = int(text) - 1
        if 0 <= idx < len(rules):
            rule = rules[idx]
            bucket_name = sh.bucket_label(rule["bucket_id"])
            sh.set_state(state_key, {
                **state,
                "step": "zalo_kw_edit_menu",
                "editing_row": rule["row_num"],
                "editing_keyword": rule["keyword"],
                "editing_bucket": rule["bucket_id"],
            })
            await messenger.send_text(
                f"🔑 Rule: {rule['keyword']} → {bucket_name}\n\n"
                "Reply:\n"
                '1. Đổi keyword\n'
                '2. Đổi category\n'
                '3. Xóa rule\n'
                "- /cancel để thoát",
                channel="zalo",
                recipient_id=chat_id,
            )
            return
        else:
            await messenger.send_text(
                f"Số không hợp lệ (1-{len(rules)}).",
                channel="zalo",
                recipient_id=chat_id,
            )
            return

    await messenger.send_text(
        'Reply "add" hoặc số thứ tự rule.',
        channel="zalo",
        recipient_id=chat_id,
    )


async def _zalo_kw_handle_add_keyword(
    chat_id: str, text: str, state: dict, state_key: str
):
    """User typed keyword(s) for a new rule. Parse and ask for category."""
    tokens = [t.strip() for t in re.split(r"[,;]+", text)]
    keywords: list[str] = []
    for t in tokens:
        if not t:
            continue
        if len(t) > 60:
            await messenger.send_text(
                f"Keyword quá dài (>60 ký tự): {t}\nThử lại.",
                channel="zalo",
                recipient_id=chat_id,
            )
            return
        norm = sh._normalize_for_match(t)
        if norm and norm not in keywords:
            keywords.append(norm)

    if not keywords:
        await messenger.send_text(
            "Keyword không hợp lệ. Thử lại.",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    from datetime import datetime
    import pytz
    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        await messenger.send_text(
            "Chưa có category nào. Tạo category bằng /manage trước.",
            channel="zalo",
            recipient_id=chat_id,
        )
        sh.set_state(state_key, {"step": "zalo_keywords"})
        return

    sh.set_state(state_key, {
        "step": "zalo_kw_add_pick_cat",
        "pending_keywords": keywords,
        "buckets": [{"id": b["id"], "name": b["name"]} for b in buckets],
    })

    preview = ", ".join(keywords)
    lines = [f"Keyword: {preview}\n\nChọn category:"]
    for i, b in enumerate(buckets, 1):
        lines.append(f"{i}. {b['name']}")

    await messenger.send_text(
        "\n".join(lines),
        channel="zalo",
        recipient_id=chat_id,
    )


async def _zalo_kw_handle_add_pick_cat(
    chat_id: str, text: str, state: dict, state_key: str
):
    """User picked a category number for the new keyword(s)."""
    buckets = state.get("buckets", [])
    keywords = state.get("pending_keywords", [])

    if not text.isdigit():
        await messenger.send_text(
            f"Reply bằng số (1-{len(buckets)}).",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    idx = int(text) - 1
    if idx < 0 or idx >= len(buckets):
        await messenger.send_text(
            f"Số không hợp lệ (1-{len(buckets)}).",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    bucket = buckets[idx]
    added, skipped = [], []
    for kw in keywords:
        if sh.add_keyword_rule(kw, bucket["id"], sub_label=""):
            added.append(kw)
        else:
            skipped.append(kw)

    parts = []
    if added:
        parts.append(f"✅ Đã thêm {len(added)} rule → {bucket['name']}:")
        for k in added:
            parts.append(f"  • {k}")
    if skipped:
        parts.append(f"⚠️ {len(skipped)} rule đã tồn tại:")
        for k in skipped:
            parts.append(f"  • {k}")

    await messenger.send_text(
        "\n".join(parts),
        channel="zalo",
        recipient_id=chat_id,
    )
    await _zalo_kw_show_list(chat_id, state_key)


async def _zalo_kw_handle_edit_menu(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle the per-rule edit menu (1=rename, 2=change cat, 3=delete)."""
    row_num = state.get("editing_row")

    if text == "1":  # Đổi keyword
        sh.set_state(state_key, {**state, "step": "zalo_kw_edit_keyword"})
        await messenger.send_text(
            f"Keyword hiện tại: {state.get('editing_keyword', '?')}\n\n"
            "Nhập keyword mới (1 keyword duy nhất):",
            channel="zalo",
            recipient_id=chat_id,
        )
    elif text == "2":  # Đổi category
        from datetime import datetime
        import pytz
        tz = pytz.timezone(TIMEZONE)
        month_key = sh.fmt_month(datetime.now(tz))
        buckets = sh.get_active_buckets(month_key)
        if not buckets:
            await messenger.send_text(
                "Chưa có category.",
                channel="zalo",
                recipient_id=chat_id,
            )
            return
        sh.set_state(state_key, {
            **state,
            "step": "zalo_kw_edit_cat",
            "buckets": [{"id": b["id"], "name": b["name"]} for b in buckets],
        })
        current = sh.bucket_label(state.get("editing_bucket", ""))
        lines = [f"Keyword: {state.get('editing_keyword', '?')}"]
        lines.append(f"Hiện tại: {current}\n")
        lines.append("Chọn category mới:")
        for i, b in enumerate(buckets, 1):
            lines.append(f"{i}. {b['name']}")
        await messenger.send_text(
            "\n".join(lines),
            channel="zalo",
            recipient_id=chat_id,
        )
    elif text == "3":  # Xóa
        sh.set_state(state_key, {**state, "step": "zalo_kw_confirm_delete"})
        keyword = state.get("editing_keyword", "?")
        bucket_name = sh.bucket_label(state.get("editing_bucket", ""))
        await messenger.send_text(
            f"⚠️ Xóa rule: {keyword} → {bucket_name}?\n\n"
            'Reply "yes" để xác nhận, hoặc bất kỳ để hủy.',
            channel="zalo",
            recipient_id=chat_id,
        )
    else:
        await messenger.send_text(
            "Reply 1, 2 hoặc 3.",
            channel="zalo",
            recipient_id=chat_id,
        )


async def _zalo_kw_handle_edit_keyword(
    chat_id: str, text: str, state: dict, state_key: str
):
    """User typed a new keyword for an existing rule."""
    row_num = state.get("editing_row")
    if not row_num:
        await messenger.send_text("Hết phiên. Gửi /keywords.", channel="zalo", recipient_id=chat_id)
        sh.clear_state(state_key)
        return

    if re.search(r"[,;]", text):
        await messenger.send_text(
            "Chỉ nhận 1 keyword khi sửa. Muốn thêm nhiều → xóa rule này rồi add mới.",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    if len(text) > 60:
        await messenger.send_text("Keyword quá dài (>60 ký tự).", channel="zalo", recipient_id=chat_id)
        return

    new_norm = sh._normalize_for_match(text)
    if not new_norm:
        await messenger.send_text("Keyword không hợp lệ.", channel="zalo", recipient_id=chat_id)
        return

    old_keyword = state.get("editing_keyword", "")
    if new_norm == old_keyword:
        await messenger.send_text("Keyword không đổi.", channel="zalo", recipient_id=chat_id)
        await _zalo_kw_show_list(chat_id, state_key)
        return

    ok = sh.update_keyword_rule(row_num, keyword=new_norm)
    if ok:
        bucket_name = sh.bucket_label(state.get("editing_bucket", ""))
        await messenger.send_text(
            f"✅ Đã đổi: {old_keyword} → {new_norm} (category: {bucket_name})",
            channel="zalo",
            recipient_id=chat_id,
        )
    else:
        await messenger.send_text("Lỗi khi cập nhật.", channel="zalo", recipient_id=chat_id)
    await _zalo_kw_show_list(chat_id, state_key)


async def _zalo_kw_handle_edit_cat(
    chat_id: str, text: str, state: dict, state_key: str
):
    """User picked a new category number for an existing rule."""
    buckets = state.get("buckets", [])
    row_num = state.get("editing_row")

    if not text.isdigit():
        await messenger.send_text(
            f"Reply bằng số (1-{len(buckets)}).",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    idx = int(text) - 1
    if idx < 0 or idx >= len(buckets):
        await messenger.send_text(
            f"Số không hợp lệ (1-{len(buckets)}).",
            channel="zalo",
            recipient_id=chat_id,
        )
        return

    new_bucket = buckets[idx]
    old_bucket_id = state.get("editing_bucket", "")
    keyword = state.get("editing_keyword", "?")

    if new_bucket["id"] == old_bucket_id:
        await messenger.send_text("Category không đổi.", channel="zalo", recipient_id=chat_id)
        await _zalo_kw_show_list(chat_id, state_key)
        return

    ok = sh.update_keyword_rule(row_num, bucket_id=new_bucket["id"])
    if ok:
        old_name = sh.bucket_label(old_bucket_id)
        await messenger.send_text(
            f"✅ Đã đổi category cho {keyword}:\n{old_name} → {new_bucket['name']}",
            channel="zalo",
            recipient_id=chat_id,
        )
    else:
        await messenger.send_text("Lỗi khi cập nhật.", channel="zalo", recipient_id=chat_id)
    await _zalo_kw_show_list(chat_id, state_key)


async def _zalo_kw_handle_confirm_delete(
    chat_id: str, text: str, state: dict, state_key: str
):
    """Handle delete confirmation (yes/no)."""
    row_num = state.get("editing_row")
    keyword = state.get("editing_keyword", "?")

    if text.lower() in ("yes", "y", "có", "co"):
        sh.soft_delete_keyword_rule(row_num)
        bucket_name = sh.bucket_label(state.get("editing_bucket", ""))
        await messenger.send_text(
            f"🗑️ Đã xóa: {keyword} → {bucket_name}",
            channel="zalo",
            recipient_id=chat_id,
        )
        await _zalo_kw_show_list(chat_id, state_key)
    else:
        await messenger.send_text("Đã hủy.", channel="zalo", recipient_id=chat_id)
        await _zalo_kw_show_list(chat_id, state_key)


# ─── Scheduled triggers (call via cron on VPS) ───────────────


async def run_weekly_summary():
    """Cron: Sunday 8 PM — send weekly spending summary to both channels."""
    from handlers.report import _scan_period, _render_category_lens
    data = _scan_period("w")
    msg = _render_category_lens(data)
    await tg.send_text(f"📅 *Weekly Summary*\n\n{msg}")
    # Zalo fan-out (best-effort)
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            await messenger.send_text(
                f"📅 Weekly Summary\n\n{msg}",
                channel="zalo",
                recipient_id=ZALO_CHAT_ID,
            )
        except Exception as e:
            print(f"[cron] Zalo weekly summary failed (non-fatal): {e}")


async def run_monthly_report():
    """Cron: last day of month — send monthly spending report to both channels."""
    from datetime import datetime
    import pytz
    import calendar

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    # Only run on the actual last day of the month
    last_day = calendar.monthrange(now.year, now.month)[1]
    if now.day != last_day:
        return

    from handlers.report import _scan_period, _render_category_lens
    data = _scan_period("m")
    msg = _render_category_lens(data)
    await tg.send_text(f"📊 *Monthly Report*\n\n{msg}")
    # Zalo fan-out (best-effort)
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            await messenger.send_text(
                f"📊 Monthly Report\n\n{msg}",
                channel="zalo",
                recipient_id=ZALO_CHAT_ID,
            )
        except Exception as e:
            print(f"[cron] Zalo monthly report failed (non-fatal): {e}")


async def _monthly_allocation_with_zalo():
    """Cron wrapper: triggers Telegram allocation wizard + Zalo notification."""
    await start_monthly_allocation(from_cron=True)
    # Zalo: read-only heads-up (full wizard is Telegram-only)
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            from datetime import datetime
            import pytz
            tz = pytz.timezone(TIMEZONE)
            month_key = sh.fmt_month(datetime.now(tz))
            await messenger.send_text(
                f"💰 Tháng mới ({month_key}) — đã đến lúc set budget!\n\n"
                "Dùng /allocate trên Zalo để xem và chỉnh budget.\n"
                "⏰ Không set trong 1h → tự động giữ budget tháng trước.",
                channel="zalo",
                recipient_id=ZALO_CHAT_ID,
            )
        except Exception as e:
            print(f"[cron] Zalo allocation prompt failed (non-fatal): {e}")


def _cron_authorized(secret: str) -> bool:
    """When CRON_SECRET is set, /trigger/* callers must pass ?secret=<value>.
    Unset → legacy open behavior (warned at startup)."""
    if not CRON_SECRET:
        return True
    return hmac_mod.compare_digest(secret or "", CRON_SECRET)


@app.post("/trigger/weekly")
async def trigger_weekly(secret: str = Query(default="")):
    if not _cron_authorized(secret):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(run_weekly_summary())
    return {"ok": True}


@app.post("/trigger/monthly-report")
async def trigger_monthly_report(secret: str = Query(default="")):
    if not _cron_authorized(secret):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(run_monthly_report())
    return {"ok": True}


@app.post("/trigger/monthly-allocation")
async def trigger_monthly_allocation(secret: str = Query(default="")):
    if not _cron_authorized(secret):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(_monthly_allocation_with_zalo())
    return {"ok": True}


@app.post("/trigger/auto-alloc-fallback")
async def trigger_auto_alloc_fallback(secret: str = Query(default="")):
    """Cron fires this 1h after monthly-allocation prompt.
    If the current month still has no buckets, auto-copy previous month's budget."""
    if not _cron_authorized(secret):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(_auto_alloc_fallback())
    return {"ok": True}


async def _auto_alloc_fallback():
    from datetime import datetime
    import pytz
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)

    # Already set — nothing to do
    current = sh.get_active_buckets(month_key, force_refresh=True)
    if current:
        return

    prev_month = datetime(now.year if now.month > 1 else now.year - 1,
                          now.month - 1 if now.month > 1 else 12, 1, tzinfo=tz)
    prev_key = sh.fmt_month(prev_month)
    prev_buckets = sh.get_active_buckets(prev_key)

    zalo_msg = ""
    if not prev_buckets:
        # No previous budget — bootstrap defaults in tracking mode
        async with sh.bootstrap_lock:
            sh.bootstrap_default_categories(month_key)
        await tg.send_text(
            f"⏰ Hết 1h chờ set budget {month_key} — "
            f"không có budget tháng trước để copy nên đã tạo categories ở tracking mode.\n"
            f"Dùng /allocate để đặt budget bất cứ lúc nào."
        )
        zalo_msg = (
            f"⏰ Hết 1h chờ set budget {month_key} — "
            f"không có budget tháng trước nên đã tạo categories ở tracking mode.\n"
            f"Dùng /allocate để chỉnh."
        )
    else:
        for b in prev_buckets:
            sh.write_budget_row(month_key, b)
        sh.invalidate_buckets_cache()

        total = sum(b.get("allocated", 0) or 0 for b in prev_buckets)
        await tg.send_text(
            f"⏰ *Auto budget — {month_key}*\n\n"
            f"Hết 1h chờ phản hồi — đã tự động giữ nguyên budget tháng {prev_key} "
            f"(*{sh.fmt_amount(total)}*).\n\n"
            f"Muốn chỉnh? Dùng /allocate."
        )
        zalo_msg = (
            f"⏰ Tự động giữ budget tháng {prev_key} cho {month_key}.\n"
            f"Dùng /allocate để chỉnh."
        )

    # Also notify Zalo
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            await messenger.send_text(
                zalo_msg,
                channel="zalo",
                recipient_id=ZALO_CHAT_ID,
            )
        except Exception as e:
            print(f"[cron] Zalo auto-alloc fallback failed (non-fatal): {e}")

    sh.clear_state(CHAT_ID)


@app.post("/trigger/daily-recap")
async def trigger_daily_recap(secret: str = Query(default="")):
    if not _cron_authorized(secret):
        return JSONResponse({"error": True, "message": "invalid cron secret"}, status_code=403)
    asyncio.create_task(send_daily_recap())
    return {"ok": True}



# ─── Health check ─────────────────────────────────────────────
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def health():
    return {"status": "ok", "bot": "Financial Tracking Bot"}


# ─── SePay webhook v2 (per-tenant via URL token) ─────────────
if _SAAS_AVAILABLE:
    @app.post("/webhooks/sepay/{token}")
    async def webhook_sepay_v2(token: str, request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": True})
        return JSONResponse(await handle_sepay_v2(token, body))


# ─── Dashboard serve ─────────────────────────────────────────
@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    if not DASHBOARD_HTML.exists():
        return JSONResponse({"error": "dashboard.html not found"}, status_code=404)
    return FileResponse(
        DASHBOARD_HTML,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=30"},
    )


@app.get("/dashboard.md", include_in_schema=False)
async def serve_dashboard_md():
    if not DASHBOARD_MD.exists():
        return JSONResponse({"error": "dashboard.md not found"}, status_code=404)
    return FileResponse(
        DASHBOARD_MD,
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=30"},
    )


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
    except Exception as e:
        import traceback
        print("ERROR:", traceback.format_exc())
        await tg.send_text(f"⚠️ Bot gặp lỗi: `{e}`")


# Valid Telegram callback prefixes & their minimum part counts. Anything
# else (malformed / forged callback_data) is dropped before dispatch.
_CALLBACK_MIN_PARTS = {
    "p": 2, "s": 2, "al": 2, "recat": 2, "mg": 2, "kw": 2,
    "cb": 2, "acc": 2, "asg": 2, "rpt": 2, "lang": 2, "lr": 2,
}


def _validate_callback(cb: dict) -> tuple[str, list[str], int] | None:
    """Validate callback_query shape → (prefix, parts, message_id) or None."""
    data = cb.get("data") or ""
    message = cb.get("message")
    if not data or not isinstance(message, dict) or "message_id" not in message:
        return None
    parts = data.split("_")
    prefix = parts[0]
    if prefix not in _CALLBACK_MIN_PARTS or len(parts) < _CALLBACK_MIN_PARTS[prefix]:
        return None
    return prefix, parts, message["message_id"]


async def _handle_callback(cb: dict):
    callback_id = cb.get("id")
    if not callback_id:
        print("[callback] rejected: missing callback id")
        return
    await tg.answer_callback(callback_id)

    # Only the configured owner may drive the bot — /webhook has no Telegram
    # auth unless TELEGRAM_WEBHOOK_SECRET is set, so this check is the last line.
    cb_chat = cb.get("message", {}).get("chat", {}).get("id")
    if str(cb_chat) != str(CHAT_ID):
        print(f"[callback] rejected: chat_id={cb_chat} != CHAT_ID")
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
    elif prefix == "lang":
        await handle_lang_callback(parts, message_id)
    elif prefix == "lr":
        await handle_learn_rule(parts, message_id)


async def _handle_message(message: dict):
    # Only the configured owner may drive the bot (see _handle_callback note).
    msg_chat = message.get("chat", {}).get("id")
    if str(msg_chat) != str(CHAT_ID):
        print(f"[message] rejected: chat_id={msg_chat} != CHAT_ID")
        return

    if message.get("from", {}).get("is_bot"):
        return                                  # ignore bot echoes

    text  = (message.get("text") or "").strip()
    state = sh.get_state(CHAT_ID) or {}

    # Commands take priority — clear any pending multi-step state so the user
    # doesn't get stuck (e.g. typing /report while in await_manage_amount).
    # The pending_tx_queue survives the clear so queued transactions aren't lost.
    if text.startswith("/"):
        pending = state.get("pending_tx_queue") or []
        sh.clear_state(CHAT_ID)
        if pending:
            preserved = sh.get_state(CHAT_ID) or {}
            sh.set_state(CHAT_ID, {**preserved, "pending_tx_queue": pending})
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
    elif step == "await_manage_daily_cap":
        await handle_manage_daily_cap(text, state)
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
    elif step == "await_credit_limit":
        await handle_credit_limit(text, state)
    elif step == "await_credit_outstanding":
        await handle_credit_outstanding(text, state)
    elif step == "await_credit_statement":
        await handle_credit_statement(text, state)
    elif step == "await_credit_due":
        await handle_credit_due(text, state)
    else:
        await _tg_cmd_help()


async def _tg_cmd_transfer(text: str):
    """Telegram /transfer <amount> <from> <to>"""
    parts = text.strip().split()
    if len(parts) < 4:
        await tg.send_text("Usage: `/transfer <amount> <from> <to>`\nVd: `/transfer 1000000 tcb_main cake_main`")
        return
    amount = _parse_money(parts[1])
    if amount is None or amount <= 0:
        await tg.send_text("⚠️ Số tiền không hợp lệ.")
        return
    from_id, to_id = parts[2].strip(), parts[3].strip()
    if from_id == to_id:
        await tg.send_text("⚠️ from và to phải khác account.")
        return

    from_acc = sh.find_account_by_id(from_id)
    to_acc = sh.find_account_by_id(to_id)
    if not from_acc:
        await tg.send_text(f"⚠️ Account `{from_id}` không tồn tại. Gửi /accounts để xem list.")
        return
    if not to_acc:
        await tg.send_text(f"⚠️ Account `{to_id}` không tồn tại.")
        return
    if from_acc["currency"] != to_acc["currency"]:
        await tg.send_text(f"⚠️ Currency mismatch: {from_acc['currency']} → {to_acc['currency']}.")
        return

    iso, month_key, ts = _zalo_now_for_tx()
    row_num, status = sh.append_transfer(
        from_account_id=from_id, to_account_id=to_id,
        amount=amount, currency=from_acc["currency"],
        description=f"transfer {from_id} → {to_id}",
        tx_date=iso, ref_code=f"TRANSFER_{from_id}_{to_id}_{ts}",
        month_key=month_key,
    )
    if status != "ok":
        await tg.send_text(f"⚠️ {status}")
        return

    sh.invalidate_accounts_cache()
    from_after = sh.find_account_by_id(from_id)
    to_after = sh.find_account_by_id(to_id)
    cur = from_acc["currency"]
    await tg.send_text(
        f"✅ *Transfer ghi nhận*\n"
        f"{from_acc['name']} → {to_acc['name']}\n"
        f"Số tiền: *{sh.fmt_amount(amount, cur)}*\n\n"
        f"Số dư mới:\n"
        f"{from_acc['name']}: {sh.fmt_amount(from_after['running_balance'], cur)}\n"
        f"{to_acc['name']}: {sh.fmt_amount(to_after['running_balance'], cur)}"
    )


async def _tg_cmd_cc_pay(text: str):
    """Telegram /cc pay <amount> <cc_id> or /cc pay <amount> <bank_id> <cc_id>"""
    parts = text.strip().split()
    if len(parts) not in (4, 5) or parts[1].lower() != "pay":
        await tg.send_text(
            "Usage:\n"
            "`/cc pay <amount> <cc_id>` — trả từ nguồn ngoài\n"
            "`/cc pay <amount> <bank_id> <cc_id>` — trả từ bank account"
        )
        return
    amount = _parse_money(parts[2])
    if amount is None or amount <= 0:
        await tg.send_text("⚠️ Số tiền không hợp lệ.")
        return

    iso, month_key, ts = _zalo_now_for_tx()
    if len(parts) == 4:
        cc_id = parts[3].strip()
        cc_acc = sh.find_account_by_id(cc_id)
        if not cc_acc:
            await tg.send_text(f"⚠️ CC `{cc_id}` không tồn tại.")
            return
        if cc_acc["type"] != "credit":
            await tg.send_text(f"⚠️ `{cc_id}` không phải credit card (type={cc_acc['type']}).")
            return

        row_num, status = sh.append_cc_payment_external(
            cc_account_id=cc_id, amount=amount, currency=cc_acc["currency"],
            description=f"cc payment external → {cc_id}",
            tx_date=iso, ref_code=f"CCPAYEXT_{cc_id}_{ts}",
            month_key=month_key,
        )
        if status != "ok":
            await tg.send_text(f"⚠️ {status}")
            return
        sh.invalidate_accounts_cache()
        cc_after = sh.find_account_by_id(cc_id)
        cur = cc_acc["currency"]
        await tg.send_text(
            f"✅ *CC payment ghi nhận (external)*\n"
            f"→ {cc_acc['name']}\n"
            f"Số tiền: *{sh.fmt_amount(amount, cur)}*\n\n"
            f"{cc_acc['name']} dư nợ: {sh.fmt_amount(cc_after['outstanding_balance'], cur)}"
        )
        return

    bank_id, cc_id = parts[3].strip(), parts[4].strip()
    bank_acc = sh.find_account_by_id(bank_id)
    cc_acc = sh.find_account_by_id(cc_id)
    if not bank_acc:
        await tg.send_text(f"⚠️ Bank `{bank_id}` không tồn tại.")
        return
    if not cc_acc:
        await tg.send_text(f"⚠️ CC `{cc_id}` không tồn tại.")
        return
    if cc_acc["type"] != "credit":
        await tg.send_text(f"⚠️ `{cc_id}` không phải credit card (type={cc_acc['type']}).")
        return

    row_num, status = sh.append_cc_payment(
        bank_account_id=bank_id, cc_account_id=cc_id,
        amount=amount, currency=bank_acc["currency"],
        description=f"cc payment {bank_id} → {cc_id}",
        tx_date=iso, ref_code=f"CCPAY_{bank_id}_{cc_id}_{ts}",
        month_key=month_key,
    )
    if status != "ok":
        await tg.send_text(f"⚠️ {status}")
        return

    sh.invalidate_accounts_cache()
    bank_after = sh.find_account_by_id(bank_id)
    cc_after = sh.find_account_by_id(cc_id)
    cur = bank_acc["currency"]
    await tg.send_text(
        f"✅ *CC payment ghi nhận*\n"
        f"{bank_acc['name']} → {cc_acc['name']}\n"
        f"Số tiền: *{sh.fmt_amount(amount, cur)}*\n\n"
        f"{bank_acc['name']}: {sh.fmt_amount(bank_after['running_balance'], cur)}\n"
        f"{cc_acc['name']} dư nợ: {sh.fmt_amount(cc_after['outstanding_balance'], cur)}"
    )


async def _tg_cmd_recat(text: str):
    """Telegram /recat — re-categorize a transaction.

    /recat            → show the 8 most recent outgoing tx as tap-to-fix buttons
    /recat <row_num>  → target a sheet row directly (power-user mode)
    """
    parts = text.strip().split()

    if len(parts) >= 2 and parts[1].isdigit():
        await _tg_recat_by_row(int(parts[1]))
        return

    # No args: show recent transactions for picking
    recent = sh.get_recent_transactions(limit=8)
    if not recent:
        await tg.send_text("📭 Không có giao dịch nào trong tháng này.")
        return

    msg = "↩️ *Re-categorize*\n\nChọn giao dịch muốn sửa phân loại:\n\n"
    buttons = []
    for tx in recent:
        desc = tx["description"][:25] + "…" if len(tx["description"]) > 25 else tx["description"]
        amount_str = sh.fmt_amount(tx["amount"], tx["currency"])
        status = f"→ {tx['bucket_name']}" if tx["bucket_name"] else "⚠️ chưa phân loại"
        msg += f"  -{amount_str} `{desc}` {status}\n"

        btn_label = f"↩️ -{amount_str} {desc}"
        if len(btn_label) > 55:
            btn_label = btn_label[:52] + "…"
        buttons.append([{"text": btn_label, "callback_data": f"recat_{tx['row_num']}"}])

    await tg.send_with_buttons(msg, buttons)


async def _tg_recat_by_row(row_num: int):
    """Re-categorize a specific transaction by sheet row number."""
    from datetime import datetime
    import pytz

    if row_num < 2:
        await tg.send_text(f"⚠️ Không tìm thấy transaction row {row_num}.")
        return
    row = sh.get_transaction_row(row_num)
    if not row:
        await tg.send_text(f"⚠️ Không tìm thấy transaction row {row_num}.")
        return

    tx_direction = "in" if (row[6] if len(row) > 6 else "") == "Tiền vào" else "out"
    if tx_direction == "in":
        await tg.send_text("ℹ️ Income hiện không cần category. Không recat.")
        return

    # Transfers & cc payments have their own 2-leg ledger — recategorizing
    # one as a bucket expense would corrupt account balances.
    ledger_type = (row[17] if len(row) > 17 else "").strip().lower()
    if ledger_type in ("transfer", "cc_payment"):
        await tg.send_text("ℹ️ Giao dịch chuyển khoản / trả thẻ có ledger riêng — không recat.")
        return

    amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
    description = row[5] if len(row) > 5 else ""
    currency = sh.row_currency(row)

    row_month = row[14] if len(row) > 14 else ""
    tz = pytz.timezone(TIMEZONE)
    month_key = row_month or sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)
    if not buckets:
        await tg.send_text(f"⚠️ Không có category active cho tháng {month_key}. Dùng /manage trước.")
        return

    sh.reset_transaction_row(row_num)

    prev_pending = (sh.get_state(CHAT_ID) or {}).get("pending_tx_queue") or []
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": row_num,
        "amount": amount, "currency": currency, "description": description,
        # Historical tx keep their own month: summaries + bucket status must
        # use the tx's month, not "now" (cross-month recat fix).
        "month_key": month_key,
        "tx_date": row[1] if len(row) > 1 else "",
        "pending_tx_queue": prev_pending,
    })

    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.send_with_buttons(
        f"↩️ *Re-categorize: -{sh.fmt_amount(amount, currency)}*\n"
        f"`{description}`\n\nKhoản này thuộc mục nào?",
        buttons,
    )


async def _handle_command(text: str):
    cmd = text.split()[0].lower()
    if   cmd == "/cancel":    await _tg_cmd_cancel()
    elif cmd == "/today":     await send_today_status()
    elif cmd == "/report":    await cmd_report(text)
    elif cmd == "/accounts":  await cmd_accounts(text)
    elif cmd == "/manage":    await start_manage()
    elif cmd == "/keywords":  await start_keywords()
    elif cmd == "/allocate":  await start_monthly_allocation()
    elif cmd == "/transfer":  await _tg_cmd_transfer(text)
    elif cmd == "/cc":        await _tg_cmd_cc_pay(text)
    elif cmd == "/recat":     await _tg_cmd_recat(text)
    elif cmd == "/pending":   await _tg_cmd_pending()
    elif cmd == "/lang":      await cmd_lang()
    elif cmd in ("/help", "/start"):
        await _tg_cmd_help()
    else:
        from i18n.core import t
        await tg.send_text(t("unknown_command"))


async def _tg_cmd_cancel():
    """/cancel — state was already cleared by _handle_message (queue preserved).
    Just tell the user, and remind them about queued transactions if any."""
    state = sh.get_state(CHAT_ID) or {}
    pending = state.get("pending_tx_queue") or []
    if pending:
        await tg.send_text(
            f"✅ Đã hủy thao tác hiện tại.\n\n"
            f"📌 Còn *{len(pending)} giao dịch* chờ phân loại — dùng /pending để xử lý."
        )
    else:
        await tg.send_text("✅ Đã hủy. Gửi /help để xem danh sách lệnh.")


async def _tg_cmd_pending():
    """/pending — categorize transactions queued while the user was mid-flow."""
    from datetime import datetime
    import pytz

    state = sh.get_state(CHAT_ID) or {}
    pending = state.get("pending_tx_queue") or []
    if not pending:
        await tg.send_text("✅ Không có giao dịch nào chờ phân loại.")
        return

    item = pending.pop(0)
    row_num = item["row_num"]
    amount = item.get("amount", 0)
    currency = item.get("currency", "VND")
    description = item.get("description", "")

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)
    if not buckets:
        await tg.send_text("⚠️ Chưa có category nào. Dùng /manage trước.")
        return

    remaining_note = ""
    if pending:
        remaining_note = f"\n📌 _Còn {len(pending)} giao dịch chờ sau giao dịch này._"

    sh.set_state(CHAT_ID, {
        "step": "await_parent",
        "row_num": row_num,
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": item.get("tx_direction", "out"),
        "tx_date": item.get("tx_date", ""),
        "pending_tx_queue": pending,  # preserve the remaining queue
    })

    frequent = sh.get_frequent_categories(3)
    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True,
                                      frequent_ids=frequent)
    await tg.send_with_buttons(
        f"💸 *-{sh.fmt_amount(amount, currency)}*\n"
        f"`{description}`\n\n"
        f"Khoản này thuộc mục nào? 🤔{remaining_note}",
        buttons,
    )


async def _tg_cmd_help():
    """/help, /start — full command list (follows /lang via i18n)."""
    from i18n.core import t
    await tg.send_text(t("help"))
