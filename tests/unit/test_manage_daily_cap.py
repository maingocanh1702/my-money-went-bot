"""Daily-cap editing via /manage (audit 2026-08-25 round 2).

/today used to say "dùng /manage để bật cap" while /manage had NO way to set
the cap — a dead-end instruction; the cap was only editable by hand in the
sheet. Now both channels edit Budget Config's daily_cap column directly.
"""
from datetime import datetime

import pytest
import pytz

import sheets as sh
from config import CHAT_ID, SHEETS as S
import handlers.manage as manage
import main


ZALO_CHAT = "1000000000000000001"
ZALO_KEY = f"zalo:{ZALO_CHAT}"


@pytest.fixture
def cap_world(monkeypatch, fake_ss):
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:F1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active"]])
    month_key = sh.fmt_month(datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
    ws_bc.update("A2:F2", [[month_key, "daily_spending", "🛒 Daily", 0, 100000, "TRUE"]])
    sh.invalidate_buckets_cache()

    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:P1", [["ID", "Date", "C", "D", "E", "Desc", "Type", "Amount",
                            "Ref", "Cum", "Bucket", "Sub", "IsDaily", "Confirmed",
                            "Month", "Currency"]])

    import telegram_api as tg
    import messenger

    sent = {"tg": [], "zalo": []}

    async def _tg_send(text, chat_id=None):
        sent["tg"].append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _tg_buttons(text, buttons, chat_id=None):
        sent["tg"].append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _zalo_text(text, channel="telegram", recipient_id=None, chat_id=None):
        sent["zalo" if channel == "zalo" else "tg"].append(text)

    monkeypatch.setattr(tg, "send_text", _tg_send)
    monkeypatch.setattr(tg, "send_with_buttons", _tg_buttons)
    monkeypatch.setattr(messenger, "send_text", _zalo_text)

    # Deterministic language for message assertions
    import i18n.core as i18n_core
    monkeypatch.setattr(i18n_core, "_lang_cache", "vi")

    fake_ss.sent = sent
    fake_ss.month_key = month_key
    return fake_ss


def _daily_cap_cell(fake_ss):
    ws = fake_ss.worksheet(S.BUDGET_CONFIG)
    return ws.row_values(2)[4]


# ─── Telegram ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tg_daily_cap_update(cap_world):
    state = {"step": "await_manage_daily_cap", "month_key": cap_world.month_key,
             "edit_bucket_id": "daily_spending"}
    sh.set_state(CHAT_ID, state)

    await manage.handle_manage_daily_cap("150k", state)

    assert _daily_cap_cell(cap_world) == "150000"
    assert any("150.000đ" in m for m in cap_world.sent["tg"])


@pytest.mark.asyncio
async def test_tg_daily_cap_zero_turns_off(cap_world):
    state = {"step": "await_manage_daily_cap", "month_key": cap_world.month_key,
             "edit_bucket_id": "daily_spending"}
    sh.set_state(CHAT_ID, state)

    await manage.handle_manage_daily_cap("0", state)

    assert _daily_cap_cell(cap_world) == ""
    assert any("tắt" in m.lower() for m in cap_world.sent["tg"])


@pytest.mark.asyncio
async def test_tg_daily_cap_rejects_garbage(cap_world):
    state = {"step": "await_manage_daily_cap", "month_key": cap_world.month_key,
             "edit_bucket_id": "daily_spending"}
    sh.set_state(CHAT_ID, state)

    await manage.handle_manage_daily_cap("abc", state)

    assert _daily_cap_cell(cap_world) == "100000", "garbage must not change the cap"


@pytest.mark.asyncio
async def test_tg_daily_bucket_menu_shows_cap_button(cap_world, monkeypatch):
    sh.set_state(CHAT_ID, {"step": "manage", "month_key": cap_world.month_key})
    # Sub-category tab is read by _show_bucket_actions
    ws_sub = cap_world.add_worksheet(S.SUBCATEGORY)
    ws_sub.update("A1:D1", [["bucket", "key", "label", "active"]])

    import telegram_api as tg

    captured = []

    async def _buttons(text, buttons, chat_id=None):
        captured.append(buttons)
        return {"ok": True, "result": {"message_id": 1}}

    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_with_buttons", _buttons)
    monkeypatch.setattr(tg, "edit_message", _noop)

    await manage._show_bucket_actions("daily_spending", message_id=1)

    flat = [b["callback_data"] for rows in captured for row in rows for b in row]
    assert "mg_dcap_daily_spending" in flat


# ─── Zalo ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zalo_daily_cap_update(cap_world):
    state = {"step": "zalo_manage_edit_daily_cap", "month_key": cap_world.month_key,
             "edit_bucket_id": "daily_spending", "edit_bucket_name": "🛒 Daily"}
    sh.set_state(ZALO_KEY, state)

    await main._zalo_manage_handle_edit_daily_cap(ZALO_CHAT, "2tr", state, ZALO_KEY)

    assert _daily_cap_cell(cap_world) == "2000000"
    assert any("2.000.000đ" in m for m in cap_world.sent["zalo"])


@pytest.mark.asyncio
async def test_zalo_bucket_menu_offers_daily_cap_only_for_daily(cap_world):
    # daily bucket → option 5 appears
    sh.set_state(ZALO_KEY, {"step": "zalo_manage", "month_key": cap_world.month_key})
    await main._zalo_manage_handle_menu(
        ZALO_CHAT, "1", sh.get_state(ZALO_KEY), ZALO_KEY)
    assert any("5. Daily cap" in m for m in cap_world.sent["zalo"])
