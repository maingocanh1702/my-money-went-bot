# Changelog

All notable changes to MyMoneyWent will be documented in this file.

## Unreleased

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
