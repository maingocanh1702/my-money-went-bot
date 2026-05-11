# FinTrack — Business Requirements Document (BRD)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-05
> **Trạng thái:** Draft

---

## 1. Tổng quan dự án

### 1.1. Tên sản phẩm
**FinTrack** — Telegram Bot tự động theo dõi tài chính cá nhân qua SePay.

### 1.2. Tầm nhìn (Vision)
Biến việc quản lý tài chính cá nhân từ "mở app ngân hàng → ghi chép thủ công → quên sau 1 tuần" thành **hoàn toàn tự động, zero-effort**: giao dịch xảy ra → bot hỏi phân loại → bấm 1 nút → xong.

### 1.3. Bối cảnh & Vấn đề
| # | Vấn đề | Chi tiết |
|---|--------|---------|
| 1 | **Ghi chép thủ công** | 73% người Việt không theo dõi chi tiêu vì quá tốn thời gian (nguồn: khảo sát cá nhân + forums tài chính VN) |
| 2 | **App phức tạp** | Các app tài chính (Money Lover, MISA) yêu cầu nhập liệu thủ công mỗi giao dịch |
| 3 | **Mất thói quen** | Dù có app, 80%+ users bỏ sau 2 tuần vì quên nhập |
| 4 | **Không có tự động hóa** | Ngân hàng VN không có open banking API chuẩn — SePay là bridge duy nhất phổ biến |

### 1.4. Giải pháp đề xuất
Bot Telegram kết nối SePay → **tự động nhận mọi giao dịch ngân hàng** → hỏi user phân loại qua nút bấm → tổng hợp báo cáo tự động. User chỉ cần 2 bước setup: mở bot + dán webhook URL vào SePay.

### 1.5. Từ personal tool → SaaS
Bot hiện tại đã hoạt động ổn định cho 1 user (tác giả) từ tháng 4/2026. Pivot sang SaaS để:
- Phục vụ nhiều users mà không cần mỗi người tự deploy
- Loại bỏ 8 bước setup thủ công → còn 2 bước
- Tạo nguồn thu recurring revenue

---

## 2. Mục tiêu kinh doanh

### 2.1. Mục tiêu ngắn hạn (3 tháng)
| # | Mục tiêu | Metric | Target |
|---|----------|--------|--------|
| 1 | Launch MVP | Bot hoạt động multi-user | Tháng 6/2026 |
| 2 | Beta users | Số users active | 10-30 users |
| 3 | Retention | Users còn dùng sau 30 ngày | ≥60% |
| 4 | Feature parity | Tất cả features từ personal bot hoạt động | 100% |

### 2.2. Mục tiêu trung hạn (6-12 tháng)
| # | Mục tiêu | Metric | Target |
|---|----------|--------|--------|
| 1 | Paid users | Chuyển đổi Free → Pro | ≥10% |
| 2 | Scale | Tổng users | 100-500 |
| 3 | Platform #2 | Messenger integration | Live |
| 4 | MRR | Monthly Recurring Revenue | $100-300 |

### 2.3. KPIs theo dõi
| KPI | Cách đo | Tần suất |
|-----|---------|----------|
| DAU (Daily Active Users) | Users có ≥1 interaction/ngày | Daily |
| Transactions/user/tháng | Avg tx count per user per month | Monthly |
| Categorization rate | % tx được phân loại / tổng tx | Weekly |
| Churn rate | Users không dùng bot ≥14 ngày | Monthly |
| Conversion rate | Free → Pro upgrades | Monthly |

---

## 3. Đối tượng người dùng (User Personas)

### 3.1. Persona chính: "Minh — Nhân viên văn phòng"
| Thuộc tính | Chi tiết |
|-----------|---------|
| **Tuổi** | 24-35 |
| **Thu nhập** | 10-25 triệu/tháng |
| **Hành vi** | Dùng Telegram hàng ngày, có tài khoản ngân hàng VN (TCB, Vietcombank, MB...) |
| **Pain point** | "Cuối tháng không hiểu tiền đi đâu hết" |
| **Nhu cầu** | Track chi tiêu tự động, không cần mở app riêng |
| **Tech level** | Biết dùng SePay hoặc có thể hướng dẫn trong 5 phút |

