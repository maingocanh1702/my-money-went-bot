"""/transfer and /cc pay — the two commands that move money between accounts.

Both used to exist twice, once per channel, and neither copy had a test. These
pin the behaviour on BOTH channels so the shared implementation cannot drift
back: same validation, same ledger call, same numbers, and a Zalo reply that
is plain text but still names the accounts the user typed.
"""
import pytest

import main
import messenger
import sheets as sh
import telegram_api as tg
from config import SHEETS as S

ZALO_CHAT = "9990001112223"


@pytest.fixture
def money_world(monkeypatch, fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:T1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied",
    ]])
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "updated"]])
    sh._ensure_accounts_tab()
    sh._ensure_ledger_tab()

    sh.add_account(account_id="bank_main", name="Bank Main", acc_type="bank",
                   currency="VND", source_keys=["sepay:bank_main"],
                   starting_balance=5_000_000)
    sh.add_account(account_id="cake_main", name="Cake Main", acc_type="bank",
                   currency="VND", source_keys=["sepay:cake_main"],
                   starting_balance=0)
    sh.add_account(account_id="hkd_acc", name="HKD Acc", acc_type="bank",
                   currency="HKD", source_keys=["sepay:hkd_acc"],
                   starting_balance=1000)
    sh.add_account(account_id="visa_cc", name="Visa CC", acc_type="credit",
                   currency="VND", source_keys=["sepay:visa_cc"],
                   credit_limit=10_000_000, statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()

    sent = {"telegram": [], "zalo": []}

    async def _tg_send(text, chat_id=None):
        sent["telegram"].append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def _zalo_send(recipient_id, text):
        # what a Zalo user actually reads: the real strip, no API call
        sent["zalo"].append(messenger._strip_markdown(text))

    monkeypatch.setattr(tg, "send_text", _tg_send)
    monkeypatch.setattr(messenger, "_zalo_send_text", _zalo_send)
    fake_ss.sent = sent
    return fake_ss


def _last(world, channel):
    assert world.sent[channel], f"nothing sent on {channel}"
    return world.sent[channel][-1]


async def _run(cmd: str, channel: str):
    """Drive the command the way its dispatcher does."""
    fn = main._cmd_transfer if cmd.split()[0] == "/transfer" else main._cmd_cc_pay
    if channel == "zalo":
        await fn(cmd, channel="zalo", chat_id=ZALO_CHAT)
    else:
        await fn(cmd)


# ─── /transfer ───────────────────────────────────────────────────


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_transfer_moves_money_and_reports_both_balances(money_world, channel):
    await _run("/transfer 1000000 bank_main cake_main", channel)

    assert sh.find_account_by_id("bank_main")["running_balance"] == 4_000_000
    assert sh.find_account_by_id("cake_main")["running_balance"] == 1_000_000
    msg = _last(money_world, channel)
    assert "Transfer ghi nhận" in msg
    assert "Bank Main" in msg and "Cake Main" in msg


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_transfer_refuses_same_account(money_world, channel):
    await _run("/transfer 1000000 bank_main bank_main", channel)
    assert "phải khác account" in _last(money_world, channel)
    assert sh.find_account_by_id("bank_main")["running_balance"] == 5_000_000


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_transfer_refuses_currency_mismatch(money_world, channel):
    await _run("/transfer 1000 bank_main hkd_acc", channel)
    assert "Currency mismatch" in _last(money_world, channel)
    assert sh.find_account_by_id("bank_main")["running_balance"] == 5_000_000


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_transfer_unknown_account_names_the_id_the_user_typed(money_world, channel):
    await _run("/transfer 1000000 bank_main no_such_acc", channel)
    msg = _last(money_world, channel)
    assert "no_such_acc" in msg, "the underscore must survive on both channels"


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_transfer_usage_example_is_copyable(money_world, channel):
    await _run("/transfer", channel)
    assert "bank_main cake_main" in _last(money_world, channel)


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_transfer_rejects_garbage_amount(money_world, channel):
    await _run("/transfer abc bank_main cake_main", channel)
    assert "không hợp lệ" in _last(money_world, channel)
    assert sh.find_account_by_id("bank_main")["running_balance"] == 5_000_000


# ─── /cc pay ─────────────────────────────────────────────────────


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_cc_pay_external_reduces_outstanding_only(money_world, channel):
    sh.append_cc_payment_external(
        cc_account_id="visa_cc", amount=0, currency="VND",
        description="seed", tx_date="2026-09-01T10:00:00",
        ref_code="SEED_visa_cc", month_key="2026-09",
    )
    before_bank = sh.find_account_by_id("bank_main")["running_balance"]

    await _run("/cc pay 500000 visa_cc", channel)

    assert sh.find_account_by_id("bank_main")["running_balance"] == before_bank
    assert "CC payment ghi nhận" in _last(money_world, channel)


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_cc_pay_from_bank_debits_the_bank(money_world, channel):
    await _run("/cc pay 500000 bank_main visa_cc", channel)

    assert sh.find_account_by_id("bank_main")["running_balance"] == 4_500_000
    assert "CC payment ghi nhận" in _last(money_world, channel)


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_cc_pay_refuses_a_non_credit_target(money_world, channel):
    await _run("/cc pay 500000 cake_main", channel)
    msg = _last(money_world, channel)
    assert "không phải credit card" in msg
    assert "cake_main" in msg


@pytest.mark.parametrize("channel", ["telegram", "zalo"])
@pytest.mark.asyncio
async def test_cc_pay_bad_shape_shows_usage(money_world, channel):
    await _run("/cc oops 500000 visa_cc", channel)
    assert "Usage" in _last(money_world, channel)


# ─── the Zalo reply is plain, but not mangled ────────────────────


@pytest.mark.asyncio
async def test_zalo_reply_carries_no_markdown_tokens(money_world):
    await _run("/transfer 1000000 bank_main cake_main", "zalo")
    msg = _last(money_world, "zalo")
    assert "*" not in msg and "`" not in msg


def test_strip_markdown_keeps_identifiers_and_drops_formatting():
    strip = messenger._strip_markdown
    assert strip("Account `bank_main` không tồn tại") == "Account bank_main không tồn tại"
    assert strip("Ref: TRANSFER_bank_main_cake_main_1757") == "Ref: TRANSFER_bank_main_cake_main_1757"
    assert strip("*Transfer ghi nhận*") == "Transfer ghi nhận"
    assert strip("📌 _Còn 2 giao dịch chờ._") == "📌 Còn 2 giao dịch chờ."
    assert strip("snake_case and _italic_ here") == "snake_case and italic here"
