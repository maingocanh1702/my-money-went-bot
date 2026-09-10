"""handlers/cancel_tx.py — cancel (and un-cancel) a past transaction.

A cancelled ride, a double-charged order, a booking the merchant reversed: the
bank's own emails only ever add rows, so without this the bot's books can only
grow. Cancelling gives back both things the transaction consumed — the credit
line it drew on, and the cashback it earned (which was holding down the card's
per-MCC cycle cap, starving every later purchase).

The row is never deleted. Both the Account Ledger and the Cashback Ledger key
on `tx_row_num`, so removing a row would silently repoint every reference below
it; instead col V is stamped, the ledger lines are voided, and every money
total skips the row (`sheets.is_cancelled`).

Channel-agnostic on purpose: main.py drives Telegram inline buttons and Zalo
numbered replies over this same core, so the two can't drift apart.
"""
from datetime import datetime, timedelta

import pytz

import sheets as sh
from config import TIMEZONE

# How far back a transaction may be cancelled. Anything older is almost
# certainly already settled on a closed statement, where giving back cap would
# rewrite a cycle the user has already reconciled against the bank.
MAX_AGE_DAYS = 30

PAGE_SIZE = 3        # first screen: the 3 most recent
MORE_PAGE_SIZE = 5   # each "older" tap pulls 5 more


def _now():
    return datetime.now(pytz.timezone(TIMEZONE))


def page(offset: int = 0, limit: int = PAGE_SIZE) -> list[dict]:
    """One page of cancellable transactions, newest first.

    Cancelled rows stay in the list (flagged `is_cancelled`) so the same picker
    that cancels can also offer to restore.
    """
    return sh.get_recent_transactions(
        limit=limit, offset=offset,
        within_days=MAX_AGE_DAYS, include_cancelled=True,
    )


def has_more(offset: int) -> bool:
    """True when at least one transaction sits past `offset` in the window."""
    return bool(page(offset=offset, limit=1))


def describe(row: list) -> dict:
    """Summarize a sheet row for the confirmation screen."""
    return {
        "date": row[1] if len(row) > 1 else "",
        "description": (row[5] if len(row) > 5 else "").strip() or "(không có mô tả)",
        "amount": sh._parse_amount(row[7]) if len(row) > 7 else 0.0,
        "currency": sh.row_currency(row),
        "account_id": (row[16] if len(row) > 16 else "").strip(),
        "tx_type": (row[17] if len(row) > 17 else "expense").strip() or "expense",
        "is_cancelled": sh.is_cancelled(row),
    }


def check(row_num: int) -> tuple[list | None, str]:
    """Validate that `row_num` may be cancelled.

    Returns (row, "") when it may, or (row_or_None, reason) where reason is one
    of: not_found / already / two_leg / income / too_old / bad_date.
    """
    if row_num < 2:
        return None, "not_found"
    row = sh.get_transaction_row(row_num)
    if not row or len(row) < 8:
        return None, "not_found"
    if sh.is_cancelled(row):
        return row, "already"
    return row, _blocking_reason(row)


def _blocking_reason(row: list) -> str:
    """Why this row may not be cancelled — "" when it may.

    Split out of `check` so `restore` enforces the same rules: `check` returns
    "already" before it gets here, so without this the guards below would be
    one-way and an un-cancel could reopen a long-closed statement cycle.
    """
    # Transfers and card payments write two ledger legs through dedicated
    # paths; unwinding one leg here would leave the other side dangling.
    if (row[17] if len(row) > 17 else "").strip() in ("transfer", "cc_payment"):
        return "two_leg"
    # Money coming IN. The picker never offers these, but /cancel_tx <row_num>
    # reaches them, and the whole screen ("hoàn lại hạn mức", a minus sign on
    # the amount) would describe the exact opposite of what the ledger does.
    if (row[6] if len(row) > 6 else "") == "Tiền vào" \
            or (row[17] if len(row) > 17 else "").strip() == "income":
        return "income"
    tx_dt = sh._parse_local_datetime(row[1] if len(row) > 1 else "")
    if tx_dt is None:
        return "bad_date"
    if (_now() - tx_dt).days > MAX_AGE_DAYS:
        return "too_old"
    return ""


