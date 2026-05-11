# Research Prompt — Global Competitive Analysis cho My Money Went

> **Mục đích:** Dùng prompt này để research toàn diện các personal finance / expense tracking app trên thị trường **GLOBAL**, lấy insight cho positioning, pricing, feature roadmap và GTM cho **My Money Went**.
>
> **Scope:** Chỉ focus thị trường global (US, EU, UK, AU, SEA non-VN, LATAM). KHÔNG nghiên cứu thị trường VN, KHÔNG so sánh pricing VND, KHÔNG đưa app VN-only vào danh sách.
>
> **Cách dùng:** Copy block "PROMPT" bên dưới, paste vào Claude/ChatGPT/Perplexity (model có web search). Có thể chạy theo từng section (A → B → C → D) nếu output dài.

---

## Context tóm tắt về My Money Went (cho researcher hiểu vị thế global)

- **Sản phẩm:** Telegram bot tự động ghi nhận giao dịch ngân hàng + email parsing; user phân loại bằng inline buttons trong chat. Không có app riêng — toàn bộ UX nằm trong messaging app.
- **Tiers (global, USD only):**
  - **Free** — 45 tx/tháng, 1 bank account, 30 ngày history, 1 email source, 5 categories
  - **Pro $4/mo** — 3 bank accounts, unlimited tx & history, 3 email sources, weekly + monthly report, CSV export, 20 custom categories, 10 custom auto-categorization rules
  - **Business $9/mo** — 5 bank accounts, unlimited email sources, Personal vs Business P&L split, income source attribution (Shopify/Amazon/Etsy/Stripe...), Google Sheets 2-way sync, unlimited custom rules
- **3 personas (global-generic):**
  - *Office worker* (24-35t, salaried) — wants automatic tracking without opening another app
  - *Freelancer* (multi-client, irregular income) — needs trend reports and tax-ready exports
  - *Solo online seller* (Shopify / Etsy / Amazon FBA / TikTok Shop / Instagram / Facebook Live) — needs to separate business vs personal cashflow, see real P&L per platform
- **Differentiators giả định:**
  1. Auto-capture qua bank webhook + email — không phải nhập tay
  2. Sống trong messaging app (Telegram) — zero app-switching friction
  3. Personal vs Business split cho solo seller (gap mà Mint/YNAB/Monarch không cover tốt)
  4. Onboarding 2-15 phút, no full bank credential sharing required
- **Threat zone (global):** YNAB, Monarch Money, Copilot Money, Rocket Money, PocketGuard, Empower, EveryDollar, Spendee, Toshl, Goodbudget, Wallet by BudgetBakers, Cleo (chatbot AI finance).

---

## PROMPT (copy phần dưới đây)

