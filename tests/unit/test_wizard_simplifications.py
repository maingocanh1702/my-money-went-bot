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
async def test_type_pick_credit_opens_credit_flow(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Credit is now supported on Telegram (parity with Zalo). Picking
    'credit' doesn't commit immediately — it advances to await_credit_limit
    and prompts for the limit; the account is created only after the full
    credit flow (limit → outstanding → statement → due).
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

    # Not committed yet — waiting for the limit, with a prompt asking for it.
    assert sh.find_account_by_id("cake_visa") is None
    assert sh.get_state(CHAT_ID)["step"] == "await_credit_limit"
    assert any("Hạn mức" in t for t in sent)


@pytest.mark.asyncio
async def test_full_credit_flow_collects_statement_and_due(
    fake_ss, bot_state_tab, monkeypatch,
):
    """End-to-end TG credit wizard: limit → outstanding → statement → due
    → commit, with statement_day/due_day persisted on the account."""
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(accounts.tg, "send_text", _noop)
    monkeypatch.setattr(accounts.tg, "edit_message", _noop)

    sh.set_state(CHAT_ID, {
        "step": "await_new_account_type",
        "pending_source_key":  "",
        "pending_setup_key":   "",
        "pending_identifier":  "",
        "new_acct_row_num":    0,
        "pending_account": {"name": "Cake Visa", "id": "cake_visa"},
    })
    await accounts._on_type_picked("credit", message_id=1)
    await accounts.handle_credit_limit("30000000", sh.get_state(CHAT_ID))
    await accounts.handle_credit_outstanding("0", sh.get_state(CHAT_ID))
    await accounts.handle_credit_statement("15", sh.get_state(CHAT_ID))
    await accounts.handle_credit_due("25", sh.get_state(CHAT_ID))

    acc = sh.find_account_by_id("cake_visa")
    assert acc is not None
    assert acc["type"] == "credit"
    assert acc["credit_limit"] == 30000000
    assert acc["statement_day"] == 15 and acc["due_day"] == 25


@pytest.mark.asyncio
async def test_credit_flow_statement_skip_leaves_calendar_month(
    fake_ss, bot_state_tab, monkeypatch,
):
    """'skip' at the statement step → statement_day unset (calendar-month
    fallback), settable later."""
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(accounts.tg, "send_text", _noop)
    monkeypatch.setattr(accounts.tg, "edit_message", _noop)

    sh.set_state(CHAT_ID, {
        "step": "await_new_account_type", "pending_source_key": "",
        "pending_setup_key": "", "pending_identifier": "", "new_acct_row_num": 0,
        "pending_account": {"name": "Visa B", "id": "visa_b"},
    })
    await accounts._on_type_picked("credit", message_id=1)
    await accounts.handle_credit_limit("10000000", sh.get_state(CHAT_ID))
    await accounts.handle_credit_outstanding("0", sh.get_state(CHAT_ID))
    await accounts.handle_credit_statement("skip", sh.get_state(CHAT_ID))
    await accounts.handle_credit_due("skip", sh.get_state(CHAT_ID))

    acc = sh.find_account_by_id("visa_b")
    assert acc is not None
    assert acc["statement_day"] is None and acc["due_day"] is None


def test_parse_billing_day():
    assert accounts.parse_billing_day("15") == (15, True, None)
    assert accounts.parse_billing_day("skip") == (None, True, None)
    assert accounts.parse_billing_day("")[1] is True and accounts.parse_billing_day("")[0] is None
    # out of range / non-numeric → not ok, with an error message
    assert accounts.parse_billing_day("31")[1] is False
    assert accounts.parse_billing_day("abc")[1] is False
