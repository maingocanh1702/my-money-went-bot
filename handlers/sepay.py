"""
handlers/sepay.py — SePay webhook handler
Triggered when a bank transaction arrives.
"""
import hashlib
import hmac
import math
from datetime import datetime
import pytz

from config import CHAT_ID, TIMEZONE, SEPAY_SECRET
from config import TX_MAX_AGE_MINUTES, EMAIL_TX_MAX_AGE_MINUTES
from config import ZALO_ENABLED, ZALO_CHAT_ID
import messenger
import sheets as sh
import telegram_api as tg
from handlers.account_resolver import resolve_account
from handlers.accounts import prompt_new_account, prompt_zalo_new_account
from handlers.zalo_render import render_zalo_logged_summary
from handlers import zalo_queue as zq


async def _ensure_buckets(month_key: str) -> tuple[list[dict], int]:
    """Get categories cho month, auto-clone previous month nếu chưa có.

    Race-safe: dùng shared lock + re-check pattern. Trả về (buckets, created)
    — `created > 0` chỉ khi default bootstrap vừa chạy và caller nên fire
    welcome msg.
    """
    buckets = sh.get_active_buckets(month_key)
    if buckets:
        return buckets, 0

    async with sh.bootstrap_lock:
        # Re-check inside lock — worker thứ 2 sẽ thấy đã có và skip bootstrap
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        if buckets:
            return buckets, 0

        cloned = sh.bootstrap_buckets_from_previous_month(month_key)
        if cloned > 0:
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            return buckets, 0

        created = sh.bootstrap_default_categories(month_key)
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        return buckets, created


async def _append_claimed_transaction(ref_code: str, *args, **kwargs) -> int:
    """Write one transaction and settle its durable claim state.

    A timeout after Google Sheets commits is ambiguous. Re-read the exact
    reference before releasing the claim so a delivery retry cannot append a
    duplicate row during the transaction-cache TTL.
    """
    try:
        row_num = sh.append_transaction(*args, **kwargs)
    except Exception:
        committed_row = sh.find_transaction_row_by_ref(ref_code, force_refresh=True)
        if committed_row is not None:
            sh.mark_ref_committed(ref_code)
            return committed_row
        sh.mark_ref_failed(ref_code)
        raise
    sh.mark_ref_committed(ref_code)
    return row_num


async def handle_trusted_email_transaction(payload: dict):
    """Process an EMAIL_SECRET-authenticated payload without SePay credentials."""
    await _handle_transaction(payload, trusted_email=True)


async def handle_sepay_webhook(payload: dict, *, authenticated: bool = False):
    await _handle_transaction(payload, trusted_email=False, authenticated=authenticated)


def _api_key_from_authorization(header: str | None) -> str:
    """Extract the key from ``Authorization: Apikey <key>`` (SePay's scheme).

    SePay sends webhook credentials only in headers — never in the JSON body.
    The scheme is matched case-insensitively; any other scheme yields "".
    """
    if not header:
        return ""
    scheme, _, key = header.strip().partition(" ")
    if scheme.lower() != "apikey":
        return ""
    return key.strip()


def has_valid_sepay_secret(
    payload: dict,
    *,
    authorization: str | None = None,
    allow_unconfigured: bool = True,
) -> bool:
    """Validate a SePay delivery without logging or processing its bank data.

    The documented path is the ``Authorization: Apikey <key>`` header. A key in
    the body is still accepted so local tools (scripts/sim_webhook.py) and tests
    can post without forging headers; it is the same shared secret either way.
    """
    if not isinstance(payload, dict):
        return False
    if not SEPAY_SECRET:
        return allow_unconfigured
    header_key = _api_key_from_authorization(authorization)
    if header_key and hmac.compare_digest(header_key, SEPAY_SECRET):
        return True
    nested_data = payload.get("data")
    nested_data = nested_data if isinstance(nested_data, dict) else {}
    incoming_secret = (
        payload.get("apikey")
        or payload.get("token")
        or payload.get("secret")
        or nested_data.get("apikey")
    )
    return hmac.compare_digest(str(incoming_secret or ""), SEPAY_SECRET)


