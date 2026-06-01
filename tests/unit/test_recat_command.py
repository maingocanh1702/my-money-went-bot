"""tests/unit/test_recat_command.py

TDD for:
  1. /recat slash command (via main._handle_command)
  2. handle_recategorize button-path month fix (row[14] instead of now())
  3. Fix 1: reject transfer/cc_payment rows (would void ledger)
  4. Fix 2: carry tx month through finalize + new-category path

Cases:
  1. /recat with no arg / non-numeric → usage hint, no state
  2. /recat <row> not found → error message
  3. /recat <income row> → polite skip, no reset
  4. /recat <expense row> → reset + state set + bucket buttons
  5. /recat <old-month row> → buckets for row's month, not current month
  6. /recat <row> whose month has NO active buckets → warning, no reset
  7. handle_recategorize (button path) with old-month row → uses row[14]
  8. /recat <transfer row> → rejection message, no reset (Fix 1)
  9. /recat <cc_payment row> → rejection message, no reset (Fix 1)
 10. handle_recategorize button path rejects transfer rows (Fix 1)
 11. _finalize uses state["month_key"] not datetime.now() (Fix 2)
 12. handle_inline_new_cat_name uses state["month_key"] (Fix 2)
"""
import pytest
from freezegun import freeze_time
import sheets as sh
from config import SHEETS as S, CHAT_ID, DAILY_BUCKET_ID
import telegram_api as tg
import main
from handlers.transaction import (
    handle_recategorize,
    handle_parent_selected,
    handle_inline_new_cat_name,
)


