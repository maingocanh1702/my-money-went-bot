# Phase 6: Polish + Deploy — 10 PRs

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Ship F09 (scheduled jobs), F10 (payment 3 sub-PRs), F11 admin commands, F13 Messenger (flagged), Sentry alerts, Railway deploy, B2 backup, DR runbook validation.
> **Tham chiếu:**
> - [Implementation Tracker](../implementation-tracker.md)
> - [Implementation Plan Payment](implementation-plan-payment-vietqr-email.md)
> - [Observability Plan](../operations/observability-plan.md)
> - [DR Runbook](../runbooks/disaster-recovery.md)
> - [Roadmap §Phase 6](../mymoneywent-roadmap.md)

---

## Overview

| PR | Scope | Tests | Est. days | Parallel safe? |
|----|-------|:-----:|:---------:|:--------------:|
| F09 | Scheduled jobs (APScheduler, TZ jitter) | 14 | 2.0 | ✅ |
| F11b | Admin commands (`/admin_stats`, `/admin_cost`, `/admin_user`, `/admin_resolve`) | 16 | 2.0 | ✅ |
| W6.1 | Sentry alerts — 7 critical | 8 | 1.0 | ✅ |
| F13 | Messenger adapter (flagged OFF) | 12 | 2.0 | ✅ |
| F10a | Payment VietQR + SePay 4-layer fuzzy match | 18 | 3.0 | ❌ (sequential with F10b/c) |
| F10b | Email backup detect (TCB secondary) | 12 | 2.0 | After F10a |
| F10c | Manual review + recurring billing | 14 | 2.0 | After F10b |
| W6.2 | Railway deploy + custom domain | 4 | 1.5 | After F10c |
| W6.3 | B2 backup automation | 4 | 1.0 | After W6.2 |
| W6.4 | DR runbook full restore validation | — (manual) | 1.0 | After W6.3 |
| **Total** | | **102** | **~17.5 days** | |

**Parallel groups:**
- Group A (parallel): F09 || F11b || W6.1 || F13 (4 features no overlap)
- Group B (sequential): F10a → F10b → F10c (payment chain)
- Group C (sequential, end): W6.2 → W6.3 → W6.4 (deploy chain)

**Solo dev rule:** max 2 active. Pair A+B (1 from each). After A done → B continues alone. C runs last as gate to Phase 7.

---

## F09 — Scheduled jobs

### Scope

- APScheduler async wired to event loop
- Jobs:
  - **Daily recap** per user TZ at 21:00 ±5 min jitter (jitter avoids thundering herd)
  - **Monthly digest** 1st of month, 09:00 user TZ
  - **Trial expiry sweep** hourly (calls F06 trial check)
  - **Onboarding state cleanup** weekly (per F01b decision)
  - **Email idempotency sweep** daily (cleans `email_seen_ids` >24h)
- Job registry pattern: each job is decorated function `@scheduled_job(cron, jitter)`
- Failure: retry 3x exponential, then alert via Sentry (W6.1)

### Files touched

```
+ core/scheduler/__init__.py
+ core/scheduler/jobs.py
+ core/scheduler/daily_recap.py
+ core/scheduler/monthly_digest.py
+ core/scheduler/trial_sweep.py
+ core/scheduler/cleanup.py
+ tests/integration/test_scheduler.py
+ tests/unit/test_jitter.py
M main.py  (boot scheduler at startup, graceful shutdown)
```

### Test plan (14)

1-3. Daily recap: triggered at 21:00 user TZ, jitter ±5 min, content correct
4-5. Monthly digest: 1st of month, includes month aggregate
6-7. Trial sweep: expires correctly, no double-trigger
8. Cleanup: stale onboarding states removed
9. Email idempotency: old Message-IDs cleaned
10. Failure retry: 3 attempts with backoff
11. Failure alert: Sentry capture on final fail
12. Multi-tenant: User A daily recap doesn't include User B data
13. TZ correctness: Asia/Ho_Chi_Minh vs Europe/Berlin same-day boundary
14. Graceful shutdown: in-flight jobs complete, no orphan

