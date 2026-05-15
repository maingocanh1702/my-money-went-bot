# Phase 03 — Parallel-run telemetry

## Context Links

- Finding: `plans/reports/code-review-260514-full-codebase-deep.md` § C1
- Files: `main.py` (legacy `/webhook` arm + new `/webhooks/sepay/{token}` arm)

## Overview

- **Priority:** P1 (gates safe cutover)
- **Status:** Not Started
- **Description:** Emit structured log event from BOTH legacy and v2 SePay paths with field `path=legacy|v2`. Lets ops dashboard count traffic split during cutover. Zero behavior change.

## Key Insights

- Cutover (Phase 4) is a single SePay dashboard change — we need observability BEFORE we flip, not after.
- structlog already configured (Phase 1) → JSON to stdout → Railway logs → Logtail/Grafana.
- Don't log the full payload (PII: account number, amount) — only the routing fact.
- Legacy module logs already exist; we add the `path` tag at the dispatch site in `main.py`, not deep in legacy.

## Requirements

### Functional
- Every SePay payload dispatched via legacy `/webhook` → logs `event="sepay.dispatch", path="legacy"`.
- Every SePay payload dispatched via new `/webhooks/sepay/{token}` → logs `event="sepay.dispatch", path="v2"`.

### Non-functional
- No PII in log fields.
- Single log line per dispatch (not per nested call).

## Architecture

```
/webhook → _process(body)
  → if "update_id" not in body:
      log.info("sepay.dispatch", path="legacy")  ← NEW
      await handle_sepay_webhook(body)           ← legacy

/webhooks/sepay/{token}
  → log.info("sepay.dispatch", path="v2")        ← NEW
  → await handle_sepay_v2(token, body)
```

## Related Code Files

### Modify
- `main.py` — add one log line in legacy SePay dispatch arm (line ~179) and one in the new route handler.

### Create
- None (uses existing `get_logger`).

### Delete
- None.

## Implementation Steps

1. At top of `main.py`, add: `from core.logging import get_logger` (if not already imported).
2. After `from contextlib` block, add module logger: `log = get_logger(__name__, component="webhook_dispatch")`.
3. In `_process(body)`, just before `await handle_sepay_webhook(body)` (legacy arm), add:
   ```python
   log.info("sepay.dispatch", path="legacy")
   ```
4. In the new `webhook_sepay_v2` route, add at entry:
   ```python
   log.info("sepay.dispatch", path="v2")
   ```
5. Add unit test `tests/unit/test_dispatch_telemetry.py` using `structlog.testing.capture_logs()` to assert each path emits the right event.
6. Run pytest.
7. Deploy. After 24h, query logs to confirm both `path=legacy` and `path=v2` counts visible.

## Todo List

- [ ] Add `log.info("sepay.dispatch", path=...)` to both arms in `main.py`
- [ ] Write telemetry unit test
- [ ] Pytest passes
- [ ] PR + Railway deploy
- [ ] Verify both events visible in prod logs

## Success Criteria

- Both events visible in Railway logs.
- 24h pre-Phase-4 baseline: `path=legacy` >> 0, `path=v2` ≈ 0 (no traffic yet).
- 24h post-Phase-4: `path=legacy` ≈ 0, `path=v2` >> 0 (cutover confirmed).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Log volume bloat | Low | Low | One line per webhook event; SePay volume <1/sec |
| Accidental PII inclusion | Low | High | Only `path` string logged; reviewed in PR |
| structlog not configured at log call | Low | Med | Phase 1 wires `configure_logging` in lifespan |

## Security Considerations

- No tokens, account numbers, or amounts logged at dispatch layer.
- `tenant_context` already binds `user_id`/`request_id` to structlog automatically (Phase 1) — present on v2 path once handler sets tenant; legacy path has no user_id (single-tenant). This asymmetry is informative for ops.

## Rollback

- `git revert <sha>` removes log lines. No data side-effects.

## Next Steps / Dependencies

- Depends on Phase 1 (structlog configured) and Phase 2 (v2 route exists).
- Gate for Phase 4: confirm telemetry working in prod before flipping SePay dashboard URL.
