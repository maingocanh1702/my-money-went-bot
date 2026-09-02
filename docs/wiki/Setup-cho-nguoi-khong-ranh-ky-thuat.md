# Setup cho người không rành kỹ thuật

Trang này là bản tiếng Việt của flow setup khuyến nghị. Nếu bạn không quen server Linux, hãy dùng Railway để khỏi phải tự cài nginx, systemd, hay SSL.

> **Telegram hay Zalo?** Hai kênh độc lập — dùng kênh nào cũng được, hoặc cả hai. Trang này hướng dẫn **Telegram**. Nếu dùng **Zalo** (thay cho hoặc bên cạnh Telegram), xem [Zalo Setup](Zalo-Setup) để lấy các biến Zalo; Google Sheet, SePay, và các secret bảo mật thì giống nhau.

## Bạn cần chuẩn bị

- Tài khoản Telegram **hoặc** Zalo (trang này hướng dẫn Telegram; Zalo xem [Zalo Setup](Zalo-Setup))
- Tài khoản Google
- Tài khoản SePay đã kết nối ngân hàng Việt Nam
- Tài khoản Railway
- Khoảng 30 đến 45 phút

## Hiểu nhanh các từ kỹ thuật

| Từ | Hiểu đơn giản là |
|---|---|
| Env vars | Các ô cấu hình trong Railway. Bạn dán giá trị vào đó, không cần sửa code. |
| Webhook | Một đường link để Telegram hoặc SePay gửi thông báo vào bot. |
| Service account | Một email robot của Google để bot ghi vào Sheet của bạn. |
| Secret | Chuỗi ngẫu nhiên giống mật khẩu, dùng để chặn request lạ. |

## Flow setup

1. Tạo bot Telegram bằng BotFather và lưu `BOT_TOKEN`.
2. Lấy `CHAT_ID` của bạn bằng userinfobot.
3. Tạo Google Sheet mới và copy `SHEET_ID`.
4. Tạo Google service account, tải `credentials.json`, rồi share Sheet cho email robot trong file đó với quyền Editor.
5. Deploy repo lên Railway.
6. Thêm đủ các biến Railway.
7. Đặt SePay webhook URL thành Railway URL kết thúc bằng `/webhook`.
8. Đặt Telegram webhook bằng `TELEGRAM_WEBHOOK_SECRET`.
9. Gửi `/today` cho bot.
10. Thử một giao dịch nhỏ và phân loại giao dịch đầu tiên.

## Copy gì, dán vào đâu

| Giá trị | Lấy ở đâu | Dán vào đâu |
|---|---|---|
| `BOT_TOKEN` | Telegram BotFather | Railway variable `BOT_TOKEN` |
| `CHAT_ID` | Telegram userinfobot | Railway variable `CHAT_ID` |
| `SHEET_ID` | URL Google Sheet | Railway variable `SHEET_ID` |
| `GOOGLE_CREDS_JSON` | Nội dung file `credentials.json` | Railway variable `GOOGLE_CREDS_JSON` |
| `SEPAY_SECRET` | Một chuỗi ngẫu nhiên dài | Railway variable `SEPAY_SECRET` và SePay API Key |
| `TELEGRAM_WEBHOOK_SECRET` | Một chuỗi ngẫu nhiên dài khác | Railway variable `TELEGRAM_WEBHOOK_SECRET` và Telegram `setWebhook` |
| `CRON_SECRET` | Một chuỗi ngẫu nhiên dài khác | Railway variable `CRON_SECRET` |

## Vì sao cần nhiều biến

Bot có 3 nhóm cấu hình:

| Nhóm | Biến | Lý do |
|---|---|---|
| Định danh | `BOT_TOKEN`, `CHAT_ID`, `SHEET_ID` | Cho app biết dùng bot nào, nói chuyện với ai, ghi vào Sheet nào. |
| Quyền Google | `GOOGLE_CREDS_JSON` | Cho app quyền ghi vào Google Sheet trên Railway. |
| Bảo mật | `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `CRON_SECRET` | Chặn webhook ngân hàng giả, Telegram update giả, và trigger cron trái phép. |

`BOT_TOKEN` / `CHAT_ID` / `TELEGRAM_WEBHOOK_SECRET` là **kênh Telegram**. Nếu dùng **Zalo** (hoặc Zalo-only), dùng các biến `ZALO_*` thay thế — xem [Zalo Setup](Zalo-Setup). `SHEET_ID`, Google credentials, `SEPAY_SECRET`, `CRON_SECRET` cần cho bất kỳ kênh nào.

## Đặt Telegram webhook không cần terminal

Sau khi Railway có domain dạng:

```text
https://your-app.up.railway.app
```

Bạn có thể mở URL này trong browser, sau khi thay placeholder:

```text
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.up.railway.app/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>&drop_pending_updates=true
```

Nếu thành công, Telegram sẽ trả về JSON có `"ok": true`.

## Checklist trước khi deploy

- [ ] Đã tạo Telegram bot.
- [ ] Đã lưu `BOT_TOKEN`.
- [ ] Đã lấy `CHAT_ID`.
- [ ] Đã tạo Google Sheet.
- [ ] Đã copy `SHEET_ID`.
- [ ] Đã bật Google Sheets API.
- [ ] Đã bật Google Drive API.
- [ ] Đã tạo service account.
- [ ] Đã tải `credentials.json`.
- [ ] Đã share Google Sheet cho `client_email` trong `credentials.json` với quyền Editor.
- [ ] Đã tạo Railway project.
- [ ] Đã thêm đủ các biến Railway (Google Sheet + secret bảo mật + biến của kênh bạn chọn).
- [ ] Đã tắt SePay native Google Sheets integration.

## Checklist thành công

- [ ] Railway domain mở được và hiện `{"status":"ok","bot":"Financial Tracking Bot"}`.
- [ ] Bot Telegram trả lời `/today`.
- [ ] SePay webhook URL kết thúc bằng `/webhook`.
- [ ] Giao dịch nhỏ đầu tiên hiện trong Telegram.
- [ ] Google Sheet tự tạo các tab.
- [ ] Giao dịch xuất hiện trong Sheet.

Nếu bị kẹt, xem [Troubleshooting](Troubleshooting).
