"""tests/unit/test_zalo_tx_picker.py

TDD for Zalo numbered category picker (Phase 2).
Tests MUST fail on current code before Step 3-5 changes are added.
"""
import asyncio
from datetime import datetime, timedelta
import pytest
import pytz


# ─── helpers ─────────────────────────────────────────────────

def _seed_budget_sheet(fake_ss, month_key: str, buckets: list[dict]):
    """Write budget rows into the fake Budget Config sheet."""
    import sheets as sh
    from config import SHEETS as S

    ws = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    ws.append_row(["month_key", "id", "name", "allocated", "daily_cap", "active"])
    for b in buckets:
        ws.append_row([month_key, b["id"], b["name"], b.get("allocated", 0), "", "TRUE"])
    sh.invalidate_buckets_cache()
    return ws


def _ensure_sheets(fake_ss, *names):
    """Create sheets by name if they don't already exist."""
    for name in names:
        if name not in fake_ss._sheets:
            fake_ss.add_worksheet(name)


def _now_iso() -> str:
    """Return a tz-aware VN timestamp that passes the 10-minute stale guard.

    Using naive datetime.now() would be localized to Asia/Ho_Chi_Minh by the
    stale guard, making it appear ~7 hours old on a UTC CI runner and causing
    the webhook payload to be rejected as stale.
    """
    return datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).isoformat()


def _mock_resolve(monkeypatch):
    """Patch resolve_account to return a matched result."""
    from handlers.account_resolver import ResolveResult
    monkeypatch.setattr(
        "handlers.account_resolver.resolve_account",
        lambda data: ResolveResult(status="matched", account_id="acc1",
                                   source_key="key:1", identifier="id1"),
    )


def _mock_accounts(monkeypatch):
    """Patch prompt_new_account to no-op."""
    from handlers import accounts as accts_mod
    monkeypatch.setattr(accts_mod, "prompt_new_account",
                        lambda *a, **kw: asyncio.sleep(0))


def _base_payload(ref: str = "ref_001") -> dict:
    """Minimal valid SePay outgoing payload."""
    from config import SEPAY_SECRET  # read the live value — CI overrides it via env vars
    return {
        "apikey": SEPAY_SECRET,
        "transferType": "out",
        "transferAmount": 50000,
        "description": "GRAB FOOD",
        "referenceCode": ref,
        "transactionDate": _now_iso(),
    }


def _seed_sepay_stubs(monkeypatch, row_num: int = 5):
    """Patch sheets helpers that sepay.py calls before the picker branch."""
    import sheets as sh
    monkeypatch.setattr(sh, "match_keyword_rule", lambda desc: None)
    monkeypatch.setattr(sh, "tx_exists", lambda ref: False)
    monkeypatch.setattr(sh, "find_recent_duplicate", lambda *a, **kw: False)
    monkeypatch.setattr(sh, "append_transaction", lambda *a, **kw: row_num)
    monkeypatch.setattr(sh, "mark_ref_committed", lambda ref: None)
    monkeypatch.setattr(sh, "mark_ref_failed", lambda ref: None)


# ─── Test 1: Zalo-only uncategorized expense sends numbered menu ─

