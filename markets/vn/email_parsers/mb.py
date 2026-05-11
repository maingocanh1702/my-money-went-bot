"""MBBank (MB) email parser. W0.6 ships the shell + can_parse heuristic;
full HTML extraction lands in F02. Contract: CanonicalTx out, no DB,
no messenger."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from core.canonical_tx import CanonicalTx

from .base import BankEmailParser, InboundEmail, register_parser

_SENDER_RE = re.compile(r"@(mbbank\.com\.vn|mb\.com\.vn)$", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"([\d,.]+)\s*(?:VND|đ)", re.IGNORECASE)


@register_parser("MB")
class MBParser(BankEmailParser):
    def can_parse(self, email: InboundEmail) -> bool:
        if not _SENDER_RE.search(email.sender or ""):
            return False
        return "MB" in (email.subject or "").upper() or "MBBank" in (email.body_text or "")

    def parse(self, email: InboundEmail) -> CanonicalTx:
        body = email.body_text or email.body_html
        match = _AMOUNT_RE.search(body)
        if not match:
            raise ValueError("MBParser: no amount found")
        amount = int(match.group(1).replace(",", "").replace(".", ""))
        direction: Literal["in", "out"] = (
            "in" if ("ghi có" in body.lower() or "+" in body) else "out"
        )
        return CanonicalTx(
            source="email_mb",
            bank="MB",
            direction=direction,
            amount=amount,
            tx_date=(
                datetime.fromisoformat(email.received_at) if email.received_at else datetime.now()
            ),
            description=email.subject or "",
        )
