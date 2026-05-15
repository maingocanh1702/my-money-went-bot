# ⚠️ DEPRECATED — Legacy SePay handler. New capture logic in markets/vn/capture/.
# DO NOT add new features here. See docs/implementation-plans/phase-2-handlers.md
"""
handlers/sepay.py — SePay webhook handler
Triggered when a bank transaction arrives.
"""
import hashlib
import hmac
import re
from datetime import datetime
import pytz

from config import CHAT_ID, TIMEZONE, DAILY_BUCKET_ID, SEPAY_SECRET
import sheets as sh
import telegram_api as tg


# ─── Bank account identification ─────────────────────────────────────
# Map gateway / bank-name keyword → short ticker dùng trong "TCB-1234".
# Match là substring (case-insensitive); thứ tự ưu tiên các từ dài hơn trước
# để "Cake by VPBank" không bị bắt nhầm thành "VPBank".
BANK_ALIASES: list[tuple[str, str]] = [
    ("cake by vpbank", "Cake"),
    ("cake",           "Cake"),
    ("techcombank",    "TCB"),
    ("tcb",            "TCB"),
    ("vietcombank",    "VCB"),
    ("vcb",            "VCB"),
    ("vietinbank",     "CTG"),
    ("ctg",            "CTG"),
    ("vpbank",         "VPB"),
    ("vpb",            "VPB"),
    ("mb bank",        "MB"),
    ("mbbank",         "MB"),
    ("tpbank",         "TPB"),
    ("tpb",            "TPB"),
    ("sacombank",      "STB"),
    ("agribank",       "AGB"),
    ("bidv",           "BIDV"),
    ("acb",            "ACB"),
    ("ocb",            "OCB"),
    ("hdbank",         "HDB"),
    ("shb",            "SHB"),
    ("vib",            "VIB"),
    ("msb",            "MSB"),
]


def _normalize_bank_name(raw: str) -> str:
    """Map tên bank dài → ticker ngắn. Fallback: lấy ký tự alphanumeric, uppercase, max 5."""
    if not raw:
        return ""
    s = raw.strip().lower()
    for keyword, ticker in BANK_ALIASES:
        if keyword in s:
            return ticker
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    return cleaned[:5] if cleaned else ""


def _extract_bank_account(data: dict) -> str:
    """Tạo bank account ID dạng 'TCB-1234'.

    Ưu tiên field `bankAccount` đã được upstream parser populate (email_parser
    set sẵn). Fallback: đọc gateway + accountNumber từ SePay native payload.

    Trả về '' nếu không có thông tin nào — caller có thể vẫn ghi GD nhưng
    nhóm "Không rõ" trong reports.
    """
    pre = data.get("bankAccount") or data.get("bank_account")
    if pre:
        return str(pre).strip()

    bank_raw = (
        data.get("gateway")
        or data.get("bank")
        or data.get("bankName")
        or data.get("bank_name")
        or ""
    )
    bank = _normalize_bank_name(bank_raw)

    acc_raw = (
        data.get("accountNumber")
        or data.get("subAccount")
        or data.get("account_number")
        or data.get("subaccount")
        or ""
    )
    cleaned_acc = re.sub(r"[^A-Za-z0-9]", "", str(acc_raw))
    last4 = cleaned_acc[-4:] if cleaned_acc else ""

    if bank and last4:
        return f"{bank}-{last4}"
    if bank:
        return bank
    if last4:
        return f"???-{last4}"
    return ""


async def _ensure_buckets(month_key: str) -> tuple[list[dict], int]:
    """Get categories cho month, auto-bootstrap defaults nếu chưa có.

    Race-safe: dùng shared lock + re-check pattern. Trả về (buckets, created)
    — `created > 0` nghĩa là bootstrap vừa chạy và caller nên fire welcome msg.
    """
    buckets = sh.get_active_buckets(month_key)
    if buckets:
        return buckets, 0

    async with sh.bootstrap_lock:
        # Re-check inside lock — worker thứ 2 sẽ thấy đã có và skip bootstrap
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        if buckets:
            return buckets, 0
        created = sh.bootstrap_default_categories(month_key)
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        return buckets, created


