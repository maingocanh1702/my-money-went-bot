# Doc 2 — User Research Findings & Primary Research Plan

**Phiên bản:** 1.0
**Ngày:** 07/05/2026
**Phạm vi:** Tổng hợp pain point của user 4 app PFM lớn (Money Lover, Spendee, YNAB, Monarch Money) trên thị trường global, kèm kế hoạch primary research để bổ sung cho team từ VN trước khi mở rộng.
**Phạm vi review:** iOS App Store (US, UK) + Google Play (US, UK).

---

## 0. Lưu ý quan trọng về phương pháp

Doc này được build dựa trên **secondary research** chứ không phải raw review mining như mục tiêu ban đầu. Lý do: sandbox technical environment không cho phép outbound đến `itunes.apple.com` và `play.google.com`, cũng không có Chrome extension live để scrape trực tiếp.

Để bù lại, mình đã sử dụng các nguồn aggregate sau:

- Reddit discussions (r/ynab, r/MonarchMoney, r/personalfinance, r/Mint, r/UKPersonalFinance) — extract qua WebSearch.
- App review aggregator sites (JustUseApp, AppGrooves, Capterra, Trustpilot, SourceForge, AppFollow public previews).
- Comparison articles từ NerdWallet, The Penny Hoarder, Rob Berger, Money With Katie, Productive With Chris, FinanceBuzz, BGR, Engadget, FangWallet, Frugal For Less, MotleyFool — các trang này thường tổng hợp negative review themes.
- Bogleheads forum threads cho YNAB và Monarch.
- Hacker News threads về Plaid và YNAB.
- Help center / status page chính thức của các app — phản ánh các issue nội tại được công nhận.
- Báo cáo bảo mật bên thứ ba (Trustwave SpiderLabs blog cho vụ Money Lover API leak).

**Tradeoff so với raw review mining:**

| Tiêu chí | Raw mining 200–500 review | Secondary aggregate (doc này) |
|---|---|---|
| Frequency exact (e.g. "37% than phiền sync") | Có | Không — chỉ qualitative |
| Sample quote nguyên văn | Có | Có nhưng paraphrased từ các trang aggregate |
| Coverage themes | Có thể miss niche pain | Tốt vì các trang aggregate đã filter pain phổ biến |
| Recency | Tươi hơn | Có lag, các trang viết tổng hợp thường vài tháng/năm |

**Khuyến nghị:** Doc này đủ tốt cho việc ra quyết định chiến lược lần đầu (positioning, feature priority). Trước khi commit ngân sách lớn, nên bổ sung primary research theo plan ở Phần 6.

---

## 1. Tóm tắt cho lãnh đạo

Top 3 pain point xuất hiện ở **cả 4 app**, đáng coi là "bệnh chung" của ngành PFM global:

Một, **bank connection unreliability** — đứng đầu mọi cluster. User phàn nàn về connection break sau 60–90 ngày, sync delay 4–18 giờ (có lúc 5–7 ngày cho credit card), và việc không phân biệt được lỗi do app, do aggregator, hay do bank. Đây là vấn đề kỹ thuật cố hữu của model dùng aggregator. App nào lý giải rõ ràng và tự refresh tự động thì giảm đáng kể churn.

Hai, **auto-categorization sai hoài** — mọi app đều có. Amazon, Target, Costco là các merchant gây bất lực nhất vì user mua nhiều thứ trong cùng một transaction. Đây là cơ hội cho team có lợi thế về AI/ML tự build categorization tốt hơn.

Ba, **subscription pricing perceived as expensive** — đặc biệt YNAB ($109/yr) và Monarch (no free tier sau Mint shutdown). User rất nhạy với giá, và việc không có free tier robust khiến nhiều user thử rồi bỏ. Cơ hội cho mid-tier pricing ($30–50/year) với feature đủ tốt.

Ngoài 3 pain trên, có 7 cluster phụ với mức độ ảnh hưởng và actionability khác nhau, chi tiết ở Phần 3.

**Cảnh báo riêng cho team từ VN:** Pain "Money Lover US connectivity tệ" được Reddit và review sites confirm — đây là chỗ sản phẩm Vietnamese-built đang bị đánh giá thấp ở US. Nếu mở rộng global, đây phải là lesson learned đầu tiên: **chọn aggregator có US coverage tốt, không thoả hiệp**.

