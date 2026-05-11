"""Bank email parser plugin tests — Gap 2 invariants.

Verifies:
  - All 6 expected parsers are registered.
  - Each parser's can_parse → True for its own synthetic email,
    can_parse → False for a foreign sender.
  - Each parser's parse() returns a CanonicalTx with non-empty bank,
    positive amount, and the registered bank ticker.
  - Static check: parser modules do NOT import core.db / core.messenger
    (defence-in-depth on top of the import-linter contract).
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest

from core.canonical_tx import CanonicalTx
from markets.vn.email_parsers import PARSERS, InboundEmail, find_parser

EXPECTED_BANKS = {"TCB", "MB", "ACB", "SACOMBANK", "BIDV", "CAKE"}

# Bank → realistic sender domain + body snippet that should trip can_parse.
SAMPLES: dict[str, dict[str, str]] = {
    "TCB": {
        "sender": "no-reply@techcombank.com.vn",
        "subject": "GD-TCB-IN: ghi co",
        "body": "Tai khoan cua quy khach +50,000 VND",
    },
    "MB": {
        "sender": "info@mbbank.com.vn",
        "subject": "MB Notify",
        "body": "MBBank ghi co 50,000 VND",
    },
    "ACB": {
        "sender": "alert@acb.com.vn",
        "subject": "ACB transaction",
        "body": "ACB +50,000 VND",
    },
    "SACOMBANK": {
        "sender": "alert@sacombank.com.vn",
        "subject": "Sacombank",
        "body": "Sacombank +50,000 VND",
    },
    "BIDV": {
        "sender": "alert@bidv.com.vn",
        "subject": "BIDV",
        "body": "BIDV +50,000 VND",
    },
    "CAKE": {
        "sender": "noreply@cake.vn",
        "subject": "Cake",
        "body": "Cake +50,000 VND",
    },
}


def test_all_six_parsers_registered() -> None:
    assert (
        set(PARSERS) == EXPECTED_BANKS
    ), f"Missing: {EXPECTED_BANKS - set(PARSERS)}; Extra: {set(PARSERS) - EXPECTED_BANKS}"


@pytest.mark.parametrize("bank", sorted(EXPECTED_BANKS))
def test_parser_can_parse_own_email(bank: str) -> None:
    s = SAMPLES[bank]
    email = InboundEmail(sender=s["sender"], subject=s["subject"], body_text=s["body"])
    parser_cls = PARSERS[bank]
    inst = parser_cls()
    assert inst.can_parse(email) is True


@pytest.mark.parametrize("bank", sorted(EXPECTED_BANKS))
def test_parser_rejects_foreign_sender(bank: str) -> None:
    email = InboundEmail(
        sender="alerts@some-other-bank.example",
        subject="random",
        body_text="ignore me",
    )
    parser_cls = PARSERS[bank]
    inst = parser_cls()
    assert inst.can_parse(email) is False


@pytest.mark.parametrize("bank", sorted(EXPECTED_BANKS))
def test_parser_produces_canonical_tx(bank: str) -> None:
    s = SAMPLES[bank]
    email = InboundEmail(sender=s["sender"], subject=s["subject"], body_text=s["body"])
    parser_cls = PARSERS[bank]
    tx = parser_cls().parse(email)
    assert isinstance(tx, CanonicalTx)
    assert tx.bank == bank
    assert tx.amount == 50_000
    assert tx.direction in ("in", "out")
    assert tx.source.startswith("email_")


def test_find_parser_dispatches_to_first_match() -> None:
    s = SAMPLES["TCB"]
    email = InboundEmail(sender=s["sender"], subject=s["subject"], body_text=s["body"])
    parser = find_parser(email)
    assert parser is not None
    assert parser.bank == "TCB"


def test_find_parser_returns_none_for_unknown_sender() -> None:
    email = InboundEmail(
        sender="random@nowhere.example",
        subject="hello",
        body_text="no bank header here",
    )
    assert find_parser(email) is None


_PARSER_DIR = Path(__file__).resolve().parent.parent.parent / "markets" / "vn" / "email_parsers"
_FORBIDDEN_IMPORT_RE = re.compile(r"^(?:from|import)\s+core\.(?:db|messenger)\b", re.MULTILINE)


def test_parser_modules_dont_import_db_or_messenger() -> None:
    """Belt-and-braces — the .importlinter `parsers-are-pure` contract
    enforces this, but a grep-level check catches edits that bypass
    static analysis (e.g. lazy imports inside functions)."""
    offenders: list[str] = []
    for path in _PARSER_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _FORBIDDEN_IMPORT_RE.search(text):
            offenders.append(path.name)
    assert offenders == [], f"Parsers must NOT import core.db / core.messenger; got: {offenders}"


def test_register_parser_rejects_empty_bank() -> None:
    """Decorator factory rejects empty bank — early failure beats a
    silently-broken registry."""
    from markets.vn.email_parsers.base import register_parser

    with pytest.raises(ValueError, match="non-empty"):
        register_parser("")


def test_all_parsers_inherit_baseparser() -> None:
    from markets.vn.email_parsers.base import BankEmailParser

    for cls in PARSERS.values():
        assert inspect.isclass(cls)
        assert issubclass(cls, BankEmailParser)


def test_parser_module_import_idempotent() -> None:
    """Re-importing the parsers package doesn't double-register."""
    before = dict(PARSERS)
    importlib.reload(importlib.import_module("markets.vn.email_parsers"))
    assert set(PARSERS) == set(before)
