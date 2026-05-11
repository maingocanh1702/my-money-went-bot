# Research Prompt — Feature Deep-dive cho Direct Competitors của My Money Went

> **Mục đích:** Research SÂU về FEATURES của Money Lover, Spendee và các app cạnh tranh trực tiếp ở global market. Khác với market research trước (focus pricing + positioning), prompt này focus 100% vào **HỌ LÀM ĐƯỢC GÌ** ở mức feature granular.
>
> **Output dùng cho:** Lập feature roadmap MVP + Phase 2 cho My Money Went, identify feature gaps phải fill, copy ý tưởng tốt từ competitors, tránh build feature thừa.
>
> **Scope:** Global market only, USD pricing, không VN context.

---

## CONTEXT VỀ MY MONEY WENT (cho researcher đối chiếu)

| Aspect | Detail |
|---|---|
| **Product** | Telegram bot + web dashboard read-only, capture transactions automatically |
| **Capture methods** | Plaid (US/CA) + TrueLayer (EU/UK) + Stripe/PayPal/Shopify/Etsy API + email parsing payout emails + manual log via bot |
| **Primary ICP** | E-commerce solopreneur — Shopify/Etsy/Amazon FBA/TikTok Shop sellers |
| **Core feature MVP** | Personal vs Business P&L split, multi-platform income aggregation, low-friction chat input |
| **Tiers (USD)** | Free (60 tx/mo) / Pro $6/mo / Solopreneur $12/mo |
| **What we DON'T have yet** | Receipt OCR, multi-currency, subscription detection, bill negotiation, native app, family sharing, investment tracking, goal setting |

---

## DEFINITION OF "DIRECT COMPETITOR"

App phải match **≥3 trong 5 attributes** sau để gọi là direct competitor:
1. **Auto-capture** transaction (any method: Plaid, email, SMS, OCR, browser ext)
2. **Multi-currency** support hoặc multi-account aggregation
3. **Pricing** entry tier ≤ $10/mo
4. **Reports** beyond basic (P&L, custom reports, trend analysis)
5. **Categorization** rule-based hoặc ML auto

---

## PROMPT (copy phần dưới)

