"""Zalo category selection flow for newly captured SePay transactions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from core import db, messenger
from core.logging import get_logger
from core.messenger import Button, Markup
from core.services import bot_state
from i18n import t

log = get_logger(__name__, component="categorize")

_STEP = "await_category"
_QUEUE_TTL = timedelta(hours=6)


def _now() -> datetime:
    return datetime.now(UTC)


def _expires_at(now: datetime | None = None) -> str:
    base = now or _now()
    return (base + _QUEUE_TTL).isoformat()


def _is_expired(payload: dict[str, Any], now: datetime | None = None) -> bool:
    raw = str(payload.get("expires_at") or "")
    if not raw:
        return True
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires <= (now or _now())


async def send_category_picker(user_id: int, tx_id: int) -> None:
    """Queue a Zalo-only category picker for a newly inserted transaction."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT channel_type, locale FROM users WHERE id = $1;",
            user_id,
        )
        if user_row is None or user_row["channel_type"] != "zalo":
            return
        locale = str(user_row["locale"] or "vi")

        tx_row = await conn.fetchrow(
            """
            SELECT id, amount, direction, description, month_key
            FROM transactions
            WHERE id = $1 AND user_id = $2;
            """,
            tx_id,
            user_id,
        )
        if tx_row is None:
            return

        category_rows = await conn.fetch(
            """
            SELECT id, name
            FROM categories
            WHERE user_id = $1
              AND month_key = $2
              AND active = TRUE
            ORDER BY id;
            """,
            user_id,
            tx_row["month_key"],
        )

    if not category_rows:
        await messenger.send(
            user_id,
            {
                "text": t(locale, "categorize.no_categories"),
                "parse_mode": "plain",
            },
        )
        return

    entry = {
        "tx_id": int(tx_row["id"]),
        "amount": int(tx_row["amount"]),
        "direction": str(tx_row["direction"]),
        "description": str(tx_row["description"] or ""),
        "month_key": str(tx_row["month_key"]),
        "options": [
            {"index": index, "category_id": int(row["id"]), "name": str(row["name"])}
            for index, row in enumerate(category_rows, start=1)
        ],
    }

    step, payload = await bot_state.get_state(user_id)
    queue = []
    if step == _STEP and not _is_expired(payload):
        queue = list(payload.get("queue") or [])
    if not any(int(item.get("tx_id", 0)) == tx_id for item in queue):
        queue.append(entry)

    await bot_state.set_state(
        user_id,
        _STEP,
        {
            "queue": queue,
            "expires_at": _expires_at(),
        },
    )

    if len(queue) == 1:
        await _send_active_picker(user_id, entry, locale)
    else:
        await messenger.send(
            user_id,
            {
                "text": t(locale, "categorize.queue_added", count=len(queue)),
                "parse_mode": "plain",
            },
        )


async def handle_numbered_category_reply(user_id: int, text: str) -> bool:
    """Handle a Zalo numeric reply. Returns True when the text was consumed."""
    stripped = text.strip()
    if not stripped.isdigit():
        return False

    step, payload = await bot_state.get_state(user_id)
    if step != _STEP:
        return False

    locale = await _resolve_locale(user_id)

    if _is_expired(payload):
        await bot_state.clear_state(user_id)
        await messenger.send(
            user_id,
            {
                "text": t(locale, "categorize.expired"),
                "parse_mode": "plain",
            },
        )
        return True

    queue = list(payload.get("queue") or [])
    if not queue:
        await bot_state.clear_state(user_id)
        return False

    selected = int(stripped)
    entry = cast(dict[str, Any], queue[0])
    option = _find_option(entry, selected)
    if option is None:
        await messenger.send(
            user_id,
            {
                "text": _render_picker_text(
                    entry, locale, prefix=t(locale, "categorize.pick_invalid")
                ),
                "markup": _render_markup(entry),
                "parse_mode": "plain",
            },
        )
        return True

    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE transactions
            SET category_id = $1
            WHERE id = $2 AND user_id = $3;
            """,
            int(option["category_id"]),
            int(entry["tx_id"]),
            user_id,
        )

    remaining = queue[1:]
    await messenger.send(
        user_id,
        {
            "text": t(locale, "categorize.confirmed", name=option["name"]),
            "parse_mode": "plain",
        },
    )
    if remaining:
        await bot_state.set_state(
            user_id,
            _STEP,
            {"queue": remaining, "expires_at": _expires_at()},
        )
        await _send_active_picker(user_id, cast(dict[str, Any], remaining[0]), locale)
    else:
        await bot_state.clear_state(user_id)
    return True


async def _send_active_picker(user_id: int, entry: dict[str, Any], locale: str = "vi") -> None:
    await messenger.send(
        user_id,
        {
            "text": _render_picker_text(entry, locale),
            "markup": _render_markup(entry),
            "parse_mode": "plain",
        },
    )


def _find_option(entry: dict[str, Any], index: int) -> dict[str, Any] | None:
    for option in entry.get("options") or []:
        if int(option.get("index", 0)) == index:
            return cast(dict[str, Any], option)
    return None


async def _resolve_locale(user_id: int) -> str:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT locale FROM users WHERE id = $1;", user_id)
    return str(row["locale"]) if row else "vi"


def _render_picker_text(
    entry: dict[str, Any], locale: str = "vi", *, prefix: str | None = None
) -> str:
    if prefix is None:
        prefix = t(locale, "categorize.pick_prefix")
    amount = int(entry["amount"])
    direction = t(
        locale,
        "categorize.direction_in" if entry["direction"] == "in" else "categorize.direction_out",
    )
    description = str(entry.get("description") or t(locale, "categorize.no_description"))
    return f"{prefix}\n{direction} {amount:,} VND\n{description}"


def _render_markup(entry: dict[str, Any]) -> Markup:
    rows = [
        [
            Button(
                label=str(option["name"]),
                callback_data=f"cat:{entry['tx_id']}:{option['category_id']}",
            )
        ]
        for option in entry.get("options") or []
    ]
    return Markup(rows=rows)


__all__ = ["handle_numbered_category_reply", "send_category_picker"]
