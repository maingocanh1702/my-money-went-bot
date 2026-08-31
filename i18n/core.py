"""
i18n/core.py — Language configuration and translation function.

Storage: language preference is stored in the Bot State JSON under key "lang".
It is preserved across clear_state() calls via the sheets module.

Usage:
    from i18n.core import t, get_lang, set_lang

    # In any handler:
    await tg.send_text(t("manage.title", month="2026-08"))

    # Toggle language:
    set_lang("en")  # or "vi"
"""
from __future__ import annotations

from config import CHAT_ID

# ── Language preference cache ────────────────────────────────
# Single-user bot → one global lang. Cached in-process for speed;
# persisted to sheets for cross-restart durability.
_lang_cache: str | None = None


def get_lang() -> str:
    """Return current language code ('vi' or 'en'). Default: 'vi'."""
    global _lang_cache
    if _lang_cache is not None:
        return _lang_cache

    # Read from sheets state (one-time on cold start)
    import sheets as sh
    state = sh.get_state(CHAT_ID) or {}
    _lang_cache = state.get("lang", "vi")
    return _lang_cache


def set_lang(lang: str) -> None:
    """Set language preference and persist to sheets."""
    global _lang_cache
    lang = lang.lower().strip()
    if lang not in ("vi", "en"):
        lang = "vi"
    _lang_cache = lang

    import sheets as sh
    state = sh.get_state(CHAT_ID) or {}
    state["lang"] = lang
    sh.set_state(CHAT_ID, state)


def t(key: str, **kwargs) -> str:
    """Translate a string key to current language.

    Supports f-string-style interpolation:
        t("budget.saved", month="2026-08")

    Falls back: EN key missing → VI → raw "[key]"
    """
    from i18n.vi import STRINGS as VI
    from i18n.en import STRINGS as EN

    lang = get_lang()
    strings = EN if lang == "en" else VI
    template = strings.get(key) or VI.get(key, f"[{key}]")
    return template.format(**kwargs) if kwargs else template
