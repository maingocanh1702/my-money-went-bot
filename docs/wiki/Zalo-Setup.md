# Zalo Setup

Telegram and Zalo are **two independent channels**. You can run the bot on Telegram, on Zalo, or on both. This page covers the Zalo channel. The Google Sheet, SePay, and the security secrets (`SEPAY_SECRET`, `CRON_SECRET`) are required either way — see [Railway Deployment](Railway-Deployment) and [Google Sheets Setup](Google-Sheets-Setup).

> **What works on Zalo:** transaction notifications, a numbered-text category picker for uncategorized expenses (reply a number), and the commands `/today`, `/report`, `/accounts`, `/keywords`, `/manage`, `/allocate`, `/recat`, `/cancel`. Zalo has no inline buttons, so everything uses numbered menus.
>
> **Telegram-only flows (for now):** creating a brand-new category mid-categorize, and first-time account onboarding for an unmapped source. A couple of advanced paths remain Telegram-only.

## Two Zalo modes

| Mode | Env | What you get |
|---|---|---|
| **Notify-only** | `ZALO_ENABLED=true` (no `ZALO_INTERACTIVE`) | Bot *sends* notifications to Zalo. It does **not** accept commands/replies from Zalo. |
| **Interactive** | `ZALO_ENABLED=true` + `ZALO_INTERACTIVE=true` + webhook | Full two-way: commands, category picker replies, menus. |

Most people want **Interactive**.

## Environment variables

| Env var | What to put there |
|---|---|
| `ZALO_ENABLED` | `true` to turn the Zalo channel on (default `false`). |
| `ZALO_BOT_TOKEN` | Bot token from the [Zalo Bot Platform](https://bot.zapps.me/). |
| `ZALO_CHAT_ID` | Your Zalo chat ID (discover it with the script below). |
| `ZALO_INTERACTIVE` | `true` to accept incoming Zalo webhook commands. |
| `ZALO_WEBHOOK_SECRET` | A random string; must match the `X-Bot-Api-Secret-Token` header Zalo sends. |
| `ZALO_USER_ID` | The authorized Zalo sender id — the bot rejects everyone else. |

If `ZALO_INTERACTIVE=true`, the app requires `ZALO_WEBHOOK_SECRET` and `ZALO_USER_ID` at startup (fail-closed).

## Step-by-step

### 1. Create a Zalo bot and get the token

Create a bot on the [Zalo Bot Platform](https://bot.zapps.me/) and copy its **bot token**. Set it as `ZALO_BOT_TOKEN`.

### 2. Discover your `ZALO_CHAT_ID`

1. Open Zalo and **send any message to your bot**.
2. Run the helper script with your token:

   ```bash
   ZALO_BOT_TOKEN=<your-token> python scripts/zalo_get_updates.py
   ```

3. It verifies the token (`getMe`) and prints the chat ID of whoever messaged the bot. Use that value for both `ZALO_CHAT_ID` and `ZALO_USER_ID` (for a single-user bot they are your own id).

### 3. Set the environment variables

On Railway (or your `.env`), set the Zalo vars above plus the always-required ones (`SHEET_ID`, Google credentials, `SEPAY_SECRET`, `CRON_SECRET`). You do **not** need `BOT_TOKEN` / `CHAT_ID` / `TELEGRAM_WEBHOOK_SECRET` for a Zalo-only deployment.

Generate the webhook secret with any random string, e.g.:

```bash
openssl rand -hex 32   # use as ZALO_WEBHOOK_SECRET
```

### 4. Register the Zalo webhook (interactive mode)

Point the Zalo Bot Platform webhook at your deployment:

```
https://<your-app>.up.railway.app/zalo/webhook
```

Configure the platform to send the secret header `X-Bot-Api-Secret-Token` equal to your `ZALO_WEBHOOK_SECRET`. The bot validates this header and the sender id (`ZALO_USER_ID`) on every event; mismatches are silently ignored.

### 5. Test

1. Send `/today` to the bot on Zalo — it should reply.
2. Trigger a small bank transaction. The bot logs it and, if it doesn't match a keyword rule, sends a numbered category menu — reply with the bucket number to categorize it.
3. Use `/keywords` to auto-categorize recurring transactions.

## Notes

- The Zalo Bot Platform API only supports plain text, so all interaction is numbered-text menus (no inline buttons). API docs: <https://bot.zapps.me/docs/>.
- The bot only talks to the configured `ZALO_USER_ID` — single-user, like the Telegram `CHAT_ID` check.
- See [Command Reference](Command-Reference) for the full command list and [Troubleshooting](Troubleshooting) if something doesn't respond.
