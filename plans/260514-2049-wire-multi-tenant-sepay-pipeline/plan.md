---
title: "Wire multi-tenant SePay pipeline (C1 launch blocker)"
description: "Wire new per-tenant SePay capture into running app; retire legacy single-tenant branch safely."
status: pending
priority: P1
effort: 6h
branch: main
tags: [security, multi-tenant, sepay, c1, launch-blocker]
created: 2026-05-14
---

## Context

Source finding: `plans/reports/code-review-260514-full-codebase-deep.md` § C1.

Pipeline (`markets/vn/capture/sepay_webhook.py` + `webhook_tokens.py` + `core/db.py` + `core/observability.py` + `core/logging.py`) is fully unit-tested but **never wired** into `main.py`:
- `main.py:22` imports legacy `handlers.sepay.handle_sepay_webhook` (single-tenant, writes to global Sheet keyed by `config.CHAT_ID`).
- `main.py:179` dispatches all SePay payloads (and email path `main.py:102`) to legacy.
- No `/webhooks/sepay/{token}` route mounted.
- Startup hook (`main.py:39`) skips `create_pool`, `init_sentry`, `configure_logging`, `request_id_middleware`.
- If user #2 onboards, their tx lands in user #1's Sheet → cross-tenant leak.

F01 `/start` IS wired (main.py:217) → mints token → consumer missing.

## Goal

Wire pipeline + decommission legacy SePay branch with parallel-run safety net. No data migration (additive routes only).

## Phases

| # | File | Status | Effort | Description |
|---|------|--------|--------|-------------|
| 1 | [phase-01-startup-wiring.md](phase-01-startup-wiring.md) | pending | 1h | DB pool + Sentry + structlog + request_id middleware on startup |
| 2 | [phase-02-mount-tenant-route.md](phase-02-mount-tenant-route.md) | pending | 1h | Add `POST /webhooks/sepay/{token}` route |
| 3 | [phase-03-parallel-run-telemetry.md](phase-03-parallel-run-telemetry.md) | pending | 30m | Tag both paths with `path=legacy\|v2` for cutover monitoring |
| 4 | [phase-04-migrate-sepay-traffic.md](phase-04-migrate-sepay-traffic.md) | pending | 1h | Switch SePay dashboard webhook URL; runbook + rollback |
| 5 | [phase-05-retire-legacy-sepay.md](phase-05-retire-legacy-sepay.md) | pending | 1h | Delete legacy SePay dispatch arm + tests |
| 6 | phase-06-email-path.md (deferred) | blocked | — | Out of scope — depends on C2 Postmark decision |

## Dependencies

- Phase 1 → 2 → 3 → 4 → 5 strictly sequential. Each ships as separate PR merged to `main`, deployed via Railway GitHub integration.
- Phase 4 is human-coordinated (SePay dashboard); requires ops window.
- Phase 5 blocked until parallel-run telemetry (Phase 3) shows zero legacy traffic for ≥24h after Phase 4.

## Rollback strategy

- Phase 1-3: pure additive → `git revert <sha>` + Railway redeploys prior commit. No data side-effects.
- Phase 4: revert is "change SePay dashboard URL back to `/webhook`". Legacy code still present.
- Phase 5: post-deletion, revert is `git revert` (legacy code restored). After legacy code is fully removed in a later release, rollback window closes.

## Success criteria

- New user `/start` → mint token → SePay webhook to `/webhooks/sepay/{token}` → row in `transactions` table scoped to that user_id.
- Existing single-tenant user transitions without data loss.
- All 458+ existing tests still pass; new integration test for the route asserts tenant isolation.
- Sentry captures any 5xx with `user_id` + `request_id` tags.

## File ownership

- Phase 1-2-3-5 touch `main.py` → strictly sequential (no parallel work on this file).
- Phase 4 touches no code (operational).
- Each phase owns its own new test files.

## Open questions (flag to user)

1. Is `financial-assistant-bot` GCP project / `CHAT_ID` env var still set on Railway prod? If yes, document removal in Phase 5 finalization.
2. Has user #2 ever signed up to prod (check `SELECT count(*) FROM users WHERE channel_user_id != legacy_owner`)? If yes, data audit required before Phase 5 (their tx may have leaked into user #1's Sheet — covered separately, not this plan).
3. Postmark vs Google Apps Script for email path (C2) — blocks Phase 6, not this plan.
4. `DATABASE_URL` env var confirmed present on Railway prod? Phase 1 fails fast if not — verify before deploy.
