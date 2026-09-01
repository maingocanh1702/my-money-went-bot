"""handlers/report.py — unified /report command (account + category lenses).

Single entry point for spending analysis. Default lens = account, matching
the project goal: tracking tx + chi tiêu per account/card. Category is a
drill-down via inline button toggle, not a separate command.

UX pattern (same as /spending):
  Row 1 — period: Tuần / Tháng / Quý / Năm
  Row 2 — lens:   🏦 Account / 📂 Category

Periods are TZ-aware (Asia/Ho_Chi_Minh), running window from period start
through "now" (not calendar-complete) — same semantics as /spending.

This will replace /status, /weekly, /report-monthly (legacy) and possibly
/spending in Phase 2 after UX is confirmed. For now Phase 1 keeps the old
commands running in parallel.

Callback scheme: `rpt_<period>_<lens>`
  period ∈ {w, m, q, y}
  lens   ∈ {a (account), c (category)}
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Tuple

import pytz

from config import SHEETS as S, TIMEZONE
import sheets as sh
import telegram_api as tg
from i18n.core import t


PERIOD_CODES = ("w", "m", "q", "y")
LENS_CODES = ("a", "c")
PERIOD_LABEL = {"w": "Tuần", "m": "Tháng", "q": "Quý", "y": "Năm"}
TYPE_EMOJI = {"bank": "🏦", "debit": "💳", "credit": "🧾", "cash": "💵"}
BUDGET_WARN_PCT = 0.80
BUDGET_CRIT_PCT = 1.00

# Legacy fallback emoji for cards that don't have emoji in their rule notes.
# Dynamic emoji is preferred — loaded via _get_emoji_map_for_report().
_FALLBACK_MCC_EMOJI: dict[str, str] = {
    "5262": "🛍️", "4722": "✈️", "5611": "👕", "5411": "🛒", "4121": "🚕",
    "5811": "🍜", "5812": "🍽️", "5813": "🍸", "5814": "🍔",
    "5499": "🏪", "4899": "🎬", "5815": "📱",
}


def _get_emoji_map_for_report(account_id: str | None = None) -> dict[str, str]:
    """Build MCC → emoji map: prefer dynamic from rules, fallback to static."""
    from handlers.cashback import _get_emoji_map
    dynamic = _get_emoji_map(account_id)
    # Merge: dynamic wins, static fills gaps
    merged = dict(_FALLBACK_MCC_EMOJI)
    merged.update(dynamic)
    return merged


# Backward compat: export the old name for any external imports
CASHBACK_MCC_EMOJI = _FALLBACK_MCC_EMOJI


# ─── Period math ────────────────────────────────────────────────


def _period_range(period_code: str, now: datetime) -> Tuple[datetime, datetime]:
    tz = pytz.timezone(TIMEZONE)
    if now.tzinfo is None:
        now = tz.localize(now)
    if period_code == "w":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
    elif period_code == "q":
        m = ((now.month - 1) // 3) * 3 + 1
        start = now.replace(
            month=m, day=1, hour=0, minute=0, second=0, microsecond=0,
        )
    elif period_code == "y":
        start = now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0,
        )
    else:  # "m" or default
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def _period_label(period_code: str, start: datetime, now: datetime) -> str:
    if period_code == "w":
        return f"Tuần {start.strftime('%d/%m')} → {now.strftime('%d/%m/%Y')}"
    if period_code == "q":
        q = (now.month - 1) // 3 + 1
        return f"Quý {q}/{now.year}"
    if period_code == "y":
        return f"Năm {now.year}"
    return f"Tháng {now.strftime('%m/%Y')}"


# ─── Aggregation ────────────────────────────────────────────────


def _parse_tx_date(s: str, tz) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt


def _scan_period(period_code: str) -> dict:
    """Single pass through Transactions sheet. Builds aggregates for BOTH
    lenses so switching is just a re-render, not a re-scan.

    Returns:
      period_code, period_label
      by_account: list of {account_id, name, type, currency, out, in, out_count, in_count}
      by_bucket:  list of {bucket_id, name, spent, count, allocated}
                  — VND only (foreign tx not categorized). Includes allocated=0
                  for buckets that have spending but no allocation.
      total_out, total_in: VND only, confirmed only (matches legacy reports)
      internal_flows: transfer/cc_payment totals excluded from spending/income
      tx_count:  all tx within period (any currency)
      heaviest_day: (date_str, amount) for the highest-spend day, VND only
      daily_totals: {date_str: amount} for daily average / heaviest calc
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    start, end = _period_range(period_code, now)
    period_label = _period_label(period_code, start, now)

    accounts = sh.get_active_accounts()
    account_by_id = {a["id"]: a for a in accounts}

    # Bucket names: use current month config as a reference (allocations only
    # apply when period_code == "m"; for other periods we just need names).
    month_key_now = now.strftime("%Y-%m")
    buckets = sh.get_active_buckets(month_key_now)
    bucket_by_id = {b["id"]: b for b in buckets}

    ws = sh._sheet(S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]

    acc_agg: dict[tuple[str, str], dict] = {}
    bucket_agg: dict[str, dict] = {}
    daily_totals: dict[str, float] = {}
    total_out = total_in = 0.0
    internal_flows: dict[tuple[str, str], dict] = {}
    tx_count = 0

    for r in rows:
        if len(r) < 8:
            continue
        tx_dt = _parse_tx_date(r[1] if len(r) > 1 else "", tz)
        if not tx_dt or not (start <= tx_dt <= end):
            continue
        tx_type = r[6] if len(r) > 6 else ""
        if tx_type not in ("Tiền ra", "Tiền vào"):
            continue
        amount = sh._parse_amount(r[7]) or 0.0
        if amount <= 0:
            continue
        currency = sh.row_currency(r)
        ledger_tx_type = (r[17] if len(r) > 17 else "").strip()
        account_id = (r[16] if len(r) > 16 else "").strip()
        bucket_id = (r[10] if len(r) > 10 else "").strip()
        confirmed = (len(r) > 13 and str(r[13]).upper() == "TRUE")

        tx_count += 1

        if ledger_tx_type in ("transfer", "cc_payment"):
            key = (ledger_tx_type, currency)
            f = internal_flows.setdefault(key, {"amount": 0.0, "count": 0})
            f["amount"] += amount
            f["count"] += 1
            continue

        # By account (all currencies, separate groups)
        key = (account_id, currency)
        a = acc_agg.setdefault(
            key, {"out": 0.0, "in": 0.0, "out_count": 0, "in_count": 0},
        )
        if tx_type == "Tiền ra":
            a["out"] += amount
            a["out_count"] += 1
        else:
            a["in"] += amount
            a["in_count"] += 1

        # Top-of-page totals (VND, all tx — confirmed or not). Income
        # almost always has Confirmed=FALSE because users don't categorize
        # income; gating on confirmed would zero out total_in.
        if currency == "VND":
            if tx_type == "Tiền ra":
                total_out += amount
                d_key = tx_dt.astimezone(tz).strftime("%d/%m")
                daily_totals[d_key] = daily_totals.get(d_key, 0.0) + amount
            else:
                total_in += amount

        # By-bucket aggregation (confirmed-only — matches legacy /report).
        # Unconfirmed tx have empty bucket_id anyway, so this is mostly a
        # belt-and-suspenders check.
        if (
            currency == "VND"
            and tx_type == "Tiền ra"
            and confirmed
            and bucket_id
        ):
            b = bucket_agg.setdefault(
                bucket_id, {"spent": 0.0, "count": 0},
            )
            b["spent"] += amount
            b["count"] += 1

    # Resolve account names
    by_account = []
    for (acc_id, currency), totals in acc_agg.items():
        if acc_id:
            acc = account_by_id.get(acc_id)
            name = acc["name"] if acc else f"`{acc_id}` (deleted)"
            acc_type = acc["type"] if acc else None
        else:
            name = "Chưa gán account"
            acc_type = None
        by_account.append({
            "account_id": acc_id, "name": name, "type": acc_type,
            "currency": currency, **totals,
        })
    # Mapped first (by total flow desc), unmapped last
    by_account.sort(key=lambda g: (g["account_id"] == "", -(g["out"] + g["in"])))

    # Resolve bucket info. Allocation is only meaningful for monthly period.
    by_bucket = []
    for bid, totals in bucket_agg.items():
        b = bucket_by_id.get(bid)
        by_bucket.append({
            "bucket_id": bid,
            "name": b["name"] if b else bid,
            "allocated": (b.get("allocated", 0) if b else 0) if period_code == "m" else 0,
            "spent": totals["spent"],
            "count": totals["count"],
        })
    # Surface budgeted-but-no-spending buckets ONLY in monthly view (so user
    # sees their full budget hierarchy, not just what they spent on).
    if period_code == "m":
        spent_ids = {bb["bucket_id"] for bb in by_bucket}
        for b in buckets:
            if b["id"] in spent_ids:
                continue
            if b.get("allocated", 0) <= 0:
                continue
            by_bucket.append({
                "bucket_id": b["id"],
                "name": b["name"],
                "allocated": b["allocated"],
                "spent": 0.0,
                "count": 0,
            })
    # Sort: spent desc, then allocated desc
    by_bucket.sort(key=lambda b: (-b["spent"], -b["allocated"]))

    heaviest = max(daily_totals.items(), key=lambda x: x[1]) if daily_totals else None

    return {
        "period_code":   period_code,
        "period_label":  period_label,
        "by_account":    by_account,
        "by_bucket":     by_bucket,
        "total_out":     total_out,
        "total_in":      total_in,
        "internal_flows": [
            {
                "tx_type": tx_type,
                "currency": currency,
                **totals,
            }
            for (tx_type, currency), totals in sorted(internal_flows.items())
        ],
        "tx_count":      tx_count,
        "heaviest_day":  heaviest,
        "daily_totals":  daily_totals,
    }


