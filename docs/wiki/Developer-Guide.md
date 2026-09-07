# Developer Guide

This page is for people who want to run, test, or modify the code locally.

## Local setup

```bash
git clone https://github.com/maingocanh1702/my-money-went-bot.git
cd my-money-went-bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Fill `.env` with your own values.

For local Google credentials, you can use:

```env
GOOGLE_CREDS=credentials.json
```

## Run tests

```bash
pytest tests/unit/ -v
```

There are 440+ unit tests. They use an in-memory fake spreadsheet and never call Google APIs, so the whole suite runs in about a second.

CI also runs `python3 scripts/check_no_personal_data.py`, which fails the build if a real account identifier, secret, or home-directory path lands in the tree. Run it before opening a pull request.

## Main files

| File or folder | Purpose |
|---|---|
| `main.py` | FastAPI entrypoint and webhook routes |
| `config.py` | Environment variables and sheet tab names |
| `sheets.py` | Google Sheets read/write logic |
| `telegram_api.py` | Telegram Bot API wrapper |
| `messenger.py` | Dual-channel send (Telegram + Zalo); strips markup for Zalo |
| `utils.py` | Money parsing, and `md_safe` for text that came from outside |
| `handlers/sepay.py` | SePay + e-mail webhook handling, dedup, exclusion ledger |
| `handlers/email_parser.py` | Bank notification e-mail → transaction |
| `handlers/account_resolver.py` | Which account a transaction belongs to |
| `handlers/transaction.py` | Transaction categorization flow |
| `handlers/accounts.py` | Account onboarding and assignment |
| `handlers/cashback.py`, `handlers/cashback_engine.py` | Cashback rules and the pure money math |
| `handlers/allocation.py`, `handlers/manage.py`, `handlers/keywords.py` | Budgets, category management, auto-categorize rules |
| `handlers/report.py`, `handlers/reports.py` | `/report` and the scheduled summaries |
| `handlers/zalo_render.py`, `handlers/zalo_queue.py` | Zalo rendering and picker state |
| `card_templates/` | YAML card definitions, their schema and validator |
| `scripts/` | Operational helpers — privacy guard, parity check, webhook simulator |
| `handlers/report.py` | Reporting |
| `tests/unit/` | Unit tests |

## Production notes

Production always requires `SEPAY_SECRET` and `CRON_SECRET`, plus the variables for **at least one chat channel**:

- Telegram channel: `BOT_TOKEN`, `CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`
- Zalo channel: `ZALO_ENABLED`, `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID`, `ZALO_SECRET_TOKEN`

The app refuses to start unless at least one channel is fully configured (validation is skipped in test mode, i.e. when `BOT_TOKEN` starts with `test:`). `BOT_TOKEN`/`CHAT_ID` are optional — a Zalo-only deployment runs without them.

## Contributing

For behavior changes:

- Add or update tests.
- Keep changes scoped.
- Match existing code style.
- Include screenshots for Telegram UX changes when useful.
