"""Small helpers for persisted conversational state."""

from __future__ import annotations

import json
from typing import Any

from core import db


async def get_state(user_id: int) -> tuple[str | None, dict[str, Any]]:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT step, payload FROM bot_state WHERE user_id = $1;",
            user_id,
        )
    if row is None:
        return None, {}
    raw_payload = row["payload"] or {}
    if isinstance(raw_payload, str):
        payload = json.loads(raw_payload)
    else:
        payload = raw_payload
    return row["step"], dict(payload)


async def set_state(user_id: int, step: str, payload: dict[str, Any]) -> None:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_state (user_id, step, payload, updated_at)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET step = EXCLUDED.step,
                payload = EXCLUDED.payload,
                updated_at = NOW();
            """,
            user_id,
            step,
            json.dumps(payload),
        )


async def clear_state(user_id: int) -> None:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_state (user_id, step, payload, updated_at)
            VALUES ($1, NULL, '{}'::jsonb, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET step = NULL,
                payload = '{}'::jsonb,
                updated_at = NOW();
            """,
            user_id,
        )


__all__ = ["clear_state", "get_state", "set_state"]
