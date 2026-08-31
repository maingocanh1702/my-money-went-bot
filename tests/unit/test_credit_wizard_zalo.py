"""Zalo credit wizard parity — collects statement/due like Telegram.

Credit cards are one shared entity; the Zalo wizard must run the same
limit → outstanding → statement → due steps and persist statement_day/due_day
onto the account (cols J/K), so a card created on Zalo behaves identically to
one created on Telegram.
"""
import pytest

import main
import sheets as sh
from config import SHEETS as S


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


@pytest.mark.asyncio
async def test_zalo_credit_wizard_collects_statement_due(fake_ss, bot_state_tab, monkeypatch):
    import messenger
    sent = []

    async def _st(text, channel=None, recipient_id=None):
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(messenger, "send_text", _st)

    key = "zalo:Z9"
    sh.set_state(key, {
        "step": "zalo_accounts_credit_limit",
        "pending_source_key": "",
        "pending_setup_key": "",
        "new_acct_row_num": None,
        "pending_account": {"name": "Cake Z", "id": "cake_z",
                            "type": "credit", "currency": "VND"},
    })
    await main._zalo_accounts_handle_credit_limit("Z9", "30000000", sh.get_state(key), key)
    await main._zalo_accounts_handle_credit_outstanding("Z9", "0", sh.get_state(key), key)
    # After outstanding the wizard must ask for the statement day, not commit.
    assert sh.get_state(key)["step"] == "zalo_accounts_credit_statement"
    assert sh.find_account_by_id("cake_z") is None

    await main._zalo_accounts_handle_credit_statement("Z9", "15", sh.get_state(key), key)
    await main._zalo_accounts_handle_credit_due("Z9", "25", sh.get_state(key), key)

    acc = sh.find_account_by_id("cake_z")
    assert acc is not None and acc["type"] == "credit"
    assert acc["credit_limit"] == 30000000
    assert acc["statement_day"] == 15 and acc["due_day"] == 25


@pytest.mark.asyncio
async def test_zalo_credit_wizard_statement_skip(fake_ss, bot_state_tab, monkeypatch):
    import messenger

    async def _st(text, channel=None, recipient_id=None):
        return {"ok": True}

    monkeypatch.setattr(messenger, "send_text", _st)

    key = "zalo:Z8"
    sh.set_state(key, {
        "step": "zalo_accounts_credit_outstanding",
        "pending_source_key": "",
        "pending_setup_key": "",
        "new_acct_row_num": None,
        "pending_account": {"name": "Visa Z", "id": "visa_z",
                            "type": "credit", "currency": "VND",
                            "credit_limit": 10000000},
    })
    await main._zalo_accounts_handle_credit_outstanding("Z8", "0", sh.get_state(key), key)
    await main._zalo_accounts_handle_credit_statement("Z8", "skip", sh.get_state(key), key)
    await main._zalo_accounts_handle_credit_due("Z8", "skip", sh.get_state(key), key)

    acc = sh.find_account_by_id("visa_z")
    assert acc is not None
    assert acc["statement_day"] is None and acc["due_day"] is None
