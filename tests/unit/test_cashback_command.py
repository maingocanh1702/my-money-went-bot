"""Phase B Phase 2 — /cashback command core (channel-agnostic helpers).

The Telegram/Zalo glue is thin; the testable core is seed_cake_card (creates the
full BRD §4.4 config), list_cashback_cards (credit-only), and recompute_cycle.
"""
import pytest
import sheets as sh
from config import SHEETS as S
import handlers.cashback as cb


@pytest.fixture(autouse=True)
def _reset(fake_ss):
    sh.invalidate_cashback_caches()
    sh.invalidate_accounts_cache()  # fake_ss is fresh per test; drop stale account cache
    yield


def _setup_tx_tab():
    ws = sh._get_spreadsheet().add_worksheet(S.TRANSACTIONS)
    ws.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    return ws


def _seed_card(account_id="cake_cc"):
    sh.add_account(account_id=account_id, name="Cake Freedom", acc_type="credit",
                   currency="VND", source_keys=[f"email_cake:{account_id}"],
                   credit_limit=50_000_000, statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()


# ── seed cake ─────────────────────────────────────────────────────

def test_seed_cake_creates_full_config(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")

    rules = sh.get_cashback_rules("cake_cc")
    assert len(rules) == 5
    assert {r["match_value"] for r in rules} == {"5262", "4722", "5611", "5411", "4121"}
    r5411 = next(r for r in rules if r["match_value"] == "5411")
    assert r5411["max_eligible_tx_per_day"] == 1
    assert all(r["monthly_cap"] == 200000 for r in rules)
    # Rate must INHERIT the card config (blank), not be hardcoded (BRD §6.1).
    assert all(r["rate"] is None for r in rules)

    cfg = sh.get_card_config("cake_cc")
    assert cfg["cashback_rate"] == 0.20
    assert cfg["min_eligible_spend"] == 5_000_000
    assert cfg["active"] is True

    tiers = sh.get_cashback_tiers("cakefreedom")
    assert len(tiers) == 2

    seeded = {m["mcc_code"] for m in sh.get_mcc_map()}
    assert {"5262", "4722", "5611", "5411", "4121"} <= seeded
    assert sh.match_mcc("WCM_WINMART 6992 HOMYLAND HCM")["mcc_code"] == "5411"


def test_seed_cake_rejects_non_credit_account(fake_ss):
    # Codex round 04 [P2]: seeding a non-credit (or unknown) account must write
    # nothing — no orphan config/rules.
    sh.add_account(account_id="tcb", name="TCB", acc_type="bank", currency="VND",
                   source_keys=["sepay:1"], starting_balance=0)
    sh.invalidate_accounts_cache()
    res = cb.seed_cake_card("tcb")
    assert res["ok"] is False
    assert sh.get_card_config("tcb") is None
    assert sh.get_cashback_rules("tcb") == []


def test_seed_cake_idempotent(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    cb.seed_cake_card("cake_cc")
    assert len(sh.get_cashback_rules("cake_cc")) == 5
    assert len(sh.get_cashback_tiers("cakefreedom")) == 2


# ── MCC pattern listing (🏷️ MCC button) ──────────────────────────

def test_mcc_overview_empty_when_no_patterns(fake_ss):
    assert "Chưa có pattern" in cb.mcc_pattern_overview_text()


def test_mcc_overview_groups_patterns_by_mcc(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    s = cb.mcc_pattern_overview_text("cake_cc")
    # header counts: 23 seeded patterns across 5 MCCs
    assert "5 MCC" in s
    # grouped under the card's rule name (not bare MCC code) + emoji prefix
    assert "🛒" in s and "Siêu thị" in s and "(5411)" in s
    # patterns shown uppercased, comma-joined, on the same line as their MCC
    line_5411 = next(ln for ln in s.splitlines() if "(5411)" in ln)
    assert "WINMART" in line_5411 and "BHX" in line_5411
    # a different MCC's pattern must NOT bleed into the 5411 line
    assert "SHOPEE" not in line_5411
    assert "SHOPEE" in s  # but it's present under 5262


def test_mcc_overview_falls_back_to_map_label_without_account(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    s = cb.mcc_pattern_overview_text()  # no account → use mcc_label from the map
    assert "(5262)" in s and "SHOPEE" in s


# ── billing cycle (statement / due day) ───────────────────────────

def test_set_billing_cycle_writes_and_validates(fake_ss):
    _seed_card()
    assert sh.set_billing_cycle("cake_cc", 15, 25) is True
    acc = sh.find_account_by_id("cake_cc")
    assert acc["statement_day"] == 15 and acc["due_day"] == 25
    # out-of-range statement day rejected, value unchanged
    assert sh.set_billing_cycle("cake_cc", 31) is False
    assert sh.find_account_by_id("cake_cc")["statement_day"] == 15
    # due_day optional — statement updates, due preserved
    assert sh.set_billing_cycle("cake_cc", 20) is True
    acc = sh.find_account_by_id("cake_cc")
    assert acc["statement_day"] == 20 and acc["due_day"] == 25


def test_set_billing_cycle_rejects_non_credit(fake_ss):
    sh.add_account(account_id="tcb", name="TCB", acc_type="bank", currency="VND",
                   source_keys=["sepay:1"], starting_balance=0)
    sh.invalidate_accounts_cache()
    assert sh.set_billing_cycle("tcb", 15) is False
    assert sh.set_billing_cycle("nope", 15) is False


def test_card_overview_shows_billing_cycle(fake_ss):
    # Bare credit card (no statement_day) → calendar-month wording.
    sh.add_account(account_id="bare_cc", name="Bare", acc_type="credit", currency="VND",
                   source_keys=["x:bare"], credit_limit=10_000_000)
    sh.invalidate_accounts_cache()
    assert "theo tháng dương lịch" in cb.card_overview_text("bare_cc")
    # Seeded card carries statement_day=15 / due_day=25 → shows the dates.
    _seed_card()
    s = cb.card_overview_text("cake_cc")
    assert "chốt ngày 15" in s and "đáo hạn ngày 25" in s


def test_set_billing_cycle_changes_cycle_grouping(fake_ss):
    # statement_day=15 → a tx on the 20th belongs to NEXT month's cycle.
    _setup_tx_tab()
    _seed_card()
    cb.seed_cake_card("cake_cc")
    sh.set_billing_cycle("cake_cc", 15, 25)
    acc = sh.find_account_by_id("cake_cc")
    assert sh.cycle_id("cake_cc", "2026-06-20T09:00:00", acc["statement_day"]) == "cake_cc_2026-07"
    assert sh.cycle_id("cake_cc", "2026-06-10T09:00:00", acc["statement_day"]) == "cake_cc_2026-06"


@pytest.mark.asyncio
async def test_cycle_input_saves_and_recomputes(monkeypatch, fake_ss):
    _setup_tx_tab()
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])
    _seed_card()  # starts at 15/25
    cb.seed_cake_card("cake_cc")
    import telegram_api as tg
    sent = []

    async def _t(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _t)
    monkeypatch.setattr(tg, "send_with_buttons", _t)
    recomputed = {}
    monkeypatch.setattr(cb, "recompute_cycle", lambda aid, *a, **k: recomputed.setdefault(aid, 3) or 3)

    # Change to NEW values to prove the input wrote them (not the seed defaults).
    await cb.handle_cashback_cycle_input("5 18", {"account_id": "cake_cc"})
    acc = sh.find_account_by_id("cake_cc")
    assert acc["statement_day"] == 5 and acc["due_day"] == 18
    assert recomputed.get("cake_cc") == 3            # auto-recompute fired
    assert any("chốt ngày 5" in t for t in sent)


@pytest.mark.asyncio
async def test_cycle_input_rejects_out_of_range(monkeypatch, fake_ss):
    _seed_card()
    import telegram_api as tg
    sent = []

    async def _t(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _t)
    monkeypatch.setattr(tg, "send_with_buttons", _t)
    await cb.handle_cashback_cycle_input("31", {"account_id": "cake_cc"})
    assert any("1–28" in t for t in sent)
    # rejected → statement_day unchanged (seed left it at 15)
    assert sh.find_account_by_id("cake_cc")["statement_day"] == 15


# ── rule edit / delete (CRUD) ─────────────────────────────────────

def test_apply_rule_field_valid(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    rid = "cake_cc_5411"
    assert cb.apply_rule_field(rid, "name", "Siêu thị mới")[0] is True
    assert cb.apply_rule_field(rid, "cap", "150000")[0] is True
    assert cb.apply_rule_field(rid, "max", "2")[0] is True
    assert cb.apply_rule_field(rid, "rate", "0.15")[0] is True
    r = next(r for r in sh.get_cashback_rules("cake_cc") if r["rule_id"] == rid)
    assert r["rule_name"] == "Siêu thị mới"
    assert r["monthly_cap"] == 150000
    assert r["max_eligible_tx_per_day"] == 2
    assert abs(float(r["rate"]) - 0.15) < 1e-9
    # rate '-' → inherit (blank)
    assert cb.apply_rule_field(rid, "rate", "-")[0] is True
    r = next(r for r in sh.get_cashback_rules("cake_cc") if r["rule_id"] == rid)
    assert r["rate"] in (None, "")


def test_apply_rule_field_invalid(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    rid = "cake_cc_5411"
    assert cb.apply_rule_field(rid, "cap", "abc")[0] is False
    assert cb.apply_rule_field(rid, "max", "-1")[0] is False
    assert cb.apply_rule_field(rid, "rate", "2")[0] is False      # >1
    assert cb.apply_rule_field(rid, "name", "")[0] is False
    assert cb.apply_rule_field("nope_9999", "cap", "100")[0] is False
    # nothing changed by the failed edits
    r = next(r for r in sh.get_cashback_rules("cake_cc") if r["rule_id"] == rid)
    assert r["monthly_cap"] == 200000


def test_delete_rule_soft_deletes(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    assert len(sh.get_cashback_rules("cake_cc")) == 5
    assert cb.delete_rule("cake_cc_5411") is True
    ids = {r["rule_id"] for r in sh.get_cashback_rules("cake_cc")}
    assert "cake_cc_5411" not in ids
    assert len(sh.get_cashback_rules("cake_cc")) == 4


def test_rule_detail_text(fake_ss):
    _seed_card()
    cb.seed_cake_card("cake_cc")
    s = cb.rule_detail_text("cake_cc_5411")
    assert "Siêu thị" in s and "MCC 5411" in s
    assert "200.000" in s            # cap
    assert "1 tx/ngày" in s          # max
    assert "kế thừa thẻ" in s        # rate inherited (blank in seed)


@pytest.mark.asyncio
async def test_tg_rule_edit_input_updates_and_reshows(monkeypatch, fake_ss):
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "ts"]])
    _seed_card()
    cb.seed_cake_card("cake_cc")
    import telegram_api as tg
    sent = []

    async def _t(text, *a, **k):
        sent.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(tg, "send_text", _t)
    monkeypatch.setattr(tg, "send_with_buttons", _t)
    await cb.handle_cashback_rule_edit_input(
        "250000", {"step": "cb_redit", "rule_id": "cake_cc_5411", "field": "cap"})
    r = next(r for r in sh.get_cashback_rules("cake_cc") if r["rule_id"] == "cake_cc_5411")
    assert r["monthly_cap"] == 250000
    assert any("Cap/kỳ" in t for t in sent)            # confirmation
    assert any("Rule:" in t for t in sent)             # detail reshown


@pytest.mark.asyncio
async def test_zalo_rule_flow_edit_and_delete(monkeypatch, fake_ss):
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "ts"]])
    _seed_card()
    cb.seed_cake_card("cake_cc")
    import messenger
    sent = []

    async def _st(text, channel=None, recipient_id=None):
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(messenger, "send_text", _st)
    key = "zalo:R1"

    # menu option 4 → rule list
    sh.set_state(key, {"step": "zalo_cashback_menu", "account_id": "cake_cc"})
    await cb.zalo_handle_menu("R1", "4", sh.get_state(key), key)
    assert sh.get_state(key)["step"] == "zalo_cashback_rule_pick"
    rids = sh.get_state(key)["rule_ids"]

    # pick the 5411 rule
    idx = rids.index("cake_cc_5411") + 1
    await cb.zalo_handle_rule_pick("R1", str(idx), sh.get_state(key), key)
    assert sh.get_state(key)["step"] == "zalo_cashback_rule_menu"

    # edit cap
    await cb.zalo_handle_rule_menu("R1", "2", sh.get_state(key), key)  # 2 = cap
    assert sh.get_state(key)["step"] == "zalo_cashback_rule_edit"
    await cb.zalo_handle_rule_edit("R1", "175000", sh.get_state(key), key)
    r = next(r for r in sh.get_cashback_rules("cake_cc") if r["rule_id"] == "cake_cc_5411")
    assert r["monthly_cap"] == 175000

    # delete with confirm
    await cb.zalo_handle_rule_menu("R1", "5", sh.get_state(key), key)
    assert sh.get_state(key)["step"] == "zalo_cashback_rule_delconfirm"
    await cb.zalo_handle_rule_delconfirm("R1", "xoa", sh.get_state(key), key)
    assert "cake_cc_5411" not in {r["rule_id"] for r in sh.get_cashback_rules("cake_cc")}


