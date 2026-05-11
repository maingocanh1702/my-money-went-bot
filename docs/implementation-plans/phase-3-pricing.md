# Phase 3: Pricing Logic — 1 PR

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Ship F06 — tier limits, 14d Pro trial, upgrade triggers, gating middleware.
> **Tham chiếu:**
> - [Implementation Tracker](../implementation-tracker.md)
> - [Feature Spec F06](../features/feature-pricing-tiers.md)
> - [BE Tech F06](../features/BE/feature-pricing-tiers-tech.md)
> - [Roadmap §Phase 3](../mymoneywent-roadmap.md)

---

## Overview

| PR | Scope | Tests | Est. days |
|----|-------|:-----:|:---------:|
| F06 | Tier limits + trial + gating middleware | 22 | 2.5 |

---

## F06 — Pricing tiers

### Scope

**Tier definitions (Free/Pro):**
- Free: 45 tx/month, 1 bank, 30d history, 5 categories
- Pro: unlimited tx, 3 banks, full history, unlimited categories, multi-channel
- Business: defer to Phase 9-10 (out of MVP)
- Family: defer to Phase 11

**14-day Pro trial:**
- Auto-assigned at `/start` (already in F-onboarding)
- This PR: trial expiry sweep + auto-downgrade to Free
- Grace: keep Pro features readable, block writes that exceed Free limits

**Upgrade triggers:**
- Hit Free limit (45 tx) → upgrade CTA
- Trial 3 days remaining → soft reminder
- Trial expired → hard prompt
- Max 1 upgrade prompt per user per week (anti-spam)

**Gating middleware:**
- Decorator `@tier_required(min_tier)` for handlers
- Service-level: `check_tier_limit(user_id, feature_key)` before writes
- Feature flags per tier in `core/services/tier_limits.py`

### Files touched

```
+ core/services/tier_limits.py
+ core/services/pricing.py
+ core/handlers/pricing.py        (/upgrade, /trial commands)
+ migrations/versions/0002_pricing_metadata.py  (if needed: tx count cache table)
M core/handlers/transaction.py    (wire tier check before insert)
M core/handlers/manage.py         (wire tier check on cat create)
M core/handlers/funding.py        (wire tier check on funding add)
+ tests/unit/test_tier_limits.py
+ tests/integration/test_pricing_flow.py
+ tests/integration/test_trial_expiry.py
```

### Test plan (22)

**Tier limits — Free (8):**
1. New user hit 44 tx → no warning yet
2. 45th tx → block + upgrade CTA
3. 46th tx attempt → rejected silently (idempotent)
4. Add 6th category → block + CTA
5. Add 2nd bank → block + CTA
6. Query tx >30d → filtered (no leak)
7. Single-channel only (block 2nd channel link)
8. 1st of month: counter resets (rolling vs calendar — see decision)

**Pro trial (5):**
9. New user `/start` → trial 14d assigned (verify already in F-onboarding tests)
10. Day 11: 3-day reminder sent
11. Day 14 boundary: trial active until 23:59 user TZ
12. Day 15: auto-downgrade to Free, hard prompt sent
13. Re-upgrade post-trial: keep historical data accessible (Pro readable, Free-limit writes)

**Upgrade triggers (4):**
14. Hit 45 tx → CTA sent
15. Hit cat limit → CTA sent
16. Same user 2 CTAs in 1 week → 2nd suppressed
17. Different reasons → still suppressed per global rate limit

**Gating middleware (3):**
18. `@tier_required('pro')` blocks Free user
19. `check_tier_limit` returns correct remaining count
20. Decorator + service check both pass → action proceeds

**Isolation (2):**
21. User A Pro limits do not leak to User B
22. Founder bypass (role=founder) — unlimited

### Acceptance criteria

- Free user hits 45 tx → blocked with `/upgrade` CTA, friendly message
- Trial countdown visible via `/trial` command
- Trial expiry sweep job runs daily (via F09 scheduler — coordinate)
- Anti-spam: max 1 upgrade prompt/week verified via test
- No tenant leak

### Decision lockdown

- [ ] **Tx counter window:** Rolling 30d vs calendar month? → **Calendar month** (simpler, aligns with billing). Reset at 1st 00:00 user TZ.
- [ ] **Trial expiry sweep:** Hourly cron or on-access lazy? → **Both**: hourly sweep + on-access check for accuracy at boundary.
- [ ] **Grace post-trial:** Reads OK, writes Free-limited. NO hard lockout.
- [ ] **Pro pricing display:** Reference F06 vNext addendum (Pro 99k locked 2026-05-11) — even if doc merge pending, code uses 99k constant
- [ ] **Founder bypass:** role=founder → all limits unlimited, no CTAs ever

### Risk

- **Trial expiry timing:** TZ boundary edge case can grant/revoke trial 1 day off. Mitigation: timezone-aware comparison, test DST switch.
- **Counter accuracy:** If tx counter cached, drift possible. MVP: compute live from `transactions` table (no cache). Cache deferred Phase 6+ if perf issue.
- **F06 addendum doc:** Code references 99k constant — if doc merge pending after this PR ships, no functional impact; only inconsistency between doc and code (resolved by doc merge). NOT a blocker for this PR.

### Coordination with other phases

- **F09 (Phase 6):** Trial expiry sweep job — F09 implements scheduler; F06 provides the sweep function. F09 wires it in.
- **F10 (Phase 6):** Payment flow — F10 transitions Free→Pro upon payment match. F06 provides `upgrade_user(user_id, tier, expires_at)`.
- **F08:** Funding sources limit (1 bank Free, 3 Pro) — F06 enforces via `tier_limits.py`.

---

## Phase 3 exit checklist (gate → Phase 4)

- [ ] F06 merged
- [ ] All 22 tests pass
- [ ] Free → Pro CTA flow demo with founder account
- [ ] Trial countdown visible
- [ ] Founder bypass verified
- [ ] CHANGELOG entry
- [ ] Roadmap Phase 3 → 100%
- [ ] Tracker progress summary updated

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial plan. 1 PR (F06). ~2.5 days est. Trial expiry coordination with F09 (Phase 6) flagged. Pricing constants reference F06 vNext addendum (Pro 99k). |
