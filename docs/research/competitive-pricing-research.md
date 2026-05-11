# Competitive Pricing Research — Expense Tracker Apps

> **Status:** Research brief, supports `docs/strategy/pricing-redesign.md` & `docs/brd-vi.md`.
> **Date:** 2026-05-07
> **Scope:** Pricing comparison của các expense tracker / personal finance apps đang có mặt trên thị trường VN và global benchmarks. Mục đích: validate Tiền Về Nơi Đâu pricing ($4 Pro / $9 Business) so với landscape hiện tại.

---

## 1. Tóm tắt nhanh (TL;DR)

Thị trường expense tracker chia rõ **3 cụm pricing**:

- **Cụm VN giá rẻ ($1-2/mo equiv):** Money Lover, MISA — pricing thấp, free tier rộng, không có bank sync auto. Đây là baseline mà mass-market VN biết.
- **Cụm international mid-tier ($2-5/mo):** Spendee, Wallet (BudgetBakers), Toshl — có bank sync (qua Plaid/Salt Edge), feature đầy đủ hơn VN apps. Tiền Về Nơi Đâu Pro $4 nằm trong cụm này.
- **Cụm premium global ($8-15/mo):** YNAB, Copilot, Monarch, PocketGuard, Rocket Money — định vị "serious budgeting tool" với deep features. Tiền Về Nơi Đâu Business $9 nằm low-end của cụm này.

**Insight chính:** Tiền Về Nơi Đâu Pro $4 hợp lý so với international mid-tier có bank sync, nhưng **cao hơn 5-10x VN apps**. Cần narrative định vị mạnh để justify premium so với Money Lover, đặc biệt là **auto transaction capture qua SePay** — không có VN app nào hiện làm được điều này ở giá < $5/mo.

---

## 2. Bảng so sánh chi tiết

### 2.1. Cụm VN (giá rẻ, free tier rộng)

| App | Free tier | Monthly | Annual | Lifetime | Bank sync | Ghi chú |
|-----|-----------|---------|--------|----------|-----------|---------|
| **Money Lover** | Có (limited wallets) | 25k VND (~$1) | 149k VND (~$6/yr) | 499k VND (~$20) | ❌ Manual + Linked Wallet add-on (29k/mo) | App #1 VN, ~5M downloads |
| **Money Lover Pro** | — | — | 1M VND/yr (~$40) | — | ✅ Linked Wallet inclusive | Tier mới, premium-positioned |
| **MISA Sổ Thu Chi** | Cơ bản miễn phí | 19k VND (~$0.75) | 89k VND (~$3.6/yr) | có lifetime | ❌ Manual | Made-in-VN, rất phổ biến |
| **1Money** | Có | (chưa xác định) | (chưa xác định) | Có lifetime | ❌ Manual | Top finance app trên Google Play VN |

**Quan sát:**
- Cụm VN apps **chưa có app nào auto-capture giao dịch ngân hàng VN** ở mức base price. Money Lover Pro $40/year mới có Linked Wallet.
- Free tier rất rộng → user VN quen với "tracking app = free". Pricing $4/mo của Tiền Về Nơi Đâu cảm giác "đắt" nếu không có narrative rõ.
- Annual price phổ biến 89-149k VND (~$3.6-6/year) → Tiền Về Nơi Đâu annual $36 (Pro) cao hơn **6-10x**.

### 2.2. Cụm international mid-tier (có bank sync, Tiền Về Nơi Đâu cạnh tranh trực tiếp)

| App | Monthly | Annual | Equiv $/mo | Bank sync | Free tier | Ghi chú |
|-----|---------|--------|-----------|-----------|-----------|---------|
| **Spendee Plus** | $1.99 | $14.99 | $1.25 | ❌ Plus = không sync | Cơ bản | Cheap entry tier |
| **Spendee Premium** | $2.99 | $22.99 | $1.92 | ✅ | Cơ bản | Comparable Pro |
| **Wallet (BudgetBakers)** | $4.49 | $26.99 | $2.25 | ✅ | Cơ bản | Lifetime $26.99-34.99 |
| **Toshl Pro** | $2.99 | $19.99 | $1.67 | ❌ | Có | No bank sync ở tier này |
| **Toshl Medici** | $4.99 | $39.99 | $3.33 | ✅ | Có | Premium tier có sync |
| **🎯 Tiền Về Nơi Đâu Pro** | **$4** | **$36** | **$3** | **✅ SePay (VN bank)** | 45 tx/mo | Pricing đề xuất |
| **🎯 Tiền Về Nơi Đâu Business** | **$9** | **$84** | **$7** | **✅ SePay multi + email** | — | Pricing đề xuất |

