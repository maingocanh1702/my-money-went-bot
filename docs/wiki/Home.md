# My Money Went Bot Wiki

This wiki is the longer, task-based manual for My Money Went Bot. The README is the front page; the wiki is where setup details, troubleshooting, privacy notes, and developer references live.

## Start here

- New user: [Setup for Non-Technical Users](Setup-for-Non-Technical-Users)
- Vietnamese user: [Setup cho nguoi khong ranh ky thuat](Setup-cho-nguoi-khong-ranh-ky-thuat)
- Using Zalo instead of (or alongside) Telegram: [Zalo Setup](Zalo-Setup)
- Deploying on Railway: [Railway Deployment](Railway-Deployment)
- Stuck during setup: [Troubleshooting](Troubleshooting)
- Want to understand privacy/security: [Security and Privacy](Security-and-Privacy)
- Want command examples: [Command Reference](Command-Reference)
- Want to develop locally: [Developer Guide](Developer-Guide)

## What the bot does

My Money Went Bot tracks your transactions automatically, into a Google Sheet you own, driven from **Telegram or Zalo** (two independent channels — set up either, or both). Transactions reach it from two sources:

- **Vietnamese bank accounts.** SePay turns each bank notification into a webhook; the bot writes the row, tags the account, and asks for a category (or applies a keyword rule). SePay's free plan covers 50 transactions a month — see [SePay Setup](SePay-Setup).
- **Credit cards.** The bank's own notification emails reach the bot through a Google Apps Script, which also covers any bank SePay hasn't signed.

Reports slice by account, category, and week/month/quarter/year. On top of the tracking sit monthly budgets, credit-card balances, and cashback tracking — for every swipe the bot works out what it earned (MCC, the card's rate, per-transaction tiers, per-category caps, daily limits, activation gate), and `/cashback` shows the whole statement cycle. Cards are YAML templates in `card_templates/`.

## Recommended setup path

Telegram and Zalo are independent channels — set up whichever you use, or both. The steps below show Telegram; for Zalo see [Zalo Setup](Zalo-Setup). For most users, use Railway:

1. Create a Telegram bot (or set up Zalo — see [Zalo Setup](Zalo-Setup)).
2. Create a Google Sheet.
3. Create Google service-account credentials.
4. Deploy this repo on Railway.
5. Connect SePay to the Railway webhook URL.
6. Set the Telegram webhook.
7. Test `/today` and one small transaction.
8. Optional — track credit cards too: set up the Gmail → Apps Script forwarder (`google_apps_script.js`) and onboard the card; add cashback on top with `/cashback seed <template>`. Steps are in the README under *Step 6*.

Detailed guide: [Setup for Non-Technical Users](Setup-for-Non-Technical-Users)

## Wiki pages

- [Setup for Non-Technical Users](Setup-for-Non-Technical-Users)
- [Setup cho nguoi khong ranh ky thuat](Setup-cho-nguoi-khong-ranh-ky-thuat)
- [Railway Deployment](Railway-Deployment)
- [Zalo Setup](Zalo-Setup)
- [Google Sheets Setup](Google-Sheets-Setup)
- [SePay Setup](SePay-Setup)
- [First Transaction Test](First-Transaction-Test)
- [Troubleshooting](Troubleshooting)
- [Security and Privacy](Security-and-Privacy)
- [Command Reference](Command-Reference)
- [Developer Guide](Developer-Guide)
- [FAQ](FAQ)
