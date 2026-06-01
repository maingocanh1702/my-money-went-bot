# Setup for Non-Technical Users

Use this path if you do not usually deploy servers. It uses Railway so you do not need to manage Linux, nginx, systemd, or SSL certificates.

> **Telegram or Zalo?** They are two independent channels — set up either, or both. This guide walks through **Telegram**. To use **Zalo** instead of (or alongside) Telegram, follow [Zalo Setup](Zalo-Setup) for the Zalo variables; the Google Sheet, SePay, and security secrets are the same.

## Before you start

You need:

- A Telegram **or** Zalo account (this guide shows Telegram; for Zalo see [Zalo Setup](Zalo-Setup))
- A Google account
- A SePay account connected to your Vietnamese bank
- A Railway account
- About 30 to 45 minutes

## Terms in plain English

| Term | Meaning |
|---|---|
| Env vars | Settings fields in Railway. You paste values there instead of editing code. |
| Webhook | A URL where Telegram or SePay sends events to your bot. |
| Service account | A Google robot email that lets the bot write to your Sheet. |
| Secret | A random password-like string used to block unknown requests. |

## The full setup flow

1. Create your Telegram bot with BotFather and save `BOT_TOKEN`.
2. Get your Telegram `CHAT_ID` from userinfobot.
3. Create a new Google Sheet and copy `SHEET_ID`.
4. Create a Google service account, download `credentials.json`, and share the Sheet with the service-account email as Editor.
5. Deploy the repo on Railway.
6. Add all Railway variables.
7. Set SePay webhook URL to the Railway `/webhook` URL.
8. Set Telegram webhook with `TELEGRAM_WEBHOOK_SECRET`.
9. Send `/today` to the bot.
10. Trigger one small transaction and categorize it.

## Values to copy and paste

| Value | Where to get it | Where to paste it |
|---|---|---|
| `BOT_TOKEN` | Telegram BotFather | Railway variable `BOT_TOKEN` |
| `CHAT_ID` | Telegram userinfobot | Railway variable `CHAT_ID` |
| `SHEET_ID` | Google Sheet URL | Railway variable `SHEET_ID` |
| `GOOGLE_CREDS_JSON` | Contents of `credentials.json` | Railway variable `GOOGLE_CREDS_JSON` |
| `SEPAY_SECRET` | A long random string | Railway variable `SEPAY_SECRET` and SePay API Key |
| `TELEGRAM_WEBHOOK_SECRET` | A different long random string | Railway variable `TELEGRAM_WEBHOOK_SECRET` and Telegram `setWebhook` |
| `CRON_SECRET` | Another long random string | Railway variable `CRON_SECRET` |

## Why there are several variables

The bot has three groups of settings:

| Group | Variables | Why they exist |
|---|---|---|
| Identity | `BOT_TOKEN`, `CHAT_ID`, `SHEET_ID` | Tell the app which bot, user, and Sheet to use. |
| Google access | `GOOGLE_CREDS_JSON` | Lets the app write to your Google Sheet on Railway. |
| Security | `SEPAY_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `CRON_SECRET` | Blocks fake bank webhooks, fake Telegram updates, and unauthorized cron triggers. |

`BOT_TOKEN` / `CHAT_ID` / `TELEGRAM_WEBHOOK_SECRET` are the **Telegram channel**. For a **Zalo** (or Zalo-only) setup, use the `ZALO_*` variables instead — see [Zalo Setup](Zalo-Setup). `SHEET_ID`, Google credentials, `SEPAY_SECRET`, and `CRON_SECRET` are needed for any channel.

## Pre-deploy checklist

- [ ] Telegram bot created.
- [ ] `BOT_TOKEN` saved.
- [ ] `CHAT_ID` saved.
- [ ] Google Sheet created.
- [ ] `SHEET_ID` copied.
- [ ] Google Sheets API enabled.
- [ ] Google Drive API enabled.
- [ ] Service account created.
- [ ] `credentials.json` downloaded.
- [ ] Google Sheet shared with the service-account `client_email` as Editor.
- [ ] Railway project created.
- [ ] All required Railway variables added (Google Sheet + security secrets + your chosen channel's variables).
- [ ] SePay native Google Sheets integration disabled.

## Success checklist

- [ ] Railway domain opens and shows `{"status":"ok","bot":"Financial Tracking Bot"}`.
- [ ] Telegram bot replies to `/today`.
- [ ] SePay webhook URL ends with `/webhook`.
- [ ] First small transaction appears in Telegram.
- [ ] Google Sheet tabs are created automatically.
- [ ] The transaction appears in the Sheet.

Next: [Railway Deployment](Railway-Deployment), [Google Sheets Setup](Google-Sheets-Setup), and [SePay Setup](SePay-Setup).