@pytest.mark.asyncio
async def test_zalo_only_uncategorized_sends_bucket_menu(fake_ss, monkeypatch):
    """Zalo-only + uncategorized expense -> numbered bucket menu sent to ZALO_CHAT_ID,
    state set to zalo_tx_pick with correct fields."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from handlers.sepay import handle_sepay_webhook
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = datetime.now().strftime("%Y-%m")

    monkeypatch.setattr(config, "TELEGRAM_ENABLED", False)
    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)
    # sepay.py imports these at module level — patch both
    monkeypatch.setattr("handlers.sepay.TELEGRAM_ENABLED", False)
    monkeypatch.setattr("handlers.sepay.ZALO_ENABLED", True)
    monkeypatch.setattr("handlers.sepay.ZALO_INTERACTIVE", True)
    monkeypatch.setattr("handlers.sepay.ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "coffee", "name": "Coffee"},
        {"id": "transport", "name": "Transport"},
    ])
    _ensure_sheets(fake_ss, S.TRANSACTIONS, S.BOT_STATE, S.KEYWORD_RULES)
    _seed_sepay_stubs(monkeypatch, row_num=5)
    _mock_resolve(monkeypatch)
    _mock_accounts(monkeypatch)

    zalo_sent = []

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)

    await handle_sepay_webhook(_base_payload())

    # A Zalo message must have been sent
    assert len(zalo_sent) > 0, "Expected at least one Zalo send (bucket menu)"

    # The menu message should list numbered options
    menu_msg = next((m for m in zalo_sent if "1." in m["text"]), None)
    assert menu_msg is not None, f"Expected numbered bucket menu. Got: {[m['text'] for m in zalo_sent]}"
    assert menu_msg["chat_id"] == ZALO_CHAT

    # State must be set to zalo_tx_pick with correct fields
    state = sh.get_state(ZALO_CHAT)
    assert state is not None, "Expected state to be set after sending picker"
    assert state.get("step") == "zalo_tx_pick"
    assert state.get("row_num") == 5
    assert state.get("amount") == 50000
    assert state.get("month_key") == MONTH
    assert isinstance(state.get("buckets"), list)
    assert len(state["buckets"]) == 3
    assert isinstance(state.get("queue"), list)
    assert state["queue"] == []


# ─── Test 2: numbered reply finalizes transaction ─────────────

@pytest.mark.asyncio
async def test_numbered_reply_finalizes_transaction(fake_ss, monkeypatch):
    """Reply '2' -> finalize_transaction with 2nd bucket; _apply_ledger_for_row
    invoked; plain-text summary sent; state cleared."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from main import _process_zalo
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = "2025-01"

    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_USER_ID", "user_abc")
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "coffee", "name": "Coffee"},
    ])
    _ensure_sheets(fake_ss, S.BOT_STATE, S.TRANSACTIONS)

    # Pre-set the picker state (tx_date required for correct daily summaries)
    sh.set_state(ZALO_CHAT, {
        "step": "zalo_tx_pick",
        "row_num": 5,
        "amount": 50000,
        "currency": "VND",
        "description": "GRAB FOOD",
        "tx_direction": "out",
        "month_key": MONTH,
        "tx_date": "2025-01-15T10:00:00",
        "buckets": [
            {"id": "food", "name": "Food"},
            {"id": "coffee", "name": "Coffee"},
        ],
        "queue": [],
    })

    finalize_calls = []
    ledger_calls = []
    zalo_sent = []

    def _mock_finalize(row_num, bucket_id, sub_label):
        finalize_calls.append({"row_num": row_num, "bucket_id": bucket_id})

    def _mock_ledger(row_num):
        ledger_calls.append(row_num)

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    monkeypatch.setattr(sh, "finalize_transaction", _mock_finalize)
    monkeypatch.setattr("handlers.transaction._apply_ledger_for_row", _mock_ledger)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)

    event = {
        "message": {
            "from": {"id": "user_abc", "is_bot": False},
            "chat": {"id": ZALO_CHAT, "chat_type": "PRIVATE"},
            "text": "2",
        }
    }
    await _process_zalo(event)

    assert len(finalize_calls) == 1, f"Expected finalize_transaction to be called once. Got: {finalize_calls}"
    assert finalize_calls[0]["bucket_id"] == "coffee", f"Reply '2' should pick bucket index 1 (coffee). Got: {finalize_calls[0]}"
    assert finalize_calls[0]["row_num"] == 5

    assert len(ledger_calls) == 1, f"Expected _apply_ledger_for_row to be called. Got: {ledger_calls}"
    assert ledger_calls[0] == 5

    # Summary message must have been sent
    assert len(zalo_sent) > 0, "Expected summary message to be sent after finalization"

    # State must be cleared (no longer zalo_tx_pick)
    final_state = sh.get_state(ZALO_CHAT)
    assert not final_state or final_state.get("step") != "zalo_tx_pick", \
        f"State should be cleared after finalization. Got: {final_state}"


# ─── Test 3: picker uses row's own month (not current month) ─

