"""
handlers/allocation.py — Monthly budget allocation flow
"""
from config import CHAT_ID
import sheets as sh
import telegram_api as tg
from i18n.core import t


async def start_monthly_allocation(from_cron: bool = False):
    """/allocate has two modes:

    1) FIRST-TIME setup (no buckets yet for this month):
       - from_cron=True  → simplified prompt: Keep prev / Set new (+ 1h auto-fallback)
       - from_cron=False → full wizard: Keep prev / Enter amounts / Track only / Skip

    2) EDIT mode (buckets already exist for this month): show the budget
       summary with per-bucket edit buttons + a 'Reset all' escape hatch.
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

    # ── Cron-triggered: simplified 2-option prompt ──────────────
    if from_cron and prev_buckets and any(b.get("allocated", 0) > 0 for b in prev_buckets):
        budgeted = [b for b in prev_buckets if b.get("allocated", 0) > 0]
        total_alloc = sum(b["allocated"] for b in budgeted)

        msg = (
            f"💰 *Budget tháng mới — {month_key}*\n\n"
            f"{t('al.prev_hint', month=prev_key)} *{sh.fmt_amount(total_alloc)}*\n\n"
            f"_⏰ 1h → auto-keep {prev_key}._"
        )

        sh.set_state(CHAT_ID, {
            "step":     "await_alloc_choice",
            "month_key": month_key,
            "copy_key":  prev_key,
        })

        buttons = [[
            {"text": t("al.btn_keep", month=prev_key), "callback_data": f"al_copy_{prev_key}"},
            {"text": t("al.btn_enter"),                 "callback_data": f"al_fresh_{month_key}"},
        ]]
        await tg.send_with_buttons(msg, buttons)
        return

    # ── Manual /allocate or cron without previous budget: full wizard ──
    msg  = f"{t('al.title')}\n\n"
    msg += f"{t('al.desc')}\n\n"
    if prev_buckets:
        budgeted = [b for b in prev_buckets if b.get("allocated", 0) > 0]
        if budgeted:
            total_alloc = sum(b["allocated"] for b in budgeted)
            msg += f"{t('al.prev_hint', month=prev_key)} *{sh.fmt_amount(total_alloc)}*\n\n"

    sh.set_state(CHAT_ID, {
        "step":     "await_alloc_choice",
        "month_key": month_key,
        "copy_key":  prev_key,
    })

    buttons_row1 = []
    if prev_buckets and any(b.get("allocated", 0) > 0 for b in prev_buckets):
        buttons_row1.append({
            "text":         t("al.btn_keep", month=prev_key),
            "callback_data": f"al_copy_{prev_key}",
        })
    buttons_row1.append({"text": t("al.btn_enter"), "callback_data": f"al_fresh_{month_key}"})
    buttons_row2 = [
        {"text": t("al.btn_track_all"), "callback_data": f"al_track_{month_key}"},
        {"text": t("btn.skip"),          "callback_data": f"al_skip_{month_key}"},
    ]
    await tg.send_with_buttons(msg, [buttons_row1, buttons_row2])


# ─── Edit mode (when buckets already exist) ──────────────────────

TYPE_BUDGET_EMOJI = "💰"


async def _show_edit_view(month_key: str, buckets: list[dict]):
    """Budget summary + per-bucket edit buttons + reset/done escape."""
    msg = f"{t('al.edit_title', month=month_key)}\n\n"
    total = 0
    for b in buckets:
        alloc = b.get("allocated", 0) or 0
        if alloc > 0:
            msg += f"{b['name']}   *{sh.fmt_amount(alloc)}*\n"
            total += alloc
        else:
            msg += f"{b['name']}   _{t('mg.tracking')}_\n"
    msg += f"─────────────────────\n*{t('al.summary_total')}: {sh.fmt_amount(total)}*\n"

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
        {"text": t("al.btn_add"), "callback_data": f"al_addbucket_{month_key}"},
    ])
    edit_rows.append([
        {"text": t("al.btn_reset"), "callback_data": f"al_resetall_{month_key}"},
        {"text": t("al.btn_close"), "callback_data": "al_close_none"},
    ])

    sh.set_state(CHAT_ID, {"step": "await_edit_choice", "month_key": month_key})
    await tg.send_with_buttons(msg, edit_rows)


async def _start_edit_bucket(bucket_id: str):
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    if not month_key:
        await tg.send_text(t("session_expired"))
        return
    buckets = sh.get_active_buckets(month_key)
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if not bucket:
        await tg.send_text(f"⚠️ Bucket `{bucket_id}` not found.")
        return
    sh.set_state(CHAT_ID, {
        **state,
        "step":            "await_edit_bucket_amount",
        "edit_bucket_id":  bucket_id,
        "edit_bucket_name": bucket["name"],
    })
    current_alloc = bucket.get("allocated", 0) or 0
    await tg.send_text(t("mg.edit_amount_prompt", name=bucket["name"], current=sh.fmt_amount(current_alloc)))


async def handle_edit_bucket_amount(text: str, state: dict):
    from utils import parse_budget_amount
    amount = parse_budget_amount(text)
    if amount is None:
        await tg.send_text(t("al.invalid_number"))
        return

    month_key = state.get("month_key", "")
    bucket_id = state.get("edit_bucket_id", "")
    if not month_key or not bucket_id:
        await tg.send_text(t("session_expired"))
        return

    # Find the bucket, update allocation, write back
    buckets = sh.get_active_buckets(month_key)
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if not bucket:
        await tg.send_text(f"⚠️ Bucket `{bucket_id}` not found.")
        sh.clear_state(CHAT_ID)
        return
    bucket["allocated"] = amount
    sh.write_budget_row(month_key, bucket)
    sh.invalidate_buckets_cache()

    # Re-render the edit view so the user sees the updated total
    refreshed = sh.get_active_buckets(month_key, force_refresh=True)
    await tg.send_text(
        t("mg.updated_amount", name=bucket["name"], amount=sh.fmt_amount(amount))
        if amount > 0 else
        t("mg.updated_tracking", name=bucket["name"])
    )
    await _show_edit_view(month_key, refreshed)


async def _reset_all_allocations(month_key: str):
    """Show confirmation before resetting all budgets."""
    await tg.send_with_buttons(
        t("al.reset_confirm"),
        [[
            {"text": t("btn.confirm_reset"), "callback_data": f"al_confirmreset_{month_key}"},
            {"text": t("mg.btn_cancel_del"), "callback_data": "al_close_none"},
        ]],
    )


async def _close_edit_view():
    sh.clear_state(CHAT_ID)
    await tg.send_text(t("al.skip"))


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
    elif action == "confirmreset": await _start_fresh(rest)
    elif action == "close":       await _close_edit_view()
    elif action == "skipbucket":  await _skip_current_bucket()


async def _handle_copy(prev_key: str):
    state    = sh.get_state(CHAT_ID)
    month_key = (state or {}).get("month_key", "")
    prev_buckets = sh.get_active_buckets(prev_key)

    if not prev_buckets:
        await tg.send_text(t("al.no_prev", month=prev_key))
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
    if current:
        buckets = current
    else:
        prev_key = sh._previous_month_key(month_key)
        prev_buckets = sh.get_active_buckets(prev_key) if prev_key else []
        buckets = prev_buckets if prev_buckets else sh.get_default_buckets()
    sh.set_state(CHAT_ID, {
        "step":          "await_alloc_amount",
        "month_key":     month_key,
        "buckets":       buckets,
        "current_index": 0,
        "allocations":   [],
    })
    await _ask_next_bucket()


async def _start_track_only(month_key: str):
    """Bootstrap categories ở tracking mode — không hỏi amount."""
    async with sh.bootstrap_lock:
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        if not buckets:
            sh.bootstrap_buckets_from_previous_month(month_key, reset_allocated=True)
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
        if not buckets:
            sh.bootstrap_default_categories(month_key)
    buckets = sh.get_active_buckets(month_key, force_refresh=True)
    sh.clear_state(CHAT_ID)
    msg  = f"🏷️ *Tracking mode — {month_key}*\n\n"
    for b in buckets:
        msg += f"{b['name']}\n"
    msg += f"\n{t('al.skip')}"
    await tg.send_text(msg)


async def _skip_allocation():
    """User chọn skip — vẫn bootstrap categories nếu chưa có để bot hoạt động."""
    state = sh.get_state(CHAT_ID) or {}
    month_key = state.get("month_key", "")
    if month_key:
        async with sh.bootstrap_lock:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_buckets_from_previous_month(month_key, reset_allocated=True)
                buckets = sh.get_active_buckets(month_key, force_refresh=True)
            if not buckets:
                sh.bootstrap_default_categories(month_key)
    sh.clear_state(CHAT_ID)
    await tg.send_text(t("al.skip"))


async def _skip_current_bucket():
    """User tapped skip on a bucket in the wizard — set it to 0 (tracking-only) and advance."""
    state = sh.get_state(CHAT_ID) or {}
    if state.get("step") != "await_alloc_amount":
        await tg.send_text(t("session_expired"))
        return
    bucket = state["buckets"][state["current_index"]]
    allocations = list(state.get("allocations") or []) + [{**bucket, "allocated": 0}]
    next_index = state["current_index"] + 1

    if next_index >= len(state["buckets"]):
        sh.set_state(CHAT_ID, {**state, "allocations": allocations, "step": "await_add_bucket"})
        await _show_alloc_summary(state["month_key"], allocations)
    else:
        sh.set_state(CHAT_ID, {**state, "current_index": next_index, "allocations": allocations})
        await _ask_next_bucket()



async def _ask_next_bucket():
    state  = sh.get_state(CHAT_ID)
    idx    = state["current_index"]
    bucket = state["buckets"][idx]
    total  = len(state["buckets"])
    await tg.send_with_buttons(
        t("al.bucket_prompt", idx=idx + 1, total=total,
          name=bucket["name"], month=state["month_key"]),
        [[{"text": t("al.btn_skip_bucket"), "callback_data": "al_skipbucket_none"}]],
    )


async def handle_alloc_amount_input(text: str, state: dict):
    """0 is valid here: it means 'track this bucket but no spending cap'
    (the bucket appears in /report under TRACKING, no budget % bar). Used
    when the user wants to monitor a category without committing a number.
    """
    from utils import parse_budget_amount
    amount = parse_budget_amount(text)
    if amount is None:
        await tg.send_text(t("al.invalid_number"))
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
    await tg.send_text(t("al.new_name_prompt"))


async def handle_new_bucket_name(text: str, state: dict):
    import unicodedata, re
    nid = unicodedata.normalize("NFD", text.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)
    nid = re.sub(r"\s+", "_", nid)
    nid = re.sub(r"[^a-z0-9_]", "", nid)
    sh.set_state(CHAT_ID, {**state, "step": "await_new_bucket_amount", "new_bucket_name": text, "new_bucket_id": nid})
    await tg.send_text(f"💰 *{text}* — budget {state['month_key']}?\n_(VD: 2500000)_")


async def handle_new_bucket_amount(text: str, state: dict):
    from utils import parse_budget_amount
    amount = parse_budget_amount(text)
    if amount is None or amount <= 0:
        await tg.send_text(t("mg.add_amount_err"))
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
    msg   = f"{t('al.summary_title', month=month_key)}\n\n"
    total = 0
    for b in allocations:
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{b['name']}   *{sh.fmt_amount(alloc)}*\n"
            total += alloc
        else:
            msg += f"{b['name']}   _{t('mg.tracking')}_\n"
    msg += f"─────────────────────\n{t('al.summary_total')}   *{sh.fmt_amount(total)}*\n\n{t('al.summary_add_more')}"
    await tg.send_with_buttons(msg, [[
        {"text": t("al.btn_add"),  "callback_data": f"al_addbucket_{month_key}"},
        {"text": t("btn.save_done"), "callback_data": f"al_done_{month_key}"},
    ]])


async def _finalize_allocation():
    state       = sh.get_state(CHAT_ID) or {}
    month_key   = state.get("month_key", "")
    allocations = state.get("allocations") or []

    for b in allocations:
        sh.write_budget_row(month_key, b)
    sh.invalidate_buckets_cache()

    sh.clear_state(CHAT_ID)

    msg   = f"{t('al.done_title', month=month_key)}\n\n"
    total = 0
    for b in allocations:
        alloc = b.get("allocated", 0)
        if alloc > 0:
            msg += f"{b['name']}   {sh.fmt_amount(alloc)}\n"
            total += alloc
        else:
            msg += f"{b['name']}   {t('mg.tracking')}\n"
    msg += (
        f"─────────────────────\n"
        f"{t('al.summary_total')}   *{sh.fmt_amount(total)}*\n\n"
        f"{t('al.done_tip')}"
    )
    await tg.send_text(msg)
