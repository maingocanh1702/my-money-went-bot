"""
handlers/allocation.py — Monthly budget allocation flow
"""
from config import CHAT_ID
import sheets as sh
import telegram_api as tg


async def start_monthly_allocation():
    """/allocate has two modes:

    1) FIRST-TIME setup (no buckets yet for this month): show the wizard
       with Keep prev / Enter amounts / Track only / Skip — for users who
       just signed up or rolled into a new month.

    2) EDIT mode (buckets already exist for this month): show the budget
       summary with per-bucket edit buttons + a 'Reset all' escape hatch.
       Re-running the wizard from scratch every time is the wrong default
       once budgets are in place — users want to tweak one bucket, not
       re-allocate everything.
    """
    from datetime import datetime
    import pytz
    from config import TIMEZONE
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)

    current_buckets = sh.get_active_buckets(month_key, force_refresh=True)

    # EDIT MODE — buckets already configured for this month
    if current_buckets:
        await _show_edit_view(month_key, current_buckets)
        return

    # FIRST-TIME SETUP — fall back to previous-month as a copy source
    prev_month = datetime(now.year if now.month > 1 else now.year - 1,
                          now.month - 1 if now.month > 1 else 12, 1, tzinfo=tz)
    prev_key = sh.fmt_month(prev_month)
    prev_buckets = sh.get_active_buckets(prev_key)

    msg  = "💰 *Set spending limits (optional)*\n\n"
    msg += "Đặt budget cho từng category để bot cảnh báo khi sắp cạn. "
    msg += "Skip cũng OK — categories sẽ chạy ở tracking mode (chỉ ghi lại tổng tiêu).\n\n"
    if prev_buckets:
        budgeted = [b for b in prev_buckets if b.get("allocated", 0) > 0]
        if budgeted:
            total_alloc = sum(b["allocated"] for b in budgeted)
            msg += f"tháng {prev_key} budget: *{sh.fmt_amount(total_alloc)}*\n\n"
    msg += f"Bạn muốn setup {month_key} thế nào?"

    sh.set_state(CHAT_ID, {
        "step":     "await_alloc_choice",
        "month_key": month_key,
        "copy_key":  prev_key,
    })

    buttons_row1 = []
    if prev_buckets and any(b.get("allocated", 0) > 0 for b in prev_buckets):
        buttons_row1.append({
            "text":         f"📋 Keep tháng {prev_key}",
            "callback_data": f"al_copy_{prev_key}",
        })
    buttons_row1.append({"text": "✏️ Enter amounts", "callback_data": f"al_fresh_{month_key}"})
    buttons_row2 = [
        {"text": "🏷️ Track only", "callback_data": f"al_track_{month_key}"},
        {"text": "⏭️ Skip", "callback_data": f"al_skip_{month_key}"},
    ]
    await tg.send_with_buttons(msg, [buttons_row1, buttons_row2])


# ─── Edit mode (when buckets already exist) ──────────────────────


TYPE_BUDGET_EMOJI = "💰"


async def _show_edit_view(month_key: str, buckets: list[dict]):
    """Budget summary + per-bucket edit buttons + reset/done escape."""
    msg = f"💰 *Budget — {month_key}*\n\n"
    total = 0
    for b in buckets:
        alloc = b.get("allocated", 0) or 0
        if alloc > 0:
            msg += f"{b['name']}   *{sh.fmt_amount(alloc)}*\n"
            total += alloc
        else:
            msg += f"{b['name']}   🏷️ tracking\n"
    msg += f"─────────────────────\n*Total: {sh.fmt_amount(total)}*\n\n"
    msg += "_Tap 1 category để sửa limit, hoặc reset toàn bộ:_"

    # 2-col grid of edit buttons
    edit_rows: list[list[dict]] = []
    pair: list[dict] = []
    for b in buckets:
        pair.append({
            "text":          f"✏️ {b['name']}",
            "callback_data": f"al_editbucket_{b['id']}",
        })
        if len(pair) == 2:
            edit_rows.append(pair)
            pair = []
    if pair:
        edit_rows.append(pair)

    edit_rows.append([
        {"text": "➕ Add bucket",    "callback_data": f"al_addbucket_{month_key}"},
    ])
    edit_rows.append([
        {"text": "🔄 Reset toàn bộ", "callback_data": f"al_resetall_{month_key}"},
        {"text": "✅ Xong",           "callback_data": "al_close_none"},
    ])

    sh.set_state(CHAT_ID, {"step": "await_edit_choice", "month_key": month_key})
    await tg.send_with_buttons(msg, edit_rows)


