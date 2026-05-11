# BE Tech Doc: Admin Tools & Audit

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_admin_tools.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_admin_tools.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/admin.py` | Admin command dispatch |
| Decorator | `services/admin_auth.py` | `@admin_only` auth |
| DB | `db.py` | admin_audit_log INSERT, admin queries |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Audit log insert
INSERT INTO admin_audit_log (admin_telegram_id, command, target_user_id, payload, result)
VALUES ($1, $2, $3, $4, $5);

-- User lookup
SELECT u.*, COUNT(t.id) as tx_count,
       (SELECT COUNT(*) FROM bank_connections bc WHERE bc.user_id = u.id AND bc.active) as bank_count
FROM users u LEFT JOIN transactions t ON t.user_id = u.id
WHERE u.id = $1 GROUP BY u.id;

-- List unmatched payments
SELECT * FROM unmatched_payments WHERE status = 'pending_review' ORDER BY received_at DESC LIMIT 20;

-- Manual resolve
UPDATE unmatched_payments SET status = 'matched_manually', resolved_by = $1, resolved_at = NOW() WHERE id = $2;

-- Force plan override
UPDATE users SET plan = $1, plan_expires_at = NOW() + ($2 || ' days')::INTERVAL WHERE id = $3;

-- Business stats
SELECT plan, COUNT(*) as count FROM users GROUP BY plan;
SELECT COUNT(*) as active_30d FROM users WHERE updated_at > NOW() - INTERVAL '30 days';
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Non-admin command | Silent ignore + audit log result='denied' |
| 2 | Security | Admin ID removed | Requires restart |
| 3 | Data Integrity | Refund already downgraded | Still mark refunded, no plan change |
| 4 | Concurrency | 2 admin resolve same payment | First write wins |
| 5 | Security | Broadcast 500 users | Rate limit 30 msg/s |
| 6 | Cross-Feature | Plan override → jobs | Recalculate scheduled_jobs |
| 7 | Data Integrity | Delete user cascade | FK ON DELETE CASCADE |
| 8 | Security | Audit log immutable | Append-only, no UPDATE/DELETE |
| 9 | Cross-Feature | Resolve already matched | Reject with message |
| 10 | Data Integrity | Large audit log | Rotate >90 days |
| 11 | Security | Admin impersonation | Telegram signature verify |
| 12 | Data Integrity | Invalid plan string | Validate against CHECK constraint |

---

## 3. API Contract

### 3.1. Admin Auth Decorator

```python
import os, functools
ADMIN_IDS = set(os.environ.get('ADMIN_TELEGRAM_IDS / ADMIN_DISCORD_IDS', '').split(','))

def admin_only(handler):
    @functools.wraps(handler)
    async def wrapper(update, context):
        user_id = str(update.effective_user.id)
        if user_id not in ADMIN_IDS:
            await db.log_admin_audit(user_id, handler.__name__, None, None, 'denied')
            return  # Silent
        result = await handler(update, context)
        return result
    return wrapper
```

### 3.2. Command Signatures

```python
@admin_only
async def admin_user(update, context):    # /admin_user {id}
@admin_only
async def admin_plan(update, context):    # /admin_plan {id} {plan} {days}
@admin_only
async def admin_unmatched(update, context):  # /admin_unmatched
@admin_only
async def admin_resolve(update, context):    # /admin_resolve {pid} {uid}
@admin_only
async def admin_refund(update, context):     # /admin_refund {mid}
@admin_only
async def admin_health(update, context):     # /admin_health
@admin_only
async def admin_stats(update, context):      # /admin_stats
```

---

## 4. Implementation Details

### 4.1. Health Check

```python
async def get_health():
    pool = db.get_pool()
    return {
        'db_pool_size': pool.get_size(),
        'db_pool_free': pool.get_idle_size(),
        'uptime_seconds': time.time() - START_TIME,
        'users_total': await db.count_users(),
        'pending_payments': await db.count_pending_payments(),
        'unmatched_queue': await db.count_unmatched(),
    }
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Admin auth pass | Valid admin ID | Command executes |
| 2 | Admin auth fail | Non-admin ID | Silent ignore |
| 3 | Audit log created | Any admin command | Row in admin_audit_log |
| 4 | Denied audit | Non-admin attempt | result='denied' |
| 5 | User lookup | /admin_user 1 | User info + stats |
| 6 | User not found | /admin_user 9999 | "User không tồn tại" |
| 7 | Plan override | /admin_plan 1 pro 30 | Plan updated |
| 8 | Invalid plan | /admin_plan 1 gold 30 | Rejected |
| 9 | Unmatched list | /admin_unmatched | Pending review items |
| 10 | Empty unmatched | No items | "Không có" |
| 11 | Resolve payment | /admin_resolve 1 42 | Status updated |
| 12 | Resolve already matched | /admin_resolve 1 42 (already) | Rejected |
| 13 | Refund | /admin_refund 1 | Plan revoked, match refunded |
| 14 | Health check | /admin_health | Pool + uptime info |
| 15 | Stats | /admin_stats | Plan distribution |
| 16 | Plan override → jobs | Force pro | weekly job enabled |
| 17 | Broadcast | /admin_broadcast "msg" | Messages queued |
| 18 | Broadcast rate limit | 500 users | 30/s respected |
| 19 | Audit log integrity | Try UPDATE | Not possible (append-only) |
| 20 | Multiple admins | 2 admin IDs in env | Both authorized |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