```
Bạn là chuyên gia phân tích product fintech. Hãy research SÂU về FEATURES của các app quản lý chi tiêu cá nhân ở global market — đây là vòng research 3 nối tiếp 2 vòng trước (vòng 1 = pricing/positioning broad, vòng 2 = visual cards).

VÒNG NÀY focus 100% vào FEATURE LANDSCAPE — họ làm được gì, làm như thế nào, UI ra sao, edge case xử lý ra sao.

QUAN TRỌNG — RULES:
- Global market only, USD pricing only, KHÔNG VN context
- Verify features qua website official, App Store screenshots, YouTube product demo, Reddit threads
- Mỗi feature claim phải có evidence: URL hoặc screenshot reference; nếu không, ghi "[unverified — cần test trực tiếp]"
- Output BẰNG TIẾNG VIỆT, giữ tên feature/setting nguyên tiếng Anh
- Ưu tiên data 2025-2026

═══════════════════════════════════════════════════════
SECTION A — APPS CẦN RESEARCH (15 apps)
═══════════════════════════════════════════════════════

TIER 1: Direct head-to-head competitors (priority cao nhất, deep-dive 100%)
1. Money Lover (Finsify) — https://moneylover.me — global, 10M+ downloads
2. Spendee — https://spendee.com — multi-currency, shared wallets
3. Toshl Finance — https://toshl.com — 200+ currencies leader
4. Wallet by BudgetBakers — https://budgetbakers.com — EU bank sync
5. Lunch Money — https://lunchmoney.app — indie developer, transparent
6. Money Manager (Realbyte) — Korean dev, Android dominant globally

TIER 2: Adjacent competitors (deep-dive selective features)
7. 1Money — https://1money.app — minimal expense tracker
8. HomeBudget with Sync — multi-device family budget
9. Fast Budget — Android-popular
10. Buxfer — https://buxfer.com — US, multi-account
11. Wally — UAE-based but global, AI features

TIER 3: Solopreneur-leaning (deep-dive Personal+Business features only)
12. Hurdlr — https://hurdlr.com — gig/solo focus, Plaid+Stripe/Square/PayPal
13. Found — https://found.com — banking + bookkeeping (US only, lessons relevant)
14. Goodbudget — https://goodbudget.com — envelope methodology
15. Actual Budget (open source) — https://actualbudget.com — privacy-first

═══════════════════════════════════════════════════════
SECTION B — FEATURE CATEGORIES CẦN RESEARCH (12 categories)
═══════════════════════════════════════════════════════

Cho mỗi app, research SÂU theo 12 categories sau. Đánh giá theo scale: ❌ (không có) / 🟡 (basic/limited) / ✅ (good) / ⭐ (best-in-class).

────────────────────────────────────
CATEGORY 1: TRANSACTION CAPTURE
────────────────────────────────────
- Manual entry UX: số bước, có quick-add widget không?
- Bank sync: provider (Plaid/Tink/TrueLayer/Salt Edge/Yodlee), số banks, regions
- SMS parsing: có không, OS support (Android only?), banks support
- Email parsing: có không, manual forward hay OAuth Gmail
- Receipt OCR: có không, accuracy, có auto-extract amount/merchant/date?
- Browser extension: có không
- Apple Wallet / Google Pay integration: có không
- Recurring transaction: tự detect hay phải set manual
- Voice input: có không (Siri/Google Assistant)
- Photo of receipt + AI extract: có không
- Import CSV/OFX/QFX: có không, format supported

────────────────────────────────────
CATEGORY 2: CATEGORIZATION
────────────────────────────────────
- Default categories: bao nhiêu, customizable?
- Custom categories: có không, có sub-categories không, độ sâu mấy level
- Category icons/colors: có customize không
- Auto-categorization: rule-based / ML / hybrid
- Rule editor: UI ra sao, support condition phức tạp không (AND/OR/regex)
- Bulk re-categorize: có không
- Split transaction: 1 tx chia nhiều categories có không
- Tag system: có không, multi-tag per tx
- Merchant database: app có database merchant để auto-recognize không

────────────────────────────────────
CATEGORY 3: REPORTS & ANALYTICS
────────────────────────────────────
- Default reports: list ra (spending by category, income vs expense, trends, etc.)
- Custom reports: user tự build report được không
- Date range filtering: presets (week/month/quarter/year/custom)?
- Comparison: month-over-month, year-over-year có không
- Charts: pie/bar/line/Sankey/heatmap, mức độ interactive
- Drill-down: click chart → see transactions
- Export reports: PDF, image, CSV, link share
- Cash flow forecasting: có không
- Net worth tracking: có không
- Spending insights AI: GPT-powered recommendations

────────────────────────────────────
CATEGORY 4: BUDGETING
────────────────────────────────────
- Budget methodology supported: zero-based / envelope / 50-30-20 / custom
- Budget periods: weekly / monthly / quarterly / yearly / rolling
- Budget alerts: when reach %, daily, weekly
- Budget rollover: unspent budget carry over có không
- Sub-budget: budget cho category con có không
- Goal setting: savings goals, debt payoff, có không
- Goal progress visualization: charts/widgets
- Multi-budget: 1 user nhiều budgets riêng biệt

────────────────────────────────────
CATEGORY 5: MULTI-CURRENCY
────────────────────────────────────
- Số currencies support
- Auto exchange rate update: source (XE, ECB, etc.), frequency
- Manual override exchange rate: có không
- Display: native currency hay convert all to base
- Multi-currency report: income $ + expense € → unified report?
- Crypto support: BTC/ETH counted as currency không

────────────────────────────────────
CATEGORY 6: MULTI-ACCOUNT
────────────────────────────────────
- Số accounts max per tier
- Account types: cash, bank, credit card, loan, investment, crypto
- Account groups/folders: có không
- Inter-account transfers: auto-detect transfer (không count as expense)
- Account reconciliation: import statement, match transactions
- Hidden/archived accounts: có không

────────────────────────────────────
CATEGORY 7: PERSONAL vs BUSINESS
────────────────────────────────────
- Có support tag personal/business không
- Auto-tag based on account: account A = business, B = personal
- P&L view: income vs expense per tag, profit margin
- Tax-deductible flag: có flag tx tax-deductible không
- Mileage tracking: có không (Hurdlr leader)
- Quarterly tax estimate: có không (QBSE leader)
- Export tax-ready report: có không
- Multi-business: user có nhiều business riêng được không

────────────────────────────────────
CATEGORY 8: COLLABORATION
────────────────────────────────────
- Family/couple sharing: có không
- Shared wallet/budget: real-time sync
- Permission levels: read-only, edit, admin
- Invite via email/link
- Multi-user transaction approval workflow
- Comments on transactions
- Activity log

────────────────────────────────────
CATEGORY 9: NOTIFICATIONS
────────────────────────────────────
- Real-time tx notification
- Daily recap: summary cuối ngày
- Weekly/monthly summary email
- Budget alert: % threshold customize được
- Bill reminder: upcoming bills
- Unusual spending detection: AI flag
- Subscription renewal reminder
- Push notification customization granularity

────────────────────────────────────
CATEGORY 10: INTEGRATIONS
────────────────────────────────────
- Google Sheets sync: 1-way / 2-way
- Excel export
- CSV/OFX/QFX export
- Zapier integration: # zaps available
- Public API: documented, rate limits
- Webhook outgoing: có không
- Apple Health / Google Fit: có không (some apps integrate)
- Calendar sync: bills as calendar events
- Email-to-add: forward receipt → auto-add tx

────────────────────────────────────
CATEGORY 11: PLATFORM & UX
────────────────────────────────────
- Platforms: iOS, Android, Web, Desktop (Mac/Win), Apple Watch, Wear OS
- Offline mode: full / partial / none
- Sync speed across devices
- Dark mode
- Languages supported
- Accessibility: VoiceOver, dynamic type
- Onboarding: số bước, thời gian, có guided tour không
- In-app help: chat support, FAQ, video tutorials

────────────────────────────────────
CATEGORY 12: SECURITY & PRIVACY
────────────────────────────────────
- 2FA support: SMS / TOTP / passkey
- Biometric lock: Face ID, Touch ID, fingerprint
- End-to-end encryption: claim có không
- Data ownership: user có thể export hết data và delete account không
- GDPR/CCPA compliance: claim
- Self-hosted option: có không (Actual Budget leader)
- Open source: yes/no
- Bank credential storage: app store hay aggregator manage
- Privacy policy: bán data cho ai không

═══════════════════════════════════════════════════════
SECTION C — OUTPUT FORMAT (BẮT BUỘC)
═══════════════════════════════════════════════════════

Output structure 4 phần CỐ ĐỊNH:

PHẦN 1: MASTER FEATURE MATRIX (1 bảng — tất cả 15 app × 12 categories)
PHẦN 2: APP FEATURE CARDS (15 cards, mỗi app 1 card)
PHẦN 3: FEATURE CATEGORY ANALYSIS (theo category, ai lead)
PHẦN 4: GAP ANALYSIS CHO MMW (feature MMW thiếu, mức độ priority)

─────────────────────────────────────────────
TEMPLATE PHẦN 1 — MASTER FEATURE MATRIX
─────────────────────────────────────────────

| App | Capture | Categ. | Reports | Budget | Multi-curr | Multi-acct | P+B Split | Collab | Notif | Integr. | Platform | Security |
|-----|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Money Lover | ✅ | ✅ | ✅ | ✅ | ⭐ | ⭐ | ❌ | ❌ | ✅ | 🟡 | ✅ | ✅ |
| Spendee | ✅ | 🟡 | 🟡 | ✅ | ✅ | ✅ | ❌ | ⭐ | ✅ | 🟡 | ✅ | ✅ |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

Scale: ❌ không có | 🟡 basic | ✅ good | ⭐ best-in-class

─────────────────────────────────────────────
TEMPLATE PHẦN 2 — APP FEATURE CARD (mỗi app)
─────────────────────────────────────────────

╔══════════════════════════════════════════════════════════╗
║  📱 APP NAME — One-line product positioning              ║
╠══════════════════════════════════════════════════════════╣
║  💰 From $X.XX/mo | 👥 X.XM users | ⭐ 4.X | 🌍 Markets │
╚══════════════════════════════════════════════════════════╝

🎯 SIGNATURE FEATURES (3 features họ làm tốt nhất, không ai bằng)
1. Feature name
   → How it works: short description
   → Why it matters: user benefit
   → Evidence: [URL screenshot/review]

2. Feature name
   → ...

3. Feature name
   → ...

📊 FEATURE-BY-CATEGORY SCORECARD

| # | Category | Score | Note (1 line) |
|---|----------|:-----:|---|
| 1 | Transaction Capture | ⭐ | Plaid + manual + receipt OCR + import CSV |
| 2 | Categorization | ✅ | 100+ default cat, ML auto, rule editor advanced |
| 3 | Reports & Analytics | ✅ | Custom reports + drill-down + Sankey |
| 4 | Budgeting | ✅ | Envelope + rollover + alerts |
| 5 | Multi-currency | ⭐ | 200+ currencies, real-time XE rates |
| 6 | Multi-account | ✅ | Unlimited, with grouping |
| 7 | Personal vs Business | ❌ | No tag, no P&L |
| 8 | Collaboration | 🟡 | Shared wallet only, no permissions |
| 9 | Notifications | ✅ | Real-time + daily recap + budget alert |
| 10 | Integrations | 🟡 | CSV only, no API, no Zapier |
| 11 | Platform & UX | ✅ | iOS/And/Web/Watch, dark mode, 20 langs |
| 12 | Security & Privacy | ✅ | 2FA TOTP, biometric, GDPR compliant |

🎁 UNIQUE / SIGNATURE INTERACTIONS (max 3 — UX họ design tốt)
• Quick-add widget on home screen: "tap-and-go" 2-tap entry
• Receipt scanner with merchant auto-recognize from database 50K+
• ...

🔴 FEATURE GAPS (max 3 — họ thiếu, MMW có thể exploit)
• No Personal vs Business split
• No e-commerce platform integration (Stripe/Shopify)
• Web dashboard read-only, can't edit

💬 USER VOICE VỀ FEATURES (1-2 quote, có link)
> "Feature X is the reason I switched from Mint" — r/personalfinance [URL]
> "Wish they had Y" — App Store review [URL]

🔗 SIMILARITY TO MMW: ⭐⭐⭐☆☆ (X/5)
Match attributes: [list]

💡 LESSONS FOR MMW (1-2 lines — học gì)
• Steal: their quick-add widget UX = best-in-class
• Avoid: their bloated category list = decision fatigue

─────────────────────────────────────────────
TEMPLATE PHẦN 3 — FEATURE CATEGORY ANALYSIS
─────────────────────────────────────────────

For each of 12 categories, trả lời:

CATEGORY: [Tên category, vd Transaction Capture]

🏆 BEST IN CLASS: [App name]
Why: [1-2 lines]

📊 RANKING TOP 5:
1. App A — what makes them lead
2. App B — close second
3. App C — solid
4. App D — average
5. App E — basic

💡 KEY INNOVATION TRENDS:
• Trend 1: AI receipt auto-categorization (Cleo, Wally lead)
• Trend 2: Open banking PSD2 OAuth (TrueLayer, Tink rising)
• Trend 3: ...

🎯 RECOMMENDATION CHO MMW:
Priority: P0 must-have / P1 should-have / P2 nice-to-have
Rationale: ...

─────────────────────────────────────────────
TEMPLATE PHẦN 4 — GAP ANALYSIS CHO MMW
─────────────────────────────────────────────

Bảng feature MMW thiếu so với competitors:

| # | Feature | Apps that have it | Difficulty to build | Impact for MMW ICP | Priority |
|---|---------|-------------------|:-------------------:|:------------------:|:--------:|
| 1 | Receipt OCR | Toshl, Wally, QBSE | Medium (use 3rd party) | High (solopreneur tax) | **P0** |
| 2 | Multi-currency 50+ | Toshl, Spendee, Money Lover | Low (XE API) | High (global ICP) | **P0** |
| 3 | Subscription detection | Rocket, Cleo, Monarch | Medium (rule-based ML) | Medium | P1 |
| 4 | Family sharing | Monarch, Spendee | High (multi-user infra) | Low (solopreneur niche) | P2 |
| 5 | Investment tracking | Monarch, Copilot, Empower | Very high | Low (out of scope) | P2/Cut |
| ... | ... | ... | ... | ... | ... |

═══════════════════════════════════════════════════════
SECTION D — DELIVERY CHECKLIST
═══════════════════════════════════════════════════════

Output cuối phải có:
[ ] Master feature matrix (Phần 1) — 15 apps × 12 categories trên 1 bảng
[ ] App feature cards (Phần 2) — 15 cards, format y nguyên template
[ ] Feature category analysis (Phần 3) — 12 categories breakdown
[ ] Gap analysis cho MMW (Phần 4) — prioritized backlog
[ ] Source list cuối file — URLs đã verify

KHÔNG cần:
- Pricing deep-dive (đã có vòng 1)
- Positioning maps (đã có vòng 1)
- GTM playbook (đã có vòng 1)
- Persona analysis (đã có)

CHỈ cần FEATURE DATA + visual format dễ scan.
```

