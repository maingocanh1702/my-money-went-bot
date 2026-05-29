# Tiền Về Nơi Đâu / My Money Went — Roadmap

> **Version:** v2.0.0
> **Ngày tạo:** 2026-05-11
> **Cập nhật lần cuối:** 2026-05-30
> **Trạng thái:** Active
> **Tham chiếu:** [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.7.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [TDD-vi v1.8.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)
> **Execution tracking:** [START HERE](START_HERE.md) → [Implementation Tracker](implementation-tracker.md) (PR-level status board) · [Phase 1](implementation-plans/phase-1-foundation-remaining.md) · [Phase 2](implementation-plans/phase-2-handlers.md) · [Phase 3](implementation-plans/phase-3-pricing.md) · [Phase 4](implementation-plans/phase-4-sepay-onboarding.md) · [Phase 5](implementation-plans/phase-5-email-parsing.md) · [Phase 6](implementation-plans/phase-6-polish-deploy.md)

> **Note:** Project dùng Telegram / Zalo / Discord / Messenger làm frontend (chat-based UI). Không có web/mobile UI → không cần file `.pen` hay screen design.

---

## 1. Overall Progress

**Tổng tiến độ: 40%** `████████░░░░░░░░░░░░` (Foundation near-complete, Zalo channel WIP)

| Phase | Status | Progress | Tasks |
|-------|--------|----------|-------|
| Phase 0: Docs & Specs | ✅ Complete | 100% | — |
| Phase 1: Foundation | 🟡 In Progress | ~95% | [plan](implementation-plans/phase-1-foundation-remaining.md) |
| Phase 2: Handlers Refactor | 🟡 Early | ~20% | [10 PRs](implementation-plans/phase-2-handlers.md) |
| Phase 3: Pricing Logic | ⬜ Not Started | 0% | [1 PR](implementation-plans/phase-3-pricing.md) |
| Phase 4: SePay Onboarding | ⬜ Not Started | 0% | [2 PRs](implementation-plans/phase-4-sepay-onboarding.md) |
| Phase 5: Email Parsing | ⬜ Not Started | 0% | [plan](implementation-plans/phase-5-email-parsing.md) |
| Phase 6: Polish + Deploy | ⬜ Not Started | 0% | [10 PRs](implementation-plans/phase-6-polish-deploy.md) |
| Phase 7: Closed Beta | ⬜ Not Started | 0% | — (create plan when Phase 6 ships) |
| Phase 8: Public Soft Launch | ⬜ Not Started | 0% | ↑ same file |
| Phase 9-10: Growth + Business Tier | ⬜ Not Started | 0% | — (create when Phase 8 ships) |
| Phase 11: Family Plan | ⬜ Not Started | 0% | — (create when pricing-tiers addendum merged) |


---

## 2. Feature Modules

**Feature implementation: 15%** `███░░░░░░░░░░░░░░░░░` (Foundation infra shipped, onboarding + settings + Zalo core landed)

| Module | Feature | Spec | BE Tech | BE Code | Bot Code | Phase |
|--------|---------|:----:|:-------:|:-------:|:--------:|:-----:|
| onboarding-start | 3-Path Onboarding | ✅ | ✅ | ✅ `/start` shipped | ✅ TG+Zalo | 1,4 |
| transaction-capture | Transaction Capture (SePay + Email) | ✅ | ✅ | 🟡 webhook_tokens + parsers shell + `_persist()` returns `int\|None` | ⬜ | 1,5 |
| categorization | Transaction Categorization | ✅ | ✅ | 🟡 `categorize.py` DB queue (Zalo) | ⬜ | 2 |
| category-management | Category Management (/manage) | ✅ | ✅ | ⬜ | ⬜ | 2 |
| reports | Reports (/status, /today, /weekly) | ✅ | ✅ | ⬜ | ⬜ | 2 |
| pricing-tiers | Pricing, Tier Limits & Trial | ✅ | ✅ | ⬜ | ⬜ | 3 |
| settings | Settings (/settings) | ✅ | ✅ | ✅ shipped | ✅ TG | 2 |
| funding-sources | Funding Sources | ✅ | ✅ | 🟡 DDL landed W0.2 | ⬜ | 2 |
| scheduled-jobs | Scheduled Jobs | ✅ | ✅ | ⬜ | ⬜ | 6 |
| F10 | Payment (Bank Transfer Auto-Detect) | ✅ | ✅ | ⬜ | ⬜ | 6 |
| F11 | Admin Tools & Audit | ✅ | ✅ | 🟡 audit_log table W0.2 | ⬜ | 6 |
| F12 | Multi-User Data Isolation | ✅ (PRD) | — | ✅ tenant_context W0.3 | — | 1 |
| messenger-channel | Messenger Channel | ✅ | ✅ | ⬜ | ⬜ | 6 |
| zalo-channel | Zalo Channel | 🟡 impl plan | — | 🟡 sender + webhook + migration 0004 (local) | 🟡 `/start` + category picker | 1 |
| F14 | Discord Channel | ✅ | ✅ | ⬜ | ⬜ | 1 |
| F15 | Personal vs Business Toggle | ✅ | ✅ | ⬜ | ⬜ | 9 |
| F16 | P&L View | ⬜ | ⬜ | ⬜ | ⬜ | 9 |
| F17 | Income Source Attribution | ⬜ | ⬜ | ⬜ | ⬜ | 9 |
| i18n-locale-switcher | Internationalization | ✅ | ✅ | 🟡 `i18n/` package landed + 11 categorize keys | — | 1 |
| F-saas | SaaS Refactor | ✅ | ✅ | 🟡 foundation W0.1-W0.6 + SePay multi-tenant (C1 P1-P3) | — | 1 |
| FAM | Family Plan | ✅ v1.2.0 | ✅ v1.1.0 | ⬜ | ⬜ | 11 |

> **Numbering note:** funding-sources = Funding Sources (entity model, DDL landed W0.2). F12 = Multi-User Data Isolation (tenant_context, not a standalone service). zalo-channel added v2.0.0 (implementation plan v0.6.0, core code WIP locally). Aligned with PRD convention post W0.2.

---

## 3. Timeline

**Target launch:** Tháng 9/2026 (tuần 15-16 from dev start)
**Wave 0 complete:** 2026-05-11 (6 PRs: W0.1-W0.6 merged, 112 tests passing) + 2026-05-12 W0.7-W0.8 + 2026-05-13 W0.9-W0.10 + settings + onboarding-start
**Work-State Engine:** 2026-05-20~21 (8 PRs merged: MYM-1/3/4/5/6/7/8/10, 340+ tests in engine suite)
**Security batch B:** 2026-05-22 (9 fixes merged: H5, H7, M1-M7, SSRF)
**Zalo channel:** 2026-05-28 (migration 0004 committed, core code WIP locally)
**Phase 1 remaining:** Docker Compose + Discord adapter + Zalo commit/cleanup

```
2026
 May                          Jun          Jul          Aug          Sep
  |──W0─|─W0 followups──|Zalo|──P2─|──P3|──P4|────P5────|────P6─────|P7─|P8─|
  Wave 0  WSE+DashLive   Chan  Hand  Price SePay  Email    Polish+    Beta Launch
  (6 PRs) Security        nel   lers        Onbd   Parse    Deploy
                                                              |──P9-10──|──P11──|
                                                              Growth     Family
                                                              Business   Plan
```

---

## 4. Phase Details

### Phase 0: Docs & Specs ✅ COMPLETE (2026-05-11)

> All specs, ADRs, and operation docs locked. Code lives in Phase 1 (Wave 0 PRs).

| Deliverable | Status | Link |
|-------------|:------:|------|
| BRD-vi | ✅ v3.1.0 | [brd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) |
| BRD-en | ✅ v3.1.0 | [brd-en.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-en.md) |
| PRD-vi | ✅ v1.7.1 | [prd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) |
| PRD-en | ✅ v1.5.0 | [prd-en.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-en.md) |
| TDD-vi | ✅ v1.8.1 | [tdd-vi.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) |
| TDD-en | ✅ | [tdd-en.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-en.md) |
| ADR-0001 (Monorepo) | ✅ | [0001-monorepo.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md) |
| ADR-0002 (Onboarding UI) | ✅ | [0002-onboarding-ui.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md) |
| ADR-0003 (Identity Model) | 🟡 Local | [0003-identity-model.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0003-identity-model-accounts-channels.md) |
| Market Strategy Overview | ✅ | [market-strategy-overview.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/market-strategy-overview.md) |
| Development Workflow | ✅ | [development-workflow.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/development-workflow.md) |
| Feature Specs (onboarding-start-F14, FAM) | ✅ | [docs/features/](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features) |
| BE Tech Docs (17 files) | ✅ | [docs/features/BE/](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE) |
| Feature: Family Plan — Product | ✅ v1.2.0 | [feature-family-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-family-plan.md) |
| Feature: Family Plan — BE Tech | ✅ v1.1.0 | [feature-family-plan-tech.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-family-plan-tech.md) |
| Zalo Channel Core Plan | 🟡 v0.6.0 | [implementation-plan-zalo-channel-core.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-zalo-channel-core.md) |
| Zalo Multi-User Research | 🟡 Local | [research-zalo-multi-user-bot.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/research-zalo-multi-user-bot.md) |
| Observability Plan | ✅ | [observability-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md) |
| DR Runbook | ✅ | [disaster-recovery.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md) |
| Competitive Research | ✅ | [research/](file:///Users/maingocanh/Projects/MyMoneyWent/docs/research) |

---

### Phase 1: Foundation 🟡 (~95% complete)

> Wave 0 PRs (W0.1→W0.6) shipped 2026-05-11. W0.7-W0.10 follow-ups shipped 2026-05-12~13. Work-State Engine (8 PRs) + Dashboard Live View A/B shipped 2026-05-20~21. Security batch B shipped 2026-05-22. Zalo channel migration 0004 committed 2026-05-28. Remaining: Docker Compose, Discord adapter, Zalo channel commit.

**Wave 0 PRs (shipped):**

| PR | Scope | Tests | Status |
|----|-------|:-----:|:------:|
| W0.1 | Repo skeleton + `.importlinter` (3 contracts) + CI + pre-commit | 4 | ✅ Merged |
| W0.2 | Alembic + `0001_initial_schema.py` (11 tables incl. `funding_sources`, `webhook_tokens`) | 20 | ✅ Merged |
| W0.3 | `core/db.py` asyncpg pool + `core/tenant_context.py` + 2-user isolation proof | 12 | ✅ Merged |
| W0.4 | `core/messenger/` (BaseSender ABC + SendPayload + TelegramSender + i18n stub) | 25 | ✅ Merged |
| W0.5 | `core/logging.py` structlog + `core/observability.py` Sentry + `/health` endpoints | 14 | ✅ Merged |
| W0.6 | Plugin email parsers (6 bank shells) + SePay webhook handler + founder seed scaffold + `parsers-are-pure` contract | 34 | ✅ Merged |
| W0.7 | Public `request_id` helpers + transaction-capture contract pin | +3 | ✅ Merged 2026-05-12 |
| W0.8 | Webhook `display_suffix VARCHAR(8)` migration | +3 | ✅ Merged 2026-05-12 |
| W0.9 | Dashboard realtime auto-rebuild + git-state detect + reconcile | +21 | ✅ Merged 2026-05-13 |
| W0.10 | Dashboard v3 rich UI + Chart.js burndown + filter + search | +311 LOC | ✅ Merged 2026-05-13 |
| **Total W0** | | **~130 tests** | **5 import-linter contracts** |

**Wave 0 follow-ups (shipped 2026-05-20~21):**

| PR | Scope | Tests | Status |
|----|-------|:-----:|:------:|
| MYM-1 (1a) | Work-State Engine skeleton + filesystem + git collectors | 127+6 e2e | ✅ Merged 2026-05-20 |
| MYM-3 (1b) | GitHub + CI + Railway collectors | 63 new (190 total) | ✅ Merged 2026-05-20 |
| MYM-4 (1b') | Dashboard projection | 23 new (213 total) | ✅ Merged 2026-05-21 |
| MYM-5 (1c) | Engine driver + aggregation + persistence + workflow | 32 new (245 total) | ✅ Merged 2026-05-21 |
| MYM-6 | Dashboard Live View Phase A (engine→build wire) | +369 LOC tests | ✅ Merged 2026-05-21 |
| MYM-7 | Dashboard Live View Phase B (doc-change awareness) | +5 signal fields, +4 overlays | ✅ Merged 2026-05-21 |
| MYM-8 | Doc-change hash-aware dedup + emission wire | 12 new (340 total) | ✅ Merged 2026-05-21 |
| MYM-10 (1d) | Urgency derivation + MAX agg + foundation_change + projection | +28 tests | ✅ Merged 2026-05-21 |
| MYM-11 | Spec §8.2 reconcile — CANONICAL_OVERLAYS +3 code extras | test fix | ✅ Merged 2026-05-21 |
| Security B | 9 fixes (H5, H7, M1-M7, SSRF) | — | ✅ Merged 2026-05-22 |
| SePay multi-tenant | C1 P1-P3 (DB pool+Sentry wire, multi-tenant webhook route, parallel-run telemetry) | — | ✅ Merged 2026-05-15 |

**Zalo channel (WIP 2026-05-28):**

| PR | Scope | Tests | Status |
|----|-------|:-----:|:------:|
| Zalo core | Migration 0004 (`channel_chat_id`, `chk_channel_type` +zalo) + start handler routing | migration+start tests | ✅ Committed to main |
| Zalo sender | `core/messenger/zalo.py` ZaloSender + OAuth token refresh | unit+contract | 🟡 Local (untracked) |
| Zalo webhook | `POST /zalo/webhook` route + `core/handlers/categorize.py` DB queue | unit+integration | 🟡 Local (untracked) |

**Task breakdown:**

| Task | Status | Notes |
|------|:------:|-------|
| Repo structure (monorepo per ADR-0001) | ✅ | `core/`, `markets/vn/`, `markets/global_/` — W0.1 |
| DB schema migration (PostgreSQL) | ✅ | `0001_initial_schema.py` (11 tables) + `0004_add_zalo_channel` |
| Multi-user routing | ✅ | `core/messenger/send.py` — W0.4 |
| Telegram adapter | ✅ | `core/messenger/telegram.py` — W0.4 |
| Zalo adapter | 🟡 | `core/messenger/zalo.py` — local, pending commit |
| Discord adapter | ⬜ | `core/messenger/discord.py` — pending |
| Docker Compose setup | ⬜ | Dev + prod configs — pending |
| Tenant isolation middleware | ✅ | `core/tenant_context.py` — W0.3 (ContextVar, 7 tests) |
| asyncpg connection pool | ✅ | `core/db.py` — W0.3 (min=2, max=10) |
| Structured logging | ✅ | `core/logging.py` structlog + tenant binding — W0.5 |
| Sentry + health endpoints | ✅ | `core/observability.py` + `/health` + `/health/detailed` — W0.5 |
| Import boundary contracts | ✅ | `.importlinter` — 5 contracts — W0.1 + W0.6 (incl. `i18n-is-pure`) |
| SePay webhook handler | ✅ | `markets/vn/capture/sepay_webhook.py` — W0.6 + multi-tenant C1 |
| Webhook token system | ✅ | `markets/vn/capture/webhook_tokens.py` — W0.6 (SHA-256 hash, never stores raw) |
| Email parser plugin framework | ✅ | `markets/vn/email_parsers/` — 6 bank shells + `@register_parser` decorator — W0.6 |
| Canonical transaction schema | ✅ | `core/canonical_tx.py` — W0.6 |
| Founder seed scaffold | ✅ | `scripts/migrate_sheets.py` — W0.6 (dry-run only) |
| Work-State Engine | ✅ | `scripts/work_state/` — 8 PRs, 340+ tests (being moved to `tools/dashboard-engine/`) |
| Dashboard Live View | ✅ | Engine→build wire + doc-change awareness — MYM-6/7 |
| Security hardening | ✅ | Batch B: 9 fixes (H5, H7, M1-M7, SSRF) + review quick wins |

### Phase 2: Handlers Refactor (Tuần 3-4)

| Task | Status | Notes |
|------|:------:|-------|
| Refactor handlers → multi-user | ⬜ | Via messenger interface (Telegram + Discord adapters) |
| Auth flow | ⬜ | `/start` → create user → assign trial |
| Category CRUD handlers | ⬜ | categorization + category-management |
| Report handlers | ⬜ | reports: `/status`, `/today` |
| Settings handlers | ⬜ | settings: `/settings` |
| Funding sources handlers | ⬜ | funding-sources (DDL landed, service logic pending) |
| Admin command authorization framework | ⬜ | `ADMIN_IDS` per platform |
| Legacy handler migration (strangler fig) | ⬜ | Deferred from W0.6 → transaction-capture scope. Each handler = own PR |

### Phase 3: Pricing Logic (Tuần 5)

| Task | Status | Notes |
|------|:------:|-------|
| Free tier limits (45 tx, 1 bank, 30d history, 5 cat) | ⬜ | pricing-tiers |
| 14-day Pro trial logic | ⬜ | Auto-assign on signup, auto-downgrade |
| Upgrade triggers | ⬜ | Max 1/tuần/user |
| Tier gating middleware | ⬜ | Check tier before feature access |

### Phase 4: SePay Onboarding (Tuần 6)

| Task | Status | Notes |
|------|:------:|-------|
| Path A: Quick connect | ⬜ | Generate webhook URL, guide user |
| Path B: SePay wizard | ⬜ | Step-by-step 3 steps with ✅/❓ |
| SePay webhook endpoint (wiring) | 🟡 | Handler exists (W0.6), needs route wiring + bot response |
| First tx celebration flow | ⬜ | "🎉 Setup hoàn tất!" |

### Phase 5: Email Parsing (Tuần 7-9)

| Task | Status | Notes |
|------|:------:|-------|
| Postmark inbound setup | ⬜ | `POST /inbound/{user_token}` |
| Path C: Email forwarding onboarding | ⬜ | Gmail + Outlook guides |
| Parser: TCB (Techcombank) | 🟡 | Shell exists (W0.6), full HTML extraction pending |
| Parser: Cake (VPBank) | 🟡 | Shell exists (W0.6), full HTML extraction pending |
| Parser: ACB | 🟡 | Shell exists (W0.6), full extraction pending |
| Parser: STB (Sacombank) | 🟡 | Shell exists (W0.6), full extraction pending |
| Parser: BIDV | 🟡 | Shell exists (W0.6), full extraction pending |
| Parser: MB Bank | 🟡 | Shell exists (W0.6), full extraction pending |
| Unparsed fallback notification | ⬜ | "Email đến nhưng không parse được" |
| Cross-source dedup (SePay + Email) | ⬜ | Fuzzy: same amount + type within 3 min |

### Phase 6: Polish + Deploy (Tuần 10-12)

| Task | Status | Notes |
|------|:------:|-------|
| Scheduling per timezone (APScheduler) | ⬜ | Jitter ±5 min per user |
| Payment: VietQR generation | ⬜ | 2 QR (VCB primary + TCB secondary) |
| Payment: Auto-detect via SePay | ⬜ | 4-layer fuzzy matching |
| Payment: Email backup detect | ⬜ | TCB email → Postmark → match |
| Payment: Manual review fallback | ⬜ | `/admin_resolve` |
| Payment: Recurring billing logic | ⬜ | Monthly 3d reminder + 7d grace |
| Admin tools: `/admin_stats` | ⬜ | F11 |
| Admin tools: `/admin_cost` | ⬜ | F11 |
| Admin tools: `/admin_user` | ⬜ | F11 |
| Admin tools: `/admin_resolve` | ⬜ | F11 |
| Observability: Sentry + alerts | 🟡 | Sentry init done (W0.5), 7 critical alerts pending |
| Messenger adapter (feature-flagged) | ⬜ | messenger-channel, `ENABLE_MESSENGER_CHANNEL` |
| Railway production deploy + domain | ⬜ | `tienvenoidau.com` |
| Backup automation (B2 + pg_dump) | ⬜ | Daily, SSE-B2 encryption |
| DR runbook validation | ⬜ | Test backup restore |

### Phase 7: Closed Beta (Tuần 13-14)

| Task | Status | Notes |
|------|:------:|-------|
| Recruit 5-10 beta users (Minh/Linh persona) | ⬜ | Friends + network |
| Monitor: actual cost vs BRD projections | ⬜ | Target ≤$25/mo |
| Monitor: parser accuracy per bank | ⬜ | Target ≥85% |
| Bug triage + critical fixes | ⬜ | |
| Backup recovery full test | ⬜ | DR runbook §11 |

### Phase 8: Public Soft Launch (Tuần 15-16)

| Task | Status | Notes |
|------|:------:|-------|
| Open to 20-30 users | ⬜ | Organic channels |
| Validate 3 onboarding paths | ⬜ | Measure completion rate |
| Monitor conversion Free→Pro | ⬜ | Target ≥5% |
| `@TienVeNoiDauUpdates` channel live | ⬜ | Out-of-band notification |

### Phase 9-10: Growth + Business Tier (Tháng 4-12 sau launch)

| Task | Status | Notes |
|------|:------:|-------|
| Growth: 30→100→500 users | ⬜ | GTM per BRD §12 |
| Hùng+ customer interviews (5-7) | ⬜ | Validate Business hypothesis |
| Beta concierge (5 sellers) | ⬜ | Manual P&L before build |
| F15: Personal vs Business Toggle | ⬜ | Must-have bundle (spec ✅) |
| F16: Tag-based P&L View | ⬜ | Must-have bundle |
| F17: Income Source Attribution | ⬜ | Must-have bundle |
| Multi-bank 5 accounts (Business) | ⬜ | Expand from Pro 3 |
| Email parser Tier 2 (6 banks) | ⬜ | VCB, VietinBank, TPBank, VPBank, HDBank, Agribank |
| Google Sheets 2-way sync | ⬜ | Business tier |
| Business tier launch | ⬜ | Target: tháng 11-12/2026 |

### Phase 11: Family Plan (Post Business launch — 2026 Q3+)

> **Blocked by:** pricing-tiers Pricing Addendum merge (decisions locked 2026-05-11, doc merge pending)

| Task | Status | Notes |
|------|:------:|-------|
| Merge pricing-tiers Pricing Addendum | ⬜ | Decisions locked: Pro 99k, Family 169k, Business 299k, grandfather 6mo. Doc merge pending. |
| Migration: 7 tables DDL | ⬜ | BE tech doc v1.1.0 |
| Family service: purchase, invite, accept, leave, remove | ⬜ | |
| Consent gate middleware | ⬜ | Disclosure versioned |
| Budget service + alert system | ⬜ | `family_budget_alerts` dedup |
| Invite accept session flow | ⬜ | `session_hash` pattern (10 min TTL) |
| Entitlement extension | ⬜ | `can_ingest_transaction()` per member |
| Bot handlers: `/family *`, `/my *` | ⬜ | 10 commands + 7 callbacks |
| Cron: invite expiry (hourly), `close_stale_memberships` (daily) | ⬜ | 90d → archived terminal |
| Grandfather pricing migration | ⬜ | 6 tháng giá cũ |
| Phase 2 — Ownership transfer | ⬜ | Deferred |

---

## 5. Phase Summary

| Phase | Tuần | Backend | Bot/Frontend | Docs |
|-------|:----:|:-------:|:------------:|:----:|
| 0: Docs & Specs | Done | — | — | ✅ 100% |
| 1: Foundation | ~done | 🟡 95% (W0+WSE+security+Zalo shipped) | 🟡 Telegram ✅ / Zalo 🟡 / Discord pending | ✅ |
| 2: Handlers | 3-4 | 🟡 20% (settings+onboarding ✅) | 🟡 2/10 commands | ✅ |
| 3: Pricing | 5 | ⬜ Tier logic | ⬜ Gating | ✅ |
| 4: SePay | 6 | 🟡 Handler exists + multi-tenant route | ⬜ Onboarding | ✅ |
| 5: Email | 7-9 | 🟡 Parser shells exist | ⬜ Path C | ✅ |
| 6: Polish | 10-12 | ⬜ Payment + Admin | ⬜ Messenger | ✅ |
| 7: Beta | 13-14 | ⬜ Fixes | ⬜ Fixes | ✅ |
| 8: Launch | 15-16 | ⬜ Monitor | ⬜ Monitor | ✅ |
| 9-10: Business | Post-launch | ⬜ P&L + Sheets | ⬜ Toggle | 🟡 F16/F17 pending |
| 11: Family | Post-Business | ⬜ 7 tables + service | ⬜ 10 cmds | ✅ |

---

## 6. Blockers & Dependencies

| Blocker | Affects | Status | Notes |
|---------|---------|:------:|-------|
| pricing-tiers Pricing Addendum doc merge | Phase 11 (Family Plan) | 🟡 Decisions locked, merge pending | Pro 99k, Family 169k, Business 299k — locked 2026-05-11 |
| Meta App Review (`pages_messaging`) | Phase 6 (Messenger flip ON) | 🔲 Pending | External dependency |
| Hộ kinh doanh registration | Phase 6 (Payment) | 🔲 Pending | Lead time 1-2 tuần |
| Hùng+ customer interviews (5-7) | Phase 9 (Business go/no-go) | 🔲 Pending | Validate hypothesis |
| ~~Bot Finance → SaaS migration~~ | ~~Phase 1~~ | ✅ Resolved | Strangler fig pattern. W0.6 ships invariants. Legacy cutover deferred to transaction-capture handler refactor. |
| Discord adapter | Phase 1 completion | 🔲 Pending | Last remaining Phase 1 item besides cleanup |
| Zalo OA live fixture | Zalo channel commit | 🔲 Pending | Need real webhook fixture to confirm signature formula + payload shape before prod |
| Zalo OA credentials | Zalo channel production | 🔲 Pending | App ID + secret key + access token needed from Zalo Developer Console |

---

## 7. Risk Register (Roadmap-Level)

| Risk | Phase | Impact | Mitigation |
|------|:-----:|:------:|------------|
| Email parser Phase 5 slip | 5 | Medium | Parser shells + plugin framework exist (W0.6). Fallback: giảm scope xuống 3 banks MVP (TCB, Cake, MB) |
| Low conversion Free→Pro | 8+ | Medium | Monitor hit-limit-rate, adjust 45→60-75 if churn > upgrade |
| Business tier validation fail | 9 | High | Reposition as personal+freelancer tracker |
| Railway cost > $50/mo | 8+ | Medium | Trigger Hetzner migration |
| Family Plan pricing conflict | 11 | Low (decisions locked) | Merge pricing-tiers addendum doc — decision work done |
| Legacy handler migration drag | 2 | Medium | Each handler = focused PR with isolation tests |

---

## 8. Key Metrics to Track

| Metric | Current (2026-05-30) | Phase 7-8 Target | Phase 9-10 Target | Phase 11+ Target |
|--------|:------------:|:----------------:|:-----------------:|:----------------:|
| Tests collected | 293+ (13 collection errors from WIP) | 300+ | 500+ | 700+ |
| Import contracts | 5 | 6+ | 7+ | 8+ |
| Active users | 0 | 10-30 | 100-500 | 500+ |
| Paying users (%) | — | ≥5% | ≥8-10% | ≥10% |
| MRR (VND) | 0 | 0 (beta) | 2.5-7.5tr | 10tr+ |
| Retention 30d | — | ≥60% | ≥70% | ≥75% |
| Parser accuracy | — | ≥85%/bank | ≥90%/bank | ≥95%/bank |
| Infra cost/mo | $0 | ≤$25 | ≤$50 | ≤$100 |
| Channels supported | 1 (TG) + 1 WIP (Zalo) | 2-3 | 3-4 | 4 |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-11 | Initial roadmap. 11 phases. Phase 0 at 75%. Chat-based UI, no .pen needed. |
| v1.1.0 | 2026-05-12 | **Major accuracy fix:** Phase 0 → COMPLETE (specs/ADRs/ops docs locked). Phase 1 → 75% (W0.1-W0.6 PRs shipped, 112 cases / 14 files, 4 contracts; Discord + Docker pending). funding-sources = Funding Sources (corrected from "Data Isolation"). BE Tech Docs → ✅ (17 files exist). Added i18n-locale-switcher, F-saas to module table. F15 spec status → ✅. Blocker "Bot Finance migration" → ✅ resolved (strangler fig W0.6). Family blocker reworded: decisions locked, doc merge pending. Timeline baseline updated (W0 done = potential compression). Wave 0 PR detail table moved from Phase 0 → Phase 1 (Phase 0 = specs only, code is Phase 1). Family Plan canonical link → `docs/features/feature-family-plan.md` (drafts/ stale v1.0.0 superseded). Email parser slip risk impact: High → Medium (shells exist). |
| v1.2.0 | 2026-05-13 | **Structure cleanup:** Import-linter contracts 4→5 (added `i18n-is-pure`, missed in v1.1.0). Task links → `implementation-plans/` (source of truth). `docs/tasks/` archived → `docs/archive/tasks/`. Added START_HERE.md entry point link. Autopilot files → `docs/autopilot/`. |
| v2.0.0 | 2026-05-30 | **Major sync (17 days of shipped work).** Phase 1 progress 75%→95%. Added: (1) Work-State Engine 8 PRs (MYM-1/3/4/5/6/7/8/10, 340+ tests) shipped 2026-05-20~21 — dashboard engine pipeline fully operational. (2) Dashboard Live View A/B merged. (3) Security batch B: 9 fixes (H5, H7, M1-M7, SSRF) merged 2026-05-22. (4) SePay multi-tenant C1 P1-P3 merged 2026-05-15. (5) Zalo channel core: migration 0004 committed, sender+webhook+categorize WIP locally (implementation plan v0.6.0). (6) ADR-0003 Identity Model (local). (7) Zalo multi-user research doc (local). Feature modules: +zalo-channel row, onboarding-start/settings→✅ shipped, i18n→package landed, transaction-capture→`_persist()` return type change, categorization→DB queue WIP. Phase 2 early: 20% (settings+onboarding ✅). Tests: 112→293+ collected. Blockers: +2 Zalo OA items. Metrics: +channels row. Timeline ASCII updated. Dashboard engine files being relocated `scripts/work_state/` → `tools/dashboard-engine/`. |
