"""Phase B Phase 3 — /report cashback section.

A global cashback section renders at the end of /report on BOTH lenses
(category default + account), and is omitted entirely when no credit card has
cashback configured.
"""
import pytest
import pytz
from datetime import datetime

import sheets as sh
from config import SHEETS as S
import handlers.report as report
import handlers.cashback as cb


def _setup_tabs(fake_ss):
    ws_tx = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws_tx.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [["Month", "Bucket", "Name", "Allocated", "DailyCap", "Active", "Source", "X"]])
    sh.invalidate_buckets_cache()
    sh.invalidate_cashback_caches()


def _seed_card_with_tx():
    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit", currency="VND",
                   source_keys=["email_cake:cake_cc"], credit_limit=50_000_000,
                   statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()
    cb.seed_cake_card("cake_cc")
    now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
    r = sh.append_transaction(now.strftime("%Y-%m-%dT%H:%M:%S"), "WCM_WINMART HCM",
                              300000, "RPT", sh.fmt_month(now),
                              account_id="cake_cc", ledger_tx_type="expense")
    sh.compute_and_record_cashback(r)


def test_section_empty_when_no_configured_card(fake_ss):
    _setup_tabs(fake_ss)
    assert report.render_cashback_section("m") == ""


def test_section_renders_for_configured_card(fake_ss):
    _setup_tabs(fake_ss)
    _seed_card_with_tx()
    s = report.render_cashback_section("m")
    assert s != ""
    assert "CASHBACK" in s
    assert "Siêu thị" in s          # MCC rule name
    assert "5.000.000" in s         # activation gate target


@pytest.mark.asyncio
async def test_cmd_report_appends_section_both_lenses(monkeypatch, fake_ss):
    _setup_tabs(fake_ss)
    _seed_card_with_tx()
    import telegram_api as tg
    sent = []

    async def _swb(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _edit(mid, text, *a, **k):
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(tg, "send_with_buttons", _swb)
    monkeypatch.setattr(tg, "edit_message", _edit)

    await report.cmd_report("/report")                       # category lens (default)
    assert any("CASHBACK" in t for t in sent)
    sent.clear()
    await report.handle_report_callback(["rpt", "m", "a"], 1)  # account lens
    assert any("CASHBACK" in t for t in sent)


@pytest.mark.asyncio
async def test_zalo_report_includes_cashback_section(monkeypatch, fake_ss):
    # Codex round 05 [P2]: Zalo /report must also show the cashback section.
    _setup_tabs(fake_ss)
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])
    _seed_card_with_tx()
    import main
    import messenger
    sent = []

    async def _st(text, channel=None, recipient_id=None):
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(messenger, "send_text", _st)
    await main._zalo_cmd_report("Z1", "/report", "zalo:Z1")
    assert any("CASHBACK" in t for t in sent)
