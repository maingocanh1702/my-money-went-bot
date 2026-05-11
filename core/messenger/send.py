"""Top-level send() entry — looks up channel, dispatches to adapter."""

from __future__ import annotations

import inspect
from typing import cast

from core import db

from .base import BaseSender, SendPayload, senders_for


async def _resolve_channel(user_id: int) -> str:
    """Read the user's channel_type from the DB. Cached not required at W0
    scale — the user table is small and asyncpg's statement cache helps."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT channel_type FROM users WHERE id = $1;", user_id)
    if row is None:
        raise LookupError(f"user_id={user_id} not found")
    return cast(str, row["channel_type"])


async def _build(factory_or_awaitable: object) -> BaseSender:
    """Call the registered factory; await it if async."""
    result = factory_or_awaitable() if callable(factory_or_awaitable) else None
    if inspect.isawaitable(result):
        return cast(BaseSender, await result)
    return cast(BaseSender, result)


async def send(user_id: int, payload: SendPayload) -> None:
    """Send a payload to user_id's channel.

    Resolves the channel via DB, dispatches to the registered adapter.
    Validation runs inside `send_validated` so contract errors raise
    before any platform API call.
    """
    channel = await _resolve_channel(user_id)
    factory = senders_for(channel)
    sender = await _build(factory)
    await sender.send_validated(user_id, payload)
