"""Cake's cancellation e-mail reverses a charge; it must not add one.

Cake sends the same table twice. The purchase:

    [CAKE] Thông báo giao dịch qua thẻ Cake thành công
    Giao dịch: Thanh toán thẻ qua ECOM
    Giá trị:   18.000 đ
    Vào lúc:   18:23 10/09/2026
    Tại:       Grab* A-9QMTIBSWW36WAV 00 VN
    Tình trạng: Thành công

and its reversal, byte-identical except for the time and the status:

    [CAKE] Thông báo giao dịch qua thẻ Cake bị huỷ
    ...
    Vào lúc:   19:04 10/09/2026
    Tình trạng: Thất bại

Nothing in either body carries a sign, so the old direction keywords never saw
the difference: 292 of 292 card e-mails in the live account were recorded as
spending, every refund included, and the card's outstanding balance drifted
five million đồng away from the bank's.
"""
from datetime import datetime, timedelta, timezone

import pytest

import sheets as sh
from config import SHEETS as S
from handlers import cancel_tx as ctx
from handlers.email_parser import parse_email

TZ = timezone(timedelta(hours=7))
CAKE_FROM = "no-reply@cake.vn"

SUBJECT_OK = "[CAKE] Thông báo giao dịch qua thẻ Cake thành công"
SUBJECT_CANCELLED = "[CAKE] Thông báo giao dịch qua thẻ Cake bị huỷ"

MERCHANT = "Grab* A-9QMTIBSWW36WAV 00 VN"


def _body(when: str, status: str, amount: str = "18.000 đ", merchant: str = MERCHANT) -> str:
    return (
        "Kính gửi Quý khách NGUYEN VAN A\n"
        "Cám ơn Quý khách đã sử dụng sản phẩm dịch vụ của Cake.\n"
        "Thông tin giao dịch\n"
        "Số thẻ: ••1234\n"
        "Giao dịch: Thanh toán thẻ qua ECOM\n"
        f"Giá trị: {amount}\n"
        f"Vào lúc: {when}\n"
        f"Tại: {merchant}\n"
        "Nguồn tiền: Tài khoản tín dụng\n"
        f"Tình trạng: {status}\n"
    )


PURCHASE = _body("18:23 10/09/2026", "Thành công")
CANCELLATION = _body("19:04 10/09/2026", "Thất bại")


# ─── The parser tells the two apart ──────────────────────────────

def test_purchase_is_a_transaction():
    p = parse_email(CAKE_FROM, SUBJECT_OK, PURCHASE, "")
    assert p is not None
    assert p["_event_kind"] == "transaction"
    assert p["transferType"] == "out"
    assert p["transferAmount"] == 18_000
    assert p["_account_hint"] == "cake_cc"


def test_cancellation_is_marked_as_one():
    p = parse_email(CAKE_FROM, SUBJECT_CANCELLED, CANCELLATION, "")
    assert p is not None
    assert p["_event_kind"] == "cancellation"


def test_the_two_mails_differ_only_by_time_and_status():
    """If this stops being true the pairing key below needs revisiting."""
    a = [l for l in PURCHASE.splitlines() if not l.startswith(("Vào lúc", "Tình trạng"))]
    b = [l for l in CANCELLATION.splitlines() if not l.startswith(("Vào lúc", "Tình trạng"))]
    assert a == b


def test_the_two_mails_get_different_reference_codes():
    """Same amount and merchant — only the timestamp separates them, so a
    shared reference would make the cancellation look like a replay."""
    ok = parse_email(CAKE_FROM, SUBJECT_OK, PURCHASE, "")
    no = parse_email(CAKE_FROM, SUBJECT_CANCELLED, CANCELLATION, "")
    assert ok["referenceCode"] != no["referenceCode"]


def test_a_status_the_parser_does_not_know_is_not_a_cancellation():
    p = parse_email(CAKE_FROM, SUBJECT_OK, _body("18:23 10/09/2026", "Đang xử lý"), "")
    assert p["_event_kind"] == "transaction"


# ─── Finding the row a cancellation reverses ─────────────────────

def _tx_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
        "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed", "Month",
        "Currency", "account_id", "tx_type", "linked_tx_row", "ledger_applied",
        "account_source_key",
    ]])
    return ws


