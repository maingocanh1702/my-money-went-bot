"""Canonical transaction schema — the contract email parsers MUST produce.

Why this lives in `core/`: the contract is shared across markets. Both
VN (SePay webhook + bank email parsers) and Global (Plaid/TrueLayer
adapters) MUST emit `CanonicalTx` so downstream pipeline code is
market-agnostic.

Parsers are PURE: take raw email, return CanonicalTx. They MUST NOT:
  - touch the DB (no asyncpg / sqlalchemy imports)
  - send messenger replies (no core.messenger imports)
  - perform side effects of any kind

This is enforced statically by the parser-purity contract in
`.importlinter` (`markets.vn.email_parsers MUST NOT import core.db /
core.messenger`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class CanonicalTx:
    """Output of every transaction-capture parser.

    Persisted later by the capture pipeline — parsers don't touch the DB.
    """

    # Originating source — 'sepay', 'email_tcb', 'email_mb', etc.
    source: str
    # Bank ticker normalised to upper case: 'TCB', 'MB', 'ACB', ...
    bank: str
    # 'in' (credit / deposit) | 'out' (debit / withdrawal / spend)
    direction: Literal["in", "out"]
    # Integer VND (no sub-unit for VND). Always positive — direction
    # carries the sign.
    amount: int
    # When the bank says the transaction happened (TZ-aware).
    tx_date: datetime
    # Bank-side reference code (may be empty if the source doesn't
    # provide one; dedupe uses (user_id, ref_code) UNIQUE).
    ref_code: str = ""
    # Free-text description / merchant memo.
    description: str = ""
    # Last 4 of the account/card if known; '' otherwise. Feeds F08
    # funding-source discovery.
    last4: str = ""
    # Provider's own event identifier when distinct from bank's ref_code:
    # SePay `id`, Plaid `transaction_id`, TrueLayer `transaction_id`, etc.
    # Used by the capture pipeline as a stronger dedupe fallback when
    # `ref_code` is empty — same provider event id ⇒ same logical event.
    provider_event_id: str = ""

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError(
                f"CanonicalTx.amount must be a positive int (direction carries sign); "
                f"got {self.amount}"
            )
        if self.direction not in ("in", "out"):
            raise ValueError(f"CanonicalTx.direction must be 'in'|'out'; got {self.direction!r}")
        if not self.source:
            raise ValueError("CanonicalTx.source must be non-empty")
        if not self.bank:
            raise ValueError("CanonicalTx.bank must be non-empty")
