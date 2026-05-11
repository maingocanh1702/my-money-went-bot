# Nghiên Cứu Chi Tiết Ứng Dụng Money Lover (2025-2026)

**Ngày nghiên cứu:** 07 Tháng 5, 2026
**Nguồn:** moneylover.me, App Store, Google Play, MoneyLover Support Center

---

## 1. Mô Hình Giá Cả (Pricing)

### 1.1 Gói Miễn Phí (Basic)
- 1 ví tiền mặt
- 1 ngân sách / 1 kế hoạch tiết kiệm / 1 sự kiện
- 1 giao dịch định kỳ / 1 hóa đơn
- Đồng bộ tối đa 5 thiết bị
- Truy cập web app
- **Không có**: xuất CSV, đính kèm ảnh, có quảng cáo

### 1.2 Gói Premium
- **Giá tham khảo (VN market):**
  - Hàng tháng: ~25,000 VND (~$1/mo)
  - Hàng năm: ~149,000 VND (~$6/yr)
  - Lifetime: ~499,000 VND (~$20 one-time)
- **Gói Premium cao cấp (Money Lover Pro):**
  - Hàng năm: ~1,000,000 VND/năm (~$40/yr)
  - Bao gồm Linked Wallet (bank sync)

### 1.3 Tính năng Premium
- Ví tiền mặt không giới hạn
- Ngân sách, tiết kiệm, sự kiện, giao dịch định kỳ không giới hạn
- Đồng bộ thiết bị không giới hạn
- Xuất CSV / Google Sheets
- Đính kèm ảnh hóa đơn vào giao dịch
- Không quảng cáo

### 1.4 Linked Wallet (Add-on riêng)
- **Là gói đăng ký riêng biệt**, không nằm trong Premium cơ bản
- Tự động đồng bộ lịch sử giao dịch ngân hàng với tài khoản MoneyLover
- Sử dụng Salt Edge làm aggregator
- **Giá:** ~350,000 VND/năm (~$14/yr) hoặc ~29,000 VND/tháng (~$1.15/mo)
- **Lý do tách riêng:** Salt Edge thu phí per-user hàng tháng → Money Lover không thể gộp vào gói Lifetime

---

## 2. Nguyên Tắc Hoạt Động

### 2.1 Luồng UX Cốt Lõi
1. Tải app → đăng ký → tạo ví tiền mặt đầu tiên
2. Nhập giao dịch: **manual** (chủ yếu), hoặc **auto** (Linked Wallet)
3. Phân loại giao dịch theo danh mục (ăn uống, đi lại, mua sắm,...)
4. Thiết lập ngân sách → theo dõi → nhận báo cáo

### 2.2 Phương thức nhập giao dịch
- **Thủ công (Manual)**: Nhập tay — phương thức chính cho đa số user
- **Linked Wallet (Bank Sync)**: Qua Salt Edge, tự động import giao dịch ngân hàng
  - Hỗ trợ nhiều quốc gia nhưng **kết nối Mỹ khá tệ** (Salt Edge yếu ở US)
  - Kết nối ngân hàng VN: limited (không realtime, phụ thuộc Salt Edge coverage)
- **OCR**: Không có tính năng OCR/scan hóa đơn tự động

### 2.3 Hệ thống ví (Wallet System)
- Cash Wallet: ví tiền mặt (free: 1, premium: unlimited)
- Linked Wallet: ví liên kết ngân hàng (add-on riêng)
- Mỗi ví có currency riêng → hỗ trợ đa tiền tệ

### 2.4 Tính năng khác
- Danh mục chi tiêu tùy chỉnh (categories)
- Ngân sách theo danh mục/thời gian
- Kế hoạch tiết kiệm (saving goals)
- Quản lý nợ & cho vay (debt/loan)
- Giao dịch định kỳ (recurring transactions)
- Báo cáo chi tiêu (pie chart, bar chart, trend)
- Hỗ trợ đa tiền tệ với tỷ giá live
- Travel Mode (chuyển đổi tiền tệ khi đi du lịch)

---

