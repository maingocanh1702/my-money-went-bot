"""
handlers/reports.py — /status, /today, weekly summary, monthly report
"""
from datetime import datetime, date, timedelta
import pytz

from config import CHAT_ID, TIMEZONE, DAILY_BUCKET_ID
import sheets as sh
import telegram_api as tg


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
        await tg.send_text(
            f"🌙 *End of day — {now.strftime('%b %d')}*\n\n"
            f"Hôm nay không tiêu đồng nào cho daily expenses. Sleep well. 💤"
        )
        return

    pct = sh.calc_pct(day["spent"], day["cap"])

    if day["spent"] > day["cap"]:
        overspent = day["spent"] - day["cap"]
        await tg.send_text(
            f"🌙 *End of day — {now.strftime('%b %d')}*\n\n"
            f"Daily spending: *{sh.fmt_amount(day['spent'])}* ({pct}% of limit)\n"
            f"Vượt *{sh.fmt_amount(overspent)}* so với cap ngày.\n\n"
            f"Muốn note lại lý do? Reply để bot ghi nhận."
        )
        sh.set_state(CHAT_ID, {"step": "await_daily_excuse", "date": now.strftime("%Y-%m-%d"), "overspent": overspent})
    else:
        remaining = day["cap"] - day["spent"]
        await tg.send_text(
            f"🌙 *End of day — {now.strftime('%b %d')}*\n\n"
            f"Daily spending: *{sh.fmt_amount(day['spent'])}* ({pct}% of limit)\n"
            f"Còn dư *{sh.fmt_amount(remaining)}*. ✨"
        )


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

    if not daily_bkt or not daily_bkt.get("daily_cap"):
        # Tracking mode không có cap — show tổng tiêu hôm nay
        day = sh.get_daily_status(now)
        msg  = f"🍜 *Daily spending — {now.strftime('%b %d')}*\n\n"
        msg += f"Đã tiêu: *{sh.fmt_amount(day['spent'])}*\n\n"
        msg += "_Chưa set daily limit. Dùng /manage để bật cap nếu muốn._"
        await tg.send_text(msg)
        return

    day = sh.get_daily_status(now)
    pct = sh.calc_pct(day["spent"], day["cap"])

    msg  = f"🍜 *Daily spending — {now.strftime('%b %d')}*\n\n"
    msg += f"{sh.make_bar(pct)} {pct}%\n"
    msg += f"Đã tiêu: *{sh.fmt_amount(day['spent'])}* / {sh.fmt_amount(day['cap'])}\n"
    msg += f"Còn lại: *{sh.fmt_amount(day['remaining'])}*\n\n"

    if pct >= 100:
        msg += "🔴 Vượt giới hạn ngày."
    elif pct >= 80:
        msg += f"🟡 Còn *{sh.fmt_amount(day['remaining'])}* hôm nay."
    elif day['spent'] == 0:
        msg += "✨ Hôm nay chưa tiêu gì."
    else:
        msg += f"💪 Còn *{sh.fmt_amount(day['remaining'])}* trong ngân sách hôm nay."

    await tg.send_text(msg)


