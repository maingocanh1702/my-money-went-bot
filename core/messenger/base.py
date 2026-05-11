"""Adapter contract — types every sender must implement.

`SendPayload` is verbatim per Gap 4 decision in the W0 autopilot spec.

Rules (enforced at runtime by `_validate_payload()`):
  - Exactly ONE of `text_key` or `text` must be set.
  - If `markup` present, it MUST be a `Markup` dataclass — never a
    platform-specific structure like Telegram's `InlineKeyboardMarkup`
    (that conversion is the adapter's job).
  - Each `Button` must have exactly ONE label source (label_key XOR label)
    AND exactly ONE action (callback_data XOR url).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

PARSER_MODE_MARKDOWN = "markdown"
PARSER_MODE_HTML = "html"
PARSER_MODE_PLAIN = "plain"
_ALLOWED_PARSE_MODES = {PARSER_MODE_MARKDOWN, PARSER_MODE_HTML, PARSER_MODE_PLAIN}


@dataclass
class Button:
    """One button in a Markup row.

    Label: exactly one of `label_key` (i18n) or `label` (raw, escape hatch).
    Action: exactly one of `callback_data` (in-bot routing) or `url` (open URL).
    """

    label_key: str | None = None
    label: str | None = None
    callback_data: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if (self.label_key is None) == (self.label is None):
            raise ValueError(
                "Button: exactly one of label_key or label must be set "
                f"(got label_key={self.label_key!r}, label={self.label!r})"
            )
        if (self.callback_data is None) == (self.url is None):
            raise ValueError(
                "Button: exactly one of callback_data or url must be set "
                f"(got callback_data={self.callback_data!r}, url={self.url!r})"
            )


@dataclass
class Markup:
    """Abstract keyboard. Adapters translate `rows` to platform format
    (Telegram InlineKeyboardMarkup, Discord buttons, Messenger quick replies)."""

    rows: list[list[Button]] = field(default_factory=list)


class SendPayload(TypedDict, total=False):
    """Outbound message payload — abstract over platform.

    Required: exactly ONE of `text_key` OR `text`.
    Optional: `text_params`, `locale`, `markup`, `parse_mode`.
    """

    text_key: str
    text_params: dict[str, Any]
    text: str
    locale: str
    markup: Markup | None
    parse_mode: Literal["markdown", "html", "plain"]


def _validate_payload(payload: SendPayload) -> None:
    """Raise ValueError if payload violates the contract."""
    has_key = "text_key" in payload and payload["text_key"] is not None
    has_text = "text" in payload and payload["text"] is not None
    if has_key == has_text:
        raise ValueError(
            f"SendPayload: exactly one of text_key or text must be set "
            f"(text_key={'set' if has_key else 'unset'}, "
            f"text={'set' if has_text else 'unset'})"
        )
    parse_mode = payload.get("parse_mode")
    if parse_mode is not None and parse_mode not in _ALLOWED_PARSE_MODES:
        raise ValueError(
            f"SendPayload.parse_mode must be one of {sorted(_ALLOWED_PARSE_MODES)}, "
            f"got {parse_mode!r}"
        )
    markup = payload.get("markup")
    if markup is not None and not isinstance(markup, Markup):
        raise TypeError(
            f"SendPayload.markup must be a core.messenger.Markup dataclass, "
            f"got {type(markup).__name__}"
        )


class BaseSender(ABC):
    """Abstract messenger adapter. Subclasses implement one channel."""

    channel_type: str = ""

    @abstractmethod
    async def send(self, user_id: int, payload: SendPayload) -> None:
        """Send `payload` to `user_id` on this channel.

        MUST call `_validate_payload(payload)` (or rely on the
        `send_validated` wrapper) before any platform API call so contract
        violations surface as ValueError immediately rather than as
        opaque platform API errors.
        """
        raise NotImplementedError

    async def send_validated(self, user_id: int, payload: SendPayload) -> None:
        """Wrapper that validates before delegating to `send()`."""
        _validate_payload(payload)
        await self.send(user_id, payload)


# ─── Adapter registry ──────────────────────────────────────────────────
# Channel → factory that builds a BaseSender. Factories are zero-arg so
# adapters can read their own config (env vars) at instantiation time.

_REGISTRY: dict[str, Callable[[], BaseSender] | Callable[[], Awaitable[BaseSender]]] = {}


def register_sender(
    channel_type: str,
) -> Callable[
    [Callable[[], BaseSender] | Callable[[], Awaitable[BaseSender]]],
    Callable[[], BaseSender] | Callable[[], Awaitable[BaseSender]],
]:
    """Decorator: register an adapter factory for `channel_type`.

    Idempotent on re-import of the same module — the second registration
    overwrites the first (matters for tests that monkeypatch a sender).
    """

    def wrapper(
        factory: Callable[[], BaseSender] | Callable[[], Awaitable[BaseSender]],
    ) -> Callable[[], BaseSender] | Callable[[], Awaitable[BaseSender]]:
        _REGISTRY[channel_type] = factory
        return factory

    return wrapper


def senders_for(
    channel_type: str,
) -> Callable[[], BaseSender] | Callable[[], Awaitable[BaseSender]]:
    """Look up the factory for a channel. Raises KeyError if none registered."""
    if channel_type not in _REGISTRY:
        raise KeyError(
            f"No sender registered for channel_type={channel_type!r}. "
            f"Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[channel_type]
