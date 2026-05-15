# Phase 2 — Atomic monthly-tx cap enforcement at `_persist`

## Context Links
- Report: `plans/reports/code-review-260514-full-codebase-deep.md` §H1 lines 87-95 (CTE INSERT pattern).
- Hot path: `markets/vn/capture/sepay_webhook.py:97-141`.
- Spec: `docs/features/feature-pricing-tiers.md:120` (Free=45, Pro/Biz=unlimited).
- Phase 1 must be merged + migrated.
- Plan.md §"Unresolved questions" D1, D5.

## Priority
P1 — launch blocker. The whole H1 fix lives or dies here.

## Status
pending — **BLOCKED on D1 (overage behavior) decision**.

## Key Insights
- TOCTOU is the whole problem. SELECT-then-INSERT in two statements = race even inside one txn at default READ COMMITTED. Must be single-statement.
- Pattern: `INSERT ... SELECT FROM dual WHERE (SELECT count < cap)` is the canonical fix. PG locks the index page during INSERT so concurrent inserters serialize at the row insertion step; the WHERE clause re-evaluates the COUNT under lock semantics.
- Subtle: COUNT inside SELECT isn't itself locked, BUT the UNIQUE constraint on `(user_id, ref_code)` already serializes per-ref-code retries. The race is two DIFFERENT events arriving — those don't share ref_code so UNIQUE doesn't help. **Need SERIALIZABLE isolation OR advisory lock OR conditional INSERT with row count.**
- Tech-lead call: use `pg_advisory_xact_lock(hashtext('plan_tx_cap:' || user_id || ':' || month_key))` to serialize on (user, month_key) pair. Lock auto-released at txn end. ~5µs overhead. Then a simple COUNT + conditional INSERT in same txn is race-free.
- For unlimited tiers (Pro/Business), short-circuit: skip lock+count entirely.

