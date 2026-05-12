# Phase 6: Polish + Deploy — Task List

> **Status:** ⬜ Not Started
> **Tuần:** 10-12
> **Depends on:** Phase 3 (pricing), Phase 4 (SePay), Phase 5 (email)

---

## Tasks

### Scheduled Jobs (F09)
- [ ] **T6.01** APScheduler setup — per-user timezone, `scheduled_jobs` table polling
- [ ] **T6.02** Daily recap job — 23:00 user TZ ±5min jitter, fire if ≥1 tx today
- [ ] **T6.03** Trial reminder — Day 12
- [ ] **T6.04** Trial downgrade — Day 14 auto-Free
- [ ] **T6.05** Weekly report job — Sunday 14:00 (Pro+)
- [ ] **T6.06** Monthly report + allocation job

### Payment (F10)
- [ ] **T6.07** `/upgrade` full flow — plan selection → VietQR generation (2 QR: VCB + TCB)
- [ ] **T6.08** Payment auto-detect via SePay — 4-layer fuzzy matching
- [ ] **T6.09** Payment auto-detect via email backup — TCB email → match
- [ ] **T6.10** Payment state machine — pending → matched → confirmed → active
- [ ] **T6.11** Manual review fallback — `/admin_resolve` link unmatched → pending
- [ ] **T6.12** Recurring billing — monthly 3d reminder + 7d grace + annual 14+3+1d
- [ ] **T6.13** Refund flow — `/admin_refund` 7d money-back

### Admin Tools (F11)
- [ ] **T6.14** `/admin_stats` — DAU, MAU, revenue, conversion
- [ ] **T6.15** `/admin_cost` — Railway + Postmark + B2 cost vs MRR
- [ ] **T6.16** `/admin_user <id>` — troubleshooter per user
- [ ] **T6.17** `/admin_help` — auto-generated from `@admin_only` registry
- [ ] **T6.18** `/admin_force_plan` — manual plan override
- [ ] **T6.19** `/admin_pause_user` — abuse mitigation

### Messenger (F13)
- [ ] **T6.20** Messenger adapter — `core/messenger/messenger.py` + `@register_sender("messenger")`
- [ ] **T6.21** Feature flag — `ENABLE_MESSENGER_CHANNEL` gate
- [ ] **T6.22** Meta webhook verification — GET challenge + POST message handling

### Deploy
- [ ] **T6.23** Railway production deploy — `tienvenoidau.com` domain + SSL
- [ ] **T6.24** Backup automation — daily `pg_dump` + `pg_dumpall --globals-only` → B2 SSE-B2
- [ ] **T6.25** Sentry production DSN + 7 critical alerts armed
- [ ] **T6.26** DR runbook validation — test full restore to staging
- [ ] **T6.27** Hộ kinh doanh registration confirmation ✓

## Definition of Done

- [ ] All 27 tasks ✅
- [ ] Payment E2E: `/upgrade` → QR → transfer → auto-detect → plan active
- [ ] Admin commands all functional
- [ ] Backup + restore tested
- [ ] `pytest` ≥ 400 tests
