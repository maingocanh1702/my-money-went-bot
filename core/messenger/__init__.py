"""Outbound messenger abstraction.

Public API:
  - `send(user_id, payload)` — top-level entry. Looks up the user's channel
    (telegram/messenger/discord) and dispatches to the right adapter.
  - `BaseSender`, `SendPayload`, `Button`, `Markup` — adapter contract types.
  - `register_sender(channel_type)` — adapter self-registration decorator.

Adapters live in sibling modules (`telegram.py`, future `messenger.py`,
`discord.py`). Each adapter owns its platform-specific concerns: API
calls, message format, button/markup conversion, error mapping.

Core handlers emit ABSTRACT payloads (text_key + i18n params + abstract
Markup); adapters translate to platform format. This keeps platform
specifics out of business logic — see ADR-0001.
"""

from __future__ import annotations

# Side-effect imports: trigger @register_sender(...) so callers of
# `senders_for(...)` find factories without importing adapter modules.
from . import telegram as _telegram  # noqa: F401
from . import zalo as _zalo  # noqa: F401
from .base import (
    PARSER_MODE_HTML,
    PARSER_MODE_MARKDOWN,
    PARSER_MODE_PLAIN,
    BaseSender,
    Button,
    Markup,
    SendPayload,
    register_sender,
    senders_for,
)
from .send import send

__all__ = [
    "BaseSender",
    "Button",
    "Markup",
    "PARSER_MODE_HTML",
    "PARSER_MODE_MARKDOWN",
    "PARSER_MODE_PLAIN",
    "SendPayload",
    "register_sender",
    "send",
    "senders_for",
]
