# FAQ

## Do I need to know programming to use this?

Not necessarily. Use the Railway setup path. You still need to copy tokens and secrets carefully, but you do not need to edit the Python code.

## Why does the bot need so many variables?

They fall into three groups:

- Identity: which chat channel (Telegram and/or Zalo), which user, and which Google Sheet to use.
- Google access: permission to write to your Sheet.
- Security: random secrets that block fake webhooks and unauthorized triggers.

## Does the bot store my bank password?

No. It receives transaction notifications from SePay. It does not need your bank login password or card PIN.

## Why is my Google Sheet empty?

Most likely the Sheet was not shared with the Google service-account email. Open `credentials.json`, copy `client_email`, and share the Sheet with that email as Editor.

## Why are transactions duplicated?

SePay's native Google Sheets integration may still be enabled. Disable it so only this bot writes rows.

## Can I track income too?

Yes, if you enable incoming transactions in SePay. Income transactions are logged but do not need expense category picking.

## Can I use a VPS instead of Railway?

Yes. Use the README's VPS section or `setup.sh`, but Railway is easier for non-technical users.

## Can multiple people use one bot?

The project is designed as single-tenant: one bot for one person. It checks `CHAT_ID` so the bot only talks to the configured user.

