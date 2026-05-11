# Implementation Plan — Telegram Channel (Primary)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Mục đích:** Consolidated plan cho Telegram-as-primary-channel, covering Phase 1-5 (Tuần 1-9). Telegram là channel mặc định, build trước Messenger. Plan này map work từ feature docs → weekly sprint delivery.
> **Tham chiếu:** [Feature: Onboarding](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_onboarding.md) · [Feature: i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_i18n.md) · [Feature: Transaction Capture](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_transaction_capture.md) · [Feature: Categorization](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_categorization.md) · [Feature: Category Management](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_category_management.md) · [Feature: Reports](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_reports.md) · [Feature: Pricing & Tiers](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_pricing_tiers.md) · [Feature: Settings](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_settings.md) · [Feature: Scheduled Jobs](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_scheduled_jobs.md) · [Feature: SaaS Refactor](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_saas_refactor.md) · [TDD v1.7.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) · [BRD v2.9.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md)

---

## 1. Executive Summary

### 1.1. Scope

Telegram bot build Phase 1-5 = 9 tuần = 45 dev days (founder solo, ~6h productive/day). Covers:

- PostgreSQL setup + Google Sheets migration (Phase 1)
- **i18n module:** dual language packs (vi/en), `t()` helper, auto-detect locale (Phase 1)
- Core SaaS foundation: multi-tenant, data isolation, channel adapter (Phase 1-2)
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
| Channel | Telegram primary, single-channel per user | Feature onboarding |
| ORM | No ORM, raw SQL | TDD §1.2 |

### 1.3. Out of scope

- Messenger channel (Phase 6, separate [plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation_plan_messenger.md))
- Payment integration (Phase 6, separate [plan](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md))
- Admin tools (Phase 6)
- Web dashboard (Phase 9+)

---

## 2. Phase-by-Phase Breakdown

### Phase 1: Foundation (Tuần 1-2, 10 days)

**Goal:** PostgreSQL running, users table, basic bot responding.

#### Tuần 1 (Day 1-5)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 1 | Railway PostgreSQL setup + DDL (`users`, `categories`, `sub_categories`, `transactions`, `bot_state`, `scheduled_jobs`, `admin_audit_log`, `analytics_events`) | All tables created | [SaaS Refactor](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_saas_refactor.md) |
| 2 | `db.py` — asyncpg pool, `create_user()`, `get_user()` | DB layer foundation | SaaS Refactor tech |
| 3 | `config.py` — env var loading, constants. `services/channels/base.py` — `BaseSender` ABC | Config + adapter base | SaaS Refactor |
| 4 | `services/channels/telegram.py` — `TelegramSender.send_text()`. FastAPI app + `/webhook/telegram` endpoint. **`i18n/` module:** `__init__.py` (`t()` helper), `vi.py`, `en.py` language packs (~106 keys) | Bot responds to `/start` + i18n foundation | [Onboarding](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_onboarding.md) · [i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_i18n.md) |
| 5 | `services/messenger.py` — outbound routing interface. `services/locale_svc.py` — auto-detect locale from Telegram `language_code`. Tests: `test_db.py`, `test_telegram_sender.py`, `test_i18n.py` | Outbound abstraction + locale detect | SaaS Refactor · i18n |

#### Tuần 2 (Day 6-10)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 6 | `/start` → auto-detect locale → language confirm buttons → save `users.locale`. Welcome message + 3-path picker (inline keyboard) in user's locale. Default categories bilingual | Onboarding entry + i18n | Onboarding · i18n |
| 7 | Path A: SePay quick connect → webhook token display. Path C: email forwarding → inbound email display | 2 paths complete | Onboarding |
| 8 | Path B: SePay wizard 3-step → `bot_state` state machine | 3rd path complete | Onboarding |
| 9 | Google Sheets migration script. Test migration with founder data | Migration ready | SaaS Refactor |
| 10 | Integration test: full onboarding E2E. Deploy to Railway staging | Phase 1 complete | All |

**Phase 1 deliverables:** Bot runs, user signup works, 3 onboarding paths, i18n (vi/en) language selection, DB foundation, data migrated.

---

### Phase 2: Core Bot Commands (Tuần 3-4, 10 days)

**Goal:** `/manage`, `/status`, `/today` working.

