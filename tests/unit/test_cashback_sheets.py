"""Phase A — cashback CRUD, cycle helpers, and orchestrator (sheets.py).

In-memory FakeSpreadsheet → zero Google API. Covers BRD §6 CRUD, MCC matching
on real merchant format, statement-cycle boundaries, eligible-spend / daily
counters with exclusion, orchestrator idempotency + activation gate + promote,
and recompute reshuffling the supermarket daily limit.
"""
from datetime import datetime, timedelta, timezone

import pytest
import sheets as sh
from config import SHEETS as S


@pytest.fixture(autouse=True)
def _reset_cashback_caches(fake_ss):
    """fake_ss rebuilds the spreadsheet per test but module caches persist —
    clear the cashback caches so rows don't leak across tests."""
    sh.invalidate_cashback_caches()
    yield


# ── seed helpers ──────────────────────────────────────────────────

def _setup_tx_tab():
    ws = sh._get_spreadsheet().add_worksheet(S.TRANSACTIONS)
    header = [
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]
    ws.update("A1:U1", [header])
    return ws


def _seed_credit(account_id="cake", statement_day=15, min_spend=0):
    sh.add_account(
        account_id=account_id, name="Cake Freedom", acc_type="credit",
        currency="VND", source_keys=[f"email_cake:{account_id}"],
        credit_limit=50_000_000, statement_day=statement_day, due_day=25,
    )
    sh.invalidate_accounts_cache()
    sh.upsert_card_config(
        account_id, cashback_rate=0.20, min_eligible_spend=min_spend,
        cap_period="statement_cycle", alert_pct=0.80, active=True,
    )


def _seed_tiers():
    ws = sh._ensure_cashback_tiers_tab()
    ws.update("A2:D3", [
        ["cakefreedom", 0, 199999, 10000],
        ["cakefreedom", 200000, "", 50000],
    ])


def _seed_rules(account_id="cake"):
    sh.add_cashback_rule(account_id, "Siêu thị", "mcc", "5411",
                         monthly_cap=200000, per_tx_cap_tier="cakefreedom",
                         max_eligible_tx_per_day=1)
    sh.add_cashback_rule(account_id, "Di chuyển", "mcc", "4121",
                         monthly_cap=200000, per_tx_cap_tier="cakefreedom",
                         max_eligible_tx_per_day=0)


def _seed_mcc():
    sh.add_mcc_map("WINMART", "5411", "Siêu thị")
    sh.add_mcc_map("LOTTE", "5411", "Siêu thị")
    sh.add_mcc_map("GRAB", "4121", "Di chuyển")


def _add_tx(account_id, desc, amount, iso_date):
    return sh.append_transaction(
        iso_date, desc, amount, f"R{amount}", iso_date[:7],
        account_id=account_id, ledger_tx_type="expense",
    )


def _full_setup(min_spend=0):
    _setup_tx_tab()
    _seed_credit(min_spend=min_spend)
    _seed_tiers()
    _seed_rules()
    _seed_mcc()


def _active_lines(account_id="cake", cycle=None):
    return [r for r in sh.get_cashback_ledger(account_id, cycle)
            if r["status"] != "void"]


# ── CRUD: rules ───────────────────────────────────────────────────

def test_add_get_cashback_rule(fake_ss):
    rid = sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411",
                               monthly_cap=200000, per_tx_cap_tier="cakefreedom",
                               max_eligible_tx_per_day=1)
    assert rid == "cake_5411"
    rules = sh.get_cashback_rules("cake")
    assert len(rules) == 1
    r = rules[0]
    assert r["match_value"] == "5411"
    assert r["monthly_cap"] == 200000
    assert r["max_eligible_tx_per_day"] == 1
    assert r["active"] is True


def test_cashback_rule_rejects_non_finite_money_values(fake_ss):
    with pytest.raises(ValueError, match="finite"):
        sh.add_cashback_rule("cake", "Broken", "mcc", "5411", rate=float("inf"))
    with pytest.raises(ValueError, match="finite"):
        sh.upsert_card_config("cake", cashback_rate=float("nan"))


