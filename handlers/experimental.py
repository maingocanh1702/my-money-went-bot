"""handlers/experimental.py — Experimental commands (not wired in dispatcher).

These commands are Phase 2 features, currently NOT reachable from the main
command dispatcher in main.py. They are isolated here to keep the active
codebase lean and avoid auditing dead code in the production path.

To enable: wire in main.py's _handle_command() and add to telegram_api's
set_my_commands() list.
"""
import re
from datetime import datetime
import pytz

from config import TIMEZONE
import sheets as sh
import telegram_api as tg


def _parse_money(text: str) -> float | None:
    s = re.sub(r"[^\d.]", "", text.strip())
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


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
