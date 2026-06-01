# First Transaction Test

Use this page after Railway, Telegram, Google Sheets, and SePay are configured.

## 1. Check the app is live

Open:

```text
https://your-app.up.railway.app/
```

Expected response:

```json
{"status":"ok","bot":"Financial Tracking Bot"}
```

## 2. Check Telegram

Open Telegram and send this to your bot:

```text
/today
```

Expected result: the bot replies.

If it does not reply, check Telegram webhook setup and `TELEGRAM_WEBHOOK_SECRET`.

On **Zalo**: send `/today` to your Zalo bot instead. If it doesn't reply, check `ZALO_ENABLED` / `ZALO_INTERACTIVE`, the `/zalo/webhook` registration, and `ZALO_WEBHOOK_SECRET` — see [Zalo Setup](Zalo-Setup).

## 3. Trigger one small transaction

Make or wait for a small bank transaction that SePay can see.

Expected result:

1. SePay sends the webhook.
2. The bot receives it.
3. The bot messages you in Telegram (or Zalo, depending on your channel; on Zalo an uncategorized expense shows a numbered menu — reply a number).
4. If the account is new, the bot asks you to set it up.
5. The bot asks for a category.
6. The transaction appears in Google Sheets.

## 4. Set up the account

For the first transaction from a new bank source, the bot may ask you to onboard the account.

Use a clear name such as:

```text
TPBank main
```

or:

```text
Vietcombank salary
```

Future transactions from the same source should auto-route to that account.

## 5. Categorize the transaction

Tap the category button in Telegram.

After that, run:

```text
/report
```

Expected result: the report includes the transaction.