def test_durable_claim_blocks_fresh_processing_and_reclaims_stale_claim(fake_ss):
    _setup_tx_tab()
    sh._processed_refs.clear()

    assert sh.tx_exists("exclusive-claim") is False
    with pytest.raises(sh.TransactionClaimInProgressError):
        sh.tx_exists("exclusive-claim")

    processed = sh._ensure_processed_refs_tab()
    stale = (datetime.now(timezone.utc) - timedelta(
        seconds=sh.PROCESSED_REF_CLAIM_TTL_SECONDS + 1
    )).isoformat()
    processed.update("C2:C2", [[stale]])
    sh._processed_refs.clear()

    assert sh.tx_exists("exclusive-claim") is False


def test_durable_claim_expands_processed_refs_past_initial_sheet_capacity(fake_ss, monkeypatch):
    _setup_tx_tab()
    processed = sh._ensure_processed_refs_tab()
    processed._row_count = 500
    processed.update(
        "A2:C500",
        [[f"old-{index}", "committed", "2026-09-01T00:00:00+00:00"] for index in range(499)],
    )
    sh._processed_refs.clear()
    monkeypatch.setattr(sh, "_ref_in_sheet", lambda _ref_code: False)

    assert sh.tx_exists("claim-after-capacity") is False
    assert processed.row_count >= 501
    assert processed.row_values(501)[0] == "claim-after-capacity"


def test_fuzzy_dedup_reads_canonical_datetime_written_to_transactions(fake_ss):
    _setup_tx_tab()
    tx_date = datetime(2026, 9, 1, 14, 0, tzinfo=timezone(timedelta(hours=7)))
    sh.append_transaction(tx_date, "Coffee", 50_000, "first-ref", "2026-09", tx_type="Tiền ra")

    assert sh.find_recent_duplicate(50_000, "out", tx_date.isoformat()) is True


def test_calendar_month_cap_period_ignores_statement_day(fake_ss):
    _setup_tx_tab()
    sh.add_account(
        account_id="bank1", name="Bank 1", acc_type="credit", currency="VND",
        source_keys=["email_cake:bank1"], statement_day=15,
    )
    sh.upsert_card_config(
        "bank1", cashback_rate=0.01, min_eligible_spend=0,
        cap_period="calendar_month", alert_pct=0.8, active=True,
    )
    assert sh.cashback_cycle_id("bank1", "2026-06-20") == "bank1_calendar_2026-06"
    assert sh.cashback_cycle_id("bank1", "2026-07-01") == "bank1_calendar_2026-07"
    assert sh.normalize_cashback_cycle_id("bank1", "2026-06") == "bank1_calendar_2026-06"
    assert sh.normalize_cashback_cycle_id("bank1", "bank1_2026-06") == "bank1_calendar_2026-06"


def test_calendar_month_versioning_isolates_legacy_statement_cycle_rows(fake_ss):
    _setup_tx_tab()
    _seed_credit(account_id="bank1", statement_day=15)
    _seed_tiers()
    _seed_rules(account_id="bank1")
    _seed_mcc()

    june = _add_tx("bank1", "WCM_WINMART June", 300_000, "2026-06-20T09:00:00")
    # Simulate the old statement-cycle writer before calendar-month support.
    sh.compute_and_record_cashback(june)
    assert sh.get_cashback_ledger("bank1")[0]["cycle"] == "bank1_2026-07"

    sh.upsert_card_config("bank1", cap_period="calendar_month")
    july = _add_tx("bank1", "WCM_WINMART July", 300_000, "2026-07-01T09:00:00")
    result = sh.compute_and_record_cashback(july)

    assert result["cycle"] == "bank1_calendar_2026-07"
    july_lines = [line for line in sh.get_cashback_ledger("bank1", result["cycle"])
                  if line["status"] != "void"]
    assert len(july_lines) == 1
    assert july_lines[0]["tx_row_num"] == july
    assert july_lines[0]["cashback_amount"] == 50_000