```
Bạn là chuyên gia phân tích cạnh tranh cho sản phẩm fintech / personal-finance ở thị trường GLOBAL. Hãy research toàn diện các app quản lý chi tiêu cá nhân và solo-business trên thị trường quốc tế (US, EU, UK, AU, Canada, SEA non-VN, LATAM) để hỗ trợ định vị "My Money Went" — Telegram bot tự động ghi nhận giao dịch ngân hàng và email parsing, 3 tier: Free / Pro $4/mo / Business $9/mo (USD only, billed monthly hoặc annually).

QUAN TRỌNG — SCOPE RULES:
- CHỈ research thị trường global. KHÔNG đưa app Việt Nam-only vào (Money Lover Vietnam-context, MISA, KiotViet, Sapo, Pancake — bỏ qua).
- Nếu một app có vận hành global (vd Money Lover của Finsify có version global), được phép nghiên cứu mảng global của họ, nhưng không phân tích pricing/positioning ở thị trường VN.
- Tất cả pricing trả về bằng USD. Nếu app gốc dùng GBP/EUR/AUD, quy đổi USD và note rate.
- KHÔNG đề cập SePay, NHNN, VND, hộ kinh doanh, hoặc bất kỳ context VN-only nào.

Yêu cầu chất lượng:
- Ưu tiên dữ liệu mới nhất 2025-2026, verify qua website chính thức, App Store / Google Play, Reddit (r/personalfinance, r/ynab, r/MonarchMoney), Trustpilot, ProductHunt.
- Khi không chắc chắn, ghi "[chưa verify]" thay vì bịa.
- Trích nguồn (URL) cho mọi pricing claim, user count, funding number.
- Output bằng tiếng Việt, giữ tên feature/pricing nguyên tiếng Anh.

═══════════════════════════════════════════════════════
SECTION A — DANH SÁCH APP CẦN RESEARCH (GLOBAL ONLY)
═══════════════════════════════════════════════════════

A.1. Direct competitor — automated personal finance (priority cao nhất):
1. YNAB (You Need A Budget) — https://ynab.com
2. Monarch Money — https://monarchmoney.com
3. Copilot Money — https://copilot.money
4. Rocket Money (formerly Truebill) — https://rocketmoney.com
5. PocketGuard — https://pocketguard.com
6. Empower (formerly Personal Capital) — https://empower.com
7. Quicken Simplifi — https://simplifi.quicken.com
8. EveryDollar (Ramsey Solutions) — https://everydollar.com

A.2. Manual + lightweight tracker:
9. Spendee — https://spendee.com
10. Toshl Finance — https://toshl.com
11. Wallet by BudgetBakers — https://budgetbakers.com
12. Goodbudget (envelope method) — https://goodbudget.com
13. Money Manager (Realbyte)
14. 1Money / Money Manager Expense & Budget
15. Expensify (cá nhân tier, không phải corporate)

A.3. Messaging-first / chatbot finance (gần với My Money Went nhất):
16. Cleo — https://web.meetcleo.com (Facebook Messenger + iOS AI chatbot)
17. Charlie (đã shutdown — research lessons learned)
18. Plum — https://withplum.com
19. Bất kỳ Telegram/WhatsApp/Discord finance bot nào active 2025-2026 (search: "telegram bot personal finance", "whatsapp expense tracker bot", "discord finance bot")

A.4. Cho persona solo online seller (e-commerce side hustle):
20. Bench Accounting — https://bench.co (bookkeeping for solopreneurs)
21. Found — https://found.com (banking + bookkeeping cho freelancer/solopreneur)
22. Lili — https://lili.co (banking + tax cho 1099/solo)
23. Hurdlr — https://hurdlr.com (mileage + expense cho gig/solo)
24. QuickBooks Self-Employed — https://quickbooks.intuit.com/self-employed
25. Wave Apps — https://waveapps.com (free accounting cho small biz)
26. FreshBooks (lite tier)
27. Link My Books / A2X (Shopify/Amazon/Etsy P&L sync)

A.5. Adjacent / reference (cho positioning, không deep-dive):
28. Mint (đã shutdown 3/2024 — học migration playbook, nơi user di cư đến)
29. Tiller (spreadsheet-based)
30. Lunch Money — https://lunchmoney.app (developer-friendly indie)
31. Actual Budget (open source, self-host)
32. Fina Money

Researcher có thể thêm app khác phát hiện trong quá trình research nếu thấy relevant với positioning "automated capture + messaging-first + personal/business split". Note rõ lý do thêm.

═══════════════════════════════════════════════════════
SECTION B — DỮ LIỆU CẦN THU THẬP CHO MỖI APP
═══════════════════════════════════════════════════════

Với mỗi app trong Section A (ưu tiên top 15), trả về template sau:

╔═══════════════════════════════════════════╗
║ APP NAME — [tên app]                      ║
╚═══════════════════════════════════════════╝

1. METADATA
   - Công ty / nhà phát triển:
   - Năm ra mắt:
   - HQ / quốc gia gốc:
   - Markets active (US/EU/UK/AU/global):
   - Số download (App Store + Google Play, gần nhất):
   - Rating (iOS / Android, kèm số rating):
   - User base công khai (MAU/paying users nếu có):
   - Funding / revenue / acquisition history:
   - Platforms: iOS / Android / Web / Desktop / Telegram / Messenger / WhatsApp / Discord

2. PRICING (USD, chi tiết — phần quan trọng nhất)
   - Free tier? Limits gì? (transactions, accounts, categories, history days, sync frequency)
   - Paid tiers: tên, giá USD/mo, giá USD/year, % discount annual
   - Có lifetime / one-time license không? Giá?
   - Free trial: bao nhiêu ngày, có bắt nhập credit card không?
   - Family / Team plan riêng? Giá?
   - Student discount?
   - Regional pricing nếu có (US vs EU vs SEA — nhưng chỉ quy USD, không VND)
   - Payment methods chấp nhận: Stripe / IAP / PayPal / crypto?

3. CÁCH HOẠT ĐỘNG (How it works)
   - Onboarding: số bước, thời gian trung bình
   - Cách nhập transaction: Manual / OCR receipt / Plaid bank sync / Open banking (TrueLayer, Tink, Yapily) / SMS / Email parsing / API
   - Bank coverage: bao nhiêu banks, regions? Dùng aggregator nào?
   - Categorization: manual / rule-based / ML model
   - Reporting: dashboards, charts, custom reports, export (CSV/Excel/PDF)
   - Multi-currency, multi-account, sub-account, hidden accounts
   - Personal vs Business split? Tag system?
   - Family / shared workspace?
   - Notifications: real-time, daily, weekly recap?
   - AI features (GPT-powered insights, anomaly detection, subscription cancel)?
   - API / Zapier / Google Sheets sync?

4. STRENGTHS (3-5 điểm)
5. WEAKNESSES (3-5 điểm — đây là gap My Money Went có thể khai thác)
6. USER FEEDBACK NỔI BẬT — quote 2-3 review từ App Store / Reddit / ProductHunt, có URL nguồn
7. POSITIONING / TAGLINE chính thức
8. TARGET SEGMENTS (mass consumer / power user / solopreneur / SMB / family)

═══════════════════════════════════════════════════════
SECTION C — CROSS-CUTTING ANALYSIS
═══════════════════════════════════════════════════════

C.1. PRICING LANDSCAPE (USD only)
- Bảng so sánh: app | Free? | Paid 1 (USD/mo) | Paid 1 (USD/year) | Paid 2 | Lifetime | Trial days
- Median giá entry paid tier
- Median giá highest paid tier
- App có annual discount > 30%?
- App có lifetime license?
- Outliers: app rẻ nhất / đắt nhất / "freemium aggressive" / "paid-only no free"
- Anchor cho My Money Went $4 Pro vs market: percentile bao nhiêu?
- Anchor cho My Money Went $9 Business vs market: percentile bao nhiêu?

C.2. FEATURE GAP MATRIX
Bảng: rows = app, columns = feature. Đánh ✅ / ❌ / 🟡. Features:
- Bank auto-sync (Plaid / TrueLayer / Tink)
- Open banking PSD2 (EU/UK)
- SMS parsing
- Email transaction parsing
- Telegram / Messenger / WhatsApp / Discord bot
- AI chatbot interaction
- Auto-categorization rule-based
- Auto-categorization ML
- Personal vs Business P&L split
- E-commerce platform attribution (Shopify, Amazon, Etsy, Stripe, PayPal payouts)
- Google Sheets / Excel 2-way sync
- CSV / OFX / QFX export
- Recurring / subscription detection
- Bill negotiation (Rocket Money style)
- Budget alerts
- Daily / weekly recap notification
- Family / shared workspace
- Receipt OCR
- Crypto / brokerage tracking
- Web dashboard
- Native mobile app
- Offline mode
- API / webhook / Zapier
- Self-hosted option

C.3. ONBOARDING FRICTION BENCHMARK
- App nào onboarding < 5 phút?
- App nào require Plaid bank link ngay từ bước 1 (high-friction)?
- App nào có "manual-only path" để bypass bank link?
- App nào yêu cầu credit card cho free trial?
- Compare với My Money Went claim 2-15 phút, không cần share bank credentials → competitive ở đâu?

C.4. POSITIONING MAP (text mô tả 2D)
Trục X: Manual entry ←→ Fully automated capture
Trục Y: Personal-only ←→ Personal + Business unified
Đặt từng app vào quadrant. Identify white space cho My Money Went.

Bonus map (text):
Trục X: Standalone app ←→ Lives in messaging/chat
Trục Y: Mass consumer ←→ Solopreneur / side-hustler
Identify white space.

C.5. THREATS & OPPORTUNITIES
- Top 3 threats (app nào nguy hiểm nhất với My Money Went, vì sao):
- Top 3 differentiators My Money Went có thể leverage (Telegram-native, email parsing, Personal/Business split) — đánh giá moat: dễ copy hay khó copy?
- Risk scenario: nếu YNAB / Monarch tích hợp Telegram bot + email parsing, My Money Went mất gì?
- Risk scenario: nếu Cleo (đã có Messenger AI) thêm bank-sync và Personal/Business split, My Money Went có lợi thế gì còn lại?

C.6. WTP & WORKAROUND VALIDATION (qua user feedback)
- Trên r/personalfinance / r/ynab / r/MonarchMoney, user phàn nàn gì nhiều nhất? (tốc độ sync, categorization sai, miss transaction, app crash, customer support, pricing tăng)
- Trên r/Entrepreneur / r/smallbusiness / r/Etsy / r/FulfillmentByAmazon, solo seller dùng tool gì để track P&L? Pain point nào lặp lại?
- Có quote nào confirm pain "không tách được tiền business vs personal"?
- Có quote nào confirm pain "Mint shutdown — đang tìm replacement không bịa data"?

C.7. GO-TO-MARKET INSIGHTS (global)
- YNAB / Monarch / Copilot acquire user qua kênh nào (ASO, podcast sponsor, YouTube, Reddit, content marketing)?
- Niche nào hiệu quả: r/personalfinance ads, podcast sponsor, finance YouTube creator?
- Có app finance nào đã thành công với Telegram channel ở thị trường global?
- Influencer / KOL global trong personal finance space (YouTube, TikTok, Instagram, podcast) — top 5 với reach lớn nhất

C.8. PRICING RECOMMENDATIONS CHO MY MONEY WENT (USD only)
Trả lời concretely:
- $4/mo Pro vs market: percentile bao nhiêu, position là "value" / "premium" / "budget"? Có nên giữ hay điều chỉnh?
- $9/mo Business vs các tool solopreneur (Found, Lili, Hurdlr, QuickBooks SE)? Justify được giá $9 không?
- Có nên thêm annual plan với discount 20-30%?
- Có nên thử Lifetime offering (vd $99 lifetime sớm cho early adopters)?
- Free tier 45 tx/tháng — quá hẹp / quá rộng so với benchmark?
- Có nên có Family / Couples plan ở mức $6-7/mo (giữa Pro và Business)?

═══════════════════════════════════════════════════════
SECTION D — DELIVERABLES & FORMAT
═══════════════════════════════════════════════════════

Output structure:

1. EXECUTIVE SUMMARY (1 trang) — top 5 takeaway cho founder
2. APP DEEP DIVES — bảng theo Section B cho 12-15 app priority cao nhất
3. PRICING TABLE — bảng tổng hợp USD pricing tất cả app
4. FEATURE GAP MATRIX — ✅/❌/🟡
5. POSITIONING ANALYSIS — text mô tả 2 maps + white space
6. THREAT/OPPORTUNITY SUMMARY
7. PRICING RECOMMENDATIONS (USD only)
8. GTM PLAYBOOK INSIGHTS
9. APPENDIX — list nguồn (URL, ngày access)

Quy tắc:
- Mọi pricing có URL hoặc "[chưa verify]"
- Quote review có link gốc
- Không suy diễn ngoài data — ghi "hypothesis, cần validate"
- Tất cả số tiền bằng USD; nếu gốc khác currency thì ghi "(£X.XX → ~$X.XX, rate Y)"
- Nếu phát hiện app chưa có trong Section A nhưng đáng chú ý, thêm vào kèm lý do

═══════════════════════════════════════════════════════
SECTION E — FOLLOW-UP RESEARCH QUESTIONS
═══════════════════════════════════════════════════════

Sau research vòng 1, đề xuất 5-10 câu hỏi đáng research sâu hơn cho vòng 2 (vd: "Monarch Money có roadmap public không — cần check changelog/Twitter"; "Cleo có data churn rate khi user upgrade Cleo Plus không"; "Tỷ lệ Mint refugee đã chuyển sang đâu — survey nào tracking?").
```

---

## Tips khi chạy prompt này

1. **Chia nhỏ output:** chạy Section A+B trước (deep dive 12-15 app), rồi Section C (cross-cutting), cuối cùng D+E.
2. **Verify pricing bằng tay:** YNAB, Monarch, Copilot, Rocket Money, EveryDollar — check trực tiếp pricing page vì LLM hay outdated.
3. **Customize sâu hơn:** thêm câu "deep-dive đặc biệt vào messaging-first finance app (Cleo + bất kỳ Telegram/WhatsApp bot nào) — đây là moat chính của My Money Went".
4. **Vòng 2 (sau desk research):**
   - Sign up trial 3-5 app top (YNAB, Monarch, Copilot, Cleo) — đếm onboarding steps thực tế, screenshot
   - 5-7 user interview: tìm Mint refugee đang dùng Monarch/Copilot, hỏi gap còn lại
   - 5-7 interview với solo Etsy/Shopify seller: hỏi cách họ tách personal vs business hiện tại
5. **Output kỳ vọng:** 1 file markdown 15-25 trang + 1 spreadsheet pricing comparison (USD).

[Mở research prompt](computer:///Users/maingocanh/Projects/MyMoneyWent/research-prompt-competitor-analysis.md)
