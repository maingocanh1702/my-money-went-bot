# Phase 1 — Schema: plan caps + month-quota counter

## Context Links
- Report: `plans/reports/code-review-260514-full-codebase-deep.md` §H1 (lines 82-96).
- Spec: `docs/features/feature-pricing-tiers.md` §"Tier Limits Matrix" (line 120), §"Use cases" (lines 47-48).
- Existing schema: `migrations/versions/0001_initial_schema.py` (users.plan, users.plan_expires_at, funding_sources).
- C1 plan (in-flight, must land first): `plans/260514-2049-wire-multi-tenant-sepay-pipeline/`.

## Priority
P1 — launch blocker (revenue leakage). Decision-independent; can start before D1/D2/D3 resolved.

## Status
pending

## Key Insights
- `users.plan` column + CHECK constraint already exists. No need to recreate.
- Caps are SMALL constants (3 tiers × 2 caps) — KISS says hardcoded module > config table. BUT spec describes Family tier coming (`v1.1.0` 2026-05-11), so a `plan_caps` table is future-proof for ~30 LOC cost.
- Tech-lead call: **hardcode as Python module `core/services/plan_limits_svc.py::CAPS`**. YAGNI on the table — Family tier is separate work that will add its own migration anyway. Saves a join in the hot path.
- We DO need a fast `count(*)` proxy for the atomic CTE. Two options:
  1. Compute inline `(SELECT COUNT(*) FROM transactions WHERE user_id=$1 AND month_key=$2 AND direction='in')` — needs index `idx_tx_user_monthkey` (already exists per 0001).
  2. Materialised counter column on `users` updated by trigger.
- Recommendation: **option 1** — index already exists, COUNT on indexed subset of ~45 rows is <1ms, zero migration risk. Trigger adds a bug surface.

## Requirements
**Functional**
- Add column `transactions.over_quota BOOLEAN NOT NULL DEFAULT false` (used by D1=C if chosen, harmless if D1=A).
- Add column `users.limits_frozen_at TIMESTAMPTZ NULL` (set when downgrade leaves user over caps, drives Phase 4 freeze logic).
- Add CHECK index for fast monthly tx-count lookup: `CREATE INDEX IF NOT EXISTS idx_tx_user_month_in ON transactions(user_id, month_key) WHERE direction='in';` (only `in` direction counts toward Free 45/mo per spec).
- Verify existing `users.plan`, `users.plan_expires_at`, `funding_sources` schema; no changes needed.

**Non-functional**
- Migration must be reversible.
- Zero downtime: all additions are nullable / default-valued; no rewrite.
- Run time on 0-row prod DB: <1s.

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: schema only — no behavior change                   │
│                                                             │
│ migrations/versions/0004_plan_caps_and_quota.py             │
│   upgrade():                                                │
│     ALTER TABLE transactions ADD COLUMN over_quota ...      │
│     ALTER TABLE users ADD COLUMN limits_frozen_at ...       │
│     CREATE INDEX idx_tx_user_month_in (partial)             │
│   downgrade():                                              │
│     DROP INDEX; DROP COLUMNs                                │
└─────────────────────────────────────────────────────────────┘
```

## Related Code Files
**Create**
- `migrations/versions/0004_plan_caps_and_quota.py`

**Modify** — none yet (Phase 2 adds the service).

**Delete** — none.

## Implementation Steps
1. Read `migrations/versions/0003_backfill_inbound_email.py` to match alembic file/style/down_revision convention.
2. Create `0004_plan_caps_and_quota.py` with `down_revision = '0003'` (or whatever 0003's revision id is — read it).
3. `upgrade()`:
   ```python
   op.execute("ALTER TABLE transactions ADD COLUMN over_quota BOOLEAN NOT NULL DEFAULT false;")
   op.execute("ALTER TABLE users ADD COLUMN limits_frozen_at TIMESTAMPTZ;")
   op.execute("""
       CREATE INDEX IF NOT EXISTS idx_tx_user_month_in
       ON transactions(user_id, month_key) WHERE direction='in';
   """)
   ```
4. `downgrade()`: drop in reverse order.
5. Run `alembic upgrade head` locally against a scratch DB; verify with `\d transactions`.
6. Run `alembic downgrade -1` then `alembic upgrade head` to confirm reversibility.
7. Commit: `feat(h1-p1): schema for plan caps + monthly tx quota index`.

## Todo List
- [ ] Read 0003 migration to match style + chain revision id.
- [ ] Write `0004_plan_caps_and_quota.py`.
- [ ] Local `alembic upgrade head` succeeds.
- [ ] Local `alembic downgrade -1 && alembic upgrade head` round-trips.
- [ ] `EXPLAIN ANALYZE SELECT COUNT(*) FROM transactions WHERE user_id=1 AND month_key='2026-05' AND direction='in';` shows Index Scan on new partial index.
- [ ] Commit + push to feature branch.

## Success Criteria
- Both new columns visible in `\d` output with expected defaults.
- Partial index used by EXPLAIN.
- Migration round-trips cleanly (up → down → up).
- Existing tests still pass (`pytest -q`).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Partial index conflicts with existing `idx_tx_user_monthkey` | Low | Low | `IF NOT EXISTS` guard; index name distinct (`_in` suffix). |
| `ALTER TABLE ... ADD COLUMN ... DEFAULT false` rewrites table on PG <11 | Very low | Med | Prod is PG 15+ (Railway default); fast-path metadata-only since PG 11. |
| Migration runs while writes in flight | Low | Low | `ALTER ADD COLUMN` takes only ACCESS EXCLUSIVE for ms in PG 11+; webhook can retry. |

## Security Considerations
None — additive schema only. `over_quota` is not user-supplied; only set by `_persist` in Phase 2.

## Rollback
`alembic downgrade -1`. Safe because no code reads these columns until Phase 2.

## Next Steps
Phase 2 (atomic enforcement in `_persist`). Phase 5 (i18n) can start in parallel.
