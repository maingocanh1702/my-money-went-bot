"""Phase 3 (C1) — Webhook dispatch telemetry.

Asserts both legacy and v2 SePay paths emit a structured log event with
field `path` set to `"legacy"` or `"v2"` respectively. Lets ops dashboards
count traffic split during the Phase 4 cutover.

Implementation note: we intercept `main._dispatch_log` directly rather
than rely on `structlog.testing.capture_logs()`. The module-level logger
is cached by `configure_logging(cache_logger_on_first_use=True)` so
capture_logs's processor-injection doesn't reliably retrofit the cached
proxy. Patching `_dispatch_log.info` is the most direct contract check.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _install_log_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace `main._dispatch_log` with a MagicMock; return it for asserts."""
    import main as main_module

    spy = MagicMock()
    monkeypatch.setattr(main_module, "_dispatch_log", spy)
    return spy


def _assert_dispatch(spy: MagicMock, *, path: str) -> None:
    """Assert exactly one sepay.dispatch event was logged with given path."""
    matches = [
        call
        for call in spy.info.call_args_list
        if call.args and call.args[0] == "sepay.dispatch" and call.kwargs.get("path") == path
    ]
    assert len(matches) == 1, (
        f"expected 1 sepay.dispatch path={path!r}, got {len(matches)} "
        f"(all info calls: {spy.info.call_args_list})"
    )


async def test_v2_route_logs_dispatch_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The new /webhooks/sepay/{token} handler emits sepay.dispatch path=v2."""
    spy = _install_log_spy(monkeypatch)
    import main as main_module

    monkeypatch.setattr(main_module, "handle_sepay_v2", AsyncMock(return_value={"ok": True}))

    await main_module.webhook_sepay_v2(
        token="test-tok",
        request=_FakeRequest(body={"id": 1, "transferType": "in"}),  # type: ignore[arg-type]
    )

    _assert_dispatch(spy, path="v2")


async def test_legacy_dispatch_logs_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """_process() dispatches non-Telegram body to legacy handler and logs path=legacy."""
    spy = _install_log_spy(monkeypatch)
    import main as main_module

    monkeypatch.setattr(main_module, "handle_sepay_webhook", AsyncMock(return_value=None))

    await main_module._process({"transferType": "in", "transferAmount": 1})

    _assert_dispatch(spy, path="legacy")


async def test_telegram_update_does_not_log_sepay_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Telegram update (`update_id` present) must not trigger sepay.dispatch."""
    spy = _install_log_spy(monkeypatch)
    import main as main_module

    monkeypatch.setattr(main_module, "_handle_message", AsyncMock(return_value=None))

    await main_module._process({"update_id": 42, "message": {"from": {"id": 1}, "text": "/start"}})

    dispatch_calls = [
        call for call in spy.info.call_args_list if call.args and call.args[0] == "sepay.dispatch"
    ]
    assert dispatch_calls == [], f"unexpected sepay.dispatch on Telegram update: {dispatch_calls}"


class _FakeRequest:
    """Minimal stand-in for fastapi.Request.json() — avoids spinning ASGI."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    async def json(self) -> dict[str, Any]:
        return self._body
