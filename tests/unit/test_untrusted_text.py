"""Text from outside, on its way into a Telegram message.

A bank memo is attacker-controlled — whoever sends you money writes it — and it
is interpolated into messages sent with Telegram's legacy Markdown, which has
no escape character. A memo shaped like a link therefore renders as a live,
clickable link inside a message the reader trusts as coming from their own bot.

Backticks were the existing defence and they are not one: a single backtick in
the memo closes the code span, and the rest of the memo is parsed as fresh
Markdown.
"""
import pytest

import handlers.sepay as sepay
import sheets as sh
import telegram_api as tg
from utils import md_safe

from tests.unit.test_phase1_sepay_flow import (  # noqa: F401  (fixture import)
    fake_world,
    _seed_account,
)
from tests.unit.test_sepay_event_identity import _payload, _tx_rows


PHISH = "[Xac nhan giao dich](https://phish.example/login)"


# ── the neutraliser ──────────────────────────────────────────────────────────

def test_a_link_shaped_memo_cannot_stay_a_link():
    out = md_safe(PHISH)
    assert "[" not in out and "]" not in out
    assert "(https://phish.example/login)" in out   # the text survives, the link does not


def test_a_backtick_cannot_close_the_span_it_was_wrapped_in():
    """`code` wrapping is not a defence — this is why the characters go."""
    assert "`" not in md_safe("coffee` *bold* [x](http://e.test)")


@pytest.mark.parametrize("raw", ["*bold*", "_italic_", "`code`", "[a](b)"])
def test_every_entity_opener_is_removed(raw):
    assert not (set(md_safe(raw)) & set("*_`[]"))


def test_parentheses_and_ordinary_text_are_kept():
    """Merchant names use parentheses constantly, and without a bracket they
    cannot form a link — removing them would cost readability for nothing."""
    assert md_safe("HIGHLANDS COFFEE (Q1) 12.000d") == "HIGHLANDS COFFEE (Q1) 12.000d"


def test_non_string_input_does_not_raise():
    assert md_safe(12345) == "12345"


# ── the path it protects ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_hostile_memo_reaches_telegram_neutralised(fake_world, monkeypatch):
    """End to end: a spend whose memo is a phishing link must not produce a
    message containing that link."""
    _seed_account()
    sent = []

    async def _capture(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _capture)
    monkeypatch.setattr(tg, "send_with_buttons", _capture)

    await sepay.handle_sepay_webhook(_payload(sepay_id=9001, desc=PHISH))

    assert sent, "the bot said nothing at all"
    body = "\n".join(str(m) for m in sent)
    assert "[Xac nhan giao dich]" not in body
    assert "](" not in body


@pytest.mark.asyncio
async def test_the_memo_is_still_written_to_the_sheet_intact(fake_world):
    """Only the message is neutralised. The ledger keeps what the bank sent —
    sanitising the stored record would destroy evidence."""
    _seed_account()

    await sepay.handle_sepay_webhook(_payload(sepay_id=9002, desc=PHISH))

    rows = _tx_rows()
    assert rows and PHISH in rows[0][5]


# ── a payload field that is not a string ─────────────────────────────────────

@pytest.mark.asyncio
async def test_a_numeric_description_does_not_crash_the_webhook(fake_world):
    """`.strip()` on an int raised AFTER the webhook was authenticated, so the
    sender retried the identical payload forever and the transaction was never
    written. Every neighbouring field is already coerced."""
    _seed_account()

    payload = _payload(sepay_id=9003)
    payload["description"] = 20260907

    await sepay.handle_sepay_webhook(payload)

    rows = _tx_rows()
    assert rows and "20260907" in rows[0][5]
