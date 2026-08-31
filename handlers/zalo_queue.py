"""handlers/zalo_queue.py — persistent Zalo pending-tx queue (parked items).

Zalo numbered-text menus depend on BOT_STATE: once a flow's state is
overwritten or cleared, the numbers in an old picker message stop working
(unlike Telegram, whose inline buttons carry row_num in callback_data).

This module gives Zalo the same guarantee Telegram got from
`pending_tx_queue`: a transaction that can't be shown as a picker right now
(user mid-flow, or the user ran a command over an active picker) is PARKED
under a dedicated Bot State row — key `zalopq:<chat_id>` — completely
separate from the flow state `zalo:<chat_id>`, so no clear_state()/set_state()
in any Zalo flow can drop it. `/pending` (Zalo) drains it one tx at a time.

Item shape (mirrors Telegram's pending_tx_queue items):
    {"row_num", "amount", "currency", "description", "tx_direction", "tx_date"}
"""
from __future__ import annotations

import sheets as sh

_ITEM_KEYS = ("row_num", "amount", "currency", "description",
              "tx_direction", "tx_date")


def parked_key(chat_id: str) -> str:
    return f"zalopq:{chat_id}"


def get_parked(chat_id: str) -> list[dict]:
    state = sh.get_state(parked_key(chat_id)) or {}
    items = state.get("items")
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def set_parked(chat_id: str, items: list[dict]) -> None:
    sh.set_state(parked_key(chat_id), {"items": items})


def parked_count(chat_id: str) -> int:
    return len(get_parked(chat_id))


def _slim(item: dict) -> dict:
    """Keep only the queue fields (drops picker-only keys like `buckets`)."""
    return {k: item.get(k) for k in _ITEM_KEYS if item.get(k) is not None}


def park(chat_id: str, item: dict) -> None:
    """Append one tx to the parked queue (dedup by row_num)."""
    if not isinstance(item, dict) or not item.get("row_num"):
        return
    items = get_parked(chat_id)
    if any(i.get("row_num") == item["row_num"] for i in items):
        return
    items.append(_slim(item))
    set_parked(chat_id, items)


def park_active_picker(chat_id: str, state: dict) -> int:
    """Park an active `await_zalo_parent` picker: current item + chained queue.

    Called before a command clears the flow state, so the numbered picker the
    user is abandoning doesn't silently lose its transactions. Returns how
    many items are parked afterwards.
    """
    if not isinstance(state, dict) or state.get("step") != "await_zalo_parent":
        return parked_count(chat_id)
    if state.get("row_num"):
        park(chat_id, state)
    for q in state.get("queue") or []:
        if isinstance(q, dict):
            park(chat_id, q)
    return parked_count(chat_id)


def pop_next_unconfirmed(chat_id: str) -> dict | None:
    """Pop the oldest parked tx that is still unconfirmed in the sheet.

    Already-confirmed rows (categorized meanwhile, e.g. via Telegram) are
    silently dropped. Returns None when nothing is left.
    """
    items = get_parked(chat_id)
    picked = None
    while items:
        candidate = items.pop(0)
        try:
            row = sh.get_transaction_row(int(candidate.get("row_num") or 0))
        except Exception:
            row = []
        if row and len(row) > 13 and str(row[13]).upper() == "TRUE":
            continue  # finalized elsewhere — skip
        picked = candidate
        break
    set_parked(chat_id, items)
    return picked
