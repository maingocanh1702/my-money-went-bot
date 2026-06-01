"""
notifier.py — Dual-channel notification fan-out (Telegram + Zalo)

For Phase 1: sends plain text notifications to both channels.
Only used for transaction notifications that do NOT need buttons.

Telegram always receives; Zalo only if ZALO_ENABLED=true.
Zalo failure never blocks Telegram delivery or transaction processing.
"""
import telegram_api as tg
import zalo_api as zalo
import asyncio


async def send_text(text: str, chat_id: str = None):
    """Send text notification to Telegram, and optionally to Zalo.

    Telegram gets full Markdown formatting.
    Zalo gets stripped plain text (handled inside zalo_api.send_text).
    """
    await tg.send_text(text, chat_id)
    # Zalo fan-out is best-effort and should not hold SePay processing open.
    async def _send_zalo():
        try:
            await zalo.send_text(text)
        except Exception as e:
            print(f"[notifier] Zalo fan-out failed (non-fatal): {e}")

    asyncio.create_task(_send_zalo())
