import pytest

from config import CHAT_ID, SHEETS as S
import handlers.manage as manage
import sheets as sh


@pytest.mark.asyncio
async def test_start_manage_clones_previous_month_before_defaults(fake_ss, monkeypatch):
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [[
        "Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X",
    ]])
    ws_bc.update("A2:H2", [[
        "2026-05", "food", "🍕 Food", 2_000_000, "", "TRUE", "test", "",
    ]])
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "updated"]])
    sh.invalidate_buckets_cache()

    monkeypatch.setattr(sh, "fmt_month", lambda _dt: "2026-06")

    sent = {}

    async def fake_send_with_buttons(text, buttons):
        sent["text"] = text
        sent["buttons"] = buttons
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(manage.tg, "send_with_buttons", fake_send_with_buttons)

    await manage.start_manage()

    buckets = sh.get_active_buckets("2026-06", force_refresh=True)
    by_id = {b["id"]: b for b in buckets}
    assert by_id["food"]["allocated"] == 2_000_000
    assert "Daily Spending" not in sent["text"]
    assert sh.get_state(CHAT_ID)["month_key"] == "2026-06"