# ── card listing (credit-only guard) ──────────────────────────────

def test_list_cashback_cards_credit_only(fake_ss):
    _seed_card()
    sh.add_account(account_id="tcb", name="TCB", acc_type="bank", currency="VND",
                   source_keys=["sepay:1"], starting_balance=0)
    sh.invalidate_accounts_cache()
    cards = cb.list_cashback_cards()
    assert [c["id"] for c in cards] == ["cake_cc"]


# ── recompute a whole cycle ───────────────────────────────────────

def test_recompute_cycle_recomputes_all_rows(fake_ss):
    _setup_tx_tab()
    _seed_card()
    cb.seed_cake_card("cake_cc")
    r1 = sh.append_transaction("2026-06-05T09:00:00", "WCM_WINMART HCM", 300000,
                               "R1", "2026-06", account_id="cake_cc",
                               ledger_tx_type="expense")
    r2 = sh.append_transaction("2026-06-06T09:00:00", "GRAB HCM", 150000,
                               "R2", "2026-06", account_id="cake_cc",
                               ledger_tx_type="expense")
    # ledger empty until we (re)compute the cycle
    assert sh.get_cashback_ledger("cake_cc") == []
    n = cb.recompute_cycle("cake_cc", "cake_cc_2026-06")
    assert n >= 2
    lines = [l for l in sh.get_cashback_ledger("cake_cc") if l["status"] != "void"]
    by_row = {l["tx_row_num"]: l for l in lines}
    assert by_row[r1]["cashback_amount"] == 50000   # WINMART 5411, first of day
    assert by_row[r2]["cashback_amount"] == 10000   # GRAB 4121, raw 30k capped to 10k


