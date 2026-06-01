"""
handlers/sepay.py — SePay webhook handler
Triggered when a bank transaction arrives.
"""
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
import pytz

from config import CHAT_ID, TIMEZONE, SEPAY_SECRET
import sheets as sh
import telegram_api as tg
import notifier
from handlers.account_resolver import resolve_account
from handlers.accounts import prompt_new_account


def _append_transaction_and_commit(ref_code: str, tx_date, description, amount, month_key, **kwargs) -> int:
    try:
        row_num = sh.append_transaction(tx_date, description, amount, ref_code, month_key, **kwargs)
    except Exception:
        sh.mark_ref_failed(ref_code)
        raise
    sh.mark_ref_committed(ref_code)
    return row_num


def _parse_webhook_amount(raw_amount, currency: str):
    try:
        parsed = Decimal(str(raw_amount).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"invalid webhook amount: {raw_amount!r}")

    amount_abs = abs(parsed)
    if (currency or "VND").upper() == "VND":
        return int(amount_abs)
    return float(amount_abs)


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
    import hmac as _hmac

    # Validate SePay webhook secret (mandatory — SEPAY_SECRET is required at startup)
    incoming_secret = (
        payload.get("apikey")
        or payload.get("token")
        or payload.get("secret")
        or (payload.get("data") or {}).get("apikey")
        or ""
    )
    if not _hmac.compare_digest(str(incoming_secret), SEPAY_SECRET):
        print("[sepay] rejected: invalid or missing webhook secret")
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
    # Currency: VND default cho mọi nguồn cũ (SePay luôn là VND).
    # Email parsers (TCB/Cake) tự set "VND"; Hang Seng set "HKD".
    currency = str(data.get("currency") or "VND").upper().strip() or "VND"
    if raw_amount is None:
        print("[sepay] skipping: no amount field found")
        return
    amount = _parse_webhook_amount(raw_amount, currency)
    signed_amount = Decimal(str(raw_amount).replace(",", "").strip())

    tx_type_raw = str(data.get("transferType") or data.get("transfer_type") or data.get("type") or "").lower()

    # Determine direction: outgoing (debit) vs incoming (credit)
    is_outgoing = "out" in tx_type_raw or "debit" in tx_type_raw or signed_amount < 0
    is_incoming = "in" in tx_type_raw or "credit" in tx_type_raw or (not is_outgoing and signed_amount > 0)

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
    if sh.find_recent_duplicate(amount, tx_type_label, raw_date, currency=currency):
        print(f"[dedup] skipped duplicate: {amount} {currency} {tx_type_label} ref={ref_code!r}")
        return

    # ─── Account resolution ──────────────────────────────────
    # Returns matched | new_identifier | no_identifier (plan §4.2). The
    # Transactions row is always written; only the ping-for-onboarding
    # behavior differs.
    resolved = resolve_account(data)
    resolved_account_id = resolved.account_id or ""

    # ─── INCOMING (Tiền vào) ──────────────────────────────────
    if is_incoming:
        row_num = _append_transaction_and_commit(
            ref_code,
            tx_date, description, amount, month_key,
            tx_type="Tiền vào",
            currency=currency,
            account_id=resolved_account_id,
            ledger_tx_type="income",
            account_source_key=resolved.source_key or "",
        )

        buckets, created = await _ensure_buckets(month_key)

        if created > 0:
            await notifier.send_text(
                f"👋 *Welcome to Financial Tracking Bot!*\n\n"
                f"Đã tạo sẵn {created} categories để bạn track. "
                f"Dùng /manage để sửa hoặc thêm category mới. "
                f"Optional: /allocate để đặt budget cho từng mục.\n\n"
                f"💡 *Lưu ý:* 'Daily Spending' là 1 category cụ thể cho chi tiêu "
                f"lặt vặt (café vặt, taxi nhỏ), KHÔNG phải tổng chi tiêu/ngày. "
                f"Xem chi tiêu tổng theo category bằng /report."
            )

        # Income notification: NO category picker. Project goal is tracking
        # expenses per account/card — income just needs to land in the
        # Transactions sheet and surface in /report's per-account Vào/Net
        # line. Forcing the user to tap 'Bỏ qua' on every salary/refund tx
        # was noise; income categorization (Salary/Refund/Gift breakdown)
        # is out of scope for the tracking goal.
        await notifier.send_text(
            f"💚 *+{sh.fmt_amount(amount, currency)} vừa vào tài khoản!*\n"
            f"`{description}`"
        )

        # Account onboarding prompt comes AFTER the tx notification so the
        # user sees the tx first, then the setup ask.
        if resolved.status == "new_identifier":
            await prompt_new_account(resolved.source_key, resolved.identifier, row_num)
        return

    # ─── OUTGOING (Tiền ra) ───────────────────────────────────
    row_num = _append_transaction_and_commit(
        ref_code,
        tx_date, description, amount, month_key,
        currency=currency,
        account_id=resolved_account_id,
        ledger_tx_type="expense",
        account_source_key=resolved.source_key or "",
    )

    buckets, created = await _ensure_buckets(month_key)

    if created > 0:
        await notifier.send_text(
            f"👋 *Welcome to Financial Tracking Bot!*\n\n"
            f"Đã tạo sẵn {created} categories để bạn track. "
            f"Dùng /manage để sửa hoặc thêm category mới. "
            f"Optional: /allocate để đặt budget cho từng mục."
        )

    # ── Auto-categorize via keyword rule (if any rule matches) ──
    matched = sh.match_keyword_rule(description)
    if matched and any(b["id"] == matched["bucket_id"] for b in buckets):
        await _auto_categorize(
            row_num=row_num,
            bucket_id=matched["bucket_id"],
            sub_label=matched["sub_label"],
            matched_keyword=matched["keyword"],
            amount=amount,
            description=description,
            tx_date=tx_date,
            tx_direction="out",
            currency=currency,
        )
        # Account prompt AFTER the tx notification (auto-cat + finalize),
        # never before — see incoming branch above for rationale.
        if resolved.status == "new_identifier":
            await prompt_new_account(resolved.source_key, resolved.identifier, row_num)
        return

    sh.set_state(CHAT_ID, {
        "step": "await_parent",
        "row_num": row_num,
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": "out",
    })

    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.send_with_buttons(
        f"💸 *-{sh.fmt_amount(amount, currency)}*\n"
        f"`{description}`\n\n"
        f"Khoản này thuộc mục nào? 🤔",
        buttons,
    )

    # Account onboarding prompt AFTER the tx notification — see incoming
    # branch for rationale.
    if resolved.status == "new_identifier":
        await prompt_new_account(resolved.source_key, resolved.identifier, row_num)


