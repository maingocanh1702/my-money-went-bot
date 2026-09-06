import pytest

import sheets as sh
from config import SHEETS as S


TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id", "ledger_tx_type", "linked_tx_row",
    "ledger_applied", "account_source_key",
]


def _seed_tx_table(fake_ss):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:U1", [TX_HEADER])
    return ws


def _seed_budget_config(fake_ss, rows=None):
    ws = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    for i, row in enumerate(rows or [], 2):
        ws.update(f"A{i}:F{i}", [row])
    sh._buckets_cache.clear()
    return ws


@pytest.fixture
def bot_state_tab(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "ts"]])
    return ws


def test_zalo_extracts_result_wrapped_update():
    import main

    update = main._extract_zalo_update({
        "ok": True,
        "result": {
            "event_name": "message.text.received",
            "message": {
                "from": {"id": "user-1"},
                "chat": {"id": "chat-1"},
                "text": "/start",
            },
        },
    })

    assert update["event_name"] == "message.text.received"
    assert update["message"]["chat"]["id"] == "chat-1"


def test_zalo_secret_token_required_when_configured(monkeypatch):
    import main

    monkeypatch.setattr(main, "ZALO_SECRET_TOKEN", "expected")
    monkeypatch.setattr(main, "ZALO_ALLOW_UNVERIFIED_WEBHOOK", False, raising=False)

    assert main._verify_zalo_webhook({"x-bot-api-secret-token": "expected"})
    assert not main._verify_zalo_webhook({"x-bot-api-secret-token": "wrong"})
    assert not main._verify_zalo_webhook({})


def test_zalo_secret_token_fail_closed_without_explicit_dev_opt_in(monkeypatch):
    import main

    monkeypatch.setattr(main, "ZALO_SECRET_TOKEN", "")
    monkeypatch.setattr(main, "ZALO_ALLOW_UNVERIFIED_WEBHOOK", False, raising=False)
    assert not main._verify_zalo_webhook({})

    monkeypatch.setattr(main, "ZALO_ALLOW_UNVERIFIED_WEBHOOK", True, raising=False)
    assert main._verify_zalo_webhook({})


def test_zalo_button_render_includes_new_category():
    import messenger

    buttons = [[
        {"text": "Food", "callback_data": "p_12_food"},
        {"text": "New", "callback_data": "p_12_new"},
        {"text": "Transport", "callback_data": "p_12_transport"},
    ]]

    assert messenger._buttons_to_numbered_text(buttons) == "1. Food\n2. Transport\n0. New"
    assert messenger.buttons_to_bucket_map(buttons) == [
        {"id": "food", "name": "Food"},
        {"id": "transport", "name": "Transport"},
    ]


@pytest.mark.asyncio
async def test_zalo_category_reply_zero_starts_new_category_flow(
    fake_ss, bot_state_tab, monkeypatch,
):
    import main

    sent = []

    async def fake_zalo_send(chat_id, text):
        sent.append((chat_id, text))

    row = [""] * 14
    row[13] = "FALSE"
    monkeypatch.setattr(main.sh, "get_transaction_row", lambda row_num: row)
    monkeypatch.setattr(main, "_zalo_send", fake_zalo_send)

    state_key = "zalo:chat-1"
    state = {
        "step": "await_zalo_parent",
        "row_num": 12,
        "buckets": [{"id": "food", "name": "Food"}],
    }

    await main._handle_zalo_category_reply("chat-1", 0, state, state_key)

    assert sh.get_state(state_key)["step"] == "await_zalo_new_cat_name"
    assert sent == [("chat-1", "Tên category mới? (VD: Gaming, Travel)")]


@pytest.mark.asyncio
async def test_zalo_category_reply_stale_new_bucket_starts_new_category_flow(
    fake_ss, bot_state_tab, monkeypatch,
):
    import main

    sent = []
    finalized = []

    async def fake_zalo_send(chat_id, text):
        sent.append((chat_id, text))

    async def fake_finalize(*args):
        finalized.append(args)

    row = [""] * 14
    row[13] = "FALSE"
    monkeypatch.setattr(main.sh, "get_transaction_row", lambda row_num: row)
    monkeypatch.setattr(main, "_zalo_send", fake_zalo_send)
    monkeypatch.setattr(main, "_zalo_finalize_transaction", fake_finalize)

    state_key = "zalo:chat-1"
    state = {
        "step": "await_zalo_parent",
        "row_num": 12,
        "buckets": [
            {"id": "food", "name": "Food"},
            {"id": "new", "name": "New"},
        ],
    }

    await main._handle_zalo_category_reply("chat-1", 2, state, state_key)

    assert sh.get_state(state_key)["step"] == "await_zalo_new_cat_name"
    assert sent == [("chat-1", "Tên category mới? (VD: Gaming, Travel)")]
    assert finalized == []


