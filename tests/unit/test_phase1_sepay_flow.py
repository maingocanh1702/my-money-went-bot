"""Phase 1 — SePay webhook → resolver → ledger: end-to-end with the
in-memory FakeSpreadsheet. The biggest acceptance criterion: idempotency.

Telegram + httpx side-effects are stubbed out (no network). We assert sheet
state and ledger state directly.
"""
import pytest
import sheets as sh
from config import SHEETS as S
import handlers.sepay as sepay
import handlers.transaction as transaction


@pytest.fixture
def fake_world(monkeypatch, fake_ss):
    """Set up the Transactions / Accounts / Ledger / BudgetConfig tabs +
    no-op all telegram_api functions. Returns a small helper namespace."""
    # Transactions tab
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:T1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied",
    ]])
    # Budget Config (sepay needs at least 1 active bucket so auto-categorize
    # logic doesn't crash; provide one for the daily bucket)
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [[
        "Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X",
    ]])
    ws_bc.update("A2:H2", [[
        "2026-05", "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", "",
    ]])
    sh.invalidate_buckets_cache()
    # Bot State tab so set_state/get_state work
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    # Stub all telegram async calls (we just want to check sheet state)
    import telegram_api as tg

    # These tests exercise the post-auth transaction flow. Authentication has
    # its own boundary tests, and a developer's local .env must not alter this
    # fake Sheets contract.
    monkeypatch.setattr(sepay, "SEPAY_SECRET", "")

    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}

    for name in ("send_text", "send_with_buttons", "edit_message",
                 "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, name, _noop)

    return fake_ss


def _seed_account(account_id="tcb_main", source="sepay:1903999888",
                  acc_type="bank", currency="VND", starting=1_000_000):
    sh.add_account(
        account_id=account_id,
        name=account_id,
        acc_type=acc_type,
        currency=currency,
        source_keys=[source],
        starting_balance=starting,
    )
    sh.invalidate_accounts_cache()


def _basic_payload(amount=50000, ref="REFX", account="1903999888",
                   tx_type="out", currency="VND", desc="highland"):
    """Use Vietnam-localized 'now' so sepay's stale-tx filter doesn't reject."""
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    payload = {
        "transferType": tx_type,
        "transferAmount": amount,
        "description": desc,
        "transactionDate": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": currency,
        "referenceCode": ref,
        "accountNumber": account,
    }
    # Keep these contract tests hermetic when a developer's shell has a real
    # SePay secret configured.
    from config import SEPAY_SECRET
    if SEPAY_SECRET:
        payload["apikey"] = SEPAY_SECRET
    return payload


# ── Resolver wiring ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sepay_matched_writes_account_id_on_tx(fake_world):
    _seed_account()
    payload = _basic_payload()
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    # row 2 = first written row
    assert rows[1][16] == "tcb_main"          # col Q account_id
    assert rows[1][17] == "expense"            # col R tx_type
    assert rows[1][19] == "FALSE"              # col T not yet applied (not categorized)


@pytest.mark.asyncio
async def test_sepay_no_identifier_writes_empty_account(fake_world):
    _seed_account()
    payload = _basic_payload(account=None)
    payload.pop("accountNumber", None)
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert rows[1][16] == ""  # no account_id


@pytest.mark.asyncio
async def test_ensure_buckets_clones_previous_month_when_empty(fake_world):
    """When the new month has NO buckets yet, clone from previous month."""
    ws = sh._sheet(S.BUDGET_CONFIG)
    # Only previous month has buckets — new month is empty
    ws.update("A3:H3", [[
        "2026-05", "food", "🍕 Food", 2_000_000, "", "TRUE", "test", "",
    ]])
    ws.update("A4:H4", [[
        "2026-05", "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", "",
    ]])
    sh.invalidate_buckets_cache()

    buckets, created = await sepay._ensure_buckets("2026-06")

    assert created == 0  # cloned, not default-bootstrapped
    by_id = {b["id"]: b for b in buckets}
    assert "food" in by_id
    assert by_id["food"]["allocated"] == 2_000_000
    assert "daily_spending" in by_id


@pytest.mark.asyncio
async def test_ensure_buckets_does_not_reclone_when_month_exists(fake_world):
    """When the new month already has buckets, don't clone extras from prev month."""
    ws = sh._sheet(S.BUDGET_CONFIG)
    ws.update("A3:H3", [[
        "2026-06", "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", "",
    ]])
    ws.update("A4:H4", [[
        "2026-05", "food", "🍕 Food", 2_000_000, "", "TRUE", "test", "",
    ]])
    sh.invalidate_buckets_cache()

    buckets, created = await sepay._ensure_buckets("2026-06")

    assert created == 0
    by_id = {b["id"]: b for b in buckets}
    # Should NOT have cloned "food" — month already had buckets
    assert "food" not in by_id
    assert "daily_spending" in by_id


# ── Idempotency: replay the same ref_code → no double row ──────


@pytest.mark.asyncio
async def test_sepay_replay_does_not_double_write(fake_world):
    _seed_account()
    payload = _basic_payload(ref="REPLAY1")
    await sepay.handle_sepay_webhook(payload)
    await sepay.handle_sepay_webhook(payload)
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    # header + exactly one tx row
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_sepay_claim_store_failure_is_retryable(fake_world, monkeypatch):
    payload = _basic_payload(ref="CLAIM_STORE_DOWN")

    def unavailable(_ref_code):
        raise sh.RetryableTransactionClaimError("claim store unavailable")

    monkeypatch.setattr(sh, "_ref_in_sheet", unavailable)
    with pytest.raises(sh.RetryableTransactionClaimError):
        await sepay.handle_sepay_webhook(payload)


@pytest.mark.asyncio
async def test_sepay_rejects_non_finite_amount_without_writing(fake_world):
    payload = _basic_payload(amount="NaN", ref="NAN_AMOUNT")
    await sepay.handle_sepay_webhook(payload)
    # Fake world creates the Transactions schema first; there must be no data row.
    assert len(sh._sheet(S.TRANSACTIONS).get_all_values()) == 1


# ── Idempotency: ledger write is itself idempotent (per-row apply) ─


@pytest.mark.asyncio
async def test_finalize_ledger_is_idempotent(fake_world):
    _seed_account()
    payload = _basic_payload(amount=200_000, ref="REF_LED")
    await sepay.handle_sepay_webhook(payload)

    # Find the row and finalize it twice
    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    row_num = 2  # first tx row
    assert rows[1][16] == "tcb_main"

    transaction._apply_ledger_for_row(row_num)
    transaction._apply_ledger_for_row(row_num)  # second call must be no-op
    transaction._apply_ledger_for_row(row_num)

    ledger_rows = sh._get_ledger_rows()
    assert len(ledger_rows) == 1

    sh.invalidate_accounts_cache()
    acc = sh.find_account_by_id("tcb_main")
    assert acc["running_balance"] == 800_000  # 1,000,000 - 200,000


# ── Currency mismatch: skip ledger, still write tx ─────────────


@pytest.mark.asyncio
async def test_currency_mismatch_skips_ledger(fake_world):
    _seed_account(currency="VND")
    payload = _basic_payload(amount=300, currency="HKD", ref="MISMATCH")
    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert rows[1][15] == "HKD"  # currency col P
    assert rows[1][16] == "tcb_main"  # account resolved...

    transaction._apply_ledger_for_row(2)  # ...but ledger write must skip

    assert sh._get_ledger_rows() == []
    sh.invalidate_accounts_cache()
    acc = sh.find_account_by_id("tcb_main")
    assert acc["running_balance"] == 1_000_000  # unchanged


# ── Recat: voids old ledger leg, account net unchanged ─────────


@pytest.mark.asyncio
async def test_recategorize_does_not_double_count(fake_world):
    _seed_account()
    payload = _basic_payload(amount=50_000, ref="RECAT")
    await sepay.handle_sepay_webhook(payload)

    transaction._apply_ledger_for_row(2)
    sh.invalidate_accounts_cache()
    assert sh.find_account_by_id("tcb_main")["running_balance"] == 950_000

    # User taps "wrong category" — sheet logic resets the row
    sh.reset_transaction_row(2)
    sh.invalidate_accounts_cache()
    assert sh.find_account_by_id("tcb_main")["running_balance"] == 1_000_000

    # User picks again → re-apply
    transaction._apply_ledger_for_row(2)
    sh.invalidate_accounts_cache()
    assert sh.find_account_by_id("tcb_main")["running_balance"] == 950_000

    # Total ledger entries: 1 active, 1 voided
    all_rows = sh._get_ledger_rows()
    assert len(all_rows) == 2
    active = sh.get_ledger_entries_for_tx(2)
    assert len(active) == 1
