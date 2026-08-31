"""Shared Zalo message renderers.

Zalo uses plain text menus instead of Telegram inline callback responses, so
finalization summaries need to be rendered explicitly for both webhook
auto-categorization and Zalo manual category replies.
"""
from datetime import datetime

import pytz

from config import DAILY_BUCKET_ID, TIMEZONE
import sheets as sh


def render_zalo_logged_summary(
    *,
    row_num: int,
    bucket_id: str,
    sub_label: str,
    amount: float,
    tx_date,
    tx_direction: str,
    currency: str,
) -> str:
    tz = pytz.timezone(TIMEZONE)
    if isinstance(tx_date, str):
        try:
            tx_dt = datetime.fromisoformat(tx_date)
        except Exception:
            tx_dt = datetime.now(tz)
    elif tx_date is not None:
        tx_dt = tx_date
    else:
        tx_dt = datetime.now(tz)
    # Naive datetimes here are local VN time. Localize them — otherwise
    # get_daily_status treats them as UTC and shifts +7h, putting an evening
    # tx (after 17:00) on the WRONG day in the daily summary.
    if getattr(tx_dt, "tzinfo", None) is None:
        try:
            tx_dt = tz.localize(tx_dt)
        except Exception:
            pass

    month_key = sh.fmt_month(tx_dt)
    parent_name = sh.bucket_label(bucket_id)
    sub_disp = f" · {sub_label}" if sub_label else ""

    if tx_direction == "in":
        msg = f"Logged: {parent_name}{sub_disp}\n+{sh.fmt_amount(amount, currency)}\n\n"
        if currency == "VND":
            income = sh.get_income_total(bucket_id, month_key)
            msg += f"{parent_name}: tổng nhận tháng này {sh.fmt_amount(income)}"
        else:
            msg += "Foreign currency — không tính vào tổng tháng."
        return f"{msg}\nSai mục? gửi /recat {row_num}"

    _LARGE_TX = 100_000

    bkt = sh.get_bucket_status(bucket_id, month_key)
    is_daily = bucket_id == DAILY_BUCKET_ID

    # Big-spend alert (budgeted non-daily only)
    if amount >= _LARGE_TX and not is_daily and bkt["allocated"] > 0:
        msg = f"!! {sh.fmt_amount(amount)} cho {parent_name}? Bucket còn {sh.fmt_amount(bkt['remaining'])}.\n\n"
    else:
        msg = ""

    msg += f"Logged: {parent_name}{sub_disp}\n-{sh.fmt_amount(amount, currency)}\n\n"

    if currency != "VND":
        cur_total = bkt.get("foreign", {}).get(currency, 0.0)
        msg += f"{parent_name} ({currency}): tổng tháng này {sh.fmt_amount(cur_total, currency)}"
    elif is_daily:
        day = sh.get_daily_status(tx_dt)
        pct = sh.calc_pct(day["spent"], day["cap"])
        msg += f"{sh.make_bar(pct)} {pct}%\n"
        msg += f"Hôm nay: {sh.fmt_amount(day['spent'])} / {sh.fmt_amount(day['cap'])}\n"
        if bkt["allocated"] > 0:
            msg += f"Monthly bucket còn: {sh.fmt_amount(bkt['remaining'])}\n\n"
        else:
            msg += f"Tháng này: {sh.fmt_amount(bkt['spent'])}\n\n"
        if pct >= 100:
            msg += "Vượt daily limit hôm nay."
        elif pct >= 80:
            msg += f"Còn {sh.fmt_amount(day['cap'] - day['spent'])} trong ngân sách hôm nay."
        else:
            msg += f"Còn {sh.fmt_amount(day['cap'] - day['spent'])} hôm nay."
    elif bkt["allocated"] > 0:
        pct = sh.calc_pct(bkt["spent"], bkt["allocated"])
        msg += f"{sh.make_bar(pct)} {pct}%\n"
        msg += f"{parent_name}: {sh.fmt_amount(bkt['spent'])} / {sh.fmt_amount(bkt['allocated'])}\n"
        msg += f"Còn lại: {sh.fmt_amount(bkt['remaining'])}"
        if bkt["remaining"] <= 0:
            msg += "\nBucket này đã hết."
        elif pct >= 80:
            msg += "\nSắp cạn — cẩn thận!"
    else:
        msg += f"{parent_name}: tổng tháng này {sh.fmt_amount(bkt['spent'])}"


    return f"{msg}\nSai mục? gửi /recat {row_num}"
