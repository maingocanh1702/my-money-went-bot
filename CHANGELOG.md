# Changelog

All notable changes to MyMoneyWent will be documented in this file.

## Unreleased

### Added
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
