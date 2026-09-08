# Changelog

All notable changes to MyMoneyWent will be documented in this file.

## Unreleased

### Added
- `/cancel_tx [row]` — cancel a transaction that already happened. It gives the
  credit limit back, claws the cashback back, and recomputes the whole billing
  cycle, so a later transaction that was refused as `mcc_cap_full` can become
  eligible again. Cancelling is a soft delete: both ledgers key on the row
  number, so the row stays and is marked cancelled, which is also what makes
  restore possible. Income rows and anything older than 30 days are refused in
  both directions. Shipped 2026-09-08 and, for a day, documented nowhere — the
  entry below about the MCC commands says this had already happened once.

### Fixed
- The interactive API docs were public. `/docs` and `/openapi.json` enumerated
  every webhook and trigger route on a live financial bot, and spelled out that
  `/trigger/*` authenticated by query parameter — the hint you need before going
  looking in logs for one. They are off, and the trigger routes read an
  `Authorization` header now; `?secret=` still works so an existing crontab does
  not break.
- The logs carried the owner's bank account number and a timestamped spend
  history. `append_transaction` logged the raw source key, which IS the account
  number, beside the amount; the ledger, dedup and excluded-event lines logged
  amounts; and the SePay handler logged the raw bank memo, directly under a
  comment telling it never to log bank data.
- The `/recat` picker rendered the bank memo unescaped inside a Markdown code
  span while every sibling call site escaped it. A memo is chosen by whoever
  sends you money, and a leading backtick closes the span and turns the rest
  into a live link inside a message you trust as coming from your own bot.
- Cashback rates were read by the money parser, which treats three digits after
  a separator as thousands grouping. A rate of `0.015` came back as `15.0`, so
  an ordinary 1.5% card would have paid fifteen million đồng on a one-million
  đồng purchase and filled its cycle cap on the spot. Rates have their own
  parser now, which also accepts `1,5%` and refuses anything outside 0–1.
- Money shorthand threw its unit away whenever the number carried a thousands
  group: `1.500k` parsed as 1.500đ, not 1.500.000đ. That number goes straight
  into a ledger leg through `/transfer` and `/cc pay`, and into the opening
  balance through the account wizard.
- Cross-source dedup treated a transaction with no known source as a duplicate
  candidate, contradicting the docstring one screen above it. Since
  `/transfer` and both credit-card payment writers never record a source, a
  transfer followed a minute later by a genuine card spend of the same amount
  ate the card spend.
- A bank notification arriving mid-flow could throw the flow away. The guard
  listing which steps to protect had not been updated when `/manage` grew an
  editable daily cap, so typing a cap was unprotected. It lists what may be
  interrupted now instead, which cannot go stale the same way.
- A notification arriving while a category picker was open replaced it, so
  tapping the picker logged the right category against the *new* transaction's
  amount, drew the wrong day's bar, and destroyed the arriving transaction's
  own flow. It queues behind now, as it already did on Zalo.
- `/accounts assign` counted cancelled transactions into the totals it asks you
  to confirm, on both channels.
- The email amount parser stripped dots but never commas, so an amount with
  decimal places returned 0.0 — writing a 0đ row that the ledger skips, every
  report skips, and nobody is told about.

### Changed
- CI pins Python through `.python-version` rather than repeating `3.11` in the
  workflow, and the GitHub Actions are pinned to commit SHAs — which
  `dependabot.yml` had claimed for a while without it being true. `ruff` is in
  `requirements-dev.txt`, so the lint gate is reproducible from
  CONTRIBUTING's instructions instead of only inside CI.
- The privacy guard no longer labels its digests. A bank account number is ten
  digits and a project id is pattern-constrained, so an unsalted SHA-256 of
  either is recoverable by enumeration, and the labels said which digest was
  worth the trouble. Service-account addresses and deployment hostnames are
  matched by shape now, which does not leak at all.
- The scheduled cron workflow skips itself while `BOT_URL` is still the
  template placeholder, instead of failing red about seven times a month on
  this repository. Fork it and set `BOT_URL` and the schedule starts working.

