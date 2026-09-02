"""Cost and growth contract for the durable transaction reservation ledger.

The ledger sits on the synchronous webhook path, so its Google Sheets call count
is a correctness-adjacent property: every avoidable call is latency the sender
waits for and quota the next delivery no longer has.
"""

from datetime import datetime, timedelta, timezone

import pytest

import sheets as sh


def _instrument(ws) -> dict[str, int]:
    """Count the Sheets calls a worksheet receives."""
    counts = {"read": 0, "write": 0, "col_values": 0}
    real_get_all_values = ws.get_all_values
    real_update = ws.update
    real_col_values = ws.col_values

    def get_all_values():
        counts["read"] += 1
        return real_get_all_values()

    def update(*args, **kwargs):
        counts["write"] += 1
        return real_update(*args, **kwargs)

    def col_values(col):
        counts["col_values"] += 1
        return real_col_values(col)

    ws.get_all_values = get_all_values
    ws.update = update
    ws.col_values = col_values
    return counts


def _stamp(age_seconds: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()


@pytest.fixture
def ledger(fake_ss, monkeypatch):
    """A ledger tab with the Transactions lookup stubbed out."""
    monkeypatch.setattr(sh, "_ref_in_sheet", lambda _ref_code, **_kwargs: False)
    return sh._ensure_processed_refs_tab()


def test_a_claim_and_its_commit_cost_one_read_and_two_writes(ledger, fake_ss, monkeypatch):
    counts = _instrument(ledger)
    tab_lookups = {"n": 0}
    real_worksheet = fake_ss.worksheet

    def counted_worksheet(name: str):
        if name == sh.S.PROCESSED_REFS:
            tab_lookups["n"] += 1
        return real_worksheet(name)

    monkeypatch.setattr(fake_ss, "worksheet", counted_worksheet)

    assert sh.tx_exists("ref-1") is False
    sh.mark_ref_committed("ref-1")

    # One authoritative read to claim, one write to reserve, one to settle.
    assert counts["read"] == 1
    assert counts["write"] == 2
    # The next free row comes from the index built by that read.
    assert counts["col_values"] == 0
    # The worksheet handle is resolved once and then held.
    assert tab_lookups["n"] == 0


def test_a_repeat_delivery_of_a_committed_reference_costs_nothing(ledger):
    assert sh.tx_exists("ref-2") is False
    sh.mark_ref_committed("ref-2")
    counts = _instrument(ledger)

    assert sh.tx_exists("ref-2") is True

    assert counts == {"read": 0, "write": 0, "col_values": 0}


def test_settled_rows_are_recycled_after_the_retention_window(ledger):
    ledger.update(
        "A2:C4",
        [
            ["old-committed", "committed", _stamp(sh.PROCESSED_REF_RETENTION_SECONDS + 60)],
            ["recent-committed", "committed", _stamp()],
            ["active-claim", "processing", _stamp()],
        ],
    )
    sh._reset_processed_ref_cache()
    sh._processed_refs.clear()

    assert sh.tx_exists("brand-new") is False

    rows = ledger.get_all_values()
    assert len(rows) == 4, "the expired row should be reused, not appended past"
    assert rows[1][0] == "brand-new"
    assert [row[0] for row in rows[2:]] == ["recent-committed", "active-claim"]


def test_settled_rows_inside_the_retention_window_are_preserved(ledger):
    ledger.update("A2:C2", [["recent-committed", "committed", _stamp()]])
    sh._reset_processed_ref_cache()
    sh._processed_refs.clear()

    assert sh.tx_exists("brand-new") is False

    rows = ledger.get_all_values()
    assert [row[0] for row in rows[1:]] == ["recent-committed", "brand-new"]


def test_an_unsettled_claim_is_never_recycled(ledger):
    ledger.update(
        "A2:C2",
        [["stuck-claim", "processing", _stamp(sh.PROCESSED_REF_RETENTION_SECONDS * 10)]],
    )
    sh._reset_processed_ref_cache()
    sh._processed_refs.clear()

    assert sh.tx_exists("brand-new") is False

    rows = ledger.get_all_values()
    assert [row[0] for row in rows[1:]] == ["stuck-claim", "brand-new"]


def test_a_failed_ledger_write_drops_the_cached_handle_and_index(ledger, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("sheets unavailable")

    monkeypatch.setattr(ledger, "update", unavailable)

    with pytest.raises(sh.RetryableTransactionClaimError):
        sh.tx_exists("ref-3")

    assert sh._processed_refs_ws is None
    assert sh._processed_ref_index == {}


def test_a_failed_ledger_read_drops_the_cached_handle_and_index(ledger, monkeypatch):
    def unavailable():
        raise RuntimeError("sheets unavailable")

    monkeypatch.setattr(ledger, "get_all_values", unavailable)

    with pytest.raises(sh.RetryableTransactionClaimError):
        sh.tx_exists("ref-4")

    assert sh._processed_refs_ws is None
    assert sh._processed_ref_index == {}


def test_commit_reindexes_when_the_claim_state_was_lost(ledger):
    assert sh.tx_exists("ref-lost") is False
    # A restarted worker settles a claim it no longer has in memory.
    sh._reset_processed_ref_cache()
    sh._processed_refs.clear()

    sh.mark_ref_committed("ref-lost")

    rows = [row for row in ledger.get_all_values()[1:] if row[0] == "ref-lost"]
    assert len(rows) == 1, "the reference must not gain a second ledger row"
    assert rows[0][1] == "committed"


def test_failure_marker_reuses_the_claim_row(ledger):
    assert sh.tx_exists("ref-failed") is False
    counts = _instrument(ledger)

    sh.mark_ref_failed("ref-failed")

    assert counts["read"] == 0
    assert counts["write"] == 1
    rows = [row for row in ledger.get_all_values()[1:] if row[0] == "ref-failed"]
    assert len(rows) == 1
    assert rows[0][1] == "failed"
