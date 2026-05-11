"""ACB email parser shell. F02 fills the parse() body."""

from __future__ import annotations

import re
from datetime import datetime

from core.canonical_tx import CanonicalTx

from .base import BankEmailParser, InboundEmail, register_parser

_SENDER_RE = re.compile(r"@acb\.com\.vn$", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"([\d,.]+)\s*(?:VND|đ)", re.IGNORECASE)


@register_parser("ACB")
class ACBParser(BankEmailParser):
    def can_parse(self, email: InboundEmail) -> bool:
        return bool(_SENDER_RE.search(email.sender or ""))

    def parse(self, email: InboundEmail) -> CanonicalTx:
        body = email.body_text or email.body_html
        match = _AMOUNT_RE.search(body)
        if not match:
            raise ValueError("ACBParser: no amount found")
        amount = int(match.group(1).replace(",", "").replace(".", ""))
        return CanonicalTx(
            source="email_acb",
            bank="ACB",
            direction="in" if "+" in body else "out",
            amount=amount,
            tx_date=(
                datetime.fromisoformat(email.received_at) if email.received_at else datetime.now()
            ),
            description=email.subject or "",
        )
