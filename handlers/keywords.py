"""
handlers/keywords.py — Manage auto-categorization keyword rules.

Entry point: /keywords command.

User flow:
  /keywords        → list rules + ➕ Add button
  ➕ Add           → bot asks for keyword(s) → user picks bucket → saved
  Tap a rule       → action menu (✏️ Đổi keyword / 🔄 Đổi category / 🗑️ Xóa)

When a SePay/email transaction arrives whose description contains a
matching keyword (longest-match wins), the transaction is auto-categorized
in handlers/sepay.py — no picker needed. User can still tap "Sai mục?" to
override the auto-pick.
"""
import re
from datetime import datetime
import pytz

from config import CHAT_ID, TIMEZONE
import sheets as sh
import telegram_api as tg
from i18n.core import t


# ─── Entry point ──────────────────────────────────────────────
async def start_keywords():
    """Entry point: /keywords command. Show all active rules."""
    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))

    sh.set_state(CHAT_ID, {"step": "keywords", "month_key": month_key})
    await _show_rule_list()


async def _show_rule_list():
    """List active rules with delete buttons + an Add button."""
    rules = sh.get_keyword_rules(force_refresh=True)

    if not rules:
        msg = (
            f"{t('kw.title')}\n\n"
            f"_{t('kw.empty')}_"
        )
        buttons = [[{"text": t("kw.btn_add"), "callback_data": "kw_add"}]]
        await tg.send_with_buttons(msg, buttons)
        return

    msg = f"{t('kw.title')}\n\n"
    for r in rules:
        bucket_name = sh.bucket_label(r["bucket_id"])
        sub = f" · {r['sub_label']}" if r["sub_label"] else ""
        msg += f"`{r['keyword']}` → {bucket_name}{sub}\n"

    # One row per rule → opens an action menu (edit keyword / change cat / delete)
    buttons = []
    for r in rules:
        bucket_name = sh.bucket_label(r["bucket_id"])
        label = f"🔑 {r['keyword']} → {bucket_name}"
        # Telegram button text limit ~64 chars; truncate to be safe
        if len(label) > 60:
            label = label[:57] + "…"
        buttons.append([{"text": label, "callback_data": f"kw_sel_{r['row_num']}"}])
    buttons.append([{"text": t("kw.btn_add"), "callback_data": "kw_add"}])

    await tg.send_with_buttons(msg, buttons)


# ─── Callback router ─────────────────────────────────────────
async def handle_keywords_callback(parts: list[str], message_id: int):
    """Route all kw_* callbacks."""
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "add":
        await _prompt_keyword_input()
    elif action == "back":
        await start_keywords()
    elif action == "pick":
        # callback: kw_pick_{bucket_id}  (new rule(s) → pick bucket)
        bucket_id = "_".join(parts[2:])
        await _save_rule_with_bucket(bucket_id, message_id)
    elif action == "sel":
        # callback: kw_sel_{row_num}  (tapped a rule → show action menu)
        row_num = int(parts[2])
        await _show_rule_actions(row_num, message_id)
    elif action == "eren":
        # callback: kw_eren_{row_num}  (edit → rename keyword)
        row_num = int(parts[2])
        await _prompt_edit_keyword(row_num)
    elif action == "ebkt":
        # callback: kw_ebkt_{row_num}  (edit → change category)
        row_num = int(parts[2])
        await _prompt_edit_bucket(row_num, message_id)
    elif action == "pickb":
        # callback: kw_pickb_{row_num}_{bucket_id}  (commit new bucket for existing rule)
        row_num = int(parts[2])
        bucket_id = "_".join(parts[3:])
        await _save_edited_bucket(row_num, bucket_id, message_id)
    elif action == "del":
        row_num = int(parts[2])
        await _confirm_delete(row_num, message_id)
    elif action == "cdel":
        row_num = int(parts[2])
        await _exec_delete(row_num, message_id)
    elif action == "cancel":
        await tg.edit_message(message_id, t("cancelled"))
        await start_keywords()


