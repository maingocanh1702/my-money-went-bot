# Runbook — Disaster Recovery

> **Version:** v1.2.0
> **Ngày tạo:** 2026-05-06
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (ops)
> **Applies to:** MyMoneyWent / Tiền Về Nơi Đâu MVP through 500 users
> **Tham chiếu:** [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [TDD-vi v1.8.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) · [Implementation Plan 500+](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-500-users-and-more.md) · [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) · [Impl Plan VietQR+Email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md)

---

## 1. Purpose

This runbook defines how to recover from production incidents without improvising under stress.

MVP recovery targets:

| Scenario | RTO | RPO |
|---|---:|---:|
| Postgres data corruption | 2h | 24h |
| Railway full outage | 4h | 24h |
| BOT_TOKEN compromised | 5m | 0 |
| Telegram bot suspended | 30m target / 5m technical switchover if backup bot ready | 0 |
| Postmark outage | Depends provider; user notification within 30m | delayed emails |
| Founder unavailable | 24h degraded ops | 0-24h |

Definitions:

- **RTO**: maximum acceptable recovery time.
- **RPO**: maximum acceptable data loss window.

---

## 2. Backup Setup

### 2.1. Daily Postgres dump

Run daily at `03:00 UTC`:

```bash
# Main schema + data
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl \
  --file="backup_$(date -u +%Y%m%dT%H%M%SZ).dump"

# Globals (roles, perms) — needed if recreate cluster from scratch
pg_dumpall "$DATABASE_URL" --globals-only \
  --file="globals_$(date -u +%Y%m%dT%H%M%SZ).sql"
```

Upload to Backblaze B2 (server-side encryption SSE-B2 enabled at bucket level):

```bash
b2 bucket update fintrack-backups --default-encryption=SSE-B2  # one-time setup
b2 file upload fintrack-backups backup_YYYYMMDDTHHMMSSZ.dump \
  postgres/daily/backup_YYYYMMDDTHHMMSSZ.dump
b2 file upload fintrack-backups globals_YYYYMMDDTHHMMSSZ.sql \
  postgres/daily/globals_YYYYMMDDTHHMMSSZ.sql
```

Retention:

- Daily backups: 30 days
- Monthly backups: 12 months once revenue starts
- B2 bucket versioning: enabled
- B2 bucket encryption: SSE-B2 server-side (verify với `b2 bucket get fintrack-backups`)

### 2.2. Integrity verification

Weekly:

```bash
pg_restore --list backup_latest.dump > /tmp/backup_list.txt
```

Spot check backup contains critical tables:

- `users`
- `transactions`
- `pending_payments`
- `payment_matches`
- `unmatched_payments`
- `admin_audit_log`
- `analytics_events`

### 2.3. Recovery test schedule

| Frequency | Test |
|---|---|
| Monthly | Download latest B2 backup + parse list |
| Quarterly | Full restore to staging + smoke test |
| Before beta launch | Mandatory full restore test |
| Before major release | Restore test if schema changed |

---

## 3. Scenario A — Postgres Data Corruption

Examples:

- bad migration corrupts data
- accidental destructive query
- app bug writes wrong rows

### Steps

1. **Freeze writes**
   - Stop Railway app or set maintenance flag.
   - Disable scheduled jobs if separate worker exists.

2. **Snapshot current DB** even if corrupt

```bash
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl \
  --file="corrupt_snapshot_$(date -u +%Y%m%dT%H%M%SZ).dump"
```

3. **Create fresh Postgres**
   - Railway → create new Postgres service/addon.
   - Copy new `DATABASE_URL`.

4. **Restore latest good backup**

```bash
pg_restore --clean --if-exists --no-owner --no-acl \
  --dbname="$NEW_DATABASE_URL" backup_latest.dump
```

5. **Run smoke queries**

```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM transactions;
SELECT COUNT(*) FROM payment_matches;
SELECT * FROM users ORDER BY created_at DESC LIMIT 5;
```

5b. **Refresh planner statistics** (post-restore stats stale → query plans tệ):

```sql
VACUUM ANALYZE;
```

6. **Point app to restored DB**
   - Update Railway `DATABASE_URL`.
   - Restart app.

7. **Smoke test app**
   - `/health`
   - test Telegram `/status` with founder account
   - test one staging webhook if safe

8. **Communicate**
   - If user impact >15m, send in-bot incident update.

### Success criteria

- App boots with restored DB.
- Founder account can run `/status`.
- Payment state consistent enough: no duplicate active paid plan for same user.

---

## 4. Scenario B — Railway Full Outage

Examples:

- Railway app/DB unavailable region-wide
- Railway billing/platform incident

### Prepared assets

- Dockerfile works locally
- `docker-compose.prod.yml` template exists
- DNS access for `api.tienvenoidau.com`
- B2 backup credentials available
- Hetzner account ready or can be provisioned quickly

### Steps

1. **Confirm outage**
   - Railway status page
   - `/health` unavailable
   - DB unreachable

2. **Provision Hetzner Singapore VM**
   - Recommended: CPX21 or higher for emergency.
   - Install Docker + Docker Compose.

3. **Deploy app**

```bash
git clone <repo>
cd MyMoneyWent
cp .env.production.example .env
# fill BOT_TOKEN, DATABASE_URL, POSTMARK, B2, PLATFORM_TOKEN

docker compose -f docker-compose.prod.yml up -d
```

4. **Restore DB**
   - Create Postgres container or managed DB.
   - Restore latest B2 backup.

5. **Update DNS**
   - `api.tienvenoidau.com` A record → Hetzner IP
   - Low TTL recommended pre-launch: 300s

6. **Reset Telegram webhook**

```bash
curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
  -d "url=https://api.tienvenoidau.com/telegram/webhook"
```

7. **Verify**
   - `/health`
   - Telegram `/status`
   - Postmark inbound test

### Success criteria

- App responds from Hetzner.
- Telegram updates arrive.
- DB restored within RPO.

---

## 5. Scenario C — BOT_TOKEN Compromised

Signals:

- unexplained messages from bot
- token appears in logs/repo
- Telegram API called from unknown IPs

### Steps

1. **Revoke token** via @BotFather
   - `/revoke` or regenerate token for bot.

2. **Update secrets**
   - Railway `BOT_TOKEN=<new token>`
   - Remove leaked token from any logs/config.

3. **Restart app**

4. **Set webhook again**

```bash
curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
  -d "url=https://api.tienvenoidau.com/telegram/webhook"
```

5. **Audit**
   - Search logs for suspicious outbound sends.
   - Rotate `BOT_TOKEN_BACKUP` if it might also be exposed.

6. **Communicate if needed**
   - If user data exposure suspected, follow PDPA breach plan.

### Success criteria

- Old token no longer works.
- Bot receives updates with new token.
- No data loss.

---

## 6. Scenario D — Telegram Bot Suspended

Signals:

- Telegram API returns bot disabled/suspended
- users report bot missing/unavailable

### Steps

1. **Confirm API error**

2. **Switch to backup bot**
   - Update `BOT_TOKEN=BOT_TOKEN_BACKUP`
   - Update bot username/link in config if needed
   - Set webhook for backup bot

3. **Notify users — MVP CONSTRAINT**
   - Problem: old bot cannot message if suspended.
   - **MVP không có email/SMS contact list** (privacy by design). Available channels:
     - **Landing page** (status banner)
     - **Status page** (manually updated)
     - **Social media** (founder Twitter/Facebook nếu maintained)
     - **`@FinTrackUpdates` Telegram channel** ✅ (created pre-launch, xem §10)
   - In-app notification chỉ reach users sau khi họ Start backup bot — KHÔNG có cách push nếu user không quay lại.
   - **Push announcement đến `@FinTrackUpdates`** sẽ reach mọi user đã subscribe channel — đây là primary out-of-band notification path.

4. **Update public links**
   - landing page CTA
   - README/internal config
   - support docs

5. **Appeal/investigate**
   - Review spam/abuse patterns.
   - Rate limits/outbound queue status.

### Important constraint

Telegram does **not** move users from one bot to another automatically. Backup bot switchover is technically fast but UX recovery depends on users starting the new bot. This is why bot pool migrations must use cohort assignment and avoid forced migration unless necessary.

---

## 7. Scenario E — Postmark Outage

Impact:

- Email forwarding path delayed/unavailable
- SePay path still works
- Payment email backup delayed, SePay primary payment still works if configured

### Steps

1. Confirm Postmark status page.
2. Check if inbound webhooks are delayed or failing.
3. Pause email-only onboarding if outage >1h.
4. Notify affected users:

```text
Email forwarding is delayed due to provider outage. SePay-connected accounts still work. We will process delayed emails when provider recovers.
```

5. When Postmark recovers:
   - watch inbound backlog
   - dedup duplicate emails
   - monitor parser failures

### Optional fallback (clarified)

**Apps Script đã DELETE từ Phase 1-2 refactor** (xem feature-spec-refactor-saas v1.2 §2.2). Nếu Postmark outage > 4h và cần emergency bridge:
- **Rebuild from scratch** (không có file sẵn trong repo). Code template lưu ở `docs/runbooks/emergency-apps-script-template.md` (tạo separately if needed).
- **Founder Gmail only** — pull bank emails của founder forward đến `/inbound/{PLATFORM_TOKEN}` để giữ payment detection live.
- **KHÔNG public path** — không guide user setup Apps Script trong incident.
- Khi Postmark phục hồi, disable Apps Script ngay.

---

## 8. Scenario F — Founder Unavailable

Problem: solo founder ops risk.

### Prepared before launch

- Trusted contact has access to this runbook
- Trusted contact can access:
  - Railway
  - domain DNS
  - B2 backup
  - Telegram admin chat
- Emergency credentials stored securely, not in repo

### Auto-degrade rules

If founder unavailable and queues grow:

- If unmatched payments >50 → pause new upgrades and show message
- If parser_fail queue >100 → disable email onboarding temporarily
- Auto-extend pending payment TTL +48h during incident

### Trusted contact minimum actions

1. Check `/admin_health`
2. Check status page/Railway
3. If DB/app outage: follow Scenario A/B
4. If payment queue high: pause upgrades
5. Post user-facing status update

---

## 8b. Scenario G — SePay Outage

Impact:

- Primary auto-tracking path down → user transactions không update real-time
- Email path C still works (Postmark independent)
- Platform payment detection cũng dùng SePay primary → fallback Email backup (per payment spec §2)

### Steps

1. **Confirm outage**
   - SePay status page / Telegram channel
   - `/admin_health` shows SePay webhook delivery rate dropped

2. **Notify users (proactive)**
   ```text
   ⚠️ SePay (đối tác bank webhook) hiện gián đoạn. Giao dịch SePay-tracked sẽ delay.
   Email forwarding vẫn hoạt động bình thường. Chúng tôi sẽ catch-up khi SePay phục hồi.
   ```

3. **Increase email backup priority**
   - Confirm Postmark inbound webhook receiving normally
   - Monitor email parser fail rate (likely spike vì user fallback chưa setup)
   - Founder personal Postmark thay tạm thời cho platform payment nếu nhất thiết

4. **Pause auto-cancel pending payments**
   - Auto-extend pending payment TTL +24h (admin command)
   - User chuyển khoản trong window outage không bị "expired" loss

5. **When SePay recovers**
   - Watch backlog catch-up
   - Verify dedup không break (SePay catch-up + Email backup trùng)
   - Check no duplicate `payment_matches` (cross-source dedup state machine, payment spec §3)

### Success criteria

- No data loss: post-recovery, SePay webhook backlog processed correctly
- No duplicate payments confirmed
- User-facing communication issued within 30m of confirmed outage

---

## 8c. Scenario H — Abuse / Spam / Bot signup attack

Impact:

- 1 user spamming `/upgrade` → flood pending_payments table
- Mass signup attack → bot rate limit hit, real users blocked
- DDoS-style call to `/health` or webhook endpoints

### Detection signals

- Sudden spike in `user_signup_success` (>10x baseline) within 1h
- Pending payments table > 100 unmatched cho 1 user_id
- Webhook 5xx rate > 5%
- Telegram send queue depth > 500

### Steps

1. **Identify scope**
   - `/admin_user {user_id}` cho user nghi ngờ
   - SQL: `SELECT user_id, COUNT(*) FROM pending_payments WHERE status='pending' GROUP BY user_id ORDER BY COUNT DESC LIMIT 5;`

2. **Block at user level**
   - `/admin_pause_user {user_id}` — disable outbound + webhook processing for user
   - Audit log entry với reason

3. **Block at IP/network level (if webhook flood)**
   - Railway Cloudflare WAF rule (if configured)
   - Or temporarily disable affected endpoint, route 503

4. **Cleanup**
   - Cancel pending payments của user abuser (`/admin_cancel_pending` batch)
   - Mark suspicious unmatched_payments as `voided` với reason

5. **Long-term mitigation**
   - Add rate limit on `/upgrade` per user (max 3/day)
   - Add rate limit on `/start` per IP (anti-mass-signup)
   - Add suspicion score: many signups same hour from similar usernames

### Success criteria

- Abuser blocked within 30 phút of detection
- No revenue lost (real paid users không bị affected)
- Post-mortem identifies root cause

---

## 8d. Scenario I — Founder Gmail Forwarding Rule Disabled

**Trigger:** Subscription email backup path silent fail. Symptoms:
- 0 emails received vào `payment@in.tienvenoidau.com` past 24h (daily monitoring task)
- Đồng thời có >1 unmatched SePay payment (user transferred TCB nhưng không match)
- User complaint qua admin: "đã chuyển TCB rồi mà chưa upgrade"

**Severity:** P2 — Subscription path TCB broken, VCB path vẫn live → revenue chỉ partial loss.

**RTO target:** 30 phút.

**Detection:**
- Daily monitoring task fire alert tới `ADMIN_TELEGRAM_IDS` nếu `count(emails received in 24h) == 0` AND `count(SePay tx unmatched) > 0`
- User báo qua /admin_user lookup
- /admin_cost dashboard show "TCB email path: 0 received past 24h"

**Recovery procedure:**

1. **Verify rule status** (5 phút):
   - Login Gmail của founder (account dedicated cho payment@platform)
   - Settings → Filters and Blocked Addresses → search "Forwards to: payment@in.tienvenoidau.com"
   - Nếu không thấy → rule bị Gmail disable hoặc xóa
   - Nếu thấy nhưng có warning "Forwarding paused" → resume

2. **Re-enable forwarding** (5 phút):
   - Forwarding and POP/IMAP → re-add `payment@in.tienvenoidau.com` if removed
   - Verify forwarding address (Gmail send verification email — tap confirm trong Postmark inbox hoặc admin panel)
   - Re-create filter: From `automail@techcombank.com.vn` OR `ebank@techcombank.com.vn` → Forward to `payment@in.tienvenoidau.com`

3. **Test forwarding** (5 phút):
   - Founder transfer test 10k tới TCB account
   - Verify email arrive Gmail → forward → Postmark webhook fire → log entry trong `unmatched_payments` (nếu không có pending) hoặc `payment_matches` (nếu test với pending ref)

4. **Backfill missed payments** (10 phút):
   - Query `unmatched_payments` chưa resolve trong 24h gần nhất
   - Cross-reference với `pending_payments` của user complaint
   - Admin command `/admin_resolve {unmatched_id} {pending_id}` → upgrade user manually
   - Notify user qua Telegram: "Xin lỗi delay xác nhận, plan đã active từ ngày..."

5. **Post-incident** (5 phút):
   - Update monitoring task threshold (vd alert sớm hơn, 12h thay vì 24h)
   - Document trong incident log
   - Schedule monthly check forwarding rule status

### Success criteria

- Forwarding rule re-active within 30 phút
- All affected users backfilled với plan upgrade
- No silent SLA violation (user vẫn upgrade trong 24h grace)
- Monitoring threshold tightened để detect sớm next occurrence

### Prevention

- [ ] Monthly manual check forwarding rule (calendar reminder)
- [ ] Backup forwarding rule trong Outlook account khác (redundancy nếu Gmail account die)
- [ ] Document trong `docs/runbooks/payment-email-setup.md` step-by-step setup
- [ ] Founder maintain Gmail account dedicated cho payment, không trộn với personal email

---

## 8e. Scenario J — Facebook Page Suspended / Restricted

**Trigger:** Messenger channel offline. Symptoms:
- Toàn user signup qua Messenger không nhận message
- Get Started button không response
- `m.me/FinTrackPage` redirect tới error page hoặc Page restricted notice
- Meta admin email notification "Page restricted" / "Page unpublished"

**Severity:** P1 — toàn ~50% user (Messenger cohort) offline. Telegram unaffected.

**RTO target:** 4-24 giờ (depend Meta response time).

**Detection:**
- 0 inbound webhook tới `/webhook/messenger` past 1 hour (during normal hour)
- Sentry error spike: Send API return 200 nhưng message không deliver
- User complaint qua Telegram (some user dual-track via friend)

**Recovery procedure:**

1. **Triage immediate** (15 phút):
   - Check Meta Business Suite → Page Quality → look for restriction reason
   - Common causes:
     - Spam policy violation (sent too many MESSAGE_TAG without proper use case)
     - Trademark/IP claim
     - User reports (multiple block từ same Page)
     - Automated detection mistakenly flag
   - Set status `users.invalid_channel=TRUE` cho toàn Messenger user (mass UPDATE) → ngừng outbound retry → tránh spike Send API errors

2. **Post out-of-band notification** (10 phút):
   - Telegram channel `@FinTrackUpdates`: "⚠️ Messenger channel tạm offline. Đang work với Meta để khôi phục. ETA: 4-24h. User Messenger có thể signup mới qua Telegram tạm thời: t.me/FinTrackBot"
   - Email tới mọi user Messenger có email collected (qua `inbound_email` lookup)
   - Twitter/Facebook (nếu maintained): same message

3. **Appeal Meta** (depends — phải đợi Meta):
   - Business Suite → Page Quality → Request Review
   - Provide evidence: Privacy policy URL, App Review approval number, screenshots use case ACCOUNT_UPDATE legitimate
   - Wait Meta response (24h-7 days typical)
   - Daily check status

4. **Continue Telegram operation** (ongoing):
   - 100% revenue stream qua Telegram
   - User Messenger không thể signup mới — accept losing TAM tạm thời
   - Monitor churn — nếu Messenger user > 1 week offline → manual outreach migrate qua Telegram

5. **If Meta permanently bans Page** (worst case):
   - Create new Page với different name (vd FinTrackVN thay Tiền Về Nơi Đâu)
   - User existing Messenger không tự động migrate — phải manual outreach
   - Marketing pivot: Telegram-only narrative + Zalo Phase 2 acceleration
   - Update DR runbook scenario này → "Messenger permanent loss"

### Success criteria

- Out-of-band notification posted within 30 phút
- All Messenger user marked `invalid_channel` → no error spam
- Page restored OR migration plan executed within 7 days
- Lessons learned documented (avoid same trigger)

### Prevention

- [ ] Compliance audit MESSAGE_TAG usage hàng tháng (đảm bảo mọi outbound proactive đúng tag)
- [ ] Privacy policy URL accessible + maintained current
- [ ] App Review approval kept current (re-submit nếu Meta require)
- [ ] Don't send marketing/promotional messages qua MESSAGE_TAG (chỉ ACCOUNT_UPDATE legitimate)
- [ ] Multiple Page admins (founder + 1 trusted contact) — nếu founder account locked vẫn còn admin
- [ ] Out-of-band channel ready: `@FinTrackUpdates` Telegram channel pre-created với existing subscriber base

---

## 9. Communication Templates

### 9.1. Short incident update

```text
⚠️ Tiền Về Nơi Đâu is experiencing delayed processing for [affected area].
Your data is safe. We are working on recovery.
Next update: [time].
```

### 9.2. Resolved update

```text
✅ Tiền Về Nơi Đâu incident resolved.
Affected window: [start]–[end].
Delayed transactions/payments are being processed now.
If anything looks wrong, send /help → Support.
```

### 9.3. Maintenance mode

```text
🛠 Tiền Về Nơi Đâu is under maintenance for database recovery.
Expected recovery: [time].
No action needed from you.
```

---

## 10. Launch Readiness Checklist

Before paid beta:

- [ ] Daily `pg_dump` to B2 configured (incl. globals)
- [ ] B2 credentials stored in **password manager** (1Password / Bitwarden), shared vault với 1 trusted contact (DR §8). KHÔNG commit, KHÔNG plain text file.
- [ ] B2 bucket SSE-B2 encryption verified
- [ ] Full restore to staging completed once
- [ ] `/health` endpoint reports DB/app status
- [ ] Admin Telegram chat exists
- [ ] At least one trusted contact has emergency runbook access
- [ ] DNS credentials available
- [ ] `BOT_TOKEN_BACKUP` exists and webhook tested in staging
- [ ] Incident templates ready
- [ ] **`@FinTrackUpdates` Telegram channel created** (out-of-band notification cho bot suspension scenarios)
  - Setup: @BotFather create channel, founder + trusted contact admin
  - Onboarding flow add optional "Join @FinTrackUpdates cho announcements" button
  - Test: post 1 announcement, verify subscriber count baseline
- [ ] PDPA breach plan TODO — defer post-MVP, create `docs/runbooks/pdpa-breach.md` khi reach 200+ users hoặc any breach incident (REMINDER: ≥200 users hoặc post-incident)

---

## 11. Quarterly DR Drill

1. Pick latest production backup.
2. Restore to staging DB.
3. Run smoke queries.
4. Point staging app to restored DB.
5. Run Telegram staging bot `/status`.
6. Test one fake SePay webhook.
7. Document:
   - restore duration
   - errors
   - missing steps
   - next improvements

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-06 | Initial runbook — backup setup, six recovery scenarios, RTO/RPO, communication templates, launch checklist. |
| v1.0.1 | 2026-05-06 | **Review fixes:** (1) §2.1 add `pg_dumpall --globals-only` cho roles backup + B2 SSE-B2 server-side encryption explicit setup. (2) §3 add `VACUUM ANALYZE` step sau restore (planner stats). (3) §6 bot suspend communication clarify MVP không có email/SMS list, suggest `@FinTrackUpdates` channel pre-launch. (4) §7 Postmark fallback Apps Script: clarify đã DELETE từ Phase 1-2, rebuild from scratch nếu cần emergency, founder-only never public. (5) §10 launch checklist: B2 credentials trong password manager (1Password/Bitwarden) shared vault với trusted contact. |
| v1.1.0 | 2026-05-06 | **Round-2 fixes (Q3 + Q4 from review):** (1) **§8b Scenario G mới — SePay outage**: detection, user notification, email backup priority, auto-extend pending TTL, post-recovery dedup verify. (2) **§8c Scenario H mới — Abuse/spam**: detection signals, /admin_pause_user, batch cancel, long-term mitigation rate limits. (3) §6 + §10 confirm `@FinTrackUpdates` channel as primary out-of-band notification path (created pre-launch). (4) §10 thêm PDPA breach plan TODO marker — defer to ≥200 users hoặc post-incident (Q8). |
| v1.2.0 | 2026-05-07 | **Multi-channel + email parallel scenarios (sync feature-spec-messenger-channel v1.1.1 + impl plan VietQR+email v1.0.0):** (1) **§8d Scenario I mới — Founder Gmail forwarding rule disabled**: detection via daily monitoring (0 emails received past 24h + >1 unmatched SePay), recovery 30 phút (re-enable rule + backfill missed payments via /admin_resolve), prevention checklist (monthly manual check, backup forwarding rule Outlook, dedicated Gmail account). (2) **§8e Scenario J mới — Facebook Page Suspended/Restricted**: triage causes (spam policy MESSAGE_TAG abuse, IP claim, user reports), mass UPDATE `users.invalid_channel` cho Messenger users, out-of-band notification qua Telegram channel + email Postmark, Meta appeal process (24h-7 days), worst case migration plan. Severity P1 (50% user offline). Prevention: compliance audit MESSAGE_TAG hàng tháng + multiple Page admins + privacy policy current. (3) Header refs bumped BRD v2.8.0 → v2.9.0, TDD v1.5.2 → v1.6.0; thêm Messenger Spec + Impl Plan VietQR refs. |

### §8f Scenario K — Discord Bot Suspended/Disabled

**Trigger:** Discord disables bot application (TOS violation, abuse report, rate limit abuse).

**Detection:** `/webhook/discord` returning 401/403, Discord API calls fail, `DiscordSender` errors spike.

**Severity:** P1 (affects all Discord users)

**Recovery:**
1. Check [Discord Developer Portal](https://discord.com/developers) for bot status + violation notice
2. Appeal via Discord support (response 1-7 days)
3. Mass UPDATE `users SET invalid_channel = TRUE WHERE channel_type = 'discord'`
4. Out-of-band notification: Telegram channel announcement
5. If appeal fails: guide users to migrate to Telegram via landing page

**Prevention:**
- Rate limit compliance (respect 429 headers + exponential backoff)
- No spam DMs to users who haven't interacted
- Regular review of Discord TOS updates
