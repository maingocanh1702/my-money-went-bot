"""Phase A — pure cashback engine (handlers/cashback_engine.py).

Tests the BRD §4.6 algorithm in isolation: no sheet I/O. All cycle/daily/cap
state is injected by the caller. Numbers follow BRD §4.6.1 (Cake Freedom:
rate 20%, per-tx tier 10k/50k, per-MCC/cycle cap 200k, gate 5tr).
"""
import pytest
from handlers.cashback_engine import compute_cashback


GATE = 5_000_000  # min_eligible_spend
CARD = {"cashback_rate": 0.20, "min_eligible_spend": GATE, "active": True}

# Two per-tx cap tiers (BRD §6.2): ≤199.999 → 10k, ≥200.000 → 50k.
TIERS = [
    {"tier_set": "cakefreedom", "tx_min": 0,      "tx_max": 199999, "per_tx_cap": 10000},
    {"tier_set": "cakefreedom", "tx_min": 200000, "tx_max": None,   "per_tx_cap": 50000},
]


def _rule(mcc, *, max_per_day=0, cap=200000, rate=0.20):
    return {
        "rule_id": f"cakefreedom_{mcc}",
        "account_id": "cakefreedom",
        "rule_name": {"5411": "Siêu thị", "4121": "Di chuyển"}.get(mcc, mcc),
        "match_type": "mcc",
        "match_value": mcc,
        "rate": rate,
        "monthly_cap": cap,
        "per_tx_cap_tier": "cakefreedom",
        "max_eligible_tx_per_day": max_per_day,
        "min_tx_amount": 0,
        "stackable": False,
        "priority": 1,
        "cap_period": "statement_cycle",
        "active": True,
    }


RULES = [
    _rule("4121", max_per_day=0),
    _rule("5411", max_per_day=1),
    _rule("5262", max_per_day=0),
]


def _run(amount, mcc, *, mcc_cycle_used=0, daily_count=0, eligible_before=GATE):
    """Helper: compute and return the single cashback line (Cake = 1 line)."""
    lines = compute_cashback(
        tx={"amount": amount},
        mcc=mcc,
        rules=RULES,
        tiers=TIERS,
        card_config=CARD,
        mcc_cycle_used=mcc_cycle_used,
        daily_count=daily_count,
        eligible_spend_before_tx=eligible_before,
    )
    assert len(lines) == 1
    return lines[0]


# ── BRD §4.6.1 example table (gate already open) ──────────────────

def test_grab_morning_under_50k_full_20pct():
    line = _run(48550, "4121")
    assert line["cashback_amount"] == 9710
    assert line["reason"] == ""
    assert line["status"] == "eligible"
    assert line["mcc_code"] == "4121"


def test_grab_noon_hits_per_tx_cap_10k():
    line = _run(150000, "4121")
    assert line["cashback_amount"] == 10000
    assert line["capped_flag"] is True
    assert line["reason"] == ""


def test_supermarket_first_of_day_gets_cashback():
    line = _run(300000, "5411", daily_count=0)
    assert line["cashback_amount"] == 50000
    assert line["reason"] == ""


def test_supermarket_second_same_day_blocked_daily_limit():
    line = _run(800000, "5411", daily_count=1)
    assert line["cashback_amount"] == 0
    assert line["reason"] == "daily_limit"


def test_ecommerce_hits_per_tx_cap_50k():
    line = _run(300000, "5262")
    assert line["cashback_amount"] == 50000
    assert line["capped_flag"] is True
    assert line["reason"] == ""


# ── MCC not eligible / unknown ────────────────────────────────────

def test_mcc_outside_list_zero_not_eligible():
    line = _run(90000, "5814")  # café — has a code but no active rule
    assert line["cashback_amount"] == 0
    assert line["reason"] == "mcc_not_eligible"


def test_mcc_unknown_zero_reason():
    line = _run(90000, "")  # description matched no MCC pattern
    assert line["cashback_amount"] == 0
    assert line["reason"] == "mcc_unknown"


# ── Activation gate (5tr) ─────────────────────────────────────────

def test_below_gate_status_pending():
    # eligible spend after this tx still < 5tr → pending (but cashback accrues)
    line = _run(48550, "4121", eligible_before=0)
    assert line["cashback_amount"] == 9710
    assert line["status"] == "pending"


def test_crossing_gate_status_eligible():
    # before just under, this tx pushes total ≥ gate → eligible
    line = _run(48550, "4121", eligible_before=GATE - 1)
    assert line["status"] == "eligible"


# ── Per-MCC cycle cap ─────────────────────────────────────────────

def test_mcc_cap_full_zero_reason():
    line = _run(300000, "5411", mcc_cycle_used=200000, daily_count=0)
    assert line["cashback_amount"] == 0
    assert line["reason"] == "mcc_cap_full"


def test_mcc_cap_partial_remaining_caps_cashback():
    # only 30k cap left for the MCC this cycle → cashback clamped to 30k
    line = _run(300000, "5411", mcc_cycle_used=170000, daily_count=0)
    assert line["cashback_amount"] == 30000
    assert line["capped_flag"] is True
    assert line["reason"] == ""


# ── Rule minimum transaction amount (BRD §4.3) ────────────────────

def _rules_with_min(min_amount):
    r = _rule("4121", max_per_day=0)
    r["min_tx_amount"] = min_amount
    return [r]


def test_below_min_tx_amount_not_eligible():
    line = compute_cashback(
        tx={"amount": 50000}, mcc="4121", rules=_rules_with_min(100000),
        tiers=TIERS, card_config=CARD, mcc_cycle_used=0, daily_count=0,
        eligible_spend_before_tx=GATE,
    )[0]
    assert line["cashback_amount"] == 0
    assert line["reason"] == "mcc_not_eligible"


def test_at_or_above_min_tx_amount_eligible():
    line = compute_cashback(
        tx={"amount": 150000}, mcc="4121", rules=_rules_with_min(100000),
        tiers=TIERS, card_config=CARD, mcc_cycle_used=0, daily_count=0,
        eligible_spend_before_tx=GATE,
    )[0]
    assert line["cashback_amount"] == 10000  # raw 30k capped to per-tx 10k
    assert line["reason"] == ""