# ─── Rendering ──────────────────────────────────────────────────


def _budget_alerts(by_bucket: list) -> list:
    """Buckets at warning (>=80%) or critical (>=100%). Returns
    list of (bucket_dict, symbol, pct_int).
    """
    alerts = []
    for b in by_bucket:
        if b["allocated"] <= 0:
            continue
        pct_f = b["spent"] / b["allocated"]
        if pct_f >= BUDGET_CRIT_PCT:
            alerts.append((b, "🔴", round(pct_f * 100)))
        elif pct_f >= BUDGET_WARN_PCT:
            alerts.append((b, "⚠️", round(pct_f * 100)))
    return alerts


def _render_account_lens(data: dict) -> str:
    """Account-first view (default). Budget alerts at the end as safety net."""
    lines = [
        f"📊 *Chi tiêu — {data['period_label']}*",
        "",
    ]
    # Top summary (VND only — multi-currency aggregation isn't meaningful)
    if data["total_out"] > 0 or data["total_in"] > 0:
        net = data["total_in"] - data["total_out"]
        net_sym = "+" if net >= 0 else "-"
        lines.append(
            f"💰 Ra: *-{sh.fmt_amount(data['total_out'])}*"
            f"  ·  Vào: +{sh.fmt_amount(data['total_in'])}"
            f"  ·  Net: {net_sym}{sh.fmt_amount(abs(net))}"
        )
    lines.append(f"📈 {data['tx_count']} tx")
    if data.get("internal_flows"):
        excluded = sum(f["count"] for f in data["internal_flows"])
        lines.append(f"_Đã tách {excluded} transfer/CC payment khỏi spending._")
    lines.append("")
    lines.append("━━━ 🏦 THEO ACCOUNT ━━━")
    lines.append("")

    if not data["by_account"]:
        lines.append("_Chưa có giao dịch nào trong kỳ này._")
    else:
        for g in data["by_account"]:
            emoji = TYPE_EMOJI.get(g["type"], "❓")
            lines.append(f"{emoji} *{g['name']}* ({g['currency']})")
            if g["in"] > 0:
                lines.append(
                    f"   Vào: +{sh.fmt_amount(g['in'], g['currency'])}"
                    f" ({g['in_count']} tx)"
                )
            if g["out"] > 0:
                lines.append(
                    f"   Ra:  -{sh.fmt_amount(g['out'], g['currency'])}"
                    f" ({g['out_count']} tx)"
                )
            lines.append("")

    if data.get("internal_flows"):
        lines.append("━━━ 🔁 INTERNAL / PAYMENTS ━━━")
        lines.append("")
        for f in data["internal_flows"]:
            label = "Chuyển khoản" if f["tx_type"] == "transfer" else "Trả CC"
            lines.append(
                f"{label}: {sh.fmt_amount(f['amount'], f['currency'])}"
                f" ({f['count']} tx)"
            )
        lines.append("")

    # Budget alerts — only meaningful for the monthly view (allocations are
    # set per month). For week/quarter/year, hide this section entirely.
    if data["period_code"] == "m":
        alerts = _budget_alerts(data["by_bucket"])
        if alerts:
            lines.append("━━━ ⚠️ CẢNH BÁO BUDGET ━━━")
            lines.append("")
            for b, sym, pct in alerts:
                lines.append(
                    f"{sym} {b['name']} — {sh.fmt_amount(b['spent'])}"
                    f" / {sh.fmt_amount(b['allocated'])} ({pct}%)"
                )
            lines.append("")

    return "\n".join(lines).rstrip()


