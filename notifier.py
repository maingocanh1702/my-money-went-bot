"""
notifier.py — Dual-channel notification fan-out (Telegram + Zalo)

Routes to whichever channels are enabled via config.TELEGRAM_ENABLED /
config.ZALO_ENABLED.  Either channel's failure never blocks the other or
SePay transaction processing.
"""
import asyncio
import config
import telegram_api as tg
import zalo_api as zalo


async def send_text(text: str, chat_id: str = None):
    """Send text notification to enabled channels.

    Telegram gets full Markdown formatting.
    Zalo fan-out is best-effort (background task) and gets plain text.
    """
    if config.TELEGRAM_ENABLED:
        try:
            await tg.send_text(text, chat_id)
        except Exception as e:
            print(f"[notifier] Telegram send failed (non-fatal): {e}")

    if config.ZALO_ENABLED:
        async def _send_zalo():
            try:
                await zalo.send_text(text)
            except Exception as e:
                print(f"[notifier] Zalo fan-out failed (non-fatal): {e}")

        asyncio.create_task(_send_zalo())
