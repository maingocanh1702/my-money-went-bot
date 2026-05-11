# Insights từ Global Competitive Research → Decisions cho My Money Went

> **Source:** competitive-intelligence-global-2026.md (uploaded 2026-05-07)
> **Mục đích:** rút insight actionable, không repeat data. Tập trung vào "vậy thì làm gì khác đi".

---

## TL;DR — 5 strategic moves quan trọng nhất

1. **Re-position moat:** "Personal + Business under $10/mo" mới là moat thực sự, KHÔNG phải Telegram bot. Đổi messaging: "Telegram = channel, P&L split = product".
2. **Bắt đầu build web dashboard** — bot-only product historically thất bại (Charlie shutdown, Cleo pivot khỏi Messenger). BRD đang để web dashboard out-of-scope là rủi ro chiến lược.
3. **Add annual plan ngay khi launch** — 92% market có annual plan, 20-25% discount là standard. $38/yr Pro, $86/yr Business.
4. **Tăng free tier 45 → 60 tx/month** — user cần đủ thời gian hình thành habit trước khi hit paywall.
5. **Lock niche "for people who SELL things"** — không cạnh tranh trên mass-market personal finance (Monarch/YNAB đã dominate). Chỉ chơi solopreneur/side-hustler segment.

---

## 1. INSIGHT VỀ POSITIONING

### 1.1 "Telegram-first" KHÔNG phải differentiator như mình nghĩ

**Evidence:**
- Cleo $300M ARR pivot AWAY từ Messenger → native app. Họ thành công DESPITE messaging-first, không phải BECAUSE.
- Charlie shutdown vì chat-only UI không đủ cho financial data (33% accuracy fail).
- Telegram finance bot ecosystem hiện tại: <5M users globally, <$10M revenue, retention <10% MAU. PiggyPal/TeleExpense đang tồn tại nhưng không scale.

**Implication:**
- Telegram bot là **acquisition channel + low-friction input layer**, không phải toàn bộ product.
- Users sẽ cần web dashboard để xem reports phức tạp, P&L breakdown, trends. Bot chỉ tốt cho 1-2 actions tại 1 thời điểm.
- **Hành động:** đưa **lightweight web dashboard vào MVP** (read-only OK, có thể là Next.js + Supabase auth via Telegram). BRD hiện đang để web dashboard out-of-scope — đây là risk lớn.

### 1.2 Moat thực sự: "Personal + Business P&L split dưới $10/mo"

**Evidence:**
| Đối thủ closest | Giá | Note |
|---|---:|---|
| Monarch Plus | $16.58/mo ($199/yr) | Vừa thêm Q2 2026, premium positioning |
| QuickBooks Solopreneur | $20/mo | Built for biz, không cover personal đẹp |
| Found Plus | $35/mo | Banking + bookkeeping, US only |
| **My Money Went Business** | **$9/mo** | **45-74% rẻ hơn** |

**Implication:**
- Đây là cái mình **PHẢI** lead với, không phải Telegram, không phải email parsing.
- Tagline thử: "The only app that tracks your salary AND your side hustle in one P&L — under $10/month."
- Product page phải dẫn ngay với: "Stop running 2 apps for personal vs business. One bot. One report. $9/mo."

### 1.3 White space: "Messaging + Solopreneur" = empty quadrant

Map 2 trong research: KHÔNG app nào occupy quadrant này. Cleo ở Messenger nhưng target Gen-Z consumer. Solopreneur tools (QBSE, Wave, Found) đều standalone app.

**Hành động:** Đây là chiến lược niche to win. Đừng cố đánh cả mass-consumer — sẽ thua Monarch/YNAB.

---

## 2. INSIGHT VỀ PRICING

### 2.1 $4/$9 stay — nhưng add annual + lifetime test

**Bằng chứng từ research:**
- $4 Pro = 33rd percentile (value), $9 Business = 41st percentile (middle). Không cần thay đổi.
- 92% apps có annual plan. **My Money Went đang chưa có** = leave money on table.
- Chỉ PocketGuard có lifetime ($149.99) — demand signal exists nhưng chưa proven mass.

**Recommendations cụ thể:**
| Tier | Monthly | Annual (proposed) | % discount | Note |
|---|---:|---:|---:|---|
| Pro | $4 | **$38/yr** | 21% | Reduces churn, captures budget users |
| Business | $9 | **$86/yr** | 20% | Enterprise-feel justification |
| **Lifetime test** | — | **$99 first 500 users** | — | Limited time only, monitor cannibalization |

### 2.2 Free tier 45 tx/month → tăng lên 60