def _render_category_lens(data: dict) -> str:
    """Category-first view: budget bars, tracking buckets, daily insights."""
    lines = [
        f"📊 *Chi tiêu — {data['period_label']}*  _(lens: category)_",
        "",
    ]
    # Top summary
    if data["period_code"] == "m":
        total_alloc = sum(b["allocated"] for b in data["by_bucket"])
        if total_alloc > 0:
            surplus = total_alloc - data["total_out"]
            surplus_pct = round(surplus / total_alloc * 100) if surplus > 0 else 0
            lines.append(
                f"💰 Tổng ra: *{sh.fmt_amount(data['total_out'])}* /"
                f" {sh.fmt_amount(total_alloc)} budget"
            )
            if surplus > 0:
                lines.append(
                    f"Còn dư: {sh.fmt_amount(surplus)} ({surplus_pct}% intact)"
                )
        else:
            lines.append(f"💰 Tổng ra: *{sh.fmt_amount(data['total_out'])}*")
    else:
        lines.append(f"💰 Tổng ra: *{sh.fmt_amount(data['total_out'])}*")
    lines.append(f"📈 {data['tx_count']} tx")
    lines.append("")

    if not data["by_bucket"]:
        lines.append("_Chưa có chi tiêu theo category trong kỳ này._")
    else:
        budgeted = [b for b in data["by_bucket"] if b["allocated"] > 0]
        tracking = [
            b for b in data["by_bucket"]
            if b["allocated"] == 0 and b["spent"] > 0
        ]

        if budgeted:
            lines.append("━━━ BUDGETED ━━━")
            for b in budgeted:
                pct = round(b["spent"] / b["allocated"] * 100) if b["allocated"] > 0 else 0
                bar = sh.make_bar(pct, 8)
                flag = " 🔴" if pct >= 100 else " ⚠️" if pct >= 80 else " ✅"
                lines.append(
                    f"{b['name']}  {sh.fmt_amount(b['spent'])}"
                    f" / {sh.fmt_amount(b['allocated'])}  {bar} {pct}%{flag}"
                )
            lines.append("")

        if tracking:
            lines.append("━━━ TRACKING ━━━")
            for b in tracking:
                if data["total_out"] > 0:
                    pct_of_total = round(b["spent"] / data["total_out"] * 100)
                    lines.append(f"{b['name']}  {sh.fmt_amount(b['spent'])} ({pct_of_total}% tổng chi)")
                else:
                    lines.append(f"{b['name']}  {sh.fmt_amount(b['spent'])}")
            lines.append("")

    # Insights
    insights = []
    if data["heaviest_day"]:
        day, amt = data["heaviest_day"]
        insights.append(f"🔥 Ngày chi nhiều nhất: {day} — {sh.fmt_amount(amt)}")
    if data["daily_totals"]:
        avg = sum(data["daily_totals"].values()) / len(data["daily_totals"])
        insights.append(f"📈 Trung bình/ngày: {sh.fmt_amount(avg)}")
    if insights:
        lines.extend(insights)

    return "\n".join(lines).rstrip()


