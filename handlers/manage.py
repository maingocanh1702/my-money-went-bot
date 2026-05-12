# ⚠️ DEPRECATED — Legacy handler. Moves to core/handlers/manage.py in Phase 2 F04.
# DO NOT add new features here. See docs/implementation-plans/phase-2-handlers.md
"""
handlers/manage.py — Edit & Delete categories, sub-categories, allocations
Entry point: /manage command
"""
import unicodedata
import re
from config import CHAT_ID, TIMEZONE
import sheets as sh
import telegram_api as tg
from datetime import datetime
import pytz


# ─── Entry point ──────────────────────────────────────────────
async def start_manage():
    """Entry point: /manage command. Auto-bootstrap defaults nếu chưa có."""
    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        # Race-safe bootstrap (dùng cùng lock với sepay)
        async with sh.bootstrap_lock:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_default_categories(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)

    sh.set_state(CHAT_ID, {"step": "manage", "month_key": month_key})
    await _show_category_list(month_key, buckets)


async def _show_category_list(month_key: str, buckets: list[dict]):
    """Show all active buckets with selection buttons."""
    msg = f"⚙️ *Manage Categories — {month_key}*\n\n"
    total = 0
    for b in buckets:
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{b['name']}   *{sh.fmt_amount(alloc)}*\n"
            total += alloc
        else:
            msg += f"{b['name']}   _🏷️ tracking_\n"
    msg += (
        f"─────────────────────\n"
        f"Total budgeted   *{sh.fmt_amount(total)}*\n\n"
        f"Chọn category để sửa:"
    )

    buttons = tg.build_bucket_buttons(buckets, "mg_sel")
    buttons.append([{"text": "➕ Add Category", "callback_data": "mg_add"}])
    await tg.send_with_buttons(msg, buttons)


# ─── Callback router ─────────────────────────────────────────
async def handle_manage_callback(parts: list[str], message_id: int):
    """Route all mg_* callbacks."""
    action = parts[1]

    if action == "back":
        await start_manage()
    elif action == "add":
        await _prompt_add_category_name()
    elif action == "trackcat":
        await _handle_track_only_button()
    elif action == "sel":
        bucket_id = "_".join(parts[2:])
        await _show_bucket_actions(bucket_id, message_id)
    elif action == "eamt":
        bucket_id = "_".join(parts[2:])
        await _prompt_edit_amount(bucket_id)
    elif action == "ren":
        bucket_id = "_".join(parts[2:])
        await _prompt_rename_bucket(bucket_id)
    elif action == "del":
        bucket_id = "_".join(parts[2:])
        await _confirm_delete_bucket(bucket_id, message_id)
    elif action == "cdel":
        bucket_id = "_".join(parts[2:])
        await _exec_delete_bucket(bucket_id, message_id)
    elif action == "subs":
        bucket_id = "_".join(parts[2:])
        await _show_sub_list(bucket_id)
    elif action == "ssel":
        bucket_id = parts[2]
        sub_key = "_".join(parts[3:])
        await _show_sub_actions(bucket_id, sub_key, message_id)
    elif action == "sren":
        bucket_id = parts[2]
        sub_key = "_".join(parts[3:])
        await _prompt_rename_sub(bucket_id, sub_key)
    elif action == "sdel":
        bucket_id = parts[2]
        sub_key = "_".join(parts[3:])
        await _exec_delete_sub(bucket_id, sub_key, message_id)
    elif action == "bback":
        bucket_id = "_".join(parts[2:])
        await _show_bucket_actions(bucket_id, message_id)