# ─── Add flow ─────────────────────────────────────────────────
async def _prompt_keyword_input():
    """Ask user to type the keyword(s) for the new rule(s)."""
    state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {**state, "step": "await_keyword_input"})
    await tg.send_text(
        "✍️ *Nhập keyword*\n\n"
        "• 1 keyword: `highland`\n"
        "• Nhiều keyword cách nhau dấu phẩy → tất cả map cùng 1 category:\n"
        "  `highland, tch, the coffee house, revi`\n\n"
        "Bot match khi description giao dịch *chứa* keyword "
        "(không phân biệt hoa/thường, dấu)."
    )


async def handle_keyword_input(text: str, state: dict):
    """User typed keyword(s) — supports bulk via comma/semicolon. Validate each,
    store list in state, then ask once for the bucket.
    """
    raw = (text or "").strip()
    if not raw:
        await tg.send_text(t("kw.keyword_empty"))
        return

    # Split on comma or semicolon. Trim + normalize each token, drop empties + dups.
    tokens = [tok.strip() for tok in re.split(r"[,;]+", raw)]
    keywords: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        if len(tok) > 60:
            await tg.send_text(t("kw.keyword_too_long", kw=tok))
            return
        norm = sh._normalize_for_match(tok)
        if norm and norm not in keywords:
            keywords.append(norm)

    if not keywords:
        await tg.send_text(t("kw.keyword_invalid"))
        return

    tz = pytz.timezone(TIMEZONE)
    month_key = state.get("month_key") or sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        await tg.send_text(t("kw.no_categories"))
        sh.set_state(CHAT_ID, {**state, "step": "keywords"})
        return

    # Check for existing rules with the same keyword(s)
    existing_rules = sh.get_keyword_rules(force_refresh=True)
    existing_map = {r["keyword"]: r["bucket_id"] for r in existing_rules}
    conflicts: list[str] = []
    for kw in keywords:
        if kw in existing_map:
            old_bucket = sh.bucket_label(existing_map[kw])
            conflicts.append(f"  • `{kw}` → {old_bucket}")

    sh.set_state(CHAT_ID, {
        **state,
        "step": "keywords_pick_bucket",
        "pending_keywords": keywords,
    })

    preview = ", ".join(f"`{k}`" for k in keywords)
    count_label = "" if len(keywords) == 1 else f" ({len(keywords)} keywords)"
    conflict_note = ""
    if conflicts:
        conflict_note = (
            "\n\n⚠️ *Đã có rule:*\n"
            + "\n".join(conflicts)
            + "\n_Chọn category mới sẽ ghi đè rule cũ._"
        )
    buttons = tg.build_bucket_buttons(buckets, "kw_pick")
    buttons.append([{"text": t("btn.cancel"), "callback_data": "kw_back"}])
    await tg.send_with_buttons(
        t("kw.pick_bucket", count_label=count_label, preview=preview, conflict=conflict_note),
        buttons,
    )


async def _save_rule_with_bucket(bucket_id: str, message_id: int):
    """Persist the (keyword(s), bucket_id) rules then return to the list."""
    state = sh.get_state(CHAT_ID) or {}
    keywords = state.get("pending_keywords") or []

    # Backward-compat: state set by an older version of this handler
    if not keywords and state.get("pending_keyword"):
        keywords = [state["pending_keyword"]]

    if not keywords:
        await tg.edit_message(message_id, t("session_expired"))
        return

    bucket_name = sh.bucket_label(bucket_id)
    added: list[str] = []
    skipped: list[str] = []
    for kw in keywords:
        if sh.add_keyword_rule(kw, bucket_id, sub_label=""):
            added.append(kw)
        else:
            skipped.append(kw)

    sh.set_state(CHAT_ID, {
        **state,
        "step": "keywords",
        "pending_keywords": None,
        "pending_keyword": None,
    })

    sections: list[str] = []
    if added:
        added_block = "\n".join(f"  • `{k}`" for k in added)
        sections.append(f"✅ Đã thêm {len(added)} rule → *{bucket_name}*:\n{added_block}")
    if skipped:
        skipped_block = "\n".join(f"  • `{k}`" for k in skipped)
        sections.append(f"⚠️ {len(skipped)} rule đã tồn tại sẵn:\n{skipped_block}")

    await tg.edit_message(message_id, "\n\n".join(sections))
    await _show_rule_list()