def _cashback_category_label(name: str, mcc: str, account_id: str | None = None) -> str:
    emoji_map = _get_emoji_map_for_report(account_id)
    emoji = emoji_map.get(str(mcc).strip(), "")
    return f"{emoji} {name}" if emoji and not str(name).startswith(emoji) else name


def render_cashback_section(period_code: str = "m") -> str:
    """Global cashback summary appended to /report on BOTH lenses.

    Per configured credit card (current statement cycle): activation-gate
    progress, per-MCC accrued/cap bars, and pending/eligible totals. Returns ""
    when no credit card has cashback configured — keeps /report uncluttered.
    """
    cards = [a for a in sh.get_active_accounts() if a.get("type") == "credit"]
    blocks: list[str] = []
    now = datetime.now(pytz.timezone(TIMEZONE))
    for card in cards:
        cfg = sh.get_card_config(card["id"])
        if not cfg or not cfg.get("active"):
            continue
        cycle = sh.cycle_id(card["id"], now, card.get("statement_day"))
        ledger = [l for l in sh.get_cashback_ledger(card["id"], cycle) if l["status"] != "void"]
        rules = {r["match_value"]: r for r in sh.get_cashback_rules(card["id"])}

        block = [t("rpt.cb_card_header", name=card['name'], cycle=cycle.split('_')[-1])]
        gate = cfg.get("min_eligible_spend") or 0
        if gate > 0:
            spent = sh.eligible_spend_in_cycle(card["id"], cycle)
            pct = min(100, round(spent / gate * 100))
            block.append(t("rpt.cb_gate", spent=sh.fmt_amount(spent),
                           gate=sh.fmt_amount(gate), bar=sh.make_bar(pct, 8), pct=pct))
            if spent < gate:
                block.append(t("rpt.cb_gate_need", amount=sh.fmt_amount(gate - spent)))

        by_mcc: dict[str, float] = {}
        for l in ledger:
            if l["mcc_code"]:
                by_mcc[l["mcc_code"]] = by_mcc.get(l["mcc_code"], 0) + l["cashback_amount"]
        for mcc, accrued in sorted(by_mcc.items()):
            rule = rules.get(mcc)
            name = rule["rule_name"] if rule else f"MCC {mcc}"
            name = _cashback_category_label(name, mcc, card["id"])
            cap = (rule["monthly_cap"] if rule else 0) or 0
            if cap > 0:
                pct = min(100, round(accrued / cap * 100))
                block.append(f"{name}: {sh.fmt_amount(accrued)}/{sh.fmt_amount(cap)} "
                             f"{sh.make_bar(pct, 8)} {pct}%")
            elif accrued > 0:
                block.append(f"{name}: {sh.fmt_amount(accrued)}")

        pending = sum(l["cashback_amount"] for l in ledger if l["status"] == "pending")
        eligible = sum(l["cashback_amount"] for l in ledger if l["status"] == "eligible")
        total_cb = pending + eligible
        if total_cb > 0:
            block.append(t("rpt.cb_total", amount=sh.fmt_amount(total_cb)))
        if pending > 0:
            block.append(t("rpt.cb_pending", amount=sh.fmt_amount(pending)))
        if eligible > 0:
            block.append(t("rpt.cb_eligible", amount=sh.fmt_amount(eligible)))
        blocks.append("\n".join(block))

    if not blocks:
        return ""
    return f"\n\n{t('rpt.cb_section')}\n" + "\n\n".join(blocks)