def test_invalid_calendar_date_preserves_existing_cashback_until_repaired(fake_ss):
    _setup_tx_tab()
    _seed_credit(account_id="bank1", statement_day=15)
    _seed_tiers()
    _seed_rules(account_id="bank1")
    _seed_mcc()
    sh.upsert_card_config("bank1", cap_period="calendar_month")

    row_num = _add_tx("bank1", "WCM_WINMART June", 300_000, "2026-06-20T09:00:00")
    computed = sh.compute_and_record_cashback(row_num)
    assert computed["lines"][0]["cashback_amount"] == 50_000

    # A manual Sheet edit can make the date unparsable after cashback has been
    # recorded. Derived money must stay intact until the source date is fixed.
    tx_ws = sh._sheet(S.TRANSACTIONS)
    tx_ws.update_cell(row_num, 2, "not-a-date")
    sh._invalidate_tx_rows_cache()

    assert sh.recompute_cashback_for_tx(row_num)["lines"] == []
    assert sh.compute_and_record_cashback(row_num)["lines"] == []
    active = [line for line in sh.get_cashback_ledger("bank1") if line["status"] != "void"]
    assert len(active) == 1
    assert active[0]["tx_row_num"] == row_num
    assert active[0]["cashback_amount"] == 50_000


def test_soft_delete_cashback_rule(fake_ss):
    rid = sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411")
    assert sh.soft_delete_cashback_rule(rid) is True
    assert sh.get_cashback_rules("cake") == []


def test_update_cashback_rule(fake_ss):
    rid = sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411", monthly_cap=200000)
    assert sh.update_cashback_rule(rid, monthly_cap=150000, rate=0.10) is True
    r = sh.get_cashback_rules("cake")[0]
    assert r["monthly_cap"] == 150000
    assert r["rate"] == 0.10


def test_re_add_soft_deleted_rule_reactivates_no_duplicate(fake_ss):
    # Codex round 04 [P2]: re-adding a soft-deleted rule_id must reactivate the
    # same row, not append a duplicate that update/soft_delete would then miss.
    rid = sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411", monthly_cap=200000)
    sh.soft_delete_cashback_rule(rid)
    assert sh.get_cashback_rules("cake") == []

    rid2 = sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411", monthly_cap=150000)
    assert rid2 == rid
    rules = sh.get_cashback_rules("cake")
    assert len(rules) == 1
    assert rules[0]["monthly_cap"] == 150000  # fields refreshed on reactivate

    raw = sh._ensure_cashback_rules_tab().get_all_values()[1:]
    assert len([r for r in raw if r and r[0] == rid]) == 1  # exactly one row

    # update + soft_delete still target the single live row
    assert sh.update_cashback_rule(rid, rate=0.15) is True
    assert sh.get_cashback_rules("cake")[0]["rate"] == 0.15
    assert sh.soft_delete_cashback_rule(rid) is True
    assert sh.get_cashback_rules("cake") == []


def test_get_cashback_rules_filters_by_account(fake_ss):
    sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411")
    sh.add_cashback_rule("other", "Siêu thị", "mcc", "5411")
    assert len(sh.get_cashback_rules("cake")) == 1
    assert len(sh.get_cashback_rules()) == 2


# ── CRUD: tiers / config / mcc map ────────────────────────────────

def test_get_cashback_tiers_sorted(fake_ss):
    _seed_tiers()
    tiers = sh.get_cashback_tiers("cakefreedom")
    assert len(tiers) == 2
    assert tiers[0]["tx_min"] == 0 and tiers[0]["per_tx_cap"] == 10000
    assert tiers[1]["tx_min"] == 200000 and tiers[1]["tx_max"] is None


def test_upsert_get_card_config(fake_ss):
    sh.upsert_card_config("cake", cashback_rate=0.20, min_eligible_spend=5_000_000,
                          cap_period="statement_cycle", alert_pct=0.80, active=True)
    cfg = sh.get_card_config("cake")
    assert cfg["cashback_rate"] == 0.20
    assert cfg["min_eligible_spend"] == 5_000_000
    assert cfg["active"] is True
    # upsert again updates the same row, not appends
    sh.upsert_card_config("cake", min_eligible_spend=3_000_000)
    assert sh.get_card_config("cake")["min_eligible_spend"] == 3_000_000
    rows = sh._ensure_cashback_config_tab().get_all_values()[1:]
    assert len([r for r in rows if r and r[0] == "cake"]) == 1


