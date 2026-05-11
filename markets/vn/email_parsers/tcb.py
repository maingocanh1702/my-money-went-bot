"""Techcombank (TCB) email parser.

W0.6 ships the registration shell + minimal can_parse heuristic. Full
HTML-table extraction lands in F02 alongside the rest of the capture
pipeline — at that point the parser swaps body text/HTML for the real
TCB notification format. The contract (CanonicalTx out, no DB / no
messenger) is locked in here so F02 just fills the parse() body.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from core.canonical_tx import CanonicalTx

from .base import BankEmailParser, InboundEmail, register_parser

_SENDER_RE = re.compile(r"@(techcombank\.com\.vn|tcb\.com\.vn)$", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"([\d,.]+)\s*(?:VND|đ)", re.IGNORECASE)


@register_parser("TCB")
class TCBParser(BankEmailParser):
    """TCB notification emails: 'GD-TCB-…'."""

    def can_parse(self, email: InboundEmail) -> bool:
        if not _SENDER_RE.search(email.sender or ""):
            return False
        return "TCB" in (email.subject or "").upper()

    def parse(self, email: InboundEmail) -> CanonicalTx:
        body = email.body_text or email.body_html
        match = _AMOUNT_RE.search(body)
        if not match:
            raise ValueError("TCBParser: no amount found in email body")
        amount = int(match.group(1).replace(",", "").replace(".", ""))
        direction: Literal["in", "out"] = (
            "in" if ("+" in body or "ghi có" in body.lower()) else "out"
        )
        return CanonicalTx(
            source="email_tcb",
            bank="TCB",
            direction=direction,
            amount=amount,
            tx_date=(
                datetime.fromisoformat(email.received_at) if email.received_at else datetime.now()
            ),
            description=email.subject or "",
        )