async def send_monthly_status():
    tz        = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets   = sh.get_active_buckets(month_key)

    if not buckets:
        await tg.send_text(
            f"⚠️ Chưa có category nào cho {month_key}.\n"
            f"Tạo giao dịch đầu tiên hoặc /manage để setup."
        )
        return

    days_left = sh.days_left_in_month()
    msg       = f"📊 *Tracking — {month_key}*\n_{days_left} ngày còn lại_\n\n"

    budgeted = [b for b in buckets if b.get("allocated", 0) > 0]
    tracking = [b for b in buckets if b.get("allocated", 0) == 0]

    total_alloc = total_spent = 0

    if budgeted:
        msg += "*BUDGETED:*\n"
        for b in budgeted:
            s   = sh.get_bucket_status(b["id"], month_key)
            pct = sh.calc_pct(s["spent"], b["allocated"])
            ico = "🔴" if pct >= 100 else "🟡" if pct >= 80 else "✅"
            msg += f"{ico} {b['name']}\n{sh.make_bar(pct)} {pct}%\n"
            msg += f"{sh.fmt_amount(s['spent'])} / {sh.fmt_amount(b['allocated'])} · còn *{sh.fmt_amount(s['remaining'])}*\n\n"
            total_alloc += b["allocated"]
            total_spent += s["spent"]

    if tracking:
        msg += "*TRACKING:*\n"
        for b in tracking:
            s = sh.get_bucket_status(b["id"], month_key)
            msg += f"📊 {b['name']}: *{sh.fmt_amount(s['spent'])}* tháng này\n"
            total_spent += s["spent"]
        msg += "\n"

    msg += f"─────────────────────\n"
    if total_alloc > 0:
        msg += f"Total: {sh.fmt_amount(total_spent)} (budgeted: {sh.fmt_amount(total_alloc)})"
    else:
        msg += f"Total spent: *{sh.fmt_amount(total_spent)}*"

    # ─── BY BANK section ──────────────────────────────────────
    # Chỉ hiện khi có ít nhất 1 bank account thật (không tính nhóm "Không rõ")
    # để không làm rối user mới chưa đủ data.
    bank_breakdown = sh.get_bank_breakdown(month_key)
    real_banks = [b for b in bank_breakdown if b["bank"] != sh.UNKNOWN_BANK_LABEL]
    if real_banks:
        msg += "\n\n*BY BANK:*\n"
        for b in bank_breakdown:  # giữ cả "Không rõ" để tổng vẫn khớp
            line = f"🏦 `{b['bank']}` · chi *{sh.fmt_amount(b['spent'])}*"
            if b["income"] > 0:
                line += f" · thu {sh.fmt_amount(b['income'])}"
            line += f" · {b['tx_count']} GD\n"
            msg += line
        msg += "_Dùng /banks để xem chi tiết theo category._"

    await tg.send_text(msg)


async def send_bank_breakdown():
    """`/banks` — chi tiết spending theo từng bank account, kèm breakdown category."""
    tz        = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    breakdown = sh.get_bank_breakdown(month_key)

    if not breakdown:
        await tg.send_text(
            f"⚠️ Chưa có giao dịch nào cho {month_key}.\n"
            f"Bot tự động tag bank cho mọi GD mới — chưa có dữ liệu để break-down."
        )
        return

    buckets    = sh.get_active_buckets(month_key)
    name_by_id = {b["id"]: b["name"] for b in buckets}

    total_spent  = sum(b["spent"] for b in breakdown)
    total_income = sum(b["income"] for b in breakdown)

    msg = f"🏦 *BANK ACCOUNTS — {month_key}*\n─────────────────────────────\n\n"

    for b in breakdown:
        msg += f"*`{b['bank']}`*\n"
        msg += f"  💸 Chi: *{sh.fmt_amount(b['spent'])}*"
        if total_spent > 0:
            pct = sh.calc_pct(b["spent"], total_spent)
            msg += f" ({pct}% tổng chi)"
        msg += "\n"
        if b["income"] > 0:
            msg += f"  💚 Thu: {sh.fmt_amount(b['income'])}\n"
        msg += f"  🧾 {b['tx_count']} giao dịch\n"

        # Top 3 category cho bank này
        if b["by_category"]:
            top = sorted(b["by_category"].items(), key=lambda x: -x[1])[:3]
            msg += "  Top categories:\n"
            for cat_id, amt in top:
                cat_name = name_by_id.get(cat_id, cat_id)
                msg += f"    · {cat_name}  {sh.fmt_amount(amt)}\n"
        msg += "\n"

    msg += "─────────────────────────────\n"
    msg += f"Total chi: *{sh.fmt_amount(total_spent)}*"
    if total_income > 0:
        msg += f"  ·  Total thu: {sh.fmt_amount(total_income)}"

    if any(b["bank"] == sh.UNKNOWN_BANK_LABEL for b in breakdown):
        msg += (
            "\n\n_Nhóm \"Không rõ\" là GD cũ trước khi bật tính năng này — "
            "GD mới sẽ tự gắn bank._"
        )

    await tg.send_text(msg)


