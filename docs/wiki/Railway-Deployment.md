# Railway Deployment

Railway is the recommended deploy target for non-technical users because it gives the bot a public HTTPS URL without manual server setup.

## 1. Create the project

1. Fork or push this repo to your GitHub account.
2. Go to Railway.
3. Create a new project.
4. Choose Deploy from GitHub repo.
5. Select `my-money-went-bot`.

Railway should detect the app and deploy it using the repo configuration.

## 2. Add variables

Open Railway project settings and add these variables. **Always required:** the Google Sheet, the security secrets, and **at least one chat channel (Telegram and/or Zalo)** — the app refuses to start unless one channel is fully configured.

Always required:

| Variable | Notes |
|---|---|
| `SHEET_ID` | From the Google Sheet URL. |
| `GOOGLE_CREDS_JSON` | Paste service-account JSON as one line (Railway). |
| `SEPAY_SECRET` | Same value as SePay Webhook API Key. |
| `CRON_SECRET` | Random string for `/trigger/*` endpoints. |

Telegram channel (set these to use Telegram):

| Variable | Notes |
|---|---|
| `BOT_TOKEN` | From Telegram BotFather. |
| `CHAT_ID` | From Telegram userinfobot. |
| `TELEGRAM_WEBHOOK_SECRET` | Same value used in Telegram `setWebhook`. |

Zalo channel (set these to use Zalo — see [Zalo Setup](Zalo-Setup)):

| Variable | Notes |
|---|---|
| `ZALO_ENABLED` | `true` to enable Zalo. |
| `ZALO_BOT_TOKEN` | Zalo Bot Platform token. |
| `ZALO_CHAT_ID` | Your Zalo chat id (discover with `scripts/zalo_get_updates.py`). |
| `ZALO_INTERACTIVE` | `true` to accept Zalo commands/replies. |
| `ZALO_WEBHOOK_SECRET` | Matches the `X-Bot-Api-Secret-Token` header Zalo sends. |
| `ZALO_USER_ID` | Authorized Zalo sender id. |

## 3. Convert Google credentials to one line

Railway variables work best when `GOOGLE_CREDS_JSON` is pasted as one line.

If you have a terminal:

```bash
cat credentials.json | tr -d '\n'
```

Paste the output into Railway.

If you do not use a terminal, open `credentials.json`, copy the full contents, remove line breaks, and paste the result into Railway.

## 4. Check the health endpoint

After deployment, Railway gives you a domain like:

```text
https://your-app.up.railway.app
```

Open it in a browser. You should see:

```json
{"status":"ok","bot":"Financial Tracking Bot"}
```

If it does not work, open Railway logs and check for missing variables or invalid Google credentials JSON.

## 5. Webhook URLs

Use these URLs:

| Service | URL |
|---|---|
| SePay | `https://your-app.up.railway.app/webhook` |
| Telegram | same `/webhook` URL, registered through `setWebhook` |
| Zalo (if used) | `https://your-app.up.railway.app/zalo/webhook` — see [Zalo Setup](Zalo-Setup) |

Telegram webhook command:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://your-app.up.railway.app/webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>" \
  -d "drop_pending_updates=true"
```

No terminal? Open this URL in your browser after replacing the placeholders:

```text
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.up.railway.app/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>&drop_pending_updates=true
```

Verify it:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
