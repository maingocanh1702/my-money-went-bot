# Global Market Strategy — My Money Went

> **Date:** 2026-05-07 (created), 2026-05-10 (reframed + promoted to BRD)
> **Trigger:** Insights từ vòng 1 competitive research + 3 strategic questions
> **Status:** ✅ **Promoted into formal BRD** — see [docs/brd-en.md v4.0.0](./brd-en.md) (2026-05-10). This doc remains the **strategic rationale** + validation plan; brd-en.md is the canonical product spec.
> **Scope:** This doc defines the **Global market track** — parallel to (NOT replacement of) the VN market strategy in [docs/brd-vi.md](./brd-vi.md).
> **Read first:** [Market Strategy Overview](./market-strategy-overview.md) — explains how VN and Global tracks coexist.
> **TL;DR:** Global market needs its own ICP, capture stack, and pricing — VN's SePay+bank-email approach doesn't transfer. This doc specs the strategic rationale; [brd-en.md](./brd-en.md) is the formal BRD. VN track continues per [brd-vi.md](./brd-vi.md) unchanged.

---

## RELATIONSHIP TO VN MARKET STRATEGY

This document is **NOT** a pivot away from Vietnam. It is the spec for a **second, parallel market track** with its own transaction-capture mechanics, ICP, and pricing.