# ─── Bucket actions ───────────────────────────────────────────
async def _show_bucket_actions(bucket_id: str, message_id: int):
    """Show action menu for a specific bucket."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    bkt_status = sh.get_bucket_status(bucket_id, month_key)
    name = sh.bucket_label(bucket_id)
    subs = sh.get_sub_categories(bucket_id)

    if bkt_status["allocated"] > 0:
        pct = sh.calc_pct(bkt_status["spent"], bkt_status["allocated"])
        msg = (
            f"⚙️ *{name}*\n"
            f"Mode: 💰 Budgeted\n"
            f"Allocated: {sh.fmt_amount(bkt_status['allocated'])}\n"
            f"Spent: {sh.fmt_amount(bkt_status['spent'])} ({pct}%)\n"
            f"Sub-categories: {len(subs)} active"
        )
    else:
        msg = (
            f"⚙️ *{name}*\n"
            f"Mode: 🏷️ Tracking-only\n"
            f"Spent: {sh.fmt_amount(bkt_status['spent'])} tháng này\n"
            f"Sub-categories: {len(subs)} active"
        )
    await tg.edit_message(message_id, msg)
    await tg.send_with_buttons("Bạn muốn làm gì?", [
        [
            {"text": "✏️ Edit Amount", "callback_data": f"mg_eamt_{bucket_id}"},
            {"text": "📝 Rename",      "callback_data": f"mg_ren_{bucket_id}"},
        ],
        [
            {"text": "📂 Sub-categories", "callback_data": f"mg_subs_{bucket_id}"},
            {"text": "🗑️ Delete",         "callback_data": f"mg_del_{bucket_id}"},
        ],
        [{"text": "← Back", "callback_data": "mg_back"}],
    ])


# ─── Edit amount ──────────────────────────────────────────────
async def _prompt_edit_amount(bucket_id: str):
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    bkt_status = sh.get_bucket_status(bucket_id, month_key)
    name = sh.bucket_label(bucket_id)

    if bkt_status["allocated"] > 0:
        current = sh.fmt_amount(bkt_status["allocated"])
    else:
        current = "🏷️ tracking-only"

    sh.set_state(CHAT_ID, {**state, "step": "await_manage_amount", "edit_bucket_id": bucket_id})
    await tg.send_text(
        f"💰 *{name}* — hiện tại: {current}\n"
        f"Nhập số tiền mới (0 = chuyển sang tracking-only):"
    )


async def handle_manage_amount(text: str, state: dict):
    """Handle freetext input for new allocation amount.
    Cho phép amount = 0 → convert sang tracking mode.
    """
    try:
        digits = "".join(c for c in text if c.isdigit())
        amount = int(digits) if digits else 0
        assert amount >= 0
    except Exception:
        await tg.send_text("⚠️ Số tiền không hợp lệ. Thử lại (VD: 3000000 hoặc 0).")
        return

    bucket_id = state["edit_bucket_id"]
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"allocated": amount})
    sh.set_state(CHAT_ID, {**state, "step": "manage", "edit_bucket_id": None})
    if amount > 0:
        await tg.send_text(f"✅ Updated: {name} → *{sh.fmt_amount(amount)}*")
    else:
        await tg.send_text(f"✅ Updated: {name} → 🏷️ tracking-only")
    await start_manage()


# ─── Rename bucket ────────────────────────────────────────────
async def _prompt_rename_bucket(bucket_id: str):
    state = sh.get_state(CHAT_ID) or {}
    name = sh.bucket_label(bucket_id)

    sh.set_state(CHAT_ID, {**state, "step": "await_manage_rename", "edit_bucket_id": bucket_id})
    await tg.send_text(f"✏️ Tên hiện tại: {name}\nNhập tên mới:")


async def handle_manage_rename(text: str, state: dict):
    """Handle freetext input for new bucket name."""
    bucket_id = state["edit_bucket_id"]
    month_key = state.get("month_key", "")
    old_name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"name": text.strip()})
    sh.set_state(CHAT_ID, {**state, "step": "manage", "edit_bucket_id": None})
    await tg.send_text(f"✅ Renamed: {old_name} → *{text.strip()}*")
    await start_manage()


# ─── Delete bucket ────────────────────────────────────────────
async def _confirm_delete_bucket(bucket_id: str, message_id: int):
    """Show confirmation screen before deleting a bucket."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)
    tx_count = sh.count_bucket_transactions(bucket_id, month_key)

    msg = (
        f"⚠️ *Xóa {name}?*\n\n"
        f"Bucket này có {tx_count} transactions trong tháng.\n"
        f"Transactions đã categorize sẽ KHÔNG bị ảnh hưởng."
    )
    await tg.edit_message(message_id, msg)
    await tg.send_with_buttons("Confirm?", [
        [
            {"text": "❌ Confirm Delete", "callback_data": f"mg_cdel_{bucket_id}"},
            {"text": "← Cancel",          "callback_data": f"mg_bback_{bucket_id}"},
        ],
    ])


