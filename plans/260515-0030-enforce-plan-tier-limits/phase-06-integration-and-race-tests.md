# Phase 6 — Integration + concurrent-insert race tests

## Context Links
- Report: §H1 lines 87-95 (the canonical race scenario).
- Phases 2, 3, 4 produced the code; this phase validates it doesn't regress under concurrency.
- Existing test conventions: `tests/markets/vn/capture/` already has `test_sepay_webhook.py` (per C1 plan).

## Priority
P1 — without race coverage we can't claim H1 is fixed.

## Status
pending — final phase, all preceding code must be merged.

## Key Insights
- Race tests in async Python are flaky-prone. Use `asyncio.gather(*tasks)` for true parallel dispatch — NOT a for-loop with `await`. Each task gets its own DB connection from the pool.
- Pool size in tests must be >= concurrency factor or test serializes silently. Set `min_size=10, max_size=20` for the test pool.
- Postgres advisory lock guarantees serialization at the SQL level — even with 20 connections all hitting at once, the lock makes them queue. The test asserts the OUTCOME (row count), not the ordering.
- Use a fresh test DB (or transaction-rollback isolation) per test to keep counts predictable.
- Mock Telegram + analytics; we're testing the DB invariant, not the side-effects.

## Requirements
**Functional**
- `tests/markets/vn/capture/test_sepay_webhook_caps.py` — covers:
  1. `test_free_user_under_cap_inserts` — sequential 44 inserts → 44 rows.
  2. `test_free_user_at_cap_hard_rejects` — 45th insert → row=45; 46th → row=45, analytics row, no exception.
  3. `test_free_user_race_at_cap` — seed 44 rows, gather(20 webhooks) → exactly 45 rows.
  4. `test_pro_user_unlimited` — gather(200 webhooks) → 200 rows, no advisory-lock contention measurable (timing < 5s wall).
  5. `test_flag_off_disables_enforcement` — `ENFORCE_PLAN_LIMITS=false` → Free user 100 inserts succeed.
- `tests/services/test_plan_limits_svc.py` — unit tests:
  6. `test_caps_constant_matches_spec` — assert CAPS values per `feature-pricing-tiers.md:120`.
  7. `test_try_insert_tx_pro_short_circuits` — verifies no advisory lock acquired (mock).
- `tests/services/test_funding_sources_svc.py` — Phase 3:
  8. `test_ensure_funding_source_under_cap_creates`
  9. `test_ensure_funding_source_at_cap_blocks_new_returns_none`
  10. `test_ensure_funding_source_existing_returns_existing_id`
  11. `test_race_5_concurrent_new_banks_on_pro_user` — gather, 5 distinct (bank,last4); cap=3 → exactly 3 created, 2 blocked.
- `tests/integration/test_downgrade_safety.py` — Phase 4:
  12. `test_cron_downgrades_expired_pro_to_free`
  13. `test_cron_idempotent_second_run_zero_updates`
  14. `test_frozen_user_blocked_msg_differs_from_normal_block`

**Non-functional**
- Each race test must complete in <10s on CI.
- No mocking of asyncpg — use real test DB.
- Tests must pass with `pytest -p no:randomly` and randomized.

## Architecture
```
test fixture:
  ├─ asyncpg pool (min=10, max=20)
  ├─ alembic upgrade head (clean schema)
  ├─ insert test user with plan='free', plan_expires_at=NOW()+1yr
  ├─ mint webhook token
  └─ yield (token, user_id, conn)

race test pattern:
  payloads = [build_payload(amount=i, ref_code=f"R{i}") for i in range(20)]
  results = await asyncio.gather(*[handle_sepay_webhook(token, p) for p in payloads])
  count = await conn.fetchval("SELECT COUNT(*) FROM transactions WHERE user_id=$1", user_id)
  assert count == 45  # seeded 44 + 1 winner
  analytics = await conn.fetch("SELECT * FROM analytics_events WHERE event='tier_limit_hit'")
  assert len(analytics) == 19
```

## Related Code Files
**Create**
- `tests/markets/vn/capture/test_sepay_webhook_caps.py`
- `tests/services/test_plan_limits_svc.py`
- `tests/services/test_funding_sources_svc.py`
- `tests/integration/test_downgrade_safety.py`
- `tests/conftest.py` — may need fixture additions (test pool, alembic setup).

**Modify** — none.

## Implementation Steps
1. Read existing `tests/markets/vn/capture/test_sepay_webhook.py` (post-C1) to match style + fixtures.
2. Identify test DB strategy (per-test transaction rollback? testcontainers? existing `conftest.py` should reveal).
3. Write unit tests first (faster feedback): 6, 7, 8-10.
4. Write integration tests: 1, 2, 12-14.
5. Write race tests last (most fragile): 3, 4, 11.
6. Run `pytest tests/markets/vn/capture/test_sepay_webhook_caps.py -v` — all green.
7. Run full suite `pytest -q` — no regressions.
8. Add `pip-audit` check inline if not already in CI (separate from this phase but good hygiene).
9. Commit: `test(h1-p6): plan-tier enforcement + race coverage`.

## Todo List
- [ ] Read existing test conventions / fixtures.
- [ ] 14 tests written (numbered 1-14 above).
- [ ] Unit tests green.
- [ ] Integration tests green.
- [ ] Race tests green 3x in a row (flake check).
- [ ] Full suite green.
- [ ] CI passes on PR.
- [ ] Commit + push.

## Success Criteria
- **The H1 race scenario from the review report (line 84) is covered by test #3.** This is THE test that proves H1 is fixed.
- All 14 tests green on CI.
- Race tests pass under randomized test order.
- Coverage of `plan_limits_svc.py` ≥ 90%.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Race test flaky on slow CI | Med | Med | Run 3x locally before merging. Use `pytest-repeat` 5x in CI for the race test specifically. |
| Pool exhaustion gives false pass (all serial) | Low | High | Assert `pool.get_size() >= concurrency` at test start. |
| Test DB state bleeds between tests | Med | High | Per-test transaction rollback via `conftest.py` fixture; verify by running suite twice. |
| Mocked Telegram silently passes when notify path is broken | Med | Low | Use `unittest.mock.AsyncMock` + assert called with expected key + cap. |

## Security Considerations
- Tests must NOT use prod credentials. Use `TEST_DATABASE_URL`, fail loudly if pointing to prod (regex check on host in fixture).
- No real Telegram tokens; mock at the `telegram_api.send_message` boundary.

## Rollback
Drop the test files. No prod impact. (Tests-only phase.)

## Next Steps
After Phase 6 green: H1 is closed. PR can merge to main. Update `plans/reports/code-review-260514-full-codebase-deep.md` H1 entry to "MITIGATED — see plans/260515-0030-enforce-plan-tier-limits/".

Future work (not this PR):
- Stripe / PayOS upgrade webhook → sets `plan`, clears `limits_frozen_at`.
- Family tier (4-tier expansion per spec v1.1.0).
- Soft warning at 35/45 (D1=B variant) if product chooses to add later.