# ─── Delete flow ─────────────────────────────────────────────
async def _confirm_delete(row_num: int, message_id: int):
    """Ask for confirmation before deleting a rule."""
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.edit_message(message_id, t("kw.rule_not_found"))
        return

    bucket_name = sh.bucket_label(rule["bucket_id"])
    msg = t("kw.delete_confirm", keyword=rule["keyword"], bucket=bucket_name)
    await tg.edit_message(message_id, msg)
    await tg.send_with_buttons(t("mg.what_to_do"), [[
        {"text": t("kw.btn_confirm_del"), "callback_data": f"kw_cdel_{row_num}"},
        {"text": t("mg.btn_cancel_del"), "callback_data": "kw_cancel"},
    ]])


async def _exec_delete(row_num: int, message_id: int):
    """Execute the soft delete and refresh the list."""
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)

    sh.soft_delete_keyword_rule(row_num)

    if rule:
        bucket_name = sh.bucket_label(rule["bucket_id"])
        await tg.edit_message(
            message_id,
            f"🗑️ Đã xóa: `{rule['keyword']}` → {bucket_name}",
        )
    else:
        await tg.edit_message(message_id, "🗑️ Đã xóa rule.")
    await _show_rule_list()


# ─── Edit flow ───────────────────────────────────────────────
async def _show_rule_actions(row_num: int, message_id: int):
    """Show the per-rule action menu when the user taps a rule in the list."""
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.edit_message(message_id, t("kw.rule_not_found"))
        await start_keywords()
        return

    bucket_name = sh.bucket_label(rule["bucket_id"])
    sub = f" · {rule['sub_label']}" if rule["sub_label"] else ""
    msg = t("kw.rule_detail", keyword=rule["keyword"], bucket=f"{bucket_name}{sub}")
    await tg.edit_message(message_id, msg)
    await tg.send_with_buttons(t("mg.what_to_do"), [
        [
            {"text": t("kw.btn_edit_keyword"), "callback_data": f"kw_eren_{row_num}"},
            {"text": t("kw.btn_edit_bucket"),  "callback_data": f"kw_ebkt_{row_num}"},
        ],
        [
            {"text": t("mg.btn_delete"), "callback_data": f"kw_del_{row_num}"},
            {"text": t("btn.back"),      "callback_data": "kw_back"},
        ],
    ])


# --- Edit: rename keyword ---------------------------------------
async def _prompt_edit_keyword(row_num: int):
    """Ask user to type the new keyword text for the rule."""
    state = sh.get_state(CHAT_ID) or {}
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.send_text("⚠️ Rule không còn tồn tại.")
        await start_keywords()
        return

    sh.set_state(CHAT_ID, {
        **state,
        "step": "await_edit_keyword",
        "editing_row": row_num,
    })
    await tg.send_text(
        f"✏️ Keyword hiện tại: `{rule['keyword']}`\n\n"
        f"Nhập keyword mới (1 keyword duy nhất). "
        f"Muốn add nhiều keyword cùng lúc thì xóa rule này và dùng *➕ Thêm rule*."
    )