---

## 2. Pain point summary theo app

### 2.1 Money Lover (Salt Edge backbone)

**Top complaints:**
- Sync giữa các device không reliable. Nhiều report user reinstall xong mất hết dữ liệu vì không sync.
- US bank connections thất bại liên tục — user request refund bị từ chối vì "third-party service".
- Recurring transactions không hiển thị đúng. List recurring transactions hiển thị sai start date so với cấu hình.
- Bug nhỏ phiền: type description thì app mở random screen.
- Budget feature "không usable" theo một số user — paradox vì app marketing là budget planner.
- Vụ vulnerability năm 2018: Trustwave SpiderLabs phát hiện API leak personal info (~10 năm trước nhưng vẫn xuất hiện trong search results, ảnh hưởng đến trust score). JustUseApp gắn safety score 8/100 dù app store rating 4.6/5.

**Implication cho team từ VN:** Phần lớn user đánh giá tích cực về core functionality (manual entry, multi-wallet) nhưng phần Bank Sync là điểm chí mạng. Sản phẩm strong ở Asia/EU mid-tier nhưng yếu ở US — đúng với chiến lược "1 đối tác Salt Edge".

### 2.2 Spendee (Hybrid: Tink/Salt Edge + Plaid US)

**Top complaints:**
- "Stopped syncing for 6+ weeks" — Spendee team được nhận report nhưng không fix kịp.
- New UI sau redesign "không flow well".
- "Large chunk of older transactions disappeared" — data loss complaint nghiêm trọng. Customer support 6 tháng mới response.
- Subscription model bị phản ứng từ user lifetime cũ ("không chịu fix bug, chỉ chạy promo subscription").
- Bank connection inconsistent — không phải bank nào cũng support. User được khuyên "check trước khi mua Premium".
- Mobile vs Web balance không khớp.

**Implication:** Spendee đang ở giai đoạn product có bug tích lũy + churn của lifetime user → bài học về việc chuyển từ lifetime sang subscription cần làm cẩn thận.

### 2.3 YNAB ($14.99/mo, $109/yr)

**Top complaints:**
- **Pricing là số 1.** $109/yr bị coi là đắt, nhất là với user feel "value đã giảm" sau khi gặp Direct Import fail.
- Bank connection: TD Canada và Discover có "widespread issue" được công nhận trên status page. Account không update được hàng tháng → user CAD/AU phàn nàn nhiều.
- Indian user, Australian user phải dùng third-party tool (budgetfeeder) vì YNAB không support bank các quốc gia này, nhưng vẫn charge full price → cảm giác "discriminatory pricing".
- Learning curve cao — UI "busy", philosophy "envelope/zero-based" khó hiểu cho user mới. NerdWallet và FinanceBuzz đều flag điều này.
- Brand drift: user cũ phàn nàn về thay đổi philosophy (ví dụ "đừng dùng từ budget"), corporate change "draining" cho loyal user adapt liên tục.

**Implication:** YNAB là benchmark cao nhất về ARR ($109) và NPS — nhưng pain pricing đã mở cơ hội cho Monarch và Copilot. Nếu sản phẩm mới positioned là "YNAB-philosophy nhưng $40/yr", có upside.

### 2.4 Monarch Money ($14.99/mo, $99.99/yr)

**Top complaints:**
- **Customer support là số 1.** Email response 48h+ nhưng "không resolve được issue". AI chatbot không thay được human. Vài review tố scam (charge sau khi cancel).
- Investment tracking là cluster than phiền lớn nhất trên Reddit. Không compare được foreign stock vs US, không retirement vs non-retirement. Monarch nhận biết đây là beta nhưng user expect đầy đủ.
- Connection issues: "accounts disconnect every 3-4 weeks" là quote phổ biến. Monarch dùng đa định tuyến Plaid + Finicity + MX nhưng vẫn fail — Plaid và Finicity hay claim incorrect credentials sai (MX cứu được).
- Sync delay 18h+ đối với một số bank, 5–7 ngày cho credit card.
- No print/export feature — user couples cần share PDF cho partner phải workaround.
- No free tier sau 7-day trial → Mint refugee feel forced into paying. Tâm lý "Mint free 15 năm, sao Monarch dám bắt $99.99".