async def _handle_transaction(payload: dict, *, trusted_email: bool, authenticated: bool = False):
    # ``authenticated`` means the HTTP boundary already verified the SePay
    # credential (from the header). Re-checking the body here would reject
    # every header-authenticated delivery, since SePay puts nothing in the body.
    if not trusted_email and not authenticated and not has_valid_sepay_secret(payload):
        print("[sepay] rejected: invalid secret")
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
    try:
        raw_amount_number = float(raw_amount)
    except (TypeError, ValueError):
        print(f"[sepay] skipping invalid amount={raw_amount!r}")
        return
    if not math.isfinite(raw_amount_number):
        print(f"[sepay] skipping non-finite amount={raw_amount!r}")
        return
    amount = abs(raw_amount_number)

    tx_type_raw = str(data.get("transferType") or data.get("transfer_type") or data.get("type") or "").lower()

    # Determine direction: outgoing (debit) vs incoming (credit)
    is_outgoing = "out" in tx_type_raw or "debit" in tx_type_raw or raw_amount_number < 0
    is_incoming = "in" in tx_type_raw or "credit" in tx_type_raw or (not is_outgoing and raw_amount_number > 0)

    if not is_outgoing and not is_incoming:
        print(f"[sepay] skipping unknown tx type={tx_type_raw!r}")
        return

    description = (data.get("description") or data.get("content") or "Không có mô tả").strip()

    # Currency: VND default cho mọi nguồn cũ (SePay luôn là VND).
    # Email parsers (TCB/Cake) tự set "VND"; Hang Seng set "HKD".
    currency = str(data.get("currency") or "VND").upper().strip() or "VND"

    # Deterministic fallback ref_code — stable across SePay retries
    # (hash of amount + description + date so duplicate deliveries are correctly deduped)
    raw_date = data.get("transactionDate") or data.get("transaction_date") or ""
    ref_code = (
        data.get("referenceCode")
        or data.get("reference_number")
        or hashlib.md5(f"{raw_amount}|{description}|{raw_date}".encode()).hexdigest()[:16]
    )

    tz = pytz.timezone(TIMEZONE)
    if raw_date:
        try:
            tx_date = datetime.fromisoformat(str(raw_date))
        except Exception:
            tx_date = datetime.now(tz)
    else:
        tx_date = datetime.now(tz)

    # Guard: reject stale transactions (SePay replays old history on first webhook setup)
    # Email transactions can be delayed (Gmail polling), so use a wider window.
    # Both windows are configurable (TX_MAX_AGE_MINUTES / EMAIL_TX_MAX_AGE_MINUTES)
    # — raise them if the bot can be down longer than the default (delayed SePay
    # retries beyond the window are silently skipped).
    is_email_source = data.get("_source", "").startswith("email_")
    max_age_minutes = EMAIL_TX_MAX_AGE_MINUTES if is_email_source else TX_MAX_AGE_MINUTES
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

    # Claim immediately before a financial write. Every authenticated source
    # must retry if this state cannot be made durable; acknowledging a SePay
    # failure here would lose a real transaction just as surely as email would.
    if sh.tx_exists(ref_code):
        print(f"DEBUG: duplicate webhook ignored, ref_code={ref_code!r}")
        return

    # ─── INCOMING (Tiền vào) ──────────────────────────────────
    if is_incoming:
        row_num = await _append_claimed_transaction(
            ref_code,
            tx_date, description, amount, ref_code, month_key,
            tx_type="Tiền vào",
            currency=currency,
            account_id=resolved_account_id,
            ledger_tx_type="income",
            account_source_key=resolved.source_key or "",
        )

        buckets, created = await _ensure_buckets(month_key)

        if created > 0:
            await tg.send_text(
                f"👋 *Welcome to Financial Tracking Bot!*\n\n"
                f"Đã tạo sẵn {created} categories để bạn track. "
                f"Dùng /manage để sửa hoặc thêm category mới. "
                f"Optional: /allocate để đặt budget cho từng mục.\n\n"
                f"💡 *Lưu ý:* 'Daily Spending' là 1 category cụ thể cho chi tiêu "
                f"lặt vặt (café vặt, taxi nhỏ), KHÔNG phải tổng chi tiêu/ngày. "
                f"Xem chi tiêu tổng theo category bằng /report."
            )
            if ZALO_ENABLED and ZALO_CHAT_ID:
                try:
                    await messenger.send_text(
                        f"Chào bạn! Đã tạo sẵn {created} categories.\n"
                        "Dùng /manage để sửa, /allocate để đặt budget.",
                        channel="zalo", recipient_id=ZALO_CHAT_ID,
                    )
                except Exception as e:
                    print(f"[zalo] welcome error: {e}")

        # Income notification: NO category picker. Project goal is tracking
        # expenses per account/card — income just needs to land in the
        # Transactions sheet and surface in /report's per-account Vào/Net
        # line. Forcing the user to tap 'Bỏ qua' on every salary/refund tx
        # was noise; income categorization (Salary/Refund/Gift breakdown)
        # is out of scope for the tracking goal.
        await tg.send_text(
            f"💚 *+{sh.fmt_amount(amount, currency)} vừa vào tài khoản!*\n"
            f"`{description}`"
        )

        # Parallel Zalo notification (income = info only, no category picker)
        if ZALO_ENABLED and ZALO_CHAT_ID:
            try:
                await messenger.send_text(
                    f"+{sh.fmt_amount(amount, currency)} vừa vào tài khoản!\n{description}",
                    channel="zalo",
                    recipient_id=ZALO_CHAT_ID,
                )
            except Exception as e:
                print(f"[zalo] income notification error: {e}")

        # Account onboarding prompt comes AFTER the tx notification so the
        # user sees the tx first, then the setup ask.
        if resolved.status == "new_identifier":
            await prompt_new_account(resolved.source_key, resolved.identifier, row_num)
            await prompt_zalo_new_account(resolved.source_key, resolved.identifier, row_num)
        return

    # ─── OUTGOING (Tiền ra) ───────────────────────────────────
    row_num = await _append_claimed_transaction(
        ref_code,
        tx_date, description, amount, ref_code, month_key,
        currency=currency,
        account_id=resolved_account_id,
        ledger_tx_type="expense",
        account_source_key=resolved.source_key or "",
    )

    # ── Cashback (credit cards only) ──────────────────────────
    # Computed here — right after the outgoing append + account resolve, BEFORE
    # the auto-categorize branch returns early — so it runs exactly once for
    # every credit expense regardless of the picker/auto-cat path. MCC-only, no
    # budget-category dependency. compute_and_record_cashback self-guards
    # (credit + active config + VND + amount>0); a non-credit/unconfigured
    # account yields no note. Never let a cashback error block the tx write.
    await _maybe_notify_cashback(resolved_account_id, row_num)

    buckets, created = await _ensure_buckets(month_key)

    if created > 0:
        await tg.send_text(
            f"👋 *Welcome to Financial Tracking Bot!*\n\n"
            f"Đã tạo sẵn {created} categories để bạn track. "
            f"Dùng /manage để sửa hoặc thêm category mới. "
            f"Optional: /allocate để đặt budget cho từng mục."
        )
        if ZALO_ENABLED and ZALO_CHAT_ID:
            try:
                await messenger.send_text(
                    f"Chào bạn! Đã tạo sẵn {created} categories.\n"
                    "Dùng /manage để sửa, /allocate để đặt budget.",
                    channel="zalo", recipient_id=ZALO_CHAT_ID,
                )
            except Exception as e:
                print(f"[zalo] welcome error: {e}")

    # ── Auto-categorize via keyword rule (if any rule matches) ──
    matched = sh.match_keyword_rule(description)
    if matched:
        bucket_exists = any(b["id"] == matched["bucket_id"] for b in buckets)
        if bucket_exists:
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
            if resolved.status == "new_identifier":
                await prompt_new_account(resolved.source_key, resolved.identifier, row_num)
                await prompt_zalo_new_account(resolved.source_key, resolved.identifier, row_num)
            return
        else:
            # Keyword matched but category was deleted — notify user
            old_name = sh.bucket_label(matched["bucket_id"]) or matched["bucket_id"]
            await tg.send_text(
                f"⚠️ Keyword `{matched['keyword']}` match → *{old_name}* "
                f"nhưng category đã bị xoá. Vui lòng chọn lại:"
            )
            if ZALO_ENABLED and ZALO_CHAT_ID:
                try:
                    await messenger.send_text(
                        f"Keyword '{matched['keyword']}' match → {old_name} "
                        "nhưng category đã bị xoá. Chọn lại bên dưới.",
                        channel="zalo", recipient_id=ZALO_CHAT_ID,
                    )
                except Exception as e:
                    print(f"[zalo] keyword-deleted warning error: {e}")

    # ── Don't clobber a flow the user is mid-typing ───────────
    # Multi-step text inputs would lose the user's work if this webhook
    # overwrote the state. Queue the tx instead; /pending drains the queue.
    existing_state = sh.get_state(CHAT_ID) or {}
    existing_step = existing_state.get("step", "")
    _CRITICAL_STEPS = (
        "await_manage_amount", "await_manage_rename", "await_sub_rename",
        "await_add_cat_name", "await_add_cat_amount",
        "await_alloc_amount", "await_edit_bucket_amount",
        "await_new_bucket_name", "await_new_bucket_amount",
        "await_keyword_input", "await_edit_keyword",
        "cb_cfg", "cb_mcc", "cb_addr", "cb_cycle", "cb_redit",
        "await_new_account_name", "await_new_account_balance",
        "await_credit_limit", "await_credit_outstanding",
        "await_credit_statement", "await_credit_due",
        "await_freetext", "await_inline_new_cat_name", "await_daily_excuse",
    )
    # Built before the branch below: the Zalo picker needs the same bucket
    # choices whether or not the Telegram side is mid-flow. Previously this was
    # only bound in the else-branch, so a mid-flow Telegram user silently lost
    # the Zalo picker (UnboundLocalError swallowed by the except below).
    frequent = sh.get_frequent_categories(3)
    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True,
                                      frequent_ids=frequent)

    if existing_step in _CRITICAL_STEPS:
        pending = existing_state.get("pending_tx_queue") or []
        pending.append({
            "row_num": row_num,
            "amount": amount,
            "currency": currency,
            "description": description,
            "tx_direction": "out",
            "tx_date": tx_date.isoformat() if hasattr(tx_date, "isoformat") else str(tx_date),
        })
        sh.set_state(CHAT_ID, {**existing_state, "pending_tx_queue": pending})
        await tg.send_text(
            f"💸 *-{sh.fmt_amount(amount, currency)}*\n"
            f"`{description}`\n\n"
            f"📌 _Giao dịch đã ghi nhận. Hoàn tất thao tác hiện tại rồi dùng /pending để phân loại._"
        )
    else:
        sh.set_state(CHAT_ID, {
            "step": "await_parent",
            "row_num": row_num,
            "amount": amount,
            "currency": currency,
            "description": description,
            "tx_direction": "out",
            "tx_date": tx_date.isoformat() if hasattr(tx_date, "isoformat") else str(tx_date),
            "pending_tx_queue": existing_state.get("pending_tx_queue") or [],
        })

        await tg.send_with_buttons(
            f"💸 *-{sh.fmt_amount(amount, currency)}*\n"
            f"`{description}`\n\n"
            f"Khoản này thuộc mục nào? 🤔",
            buttons,
        )

    # Parallel Zalo: send numbered category picker + set state for reply
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            zalo_state_key = f"zalo:{ZALO_CHAT_ID}"
            # Build bucket map for Zalo numbered selection
            bucket_map = messenger.buttons_to_bucket_map(buttons)
            item = {
                "row_num": row_num,
                "amount": amount,
                "currency": currency,
                "description": description,
                "tx_direction": "out",
                "tx_date": tx_date.isoformat() if hasattr(tx_date, "isoformat") else str(tx_date),
                "buckets": bucket_map,
            }
            existing = sh.get_state(zalo_state_key) or {}
            existing_step = str(existing.get("step") or "")
            if existing_step == "await_zalo_parent" and existing.get("row_num"):
                queue = existing.get("queue") if isinstance(existing.get("queue"), list) else []
                pending_rows = {existing.get("row_num")}
                pending_rows.update(q.get("row_num") for q in queue if isinstance(q, dict))
                if row_num not in pending_rows:
                    queue.append(item)
                    sh.set_state(zalo_state_key, {**existing, "queue": queue})
                await messenger.send_text(
                    f"Có thêm giao dịch cần phân loại:\n"
                    f"-{sh.fmt_amount(amount, currency)}\n"
                    f"{description}\n\n"
                    "Mình đã xếp hàng sau giao dịch hiện tại.",
                    channel="zalo",
                    recipient_id=ZALO_CHAT_ID,
                )
            elif existing_step:
                # User is mid-flow (manage/allocate/keywords/... — every Zalo
                # flow is a text state machine, so overwriting it here would
                # destroy their in-progress work, exactly the clobber the
                # Telegram side fixed with pending_tx_queue). Park the tx in
                # the durable Zalo queue instead; /pending drains it.
                zq.park(ZALO_CHAT_ID, item)
                await messenger.send_text(
                    f"💸 -{sh.fmt_amount(amount, currency)}\n"
                    f"{description}\n\n"
                    "Giao dịch đã ghi nhận. Hoàn tất thao tác hiện tại rồi "
                    "gửi /pending để phân loại.",
                    channel="zalo",
                    recipient_id=ZALO_CHAT_ID,
                )
            else:
                await messenger.send_with_buttons(
                    f"-{sh.fmt_amount(amount, currency)}\n{description}\n\nKhoản này thuộc mục nào?",
                    buttons,
                    channel="zalo",
                    recipient_id=ZALO_CHAT_ID,
                )
                sh.set_state(zalo_state_key, {
                    "step": "await_zalo_parent",
                    **item,
                    "queue": [],
                })
        except Exception as e:
            print(f"[zalo] category picker error: {e!r}")
            import traceback; traceback.print_exc()

    # Account onboarding prompt AFTER the tx notification — see incoming
    # branch for rationale.
    if resolved.status == "new_identifier":
        await prompt_new_account(resolved.source_key, resolved.identifier, row_num)
        await prompt_zalo_new_account(resolved.source_key, resolved.identifier, row_num)


