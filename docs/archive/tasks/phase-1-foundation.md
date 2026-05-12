# Phase 1: Foundation — Task List

> **Status:** 🟡 In Progress (~75%)
> **Tuần:** 1-2 (remaining: ~1 tuần)
> **Depends on:** Phase 0 ✅
> **Roadmap:** [mymoneywent-roadmap.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/mymoneywent-roadmap.md)

---

## ✅ Completed (Wave 0)

- [x] **T1.01** Repo skeleton + monorepo structure — `core/`, `markets/vn/`, `markets/global_/` (W0.1)
- [x] **T1.02** Import boundary contracts — 4 contracts in `.importlinter` (W0.1 + W0.6)
- [x] **T1.03** CI pipeline — GitHub Actions: pre-commit → lint-imports → pytest (W0.1)
- [x] **T1.04** Pre-commit hooks — ruff, black, mypy, detect-secrets, lint-imports (W0.1)
- [x] **T1.05** DB schema migration — `0001_initial_schema.py`, 11 tables (W0.2)
  - `users`, `bank_connections`, `categories`, `funding_sources`, `transactions`, `webhook_tokens`, `bot_state`, `scheduled_jobs`, `monthly_reports`, `admin_audit_log`, `analytics_events`
- [x] **T1.06** asyncpg connection pool — `core/db.py` (min=2, max=10) (W0.3)
- [x] **T1.07** Tenant context — `core/tenant_context.py` ContextVar per-request (W0.3)
- [x] **T1.08** Tenant isolation proof — 2-user test + concurrent task isolation test (W0.3)
- [x] **T1.09** Messenger adapter interface — `core/messenger/base.py` BaseSender ABC + SendPayload (W0.4)
- [x] **T1.10** Telegram adapter — `core/messenger/telegram.py` TelegramSender (W0.4)
- [x] **T1.11** i18n stub — `core/messenger/i18n.py` + `locales/{vi,en}.json` (W0.4)
- [x] **T1.12** Structured logging — `core/logging.py` structlog + tenant binding (W0.5)
- [x] **T1.13** Sentry integration — `core/observability.py` before_send tags user_id/request_id (W0.5)
- [x] **T1.14** Health endpoints — `/health` liveness + `/health/detailed` DB check (W0.5)
- [x] **T1.15** Request ID middleware — UUID4 per request, propagates to tenant_context (W0.5)
- [x] **T1.16** Canonical transaction schema — `core/canonical_tx.py` CanonicalTx dataclass (W0.6)
- [x] **T1.17** Email parser plugin framework — `markets/vn/email_parsers/` + `@register_parser` (W0.6)
- [x] **T1.18** 6 bank parser shells — TCB, Cake, ACB, Sacombank, BIDV, MB (W0.6)
- [x] **T1.19** SePay webhook handler — `markets/vn/capture/sepay_webhook.py` (W0.6)
- [x] **T1.20** Webhook token system — `markets/vn/capture/webhook_tokens.py` SHA-256 hash (W0.6)
- [x] **T1.21** Founder seed scaffold — `scripts/migrate_sheets.py` dry-run skeleton (W0.6)
- [x] **T1.22** Parser purity contract — `parsers-are-pure` import-linter contract (W0.6)

## 🔲 Remaining

- [ ] **T1.23** Discord adapter
  - File: `core/messenger/discord.py`
  - Spec: [feature-discord-channel.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-discord-channel.md)
  - Pattern: Follow TelegramSender — implement BaseSender, `@register_sender("discord")`
  - AC:
    - [ ] Slash command support (Discord interactions endpoint)
    - [ ] Button → Discord components (action rows)
    - [ ] parse_mode mapping (Discord markdown)
    - [ ] Contract test extends `ADAPTERS` parametrisation in `test_messenger_contract.py`
  - Estimate: 1-2 ngày

- [ ] **T1.24** Docker Compose (dev)
  - File: `docker-compose.yml`
  - Services: app (Python), postgres (16-alpine), redis (optional, defer if not needed)
  - AC:
    - [ ] `docker compose up` spins up dev environment
    - [ ] Alembic auto-migrate on startup
    - [ ] Hot reload (volume mount)
    - [ ] `.env.example` documents required vars
  - Estimate: 0.5 ngày

- [ ] **T1.25** Docker Compose (prod/Railway)
  - File: `railway.toml` update, `Dockerfile` if needed
  - AC:
    - [ ] Railway deploy config matches dev stack
    - [ ] Health check endpoint configured
  - Estimate: 0.5 ngày

- [ ] **T1.26** Founder seed — implement `_step_*` functions
  - File: `scripts/migrate_sheets.py`
  - AC:
    - [ ] `_step_users()` reads from Google Sheets → INSERT users
    - [ ] `_step_categories()` reads categories
    - [ ] `_step_funding_sources()` reads col P
    - [ ] `_step_transactions()` reads transactions
    - [ ] Idempotent (re-run safe)
    - [ ] Verification passes
  - Depends on: T1.06 (pool), T1.05 (schema)
  - Estimate: 1 ngày

---

## Phase 1 Definition of Done

- [ ] All 26 tasks ✅
- [ ] `pytest -v` ≥ 130 tests passing
- [ ] `lint-imports` 4+ contracts, 0 broken
- [ ] `ruff` / `black --check` / `mypy --strict` all green
- [ ] `docker compose up` → app + DB running, `/health/detailed` returns 200
- [ ] Discord adapter passes contract tests
- [ ] Founder seed script runs successfully (dry-run → `--apply`)