#### Tuần 3 (Day 11-15)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 11 | `handlers/manage.py` — `/manage` list categories. Show name, budget, spent | Category list | [Cat Mgmt](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_category_management.md) |
| 12 | `/manage` → rename, delete (soft), add category. Budget update | CRUD complete | Cat Mgmt |
| 13 | Sub-category CRUD via `/manage` → drill-down | Sub-cat management | Cat Mgmt |
| 14 | `handlers/report.py` — `/status` monthly overview with progress bars | Monthly report | [Reports](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_reports.md) |
| 15 | `/today` daily spending. Empty states for both commands | Daily report | Reports |

#### Tuần 4 (Day 16-20)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 16 | `/help` command (auto-generated from handler registry). `/settings` basic display | Help + settings | [Settings](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_settings.md) |
| 17 | Settings: timezone change + webhook token regen + daily recap toggle + **language change** | Settings complete | Settings · i18n |
| 18 | Tier limit engine: `services/tier_check.py`. Integrate into manage + report | Tier enforcement | [Pricing](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_pricing_tiers.md) |
| 19 | Trial logic: auto-assign 14d, reminder Day 12, downgrade Day 14 | Trial complete | Pricing |
| 20 | Integration test: all commands. Code cleanup. Deploy | Phase 2 complete | All |

**Phase 2 deliverables:** All bot commands work. Tier limits enforced. Trial logic active.

---

### Phase 3: Transaction Pipeline (Tuần 5-6, 10 days)

**Goal:** SePay webhook → categorize → confirmed.

#### Tuần 5 (Day 21-25)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 21 | `/hook/{token}` endpoint. `handlers/sepay.py` — parse SePay payload | Webhook receives | [Tx Capture](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_transaction_capture.md) |
| 22 | `services/tx_pipeline.py` — normalize → dedup → stale → tier → INSERT | Pipeline complete | Tx Capture |
| 23 | `handlers/transaction.py` — category picker (inline keyboard). 2-level: parent → sub → confirm | Picker UI | [Categorization](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_categorization.md) |
| 24 | State machine: `await_parent` → `await_sub` → confirmed. Inline category create | State machine | Categorization |
| 25 | Dedup: exact ref + fuzzy cross-source. Stale check: 10min SePay, 24h email | Dedup complete | Tx Capture |

#### Tuần 6 (Day 26-30)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 26 | `services/scheduler.py` — APScheduler poll loop. Daily recap fire 23:00 | Scheduler running | [Sched Jobs](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_scheduled_jobs.md) |
| 27 | Monthly allocation auto-clone (1st of month). Jitter algorithm | Auto-clone | Sched Jobs |
| 28 | Trial scheduled checks: reminder, downgrade. Upgrade prompt cooldown | Trial automation | Pricing |
| 29 | Upgrade flow: `/upgrade` → plan display → ref code generation → VietQR placeholder | Upgrade UI scaffold | Pricing |
| 30 | Full E2E test: signup → SePay webhook → categorize → /status. Deploy | Phase 3 complete | All |

**Phase 3 deliverables:** SePay pipeline live. Category picker works. Scheduled jobs running. Upgrade flow scaffolded.

---

### Phase 4: Email Parsing (Tuần 7-8, 10 days)

**Goal:** Email forwarding → TCB, Cake parsers. 6-bank coverage.

#### Tuần 7 (Day 31-35)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 31 | Postmark Inbound setup. `/inbound/{token}` endpoint. Bank detection (from address) | Inbound receives | Tx Capture |
| 32 | `parsers/tcb.py` — TCB email HTML parse. Fixtures from real emails | TCB parser | Tx Capture |
| 33 | `parsers/cake.py` — Cake email parse. Test with fixtures | Cake parser | Tx Capture |
| 34 | `parsers/acb.py` + `parsers/stb.py` — ACB, Sacombank parsers | 2 more banks | Tx Capture |
| 35 | `parsers/bidv.py` + `parsers/mb.py` — BIDV, MB Bank parsers | 6 banks total | Tx Capture |

#### Tuần 8 (Day 36-40)

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 36 | Cross-source dedup integration. SePay + Email same tx | Dedup verified | Tx Capture |
| 37 | Email fallback notification (parse fail). Unknown bank handling | Error handling | Tx Capture |
| 38 | `/weekly` command (Pro+). `/report` monthly detail (Pro+) | Pro reports | Reports |
| 39 | `/export` CSV generation + file attachment send | Export complete | Reports |
| 40 | Integration test: SePay + Email dual-source. All 6 banks. Deploy | Phase 4 complete | All |

