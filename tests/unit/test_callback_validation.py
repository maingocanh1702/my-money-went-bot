"""tests/unit/test_callback_validation.py — Callback schema validation tests.

Ensures that malformed callback_data doesn't crash the bot, and that
callbacks from unauthorized chat IDs are rejected.
"""
import os
import pytest

from config import SHEETS as S


@pytest.fixture
def fake_world(monkeypatch, fake_ss):
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    import telegram_api as tg
    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}
    for name in ("send_text", "send_with_buttons", "edit_message",
                 "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, name, _noop)
    return fake_ss


def _make_cb(data: str, chat_id: int = None) -> dict:
    if chat_id is None:
        chat_id = int(os.environ.get("CHAT_ID", "0"))
    return {
        "id": "cb_test",
        "message": {"message_id": 42, "chat": {"id": chat_id}},
        "from": {"id": chat_id, "is_bot": False},
        "data": data,
    }


# ── Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_data_no_crash(fake_world):
    """Callback with empty data → gracefully ignored."""
    from main import _handle_callback
    await _handle_callback(_make_cb(""))


@pytest.mark.asyncio
async def test_unknown_prefix_no_crash(fake_world):
    """Callback with unrecognized prefix → ignored without crash."""
    from main import _handle_callback
    await _handle_callback(_make_cb("zzz_something"))


@pytest.mark.asyncio
async def test_missing_parts_no_crash(fake_world):
    """Callback with known prefix but insufficient parts → ignored."""
    from main import _handle_callback
    # "mg" prefix requires at least 2 parts ("mg_xxx")
    await _handle_callback(_make_cb("mg"))


@pytest.mark.asyncio
async def test_no_message_id_no_crash(fake_world, monkeypatch):
    """Callback missing message.message_id → ignored."""
    import telegram_api as tg
    async def _noop(*a, **k):
        return {"ok": True}
    monkeypatch.setattr(tg, "answer_callback", _noop)

    from main import _handle_callback
    cb = {
        "id": "cb_test",
        "message": {"chat": {"id": int(os.environ.get("CHAT_ID", "0"))}},
        "data": "mg_list",
    }
    await _handle_callback(cb)  # should not crash


@pytest.mark.asyncio
async def test_no_callback_id_no_crash(fake_world, monkeypatch):
    """Callback missing callback_query.id → ignored before answer_callback."""
    import telegram_api as tg
    async def fail_if_called(*a, **k):
        raise AssertionError("answer_callback should not be called without id")
    monkeypatch.setattr(tg, "answer_callback", fail_if_called)

    from main import _handle_callback
    cb = {
        "message": {"message_id": 42, "chat": {"id": int(os.environ.get("CHAT_ID", "0"))}},
        "data": "mg_list",
    }
    await _handle_callback(cb)


@pytest.mark.asyncio
async def test_valid_callback_dispatches(fake_world, monkeypatch):
    """Callback with valid prefix + correct chat_id → handler is called."""
    from main import _handle_callback
    import main

    dispatched = []
    async def fake_report_callback(parts, message_id):
        dispatched.append((parts, message_id))

    monkeypatch.setattr(main, "handle_report_callback", fake_report_callback)

    correct_chat_id = int(os.environ.get("CHAT_ID", "0"))
    cb = _make_cb("rpt_week", chat_id=correct_chat_id)
    await _handle_callback(cb)

    assert len(dispatched) == 1
    assert dispatched[0][0] == ["rpt", "week"]
    assert dispatched[0][1] == 42
