"""Locale auto-detection — per-channel + edge cases.

5-category coverage:
- Happy path: vi / en / locale tags with regions.
- Retry / idempotency: same input ⇒ same output (pure function).
- Missing optional fields: None / empty string → default 'vi'.
- Pathological inputs: unknown / mixed-case / unicode / surrounding whitespace.
- Concurrent access: N/A — pure stateless functions (skip with comment).
"""

from __future__ import annotations

import pytest

from core.locale_svc import (
    CATEGORIES_BY_LOCALE,
    SUPPORTED_LOCALES,
    default_categories_for,
    detect_locale_from_discord,
    detect_locale_from_messenger,
    detect_locale_from_telegram,
    fmt_currency,
)

# ── happy path: Telegram ────────────────────────────────────────────


@pytest.mark.parametrize(
    "lang,expected",
    [
        ("vi", "vi"),
        ("vi-VN", "vi"),
        ("VI", "vi"),
        ("en", "en"),
        ("en-US", "en"),
        ("EN-GB", "en"),
    ],
)
def test_detect_telegram_happy(lang: str, expected: str) -> None:
    assert detect_locale_from_telegram(lang) == expected


# ── missing optional fields ────────────────────────────────────────


@pytest.mark.parametrize("lang", [None, "", "   "])
def test_detect_telegram_null_or_empty_defaults_to_vi(lang: str | None) -> None:
    assert detect_locale_from_telegram(lang) == "vi"


# ── pathological / non-vi tags fall through to en ───────────────────


@pytest.mark.parametrize("lang", ["pt-BR", "ja", "ko", "zh-CN", "fr", "de-DE"])
def test_detect_non_vi_falls_through_to_en(lang: str) -> None:
    assert detect_locale_from_telegram(lang) == "en"


# ── Discord variants ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "loc,expected",
    [("vi", "vi"), ("en-US", "en"), ("", "vi"), (None, "vi"), ("zh-TW", "en")],
)
def test_detect_discord(loc: str | None, expected: str) -> None:
    assert detect_locale_from_discord(loc) == expected


# ── Messenger variants (uses underscore separator: 'vi_VN', 'en_US') ──


@pytest.mark.parametrize(
    "loc,expected",
    [("vi_VN", "vi"), ("en_US", "en"), ("", "vi"), (None, "vi"), ("pt_BR", "en")],
)
def test_detect_messenger(loc: str | None, expected: str) -> None:
    assert detect_locale_from_messenger(loc) == expected


# ── idempotency: same input twice ⇒ same output ─────────────────────


def test_detect_is_idempotent() -> None:
    assert detect_locale_from_telegram("vi-VN") == detect_locale_from_telegram("vi-VN")
    assert detect_locale_from_telegram(None) == detect_locale_from_telegram(None)


# ── default-category catalog ────────────────────────────────────────


def test_default_categories_vi_uses_vietnamese_names() -> None:
    cats = default_categories_for("vi")
    assert [c["slug"] for c in cats] == ["daily_spending", "saving", "subscription"]
    assert cats[0]["name"] == "🛒 Chi tiêu hàng ngày"
    assert cats[0]["daily_cap"] == 100_000
    assert cats[1]["daily_cap"] is None


def test_default_categories_en_uses_english_names() -> None:
    cats = default_categories_for("en")
    assert [c["slug"] for c in cats] == ["daily_spending", "saving", "subscription"]
    assert cats[0]["name"] == "🛒 Daily Spending"


def test_default_categories_unknown_locale_falls_back_to_vi() -> None:
    assert default_categories_for("fr") == default_categories_for("vi")


def test_categories_table_covers_supported_locales() -> None:
    for lc in SUPPORTED_LOCALES:
        assert lc in CATEGORIES_BY_LOCALE
        assert len(CATEGORIES_BY_LOCALE[lc]) >= 1


def test_categories_have_matching_slugs_across_locales() -> None:
    vi_slugs = [c["slug"] for c in CATEGORIES_BY_LOCALE["vi"]]
    en_slugs = [c["slug"] for c in CATEGORIES_BY_LOCALE["en"]]
    assert vi_slugs == en_slugs, "slug ordering/identity must match across locales"


# ── currency formatting ─────────────────────────────────────────────


def test_fmt_currency_vi() -> None:
    assert fmt_currency(1_500_000, "vi") == "1.500.000đ"


def test_fmt_currency_en() -> None:
    assert fmt_currency(1_500_000, "en") == "1.500.000 VND"


def test_fmt_currency_zero() -> None:
    assert fmt_currency(0, "vi") == "0đ"
    assert fmt_currency(0, "en") == "0 VND"


def test_fmt_currency_negative() -> None:
    # Refunds / corrections show negative amount, grouping still works.
    assert fmt_currency(-50_000, "vi") == "-50.000đ"
