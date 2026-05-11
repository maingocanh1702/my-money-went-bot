# Market Strategy Overview — VN vs Global

> **Version:** v1.1.0
> **Created:** 2026-05-10
> **Last updated:** 2026-05-10
> **Status:** Active — entry-point doc cho repo
> **Purpose:** Phân biệt rõ 2 market strategies song song. Đọc doc này TRƯỚC khi đọc BRD nào để khỏi nhầm framing.

---

## TL;DR

MyMoneyWent chạy **2 strategies song song**, mỗi market có capture stack + ICP + pricing riêng. **Channel architecture là shared** (Telegram + Discord + Messenger + future platforms qua `messenger.send()` interface). Chỉ **Zalo là VN-exclusive**.

| Aspect | 🇻🇳 VN market (Tiền Về Nơi Đâu) | 🌐 Global market (My Money Went) |
|---|---|---|
| **Status** | Primary near-term focus | Parallel track, validation phase |
| **Source of truth** | [docs/brd-vi.md v3.1.0](./brd-vi.md) | [docs/brd-en.md v4.0.0](./brd-en.md) (promoted from [strategic-pivot-global.md](./strategic-pivot-global.md)) |
| **Launch target** | Tháng 9/2026 | TBD (post-validation sprint) |
| **Transaction capture (expense)** | SePay webhook (real-time) + email parsing bank emails VN | Plaid (US/CA) + TrueLayer (UK) + Tink (EU) |
| **Transaction capture (income)** | Cùng pipeline expense (SePay/email báo có) | Stripe/PayPal/Shopify/Etsy/Amazon SP-API + payout email parsing |
| **Banks/integrations** | TCB, Cake, ACB, Sacombank/STB, BIDV, MB (VCB Phase 2) | 12,000+ banks via Plaid/TrueLayer/Tink |
| **ICP** | Minh (office worker) / Linh (freelancer) / Hùng+ (online seller) | E-commerce solopreneur ($2K-50K/mo revenue) — 3 sub-variants |
| **Tagline** | "Bot tự động theo dõi tài chính" | "Income from everywhere → one P&L" |
| **Channels (MVP)** | Telegram + Discord (co-primary), Messenger Phase 3+ | Telegram + Discord + Messenger (all 3 in MVP) + read-only web dashboard |
| **Channels (long-term)** | Telegram + Discord + Messenger + **Zalo (VN-only)** + future | Telegram + Discord + Messenger + WhatsApp + future (NO Zalo) |
| **Web dashboard** | Out of scope (chat-only UI) | In MVP scope (read-only, Next.js + Supabase) |
| **Payment** | Bank transfer + auto-detect (SePay/email), VietQR — 0% fee | Stripe (likely) — TBD |
| **Pricing** | Free / Pro $4 / Business $9 (VND-equivalent) | Free / Pro $6 / Solopreneur $12 + annual plans |
| **GTM channels** | Facebook seller groups, Telegram channels, VN content/SEO | r/Etsy, r/Shopify, r/FulfillmentByAmazon, r/sidehustle, Indie Hackers, Twitter |

---

## Why 2 strategies, not 1

VN bank email parsing + SePay không transfer được sang global, và Plaid + e-commerce APIs không make sense ở VN:

| Mismatch | Lý do |
|---|---|
| SePay không có equivalent ở US/EU/UK | Open banking ở VN chưa enforce — SePay là bridge phổ biến nhất. Global dùng Plaid/TrueLayer/Tink (PSD2). |
| US/EU banks gửi minimal/no transaction emails | Chỉ alert kiểu "transaction over $X". Không thể parse được như VN banks (gửi full chi tiết). |
| Vietnamese sellers KHÔNG dùng Stripe/Shopify | Thanh toán chủ yếu qua bank transfer, COD, ví điện tử. Stripe/PayPal/Shopify integration là dead code ở VN. |
| Plaid cost giết VN unit economics | $0.30-0.60/account/mo → margin âm ở $4 Pro tier VN. |
| ICP khác nhau hoàn toàn | VN target office worker / freelancer / online seller. Global target e-commerce solopreneur ($2K-50K/mo, multi-platform). WTP và pain khác. |