@pytest.mark.asyncio
async def test_zalo_start_clears_stale_state(fake_ss, bot_state_tab, monkeypatch):
    import main

    monkeypatch.setattr(main, "ZALO_CHAT_ID", "1000000000000000001")
    sh.set_state("zalo:1000000000000000001", {"step": "zalo_manage", "month_key": "2026-06"})

    sent = []

    async def fake_send(text, channel=None, recipient_id=None):
        sent.append(text)

    monkeypatch.setattr(main.messenger, "send_text", fake_send)

    await main._handle_zalo_text({
        "message": {
            "chat": {"id": "1000000000000000001"},
            "text": "/start",
        },
    })

    assert sh.get_state("zalo:1000000000000000001") == {}
    assert sent and "Financial Tracking Bot" in sent[0]


@pytest.mark.asyncio
async def test_auto_alloc_fallback_zalo_message_when_no_previous_budget(
    fake_ss, bot_state_tab, monkeypatch,
):
    import main

    _seed_budget_config(fake_ss)
    monkeypatch.setattr(main, "ZALO_ENABLED", True)
    monkeypatch.setattr(main, "ZALO_CHAT_ID", "1000000000000000001")
    monkeypatch.setattr(sh, "fmt_month", lambda dt: "2026-06" if dt.month == 6 else "2026-05")

    tg_sent = []
    zalo_sent = []

    async def fake_tg_send(text, chat_id=None):
        tg_sent.append(text)

    async def fake_zalo_send(text, channel=None, recipient_id=None):
        zalo_sent.append(text)

    monkeypatch.setattr(main.tg, "send_text", fake_tg_send)
    monkeypatch.setattr(main.messenger, "send_text", fake_zalo_send)

    await main._auto_alloc_fallback()

    assert tg_sent and "không có budget tháng trước" in tg_sent[0]
    assert zalo_sent and "tracking mode" in zalo_sent[0]
    assert "Tự động giữ budget tháng" not in zalo_sent[0]


