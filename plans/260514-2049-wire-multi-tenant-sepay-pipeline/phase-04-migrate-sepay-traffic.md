# Phase 04 — Migrate SePay traffic to v2 endpoint

## Context Links

- Finding: `plans/reports/code-review-260514-full-codebase-deep.md` § C1
- SePay dashboard: https://my.sepay.vn → Cài đặt → Webhook (per `.env.example:23`)
- Files: none (operational change)

## Overview

- **Priority:** P0 (the actual cutover)
- **Status:** Not Started
- **Description:** Update SePay dashboard webhook URL from `https://<railway>/webhook` to per-tenant URL. NO CODE CHANGE this phase.

## Key Insights

- Legacy `/webhook` stays alive — if cutover breaks, revert dashboard URL.
- SePay supports only ONE webhook URL per account (verify in dashboard before scheduling).
- The "per-tenant URL" question: SePay sends ALL transactions for the registered SePay account to one URL. In MMW's model, each user registers their own SePay account → their own webhook URL → their own token. So during cutover for the original single-tenant owner (you), you change YOUR SePay account's webhook to YOUR per-tenant URL.
- For future users: onboarding flow already gives them their `/webhooks/sepay/{token}` URL via `/start` → `/settings`. No global cutover needed for them.

## Requirements

### Functional
- Original single-tenant SePay account's webhook URL changed from `/webhook` to `/webhooks/sepay/{owner_token}`.
- Within 30min of switch: telemetry shows `path=v2` traffic, `path=legacy` decline to zero.
- New transactions persisted in `transactions` table with correct `user_id`.

### Non-functional
- Cutover window: scheduled (off-peak VN time, e.g., 10pm-12am ICT).
- Rollback time: <5min (just revert SePay dashboard URL).
- Data continuity: legacy Google Sheet + new Postgres both retain history (no merging this phase).

## Architecture

```
BEFORE:
  SePay → https://<railway>/webhook → legacy handler → Google Sheet (CHAT_ID)

AFTER:
  SePay → https://<railway>/webhooks/sepay/{owner_token} → v2 handler → Postgres (user_id)
```

## Related Code Files

- None modified.

## Implementation Steps (RUNBOOK)

### Pre-flight (T-1 day)

1. Verify Phase 1-3 deployed and stable for ≥24h.
2. Confirm telemetry: `path=legacy` showing real traffic.
3. Owner runs `/start` on prod bot (idempotent — re-issues welcome only). Owner takes the SePay webhook URL from `/settings` (or query `webhook_tokens.display_suffix` for the owner's user_id).
4. Construct full URL: `https://<railway-public-domain>/webhooks/sepay/{raw_token}` (raw token must be retained from `/start` flow; if lost, regenerate via `/settings`).
5. Run synthetic POST against the URL using a SePay-shape payload (curl):
   ```bash
   curl -X POST https://<railway>/webhooks/sepay/{token} \
     -H "Content-Type: application/json" \
     -d '{"id": 999999, "gateway": "TCB", "transactionDate": "2026-05-15 10:00:00",
          "accountNumber": "0123456789", "transferType": "in",
          "transferAmount": 1, "content": "TEST", "referenceCode": "PHASE4-PROBE"}'
   ```
   Verify: row appears in `transactions` with `ref_code='PHASE4-PROBE'`; `tenant_context` user_id correct; no Sentry error.
6. Delete the probe row: `DELETE FROM transactions WHERE ref_code='PHASE4-PROBE';`.

### Cutover (T-0)

7. Log into https://my.sepay.vn → Cài đặt → Webhook.
8. Change URL field: `/webhook` → `/webhooks/sepay/{owner_token}`.
9. Save.
10. Within 5min, generate a real low-stakes transaction (e.g., transfer 1,000 VND to self).
11. Verify in Railway logs: `sepay.dispatch path=v2` event.
12. Verify in Postgres: row in `transactions` with the new tx amount.
13. Verify legacy Google Sheet did NOT receive the new tx.

### Post-cutover (T+24h)

14. Re-check telemetry: `path=legacy` should be 0 for 24h.
15. If non-zero: investigate (SePay may re-deliver pending retries to old URL within their retry window — typically <1h).
16. Once 24h clean → Phase 5 unblocked.

## Todo List

- [ ] Verify Phase 1-3 stable in prod for 24h
- [ ] Synthetic probe via curl → verify row appears, then delete
- [ ] Schedule cutover window (10pm-12am ICT)
- [ ] Update SePay dashboard URL
- [ ] Live transaction test
- [ ] Monitor 24h: legacy traffic = 0
- [ ] Update `.env.example` to document per-tenant URL pattern (replace single-URL docs)

## Success Criteria

- 24h post-cutover: `path=legacy` event count = 0.
- 24h post-cutover: `path=v2` event count > 0 with rows in `transactions`.
- No Sentry incidents.
- Owner sees their tx in bot replies (once F02 wires categorization on v2 path — note: out of scope this plan).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SePay rejects new URL (length/format) | Low | High | Probe with curl + dashboard "test webhook" button before live tx |
| Owner's raw token lost between mint and cutover | Med | High | Regenerate via `/settings` → re-do probe → cutover |
| In-flight retries arrive at old URL post-cutover | Med | Low | Legacy `/webhook` still alive; dedup via ref_code if same tx fires both URLs |
| Misconfigured token → silent 200, tx lost | Med | High | Pre-flight probe verifies the right token; live monitoring catches drop in `path=v2` |
| Railway domain change | Low | High | Use stable `<service>.up.railway.app` or custom domain |

## Security Considerations

- SePay dashboard URL contains raw token — treat that URL as a secret (don't paste in chat logs, screenshots).
- TLS terminates at Railway edge — token transits encrypted.
- No new code paths → no new code review needed.

## Rollback

**5-minute rollback:** Log into SePay dashboard → revert URL to `/webhook` → save. Legacy code path still serves; data flow resumes to Google Sheet. No code revert needed.

**Data inconsistency:** Transactions captured by v2 between cutover and rollback live in Postgres only; legacy Sheet has gap. Document in incident log; either re-import or accept gap (low volume during cutover window).

## Next Steps / Dependencies

- Blocks Phase 5 (can't delete legacy until traffic is 0).
- Does NOT block C2 (email) or H1 (plan-tier enforcement).
