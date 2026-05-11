"""i18n stub — translation lookup + fallback semantics."""

from __future__ import annotations

from core.messenger import i18n


def setup_function() -> None:
    i18n.reset_cache()


def test_t_returns_vi_translation_with_params() -> None:
    assert i18n.t("greeting", "vi", name="Mai") == "Xin chào, Mai!"


def test_t_returns_en_translation() -> None:
    assert i18n.t("greeting", "en", name="Alice") == "Hello, Alice!"


def test_t_unknown_locale_falls_back_to_vi() -> None:
    # 'fr' is not bundled — falls through to vi (default market).
    assert i18n.t("greeting", "fr", name="Léo") == "Xin chào, Léo!"


def test_t_unknown_key_returns_loud_marker() -> None:
    result = i18n.t("definitely_not_a_real_key", "vi")
    assert result == "??definitely_not_a_real_key??"


def test_t_no_params_returns_template_unchanged() -> None:
    # Template has no placeholders → format() with empty kwargs is a no-op.
    assert i18n.t("btn_confirm", "vi") == "✅ Xác nhận"
    assert i18n.t("btn_confirm", "en") == "✅ Confirm"