# ─── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
def world(monkeypatch, fake_ss):
    """Minimal sheet world + tg call recorder for /recat tests."""
    # Transactions sheet with header
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:P1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
    ]])

    # Budget Config: current-month buckets + one old-month bucket
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:F1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active"]])
    ws_bc.update("A2:F2", [["2026-05", "food", "🍜 Food", 0, "", "TRUE"]])
    ws_bc.update("A3:F3", [["2026-05", "transport", "🚌 Transport", 0, "", "TRUE"]])
    ws_bc.update("A4:F4", [["2025-11", "old_cat", "🏷 OldCat", 0, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    # Bot State sheet (needed by set_state / get_state)
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    # Record all tg calls
    calls = {"texts": [], "buttons": [], "edits": []}

    async def _text(text, *a, **k):
        calls["texts"].append(text)
        return {"ok": True, "result": {"message_id": 99}}

    async def _buttons(text, btns, *a, **k):
        calls["buttons"].append({"text": text, "buttons": btns})
        return {"ok": True, "result": {"message_id": 99}}

    async def _edit(msg_id, text, *a, **k):
        calls["edits"].append({"msg_id": msg_id, "text": text})
        return {"ok": True}

    monkeypatch.setattr(tg, "send_text", _text)
    monkeypatch.setattr(tg, "send_with_buttons", _buttons)
    monkeypatch.setattr(tg, "edit_message", _edit)

    return calls, ws_tx


def _seed_row(ws_tx, row_num, *, direction="Tiền ra", month="2026-05",
              desc="Grab food", amount="75000", confirmed="FALSE", parent="",
              ledger_type=""):
    """Seed one transaction row at 1-indexed row_num.

    Column layout A–R mirrors append_transaction schema:
      A=ID, B=Date, C-E=blank, F=Desc, G=Type, H=Amount, I=Ref, J=Cumulative,
      K=ParentCat, L=SubCat, M=IsDaily, N=Confirmed, O=Month, P=Currency,
      Q=account_id, R=ledger_tx_type
    """
    ws_tx.update(f"A{row_num}:R{row_num}", [[
        "", "2026-05-15", "", "", "",
        desc, direction, amount,
        "REF01", "0", parent, "", "FALSE", confirmed,
        month, "VND",
        "",           # Q=account_id
        ledger_type,  # R=ledger_tx_type
    ]])
    # Invalidate short-lived tx cache so the row is visible immediately
    sh._tx_rows_cache.update({"ts": 0.0, "rows": None})


# ─── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_no_arg_sends_usage(world):
    calls, _ = world
    await main._handle_command("/recat")
    assert any("Usage" in t and "recat" in t for t in calls["texts"]), (
        f"Expected usage hint, got: {calls['texts']}"
    )
    assert not calls["buttons"], "No buttons expected for bad usage"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_nonnumeric_arg_sends_usage(world):
    calls, _ = world
    await main._handle_command("/recat abc")
    assert any("Usage" in t and "recat" in t for t in calls["texts"]), (
        f"Expected usage hint, got: {calls['texts']}"
    )
    assert not calls["buttons"], "No buttons expected for bad usage"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_missing_row_sends_error(world):
    calls, _ = world
    # Row 999 not seeded → row_values(999) returns []
    await main._handle_command("/recat 999")
    assert any("999" in t for t in calls["texts"]), (
        f"Expected not-found message with row number, got: {calls['texts']}"
    )
    assert not calls["buttons"]


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_income_row_skips_without_reset(world):
    """Income row → polite skip message; reset_transaction_row NOT called."""
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền vào", month="2026-05",
              parent="food", confirmed="TRUE")
    await main._handle_command("/recat 2")
    assert any("income" in t.lower() or "không cần" in t.lower()
               for t in calls["texts"]), (
        f"Expected income-skip message, got: {calls['texts']}"
    )
    assert not calls["buttons"]
    # Confirm reset was NOT called: parent and confirmed must be unchanged
    row = sh.get_transaction_row(2)
    assert row[10] == "food", f"K=ParentCat should be untouched, got: {row[10]!r}"
    assert row[13] == "TRUE", f"N=Confirmed should be untouched, got: {row[13]!r}"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_expense_row_resets_state_and_shows_buttons(world):
    """Expense row → reset_transaction_row called, state set, bucket picker shown."""
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2026-05",
              parent="food", confirmed="TRUE")
    await main._handle_command("/recat 2")
    # Bucket picker must be sent
    assert calls["buttons"], "Expected send_with_buttons call"
    all_cd = [
        btn["callback_data"]
        for row in calls["buttons"][0]["buttons"]
        for btn in row
        if "callback_data" in btn
    ]
    assert any("p_2_food" in cd or "p_2_transport" in cd for cd in all_cd), (
        f"Expected current-month bucket buttons, got: {all_cd}"
    )
    # State must be set
    state = sh.get_state(CHAT_ID)
    assert state is not None and state.get("step") == "await_parent"
    assert state.get("row_num") == 2
    # Row must be reset (K and N cleared)
    row = sh.get_transaction_row(2)
    assert row[10] == "", f"K=ParentCat should be cleared, got: {row[10]!r}"
    assert row[13] == "FALSE", f"N=Confirmed should be cleared, got: {row[13]!r}"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_old_month_row_uses_rows_own_month(world):
    """Row with old month in col O → buckets fetched for row's month, not now()."""
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    await main._handle_command("/recat 2")
    assert calls["buttons"], "Expected send_with_buttons call"
    all_cd = [
        btn["callback_data"]
        for row in calls["buttons"][0]["buttons"]
        for btn in row
        if "callback_data" in btn
    ]
    # Must show 2025-11 bucket (old_cat), NOT current-month buckets (food/transport)
    assert any("old_cat" in cd for cd in all_cd), (
        f"Expected old_cat from row's month (2025-11), got: {all_cd}"
    )
    assert not any("food" in cd or "transport" in cd for cd in all_cd), (
        f"Should NOT show 2026-05 buckets, got: {all_cd}"
    )


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_no_active_buckets_warns_and_skips_reset(world):
    """Row month with NO active buckets → warning sent, reset NOT called."""
    calls, ws_tx = world
    # Month "2020-01" has no buckets in Budget Config
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2020-01",
              parent="food", confirmed="TRUE")
    await main._handle_command("/recat 2")
    assert calls["texts"], "Expected a warning text"
    assert any("category" in t.lower() or "active" in t.lower()
               for t in calls["texts"]), (
        f"Expected no-category warning, got: {calls['texts']}"
    )
    assert not calls["buttons"], "No buttons expected when no buckets"
    # Row must NOT be reset
    row = sh.get_transaction_row(2)
    assert row[10] == "food", f"K=ParentCat must be untouched, got: {row[10]!r}"
    assert row[13] == "TRUE", f"N=Confirmed must be untouched, got: {row[13]!r}"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_handle_recategorize_button_uses_rows_own_month(world):
    """Button-path: handle_recategorize uses row[14] for bucket lookup.

    This test FAILS before the Step 4 fix in handlers/transaction.py
    (current code uses datetime.now() instead of row[14]).
    """
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11",
              parent="food", confirmed="TRUE")
    await handle_recategorize(["recat", "2"], 100)
    assert calls["buttons"], "Expected send_with_buttons call from button path"
    all_cd = [
        btn["callback_data"]
        for row in calls["buttons"][0]["buttons"]
        for btn in row
        if "callback_data" in btn
    ]
    # Must use row's own month (2025-11 → old_cat), NOT now() month (2026-05 → food/transport)
    assert any("old_cat" in cd for cd in all_cd), (
        f"Expected old_cat from row's month (2025-11), got: {all_cd}"
    )
    assert not any("food" in cd or "transport" in cd for cd in all_cd), (
        f"Should NOT show current-month (2026-05) buckets, got: {all_cd}"
    )


