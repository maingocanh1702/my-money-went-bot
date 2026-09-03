"""Tests for /accounts assign — bulk historical backfill.

Use case: account onboarded after tx already landed. /accounts assign
<slug> scans unmapped tx (same currency), shows preview, commits on
confirm. One-time recovery; future tx self-resolve via the slug-auto-link
path (commit b9c4576) and Phase C source_key tracking.
"""
import json
import pytest

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.accounts as accounts


TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id",
]


def _seed_tx(fake_ss, rows):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:Q1", [TX_HEADER])
    for i, r in enumerate(rows):
        padded = list(r) + [""] * (17 - len(r))
        ws.update(f"A{i+2}:Q{i+2}", [padded])


def _seed_account(fake_ss, account_id, currency="VND"):
    sh.add_account(
        account_id=account_id, name=account_id.upper(),
        acc_type="bank", currency=currency, source_keys=[],
    )
    sh.invalidate_accounts_cache()


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


@pytest.mark.asyncio
async def test_assign_shows_preview_with_buttons(
    fake_ss, bot_state_tab, monkeypatch,
):
    _seed_account(fake_ss, "bank_3456", currency="VND")
    _seed_tx(fake_ss, [
        # 3 unmapped VND tx — eligible
        ["t1", "2026-05-01T10:00:00", "", "", "", "x", "Tiền ra", "100000",
         "r1", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", ""],
        ["t2", "2026-05-02T10:00:00", "", "", "", "y", "Tiền vào", "500000",
         "r2", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", ""],
        ["t3", "2026-05-03T10:00:00", "", "", "", "z", "Tiền ra", "50000",
         "r3", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", ""],
        # Already mapped — must be skipped
        ["t4", "2026-05-04T10:00:00", "", "", "", "w", "Tiền ra", "10000",
         "r4", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", "other_acc"],
        # Wrong currency — must be skipped
        ["t5", "2026-05-05T10:00:00", "", "", "", "u", "Tiền ra", "100",
         "r5", "0", "", "", "FALSE", "FALSE", "2026-05", "HKD", ""],
    ])

    sent = {}
    async def fake_send(text, buttons, chat_id=None):
        sent["text"] = text
        sent["buttons"] = buttons
    monkeypatch.setattr(accounts.tg, "send_with_buttons", fake_send)

    await accounts._cmd_accounts_assign("bank_3456")

    assert "bank_3456" in sent["text"]
    assert "3 tx" in sent["text"]   # only the 3 eligible ones
    assert "+500.000đ" in sent["text"]  # in total
    assert "-150.000đ" in sent["text"]  # out total
    cbs = [b["callback_data"] for row in sent["buttons"] for b in row]
    assert "asg_yes_bank_3456" in cbs
    assert "asg_no" in cbs

    # State stashed the candidate rows for the callback
    state = sh.get_state(CHAT_ID) or {}
    assert state.get("step") == "await_assign_confirm"
    assert state.get("assign_slug") == "bank_3456"
    assert sorted(state.get("assign_rows")) == [2, 3, 4]  # rows for t1, t2, t3


@pytest.mark.asyncio
async def test_assign_no_candidates_when_all_mapped(
    fake_ss, bot_state_tab, monkeypatch,
):
    _seed_account(fake_ss, "bank_3456")
    _seed_tx(fake_ss, [
        ["t1", "2026-05-01T10:00:00", "", "", "", "x", "Tiền ra", "100000",
         "r1", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", "bank_3456"],
    ])
    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)

    await accounts._cmd_accounts_assign("bank_3456")
    assert any("không cần backfill" in t for t in sent)


@pytest.mark.asyncio
async def test_assign_rejects_unknown_slug(fake_ss, bot_state_tab, monkeypatch):
    _seed_tx(fake_ss, [])
    sh._ensure_accounts_tab()
    sh.invalidate_accounts_cache()
    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)
    await accounts._cmd_accounts_assign("nonexistent")
    assert any("không tồn tại" in t for t in sent)


@pytest.mark.asyncio
async def test_assign_confirm_writes_account_id_to_rows(
    fake_ss, bot_state_tab, monkeypatch,
):
    _seed_account(fake_ss, "bank_3456")
    _seed_tx(fake_ss, [
        ["t1", "2026-05-01T10:00:00", "", "", "", "x", "Tiền ra", "100000",
         "r1", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", ""],
        ["t2", "2026-05-02T10:00:00", "", "", "", "y", "Tiền vào", "500000",
         "r2", "0", "", "", "FALSE", "FALSE", "2026-05", "VND", ""],
    ])

    # Prime state as if the user just saw the preview
    sh.set_state(CHAT_ID, {
        "step":        "await_assign_confirm",
        "assign_slug": "bank_3456",
        "assign_rows": [2, 3],
    })

    edited = {}
    async def fake_edit(message_id, text, chat_id=None, inline_keyboard=None):
        edited["text"] = text
    monkeypatch.setattr(accounts.tg, "edit_message", fake_edit)

    await accounts.handle_assign_callback(["asg", "yes", "bank_3456"], message_id=99)

    ws = sh._sheet(S.TRANSACTIONS)
    rows = ws.get_all_values()
    # Col Q (index 16) on rows 2 and 3 should now be "bank_3456"
    assert rows[1][16] == "bank_3456"
    assert rows[2][16] == "bank_3456"
    assert "2 tx" in edited["text"]
    # State cleared
    state = sh.get_state(CHAT_ID)
    assert not state or not state.get("assign_rows")


@pytest.mark.asyncio
async def test_assign_callback_no_cancels_and_clears_state(
    fake_ss, bot_state_tab, monkeypatch,
):
    sh.set_state(CHAT_ID, {
        "step":        "await_assign_confirm",
        "assign_slug": "bank_3456",
        "assign_rows": [2],
    })
    edited = {}
    async def fake_edit(message_id, text, chat_id=None, inline_keyboard=None):
        edited["text"] = text
    monkeypatch.setattr(accounts.tg, "edit_message", fake_edit)

    await accounts.handle_assign_callback(["asg", "no"], message_id=99)
    assert "hủy" in edited["text"].lower()
    state = sh.get_state(CHAT_ID)
    assert not state or not state.get("assign_rows")
