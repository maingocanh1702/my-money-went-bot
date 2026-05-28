# MyMoneyWent — Progress Dashboard

> **Auto-generated** từ [`implementation-tracker.md`](implementation-tracker.md) bằng `scripts/build-dashboard.py`.
> KHÔNG edit trực tiếp — sửa tracker rồi rebuild.
> **Cập nhật:** 2026-05-28 18:31 · **Branch hiện tại:** `main`

Để xem dashboard HTML đẹp hơn: mở [`dashboard.html`](dashboard.html) bằng browser.

---

## Tổng quan

- **MVP progress:** **17%** (6/36 PR merged)
- **In flight:** 0 PR · **Blocked:** 0 · **Deferred:** 0
- **Target launch:** Tháng 9/2026 (~16 weeks runway)

## Phase progress

| Phase | Merged / Total | % | Progress |
|-------|:--------------:|:-:|:---------|
| Phase 1 | 4 / 7 | 57% | `█████░░░░░` |
| Phase 2 | 2 / 10 | 20% | `██░░░░░░░░` |
| Phase 3 | 0 / 1 | 0% | `░░░░░░░░░░` |
| Phase 4 | 0 / 2 | 0% | `░░░░░░░░░░` |
| Phase 5 | 0 / 6 | 0% | `░░░░░░░░░░` |
| Phase 6 | 0 / 10 | 0% | `░░░░░░░░░░` |

## Phase breakdown — features & tasks

### Phase 1 — 4/7 · 57% `█████░░░░░`

| PR | Feature | Status | Computed | Branch |
|----|---------|:------:|:--------:|--------|
| `W0.7` | Public `request_id` helpers + F02 xfail contract pin | ✅ Merged | WAITING ✓ normal | `chore/W0.7-tenant-context-public-api` |
| `W0.8` | Webhook `display_suffix VARCHAR(8)` migration (G3 option b) | ✅ Merged | BACKLOG ✓ normal | `feat/webhook-display-suffix-migration` |
| `W0.9` | Dashboard realtime — auto-rebuild + git-state detect + reconcile | ✅ Merged | WAITING ✓ normal | `feat/dashboard-realtime` |
| `W0.10` | Dashboard v3 rich UI + click-through + Chart.js | ✅ Merged | WAITING ✓ normal | `feat/dashboard-v3-rich-v2` |
| `work-state-engine-1a` | Work-State Engine — Phase 1a (skeleton + filesystem + git) | ✅ Merged | WAITING ✓ normal | `feat/MYM-1-work-state-engine-1a` |
| `work-state-engine-1b` | Work-State Engine — Phase 1b (github + ci + railway collectors) | ✅ Merged | WAITING ✓ normal | `feat/MYM-3-work-state-engine-1b` |
| `work-state-engine-1b'` | Work-State Engine — Phase 1b' (dashboard projection follow-up) | ✅ Merged | WAITING ✓ normal | `feat/MYM-4-work-state-engine-1b-projection` |
| `work-state-engine-1c` | Work-State Engine — Phase 1c (driver + aggregation + persistence + workflow) | ✅ Merged | WAITING ✓ normal | `feat/MYM-5-work-state-engine-1c` |
| `dashboard-live-view-A` | Dashboard Live View — Phase A (engine→build wire) | ✅ Merged | WAITING ✓ normal | `feat/MYM-6-dashboard-live-view-A` |
| `dashboard-live-view-B` | Dashboard Live View — Phase B (doc-change awareness) | ✅ Merged | WAITING ✓ normal | `feat/MYM-7-dashboard-live-view-B` |
| `doc-change-hash-dedup` | Doc-change hash-aware dedup + engine emission wire | ✅ Merged | WAITING ✓ normal | `feat/MYM-8-doc-change-hash-dedup` |
| `work-state-engine-1d` | Work-State Engine — Phase 1d (urgency + MAX agg + foundation_change + projection) | ✅ Merged | WAITING ✓ normal | `feat/MYM-10-work-state-1d-urgency-bundle` |
| `W1.1` | Docker Compose dev + prod | ⬜ Not started | BACKLOG ✓ normal | `infra/W1.1-docker-compose` |
| `W1.2` | Discord adapter (`core/messenger/discord.py`) | ⬜ Not started | BACKLOG ✓ normal | `feat/W1.2-discord-adapter` |
| `W1.3` | Phase 1 integration smoke | ⬜ Not started | BACKLOG ✓ normal | `chore/W1.3-phase1-smoke` |

