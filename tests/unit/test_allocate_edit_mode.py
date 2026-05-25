"""/allocate edit mode — when buckets already exist for the month, /allocate
shows a summary with per-bucket edit buttons instead of running the wizard
from scratch.

User feedback: 'sau khi set spending limit rồi, vào allocate vẫn set limit
được tiếp, trong khi flow đúng nên là nếu đã set xong limit rồi thì muốn
sửa chứ ko muốn set lại'.
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
async def test_allocate_shows_edit_view_when_buckets_exist(
    fake_ss, bot_state_tab, monkeypatch,
):
    """Second invocation of /allocate (current month has buckets) → edit
    view with per-bucket buttons, not the wizard."""
    _seed_buckets(fake_ss, "2026-05", [
        {"id": "saving",         "name": "🏦 Saving",         "allocated": 2000000},
        {"id": "food",           "name": "🍕 Food",            "allocated": 2000000},
        {"id": "coffee",         "name": "☕ Coffee",          "allocated": 0},  # tracking
    ])

    sent = {}
    async def fake_send(text, buttons, chat_id=None):
        sent["text"] = text
        sent["buttons"] = buttons
    monkeypatch.setattr(alloc.tg, "send_with_buttons", fake_send)

    # Patch datetime.now to return May 2026 — _start_monthly_allocation uses it
    import handlers.allocation as alloc_mod
    real_datetime = alloc_mod.__dict__.get("datetime")  # local imports

    # Easier: monkeypatch sh.fmt_month to return the expected key
    monkeypatch.setattr(sh, "fmt_month", lambda d: "2026-05")

    await alloc.start_monthly_allocation()

    # Should NOT contain wizard buttons (Keep / Enter amounts / Track / Skip)
    cbs = [b["callback_data"] for row in sent["buttons"] for b in row]
    assert not any(cb.startswith("al_copy_")  for cb in cbs)
    assert not any(cb.startswith("al_fresh_") for cb in cbs)
    assert not any(cb.startswith("al_track_") for cb in cbs)
    # Should contain edit buttons + reset
    assert any(cb == "al_editbucket_saving" for cb in cbs)
    assert any(cb == "al_editbucket_food"   for cb in cbs)
    assert any(cb == "al_editbucket_coffee" for cb in cbs)
    assert any(cb.startswith("al_resetall_") for cb in cbs)
    assert any(cb.startswith("al_close")    for cb in cbs)
    # Summary text has totals
    assert "2026-05" in sent["text"]
    assert "Total" in sent["text"]


@pytest.mark.asyncio
async def test_allocate_shows_wizard_when_no_buckets(
    fake_ss, bot_state_tab, monkeypatch,
):
    """First-time setup: no buckets for this month → wizard with
    Enter / Track / Skip buttons (existing behavior)."""
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    sh._buckets_cache.clear()

    sent = {}
    async def fake_send(text, buttons, chat_id=None):
        sent["text"] = text
        sent["buttons"] = buttons
    monkeypatch.setattr(alloc.tg, "send_with_buttons", fake_send)
    monkeypatch.setattr(sh, "fmt_month", lambda d: "2026-06")

    await alloc.start_monthly_allocation()

    cbs = [b["callback_data"] for row in sent["buttons"] for b in row]
    # Wizard buttons present
    assert any(cb.startswith("al_fresh_") for cb in cbs)
    assert any(cb.startswith("al_track_") for cb in cbs)
    assert any(cb.startswith("al_skip_")  for cb in cbs)
    # No edit buttons
    assert not any(cb.startswith("al_editbucket_") for cb in cbs)


@pytest.mark.asyncio
async def test_edit_bucket_callback_prompts_for_new_amount(
    fake_ss, bot_state_tab, monkeypatch,
):
    _seed_buckets(fake_ss, "2026-05", [
        {"id": "saving", "name": "🏦 Saving", "allocated": 2000000},
    ])
    sh.set_state(CHAT_ID, {
        "step": "await_edit_choice",
        "month_key": "2026-05",
    })

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)

    await alloc._start_edit_bucket("saving")

    assert any("Saving" in t and "2.000.000đ" in t for t in sent)
    state = sh.get_state(CHAT_ID) or {}
    assert state["step"] == "await_edit_bucket_amount"
    assert state["edit_bucket_id"] == "saving"


@pytest.mark.asyncio
async def test_edit_bucket_amount_saves_new_allocation(
    fake_ss, bot_state_tab, monkeypatch,
):
    _seed_buckets(fake_ss, "2026-05", [
        {"id": "saving", "name": "🏦 Saving", "allocated": 2000000},
    ])

    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    async def fake_send_buttons(text, buttons, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)
    monkeypatch.setattr(alloc.tg, "send_with_buttons", fake_send_buttons)

    state = {
        "step":             "await_edit_bucket_amount",
        "month_key":        "2026-05",
        "edit_bucket_id":   "saving",
        "edit_bucket_name": "🏦 Saving",
    }
    sh.set_state(CHAT_ID, state)

    await alloc.handle_edit_bucket_amount("3500000", state)

    # New allocation persisted in Budget Config
    sh.invalidate_buckets_cache()
    buckets = sh.get_active_buckets("2026-05")
    saving = next(b for b in buckets if b["id"] == "saving")
    assert saving["allocated"] == 3500000


@pytest.mark.asyncio
async def test_edit_bucket_amount_zero_is_track_only(
    fake_ss, bot_state_tab, monkeypatch,
):
    _seed_buckets(fake_ss, "2026-05", [
        {"id": "saving", "name": "🏦 Saving", "allocated": 2000000},
    ])

    async def fake_send(text, chat_id=None):
        pass
    async def fake_send_buttons(text, buttons, chat_id=None):
        pass
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)
    monkeypatch.setattr(alloc.tg, "send_with_buttons", fake_send_buttons)

    state = {
        "step":             "await_edit_bucket_amount",
        "month_key":        "2026-05",
        "edit_bucket_id":   "saving",
        "edit_bucket_name": "🏦 Saving",
    }
    sh.set_state(CHAT_ID, state)

    await alloc.handle_edit_bucket_amount("0", state)

    sh.invalidate_buckets_cache()
    saving = next(b for b in sh.get_active_buckets("2026-05") if b["id"] == "saving")
    assert saving["allocated"] == 0  # track-only


@pytest.mark.asyncio
async def test_close_edit_view_clears_state(
    fake_ss, bot_state_tab, monkeypatch,
):
    sh.set_state(CHAT_ID, {"step": "await_edit_choice", "month_key": "2026-05"})
    sent = []
    async def fake_send(text, chat_id=None):
        sent.append(text)
    monkeypatch.setattr(alloc.tg, "send_text", fake_send)

    await alloc._close_edit_view()
    state = sh.get_state(CHAT_ID)
    assert not state or not state.get("step")
