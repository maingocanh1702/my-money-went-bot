"""
handlers/zalo_render.py — plain-text logged summary for Zalo tx picker.
Mirrors transaction.py::_finalize's budget-feedback message in plain text
(no Telegram markdown, no inline buttons).
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
    amount,
    tx_date,
    tx_direction: str,
    currency: str,
) -> str:
    """Build a plain-text logged summary message for a Zalo category pick.

    Mirrors the branches from transaction._finalize (income / foreign /
    daily / budgeted / tracking-only) without Telegram markup or buttons.
    row_num is included in the header so Zalo-only users can identify the
    transaction; /recat is Telegram-only and not advertised here.
    Bucket name is resolved from the transaction's own month (not current month)
    to stay accurate for delayed/cross-month transactions.
    """
    tz = pytz.timezone(TIMEZONE)

    # Normalise tx_date to an aware datetime
    if isinstance(tx_date, str):
        try:
            tx_date = datetime.fromisoformat(tx_date)
        except ValueError:
            parsed = sh._parse_dt(tx_date)
            tx_date = tz.localize(parsed.replace(tzinfo=None)) if parsed else datetime.now(tz)
    if tx_date is None:
        tx_date = datetime.now(tz)
    if tx_date.tzinfo is None:
        tx_date = tz.localize(tx_date)

    month_key = sh.fmt_month(tx_date)

    # Resolve bucket name from the transaction's own month so cross-month
    # picks (e.g. email-delayed tx) show the name that was active then.
    buckets_for_month = sh.get_active_buckets(month_key)
    matched = next((b for b in buckets_for_month if b["id"] == bucket_id), None)
    parent_name = matched["name"] if matched else sh.bucket_label(bucket_id)

    sub_disp = f" · {sub_label}" if sub_label else ""
    is_daily = bucket_id == DAILY_BUCKET_ID
    row_tag = f" (row {row_num})"

    # ── INCOMING ──────────────────────────────────────────────
    if tx_direction == "in":
        msg = f"Ghi nhận{row_tag}: {parent_name}{sub_disp}\n+{sh.fmt_amount(amount, currency)}\n\n"
        if currency == "VND":
            income = sh.get_income_total(bucket_id, month_key)
            msg += f"{parent_name}: tổng nhận {sh.fmt_amount(income)} tháng này"
        else:
            msg += "(Foreign currency — không tính vào tổng tháng)"
        return msg

    # ── OUTGOING ──────────────────────────────────────────────
    bkt = sh.get_bucket_status(bucket_id, month_key)

    if currency != "VND":
        cur_total = bkt.get("foreign", {}).get(currency, 0.0)
        return (
            f"Logged{row_tag}: {parent_name}{sub_disp}\n"
            f"-{sh.fmt_amount(amount, currency)}\n\n"
            f"{parent_name} ({currency}): tổng tháng này {sh.fmt_amount(cur_total, currency)}"
        )

    msg = f"Logged{row_tag}: {parent_name}{sub_disp}\n-{sh.fmt_amount(amount)}\n\n"

    if is_daily:
        day = sh.get_daily_status(tx_date)
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
        msg += f"Remaining: {sh.fmt_amount(bkt['remaining'])}"
        if bkt["remaining"] <= 0:
            msg += "\nBucket này đã hết."
        elif pct >= 80:
            msg += "\nSắp cạn — cẩn thận!"
    else:
        msg += f"{parent_name}: tổng tháng này {sh.fmt_amount(bkt['spent'])}"

    return msg
