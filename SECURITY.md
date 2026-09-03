# Security policy

## You run your own bot

This project is not a hosted service. Every deployment is separate: your bot
token, your Google Sheet, your Railway service, your secrets. Nobody involved
in this repository can see your transactions, and there is no shared backend
that a vulnerability here would expose.

That also means the security of your deployment is yours to keep. In practice:

- **Never commit `.env`, `credentials.json`, or a real secret**, including into
  `google_apps_script.js`. Git history is forever, and a secret that reached a
  public repository must be rotated, not just deleted.
- **Set all eight required variables.** The bot refuses to start without them
  rather than exposing an unauthenticated webhook. `SEPAY_SECRET`,
  `TELEGRAM_WEBHOOK_SECRET`, `EMAIL_SECRET` and `CRON_SECRET` are what stand
  between the public internet and writes into your Sheet.
- **Use a different random value for each secret**, and set the paired value at
  the other end at the same time — `SEPAY_SECRET` in the SePay dashboard,
  `EMAIL_SECRET` in the Apps Script, `TELEGRAM_WEBHOOK_SECRET` in `setWebhook`.
  A mismatch rejects real traffic; a blank one accepts forged traffic.
- **Share the Google Sheet with the service account only.** It needs Editor on
  that one Sheet, nothing else in your Drive.
- **Rotate anything that leaks.** A leaked `EMAIL_SECRET` plus your Railway URL
  is enough for someone to write fabricated transactions into your Sheet.

## Reporting a vulnerability

Please report privately rather than in a public issue: open a
[security advisory](https://github.com/maingocanh1702/my-money-went-bot/security/advisories/new)
on this repository.

Useful to include: what an attacker can do, the smallest set of steps that
shows it, and which version or commit you tested. Expect an acknowledgement
within about a week — this is a spare-time project, not a staffed one, and it
is better to say that plainly than to promise a response time nobody meets.

Please do not test against anyone else's deployment. Reproduce on your own.

## Scope

In scope: anything in this repository — the webhook endpoints and their
authentication, the Apps Script, the Sheets access paths, dependency issues
that are actually reachable from this code.

Out of scope: the security of Telegram, Zalo, SePay, Google, or Railway
themselves; and misconfiguration of an individual deployment (a missing secret,
a Sheet shared publicly). Those are worth an ordinary issue if the docs led you
there — a setup guide that talks someone into an insecure configuration *is* a
bug in this repository.
