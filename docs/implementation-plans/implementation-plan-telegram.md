# Implementation Plan — Telegram + Discord (Co-Primary Channels)

> **Version:** v2.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Mục đích:** Consolidated plan cho **Telegram + Discord co-primary channels**, covering Phase 1-5 (Tuần 1-10, 48 dev days). Telegram build first → Discord adapter layers on top (shared handlers, DB, pipeline). Plan này map work từ feature docs → weekly sprint delivery.
> **Tham chiếu:** [Feature: Onboarding](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-onboarding.md) · [Feature: i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md) · [Feature: Discord](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-discord-channel.md) · [Feature: Transaction Capture](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-transaction-capture.md) · [Feature: Categorization](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-categorization.md) · [Feature: Category Management](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-category-management.md) · [Feature: Reports](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-reports.md) · [Feature: Pricing & Tiers](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md) · [Feature: Settings](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-settings.md) · [Feature: Scheduled Jobs](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-scheduled-jobs.md) · [Feature: SaaS Refactor](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) · [TDD v1.8.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) · [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md)

---

## 1. Executive Summary

### 1.1. Scope

Telegram + Discord bot build Phase 1-5 = 10 tuần = 48 dev days (founder solo, ~6h productive/day). Covers:

- PostgreSQL setup + Google Sheets migration (Phase 1)
- **i18n module:** dual language packs (vi/en), `t()` helper, auto-detect locale (Phase 1)
- Core SaaS foundation: multi-tenant, data isolation, channel adapter (Phase 1-2)
- **Discord adapter:** `DiscordSender`, Ed25519 verify, slash commands, Rich Embeds, button components (Phase 2)
- Bot commands: `/start`, `/manage`, `/status`, `/today`, `/settings`, `/help` (Phase 2-3)
- Transaction capture pipeline: SePay webhook + email parsing (Phase 3-5)
- Category picker with 2-level state machine (Phase 2-3)
- Scheduled jobs: daily recap, monthly allocation, trial management (Phase 3-4)
- Tier enforcement: Free/Pro/Business limits (Phase 3)
- Email parser: TCB, Cake, ACB, STB, BIDV, MB (Phase 4-5)

### 1.2. Decisions

| Decision | Choice | Source |
|----------|--------|-------|
| Language | Python 3.11+ | Existing codebase |
| Framework | FastAPI + python-telegram-bot | TDD §1.1 |
| DB | asyncpg raw SQL | TDD §1.2 |
| Deploy | Railway | TDD |
| Channels | Telegram + Discord co-primary, single-channel per user | BRD-vi §1.6 |
| Discord | DM-first, slash commands, Rich Embeds, Ed25519 | [Discord spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-discord-channel.md) |
| ORM | No ORM, raw SQL | TDD §1.2 |

### 1.3. Out of scope

- Messenger channel (Phase 6, separate [plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-messenger.md))
- Payment integration (Phase 6, separate [plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md))
- Admin tools (Phase 6)
- Web dashboard (Phase 9+)

---

## 2. Phase-by-Phase Breakdown

### Phase 1: Foundation (Tuần 1-2, 10 days)

**Goal:** PostgreSQL running, users table, Telegram bot responding. Channel adapter pattern ready for Discord.

#### Tuần 1 (Day 1-5)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 1 | Railway PostgreSQL setup + DDL (`users`, `categories`, `sub_categories`, `transactions`, `bot_state`, `scheduled_jobs`, `admin_audit_log`, `analytics_events`) | All tables created | [SaaS Refactor](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) |
| 2 | `db.py` — asyncpg pool, `create_user()`, `get_user()` | DB layer foundation | SaaS Refactor tech |
| 3 | `config.py` — env var loading, constants. `services/channels/base.py` — `BaseSender` ABC (`send_text()`, `send_embed()`, `send_buttons()`, `send_file()`, `edit_message()`) | Config + adapter base | SaaS Refactor |
| 4 | `services/channels/telegram.py` — `TelegramSender`. FastAPI app + `/webhook/telegram` endpoint. **`i18n/` module:** `__init__.py` (`t()` helper), `vi.py`, `en.py` language packs (~106 keys) | Telegram responds + i18n | [Onboarding](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-onboarding.md) · [i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md) |
| 5 | `services/messenger.py` — outbound routing interface (routes to adapter by `channel_type`). `services/locale_svc.py` — auto-detect locale from Telegram `language_code` + Discord `interaction.locale`. Tests: `test_db.py`, `test_telegram_sender.py`, `test_i18n.py` | Outbound abstraction + locale detect | SaaS Refactor · i18n |

