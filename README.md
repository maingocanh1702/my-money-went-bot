# 💰 My Money Went Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[🇻🇳 Tiếng Việt](README.vi.md)

![My Money Went Bot — automatic transaction tracking for Vietnamese bank accounts and credit cards, written to a Google Sheet you own and categorized from Telegram or Zalo](docs/screenshots/banner.png)

**Automatic transaction tracking for your Vietnamese bank accounts and your credit cards.** Every transaction lands in a Google Sheet you own and gets categorized from Telegram or Zalo — no manual entry, no bank login, no third-party data store.

> 🙏 **Credits:** built on top of patterns from [`maddyle8124/spend-less-bot`](https://github.com/maddyle8124/spend-less-bot). Big thanks to Maddy — without that seed this wouldn't exist.

---

## What it does

![How it works — a bank account transaction arrives by SePay webhook and a credit-card swipe arrives as a notification email via Gmail and Apps Script; the bot deduplicates, resolves the account and categorizes it; the row lands in your Google Sheet and comes back to you on Telegram or Zalo](docs/screenshots/how-it-works.png)

**My Money Went Bot is a personal expense tracker that lives in your Telegram (or Zalo) chat.** It catches your transactions the moment they happen, from two sources at once:

- **Vietnamese bank accounts** — link them to [SePay](https://sepay.vn) and every transfer, card payment or salary arrives as a webhook within seconds. SePay's free plan covers 50 transactions a month; see [What SePay costs](#what-sepay-costs).
- **Credit cards** — your bank emails you for every swipe, and a small Google Apps Script forwards those emails to the bot. This also covers any bank SePay hasn't signed. Costs nothing.

Either way the transaction is written to a Google Sheet *you own*, tagged with the account it came from, and categorized with one tap — or with no tap at all, once you've taught the bot a keyword rule. `/report` then slices everything by account, by category, and by week / month / quarter / year.

On top of that tracking sit the things you'd otherwise do by hand: monthly budgets per category, credit-card balances and payments, and **cashback tracking** that tells you what each swipe earned before the statement closes.

<details>
<summary>📐 Detailed flow — the two sources, categorizing, and the cashback branch</summary>

```mermaid
flowchart TD
    A[🏦 Bank account<br/>money in / out] -->|SePay webhook| B[🤖 Bot<br/>dedup → resolve account]
    A2[💳 Card notification<br/>email] -->|Gmail → Apps Script| B
    B -.->|source not mapped yet| I[📝 Onboard wizard<br/>name → type → done]
    I -.->|later tx auto-route| B
    B --> C[📊 Row in your<br/>Google Sheet]
    C --> D{Keyword rule<br/>matches?}
    D -->|✅ yes| E[🎯 Auto-categorized]
    D -->|❌ no| F[💬 You tap a category]
    E --> H[📈 /report<br/>account × category × period]
    F --> H
    C --> K{Credit card?}
    K -->|yes| L[💰 Cashback engine<br/>MCC → rate → per-tx tier<br/>→ cycle cap → daily limit → gate]
    L --> M[🧾 Cashback Ledger<br/>one line per swipe]
    M --> N[💳 /cashback<br/>this statement cycle]

    classDef bank fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef bot fill:#dbeafe,stroke:#2563eb,color:#1e40af
    classDef store fill:#dcfce7,stroke:#16a34a,color:#15803d
    classDef user fill:#fce7f3,stroke:#db2777,color:#9d174d
    classDef out fill:#f3e8ff,stroke:#9333ea,color:#6b21a8
    class A,A2 bank
    class B,E,I,L bot
    class C,M store
    class F user
    class H,N out
```

</details>

**No database. No third-party data store. Single-tenant — one bot per person.** Your Google Sheet IS the entire backend. Your data, your sheet, your rules.

---

## Why this exists

Most personal finance apps (Money Lover, Misa, MoneyKeeper, ...) want your bank credentials, run on their cloud, and gatekeep your data behind a freemium wall. This bot does the opposite:

- **You own the data.** It lives in your Google Sheet. Export, fork, archive, pivot — your call.
- **You see every line of code.** ~3,000 LOC of Python. Audit, customize, ship.
- **You categorize once.** Auto-categorization via `/keywords` means recurring tx (Spotify, Grab, ...) skip the picker.
- **Reports match your real model** — per-account *and* per-category, across week/month/quarter/year. Not just "monthly category bar chart".
- **Nothing is entered by hand.** Both a bank transfer and a card swipe reach the sheet on their own, so the record is complete rather than whatever you remembered to type in.

---

## Features

![Feature overview — how transactions are caught from both sources, categorizing and reporting, cashback tracking, the system architecture, supported banks, and the command list](docs/screenshots/features-architecture.png)

The full feature breakdown.

### Catching every transaction

🏦 **Bank accounts, via SePay** — every transfer, card payment or salary that touches a linked account arrives as a webhook within seconds and is tagged with the account it came from. Enable *Tiền ra* only for spending, or both directions to see income too.

📧 **Credit cards and other banks, via notification email** — `google_apps_script.js` polls Gmail every minute, forwards each notification email exactly once (deduplicated by message id, not by thread) to `/webhook/email`, and `handlers/email_parser.py` turns it into the same transaction payload SePay would have sent. Everything downstream — accounts, categories, reports, cashback — is identical whichever way a transaction arrived.

🔍 **No duplicates, no gaps** — a transaction that arrives twice (once from SePay, once by email) is dropped by a fuzzy cross-source check, and a webhook retried by SePay is caught by a durable reference ledger.

🤖 **Smart account onboarding** — the first time a transaction arrives from an unmapped source, the bot asks. Three-step wizard: name → type → done (a credit card also asks for limit, statement day and due day). Later transactions from that source route themselves.

🔁 **Historical backfill** — `/accounts assign <slug>` retroactively links unmapped past transactions to a newly-onboarded account, so nothing is lost between "first webhook" and "wizard complete".

### Making sense of it

⚡ **Auto-categorize** — `/keywords` lets you define patterns ("GRAB" → Daily Spending, "Spotify" → Subscription). Matching transactions skip the prompt entirely.

📊 **Unified `/report` with 2 lenses × 4 periods** — week/month/quarter/year via inline buttons. Toggle account ↔ category lens in-place. No re-typing the command.

🎯 **Smart budget allocation** — `/allocate` sets monthly caps per category. After setup, it returns in *edit mode* — tap one bucket to change its limit, no re-walking the full wizard.

🧾 **Balances and transfers** — outstanding balance per credit card, `/cc pay` to record a payment, `/transfer` for moves between your own accounts, all on an append-only ledger.

### Credit-card cashback

💳 **Cashback tracking** — because the bot already sees every swipe, it can also work out what each one earned. It classifies the merchant into an MCC using a self-learning keyword → MCC map (when it can't tell, it asks once with the card's categories as buttons and remembers your answer), then applies the card's rate, per-transaction tier caps, the per-category cap for the cycle, daily transaction limits and the activation gate (e.g. "spend 5,000,000đ this cycle to unlock"). Cashback shows as *pending* until the gate is met, and every 0đ line carries a reason (`mcc_unknown`, `mcc_not_eligible`, `daily_limit`, `mcc_cap_full`) so the ledger is auditable. Wrong? Tap **Sai CB** to void it.

🗓 **Statement-cycle aware** — caps and gates reset on the card's statement day, not on the 1st (`cap_period: statement_cycle` or `calendar_month`, per card). `/cashback` shows the live cycle: per-category progress bars, cycle total, spend vs gate, and "need X more to activate".

📇 **Card templates in YAML** — `card_templates/cake_freedom.yaml` for a real card, `card_templates/example_visa.yaml` for the fields it doesn't use. `/cashback seed cake_freedom` applies one in seconds; `/cashback setup` walks you through a card no template covers; `/cashback export` turns a tuned config back into a template you can share. Adding a card nobody has covered is a pull request, not a code change.

### Everywhere

💬 **Zalo channel** — the same flows on Zalo Bot Platform via numbered text menus: category picker, `/report`, `/manage`, `/allocate`, `/keywords`, `/cashback`, `/recat`, `/pending`.

🌐 **Bilingual UI** — `/lang` switches the whole bot between Vietnamese and English.

🇻🇳 **Vietnamese banks, VND-first** — works with anything SePay supports plus any bank you add an email parser for. A foreign-currency account (HKD, USD, ...) is tracked per-account without polluting VND totals or the daily cap.

---

## Screenshots

**Tracking and reporting.** A transaction auto-categorized from a keyword rule, and the same month reported by category and by account:

<table>
  <tr>
    <td><img src="docs/screenshots/auto-categorize.png" alt="A transaction auto-categorized from a keyword rule, with the budget bar updating" /></td>
    <td><img src="docs/screenshots/report-monthly.png" alt="Monthly report with budget bars and tracking buckets" /></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/report-monthly-category-telegram.png" alt="Category-lens monthly report" /></td>
    <td><img src="docs/screenshots/report-monthly-account-telegram.png" alt="Account-lens monthly report — the same month sliced per bank account" /></td>
  </tr>
</table>

**Cashback.** A Grab ride on a Cake Freedom card: the transaction is logged, the cashback line shows what it earned and that it is still pending, and the gate bar shows how far the cycle is from activation. `/cashback` gives the whole statement cycle at a glance:

<table>
  <tr>
    <td><img src="docs/screenshots/cashback-transaction-telegram.png" alt="A credit-card transaction logged with its cashback line, category cap and activation-gate progress, followed by the keyword-rule prompt" /></td>
    <td><img src="docs/screenshots/cashback-overview-telegram.png" alt="/cashback overview for one statement cycle: rate, gate, billing days, per-category caps with progress bars, cycle total and the amount still needed to activate" /></td>
  </tr>
</table>

The same flows on Zalo — keyword rules and an auto-categorized transaction:

<img src="docs/screenshots/zalo-bot.PNG" width="48%" alt="Keyword rules and an auto-categorized transaction on Zalo" />

![Demo preview](docs/media/my-money-went-bot-demo-preview.gif)

[Watch the 54-second demo with audio](https://raw.githubusercontent.com/maingocanh1702/my-money-went-bot/main/docs/media/my-money-went-bot-demo.mp4) — one transaction flowing through Telegram, categorization and reporting.

---

## Supported banks and cards

### Bank accounts — via SePay

Whatever [SePay supports](https://sepay.vn/ngan-hang.html), this bot tracks. SePay directly connects to **10 Vietnamese banks** (as of 2026):

| Bank | Code |
|---|---|
| VPBank | VPB |
| ACB | ACB |
| Sacombank | STB |
| VietinBank | ICB |
| MBBank | MBB |
| BIDV | BIDV |
| MSB | MSB |
| TPBank | TPB |
| KienLongBank | KLB |
| OCB | OCB |

A subset (BIDV, MB, VietinBank, ACB, OCB, KienLongBank, MSB) use **direct API integration** for instant webhooks; the rest go through **SMS Banking** which has a slight delay. Either way the bot handles the payload identically.

#### What SePay costs

SePay's **Free** plan is 0đ/month and includes **50 transactions/month**. Going over is allowed — the extra transactions are billed afterwards (pay-as-you-go) — or you can move to a paid plan: **Startup** from 120,000đ/month with a much larger quota, or **Shop** at 70,000đ per store/month with unlimited transactions. SePay's FAQ counts *incoming* transactions toward the quota. For a one-person bot the free plan is usually enough; check the [pricing page](https://sepay.vn/bang-gia.html) and [FAQ](https://sepay.vn/faq.html) for the current terms, they change.

### Credit cards and other banks — via notification email

| Bank / card | Arrives as | Cashback template |
|---|---|---|
| Cake by VPBank — Freedom card | notification email | [`card_templates/cake_freedom.yaml`](card_templates/cake_freedom.yaml) |

Cake ships as the worked example. **Any bank that emails you a per-transaction notification can be added**, and it is deliberately small: one sender in `google_apps_script.js`, one `_parse_<bank>` in `handlers/email_parser.py` returning the same dict `_parse_cake` does, and — for a card — a YAML template ([`example_visa.yaml`](card_templates/example_visa.yaml) shows the fields Cake's template doesn't use). Nothing else changes: account resolution, dedup, categories, reports and the cashback engine are shared. The email path also costs nothing — Gmail and Google Apps Script are free — so it is the cheapest way to cover a bank SePay has not signed.

---

## What you'll need

| Requirement | Where to get it |
|---|---|
| Telegram account | You probably have one |
| [SePay](https://sepay.vn) account | Connects to your Vietnamese bank accounts (free plan: 50 tx/month) |
| Google account | For Google Sheets + Google Cloud — and Gmail + Apps Script if you use the email path |
| Server with public HTTPS | [Railway](https://railway.app) is simplest (free tier OK). Or Ubuntu VPS + [ngrok](https://ngrok.com) for testing. |
| Python 3.11+ | On your server / Railway |

---

## Documentation

- [Quick intro](docs/QUICK_INTRO.md) — what the bot is, in five minutes.
- [AI assistant setup guide](docs/AI_SETUP.md) — paste one prompt into Claude, ChatGPT or Cursor and be walked through the whole setup.
- Not technical? Start with [Setup for non-technical users](https://github.com/maingocanh1702/my-money-went-bot/wiki/Setup-for-Non-Technical-Users).
- Full [wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki): [Google Sheets](https://github.com/maingocanh1702/my-money-went-bot/wiki/Google-Sheets-Setup) · [SePay](https://github.com/maingocanh1702/my-money-went-bot/wiki/SePay-Setup) · [Railway deployment](https://github.com/maingocanh1702/my-money-went-bot/wiki/Railway-Deployment) · [Zalo](https://github.com/maingocanh1702/my-money-went-bot/wiki/Zalo-Setup) · [First transaction test](https://github.com/maingocanh1702/my-money-went-bot/wiki/First-Transaction-Test) · [Command reference](https://github.com/maingocanh1702/my-money-went-bot/wiki/Command-Reference) · [Troubleshooting](https://github.com/maingocanh1702/my-money-went-bot/wiki/Troubleshooting) · [Security and privacy](https://github.com/maingocanh1702/my-money-went-bot/wiki/Security-and-Privacy) · [Developer guide](https://github.com/maingocanh1702/my-money-went-bot/wiki/Developer-Guide)

The wiki pages are versioned in this repo under `docs/wiki/` — edit them there and send a pull request.

---

## Quick start

### Step 1 — Create your Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → save the token.
2. Message [@userinfobot](https://t.me/userinfobot) → save your chat ID.

### Step 2 — Set up Google Sheets

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → new project.
2. Enable **Google Sheets API** + **Google Drive API**.
3. **IAM & Admin → Service Accounts → Create** → **Keys → Add Key → JSON** → download as `credentials.json`.
4. Create a new Google Sheet. Copy the **SHEET_ID** from the URL.
5. Share the sheet with the service account email (Editor access).

**Sheet tabs auto-create on first webhook** — no manual schema setup. Tabs:

| Tab | Purpose |
|---|---|
| `Đầu ra` | All transactions (one row per tx) |
| `Accounts` | Onboarded accounts (name, type, source_keys) |
| `Account Ledger` | Append-only ledger — source of truth for balances |
| `Pending Accounts` | Onboarding queue (24h TTL) |
| `Budget Config` | Per-month bucket allocations |
| `Sub-category Config` | Optional sub-labels per bucket |
| `Keyword Rules` | Auto-categorize patterns |
| `Bot State` | Wizard / picker state per chat |
| `Monthly Reports` | Archived monthly summaries |
| `Cashback Rules` | MCC-based cashback rules per card |
| `Cashback Tx Tiers` | Per-transaction cap tiers |
| `Cashback Card Config` | Card cashback settings (rate, gate, period) |
| `Cashback Ledger` | Per-MCC cashback earned per cycle |
| `MCC Map` | Keyword → MCC code mapping |

### Step 3 — Set up SePay

1. Sign up at [sepay.vn](https://sepay.vn), connect your bank account(s). The Free plan (50 transactions/month) is enough to start — see [What SePay costs](#what-sepay-costs).
2. **Webhook settings** → URL = `https://<your-domain>/webhook`, authentication = **API Key** with the value of your `SEPAY_SECRET`. Pick which directions to track:
   - **Only spending** → enable **Tiền ra** only.
   - **Spending + income** → enable both **Tiền ra** and **Tiền vào**.

   (Income tx are logged but skip the category picker — see [Why this exists](#why-this-exists).)
3. ⚠️ **Disable SePay's native Google Sheets integration** — this bot writes its own rows; doubling = duplicate transactions.

Credit cards and banks SePay doesn't cover come in through email instead — see [Step 6](#step-6--track-your-credit-cards-too-optional).

### Step 4 — Deploy

```bash
git clone https://github.com/maingocanh1702/my-money-went-bot.git
cd my-money-went-bot
cp .env.example .env
# Fill the required values in .env: BOT_TOKEN, CHAT_ID, SHEET_ID,
# GOOGLE_CREDS_JSON (or GOOGLE_CREDS=credentials.json), SEPAY_SECRET,
# TELEGRAM_WEBHOOK_SECRET, CRON_SECRET, EMAIL_SECRET
# (plus ZALO_SECRET_TOKEN when ZALO_ENABLED=true)
```

**Railway** (recommended):

1. Push your fork to GitHub.
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Add every required env var in the Railway dashboard. For `GOOGLE_CREDS_JSON`, paste the full JSON as one line; generate a distinct long random value for each `*_SECRET` variable. If Zalo is enabled, set `ZALO_SECRET_TOKEN` too.
4. Railway gives you a `*.up.railway.app` URL — use that as your SePay webhook URL.
5. Register the Telegram webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://<your-app>.up.railway.app/webhook" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```

**VPS** (Ubuntu 22.04):

```bash
sudo apt install -y python3.11 python3-pip python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
chmod 600 .env credentials.json

# systemd service
sudo tee /etc/systemd/system/mmwbot.service <<EOF
[Unit]
Description=My Money Went Bot
After=network.target
[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
EnvironmentFile=$(pwd)/.env
Restart=always
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now mmwbot
journalctl -u mmwbot -f   # watch logs
```

### Step 5 — First run

1. Open a chat with your bot on Telegram, send `/today` — bot should reply.
2. Make a small test transaction through your bank — within a few seconds the bot pings: *"Account chưa map"* + *"Khoản này thuộc mục nào?"*.
3. Tap **✅ Setup** → onboard the account (name → type).
4. Tap a category for the transaction.
5. Type `/report` → see your spending breakdown.

Future tx from the same account auto-route. Set up `/keywords` rules to auto-categorize recurring tx.

### Step 6 — Track your credit cards too (optional)

SePay covers bank accounts. Cards — and any bank SePay hasn't signed — reach the bot through their notification emails instead, forwarded by a Google Apps Script. Once a card is tracked you can also turn cashback on for it.

1. Generate `EMAIL_SECRET` (`openssl rand -hex 16`) and set it on Railway.
2. Go to [script.google.com](https://script.google.com) → New project → paste [`google_apps_script.js`](google_apps_script.js).
3. Replace the two placeholders at the top: `WEBHOOK_URL` = `https://<your-domain>/webhook/email`, `WEBHOOK_SECRET` = your `EMAIL_SECRET`.
4. Run `checkBankEmails` once to grant Gmail access, then run `bootstrapProcessed` once so the bot does not replay your whole inbox.
5. **Triggers → Add trigger** → `checkBankEmails` → time-driven → every minute.
6. Make one small purchase with the card. The bot pings; onboard the source as **🧾 Credit** (it asks for limit, statement day and due day).

Every swipe is now tracked like any other transaction. To add cashback on top, run `/cashback templates` → `/cashback seed cake_freedom <card-slug>` (or `/cashback setup <card-slug>` for a card no template covers); from then on each swipe replies with what it earned and `/cashback` shows the current statement cycle.

---

## Bot commands

| Command | What it does |
|---|---|
| `/today` | Today's spending vs daily cap (Daily Spending bucket). |
| `/report [period]` | Full spending report. Inline buttons for week/month/quarter/year × account/category lens. |
| `/accounts` | List configured accounts. `/accounts add` opens the wizard. `/accounts assign <slug>` bulk-tags historical txs. |
| `/manage` | Add / rename / delete categories. Per-bucket edit-amount. |
| `/keywords` | Manage auto-categorize rules. |
| `/allocate` | Edit budget. Wizard on first run, per-bucket edit-mode after. |
| `/cashback` | Credit-card cashback: rules, MCC map, billing cycle, overview. |
| `/cashback templates` | List available YAML card templates. |
| `/cashback seed <template> [cc]` | Apply a template — `cake_freedom`, or your own. |
| `/cashback setup [cc]` | Wizard to create custom cashback rules from scratch. |
| `/cashback export [cc]` | Export card config as YAML template. |
| `/cashback savetemplate [cc]` | Save current config as a reusable template. |
| `/transfer <amount> <from> <to>` | Record an internal transfer between tracked accounts. |
| `/cc pay <amount> [bank] <cc>` | Record a credit-card payment. |
| `/recat [row]` | Re-categorize a past transaction. No argument → pick from the 8 most recent; `/recat <row>` targets a sheet row directly. |
| `/pending` | Categorize transactions queued while you were mid-flow. |
| `/lang` | Switch bot language (vi/en). |
| `/cancel` | Abort the current multi-step flow. |
| `/help` | Command list. |

💡 Wherever the bot asks for an amount, Vietnamese shorthand works: `500k`, `3tr`, `3tr5`, `1m2`, `2 triệu` — all parsed as VND. Most commands also work on Zalo via numbered menus.

---

## Architecture

Two inputs, one pipeline, one spreadsheet.

```
 bank accounts                          credit cards / banks outside SePay
┌──────────────┐                        ┌──────────────┐   ┌─────────────────┐
│ VN bank      │  money in / out        │ Bank e-mail  │   │ Google Apps     │
│ (via SePay)  │ ──── webhook ───┐      │ notification │──►│ Script (Gmail,  │
└──────────────┘  POST /webhook  │      │              │   │ every minute)   │
                                 │      └──────────────┘   └────────┬────────┘
                                 ▼                                  │ POST /webhook/email
                    ┌────────────────────────────┐◄─────────────────┘
                    │  FastAPI bot (Railway/VPS) │
                    │  ├ email_parser  → same payload shape as SePay
                    │  ├ account_resolver → which account / card
                    │  ├ dedup (ref + fuzzy cross-source)
                    │  ├ transaction row + category (rule or tap)
                    │  └ cashback_engine → MCC · rate · tiers · caps · gate
                    └──────────────┬─────────────┘
                                   │ rows                 ┌────────────────┐
                                   ▼                      │ You            │
                    ┌────────────────────────────┐        │ Telegram / Zalo│
                    │ Google Sheet (yours)       │◄──────►│ tap category,  │
                    │ Đầu ra · Accounts · Ledger │ Bot API│ /report,       │
                    │ Cashback Ledger · MCC Map  │        │ /cashback      │
                    └────────────────────────────┘        └────────────────┘
```

**Source of truth = ledger tables.** `running_balance` is a cache recomputed from the `Account Ledger` on every write, and cashback is one `Cashback Ledger` line per transaction — `/cashback` is a read over that ledger for the current statement cycle, never a separately stored total. See [`handlers/account_resolver.py`](handlers/account_resolver.py), [`handlers/cashback_engine.py`](handlers/cashback_engine.py) and [`sheets.py`](sheets.py).

**The cashback pipeline, per transaction:** `email_parser` (or SePay) → `account_resolver` picks the card → the row is written → `cashback_engine` classifies the merchant via `MCC Map` (asking you once if it can't) → finds the card's rule for that MCC → applies the rule's rate (or the card's default) → caps it by the per-transaction tier → caps it by what's left of that MCC's cycle cap → checks the daily transaction limit → marks it *pending* until the cycle's spend passes the activation gate. The result is appended to `Cashback Ledger` and summarized in the reply. The engine is pure (no I/O) so all of that is unit-tested against an in-memory sheet.

### Project layout

```
.
├── main.py                       # FastAPI entry — routes all webhooks (TG + Zalo + email)
├── config.py                     # Reads env vars, sheet tab names
├── sheets.py                     # All Google Sheets read/write logic
├── telegram_api.py               # Telegram Bot API wrapper
├── messenger.py                  # Multi-channel send layer (Telegram + Zalo)
├── i18n/                         # UI strings — vi.py / en.py, /lang switches
├── handlers/
│   ├── sepay.py                  # Incoming SePay webhook handler
│   ├── email_parser.py           # Bank notification emails → SePay-shaped payload
│   ├── account_resolver.py       # Maps payload → account_id
│   ├── accounts.py               # /accounts wizard + onboarding + backfill
│   ├── transaction.py            # Category picker + confirmation flow
│   ├── allocation.py             # /allocate budget wizard + edit mode
│   ├── manage.py                 # /manage categories (+ daily cap)
│   ├── keywords.py               # /keywords auto-categorize rules
│   ├── cashback.py               # /cashback command (rules, MCC, cycles)
│   ├── cashback_engine.py        # Pure cashback computation (no I/O)
│   ├── report.py                 # Unified /report (account + category lenses)
│   ├── reports.py                # /today snapshot + daily recap
│   ├── zalo_queue.py             # Durable Zalo pending-tx queue (/pending)
│   └── zalo_render.py            # Zalo plain-text summaries
├── card_templates/               # YAML cashback card templates
│   ├── __init__.py               # Loader, validator, exporter, cache
│   ├── schema.py                 # CardTemplate, CardConfig, RuleConfig dataclasses
│   ├── validate.py               # Standalone CLI validator
│   ├── cake_freedom.yaml         # Cake by VPBank Freedom — a real card
│   └── example_visa.yaml         # Sample template: per-rule rates, calendar month
├── scripts/
│   ├── sim_webhook.py            # POST fake SePay / Cake payloads to a local bot
│   ├── cashback_reconcile.py     # End of cycle: ledger estimate vs what the bank actually paid
│   ├── check_no_personal_data.py # CI guard: no real account ids / secrets in the tree
│   └── check_parity.sh           # Diff this repo against a private fork
├── tests/unit/                   # Unit tests, in-memory FakeSpreadsheet
├── google_apps_script.js         # Gmail → /webhook/email forwarder (the email path)
├── .env.example                  # Template — copy to .env and fill in
├── crontab.txt                   # Example cron jobs (VPS reference; prod = GitHub Actions)
├── setup.sh                      # VPS bootstrap script
├── railway.toml                  # Railway deploy config
├── requirements.txt        # runtime dependencies
└── requirements-dev.txt    # runtime + test dependencies
```

---

## Security ⚠️

A few things to be careful about — this handles bank notification data:

**1. Protect your `.env` and `credentials.json`.** These are the keys to your bot. Anyone with them reads your spending data.

```bash
chmod 600 .env credentials.json
```

Never commit either to GitHub — `.gitignore` already blocks them.

**2. Webhook authentication is mandatory in production.** The app refuses to start until every secret below is configured. This prevents an accidentally public financial webhook.

| Env var | Protects | Without it |
|---|---|---|
| `SEPAY_SECRET` | `/webhook` (SePay payloads) | App will not start |
| `TELEGRAM_WEBHOOK_SECRET` | `/webhook` (Telegram updates) | App will not start |
| `CRON_SECRET` | `/trigger/*` | App will not start |
| `EMAIL_SECRET` | `/webhook/email` | App will not start |

For `TELEGRAM_WEBHOOK_SECRET`, re-register the webhook with the same value (`setWebhook` + `secret_token` — see `.env.example`). For `CRON_SECRET`, append `?secret=<value>` to the URLs in `crontab.txt`. Keep a WAF such as Cloudflare in front of your Railway app as an additional network layer.

**3. Use SSH keys, not passwords.** If you VPS-deploy, password SSH is brute-forceable:

```bash
ssh-keygen -t ed25519
ssh-copy-id root@your-server
# Then in /etc/ssh/sshd_config:
#   PasswordAuthentication no
```

**4. Bot only talks to your `CHAT_ID`.** Hardcoded check — no one else can interact even if they find the bot name.

**5. No banking credentials touch this code.** The bot receives transaction *notifications* (amount + description) from SePay. Your bank login, card numbers, etc. never pass through.

**6. PII in descriptions.** SePay's payload includes raw transfer descriptions which may contain partner names, account numbers, references. These get written to the `Description` column. Anyone with read access to your Sheet sees this — keep the Sheet private.

---

## Troubleshooting

| Problem | Check |
|---|---|
| No message when transaction happens | Service running? `systemctl status mmwbot` or Railway logs |
| Bot crashed | `journalctl -u mmwbot -n 50` |
| Wrong amounts in sheet | Check logs for `DEBUG append_transaction:` |
| Duplicate rows in sheet | Make sure SePay's native Sheets integration is disabled |
| Daily recap at wrong time | Server in UTC? Shift cron hours by -7 from ICT |
| `/allocate` not saving | Check logs for `[allocate]` messages |
| Bot doesn't auto-route tx from known account | Check that `source_keys` cell in `Accounts` tab has the right SePay account number |

---

## Updating the bot

```bash
# On your server
cd /path/to/my-money-went-bot
git pull
systemctl restart mmwbot
journalctl -u mmwbot -f   # watch logs
```

On Railway: just push to your fork, Railway auto-deploys.

---

## Roadmap (deferred)

Intentionally out of scope for now:

- 💬 **Facebook Messenger bot** — same UX as Telegram, another front-end.
- 🎮 **Discord bot** — for users who live in Discord, not Telegram.

Shipped from the original roadmap: credit cards + cashback, manual `/transfer`,
email ingestion for banks outside SePay, multi-currency accounts, and a Zalo
channel.

---

## Development

```bash
pip install -r requirements-dev.txt   # runtime + test dependencies
pytest tests/unit/ -v
```

440+ unit tests use an in-memory `FakeSpreadsheet` — zero Google API calls during tests. The cashback engine is pure, so its money math is tested line by line (caps, tiers, daily limits, gate, cycle boundaries). Tests with `@freeze_time` need `freezegun` for deterministic period assertions. CI also runs `scripts/check_no_personal_data.py`, which fails the build if a real account identifier or secret ever lands in the tree.

To poke a local bot without a bank: `python scripts/sim_webhook.py sepay --amount 50000 --type out --desc "highland"` or `... email-cake --amount 50000 --type out --desc "PAYOO BHX"`.

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup and pull-request expectations, and **[SECURITY.md](SECURITY.md)** for how to report a vulnerability and how to keep your own deployment's secrets safe.

The most useful contribution needs no Python: cashback cards are YAML in `card_templates/`, so adding one for a bank nobody has covered is a pull request, not a code change.

Contributions welcome — issue / PR / fork. Be opinionated about scope: this bot is intentionally minimal. Features outside the [Roadmap](#roadmap-deferred) are unlikely to be merged but happy to discuss.

When opening a PR:
- Include tests for new behavior.
- Match existing code style (functional helpers, docstrings, no over-engineering).
- For UX changes, attach a Telegram screenshot.

---

## Acknowledgments

This project started as a fork-and-rewrite of [`maddyle8124/spend-less-bot`](https://github.com/maddyle8124/spend-less-bot). The core idea — Telegram bot + SePay webhook + Google Sheet — comes from there. My Money Went Bot adds the credit-card cashback engine and YAML card templates, the email ingestion path for cards and banks outside SePay, per-account tracking with an append-only ledger, unified multi-period reports, the account onboarding wizard, a Zalo channel, and a number of UX refinements.

---

## License

[MIT](LICENSE) — fork it, ship it, sell it.

If you build something cool on top, a backlink or shoutout is appreciated but not required.