## Requirements
**Functional**
- Plan tier `free` → cap monthly `direction='in'` tx count at 45 (cap from `CAPS["free"]["monthly_tx"]`).
- Plan tier `pro` / `business` → no cap (skip enforcement entirely).
- Only count `direction='in'` (per spec; outgoing transfers don't count).
- Behavior at cap (D1 — assume A=hard-reject pending decision):
  - INSERT skipped.
  - Telegram bot DM sent: `i18n.t('limit.tx_monthly_hit', cap=45)` with upgrade CTA (uses string from Phase 5).
  - Analytics event `tier_limit_hit` (per spec line 164) — write to `analytics_events` via existing `core/settings_svc.emit_analytics` helper.
  - Return `{"ok": True}` to SePay (don't trigger retries).
- Behavior at cap (D1=C variant): INSERT with `over_quota=true`, reports/exports filter `WHERE NOT over_quota`. Phase 6 tests both branches.
- Feature flag `ENFORCE_PLAN_LIMITS` (env var, default `false`); when false, skip enforcement entirely (defense for canary rollout).

**Non-functional**
- p99 latency increase < 5ms (advisory lock + COUNT on ≤45 indexed rows).
- Zero false positives: the same legitimate retry of one event must NOT count twice (ON CONFLICT DO NOTHING already handles this — verify ref_code dedupe runs before count check OR count check is idempotent under retry).
- Sentry breadcrumb on every block decision; never silently drop.

## Architecture
```
handle_sepay_webhook(token, payload)
  ├─ resolve_token → user_id
  ├─ tenant_context.set_tenant(user_id)
  ├─ _to_canonical(payload) → tx
  └─ _persist(user_id, tx, month_key)
       ├─ build ref_code (existing logic)
       └─ if ENFORCE_PLAN_LIMITS:
            plan_limits_svc.try_insert_tx(conn, user_id, tx, month_key, ref_code)
              ├─ async with conn.transaction():
              │    plan = SELECT plan FROM users WHERE id=$1
              │    if plan in ('pro','business'):  # unlimited
              │       INSERT ... ON CONFLICT DO NOTHING RETURNING id
              │       return InsertResult(inserted=bool, reason=None)
              │    # free tier
              │    SELECT pg_advisory_xact_lock(hashtext('cap:' || $1 || ':' || $2))
              │    count = SELECT COUNT(*) FROM tx WHERE user_id=$1 AND month_key=$2
              │                                       AND direction='in'
              │    if count >= 45:
              │       emit_analytics('tier_limit_hit', limit_type='tx_monthly')
              │       return InsertResult(inserted=False, reason='tx_cap')
              │    INSERT ... ON CONFLICT DO NOTHING RETURNING id
              │    return InsertResult(inserted=bool, reason=None)
          else: (legacy raw insert — unchanged)
       └─ if not inserted and reason=='tx_cap':
            await notify_user_limit_hit(user_id, 'tx_monthly', cap=45)
```

Sequence under race (D1=A, 10 concurrent at 44/45):
1. All 10 webhook tasks enter `try_insert_tx`.
2. All 10 hit `pg_advisory_xact_lock` — PG serializes them.
3. First releases: count=44 → insert → row=45, lock released.
4. Second: count=45 → skip, analytics row, lock released.
5. … 3rd-10th identical to step 4. Total rows = 45 exactly.

## Related Code Files
**Create**
- `core/services/plan_limits_svc.py` (~120 LOC)
  - `CAPS = {"free": {"monthly_tx": 45, "banks": 1}, "pro": {..., "banks": 3}, "business": {..., "banks": 5}}`
  - `InsertResult` dataclass.
  - `async def try_insert_tx(conn, user_id, tx, month_key, ref_code) -> InsertResult`
  - `async def notify_user_limit_hit(user_id, limit_type, **ctx)` — sends Telegram DM via existing `telegram_api`.

**Modify**
- `markets/vn/capture/sepay_webhook.py::_persist` — wrap existing INSERT in `try_insert_tx` when flag on. Keep behavior identical when flag off.
- `core/settings.py` (or wherever env vars live) — add `ENFORCE_PLAN_LIMITS: bool` default false.

**Delete** — none.

## Implementation Steps
1. Write `core/services/plan_limits_svc.py` with CAPS, `InsertResult`, `try_insert_tx`. Unit-tested in isolation.
2. Add `ENFORCE_PLAN_LIMITS` to env config; document in `.env.example`.
3. Edit `_persist` to branch on flag. Keep legacy path so flag-off behavior is byte-identical.
4. Add `notify_user_limit_hit` — uses `telegram_api.send_message(chat_id, ...)` after resolving chat_id from `users` row. Look up i18n key from Phase 5 (placeholder string if Phase 5 not done).
5. Local pytest: `test_plan_limits_svc.py` unit tests cover plan='pro' short-circuit, free under cap, free at cap.
6. Local integration: spin up TestClient, POST 46 webhooks → DB has 45 rows, 1 analytics row.
7. Race test (Phase 6 will own this, but smoke-test locally with `asyncio.gather(*[handle_sepay_webhook(...)]*20)`).
8. Commit: `feat(h1-p2): atomic plan-tier tx cap enforcement at _persist`.

## Todo List
- [ ] D1 resolved by founder (default to A=hard-reject if no answer in 24h).
- [ ] `plan_limits_svc.py` written + linted.
- [ ] `_persist` modified, flag-gated.
- [ ] Unit tests pass.
- [ ] Integration test (sequential 46 inserts) passes.
- [ ] Local smoke race test (20 gather) gives exactly 45 rows.
- [ ] Sentry breadcrumb visible in logs on block.
- [ ] Commit + push.

## Success Criteria
- 20 concurrent inserts at cap-1 → exactly 45 rows in DB.
- Pro user 1000 inserts → 1000 rows (no enforcement overhead).
- Free user 46th attempt → `ok:True`, no row, analytics_events has `tier_limit_hit`, bot DM sent (Telegram API mocked in tests).
- Flag off → behavior identical to pre-Phase-2 commit (verified by checksum / golden snapshot of `_persist` SQL).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Advisory lock hashes collide across users | Very low | Med | `hashtext` is 32-bit, collision prob ~10^-9 at 10k users. Use `(int8send(user_id) || month_key)::bytea` via `hashtextextended` (64-bit) if paranoid. |
| Long-running txn blocks other webhook | Low | Med | Lock duration = COUNT + INSERT = ~2ms. Set `statement_timeout=5s` on pool (already set per `core/db.py:create_pool`). |
| `emit_analytics` failure breaks the txn | Med | High | Wrap analytics in `try/except`, log to structlog, do NOT raise. Per M6 in report — but accept the swallow specifically for this call. |
| Bot DM fails (Telegram down) | Med | Low | Already async / fire-and-forget; failure does not roll back DB. |
| Flag accidentally on in test → flaky tests | Med | Low | Default `false`; pytest fixture sets explicitly. |

## Security Considerations
- The advisory lock key is `hashtext('cap:' || user_id || ':' || month_key)` — derived from server-side user_id (resolved from token), never client input. Safe.
- `try_insert_tx` always operates inside `tenant_context.set_tenant(user_id)` — all log lines tagged correctly.
- No new attack surface: enforcement is server-side post-token-resolve.

## Rollback
Set `ENFORCE_PLAN_LIMITS=false` and redeploy. Behavior reverts to current. No DB rollback needed (schema additions from Phase 1 are still in place but unused).

## Next Steps
Phase 3 (bank cap, similar pattern at `funding_sources` insert).
Phase 6 will pile race + load tests on top of this.
