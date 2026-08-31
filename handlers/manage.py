"""
handlers/manage.py — Edit & Delete categories, sub-categories, allocations
Entry point: /manage command
"""
import unicodedata
import re
from config import CHAT_ID, TIMEZONE, DAILY_BUCKET_ID
import sheets as sh
import telegram_api as tg
from datetime import datetime
import pytz
from i18n.core import t


# ─── Entry point ──────────────────────────────────────────────
async def start_manage():
    """Entry point: /manage command. Clone previous month before defaults."""
    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        # Race-safe bootstrap (dùng cùng lock với sepay)
        async with sh.bootstrap_lock:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_buckets_from_previous_month(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_default_categories(month_key)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)

    sh.set_state(CHAT_ID, {"step": "manage", "month_key": month_key})
    await _show_category_list(month_key, buckets)


async def _show_category_list(month_key: str, buckets: list[dict]):
    """Show all active buckets with selection buttons."""
    msg = f"{t('mg.title', month=month_key)}\n\n"
    total = 0
    for b in buckets:
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{b['name']}   *{sh.fmt_amount(alloc)}*\n"
            total += alloc
        else:
            msg += f"{b['name']}   _{t('mg.tracking')}_\n"
    msg += (
        f"─────────────────────\n"
        f"{t('mg.total_budgeted')}   *{sh.fmt_amount(total)}*\n\n"
        f"{t('mg.choose_edit')}"
    )

    buttons = tg.build_bucket_buttons(buckets, "mg_sel")
    buttons.append([{"text": t("mg.btn_add"), "callback_data": "mg_add"}])
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
    elif action == "dcap":
        bucket_id = "_".join(parts[2:])
        await _prompt_edit_daily_cap(bucket_id)
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
        await _confirm_delete_sub(bucket_id, sub_key, message_id)
    elif action == "csdel":
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
            f"{t('mg.budgeted', amount=sh.fmt_amount(bkt_status['allocated']))}\n"
            f"{t('mg.spent', amount=sh.fmt_amount(bkt_status['spent']), pct=pct)}\n"
            f"{t('mg.sub_count', count=len(subs))}"
        )
    else:
        msg = (
            f"⚙️ *{name}*\n"
            f"{t('mg.tracking_only')}\n"
            f"{t('mg.spent_month', amount=sh.fmt_amount(bkt_status['spent']))}\n"
            f"{t('mg.sub_count', count=len(subs))}"
        )

    # Daily Spending: surface the per-day cap (/today compares against it) —
    # previously the cap was only editable by hand in the sheet.
    is_daily = bucket_id == DAILY_BUCKET_ID
    if is_daily:
        buckets = sh.get_active_buckets(month_key)
        bkt = next((b for b in buckets if b["id"] == bucket_id), None)
        cap = (bkt or {}).get("daily_cap")
        cap_disp = sh.fmt_amount(cap) if cap else "—"
        msg += f"\n{t('mg.daily_cap_line', amount=cap_disp)}"

    await tg.edit_message(message_id, msg)
    buttons = [
        [
            {"text": t("mg.btn_edit_budget"), "callback_data": f"mg_eamt_{bucket_id}"},
            {"text": t("mg.btn_rename"),      "callback_data": f"mg_ren_{bucket_id}"},
        ],
        [
            {"text": t("mg.btn_subs"),   "callback_data": f"mg_subs_{bucket_id}"},
            {"text": t("mg.btn_delete"), "callback_data": f"mg_del_{bucket_id}"},
        ],
    ]
    if is_daily:
        buttons.insert(1, [{"text": t("mg.btn_daily_cap"), "callback_data": f"mg_dcap_{bucket_id}"}])
    buttons.append([{"text": t("btn.back"), "callback_data": "mg_back"}])
    await tg.send_with_buttons(t("mg.what_to_do"), buttons)


# ─── Edit amount ──────────────────────────────────────────────
async def _prompt_edit_amount(bucket_id: str):
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    bkt_status = sh.get_bucket_status(bucket_id, month_key)
    name = sh.bucket_label(bucket_id)

    if bkt_status["allocated"] > 0:
        current = sh.fmt_amount(bkt_status["allocated"])
    else:
        current = t("mg.tracking")

    sh.set_state(CHAT_ID, {**state, "step": "await_manage_amount", "edit_bucket_id": bucket_id})
    await tg.send_text(t("mg.edit_amount_prompt", name=name, current=current))