#### Tuần 2 (Day 6-10)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 6 | `/start` → auto-detect locale → language confirm buttons → save `users.locale`. Welcome message + 3-path picker (inline keyboard) in user's locale. Default categories bilingual | Onboarding entry + i18n | Onboarding · i18n |
| 7 | Path A: SePay quick connect → webhook token display. Path C: email forwarding → inbound email display | 2 paths complete | Onboarding |
| 8 | Path B: SePay wizard 3-step → `bot_state` state machine | 3rd path complete | Onboarding |
| 9 | Google Sheets migration script. Test migration with founder data | Migration ready | SaaS Refactor |
| 10 | Integration test: full onboarding E2E. Deploy to Railway staging | Phase 1 complete | All |

**Phase 1 deliverables:** Telegram bot runs, user signup works, 3 onboarding paths, i18n (vi/en) language selection, DB foundation, channel adapter pattern ready, data migrated.

---

### Phase 2: Core Bot Commands + Discord Adapter (Tuần 3-4, 10 days)

**Goal:** `/manage`, `/status`, `/today` working on Telegram. Discord adapter live — same commands work on Discord.

#### Tuần 3 (Day 11-15)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 11 | `handlers/manage.py` — `/manage` list categories. Show name, budget, spent | Category list | [Cat Mgmt](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-category-management.md) |
| 12 | `/manage` → rename, delete (soft), add category. Budget update | CRUD complete | Cat Mgmt |
| 13 | Sub-category CRUD via `/manage` → drill-down | Sub-cat management | Cat Mgmt |
| 14 | `handlers/report.py` — `/status` monthly overview with progress bars | Monthly report | [Reports](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-reports.md) |
| 15 | `/today` daily spending. Empty states for both commands | Daily report | Reports |

#### Tuần 4 (Day 16-20)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 16 | `/help` command (auto-generated from handler registry). `/settings` basic display | Help + settings | [Settings](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-settings.md) |
| 17 | Settings: timezone change + webhook token regen + daily recap toggle + **language change** | Settings complete | Settings · i18n |
| 18 | **`services/channels/discord.py`** — `DiscordSender` (extend `BaseSender`): `send_embed()`, `send_buttons()` via Action Rows, `respond_interaction()`, `edit_original()`, `_get_dm_channel()`. **`handlers/discord_interaction.py`** — Ed25519 signature verify + POST `/webhook/discord` endpoint | Discord adapter + webhook | [Discord](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-discord-channel.md) |
| 19 | **`discord_commands.py`** — register global slash commands (`/start`, `/status`, `/today`, `/manage`, `/settings`, `/help`, `/upgrade`, `/weekly`, `/report`, `/export`) with `name_localizations` + `description_localizations`. `parsers/discord_payload.py` — normalize Discord Interaction → internal Update. **Embed builder** + **button component builder** helpers | Slash commands + rendering | Discord |
| 20 | Discord E2E: `/start` DM → language select (buttons) → onboarding path (buttons) → `/status` (Rich Embed). Defer pattern for >3s responses. `test_discord_sender.py`, `test_discord_interaction.py` | Discord fully working | Discord |
| 21 | Tier limit engine: `services/tier_check.py`. Integrate into manage + report | Tier enforcement | [Pricing](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md) |
| 22 | Trial logic: auto-assign 14d, reminder Day 12, downgrade Day 14 | Trial complete | Pricing |
| 23 | Integration test: all commands on **both Telegram + Discord**. Code cleanup. Deploy | Phase 2 complete | All |

**Phase 2 deliverables:** All bot commands work on both Telegram + Discord. Discord adapter live (slash commands, embeds, buttons). Tier limits enforced. Trial logic active.

---

### Phase 3: Transaction Pipeline (Tuần 5-6, 10 days)

**Goal:** SePay webhook → categorize → confirmed (works on both Telegram + Discord).

#### Tuần 5 (Day 24-28)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 24 | `/hook/{token}` endpoint. `handlers/sepay.py` — parse SePay payload | Webhook receives | [Tx Capture](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-transaction-capture.md) |
| 25 | `services/tx_pipeline.py` — normalize → dedup → stale → tier → INSERT | Pipeline complete | Tx Capture |
| 26 | `handlers/transaction.py` — category picker (inline keyboard / Action Row buttons). 2-level: parent → sub → confirm | Picker UI (both channels) | [Categorization](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-categorization.md) |
| 27 | State machine: `await_parent` → `await_sub` → confirmed. Inline category create. Discord pagination (>25 cats) | State machine | Categorization · Discord |
| 28 | Dedup: exact ref + fuzzy cross-source. Stale check: 10min SePay, 24h email | Dedup complete | Tx Capture |

