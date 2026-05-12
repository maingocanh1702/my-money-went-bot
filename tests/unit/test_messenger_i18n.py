"""Legacy `core.messenger.i18n` compat shim — key-first signature.

The actual i18n module lives at top-level `i18n/`. This test pins the
compat shim's behaviour so older call sites don't silently break when
the underlying pack changes.
"""

from __future__ import annotations

from core.messenger import i18n


def test_compat_t_returns_vi_translation_with_params() -> None:
    assert (
        i18n.t("onboard.welcome", "vi", name="Mai")
        == "Xin chào Mai! 👋 Mình là bot quản lý chi tiêu cá nhân."
    )


def test_compat_t_returns_en_translation() -> None:
    assert (
        i18n.t("onboard.welcome", "en", name="Alice")
        == "Hi Alice! 👋 I'm your personal finance bot."
    )


def test_compat_t_unknown_locale_falls_back_to_vi() -> None:
    # 'fr' not bundled → fall through to vi (default).
    assert i18n.t("onboard.welcome", "fr", name="Léo").startswith("Xin chào Léo!")


def test_compat_t_unknown_key_returns_loud_marker() -> None:
    assert i18n.t("definitely_not_a_real_key", "vi") == "??definitely_not_a_real_key??"


def test_compat_t_no_params_returns_template_unchanged() -> None:
    assert i18n.t("btn.confirm", "vi") == "✅ Xác nhận"
    assert i18n.t("btn.confirm", "en") == "✅ Confirm"