---

## TIPS CHẠY PROMPT

| Tip | Detail |
|---|---|
| **Verify features bằng cách signup trial** | Money Lover, Spendee, Lunch Money đều có free tier. Tạo account và screenshot feature thực tế. |
| **YouTube product demo = gold** | Mỗi app phổ biến đều có review YouTube. Search "[app name] full review 2025-2026". Verify features qua video. |
| **App Store screenshots = quick scan** | Screenshots trên App Store/Play Store thường highlight signature features. Quick scan để confirm. |
| **Reddit "wish list" = gap signal** | Search "r/[app subreddit] wish list" hoặc "[app] missing features" — users tự liệt kê gap. |
| **Changelog = roadmap signal** | Money Lover, Lunch Money có public changelog. Đọc 6-12 tháng gần nhất để biết họ đang build gì. |

---

## EXPECTED OUTPUT SIZE

| Section | Size |
|---|---|
| Phần 1 Master matrix | 1 trang (1 bảng lớn) |
| Phần 2 App cards | ~15 trang (1 trang/app) |
| Phần 3 Category analysis | ~6 trang (12 categories × ~0.5 trang) |
| Phần 4 Gap analysis | 1-2 trang (1 bảng prioritized) |
| **Total** | **~25-30 trang markdown** |

---

## FOLLOW-UP RESEARCH (Vòng 4 nếu cần)

Sau vòng feature deep-dive, có thể cần vòng 4 focus vào:

1. **UX teardown** — screenshot/video walkthrough top 3 onboarding flows + transaction-add flows
2. **AI capability comparison** — Cleo, Wally, Monarch AI features hands-on test
3. **Integration ecosystem map** — bao nhiêu Zapier zaps, public API users, third-party tools
4. **Mobile-first features** — widgets, Apple Watch complications, share sheet integrations

---

[Mở prompt feature research](computer:///Users/maingocanh/Projects/MyMoneyWent/research-prompt-features-deep-dive.md)
