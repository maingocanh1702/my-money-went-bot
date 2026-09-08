"""/cancel_tx — cancelling a past transaction gives back credit + cashback.

The bug this exists for: banks only ever email ADDITIONS, so a cancelled Grab
ride, a double charge or a reversed booking stayed on the books forever, and
its cashback kept holding down the card's per-MCC cycle cap — starving every
later purchase, which then reported "đã đạt cap kỳ này — 0đ hoàn tiền".
"""
import pytest
import pytz
from datetime import datetime, timedelta

import sheets as sh
import handlers.cancel_tx as ctx
import handlers.cashback as cb
import handlers.transaction as txn
from config import SHEETS as S

TZ = pytz.timezone("Asia/Ho_Chi_Minh")


@pytest.fixture
def world(monkeypatch, fake_ss):
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    month = sh.fmt_month(datetime.now(TZ))
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [["Month", "Bucket", "Name", "Allocated",
                            "DailyCap", "Active", "Source", "X"]])
    ws_bc.update("A2:H2", [[month, "daily_spending", "🛒 Daily", 0,
                            100000, "TRUE", "test", ""]])
    sh.invalidate_buckets_cache()
    sh.invalidate_cashback_caches()

    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit",
                   currency="VND", source_keys=["email_cake:cake_cc"],
                   credit_limit=50_000_000, statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()
    cb.seed_cake_card("cake_cc")
    return {"month": month}


def _tx(month, desc="WCM_WINMART HCM", amount=300_000, days_ago=0, hour=10,
        source_key=""):
    when = datetime.now(TZ) - timedelta(days=days_ago)
    when = when.replace(hour=hour, minute=0, second=0, microsecond=0)
    return sh.append_transaction(
        when.strftime("%Y-%m-%dT%H:%M:%S"), desc, amount,
        f"REF{desc[:4]}{days_ago}{hour}", month,
        account_id="cake_cc", ledger_tx_type="expense",
        account_source_key=source_key)


def _active(account="cake_cc"):
    return [l for l in sh.get_cashback_ledger(account) if l["status"] != "void"]


def _outstanding(account="cake_cc"):
    return (sh.find_account_by_id(account) or {}).get("outstanding_balance", 0)


# ── the flag itself ────────────────────────────────────────────────────────

def test_is_cancelled_reads_col_v(world):
    r = _tx(world["month"])
    assert sh.is_cancelled(sh.get_transaction_row(r)) is False
    sh.set_transaction_cancelled(r, datetime.now(TZ).isoformat())
    assert sh.is_cancelled(sh.get_transaction_row(r)) is True
    sh.set_transaction_cancelled(r, "")
    assert sh.is_cancelled(sh.get_transaction_row(r)) is False


def test_cancel_stamps_and_row_survives(world):
    r = _tx(world["month"])
    before = len(sh._get_tx_rows(force_refresh=True))
    assert ctx.cancel(r)["ok"] is True
    # The row must stay put: both ledgers key on tx_row_num.
    assert len(sh._get_tx_rows(force_refresh=True)) == before
    assert sh.is_cancelled(sh.get_transaction_row(r)) is True


# ── credit limit ───────────────────────────────────────────────────────────

def test_cancel_gives_back_the_credit_line(world):
    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    txn._apply_ledger_for_row(r)
    sh.update_account_cache("cake_cc")
    sh.invalidate_accounts_cache()
    assert _outstanding() == 300_000

    ctx.cancel(r)
    sh.invalidate_accounts_cache()
    assert _outstanding() == 0


def test_restore_puts_the_credit_line_back(world):
    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    txn._apply_ledger_for_row(r)
    ctx.cancel(r)
    sh.invalidate_accounts_cache()
    assert _outstanding() == 0

    assert ctx.restore(r)["ok"] is True
    sh.invalidate_accounts_cache()
    assert _outstanding() == 300_000


def test_finalizing_a_cancelled_row_does_not_respend(world):
    """The ledger choke point every finalize path funnels through."""
    r = _tx(world["month"])
    ctx.cancel(r)
    sh.finalize_transaction(r, "daily_spending", "")
    txn._apply_ledger_for_row(r)
    sh.update_account_cache("cake_cc")
    sh.invalidate_accounts_cache()
    assert _outstanding() == 0


# ── cashback + the cap this feature exists to free ─────────────────────────

def test_cancel_claws_back_the_cashback(world):
    r = _tx(world["month"])
    sh.compute_and_record_cashback(r)
    assert len(_active()) == 1
    earned = sh.cashback_total_for_tx(r)
    assert earned > 0

    result = ctx.cancel(r)
    assert result["cashback_reclaimed"] == earned
    assert sh.cashback_total_for_tx(r) == 0
    assert _active() == []


