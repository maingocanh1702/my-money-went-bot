# MyMoneyWent — Progress Dashboard

> **Auto-generated** từ [`implementation-tracker.md`](implementation-tracker.md) bằng `scripts/build-dashboard.py`.
> KHÔNG edit trực tiếp — sửa tracker rồi rebuild.
> **Cập nhật:** 2026-05-13 08:19 · **Branch hiện tại:** `main`

Để xem dashboard HTML đẹp hơn: mở [`dashboard.html`](dashboard.html) bằng browser.

---

## Tổng quan

- **MVP progress:** **11%** (4/35 PR merged)
- **In flight:** 1 PR · **Blocked:** 0 · **Deferred:** 0
- **Target launch:** Tháng 9/2026 (~16 weeks runway)

## Phase progress

| Phase | Merged / Total | % | Progress |
|-------|:--------------:|:-:|:---------|
| Phase 1 | 3 / 7 | 43% | `████░░░░░░` |
| Phase 2 | 1 / 9 | 11% | `█░░░░░░░░░` |
| Phase 3 | 0 / 1 | 0% | `░░░░░░░░░░` |
| Phase 4 | 0 / 2 | 0% | `░░░░░░░░░░` |
| Phase 5 | 0 / 6 | 0% | `░░░░░░░░░░` |
| Phase 6 | 0 / 10 | 0% | `░░░░░░░░░░` |

## Phase breakdown — features & tasks

### Phase 1 — 3/7 · 43% `████░░░░░░`

| PR | Feature | Status | Branch |
|----|---------|:------:|--------|
| `W0.7` | Public `request_id` helpers + F02 xfail contract pin | ✅ Merged | `chore/W0.7-tenant-context-public-api` |
| `W0.8` | Webhook `display_suffix VARCHAR(8)` migration (G3 option b) | ✅ Merged | `feat/webhook-display-suffix-migration` |
| `W0.9` | Dashboard realtime — auto-rebuild + git-state detect + reconcile | ✅ Merged | `feat/dashboard-realtime` |
| `W0.10` | Dashboard v3 rich UI + FastAPI serve | 🟡 In review | `feat/dashboard-v3-rich` |
| `W1.1` | Docker Compose dev + prod | ⬜ Not started | `infra/W1.1-docker-compose` |
| `W1.2` | Discord adapter (`core/messenger/discord.py`) | ⬜ Not started | `feat/W1.2-discord-adapter` |
| `W1.3` | Phase 1 integration smoke | ⬜ Not started | `chore/W1.3-phase1-smoke` |

### Phase 2 — 1/9 · 11% `█░░░░░░░░░`

| PR | Feature | Status | Branch |
|----|---------|:------:|--------|
| `F-onboarding` | F01 — `/start` + user create + trial assign | ⬜ Not started | `feat/F01-onboarding-start` |
| `F08` | Funding sources resolver + handlers | ⬜ Not started | `feat/F08-funding-sources` |
| `F02` | Transaction capture EXPANDED (inherit W0.6 legacy cutover) | ⬜ Not started | `feat/F02-tx-capture-cutover` |
| `F04` | Category management (`/manage`) | ⬜ Not started | `feat/F04-category-mgmt` |
| `F03` | Categorization auto-rules + manual | ⬜ Not started | `feat/F03-categorization` |
| `F05` | Reports `/status`, `/today`, `/weekly` | ⬜ Not started | `feat/F05-reports` |
| `F07` | Settings `/settings` | ✅ Merged | `feat/F07-settings` |
| `F11a` | F11 — Admin auth framework only (commands defer Phase 6) | ⬜ Not started | `feat/F11a-admin-auth` |
| `F-i18n` | VI/EN locale switcher | ❌ Blocked | `feat/F-i18n` |

### Phase 3 — 0/1 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Branch |
|----|---------|:------:|--------|
| `F06` | Tier limits + 14d trial + gating middleware | ⬜ Not started | `feat/F06-pricing-tiers` |

### Phase 4 — 0/2 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Branch |
|----|---------|:------:|--------|
| `F01b` | Path A (Quick connect) + Path B (Wizard) | ⬜ Not started | `feat/F01b-sepay-paths` |
| `F01c` | First-tx celebration flow | ⬜ Not started | `feat/F01c-first-tx-flow` |

### Phase 5 — 0/6 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Branch |
|----|---------|:------:|--------|
| `W5.1` | Postmark inbound + `/inbound/{token}` route | ⬜ Not started | `infra/W5.1-postmark-inbound` |
| `F01d` | Path C onboarding (email forwarding guides) | ⬜ Not started | `feat/F01d-email-forwarding` |
| `P-TCB` | Parser: Techcombank full extraction | ⬜ Not started | `feat/parser-tcb` |
| `P-Cake` | Parser: Cake (VPBank) | ⬜ Not started | `feat/parser-cake` |
| `P-MB` | Parser: MB Bank | ⬜ Not started | `feat/parser-mb` |
| `P-ACB` | Parser: ACB (deferred to Phase 5b) | ⏸️ Deferred | `feat/parser-acb` |
| `P-STB` | Parser: Sacombank (deferred to Phase 5b) | ⏸️ Deferred | `feat/parser-stb` |
| `P-BIDV` | Parser: BIDV (deferred to Phase 5b) | ⏸️ Deferred | `feat/parser-bidv` |
| `F02-dedup` | Cross-source dedup (SePay + Email) | ⬜ Not started | `feat/F02-dedup` |

