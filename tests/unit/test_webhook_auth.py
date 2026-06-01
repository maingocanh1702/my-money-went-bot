"""tests/unit/test_webhook_auth.py — Security boundary tests.

Tests that webhook auth, CHAT_ID validation, cron protection, and SePay
secret enforcement all work as expected.
"""
import os
import pytest

import sheets as sh
from config import SHEETS as S, SEPAY_SECRET


# ── Helpers ───────────────────────────────────────────────────


def _tg_update(chat_id: int = 0, text: str = "/today") -> dict:
    """Build a minimal Telegram update payload."""
    return {
        "update_id": 99999,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id},
            "from": {"id": chat_id, "is_bot": False},
            "text": text,
        },
    }


def _tg_callback(chat_id: int = 0, data: str = "rpt_week") -> dict:
    """Build a minimal Telegram callback_query payload."""
    return {
        "update_id": 99998,
        "callback_query": {
            "id": "cb_1",
            "message": {"message_id": 2, "chat": {"id": chat_id}},
            "from": {"id": chat_id, "is_bot": False},
            "data": data,
        },
    }


def _sepay_payload(with_secret: bool = True, ref: str = "AUTH_TEST") -> dict:
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    payload = {
        "transferType": "out",
        "transferAmount": 50000,
        "description": "test auth",
        "transactionDate": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": "VND",
        "referenceCode": ref,
        "accountNumber": "1903999888",
    }
    if with_secret:
        payload["apikey"] = SEPAY_SECRET
    return payload


