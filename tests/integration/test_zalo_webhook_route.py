"""FastAPI route tests for `/zalo/webhook`."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from core.handlers.zalo_webhook import ZaloTextEvent


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    import main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_zalo_webhook_disabled_acknowledges_without_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZALO_ENABLED", raising=False)
    monkeypatch.delenv("ZALO_INTERACTIVE", raising=False)

    with _client(monkeypatch) as client:
        response = client.post("/zalo/webhook", json={"event_name": "user_send_text"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_zalo_webhook_rejects_invalid_signature_when_secret_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZALO_ENABLED", "true")
    monkeypatch.setenv("ZALO_OA_SECRET_KEY", "secret")  # pragma: allowlist secret

    with _client(monkeypatch) as client:
        response = client.post(
            "/zalo/webhook",
            json={
                "event_name": "user_send_text",
                "sender": {"id": "zalo-user"},
                "message": {"text": "/start"},
            },
            headers={"x-zevent-signature": "bad"},
        )

    assert response.status_code == 401
    assert response.json() == {"ok": False}


def test_zalo_webhook_schedules_user_text_event(monkeypatch: pytest.MonkeyPatch) -> None:
    handled: list[ZaloTextEvent] = []

    async def _fake_handler(event: ZaloTextEvent) -> None:
        handled.append(event)

    monkeypatch.setenv("ZALO_ENABLED", "true")
    monkeypatch.delenv("ZALO_OA_SECRET_KEY", raising=False)
    monkeypatch.setattr("core.handlers.zalo_webhook.handle_zalo_text_event", _fake_handler)

    with _client(monkeypatch) as client:
        response = client.post(
            "/zalo/webhook",
            json={
                "event_name": "user_send_text",
                "sender": {"id": "zalo-user"},
                "message": {"text": "/start"},
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(handled) == 1
    assert handled[0].sender_id == "zalo-user"
    assert handled[0].text == "/start"