@pytest.mark.asyncio
async def test_picker_uses_row_month_not_current_month(fake_ss, monkeypatch):
    """Bucket lookup uses the tx's own month (from state['month_key']), not now().
    Seed buckets only for a specific month; verify state['month_key'] matches."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from main import _process_zalo
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    # Use a past month to prove the implementation doesn't fall back to now()
    PAST_MONTH = "2024-12"
    CURRENT_MONTH = datetime.now().strftime("%Y-%m")

    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_USER_ID", "user_abc")
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)

    # Seed buckets ONLY for the past month; current month has nothing
    _seed_budget_sheet(fake_ss, PAST_MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "old_cat", "name": "Old Category"},
    ])
    _ensure_sheets(fake_ss, S.BOT_STATE, S.TRANSACTIONS)

    # Pre-set picker state with PAST_MONTH and actual tx_date
    sh.set_state(ZALO_CHAT, {
        "step": "zalo_tx_pick",
        "row_num": 7,
        "amount": 30000,
        "currency": "VND",
        "description": "PAST TX",
        "tx_direction": "out",
        "month_key": PAST_MONTH,
        "tx_date": "2024-12-20T10:00:00",
        "buckets": [
            {"id": "food", "name": "Food"},
            {"id": "old_cat", "name": "Old Category"},
        ],
        "queue": [],
    })

    finalize_calls = []
    zalo_sent = []

    def _mock_finalize(row_num, bucket_id, sub_label):
        finalize_calls.append({"row_num": row_num, "bucket_id": bucket_id})

    def _mock_ledger(row_num):
        pass

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    monkeypatch.setattr(sh, "finalize_transaction", _mock_finalize)
    monkeypatch.setattr("handlers.transaction._apply_ledger_for_row", _mock_ledger)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)

    # Reply "2" to pick "old_cat" (the second bucket from PAST_MONTH)
    event = {
        "message": {
            "from": {"id": "user_abc", "is_bot": False},
            "chat": {"id": ZALO_CHAT, "chat_type": "PRIVATE"},
            "text": "2",
        }
    }
    await _process_zalo(event)

    # Must finalize against old_cat (PAST_MONTH's bucket), not current month's
    assert len(finalize_calls) == 1
    assert finalize_calls[0]["bucket_id"] == "old_cat", \
        f"Must use row's month bucket. Got: {finalize_calls[0]['bucket_id']}"

    # State must be cleared
    final_state = sh.get_state(ZALO_CHAT)
    assert not final_state or final_state.get("step") != "zalo_tx_pick"


# ─── Test 4: invalid reply reprompts with menu ────────────────

@pytest.mark.asyncio
async def test_invalid_reply_reprompts_menu(fake_ss, monkeypatch):
    """Reply '9' (out of range), '0', or non-numeric -> reprompt; state unchanged."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from main import _process_zalo
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = "2025-01"

    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_USER_ID", "user_abc")
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "coffee", "name": "Coffee"},
    ])
    _ensure_sheets(fake_ss, S.BOT_STATE, S.TRANSACTIONS)

    initial_state = {
        "step": "zalo_tx_pick",
        "row_num": 5,
        "amount": 50000,
        "currency": "VND",
        "description": "GRAB",
        "tx_direction": "out",
        "month_key": MONTH,
        "tx_date": "2025-01-15T10:00:00",
        "buckets": [
            {"id": "food", "name": "Food"},
            {"id": "coffee", "name": "Coffee"},
        ],
        "queue": [],
    }
    sh.set_state(ZALO_CHAT, initial_state.copy())

    finalize_calls = []
    zalo_sent = []

    def _mock_finalize(row_num, bucket_id, sub_label):
        finalize_calls.append(bucket_id)

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    monkeypatch.setattr(sh, "finalize_transaction", _mock_finalize)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)

    for bad_reply in ("9", "abc", "0"):
        zalo_sent.clear()
        finalize_calls.clear()
        sh.set_state(ZALO_CHAT, initial_state.copy())

        event = {
            "message": {
                "from": {"id": "user_abc", "is_bot": False},
                "chat": {"id": ZALO_CHAT, "chat_type": "PRIVATE"},
                "text": bad_reply,
            }
        }
        await _process_zalo(event)

        assert finalize_calls == [], \
            f"Reply {bad_reply!r}: finalize_transaction must NOT be called"
        assert len(zalo_sent) > 0, \
            f"Reply {bad_reply!r}: expected a reprompt message to be sent"
        state = sh.get_state(ZALO_CHAT)
        assert state is not None and state.get("step") == "zalo_tx_pick", \
            f"Reply {bad_reply!r}: state step should remain 'zalo_tx_pick'. Got: {state}"


# ─── Test 5a: 2nd tx while first pending -> appended to queue ─

