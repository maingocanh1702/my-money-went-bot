"""
handlers/cashback.py — Manage cashback tracking rules + view summary.

Entry point: /cashback command.

User flow:
  /cashback        → show monthly cashback summary + ⚙️ Rules button
  /cashback rules  → list rules per account + ➕ Add
  ➕ Add           → pick account → enter keyword (or skip) → enter % → saved
  Tap a rule       → action menu (✏️ Edit / 🗑️ Delete)

Cashback rules are per-account, matching by keyword in expense description.
Two modes:
  - pct > 0: auto-calculate cashback = pct% × expense amount on confirm
  - pct = 0: match incoming webhook (tiền vào) by keyword → log actual amount
"""
from datetime import datetime
import pytz

from config import CHAT_ID, TIMEZONE
import sheets as sh
import telegram_api as tg


# ─── Entry point ──────────────────────────────────────────────
async def cmd_cashback(text: str):
    """Entry point: /cashback or /cashback rules."""
    parts = text.strip().split()
    if len(parts) >= 2 and parts[1].lower() == "rules":
        await _show_rules_list()
    else:
        await _show_summary()


# ─── Summary ─────────────────────────────────────────────────
async def _show_summary():
    """Monthly cashback summary across all accounts."""
    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))
    month_label = datetime.now(tz).strftime("%m/%Y")

    summary = sh.get_cashback_summary(month_key)
    accounts = sh.get_active_accounts()
    acc_names = {a["id"]: a["name"] for a in accounts}

    if not summary:
        rules = sh.get_cashback_rules()
        if not rules:
            msg = (
                "💰 *Cashback Tracking*\n\n"
                "_Chưa có cashback rule nào._\n\n"
                "Tạo rule để bot tự tính cashback khi bạn chi tiêu, "
                "hoặc match tiền hoàn vào từ ngân hàng.\n\n"
                "VD: Cake Credit 1% mặc định, 5% cho Shopee"
            )
        else:
            msg = (
                f"💰 *Cashback — {month_label}*\n\n"
                f"_Chưa có cashback nào tháng này._\n"
                f"Đã config {len(rules)} rule(s) — cashback sẽ tự tích lũy khi có giao dịch."
            )
        buttons = [[{"text": "⚙️ Rules", "callback_data": "cb_rules"}]]
        await tg.send_with_buttons(msg, buttons)
        return

    grand_total = sum(s["total"] for s in summary)

    lines = [f"💰 *Cashback — {month_label}*\n"]

    for s in summary:
        acc_name = acc_names.get(s["account_id"], s["account_id"])
        lines.append(f"*{acc_name}:* {sh.fmt_amount(s['total'])}")

        # Breakdown by rule
        by_rule = sh.get_cashback_by_rule(s["account_id"], month_key)
        for br in by_rule:
            if br["keyword"]:
                label = f'{br["cashback_pct"]}% {br["keyword"]}'
            elif br["cashback_pct"] > 0:
                label = f'{br["cashback_pct"]}% mặc định'
            else:
                label = "webhook"
            lines.append(f"   {label}: {sh.fmt_amount(br['total'])} ({br['count']} tx)")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━")
    lines.append(f"*Tổng: {sh.fmt_amount(grand_total)}*")

    buttons = [[{"text": "⚙️ Rules", "callback_data": "cb_rules"}]]
    await tg.send_with_buttons("\n".join(lines), buttons)