**Implication:** Monarch là "Mint replacement" nhưng đang đứng giữa: chưa đạt độ ổn định của YNAB, chưa polished bằng Copilot. Cơ hội cho new entrant nếu fix được customer support và có free tier.

---

## 3. Pain point clusters tổng hợp (cross-app)

### Cluster 1: Bank connection / sync reliability (XUẤT HIỆN Ở 4/4 APP)

Đây là cluster lớn nhất. Sub-themes:

- Connection break sau 60–90 ngày (do PSD2 reauth requirement ở EU và bank security policy ở US).
- Sync delay 4 giờ (best case YNAB) tới 5–7 ngày (worst case Monarch credit card).
- User không phân biệt được lỗi do app, aggregator (Plaid/MX/Finicity), hay bank.
- Specific bank fail: TD Canada, Discover, Chase UK app-to-app, Australian banks (YNAB unsupported), Indian banks (YNAB unsupported), Scotiabank (YNAB).
- "Plaid claims wrong credentials" khi credentials đúng → frustrating user phải re-enter.
- Reinstall = mất transaction data nếu chưa sync (Money Lover).

**Feature implications cho new product:**
- Connection health dashboard transparent: "Your Chase connection last synced 3h ago, expected next sync in 1h".
- Auto-refresh khi user mở app + visible "syncing now" indicator.
- Per-bank status page (giống YNAB status page) để user biết khi bank nào down toàn cầu.
- Fallback: nếu auto-sync fail >24h, prompt user manual entry hoặc CSV import flow.
- Multi-aggregator backend (Phase 3 trong Doc 1) → khi user complain Plaid lỗi, tự thử MX.

### Cluster 2: Auto-categorization errors (XUẤT HIỆN Ở 4/4 APP)

Sub-themes:
- Amazon, Target, Costco là worst — multi-purpose retailer.
- Subscription names viết tắt (ví dụ "GOOG*GSUITE PROD*") không nhận diện đúng.
- Foreign character / merchant local không trong training data.
- Recurring transaction được categorize lại mỗi lần (không nhớ user correction).
- Manual edit hàng tuần là friction lớn.

**Feature implications:**
- "Memory rule" engine: user correct 1 lần → nhớ cho tất cả lần sau, tự động.
- Bulk recategorize action: chọn 50 transaction từ 1 merchant cùng lúc.
- AI categorization in-house (xem Doc 1 §6) cho first-pass + rule cache cho personalized.
- Split transaction: 1 Amazon order chia thành "Groceries $30 + Electronics $50".

### Cluster 3: Pricing / subscription friction

Sub-themes:
- $109/yr (YNAB) và $99.99/yr (Monarch) bị nhiều người cho là đắt.
- No free tier hoặc free tier quá hạn chế → Mint refugee không dám commit.
- Lifetime user của Spendee feeling burned khi shift sang subscription.
- Khó cancel subscription (Monarch complaints về "scam-like").
- Apple/Google 30% cut khiến app không thể giảm giá thêm.
- User trong "developing market" (Ấn Độ, Australia) phàn nàn vì phải trả full giá nhưng coverage thấp.

**Feature implications:**
- Tier free robust thực sự, không chỉ 7-day trial. Có thể: free = manual entry only, paid = bank sync.
- Pricing dưới $50/year nếu chỉ AI category + manual entry, $80–90/year nếu kèm Plaid-tier sync.
- Cancellation flow phải dễ — không tạo dark pattern.
- Locale-based pricing (PPP adjustment) cho dev market.

### Cluster 4: Customer support quality

Sub-themes:
- Monarch: 48h email, không resolve được → đứng đầu complaint.
- Spendee: 6 tháng silence với data loss case.
- Money Lover: dev không response.
- YNAB: support tốt hơn nhưng vẫn slow khi widespread issue.
- AI chatbot không thay được human.

**Feature implications:**
- Live chat trong giờ làm việc (đầu tư) cho user paid.
- Public status page rõ ràng + email notification cho user khi bank của họ bị down.
- Self-service troubleshooting flow cho 80% issue phổ biến.
- "Wait time" estimate transparent.

### Cluster 5: Geographic / bank coverage gaps

Sub-themes:
- YNAB không support India, Australia nhưng vẫn charge full giá.
- Money Lover US tệ.
- Spendee Premium bán nhưng không phải bank nào cũng support.
- Chase UK app-to-app only — không web flow.