@pytest.mark.asyncio
async def test_second_tx_while_pending_queues(fake_ss, monkeypatch):
    """2nd uncategorized tx while one is pending -> appended to queue,
    state not clobbered."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from handlers.sepay import handle_sepay_webhook
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = datetime.now().strftime("%Y-%m")

    monkeypatch.setattr(config, "TELEGRAM_ENABLED", False)
    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)
    # sepay.py imports these at module level — patch both
    monkeypatch.setattr("handlers.sepay.TELEGRAM_ENABLED", False)
    monkeypatch.setattr("handlers.sepay.ZALO_ENABLED", True)
    monkeypatch.setattr("handlers.sepay.ZALO_INTERACTIVE", True)
    monkeypatch.setattr("handlers.sepay.ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
    ])
    _ensure_sheets(fake_ss, S.TRANSACTIONS, S.BOT_STATE, S.KEYWORD_RULES)

    zalo_sent = []
    row_counter = [4]

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    def _mock_append(*a, **kw):
        row_counter[0] += 1
        return row_counter[0]

    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)
    monkeypatch.setattr(sh, "match_keyword_rule", lambda desc: None)
    monkeypatch.setattr(sh, "tx_exists", lambda ref: False)
    monkeypatch.setattr(sh, "find_recent_duplicate", lambda *a, **kw: False)
    monkeypatch.setattr(sh, "append_transaction", _mock_append)
    monkeypatch.setattr(sh, "mark_ref_committed", lambda ref: None)
    monkeypatch.setattr(sh, "mark_ref_failed", lambda ref: None)
    _mock_resolve(monkeypatch)
    _mock_accounts(monkeypatch)

    # First tx
    payload1 = _base_payload("ref_001")
    payload1["description"] = "TX ONE"
    await handle_sepay_webhook(payload1)

    state_after_first = sh.get_state(ZALO_CHAT)
    assert state_after_first is not None, "State must be set after first tx"
    assert state_after_first.get("step") == "zalo_tx_pick"
    first_row_num = state_after_first["row_num"]

    # Second tx while first is still pending
    payload2 = _base_payload("ref_002")
    payload2["description"] = "TX TWO"
    payload2["transferAmount"] = 30000
    await handle_sepay_webhook(payload2)

    state_after_second = sh.get_state(ZALO_CHAT)
    assert state_after_second is not None
    # Original row_num must not be clobbered
    assert state_after_second["row_num"] == first_row_num, \
        f"State was clobbered! row_num changed from {first_row_num} to {state_after_second['row_num']}"
    assert state_after_second.get("step") == "zalo_tx_pick"

    queue = state_after_second.get("queue", [])
    assert len(queue) == 1, f"Expected 1 queued item, got {queue}"
    assert queue[0]["description"] == "TX TWO"


# ─── Test 5b: queue promoted after first resolved ─────────────

@pytest.mark.asyncio
async def test_queue_promoted_after_first_resolved(fake_ss, monkeypatch):
    """After first tx resolved, queued row is promoted: menu re-sent,
    state = that row, queue = []."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from main import _process_zalo
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = "2025-01"

    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_USER_ID", "user_abc")
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "coffee", "name": "Coffee"},
    ])
    _ensure_sheets(fake_ss, S.BOT_STATE, S.TRANSACTIONS)

    # State: first tx pending, second in queue (both with tx_date for daily summaries)
    sh.set_state(ZALO_CHAT, {
        "step": "zalo_tx_pick",
        "row_num": 5,
        "amount": 50000,
        "currency": "VND",
        "description": "TX ONE",
        "tx_direction": "out",
        "month_key": MONTH,
        "tx_date": "2025-01-15T10:00:00",
        "buckets": [
            {"id": "food", "name": "Food"},
            {"id": "coffee", "name": "Coffee"},
        ],
        "queue": [{
            "row_num": 6,
            "amount": 30000,
            "currency": "VND",
            "description": "TX TWO",
            "tx_direction": "out",
            "month_key": MONTH,
            "tx_date": "2025-01-15T10:05:00",
            "buckets": [
                {"id": "food", "name": "Food"},
                {"id": "coffee", "name": "Coffee"},
            ],
        }],
    })

    finalize_calls = []
    zalo_sent = []

    def _mock_finalize(row_num, bucket_id, sub_label):
        finalize_calls.append({"row_num": row_num, "bucket_id": bucket_id})

    def _mock_ledger(row_num):
        pass

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    monkeypatch.setattr(sh, "finalize_transaction", _mock_finalize)
    monkeypatch.setattr("handlers.transaction._apply_ledger_for_row", _mock_ledger)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)

    # Resolve first tx by replying "1" (Food)
    event = {
        "message": {
            "from": {"id": "user_abc", "is_bot": False},
            "chat": {"id": ZALO_CHAT, "chat_type": "PRIVATE"},
            "text": "1",
        }
    }
    await _process_zalo(event)

    # First tx finalized
    assert len(finalize_calls) == 1
    assert finalize_calls[0]["row_num"] == 5
    assert finalize_calls[0]["bucket_id"] == "food"

    # State promoted to second tx
    state = sh.get_state(ZALO_CHAT)
    assert state is not None, "Expected state to be set for promoted queue item"
    assert state.get("step") == "zalo_tx_pick", \
        f"Promoted state should be zalo_tx_pick. Got: {state}"
    assert state.get("row_num") == 6, f"Promoted row_num should be 6. Got: {state.get('row_num')}"
    assert state.get("description") == "TX TWO"
    assert state.get("queue") == []

    # A numbered menu for TX TWO must have been sent
    menu_sent = any("1." in m["text"] for m in zalo_sent)
    assert menu_sent, \
        f"Expected numbered menu for promoted TX TWO. Messages: {[m['text'] for m in zalo_sent]}"


