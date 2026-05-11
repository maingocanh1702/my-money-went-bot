# BE Tech Doc: Pricing, Tier Limits & Trial (F06)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-pricing-tiers.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Service | `services/plan_svc.py` | Tier enforcement, trial logic, upgrade/downgrade |
| Middleware | `services/tier_check.py` | Per-request tier limit checking |
| Scheduled | `services/trial_scheduler.py` | Trial reminder/downgrade jobs |
| DB | `db.py` | Plan CRUD, tier count queries |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Get user plan info
SELECT plan, trial_ends_at, plan_expires_at, plan_grace_until, billing_period
FROM users WHERE id = $1;

-- Upgrade plan
UPDATE users SET plan = $1, plan_expires_at = $2, billing_period = $3, trial_ends_at = NULL
WHERE id = $4;

-- Downgrade to free
UPDATE users SET plan = 'free', plan_expires_at = NULL, plan_grace_until = NULL, billing_period = NULL
WHERE id = $1;

-- Trial expiry check (scheduled job)
SELECT id FROM users
WHERE trial_ends_at IS NOT NULL AND trial_ends_at <= NOW() AND plan != 'free';

-- Grace period expiry
SELECT id FROM users
WHERE plan_grace_until IS NOT NULL AND plan_grace_until <= NOW() AND plan != 'free';

-- Tier limit: tx count
SELECT COUNT(*) FROM transactions WHERE user_id = $1 AND month_key = $2;

-- Tier limit: bank connections
SELECT COUNT(*) FROM bank_connections WHERE user_id = $1 AND active = TRUE;

-- Tier limit: categories
SELECT COUNT(*) FROM categories WHERE user_id = $1 AND active = TRUE;
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | Trial + upgrade during trial | Cancel trial (trial_ends_at=NULL), start paid |
| 2 | Cross-Feature | Downgrade with >Free limits | Data preserved, new actions blocked |
| 3 | Data Integrity | plan_expires_at NULL | Treat as Free |
| 4 | Concurrency | 2 upgrade requests | Idempotent: check pending_payments |
| 5 | Cross-Feature | Downgrade → scheduled jobs | Disable weekly/monthly jobs |
| 6 | Data Integrity | Trial end + tx processing | Tx completes, then downgrade |
| 7 | Cross-Feature | Annual cancel mid-term | No refund pro-rata (policy) |
| 8 | Data Integrity | Timezone affects monthly count | UTC month_key |
| 9 | Security | Spoofed upgrade trigger | Validate user_id |
| 10 | Cross-Feature | Grace period → still Pro features | Check plan_grace_until > NOW() |
| 11 | Data Integrity | Upgrade trigger cooldown | Last trigger timestamp per user |
| 12 | Concurrency | Trial downgrade race with payment | Transaction lock on user row |

---

## 3. API Contract

### 3.1. Tier Check Function

```python
TIER_LIMITS = {
    'free':     {'tx_per_month': 45, 'banks': 1, 'history_days': 30, 'categories': 5, 'email_sources': 1},
    'pro':      {'tx_per_month': float('inf'), 'banks': 3, 'history_days': float('inf'), 'categories': 20, 'email_sources': 3},
    'business': {'tx_per_month': float('inf'), 'banks': 5, 'history_days': float('inf'), 'categories': float('inf'), 'email_sources': float('inf')},
}

async def check_tier_limit(user_id: int, limit_type: str) -> bool:
    """Returns True if within limit."""

async def get_effective_plan(user: User) -> str:
    """Returns effective plan considering trial + grace period."""
    if user.trial_ends_at and user.trial_ends_at > datetime.utcnow():
        return 'pro'  # Trial = Pro features
    if user.plan_grace_until and user.plan_grace_until > datetime.utcnow():
        return user.plan  # Grace period
    if user.plan_expires_at and user.plan_expires_at < datetime.utcnow():
        return 'free'  # Expired
    return user.plan
```

### 3.2. Pricing Config

```python
PRICING = {
    'pro':      {'monthly': 79_000, 'annual': 758_400},   # VND
    'business': {'monthly': 199_000, 'annual': 1_910_400},
}
PRICING_USD = {
    'pro':      {'monthly': 400, 'annual': 3_840},         # cents
    'business': {'monthly': 900, 'annual': 8_640},
}
```

---

## 4. Implementation Details

### 4.1. Trial Flow

```python
async def handle_trial_expiry(user_id: int):
    user = await db.get_user(user_id)
    if user.plan_expires_at:  # Already paid, trial irrelevant
        return
    await db.update_user(user_id, plan='free', trial_ends_at=None)
    await disable_pro_scheduled_jobs(user_id)
    await messenger.send(user_id, {"type": "text", "text": TRIAL_EXPIRED_MSG})
```

### 4.2. Upgrade Trigger Cooldown

```python
UPGRADE_COOLDOWN_DAYS = 7
async def should_show_upgrade(user_id: int) -> bool:
    last = await db.get_last_upgrade_trigger(user_id)
    if not last: return True
    return (datetime.utcnow() - last).days >= UPGRADE_COOLDOWN_DAYS
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | New user trial | Signup | trial_ends_at = NOW() + 14d |
| 2 | Trial active | Day 5 | effective_plan = 'pro' |
| 3 | Trial reminder | Day 12 | Reminder sent |
| 4 | Trial expiry | Day 14 | plan = 'free' |
| 5 | Upgrade during trial | Pay Pro | trial_ends_at = NULL, plan = 'pro' |
| 6 | Free tx limit 44 | 44th tx | Allowed |
| 7 | Free tx limit 46 | 46th tx | Blocked |
| 8 | Pro tx unlimited | 500th tx | Allowed |
| 9 | Free bank limit | 2nd bank | Blocked |
| 10 | Pro bank limit | 4th bank | Blocked |
| 11 | Free category limit | 6th category | Blocked |
| 12 | Business unlimited | 100th category | Allowed |
| 13 | Grace period active | 3 days after expiry | Pro features |
| 14 | Grace period expired | 8 days after expiry | Downgrade free |
| 15 | Annual pricing | Pro annual | 758,400 VND |
| 16 | Monthly pricing | Pro monthly | 79,000 VND |
| 17 | Upgrade cooldown | Trigger 3 days ago | Don't show |
| 18 | Upgrade cooldown | Trigger 8 days ago | Show |
| 19 | Downgrade disables jobs | Pro → Free | weekly/monthly jobs disabled |
| 20 | Concurrent upgrade | 2 requests | 1 pending_payment |
| 21 | Effective plan logic | Trial + paid | Paid wins |
| 22 | NULL plan_expires | No expiry set | Treat as free |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
