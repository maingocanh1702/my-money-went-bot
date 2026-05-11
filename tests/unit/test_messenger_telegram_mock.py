"""TelegramSender unit tests — httpx mocked, no DB, no network."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.messenger import Button, Markup, SendPayload
from core.messenger.telegram import TelegramSender


def _ok_response(payload: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock httpx.Response that mimics Telegram's success shape."""
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=payload or {"ok": True, "result": {}})
    return resp


@pytest.fixture
def chat_id_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub `_resolve_chat_id` so we don't need a DB pool for unit tests."""

    async def _fake(_self: Any, user_id: int) -> int:
        return 1_000 + user_id

    monkeypatch.setattr("core.messenger.telegram.TelegramSender._resolve_chat_id", _fake)


@pytest.mark.usefixtures("chat_id_resolver")
async def test_send_calls_telegram_api_with_text_key_and_locale() -> None:
    """text_key resolves through i18n; chat_id pulled via _resolve_chat_id."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    sender = TelegramSender(bot_token="TEST_TOKEN", http_client=client)

    payload: SendPayload = {
        "text_key": "greeting",
        "text_params": {"name": "Alice"},
        "locale": "vi",
    }
    await sender.send_validated(user_id=42, payload=payload)

    assert client.post.await_count == 1
    call_args = client.post.await_args
    assert call_args is not None
    url = call_args.args[0]
    body = call_args.kwargs["json"]
    assert url.endswith("/botTEST_TOKEN/sendMessage")
    assert body["chat_id"] == 1042
    assert body["text"] == "Xin chào, Alice!"
    # No parse_mode default
    assert "parse_mode" not in body


@pytest.mark.usefixtures("chat_id_resolver")
async def test_send_renders_abstract_markup_to_inline_keyboard() -> None:
    """Markup.rows → {inline_keyboard: [[{text, callback_data|url}]]}."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    sender = TelegramSender(bot_token="TEST_TOKEN", http_client=client)

    markup = Markup(
        rows=[
            [
                Button(label_key="btn_confirm", callback_data="confirm:1"),
                Button(label_key="btn_cancel", callback_data="cancel:1"),
            ],
            [Button(label="Help", url="https://example.com/help")],
        ]
    )
    payload: SendPayload = {
        "text_key": "tx_recorded",
        "text_params": {"amount": "50,000"},
        "locale": "en",
        "markup": markup,
    }
    await sender.send_validated(user_id=7, payload=payload)

    call_args = client.post.await_args
    assert call_args is not None
    body = call_args.kwargs["json"]
    kbd = body["reply_markup"]["inline_keyboard"]
    assert len(kbd) == 2
    assert kbd[0][0] == {"text": "✅ Confirm", "callback_data": "confirm:1"}
    assert kbd[0][1] == {"text": "❌ Cancel", "callback_data": "cancel:1"}
    assert kbd[1][0] == {"text": "Help", "url": "https://example.com/help"}
    assert body["text"] == "Transaction recorded: 50,000."


@pytest.mark.usefixtures("chat_id_resolver")
async def test_send_maps_parse_mode_markdown_to_markdownv2() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    sender = TelegramSender(bot_token="TEST_TOKEN", http_client=client)

    await sender.send_validated(
        user_id=1,
        payload={"text": "*bold*", "parse_mode": "markdown"},
    )
    call_args = client.post.await_args
    assert call_args is not None
    body = call_args.kwargs["json"]
    assert body["parse_mode"] == "MarkdownV2"


@pytest.mark.usefixtures("chat_id_resolver")
async def test_send_raises_when_telegram_returns_ok_false() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response({"ok": False, "description": "Bad request"}))
    sender = TelegramSender(bot_token="TEST_TOKEN", http_client=client)
    with pytest.raises(RuntimeError, match="Telegram API rejected"):
        await sender.send_validated(user_id=1, payload={"text": "hi"})


@pytest.mark.usefixtures("chat_id_resolver")
async def test_send_raises_when_payload_invalid() -> None:
    """send_validated runs SendPayload validation before any API call."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    sender = TelegramSender(bot_token="TEST_TOKEN", http_client=client)
    with pytest.raises(ValueError, match="exactly one of text_key or text"):
        await sender.send_validated(user_id=1, payload={})
    client.post.assert_not_awaited()


def test_init_rejects_empty_token() -> None:
    with pytest.raises(ValueError, match="bot_token must be non-empty"):
        TelegramSender(bot_token="")