def _purchase(when, amount=18_000, desc=MERCHANT, account="cake_cc"):
    return sh.append_transaction(
        when.strftime("%Y-%m-%dT%H:%M:%S"), desc, amount,
        f"REF{when.strftime('%H%M%S')}", sh.fmt_month(when),
        tx_type="Tiền ra", account_id=account, ledger_tx_type="expense",
    )


def _at(hour, minute, days_ago=0):
    return (datetime.now(TZ) - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)


def test_matches_the_charge_it_reverses(fake_ss):
    _tx_tab(fake_ss)
    row = _purchase(_at(18, 23))
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found == row


def test_ignores_a_charge_that_came_after_the_notice(fake_ss):
    """A reversal cannot precede what it reverses. Without this guard a later
    identical ride would be the newest match and get cancelled instead."""
    _tx_tab(fake_ss)
    _purchase(_at(21, 0))
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_picks_the_most_recent_of_several_identical_charges(fake_ss):
    _tx_tab(fake_ss)
    _purchase(_at(9, 0))
    second = _purchase(_at(18, 23))
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found == second


def test_never_matches_a_row_already_cancelled(fake_ss):
    """Two notices for a merchant the user visits often must not walk backwards
    through their history cancelling one charge after another."""
    _tx_tab(fake_ss)
    row = _purchase(_at(18, 23))
    sh.set_transaction_cancelled(row, _at(19, 0).strftime("%Y-%m-%d %H:%M:%S"))
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_a_declined_payment_has_nothing_to_reverse(fake_ss):
    """Same notice, no purchase behind it. Inventing a match would cancel a
    real transaction."""
    _tx_tab(fake_ss)
    _purchase(_at(18, 23), amount=39_000)          # a different ride
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_a_different_merchant_is_not_a_match(fake_ss):
    _tx_tab(fake_ss)
    _purchase(_at(18, 23), desc="PAYOO*BACHHOAXANH_9272 TP THU DUC")
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_a_different_card_is_not_a_match(fake_ss):
    _tx_tab(fake_ss)
    _purchase(_at(18, 23), account="tpb_main")
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_an_income_row_is_never_reversed_this_way(fake_ss):
    """The confirmation would promise the opposite of what the ledger does —
    the same guard /cancel_tx enforces by hand."""
    _tx_tab(fake_ss)
    sh.append_transaction(
        _at(18, 23).strftime("%Y-%m-%dT%H:%M:%S"), MERCHANT, 18_000, "REFIN",
        sh.fmt_month(_at(18, 23)), tx_type="Tiền vào",
        account_id="cake_cc", ledger_tx_type="income",
    )
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_a_charge_older_than_the_cancel_window_is_left_alone(fake_ss):
    _tx_tab(fake_ss)
    _purchase(_at(18, 23, days_ago=ctx.MAX_AGE_DAYS + 5))
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="VND",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


def test_currency_must_match(fake_ss):
    _tx_tab(fake_ss)
    _purchase(_at(18, 23))
    found = ctx.find_original_for_cancellation(
        amount=18_000, description=MERCHANT, currency="HKD",
        account_id="cake_cc", before=_at(19, 4))
    assert found is None


# ─── End to end, through the webhook the real mail takes ─────────

@pytest.fixture
def world(monkeypatch, fake_ss):
    _tx_tab(fake_ss)
    ws_bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws_bc.update("A1:H1", [["Month", "Bucket", "Name", "Allocated", "DailyCap",
                            "Active", "Source", "X"]])
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
    monkeypatch.setattr(tg, "send_with_buttons", _send_text)
    for n in ("edit_message", "delete_message", "answer_callback"):
        monkeypatch.setattr(tg, n, _noop)

    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit",
                   currency="VND", source_keys=["email_cake:cake_cc"],
                   credit_limit=10_000_000, statement_day=18, due_day=4)
    sh.invalidate_accounts_cache()
    return {"sent": sent}


def _payload(subject, body):
    p = parse_email(CAKE_FROM, subject, body, "")
    assert p is not None, "the mail no longer parses"
    return p


def _live_rows():
    """Rows that still count as money. Column A (ID) is blank on appended rows,
    so presence is judged by the amount column."""
    return [r for r in sh._get_tx_rows()
            if len(r) > 7 and str(r[7]).strip() and not sh.is_cancelled(r)]


def _outstanding():
    sh.invalidate_accounts_cache()
    return sh.find_account_by_id("cake_cc")["outstanding_balance"]