# ─── Rules list ──────────────────────────────────────────────
async def _show_rules_list():
    """List all active cashback rules with action buttons."""
    rules = sh.get_cashback_rules(force_refresh=True)
    accounts = sh.get_active_accounts()
    acc_names = {a["id"]: a["name"] for a in accounts}

    if not rules:
        msg = (
            "⚙️ *Cashback Rules*\n\n"
            "_Chưa có rule nào._\n\n"
            "Mỗi rule gắn với 1 account/thẻ:\n"
            "• Keyword rỗng = default rule (áp dụng mọi chi tiêu)\n"
            "• Keyword cụ thể = chỉ match giao dịch chứa keyword đó\n"
            "• % = 0 → match tiền vào (webhook) thay vì tự tính"
        )
        buttons = [
            [{"text": "➕ Add Rule", "callback_data": "cb_add"}],
            [{"text": "← Cashback", "callback_data": "cb_back"}],
        ]
        await tg.send_with_buttons(msg, buttons)
        return

    msg = "⚙️ *Cashback Rules*\n\n"
    for r in rules:
        acc_name = acc_names.get(r["account_id"], r["account_id"])
        kw_disp = f'`{r["keyword"]}`' if r["keyword"] else "_mặc định_"
        pct_disp = f'{r["cashback_pct"]}%' if r["cashback_pct"] > 0 else "webhook"
        limits = []
        if r.get("cb_min", 0) > 0:
            limits.append(f'min {sh.fmt_amount(r["cb_min"])}')
        if r.get("cb_max", 0) > 0:
            limits.append(f'max {sh.fmt_amount(r["cb_max"])}')
        if r.get("cb_cap", 0) > 0:
            limits.append(f'cap {sh.fmt_amount(r["cb_cap"])}/mo')
        limit_str = f' · _{"  ".join(limits)}_' if limits else ""
        msg += f"• {acc_name} · {kw_disp} → {pct_disp}{limit_str}\n"
    msg += "\nTap 1 rule để sửa hoặc xóa:"

    buttons = []
    for r in rules:
        acc_name = acc_names.get(r["account_id"], r["account_id"])
        kw = r["keyword"] or "default"
        pct = f'{r["cashback_pct"]}%' if r["cashback_pct"] > 0 else "webhook"
        label = f"{acc_name} · {kw} → {pct}"
        if len(label) > 60:
            label = label[:57] + "…"
        buttons.append([{"text": label, "callback_data": f"cb_sel_{r['row_num']}"}])
    buttons.append([{"text": "➕ Add Rule", "callback_data": "cb_add"}])
    buttons.append([{"text": "← Cashback", "callback_data": "cb_back"}])

    await tg.send_with_buttons(msg, buttons)


# ─── Callback router ─────────────────────────────────────────
async def handle_cashback_callback(parts: list[str], message_id: int):
    """Route all cb_* callbacks."""
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "back":
        await _show_summary()
    elif action == "rules":
        await _show_rules_list()
    elif action == "add":
        await _prompt_pick_account()
    elif action == "acc":
        # cb_acc_{account_id} — user picked account for new rule
        account_id = "_".join(parts[2:])
        await _prompt_keyword(account_id)
    elif action == "skipkw":
        # cb_skipkw — user wants default rule (no keyword)
        await _prompt_pct("")
    elif action == "sel":
        # cb_sel_{row_num} — user tapped a rule
        row_num = int(parts[2])
        await _show_rule_actions(row_num, message_id)
    elif action == "del":
        row_num = int(parts[2])
        await _confirm_delete(row_num, message_id)
    elif action == "cdel":
        row_num = int(parts[2])
        await _exec_delete(row_num, message_id)
    elif action == "cancel":
        await tg.edit_message(message_id, "❌ Hủy.")
        await _show_rules_list()
    elif action == "nolimit":
        # cb_nolimit — skip limits step, save with no limits
        state = sh.get_state(CHAT_ID) or {}
        await _save_rule(state, cb_min=0, cb_max=0, cb_cap=0)
    elif action == "suggest":
        # cb_suggest_{account_id}_{keyword} — from keyword save suggestion
        # cb_suggest_skip — dismiss
        if len(parts) >= 3 and parts[2] == "skip":
            await tg.edit_message(message_id, "👌")
        elif len(parts) >= 4:
            account_id = parts[2]
            keyword = "_".join(parts[3:])  # keyword may contain underscores
            # Check if rule already exists
            existing = sh.match_cashback_rule(account_id, keyword, "*")
            if existing and existing.get("keyword") == sh._normalize_for_match(keyword):
                await tg.edit_message(
                    message_id,
                    f"ℹ️ Cashback rule cho `{keyword}` trên account này đã có rồi.",
                )
            else:
                # Pre-fill account + keyword, prompt for %
                sh.set_state(CHAT_ID, {
                    "step": "cashback_await_pct",
                    "cb_account_id": account_id,
                    "cb_keyword": keyword,
                })
                acc = sh.find_account_by_id(account_id)
                acc_name = acc["name"] if acc else account_id
                await tg.edit_message(
                    message_id,
                    f"💰 Thêm cashback rule: `{keyword}` → *{acc_name}*",
                )
                await tg.send_text(
                    f"📊 *Cashback %* cho keyword `{keyword}`\n\n"
                    f"Nhập số:\n"
                    f"• `1` → 1% cashback\n"
                    f"• `5` → 5%\n"
                    f"• `0.5` → 0.5%\n"
                    f"• `0` → dùng amount thực tế từ webhook tiền vào"
                )


# ─── Add rule flow ───────────────────────────────────────────

