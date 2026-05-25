"""Wizard simplification — VND-default + 3-step bank/debit/cash flow.

Phase 1 OSS scope: only bank/debit/cash account types are supported.
Currency picker is skipped entirely (VND default). Credit card setup is
out of scope; the underlying ledger model still supports it but the
wizard refuses the type.
"""
import pytest

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.accounts as accounts


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


# ─── VND-only wizard skips currency ─────────────────────────────


@pytest.mark.asyncio
async def test_type_pick_bank_skips_currency_and_commits(
    fake_ss, bot_state_tab, monkeypatch,
):
    sent_text = []
    edited = []
    async def fake_send(text, chat_id=None):
        sent_text.append(text)
    async def fake_edit(message_id, text, chat_id=None, inline_keyboard=None):
        edited.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)
    monkeypatch.setattr(accounts.tg, "edit_message", fake_edit)

    # Wizard state right after user typed the account name
    sh.set_state(CHAT_ID, {
        "step": "await_new_account_type",
        "pending_source_key":  "",
        "pending_setup_key":   "",
        "pending_identifier":  "",
        "new_acct_row_num":    0,
        "pending_account": {"name": "TPB Main", "id": "tpb_main"},
    })

    await accounts._on_type_picked("bank", message_id=42)

    # Account committed with VND immediately — no currency buttons,
    # no Currency? prompt.
    assert not any("Currency?" in t for t in edited), \
        f"unexpected currency prompt: {edited}"
    acc = sh.find_account_by_id("tpb_main")
    assert acc is not None
    assert acc["currency"] == "VND"
    assert acc["type"] == "bank"


@pytest.mark.asyncio
async def test_type_pick_credit_is_rejected_out_of_scope(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Phase 1 OSS only accepts bank/debit/cash. 'credit' is silently
    ignored — _on_type_picked returns early. Credit-card support is on
    the Roadmap but not in the v1 wizard surface.
    """
    sh.set_state(CHAT_ID, {
        "step": "await_new_account_type",
        "pending_source_key":  "",
        "pending_setup_key":   "",
        "pending_identifier":  "",
        "new_acct_row_num":    0,
        "pending_account": {"name": "Cake Visa", "id": "cake_visa"},
    })

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    async def fake_edit(message_id, text, chat_id=None, inline_keyboard=None):
        sent.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)
    monkeypatch.setattr(accounts.tg, "edit_message", fake_edit)

    await accounts._on_type_picked("credit", message_id=42)

    # No account created, no further prompt sent
    assert sh.find_account_by_id("cake_visa") is None
    assert sent == []
