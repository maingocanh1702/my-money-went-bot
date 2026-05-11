# BE Tech Doc: SaaS Refactor — Multi-tenant + Data Isolation

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-saas-refactor.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| DB Layer | `db.py` | asyncpg pool, all queries |
| Messenger | `services/messenger.py` | Outbound routing |
| Adapter Base | `services/channels/base.py` | BaseSender ABC |
| Telegram | `services/channels/telegram.py` | TelegramSender |
| Config | `config.py` | Env vars, constants |
| Migration | `scripts/migrate_sheets.py` | Google Sheets → PostgreSQL |

---

## 2. Database Schema

> Full DDL: [TDD-vi v1.8.1 §2.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)

### 2.1. Connection Pool Config

```python
pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=10,
    command_timeout=30,
    statement_cache_size=100,
)
```

### 2.2. Data Isolation Pattern

```python
# EVERY query MUST include user_id scope
async def get_categories(user_id: int, month_key: str):
    return await pool.fetch(
        "SELECT * FROM categories WHERE user_id = $1 AND month_key = $2 AND active = TRUE",
        user_id, month_key
    )
# NEVER: SELECT * FROM categories WHERE month_key = $2 (missing user_id!)
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Query without user_id | Code review enforce |
| 2 | Data Integrity | Pool exhaustion | Max pool + health alert |
| 3 | Concurrency | 500 concurrent webhooks | asyncpg pool handles |
| 4 | Security | Token collision | UNIQUE + 24-char random |
| 5 | Data Integrity | Migration data loss | Validate row counts |
| 6 | Cross-Feature | Bot restart mid-state | bot_state persists |
| 7 | Security | SQL injection | Parameterized queries |
| 8 | Data Integrity | FK violation | Proper constraints + error handling |
| 9 | Concurrency | Migration during production | Maintenance window |
| 10 | Cross-Feature | Missing adapter | KeyError → error log |
| 11 | Data Integrity | Connection timeout | Retry with backoff |
| 12 | Security | DATABASE_URL leak | Env var only, never log |

---

## 3. API Contract

### 3.1. Channel Adapter Pattern

```python
# services/messenger.py
ADAPTERS = {
    'telegram': TelegramSender(),
    'messenger': MessengerSender(),
    'discord': DiscordSender(),
}

async def send(user_id: int, payload: dict):
    user = await db.get_user(user_id)
    adapter = ADAPTERS.get(user.channel_type)
    if not adapter:
        log.error(f"Unknown channel: {user.channel_type}")
        return
    if payload['type'] == 'text':
        await adapter.send_text(user, payload['text'], payload.get('reply_markup'), payload.get('tag'))
    elif payload['type'] == 'image':
        await adapter.send_image(user, payload['url'], payload.get('caption'), payload.get('tag'))
```

### 3.2. Health Check

```python
@app.get("/health")
async def health():
    pool = db.get_pool()
    try:
        await pool.fetchval("SELECT 1")
        return {"status": "ok", "pool_size": pool.get_size(), "pool_free": pool.get_idle_size()}
    except:
        return JSONResponse(status_code=503, content={"status": "degraded"})
```

---

## 4. Implementation Details

### 4.1. Migration Script

```python
async def migrate_from_sheets():
    """One-time migration: Google Sheets → PostgreSQL."""
    sheets_data = await fetch_all_sheets()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for user in sheets_data['users']:
                await conn.execute("INSERT INTO users ...")
            for cat in sheets_data['categories']:
                await conn.execute("INSERT INTO categories ...")
            for tx in sheets_data['transactions']:
                await conn.execute("INSERT INTO transactions ...")
    # Validate counts
    assert await conn.fetchval("SELECT COUNT(*) FROM users") == len(sheets_data['users'])
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Pool creation | DATABASE_URL | Pool created, min=2 |
| 2 | Pool exhaustion | 15 concurrent queries | Queued, not crash |
| 3 | Health check OK | DB running | {"status": "ok"} |
| 4 | Health check fail | DB down | 503 degraded |
| 5 | User scoped query | user_id=1 | Only user 1 data |
| 6 | Cross-user isolation | user_id=1 vs 2 | No data leak |
| 7 | Adapter dispatch Telegram | channel_type=telegram | TelegramSender called |
| 8 | Adapter dispatch Messenger | channel_type=messenger | MessengerSender called |
| 9 | Unknown adapter | channel_type=zalo | Error logged |
| 10 | Parameterized query | SQL injection input | Escaped safely |
| 11 | Token uniqueness | 10000 tokens | 0 collisions |
| 12 | Connection timeout | Slow query >30s | Timeout error |
| 13 | Transaction rollback | Error mid-insert | All rolled back |
| 14 | bot_state persist | Crash mid-flow | State recovered |
| 15 | Migration validate | 100 rows | Count matches |
| 16 | send_text routing | user channel=telegram | sendMessage called |
| 17 | send_image routing | user channel=messenger | Meta API called |
| 18 | ENV var missing | DATABASE_URL unset | Startup fail with clear error |
| 19 | Pool min/max | Config check | min=2, max=10 |
| 20 | Graceful shutdown | SIGTERM | Pool closed, connections drained |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