### Acceptance criteria

- All 5 job types fire correctly in scheduled window
- TZ + jitter respected
- Failure handling robust
- Multi-tenant isolation in job code

### Decision lockdown

- [ ] **Scheduler lib:** APScheduler (async). Already in pyproject? — Verify, install if needed.
- [ ] **Job persistence:** In-memory + DB-backed (sqlalchemy_jobstore) for cron jobs surviving restart? **MVP: memory only**, restart re-schedules from code. Simpler.
- [ ] **Jitter:** ±5 min uniform random.
- [ ] **Job runner:** Single instance (no distributed). Railway single-replica deploy assumed.

### Risk

- **Multi-instance future:** If horizontal scale needed, need distributed lock. Defer to Phase 9+.
- **TZ DST:** Two transitions/year in northern hemisphere — VN no DST so OK; EU users edge case.

---

## F11b — Admin commands

> F11a authz framework shipped in Phase 2. Here: actual commands.

### Scope

- `/admin_stats` — total users, active users, MRR estimate, parser accuracy snapshot
- `/admin_cost` — daily Postmark + SePay + Railway estimated cost
- `/admin_user <id>` — single user detail (plan, tx count, last activity)
- `/admin_resolve <payment_ref>` — manual payment match override (Phase 6 F10c integration)

### Files touched

```
+ core/handlers/admin.py
+ core/services/admin_stats.py
+ core/services/admin_cost.py
+ tests/integration/test_admin_commands.py
```

### Test plan (16)

Per command (4 each × 4 commands = 16):
- Positive: founder calls → expected output
- Negative: regular user calls → silent ignore (per F11a authz)
- Edge: empty system (0 users) → graceful
- Audit: action logged to `admin_audit_log`

### Acceptance criteria

- All 4 commands functional with real founder data
- Audit log captures every invocation
- No regular user can discover commands

### Decision lockdown

- [ ] **Stats source:** Live queries (no cache MVP). Cache layer Phase 9+.
- [ ] **Cost source:** Hardcoded rates (Postmark $1/10k emails, SePay 0 if free tier, Railway $5-25/mo). Update via config when prices change.
- [ ] **`/admin_resolve`:** Takes payment_ref, sets `payments.matched_user_id` manually, triggers upgrade.

---

## W6.1 — Sentry alerts (7 critical)

### Scope (per `observability-plan.md`):

1. **Tenant leak** — any cross-user data assertion failure in prod
2. **Parser failure** — bank email arrives, no parser matches OR parser throws
3. **Payment match miss** — user pays, no auto-match in 1 hour
4. **SePay webhook silence** — no webhook for >2 hours when user had recent activity
5. **DB pool exhaustion** — connection pool full warning
6. **Migration failure** — alembic upgrade fails on boot
7. **Cost spike** — daily cost >$2 (signal of abuse or bug)

### Files touched

```
+ core/observability/alerts.py
M core/observability.py  (wire alert dispatch)
+ tests/integration/test_alerts.py
+ docs/operations/sentry-alert-rules.md
```

### Test plan (8)

1-7. Each alert type fires correctly under simulated condition
8. Alert deduplication: same alert 100x/hour → max 1 notification (rate limit)

### Acceptance criteria

- 7 alerts wired and tested via synthetic trigger
- Alert notification channel: Sentry → Telegram founder DM (via bot)
- Rate limit prevents alert storm

### Decision lockdown

- [ ] **Notification channel:** Sentry email + bot DM to founder. NO PagerDuty (overkill solo).
- [ ] **Rate limit:** 1/hour/alert-type/affected-user.
- [ ] **Severity:** Tenant leak = P0 (immediate); others P1 (within day).

---

## F13 — Messenger adapter (flagged OFF)

### Scope

- `core/messenger/messenger_fb.py` — Facebook Messenger Send API impl
- Reuse `BaseSender` ABC
- Feature flag `ENABLE_MESSENGER_CHANNEL=false` (default) — env-driven
- Webhook handler stub (auth: verify_token, signature)
- Per `feature-messenger-channel.md` spec — single-bot per pages_messaging app