def _categorize(row_num):
    """The webhook writes the row and shows the picker; the ledger is applied
    when the user picks a category. In the live account every one of these rows
    was auto-categorized by the "grab" keyword, so the ledger was applied."""
    from handlers.transaction import _apply_ledger_for_row
    _apply_ledger_for_row(row_num)


@pytest.mark.asyncio
async def test_purchase_then_cancellation_nets_to_zero(world):
    """The bug, end to end: before this, the reversal appended a SECOND
    expense, so a ride that cost nothing left 36.000đ of debt on the books."""
    import handlers.sepay as sepay

    now = datetime.now(TZ)
    purchase = _body(now.replace(hour=18, minute=23).strftime("%H:%M %d/%m/%Y"), "Thành công")
    cancel = _body(now.replace(hour=19, minute=4).strftime("%H:%M %d/%m/%Y"), "Thất bại")

    await sepay.handle_trusted_email_transaction(_payload(SUBJECT_OK, purchase))
    assert len(_live_rows()) == 1
    _categorize(2)
    assert _outstanding() == 18_000

    await sepay.handle_trusted_email_transaction(_payload(SUBJECT_CANCELLED, cancel))
    assert len(_live_rows()) == 0, "the reversal appended a row instead of reversing one"
    assert _outstanding() == 0, "the credit line was not given back"


@pytest.mark.asyncio
async def test_the_cancellation_is_recorded_and_the_owner_is_told(world):
    import handlers.sepay as sepay

    now = datetime.now(TZ)
    await sepay.handle_trusted_email_transaction(_payload(
        SUBJECT_OK, _body(now.replace(hour=18, minute=23).strftime("%H:%M %d/%m/%Y"), "Thành công")))
    await sepay.handle_trusted_email_transaction(_payload(
        SUBJECT_CANCELLED, _body(now.replace(hour=19, minute=4).strftime("%H:%M %d/%m/%Y"), "Thất bại")))

    assert any("huỷ" in t.lower() for t in world["sent"]), "the owner was never told"
    ws = sh._sheet(S.EXCLUDED_EVENTS)
    reasons = [r[7] for r in ws.get_all_values()[1:] if len(r) > 7]
    assert "cancellation_applied" in reasons


@pytest.mark.asyncio
async def test_a_redelivered_cancellation_changes_nothing(world):
    """Apps Script retries, and the claim cache cannot help here: no row is
    written, so after a restart it has nothing to recognise. A second pass must
    not walk back and cancel an earlier ride of the same price."""
    import handlers.sepay as sepay

    now = datetime.now(TZ)
    earlier = _body(now.replace(hour=9, minute=0).strftime("%H:%M %d/%m/%Y"), "Thành công")
    purchase = _body(now.replace(hour=18, minute=23).strftime("%H:%M %d/%m/%Y"), "Thành công")
    cancel = _body(now.replace(hour=19, minute=4).strftime("%H:%M %d/%m/%Y"), "Thất bại")

    await sepay.handle_trusted_email_transaction(_payload(SUBJECT_OK, earlier))
    await sepay.handle_trusted_email_transaction(_payload(SUBJECT_OK, purchase))
    assert len(_live_rows()) == 2

    await sepay.handle_trusted_email_transaction(_payload(SUBJECT_CANCELLED, cancel))
    assert len(_live_rows()) == 1
    after_first = _outstanding()

    sh._reset_processed_ref_cache()          # as if the process had restarted
    await sepay.handle_trusted_email_transaction(_payload(SUBJECT_CANCELLED, cancel))
    assert len(_live_rows()) == 1, "the replay cancelled a second, unrelated ride"
    assert _outstanding() == after_first


@pytest.mark.asyncio
async def test_a_declined_payment_writes_no_row_and_cancels_nothing(world):
    """Cake sends this same notice when a payment is refused outright. There is
    no purchase behind it and nothing moved."""
    import handlers.sepay as sepay

    now = datetime.now(TZ)
    await sepay.handle_trusted_email_transaction(_payload(
        SUBJECT_CANCELLED,
        _body(now.replace(hour=19, minute=4).strftime("%H:%M %d/%m/%Y"), "Thất bại")))

    assert len(_live_rows()) == 0
    ws = sh._sheet(S.EXCLUDED_EVENTS)
    reasons = [r[7] for r in ws.get_all_values()[1:] if len(r) > 7]
    assert "cancellation_no_match" in reasons