# ─── Test 6: mutual exclusion — Telegram-enabled skips Zalo picker ─

@pytest.mark.asyncio
async def test_telegram_enabled_no_zalo_picker(fake_ss, monkeypatch):
    """Both channels enabled -> Telegram picker fires; no zalo_tx_pick state set."""
    import config
    import zalo_api as zalo_mod
    import telegram_api as tg
    import sheets as sh
    from handlers.sepay import handle_sepay_webhook
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    CHAT_ID_TG = "456"
    MONTH = datetime.now().strftime("%Y-%m")

    monkeypatch.setattr(config, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "CHAT_ID", CHAT_ID_TG)
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
    ])
    _ensure_sheets(fake_ss, S.TRANSACTIONS, S.BOT_STATE, S.KEYWORD_RULES)
    _seed_sepay_stubs(monkeypatch, row_num=5)
    _mock_resolve(monkeypatch)
    _mock_accounts(monkeypatch)

    zalo_sent = []
    tg_buttons_sent = []

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append(text)

    async def _mock_tg_buttons(text, buttons):
        tg_buttons_sent.append(text)

    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)
    monkeypatch.setattr(tg, "send_with_buttons", _mock_tg_buttons)

    await handle_sepay_webhook(_base_payload("ref_tg_001"))

    # Telegram picker must fire
    assert len(tg_buttons_sent) > 0, "Expected Telegram send_with_buttons to be called"

    # Zalo picker state must NOT be set
    zalo_state = sh.get_state(ZALO_CHAT)
    assert not zalo_state or zalo_state.get("step") != "zalo_tx_pick", \
        f"Zalo picker state must NOT be set when Telegram is enabled. Got: {zalo_state}"


# ─── Test 7: state key routing end-to-end (STATE_KEY_MISMATCH guard) ─

