# Troubleshooting

Start with the symptom you see.

## Railway deploy failed

Likely causes:

- Missing required variable.
- Invalid `GOOGLE_CREDS_JSON`.
- Bad JSON formatting.

What to check:

- All required Railway variables exist (Google Sheet + security secrets + at least one channel's variables).
- `GOOGLE_CREDS_JSON` is the full service-account JSON.
- The JSON is one line.
- Your channel's variables are set: Telegram (`BOT_TOKEN`, `CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`) and/or Zalo (`ZALO_*` — see [Zalo Setup](Zalo-Setup)).

## Railway URL does not show `status: ok`

Likely causes:

- App crashed during startup.
- Required security secret is missing.
- Google credentials cannot be parsed.

What to do:

1. Open Railway logs.
2. Search for `FATAL` or missing env var names.
3. Fix variables and redeploy.

## Bot does not reply to `/today`

Likely causes:

- Telegram webhook was not set.
- Wrong Railway URL was used.
- `TELEGRAM_WEBHOOK_SECRET` in Railway does not match the `setWebhook` secret.
- Wrong `CHAT_ID`.
- (Zalo) `ZALO_ENABLED` not set, the `/zalo/webhook` URL not registered, or `ZALO_SECRET_TOKEN` / `ZALO_CHAT_ID` mismatch — see [Zalo Setup](Zalo-Setup).

What to do:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

Check that `url` ends with:

```text
/webhook
```

Then run `setWebhook` again if needed.

## Transaction arrives but Google Sheet is empty

Likely causes:

- Google Sheet was not shared with the service-account email.
- Wrong `SHEET_ID`.
- Google Sheets API or Drive API is not enabled.

What to do:

1. Open `credentials.json`.
2. Copy `client_email`.
3. Share the Google Sheet with that email as Editor.
4. Confirm `SHEET_ID` matches the Sheet URL.

## Transactions are duplicated

Likely cause:

- SePay native Google Sheets integration is still enabled.

What to do:

- Disable SePay's native Google Sheets integration.
- Let this bot be the only writer to the Sheet.

## SePay says webhook was sent but bot gets nothing

Likely causes:

- Wrong webhook URL.
- SePay API Key does not match `SEPAY_SECRET`.
- Railway app is down.

What to check:

- URL is `https://your-app.up.railway.app/webhook`.
- SePay API Key equals Railway `SEPAY_SECRET`.
- Railway health endpoint works.

## Bot works but only for some commands

Likely causes:

- `CHAT_ID` is wrong.
- Telegram updates are coming from another user or group.

What to do:

- Re-check your `CHAT_ID` using userinfobot.
- Use the bot in a direct chat first.

