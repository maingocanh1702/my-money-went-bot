"""i18n `t()` helper — translation resolution + fallback semantics.

Test categories covered (per wave0-retrospective §4):
- Happy path: basic vi/en lookups with and without format args.
- Retry / idempotency: N/A — pure function, no side effects (skip with comment).
- Missing optional fields: missing format kwargs returns raw template.
- Pathological inputs: unknown locale, unknown key, both-missing fallback.
- Concurrent access: N/A — module-level dicts are read-only after import (skip).
"""

from __future__ import annotations

import pytest

from i18n import DEFAULT_LOCALE, PACKS, SUPPORTED_LOCALES, t

# ── happy path ───────────────────────────────────────────────────────


def test_t_basic_vi() -> None:
    assert t("vi", "btn.confirm") == "✅ Xác nhận"


def test_t_basic_en() -> None:
    assert t("en", "btn.confirm") == "✅ Confirm"


def test_t_format_args_substituted() -> None:
    out = t("vi", "cat.confirm_tracking", name="Ăn uống", amount="500k")
    assert out == "Đã ghi vào Ăn uống: 500k."


def test_t_format_args_en() -> None:
    out = t("en", "cat.confirm_tracking", name="Food", amount="500k")
    assert out == "Logged to Food: 500k."


# ── missing optional / pathological ─────────────────────────────────


def test_t_missing_format_args_returns_raw_template() -> None:
    # Spec edge case #11 — format KeyError must not crash.
    raw = PACKS["vi"]["cat.confirm_tracking"]
    assert t("vi", "cat.confirm_tracking") == raw


def test_t_unknown_locale_falls_back_to_default() -> None:
    # 'fr' is not in SUPPORTED_LOCALES → falls back to PACKS[DEFAULT_LOCALE].
    assert t("fr", "btn.confirm") == PACKS[DEFAULT_LOCALE]["btn.confirm"]


def test_t_missing_en_key_falls_back_to_vi() -> None:
    # Synthesize a key that only exists in vi to verify cross-pack fallback.
    PACKS["vi"]["__test.vi_only"] = "VI-only"
    try:
        assert t("en", "__test.vi_only") == "VI-only"
    finally:
        PACKS["vi"].pop("__test.vi_only", None)


def test_t_missing_in_both_returns_loud_marker() -> None:
    assert t("vi", "truly.does.not.exist") == "[MISSING: truly.does.not.exist]"
    assert t("en", "truly.does.not.exist") == "[MISSING: truly.does.not.exist]"


def test_t_default_locale_is_vi() -> None:
    assert DEFAULT_LOCALE == "vi"
    assert "vi" in SUPPORTED_LOCALES
    assert "en" in SUPPORTED_LOCALES


# ── pathological format strings ─────────────────────────────────────


@pytest.mark.parametrize(
    "locale,key",
    [("vi", "onboard.welcome"), ("en", "onboard.welcome"), ("vi", "payment.matched")],
)
def test_t_extra_kwargs_ignored(locale: str, key: str) -> None:
    # Passing irrelevant kwargs should NOT raise — str.format ignores them.
    out_with = t(locale, key, name="X", amount="1đ", bogus="ignored")
    assert isinstance(out_with, str)
    assert "X" in out_with or "1đ" in out_with or out_with  # non-empty
