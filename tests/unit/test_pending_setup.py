"""Pending Accounts persistence — verifies setup survives state-overwriting tx.

This is the regression test for the bug observed in production: SePay sent an
unmapped account, bot prompted "Setup?", but the next transaction arrived
moments later, overwrote BOT_STATE with its own category-picker step, and
when the user finally tapped Setup → "⚠️ Hết phiên setup".

Fix (combined option B + C from review): persist pending rows in a dedicated
sheet keyed by `setup_key = md5(source_key)[:12]`, embed that key in
callback_data so taps always know which pending row to load. 24h TTL.
"""
import json
from datetime import datetime, timedelta

import pytest

import sheets as sh
from config import SHEETS as S


def _ensure_pending_tab(fake_ss):
    """Force Pending Accounts tab into existence via the helper."""
    sh._ensure_pending_accounts_tab()


def test_setup_key_is_deterministic_and_12_hex():
    k1 = sh._compute_setup_key("sepay:1903999888")
    k2 = sh._compute_setup_key("sepay:1903999888")
    assert k1 == k2
    assert len(k1) == 12
    assert all(c in "0123456789abcdef" for c in k1)


def test_setup_key_differs_per_source_key():
    a = sh._compute_setup_key("sepay:1903999888")
    b = sh._compute_setup_key("sepay:1903999889")
    c = sh._compute_setup_key("email_cake:cake_cc")
    assert len({a, b, c}) == 3


def test_add_pending_writes_row(fake_ss):
    _ensure_pending_tab(fake_ss)
    setup_key = sh.add_pending_account(
        source_key="sepay:1900123456",
        identifier="1900123456",
        tx_row_num=42,
    )
    assert setup_key
    ws = sh._sheet(S.PENDING_ACCOUNTS)
    rows = ws.get_all_values()
    # header + 1 row
    assert len(rows) == 2
    assert rows[1][0] == setup_key
    assert rows[1][1] == "sepay:1900123456"
    assert rows[1][2] == "1900123456"
    assert rows[1][3] == "42"
    assert rows[1][4] == "pending"


def test_add_pending_idempotent_for_same_source_key(fake_ss):
    """Duplicate webhook delivery should not enqueue a second prompt."""
    _ensure_pending_tab(fake_ss)
    k1 = sh.add_pending_account("sepay:1234", "1234", tx_row_num=10)
    k2 = sh.add_pending_account("sepay:1234", "1234", tx_row_num=11)
    assert k1 == k2
    rows = sh._sheet(S.PENDING_ACCOUNTS).get_all_values()
    assert len(rows) == 2  # header + 1 row only


def test_get_pending_returns_entry_while_pending(fake_ss):
    _ensure_pending_tab(fake_ss)
    setup_key = sh.add_pending_account("sepay:5555", "5555", tx_row_num=7)
    entry = sh.get_pending_by_setup_key(setup_key)
    assert entry is not None
    assert entry["status"] == "pending"
    assert entry["source_key"] == "sepay:5555"
    assert entry["identifier"] == "5555"
    assert entry["tx_row_num"] == 7


def test_get_pending_returns_none_for_unknown_key(fake_ss):
    _ensure_pending_tab(fake_ss)
    assert sh.get_pending_by_setup_key("000000000000") is None


def test_pending_persists_across_many_state_overwrites(fake_ss):
    """Core regression: many tx land between prompt and tap — setup still valid."""
    _ensure_pending_tab(fake_ss)
    # Also need bot_state tab so set_state/clear_state work
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "ts"]])

    setup_key = sh.add_pending_account("sepay:9999", "9999", tx_row_num=1)

    # Simulate 10 subsequent transactions, each overwriting BOT_STATE
    for i in range(10):
        sh.set_state("0", {"step": "await_parent", "row_num": i + 2})
    # State now has no `pending_source_key`. Old bug: would have lost prompt context.

    entry = sh.get_pending_by_setup_key(setup_key)
    assert entry is not None
    assert entry["status"] == "pending"
    assert entry["source_key"] == "sepay:9999"


def test_mark_completed_makes_get_return_none(fake_ss):
    _ensure_pending_tab(fake_ss)
    setup_key = sh.add_pending_account("sepay:7777", "7777", tx_row_num=3)
    assert sh.mark_pending_completed(setup_key) is True
    assert sh.get_pending_by_setup_key(setup_key) is None  # no longer pending