# ─── Fix 1: transfer/cc_payment rejection ───────────────────────────────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_transfer_row_rejected(world):
    """/recat on a transfer row → rejection msg, no reset, no buttons (Fix 1)."""
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2026-05",
              parent="food", confirmed="TRUE", ledger_type="transfer")
    await main._handle_command("/recat 2")
    assert calls["texts"], "Expected rejection message"
    assert any("chuyển khoản" in t.lower() or "transfer" in t.lower() or "ledger" in t.lower()
               for t in calls["texts"]), (
        f"Expected transfer-rejection message, got: {calls['texts']}"
    )
    assert not calls["buttons"], "No buttons expected for transfer row"
    row = sh.get_transaction_row(2)
    assert row[10] == "food", f"K=ParentCat must not be reset, got: {row[10]!r}"
    assert row[13] == "TRUE", f"N=Confirmed must not be reset, got: {row[13]!r}"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_cc_payment_row_rejected(world):
    """/recat on a cc_payment row → rejection msg, no reset, no buttons (Fix 1)."""
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2026-05",
              parent="food", confirmed="TRUE", ledger_type="cc_payment")
    await main._handle_command("/recat 2")
    assert calls["texts"], "Expected rejection message"
    assert any("trả thẻ" in t.lower() or "cc_payment" in t.lower() or "ledger" in t.lower()
               for t in calls["texts"]), (
        f"Expected cc_payment-rejection message, got: {calls['texts']}"
    )
    assert not calls["buttons"], "No buttons expected for cc_payment row"
    row = sh.get_transaction_row(2)
    assert row[10] == "food", f"K=ParentCat must not be reset, got: {row[10]!r}"
    assert row[13] == "TRUE", f"N=Confirmed must not be reset, got: {row[13]!r}"


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_handle_recategorize_transfer_row_rejected(world):
    """Button path rejects transfer row BEFORE reset_transaction_row (Fix 1)."""
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2026-05",
              parent="old_cat", confirmed="TRUE", ledger_type="transfer")
    await handle_recategorize(["recat", "2"], 100)
    # Any message must be sent (text or edit)
    assert calls["texts"] or calls["edits"], "Expected rejection feedback to user"
    # Row must NOT be reset: parent and confirmed unchanged
    row = sh.get_transaction_row(2)
    assert row[10] == "old_cat", f"K=ParentCat must not be reset, got: {row[10]!r}"
    assert row[13] == "TRUE", f"N=Confirmed must not be reset, got: {row[13]!r}"