def find_original_for_cancellation(*, amount: float, description: str, currency: str,
                                   account_id: str = "", before: datetime | None = None,
                                   max_age_days: int = MAX_AGE_DAYS) -> int | None:
    """The row a bank cancellation notice is reversing, or None.

    Cake's cancellation e-mail is a byte-for-byte copy of the purchase e-mail
    with a later timestamp and a different status line, so the pairing key is
    everything the two share: card, merchant string, amount and currency.

    Newest first, because the notice reverses the most recent matching charge.
    Cancelled rows are skipped — otherwise a second notice for a merchant the
    user visits often would keep re-matching the row it already reversed
    instead of finding nothing. Rows dated after the notice are skipped too: a
    reversal cannot precede what it reverses, and without that guard a later
    identical purchase would be the "newest match" and get cancelled instead.

    Returns None rather than guessing. A card payment that was declined outright
    produces this same notice with no purchase behind it, and inventing a match
    for it would cancel a real transaction.
    """
    want_desc = (description or "").strip().lower()
    want_cur = (currency or "VND").upper().strip() or "VND"
    want_acct = (account_id or "").strip()
    cutoff = (before or _now())
    if cutoff.tzinfo is None:
        cutoff = pytz.timezone(TIMEZONE).localize(cutoff)
    oldest = cutoff - timedelta(days=max_age_days)

    best_row = None
    best_dt = None
    for idx, row in enumerate(sh._get_tx_rows(), start=2):
        if len(row) < 8 or sh.is_cancelled(row):
            continue
        if (row[5] if len(row) > 5 else "").strip().lower() != want_desc:
            continue
        if sh.row_currency(row) != want_cur:
            continue
        if want_acct and (row[16] if len(row) > 16 else "").strip() != want_acct:
            continue
        try:
            if abs(sh._parse_amount(row[7]) - amount) >= 1:
                continue
        except (ValueError, TypeError):
            continue
        row_dt = sh._parse_local_datetime(row[1] if len(row) > 1 else "")
        if row_dt is None or row_dt > cutoff or row_dt < oldest:
            continue
        if _blocking_reason(row):
            continue          # income, a transfer leg, out of the cancel window
        if best_dt is None or row_dt > best_dt:
            best_dt, best_row = row_dt, idx
    return best_row


def _reapply_ledger(row_num: int) -> None:
    """Re-write the Account Ledger entry for a restored row.

    Imported lazily: handlers.transaction imports sheets, which this module
    also imports, so a module-level import would close the cycle.
    """
    from handlers.transaction import _apply_ledger_for_row
    _apply_ledger_for_row(row_num)


def _refresh_cashback(row_num: int) -> bool:
    """Rebuild the card's whole cashback cycle around this row. False on failure.

    Not just this row: freeing (or re-consuming) its slice of the per-MCC cycle
    cap changes what every LATER transaction in the cycle earned, on other days
    too. recompute_cashback_for_tx replays the cycle chronologically.

    The rebuild commits as a single batched Sheets write, so a quota or 5xx
    error leaves the OLD cashback lines live — still holding the cap down, the
    very symptom cancelling is meant to clear. The credit line is already back
    by then, so we don't unwind; we return False and let the caller say so,
    because the repair is `/cashback recompute <cc_id>` and a user who was told
    "đã tính lại cả kỳ" would never know to run it.
    """
    try:
        sh.recompute_cashback_for_tx(row_num)
        return True
    except Exception as e:      # never let a cashback rebuild strand a cancel
        print(f"[cancel_tx] cashback recompute failed row={row_num}: {e}")
        return False