def test_mark_skipped_makes_get_return_none(fake_ss):
    _ensure_pending_tab(fake_ss)
    setup_key = sh.add_pending_account("sepay:8888", "8888", tx_row_num=4)
    assert sh.mark_pending_skipped(setup_key) is True
    assert sh.get_pending_by_setup_key(setup_key) is None


def test_expired_pending_returns_none(fake_ss):
    """Pending row older than TTL → get returns None and side-effect marks it."""
    _ensure_pending_tab(fake_ss)
    setup_key = sh.add_pending_account("sepay:6666", "6666", tx_row_num=5)

    # Backdate created_at by 25 hours
    ws = sh._sheet(S.PENDING_ACCOUNTS)
    old_ts = (datetime.utcnow() - timedelta(hours=25)).isoformat()
    ws.update_cell(2, 6, old_ts)  # col F = created_at

    entry = sh.get_pending_by_setup_key(setup_key)
    assert entry is None

    # The row should now be marked expired
    rows = ws.get_all_values()
    assert rows[1][4] == "expired"


def test_stale_pending_row_is_flipped_and_new_row_appended(fake_ss):
    """Regression for production bug: pending row sat 12 days without any
    lookup touching it. status was still 'pending' but TTL long exceeded.
    A new tx for the same source arrived; add_pending_account naively reused
    the stale-pending row → returned same setup_key → user got prompt →
    tapped Setup → lookup expired the row → "đã hết hạn".

    Fix: add_pending_account itself must TTL-check the existing pending row.
    If stale, flip to expired and append a fresh row.
    """
    _ensure_pending_tab(fake_ss)

    # Day -12: prompt sent, row pending, user never tapped
    setup_key = sh.add_pending_account("sepay:1900123456", "1900123456", tx_row_num=1)

    # Backdate created_at to 12 days ago (way past 24h TTL)
    ws = sh._sheet(S.PENDING_ACCOUNTS)
    old_ts = (datetime.utcnow() - timedelta(days=12)).isoformat()
    ws.update_cell(2, 6, old_ts)

    # Sanity: row exists, status=pending, but stale
    rows = ws.get_all_values()
    assert rows[1][0] == setup_key
    assert rows[1][4] == "pending"

    # Today: new tx for same source → add_pending_account must NOT reuse
    setup_key_2 = sh.add_pending_account("sepay:1900123456", "1900123456", tx_row_num=99)
    assert setup_key_2 == setup_key  # md5 deterministic

    # Sheet now: old row flipped to expired + new pending row appended
    rows = ws.get_all_values()
    assert len(rows) == 3  # header + 2 data rows
    assert rows[1][4] == "expired"   # old row flipped
    assert rows[1][6] != ""          # completed_at filled when flipped
    assert rows[2][4] == "pending"   # new row pending
    assert rows[2][3] == "99"        # new tx_row_num
    # created_at on the new row must be recent (not the backdated 12-day one)
    new_created = datetime.fromisoformat(rows[2][5])
    assert (datetime.utcnow() - new_created).total_seconds() < 10

    # User taps Setup right after — must succeed
    entry = sh.get_pending_by_setup_key(setup_key)
    assert entry is not None, "stale-pending was reused; lookup expired the new prompt"
    assert entry["status"] == "pending"
    assert entry["tx_row_num"] == 99


def test_skipped_row_does_not_shadow_new_pending_row(fake_ss):
    """Regression: setup_key collision is by design (md5(source_key)). When a
    previous prompt for the same source was skipped, a later email re-triggers
    `add_pending_account`, which appends a NEW `pending` row with the SAME
    setup_key. `get_pending_by_setup_key` must skip past the old `skipped` row
    and return the new `pending` one — otherwise the user sees
    "Phiên setup đã hết hạn hoặc đã hoàn tất" forever.
    """
    _ensure_pending_tab(fake_ss)

    # Round 1: user skipped earlier prompt
    setup_key = sh.add_pending_account("email_cake:cake_cc", "cake_cc", tx_row_num=1)
    assert sh.mark_pending_skipped(setup_key) is True
    assert sh.get_pending_by_setup_key(setup_key) is None  # skipped → None

    # Round 2: new tx for the same source → resolver still says new_identifier
    # → add_pending_account appends a fresh pending row (idempotency check
    # requires status="pending", which the skipped row no longer satisfies).
    setup_key_2 = sh.add_pending_account("email_cake:cake_cc", "cake_cc", tx_row_num=2)
    assert setup_key_2 == setup_key  # md5 is deterministic

    # Sheet now has 2 rows with same setup_key — one skipped, one pending
    rows = sh._sheet(S.PENDING_ACCOUNTS).get_all_values()
    assert len(rows) == 3  # header + 2 rows
    statuses = [r[4] for r in rows[1:]]
    assert sorted(statuses) == ["pending", "skipped"]

    # Lookup MUST return the pending one, not None
    entry = sh.get_pending_by_setup_key(setup_key)
    assert entry is not None, "stale skipped row shadowed the new pending row"
    assert entry["status"] == "pending"
    assert entry["tx_row_num"] == 2  # the new row, not the old one


