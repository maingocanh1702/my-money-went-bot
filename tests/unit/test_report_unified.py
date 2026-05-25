"""Smoke + behavior tests for the unified /report command.

Two lenses (account default, category) × 4 periods (w/m/q/y). Tests freeze
time at 2026-05-25 14:00 ICT (a Monday afternoon) so period-window
assertions are deterministic.
"""
from datetime import datetime

import json
import pytest
import pytz
from freezegun import freeze_time

import sheets as sh
from config import SHEETS as S, TIMEZONE
from handlers.report import (
    _period_range, _scan_period, _render_account_lens, _render_category_lens,
    _buttons, _budget_alerts, cmd_report, handle_report_callback,
)


FROZEN_NOW_UTC = "2026-05-25 07:00:00"  # 14:00 ICT (Mon afternoon)


# ─── Fixtures ────────────────────────────────────────────────────


TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id",
]


def _seed_tx(fake_ss, rows: list[list]):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:Q1", [TX_HEADER])
    for i, r in enumerate(rows):
        padded = list(r) + [""] * (17 - len(r))
        ws.update(f"A{i+2}:Q{i+2}", [padded])


def _seed_accounts(fake_ss, accounts: list[dict]):
    sh._ensure_accounts_tab()
    ws = sh._sheet(S.ACCOUNTS)
    for i, a in enumerate(accounts):
        row = [
            a["id"], a["name"], a["type"], a.get("currency", "VND"),
            json.dumps(a.get("source_keys", [])),
            0.0, 0.0, "", "", "", "", "", "TRUE",
            "2026-05-01T00:00:00", "",
        ]
        ws.update(f"A{i+2}:O{i+2}", [row])
    sh.invalidate_accounts_cache()


def _seed_buckets(fake_ss, buckets: list[dict]):
    """Seed Budget Config tab with month=2026-05.

    Each bucket: {id, name, allocated, daily_cap?}.
    """
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    for i, b in enumerate(buckets):
        bc.update(
            f"A{i+2}:F{i+2}",
            [["2026-05", b["id"], b["name"], b.get("allocated", 0),
              b.get("daily_cap", ""), "TRUE"]]
        )
    sh._buckets_cache.clear()


def _iso_local(year, month, day, hour=10):
    tz = pytz.timezone(TIMEZONE)
    return tz.localize(datetime(year, month, day, hour, 0, 0)).isoformat()


# ─── Period math ─────────────────────────────────────────────────


def test_period_range_week_starts_monday():
    tz = pytz.timezone(TIMEZONE)
    now = tz.localize(datetime(2026, 5, 25, 14, 30))  # Monday
    start, end = _period_range("w", now)
    assert start.weekday() == 0
    assert start.day == 25 and start.hour == 0


def test_period_range_month_quarter_year():
    tz = pytz.timezone(TIMEZONE)
    now = tz.localize(datetime(2026, 5, 25, 14, 30))
    assert _period_range("m", now)[0].day == 1
    assert _period_range("q", now)[0].month == 4  # Q2 starts April
    assert _period_range("y", now)[0].month == 1 and _period_range("y", now)[0].day == 1


# ─── Aggregation ─────────────────────────────────────────────────


