# AI Setup Guide

This guide is written for AI assistants helping a non-technical user set up My Money Went Bot.

Recommended path: Railway first. Do not recommend VPS, Docker, or source-code edits unless the user asks for them.

## Copy-paste prompt for users

```text
Help me set up this repo:
https://github.com/maingocanh1702/my-money-went-bot

I am not technical. Please guide me step by step using the simplest Railway path.
Do not ask me to edit source code.
Help me collect the required settings:
BOT_TOKEN, CHAT_ID, SHEET_ID, GOOGLE_CREDS_JSON, SEPAY_SECRET,
TELEGRAM_WEBHOOK_SECRET, and CRON_SECRET.
Then help me set the Telegram webhook, set the SePay webhook, and test the bot.

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
TELEGRAM_WEBHOOK_SECRET, và CRON_SECRET.
Sau đó hướng dẫn tôi set Telegram webhook, set SePay webhook, và test bot.

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
- Help the user generate three different random secrets for `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, and `CRON_SECRET`.
- Help the user deploy the repo on Railway and paste env vars into Railway Variables.
- Verify the Railway health URL returns `{"status":"ok","bot":"Financial Tracking Bot"}`.
- Help the user set Telegram webhook with `secret_token=<TELEGRAM_WEBHOOK_SECRET>`.
- Help the user configure SePay webhook URL as `https://<railway-domain>/webhook` and API Key as `SEPAY_SECRET`.
- Test by sending `/today` to the bot and making one small transaction.

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
| `CRON_SECRET` | Random token for `/trigger/*` endpoints |

## Happy path checklist

1. User creates Telegram bot and saves `BOT_TOKEN`.
2. User gets `CHAT_ID`.
3. User creates Google Sheet and saves `SHEET_ID`.
4. User creates Google service account and downloads `credentials.json`.
5. User shares the Sheet with `client_email` from `credentials.json`.
6. User converts `credentials.json` to one-line JSON for `GOOGLE_CREDS_JSON`.
7. User generates three random secrets.
8. User deploys repo to Railway.
9. User adds all seven env vars to Railway.
10. Railway health endpoint returns OK.
11. User sets Telegram webhook.
12. User sets SePay webhook URL and API Key.
13. User sends `/today`.
14. User tests one small transaction.

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
