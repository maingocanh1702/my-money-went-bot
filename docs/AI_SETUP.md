# AI Setup Guide

This guide is written for AI assistants helping a non-technical user set up My Money Went Bot.

The short version of it lives at the top of the README, so a reader can copy one prompt and start. This page is the longer brief for the assistant.

Recommended path: Railway first. Do not recommend VPS, Docker, or source-code edits unless the user asks for them.

## Copy-paste prompt for users

```text
Help me set up this repo:
https://github.com/maingocanh1702/my-money-went-bot

I am not technical. Please guide me step by step using the simplest Railway path.
Do not ask me to edit source code.
Help me collect the required settings:
BOT_TOKEN, CHAT_ID, SHEET_ID, GOOGLE_CREDS_JSON, SEPAY_SECRET,
TELEGRAM_WEBHOOK_SECRET, EMAIL_SECRET, and CRON_SECRET.
All of them are mandatory — the bot refuses to start if any is missing.
Then help me set the Telegram webhook, set the SePay webhook, add the Google
Apps Script that forwards my card notification emails, and test the bot.

I also use Zalo. After Telegram works, walk me through adding Zalo as a second
channel: creating the bot in Zalo Bot Manager, finding my ZALO_CHAT_ID with
scripts/zalo_get_updates.py, and setting ZALO_ENABLED, ZALO_BOT_TOKEN,
ZALO_CHAT_ID and ZALO_SECRET_TOKEN, then registering the Zalo webhook.
(Skip this if I say I do not use Zalo.)

Important: do not ask me to paste real secrets into a public chat.
```

Vietnamese version:

```text
Hãy giúp tôi setup repo này:
https://github.com/maingocanh1702/my-money-went-bot

Tôi không rành kỹ thuật. Hãy hướng dẫn từng bước đơn giản nhất bằng Railway.
Đừng yêu cầu tôi sửa code.
Hãy giúp tôi lấy đủ các biến cấu hình:
BOT_TOKEN, CHAT_ID, SHEET_ID, GOOGLE_CREDS_JSON, SEPAY_SECRET,
TELEGRAM_WEBHOOK_SECRET, EMAIL_SECRET, và CRON_SECRET.
Tất cả đều bắt buộc — thiếu một biến là bot không khởi động.
Sau đó hướng dẫn tôi set Telegram webhook, set SePay webhook, thêm Google Apps
Script để chuyển email thông báo thẻ, và test bot.

Tôi có dùng Zalo. Khi Telegram chạy được rồi, hướng dẫn tôi thêm Zalo làm kênh
thứ hai: tạo bot trong Zalo Bot Manager, lấy ZALO_CHAT_ID bằng
scripts/zalo_get_updates.py, set ZALO_ENABLED, ZALO_BOT_TOKEN, ZALO_CHAT_ID và
ZALO_SECRET_TOKEN, rồi đăng ký webhook Zalo.
(Bỏ qua phần này nếu tôi nói tôi không dùng Zalo.)

Lưu ý: đừng yêu cầu tôi paste secret thật vào chat công khai.
```

## Assistant instructions

Use short steps. Ask for one thing at a time. Keep the user on the Railway path unless they explicitly ask for VPS or Docker.

Do:

- Explain that the bot is single-tenant: one bot for one user's Telegram chat and Google Sheet.
- Help the user create a Telegram bot with BotFather and get `BOT_TOKEN`.
- Help the user get their own `CHAT_ID`.
- Help the user create a Google Sheet and copy `SHEET_ID`.
- Help the user create a Google service account, download `credentials.json`, and share the Sheet with the service account email as Editor.
- Help the user convert `credentials.json` into one-line `GOOGLE_CREDS_JSON`.
- Help the user generate four different random secrets for `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_SECRET`, and `CRON_SECRET`.
- Help the user deploy the repo on Railway and paste env vars into Railway Variables.
- Verify the Railway health URL returns `{"status":"ok","bot":"Financial Tracking Bot"}`.
- Help the user set Telegram webhook with `secret_token=<TELEGRAM_WEBHOOK_SECRET>`.
- Help the user configure SePay webhook URL as `https://<railway-domain>/webhook` and API Key as `SEPAY_SECRET`.
- Test by sending `/today` to the bot and making one small transaction.
- Ask whether the user uses Zalo. If they do, add it **after** Telegram is working:
  create the bot in Zalo Bot Manager (the name must start with `Bot`), find
  `ZALO_CHAT_ID` with `python3 scripts/zalo_get_updates.py` after they message the
  bot once, generate `ZALO_SECRET_TOKEN`, set the four Zalo variables on Railway,
  and register the webhook at `https://<domain>/zalo/webhook` with that secret.
  Tell them what they are getting: the same bot, same commands, but numbered
  replies instead of buttons, because Zalo's API sends plain text only.
