"""Tiền vào (incoming SePay tx) does NOT prompt for a category picker.

Project goal is tracking expenses per account. Income just needs to land
in Transactions + surface in /report's per-account Vào line. Forcing the
user to tap 'Bỏ qua' on every salary/refund was noise; income
categorization is out of scope.
"""
import pytest
from freezegun import freeze_time

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.sepay as sepay


# Freeze inside SePay's 10-minute stale window. Payload date = 14:00 ICT,
# so "now" = 14:05 ICT = 07:05 UTC keeps the tx fresh.
FROZEN_NOW_UTC = "2026-05-25 07:05:00"


TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id", "ledger_tx_type", "linked_tx_row",
    "ledger_applied", "account_source_key",
]


@pytest.fixture(autouse=True)
def tx_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:U1", [TX_HEADER])
    return ws


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


@pytest.fixture(autouse=True)
def budget_config_tab(fake_ss):
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    # Seed at least one bucket so _ensure_buckets doesn't trigger the
    # welcome message path
    bc.update("A2:F2", [["2026-05", "food", "🍕 Food", 0, "", "TRUE"]])
    sh._buckets_cache.clear()
    return bc


@freeze_time(FROZEN_NOW_UTC)
@pytest.mark.asyncio
async def test_incoming_tx_emits_notification_not_picker(
    fake_ss, bot_state_tab, monkeypatch,
):
    sh._ensure_accounts_tab()
    sh.invalidate_accounts_cache()

    sent_text = []
    sent_buttons = []
    async def fake_send_text(text, chat_id=None):
        sent_text.append(text)
    async def fake_send_buttons(text, buttons, chat_id=None):
        sent_buttons.append((text, buttons))
    monkeypatch.setattr(sepay.tg, "send_text", fake_send_text)
    monkeypatch.setattr(sepay.tg, "send_with_buttons", fake_send_buttons)

    payload = {
        "transferType":   "in",
        "transferAmount": 10_000_000,
        "content":        "BankAPINotify LUONG THANG 5",
        "referenceCode":  "FT26145890185611",
        "accountNumber":  "1900123456",
        "transactionDate": "2026-05-25 14:00:00",
    }
    await sepay.handle_sepay_webhook(payload)

    # Income notification was sent
    notifs = [t for t in sent_text if "vừa vào tài khoản" in t]
    assert len(notifs) == 1
    assert "10.000.000đ" in notifs[0]
    assert "LUONG THANG" in notifs[0]

    # No category-picker buttons. The account-onboarding prompt IS expected
    # (since this is a new sepay account) — those buttons have prefix
    # acc_setup_ / acc_skip_, not the p_<row>_<bucket> pattern of category
    # picker.
    all_callbacks = [
        b["callback_data"]
        for _text, button_rows in sent_buttons
        for row in button_rows
        for b in row
    ]
    category_cbs = [
        cb for cb in all_callbacks if cb.startswith("p_") or cb == "Bỏ qua"
    ]
    assert category_cbs == [], (
        f"unexpected category-picker callbacks for income: {category_cbs}"
    )

    # State NOT set to await_parent — user is free to do something else
    state = sh.get_state(CHAT_ID) or {}
    assert state.get("step") != "await_parent"
