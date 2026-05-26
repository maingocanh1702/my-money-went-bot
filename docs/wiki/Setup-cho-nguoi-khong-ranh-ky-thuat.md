# Setup cho nguoi khong ranh ky thuat

Trang nay la ban tieng Viet cua flow setup khuyen nghi. Neu ban khong quen server Linux, hay dung Railway de khong phai tu cai nginx, systemd, hay SSL.

## Ban can chuan bi

- Tai khoan Telegram
- Tai khoan Google
- Tai khoan SePay da ket noi ngan hang Viet Nam
- Tai khoan Railway
- Khoang 30 den 45 phut

## Hieu nhanh cac tu ky thuat

| Tu | Hieu don gian la |
|---|---|
| Env vars | Cac o cau hinh trong Railway. Ban copy gia tri vao do, khong can sua code. |
| Webhook | Mot duong link de Telegram hoac SePay gui thong bao vao bot. |
| Service account | Mot email robot cua Google de bot ghi vao Sheet cua ban. |
| Secret | Chuoi random giong mat khau, dung de chan request la. |

## Flow setup

1. Tao bot Telegram bang BotFather va luu `BOT_TOKEN`.
2. Lay `CHAT_ID` cua ban bang userinfobot.
3. Tao Google Sheet moi va copy `SHEET_ID`.
4. Tao Google service account, tai `credentials.json`, roi share Sheet cho email robot trong file do voi quyen Editor.
5. Deploy repo len Railway.
6. Them du cac bien Railway.
7. Set SePay webhook URL thanh Railway URL ket thuc bang `/webhook`.
8. Set Telegram webhook bang `TELEGRAM_WEBHOOK_SECRET`.
9. Gui `/today` cho bot.
10. Thu mot giao dich nho va phan loai giao dich dau tien.

## Copy gi, dan vao dau

| Gia tri | Lay o dau | Dan vao dau |
|---|---|---|
| `BOT_TOKEN` | Telegram BotFather | Railway variable `BOT_TOKEN` |
| `CHAT_ID` | Telegram userinfobot | Railway variable `CHAT_ID` |
| `SHEET_ID` | URL Google Sheet | Railway variable `SHEET_ID` |
| `GOOGLE_CREDS_JSON` | Noi dung file `credentials.json` | Railway variable `GOOGLE_CREDS_JSON` |
| `SEPAY_SECRET` | Mot chuoi random dai | Railway variable `SEPAY_SECRET` va SePay API Key |
| `TELEGRAM_WEBHOOK_SECRET` | Mot chuoi random dai khac | Railway variable `TELEGRAM_WEBHOOK_SECRET` va Telegram `setWebhook` |
| `CRON_SECRET` | Mot chuoi random dai khac | Railway variable `CRON_SECRET` |

## Vi sao can nhieu bien

Bot co 3 nhom cau hinh:

| Nhom | Bien | Ly do |
|---|---|---|
| Dinh danh | `BOT_TOKEN`, `CHAT_ID`, `SHEET_ID` | Cho app biet dung bot nao, noi chuyen voi ai, ghi vao Sheet nao. |
| Quyen Google | `GOOGLE_CREDS_JSON` | Cho app quyen ghi vao Google Sheet tren Railway. |
| Bao mat | `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `CRON_SECRET` | Chan webhook ngan hang gia, Telegram update gia, va trigger cron trai phep. |

## Set Telegram webhook khong can terminal

Sau khi Railway co domain dang:

```text
https://your-app.up.railway.app
```

Ban co the mo URL nay trong browser, sau khi thay placeholder:

```text
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.up.railway.app/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>&drop_pending_updates=true
```

Neu thanh cong, Telegram se tra ve JSON co `"ok": true`.

## Checklist truoc khi deploy

- [ ] Da tao Telegram bot.
- [ ] Da luu `BOT_TOKEN`.
- [ ] Da lay `CHAT_ID`.
- [ ] Da tao Google Sheet.
- [ ] Da copy `SHEET_ID`.
- [ ] Da bat Google Sheets API.
- [ ] Da bat Google Drive API.
- [ ] Da tao service account.
- [ ] Da tai `credentials.json`.
- [ ] Da share Google Sheet cho `client_email` trong `credentials.json` voi quyen Editor.
- [ ] Da tao Railway project.
- [ ] Da them du 7 bien Railway.
- [ ] Da tat SePay native Google Sheets integration.

## Checklist thanh cong

- [ ] Railway domain mo duoc va hien `{"status":"ok","bot":"Financial Tracking Bot"}`.
- [ ] Bot Telegram tra loi `/today`.
- [ ] SePay webhook URL ket thuc bang `/webhook`.
- [ ] Giao dich nho dau tien hien trong Telegram.
- [ ] Google Sheet tu tao cac tab.
- [ ] Giao dich xuat hien trong Sheet.

Neu bi ket, xem [Troubleshooting](Troubleshooting).