def test_add_get_mcc_map(fake_ss):
    assert sh.add_mcc_map("WINMART", "5411", "Siêu thị") is True
    rows = sh.get_mcc_map()
    assert any(m["mcc_code"] == "5411" for m in rows)


def test_match_mcc_real_merchant_format(fake_ss):
    sh.add_mcc_map("WINMART", "5411", "Siêu thị")
    m = sh.match_mcc("WCM_WINMART 6992 HOMYLAND HO CHI MINH VN")
    assert m is not None
    assert m["mcc_code"] == "5411"


def test_match_mcc_no_match_none(fake_ss):
    sh.add_mcc_map("WINMART", "5411", "Siêu thị")
    assert sh.match_mcc("ABC COFFEE SHOP HCM") is None


# ── cycle_id boundary (statement_day) ─────────────────────────────

def test_cycle_id_before_statement_day(fake_ss):
    # day 10 <= statement_day 15 → cycle closes this month
    assert sh.cycle_id("cake", "2026-06-10T09:00:00", 15) == "cake_2026-06"


def test_cycle_id_after_statement_day_rolls_to_next(fake_ss):
    # day 20 > statement_day 15 → belongs to cycle closing next month
    assert sh.cycle_id("cake", "2026-06-20T09:00:00", 15) == "cake_2026-07"


def test_cycle_id_on_statement_day_belongs_to_closing_cycle(fake_ss):
    # the statement_day date itself is in the closing cycle (BRD edge case 7)
    assert sh.cycle_id("cake", "2026-06-15T09:00:00", 15) == "cake_2026-06"


def test_cycle_id_december_rolls_year(fake_ss):
    assert sh.cycle_id("cake", "2026-12-20T09:00:00", 15) == "cake_2027-01"


# ── eligible_spend / daily_count with exclusion ───────────────────

def test_eligible_spend_in_cycle_excludes_row(fake_ss):
    _full_setup()
    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    r2 = _add_tx("cake", "GRAB 2 HCM", 200000, "2026-06-11T09:00:00")
    sh.compute_and_record_cashback(r1)
    sh.compute_and_record_cashback(r2)
    cycle = "cake_2026-06"
    assert sh.eligible_spend_in_cycle("cake", cycle) == 500000
    assert sh.eligible_spend_in_cycle("cake", cycle, exclude_tx_row=r1) == 200000


def test_daily_eligible_count_excludes_row(fake_ss):
    _full_setup()
    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    sh.compute_and_record_cashback(r1)
    assert sh.daily_eligible_count("cake", "5411", "2026-06-10T20:00:00") == 1
    assert sh.daily_eligible_count("cake", "5411", "2026-06-10T20:00:00",
                                   exclude_tx_row=r1) == 0


# ── orchestrator: records, idempotent ─────────────────────────────

def test_compute_records_one_ledger_line(fake_ss):
    _full_setup()
    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    res = sh.compute_and_record_cashback(r1)
    lines = _active_lines()
    assert len(lines) == 1
    assert lines[0]["cashback_amount"] == 50000
    assert lines[0]["mcc_code"] == "5411"
    assert res["daily_limit_first"] is True


def test_compute_idempotent_void_then_rewrite(fake_ss):
    _full_setup()
    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    sh.compute_and_record_cashback(r1)
    sh.compute_and_record_cashback(r1)  # second call must not double up
    lines = _active_lines()
    assert len(lines) == 1
    assert sum(l["cashback_amount"] for l in lines) == 50000
    # old line is kept as void (audit), not deleted
    all_rows = sh.get_cashback_ledger("cake")
    assert any(r["status"] == "void" for r in all_rows)


