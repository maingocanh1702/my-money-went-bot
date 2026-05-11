# Feature: Scheduled Jobs (F09)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.9](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)

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

| Job | Schedule | Condition | Scope |
|-----|----------|-----------|-------|
| `daily_recap` | 23:00 ±5min jitter | enabled=TRUE, ≥1 tx | per-user |
| `trial_reminder` | Day 12 of trial | trial active | per-user |
| `trial_downgrade` | Day 14 of trial | trial active | per-user |
| `family_trial_reminder` | Day 12 of Family trial | family.status='trialing' | per-family |
| `family_trial_downgrade` | Day 14 of Family trial | family.status='trialing' | per-family |
| `weekly` | Sunday 14:00 ±5min | Pro+ only | per-user |
| `monthly_report` | Last day month 14:00 ±5min | Pro+ only | per-user |
| `monthly_allocation` | 1st of month 08:00 ±5min | All | per-user |
| `close_stale_memberships` 🆕 | Daily 03:00 UTC | family.status in (downgraded, cancelled), 90d past `downgraded_at`/`cancelled_at` | **global** (not per-user) |
| `expire_pending_invites` 🆕 | Hourly :00 | `family_invites.status='pending' AND expires_at < now()` | global |

### Family-related cron jobs (sync feature-family-plan.md §4.6 + §4.1)

**`close_stale_memberships`** — daily, global scope, idempotent

```python
def close_stale_memberships():
    """
    Sau 90 ngày kể từ family downgrade/cancel, close TẤT CẢ memberships
    (gồm owner) để unlock single-active-family invariant cho mọi user.
    Owner archived access qua `family_accounts.owner_user_id` direct check,
    không cần membership active.
    """
    cutoff = now() - timedelta(days=90)
    stale_families = db.query(FamilyAccount).filter(
        FamilyAccount.status.in_(["downgraded", "cancelled"]),
        or_(
            FamilyAccount.downgraded_at < cutoff,
            FamilyAccount.cancelled_at < cutoff,
        ),
    ).all()
    for fam in stale_families:
        db.query(FamilyMember).filter(
            FamilyMember.family_id == fam.id,
            FamilyMember.removed_at.is_(None),
        ).update({"removed_at": now()})
    db.commit()
```

**Key design rule:** Close ALL members (gồm owner). Nếu giữ owner membership forever, owner bị `uq_user_single_active_family` chặn join family mới. Owner archived access đi qua `can_view_archived_family(user_id, family_id)` (FAM §4.6) trực tiếp trên `family_accounts.owner_user_id`.

**`expire_pending_invites`** — hourly, global scope

```python
def expire_pending_invites():
    db.query(FamilyInvite).filter(
        FamilyInvite.status == "pending",
        FamilyInvite.expires_at < now(),
    ).update({"status": "expired"})
    db.commit()
```

**Idempotency:** Cả 2 job pure UPDATE — chạy lại không tạo side effect bất thường. OK nếu cron miss 1 chu kỳ, lần sau catch up tự nhiên.

**Failure handling:** Job fail → admin alert (Sentry), retry lần sau. Không block các job khác.

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
- [ ] **Family jobs:** `close_stale_memberships` chạy daily 03:00 UTC, close TẤT CẢ memberships (gồm owner) sau 90 ngày downgrade/cancel. Idempotent.
- [ ] **Family jobs:** `expire_pending_invites` chạy hourly, flip `pending → expired` cho row quá `expires_at`. Idempotent.
- [ ] **Family jobs:** Sau cron đóng owner membership, owner Pro vẫn xem được "Archived family" tab qua `can_view_archived_family()` direct check.
- [ ] **Family jobs:** Sau cron, owner có thể join/tạo family mới (không bị `uq_user_single_active_family` chặn).
- [ ] **Family trial reminders:** Day 12 + Day 14 fire đúng (track qua `family_accounts.trial_ends_at`, distinct from `users.trial_ends_at`).

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.9 |
| v1.1.0 | 2026-05-11 | **Family Plan cron jobs (sync feature-family-plan v1.0.0 §4.6):** (1) Thêm 4 job types: `family_trial_reminder` (Day 12 family trial), `family_trial_downgrade` (Day 14), `close_stale_memberships` (daily global, 90-day grace cho downgraded/cancelled family — close ALL members gồm owner để unlock single-active-family invariant), `expire_pending_invites` (hourly global, flip pending→expired). (2) Acceptance criteria mở rộng với 5 Family-specific checks. (3) Cross-ref FAM §4.6 cho behavior contract + `can_view_archived_family()` archived owner access. |
| v1.0.1 | 2026-05-08 | **i18n note:** Daily recap, weekly report, payment reminder messages served via `t(user.locale, key)`. |
