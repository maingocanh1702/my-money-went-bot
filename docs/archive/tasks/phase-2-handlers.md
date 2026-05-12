# Phase 2: Handlers Refactor — Task List

> **Status:** ⬜ Not Started
> **Tuần:** 3-4
> **Depends on:** Phase 1 ✅
> **Roadmap:** [mymoneywent-roadmap.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/mymoneywent-roadmap.md)
> **Key spec:** [development-workflow.md §4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/development-workflow.md) — strangler fig, each handler = own PR

---

## Strategy

Legacy `handlers/` → multi-tenant rewrite via `core/messenger/` interface. Each handler = 1 focused PR with isolation tests. Strangler fig pattern (W0.6 decision): legacy code coexists, new code uses `SendPayload` + `tenant_context`.

---

## Tasks

### Auth & Onboarding (F01)

- [ ] **T2.01** `/start` handler — multi-tenant rewrite
  - Spec: [feature-onboarding.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-onboarding.md) + [BE tech](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-onboarding-tech.md)
  - AC:
    - [ ] `INSERT INTO users` with `channel_type`, `channel_user_id`
    - [ ] Generate `webhook_token` via `mint_token()` (W0.6)
    - [ ] Generate `inbound_email` = `u{user_id}@in.tienvenoidau.com`
    - [ ] Create 3 default categories (Daily Spending, Saving, Subscription)
    - [ ] Assign 14-day Pro trial (`trial_ends_at = now + 14d`)
    - [ ] Welcome message via `SendPayload` + 3-path selector buttons
    - [ ] Idempotent — `/start` when account exists → show status
    - [ ] Tenant context set before any DB write
  - Tests: ≥8 (happy path, idempotent, missing fields, tenant isolation)
  - Estimate: 1.5 ngày

### Categorization (F03)

- [ ] **T2.02** Category picker handler — inline buttons
  - Spec: [feature-categorization.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-categorization.md)
  - AC:
    - [ ] Inline keyboard: 2 buttons/row, all active categories
    - [ ] "➕ New category" at end
    - [ ] "⏭️ Bỏ qua" for incoming tx
    - [ ] Sub-category picker after parent
    - [ ] State machine: `await_parent` → `await_sub` → `done` (via `bot_state` table)
    - [ ] "🔄 Wrong category?" on confirmation → re-pick
  - Tests: ≥6
  - Estimate: 1.5 ngày

### Category Management (F04)

- [ ] **T2.03** `/manage` handler — CRUD categories
  - Spec: [feature-category-management.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-category-management.md)
  - AC:
    - [ ] List categories + total per category
    - [ ] Tap category → Rename / Edit Budget / Delete (soft) / Sub-categories
    - [ ] Add category inline
    - [ ] Budget = 0 → tracking mode, > 0 → budgeted mode
    - [ ] Tier limits enforced (Free 5, Pro 20, Business unlimited)
  - Tests: ≥6
  - Estimate: 1 ngày

### Reports (F05)

- [ ] **T2.04** `/status` handler — monthly overview
  - Spec: [feature-reports.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-reports.md)
  - AC:
    - [ ] Tách BUDGETED vs TRACKING vs INCOME sections
    - [ ] Progress bar cho budgeted categories
    - [ ] Summary totals
  - Tests: ≥4
  - Estimate: 1 ngày

- [ ] **T2.05** `/today` handler — daily overview
  - AC:
    - [ ] Daily spending + progress bar if daily_cap set
    - [ ] Remaining budget
  - Tests: ≥3
  - Estimate: 0.5 ngày

### Settings (F07)

- [ ] **T2.06** `/settings` handler
  - Spec: [feature-settings.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-settings.md)
  - AC:
    - [ ] Show webhook URL + regenerate option
    - [ ] Show inbound email
    - [ ] Timezone selector
    - [ ] Toggle daily recap
    - [ ] Plan info + trial status
    - [ ] Regenerate webhook → invalidate old immediately
  - Tests: ≥5
  - Estimate: 1 ngày

### Funding Sources (F08)

- [ ] **T2.07** `/accounts` handler + auto-discovery
  - Spec: [feature-funding-sources.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md) + [BE tech](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-funding-sources-tech.md)
  - AC:
    - [ ] List funding sources (active + hidden)
    - [ ] Rename / Hide / Manual-add
    - [ ] Auto-discovery from SePay payload → UPSERT
    - [ ] Embed in category picker header
    - [ ] `funding_source_id` populated on tx INSERT
  - Tests: ≥6
  - Estimate: 1.5 ngày

### Admin Framework

- [ ] **T2.08** Admin command authorization middleware
  - AC:
    - [ ] `ADMIN_TELEGRAM_IDS` env var (comma-separated, multi-admin)
    - [ ] `@admin_only` decorator
    - [ ] Rate limit 30/min per admin
    - [ ] `admin_audit_log` INSERT on every admin command
    - [ ] Non-admin attempt → deny + log `admin_command_denied` event
  - Tests: ≥5
  - Estimate: 0.5 ngày

### Legacy Cleanup

- [ ] **T2.09** Remove legacy `handlers/transaction.py` (after T2.02 lands)
- [ ] **T2.10** Remove legacy `handlers/manage.py` (after T2.03 lands)
- [ ] **T2.11** Remove legacy `handlers/reports.py` (after T2.04+T2.05 land)
- [ ] **T2.12** Remove legacy `handlers/allocation.py` (after T2.03 lands)
- [ ] **T2.13** Remove legacy `telegram_api.py` (after all handlers use `core/messenger/`)
  - AC: `ruff` confirms 0 imports of old module
  - Estimate: 0.5 ngày total for T2.09-T2.13

---

## Phase 2 Definition of Done

- [ ] All 13 tasks ✅
- [ ] `pytest -v` ≥ 200 tests passing
- [ ] All handlers emit `SendPayload`, no raw Telegram API calls outside `core/messenger/`
- [ ] Legacy `handlers/` directory empty or removed
- [ ] Legacy `telegram_api.py` removed
- [ ] `lint-imports` clean
- [ ] `/start` → category picker → `/status` → `/manage` → `/settings` end-to-end flow works