def cancel(row_num: int) -> dict:
    """Cancel one transaction. Returns {ok, reason, cashback_reclaimed, ...}.

    Order matters: the flag is written BEFORE the cashback rebuild, so the
    replay sees the row as cancelled and hands its cap to later purchases.
    """
    row, reason = check(row_num)
    if reason:
        return {"ok": False, "reason": reason,
                **(describe(row) if row else {})}

    info = describe(row)
    info["cashback_reclaimed"] = sh.cashback_total_for_tx(row_num)

    # Whose balance to recompute. Deliberately NOT the set of entries we are
    # about to void: on a retry after a half-finished cancel those entries are
    # already void, the set comes back empty, and the account would keep a
    # stale outstanding_balance forever with the bot reporting success.
    touched = {e["account_id"] for e in sh.get_ledger_entries_for_tx(row_num)}
    touched.add(info.get("account_id") or "")
    touched.discard("")

    try:
        # 1. Give back the credit line / balance this tx consumed.
        #    col T is cleared UNCONDITIONALLY: a cancelled row is by definition
        #    not ledger-applied. Clearing it only when there were live entries
        #    to void meant a retry after a half-finished cancel left T=TRUE, and
        #    restore's _apply_ledger_for_row then early-returns on that flag —
        #    reporting success while the balance stays short for good.
        sh.void_ledger_for_tx(row_num)
        sh._sheet(sh.S.TRANSACTIONS).update_cell(row_num, 20, "FALSE")  # ledger_applied
        sh._invalidate_tx_rows_cache()

        # 2. Mark cancelled, then rebuild cashback so the freed cap flows onward.
        sh.set_transaction_cancelled(row_num, _now().isoformat())
        info["cashback_recomputed"] = _refresh_cashback(row_num)
    finally:
        # 3. Always — a throw above may have left the ledger voided but the
        #    cached balance still carrying this tx.
        for acc_id in touched:
            try:
                sh.update_account_cache(acc_id)
            except Exception as e:
                print(f"[cancel_tx] cache refresh failed acc={acc_id}: {e}")

    print(f"[cancel_tx] cancelled row={row_num} "
          f"cashback_reclaimed={info['cashback_reclaimed']}")
    return {"ok": True, "reason": "", **info}


def restore(row_num: int) -> dict:
    """Undo a cancellation — put back exactly what `cancel` took down."""
    if row_num < 2:
        return {"ok": False, "reason": "not_found"}
    row = sh.get_transaction_row(row_num)
    if not row or len(row) < 8:
        return {"ok": False, "reason": "not_found"}
    if not sh.is_cancelled(row):
        return {"ok": False, "reason": "not_cancelled", **describe(row)}
    # The age window guards a closed statement cycle from being rewritten, and
    # un-cancelling rewrites one just as surely as cancelling does.
    reason = _blocking_reason(row)
    if reason:
        return {"ok": False, "reason": reason, **describe(row)}

    info = describe(row)
    # Read BEFORE clearing the flag: this is the question restore turns on, and
    # `_apply_ledger_for_row` refuses while the row still reads as cancelled.
    had_ledger = sh.had_ledger_entry(row_num)

    sh.set_transaction_cancelled(row_num, "")
    try:
        # Re-apply only when this tx HAD moved money. A row finalized with
        # "skip categorization" is Confirmed=TRUE with no ledger entry ever
        # written, so keying off is_confirmed would mint a balance movement
        # that never existed — money out of nothing on a cancel→restore.
        if had_ledger:
            try:
                _reapply_ledger(row_num)
            except Exception as e:
                # col V is already cleared, so the tx is live in every total
                # again while its balance movement is missing. Report it —
                # silently returning ok:True here is the ledger-side twin of
                # the cashback failure we already warn about.
                print(f"[cancel_tx] ledger re-apply failed row={row_num}: {e}")
                info["ledger_reapplied"] = False

        info["cashback_recomputed"] = _refresh_cashback(row_num)
    finally:
        account_id = info.get("account_id")
        if account_id:
            try:
                sh.update_account_cache(account_id)
            except Exception as e:
                print(f"[cancel_tx] cache refresh failed acc={account_id}: {e}")

    info["cashback_reclaimed"] = sh.cashback_total_for_tx(row_num)
    print(f"[cancel_tx] restored row={row_num} ledger_back={had_ledger} "
          f"cashback_back={info['cashback_reclaimed']}")
    return {"ok": True, "reason": "", **info}