# ─── Fix 2: month_key threading through state ────────────────────────────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_finalize_uses_state_month_key(world, monkeypatch):
    """_finalize uses state['month_key'] for bucket_status, not datetime.now() (Fix 2).

    FAILS before fix because _finalize ignores state['month_key'] and uses
    fmt_month(tx_date) which falls back to now() → '2026-05'.
    """
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    # Manually pre-seed state as if _cmd_recat/handle_recategorize set it with month_key
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Grab food",
        "month_key": "2025-11",  # this is what Fix 2 adds to set_state calls
    })

    # Spy on get_bucket_status to capture which month is queried
    bucket_status_months = []

    def _spy_bucket_status(bucket_id, month_key):
        bucket_status_months.append(month_key)
        return {"spent": 0, "allocated": 0, "remaining": 0, "foreign": {}}

    monkeypatch.setattr(sh, "get_bucket_status", _spy_bucket_status)
    monkeypatch.setattr(sh, "get_sub_categories", lambda bid: [])
    monkeypatch.setattr(sh, "bucket_label", lambda bid: bid)

    await handle_parent_selected(["p", "2", "old_cat"], 100)

    assert "2025-11" in bucket_status_months, (
        f"_finalize must use state['month_key']='2025-11', got: {bucket_status_months}"
    )
    assert "2026-05" not in bucket_status_months, (
        f"_finalize must NOT fall back to current month 2026-05, got: {bucket_status_months}"
    )


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_inline_new_cat_uses_state_month_key(world, monkeypatch):
    """handle_inline_new_cat_name uses state['month_key'] for write_budget_row (Fix 2).

    FAILS before fix because handle_inline_new_cat_name ignores state['month_key']
    and uses fmt_month(datetime.now()) → '2026-05'.
    """
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    # Pre-seed state as if /recat 2 + "➕ New category" button were tapped
    sh.set_state(CHAT_ID, {
        "step": "await_inline_new_cat_name", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Grab food",
        "month_key": "2025-11",   # Fix 2 propagates this through handle_parent_selected
        "message_id": 100,
    })

    write_budget_months = []

    def _spy_write_budget(month_key, bucket):
        write_budget_months.append(month_key)

    monkeypatch.setattr(sh, "write_budget_row", _spy_write_budget)
    monkeypatch.setattr(sh, "invalidate_buckets_cache", lambda: None)
    # Return empty list so dedup check (any b["id"] == nid) passes
    monkeypatch.setattr(sh, "get_active_buckets", lambda mk, **kw: [])

    # Stub _finalize so we don't need the full sheet setup
    import handlers.transaction as tx_mod

    async def _noop_finalize(*a, **k):
        pass

    monkeypatch.setattr(tx_mod, "_finalize", _noop_finalize)

    state = sh.get_state(CHAT_ID) or {}
    await handle_inline_new_cat_name("New Expense Cat", state)

    assert "2025-11" in write_budget_months, (
        f"write_budget_row must be called with '2025-11', got: {write_budget_months}"
    )
    assert "2026-05" not in write_budget_months, (
        f"write_budget_row must NOT use current month '2026-05', got: {write_budget_months}"
    )


# ─── Codex P2: tx_date propagation (daily-bucket historical recats) ──────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_carries_tx_date_in_state(world):
    """_cmd_recat stores row[1] as tx_date so _finalize uses the historical date.

    Without this, daily-bucket recats on old rows call get_daily_status(now)
    instead of get_daily_status(row_date), showing wrong daily cap progress.

    FAILS before fix because _cmd_recat does not set 'tx_date' in state.
    """
    calls, ws_tx = world
    # Seed with a distinct date in column B so we can assert it lands in state
    ws_tx.update("A2:R2", [[
        "", "2025-11-15T07:30:00", "", "", "",
        "Old expense", "Tiền ra", "50000",
        "REF99", "0", "", "", "FALSE", "FALSE",
        "2025-11", "VND", "", "expense",
    ]])
    sh._tx_rows_cache.update({"ts": 0.0, "rows": None})

    await main._handle_command("/recat 2")

    state = sh.get_state(CHAT_ID)
    assert state is not None
    assert state.get("tx_date") == "2025-11-15T07:30:00", (
        f"Expected tx_date='2025-11-15T07:30:00' in state, got: {state.get('tx_date')!r}"
    )


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_handle_recategorize_carries_tx_date_in_state(world):
    """handle_recategorize (button path) also stores row[1] as tx_date (P2 fix)."""
    calls, ws_tx = world
    ws_tx.update("A2:R2", [[
        "", "2025-11-15T07:30:00", "", "", "",
        "Old expense", "Tiền ra", "50000",
        "REF99", "0", "old_cat", "", "FALSE", "TRUE",
        "2025-11", "VND", "", "expense",
    ]])
    sh._tx_rows_cache.update({"ts": 0.0, "rows": None})

    await handle_recategorize(["recat", "2"], 100)

    state = sh.get_state(CHAT_ID)
    assert state is not None
    assert state.get("tx_date") == "2025-11-15T07:30:00", (
        f"Expected tx_date='2025-11-15T07:30:00' in state, got: {state.get('tx_date')!r}"
    )


