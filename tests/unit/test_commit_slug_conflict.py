"""Regression: wizard _commit must AUTO-LINK source to existing account
when user re-onboards an account whose slug already exists.

Production bug (2026-05-25): user created `bank_3456` via `/accounts add`
(no source). Later a SePay tx for sepay:1900123456 arrived → resolver
returned new_identifier → prompt fired → user ran wizard naming the
account "TPB 2601" again → slug `bank_3456` collision → _commit cancelled.
The right action is to bind the new source_key to the existing account.
"""
import pytest

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.accounts as accounts


@pytest.fixture
def bot_state_tab(fake_ss):
    """Create the BOT_STATE tab so set_state/clear_state work."""
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


@pytest.mark.asyncio
async def test_commit_slug_exists_with_source_links_to_existing(
    fake_ss, bot_state_tab, monkeypatch,
):
    # Pre-existing account with empty source_keys (user did /accounts add)
    sh.add_account(
        account_id="bank_3456", name="TPB 2601", acc_type="bank",
        currency="VND", source_keys=[],
    )
    sh.invalidate_accounts_cache()

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)

    # Simulate wizard state at the moment _commit is called: a SePay tx
    # triggered new_identifier for sepay:1900123456, user re-typed the
    # same account name.
    state = {
        "step": "await_new_account_balance",
        "pending_source_key": "sepay:1900123456",
        "pending_setup_key":  "",
        "pending_identifier": "1900123456",
        "new_acct_row_num":   0,
        "pending_account": {
            "name": "TPB 2601",
            "id":   "bank_3456",  # slug collides with existing
            "type": "bank",
            "currency": "VND",
            "starting_balance": 0,
        },
    }
    sh.set_state(CHAT_ID, state)

    await accounts._commit(state)

    # Should NOT have refused — should bind source_key to existing account
    assert any("link" in t.lower() or "đã có sẵn" in t.lower() for t in sent), \
        f"expected bind message, got: {sent!r}"
    assert not any("Hủy" in t for t in sent), \
        f"should not cancel; got: {sent!r}"

    # The existing account now has the source_key bound
    sh.invalidate_accounts_cache()
    acc = sh.find_account_by_id("bank_3456")
    assert "sepay:1900123456" in acc["source_keys"]

    # And resolver now matches future tx for this source
    from handlers.account_resolver import resolve_account
    res = resolve_account({"accountNumber": "1900123456"})
    assert res.status == "matched"
    assert res.account_id == "bank_3456"


@pytest.mark.asyncio
async def test_commit_slug_exists_without_source_still_errors(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Manual /accounts add path (no pending source_key) — slug collision
    is genuine 'pick another name' case, not a link opportunity."""
    sh.add_account(
        account_id="bank_3456", name="TPB 2601", acc_type="bank",
        currency="VND", source_keys=[],
    )
    sh.invalidate_accounts_cache()

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)

    state = {
        "step": "await_new_account_balance",
        "pending_source_key": "",  # ← no source (manual /accounts add)
        "pending_setup_key":  "",
        "pending_identifier": "",
        "new_acct_row_num":   0,
        "pending_account": {
            "name": "TPB 2601",
            "id":   "bank_3456",
            "type": "bank",
            "currency": "VND",
            "starting_balance": 0,
        },
    }
    sh.set_state(CHAT_ID, state)

    await accounts._commit(state)
    # Should refuse, no auto-link
    assert any("đã tồn tại" in t for t in sent), \
        f"expected slug-conflict error, got: {sent!r}"
