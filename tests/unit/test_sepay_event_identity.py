"""Event identity: SePay's own transaction id, and what may no longer be dropped.

Two coffees of the same price, on the same card, in the same minute are two
transactions. Before SePay's `id` became the identity they hashed to the same
reference and the second one was swallowed, and the fuzzy cross-source check
would have dropped it anyway. Both paths are covered here, along with the
upgrade window in which a retry can arrive carrying its new identity for a row
written under the old one.
"""
import pytest

import sheets as sh
from config import SHEETS as S
import handlers.sepay as sepay

from tests.unit.test_phase1_sepay_flow import (  # noqa: F401  (fixture import)
    fake_world,
    _seed_account,
)


def _now_str():
    """The stale-transaction guard rejects old dates, so tests live in the present.
    Captured once per test so two deliveries can carry the identical second."""
    from datetime import datetime
    import pytz
    return datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%dT%H:%M:%S")


def _tx_rows():
    """Written transaction rows, header excluded."""
    return sh._sheet(S.TRANSACTIONS).get_all_values()[1:]


def _payload(*, sepay_id=None, ref=None, amount=45000, desc="highland", when=None,
             account="1903999888", tx_type="out"):
    """A SePay payload. `sepay_id=None` reproduces a pre-upgrade delivery."""
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    payload = {
        "transferType": tx_type,
        "transferAmount": amount,
        "description": desc,
        "transactionDate": when or datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": "VND",
    }
    if sepay_id is not None:
        payload["id"] = sepay_id
    if ref is not None:
        payload["referenceCode"] = ref
    if account is not None:
        payload["accountNumber"] = account
    return payload


# ── the bug this slice exists to fix ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_two_distinct_ids_identical_in_every_other_way_are_both_written(fake_world):
    """The regression: same amount, same description, same second, no bank
    reference — the old content hash collided and the second spend vanished."""
    _seed_account()
    when = _now_str()

    await sepay.handle_sepay_webhook(_payload(sepay_id=1001, when=when))
    await sepay.handle_sepay_webhook(_payload(sepay_id=1002, when=when))

    rows = _tx_rows()
    assert len(rows) == 2, "a distinct provider id is a distinct transaction"
    assert [r[8] for r in rows] == ["sepay:1001", "sepay:1002"]


@pytest.mark.asyncio
async def test_same_id_delivered_ten_times_writes_one_row(fake_world):
    _seed_account()
    payload = _payload(sepay_id=2001, when=_now_str())
    for _ in range(10):
        await sepay.handle_sepay_webhook(dict(payload))

    assert len(_tx_rows()) == 1


@pytest.mark.asyncio
async def test_provider_id_wins_over_the_bank_reference(fake_world):
    """`referenceCode` is an external value with no uniqueness guarantee, so it
    must not decide identity when SePay supplied its own id."""
    _seed_account()
    when = _now_str()

    await sepay.handle_sepay_webhook(_payload(sepay_id=3001, ref="SHARED", when=when))
    await sepay.handle_sepay_webhook(_payload(sepay_id=3002, ref="SHARED", when=when))

    rows = _tx_rows()
    assert len(rows) == 2
    assert [r[8] for r in rows] == ["sepay:3001", "sepay:3002"]


# ── backward compatibility ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payload_without_an_id_still_uses_its_reference(fake_world):
    _seed_account()
    await sepay.handle_sepay_webhook(_payload(ref="FT24051200001"))

    rows = _tx_rows()
    assert len(rows) == 1
    assert rows[0][8] == "FT24051200001"


@pytest.mark.asyncio
async def test_retry_of_a_row_written_before_the_upgrade_is_not_written_again(fake_world):
    """The upgrade window: the row exists under its bank reference, and SePay
    retries the same transaction — now carrying the id the bot keys on."""
    _seed_account()
    when = _now_str()

    await sepay.handle_sepay_webhook(_payload(ref="FT99", when=when))          # pre-upgrade
    assert _tx_rows()[0][8] == "FT99"

    await sepay.handle_sepay_webhook(_payload(sepay_id=4001, ref="FT99", when=when))

    rows = _tx_rows()
    assert len(rows) == 1, "the same transaction must not be written under two identities"
    assert rows[0][8] == "FT99"


@pytest.mark.asyncio
async def test_the_legacy_lookup_can_be_retired(fake_world, monkeypatch):
    """Once the provider's retry window has passed the operator turns the
    transition lookup off, and only the new identity is consulted."""
    _seed_account()
    when = _now_str()
    await sepay.handle_sepay_webhook(_payload(ref="FT77", when=when))

    monkeypatch.setattr(sepay, "SEPAY_LEGACY_REF_LOOKUP", False)
    await sepay.handle_sepay_webhook(_payload(sepay_id=5001, ref="FT77", when=when))

    assert len(_tx_rows()) == 2


# ── the fuzzy check keeps its real job ───────────────────────────────────────

def test_fuzzy_dedup_ignores_a_row_from_the_same_source():
    """Same source, same everything: two transactions, not one."""
    assert sh.find_recent_duplicate(
        45000, "Tiền ra", _now_str(), source="sepay",
    ) is False


@pytest.mark.asyncio
async def test_fuzzy_dedup_still_pairs_the_same_spend_seen_on_two_sources(fake_world):
    """A card payment can arrive from SePay and again from the bank's email.
    Those carry unrelated identities, so only the fuzzy check can pair them."""
    _seed_account()
    _seed_account(account_id="cake_visa", source="email_cake:cake_cc", acc_type="credit")
    when = _now_str()

    await sepay.handle_sepay_webhook(_payload(sepay_id=6001, when=when))
    assert len(_tx_rows()) == 1

    email = _payload(when=when, account=None)
    email.pop("accountNumber", None)
    email["_source"] = "email_cake"
    email["_account_hint"] = "cake_cc"
    await sepay.handle_trusted_email_transaction(email)

    assert len(_tx_rows()) == 1, "the same spend seen twice stays one row"