**Quan sát:**
- Tiền Về Nơi Đâu Pro $4/mo nằm **đúng sweet spot** cụm này. Annual $36 cao hơn Spendee Premium ($23) nhưng tương đương Toshl Medici ($40) và rẻ hơn Wallet lifetime ($27 one-time chỉ rẻ trong 12 tháng đầu).
- **Không có app nào trong cụm này làm bank sync VN tốt** — Spendee/Wallet dùng Salt Edge/Plaid, không support TPBank/Vietcombank/MB nhịp realtime. Đây là moat của Tiền Về Nơi Đâu.
- Business tier $9 không có direct competitor trong cụm mid — gần với Toshl Medici annual ($40) nhưng Tiền Về Nơi Đâu Business positioning khác (P&L view, multi-bank, email parsing).

### 2.3. Cụm premium global ($8-15/mo)

| App | Monthly | Annual | Equiv $/mo | Tính năng định vị |
|-----|---------|--------|-----------|------------------|
| **YNAB** | $14.99 | $109 | $9.08 | Zero-based budgeting, học thuật, có 34-day trial |
| **Copilot Money** | $13 | $95 | $7.92 | iOS-first, AI categorization, no free tier |
| **Monarch Core** | $14.99 | $99.99 | $8.33 | Couples/household sharing, AI assistant |
| **Monarch Plus** | — | $199 | $16.58 | Business owner tools, long-term planning |
| **PocketGuard Plus** | $12.99 | $74.99 | $6.25 | Anti-overspending focus, lifetime $99.99 |
| **Rocket Money** | $7-14 | (pay-what-fair) | $7-14 | Subscription tracking + bill negotiation |
| **🎯 Tiền Về Nơi Đâu Business** | **$9** | **$84** | **$7** | P&L personal vs business split, VN-focused |

**Quan sát:**
- Tiền Về Nơi Đâu Business $9 ở **low-end cụm premium global** — cùng range với PocketGuard ($6.25-12.99), Rocket Money ($7-14), thấp hơn YNAB/Monarch.
- Cụm này không có sản phẩm cho thị trường VN. YNAB/Monarch không support tài khoản VN.
- → Tiền Về Nơi Đâu Business **không cạnh tranh trực tiếp** với cụm này về địa lý, nhưng justify được pricing $9 vì "premium tier" của serious finance tool worldwide.

---

## 3. So sánh price/feature cho persona Tiền Về Nơi Đâu

### 3.1. Persona Minh (Free → Pro)

Minh cần: 1 bank, transaction history dài, weekly report. So sánh option:

| Option | Cost/year | Auto-capture VN bank | Weekly report |
|--------|-----------|---------------------|---------------|
| Money Lover free | $0 | ❌ | ❌ |
| Money Lover annual | ~$6 | ❌ (cần Linked Wallet add-on $8/yr extra) | ✅ |
| MISA Premium annual | ~$3.6 | ❌ | ✅ |
| Spendee Premium annual | $23 | ✅ (nhưng VN bank limited) | ✅ |
| **Tiền Về Nơi Đâu Pro annual** | **$36** | **✅ (SePay realtime)** | **✅** |

→ Tiền Về Nơi Đâu đắt hơn VN baseline nhưng **rẻ hơn Money Lover Pro full ($40/yr)** với feature comparable. Value prop: zero-effort tracking qua SePay.

### 3.2. Persona Hùng (Business)

Hùng cần: Personal vs business split, multi-bank, P&L view. So sánh:

| Option | Cost/year | Personal/Business split | Multi-bank | P&L |
|--------|-----------|------------------------|------------|-----|
| Money Lover Pro | $40 | ❌ (tag manually) | ✅ (Linked Wallet) | ❌ |
| YNAB | $109 | ❌ | ✅ | partial |
| Monarch Core | $100 | ✅ (categories) | ✅ | ✅ |
| **Tiền Về Nơi Đâu Business annual** | **$84** | **✅ native toggle** | **✅ 5 banks** | **✅** |

→ Tiền Về Nơi Đâu Business **rẻ hơn Monarch Core 16%** với feature ngang/tốt hơn cho VN context. Đây là pricing thắng so với premium global.

---

## 4. Implications cho Tiền Về Nơi Đâu pricing strategy

### 4.1. Pricing $4 Pro / $9 Business hợp lý nhưng cần narrative

**Strengths:**
- $4 Pro nằm sweet spot mid-tier global (Toshl/Wallet/Spendee).
- $9 Business rẻ hơn rõ ràng so với Monarch/YNAB cho persona business owner.
- Annual discount 25% (Pro $36/yr) trong khoảng standard market (most apps cho 30-50% discount annual).

**Risks:**
- **VN free-tier expectation gap:** User VN biết Money Lover/MISA free, $4/mo có thể feel cao 5-10x.
- **Awareness gap:** SePay auto-capture là moat nhưng user chưa biết khái niệm này. Cần education.
- **Annual sticker shock:** $36 = ~890k VND/năm. Money Lover lifetime chỉ 499k. Cần justify "subscription ≠ ownership" carefully.

### 4.2. Recommendations