## 3. Mô Hình Kinh Doanh

### 3.1 Nguồn doanh thu
1. **Premium subscription**: Gói chính (monthly/annual/lifetime)
2. **Linked Wallet subscription**: Gói add-on bank sync (monthly/annual)
3. **Quảng cáo**: Hiển thị trong gói miễn phí

### 3.2 Chiến lược monetization
- **Freemium rộng**: Free tier đủ dùng cho tracking cơ bản → thu hút lượng lớn user
- **Lifetime option**: Tạo perceived value cao cho premium cơ bản (~$20 one-time)
- **Bank sync tách riêng**: Do chi phí Salt Edge per-user → phải subscription riêng
- **Hệ quả**: User phải trả cả Premium + Linked Wallet = đắt hơn so với impression ban đầu

### 3.3 Đối tác kỹ thuật
- **Salt Edge**: Data aggregator duy nhất, cover 5,000+ ngân hàng ở 50+ quốc gia
- **Lý do chọn Salt Edge**: User base phân tán từ VN, SEA, EU → Salt Edge là bên duy nhất "ôm" được hết
- **Nhược điểm**: Salt Edge kết nối ở Mỹ kém → mất thị phần US

---

## 4. Tính Năng Nổi Bật & Differentiators

### 4.1 Điểm mạnh
- **#1 VN market**: ~5M+ downloads, app tài chính phổ biến nhất VN
- **Giao diện đơn giản**: Dễ dùng, UX clean, phù hợp mass market
- **Đa nền tảng**: iOS, Android, Web
- **Lifetime option**: Hấp dẫn cho user không muốn subscription
- **Đa tiền tệ**: Exchange rate live, Travel Mode
- **Chia sẻ ví**: Cho phép chia sẻ ví với người khác (vợ/chồng, bạn bè)

### 4.2 Điểm yếu / Complaints phổ biến
- Bank sync (Linked Wallet) là add-on riêng, không realtime
- **Không có auto-capture giao dịch VN bank** ở base price
- Phân loại giao dịch thủ công (không có AI categorization mạnh)
- Premium lifetime vẫn thiếu nhiều feature (Linked Wallet, Money Insider)
- Một số user phàn nàn về bugs, sync chậm giữa devices
- Báo cáo cơ bản, thiếu insights nâng cao
- Không có tính năng đầu tư / net worth tracking

---

## 5. Thông Tin Thị Trường

### 5.1 User base
- **Downloads**: 5M+ (Google Play + App Store)
- **Rating**: 4.9 sao, 100,000+ đánh giá 5 sao
- **Thị trường chính**: Việt Nam, Đông Nam Á, một phần EU
- **"App of the Day"** recognition trên App Store

### 5.2 Định vị
- Mass-market expense tracker giá rẻ
- Đối thủ trực tiếp: MISA Sổ Thu Chi (VN), 1Money (SEA)
- **Không** cạnh tranh trực tiếp với YNAB/Monarch (khác segment hoàn toàn)

---

## 6. So Sánh Với Tiền Về Nơi Đâu (MyMoneyWent)

| Yếu tố | Money Lover | Tiền Về Nơi Đâu |
|---------|-------------|----------|
| Auto bank sync VN | ❌ (Linked Wallet add-on, qua Salt Edge) | ✅ SePay realtime |
| Giá bank sync | ~350k VND/năm extra | Included trong Pro $4/mo |
| Free tier | Rộng, đủ dùng | 45 tx/mo, 1 bank |
| Lifetime | ✅ ~500k VND (không có bank sync) | ❌ |
| P&L Business | ❌ | ✅ (Business tier) |
| AI categorization | ❌ | Có thể develop |
| Market position | Incumbent #1 VN | Challenger, niche auto-tracking |

### Key insight
Money Lover Pro ($40/yr) với Linked Wallet inclusive là đối thủ pricing gần nhất của Tiền Về Nơi Đâu Pro ($36/yr). Nhưng Tiền Về Nơi Đâu có **SePay realtime** — không app VN nào làm được ở giá < $5/mo.
