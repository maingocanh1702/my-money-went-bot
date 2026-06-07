"""Cross-month tombstone for deleted default categories.

Regression: tren ban code cu, default seed (vd Clothes/Work Supplements) bi
user xoa van "song lai" khi mot thang moi roi vao nhanh default-seed. Tombstone
phai ton trong viec xoa: default da xoa KHONG duoc re-seed o thang sau.
"""

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


def test_deleted_default_not_reseeded_next_month(fake_ss):
    """daily_spending bi xoa o 2026-05 thi 2026-06 khong dung lai."""
    ws = _bc(fake_ss)
    _row(ws, "2026-05", "daily_spending", "Daily Spending", "FALSE")
    _row(ws, "2026-05", "subscription", "Subscription", "TRUE")
    sh.invalidate_buckets_cache()

    created = sh.bootstrap_default_categories("2026-06")

    june = {b["id"] for b in sh.get_active_buckets("2026-06", force_refresh=True)}
    expected_count = len(sh.get_default_buckets()) - 1
    assert "daily_spending" not in june
    assert "subscription" in june
    assert created == expected_count


def test_readded_default_seeds_again(fake_ss):
    """Xoa o 05 roi them lai o 06 thi trang thai moi nhat TRUE cho phep seed."""
    ws = _bc(fake_ss)
    _row(ws, "2026-05", "subscription", "Subscription", "FALSE")
    _row(ws, "2026-06", "subscription", "Subscription", "TRUE")
    sh.invalidate_buckets_cache()

    sh.bootstrap_default_categories("2026-07")

    july = {b["id"] for b in sh.get_active_buckets("2026-07", force_refresh=True)}
    assert "subscription" in july


def test_fresh_user_gets_all_defaults(fake_ss):
    """Sheet rong thi seed day du default set."""
    _bc(fake_ss)
    sh.invalidate_buckets_cache()

    created = sh.bootstrap_default_categories("2026-06")

    seeded = {b["id"] for b in sh.get_active_buckets("2026-06", force_refresh=True)}
    expected = {b["id"] for b in sh.get_default_buckets()}
    assert seeded == expected
    assert created == len(expected)


def test_same_month_delete_then_bootstrap_no_resurrect(fake_ss):
    """Xoa trong chinh thang do roi bootstrap lai thi khong dung lai."""
    ws = _bc(fake_ss)
    _row(ws, "2026-06", "daily_spending", "Daily Spending", "FALSE")
    sh.invalidate_buckets_cache()

    created = sh.bootstrap_default_categories("2026-06")

    june = {b["id"] for b in sh.get_active_buckets("2026-06", force_refresh=True)}
    expected_count = len(sh.get_default_buckets()) - 1
    assert "daily_spending" not in june
    assert created == expected_count
