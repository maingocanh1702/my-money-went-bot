"""Minimal i18n stub.

Loads `core/messenger/locales/{vi,en}.json` once at import time and
exposes `t(key, locale, **params)` for adapters.

Production version (later wave) will likely use ICU / Babel / gettext.
W0.4 just needs a deterministic key → string lookup so adapter tests
have something to validate.

Behaviour:
  - `t("greeting", "vi")` → translation string from vi.json
  - Missing key: returns the key itself wrapped in `??` markers (loud)
  - Missing locale: falls back to `vi` (default market = Vietnam)
  - Params: applied via `str.format(**params)` if present
"""

from __future__ import annotations

import json
from importlib import resources

_DEFAULT_LOCALE = "vi"
_FALLBACK_LOCALES = ("vi", "en")

_CACHE: dict[str, dict[str, str]] = {}


def _load(locale: str) -> dict[str, str]:
    if locale in _CACHE:
        return _CACHE[locale]
    try:
        ref = resources.files("core.messenger.locales").joinpath(f"{locale}.json")
        with ref.open(encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)
        _CACHE[locale] = data
        return data
    except (FileNotFoundError, ModuleNotFoundError):
        _CACHE[locale] = {}
        return _CACHE[locale]


def t(key: str, locale: str = _DEFAULT_LOCALE, **params: object) -> str:
    """Translate `key` to `locale`. Falls back to vi, then key itself."""
    for candidate in (locale, *_FALLBACK_LOCALES):
        bundle = _load(candidate)
        if key in bundle:
            template = bundle[key]
            if params:
                return template.format(**params)
            return template
    return f"??{key}??"


def reset_cache() -> None:
    """Test helper — drop the in-memory locale cache."""
    _CACHE.clear()
