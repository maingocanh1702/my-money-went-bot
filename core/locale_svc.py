"""Locale auto-detection + bilingual default-category catalog.

Spec: docs/features/feature-i18n.md §8 (detect algorithm), §4 (categories).
BE tech: docs/features/BE/feature-i18n-tech.md §3.2, §4.2.

Detection rules (identical across channels; normalized lowercase):
    NULL / empty       → 'vi' (default — Vietnam-first launch)
    startswith('vi')   → 'vi'  (e.g. 'vi', 'vi-VN', 'vi_VN')
    anything else      → 'en'  (e.g. 'en-US', 'pt-BR', 'ja')

The 3 channel functions are deliberately kept as thin wrappers around
`_normalize()` so callers stay channel-agnostic at the signature level
(easier to wire in channel-specific handlers) while behaviour is shared.
"""

from __future__ import annotations

from typing import Final, TypedDict


class CategorySpec(TypedDict):
    """Shape of a default-category seed row."""

    slug: str
    name: str
    daily_cap: int | None


SUPPORTED_LOCALES: Final[tuple[str, ...]] = ("vi", "en")
_DEFAULT: Final[str] = "vi"


def _normalize(raw: str | None) -> str:
    """Map a raw language tag to one of SUPPORTED_LOCALES.

    Strips surrounding whitespace first so accidentally-padded values
    (e.g. ' vi ', whitespace-only) behave the same as None/empty.
    """
    if not raw:
        return _DEFAULT
    lc = raw.strip().lower()
    if not lc:
        return _DEFAULT
    if lc.startswith("vi"):
        return "vi"
    return "en"


def detect_locale_from_telegram(language_code: str | None) -> str:
    """Detect locale from Telegram `user.language_code` (e.g. 'vi', 'en-US')."""
    return _normalize(language_code)


def detect_locale_from_discord(interaction_locale: str | None) -> str:
    """Detect locale from Discord interaction `locale` field (e.g. 'vi', 'en-US')."""
    return _normalize(interaction_locale)


def detect_locale_from_messenger(profile_locale: str | None) -> str:
    """Detect locale from Messenger user profile `locale` (e.g. 'vi_VN', 'en_US')."""
    return _normalize(profile_locale)


# ─────────────────────────────────────────────────────────────────────
# Default categories per locale — used by onboarding to seed users.
# Kept here (not in i18n/) because these are seed *data*, not translation
# templates. The names are localized but slugs are language-agnostic.
# ─────────────────────────────────────────────────────────────────────
CATEGORIES_BY_LOCALE: Final[dict[str, list[CategorySpec]]] = {
    "vi": [
        {"slug": "daily_spending", "name": "🛒 Chi tiêu hàng ngày", "daily_cap": 100_000},
        {"slug": "saving", "name": "🏦 Tiết kiệm", "daily_cap": None},
        {"slug": "subscription", "name": "📱 Đăng ký dịch vụ", "daily_cap": None},
    ],
    "en": [
        {"slug": "daily_spending", "name": "🛒 Daily Spending", "daily_cap": 100_000},
        {"slug": "saving", "name": "🏦 Saving", "daily_cap": None},
        {"slug": "subscription", "name": "📱 Subscription", "daily_cap": None},
    ],
}


def default_categories_for(locale: str) -> list[CategorySpec]:
    """Return default category seed rows for `locale` (falls back to vi)."""
    return CATEGORIES_BY_LOCALE.get(locale, CATEGORIES_BY_LOCALE[_DEFAULT])


# ─────────────────────────────────────────────────────────────────────
# Currency formatting — needs locale because suffix differs ('đ' vs 'VND').
# Both locales use VN-style grouping (dot-separated thousands) since VND is
# the only currency we operate in today.
# ─────────────────────────────────────────────────────────────────────
def fmt_currency(amount: int, locale: str) -> str:
    """Format an integer VND amount per locale.

    1500000, 'vi' → '1.500.000đ'
    1500000, 'en' → '1.500.000 VND'
    """
    grouped = f"{amount:,.0f}".replace(",", ".")
    if locale == "vi":
        return f"{grouped}đ"
    return f"{grouped} VND"


__all__ = [
    "CATEGORIES_BY_LOCALE",
    "CategorySpec",
    "SUPPORTED_LOCALES",
    "default_categories_for",
    "detect_locale_from_discord",
    "detect_locale_from_messenger",
    "detect_locale_from_telegram",
    "fmt_currency",
]
