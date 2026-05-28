# My Money Went Bot

![My Money Went Bot — Bot Telegram tự động theo dõi chi tiêu từ ngân hàng Việt Nam và ghi vào Google Sheet của bạn](screenshots/banner.png)

[English](../README.md) | [Tiếng Việt](../README.vi.md) | [Setup bằng AI](AI_SETUP.md)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Channel-Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Backend-Google%20Sheets-34A853?style=for-the-badge&logo=googlesheets&logoColor=white)
![SePay](https://img.shields.io/badge/Bank%20Webhook-SePay-0F172A?style=for-the-badge)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-D4A017?style=for-the-badge)

# My Money Went Bot - theo dõi tiền đi đâu ngay trong Telegram

Bot tự ghi giao dịch ngân hàng Việt Nam vào Google Sheet của bạn, hỏi bạn phân loại chi tiêu bằng nút bấm, rồi tạo báo cáo theo ngày, tuần, tháng, quý, năm.

---

## Bạn đang gặp vấn đề này?

- Muốn biết tiền đi đâu nhưng lười nhập tay từng khoản.
- App quản lý chi tiêu bắt đăng nhập ngân hàng hoặc giữ data trên cloud của họ.
- Sao kê ngân hàng khó đọc, khó phân loại, khó xem theo account/category.
- Google Sheet linh hoạt nhưng cập nhật thủ công quá mệt.
- Giao dịch lặp lại như Grab, Spotify, Bách Hóa Xanh cứ phải phân loại lại nhiều lần.

## Bot này làm gì?

My Money Went Bot nối 3 thứ bạn đã dùng:

```text
SePay webhook -> Telegram bot -> Google Sheet của bạn
```

Khi có giao dịch mới:

1. SePay gửi webhook về bot.
2. Bot ghi giao dịch vào Google Sheet.
3. Bot nhắn Telegram hỏi category nếu chưa biết.
4. Bạn tap một nút để phân loại.
5. Lần sau nếu khớp keyword rule, bot tự phân loại luôn.

## Vì sao đáng dùng?

**Data nằm ở chỗ của bạn.** Không database riêng. Không data store bên thứ ba. Google Sheet của bạn là backend.

**Setup cho một người dùng.** Bot chỉ nói chuyện với `CHAT_ID` của bạn, phù hợp dùng cá nhân.

**Không cần đưa mật khẩu ngân hàng cho bot.** Bot nhận thông báo giao dịch qua SePay webhook, không cần username, password, OTP hay số thẻ.

**Báo cáo đúng cách bạn tiêu tiền.** Xem theo account, category, period; không chỉ là chart category theo tháng.

**Dạy một lần, dùng lại lâu dài.** Keyword rules giúp các giao dịch quen thuộc tự vào đúng bucket.

## Tính năng chính

| Tính năng | Tác dụng |
|---|---|
| Telegram category picker | Tap nút để phân loại giao dịch mới |
| Auto-categorize | Rule kiểu `GRAB -> Daily Spending`, `Spotify -> Subscription` |
| Per-account tracking | Biết giao dịch đến từ account nào |
| `/report` | Xem report theo week/month/quarter/year |
| `/today` | Xem chi tiêu hôm nay |
| `/allocate` | Đặt budget theo category |
| Google Sheet backend | Dễ export, pivot, audit, chỉnh tay khi cần |
| Webhook secrets | Chặn request giả từ bên ngoài |

## Setup nhanh nhất

Nếu không rành kỹ thuật, dùng Railway:

1. Tạo Telegram bot và lấy `BOT_TOKEN`.
2. Lấy Telegram `CHAT_ID`.
3. Tạo Google Sheet và lấy `SHEET_ID`.
4. Tạo Google service account, lấy `GOOGLE_CREDS_JSON`.
5. Tạo 3 secret: `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `CRON_SECRET`.
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
| Google account | Tạo Sheet và service account |
| SePay account | Nhận webhook giao dịch ngân hàng Việt Nam |
| Railway account | Deploy bot có HTTPS public |

## Link nhanh

- [README tiếng Việt](../README.vi.md)
- [README English](../README.md)
- [AI setup guide](AI_SETUP.md)
- [Railway deployment wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki/Railway-Deployment)
- [Security and privacy wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki/Security-and-Privacy)
