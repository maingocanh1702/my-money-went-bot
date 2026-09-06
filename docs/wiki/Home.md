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

My Money Went Bot does two things, both into a Google Sheet you own, driven from **Telegram or Zalo** (two independent channels — set up either, or both):

- **Credit-card cashback tracking.** The bank's own notification emails (Cake by VPBank, Techcombank, Hang Seng, ...) reach the bot through a Google Apps Script. For every swipe the bot classifies the merchant into an MCC, applies the card's rate, per-transaction tiers, per-category caps, daily limits and the activation gate, and replies with what the swipe earned. `/cashback` shows the whole statement cycle. Cards are YAML templates in `card_templates/`.
- **Money in and out of your bank accounts.** SePay turns each bank notification into a webhook; the bot writes the row, tags the account, and asks for a category (or applies a keyword rule). Reports by account, category, and week/month/quarter/year. SePay's free plan covers 50 transactions a month — see [SePay Setup](SePay-Setup).

## Recommended setup path

Telegram and Zalo are independent channels — set up whichever you use, or both. The steps below show Telegram; for Zalo see [Zalo Setup](Zalo-Setup). For most users, use Railway:

1. Create a Telegram bot (or set up Zalo — see [Zalo Setup](Zalo-Setup)).
2. Create a Google Sheet.
3. Create Google service-account credentials.
4. Deploy this repo on Railway.
5. Connect SePay to the Railway webhook URL.
6. Set the Telegram webhook.
7. Test `/today` and one small transaction.
8. Optional — credit-card cashback: set up the Gmail → Apps Script forwarder (`google_apps_script.js`), onboard the card, then `/cashback seed <template>`. Steps are in the README under *Step 6 — Turn on credit-card cashback*.

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
