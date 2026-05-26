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
    from config import SEPAY_SECRET
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return {
        "transferType": tx_type,
        "transferAmount": amount,
        "description": desc,
        "transactionDate": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": currency,
        "referenceCode": ref,
        "accountNumber": account,
        "apikey": SEPAY_SECRET,
    }


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
async def test_sepay_retry_after_append_failure_processes_ref(fake_world, monkeypatch):
    _seed_account()
    payload = _basic_payload(ref="RETRY_AFTER_APPEND_FAIL")

    original_append = sh.append_transaction
    calls = {"count": 0}

    def flaky_append(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated append failure")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(sh, "append_transaction", flaky_append)

    with pytest.raises(RuntimeError, match="simulated append failure"):
        await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert len(rows) == 1

    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert len(rows) == 2
    assert rows[1][8] == "RETRY_AFTER_APPEND_FAIL"

    ref_rows = sh._sheet(S.PROCESSED_REFS).get_all_values()
    matching = [r for r in ref_rows[1:] if r[0] == "RETRY_AFTER_APPEND_FAIL"]
    assert matching[-1][1] == "committed"


def test_tx_exists_committed_ref_is_deduped(fake_world):
    ws_refs = fake_world.add_worksheet(S.PROCESSED_REFS)
    ws_refs.update("A1:C1", [["ref_code", "status", "created_at"]])
    ws_refs.update("A2:C2", [["COMMITTED_REF", "committed", "2026-05-26T00:00:00"]])

    assert sh.tx_exists("COMMITTED_REF") is True


def test_tx_exists_failed_ref_is_recoverable(fake_world):
    ws_refs = fake_world.add_worksheet(S.PROCESSED_REFS)
    ws_refs.update("A1:C1", [["ref_code", "status", "created_at"]])
    ws_refs.update("A2:C2", [["FAILED_REF", "failed", "2026-05-26T00:00:00"]])

    assert sh.tx_exists("FAILED_REF") is False

    rows = ws_refs.get_all_values()
    assert len([r for r in rows[1:] if r[0] == "FAILED_REF"]) == 1
    assert rows[1][1] == "processing"


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


@pytest.mark.asyncio
async def test_sepay_vnd_amount_preserves_integer_precision(fake_world):
    _seed_account()
    payload = _basic_payload(
        amount="9007199254740993",
        ref="BIG_VND",
        desc="large vnd precision check",
    )

    await sepay.handle_sepay_webhook(payload)

    rows = sh._sheet(S.TRANSACTIONS).get_all_values()
    assert rows[1][7] == "9007199254740993"


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