async def _start_edit_bucket(bucket_id: str):
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    if not month_key:
        await tg.send_text("⚠️ State đã hết hạn. Chạy /allocate lại.")
        return
    buckets = sh.get_active_buckets(month_key)
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if not bucket:
        await tg.send_text(f"⚠️ Bucket `{bucket_id}` không tồn tại trong tháng này.")
        return
    sh.set_state(CHAT_ID, {
        **state,
        "step":            "await_edit_bucket_amount",
        "edit_bucket_id":  bucket_id,
        "edit_bucket_name": bucket["name"],
    })
    current_alloc = bucket.get("allocated", 0) or 0
    await tg.send_text(
        f"✏️ *{bucket['name']}* (hiện: {sh.fmt_amount(current_alloc)})\n\n"
        f"Nhập limit mới cho {month_key}:\n"
        f"_(số, vd `3000000`, hoặc `0` để track-only không cap)_"
    )


async def handle_edit_bucket_amount(text: str, state: dict):
    raw = "".join(c for c in text if c.isdigit())
    if not raw:
        await tg.send_text(
            "⚠️ Số không hợp lệ. Thử lại (vd `3000000` hoặc `0`)."
        )
        return
    try:
        amount = int(raw)
    except ValueError:
        await tg.send_text("⚠️ Số không hợp lệ.")
        return
    if amount < 0:
        await tg.send_text("⚠️ Số phải ≥ 0. `0` = track-only không cap.")
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    if not month_key or not bucket_id:
        await tg.send_text("⚠️ State đã hết hạn. Chạy /allocate lại.")
        return

    # Find the bucket, update allocation, write back
    buckets = sh.get_active_buckets(month_key)
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if not bucket:
        await tg.send_text(f"⚠️ Bucket `{bucket_id}` đã biến mất.")
        sh.clear_state(CHAT_ID)
        return
    bucket["allocated"] = amount
    sh.write_budget_row(month_key, bucket)
    sh.invalidate_buckets_cache()

    # Re-render the edit view so the user sees the updated total
    refreshed = sh.get_active_buckets(month_key, force_refresh=True)
    await tg.send_text(
        f"✅ Đã update *{bucket['name']}* → {sh.fmt_amount(amount)}"
        + (" (track-only)" if amount == 0 else "")
    )
    await _show_edit_view(month_key, refreshed)


async def _reset_all_allocations(month_key: str):
    """Drop into the wizard branch so user starts the allocation flow from
    scratch. We don't actually delete buckets — `_start_fresh` re-iterates
    them and overwrites with new amounts."""
    await _start_fresh(month_key)


async def _close_edit_view():
    sh.clear_state(CHAT_ID)
    await tg.send_text("👌 OK, budget giữ nguyên. Dùng /allocate lại khi muốn chỉnh tiếp.")


async def handle_alloc_callback(parts: list[str], message_id: int):
    action = parts[1]
    rest   = "_".join(parts[2:])
    if   action == "copy":        await _handle_copy(rest)
    elif action == "fresh":       await _start_fresh(rest)
    elif action == "track":       await _start_track_only(rest)
    elif action == "addbucket":   await _prompt_new_bucket_name()
    elif action == "done":        await _finalize_allocation()
    elif action == "skip":        await _skip_allocation()
    elif action == "editbucket":  await _start_edit_bucket(rest)
    elif action == "resetall":    await _reset_all_allocations(rest)
    elif action == "close":       await _close_edit_view()


