# 📊 Feature Landscape Round 3 — Global Expense Tracker Apps

**Ngày:** 2026-05-08 | **Vòng:** 3 (Feature Deep-Dive)
**Apps research:** 15 | **Categories:** 12 | **Sources verified:** 200+

---

## 📑 MỤC LỤC

- **[PHẦN 1](#phần-1--master-feature-matrix)** — Master Feature Matrix (15 × 12)
- **[PHẦN 2](#phần-2--app-feature-summary-cards)** — App Feature Summary Cards (full cards trong `cards/`)
- **[PHẦN 3](#phần-3--feature-category-analysis)** — 12-Category Analysis (ai lead)
- **[PHẦN 4](#phần-4--gap-analysis-cho-mmw)** — Gap Analysis cho MMW (prioritized backlog)
- **[Sources](#-sources-verified)** — Master source list

---

## PHẦN 1 — MASTER FEATURE MATRIX

**Scale:** ❌ không có | 🟡 basic/limited | ✅ good | ⭐ best-in-class

| # | App | 1.Capture | 2.Categ | 3.Reports | 4.Budget | 5.Multi-Curr | 6.Multi-Acct | 7.P+B Split | 8.Collab | 9.Notif | 10.Integr | 11.Platform | 12.Security | Score* |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 | **Money Lover** | 🟡 | 🟡 | 🟡 | ✅ | ✅ | ✅ | ❌ | 🟡 | 🟡 | ❌ | ✅ | 🟡 | 19 |
| 2 | **Spendee** | ⭐ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ⭐ | ✅ | 🟡 | ⭐ | ✅ | 30 |
| 3 | **Toshl Finance** | ✅ | ✅ | ⭐ | ⭐ | ⭐ | ✅ | 🟡 | ❌ | ✅ | 🟡 | ✅ | ✅ | 30 |
| 4 | **Wallet (BudgetBakers)** | ⭐ | ⭐ | 🟡 | ⭐ | ⭐ | ⭐ | 🟡 | 🟡 | 🟡 | 🟡 | ⭐ | ⭐ | 33 |
| 5 | **Lunch Money** | 🟡 | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | 🟡 | ❌ | 🟡 | ⭐ | ⭐ | 🟡 | 31 |
| 6 | **Money Manager (Realbyte)** | 🟡 | ⭐ | 🟡 | ⭐ | 🟡 | ⭐ | 🟡 | ❌ | 🟡 | 🟡 | 🟡 | 🟡 | 22 |
| 7 | **1Money** | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ❌ | ❌ | 🟡 | ❌ | ✅ | 🟡 | 12 |
| 8 | **HomeBudget w/ Sync** | 🟡 | 🟡 | 🟡 | ✅ | ❌ | ✅ | ❌ | ✅ | 🟡 | 🟡 | ⭐ | 🟡 | 19 |
| 9 | **Fast Budget** | 🟡 | ✅ | 🟡 | ✅ | 🟡 | 🟡 | 🟡 | ❌ | 🟡 | 🟡 | ✅ | 🟡 | 19 |
| 10 | **Buxfer** | ⭐ | ✅ | ✅ | ✅ | ✅ | ⭐ | 🟡 | ✅ | 🟡 | 🟡 | ✅ | ⭐ | 30 |
| 11 | **Wally** | ✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 | ❌ | ❌ | ✅ | 🟡 | ✅ | ⭐ | 24 |
| 12 | **Hurdlr** | ⭐ | ⭐ | ⭐ | 🟡 | ❌ | ⭐ | ⭐ | ❌ | 🟡 | ⭐ | ⭐ | 🟡 | 30 |
| 13 | **Found** | ⭐ | ⭐ | ⭐ | 🟡 | ❌ | 🟡 | ⭐ | 🟡 | 🟡 | 🟡 | ⭐ | ⭐ | 28 |
| 14 | **Goodbudget** | 🟡 | ⭐ | ⭐ | ⭐ | 🟡 | ⭐ | ❌ | ⭐ | 🟡 | 🟡 | ⭐ | 🟡 | 28 |
| 15 | **Actual Budget** | ⭐ | ⭐ | ⭐ | ⭐ | 🟡 | ⭐ | ❌ | ❌ | 🟡 | 🟡 | ⭐ | ⭐ | 31 |

*Score tính nhanh: ❌=0, 🟡=1, ✅=3, ⭐=4 (max 48). Chỉ để rank tổng quát, không phải absolute quality.

### 🏆 RANKINGS NHANH

**Top 5 tổng thể (feature breadth):** Wallet BudgetBakers (33) > Lunch Money/Actual Budget (31) > Spendee/Toshl/Buxfer/Hurdlr (30)

**Top 3 cho Solopreneur ICP (P+B + tax):** Hurdlr ⭐⭐⭐⭐⭐ → Found ⭐⭐⭐⭐ → Toshl 🟡 (mọi app khác = ❌)

**Top 3 cho Shared Finance ICP (couples/families):** Spendee ⭐ → Goodbudget ⭐ → HomeBudget ✅ → Wallet 🟡

---

## PHẦN 2 — APP FEATURE SUMMARY CARDS

> Full cards (8-12KB mỗi card) trong `cards/`. Tóm tắt 1 dòng + 3 signature features + similarity score.

### TIER 1 — DIRECT HEAD-TO-HEAD COMPETITORS

#### 1️⃣ [Money Lover](cards/money-lover.md) — *Multi-currency tracker SE Asia, Linked Wallet bank sync*
- **💰** Free / Premium $19.99 lifetime | **👥** 10M+ | **⭐** 4.6 | **🌍** Global (SEA mạnh)
- **Signature:** (1) Linked Wallet bank sync 8+ SEA countries, (2) Multi-Wallet management Premium, (3) Goal Wallets motivational
- **Gaps:** Không OCR, không split tx, không API
- **Similarity to MMW:** ⭐⭐⭐☆☆ (3/5)
- **Steal:** Goal wallets framing | **Avoid:** Thiếu OCR là pain point lớn

#### 2️⃣ [Spendee](cards/spendee.md) — *Social-first tracker với shared wallets + AI receipt scanner*
- **💰** Free / Plus $1.99 / Premium $5.99 / Lifetime $119.99 | **👥** 3M+ | **⭐** 4.6 | **🌍** Global (EU mạnh)
- **Signature:** (1) ⭐ AI Receipt Scanner (3-5s), (2) ⭐ Shared Wallets (transparent "ai chi bao nhiêu"), (3) Bank Connect 2,500+ providers
- **Gaps:** Không recurring expense setup, không net worth, không API/Zapier
- **Similarity to MMW:** ⭐⭐⭐⭐☆ (4/5) — *highest match cho shared finance ICP*
- **Steal:** Shared wallets UX + AI receipt scanner | **Avoid:** Bill/subscription tracking yếu

#### 3️⃣ [Toshl Finance](cards/toshl.md) — *200+ currencies leader + River Flow analytics*
- **💰** Free / Pro $2.99 / Medici $4.99 | **👥** 3M+ | **⭐** 4.7 | **🌍** Global
- **Signature:** (1) ⭐ River Flow visualization (cash flow as river), (2) ⭐ 200+ curr + 30 crypto + historical rates back to 1999, (3) ⭐ Flexible recurring (custom intervals: bi-weekly, "stop after 10 times")
- **Gaps:** Không OCR, không collaboration, không crypto wallet auto-track
- **Similarity to MMW:** ⭐⭐⭐☆☆ (3/5)
- **Steal:** River Flow metaphor cho Telegram + flexible recurring | **Avoid:** Single-user model

#### 4️⃣ [Wallet by BudgetBakers](cards/wallet-budgetbakers.md) — *EU bank sync leader + family sharing*
- **💰** From €4.99/mo | **👥** ~500K | **⭐** 4.5 | **🌍** EU (50+ langs), APAC, Americas
- **Signature:** (1) ⭐ SaltEdge sync 15K banks (5K EU PSD2), (2) ⭐ ML auto-cat + rule editor + sub-categories, (3) ⭐ Rollover budgets + sub-budgets
- **Gaps:** Không mobile OCR, FX rates overnight (không real-time), không net worth
- **Similarity to MMW:** ⭐⭐⭐☆☆ (3/5)
- **Steal:** SaltEdge sync (cho EU TAM), family permissions framework | **Avoid:** Overnight FX, no mobile OCR

#### 5️⃣ [Lunch Money](cards/lunch-money.md) — *Indie + open API + crypto-native*
- **💰** Free / $14.99/mo | **👥** ~100K | **⭐** 4.5+ | **🌍** Global (US-focus)
- **Signature:** (1) ⭐ Open API v2 + Zapier 8K apps, (2) ⭐ Recurring detection ML + calendar view, (3) ⭐ Net worth + crypto portfolio
- **Gaps:** Không family sharing, không investment beyond crypto, không tax export
- **Similarity to MMW:** ⭐⭐⭐⭐☆ (3.5/5)
- **Steal:** Open API early = developer moat (CPA plugins) | **Avoid:** Indie = no collaboration ceiling

#### 6️⃣ [Money Manager (Realbyte)](cards/money-manager-realbyte.md) — *Android-dominant 20M downloads, double-entry accounting*
- **💰** Free / $2.49/mo cloud sync | **👥** 20M+ downloads | **⭐** 4.64 (And), 4.81 (iOS) | **🌍** Global (Android-first, Korean dev)
- **Signature:** (1) ⭐ Double-entry accounting (rare in consumer), (2) Asset+liability tracking (loans, insurance, real estate), (3) Subcategory budgets visual
- **Gaps:** Không bank sync (manual only), không family sharing, không crypto/investment
- **Similarity to MMW:** ⭐⭐☆☆☆ (2.5/5)
- **Steal:** Manual entry can scale to 20M (proof: telegram text entry beats form) | **Avoid:** Double-entry niche

---

### TIER 2 — ADJACENT COMPETITORS

#### 7️⃣ [1Money](cards/1money.md) — *Minimal one-tap entry tracker*
- **💰** $7.99/mo | **👥** Moderate | **⭐** 4.7 | **🌍** Global
- **Signature:** (1) One-tap transaction entry, (2) Cloud sync iOS/Android, (3) Crypto + precious metals tracking (top 100 crypto)
- **Gaps:** Không bank sync, không sharing, không business
- **Similarity to MMW:** ⭐⭐⭐☆☆ (3/5)
- **Steal:** Speed-first capture UX | **Avoid:** Recent free→paid flip kills retention

#### 8️⃣ [HomeBudget with Sync](cards/homebudget-sync.md) — *Family-first multi-OS (5 platforms)*
- **💰** Free Lite (20 tx) / Pro per-OS purchase | **👥** Established | **⭐** 4.5 | **🌍** Global multi-platform
- **Signature:** (1) ✅ Family Sync OTA (WiFi/3G/4G real-time), (2) ⭐ 5 OSes parity (iOS/iPad/Android/Mac/Win), (3) Bills-due first-class workflow
- **Gaps:** Không bank sync, single-currency only, sync reliability issues reported
- **Similarity to MMW:** ⭐⭐☆☆☆ (2/5)
- **Steal:** Bills-due as separate workflow | **Avoid:** Per-OS pricing = adoption blocker

#### 9️⃣ [Fast Budget](cards/fast-budget.md) — *Android-native Italian app + debt tracking*
- **💰** Free + Premium [unverified] | **👥** ~100K Android | **⭐** 4.3 | **🌍** Global (Italian origin)
- **Signature:** (1) Debt/credit tracking first-class, (2) Calendar view forward-look (scheduled tx), (3) Subscription manager + Dropbox auto-backup
- **Gaps:** Bank sync Italian-focused only, không collaboration, web app minimal
- **Similarity to MMW:** ⭐⭐☆☆☆ (2/5)
- **Steal:** Debt as separate workflow + calendar cash flow | **Avoid:** Android-first, iOS afterthought

#### 🔟 [Buxfer](cards/buxfer.md) — *Bank aggregation powerhouse 20K banks + 110 countries*
- **💰** $9.99-$24.99/mo (PLUS/PRO/PRIME) | **👥** 150K+ | **⭐** 4.2 | **🌍** 110 countries
- **Signature:** (1) ⭐ 20K+ banks 110 countries, (2) Nested tags unlimited depth + rules, (3) Investment portfolio + retirement planner
- **Gaps:** Không AI/ML, support outage Jan 2025 (unresolved), web-first UX (mobile second-class)
- **Similarity to MMW:** ⭐⭐⭐☆☆ (3/5)
- **Steal:** Nested tags > flat categories (P&L control) | **Avoid:** Support outage = retention killer

#### 1️⃣1️⃣ [Wally](cards/wally.md) — *AI-first WallyGPT + privacy-conscious AI*
- **💰** Free / Gold $1.99/mo or $24.99/yr | **👥** "#1 Finance App 40+ times" | **⭐** 3.9 | **🌍** 70 countries, 15K banks
- **Signature:** (1) ⭐ WallyGPT chat-based advisor (LLM "brutally honest"), (2) Auto-categorization + merchant DB, (3) ⭐ Privacy-first AI (data destroyed 30 days, never trained)
- **Gaps:** Không collaboration, AI hallucination concerns, multi-curr behind paywall ($7.99)
- **Similarity to MMW:** ⭐⭐⭐⭐☆ (3.5/5)
- **Steal:** Privacy-first AI policy resonates vs ChatGPT concerns | **Avoid:** Multi-curr paywall

---

### TIER 3 — SOLOPRENEUR-LEANING

#### 1️⃣2️⃣ [Hurdlr](cards/hurdlr.md) — *Gig/freelancer GPS mileage + tax tracker*
- **💰** Free / $9.99/mo Premium / $200/yr Pro | **⭐** 4.3-4.7 | **🌍** US (iOS/Android)
- **Signature:** (1) ⭐ GPS automatic mileage (swipe Business/Personal), (2) ⭐ Real-time quarterly tax estimate + Schedule C export, (3) ⭐ Multi-platform revenue auto-sync (Stripe/Square/PayPal/Uber/Shopify/Airbnb)
- **Gaps:** Không multi-business, sync glitches reported (3.0 GMB), không household/family
- **Similarity to MMW:** ⭐⭐⭐⭐⭐ (5/5) — *closest competitor cho solopreneur ICP*
- **Steal:** Tax calendar engagement lever + multi-platform revenue sync | **Avoid:** Sync glitches

#### 1️⃣3️⃣ [Found](cards/found.md) — *Banking + bookkeeping for self-employed (US-only)*
- **💰** Free Core / $35/mo Plus / $80/mo Pro | **⭐** N/A new | **🌍** US-only
- **Signature:** (1) ⭐ Unified business bank account + auto-categorized bookkeeping, (2) ⭐ Auto tax withholding + Taxes Pocket, (3) ⭐ Schedule C auto-generation + in-app federal tax payment
- **Gaps:** US-only, business-only (no personal), no multi-business, closed integrations (no API)
- **Similarity to MMW:** ⭐⭐⭐⭐☆ (4.5/5)
- **Steal:** Taxes Pocket pattern (auto set-aside %) + invoice generation | **Avoid:** Owning bank account (out of scope cho Telegram bot)

#### 1️⃣4️⃣ [Goodbudget](cards/goodbudget.md) — *Envelope budgeting pioneer + couples sync*
- **💰** Free (10 envelopes) / $10/mo Premium | **⭐** 4.5+ | **🌍** Global iOS/Android/Web
- **Signature:** (1) ⭐ Digital envelope system (zero-based budgeting), (2) Hybrid bank sync + manual Match feature (Premium), (3) ⭐ Multi-user household sync (5 devices, real-time)
- **Gaps:** Zero business features, no income tracking, limited reports
- **Similarity to MMW:** ⭐☆☆☆☆ (1.5/5) — *misaligned ICP*
- **Steal:** Match feature (manual + auto-import dedup) | **Avoid:** Envelope methodology không fit solopreneur

#### 1️⃣5️⃣ [Actual Budget](cards/actual-budget.md) — *Open-source self-hosted privacy-first*
- **💰** 100% Free OSS + $1.50/mo SimpleFIN optional | **⭐** 4.7+ | **🌍** Global
- **Signature:** (1) ⭐ E2EE optional + local-first, (2) ⭐ 100% open source MIT + self-host (Docker/Railway), (3) ⭐ Zero-based budgeting YNAB-compatible + Sankey viz
- **Gaps:** Zero business features, no collaboration (privacy by design), bank tokens stored plaintext server-side
- **Similarity to MMW:** ⭐⭐☆☆☆ (2/5)
- **Steal:** Transparent privacy stance ("we see tx but never sell") | **Avoid:** Open-source = solopreneurs không quan tâm; "privacy" < "tax readiness"

---

## PHẦN 3 — FEATURE CATEGORY ANALYSIS

> Cho mỗi category: Best in class → Top 5 → Trends → MMW recommendation

### CATEGORY 1: TRANSACTION CAPTURE

🏆 **BEST IN CLASS:** **Found** (auto-capture at source — debit card swipe = instant ledger, zero sync delay)

📊 **TOP 5:**
1. **Found** ⭐⭐ — bank-first (own account = perfect data source)
2. **Hurdlr** ⭐ — GPS mileage + 9,500 banks + Stripe/Square/PayPal direct
3. **Buxfer** ⭐ — 20K+ banks, 110 countries
4. **Wallet BudgetBakers** ⭐ — SaltEdge 15K banks (PSD2 EU)
5. **Spendee** ⭐ — 2,500 providers + AI receipt scanner

💡 **KEY TRENDS:**
- **Bank sync = table stakes ở phương Tây**, nhưng manual entry vẫn scale 20M+ users (Money Manager) ở developing markets
- **AI Receipt OCR** chỉ Spendee + Wally làm tốt; phần lớn còn manual photo attach
- **Direct payment processor integration** (Stripe/Square/PayPal/Shopify) đang vượt generic bank sync về real-time + revenue tracking
- **Voice/SMS/Email parse** = vùng trắng (chưa app nào làm tốt)

🎯 **RECOMMENDATION CHO MMW: P0**
- Skip Plaid/SaltEdge generic bank sync ở MVP (cost + delay + complexity)
- Direct integrate Stripe + PayPal + Wise (90% solopreneur income) qua OAuth
- Telegram natural language parse ("spent $50 on Uber") = lower friction than form-filling
- Receipt OCR via Tesseract + photo upload Telegram = Phase 2

---

### CATEGORY 2: CATEGORIZATION

🏆 **BEST IN CLASS:** **Wallet BudgetBakers** (ML + sub-cats + custom rule editor) tied with **Hurdlr** (auto B/P tagging on every layer)

📊 **TOP 5:**
1. **Wallet BudgetBakers** ⭐ — ML auto + rule editor + sub-cats + bulk reclassify
2. **Hurdlr** ⭐ — auto B/P + ML rules + GPS swipe
3. **Lunch Money** ⭐ — split tx, tags, API rules
4. **Found** ⭐ — ML + tax-deductible auto-flag
5. **Money Manager** ⭐ — sub-categories + visual icons (manual only)
6. **Goodbudget** ⭐ — AI envelope suggestions

💡 **TRENDS:**
- **Auto-categorization với ML** = expected (Wally, Wallet, Hurdlr, Lunch Money)
- **Split transactions** (1 tx → multiple categories) — chỉ Lunch Money + Actual làm; rare
- **Tags hierarchical (nested)** — Buxfer unique (unlimited depth)
- **Rule editor advanced** (AND/OR/regex) — Wallet best, Lunch Money via API

🎯 **RECOMMENDATION CHO MMW: P0**
- Default 30 categories + custom unlimited
- Auto-categorize via merchant DB lookup (free, no ML cost)
- **B/P auto-tag based on income source** (Stripe = business, manual = ask) — must-have differentiator
- Split tx support cho receipts mixed B/P

---

### CATEGORY 3: REPORTS & ANALYTICS

🏆 **BEST IN CLASS:** **Toshl Finance** (River Flow signature visualization) tied with **Hurdlr** (P&L + Tax Deductions Report + Schedule C ready)

📊 **TOP 5:**
1. **Toshl** ⭐ — River Flow + 200+ curr historical + location analytics
2. **Hurdlr** ⭐ — Tax-ready P&L + mileage audit trail
3. **Found** ⭐ — Auto P&L + Income Statement + Schedule C
4. **Lunch Money** ⭐ — Calendar view + drill-down + crypto net worth
5. **Actual Budget** ⭐ — Sankey + Net worth + custom plugins (2026 roadmap)

💡 **TRENDS:**
- **Visual storytelling** (Sankey, River Flow) > raw numbers — emotional clarity
- **Tax-specific reports** (Schedule C, quarterly) chỉ Hurdlr + Found
- **AI insights** ("you spent more on X") = Wally only via WallyGPT
- **Cash flow forecast** = vùng trắng (chưa app nào làm tốt for personal)

🎯 **RECOMMENDATION CHO MMW: P0 + P1**
- P0: Monthly P&L per B/P split (income, expense, profit)
- P0: Quarterly tax estimate report (US Schedule C-ready)
- P1: River Flow-inspired Telegram message ("Your money: +$2K → -$1.2K rent → -$300 food → +$500 left")
- P2: Sankey/visual on web dashboard

---

### CATEGORY 4: BUDGETING

🏆 **BEST IN CLASS:** **Goodbudget + Actual Budget** (zero-based envelope, the methodology leaders) tied with **Toshl** (flexible custom periods bi-weekly)

📊 **TOP 5:**
1. **Goodbudget** ⭐ — envelope methodology pioneer + couple sync
2. **Actual Budget** ⭐ — YNAB-compatible + rollover + goals
3. **Toshl** ⭐ — flexible periods (bi-weekly, custom) + tag-filtered
4. **Wallet BudgetBakers** ⭐ — sub-budgets + rollover + alerts
5. **Money Manager** ⭐ — sub-category budgets visual

💡 **TRENDS:**
- **Zero-based / envelope** dominant methodology cho household
- **Rollover** = expected; **sub-budgets** = differentiator
- **Goals + savings targets** integrated với budgeting
- **Solopreneur**: budgeting LESS important than tax estimate + P&L (Hurdlr, Found chỉ 🟡)

🎯 **RECOMMENDATION CHO MMW: P1 (NOT P0)**
- Solopreneur ICP không cần envelope budgeting; cần P&L + tax visibility
- Skip envelope methodology entirely (Hurdlr/Found đã chứng minh)
- Light budgeting: monthly category limit + alert at 80% — đủ
- Don't compete với YNAB/Goodbudget on budgeting depth

---

### CATEGORY 5: MULTI-CURRENCY

🏆 **BEST IN CLASS:** **Toshl Finance** (200+ currencies + 30 crypto + historical rates back to 1999)

📊 **TOP 5:**
1. **Toshl** ⭐ — 200+ curr + crypto + historical
2. **Wallet BudgetBakers** ⭐ — 100+ curr + manual override
3. **Lunch Money** ⭐ — 100+ curr + crypto-native net worth
4. **Buxfer** ✅ — 130 curr + auto daily conversion
5. **Spendee** ✅ — multi-curr designed for nomads + Ethereum wallet

💡 **TRENDS:**
- **Crypto integration** (BTC/ETH/stablecoins) = Lunch Money, 1Money lead
- **Historical rates** (back-dated tx) = Toshl unique
- **Real-time FX** vs **overnight refresh** — Wallet BudgetBakers còn dùng overnight (frustrate users)
- **Multi-curr behind paywall** (Wally $7.99) = WTP signal

🎯 **RECOMMENDATION CHO MMW: P0**
- 50+ currencies via OpenExchangeRates/Wise API (live rates)
- Crypto support BTC/ETH/USDT từ MVP (Gen-Z nomad ICP)
- Multi-curr free, paywall behind only on advanced features (auto-rebalance, etc.)

---

### CATEGORY 6: MULTI-ACCOUNT

🏆 **BEST IN CLASS:** **Buxfer** (unlimited 110 countries) tied with **Wallet BudgetBakers** (unlimited + groups + reconcile + archive)

📊 **TOP 5:**
1. **Buxfer** ⭐ — unlimited + 110 countries + transfer detection
2. **Wallet BudgetBakers** ⭐ — unlimited + groups + reconcile
3. **Lunch Money** ⭐ — unlimited synced + manual + reconcile
4. **Money Manager** ⭐ — assets/liabilities/loans/insurance
5. **Hurdlr** ⭐ — multi-bank + Stripe/Square/PayPal centralized

💡 **TRENDS:**
- **Account types** mở rộng: cash → bank → CC → crypto → loans → insurance → real estate
- **Auto-detect transfers** giữa accounts (không count as expense) = expected
- **Account groups** (organize by type) — chỉ vài app
- **Archive** (hide nhưng giữ history) = retention pattern

🎯 **RECOMMENDATION CHO MMW: P1**
- Unlimited accounts từ MVP (Hurdlr proves)
- 6 account types: cash, bank, CC, crypto, loans, savings goal
- Auto-detect transfers (Stripe → bank = transfer, not income)
- Account groups + archive — Phase 2

---

### CATEGORY 7: PERSONAL vs BUSINESS SPLIT 🔥

🏆 **BEST IN CLASS:** **Hurdlr** (auto B/P tag mileage + income + expense + Schedule C export)

📊 **TOP 5 (very limited field):**
1. **Hurdlr** ⭐ — full auto-tag every layer, GPS swipe, Schedule C
2. **Found** ⭐ — business-only design, auto tax categorize, Taxes Pocket
3. **Toshl** 🟡 — location-tagging proxy, no formal P/B
4. **Wallet BudgetBakers** 🟡 — [unverified expense tags for biz]
5. **Money Manager** 🟡 — workaround via insurance/loan accounts

💡 **TRENDS:**
- **HUGE WHITE SPACE**: Chỉ 2/15 apps làm P+B split tốt
- **Tax export** (quarterly, Schedule C, deductions) = Hurdlr + Found only
- **Mileage tracking** (GPS) = Hurdlr signature; no consumer competitor
- **Multi-business** = vùng trắng (Hurdlr + Found đều single-biz)

🎯 **RECOMMENDATION CHO MMW: P0 — KILLER DIFFERENTIATOR**
- **B/P tag on every transaction** — manual + auto-rule
- **Income source auto-tag**: Stripe/Square/Shopify income = business; manual = personal default
- **Quarterly tax estimate** prominently surfaced (US/EU rates)
- **Schedule C export** for US filers (PDF + CSV cho accountant)
- **Multi-business** — Phase 2 differentiator vs Hurdlr (LLC + side hustle)

---

### CATEGORY 8: COLLABORATION

🏆 **BEST IN CLASS:** **Spendee** (shared wallets transparent + invite-based)

📊 **TOP 5:**
1. **Spendee** ⭐ — shared wallets killer feature
2. **Goodbudget** ⭐ — couples sync 5 devices real-time
3. **HomeBudget** ✅ — Family Sync OTA 5 OSes
4. **Buxfer** ✅ — share with family/accountants + IOU splitting
5. **Wallet BudgetBakers** 🟡 — family sharing 4 members, view-only/edit permissions

❌ **Hurdlr, Found, Lunch Money, Actual Budget, Toshl, Wally, 1Money, Fast Budget, Money Manager** = **ZERO collaboration**

💡 **TRENDS:**
- **9/15 apps có ZERO collaboration** = unmet TAM
- **Shared wallets** (Spendee model) > Family sharing (BudgetBakers model) cho users
- **Permission granularity** (view-only, edit, admin) chỉ Wallet BudgetBakers
- **Approval workflow / activity log** = vùng trắng
- **Accountant access (read-only)** = vùng trắng

🎯 **RECOMMENDATION CHO MMW: P1 (NOT P0)**
- Solopreneur MVP = single-user only (theo Hurdlr/Found pattern)
- Phase 2: Accountant access (read-only Schedule C + receipts) = differentiator
- Phase 3 (chỉ nếu pivot): Couples mode hoặc shared wallets

---

### CATEGORY 9: NOTIFICATIONS

🏆 **BEST IN CLASS:** **Wally** (real-time + WallyGPT proactive insights)

📊 **TOP 5:**
1. **Wally** ✅ — real-time sync + recurring bill reminders
2. **Spendee** ✅ — budget alerts customizable + bill reminders + real-time
3. **Toshl** ✅ — budget alerts + bill reminders Pro+
4. **Money Lover** 🟡 — bill reminders + budget alerts
5. **Buxfer** 🟡 — bill reminders + budget alerts

💡 **TRENDS:**
- **Real-time tx notification** = standard
- **Daily/weekly/monthly digest** (email) = vùng trắng
- **Unusual spending AI detection** = WallyGPT only
- **Subscription renewal reminder** = Fast Budget unique
- **Bill reminder** = trở thành expected

🎯 **RECOMMENDATION CHO MMW: P0 (TELEGRAM ADVANTAGE)**
- Telegram-native = inherent notification advantage (no push opt-in friction)
- Daily recap message: "Today: +$X earned, -$Y spent, $Z to taxes"
- Weekly P&L summary message
- Quarterly tax deadline alerts (US/EU calendar)
- Unusual spending AI: P1 (cần ML training data)

---

### CATEGORY 10: INTEGRATIONS

🏆 **BEST IN CLASS:** **Lunch Money** (open API v2 + Zapier 8K apps + GitHub awesome-lunchmoney)

📊 **TOP 5:**
1. **Lunch Money** ⭐ — API + Zapier + webhook + community plugins
2. **Hurdlr** ⭐ — Stripe/Square/PayPal/Shopify/Airbnb/Uber/9.5K banks
3. **Spendee** 🟡 — bank + e-wallet + Coinbase
4. **Buxfer** 🟡 — statement upload only [no Zapier confirmed]
5. **Wallet/Toshl/Found/etc.** 🟡 — CSV/XLS only

💡 **TRENDS:**
- **API as moat**: Lunch Money proves dev community = retention
- **9/15 apps** chỉ có CSV/XLS (no Zapier, no API) = blind spot
- **Direct payment processor sync** (Stripe/Square) = expansion of "bank sync"
- **Google Sheets 2-way** = vùng trắng (no app làm tốt)
- **Calendar sync** (bills as events) = vùng trắng

🎯 **RECOMMENDATION CHO MMW: P0 + P1**
- P0: Stripe + PayPal + Wise direct OAuth (top 3 solopreneur revenue sources)
- P1: Public API (REST + webhook) — moat cho CPA/freelancer plugins
- P1: Google Sheets 1-way export (free tier value)
- P2: Zapier integration (developer ecosystem)

---

### CATEGORY 11: PLATFORM & UX

🏆 **BEST IN CLASS:** **Spendee + Wallet BudgetBakers + HomeBudget + Hurdlr + Found + Lunch Money + Actual Budget** (all ⭐)

📊 **TOP 5:**
1. **HomeBudget** ⭐ — 5 OSes parity (iOS/iPad/Android/Mac/Win)
2. **Wallet BudgetBakers** ⭐ — iOS/Android/Web + offline + 50+ langs
3. **Spendee** ⭐ — iOS/Android/Web + Editors' Choice
4. **Lunch Money** ⭐ — Web + iOS app + offline
5. **Actual Budget** ⭐ — iOS/Android/Web PWA + self-host desktop

💡 **TRENDS:**
- **Web app** = expected (nhưng Money Manager còn không có)
- **Offline-first** = niche but loyal (Money Manager, Actual)
- **Dark mode** = standard
- **Languages 5+** = standard cho global
- **Apple Watch / Wear OS** = vùng trắng

🎯 **RECOMMENDATION CHO MMW: P0**
- Telegram bot (primary) + Web dashboard (secondary view) — đủ cho MVP
- Skip native iOS/Android apps (Telegram = both)
- 5 languages: EN, ES, PT, FR, DE (cover 80% global market)
- Dark mode trên web — Phase 2

---

### CATEGORY 12: SECURITY & PRIVACY

🏆 **BEST IN CLASS:** **Actual Budget** (E2EE optional + open source + self-host) tied with **Wally** (ISO 27001 + E2EE + GDPR + privacy AI policy)

📊 **TOP 5:**
1. **Actual Budget** ⭐⭐ — E2EE + OSS + self-host
2. **Wally** ⭐ — ISO 27001 + E2EE connection + GDPR + AI privacy
3. **Wallet BudgetBakers** ⭐ — 2FA + biometric + PSD2 + GDPR
4. **Buxfer** ⭐ — 256-bit + PCI + SOC3 + daily audits
5. **Found** ⭐ — FDIC banking-grade + Lead Bank Member FDIC

💡 **TRENDS:**
- **2FA + biometric** = expected (nhưng nhiều app không có TOTP)
- **E2EE** = differentiator nhưng caveat (Actual: bank tokens plaintext)
- **Self-host** = niche (Actual only)
- **Privacy policy clarity** ("we never sell data") matters more than encryption claims
- **Compliance certs** (SOC2, ISO 27001, PCI) = enterprise B2B angle

🎯 **RECOMMENDATION CHO MMW: P0 (table stakes)**
- 2FA TOTP + Telegram-native auth
- Biometric web app (WebAuthn passkey)
- GDPR compliant + clear privacy policy ("never sell, never train AI on your data")
- Don't claim E2EE if can't deliver fully (Actual lesson)
- Compliance: SOC2 type 1 trong Year 1 (B2B accountant TAM)

---

## PHẦN 4 — GAP ANALYSIS CHO MMW

> Backlog priority cho MMW MVP + Phase 2. Mỗi feature: ai có sẵn → khó build → impact ICP solopreneur

| # | Feature | Apps có | Difficulty | Impact ICP | Priority | Phase |
|---|---|---|:-:|:-:|:-:|:-:|
| 1 | **Personal vs Business auto-tag** (income source rule + manual) | Hurdlr ⭐, Found ⭐ | Medium (rule engine) | ⭐⭐⭐⭐⭐ Killer | **P0** | MVP |
| 2 | **Quarterly tax estimate** (US/EU rates) | Hurdlr, Found | Medium (tax tables) | ⭐⭐⭐⭐⭐ | **P0** | MVP |
| 3 | **Stripe + PayPal + Wise direct OAuth** | Hurdlr (Stripe/Sq/PayPal) | Medium-High (OAuth flows) | ⭐⭐⭐⭐⭐ | **P0** | MVP |
| 4 | **Multi-currency 50+** + crypto BTC/ETH | Toshl ⭐, Spendee, Lunch Money | Low (XE/OpenExchangeRates API) | ⭐⭐⭐⭐ | **P0** | MVP |
| 5 | **Telegram natural language parse** ("spent $50 on Uber") | None ⭐⭐⭐⭐⭐ Unique | Medium (NLP regex + LLM fallback) | ⭐⭐⭐⭐⭐ | **P0** | MVP |
| 6 | **Daily/weekly P&L recap message** | None (Wally proactive partial) | Low (cron + template) | ⭐⭐⭐⭐ | **P0** | MVP |
| 7 | **Schedule C export PDF + CSV** (US) | Hurdlr, Found | Low (template) | ⭐⭐⭐⭐⭐ US | **P0** | MVP |
| 8 | **Receipt photo + Tesseract OCR** | Spendee, Wally | Medium (Tesseract + merchant DB) | ⭐⭐⭐⭐ | **P1** | Phase 2 |
| 9 | **Recurring tx auto-detect** (Netflix, Spotify) | Lunch Money ⭐, Toshl | Medium (pattern matching ML) | ⭐⭐⭐⭐ | **P1** | Phase 2 |
| 10 | **Public API + webhook** (CPA plugins) | Lunch Money ⭐ | Medium-High (REST + auth + docs) | ⭐⭐⭐ | **P1** | Phase 2 |
| 11 | **Mileage tracking** (manual entry "logged 12 miles") | Hurdlr GPS | Low (manual entry) | ⭐⭐⭐ US | **P1** | Phase 2 |
| 12 | **Subscription detection + cancel reminders** | Fast Budget partial | Medium (recurring rules + alerts) | ⭐⭐⭐ | **P1** | Phase 2 |
| 13 | **Accountant read-only access** (Schedule C view) | None — vùng trắng | Medium (RBAC + invite) | ⭐⭐⭐⭐ | **P1** | Phase 2 |
| 14 | **Multi-business support** (LLC + side hustle) | None — vùng trắng | High (workspace model) | ⭐⭐⭐ | **P2** | Phase 3 |
| 15 | **Invoice generation** (text-to-invoice via Telegram) | Found, Hurdlr | Medium (PDF + payment link) | ⭐⭐⭐ | **P2** | Phase 3 |
| 16 | **Sankey/River Flow visualization** (web dashboard) | Toshl ⭐, Actual Budget | Medium (D3.js viz) | ⭐⭐ | **P2** | Phase 3 |
| 17 | **Couples mode / shared wallet** | Spendee ⭐, Goodbudget | High (multi-user infra) | ⭐⭐ (different ICP) | **P3 / Cut** | Maybe |
| 18 | **Investment portfolio tracking** (stocks, dividends) | Buxfer | Very high (price feeds + cost basis) | ⭐ Out of scope | **Cut** | — |
| 19 | **Envelope budgeting methodology** | Goodbudget, Actual Budget | Medium | ⭐ Wrong ICP | **Cut** | — |
| 20 | **Self-hosted / open source** | Actual Budget | Very high | ⭐ Wrong ICP | **Cut** | — |

### 🎯 PRIORITIZED ROADMAP TÓM TẮT

**MVP (P0) — 7 features**: P/B auto-tag • Quarterly tax estimate • Stripe/PayPal/Wise OAuth • 50+ multi-curr + crypto • Telegram NL parse • Daily/weekly recap • Schedule C export

**Phase 2 (P1) — 6 features**: Receipt OCR • Recurring detection • Public API • Mileage manual entry • Subscription cancel reminders • Accountant read-only access

**Phase 3 (P2) — 3 features**: Multi-business • Invoice generation • Sankey viz

**CUT/MAYBE — 4 features**: Couples mode (different ICP) • Investment tracking (out of scope) • Envelope budgeting (wrong ICP) • Self-host (wrong ICP)

### 💎 4 KILLER COMBINATIONS (chỉ MMW có)

1. **Telegram NL parse + B/P auto-tag + Quarterly tax** = "spent $50 on Uber" → Bot reply: "Logged: $50 transport (Personal). Q2 tax estimate: $1,240 (no change)"
2. **Stripe webhook + Schedule C export** = real-time business revenue capture, zero sync delay (beat Hurdlr's 3-5 day Plaid lag)
3. **Daily P&L recap in Telegram** = retention loop without push notification opt-in (Telegram = always reachable)
4. **Accountant read-only access** = B2B viral channel (CPA invites client → client signs up to grant access)

### ⚠️ KHÔNG NÊN (lessons từ research)

- **Don't compete với YNAB/Goodbudget on envelope budgeting** — wrong ICP
- **Don't claim E2EE** unless deliver fully (Actual Budget plaintext bank tokens lesson)
- **Don't add couples mode at MVP** — Hurdlr/Found chứng minh single-user solopreneur scale tốt
- **Don't pursue investment tracking** — Buxfer/Lunch Money chứng minh expansion là mess
- **Don't bloat categories** — Money Lover/Money Manager 25-100 default categories = decision fatigue

---

## ❓ UNRESOLVED QUESTIONS

1. **Hurdlr's Plaid cost** — chưa verify per-user fee Hurdlr trả Plaid ($0.10-0.30/MAU est.); MMW phải tính tương tự nếu chọn Plaid
2. **Found's accountant access** — docs imply có nhưng không explicit feature page; cần test trực tiếp
3. **Lunch Money API v2 GA date** — alpha → GA "Q1 2026" — chưa confirm released
4. **Spendee Premium accuracy** — AI receipt scanner accuracy metrics chưa public
5. **Money Lover P+B [unverified]** — có tag personal/business hay không? Cần test
6. **Wally pricing model** — free + Gold $1.99 vs trước $7.99 multi-curr in-app purchase — confusing, cần verify current
7. **Buxfer support recovery** — Jan 2025 outage có resolved chưa as of May 2026?
8. **Actual Budget plugins ecosystem** — 2026 roadmap claim "plugins ready" nhưng GitHub 0 plugins live
9. **Stripe/Square real-time API quality** — Hurdlr có specific issues với sync; MMW cần verify trước khi commit
10. **Toshl recurring custom intervals UI** — "stop after 10 times" chỉ documented in blog post; cần verify UI hiện tại

---

## 🔗 SOURCES VERIFIED (Master List)

> Total ~200+ unique URLs across 15 cards. Subset top sources per app dưới đây; full list trong từng card file.

**Money Lover:** moneylover.me • zendesk help center • Play Store • App Store
**Spendee:** spendee.com/features • help.spendee.com • bank-connect • App Store reviews
**Toshl:** toshl.com/currencies • River Flow blog • WealthNoob 2026 review • bank-connections
**Wallet BudgetBakers:** budgetbakers.com/features • support.budgetbakers.com • Choice.com.au • freenance.io
**Lunch Money:** lunchmoney.app • lunchmoney.dev (API) • GitHub awesome-lunchmoney • Indie Hackers • Product Hunt
**Money Manager Realbyte:** realbyteapps.com • help.realbyteapps.com • justuseapp • appgrooves
**1Money:** 1moneyapp.com • App Store • Banktrack alternatives 2025 • Apptopia
**HomeBudget:** anishu.com • G2 reviews • YourMoney review • TechnologyEvaluation
**Fast Budget:** fastbudget.app • Play Store • NerdWallet 2026 • Engadget
**Buxfer:** buxfer.com/features • Capterra reviews • TechRadar • G2 • TrustRadius
**Wally:** wally.me • WallyGPT TheFintechTimes • GOBankingRates • Wamda • Globe and Mail safety
**Hurdlr:** hurdlr.com • Hurdlr University integrations • Fit Small Business • College Investor • Capterra
**Found:** found.com/taxes • found.com/bookkeeping • NerdWallet • Business.org • Self-Employed.com
**Goodbudget:** goodbudget.com/how-it-works • bank-sync help • NerdWallet • CFO Club YNAB alternatives
**Actual Budget:** actualbudget.org • GitHub actualbudget/actual • Roadmap 2026 • Issue #5550 SimpleFIN security

---

## 📁 FILE STRUCTURE

```
assets/research/2026-05-08-feature-landscape-round3/
├── FINAL-REPORT.md           ← This file (master deliverable)
├── cards/                     ← 15 detailed app feature cards
│   ├── money-lover.md
│   ├── spendee.md
│   ├── toshl.md
│   ├── wallet-budgetbakers.md
│   ├── lunch-money.md
│   ├── money-manager-realbyte.md
│   ├── 1money.md
│   ├── homebudget-sync.md
│   ├── fast-budget.md
│   ├── buxfer.md
│   ├── wally.md
│   ├── hurdlr.md
│   ├── found.md
│   ├── goodbudget.md
│   └── actual-budget.md
├── MATRIX.md                  ← Tier 1B intermediate matrix
├── SCORECARD-MATRIX.md        ← Tier 2 intermediate matrix
├── QUICK-REFERENCE-MATRIX.md  ← Tier 1A quick lookup
└── RESEARCH-SUMMARY.md        ← Tier 1A executive summary
```