def _fill_4121_cap(month):
    """Four ≥200k Grab rides fill MCC 4121's 200k cycle cap.

    Cake caps a single ≥200k transaction at 50k, so filling 200k takes four.
    Same calendar day on purpose: 4121 has no daily limit, and same-day keeps
    every row inside one statement cycle no matter when the suite runs.
    """
    rows = [_tx(month, desc="GRAB* RIDE VN", amount=250_000 + i,
                days_ago=1, hour=8 + i) for i in range(4)]
    for r in rows:
        sh.recompute_cashback_for_tx(r)
    return rows


def test_cancelling_frees_the_mcc_cap_for_a_later_tx(world):
    """The reported bug, end to end.

    Grab rides on one card, one cycle. Once the 200k Di chuyển cap is full the
    next ride earns 0đ with reason mcc_cap_full — the "đã đạt cap kỳ này"
    message. Cancelling one of the earlier rides must hand that cap to the
    later ride, not leave it stranded.
    """
    month = world["month"]
    filled = _fill_4121_cap(month)
    later = _tx(month, desc="GRAB* RIDE VN", amount=100_000, days_ago=1, hour=20)
    sh.recompute_cashback_for_tx(later)

    starved = [l for l in _active() if l["tx_row_num"] == later]
    assert starved and starved[0]["cashback_amount"] == 0
    assert starved[0]["reason"] == "mcc_cap_full"

    ctx.cancel(filled[0])

    freed = [l for l in _active() if l["tx_row_num"] == later]
    assert freed, "the later tx lost its ledger line entirely"
    assert freed[0]["cashback_amount"] > 0, "cancelling did not release the cap"
    assert freed[0]["reason"] == ""
    # And the cancelled tx keeps nothing.
    assert sh.cashback_total_for_tx(filled[0]) == 0


def test_restore_re_earns_and_retakes_the_cap(world):
    month = world["month"]
    filled = _fill_4121_cap(month)
    later = _tx(month, desc="GRAB* RIDE VN", amount=100_000, days_ago=1, hour=20)
    sh.recompute_cashback_for_tx(later)
    ctx.cancel(filled[0])
    assert [l for l in _active() if l["tx_row_num"] == later][0]["cashback_amount"] > 0

    ctx.restore(filled[0])

    assert sh.cashback_total_for_tx(filled[0]) > 0
    retaken = [l for l in _active() if l["tx_row_num"] == later]
    assert retaken and retaken[0]["cashback_amount"] == 0
    assert retaken[0]["reason"] == "mcc_cap_full"


# ── guards ─────────────────────────────────────────────────────────────────

def test_refuses_a_transaction_older_than_the_window(world):
    r = _tx(world["month"], days_ago=ctx.MAX_AGE_DAYS + 2)
    assert ctx.check(r)[1] == "too_old"
    assert ctx.cancel(r) == {"ok": False, "reason": "too_old", **ctx.describe(
        sh.get_transaction_row(r))}
    assert sh.is_cancelled(sh.get_transaction_row(r)) is False


def test_allows_a_transaction_inside_the_window(world):
    r = _tx(world["month"], days_ago=ctx.MAX_AGE_DAYS - 1)
    assert ctx.check(r)[1] == ""


def test_refuses_two_leg_transfers(world):
    r = sh.append_transaction(
        datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S"), "Chuyển khoản",
        500_000, "RTRF", world["month"], account_id="cake_cc",
        ledger_tx_type="transfer")
    assert ctx.check(r)[1] == "two_leg"
    assert ctx.cancel(r)["ok"] is False


def test_refuses_a_missing_row(world):
    assert ctx.check(1)[1] == "not_found"
    assert ctx.check(9999)[1] == "not_found"


def test_cancel_is_idempotent(world):
    r = _tx(world["month"])
    assert ctx.cancel(r)["ok"] is True
    second = ctx.cancel(r)
    assert second["ok"] is False and second["reason"] == "already"


def test_restore_refuses_a_live_row(world):
    r = _tx(world["month"])
    out = ctx.restore(r)
    assert out["ok"] is False and out["reason"] == "not_cancelled"


# ── cancelled rows disappear from the money ────────────────────────────────

def test_cancelled_tx_drops_out_of_bucket_spend(world):
    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    assert sh.get_bucket_status("daily_spending", world["month"])["spent"] == 300_000

    ctx.cancel(r)
    assert sh.get_bucket_status("daily_spending", world["month"])["spent"] == 0


def test_cancelled_tx_drops_out_of_the_picker_but_not_the_cancel_picker(world):
    r = _tx(world["month"])
    ctx.cancel(r)
    # /recat must not offer it…
    assert all(t["row_num"] != r for t in sh.get_recent_transactions(limit=20))
    # …but /cancel_tx must, so it can be restored.
    assert any(t["row_num"] == r for t in ctx.page(limit=20))


