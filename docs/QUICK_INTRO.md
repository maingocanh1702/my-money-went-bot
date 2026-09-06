# My Money Went Bot

![My Money Went Bot — automatic transaction tracking for Vietnamese bank accounts and credit cards, written to a Google Sheet you own and categorized from Telegram or Zalo](screenshots/banner.png)

[English](../README.md) | [Tiếng Việt](../README.vi.md) | [Setup bằng AI](AI_SETUP.md)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Channel-Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Backend-Google%20Sheets-34A853?style=for-the-badge&logo=googlesheets&logoColor=white)
![SePay](https://img.shields.io/badge/Bank%20Webhook-SePay-0F172A?style=for-the-badge)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-D4A017?style=for-the-badge)

# My Money Went Bot - tự động theo dõi giao dịch thẻ và ngân hàng, ngay trong Telegram

Bot tự ghi mọi giao dịch **thẻ tín dụng** và **tài khoản ngân hàng Việt Nam** vào Google Sheet của bạn, hỏi bạn phân loại bằng nút bấm (hoặc tự phân loại nếu đã có keyword rule), rồi báo cáo theo ngày, tuần, tháng, quý, năm. Trên nền đó có thêm ngân sách theo danh mục, dư nợ thẻ, và theo dõi cashback.

---

## Bạn đang gặp vấn đề này?

- Muốn biết tiền đi đâu nhưng lười nhập tay từng khoản.
- Giao dịch thẻ tín dụng nằm một nơi, giao dịch ngân hàng nằm một nơi, cuối tháng không cộng lại được.
- Có thẻ cashback nhưng chỉ biết được hoàn bao nhiêu khi ngân hàng chốt sao kê.
- App quản lý chi tiêu bắt đăng nhập ngân hàng hoặc giữ data trên cloud của họ.
- Sao kê ngân hàng khó đọc, khó phân loại, khó xem theo account/category.
- Google Sheet linh hoạt nhưng cập nhật thủ công quá mệt.
- Giao dịch lặp lại như Grab, Spotify, Bách Hóa Xanh cứ phải phân loại lại nhiều lần.

## Bot này làm gì?

My Money Went Bot nối những thứ bạn đã dùng:

```text
Tài khoản ngân hàng  ── SePay webhook ─────────────┐
                                                   ├─> Bot (Telegram / Zalo) ─> Google Sheet của bạn
Thẻ tín dụng / bank ── email thông báo ─ Apps Script ┘        └─ cashback engine: MCC · rate · cap · cổng
```

Với tài khoản ngân hàng, SePay nhận thông báo từ ngân hàng và gửi webhook cho bot. Gói Free của SePay là 0đ với 50 giao dịch/tháng; vượt thì tính phí phần vượt hoặc lên gói trả phí — xem [bảng giá SePay](https://sepay.vn/bang-gia.html).

Với thẻ tín dụng, bot đọc chính email thông báo mà ngân hàng gửi cho bạn — cách này cũng phủ luôn ngân hàng nào SePay chưa hỗ trợ, và không tốn phí.

Vì bot đã thấy mọi lần quẹt, nó tính luôn được cashback: mỗi lần quẹt trả lời ngay được hoàn bao nhiêu, `/cashback` cho thấy cả kỳ sao kê. Rule của từng thẻ là file YAML trong `card_templates/` — thêm thẻ khác chỉ cần thêm một file, không sửa code.

Điểm quan trọng: **My Money Went Bot không truy cập tài khoản ngân hàng của bạn.** Bot không đăng nhập ngân hàng, không đọc biến động số dư trực tiếp, không truy vấn lịch sử giao dịch, và không giữ username/password/OTP/số thẻ. Bot chỉ nhận dữ liệu giao dịch mà **SePay gửi qua webhook** sau khi bạn tự cấu hình SePay — hoặc, với thẻ tín dụng, **email thông báo** mà Google Apps Script của bạn chuyển tới từ Gmail của chính bạn.

**SePay** là công ty hạ tầng Open Banking tại Việt Nam, cung cấp API ngân hàng và giải pháp tự động hóa dòng tiền. SePay là bên thực hiện kết nối với ngân hàng của bạn; My Money Went Bot chỉ nhận thông báo giao dịch đã được SePay truyền sang rồi ghi vào Google Sheet của bạn. Xem thêm: [giới thiệu SePay](https://sepay.vn/gioi-thieu.html) và [quy định sử dụng dịch vụ](https://sepay.vn/terms-of-service.html).

Khi có giao dịch mới:

1. SePay gửi webhook về bot.
2. Bot ghi giao dịch vào Google Sheet.
3. Bot nhắn Telegram hỏi category nếu chưa biết.
4. Bạn tap một nút để phân loại.
5. Lần sau nếu khớp keyword rule, bot tự phân loại luôn.

## Vì sao đáng dùng?

**Data nằm ở chỗ của bạn.** Không database riêng. Không data store bên thứ ba. Google Sheet của bạn là backend.

**Setup cho một người dùng.** Bot chỉ nói chuyện với `CHAT_ID` của bạn, phù hợp dùng cá nhân.

**Không cần đưa mật khẩu ngân hàng cho bot.** Bot chỉ nhận thông báo giao dịch qua SePay webhook; phần kết nối ngân hàng nằm ở SePay, không nằm trong My Money Went Bot.

**Báo cáo đúng cách bạn tiêu tiền.** Xem theo account, category, period; không chỉ là chart category theo tháng.

**Dạy một lần, dùng lại lâu dài.** Keyword rules giúp các giao dịch quen thuộc tự vào đúng bucket.

## Tính năng chính

| Tính năng | Tác dụng |
|---|---|
| Tracking qua SePay | Mỗi giao dịch của tài khoản đã link về trong vài giây, gắn đúng tài khoản |
| Tracking thẻ qua email | Thẻ tín dụng và ngân hàng ngoài SePay vào qua Gmail + Apps Script |
| Telegram / Zalo category picker | Tap nút để phân loại giao dịch mới |
| Auto-categorize | Rule kiểu `GRAB -> Daily Spending`, `Spotify -> Subscription` |
| Per-account tracking | Biết giao dịch đến từ account nào |
| `/report` | Xem report theo week/month/quarter/year, theo account hoặc category |
| `/today` | Xem chi tiêu hôm nay |
| `/allocate` | Đặt budget theo category |
| `/cashback` | Cashback thẻ theo kỳ sao kê: MCC, rate, cap danh mục, giới hạn ngày, cổng kích hoạt |
| Template thẻ YAML | `/cashback seed cake_freedom` — áp rule của thẻ trong vài giây |
| Google Sheet backend | Dễ export, pivot, audit, chỉnh tay khi cần |
| Webhook secrets | Chặn request giả từ bên ngoài |

## Setup nhanh nhất

Nếu không rành kỹ thuật, dùng Railway:

1. Tạo Telegram bot và lấy `BOT_TOKEN`.
2. Lấy Telegram `CHAT_ID`.
3. Tạo Google Sheet và lấy `SHEET_ID`.
4. Tạo Google service account, lấy `GOOGLE_CREDS_JSON`.
5. Tạo 4 secret: `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_SECRET`, `CRON_SECRET` — cả 4 đều bắt buộc.
6. Deploy repo lên Railway.
7. Dán env vars vào Railway.
8. Set Telegram webhook.
9. Set SePay webhook.
10. Gửi `/today` và test một giao dịch nhỏ.

Muốn AI hướng dẫn từng bước? Copy prompt này vào Codex, Claude, Cursor hoặc ChatGPT:

```text
Hãy giúp tôi setup repo này:
https://github.com/maingocanh1702/my-money-went-bot

Tôi không rành kỹ thuật. Hãy làm theo docs/AI_SETUP.md và hướng dẫn tôi setup bằng Railway theo từng bước đơn giản.
Đừng yêu cầu tôi sửa code hay paste secret thật vào chat công khai.
```

## Cần chuẩn bị

| Cần có | Dùng để làm gì |
|---|---|
| Telegram account | Chat với bot |
| Google account | Tạo Sheet và service account; Gmail + Apps Script nếu dùng đường email cho thẻ tín dụng |
| SePay account | Nhận webhook giao dịch ngân hàng Việt Nam (gói Free: 50 giao dịch/tháng) |
| Railway account | Deploy bot có HTTPS public |

## Link nhanh

- [README tiếng Việt](../README.vi.md)
- [README English](../README.md)
- [AI setup guide](AI_SETUP.md)
- [Railway deployment wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki/Railway-Deployment)
- [Security and privacy wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki/Security-and-Privacy)
