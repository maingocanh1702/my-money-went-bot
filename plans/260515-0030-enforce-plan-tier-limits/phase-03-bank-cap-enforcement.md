# Phase 3 — Bank-cap enforcement at `funding_sources` insert

## Context Links
- Report: §H1 lines 82-96.
- Spec: `docs/features/feature-pricing-tiers.md:120` (Free=1, Pro=3, Biz=5 banks), §"TIER_BANK_LIMIT" line 148.
- Schema: `migrations/versions/0001_initial_schema.py:120-149` — `funding_sources` table with `UNIQUE(user_id, kind, bank, last4)`.
- Decision D2 (recommended: enforce on `funding_sources` row insert, not via transactions distinct-count).

## Priority
P1 — launch blocker.

## Status
pending — depends on D2 resolution + Phase 1 complete.

## Key Insights
- Bank cap is a small integer (1/3/5) — same advisory-lock + count + conditional-insert pattern as Phase 2.
- BUT `funding_sources` rows are auto-created from webhook side effects when SePay surfaces a new (bank,last4) pair. So enforcement must happen at the auto-create site too, not only at user-initiated `/banks/add`.
- Tech-lead call: enforcement lives in `core/services/funding_sources_svc.py::ensure_funding_source(user_id, bank, last4, kind)`. Both webhook auto-create AND `/settings` UI go through this single helper. **DRY enforced via single chokepoint.**
- Auto-create path: if user is Free + already has 1 funding_source + SePay webhook surfaces a 2nd bank → reject the funding_source insert, BUT keep the transaction insert (it links via the existing bank's `funding_source_id` set to NULL). Otherwise we'd silently drop legitimate income. User then sees Telegram nudge "new bank detected, upgrade to track".
- This decouples tx ingestion from bank cap — important because tx cap (Phase 2) blocks the tx itself, but bank cap should NOT block the tx, only the bank-tracking metadata.

## Requirements
**Functional**
- `funding_sources_svc.ensure_funding_source(user_id, bank, last4, kind, *, conn)` returns `(id, created: bool, blocked: bool)`.
- If user.plan='free' and existing count >= 1, and the (bank,last4) combo is new → `blocked=True`, no row inserted, analytics event `tier_limit_hit` with `limit_type='bank_count'`.
- If existing (bank,last4) row exists → returns existing id, `created=False, blocked=False`.
- Pro: cap=3, Biz: cap=5; same logic.
- Wire `_persist` in sepay_webhook to call `ensure_funding_source` BEFORE the INSERT; if `blocked`, proceed with tx INSERT using `funding_source_id=NULL`.

**Non-functional**
- Same race-safety: advisory lock keyed on `(user_id, 'bank_cap')` while counting + inserting.
- Notify user via Telegram only ONCE per limit-hit per month (avoid spam). Use `analytics_events` as the dedupe surface: query last 30d for same `tier_limit_hit/limit_type=bank_count/user_id` before sending.

## Architecture
```
_persist(...)
  ├─ if ENFORCE_PLAN_LIMITS:
  │    fs_id, _, fs_blocked = await ensure_funding_source(
  │        conn, user_id, tx.bank, tx.last4, kind='bank_account')
  │    if fs_blocked:
  │       await notify_user_limit_hit(user_id, 'bank_count', detected=f"{tx.bank}/{tx.last4}")
  │  else: fs_id = None
  ├─ tx_cap check (Phase 2)
  └─ INSERT INTO transactions (..., funding_source_id=$N, ...)
```

## Related Code Files
**Create / Modify**
- `core/services/funding_sources_svc.py` — NEW file with `ensure_funding_source` + count helper.
- `markets/vn/capture/sepay_webhook.py::_persist` — call `ensure_funding_source` first, thread `funding_source_id` into INSERT.
- `migrations/versions/0001_initial_schema.py:164` — already has `funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL` on transactions; no schema change needed.

## Implementation Steps
1. Write `funding_sources_svc.ensure_funding_source` with advisory lock on `hashtext('bank_cap:' || user_id)`.
2. Use `INSERT INTO funding_sources (...) ON CONFLICT (user_id, kind, bank, last4) DO UPDATE SET last_tx_at=NOW() RETURNING id, xmax = 0 AS inserted` — the `xmax=0` trick distinguishes insert from update.
3. Before the INSERT, run `SELECT COUNT(*) FROM funding_sources WHERE user_id=$1 AND status='active'` under the advisory lock; reject if count >= cap AND no existing row matches.
4. Modify `_persist` to call this helper, thread `funding_source_id`.
5. Add dedup-notify helper checking analytics_events for prior `tier_limit_hit` in last 30d.
6. Unit + integration tests (smoke; full coverage in Phase 6).
7. Commit: `feat(h1-p3): bank-cap enforcement at funding_sources insert`.

## Todo List
- [ ] D2 confirmed.
- [ ] `funding_sources_svc.py` written.
- [ ] `_persist` updated to thread `funding_source_id`.
- [ ] Dedup-notify helper.
- [ ] Unit tests for ensure_funding_source (under cap, at cap, existing match).
- [ ] Free user 2nd bank webhook → tx inserts with `funding_source_id=NULL`, no `funding_sources` row, 1 analytics event.
- [ ] Pro user 4th bank → same block behavior at cap=3.
- [ ] Commit + push.

## Success Criteria
- New bank for free user beyond cap: tx still recorded (no revenue loss), funding_sources stays at 1, analytics event present.
- Existing bank: idempotent, `last_tx_at` advances.
- No race: 5 concurrent calls for 5 distinct banks on Pro user (cap=3) → exactly 3 rows, 2 blocks.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `funding_source_id=NULL` breaks downstream reports | Low | Med | Already nullable per schema (line 164). Reports must handle NULL — verify in Phase 6. |
| Notify-spam (one per blocked tx = N per day) | Med | Low | Dedup via analytics_events lookback. |
| Counting `status='active'` misses paused/archived rows | Low | Low | Spec implies cap = active connections only. Document in service docstring. |

## Security Considerations
- Same as Phase 2: server-side user_id, no client input on the cap decision.
- `funding_sources` rows leak nothing across tenants — `user_id` filter on every query.

## Rollback
`ENFORCE_PLAN_LIMITS=false` env flip; reverts to pre-Phase-3 behavior (tx still inserted, but funding_source auto-create resumes unbounded — that was the bug, but it's not worse than current state).

## Next Steps
Phase 4 (downgrade safety) — what happens to over-cap users when plan reverts.
