# 📊 Financial Tracking Bot

A personal finance Telegram bot that hooks into your bank via SePay and asks you to categorize each transaction. Tracks your monthly spending in Google Sheets — with daily recaps, weekly summaries, and monthly reports. **Budget allocation is optional** — the bot works as a pure tracker out of the box.

---

## Demo
[![Watch the demo](https://img.youtube.com/vi/4e6c7c4HcbM/0.jpg)](https://youtube.com/shorts/uw31SR4ba8A)
```
Bank transaction happens
  → SePay notifies the bot
    → Bot asks "where did this money go?"
      → You tap a category
        → Bot logs it to Google Sheets + shows tổng tháng
          (% of budget if you set one — totally optional)
```

---

## What you'll need before starting

| Requirement | Where to get it |
|-------------|----------------|
| A Telegram account | You probably have one |
| A SePay account | [sepay.vn](https://sepay.vn) — connects to your Vietnamese bank |
| A Google account | For Google Sheets + Google Cloud |
| A server or VPS | Any Linux VPS (Ubuntu 22.04 recommended), or run locally with [ngrok](https://ngrok.com) for testing |
| Python 3.11+ | On your server |

---

## Step 1 — Create your Telegram Bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** — looks like `123456789:ABCdef...`
4. Message **@userinfobot** to get your personal **chat ID** — looks like `987654321`

---

## Step 2 — Set up Google Sheets

### 2a. Create the spreadsheet

Create a new Google Sheet and add these tabs (exact names matter):

| Tab name | Purpose |
|----------|---------|
| `Đầu ra` | All transactions |
| `Budget Config` | Monthly budget buckets |
| `Sub-category Config` | Sub-labels per bucket |
| `Bot State` | Bot conversation state (don't touch) |
| `Monthly Reports` | Archived monthly summaries |

### 2b. Set up column headers

**`Đầu ra` tab — row 1 headers:**
```
A: ID  |  B: Date  |  C: -  |  D: -  |  E: -  |  F: Description
G: Type  |  H: Amount  |  I: Ref Code  |  J: Cumulative
K: Category  |  L: Sub-category  |  M: Is Daily  |  N: Confirmed  |  O: Month
```

**`Budget Config` tab — row 1 headers:**
```
A: Month  |  B: Bucket ID  |  C: Name  |  D: Allocated  |  E: Daily Cap  |  F: Active  |  G: Source  |  H: -
```

> **Note:** The `Allocated` column is **optional**. Set it to `0` (or leave blank) to enable tracking-only mode for that category — the bot will just log spending totals without comparing to a budget. Set a positive number to enable budget alerts.

**`Sub-category Config` tab — row 1 headers:**
```
A: Bucket ID  |  B: Key  |  C: Label  |  D: Active
```

**`Bot State` tab — row 1 headers:**
```
A: Chat ID  |  B: State JSON  |  C: Updated At
```

**`Monthly Reports` tab — row 1 headers:**
```
A: Month  |  B: Bucket  |  C: Allocated  |  D: Spent  |  E: Remaining  |  F: %  |  G: Timestamp
```

### 2c. Create a Google Service Account

This lets the bot read/write your sheet without logging in as you.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Give it any name, click through the steps
6. On the service account page, go to **Keys → Add Key → JSON**
7. Download the file — rename it to `credentials.json`
8. Copy the service account **email** (looks like `bot@your-project.iam.gserviceaccount.com`)
9. **Share your Google Sheet** with that email (Editor access), just like sharing with a person

---

## Step 3 — Set up SePay

1. Create an account at [sepay.vn](https://sepay.vn)
2. Connect your bank account
3. Go to **Webhook settings** and set the URL to:
   ```
   https://your-server-ip-or-domain/webhook
   ```
4. **Important:** Disable SePay's built-in Google Sheets integration if you have it turned on — the bot handles its own writing and having both active will create duplicate rows.

---

## Step 4 — Set up the server

### Install dependencies

```bash
# On your VPS (Ubuntu 22.04)
apt update && apt install -y python3.11 python3-pip python3-venv

cd /root
git clone https://github.com/your-username/financial-tracking-bot.git financial-tracking-bot
cd financial-tracking-bot

python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn gspread google-auth python-dotenv pytz
```

### Configure secrets

```bash
cp .env.example .env
nano .env   # fill in your BOT_TOKEN, CHAT_ID, SHEET_ID
```

Upload your `credentials.json` to the project folder:
```bash
# From your local machine
scp credentials.json root@your-server:/root/financial-tracking-bot/
```

Lock down the file so only your user can read it:
```bash
chmod 600 credentials.json
chmod 600 .env
```

### Register the webhook with Telegram

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-server-ip/webhook"
```

### Run as a systemd service (auto-restart, survives reboots)

Create the service file:
```bash
nano /etc/systemd/system/financial-tracking-bot.service
```

Paste this (adjust paths if needed):
```ini
[Unit]
Description=financial-tracking-bot
After=network.target

[Service]
WorkingDirectory=/root/financial-tracking-bot
ExecStart=/root/financial-tracking-bot/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=/root/financial-tracking-bot/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable financial-tracking-bot
systemctl start financial-tracking-bot
systemctl status financial-tracking-bot   # should say "active (running)"
```

### Set up cron jobs (scheduled reports)

```bash
crontab -e
```

Add these lines (times are in your server's local timezone — check with `date`):

```
# Daily recap at 11 PM
0 23 * * * curl -s -X POST http://localhost:8000/trigger/daily-recap

# Weekly summary every Sunday at 2 PM
0 14 * * 0 curl -s -X POST http://localhost:8000/trigger/weekly

# Monthly allocation prompt — 2 AM on the 1st
0 2 1 * * curl -s -X POST http://localhost:8000/trigger/monthly-allocation

# Monthly report — last day of month at 2 PM
0 14 28-31 * * [ $(date -d tomorrow +\%d) -eq 1 ] && curl -s -X POST http://localhost:8000/trigger/monthly-report
```

> ⚠️ If your server is in UTC but you're in UTC+7, shift all hours by -7. Example: 11 PM local = 16:00 UTC.

---

## Step 5 — First run

1. Start a chat with your bot on Telegram
2. Make a small test transaction through your bank — the bot will auto-create default tracking categories and ping you to categorize within seconds
3. Tap a category to assign the transaction
4. (Optional) Send `/allocate` to set spending limits for any category
5. Send `/manage` anytime to add, rename, or delete categories

---

## Bot commands

| Command | What it does |
|---------|-------------|
| `/status` | Monthly overview — all categories, % spent (for budgeted) |
| `/today` | How much you've spent today vs daily limit |
| `/manage` | Add / rename / delete categories |
| `/allocate` | (Optional) set or update budget for this month |
| `/weekly` | Spending breakdown for the past 7 days |
| `/report` | Full monthly summary |

---

## Customizing bucket categories

Edit `config.py` to change default bucket IDs or the daily spending bucket:

```python
DAILY_BUCKET_ID = "daily_spending"   # change this if you rename your daily bucket
```

To add sub-categories for a bucket, either type a custom one when prompted after a transaction, or manually add rows to the `Sub-category Config` sheet:

```
A: bucket_id  |  B: key  |  C: Display Label  |  D: TRUE
```

---

## Security notes ⚠️

A few things to be careful about — especially since this handles bank data:

**1. Protect your `.env` and `credentials.json`**
These two files are the keys to your bot. Anyone with them can read your spending data.
```bash
chmod 600 .env credentials.json
```
Never commit either file to GitHub. The `.gitignore` already blocks them.

**2. Your webhook URL has no authentication**
Right now anyone who knows your URL can send fake transactions to the bot. For personal use this is low risk, but if you care: add a secret token check to the `/webhook` endpoint and configure the same token in SePay.

**3. Use SSH keys instead of passwords**
Password-based SSH is brute-forceable. Switch to key-based auth:
```bash
# On your local machine
ssh-keygen -t ed25519
ssh-copy-id root@your-server
```
Then disable password auth in `/etc/ssh/sshd_config`:
```
PasswordAuthentication no
```

**4. The bot only talks to your chat ID**
`CHAT_ID` is checked on every message — no one else can interact with your bot even if they find it.

**5. No banking credentials stored anywhere**
The bot only receives transaction notifications (amount + description) from SePay. Your bank login, card numbers, etc. never pass through this code.

---

## Updating the bot

```bash
# On your server
cd /root/financial-tracking-bot
git pull
systemctl restart financial-tracking-bot
journalctl -u financial-tracking-bot -f   # watch logs
```

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| No message when transaction happens | Is the service running? `systemctl status financial-tracking-bot` |
| Bot crashed | `journalctl -u financial-tracking-bot -n 50` |
| Wrong amounts in sheet | Check logs for `DEBUG append_transaction` |
| Duplicate rows in sheet | Make sure SePay's native Sheets integration is disabled |
| Daily recap at wrong time | Check server timezone with `date`, adjust cron hours accordingly |
| `/allocate` not saving | Check logs for `DEBUG write_budget_row` |

---

## Project structure

```
.
├── main.py                  # FastAPI entry point — routes all webhooks
├── config.py                # Reads env vars, sheet tab names
├── sheets.py                # All Google Sheets read/write logic
├── telegram_api.py          # Telegram Bot API wrapper
├── handlers/
│   ├── sepay.py             # Handles incoming bank transactions, auto-bootstraps default categories
│   ├── transaction.py       # Category picker + confirmation flow
│   ├── allocation.py        # (Optional) monthly budget setup flow
│   ├── manage.py            # Add / edit / delete categories
│   └── reports.py           # Status, daily, weekly, monthly reports
├── .env.example             # Template — copy to .env and fill in
├── .gitignore               # Keeps secrets out of git
└── README.md                # This file
```

---

## License

MIT — use it, break it, make it yours.