async def handle_edit_keyword_input(text: str, state: dict):
    """User typed the new keyword for an existing rule. Single-keyword only.

    Bulk edit (multiple comma-separated values) is rejected — the user is told
    to delete + re-add via the bulk add flow instead.
    """
    raw = (text or "").strip()
    if not raw:
        await tg.send_text("⚠️ Keyword rỗng. Thử lại hoặc /keywords để hủy.")
        return

    if re.search(r"[,;]", raw):
        await tg.send_text(
            "⚠️ Chỉ nhận *1 keyword* khi sửa.\n"
            "Muốn add nhiều keyword 1 lúc → xóa rule này và dùng *➕ Thêm rule*."
        )
        return

    if len(raw) > 60:
        await tg.send_text("⚠️ Keyword quá dài (>60 ký tự). Thử lại.")
        return

    new_norm = sh._normalize_for_match(raw)
    if not new_norm:
        await tg.send_text("⚠️ Keyword không hợp lệ. Thử lại.")
        return

    row_num = state.get("editing_row")
    if not row_num:
        await tg.send_text("⚠️ Hết phiên. Thử /keywords lại.")
        return

    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.send_text("⚠️ Rule không còn tồn tại.")
        sh.set_state(CHAT_ID, {**state, "step": "keywords", "editing_row": None})
        await start_keywords()
        return

    old_keyword = rule["keyword"]
    if new_norm == old_keyword:
        await tg.send_text("ℹ️ Keyword không đổi.")
        sh.set_state(CHAT_ID, {**state, "step": "keywords", "editing_row": None})
        await _show_rule_list()
        return

    ok = sh.update_keyword_rule(row_num, keyword=new_norm)
    sh.set_state(CHAT_ID, {**state, "step": "keywords", "editing_row": None})

    if ok:
        bucket_name = sh.bucket_label(rule["bucket_id"])
        await tg.send_text(
            f"✅ Đã đổi: `{old_keyword}` → `{new_norm}`\n_(category: {bucket_name})_"
        )
    else:
        await tg.send_text("⚠️ Lỗi khi cập nhật rule. Thử lại.")
    await _show_rule_list()


# --- Edit: change bucket ----------------------------------------
async def _prompt_edit_bucket(row_num: int, message_id: int):
    """Show bucket buttons so the user can re-route an existing rule."""
    state = sh.get_state(CHAT_ID) or {}
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.edit_message(message_id, "⚠️ Rule không còn tồn tại.")
        await start_keywords()
        return

    tz = pytz.timezone(TIMEZONE)
    month_key = state.get("month_key") or sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)

    if not buckets:
        await tg.edit_message(
            message_id,
            "⚠️ Chưa có category nào. Dùng /manage để tạo category trước."
        )
        return

    current_bucket = sh.bucket_label(rule["bucket_id"])
    msg = (
        f"🔑 `{rule['keyword']}`\n"
        f"Hiện tại: *{current_bucket}*\n\n"
        f"Đổi sang category nào?"
    )
    await tg.edit_message(message_id, msg)

    # callback: kw_pickb_{row_num}_{bucket_id}
    buttons = [
        {"text": b["name"], "callback_data": f"kw_pickb_{row_num}_{b['id']}"}
        for b in buckets
    ]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([{"text": "← Hủy", "callback_data": f"kw_sel_{row_num}"}])
    await tg.send_with_buttons("Chọn category:", rows)


async def _save_edited_bucket(row_num: int, bucket_id: str, message_id: int):
    """Persist the new bucket on an existing rule and refresh the list."""
    rules = sh.get_keyword_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.edit_message(message_id, "⚠️ Rule không còn tồn tại.")
        await start_keywords()
        return

    if rule["bucket_id"] == bucket_id:
        await tg.edit_message(message_id, "ℹ️ Category không đổi.")
        await _show_rule_list()
        return

    ok = sh.update_keyword_rule(row_num, bucket_id=bucket_id)
    if ok:
        old_bucket = sh.bucket_label(rule["bucket_id"])
        new_bucket = sh.bucket_label(bucket_id)
        await tg.edit_message(
            message_id,
            f"✅ Đã đổi category cho `{rule['keyword']}`:\n"
            f"{old_bucket} → *{new_bucket}*",
        )
    else:
        await tg.edit_message(message_id, "⚠️ Lỗi khi cập nhật rule.")
    await _show_rule_list()
