# Phase 3: Pricing Logic — Task List

> **Status:** ⬜ Not Started
> **Tuần:** 5
> **Depends on:** Phase 2 ✅ (handlers must exist to gate)
> **Roadmap:** [mymoneywent-roadmap.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/mymoneywent-roadmap.md)

---

## Tasks

- [ ] **T3.01** Tier gating middleware
  - Spec: [feature-pricing-tiers.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md) + [BE tech](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-pricing-tiers-tech.md)
  - AC:
    - [ ] `get_user_tier(user_id)` → `free | pro | family | business`
    - [ ] Derive from `users.plan`, `users.trial_ends_at`, `users.plan_expires_at`
    - [ ] Middleware checks tier before feature-gated commands
  - Tests: ≥5
  - Estimate: 0.5 ngày

- [ ] **T3.02** Free tier limits enforcement
  - AC:
    - [ ] 45 tx/tháng → reject + upgrade prompt
    - [ ] 1 bank account (SePay webhook)
    - [ ] 30 ngày transaction history
    - [ ] 5 categories total
    - [ ] 1 email source
    - [ ] System default auto-cat rules only
  - Tests: ≥8 (one per limit + edge cases)
  - Estimate: 1 ngày

- [ ] **T3.03** 14-day Pro trial logic
  - AC:
    - [ ] New user → `trial_ends_at = now + 14d`, `plan = 'pro'`
    - [ ] Day 12 → reminder message
    - [ ] Day 14 → auto-downgrade to Free, data preserved
    - [ ] Downgrade idempotent (runs in scheduled job)
    - [ ] Pro→Family → trial reset 14d (1 lần, track `family_trial_used_at`)
  - Tests: ≥5
  - Estimate: 1 ngày

- [ ] **T3.04** Upgrade trigger service
  - AC:
    - [ ] Max 1 upgrade message/tuần/user
    - [ ] Trigger on: 35/45 tx hit, Day 12 trial, 30d history limit, 2nd bank attempt
    - [ ] `analytics_events` INSERT per trigger
    - [ ] Upgrade message via `SendPayload` with upgrade button
  - Tests: ≥4
  - Estimate: 0.5 ngày

- [ ] **T3.05** `/upgrade` command skeleton
  - AC:
    - [ ] Show current plan + available plans + pricing
    - [ ] Plan selection buttons
    - [ ] Hands off to payment flow (Phase 6) — stub for now
  - Tests: ≥3
  - Estimate: 0.5 ngày

---

## Phase 3 Definition of Done

- [ ] All 5 tasks ✅
- [ ] Free user hitting limit → receives upgrade prompt
- [ ] Trial auto-downgrade works (test with mocked time)
- [ ] Tier check on all gated commands (`/weekly`, `/report`, `/export`)
- [ ] `pytest -v` ≥ 230 tests passing