async def _auto_categorize(
    *,
    row_num: int,
    bucket_id: str,
    sub_label: str,
    matched_keyword: str,
    amount: float,
    description: str,
    tx_date,
    tx_direction: str,
    currency: str = "VND",
):
    """Finalize a transaction automatically when a keyword rule matched.

    Sends a brief 'Auto-cat' notice (so the user knows which keyword fired
    and can verify the bot picked the right bucket), then delegates to
    transaction._finalize for the budget feedback + 'Sai mục?' button.
    """
    # Local import to avoid any circular-import risk between sepay <-> transaction
    from handlers.transaction import _finalize

    sign = "+" if tx_direction == "in" else "-"
    bucket_name = sh.bucket_label(bucket_id)
    sub_disp = f" · {sub_label}" if sub_label else ""

    notice = (
        f"🤖 *Auto-categorized:* {sign}{sh.fmt_amount(amount, currency)} → "
        f"*{bucket_name}*{sub_disp}\n"
        f"`{description}`\n"
        f"(matched keyword: `{matched_keyword}`)"
    )
    await notifier.send_text(notice)

    # _finalize reads amount/tx_direction/tx_date from state, so populate it.
    sh.set_state(CHAT_ID, {
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": tx_direction,
        "tx_date": tx_date.isoformat() if hasattr(tx_date, "isoformat") else str(tx_date),
    })

    await _finalize(row_num, bucket_id, sub_label, message_id=None)
