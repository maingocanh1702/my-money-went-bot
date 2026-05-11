# My Money Went — Business Requirements Document (BRD)

> **Version:** v4.0.0
> **Created:** 2026-05-10
> **Last updated:** 2026-05-10
> **Status:** Draft — promoted from `strategic-pivot-global.md`, pending validation sprint per Section 11.
>
> **🌐 SCOPE NOTE:** This BRD specifies the **🌍 Global market track only**, focused on the e-commerce solopreneur ICP. Transaction capture stack (Plaid/TrueLayer/Tink for bank expenses + Stripe/PayPal/Shopify/Etsy/Amazon SP-API for income + e-commerce payout email parsing as backup), single ICP (e-commerce solopreneur), pricing tiers ($6 Pro / $12 Solopreneur), and channel mix (Telegram + Discord + Messenger + read-only web dashboard) are all **global-specific**. The **Vietnam market** track is a **parallel track** with its own capture stack (SePay + VN bank email parsing) and 3 personas (Minh/Linh/Hùng+) — see [docs/brd-vi.md](./brd-vi.md). Both tracks share Phase 1-2 multi-tenant foundation; they diverge from Phase 3+. Read [docs/market-strategy-overview.md](./market-strategy-overview.md) first to understand how the two tracks coexist. Strategic source: [./strategic-pivot-global.md](./strategic-pivot-global.md).
>
> **🏗️ CODE STRUCTURE:** Per [ADR-0001](./adr/0001-monorepo-not-split-repos.md), Global code lives at `markets/global/` (capture/payment/pricing/web_dashboard), shared foundation in `core/` (messenger, auth, db, tenant_context). Global-specific implementations (Plaid/TrueLayer/Tink, Stripe/Shopify/Etsy/PayPal/Amazon SP-API integrations, web dashboard, USD pricing) live in `markets/global/`. NOT a separate repo — single monorepo, adapter pattern shared with VN track. Re-evaluation triggers in ADR.
>
> **Change v4.0.0 vs v3.0.0 — MAJOR REWRITE:** Discarded VN-derived content (SePay, VN banks, Minh/Linh/Hùng+ personas, dual VND/USD pricing). Promoted strategic-pivot-global.md into BRD form. Distinct global ICP, capture stack, pricing, GTM, validation plan. Launch target moved from a fixed date to "TBD post-validation sprint" — this BRD has not been validated yet and represents forward-looking strategy, not a locked spec.

---

## 1. Project overview

### 1.1. Product name
**My Money Went** — multi-platform finance tracking for **e-commerce solopreneurs**. The product runs as a chat bot on **Telegram + Discord + Messenger** (MVP) plus a **read-only web dashboard** for depth views (P&L, charts, settings, integration setup). Tagline (A/B test candidates): *"Income from everywhere → one P&L"* and *"Stop running 3 apps for your side hustle"*.

### 1.2. Vision
Consolidate **income from everywhere → one P&L**. Solopreneurs sell on Stripe, PayPal, Shopify, Etsy, Amazon, TikTok Shop, Instagram Shop — and pay personal + business expenses out of the same bank account. My Money Went unifies all sources into a single Personal-vs-Business P&L without forcing the user to leave their messaging app for daily interactions, while offering a read-only web dashboard for monthly/quarterly depth and integration setup.

### 1.3. Background & problem

| # | Problem | Detail | Source status |
|---|--------|---------|---|
| 1 | **Income split across 5+ platforms** | Solopreneur sells on Shopify + Etsy + Amazon FBA + TikTok Shop + Instagram Shop, plus payment rails Stripe + PayPal. Each has its own dashboard. There is no consolidated "what did I actually earn this month, net of fees" view. **Working hypothesis — needs validation via 10 customer interviews (see Section 11).** | Working hypothesis |
| 2 | **Bank account is one nail; income is many hammers** | Personal expenses + business expenses + business income all flow through the same 1-2 personal bank accounts. Solopreneurs cannot tell, mid-month, whether the shop is actually profitable after personal withdrawals. | Working hypothesis |
| 3 | **Existing tools are mis-fit** | QuickBooks Self-Employed ($20/mo) is over-built and accounting-jargon-heavy. Found ($35/mo) is bank-bundled and US-only. Monarch ($16.58/mo Plus) is a personal-finance app — no e-commerce platform integration. Lunch Money / Copilot are pretty but personal-finance-focused. | Market observation |
| 4 | **Spreadsheet workflow leaks** | Solopreneurs typically maintain a Google Sheet with manual paste from each platform's CSV. It breaks at 2-3 platforms, takes 4-8 hours/month, and the Personal-vs-Business split is always wrong by ~5%. | Working hypothesis |

**Important note:** This section is grounded in **founder observation + secondary research on competitor pricing/positioning**, not primary user research. Before committing dev budget:
- Validate problems 1 + 4 via **10 customer interviews** with active e-commerce solopreneurs ($2K-50K/mo revenue, ≥2 platforms) recruited via Reddit + IG + FB groups.
- Decision threshold: **≥30% of survey respondents** (n=50-100) say "very likely to pay $12/mo" AND **≥40% use ≥2 e-commerce platforms** (per Section 11 / strategic-pivot-global.md Section 7).

### 1.4. Proposed solution
A multi-platform finance bot for e-commerce solopreneurs. The capture stack:
- **Bank expenses:** Plaid (US/CA) + TrueLayer (UK) + Tink (EU) — read-only open banking links.
- **E-commerce income (primary):** OAuth-based API integrations with Stripe, PayPal, Shopify, Etsy, and (Phase 2) Amazon SP-API.
- **E-commerce income (backup):** Payout email parsing — user forwards Stripe/PayPal/Shopify/Etsy payout emails to a unique inbound address; bot parses normalized transactions. This is the moat: no competitor focuses on payout emails, and it covers the long tail of platforms without OAuth integrations (TikTok Shop, Instagram Shop, etc.).
- **Manual fallback:** `/add 50 coffee` or web dashboard manual entry for cash and edge cases.

The product is a **3-tier subscription** (Free / Pro $6/mo / Solopreneur $12/mo) plus a **14-day Pro trial** for new users. UX is hybrid 3-layer: Telegram + Discord + Messenger bots for daily input + categorization (~80% of interactions), and a Next.js web dashboard for depth + setup (~20% of interactions, read-only for transactions). A native mobile app is **deferred to Year 2** per strategic-pivot-global.md Section 2.2.

### 1.5. From personal tool → SaaS
The original bot has been running as a single-user personal tool for the founder since April 2026 (VN-context, SePay-based — see `brd-vi.md`). The global track is a **net-new SaaS build**, not a port: it shares Phase 1-2 multi-tenant foundation, messenger interface, auth, admin tools, and observability with the VN track, but the capture stack, ICP, pricing, channels, and GTM are all distinct.

### 1.6. Bot ownership decision

**1 shared bot per platform, owned and operated by the platform** — users do NOT bring their own bot. This is the same architectural decision as the VN track and applies identically here. The user-facing TAM reference is updated from "Hùng+ TAM" (VN online seller) to **"e-commerce solopreneur TAM"** (global).