**Logic:** User chi $30/tuần ≈ 8-10 tx/tuần → hit cap trong 5 tuần. Chưa đủ để form habit.
- Industry benchmark: EveryDollar (manual entry, không cap), Spendee (unlimited free), PocketGuard (3 accounts crippled), Goodbudget (10 envelopes)
- 45 → 60 tx (2 tx/ngày average) = "user qua được tháng đầu tiên" = better Free → Pro conversion

### 2.3 Family/Couples plan: chưa cần, defer Year 2

Monarch include household free trong $14.99/mo. My Money Went không nên rush vào — bundle vào Business tier nếu có demand. Re-evaluate khi >20% user base có shared use case.

---

## 3. INSIGHT VỀ PRODUCT & FEATURES

### 3.1 Email parsing là feature ĐỘC NHẤT — nhưng moat yếu hơn mình nghĩ

**Lý do:** Zero competitors làm email parsing **vì Plaid đã solve cho US/EU**. My Money Went email parsing có giá trị thực sự ở thị trường:
- Privacy-conscious users (không muốn share bank credentials qua Plaid)
- Markets có open banking yếu (SEA, LATAM, một phần Đông Âu)
- Power users dùng banks không có Plaid coverage

**Implication:**
- Đừng marketing email parsing như "feature siêu cool" — sẽ flat với target US/EU.
- **Marketing nó như "no bank credentials needed"** — privacy-first angle. Đây là gold post-Mint shutdown.
- Tagline thử: "Track expenses without giving any app your banking password."

### 3.2 Subscription detection + bill negotiation = Rocket Money's moat

Rocket Money 10M users, 4.1M paying chủ yếu vì bill negotiation (saves $180-400/yr average). Đây KHÔNG phải feature mình nên build — rất operational-heavy, commission model phức tạp.

**Thay vào đó:** subscription detection (auto-flag recurring charges) là quick win, low effort. Should be Pro tier feature.

### 3.3 Google Sheets sync = sleeper feature

KHÔNG đối thủ nào trong list có Google Sheets 2-way sync. Đây là moat nhỏ cho power user/freelancer/accountant audience. **Nên ship ở Business tier như đã plan.**

### 3.4 Critical missing: Receipt OCR

Toshl, QBSE, Wave có receipt OCR. Solopreneur cần upload receipt cho expense categorization tax purposes. **My Money Went đang không có** — gap đáng cân nhắc cho Business tier.

### 3.5 Multi-currency: power user pain point lớn

YNAB users phàn nàn liên tục về thiếu multi-currency. Toshl thắng power user nhờ 200+ currencies. Solopreneur bán trên Etsy/Shopify global → rất cần. **Cân nhắc làm priority cho Business tier sau MVP.**

---

## 4. INSIGHT VỀ GO-TO-MARKET

### 4.1 3 channels theo thứ tự ROI

| Channel | Cost | Speed | Reach | Recommendation |
|---|---|---|---|---|
| **Reddit organic** (r/personalfinance, r/Entrepreneur, r/smallbusiness, r/Etsy) | $0 | Slow | Medium | **Phase 1 must-do** — Mint refugee threads, comparison posts |
| **Mid-tier YouTube/podcast** | $5-15K/video | Medium | High | **Phase 2** — Joseph Hogue, Jeremy Lefebvre tier first |
| **Telegram channels/communities** | $0-low | Slow | Niche | **Phase 3 unique angle** — no incumbent here |

### 4.2 "Mint replacement" narrative window vẫn mở

Mint shutdown 3/2024, 3.6M users vẫn fragmented. Monarch là primary beneficiary nhưng KHÔNG dominant. **2 năm sau vẫn có market đang settle** = narrative còn live cho 6-12 tháng nữa.

Content strategy: SEO long-tail "best mint alternative 2026", "mint replacement for freelancers", "mint shutdown what to use".

### 4.3 Influencer cost reality check

Top creators (Humphrey Yang 3.4M TikTok, Brian Jung 2.1M YouTube) = $50K+/post. Quá đắt cho seed stage.

**Realistic targets:** 700K-900K subscriber tier (Joseph Hogue, Jeremy Lefebvre, Ryan Scribner) = $5-15K/video. Test 2-3 videos để có CAC data trước khi scale.

### 4.4 "No bank credentials" = sharpest positioning angle

Privacy-conscious users đang growing post-Mint (Intuit pushed users to Credit Karma without consent). Plus crypto/web3 audience overlap. KHÔNG đối thủ nào claim này vì all are Plaid-dependent.

---

## 5. RISKS — Cần monitor sát

### 5.1 Monarch Plus (HIGH probability, 6-12 month timeline)

