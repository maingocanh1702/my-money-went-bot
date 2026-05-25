# 📊 Financial Tracking Bot

A Telegram bot that ingests Vietnamese bank notifications via [SePay](https://sepay.vn) and turns them into a per-account, per-category spending report — backed entirely by a Google Sheet you own.

[🇻🇳 Tiếng Việt](README.vi.md)

```
Bank tx happens
  → SePay webhook → bot writes Transactions row
    → Auto-categorize if a /keywords rule matches the description (no prompt)
    → Otherwise: bot asks "what category?" (skipped entirely for income)
      → You tap a category
        → Tx appears in /report grouped by account + category
```

No backend database. No third-party data store. Single-tenant by design — one bot instance per user.

---

## Features

- **Per-account tracking** — every tx tagged with which bank account it came from. `/report` slices by account (TPB / Vietcombank / cash) and by category.
- **Multi-period reports** — `/report` switches between week / month / quarter / year via inline buttons.
- **Two report lenses** — category (default: budget bars + warnings) and account (flow per card). Toggle in-place.
- **Account onboarding** — auto-prompts when a tx arrives from an unmapped source. Short 3-step wizard: name → type → done.
- **Budget allocation** — `/allocate` sets monthly caps per category. Edit-mode shows existing buckets with per-bucket tap-to-edit (no re-walking the full wizard every time).
- **Auto-categorize** — `/keywords` defines patterns that auto-tag matching descriptions, skipping the picker entirely.
- **Backfill historical tx** — `/accounts assign <slug>` plus the col-U `account_source_key` mechanism auto-attribute legacy txs to a newly-onboarded account.

---

## Commands

| Command | What it does |
|---------|--------------|
| `/today` | Today's spending vs daily cap (Daily Spending bucket). |
| `/report [period]` | Unified spending report. Default = month + category lens. Inline buttons switch period (tuần/tháng/quý/năm) + lens (account/category). |
| `/accounts` | List configured accounts. `/accounts add` opens the wizard. `/accounts assign <slug>` bulk-attributes unmapped historical txs. |
| `/manage` | Add / rename / delete categories. Per-bucket edit-amount. |
| `/keywords` | Manage auto-categorize rules. |
| `/allocate` | Edit budget. First run = wizard. Subsequent runs = edit-mode (per-bucket buttons). |

---

## Architecture

```
┌──────────┐   webhook    ┌────────────────┐    write     ┌──────────────┐
│  SePay   │ ───────────► │  FastAPI bot   │ ───────────► │ Google Sheet │
└──────────┘              │  (Railway/VPS) │              │   (yours)    │
                          └──────┬─────────┘              └──────────────┘
                                 │ Telegram Bot API
                                 ▼
                          ┌────────────────┐
                          │   You (chat)   │
                          └────────────────┘
```

**Source of truth = ledger table**. `running_balance` / `outstanding_balance` are caches recomputed from the ledger on every write. See `handlers/account_resolver.py` and `sheets.py` for details.

Sheet tabs (auto-created on first run):

| Tab | Purpose |
|-----|---------|
| `Đầu ra` | All transactions (one row per tx, cols A–U). |
| `Accounts` | Onboarded accounts (name, type, currency, source_keys mapped). |
| `Account Ledger` | Append-only ledger entries — source of truth for balances. |
| `Pending Accounts` | Onboarding queue for tx whose source isn't mapped yet (24h TTL). |
| `Budget Config` | Per-month bucket allocations. |
| `Sub-category Config` | Sub-labels per bucket (optional). |
| `Keyword Rules` | Auto-categorize patterns. |
| `Bot State` | Wizard / picker state per chat (ephemeral). |
| `Monthly Reports` | Archived monthly summaries. |

---

## Quick start

You'll need:

- Telegram account
- [SePay](https://sepay.vn) account connected to your VN bank
- Google account (Sheets + Cloud Console)
- A server with public HTTPS endpoint — [Railway](https://railway.app) is the simplest. Or any Ubuntu VPS + ngrok for testing.
- Python 3.11+

### 1 — Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Message [@userinfobot](https://t.me/userinfobot) → copy your chat ID.

### 2 — Google service account

1. [console.cloud.google.com](https://console.cloud.google.com) → new project.
2. Enable **Google Sheets API** + **Google Drive API**.
3. **IAM & Admin → Service Accounts → Create Service Account** → **Keys → Add Key → JSON** → download as `credentials.json`.
4. Create a new Google Sheet. Note the SHEET_ID from the URL.
5. Share the sheet with the service account email (Editor access).
6. Tabs auto-create on first webhook — no manual schema setup needed.

### 3 — SePay webhook

1. Create [sepay.vn](https://sepay.vn) account, connect your bank.
2. **Webhook settings** → URL = `https://<your-domain>/webhook`. Enable both "Tiền vào" and "Tiền ra".
3. **Disable SePay's native Google Sheets integration** if enabled — this bot writes its own rows; doubling = duplicates.

### 4 — Deploy

```bash
git clone https://github.com/<your-user>/financial-tracking-bot.git
cd financial-tracking-bot
cp .env.example .env
# Edit .env with BOT_TOKEN, CHAT_ID, SHEET_ID, GOOGLE_CREDS (or GOOGLE_CREDS_JSON)
```

**Railway** (recommended):

1. Push to GitHub.
2. New Railway project → connect repo.
3. Add env vars from `.env`. For `GOOGLE_CREDS_JSON`, paste the full credentials JSON as a single line.
4. Railway gives you a `*.up.railway.app` URL — use that as your SePay webhook.
5. Register the Telegram webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://<your-app>.up.railway.app/webhook"
   ```

**VPS** (Ubuntu 22.04):

```bash
apt install -y python3.11 python3-pip python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
chmod 600 .env credentials.json

# systemd service
sudo tee /etc/systemd/system/finbot.service <<EOF
[Unit]
Description=Financial Tracking Bot
After=network.target
[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
EnvironmentFile=$(pwd)/.env
Restart=always
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now finbot
```

### 5 — First run

1. Trigger any small bank tx.
2. Bot pings: "Account chưa map" + "Khoản này thuộc mục nào?". Tap Setup → wizard. Tap a category.
3. Future txs from the same account auto-route.
4. Type `/report` to see the breakdown.

---

## Known limitations & security considerations

**Single-tenant.** One bot instance per user. To serve multiple users, you'd need a multi-tenant refactor (database per user, user-scoped webhooks, etc.) — out of scope for this codebase.

**No PII redaction.** The `Description` column stores raw SePay payload text, which can contain partner names, account numbers, and other PII. Anyone with read access to your Sheet sees this. Self-hosted only.

**Webhook auth is opt-in.** SePay's API key check is supported via the `SEPAY_SECRET` env var. If unset, the webhook accepts any caller who knows the URL. **Recommended:** set the secret and put Cloudflare or another WAF in front.

**No automatic credit-card-statement parsing.** Credit-card payments must be logged manually via `/cc pay`. Auto-detection from SePay bank-side ("transfer to credit card") is deferred to a later phase.

**Income (Tiền vào) is not categorized.** Project goal is tracking *spending*. Incoming tx just land in Transactions and surface in `/report` per-account flow.

---

## Roadmap (deferred)

- **Credit card support** — outstanding balance, utilization %, `/cc pay`, statement-cycle reset. Out of Phase 1 OSS scope; the underlying ledger model already supports it but the wizard / command surface ships with bank/debit/cash only.
- **Manual `/transfer` between tracked accounts** — bank → bank internal moves. Out of Phase 1 scope.
- **Email ingestion** for bank notification emails (TCB, Cake, HSBC, ...) — Phase 1 ships SePay only.
- **TRANSFERS section in /report** to separate transfer-like buckets (Saving, etc.) from spending totals.
- **Multi-tenant SaaS** — would require a separate codebase (user database, per-user Sheet, webhook scoping). Out of scope for this repo.

---

## Development

```bash
pip install -r requirements.txt
pytest tests/unit/ -v
```

121 unit tests use an in-memory FakeSpreadsheet (no Google API calls). Tests with `@freeze_time` need `freezegun` for deterministic period assertions.

---

## License

[MIT](LICENSE) — fork it, ship it, sell it.

If you build something cool on top, a backlink or shoutout is appreciated but not required.
