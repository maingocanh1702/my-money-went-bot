# My Money Went Bot Wiki

This wiki is the longer, task-based manual for My Money Went Bot. The README is the front page; the wiki is where setup details, troubleshooting, privacy notes, and developer references live.

## Start here

- New user: [Setup for Non-Technical Users](Setup-for-Non-Technical-Users)
- Vietnamese user: [Setup cho nguoi khong ranh ky thuat](Setup-cho-nguoi-khong-ranh-ky-thuat)
- Deploying on Railway: [Railway Deployment](Railway-Deployment)
- Stuck during setup: [Troubleshooting](Troubleshooting)
- Want to understand privacy/security: [Security and Privacy](Security-and-Privacy)
- Want command examples: [Command Reference](Command-Reference)
- Want to develop locally: [Developer Guide](Developer-Guide)

## What the bot does

My Money Went Bot receives Vietnamese bank transaction notifications through SePay, writes each transaction to your own Google Sheet, and lets you categorize expenses from Telegram. Reports can be viewed by account, category, and period.

## Recommended setup path

For most users, use Railway:

1. Create a Telegram bot.
2. Create a Google Sheet.
3. Create Google service-account credentials.
4. Deploy this repo on Railway.
5. Connect SePay to the Railway webhook URL.
6. Set the Telegram webhook.
7. Test `/today` and one small transaction.

Detailed guide: [Setup for Non-Technical Users](Setup-for-Non-Technical-Users)

## Wiki pages

- [Setup for Non-Technical Users](Setup-for-Non-Technical-Users)
- [Setup cho nguoi khong ranh ky thuat](Setup-cho-nguoi-khong-ranh-ky-thuat)
- [Railway Deployment](Railway-Deployment)
- [Google Sheets Setup](Google-Sheets-Setup)
- [SePay Setup](SePay-Setup)
- [First Transaction Test](First-Transaction-Test)
- [Troubleshooting](Troubleshooting)
- [Security and Privacy](Security-and-Privacy)
- [Command Reference](Command-Reference)
- [Developer Guide](Developer-Guide)
- [FAQ](FAQ)
