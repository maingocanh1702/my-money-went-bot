# Implementation Plan — 500 Users and More

> **Version:** v1.3.0
> **Ngày tạo:** 2026-05-06
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Mục đích:** Roadmap scale từ MVP (100 users) lên 500-2000+ users. Document spec gaps, engineering work, operational readiness, và migration trigger.
> **Scope note:** Bỏ qua phần đăng ký hộ kinh doanh (xử lý parallel ngoài scope plan này). Tax/VAT workflow chỉ cover phần technical (reconciliation, invoice generation), không cover legal entity setup.
> **Tham chiếu:** [BRD v2.9.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd.md) · [TDD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) · [Feature Spec Refactor SaaS v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_saas_refactor.md) · [Feature Spec Payment v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_payment.md) · [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md) · [Impl Plan VietQR+Email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md)

---

## 1. Executive Summary

### 1.1. Current state assessment

| Doc | Coverage cho 0-100 | 100-500 | 500-2000 | 2000+ |
|---|---|---|---|---|
| BRD/PRD/TDD | 95% | 85% | 60% | 40% |
| Refactor spec | 100% | 100% | 100% | n/a |
| Payment spec | 100% | 100% | 80% | 50% |
| **Average** | **97%** | **88%** | **75%** | **45%** |

**Verdict**: Docs đủ **start Phase 1 foundation dev**. Launch MVP cho 100 users **YÊU CẦU C2/C3/C6 specs phải implemented** (3 spec phải write trước hoặc song song Phase 1, dev distribute Phase 1-6). Để vận hành 500-2000 users ổn định cần thêm **7 spec/runbook** mới + 2 expand existing.

### 1.2. Critical gaps blocking scale

