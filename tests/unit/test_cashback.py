"""tests/unit/test_cashback.py — Unit tests for cashback tracking feature.

Covers:
  1. CRUD: add/get/match/delete cashback rules
  2. Match priority: keyword > default, specific account > wildcard
  3. Logging: log_cashback idempotency + get_cashback_total/summary
  4. Auto-log on expense confirm (pct-based)
  5. Webhook income match (pct=0)
"""
import pytest
import sheets as sh
from config import SHEETS as S


# ─── Helpers ──────────────────────────────────────────────────

def _setup_cashback_rules_tab(fake_ws):
    """Create the Cashback Rules tab with header."""
    return fake_ws(S.CASHBACK_RULES, sh.CASHBACK_RULES_HEADER)


def _setup_cashback_log_tab(fake_ws):
    """Create the Cashback Log tab with header."""
    return fake_ws(S.CASHBACK_LOG, sh.CASHBACK_LOG_HEADER)


def _add_rule(ws, account_id, keyword, pct, category_id="*", active="TRUE",
              cb_min=0, cb_max=0, cb_cap=0):
    """Manually add a row to the Cashback Rules sheet."""
    row_num = len(ws.get_all_values()) + 1
    ws.update(f"A{row_num}:I{row_num}", [[
        account_id, keyword, str(pct), category_id, active, "2026-01-01T00:00:00",
        str(cb_min), str(cb_max), str(cb_cap),
    ]])
    sh.invalidate_cashback_rules_cache()
    return row_num


# ─── CRUD Tests ──────────────────────────────────────────────

