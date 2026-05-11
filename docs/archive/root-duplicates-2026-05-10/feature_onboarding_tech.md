# BE Tech Doc: 3-Path Onboarding (F01)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_onboarding.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_onboarding.md)
> **TDD ref:** [TDD v1.6.0 §2.1 users, §3.1 endpoints](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)

---

## 1. Implementation Overview

### 1.1. Module Map

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/onboarding.py` | Parse `/start` + postback → state machine |
| Service | `services/user_svc.py` | User CRUD, token generation |
| DB | `db.py` | `create_user()`, `get_user_by_channel()`, `upsert_bot_state()` |
| Channel | `services/messenger.py` | Outbound welcome + quick replies |

### 1.2. Entry Points

| Channel | Trigger | Handler |
|---------|---------|---------|
| Telegram | `/start` command | `handle_start(update)` |
| Discord | `/start` slash command (DM) | `handle_start(interaction)` |
| Messenger | `GET_STARTED` postback | `handle_get_started(update)` |

---

## 2. Database Schema

### 2.1. Tables Used

| Table | Operations | Scope |
|-------|-----------|-------|
| `users` | INSERT, SELECT | Create user, check existing |
| `bank_connections` | INSERT | Path A/B: create SePay connection |
| `bot_state` | UPSERT, DELETE | State machine steps |
| `scheduled_jobs` | INSERT | Auto-create daily_recap + monthly_allocation |

### 2.2. Key Queries

```sql
-- Idempotent user creation
INSERT INTO users (channel_type, channel_user_id, chat_id, webhook_token, inbound_email, plan, trial_ends_at, onboard_path)
VALUES ($1, $2, $3, $4, $5, 'free', NOW() + INTERVAL '14 days', NULL)
ON CONFLICT (channel_type, channel_user_id) DO NOTHING
RETURNING *;

-- Check existing user
SELECT * FROM users WHERE channel_type = $1 AND channel_user_id = $2;

-- Set onboard path
UPDATE users SET onboard_path = $1, updated_at = NOW() WHERE id = $2;

-- Create bank connection (Path A/B)
INSERT INTO bank_connections (user_id, type, bank_name, label) VALUES ($1, 'sepay', NULL, 'SePay Auto');

-- Auto-create scheduled jobs
INSERT INTO scheduled_jobs (user_id, job_type, enabled, next_run_utc)
VALUES ($1, 'daily_recap', TRUE, $2), ($1, 'monthly_allocation', TRUE, $3)
ON CONFLICT (user_id, job_type) DO NOTHING;
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | 2 `/start` cùng lúc | ON CONFLICT DO NOTHING → idempotent |
| 2 | Data Integrity | webhook_token collision | Retry với new token (UNIQUE constraint) |
| 3 | Security | Spoofed telegram_id | Validate via Telegram Bot API signature |
| 4 | Data Integrity | channel_user_id quá dài | VARCHAR(64) truncate + log |
| 5 | Cross-Feature | User đã tồn tại bấm /start lại | Return existing user, show current state |
| 6 | Concurrency | Trial calculation race | trial_ends_at = NOW() + 14d atomic |
| 7 | Data Integrity | Missing chat_id (Messenger) | NULL allowed, PSID dùng cho send |
| 8 | Security | Telegram webhook not from Bot API | Verify secret_token header |
| 9 | Cross-Feature | Scheduled jobs creation fail | User still created, jobs retry on next request |
| 10 | Data Integrity | inbound_email format collision | u{id}@domain — id auto-increment = unique |
| 11 | Concurrency | Path selection mid-onboarding restart | bot_state cleanup → re-prompt |
| 12 | Security | Path B wizard — SePay URL injection | Sanitize webhook_token output |

---

## 3. API Contract

### 3.1. Internal Functions

```python
async def create_or_get_user(channel_type: str, channel_user_id: str, chat_id: int = None) -> User:
    """Idempotent user creation. Returns existing if found."""

async def set_onboard_path(user_id: int, path: str) -> None:
    """Update onboard_path: 'sepay_quick' | 'sepay_wizard' | 'email'"""

async def generate_webhook_token() -> str:
    """24-char URL-safe random token. Retry on collision."""
```

### 3.2. Webhook Token Generation

```python
import secrets
def generate_webhook_token() -> str:
    return secrets.token_urlsafe(18)  # 24 chars
```

---

## 4. Implementation Details

### 4.1. State Machine (bot_state)

| Step | Payload | Next |
|------|---------|------|
| `NULL` (idle) | — | User sends `/start` → welcome |
| `await_path_selection` | `{}` | User selects A/B/C |
| `onboard_path_b_step1` | `{step: 1}` | SePay registration check |
| `onboard_path_b_step2` | `{step: 2}` | Bank connection |
| `onboard_path_b_step3` | `{step: 3}` | Webhook paste |
| `onboard_path_c_email_guide` | `{bank: 'gmail'}` | Email forwarding guide |

### 4.2. Token Format

- Webhook URL: `https://api.fintrack.app/hook/{webhook_token}`
- Inbound email: `u{user_id}@in.fintrack.app`

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Create new Telegram user | `/start`, telegram_id=123 | User created, trial 14d |
| 2 | Create new Messenger user | GET_STARTED, psid=456 | User created, channel_type=messenger |
| 3 | Idempotent creation | `/start` twice, same id | Same user returned |
| 4 | Token uniqueness | 1000 tokens | 0 collisions |
| 5 | Path A selection | Callback `ONBOARD_PATH_A` | onboard_path='sepay_quick', bank_connection created |
| 6 | Path B step 1 | Callback `ONBOARD_PATH_B` | bot_state step='onboard_path_b_step1' |
| 7 | Path B step 2 | Reply "✅ Đã đăng ký" | bot_state advances |
| 8 | Path B step 3 | Reply "✅ Đã dán" | bot_state cleared, onboard done |
| 9 | Path C selection | Callback `ONBOARD_PATH_C` | inbound_email generated |
| 10 | Path C email guide | Reply "📱 Gmail" | Guide message sent |
| 11 | Trial auto-assign | New user | trial_ends_at = NOW() + 14d |
| 12 | Scheduled jobs auto-create | New user | daily_recap + monthly_allocation rows |
| 13 | Channel type validation | channel_type='invalid' | Reject, CHECK constraint |
| 14 | Concurrent `/start` | 2 parallel requests, same user | 1 row created |
| 15 | Existing user re-start | `/start` for existing | Welcome back message |
| 16 | Bot state cleanup on restart | `/start` mid-onboarding | Clear old state |
| 17 | Webhook token collision | Mock collision then success | Retry generates new token |
| 18 | Invalid chat_id | chat_id=NULL for Telegram | Log warning, use telegram_id |
| 19 | Display name extraction | Telegram first+last name | Concatenated display_name |
| 20 | Messenger PSID format | 17-digit numeric string | Stored as channel_user_id |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
