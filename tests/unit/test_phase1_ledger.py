"""Phase 1 — ledger math: idempotency, void/reverse, account cache."""
import pytest
import sheets as sh
from config import SHEETS as S


def _setup_tx_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    header = [
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied",
    ]
    ws.update("A1:T1", [header])
    return ws


def _seed_bank_account(account_id="tcb_main", starting=1_000_000, cur="VND"):
    sh.add_account(
        account_id=account_id,
        name=account_id,
        acc_type="bank",
        currency=cur,
        source_keys=[f"sepay:{account_id}"],
        starting_balance=starting,
    )
    sh.invalidate_accounts_cache()


def _seed_credit_account(account_id="cake_visa", limit=10_000_000):
    sh.add_account(
        account_id=account_id,
        name=account_id,
        acc_type="credit",
        currency="VND",
        source_keys=[f"sepay:{account_id}"],
        credit_limit=limit,
        statement_day=15,
        due_day=25,
    )
    sh.invalidate_accounts_cache()


# ── Idempotency ────────────────────────────────────────────────

def test_append_ledger_entry_dedup_on_repeat(fake_ss):
    sh._ensure_ledger_tab()

    id1 = sh.append_ledger_entry(
        tx_row_num=5, account_id="tcb_main", direction="-",
        amount=50000, currency="VND", tx_type="expense",
    )
    id2 = sh.append_ledger_entry(
        tx_row_num=5, account_id="tcb_main", direction="-",
        amount=50000, currency="VND", tx_type="expense",
    )
    assert id1 == id2 == "L5_1"
    rows = sh._get_ledger_rows()
    assert len(rows) == 1


def test_append_ledger_entry_two_legs_distinct(fake_ss):
    sh._ensure_ledger_tab()
    # Transfer: 1 tx row, 2 legs (out from acct A, in to acct B)
    sh.append_ledger_entry(
        tx_row_num=10, account_id="tcb_main", direction="-",
        amount=1_000_000, currency="VND", tx_type="transfer", leg="out",
    )
    sh.append_ledger_entry(
        tx_row_num=10, account_id="cake_main", direction="+",
        amount=1_000_000, currency="VND", tx_type="transfer", leg="in",
    )
    rows = sh._get_ledger_rows()
    assert len(rows) == 2


def test_is_and_mark_ledger_applied(fake_ss):
    _setup_tx_tab(fake_ss)
    row_num = sh.append_transaction("2026-05-10", "x", 100, "R1", "2026-05")
    assert sh.is_ledger_applied(row_num) is False
    sh.mark_ledger_applied(row_num)
    assert sh.is_ledger_applied(row_num) is True


# ── Void / reverse ─────────────────────────────────────────────

def test_void_ledger_for_tx(fake_ss):
    sh._ensure_ledger_tab()
    sh.append_ledger_entry(
        tx_row_num=5, account_id="tcb_main", direction="-",
        amount=50000, currency="VND", tx_type="expense",
    )
    voided = sh.void_ledger_for_tx(5)
    assert voided == 1
    # Subsequent get returns no active entries
    assert sh.get_ledger_entries_for_tx(5) == []
    # Re-running void is no-op
    assert sh.void_ledger_for_tx(5) == 0


def test_reset_transaction_row_voids_ledger_and_refreshes_cache(fake_ss):
    _setup_tx_tab(fake_ss)
    _seed_bank_account("tcb_main", starting=1_000_000)
    row_num = sh.append_transaction(
        "2026-05-10", "highland", 50000, "R1", "2026-05",
        account_id="tcb_main",
    )
    sh.append_ledger_entry(
        tx_row_num=row_num, account_id="tcb_main", direction="-",
        amount=50000, currency="VND", tx_type="expense",
    )
    sh.mark_ledger_applied(row_num)
    sh.update_account_cache("tcb_main")
    acc = sh.find_account_by_id("tcb_main")
    assert acc["running_balance"] == 950_000

    # Recat: reset clears ledger + restores starting balance
    sh.reset_transaction_row(row_num)
    assert sh.is_ledger_applied(row_num) is False
    sh.invalidate_accounts_cache()
    acc2 = sh.find_account_by_id("tcb_main")
    assert acc2["running_balance"] == 1_000_000


# ── Account cache math ─────────────────────────────────────────

def test_update_account_cache_bank_signed_sum(fake_ss):
    _seed_bank_account("tcb_main", starting=1_000_000)
    sh._ensure_ledger_tab()

    sh.append_ledger_entry(
        tx_row_num=2, account_id="tcb_main", direction="-",
        amount=200_000, currency="VND", tx_type="expense",
    )
    sh.append_ledger_entry(
        tx_row_num=3, account_id="tcb_main", direction="+",
        amount=500_000, currency="VND", tx_type="income",
    )
    sh.update_account_cache("tcb_main")
    acc = sh.find_account_by_id("tcb_main")
    # 1,000,000 − 200,000 + 500,000 = 1,300,000
    assert acc["running_balance"] == 1_300_000


def test_update_account_cache_credit_outstanding(fake_ss):
    _seed_credit_account("cake_visa", limit=10_000_000)
    sh._ensure_ledger_tab()

    # 2 spend events totalling 600k
    sh.append_ledger_entry(
        tx_row_num=2, account_id="cake_visa", direction="-",
        amount=400_000, currency="VND", tx_type="expense",
    )
    sh.append_ledger_entry(
        tx_row_num=3, account_id="cake_visa", direction="-",
        amount=200_000, currency="VND", tx_type="expense",
    )
    sh.update_account_cache("cake_visa")
    acc = sh.find_account_by_id("cake_visa")
    assert acc["outstanding_balance"] == 600_000

    # CC payment reduces outstanding by 500k
    sh.append_ledger_entry(
        tx_row_num=4, account_id="cake_visa", direction="+",
        amount=500_000, currency="VND", tx_type="cc_payment",
    )
    sh.update_account_cache("cake_visa")
    acc2 = sh.find_account_by_id("cake_visa")
    assert acc2["outstanding_balance"] == 100_000


def test_update_account_cache_skips_voided_entries(fake_ss):
    _seed_bank_account("tcb_main", starting=1_000_000)
    sh._ensure_ledger_tab()

    sh.append_ledger_entry(
        tx_row_num=2, account_id="tcb_main", direction="-",
        amount=200_000, currency="VND", tx_type="expense",
    )
    sh.update_account_cache("tcb_main")
    assert sh.find_account_by_id("tcb_main")["running_balance"] == 800_000

    sh.void_ledger_for_tx(2)
    sh.update_account_cache("tcb_main")
    assert sh.find_account_by_id("tcb_main")["running_balance"] == 1_000_000


def test_update_account_cache_currency_mismatch_skipped(fake_ss):
    """Defensive: a HKD entry sneaking into a VND account must NOT corrupt
    running_balance — update_account_cache filters by currency."""
    _seed_bank_account("tcb_main", starting=1_000_000, cur="VND")
    sh._ensure_ledger_tab()
    # Bypass append_ledger_entry's currency contract — manually inject a row
    ws = sh._ensure_ledger_tab()
    ws.append_row([
        "L_BAD", "9", "tcb_main", "-", 300, "HKD", "expense",
        "2026-05-10T00:00:00", "wrong currency",
    ])
    sh.update_account_cache("tcb_main")
    assert sh.find_account_by_id("tcb_main")["running_balance"] == 1_000_000