#### Tuần 6 (Day 29-33)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 29 | `services/scheduler.py` — APScheduler poll loop. Daily recap fire 23:00 (DM for both Telegram + Discord) | Scheduler running | [Sched Jobs](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-scheduled-jobs.md) |
| 30 | Monthly allocation auto-clone (1st of month). Jitter algorithm | Auto-clone | Sched Jobs |
| 31 | Trial scheduled checks: reminder, downgrade. Upgrade prompt cooldown | Trial automation | Pricing |
| 32 | Upgrade flow: `/upgrade` → plan display → ref code generation → VietQR placeholder | Upgrade UI scaffold | Pricing |
| 33 | Full E2E test: signup → SePay webhook → categorize → /status on **both channels**. Deploy | Phase 3 complete | All |

**Phase 3 deliverables:** SePay pipeline live. Category picker works (both channels). Scheduled jobs running. Upgrade flow scaffolded.

---

### Phase 4: Email Parsing (Tuần 7-8, 10 days)

**Goal:** Email forwarding → TCB, Cake parsers. 6-bank coverage.

#### Tuần 7 (Day 34-38)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 34 | Postmark Inbound setup. `/inbound/{token}` endpoint. Bank detection (from address) | Inbound receives | Tx Capture |
| 35 | `parsers/tcb.py` — TCB email HTML parse. Fixtures from real emails | TCB parser | Tx Capture |
| 36 | `parsers/cake.py` — Cake email parse. Test with fixtures | Cake parser | Tx Capture |
| 37 | `parsers/acb.py` + `parsers/stb.py` — ACB, Sacombank parsers | 2 more banks | Tx Capture |
| 38 | `parsers/bidv.py` + `parsers/mb.py` — BIDV, MB Bank parsers | 6 banks total | Tx Capture |

#### Tuần 8 (Day 39-43)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 39 | Cross-source dedup integration. SePay + Email same tx | Dedup verified | Tx Capture |
| 40 | Email fallback notification (parse fail). Unknown bank handling | Error handling | Tx Capture |
| 41 | `/weekly` command (Pro+). `/report` monthly detail (Pro+) | Pro reports | Reports |
| 42 | `/export` CSV generation + file attachment send (Telegram doc / Discord file) | Export complete | Reports |
| 43 | Integration test: SePay + Email dual-source. All 6 banks. Both channels. Deploy | Phase 4 complete | All |

**Phase 4 deliverables:** Email pipeline live. 6 banks supported. Pro reports + export.

---

### Phase 5: Polish + Pre-Phase 6 (Tuần 9-10, 5 days)

**Goal:** Production-ready Telegram + Discord bot.

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 44 | Error handling audit: every handler try/catch. Empty/error states. Discord defer pattern audit | Resilience | All |
| 45 | Analytics events integration (`analytics_events` table). Discord-specific events (`discord_signup`, `discord_interaction`) | Tracking | All |
| 46 | Performance: connection pool tuning, query optimization, response time check | p95 < 2s | SaaS Refactor |
| 47 | Security audit: token validation, Ed25519 verify, user_id scoping, rate limiting (both channels) | Security | All |
| 48 | Final E2E test matrix (**both Telegram + Discord**). README update. CHANGELOG. Deploy to production | Phase 5 complete | All |

**Phase 5 deliverables:** Telegram + Discord bot production-ready. Foundation cho Phase 6 Messenger + Payment.

---

## 3. Acceptance Criteria per Phase

| Phase | AC |
|-------|-----|
| 1 | Telegram bot responds `/start`. User created in DB. 3 paths work. Data migrated. Channel adapter pattern ready |
| 2 | `/manage` CRUD. `/status` + `/today`. **Discord adapter live** — slash commands, embeds, buttons. Tier limits. Trial 14d |
| 3 | SePay webhook → categorize E2E (**both channels**). Scheduler + daily recap. Dedup |
| 4 | Email parse 6 banks. Cross-source dedup. Pro reports + export |
| 5 | Error handling. Analytics. Performance. Security. **Production deploy (Telegram + Discord)** |

---

## 4. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| 1 | SePay API changes | Low | High | Monitor docs, version parsers |
| 2 | Bank email format changes | Medium | Medium | Versioned parsers + fallback chain |
| 3 | Postmark downtime | Low | Medium | SePay primary, email is backup |
| 4 | Railway deploy issues | Low | High | Docker fallback ready |
| 5 | Solo founder burnout | Medium | High | 6h/day cap, buffer days |
| 6 | Telegram rate limit | Low | Low | 30 msg/s limit, jitter spreads |
| 7 | Google Sheets migration loss | Low | Critical | Backup before, validate counts |
| 8 | Discord rate limit (100 DM/2h initial) | Medium | Medium | Request rate limit increase via Dev Portal. Queue + backoff |
| 9 | Discord API breaking changes | Low | Medium | Pin library version, monitor changelog |

