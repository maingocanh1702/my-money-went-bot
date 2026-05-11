# Feature Spec — Admin Tools & Audit

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-06
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase liên quan:** Phase 1-2 foundation (schema `admin_audit_log` + `@admin_only` + `ADMIN_TELEGRAM_IDS` parsing) + Phase 6 polish/deploy (full commands implementation) + Phase 7 beta (test all commands end-to-end)
> **Tham chiếu:** [BRD v2.9.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd.md) · [TDD v1.6.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) · [Feature Spec Payment v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/feature-spec-payment-bank-transfer.md) · [Implementation Plan 500+ v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plan-500-users-and-more.md)

---

## 1. Mục tiêu & non-goals

### 1.1. Mục tiêu

Build admin tooling đủ để founder vận hành beta/public launch mà không cần DB shell cho mọi incident:

- Review và resolve unmatched payments
- Refund/revoke/credit subscriptions
- Search user, inspect state, debug onboarding/payment/parser issues
- Force-adjust plan khi cần support/manual compensation
- Audit mọi admin action để tránh thao tác âm thầm trên financial/user data

Admin tools là **foundation requirement**, không phải polish: schema `admin_audit_log`, `ADMIN_TELEGRAM_IDS`, và auth framework phải có từ Phase 1-2 để Phase 6 không migrate ngược.

### 1.2. Non-goals

- KHÔNG build full internal CRM/dashboard đẹp trong MVP.
- KHÔNG cho admin sửa transaction arbitrary qua UI rộng; mọi destructive action phải explicit command + confirmation.
- KHÔNG support multi-role complex RBAC trong MVP. Chỉ `admin` allowlist.
- KHÔNG expose web dashboard public internet nếu chưa có auth/session hardening.

---

## 2. Admin Identity & Authorization

### 2.1. Config

```bash
ADMIN_TELEGRAM_IDS=828512068897603585,123456789
ADMIN_CHAT_ID=<optional admin group chat id>
```

- `ADMIN_TELEGRAM_IDS`: comma-separated Telegram user ids allowed to run admin commands.
- `ADMIN_CHAT_ID`: optional chat/group where alerts are sent. If absent, send to first admin id.

### 2.2. Authorization rule

Every admin command MUST pass:

```python
def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.ADMIN_TELEGRAM_IDS
```

Pattern:

```python
@admin_only
async def admin_refund(ctx, match_id: int):
    ...
```

Denied attempts are logged with `result='denied'`.

### 2.3. Rate limiting

Admin commands default rate limit: **30 commands/phút per admin** (token bucket). Bảo vệ chống accidental flood (vd loop bug call `/admin_stats` infinite, fat-finger replay).

**Config**:
```bash
ADMIN_RATE_LIMIT_PER_MIN=30   # default
```

Có thể adjust qua command `/admin_set_rate_limit {N}` (Yes confirmation, max 120/min, audit log).

**Implementation**:
- Token bucket per `admin_telegram_id`, refill 30 tokens/min linearly
- Exceeded → bot reply "Rate limit hit, retry in {sec}s" + log denied attempt
- `/admin_health` always exempt (need to check status during incident)
- `/admin_help` exempt cho discoverability

### 2.4. Confirmation rule

Destructive commands require confirmation:

- refund
- force plan change
- cancel pending payment
- manual match
- data export/delete

UX:

```text
/admin_refund 42

Bot:
⚠️ Refund match #42 — 100,000đ for user 123.
This will mark payment refunded and downgrade/recompute plan.
Type: confirm refund 42
```

---

## 3. Data Model

### 3.1. Admin audit log

Already canonical in TDD v1.6.0.

```sql
CREATE TABLE admin_audit_log (
    id                 BIGSERIAL PRIMARY KEY,
    admin_telegram_id  BIGINT NOT NULL,
    command            VARCHAR(64) NOT NULL,
    target_user_id     INTEGER REFERENCES users(id),
    payload            JSONB,
    result             VARCHAR(16), -- 'success'|'fail'|'denied'
    error_message      TEXT,
    executed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_admin_audit_admin
ON admin_audit_log(admin_telegram_id, executed_at DESC);

CREATE INDEX idx_admin_audit_target
ON admin_audit_log(target_user_id, executed_at DESC);
```

### 3.2. Audit event payload examples

```json
{
  "command": "/admin_refund",
  "match_id": 42,
  "amount": 100000,
  "reason": "7-day money back",
  "before": {"plan": "pro", "plan_expires_at": "2026-06-05T00:00:00Z"},
  "after": {"plan": "free", "plan_expires_at": null}
}
```

