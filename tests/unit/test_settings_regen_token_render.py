"""Regression test for Codex R1 P2 (2026-05-13): the regenerated webhook
token must not be sent with ``parse_mode='markdown'``.

``secrets.token_urlsafe(24)`` produces URL-safe base64 over alphabet
``[A-Za-z0-9_-]``. Telegram's classic Markdown parser mangles ``_`` even
inside backticks, which would corrupt copy/paste of the raw token.

The minimum-viable fix is in ``handlers/settings._handle_regen``: the
regen-success send now uses ``parse_mode='plain'``. This test guards that
no future change re-introduces markdown rendering on this code path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.settings_svc import SettingsOverview
from handlers import settings as settings_handler


@pytest.mark.asyncio
async def test_regen_success_message_never_uses_markdown_parse_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_handle_regen`` must NOT pass ``parse_mode='markdown'`` on any send."""
    sent: list[dict[str, Any]] = []

    async def fake_send(user_id: int, payload: Any) -> None:
        sent.append(dict(payload))

    async def fake_mint_token(user_id: int, *, kind: str) -> str:
        # Realistic token shape: secrets.token_urlsafe() emits `_` / `-`.
        return "abc_def-ghi_jkl-mno"

    async def fake_emit_analytics(*args: Any, **kwargs: Any) -> None:
        return None

    async def fake_get_overview(user_id: int) -> SettingsOverview:
        return SettingsOverview(
            user_id=user_id,
            locale="vi",
            timezone="Asia/Ho_Chi_Minh",
            inbound_email="u1@in.mymoneywent.com",
            daily_recap_enabled=True,
            plan="free",
            plan_status="free",
            trial_days_left=None,
            webhook_created_at=datetime.now(tz=UTC),
            webhook_display_suffix="…mno",
        )

    monkeypatch.setattr("handlers.settings.messenger.send", fake_send)
    monkeypatch.setattr("handlers.settings.mint_token", fake_mint_token)
    monkeypatch.setattr("handlers.settings.settings_svc.emit_analytics", fake_emit_analytics)
    monkeypatch.setattr("handlers.settings.settings_svc.get_overview", fake_get_overview)

    await settings_handler._handle_regen(user_id=42, locale="vi")

    assert sent, "expected at least one send call from _handle_regen"
    regen_payloads = [p for p in sent if p.get("text_key") == "settings.regen_success"]
    assert len(regen_payloads) == 1, f"expected exactly one regen_success send, got {sent!r}"
    assert regen_payloads[0].get("parse_mode") != "markdown", (
        f"regen success message must not use markdown parse_mode "
        f"(token chars `_` / `-` get mangled): {regen_payloads[0]!r}"
    )


@pytest.mark.parametrize("locale", ["vi", "en"])
def test_regen_success_template_has_no_literal_backticks(locale: str) -> None:
    """Codex R1 P1 (2026-05-13): i18n template wrapped {token} in literal
    backticks. With parse_mode='plain' (set in handlers/settings.py), those
    backticks render literally in the Telegram UI, corrupting one-tap copy
    of the raw token. Guard both locales.
    """
    from i18n import t

    rendered = t(locale, "settings.regen_success", token="abc_def-ghi_jkl-mno")
    assert "`" not in rendered, (
        f"settings.regen_success ({locale}) contains literal backtick(s) "
        f"that would render in plain mode: {rendered!r}"
    )
    assert (
        "abc_def-ghi_jkl-mno" in rendered
    ), f"token substitution missing from rendered template: {rendered!r}"