async def _maybe_notify_cashback(account_id: str, row_num: int):
    """Compute + record cashback for a credit-card expense. Best-effort:
    any failure is logged and swallowed so the transaction itself is never affected.

    Known MCC: cashback is computed silently — the compact line will be
    appended to the budget feedback message by transaction._finalize.
    Unknown MCC: asks user to pick via inline keyboard (learn flow).
    Gate activation: sends a standalone celebration message.
    """
    if not account_id:
        return
    acc = sh.find_account_by_id(account_id)
    if not acc or acc.get("type") != "credit":
        return
    try:
        result = sh.recompute_cashback_for_tx(row_num)
    except Exception:
        import logging
        logging.exception("[cashback] compute failed for row %s", row_num)
        return

    lines = result.get("lines", [])

    # Check if ALL lines are unknown/not-eligible (no real cashback computed)
    only_unknown = all(
        l.get("reason") in ("mcc_unknown", "mcc_not_eligible")
        for l in lines
    ) if lines else False

    if only_unknown:
        # Ask user instead of silently skipping
        await _ask_cashback_learn(account_id, row_num)
        return

    # Gate activation: standalone celebration (only fires once per cycle)
    if result.get("gate_just_opened"):
        gate_msg = "🎉 Đã đạt mốc chi tiêu — hoàn tiền kỳ này đã được kích hoạt!"
        await tg.send_text(gate_msg)
        if ZALO_ENABLED and ZALO_CHAT_ID:
            try:
                await messenger.send_text(gate_msg, channel="zalo", recipient_id=ZALO_CHAT_ID)
            except Exception as e:
                print(f"[zalo] gate note error: {e}")

    # Known MCC: cashback data is in the ledger. The compact line will be
    # appended to the budget message by _finalize → _get_cashback_line().
    # No separate message needed.


