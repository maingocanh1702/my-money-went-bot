#!/usr/bin/env python3
"""Seed Cake Freedom cashback config — local, quota-safe.

Lý do tồn tại: `/cashback seed cake` trên bot nạp 23 MCC pattern + 5 rule + tiers
+ config, mỗi item đọc lại cả tab để dedupe → bùng >60 read/phút → APIError 429
('Read requests per minute per user'). Script này gọi ĐÚNG các hàm canonical
`sh.add_*` (không lệch format) nhưng bọc retry-on-429 per-call + nghỉ nhẹ giữa các
call, nên nó luôn chạy xong (tiến độ đơn điệu, idempotent — chạy lại an toàn).

Chạy:
  python scripts/seed_cake_cashback.py                 # tự chọn thẻ credit duy nhất
  python scripts/seed_cake_cashback.py cake_freedom    # chỉ định id

Cần env như app (SHEET_ID + credentials). Sau khi xong, kiểm bằng /cashback trên bot
hoặc: python scripts/cashback_reconcile.py cake_freedom
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sheets as sh
from handlers.cashback import CAKE_RULES, CAKE_TIERS, CAKE_TIER_SET, list_cashback_cards

SLEEP_BETWEEN = 1.2      # nghỉ nhẹ giữa các call để hạ nhịp đọc
BACKOFF_429 = 65         # quota là 'per minute' → nghỉ qua mốc phút
MAX_RETRY = 6


def _is_429(e: Exception) -> bool:
    s = str(e)
    return "429" in s or "Quota exceeded" in s or "RESOURCE_EXHAUSTED" in s


def with_retry(label: str, fn, *args, **kwargs):
    """Gọi fn; nếu dính 429 thì nghỉ qua mốc phút rồi thử lại (tới MAX_RETRY)."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = fn(*args, **kwargs)
            time.sleep(SLEEP_BETWEEN)
            return r
        except Exception as e:
            if _is_429(e) and attempt < MAX_RETRY:
                print(f"   ⏳ 429 ở '{label}' (lần {attempt}) → nghỉ {BACKOFF_429}s rồi thử lại...")
                time.sleep(BACKOFF_429)
                continue
            raise


def main():
    cc_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not cc_id:
        cards = list_cashback_cards()
        if len(cards) == 1:
            cc_id = cards[0]["id"]
        elif not cards:
            sys.exit("❌ Không có thẻ credit nào. Onboard thẻ Cake (type=credit) trước.")
        else:
            ids = ", ".join(c["id"] for c in cards)
            sys.exit(f"❌ Nhiều thẻ credit ({ids}). Truyền id: python scripts/seed_cake_cashback.py <id>")

    acc = sh.find_account_by_id(cc_id)
    if not acc or acc.get("type") != "credit":
        sys.exit(f"❌ '{cc_id}' không phải thẻ credit (hoặc không tồn tại).")

    print(f"🌱 Seeding cashback cho '{cc_id}' (quota-safe)...\n")

    # 1. Card config
    with_retry("config", sh.upsert_card_config, cc_id,
               cashback_rate=0.20, min_eligible_spend=5_000_000,
               cap_period="statement_cycle", alert_pct=0.80, active=True)
    print("  ✓ config (rate 20%, gate 5.000.000đ, BẬT)")

    # 2. Tiers (seed once)
    if not with_retry("get_tiers", sh.get_cashback_tiers, CAKE_TIER_SET):
        ws = sh._ensure_cashback_tiers_tab()
        for tx_min, tx_max, cap in CAKE_TIERS:
            nr = sh._next_row(ws, col=1)
            with_retry("tier", ws.update, f"A{nr}:D{nr}", [[CAKE_TIER_SET, tx_min, tx_max, cap]])
        sh.invalidate_cashback_caches()
        print(f"  ✓ tiers ({len(CAKE_TIERS)} bậc: 10k ≤199.999đ / 50k ≥200.000đ)")
    else:
        print("  • tiers đã có — bỏ qua")

    # 3. Rules + MCC patterns
    n_rules = n_pat = 0
    for mcc, name, max_day, pats in CAKE_RULES:
        with_retry(f"rule {mcc}", sh.add_cashback_rule, cc_id, name, "mcc", mcc,
                   rate="", monthly_cap=200000, per_tx_cap_tier=CAKE_TIER_SET,
                   max_eligible_tx_per_day=max_day)
        n_rules += 1
        added_here = 0
        for p in pats:
            if with_retry(f"mcc {p}", sh.add_mcc_map, p, mcc, name):
                n_pat += 1
                added_here += 1
        print(f"  ✓ rule {mcc} {name} (+{added_here} pattern)")

    print(f"\n✅ Xong: {n_rules} rule, {n_pat} pattern mới. "
          f"Kiểm: /cashback trên bot, hoặc python scripts/cashback_reconcile.py {cc_id}")


if __name__ == "__main__":
    main()