→ **Kết luận:** mỗi market cần **content stack riêng** (capture mechanism, ICP, pricing, GTM). **Channel architecture stack là chung** (Telegram + Discord + Messenger + future).

---

## Shared foundation (Phase 1-2 common work)

Phase 1-2 multi-tenant foundation work **support cả 2 track**, không bị sunk cost dù hướng nào tiến trước:

- ✅ Multi-tenant DB schema (users, channels, integrations table generic)
- ✅ `messenger.send()` interface — channel-agnostic, support Telegram + Discord + Messenger từ Day 1; Zalo + WhatsApp + future plug-in sau
- ✅ Auth + tenant isolation
- ✅ Admin tools + audit log framework
- ✅ Observability + DR runbook

→ Dev có thể start Phase 1-2 ngay theo brd-vi.md mà KHÔNG cần lock global decision trước. brd-en.md cũng reuse cùng foundation khi global track tiến vào dev.

---

## Where each track diverges

| Phase | 🇻🇳 VN track | 🌐 Global track |
|---|---|---|
| **1-2: Foundation** | Shared (multi-tenant DB + messenger interface for Telegram/Discord/Messenger) | Shared |
| **3: Pricing logic** | Free / Pro $4 / Business $9 (VND tiers) | Free / Pro $6 / Solopreneur $12 + annual plans |
| **4: Onboarding** | SePay quick connect + wizard | Plaid Link flow + e-commerce OAuth (Stripe/Shopify/Etsy/PayPal) |
| **5: Transaction capture** | Postmark + 6 banks VN parser (TCB/Cake/ACB/STB/BIDV/MB) | Plaid + Stripe/PayPal/Shopify/Etsy API + payout email parsing |
| **6: Polish/deploy** | VietQR + email payment, hộ kinh doanh registration blocker | Stripe payment, web dashboard read-only build (Next.js + Supabase) |
| **7-8: Beta + launch** | VN closed beta → soft launch tháng 9/2026 | Validation sprint (50-100 user survey + 10 interviews) trước khi commit dev |
| **Phase 3+: VN-only adds** | Zalo channel (Phase 3+, code path khác) | n/a — Zalo VN-only |
| **Phase 3+: Global-only adds** | n/a | WhatsApp Cloud API (US ICP coverage) |

---

## Decision flow — khi nào branch?

```
Phase 1-2 (Tuần 1-4): Shared foundation
                │
                ▼
        ┌───────────────┐
        │ Decision gate │  ← Lock primary track theo validation kết quả
        └───────┬───────┘
                │
        ┌───────┴───────┐
        ▼               ▼
   VN track         Global track
   (Phase 3-8       (Validation sprint
   theo brd-vi)     2-3 tuần trước
                    khi commit Phase 3+ dev
                    theo brd-en)
```

Cả 2 track có thể chạy parallel nếu resource cho phép, nhưng **KHÔNG nên start Phase 5 cả 2 cùng lúc** — phân tán effort. Recommend:
1. Lock VN track → ship MVP tháng 9/2026 theo brd-vi.md → revenue validate Hùng+ persona
2. Sau MVP launch, chạy global validation sprint song song (per brd-en.md Section 11)
3. Nếu global validate OK, Phase 2 (post-launch ~tháng 11-12) start global build trên cùng multi-tenant foundation

---

## Doc precedence — cái nào lock cái nào