- The MCC map can be corrected, not just extended. `<pattern> <mcc> [label]` now
  re-points a pattern that already exists instead of refusing it as a duplicate,
  `ren <old> <new>` fixes the keyword itself while keeping its MCC and label, and
  `del <pattern>` turns one off. `skip <pattern>` / `unskip <pattern>` manage the
  no-cashback list, which until now could only be added to by tapping a button on
  a live transaction — so a merchant could not be excluded until it charged you
  again, and once excluded there was no way to see it or undo it. The list is now
  shown at the bottom of the MCC screen. Both were only possible by opening the Google
  Sheet by hand — which the bot then ignored, because the MCC cache has no TTL and
  a manual sheet edit invalidates nothing.
- Debit cards are documented as a first-class thing the bot tracks, alongside
  credit cards. No code changed — the account type, the e-mail path and the
  onboarding wizard already supported it; nothing in the docs said so, which is
  the same as not supporting it. A debit card needs an alert e-mail from its
  bank and nothing else: no parser of its own, no YAML template. It skips the
  statement-cycle and cashback machinery, which is what a debit card should do.
- The two channels are described honestly: Telegram is the one this bot is best
  on, Zalo runs alongside it. Zalo's Bot API sends plain text and nothing else,
  so a category picker becomes a numbered list you reply to, messages are never
  edited in place, and formatting is stripped — a platform limit, not missing
  work here. Both READMEs and the Zalo wiki page now carry the comparison, and
  say that anything richer than text lands on Telegram first.
- A "What it costs to run" section in both READMEs, with the free-tier limits of
  every service the bot touches and the arithmetic to work out your own volume.
  Hosting is the only bill (~$5/month on Railway, from ~68,000đ/month self-hosted);
  the quota worth reading twice is SePay's, which counts *incoming* transactions
  only, while this bot mostly records money going out.
- Setting up the Zalo channel is now part of the guide rather than a page you had
  to already know existed: a numbered *Step 7* in both READMEs, and the AI setup
  prompt asks about Zalo once Telegram is working.
- The AI-assisted setup now sits at the top of both READMEs with the prompt
  inline, instead of a link two-thirds of the way down. Setup is mostly
  collecting values and pasting them into one dashboard, which an assistant
  walks a non-technical person through well — so the shortest path to a running
  bot is the first thing the page offers.

### Fixed
- The MCC code is validated as four digits. It was not, and the failure was
  silent: one extra word — `TIKTOK SHOP 5611 Thoi trang` — filed the pattern
  under an MCC of `SHOP`. No card has a rule for `SHOP`, and an inferred MCC with
  no matching rule earns nothing — `compute_cashback` returns a 0đ audit line
  with reason `mcc_not_eligible`. So those swipes earned **nothing** where they
  should have earned the fashion rate, without a prompt and without an error,
  and the entry looked perfectly normal in the list.
- `docs/ZALO_BOT_SETUP.md` described a bot that no longer exists: it said Zalo was
  notification-only, that categorizing had to happen on Telegram, and that
  `ZALO_SECRET_TOKEN` was an optional extra for a "beta". All three were wrong —
  every command works on Zalo through numbered replies, and the secret is
  mandatory whenever the channel is on, because `/zalo/webhook` is public. The
  wiki page also still claimed a Zalo-only deployment was possible; `config.py`
  has never allowed one.
- Money read out of a sheet cell is now read the way the cell is *displayed*.
  Google returns the formatted value, so a Vietnamese-locale sheet shows 50000
  as `50.000` — which `float()` read as fifty. Amounts with repeated separators
  (`1.234.567`) raised instead. Both readers, the cell reader and the typed-input
  parser, now share one rule for what `.` and `,` mean, and agree on every form.
  A typed `1,234,567.89` no longer becomes 123,456,789.
