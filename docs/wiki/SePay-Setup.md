# SePay Setup

SePay sends bank transaction notifications to the bot.

## 1. Connect your bank

1. Create a SePay account.
2. Connect your Vietnamese bank account.
3. Confirm SePay is receiving transaction notifications.

## 2. Set webhook URL

In SePay webhook settings, set:

```text
https://your-app.up.railway.app/webhook
```

Replace `your-app.up.railway.app` with your Railway domain.

## 3. Set API Key

Create a long random string and use it in both places:

| Place | Value |
|---|---|
| Railway variable `SEPAY_SECRET` | Your random string |
| SePay Webhook API Key | Same random string |

The bot rejects SePay requests unless the secret matches.

## 4. Choose transaction direction

Recommended for expense tracking:

- Enable outgoing transactions (`Tiền ra`).

Optional:

- Enable incoming transactions (`Tiền vào`) if you also want income logged.

Incoming transactions are logged but do not need category picking.

## 5. Disable native Google Sheets integration

If SePay's native Google Sheets integration is also enabled, transactions can appear twice:

1. Once from SePay's own Google Sheets integration.
2. Once from this bot.

Disable SePay's native Google Sheets integration when using this bot.

