# Developer Guide

This page is for people who want to run, test, or modify the code locally.

## Local setup

```bash
git clone https://github.com/maingocanh1702/my-money-went-bot.git
cd my-money-went-bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

Unit tests use an in-memory fake spreadsheet and should not call Google APIs.

## Main files

| File or folder | Purpose |
|---|---|
| `main.py` | FastAPI entrypoint and webhook routes |
| `config.py` | Environment variables and sheet tab names |
| `sheets.py` | Google Sheets read/write logic |
| `telegram_api.py` | Telegram Bot API wrapper |
| `handlers/sepay.py` | SePay webhook handling |
| `handlers/transaction.py` | Transaction categorization flow |
| `handlers/accounts.py` | Account onboarding and assignment |
| `handlers/report.py` | Reporting |
| `tests/unit/` | Unit tests |

## Production notes

Production requires these security variables:

- `SEPAY_SECRET`
- `TELEGRAM_WEBHOOK_SECRET`
- `CRON_SECRET`

The app refuses to start without them unless `BOT_TOKEN` starts with `test:`.

## Contributing

For behavior changes:

- Add or update tests.
- Keep changes scoped.
- Match existing code style.
- Include screenshots for Telegram UX changes when useful.