async def _prompt_pick_account():
    """Step 1: Pick an account for the new cashback rule."""
    accounts = sh.get_active_accounts()
    if not accounts:
        await tg.send_text(
            "⚠️ Chưa có account nào. Dùng /accounts để setup account trước."
        )
        return

    sh.set_state(CHAT_ID, {"step": "cashback_pick_account"})

    buttons = []
    for a in accounts:
        label = f"{a['name']} ({a['type']})"
        buttons.append([{"text": label, "callback_data": f"cb_acc_{a['id']}"}])
    buttons.append([{"text": "❌ Hủy", "callback_data": "cb_cancel"}])

    await tg.send_with_buttons(
        "➕ *New Cashback Rule*\n\nChọn account/thẻ:",
        buttons,
    )


async def _prompt_keyword(account_id: str):
    """Step 2: Ask for keyword (or skip for default rule)."""
    state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {
        **state,
        "step": "cashback_await_keyword",
        "cb_account_id": account_id,
    })
    await tg.send_with_buttons(
        "✍️ *Nhập keyword* cho rule này\n\n"
        "VD: `shopee`, `grab`, `highland`\n\n"
        "Hoặc bỏ trống → rule mặc định áp dụng mọi chi tiêu của account này.",
        [[{"text": "⏩ Bỏ trống (default rule)", "callback_data": "cb_skipkw"}]],
    )


async def handle_cashback_keyword_input(text: str, state: dict):
    """User typed keyword for the new cashback rule."""
    keyword = (text or "").strip()
    if len(keyword) > 60:
        await tg.send_text("⚠️ Keyword quá dài (>60 ký tự). Thử lại.")
        return
    await _prompt_pct(keyword)


async def _prompt_pct(keyword: str):
    """Step 3: Ask for cashback percentage."""
    state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {
        **state,
        "step": "cashback_await_pct",
        "cb_keyword": keyword,
    })
    kw_disp = f"`{keyword}`" if keyword else "_mặc định (all)_"
    await tg.send_text(
        f"📊 *Cashback %* cho keyword {kw_disp}\n\n"
        f"Nhập số:\n"
        f"• `1` → 1% cashback\n"
        f"• `5` → 5%\n"
        f"• `0.5` → 0.5%\n"
        f"• `0` → dùng amount thực tế từ webhook tiền vào\n\n"
        f"_(VD: Cake Credit thường hoàn 1% mặc định, 5% cho online shopping)_"
    )


async def handle_cashback_pct_input(text: str, state: dict):
    """User typed cashback percentage → prompt for limits."""
    raw = (text or "").strip().replace(",", ".")
    try:
        pct = float(raw)
    except ValueError:
        await tg.send_text("⚠️ Số không hợp lệ. Nhập số (VD: `1`, `5`, `0.5`, `0`).")
        return
    if pct < 0 or pct > 100:
        await tg.send_text("⚠️ Phần trăm phải từ 0 đến 100.")
        return

    account_id = state.get("cb_account_id", "")
    keyword = state.get("cb_keyword", "")

    if not account_id:
        await tg.send_text("⚠️ Hết phiên. Thử /cashback rules lại.")
        return

    # Prompt for limits (optional step)
    sh.set_state(CHAT_ID, {
        **state,
        "step": "cashback_await_limits",
        "cb_pct": pct,
    })
    await tg.send_with_buttons(
        f"⚙️ *Giới hạn cashback* (optional)\n\n"
        f"Nhập theo format: `min max cap`\n"
        f"• `min`: cashback tối thiểu mỗi tx (VND)\n"
        f"• `max`: cashback tối đa mỗi tx (VND)\n"
        f"• `cap`: tổng cashback tối đa/tháng (VND)\n\n"
        f"VD:\n"
        f"• `0 200000 0` → max 200k/tx, không cap tháng\n"
        f"• `0 0 500000` → không limit tx, cap 500k/tháng\n"
        f"• `1000 50000 200000` → min 1k, max 50k/tx, cap 200k/tháng\n\n"
        f"Hoặc bỏ trống → không giới hạn.",
        [[{"text": "⏩ Bỏ trống (no limits)", "callback_data": "cb_nolimit"}]],
    )


async def handle_cashback_limits_input(text: str, state: dict):
    """User typed limits: 'min max cap' → save rule."""
    raw = (text or "").strip()
    parts = raw.split()
    cb_min, cb_max, cb_cap = 0.0, 0.0, 0.0

    if len(parts) >= 1:
        try:
            cb_min = float(parts[0].replace(",", ""))
        except ValueError:
            await tg.send_text("⚠️ Giá trị min không hợp lệ. Format: `min max cap` (VD: `0 200000 0`)")
            return
    if len(parts) >= 2:
        try:
            cb_max = float(parts[1].replace(",", ""))
        except ValueError:
            await tg.send_text("⚠️ Giá trị max không hợp lệ.")
            return
    if len(parts) >= 3:
        try:
            cb_cap = float(parts[2].replace(",", ""))
        except ValueError:
            await tg.send_text("⚠️ Giá trị cap không hợp lệ.")
            return

    await _save_rule(state, cb_min, cb_max, cb_cap)