# ── picker paging ──────────────────────────────────────────────────────────

def test_first_page_is_three_newest(world):
    rows = [_tx(world["month"], amount=10_000 + i, days_ago=i, hour=9)
            for i in range(6)]
    first = ctx.page()
    assert len(first) == ctx.PAGE_SIZE
    assert [t["row_num"] for t in first] == sorted(rows, reverse=True)[:3]


def test_paging_walks_backwards_without_repeats(world):
    rows = [_tx(world["month"], amount=10_000 + i, days_ago=i, hour=9)
            for i in range(6)]
    first = ctx.page()
    more = ctx.page(offset=ctx.PAGE_SIZE, limit=ctx.MORE_PAGE_SIZE)
    seen = [t["row_num"] for t in first] + [t["row_num"] for t in more]
    assert len(seen) == len(set(seen)) == len(rows)
    assert ctx.has_more(0) is True
    assert ctx.has_more(len(rows)) is False


def test_paging_stays_inside_the_30_day_window(world):
    _tx(world["month"], amount=11_000, days_ago=1)
    old = _tx(world["month"], amount=12_000, days_ago=ctx.MAX_AGE_DAYS + 5)
    assert all(t["row_num"] != old for t in ctx.page(limit=50))


# ── regressions from the 2026-09-08 review ─────────────────────────────────

def test_restore_does_not_mint_a_ledger_entry_for_a_skipped_row(world):
    """The money-from-nothing bug.

    "Bỏ qua phân loại" finalizes with Confirmed=TRUE but writes NO ledger
    entry. Cancelling such a row voids nothing, so restoring it must not
    create the entry that never existed — keying off is_confirmed did.
    """
    r = _tx(world["month"], amount=30_000_000)
    sh.finalize_transaction(r, "", "")          # the /skip path
    assert sh.is_confirmed(sh.get_transaction_row(r)) is True
    assert sh.get_ledger_entries_for_tx(r) == []
    sh.update_account_cache("cake_cc")
    sh.invalidate_accounts_cache()
    assert _outstanding() == 0

    ctx.cancel(r)
    ctx.restore(r)

    sh.invalidate_accounts_cache()
    assert _outstanding() == 0, "restore invented a balance movement"
    assert sh.get_ledger_entries_for_tx(r) == []


def test_restore_reapplies_even_when_the_row_is_unconfirmed(world):
    """Mirror case: a live ledger entry on a row that was never confirmed.

    Cancel voids it; keying restore off is_confirmed used to skip the
    re-apply, leaving the tx live in every total with no ledger line.
    """
    r = _tx(world["month"])
    txn._apply_ledger_for_row(r)                # entry exists, Confirmed=FALSE
    sh.update_account_cache("cake_cc")
    sh.invalidate_accounts_cache()
    assert _outstanding() == 300_000
    assert sh.is_confirmed(sh.get_transaction_row(r)) is False

    ctx.cancel(r)
    sh.invalidate_accounts_cache()
    assert _outstanding() == 0

    ctx.restore(r)
    sh.invalidate_accounts_cache()
    assert _outstanding() == 300_000


def test_retry_after_a_half_finished_cancel_still_fixes_the_balance(world):
    """cancel() died after voiding the ledger, before stamping col V.

    On the retry get_ledger_entries_for_tx is already empty, so deriving the
    cache-refresh set from it left outstanding_balance stale forever while the
    bot reported success.
    """
    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    txn._apply_ledger_for_row(r)
    sh.update_account_cache("cake_cc")

    # Simulate the interrupted run: ledger voided, col V never written.
    sh.void_ledger_for_tx(r)
    sh.invalidate_accounts_cache()
    assert _outstanding() == 300_000            # cache still carries the tx
    assert sh.is_cancelled(sh.get_transaction_row(r)) is False

    assert ctx.cancel(r)["ok"] is True
    sh.invalidate_accounts_cache()
    assert _outstanding() == 0


def test_refuses_income_rows(world):
    """The picker hides them, /cancel_tx <row> reaches them, and the confirm
    screen would promise a refund while the ledger does the opposite."""
    r = sh.append_transaction(
        datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S"), "LUONG THANG 9",
        30_000_000, "RSAL", world["month"], account_id="cake_cc",
        tx_type="Tiền vào", ledger_tx_type="income")
    assert ctx.check(r)[1] == "income"
    assert ctx.cancel(r)["ok"] is False