def test_add_cashback_rule(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    ok = sh.add_cashback_rule("cake_cc", "shopee", 5.0, "*")
    assert ok is True

    rules = sh.get_cashback_rules(force_refresh=True)
    assert len(rules) == 1
    assert rules[0]["account_id"] == "cake_cc"
    assert rules[0]["keyword"] == "shopee"
    assert rules[0]["cashback_pct"] == 5.0


def test_add_duplicate_rule_returns_false(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    sh.add_cashback_rule("cake_cc", "shopee", 5.0)
    ok = sh.add_cashback_rule("cake_cc", "shopee", 3.0)  # same account + keyword
    assert ok is False
    assert len(sh.get_cashback_rules(force_refresh=True)) == 1


def test_add_default_rule_empty_keyword(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    ok = sh.add_cashback_rule("cake_cc", "", 1.0)
    assert ok is True
    rules = sh.get_cashback_rules(force_refresh=True)
    assert rules[0]["keyword"] == ""
    assert rules[0]["cashback_pct"] == 1.0


def test_soft_delete_rule(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    sh.add_cashback_rule("cake_cc", "shopee", 5.0)
    rules = sh.get_cashback_rules(force_refresh=True)
    assert len(rules) == 1

    sh.soft_delete_cashback_rule(rules[0]["row_num"])
    rules = sh.get_cashback_rules(force_refresh=True)
    assert len(rules) == 0


def test_update_cashback_rule(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    sh.add_cashback_rule("cake_cc", "shopee", 5.0)
    rules = sh.get_cashback_rules(force_refresh=True)

    sh.update_cashback_rule(rules[0]["row_num"], cashback_pct=3.0)
    rules = sh.get_cashback_rules(force_refresh=True)
    assert rules[0]["cashback_pct"] == 3.0


def test_get_rules_filter_by_account(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    sh.add_cashback_rule("cake_cc", "shopee", 5.0)
    sh.add_cashback_rule("tcb_debit", "grab", 1.0)

    cake_rules = sh.get_cashback_rules(account_id="cake_cc")
    assert len(cake_rules) == 1
    assert cake_rules[0]["account_id"] == "cake_cc"


def test_get_rules_wildcard_account_included(fake_ws):
    """Rules with account_id='*' should be returned for any account filter."""
    _setup_cashback_rules_tab(fake_ws)
    sh.add_cashback_rule("*", "", 0.5)
    sh.add_cashback_rule("cake_cc", "shopee", 5.0)

    rules = sh.get_cashback_rules(account_id="cake_cc")
    assert len(rules) == 2  # cake_cc specific + wildcard


# ─── Match Priority Tests ───────────────────────────────────

def test_match_keyword_over_default(fake_ws):
    """Specific keyword match should win over default (empty keyword) rule."""
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "cake_cc", "", 1)         # default: 1%
    _add_rule(ws, "cake_cc", "shopee", 5)   # keyword: 5%

    result = sh.match_cashback_rule("cake_cc", "SHOPEE THANH TOAN 500K")
    assert result is not None
    assert result["cashback_pct"] == 5.0
    assert result["keyword"] == "shopee"


def test_match_default_when_no_keyword_match(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "cake_cc", "", 1)         # default
    _add_rule(ws, "cake_cc", "shopee", 5)   # keyword

    result = sh.match_cashback_rule("cake_cc", "WINMART MUA HANG 200K")
    assert result is not None
    assert result["cashback_pct"] == 1.0
    assert result["keyword"] == ""


def test_match_specific_account_over_wildcard(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "*", "", 0.5)             # wildcard: 0.5%
    _add_rule(ws, "cake_cc", "", 1)         # specific: 1%

    result = sh.match_cashback_rule("cake_cc", "random expense")
    assert result is not None
    assert result["cashback_pct"] == 1.0
    assert result["account_id"] == "cake_cc"


def test_match_wildcard_for_unknown_account(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "*", "", 0.5)

    result = sh.match_cashback_rule("some_other_acc", "random expense")
    assert result is not None
    assert result["cashback_pct"] == 0.5


def test_match_returns_none_when_no_rules(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    result = sh.match_cashback_rule("cake_cc", "any description")
    assert result is None


def test_match_returns_none_for_wrong_account(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "cake_cc", "shopee", 5)

    result = sh.match_cashback_rule("tcb_debit", "SHOPEE 500K")
    assert result is None


def test_match_longest_keyword_wins(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "cake_cc", "shop", 1)
    _add_rule(ws, "cake_cc", "shopee", 5)

    result = sh.match_cashback_rule("cake_cc", "SHOPEE THANH TOAN")
    assert result is not None
    assert result["keyword"] == "shopee"
    assert result["cashback_pct"] == 5.0


def test_match_diacritics_insensitive(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "tcb_debit", "hoan tien", 0)

    result = sh.match_cashback_rule("tcb_debit", "HOÀN TIỀN THẺ TÍN DỤNG")
    assert result is not None


def test_match_inactive_rule_ignored(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "cake_cc", "shopee", 5, active="FALSE")

    result = sh.match_cashback_rule("cake_cc", "SHOPEE 500K")
    assert result is None


# ─── Logging Tests ───────────────────────────────────────────

def test_log_cashback_basic(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    row = sh.log_cashback(
        account_id="cake_cc", tx_row_num=10, amount=5000,
        currency="VND", source="rule_pct", rule_row_num=2,
        month_key="2026-08",
    )
    assert row > 0


def test_log_cashback_idempotent(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    row1 = sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    row2 = sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    assert row1 > 0
    assert row2 == 0  # dedup


def test_log_different_source_not_deduped(fake_ws):
    """Same tx_row but different source (rule_pct vs webhook) should both log."""
    _setup_cashback_log_tab(fake_ws)
    row1 = sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    row2 = sh.log_cashback("cake_cc", 10, 50000, "VND", "webhook", 3, "2026-08")
    assert row1 > 0
    assert row2 > 0


def test_get_cashback_total(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("cake_cc", 11, 3000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("cake_cc", 12, 2000, "VND", "rule_pct", 2, "2026-07")  # diff month

    total = sh.get_cashback_total("cake_cc", "2026-08")
    assert total == 8000


def test_get_cashback_total_ignores_other_accounts(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("tcb_debit", 11, 3000, "VND", "rule_pct", 3, "2026-08")

    total = sh.get_cashback_total("cake_cc", "2026-08")
    assert total == 5000


def test_get_cashback_summary(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("cake_cc", 11, 3000, "VND", "webhook", 3, "2026-08")
    sh.log_cashback("tcb_debit", 12, 2000, "VND", "rule_pct", 4, "2026-08")

    summary = sh.get_cashback_summary("2026-08")
    assert len(summary) == 2
    # Sorted by total desc
    assert summary[0]["account_id"] == "cake_cc"
    assert summary[0]["total"] == 8000
    assert summary[0]["by_source"]["rule_pct"] == 5000
    assert summary[0]["by_source"]["webhook"] == 3000
    assert summary[1]["account_id"] == "tcb_debit"
    assert summary[1]["total"] == 2000


def test_get_cashback_by_rule(fake_ws):
    ws_rules = _setup_cashback_rules_tab(fake_ws)
    _setup_cashback_log_tab(fake_ws)

    rule_rn = _add_rule(ws_rules, "cake_cc", "", 1)
    sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", rule_rn, "2026-08")
    sh.log_cashback("cake_cc", 11, 3000, "VND", "rule_pct", rule_rn, "2026-08")

    breakdown = sh.get_cashback_by_rule("cake_cc", "2026-08")
    assert len(breakdown) == 1
    assert breakdown[0]["total"] == 8000
    assert breakdown[0]["count"] == 2


# ─── Empty Account ID Edge Cases ────────────────────────────

def test_match_empty_account_returns_none(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    assert sh.match_cashback_rule("", "any description") is None


def test_add_rule_empty_account_returns_false(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    assert sh.add_cashback_rule("", "shopee", 5.0) is False


# ─── Min/Max/Cap Tests ──────────────────────────────────────

def test_rules_have_min_max_cap_fields(fake_ws):
    ws = _setup_cashback_rules_tab(fake_ws)
    _add_rule(ws, "cake_cc", "shopee", 5, cb_min=1000, cb_max=50000, cb_cap=200000)
    rules = sh.get_cashback_rules(force_refresh=True)
    assert rules[0]["cb_min"] == 1000
    assert rules[0]["cb_max"] == 50000
    assert rules[0]["cb_cap"] == 200000


def test_add_rule_with_limits(fake_ws):
    _setup_cashback_rules_tab(fake_ws)
    ok = sh.add_cashback_rule("cake_cc", "shopee", 5, cb_min=500, cb_max=100000, cb_cap=300000)
    assert ok is True
    rules = sh.get_cashback_rules(force_refresh=True)
    assert rules[0]["cb_min"] == 500
    assert rules[0]["cb_max"] == 100000
    assert rules[0]["cb_cap"] == 300000


def test_compute_no_limits(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 0, "cb_max": 0, "cb_cap": 0, "row_num": 2}
    amount, info = sh.compute_cashback_amount(5000, rule, "2026-08")
    assert amount == 5000
    assert info == ""


def test_compute_min_clamp(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 2000, "cb_max": 0, "cb_cap": 0, "row_num": 2}
    amount, info = sh.compute_cashback_amount(500, rule, "2026-08")
    assert amount == 2000
    assert "min" in info


def test_compute_max_clamp(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 0, "cb_max": 10000, "cb_cap": 0, "row_num": 2}
    amount, info = sh.compute_cashback_amount(50000, rule, "2026-08")
    assert amount == 10000
    assert "max" in info


def test_compute_cap_deduction(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 0, "cb_max": 0, "cb_cap": 100000, "row_num": 2}
    # Log 80k already used this month
    sh.log_cashback("cake_cc", 10, 80000, "VND", "rule_pct", 2, "2026-08")

    # Try to add 50k more → capped at 20k remaining
    amount, info = sh.compute_cashback_amount(50000, rule, "2026-08")
    assert amount == 20000
    assert "cap" in info


def test_compute_cap_exhausted(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 0, "cb_max": 0, "cb_cap": 100000, "row_num": 2}
    sh.log_cashback("cake_cc", 10, 100000, "VND", "rule_pct", 2, "2026-08")

    amount, info = sh.compute_cashback_amount(5000, rule, "2026-08")
    assert amount == 0
    assert "đã đạt cap" in info


def test_compute_cap_with_room(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 0, "cb_max": 0, "cb_cap": 200000, "row_num": 2}
    sh.log_cashback("cake_cc", 10, 50000, "VND", "rule_pct", 2, "2026-08")

    amount, info = sh.compute_cashback_amount(5000, rule, "2026-08")
    assert amount == 5000
    # Should show progress: 55,000đ/200,000đ
    assert "/" in info


def test_compute_min_max_cap_combo(fake_ws):
    """Test min + max + cap all together."""
    _setup_cashback_log_tab(fake_ws)
    rule = {"cb_min": 1000, "cb_max": 50000, "cb_cap": 200000, "row_num": 2}

    # Small amount → clamp up to min
    amount, info = sh.compute_cashback_amount(300, rule, "2026-08")
    assert amount == 1000

    # Large amount → clamp down to max
    amount2, info2 = sh.compute_cashback_amount(99000, rule, "2026-08")
    assert amount2 == 50000


def test_get_rule_month_total(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("cake_cc", 11, 3000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("cake_cc", 12, 2000, "VND", "rule_pct", 3, "2026-08")  # different rule

    total = sh.get_rule_month_total(2, "2026-08")
    assert total == 8000


def test_get_rule_month_total_ignores_other_months(fake_ws):
    _setup_cashback_log_tab(fake_ws)
    sh.log_cashback("cake_cc", 10, 5000, "VND", "rule_pct", 2, "2026-08")
    sh.log_cashback("cake_cc", 11, 3000, "VND", "rule_pct", 2, "2026-07")

    total = sh.get_rule_month_total(2, "2026-08")
    assert total == 5000