Optional mirror to `analytics_events` only for metrics, not as source of audit truth.

---

## 4. Command Surface

### 4.1. User inspection

| Command | Purpose | Output |
|---|---|---|
| `/admin_users [query]` | Search users by id, username, telegram_id | compact list |
| `/admin_user {user_id}` | Full user snapshot | plan, trial, tx count, sources, last active |
| `/admin_logs {user_id}` | Last 50 events/audit rows | timeline |
| `/admin_state {user_id}` | Current bot_state | step + payload summary |

### 4.2. Payment operations

| Command | Purpose | Confirmation? |
|---|---|---|
| `/admin_pending` | List pending payments expiring soon / review | No |
| `/admin_unmatched` | List unmatched payment queue | No |
| `/admin_resolve {unmatched_id} {pending_id}` | Link incoming transfer to pending payment | Yes |
| `/admin_refund {match_id}` | Mark refunded + recompute/revoke plan | Yes |
| `/admin_extend {pending_id} {hours}` | Extend pending payment TTL (hard cap **168h = 7 ngày**) | Yes if >48h |
| `/admin_cancel_pending {pending_id}` | Cancel pending payment | Yes |

### 4.3. Plan/account operations

| Command | Purpose | Confirmation? |
|---|---|---|
| `/admin_force_plan {user_id} {plan} {expires_at}` | Manual comp/override. `expires_at` ISO format (`YYYY-MM-DD`), validate ≤ 2 năm future để tránh typo "29991231" | Yes |
| `/admin_recompute_plan {user_id}` | Recompute plan from payment history | Yes if changes |
| `/admin_export_user {user_id}` | PDPA data export | Yes |
| `/admin_pause_user {user_id}` | Pause outbound sends/support issue | Yes |

### 4.4. Ops stats

| Command | Purpose |
|---|---|
| `/admin_help [category]` | **Hybrid: auto-generated list** từ command registry (luôn up-to-date) + **manual prose intro** (ngắn 2-3 câu cho new admin). Critical cho trusted contact (DR §8). Optional `category` arg filter (`payment` / `user` / `ops` / `plan`) |
| `/admin_set_rate_limit {N}` | Adjust per-admin rate limit. Default 30/min, max 120. Confirmation required. |
| `/admin_stats` | Today: signups, DAU, tx, payments, errors, queue depth |
| `/admin_health` | DB, Postmark, SePay webhook, Telegram send health (detail checks ở observability-plan §7.2) |
| `/admin_parser_stats` | Parser success/fail by bank, last 24h/7d |
| `/admin_payment_stats` | Layer 1/2/3/4 distribution, unmatched queue |

---

### 4.5. `/admin_help` implementation

**Hybrid approach** — auto-generate primary, manual override secondary:

```python
# services/admin/registry.py
ADMIN_COMMANDS = {}  # populated by @admin_only decorator at module load

@admin_only(category='payment', destructive=True, confirm_phrase='confirm refund {match_id}')
async def admin_refund(ctx, match_id: int):
    """Mark match refunded + recompute plan."""
    ...

# /admin_help auto-generated section:
async def admin_help(ctx, category=None):
    intro = MANUAL_INTRO  # 2-3 sentence prose stored separately
    sections = group_by_category(ADMIN_COMMANDS, filter=category)
    return format_help(intro, sections)
```

**Manual intro example** (separate file `services/admin/help_intro.md`):

```text
Admin commands cho FinTrack ops. Mọi destructive action cần confirmation.
Unknown command? Try /admin_help {category} với category = payment | user | plan | ops.
Emergency? Xem docs/runbooks/disaster-recovery.md.
```

→ Add new command = decorator → tự động vào /admin_help, không quên update.

---

## 5. Manual Resolve Flow

### 5.1. Unmatched payment → pending payment

```text
/admin_unmatched

#17 · 100,000đ · email_vcb_platform · 2026-05-06 10:14
Desc: PAY 123 PRO M X9K2
Candidates: pending #88 user 123 Pro monthly 100,000đ

/admin_resolve 17 88
```

Bot response:

```text
⚠️ Manual resolve unmatched #17 → pending #88
User: 123
Amount: 100,000đ
Plan: Pro monthly
Type: confirm resolve 17 88
```

On confirm:

1. Lock `pending_payments` row `FOR UPDATE`
2. Verify status is `pending` or `manual_review`
3. Insert `payment_matches` with `source='manual'`, `match_layer=4`, `reviewed_by=admin_id`
4. Set pending status `matched`
5. Activate user plan
6. Mark unmatched `matched_manually`
7. Send confirmation to user
8. Write `admin_audit_log`

### 5.2. Refund flow