async def handle_manage_amount(text: str, state: dict):
    """Handle freetext input for new allocation amount.
    Cho phép amount = 0 → convert sang tracking mode.
    Input không hợp lệ bị reject — trước đây "abc" âm thầm thành 0
    (tracking-only) khiến bucket mất budget ngoài ý muốn.
    """
    from utils import parse_budget_amount
    amount = parse_budget_amount(text)
    if amount is None:
        await tg.send_text(t("mg.edit_amount_err"))
        return

    bucket_id = state["edit_bucket_id"]
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"allocated": amount})
    sh.set_state(CHAT_ID, {**state, "step": "manage", "edit_bucket_id": None})
    if amount > 0:
        await tg.send_text(t("mg.updated_amount", name=name, amount=sh.fmt_amount(amount)))
    else:
        await tg.send_text(t("mg.updated_tracking", name=name))
    await start_manage()


# ─── Edit daily cap (Daily Spending bucket) ───────────────────
async def _prompt_edit_daily_cap(bucket_id: str):
    """Prompt for the per-day cap that /today + the nightly recap use.

    Previously this cap was only editable by hand in the Budget Config sheet
    while /today told users to "use /manage" — a dead end. Now it's a button."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)
    buckets = sh.get_active_buckets(month_key)
    bkt = next((b for b in buckets if b["id"] == bucket_id), None)
    cap = (bkt or {}).get("daily_cap")
    current = sh.fmt_amount(cap) if cap else "—"

    sh.set_state(CHAT_ID, {**state, "step": "await_manage_daily_cap", "edit_bucket_id": bucket_id})
    await tg.send_text(t("mg.daily_cap_prompt", name=name, current=current))


async def handle_manage_daily_cap(text: str, state: dict):
    """Freetext input for the daily cap. 0 = turn the cap off (/today switches
    to tracking mode and the nightly recap stops firing)."""
    from utils import parse_budget_amount
    amount = parse_budget_amount(text)
    if amount is None:
        await tg.send_text(t("mg.daily_cap_err"))
        return

    bucket_id = state["edit_bucket_id"]
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"daily_cap": amount or None})
    sh.set_state(CHAT_ID, {**state, "step": "manage", "edit_bucket_id": None})
    if amount > 0:
        await tg.send_text(t("mg.daily_cap_set", name=name, amount=sh.fmt_amount(amount)))
    else:
        await tg.send_text(t("mg.daily_cap_off", name=name))
    await start_manage()


# ─── Rename bucket ────────────────────────────────────────────
async def _prompt_rename_bucket(bucket_id: str):
    state = sh.get_state(CHAT_ID) or {}
    name = sh.bucket_label(bucket_id)

    sh.set_state(CHAT_ID, {**state, "step": "await_manage_rename", "edit_bucket_id": bucket_id})
    await tg.send_text(t("mg.rename_prompt", name=name))


async def handle_manage_rename(text: str, state: dict):
    """Handle freetext input for new bucket name."""
    bucket_id = state["edit_bucket_id"]
    month_key = state.get("month_key", "")
    old_name = sh.bucket_label(bucket_id)

    sh.update_bucket(month_key, bucket_id, {"name": text.strip()})
    sh.set_state(CHAT_ID, {**state, "step": "manage", "edit_bucket_id": None})
    await tg.send_text(t("mg.renamed", old=old_name, new=text.strip()))
    await start_manage()


# ─── Delete bucket ────────────────────────────────────────────
async def _confirm_delete_bucket(bucket_id: str, message_id: int):
    """Show confirmation screen before deleting a bucket."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)
    tx_count = sh.count_bucket_transactions(bucket_id, month_key)

    msg = t("mg.delete_confirm", name=name, count=tx_count)
    await tg.send_with_buttons(msg, [
        [
            {"text": t("btn.confirm_delete"), "callback_data": f"mg_cdel_{bucket_id}"},
            {"text": t("mg.btn_cancel_del"),  "callback_data": f"mg_bback_{bucket_id}"},
        ],
    ])