**Phase 4 deliverables:** Email pipeline live. 6 banks supported. Pro reports + export.

---

### Phase 5: Polish + Pre-Phase 6 (Tuần 9, 5 days)

**Goal:** Production-ready Telegram bot.

| Day | Work | Output | Feature ref |
|-----|------|--------|-------------|
| 41 | Error handling audit: every handler try/catch. Empty/error states | Resilience | All |
| 42 | Analytics events integration (`analytics_events` table) | Tracking | All |
| 43 | Performance: connection pool tuning, query optimization, response time check | p95 < 2s | SaaS Refactor |
| 44 | Security audit: token validation, user_id scoping, rate limiting | Security | All |
| 45 | Final E2E test matrix. README update. CHANGELOG. Deploy to production | Phase 5 complete | All |

**Phase 5 deliverables:** Telegram bot production-ready. Foundation cho Phase 6 Messenger + Payment.

---

## 3. Acceptance Criteria per Phase

| Phase | AC |
|-------|-----|
| 1 | Bot responds `/start`. User created in DB. 3 paths work. Data migrated |
| 2 | `/manage` CRUD. `/status` + `/today`. Tier limits. Trial 14d |
| 3 | SePay webhook → categorize E2E. Scheduler + daily recap. Dedup |
| 4 | Email parse 6 banks. Cross-source dedup. Pro reports + export |
| 5 | Error handling. Analytics. Performance. Security. Production deploy |

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

---

## 5. Prerequisites

- [ ] Railway account + PostgreSQL provisioned
- [ ] Telegram Bot created via @BotFather
- [ ] BOT_TOKEN + ADMIN_TELEGRAM_IDS configured
- [ ] SePay account active
- [ ] Postmark account + inbound domain configured
- [ ] Domain DNS: `api.fintrack.app` → Railway
- [ ] Email domain: `in.fintrack.app` → Postmark Inbound
- [ ] Google Sheets API access (for migration)

---

## 6. Test Strategy

### Unit Tests per Phase

| Phase | Tests | Coverage target |
|-------|-------|----------------|
| 1 | db.py (15), telegram_sender (10), onboarding (20) | ≥80% |
| 2 | manage (20), report (22), settings (20), tier (22) | ≥85% |
| 3 | sepay_handler (24), tx_pipeline (20), categorization (20), scheduler (22) | ≥85% |
| 4 | parsers × 6 (60), dedup (10), export (10) | ≥90% parsers |
| 5 | Integration E2E (20) | Full flow |

### Smoke Test Checklist (after each phase)

- [ ] Server starts, `/` returns 200
- [ ] `/webhook/telegram` accepts POST
- [ ] Console clean (0 unhandled errors)
- [ ] All routes return expected (not blank)
- [ ] Previous phase features still work

---

## 7. Definition of Done (Phase 5 complete)

- [ ] All bot commands working: `/start`, `/manage`, `/status`, `/today`, `/weekly`, `/report`, `/export`, `/settings`, `/help`, `/upgrade`
- [ ] SePay webhook pipeline live
- [ ] Email parsing 6 banks live
- [ ] Cross-source dedup verified
- [ ] Scheduled jobs: daily recap, monthly allocation, trial management
- [ ] Tier enforcement: Free (45tx, 5cat, 1bank), Pro (unlimited), Business (unlimited)
- [ ] Trial 14-day with reminder + auto-downgrade
- [ ] All handlers: try/catch + empty/error states
- [ ] Analytics events tracked
- [ ] p95 response time < 2s
- [ ] 0 cross-user data leakage
- [ ] Production deploy on Railway
- [ ] All user-facing messages served via `t(user.locale, key)` (vi + en)
- [ ] Language selection in onboarding (auto-detect + confirm)
- [ ] Language change in `/settings`
- [ ] Admin messages English hardcoded
- [ ] README + CHANGELOG updated

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial Telegram implementation plan — Phase 1-5 (9 tuần) |
| v1.1.0 | 2026-05-08 | **i18n integration:** (1) Phase 1 Day 4-5 — add `i18n/` module, `t()` helper, vi.py + en.py language packs, `locale_svc.py` auto-detect. (2) Phase 1 Day 6 — `/start` language confirm step, bilingual default categories. (3) Phase 2 Day 17 — settings language change. (4) Definition of Done thêm i18n criteria. |
