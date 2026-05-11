"""
handlers/transaction.py — finalize + confirm transaction labeling
"""
from datetime import datetime
import pytz
from config import CHAT_ID, DAILY_BUCKET_ID, TIMEZONE
import sheets as sh
import telegram_api as tg

_LARGE_TX = 100_000  # alert threshold in VND


async def handle_parent_selected(parts: list[str], message_id: int):
    # callback_data: p_{rowNum}_{bucketId}
    row_num   = int(parts[1])
    bucket_id = "_".join(parts[2:])

    # Skip categorization (used for income transactions)
    if bucket_id == "skip":
        sh.finalize_transaction(row_num, "", "")
        state = sh.get_state(CHAT_ID) or {}
        amount = state.get("amount") or 0
        sh.clear_state(CHAT_ID)
        await tg.edit_message(message_id, f"✅ Đã ghi nhận +{sh.fmt_amount(amount)} (không phân loại)")
        return

    # User tapped "➕ New category" — prompt for name, defer finalize until name is provided
    if bucket_id == "new":
        prev_state = sh.get_state(CHAT_ID) or {}
        sh.set_state(CHAT_ID, {
            **prev_state,                       # preserve tx_date, tx_direction, amount, description
            "step": "await_inline_new_cat_name",
            "row_num": row_num,
            "message_id": message_id,
        })
        await tg.edit_message(message_id, "📝 *Tên category mới?* _(VD: 🎮 Gaming)_")
        return

    sh.finalize_transaction(row_num, bucket_id, "")

    subs = sh.get_sub_categories(bucket_id)
    if not subs:
        await _finalize(row_num, bucket_id, "", message_id)
        return

    prev_state = sh.get_state(CHAT_ID) or {}
    buttons    = tg.build_sub_buttons(subs, f"s_{row_num}")
    buttons.append([{"text": "📦 Other", "callback_data": f"s_{row_num}_other"}])

    await tg.edit_message(message_id, f"✏️ *{sh.bucket_label(bucket_id)}* — what specifically?")
    resp       = await tg.send_with_buttons("Pick a sub-category:", buttons)
    sub_msg_id = resp.get("result", {}).get("message_id")

    sh.set_state(CHAT_ID, {
        **prev_state,
        "step":            "await_sub",
        "row_num":         row_num,
        "parent_category": bucket_id,
        "message_id":      message_id,
        "sub_msg_id":      sub_msg_id,
    })


async def handle_sub_selected(parts: list[str], message_id: int):
    # callback_data: s_{rowNum}_{subKey}
    row_num = int(parts[1])
    sub_key = "_".join(parts[2:])
    state   = sh.get_state(CHAT_ID)
    parent  = (state or {}).get("parent_category") or sh.get_parent_from_sheet(row_num)

    if sub_key == "other":
        sh.set_state(CHAT_ID, {**(state or {}), "step": "await_freetext", "row_num": row_num, "message_id": message_id})
        await tg.send_text("📝 What is this exactly? _(just type it)_")
        return

    sub_display = sh.get_sub_label(parent, sub_key)
    await _finalize(row_num, parent, sub_display, message_id)


async def handle_freetext_sub(text: str, state: dict):
    row_num = state["row_num"]
    parent  = state.get("parent_category") or sh.get_parent_from_sheet(row_num)
    sh.save_custom_sub(parent, text)
    await _finalize(row_num, parent, f"📦 {text}", state.get("message_id"))


async def handle_inline_new_cat_name(text: str, state: dict):
    """User typed name for a brand-new category triggered via the inline '➕ New category' button.

    Creates the bucket as track-only (allocated=0, daily_cap=None) for the current month,
    then finalizes the pending transaction against it (no sub-category prompt).
    """
    import unicodedata, re
    name = text.strip()
    if not name or len(name) > 40:
        await tg.send_text("⚠️ Tên không hợp lệ (1-40 ký tự). Thử lại.")
        return

    # Normalize → id (mirrors handlers/manage.py:340-346 + allocation.py)
    nid = unicodedata.normalize("NFD", name.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)   # strip diacritics — escape form, consistent with manage.py + allocation.py
    nid = re.sub(r"[^\w\s]", "", nid)            # strip emoji/symbols
    nid = re.sub(r"\s+", "_", nid.strip())
    nid = re.sub(r"[^a-z0-9_]", "", nid) or "custom"

    # Reserved sentinels — would collide with callback "p_{row}_new" / "p_{row}_skip"
    if nid in ("new", "skip"):
        await tg.send_text(f"⚠️ Tên *{name}* trùng từ khóa hệ thống. Nhập tên khác.")
        return

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))

    # Dedup against existing buckets this month
    existing = sh.get_active_buckets(month_key, force_refresh=True)
    if any(b["id"] == nid for b in existing):
        await tg.send_text(f"⚠️ *{name}* đã tồn tại. Nhập tên khác.")
        return

    # Create as track-only — user can /allocate or /manage later to set a budget
    sh.write_budget_row(month_key, {"id": nid, "name": name, "allocated": 0, "daily_cap": None})
    sh.invalidate_buckets_cache()

    # Finalize the pending transaction against the newly-created category
    row_num = state["row_num"]
    await _finalize(row_num, nid, "", state.get("message_id"))


