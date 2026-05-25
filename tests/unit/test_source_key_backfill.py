"""Phase C — col U account_source_key + auto-backfill.

When a tx for an un-onboarded account arrives, append_transaction now
stores the raw source_key (e.g. "sepay:02635252601") in col U even
though col Q (account_id) is empty. Once the user onboards the account
later, sh.backfill_account_id_by_source_key matches col U and fills
col Q on all the orphan rows. The slug-auto-link path in _commit calls
this automatically.
"""
import json
import pytest

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.accounts as accounts


TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id", "ledger_tx_type", "linked_tx_row",
    "ledger_applied", "account_source_key",
]


def _seed_tx_table(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:U1", [TX_HEADER])
    return ws


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


# ─── append_transaction writes col U ────────────────────────────


def test_append_transaction_writes_source_key_to_col_u(fake_ss):
    _seed_tx_table(fake_ss)
    sh.append_transaction(
        tx_date="2026-05-25T10:00:00",
        description="GRAB", amount=50000, ref_code="r1",
        month_key="2026-05",
        tx_type="Tiền ra", currency="VND",
        account_id="",  # un-onboarded
        account_source_key="sepay:02635252601",
    )
    ws = sh._sheet(S.TRANSACTIONS)
    row = ws.row_values(2)
    assert row[16] == ""                      # account_id still empty
    assert row[20] == "sepay:02635252601"     # but col U has source_key


def test_append_transaction_lowercases_source_key(fake_ss):
    _seed_tx_table(fake_ss)
    sh.append_transaction(
        tx_date="2026-05-25T10:00:00",
        description="x", amount=1000, ref_code="r1",
        month_key="2026-05",
        account_source_key="Email_Cake:CAKE_CC",  # mixed case
    )
    row = sh._sheet(S.TRANSACTIONS).row_values(2)
    assert row[20] == "email_cake:cake_cc"


def test_append_transaction_default_source_key_empty(fake_ss):
    """Backward-compat: callers that don't pass account_source_key still work
    (col U just stays empty — same as legacy rows pre-Phase-C)."""
    _seed_tx_table(fake_ss)
    sh.append_transaction(
        tx_date="2026-05-25T10:00:00",
        description="x", amount=1000, ref_code="r1",
        month_key="2026-05",
    )
    row = sh._sheet(S.TRANSACTIONS).row_values(2)
    assert row[20] == ""


# ─── backfill_account_id_by_source_key ──────────────────────────


def test_backfill_assigns_account_id_to_matching_rows(fake_ss):
    _seed_tx_table(fake_ss)
    # 3 rows for sepay:02635252601 (no account_id yet) +
    # 1 row already mapped + 1 row with different source
    sh.append_transaction(
        tx_date="2026-05-20T10:00:00", description="a", amount=100,
        ref_code="r1", month_key="2026-05",
        account_source_key="sepay:02635252601",
    )
    sh.append_transaction(
        tx_date="2026-05-21T10:00:00", description="b", amount=200,
        ref_code="r2", month_key="2026-05",
        account_source_key="sepay:02635252601",
    )
    sh.append_transaction(
        tx_date="2026-05-22T10:00:00", description="c", amount=300,
        ref_code="r3", month_key="2026-05",
        account_id="already_mapped",
        account_source_key="sepay:02635252601",
    )
    sh.append_transaction(
        tx_date="2026-05-23T10:00:00", description="d", amount=400,
        ref_code="r4", month_key="2026-05",
        account_source_key="sepay:other_account",
    )

    n = sh.backfill_account_id_by_source_key(
        account_id="tpb_2601",
        source_key="sepay:02635252601",
    )
    assert n == 2  # only the 2 unmapped rows with matching source

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert rows[1][16] == "tpb_2601"           # was empty → filled
    assert rows[2][16] == "tpb_2601"           # was empty → filled
    assert rows[3][16] == "already_mapped"     # not overwritten
    assert rows[4][16] == ""                   # different source — skipped


def test_backfill_lowercases_source_key_for_matching(fake_ss):
    _seed_tx_table(fake_ss)
    sh.append_transaction(
        tx_date="2026-05-20T10:00:00", description="a", amount=100,
        ref_code="r1", month_key="2026-05",
        account_source_key="sepay:abc",
    )
    # Call with uppercase — should still match
    n = sh.backfill_account_id_by_source_key("tpb", "SEPAY:ABC")
    assert n == 1


def test_backfill_noop_when_source_or_account_empty(fake_ss):
    _seed_tx_table(fake_ss)
    sh.append_transaction(
        tx_date="2026-05-20T10:00:00", description="a", amount=100,
        ref_code="r1", month_key="2026-05",
        account_source_key="sepay:abc",
    )
    assert sh.backfill_account_id_by_source_key("", "sepay:abc") == 0
    assert sh.backfill_account_id_by_source_key("tpb", "") == 0


def test_backfill_noop_when_tx_tab_missing(fake_ss):
    """Edge case: account onboarding before any tx exists. The function
    shouldn't blow up — just return 0."""
    n = sh.backfill_account_id_by_source_key("tpb", "sepay:abc")
    assert n == 0


# ─── _commit invokes backfill end-to-end ────────────────────────


@pytest.mark.asyncio
async def test_commit_with_source_backfills_historical_tx(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Full integration: tx landed before account → user runs wizard →
    _commit creates account → backfill auto-fills account_id on the
    orphan tx. No need for /accounts assign in this path."""
    _seed_tx_table(fake_ss)
    # 2 orphan tx with source_key set
    sh.append_transaction(
        tx_date="2026-05-20T10:00:00", description="a", amount=100,
        ref_code="r1", month_key="2026-05",
        account_source_key="sepay:02635252601",
    )
    sh.append_transaction(
        tx_date="2026-05-21T10:00:00", description="b", amount=200,
        ref_code="r2", month_key="2026-05",
        account_source_key="sepay:02635252601",
    )

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(accounts.tg, "send_text", fake_send)

    state = {
        "step": "await_new_account_balance",
        "pending_source_key": "sepay:02635252601",
        "pending_setup_key":  "",
        "pending_identifier": "02635252601",
        "new_acct_row_num":   0,
        "pending_account": {
            "name": "TPB 2601", "id": "tpb_2601",
            "type": "bank", "currency": "VND",
            "starting_balance": 0,
        },
    }
    sh.set_state(CHAT_ID, state)

    await accounts._commit(state)

    # Account created
    sh.invalidate_accounts_cache()
    acc = sh.find_account_by_id("tpb_2601")
    assert acc is not None
    assert "sepay:02635252601" in acc["source_keys"]

    # Historical tx now bear the account_id
    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert rows[1][16] == "tpb_2601"
    assert rows[2][16] == "tpb_2601"
