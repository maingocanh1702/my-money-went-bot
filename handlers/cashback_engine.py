"""Pure cashback engine — BRD §4.6.

No sheet I/O: every piece of cycle/daily/cap state is injected by the caller
(`sheets.compute_and_record_cashback`). Keeping it pure makes the money math
unit-testable without Google Sheets.

A "line" is one Cashback Ledger row (dict). Cake Freedom produces exactly one
line per transaction (single matching rule). 0đ lines carry a `reason` for
audit (NFR-6): mcc_unknown / mcc_not_eligible / daily_limit / mcc_cap_full.
"""


def _vnd(n) -> int:
    """Round to whole VND (no minor units). Mirrors fmt_amount's int(round())."""
    return int(round(float(n or 0)))


def _line(*, rule_id, mcc_code, eligible_amount, rate, cashback_amount,
          capped_flag, status, reason):
    return {
        "rule_id":         rule_id or "",
        "mcc_code":        mcc_code or "",
        "eligible_amount": _vnd(eligible_amount),
        "rate":            float(rate or 0),
        "cashback_amount": _vnd(cashback_amount),
        "capped_flag":     bool(capped_flag),
        "status":          status,
        "reason":          reason or "",
    }


def _audit_line(rule_id, mcc, amount, reason, rate=0.0, capped=False):
    """A 0đ line written purely for audit (the transaction earned no cashback)."""
    return _line(
        rule_id=rule_id, mcc_code=mcc, eligible_amount=amount, rate=rate,
        cashback_amount=0, capped_flag=capped, status="eligible", reason=reason,
    )


def _tier_cap(tiers, tier_set, amount):
    """Per-tx cap for `amount` from the rule's tier set. None = no per-tx cap.

    A tier matches when tx_min <= amount <= tx_max (empty tx_max = ∞).
    """
    if not tier_set:
        return None
    for t in tiers or []:
        if str(t.get("tier_set", "")).strip() != str(tier_set).strip():
            continue
        lo = float(t.get("tx_min") or 0)
        hi = t.get("tx_max")
        hi = float(hi) if hi not in (None, "") else float("inf")
        if lo <= amount <= hi:
            return float(t.get("per_tx_cap") or 0)
    return None


def _resolve_rate(rule, card_config):
    """Rule rate, inheriting the card's cashback_rate when the rule's is blank
    (BRD §6.1 col F: empty = kế thừa cashback_rate cấp thẻ)."""
    raw = rule.get("rate")
    if raw is None or raw == "":
        return float(card_config.get("cashback_rate") or 0)
    return float(raw)


def _compute_one(rule, amount, mcc, tiers, card_config,
                 mcc_cycle_used, daily_count, eligible_spend_before_tx):
    """Apply one rule to one transaction — BRD §4.6 order."""
    rule_id = rule.get("rule_id", "")
    rate = _resolve_rate(rule, card_config)

    # 1b. Rule minimum transaction amount (BRD §4.3): below the threshold the
    #     purchase doesn't qualify for this rule → 0đ, treated as not eligible.
    #     (Cake Freedom uses min_tx_amount=0, so this is a no-op there.)
    min_tx = float(rule.get("min_tx_amount") or 0)
    if min_tx > 0 and amount < min_tx:
        return _audit_line(rule_id, mcc, amount, "mcc_not_eligible", rate=rate)

    # 2. Daily eligible-tx limit (e.g. Siêu thị = 1/ngày). daily_count is the
    #    number of cashback>0 same-MCC same-day tx already recorded.
    max_per_day = int(rule.get("max_eligible_tx_per_day") or 0)
    if max_per_day > 0 and daily_count >= max_per_day:
        return _audit_line(rule_id, mcc, amount, "daily_limit", rate=rate)

    # 3. Per-transaction cap by amount band.
    raw = rate * amount
    per_tx_cap = _tier_cap(tiers, rule.get("per_tx_cap_tier"), amount)
    per_tx_cb = raw if per_tx_cap is None else min(raw, per_tx_cap)

    # 4. Per-MCC/cycle cap (default 200k). Full → 0đ audit line.
    monthly_cap = float(rule.get("monthly_cap") or 0)
    cap_remaining = None
    if monthly_cap > 0:
        cap_remaining = monthly_cap - float(mcc_cycle_used or 0)
        if cap_remaining <= 0:
            return _audit_line(rule_id, mcc, amount, "mcc_cap_full",
                               rate=rate, capped=True)
        cashback = min(per_tx_cb, cap_remaining)
    else:
        cashback = per_tx_cb

    capped_flag = (
        (per_tx_cap is not None and raw > per_tx_cap)
        or (cap_remaining is not None and per_tx_cb > cap_remaining)
    )

    # 5. Activation gate: pending until cycle eligible-spend reaches the
    #    threshold. The current tx counts toward the total (MCC is eligible).
    eligible_after = float(eligible_spend_before_tx or 0) + amount
    min_spend = float(card_config.get("min_eligible_spend") or 0)
    status = "pending" if eligible_after < min_spend else "eligible"

    return _line(
        rule_id=rule_id, mcc_code=mcc, eligible_amount=amount, rate=rate,
        cashback_amount=cashback, capped_flag=capped_flag,
        status=status, reason="",
    )


def compute_cashback(tx, mcc, rules, tiers, card_config,
                     mcc_cycle_used, daily_count, eligible_spend_before_tx):
    """Compute cashback line(s) for a transaction. Returns list[dict].

    Args:
      tx: dict with at least `amount`.
      mcc: inferred MCC code ("" / None = no MCC pattern matched).
      rules: active cashback rules for the card.
      tiers: per-tx cap tiers for the card's tier set.
      card_config: dict with cashback_rate + min_eligible_spend.
      mcc_cycle_used: cashback already accrued for this MCC this cycle (excl tx).
      daily_count: cashback>0 same-MCC same-day tx already recorded (excl tx).
      eligible_spend_before_tx: Σ eligible spend this cycle excluding this tx.
    """
    amount = float(tx.get("amount") or 0)
    mcc = (mcc or "").strip()

    # 1. No MCC inferred at all.
    if not mcc:
        return [_audit_line("", "", amount, "mcc_unknown")]

    # MCC inferred but no active rule for it on this card → not eligible.
    matched = [
        r for r in (rules or [])
        if str(r.get("match_type", "")).strip() == "mcc"
        and str(r.get("match_value", "")).strip() == mcc
        and r.get("active", True)
    ]
    if not matched:
        return [_audit_line("", mcc, amount, "mcc_not_eligible")]

    # Cake = one rule per MCC. NOTE (deferred to Phase B): when >1 non-stackable
    # rule matches the same MCC, BRD §4.7 says only the priority winner applies;
    # this returns a line per match. Harmless for Cake (1 rule/MCC); revisit when
    # stacking/multi-rule cards are added.
    return [
        _compute_one(rule, amount, mcc, tiers, card_config,
                     mcc_cycle_used, daily_count, eligible_spend_before_tx)
        for rule in matched
    ]
