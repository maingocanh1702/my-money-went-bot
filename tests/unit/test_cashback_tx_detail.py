"""Per-transaction cashback detail block (render_cashback_tx_detail).

Appended under the "+X cashback" notice for a credit-card expense, scoped to the
card + its current statement cycle: this category's accrued/cap bar, cycle total
split pending/eligible, and the activation-gate bar + remaining-spend reminder.
"""
import pytest
import pytz
from datetime import datetime

import sheets as sh
from config import SHEETS as S
import handlers.report as report
import handlers.cashback as cb


def _setup_tabs(fake_ss):
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X"]])
    sh.invalidate_buckets_cache()
    sh.invalidate_cashback_caches()


def _seed_card():
    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit", currency="VND",
                   source_keys=["email_cake:cake_cc"], credit_limit=50_000_000,
                   statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()
    cb.seed_cake_card("cake_cc")


def _log_supermarket(amount: int, ref: str):
    """Append a Siêu thị (MCC 5411) expense + record cashback; return result dict."""
    now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
    r = sh.append_transaction(now.strftime("%Y-%m-%dT%H:%M:%S"), "WCM_WINMART HCM",
                              amount, ref, sh.fmt_month(now),
                              account_id="cake_cc", ledger_tx_type="expense")
    return sh.compute_and_record_cashback(r), r


def test_empty_when_no_config(fake_ss):
    _setup_tabs(fake_ss)
    assert report.render_cashback_tx_detail("nope", "nope_2026-06", "5411") == ""


def test_detail_has_all_four_blocks(fake_ss):
    _setup_tabs(fake_ss)
    _seed_card()
    result, _ = _log_supermarket(300_000, "D1")
    cycle = result["cycle"]
    mcc = next(l["mcc_code"] for l in result["lines"] if l["cashback_amount"] > 0)

    s = report.render_cashback_tx_detail("cake_cc", cycle, mcc)
    assert s != ""
    # 4. which card
    assert "Cake CC" in s
    # 1. this category accrued vs per-cycle cap (200k)
    assert "🛒 Siêu thị" in s
    assert "200.000" in s
    # 2. cycle total first, then activated portion (pending = total − activated)
    assert "Σ hoàn kỳ này" in s and "đã kích hoạt" in s
    # 3. activation gate (5tr) + remaining reminder (300k < 5tr → still pending)
    assert "5.000.000" in s
    assert "Cần chi tiêu thêm" in s


def test_gate_met_shows_qualified(fake_ss):
    _setup_tabs(fake_ss)
    _seed_card()
    # One large eligible tx clears the 5tr gate in a single shot.
    result, _ = _log_supermarket(5_200_000, "BIG")
    cycle = result["cycle"]
    mcc = next(l["mcc_code"] for l in result["lines"] if l["cashback_amount"] > 0)

    s = report.render_cashback_tx_detail("cake_cc", cycle, mcc)
    assert "Đã đủ điều kiện hoàn tiền" in s
    assert "Cần chi tiêu thêm" not in s


def test_snapshot_mcc_empty_lists_all_categories(fake_ss):
    """On-demand view (mcc='') lists every configured category + total, not just
    the one that earned cashback."""
    _setup_tabs(fake_ss)
    _seed_card()
    result, _ = _log_supermarket(300_000, "D1")  # only Siêu thị earned
    cycle = result["cycle"]

    s = report.render_cashback_tx_detail("cake_cc", cycle, "")  # no specific MCC
    # Every seeded category appears (even 0đ ones), not just Siêu thị.
    for name in ("Siêu thị", "Sàn TMĐT", "Du lịch", "Thời trang", "Di chuyển"):
        assert name in s, f"missing category {name}"
    assert "Σ hoàn kỳ này" in s
    # Siêu thị shows its accrued (5.400đ on a 1-tx/day 20% supermarket rule cap).
    line_5411 = next(ln for ln in s.splitlines() if "Siêu thị" in ln)
    assert "/200.000" in line_5411