def test_recompute_cycle_accepts_short_cycle_label(fake_ss):
    # Codex round 02 [P2]: a user types the month shown elsewhere (2026-06), not
    # the internal cake_cc_2026-06 — recompute_cycle must normalize it.
    _setup_tx_tab()
    _seed_card()
    cb.seed_cake_card("cake_cc")
    r = sh.append_transaction("2026-06-05T09:00:00", "WCM_WINMART HCM", 300000,
                              "RS", "2026-06", account_id="cake_cc", ledger_tx_type="expense")
    n = cb.recompute_cycle("cake_cc", "2026-06")  # short form
    assert n >= 1
    line = [l for l in sh.get_cashback_ledger("cake_cc") if l["tx_row_num"] == r][0]
    assert line["cashback_amount"] == 50000


@pytest.mark.asyncio
async def test_zalo_cashback_uses_sender_chat(monkeypatch, fake_ss):
    # Codex round 02 [P2]: replies must go to the requesting chat, not the
    # hardcoded ZALO_CHAT_ID (empty in tests).
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])
    _seed_card()
    import messenger
    recipients = []

    async def _st(text, channel=None, recipient_id=None):
        recipients.append(recipient_id)
        return {"ok": True}

    monkeypatch.setattr(messenger, "send_text", _st)
    await cb.zalo_start_cashback("SENDER123", "/cashback", "zalo:SENDER123")
    assert recipients and all(r == "SENDER123" for r in recipients)


@pytest.mark.asyncio
async def test_zalo_pick_rejects_zero_and_negative(monkeypatch, fake_ss):
    # Codex round 03 [P2]: "0" → int-1 = -1 must NOT select cards[-1].
    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])
    _seed_card("cake_cc")
    _seed_card("visa_cc")  # 2 cards; cards[-1] would be visa_cc
    import messenger
    msgs = []

    async def _st(text, channel=None, recipient_id=None):
        msgs.append(text)
        return {"ok": True}

    monkeypatch.setattr(messenger, "send_text", _st)
    state = {"step": "zalo_cashback_pick", "cards": ["cake_cc", "visa_cc"]}
    sh.set_state("zalo:S", state)
    await cb.zalo_handle_pick("S", "0", state, "zalo:S")
    assert any("không hợp lệ" in m for m in msgs)
    # state must NOT advance to a card menu (no valid card was picked)
    assert sh.get_state("zalo:S").get("step") == "zalo_cashback_pick"