### Phase 2 — 2/10 · 20% `██░░░░░░░░`

| PR | Feature | Status | Computed | Branch |
|----|---------|:------:|:--------:|--------|
| `onboarding-start` | `/start` + user create + trial assign | ✅ Merged | BACKLOG ✓ normal | `feat/F01-onboarding-start` |
| `funding-sources` | Funding sources resolver + handlers | ⬜ Not started | WAITING ✓ normal | `feat/funding-sources` |
| `transaction-capture` | Transaction capture EXPANDED (inherit W0.6 legacy cutover) | ⬜ Not started | BACKLOG ✓ normal | `feat/transaction-capture` |
| `manual-transaction-entry` | Manual transaction entry — Channel 3 of transaction-capture | ⬜ Not started | BACKLOG ✓ normal | `feat/manual-transaction-entry` |
| `category-management` | Category management (`/manage`) | ⬜ Not started | BACKLOG ✓ normal | `feat/category-management` |
| `categorization` | Categorization auto-rules + manual | ⬜ Not started | BACKLOG ✓ normal | `feat/categorization` |
| `reports` | Reports `/status`, `/today`, `/weekly` | ⬜ Not started | WAITING ✓ normal | `feat/reports` |
| `settings` | Settings `/settings` | ✅ Merged | IN_PROGRESS ✓ normal | `feat/F07-settings` |
| `admin-auth` | Admin auth framework only (commands defer Phase 6) | ⬜ Not started | BACKLOG ✓ normal | `feat/admin-auth` |
| `i18n-locale-switcher` | VI/EN locale switcher | ⬜ Not started | BACKLOG ✓ normal | `feat/i18n-locale-switcher` |

### Phase 3 — 0/1 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Computed | Branch |
|----|---------|:------:|:--------:|--------|
| `pricing-tiers` | Tier limits + 14d trial + gating middleware | ⬜ Not started | WAITING ✓ normal | `feat/pricing-tiers` |

### Phase 4 — 0/2 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Computed | Branch |
|----|---------|:------:|:--------:|--------|
| `sepay-onboarding-paths` | Path A (Quick connect) + Path B (Wizard) | ⬜ Not started | BACKLOG ✓ normal | `feat/sepay-onboarding-paths` |
| `first-tx-celebration` | First-tx celebration flow | ⬜ Not started | BACKLOG ✓ normal | `feat/first-tx-celebration` |

### Phase 5 — 0/6 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Computed | Branch |
|----|---------|:------:|:--------:|--------|
| `W5.1` | Postmark inbound + `/inbound/{token}` route | ⬜ Not started | BACKLOG ✓ normal | `infra/W5.1-postmark-inbound` |
| `email-forwarding-onboarding` | Path C onboarding (email forwarding guides) | ⬜ Not started | BACKLOG ✓ normal | `feat/email-forwarding-onboarding` |
| `parser-techcombank` | Parser: Techcombank full extraction | ⬜ Not started | BACKLOG ✓ normal | `feat/parser-techcombank` |
| `parser-cake-vpbank` | Parser: Cake (VPBank) | ⬜ Not started | BACKLOG ✓ normal | `feat/parser-cake-vpbank` |
| `parser-mbbank` | Parser: MB Bank | ⬜ Not started | BACKLOG ✓ normal | `feat/parser-mbbank` |
| `parser-acb` | Parser: ACB (deferred to Phase 5b) | ⏸️ Deferred | BACKLOG ✓ normal | `feat/parser-acb` |
| `parser-sacombank` | Parser: Sacombank (deferred to Phase 5b) | ⏸️ Deferred | BACKLOG ✓ normal | `feat/parser-sacombank` |
| `parser-bidv` | Parser: BIDV (deferred to Phase 5b) | ⏸️ Deferred | BACKLOG ✓ normal | `feat/parser-bidv` |
| `cross-source-dedup` | Cross-source dedup (SePay + Email) | ⬜ Not started | BACKLOG ✓ normal | `feat/cross-source-dedup` |

