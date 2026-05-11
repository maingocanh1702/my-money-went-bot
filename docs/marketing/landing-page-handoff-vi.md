# Tiền Về Nơi Đâu — Landing Page Handoff (VN)

> **Domain:** `tienvenoidau.com`
> **Ngôn ngữ:** Tiếng Việt
> **Currency:** VND
> **Nguồn:** `brd-vi.md` v3.1.0
> **Cập nhật:** 2026-05-07

---

## 1. Branding

| Thuộc tính | Giá trị |
|---|---|
| **Tên sản phẩm** | Tiền Về Nơi Đâu |
| **Domain** | `tienvenoidau.com` |
| **Tagline chính** | Giao dịch xảy ra — Bot tự động phân loại — Báo cáo tự có |
| **Tagline phụ (A/B test)** | "Tiền đi đâu? Bot biết hết." / "Quản lý tài chính không cần mở app" |
| **Elevator pitch** | Bot Telegram & Discord tự động theo dõi mọi giao dịch ngân hàng, phân loại chi tiêu, và tạo báo cáo tài chính — không cần nhập tay, không cần mở app. |

---

## 2. Hero Section

| Thuộc tính | Nội dung |
|---|---|
| **Headline** | Tự động theo dõi tiền — Ngay trong Telegram và nhiều ứng dụng khác |
| **Subheadline** | Kết nối ngân hàng → Bot nhận giao dịch → Tự động phân loại → Báo cáo real-time. Setup 2 phút. Miễn phí. |
| **CTA chính** | "Bắt đầu miễn phí" → link tới Telegram bot |
| **CTA phụ** | "Xem cách hoạt động" → scroll tới How It Works |
| **Visual** | Chat bubble mockup — show 1 giao dịch vào bot → bot tự động phân loại, no need to click button |

**Social proof (hiển thị khi có data):**
- "X giao dịch đã được xử lý" (live counter từ DB)
- "Y người đang dùng Tiền Về Nơi Đâu"

---

## 3. Pain Points Section

**Section heading:** "Bạn có gặp vấn đề này không?"

### 3.1. Cho cá nhân

| # | Icon | Pain point | Copy |
|---|---|---|---|
| 1 | 😩 | Không biết tiền đi đâu | "Cuối tháng nhìn tài khoản: Tiền đâu hết rồi?" |
| 2 | 📱 | App nhập tay rồi bỏ | "Tải app quản lý chi tiêu, nhập tay 3 ngày rồi quên. Ai cũng vậy." |
| 3 | 📉 | Thu nhập bất ổn | "Freelancer: tháng 40 triệu, tháng 8 triệu — không biết khi nào hết tiền" |

### 3.2. Cho chủ shop / online seller

| # | Icon | Pain point | Copy |
|---|---|---|---|
| 1 | 💸 | Không tách được tiền shop vs cá nhân | "Tiền shop và tiền nhà lẫn lộn — không biết shop lãi thật bao nhiêu" |
| 2 | 📊 | Mất 4-6 tiếng cuối tháng cộng Excel | "Mất 4 tiếng cộng Excel mà vẫn sai số 2-3 triệu. Tháng nào cũng vậy." |
| 3 | 🏪 | 60-80 đơn/ngày, không thể nhập tay | "80 đơn/ngày — app nào nhập tay cho nổi?" |
| 4 | 🤷 | Không biết kênh nào lãi | "Chạy ads 3 sàn, trả tiền 3 đầu — không biết cái nào lãi nhất" |

---

## 4. How It Works Section

**Section heading:** "Cách hoạt động"

### 3 bước (layout: cards hoặc timeline)