async def handle_recategorize(parts: list[str], message_id: int):
    """User tapped 'Wrong category?' — reset the row and re-show the bucket picker."""
    row_num = int(parts[1])
    row = sh.get_transaction_row(row_num)
    amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
    description = row[5] if len(row) > 5 else ""

    # Reset finalized columns so the transaction isn't double-counted
    sh.reset_transaction_row(row_num)

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    sh.set_state(CHAT_ID, {"step": "await_parent", "row_num": row_num, "amount": amount, "description": description})

    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.edit_message(message_id, f"↩️ *Re-categorize: -{sh.fmt_amount(amount)}*\n`{description}`\n\nWhere did this actually go?")
    await tg.send_with_buttons("Pick a category:", buttons)


async def _finalize(row_num: int, parent_category: str, sub_label: str, message_id: int | None):
    sh.finalize_transaction(row_num, parent_category, sub_label)

    state = sh.get_state(CHAT_ID) or {}
    sh.clear_state(CHAT_ID)

    # Delete sub-category picker message if present
    sub_msg_id = state.get("sub_msg_id")
    if sub_msg_id:
        await tg.delete_message(sub_msg_id)

    tz = pytz.timezone(TIMEZONE)

    amount = state.get("amount") or 0
    if not amount:
        row    = sh.get_transaction_row(row_num)
        amount = sh._parse_amount(row[7]) if len(row) > 7 else 0

    tx_direction = state.get("tx_direction", "out")
    tx_date_str  = state.get("tx_date")
    tx_date      = datetime.fromisoformat(tx_date_str) if tx_date_str else datetime.now(tz)
    month_key    = sh.fmt_month(tx_date)
    is_daily     = parent_category == DAILY_BUCKET_ID
    parent_name  = sh.bucket_label(parent_category)
    sub_disp     = f" · {sub_label}" if sub_label else ""

    # ── INCOMING transaction ──────────────────────────────────
    if tx_direction == "in":
        msg = f"✅ *Ghi nhận: {parent_name}{sub_disp}*\n💚 +{sh.fmt_amount(amount)}\n\n"
        income = sh.get_income_total(parent_category, month_key)
        msg += f"{parent_name}: tổng nhận *{sh.fmt_amount(income)}* tháng này"
        recat_button = [[{"text": "🔄 Sai mục?", "callback_data": f"recat_{row_num}"}]]
        await tg.send_with_buttons(msg, recat_button)
        return

    # ── OUTGOING transaction ──────────────────────────────────
    bkt = sh.get_bucket_status(parent_category, month_key)

    # Big-spend alert: chỉ fire cho budgeted bucket (không judge tracking-only)
    # và chỉ với non-daily (daily có alert riêng dưới)
    if amount >= _LARGE_TX and not is_daily and bkt["allocated"] > 0:
        await tg.send_text(
            f"👀 *{sh.fmt_amount(amount)} cho {parent_name}?* "
            f"Bucket này còn *{sh.fmt_amount(bkt['remaining'])}*."
        )

    # Confirmation message
    msg = f"✅ *Logged: {parent_name}{sub_disp}*\n💸 -{sh.fmt_amount(amount)}\n\n"

    if is_daily:
        day = sh.get_daily_status(tx_date)
        pct = sh.calc_pct(day["spent"], day["cap"])

        msg += f"{sh.make_bar(pct)} {pct}%\n"
        msg += f"Hôm nay: {sh.fmt_amount(day['spent'])} / {sh.fmt_amount(day['cap'])}\n"

        if bkt["allocated"] > 0:
            msg += f"Monthly bucket còn: *{sh.fmt_amount(bkt['remaining'])}*\n\n"
        else:
            msg += f"Tháng này: *{sh.fmt_amount(bkt['spent'])}*\n\n"

        if pct >= 100:
            msg += "🔴 Vượt daily limit hôm nay."
        elif pct >= 80:
            msg += f"🟡 Còn *{sh.fmt_amount(day['cap'] - day['spent'])}* trong ngân sách hôm nay."
        else:
            msg += f"💪 Còn *{sh.fmt_amount(day['cap'] - day['spent'])}* hôm nay."
    elif bkt["allocated"] > 0:
        # Budgeted: progress bar + remaining
        pct = sh.calc_pct(bkt["spent"], bkt["allocated"])
        msg += f"{sh.make_bar(pct)} {pct}%\n"
        msg += f"{parent_name}: {sh.fmt_amount(bkt['spent'])} / {sh.fmt_amount(bkt['allocated'])}\n"
        msg += f"Remaining: *{sh.fmt_amount(bkt['remaining'])}*"

        if bkt["remaining"] <= 0:
            msg += "\n🔴 Bucket này đã hết."
        elif pct >= 80:
            msg += "\n🟠 Sắp cạn — cẩn thận!"
    else:
        # Tracking-only: chỉ show tổng tháng, không judge
        msg += f"📊 {parent_name}: tổng tháng này *{sh.fmt_amount(bkt['spent'])}*"

    recat_button = [[{"text": "🔄 Sai mục?", "callback_data": f"recat_{row_num}"}]]
    await tg.send_with_buttons(msg, recat_button)
