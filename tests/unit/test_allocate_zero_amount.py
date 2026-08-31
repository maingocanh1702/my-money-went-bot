"""Regression: /allocate accepts 0 as a valid bucket amount.

User feedback: 'nếu ko muốn track 1 category nào đấy thì type 0 ở set
nhưng ko dc'. Old behavior rejected 0 with 'That's not a valid amount.
Try again (e.g. 3000000)'. 0 should be the canonical 'track-only, no
cap' marker — bucket survives in Budget Config with allocated=0, shows
under TRACKING in /report.
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


@pytest.fixture(autouse=True)
def budget_config_tab(fake_ss):
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    sh._buckets_cache.clear()
    return bc


@pytest.mark.asyncio
async def test_allocate_amount_zero_is_accepted(
    fake_ss, bot_state_tab, monkeypatch,
):
    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    async def fake_send_buttons(text, buttons, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)
    monkeypatch.setattr(alloc.tg, "send_with_buttons", fake_send_buttons)

    state = {
        "step":          "await_alloc_amount",
        "month_key":     "2026-05",
        "buckets":       [
            {"id": "saving",   "name": "🏦 Saving"},
            {"id": "clothes",  "name": "👗 Clothes"},
        ],
        "current_index": 0,
        "allocations":   [],
    }
    sh.set_state(CHAT_ID, state)

    # Type 0 for Saving — must NOT be rejected
    await alloc.handle_alloc_amount_input("0", state)
    assert not any("not a valid" in t for t in sent), \
        f"0 was rejected as invalid: {sent}"

    # State advanced to next bucket with allocation recorded
    new_state = sh.get_state(CHAT_ID) or {}
    assert new_state["current_index"] == 1
    assert new_state["allocations"] == [
        {"id": "saving", "name": "🏦 Saving", "allocated": 0},
    ]


@pytest.mark.asyncio
async def test_allocate_amount_negative_still_rejected(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Defensive — only digits are extracted from input, but if the parsed
    value were ever negative we'd still error. Verifies the boundary."""
    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)

    state = {
        "step":          "await_alloc_amount",
        "month_key":     "2026-05",
        "buckets":       [{"id": "saving", "name": "🏦 Saving"}],
        "current_index": 0,
        "allocations":   [],
    }
    sh.set_state(CHAT_ID, state)

    # Empty/garbage input still rejected
    await alloc.handle_alloc_amount_input("abc", state)
    assert any("hợp lệ" in t for t in sent)  # "Số không hợp lệ"
    # State unchanged
    s = sh.get_state(CHAT_ID)
    assert s["current_index"] == 0