---

## 5. Prerequisites

- [ ] Railway account + PostgreSQL provisioned
- [ ] Telegram Bot created via @BotFather
- [ ] BOT_TOKEN + ADMIN_TELEGRAM_IDS configured
- [ ] **Discord Application created via [Discord Developer Portal](https://discord.com/developers)**
- [ ] **DISCORD_BOT_TOKEN + DISCORD_APPLICATION_ID + DISCORD_PUBLIC_KEY configured**
- [ ] **Discord bot invited to test server (for dev) + DM permissions enabled**
- [ ] SePay account active
- [ ] Postmark account + inbound domain configured
- [ ] Domain DNS: `api.tienvenoidau.com` → Railway
- [ ] Email domain: `in.tienvenoidau.com` → Postmark Inbound
- [ ] Google Sheets API access (for migration)

---

## 6. Test Strategy

### Unit Tests per Phase

| Phase | Tests | Coverage target |
|-------|-------|----------------|
| 1 | db.py (15), telegram_sender (10), onboarding (20) | ≥80% |
| 2 | manage (20), report (22), settings (20), tier (22), **discord_sender (15), discord_interaction (15)** | ≥85% |
| 3 | sepay_handler (24), tx_pipeline (20), categorization (20), scheduler (22) | ≥85% |
| 4 | parsers × 6 (60), dedup (10), export (10) | ≥90% parsers |
| 5 | Integration E2E (20) — **both Telegram + Discord** | Full flow |

### Smoke Test Checklist (after each phase)

- [ ] Server starts, `/` returns 200
- [ ] `/webhook/telegram` accepts POST
- [ ] **`/webhook/discord` accepts POST (Ed25519 verified)**
- [ ] Console clean (0 unhandled errors)
- [ ] All routes return expected (not blank)
- [ ] Previous phase features still work
- [ ] **Discord slash commands respond in DM**

---

## 7. Definition of Done (Phase 5 complete)

- [ ] All bot commands working on **both Telegram + Discord**: `/start`, `/manage`, `/status`, `/today`, `/weekly`, `/report`, `/export`, `/settings`, `/help`, `/upgrade`
- [ ] **Discord adapter:** slash commands registered globally, Rich Embeds, Action Row buttons, Ed25519 verify, defer pattern
- [ ] **Discord DM:** onboarding, category picker (with pagination >25), reports, settings all work in DM
- [ ] SePay webhook pipeline live
- [ ] Email parsing 6 banks live
- [ ] Cross-source dedup verified
- [ ] Scheduled jobs: daily recap (both channels), monthly allocation, trial management
- [ ] Tier enforcement: Free (45tx, 5cat, 1bank), Pro (unlimited), Business (unlimited)
- [ ] Trial 14-day with reminder + auto-downgrade
- [ ] All handlers: try/catch + empty/error states
- [ ] Analytics events tracked (including `discord_signup`, `discord_interaction`)
- [ ] p95 response time < 2s
- [ ] 0 cross-user data leakage
- [ ] Production deploy on Railway
- [ ] All user-facing messages served via `t(user.locale, key)` (vi + en)
- [ ] Language selection in onboarding (auto-detect + confirm) — both channels
- [ ] Language change in `/settings`
- [ ] Admin messages English hardcoded
- [ ] README + CHANGELOG updated

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial Telegram implementation plan — Phase 1-5 (9 tuần) |
| v1.1.0 | 2026-05-08 | **i18n integration:** Phase 1 Day 4-5 add `i18n/` module, Phase 1 Day 6 language confirm, Phase 2 Day 17 settings language change, Definition of Done thêm i18n criteria. |
| v2.0.0 | 2026-05-09 | **Discord co-primary channel:** (1) Renamed plan “Telegram + Discord (Co-Primary)”. (2) Phase 2 Day 18-20 — `DiscordSender` adapter, Ed25519 verify, `/webhook/discord`, slash command registration, embed builder, button components, Discord E2E. (3) Phase 1 Day 3 — `BaseSender` ABC expanded with `send_embed()`, `send_buttons()`. (4) Phase 1 Day 5 — locale detect adds Discord `interaction.locale`. (5) All Phase 3-5 day numbers shifted +3 (45→48 days, 9→10 tuần). (6) Acceptance criteria, risk register (+2 Discord risks), prerequisites (+3 Discord items), test strategy, smoke test, Definition of Done all updated for dual-channel. |
