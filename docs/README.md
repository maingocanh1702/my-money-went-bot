# Documentation

## If you are setting up a bot

Start here — these are written for operators, not contributors:

- **[Quick intro](QUICK_INTRO.md)** — what the bot does, in five minutes.
- **[AI assistant setup guide](AI_SETUP.md)** — paste one prompt into Claude,
  ChatGPT or Cursor and be walked through the whole setup.
- **[Wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki)** — the
  full guides: Google Sheets, SePay, Railway deployment, Zalo, first
  transaction test, command reference, troubleshooting, security and privacy.
  Not technical? Go straight to *Setup for non-technical users*.
- **[Zalo bot setup](ZALO_BOT_SETUP.md)** — the Zalo channel in detail.

The wiki pages are versioned here in `wiki/` and published automatically on
every push to `main`, so edit them here rather than on the wiki itself.

## Everything else in this folder

`autopilot-*` and the `postgres-sot-*` decision table are the maintainer's
agent-assisted development harness and design records. They document how this
repository is worked on, not how to run the bot. Nothing in the bot depends on
them and you can skip them.