### Files touched

```
+ core/messenger/messenger_fb.py
+ markets/vn/capture/messenger_webhook.py
+ tests/contract/test_messenger_messenger_fb_contract.py
+ tests/integration/test_messenger_webhook_auth.py
M core/messenger/__init__.py
```

### Test plan (12)

Contract (8): same suite as TelegramSender/DiscordSender (8 cases)
Webhook (3): signature verify, verify_token GET, payload parse
Flag (1): feature flag OFF → adapter not loaded

### Acceptance criteria

- Code ships dark (flag OFF)
- Contract test pass cho 3 senders (TG + Discord + Messenger)
- Webhook handler ready for Meta App Review submission

### Decision lockdown

- [ ] **Flag default:** OFF. Flip ON post Meta App Review approval (external dependency).
- [ ] **No user-facing changes:** F13 ships, no users see it until flag flipped.
- [ ] **Signature verification:** Use FB-supplied SHA1 verify per Meta spec.

---

## F10a — Payment VietQR + SePay 4-layer fuzzy

> Detail per [`implementation-plan-payment-vietqr-email.md`](implementation-plan-payment-vietqr-email.md). Summary here.

### Scope

- VietQR generation via `vietqr.io` public image URL
- 2 QR display (VCB primary + TCB secondary)
- SePay webhook → 4-layer fuzzy match against `payments` pending table
  - Layer 1: exact ref code
  - Layer 2: ref code partial + amount
  - Layer 3: amount + ±10 min window
  - Layer 4: amount + ±1 hour (manual review queue)

### Files touched

```
+ core/services/payment.py
+ core/services/payment_matcher.py
+ core/handlers/payment.py
+ migrations/versions/0004_payments_table.py
+ tests/integration/test_payment_match.py
```

### Test plan (18)

Match layers (8): each layer tested positive + negative
Edge (4): duplicate payment ref; very old pending; user not found; currency mismatch
Isolation (2): user A payment never matches user B
QR (2): URL format, 2-QR display
Manual queue (2): unmatched → `/admin_resolve` queue

### Acceptance criteria

- Per implementation-plan-payment-vietqr-email.md acceptance
- 4-layer fuzzy match passes integration tests
- Manual review queue accessible to founder

---

## F10b — Email backup detect (TCB secondary)

### Scope

- Postmark inbound (W5.1 reused) → TCB email parser → payment matcher fallback
- Resolves: if SePay miss (VCB outage), email path still detects

### Files touched

```
M markets/vn/capture/postmark_webhook.py  (route TCB emails to payment matcher too)
M core/services/payment_matcher.py  (accept email source)
+ tests/integration/test_payment_email_path.py
```

### Test plan (12)

- 4 SePay scenarios from F10a but via email
- 4 cross-source dedup (F02-dedup integration — payment counted once)
- 4 edge: SePay arrives 2 min before email → dedup, email = redundant confirm

### Acceptance criteria

- Email path matches with same 4-layer logic
- Cross-source dedup prevents double-credit
- Founder demo: pay to TCB → email arrives → matched

---

## F10c — Manual review fallback + recurring billing

### Scope

- `/admin_resolve` command (F11b dependency) — list pending, match by hand
- Recurring billing: monthly cron (via F09) for active Pro users
  - 3 days before expiry: friendly reminder + payment instructions
  - On expiry: 7-day grace (Pro features still active)
  - End of grace: downgrade to Free
- Payment confirmed during grace → reset expiry +1 month

### Files touched

```
+ core/services/recurring_billing.py
+ core/scheduler/billing_sweep.py
M core/handlers/admin.py  (/admin_resolve)
+ tests/integration/test_recurring_billing.py
```

### Test plan (14)

Recurring (8): 3d reminder, on expiry, 7d grace, post-grace downgrade, mid-grace renewal, double-charge prevention, partial payment, refund
Manual review (4): list pending, match single, match wrong → revert, audit log
Tenant (2): isolation

### Acceptance criteria

- Recurring cycle works end-to-end with founder test account
- Grace period correct (7 days post-expiry)
- Manual override audit-trailed

