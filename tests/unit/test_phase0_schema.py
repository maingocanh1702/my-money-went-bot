"""Phase 0 — Accounts/Ledger sheet bootstrap + Transactions cols Q–T.

These tests use the in-memory FakeSpreadsheet so they hit zero Google API.
"""
import pytest
import sheets as sh
from config import SHEETS as S
from datetime import datetime


def test_accounts_tab_created_with_correct_header(fake_ss):
    ws = sh._ensure_accounts_tab()
    rows = ws.get_all_values()
    assert rows[0] == sh.ACCOUNTS_HEADER
    # 15 cols per plan §2.1 + col P starting_outstanding (credit opening debt)
    # + cols Q/R linked_credit_id, redeem_only (cashback wallet, BRD §6.6,
    # declared in cashback Phase A so the header isn't changed twice).
    assert len(sh.ACCOUNTS_HEADER) == 18
    assert sh.ACCOUNTS_HEADER[15] == "starting_outstanding"
    assert sh.ACCOUNTS_HEADER[-1] == "redeem_only"


def test_ledger_tab_created_with_correct_header(fake_ss):
    ws = sh._ensure_ledger_tab()
    rows = ws.get_all_values()
    assert rows[0] == sh.LEDGER_HEADER
    assert len(sh.LEDGER_HEADER) == 9  # plan §2.3


def test_fmt_month_treats_naive_datetimes_as_local_time():
    # Bank email parsers return local Vietnam times without tzinfo. These must
    # stay in the same calendar month instead of being interpreted as UTC.
    assert sh.fmt_month(datetime(2026, 5, 31, 20, 30)) == "2026-05"


def test_ensure_accounts_tab_idempotent(fake_ss):
    ws1 = sh._ensure_accounts_tab()
    ws1.update("A2:B2", [["test_acct", "Test"]])
    ws2 = sh._ensure_accounts_tab()  # second call — should NOT recreate
    assert ws2.get_all_values()[1][:2] == ["test_acct", "Test"]


# ── Transactions append: cols Q–T appended with safe defaults ──

def _setup_tx_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    # Mirror the real header so col_values(2) correctly finds row 2 as next.
    header = [
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied",
    ]
    ws.update("A1:T1", [header])
    return ws


def test_append_transaction_default_extras(fake_ss):
    _setup_tx_tab(fake_ss)
    row_num = sh.append_transaction(
        "2026-05-10T10:00:00", "test desc", 50000, "REF1", "2026-05",
    )
    assert row_num == 2
    row = sh._sheet(S.TRANSACTIONS).row_values(row_num)
    # Q=account_id (idx 16), R=tx_type, S=linked_tx_row, T=ledger_applied
    assert row[16] == ""           # account_id default empty
    assert row[17] == "expense"    # tx_type default for outgoing
    assert row[18] == ""           # linked_tx_row default empty
    assert row[19] == "FALSE"      # ledger_applied default


def test_append_transaction_income_default_to_income_type(fake_ss):
    _setup_tx_tab(fake_ss)
    row_num = sh.append_transaction(
        "2026-05-10T10:00:00", "salary", 1_000_000, "REF2", "2026-05",
        tx_type="Tiền vào",
    )
    row = sh._sheet(S.TRANSACTIONS).row_values(row_num)
    assert row[6] == "Tiền vào"
    assert row[17] == "income"  # auto-derived from "Tiền vào"


def test_append_transaction_with_explicit_account_id(fake_ss):
    _setup_tx_tab(fake_ss)
    row_num = sh.append_transaction(
        "2026-05-10T10:00:00", "highland", 50000, "REF3", "2026-05",
        account_id="bank_main",
    )
    row = sh._sheet(S.TRANSACTIONS).row_values(row_num)
    assert row[16] == "bank_main"
    assert row[17] == "expense"
    assert row[19] == "FALSE"  # not yet applied


def test_append_transaction_with_linked_row(fake_ss):
    _setup_tx_tab(fake_ss)
    row_num = sh.append_transaction(
        "2026-05-10T10:00:00", "transfer", 1_000_000, "REF4", "2026-05",
        account_id="bank_main",
        ledger_tx_type="transfer",
        linked_tx_row=99,
    )
    row = sh._sheet(S.TRANSACTIONS).row_values(row_num)
    assert row[16] == "bank_main"
    assert row[17] == "transfer"
    assert row[18] == "99"
