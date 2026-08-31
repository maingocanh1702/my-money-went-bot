"""Tests for the 2026-08 audit fixes: Telegram auth hardening, the
pending-tx queue (no more state clobbering), auto-categorize state
preservation, and the recat transfer guard.
"""
import pytest

import sheets as sh
from config import CHAT_ID, SHEETS as S
import main
import handlers.sepay as sepay
import handlers.transaction as transaction


# ─── Shared world ────────────────────────────────────────────────


@pytest.fixture
def fake_world(monkeypatch, fake_ss):
    """Transactions / Budget Config / Bot State tabs + stubbed telegram_api."""
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:T1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied",
    ]])
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [[
        "Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X",
    ]])
    from datetime import datetime
    import pytz
    month_key = sh.fmt_month(datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
    ws_bc.update("A2:H2", [[
        month_key, "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", "",
    ]])
    sh.invalidate_buckets_cache()
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    import telegram_api as tg

    sent = {"texts": [], "buttons": []}

    async def _send_text(text, chat_id=None):
        sent["texts"].append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _send_buttons(text, buttons, chat_id=None):
        sent["buttons"].append((text, buttons))
        return {"ok": True, "result": {"message_id": 1}}

    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _send_text)
    monkeypatch.setattr(tg, "send_with_buttons", _send_buttons)
    for name in ("edit_message", "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, name, _noop)

    fake_ss.sent = sent
    return fake_ss


def _payload(amount=50000, ref="REFQ", desc="mystery merchant"):
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return {
        "transferType": "out",
        "transferAmount": amount,
        "description": desc,
        "transactionDate": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": "VND",
        "referenceCode": ref,
        "accountNumber": "9999000111",
    }


# ─── Telegram auth hardening ─────────────────────────────────────


@pytest.mark.asyncio
async def test_message_from_wrong_chat_is_rejected(fake_world, monkeypatch):
    called = []

    async def _spy():
        called.append(True)

    monkeypatch.setattr(main, "send_today_status", _spy)
    await main._handle_message({"chat": {"id": 424242}, "text": "/today"})
    assert not called, "message from a non-owner chat must not dispatch commands"


@pytest.mark.asyncio
async def test_callback_from_wrong_chat_is_rejected(fake_world, monkeypatch):
    called = []

    async def _spy(parts, message_id):
        called.append(parts)

    monkeypatch.setattr(main, "handle_parent_selected", _spy)
    await main._handle_callback({
        "id": "cbid",
        "data": "p_5_daily_spending",
        "message": {"chat": {"id": 424242}, "message_id": 9},
    })
    assert not called, "callback from a non-owner chat must not dispatch"


def test_validate_callback_shapes():
    ok = main._validate_callback(
        {"data": "p_5_food", "message": {"message_id": 7}})
    assert ok == ("p", ["p", "5", "food"], 7)
    # Unknown prefix
    assert main._validate_callback(
        {"data": "hack_1", "message": {"message_id": 7}}) is None
    # Missing message
    assert main._validate_callback({"data": "p_5_food"}) is None
    # Too few parts
    assert main._validate_callback(
        {"data": "p", "message": {"message_id": 7}}) is None


# ─── Pending queue: webhook must not clobber a mid-typing flow ───


@pytest.mark.asyncio
async def test_webhook_queues_tx_when_user_mid_flow(fake_world):
    sh.set_state(CHAT_ID, {"step": "await_keyword_input", "month_key": "2026-08"})

    await sepay.handle_sepay_webhook(_payload(ref="REFQ1"))

    state = sh.get_state(CHAT_ID) or {}
    assert state.get("step") == "await_keyword_input", \
        "webhook clobbered the user's in-progress flow"
    queue = state.get("pending_tx_queue") or []
    assert len(queue) == 1 and queue[0]["amount"] == 50000
    assert any("/pending" in t for t in fake_world.sent["texts"])


@pytest.mark.asyncio
async def test_webhook_shows_picker_when_idle(fake_world):
    await sepay.handle_sepay_webhook(_payload(ref="REFQ2"))
    state = sh.get_state(CHAT_ID) or {}
    assert state.get("step") == "await_parent"
    assert not state.get("pending_tx_queue")


@pytest.mark.asyncio
async def test_command_clear_preserves_queue(fake_world, monkeypatch):
    async def _noop():
        pass

    monkeypatch.setattr(main, "send_today_status", _noop)
    sh.set_state(CHAT_ID, {
        "step": "await_manage_amount",
        "pending_tx_queue": [{"row_num": 5, "amount": 1000,
                              "currency": "VND", "description": "x",
                              "tx_direction": "out"}],
    })
    await main._handle_message({"chat": {"id": 0}, "text": "/today"})
    state = sh.get_state(CHAT_ID) or {}
    assert not state.get("step"), "command must clear the in-progress step"
    assert len(state.get("pending_tx_queue") or []) == 1, \
        "command clear must NOT drop the pending queue"


@pytest.mark.asyncio
async def test_pending_command_promotes_queue_item(fake_world, monkeypatch):
    monkeypatch.setattr(sh, "get_frequent_categories", lambda n=3: [])
    sh.set_state(CHAT_ID, {"pending_tx_queue": [
        {"row_num": 7, "amount": 20000, "currency": "VND",
         "description": "GRAB", "tx_direction": "out"},
    ]})
    await main._tg_cmd_pending()
    state = sh.get_state(CHAT_ID) or {}
    assert state.get("step") == "await_parent"
    assert state.get("row_num") == 7
    assert state.get("pending_tx_queue") == []
    assert fake_world.sent["buttons"], "picker must be shown"


# ─── Auto-categorize must not touch stored state ─────────────────


@pytest.mark.asyncio
async def test_finalize_with_tx_info_preserves_state(fake_world, monkeypatch):
    monkeypatch.setattr(sh, "finalize_transaction", lambda *a, **k: None)
    monkeypatch.setattr(transaction, "_apply_ledger_for_row", lambda row: None)
    monkeypatch.setattr(sh, "get_bucket_status",
                        lambda bid, mk: {"spent": 10_000, "allocated": 0,
                                         "remaining": 0, "foreign": {}})
    monkeypatch.setattr(sh, "bucket_label", lambda bid: "🍜 Food")
    monkeypatch.setattr(sh, "get_transaction_row", lambda rn: [])
    monkeypatch.setattr(sh, "match_keyword_rule",
                        lambda desc: {"keyword": "grab", "bucket_id": "food",
                                      "sub_label": "", "row_num": 2})

    user_state = {
        "step": "await_keyword_input",
        "month_key": "2026-08",
        "pending_tx_queue": [{"row_num": 9, "amount": 5000,
                              "currency": "VND", "description": "x",
                              "tx_direction": "out"}],
    }
    sh.set_state(CHAT_ID, user_state)

    tx_info = {
        "amount": 40_000,
        "currency": "VND",
        "description": "GRAB RIDE",
        "tx_direction": "out",
        "tx_date": "2026-08-24T10:00:00+07:00",
    }
    await transaction._finalize(11, "food", "", message_id=None, tx_info=tx_info)

    stored = sh.get_state(CHAT_ID) or {}
    assert stored.get("step") == "await_keyword_input", \
        "auto-categorize clobbered the user's in-progress flow"
    assert stored.get("pending_tx_queue") == user_state["pending_tx_queue"], \
        "auto-categorize dropped the pending_tx_queue"


# ─── Recat transfer guard ────────────────────────────────────────


@pytest.mark.asyncio
async def test_recat_refuses_transfer_rows(fake_world, monkeypatch):
    ws = sh._sheet(S.TRANSACTIONS)
    ws.update("A2:T2", [[
        "", "2026-08-20T10:00:00", "", "", "", "transfer a → b", "Tiền ra",
        "500000", "R1", "0", "", "", "FALSE", "TRUE", "2026-08", "VND",
        "acc_a", "transfer", "", "TRUE",
    ]])
    sh._invalidate_tx_rows_cache()

    resets = []
    monkeypatch.setattr(sh, "reset_transaction_row", lambda rn: resets.append(rn))

    await transaction.handle_recategorize(["recat", "2"], message_id=1)

    assert not resets, "transfer row must never be reset for recat"
    assert any("ledger riêng" in t for t in fake_world.sent["texts"])


# ─── Cron trigger auth helper ────────────────────────────────────


def test_cron_authorized(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "")
    assert main._cron_authorized("") is True      # unset → legacy open
    monkeypatch.setattr(main, "CRON_SECRET", "s3cret")
    assert main._cron_authorized("s3cret") is True
    assert main._cron_authorized("wrong") is False
    assert main._cron_authorized("") is False