### Phase 6 — 0/10 · 0% `░░░░░░░░░░`

| PR | Feature | Status | Branch |
|----|---------|:------:|--------|
| `F09` | Scheduled jobs (APScheduler, TZ jitter ±5min) | ⬜ Not started | `feat/F09-scheduled-jobs` |
| `F10a` | F10 — Payment VietQR + SePay auto-detect (4-layer fuzzy) | ⬜ Not started | `feat/F10a-payment-vietqr-sepay` |
| `F10b` | F10 — Email backup detect (TCB email path) | ⬜ Not started | `feat/F10b-payment-email-backup` |
| `F10c` | F10 — Manual review fallback + recurring billing | ⬜ Not started | `feat/F10c-payment-recurring` |
| `F11b` | F11 — Admin commands (`/admin_stats`, `/admin_cost`, `/admin_user`, `/admin_resolve`) | ⬜ Not started | `feat/F11b-admin-commands` |
| `W6.1` | Sentry alerts — 7 critical (per observability-plan.md) | ⬜ Not started | `infra/W6.1-sentry-alerts` |
| `F13` | Messenger adapter (feature-flagged `ENABLE_MESSENGER_CHANNEL=false`) | ⬜ Not started | `feat/F13-messenger-channel` |
| `W6.2` | Railway deploy + custom domain (tienvenoidau.com) | ⬜ Not started | `infra/W6.2-railway-deploy` |
| `W6.3` | Backup automation (B2 + pg_dump daily, SSE-B2) | ⬜ Not started | `infra/W6.3-backup-b2` |
| `W6.4` | DR runbook full validation (test restore) | ⬜ Not started | `chore/W6.4-dr-restore-test` |
| `(to be created when Phase W enters implementation planning)` | — | ⏸️ Deferred | `—` |

## Timeline

```mermaid
gantt
    title MyMoneyWent roadmap
    dateFormat YYYY-MM-DD
    axisFormat %b
    section Phase 1
    P1 (43%) : active, 2026-05-05, 2026-05-22
    section Phase 2
    P2 (11%) : active, 2026-05-22, 2026-06-15
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

### W0.10 — Dashboard v3 rich UI + FastAPI serve

- **Status:** 🟡 In review
- **Branch:** `feat/dashboard-v3-rich`
- **Wave:** Wave 0 follow-up
- **Gates:** 🔒X
- **Phase:** Phase 1
- **Notes:** **STALE — base = `1ec2f4f` (trước F07 merge)**. 2 dashboard commits trên top of autopilot v0.2.2 stack (16 total commits ahead): `4e59b64` (Chart.js MVP trajectory, filter buttons, search, click-through, animations) + `c5721be` (FastAPI `/dashboard` + `/dashboard.md` cho Railway, 30s cache). Dashboard portion chưa Codex-reviewed (14 fix() commits dưới là từ autopilot v0.2.2 internal rounds, đã shipped riêng → reconcile_status heuristic false-positive thành 🟠 trong dashboard view). `git diff main..feat/dashboard-v3-rich` show ~6000 lines deletion vì branch chưa rebase qua F07 → **merge thẳng = mất F07 + autopilot v0.2.2/v0.2.3**. Next move: cherry-pick 2 commits sang branch mới từ main, resolve conflict ở `scripts/build-dashboard.py` (overlap với W0.9 detect_git_state), verify, Codex 1× → ready merge.

### F-i18n — VI/EN locale switcher

- **Status:** ❌ Blocked
- **Branch:** `feat/F-i18n`
- **Wave:** Wave 1
- **Gates:** 🔒X
- **Phase:** Phase 2
- **Notes:** Stub đã land W0.4; expand to all user-facing strings

## Up next

| PR | Feature | Phase | Status |
|----|---------|-------|--------|
| `W1.1` | Docker Compose dev + prod | Phase 1 | ⬜ Not started |
| `W1.2` | Discord adapter (`core/messenger/discord.py`) | Phase 1 | ⬜ Not started |
| `W1.3` | Phase 1 integration smoke | Phase 1 | ⬜ Not started |
| `F-onboarding` | F01 — `/start` + user create + trial assign | Phase 2 | ⬜ Not started |
| `F08` | F08 — Funding sources resolver + handlers | Phase 2 | ⬜ Not started |

---

**Rebuild:** chạy `python scripts/build-dashboard.py` sau mỗi PR merge (theo Step 10 của [development-workflow.md](operations/development-workflow.md) §2.7 Post-merge updates).