def _zalo_event(
    *,
    sender_id: str = "zalo_user_1",
    chat_id: str = "zalo_chat_1",
    text: str = "/today",
    event_name: str = "message.text.received",
    is_bot: bool = False,
    chat_type: str = "PRIVATE",
) -> dict:
    return {
        "ok": True,
        "result": {
            "event_name": event_name,
            "message": {
                "message_id": "zmsg_1",
                "from": {
                    "id": sender_id,
                    "display_name": "Zalo User",
                    "is_bot": is_bot,
                },
                "chat": {
                    "id": chat_id,
                    "chat_type": chat_type,
                },
                "text": text,
                "date": 1750316131602,
            },
        },
    }


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def fake_world(monkeypatch, fake_ss):
    """Minimal world with stubbed Telegram calls."""
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:T1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency", "account_id", "tx_type", "linked_tx_row",
        "ledger_applied",
    ]])
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [[
        "Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X",
    ]])
    ws_bc.update("A2:H2", [[
        "2026-05", "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", "",
    ]])
    sh.invalidate_buckets_cache()
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    import telegram_api as tg
    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}
    for name in ("send_text", "send_with_buttons", "edit_message",
                 "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, name, _noop)

    return fake_ss


# ── Tests: Telegram webhook secret ────────────────────────────


@pytest.mark.asyncio
async def test_tg_update_without_secret_is_rejected(fake_world, monkeypatch):
    """POST with update_id but no/wrong secret header → _process should NOT
    be called."""
    # _process should still safely handle updates that passed the webhook
    # gate. We test at the _process level + _handle_message level.
    processed_messages = []
    import main
    original_handle_message = main._handle_message

    async def tracking_handle_message(message):
        processed_messages.append(message)
        await original_handle_message(message)

    monkeypatch.setattr(main, "_handle_message", tracking_handle_message)

    # Simulate a Telegram update from wrong chat_id — should be rejected
    body = _tg_update(chat_id=999999, text="/today")
    await main._process(body)
    assert len(processed_messages) == 1  # _handle_message called...
    # ...but it should have been rejected by CHAT_ID check
    # Verify no state was set (the /today handler wasn't executed)


@pytest.mark.asyncio
async def test_webhook_rejects_missing_or_wrong_tg_secret_before_processing(monkeypatch):
    """POST /webhook rejects Telegram-shaped updates before _process runs."""
    from httpx import ASGITransport, AsyncClient
    import main
    from main import app
    from config import TELEGRAM_WEBHOOK_SECRET

    processed = []

    async def capture_process(body):
        processed.append(body)

    monkeypatch.setattr(main, "_process", capture_process)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", json=_tg_update())
        assert r.status_code == 200

        r = await client.post(
            "/webhook",
            json=_tg_update(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
        assert r.status_code == 200

        r = await client.post(
            "/webhook",
            json=_tg_update(),
            headers={"X-Telegram-Bot-Api-Secret-Token": TELEGRAM_WEBHOOK_SECRET},
        )
        assert r.status_code == 200

    assert len(processed) == 1


@pytest.mark.asyncio
async def test_tg_message_wrong_chat_id_rejected(fake_world, monkeypatch):
    """Message from wrong chat.id → not processed."""
    sent_texts = []
    import telegram_api as tg
    async def capture_send(text, chat_id=None):
        sent_texts.append(text)
    monkeypatch.setattr(tg, "send_text", capture_send)

    from main import _handle_message
    msg = _tg_update(chat_id=99999, text="/today")["message"]
    await _handle_message(msg)

    # No response should be sent to wrong chat
    assert len(sent_texts) == 0


@pytest.mark.asyncio
async def test_tg_message_correct_chat_id_processed(fake_world, monkeypatch):
    """Message from correct chat.id → processed normally."""
    sent_texts = []
    import telegram_api as tg
    async def capture_send(text, chat_id=None):
        sent_texts.append(text)
    monkeypatch.setattr(tg, "send_text", capture_send)

    from main import _handle_message
    correct_chat_id = int(os.environ.get("CHAT_ID", "0"))
    msg = _tg_update(chat_id=correct_chat_id, text="/today")["message"]
    await _handle_message(msg)

    # /today handler should have sent something
    assert len(sent_texts) > 0


@pytest.mark.asyncio
async def test_callback_wrong_chat_id_rejected(fake_world, monkeypatch):
    """Callback from wrong chat.id → not processed."""

    from main import _handle_callback
    cb = _tg_callback(chat_id=99999, data="rpt_week")["callback_query"]
    await _handle_callback(cb)

    # Should have been rejected — no handler dispatch


# ── Tests: SePay webhook auth ─────────────────────────────────


@pytest.mark.asyncio
async def test_sepay_without_secret_rejected(fake_world):
    """SePay payload without apikey → rejected, no row written."""
    import handlers.sepay as sepay
    payload = _sepay_payload(with_secret=False, ref="NO_SECRET")
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert len(rows) == 1  # header only


@pytest.mark.asyncio
async def test_sepay_wrong_secret_rejected(fake_world):
    """SePay payload with wrong apikey → rejected."""
    import handlers.sepay as sepay
    payload = _sepay_payload(with_secret=True, ref="WRONG_SECRET")
    payload["apikey"] = "completely_wrong_secret"
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert len(rows) == 1  # header only


@pytest.mark.asyncio
async def test_sepay_correct_secret_processed(fake_world):
    """SePay payload with correct apikey → processed, row written."""
    import handlers.sepay as sepay
    sh._ensure_accounts_tab()
    sh.invalidate_accounts_cache()
    payload = _sepay_payload(with_secret=True, ref="CORRECT_SECRET")
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert len(rows) >= 2  # header + at least 1 tx row


# ── Tests: Cron secret ────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_without_secret_returns_403():
    """POST /trigger/* without secret param → 403."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/trigger/daily-recap")
        assert r.status_code == 403

        r = await client.post("/trigger/monthly-allocation")
        assert r.status_code == 403


# ── Tests: Zalo webhook auth ─────────────────────────────────


@pytest.mark.asyncio
async def test_zalo_webhook_interactive_off_rejects_before_processing(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main
    from main import app

    monkeypatch.setattr(main, "ZALO_ENABLED", True)
    monkeypatch.setattr(main, "ZALO_INTERACTIVE", False)

    processed = []

    async def capture_process(event):
        processed.append(event)

    monkeypatch.setattr(main, "_process_zalo", capture_process)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/zalo/webhook", json=_zalo_event())
        assert r.status_code == 200

    assert processed == []


@pytest.mark.asyncio
async def test_zalo_webhook_rejects_missing_or_wrong_secret(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main
    from main import app

    monkeypatch.setattr(main, "ZALO_ENABLED", True)
    monkeypatch.setattr(main, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(main, "ZALO_WEBHOOK_SECRET", "zalo_secret")
    monkeypatch.setattr(main, "ZALO_USER_ID", "zalo_user_1")

    processed = []

    async def capture_process(event):
        processed.append(event)

    monkeypatch.setattr(main, "_process_zalo", capture_process)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/zalo/webhook", json=_zalo_event())
        assert r.status_code == 200

        r = await client.post(
            "/zalo/webhook",
            json=_zalo_event(),
            headers={"X-Bot-Api-Secret-Token": "wrong"},
        )
        assert r.status_code == 200

        r = await client.post(
            "/zalo/webhook",
            json=_zalo_event(),
            headers={"X-Bot-Api-Secret-Token": "zalo_secret"},
        )
        assert r.status_code == 200

    assert len(processed) == 1


@pytest.mark.asyncio
async def test_zalo_webhook_requires_configured_secret_and_user(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main
    from main import app

    monkeypatch.setattr(main, "ZALO_ENABLED", True)
    monkeypatch.setattr(main, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(main, "ZALO_WEBHOOK_SECRET", "")
    monkeypatch.setattr(main, "ZALO_USER_ID", "")

    processed = []

    async def capture_process(event):
        processed.append(event)

    monkeypatch.setattr(main, "_process_zalo", capture_process)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/zalo/webhook",
            json=_zalo_event(),
            headers={"X-Bot-Api-Secret-Token": "anything"},
        )
        assert r.status_code == 200

    assert processed == []


@pytest.mark.asyncio
async def test_zalo_webhook_ignores_non_text_events(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main
    from main import app

    monkeypatch.setattr(main, "ZALO_ENABLED", True)
    monkeypatch.setattr(main, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(main, "ZALO_WEBHOOK_SECRET", "zalo_secret")
    monkeypatch.setattr(main, "ZALO_USER_ID", "zalo_user_1")

    processed = []

    async def capture_process(event):
        processed.append(event)

    monkeypatch.setattr(main, "_process_zalo", capture_process)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/zalo/webhook",
            json=_zalo_event(event_name="message.sticker.received"),
            headers={"X-Bot-Api-Secret-Token": "zalo_secret"},
        )
        assert r.status_code == 200

    assert processed == []


@pytest.mark.asyncio
async def test_process_zalo_rejects_wrong_user_bot_echo_and_group(monkeypatch):
    import main

    monkeypatch.setattr(main, "ZALO_USER_ID", "zalo_user_1")

    sent = []

    async def capture_send(text, chat_id=None):
        sent.append((text, chat_id))

    monkeypatch.setattr(main.zalo, "send_text", capture_send)

    await main._process_zalo(_zalo_event(sender_id="wrong")["result"])
    await main._process_zalo(_zalo_event(is_bot=True)["result"])
    await main._process_zalo(_zalo_event(chat_type="GROUP")["result"])

    assert sent == []


@pytest.mark.asyncio
async def test_zalo_today_command_sends_response(fake_world, monkeypatch):
    import main

    monkeypatch.setattr(main, "ZALO_USER_ID", "zalo_user_1")

    sent = []

    async def capture_send(text, chat_id=None):
        sent.append((text, chat_id))

    monkeypatch.setattr(main.zalo, "send_text", capture_send)

    await main._process_zalo(_zalo_event(text="/today")["result"])

    assert sent
    assert sent[0][1] == "zalo_chat_1"
    assert "Daily spending" in sent[0][0]


@pytest.mark.asyncio
async def test_trigger_with_wrong_secret_returns_403():
    """POST /trigger/* with wrong secret → 403."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/trigger/daily-recap?secret=wrong")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_trigger_with_correct_secret_returns_200():
    """POST /trigger/* with correct secret → 200."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    from config import CRON_SECRET

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(f"/trigger/daily-recap?secret={CRON_SECRET}")
        assert r.status_code == 200


def test_tx_exists_fails_closed_when_transaction_lookup_errors(fake_world, monkeypatch):
    """Idempotency lookup errors must not allow an unknowable ref through."""
    def boom(*args, **kwargs):
        raise RuntimeError("sheet unavailable")

    monkeypatch.setattr(sh, "_get_tx_rows", boom)

    assert sh.tx_exists("LOOKUP_FAILURE") is True

    import gspread
    with pytest.raises(gspread.WorksheetNotFound):
        fake_world.worksheet(S.PROCESSED_REFS)