### Phase 6 — 0/10 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Computed | Branch |
|----|---------|:------:|:--------:|--------|
| `scheduled-jobs` | Scheduled jobs (APScheduler, TZ jitter ±5min) | ⬜ Not started | BACKLOG ✓ normal | `feat/scheduled-jobs` |
| `payment-vietqr` | Payment VietQR + SePay auto-detect (4-layer fuzzy) | ⬜ Not started | BACKLOG ✓ normal | `feat/payment-vietqr` |
| `payment-email-backup` | Email backup detect (Techcombank email path) | ⬜ Not started | BACKLOG ✓ normal | `feat/payment-email-backup` |
| `payment-recurring` | Manual review fallback + recurring billing | ⬜ Not started | BACKLOG ✓ normal | `feat/payment-recurring` |
| `admin-commands` | Admin commands (`/admin_stats`, `/admin_cost`, `/admin_user`, `/admin_resolve`) | ⬜ Not started | BACKLOG ✓ normal | `feat/admin-commands` |
| `W6.1` | Sentry alerts — 7 critical (per observability-plan.md) | ⬜ Not started | BACKLOG ✓ normal | `infra/W6.1-sentry-alerts` |
| `messenger-channel` | Messenger adapter (feature-flagged `ENABLE_MESSENGER_CHANNEL=false`) | ⬜ Not started | BACKLOG ✓ normal | `feat/messenger-channel` |
| `W6.2` | Railway deploy + custom domain (tienvenoidau.com) | ⬜ Not started | BACKLOG ✓ normal | `infra/W6.2-railway-deploy` |
| `W6.3` | Backup automation (B2 + pg_dump daily, SSE-B2) | ⬜ Not started | BACKLOG ✓ normal | `infra/W6.3-backup-b2` |
| `W6.4` | DR runbook full validation (test restore) | ⬜ Not started | BACKLOG ✓ normal | `chore/W6.4-dr-restore-test` |
| `(to be created when Phase W enters implementation planning)` | — | ⏸️ Deferred | — | `—` |
| `parser-evolver` | GEPA-style auto-tune cho email parsers (POC: ACB) | ⏸️ Deferred | BACKLOG ✓ normal | `feat/MYM-XXX-parser-evolver-poc` |

## Timeline

```mermaid
gantt
    title MyMoneyWent roadmap
    dateFormat YYYY-MM-DD
    axisFormat %b
    section Phase 1
    P1 (57%) : active, 2026-05-05, 2026-05-22
    section Phase 2
    P2 (20%) : active, 2026-05-22, 2026-06-15
    section Phase 3
    P3 (0%) : 2026-06-15, 2026-06-25
    section Phase 4
    P4 (0%) : 2026-06-25, 2026-07-10
    section Phase 5
    P5 (0%) : 2026-07-10, 2026-08-10
    section Phase 6
    P6 (0%) : 2026-08-10, 2026-09-15
```

## Đang làm

_Không có PR active._

## Up next

| PR | Feature | Phase | Status |
|----|---------|-------|--------|
| `W1.1` | Docker Compose dev + prod | Phase 1 | ⬜ Not started |
| `W1.2` | Discord adapter (`core/messenger/discord.py`) | Phase 1 | ⬜ Not started |
| `W1.3` | Phase 1 integration smoke | Phase 1 | ⬜ Not started |
| `funding-sources` | Funding sources resolver + handlers | Phase 2 | ⬜ Not started |
| `transaction-capture` | Transaction capture EXPANDED (inherit W0.6 legacy cutover) | Phase 2 | ⬜ Not started |

---

**Rebuild:** chạy `python scripts/build-dashboard.py` sau mỗi PR merge (theo Step 10 của [development-workflow.md](operations/development-workflow.md) §2.7 Post-merge updates).
