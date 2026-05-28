# Agent Instructions

If you are an AI coding or setup agent helping a user run this repo, read `docs/AI_SETUP.md` first.

Default setup path: Railway.

For non-technical users:

- Do not ask them to edit source code.
- Do not ask them to commit secrets.
- Walk them through env vars one at a time.
- Keep real tokens and credentials out of public chat.
- Use `README.vi.md` for Vietnamese users and `README.md` for English users.

Required env vars:

- `BOT_TOKEN`
- `CHAT_ID`
- `SHEET_ID`
- `GOOGLE_CREDS_JSON`
- `SEPAY_SECRET`
- `TELEGRAM_WEBHOOK_SECRET`
- `CRON_SECRET`

Use Docker/GitHub Packages only if the user asks for VPS, server, NAS, or self-hosted deployment.
