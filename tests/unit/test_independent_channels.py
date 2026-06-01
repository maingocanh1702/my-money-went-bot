"""tests/unit/test_independent_channels.py

TDD for independent channel config (Phase 1).
Suite MUST fail on unmodified code — it drives the implementation.
"""
import asyncio
import pytest


# ── Helpers ───────────────────────────────────────────────────


def _tg_kwargs(**overrides) -> dict:
    """Full Telegram-only config kwargs."""
    base = dict(
        telegram_enabled=True,
        bot_token="123:abc",
        chat_id="456",
        tg_secret="tg_secret",
        zalo_enabled=False,
        zalo_token="",
        zalo_chat="",
        zalo_interactive=False,
        zalo_secret="",
        zalo_user="",
        sepay_secret="sepay",
        cron_secret="cron",
    )
    base.update(overrides)
    return base


def _zalo_kwargs(**overrides) -> dict:
    """Full Zalo-only config kwargs (non-interactive)."""
    base = dict(
        telegram_enabled=False,
        bot_token="",
        chat_id="",
        tg_secret="",
        zalo_enabled=True,
        zalo_token="zalo_tok",
        zalo_chat="zalo_chat",
        zalo_interactive=False,
        zalo_secret="",
        zalo_user="",
        sepay_secret="sepay",
        cron_secret="cron",
    )
    base.update(overrides)
    return base


# ── Tests: config._missing_channel_vars ───────────────────────


def test_telegram_only_fully_configured_returns_empty():
    from config import _missing_channel_vars
    assert _missing_channel_vars(**_tg_kwargs()) == []


def test_zalo_only_non_interactive_fully_configured_returns_empty():
    from config import _missing_channel_vars
    assert _missing_channel_vars(**_zalo_kwargs()) == []


def test_both_channels_configured_returns_empty():
    from config import _missing_channel_vars
    missing = _missing_channel_vars(
        telegram_enabled=True,
        bot_token="123:abc",
        chat_id="456",
        tg_secret="tg_secret",
        zalo_enabled=True,
        zalo_token="zalo_tok",
        zalo_chat="zalo_chat",
        zalo_interactive=False,
        zalo_secret="",
        zalo_user="",
        sepay_secret="sepay",
        cron_secret="cron",
    )
    assert missing == []


def test_neither_channel_configured_returns_error():
    from config import _missing_channel_vars
    missing = _missing_channel_vars(
        telegram_enabled=False,
        bot_token="",
        chat_id="",
        tg_secret="",
        zalo_enabled=False,
        zalo_token="",
        zalo_chat="",
        zalo_interactive=False,
        zalo_secret="",
        zalo_user="",
        sepay_secret="sepay",
        cron_secret="cron",
    )
    assert any("at least one channel" in m for m in missing)


def test_zalo_interactive_missing_secret_and_user():
    from config import _missing_channel_vars
    missing = _missing_channel_vars(**_zalo_kwargs(
        zalo_interactive=True,
        zalo_secret="",
        zalo_user="",
    ))
    assert "ZALO_WEBHOOK_SECRET" in missing
    assert "ZALO_USER_ID" in missing


def test_zalo_interactive_fully_configured_returns_empty():
    from config import _missing_channel_vars
    assert _missing_channel_vars(**_zalo_kwargs(
        zalo_interactive=True,
        zalo_secret="zs",
        zalo_user="zu",
    )) == []


def test_missing_sepay_secret_flagged():
    from config import _missing_channel_vars
    assert "SEPAY_SECRET" in _missing_channel_vars(**_tg_kwargs(sepay_secret=""))


def test_missing_cron_secret_flagged():
    from config import _missing_channel_vars
    assert "CRON_SECRET" in _missing_channel_vars(**_tg_kwargs(cron_secret=""))


def test_telegram_missing_tg_secret_flagged():
    """Telegram channel requires TELEGRAM_WEBHOOK_SECRET when it's the only channel."""
    from config import _missing_channel_vars
    missing = _missing_channel_vars(**_tg_kwargs(tg_secret=""))
    assert "TELEGRAM_WEBHOOK_SECRET" in missing


# ── Tests: TELEGRAM_ENABLED flag ──────────────────────────────


def test_telegram_enabled_flag_exists():
    from config import TELEGRAM_ENABLED  # ImportError on unmodified code → FAIL
    assert isinstance(TELEGRAM_ENABLED, bool)


def test_telegram_enabled_is_true_in_test_env():
    """conftest sets BOT_TOKEN=test:dummy, CHAT_ID=0 — both non-empty → enabled."""
    from config import TELEGRAM_ENABLED
    assert TELEGRAM_ENABLED is True


