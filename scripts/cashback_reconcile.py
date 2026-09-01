#!/usr/bin/env python3
"""Cashback reconciliation — ước tính (Cashback Ledger) vs thực nhận (ngân hàng).

Đọc tab "Cashback Ledger" của một thẻ credit cho một kỳ sao kê, tổng hợp theo
status + theo MCC, và (tùy chọn) so với số cashback ngân hàng thực trả để soi lệch.
Dùng ở cuối mỗi kỳ sao kê để validate model (keyword→MCC + cap + cổng) — xem
implementation-plan-cashback.md / BRD FR-4.

Chạy:
  python scripts/cashback_reconcile.py <cc_id>                 # kỳ hiện tại
  python scripts/cashback_reconcile.py <cc_id> --cycle cake_2026-06
  python scripts/cashback_reconcile.py <cc_id> --actual 470000 # so với thực nhận
  python scripts/cashback_reconcile.py <cc_id> --unknown       # liệt kê tx chưa suy ra MCC (để bổ sung pattern)

Cần env như app (SHEET_ID + GOOGLE_CREDS_JSON/credentials.json). Đọc-only, không ghi sheet.
"""
import argparse
import os
import sys
from datetime import datetime

# Repo root on sys.path so `import sheets` works no matter the cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pytz
except Exception:
    pytz = None

import sheets as sh
from config import TIMEZONE


def _num(v) -> float:
    try:
        return sh._parse_amount(v)
    except Exception:
        try:
            return float(str(v).replace(",", "").replace("đ", "").strip() or 0)
        except Exception:
            return 0.0


def _fmt(n) -> str:
    try:
        return sh.fmt_amount(n)
    except Exception:
        return f"{int(round(n)):,}đ".replace(",", ".")