def test_compute_skips_non_credit_account(fake_ss):
    _setup_tx_tab()
    sh.add_account(account_id="bank1", name="Bank 1", acc_type="bank",
                   currency="VND", source_keys=["sepay:bank1"], starting_balance=0)
    sh.invalidate_accounts_cache()
    r1 = _add_tx("bank1", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    res = sh.compute_and_record_cashback(r1)
    assert res["lines"] == []
    assert sh.get_cashback_ledger("bank1") == []


def test_compute_skips_negative_refund_amount(fake_ss):
    # Codex round 05 [P2] / BRD FR-2.3: a refund/correction stored as a negative
    # amount (still default expense type) must be skipped, not written as a
    # negative cashback line that distorts cycle spend/caps.
    _full_setup()
    r = sh.append_transaction(
        "2026-06-10T09:00:00", "WCM_WINMART refund", -300000, "RNEG", "2026-06",
        account_id="cake", ledger_tx_type="expense",
    )
    res = sh.compute_and_record_cashback(r)
    assert res["lines"] == []
    assert sh.get_cashback_ledger("cake") == []


def test_compute_skips_non_vnd_transaction(fake_ss):
    # Codex round 02 [P2]: a foreign-currency purchase on a VND card must not be
    # treated as VND spend (would wrongly earn cashback / open the 5tr gate).
    _full_setup()
    r = sh.append_transaction(
        "2026-06-10T09:00:00", "WCM_WINMART HK", 300, "RHK", "2026-06",
        account_id="cake", ledger_tx_type="expense", currency="HKD",
    )
    res = sh.compute_and_record_cashback(r)
    assert res["lines"] == []
    assert sh.get_cashback_ledger("cake") == []


def test_recompute_voids_when_tx_no_longer_qualifies(fake_ss):
    # Codex round 03 [P2]: a tx that earned cashback then becomes ineligible
    # (e.g. currency corrected to foreign) must have its old line voided, not
    # left active to keep skewing caps / daily counts / cycle spend.
    _full_setup()
    r = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    sh.compute_and_record_cashback(r)
    assert len(_active_lines()) == 1
    sh._sheet(S.TRANSACTIONS).update_cell(r, 16, "HKD")  # col P currency → foreign
    res = sh.compute_and_record_cashback(r)
    assert res["lines"] == []
    assert _active_lines() == []  # old line voided on the skip path


# ── orchestrator: activation gate ─────────────────────────────────


def test_below_min_tx_does_not_open_gate(fake_ss):
    # Codex round 03 [P2]: a below-min purchase is mcc_not_eligible and must not
    # count toward the activation gate (consistent with eligible_spend_in_cycle).
    _setup_tx_tab()
    _seed_credit(min_spend=5_000_000)
    _seed_tiers()
    sh.add_cashback_rule("cake", "Di chuyển", "mcc", "4121",
                         monthly_cap=200000, per_tx_cap_tier="cakefreedom")
    sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411", monthly_cap=200000,
                         per_tx_cap_tier="cakefreedom", max_eligible_tx_per_day=1,
                         min_tx_amount=100000)
    sh.add_mcc_map("GRAB", "4121")
    sh.add_mcc_map("WINMART", "5411")

    r1 = _add_tx("cake", "GRAB big HCM", 4_950_000, "2026-06-05T09:00:00")
    sh.compute_and_record_cashback(r1)
    assert _active_lines()[0]["status"] == "pending"

    # below-min supermarket tx would push raw spend over 5tr, but it's not
    # eligible — the gate must stay shut and tx1 stay pending.
    r2 = _add_tx("cake", "WCM_WINMART small", 50000, "2026-06-06T09:00:00")
    res2 = sh.compute_and_record_cashback(r2)
    assert res2["gate_just_opened"] is False
    line1 = [l for l in _active_lines() if l["tx_row_num"] == r1][0]
    assert line1["status"] == "pending"

def test_gate_just_opened_promotes_pending(fake_ss):
    _full_setup(min_spend=5_000_000)
    r1 = _add_tx("cake", "WCM_WINMART big HCM", 4_900_000, "2026-06-05T09:00:00")
    res1 = sh.compute_and_record_cashback(r1)
    assert res1["gate_just_opened"] is False
    # tx1 line is pending (cycle spend below gate)
    assert _active_lines()[0]["status"] == "pending"

    r2 = _add_tx("cake", "GRAB HCM", 200_000, "2026-06-06T09:00:00")
    res2 = sh.compute_and_record_cashback(r2)
    assert res2["gate_just_opened"] is True
    # all pending lines in the cycle promoted to eligible
    assert all(l["status"] == "eligible" for l in _active_lines(cycle="cake_2026-06"))


