"""ZaloSender unit tests with mocked httpx and no DB."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.messenger import Button, Markup
from core.messenger.zalo import ZaloSender


def _response(status_code: int = 200, payload: dict[str, Any] | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=payload if payload is not None else {"error": 0})
    return resp


@pytest.fixture
def recipient_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(_self: Any, user_id: int) -> str:
        return f"oa-user-{user_id}"

    monkeypatch.setattr("core.messenger.zalo.ZaloSender._resolve_recipient_id", _fake)


@pytest.mark.usefixtures("recipient_resolver")
async def test_send_posts_zalo_customer_service_payload() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_response())
    sender = ZaloSender(access_token="ACCESS", http_client=client)

    await sender.send_validated(42, {"text": "hello"})

    assert client.post.await_count == 1
    call_args = client.post.await_args
    assert call_args is not None
    assert call_args.args[0].endswith("/v3.0/oa/message/cs")
    assert call_args.kwargs["headers"] == {"access_token": "ACCESS"}
    assert call_args.kwargs["json"] == {
        "recipient": {"user_id": "oa-user-42"},
        "message": {"text": "hello"},
    }


@pytest.mark.usefixtures("recipient_resolver")
async def test_send_renders_markup_as_numbered_plain_text() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_response())
    sender = ZaloSender(access_token="ACCESS", http_client=client)

    await sender.send_validated(
        1,
        {
            "text": "Pick one",
            "markup": Markup(
                rows=[
                    [Button(label="Food", callback_data="cat:1:10")],
                    [Button(label="Help", url="https://example.com")],
                ]
            ),
        },
    )

    call_args = client.post.await_args
    assert call_args is not None
    text = call_args.kwargs["json"]["message"]["text"]
    assert text == "Pick one\n\n1. Food\nHelp: https://example.com"


@pytest.mark.usefixtures("recipient_resolver")
async def test_send_refreshes_access_token_once_on_401() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(
        side_effect=[
            _response(401),
            _response(200, {"access_token": "NEW", "refresh_token": "REFRESH2"}),
            _response(200),
        ]
    )
    sender = ZaloSender(
        access_token="OLD",
        refresh_token="REFRESH1",
        app_id="APP",
        secret_key="SECRET",  # pragma: allowlist secret
        http_client=client,
        auto_refresh=True,
    )

    await sender.send_validated(1, {"text": "hello"})

    assert client.post.await_count == 3
    refresh_call = client.post.await_args_list[1]
    assert refresh_call.args[0].endswith("/v4/oa/access_token")
    assert refresh_call.kwargs["headers"] == {"secret_key": "SECRET"}  # pragma: allowlist secret
    retry_call = client.post.await_args_list[2]
    assert retry_call.kwargs["headers"] == {"access_token": "NEW"}


@pytest.mark.usefixtures("recipient_resolver")
async def test_send_chunks_long_text() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_response())
    sender = ZaloSender(access_token="ACCESS", http_client=client, text_limit=5)

    await sender.send_validated(1, {"text": "12345\n67890"})

    assert client.post.await_count == 2
    first = client.post.await_args_list[0].kwargs["json"]["message"]["text"]
    second = client.post.await_args_list[1].kwargs["json"]["message"]["text"]
    assert (first, second) == ("12345", "67890")


@pytest.mark.usefixtures("recipient_resolver")
async def test_send_raises_when_zalo_body_reports_error() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_response(200, {"error": -201, "message": "Invalid user"}))
    sender = ZaloSender(access_token="ACCESS", http_client=client)

    with pytest.raises(RuntimeError, match="Zalo API rejected"):
        await sender.send_validated(1, {"text": "hello"})


def test_init_rejects_empty_access_token() -> None:
    with pytest.raises(ValueError, match="access_token must be non-empty"):
        ZaloSender(access_token="")