# ─── Codex P2 (round 4): tolerant date parsing in _finalize ─────────────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_finalize_survives_non_iso_date_in_state(world, monkeypatch):
    """_finalize must not raise ValueError for Vietnamese-format dates (dd/mm/yyyy).

    Raw sheet dates like '15/11/2025 07:30:00' are stored verbatim in state
    by _cmd_recat/handle_recategorize. _finalize must use a tolerant parser
    (sh._parse_dt) instead of datetime.fromisoformat which only accepts ISO.

    FAILS before fix because datetime.fromisoformat('15/11/2025 07:30:00') raises.
    """
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    # Pre-seed state with Vietnamese-format date — exactly what row[1] may contain
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Old expense",
        "month_key": "2025-11",
        "tx_date": "15/11/2025 07:30:00",  # non-ISO — fromisoformat raises ValueError
    })

    monkeypatch.setattr(sh, "get_bucket_status",
                        lambda bid, mk: {"spent": 0, "allocated": 0, "remaining": 0, "foreign": {}})
    monkeypatch.setattr(sh, "get_sub_categories", lambda bid: [])
    monkeypatch.setattr(sh, "bucket_label", lambda bid: bid)

    # Must complete without raising ValueError
    try:
        await handle_parent_selected(["p", "2", "old_cat"], 100)
    except ValueError as exc:
        pytest.fail(f"_finalize raised ValueError on non-ISO date: {exc}")


# ─── Codex P2 (round 5-A): _parse_dt must handle space-separator datetime ────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_finalize_handles_space_separator_datetime_in_state(world, monkeypatch):
    """str(tz_aware_datetime) produces 'YYYY-MM-DD HH:MM:SS+TZ' (space, not T).

    _parse_dt must handle this format so _finalize uses the historical date
    for daily-bucket recats, not today. Without the fix, _parse_dt returns None
    → silent fallback to now() → daily status shows today's spend, not November 2025.

    FAILS before fix because _parse_dt has no format matching this pattern.
    """
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    # Pre-seed state WITHOUT month_key so _finalize must derive it from tx_date
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Old expense",
        # No month_key — forces _finalize to use fmt_month(tx_date)
        "tx_date": "2025-11-15 07:30:00+00:00",  # str(tz_aware_dt) — space separator
    })

    daily_status_dates = []

    def _spy_daily(tx_date):
        daily_status_dates.append(tx_date)
        return {"spent": 0, "cap": 100000, "remaining": 100000}

    monkeypatch.setattr(sh, "get_daily_status", _spy_daily)
    monkeypatch.setattr(sh, "get_bucket_status",
                        lambda bid, mk: {"spent": 0, "allocated": 0, "remaining": 0, "foreign": {}})
    monkeypatch.setattr(sh, "get_sub_categories", lambda bid: [])
    monkeypatch.setattr(sh, "bucket_label", lambda bid: bid)
    monkeypatch.setattr(sh, "calc_pct", lambda s, t: 0)

    await handle_parent_selected(["p", "2", DAILY_BUCKET_ID], 100)

    assert daily_status_dates, "Expected _finalize to call get_daily_status"
    dt = daily_status_dates[0]
    assert dt.year == 2025 and dt.month == 11, (
        f"Expected historical date (2025-11), got {dt!r} — "
        f"_parse_dt likely returned None for space-separator format"
    )


