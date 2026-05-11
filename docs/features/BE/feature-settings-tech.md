# BE Tech Doc: Settings (F07)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-settings.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-settings.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/settings.py` | `/settings` command + callbacks |
| Service | `services/user_svc.py` | Token regen, timezone update |
| DB | `db.py` | User settings CRUD |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Get settings
SELECT webhook_token, inbound_email, timezone, daily_recap_enabled, plan, trial_ends_at, plan_expires_at
FROM users WHERE id = $1;

-- Regenerate webhook token
UPDATE users SET webhook_token = $1, updated_at = NOW() WHERE id = $2;

-- Update timezone
UPDATE users SET timezone = $1, updated_at = NOW() WHERE id = $2;

-- Toggle daily recap
UPDATE users SET daily_recap_enabled = $1, updated_at = NOW() WHERE id = $2;

-- Recalculate scheduled job after timezone change
UPDATE scheduled_jobs SET next_run_utc = $1 WHERE user_id = $2 AND job_type = 'daily_recap';
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Old token used post-regen | 200 OK + log (token not found) |
| 2 | Cross-Feature | Timezone change → jobs | Recalculate next_run_utc |
| 3 | Data Integrity | Invalid timezone | Validate against pytz.all_timezones |
| 4 | Cross-Feature | Recap toggle → scheduled_jobs | Update enabled flag |
| 5 | Security | User sees full token | Show last 6 chars only |
| 6 | Data Integrity | Token collision on regen | Retry with new token |
| 7 | Concurrency | 2 regen same time | Last write wins, UNIQUE OK |
| 8 | Cross-Feature | Regen while pending payment | Payment uses ref_code, not token |
| 9 | Security | Settings scope | WHERE user_id = $1 |
| 10 | Data Integrity | Timezone DST edge | pytz handles DST |
| 11 | Cross-Feature | Messenger persistent menu | Same settings via postback |
| 11b | Cross-Feature | Discord slash command | /settings slash command |
| 12 | Data Integrity | inbound_email immutable | Never changes (u{id}@domain) |

---

## 3. API Contract

### 3.1. Callback Data

```python
f"settings:regen"          # Regenerate token
f"settings:regen_confirm"  # Confirm regen
f"settings:tz"             # Start timezone change
f"settings:recap_toggle"   # Toggle recap
f"settings:upgrade"        # Redirect to /upgrade
```

---

## 4. Implementation Details

### 4.1. Timezone Validation

```python
import pytz
def validate_timezone(tz_str: str) -> bool:
    return tz_str in pytz.all_timezones

COMMON_TIMEZONES = [
    'Asia/Ho_Chi_Minh', 'Asia/Bangkok', 'Asia/Tokyo',
    'Asia/Singapore', 'America/New_York', 'Europe/London',
    'Australia/Sydney', 'Pacific/Auckland',
]
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | View settings | `/settings` | All fields displayed |
| 2 | Token display | Full token | Only last 6 shown |
| 3 | Regen token | Confirm | New token, old invalid |
| 4 | Old token used | Old token webhook | 200 OK, not found |
| 5 | Valid timezone | Asia/Ho_Chi_Minh | Updated |
| 6 | Invalid timezone | ABC | Rejected |
| 7 | Timezone → job recalc | Change TZ | next_run_utc updated |
| 8 | Recap ON→OFF | Toggle | enabled=FALSE |
| 9 | Recap OFF→ON | Toggle | enabled=TRUE, job rescheduled |
| 10 | Plan info display | Pro trial | Shows trial status |
| 11 | Token collision | Mock collision | Retry success |
| 12 | Concurrent regen | 2 requests | Both succeed, last wins |
| 13 | Messenger settings | Postback | Same behavior |
| 14 | User scope | Wrong user_id | Empty result |
| 15 | Inbound email display | u42@in.app | Full email shown |
| 16 | DST timezone | America/New_York | Handles DST |
| 17 | Bank connections list | 2 banks | Both shown |
| 18 | Upgrade redirect | settings:upgrade | /upgrade flow |
| 19 | Common TZ suggestions | Unknown TZ | Show common list |
| 20 | Settings on Messenger | Persistent menu | Quick replies |
| 20b | Settings on Discord | /settings slash | Embed + buttons |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
