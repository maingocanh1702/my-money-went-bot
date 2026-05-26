# Security and Privacy

This project handles bank transaction notifications, so setup should be stricter than a simple demo bot.

## Where your data lives

Your transaction data is written to your Google Sheet. The bot does not use a separate database.

The app may temporarily process incoming webhook payloads while running, but your long-term data store is the Sheet you own.

## What the bot does not need

The bot does not need:

- Your bank login password.
- Your bank card PIN.
- Your full online banking credentials.

It receives transaction notifications from SePay.

## Who can read the Sheet

Anyone with access to your Google Sheet can read the transaction data.

Keep the Sheet private and only share it with:

- Your own Google account.
- The Google service-account `client_email` used by the bot.

## Why secrets are required

| Secret | Protects against |
|---|---|
| `SEPAY_SECRET` | Fake SePay transaction webhooks |
| `TELEGRAM_WEBHOOK_SECRET` | Fake Telegram webhook updates |
| `CRON_SECRET` | Unauthorized calls to `/trigger/*` endpoints |

Without these secrets, a public webhook URL is easier to abuse.

## Files to protect

Never publish:

- `.env`
- `credentials.json`
- Telegram bot token
- Google service-account JSON
- Railway variables

If any secret is leaked, rotate it.

## If a secret leaks

1. Regenerate the leaked value.
2. Update Railway variables.
3. Update the matching external service, such as Telegram or SePay.
4. Redeploy if Railway does not restart automatically.
5. For Google credentials, create a new service-account key and delete the old key.