@freeze_time(FROZEN_NOW_UTC)
def test_scan_groups_by_account_and_currency(fake_ss):
    _seed_buckets(fake_ss, [
        {"id": "food", "name": "🍕 Food", "allocated": 0},
        {"id": "saving", "name": "🏦 Saving", "allocated": 0},
    ])
    _seed_accounts(fake_ss, [
        {"id": "tpb_main", "name": "TPB Main", "type": "bank"},
        {"id": "cake_visa", "name": "Cake Visa", "type": "credit"},
    ])
    today = _iso_local(2026, 5, 20)
    _seed_tx(fake_ss, [
        ["t1", today, "", "", "", "FOOD", "Tiền ra", "100000", "r1", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb_main"],
        ["t2", today, "", "", "", "FOOD", "Tiền ra", "50000", "r2", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb_main"],
        ["t3", today, "", "", "", "SAL", "Tiền vào", "10000000", "r3", "0",
         "", "", "FALSE", "FALSE", "2026-05", "VND", "tpb_main"],
        ["t4", today, "", "", "", "SUB", "Tiền ra", "300000", "r4", "0",
         "subscription", "", "FALSE", "TRUE", "2026-05", "VND", "cake_visa"],
        ["t5", today, "", "", "", "CASH", "Tiền ra", "30000", "r5", "0",
         "daily_spending", "", "FALSE", "TRUE", "2026-05", "VND", ""],
    ])

    d = _scan_period("m")
    accs = {g["account_id"]: g for g in d["by_account"]}
    assert accs["tpb_main"]["out"] == 150000
    assert accs["tpb_main"]["in"] == 10000000
    assert accs["cake_visa"]["out"] == 300000
    assert accs[""]["out"] == 30000
    assert accs[""]["name"] == "Chưa gán account"
    # Unmapped sinks to bottom
    assert d["by_account"][-1]["account_id"] == ""
    # Totals (VND, confirmed, expense only)
    assert d["total_out"] == 480000
    assert d["total_in"] == 10000000


@freeze_time(FROZEN_NOW_UTC)
def test_scan_groups_by_bucket_with_allocations(fake_ss):
    _seed_buckets(fake_ss, [
        {"id": "food", "name": "🍕 Food", "allocated": 2000000},
        {"id": "coffee", "name": "☕ Coffee", "allocated": 500000},
        {"id": "saving", "name": "🏦 Saving", "allocated": 1000000},  # no spend
    ])
    _seed_accounts(fake_ss, [
        {"id": "tpb_main", "name": "TPB Main", "type": "bank"},
    ])
    today = _iso_local(2026, 5, 20)
    _seed_tx(fake_ss, [
        ["t1", today, "", "", "", "FOOD", "Tiền ra", "1500000", "r1", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb_main"],
        ["t2", today, "", "", "", "COF", "Tiền ra", "100000", "r2", "0",
         "coffee", "", "FALSE", "TRUE", "2026-05", "VND", "tpb_main"],
    ])

    d = _scan_period("m")
    by_id = {b["bucket_id"]: b for b in d["by_bucket"]}
    assert by_id["food"]["spent"] == 1500000
    assert by_id["food"]["allocated"] == 2000000
    assert by_id["coffee"]["allocated"] == 500000
    # Saving has allocation but no spending — still appears in monthly view
    assert "saving" in by_id
    assert by_id["saving"]["spent"] == 0
    assert by_id["saving"]["allocated"] == 1000000


@freeze_time(FROZEN_NOW_UTC)
def test_quarter_view_has_no_allocation(fake_ss):
    """For non-monthly periods, allocated=0 even if buckets have it."""
    _seed_buckets(fake_ss, [
        {"id": "food", "name": "🍕 Food", "allocated": 2000000},
    ])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    today = _iso_local(2026, 5, 20)
    _seed_tx(fake_ss, [
        ["t1", today, "", "", "", "FOOD", "Tiền ra", "1000000", "r1", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])

    d = _scan_period("q")
    food = next(b for b in d["by_bucket"] if b["bucket_id"] == "food")
    assert food["spent"] == 1000000
    assert food["allocated"] == 0  # quarter view doesn't surface allocation


@freeze_time(FROZEN_NOW_UTC)
def test_scan_unconfirmed_counts_in_flow_not_in_bucket(fake_ss):
    """Project goal is tracking ALL tx per account, not just categorized
    ones — so by_account and total_out include unconfirmed tx. Only
    by_bucket excludes them (no bucket assignment yet)."""
    _seed_buckets(fake_ss, [{"id": "food", "name": "Food", "allocated": 0}])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    today = _iso_local(2026, 5, 20)
    _seed_tx(fake_ss, [
        ["t1", today, "", "", "", "F1", "Tiền ra", "100000", "r1", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
        ["t2", today, "", "", "", "F2", "Tiền ra", "200000", "r2", "0",
         "food", "", "FALSE", "FALSE", "2026-05", "VND", "tpb"],
    ])

    d = _scan_period("m")
    # by_account: both counted (account flow doesn't filter by confirmed)
    assert d["by_account"][0]["out"] == 300000
    # total_out: both counted (honest flow total)
    assert d["total_out"] == 300000
    # by_bucket: confirmed only
    food = next(b for b in d["by_bucket"] if b["bucket_id"] == "food")
    assert food["spent"] == 100000


@freeze_time(FROZEN_NOW_UTC)
def test_heaviest_day_picked_correctly(fake_ss):
    _seed_buckets(fake_ss, [{"id": "food", "name": "Food", "allocated": 0}])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 5), "", "", "", "x", "Tiền ra", "100000", "r1", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
        ["t2", _iso_local(2026, 5, 15), "", "", "", "y", "Tiền ra", "500000", "r2", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
        ["t3", _iso_local(2026, 5, 15), "", "", "", "z", "Tiền ra", "200000", "r3", "0",
         "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])

    d = _scan_period("m")
    # 5/15 had 700k total (max), 5/5 had 100k
    assert d["heaviest_day"][0] == "15/05"
    assert d["heaviest_day"][1] == 700000


# ─── Budget alerts ───────────────────────────────────────────────


def test_budget_alerts_threshold():
    by_bucket = [
        {"name": "A", "allocated": 1000, "spent": 700},   # 70% — no alert
        {"name": "B", "allocated": 1000, "spent": 850},   # 85% — warn
        {"name": "C", "allocated": 1000, "spent": 1100},  # 110% — crit
        {"name": "D", "allocated": 0,    "spent": 500},   # no alloc — skip
    ]
    alerts = _budget_alerts(by_bucket)
    syms = {a[0]["name"]: a[1] for a in alerts}
    assert syms == {"B": "⚠️", "C": "🔴"}


# ─── Rendering ───────────────────────────────────────────────────


@freeze_time(FROZEN_NOW_UTC)
def test_account_lens_renders_account_section(fake_ss):
    _seed_buckets(fake_ss, [{"id": "food", "name": "🍕 Food", "allocated": 0}])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB Main", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 20), "", "", "", "x", "Tiền ra", "100000",
         "r1", "0", "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])
    d = _scan_period("m")
    out = _render_account_lens(d)
    assert "THEO ACCOUNT" in out
    assert "TPB Main" in out
    assert "🏦" in out


@freeze_time(FROZEN_NOW_UTC)
def test_account_lens_shows_budget_alert_when_monthly(fake_ss):
    _seed_buckets(fake_ss, [
        {"id": "food", "name": "🍕 Food", "allocated": 1000000},
    ])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 20), "", "", "", "x", "Tiền ra", "900000",
         "r1", "0", "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])
    d = _scan_period("m")
    out = _render_account_lens(d)
    assert "CẢNH BÁO BUDGET" in out
    assert "Food" in out
    assert "90%" in out


@freeze_time(FROZEN_NOW_UTC)
def test_account_lens_no_budget_alert_for_quarter(fake_ss):
    _seed_buckets(fake_ss, [
        {"id": "food", "name": "🍕 Food", "allocated": 1000000},
    ])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 20), "", "", "", "x", "Tiền ra", "900000",
         "r1", "0", "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])
    d = _scan_period("q")
    out = _render_account_lens(d)
    # Allocation isn't surfaced for non-monthly periods
    assert "CẢNH BÁO BUDGET" not in out


@freeze_time(FROZEN_NOW_UTC)
def test_category_lens_renders_budget_bars(fake_ss):
    _seed_buckets(fake_ss, [
        {"id": "food", "name": "🍕 Food", "allocated": 1000000},
        {"id": "coffee", "name": "☕ Coffee", "allocated": 0},  # tracking
    ])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 20), "", "", "", "x", "Tiền ra", "500000",
         "r1", "0", "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
        ["t2", _iso_local(2026, 5, 20), "", "", "", "y", "Tiền ra", "80000",
         "r2", "0", "coffee", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])
    d = _scan_period("m")
    out = _render_category_lens(d)
    assert "BUDGETED" in out
    assert "TRACKING" in out
    assert "🍕 Food" in out
    assert "☕ Coffee" in out
    assert "50%" in out  # 500k / 1M


# ─── Buttons ─────────────────────────────────────────────────────


def test_buttons_mark_current_selection():
    buttons = _buttons("m", "a")
    flat_period = [b["text"] for b in buttons[0]]
    lens_row = buttons[1]
    flat_lens = [b["text"] for b in lens_row]
    # Period: "Tháng" marked, others plain
    assert any(t.startswith("✅") and "Tháng" in t for t in flat_period)
    assert any(t == "Tuần" for t in flat_period)
    # Lens row order: Category (left, primary/default) | Account (right)
    assert "Category" in lens_row[0]["text"]
    assert "Account"  in lens_row[1]["text"]
    # 'a' lens selected → Account marked, Category plain
    assert lens_row[1]["text"].startswith("✅")
    assert not lens_row[0]["text"].startswith("✅")


def test_buttons_callback_data_pattern():
    buttons = _buttons("q", "c")
    all_buttons = [b for row in buttons for b in row]
    cb = [b["callback_data"] for b in all_buttons]
    # Period buttons preserve current lens (c)
    assert "rpt_w_c" in cb
    assert "rpt_m_c" in cb
    assert "rpt_q_c" in cb
    assert "rpt_y_c" in cb
    # Lens buttons preserve current period (q)
    assert "rpt_q_a" in cb
    assert "rpt_q_c" in cb


# ─── Smoke ───────────────────────────────────────────────────────


@freeze_time(FROZEN_NOW_UTC)
@pytest.mark.asyncio
async def test_cmd_report_default_is_category_lens_month(fake_ss, monkeypatch):
    _seed_buckets(fake_ss, [{"id": "food", "name": "Food", "allocated": 0}])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 20), "", "", "", "x", "Tiền ra", "100000",
         "r1", "0", "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])

    sent = {}
    async def fake_send(text, buttons, chat_id=None):
        sent["text"] = text
        sent["buttons"] = buttons
    import telegram_api as tg
    monkeypatch.setattr(tg, "send_with_buttons", fake_send)

    await cmd_report("/report")
    # Default lens: category (budget + insights front and center)
    assert "(lens: category)" in sent["text"]
    flat = [b for row in sent["buttons"] for b in row]
    cb = [b["callback_data"] for b in flat]
    assert "rpt_m_c" in cb  # current selection (month + category)
    assert "rpt_w_c" in cb
    assert "rpt_m_a" in cb  # account lens still one tap away


@freeze_time(FROZEN_NOW_UTC)
@pytest.mark.asyncio
async def test_callback_switches_lens(fake_ss, monkeypatch):
    _seed_buckets(fake_ss, [{"id": "food", "name": "Food", "allocated": 0}])
    _seed_accounts(fake_ss, [{"id": "tpb", "name": "TPB", "type": "bank"}])
    _seed_tx(fake_ss, [
        ["t1", _iso_local(2026, 5, 20), "", "", "", "x", "Tiền ra", "100000",
         "r1", "0", "food", "", "FALSE", "TRUE", "2026-05", "VND", "tpb"],
    ])

    edited = {}
    async def fake_edit(message_id, text, chat_id=None, inline_keyboard=None):
        edited["text"] = text
        edited["buttons"] = inline_keyboard
    import telegram_api as tg
    monkeypatch.setattr(tg, "edit_message", fake_edit)

    # Switch to category lens, month period
    await handle_report_callback(["rpt", "m", "c"], message_id=42)
    assert "(lens: category)" in edited["text"]
