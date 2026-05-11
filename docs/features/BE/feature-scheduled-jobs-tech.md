# BE Tech Doc: Scheduled Jobs (F09)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-scheduled-jobs.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-scheduled-jobs.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Scheduler | `services/scheduler.py` | APScheduler setup, poll loop |
| Executor | `services/job_executor.py` | Execute individual job types |
| DB | `db.py` | Job CRUD, ready-to-run query |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Jobs ready to run
SELECT sj.*, u.channel_type, u.channel_user_id, u.timezone, u.plan, u.daily_recap_enabled
FROM scheduled_jobs sj
JOIN users u ON u.id = sj.user_id
WHERE sj.enabled = TRUE AND sj.next_run_utc <= NOW()
ORDER BY sj.next_run_utc
LIMIT 50;

-- Advance next_run_utc after execution
UPDATE scheduled_jobs SET last_run_utc = NOW(), next_run_utc = $1 WHERE id = $2;

-- Create default jobs for new user
INSERT INTO scheduled_jobs (user_id, job_type, enabled, next_run_utc) VALUES
($1, 'daily_recap', TRUE, $2),
($1, 'monthly_allocation', TRUE, $3)
ON CONFLICT (user_id, job_type) DO NOTHING;

-- Disable Pro-only jobs on downgrade
UPDATE scheduled_jobs SET enabled = FALSE WHERE user_id = $1 AND job_type IN ('weekly', 'monthly_report');
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | 500 users fire 23:00 | Jitter ±5min spread |
| 2 | Data Integrity | Job fail (DB/Telegram/Discord down) | Log, advance next_run, don't block |
| 3 | Cross-Feature | Downgrade Pro→Free | Disable weekly/monthly_report |
| 4 | Data Integrity | App restart mid-cycle | next_run_utc persisted, resume |
| 5 | Concurrency | Multi-instance deploy | Single instance MVP |
| 6 | Data Integrity | TZ change mid-cycle | Cancel + re-schedule |
| 7 | Cross-Feature | Recap disabled | enabled=FALSE, skip |
| 8 | Data Integrity | next_run in past | Run immediately, advance |
| 9 | Cross-Feature | Messenger 24h rule | MESSAGE_TAG ACCOUNT_UPDATE |
| 10 | Data Integrity | DST transition | Recalculate UTC via pytz |
| 11 | Concurrency | Telegram/Discord rate limit | Jitter spreads, retry backoff |
| 12 | Data Integrity | Job type unknown | Log warning, skip |

---

## 3. API Contract

### 3.1. Internal Trigger

```python
POST /trigger/{job_type}
# Admin-only, manual trigger for debugging
```

---

## 4. Implementation Details

### 4.1. Poll Loop

```python
async def scheduler_loop():
    while True:
        jobs = await db.get_ready_jobs(limit=50)
        for job in jobs:
            try:
                await execute_job(job)
                next_run = calculate_next_run(job)
                await db.advance_job(job.id, next_run)
            except Exception as e:
                log.error(f"Job {job.id} failed: {e}")
                next_run = calculate_next_run(job)  # Still advance
                await db.advance_job(job.id, next_run)
        await asyncio.sleep(60)  # Poll every 60s
```

### 4.2. Jitter Algorithm

```python
def calculate_jitter_offset(user_id: int) -> int:
    """Deterministic offset -5 to +5 minutes based on user_id."""
    return (hash(str(user_id)) % 11) - 5

def calculate_next_run(job) -> datetime:
    user_tz = pytz.timezone(job.timezone)
    if job.job_type == 'daily_recap':
        base = datetime.now(user_tz).replace(hour=23, minute=0, second=0) + timedelta(days=1)
    elif job.job_type == 'weekly':
        days_until_sunday = (6 - datetime.now(user_tz).weekday()) % 7 or 7
        base = datetime.now(user_tz).replace(hour=14, minute=0) + timedelta(days=days_until_sunday)
    # ... other job types
    offset = timedelta(minutes=calculate_jitter_offset(job.user_id))
    return (base + offset).astimezone(pytz.utc)
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Poll finds ready jobs | 3 jobs past due | All 3 executed |
| 2 | Poll skips future jobs | next_run = +1h | Not executed |
| 3 | Daily recap fire | 23:00 user TZ | Recap sent |
| 4 | Daily recap 0 tx | No tx today | Skip, no message |
| 5 | Weekly fire Sunday | Pro user, Sunday 14:00 | Report sent |
| 6 | Weekly Free user | Free user | Job disabled |
| 7 | Monthly allocation | 1st of month | Categories cloned |
| 8 | Trial reminder | Day 12 | Reminder message |
| 9 | Trial downgrade | Day 14 | Plan = free |
| 10 | Job fail recovery | DB error | Log, advance next_run |
| 11 | Jitter spread | user_id=1 vs 100 | Different offsets |
| 12 | Jitter range | 1000 users | All within ±5min |
| 13 | TZ change | Asia/Tokyo → UTC+9 | next_run recalculated |
| 14 | DST transition | America/New_York | Correct UTC conversion |
| 15 | Past next_run | Restart after 2h down | Jobs fire immediately |
| 16 | Downgrade disables | Pro→Free | weekly disabled |
| 17 | Upgrade enables | Free→Pro | weekly enabled+scheduled |
| 18 | New user auto-jobs | Signup | 2 jobs created |
| 19 | Duplicate job create | ON CONFLICT | No duplicate |
| 20 | Manual trigger | /trigger/daily_recap | Job executes |
| 21 | Messenger TAG | Recap for Messenger user | tag=ACCOUNT_UPDATE |
| 22 | Rate limit backoff | 30 msgs in burst | Spreads via jitter |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
