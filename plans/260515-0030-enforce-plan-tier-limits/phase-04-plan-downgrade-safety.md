# Phase 4 — Plan downgrade safety

## Context Links
- Spec: `docs/features/feature-pricing-tiers.md` §"Cross-Feature" line 61 ("Downgrade khi có > Free limits | Data preserved, new tx blocked").
- Phase 1 added `users.limits_frozen_at TIMESTAMPTZ`.
- D3 (plan source / downgrade trigger) — recommendation in plan.md: cron skeleton, payment webhook later.

## Priority
P2 — important but won't block launch if no paid users exist yet. Lands before paid plan announcement.

## Status
pending — depends on Phase 2 (uses same `try_insert_tx` chokepoint).

## Key Insights
- Two downgrade triggers: (a) `plan_expires_at < NOW()` (cron job auto-downgrade), (b) explicit user action `/cancel` (future). Both write `plan='free'` to `users` row.
- "Data preserved" means: existing transactions + funding_sources stay. New tx inserts beyond `free` cap are rejected.
- Edge case: user was Pro with 3 banks, downgrades to Free (cap=1). Now they have 3 active funding_sources but cap=1. Phase 3's `ensure_funding_source` already handles this (existing row matches → not blocked; cap enforced only on NEW banks). So existing banks keep ingesting. The user must manually `/banks/pause` two to comply.
- Edge case 2: user was Pro with 200 tx in May, downgrades May 20. Spec says new tx blocked once over Free's 45/mo. By the time downgrade hits, user already has 200 rows in May → every new May tx is rejected (200 > 45). Correct, but user-hostile if not messaged. Set `limits_frozen_at=NOW()` and on every block, surface "Your plan downgraded May 20; this month's tx are at 200/45 — upgrade to resume."
- Tech-lead call: enforcement code is already in Phase 2's `try_insert_tx` — it reads current `users.plan` per insert. **No new enforcement logic.** This phase only adds: (a) downgrade trigger script, (b) `limits_frozen_at` stamping, (c) clearer Telegram messaging on the cap-block path.

## Requirements
**Functional**
- `tools/cron/expire_plans.py` — script run hourly (Railway cron or GH Actions). SELECT users WHERE `plan != 'free' AND plan_expires_at < NOW()`. For each: `UPDATE users SET plan='free', limits_frozen_at=NOW() WHERE id=$1`. Emit analytics `plan_downgraded`.
- `try_insert_tx` (from Phase 2) — when block decision fires AND `limits_frozen_at IS NOT NULL`, use a different i18n key (`limit.tx_monthly_frozen` — explains downgrade context).
- `/settings` UI (existing handler) — show downgrade banner if `limits_frozen_at IS NOT NULL` within last 30 days.

**Non-functional**
- Cron idempotent: re-running same hour is a no-op.
- Stamping `limits_frozen_at` only once per downgrade event (clear on next upgrade).

## Architecture
```
┌──────────────────────────────────────────────────────────┐
│ tools/cron/expire_plans.py  (hourly)                     │
│   UPDATE users SET plan='free', limits_frozen_at=NOW()   │
│     WHERE plan != 'free' AND plan_expires_at < NOW()     │
│     AND limits_frozen_at IS NULL                         │
│   RETURNING id                                           │
│   → for each id: emit_analytics('plan_downgraded')       │
│                                                          │
│ Phase 2's try_insert_tx already enforces; this phase     │
│ just adds context to the user-facing message.            │
│                                                          │
│ On upgrade (future Stripe webhook):                      │
│   UPDATE users SET plan=$new, limits_frozen_at=NULL      │
└──────────────────────────────────────────────────────────┘
```

## Related Code Files
**Create**
- `tools/cron/expire_plans.py`
- `tools/cron/__init__.py` (if dir doesn't exist)

**Modify**
- `core/services/plan_limits_svc.py::notify_user_limit_hit` — branch i18n key on `limits_frozen_at`.
- `handlers/settings.py` (legacy — verify still in use post-C1) — add downgrade banner.
- `railway.toml` or GH Actions workflow — schedule hourly run.

## Implementation Steps
1. Write `tools/cron/expire_plans.py` as a standalone async script:
   ```python
   async def main():
       await db.create_pool(os.environ['DATABASE_URL'])
       pool = db.get_pool()
       async with pool.acquire() as conn:
           rows = await conn.fetch("""
               UPDATE users SET plan='free', limits_frozen_at=NOW()
               WHERE plan != 'free' AND plan_expires_at < NOW()
                 AND limits_frozen_at IS NULL
               RETURNING id, plan as old_plan
           """)
       for row in rows:
           await emit_analytics(...)
       log.info("expire_plans.done", count=len(rows))
   ```
2. Add Railway scheduled service OR GH Actions cron in `.github/workflows/expire-plans.yml`.
3. Modify `notify_user_limit_hit` to lookup `limits_frozen_at` and pick i18n key.
4. Add settings banner.
5. Unit test the SQL: insert user with past `plan_expires_at`, run script, assert `plan='free'` and `limits_frozen_at` stamped.
6. Commit: `feat(h1-p4): plan downgrade safety + expire-plans cron`.

## Todo List
- [ ] `expire_plans.py` written.
- [ ] Cron scheduled (Railway or GH Actions).
- [ ] `notify_user_limit_hit` branches on frozen-flag.
- [ ] Settings banner shows downgrade context.
- [ ] Unit test for the cron's UPDATE statement.
- [ ] Integration test: simulate Pro user with 200 tx, run cron, attempt 201st tx → blocked with frozen-context message.
- [ ] Commit + push.

## Success Criteria
- After cron: any user with `plan_expires_at < NOW()` is `plan='free'` and `limits_frozen_at IS NOT NULL`.
- Frozen Free user attempting 46th tx receives `limit.tx_monthly_frozen` message, not generic `limit.tx_monthly_hit`.
- Re-running cron same hour → 0 rows updated (idempotent via `AND limits_frozen_at IS NULL`).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cron misses a user (clock skew) | Low | Low | Run hourly; missed user enforced at next webhook anyway since `plan` is checked per insert. |
| Cron downgrades user mid-grace-period | Med | Med | Use `plan_expires_at` as the canonical end; grace period is set BY upgrade flow, not cron. |
| Family tier (future) not handled | High (when launched) | Low | Spec line 233 — Family adds `family_owner` plan. Update CAPS dict + cron query when Family ships. Out of scope here. |
| Stale `limits_frozen_at` after re-upgrade | Med | Low | Upgrade path (out of scope this phase) MUST `SET limits_frozen_at=NULL`. Document in `feature-payment.md` integration note. |

## Security Considerations
- Cron runs with full DB access. Restrict to Railway service / GH Actions runner; never expose as HTTP endpoint.
- Idempotency guard (`AND limits_frozen_at IS NULL`) prevents stamp-overwriting on re-runs.

## Rollback
Drop cron schedule; users stay on stale plan. Phase 2 still enforces correctly per current `users.plan` value.

## Next Steps
Phase 5 (i18n strings) — needs new keys for frozen / hit messages.
Phase 6 (tests).
