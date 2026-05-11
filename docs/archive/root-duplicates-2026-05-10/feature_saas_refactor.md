# Feature: SaaS Refactor — Multi-tenant + Data Isolation

> **Version:** v1.0.0 (refactored từ feature-spec-refactor-saas v1.3.0)
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 1-2 (Tuần 1-4)
> **Tham chiếu:** [Original spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-refactor-saas.md)

---

## 1. Mô tả

Chuyển từ personal Telegram/Discord bot (Google Sheets, single-user) sang multi-tenant SaaS (PostgreSQL, multi-user). Bao gồm: DB migration, per-user data isolation, channel adapter pattern (Telegram/Discord/Messenger), outbound messaging abstraction, email parser plugin pattern. F08 (Multi-User Data Isolation) gộp vào đây vì cùng domain.

**Key decisions:**
- PostgreSQL (Railway-managed) thay Google Sheets
- Raw SQL (asyncpg) thay ORM
- Shared bot model (platform-owned, multi-tenant via `user_id`)
- `services/messenger.py` interface abstraction → channel adapters

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | System | Boot app | PostgreSQL connection pool init, health check |
| 2 | User A | `/start` → webhook arrives | Data scoped to user_id A, isolated |
| 3 | User B | `/status` | Chỉ thấy data của B, không thấy A |
| 4 | System | SePay webhook → process_transaction | Lookup user by token → scope all queries |
| 5 | System | Email inbound → parser | Lookup user by token → extract → scope |
| 6 | Admin | `/admin_user {id}` | Cross-tenant access (admin only) |
| 7 | System | Outbound message | `messenger.send(user_id, payload)` → adapter dispatch |
| 8 | System | New email bank added | Plugin parser loaded at runtime |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Query without user_id filter | Code review enforce: mọi query PHẢI có WHERE user_id |
| 2 | Data Integrity | DB connection pool exhaustion | Max pool size + queue + health alert |
| 3 | Concurrency | 500 users concurrent webhooks | asyncpg pool handles concurrent queries |
| 4 | Security | Token collision between users | UNIQUE constraint + 24-char random |
| 5 | Data Integrity | Google Sheets → PostgreSQL migration data | One-time script, validate row counts |
| 6 | Cross-Feature | Bot restart mid-transaction | bot_state table persists conversation state |
| 7 | Security | SQL injection via description field | Parameterized queries (asyncpg) |
| 8 | Data Integrity | Foreign key violation on INSERT | Proper FK constraints + error handling |
| 9 | Concurrency | Migration script runs during production | Maintenance window, app pause |
| 10 | Cross-Feature | Channel adapter missing for new channel | KeyError → fallback error message |

---

## 3. Screens & States

Refactor là backend concern — không có user-facing screens trực tiếp.

- **Loading:** N/A
- **Ready:** App boots, DB connected, endpoints responsive
- **Error:** Health check `/health` returns degraded status
- **Empty:** N/A

---

## 4. Domain Model

Full DDL: [TDD v1.6.0 §2.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)

**Key tables:** `users`, `categories`, `transactions`, `bot_state`, `bank_connections`, `scheduled_jobs`, `monthly_reports`, `analytics_events`, `admin_audit_log`

**Data isolation pattern:** Mọi query PHẢI có `WHERE user_id = $1` (ngoại trừ admin tools).

---

## 5. API Endpoints

| Method | Path | Source |
|--------|------|--------|
| POST | `/webhook/telegram` | Telegram Bot API |
| POST | `/webhook/discord` | Discord Interaction endpoint |
| POST | `/webhook/messenger` | Meta Page webhook |
| POST | `/hook/{token}` | SePay per-user |
| POST | `/inbound/{token}` | Postmark per-user |
| GET | `/` | Health check simple |
| GET | `/health` | Health check detailed |

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 500 | `DB_CONNECTION_FAIL` | N/A (internal) | PostgreSQL unreachable |
| 500 | `DB_POOL_EXHAUSTED` | N/A (internal) | Pool max reached |
| 200 | `TOKEN_INVALID` | N/A (silent 200) | Unknown webhook token |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `app_started` | Boot success | `version`, `db_pool_size` |
| `app_health_degraded` | Health check fail | `component`, `error` |
| `migration_completed` | Schema migration | `migration_id`, `duration_ms` |

---

## 8. State Machine

Không có state machine — refactor là infrastructure work.

### Migration Strategy
```
Phase 1 Legacy:  sheets.py → Google Sheets API → Google Sheets
Phase 1 Target:  db.py → asyncpg → PostgreSQL (Railway)

Steps:
1. Create DDL schema
2. Create db.py with same interface as sheets.py
3. Swap imports
4. Import founder's existing data
5. Remove sheets.py dependency
```

---

## 9. Caching Strategy

- **DB connection pool:** asyncpg managed pool (min=2, max=10)
- **User lookup cache:** LRU 5 phút per webhook_token
- **Channel adapter registry:** In-memory dict at startup

---

## 10. Acceptance Criteria

- [ ] PostgreSQL schema deployed, all tables created
- [ ] asyncpg connection pool stable (p95 query <50ms)
- [ ] All queries scoped by user_id (code audit)
- [ ] Google Sheets data migrated + validated
- [ ] `messenger.send()` abstraction working
- [ ] Channel adapters (Telegram/Discord/Messenger) dispatching correctly
- [ ] Health check endpoint responsive
- [ ] Zero cross-tenant data leaks (test with 2 users)
- [ ] Bot restart → state recovered from bot_state table

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Refactor từ feature-spec-refactor-saas v1.3.0 + F08 data isolation |
| v1.0.1 | 2026-05-08 | **i18n note:** `users.locale` column added to schema (TDD v1.7.0). Per-user locale scoped. |
