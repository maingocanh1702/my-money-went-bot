# Feature: Admin Tools & Audit

> **Version:** v1.0.0 (refactored từ feature-spec-admin-tools v1.0.0)
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 1 foundation + Phase 6 payment admin
> **Tham chiếu:** [Original spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-admin-tools.md)

---

## 1. Mô tả

Admin tools qua Telegram bot commands cho founder + trusted contacts. Auth qua `ADMIN_TELEGRAM_IDS (+ ADMIN_DISCORD_IDS cho Discord admin)` env var (comma-separated). Mọi admin action ghi `admin_audit_log`. Scope: user lookup, plan management, payment manual review, system health.

**Non-goals:** Không build web dashboard cho MVP. CLI/Telegram đủ cho <100 users.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | Admin | `/admin_user {user_id}` | Xem user info: plan, tx count, bank connections |
| 2 | Admin | `/admin_plan {user_id} pro 30d` | Override plan + expiry |
| 3 | Admin | `/admin_unmatched` | List pending_review payments |
| 4 | Admin | `/admin_resolve {payment_id} {user_id}` | Manual link unmatched → user |
| 5 | Admin | `/admin_refund {match_id}` | Revoke plan + mark refunded |
| 6 | Admin | `/admin_health` | DB connections, uptime, queue size |
| 7 | Admin | `/admin_stats` | User count, MRR, churn |
| 8 | Admin | `/admin_broadcast {message}` | Gửi message tới all active users |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Non-admin gọi admin command | Silent ignore + log warning |
| 2 | Security | Admin ID bị remove khỏi env | Restart required, no dynamic reload |
| 3 | Data Integrity | Admin refund khi user đã downgrade | Still refund, no plan change needed |
| 4 | Concurrency | 2 admin resolve cùng payment | First write wins, second → error |
| 5 | Security | Admin broadcast tới 500 users | Rate limit 30 msg/s (Telegram limit) |
| 6 | Cross-Feature | Admin override plan → scheduled jobs | Recalculate jobs for new plan |
| 7 | Data Integrity | Admin delete user | Cascade delete via FK |
| 8 | Security | Audit log tamper attempt | Append-only table, no UPDATE/DELETE |
| 9 | Cross-Feature | Admin resolve unmatched → existing matched | Reject "Payment đã matched" |
| 10 | Data Integrity | Audit log disk full | Rotate old logs (>90 days archive) |

---

## 3. Screens & States

Admin tools là text-based responses trong Telegram chat. Không có UI screens.

### Admin Commands
- **Loading:** "⏳ Đang truy vấn..."
- **Ready:** Formatted text response
- **Error:** "⚠️ {error_message}"
- **Empty:** "Không tìm thấy kết quả."

---

## 4. Domain Model

```sql
CREATE TABLE admin_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    admin_telegram_id BIGINT NOT NULL,
    command         VARCHAR(64) NOT NULL,
    target_user_id  INTEGER REFERENCES users(id),
    payload         JSONB,
    result          VARCHAR(16),  -- 'success'|'fail'|'denied'
    error_message   TEXT,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Auth pattern:** Decorator-based

```python
def admin_only(handler):
    async def wrapper(update, context):
        if str(update.effective_user.id) not in ADMIN_IDS:
            log.warning(f"Unauthorized admin attempt: {update.effective_user.id}")
            return
        return await handler(update, context)
    return wrapper
```

---

## 5. API Endpoints

Không có REST API — admin commands qua Telegram bot `/webhook/telegram`.

| Command | Mô tả |
|---------|-------|
| `/admin_user {id}` | User lookup |
| `/admin_plan {id} {plan} {days}` | Override plan |
| `/admin_unmatched` | List unmatched payments |
| `/admin_resolve {pid} {uid}` | Manual link payment |
| `/admin_refund {mid}` | Refund + revoke |
| `/admin_health` | System health |
| `/admin_stats` | Business metrics |

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 403 | `ADMIN_UNAUTHORIZED` | N/A (silent) | Non-admin |
| 404 | `ADMIN_USER_NOT_FOUND` | "User {id} không tồn tại." | Invalid user_id |
| 409 | `ADMIN_ALREADY_MATCHED` | "Payment đã matched." | Resolve duplicate |
| 400 | `ADMIN_INVALID_PLAN` | "Plan phải là free/pro/business." | Invalid input |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `admin_command_executed` | Any admin command | `admin_id`, `command`, `target_user_id` |
| `admin_plan_override` | Plan change | `admin_id`, `user_id`, `old_plan`, `new_plan` |
| `admin_payment_resolved` | Manual resolve | `admin_id`, `payment_id`, `user_id` |
| `admin_refund_processed` | Refund | `admin_id`, `match_id`, `amount` |
| `admin_unauthorized_attempt` | Non-admin try | `telegram_id` |

---

## 8. State Machine

Admin tools không có state machine — request-response pattern.

### Admin Workflow: Unmatched Payment Resolution
```
1. Alert "⚠️ Unmatched payment" → admin Telegram
2. Admin `/admin_unmatched` → list pending_review
3. Admin cross-check bank statement
4. Admin `/admin_resolve {pid} {uid}` → match + upgrade
   OR Admin decides → refund manually + `/admin_refund`
```

---

## 9. Caching Strategy

- **Admin commands:** Không cache (low frequency, need fresh data)
- **ADMIN_IDS:** In-memory set, loaded at startup

---

## 10. Acceptance Criteria

- [ ] Admin auth: chỉ `ADMIN_TELEGRAM_IDS (+ ADMIN_DISCORD_IDS cho Discord admin)` execute được admin commands
- [ ] Non-admin → silent ignore + audit log
- [ ] Mọi admin action ghi `admin_audit_log`
- [ ] User lookup hiện đầy đủ info
- [ ] Plan override hoạt động + recalculate scheduled jobs
- [ ] Unmatched payment list + manual resolve
- [ ] Refund flow: revoke plan + mark refunded
- [ ] Health check: DB connections, uptime

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Refactor từ feature-spec-admin-tools → chuẩn 10-section |
| v1.0.1 | 2026-05-08 | **i18n note:** Admin messages are ENGLISH HARDCODED (not served via `t()`). Admin = founder only, no i18n overhead. |
