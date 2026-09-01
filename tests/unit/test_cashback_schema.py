"""Phase A — cashback tab bootstrap + dynamic Accounts header.

Asserts each _ensure_*_tab writes the full header (no truncation) and the
Accounts header now extends to `redeem_only` (col R) — the bug being fixed is
the hardcoded `A1:O1` range that cut the header off at col O.
"""
import pytest
import sheets as sh


def _header_of(ws):
    rows = ws.get_all_values()
    assert rows, "tab created but empty"
    return rows[0]


# ── 5 new cashback tabs: full header, no truncation ───────────────

def test_cashback_rules_tab_full_header(fake_ss):
    ws = sh._ensure_cashback_rules_tab()
    assert _header_of(ws) == sh.CASHBACK_RULES_HEADER
    assert len(sh.CASHBACK_RULES_HEADER) == 18  # A–R per BRD §6.1


def test_cashback_tiers_tab_full_header(fake_ss):
    ws = sh._ensure_cashback_tiers_tab()
    assert _header_of(ws) == sh.CASHBACK_TIERS_HEADER
    assert len(sh.CASHBACK_TIERS_HEADER) == 4  # A–D per BRD §6.2


def test_cashback_config_tab_full_header(fake_ss):
    ws = sh._ensure_cashback_config_tab()
    assert _header_of(ws) == sh.CASHBACK_CONFIG_HEADER
    assert len(sh.CASHBACK_CONFIG_HEADER) == 6  # A–F per BRD §6.3


def test_cashback_ledger_tab_full_header_has_reason(fake_ss):
    ws = sh._ensure_cashback_ledger_tab()
    assert _header_of(ws) == sh.CASHBACK_LEDGER_HEADER
    assert len(sh.CASHBACK_LEDGER_HEADER) == 13  # A–M per BRD §6.4
    assert sh.CASHBACK_LEDGER_HEADER[-1] == "reason"  # col M — 0đ audit reason


def test_mcc_map_tab_full_header(fake_ss):
    ws = sh._ensure_mcc_map_tab()
    assert _header_of(ws) == sh.MCC_MAP_HEADER
    assert len(sh.MCC_MAP_HEADER) == 7  # A–G per BRD §6.5


# ── Accounts header: dynamic range, extends to redeem_only ────────

def test_accounts_header_extends_to_redeem_only(fake_ss):
    assert len(sh.ACCOUNTS_HEADER) == 18
    assert sh.ACCOUNTS_HEADER[-2] == "linked_credit_id"
    assert sh.ACCOUNTS_HEADER[-1] == "redeem_only"


def test_ensure_accounts_tab_writes_full_header_no_truncation(fake_ss):
    # The bug: `A1:O1` truncated the header at col O (15 cells). Dynamic range
    # must write all 18 cells so credit accounts get linked_credit_id/redeem_only.
    ws = sh._ensure_accounts_tab()
    header = _header_of(ws)
    assert header == sh.ACCOUNTS_HEADER
    assert len(header) == 18
    assert header[-1] == "redeem_only"