| # | Gap | Trigger scale | Effort spec | Effort dev |
|---|------|--------------|-------------|------------|
| C1 | Customer support automation | 200+ users | 1-2 ngày | 5-7 ngày |
| C2 | Admin tools / dashboard | Pre-launch | 1-2 ngày | 3-5 ngày |
| C3 | Disaster recovery runbook | Pre-launch | 1 ngày | 2 ngày (test runs) |
| C4 | DB scaling concrete plan | 500+ users | 1 ngày | 3-5 ngày |
| C5 | Concurrency audit + race conditions | 500+ users | 2 ngày | 3-4 ngày |
| C6 | Production observability | Pre-launch + scale | 1 ngày | 3-5 ngày |
| C7 | Tax/reconciliation workflow | MRR > $200/mo (≈300 users) | 1 ngày | 3-4 ngày |
| C8 | Bot pool implementation (expand PRD §5.4.2) | 500-700 users | 2 ngày | 5-7 ngày |
| C9 | Outbound queue + rate limiter (expand PRD §5.4.2) | 100+ users | 1 ngày | 3-4 ngày |
| C10 | **Channel adapter pattern + Messenger MVP build** | Pre-launch (MVP) | Done — [feature-spec-messenger-channel v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md) + [impl plan VietQR+email v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-payment-vietqr-email.md) | 10 ngày Messenger build (Phase 6 Tuần 10-11) + **3-5 ngày VietQR/email parallel** (integration/test surface, không phải 2 ngày) |
| C11 | **Landing page + Privacy policy + Terms** (pre-launch operational item) | Phase 7 (required cho Meta App Review + PDPA) | Done — [decision-onboarding-ui-strategy v1.0.1 §5.2 + §8](file:///Users/maingocanh/Projects/MyMoneyWent/docs/decision-onboarding-ui-strategy.md) | ~3 ngày dev (1 day landing + 1 day privacy + 1 day polish) |
| C12 | Web dashboard (read-only reports) | MRR >$300/mo + user feedback >30% request | Trigger-based, defer | 5-10 ngày dev khi trigger hit. Detail trong [decision-onboarding-ui-strategy §6 triggers](file:///Users/maingocanh/Projects/MyMoneyWent/docs/decision-onboarding-ui-strategy.md) |

**Total work**: ~11-13 ngày spec writing + ~46-65 ngày dev (thêm 13-15 ngày Messenger + VietQR + 3 ngày landing/privacy + 5-10 ngày dashboard if triggered), spread across 12 tháng post-launch.

### 1.3. Phasing principle

**Build-just-in-time** cho operational specs (support, scaling), nhưng **spec-first cho foundation decisions** ảnh hưởng schema/interface từ ngày 1.

**Foundation specs PHẢI WRITE TRƯỚC Phase 1 dev** (vì ảnh hưởng schema + interface):
- **C2 admin tools** → schema `admin_audit_log`, env `ADMIN_TELEGRAM_IDS`, command auth pattern
- **C9 messenger abstraction** → interface `messenger.send(user_id, payload)` thay vì hardcode `telegram.send_message(chat_id, text)`. Initial impl direct-send, swap sang queue sau không refactor handlers
- **C10 (NEW v1.3.0) channel adapter pattern** → `services/channels/{base,telegram,messenger}.py` adapter với `BaseSender` ABC. Foundation cho Messenger MVP build (Phase 6 Tuần 10-11) + Zalo/WhatsApp Phase 2+. Schema `users.channel_type` + `channel_user_id` thay `telegram_id UNIQUE`. Detail: [feature-spec-messenger-channel v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md).

**Operational specs viết khi cận trigger:**
```
Pre-Phase 1 (week 0): C2 admin tools spec, C3 DR runbook, C6 observability outline,
                       C9 messenger interface + C10 channel adapter decision
                       (channel adapter pattern viết vào refactor spec + messenger spec)
Phase 1-6 (MVP build): implement C2 + C3 + C6 + C9 + C10 Telegram adapter
                       (Messenger adapter Phase 6 Tuần 10-11)
Phase 7-8 (Beta + Soft launch, 0-100): verify all critical specs working
                                        + ≥2 user signup qua Messenger validate parity
                                        + C11 landing + privacy + terms ship
                                        (decision-onboarding-ui-strategy §5.2: ~3 ngày dev,
                                         chat-only onboarding, KHÔNG build web form)
Tháng 1-3 post-launch (100-200): C9 swap direct-send → queue (no handler refactor needed)
Tháng 4-6 post-launch (200-400): C1 (support automation) ship, C5 audit
Tháng 7-9 post-launch (400-700): C8 (bot pool — Telegram only, Messenger có Meta tự throttle),
                                  C4 (DB scaling)
Tháng 10-12 post-launch (700+): C7 (tax workflow), refine all
                                  + C12 web dashboard (read-only reports) — chỉ trigger
                                    nếu MRR >$300/mo + user feedback request
                                    (decision-onboarding-ui-strategy §6 triggers)
```

---

## 2. Scale Tiers — Concrete Trigger + Action

### 2.1. Tier 0-100 active users (MVP launch — Phase 7-8 BRD)

**Profile:** Closed beta + soft launch. Founder solo handle support. 1 Railway instance. 1 Telegram bot. 1 Postmark account.

| Aspect | Status | Notes |
|---|---|---|
| Bot pool | Single bot OK | ~5-10 msg/s peak — well under 30/s limit |
| DB | Single Postgres | Connection pool min=2, max=10 |
| Postmark | $10 starter tier | <10k email/mo |
| Support | Founder direct via Telegram | <2h/day workload |
| Backup | Daily B2 + Railway WAL | Manual restore test 1x/tháng |
| Monitoring | Sentry free + Railway built-in | Basic only |

**Required to ship (in dependency order):**
- ⏳ **Pre-Phase 1 (week 0)**: write C2 admin tools spec, C3 DR runbook, C6 observability outline (3-5 ngày)
- ⏳ **Phase 1-2 foundation**: `admin_audit_log` table, `ADMIN_TELEGRAM_IDS` auth framework, **`messenger.send()` interface abstraction** (C9 foundation, direct-send initial impl)
- ⏳ Phase 1-6 dev complete (refactor + onboarding + payment + email parsing)
- ⏳ Phase 6 expanded (tuần 10-12): payment integration + admin commands + observability dashboard
- ⏳ Phase 7: 1 successful DR full-restore test (C3 scenario A)

**Triggers to next tier:**
- Active users reach 100 → start C9 outbound queue planning
- Support time > 5h/tuần → start C1 support automation planning

### 2.2. Tier 100-500 active users (Steady-state MVP)

**Profile:** 12 months post-launch target. ~5-15% paying conversion. MRR $50-200. Founder still solo but stretched.

| Aspect | Status | Action |
|---|---|---|
| Bot pool | Single bot vẫn OK | Add **outbound queue** (C9) — buffer message để smooth peaks |
| DB | Tune pool max=20, add read replica nếu cần | Concrete plan trong C4 |
| Postmark | $15-30/mo | Volume tier khi >10k email/mo |
| Support | **Bottleneck** ở 200+ | C1 support automation MUST ship trước 300 users |
| Backup | Daily + monthly recovery test | Automated test |
| Monitoring | Per-user metrics dashboard | Build C6 fully |

**New work needed:**
- C9 Outbound queue (3-4 ngày dev)
- C1 Customer support automation (5-7 ngày dev)
- C5 Concurrency audit (3-4 ngày dev)
- C6 Observability full implementation (3-5 ngày dev)

**Triggers to next tier:**
- Active users reach 500 → bot pool migration MUST start
- Telegram peak >25 msg/s → outbound queue rate limiter mandatory
- Postgres connection saturation → read replica

### 2.3. Tier 500-2000 active users (Growth phase)

**Profile:** Beyond MVP target. Founder cần thuê support hoặc fully automate. MRR $400-2000.

| Aspect | Action |
|---|---|
| Bot pool | **Migrate sang 2-3 bot** (C8). Sticky route theo `users.bot_id` |
| DB | **Read replica** cho reports + analytics queries. Partition `transactions` by month. Vacuum schedule |
| Postmark | $30-60/mo + email parser fallback bank tiering |
| Support | Hire 1 part-time + automation FAQ bot covers 70% common cases |
| Hosting | **Migrate Hetzner Singapore** nếu Railway >$30/mo (BRD §5.5 trigger) |
| Backup | Multiple region B2 + automated weekly recovery test |
| Monitoring | PagerDuty / on-call rotation |

**New work needed:**
- C8 Bot pool implementation (5-7 ngày dev)
- C4 DB scaling implementation (3-5 ngày dev)
- C7 Tax/reconciliation (3-4 ngày dev) — VAT invoice automation
- Railway → Hetzner migration runbook (3-5 ngày dev + test)

### 2.4. Tier 2000+ users (Re-architecture territory)

**Profile:** Out of MVP scope. Cần dedicated team, full ops infrastructure.

Action: Re-evaluate architecture. Khả năng cao cần:
- **Local Bot API server self-host** (telegram-bot-api binary)
- **Postgres horizontal scaling** (Citus / sharding)
- **App tier horizontal scaling** (multi-instance + shared state via Redis)
- **Dedicated DevOps role**

→ **Defer detailed planning đến khi reach 1000 active users**. Trigger: MRR > $1500 + sustained growth 20%+ MoM.

---

## 3. Spec Gaps — Detailed Action Items

### C1. Customer Support Automation 🔴 (Blocker @ 200+)

**Why critical:** BRD §5.4.3 đã warn: ở 500 users với 1-2 ticket/user/tháng = 500-1000 ticket. Solo founder handle không nổi (25-50h/tuần support work).

**Trigger to write spec:** Khi active users reach 100 (Phase 7 beta).
**Trigger to ship:** Trước khi reach 250 active users.

**Spec scope (write thành `docs/feature-spec-support-automation.md`):**

1. **In-bot FAQ system**
   - `/help` command với inline keyboard categories: Setup / Payment / Categorization / Account
   - Pre-written answers cho top 30 common questions (compiled từ beta feedback)
   - Search trong FAQ qua keyword matching

2. **Self-serve troubleshooting flows**
   - "Webhook không nhận transaction" → guide check SePay setup → test endpoint
   - "Email forwarding không hoạt động" → guide verify forwarding rule → check inbound logs
   - "Payment chuyển rồi nhưng chưa nhận confirmation" → /payment_help (đã spec)
   - "Bị charge nhầm / muốn refund" → escalate to founder review

3. **Admin queue management**
   - Telegram admin chat (group hoặc DM) hiển thị tickets cần handle
   - Categories: payment_unmatched, parser_fail, pricing_question, bug_report
   - SLA: respond <24h cho payment, <72h cho khác

4. **Knowledge base self-serve**
   - Static landing page `help.fintrack.app` với top articles
   - Auto-link từ bot khi user query không match FAQ

5. **Metrics dashboard**
   - Tickets/day, resolution time, FAQ hit rate
   - User satisfaction (`/feedback` after resolution)

**Acceptance Criteria (high-level):**
- [ ] FAQ bot resolve ≥70% tier-1 question (no human)
- [ ] Average response time tier-2 (founder) <12h
- [ ] Founder support time <15h/tuần ở 500 users
- [ ] Self-serve troubleshooting cover top 10 known issues

**Effort:** 1-2 ngày spec write, 5-7 ngày dev (FAQ flow + admin queue + metrics).

---

### C2. Admin Tools / Dashboard 🔴 (Blocker — write spec BEFORE Phase 1 dev)

**Why critical:** Manual review payment, refund processing, force-cancel pending — không có thì founder không operate được day 1. Quan trọng hơn: admin actions ảnh hưởng **schema + auth + logging từ Phase 1** — nếu spec viết muộn, phải refactor ngược.

**Specifically affecting Phase 1-2 work:**
- DB schema cần `admin_audit_log` table (ghi mọi admin action) — phải có trong initial migration
- env var `ADMIN_TELEGRAM_IDS` (plural — multiple admin support) — phải defined ở config từ đầu
- Command authorization framework — pattern dispatch checking `is_admin(from_id)` trước handler
- Manual plan override → schema cần `plan_override_until` hoặc audit pattern để revert
- Manual payment resolve → cần endpoint riêng và admin-only handler

**Trigger to write spec:** **TUẦN NÀY (week 0, Pre-Phase 1)**. KHÔNG defer tới wave sau vì schema impact.
**Trigger to ship implementation:** Foundation parts ở Phase 1-2 (DB schema + auth pattern), full commands ở Phase 6.

**Spec scope:** [`docs/features/feature_admin_tools.md`](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_admin_tools.md)

1. **Schema additions (Phase 1 migration)**:
   ```sql
   CREATE TABLE admin_audit_log (
       id              BIGSERIAL PRIMARY KEY,
       admin_telegram_id BIGINT NOT NULL,
       command         VARCHAR(64) NOT NULL,
       target_user_id  INT REFERENCES users(id),
       payload         JSONB,
       result          VARCHAR(16),                     -- 'success'|'fail'|'denied'
       error_message   TEXT,
       executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   CREATE INDEX idx_admin_audit_admin ON admin_audit_log(admin_telegram_id, executed_at DESC);
   CREATE INDEX idx_admin_audit_target ON admin_audit_log(target_user_id, executed_at DESC);
   ```

2. **Authorization framework (Phase 2)**:
   - env `ADMIN_TELEGRAM_IDS` = comma-separated list `123,456,789`
   - Decorator/middleware `@admin_only` cho mọi `/admin_*` command
   - Auto-log mọi admin invocation vào `admin_audit_log` (success + denied attempts)
   - Confirmation step cho destructive ops (refund, force-cancel) — type 'confirm'

3. **Telegram admin commands** (in admin chat only, restricted bằng `ADMIN_TELEGRAM_IDS`):
   - `/admin_users [search]` — list/search users
   - `/admin_user {user_id}` — user detail (plan, tx count, last active)
   - `/admin_pending` — list pending payments needing review
   - `/admin_unmatched` — list unmatched_payments queue
   - `/admin_resolve {unmatched_id} {pending_id}` — manual link
   - `/admin_refund {match_id}` — refund + downgrade plan
   - `/admin_extend {pending_id} {hours}` — extend pending TTL
   - `/admin_force_plan {user_id} {plan} {expires_at}` — manual plan adjust (free month, comp upgrade, etc.)
   - `/admin_logs {user_id}` — last 50 events for user
   - `/admin_stats` — daily summary (signups, payments, errors)

4. **Optional minimal web dashboard** (Phase 7+):
   - Single-page HTML serve từ FastAPI route `/admin` (auth via session cookie)
   - Tables: users, pending_payments, unmatched_payments, payment_matches
   - Action buttons cho common operations
   - Metrics charts (chart.js client-side)

5. **CLI scripts** cho founder local use:
   - `scripts/manual_match.py {unmatched_id} {pending_id}` — emergency link
   - `scripts/recompute_plan.py {user_id}` — recalc plan_expires_at từ payment history
   - `scripts/export_user.py {user_id}` — full data export (PDPA request)

**Acceptance Criteria:**
- [ ] Mọi action trong payment spec §10.7 có command
- [ ] Restricted bằng `ADMIN_TELEGRAM_IDS` env var (comma-separated list, multi-admin)
- [ ] Audit log mỗi admin command vào `admin_audit_log`; optionally mirror summary event vào `analytics_events`
- [ ] Force-action có confirmation step ("Type 'confirm' to proceed")

**Effort:** 1-2 ngày spec, 3-5 ngày dev. Web dashboard optional có thể defer.

---

### C3. Disaster Recovery Runbook 🔴 (Blocker pre-launch)

**Why critical:** BRD §10 success criterion "Backup recovery test thành công" là 1 dòng. Cần actual runbook để khi sự cố xảy ra founder biết làm gì.

**Trigger to write:** Trước Phase 7 beta launch.
**Trigger to test:** Phase 7 (test 1 lần với staging).

**Document scope:** [`docs/runbooks/disaster-recovery.md`](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md)

1. **Backup setup**
   - `pg_dump` script chạy daily 03:00 UTC
   - Upload tới B2 với versioning (30-day retention)
   - Encryption at rest (B2 server-side)
   - Verify backup integrity weekly (parse + spot check)

2. **Recovery scenarios + playbook**

   **Scenario A: Postgres data corruption**
   - Stop app instance
   - Spin up fresh Postgres on Railway (new addon)
   - Download latest B2 backup
   - `psql < backup.sql`
   - Update `DATABASE_URL` env var
   - Restart app
   - Verify với 5 mock query
   - **RTO: 2 hours**, **RPO: 24 hours** (last daily backup)

   **Scenario B: Railway full outage**
   - Migrate to Hetzner Singapore (pre-prepared docker-compose ready)
   - Restore từ B2 backup
   - Update DNS A record `api.fintrack.app` → Hetzner IP
   - Verify with smoke test
   - **RTO: 4 hours**, **RPO: 24 hours**

   **Scenario C: BOT_TOKEN compromised**
   - Revoke compromised token via @BotFather
   - Generate new token
   - Update `BOT_TOKEN` env var ở Railway
   - Update Telegram webhook
   - **RTO: 5 minutes**, **RPO: 0** (no data loss)

   **Scenario D: Bot bị Telegram suspend**
   - Switch sang `BOT_TOKEN_BACKUP` env var
   - Update Telegram webhook to new bot
   - Notify all users qua mass message via new bot
   - Investigate ToS violation, appeal
   - **RTO: 5 minutes**, **RPO: 0**

   **Scenario E: Postmark outage**
   - Email path C → fallback to Apps Script (founder's Gmail) tạm thời?
   - Hoặc accept gián đoạn 1-4h, notify users qua bot
   - **RTO: depends Postmark**, **RPO: emails delivered late**

   **Scenario F: Founder unavailable (illness, travel)**
   - Pre-share emergency runbook với 1 trusted contact
   - Auto-pause new signup khi unmatched > 50 (avoid digging deeper hole)
   - Auto-extend pending payment TTL +48h

3. **Test schedule**
   - Monthly: B2 download + parse spot check (15 min)
   - Quarterly: Full restore to staging + smoke test (2h)
   - Annually: End-to-end DR drill including DNS migration (1 day)

4. **Communication plan**
   - User-facing status page: hosted on GitHub Pages, manually updated
   - In-bot announcement template
   - Admin Telegram chat for incident coordination

**Acceptance Criteria:**
- [ ] All 6 scenarios có step-by-step playbook
- [ ] RTO/RPO documented per scenario
- [ ] 1 successful full restore test before launch
- [ ] Quarterly test schedule on calendar

**Effort:** 1 ngày write + 2 ngày test runs.

---

### C4. Database Scaling Concrete Plan 🟡 (Trigger @ 500+)

**Why needed:** PRD §5.4.1 nói "100-500 optimize queries", "500+ evaluate Hetzner" — quá vague. Cần concrete plan với metrics + thresholds.

**Trigger to write:** Khi reach 200 active users.
**Trigger to implement:** Khi reach 500 hoặc khi metrics show bottleneck.

**Document scope (write thành `docs/feature-spec-db-scaling.md`):**

1. **Metric thresholds** (từ Postgres `pg_stat_*`):
   - Connection pool saturation: `active_connections / max_connections > 80%` → action
   - Slow query: `avg_query_time > 100ms` cho any common query → optimize
   - Disk size: `pg_database_size > 5GB` → consider partitioning
   - Index bloat: `pg_indexes_size > 30%` of table → reindex

2. **Optimization tier 1 (no infra change, ~200-500 users):**
   - Add indexes:
     - `(user_id, created_at DESC)` cho timeline query
     - `(month_key, user_id)` cho monthly aggregation
     - Partial index `WHERE status = 'pending'` cho job/payment scan
   - Connection pool tuning: `min=5, max=30` (Railway Hobby cap)
   - Query rewrites: avoid N+1 trong report generation
   - Vacuum schedule: autovacuum aggressive cho high-churn `bot_state`

3. **Optimization tier 2 (~500-1000 users — but METRIC-triggered, not user-count-triggered):**

   > **Read replica trigger:** chỉ deploy khi ≥1 metric sau hit threshold:
   > - Primary DB CPU > 70% sustained > 1 hour
   > - Connection pool saturation > 85% sustained
   > - Slow query (`/status`, `/report`) p95 > 1.5s
   >
   > Ở 500 users với good indexes, query hygiene + connection pooling thường **đủ — không nhất thiết cần replica**. Nhiều system hoạt động well ở 500-1000 users mà không cần replica nếu queries được tune tốt.

   - **Read replica** cho reports + analytics (chỉ khi metric trigger):
     - Setup Railway Postgres replica addon (or Hetzner DIY)
     - Route `/status`, `/today`, `/weekly`, `/report` queries → replica
     - Real-time queries (matcher, state machine) → primary
   - **Connection pooler** (PgBouncer): transaction-mode pooling
     - Reduce idle connection count
     - Reuse trên handler invocations

4. **Optimization tier 3 (~1000-2000 users):**
   - **Partition `transactions` table** by `month_key`
     - Auto-create partition every month (cron)
     - Drop old partitions (Free tier 30-day retention enforce)
   - **Partition `payment_matches`** by year
   - **Materialized views** cho heavy aggregations (monthly_reports)
     - Refresh daily

5. **Optimization tier 4 (2000+):**
   - Consider **Citus** (Postgres horizontal scaling) — defer, evaluate alternatives first
   - Or migrate sang dedicated DB box (Hetzner CCX22)

**Acceptance Criteria:**
- [ ] Tier 1 indexes deployed before launch
- [ ] Monitoring alerts cho 4 metrics threshold
- [ ] Tier 2 spec reviewed when active users > 300
- [ ] Tier 3 spec reviewed when active users > 800

**Effort:** 1 ngày spec, 3-5 ngày dev khi implement (per tier).

---

### C5. Concurrency Audit + Race Conditions 🟡 (Trigger @ 500+)

**Why needed:** Spec assume sequential execution. Ở 500 concurrent users có race condition risks.

**Known race condition surfaces:**

1. **Payment matcher** (đã có row lock trong `confirm_match()` từ payment spec v1.2.0) — verify implementation
2. **State machine concurrent webhooks**:
   - User đang `await_sub` → 2 webhook fire đồng thời cho 2 tx khác nhau
   - Race trên `bot_state.payload`
3. **Categorization concurrent click**:
   - User bấm 2 category button trong 100ms (network jitter)
   - Cả 2 callback xử lý → tx categorized 2 lần
4. **Trial expiry job**:
   - APScheduler trigger trùng nếu instance restart trong 1 phút trước fire
5. **Tier limit check race**:
   - Free user có 44 tx, 2 webhook fire đồng thời → cả 2 pass `count < 45` check → 46 tx inserted
6. **`/upgrade` race**:
   - User bấm upgrade 2 lần → 2 pending_payments created với plan giống → user transfer 1 lần → match cái nào?

**Trigger to write:** Khi reach 200 active users (likely first race condition manifests).
**Trigger to implement:** Audit + fix when reach 500 active users.

**Document scope (write thành `docs/feature-spec-concurrency-audit.md`):**

1. **Audit each multi-step state machine**:
   - List of operations + lock requirements
   - For each: pessimistic lock (`FOR UPDATE`) vs optimistic lock (version column) vs idempotency key

2. **Recommended patterns**:

   - **Pessimistic row lock cho state machine**:
     ```python
     async with db.transaction():
         state = await db.fetch_for_update('bot_state', user_id)
         # mutate state...
     ```
   - **Idempotency keys cho webhook callbacks**:
     - Telegram callback có `callback_query.id` unique
     - SePay/email có dedup_key (đã spec)
     - Insert với `ON CONFLICT DO NOTHING`
   - **Atomic counters**:
     - Free tier tx count: SELECT COUNT() bị race. Use `INSERT ... RETURNING` count, hoặc dedicated counter row với `UPDATE ... WHERE count < 45 RETURNING true`
   - **Advisory locks** cho long-running ops (vd report generation):
     ```python
     await db.execute("SELECT pg_advisory_lock(:lock_id)", lock_id=hash(user_id))
     ```

3. **Test plan**:
   - Concurrency stress test (vd `locust`): 50 user × 10 concurrent action mỗi user
   - Assert no data loss, no duplicate, no state corruption
   - Run ở staging trước mỗi release

**Acceptance Criteria:**
- [ ] All 6 known race surfaces có locking strategy documented
- [ ] Concurrency stress test pass với 100 mock users × 10 concurrent ops
- [ ] No `bot_state` corruption sau test

**Effort:** 2 ngày spec + audit, 3-4 ngày dev fixes + tests.

---

### C6. Production Observability 🟡 (Pre-launch + scale)

**Why needed:** TDD §5.4 list 5 metric nhưng không có dashboard, alert rule, log strategy.

**Trigger to write outline:** Pre-launch (Phase 6).
**Trigger to fully implement:** Phase 7-8 + iterate as scale.

**Document scope:** [`docs/observability-plan.md`](file:///Users/maingocanh/Projects/MyMoneyWent/docs/observability-plan.md)

1. **Metrics to track**

   **System health:**
   - Uptime (Railway built-in + UptimeRobot ping `/health`)
   - Response time p50/p95/p99 cho mỗi endpoint
   - Error rate per endpoint (Sentry)
   - DB connection pool usage
   - Memory RSS, CPU usage

   **Business metrics:**
   - DAU, WAU, MAU
   - Signup rate (per source)
   - Onboarding funnel: signup → first tx → first categorize → day 7 active
   - Conversion: trial → paid, Free → Pro
   - Retention 7-day, 30-day
   - MRR per cohort

   **Per-user health:**
   - Webhook firing rate per user (last 7d)
   - Email parse success rate per user
   - Categorization rate (% tx categorized within 24h)
   - Trial expiry timeline

   **Operational:**
   - Payment match rate (Layer 1 / 2 / 3 / 4 distribution)
   - Unmatched payment queue depth
   - Parser accuracy per bank
   - Postmark email volume vs tier

2. **Dashboards**
   - **Founder daily dashboard** (single HTML page, refresh từ Postgres):
     - DAU, signups today, payments today, errors today, queue depth
   - **Per-user troubleshooter** (admin command `/admin_user`):
     - All metrics for 1 user, last 30 days
   - **Cohort retention** (monthly):
     - Manually export CSV → Sheets/Excel pivot

3. **Alerting**
   - **Critical (PagerDuty / Telegram admin chat with high priority)**:
     - Error rate >10/hour
     - Uptime < 99% over 1 hour
     - DB connection saturation > 90%
     - Bot send queue > 100 pending > 5 min
     - Payment unmatched queue > 20
   - **Warning (Telegram admin chat normal)**:
     - Parser accuracy drop > 5% for any bank
     - Postmark volume > 80% tier limit
     - Daily backup fail
     - Free→Pro conversion drop > 20% week-over-week

4. **Logging**
   - Structured JSON log từ FastAPI
   - Railway logs auto-collected (1-day retention free tier)
   - Forward critical logs sang Sentry
   - Per-user log query qua admin command

5. **Tracing** (defer to 500+ users)
   - OpenTelemetry instrumentation cho slow request investigation
   - Use Sentry Performance hoặc self-host Jaeger

**Acceptance Criteria:**
- [ ] Pre-launch: founder dashboard live + 5 critical alerts armed
- [ ] Phase 8 soft launch: per-user troubleshooter command working
- [ ] 200+ users: parser accuracy auto-monitor + weekly digest
- [ ] 500+ users: tracing instrumentation cho top 5 slow endpoints

**Effort:** 1 ngày outline, 3-5 ngày dev (basic), iterative expand at scale.

---

### C7. Tax / Reconciliation Workflow 🟡 (Trigger @ MRR > $200/mo)

**Why needed:** Khi hit doanh thu ~100tr/năm threshold (BRD risk #9 + payment spec §8.2). Pre-condition là hộ kinh doanh đã đăng ký (skip per scope note — assume done parallel).

**Trigger to write:** Khi MRR > $100/mo (~250 users).
**Trigger to ship:** Khi MRR > $200/mo (~400-500 users).

**Document scope (write thành `docs/feature-spec-tax-reconciliation.md`):**

> **Note**: Spec này chỉ cover **technical workflow** (invoice automation, reconciliation script, monthly summary). Phần **legal entity setup** (đăng ký hộ kinh doanh, mã số thuế) là pre-requisite ngoài scope plan này.

1. **VAT invoice generation**
   - Tích hợp với Misa eInvoice API (hoặc Viettel/FPT eInvoice)
   - Template: invoice per paying transaction (monthly billing cycle)
   - Auto-issue khi `payment_matches.status = 'matched'`
   - Email invoice tới user's inbound email (hoặc `users.invoice_email` field mới)

2. **Monthly reconciliation**
   - Daily cron: pull bank statement (qua API SePay hoặc manual upload CSV)
   - Match với `payment_matches` records
   - Flag discrepancies: bank statement có transfer mà không có match (incoming refund?), match có mà bank không có (false match?)
   - Output: `monthly_reconciliation_{YYYY-MM}.csv` to admin

3. **Tax declaration helper**
   - Monthly summary report: total revenue, refunds, net
   - Format ready cho kế toán dịch vụ submit
   - Include user breakdown for VAT individual invoice tracking

4. **Refund audit trail**
   - Mỗi refund: who, when, amount, original payment, reason
   - Export CSV cho tax review

5. **Schema changes**
   ```sql
   ALTER TABLE users ADD COLUMN invoice_email VARCHAR(128);
   ALTER TABLE users ADD COLUMN tax_id VARCHAR(32);  -- buyer's MST nếu có

   CREATE TABLE invoices (
       id              SERIAL PRIMARY KEY,
       user_id         INT REFERENCES users(id),
       payment_match_id INT REFERENCES payment_matches(id),
       invoice_number  VARCHAR(64) UNIQUE,         -- từ Misa eInvoice
       amount          BIGINT,
       vat_amount      BIGINT DEFAULT 0,           -- 0 nếu hộ KD chưa lên VAT
       issued_at       TIMESTAMPTZ,
       provider        VARCHAR(32),                -- 'misa'|'viettel'|'manual'
       pdf_url         TEXT
   );
   ```

**Acceptance Criteria:**
- [ ] Auto-issue invoice trong < 5 phút sau payment confirmed
- [ ] Monthly reconciliation script chạy + report tới admin
- [ ] Discrepancy < 1% (bank vs match records)
- [ ] Refund audit trail complete

**Effort:** 1 ngày spec, 3-4 ngày dev (assuming Misa eInvoice API có sẵn doc).

---

### C8. Bot Pool Implementation 🟡 (Trigger @ 500+)

**Why needed:** PRD §5.4.2 đã list bot pool roadmap nhưng quá thin. Khi reach 500-700 users với spike traffic, single bot rate limit (30 msg/s) sẽ hit.

**Trigger to write:** Khi reach 300 active users (start planning).
**Trigger to ship:** Khi reach 500-700 users hoặc khi >25 msg/s sustained.

**Document scope (write thành `docs/feature-spec-bot-pool.md`):**

1. **Architecture**
   - Platform tạo 5 bot via @BotFather, store tokens trong env vars `BOT_TOKEN_1` through `BOT_TOKEN_5`
   - DB schema: thêm `users.bot_id INT NOT NULL DEFAULT 1` + `bots(id, token_encrypted, name, active)` table
   - Sticky route: user always routed tới same bot — `bot_id = (user_id % len(active_bots)) + 1`

2. **Migration strategy — GRADUAL COHORT ASSIGNMENT (not force migration)**

   > **Why not force migrate:** Telegram bot không thể move chat history hoặc user relationship sang bot khác. Force `/migrate` command yêu cầu user phải bấm Start bot mới = **major churn point cho consumer SaaS**. Existing users đã invest thời gian vào bot 1 (categorize history, custom categories, settings) — buộc họ chuyển = rủi ro mất user, không phải UX cải thiện.

   **Strategy:**
   - **MVP (single bot)**: tất cả users on `bot_id=1`. Track per-bot send queue depth + rate limit metrics.
   - **Soft expansion (300-500 active users)**: Setup pool 2-3 bots ở backend nhưng **vẫn route 100% new + existing user vào bot 1** until rate limit metrics show pressure.
   - **Cohort split (chỉ khi bot 1 rate limit hit sustained)**:
     - **New users only**: signup links cho bot pool entries (vd `t.me/FinTrackBot` vs `t.me/FinTrackBotV2`). User mới chọn bot khi click landing link → assigned `bot_id` permanent.
     - **Existing users**: stay on bot 1 indefinitely. KHÔNG forced.
   - **Force migration only as last resort**: nếu bot 1 consistently > 28 msg/s sustained 1 week + cannot smooth qua outbound queue → consider partial migration với **opt-in incentive** (vd 1 month free Pro), KHÔNG mandatory.

   **Step-by-step:**

   **Step 1: Setup new bots backend (1 day)**
   - Create 2-4 new bots via @BotFather: `@FinTrackBot2`, etc.
   - Add tokens to Railway env (`BOT_TOKEN_2`, etc.)
   - Create `bots` table, populate

   **Step 2: Deploy code với bot pool support (1 day)**
   - `messenger.send()` resolves `bot_id` từ `users.bot_id` (default = 1)
   - Telegram webhook setup cho mỗi bot riêng `/telegram/webhook/{bot_id}`
   - Outbound queue (C9) per-bot rate limiter

   **Step 3: New cohort assignment (week 2+)**
   - Bot pool entry strategy: marketing landing pages link to different bot URL
   - vd Facebook campaign → `t.me/FinTrackBotV2`, organic → `t.me/FinTrackBot`
   - Round-robin balance qua landing tracking
   - **Existing users vẫn on bot 1, không touch**

   **Step 4: Monitor + react (ongoing)**
   - Track per-bot active user count + send queue depth
   - If bot 1 nearing rate limit → push more new users vào bot 2-N
   - Add bot 6, 7, 8 khi cohort 2-5 đầy

   **Step 5: Last resort partial force-migrate (only if bot 1 consistently > 28 msg/s)**
   - Identify least-active 20% users on bot 1
   - DM với incentive: "Migrate sang @FinTrackBotV2 để nhận 1 month free Pro"
   - Opt-in only, no auto-force

3. **Failure modes**
   - Bot N suspended → mark `bots.active = FALSE`. **NEW** users assigned to active pool. **Existing** users on bot N: notify + `BOT_TOKEN_BACKUP` switchover (PRD §1.4 runbook), KHÔNG force migrate
   - User block bot N → bot send fail → mark user inactive. Don't auto-migrate.
   - Bot N WhatsApp-style API change → graceful degrade, push update notification

4. **Code structure**
   ```python
   # services/bot_pool.py
   class BotPool:
       def __init__(self):
           self.bots = load_bots_from_db()

       def get_bot_for_user(self, user_id: int) -> Bot:
           bot_id = user.bot_id  # already assigned at signup
           return self.bots[bot_id]

       async def send_text(user_id, text):
           bot = self.get_bot_for_user(user_id)
           return await bot.send_message(...)
   ```

**Acceptance Criteria:**
- [ ] 2-5 bots active backend; existing users **NOT forced migrate**
- [ ] New cohort assignment qua landing link work without UX friction
- [ ] Per-bot rate limit < 25 msg/s sustained
- [ ] Failover khi 1 bot suspend < 30 phút (`BOT_TOKEN_BACKUP` switchover, no migration)
- [ ] No churn spike sau bot pool deploy (existing users untouched)

**Effort:** 2 ngày spec, 5-7 ngày dev. Migration period **không cần** vì gradual cohort, không force.

---

### C9. Outbound Queue + Rate Limiter 🟡 (Foundation in Phase 1, full implementation @ 100+)

**Why needed:** PRD §5.4.2 listed but only as "deferred AC". Khi reach 100 users với spike (vd 23:00 daily recap), single send burst có thể hit Telegram rate limit dù còn dưới 30/s.

**FOUNDATION DECISION (Pre-Phase 1):**

Architecture phải prepare từ Phase 1 dù chưa implement queue. Cụ thể: **mọi outbound message đi qua interface `messenger.send(user_id, payload)`** thay vì hardcode `telegram.send_message(chat_id, text)` ở handlers. Initial implementation = direct-send (no queue), nhưng swap sang queue sau **không refactor handlers**.

```python
# services/messenger.py — Phase 1 implementation
class Messenger:
    """Single point of outbound message dispatch.
    Direct-send initially. Swap to queue-backed at 100+ users without handler changes."""

    async def send(self, user_id: int, payload: dict) -> SendResult:
        # Phase 1-6 initial: direct send
        user = await db.fetch_user(user_id)
        bot = self._get_bot_for_user(user)  # single bot ở MVP, bot_pool sau
        return await bot.send_message(chat_id=user.chat_id, **payload)

# Handler usage (everywhere)
# ❌ Bad — hardcoded, refactor pain later:
# await tg.send_text(text, chat_id=user.chat_id)

# ✅ Good — abstracted, swappable:
await messenger.send(user_id, {'type': 'text', 'text': text})
```

**Trigger to write full queue spec:** Khi reach 50 active users.
**Trigger to ship queue impl:** Khi reach 100-150 active users (swap `Messenger.send` internal từ direct → queue).

**Document scope (expand PRD §5.4.2 hoặc thành mini-spec):**

1. **Schema**
   ```sql
   CREATE TABLE outbound_messages (
       id              BIGSERIAL PRIMARY KEY,
       user_id         INT REFERENCES users(id),
       bot_id          INT REFERENCES bots(id),         -- when bot pool exists
       payload         JSONB NOT NULL,                  -- {type, text, reply_markup, ...}
       priority        SMALLINT DEFAULT 5,              -- 1=highest (auth), 9=lowest (broadcast)
       status          VARCHAR(16) DEFAULT 'pending',
                                                        -- 'pending'|'sent'|'failed'|'cancelled'
       attempts        INT DEFAULT 0,
       next_attempt_at TIMESTAMPTZ DEFAULT NOW(),
       sent_at         TIMESTAMPTZ,
       error           TEXT,
       created_at      TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE INDEX idx_outbound_pending ON outbound_messages(next_attempt_at, priority)
       WHERE status = 'pending';
   ```

2. **Worker**
   - Single worker (initially) polls `outbound_messages` mỗi 100ms
   - Token bucket rate limiter: 25/s per bot (buffer dưới 30 limit)
   - Process oldest priority-1 first
   - On send fail: increment attempts, exponential backoff (1s, 5s, 30s, 5min)
   - Max 5 attempts, then mark 'failed' + alert admin

3. **API change**
   ```python
   # Old: direct send
   await tg.send_text(text, chat_id=chat_id)

   # New: enqueue
   await outbound_queue.enqueue(user_id, payload={'type': 'text', 'text': text})
   ```

4. **Spike smoothing for daily_recap**
   - Daily recap fires 22:55-23:05 (jitter ±5 already in spec PRD F09)
   - Each fire enqueues message → worker drains gradually 25/s
   - User receives recap within 1-2 min, không impact perceived latency

**Acceptance Criteria:**
- [ ] Send rate consistent <25/s even when 500 daily_recap fire trong 1 phút
- [ ] No Telegram 429 errors trong stress test (simulate 200 user × 10 msg burst)
- [ ] Failed message logged + admin alerted
- [ ] Priority works (auth message delivers before broadcast)

**Effort:** 1 ngày spec expand, 3-4 ngày dev + test.

---

## 4. Engineering Effort Roadmap

### 4.1. Pre-launch (Phase 1-7 BRD, weeks 1-13)

**Phase 1-2** (refactor): 20-28 days — already specced.

**Phase 3-5** (pricing + onboarding + email parsing): per BRD timeline.

**Phase 6 polish**: thêm các work mới:
- ✅ C2 admin tools spec + dev (1-2 ngày spec, 3-5 ngày dev)
- ✅ C3 disaster recovery runbook write + 1 test (1 ngày + 2 ngày test)
- ✅ C6 observability outline + basic dashboard (1 ngày + 3-5 ngày dev)
- ✅ Payment auto-detect (8-12 ngày, đã spec)

**Total Phase 6 expanded**: 14-20 days vs 10 days original. Has buffer in BRD timeline (tuần 16).

### 4.2. Tier 100-500 users (post-launch tháng 1-9)

| Month | New work | Trigger |
|-------|----------|---------|
| 1-2 (50-100 users) | C9 outbound queue (spec + dev, 4-5 ngày) | Approaching 100 users |
| 3-4 (100-200 users) | C1 support automation spec start | Support time > 5h/week |
| 4-5 (200-300 users) | C1 dev (5-7 ngày) | Before reach 250 users |
| 5-6 (300-400 users) | C5 concurrency audit + fixes (5-7 ngày) | Race condition reports start |
| 6-9 (400-500 users) | C8 bot pool spec + dev (7-9 ngày), C4 DB tier 2 (3-5 ngày) | Approaching 500 users |

### 4.3. Tier 500-2000 users (year 2+)

| Quarter | New work |
|---------|----------|
| Q1 (500-800) | C7 tax workflow (3-4 ngày), Hetzner migration evaluation |
| Q2 (800-1200) | C4 DB tier 3 (partition tables), monitoring expand |
| Q3 (1200-1600) | Hire support 1 part-time, knowledge base expand |
| Q4 (1600-2000+) | Re-architecture planning: bot API self-host, Postgres horizontal scaling |

---

## 5. Operational Readiness Checklist

### 5.1. Pre-launch (must-have day 1)

**Tech:**
- [ ] Phase 1-7 dev complete + tested
- [ ] C2 admin tools shipped
- [ ] C3 disaster recovery runbook written + 1 successful test
- [ ] C6 basic observability + critical alerts armed
- [ ] Backup automation running
- [ ] CI/CD pipeline (GitHub Actions or Railway hook)

**Operational:**
- [ ] Founder familiar với 6 disaster scenarios runbook
- [ ] Admin Telegram chat setup (founder + 1 trusted contact emergency)
- [ ] Status page URL (even if static + manually updated)
- [ ] Privacy policy + ToS published
- [ ] Refund policy text in bot `/help`
- [ ] Beta user welcome message + onboarding email sequence

**Business:**
- [ ] Hộ kinh doanh registered (out of scope, but BLOCKER)
- [ ] Bank accounts dedicated cho subscription (separate từ personal)
- [ ] Postmark account verified + domain DNS configured
- [ ] SePay account configured cho platform's primary bank

### 5.2. 100 users milestone

- [ ] DAU/conversion dashboard active
- [ ] First successful end-to-end recovery test passed
- [ ] Per-user troubleshooter command working
- [ ] Support response time tracked, average <12h

### 5.3. 250 users milestone

- [ ] C1 support automation deployed (FAQ + self-serve)
- [ ] C9 outbound queue running
- [ ] Founder support time <15h/week
- [ ] Tax accountant relationship established (parallel với scope-out item)

### 5.4. 500 users milestone

- [ ] C8 bot pool plan finalized (start migration)
- [ ] C5 concurrency audit complete + fixes deployed
- [ ] C4 DB scaling tier 2 implemented (read replica setup if needed)
- [ ] C6 observability tracing instrumented
- [ ] Hire decision: support hire vs pure automation push

### 5.5. 1000 users milestone

- [ ] Bot pool 5 bots stable
- [ ] Hetzner migration complete (if Railway bill > $50/mo)
- [ ] C4 DB tier 3 (partitioning) implemented
- [ ] Annual recurring revenue > $500/mo
- [ ] Plan re-architecture cho 2000+ users

---

## 5b. Deferred items — REMINDER list

Track items đã decided defer, set milestone re-evaluate:

| # | Item | Defer reason | Re-evaluate trigger |
|---|------|--------------|---------------------|
| D1 | `daily_metrics` rollup job (observability §8) | Premature — analytics_events query đủ fast pre-launch | Dashboard query >1s sustained, hoặc 100+ users milestone, hoặc analytics_events >10M rows |
| D2 | PDPA breach plan runbook (`docs/runbooks/pdpa-breach.md`) | No incident yet, MVP user count nhỏ | ≥200 users milestone hoặc any breach incident (whichever first) |

**Action**: trước mỗi monthly review, check trigger conditions. Nếu hit → schedule spec writing trong sprint kế tiếp.

---

## 6. Risk Register — Scale Risks

| # | Risk | Trigger scale | Mitigation |
|---|------|---------------|------------|
| R1 | Solo founder support burnout | 200+ | C1 ship trước 250 users; consider hire 300+ |
| R2 | Telegram rate limit cause message loss | 500+ | C9 outbound queue + C8 bot pool |
| R3 | DB query slow → user perceived latency | 500+ | C4 read replica + indexes |
| R4 | Race condition data corruption | 500+ | C5 audit + locking |
| R5 | Postmark cost spike (heavy email user) | 1000+ | Tier negotiation + parser efficiency |
| R6 | Bot N suspension → service disruption | Anytime | BOT_TOKEN_BACKUP + bot pool resilience |
| R7 | Database disk full | 1500+ | Tier 3 partitioning + archive policy |
| R8 | Tax audit catches non-compliance | MRR>200 | Out-of-scope hộ KD setup + C7 reconciliation |
| R9 | Single founder unavailable (illness) | Anytime | Emergency runbook shared với trusted contact (C3 §F) |
| R10 | Customer churn spike | Anytime | Observability funnel + retention experiments |

---

## 7. Open Questions

Cần resolve cùng founder trước khi execute:

1. **Hire vs full-automate cho support ở 300+ users?**
   - Hire 1 part-time: $300-500/mo, scale linear
   - Pure automation: 1-time cost dev, scale infinite
   - Recommendation: Hybrid — automate tier 1, hire tier 2 khi MRR > $500

2. **Bot pool: 5 bots vs auto-scale?**
   - 5 bots fixed simpler, manual rebalance
   - Auto-scale (spawn bot khi queue depth high) flexible but complex
   - Recommendation: Start với 2 bots, manually expand to 5 khi need

3. **Hetzner migration: when exact?**
   - BRD trigger: Railway bill > $30/mo for 2 months
   - But migration costs 1 week dev time
   - Recommendation: skip until > $50/mo to avoid premature optimization

4. **Knowledge base: in-bot only vs web?**
   - In-bot: simpler, 1 channel
   - Web: SEO benefit, accessible without bot
   - Recommendation: Web from day 1 for SEO marketing benefit

5. **Tax accountant relationship: monthly retainer vs per-job?**
   - Monthly retainer 500k-1tr/tháng
   - Per-job ~200k/declaration
   - Recommendation: Monthly khi MRR > $300 (~3-4 declarations/year)

6. **Beta vs gradual rollout?**
   - Closed beta 5-10 users → soft launch 30 → public
   - Recommendation: Stick với BRD timeline (Phase 7 closed beta, Phase 8 soft launch)

7. **Re-architecture trigger cho 2000+?**
   - MRR threshold? User count? Latency?
   - Recommendation: Start planning at 1000 active users, decide details based on actual bottleneck profile

---

## 8. Cross-doc Updates Needed

Khi spec mới được viết, cập nhật cross-ref:

| Source spec | Files to update |
|-------------|-----------------|
| C1 support-automation | PRD §F (add F11 Support), README quick links, BRD §10 success criteria |
| C2 admin-tools | TDD §3 endpoints, payment spec §10.7, README |
| C3 disaster-recovery | TDD §5.3 backup, BRD §10 + §7 risks, README |
| C4 db-scaling | TDD §8 performance, PRD §5.4.1, README |
| C5 concurrency | TDD §6 security, all relevant feature specs, refactor spec §3 AC |
| C6 observability | TDD §5.4 monitoring, README, BRD §10 |
| C7 tax-reconciliation | TDD §2.1 schema, payment spec §8, BRD §5.2.4 |
| C8 bot-pool | PRD §1.4 bot ownership, PRD §5.4.2, refactor spec, TDD §3 |
| C9 outbound-queue | PRD §5.4.2 expand, TDD §3, all handler specs |

---

## 9. Summary — Next Actions

**Pre-Phase 1 (week 0 — week này, BEFORE dev start):**
1. ✅ Read this plan với founder, agree priorities
2. **Write C2 admin tools spec FIRST** (1-2 ngày) — vì impact schema/auth từ Phase 1. KHÔNG defer.
3. Write **C3 disaster recovery runbook** (1 ngày)
4. Write **C6 observability outline** (1 ngày)
5. Update refactor spec với messenger interface foundation (đã done v1.2.0)

**Tuần 1-2 (Phase 1 foundation):**
6. Implement DB schema **including `admin_audit_log`** (initial migration)
7. Implement `services/messenger.py` interface (direct-send initial impl)
8. Implement `services/admin.py` auth framework
9. Resolve open questions §7 (support model, bot pool count, etc.)
10. Setup CI/CD pipeline
11. Setup staging environment

**Tuần 3-4 (Phase 2 handlers):**
12. Refactor handlers: tất cả outbound đi qua `messenger.send()` — verify grep test
13. Admin command framework available (commands implement Phase 6)

**Sau Phase 6 deploy (~tuần 12):**
14. Verify admin commands work end-to-end
15. Test C3 disaster recovery (1 successful restore)
16. Verify C6 observability tất cả critical alerts armed

**Sau Phase 8 launch:**
17. Monitor active users count, trigger spec writing per §4.2 schedule
18. C9 swap direct-send → queue khi reach 100-150 users (no handler refactor needed)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|---------|
| v1.0.0 | 2026-05-05 | Initial plan — 7 spec gaps + 2 expand existing, 11-13 ngày spec writing + ~30-43 ngày dev work, scale roadmap from MVP (100 users) to 2000+. Excludes hộ kinh doanh registration (handled parallel). |
| v1.1.0 | 2026-05-06 | **Round-1 review fixes:** (1) **Phase 6 timeline expand** trong BRD reflected: tuần 10-11 → 10-12 (Phase 7-8 dịch tới 13-14, 15-16; tổng 16 tuần giữ nguyên). (2) **C2 admin tools = spec-FIRST**: write trước Phase 1 dev vì schema/auth impact từ ngày 1. Thêm DDL `admin_audit_log` + auth framework `ADMIN_TELEGRAM_IDS` (plural) + `@admin_only` decorator vào C2 spec scope + refactor spec §4.1 + Phase 1.2 sub-tasks. (3) **C9 messenger interface foundation**: thêm yêu cầu `messenger.send(user_id, payload)` interface ở Phase 1, initial direct-send impl, swap sang queue sau không refactor handlers. Update refactor spec §2.2 + §3.3 AC. (4) **C8 bot pool — gradual cohort assignment**: rewrite migration strategy bỏ force-migrate (Telegram bot không move user relationship được, force = churn). New cohorts assigned via landing link, existing users stay on bot 1. Force chỉ là last resort với opt-in incentive. (5) **C4 read replica metric-triggered**: clarify đừng deploy ở 500 users by default — chỉ khi metric (CPU, pool saturation, slow query) hit threshold. (6) Wording §1.1 + §2.1 safer: "đủ start Phase 1 foundation" thay vì "đủ launch MVP". (7) Date 2026-05-05 → 2026-05-06. |
| v1.2.0 | 2026-05-06 | **Round-3 review fixes (Q1-Q8 decisions):** (1) Q1+Q2 admin tools: rate limit 30/min default + configurable, /admin_help hybrid auto-generate + manual intro — applied to feature-spec-admin-tools v1.1.0. (2) Q3 DR scenarios G (SePay outage) + H (abuse/spam) — added to disaster-recovery v1.1.0. (3) Q4 @FinTrackUpdates channel confirmed pre-launch action item. (4) Q5 error budget 0.1% với 3-tier policy — added observability v1.1.0 §4b. (5) Q6 cost monitoring dashboard với /admin_cost command — added observability §4.3. (6) Q7 daily_metrics rollup deferred → tracked in §5b new. (7) Q8 PDPA breach plan deferred → tracked in §5b new. New §5b "Deferred items REMINDER list" section. |
| v1.3.0 | 2026-05-07 | **C10 Channel adapter + Messenger MVP build (sync feature-spec-messenger-channel v1.1.1 + impl plan VietQR+email v1.0.0):** (1) §1.2 critical gaps thêm **C10 — channel adapter pattern + Messenger MVP build** (foundation + code ship MVP, public flag-gated sau Meta App Review), trigger pre-launch MVP, spec done, 10 ngày dev Messenger build (Phase 6 Tuần 10-11) + **3-5 ngày VietQR/email parallel** (integration/test surface, không phải 2 ngày). (2) §1.3 phasing principle thêm C10 vào foundation specs PHẢI write trước Phase 1 dev — `services/channels/{base,telegram,messenger}.py` adapter pattern, schema `users.channel_type` + `channel_user_id` thay `telegram_id UNIQUE`. (3) §1.3 timeline phasing thêm steps cho Phase 1-6 (implement Telegram adapter foundation), Phase 6 Tuần 10-11 (Messenger adapter + App Review submit parallel), Phase 7-8 (validate parity nếu review approved, Telegram-only nếu chưa). (4) §1.3 note: C8 bot pool Phase 7-9 chỉ apply Telegram (Messenger có Meta tự throttle). (5) Total work: 30-43 → **43-58 ngày dev** (thêm 13-15 ngày Messenger + VietQR). (6) Header refs bumped BRD v2.8.0 → v2.9.0, PRD v1.5.0 → v1.6.0, TDD v1.5.2 → v1.6.0; thêm Messenger Spec + Impl Plan VietQR refs. |
| v1.4.0 | 2026-05-07 | **C11 Landing/Privacy/Terms + C12 Web Dashboard (sync decision-onboarding-ui-strategy v1.0.1):** (1) §1.2 critical gaps thêm **C11 — Landing page + Privacy policy + Terms** (pre-launch operational item, ~3 ngày dev Phase 7, required cho Meta App Review + PDPA Vietnam compliance) + **C12 — Web dashboard read-only reports** (trigger-based defer, 5-10 ngày dev khi MRR >$300/mo + user feedback >30% request). (2) §1.3 phasing thêm Phase 7-8 ship C11 (chat-only onboarding decision, KHÔNG build web form) + tháng 10-12 trigger evaluation cho C12. (3) Total work: 43-58 → **46-65 ngày dev** (thêm 3 ngày landing/privacy + 5-10 ngày dashboard if triggered). (4) Cross-link tới decision-onboarding-ui-strategy.md cho rationale chat vs web. |
