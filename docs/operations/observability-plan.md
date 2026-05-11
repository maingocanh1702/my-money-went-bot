# Observability Plan — Production Monitoring & Alerts

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-06
> **Trạng thái:** Draft
> **Owner:** Founder (dev/ops)
> **Phase liên quan:** Phase 6 deploy readiness + Phase 7 beta monitoring + scale to 500 users
> **Tham chiếu:** [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.7.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [TDD-vi v1.8.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) · [Implementation Plan 500+ v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-500-users-and-more.md)

---

## 1. Goals

Observability must answer 5 questions quickly:

1. Is the bot alive?
2. Are users receiving messages?
3. Are transactions/payments being processed correctly?
4. Which user/bank/source is failing?
5. Is the business funnel healthy enough to continue scaling?

MVP observability should be simple and founder-operable: Railway metrics + Sentry + Postgres analytics + Telegram admin alerts.

---

## 2. Signals

### 2.1. System health

| Signal | Source | Target / Alert |
|---|---|---|
| `/health` uptime | UptimeRobot/Railway | alert if down >2 min |
| Webhook response p95 | app metrics/logs | warning >500ms, critical >2s |
| Bot reply latency p95 | analytics event timestamps | warning >2s |
| Error count | Sentry | critical >10 errors/hour |
| Memory RSS | Railway | warning >80% plan limit |
| CPU | Railway | warning sustained >80% for 15m |
| DB pool usage | app metric | warning >80%, critical >90% |
| DB slow query | app log/pg_stat_statements | warning >100ms common query |
| **SePay webhook delivery** | rolling 1h count of `/hook/{user_token}` hits vs baseline | alert if drop >50% (SePay outage hoặc network issue) |
| **PLATFORM_TOKEN webhook silence** | last event timestamp on `/hook/{PLATFORM_TOKEN}` | **CRITICAL** alert if no events 24h (platform bank disconnected from SePay = revenue blind) |
| **Postmark API health** | Postmark status API ping + last inbound timestamp | warning if no inbound 6h despite known active forwarders |
| **B2 backup reachability** | nightly upload result | critical if 2 consecutive nights fail |

### 2.2. Transaction pipeline

| Signal | Event / Query | Target |
|---|---|---|
| `tx_received` count | analytics_events | stable by active user count |
| `tx_categorized` latency | `tx_categorized - tx_received` | p75 <24h |
| Categorization rate | categorized / received | >70% active users |
| Dedup skip count | internal metric | watch spikes |
| Invalid token hits | logs | alert if spike (probing) |
| Stale tx skipped | logs/events | watch by source |

### 2.3. Email parser health

| Signal | Target / Alert |
|---|---|
| Parser accuracy per bank | ≥85%; alert if drop >5% WoW |
| `email_parse_fail` by bank | warning if >15% daily |
| Unparsed email queue | warning >20 pending |
| Postmark volume | warning at 80% tier limit |
| Postmark webhook errors | critical if sustained >10m |

### 2.4. Payment health

| Signal | Target / Alert |
|---|---|
| Layer 1 match rate | ≥95% of transfers |
| Layer 4 manual review | ≤5% of transfers |
| Unmatched payment queue | warning >5, critical >20 |
| Payment confirmation latency | SePay p95 ≤60s; email p95 ≤5m |
| Refund count | monitor weekly |
| Duplicate payment events | alert if spike |

### 2.5. Business funnel

| Signal | Target / Notes |
|---|---|
| Signups/day | GTM dependent |
| Onboarding completion | ≥80% one session |
| First transaction received | core activation |
| Trial day 1/7/14 retention | detect weak onboarding |
| Free limit hit rate | 40-60% target |
| Trial → paid conversion | ≥8-10% after beta |
| MRR | target $150-450 at 12 months |
| Churn | track monthly, target <7% |

---

## 3. Analytics Events

Canonical events are defined in PRD §6. Minimum MVP implementation:

### 3.1. User lifecycle

- `user_signup_success`
- `user_onboard_path_selected`
- `user_onboard_completed`
- `command_used`

### 3.2. Transaction/email

- `tx_received`
- `tx_categorized`
- `tx_skipped`
- `email_parse_success`
- `email_parse_fail`
- `tx_limit_hit`

### 3.3. Payment/subscription

- `payment_initiated`
- `payment_matched`
- `payment_expired`
- `payment_unmatched`
- `payment_refunded`
- `subscription_renewed`
- `subscription_expired_grace`
- `subscription_downgraded`

### 3.4. Admin/ops

Admin actions are canonical in `admin_audit_log`; optionally mirror summary metrics:

- `admin_command_executed`
- `admin_command_denied`
- `admin_manual_payment_resolved`

---

## 4. Dashboards

### 4.1. Founder daily dashboard

MVP: FastAPI route `/admin/stats` or Telegram `/admin_stats` output.

Must show:

```text
📊 Tiền Về Nơi Đâu — Today
Users: 34 total · 12 DAU · +3 signup
Tx: 82 received · 54 categorized · 66% categorized
Email: 41 parsed · 4 failed · parser fail 8.9%
Payments: 2 initiated · 2 matched · 0 unmatched
Errors: 1 Sentry · 0 critical
Queues: outbound 0 · unmatched payments 0 · unparsed emails 4
Infra: DB pool 30% · p95 webhook 140ms
```

### 4.2. Per-user troubleshooter

Command: `/admin_user {user_id}`

Show:

- plan/trial/expiry/grace
- onboarding path/status
- bank_connections
- inbound email
- last 10 tx
- parser failures for user
- payment pending/matches
- bot_state step
- last 20 analytics events

### 4.3. Cost dashboard

Track unit economics health: infrastructure cost vs MRR. Critical cho decide khi nào migrate Hetzner (BRD §5.5 trigger), khi nào upgrade Postmark tier, etc.

**Metrics weekly tracked**:

| Metric | Source | Target / Alert |
|---|---|---|
| Railway monthly bill | Railway billing API hoặc manual log | Trigger Hetzner migration evaluation nếu >$50/mo sustained 2 tháng |
| Postmark monthly bill | Postmark dashboard | Alert nếu volume >80% tier limit (upgrade tier hoặc optimize parser efficiency) |
| Backblaze B2 cost | B2 dashboard | Stable <$2/mo expected |
| Domain + misc | Manual log | $1-2/mo |
| **Total infra cost** | Sum | Compare với MRR |
| **Cost per active user** | infra / DAU | Track trend, target <$0.30 ở 100+ users |
| **Margin %** | (MRR - infra) / MRR | >70% target ở 200+ users (BRD §5.4.3) |

**Display** (admin command `/admin_cost` hoặc weekly review):
```text
💰 Cost & Margin — Week ending YYYY-MM-DD

Infra:
  Railway:   $14.20  (+$2 WoW)
  Postmark:  $10.00
  B2:        $1.10
  Domain:    $1.00
  TOTAL:     $26.30/mo

Revenue:
  Active paid:  18 users (12 Pro + 3 Business + 3 trial)
  Gross MRR:    $75
  After fees:   $73 (PayPal mix)

Margin:        +$46.70/mo (62%)
Cost/active:   $0.26/user (good)

Trigger watch:
  Railway $30/mo trigger: 47% (safe)
  Postmark 10k tier:    62% used (safe)
```

**Alerts**:
- Cost > 1.5x previous month → investigate (stale traffic? attack? bug?)
- Margin < 50% sustained 2 weeks → strategic review

**Effort**: 1 ngày dev cho admin command + 0.5 ngày cho automated weekly digest.

### 4.4. Weekly founder review

Manual export is fine for MVP.

Metrics:

- signup → first tx conversion
- first tx → categorized conversion
- trial day 7 retention
- payment conversion
- parser accuracy by bank
- support tickets/unmatched queue

---

## 4b. Error Budget

**Definition**: chấp nhận **0.1% error rate** trên total request volume (excludes user-input errors như invalid command).

**Calculation** (rolling 30-day window):
```
error_rate = errors_5xx / total_requests
budget_remaining = 0.001 - error_rate  (positive = healthy)
```

**Policy khi budget exhausted**:

| Budget state | Action |
|---|---|
| `>50%` remaining (error rate <0.05%) | ✅ Ship features normally |
| `0-50%` remaining (error rate 0.05-0.1%) | ⚠️ Slow down: review every PR for stability impact, prioritize bug fixes |
| `<0%` (error rate >0.1%) | 🛑 **Freeze new features** until error rate recovers. Focus 100% trên reliability work |

**Why 0.1%**: industry standard cho consumer SaaS B2C. Stricter (vd 0.01%) phù hợp với fintech/payment chỗ regulator quan trọng — có thể tighten sau khi reach 500 users + có legal entity.

**Reset**: budget resets monthly trên rolling 30-day window. Major incident có thể single-handedly burn budget — đó là expected, đó là protect mechanism.

**Implementation**:
- `/admin_stats` show current error rate + budget remaining
- Critical alert §5.1: budget < 20% → notification (gentle warning before freeze trigger)

---

## 5. Alerting

### 5.1. Critical alerts

Destination: Telegram admin chat + Sentry email.

| Alert | Threshold |
|---|---|
| App down | `/health` down >2 min |
| Error burst | Sentry >10 errors/hour |
| DB pool critical | >90% for 5 min |
| Payment unmatched queue | >20 pending |
| Bot send failures | >20 failed sends in 10 min |
| Daily backup failed | no successful backup in 26h |
| Parser total failure | any MVP bank parse success = 0 for 24h while emails received |

### 5.2. Warning alerts

Destination: Telegram admin chat normal priority.

| Alert | Threshold |
|---|---|
| Parser accuracy drop | >5% WoW drop per bank |
| Postmark volume | >80% tier |
| Webhook p95 slow | >500ms for 15m |
| Payment Layer 1 rate low | <90% over rolling 20 payments |
| Support queue high | >10 open support items |
| Free→Pro conversion drop | >20% WoW after 100 users |

---

## 6. Logging

### 6.1. Structured JSON logs

Every request/job log should include:

```json
{
  "ts": "2026-05-06T08:00:00Z",
  "level": "info",
  "event": "tx_received",
  "request_id": "...",
  "user_id": 123,
  "source": "sepay",
  "duration_ms": 120
}
```

### 6.2. Redaction rules

Never log:

- BOT_TOKEN
- PLATFORM_TOKEN
- full webhook_token
- full inbound email token if sensitive
- bank account numbers
- raw email bodies unless debug mode in staging

Allowed:

- token last 4 chars
- amount
- source bank id
- normalized description **first 60 chars + sha256 hash của full description** (cho trace mà không leak vendor/recipient name)

**Sensitive in tx descriptions:** bank transfer description thường chứa tên người nhận, mã đơn hàng, số tài khoản. Production logs phải:
- Truncate < 60 chars
- Hash full description với sha256 (debug parser issue qua hash match)
- Raw description chỉ trong staging với `LOG_SENSITIVE=1` env, never production

### 6.3. Sentry

Capture:

- unhandled exceptions
- payment matcher failures
- parser exceptions by bank
- Telegram send failures after retry exhausted
- scheduled job failures

Sentry tags:

- `user_id`
- `source`
- `bank`
- `job_type`
- `plan`

---

## 7. Health Endpoints

### 7.1. `/health`

Public-ish monitoring endpoint. No sensitive data.

**HTTP status convention** (quan trọng cho UptimeRobot/Pingdom — chúng parse status code, không parse JSON body):
- `200 OK` — all dependencies healthy
- `503 Service Unavailable` — DB down hoặc critical dependency fail
- KHÔNG return `200` với `"ok": false` — monitoring tool sẽ miss

```json
// 200 OK — healthy
{
  "ok": true,
  "app": "fintrack",
  "version": "...",
  "db": "ok",
  "uptime_sec": 12345
}

// 503 — DB unreachable
{
  "ok": false,
  "app": "fintrack",
  "db": "fail",
  "error": "connection timeout"
}
```

### 7.2. `/admin_health`

Admin command, not public.

Checks:

- DB connection
- Postmark config present
- Telegram send test disabled by default but available
- B2 backup last success
- outbound queue depth
- unmatched payment queue depth
- parser failure rate last 24h

---

## 8. Storage & Queries

Use `analytics_events` for product/ops events.

Required indexes:

```sql
CREATE INDEX idx_analytics_event ON analytics_events(event_name, created_at);
CREATE INDEX idx_analytics_user_time ON analytics_events(user_id, created_at DESC);
```

For frequent dashboard queries, add materialized/daily rollup later:

```sql
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    signups INT,
    dau INT,
    tx_received INT,
    tx_categorized INT,
    payments_matched INT,
    parser_failures INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Not required pre-launch unless dashboard queries get slow.

> **DEFERRED — TODO REMINDER**: Scheduled job spec để populate `daily_metrics` (cron 00:30 daily, aggregate prior day analytics_events) chưa viết. Defer to khi:
> - Dashboard query >1s sustained, hoặc
> - `analytics_events` table > 10M rows
> Whichever first. Estimate khi viết: 0.5 ngày spec + 0.5 ngày dev. Re-evaluate ở 100+ users milestone (per implementation plan §5).

---

## 9. Launch Readiness Checklist

Pre-paid beta:

- [ ] Sentry project configured
- [ ] `/health` endpoint live
- [ ] Uptime monitor configured
- [ ] `/admin_stats` command works
- [ ] `/admin_user {user_id}` troubleshooter works minimally
- [ ] Critical alerts route to admin Telegram chat
- [ ] Daily backup failure alert exists
- [ ] Payment unmatched queue alert exists
- [ ] Parser failure alert exists
- [ ] Logs redact tokens/secrets

Phase 8 soft launch:

- [ ] Founder daily dashboard working
- [ ] Parser accuracy by bank visible
- [ ] Payment layer distribution visible
- [ ] Trial/onboarding funnel visible

100+ users:

- [ ] Outbound queue depth visible
- [ ] Support queue metrics visible
- [ ] Weekly digest auto-generated

500+ users:

- [ ] tracing/performance instrumentation for top slow endpoints
- [ ] DB slow query dashboard
- [ ] per-bot metrics if bot pool exists

---

## 10. Weekly Review Template

```md
# Weekly Tiền Về Nơi Đâu Ops Review — YYYY-MM-DD

## Health
- Uptime:
- Error count:
- DB pool max:
- Backup status:

## Funnel
- Signups:
- Onboarding completion:
- First tx rate:
- Trial → paid:
- MRR:

## Product quality
- Tx received:
- Categorization rate:
- Parser accuracy by bank:
- Payment match Layer 1/2/3/4:

## Support
- Tickets/unmatched:
- Avg response time:
- Top 3 issues:

## Decisions needed
1.
2.
3.
```

---

## 11. Effort Estimate

| Work | Effort |
|---|---:|
| `/health` + basic structured logging | 0.5-1 day |
| Sentry integration + tags | 0.5 day |
| Analytics event helper + key events | 1 day |
| `/admin_stats` + `/admin_health` | 1 day |
| Alerts to admin Telegram chat | 1 day |
| Dashboard query polish | 1 day |
| **Total MVP** | **3-5 dev days** |

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-06 | Initial observability plan — signals, dashboards, alerts, logging, health endpoints, launch checklist. |
| v1.0.1 | 2026-05-06 | **Review fixes:** (1) §2.1 thêm 4 dependency health signals: SePay webhook delivery rate, **PLATFORM_TOKEN webhook silence (CRITICAL alert if 24h zero)**, Postmark API health, B2 backup reachability. (2) §6.2 redaction: tx description phải truncate <60 char + sha256 hash full description (chứa vendor/recipient sensitive). (3) §7.1 `/health` endpoint: return **HTTP 503** khi DB down, không phải 200 với `ok:false` (UptimeRobot/Pingdom parse status code). |
| v1.1.0 | 2026-05-06 | **Round-2 fixes (Q5 + Q6 + Q7 from review):** (1) **§4b Error budget mới**: 0.1% error rate target (rolling 30-day), policy 3 tier (>50% remaining ship features / 0-50% slow down / <0% freeze new features). Implementation `/admin_stats` show budget. (2) **§4.3 Cost dashboard mới**: track Railway + Postmark + B2 cost vs MRR, cost-per-active-user, margin %. Triggers cho Hetzner migration + Postmark tier upgrade. Admin command `/admin_cost`. (3) §8 `daily_metrics` rollup job: **DEFERRED TODO marker** — re-evaluate ở 100+ users milestone hoặc khi dashboard query >1s sustained. |