On `/admin_refund {match_id}` confirm:

1. Mark `payment_matches.status='refunded'`
2. Set `refunded_at=NOW()`, `refund_notes`
3. Recompute user plan from remaining non-refunded matches
4. If no active paid cycle → downgrade Free
5. Admin manually transfers refund via bank app
6. Send user message confirming refund status
7. Write `admin_audit_log`

Note: actual money transfer is manual MVP. The command records product/account state, not bank API transfer.

---

## 6. Minimal Web Dashboard (Optional Phase 7+)

Only if Telegram admin commands become painful.

- Route: `/admin`
- Auth: signed session cookie + admin Telegram login code OR Basic Auth over HTTPS for staging only
- Tables:
  - users
  - pending_payments
  - unmatched_payments
  - payment_matches
  - admin_audit_log
- Actions still require confirmation.

MVP can defer this. Telegram commands are enough for 0-100 users.

---

## 7. Security Requirements

- Admin commands only accepted from private DM/admin chat and `ADMIN_TELEGRAM_IDS`.
- Every denied attempt logged.
- Destructive commands require confirmation phrase.
- Admin output must redact sensitive data:
  - no full bank account numbers
  - no raw token values
  - webhook tokens shown only last 4 chars unless explicit `/admin_reveal_token` (not MVP)
- Audit log append-only by app convention. No admin command deletes audit rows.
- **Optional DB-level enforce** (recommend Phase 6+): create dedicated DB role `app_role` với `REVOKE DELETE, UPDATE ON admin_audit_log FROM app_role`. App connects qua `app_role`. Migrations dùng superuser role riêng. Bảo vệ chống insider modify audit trail.

---

## 8. Acceptance Criteria

### 8.1. Foundation (Phase 1-2)

- [ ] `admin_audit_log` exists in initial migration
- [ ] `ADMIN_TELEGRAM_IDS` parsed from env, supports multiple ids
- [ ] `@admin_only` decorator/middleware exists
- [ ] Denied admin command logs `result='denied'`
- [ ] Admin framework can route `/admin_stats` stub safely

### 8.2. Phase 6 commands

- [ ] `/admin_users`, `/admin_user`, `/admin_logs`, `/admin_stats` work
- [ ] `/admin_pending`, `/admin_unmatched` work
- [ ] `/admin_resolve` manual link works end-to-end
- [ ] `/admin_refund` marks refunded + recomputes plan
- [ ] `/admin_force_plan` works with confirmation
- [ ] All successful/failed/denied actions write `admin_audit_log`

### 8.3. Safety

- [ ] Non-admin cannot execute any `/admin_*` command
- [ ] Destructive command without confirmation does nothing
- [ ] Audit log contains before/after payload for plan/payment changes
- [ ] Admin output redacts tokens and account numbers

---

## 9. Test Plan

- Unit test `is_admin()` parsing, empty env, malformed env
- Unit test `@admin_only` allow/deny/audit
- Integration test manual resolve with row lock
- Integration test refund recompute plan
- Integration test force plan confirmation
- Grep test: no admin command bypasses audit helper

---

## 10. Effort Estimate

| Work | Effort |
|---|---:|
| Foundation schema + auth framework | 1 day |
| Read-only commands | 1 day |
| Payment manual resolve/refund commands | 1-2 days |
| Force plan/export/logs | 1 day |
| Tests + polish | 1 day |
| **Total** | **3-5 dev days** |

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-06 | Initial spec — admin commands, audit log, auth framework, manual payment operations, safety/confirmation rules. |
| v1.0.1 | 2026-05-06 | **Review fixes:** (1) `/admin_extend` hard cap 168h (7 days). (2) `/admin_force_plan` validate `expires_at` ≤ 2 năm future. (3) Thêm `/admin_help` cho trusted contact case (DR §8). (4) §7 thêm optional DB-level enforce audit append-only via `app_role` REVOKE DELETE. (5) Phase reference expanded include Phase 7 beta test. |
| v1.1.0 | 2026-05-06 | **Round-2 fixes (Q1 + Q2 from review):** (1) §2.3 mới — **rate limiting**: default 30 commands/phút per admin, env `ADMIN_RATE_LIMIT_PER_MIN`, `/admin_set_rate_limit` adjust runtime. `/admin_health` + `/admin_help` exempt. (2) §4.5 mới — `/admin_help` **hybrid auto-generate + manual intro**: registry pattern qua `@admin_only` decorator → tự động vào /admin_help, không quên update. Manual intro stored separate `services/admin/help_intro.md` cho prose. (3) §4.4 thêm `/admin_set_rate_limit` command. |
