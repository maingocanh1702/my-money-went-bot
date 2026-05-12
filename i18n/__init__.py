"""i18n module — `t(locale, key, **kwargs)` helper + language packs.

Spec: docs/features/feature-i18n.md, docs/features/BE/feature-i18n-tech.md

Design:
- PACKS: in-memory dict {locale: {key: template}} loaded once at import.
- t() resolves: target locale → DEFAULT_LOCALE fallback → '[MISSING: key]'.
- format() KeyError (missing kwargs) returns raw template, never crashes.

Adding a new locale = add `i18n/<lc>.py` exposing UPPERCASE dict, plus an
entry in PACKS below. Key parity is enforced by tests/unit/test_i18n_parity.py.
"""

from __future__ import annotations

from i18n.en import EN
from i18n.vi import VI

DEFAULT_LOCALE = "vi"
SUPPORTED_LOCALES = ("vi", "en")
PACKS: dict[str, dict[str, str]] = {"vi": VI, "en": EN}


def t(locale: str, key: str, **kwargs: object) -> str:
    """Translate `key` for `locale` with optional format args.

    Resolution order:
        1. PACKS[locale][key]
        2. PACKS[DEFAULT_LOCALE][key]
        3. '[MISSING: key]'

    If format() raises KeyError (template references arg not provided), returns
    the raw unsubstituted template — never raises to caller. See edge case #11
    in feature spec.
    """
    pack = PACKS.get(locale, PACKS[DEFAULT_LOCALE])
    template = pack.get(key)
    if template is None and locale != DEFAULT_LOCALE:
        template = PACKS[DEFAULT_LOCALE].get(key)
    if template is None:
        return f"[MISSING: {key}]"
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def available_keys(locale: str = DEFAULT_LOCALE) -> set[str]:
    """Return set of translation keys for `locale` (debug/test helper)."""
    return set(PACKS.get(locale, {}).keys())


__all__ = ["DEFAULT_LOCALE", "EN", "PACKS", "SUPPORTED_LOCALES", "VI", "available_keys", "t"]
