"""handlers/accounts.py — account onboarding + /accounts list + /transfer + /cc pay.

Onboarding flow (applies uniformly to bank/debit/credit/cash):
  1. Webhook delivers a tx with an unmapped identifier → resolver returns
     `new_identifier` → sepay.py calls `prompt_new_account(...)`.
  2. `prompt_new_account` persists a row in the `Pending Accounts` sheet
     keyed by `setup_key = md5(source_key)[:12]` and sends a Telegram
     message with callback_data carrying that key.
  3. Setup remains valid for 24h even after many subsequent transactions
     overwrite the in-memory BOT_STATE — when the user finally taps
     "Setup", we look the pending row back up by setup_key.
  4. Once the wizard commits, the pending row is marked `completed`.

State keys used DURING the wizard (transient — written only after user
taps Setup, cleared on commit):
    step                 — see below
    pending_setup_key    — handle to the Pending Accounts row
    pending_source_key   — convenience copy of the source_key
    pending_identifier   — raw identifier (for display)
    pending_account      — partially-filled dict the wizard accumulates
    new_acct_row_num     — Transactions row that triggered onboarding

Steps:
    await_new_account_name      → user types display name
    await_new_account_id        → user types slug (or "auto" to derive from name)
    await_new_account_type      → inline buttons: bank/debit/credit/cash
    await_new_account_currency  → inline buttons: VND/HKD/USD/Other
    await_new_account_balance   → for bank/debit/cash: starting balance (number)
    await_credit_limit          → for credit: hạn mức
    await_credit_statement      → statement_day (1-28)
    await_credit_due            → due_day (1-28)
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
import pytz

from config import CHAT_ID, TIMEZONE
import sheets as sh
import telegram_api as tg


# ─── Helpers ──────────────────────────────────────────────────


def _slugify(name: str) -> str:
    s = unicodedata.normalize("NFD", name.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("đ", "d")
    s = re.sub(r"[^a-z0-9_]+", "_", s).strip("_")
    return s or "account"


def _state() -> dict:
    return sh.get_state(CHAT_ID) or {}


def _set(extra: dict):
    sh.set_state(CHAT_ID, {**_state(), **extra})


def _mask(identifier: str) -> str:
    """Mask account-number-like identifiers for display.
    Keep last 4, mask the rest. Leave short tokens (e.g. "default") alone.
    """
    s = (identifier or "").strip()
    if len(s) <= 4 or not any(ch.isdigit() for ch in s):
        return s
    return "*" * (len(s) - 4) + s[-4:]


# ─── Entry: ping when resolver returns new_identifier ──────────


async def prompt_new_account(source_key: str, identifier: str, tx_row_num: int):
    """Send a one-line onboarding prompt to the user.

    Persists the pending entry to the `Pending Accounts` sheet so setup
    survives any number of subsequent state-overwriting transactions
    within a 24h TTL window. Callback_data carries the setup_key so
    the user can tap "Setup" at any time, not just before the next tx.
    """
    setup_key = sh.add_pending_account(
        source_key=source_key,
        identifier=identifier,
        tx_row_num=int(tx_row_num) if tx_row_num else 0,
    )
    if not setup_key:
        # Unexpected — source_key was empty. Bail silently rather than
        # spamming a broken prompt.
        print(f"[accounts] prompt_new_account skipped (empty source_key)")
        return

    masked = _mask(identifier)
    # Plain parens around backtick code — `_(...)_` italic-wrap silently fails
    # in Telegram legacy Markdown when the code segment contains underscores
    # (e.g. source_key="sepay:02635252601" or "email_cake:cake_cc").
    msg = (
        f"🔍 *Account chưa map:* `{masked}`\n"
        f"(source: `{source_key}`)\n\n"
        f"Bot không biết account/card này. Setup ngay?\n"
        f"_Còn hiệu lực 24h kể cả khi có tx khác đến._"
    )
    buttons = [[
        {"text": "✅ Setup",  "callback_data": f"acc_setup_{setup_key}"},
        {"text": "⏭️ Skip",   "callback_data": f"acc_skip_{setup_key}"},
    ]]
    await tg.send_with_buttons(msg, buttons)


# ─── Callback router ───────────────────────────────────────────


async def handle_accounts_callback(parts: list[str], message_id: int):
    """All `acc_*` callback_data routes here.

    Callback formats:
        acc_setup_<setup_key>     → start onboarding for that pending row
        acc_skip_<setup_key>      → mark pending row skipped
        acc_type_<bank|...>       → wizard step (transient state)
        acc_cur_<VND|HKD|...>     → wizard step (transient state)
    """
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "setup":
        setup_key = parts[2] if len(parts) >= 3 else ""
        await _start_setup(message_id, setup_key)
    elif action == "skip":
        setup_key = parts[2] if len(parts) >= 3 else ""
        if setup_key:
            sh.mark_pending_skipped(setup_key)
        await tg.edit_message(message_id, "⏭️ Đã skip — tx ghi không gắn account.")
        sh.clear_state(CHAT_ID)
    elif action == "type":
        # acc_type_{bank|debit|credit|cash}
        await _on_type_picked(parts[2], message_id)
    elif action == "cur":
        # acc_cur_{VND|HKD|USD|other}
        await _on_currency_picked(parts[2], message_id)


# ─── State machine ─────────────────────────────────────────────


async def _start_setup(message_id: int, setup_key: str):
    """Look up the pending row, hydrate BOT_STATE, ask for account name.

    `setup_key` arrives in the callback_data — it survives any number of
    transactions arriving between prompt and tap.
    """
    if not setup_key:
        await tg.edit_message(
            message_id,
            "⚠️ Callback thiếu setup_key (prompt cũ?). Chờ tx tiếp theo nhé."
        )
        return

    entry = sh.get_pending_by_setup_key(setup_key)
    if not entry:
        await tg.edit_message(
            message_id,
            "⚠️ Phiên setup đã hết hạn hoặc đã hoàn tất. /accounts để add tay."
        )
        return

    _set({
        "step":                "await_new_account_name",
        "pending_setup_key":   setup_key,
        "pending_source_key":  entry["source_key"],
        "pending_identifier":  entry["identifier"],
        "new_acct_row_num":    entry["tx_row_num"],
        "pending_account":     {},
    })
    masked = _mask(entry["identifier"])
    await tg.edit_message(
        message_id,
        f"📝 *Setup account mới* — `{masked}`\n\n"
        f"Tên hiển thị (vd: `TCB Tiêu dùng`, `Cake Visa ****8421`):",
    )


async def handle_new_account_name(text: str, state: dict):
    name = text.strip()
    if not (1 <= len(name) <= 60):
        await tg.send_text("⚠️ Tên 1-60 ký tự. Thử lại.")
        return
    pending = state.get("pending_account") or {}
    pending["name"] = name
    pending["id"] = _slugify(name)
    _set({"pending_account": pending, "step": "await_new_account_type"})
    # Phase 1 OSS: bank / debit / cash. Credit-card support deferred.
    buttons = [[
        {"text": "🏦 Bank",  "callback_data": "acc_type_bank"},
        {"text": "💳 Debit", "callback_data": "acc_type_debit"},
    ], [
        {"text": "💵 Cash",  "callback_data": "acc_type_cash"},
    ]]
    # Note: avoid italic wrapper `_(...)_` around backtick-code; Telegram
    # legacy Markdown silently rejects when the code segment contains an
    # underscore (which _slugify produces for spaced names like "TPB 2601").
    await tg.send_with_buttons(f"Loại tài khoản? (slug: `{pending['id']}`)", buttons)


async def _on_type_picked(acc_type: str, message_id: int):
    """Phase 1 is VND-only — currency step skipped entirely. Account types
    accepted: bank / debit / cash. Credit-card support deferred from
    Phase 1 OSS scope.
    """
    if acc_type not in ("bank", "debit", "cash"):
        return
    state = _state()
    pending = state.get("pending_account") or {}
    pending["type"] = acc_type
    pending["currency"] = "VND"
    pending["starting_balance"] = 0
    await tg.edit_message(message_id, f"Type: *{acc_type}* ✅  (VND)")
    # 3-step wizard: name → type → commit. No balance / limit prompt.
    await _commit({**state, "pending_account": pending})


# Legacy callback handler kept for wizards that landed at
# await_new_account_currency under the old code path; new flow doesn't
# trigger this state anymore.
async def _on_currency_picked(currency: str, message_id: int):
    state = _state()
    pending = state.get("pending_account") or {}
    pending["currency"] = currency
    if pending.get("type") == "credit":
        _set({"pending_account": pending, "step": "await_credit_limit"})
        await tg.edit_message(message_id, f"Currency: *{currency}* ✅")
        await tg.send_text(
            "🧾 Credit card setup\n\n"
            f"*Hạn mức* ({currency})? (số, vd `30000000`)"
        )
    else:
        pending["starting_balance"] = 0
        await tg.edit_message(message_id, f"Currency: *{currency}* ✅")
        await _commit({**state, "pending_account": pending})


def _parse_money(text: str) -> float | None:
    s = re.sub(r"[^\d.]", "", text.strip())
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# Legacy handler kept for backward compatibility with wizards that started
# under the old prompt-for-balance flow (state="await_new_account_balance").
# The new flow skips straight from currency → commit for non-credit accounts.
async def handle_new_account_balance(text: str, state: dict):
    val = _parse_money(text)
    if val is None or val < 0:
        await tg.send_text("⚠️ Số không hợp lệ. Nhập số dương (vd `1000000`).")
        return
    pending = state.get("pending_account") or {}
    pending["starting_balance"] = val
    _set({"pending_account": pending})
    await _commit(state)


async def handle_credit_limit(text: str, state: dict):
    """After limit, ask current outstanding so the bot's outstanding starts
    at the user's real debt (not 0). Without this, /report shows 'dư nợ 0'
    on day one even if the card already has prior-cycle debt.
    """
    val = _parse_money(text)
    if val is None or val <= 0:
        await tg.send_text("⚠️ Hạn mức phải là số dương.")
        return
    pending = state.get("pending_account") or {}
    pending["credit_limit"] = val
    _set({"pending_account": pending, "step": "await_credit_outstanding"})
    await tg.send_text(
        f"💳 *Dư nợ hiện tại* (VND)?\n"
        f"(số đang nợ trên thẻ ngay lúc setup, vd `3000000`. "
        f"`0` nếu thẻ chưa dùng / đã trả hết.)"
    )


async def handle_credit_outstanding(text: str, state: dict):
    """Last step of credit wizard. Outstanding starts here; /cc pay later
    will decrement it as user pays off statements.
    """
    val = _parse_money(text)
    if val is None or val < 0:
        await tg.send_text("⚠️ Dư nợ phải ≥ 0. Nhập số hợp lệ (vd `3000000` hoặc `0`).")
        return
    pending = state.get("pending_account") or {}
    limit = float(pending.get("credit_limit") or 0)
    if val > limit:
        await tg.send_text(
            f"⚠️ Dư nợ ({sh.fmt_amount(val)}) lớn hơn hạn mức ({sh.fmt_amount(limit)})."
            f" Kiểm tra lại số."
        )
        return
    pending["starting_outstanding"] = val
    pending["starting_balance"] = 0  # not used for credit; safe default
    _set({"pending_account": pending})
    await _commit({**state, "pending_account": pending})


async def _commit(state: dict):
    """Write the account row + backfill the triggering tx + any other recent
    unresolved tx whose source matches.
    """
    pending = state.get("pending_account") or {}
    source_key = state.get("pending_source_key") or ""
    trigger_row = state.get("new_acct_row_num")

    if not pending.get("id") or not pending.get("type") or not pending.get("currency"):
        await tg.send_text("⚠️ Thiếu dữ liệu, hủy. Thử lại bằng /accounts add.")
        sh.clear_state(CHAT_ID)
        return

    # Resolve the wizard outcome into one of three states inside a single
    # critical section so concurrent webhooks can't race.
    #
    # 1. source_key already bound to some account  → "bound_existing"
    #    (resolver should have matched and skipped the prompt; if we land
    #    here it's a parallel-onboarding race — use the winner).
    #
    # 2. slug already exists with a different account → "linked_to_slug"
    #    Common case: user previously did `/accounts add` with no source
    #    binding (or under a different source), tx now arrives for THIS
    #    account, wizard names the same account again. Treat as
    #    re-onboarding from a new source — add source_key to existing
    #    account, do not error.
    #
    # 3. otherwise → "created_new"
    bind_message: str | None = None
    async with sh.account_lock:
        existing_by_source = (
            sh.find_account_by_source_key(source_key) if source_key else None
        )
        if existing_by_source:
            account_id = existing_by_source["id"]
            bind_message = (
                f"ℹ️ Account `{account_id}` đã có sẵn (parallel onboarding) — dùng cái cũ."
            )
        else:
            ok = sh.add_account(
                account_id=pending["id"],
                name=pending["name"],
                acc_type=pending["type"],
                currency=pending["currency"],
                source_keys=[source_key] if source_key else [],
                starting_balance=float(pending.get("starting_balance") or 0),
                credit_limit=float(pending.get("credit_limit") or 0),
                starting_outstanding=float(pending.get("starting_outstanding") or 0),
                statement_day=pending.get("statement_day"),
                due_day=pending.get("due_day"),
            )
            if ok:
                account_id = pending["id"]
            else:
                # Slug conflict. Differentiate "re-onboard same account from
                # new source" (auto-link) vs "user picked an unrelated name
                # that happens to collide" (refuse).
                slug_match = sh.find_account_by_id(pending["id"])
                if slug_match and source_key:
                    sh.add_source_key_to_account(slug_match["id"], source_key)
                    account_id = slug_match["id"]
                    bind_message = (
                        f"🔗 Account `{account_id}` đã có sẵn — đã link thêm source "
                        f"`{source_key}` vào account này."
                    )
                else:
                    # Manual onboarding (no source) hitting an existing slug,
                    # or slug genuinely conflicting — bail with guidance.
                    await tg.send_text(
                        f"⚠️ Slug `{pending['id']}` đã tồn tại. "
                        f"Hủy. Thử lại với tên khác (vd thêm số / hậu tố)."
                    )
                    sh.clear_state(CHAT_ID)
                    return

    # Backfill: triggering tx + any other unresolved tx in last 24h with the
    # same source_key (resolver re-runs to verify).
    backfilled = _backfill_recent(account_id, source_key, trigger_row)

    # Additional backfill: tx that landed BEFORE this account existed but
    # carry the same source_key in col U. Covers the gap between "first
    # webhook arrives" and "user finishes wizard" — and any historical tx
    # written by the post-Phase-C deploy that share this source. Safe even
    # when source_key is empty (function no-ops).
    src_backfilled = sh.backfill_account_id_by_source_key(account_id, source_key)
    if src_backfilled:
        backfilled = (backfilled or 0) + src_backfilled

    # Mark the queued pending row as completed so its setup button no
    # longer activates if user taps the old prompt again.
    setup_key = state.get("pending_setup_key") or ""
    if setup_key:
        sh.mark_pending_completed(setup_key)

    sh.clear_state(CHAT_ID)
    if bind_message:
        # Linked to existing account (case 1 or 2 above) — explain what
        # happened so the user doesn't think we created a duplicate.
        summary = bind_message
    else:
        summary = (
            f"✅ Account *{pending['name']}* đã setup\n"
            f"  · slug: `{account_id}`\n"
            f"  · type: {pending['type']} · {pending['currency']}\n"
        )
        if source_key:
            summary += f"  · source: `{source_key}`\n"
    if backfilled:
        summary += f"\n🔁 Đã backfill {backfilled} tx gần đây."
    await tg.send_text(summary)


# ─── /accounts command (list + add) ──────────────────────────


TYPE_EMOJI = {"bank": "🏦", "debit": "💳", "credit": "🧾", "cash": "💵"}


def _account_list_lines() -> list[str]:
    """Render `/accounts` list view: one block per active account.

    Project goal is tracking tx per account, not maintaining absolute
    balance — so this view intentionally omits running_balance and
    outstanding_balance. It surfaces what the user needs to verify their
    onboarding state: name, type, currency, and which source_keys map to
    this account (so they can tell whether a future SePay/email tx will
    auto-route to it).
    """
    accounts = sh.get_active_accounts(force_refresh=True)
    if not accounts:
        return ["_Chưa có account nào. Dùng `/accounts add` để tạo, hoặc đợi tx mới đến — bot sẽ tự ping._"]

    lines: list[str] = []
    for a in accounts:
        emoji = TYPE_EMOJI.get(a["type"], "•")
        block = [
            f"{emoji} *{a['name']}* ({a['currency']}, {a['type']})",
            f"  · slug: `{a['id']}`",
        ]
        source_keys = a.get("source_keys") or []
        if source_keys:
            block.append("  · source: " + ", ".join(f"`{k}`" for k in source_keys))
        else:
            block.append("  · source: _(chưa map nguồn nào — tx mới sẽ trigger onboarding)_")
        lines.append("\n".join(block))
    return lines


async def cmd_accounts(text: str = ""):
    """Subcommands:
      /accounts                  → list configured accounts (default)
      /accounts add              → manual onboarding wizard
      /accounts assign <slug>    → bulk-assign all unmapped tx (same currency
                                   as the account) → this account. One-time
                                   recovery for historical tx that pre-date
                                   the account.

    Project goal is tracking tx + chi tiêu per account, not absolute balance.
    The list view shows enough to verify which sources map where so the user
    knows whether incoming tx will get categorized to the right account.
    """
    parts = (text or "").strip().split()
    sub = parts[1].lower() if len(parts) >= 2 else ""

    if sub in ("add", "new", "create"):
        sh.set_state(CHAT_ID, {
            "step":                "await_new_account_name",
            "pending_source_key":  "",
            "pending_setup_key":   "",
            "pending_identifier":  "",
            "new_acct_row_num":    0,
            "pending_account":     {},
        })
        await tg.send_text(
            "📝 *Setup account mới* (manual)\n\n"
            "Tên hiển thị (vd: `TCB Tiêu dùng`, `Cake Visa ****8421`):"
        )
        return

    if sub == "assign":
        slug = parts[2].strip() if len(parts) >= 3 else ""
        await _cmd_accounts_assign(slug)
        return

    # Default: list mode
    lines = _account_list_lines()
    msg = "🏦 *Accounts đã setup*\n\n" + "\n\n".join(lines)
    msg += (
        "\n\n_Dùng `/accounts add` để thêm account mới, hoặc `/report` xem chi tiêu."
        "\nDùng `/accounts assign <slug>` để gán tx lịch sử chưa map → 1 account._"
    )
    await tg.send_text(msg)


async def _cmd_accounts_assign(slug: str):
    """One-time bulk backfill: assign all unmapped tx of matching currency
    to a single account.

    Use case: account was onboarded after the tx already landed (or the
    account_source_key column wasn't populated yet because the schema didn't
    track it before commit b9c4576). Once /accounts assign runs, the
    historical tx start appearing in /report under that account.

    Safety:
      - Filters by account.currency (won't mix HKD tx into a VND account)
      - Shows a preview with totals + tx count before committing
      - Idempotent: only touches tx where account_id is empty
    """
    if not slug:
        await tg.send_text(
            "Usage: `/accounts assign <slug>`\n"
            "Vd: `/accounts assign tpb_2601`\n\n"
            "Gán tất cả tx (cùng currency) chưa map account → account này.\n"
            "Dùng /accounts để xem list slug."
        )
        return

    acc = sh.find_account_by_id(slug)
    if not acc:
        await tg.send_text(
            f"⚠️ Account `{slug}` không tồn tại. /accounts để xem list."
        )
        return

    # Scan Transactions for candidates (unmapped + matching currency)
    ws = sh._sheet(sh.S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]

    candidate_rows: list[int] = []
    total_out = total_in = 0.0
    out_count = in_count = 0
    for i, r in enumerate(rows):
        if len(r) < 8:
            continue
        existing_acc = (r[16] if len(r) > 16 else "").strip()
        if existing_acc:
            continue   # already mapped — skip
        tx_currency = sh.row_currency(r)
        if tx_currency != acc["currency"]:
            continue
        tx_type = r[6] if len(r) > 6 else ""
        if tx_type not in ("Tiền ra", "Tiền vào"):
            continue
        amount = sh._parse_amount(r[7]) or 0.0
        if amount <= 0:
            continue
        candidate_rows.append(i + 2)  # +2 = +1 (skip header) + 1 (1-indexed)
        if tx_type == "Tiền ra":
            total_out += amount
            out_count += 1
        else:
            total_in += amount
            in_count += 1

    if not candidate_rows:
        await tg.send_text(
            f"✅ Không có tx {acc['currency']} nào chưa map account."
            f" `{slug}` không cần backfill."
        )
        return

    # Stash row list in BOT_STATE for the confirmation step (callback re-reads it)
    sh.set_state(CHAT_ID, {
        "step":         "await_assign_confirm",
        "assign_slug":  slug,
        "assign_rows":  candidate_rows,
    })

    msg = (
        f"🔗 *Bulk assign — `{slug}`* ({acc['currency']}, {acc['type']})\n\n"
        f"Tx {acc['currency']} chưa map:\n"
        f"  ⬇️ Vào: +{sh.fmt_amount(total_in, acc['currency'])} ({in_count} tx)\n"
        f"  ⬆️ Ra:  -{sh.fmt_amount(total_out, acc['currency'])} ({out_count} tx)\n\n"
        f"*Tổng:* {len(candidate_rows)} tx → gán hết vào `{slug}`?"
    )
    buttons = [[
        {"text": "✅ Yes, assign all", "callback_data": f"asg_yes_{slug}"},
        {"text": "❌ Hủy",              "callback_data": "asg_no"},
    ]]
    await tg.send_with_buttons(msg, buttons)


async def handle_assign_callback(parts: list[str], message_id: int):
    """Callback router for /accounts assign confirmation.

    Pattern: `asg_yes_<slug>` | `asg_no`
    """
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "no":
        sh.clear_state(CHAT_ID)
        await tg.edit_message(message_id, "❌ Đã hủy bulk assign.")
        return

    if action != "yes":
        return

    state = sh.get_state(CHAT_ID) or {}
    rows: list[int] = state.get("assign_rows") or []
    slug: str = state.get("assign_slug") or ""

    if not rows or not slug:
        await tg.edit_message(
            message_id,
            "⚠️ State đã hết hạn. Chạy `/accounts assign <slug>` lại.",
        )
        return

    # Batch update col Q across all candidate rows in ONE API call
    ws = sh._sheet(sh.S.TRANSACTIONS)
    batch = [
        {"range": f"Q{rn}:Q{rn}", "values": [[slug]]}
        for rn in rows
    ]
    ws.batch_update(batch)

    sh.clear_state(CHAT_ID)
    await tg.edit_message(
        message_id,
        f"✅ Đã assign *{len(rows)} tx* → `{slug}`.\n"
        f"Dùng /report để xem chi tiêu theo account."
    )


# ─── /transfer + /cc pay commands ─────────────────────────────


def _now_for_tx() -> tuple[str, str, str]:
    """(iso_string, month_key, ref_code-suffix-from-timestamp)."""
    import time
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return now.isoformat(timespec="seconds"), sh.fmt_month(now), str(int(time.time()))


async def cmd_transfer(text: str):
    """`/transfer <amount> <from_id> <to_id>` — manual transfer."""
    parts = text.strip().split()
    if len(parts) < 4:
        await tg.send_text(
            "Usage: `/transfer <amount> <from> <to>`\n"
            "Vd: `/transfer 1000000 tcb_main cake_main`"
        )
        return
    amount = _parse_money(parts[1])
    if amount is None or amount <= 0:
        await tg.send_text("⚠️ Số tiền không hợp lệ.")
        return
    from_id, to_id = parts[2].strip(), parts[3].strip()
    if from_id == to_id:
        await tg.send_text("⚠️ from và to phải khác account.")
        return

    from_acc = sh.find_account_by_id(from_id)
    to_acc = sh.find_account_by_id(to_id)
    if not from_acc:
        await tg.send_text(f"⚠️ Account `{from_id}` không tồn tại. /accounts để xem list.")
        return
    if not to_acc:
        await tg.send_text(f"⚠️ Account `{to_id}` không tồn tại.")
        return
    if from_acc["currency"] != to_acc["currency"]:
        await tg.send_text(
            f"⚠️ Currency mismatch: {from_acc['currency']} → {to_acc['currency']}. "
            f"Bot không tự convert."
        )
        return

    iso, month_key, ts = _now_for_tx()
    desc = f"transfer {from_id} → {to_id}"
    ref = f"TRANSFER_{from_id}_{to_id}_{ts}"

    row_num, status = sh.append_transfer(
        from_account_id=from_id, to_account_id=to_id,
        amount=amount, currency=from_acc["currency"],
        description=desc, tx_date=iso, ref_code=ref, month_key=month_key,
    )
    if status != "ok":
        await tg.send_text(f"⚠️ {status}")
        return

    sh.invalidate_accounts_cache()
    from_after = sh.find_account_by_id(from_id)
    to_after = sh.find_account_by_id(to_id)
    cur = from_acc["currency"]
    await tg.send_text(
        f"✅ *Transfer ghi nhận*\n"
        f"  {from_acc['name']} → {to_acc['name']}\n"
        f"  Số tiền: *{sh.fmt_amount(amount, cur)}*\n\n"
        f"📊 Số dư mới:\n"
        f"  {from_acc['name']}: {sh.fmt_amount(from_after['running_balance'], cur)}\n"
        f"  {to_acc['name']}: {sh.fmt_amount(to_after['running_balance'], cur)}"
    )


async def cmd_cc_pay(text: str):
    """`/cc pay <amount> <cc_id>`                 — external payment (source not tracked)
    `/cc pay <amount> <bank_id> <cc_id>`         — paid from tracked bank account

    The 2-arg form decreases the credit's outstanding without writing a
    bank −leg — use when the payment came from an account the bot doesn't
    onboard (friend, cash deposit, salary auto-pay from an unregistered
    bank). The 3-arg form is unchanged.
    """
    parts = text.strip().split()
    # parts[0]="/cc", parts[1]="pay", parts[2]=amount, parts[3]=bank|cc, parts[4]=cc?
    if len(parts) < 4 or parts[1].lower() != "pay":
        await tg.send_text(
            "Usage:\n"
            "`/cc pay <amount> <cc_id>` — trả từ nguồn ngoài (không track)\n"
            "`/cc pay <amount> <bank_id> <cc_id>` — trả từ bank account đã onboard\n\n"
            "Vd: `/cc pay 2450000 cake_visa_8421`"
        )
        return
    amount = _parse_money(parts[2])
    if amount is None or amount <= 0:
        await tg.send_text("⚠️ Số tiền không hợp lệ.")
        return

    iso, month_key, ts = _now_for_tx()

    # 2-arg form: external source
    if len(parts) == 4:
        cc_id = parts[3].strip()
        cc_acc = sh.find_account_by_id(cc_id)
        if not cc_acc:
            await tg.send_text(f"⚠️ CC `{cc_id}` không tồn tại.")
            return
        if cc_acc["type"] != "credit":
            await tg.send_text(
                f"⚠️ `{cc_id}` không phải credit card (type={cc_acc['type']})."
            )
            return

        desc = f"cc payment external → {cc_id}"
        ref = f"CCPAYEXT_{cc_id}_{ts}"
        row_num, status = sh.append_cc_payment_external(
            cc_account_id=cc_id,
            amount=amount, currency=cc_acc["currency"],
            description=desc, tx_date=iso, ref_code=ref, month_key=month_key,
        )
        if status != "ok":
            await tg.send_text(f"⚠️ {status}")
            return

        sh.invalidate_accounts_cache()
        cc_after = sh.find_account_by_id(cc_id)
        cur = cc_acc["currency"]
        await tg.send_text(
            f"✅ *CC payment ghi nhận* (external)\n"
            f"  → {cc_acc['name']}\n"
            f"  Số tiền: *{sh.fmt_amount(amount, cur)}*\n\n"
            f"📊 Sau payment:\n"
            f"  {cc_acc['name']} dư nợ: "
            f"{sh.fmt_amount(cc_after['outstanding_balance'], cur)}"
        )
        return

    # 3-arg form: tracked bank → CC (existing behavior)
    bank_id, cc_id = parts[3].strip(), parts[4].strip()
    bank_acc = sh.find_account_by_id(bank_id)
    cc_acc = sh.find_account_by_id(cc_id)
    if not bank_acc:
        await tg.send_text(f"⚠️ Bank `{bank_id}` không tồn tại.")
        return
    if not cc_acc:
        await tg.send_text(f"⚠️ CC `{cc_id}` không tồn tại.")
        return
    if cc_acc["type"] != "credit":
        await tg.send_text(
            f"⚠️ `{cc_id}` không phải credit card (type={cc_acc['type']})."
        )
        return

    desc = f"cc payment {bank_id} → {cc_id}"
    ref = f"CCPAY_{bank_id}_{cc_id}_{ts}"
    row_num, status = sh.append_cc_payment(
        bank_account_id=bank_id, cc_account_id=cc_id,
        amount=amount, currency=bank_acc["currency"],
        description=desc, tx_date=iso, ref_code=ref, month_key=month_key,
    )
    if status != "ok":
        await tg.send_text(f"⚠️ {status}")
        return

    sh.invalidate_accounts_cache()
    bank_after = sh.find_account_by_id(bank_id)
    cc_after = sh.find_account_by_id(cc_id)
    cur = bank_acc["currency"]
    await tg.send_text(
        f"✅ *CC payment ghi nhận*\n"
        f"  {bank_acc['name']} → {cc_acc['name']}\n"
        f"  Số tiền: *{sh.fmt_amount(amount, cur)}*\n\n"
        f"📊 Sau payment:\n"
        f"  {bank_acc['name']}: {sh.fmt_amount(bank_after['running_balance'], cur)}\n"
        f"  {cc_acc['name']} dư nợ: {sh.fmt_amount(cc_after['outstanding_balance'], cur)}"
    )


def _backfill_recent(account_id: str, source_key: str, trigger_row: int | None) -> int:
    """Stamp account_id onto the triggering tx + any other unresolved tx
    whose payload identifier matches this source_key.

    Phase 1 simplification: we backfill ONLY by matching the description-less
    layer (we don't store original payload on the row). For SePay we cannot
    re-resolve from the row alone, so we always backfill the trigger row,
    plus we let the user know other historical rows will need /reconcile.
    """
    count = 0
    # Always backfill the triggering row
    if trigger_row:
        sh.set_tx_account(int(trigger_row), account_id)
        # If that row was already confirmed (auto-categorized), also write
        # the ledger entry now so balance reflects it.
        try:
            row = sh.get_transaction_row(int(trigger_row))
            confirmed = (len(row) > 13 and str(row[13]).upper() == "TRUE")
            if confirmed and not sh.is_ledger_applied(int(trigger_row)):
                amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
                currency = sh.row_currency(row)
                tx_type_legacy = row[6] if len(row) > 6 else "Tiền ra"
                acc = sh.find_account_by_id(account_id)
                if acc and acc["currency"] == currency.upper():
                    direction = "+" if tx_type_legacy == "Tiền vào" else "-"
                    ledger_tx_type = "income" if direction == "+" else "expense"
                    sh.append_ledger_entry(
                        tx_row_num=int(trigger_row),
                        account_id=account_id,
                        direction=direction,
                        amount=amount,
                        currency=currency,
                        tx_type=ledger_tx_type,
                    )
                    sh.update_account_cache(account_id)
                    sh.mark_ledger_applied(int(trigger_row))
        except Exception as e:
            print(f"[accounts] backfill ledger error row={trigger_row}: {e}")
        count += 1
    return count
