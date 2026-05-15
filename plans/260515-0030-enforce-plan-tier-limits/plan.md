---
title: "Enforce plan-tier limits (H1 fix)"
description: "Atomic capture-time enforcement of monthly tx + bank caps per Free/Pro/Business tiers; closes second launch blocker."
status: pending
priority: P1
effort: 8h
branch: feat/c1-p5-retire-legacy
tags: [security, multi-tenant, billing, race-conditions, h1]
created: 2026-05-15
---

# Enforce plan-tier limits — H1 launch blocker

## Why this exists

Spec defines 3 tiers (Free 45 tx/mo + 1 bank, Pro 99k VND + 3 banks, Business 299k VND + 5 banks; per `docs/features/feature-pricing-tiers.md`, post-2026-05-11 pricing bump). **ZERO enforcement code exists.** Naive `count(*) ... ; insert` is TOCTOU: 10 concurrent webhook deliveries at 44/45 all read 44, all insert → 54. Hot insert path is `markets/vn/capture/sepay_webhook.py::_persist` (post-C1).

`users.plan` column already exists (CHECK `IN ('free','pro','business')`, default `'free'`) and `plan_expires_at TIMESTAMPTZ` exists — schema groundwork done.

## Scope

In: monthly tx cap, distinct bank cap, downgrade-safety freeze, i18n strings, race-test.
Out: billing flow (Stripe/PayOS), Family tier (4-tier expansion is separate per spec v1.1.0).

## Phases

| # | File | Status | Effort | Blockers |
|---|------|--------|--------|----------|
| 1 | [phase-01-schema-plan-caps-table.md](phase-01-schema-plan-caps-table.md) | pending | 1.5h | — |
| 2 | [phase-02-atomic-tx-cap-enforcement.md](phase-02-atomic-tx-cap-enforcement.md) | pending | 2h | P1 + D1 resolved |
| 3 | [phase-03-bank-cap-enforcement.md](phase-03-bank-cap-enforcement.md) | pending | 1h | P1 + D2 resolved |
| 4 | [phase-04-plan-downgrade-safety.md](phase-04-plan-downgrade-safety.md) | pending | 1h | P2, P3 |
| 5 | [phase-05-i18n-limit-strings.md](phase-05-i18n-limit-strings.md) | pending | 0.5h | D1 |
| 6 | [phase-06-integration-and-race-tests.md](phase-06-integration-and-race-tests.md) | pending | 2h | P2, P3, P4 |

Total ~8h. Phases 1 & 5 can run parallel to 2; 3 runs after 1; 6 last.

## Key files (touched across phases)

- `markets/vn/capture/sepay_webhook.py` — `_persist` hot path (Phase 2)
- `migrations/versions/0004_plan_caps_and_quota.py` NEW (Phase 1)
- `core/services/plan_limits_svc.py` NEW — single source of truth for caps + enforcement helpers (Phase 2)
- `core/services/funding_sources_svc.py` NEW or existing — bank-cap gate (Phase 3)
- `core/services/user_svc.py` — downgrade hook (Phase 4)
- `i18n/vi.py`, `i18n/en.py` — limit strings (Phase 5)
- `tests/markets/vn/test_sepay_webhook_caps.py` NEW (Phase 6)

## Test matrix

- Unit: cap lookup, downgrade safety predicate.
- Integration: webhook → insert hits cap → 200 + skip + analytics row.
- Race: 20 concurrent inserts at cap-1 → exactly cap rows (`asyncio.gather`).
- Rollback: migration `downgrade()` drops `monthly_tx_count` materialized view / column.

## Rollback strategy

Each phase ships behind feature flag `ENFORCE_PLAN_LIMITS` (env var, default `false` for Phase 1; flip to `true` after Phase 2 deploys clean for 24h). Reverting = flip flag off; schema additions are non-destructive (new columns nullable, new table additive).

## Success criteria (measurable)

1. 20-concurrent-insert race test → DB row count == cap, exactly.
2. Free user POST after cap → 200 OK, `over_quota_attempts` analytics row, no `transactions` row inserted (assuming D1=hard-reject).
3. Bank cap: Free user attempting 2nd `funding_sources` row → rejected with `TIER_BANK_LIMIT` error.
4. Downgrade Pro→Free with 3 banks active → existing rows preserved, status flag visible, new tx beyond Free cap blocked.
5. `pip-audit` + existing test suite still green.

## Unresolved questions (decide before Phase 2 starts)

**D1. Overage behavior — Free user hits 46th tx.**
- A. Hard-reject `_persist`, Telegram nudge "limit reached, upgrade?".
- B. Soft-allow with banner CTA on bot reply.
- C. Hybrid — insert with `over_quota=true` flag, history visible but reports clip at cap.
- Spec signal (`feature-pricing-tiers.md:48`): "Hard block 'Hết quota'" → suggests A. Tech-lead recommendation: **A** (protects unit economics, spec-aligned). C doubles complexity for a launch blocker.

**D2. Bank-count source-of-truth.**
- A. Distinct `accountNumber` from `transactions` (lazy, no setup friction).
- B. Explicit `funding_sources` rows per F08 (intentional, schema already exists with `UNIQUE(user_id, kind, bank, last4)`).
- Spec signal: F08 + `funding_sources` table already shipped per migration 0001. Recommendation: **B** — enforce at `funding_sources` insert. SePay webhook auto-creates `funding_sources` row on first sighting of a (bank,last4) pair, so user-facing onboarding friction is zero.

**D3. Plan source / downgrade trigger.**
- `users.plan` enum is canonical (already on row). `plan_expires_at` controls auto-revert. Question: who flips it? Cron job (`tools/cron/expire_plans.py` NEW)? Webhook from Stripe/PayOS (not in scope)?
- Recommendation: **add `tools/cron/expire_plans.py` skeleton with daily check** — wires the safety net without coupling to a specific payment provider. Actual payment integration plugs in later.

**D4. Grandfathering / migration.**
- No prod users yet (per C1 plan reviews). All existing rows → `plan='free'`.
- Retroactive count: only count rows from current `month_key = strftime('%Y-%m')` going forward. No backfill.

**D5. Enforcement layer.**
- Recommendation: **app-layer atomic CTE INSERT in `_persist`** (per review report:87-95) as primary. **DB-level CHECK trigger as defense-in-depth** in Phase 4.

These 5 should be resolved by founder before Phase 2 begins; Phases 1/5 are decision-independent.