- Nothing is discarded without a record. Every declined event — before the
  ingestion boundary, past the age window, or a cross-source duplicate — is
  appended to an `Excluded Events` tab with its reason. Set `INGESTION_START_AT`
  to the date this installation starts owning transactions and late-arriving
  transactions stop being thrown away; leave it unset and nothing changes.
- Transactions are identified by SePay's own `id` rather than `referenceCode`,
  which is not guaranteed unique. The cross-source duplicate check no longer
  collapses two genuinely distinct spends that share an amount, type and second.

### Removed
- Email parsers for Techcombank and Hang Seng, and the `techcombank_visa`
  cashback template. They were written against one maintainer's mailbox and
  card terms, and nobody else could verify either. The email path itself is
  unchanged — Cake by VPBank remains as the worked example, and adding a bank
  is still one sender in `google_apps_script.js` plus one `_parse_<bank>`.
- The maintainer's own name from the merchant-keyword stop list. Vietnamese
  transfers carry the sender's name, so that list needed one — it is now
  yours to set via `MERCHANT_NOISE_WORDS` in `.env`.

### Changed
- `account_resolver` treats every `email_<bank>` source the same, so a new
  parser needs no change there.
- `card_templates/example_visa.yaml` replaces the Techcombank template as the
  second worked example: per-rule rates, calendar-month caps, no gate.
- `/help` documents the MCC-editing commands, and Zalo finally shows the same
  help as Telegram. The Zalo branch carried its own hand-written copy of the
  command list — hardcoded in Vietnamese, so `/lang` did nothing there, and it
  had drifted: `/recat`, `/pending` and the cashback commands were listed, the
  MCC ones were not, and every future command would have had to be remembered
  in two places. Both channels now render one string, with a short Zalo-only
  note that choices there are made by replying with a number.

## v1.0.0 — 2026-09-01 (Open-Source Release)

Architecture migration from private mono repo. All SaaS/multi-tenant code removed.

### Features

#### 💰 Transaction Tracking
- Record income/expenses via Telegram & Zalo messages
- Auto-detect bank transactions via SePay webhook
- Email parsing for Techcombank, Cake, Hang Seng bank notifications
- Smart categorization with keyword rules
- Sub-category support with budget allocation

#### 💳 Cashback Tracking (NEW)
- Multi-card cashback engine with MCC-based rules
- YAML template system for card configurations
- Built-in templates: Cake Freedom, Techcombank Visa
- `/cashback setup` — wizard to create custom card configs
- `/cashback export` — export config as YAML
- `/cashback savetemplate` — save config as reusable template
- `/cashback seed <template>` — apply template to any card
- `/cashback templates` — list all available templates
- Per-MCC cap tracking with alert notifications
- Per-transaction cap tiers

#### 📊 Reports & Analytics
- Daily spending summary with budget progress
- Weekly recap with category breakdown
- Monthly report with trends analysis
- Cashback overview with per-MCC breakdown

#### 🏦 Account Management
- Multi-account support (bank, cash, credit card)
- Account transfers and credit card payments
- Pending transaction queue for mid-flow webhooks
- Balance tracking across accounts

#### 🔤 Smart Keyword Engine
- Self-learning keyword rules from manual categorization
- Automatic category suggestion after manual picks
- Rule management via `/keywords` command

#### 📧 Email Integration
- Google Apps Script for Gmail → webhook pipeline
- Support for Techcombank, Cake, Hang Seng email formats
- Auto-forward detection for multi-account setups

#### 🌐 Multi-Channel
- Telegram (full feature parity)
- Zalo Bot Platform (full feature parity)
- Channel-aware message rendering

#### 🌍 i18n
- Vietnamese (default) and English
- `/lang` command to switch languages
- 210+ translated keys

#### ⏰ Scheduled Triggers
- Monthly budget allocation prompt
- Weekly spending recap
- Monthly report generation
- Auto-allocation fallback
- Optional daily recap

#### 🔐 Security
- SePay webhook signature verification
- Telegram webhook secret token
- Cron trigger authentication
- Email webhook secret
- Stale transaction guard (configurable age window)
