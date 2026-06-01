#!/usr/bin/env python3
"""
scripts/zalo_get_updates.py — Discover your ZALO_CHAT_ID

Usage:
    1. Set ZALO_BOT_TOKEN env var (or pass as argument)
    2. Open Zalo and send a message to your bot
    3. Run: python scripts/zalo_get_updates.py
    4. The script will print the chat ID of whoever messaged the bot

This uses getUpdates (long polling) one time to fetch recent messages.
"""
import asyncio
import os
import sys
import httpx

ZALO_BOT_TOKEN = os.environ.get("ZALO_BOT_TOKEN", "")


async def main():
    token = ZALO_BOT_TOKEN or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not token:
        print("❌ Usage: ZALO_BOT_TOKEN=xxx python scripts/zalo_get_updates.py")
        print("   or:   python scripts/zalo_get_updates.py <BOT_TOKEN>")
        sys.exit(1)

    base = f"https://bot-api.zaloplatforms.com/bot{token}"

    async with httpx.AsyncClient(timeout=35) as client:
        # First, verify the token is valid
        print("🔍 Verifying bot token...")
        r = await client.post(f"{base}/getMe")
        data = r.json()
        if not data.get("ok"):
            print(f"❌ Invalid token: {data}")
            sys.exit(1)
        bot_info = data.get("result", {})
        print(f"✅ Bot: {bot_info.get('display_name', 'Unknown')} (ID: {bot_info.get('id', '?')})")

        print("\n📨 Fetching recent messages (waiting up to 30s for new ones)...")
        print("   💡 Tip: gửi 1 tin nhắn bất kỳ cho bot trên Zalo rồi chờ...\n")

        r = await client.post(f"{base}/getUpdates", json={"timeout": "30"})
        data = r.json()

        if not data.get("ok"):
            print(f"❌ getUpdates failed: {data}")
            sys.exit(1)

        updates = data.get("result", [])
        if not updates:
            print("⚠️  Không nhận được message nào.")
            print("   → Hãy gửi tin nhắn cho bot trên Zalo trước, rồi chạy lại script này.")
            sys.exit(0)

        print(f"📬 Nhận được {len(updates)} update(s):\n")
        seen_chats = set()
        for update in updates:
            msg = update.get("message", {})
            sender = msg.get("from", {})
            chat = msg.get("chat", {})
            text = msg.get("text", "(no text)")

            chat_id = chat.get("id", "?")
            if chat_id not in seen_chats:
                seen_chats.add(chat_id)
                print(f"  👤 {sender.get('display_name', 'Unknown')}")
                print(f"     chat_id: {chat_id}")
                print(f"     user_id: {sender.get('id', '?')}")
                print(f"     text:    {text}")
                print()

        if seen_chats:
            primary = list(seen_chats)[0]
            print(f"═══════════════════════════════════════════")
            print(f"  ✅ Set ZALO_CHAT_ID={primary}")
            print(f"═══════════════════════════════════════════")


if __name__ == "__main__":
    asyncio.run(main())
