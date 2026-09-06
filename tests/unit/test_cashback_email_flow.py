"""Phase B Phase 2 — webhook hook: credit-card expense → Cashback Ledger.

Email Cake CC transactions converge on handle_sepay_webhook (same as SePay).
The hook must compute cashback once on the outgoing path (before the
auto-categorize/picker branch) for credit accounts only, write the ledger, and
surface the FR-2.7 daily-limit notice. Bank/SePay tx must NOT earn cashback.

tg/messenger side-effects stubbed; we assert ledger state + captured notices.
"""
import pytest
import pytz
from datetime import datetime

import sheets as sh
from config import SHEETS as S
import handlers.sepay as sepay


@pytest.fixture
def cc_world(monkeypatch, fake_ss):
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X"]])
    ws_bc.update("A2:H2", [["2026-06", "daily_spending", "🛒 Daily", 0, 100000, "TRUE", "test", ""]])
    sh.invalidate_buckets_cache()
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])
    sh.invalidate_cashback_caches()

    import telegram_api as tg
    sent: list[str] = []

    async def _send_text(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _noop(*a, **k):
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _send_text)
    async def _send_with_buttons(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}
    monkeypatch.setattr(tg, "send_with_buttons", _send_with_buttons)
    for n in ("edit_message", "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, n, _noop)
    return {"ss": fake_ss, "sent": sent}


def _seed_cc():
    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit",
                   currency="VND", source_keys=["email_cake:cake_cc"],
                   credit_limit=50_000_000, statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()
    sh.upsert_card_config("cake_cc", cashback_rate=0.20, min_eligible_spend=0,
                          cap_period="statement_cycle", alert_pct=0.80, active=True)
    sh.add_cashback_rule("cake_cc", "Siêu thị", "mcc", "5411", monthly_cap=200000,
                         per_tx_cap_tier="cakefreedom", max_eligible_tx_per_day=1)
    ws = sh._ensure_cashback_tiers_tab()
    ws.update("A2:D3", [["cakefreedom", 0, 199999, 10000],
                        ["cakefreedom", 200000, "", 50000]])
    sh.add_mcc_map("WINMART", "5411", "Siêu thị")
    sh.invalidate_cashback_caches()


def _cc_payload(amount, desc):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now = datetime.now(tz)
    return {
        "_source": "email_cake", "_account_hint": "cake_cc",
        "transferType": "out", "transferAmount": amount, "description": desc,
        "transactionDate": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": "VND", "referenceCode": f"CC{amount}{desc[:6]}",
    }


def _active(account):
    return [l for l in sh.get_cashback_ledger(account) if l["status"] != "void"]


@pytest.mark.asyncio
async def test_email_cc_first_supermarket_earns_cashback(cc_world):
    _seed_cc()
    await sepay.handle_sepay_webhook(
        _cc_payload(243087, "WCM_WINMART 6992 HOMYLAND HO CHI MINH VN"))
    lines = _active("cake_cc")
    assert len(lines) == 1
    assert lines[0]["cashback_amount"] == 48617   # round(0.20 * 243087)
    assert lines[0]["mcc_code"] == "5411"
    # Cashback is now compacted into the budget message (sent when user picks
    # a category via _finalize), NOT as a separate webhook-time message.
    # Verify the compact line helper would produce the right text:
    from handlers.transaction import _get_cashback_line
    cb_line = _get_cashback_line(2)  # tx row 2
    assert "hoàn tiền" in cb_line
    assert "Siêu thị" in cb_line


@pytest.mark.asyncio
async def test_email_cc_second_supermarket_blocked_same_day(cc_world):
    _seed_cc()
    await sepay.handle_sepay_webhook(_cc_payload(243087, "WCM_WINMART A"))
    await sepay.handle_sepay_webhook(_cc_payload(300000, "WCM_WINMART B"))
    lines = _active("cake_cc")
    blocked = [l for l in lines if l["cashback_amount"] == 0 and l["reason"] == "daily_limit"]
    assert len(blocked) == 1
    # Daily limit text now appears inline in the budget message (via _get_cashback_line).
    from handlers.transaction import _get_cashback_line
    cb_line = _get_cashback_line(3)  # tx row 3 (blocked)
    assert "hết lượt" in cb_line


@pytest.mark.asyncio
async def test_email_cc_out_of_order_earlier_time_wins(cc_world):
    # Codex round 01 [P1]: the live hook must rebuild the cycle (recompute), so a
    # later-arriving but earlier-timestamp tx wins the daily slot.
    _seed_cc()
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    today = datetime.now(tz)

    def pl(amount, desc, hour):
        dt = today.replace(hour=hour, minute=0, second=0, microsecond=0)
        return {
            "_source": "email_cake", "_account_hint": "cake_cc", "transferType": "out",
            "transferAmount": amount, "description": desc,
            "transactionDate": dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "currency": "VND", "referenceCode": f"OOO{amount}",
        }

    await sepay.handle_sepay_webhook(pl(300000, "WCM_WINMART LATE", 15))   # arrives 1st
    await sepay.handle_sepay_webhook(pl(250000, "WCM_WINMART EARLY", 9))   # arrives 2nd, earlier time
    lines = _active("cake_cc")
    early = [l for l in lines if l["eligible_amount"] == 250000][0]
    late = [l for l in lines if l["eligible_amount"] == 300000][0]
    assert early["cashback_amount"] == 50000   # earliest-by-time wins
    assert late["cashback_amount"] == 0
    assert late["reason"] == "daily_limit"


def test_backfill_recomputes_cashback_for_late_onboarded_credit(fake_ss):
    # A credit-card tx lands BEFORE the account is onboarded (account_id empty,
    # source_key recorded). Onboarding later calls backfill_account_id_by_source_key,
    # which must (re)compute cashback for the now-attributed historical rows.
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    sh.invalidate_cashback_caches()
    r = sh.append_transaction(
        "2026-06-10T09:00:00", "WCM_WINMART HCM", 300000, "REFBF", "2026-06",
        account_id="", ledger_tx_type="expense",
        account_source_key="email_cake:cake_cc",
    )
    # No account yet → no cashback.
    assert sh.compute_and_record_cashback(r)["lines"] == []

    _seed_cc()  # onboards cake_cc (source_keys email_cake:cake_cc) + config + rule + mcc
    n = sh.backfill_account_id_by_source_key("cake_cc", "email_cake:cake_cc")
    assert n == 1
    lines = _active("cake_cc")
    assert len(lines) == 1
    assert lines[0]["cashback_amount"] == 50000
    assert lines[0]["mcc_code"] == "5411"


def test_backfill_recomputes_already_stamped_trigger_row(fake_ss):
    # Codex round 02 [P2]: the wizard's trigger tx is stamped with account_id by
    # an earlier path, so it's absent from backfill's `updates`. Backfill must
    # still recompute the account's cycles so that row gets cashback.
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    sh.invalidate_cashback_caches()
    _seed_cc()  # account + config already exist
    # trigger row ALREADY stamped with account_id (no row left to backfill)
    r = sh.append_transaction("2026-06-10T09:00:00", "WCM_WINMART HCM", 300000,
                              "RTRIG", "2026-06", account_id="cake_cc",
                              ledger_tx_type="expense",
                              account_source_key="email_cake:cake_cc")
    assert _active("cake_cc") == []
    sh.backfill_account_id_by_source_key("cake_cc", "email_cake:cake_cc")  # 0 updates
    lines = _active("cake_cc")
    assert len(lines) == 1
    assert lines[0]["cashback_amount"] == 50000


@pytest.mark.asyncio
async def test_email_cc_gate_open_sends_activation_notice(cc_world):
    # Codex round 05 [P2] / FR-2.6: crossing min_eligible_spend must notify.
    _seed_cc()
    sh.upsert_card_config("cake_cc", min_eligible_spend=5_000_000)
    sh.add_cashback_rule("cake_cc", "Di chuyển", "mcc", "4121", rate="",
                         monthly_cap=200000, per_tx_cap_tier="cakefreedom")
    sh.add_mcc_map("GRAB", "4121")
    sh.invalidate_cashback_caches()

    await sepay.handle_sepay_webhook(_cc_payload(4_900_000, "WCM_WINMART BIG"))  # pending
    await sepay.handle_sepay_webhook(_cc_payload(200_000, "GRAB ride"))          # crosses gate
    assert any("kích hoạt" in t for t in cc_world["sent"])


@pytest.mark.asyncio
async def test_bank_sepay_tx_earns_no_cashback(cc_world):
    sh.add_account(account_id="bank1", name="Bank 1", acc_type="bank", currency="VND",
                   source_keys=["sepay:111"], starting_balance=0)
    sh.invalidate_accounts_cache()
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now = datetime.now(tz)
    await sepay.handle_sepay_webhook({
        "transferType": "out", "transferAmount": 300000, "description": "WCM_WINMART",
        "transactionDate": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "currency": "VND", "referenceCode": "BANK1", "accountNumber": "111",
    })
    assert sh.get_cashback_ledger("bank1") == []