| Aspect | Self-hosted / BYO bot | SaaS shared bot (chosen) |
|---|---|---|
| Bot creation | User self-creates via @BotFather (Telegram) / Discord Developer Portal / Meta App Dashboard | Platform creates 1 bot per platform (Telegram + Discord + Messenger), all users share |
| Token management | User manages own `BOT_TOKEN` | Platform manages tokens in Railway env (`TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `MESSENGER_PAGE_TOKEN`) |
| Deployment | One instance per user | 1 instance per platform, multi-tenant DB |
| Setup time | 30-60 minutes (8 steps) | 2-15 minutes (1 of 3 onboarding paths) |
| User identification | Hardcoded `CHAT_ID` env | Lookup `users.platform_id` from DB (Telegram chat_id, Discord user_id, Messenger PSID) |
| TAM reachable | <1% (developer / tech-savvy only) | 100% solopreneur TAM (Telegram + Discord + Messenger) |

**Platform priority:**

| Platform | Status | Rationale |
|---|---|---|
| **Telegram** | ✅ MVP (primary) | Bot ecosystem mature, inline buttons + Mini App option, ~40-50% penetration in UK/EU solopreneur segments. Lower in US (~15-25%) — mitigated by Discord + Messenger co-channels. |
| **Discord** | ✅ MVP (co-primary) | Slash commands + bot API mature, strong overlap with US/UK solopreneur creator/community segments (Etsy, side-hustle, dropshipping Discords). |
| **Messenger** | ✅ MVP (co-primary) | Reaches Instagram Shop / FB Shop / TikTok Shop sellers who are primarily on Meta surfaces. Meta API restrictions are real but workable for a finance tool with explicit user opt-in. |
| **Zalo** | ❌ Out of scope (VN-only — see brd-vi.md) | Vietnam-specific. Not part of global track. |
| **WhatsApp Cloud API** | 🔜 Coming soon (Phase 3+) | Largest reach in EU/LatAm/SEA solopreneurs, but Cloud API has stricter rate limits and template-message rules. Defer until post-validation. |

**Why not let users bring their own bot?** Same comparison as VN track — preserved here:

| Approach | Pros | Cons |
|---|---|---|
| Shared bot (chosen) | UX 2-15 min onboarding, scales TAM, single codebase | Per-platform rate limits (Telegram ~30 msg/s, Discord ~50 msg/s, Messenger templated) |
| BYO bot (bring your own) | No per-user rate limit, no platform SPOF | 30-60 min setup kills conversion, support nightmare when users lose token, lose 50%+ of non-tech-savvy solopreneurs |
| Hybrid (shared default + BYO advanced) | Covers both segments | 2x complexity, neither path optimized |

→ **Shared bot is the only viable choice for mass-market consumer SaaS. Multi-platform (Telegram + Discord + Messenger) MVP reduces single-platform-failure risk and expands TAM coverage.**

**Operational implications:**
- Single point of failure per platform: Telegram suspends bot → only Telegram users are offline; Discord + Messenger users unaffected. Multi-platform reduces SPOF.
- Privacy: a token compromise on one platform = read access to conversations on that platform only. Token rotation runbook is mandatory **per platform**, stored in a secret manager (no commits, no logs).

---

## 2. Business goals

### 2.1. Short-term goals (3 months post-launch)

| # | Goal | Metric | Target |
|---|----------|--------|--------|
| 1 | Launch MVP | Multi-platform bots + read-only web dashboard live, 3-path onboarding (Plaid bank link + e-com OAuth + payout email forwarding) | **TBD post-validation sprint** (typically 3-5 months after Week 6 Go decision; see Section 11 + 8) |
| 2 | Beta users | Active beta solopreneurs | 10-30 |
| 3 | Retention | Users still active after 30 days | ≥60% |
| 4 | Onboarding completion | % beta users who connect ≥1 income source + ≥1 expense source | ≥70% |
| 5 | First paying conversion | ≥1 paying Pro/Solopreneur user in month 1 | 1 user |

### 2.2. Mid-term goals (6-12 months)

| # | Goal | Metric | Target |
|---|----------|--------|--------|
| 1 | Paid conversion (Pro) | Free → Pro | ≥10% |
| 2 | Paid conversion (Solopreneur) | Free → Solopreneur | ≥3% |
| 3 | Scale | Total active users | 100-500 |
| 4 | Multi-platform reach | % users on Discord or Messenger (vs Telegram) | ≥30% |
| 5 | MRR | Monthly Recurring Revenue | **$150-450** (revised for $6/$12 pricing) |

> **TODO:** User-count and MRR targets are placeholders until validation sprint completes. Re-baseline post-Week 6 Go decision.

### 2.3. KPIs tracked

| KPI | How measured | Frequency |
|-----|---------|----------|
| DAU (Daily Active Users) | Users with ≥1 interaction/day | Daily |
| Transactions/user/month | Avg tx count per user per month | Monthly |
| Categorization rate | % tx categorized / total tx | Weekly |
| Income source diversity | Avg # connected platforms per user | Monthly |
| Churn rate | Users inactive ≥14 days | Monthly |
| Conversion Free → Pro | Trial → paid Pro | Monthly |
| Conversion Free → Solopreneur | Trial → paid Solopreneur | Monthly |
| Free tier limit hit rate | % users hitting 60 tx/mo cap | Monthly |
| Web dashboard MAU | % active users who open dashboard ≥1x/month | Monthly |

---

## 3. User personas

> **Major change vs v3.0.0:** Minh / Linh / Hùng+ (VN-specific) are **removed**. Global track focuses on a single ICP — **e-commerce solopreneur** — with three sub-variants by revenue scale and platform count.

The global track collapses to **one primary ICP**. Sub-variants are for marketing segmentation and tier-mapping, not separate product builds.

### 3.1. Primary ICP: E-commerce Solopreneur

| Attribute | Detail |
|-----------|---------|
| **Age** | 26-45 (median 33) |
| **Geography** | US (40%), UK (15%), EU (20%), Canada/AU (15%), other English-first markets (10%) |
| **Revenue** | $2K-50K/month gross |
| **Platforms sold on** | Shopify / Etsy / Amazon FBA / TikTok Shop / Instagram Shop / direct via Stripe checkout |
| **Payment rails** | Stripe (60%), PayPal (50%), platform-native payouts (Shopify Payments, Etsy Payments) |
| **Banking** | 1-2 personal bank accounts (mixed personal + business). ~30% have a separate business account, ~70% don't. |
| **Team size** | Solo (75%), 1 part-time helper (20%), 2-3 helpers (5%) |
| **Tools used today** | Excel/Google Sheets + each platform's native dashboard + bank app + (sometimes) QuickBooks Self-Employed |
| **Tech comfort** | Comfortable with OAuth flows, can install a Telegram/Discord/Messenger bot with a 2-minute video |
| **Channel preference** | US: Discord + Messenger; UK/EU: Telegram + Discord; LatAm/SEA: WhatsApp (Phase 3+) |

**Job-to-be-done:**
> "When I check my finances at month-end, I want to know whether my shop is actually profitable after the personal money I pulled out — so I can decide whether to scale ad spend, restock, or slow down."

**Verbatim pain points** (validated via secondary research — Reddit r/Etsy, r/Shopify, r/sidehustle threads; **needs primary-research validation** per Section 11):

> "I have Stripe, Shopify Payments, and PayPal. End of month I export 3 CSVs and try to figure out what's actually mine vs the business. It takes 4 hours and I never trust the number."

> "QBSE doesn't connect to Etsy properly. Found is great but US-only. Monarch is for personal finance, not for my shop."

> "I just want to know if I should buy more inventory this week. I shouldn't need a CPA to answer that."

### 3.2. Sub-variants (for marketing segmentation / tier mapping)

| Variant | Revenue range | Platforms | % of ICP | Tier likely | WTP estimate |
|---|---|---|---|---|---|
| **(a) Side-hustle Etsy seller** | $2K-10K/mo | 1-2 (Etsy + maybe Stripe) | 40% | Free → Pro | $5-10/mo |
| **(b) Full-time Shopify owner** | $10K-50K/mo | 2-3 (Shopify + Stripe + maybe Etsy) | 35% | Pro → Solopreneur | $10-15/mo |
| **(c) Multi-platform veteran** | $30K-50K/mo | 3+ (Shopify + Etsy + Amazon + Stripe + PayPal) | 25% | Solopreneur | $12-25/mo |

> **TODO:** Sub-variant percentages are estimates based on competitor market sizing and Reddit thread sampling. Validate via survey question "how many platforms do you currently sell on?" in Section 11 sprint.

**WTP anchors (vs benchmarks):**
- QuickBooks Self-Employed: **$20/mo** (over-built, accounting-jargon)
- Found: **$35/mo** (bank-bundled, US-only, requires switching banks)
- Monarch Plus: **$16.58/mo** (personal finance, no e-com integration)
- Lunch Money: **$10/mo** (personal finance, freelancer-friendly, no e-com)
- Bonsai: **$24/mo** (freelancer billing, no e-com)
- Solopreneur DIY (Excel): $0 + 4-8 hours/month

→ My Money Went **Solopreneur $12/mo** sits below all paid e-com-aware benchmarks while delivering the consolidated P&L none of them offer. **Pro $6/mo** anchors below Lunch Money's $10 and matches the entry-level personal finance category.

### 3.3. Anti-personas (NOT the target)

| Not the target | Why | Where they should go |
|---|---|---|
| **Amazon FBA enterprise (>$1M/yr revenue)** | Need real ERP, multi-entity accounting, payroll, sales tax filing | Hire an accountant / use A2X + QuickBooks Online |
| **Side-hustle <$2K/mo** | Volume too low to justify $6/mo subscription | Stay on spreadsheet |
| **Pure freelancer (no e-com platforms)** | Doesn't need Stripe/Shopify/Etsy integrations | Lunch Money or Bonsai |
| **Personal finance only (no business income)** | Wrong product category | Monarch / Copilot / YNAB |
| **Investment / crypto tracking** | Wrong product category | Kubera / CoinTracker |
| **Inventory management** | Wrong product category | Cin7 / Sortly |
| **Tax filing** | Regulatory risk too high | TurboTax / accountant |

---

## 4. Product scope

### 4.1. In-scope MVP

**Decision:** MVP serves the full e-commerce solopreneur ICP with **3 capture paths** — Plaid bank linking (expenses), e-com OAuth (income primary), payout email forwarding (income backup). Manual fallback always available.

| # | Feature | Description | Tier |
|---|---------|-------|------|
| 1 | **Plaid bank linking** | OAuth-based bank link via Plaid (US/CA), TrueLayer (UK), Tink (EU). Read-only, never stores credentials. | All |
| 2 | **Stripe OAuth integration** | Connect Stripe account; pull payouts, transactions, fees | All |
| 3 | **PayPal OAuth integration** | Connect PayPal account; pull transactions and payouts | All |
| 4 | **Shopify OAuth integration** | Connect Shopify store via app; pull orders + payouts | Pro+ |
| 5 | **Etsy OAuth integration** | Connect Etsy shop; pull sales + deposits | Pro+ |
| 6 | **Payout email forwarding ingest** | Bot issues unique inbound address `u<id>@in.mymoneywent.com`; user forwards Stripe/PayPal/Shopify/Etsy payout emails; bot parses to canonical transaction schema | All |
| 7 | **Read-only web dashboard** | Next.js dashboard: P&L (Personal vs Business), monthly/quarterly charts, integration setup, settings, categories, rules, CSV export. **Read-only for transactions** (edits happen via bot). | All |
| 8 | **Telegram bot** | Inline buttons for categorization, `/today`, `/balance`, `/add`, daily recap | All |
| 9 | **Discord bot** | Slash commands `/today`, `/balance`, `/add`, `/categorize`, daily recap via DM | All |
| 10 | **Messenger bot** | Quick-reply categorization, daily recap, manual `/add` | All |
| 11 | **Auto transaction capture** | Plaid + e-com OAuth + email parser normalize into canonical transaction schema | All |
| 12 | **Personal vs Business split** | Tag each tx personal/business. Auto-default by source (Plaid bank → personal unless override; Stripe/Shopify/Etsy → business). Manual override anytime. | All |
| 13 | **P&L view** | Personal vs Business income/expense, real-time, in web dashboard | Pro+ (Free = view only Personal side) |
| 14 | **Category management** | Create/edit/delete categories via bot or web dashboard | All |
| 15 | **Auto-categorization (rule-based)** | System defaults for common merchants (UBER, AMAZON, ADOBE, FB ADS, GOOGLE ADS, STRIPE FEE, SHOPIFY FEE, ETSY FEE, etc.) + user-defined custom rules. Free: defaults only. Pro: +15 custom rules. Solopreneur: unlimited. | All (tiered) |
| 16 | **Manual log fallback** | `/add 50 coffee personal` via bot, or manual entry in web dashboard | All |
| 17 | **Daily recap** | Auto-send daily summary at user-configured time/timezone | All |
| 18 | **Multi-tenant isolation** | Each user's data fully isolated | All |
| 19 | **Free tier limits** | 60 tx/mo, 1 bank link, 1 e-com integration, 30-day history, 1 email forwarding source, 5 categories, system default rules only, no Personal/Business split (view Personal only) | Free |
| 20 | **14-day Pro trial** | New users default to Pro for 14 days, auto-downgrade to Free if not upgraded | Free |
| 21 | **Pro: multi-source** | 3 bank links, 3 e-com integrations, unlimited tx, unlimited history, 3 email sources, 15 custom auto-cat rules, Personal/Business split | Pro |
| 22 | **Pro: reports** | Weekly + monthly P&L reports (email + dashboard) | Pro |
| 23 | **Pro: CSV/PDF export** | Export to spreadsheet or PDF | Pro |
| 24 | **Solopreneur: unlimited** | Unlimited bank + e-com integrations + email sources + custom rules | Solopreneur |
| 25 | **Solopreneur: Google Sheets sync** | 2-way sync with Google Sheets for accountants | Solopreneur |
| 26 | **Solopreneur: priority support** | Email + chat support, <24h response | Solopreneur |

### 4.2. Phase 2 (post-MVP, ~3-6 months after launch)

| # | Feature | Tier | Description |
|---|---------|------|-------|
| 1 | **Amazon SP-API integration** | Pro+ | Connect Amazon Seller Central; pull settlement reports (bi-weekly, complex schema) |
| 2 | **TikTok Shop integration** | Pro+ | OAuth or email parsing fallback |
| 3 | **Instagram Shop integration** | Pro+ | Email parsing initially (Meta API access pending) |
| 4 | **Receipt OCR** | Pro+ | Upload photo of receipt → extract merchant, amount, category |
| 5 | **Multi-currency support** | Solopreneur | Track tx in native currency, convert to user's home currency for P&L |
| 6 | **Advanced P&L** | Solopreneur | Cost-of-goods-sold tracking, ad-spend attribution per platform, cohort margin analysis |
| 7 | **WhatsApp Cloud API** | All | Add WhatsApp as 4th channel for LatAm/SEA reach |
| 8 | **Quarterly/annual reports** | Pro+ | Tax-ready exports (Schedule C-friendly format for US users) |

### 4.3. Phase 3+ (validate before building)

| Feature | Description | Status |
|---|---|---|
| **Native iOS/Android app** | Re-evaluate at month 12 based on PMF + revenue. Telegram Mini App is a cheaper alternative. | 🔜 Year 2 evaluation |
| **Auto-categorization ML upgrade** | Upgrade rule-based → ML model (self-learns from user behavior, ≥10K tx data). Supplement, not replace, rules. | Backlog |
| **Team / multi-user workspace** | Multi-user shared workspace for solopreneurs hiring helpers | Backlog |
| **Tax filing assistance** | Schedule C / quarterly estimated tax helpers (regulatory complexity) | Backlog (high regulatory risk) |
| **Inventory tracking** | Light SKU + COGS tracking for Shopify/Etsy sellers | Backlog |

### 4.4. Out of scope

| # | Feature | Rationale |
|---|---------|-------|
| 1 | **Native iOS/Android app** | Deferred to Year 2 per strategic-pivot-global.md Section 2.2. Cost prohibitive ($80-150K, 6-9 months), category already crowded with Monarch/YNAB/Copilot, ICP doesn't need another app. |
| 2 | **Inventory management (full)** | Wrong product category. Use Cin7, Sortly, or platform-native. |
| 3 | **Invoice generation** | Wrong product category. Use Bonsai, Stripe Invoicing. |
| 4 | **Tax filing automation** | Regulatory risk too high. Cross-jurisdiction complexity (US/UK/EU each have different rules). |
| 5 | **Investment / crypto tracking** | Wrong product category. Use Kubera, CoinTracker. |
| 6 | **Editing transactions in web dashboard (MVP)** | All edits go through the bot for MVP. Reduces dashboard scope. Phase 2 may add. |
| 7 | **Real-time chat in web dashboard** | Bot is the chat surface. Dashboard is for reading + setup only. |
| 8 | **Multi-user workspace (MVP)** | Single-user only for MVP. Team workspace deferred to Phase 3+. |
| 9 | **Native Vietnamese support / VN bank email parsing / SePay / Zalo** | Belongs to VN track — see `brd-vi.md`. |

---

## 5. Business model

### 5.1. Pricing tiers

**3-tier USD pricing** — single global tier, no geo-pricing. Solopreneur ICP has higher WTP than VN price-sensitive segments and tolerates USD pricing parity with Western competitors.

| Tier | Monthly | Annual | Annual savings |
|---|---|---|---|
| **Free** | $0 | $0 | — |
| **Pro** | **$6/mo** | **$58/yr** ($4.83/mo) | 19% off |
| **Solopreneur** | **$12/mo** | **$115/yr** ($9.58/mo) | 20% off |

**Trial:** Every new user gets **14 days of Pro** free, no credit card required. Day 12: in-bot upgrade prompt. Day 14: auto-downgrade to Free, all data preserved.

**Pricing justification:**

| Anchor | Price | My Money Went vs anchor |
|---|---|---|
| QuickBooks Self-Employed | $20/mo | Solopreneur $12 = **40% cheaper**, no accounting jargon |
| Found | $35/mo | Solopreneur $12 = **66% cheaper**, no bank-switching required |
| Monarch Plus | $16.58/mo | Solopreneur $12 = **28% cheaper**, AND has e-com integrations |
| Lunch Money | $10/mo | Pro $6 = **40% cheaper**, AND has Stripe integration |
| DIY spreadsheet | $0 + 4-8h/mo | $6/mo saves ≥4h/mo @ ~$25/h freelancer time = $100/mo value → 16x ROI |

**Why $6 floor for Pro (not $4):** Plaid alone costs $1.50-3/user/mo (per strategic-pivot-global.md Section 3.4). At $4 Pro, Plaid + Postmark + Railway eats most of the margin. $6 gives room for ~60-70% gross margin while remaining the cheapest tier in the e-commerce-aware finance category.

**Feature matrix:**

| Feature | Free | Pro $6/mo | Solopreneur $12/mo |
|---------|------|----------------------|---------------------------|
| Plaid bank linking | 1 account | 3 accounts | Unlimited |
| Stripe / PayPal OAuth | 1 integration | 3 integrations | Unlimited |
| Shopify OAuth | ❌ | ✅ | ✅ |
| Etsy OAuth | ❌ | ✅ | ✅ |
| Amazon SP-API (Phase 2) | ❌ | ✅ | ✅ |
| Payout email parsing | 1 source | 3 sources | Unlimited |
| Transactions/month | **60** | Unlimited | Unlimited |
| Transaction history | 30 days | Unlimited | Unlimited |
| Personal vs Business split | View Personal only | ✅ Both | ✅ Both |
| P&L view | ❌ | ✅ | ✅ |
| Categories | 5 total | Up to 20 custom | Unlimited |
| Auto-cat rules | System defaults only | +15 custom rules | Unlimited custom rules |
| Web dashboard | ✅ Read-only basic | ✅ Full | ✅ Full |
| Weekly + monthly reports | ❌ | ✅ | ✅ |
| CSV/PDF export | ❌ | ✅ | ✅ |
| Google Sheets 2-way sync | ❌ | ❌ | ✅ |
| Multi-currency (Phase 2) | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |

### 5.2. Monetization strategy

#### 5.2.1. Persona-to-tier mapping (sub-variants from Section 3.2)

| Sub-variant | Revenue scale | Tier likely | WTP estimate |
|---------|-------------|-------------|------|
| (a) Side-hustle Etsy seller | $2-10K/mo | Free → Pro | $5-10/mo |
| (b) Full-time Shopify owner | $10-50K/mo | Pro → Solopreneur | $10-15/mo |
| (c) Multi-platform veteran | $30-50K/mo | Solopreneur | $12-25/mo |

#### 5.2.2. Conversion targets & revenue projection

> **TODO:** All revenue projections below are forward-looking estimates pending validation sprint (Section 11). Will be re-baselined post-Week 6 Go decision with actual signup-rate, trial-conversion, and churn data.

Free tier 60 tx/mo cap is set **above** typical solopreneur personal-only volume but **below** combined personal + business volume → ~50-60% of active users projected to hit limit → upgrade pressure.

**Churn assumption:** SaaS B2C global benchmark is 4-6%/month for solopreneur tools (vs 7-8% for VN B2C consumer). Apply **5%/mo** for projection.

**Conservative cohort (4% Pro + 2% Solopreneur paid, steady-state at 100 active users):**

| Tier | % active | Users | Gross MRR | Net after 5% churn |
|------|---------|----------|-----------|----|
| Free | 94% | 94 | $0 | — |
| Pro ($6) | 4% | 4 | $24 | $22.80 |
| Solopreneur ($12) | 2% | 2 | $24 | $22.80 |
| **Total** | 100% | 100 | **$48/mo** | **~$45.60/mo** |

**Steady-state at 500 active users:**

| Tier | % active | Users | Gross MRR | Net after 5% churn |
|------|---------|----------|-----------|----|
| Free | 94% | 470 | $0 | — |
| Pro ($6) | 4% | 20 | $120 | $114 |
| Solopreneur ($12) | 2% | 10 | $120 | $114 |
| **Total** | 100% | 500 | **$240/mo** | **~$228/mo** |

**LTV at 5% churn:**
- Pro: $6 / 5% = **$120**
- Solopreneur: $12 / 5% = **$240**

→ CAC payback: target CAC < $30 for Pro, < $60 for Solopreneur to keep LTV/CAC ≥ 4x.

**Sensitivity to churn:**

| Churn rate | MRR @ 500 active | LTV Pro | LTV Solopreneur |
|---|---|---|---|
| 3% (best case) | $233 | $200 | $400 |
| 5% (target) | $228 | $120 | $240 |
| 7% | $223 | $86 | $171 |
| 10% (worst case) | $216 | $60 | $120 |

#### 5.2.3. Upgrade trigger logic

| Trigger | Message | Target tier |
|---------------|---------|-------------|
| Day 12 of trial | "Trial ends in 2 days. Keep Pro for weekly P&L reports?" | Pro |
| Hit 30-day history limit | "Want to see transactions older than 30 days?" | Pro |
| Hit 50/60 tx (Free) | "You've used 50/60 transactions this month. Upgrade for unlimited." | Pro |
| Hit 60 tx (Free) | "Quota reached. New transactions won't be tracked until next month or upgrade." | Pro |
| Add 2nd bank or 2nd e-com integration (Free) | "Free supports 1 of each. Pro gives you 3, Solopreneur unlimited." | Pro/Solopreneur |
| Connect Shopify or Etsy (Free) | "Shopify and Etsy integrations are Pro features. Start a trial?" | Pro |
| Tag 5+ tx as 'business' (Free) | "Looks like you mix personal + business. Solopreneur gives you a full P&L split." | Solopreneur |
| Connect 3rd e-com integration (Pro) | "Solopreneur gives you unlimited integrations + Google Sheets sync." | Solopreneur |

Rule: max 1 upgrade message per week per user.

#### 5.2.4. Payment

- **Stripe Checkout** (primary) — credit card + Apple Pay + Google Pay. ~2.9% + $0.30/tx fee.
- **PayPal** (secondary, via Stripe or direct) — for users without credit card. ~3.5% + $0.30/tx.
- **Annual prepay** — pushes annual discount aggressively in monthly upgrade messages to reduce involuntary churn (annual = ~0% involuntary churn vs ~1-2% monthly).
- **Refund:** 14-day money-back, no questions asked.

**Recurring billing:**
- Monthly: reminder 3 days before renewal, grace period 7 days after failed charge, then auto-downgrade to Free.
- Annual: reminders 30 + 7 + 1 days before renewal.

### 5.3. Operating cost projection

> **TODO:** Cost numbers below are **estimates pending Plaid sandbox quote** (Section 11 Q5 / strategic-pivot-global.md Section 7). Re-validate after the validation sprint with actual pricing from Plaid + TrueLayer + Postmark.

#### 5.3.1. Pricing rates (May 2026 estimates)

| Resource | Estimated rate |
|----------|---------------|
| Plaid (US/CA) | $0.30-0.60/account/month + per-transaction fees → **~$1.50-3/user/mo blended** |
| TrueLayer (UK) | ~£0.10/connection/month |
| Tink (EU) | Negotiated tiers (similar order) |
| Stripe / PayPal / Shopify / Etsy APIs | Free (subject to app review and rate limits) |
| Railway Hobby (app + Postgres) | ~$15-50/mo depending on user scale |
| Postmark (inbound email parsing) | $10/mo (≤10K emails) → $35/mo (volume tier) |
| Domain + SSL | $1/mo |
| Backblaze B2 backup | $1-2/mo |

#### 5.3.2. Cost projection by scale

| Item | 10 users | 100 users | 500 users |
|----------|----------|-----------|-----------|
| Railway (app + Postgres) | $5 (min) | $15-25 | $40-80 |
| Plaid (~$1.50-3/user/mo, blended) | $15-30 | $150-300 | $750-1500 |
| Postmark | $10 | $10 | $35 |
| Backblaze B2 | $1 | $1 | $2 |
| Domain + SSL | $1 | $1 | $1 |
| **Total estimated fixed cost** | **~$32-47** | **~$177-337** | **~$828-1618** |

> **TODO:** **The Plaid line dominates cost at scale.** This is the single biggest validation question (Section 11 Q5). Real pricing may be lower if Plaid offers volume tiers or per-product pricing (Auth-only is cheaper than Transactions). Actions: (a) get Plaid sandbox quote, (b) negotiate volume tier, (c) consider tiering Plaid limits per plan (Free: no Plaid; Pro: 3 accounts; Solopreneur: unlimited).

**Cost-control levers:**
- **Tier Plaid by plan:** Free users get manual-only mode + e-com OAuth (no Plaid cost); Pro gets 3 Plaid accounts; Solopreneur unlimited. Cuts Plaid cost ~30-40% at 100 users.
- **Passive aggregation:** Refresh Plaid data daily (not real-time) for Free/Pro to reduce per-tx API cost.
- **Email parsing as primary income capture:** Stripe/PayPal/Shopify OAuth is free; only fall back to Plaid for non-platform transactions.

### 5.4. Break-even analysis

> **TODO:** Break-even numbers depend on Section 5.3 cost validation. Re-baseline after Plaid sandbox quote.

#### 5.4.1. Break-even at 100 users (rough estimate, $6 Pro / $12 Solopreneur, 6% paid mix)

Assuming 4% Pro + 2% Solopreneur:
- Revenue @ 100 users: $48/mo gross
- Cost @ 100 users: $177-337/mo (Plaid-dominated)

→ **At 100 users, the product is deeply cash-negative** (-$129 to -$289/mo). Break-even requires either:
- (a) Significantly higher conversion (10%+ paid), OR
- (b) Plaid cost lower than estimate (e.g., Auth-only tier or tiered-by-plan = ~$0.50/user/mo blended), OR
- (c) Founder subsidy through ~500-1000 users.

#### 5.4.2. Break-even at 500 users (rough estimate)

- Revenue @ 500 users: $240/mo gross
- Cost @ 500 users: $828-1618/mo

→ **Still cash-negative** at $1.50-3/user Plaid cost. The economics only work if Plaid blended cost is closer to $0.50/user (via tiering Free out of Plaid).

#### 5.4.3. Path to viable unit economics

| Lever | Impact |
|---|---|
| Tier Plaid out of Free (Free = e-com + email + manual only) | -30-40% Plaid cost; Free users still get value via e-com OAuth |
| Negotiate Plaid volume tier | -20-40% Plaid cost above ~500 users |
| Push annual conversion (target 30% of paid users on annual) | +0% involuntary churn → effective MRR +5-10% |
| Conversion 6% → 10% (via tighter Free limits + better trial onboarding) | +67% revenue at same user count |
| Self-host Plaid alternative (TrueLayer-only for UK, manual for US) | Lower coverage, lower cost — only viable for niche launch |

> **TODO:** Build a sensitivity model post-validation sprint with actual Plaid pricing. Decision: if Plaid blended cost > $1.50/user even after tiering, consider repositioning Free as **e-com + email + manual only (no bank link)** and making Plaid a Pro-only feature.

---

## 6. Competitive analysis

### 6.1. Competitor categorization

| Capability | Personal-finance-only | E-commerce-aware | Accountant-grade |
|-----------|-------------------|------|------|
| **Products** | Monarch, YNAB, Copilot, Lunch Money, Cleo | **My Money Went**, QuickBooks Self-Employed, Found | QuickBooks Online, Xero, FreshBooks |
| **TAM** | Mass-market personal finance | E-commerce solopreneur niche | SMB / accountant |
| **Pricing** | $5-17/mo | $12-35/mo | $25-90/mo |

### 6.2. Direct comparison

| Product | Pricing | E-com integrations | P&L Personal vs Business | Channel | vs My Money Went |
|----------|---------|---------------|------------------------|---------|----------------|
| **Monarch Plus** | $16.58/mo | ❌ (manual import only) | Partial (tags) | Web + mobile app | MMW: e-com integrations + cheaper |
| **YNAB** | $14.99/mo | ❌ | ❌ (envelope budgeting) | Web + mobile app | Different product (budgeting vs P&L) |
| **Lunch Money** | $10/mo | Stripe only | ❌ | Web | MMW: more e-com platforms |
| **Copilot** | $13/mo | ❌ | ❌ | iOS only | MMW: cross-platform + e-com |
| **QuickBooks Self-Employed** | $20/mo | Limited (Etsy partial, no Shopify direct) | ✅ | Web + mobile | MMW: 40% cheaper, no accounting jargon, more platforms |
| **Found** | $35/mo (incl. business banking) | Stripe + Shopify partial | ✅ | iOS + web (US-only) | MMW: 66% cheaper, no bank-switching, global |
| **Cleo** | Free + $5.99/mo Plus | ❌ | ❌ | Mobile + Messenger (pivoted away from chat-only) | Different audience (Gen Z personal finance) |
| **Bonsai** | $24/mo | ❌ | ✅ (freelancer focused) | Web | Different audience (pure freelancer, no e-com) |
| **DIY spreadsheet** | $0 + 4-8h/mo | Manual paste | Manual tag | N/A | MMW: automated + chat UX |

### 6.3. Direct competitor analysis: QuickBooks Self-Employed vs My Money Went Solopreneur

This is the **most direct head-to-head**:

| Dimension | QuickBooks Self-Employed | My Money Went Solopreneur |
|-----------|------------------------------|-------------|
| **Monthly cost** | $20/mo | $12/mo |
| **Annual cost** | $240 | $115 |
| **Bank linking** | ✅ (Plaid-equivalent) | ✅ (Plaid + TrueLayer + Tink) |
| **Stripe integration** | Limited | ✅ Native OAuth |
| **PayPal integration** | ✅ | ✅ |
| **Shopify integration** | ❌ direct (Etsy partial) | ✅ Native OAuth |
| **Etsy integration** | Partial | ✅ Native OAuth |
| **Amazon FBA** | ❌ | ✅ Phase 2 (SP-API) |
| **Personal vs Business split** | ✅ (rule-based) | ✅ (rule-based + manual override) |
| **Channel** | Web + mobile app | Telegram + Discord + Messenger + web dashboard |
| **Setup time** | 20-30 min | 5-15 min (3 paths) |
| **Tax filing helpers** | ✅ (Schedule C export) | Phase 2 |
| **Accounting jargon** | High (debits/credits, invoicing) | Low (chat-first UX) |
| **Geography** | US only | Global (US/CA/UK/EU at MVP) |

→ **My Money Went is positioned as "QBSE for the chat-first, multi-platform solopreneur generation"**: 40% cheaper, more e-com platforms, friendlier UX, global from day 1. QBSE wins on tax filing maturity (Phase 2 for MMW) and brand trust.

### 6.4. Real competitive advantages

1. **Multi-platform e-com OAuth + payout email parsing** — no competitor in the personal-finance category covers Shopify + Etsy + Stripe + PayPal as first-class. QBSE only partially covers them, Monarch/YNAB don't at all.
2. **Chat-first input + web-first depth** — daily interactions stay in the messenger surface (low friction); monthly/quarterly review happens in the dashboard. Competitors are app-only or web-only.
3. **Personal vs Business split** as a first-class concept — most personal finance tools don't have this; most accounting tools assume separate accounts. Solopreneurs live in the messy middle.
4. **3-path onboarding** — Plaid bank link, e-com OAuth, payout email forwarding. Cover 100% of the ICP regardless of which platforms they sell on or whether they're comfortable linking a bank.
5. **Global from day 1** — Plaid + TrueLayer + Tink + e-com APIs work in US/CA/UK/EU. Found is US-only. Lunch Money is US-only.
6. **Cheaper than every e-com-aware competitor** — $12 Solopreneur vs $20 QBSE / $35 Found / $16.58 Monarch.

### 6.5. Competitive risks

| Risk | Level | Mitigation |
|------|-------|-----------|
| QBSE lowers price or adds Shopify direct | Medium | Speed-to-market: launch + build community before they react |
| Monarch adds e-com integrations | Medium | Personal/Business split + chat UX is the moat — even if Monarch adds Stripe, they don't have Shopify/Etsy or chat |
| New entrant (Lunch Money expands e-com) | Medium | Founder solo can move faster than VC-backed teams; niche-first positioning |
| Plaid raises prices or revokes access | High | Multi-provider strategy (TrueLayer/Tink/Plaid) + email parsing fallback + manual mode |
| Stripe/Shopify/Etsy revoke partner API access | Low-Medium | Apply early, build relationships, have email parsing fallback ready |

---

## 7. Risks & mitigation

| # | Risk | Level | Mitigation |
|---|--------|--------|-----------|
| 1 | **Solopreneur niche too small** | Medium | Validate via 50-100 user survey + 10 interviews (Section 11). Decision threshold ≥30% "very likely to pay $12". |
| 2 | **Plaid cost kills margin** | High | Tier Plaid by plan (Free = no Plaid); negotiate volume tier; positioning fallback "e-com + email + manual" if Plaid economically infeasible. |
| 3 | **Stripe/Shopify partner API rejection or delay** | Low-Medium | Apply early during validation sprint (Section 11 Q6). Email parsing fallback ready for any platform without OAuth. |
| 4 | **Email parser accuracy < 85%** for any major platform (Stripe/PayPal/Shopify/Etsy) | High | Test parser with 50+ email samples per platform pre-launch. Build "unparsed" notification flow. Monitor weekly. |
| 5 | **Telegram not effective for US ICP** | Medium-High | Multi-platform from day 1: Discord + Messenger MVP. WhatsApp Phase 2. |
| 6 | **Web dashboard build delays MVP** | Medium | Scope tightly: read-only for transactions, no editing in dashboard MVP. 4-6 weeks for one mid-level dev (per pivot doc). |
| 7 | **Security breach — leak transaction or banking data** | High | Encrypt at rest, never store bank credentials (Plaid handles), audit log access, daily B2 backup, GDPR/CCPA compliance built-in. |
| 8 | **Low conversion Pro / Solopreneur** | Medium | Free 60 tx + 1 e-com integration cap forces upgrade pressure. A/B test pricing $5-7 Pro / $10-15 Solopreneur in beta. |
| 9 | **Solopreneur tier failure (TAM too small or P&L not perceived as $12 value)** | High | (1) Validate **before** building Phase 2 features via Section 11 sprint. (2) Threshold: ≥30% survey + ≥3/10 interviews say "yes $12". (3) Backup: reposition as Pro-only product, drop Solopreneur tier, target $200-300 MRR ceiling. |
| 10 | **GDPR / CCPA compliance** | High | Privacy policy clear, data retention policy, breach response plan, "delete data anytime" UX, DPA with Plaid + Postmark + Stripe. |
| 11 | **Multi-platform bot maintenance burden (3 platforms × 1 founder)** | Medium | `messenger.send()` interface abstracts platform differences. Per-platform adapters thin. Telegram primary; Discord/Messenger feature parity ≤30 days lag acceptable. |
| 12 | **Founder solo support burnout @ 200+ users** | High | Customer support automation (FAQ bot + self-serve troubleshooting) MUST ship before reaching 250 users. Hire part-time when MRR > $1000. |
| 13 | **Cost burn > revenue (valley of death) at 100-500 users** | High | Cost monitoring dashboard. Founder must accept ~$300-500/mo subsidy for first 6-9 months OR validate Plaid cost can be tiered to ~$0.50/user blended. |
| 14 | **Native app pressure from competitors** | Medium | Stay focused on chat-first + web; Telegram Mini App as cheaper alternative. Re-evaluate at month 12 only if PMF + revenue justify. |

---

## 8. Timeline overview

> **TODO:** Specific week-by-week timeline depends on Week 6 validation Go decision. Below is a notional plan assuming Go decision around Week 6 of validation sprint.

**Notional plan: ~16-20 weeks from Go decision** (vs VN track 14-16 weeks). Extra ~4 weeks for web dashboard scope.

| Phase | Duration | Deliverables |
|-------|-----------|-------------|
| **Phase 0: Validation sprint** | Weeks 1-5 | Survey 50-100 solopreneurs, 10 interviews, Plaid sandbox sign-up, Stripe Connect partner application. **Decision gate Week 6.** |
| **Phase 1: Foundation** | Weeks 7-8 | Repo, DB schema (multi-tenant + multi-platform + integrations table), `messenger.send()` interface (Telegram + Discord + Messenger adapters), Docker Compose |
| **Phase 2: Auth + handlers** | Weeks 9-10 | Multi-platform auth flow (Telegram OAuth → web dashboard via Supabase), tenant isolation, admin auth framework |
| **Phase 3: Capture stack** | Weeks 11-13 | Plaid + TrueLayer + Tink integration, Stripe + PayPal + Shopify + Etsy OAuth, payout email parser (4 platforms MVP), unparsed email fallback |
| **Phase 4: Bot + categorization** | Weeks 14-15 | Inline buttons / slash commands / quick replies, auto-categorization rules, manual `/add`, daily recap per timezone |
| **Phase 5: Web dashboard** | Weeks 16-19 | Next.js dashboard: P&L, charts, settings, integration setup, CSV/PDF export, read-only transactions |
| **Phase 6: Pricing + payments + admin** | Weeks 20-21 | Stripe Checkout, trial logic, upgrade triggers, admin tools, observability dashboard |
| **Phase 7: Closed beta** | Weeks 22-23 | 5-10 beta users, monitor parser accuracy, iterate critical bugs, test backup/restore |
| **Phase 8: Public soft launch** | Weeks 24-25 | 20-30 users, validate 3 onboarding paths, monitor cost vs revenue |

**Risk timeline:**

| Phase | Slip likelihood | Mitigation |
|---|---|---|
| Phase 0 validation | Medium | Survey response rate < 30 → extend by 2 weeks |
| Phase 3 (capture) | High | If Plaid cost prohibitive or Stripe partner approval delays, scope down to TrueLayer + email parsing only |
| Phase 5 (web dashboard) | High | If slipping, ship MVP with bot-only and dashboard read-only basic; full dashboard in v1.1 |

---

## 9. Stakeholders

| Role | Person | Responsibility |
|---------|-------|-------------|
| Product Owner | Founder | Feature priority, pricing, persona prioritization, validation Go/No-Go |
| Developer | Founder + AI pair | Implement, deploy, maintain |
| Beta testers (validation sprint) | 10 e-commerce solopreneurs recruited via Reddit/IG/FB | Survey + interview feedback, validate $12 WTP |
| Beta testers (Phase 7) | 5-10 paying-intent solopreneurs | UX feedback, bug reports, integration coverage validation |
| Users | Public (post soft launch) | Use, feedback, pay |
| Legal advisor (ad-hoc) | Freelance lawyer (US + EU jurisdictions) | GDPR/CCPA review, payment terms, Plaid + Stripe DPA review |

---

## 10. Success criteria

> **TODO:** All numeric targets pending validation sprint baseline.

### MVP launch (Phase 8, ~Week 25 from Go decision)

**Functional criteria:**
- [ ] Bot operates stably for ≥10 concurrent users on each of 3 platforms (Telegram + Discord + Messenger)
- [ ] **3-path onboarding** functional: Plaid bank link, e-com OAuth (≥4 platforms: Stripe + PayPal + Shopify + Etsy), payout email forwarding
- [ ] Web dashboard live with P&L, charts, settings, integration setup
- [ ] Zero data cross-contamination between users (multi-tenant isolation)
- [ ] Daily recap fires on correct timezone for each user
- [ ] Trial flow works (auto-downgrade Day 14)
- [ ] Free tier limits enforced correctly (60 tx, 1 bank, 1 e-com integration, 30-day history)
- [ ] Admin tools commands working end-to-end (cross-track shared spec)

**Reliability criteria:**
- [ ] Uptime ≥99% over 2-week beta
- [ ] **Email parser accuracy ≥85%** per platform (Stripe + PayPal + Shopify + Etsy) — test 50+ samples per platform
- [ ] Plaid integration uptime ≥99% (graceful degradation when Plaid down)
- [ ] Backup recovery test passes (full DB restore from B2 to staging)
- [ ] Critical alerts armed, routing to admin notification channel

**Cost criteria:**
- [ ] Actual cost ≤ projected estimate at 10-30 users (validate Plaid cost reality)
- [ ] **Per-user blended cost ≤ $2/user/month at 100 users** (post-tiering)
- [ ] Cost dashboard active showing Railway + Plaid + Postmark + Stripe vs MRR weekly

**Onboarding criteria:**
- [ ] Plaid bank link path: median ≤5 min from /start to first transaction
- [ ] E-com OAuth path: median ≤8 min for Stripe/Shopify/Etsy each
- [ ] Email forwarding path: median ≤10 min (forward rule setup is bottleneck)
- [ ] ≥80% beta users complete onboarding in 1 session

**Operational readiness:**
- [ ] Disaster recovery runbook documented (cross-track shared)
- [ ] Backup credentials stored in password manager, shared vault with 1 trusted contact
- [ ] GDPR/CCPA privacy policy + data deletion UX live
- [ ] Plaid + Stripe + Postmark DPAs reviewed and signed

### 3 months post-launch
- [ ] ≥30 active users
- [ ] 30-day retention ≥60%
- [ ] ≥3 paying users (Pro or Solopreneur)
- [ ] Free → paid conversion ≥6%
- [ ] Free tier hit-limit rate 40-60% (validates gating)
- [ ] NPS ≥40 (in-bot survey)

### 12 months post-launch
- [ ] 100-500 active users
- [ ] MRR $150-450
- [ ] Free → Pro conversion ≥10%
- [ ] Free → Solopreneur conversion ≥3%
- [ ] Net margin ≥40% (after Plaid + payment fees + support time)

---

## 11. Validation plan (pre-build)

**Direct from strategic-pivot-global.md Section 7.** Run as a **2-3 week validation sprint** before committing dev resources to Phase 1.

### 11.1. Validation questions and decision thresholds

| # | Question | Method | Decision threshold |
|---|---|---|---|
| 1 | Will e-commerce solopreneurs pay $12/mo for consolidated P&L? | 50-100 user survey + 10 deep interviews | **≥30% "very likely to pay"** |
| 2 | Do they actually use multiple platforms (Stripe + Shopify + Etsy + …)? | Survey question | **≥40% use ≥2 platforms** |
| 3 | Are they open to a chat bot (Telegram/Discord/Messenger) as primary UX? | Survey + prototype test | **≥50% comfortable with chat UX** |
| 4 | Is the web dashboard necessary (vs bot-only)? | A/B test 2 prototypes | Bot-only retention <2 weeks → confirms dashboard need |
| 5 | What is the real Plaid cost for 100 users? | Plaid sandbox sign-up + pricing quote | **<$3/user/month** blended (or tier-able to <$1.50) |
| 6 | Is Stripe/Shopify partner API access feasible in <30 days? | Apply, test approval timeline | **Approval ≤30 days** for at least Stripe Connect |

### 11.2. Recruitment strategy

- **Reddit:** r/Etsy, r/FulfillmentByAmazon, r/Shopify, r/sidehustle, r/Entrepreneur — post survey link + offer $25 gift card for 30-min interview.
- **Instagram:** DM small-medium e-com sellers (1K-50K followers).
- **Facebook groups:** "Shopify Sellers", "Etsy Entrepreneurs", "Amazon FBA Sellers" — post value content first, then survey.
- **Twitter / X:** small-business / solopreneur Twitter (#buildinpublic, #shopify).

**Incentive:** $25-50 gift card (Amazon, Target, or PayPal) for 30-min interview. **Free 6 months Solopreneur tier** for those who complete the survey + a 60-min deep interview.

### 11.3. Decision gate (Week 6)

| Outcome | Action |
|---|---|
| **GO** (≥4 of 6 thresholds met, including #1 and #5) | Promote this BRD into PRD-level feature specs, scope global MVP (Phases 1-8), start Phase 1 (Foundation) |
| **PARTIAL** (2-3 thresholds met) | Re-scope: drop Solopreneur tier, ship Pro-only MVP at $6, focus on side-hustle (a) sub-variant, re-validate after 3 months of beta |
| **NO-GO** (<2 thresholds met) | Park global track, re-evaluate post-VN-launch with VN-validated infrastructure |

---

## 12. Go-to-market strategy

### 12.1. Channel hypothesis

The global track funnels through one ICP — **e-commerce solopreneur** — so GTM is more focused than the VN track's 2-funnel approach. All channels target the same ICP with content variants by sub-variant (side-hustle vs full-time vs multi-platform).

| Channel | Cost expectation | Test priority | Hypothesis |
|---------|-----|----|---|
| **Reddit (r/Etsy, r/Shopify, r/FulfillmentByAmazon, r/sidehustle)** | $0 + 5-10h/week engagement | Week 1-4 | Story-format posts ("I built a tool to consolidate my Stripe + Shopify + Etsy P&L → opening it up") convert with tech-savvy solopreneurs. Value-first comments before any pitch. |
| **Indie Hackers** | $0 | Week 2-4 | Build-in-public + monthly revenue posts. Audience overlap with solopreneur ICP. |
| **Twitter/X solopreneur community** | $0 + time | Week 1-8 | #buildinpublic + reply guy strategy on Shopify / Etsy / solopreneur threads |
| **Content SEO (English blog)** | $50-100/mo (hosting) | Month 2-4 | "How to track Etsy + Shopify + personal finances together", "Best app for solopreneur P&L 2026", "QuickBooks Self-Employed alternatives for Shopify sellers" — long-tail SEO |
| **Friend/network referral** | $0 | Week 1 | 5-10 network solopreneurs test, organic word-of-mouth |
| **Product Hunt niche launch** | $0 | Week 4-8 | Niche Tuesday/Wednesday launch (not big launch), ride solopreneur category |
| **Reddit ads (small test)** | $50-100 / 30 days | Month 3-4 | Target r/Shopify + r/Etsy subreddits, $5-12 CAC target |
| **Instagram DM outreach** | $0 + time | Month 1-3 | DM small-medium sellers with personalized offer (free 1 month Solopreneur) |
| **Newsletter sponsorships (solopreneur niche)** | $200-500 per slot | Month 4-6 | Sponsor newsletters like "The Hustle", "Trends.vc", or niche e-com newsletters |
| **YouTube creator partnerships** | $300-1000 per video | Month 5-6 | Solopreneur YouTubers with 10K-100K subs (Shopify tutorials, Etsy tips) |

> **Channels NOT in scope for global track:** Facebook seller groups (VN-specific), VN content/SEO, Zalo, Telegram VN groups. These belong to brd-vi.md.

### 12.2. CAC budget by phase

> **TODO:** CAC targets pending Pro/Solopreneur LTV validation.

| Phase | Total CAC budget | CAC target/paying user | Rationale |
|---|---|---|---|
| Beta (0-30 users) | $0 | $0 | All organic + network |
| Soft launch (30-100 users) | $200-500 | $10-30 | Test 2-3 channels, learn what works |
| Growth (100-500 users) | $3000-6000 | $15-40 | Scale most-effective channel |

**LTV check:** Pro LTV = $120, Solopreneur LTV = $240 (at 5% churn). Keep CAC < $30 Pro, < $60 Solopreneur for healthy LTV/CAC ≥ 4x.

### 12.3. Acquisition funnel

**Free funnel (side-hustle Etsy seller sub-variant):**
```
Awareness (Reddit / blog) → Click landing → Telegram/Discord/Messenger bot start
→ Onboarding (5-15 min) → Day 1 first OAuth + first transaction
→ Day 7 activated → Day 14 trial end
```

**Free → Solopreneur funnel (multi-platform veteran sub-variant):**
```
Awareness (newsletter / YouTube) → Click "Solopreneur demo" landing
→ Schedule 30-min call OR self-serve trial → Day 1 connect 3+ platforms
→ Day 7 first P&L view (web dashboard) → Day 14 trial end → Upgrade Solopreneur
```

### 12.4. 90-day channel test plan post-MVP launch

| Week | Activity | Decision point |
|---|---|---|
| 1-2 | Launch organic: Reddit + Indie Hackers + Twitter + friend referral | Measure: signup rate, Free → trial conversion |
| 3-4 | Add: SEO blog (2 posts/week), Product Hunt niche launch | Compare CAC organic vs paid baseline |
| 5-8 | Test Reddit ads $100 budget | Measure CAC paid Pro |
| 9-12 | Test newsletter sponsorship + 1 YouTube creator | Measure CAC paid Solopreneur |
| Week 13 | **Decision:** Double down channels with CAC/LTV > 1.5x, kill channels < 1x |

### 12.5. GTM risks

| Risk | Level | Mitigation |
|------|------|---|
| Solopreneur not active on Telegram (US) | High | Discord + Messenger MVP. WhatsApp Cloud Phase 2. |
| Reddit auto-promote ban | Medium | Build relationship first, value-first content, partner with mods |
| US solopreneur saturated with "tool" pitches | Medium | Differentiation: "not accounting, not POS — chat-first P&L for solopreneurs" |
| Content SEO slow ramp (3-6 month timeline) | High | Don't rely on SEO for first 100 users — content is long-term play |
| Paid ad CAC unexpectedly high | Medium | Cap budget $200-500 per test, kill if CAC > $50 |

### 12.6. Quick wins in week 1 post-launch

1. Post on r/Etsy, r/Shopify, r/sidehustle, r/Entrepreneur with story format (no pitch, share build)
2. Indie Hackers launch post + monthly revenue commitment
3. DM 30-50 friends/network solopreneurs: "Try the bot, free 1 month Solopreneur"
4. Twitter thread: "I built a tool to consolidate Stripe + Shopify + Etsy + PayPal into one P&L. Here's what I learned…"
5. Submit Product Hunt niche launch (Tuesday/Wednesday)

→ Target week 1: 30-50 signups, 10-15 active users.

---

## Appendix

### A. Glossary

| Term | Definition |
|------|-----------|
| Workspace | Tenant boundary containing data, settings, integrations of one user |
| Channel Identity | User identity per platform: Telegram (chat_id), Discord (user_id), Messenger (PSID) |
| Source Connector | Plaid / e-com OAuth / payout email forwarding source ingesting transactions |
| Canonical Transaction | Internal normalized schema for all financial events |
| Personal vs Business split | Tag (personal / business / unknown) on each transaction; foundational for solopreneur P&L |
| ICP | Ideal Customer Profile — here: e-commerce solopreneur, $2-50K/mo revenue, ≥1 platform |
| WTP | Willingness to Pay |
| TAM | Total Addressable Market |
| Solopreneur | One-person e-commerce business, sells on ≥1 platform, mixes personal + business finances |

### B. References

| Document | Link |
|------|---|
| Strategic source (global track) | [./strategic-pivot-global.md](./strategic-pivot-global.md) |
| VN market BRD (parallel track) | [./brd-vi.md](./brd-vi.md) |
| Market strategy overview (VN + Global coexistence) | [./market-strategy-overview.md](./market-strategy-overview.md) |
| Current self-hosted repo | `/Users/maingocanh/Projects/Bot Finance` |

### C. Changelog

| Version | Date | Change |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial English BRD (effectively a translation of VN BRD, did NOT reflect global strategy) |
| v3.0.0 | 2026-05-09 | Synced with VN BRD v3.0.0 — dual VND/USD pricing, still VN-derived content |
| v4.0.0 | 2026-05-10 | **MAJOR REWRITE — Global track BRD:** Discarded VN-derived content (SePay, VN banks, Minh/Linh/Hùng+ personas, dual VND/USD pricing). Promoted strategic-pivot-global.md into formal BRD form. (1) Single ICP: e-commerce solopreneur with 3 sub-variants (side-hustle Etsy / full-time Shopify / multi-platform veteran). (2) Capture stack: Plaid + TrueLayer + Tink (bank) + Stripe/PayPal/Shopify/Etsy OAuth (e-com) + payout email parsing (backup). (3) Pricing: Free / Pro $6 / Solopreneur $12 + annual plans. Justified $6 floor by Plaid cost (~$1.50-3/user/mo). (4) Channels: Telegram + Discord + Messenger MVP + read-only web dashboard. WhatsApp Phase 2. Zalo dropped (VN-only). (5) GTM: Reddit r/Etsy/r/Shopify/r/FulfillmentByAmazon/r/sidehustle, Indie Hackers, Twitter, content SEO. Dropped Facebook seller groups + VN content. (6) Validation plan: 50-100 user survey + 10 interviews + Plaid sandbox quote + Stripe Connect application (per strategic-pivot-global.md Section 7). (7) Cost projection marked TBD pending Plaid quote. (8) Launch target = "TBD post-validation sprint". (9) Preserved Section 1.6 bot ownership decision and "why not BYO bot" comparison table. |

---

**End of Document**