**Feature implications:**
- Trang public liệt kê bank coverage theo từng quốc gia trước khi user pay.
- Cảnh báo trong onboarding "Your bank X is not supported, do you still want to continue?"
- Locale pricing cho thị trường có coverage hạn chế.

### Cluster 6: Learning curve / complexity

Sub-themes:
- YNAB: philosophy envelope/zero-based khó hiểu, "tốn vài tuần để comfortable".
- Monarch: setup process "very painful".
- "Busy interface" YNAB.

**Feature implications:**
- Onboarding tour có gốc theo persona ("I want simple tracking" vs "I want serious budgeting").
- Default category cleaner.
- "First connection" flow optimize: connect 1 bank trước, cho user thấy magic, mới push connect more.

### Cluster 7: Feature gaps theo product mature

Sub-themes:
- Investment tracking (Monarch beta, Copilot weak, YNAB không có).
- No print/export PDF (Monarch).
- Joint savings buckets không reflect (Monarch).
- Spendee: large chunk old transaction disappear.
- Money Lover: budget feature usability bug.

**Feature implications:**
- Investment tracking phase 2 — không phải MVP nhưng là retention feature cho user lâu năm.
- Print/PDF export đơn giản — quick win.
- Shared accounts / joint logic phải design ngay từ data model.

### Cluster 8: Privacy & security perception

Sub-themes:
- Money Lover API leak (2018) vẫn ảnh hưởng trust score.
- Plaid "lưu username/password" — Hacker News critique.
- General wariness sau breach của các app PFM khác.

**Feature implications:**
- Privacy-first marketing: "We never see your password — OAuth only".
- SOC2 Type II certification (~$50K invest, payback 1+ năm).
- Apple FinanceKit positioning ở US: "Native, no scraping, no password".
- Local-only mode cho user ultra paranoid (manual entry, không cloud sync).

### Cluster 9: Cross-platform / cross-device

Sub-themes:
- Copilot iOS/macOS only — Android user complain rất nhiều.
- Spendee mobile vs web balance khác nhau.
- Money Lover sync giữa device fail.

**Feature implications:**
- Cross-platform parity quan trọng — Android không phải optional.
- Web app cần real-time sync với mobile.

### Cluster 10: Brand / philosophy drift

Sub-themes:
- YNAB user cũ feel "corporate philosophy change draining".
- Mint refugee jaded với paid model.

**Feature implications:**
- Communicate change rõ ràng, có changelog public.
- Long-term loyal user perks (legacy pricing, early access feature mới).

---

## 4. Phân khúc user nhận diện được

Từ các thread Reddit và comparison article, mình thấy 4 segment chính:

**Segment A — "Mint refugee" (US, post-2024 shutdown)**
Quen với free, từ chối paid. Nhạy với pricing, value automatic categorization, ghét manual work. Đang được Monarch và Copilot tranh giành.

**Segment B — "Disciplined budgeter" (US/UK, YNAB stronghold)**
Sẵn sàng trả $100+/yr nếu philosophy thuyết phục. Quan tâm giáo dục tài chính, không chỉ tracking. Loyal nếu app respect philosophy.

**Segment C — "Couples / family CFO"**
Cần shared finance feature. Pain: app couples-specific (Honeydue) yếu feature, app general (Monarch, YNAB) couples logic chắp vá.

**Segment D — "International / mixed currency"**
Nhiều ngân hàng ở nhiều quốc gia. Money Lover Salt Edge đang serve nhưng còn thô. Niche nhưng underserved.

---

## 5. Implications cho team từ VN

### 5.1 Positioning candidate

Dựa trên gap thấy được:

**Option 1 — Mint successor mid-tier:** $40–50/yr, free tier robust (manual + receipt scan), bank sync paid add-on. Target Mint refugee. Cạnh tranh với Monarch nhưng ở giá thấp hơn.

**Option 2 — Privacy-first iOS native:** Tận dụng FinanceKit, không Plaid, no scraping. Pricing $30/yr. Niche nhưng có market sau các vụ data breach.

**Option 3 — Couples / shared finance specialist:** Build couples flow tốt nhất, monetize via $5/mo cho cặp. Niche nhưng concentration cao.

