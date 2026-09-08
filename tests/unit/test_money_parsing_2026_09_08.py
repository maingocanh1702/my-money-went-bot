"""Guards for the 2026-09-08 audit's two money-parsing defects.

Both were silent: no exception, no warning, just the wrong number written to
the sheet and to the ledger.
"""
import pytest

import sheets as sh
import utils
from utils import parse_money


# ─── "1.500k" is 1500 thousand, not 1.5 thousand ─────────────────

@pytest.mark.parametrize("text, expected", [
    ("1.500k",     1_500_000),   # was 1_500 — the unit was thrown away
    ("20.000k",   20_000_000),   # was 20_000
    ("12.345k",   12_345_000),   # was 12_345
    ("1,500k",     1_500_000),   # comma grouping, same story
    ("1.500.000k", 1_500_000_000),
])
def test_shorthand_keeps_its_unit_when_the_number_is_grouped(text, expected):
    assert parse_money(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("500k",      500_000),
    ("100k",      100_000),
    ("1.5tr",   1_500_000),      # 1-2 digits after the separator is a decimal
    ("1,5tr",   1_500_000),
    ("0.5tr",     500_000),
    ("3tr5",    3_500_000),      # trailing-digit shorthand
    ("2k5",           2_500),
    ("1tr2",    1_200_000),
    ("2 trieu", 2_000_000),
    ("2 triệu", 2_000_000),
    ("1 ty",1_000_000_000),
])
def test_shorthand_forms_that_already_worked_still_work(text, expected):
    assert parse_money(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("1.500",       1_500),      # no unit: three digits is grouping
    ("1.234.567", 1_234_567),
    ("1,234,567", 1_234_567),
    ("100.50",      100.5),
])
def test_plain_amounts_are_unaffected(text, expected):
    assert parse_money(text) == expected


def test_shorthand_rejects_a_non_number_in_front_of_the_unit():
    assert parse_money("abck") is None
    assert parse_money("..k") is None


def test_transfer_amount_reaches_the_ledger_intact():
    """The path that made this expensive: /transfer, /cc pay and the account
    wizard all write parse_money's result straight into a ledger leg."""
    assert parse_money("1.500k") == parse_money("1500k") == 1_500_000


# ─── A rate is not money ─────────────────────────────────────────

@pytest.mark.parametrize("cell, expected", [
    ("0.015", 0.015),   # was 15.0 — a 1.5% card paid out 1500%
    ("0.025", 0.025),   # was 25.0
    ("0.005", 0.005),   # was 5.0
    ("0.075", 0.075),   # was 75.0
    ("0.125", 0.125),
])
def test_three_decimal_rates_are_not_read_as_thousands(cell, expected):
    assert sh._to_ratio(cell) == pytest.approx(expected)


@pytest.mark.parametrize("cell, expected", [
    ("0.2", 0.2), ("0.20", 0.2), ("0.01", 0.01), ("1", 1.0), ("0", 0.0),
    ("0,015", 0.015),        # a VN-locale sheet shows the decimal as a comma
    ("1.5%", 0.015),         # a percent-formatted cell
    ("20%", 0.2),
])
def test_rate_cell_shapes(cell, expected):
    assert sh._to_ratio(cell) == pytest.approx(expected)


def test_blank_rate_means_inherit():
    assert sh._to_ratio("") is None
    assert sh._to_ratio("   ") is None


def test_out_of_range_rate_is_refused_not_paid_out(capsys):
    """update_card_config rejects anything outside 0-1 at write time, so a cell
    holding it was hand-edited. Paying 200x back is the worse failure."""
    assert sh._to_ratio("2") is None
    assert sh._to_ratio("15") is None
    assert sh._to_ratio("-0.1") is None
    assert "out-of-range" in capsys.readouterr().out


def test_money_cells_still_read_grouping_as_grouping():
    """The fix must not leak into the money path: 50.000đ is fifty thousand."""
    assert sh._to_num("50.000") == 50_000
    assert sh._to_num("1.234.567") == 1_234_567
    assert sh._parse_amount("50.000") == 50_000


def test_rule_and_card_config_read_rates_through_the_ratio_parser():
    """Pin the call sites, so a future field added next to them can't quietly
    go back through the money parser."""
    src = open("sheets.py", encoding="utf-8").read()
    for field in ('"rate":', '"cashback_rate":', '"alert_pct":'):
        line = next(ln for ln in src.splitlines()
                    if ln.strip().startswith(field) and "_to_" in ln)
        assert "_to_ratio(" in line, f"{field} still parsed as money: {line.strip()}"


def test_utils_shorthand_uses_the_shared_separator_resolver():
    assert utils.resolve_separators("1.500") == "1500"
    assert utils.resolve_separators("1.5") == "1.5"
