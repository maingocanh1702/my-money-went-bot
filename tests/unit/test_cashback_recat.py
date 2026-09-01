"""Phase B Phase 3 — recat hooks: void cashback on reset, recompute on finalize.

handle_recategorize voids the tx's cashback immediately (so /report doesn't
count a tx being edited) and flags state; _finalize recomputes ONLY when that
flag is set (never for a brand-new tx, already computed at webhook time).
"""
import pytest
import pytz
from datetime import datetime

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.transaction as txn
import handlers.cashback as cb


@pytest.fixture
def world(monkeypatch, fake_ss):
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    month = sh.fmt_month(datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X"]])
    ws_bc.update("A2:H2", [[month, "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", ""]])
    sh.invalidate_buckets_cache()
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])
    sh.invalidate_cashback_caches()

    import telegram_api as tg

    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}

    for n in ("send_text", "send_with_buttons", "edit_message", "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, n, _noop)

    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit", currency="VND",
                   source_keys=["email_cake:cake_cc"], credit_limit=50_000_000,
                   statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()
    cb.seed_cake_card("cake_cc")
    return {"month": month}


def _mk_winmart_tx(month):
    now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
    return sh.append_transaction(now.strftime("%Y-%m-%dT%H:%M:%S"), "WCM_WINMART HCM",
                                 300000, "RREC", month, account_id="cake_cc",
                                 ledger_tx_type="expense")


def _active(account="cake_cc"):
    return [l for l in sh.get_cashback_ledger(account) if l["status"] != "void"]


@pytest.mark.asyncio
async def test_recat_voids_cashback_and_sets_flag(world):
    r = _mk_winmart_tx(world["month"])
    sh.compute_and_record_cashback(r)
    assert len(_active()) == 1

    await txn.handle_recategorize(["recat", str(r)], message_id=1)

    assert _active() == []  # cashback voided while the tx is being edited
    assert sh.get_state(CHAT_ID).get("cashback_recompute_after_finalize") is True


@pytest.mark.asyncio
async def test_finalize_recomputes_when_flag_set(world):
    r = _mk_winmart_tx(world["month"])
    sh.compute_and_record_cashback(r)
    await txn.handle_recategorize(["recat", str(r)], message_id=1)  # voids + flag
    assert _active() == []

    await txn._finalize(r, "daily_spending", "", message_id=1)

    lines = _active()
    assert len(lines) == 1
    assert lines[0]["cashback_amount"] == 50000  # recomputed back


@pytest.mark.asyncio
async def test_finalize_does_not_recompute_without_flag(world):
    # A brand-new tx finalize (no recat flag) must NOT recompute — the webhook
    # already computed it; recomputing here would be redundant churn.
    r = _mk_winmart_tx(world["month"])
    sh.compute_and_record_cashback(r)
    sh.set_state(CHAT_ID, {"row_num": r})  # no cashback_recompute_after_finalize
    before = sh.get_cashback_ledger("cake_cc")

    await txn._finalize(r, "daily_spending", "", message_id=1)

    after = sh.get_cashback_ledger("cake_cc")
    assert len(after) == len(before)        # no void+rewrite churn
    assert len(_active()) == 1
