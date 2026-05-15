# Phase 05 — Retire legacy SePay branch

## Context Links

- Finding: `plans/reports/code-review-260514-full-codebase-deep.md` § C1
- Files: `main.py` (legacy dispatch arm), `handlers/sepay.py` (legacy module — stays for now, only the dispatch site removed)

## Overview

- **Priority:** P0 (closes the cross-tenant leak surface)
- **Status:** Blocked by Phase 4 (≥24h zero legacy traffic confirmed)
- **Description:** Delete the legacy SePay dispatch arm in `main.py:179`. Telegram callback/message paths (`_handle_callback`, `_handle_message`) STAY — they're separate concern (F02 cutover).

## Key Insights

- Pre-condition: Phase 4 telemetry shows `path=legacy` = 0 for ≥24h.
- Do NOT delete `handlers/sepay.py` module yet — referenced by `_process_email` (email path, C2 deferred).
- Do NOT delete `_handle_callback` / `_handle_message` — Telegram callback prefix routing (`p_`, `s_`, `al_`, etc.) still owned by legacy handlers. F02 will cut those over separately.
- After this phase: cross-tenant leak risk for SePay = 0. (Email path still single-tenant — flagged in C2.)

## Requirements

### Functional
- `_process(body)` no longer dispatches to legacy `handle_sepay_webhook` for non-Telegram bodies.
- The `else` arm is replaced with a structured log warning: "received non-Telegram body on legacy /webhook" (helps catch any SePay re-delivery slipping through).
- Existing Telegram dispatch unchanged.

### Non-functional
- Test coverage drops for legacy SePay dispatch (intentional); add test that confirms non-Telegram POST to `/webhook` is no-op + logged warning.

## Architecture

```
BEFORE:
  /webhook → _process(body):
    if "update_id" in body: → Telegram routes
    else: → handle_sepay_webhook(body)   ← LEGACY (writes to Sheet by CHAT_ID)

AFTER:
  /webhook → _process(body):
    if "update_id" in body: → Telegram routes
    else: log.warning("legacy_webhook.unexpected_body")  ← no-op
```

## Related Code Files

### Modify
- `main.py` — replace `else: await handle_sepay_webhook(body)` arm with logged no-op.
- `main.py` — remove the import `from handlers.sepay import handle_sepay_webhook` IF no other reference. `_process_email` at line 102 also calls it → check; if email path still wired, KEEP the import. (Email retirement = Phase 6, deferred.)
- `tests/` — remove/skip any test that asserts legacy SePay dispatch via `/webhook`.

### Create
- `tests/integration/test_legacy_webhook_no_sepay.py` — POST a SePay-shape body to `/webhook`, assert no insert in `transactions`, no write to legacy Sheet, warning logged.

### Delete
- The legacy dispatch arm only (not the module).

## Implementation Steps

1. Replace `main.py:178-179`:
   ```python
   # --- SePay webhook (LEGACY, retired — see plans/260514-2049-...) ---
   else:
       log.warning("legacy_webhook.unexpected_body", body_keys=list(body.keys()))
   ```
2. Check if `handlers.sepay.handle_sepay_webhook` is still referenced by `_process_email` (line ~102). If yes: KEEP the import (email path still alive, retire in Phase 6). If no: remove import.
3. Write `tests/integration/test_legacy_webhook_no_sepay.py`:
   - POST `{"id": 1, "transferType": "in", "transferAmount": 1000, ...}` to `/webhook`.
   - Assert response = `{"ok": True}` (preserved).
   - Assert no row in `transactions`.
   - Assert structlog captured `legacy_webhook.unexpected_body` event.
4. Remove or skip any test that asserted the legacy SePay dispatch worked through `/webhook`.
5. Run full test suite.
6. PR + Railway deploy.
7. Monitor 48h: confirm `legacy_webhook.unexpected_body` count = 0 (no stragglers).

## Todo List

- [ ] Confirm Phase 4 telemetry shows 24h zero legacy traffic
- [ ] Replace dispatch arm with logged no-op
- [ ] Decide on import retention (depends on email path status)
- [ ] Write `test_legacy_webhook_no_sepay.py`
- [ ] Remove/skip obsolete legacy-dispatch tests
- [ ] Full test suite passes
- [ ] PR + Railway deploy
- [ ] 48h monitor: no `legacy_webhook.unexpected_body` events
- [ ] Decommission `CHAT_ID` env var on Railway if no longer needed (open Q in plan.md)

## Success Criteria

- Codebase has zero call sites to legacy `handlers.sepay.handle_sepay_webhook` from SePay HTTP path (email path remains until Phase 6).
- Cross-tenant SePay leak surface = 0.
- All tests pass; no test asserts legacy SePay dispatch.
- 48h post-deploy: no warnings about unexpected bodies on `/webhook`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SePay re-deliveries arrive post-Phase-4 | Med | Low | Logged warning surfaces them; idempotent no-op |
| Test depends on legacy dispatch behavior | Med | Med | Search for `handle_sepay_webhook` in tests/ before merge |
| Email path indirectly broken | Low | High | Verify `_process_email` import path intact; Phase 6 owns email |
| Premature deletion before 24h telemetry clean | Med | High | Hard gate in todo list; lead approves only after metric review |

## Security Considerations

- Closes the multi-tenant leak surface for SePay path.
- Email path (C2) still vulnerable to single-tenant routing — explicitly out of scope, tracked separately.
- No new auth paths added.

## Rollback

- `git revert <sha>` restores the legacy dispatch arm. Phase 4 rollback (SePay dashboard URL revert) needed in parallel to restore data flow.
- If revert happens after legacy code is fully removed in a later release (out of this plan), rollback becomes "redeploy a snapshot" — document the snapshot SHA.

## Next Steps / Dependencies

- Phase 6 (email path, deferred — C2 + Postmark decision blocker).
- F02 full strangler-fig cutover (Telegram handlers) is a separate multi-week plan, not gated by this phase.
- Remove `CHAT_ID` env var from Railway prod IF audit confirms no remaining single-tenant path uses it (open question in plan.md).