### 3.2. Persona phụ: "Linh — Freelancer"
| Thuộc tính | Chi tiết |
|-----------|---------|
| **Tuổi** | 22-30 |
| **Thu nhập** | Không cố định, 8-40 triệu/tháng |
| **Hành vi** | Nhiều nguồn thu, chi tiêu không đều |
| **Pain point** | "Thu nhập bất ổn, không biết tháng nào đủ tiêu tháng nào thiếu" |
| **Nhu cầu** | Track cả thu và chi, xem trend theo tháng |

### 3.3. Persona Business tier: "Hùng+" — Online seller / chủ shop nhỏ

#### 3.3.1. Demographics & Context

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Tên đại diện** | Hùng |
| **Tuổi** | 28-42 (median 33) |
| **Giới tính** | 60% nữ, 40% nam (online seller VN nghiêng nữ) |
| **Địa lý** | Hà Nội, TP.HCM, Đà Nẵng (tier 1) + Hải Phòng, Cần Thơ, Vinh (tier 2) |
| **Nghề chính** | Online seller (Shopee/TikTok Shop/Lazada/Facebook Live), shop offline nhỏ, hoặc kết hợp |
| **Sản phẩm điển hình** | Quần áo, mỹ phẩm, đồ ăn nhà làm, phụ kiện, hàng nhập Quảng Châu, mẹ và bé |
| **Doanh thu shop (gross)** | 30-200 triệu/tháng, median 80 triệu |
| **Lãi ròng (sau chi phí)** | 5-30 triệu/tháng — nhưng họ thường **không biết chính xác** |
| **Quy mô team** | 1 mình (60%), 1-2 nhân viên đóng gói (35%), 3-5 nhân viên (5%) |
| **Banking setup** | 2-3 tài khoản: 1 cá nhân (Vietcombank/TCB), 1-2 nhận thanh toán shop (MB/ACB) |
| **Đang dùng SePay** | Đã có sẵn, dùng để auto-confirm đơn hàng (8-18 tháng) |
| **Tech level** | Trung bình — biết dùng Shopee Seller Center, Telegram, Zalo, Excel cơ bản |

#### 3.3.2. Job-to-be-done (JTBD)

**JTBD chính:**
> "Khi tôi check tài chính cuối tháng, tôi muốn biết shop có thực sự lãi sau khi đã rút tiền dùng cá nhân — để quyết định tháng sau có nên scale ads, nhập thêm hàng, hay nên chậm lại."

**JTBD phụ (theo thứ tự frequency):**
1. "Khi đến kỳ nộp thuế quý, tôi muốn data sạch để gửi kế toán dịch vụ, không phải ngồi 4 tiếng tổng hợp Excel."
2. "Khi ngân hàng yêu cầu chứng minh thu nhập để duyệt thẻ tín dụng / loan nhập hàng, tôi muốn có cashflow report 6 tháng nhanh chóng."
3. "Khi tôi muốn biết platform nào (Shopee/TikTok/Facebook) đóng góp lãi nhiều nhất, để dồn ads budget đúng chỗ."
4. "Khi tôi và chồng/vợ thảo luận tài chính gia đình, tôi muốn show được rõ ràng tiền shop vs tiền chung."

#### 3.3.3. Day-in-the-life