| Question | Source of truth |
|---|---|
| VN market scope, features, timeline | [docs/brd-vi.md v3.1.0](./brd-vi.md) |
| Global market scope, features, timeline | [docs/brd-en.md v4.0.0](./brd-en.md) |
| VN product requirements | [docs/prd-vi.md v1.7.1](./prd-vi.md) |
| Global product requirements | [docs/prd-en.md v2.0.0](./prd-en.md) |
| Global strategic rationale + validation plan | [strategic-pivot-global.md](./strategic-pivot-global.md) (background; brd-en.md is the formal spec) |
| Tech architecture VN (shared foundation + VN capture) | [docs/tdd-vi.md v1.8.1](./tdd-vi.md) |
| Tech architecture Global (shared foundation + Global capture) | [docs/tdd-en.md v1.0.0](./tdd-en.md) |
| Transaction capture for VN | [feature-transaction-capture-tech.md](./features/BE/feature-transaction-capture-tech.md), [feature-payment.md](./features/feature-payment.md) |
| Transaction capture for Global | [prd-en.md §3.2](./prd-en.md), [tdd-en.md §6](./tdd-en.md) |
| Multi-channel architecture (Telegram/Discord/Messenger/Zalo/WhatsApp) | [feature-messenger-channel.md](./features/feature-messenger-channel.md) |
| Code structure (monorepo vs split repos) | [adr/0001-monorepo-not-split-repos.md](./adr/0001-monorepo-not-split-repos.md) — `core/ + markets/vn/ + markets/global/` adapter pattern |

**Khi brd-vi.md vs brd-en.md spec khác nhau:** Đó là **expected** — họ là spec cho 2 markets khác nhau. Mỗi BRD canonical cho market của mình.

**Khi brd-en.md vs strategic-pivot-global.md mâu thuẫn:** brd-en.md wins (formal spec). Pivot doc giờ chỉ là strategic background.

**Khi cần channel architecture decision:** feature-messenger-channel.md là source of truth — nó implement messenger interface cho cả 2 markets.

---

## Common pitfalls / framing checks

❌ "We're pivoting from VN to global" → SAI. 2 strategies song song.
❌ "Drop bank email parsing because Plaid replaces it" → SAI. Bank email parsing là VN-specific, Plaid là global-specific.
❌ "Strategic-pivot-global.md là canonical global spec" → SAI. brd-en.md là canonical; pivot doc giờ chỉ là background/rationale.
❌ "Discord là VN-specific channel" → SAI. Discord là shared channel cho cả 2 markets, in MVP cho cả hai.
❌ "Messenger là Global-only channel" → SAI. Messenger là shared channel — VN có Messenger Phase 3+, Global có Messenger MVP.
❌ "Phase 5 VN email parser là sunk cost nếu global track lên" → SAI. Phase 5 là VN feature, song song với global Plaid build, không bị ảnh hưởng.
❌ "brd.md (FinTrack v2.9.0) vẫn là canonical" → SAI. brd.md đã archived (xem `docs/archive/`). brd-vi.md + brd-en.md là canonical.

✅ "VN dùng SePay+VN-bank-email; Global dùng Plaid+e-commerce-APIs"
✅ "Phase 1-2 foundation shared, Phase 3+ content branches by market"
✅ "Channels Telegram+Discord+Messenger shared cho cả 2 market; Zalo VN-only"
✅ "brd-vi.md = VN spec, brd-en.md = Global spec, 2 BRDs canonical sibling"

---

## Changelog

| Date | Change |
|---|---|
| 2026-05-10 | v1.0.0 — Initial doc tạo sau founder clarify "2 markets, 2 strategies, parallel" |
| 2026-05-10 | v1.1.0 — Updated after structural changes: brd.md (FinTrack) archived; brd-en.md v4.0.0 promoted from strategic-pivot-global.md as canonical Global BRD; channel architecture clarified (Telegram+Discord+Messenger shared, Zalo VN-only). Source-of-truth table, divergence table, decision flow, pitfalls section all refreshed. |
| 2026-05-10 | v1.2.0 — Doc split: `prd.md` → `prd-vi.md` v1.7.1, `prd-en.md` v2.0.0 (full Global PRD rewrite), `tdd.md` → `tdd-vi.md` v1.8.1, `tdd-en.md` v1.0.0 (new Global TDD). Doc precedence table updated. Domains: VN = tienvenoidau.com, Global = mymoneywent.com. |
