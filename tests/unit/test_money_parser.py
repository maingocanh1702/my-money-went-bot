import pytest

import main
from utils import parse_money, parse_budget_amount


def test_parse_money_accepts_vietnamese_thousand_formats():
    assert main._parse_money("100.000đ") == 100_000
    assert main._parse_money("1.000đ") == 1_000
    assert main._parse_money("1,000 VND") == 1_000
    assert main._parse_money("1.000.000đ") == 1_000_000


def test_parse_money_accepts_plain_and_decimal_formats():
    assert main._parse_money("100000") == 100_000
    assert main._parse_money("100.50") == 100.5
    assert main._parse_money("1,5") == 1.5
    assert main._parse_money("-100.000đ") == -100_000


@pytest.mark.parametrize("text,expected", [
    ("500k", 500_000),
    ("2k5", 2_500),
    ("3tr", 3_000_000),
    ("3TR", 3_000_000),
    ("3tr5", 3_500_000),
    ("1.5tr", 1_500_000),
    ("2 triệu", 2_000_000),
    ("2 trieu", 2_000_000),
    ("1m", 1_000_000),
    ("1m2", 1_200_000),
    ("1 tỷ", 1_000_000_000),
    ("-500k", -500_000),
])
def test_parse_money_accepts_shorthand(text, expected):
    """Previously '500k' silently became 500đ (digit-strip). Now the
    Vietnamese shorthand parses to the intended value."""
    assert parse_money(text) == expected
    assert main._parse_money(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "abc", "tr", "k", "5tr/tháng", None])
def test_parse_money_rejects_garbage(text):
    assert parse_money(text) is None


def test_parse_budget_amount_semantics():
    """Budget fields: non-negative whole VND; garbage/negative rejected —
    previously 'abc' silently became 0 (flipping a bucket to tracking-only)."""
    assert parse_budget_amount("0") == 0
    assert parse_budget_amount("3tr") == 3_000_000
    assert parse_budget_amount("2,000,000") == 2_000_000
    assert parse_budget_amount("abc") is None
    assert parse_budget_amount("-500k") is None