async def run_weekly_summary():
    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)

    dow   = now.weekday()  # Mon=0, Sun=6
    start = (now - timedelta(days=dow)).replace(hour=0, minute=0, second=0, microsecond=0)

    ws   = sh._sheet(sh.S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]

    by_bucket: dict[str, float] = {}
    by_sub:    dict[str, float] = {}

    for r in rows:
        if len(r) < 14 or str(r[13]).upper() != "TRUE":
            continue
        # Only count outgoing (spending) transactions
        if len(r) > 6 and r[6] == "Tiền vào":
            continue
        try:
            d = datetime.fromisoformat(str(r[1]))
            if d.tzinfo is None:
                d = tz.localize(d)  # stored as Vietnam local time
            else:
                d = d.astimezone(tz)
        except Exception:
            continue
        if d < start or d > now:
            continue
        parent = r[10] or ""
        sub    = r[11] or "Other"
        amt    = sh._parse_amount(r[7])
        by_bucket[parent] = by_bucket.get(parent, 0) + amt
        key = f"{parent}||{sub}"
        by_sub[key] = by_sub.get(key, 0) + amt

    buckets    = sh.get_active_buckets(month_key)
    week_start = start.strftime("%d/%m")
    week_end   = now.strftime("%d/%m")
    msg = f"📊 *Week recap ({week_start} – {week_end})*\n\n"

    total_week = sum(by_bucket.values())
    if total_week == 0:
        await tg.send_text(f"📊 *Week recap ({week_start} – {week_end})*\n\n✨ Tuần này không tiêu gì.")
        return

    for b in buckets:
        week_spent = by_bucket.get(b["id"], 0)
        if week_spent == 0:
            continue
        if b.get("allocated", 0) > 0:
            # Budgeted: so sánh với budget tuần ước tính
            week_budget = round(b["allocated"] / 4.3)
            flag = "⚠️" if week_spent > week_budget else "✅"
            msg += f"{b['name']}: *{sh.fmt_amount(week_spent)}* / ~{sh.fmt_amount(week_budget)} {flag}\n"
        else:
            # Tracking: chỉ show tổng tuần
            msg += f"📊 {b['name']}: *{sh.fmt_amount(week_spent)}* tuần này\n"

        if b["id"] == DAILY_BUCKET_ID:
            subs = sh.get_sub_categories(b["id"])
            for sub in subs:
                k   = f"{b['id']}||{sub['label']}"
                amt = by_sub.get(k, 0)
                if amt == 0:
                    continue
                s_pct = sh.calc_pct(amt, week_spent)
                msg += f"  {sub['label']}   {sh.fmt_amount(amt)}  {sh.make_bar(s_pct, 5)}\n"
        msg += "\n"

    msg += f"─────────────────────\nWeek total: *{sh.fmt_amount(total_week)}*"
    await tg.send_text(msg)


