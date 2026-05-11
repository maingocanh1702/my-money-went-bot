# Tiền Về Nơi Đâu — Business Requirements Document (BRD)

> **Version:** v3.1.0
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Draft (consolidated + 3 round revisions)
> **Thay đổi v2.3 vs v2.2 — MAJOR SCOPE EXPAND:** Combine option B+C — email parsing + SePay onboarding wizard ĐÃ vào MVP scope (không còn defer Phase 2). Lý do: serve full Hùng+ TAM ngay launch, không leave 50-60% chưa có SePay ngoài. Trade-off: timeline 8-10 tuần → **14-16 tuần**, cost @ 100 users $12-17 → **$22-27** (Postmark $10/mo), break-even threshold 4% → 7%, launch shift tháng 7-8 → **tháng 9/2026**.

---

## 1. Tổng quan dự án

### 1.1. Tên sản phẩm
**Tiền Về Nơi Đâu** — Bot tự động theo dõi tài chính cá nhân và shop nhỏ qua SePay, hoạt động trên **Telegram & Discord** (MVP), Zalo & Messenger coming soon.

### 1.2. Tầm nhìn (Vision)
Biến việc quản lý tài chính từ "mở app ngân hàng → ghi chép thủ công → quên sau 1 tuần" thành **low-effort tracking trong messaging app**: giao dịch xảy ra → bot hỏi phân loại → bấm 1 nút → P&L cập nhật real-time. **MVP launch trên Telegram + Discord** — 2 platform có bot ecosystem mạnh nhất, API thân thiện, cùng codebase qua messenger abstraction layer.

### 1.3. Bối cảnh & Vấn đề

| # | Vấn đề | Chi tiết | Status nguồn |
|---|--------|---------|---|
| 1 | **Ghi chép thủ công không bền** | Hypothesis (founder + informal observation từ Facebook seller groups): user thử tracking app, friction nhập tay làm bỏ trong 2-4 tuần. **Cần validate qua 5-7 customer interview ở Phase Validation** | Working hypothesis |
| 2 | **App phức tạp** | Money Lover, MISA Money Keeper yêu cầu nhập tay từng giao dịch — không scale với 60-80 đơn/ngày của online seller (verified qua App Store reviews + reading user complaints) | Quan sát thị trường |
| 3 | **Open banking VN chưa chuẩn hoá** | NHNN có Quyết định về Open API nhưng chưa enforce cho consumer fintech. SePay là bridge phổ biến nhất hiện tại | Quan sát thị trường |
| 4 | **Online seller không tách được shop vs cá nhân** | Quote từ informal observation Facebook seller groups (xem Section 3.3.4 verbatim quotes). **Cần validate strength of pain qua interview** | Working hypothesis |

**Lưu ý quan trọng:** Section này dựa trên **founder observation** + informal community research, không phải published market research. Trước khi commit budget lớn:
- Validate vấn đề 1 + 4 qua **5-7 customer interview** (xem Section 11)
- Decision threshold: ≥4/7 interview confirm pain "đập đầu Excel cuối tháng" → green light cho Hùng+ persona

### 1.4. Giải pháp đề xuất
Bot **Telegram + Discord** kết nối SePay → **tự động nhận giao dịch ngân hàng** → user phân loại qua nút bấm → tổng hợp báo cáo tự động. Cấu trúc 3 tier (Free / Pro / Business) phục vụ từ user cá nhân đến chủ shop nhỏ. Zalo & Messenger sẽ mở rộng ở Phase 3+ (coming soon).

### 1.5. Từ personal tool → SaaS
Bot hiện tại đã hoạt động ổn định cho 1 user (tác giả) từ tháng 4/2026. Pivot sang SaaS để:
- Phục vụ nhiều users mà không cần mỗi người tự deploy
- Loại bỏ 8 bước setup thủ công → còn 2 bước (mở bot + dán webhook URL)
- Tạo nguồn thu recurring revenue
- Mở rộng segment xuống tới **online seller / chủ shop nhỏ** với Business tier

### 1.6. Bot ownership decision

**1 shared bot do platform sở hữu trên mỗi platform** — KHÔNG bắt user tự tạo bot. Đây là quyết định kiến trúc cốt lõi của SaaS:

| Aspect | Self-hosted (current) | SaaS shared bot (target) |
|---|---|---|
| Bot creation | User tự tạo qua @BotFather | Platform tạo 1 lần trên Telegram + Discord, mọi user dùng chung |
| BOT_TOKEN | User tự manage | Platform owner manage trong Railway env (`TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`) |
| Deployment | Mỗi user 1 instance | 1 instance, multi-tenant DB, multi-platform |
| Setup time | 30-60 phút (8 bước) | 2-15 phút (1 trong 3 path) |
| User identification | Hardcode `CHAT_ID` env | Lookup `users.platform_id` từ DB (Telegram chat_id hoặc Discord user_id) |
| TAM reachable | <1% (chỉ dev/tech-savvy) | 100% Hùng+ TAM (Telegram + Discord) |

**Platform priority:**

| Platform | Status | Lý do |
|---|---|---|
| **Telegram** | ✅ MVP (primary) | Bot ecosystem mạnh, inline buttons, popular trong VN online seller + dev community |
| **Discord** | ✅ MVP (co-primary) | Bot API mature + slash commands, popular trong VN gaming/MMO/tech community, overlap lớn với Hùng+ dropshipper segment |
| **Zalo** | 🔜 Coming soon (Phase 3+) | OA API hạn chế, cần official account approval, nhưng user base lớn nhất VN |
| **Messenger** | 🔜 Coming soon (Phase 3+) | Meta API restrictions ngày càng chặt, nhưng reach rộng cho online seller trên Facebook |