def _resolve_cycle(cc_id: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    acc = sh.find_account_by_id(cc_id)
    if not acc:
        msg = [f"❌ Không tìm thấy account '{cc_id}'.",
               "   ('cake_cc' chỉ là hint trong email parser — id thật là slug bạn đặt khi onboard.)"]
        try:
            accs = sh.get_active_accounts()
        except Exception:
            accs = []
        if accs:
            msg.append("\n   Account đang có (★ = credit):")
            for a in accs:
                star = "★" if a.get("type") == "credit" else " "
                msg.append(f"     {star} {a.get('id'):<16} type={a.get('type')}  {a.get('name','')}")
            msg.append("\n   → Dùng id của thẻ credit ở trên, hoặc onboard thẻ trước nếu chưa có.")
        else:
            msg.append("\n   Chưa có account nào → onboard thẻ Cake credit trước (gửi 1 giao dịch / dùng wizard).")
        sys.exit("\n".join(msg))
    if acc.get("type") != "credit":
        sys.exit(f"❌ '{cc_id}' không phải thẻ credit (type={acc.get('type')}).")
    stmt = acc.get("statement_day")
    if not stmt:
        sys.exit(f"❌ '{cc_id}' chưa có statement_day → không xác định được kỳ. "
                 f"Truyền --cycle thủ công.")
    now = datetime.now(pytz.timezone(TIMEZONE)) if pytz else datetime.now()
    return sh.cycle_id(cc_id, now, stmt)


def main():
    ap = argparse.ArgumentParser(description="Cashback reconciliation")
    ap.add_argument("cc_id", help="account id của thẻ credit (vd cake_cc)")
    ap.add_argument("--cycle", help="mã cycle (vd cake_2026-06); mặc định = kỳ hiện tại")
    ap.add_argument("--actual", type=float, help="số cashback ngân hàng thực trả (VND)")
    ap.add_argument("--unknown", action="store_true",
                    help="liệt kê các tx không suy ra được MCC / ngoài DS để bổ sung pattern")
    args = ap.parse_args()

    cycle = _resolve_cycle(args.cc_id, args.cycle)
    rows = sh.get_cashback_ledger(args.cc_id, cycle)
    if not rows:
        sys.exit(f"(Không có dòng cashback nào cho {args.cc_id} kỳ {cycle}.)")

    # Gom theo status (bỏ void) và theo MCC (chỉ dòng được hoàn).
    by_status: dict[str, float] = {}
    by_mcc: dict[str, dict] = {}
    reason_count: dict[str, int] = {}
    unknown_rows = []
    earned_statuses = ("eligible", "confirmed")

    for r in rows:
        status = str(r.get("status", "")).strip().lower()
        amt = _num(r.get("cashback_amount"))
        reason = str(r.get("reason", "")).strip()
        mcc = str(r.get("mcc_code", "")).strip() or "—"
        if status == "void":
            continue
        by_status[status] = by_status.get(status, 0.0) + amt
        if reason:
            reason_count[reason] = reason_count.get(reason, 0) + 1
        if reason in ("mcc_unknown", "mcc_not_eligible"):
            unknown_rows.append(r)
        if amt > 0 and status in earned_statuses:
            m = by_mcc.setdefault(mcc, {"earned": 0.0, "n": 0})
            m["earned"] += amt
            m["n"] += 1

    earned = sum(by_status.get(s, 0.0) for s in earned_statuses)
    pending = by_status.get("pending", 0.0)

    # Cap mỗi MCC (từ rules) để show progress /cap.
    caps = {}
    names = {}
    try:
        for rule in sh.get_cashback_rules(args.cc_id):
            if str(rule.get("match_type")) == "mcc":
                mv = str(rule.get("match_value", "")).strip()
                caps[mv] = _num(rule.get("monthly_cap"))
                names[mv] = rule.get("rule_name", "")
    except Exception:
        pass

    print(f"\n═══ Cashback reconciliation — {args.cc_id} · kỳ {cycle} ═══\n")
    print("Theo MCC (chỉ dòng được hoàn):")
    if by_mcc:
        for mcc, d in sorted(by_mcc.items(), key=lambda kv: -kv[1]["earned"]):
            cap = caps.get(mcc)
            label = names.get(mcc, "")
            cap_str = f" / {_fmt(cap)}" + (" ⚠️ ĐẦY" if cap and d["earned"] >= cap else "") if cap else ""
            print(f"  {mcc:<6} {label:<16} {_fmt(d['earned'])}{cap_str}  ({d['n']} gd)")
    else:
        print("  (chưa có dòng nào được hoàn)")

    print("\nTheo trạng thái:")
    for s, v in sorted(by_status.items()):
        print(f"  {s:<10} {_fmt(v)}")

    print(f"\n  ĐÃ KÍCH HOẠT (eligible+confirmed): {_fmt(earned)}")
    if pending:
        print(f"  CHỜ CỔNG (pending, chưa đạt mốc 5tr): {_fmt(pending)}")

    if reason_count:
        print("\n0đ theo lý do (đáng soi cho việc bổ sung pattern MCC):")
        for rs, c in sorted(reason_count.items(), key=lambda kv: -kv[1]):
            print(f"  {rs:<18} {c} dòng")

    if args.unknown and unknown_rows:
        print("\nGiao dịch chưa suy ra MCC / ngoài DS (xem mô tả để thêm pattern qua /cashback mcc):")
        for r in unknown_rows:
            print(f"  row {r.get('tx_row_num'):<5} {_fmt(r.get('eligible_amount'))}"
                  f"  reason={r.get('reason')}")

    if args.actual is not None:
        diff = args.actual - earned
        pct = (diff / args.actual * 100) if args.actual else 0
        sign = "+" if diff >= 0 else "−"
        print("\n─── Đối soát với thực nhận ───")
        print(f"  Ước tính : {_fmt(earned)}")
        print(f"  Thực nhận: {_fmt(args.actual)}")
        print(f"  Lệch     : {sign}{_fmt(abs(diff))}  ({pct:+.1f}%)")
        if abs(diff) > 0.05 * max(args.actual, 1):
            print("  ⚠️ Lệch >5% — soi: MCC suy luận sai, pattern thiếu, hoặc hiểu sai cap/cổng.")
    print()


if __name__ == "__main__":
    main()