| Thời gian | Hoạt động | Pain liên quan tài chính |
|-----------|-----------|------------------------|
| 7:00-8:00 | Check đơn Shopee, TikTok Shop, Facebook | Tiền vào liên tục, không track kịp |
| 8:30-10:00 | Đi nhập hàng / nhận hàng từ supplier, thanh toán | Trả supplier qua chuyển khoản — đây là chi phí lớn nhất nhưng không tag rõ |
| 10:00-15:00 | Livestream, chat khách, đóng gói, ship | Không có thời gian xem báo cáo |
| 15:00-17:00 | Gửi đơn cho shipper, chạy Ads | Trả tiền ads (Facebook/Shopee) — chi phí phân tán nhiều account |
| 19:00-21:00 | Ăn cơm, scroll Telegram | Đây là window FinTrack reach Hùng |
| 21:30-22:30 | Check tổng kết ngày trên Excel (5-10 phút), trả lời khách | Thường skip vì mệt |
| **Cuối tháng** | **Dành 4-6 tiếng cộng Excel ra báo cáo** | **Pain spike — đây là moment quyết định mua tool** |

#### 3.3.4. Pain points (verbatim quotes)

> "Tháng nào cũng đập đầu vào tường vì không biết shop lãi thật bao nhiêu sau khi trừ tiền tiêu cá nhân."

> "Mất 4 tiếng cuối tháng cộng Excel mà vẫn sai số. Sai 2-3 triệu là chuyện bình thường."

> "Tiền shop và tiền nhà lẫn lộn, đến lúc cần khoản gấp không biết có đủ không. Có lần tưởng còn 50tr, hóa ra chỉ 12tr."

> "Kế toán dịch vụ tính 500k-1tr/tháng nhưng họ làm theo invoice mình gửi, không real-time. Mình muốn biết hôm nay lãi bao nhiêu thì phải tự cộng."

> "Đã thử Money Lover, MISA Money Keeper. Nhập tay không nổi với 60-80 đơn/ngày. Bỏ sau 1 tuần."

> "Dùng KiotViet thì quá nặng cho mình, mình chỉ bán online không cần POS, không cần quản kho phức tạp."

> "Ads Facebook trả 1 đầu, ads Shopee trả 1 đầu, ads TikTok trả 1 đầu. Không biết platform nào lãi nhất để dồn budget."

#### 3.3.5. Current workarounds & WTP anchor

| Workaround | % users dùng | Cost/tháng | Pain với cách này |
|-----------|-------------|-----------|-------------------|
| Excel/Google Sheets thủ công | 65% | 0đ + 4-6h cuối tháng | Tốn thời gian, sai số, không real-time |
| Kế toán dịch vụ (freelance) | 20% | 300k-1tr | Không real-time, gửi invoice qua lại mệt |
| Sổ tay giấy + tinh thần | 10% | 0đ | Mất sổ là mất hết |
| KiotViet / Sapo POS | 3% | 150-300k | Quá nặng, nhiều feature không dùng |
| MISA mShopkeeper | 2% | 100-200k | Ecosystem MISA quá enterprise |

**WTP anchor cho FinTrack Business $9 (220k VND):**
- So với kế toán dịch vụ 500k/tháng → FinTrack rẻ hơn 56%, **plus real-time** → strong sell.
- So với KiotViet 200k/tháng → FinTrack tương đương price, less features (no inventory) nhưng **simpler + Telegram-native** → trade-off OK cho seller không cần POS.
- So với Excel free → FinTrack đắt hơn nhưng tiết kiệm 4-6h/tháng. 4h × 100k/h (giá trị thời gian Hùng) = **400k value** so với 220k cost → ROI 1.8x.

→ **220k VND ($9/mo) là sweet spot**: dưới 250k psychological threshold, trên 100k để đủ "serious" (không bị coi là toy).

#### 3.3.6. Decision criteria khi Hùng+ chọn tool

1. **"Có tự động không?"** — Phải auto-capture giao dịch. Nếu nhập tay là dead.
2. **"Có tách shop vs cá nhân không?"** — Critical, đây là pain #1.
3. **"Có thấy lãi/lỗ shop ngay không?"** — Real-time P&L view.
4. **"Có gửi cho kế toán được không?"** — Google Sheets sync hoặc CSV export.
5. **"Có chạy trên Telegram/Zalo không?"** — Họ sống trong messaging app.
6. **"Setup có phức tạp không?"** — Phải <30 phút, lý tưởng <5 phút.
7. **"Giá có hợp lý không?"** — Giới hạn psychological 250k/tháng.

