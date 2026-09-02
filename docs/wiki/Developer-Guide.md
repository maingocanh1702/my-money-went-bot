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

There are 120 unit tests. They use an in-memory fake spreadsheet and should not call Google APIs.

## Main files

| File or folder | Purpose |
|---|---|
| `main.py` | FastAPI entrypoint and webhook routes |
| `config.py` | Environment variables and sheet tab names |
| `sheets.py` | Google Sheets read/write logic |
| `telegram_api.py` | Telegram Bot API wrapper |
| `zalo_api.py` | Zalo Bot Platform API wrapper |
| `notifier.py` | Dual-channel notification fan-out (Telegram + Zalo) |
| `handlers/zalo_render.py` | Plain-text Zalo logged-summary renderer |
| `handlers/sepay.py` | SePay webhook handling |
| `handlers/transaction.py` | Transaction categorization flow |
| `handlers/accounts.py` | Account onboarding and assignment |
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
