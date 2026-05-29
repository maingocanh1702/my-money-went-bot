"""Zalo webhook parser and signature unit tests."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from core.handlers.zalo_webhook import (
    loads_body,
    parse_zalo_text_event,
    verify_zalo_signature,
)


def test_parse_user_send_text_event() -> None:
    event = parse_zalo_text_event(
        {
            "event_name": "user_send_text",
            "sender": {"id": "zalo-user"},
            "message": {"text": "  /start  "},
        }
    )

    assert event is not None
    assert event.sender_id == "zalo-user"
    assert event.text == "/start"


def test_parse_ignores_unknown_or_incomplete_events() -> None:
    assert parse_zalo_text_event({"event_name": "oa_follow"}) is None
    assert parse_zalo_text_event({"event_name": "user_send_text"}) is None


def test_loads_body_returns_none_for_invalid_json() -> None:
    assert loads_body(b"{") is None
    assert loads_body(b"[]") is None


def test_signature_verifies_hmac_when_secret_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZALO_OA_SECRET_KEY", "secret")  # pragma: allowlist secret
    raw = b'{"event_name":"user_send_text"}'
    digest = hmac.new(b"secret", raw, hashlib.sha256).hexdigest()  # pragma: allowlist secret

    assert verify_zalo_signature(raw, {"x-zevent-signature": f"sha256={digest}"})
    assert not verify_zalo_signature(raw, {"x-zevent-signature": "bad"})


def test_signature_rejects_prod_without_secret_unless_explicitly_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZALO_OA_SECRET_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("ZALO_ALLOW_UNVERIFIED_WEBHOOK", raising=False)

    assert not verify_zalo_signature(b"{}", {})

    monkeypatch.setenv("ZALO_ALLOW_UNVERIFIED_WEBHOOK", "true")
    assert verify_zalo_signature(b"{}", {})