→ FinTrack Business hit được **6/7 tiêu chí** (chỉ thiếu Zalo, để Phase 2).

#### 3.3.7. Buying triggers

| Trigger | Frequency | Pre-trigger emotion | Conversion likelihood |
|---------|-----------|--------------------|-----------------------|
| Vừa cộng Excel xong và sai số | Hàng tháng | Frustrated, mệt | **Cao** |
| Đến deadline nộp thuế quý | 4 lần/năm | Stressed | Cao |
| Muốn apply loan ngân hàng | 1-2 lần/năm | Anxious, urgent | **Rất cao** |
| Bạn bè seller khác recommend | Random | Curious | Trung bình |
| Cãi nhau với chồng/vợ về tài chính | Random | Stressed | Trung bình |

→ **GTM implication:** Marketing nên target "moment vừa cộng Excel xong".

#### 3.3.8. Anti-persona (KHÔNG phải Hùng+)

| KHÔNG phải Hùng+ | Lý do | Đi đâu |
|-----------------|-------|--------|
| Người chỉ track chi tiêu cá nhân | Không có shop | → Pro tier hoặc Free |
| Shop lớn (>500tr/tháng doanh thu) | Cần ERP/POS thật | → KiotViet, MISA AMIS |
| Người đầu tư stock/crypto | Wrong product category | → Snowball, finhay |
| DN >5 nhân viên cần phân quyền | Cần workspace/team | → Phase 3+ |
| Người cần inventory management | FinTrack không track tồn kho | → Sapo, KiotViet |

#### 3.3.9. Variants of Hùng+ (sub-personas)

**A. "Hùng-seller"** (60% Business users dự kiến)
- Online seller thuần (Shopee + TikTok Shop), 30-150tr/tháng, 2-3 bank accounts

**B. "Linh-freelancer"** (25% Business users dự kiến)
- Freelancer chuyên nghiệp, multiple clients, cần data clean cho khai thuế quý

**C. "Tuấn-mixed"** (15% Business users dự kiến)
- Shop offline + online, hoặc day job + side hustle, 50-200tr/tháng

#### 3.3.10. Implications cho product roadmap

| Feature | Mức độ critical | Lý do |
|---------|----------------|-------|
| **Tag-based P&L** | Must-have | Phân biệt Shopee ads vs TikTok ads |
| **Income source attribution** | Must-have | Nhận diện "tiền này từ Shopee" |
| **Personal vs Business toggle** | Must-have | Pain #1 của Hùng+ |
| **Google Sheets 2-way sync** | Should-have | Để kế toán dịch vụ truy cập |
| **Multi-bank (3-5 accounts)** | Must-have | Hùng+ có 2-3 bank accounts tối thiểu |

#### 3.3.11. Validation plan trước khi commit Business tier

1. **5-7 customer interview** với online seller VN (100k thẻ điện thoại incentive)
2. **Landing page test:** mock-up Business tier → đo signup rate
3. **Beta concierge:** 5 early adopter, làm P&L thủ công qua Telegram
4. **Go/no-go threshold:** ≥3/5 nói "tôi sẽ trả $9/mo" → green light

---

## 4. Phạm vi sản phẩm

### 4.1. Trong phạm vi (In-scope) — MVP
| # | Feature | Mô tả |
|---|---------|-------|
| 1 | **Zero-config onboarding** | /start → nhận webhook URL → dán vào SePay → done |
| 2 | **Auto transaction capture** | SePay webhook → bot nhận tự động, cả thu và chi |
| 3 | **Category management** | Tạo/sửa/xóa categories qua /manage |
| 4 | **Transaction categorization** | Inline buttons để phân loại nhanh |
| 5 | **Tracking mode** | Theo dõi chi tiêu theo category, không bắt buộc budget |
| 6 | **Budget mode (optional)** | Đặt ngân sách cho category, cảnh báo khi sắp hết |
| 7 | **Reports** | /status, /today — báo cáo tháng và ngày |
| 8 | **Daily recap** | Tự động gửi tổng kết cuối ngày (23h) |
| 9 | **Multi-user isolation** | Mỗi user data riêng biệt, không cross-contamination |

