#!/usr/bin/env python3
"""Print the Zalo sender ids that have messaged your bot, for ZALO_CHAT_ID.

Zalo's Bot API has no "who am I" endpoint. The only way to learn your own
sender id is to message the bot and read it back off the update — which is why
this script exists rather than a line in the docs telling you to grep the
server log.

    1. Open Zalo, find your bot, send it any message ("hi" will do).
    2. python3 scripts/zalo_get_updates.py
    3. Copy the sender id into ZALO_CHAT_ID.

Reads ZALO_BOT_TOKEN from the environment or from .env. Pass the token as the
first argument to override both.

Note: getUpdates and a registered webhook are mutually exclusive on most bot
platforms — if the bot already has its webhook set, unset it in Zalo Bot
Manager first, or read the sender id from your server logs instead.
"""
from __future__ import annotations

import json
import os
import sys

import httpx

API_BASE = "https://bot-api.zaloplatforms.com"


def _token() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    token = os.environ.get("ZALO_BOT_TOKEN", "").strip()
    if token:
        return token
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return os.environ.get("ZALO_BOT_TOKEN", "").strip()


def _senders(payload: dict) -> list[tuple[str, str, str]]:
    """(sender_id, display name, message text) for each update, newest last."""
    out = []
    for update in payload.get("result") or payload.get("data") or []:
        message = update.get("message") or update.get("event_data") or {}
        sender = message.get("from") or message.get("sender") or {}
        sid = str(sender.get("id") or sender.get("user_id") or "")
        if sid:
            out.append((sid, str(sender.get("display_name") or sender.get("name") or ""),
                        str(message.get("text") or "")[:40]))
    return out


def main() -> int:
    token = _token()
    if not token:
        print("No ZALO_BOT_TOKEN. Set it in .env, export it, or pass it as an argument:")
        print("    python3 scripts/zalo_get_updates.py <bot-token>")
        return 2

    try:
        r = httpx.get(f"{API_BASE}/bot{token}/getUpdates", timeout=15)
    except httpx.HTTPError as e:
        print(f"Could not reach the Zalo Bot API: {e}")
        return 1

    if r.status_code != 200:
        print(f"Zalo returned HTTP {r.status_code}: {r.text[:300]}")
        return 1

    try:
        payload = r.json()
    except ValueError:
        print(f"Zalo returned something that is not JSON:\n{r.text[:300]}")
        return 1

    senders = _senders(payload)
    if not senders:
        print("No updates yet. Message your bot on Zalo, then run this again.")
        print("If the bot already has a webhook registered, getUpdates stays empty —")
        print("unset the webhook in Zalo Bot Manager, or read sender_id from your logs.")
        print(f"\nRaw response:\n{json.dumps(payload, ensure_ascii=False, indent=2)[:800]}")
        return 1

    print("Sender ids that have messaged this bot (most recent last):\n")
    seen = set()
    for sid, name, text in senders:
        if sid in seen:
            continue
        seen.add(sid)
        label = f" — {name}" if name else ""
        preview = f'  "{text}"' if text else ""
        print(f"  ZALO_CHAT_ID={sid}{label}{preview}")
    print("\nYours is the one whose message you just sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