# ── orchestrator: daily limit + recompute reshuffle ───────────────

def test_daily_limit_blocks_second_supermarket(fake_ss):
    _full_setup()
    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    r2 = _add_tx("cake", "LOTTE MART HCM", 800000, "2026-06-10T18:00:00")
    sh.compute_and_record_cashback(r1)
    res2 = sh.compute_and_record_cashback(r2)
    assert res2["daily_limit_blocked"] is True
    line2 = [l for l in _active_lines() if l["tx_row_num"] == r2][0]
    assert line2["cashback_amount"] == 0
    assert line2["reason"] == "daily_limit"


def test_recompute_promotes_second_when_first_loses_mcc(fake_ss):
    _full_setup()
    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    r2 = _add_tx("cake", "LOTTE MART HCM", 800000, "2026-06-10T18:00:00")
    sh.compute_and_record_cashback(r1)
    sh.compute_and_record_cashback(r2)  # tx2 blocked by daily limit
    line2 = [l for l in _active_lines() if l["tx_row_num"] == r2][0]
    assert line2["cashback_amount"] == 0

    # MCC Map edited: WINMART no longer maps → tx1 stops being 5411.
    mcc_ws = sh._ensure_mcc_map_tab()
    for i, row in enumerate(mcc_ws.get_all_values()[1:]):
        if row and row[0] == sh._normalize_for_match("WINMART"):
            mcc_ws.update_cell(i + 2, 6, "FALSE")  # col F = active
    sh.invalidate_cashback_caches()

    sh.recompute_cashback_for_tx(r1)
    # tx1 no longer earns; tx2 (still 5411) is now the day's first → promoted
    line1 = [l for l in _active_lines() if l["tx_row_num"] == r1][0]
    line2b = [l for l in _active_lines() if l["tx_row_num"] == r2][0]
    assert line1["cashback_amount"] == 0
    assert line2b["cashback_amount"] == 50000


def test_recompute_resolves_daily_winner_chronologically(fake_ss):
    # tx1 (09:00) is the earlier supermarket tx but is initially NOT eligible
    # (WINMART unmapped), so tx2 (18:00, LOTTE) wins the day's single slot.
    # Codex round 01 [P2]: when WINMART later maps and we recompute, computing
    # the target before siblings would wrongly keep tx2 as winner. The earlier
    # tx1 must win once the whole day is rebuilt in chronological order.
    _setup_tx_tab()
    _seed_credit(min_spend=0)
    _seed_tiers()
    _seed_rules()
    sh.add_mcc_map("LOTTE", "5411", "Siêu thị")
    sh.add_mcc_map("GRAB", "4121", "Di chuyển")  # WINMART intentionally absent

    r1 = _add_tx("cake", "WCM_WINMART 1 HCM", 300000, "2026-06-10T09:00:00")
    r2 = _add_tx("cake", "LOTTE MART HCM", 800000, "2026-06-10T18:00:00")
    sh.compute_and_record_cashback(r1)  # mcc_unknown → 0đ
    sh.compute_and_record_cashback(r2)  # day's first eligible → 50000
    assert [l for l in _active_lines() if l["tx_row_num"] == r2][0]["cashback_amount"] == 50000

    # WINMART now maps → tx1 becomes 5411 and, being earlier, should win.
    sh.add_mcc_map("WINMART", "5411", "Siêu thị")
    sh.invalidate_cashback_caches()
    sh.recompute_cashback_for_tx(r1)

    line1 = [l for l in _active_lines() if l["tx_row_num"] == r1][0]
    line2 = [l for l in _active_lines() if l["tx_row_num"] == r2][0]
    assert line1["cashback_amount"] == 50000   # earlier tx wins the slot
    assert line2["cashback_amount"] == 0        # later tx blocked by daily limit
    assert line2["reason"] == "daily_limit"
