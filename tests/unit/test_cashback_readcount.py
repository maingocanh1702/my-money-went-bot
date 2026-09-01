"""Read-efficiency guard (Sheets 429 fix).

recompute_cashback_for_tx fires on every credit expense; the old per-row
implementation read the (uncached) Cashback Ledger ~4× per cycle tx → O(N)
reads → 429 ('Read requests per minute per user'). These tests pin the ledger
read count to a small constant regardless of cycle size, and assert the rebuilt
ledger is byte-identical (parity) to the per-tx behavior.
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
    ws.update("A1:U1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency",
        "account_id", "tx_type", "linked_tx_row", "ledger_applied", "src_key",
    ]])
    return ws


def _seed(account_id="cake_cc", statement_day=15, cap=200000, max_day=0):
    sh.add_account(account_id=account_id, name="Cake CC", acc_type="credit",
                   currency="VND", source_keys=[f"email_cake:{account_id}"],
                   credit_limit=50_000_000, statement_day=statement_day, due_day=25)
    sh.invalidate_accounts_cache()
    sh.upsert_card_config(account_id, cashback_rate=0.20, min_eligible_spend=0,
                          cap_period="statement_cycle", alert_pct=0.80, active=True)
    sh.add_cashback_rule(account_id, "Di chuyển", "mcc", "4121", monthly_cap=cap,
                         per_tx_cap_tier="cakefreedom", max_eligible_tx_per_day=max_day)
    ws = sh._ensure_cashback_tiers_tab()
    ws.update("A2:D3", [["cakefreedom", 0, 199999, 10000],
                        ["cakefreedom", 200000, "", 50000]])
    sh.add_mcc_map("GRAB", "4121")
    sh.add_mcc_map("WINMART", "5411")
    sh.invalidate_cashback_caches()


def _add(account_id, desc, amount, iso):
    return sh.append_transaction(iso, desc, amount, f"R{desc}{iso}", iso[:7],
                                 account_id=account_id, ledger_tx_type="expense")


def _spy_ledger_reads():
    ws = sh._ensure_cashback_ledger_tab()
    cnt = {"n": 0}
    orig = ws.get_all_values

    def counting():
        cnt["n"] += 1
        return orig()

    ws.get_all_values = counting
    return cnt


def _active(account_id):
    return [l for l in sh.get_cashback_ledger(account_id) if l["status"] != "void"]


# ── (a) read-bound: ledger reads don't scale with cycle size ──────

def test_recompute_ledger_reads_bounded(fake_ss):
    _setup_tx_tab()
    _seed()
    K = 8
    rows = []
    for d in range(1, K + 1):
        r = _add("cake_cc", "GRAB ride", 40000, f"2026-06-{d:02d}T09:00:00")
        rows.append(r)
        sh.compute_and_record_cashback(r)  # seed the ledger (per-tx, setup only)

    cnt = _spy_ledger_reads()
    sh.recompute_cashback_for_tx(rows[0])  # ONE full-cycle recompute
    # O(1) reads — not ~4*K. Generous ceiling well under K.
    assert cnt["n"] <= 3, f"ledger read {cnt['n']}× for K={K} (expected O(1))"


# ── (b) parity: rebuilt ledger identical to per-tx behavior ───────

def test_recompute_parity_cross_day_cap(fake_ss):
    _setup_tx_tab()
    _seed(cap=60000, max_day=1)  # small cap so day-2 tx is cap-limited
    # use 5411 (WINMART/LOTTE) with daily limit 1
    sh.add_cashback_rule("cake_cc", "Siêu thị", "mcc", "5411", monthly_cap=60000,
                         per_tx_cap_tier="cakefreedom", max_eligible_tx_per_day=1)
    sh.add_mcc_map("LOTTE", "5411")
    sh.invalidate_cashback_caches()

    r1 = _add("cake_cc", "WCM_WINMART", 250000, "2026-06-05T09:00:00")
    r2 = _add("cake_cc", "LOTTE MART", 250000, "2026-06-06T09:00:00")
    sh.compute_and_record_cashback(r1)
    sh.compute_and_record_cashback(r2)

    sh.recompute_cashback_for_tx(r1)  # rebuild whole cycle
    lines = {l["tx_row_num"]: l for l in _active("cake_cc")}
    assert lines[r1]["cashback_amount"] == 50000   # day 1 per-tx cap
    assert lines[r2]["cashback_amount"] == 10000   # day 2: 60k cap - 50k used
    assert lines[r1]["mcc_code"] == "5411"
    assert lines[r2]["capped_flag"] is True


# ── Phase 2: seed reads bounded (not ~per 23 patterns + 5 rules) ──

def _spy_rules_mcc_reads():
    cnt = {"n": 0}
    for ws in (sh._ensure_cashback_rules_tab(), sh._ensure_mcc_map_tab()):
        orig = ws.get_all_values

        def make(o):
            def counting():
                cnt["n"] += 1
                return o()
            return counting
        ws.get_all_values = make(orig)
    return cnt


def test_recompute_uses_fresh_transactions_not_stale_cache(fake_ss):
    # Codex round 02 [P2]: the rebuild must read current Transactions, not a
    # stale TTL cache that could omit a tx in the cycle.
    import time
    _setup_tx_tab()
    _seed()
    r1 = _add("cake_cc", "GRAB ride", 40000, "2026-06-05T09:00:00")
    sh.compute_and_record_cashback(r1)
    snapshot_r1 = list(sh._get_tx_rows(force_refresh=True))   # cache holds only r1
    r2 = _add("cake_cc", "GRAB ride", 40000, "2026-06-06T09:00:00")
    sh.compute_and_record_cashback(r2)
    # Poison the cache so it omits r2 (simulates a still-valid stale snapshot).
    sh._tx_rows_cache["rows"] = snapshot_r1
    sh._tx_rows_cache["ts"] = time.time()

    sh.recompute_cashback_for_tx(r2)   # target r2 → voided; must be rebuilt from fresh read
    active = {l["tx_row_num"] for l in _active("cake_cc")}
    assert r2 in active, "rebuild used stale tx cache and dropped r2"


def test_bulk_rules_dedupes_duplicate_ids_in_one_batch(fake_ss):
    # Codex round 01 [P2]: two specs → same new rule_id in one batch must dedupe
    # (last-wins), not crash with IndexError.
    specs = [
        {"account_id": "x", "rule_name": "First", "match_type": "mcc", "match_value": "5411"},
        {"account_id": "x", "rule_name": "Second", "match_type": "mcc", "match_value": "5411"},
    ]
    sh.add_cashback_rules_bulk(specs)  # must not raise
    rules = [r for r in sh.get_cashback_rules("x") if r["rule_id"] == "x_5411"]
    assert len(rules) == 1
    assert rules[0]["rule_name"] == "Second"  # last spec wins


def test_seed_reads_bounded_and_idempotent(fake_ss):
    import handlers.cashback as cb
    sh.add_account(account_id="cake_cc", name="Cake CC", acc_type="credit",
                   currency="VND", source_keys=["email_cake:cake_cc"],
                   credit_limit=50_000_000, statement_day=15, due_day=25)
    sh.invalidate_accounts_cache()

    cnt = _spy_rules_mcc_reads()
    res = cb.seed_cake_card("cake_cc")
    assert res["ok"] is True
    assert res["rules"] == 5
    assert res["patterns"] >= 20            # 23 seed patterns
    assert cnt["n"] <= 4, f"rules+mcc read {cnt['n']}× (expected bounded, not per-item)"

    # idempotent re-seed: still bounded, no duplicate rows
    cnt["n"] = 0
    cb.seed_cake_card("cake_cc")
    assert cnt["n"] <= 4
    assert len(sh.get_cashback_rules("cake_cc")) == 5
    mcc_codes = {m["mcc_code"] for m in sh.get_mcc_map()}
    assert {"5262", "4722", "5611", "5411", "4121"} <= mcc_codes
