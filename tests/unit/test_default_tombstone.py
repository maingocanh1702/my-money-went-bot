"""Cross-month tombstone for deleted default categories.

Regression: trên bản code cũ, default seed (vd Clothes/Work Supplements) bị
user xoá vẫn "sống lại" khi một tháng mới rơi vào nhánh default-seed. Tombstone
phải tôn trọng việc xoá: default đã xoá KHÔNG được re-seed ở tháng sau.
"""
import pytest

from config import SHEETS as S
import sheets as sh


HEADER = ["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X"]


def _bc(fake_ss):
    ws = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws.update("A1:H1", [HEADER])
    return ws


def _row(ws, month, bid, name, active):
    from sheets import _next_row
    n = _next_row(ws, col=1)
    ws.update(f"A{n}:H{n}", [[month, bid, name, 0, "", active, "test", ""]])


def test_deleted_default_not_reseeded_next_month(fake_ss, monkeypatch):
    """daily_spending bị xoá (FALSE) ở 2026-05 → bootstrap 2026-06 KHÔNG dựng lại."""
    ws = _bc(fake_ss)
    # May: user đã xoá daily_spending, giữ subscription
    _row(ws, "2026-05", "daily_spending", "🛒 Daily Spending", "FALSE")
    _row(ws, "2026-05", "subscription", "📱 Subscription", "TRUE")
    sh.invalidate_buckets_cache()

    created = sh.bootstrap_default_categories("2026-06")

    june = {b["id"] for b in sh.get_active_buckets("2026-06", force_refresh=True)}
    assert "daily_spending" not in june        # tombstone giữ được
    assert "subscription" in june              # default chưa xoá vẫn seed
    assert created == 1


def test_readded_default_seeds_again(fake_ss, monkeypatch):
    """Xoá ở 05 rồi thêm lại ở 06 (TRUE) → trạng thái mới nhất TRUE → 07 vẫn seed."""
    ws = _bc(fake_ss)
    _row(ws, "2026-05", "subscription", "📱 Subscription", "FALSE")  # xoá
    _row(ws, "2026-06", "subscription", "📱 Subscription", "TRUE")   # thêm lại
    sh.invalidate_buckets_cache()

    sh.bootstrap_default_categories("2026-07")

    july = {b["id"] for b in sh.get_active_buckets("2026-07", force_refresh=True)}
    assert "subscription" in july


def test_fresh_user_gets_all_defaults(fake_ss, monkeypatch):
    """Sheet rỗng → seed đầy đủ default set."""
    _bc(fake_ss)
    sh.invalidate_buckets_cache()

    created = sh.bootstrap_default_categories("2026-06")

    seeded = {b["id"] for b in sh.get_active_buckets("2026-06", force_refresh=True)}
    expected = {b["id"] for b in sh.get_default_buckets()}
    assert seeded == expected
    assert created == len(expected)


def test_same_month_delete_then_bootstrap_no_resurrect(fake_ss, monkeypatch):
    """Xoá trong CHÍNH tháng đó rồi bootstrap lại → không dựng lại (in-month check)."""
    ws = _bc(fake_ss)
    _row(ws, "2026-06", "daily_spending", "🛒 Daily Spending", "FALSE")  # vừa xoá
    sh.invalidate_buckets_cache()

    created = sh.bootstrap_default_categories("2026-06")

    june = {b["id"] for b in sh.get_active_buckets("2026-06", force_refresh=True)}
    assert "daily_spending" not in june
    assert created != 1 or "daily_spending" not in june  # never resurrected
