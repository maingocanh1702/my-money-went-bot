# BRD Section 5.1 & 5.2 — Pricing Tier (revised)

> **Status:** Superseded reference. Canonical pricing/payment/email-source spec is now `docs/brd-vi.md` v2.7.1 + `docs/prd.md` v1.4.0. Keep this file only for historical reasoning behind the pricing redesign.
>
> Bản viết lại pricing structure cho FinTrack BRD v1.0. Lý do redesign: pricing hiện tại có 80% giá trị nằm ở Free, gating yếu (cap 8 categories không bao giờ chạm), undercharge cho business use case (multi-account + email parsing đặt vào tier $3).
>
> **Cập nhật:** 2026-05-07

---

## 5.1. Pricing Tiers (revised)

### 5.1.1. Cấu trúc 3 tier + free trial

Đổi từ **2-tier (Free / Pro $3)** sang **3-tier (Free / Pro / Business)** + **14-day Pro trial cho new users**.

**Geo-based pricing (2 domain, 1 codebase):**

| Market | Domain | Pro | Business |
|---|---|---|---|
| 🇻🇳 **Việt Nam** | `tienvenoidau.com` | **79k VND/mo** (~$3.16) | **199k VND/mo** (~$7.96) |
| 🌍 **Global** | `mymoneywent.com` | **$4/mo** | **$9/mo** |

> VN pricing dưới ngưỡng tâm lý (79k < 100k, 199k < 200k). Global pricing competitive với Money Lover Linked Wallet.

| Feature | Free | Pro | Business |
|---------|------|----------------------|---------------------------|
| SePay config (auto transaction capture) | ✅ | ✅ | ✅ |
| /status, /today | ✅ | ✅ | ✅ |
| Daily recap tự động | ✅ | ✅ | ✅ |
| Bank accounts (SePay) | 1 | 3 | 5 |
| Transactions/tháng | **45** | Unlimited | Unlimited |
| Transaction history | 30 ngày | Unlimited | Unlimited |
| Categories | 5 default + 3 custom (=8) | Up to 20 custom | Unlimited |
| Auto-categorization rules | System defaults only | System defaults + **10 custom rules** | System defaults + **unlimited custom rules** |
| Weekly + Monthly report | ❌ | ✅ | ✅ |
| CSV export | ❌ | ✅ | ✅ |
| Email transaction parsing | ❌ | 1 email source | Unlimited |
| Personal vs Business split | ❌ | ❌ | ✅ |
| P&L view (income vs expense by tag) | ❌ | ❌ | ✅ |
| Google Sheets sync | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |

### 5.1.2. Annual plan discount

| Tier | Monthly | Annual (paid upfront) | Discount |
|------|---------|----------------------|----------|
| Pro | 79k/mo | 758k/năm (63.2k/mo equiv) | 20% |
| Business | 199k/mo | 1.91tr/năm (159.2k/mo equiv) | 20% |

Annual plan giúp giảm churn, cải thiện cashflow, và là psychological anchor: "758k cả năm" cảm giác rẻ hơn "79k mỗi tháng × 12".

### 5.1.3. Free trial cho new users

- New user mặc định nhận **14 ngày Pro trial** ngay sau onboarding.
- Không cần thẻ tín dụng. Không auto-charge.
- Day 12: bot gửi 1 message "Trial còn 2 ngày. Upgrade để giữ tính năng X bạn đang dùng nhiều".
- Day 14: downgrade về Free. Data preserved, nhưng UI hit limit (vd: history chỉ thấy 30 ngày, weekly report bị khóa).
- One-tap upgrade qua bot inline button.

Lý do: tracking app cần 2-3 tuần để form habit. Nếu user trial Pro 14 ngày rồi mất features, **loss aversion** mạnh hơn nhiều so với upsell từ Free.

---

## 5.2. Chiến lược Monetization (revised)

### 5.2.1. Persona-to-tier mapping

| Persona | Likely tier | Lý do | Willingness-to-pay estimate |
|---------|-------------|-------|----------------------------|
| Minh (nhân viên văn phòng, 1 bank) | Free → Pro | Dùng nhiều, cần history dài + weekly report sau 1-2 tháng | 50-100k/mo |
| Linh (freelancer, thu nhập biến động) | Pro | Cần monthly report để hiểu trend, có thể có 2 nguồn thu | 79-150k/mo |
| Hùng (chủ shop, personal + business) | Business | Tách chi cá nhân vs shop là pain chính, có 2-3 tài khoản | 150-300k/mo |

→ Pricing 79k/199k đặt **dưới ngưỡng tâm lý** của mỗi persona (79k < 100k, 199k < 200k), maximize impulse-buy.

### 5.2.2. Conversion target & revenue projection

Free tier giới hạn **45 tx/tháng** là gating aggressive — nghiên cứu hành vi chi tiêu user VN đô thị cho thấy median ~30-80 tx/tháng (ăn uống ~20-30, transport ~10-15, online shop ~5-10, bills ~5-10). 45 tx đặt **dưới median** → ~50-60% active user sẽ chạm limit trong tháng đầu. Conversion rate kỳ vọng cao hơn 10% baseline ban đầu.

Giả định ở 100 users (sau 6 tháng launch), conservative 5% paid (4% Pro + 1% Business):

| Tier | % users | Số users | Revenue/mo |
|------|---------|----------|-----------|
| Free | 95% | 95 | $0 |
| Pro (79k) | 4% | 4 | 316k VND ($12.64) |
| Business (199k) | 1% | 1 | 199k VND ($7.96) |
| **Total** | 100% | 100 | **515k VND ($20.60/mo)** |

