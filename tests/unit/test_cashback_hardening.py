"""Phase B Phase 1 (HARDEN) — recompute_cashback_for_tx must rebuild the whole
affected statement CYCLE in timestamp order, not just the same day.

Absorbs two Phase A deferrals (CHANGELOG "Deferred to Phase B"):
  (a) out-of-order arrivals — earliest-by-time tx wins the daily slot regardless
      of webhook write order, once the day is rebuilt chronologically.
  (b) cross-day MCC-cap dependents — voiding/changing an earlier tx that consumed
      cap must refresh later same-cycle tx on OTHER days (cap_remaining changed).
"""
import pytest
import sheets as sh
from config import SHEETS as S


@pytest.fixture(autouse=True)
def _reset(fake_ss):
    sh.invalidate_cashback_caches()
    yield


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


def _seed_credit(statement_day=15):
    sh.add_account(account_id="cake", name="Cake", acc_type="credit",
                   currency="VND", source_keys=["email_cake:cake"],
                   credit_limit=50_000_000, statement_day=statement_day, due_day=25)
    sh.invalidate_accounts_cache()
    sh.upsert_card_config("cake", cashback_rate=0.20, min_eligible_spend=0,
                          cap_period="statement_cycle", alert_pct=0.80, active=True)


def _seed_tiers():
    ws = sh._ensure_cashback_tiers_tab()
    ws.update("A2:D3", [
        ["cakefreedom", 0, 199999, 10000],
        ["cakefreedom", 200000, "", 50000],
    ])


def _add(desc, amount, iso):
    return sh.append_transaction(iso, desc, amount, f"R{amount}{iso}", iso[:7],
                                 account_id="cake", ledger_tx_type="expense")


def _active():
    return [r for r in sh.get_cashback_ledger("cake") if r["status"] != "void"]


def _line(rows, tx_row):
    return [l for l in rows if l["tx_row_num"] == tx_row][0]


def _disable_mcc_pattern(pattern):
    ws = sh._ensure_mcc_map_tab()
    norm = sh._normalize_for_match(pattern)
    for i, row in enumerate(ws.get_all_values()[1:]):
        if row and row[0] == norm:
            ws.update_cell(i + 2, 6, "FALSE")  # col F = active
    sh.invalidate_cashback_caches()


# ── (a) out-of-order arrivals within a day ────────────────────────

def test_recompute_out_of_order_makes_earliest_win(fake_ss):
    _setup_tx_tab()
    _seed_credit()
    _seed_tiers()
    sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411", monthly_cap=200000,
                         per_tx_cap_tier="cakefreedom", max_eligible_tx_per_day=1)
    sh.add_mcc_map("WINMART", "5411")
    sh.add_mcc_map("LOTTE", "5411")

    r_late = _add("WCM_WINMART HCM", 300000, "2026-06-10T15:00:00")
    r_early = _add("LOTTE MART HCM", 300000, "2026-06-10T09:00:00")  # arrives 2nd, earlier time
    sh.compute_and_record_cashback(r_late)   # first written → wins the slot
    sh.compute_and_record_cashback(r_early)  # blocked by daily limit
    assert _line(_active(), r_early)["cashback_amount"] == 0

    sh.recompute_cashback_for_tx(r_early)
    rows = _active()
    assert _line(rows, r_early)["cashback_amount"] == 50000   # earliest-by-time wins
    assert _line(rows, r_late)["cashback_amount"] == 0
    assert _line(rows, r_late)["reason"] == "daily_limit"


# ── (b) cross-day MCC-cap dependents in the same cycle ────────────

def test_recompute_refreshes_later_day_when_cap_freed(fake_ss):
    _setup_tx_tab()
    _seed_credit(statement_day=15)
    _seed_tiers()
    # small cap so the 2nd day's tx is cap-limited until the 1st day frees it
    sh.add_cashback_rule("cake", "Siêu thị", "mcc", "5411", monthly_cap=60000,
                         per_tx_cap_tier="cakefreedom", max_eligible_tx_per_day=1)
    sh.add_mcc_map("WINMART", "5411")
    sh.add_mcc_map("LOTTE", "5411")

    r1 = _add("WCM_WINMART HCM", 250000, "2026-06-05T09:00:00")  # day 1
    r2 = _add("LOTTE MART HCM", 250000, "2026-06-06T09:00:00")   # day 2, same cycle
    sh.compute_and_record_cashback(r1)
    sh.compute_and_record_cashback(r2)
    assert _line(_active(), r1)["cashback_amount"] == 50000
    assert _line(_active(), r2)["cashback_amount"] == 10000  # capped (60k - 50k)

    # WINMART unmapped → r1 (day 1) no longer eligible, frees the MCC cap.
    _disable_mcc_pattern("WINMART")
    sh.recompute_cashback_for_tx(r1)

    rows = _active()
    assert _line(rows, r1)["cashback_amount"] == 0
    # cross-day: r2 on a DIFFERENT day must be refreshed with the freed cap
    assert _line(rows, r2)["cashback_amount"] == 50000