### 4.2. Phase 2 (sau MVP)
| # | Feature | Mô tả |
|---|---------|-------|
| 1 | Weekly + Monthly reports | Báo cáo tuần và tháng chi tiết |
| 2 | CSV export | Xuất data ra spreadsheet |
| 3 | Email transaction parsing | Parse email ngân hàng (TCB, Cake) |
| 4 | Multiple bank accounts | 1 user kết nối nhiều tài khoản SePay |
| 5 | Messenger integration | Platform thứ 2 sau Telegram |

### 4.3. Ngoài phạm vi (Out of scope)
| # | Feature | Lý do |
|---|---------|-------|
| 1 | Web dashboard | UI chính là messaging platform, không build web app |
| 2 | AI auto-categorize | Cần data thực từ users trước, defer |
| 3 | Investment tracking | Khác product category, không phải spending tracker |
| 4 | Multi-currency | VND only cho MVP, thị trường VN |
| 5 | Shared/family accounts | Complexity cao, defer sau growth phase |

---

## 5. Mô hình kinh doanh

### 5.1. Pricing Tiers (3-tier + free trial)

Đổi từ 2-tier (Free / Pro $3) sang **3-tier (Free / Pro $4 / Business $9)** + **14-day Pro trial cho new users**.

| Feature | Free | Pro ($4/mo, 100k VND) | Business ($9/mo, 220k VND) |
|---------|------|----------------------|---------------------------|
| SePay auto transaction capture | ✅ | ✅ | ✅ |
| /status, /today | ✅ | ✅ | ✅ |
| Daily recap tự động | ✅ | ✅ | ✅ |
| Bank accounts (SePay) | 1 | 3 | 5 |
| Transactions/tháng | **45** | Unlimited | Unlimited |
| Transaction history | 30 ngày | Unlimited | Unlimited |
| Categories | 5 default + 3 custom (=8) | Up to 20 custom | Unlimited |
| Weekly + Monthly report | ❌ | ✅ | ✅ |
| CSV export | ❌ | ✅ | ✅ |
| Email transaction parsing | ❌ | 1 email source | Unlimited |
| Personal vs Business split | ❌ | ❌ | ✅ |
| P&L view (income vs expense by tag) | ❌ | ❌ | ✅ |
| Google Sheets sync | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |

**Annual plan discount:**

| Tier | Monthly | Annual (paid upfront) | Discount |
|------|---------|----------------------|----------|
| Pro | $4/mo | $36/year ($3/mo equiv) | 25% |
| Business | $9/mo | $84/year ($7/mo equiv) | 22% |

**Free trial:** New user nhận 14 ngày Pro trial. Không cần thẻ. Day 12: reminder. Day 14: downgrade về Free, data preserved.

### 5.2. Chiến lược Monetization

**Persona-to-tier mapping:**

| Persona | Likely tier | WTP estimate |
|---------|-------------|--------------|
| Minh (nhân viên VP, 1 bank) | Free → Pro | $3-5/mo |
| Linh (freelancer, thu nhập biến động) | Pro | $4-7/mo |
| Hùng+ (chủ shop, personal + business) | Business | $7-12/mo |

**Revenue projection (100 users):**

| Tier | % users | Số users | Revenue/mo |
|------|---------|----------|-----------|
| Free | 85% | 85 | $0 |
| Pro ($4) | 12% | 12 | $48 |
| Business ($9) | 3% | 3 | $27 |
| **Total** | 100% | 100 | **$75/mo** |

**Revenue projection (500 users):**