So với pricing cũ (Free / Pro $3, 10% conversion): $30/mo. Với pricing mới và 5% paid, revenue thấp hơn nhưng conversion-friendly hơn cho VN market.

### 5.2.3. Conversion target ở 500 users (tháng 9-12):

| Tier | % users | Số users | Revenue/mo |
|------|---------|----------|-----------|
| Free | 95% | 475 | $0 |
| Pro (79k) | 4% | 20 | 1,580k VND ($63.20) |
| Business (199k) | 1% | 5 | 995k VND ($39.80) |
| **Total** | 100% | 500 | **2,575k VND ($103.00/mo)** |

→ MRR target **$100-300** tùy paid conversion thực tế. Nếu paid conversion đạt 8-10% (realistic với 45 tx gating), MRR có thể lên $165-206.

### 5.2.4. Upgrade trigger logic

| Trigger event | Message | Target tier |
|---------------|---------|-------------|
| Day 12 of trial | "Trial còn 2 ngày, giữ Pro để xem report tuần?" | Pro |
| User chạm 30 ngày history limit | "Muốn xem lại giao dịch cũ hơn 30 ngày?" | Pro |
| User dùng 35/45 tx (Free) | "Bạn đã dùng 35/45 giao dịch tháng này. Upgrade để unlimited" | Pro |
| User chạm 45 tx/tháng limit | "Đã hết quota tháng này. Giao dịch mới sẽ không được track. Upgrade?" | Pro |
| User add bank account thứ 2 (Free) | "Free tier hỗ trợ 1 tài khoản. Pro cho 3, Business cho 5" | Pro hoặc Business |
| User dùng emoji 🏪 hoặc tag "shop"/"business" | "Có vẻ bạn quản lý cả tiền cá nhân và shop. Business tier có tách riêng" | Business |
| Cuối tháng (Free user) | "Xem báo cáo tháng đầy đủ với Pro" | Pro |

**Quy tắc**: tối đa 1 upgrade message/tuần/user. Tránh spam.

### 5.2.5. Payment

- **Primary**: PayOS (chuyển khoản VN, 1.5-2% fee, settle vào tài khoản VN). Tốt cho 90% paying users là VN.
- **Secondary**: Stripe (card quốc tế, 3.4% + 30c fee). Cho user nước ngoài hoặc preference card.
- **Refund policy**: 7 ngày money-back, no questions asked. Tăng trust, giảm friction upgrade quyết định.

---

## 5.3. So sánh pricing với competitor VN

| Sản phẩm | Free tier | Paid tier | So với Tiền Về Nơi Đâu |
|---------|-----------|-----------|----------------|
| Money Lover | Cơ bản | Premium 99k/năm (~$4/year) | Tiền Về Nơi Đâu Pro 758k/năm — cao hơn, **justify bằng auto capture + zero-effort** |
| Spendee | 30 ngày trial | Plus 470k/năm ($19/year) | Tiền Về Nơi Đâu Pro tương đương Plus về price point |
| MISA Money Keeper | Free hoàn toàn | — | Tiền Về Nơi Đâu có advantage zero-effort |
| Sổ Thu Chi MISA | Free | Premium 50k/năm | Tiền Về Nơi Đâu price cao hơn, value cao hơn |

**Insight**: Tiền Về Nơi Đâu price ở mức "premium" so với competitor VN nhưng 79k dưới ngưỡng 100k tâm lý. Cần **narrative định vị**: "Bạn trả thêm vì không phải nhập tay" — value prop = thời gian tiết kiệm. Với 100 tx/tháng × 30 giây/tx nhập tay = 50 phút/tháng. 79k/mo = 1,580đ/phút thời gian tiết kiệm. Mạnh hơn nhiều so với 99k/năm Money Lover (cần tự nhập).

---

## 5.4. Risks & A/B test plan

### 5.4.1. Risks của pricing mới

| Risk | Mitigation |
|------|-----------|
| User không trial vì sợ "auto charge" | Bắt buộc no-credit-card trial. State rõ trong onboarding |
| Pro $4 quá cao cho user VN | A/B test $3 vs $4 vs $5 với 50 user mỗi nhóm |
| Business tier không có người mua (TAM nhỏ) | OK ban đầu — lock learning. Nếu sau 3 tháng <1% chọn, cân nhắc gộp vào Pro với add-on |
| Trial users không convert | Track funnel chi tiết: trial day 1/7/14 retention, downgrade reason |

### 5.4.2. A/B test cần chạy trong beta

| Test | Hypothesis | Success metric |
|------|-----------|---------------|
| Pro pricing 59k vs 79k vs 99k | 79k sweet spot (dưới 100k tâm lý) | Net revenue per 100 users |
| Trial 14 ngày vs 7 ngày vs 30 ngày | 14 ngày tối ưu | Trial → paid conversion |
| Show Business tier vs hide ban đầu | Show làm tăng anchor effect cho Pro | Pro conversion rate |
| Annual discount 20% vs 25% vs 30% | 20% sweet spot | % chọn annual |

---

## 5.5. Migration plan từ pricing cũ

Nếu BRD v1 đã được communicate ra ngoài (forum, beta signup):

1. **Beta users (đã có):** Grandfather 49k lifetime cho 30 user đầu — tạo loyalty + word-of-mouth.
2. **Public launch:** Pricing mới 79k/199k áp dụng cho user mới.
3. **Communication:** Frame là "chúng tôi mở rộng tier để serve người dùng business tốt hơn", không phải "tăng giá".

---

**End of revised section.**