async def handle_sepay_webhook(payload: dict):
    # Optional: validate SePay webhook secret
    # Set SEPAY_SECRET in .env to match the token configured in SePay dashboard
    if SEPAY_SECRET:
        # SePay docs specify `apikey`; accept legacy field names for backward compat
        # but compare in constant time to avoid timing-side-channel leaks.
        incoming_secret = (
            payload.get("apikey")
            or payload.get("token")
            or payload.get("secret")
            or (payload.get("data") or {}).get("apikey")
            or ""
        )
        if not hmac.compare_digest(str(incoming_secret), SEPAY_SECRET):
            print(f"[sepay] rejected: invalid secret")
            return

    data = payload.get("data") if "data" in payload else payload

    # Log only safe fields for debugging (never log full payload — contains bank data)
    print(f"[sepay] incoming: transferType={data.get('transferType')!r} "
          f"amount={data.get('transferAmount')} ref={data.get('referenceCode')!r}")

    # Try all known SePay field names for amount (use explicit None check to handle 0)
    raw_amount = next(
        (data[k] for k in ("transferAmount", "transfer_amount", "amount") if data.get(k) is not None),
        None
    )
    if raw_amount is None:
        print("[sepay] skipping: no amount field found")
        return
    amount = abs(float(raw_amount))

    tx_type_raw = str(data.get("transferType") or data.get("transfer_type") or data.get("type") or "").lower()

    # Determine direction: outgoing (debit) vs incoming (credit)
    is_outgoing = "out" in tx_type_raw or "debit" in tx_type_raw or float(raw_amount) < 0
    is_incoming = "in" in tx_type_raw or "credit" in tx_type_raw or (not is_outgoing and float(raw_amount) > 0)

    if not is_outgoing and not is_incoming:
        print(f"[sepay] skipping unknown tx type={tx_type_raw!r}")
        return

    description = (data.get("description") or data.get("content") or "Không có mô tả").strip()

    # Deterministic fallback ref_code — stable across SePay retries
    # (hash of amount + description + date so duplicate deliveries are correctly deduped)
    raw_date = data.get("transactionDate") or data.get("transaction_date") or ""
    ref_code = (
        data.get("referenceCode")
        or data.get("reference_number")
        or hashlib.md5(f"{raw_amount}|{description}|{raw_date}".encode()).hexdigest()[:16]
    )

    # Idempotency: skip duplicate webhook deliveries from SePay
    if sh.tx_exists(ref_code):
        print(f"DEBUG: duplicate webhook ignored, ref_code={ref_code!r}")
        return

    tz = pytz.timezone(TIMEZONE)
    if raw_date:
        try:
            tx_date = datetime.fromisoformat(str(raw_date))
        except Exception:
            tx_date = datetime.now(tz)
    else:
        tx_date = datetime.now(tz)

    # Guard: reject stale transactions (SePay replays old history on first webhook setup)
    # Email transactions can be delayed (Gmail polling), so use a wider window
    is_email_source = data.get("_source", "").startswith("email_")
    max_age_minutes = 1440 if is_email_source else 10  # 24h for email, 10min for SePay
    now = datetime.now(tz)
    if tx_date.tzinfo is None:
        tx_date_aware = tz.localize(tx_date)
    else:
        tx_date_aware = tx_date.astimezone(tz)
    age_minutes = (now - tx_date_aware).total_seconds() / 60
    if age_minutes > max_age_minutes:
        print(f"[sepay] skipping stale tx: {age_minutes:.0f}min old (max={max_age_minutes}), ref={ref_code!r}")
        return

    month_key = sh.fmt_month(tx_date)

    # ─── Fuzzy dedup: chặn duplicate giữa SePay + email sources ──
    tx_type_label = "Tiền vào" if is_incoming else "Tiền ra"
    if sh.find_recent_duplicate(amount, tx_type_label, raw_date):
        print(f"[dedup] skipped duplicate: {amount} {tx_type_label} ref={ref_code!r}")
        return

    # ─── Bank account ID — gắn vào row để break-down theo bank ──
    bank_account = _extract_bank_account(data)
    print(f"[sepay] bank_account={bank_account!r}")

    # ─── INCOMING (Tiền vào) ──────────────────────────────────
    if is_incoming:
        row_num = sh.append_transaction(
            tx_date, description, amount, ref_code, month_key,
            tx_type="Tiền vào",
            bank_account=bank_account,
        )

        buckets, created = await _ensure_buckets(month_key)

        msg = (
            f"💚 *+{sh.fmt_amount(amount)} vừa vào tài khoản!*\n"
            f"`{description}`\n\n"
        )

        if created > 0:
            await tg.send_text(
                f"👋 *Welcome to Financial Tracking Bot!*\n\n"
                f"Đã tạo sẵn {created} categories để bạn track. "
                f"Dùng /manage để sửa hoặc thêm category mới. "
                f"Optional: /allocate để đặt budget cho từng mục."
            )

        # Let user optionally categorize income too
        sh.set_state(CHAT_ID, {
            "step": "await_parent",
            "row_num": row_num,
            "amount": amount,
            "description": description,
            "tx_direction": "in",
        })

        msg += "Khoản này thuộc mục nào? 🤔"
        buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
        buttons.append([{"text": "⏭️ Bỏ qua", "callback_data": f"p_{row_num}_skip"}])
        await tg.send_with_buttons(msg, buttons)
        return

    # ─── OUTGOING (Tiền ra) ───────────────────────────────────
    row_num = sh.append_transaction(
        tx_date, description, amount, ref_code, month_key,
        bank_account=bank_account,
    )

    buckets, created = await _ensure_buckets(month_key)

    if created > 0:
        await tg.send_text(
            f"👋 *Welcome to Financial Tracking Bot!*\n\n"
            f"Đã tạo sẵn {created} categories để bạn track. "
            f"Dùng /manage để sửa hoặc thêm category mới. "
            f"Optional: /allocate để đặt budget cho từng mục."
        )

    sh.set_state(CHAT_ID, {
        "step": "await_parent",
        "row_num": row_num,
        "amount": amount,
        "description": description,
        "tx_direction": "out",
    })

    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.send_with_buttons(
        f"💸 *-{sh.fmt_amount(amount)}*\n"
        f"`{description}`\n\n"
        f"Khoản này thuộc mục nào? 🤔",
        buttons,
    )