| Question | Answer |
|---|---|
| Does this replace brd-vi.md? | **No.** brd-vi.md (v3.1.0) remains canonical for VN market. brd-en.md (v4.0.0, this doc's spec) is canonical for global market. They are siblings. |
| Should we drop SePay / VN bank email parsing? | **No.** Those are VN-specific and stay committed for VN launch. |
| What's shared between tracks? | Phase 1-2 multi-tenant foundation, `messenger.send()` interface (Telegram + Discord + Messenger + future platforms), auth, admin tools, observability. |
| What's different? | Phase 3+ branches by market: capture stack (SePay+VN-bank-email vs Plaid+e-commerce-APIs), pricing tiers ($4/$9 vs $6/$12), ICP, GTM. **Zalo** is the only platform exclusive to VN (Phase 3+). |
| Separate Git repos for VN and Global? | **No** — single monorepo with `core/ + markets/vn/ + markets/global/` adapter pattern per [ADR-0001](./adr/0001-monorepo-not-split-repos.md). Re-evaluate Q3 2026. |

See [market-strategy-overview.md](./market-strategy-overview.md) for the full side-by-side comparison.

---

## TÓM TẮT 3 DECISION (Global track)

| # | Câu hỏi | Answer | Move (Global track only) |
|---|---|:---:|---|
| 1 | Global ICP definition? | ✅ Lock | **"E-commerce solopreneur"** (Stripe/Shopify/Etsy/PayPal users). Tagline **"Income from everywhere → one P&L"**. (VN keeps its 3 personas — see BRD.) |
| 2 | Build webapp/native app for global? | ✅ YES (web only) | Global MVP = **Telegram bot + read-only web dashboard**. NOT a native app in 12 months. (VN remains chat-only per BRD.) |
| 3 | Transaction capture for global? | ✅ Distinct from VN | **(a) Plaid/TrueLayer/Tink cho expense, (b) Stripe/PayPal/Shopify API + payout email parsing cho income, (c) Manual fallback**. VN continues SePay+bank email per BRD. |

---

## 1. STRATEGY & POSITIONING — REDEFINE

### 1.1 Vấn đề với positioning hiện tại

BRD v2.9.0 builds cho VN market với 3 personas: office worker / freelancer / online seller. Nếu reuse cùng positioning cho global track, **3 problems**:

| Problem | Why |
|---|---|
| **"Online seller" persona quá rộng globally** | Bao gồm cả Amazon FBA enterprise, Shopify $1M/year shop, side-hustle Etsy seller. WTP và pain rất khác nhau. |
| **"Telegram-first" không sell ở US/EU** | Telegram penetration thấp ở US (15-25%), users coi là sketchy/messaging-only. Ở UK/EU OK hơn (40-50%). |
| **Free/Pro/Business 3-tier mass-market** | Mass market đã bị Monarch + YNAB cover. White space chỉ ở niche. |

### 1.2 Recommended global-track positioning

**Global track focuses on 1 ICP only** (VN's 3 personas stay committed in BRD v2.9.0 — this scoping applies to global track only):

```
PRIMARY ICP: E-commerce Solopreneur
─────────────────────────────────
  Bán trên: Shopify / Etsy / Amazon FBA / TikTok Shop / Instagram Shop
  Revenue:  $2K-50K/month
  Pain:     "Income chia 5 platforms, bank account 1 nơi, 
             không biết shop thực sự lãi bao nhiêu sau khi trừ chi tiêu cá nhân"
  WTP:      $9-20/month (vs QBSE $20, Found $35, accountant $200+)
  Tools they use today: Excel + bank app + Stripe dashboard + Shopify reports
```

**Out of scope for global track** (vẫn served bởi VN track với localized strategy): office worker (global đã bị Monarch/Cleo dominate), freelancer-only (Lunch Money/Bonsai cover globally). Quyết định scope chỉ apply ở global track — VN BRD vẫn target cả 3 personas Minh/Linh/Hùng+.

### 1.3 New tagline candidates (test A/B)

| Candidate | Strength | Risk |
|---|---|---|
| **"Income from everywhere → one P&L"** | Clear value, không platform-specific | Hơi abstract |
| **"Stop running 3 apps for your side hustle"** | Concrete pain, ICP-specific | Có thể narrow quá |
| **"Personal vs Business in one chat"** | Shows the moat | Telegram-locked feel |
| **"Shopify + Etsy + Stripe in your bank app"** | Concrete platforms | Quá feature-y |

→ Recommendation test **#1 + #2** trên landing page A/B.

### 1.4 Implications

- **Domain strategy:** Giữ `mymoneywent.com`. Drop `tienvenoidau.com` cho global launch (focus VN sau).
- **Marketing channel:** Reddit r/Etsy, r/FulfillmentByAmazon, r/Shopify, r/sidehustle. Không phải r/personalfinance.
- **Content SEO:** "How to track Etsy + Shopify + personal finances together", "Best app for solopreneur P&L".

---

## 2. WEBAPP / NATIVE APP DECISION

### 2.1 Evidence từ research — chat-only KHÔNG scale

| Datapoint | Implication |
|---|---|
| **Charlie shutdown** (chat-only AI, 33% accuracy fail) | Users không trust chat-only cho financial data |
| **Cleo pivoted Messenger → native app** | Even with $300M ARR, messaging-first không enough |
| **Telegram finance bot retention <10% MAU** | Bot alone = users log 2-3 tx rồi ghost |
| **PiggyPal, TeleExpense, etc. <$10M ecosystem** | Toàn category messaging-first finance đang struggle |

### 2.2 Why standalone native app KHÔNG phải answer

| Reason | Detail |
|---|---|
| Cost prohibitive | Native iOS + Android = 6-9 months engineering, $80-150K |
| Already crowded | Competing with Monarch, YNAB, Copilot (đẹp + funded) |
| ICP đã có app | Solopreneur đã dùng Shopify/Stripe app — không thiếu thêm 1 app |
| Loss of differentiation | "Just another finance app" → mất moat low-friction chat |

### 2.3 Recommendation: Hybrid 3-layer architecture

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1: TELEGRAM BOT (Input Layer)                    │
│  ─────────────────────────────────────────              │
│  • Quick categorize tx via inline buttons                │
│  • Notification: incoming tx, daily recap                │
│  • Manual log: /add 50 coffee                            │
│  • Quick query: /today, /balance                         │
│  → Use: 80% daily interactions, low-friction             │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  LAYER 2: WEB DASHBOARD (Reading + Setup Layer)         │
│  ─────────────────────────────────────────              │
│  • Full P&L view (Personal vs Business)                 │
│  • Charts, trends, monthly/quarterly reports            │
│  • Connect integrations (Stripe, PayPal, Shopify, bank) │
│  • Settings, rules, custom categories                   │
│  • Read-only mobile responsive                           │
│  → Use: 20% interactions, depth + setup                 │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  LAYER 3: NATIVE APP (Defer to Year 2)                  │
│  ─────────────────────────────────────────              │
│  • Build only nếu PMF + revenue justify                 │
│  • Or use Telegram Mini App (web inside Telegram)       │
│  → Decision: re-evaluate at Month 12                    │
└─────────────────────────────────────────────────────────┘
```

### 2.4 Web dashboard MVP scope

| In MVP | NOT in MVP |
|---|---|
| Login (Telegram OAuth) | Native mobile app |
| P&L Personal vs Business view | Editing transactions (do qua bot) |
| Monthly/Quarterly reports | Real-time chat in web |
| Connect Stripe/PayPal/Shopify | Multi-user workspace |
| Bank link (Plaid/TrueLayer) | Goal setting, gamification |
| Settings (categories, rules) | Investment tracking |
| CSV/PDF export | Crypto support |

**Tech stack đề xuất:** Next.js + Supabase (auth via Telegram bot) + Recharts. Build time ~4-6 weeks cho 1 dev mid-level.

### 2.5 Implication cho global track scope (NOT a change to VN BRD)

VN BRD section 4.4 ghi "Web dashboard = Out of scope, lý do: UI chính là messaging platform" — **đây là decision đúng cho VN market**, không cần thay đổi. Web dashboard read-only chỉ IN scope cho **Global track MVP**, lý do: messaging UI alone không đủ cho financial data depth ở solopreneur ICP. VN ICP (Minh/Linh/Hùng+) khác, chat-only OK.

---

## 3. TRANSACTION CAPTURE — GLOBAL-SPECIFIC STACK

### 3.1 Why the global track needs its own capture stack

VN's capture stack (SePay webhook + bank email parsing) is **VN-specific** and stays committed for VN per BRD v2.9.0. The global market needs a **different stack** because:

| VN context (works for VN, ship per BRD) | Global reality (this doc's scope) |
|---|---|
| Banks gửi email transaction chi tiết | US/EU banks gửi minimal alerts (or none) — chỉ "transaction over $X" |
| SePay là bridge phổ biến cho real-time webhook | Không có SePay-equivalent — global dùng Plaid/TrueLayer/Tink (PSD2 / open banking) |
| Bank email parsing là path of least resistance | Bank email parsing là dead end ở US/EU/AU |

→ **Global track sẽ dùng Plaid/TrueLayer + e-commerce platform APIs + payout email parsing**, không thay thế VN stack — chạy song song.

### 3.2 Nhưng: có 1 form email parsing VẪN WORK — và còn tốt hơn

**E-commerce platform notification emails:**

| Platform | Email Type | Frequency | Data quality |
|---|---|---|---|
| **Stripe** | Payout summary, receipt | Daily/payout | High (amount, fees, net) |
| **PayPal** | Transaction notification | Each tx | High |
| **Shopify** | Order confirmation, payout | Each order + payout | High |
| **Etsy** | Sale notification, deposit | Each sale + deposit | Medium-High |
| **Amazon Seller Central** | Settlement report | Bi-weekly | High but complex |
| **TikTok Shop / Instagram** | Order, payout | Each order | Medium |

→ **Global track email parsing target:** **e-commerce platform payout emails** (Stripe/PayPal/Shopify/Etsy etc.), không phải bank emails. Đây là moat thực sự cho solopreneur ICP — không đối thủ nào focus vào đây. **(VN track tiếp tục parse bank emails per BRD — different problem, different solution.)**

### 3.3 Capture strategy by data type

| Data | Primary method | Backup | Markets |
|---|---|---|---|
| **Bank expenses (debit/credit cards)** | Plaid (US/CA) + TrueLayer (UK) + Tink (EU) | Manual log | Global |
| **E-commerce income** | Stripe API + PayPal API + Shopify API | Email parsing payout emails | Global |
| **Marketplace sales** | Etsy API + Amazon SP-API | Email parsing order/payout | Global |
| **Cash/transfer expenses** | Manual log via bot (`/add 50 coffee`) | Receipt OCR (Phase 2) | Global |
| **Subscriptions** | Auto-detect từ Plaid + flag recurring | Manual flag | Global |

### 3.4 Cost implication

| Provider | Cost | Coverage |
|---|---|---|
| Plaid | $0.30-0.60/account/mo + $X/transaction | 12,000+ banks US/CA/UK/EU |
| TrueLayer | ~£0.10/connection/mo | UK + EU PSD2 |
| Tink | Negotiated tiers | EU PSD2 |
| Stripe API | Free | Stripe accounts only |
| PayPal API | Free | PayPal accounts only |
| Shopify API | Free (need app review) | Shopify merchants |
| Etsy API | Free (limited rate) | Etsy sellers |

**Estimated cost for 1000 users (mixed mode):**
- Plaid + Stripe + Shopify avg: ~$1.50-3/user/month
- $9 Business tier - $3 cost = $6 gross margin = 67%
- Tier $4 Pro - $1.50 cost = $2.50 gross margin = 62%

→ Margin OK nhưng **Pro tier thinner than VN model**. Có thể cần re-price Pro lên $5-6/mo cho global, hoặc giảm Plaid coverage cho Free/Pro tier.

### 3.5 Privacy positioning vẫn còn

Mặc dù bây giờ phải dùng Plaid (cần bank credentials), vẫn có angles:
- "Optional bank link" — user có thể chọn manual-only mode (như EveryDollar)
- "Read-only access" — Plaid grants read-only, never write
- "We never store credentials" — Plaid handles, MMW chỉ nhận tokenized data
- "Delete data anytime" — GDPR/CCPA compliance built-in

**Privacy framing modified:** "Connect what you want, skip what you don't. We never see your password."

---

## 4. UPDATED PRODUCT MAP

```
                    ┌───────────────────────────────┐
                    │    My Money Went              │
                    │    (Solopreneur P&L)          │
                    └───────────────┬───────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
  ┌──────────┐                ┌──────────┐                ┌──────────┐
  │  INCOME  │                │ EXPENSES │                │   VIEW   │
  │  side    │                │   side   │                │  layer   │
  └─────┬────┘                └─────┬────┘                └─────┬────┘
        │                           │                           │
   • Stripe API                • Plaid (US/CA)             • Telegram bot
   • PayPal API                • TrueLayer (UK)            • Web dashboard
   • Shopify API               • Tink (EU)                 • CSV/PDF export
   • Etsy API                  • Manual log via bot        • Google Sheets sync
   • Email parsing              • Receipt OCR (Phase 2)
     (payout emails)
```

---

## 5. PRICING IMPLICATION

Cho global track ICP (e-commerce solopreneur), pricing có thể cao hơn VN tiers:

| Tier | OLD (VN-context) | NEW (global solopreneur) | Justification |
|---|---:|---:|---|
| Free | 45 tx/mo | 60 tx/mo, 1 bank, no e-com | Industry benchmark + habit-forming |
| Pro | $4/mo | **$6/mo** | Plaid cost + e-com platform 1 source |
| **Solopreneur** (renamed Business) | $9/mo | **$12/mo** | Stripe+PayPal+Shopify+Etsy unlimited + P&L |
| **Annual Pro** | — | $58/yr (19% off) | New |
| **Annual Solo** | — | $115/yr (20% off) | New |

**Justification $12 Solopreneur:** Stripe processing là $0.50-1/user/mo, multi-platform API access có cost. $12 vẫn rẻ hơn Monarch Plus $16.58, QBSE $20, Found $35 — và cover personal+business.

---

## 6. RISKS CỦA GLOBAL TRACK

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Solopreneur niche quá nhỏ | Medium | High | Validate qua 50-100 user survey trước commit |
| API integrations Stripe/Shopify rejected | Low-Medium | High | Prototype Stripe Connect first, test access |
| Plaid cost giết margin nếu user heavy | Medium | Medium | Tier Plaid limits per plan; passive aggregation |
| Web dashboard build chậm MVP | Medium | Medium | Scope chặt: read-only, no editing trong web |
| Email parsing platform emails rate-limited | Low | Medium | OAuth direct API integration làm primary, email = backup |
| Telegram bot không là channel hiệu quả cho US ICP | Medium-High | High | Add WhatsApp Cloud API + Discord bot từ Day 1 architecture |

---

## 7. WHAT TO VALIDATE TRƯỚC KHI COMMIT

| # | Question | Method | Decision threshold |
|---|---|---|---|
| 1 | E-commerce solopreneur có pay $12/mo cho consolidated P&L không? | 50-100 user survey + 10 interview | ≥30% "very likely" pay |
| 2 | Họ thực sự dùng nhiều platforms (Stripe + Shopify + Etsy)? | Survey question | ≥40% dùng ≥2 platforms |
| 3 | Họ open với Telegram bot làm UX chính? | Survey + prototype test | ≥50% comfortable với chat UX |
| 4 | Web dashboard có cần thiết không (vs full bot)? | A/B test 2 prototypes | Bot-only retention <2 weeks |
| 5 | Plaid cost reality cho 100 users? | Sandbox test, get pricing quote | <$3/user/month |
| 6 | Stripe/Shopify partner API access feasible? | Apply, test approval timeline | Approval ≤30 days |

→ **Recommended:** Run validation sprint **2-3 weeks** trước khi commit dev resources.

---

## 8. SUMMARY DECISION TABLE — VN vs GLOBAL TRACKS

Both tracks are committed. This table contrasts spec, NOT a replacement.

| Aspect | 🇻🇳 VN track (per BRD v2.9.0) | 🌐 Global track (this doc) |
|---|---|---|
| **Market** | Vietnam | Global, English-first |
| **Primary ICP** | 3 personas (office/freelance/seller — Minh/Linh/Hùng+) | E-commerce solopreneur ONLY |
| **Tagline** | "Bot Telegram theo dõi tài chính" | "Income from everywhere → one P&L" |
| **Capture method** | SePay webhook + email parse bank emails (TCB, Cake, ACB, STB, BIDV, MB) | Plaid + Stripe/PP/Shopify API + email parse PAYOUT emails |
| **UX surface** | Telegram + Messenger (feature-flagged) | Telegram bot + Web dashboard read-only |
| **Pricing** | Free / Pro $4 / Business $9 | Free / Pro $6 / Solopreneur $12 + annual plans |
| **Channels** | Telegram first, Messenger added | Telegram + WhatsApp Cloud + Discord (multi from Day 1) |
| **GTM target** | Facebook seller groups, VN content/SEO | r/Etsy, r/Shopify, r/FulfillmentByAmazon, r/sidehustle |
| **Web dashboard** | Out of scope | IN MVP scope (read-only) |
| **Launch target** | Tháng 9/2026 | TBD post-validation |

---

## 9. NEXT STEPS (Global track only — VN track ships per BRD independently)

**Tuần 1-2 (Decision):**
- [x] Founder confirm 2-track strategy (VN + Global parallel) — confirmed 2026-05-10
- [ ] Founder review + buy-in trên 3 global track decisions in this doc
- [ ] Decide validation sprint resource (does NOT block VN Phase 1-2 dev)

**Tuần 3-5 (Validation sprint — global only):**
- [ ] Survey 100 e-commerce solopreneurs (Stripe/Shopify/Etsy users) — recruit qua Reddit, IG, FB groups
- [ ] 10 deep interviews — test value prop "$12 P&L all platforms"
- [ ] Plaid sandbox sign-up + cost quote
- [ ] Stripe Connect partner application

**Tuần 6 (Decision gate — global track):**
- [ ] Go/No-Go meeting — review validation results vs decision thresholds
- [ ] If GO: promote this doc into formal `docs/global-brd.md` / `docs/global-prd.md`, scope global MVP (web dashboard + Plaid + e-com APIs)
- [ ] If NO-GO: park global track, re-evaluate later post-VN-launch

**Note:** VN Phase 1-2 foundation work (multi-tenant DB, messenger interface, auth) is **shared infrastructure** — it benefits the global track too if/when global goes ahead. No need to wait on global decision before starting VN Phase 1.

---

## Changelog

| Date | Change |
|---|---|
| 2026-05-07 | v1.0 — Initial draft framing this as a "pivot from VN to global" |
| 2026-05-10 | v1.1 — Reframed as **parallel global track** (not pivot/replacement). VN strategy per BRD v2.9.0 stays committed. Title, intro, section 3.1, section 8 (decision table), section 9 (next steps) updated. New cross-link to [market-strategy-overview.md](./market-strategy-overview.md). |
| 2026-05-10 | v1.2 — **Promoted into formal BRD** at [docs/brd-en.md v4.0.0](./brd-en.md). This doc role is now strategic rationale + validation plan; brd-en.md is canonical product spec. VN BRD references updated from `brd.md` (archived) to `brd-vi.md`. Channel architecture clarified: Telegram + Discord + Messenger shared, Zalo VN-exclusive. |

[Mở global market strategy doc](computer:///Users/maingocanh/Projects/MyMoneyWent/docs/strategic-pivot-global.md)
