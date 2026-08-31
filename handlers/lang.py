"""
handlers/lang.py — /lang command: switch bot UI language (vi/en)
"""
from i18n.core import t, get_lang, set_lang
import telegram_api as tg


LANG_NAMES = {"vi": "🇻🇳 Tiếng Việt", "en": "🇬🇧 English"}


async def cmd_lang():
    """Show current language and toggle buttons."""
    lang = get_lang()
    msg = (
        f"{t('lang.title')}\n\n"
        f"{t('lang.current', lang_name=LANG_NAMES[lang])}\n\n"
        f"{t('lang.choose')}"
    )
    buttons = [[
        {"text": "🇻🇳 Tiếng Việt", "callback_data": "lang_vi"},
        {"text": "🇬🇧 English",     "callback_data": "lang_en"},
    ]]
    await tg.send_with_buttons(msg, buttons)


async def handle_lang_callback(parts: list[str], message_id: int):
    """Handle lang_vi / lang_en callbacks."""
    if len(parts) < 2:
        return
    lang = parts[1]
    if lang not in ("vi", "en"):
        return
    set_lang(lang)
    lang_name = LANG_NAMES[lang]
    await tg.edit_message(message_id, t("lang.switched", lang_name=lang_name))