@pytest.mark.asyncio
async def test_zalo_inline_keyboard_fallback_on_api_reject(monkeypatch):
    """When Zalo API rejects reply_markup, fall back to numbered text."""
    import httpx
    import messenger

    messenger.reset_zalo_inline_cache()
    monkeypatch.setattr(messenger, "ZALO_INLINE_KEYBOARD", True)
    monkeypatch.setattr(messenger, "ZALO_BOT_TOKEN", "test-token")

    sent_bodies = []

    async def fake_post(self, url, **kwargs):
        body = kwargs.get("json", {})
        sent_bodies.append(body)
        # If reply_markup present → reject (simulate API not supporting it)
        if "reply_markup" in body:
            return httpx.Response(200, json={"ok": False, "error": "unsupported"}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "1"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    buttons = [[{"text": "Food", "callback_data": "p_5_food"}]]
    await messenger.send_with_buttons(
        "Pick one:", buttons, channel="zalo", recipient_id="chat-1"
    )

    # First call: tried inline keyboard (rejected)
    # Second call: sent numbered text fallback
    assert len(sent_bodies) == 2
    assert "reply_markup" in sent_bodies[0]
    assert "reply_markup" not in sent_bodies[1]
    assert "1. Food" in sent_bodies[1]["text"]

    messenger.reset_zalo_inline_cache()


@pytest.mark.asyncio
async def test_zalo_inline_keyboard_accepted(monkeypatch):
    """When Zalo API accepts reply_markup, no fallback needed."""
    import httpx
    import messenger

    messenger.reset_zalo_inline_cache()
    monkeypatch.setattr(messenger, "ZALO_INLINE_KEYBOARD", True)
    monkeypatch.setattr(messenger, "ZALO_BOT_TOKEN", "test-token")

    sent_bodies = []

    async def fake_post(self, url, **kwargs):
        body = kwargs.get("json", {})
        sent_bodies.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "1"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    buttons = [[{"text": "Food", "callback_data": "p_5_food"}]]
    await messenger.send_with_buttons(
        "Pick one:", buttons, channel="zalo", recipient_id="chat-1"
    )

    # Only one call — inline keyboard accepted, no fallback
    assert len(sent_bodies) == 1
    assert "reply_markup" in sent_bodies[0]

    messenger.reset_zalo_inline_cache()


@pytest.mark.asyncio
async def test_zalo_inline_keyboard_disabled_skips_attempt(monkeypatch):
    """When ZALO_INLINE_KEYBOARD=false, go straight to numbered text."""
    import httpx
    import messenger

    messenger.reset_zalo_inline_cache()
    monkeypatch.setattr(messenger, "ZALO_INLINE_KEYBOARD", False)
    monkeypatch.setattr(messenger, "ZALO_BOT_TOKEN", "test-token")

    sent_bodies = []

    async def fake_post(self, url, **kwargs):
        body = kwargs.get("json", {})
        sent_bodies.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "1"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    buttons = [[{"text": "Food", "callback_data": "p_5_food"}]]
    await messenger.send_with_buttons(
        "Pick one:", buttons, channel="zalo", recipient_id="chat-1"
    )

    # Only numbered text, no inline attempt
    assert len(sent_bodies) == 1
    assert "reply_markup" not in sent_bodies[0]
    assert "1. Food" in sent_bodies[0]["text"]

    messenger.reset_zalo_inline_cache()


def test_zalo_extract_callback_query():
    """callback_query events are extracted from Zalo webhook payloads."""
    import main

    update = main._extract_zalo_update({
        "ok": True,
        "result": {
            "callback_query": {
                "id": "cb-1",
                "data": "p_5_food",
                "message": {"chat": {"id": "chat-1"}, "message_id": "msg-1"},
            },
        },
    })

    cb = update.get("callback_query")
    assert cb is not None
    assert cb["data"] == "p_5_food"
    assert cb["message"]["chat"]["id"] == "chat-1"


@pytest.mark.asyncio
async def test_zalo_setup_pending_account_starts_wizard(fake_ss, bot_state_tab, monkeypatch):
    import main

    sent = []

    async def fake_send(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(main, "_zalo_send", fake_send)
    setup_key = sh.add_pending_account("email_cake:cake_cc", "Cake credit card", 9)

    await main._zalo_handle_account_setup_action(
        "1000000000000000001",
        "setup",
        setup_key,
        "zalo:1000000000000000001",
    )

    state = sh.get_state("zalo:1000000000000000001")
    assert state["step"] == "zalo_accounts_name"
    assert state["pending_source_key"] == "email_cake:cake_cc"
    assert state["new_acct_row_num"] == 9
    assert "Nhập tên hiển thị" in sent[-1][1]


def test_zalo_backfill_unconfirmed_tx_does_not_apply_ledger(fake_ss):
    import main

    _seed_tx_table(fake_ss)
    sh.add_account(
        account_id="cake_visa",
        name="Cake Visa",
        acc_type="credit",
        currency="VND",
        source_keys=["email_cake:cake_cc"],
        credit_limit=30000000,
    )
    row_num = sh.append_transaction(
        tx_date="2026-05-29T01:00:00",
        description="CARD POS",
        amount=150000,
        ref_code="email-1",
        month_key="2026-05",
        account_source_key="email_cake:cake_cc",
    )

    assert main._zalo_backfill_account("cake_visa", "email_cake:cake_cc", row_num) == 1
    row = sh._sheet(S.TRANSACTIONS).row_values(row_num)
    assert row[16] == "cake_visa"
    assert row[19] == "FALSE"
    assert sh._get_ledger_rows() == []


@pytest.mark.asyncio
async def test_zalo_auto_cat_sends_logged_month_total(fake_ss, bot_state_tab, monkeypatch):
    from datetime import datetime
    import pytz

    import handlers.sepay as sepay

    _seed_tx_table(fake_ss)

    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    tx_date = datetime.now(tz)
    month_key = sh.fmt_month(tx_date)

    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    bc.update("A2:F2", [[month_key, "coffee", "☕ Coffee", 0, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    kw = fake_ss.add_worksheet(S.KEYWORD_RULES)
    kw.update("A1:E1", [["keyword", "bucket_id", "sub_label", "active", "created_at"]])
    kw.update("A2:E2", [["tch", "coffee", "", "TRUE", ""]])
    sh.invalidate_keyword_rules_cache()

    async def fake_tg_send_text(*args, **kwargs):
        return {"ok": True, "result": {"message_id": 1}}

    async def fake_tg_send_with_buttons(*args, **kwargs):
        return {"ok": True, "result": {"message_id": 2}}

    monkeypatch.setattr(sepay.tg, "send_text", fake_tg_send_text)
    monkeypatch.setattr(sepay.tg, "send_with_buttons", fake_tg_send_with_buttons)
    monkeypatch.setattr(sepay, "ZALO_ENABLED", True)
    monkeypatch.setattr(sepay, "ZALO_CHAT_ID", "1000000000000000001")

    zalo_sent = []

    async def fake_zalo_send(text, channel=None, recipient_id=None):
        zalo_sent.append(text)

    monkeypatch.setattr(sepay.messenger, "send_text", fake_zalo_send)

    await sepay.handle_sepay_webhook({
        "transferType": "out",
        "transferAmount": 10_000,
        "content": "BankAPINotify MAI NGOC ANH chuyen tien tch",
        "referenceCode": "ZALO_AUTO_CAT_TOTAL_1",
        "transactionDate": tx_date.isoformat(),
    })

    assert any("🤖" in msg and "tch" in msg for msg in zalo_sent)
    summary = next(msg for msg in zalo_sent if msg.startswith("Logged:"))
    assert "Logged: ☕ Coffee" in summary
    assert "-10.000đ" in summary
    assert "☕ Coffee: tổng tháng này 10.000đ" in summary
    assert "Sai mục? gửi /recat 2" in summary


@pytest.mark.asyncio
async def test_zalo_manual_category_reply_sends_logged_month_total(
    fake_ss, bot_state_tab, monkeypatch,
):
    from datetime import datetime
    import pytz

    import main

    _seed_tx_table(fake_ss)

    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    tx_date = datetime.now(tz)
    month_key = sh.fmt_month(tx_date)

    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    bc.update("A2:F2", [[month_key, "coffee", "☕ Coffee", 0, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    row_num = sh.append_transaction(
        tx_date=tx_date.isoformat(),
        description="manual coffee",
        amount=12_000,
        ref_code="ZALO_MANUAL_TOTAL_1",
        month_key=month_key,
    )

    sent = []

    async def fake_send(text, channel=None, recipient_id=None):
        sent.append(text)

    monkeypatch.setattr(main.messenger, "send_text", fake_send)

    await main._zalo_finalize_transaction(
        "1000000000000000001",
        row_num,
        "coffee",
        "",
        {
            "row_num": row_num,
            "amount": 12_000,
            "currency": "VND",
            "tx_direction": "out",
            "tx_date": tx_date.isoformat(),
        },
        "zalo:1000000000000000001",
    )

    assert sent[-1].startswith("Logged: ☕ Coffee")
    assert "-12.000đ" in sent[-1]
    assert "☕ Coffee: tổng tháng này 12.000đ" in sent[-1]
    assert f"Sai mục? gửi /recat {row_num}" in sent[-1]


@pytest.mark.asyncio
async def test_zalo_manage_clones_previous_month_before_defaults(
    fake_ss, bot_state_tab, monkeypatch,
):
    import main

    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    bc.update("A2:F2", [["2026-05", "food", "🍕 Food", 2_000_000, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    monkeypatch.setattr(sh, "fmt_month", lambda _dt: "2026-06")

    sent = []

    async def fake_send(text, channel=None, recipient_id=None):
        sent.append(text)

    monkeypatch.setattr(main.messenger, "send_text", fake_send)

    await main._zalo_cmd_manage("1000000000000000001", "zalo:1000000000000000001")

    buckets = sh.get_active_buckets("2026-06", force_refresh=True)
    assert [b["id"] for b in buckets] == ["food"]
    assert "Food" in sent[0]
    assert "Daily Spending" not in sent[0]


@pytest.mark.asyncio
async def test_zalo_allocate_clones_previous_month_before_defaults(
    fake_ss, bot_state_tab, monkeypatch,
):
    import main

    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    bc.update("A2:F2", [["2026-05", "food", "🍕 Food", 2_000_000, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    monkeypatch.setattr(sh, "fmt_month", lambda _dt: "2026-06")

    sent = []

    async def fake_send(text, channel=None, recipient_id=None):
        sent.append(text)

    monkeypatch.setattr(main.messenger, "send_text", fake_send)

    await main._zalo_cmd_allocate("1000000000000000001", "zalo:1000000000000000001")

    buckets = sh.get_active_buckets("2026-06", force_refresh=True)
    assert [b["id"] for b in buckets] == ["food"]
    assert "Food" in sent[0]
    assert "Daily Spending" not in sent[0]
