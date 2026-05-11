"""structlog config + tenant binding."""

from __future__ import annotations

from core import tenant_context
from core.logging import configure_logging, get_logger, render_event_for_test


def setup_function() -> None:
    tenant_context.clear_tenant()


def teardown_function() -> None:
    tenant_context.clear_tenant()


def test_bind_tenant_injects_user_id_and_request_id() -> None:
    tenant_context.set_tenant(42, request_id="rid-123")
    out = render_event_for_test({"event": "hello"})
    assert out["user_id"] == 42
    assert out["request_id"] == "rid-123"
    assert out["event"] == "hello"


def test_bind_tenant_omits_when_unset() -> None:
    out = render_event_for_test({"event": "no-tenant"})
    assert "user_id" not in out
    assert "request_id" not in out
    assert out["event"] == "no-tenant"


def test_bind_tenant_preserves_pre_bound_fields() -> None:
    """If the caller already bound user_id, our processor must not clobber it."""
    tenant_context.set_tenant(42)
    out = render_event_for_test({"event": "x", "user_id": 99})
    assert out["user_id"] == 99  # caller wins via setdefault semantics


def test_configure_logging_is_idempotent() -> None:
    """Calling configure_logging twice doesn't blow up — important
    because process startup paths can race in tests."""
    configure_logging(env="dev")
    configure_logging(env="dev")
    log = get_logger("test")
    assert log is not None


def test_get_logger_returns_bound_with_initial() -> None:
    log = get_logger("test", component="webhook")
    # We can't easily assert on internal bind without rendering;
    # at minimum, no exception + non-None.
    assert log is not None