async def _handle_copy(prev_key: str):
    state    = sh.get_state(CHAT_ID)
    month_key = (state or {}).get("month_key", "")
    prev_buckets = sh.get_active_buckets(prev_key)

    if not prev_buckets:
        await tg.send_text(f"⚠️ No budget found for {prev_key}. Let's start fresh!")
        await _start_fresh(month_key)
        return

    for b in prev_buckets:
        sh.write_budget_row(month_key, b)

    sh.set_state(CHAT_ID, {"step": "await_add_bucket", "month_key": month_key, "allocations": prev_buckets})
    await _show_alloc_summary(month_key, prev_buckets)


async def _start_fresh(month_key: str):
    """Iterate the user's ACTUAL buckets for this month, not the hard-coded
    defaults. Defaults are only the seed for a brand-new month — once the
    user customized via /manage (added Coffee/Food/Drink, removed Work
    Supplements, etc.), /allocate Enter-amounts must follow those changes.
    Falling back to defaults only when the month has no buckets at all
    (genuine fresh start).
    """
    current = sh.get_active_buckets(month_key, force_refresh=True)
    buckets = current if current else sh.get_default_buckets()
    sh.set_state(CHAT_ID, {
        "step":          "await_alloc_amount",
        "month_key":     month_key,
        "buckets":       buckets,
        "current_index": 0,
        "allocations":   [],
    })
    await _ask_next_bucket()


async def _start_track_only(month_key: str):
    """Bootstrap default categories ở tracking mode — không hỏi amount."""
    async with sh.bootstrap_lock:
        sh.bootstrap_default_categories(month_key)
    buckets = sh.get_active_buckets(month_key, force_refresh=True)
    sh.clear_state(CHAT_ID)
    msg  = f"🏷️ *Tracking mode — {month_key}*\n\n"
    msg += "Đã setup các categories sau (không có budget limit):\n\n"
    for b in buckets:
        msg += f"{b['name']}\n"
    msg += "\nDùng /manage để thêm/sửa category, /allocate sau này nếu muốn đặt budget."
    await tg.send_text(msg)


