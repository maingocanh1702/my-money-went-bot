# Setup cho người không rành kỹ thuật

Trang này là bản tiếng Việt của flow setup khuyến nghị. Nếu bạn không quen server Linux, hãy dùng Railway để không phải tự cài nginx, systemd, hay SSL.

## Bạn cần chuẩn bị

- Tài khoản Telegram
- Tài khoản Google
- Tài khoản SePay đã kết nối ngân hàng Việt Nam
- Tài khoản Railway
- Khoảng 30 đến 45 phút

## Trước khi kết nối ngân hàng

My Money Went Bot **không truy cập trực tiếp tài khoản ngân hàng của bạn**. Bot không đăng nhập ngân hàng, không đọc biến động số dư, không truy vấn lịch sử giao dịch, và không giữ username/password/OTP/số thẻ. Bot chỉ nhận thông tin giao dịch mà **SePay gửi qua webhook** sau khi bạn cấu hình SePay.

SePay là bên thực hiện kết nối với ngân hàng. Theo phần giới thiệu của SePay, đây là công ty hạ tầng Open Banking tại Việt Nam, cung cấp API ngân hàng và giải pháp tự động hóa dòng tiền; SePay cũng công bố quy định sử dụng dịch vụ và trách nhiệm bảo vệ dữ liệu khách hàng. Vì vậy flow đúng là: **ngân hàng ↔ SePay ↔ My Money Went Bot ↔ Google Sheet của bạn**.

## Hiểu nhanh các từ kỹ thuật

| Từ              | Hiểu đơn giản là                                                           |
| --------------- | --------------------------------------------------------------------------- |
| Env vars        | Các ô cấu hình trong Railway. Bạn copy giá trị vào đó, không cần sửa code. |
| Webhook         | Một đường link để Telegram hoặc SePay gửi thông báo vào bot.               |
| Service account | Một email robot của Google để bot ghi vào Sheet của bạn.                    |
| Secret          | Chuỗi random giống mật khẩu, dùng để chặn request lạ.                     |

## Flow setup

1. Tạo bot Telegram bằng BotFather và lưu `BOT_TOKEN`.
2. Lấy `CHAT_ID` của bạn bằng userinfobot.
3. Tạo Google Sheet mới và copy `SHEET_ID`.
4. Tạo Google service account, tải `credentials.json`, rồi share Sheet cho email robot trong file đó với quyền Editor.
5. Deploy repo lên Railway.
6. Thêm đủ các biến Railway.
7. Set SePay webhook URL thành Railway URL kết thúc bằng `/webhook`.
8. Set Telegram webhook bằng `TELEGRAM_WEBHOOK_SECRET`.
9. Gửi `/today` cho bot.
10. Thử một giao dịch nhỏ và phân loại giao dịch đầu tiên.

## Copy gì, dán vào đâu

| Giá trị                   | Lấy ở đâu                        | Dán vào đâu                                                         |
| ------------------------- | --------------------------------- | ------------------------------------------------------------------- |
| `BOT_TOKEN`               | Telegram BotFather               | Railway variable `BOT_TOKEN`                                        |
| `CHAT_ID`                 | Telegram userinfobot             | Railway variable `CHAT_ID`                                          |
| `SHEET_ID`                | URL Google Sheet                 | Railway variable `SHEET_ID`                                         |
| `GOOGLE_CREDS_JSON`       | Nội dung file `credentials.json` | Railway variable `GOOGLE_CREDS_JSON`                                |
| `SEPAY_SECRET`            | Một chuỗi random dài             | Railway variable `SEPAY_SECRET` và SePay API Key                    |
| `TELEGRAM_WEBHOOK_SECRET` | Một chuỗi random dài khác        | Railway variable `TELEGRAM_WEBHOOK_SECRET` và Telegram `setWebhook` |
| `CRON_SECRET`             | Một chuỗi random dài khác        | Railway variable `CRON_SECRET`                                      |

## Vì sao cần nhiều biến

Bot có 3 nhóm cấu hình:

| Nhóm         | Biến                                                     | Lý do                                                                       |
| ------------ | -------------------------------------------------------- | --------------------------------------------------------------------------- |
| Định danh    | `BOT_TOKEN`, `CHAT_ID`, `SHEET_ID`                       | Cho app biết dùng bot nào, nói chuyện với ai, ghi vào Sheet nào.            |
| Quyền Google | `GOOGLE_CREDS_JSON`                                      | Cho app quyền ghi vào Google Sheet trên Railway.                            |
| Bảo mật      | `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `CRON_SECRET` | Chặn webhook ngân hàng giả, Telegram update giả, và trigger cron trái phép. |

## Set Telegram webhook không cần terminal

Sau khi Railway có domain dạng:

```
https://your-app.up.railway.app
```

Bạn có thể mở URL này trong browser, sau khi thay placeholder:

```
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
- [ ] Đã thêm đủ 7 biến Railway.
- [ ] Đã tắt SePay native Google Sheets integration.

## Checklist thành công

- [ ] Railway domain mở được và hiện `{"status":"ok","bot":"Financial Tracking Bot"}`.
- [ ] Bot Telegram trả lời `/today`.
- [ ] SePay webhook URL kết thúc bằng `/webhook`.
- [ ] Giao dịch nhỏ đầu tiên hiện trong Telegram.
- [ ] Google Sheet tự tạo các tab.
- [ ] Giao dịch xuất hiện trong Sheet.

Nếu bị kẹt, xem [Troubleshooting](Troubleshooting).