- Ask whether the user has cards they want tracked. Any card whose bank emails them per
  transaction can be added — **credit and debit alike, the same way**. Point them at the
  Gmail + Apps Script step (README *Step 6*) and at the onboarding wizard's account type:
  `credit` if they also want cashback tracking, `debit` if they just want the spending
  recorded. A debit card needs no template and no code.

Do not:

- Ask the user to commit `.env`, `credentials.json`, or real secrets.
- Ask the user to paste real secrets into screenshots or public chat.
- Recommend disabling the security secrets.
- Recommend SePay native Google Sheets integration; it can duplicate rows because the bot writes to Sheets itself.
- Recommend Docker or VPS as the first path for a non-technical user.

## Required env vars

| Env var | Meaning |
|---|---|
| `BOT_TOKEN` | Telegram bot token from BotFather |
| `CHAT_ID` | The user's Telegram chat ID |
| `SHEET_ID` | Google Sheet ID from the Sheet URL |
| `GOOGLE_CREDS_JSON` | One-line Google service-account JSON |
| `SEPAY_SECRET` | Same value as SePay webhook API Key |
| `TELEGRAM_WEBHOOK_SECRET` | Random token used in Telegram `setWebhook` |
| `EMAIL_SECRET` | Random token; must match the `SECRET` in `google_apps_script.js` |
| `CRON_SECRET` | Random token for `/trigger/*` endpoints |

Every one of these is required. The bot handles money over public webhooks, so it fails fast at startup rather than running with an unauthenticated endpoint.

## Optional: the Zalo channel

Telegram is required whether or not Zalo is used — there is no Zalo-only mode, and the bot exits at startup without `BOT_TOKEN`, `CHAT_ID` and `TELEGRAM_WEBHOOK_SECRET`. Zalo is a second channel on top.

| Env var | Meaning |
|---|---|
| `ZALO_ENABLED` | `true` to turn the channel on |
| `ZALO_BOT_TOKEN` | Bot token messaged to the user by Zalo Bot Manager |
| `ZALO_CHAT_ID` | The user's Zalo sender id — also the only sender the bot accepts |
| `ZALO_SECRET_TOKEN` | Random token; **required** once `ZALO_ENABLED=true`, because `/zalo/webhook` is public |

Then register the webhook:

```bash
curl -X POST "https://bot-api.zaloplatforms.com/bot<ZALO_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<your-app>.up.railway.app/zalo/webhook","secret_token":"<ZALO_SECRET_TOKEN>"}'
```

Set expectations honestly: every command works on Zalo, but Zalo's Bot API sends plain text only, so a category picker is a numbered list the user replies to rather than buttons to tap.

## Happy path checklist

1. User creates Telegram bot and saves `BOT_TOKEN`.
2. User gets `CHAT_ID`.
3. User creates Google Sheet and saves `SHEET_ID`.
4. User creates Google service account and downloads `credentials.json`.
5. User shares the Sheet with `client_email` from `credentials.json`.
6. User converts `credentials.json` to one-line JSON for `GOOGLE_CREDS_JSON`.
7. User generates four random secrets.
8. User deploys repo to Railway.
9. User adds all eight env vars to Railway.
10. Railway health endpoint returns OK.
11. User sets Telegram webhook.
12. User sets SePay webhook URL and API Key.
13. User sends `/today`.
14. User tests one small transaction.
15. Optional — user sets up the Gmail → Apps Script forwarder and onboards each card,
    credit or debit, as it first spends.
16. Optional — user adds Zalo: bot created, `ZALO_CHAT_ID` found, four Zalo variables
    set, webhook registered, `/today` answered on Zalo.

## Verification commands

Railway health:

```bash
curl https://<your-app>.up.railway.app/
```

Set Telegram webhook:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://<your-app>.up.railway.app/webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>" \
  -d "drop_pending_updates=true"
```

Check Telegram webhook:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

## Troubleshooting priority

If setup fails, check in this order:

1. Railway logs.
2. Missing or misspelled env vars.
3. `GOOGLE_CREDS_JSON` is not valid one-line JSON.
4. Google Sheet was not shared with the service account `client_email`.
5. Telegram webhook URL or `TELEGRAM_WEBHOOK_SECRET` mismatch.
6. SePay webhook URL does not end with `/webhook`.
7. SePay API Key does not match `SEPAY_SECRET`.
