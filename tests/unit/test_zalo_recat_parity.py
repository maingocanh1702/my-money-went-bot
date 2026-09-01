"""Zalo /recat parity with Telegram (audit 2026-08-25 round 2):

  - no-arg /recat shows a numbered picker of recent tx;
  - transfer/cc_payment rows are refused (2-leg ledger protection);
  - cross-month recat uses the transaction's OWN month for the bucket list
    (previously "now", mis-bucketing historical fixes).
"""
from datetime import datetime

import pytest
import pytz

import sheets as sh
from config import SHEETS as S
import main


ZALO_CHAT = "397f0cd1e99c00c2598d"
ZALO_KEY = f"zalo:{ZALO_CHAT}"

TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id", "ledger_tx_type", "linked_tx_row",
    "ledger_applied", "account_source_key",
]


@pytest.fixture
def recat_world(monkeypatch, fake_ss):
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [TX_HEADER])

    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:F1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active"]])
    month_key = sh.fmt_month(datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
    ws_bc.update("A2:F2", [[month_key, "food", "🍜 Food", 0, "", "TRUE"]])
    ws_bc.update("A3:F3", [["2026-01", "trip", "✈️ Trip Jan", 0, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    sent = []

    async def _zalo_send(chat_id, text):
        sent.append(text)

    monkeypatch.setattr(main, "_zalo_send", _zalo_send)
    fake_ss.sent = sent
    fake_ss.month_key = month_key
    return fake_ss


def _seed_row(row_num, *, desc, month, tx_type="Tiền ra", ledger_type="expense",
              confirmed="TRUE", bucket="food", amount="50000"):
    ws = sh._sheet(S.TRANSACTIONS)
    ws.update(f"A{row_num}:U{row_num}", [[
        "", f"2026-08-20T10:00:00", "", "", "", desc, tx_type, amount,
        f"R{row_num}", "0", bucket, "", "FALSE", confirmed, month, "VND",
        "acc_a" if ledger_type in ("transfer", "cc_payment") else "",
        ledger_type, "", "FALSE", "",
    ]])
    sh._invalidate_tx_rows_cache()


@pytest.mark.asyncio
async def test_zalo_recat_refuses_transfer_rows(recat_world, monkeypatch):
    _seed_row(2, desc="transfer a → b", month=recat_world.month_key,
              ledger_type="transfer")
    resets = []
    monkeypatch.setattr(sh, "reset_transaction_row", lambda rn: resets.append(rn))

    await main._zalo_cmd_recat(ZALO_CHAT, "/recat 2", ZALO_KEY)

    assert not resets, "transfer row must never be reset for recat (Zalo)"
    assert any("ledger riêng" in m for m in recat_world.sent)


@pytest.mark.asyncio
async def test_zalo_recat_refuses_income(recat_world, monkeypatch):
    _seed_row(2, desc="salary", month=recat_world.month_key,
              tx_type="Tiền vào", ledger_type="income")
    resets = []
    monkeypatch.setattr(sh, "reset_transaction_row", lambda rn: resets.append(rn))

    await main._zalo_cmd_recat(ZALO_CHAT, "/recat 2", ZALO_KEY)

    assert not resets
    assert any("Income" in m for m in recat_world.sent)


@pytest.mark.asyncio
async def test_zalo_recat_no_arg_shows_numbered_picker(recat_world):
    _seed_row(2, desc="GRAB RIDE", month=recat_world.month_key)
    _seed_row(3, desc="WINMART", month=recat_world.month_key)

    await main._zalo_cmd_recat(ZALO_CHAT, "/recat", ZALO_KEY)

    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "zalo_recat_pick"
    # Most recent first
    assert state.get("recat_rows") == [3, 2]
    picker = recat_world.sent[-1]
    assert "1." in picker and "WINMART" in picker and "GRAB RIDE" in picker


@pytest.mark.asyncio
async def test_zalo_recat_pick_starts_recat_flow(recat_world):
    _seed_row(2, desc="GRAB RIDE", month=recat_world.month_key)
    sh.set_state(ZALO_KEY, {"step": "zalo_recat_pick", "recat_rows": [2]})

    await main._zalo_recat_handle_pick(
        ZALO_CHAT, "1", sh.get_state(ZALO_KEY), ZALO_KEY)

    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "await_zalo_parent"
    assert state.get("row_num") == 2
    assert state.get("cashback_recompute_after_finalize") is True
    assert state.get("tx_date"), "recat state must carry the tx's own date"


@pytest.mark.asyncio
async def test_zalo_recat_uses_row_month_for_buckets(recat_world):
    # Historical tx from 2026-01 — bucket list must come from THAT month.
    _seed_row(2, desc="old trip expense", month="2026-01", bucket="trip")

    await main._zalo_cmd_recat(ZALO_CHAT, "/recat 2", ZALO_KEY)

    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "await_zalo_parent"
    bucket_ids = [b["id"] for b in state.get("buckets") or []]
    assert bucket_ids == ["trip"], \
        f"cross-month recat must use the tx's month buckets, got {bucket_ids}"