# ─── Codex P2 (round 5-B): handle_recategorize guards reset before empty buckets


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_handle_recategorize_no_active_buckets_skips_reset(world):
    """Button path with old-month row whose month has no active buckets.

    reset_transaction_row must NOT be called (matches _cmd_recat behavior).
    FAILS before fix because handle_recategorize calls reset before bucket check.
    """
    calls, ws_tx = world
    # Month "2020-01" has no buckets in Budget Config
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2020-01",
              parent="old_cat", confirmed="TRUE")
    await handle_recategorize(["recat", "2"], 100)
    # Row must NOT be reset
    row = sh.get_transaction_row(2)
    assert row[10] == "old_cat", f"K=ParentCat must be untouched, got: {row[10]!r}"
    assert row[13] == "TRUE", f"N=Confirmed must be untouched, got: {row[13]!r}"


# ─── Codex P2 (round 6): fromisoformat preserves TZ for microsecond timestamps


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_finalize_preserves_tz_offset_for_microsecond_timestamp(world, monkeypatch):
    """tx_date 'YYYY-MM-DDThh:mm:ss.ffffff+HH:MM' must keep its TZ offset.

    _parse_dt truncates to [:26] which drops the offset for microsecond strings,
    treating +07:00 as UTC — this can shift a VN May-31 23:30 tx to June 1.
    The fix: try fromisoformat first (Python 3.11+ handles the full string),
    fall back to _parse_dt only for non-ISO formats.

    FAILS before fix because _parse_dt returns wrong UTC time.
    """
    import pytz as _pytz
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Old expense",
        # No month_key — forces _finalize to derive month from tx_date
        "tx_date": "2026-05-31T23:30:00.123456+07:00",  # VN May 31, UTC May 31 16:30
    })

    daily_dates = []
    monkeypatch.setattr(
        sh, "get_daily_status",
        lambda dt: (daily_dates.append(dt), {"spent": 0, "cap": 100000, "remaining": 100000})[1],
    )
    monkeypatch.setattr(sh, "get_bucket_status",
                        lambda bid, mk: {"spent": 0, "allocated": 0, "remaining": 0, "foreign": {}})
    monkeypatch.setattr(sh, "get_sub_categories", lambda bid: [])
    monkeypatch.setattr(sh, "bucket_label", lambda bid: bid)
    monkeypatch.setattr(sh, "calc_pct", lambda s, t: 0)

    await handle_parent_selected(["p", "2", DAILY_BUCKET_ID], 100)

    assert daily_dates, "_finalize should have called get_daily_status"
    dt_vn = daily_dates[0].astimezone(_pytz.timezone("Asia/Ho_Chi_Minh"))
    # Must be May 31 VN time — before fix _parse_dt's [:26] truncation shifts it to June 1
    assert dt_vn.month == 5 and dt_vn.day == 31, (
        f"Expected VN date 2026-05-31, got {dt_vn!r} — TZ offset was not preserved"
    )


# ─── Codex P3 (round 8): /recat 1 hits header row → ValueError crash ─────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_recat_header_row_sends_not_found_not_crash(world):
    """/recat 1 reads the sheet header row; _parse_amount('Amount') crashes.

    Should send a not-found message instead of propagating ValueError.
    FAILS before fix because there is no row_num < 2 guard.
    """
    calls, _ = world
    try:
        await main._handle_command("/recat 1")
    except ValueError:
        pytest.fail("/recat 1 raised ValueError — missing row_num < 2 guard")
    assert calls["texts"], "Expected a not-found error message for /recat 1"
    assert not calls["buttons"]


