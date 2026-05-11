"""Bank email parser plugin pattern (Gap 2).

ABC + module-level registry + `@register_parser('BANK')` decorator.

Parsers are PURE. Hard invariants enforced by the import-linter
`parsers-are-pure` contract:
  - parsers MUST NOT import `core.db` (no DB writes from a parser)
  - parsers MUST NOT import `core.messenger` (no replies from a parser)
  - parsers only take raw email → emit CanonicalTx

Pipeline orchestration (dedupe, DB write, messenger reply) lives in
`markets.vn.capture` — parsers stay laser-focused on parsing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from core.canonical_tx import CanonicalTx


@dataclass(frozen=True, slots=True)
class InboundEmail:
    """Minimal inbound-email envelope. The mail-receiver layer (W0.6+,
    later wave) builds these from SMTP/SES/etc. and hands them to
    parsers."""

    sender: str  # 'no-reply@techcombank.com.vn'
    subject: str
    body_text: str  # plain-text body (may be empty when only HTML)
    body_html: str = ""  # HTML body (often where TCB / MB put the table)
    received_at: str = ""  # ISO-8601 from the mailbox metadata


class BankEmailParser(ABC):
    """Abstract parser for one bank.

    `bank` is the normalised ticker: 'TCB', 'MB', 'ACB', 'CAKE', 'BIDV',
    'SACOMBANK'. Capture pipeline matches on `bank` to log
    `source='email_<bank>'` on the resulting tx row.
    """

    bank: str = ""

    @abstractmethod
    def can_parse(self, email: InboundEmail) -> bool:
        """Cheap predicate — usually a sender-address / subject prefix
        check. MUST NOT raise. MUST NOT touch the DB."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, email: InboundEmail) -> CanonicalTx:
        """Extract a CanonicalTx from the email body.

        Raises ValueError if parsing fails — the capture pipeline catches
        that and routes to the unparseable-email admin queue."""
        raise NotImplementedError


PARSERS: dict[str, type[BankEmailParser]] = {}


def register_parser(bank: str) -> Callable[[type[BankEmailParser]], type[BankEmailParser]]:
    """Class decorator: register a `BankEmailParser` subclass for `bank`.

    Idempotent — repeat registration overwrites (matters for tests that
    monkeypatch a parser)."""
    if not bank:
        raise ValueError("register_parser: bank must be a non-empty string")

    def wrapper(cls: type[BankEmailParser]) -> type[BankEmailParser]:
        cls.bank = bank
        PARSERS[bank] = cls
        return cls

    return wrapper


def get_parser(bank: str) -> type[BankEmailParser]:
    """Look up a parser by bank ticker. Raises KeyError if not registered."""
    if bank not in PARSERS:
        raise KeyError(f"No parser registered for bank={bank!r}. " f"Registered: {sorted(PARSERS)}")
    return PARSERS[bank]


def find_parser(email: InboundEmail) -> BankEmailParser | None:
    """Return the first registered parser whose `can_parse(email)` is True,
    or None if no parser claims the email."""
    for cls in PARSERS.values():
        inst = cls()
        try:
            if inst.can_parse(email):
                return inst
        except Exception:  # noqa: BLE001, S112 — defensive: a broken parser
            # must not crash the dispatcher. Parser purity rules mean
            # parsers can't use core logging directly; the dispatcher
            # caller (markets.vn.capture) logs the skip with full context.
            continue
    return None