async def _exec_delete_bucket(bucket_id: str, message_id: int):
    """Execute soft delete on a bucket."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)

    sh.soft_delete_bucket(month_key, bucket_id)
    await tg.edit_message(message_id, f"🗑️ Deleted: {name}")
    await start_manage()


# ─── Sub-category list ────────────────────────────────────────
async def _show_sub_list(bucket_id: str):
    """Show all active sub-categories for a bucket."""
    name = sh.bucket_label(bucket_id)
    subs = sh.get_sub_categories(bucket_id)

    if not subs:
        await tg.send_with_buttons(
            f"📂 *{name}* — no sub-categories yet.\n"
            f"They'll be created automatically when you categorize transactions.",
            [[{"text": "← Back", "callback_data": f"mg_bback_{bucket_id}"}]],
        )
        return

    msg = f"📂 *Sub-categories of {name}*\n\n"
    for s in subs:
        msg += f"{s['label']}\n"

    buttons = [
        [
            {"text": s["label"], "callback_data": f"mg_ssel_{bucket_id}_{s['key']}"}
            for s in subs[i:i + 2]
        ]
        for i in range(0, len(subs), 2)
    ]
    buttons.append([{"text": "← Back", "callback_data": f"mg_bback_{bucket_id}"}])
    await tg.send_with_buttons(msg, buttons)


# ─── Sub-category actions ─────────────────────────────────────
async def _show_sub_actions(bucket_id: str, sub_key: str, message_id: int):
    """Show action menu for a specific sub-category."""
    name = sh.bucket_label(bucket_id)
    sub_label = sh.get_sub_label(bucket_id, sub_key)

    await tg.edit_message(message_id, f"⚙️ *{sub_label}*\n_(sub of {name})_")
    await tg.send_with_buttons("What do you want to do?", [
        [
            {"text": "📝 Rename", "callback_data": f"mg_sren_{bucket_id}_{sub_key}"},
            {"text": "🗑️ Delete", "callback_data": f"mg_sdel_{bucket_id}_{sub_key}"},
        ],
        [{"text": "← Back", "callback_data": f"mg_subs_{bucket_id}"}],
    ])


# ─── Rename sub-category ─────────────────────────────────────
async def _prompt_rename_sub(bucket_id: str, sub_key: str):
    state = sh.get_state(CHAT_ID) or {}
    sub_label = sh.get_sub_label(bucket_id, sub_key)

    sh.set_state(CHAT_ID, {
        **state, "step": "await_sub_rename",
        "edit_bucket_id": bucket_id, "edit_sub_key": sub_key,
    })
    await tg.send_text(f"✏️ Tên hiện tại: {sub_label}\nNhập tên mới:")


async def handle_sub_rename(text: str, state: dict):
    """Handle freetext input for new sub-category name."""
    bucket_id = state["edit_bucket_id"]
    sub_key = state["edit_sub_key"]
    old_label = sh.get_sub_label(bucket_id, sub_key)

    sh.update_sub_category(bucket_id, sub_key, text.strip())
    sh.set_state(CHAT_ID, {
        **state, "step": "manage",
        "edit_bucket_id": None, "edit_sub_key": None,
    })
    await tg.send_text(f"✅ Renamed: {old_label} → *{text.strip()}*")
    await _show_sub_list(bucket_id)


# ─── Delete sub-category ─────────────────────────────────────
async def _exec_delete_sub(bucket_id: str, sub_key: str, message_id: int):
    """Execute soft delete on a sub-category (no confirmation needed)."""
    sub_label = sh.get_sub_label(bucket_id, sub_key)

    sh.soft_delete_sub_category(bucket_id, sub_key)
    await tg.edit_message(message_id, f"🗑️ Deleted: {sub_label}")
    await _show_sub_list(bucket_id)


# ─── Add new category ────────────────────────────────────────
async def _prompt_add_category_name():
    """Prompt user to enter a name for the new category."""
    state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {**state, "step": "await_add_cat_name"})
    await tg.send_text(
        "➕ *Add New Category*\n\n"
        "Nhập tên category mới:\n"
        "_(VD: 🎮 Gaming, ✈️ Travel, 🍕 Food)_"
    )


async def handle_add_cat_name(text: str, state: dict):
    """Handle freetext input for new category name."""
    name = text.strip()
    if not name:
        await tg.send_text("⚠️ Tên không được để trống. Thử lại:")
        return

    # Generate a slug-style ID from the name
    nid = unicodedata.normalize("NFD", name.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)  # strip diacritics
    nid = re.sub(r"[^\w\s]", "", nid)            # strip emoji/symbols
    nid = re.sub(r"\s+", "_", nid.strip())
    nid = re.sub(r"[^a-z0-9_]", "", nid)
    if not nid:
        nid = "custom"

    # Check duplicate ID in current month
    month_key = state.get("month_key", "")
    existing = sh.get_active_buckets(month_key, force_refresh=True)
    if any(b["id"] == nid for b in existing):
        await tg.send_text(
            f"⚠️ Category *{name}* đã tồn tại rồi!\n"
            f"Nhập tên khác hoặc gửi /manage để quay lại."
        )
        return

    sh.set_state(CHAT_ID, {
        **state,
        "step": "await_add_cat_amount",
        "new_cat_name": name,
        "new_cat_id": nid,
    })
    await tg.send_with_buttons(
        f"💰 *{name}* — chọn mode:\n"
        f"• Nhập số tiền budget (VD: 2000000)\n"
        f"• Hoặc tap *Track only* để chỉ track không đặt budget",
        [[{"text": "🏷️ Track only", "callback_data": "mg_trackcat"}]],
    )


async def handle_add_cat_amount(text: str, state: dict):
    """Handle freetext input for new category amount and write to sheet.
    Cho phép amount = 0 → tracking mode.
    """
    try:
        digits = "".join(c for c in text if c.isdigit())
        amount = int(digits) if digits else 0
        assert amount >= 0
    except Exception:
        await tg.send_text("⚠️ Số tiền không hợp lệ. Thử lại (VD: 2000000 hoặc 0).")
        return

    await _save_new_category(state, amount)


async def _save_new_category(state: dict, amount: int):
    """Persist new category — shared bởi cả freetext amount và 'Track only' button."""
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

    # Clear temp state
    sh.set_state(CHAT_ID, {
        **state,
        "step": "manage",
        "new_cat_name": None,
        "new_cat_id": None,
    })

    if amount > 0:
        await tg.send_text(f"✅ Đã thêm: *{name}* — {sh.fmt_amount(amount)}")
    else:
        await tg.send_text(f"✅ Đã thêm: *{name}* — 🏷️ tracking-only")
    await start_manage()


async def _handle_track_only_button():
    """User tap 'Track only' button trong flow add category."""
    state = sh.get_state(CHAT_ID) or {}
    if state.get("step") != "await_add_cat_amount" or not state.get("new_cat_name"):
        await tg.send_text("⚠️ State không hợp lệ. Dùng /manage để bắt đầu lại.")
        return
    await _save_new_category(state, 0)