| Bước | Icon | Headline | Mô tả | Note |
|---|---|---|---|---|
| 1 | 🔗 | **Kết nối trong 2 phút** | Không cần tải app mới. Mở bot Telegram, kết nối ngân hàng qua SePay hoặc email. Bot hướng dẫn từng bước. | 3 path: SePay quick (2'), SePay wizard (10'), Email forwarding (5') |
| 2 | 🤖 | **Bot tự phân loại** | Giao dịch từ SHOPEE, GRAB, tiền điện, nước... được tự động phân loại. Không match? Bot hỏi bạn bằng nút bấm — bấm 1 cái xong. | Auto-cat rule-based + manual fallback |
| 3 | 📊 | **Báo cáo ngay khi cần** | Gõ /today xem chi tiêu hôm nay. Gõ /status xem tổng tháng. Bot gửi tổng kết tự động mỗi tối — không cần làm gì. | Daily recap auto |

### Flow diagram (dùng cho illustration)

```
Giao dịch ngân hàng
       ↓
  SePay webhook / Email forward
       ↓
  Bot nhận & phân loại tự động
       ↓
  ┌─ Match rule → Auto-categorize + Notify
  └─ Không match → Hỏi user bằng nút bấm
       ↓
  Báo cáo cập nhật real-time
```

---

## 5. Features Section

**Section heading:** "Tính năng nổi bật"

### 5.1. Feature highlights (6 cards — grid layout)

| # | Icon | Feature | Mô tả ngắn |
|---|---|---|---|
| 1 | ⚡ | **Tự động capture** | Giao dịch ngân hàng tự động vào bot — không nhập tay, không sót |
| 2 | 🏷️ | **Phân loại thông minh** | Bot tự nhận diện SHOPEE, GRAB, tiền điện... và phân loại. Bạn tạo thêm rules riêng |
| 3 | 📊 | **Báo cáo real-time** | /today, /status, tổng kết cuối ngày tự động — biết tiền đi đâu bất kỳ lúc nào |
| 4 | 🏦 | **Nhiều ngân hàng** | Kết nối đến 3-5 tài khoản cùng lúc, tất cả về 1 chỗ |
| 5 | 💼 | **Tách shop / cá nhân** | Biết shop lãi bao nhiêu thật — tách riêng tiền shop và tiền nhà |
| 6 | 💬 | **Không cần app mới** | Hoạt động ngay trong Telegram & Discord — app bạn đã có sẵn |

### 5.2. Feature comparison table (section mở rộng dưới highlights)

| Tính năng | Free | Pro | Business |
|-----------|------|-----|----------|
| Tự động nhận giao dịch (SePay + Email) | ✅ | ✅ | ✅ |
| Phân loại bằng nút bấm | ✅ | ✅ | ✅ |
| Phân loại tự động (rules mặc định) | ✅ | ✅ | ✅ |
| Tạo rules phân loại riêng | ❌ | **10 rules** | **Không giới hạn** |
| Xem chi tiêu hôm nay (/today) | ✅ | ✅ | ✅ |
| Tổng kết tự động mỗi tối | ✅ | ✅ | ✅ |
| Tài khoản ngân hàng | 1 | 3 | 5 |
| Giao dịch / tháng | **45** | Không giới hạn | Không giới hạn |
| Lịch sử giao dịch | 30 ngày | Không giới hạn | Không giới hạn |
| Danh mục chi tiêu | 5 | 20 | Không giới hạn |
| Nguồn email parsing | 1 | 3 | Không giới hạn |
| Báo cáo tuần + tháng | ❌ | ✅ | ✅ |
| Xuất CSV | ❌ | ✅ | ✅ |
| Tách Cá nhân / Shop | ❌ | ❌ | ✅ |
| Báo cáo lãi/lỗ (P&L) | ❌ | ❌ | ✅ |
| Google Sheets sync | ❌ | ❌ | ✅ |
| Hỗ trợ ưu tiên | ❌ | ❌ | ✅ |

---

## 6. Pricing Section

**Section heading:** "Bảng giá"

### 6.1. Pricing cards (3 cards, Pro highlighted)

| | Free | Pro ⭐ | Business |
|---|---|---|---|
| **Badge** | — | "Phổ biến nhất" | "Cho chủ shop" |
| **Giá/tháng** | **0đ** | **79.000đ** | **199.000đ** |
| **Giá/năm** | — | **758.000đ** (tiết kiệm 20%) | **1.910.000đ** (tiết kiệm 20%) |
| **Dùng thử** | — | 14 ngày miễn phí | 14 ngày miễn phí |
| **CTA** | "Bắt đầu miễn phí" | "Dùng thử 14 ngày" | "Dùng thử 14 ngày" |
| **Highlight features** | 45 giao dịch/tháng, 1 bank | Unlimited giao dịch, 3 bank, report tuần/tháng | Tách shop/cá nhân, P&L, Sheets sync, 5 bank |

### 6.2. Copy dưới bảng giá

- "Bắt đầu miễn phí, upgrade khi cần. Mọi tài khoản mới đều được 14 ngày dùng thử Pro."
- "Hoàn tiền trong 7 ngày, không hỏi lý do."
- "Không cần thẻ tín dụng để bắt đầu."

---

## 7. Ai Nên Dùng Section

**Section heading:** "Dành cho ai?"

### 3 persona cards

| Icon | Tên | Mô tả | Pain quote | Gói phù hợp |
|---|---|---|---|---|
| 👨‍💼 | **Nhân viên văn phòng** | 24-35 tuổi, lương 10-25 triệu, 1 tài khoản bank | "Cuối tháng không hiểu tiền đi đâu hết" | Free → Pro |
| 👩‍💻 | **Freelancer** | 22-30 tuổi, thu nhập bất ổn 8-40 triệu | "Tháng nào đủ tiêu tháng nào thiếu, không biết" | Pro |
| 🛍️ | **Chủ shop online** | 28-42 tuổi, doanh thu 30-200 triệu, 2-3 tài khoản | "Shop lãi bao nhiêu thật sau khi trừ tiền tiêu cá nhân?" | Business |

---

## 8. So Sánh Section (optional)

**Section heading:** "So sánh với cách quản lý khác"

> ⚠️ **Lưu ý:** KHÔNG nêu tên cụ thể sản phẩm đối thủ. Dùng mô tả chung.

| | Tiền Về Nơi Đâu | App quản lý chi tiêu | Bảng tính thủ công | Kế toán dịch vụ |
|---|---|---|---|---|
| **Tự động capture** | ✅ Giao dịch tự vào bot | ❌ Phải nhập tay | ❌ Copy/paste statement | ❌ Gửi invoice cho kế toán |
| **Thời gian setup** | 2-5 phút | 10-20 phút | 0 phút (nhưng 4-6h/tháng duy trì) | 1-2 tuần |
| **Tách shop/cá nhân** | ✅ (gói Business) | ❌ | Thủ công, dễ sai | ✅ (manual, chậm) |
| **Cập nhật real-time** | ✅ | ✅ (nếu nhập tay kịp) | ❌ | ❌ (chậm 7-30 ngày) |
| **Chi phí** | Từ **0đ** | 50k-200k/năm | 0đ + thời gian | 300k-1tr/tháng |
| **Cần cài app mới** | ❌ Dùng Telegram | ✅ | ❌ | ❌ |
| **Effort hàng ngày** | 0 phút (tự động) | 5-15 phút/ngày nhập tay | 30-60 phút/ngày | 0 (nhưng chờ report) |

### Key differentiators (copy-ready bullets)

1. **Không cần app mới** — Hoạt động trong Telegram & Discord, app bạn đã có
2. **Tự động 100%** — Giao dịch vào, bot tự phân loại, report tự tạo
3. **Setup 2 phút** — Nhanh gấp 5-10 lần so với tải app mới + đăng ký + liên kết ngân hàng
4. **Tách shop vs cá nhân** — Tính năng duy nhất dành cho chủ shop nhỏ mà các app chi tiêu thông thường không có
5. **Rẻ hơn 60-84%** so với thuê kế toán — và cập nhật real-time

---

## 9. FAQ Section

**Section heading:** "Câu hỏi thường gặp"
**Layout:** Accordion (click to expand)

| # | Câu hỏi | Trả lời |
|---|---|---|
| 1 | **Dùng miễn phí được bao lâu?** | Mãi mãi. Gói Free giới hạn 45 giao dịch/tháng và 1 tài khoản ngân hàng. Đủ cho tracking cá nhân cơ bản. |
| 2 | **Cần cài app gì không?** | Không cần. Bạn chỉ cần Telegram hoặc Discord — mở bot và bắt đầu. |
| 3 | **Hỗ trợ ngân hàng nào?** | Mọi ngân hàng kết nối qua SePay (hầu hết bank VN). Ngoài ra hỗ trợ email parsing cho: Techcombank, Cake, ACB, Sacombank, BIDV, MB. Thêm ngân hàng dần. |
| 4 | **Dữ liệu có an toàn không?** | Bot KHÔNG truy cập tài khoản ngân hàng. Bot chỉ nhận thông báo giao dịch qua webhook hoặc email. Dữ liệu mã hóa, không lưu số tài khoản. |
| 5 | **14 ngày dùng thử hoạt động thế nào?** | Mọi user mới tự động được Pro 14 ngày, không cần thẻ. Sau 14 ngày tự động về Free, dữ liệu giữ nguyên. |
| 6 | **Hủy subscription thế nào?** | Gõ /cancel trong bot. Hoàn tiền trong 7 ngày đầu, không hỏi lý do. |
| 7 | **SePay là gì?** | SePay là dịch vụ webhook ngân hàng phổ biến ở VN — khi có giao dịch, SePay gửi thông báo real-time tới bot. Nếu chưa có SePay, bot hướng dẫn setup hoặc bạn dùng email forwarding thay thế. |
| 8 | **Không muốn dùng SePay?** | Dùng email forwarding: forward email thông báo giao dịch từ ngân hàng về bot. Không cần SePay. |
| 9 | **Tách tiền shop và cá nhân thế nào?** | Gói Business tự động tách theo tài khoản bank (bank A = shop, bank B = cá nhân). Hoặc tag thủ công cho từng giao dịch. |
| 10 | **Xuất cho kế toán được không?** | Được. Business sync real-time với Google Sheets. Pro xuất CSV. |

---

## 10. Platforms & Banks Section

### 10.1. Nền tảng hỗ trợ

| Platform | Status | Badge text |
|---|---|---|
| Telegram | ✅ Live | "Dùng trên Telegram" |
| Discord | ✅ Live | "Dùng trên Discord" |
| Zalo | 🔜 | "Sắp ra mắt" |
| Messenger | 🔜 | "Sắp ra mắt" |

### 10.2. Ngân hàng hỗ trợ (show logo)

**Email parsing trực tiếp:** Techcombank, Cake by VPBank, ACB, Sacombank, BIDV, MB Bank

**Qua SePay:** "Và hơn 30 ngân hàng VN khác" (show dòng text + SePay logo)

---

## 11. Trust & Footer

### 11.1. Trust signals (show dưới pricing hoặc trước CTA cuối)

- 🔒 "Dữ liệu mã hóa — Không truy cập tài khoản ngân hàng"
- 💰 "Hoàn tiền 7 ngày, không hỏi lý do"
- ⚡ "X giao dịch đã được xử lý" (live counter nếu có)

### 11.2. Final CTA Section

| Thuộc tính | Nội dung |
|---|---|
| **Headline** | Bắt đầu theo dõi tài chính tự động — Miễn phí |
| **Sub** | Setup 2 phút. Không cần tải app. Không cần thẻ tín dụng. |
| **CTA** | "Bắt đầu miễn phí trên Telegram" |

### 11.3. Footer links

- Điều khoản sử dụng
- Chính sách bảo mật
- Liên hệ / Hỗ trợ
- Blog (nếu có)

---

## 12. Page Layout

```
┌─────────────────────────────────────┐
│  NAV: Logo | Tính năng | Giá | FAQ  │
├─────────────────────────────────────┤
│  HERO: Headline + Sub + CTA        │
│        + Chat bubble mockup        │
├─────────────────────────────────────┤
│  PAIN POINTS: 3-4 cards            │
│  "Bạn có gặp vấn đề này không?"   │
├─────────────────────────────────────┤
│  HOW IT WORKS: 3 steps timeline    │
│  Kết nối → Bot phân loại → Report  │
├─────────────────────────────────────┤
│  FEATURES: 6 cards grid            │
├─────────────────────────────────────┤
│  PRICING: 3 tier cards             │
│  Free | Pro ⭐ | Business           │
├─────────────────────────────────────┤
│  FEATURE TABLE: Full comparison    │
├─────────────────────────────────────┤
│  WHO IS THIS FOR: 3 persona cards  │
├─────────────────────────────────────┤
│  VS ALTERNATIVES: Comparison table │
├─────────────────────────────────────┤
│  FAQ: Accordion                    │
├─────────────────────────────────────┤
│  FINAL CTA: "Bắt đầu miễn phí"    │
├─────────────────────────────────────┤
│  FOOTER: Trust + Links             │
└─────────────────────────────────────┘
```

---

## 13. Design Direction

### 13.1. Colors

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--primary` | `#2563EB` (blue-600) | CTA, links, accents |
| `--primary-hover` | `#1D4ED8` (blue-700) | Button hover |
| `--bg-hero` | `#0F172A` (slate-900) | Dark hero section |
| `--bg-body` | `#F8FAFC` (slate-50) | Light body |
| `--bg-card` | `#FFFFFF` | Feature/pricing cards |
| `--text-primary` | `#0F172A` | Body text |
| `--text-secondary` | `#64748B` | Sub text |
| `--accent-green` | `#10B981` | Income, success |
| `--accent-red` | `#EF4444` | Expense |
| `--accent-gold` | `#F59E0B` | Pro badge |
| `--accent-purple` | `#8B5CF6` | Business badge |

### 13.2. Typography

- **Font:** Inter hoặc Outfit (Google Fonts, hỗ trợ tiếng Việt tốt)
- **Headline:** 48-64px / bold
- **Subheadline:** 20-24px / regular
- **Body:** 16-18px / regular
- Test kỹ dấu tiếng Việt + chữ dài (vd "Không giới hạn")

### 13.3. Visual style

- Dark hero + light body
- Glassmorphism cho pricing cards
- Micro-animations: cards fade-in on scroll, CTA pulse, step counter animate
- Chat bubble mockup trong hero — show bot conversation flow thật
- Dùng icons + illustrations, không dùng stock photo

---

## 14. Technical

### 14.1. Links

| CTA | Link |
|---|---|
| Telegram bot | `https://t.me/TienVeNoiDauBot` |
| Discord bot | Discord OAuth invite link |

### 14.2. Analytics events

| Event | Trigger |
|---|---|
| `landing_hero_cta_click` | Click CTA hero |
| `landing_pricing_cta_click` | Click CTA pricing |
| `landing_faq_expand` | Mở FAQ item |
| `landing_comparison_view` | Scroll tới comparison |
| `landing_final_cta_click` | Click CTA cuối trang |

### 14.3. SEO

- **Title:** "Tiền Về Nơi Đâu — Bot tự động theo dõi tài chính qua Telegram"
- **Meta description:** "Quản lý chi tiêu tự động bằng bot Telegram. Kết nối ngân hàng, bot phân loại giao dịch, báo cáo real-time. Miễn phí."
- **H1:** Dùng headline hero (1 H1 duy nhất)
- **Semantic HTML:** header, main, section, footer

---

## 15. Assets cần chuẩn bị

| Item | Ai | Cần trước |
|---|---|---|
| Logo Tiền Về Nơi Đâu (SVG + PNG) | Designer | Build |
| Bot conversation screenshots / mockups | Designer | Build |
| Bank logos (TCB, ACB, BIDV, MB, Cake, STB) | Collect | Build |
| Telegram & Discord icons | Standard | Build |
| Privacy Policy | Founder / Legal | Launch |
| Terms of Service | Founder / Legal | Launch |
| Testimonials | Founder (post-beta) | Post-launch |