| Tier | % users | Số users | Revenue/mo |
|------|---------|----------|-----------|
| Free | 82% | 410 | $0 |
| Pro | 14% | 70 | $280 |
| Business | 4% | 20 | $180 |
| **Total** | 100% | 500 | **$460/mo** |

**Upgrade trigger logic:** Tối đa 1 upgrade message/tuần/user. Triggers: trial sắp hết, chạm tx limit (35/45), chạm history limit, add bank thứ 2, cuối tháng.

**Payment:** PayOS (chuyển khoản VN, 1.5-2% fee) primary. Stripe (card quốc tế, 3.4% + 30c) secondary. 7 ngày money-back, no questions asked.

### 5.3. Chi phí vận hành ước tính

**So sánh hosting platform:**

| Platform | 10 users | 100 users | 500 users | VN latency |
|----------|----------|-----------|-----------|------------|
| **Railway** (recommend MVP) | $10-15 | $20-30 | $40-60 | Trung bình (US) |
| Fly.io (Singapore) | $5-10 | $15-25 | $40-60 | Tốt |
| DigitalOcean (Singapore) | $20-25 | $27-32 | $55-65 | Tốt nhất |
| Hetzner DIY (EU) | $5-8 | $10-15 | $25-35 | Trung bình |

**Breakdown Railway (recommend cho MVP):**

| Hạng mục | 10 users | 100 users | 500 users |
|----------|----------|-----------|-----------|
| Railway app | $5 | $10 | $20 |
| PostgreSQL (managed) | $5 | $10 | $25 |
| Domain + SSL | $1 | $1 | $1 |
| Backup + monitoring | $0 | $1 | $2 |
| **Tổng** | **~$11** | **~$22** | **~$48** |

**Phase 2 chi phí thêm:** Email parsing (Postmark +$10-15), multi-bank (+$2-5), Messenger (+$0-5).

### 5.4. Break-even analysis

**Break-even theo scale (Railway, Pro $4):**

| Scale | Cost | Paying users cần | % conversion cần |
|-------|------|------------------|------------------|
| 10 users | $11 | 3 | 30% (beta, OK) |
| 50 users | $15 | 4 | 8% |
| 100 users | $22 | 6 | 6% |
| 200 users | $30 | 8 | 4% |
| 500 users | $48 | 12 | 2.4% |

**Insight:** Unit economics improve mạnh khi scale. Ở 500 users chỉ cần 2.4% conversion là break-even.

### 5.5. So sánh pricing với competitor VN

| Sản phẩm | Free | Paid | So với FinTrack |
|---------|------|------|----------------|
| Money Lover | Cơ bản | Premium 99k/năm | FinTrack $36/năm — cao hơn, **justify bằng auto capture** |
| Spendee | 30 ngày trial | Plus 470k/năm | FinTrack tương đương price point |
| MISA Money Keeper | Free hoàn toàn | — | FinTrack advantage zero-effort |

**Narrative:** "Bạn trả thêm vì không phải nhập tay" — 100 tx/tháng × 30s nhập = 50 phút. $4/mo = $0.08/phút tiết kiệm.

### 5.6. Risks & A/B test plan

| Test | Hypothesis | Success metric |
|------|-----------|---------------|
| Pro pricing $3 vs $4 vs $5 | $4 sweet spot | Net revenue per 100 users |
| Trial 14 vs 7 vs 30 ngày | 14 ngày tối ưu | Trial → paid conversion |
| Show Business tier vs hide | Show tăng anchor cho Pro | Pro conversion rate |
| Annual discount 25% vs 30% | 25% sweet spot | % chọn annual |

**Migration:** Beta users (30 đầu) → grandfather $3 lifetime. Public launch → pricing mới $4.

---

## 6. Phân tích cạnh tranh