def test_restore_obeys_the_same_30_day_window(world):
    """Un-cancelling rewrites a closed statement cycle just as cancelling does."""
    r = _tx(world["month"], days_ago=1)
    assert ctx.cancel(r)["ok"] is True

    # The row ages out while it sits cancelled.
    stale = (datetime.now(TZ) - timedelta(days=ctx.MAX_AGE_DAYS + 3))
    sh._sheet(S.TRANSACTIONS).update_cell(r, 2, stale.strftime("%Y-%m-%dT%H:%M:%S"))
    sh._invalidate_tx_rows_cache()

    out = ctx.restore(r)
    assert out["ok"] is False and out["reason"] == "too_old"
    assert sh.is_cancelled(sh.get_transaction_row(r)) is True


def test_cancel_reports_a_failed_cashback_rebuild(world, monkeypatch):
    """The rebuild commits in one batched write; a 429 leaves the old lines
    live and the cap still held down. ok stays True (the credit line IS back)
    but the caller must be able to tell the user."""
    r = _tx(world["month"])
    sh.compute_and_record_cashback(r)

    def _boom(*a, **k):
        raise RuntimeError("429 quota exceeded")
    monkeypatch.setattr(sh, "recompute_cashback_for_tx", _boom)

    result = ctx.cancel(r)
    assert result["ok"] is True
    assert result["cashback_recomputed"] is False
    assert sh.is_cancelled(sh.get_transaction_row(r)) is True


def test_dedup_ignores_a_cancelled_row(world):
    """Cancelling is exactly when a merchant re-charges — a cancelled row must
    not pair as the duplicate and swallow the genuine second charge."""
    # Same instant the row carries, so the pair falls inside the dedup window.
    when = datetime.now(TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    when = when.strftime("%Y-%m-%dT%H:%M:%S")
    r = _tx(world["month"], amount=150_000, source_key="email_cake:cake_cc")
    assert sh.find_recent_duplicate(150_000, "Tiền ra", when, source="sepay") is True

    ctx.cancel(r)
    assert sh.find_recent_duplicate(150_000, "Tiền ra", when, source="sepay") is False


@pytest.mark.asyncio
async def test_recat_refuses_a_cancelled_row(world, monkeypatch):
    """/recat <row> would clear Confirmed and walk a flow that changes nothing."""
    import telegram_api as tg
    sent = []

    async def _capture(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _capture)
    for n in ("send_with_buttons", "edit_message", "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, n, _noop)

    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    ctx.cancel(r)

    await txn.handle_recategorize(["recat", str(r)], message_id=1)

    assert any("đã huỷ" in s for s in sent), sent
    # Confirmed must survive — clearing it is what fed the money-losing case.
    assert sh.is_confirmed(sh.get_transaction_row(r)) is True


def test_restore_after_a_retried_cancel_gives_the_credit_line_back(world):
    """cancel() died between voiding the ledger and stamping col V.

    The retry used to skip clearing col T (no live entries left to void), so
    restore's _apply_ledger_for_row early-returned on ledger_applied=TRUE and
    the balance stayed short for good while the bot reported success.
    """
    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    txn._apply_ledger_for_row(r)
    assert sh.is_ledger_applied(r) is True

    sh.void_ledger_for_tx(r)          # the interrupted run: col T left TRUE
    assert ctx.cancel(r)["ok"] is True
    assert sh.is_ledger_applied(r) is False, "cancel left the row ledger-applied"

    assert ctx.restore(r)["ok"] is True
    sh.invalidate_accounts_cache()
    assert _outstanding() == 300_000


def test_restore_reports_a_failed_ledger_reapply(world, monkeypatch):
    """Ledger-side twin of the cashback warning — must not return a silent ok."""
    r = _tx(world["month"])
    sh.finalize_transaction(r, "daily_spending", "")
    txn._apply_ledger_for_row(r)
    ctx.cancel(r)

    def _boom(*a, **k):
        raise RuntimeError("429 quota exceeded")
    monkeypatch.setattr("handlers.transaction._apply_ledger_for_row", _boom)

    result = ctx.restore(r)
    assert result["ledger_reapplied"] is False


def test_no_restore_offered_once_the_row_ages_out(world):
    """Cancelled on day 29, opened on day 31 — restore can only refuse, so the
    confirm screen must say so rather than offer a button."""
    r = _tx(world["month"], days_ago=1)
    ctx.cancel(r)
    stale = datetime.now(TZ) - timedelta(days=ctx.MAX_AGE_DAYS + 3)
    sh._sheet(S.TRANSACTIONS).update_cell(r, 2, stale.strftime("%Y-%m-%dT%H:%M:%S"))
    sh._invalidate_tx_rows_cache()

    row = sh.get_transaction_row(r)
    assert ctx.check(r)[1] == "already"       # still the restore screen…
    assert ctx._blocking_reason(row) == "too_old"   # …but the button is wrong