def test_expired_row_does_not_shadow_new_pending_row(fake_ss):
    """Same shadowing scenario but the stale row is expired (24h+ old)."""
    _ensure_pending_tab(fake_ss)

    # Round 1: prompt arrives, user ignores, TTL elapses
    setup_key = sh.add_pending_account("sepay:1903888777", "1903888777", tx_row_num=1)
    ws = sh._sheet(S.PENDING_ACCOUNTS)
    old_ts = (datetime.utcnow() - timedelta(hours=25)).isoformat()
    ws.update_cell(2, 6, old_ts)  # col F = created_at

    # First lookup observes the expired row and side-effects status=expired
    assert sh.get_pending_by_setup_key(setup_key) is None
    rows = ws.get_all_values()
    assert rows[1][4] == "expired"

    # Round 2: new tx for same source → fresh pending row appended
    setup_key_2 = sh.add_pending_account("sepay:1903888777", "1903888777", tx_row_num=2)
    assert setup_key_2 == setup_key

    rows = ws.get_all_values()
    assert len(rows) == 3
    statuses = [r[4] for r in rows[1:]]
    assert sorted(statuses) == ["expired", "pending"]

    # Lookup must skip past the expired row and return the fresh pending one
    entry = sh.get_pending_by_setup_key(setup_key)
    assert entry is not None, "stale expired row shadowed the new pending row"
    assert entry["status"] == "pending"
    assert entry["tx_row_num"] == 2


def test_pending_works_for_all_account_types(fake_ss):
    """Bank, debit, credit, cash — pending queue is type-agnostic; type is
    chosen later in the wizard. Verify add+get works regardless."""
    _ensure_pending_tab(fake_ss)
    cases = [
        ("sepay:bank1903", "bank1903"),       # → user will pick bank
        ("sepay:debit5555", "debit5555"),      # → user will pick debit
        ("email_cake:cake_cc", "cake_cc"),     # → user will pick credit
        ("manual:cash1", "cash1"),             # → user will pick cash
    ]
    keys = [sh.add_pending_account(sk, ident, tx_row_num=i + 1)
            for i, (sk, ident) in enumerate(cases)]
    assert len(set(keys)) == 4   # all distinct
    for k in keys:
        assert sh.get_pending_by_setup_key(k) is not None


@pytest.mark.asyncio
async def test_prompt_new_account_writes_sheet_not_state(fake_ss, monkeypatch):
    """End-to-end: prompt_new_account must persist to sheet, NOT depend on
    BOT_STATE for the setup_key. The callback_data must carry the key."""
    _ensure_pending_tab(fake_ss)
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "ts"]])

    captured = {}

    async def fake_send(msg, buttons):
        captured["msg"] = msg
        captured["buttons"] = buttons
        return {"ok": True, "result": {"message_id": 1}}

    import telegram_api as tg
    monkeypatch.setattr(tg, "send_with_buttons", fake_send)

    from handlers.accounts import prompt_new_account
    await prompt_new_account("sepay:1900123456", "1900123456", tx_row_num=2)

    # Sheet has the row
    rows = sh._sheet(S.PENDING_ACCOUNTS).get_all_values()
    assert len(rows) == 2
    setup_key = rows[1][0]

    # Buttons carry the setup_key
    cb_data = [b["callback_data"] for row in captured["buttons"] for b in row]
    assert f"acc_setup_{setup_key}" in cb_data
    assert f"acc_skip_{setup_key}" in cb_data

    # State should NOT have pending_source_key (that only loads after user
    # taps Setup — the whole point is setup_key lives in the sheet, not state)
    state = sh.get_state("0") or {}
    assert "pending_source_key" not in state