Q2 2026 vừa add business tracking ở $199/yr. Nếu họ lower price hoặc thêm email parsing → direct collision.
- **Probability họ lower price:** 60%
- **Mitigation:** Speed to market, lock in early adopters, double down Telegram channel (họ không quan tâm)

### 5.2 Cleo pivot (LOW-MEDIUM, 12+ months)

Cleo $300M ARR có thể thêm personal/business split. Nhưng họ target Gen-Z consumer, không phải solopreneur. Different ICP = limited overlap.
- **Mitigation:** Position rõ "for people who sell things" vs Cleo "for people who spend things".

### 5.3 YNAB (LOW, 18+ months)

Brand loyalty cực mạnh nhưng philosophically committed to manual zero-based budgeting. Khó pivot sang automation. Probability họ thêm Telegram bot: ~10%.

### 5.4 Risk lớn nhất ÍT người để ý: Telegram chính sách thay đổi

- Telegram block/restrict bot ở 1 thị trường (như đã xảy ra ở Brazil 2023, Russia)
- Telegram thay đổi rate limit / pricing for Bot API
- Telegram acquired/sanctioned

**Mitigation cần plan ngay:**
- Multi-platform architecture từ early — không hardcode Telegram-only
- Backup plan: Discord bot, WhatsApp Cloud API, web app standalone

---

## 6. CRITICAL QUESTIONS CẦN VALIDATE (Vòng 2 research)

| # | Câu hỏi | Method | Priority |
|---|---|---|---|
| 1 | Solopreneur có thực sự pay $9/mo cho personal+biz split không? | Survey 50-100 solo Etsy/Shopify sellers | **P0** |
| 2 | Monarch Plus adoption rate (Core $99 → Plus $199)? | Public earnings/analyst report | **P0** |
| 3 | Privacy-conscious segment size post-Mint? | NerdWallet/CNBC survey 2026 | P1 |
| 4 | PiggyPal + TeleExpense MAU thực tế? | Direct outreach to founders or scrape Telegram channel members | P1 |
| 5 | Regulatory: Telegram bot thu subscription có cần money transmitter license ở US/EU? | Lawyer consult | **P0 trước launch** |
| 6 | YNAB community willingness to switch nếu có automation? | Reddit poll r/ynab | P2 |
| 7 | Telegram Mini App có ai làm finance không? | Telegram directory + Telegram dev community | P1 |

---

## 7. 90-day action items từ insights này

**Tuần 1-2 (decision)**
- [ ] Re-evaluate web dashboard scope cho MVP — proposal: read-only dashboard ship cùng bot
- [ ] Lock niche positioning: "for solopreneurs who sell online" — update landing page copy
- [ ] Add annual plan tier to pricing page ($38/yr, $86/yr)

**Tuần 3-6 (validation)**
- [ ] Survey 50 solo Etsy/Shopify sellers về WTP cho personal+biz split
- [ ] Lawyer consult: money transmitter license cho Telegram bot subscription model
- [ ] Mock landing page A/B test: "Telegram bot for finance" vs "Track salary + side hustle in one P&L"

**Tuần 7-12 (build + GTM prep)**
- [ ] Tăng free tier 45 → 60 tx/mo
- [ ] Add subscription detection feature cho Pro tier
- [ ] Reddit organic strategy: 5-10 helpful comparison posts in r/personalfinance, r/Entrepreneur
- [ ] Identify 5 mid-tier YouTube/podcast creators for sponsor outreach
- [ ] Build "Mint refugee migration guide" content for SEO

---

## 8. CHANGES vs BRD v2.8.0 (cần update)

| Section BRD | Hiện tại | Đề xuất update |
|---|---|---|
| 4.4 Out of scope | Web dashboard | **MOVE TO IN-SCOPE** read-only web dashboard cho MVP |
| 5.1 Pricing | Chỉ monthly | **ADD** annual plans + lifetime test |
| 4.1 Free tier | 45 tx/mo | **CHANGE** to 60 tx/mo |
| 3 Personas | Office worker / freelancer / online seller (chung chung) | **SHARPEN** primary ICP = solopreneur (Etsy/Shopify/TikTok seller) — drive 80% messaging |
| 4.2 Phase 2 | Có receipt OCR? | **ADD** receipt OCR vào Business tier roadmap |
| 4.2 Phase 2 | Multi-currency | **PROMOTE** lên Phase 2 must-have (power user demand cao) |
| 8 Marketing | Chưa có channel rõ | **ADD** GTM playbook 3-phase (Reddit → mid-tier YT → Telegram community) |
| 9 Risks | Generic | **ADD** Telegram platform risk + multi-platform architecture từ Day 1 |

---

[Mở insights doc](computer:///Users/maingocanh/Projects/MyMoneyWent/insights-from-competitive-research.md)
