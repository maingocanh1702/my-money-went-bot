"""Fail-closed authentication and durable retry checks for public inbound paths."""
import pytest


@pytest.mark.asyncio
async def test_email_webhook_requires_the_configured_secret(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main

    monkeypatch.setattr(main, "EMAIL_SECRET", "email-secret")
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/webhook/email", json={"secret": "wrong"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sepay_webhook_rejects_invalid_secret_before_processing(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main

    monkeypatch.setattr(main, "has_valid_sepay_secret", lambda *_args, **_kwargs: False)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/webhook", json={"transferAmount": 100_000})
    assert response.status_code == 401


def test_sepay_secret_checker_rejects_wrong_or_malformed_payloads(monkeypatch):
    from handlers import sepay

    monkeypatch.setattr(sepay, "SEPAY_SECRET", "sepay-secret")
    assert sepay.has_valid_sepay_secret({"apikey": "sepay-secret"})
    assert not sepay.has_valid_sepay_secret({"apikey": "wrong"})
    assert not sepay.has_valid_sepay_secret({"data": "not an object"})


@pytest.mark.asyncio
async def test_public_webhook_requires_a_json_object():
    from httpx import ASGITransport, AsyncClient
    import main

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/webhook", json=["not", "an", "event"])
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sepay_webhook_returns_retryable_status_when_financial_write_fails(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main

    async def fail_write(_payload):
        raise RuntimeError("sheet unavailable")

    monkeypatch.setattr(main, "has_valid_sepay_secret", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(main, "handle_sepay_webhook", fail_write)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/webhook", json={"transferAmount": 100_000})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_authenticated_email_uses_the_trusted_email_path(monkeypatch):
    import main

    received = []

    async def capture(parsed):
        received.append(parsed)

    monkeypatch.setattr(main, "handle_trusted_email_transaction", capture)
    monkeypatch.setattr(main, "parse_email", lambda **_kwargs: {"_source": "email_cake"})
    assert await main._process_email({"from": "bank@example.test", "subject": "tx", "body": "body"}) is True
    assert received == [{"_source": "email_cake"}]


@pytest.mark.asyncio
async def test_supported_non_transaction_email_is_acknowledged_without_blocking_backlog():
    import main

    assert await main._process_email({
        "from": "Cake by VPBank <no-reply@cake.vn>",
        "subject": "Sao ke thang 6 cua ban da san sang",
        "body": "Xem sao ke thang 6 trong ung dung Cake.",
        "date": "2026-06-30T12:00:00+07:00",
    }) is True


@pytest.mark.asyncio
async def test_transaction_shaped_email_with_unknown_format_remains_retryable():
    import main

    assert await main._process_email({
        "from": "no-reply@cake.vn",
        "subject": "Thông báo biến động số dư",
        "body": "Nội dung mới, nhưng không đọc được số tiền.",
        "date": "2026-06-30T12:00:00+07:00",
    }) is False


@pytest.mark.asyncio
async def test_zalo_inline_callback_never_routes_to_telegram_handlers(monkeypatch):
    import main

    routed = []

    async def should_not_run(*_args):
        routed.append(True)

    monkeypatch.setattr(main, "handle_parent_selected", should_not_run)
    await main._handle_zalo_callback({
        "id": "zalo-callback", "data": "p_5_food",
        "message": {"chat": {"id": "zalo-user"}, "message_id": "42"},
    })
    assert routed == []