**Narrative định vị (cao priority):**
- Tagline: *"Trả phí cho thời gian, không cho phần mềm"* — nhấn mạnh value prop là 30-50 phút/tháng tiết kiệm so với manual entry.
- So sánh trực tiếp với Money Lover Pro: "Tiền Về Nơi Đâu Pro $36/năm vs Money Lover Pro 1M VND/năm — rẻ hơn 30%, có auto-capture VN bank realtime."
- Đừng so với Money Lover free — user mặc định thấy free là baseline. Set expectation từ đầu là "premium tracker, đáng giá thời gian tiết kiệm."

**Free tier gating (đã có trong pricing-redesign.md, validate lại):**
- 45 tx/mo limit là correct — Money Lover free unlimited tx, Tiền Về Nơi Đâu chấp nhận thua ở "tx volume", thắng ở "automation". Phải truyền thông rõ đây là tradeoff.
- 30-day history limit: ngắn hơn Money Lover (90-day free), aggressive nhưng OK nếu trial 14-day Pro convert tốt.

**Pricing experiments cần chạy:**
- A/B test annual price $36 vs $29 (~20% off thay vì 25%) — thấp hơn anchor lifetime Money Lover (499k = $20) một mức vừa đủ tạo upgrade pressure.
- Test "lifetime offer" sau 6 tháng: $99 lifetime cho user đã active 3 tháng → tận dụng sticker shock của recurring annual để chốt high-LTV user (như Wallet làm: $26.99 lifetime).
- Localized VND pricing display: hiển thị "100k VND/tháng" thay vì "$4/mo" — VN user xử lý VND tốt hơn, và 100k feels more reasonable than seeing $4 đổi ra cảm giác "tiền nước ngoài".

**Risk mitigation:**
- Ra mắt với **price anchor**: hiển thị Business $9 trước, làm cho Pro $4 cảm giác là "deal tốt".
- Grandfather pricing $3/mo cho first 30 beta users — tạo social proof + case study.
- Money-back 7 ngày (đã có trong pricing-redesign.md) — giảm friction quyết định mua.

### 4.3. Long-term pricing signals cần monitor

| Signal | Action trigger |
|--------|---------------|
| Money Lover ra Linked Wallet giá thấp hơn $40/yr | Re-evaluate Pro $4 — có thể cần discount hoặc thêm feature |
| MISA hoặc TPBank ra app tracking riêng (tích hợp ngân hàng) | Threat lớn — khả năng phải pivot positioning |
| User churn lý do "đắt" > 30% | Test giảm annual xuống $29 |
| Trial → paid conversion < 5% | Kéo dài trial từ 14 → 21 ngày, hoặc tăng aggressive trigger |
| Business tier < 1% adoption sau 3 tháng | Gộp Business features vào Pro+addon (như 1Money's "lifetime subscription" model) |

---

## 5. Caveats về methodology

- Pricing search ngày 2026-05-07. Pricing apps thay đổi liên tục — đặc biệt Money Lover/MISA hay chạy sale 50% theo dịp lễ VN.
- Số liệu Money Lover có conflict: một số nguồn nêu monthly 25k, lifetime 499k; nguồn khác nói Pro $40/yr full version. Có thể là 2 SKU khác nhau (Premium vs Pro). Cần verify trực tiếp trong app.
- Không research được số liệu MAU/conversion rate của competitors — pricing alone không phản ánh market share.
- VN-specific apps khác có thể có (Timo, Cake, Money Mate) — chưa cover trong scope research này.

---

## 6. Sources

### VN apps
- [Money Lover Premium pricing - support page](https://moneylover.zendesk.com/hc/en-us/articles/35836986998809-Premium-Main-features-and-purchase-instructions)
- [Money Lover - App Store VN](https://apps.apple.com/vn/app/money-lover-quan-ly-thu-chi/id486312413?l=vi)
- [MISA Sổ Thu Chi - upgrade guide](https://sothuchi.misa.vn/huong-dan-nang-cap-len-phien-ban-so-thu-chi-misa-premium/)
- [So sánh Sổ Thu Chi MISA và Money Lover](https://premiumvns.com/so-sanh-so-thu-chi-misa-va-money-lover/)
- [1Money - Google Play](https://play.google.com/store/apps/details?id=org.pixelrush.moneyiq)

### International mid-tier
- [Spendee pricing](https://www.spendee.com/pricing)
- [Wallet by BudgetBakers - Premium info](https://support.budgetbakers.com/hc/en-us/articles/7151349344018-Everything-about-Premium)
- [Toshl Finance pricing](https://toshl.com/pricing/)

### Premium global benchmarks
- [YNAB pricing](https://www.ynab.com/pricing)
- [Copilot Money pricing](https://copilot.money/pricing/)
- [Monarch Money pricing](https://www.monarch.com/pricing)
- [PocketGuard vs Rocket Money 2026](https://pocketguard.com/blog/pocketguard-vs-rocket-money/)

---

**End of research brief.**
