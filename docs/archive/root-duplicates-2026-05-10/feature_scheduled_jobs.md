# Feature: Scheduled Jobs (F09)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD v1.5.0 §3.9](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-en.md)

---

## 1. Mô tả

APScheduler in-process quản lý per-user scheduled jobs: daily recap, trial reminder/downgrade, weekly/monthly report, monthly allocation reset. Timezone-aware với jitter ±5 phút để tránh burst.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | System | 23:00 user timezone | Daily recap gửi (nếu ≥1 tx) |
| 2 | System | Day 12 of trial | Trial reminder |
| 3 | System | Day 14 of trial | Auto-downgrade Free |
| 4 | System | Sunday 14:00 | Weekly report (Pro+) |
| 5 | System | Last day of month 14:00 | Monthly report (Pro+) |
| 6 | System | 1st of month 08:00 | Monthly allocation reset |
| 7 | System | New user signup | Auto-create daily_recap + monthly_allocation jobs |
| 8 | User | Đổi timezone | Recalculate next_run_utc |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | 500+ users fire 23:00 cùng lúc | Jitter ±5min: `offset = hash(user_id) % 11 - 5` |
| 2 | Data Integrity | Job fail (DB error, Telegram/Discord down) | Log error, không block jobs khác |
| 3 | Cross-Feature | User downgrade Pro → Free | Disable weekly/monthly jobs |
| 4 | Data Integrity | App restart giữa job cycle | APScheduler recover từ DB state |
| 5 | Concurrency | Multi-instance deploy | Single instance MVP. Multi → Postgres job queue |
| 6 | Data Integrity | Timezone thay đổi khi job đang pending | Cancel + re-schedule |
| 7 | Cross-Feature | Daily recap disabled | Job exists but `enabled=FALSE` |
| 8 | Data Integrity | next_run_utc trong quá khứ (catch up) | Run immediately, advance to next cycle |
| 9 | Cross-Feature | Messenger 24h rule cho scheduled messages | Dùng MESSAGE_TAG ACCOUNT_UPDATE |
| 10 | Cross-Feature | Discord scheduled messages | DM anytime (no window restriction) |
| 10 | Data Integrity | DST transition | Recalculate UTC offset, pytz handles |

---

## 3. Screens & States

Scheduled jobs không có UI riêng — output hiện dưới dạng messages (daily recap, reports).

- **Loading:** N/A (background)
- **Ready:** Messages gửi đúng giờ
- **Error:** Admin alert nếu job fail
- **Empty:** N/A

---

## 4. Domain Model

```sql
CREATE TABLE scheduled_jobs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    job_type    VARCHAR(32) NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_utc TIMESTAMPTZ,
    last_run_utc TIMESTAMPTZ,
    config      JSONB DEFAULT '{}',
    UNIQUE(user_id, job_type)
);
CREATE INDEX idx_jobs_next_run ON scheduled_jobs(next_run_utc) WHERE enabled = TRUE;
```

### Job Types

| Job | Schedule | Condition |
|-----|----------|-----------|
| `daily_recap` | 23:00 ±5min jitter | enabled=TRUE, ≥1 tx |
| `trial_reminder` | Day 12 of trial | trial active |
| `trial_downgrade` | Day 14 of trial | trial active |
| `weekly` | Sunday 14:00 ±5min | Pro+ only |
| `monthly_report` | Last day month 14:00 ±5min | Pro+ only |
| `monthly_allocation` | 1st of month 08:00 ±5min | All |

---

## 5. API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/trigger/{job_type}` | Manual trigger (internal/admin) |

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 500 | `JOB_EXEC_FAIL` | N/A (admin alert only) | Job execution error |
| 404 | `JOB_NOT_FOUND` | "Job type không tồn tại." | Invalid job_type |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `job_executed` | Job run thành công | `user_id`, `job_type`, `duration_ms` |
| `job_failed` | Job run thất bại | `user_id`, `job_type`, `error` |
| `job_skipped` | Skip (vd 0 tx cho recap) | `user_id`, `job_type`, `reason` |

---

## 8. State Machine

Jobs không có state machine — chạy theo schedule, fire-and-forget.

### Jitter Algorithm
```python
offset_min = hash(user_id) % 11 - 5  # range [-5, +5] phút
fire_time = base_time + timedelta(minutes=offset_min)
```

### Timeout Spec

| Job | Fire window | Behavior khi miss |
|-----|-------------|-------------------|
| daily_recap | 22:55-23:05 | Skip (không catch up) |
| weekly | 13:55-14:05 Sunday | Run next Sunday |
| monthly_report | 13:55-14:05 last day | Skip month đó |

---

## 9. Caching Strategy

- **Jobs ready to run:** Query `WHERE next_run_utc <= NOW() AND enabled = TRUE` mỗi 60s
- **User timezone:** Cache in-process per job cycle

---

## 10. Acceptance Criteria

- [ ] APScheduler polls scheduled_jobs table per user
- [ ] Timezone-aware: next_run_utc tính từ user timezone
- [ ] Job failure không block jobs khác
- [ ] New users auto-get daily_recap + monthly_allocation
- [ ] Jitter ±5min deterministic theo user_id
- [ ] Scheduled jobs isolated per user
- [ ] Telegram/Discord rate limit respected (spread via jitter)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.9 |
| v1.0.1 | 2026-05-08 | **i18n note:** Daily recap, weekly report, payment reminder messages served via `t(user.locale, key)`. |