async def _save_rule(state: dict, cb_min: float = 0, cb_max: float = 0, cb_cap: float = 0):
    """Final step: save the cashback rule with all parameters."""
    account_id = state.get("cb_account_id", "")
    keyword = state.get("cb_keyword", "")
    pct = state.get("cb_pct", 0)

    if not account_id:
        await tg.send_text("⚠️ Hết phiên. Thử /cashback rules lại.")
        return

    ok = sh.add_cashback_rule(
        account_id, keyword, pct,
        category_id="*", cb_min=cb_min, cb_max=cb_max, cb_cap=cb_cap,
    )
    sh.set_state(CHAT_ID, {"step": ""})

    if ok:
        acc = sh.find_account_by_id(account_id)
        acc_name = acc["name"] if acc else account_id
        kw_disp = f"`{keyword}`" if keyword else "_mặc định_"
        pct_disp = f"{pct}%" if pct > 0 else "webhook (dùng amount thực tế)"
        limits_lines = []
        if cb_min > 0:
            limits_lines.append(f"• Min/tx: {sh.fmt_amount(cb_min)}")
        if cb_max > 0:
            limits_lines.append(f"• Max/tx: {sh.fmt_amount(cb_max)}")
        if cb_cap > 0:
            limits_lines.append(f"• Cap/tháng: {sh.fmt_amount(cb_cap)}")
        limits_str = "\n".join(limits_lines)
        if limits_str:
            limits_str = f"\n{limits_str}"
        await tg.send_text(
            f"✅ Đã thêm cashback rule:\n"
            f"• Account: *{acc_name}*\n"
            f"• Keyword: {kw_disp}\n"
            f"• Cashback: {pct_disp}{limits_str}"
        )
    else:
        await tg.send_text("⚠️ Rule đã tồn tại hoặc lỗi khi lưu.")

    await _show_rules_list()


# ─── Rule actions ────────────────────────────────────────────

async def _show_rule_actions(row_num: int, message_id: int):
    """Show action menu for a specific rule."""
    rules = sh.get_cashback_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.edit_message(message_id, "⚠️ Rule không còn tồn tại.")
        await _show_rules_list()
        return

    acc = sh.find_account_by_id(rule["account_id"])
    acc_name = acc["name"] if acc else rule["account_id"]
    kw_disp = f'`{rule["keyword"]}`' if rule["keyword"] else "_mặc định_"
    pct_disp = f'{rule["cashback_pct"]}%' if rule["cashback_pct"] > 0 else "webhook"

    lines = [
        f"💰 *Cashback Rule*\n",
        f"Account: *{acc_name}*",
        f"Keyword: {kw_disp}",
        f"Rate: {pct_disp}",
    ]
    if rule.get("cb_min", 0) > 0:
        lines.append(f'Min/tx: {sh.fmt_amount(rule["cb_min"])}')
    if rule.get("cb_max", 0) > 0:
        lines.append(f'Max/tx: {sh.fmt_amount(rule["cb_max"])}')
    if rule.get("cb_cap", 0) > 0:
        lines.append(f'Cap/tháng: {sh.fmt_amount(rule["cb_cap"])}')

    await tg.edit_message(message_id, "\n".join(lines))
    await tg.send_with_buttons("Chọn:", [
        [{"text": "🗑️ Xóa", "callback_data": f"cb_del_{row_num}"}],
        [{"text": "← Back", "callback_data": "cb_rules"}],
    ])


async def _confirm_delete(row_num: int, message_id: int):
    """Ask for confirmation before deleting."""
    rules = sh.get_cashback_rules(force_refresh=True)
    rule = next((r for r in rules if r["row_num"] == row_num), None)
    if not rule:
        await tg.edit_message(message_id, "⚠️ Rule không còn tồn tại.")
        return

    acc = sh.find_account_by_id(rule["account_id"])
    acc_name = acc["name"] if acc else rule["account_id"]
    kw = rule["keyword"] or "default"

    await tg.edit_message(message_id, f"⚠️ *Xóa rule này?*\n{acc_name} · {kw}")
    await tg.send_with_buttons("Confirm?", [[
        {"text": "❌ Xóa", "callback_data": f"cb_cdel_{row_num}"},
        {"text": "← Hủy", "callback_data": "cb_cancel"},
    ]])


async def _exec_delete(row_num: int, message_id: int):
    """Execute the soft delete."""
    sh.soft_delete_cashback_rule(row_num)
    await tg.edit_message(message_id, "🗑️ Đã xóa cashback rule.")
    await _show_rules_list()