# ── Tests: telegram_api no-op when BOT_TOKEN empty ───────────


@pytest.mark.asyncio
async def test_send_text_noop_when_bot_token_empty(monkeypatch):
    import telegram_api as tg

    called = []

    async def _mock_post(*a, **kw):
        called.append(a)

    monkeypatch.setattr(tg, "BOT_TOKEN", "")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    result = await tg.send_text("hello")
    assert result is None
    assert called == []


@pytest.mark.asyncio
async def test_send_with_buttons_noop_when_bot_token_empty(monkeypatch):
    import telegram_api as tg

    called = []

    async def _mock_post(*a, **kw):
        called.append(a)

    monkeypatch.setattr(tg, "BOT_TOKEN", "")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    result = await tg.send_with_buttons("hello", [[]])
    assert result is None
    assert called == []


@pytest.mark.asyncio
async def test_edit_message_noop_when_bot_token_empty(monkeypatch):
    import telegram_api as tg

    called = []

    async def _mock_post(*a, **kw):
        called.append(a)

    monkeypatch.setattr(tg, "BOT_TOKEN", "")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    result = await tg.edit_message(1, "hello")
    assert result is None
    assert called == []


@pytest.mark.asyncio
async def test_delete_message_noop_when_bot_token_empty(monkeypatch):
    import telegram_api as tg

    called = []

    async def _mock_post(*a, **kw):
        called.append(a)

    monkeypatch.setattr(tg, "BOT_TOKEN", "")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    await tg.delete_message(1)
    assert called == []


@pytest.mark.asyncio
async def test_answer_callback_noop_when_bot_token_empty(monkeypatch):
    import telegram_api as tg

    called = []

    async def _mock_post(*a, **kw):
        called.append(a)

    monkeypatch.setattr(tg, "BOT_TOKEN", "")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    await tg.answer_callback("cb_id")
    assert called == []


@pytest.mark.asyncio
async def test_set_my_commands_noop_when_bot_token_empty(monkeypatch):
    import telegram_api as tg

    called = []

    async def _mock_post(*a, **kw):
        called.append(a)

    monkeypatch.setattr(tg, "BOT_TOKEN", "")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    await tg.set_my_commands()
    assert called == []


@pytest.mark.asyncio
async def test_telegram_send_still_works_when_token_set(monkeypatch):
    """Regression: with BOT_TOKEN set, send_text must call httpx."""
    import telegram_api as tg

    called = []

    class _Resp:
        def json(self):
            return {"ok": True}

    async def _mock_post(*a, **kw):
        called.append(a)
        return _Resp()

    monkeypatch.setattr(tg, "BOT_TOKEN", "test:dummy")
    monkeypatch.setattr(tg._client, "post", _mock_post)

    await tg.send_text("hello")
    assert len(called) > 0


# ── Tests: notifier routing ────────────────────────────────────


@pytest.mark.asyncio
async def test_notifier_telegram_disabled_skips_tg_send(monkeypatch):
    """TELEGRAM_ENABLED=False → tg.send_text MUST NOT be called."""
    import config
    import telegram_api as tg
    import zalo_api as zalo_mod
    import notifier

    tg_called = []
    zalo_called = []

    async def _mock_tg(text, chat_id=None):
        tg_called.append(text)

    async def _mock_zalo(text, chat_id=None):
        zalo_called.append(text)

    monkeypatch.setattr(tg, "send_text", _mock_tg)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo)
    monkeypatch.setattr(config, "TELEGRAM_ENABLED", False)
    monkeypatch.setattr(config, "ZALO_ENABLED", True)

    await notifier.send_text("test notification")
    await asyncio.sleep(0)  # let background task run

    assert tg_called == [], "Telegram must not be called when TELEGRAM_ENABLED=False"
    assert len(zalo_called) > 0, "Zalo must still be called"


@pytest.mark.asyncio
async def test_notifier_zalo_disabled_skips_zalo_send(monkeypatch):
    """ZALO_ENABLED=False → zalo.send_text MUST NOT be called."""
    import config
    import telegram_api as tg
    import zalo_api as zalo_mod
    import notifier

    tg_called = []
    zalo_called = []

    async def _mock_tg(text, chat_id=None):
        tg_called.append(text)

    async def _mock_zalo(text, chat_id=None):
        zalo_called.append(text)

    monkeypatch.setattr(tg, "send_text", _mock_tg)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo)
    monkeypatch.setattr(config, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_ENABLED", False)

    await notifier.send_text("test notification")
    await asyncio.sleep(0)

    assert len(tg_called) > 0, "Telegram must be called when enabled"
    assert zalo_called == [], "Zalo must not be called when ZALO_ENABLED=False"