**Option 4 — International power user:** Multi-currency, Salt Edge + GoCardless, target expat / digital nomad. Niche cực — có thể không scale lớn nhưng ARPU cao.

Khuyến nghị: validate Option 1 và Option 2 trong primary research; Option 3, 4 là backup nếu validation fail.

### 5.2 Feature priorities cho MVP

Dựa trên pain frequency:

P0 (cần có ngày 1): manual entry tốt + categorization rule engine + budget basic + multi-currency.

P1 (3 tháng đầu): GoCardless EU bank sync + FinanceKit iOS US + status page transparent.

P2 (6 tháng): receipt scan AI + recurring detection + couples shared (cho Option 3).

P3 (12 tháng): investment tracking (cho retention) + Plaid US (khi đủ scale).

### 5.3 Anti-feature (đừng build sớm)

- Multi-aggregator fallback (Plaid + MX + Finicity) — đợi tới có 5K paying user.
- Crypto integration — nice-to-have, không phải core pain.
- Bill negotiation (kiểu Snoop) — không phải core PFM.
- AI advisor / chatbot — user không trust, có thể chậm và sai.

---

## 6. Primary Research Plan (must-do trước khi commit ngân sách)

Doc 2 này dựa trên secondary research. Trước khi spend serious dev resource, cần primary research để verify hypothesis. Plan đề xuất:

### 6.1 App store review mining (raw, do team làm)

Mục tiêu: confirm cluster pattern bằng raw data từ chính app store.

Thực hiện:
- Dùng `google-play-scraper` (Python lib) trên máy local — chạy script đơn giản:
  ```python
  from google_play_scraper import reviews, Sort
  result, _ = reviews('com.bookmark.money', country='us', sort=Sort.NEWEST, count=500)
  ```
  Lặp cho `com.cleevio.spendee`, `com.youneedabudget.evergreen.app`, `com.monarchmoney.mobile`. Cả `country='us'` và `country='gb'`.
- Cho iOS: dùng iTunes RSS feed (10 page × ~50 review = ~500 review/app). URL pattern:
  `https://itunes.apple.com/{us|gb}/rss/customerreviews/page=N/id={APP_ID}/sortBy=mostRecent/json`
  với APP_ID: 486312413 (Money Lover), 635861140 (Spendee), 1010865877 (YNAB), 1459319842 (Monarch).
- Filter rating ≤ 2 → ~150–250 negative review/app.
- Cluster bằng AI (Claude/GPT) hoặc semi-manual với spreadsheet.
- Output: bảng frequency theme, exact quote. Verify hoặc refute cluster pattern ở Phần 3.

Effort: 1 dev x 2 ngày setup script + 1 ngày phân tích.

### 6.2 Phỏng vấn user (qualitative deep-dive)

Mục tiêu: hiểu *vì sao* user hành động như họ làm, thay vì chỉ *cái gì*.

Recruitment:
- 6–8 user mỗi thị trường target. Total 12–16 buổi.
- Phân khúc: 50% Mint refugee (đang thử Monarch / Copilot / Rocket Money), 25% YNAB user, 25% manual / spreadsheet user.
- Recruitment via UserInterviews.com hoặc Respondent.io. Incentive ~$50–100/buổi 60 phút.
- Screening: dùng app PFM trong 6 tháng qua, thu nhập $40K+/yr, age 25–45 (sweet spot cho PFM).

Discussion guide rút gọn (60 phút):
1. Warm-up (5 min): tài chính cá nhân hiện tại quản lý thế nào?
2. App journey (15 min): app nào đang dùng? Tại sao chọn? Bỏ app nào trước đó? Tại sao bỏ?
3. Demo current behavior (15 min): mở app đang dùng, walk through các action thường xuyên. Quan sát friction.
4. Pain probe (15 min): 3 lần frustration gần nhất với app? Specific scenario.
5. Wishlist (5 min): magic wand, app sẽ làm gì khác?
6. Pricing (5 min): trả bao nhiêu/năm cho app PFM lý tưởng?

Effort: 2 researcher x 2 tuần (recruit + interview + synthesis). Cost: ~$1.500 incentive + $500 platform fee.

### 6.3 Survey diện rộng (quantitative)

Mục tiêu: đo size của từng pain point và willingness to pay.

Sample: 200–400 respondent qua Reddit (r/personalfinance, r/ynab, r/MonarchMoney) + paid survey panel.