| Sản phẩm | Ưu điểm | Nhược điểm | So với FinTrack |
|----------|---------|------------|----------------|
| **Money Lover** | UI đẹp, nhiều features | Nhập liệu thủ công, subscription đắt | FinTrack tự động hóa hoàn toàn |
| **MISA** | Ecosystem lớn, tích hợp kế toán | Phức tạp, enterprise-focused | FinTrack đơn giản, consumer-focused |
| **Sổ Thu Chi** | Miễn phí, đơn giản | Thủ công, không tự động | FinTrack zero-effort |
| **Excel/Sheets DIY** | Linh hoạt tối đa | Tốn thời gian, dễ bỏ | FinTrack tự ghi, user chỉ bấm nút |

### Competitive advantage
1. **Zero-effort**: Giao dịch → bot hỏi → bấm 1 nút → xong. Không app, không form.
2. **Telegram-native**: Không cần install app mới, sống trong platform user đã dùng.
3. **SePay integration**: Tự động capture 100% giao dịch ngân hàng VN.
4. **2-step setup**: Competitor nào cũng cần 5+ bước. FinTrack cần 2.

---

## 7. Rủi ro & Giảm thiểu

| # | Rủi ro | Mức độ | Giảm thiểu |
|---|--------|--------|-----------|
| 1 | **SePay dependency** — SePay thay đổi API hoặc ngừng hoạt động | Cao | Monitor SePay status, chuẩn bị email parsing fallback |
| 2 | **Telegram block ở VN** | Thấp | Messenger là platform #2, sẵn sàng switch |
| 3 | **Security breach** — leak transaction data | Cao | Không lưu thông tin ngân hàng nhạy cảm (chỉ amount + description), encrypt at rest |
| 4 | **Low conversion** — users không upgrade Pro | Trung bình | Iterate pricing, tìm feature gating hợp lý |
| 5 | **SePay onboarding friction** — users không biết dùng SePay | Trung bình | Video hướng dẫn 60s, in-bot step-by-step guide |
| 6 | **Scale issues** — PostgreSQL bottleneck | Thấp | Workload nhẹ (text-based), 1 VPS xử lý được 10k+ users |

---

## 8. Timeline tổng quan

| Phase | Thời gian | Deliverables |
|-------|-----------|-------------|
| **Phase 1: Foundation** | Tuần 1-2 | Repo mới, DB schema, db.py, multi-user routing |
| **Phase 2: Handlers** | Tuần 2-3 | Refactor tất cả handlers → multi-user |
| **Phase 3: Polish** | Tuần 3-4 | Scheduling, onboarding flow, deploy Railway |
| **Phase 4: Launch** | Tuần 4-5 | Domain, beta test 10 users, iterate |
| **Phase 5: Growth** | Tháng 2-3 | Pro tier, Messenger, CSV export |

---

## 9. Stakeholders

| Vai trò | Người | Trách nhiệm |
|---------|-------|-------------|
| Product Owner | Bạn | Quyết định feature priority, pricing |
| Developer | Bạn + AI pair | Implement, deploy, maintain |
| Beta Testers | 5-10 bạn bè/đồng nghiệp | Feedback UX, bug reports |
| Users | Public (sau beta) | Sử dụng, feedback, trả tiền |

---

## 10. Tiêu chí thành công (Success Criteria)

### MVP Launch (Tháng 6/2026)
- [ ] Bot hoạt động ổn định cho ≥10 users đồng thời
- [ ] Onboarding ≤2 bước, ≤5 phút
- [ ] Zero data cross-contamination giữa users
- [ ] Daily recap fire đúng timezone cho mỗi user
- [ ] Uptime ≥99% (Railway)

### 3 tháng sau launch
- [ ] ≥30 active users
- [ ] Retention 30-day ≥60%
- [ ] ≥3 paying Pro users
- [ ] NPS ≥40 (từ survey in-bot)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial BRD |
| v1.1.0 | 2026-05-05 | Deep-dive Hùng+ persona (section 3.3), 3-tier pricing (section 5.1-5.2), revised cost + break-even (section 5.3-5.6) |