### Decision lockdown

- [ ] **Grace period:** 7 days (per BRD).
- [ ] **Refund handling:** Manual only via `/admin_resolve` (no auto-refund MVP).
- [ ] **Hộ kinh doanh registration:** External blocker for legal receipt issuance — flag, ship code first, legal can lag.

---

## W6.2 — Railway deploy + custom domain

### Scope

- Railway service config (Dockerfile-based deploy)
- Custom domain: `tienvenoidau.com` → Railway
- SSL via Let's Encrypt (Railway-managed)
- Production env vars (Postgres URL, Sentry DSN, Postmark API, SePay creds, etc.)
- Secrets review checklist

### Files touched

```
+ railway.toml  (already exists pre-Wave 0, update)
+ docs/operations/deploy-railway.md  (runbook)
M README.md  (deploy section)
```

### Test plan (4 — manual)

1. Cold deploy: connect repo, push main, service boots
2. Domain resolves: `https://tienvenoidau.com/health` returns 200
3. Migration runs: alembic upgrade head on deploy
4. Rollback: deploy previous commit → bot reverts cleanly

### Acceptance criteria

- Production live at custom domain
- HTTPS valid
- Migration auto-runs
- Rollback tested

### Decision lockdown

- [ ] **Railway plan:** Hobby ($5/mo) MVP. Upgrade to Pro when needed.
- [ ] **Postgres:** Railway-managed Postgres 16, single instance.
- [ ] **Secrets:** Railway env vars (no .env file in prod).

---

## W6.3 — B2 backup automation

### Scope

- Daily `pg_dump` cron (via Railway scheduled service or external)
- Upload to Backblaze B2 with SSE-B2 encryption
- Retention: 30 days rolling, 1 monthly forever
- Manifest file with checksums

### Files touched

```
+ scripts/backup_pg_to_b2.sh
+ docs/operations/backup-b2.md
M railway.toml  (add cron service or external trigger)
```

### Test plan (4 — manual)

1. Manual run: pg_dump → B2 upload, file appears
2. Encryption verified (B2 dashboard)
3. Retention: 31st day, oldest dump rotated
4. Checksum verify on download

### Acceptance criteria

- Daily backup runs
- 30+1 retention working
- Restore tested in W6.4

---

## W6.4 — DR runbook validation

### Scope

Per `runbooks/disaster-recovery.md` §11 — execute full restore:
1. Provision fresh Postgres
2. Download latest B2 backup
3. Verify checksum
4. `pg_restore` to fresh DB
5. Boot bot pointing to restored DB
6. Verify founder data integrity (user count, tx count, latest tx date)
7. Document RTO (recovery time objective) actual vs target

### Files touched

```
M docs/runbooks/disaster-recovery.md  (add observed RTO + lessons)
+ docs/runbooks/dr-test-2026-MM-DD.md  (test log)
```

### Test plan

Manual exercise. No automated tests.

### Acceptance criteria

- Restore completed in <4 hours (RTO target)
- Founder data 100% intact
- Lessons documented
- DR runbook updated

---

## Phase 6 exit checklist (gate → Phase 7 Closed Beta)

- [ ] All 10 PRs merged
- [ ] Production live at tienvenoidau.com
- [ ] Backup daily, 30+1 retention
- [ ] DR restore validated, RTO <4h
- [ ] 7 Sentry alerts wired and tested
- [ ] Payment full flow (SePay + email backup) works with founder TCB account
- [ ] Recurring billing cycle simulated end-to-end
- [ ] F13 Messenger code shipped flagged OFF
- [ ] Admin commands all functional
- [ ] Scheduled jobs running in prod (verify daily recap fires)
- [ ] Roadmap Phase 6 → 100%
- [ ] Ready for closed beta recruitment

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial plan. 10 PRs across 3 parallel groups. ~17.5 days est. F10 chain sequential (a→b→c). Deploy chain (W6.2→W6.3→W6.4) blocks Phase 7. F10c flagged Hộ kinh doanh as external (non-code) blocker. |
