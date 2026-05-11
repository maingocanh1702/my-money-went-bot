"""Structured logging — structlog with tenant + request_id binding.

Production: JSON to stdout (Railway captures stdout → logtail). Dev:
human-friendly console renderer with colours.

Binding policy:
  Every log line gets `user_id` + `request_id` from `tenant_context`
  via the `bind_tenant` processor. If the context is unset (e.g. log
  before request handler runs), those fields are omitted.

`get_logger(name)` returns a `structlog.stdlib.BoundLogger`. Callers
should bind further fields per call site (e.g. `log.info("tx.captured",
amount=50000)`).
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from core import tenant_context


def _bind_tenant(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """structlog processor: inject user_id + request_id from ContextVars."""
    uid = tenant_context.get_user_id_or_none()
    if uid is not None:
        event_dict.setdefault("user_id", uid)
    rid = tenant_context.get_request_id()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def _resolve_env() -> str:
    return os.environ.get("APP_ENV", "dev").lower()


def configure_logging(env: str | None = None, *, level: str = "INFO") -> None:
    """Wire up structlog + stdlib logging. Idempotent."""
    env = (env or _resolve_env()).lower()

    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _bind_tenant,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env in {"prod", "production", "staging"}:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound logger. `name` becomes the logger name; `initial`
    kwargs are bound up-front (e.g. component='webhook')."""
    logger = structlog.get_logger(name) if name else structlog.get_logger()
    if initial:
        logger = logger.bind(**initial)
    return logger  # type: ignore[no-any-return]


def render_event_for_test(event_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Test helper: run our processors against a synthetic event dict
    so tests can assert tenant binding without spinning a real logger."""
    out: EventDict = dict(event_dict)
    _bind_tenant(None, "info", out)
    return dict(out)