async def run_monthly_report():
    tz        = pytz.timezone(TIMEZONE)
    now       = datetime.now(tz)
    month_key = sh.fmt_month(now)
    buckets   = sh.get_active_buckets(month_key)

    if not buckets:
        await tg.send_text(f"⚠️ Chưa có data cho {month_key}.")
        return

    prev_date = datetime(now.year if now.month > 1 else now.year - 1,
                         now.month - 1 if now.month > 1 else 12, 1, tzinfo=tz)
    prev_key  = sh.fmt_month(prev_date)

    ws   = sh._sheet(sh.S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]

    this_txns = [r for r in rows if len(r) >= 15 and r[14] == month_key and str(r[13]).upper() == "TRUE" and r[6] != "Tiền vào"]
    prev_txns = [r for r in rows if len(r) >= 15 and r[14] == prev_key  and str(r[13]).upper() == "TRUE" and r[6] != "Tiền vào"]

    total_alloc = total_spent = 0
    results = []
    for b in buckets:
        s    = sh.get_bucket_status(b["id"], month_key)
        prev = sh.get_bucket_status(b["id"], prev_key)
        total_alloc += b.get("allocated", 0)
        total_spent += s["spent"]
        pct = sh.calc_pct(s["spent"], b["allocated"]) if b.get("allocated", 0) > 0 else 0
        results.append({**b, "spent": s["spent"], "remaining": s["remaining"], "pct": pct, "prev_spent": prev["spent"]})

    sub_totals: dict[str, float] = {}
    for r in this_txns:
        k = r[11] or "Other"
        sub_totals[k] = sub_totals.get(k, 0) + sh._parse_amount(r[7])
    top3 = sorted(sub_totals.items(), key=lambda x: -x[1])[:3]

    daily_totals: dict[str, float] = {}
    for r in this_txns:
        try:
            d = datetime.fromisoformat(str(r[1])).astimezone(tz).strftime("%d/%m")
        except Exception:
            continue
        daily_totals[d] = daily_totals.get(d, 0) + sh._parse_amount(r[7])

    heaviest = max(daily_totals.items(), key=lambda x: x[1]) if daily_totals else None

    daily_bkt = next((b for b in buckets if b["id"] == DAILY_BUCKET_ID), None)
    daily_cap = daily_bkt["daily_cap"] if daily_bkt and daily_bkt.get("daily_cap") else 100_000
    good_days = sum(1 for v in daily_totals.values() if v < daily_cap * 0.8)

    month_disp = now.strftime("%m/%Y")

    msg  = f"📅 *MONTHLY REPORT — {month_disp}*\n─────────────────────────────\n\n"
    msg += f"💰 Total spent: *{sh.fmt_amount(total_spent)}*"
    if total_alloc > 0:
        surplus     = total_alloc - total_spent
        surplus_pct = sh.calc_pct(surplus, total_alloc) if surplus > 0 else 0
        msg += f" / budgeted {sh.fmt_amount(total_alloc)}\n"
        msg += f"Còn dư: {sh.fmt_amount(surplus)} ({surplus_pct}% intact)\n\n"
    else:
        msg += "\n\n"

    budgeted_results = [b for b in results if b.get("allocated", 0) > 0]
    tracking_results = [b for b in results if b.get("allocated", 0) == 0]

    if budgeted_results:
        msg += "*BUDGETED:*\n"
        for b in budgeted_results:
            flag = " 🔴" if b["pct"] >= 100 else " ⚠️" if b["pct"] >= 80 else " ✅"
            msg += f"{b['name']}  {sh.fmt_amount(b['spent'])} / {sh.fmt_amount(b['allocated'])}  {b['pct']}%{flag}\n"
        msg += "\n"

    if tracking_results:
        msg += "*TRACKING:*\n"
        for b in tracking_results:
            line = f"{b['name']}  {sh.fmt_amount(b['spent'])}"
            if b["prev_spent"] > 0:
                diff_pct = round(((b["spent"] - b["prev_spent"]) / b["prev_spent"]) * 100)
                arrow = "📈" if diff_pct > 0 else "📉" if diff_pct < 0 else ""
                line += f"  {arrow}{abs(diff_pct)}% vs prev"
            msg += line + "\n"
        msg += "\n"

    if top3:
        msg += "*TOP SPENDING CATEGORIES:*\n"
        for i, (sub, amt) in enumerate(top3):
            msg += f"{i+1}. {sub}   {sh.fmt_amount(amt)}\n"

    # VS last month chỉ áp dụng cho budgeted (tracking đã có inline)
    up   = [b for b in budgeted_results if b["prev_spent"] > 0 and b["spent"] > b["prev_spent"] * 1.2]
    down = [b for b in budgeted_results if b["prev_spent"] > 0 and b["spent"] < b["prev_spent"] * 0.8]
    if up or down:
        msg += "\n*VS LAST MONTH:*\n"
        for b in up:
            chg = round(((b["spent"] - b["prev_spent"]) / b["prev_spent"]) * 100)
            msg += f"📈 {b['name']} +{chg}%\n"
        for b in down:
            chg = round(((b["prev_spent"] - b["spent"]) / b["prev_spent"]) * 100)
            msg += f"📉 {b['name']} -{chg}%\n"

    if heaviest:
        msg += f"\n📅 Heaviest day: {heaviest[0]} ({sh.fmt_amount(heaviest[1])})\n"
    msg += f"🧾 Transactions: {len(this_txns)}"
    if prev_txns:
        diff = len(this_txns) - len(prev_txns)
        msg += f" ({'+' if diff >= 0 else ''}{diff} vs last month)"

    # Wins / Watch chỉ liệt kê khi có budgeted bucket
    if budgeted_results:
        msg += "\n\n*WINS 💪*\n"
        saving_b = next((b for b in budgeted_results if b["id"] == "saving"), None)
        if saving_b and saving_b["pct"] >= 100:
            msg += "→ Saving goal hit 100% 🎉\n"
        if good_days > 0 and daily_bkt and daily_bkt.get("daily_cap"):
            msg += f"→ {good_days} ngày giữ Daily under {round(daily_cap * 0.8 / 1000)}k\n"

        over_budget = [b for b in budgeted_results if b["pct"] > 100]
        near_limit  = [b for b in budgeted_results if 80 <= b["pct"] <= 100]
        msg += "\n*WATCH NEXT MONTH ⚠️*\n"
        if not over_budget and not near_limit:
            msg += "→ Tất cả budgeted buckets đều xanh 🎉\n"
        else:
            for b in over_budget:
                msg += f"→ {b['name']} vượt {b['pct'] - 100}%\n"
            for b in near_limit:
                msg += f"→ {b['name']} ở {b['pct']}% — sắp cạn\n"

    msg += "\n─────────────────────────────\nDùng /allocate để đặt budget tháng sau (optional)."

    sh.archive_report(month_key, results)
    await tg.send_text(msg)
