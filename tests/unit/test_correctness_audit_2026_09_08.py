"""Guards for the 2026-09-08 audit's correctness findings.

Every one of these fails silently in production: no exception, no warning,
just a missing transaction or a confirmation quoting the wrong number.
"""
from datetime import datetime, timedelta, timezone

import pytest

import sheets as sh
from config import SHEETS as S

TZ = timezone(timedelta(hours=7))


def _tx_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
        "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed", "Month",
        "Currency", "account_id", "tx_type", "linked_tx_row", "ledger_applied",
        "account_source_key",
    ]])
    return ws


def _write(when, amount, source_key="", tx_type="Tiền ra"):
    return sh.append_transaction(
        when.strftime("%Y-%m-%dT%H:%M:%S"), "SHOP", amount,
        f"REF{when.strftime('%H%M%S')}", "2026-09",
        tx_type=tx_type, account_source_key=source_key,
    )


# ─── An unknown source is not a match ────────────────────────────

def test_a_row_with_no_source_key_never_pairs_as_a_duplicate(fake_ss):
    """/transfer, /cc pay and both cc-payment writers leave column U empty,
    and the resolver leaves it empty whenever a payload carries no account
    identifier. Pairing against those swallowed real, distinct spends."""
    _tx_tab(fake_ss)
    when = datetime.now(TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    _write(when, 200_000, source_key="")          # e.g. a manual /transfer leg

    seventy_seconds_later = (when + timedelta(seconds=70)).isoformat()
    assert sh.find_recent_duplicate(
        200_000, "Tiền ra", seventy_seconds_later, source="sepay") is False


def test_a_caller_that_names_no_source_never_pairs(fake_ss):
    _tx_tab(fake_ss)
    when = datetime.now(TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    _write(when, 200_000, source_key="email_cake:cake_cc")
    assert sh.find_recent_duplicate(
        200_000, "Tiền ra", (when + timedelta(seconds=30)).isoformat()) is False


def test_two_known_and_different_sources_still_pair(fake_ss):
    """The feature itself: one spend delivered by both SePay and the bank's
    notification email is one transaction."""
    _tx_tab(fake_ss)
    when = datetime.now(TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    _write(when, 200_000, source_key="email_cake:cake_cc")
    assert sh.find_recent_duplicate(
        200_000, "Tiền ra", (when + timedelta(seconds=30)).isoformat(),
        source="sepay") is True


def test_two_events_from_the_same_source_are_two_transactions(fake_ss):
    """Two coffees of the same price on the same card in the same minute."""
    _tx_tab(fake_ss)
    when = datetime.now(TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    _write(when, 45_000, source_key="sepay:1903999888")
    assert sh.find_recent_duplicate(
        45_000, "Tiền ra", (when + timedelta(seconds=40)).isoformat(),
        source="sepay") is False


def test_the_dedup_guard_matches_its_docstring():
    """The code said the opposite of the docstring above it for long enough
    that only a test keeps them together."""
    src = open("sheets.py", encoding="utf-8").read()
    assert "if not new_source or not row_source or row_source == new_source:" in src


# ─── The mid-flow guard cannot rot ───────────────────────────────

def test_every_telegram_text_step_is_protected_from_a_webhook():
    """The allow-list this replaces was written before /manage grew an
    editable daily cap, and 'await_manage_daily_cap' was never added — so a
    webhook arriving while the user typed a cap threw the flow away. A
    deny-list protects a new step the day it is added."""
    import re
    main_src = open("main.py", encoding="utf-8").read()
    sepay_src = open("handlers/sepay.py", encoding="utf-8").read()

    router_steps = {
        s for s in re.findall(r'(?:if|elif) step == "([a-z_]+)"', main_src)
        if not s.startswith("zalo")
    }
    assert "await_manage_daily_cap" in router_steps, "test is looking at the wrong router"

    replaceable = set(re.findall(
        r'_REPLACEABLE_STEPS = \((.*?)\)', sepay_src, re.S)[0].replace('"', '').split(","))
    replaceable = {s.strip() for s in replaceable if s.strip()}

    # A text step must never be replaceable; only the pickers may be.
    assert not (router_steps & replaceable), \
        f"a text-input step is treated as replaceable: {router_steps & replaceable}"
    assert replaceable == {"await_parent", "await_sub"}


def test_a_live_picker_is_queued_behind_not_overwritten():
    """_finalize reads amount, currency and date from the state, so replacing
    it under a live picker made the old buttons log the right category against
    the new transaction's amount."""
    src = open("handlers/sepay.py", encoding="utf-8").read()
    assert "if existing_step:" in src
    assert "_CRITICAL_STEPS" not in src, "the rotting allow-list is back"


def test_finalize_falls_back_to_the_sheet_on_a_mismatched_state():
    src = open("handlers/transaction.py", encoding="utf-8").read()
    assert "int(state_row) != int(row_num)" in src


# ─── Cancelled rows are not money an account holds ───────────────

def test_assign_preview_skips_cancelled_rows():
    for path in ("handlers/accounts.py", "main.py"):
        src = open(path, encoding="utf-8").read()
        assert "is_cancelled(r)" in src or "is_cancelled(row)" in src, \
            f"{path}: /accounts assign preview counts cancelled rows"


# ─── One amount parser, the tested one ───────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("500,000 VND", 500_000),
    ("-50.000đ", 50_000),
    ("1.234.567 VND", 1_234_567),
    ("1.234.567,89", 1_234_567.89),   # returned 0.0 — a 0đ row vanishes silently
    ("2.500.000,50", 2_500_000.50),
    ("50,000.25", 50_000.25),
])
def test_email_amount_parser_handles_decimals(text, expected):
    from handlers.email_parser import _parse_amount_str
    assert _parse_amount_str(text) == pytest.approx(expected)


def test_email_amount_parser_returns_zero_only_for_real_garbage():
    from handlers.email_parser import _parse_amount_str
    assert _parse_amount_str("no digits here") == 0.0