def render_cashback_tx_detail(account_id: str, cycle: str, mcc: str = "") -> str:
    """Cashback snapshot for a card's statement cycle.

    Two callers, one format:
      - tx notice (FR-2.5): pass the triggering tx's `mcc` → section 1 shows
        just that category's accrued/cap bar;
      - on-demand /cashback view: pass mcc="" → section 1 lists EVERY configured
        category's accrued/cap bar (the full per-category breakdown).

    Always shown:
      2. cycle cashback total to date (= pending + eligible), then the activated
         (credited) portion — pending is accrued but not credited until the gate;
      3. cycle eligible-spend + bar vs the activation gate (5tr) + a short
         "Cần chi tiêu thêm X" reminder while still below it.

    Scope is the statement cycle (same scope as the 200k cap and 5tr gate).
    Returns "" when the card has no active cashback config.
    """
    acc = sh.find_account_by_id(account_id)
    cfg = sh.get_card_config(account_id)
    if not acc or not cfg or not cfg.get("active") or not cycle:
        return ""

    ledger = [l for l in sh.get_cashback_ledger(account_id, cycle) if l["status"] != "void"]
    rules = {r["match_value"]: r for r in sh.get_cashback_rules(account_id)}

    out = [f"💳 {acc.get('name', account_id)} · kỳ {cycle.split('_')[-1]}"]

    # 1. Per-category accrued vs per-cycle cap. A specific mcc (tx notice) → just
    #    that category; mcc="" (on-demand view) → every configured rule category.
    accrued_by_mcc: dict[str, float] = {}
    for l in ledger:
        if l["mcc_code"]:
            accrued_by_mcc[l["mcc_code"]] = accrued_by_mcc.get(l["mcc_code"], 0) + l["cashback_amount"]
    mccs_to_show = [mcc] if mcc else sorted(rules.keys())
    for m in mccs_to_show:
        rule = rules.get(m)
        name = _cashback_category_label(rule["rule_name"] if rule else f"MCC {m}", m, account_id)
        accrued = accrued_by_mcc.get(m, 0)
        cap = (rule["monthly_cap"] if rule else 0) or 0
        if cap > 0:
            pct = min(100, round(accrued / cap * 100))
            out.append(f"{name}: {sh.fmt_amount(accrued)}/{sh.fmt_amount(cap)} "
                       f"{sh.make_bar(pct, 8)} {pct}%")
        elif accrued > 0:
            out.append(f"{name}: {sh.fmt_amount(accrued)}")

    # 2. Cycle cashback total to date = pending + eligible; show total first,
    #    then the activated (credited) portion. (pending = total − activated.)
    eligible = sum(l["cashback_amount"] for l in ledger if l["status"] == "eligible")
    pending = sum(l["cashback_amount"] for l in ledger if l["status"] == "pending")
    total = eligible + pending
    out.append(f"Σ hoàn kỳ này: {sh.fmt_amount(total)} · "
               f"✅ đã kích hoạt {sh.fmt_amount(eligible)}")

    # 3. Activation gate: cycle eligible-spend vs threshold + remaining reminder.
    gate = cfg.get("min_eligible_spend") or 0
    if gate > 0:
        spent = sh.eligible_spend_in_cycle(account_id, cycle)
        pct = min(100, round(spent / gate * 100))
        out.append(f"Tổng chi tiêu hợp lệ: {sh.fmt_amount(spent)}/{sh.fmt_amount(gate)} "
                   f"{sh.make_bar(pct, 8)} {pct}%")
        if spent < gate:
            out.append(f"⏳ Cần chi tiêu thêm {sh.fmt_amount(gate - spent)} "
                       f"để đủ điều kiện hoàn tiền")
        else:
            out.append("✅ Đã đủ điều kiện hoàn tiền kỳ này")

    return "\n".join(out)


