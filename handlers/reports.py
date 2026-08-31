"""handlers/reports.py — /today snapshot + scheduled daily recap.

Pre-Phase-2 this file also hosted /status (monthly category report),
/weekly (week summary), and /report (full monthly). Those were consolidated
into the unified /report (handlers/report.py, singular) with period
buttons and lens toggle. Only the today-snapshot + recap paths remain here.
"""
from datetime import datetime, date
import pytz

from config import CHAT_ID, TIMEZONE, DAILY_BUCKET_ID, ZALO_ENABLED, ZALO_CHAT_ID
import sheets as sh
import telegram_api as tg
import messenger


async def send_daily_recap():
    """End-of-day check-in. Called by cron at ~11 PM.
    Skip nếu daily bucket không có daily_cap (tracking-only no limit).
    """
    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)

    # Check daily_cap có thực sự được set không
    buckets = sh.get_active_buckets(month_key)
    daily_bkt = next((b for b in buckets if b["id"] == DAILY_BUCKET_ID), None)
    if not daily_bkt or not daily_bkt.get("daily_cap"):
        # Tracking mode không có cap → skip recap (tránh làm phiền user)
        return

    day = sh.get_daily_status(now)

    if day["spent"] == 0:
        msg = (
            f"🌙 *Kết thúc ngày — {now.strftime('%d/%m')}*\n\n"
            f"Hôm nay không tiêu đồng nào cho daily expenses. Sleep well. 💤"
        )
        await tg.send_text(msg)
        await _zalo_recap(msg)
        return

    pct = sh.calc_pct(day["spent"], day["cap"])

    if day["spent"] > day["cap"]:
        overspent = day["spent"] - day["cap"]
        msg = (
            f"🌙 *Kết thúc ngày — {now.strftime('%d/%m')}*\n\n"
            f"Daily spending: *{sh.fmt_amount(day['spent'])}* ({pct}% of limit)\n"
            f"Vượt *{sh.fmt_amount(overspent)}* so với cap ngày.\n\n"
            f"Muốn note lại lý do? Reply để bot ghi nhận."
        )
        await tg.send_text(msg)
        # Zalo gets recap WITH excuse prompt — same Y/text flow
        zalo_recap_msg = (
            f"Kết thúc ngày — {now.strftime('%d/%m')}\n\n"
            f"Daily spending: {sh.fmt_amount(day['spent'])} ({pct}% of limit)\n"
            f"Vượt {sh.fmt_amount(overspent)} so với cap ngày.\n\n"
            "Muốn note lại lý do? Reply để bot ghi nhận."
        )
        await _zalo_recap(zalo_recap_msg)
        if ZALO_ENABLED and ZALO_CHAT_ID:
            sh.set_state(f"zalo:{ZALO_CHAT_ID}", {
                "step": "await_zalo_daily_excuse",
                "date": now.strftime("%Y-%m-%d"),
                "overspent": overspent,
            })
        sh.set_state(CHAT_ID, {"step": "await_daily_excuse", "date": now.strftime("%Y-%m-%d"), "overspent": overspent})
    else:
        remaining = day["cap"] - day["spent"]
        msg = (
            f"🌙 *Kết thúc ngày — {now.strftime('%d/%m')}*\n\n"
            f"Daily spending: *{sh.fmt_amount(day['spent'])}* ({pct}% of limit)\n"
            f"Còn dư *{sh.fmt_amount(remaining)}*. ✨"
        )
        await tg.send_text(msg)
        await _zalo_recap(msg)


async def handle_daily_excuse(text: str, state: dict):
    """User replied to the end-of-day recap message."""
    overspent = state.get("overspent", 0)
    sh.clear_state(CHAT_ID)
    await tg.send_text(
        f"Đã ghi nhận. Vượt *{sh.fmt_amount(overspent)}* hôm nay.\n"
        f"Mai là một ngày mới."
    )


async def send_today_status():
    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)

    # Check daily_cap có được set không
    buckets = sh.get_active_buckets(month_key)
    daily_bkt = next((b for b in buckets if b["id"] == DAILY_BUCKET_ID), None)

    # Clarifier: 'Daily Spending' is ONE bucket (café vặt, taxi vặt, ...),
    # not the day's grand total. Common confusion — surface the distinction
    # here so users don't think /today double-counts their other categories.
    scope_hint = (
        "_(Bucket 'Daily Spending' = chi tiêu lặt vặt (café vặt, taxi nhỏ)._\n"
        "_KHÔNG phải tổng chi tiêu ngày — xem /report để xem hết theo category.)_"
    )

    if not daily_bkt or not daily_bkt.get("daily_cap"):
        # Tracking mode không có cap — show tổng tiêu hôm nay
        day = sh.get_daily_status(now)
        msg  = f"🍜 *Chi tiêu hôm nay — {now.strftime('%d/%m')}*\n\n"
        msg += f"Đã tiêu: *{sh.fmt_amount(day['spent'])}*\n\n"
        msg += "_Chưa set daily limit. Bật: /manage → 🛒 Daily Spending → ⏰ Daily cap._\n\n"
        msg += scope_hint
        await tg.send_text(msg)
        return

    day = sh.get_daily_status(now)
    pct = sh.calc_pct(day["spent"], day["cap"])

    msg  = f"🍜 *Chi tiêu hôm nay — {now.strftime('%d/%m')}*\n\n"
    msg += f"{sh.make_bar(pct)} {pct}%\n"
    msg += f"Đã tiêu: *{sh.fmt_amount(day['spent'])}* / {sh.fmt_amount(day['cap'])}\n"
    msg += f"Còn lại: *{sh.fmt_amount(day['remaining'])}*\n\n"

    if pct >= 100:
        msg += "🔴 Vượt giới hạn ngày.\n\n"
    elif pct >= 80:
        msg += f"🟡 Còn *{sh.fmt_amount(day['remaining'])}* hôm nay.\n\n"
    elif day['spent'] == 0:
        msg += "✨ Hôm nay chưa tiêu gì.\n\n"
    else:
        msg += f"💪 Còn *{sh.fmt_amount(day['remaining'])}* trong ngân sách hôm nay.\n\n"

    msg += scope_hint

    await tg.send_text(msg)


async def _zalo_recap(text: str):
    """Best-effort Zalo fan-out for daily recap. Non-fatal."""
    if not ZALO_ENABLED or not ZALO_CHAT_ID:
        return
    try:
        await messenger.send_text(text, channel="zalo", recipient_id=ZALO_CHAT_ID)
    except Exception as e:
        print(f"[reports] Zalo recap fan-out failed (non-fatal): {e}")