**Implication operational:**
- Single point of failure per platform: Telegram suspend bot → chỉ Telegram users offline, Discord users không ảnh hưởng (và ngược lại). **Multi-platform giảm SPOF risk** so với single-platform.
- Telegram rate limit ~30 msg/s, Discord rate limit ~50 msg/s (global). Roadmap: 1 bot mỗi platform (0-500) → bot pool (500-2000) → self-host API server (2000+). Detail xem [PRD section 5.4.2](file:///Users/maingocanh/Projects/Tiền Về Nơi Đâu/docs/prd.md).
- Privacy: BOT_TOKEN compromise trên 1 platform = read conversations trên platform đó. Token rotation runbook bắt buộc cho **mỗi platform**, store trong secret manager (không commit, không log).

**Why not let user bring own bot?** Đã consider và reject:

| Approach | Pros | Cons |
|---|---|---|
| Shared bot (chosen) | UX 2-15 phút, scale được TAM | Rate limit per platform |
| BYO bot (bring your own) | No rate limit per user, no SPOF | Setup 30-60 phút giết conversion, support nightmare khi user lú BOT_TOKEN, lose 50%+ Hùng+ không tech-savvy |
| Hybrid (shared default + BYO advanced) | Cover cả 2 segment | Complexity 2x, maintenance burden, không optimize được path nào |

→ **Shared bot is the only viable choice cho mass-market consumer SaaS. Multi-platform (Telegram + Discord) MVP giảm platform risk + mở rộng TAM.**

---

## 2. Mục tiêu kinh doanh

### 2.1. Mục tiêu ngắn hạn (3 tháng)

| # | Mục tiêu | Metric | Target |
|---|----------|--------|--------|
| 1 | Launch MVP | Bot hoạt động multi-user trên Railway, 3-path onboarding (SePay quick + wizard + email parsing) | **Tháng 9/2026** (revised từ tháng 7-8 do scope expand B+C) |
| 2 | Beta users | Số users active | 10-30 users |
| 3 | Retention | Users còn dùng sau 30 ngày | ≥60% |
| 4 | Feature parity | Tất cả features từ personal bot hoạt động | 100% |
| 5 | Paying conversion (beta) | ≥1 paying Pro user trong tháng đầu | 1 user |

### 2.2. Mục tiêu trung hạn (6-12 tháng)

| # | Mục tiêu | Metric | Target |
|---|----------|--------|--------|
| 1 | Paid users (Pro) | Conversion Free → Pro | ≥10% |
| 2 | Paid users (Business) | Conversion Free → Business | ≥2% |
| 3 | Scale | Tổng users | 100-500 |
| 4 | Platform mở rộng | Zalo / Messenger integration | Validate demand (coming soon) |
| 5 | MRR | Monthly Recurring Revenue | **$100-300** (revised với pricing VN 79k/199k) |

### 2.3. KPIs theo dõi

| KPI | Cách đo | Tần suất |
|-----|---------|----------|
| DAU (Daily Active Users) | Users có ≥1 interaction/ngày | Daily |
| Transactions/user/tháng | Avg tx count per user per month | Monthly |
| Categorization rate | % tx được phân loại / tổng tx | Weekly |
| Churn rate | Users không dùng bot ≥14 ngày | Monthly |
| Conversion rate Free→Pro | Trial → paid Pro | Monthly |
| Conversion rate Free→Business | Trial → paid Business | Monthly |
| Free tier limit hit rate | % user chạm 45 tx/tháng cap | Monthly |

---

## 3. Đối tượng người dùng (User Personas)

Cấu trúc persona theo tier mục tiêu: **Minh & Linh là volume persona** (drive Free/Pro signups), **Hùng+ là revenue persona** (drive Business tier — high WTP).

### 3.1. Persona Free/Pro #1: "Minh — Nhân viên văn phòng"

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Tuổi** | 24-35 |
| **Thu nhập** | 10-25 triệu/tháng |
| **Hành vi** | Dùng Telegram/Discord hàng ngày, có 1 tài khoản ngân hàng VN (TCB, Vietcombank, MB...) |
| **Pain point** | "Cuối tháng không hiểu tiền đi đâu hết" |
| **Nhu cầu** | Track chi tiêu tự động, không cần mở app riêng |
| **Tier likely** | Free → Pro (sau khi hit 45 tx limit) |
| **Tech level** | Biết dùng SePay hoặc có thể hướng dẫn trong 5 phút |

### 3.2. Persona Free/Pro #2: "Linh — Freelancer"

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Tuổi** | 22-30 |
| **Thu nhập** | Không cố định, 8-40 triệu/tháng |
| **Hành vi** | Nhiều nguồn thu, chi tiêu không đều, có thể có hộ kinh doanh đăng ký |
| **Pain point** | "Thu nhập bất ổn, không biết tháng nào đủ tiêu tháng nào thiếu" |
| **Nhu cầu** | Track cả thu và chi, xem trend theo tháng, có thể cần cho khai thuế |
| **Tier likely** | Pro (cần weekly/monthly report) |

### 3.3. Persona Business tier: "Hùng+" — Online seller / chủ shop nhỏ

**Đây là primary persona cho Business tier — revenue driver thực sự của Tiền Về Nơi Đâu ở mid-stage.**

#### 3.3.1. Demographics

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Tuổi** | 28-42 (median 33) |
| **Giới tính** | 60% nữ, 40% nam |
| **Địa lý** | Hà Nội, TP.HCM, Đà Nẵng + tier 2 |
| **Nghề chính** | Online seller (Shopee/TikTok Shop/Lazada/Facebook Live), shop offline nhỏ, hoặc kết hợp |
| **Doanh thu shop** | 30-200 triệu/tháng (gross), median 80 triệu |
| **Lãi ròng** | 5-30 triệu/tháng — nhưng họ thường **không biết chính xác** |
| **Quy mô team** | 1 mình (60%), 1-2 nhân viên (35%), 3-5 nhân viên (5%) |
| **Banking** | 2-3 tài khoản: 1 cá nhân, 1-2 nhận thanh toán shop |
| **SePay status** | **~40-50% đã có** (người bán Shopee/TikTok cần auto-confirm đơn → đã setup SePay). **50-60% chưa có**, chỉ dùng bank app push notification hoặc email từ ngân hàng |
| **Implication onboarding** | Phải có **3 entry path** trong MVP: (a) "Đã có SePay" → quick setup 2-5 phút, (b) "Chưa có SePay nhưng OK setup" → wizard hướng dẫn 10-15 phút, (c) "Chỉ muốn dùng email" → email forwarding parsing 5-10 phút setup. Đây là quyết định product chính: **MVP cover full TAM**, không leave 50-60% Hùng+ ngoài cho đến Phase 2 |

#### 3.3.2. Job-to-be-done

> "Khi tôi check tài chính cuối tháng, tôi muốn biết shop có thực sự lãi sau khi đã rút tiền dùng cá nhân — để quyết định scale ads, nhập thêm hàng, hay chậm lại."

#### 3.3.3. Pain points (verbatim)

> "Tháng nào cũng đập đầu vào tường vì không biết shop lãi thật bao nhiêu sau khi trừ tiền tiêu cá nhân."

> "Mất 4 tiếng cuối tháng cộng Excel mà vẫn sai số. Sai 2-3 triệu là chuyện bình thường."

> "Tiền shop và tiền nhà lẫn lộn, đến lúc cần khoản gấp không biết có đủ không."

> "Đã thử Money Lover, MISA. Nhập tay không nổi với 60-80 đơn/ngày."

> "Ads Facebook trả 1 đầu, ads Shopee trả 1 đầu, ads TikTok trả 1 đầu. Không biết platform nào lãi nhất."

#### 3.3.4. Workarounds & WTP anchor

| Workaround hiện tại | % users | Cost/tháng | Pain |
|-----|------|------|------|
| Excel/Sheets thủ công | 65% | 0đ + 4-6h cuối tháng | Tốn time, sai số |
| Kế toán dịch vụ | 20% | 300k-1tr | Không real-time |
| Sổ tay giấy | 10% | 0đ | Mất sổ là mất hết |
| KiotViet POS | 3% | 150-300k | Quá nặng cho online seller |
| MISA mShopkeeper | 2% | 100-200k | Enterprise feel |

**WTP cho Tiền Về Nơi Đâu Business 199k VND ($7.96):**
- vs kế toán dịch vụ 500k → rẻ hơn 60% + real-time
- vs KiotViet 200k → rẻ hơn nhẹ, simpler
- vs Excel free → tiết kiệm 4-6h/tháng = 400k value → ROI 2x
- 199k VND đặt **dưới ngưỡng tâm lý 200k** — impulse-buy friendly cho online seller

#### 3.3.5. Sub-variants trong Business tier

| Variant | % Business users dự kiến | Pain chính |
|------|----|------|
| Hùng-seller (online seller thuần) | 60% | Tách shop vs cá nhân + multi-platform attribution |
| Linh-freelancer (multi-client) | 25% | Data clean cho khai thuế quý |
| Tuấn-mixed (offline + side hustle) | 15% | Nhìn tổng cashflow, decide khi nào full-time |

#### 3.3.6. Anti-personas (KHÔNG phải Hùng+)

| KHÔNG phải | Lý do | Đi đâu |
|-----------------|-------|--------|
| Track chi tiêu cá nhân | Không cần tách | → Pro hoặc Free |
| Shop >500tr/tháng doanh thu | Cần ERP thật | → KiotViet, MISA AMIS |
| Đầu tư stock/crypto | Wrong product | → Snowball, Finhay |
| Doanh nghiệp >5 nhân viên | Cần workspace/team feature | → Phase 3+ |
| Cần inventory management | Wrong product | → Sapo, KiotViet |

---

## 4. Phạm vi sản phẩm

### 4.1. Trong phạm vi (In-scope) — MVP

**Quyết định v2.3:** MVP serve full Hùng+ TAM với 3 entry path (B+C combined). Không leave 50-60% Hùng+ ngoài cho đến Phase 2.

| # | Feature | Mô tả | Tier |
|---|---------|-------|------|
| 1 | **3-path onboarding** | (a) Quick connect SePay, (b) SePay setup wizard, (c) Email forwarding setup | All |
| 2 | **SePay quick connect** | User đã có SePay → /start → nhận webhook URL → dán vào SePay → done (2-5 phút) | All |
| 3 | **SePay setup wizard** | User chưa có SePay → bot guide step-by-step: tạo SePay account → link bank → config webhook (10-15 phút) | All |
| 4 | **Email forwarding ingest** | User chỉ muốn email → bot cấp unique inbound address `u<id>@in.tienvenoidau.com` → user setup forwarding rule trong Gmail/Outlook → bot parse email tự động | All |
| 5 | **Multi-bank email parser** | Parse email transaction từ banks VN có hỗ trợ email notification. **MVP (6 banks):** TCB, Cake, ACB, Sacombank, BIDV, MB. **Phase 2 (Tier 2):** VCB, VietinBank, TPBank, VPBank, HDBank, Agribank + on-demand. Fallback "unparsed" notification cho bank chưa support | All |
| 6 | **Auto transaction capture** | SePay webhook + Email parser normalize vào canonical transaction schema | All |
| 7 | **Category management** | Tạo/sửa/xóa categories qua /manage | All |
| 8 | **Transaction categorization** | Inline buttons để phân loại nhanh (manual fallback khi không match rule) | All |
| 9 | **Auto-categorization (rule-based)** | Tự động phân loại giao dịch theo nội dung (description matching). **Platform default rules** cho VN phổ biến (SHOPEE, GRAB, LAZADA, TIKI, VIETTEL, FPT, ĐIỆN, NƯỚC...) + **user custom rules** (keyword → category mapping). Khi match → auto-categorize + notify, không hỏi. User có thể override bất kỳ lúc nào. Free: chỉ system defaults. Pro: +10 custom rules. Business: unlimited custom rules | All (tiered) |
| 10 | **Tracking mode** | Theo dõi chi tiêu theo category | All |
| 11 | **Budget mode (optional)** | Đặt ngân sách cho category, cảnh báo | All |
| 12 | **Reports** | /status, /today | All |
| 13 | **Daily recap** | Tự động gửi tổng kết cuối ngày (theo timezone) | All |
| 14 | **Multi-user isolation** | Mỗi user data riêng biệt | All |
| 15 | **Free tier limits** | 45 tx/tháng, 1 bank account, 30 ngày history, **1 email source**, 5 categories (3 auto-created defaults + 2 custom slots), **system default rules only** (no custom auto-cat rules) | Free |
| 16 | **14-day Pro trial** | New user mặc định Pro 14 ngày, auto-downgrade | Free |
| 17 | **Pro: Multi-bank** | 3 bank accounts | Pro |
| 18 | **Pro: Reports** | Weekly + Monthly report | Pro |
| 19 | **Pro: CSV export** | Export data ra spreadsheet | Pro |
| 20 | **Pro: Custom auto-cat rules** | 10 custom keyword → category rules (bổ sung system defaults) | Pro |
| 21 | **Pro: Email parsing 3 sources** | 3 email forwarding sources (Free = 1, Pro = 3, Business = unlimited; Free/Pro khác nhau ở tx cap 45 vs unlimited) | Pro |

### 4.2. Phase 2 (sau MVP — Business tier launch ~tháng 11-12)

**3 must-have features bundle ship đồng thời** (không split phase, theo Critical 7):

| # | Feature | Tier | Mô tả |
|---|---------|------|-------|
| 1 | **Personal vs Business toggle** | Business | Tag mỗi tx personal/business, auto theo bank account (must-have bundle) |
| 2 | **Tag-based P&L view** | Business | /pnl tách Business vs Personal, real-time (must-have bundle) |
| 3 | **Income source attribution** | Business | Auto-tag Shopee/TikTok/Facebook source (must-have bundle) |
| 4 | **Multi-bank 5 accounts** | Business | Mở rộng từ Pro 3 → Business 5 |
| 5 | **Multi-bank email parser expansion** | Business | Parse từ unlimited email sources (Pro chỉ 3) + thêm bank Tier 2: VCB, VietinBank, TPBank, VPBank, HDBank, Agribank + on-demand |
| 6 | **Google Sheets 2-way sync** | Business | Real-time sync cho kế toán dịch vụ |
| 7 | **Multi-account workspace** | Phase 3 | 1 user kết nối nhiều tài khoản SePay |

### 4.3. Phase 3+ (validate trước build)

| Feature | Mô tả | Status |
|---|---|---|
| **Zalo OA integration** | Mở rộng sang Zalo — user base lớn nhất VN, cần OA approval | 🔜 Coming soon |
| **Messenger integration** | Mở rộng sang Facebook Messenger — reach online seller trên Facebook | 🔜 Coming soon |
| Auto-categorization **ML upgrade** | Nâng cấp rule-based → ML model (tự học từ user behavior, ≥10k tx data). Supplement, không replace rules | Backlog |
| Team/family workspace | Multi-user shared workspace | Backlog |

### 4.4. Ngoài phạm vi (Out of scope)

| # | Feature | Lý do |
|---|---------|-------|
| 1 | Web dashboard | UI chính là messaging platform |
| 2 | Investment tracking | Khác product category |
| 3 | Multi-currency | VND only cho MVP |
| 4 | Inventory management | Wrong product, Tiền Về Nơi Đâu không track tồn kho |
| 5 | Invoice generation | Tool khác làm tốt hơn |
| 6 | Tax filing automation | Regulatory risk cao |

---

## 5. Mô hình kinh doanh

### 5.1. Pricing Tiers

Cấu trúc **3-tier**: Free / Pro / Business + **14-day Pro trial cho new users**.

**Geo-based pricing (2 domain, 1 codebase):**

| Market | Domain | Pro | Business | Currency |
|---|---|---|---|---|
| 🇻🇳 **Việt Nam** | `tienvenoidau.com` | **79k VND/mo** (~$3.16) | **199k VND/mo** (~$7.96) | VND |
| 🌍 **Global** | `mymoneywent.com` | **$4/mo** (100k VND equiv) | **$9/mo** (220k VND equiv) | USD |

> **Lý do tách pricing:** VN market price-sensitive hơn — 79k dưới ngưỡng tâm lý 100k, 199k dưới 200k. Global pricing giữ $4/$9 để competitive với Money Lover Linked Wallet ($3-5/mo). Cùng 1 codebase, pricing resolve theo domain/locale.

**Feature matrix (chung cho cả 2 market, chỉ khác giá):**

| Feature | Free | Pro | Business |
|---------|------|----------------------|---------------------------|
| SePay config (auto capture) | ✅ | ✅ | ✅ |
| /status, /today | ✅ | ✅ | ✅ |
| Daily recap tự động | ✅ | ✅ | ✅ |
| Bank accounts | 1 | 3 | 5 |
| Transactions/tháng | **45** | Unlimited | Unlimited |
| Transaction history | 30 ngày | Unlimited | Unlimited |
| Categories | 5 total (3 default + custom) | Up to 20 custom | Unlimited |
| Auto-categorization rules | System defaults only | System defaults + **10 custom rules** | System defaults + **unlimited custom rules** |
| Weekly + Monthly report | ❌ | ✅ | ✅ |
| CSV export | ❌ | ✅ | ✅ |
| Email transaction parsing | 1 email source | 3 email sources | Unlimited |
| Personal vs Business split | ❌ | ❌ | ✅ |
| P&L view (income vs expense by tag) | ❌ | ❌ | ✅ |
| Google Sheets sync | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |

> **Lưu ý SePay:** Khi kết nối bank account qua SePay (cả 3 tier), user tự thanh toán chi phí gói SePay. Tiền Về Nơi Đâu không cover chi phí này.

**Annual plan (20% off cho cả 2 tier):**

| Market | Pro Annual | Business Annual |
|---|---|---|
| 🇻🇳 VN | 758k VND/năm (63.2k/mo) | 1.91tr VND/năm (159.2k/mo) |
| 🌍 Global | $38.40/năm ($3.20/mo) | $86.40/năm ($7.20/mo) |

Tương đương ~2.4 tháng free khi trả năm.

**Trial:** Mọi new user nhận 14 ngày Pro miễn phí, không cần thẻ. Day 12 prompt upgrade. Day 14 auto-downgrade Free, data preserved.

### 5.2. Chiến lược Monetization

#### 5.2.1. Persona-to-tier mapping

| Persona | Tier likely | WTP estimate |
|---------|-------------|------|
| Minh (nhân viên văn phòng) | Free → Pro | 50-100k/mo |
| Linh (freelancer) | Pro | 79-150k/mo |
| Hùng+ (online seller / chủ shop) | Business | 150-300k/mo |

#### 5.2.2. Conversion target & revenue projection (with churn modeled)

Free tier 45 tx/tháng đặt **dưới median chi tiêu user đô thị VN** (~30-80 tx) → ~50-60% active users sẽ chạm limit → upgrade pressure mạnh.

**Churn assumption:** Realistic SaaS B2C VN có churn 5-8%/tháng (industry standard cho consumer fintech). Apply 7%/tháng cho projection — voluntary churn (user cancel) + involuntary (payment fail).

**Cohort projection — conservative 5% paid (4% Pro + 1% Business), steady-state ở 100 active users:**

| Tier | % active users | Số users | Gross Revenue/mo | Sau 7% churn impact |
|------|---------|----------|-----------|----|
| Free | 95% | 95 | $0 | — |
| Pro (79k) | 4% | 4 | 316k VND ($12.64) | $11.75 (−$0.89) |
| Business (199k) | 1% | 1 | 199k VND ($7.96) | $7.40 (−$0.56) |
| **Total** | 100% | 100 | **515k VND ($20.60)** | **~$19.15/mo** |

**Steady-state ở 500 active users (cần acquire ~650-700 total):**

| Tier | % active | Số users | Gross | Net sau churn |
|------|---------|----------|-----------|----|
| Free | 95% | 475 | $0 | — |
| Pro (79k) | 4% | 20 | 1,580k VND ($63.20) | $58.78 |
| Business (199k) | 1% | 5 | 995k VND ($39.80) | $37.01 |
| **Total** | 100% | 500 | **2,575k VND ($103.00)** | **~$95.79/mo** |

**Implications của churn 7%:**
- Phải acquire ~25-30% extra users so với projection no-churn để giữ steady-state
- LTV Pro ở 7% churn: $3.16/mo ÷ 7% = ~$45
- LTV Business: $7.96/mo ÷ 7% = ~$114
- → CAC payback < $15-25 cho Pro để economic make sense

**Sensitivity tới churn:**

| Churn rate | MRR @ 500 active | LTV Pro |
|---|---|---|
| 3% (best case) | $100 | $105 |
| 5% (target) | $98 | $63 |
| 7% (realistic VN B2C) | $96 | $45 |
| 10% (worst case) | $93 | $32 |

→ MRR target **$93-100** ở 500 users với churn realistic và 5% paid conversion. Cần **tăng paid conversion lên 8-10%** hoặc accept margin mỏng giai đoạn đầu.

**Cách giảm churn (priority cho retention work):**

1. Daily recap forming habit (nếu user dùng đều, churn thấp hơn 50%)
2. Annual plan discount → switch tới yearly billing (involuntary churn ~0%)
3. Win-back flow cho user inactive 14 ngày
4. Onboarding completion rate cao (user complete setup → churn 30-day giảm 60%)

#### 5.2.3. Upgrade trigger logic

| Trigger event | Message | Target tier |
|---------------|---------|-------------|
| Day 12 of trial | "Trial còn 2 ngày, giữ Pro để xem report tuần?" | Pro |
| User chạm 30 ngày history limit | "Muốn xem lại giao dịch cũ hơn 30 ngày?" | Pro |
| User dùng 35/45 tx (Free) | "Bạn đã dùng 35/45 giao dịch tháng này. Upgrade để unlimited" | Pro |
| User chạm 45 tx/tháng | "Đã hết quota. Giao dịch mới sẽ không được track" | Pro |
| User add bank account thứ 2 (Free) | "Free hỗ trợ 1 tài khoản. Pro cho 3, Business cho 5" | Pro/Business |
| User dùng emoji 🏪 hoặc tag "shop"/"business" | "Có vẻ bạn quản lý cả tiền cá nhân và shop. Business tier có tách riêng" | Business |
| Cuối tháng (Free user) | "Xem báo cáo tháng đầy đủ với Pro" | Pro |

Quy tắc: max 1 upgrade message/tuần/user.

#### 5.2.4. Payment

- **Bank transfer + auto-detect** (primary, 0% fee) — user chuyển khoản tới platform's bank account với ref string `PAY-{user_id}-{plan}-{period}-{nonce4}` → SePay webhook detect ≤ 60s, Email parsing backup ≤ 5min. 4-layer fuzzy matching cho typo tolerance. Detail spec: [feature_payment.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_payment.md).
- **PayPal** (quốc tế, ~4.4% + fixed fee) — Phase 2 nếu có demand
- **USDT** (crypto, ~0% fee — chỉ blockchain gas fee) — Phase 2 nếu có demand
- **Refund:** 7 ngày money-back, no questions asked. Manual transfer back qua bank.

**Pre-launch blocker:** Founder phải đăng ký **hộ kinh doanh** trước paying user đầu tiên (Phase 6 deploy). Lead time 1-2 tuần. Xem feature spec §8 cho compliance checklist đầy đủ.

**Recurring billing:**
- Monthly: reminder 3 ngày trước expiry, grace period 7 ngày sau expiry, sau đó auto-downgrade Free
- Annual: reminder 14+3+1 ngày trước expiry, cùng grace period 7 ngày
- Push annual mạnh ở mọi monthly upgrade message để giảm friction recurring

### 5.3. Chi phí vận hành ước tính (Railway, recommend platform MVP)

#### 5.3.1. Pricing rate (Railway Hobby plan, May 2026)

| Resource | Per-month rate |
|----------|---------------|
| Memory (actual RSS) | ~$10.14/GB/mo |
| CPU (actual usage) | ~$20.29/vCPU/mo |
| Volume | ~$0.16/GB/mo |
| Egress | $0.05/GB |
| Hobby plan minimum | $5/mo (includes $5 credit) |

Railway charge **actual consumption**, không phải provisioned limit.

#### 5.3.2. Cost projection theo scale (MVP scope = B+C combined, email parsing IN MVP)

| Hạng mục | 10 users | 100 users | 500 users |
|----------|----------|-----------|-----------|
| Railway resource usage (app + Postgres) | $5 (min) | $10-15 | $30-50 |
| Domain + SSL | $1 | $1 | $1 |
| Backup ngoài (Backblaze B2) | $1 | $1 | $2 |
| **Inbound email parsing (Postmark / Mailgun)** | $10 | $10 (≤10k email/mo) | $35 (volume tier) |
| **Tổng fixed cost MVP** | **~$17** | **~$22-27** | **~$68-88** |

**Lưu ý cost shift:** Email parsing từ Phase 2 (+$15 optional) → **MVP mandatory (+$10-35)**. Tổng cost @ 100 users: $22-27 (vs $12-17 ở v2.2). Trade-off chấp nhận để cover full TAM.

**Optional alternative để tiết kiệm:**

| Cách | Cost saving | Trade-off |
|---|---|---|
| Self-host inbound mail server (Postfix + parsing service) | -$10/mo | +20-30h setup, ongoing maintenance, deliverability risk |
| Email forwarding qua Cloudflare Email Routing (free) + parser tự build | -$10/mo | Cloudflare miễn phí nhưng có rate limit, không guarantee enterprise reliability |
| Outsource email parsing tới user's existing tools (Zapier, Pipedream) | -$10/mo | Push complexity sang user, mất "zero-effort" value prop |

→ Recommend **Postmark $10/mo trong MVP** để giảm risk + ship nhanh. Migrate self-host sau khi $200+ MRR.

#### 5.3.3. So sánh hosting platform alternative

| Platform | 100 users | Setup effort | VN latency | Khi nào dùng |
|----------|-----------|--------------|------------|----------------|
| **Railway Hobby** (recommend MVP) | $10-15 | 30 phút | 200-300ms | Pre-revenue → mid-stage |
| Hetzner Singapore DIY | $7-10 | 8-15h ban đầu | 50-80ms | Khi MRR > $200 hoặc Railway bill > $25/mo |
| Fly.io DIY Postgres | $13-18 | 4-6h | 50-80ms | Alternative trung bình |
| Fly.io managed Postgres | $46 | 1h | 50-80ms | Không recommend (Postgres giá tăng 2024) |
| DO Singapore managed | $27-32 | 2-4h | 30-50ms | Khi cần stability + paid users VN |
| VN VPS (Tinohost/Bizfly) | $5-8 | 8-15h | <30ms | Khi VN latency là feature critical |

#### 5.3.4. Variable cost không tính

- **Payment fees:** Bank transfer 0%, PayPal ~4.4%, USDT ~0% — blended ~1-2% tùy mix (COGS)
- **Customer support time:** 100 users × 1-2 ticket/tháng × 10-15p = 15-50h/tháng cho solo founder
- **Developer ops time** (chỉ áp khi self-host): 8-15h setup + 2-4h/tháng maintenance

### 5.4. Break-even Analysis

#### 5.4.1. Break-even theo platform @ 100 users (Pro 79k, Business 199k, MVP scope = B+C combined)

Với blended ARPU ~$5.15/paying user (4:1 Pro:Business ratio):

| Platform | Cost (incl. email parsing) | Paying users cần | % conversion break-even |
|---------|------|----------------|----------------------|
| **Railway Hobby + Postmark** | $25 | **5** | **5%** |
| Hetzner Singapore + Postmark | $20 | 4 | 4% |
| DO Singapore + Postmark | $42 | 9 | 9% |
| Fly.io managed + Postmark | $56 | 11 | 11% |

→ Railway @ 5% break-even — sát với conservative 5% paid assumption. Cần đạt **≥6% paid** để có buffer.

> **⚠️ Lưu ý:** Với 5% paid (4% Pro + 1% Business), revenue @100 users = $20.60 < cost $25. Break-even cần ~6.1% paid. Founder accept subsidize ~$5/mo giai đoạn 100 users.

#### 5.4.2. Break-even theo scale (Railway, MVP với email parsing)

| Scale | Cost/mo | Revenue @5% paid | Lãi/Lỗ |
|-------|---------|-----------------|--------------|
| 10 users | $17 | $2.06 | ❌ Lỗ $14.94 (beta, founder subsidize) |
| 50 users | $20 | $10.30 | ❌ Lỗ $9.70 |
| 100 users | $25 | $20.60 | ❌ Lỗ $4.40 (gần break-even) |
| 200 users | $32 | $41.20 | ✅ Lãi $9.20 |
| 500 users | $73 | $103.00 | ✅ Lãi $30.00 |

**Insight quan trọng:** Với pricing 79k/199k và 5% paid, **break-even ở ~150-200 users**. Dưới 200 users founder phải subsidize. Recommend: **founder pay out-of-pocket $50-100/tháng cho 4-6 tháng đầu**, accept sunk cost. Nếu paid conversion đạt 8-10% thì break-even sớm hơn (~100 users).

#### 5.4.3. Margin analysis — Phân biệt 2 mức margin

**A. Infrastructure margin (chỉ trừ cost hosting, KHÔNG phải business margin):**

| Scale | Infra cost | Mix dự kiến | Revenue | Infra margin |
|-------|-----------|-------------|---------|-----|
| 100 users | $15 | 4% Pro + 1% Business | $20.60 | **+$5.60 (27%)** |
| 500 users | $40 | 4% Pro + 1% Business | $103.00 | **+$63.00 (61%)** |

**B. Realistic business margin (trừ cả operating cost):**

| Scale | Revenue | Infra | Payment fees (~1.5% blended) | Customer support (solo founder time @250k/h) | Net margin |
|-------|---------|-------|---------------------------|---------------------------------------------|------------|
| 100 users | $20.60 | $15 | $0.31 | $200/mo (~30h × 250k) | **-$195 (LOSS, founder time = burn)** |
| 500 users | $103.00 | $40 | $1.55 | $400/mo (~50h × 250k) | **-$339 (LOSS nếu thuê support)** |

**C. Realistic margin nếu founder không tính lương cho mình (bootstrap mode):**

| Scale | Revenue | Infra + Fees | Net margin |
|-------|---------|--------------|------------|
| 100 users | $20.60 | $15.31 | **+$5.29 (26%) — founder làm support free, margin mỏng** |
| 500 users | $103.00 | $41.55 | **+$61.45 (60%) — chỉ viable nếu founder tự support** |

**Kết luận:**
- **Pricing 79k/199k với 5% paid** cho margin mỏng — chỉ viable ở bootstrap mode (founder tự làm mọi thứ).
- **Break-even infra ở ~150-200 users**. Dưới đó founder subsidize.
- **Business margin thực tế** là negative khi tính support time ở mọi scale dưới 1000 users.
- **Upside path:** Nếu paid conversion tăng lên 8-10% (realistic nếu 45 tx gating works), revenue @500 users = $165-206 → margin tốt hơn nhiều.
- Phải design cho **support automation** (FAQ bot, self-serve onboarding) để giữ support time <20h/tháng ở 500 users.
- **Pricing 79k/199k là play cho conversion volume** — sacrifice margin per user để maximize total paying users trong VN price-sensitive market.

---

## 6. Phân tích cạnh tranh

### 6.1. Phân loại competitor theo feature

Competitor không monolithic — phải phân theo capability để định vị đúng:

| Capability | Manual entry only | Auto-capture from bank |
|-----------|-------------------|----------------------|
| **Sản phẩm** | Money Lover Free, MISA Money Keeper, Sổ Thu Chi | **Money Lover + Linked Wallet, Tiền Về Nơi Đâu** |
| **TAM VN** | Mass market | Niche (cần connection với bank) |
| **Pricing model** | One-time / Free | Subscription |

### 6.2. So sánh chi tiết

| Sản phẩm | Pricing | Auto-capture? | Personal/Business split? | Channel | So với Tiền Về Nơi Đâu |
|----------|---------|---------------|------------------------|---------|----------------|
| **Money Lover Free** | Miễn phí | ❌ (manual) | ❌ | Mobile app | Khác category — Tiền Về Nơi Đâu auto-capture |
| **Money Lover Premium** | $24.49 one-time | ❌ (vẫn manual) | ❌ | Mobile app | Premium chỉ unlock features (CSV, attach), không có auto-capture |
| **Money Lover + Linked Wallet** | Premium $24.49 + Linked Wallet sub (~$3-5/mo) | ✅ | ❌ | Mobile app | **Đây mới là direct competitor.** Tiền Về Nơi Đâu chạy Telegram (no app install), có Personal/Business split |
| **MISA Money Keeper** | Free + ads | ❌ (manual) | ❌ | Mobile app | Khác category |
| **Sổ Thu Chi MISA** | Free | ❌ | ❌ | Mobile app | Khác category |
| **Excel/Sheets DIY** | Free + 4-6h/tháng | Semi (paste statement) | Manual tag | N/A | Tiền Về Nơi Đâu tự động + chat UX |
| **KiotViet POS** | 200-300k/mo | ✅ (POS scope) | ❌ (POS focused) | Web + mobile | Wrong category cho online seller cá nhân |
| **Kế toán dịch vụ** | 500k-1tr/mo | Manual (kế toán nhận invoice) | ✅ (manual) | Email/Zalo | Tiền Về Nơi Đâu Business: 56% rẻ hơn + real-time |

### 6.3. Direct competitor analysis: Money Lover + Linked Wallet vs Tiền Về Nơi Đâu

Đây là cuộc cạnh tranh thực sự. So sánh head-to-head:

| Dimension | Money Lover + Linked Wallet | Tiền Về Nơi Đâu Pro |
|-----------|------------------------------|-------------|
| **Total cost năm 1** | $24.49 + ~$36-60 sub = $60-84 | $36-48 (annual hoặc monthly) |
| **Total cost năm 2-5** | ~$36-60/năm | $36-48/năm |
| **5-year TCO** | ~$180-300 | $180-240 |
| **Auto-capture** | ✅ Bank API | ✅ SePay webhook |
| **Bank coverage VN** | Vietcombank, TCB, BIDV, Sacombank... (limited list) | Mọi bank SePay support |
| **Channel** | Mobile app (cần install) | Telegram + Discord (đã có sẵn) |
| **Setup time** | 10-20 phút (download app + link bank + verify) | 2-5 phút (start bot + paste webhook) |
| **Multi-bank** | ✅ | ✅ Pro 3 banks, Business 5 banks |
| **Personal/Business split** | ❌ | ✅ (Business tier) |
| **Khai thuế support** | Manual export | ✅ Google Sheets sync (Business) |
| **Habit formation** | App icon trên màn hình → có thể quên | Trong Telegram → check bot khi check chat |
| **Privacy concern** | Read-only access bank account | Webhook nhận data từ SePay (không touch bank credential) |

→ **TCO 5 năm gần như tương đương** giữa Money Lover Linked Wallet và Tiền Về Nơi Đâu Pro. Khác biệt chính ở **3 điểm:**

1. **Channel** — Telegram + Discord native vs mobile app: lợi cho Tiền Về Nơi Đâu với user đã sống trong messaging (2 platform từ MVP, Zalo + Messenger coming soon)
2. **Personal/Business split** — Tiền Về Nơi Đâu có (Business tier), Money Lover không
3. **Bank coverage** — Money Lover hỗ trợ direct bank, Tiền Về Nơi Đâu qua SePay (cần user có SePay)

### 6.4. Competitive advantage thực sự

Bỏ qua claim cũ "9x đắt hơn Money Lover" (sai vì so sánh apple-to-orange). Differentiation thực sự:

1. **Telegram + Discord native trong VN context** — đa số online seller đã dùng Telegram (cộng đồng MMO, dropshipper VN active trên Telegram), Discord popular trong gaming/tech/MMO community. Tiền Về Nơi Đâu sống trong workflow đã có trên cả 2 platform.
2. **Personal vs Business split** — feature không competitor consumer-facing nào có. KiotViet có nhưng quá nặng. Kế toán dịch vụ có nhưng không real-time.
3. **3-path onboarding cover 100% Hùng+ TAM ngay từ MVP**: SePay quick connect (40-50% có sẵn SePay), SePay wizard (10-20% sẵn sàng setup), Email forwarding parsing (40-50% chỉ muốn dùng email). Không competitor consumer nào có 3 path này.
4. **Setup time 2-15 phút** tùy path. Money Lover Linked Wallet 10-20 phút (download app + link bank + verify SMS) — chỉ 1 path duy nhất, không serve user prefer email-only.
5. **Real-time P&L** vs kế toán dịch vụ delay 7-30 ngày.

### 6.5. Định vị giá thị trường (revised)

| Comparable | Price/year | Tiền Về Nơi Đâu equivalent | Gap |
|-----------|-----------|--------------------|---|
| Money Lover Linked Wallet (auto-capture) | $36-60/năm | Pro 758k VND (~$30)/năm | **Tiền Về Nơi Đâu rẻ hơn 17-50%** |
| Money Lover Premium one-time + Linked Wallet | $60-84 năm 1 | Pro 758k (~$30) năm 1 | Tiền Về Nơi Đâu **rẻ hơn 50-64%** năm đầu |
| Kế toán dịch vụ | 6-12tr/năm ($240-480) | Business 1.91tr (~$76)/năm | Tiền Về Nơi Đâu **68-84% rẻ hơn** |
| KiotViet POS | 2.4-3.6tr/năm | Business 1.91tr (~$76)/năm | Tiền Về Nơi Đâu **47-79% rẻ hơn** (nhưng feature scope khác) |

→ Tiền Về Nơi Đâu Pro 79k/mo **rẻ hơn đáng kể** so với Money Lover Linked Wallet. Tiền Về Nơi Đâu Business 199k là **extreme value play** so với kế toán dịch vụ và KiotViet — dưới ngưỡng 200k tâm lý.

### 6.6. Risk competitive

| Risk | Mức độ | Mitigation |
|------|-------|-----------|
| Money Lover thêm Telegram bot integration | Trung bình | Speed-to-market: launch trước, build community |
| MISA cho ra Telegram bot Money Keeper | Thấp | MISA enterprise focus, ít likely care consumer chat-bot |
| New entrant Vietnamese (vd Cake, Tymee, Misa expand) | Trung bình | Tier-based positioning + Personal/Business split là moat |
| SePay tự build feature tracking | Cao | SePay focus payment, ít likely build full P&L. Nếu họ build, partnership > compete |

---

## 7. Rủi ro & Giảm thiểu

| # | Rủi ro | Mức độ | Giảm thiểu |
|---|--------|--------|-----------|
| 1 | **SePay dependency** — đổi API hoặc ngừng hoạt động | Trung bình (giảm từ Cao) | Email parsing đã có trong MVP → khi SePay down, user vẫn dùng được path email |
| 1b | **Email parser accuracy < 80%** ở 1+ banks | Cao | (1) Test parser với 50+ email mẫu mỗi bank trước launch. (2) Build "unparsed" notification flow — user vẫn thấy có email đến nhưng phải manual entry. (3) Monitor parser accuracy weekly, alert nếu drop |
| 1c | **Bank thay đổi format email** | Trung bình | Versioned parsers + fallback chain. Subscribe alerts từ 6 banks MVP cho changes |
| 1d | **Postmark/Mailgun pricing thay đổi** | Thấp | Architect parsing pipeline modular để swap email service. Self-host fallback nếu cần |
| 2 | **Telegram block ở VN** | Thấp (giảm từ trước) | Discord là co-primary platform — user chuyển sang Discord ngay. Zalo/Messenger coming soon Phase 3+ |
| 3 | **Security breach** — leak transaction data | Cao | Encrypt at rest, không lưu account number, audit log access, daily backup B2 |
| 4 | **Low conversion Pro** — user không upgrade | Trung bình | Free 45 tx force upgrade, A/B test pricing $3-5 trong beta |
| 5 | **Business tier failure** — TAM nhỏ hơn dự kiến HOẶC must-have features (Personal/Business toggle, P&L, Sheets sync) build không đủ tốt | **Cao** | (1) Validate **trước** build với 5-7 customer interview Hùng+ + 5 beta concierge user. (2) Threshold go/no-go: ≥3/5 nói "trả $9/mo" → mới build. (3) Bundle 3 must-have features ship đồng thời, không split phase. (4) Backup plan: nếu Business fail, MRR target hạ xuống $250-300 (chỉ Pro), reposition Tiền Về Nơi Đâu thành "Telegram tracker cho cá nhân + freelancer" |
| 6 | **45 tx Free quá tight** → user churn thay vì upgrade | Trung bình | Monitor hit-limit-rate, nếu churn > upgrade thì nới 45 → 60-75 |
| 7 | **SePay onboarding friction** | Trung bình | Video 60s, in-bot step-by-step guide |
| 8 | **Railway pricing thay đổi** | Trung bình | Architect Docker Compose từ đầu để migrate Hetzner trong 1 tuần |
| 9 | **Compliance VN (Nghị định 13/2023 PDPA)** | Cao | Privacy policy rõ, data retention policy, breach response plan. PDPA breach runbook deferred — re-eval @ 200 users hoặc post-incident (xem [implementation plan §5b](file:///Users/maingocanh/Projects/Tiền Về Nơi Đâu/docs/implementation-plan-500-users-and-more.md)) |
| 10 | **Scale > 500 users PostgreSQL bottleneck** | Thấp | Workload nhẹ, single-VM Hetzner xử lý 1k+ user. DB scaling concrete plan ở implementation plan §C4 |
| 11 | **Abuse / spam attacks** (mass signup, /upgrade flood, webhook DDoS) | Trung bình | Rate limit per user (3 /upgrade/day, anti-mass-signup per IP) + admin tools `/admin_pause_user` + DR runbook §8c playbook. Detection signals trong observability §2.5 |
| 12 | **Founder solo support burnout @ 200+ users** | Cao | C1 customer support automation MUST ship trước reach 250 users (FAQ bot + self-serve troubleshooting). Tracked trong implementation plan §C1. Hire 1 part-time consider khi MRR > $500 |
| 13 | **Telegram bot suspended** (rare nhưng impactful) | Thấp-Trung bình | `BOT_TOKEN_BACKUP` env var ready. `@TienVeNoiDauUpdates` channel làm out-of-band notification path (created pre-launch). DR runbook §6 Scenario D playbook |
| 14 | **Cost burn > revenue** ở scale 100-300 users (valley of death) | Trung bình | Cost monitoring dashboard (observability §4.3) + error budget policy (observability §4b). Trigger Hetzner migration nếu Railway > $50/mo. Founder accept $50-100/mo burn 3-4 tháng đầu (BRD §5.4.2) |

---

## 8. Timeline tổng quan

**Revised v2.3 (combined B+C scope):** **14-16 tuần** từ ngày bắt đầu (vs 8-10 tuần v2.0). Mở rộng do thêm SePay wizard + email parsing vào MVP. Trade-off: thêm 4-6 tuần dev time, đổi lại MVP cover 100% Hùng+ TAM ngay launch.

**Revised v2.7.2 (admin tools + observability scope):** Phase 6 mở rộng tuần 10-11 → **tuần 10-12** (10 ngày → 14-20 ngày work) để cover payment integration (8-12 ngày) + admin tools commands (3-5 ngày) + observability dashboard (3-5 ngày). Tổng timeline vẫn **16 tuần** vì Phase 7 dịch tuần 13-14, Phase 8 dịch tuần 15-16 (buffer week 16 absorbed). Pre-Phase 1: viết 3 spec critical — [admin tools](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_admin_tools.md), [disaster recovery](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md), [observability](file:///Users/maingocanh/Projects/MyMoneyWent/docs/observability-plan.md) — 3-5 ngày, parallel với hộ kinh doanh registration lead time.

| Phase | Thời gian | Deliverables |
|-------|-----------|-------------|
| **Phase 1: Foundation** | Tuần 1-2 | Repo mới, DB schema (incl. `admin_audit_log`, `analytics_events`), multi-user routing, **messenger.send() interface abstraction cho Telegram + Discord**, Docker Compose setup |
| **Phase 2: Handlers refactor** | Tuần 3-4 | Refactor handlers → multi-user via messenger interface (**Telegram + Discord adapters**), auth flow, tenant isolation, **admin command authorization framework** (ADMIN_IDS per platform) |
| **Phase 3: Pricing logic** | Tuần 5 | Free tier limits (45 tx, 1 bank), trial logic, upgrade triggers |
| **Phase 4: SePay onboarding** | Tuần 6 | Quick connect path + Wizard guide step-by-step cho user chưa có SePay |
| **Phase 5: Email parsing** | Tuần 7-9 | Inbound email service setup (Postmark) + parser cho 6 banks MVP (TCB, Cake, ACB, STB, BIDV, MB) + fallback unparsed notification |
| **Phase 6: Polish + Deploy** | Tuần 10-12 | **Expanded to 3 tuần** (was 2): scheduling per timezone, onboarding flow polish, **payment integration: bank transfer auto-detect via SePay primary + Email backup + manual review fallback** (8-12 ngày dev), **admin tools commands** (3-5 ngày, [spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_admin_tools.md)), **observability dashboard + alerts** (3-5 ngày, [plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/observability-plan.md)), Railway production deploy + domain, backup automation + [DR runbook](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md). PayPal/USDT defer Phase 2. |
| **Phase 7: Closed beta** | Tuần 13-14 | Beta 5-10 user thật, đo actual cost, iterate critical bugs, **test recovery backup full restore** (DR runbook §F.A scenario) |
| **Phase 8: Public soft launch** | Tuần 15-16 | Mở rộng 20-30 user, validate 3 onboarding path, monitor parser accuracy. Buffer absorbed nếu Phase 5/6 slip |

**Phase 9-12 (tháng 4-12 sau launch):**
- Tháng 4-6: Growth Free → Pro, validate conversion target, monitor email parser accuracy + add bank
- Tháng 7-9: Customer interview Hùng+, validate Business tier hypothesis
- Tháng 10-12: Build Business tier (Phase 2 features bundle), launch ~tháng 11-12

**Risk timeline:**

| Phase | Khả năng slip | Mitigation |
|---|---|---|
| Phase 5 (Email parsing) | **Cao** | 6 bank parsers là 6 mini-projects. Nếu slip, giảm scope xuống 3 banks đã có mẫu tốt nhất (recommend TCB, Cake, MB/BIDV tùy fixture) → MVP launch với 3 banks, add phần còn lại sau |
| Phase 6 (Payment integration) | Thấp-Trung bình | Bank transfer auto-detect reuse SePay+Email infra (đã build từ Phase 1-5). Manual review fallback cho ≤5% edge case. PayPal/USDT defer Phase 2 nếu cần |
| Phase 7 (Beta) | Trung bình | Bug discovery trong beta là expected, buffer 2 tuần đã include |

---

## 9. Stakeholders

| Vai trò | Người | Trách nhiệm |
|---------|-------|-------------|
| Product Owner | Founder | Quyết định feature priority, pricing, persona prioritization |
| Developer | Founder + AI pair | Implement, deploy, maintain |
| Beta Testers Free/Pro | 5-10 bạn bè/đồng nghiệp (persona Minh/Linh) | Feedback UX, bug reports |
| Beta Testers Business | 5 online seller recruit từ Facebook group | Validate Business hypothesis |
| Users | Public (sau soft launch) | Sử dụng, feedback, trả tiền |
| Legal advisor (consult ad-hoc) | Lawyer freelance | Review privacy policy, PDPA compliance, payment terms |

---

## 10. Tiêu chí thành công (Success Criteria)

### MVP Launch (Tuần 14-16, ~tháng 9/2026)

**Functional criteria:**

- [ ] Bot hoạt động ổn định cho ≥10 users đồng thời
- [ ] **3-path onboarding** đều functional: SePay quick connect, SePay wizard, Email forwarding parsing
- [ ] Zero data cross-contamination giữa users
- [ ] Daily recap fire đúng timezone cho mỗi user
- [ ] Trial flow hoạt động đúng (auto-downgrade Day 14)
- [ ] Free tier limits enforce đúng (45 tx, 1 bank, 30 ngày history, 1 email source, 5 categories)
- [ ] **Admin tools commands** working end-to-end (xem [feature_admin_tools.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_admin_tools.md)): `/admin_help` (auto-generated), `/admin_resolve`, `/admin_refund`, `/admin_force_plan`, `/admin_stats`, `/admin_cost`. Rate limit 30/min per admin enforced.
- [ ] **`@TienVeNoiDauUpdates` Telegram channel created** pre-launch — out-of-band notification path cho bot suspension scenarios

**Reliability criteria:**

- [ ] Uptime ≥99% (Railway) trong 2 tuần beta
- [ ] **Email parser accuracy ≥85%** cho mỗi bank trong 6 banks MVP support (test 50+ email mẫu/bank)
- [ ] Unparsed email fallback flow hoạt động (user nhận notification "có email đến nhưng không parse được, manual entry?")
- [ ] **Backup recovery test thành công**: ít nhất 1 lần test full DB restore từ B2 backup vào staging environment, verify data integrity (DR runbook §11 quarterly drill schedule)
- [ ] **Error budget tracked**: rolling 30-day error rate < 0.1% (observability §4b 3-tier policy)
- [ ] **Critical alerts armed**: 7 critical alerts trong observability §5.1 routing tới admin Telegram chat
- [ ] **PLATFORM_TOKEN webhook silence** monitoring active (alert nếu 24h zero events — revenue blind detection)

**Cost criteria:**

- [ ] Actual cost ≤ $25/mo @ 10-20 users (validate BRD numbers, threshold elevated từ $15 do email parsing infra)
- [ ] Postmark email volume ≤ 10k/mo @ 100 users (stay trong $10 tier)
- [ ] **Cost dashboard active** (observability §4.3): `/admin_cost` show Railway + Postmark + B2 cost vs MRR weekly
- [ ] **Margin > 50% sustained** ở 100 users (early signal cho unit economics health)

**Onboarding criteria:**

- [ ] SePay quick connect path: median time ≤5 phút từ /start tới first transaction
- [ ] SePay wizard path: median time ≤15 phút
- [ ] Email forwarding path: median time ≤10 phút (forward rule setup là bottleneck)
- [ ] ≥80% beta users complete onboarding trong 1 session

**Operational readiness criteria:**

- [ ] **Disaster recovery runbook** ([docs/runbooks/disaster-recovery.md](file:///Users/maingocanh/Projects/Tiền Về Nơi Đâu/docs/runbooks/disaster-recovery.md)) — 8 scenarios documented (incl. Scenario G SePay outage, Scenario H abuse/spam)
- [ ] **B2 backup credentials** stored trong password manager (1Password/Bitwarden), shared vault với 1 trusted contact
- [ ] **B2 SSE-B2 server-side encryption** verified
- [ ] Daily `pg_dump` (incl. `pg_dumpall --globals-only` cho roles) automated
- [ ] Trusted contact briefed on emergency runbook + access các critical credentials

### 3 tháng sau launch

- [ ] ≥30 active users
- [ ] Retention 30-day ≥60%
- [ ] ≥3 paying Pro users
- [ ] Free→Pro conversion ≥8%
- [ ] Free tier hit-limit rate 40-60% (validate gating)
- [ ] NPS ≥40 (từ survey in-bot)

### 12 tháng sau launch

- [ ] 100-500 active users
- [ ] MRR $100-300 (2.5tr-7.5tr VND)
- [ ] Free→Pro conversion ≥10%
- [ ] Business tier launched (Phase 2)
- [ ] Free→Business conversion ≥2%
- [ ] Net margin ≥70%

---

## 11. Validation Plan trước commit Business tier

Trước khi build Phase 2 Business tier (tháng 5-6 sau launch):

1. **5-7 customer interview** với online seller VN active trên Shopee/TikTok (recruit qua Facebook group, đổi **300k thẻ + 6 tháng Business tier free** / 30 phút phỏng vấn — sửa từ 100k v2.0 vì 100k dưới market rate cho seller có WTP cao).
2. **Landing page test:** Mock-up "Business tier $9/mo, P&L cho online seller" → đo signup rate.
3. **Beta concierge:** Với 5 Hùng+ early adopter, làm thủ công P&L cho họ qua Telegram chat trước khi build feature → validate có thật giúp ích không.
4. **Threshold go/no-go:** ≥3/5 beta concierge user nói "tôi sẽ trả $9/mo cho cái này" → green light build.

---

## 12. Go-to-market strategy

### 12.1. Channel hypothesis theo persona

Cấu trúc 2 funnel khác nhau cho 2 nhóm persona:

**Funnel A — Minh/Linh (Free + Pro target, volume play):**

| Channel | Cost expectation | Test ưu tiên | Hypothesis |
|---------|-----|----|---|
| Telegram channel/group post (organic) | $0 | Tuần 1-2 sau launch | Founder post lên Telegram VN groups (lập trình, freelancer, dev VN) — tự nhiên reach 1k-5k impression |
| Discord server post (organic) | $0 | Tuần 1-2 sau launch | Post lên Discord VN servers (dev, gaming, MMO, tech) — overlap lớn với Hùng+ dropshipper segment |
| Reddit r/vietnam, r/Vietnamese | $0 | Tuần 2-4 | Story-format post "Tôi build tracker bot tự dùng → giờ open" — convert tốt với tech-savvy audience |
| Content marketing SEO (blog Vietnamese) | $50-100/tháng (hosting blog) | Tháng 2-3 | "Cách track chi tiêu tự động bằng Telegram", "Bot tracking thay Money Lover" — long-tail SEO |
| Friend referral | $0 | Tuần 1 | Nhờ 5-10 người trong network test, organic word-of-mouth |
| Facebook ads (small test) | $50-100 cho 30 ngày | Tháng 3-4 | Target dev VN 24-35 tuổi, interest "Telegram, productivity" |

**Funnel B — Hùng+ (Business target, high-WTP play):**

Đây là funnel **quan trọng hơn** vì revenue/user gấp 2.25x Pro. Cần đầu tư riêng. **MVP đã cover full Hùng+ TAM** (3-path onboarding) → Funnel B không bị giới hạn ở "Hùng+ đã có SePay" như v2.2.

| Channel | Cost expectation | Test ưu tiên | Hypothesis |
|---------|-----|----|---|
| Facebook group online seller VN | $0 + 5-10h/tuần engagement | Tuần 1-4 | Active groups: "Cộng đồng bán hàng online", "Shopee Sellers VN", "TikTok Shop VN", "Cộng đồng MMO Việt Nam". Founder share value content (vd "Cách tính lãi shop trong 30s") trước khi pitch |
| Content "P&L cho online seller" (blog + TikTok video) | $0-100/tháng | Tháng 1-3 | Pain-driven content. Highlight 3-path onboarding (vd "Không cần SePay vẫn dùng được — chỉ forward email bank") để reach 50-60% Hùng+ chưa có SePay |
| Partnership SePay co-marketing | $0 (revenue share) | Tháng 4-6 | Nếu SePay không compete: proposal co-market — SePay user nhận Tiền Về Nơi Đâu Pro 1 tháng free, Tiền Về Nơi Đâu share 20-30% revenue back |
| KOL micro-influencer seller community | $200-500 per post | Tháng 5-6 | Tìm seller 5-50k follower trên Facebook/TikTok, deal swap (free Business tier 1 năm cho 1 review post) |
| Direct outreach DM Hùng+ | $0 + time | Tháng 1-3 | Tìm seller active comment trong group → DM offer beta concierge (free P&L manual 1 tháng) |
| **Email-only seller targeting** | $0 | Tháng 2-3 | Target audience không quen tech: "Bạn nhận email báo giao dịch từ ngân hàng? Forward về bot, có ngay báo cáo." Đây là segment ít competitor đụng vì cần email parsing — Tiền Về Nơi Đâu có moat |

### 12.2. CAC budget theo phase

| Phase | Tổng CAC budget | CAC target/user (paying) | Lý do |
|---|---|---|---|
| Beta (0-30 users) | $0 | $0 | All organic + network |
| Soft launch (30-100 users) | $100-200 | $5-10 | Test 2-3 channel, learn what works |
| Growth (100-500 users) | $1500-3000 | $5-12 | Scale channel hiệu quả nhất từ phase trước |

**LTV check:** Pro LTV = $57 (churn 7%), Business LTV = $129. CAC dưới $50 cho Pro, dưới $100 cho Business để có LTV/CAC > 1.3x (healthy minimum).

### 12.3. Acquisition funnel by tier

**Free tier funnel:**
```
Awareness (content/group post) → Click landing → Telegram bot start
→ Onboarding (5-15 phút) → Day 1 first transaction → Day 7 activated
```

**Free → Pro upgrade trigger:** Tự động trong bot khi hit limit (đã spec section 5.2.3).

**Free → Business funnel cho Hùng+:**
```
Awareness (seller community content) → Click "Business demo" landing
→ Schedule 30-min call HOẶC self-serve trial → Day 1 setup multi-bank
→ Day 7 first P&L view → Day 14 trial end → Upgrade Business
```

### 12.4. Channel test plan 90 ngày sau MVP launch

| Tuần | Activity | Decision point |
|---|---|---|
| 1-2 | Launch organic: Telegram groups + FB seller groups + friend referral | Đo: signup rate, Free→trial conversion |
| 3-4 | Add: Reddit posts + content blog (2 posts/tuần) | Compare CAC organic vs paid baseline |
| 5-8 | Test FB ads $100 budget: target Minh persona (dev VN) | Đo: CAC paid Pro |
| 9-12 | Test KOL micro-influencer: 2-3 deals seller community | Đo: CAC paid Business |
| Tuần 13 | **Decision:** Double down channel có CAC/LTV > 1.5x, kill channel < 1x |

### 12.5. Risks & mitigation GTM

| Risk | Mức độ | Mitigation |
|------|------|---|
| Hùng+ không sống trên Telegram (chỉ Facebook/Zalo) | Trung bình (giảm từ Cao) | Discord là co-primary platform mở rộng reach. Zalo/Messenger coming soon Phase 3+ |
| FB group ban tự promote | Trung bình | Build relationship trước, value-first content. Hoặc partner với group admin |
| Seller community VN bão hòa với "tool quản lý" pitch | Trung bình | Differentiation: "không phải accounting, không phải POS — là P&L cho người không phải kế toán" |
| Content marketing slow ramp | Cao (cho expectation tháng 1-3) | Không rely vào content cho 100 users đầu — content là long-term play |
| Paid ads VN có CAC cao bất thường | Trung bình | Cap budget $100-200 trong test, không scale nếu CAC > $30 |

### 12.6. Quick wins ngay tuần 1 sau launch

5 việc nên làm tuần đầu, ít cost cao impact:

1. Post lên 5-10 Telegram groups VN + 5-10 Discord servers VN (lập trình, dev, freelancer, indie maker, MMO)
2. Post Reddit r/vietnam với story format (không pitch, chỉ chia sẻ)
3. DM 20-30 friend trong network: "Test bot tracking chi tiêu, 1 tháng Pro free"
4. Join 5 Facebook seller group lớn nhất, comment value (không promote ngay)
5. Submit Product Hunt — niche launch (không big launch, just visibility)

→ Target tuần 1: 30-50 signup, 10-15 active user.

---

## Appendix

### A. Glossary

| Term | Definition |
|------|-----------|
| Workspace | Tenant boundary chứa data, settings, channel/source connections của 1 user |
| Channel Identity | User identity trên platform: Telegram (chat_id), Discord (user_id) |
| Source Connector | SePay webhook hoặc email forwarding ingest transaction |
| Canonical Transaction | Schema chuẩn hoá internal cho mọi loại event tài chính |
| Tracking-only | Mode categorize + report, không có budget limit |
| Entity Type | Tag personal / business / unknown của 1 transaction (Business tier) |
| WTP | Willingness to Pay |
| TAM | Total Addressable Market |

### B. References

| Tài liệu | Link |
|------|---|
| Current self-hosted repo | `/Users/maingocanh/Projects/Bot Finance` |
| README | `/Users/maingocanh/Projects/Bot Finance/README.md` |
| Feature spec — Personal vs Business toggle | `fintrack-feature-spec-personal-vs-business-toggle.md` |
| Pricing redesign deep-dive | `fintrack-brd-section-5.1-5.2-revised.md` |
| Cost projection deep-dive | `fintrack-brd-section-5.3-revised.md` |
| Persona Hùng+ deep-dive | `fintrack-brd-section-3-business-persona.md` |

### C. Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial BRD |
| v2.0.0 | 2026-05-05 | **Major revision:** Persona Hùng+ deep-dive (3.3); pricing 3-tier với Free 45 tx + Business $9 (5.1-5.2); cost projection sửa với Railway actual rates $10-15/mo cho 100 users (5.3); break-even tính lại (5.4); MRR target tăng $150-450 (2.2); timeline mở 4-5 tuần → 8-10 tuần (8); validation plan cho Business tier (11). |
| v2.1.0 | 2026-05-05 | **Critical fixes from review:** (1) Margin analysis tách rõ "infrastructure margin" vs "business margin" — Section 5.4.3 nói rõ profit chỉ valid khi không tính founder support time. (2) Section 6 viết lại với Money Lover pricing đúng — Money Lover Premium $24.49 one-time (không phải $4/năm), competitor thực sự là **Money Lover + Linked Wallet** (auto-capture subscription ~$3-5/mo). Tiền Về Nơi Đâu Pro **gần ngang** Money Lover Linked Wallet về 5-year TCO, không phải "9x đắt hơn". Differentiation thực: Telegram-native + Personal/Business split + SePay-first. |
| v2.2.0 | 2026-05-05 | **Round 2 critical fixes + new sections:** (3) Risk 5 Business tier failure nâng Medium → **Cao**, thêm backup plan nếu Business tier fail (hạ MRR target xuống $250-300). (4) Churn 7%/tháng modeled vào revenue projection — MRR steady-state ở 500 users là $427 (không phải $460), LTV Pro $57. (5) Sửa SePay assumption — chỉ 40-50% Hùng+ có sẵn SePay, 50-60% chưa có → onboarding cần 2 path (quick setup vs SePay setup wizard). (6) Section 12 mới — **GTM strategy** với 2 funnel separate cho Minh/Linh (volume) vs Hùng+ (high-WTP), CAC budget $5-12/paying user, channel test plan 90 ngày, 5 quick wins tuần 1. |
| v2.3.0 | 2026-05-05 | **MAJOR SCOPE EXPAND — Combine B+C:** Email parsing + SePay onboarding wizard ĐÃ vào MVP scope (không còn defer Phase 2). MVP serve full Hùng+ TAM ngay launch với 3 entry path: (a) SePay quick connect, (b) SePay setup wizard, (c) Email forwarding parsing initially planned as 5 banks. Trade-off: **timeline 14-16 tuần** (vs 8-10), **cost @ 100 users $22-27** (vs $12-17), **break-even 7%** (vs 4%), **launch tháng 9/2026** (vs 7-8). Thêm Risk 1b/1c/1d cho email parser. Phase 2 giữ Business tier features bundle. Section 12 Funnel B thêm channel "email-only seller targeting" — segment ít competitor đụng vì cần email parsing infrastructure. Superseded by v2.5 bank list. |
| v2.3.1 | 2026-05-05 | **Important fixes from review:** (6) Section 1.3 — claims đánh dấu rõ "working hypothesis" cần validate, không phải fact. Add validation threshold ≥4/7 interview confirm pain. (9) Section 10 success criteria — restructure thành 4 group (functional, reliability, cost, onboarding). Thêm: backup recovery test phải pass, email parser accuracy ≥85%/bank, onboarding time targets per path. |
| v2.4.0 | 2026-05-05 | **Sync với PRD v1.1.0 — product decisions:** (1) Annual pricing đổi từ Pro 25% / Business 22% → **20% off cho cả 2 tier** (Pro $38.40/yr, Business $86.40/yr). (2) Email forwarding mở cho **Free tier** (1 source) — trước đây Free = ❌. Free vẫn cap 45 tx/tháng nên không phá pricing differentiation. Mục đích: cover full Hùng+ TAM (50-60% chưa có SePay) ngay từ Free, tăng top-of-funnel cho conversion Free→Pro. (3) Categories Free đổi từ "5 default + 3 custom = 8 total" → "**5 total** (3 default auto-create + 2 custom)" — đơn giản hóa mental model, ép user prioritize categories quan trọng nhất. Section 4.1 #14 + 5.1 + 10 + 19 update theo. |
| v2.5.0 | 2026-05-05 | **Email + Payment + SePay cost update:** (1) Pro email sources: 1 → **3** (Free=1, Pro=3, Business=unlimited). (2) Thêm **SePay cost disclaimer**: user tự trả chi phí gói SePay, Tiền Về Nơi Đâu không cover. (3) Email parser banks mở rộng: MVP 5 → **6 banks** (TCB, Cake, ACB, STB, BIDV, MB) + Tier 2 Phase 2 (VCB, VietinBank, TPBank, VPBank, HDBank, Agribank) + Tier 3 on-demand (11 banks). VCB chuyển từ MVP → Phase 2 (chưa confirm email notification support). (4) Payment methods: PayOS + Stripe → **Bank transfer (0%) + PayPal (~4.4%) + USDT (~0%)**. Blended fee giảm từ ~1.8% → ~1.5%. |
| v2.6.0 | 2026-05-05 | **Bot architecture decision + refactor work spec:** (1) Section 1.6 mới — **Bot ownership model**: 1 shared bot platform-owned. Document trade-off vs BYO bot và hybrid, reject cả 2 alternative. Operational implications: BOT_TOKEN_BACKUP, rate limit, token rotation. (2) Cross-ref tới PRD section 5.4.2 cho bot pool roadmap (1 bot → pool 2-5 → Local Bot API server). (3) Cross-ref tới feature spec mới `feature-spec-refactor-saas.md` cho Phase 1-2 refactor work (rewrite từ personal single-tenant → SaaS multi-tenant). |
| v2.7.0 | 2026-05-05 | **Payment auto-detect mechanism spec:** (1) §5.2.4 expanded — Bank transfer **primary với auto-detect** qua SePay (≤60s) + Email backup (≤5min), 4-layer fuzzy matching, ref format `PAY-{user_id}-{plan}-{period}-{nonce4}`. PayPal/USDT defer Phase 2. (2) Recurring billing logic: monthly reminder 3d trước expiry + grace 7d, annual reminder 14+3+1d. (3) **Pre-launch blocker flagged**: hộ kinh doanh registration phải hoàn tất trước Phase 6 deploy (lead time 1-2 tuần). (4) Cross-ref tới `feature-spec-payment-bank-transfer.md` cho 4-layer algorithm, 14 edge cases, tax/compliance checklist, effort estimate 8-12 ngày dev. |
| v2.7.1 | 2026-05-05 | **Phase 6 timeline wording fix:** Phase 6 deliverable đổi từ "bank transfer/manual verification MVP" → "bank transfer auto-detect via SePay primary + Email backup; manual review fallback" để consistent với §5.2.4 + feature spec. Phase 6 risk wording cũng sync. Không thay đổi scope. |
| v2.7.2 | 2026-05-06 | **Timeline expand cho admin tools + observability scope (sync implementation-plan-500-users-and-more.md):** (1) Phase 6 mở rộng tuần 10-11 → **tuần 10-12** (3 tuần) để fit 14-20 ngày work: payment integration + admin tools commands + observability dashboard. (2) Phase 7 dịch tuần 13-14, Phase 8 dịch tuần 15-16 (buffer absorbed). Tổng timeline vẫn 16 tuần. (3) Phase 1-2 deliverable thêm: `admin_audit_log` table + `messenger.send()` interface abstraction + admin auth framework — foundation cho admin tools sau này. (4) Pre-Phase 1 task: viết 3 spec critical: `feature-spec-admin-tools.md`, `runbooks/disaster-recovery.md`, `observability-plan.md`. |
| v2.8.0 | 2026-05-06 | **Sync với 3 spec mới (admin-tools v1.1.0, DR runbook v1.1.0, observability v1.1.0) + implementation plan v1.2.0:** (1) **§7 risk register expanded** từ 10 → 14 risks: thêm Risk 11 (abuse/spam attacks — DR §8c playbook), Risk 12 (founder support burnout @ 200+ — C1 automation must ship trước 250), Risk 13 (Telegram bot suspended — BOT_TOKEN_BACKUP + @TienVeNoiDauUpdates channel), Risk 14 (cost burn > revenue valley of death 100-300 users — cost dashboard + error budget). Risk 9 PDPA + Risk 10 scale cross-ref tới implementation plan §C4 + §5b. (2) **§10 success criteria** expanded thành 5 groups: Functional (+admin tools commands /admin_help auto-gen, rate limit 30/min, /admin_cost; +@TienVeNoiDauUpdates channel), Reliability (+error budget 0.1% rolling 30-day, +7 critical alerts armed, +PLATFORM_TOKEN silence monitoring), Cost (+cost dashboard, +margin >50% sustained), Onboarding (giữ), **Operational readiness mới** (DR runbook 8 scenarios, B2 password manager, SSE-B2 encryption, pg_dumpall globals, trusted contact briefed). (3) No scope/timeline change — tất cả là spec consolidation. |
| v2.9.0 | 2026-05-07 | **Multi-platform strategy update — Telegram + Discord first, Zalo & Messenger coming soon:** (1) **Platform priority thay đổi**: MVP build cho **Telegram + Discord** (co-primary), Zalo & Messenger defer Phase 3+ (coming soon). Discord thêm vào MVP vì bot API mature, slash commands, VN gaming/MMO/tech community overlap lớn với Hùng+ dropshipper segment, cùng codebase qua `messenger.send()` abstraction. (2) **§1.6 Bot ownership** expanded: platform priority table, `DISCORD_BOT_TOKEN` env, multi-platform giảm SPOF risk (1 platform down → platform kia vẫn hoạt động). (3) **§2.2** mục tiêu trung hạn: Platform mở rộng = Zalo/Messenger (coming soon), không còn là platform #2. (4) **§4.3 Phase 3+** thêm Status column: Zalo OA + Messenger = 🔜 Coming soon. (5) **§7 Risk 2** Telegram block giảm xuống Thấp vì Discord là co-primary fallback. (6) **§8 Phase 1-2** deliverables thêm Discord adapter. (7) **§12 GTM** thêm Discord server organic channel, risk Hùng+ giảm Cao → Trung bình. (8) Glossary Channel Identity cập nhật cho multi-platform. |
| v3.0.0 | 2026-05-07 | **MAJOR PRICING REVISION — VN market pricing:** (1) **Pricing đổi từ USD sang VND-first**: Pro $4 (100k VND) → **79k VND (~$3.16)**, Business $9 (220k VND) → **199k VND (~$7.96)**. Lý do: đặt dưới ngưỡng tâm lý VN (79k < 100k, 199k < 200k) để maximize conversion trong price-sensitive market. (2) **Revenue projection recalculated** với conservative 5% paid (4% Pro + 1% Business): @100 users = 515k VND ($20.60)/mo, @500 users = 2,575k VND ($103)/mo. (3) **Break-even dịch lên ~150-200 users** (vs ~50-100 trước). @100 users lỗ ~$4.40/mo — founder subsidize. (4) **LTV giảm**: Pro $45 (vs $57), Business $114 (vs $129). CAC payback < $15-25. (5) **MRR target hạ**: $100-300 (vs $150-450). (6) **Competitive positioning mạnh hơn**: Pro 758k/năm rẻ hơn 17-50% so với Money Lover Linked Wallet. Business 199k dưới ngưỡng 200k tâm lý. (7) **WTP anchor updated**: VND-denominated (50-300k range). (8) **Annual plan**: Pro 758k/năm, Business 1.91tr/năm (20% off giữ nguyên). Trade-off: margin mỏng hơn nhưng conversion volume play cho VN market. |
| v3.1.0 | 2026-05-07 | **NEW MVP FEATURE — Auto-categorization rule-based:** (1) **§4.1 #9 mới**: Auto-categorization theo nội dung giao dịch (description matching). Platform cung cấp **default rules** cho VN phổ biến (SHOPEE, GRAB, LAZADA, TIKI, VIETTEL, FPT, ĐIỆN, NƯỚC...). User tạo **custom rules** (keyword → category mapping). Khi match → auto-categorize + notify, không hỏi. User override bất kỳ lúc nào. (2) **Tier gating**: Free = system defaults only, Pro = +10 custom rules, Business = unlimited custom rules. (3) **§4.1 #8 sửa**: Transaction categorization giờ là manual fallback khi không match rule. (4) **§4.1 #15 sửa**: Free tier limits thêm "system default rules only". (5) **§4.1 #20 mới**: Pro custom auto-cat rules (10 rules). (6) **§4.3 sửa**: "Auto-categorization ML-based" → "Auto-categorization **ML upgrade**" — nâng cấp rule-based → ML model, supplement không replace. (7) **§5.1 pricing table** thêm row Auto-categorization rules. (8) Sync `brd-en.md` + `pricing-redesign.md`. |

---

**End of Document**
