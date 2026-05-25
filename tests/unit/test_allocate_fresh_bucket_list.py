"""Regression for /allocate Enter-amounts iterating wrong bucket list.

Bug: _start_fresh used sh.get_default_buckets() (hard-coded list:
Daily Spending, Saving, Work Supplements, Clothes, Subscription) even
when the current month had its own customized bucket set (e.g. user
removed Work Supplements via /manage and added Coffee/Food/Drink/Sports).
The wizard then asked the user to allocate for buckets that don't exist
this month.

Fix: read sh.get_active_buckets(month_key) first; fall back to defaults
only when the month is truly empty (brand-new user).
"""
import pytest

import sheets as sh
from config import SHEETS as S, CHAT_ID
import handlers.allocation as alloc


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


def _seed_buckets(fake_ss, month_key, buckets):
    """Seed Budget Config tab with given buckets for month_key.
    `buckets` = list of {id, name, allocated, daily_cap?}.
    """
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    for i, b in enumerate(buckets):
        bc.update(
            f"A{i+2}:F{i+2}",
            [[month_key, b["id"], b["name"], b.get("allocated", 0),
              b.get("daily_cap", ""), "TRUE"]],
        )
    sh._buckets_cache.clear()


@pytest.mark.asyncio
async def test_start_fresh_uses_current_month_buckets(
    fake_ss, bot_state_tab, monkeypatch,
):
    """When the current month already has custom buckets, the wizard
    must iterate those — not the hard-coded defaults."""
    custom = [
        {"id": "daily_spending", "name": "🛒 Daily Spending"},
        {"id": "saving",         "name": "🏦 Saving"},
        {"id": "subscription",   "name": "📱 Subscription"},
        {"id": "sports",         "name": "🏋️ Sports"},
        {"id": "drink",          "name": "🍺 Drink"},
        {"id": "food",           "name": "🍕 Food"},
        {"id": "coffee",         "name": "☕ Coffee"},
    ]
    _seed_buckets(fake_ss, "2026-05", custom)

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)

    await alloc._start_fresh("2026-05")

    state = sh.get_state(CHAT_ID) or {}
    bucket_ids = [b["id"] for b in state["buckets"]]

    # Must match custom set exactly — no Work Supplements, no Clothes
    assert "work_supplements" not in bucket_ids
    assert "clothes" not in bucket_ids
    assert set(bucket_ids) == {
        "daily_spending", "saving", "subscription",
        "sports", "drink", "food", "coffee",
    }
    # First bucket prompt mentions one of the user's actual buckets
    assert any("Daily Spending" in t for t in sent)


@pytest.mark.asyncio
async def test_start_fresh_falls_back_to_defaults_when_month_empty(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Brand-new month with no buckets → fall back to hard-coded defaults
    so the wizard can still bootstrap. Original behavior for first-time users.
    """
    # Seed Budget Config tab with header only (empty for 2026-06)
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    sh._buckets_cache.clear()

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)

    await alloc._start_fresh("2026-06")

    state = sh.get_state(CHAT_ID) or {}
    bucket_ids = [b["id"] for b in state["buckets"]]
    # Defaults (hard-coded in sheets.get_default_buckets)
    defaults = [b["id"] for b in sh.get_default_buckets()]
    assert set(bucket_ids) == set(defaults)