# ─── Codex P2 (round 9): re-localize Vietnamese dates as bot timezone ─────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_finalize_vietnamese_date_uses_bot_timezone_not_utc(world, monkeypatch):
    """Vietnamese-format dates in state are VN local time, not UTC.

    _parse_dt attaches UTC to naive datetimes; for the 'dd/mm/yyyy HH:MM:SS'
    fallback path, _finalize must re-localize in TIMEZONE so a VN 23:30 entry
    stays on May 31 instead of shifting to June 1 (UTC → VN = +7h).

    FAILS before fix because _parse_dt's UTC treatment shifts the date.
    """
    import pytz as _pytz
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    # No month_key — forces _finalize to derive month from tx_date
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Old expense",
        "tx_date": "31/05/2026 23:30:00",  # VN local time near midnight
    })

    daily_dates = []
    monkeypatch.setattr(
        sh, "get_daily_status",
        lambda dt: (daily_dates.append(dt), {"spent": 0, "cap": 100000, "remaining": 100000})[1],
    )
    monkeypatch.setattr(sh, "get_bucket_status",
                        lambda bid, mk: {"spent": 0, "allocated": 0, "remaining": 0, "foreign": {}})
    monkeypatch.setattr(sh, "get_sub_categories", lambda bid: [])
    monkeypatch.setattr(sh, "bucket_label", lambda bid: bid)
    monkeypatch.setattr(sh, "calc_pct", lambda s, t: 0)

    await handle_parent_selected(["p", "2", DAILY_BUCKET_ID], 100)

    assert daily_dates, "Expected _finalize to call get_daily_status"
    VN = _pytz.timezone("Asia/Ho_Chi_Minh")
    dt_vn = daily_dates[0].astimezone(VN)
    # Must be May 31 VN time — before fix UTC treatment shifts 23:30 VN → June 1 06:30 VN
    assert dt_vn.month == 5 and dt_vn.day == 31, (
        f"Expected VN date 2026-05-31, got {dt_vn!r} — Vietnamese date treated as UTC"
    )


# ─── Codex P2 (round 11): localize naive fromisoformat results ───────────────


@pytest.mark.asyncio
@freeze_time("2026-05-01")
async def test_finalize_naive_iso_date_uses_bot_timezone(world, monkeypatch):
    """Naive ISO timestamps (no +TZ suffix) must be localized as TIMEZONE.

    fromisoformat('2026-05-31 23:30:00') returns a naive datetime; get_daily_status
    treats naive datetimes as UTC, shifting a VN 23:30 entry to June 1 06:30 VN.
    Fix: localize naive fromisoformat results in TIMEZONE before using.

    FAILS before fix because naive datetime is passed directly to get_daily_status.
    """
    import pytz as _pytz
    calls, ws_tx = world
    _seed_row(ws_tx, 2, direction="Tiền ra", month="2025-11")
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": 2,
        "amount": 75000, "currency": "VND", "description": "Old expense",
        "tx_date": "2026-05-31 23:30:00",  # naive ISO — no TZ, fromisoformat succeeds
    })

    daily_dates = []
    monkeypatch.setattr(
        sh, "get_daily_status",
        lambda dt: (daily_dates.append(dt), {"spent": 0, "cap": 100000, "remaining": 100000})[1],
    )
    monkeypatch.setattr(sh, "get_bucket_status",
                        lambda bid, mk: {"spent": 0, "allocated": 0, "remaining": 0, "foreign": {}})
    monkeypatch.setattr(sh, "get_sub_categories", lambda bid: [])
    monkeypatch.setattr(sh, "bucket_label", lambda bid: bid)
    monkeypatch.setattr(sh, "calc_pct", lambda s, t: 0)

    await handle_parent_selected(["p", "2", DAILY_BUCKET_ID], 100)

    assert daily_dates, "Expected _finalize to call get_daily_status"
    dt = daily_dates[0]
    # Must be TZ-aware: naive datetimes are treated as UTC by get_daily_status,
    # which would shift VN 23:30 May 31 to Jun 1. The fix must localize before passing.
    assert dt.tzinfo is not None, (
        f"tx_date passed to get_daily_status must be TZ-aware, got naive {dt!r}"
    )
    VN = _pytz.timezone("Asia/Ho_Chi_Minh")
    dt_vn = dt.astimezone(VN)
    # Must be May 31 VN time — before fix naive UTC shifts 23:30 → June 1 06:30 VN
    assert dt_vn.month == 5 and dt_vn.day == 31, (
        f"Expected VN date 2026-05-31, got {dt_vn!r} — naive datetime treated as UTC"
    )
