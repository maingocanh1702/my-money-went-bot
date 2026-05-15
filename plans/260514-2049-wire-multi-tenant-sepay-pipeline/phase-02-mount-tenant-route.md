# Phase 02 — Mount per-tenant SePay route

## Context Links

- Finding: `plans/reports/code-review-260514-full-codebase-deep.md` § C1
- Files: `main.py`, `markets/vn/capture/sepay_webhook.py`, `markets/vn/capture/webhook_tokens.py`
- Test: `tests/integration/test_sepay_webhook.py` (existing handler tests; this phase adds HTTP-layer test)

## Overview

- **Priority:** P0 (multi-tenant capture entry point)
- **Status:** Not Started
- **Description:** Mount `POST /webhooks/sepay/{token}` calling `markets.vn.capture.sepay_webhook.handle_sepay_webhook(token, body)`. Legacy `/webhook` left intact for parallel-run safety net.

## Key Insights

- Handler already returns `{"ok": True}` for bad token / bad payload → SePay never retries on validation failure (preserves their retry budget).
- Bodies must be processed inline (handler is async, awaits DB) — but DB insert <50ms, well under SePay's 30s timeout.
- No body-size limit on FastAPI by default — SePay payloads are tiny (<2KB), no DoS surface added.
- Token in URL path is conventional for webhook-per-tenant providers (Stripe, GitHub use similar patterns).

## Requirements

### Functional
- `POST /webhooks/sepay/{token}` accepts JSON body, dispatches to `handle_sepay_webhook(token, body)`.
- Returns `{"ok": True}` always (even on bad JSON → match silent-200 semantics of handler).
- Background processing NOT used here — handler is fast + we want to surface 5xx for monitoring.

### Non-functional
- Latency p99 ≤ 200ms (DB insert).
- All events logged via `log.info("sepay.webhook.persisted", ...)` (already done by handler).
- Sentry catches uncaught exceptions automatically (Phase 1 wired it).

## Architecture

```
SePay POST /webhooks/sepay/{token}
  → FastAPI route extracts token from path
  → await request.json() (catch ValueError → return {"ok": True})
  → await handle_sepay_webhook(token, body)
      → resolve_token(token) → user_id (or silent 200)
      → tenant_context.set_tenant(user_id)
      → _to_canonical(body)
      → _persist(user_id, tx, month_key) → INSERT into transactions
  → JSONResponse({"ok": True})
```

## Related Code Files

### Modify
- `main.py` — add new route after existing `/webhook` route.

### Create
- `tests/integration/test_sepay_route.py` — TestClient POST to `/webhooks/sepay/{token}` with mint-token fixture; assert row in `transactions` scoped to right `user_id`; assert bad token returns 200 with no insert; assert two distinct users don't leak across each other.

### Delete
- None.

## Implementation Steps

1. Add import in `main.py`: `from markets.vn.capture.sepay_webhook import handle_sepay_webhook as handle_sepay_v2` (alias to avoid name clash with legacy import).
2. Add route below existing `/webhook`:
   ```python
   @app.post("/webhooks/sepay/{token}")
   async def webhook_sepay_v2(token: str, request: Request):
       try:
           body = await request.json()
       except Exception:
           return JSONResponse({"ok": True})
       return JSONResponse(await handle_sepay_v2(token, body))
   ```
3. Write `tests/integration/test_sepay_route.py`:
   - Fixture: seed user_A + mint token_A; seed user_B + mint token_B.
   - Test 1: POST real-shape SePay payload to `/webhooks/sepay/{token_A}` → row appears under `user_A.id` only.
   - Test 2: POST to `/webhooks/sepay/{token_B}` → row under `user_B.id` only.
   - Test 3: POST to `/webhooks/sepay/garbage-token` → 200, zero rows inserted.
   - Test 4: POST garbage JSON body → 200, zero rows.
4. Run full test suite; verify pass.
5. Manual smoke against staging: mint token via `/start`, `curl -X POST https://staging/webhooks/sepay/{token}` with SePay-shape body, verify row appears.

## Todo List

- [ ] Add `POST /webhooks/sepay/{token}` to `main.py`
- [ ] Import handler under alias `handle_sepay_v2`
- [ ] Write `tests/integration/test_sepay_route.py` (4 tests above)
- [ ] Pytest full suite passes
- [ ] Manual smoke vs staging Postgres
- [ ] PR + Railway deploy
- [ ] Verify route reachable: `curl https://<railway-url>/webhooks/sepay/test` returns 200 `{"ok": true}`

## Success Criteria

- New integration test confirms tenant isolation (user_A's webhook never touches user_B's rows).
- Existing 458+ tests still pass.
- Production route reachable; bad-token returns 200 without DB writes.
- Sentry shows zero new exceptions in 24h post-deploy.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Token collision (two users get same token) | Negligible | High | `secrets.token_urlsafe(24)` ~144 bits entropy + UNIQUE constraint |
| Inline DB write blocks event loop | Low | Med | Insert <50ms; if becomes issue, move to BackgroundTasks (separate PR) |
| Race between mint + first webhook | Low | Low | mint commits before user sees token; SePay can't fire before user configures |
| Bad regex in route path | Low | Med | FastAPI handles path params safely; no regex used |

## Security Considerations

- Token-in-URL: standard practice; tokens treated as bearer secrets — never log raw token (handler logs only `token_len`).
- Path traversal: FastAPI URL parser rejects `/` in `{token}` segment by default.
- Timing-safe comparison already in `resolve_token` via `hmac.compare_digest`.
- No CSRF concern (no cookies; pure server-to-server webhook).

## Rollback

- `git revert <sha>` removes route. Legacy `/webhook` still serves SePay if dashboard URL unchanged.
- No data rollback needed (only new rows are valid scoped writes).

## Next Steps / Dependencies

- Requires Phase 1 (DB pool, request_id middleware).
- Phase 3 adds path telemetry to both legacy + v2 routes.
- Phase 4 cuts SePay dashboard over to the new URL.
