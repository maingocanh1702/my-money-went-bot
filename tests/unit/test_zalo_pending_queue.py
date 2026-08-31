"""Tests for the Zalo durable pending queue (audit 2026-08-25 round 2).

Zalo flows are text state machines: overwriting or clearing `zalo:<chat>`
kills any numbered picker. These tests pin the new guarantees:
  - a webhook arriving while the Zalo user is mid-flow PARKS the tx
    (state untouched) instead of clobbering their state;
  - a command over an active picker parks the picker's transactions;
  - /pending (Zalo) drains the parked queue;
  - finalize/cancel remind the user about parked transactions.
"""
from datetime import datetime

import pytest
import pytz

import sheets as sh
from config import SHEETS as S
import main
import handlers.sepay as sepay
from handlers import zalo_queue as zq


ZALO_CHAT = "397f0cd1e99c00c2598d"
ZALO_KEY = f"zalo:{ZALO_CHAT}"

TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id", "ledger_tx_type", "linked_tx_row",
    "ledger_applied", "account_source_key",
]


@pytest.fixture
def zalo_world(monkeypatch, fake_ss):
    """Tabs + stubbed Telegram/Zalo sends + Zalo enabled."""
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [TX_HEADER])

    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:F1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active"]])
    month_key = sh.fmt_month(datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
    ws_bc.update("A2:F2", [[month_key, "food", "🍜 Food", 0, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    import telegram_api as tg
    import messenger

    sent = {"tg": [], "zalo": []}

    async def _tg_send(text, chat_id=None):
        sent["tg"].append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _tg_buttons(text, buttons, chat_id=None):
        sent["tg"].append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _zalo_text(text, channel="telegram", recipient_id=None, chat_id=None):
        (sent["zalo"] if channel == "zalo" else sent["tg"]).append(text)

    async def _zalo_buttons(text, buttons, channel="telegram", recipient_id=None, chat_id=None):
        (sent["zalo"] if channel == "zalo" else sent["tg"]).append(text)

    monkeypatch.setattr(tg, "send_text", _tg_send)
    monkeypatch.setattr(tg, "send_with_buttons", _tg_buttons)
    monkeypatch.setattr(messenger, "send_text", _zalo_text)
    monkeypatch.setattr(messenger, "send_with_buttons", _zalo_buttons)

    for mod in (sepay, main):
        monkeypatch.setattr(mod, "ZALO_ENABLED", True, raising=False)
        monkeypatch.setattr(mod, "ZALO_CHAT_ID", ZALO_CHAT, raising=False)

    fake_ss.sent = sent
    fake_ss.month_key = month_key
    return fake_ss


def _payload(amount=50000, ref="ZQ1", desc="mystery merchant"):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return {
        "transferType": "out",
        "transferAmount": amount,
        "description": desc,
        "transactionDate": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": "VND",
        "referenceCode": ref,
    }


def _seed_unconfirmed_row(row_num=2, amount=50000, desc="GRAB RIDE"):
    ws = sh._sheet(S.TRANSACTIONS)
    month_key = sh.fmt_month(datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
    ws.update(f"A{row_num}:U{row_num}", [[
        "", datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).isoformat(), "", "", "",
        desc, "Tiền ra", str(amount), f"R{row_num}", "0", "", "", "FALSE", "FALSE",
        month_key, "VND", "", "expense", "", "FALSE", "",
    ]])
    sh._invalidate_tx_rows_cache()


# ─── Webhook must not clobber a Zalo mid-typing flow ─────────────


@pytest.mark.asyncio
async def test_webhook_parks_tx_when_zalo_user_mid_flow(zalo_world):
    sh.set_state(ZALO_KEY, {"step": "zalo_manage_rename", "edit_bucket_id": "food",
                            "month_key": zalo_world.month_key})

    await sepay.handle_sepay_webhook(_payload(ref="ZQPARK1"))

    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "zalo_manage_rename", \
        "webhook clobbered the Zalo user's in-progress flow"
    parked = zq.get_parked(ZALO_CHAT)
    assert len(parked) == 1 and parked[0]["amount"] == 50000
    assert any("/pending" in m for m in zalo_world.sent["zalo"])


@pytest.mark.asyncio
async def test_webhook_still_shows_picker_when_zalo_idle(zalo_world):
    await sepay.handle_sepay_webhook(_payload(ref="ZQIDLE1"))
    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "await_zalo_parent"
    assert zq.parked_count(ZALO_CHAT) == 0


# ─── Commands over an active picker park its transactions ────────


@pytest.mark.asyncio
async def test_zalo_command_parks_active_picker(zalo_world, monkeypatch):
    async def _noop(chat_id):
        pass

    monkeypatch.setattr(main, "_zalo_cmd_today", _noop)
    sh.set_state(ZALO_KEY, {
        "step": "await_zalo_parent", "row_num": 5, "amount": 10000,
        "currency": "VND", "description": "a", "tx_direction": "out",
        "buckets": [{"id": "food", "name": "Food"}],
        "queue": [{"row_num": 6, "amount": 20000, "currency": "VND",
                   "description": "b", "tx_direction": "out",
                   "buckets": [{"id": "food", "name": "Food"}]}],
    })

    await main._handle_zalo_text({
        "message": {"chat": {"id": ZALO_CHAT}, "text": "/today"},
    })

    assert not (sh.get_state(ZALO_KEY) or {}).get("step")
    parked = zq.get_parked(ZALO_CHAT)
    assert [p["row_num"] for p in parked] == [5, 6], \
        "command over an active picker must park its transactions"
    # `buckets` (picker-only key) must not be persisted in the parked items
    assert all("buckets" not in p for p in parked)


@pytest.mark.asyncio
async def test_zalo_cancel_mentions_parked(zalo_world):
    sh.set_state(ZALO_KEY, {
        "step": "await_zalo_parent", "row_num": 9, "amount": 5000,
        "currency": "VND", "description": "x", "tx_direction": "out",
        "buckets": [{"id": "food", "name": "Food"}], "queue": [],
    })
    await main._handle_zalo_text({
        "message": {"chat": {"id": ZALO_CHAT}, "text": "/cancel"},
    })
    assert zq.parked_count(ZALO_CHAT) == 1
    assert any("/pending" in m for m in zalo_world.sent["zalo"])


# ─── /pending drains the parked queue ────────────────────────────


@pytest.mark.asyncio
async def test_zalo_pending_promotes_parked_item(zalo_world):
    _seed_unconfirmed_row(row_num=2)
    zq.park(ZALO_CHAT, {"row_num": 2, "amount": 50000, "currency": "VND",
                        "description": "GRAB RIDE", "tx_direction": "out"})

    await main._zalo_cmd_pending(ZALO_CHAT, ZALO_KEY)

    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "await_zalo_parent"
    assert state.get("row_num") == 2
    assert zq.parked_count(ZALO_CHAT) == 0
    assert any("Khoản này thuộc mục nào?" in m for m in zalo_world.sent["zalo"])


@pytest.mark.asyncio
async def test_zalo_pending_skips_confirmed_rows(zalo_world):
    ws = sh._sheet(S.TRANSACTIONS)
    ws.update("A2:U2", [[
        "", "2026-08-20T10:00:00", "", "", "", "done", "Tiền ra", "9000",
        "R2", "0", "food", "", "FALSE", "TRUE", "2026-08", "VND",
        "", "expense", "", "FALSE", "",
    ]])
    sh._invalidate_tx_rows_cache()
    zq.park(ZALO_CHAT, {"row_num": 2, "amount": 9000, "currency": "VND",
                        "description": "done", "tx_direction": "out"})

    await main._zalo_cmd_pending(ZALO_CHAT, ZALO_KEY)

    assert zq.parked_count(ZALO_CHAT) == 0
    assert any("Không có giao dịch nào chờ" in m for m in zalo_world.sent["zalo"])
    assert not (sh.get_state(ZALO_KEY) or {}).get("step")


@pytest.mark.asyncio
async def test_zalo_pending_empty(zalo_world):
    await main._zalo_cmd_pending(ZALO_CHAT, ZALO_KEY)
    assert any("Không có giao dịch nào chờ" in m for m in zalo_world.sent["zalo"])


# ─── Finalize reminds about parked transactions ──────────────────


@pytest.mark.asyncio
async def test_zalo_finalize_reminds_parked(zalo_world):
    _seed_unconfirmed_row(row_num=2, desc="manual coffee")
    zq.park(ZALO_CHAT, {"row_num": 3, "amount": 1000, "currency": "VND",
                        "description": "parked", "tx_direction": "out"})

    await main._zalo_finalize_transaction(
        ZALO_CHAT, 2, "food", "",
        {"row_num": 2, "amount": 50000, "currency": "VND",
         "tx_direction": "out"},
        ZALO_KEY,
    )

    summary = next(m for m in zalo_world.sent["zalo"] if m.startswith("Logged:"))
    assert "chờ phân loại" in summary and "/pending" in summary
    assert zq.parked_count(ZALO_CHAT) == 1, "finalize must not consume parked items"


# ─── zalo_queue unit behavior ────────────────────────────────────


def test_park_dedupes_by_row_num(fake_ss):
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "updated"]])
    zq.park("c1", {"row_num": 4, "amount": 1})
    zq.park("c1", {"row_num": 4, "amount": 1})
    zq.park("c1", {"row_num": 5, "amount": 2})
    assert [p["row_num"] for p in zq.get_parked("c1")] == [4, 5]


def test_parked_queue_survives_flow_state_clears(fake_ss):
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "updated"]])
    zq.park(ZALO_CHAT, {"row_num": 8, "amount": 1})
    # Any amount of flow-state churn must not touch the parked queue.
    sh.set_state(ZALO_KEY, {"step": "zalo_manage"})
    sh.clear_state(ZALO_KEY)
    sh.set_state(ZALO_KEY, {"step": "await_zalo_kw_learn"})
    sh.clear_state(ZALO_KEY)
    assert zq.parked_count(ZALO_CHAT) == 1