async def _exec_delete_bucket(bucket_id: str, message_id: int):
    """Execute soft delete on a bucket."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    name = sh.bucket_label(bucket_id)

    sh.soft_delete_bucket(month_key, bucket_id)
    await tg.edit_message(message_id, t("mg.deleted", name=name))
    await start_manage()


# ─── Sub-category list ────────────────────────────────────────
async def _show_sub_list(bucket_id: str):
    """Show all active sub-categories for a bucket."""
    name = sh.bucket_label(bucket_id)
    subs = sh.get_sub_categories(bucket_id)

    if not subs:
        await tg.send_with_buttons(
            t("mg.subs_empty", name=name),
            [[{"text": t("btn.back"), "callback_data": f"mg_bback_{bucket_id}"}]],
        )
        return

    msg = f"{t('mg.subs_title', name=name)}\n\n"
    for s in subs:
        msg += f"{s['label']}\n"

    buttons = [
        [
            {"text": s["label"], "callback_data": f"mg_ssel_{bucket_id}_{s['key']}"}
            for s in subs[i:i + 2]
        ]
        for i in range(0, len(subs), 2)
    ]
    buttons.append([{"text": t("btn.back"), "callback_data": f"mg_bback_{bucket_id}"}])
    await tg.send_with_buttons(msg, buttons)


# ─── Sub-category actions ─────────────────────────────────────
async def _show_sub_actions(bucket_id: str, sub_key: str, message_id: int):
    """Show action menu for a specific sub-category."""
    name = sh.bucket_label(bucket_id)
    sub_label = sh.get_sub_label(bucket_id, sub_key)

    await tg.edit_message(message_id, t("mg.sub_actions_title", sub=sub_label, parent=name))
    await tg.send_with_buttons(t("mg.what_to_do"), [
        [
            {"text": t("mg.btn_rename"), "callback_data": f"mg_sren_{bucket_id}_{sub_key}"},
            {"text": t("mg.btn_delete"), "callback_data": f"mg_sdel_{bucket_id}_{sub_key}"},
        ],
        [{"text": t("btn.back"), "callback_data": f"mg_subs_{bucket_id}"}],
    ])


# ─── Rename sub-category ─────────────────────────────────────
async def _prompt_rename_sub(bucket_id: str, sub_key: str):
    state = sh.get_state(CHAT_ID) or {}
    sub_label = sh.get_sub_label(bucket_id, sub_key)

    sh.set_state(CHAT_ID, {
        **state, "step": "await_sub_rename",
        "edit_bucket_id": bucket_id, "edit_sub_key": sub_key,
    })
    await tg.send_text(t("mg.sub_rename_prompt", name=sub_label))


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
    await tg.send_text(t("mg.renamed", old=old_label, new=text.strip()))
    await _show_sub_list(bucket_id)


# ─── Delete sub-category ─────────────────────────────────────────
async def _confirm_delete_sub(bucket_id: str, sub_key: str, message_id: int):
    """Show confirmation before deleting a sub-category."""
    name = sh.bucket_label(bucket_id)
    sub_label = sh.get_sub_label(bucket_id, sub_key)
    await tg.send_with_buttons(
        t("mg.sub_delete_confirm", sub=sub_label, parent=name),
        [[
            {"text": t("btn.confirm_delete"), "callback_data": f"mg_csdel_{bucket_id}_{sub_key}"},
            {"text": t("mg.btn_cancel_del"),  "callback_data": f"mg_subs_{bucket_id}"},
        ]],
    )


async def _exec_delete_sub(bucket_id: str, sub_key: str, message_id: int):
    """Execute soft delete on a sub-category after confirmation."""
    sub_label = sh.get_sub_label(bucket_id, sub_key)

    sh.soft_delete_sub_category(bucket_id, sub_key)
    await tg.edit_message(message_id, t("mg.sub_deleted", name=sub_label))
    await _show_sub_list(bucket_id)


# ─── Add new category ────────────────────────────────────────
async def _prompt_add_category_name():
    """Prompt user to enter a name for the new category."""
    state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {**state, "step": "await_add_cat_name"})
    await tg.send_text(t("mg.add_title"))


async def handle_add_cat_name(text: str, state: dict):
    """Handle freetext input for new category name."""
    name = text.strip()
    if not name:
        await tg.send_text(t("mg.add_name_empty"))
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
        await tg.send_text(t("mg.add_duplicate", name=name))
        return

    sh.set_state(CHAT_ID, {
        **state,
        "step": "await_add_cat_amount",
        "new_cat_name": name,
        "new_cat_id": nid,
    })
    await tg.send_with_buttons(
        t("mg.add_mode", name=name),
        [[{"text": t("mg.btn_track_only"), "callback_data": "mg_trackcat"}]],
    )


async def handle_add_cat_amount(text: str, state: dict):
    """Handle freetext input for new category amount and write to sheet.
    Cho phép amount = 0 → tracking mode. Input không hợp lệ bị reject
    (không âm thầm chuyển thành 0 như trước).
    """
    from utils import parse_budget_amount
    amount = parse_budget_amount(text)
    if amount is None:
        await tg.send_text(t("mg.add_amount_err"))
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
        await tg.send_text(t("mg.added_budgeted", name=name, amount=sh.fmt_amount(amount)))
    else:
        await tg.send_text(t("mg.added_tracking", name=name))
    await start_manage()


async def _handle_track_only_button():
    """User tap 'Track only' button trong flow add category."""
    state = sh.get_state(CHAT_ID) or {}
    if state.get("step") != "await_add_cat_amount" or not state.get("new_cat_name"):
        await tg.send_text(t("invalid_state"))
        return
    await _save_new_category(state, 0)
