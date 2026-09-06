"""Reading money back out of a Google Sheet, and out of what a person types.

Google returns a cell as it is DISPLAYED, so the sheet's locale decides
whether fifty thousand đồng arrives as "50000", "50,000" or "50.000". Handing
that to float() reads the last one as fifty — a thousand-fold loss, silent,
in every total the row appears in. These tests pin the rule that decides what
a separator means, on both readers, so the two cannot drift apart again.
"""
import pytest

import sheets as sh
from config import SHEETS as S
from utils import parse_money


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


# ── the shape of the number decides, not float() ──────────────────────────

@pytest.mark.parametrize("cell,expected", [
    ("50000",        50_000),      # plain
    ("50,000",       50_000),      # US thousands
    ("50.000",       50_000),      # VN thousands — read as 50.0 before this fix
    ("1.234.567",    1_234_567),   # VN thousands, repeated — used to raise
    ("2,000,000",    2_000_000),   # US thousands, repeated
    ("1,234,567.89", 1_234_567.89),  # US thousands + decimal point
    ("50.000,50",    50_000.50),   # VN thousands + decimal comma
    ("50000.0",      50_000.0),    # float repr
    ("100.50",       100.50),      # two decimals
    ("1,5",          1.5),         # decimal comma — used to read as 15
    ("1.5",          1.5),
])
def test_a_cell_is_read_the_way_it_is_displayed(cell, expected):
    assert sh._parse_amount(cell) == pytest.approx(expected)


def test_the_vietnamese_locale_cell_is_not_read_as_a_thousandth_of_itself():
    """The one that quietly loses money: a VN-locale sheet shows 50000 as
    "50.000", and float() reads that as fifty."""
    assert sh._parse_amount("50.000") == 50_000
    assert sh._parse_amount("50.000") != 50.0


def test_the_two_money_readers_agree():
    """One rule for reading money, whether it came from a cell or a keyboard.
    They disagreed on every one of these before the shared resolver."""
    for text in ["50.000", "1.234.567", "1,234,567.89", "50.000,50", "1,5"]:
        assert sh._parse_amount(text) == parse_money(text), text


def test_a_typed_amount_with_grouping_and_decimals_is_not_multiplied():
    """parse_money stripped every separator when it saw more than one, so
    "1,234,567.89" became 123,456,789 — a hundredfold overcount."""
    assert parse_money("1,234,567.89") == pytest.approx(1_234_567.89)
    assert parse_money("50.000,50") == pytest.approx(50_000.50)


# ── decoration and notation the sheet adds by itself ──────────────────────

@pytest.mark.parametrize("cell,expected", [
    ("50.000 ₫",     50_000),
    ("HKD 300.00",   300.00),
    ("$1,234.56",    1_234.56),
    ("-100.000đ",    -100_000),
    ("(50.000)",     -50_000),     # accounting negative
])
def test_currency_decoration_does_not_change_the_number(cell, expected):
    assert sh._parse_amount(cell) == pytest.approx(expected)


def test_scientific_notation_survives():
    """Sheets renders large numbers as "1.23457E+12". Stripping separators
    out of that would mangle it, so it is recognised before they are touched."""
    assert sh._parse_amount("1.23457E+12") == pytest.approx(1.23457e12)
    assert sh._parse_amount("-2.5E+9") == pytest.approx(-2.5e9)


# ── what an unreadable cell does ──────────────────────────────────────────

def test_a_blank_cell_is_zero():
    assert sh._parse_amount("") == 0.0
    assert sh._parse_amount("   ") == 0.0


def test_an_unreadable_cell_is_loud_rather_than_zero():
    """A cell holding money the bot cannot parse is its owner's problem to
    see. Returning 0.0 would delete that money from every total instead."""
    with pytest.raises(ValueError):
        sh._parse_amount("n/a")


def test_to_num_still_turns_an_unreadable_cell_into_none():
    """Cells where blank-or-unset is legitimate (an inherited cashback rate)
    go through _to_num, which must keep absorbing the failure."""
    assert sh._to_num("n/a") is None
    assert sh._to_num("") is None
    assert sh._to_num("50.000") == 50_000


# ── and what it adds up to ────────────────────────────────────────────────

def test_a_month_of_vietnamese_locale_rows_totals_correctly(fake_ss):
    """The whole point: three salary rows displayed in a VN-locale sheet.
    Before the fix this totalled 45,000đ instead of 45,000,000đ."""
    rows = [
        ["1", "2026-09-01T09:00:00", "", "", "", "Salary", "Tiền vào",
         "20.000.000", "r1", "", "income", "", "", "TRUE", "2026-09", "VND"],
        ["2", "2026-09-05T09:00:00", "", "", "", "Bonus", "Tiền vào",
         "15.000.000", "r2", "", "income", "", "", "TRUE", "2026-09", "VND"],
        ["3", "2026-09-09T09:00:00", "", "", "", "Refund", "Tiền vào",
         "10.000.000", "r3", "", "income", "", "", "TRUE", "2026-09", "VND"],
    ]
    _seed_tx(fake_ss, rows)
    sh._tx_rows_cache.update({"ts": 0.0, "rows": None})

    assert sh.get_income_total("income", "2026-09") == 45_000_000