async def _ask_cashback_learn(account_id: str, row_num: int):
    """Ask user to classify an unknown-MCC transaction directly with MCC picker.

    Builds MCC buttons DYNAMICALLY from cashback rules for the card (U4),
    so adding a new rule auto-appears here.
    Shows buttons + 'Không hoàn' in ONE set (1 tap).
    Checks exclusion list first to avoid re-asking patterns already declined.
    """
    try:
        tx_row = sh.get_transaction_row(row_num)
        description = tx_row[5] if len(tx_row) > 5 else ""
        amount = sh._parse_amount(tx_row[7]) if len(tx_row) > 7 else 0

        if not description:
            return

        # Check exclusion list — user previously said "no" for this pattern
        if sh.is_mcc_excluded(description):
            print(f"[cashback] excluded pattern match for row {row_num}: {description}")
            return

        # Also check if MCC map already covers this (race condition guard)
        if sh.match_mcc(description):
            return

        acc = sh.find_account_by_id(account_id)
        card_name = acc.get("name", account_id) if acc else account_id
        desc_short = description[:35] + ("…" if len(description) > 35 else "")

        msg = (
            f"💳 *{card_name}* · {desc_short}\n"
            f"{sh.fmt_amount(amount)} — chưa nhận diện MCC\n\n"
            f"Chọn nhóm hoàn tiền:"
        )

        # Build MCC buttons dynamically from this card's cashback rules
        from handlers.cashback import _get_mcc_choices
        choices = _get_mcc_choices(account_id)
        if not choices:
            # No rules configured yet — nothing to show
            return
        # Build 2 buttons per row + "Không hoàn" at the end
        buttons = []
        row_buf = []
        for mcc, label in choices:
            row_buf.append({
                "text": label,
                "callback_data": f"cb_learn_mcc_{row_num}_{mcc}",
            })
            if len(row_buf) == 2:
                buttons.append(row_buf)
                row_buf = []
        if row_buf:
            buttons.append(row_buf)
        buttons.append([{"text": "❌ Không hoàn", "callback_data": f"cb_learn_no_{row_num}"}])

        await tg.send_with_buttons(msg, buttons)

        # ── Zalo: numbered MCC learn picker ──
        # Skipped when the Zalo user is mid-flow — setting the learn state
        # would clobber whatever they're typing. The Telegram picker (inline
        # buttons, stateless) still asks, and the MCC stays learnable later.
        if ZALO_ENABLED and ZALO_CHAT_ID:
            try:
                zalo_state_key = f"zalo:{ZALO_CHAT_ID}"
                if (sh.get_state(zalo_state_key) or {}).get("step"):
                    print("[zalo] cashback learn picker skipped (user mid-flow)")
                else:
                    zalo_lines = [
                        f"{card_name} · {desc_short}",
                        f"{sh.fmt_amount(amount)} — chưa nhận diện MCC",
                        "",
                        "Chọn nhóm hoàn tiền:",
                    ]
                    # ``choices`` is [(mcc, "emoji name"), ...] — the same list the
                    # Telegram buttons were built from. This block used to iterate
                    # an undefined ``rules`` with an unimported emoji map, so it
                    # raised NameError on every call and the except below hid it.
                    rule_list = []
                    for i, (mcc, label) in enumerate(choices, 1):
                        zalo_lines.append(f"{i}. {label}")
                        rule_list.append({"mcc": mcc, "name": label})
                    zalo_lines.append("0. Không hoàn")
                    zalo_lines.append("\nReply số để chọn")

                    await messenger.send_text(
                        "\n".join(zalo_lines),
                        channel="zalo", recipient_id=ZALO_CHAT_ID,
                    )
                    sh.set_state(zalo_state_key, {
                        "step": "await_zalo_cb_learn_mcc",
                        "row_num": row_num,
                        "account_id": account_id,
                        "rules": rule_list,
                    })
            except Exception as e:
                print(f"[zalo] cashback learn picker error: {e!r}")
                import traceback; traceback.print_exc()
    except Exception as e:
        print(f"[cashback] ask_learn error row={row_num}: {e}")



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

    Sends a brief 'Auto-categorized' notice (so the user knows which keyword fired
    and can verify the bot picked the right bucket), then delegates to
    transaction._finalize for the budget feedback + 'Sai mục?' button.
    """
    # Local import to avoid any circular-import risk between sepay <-> transaction
    from handlers.transaction import _finalize

    sign = "+" if tx_direction == "in" else "-"
    bucket_name = sh.bucket_label(bucket_id)
    sub_disp = f" · {sub_label}" if sub_label else ""

    notice = (
        f"🤖 {sign}{sh.fmt_amount(amount, currency)} → "
        f"*{bucket_name}*{sub_disp} (`{matched_keyword}`)"
    )
    await tg.send_text(notice)

    # Parallel Zalo notification (auto-cat = info only, no picker needed)
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            await messenger.send_text(
                f"🤖 {sign}{sh.fmt_amount(amount, currency)} → {bucket_name}{sub_disp} ({matched_keyword})",
                channel="zalo",
                recipient_id=ZALO_CHAT_ID,
            )
        except Exception as e:
            print(f"[zalo] auto-cat notification error: {e}")

    # Pass tx data directly — do NOT write it into BOT_STATE. Overwriting
    # state here used to clobber whatever the user was mid-typing (keyword,
    # rename, budget amount, ...) AND drop the pending_tx_queue whenever an
    # auto-categorized tx arrived at the wrong moment.
    tx_info = {
        "amount": amount,
        "currency": currency,
        "description": description,
        "tx_direction": tx_direction,
        "tx_date": tx_date.isoformat() if hasattr(tx_date, "isoformat") else str(tx_date),
    }
    await _finalize(row_num, bucket_id, sub_label, message_id=None, tx_info=tx_info)

    # Telegram gets the final "Logged + monthly total" summary from
    # transaction._finalize. Zalo needs the same follow-up explicitly because
    # it does not share Telegram's inline-button response path.
    if ZALO_ENABLED and ZALO_CHAT_ID:
        try:
            await messenger.send_text(
                render_zalo_logged_summary(
                    row_num=row_num,
                    bucket_id=bucket_id,
                    sub_label=sub_label,
                    amount=amount,
                    tx_date=tx_date,
                    tx_direction=tx_direction,
                    currency=currency,
                ),
                channel="zalo",
                recipient_id=ZALO_CHAT_ID,
            )
        except Exception as e:
            print(f"[zalo] auto-cat summary error: {e}")