@pytest.mark.asyncio
async def test_state_key_routing_end_to_end(fake_ss, monkeypatch):
    """Picker state written by SePay webhook (keyed by ZALO_CHAT_ID) must be
    readable by _process_zalo (keyed by incoming chat_id).

    For private Zalo chats the invariant is: ZALO_CHAT_ID == incoming chat_id.
    This test proves the routing works end-to-end through both paths.
    """
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from handlers.sepay import handle_sepay_webhook
    from main import _process_zalo
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = datetime.now().strftime("%Y-%m")

    monkeypatch.setattr(config, "TELEGRAM_ENABLED", False)
    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_USER_ID", "user_abc")
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)
    monkeypatch.setattr("handlers.sepay.TELEGRAM_ENABLED", False)
    monkeypatch.setattr("handlers.sepay.ZALO_ENABLED", True)
    monkeypatch.setattr("handlers.sepay.ZALO_INTERACTIVE", True)
    monkeypatch.setattr("handlers.sepay.ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "coffee", "name": "Coffee"},
    ])
    _ensure_sheets(fake_ss, S.TRANSACTIONS, S.BOT_STATE, S.KEYWORD_RULES)
    _seed_sepay_stubs(monkeypatch, row_num=5)
    _mock_resolve(monkeypatch)
    _mock_accounts(monkeypatch)

    finalize_calls = []
    zalo_sent = []

    def _mock_finalize(row_num, bucket_id, sub_label):
        finalize_calls.append({"row_num": row_num, "bucket_id": bucket_id})

    def _mock_ledger(row_num):
        pass

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    monkeypatch.setattr(sh, "finalize_transaction", _mock_finalize)
    monkeypatch.setattr("handlers.transaction._apply_ledger_for_row", _mock_ledger)
    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)

    # Phase 1: SePay webhook creates the picker state under ZALO_CHAT_ID
    await handle_sepay_webhook(_base_payload("ref_e2e_001"))

    picker_state = sh.get_state(ZALO_CHAT)
    assert picker_state is not None, "SePay webhook must set picker state under ZALO_CHAT_ID"
    assert picker_state.get("step") == "zalo_tx_pick"

    # Phase 2: User reply arrives via Zalo webhook with chat_id == ZALO_CHAT_ID
    # This is the invariant: ZALO_CHAT_ID (outbound key) == event chat_id (inbound key).
    reply_event = {
        "message": {
            "from": {"id": "user_abc", "is_bot": False},
            "chat": {"id": ZALO_CHAT, "chat_type": "PRIVATE"},
            "text": "1",
        }
    }
    await _process_zalo(reply_event)

    # The picker must have routed correctly (finalize called, not the help menu)
    assert len(finalize_calls) == 1, \
        f"Reply must route to picker. finalize_calls={finalize_calls}. " \
        f"If 0, state key mismatch: picker stored under ZALO_CHAT_ID but reply keyed differently."
    assert finalize_calls[0]["bucket_id"] == "food"


# ─── Test 9: slash commands blocked while picker active ───────

@pytest.mark.asyncio
async def test_slash_commands_blocked_while_picker_active(fake_ss, monkeypatch):
    """While zalo_tx_pick is active, non-cancel commands must NOT clobber state
    and must reprompt the picker menu."""
    import config
    import zalo_api as zalo_mod
    import sheets as sh
    from main import _process_zalo
    from config import SHEETS as S

    ZALO_CHAT = "zalo_chat_123"
    MONTH = "2025-01"

    monkeypatch.setattr(config, "ZALO_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_INTERACTIVE", True)
    monkeypatch.setattr(config, "ZALO_USER_ID", "user_abc")
    monkeypatch.setattr(config, "ZALO_CHAT_ID", ZALO_CHAT)

    _seed_budget_sheet(fake_ss, MONTH, [
        {"id": "food", "name": "Food"},
        {"id": "coffee", "name": "Coffee"},
    ])
    _ensure_sheets(fake_ss, S.BOT_STATE)

    picker_state = {
        "step": "zalo_tx_pick",
        "row_num": 5,
        "amount": 50000,
        "currency": "VND",
        "description": "GRAB",
        "tx_direction": "out",
        "month_key": MONTH,
        "tx_date": "2025-01-15T10:00:00",
        "buckets": [
            {"id": "food", "name": "Food"},
            {"id": "coffee", "name": "Coffee"},
        ],
        "queue": [],
    }
    sh.set_state(ZALO_CHAT, picker_state.copy())

    zalo_sent = []
    manage_called = []

    async def _mock_zalo_send(text, chat_id=None):
        zalo_sent.append({"text": text, "chat_id": chat_id})

    async def _mock_mg_show_list(chat_id):
        manage_called.append(chat_id)

    monkeypatch.setattr(zalo_mod, "send_text", _mock_zalo_send)
    monkeypatch.setattr("main._zalo_mg_show_list", _mock_mg_show_list)

    event = {
        "message": {
            "from": {"id": "user_abc", "is_bot": False},
            "chat": {"id": ZALO_CHAT, "chat_type": "PRIVATE"},
            "text": "/manage",
        }
    }
    await _process_zalo(event)

    # /manage must NOT have dispatched
    assert manage_called == [], "/manage must not run while picker is active"

    # State must be unchanged
    state = sh.get_state(ZALO_CHAT)
    assert state is not None and state.get("step") == "zalo_tx_pick", \
        f"Picker state must be preserved. Got: {state}"
    assert state.get("row_num") == 5

    # A reprompt message with the menu must have been sent
    assert len(zalo_sent) > 0, "Expected reprompt message to be sent"
    assert "1." in zalo_sent[0]["text"], \
        f"Expected numbered menu in reprompt. Got: {zalo_sent[0]['text']!r}"
