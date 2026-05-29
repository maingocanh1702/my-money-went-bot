# Zalo Channel Core Implementation Plan

| Field | Value |
|-------|-------|
| Version | v0.6.0 |
| Tạo ngày | 2026-05-28 |
| Cập nhật | 2026-05-28 |
| Tác giả | Antigravity (review & rewrite) |
| Trạng thái | ✅ Core implemented locally — pending live Zalo OA fixture/manual verification |
| Liên quan | [feature-messenger-channel.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md), [0001_initial_schema.py](file:///Users/maingocanh/Projects/MyMoneyWent/migrations/versions/0001_initial_schema.py) |

### Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v0.1.0 | 2026-05-28 | Draft gốc — scope V1, messenger adapter, webhook route, numbered category flow |
| v0.2.0 | 2026-05-28 | Rewrite sau review 13 issues: fix webhook auth (X-ZEvent-Signature), thêm OAuth token lifecycle, fix schema (channel_chat_id TEXT), fix migration DROP+ADD, thêm categorize.py handler, queue-based concurrent categorization, env vars spec, tech debt section |
| v0.3.0 | 2026-05-28 | Incorporate review findings: mark Zalo webhook signature/payload as live-fixture-gated, clarify OAuth v4 facts verified from Zalo docs, soften `/today`/`/report` acceptance until core builders exist, require API Explorer/manual probe before hardcoding send limits and signature parser |
| v0.4.0 | 2026-05-28 | Cowork review round: (1) move category picker trigger from `_persist()` to `handle_sepay_webhook()` orchestration layer, (2) `_persist()` must return `int | None` so caller knows if row was inserted (avoid duplicate pickers on webhook retries), (3) explicitly document `User` dataclass + `_row_to_user()` + INSERT query updates for `channel_chat_id`, (4) reword `bot_state` PK tech debt — current PK works fine when Telegram migrates; only needs change if user model moves to multi-channel-per-user |
| v0.5.0 | 2026-05-28 | Implementation pass: added Zalo sender, `/zalo/webhook` route, Zalo text parser/signature candidate, DB-backed category queue, SePay inserted-id orchestration, and unit/route/contract tests. Remaining gate is live Zalo OA webhook fixture + manual send verification. |
| v0.6.0 | 2026-05-28 | Post-review fixes: (1) migrate all hardcoded ASCII Vietnamese in `categorize.py` + `zalo_webhook.py` to i18n keys (`categorize.*` — 11 keys in vi.py + en.py, parity-tested), (2) fix plan TTL from 30min to 6h matching `_QUEUE_TTL`, (3) document HMAC-SHA256 vs plain SHA256 discrepancy in signature code block, (4) `_env_bool` dedup deferred — only 2 Zalo-specific occurrences |

---

## Summary

Build Zalo as a first-class core channel beside Telegram, using the existing `core.messenger` abstraction and PostgreSQL multi-tenant model. Do not expand the deprecated `sheets.py` / legacy `handlers/*` path. V1 supports Zalo `/start`, read-only commands, transaction notifications, and numbered parent-category selection; sub-category flows stay out of scope until the core schema has a sub-category model.

## Verification Status

**Verified enough to plan against**:

- Repo architecture: `core.messenger` and PostgreSQL multi-tenant schema already exist; `sheets.py`, legacy `handlers/*`, and legacy Google Sheets state are deprecated.
- Zalo OAuth v4 docs confirm `https://oauth.zaloapp.com/v4/oa/access_token`, `grant_type=refresh_token`, `app_id`, `refresh_token`, `secret_key` header, JSON response with `access_token`, `refresh_token`, and `expires_in`.
- Zalo OAuth docs state access tokens expire after 25 hours.
- Zalo consultation-message endpoint is expected to be `POST https://openapi.zalo.me/v3.0/oa/message/cs`, but must still be tested with API Explorer / real OA credentials.

**Implemented in repo**:

- `core.messenger.zalo.ZaloSender` registered under `channel_type='zalo'`.
- `POST /zalo/webhook` route behind `ZALO_ENABLED` / `ZALO_INTERACTIVE`.
- `core.handlers.categorize` with DB `bot_state` queue for numbered parent-category selection.
- SePay handler now distinguishes new inserts from duplicate webhook retries and only triggers category picker on new rows.
- Tests added for sender, parser/signature candidate, FastAPI route wiring, category rendering, and messenger contract.

**Must verify before implementation hardcodes behavior**:

- Exact webhook signature formula and required headers (`X-ZEvent-Signature`, timestamp placement, raw body encoding).
- Exact webhook payload shape for text messages from the chosen Zalo product surface.
- Exact outbound text length limit for the chosen API. Keep chunking configurable until the first successful manual send confirms 2000 vs 640 chars.
- Whether `sender.id` is sufficient for both `channel_user_id` and outbound `recipient.user_id`; capture a real webhook fixture and one successful send response before merging.

## Key Changes

### 1. DB: Alembic migration `0004_add_zalo_channel`

**Extend `chk_channel_type` CHECK constraint** (Postgres does not support ALTER CHECK inline — must DROP + re-ADD):

```sql
-- Step 1: Drop existing constraint
ALTER TABLE users DROP CONSTRAINT chk_channel_type;

-- Step 2: Re-add with 'zalo' included
ALTER TABLE users ADD CONSTRAINT chk_channel_type
    CHECK (channel_type IN ('telegram', 'messenger', 'discord', 'zalo'));
```

**Add `channel_chat_id TEXT NULL`** for non-numeric / overflow-BIGINT platform routing IDs (Zalo IDs can be 19+ digit strings that overflow BIGINT max 9.2×10¹⁸):

```sql
ALTER TABLE users ADD COLUMN channel_chat_id TEXT NULL;

CREATE INDEX idx_users_channel_chat_id
    ON users(channel_chat_id)
    WHERE channel_chat_id IS NOT NULL;
```

Decision rationale: Adding a new column is preferred over migrating `chat_id BIGINT → TEXT` because it avoids breaking Telegram queries that rely on integer `chat_id` throughout the codebase (TelegramSender._resolve_chat_id returns `int`).

**Update `core.services.user_svc`**:

- **`User` dataclass**: Add field `channel_chat_id: str | None` (after `chat_id`).
- **`_row_to_user()`**: Map `row["channel_chat_id"]` to the new field.
- **`create_or_get_user()`**:
  - Add optional param `channel_chat_id: str | None = None`.
  - INSERT query: add `channel_chat_id` as new column + positional param (`$6`).
  - Self-heal backfill: same pattern as existing `chat_id` backfill — if `channel_chat_id` is provided and existing row has NULL, UPDATE it.

**Update `core.handlers.start.handle_start()`**:

- Add optional param `channel_chat_id: str | None = None`.
- Pass through to `create_or_get_user(channel_chat_id=channel_chat_id)`.

### 2. Zalo messenger adapter: `core/messenger/zalo.py`

Implement `ZaloSender(BaseSender)` registered via `@register_sender("zalo")`.

**Routing**: Resolve recipient by `users.channel_chat_id`, fallback `users.channel_user_id`. Return value is `str` (not `int` like TelegramSender).

**Outbound API**: POST to `https://openapi.zalo.me/v3.0/oa/message/cs` with:

```json
{
  "recipient": { "user_id": "<resolved_user_id>" },
  "message": { "text": "<plain_text>" }
}
```

Header: `access_token: <ZALO_OA_ACCESS_TOKEN>`.

**Access token management**: Zalo OA access tokens expire every ~25 hours. V1 approach:

- Store `ZALO_OA_ACCESS_TOKEN` and `ZALO_OA_REFRESH_TOKEN` as env vars (Railway secrets).
- On 401 response → auto-refresh via `POST https://oauth.zaloapp.com/v4/oa/access_token` with form fields `grant_type=refresh_token`, `app_id`, `refresh_token`, and header `secret_key`.
- After refresh, new `access_token` + new `refresh_token` are returned. **V1 limitation**: new refresh_token must be manually updated in Railway secrets until we build a persistent token store (V2).
- Log a CRITICAL alert when refresh succeeds so operator updates the Railway env var.
- Alternative V1: use Zalo API Explorer to generate long-lived test tokens for initial development.
- Implementation note: token refresh may be disabled behind `ZALO_AUTO_REFRESH=false` for the first PR if we want to avoid production ambiguity. In that case, expired token sends log a clear operator action and do not retry endlessly.

**Text rendering**:

- Render `SendPayload` text as plain text; strip/ignore Markdown parse mode.
- `Markup` with `callback_data` buttons → numbered plain-text options: `1. Label\n2. Label\n...`
- `Markup` with `url` buttons → plain link lines: `🔗 Label: https://...` (not numbered, not selectable by reply).
- Chunk outbound text using a configurable `ZALO_TEXT_LIMIT` defaulting to **2000 chars**. If the first manual/API Explorer send proves the selected API rejects above 640 chars, set default to 600 with safety margin before enabling production fan-out.

**Side-effect import**: Add `from . import zalo as _zalo  # noqa: F401` in `core/messenger/__init__.py` (same pattern as telegram import).

### 3. Zalo webhook route: `POST /zalo/webhook`

Add in `main.py`, guarded by `ZALO_ENABLED=true` and `ZALO_INTERACTIVE=true`.

**Webhook signature verification** (Zalo uses `X-ZEvent-Signature` header, NOT Telegram-style `X-Bot-Api-Secret-Token`):

```python
# Candidate Zalo signature formula — MUST be confirmed against a real webhook fixture
# before merging implementation.
# Plan originally specified: sha256(app_id + raw_body + timestamp + oa_secret_key)
# Implementation uses: HMAC-SHA256(secret_key, raw_body) which is more secure.
# The correct formula will be determined by the first real webhook fixture.
import hashlib

def _verify_zalo_signature(
    header_signature: str,
    app_id: str,
    raw_body: str,
    timestamp: str,
    oa_secret_key: str,
) -> bool:
    computed = hashlib.sha256(
        (app_id + raw_body + timestamp + oa_secret_key).encode()
    ).hexdigest()
    return hmac.compare_digest(computed, header_signature)
```

Required env vars: `ZALO_APP_ID`, `ZALO_OA_SECRET_KEY`, `ZALO_OA_ACCESS_TOKEN`, `ZALO_OA_REFRESH_TOKEN`.

**Implementation gate**: Before wiring this check into production, capture one real webhook request from Zalo and add it as a sanitized fixture test: raw body, relevant headers, expected signature result, and parsed event fields. If the real signature formula differs, update this section and implementation together.

**Candidate webhook event body** (Zalo `user_send_text` event; confirm with live fixture):

```json
{
  "app_id": "...",
  "sender": { "id": "246845883529197922" },
  "user_id_by_app": "552177279717587730",
  "recipient": { "id": "388613280878808645" },
  "event_name": "user_send_text",
  "message": { "text": "/start", "msg_id": "..." },
  "timestamp": "154390853474"
}
```

**Dispatch logic**:

- Accept only `event_name == "user_send_text"`.
- Ignore events where `sender.id` is missing.
- Extract text from `message.text`.

**Command routing**:

| Command | Action |
|---------|--------|
| `/start` | Call `core.handlers.start.handle_start(channel_type="zalo", channel_user_id=sender.id, channel_chat_id=sender.id)` |
| `/today`, `/report`, `/accounts` | Best-effort only if core read builders exist; otherwise return "Hiện tại chỉ hỗ trợ qua Telegram" |
| Numeric reply (`1`, `2`, ...) | Route to `core/handlers/categorize.py` numbered reply resolver |
| Anything else | Return help text |

**Note on Zalo IDs**: V1 assumes `sender.id` serves as both user identifier and routing target for outbound messages. Confirm this with one successful reply/send before enabling `ZALO_INTERACTIVE=true` in production. Both `channel_user_id` and `channel_chat_id` will be set to `sender.id` only after that confirmation.

### 4. Numbered category flow: `core/handlers/categorize.py` (NEW)

Decoupled core handler for post-transaction category selection, called from `markets/vn/capture/sepay_webhook.py`.

**Trigger point**: In `handle_sepay_webhook()`, AFTER `_persist()` returns. `_persist()` is a pure DB function and MUST NOT contain messaging side-effects. The orchestration layer (`handle_sepay_webhook`) owns the decision to send notifications.

**`_persist()` return value change**: Currently `_persist()` returns `None` and uses `ON CONFLICT DO NOTHING` without `RETURNING`. To avoid sending duplicate category pickers on SePay webhook retries, `_persist()` must be modified to return the inserted transaction ID (or `None` if the row already existed):

```python
async def _persist(user_id: int, tx: CanonicalTx, month_key: str) -> int | None:
    """Persist transaction. Returns tx_id if newly inserted, None if duplicate."""
    # ... existing ref_code logic ...
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO transactions
                (user_id, tx_date, description, direction, amount,
                 ref_code, source, month_key)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id, ref_code) DO NOTHING
            RETURNING id;
            """,
            user_id, tx.tx_date, tx.description, tx.direction,
            tx.amount, ref_code, tx.source, month_key,
        )
    return int(row["id"]) if row is not None else None
```

Then in `handle_sepay_webhook()`:

```python
tx_id = await _persist(user_id, tx, month_key)
if tx_id is not None:
    log.info("sepay.webhook.persisted", ...)
    # Only send category picker for genuinely new transactions
    from core.handlers.categorize import send_category_picker
    await send_category_picker(user_id=user_id, tx_id=tx_id)
else:
    log.info("sepay.webhook.duplicate_skipped", ref_code=...)
```

This sends the user a channel-abstract category picker using active parent categories for the current month.

**Queue-based concurrent categorization**: When multiple transactions arrive before the user replies, pending categorizations are queued in `bot_state.payload`:

```json
{
  "step": "await_category",
  "payload": {
    "queue": [
      {
        "tx_id": 123,
        "options": [
          {"number": 1, "category_id": 5, "label": "Chi tiêu hàng ngày"},
          {"number": 2, "category_id": 6, "label": "Tiết kiệm"},
          {"number": 3, "category_id": 7, "label": "Đăng ký dịch vụ"}
        ],
        "created_at": "2026-05-28T10:00:00Z"
      },
      {
        "tx_id": 124,
        "options": [...],
        "created_at": "2026-05-28T10:00:05Z"
      }
    ],
    "expires_at": "2026-05-28T10:30:00Z"
  }
}
```

- First item in `queue` is the "active" one shown to the user.
- When user replies `1`/`2`/etc: validate against active item, update `transactions.category_id`, set `confirmed=true`, shift queue, send next picker or confirmation if queue empty.
- New transactions arriving while queue is active: append to `queue`, send "Bạn có thêm giao dịch cần phân loại — hoàn tất cái hiện tại trước nhé" info message.
- `expires_at` is TTL for the entire queue (6 hours from first item, matching `_QUEUE_TTL` in implementation). Renewed on each new item appended.

**bot_state conflict avoidance**: V1 assumption — Telegram legacy continues using Google Sheets state (`sh.get_state(CHAT_ID)`), only Zalo uses DB `bot_state` table. No conflict because:

1. Telegram `/start` uses core `handle_start()` but all other Telegram flows use legacy Sheets state.
2. Zalo category flow uses DB `bot_state` exclusively.
3. Each `user_id` implies exactly one `channel_type` (via `UNIQUE(channel_type, channel_user_id)` on `users`), so `bot_state` PK `user_id` is sufficient even when Telegram eventually migrates to DB state. See Tech Debt §1 for the only scenario requiring PK change.

**Edge case handling**:

| Case | Behavior |
|------|----------|
| Invalid number | Send "Số không hợp lệ, vui lòng chọn lại" + re-show options |
| Expired state (past `expires_at`) | Send "Thời gian phân loại đã hết. Bạn có thể phân loại sau qua /manage" |
| Duplicate webhook (same tx_id already in queue) | Skip silently |
| Unauthorized sender | Ignore event |
| Group chat / non-text event | Ignore event |
| Queue empty but user sends number | Send "Không có giao dịch nào cần phân loại" |

**No background TTL cleanup needed**: Expired states are checked lazily on next user interaction. Stale `bot_state` rows with expired payloads are harmless (overwritten on next transaction).

### 5. Env vars to add

| Var | Required | Description |
|-----|----------|-------------|
| `ZALO_ENABLED` | Yes | `true` to enable Zalo webhook route |
| `ZALO_INTERACTIVE` | Yes | `true` to enable Zalo interactive commands |
| `ZALO_TEXT_LIMIT` | No | Outbound text chunk limit; default 2000 until manual verification proves a lower limit |
| `ZALO_AUTO_REFRESH` | No | `true` to attempt OAuth refresh on 401; default can stay `false` in first PR |
| `ZALO_APP_ID` | Yes | Zalo app ID from developer console |
| `ZALO_OA_SECRET_KEY` | Yes | OA secret key for webhook signature verification |
| `ZALO_OA_ACCESS_TOKEN` | Yes | OAuth access token for send API (expires ~25h) |
| `ZALO_OA_REFRESH_TOKEN` | Yes | OAuth refresh token (single-use, 3-month validity) |

## Test Plan

### Unit

- `ZaloSender` validates payload contract, sends plain text, chunks over 2000 chars (and 600 if limit proves to be 640), resolves recipient from `channel_chat_id`.
- `Markup` with `callback_data` buttons renders to numbered text in deterministic order.
- `Markup` with `url` buttons renders as plain link lines (not numbered).
- Zalo webhook signature verification: correct signature passes, wrong signature rejects.
- Zalo webhook signature fixture: sanitized real raw body + headers verify successfully before production auth is enabled.
- Webhook event parser extracts `sender.id`, `message.text`, handles missing fields gracefully.
- Numbered reply resolver maps valid numbers and rejects invalid/expired replies.
- Queue logic: append, shift, empty, duplicate tx_id detection.
- Access token refresh: 401 triggers refresh, new tokens are used on retry.
- `_persist()` returns `int` on new insert, `None` on duplicate (ON CONFLICT).

### Integration

- Migration `0004` permits inserting `users(channel_type='zalo')` and `channel_chat_id`.
- Migration `0004` DROP + ADD constraint works with existing data (no rows have channel_type outside the new constraint).
- `create_or_get_user(channel_type="zalo", channel_chat_id="2911254799136969152")` inserts correctly; `User` dataclass includes `channel_chat_id` field.
- `create_or_get_user()` self-heals `channel_chat_id` on re-call (same pattern as `chat_id` backfill).
- `/zalo/webhook` rejects bad signature, disabled flags, non-text events.
- Zalo `/start` creates or reuses a user row and seeds default categories.
- `/today`, `/report`, `/accounts` either return core data if builders exist or a clear Telegram-only fallback; they are not required to call legacy report handlers.
- SePay insert for a Zalo user: `_persist()` returns tx_id → `handle_sepay_webhook()` calls `send_category_picker` → `bot_state` row created.
- SePay duplicate webhook: `_persist()` returns `None` → no category picker sent.
- Reply `1` confirms the correct transaction category and shifts queue.
- Second concurrent SePay transaction appends to queue correctly.
- Queue exhaustion sends final confirmation and clears `bot_state`.
- Telegram existing tests still pass — messenger contract, `/start`, legacy Sheets state untouched.

### Manual

- Configure Zalo OA credentials in Railway.
- Set webhook URL in Zalo Developer Console.
- Capture and save a sanitized webhook fixture before implementing final signature parsing.
- Use API Explorer or a one-off local probe to confirm `recipient.user_id`, send endpoint, and text length limit.
- Send `/start` from Zalo and confirm user row has `channel_type='zalo'` and `channel_chat_id` populated.
- Trigger one small SePay transaction and confirm Zalo receives numbered category choices.
- Reply with `1` and verify the transaction row is confirmed with the expected category.
- Trigger 2 rapid SePay transactions, confirm queue behavior, reply to both sequentially.

## Assumptions

- V1 is core-only and does not add new legacy Google Sheet behavior.
- V1 supports parent category selection only; sub-categories remain a later schema/task.
- Zalo routing uses `channel_chat_id` (= `sender.id`) for both identification and message sending only after live send verification confirms that `sender.id` is accepted by the send API.
- Zalo interactive mode remains behind `ZALO_ENABLED=true` and `ZALO_INTERACTIVE=true`.
- Official Zalo OA API (v3.0) is the only allowed integration surface; no personal-account automation.
- Telegram legacy flows continue using Google Sheets state; Zalo uses DB `bot_state`. No overlap in V1.
- Zalo OA access token refresh requires manual Railway env update in V1 (automated persistent token store is V2 scope).
- Zalo OA follower requirement: users who message the OA auto-follow. If user unfollows, send will fail — ZaloSender logs warning and does not retry (user can re-follow and `/start` again).

## Tech Debt (Documented for V2)

1. **bot_state PK**: Current PK `user_id` is correct as long as each `user_id` maps to exactly one channel (enforced by `UNIQUE(channel_type, channel_user_id)` on `users`). PK only needs to change to `(user_id, channel_type)` if the user model evolves to support **multi-channel per user** (identity merging). Not needed when Telegram migrates off Sheets state — that just means more channel types writing to `bot_state`, each under their own `user_id`.
2. **Token persistence**: Store Zalo OAuth tokens in DB table (e.g., `oauth_tokens`) with auto-refresh background job, eliminating manual Railway env updates. When enabling `ZALO_AUTO_REFRESH=true`, add a mutex/lock to prevent concurrent 401 responses from racing two refresh calls (Zalo refresh tokens are single-use — the second call would get an invalid token).
3. **Zalo text limit**: Verify exact char limit (640 vs 2000) during development; adjust chunking accordingly.
4. **Zalo rich messages**: Explore Zalo list/article templates for better category picker UX (instead of numbered text).
5. **Core reports**: Move `/today`, `/report`, and `/accounts` builders into core services so every channel can use the same read-only data paths without legacy handlers.