Câu hỏi key:
- Rank top 3 pain với app PFM hiện tại
- Willingness to pay: 1) free, 2) $30/yr, 3) $50/yr, 4) $80/yr, 5) $100+/yr
- Privacy concern level (Likert 1–5)
- iOS/Android, country, age, income bracket
- Open question: "What feature would make you switch app?"

Effort: 1 PM x 1 tuần. Cost: $500–1.000 panel fee.

### 6.4 Competitive UX teardown (heuristic)

Mục tiêu: hiểu UX detail mà review không capture.

Thực hiện:
- Designer + PM dùng thực sự 4 app trong 2 tuần. Document mọi friction.
- Setup task scenario chuẩn (connect bank, create budget, categorize transaction, view monthly report) → time to complete cho mỗi app.
- Output: heuristic teardown deck, 30–40 slide.

Effort: 1 designer + 1 PM x 2 tuần.

### 6.5 Tổng timeline + budget Primary Research

| Activity | Tuần | Cost |
|---|---|---|
| App store review mining | 1 | $0 (in-house) |
| User interview recruitment | 1–2 | $1.500 |
| User interview execute + synthesis | 3–4 | $500 platform |
| Survey design + run | 3–4 | $1.000 |
| Competitive teardown | 5–6 | $0 (in-house) |
| Final synthesis report | 6 | $0 (in-house) |
| **Tổng** | **6 tuần** | **~$3.000** |

ROI: với ngân sách dev cho global expansion ước $200–500K, $3K research là không có lý do không làm.

---

## 7. Câu hỏi mở dành cho team

Một, target market đầu tiên là EU (qua GoCardless free) hay US (qua FinanceKit + manual)? Quyết định này thay đổi toàn bộ Phase 1 trong Doc 1.

Hai, pricing positioning: dưới YNAB (mid-tier $40–60), bằng YNAB ($100+), hay free + ads / freemium?

Ba, có muốn build couples flow như USP chính không? Nếu có, đầu tư shared logic ngay từ data model.

Bốn, có muốn maintain sản phẩm VN concurrent với product global, hay coi global là next gen và VN sẽ legacy dần? Quyết định này impact codebase architecture.

Năm, technical capacity team có sẵn cho việc duy trì 3+ aggregator integration trong 18 tháng không?

---

## 8. Nguồn tham khảo

**Reddit / Forum threads:**
- r/ynab discussions về Plaid/Direct Import
- r/MonarchMoney discussions về connection issues
- Bogleheads thread "Monarch — connectivity with banks"
- Hacker News thread về YNAB và Plaid security

**Aggregate review sites:**
- Trustpilot: ynab.com, www.monarchmoney.com, spendee.com
- Capterra: Spendee profile
- JustUseApp: Money Lover, Spendee profiles
- AppGrooves: Money Lover negative reviews
- SourceForge: Spendee, YNAB reviews
- Slashdot: Money Lover

**Comparison / review articles:**
- NerdWallet: best budget apps, Monarch review, Honeydue review
- The Penny Hoarder: YNAB review, couples budgeting apps
- Rob Berger: Monarch Money review, couples budgeting apps
- Money With Katie: Copilot Money review
- Productive With Chris: YNAB review, Monarch review
- FinanceBuzz: YNAB review
- BGR: Mint alternatives
- Engadget: best budgeting apps 2026
- The College Investor: best budgeting apps
- Frugal For Less: Spendee review
- FangWallet: Copilot vs Monarch
- TechRadar / American Banker / Dark Reading: Money Lover security flaws (2018)
- Trustwave SpiderLabs blog: Money Lover vulnerability writeup

**Help center / status pages:**
- ynabstatus.com
- help.spendee.com
- help.monarch.com
- moneylover.zendesk.com

---

## 9. Phụ lục: app ID và package name (cho team chạy review mining)

| App | iOS App ID | Google Play Package | Dev |
|---|---|---|---|
| Money Lover | 486312413 | com.bookmark.money | Finsify JSC (VN) |
| Spendee | 635861140 | com.cleevio.spendee | Spendee a.s. (CZ) |
| YNAB | 1010865877 | com.youneedabudget.evergreen.app | YNAB LLC (US) |
| Monarch Money | 1459319842 | com.monarchmoney.mobile | Monarch Money Inc (US) |
