"""Sentry init + before_send tenant-tagging.

We don't hit Sentry's network — we drive `_sentry_before_send` directly
and assert it adds `user_id` + `request_id` tags + `user.id`.
"""

from __future__ import annotations

from core import tenant_context
from core.observability import _sentry_before_send, init_sentry


def setup_function() -> None:
    tenant_context.clear_tenant()


def teardown_function() -> None:
    tenant_context.clear_tenant()


def test_before_send_adds_user_id_tag_and_user_id_field() -> None:
    tenant_context.set_tenant(42, request_id="rid-X")
    event: dict[str, object] = {"exception": {"values": []}}
    out = _sentry_before_send(event, {})
    assert out is not None
    assert out["tags"]["user_id"] == 42
    assert out["tags"]["request_id"] == "rid-X"
    assert out["user"]["id"] == 42


def test_before_send_no_tenant_leaves_event_alone() -> None:
    event: dict[str, object] = {"exception": {"values": []}}
    out = _sentry_before_send(event, {})
    assert out is not None
    assert "tags" not in out  # nothing added
    assert "user" not in out


def test_init_sentry_returns_false_when_no_dsn(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No DSN → no-op. Lets local dev run without a Sentry project."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry(dsn=None) is False
    assert init_sentry(dsn="") is False


def test_init_sentry_returns_true_with_dsn() -> None:
    """A DSN-shaped string activates the SDK — we don't verify network."""
    # NB: pseudo DSN — sentry_sdk doesn't validate at init, just stores it.
    ok = init_sentry(
        dsn="https://public@o0.ingest.sentry.io/0",
        environment="test",
        traces_sample_rate=0.0,
    )
    assert ok is True
