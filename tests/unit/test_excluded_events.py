"""Nothing financial is declined without a record.

An authenticated webhook that is acknowledged and then dropped with nothing but
a log line is money that vanished: no row, no total, no way to discover later
that it happened. Both remaining decline paths — the history boundary and the
cross-source duplicate — now leave a line in the Excluded Events tab.

The boundary itself also changes meaning here. Age was doing two jobs: keeping a
provider's first-registration history replay out, and standing in as replay
protection. The claim ledger owns the second job, so with INGESTION_START_AT set
a merely delayed transaction is recorded rather than thrown away.
"""
import pytest

import sheets as sh
from config import SHEETS as S
import handlers.sepay as sepay

from tests.unit.test_phase1_sepay_flow import (  # noqa: F401  (fixture import)
    fake_world,
    _seed_account,
)
from tests.unit.test_sepay_event_identity import _now_str, _payload, _tx_rows


def _excluded_rows():
    try:
        return sh._sheet(S.EXCLUDED_EVENTS).get_all_values()[1:]
    except Exception:
        return []


def _hours_ago(hours):
    from datetime import datetime, timedelta
    import pytz
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return (datetime.now(tz) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


# ── the history boundary ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_an_event_older_than_the_window_is_recorded_not_just_dropped(fake_world):
    _seed_account()
    await sepay.handle_sepay_webhook(_payload(sepay_id=7001, when=_hours_ago(6)))

    assert _tx_rows() == [], "it is still kept out of the transaction record"

    excluded = _excluded_rows()
    assert len(excluded) == 1, "but it is no longer invisible"
    assert excluded[0][3] == "sepay:7001"        # ref_code
    assert excluded[0][7] == "older_than_max_age"  # reason


@pytest.mark.asyncio
async def test_before_the_ingestion_start_is_excluded_with_that_reason(fake_world, monkeypatch):
    _seed_account()
    monkeypatch.setattr(sepay, "INGESTION_START_AT", "2026-09-01")

    await sepay.handle_sepay_webhook(_payload(sepay_id=7002, when="2026-08-15T09:00:00"))

    assert _tx_rows() == []
    excluded = _excluded_rows()
    assert len(excluded) == 1
    assert excluded[0][7] == "before_ingestion_start"


@pytest.mark.asyncio
async def test_a_delayed_transaction_after_the_start_is_recorded_not_discarded(fake_world, monkeypatch):
    """The behaviour change that matters: six hours late, well past the age
    window, but after the boundary — so it belongs in the record."""
    _seed_account()
    monkeypatch.setattr(sepay, "INGESTION_START_AT", "2026-01-01")

    await sepay.handle_sepay_webhook(_payload(sepay_id=7003, when=_hours_ago(6)))

    rows = _tx_rows()
    assert len(rows) == 1, "a late transaction is still a real transaction"
    assert rows[0][8] == "sepay:7003"
    assert _excluded_rows() == []


@pytest.mark.asyncio
async def test_a_misconfigured_boundary_does_not_exclude_everything(fake_world, monkeypatch):
    """An unparseable value must fall back to the age windows, never to
    'exclude every transaction'."""
    _seed_account()
    monkeypatch.setattr(sepay, "INGESTION_START_AT", "last tuesday")

    await sepay.handle_sepay_webhook(_payload(sepay_id=7004, when=_now_str()))

    assert len(_tx_rows()) == 1, "a fresh transaction still goes through"


# ── the cross-source duplicate ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_cross_source_duplicate_is_recorded_when_it_is_skipped(fake_world):
    _seed_account()
    _seed_account(account_id="cake_visa", source="email_cake:cake_cc", acc_type="credit")
    when = _now_str()

    await sepay.handle_sepay_webhook(_payload(sepay_id=7005, when=when))
    assert len(_tx_rows()) == 1

    email = _payload(when=when, account=None)
    email.pop("accountNumber", None)
    email["_source"] = "email_cake"
    email["_account_hint"] = "cake_cc"
    await sepay.handle_trusted_email_transaction(email)

    assert len(_tx_rows()) == 1, "still one row for one spend"
    excluded = _excluded_rows()
    assert len(excluded) == 1
    assert excluded[0][7] == "cross_source_duplicate"
    assert excluded[0][2] == "email"          # which source was declined


# ── the record is useful, not just present ───────────────────────────────────

@pytest.mark.asyncio
async def test_the_record_carries_enough_to_reconstruct_the_event(fake_world):
    _seed_account()
    when = _hours_ago(9)
    await sepay.handle_sepay_webhook(
        _payload(sepay_id=7006, amount=123456, desc="winmart q2", when=when))

    row = _excluded_rows()[0]
    assert row[0], "recorded_at"
    assert row[1].startswith(when[:10])       # occurred_at keeps the real date
    assert row[2] == "sepay"
    assert row[3] == "sepay:7006"
    assert str(row[4]) in ("123456", "123456.0")
    assert row[5] == "VND"
    assert row[6] == "Tiền ra"
    assert "winmart" in row[8]


@pytest.mark.asyncio
async def test_a_failing_ledger_never_blocks_the_response(fake_world, monkeypatch):
    """Recording is best-effort. If the tab cannot be written the bot still
    answers the provider — a bookkeeping failure must not become an outage."""
    _seed_account()

    def _boom(*a, **k):
        raise RuntimeError("sheets unavailable")

    monkeypatch.setattr(sh, "_ensure_excluded_events_tab", _boom)
    await sepay.handle_sepay_webhook(_payload(sepay_id=7007, when=_hours_ago(6)))

    assert _tx_rows() == []
