"""Adapter-agnostic contract tests.

Parametrise over every `BaseSender` concrete class. Today: TelegramSender.
Wave 6: DiscordSender, MessengerSender.

The contract under test:
  - Adapter exposes a non-empty `channel_type` class attr.
  - Adapter's factory is registered in the global registry under that name.
  - `send_validated()` raises ValueError for invalid payloads (both
    text+text_key set, neither set, bad parse_mode).
  - `send_validated()` accepts a minimal valid payload (mock transport).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.messenger import BaseSender, SendPayload, senders_for
from core.messenger.telegram import TelegramSender

# (channel_type, factory-that-builds-an-instance-with-mocked-transport)
ADAPTERS: list[tuple[str, type[BaseSender]]] = [
    ("telegram", TelegramSender),
]


def _build(adapter_cls: type[BaseSender]) -> BaseSender:
    """Build an adapter with all I/O mocked.

    Today only TelegramSender exists. When we add Discord/Messenger in
    W6 we'll branch here so each gets the right mock transport.
    """
    client = MagicMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value={"ok": True})
    client.post = AsyncMock(return_value=resp)
    return adapter_cls(bot_token="TEST", http_client=client)  # type: ignore[call-arg]


@pytest.fixture
def mock_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub DB-dependent chat-id resolution for all adapters under test."""

    async def _fake(_self: Any, user_id: int) -> int:
        return 1000 + user_id

    monkeypatch.setattr("core.messenger.telegram.TelegramSender._resolve_chat_id", _fake)


@pytest.mark.parametrize("channel_type,adapter_cls", ADAPTERS)
def test_channel_type_attr_is_set(channel_type: str, adapter_cls: type[BaseSender]) -> None:
    assert adapter_cls.channel_type == channel_type


@pytest.mark.parametrize("channel_type,_adapter_cls", ADAPTERS)
def test_factory_is_registered(channel_type: str, _adapter_cls: type[BaseSender]) -> None:
    # senders_for() raises KeyError if missing.
    factory = senders_for(channel_type)
    assert callable(factory)


@pytest.mark.parametrize("_channel_type,adapter_cls", ADAPTERS)
@pytest.mark.usefixtures("mock_chat_id")
async def test_minimal_valid_payload_succeeds(
    _channel_type: str, adapter_cls: type[BaseSender]
) -> None:
    sender = _build(adapter_cls)
    await sender.send_validated(user_id=1, payload={"text": "hello"})


@pytest.mark.parametrize("_channel_type,adapter_cls", ADAPTERS)
@pytest.mark.usefixtures("mock_chat_id")
async def test_invalid_payload_text_and_key_both_set_raises(
    _channel_type: str, adapter_cls: type[BaseSender]
) -> None:
    sender = _build(adapter_cls)
    payload: SendPayload = {"text": "hi", "text_key": "greeting"}
    with pytest.raises(ValueError):
        await sender.send_validated(user_id=1, payload=payload)


@pytest.mark.parametrize("_channel_type,adapter_cls", ADAPTERS)
@pytest.mark.usefixtures("mock_chat_id")
async def test_invalid_payload_neither_set_raises(
    _channel_type: str, adapter_cls: type[BaseSender]
) -> None:
    sender = _build(adapter_cls)
    with pytest.raises(ValueError):
        await sender.send_validated(user_id=1, payload={})


@pytest.mark.parametrize("_channel_type,adapter_cls", ADAPTERS)
@pytest.mark.usefixtures("mock_chat_id")
async def test_invalid_parse_mode_raises(_channel_type: str, adapter_cls: type[BaseSender]) -> None:
    sender = _build(adapter_cls)
    bad = {"text": "hi", "parse_mode": "xml"}
    with pytest.raises(ValueError):
        await sender.send_validated(user_id=1, payload=bad)  # type: ignore[arg-type]