async def _skip_allocation():
    """User chọn skip — vẫn bootstrap categories nếu chưa có để bot hoạt động."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    if month_key:
        async with sh.bootstrap_lock:
            sh.bootstrap_default_categories(month_key)
    sh.clear_state(CHAT_ID)
    await tg.send_text(
        "👌 OK, không đặt budget. Categories vẫn track tổng tiêu mỗi tháng.\n"
        "Đổi ý lúc nào dùng /allocate hoặc /manage."
    )


async def _ask_next_bucket():
    state  = sh.get_state(CHAT_ID)
    idx    = state["current_index"]
    bucket = state["buckets"][idx]
    total  = len(state["buckets"])
    await tg.send_text(
        f"📊 Bucket {idx + 1}/{total}\n\n"
        f"*{bucket['name']}* — how much for {state['month_key']}?\n"
        f"_(e.g. 3000000 hoặc 0 để track-only không cap)_"
    )


async def handle_alloc_amount_input(text: str, state: dict):
    """0 is valid here: it means 'track this bucket but no spending cap'
    (the bucket appears in /report under TRACKING, no budget % bar). Used
    when the user wants to monitor a category without committing a number.
    """
    raw = "".join(c for c in text if c.isdigit())
    if not raw:
        await tg.send_text(
            "⚠️ That's not a valid number. Try again "
            "(e.g. `3000000`, or `0` để track-only)."
        )
        return
    try:
        amount = int(raw)
    except ValueError:
        await tg.send_text(
            "⚠️ That's not a valid number. Try again "
            "(e.g. `3000000`, or `0` để track-only)."
        )
        return
    if amount < 0:
        await tg.send_text("⚠️ Số phải ≥ 0. `0` = track-only không cap.")
        return

    bucket       = state["buckets"][state["current_index"]]
    allocations  = list(state.get("allocations") or []) + [{**bucket, "allocated": amount}]
    next_index   = state["current_index"] + 1

    if next_index >= len(state["buckets"]):
        sh.set_state(CHAT_ID, {**state, "allocations": allocations, "step": "await_add_bucket"})
        await _show_alloc_summary(state["month_key"], allocations)
    else:
        sh.set_state(CHAT_ID, {**state, "current_index": next_index, "allocations": allocations})
        await _ask_next_bucket()


async def _prompt_new_bucket_name():
    state = sh.get_state(CHAT_ID)
    sh.set_state(CHAT_ID, {**state, "step": "await_new_bucket_name"})
    await tg.send_text("📝 What's the new bucket called? _(e.g. Hanoi Trip)_")


async def handle_new_bucket_name(text: str, state: dict):
    import unicodedata, re
    nid = unicodedata.normalize("NFD", text.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)
    nid = re.sub(r"\s+", "_", nid)
    nid = re.sub(r"[^a-z0-9_]", "", nid)
    sh.set_state(CHAT_ID, {**state, "step": "await_new_bucket_amount", "new_bucket_name": text, "new_bucket_id": nid})
    await tg.send_text(f"💰 *{text}* — how much for {state['month_key']}?\n_(e.g. 2500000)_")


async def handle_new_bucket_amount(text: str, state: dict):
    try:
        amount = int("".join(c for c in text if c.isdigit()))
        assert amount > 0
    except Exception:
        await tg.send_text("⚠️ That's not a valid amount. Try again.")
        return

    new_bucket = {
        "id":        state["new_bucket_id"],
        "name":      state["new_bucket_name"],
        "allocated": amount,
        "daily_cap": None,
    }
    allocations = list(state.get("allocations") or []) + [new_bucket]
    sh.set_state(CHAT_ID, {**state, "step": "await_add_bucket", "allocations": allocations,
                            "new_bucket_name": None, "new_bucket_id": None})
    await _show_alloc_summary(state["month_key"], allocations)


async def _show_alloc_summary(month_key: str, allocations: list[dict]):
    msg   = f"✅ *Budget for {month_key}:*\n\n"
    total = 0
    for b in allocations:
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{b['name']}   *{sh.fmt_amount(alloc)}*\n"
            total += alloc
        else:
            msg += f"{b['name']}   _🏷️ tracking_\n"
    msg += f"─────────────────────\nTotal budgeted   *{sh.fmt_amount(total)}*\n\nThêm bucket nữa không?"
    await tg.send_with_buttons(msg, [[
        {"text": "➕ Add bucket",    "callback_data": f"al_addbucket_{month_key}"},
        {"text": "✅ Save & done",   "callback_data": f"al_done_{month_key}"},
    ]])


async def _finalize_allocation():
    state       = sh.get_state(CHAT_ID) or {}
    month_key   = state.get("month_key", "")
    allocations = state.get("allocations") or []

    for b in allocations:
        sh.write_budget_row(month_key, b)
    sh.invalidate_buckets_cache()

    sh.clear_state(CHAT_ID)

    msg   = f"🎯 *Locked in for {month_key}!*\n\n"
    total = 0
    for b in allocations:
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{b['name']}   {sh.fmt_amount(alloc)}\n"
            total += alloc
        else:
            msg += f"{b['name']}   🏷️ tracking\n"
    msg += (
        f"─────────────────────\n"
        f"Total budgeted   *{sh.fmt_amount(total)}*\n\n"
        f"_💡 Chỉnh budget cho 1 category đơn lẻ: dùng /manage (không cần "
        f"chạy lại /allocate từ đầu)._"
    )
    await tg.send_text(msg)