def _buttons(period_code: str, lens_code: str) -> list:
    def period_label(c: str) -> str:
        name = PERIOD_LABEL[c]
        return f"✅ {name}" if c == period_code else name
    def lens_label(c: str, lbl: str) -> str:
        return f"✅ {lbl}" if c == lens_code else lbl

    row_period = [
        {"text": period_label("w"), "callback_data": f"rpt_w_{lens_code}"},
        {"text": period_label("m"), "callback_data": f"rpt_m_{lens_code}"},
        {"text": period_label("q"), "callback_data": f"rpt_q_{lens_code}"},
        {"text": period_label("y"), "callback_data": f"rpt_y_{lens_code}"},
    ]
    # Category first (left) because it's the default lens — reading left→right
    # the user lands on the active selection first, account is the secondary
    # toggle on the right.
    row_lens = [
        {"text": lens_label("c", "📂 Category"), "callback_data": f"rpt_{period_code}_c"},
        {"text": lens_label("a", "🏦 Account"),  "callback_data": f"rpt_{period_code}_a"},
    ]
    return [row_period, row_lens]


# ─── Public entry points ────────────────────────────────────────


_PERIOD_ALIASES = {
    "tuần": "w", "tuan": "w", "week": "w", "w": "w",
    "tháng": "m", "thang": "m", "month": "m", "m": "m",
    "quý": "q", "quy": "q", "quarter": "q", "q": "q",
    "năm": "y", "nam": "y", "year": "y", "y": "y",
}


async def cmd_report(text: str = ""):
    """`/report [tuần|tháng|quý|năm]` — unified spending report.

    Default: tháng + 📂 Category lens — budget bars + warnings are the
    most frequent need on open. Account lens (project-goal view) is one
    tap away via the lens-toggle row.

    Period arg is optional; lens always defaults to category on first
    show and changes only via inline button.
    """
    period_code = "m"
    parts = (text or "").strip().split()
    if len(parts) >= 2:
        period_code = _PERIOD_ALIASES.get(parts[1].lower(), "m")
    lens_code = "c"

    data = _scan_period(period_code)
    msg = _render_account_lens(data) if lens_code == "a" else _render_category_lens(data)
    msg += render_cashback_section(period_code)  # global, both lenses
    buttons = _buttons(period_code, lens_code)
    await tg.send_with_buttons(msg, buttons)


async def handle_report_callback(parts: list[str], message_id: int):
    """Callback router: `rpt_<period>_<lens>` → edit message in place."""
    if len(parts) < 3:
        return
    period_code = parts[1]
    lens_code = parts[2]
    if period_code not in PERIOD_CODES or lens_code not in LENS_CODES:
        return

    data = _scan_period(period_code)
    msg = _render_account_lens(data) if lens_code == "a" else _render_category_lens(data)
    msg += render_cashback_section(period_code)  # global, both lenses
    buttons = _buttons(period_code, lens_code)
    await tg.edit_message(message_id, msg, inline_keyboard=buttons)
