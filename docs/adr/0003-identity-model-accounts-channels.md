# ADR-0003: Split `users` into `accounts` + `channels` for cross-channel identity

> **Status:** 🟡 Proposed
> **Date:** 2026-05-30
> **Decision maker:** Founder (Ngoc-Anh)
> **Context cross-refs:** [brd-vi.md](../brd-vi.md) §1.6 · [Web Dashboard BRD](../webapp/brd.md) · [Zalo Bot API Research](../research-zalo-multi-user-bot.md) · [ADR-0001](0001-monorepo-not-split-repos.md)

---

## Context

MyMoneyWent is expanding from 1 bot channel (Telegram) to 3 user surfaces first
(Telegram, Zalo, Web dashboard), with Discord/Messenger possible later. The
current `users` table conflates **identity** (who you are, what plan you have,
what data you own) with **delivery** (which bot channel to send messages on).

Current schema:
```sql
users (
    id, channel_type, channel_user_id, chat_id, channel_chat_id,
    plan, trial_ends_at, locale, timezone, ...
    UNIQUE(channel_type, channel_user_id)
)
```

**Problem:** If Minh signs up via Telegram (`user_id=1`) then later uses the Zalo bot, he gets `user_id=2` — a completely separate account with separate transactions, categories, and plan. There's no way to:

1. Link channels so Minh sees the same data everywhere
2. Send notifications to multiple channels simultaneously
3. Let Minh sign up on web and later connect Telegram/Zalo
4. Avoid paying for Pro on each channel separately

This will increasingly hurt UX as we add channels. The Web Dashboard BRD (progressive: companion → standalone) makes this urgent — web users need to link their bot accounts.

## Decision

**Split identity from bot delivery endpoints.** `accounts` becomes the long-term
identity + data ownership anchor, while `channels` stores Telegram/Zalo/Discord
delivery endpoints. Web is not a delivery channel; web login lives in
`auth_identities`.

Implement as a strangler migration: add `channels` first while keeping
`users.id` as the account id in runtime code, then rename `users` to `accounts`
only after code and tests have moved to account semantics. This avoids a
big-bang FK rename across the whole app.

## Schema

### `accounts` — replaces `users` as the identity anchor

```sql
CREATE TABLE accounts (
    id                   SERIAL PRIMARY KEY,
    email                VARCHAR(255) UNIQUE,       -- nullable; denormalized primary email
    phone                VARCHAR(20) UNIQUE,        -- nullable; only after explicit verification
    display_name         VARCHAR(128),
    inbound_email        VARCHAR(64) UNIQUE,
    plan                 VARCHAR(16) NOT NULL DEFAULT 'free',
    trial_ends_at        TIMESTAMPTZ,
    plan_expires_at      TIMESTAMPTZ,
    timezone             VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    locale               VARCHAR(5)  NOT NULL DEFAULT 'vi',
    daily_recap_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    onboard_path         VARCHAR(8),
    role                 VARCHAR(16) NOT NULL DEFAULT 'user',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_plan   CHECK (plan IN ('free', 'pro', 'business')),
    CONSTRAINT chk_locale CHECK (locale IN ('vi', 'en')),
    CONSTRAINT chk_role   CHECK (role IN ('user', 'founder', 'admin'))
);
```

### `auth_identities` — web/social login identities, N per account

Web dashboard auth should not be stored as `channels(channel_type='web')`
because it is not a message delivery endpoint. It is an authentication identity.

```sql
CREATE TABLE auth_identities (
    id                   SERIAL PRIMARY KEY,
    account_id           INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    provider             VARCHAR(32) NOT NULL,       -- password, google, passkey, zalo_login
    provider_subject     VARCHAR(255) NOT NULL,      -- provider user id / credential id
    email                VARCHAR(255),
    email_verified_at    TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uniq_auth_identity UNIQUE (provider, provider_subject)
);

CREATE INDEX idx_auth_identities_account ON auth_identities(account_id);
CREATE INDEX idx_auth_identities_email ON auth_identities(email)
WHERE email IS NOT NULL;
```

### `channels` — bot delivery endpoints, N per account

```sql
CREATE TABLE channels (
    id                SERIAL PRIMARY KEY,
    account_id        INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    channel_type      VARCHAR(16) NOT NULL,
    channel_user_id   VARCHAR(64) NOT NULL,
    channel_chat_id   TEXT,                          -- Zalo/Discord string IDs
    chat_id           BIGINT,                        -- Telegram numeric chat_id
    telegram_id       BIGINT,                        -- legacy compat
    is_primary        BOOLEAN NOT NULL DEFAULT FALSE, -- default channel for interactive prompts
    active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_channel_type CHECK (channel_type IN (
        'telegram', 'discord', 'messenger', 'zalo'
    )),
    CONSTRAINT uniq_channel_user UNIQUE (channel_type, channel_user_id)
);

-- Fast lookup: given a platform user_id, find the account
CREATE INDEX idx_channels_lookup ON channels(channel_type, channel_user_id);
-- Fast lookup: given an account, find all channels
CREATE INDEX idx_channels_account ON channels(account_id);
-- At most one primary active bot channel per account
CREATE UNIQUE INDEX uniq_channels_primary_per_account
ON channels(account_id)
WHERE is_primary = TRUE AND active = TRUE;
```

### FK migration — all data tables point to `accounts.id`

```sql
-- transactions, categories, funding_sources, webhook_tokens,
-- bot_state, bank_connections, scheduled_jobs, monthly_reports,
-- admin_audit_log.target_user_id, analytics_events:
-- All eventually change user_id → account_id (FK to accounts.id).
```

### `link_codes` — for cross-channel linking

```sql
CREATE TABLE link_codes (
    id            SERIAL PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    code_hash     CHAR(64) NOT NULL UNIQUE,       -- SHA-256(code); raw code is never stored
    expires_at    TIMESTAMPTZ NOT NULL,
    used_at       TIMESTAMPTZ,
    used_channel_id INTEGER REFERENCES channels(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_link_codes_account ON link_codes(account_id, created_at DESC);
```

### `account_merge_events` — audit trail for manual/confirmed merges

```sql
CREATE TABLE account_merge_events (
    id                  BIGSERIAL PRIMARY KEY,
    source_account_id   INTEGER NOT NULL,
    target_account_id   INTEGER NOT NULL REFERENCES accounts(id),
    initiated_channel_id INTEGER REFERENCES channels(id),
    status              VARCHAR(16) NOT NULL, -- confirmed, completed, rejected, failed
    moved_counts        JSONB NOT NULL DEFAULT '{}',
    skipped_counts      JSONB NOT NULL DEFAULT '{}',
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_merge_status CHECK (
        status IN ('confirmed', 'completed', 'rejected', 'failed')
    )
);
```

## Cross-Channel Linking Flows

### Flow 1: Link code (channel → channel)

```
Minh on Telegram:  /link
Bot:               "Mã liên kết: K7X2M9 (hết hạn 10 phút)"

Minh on Zalo:      /link K7X2M9
Bot:               "Đã liên kết Zalo với tài khoản Telegram! 
                    Bạn sẽ nhận thông báo trên cả hai kênh."
```

Implementation:
```python
# /link (no args) — generate code
async def handle_link_generate(account_id: int) -> str:
    code = generate_human_code(length=10)  # e.g. "K7X2-M9Q4"
    code_hash = sha256(code)
    await db.execute(
        """INSERT INTO link_codes (account_id, code_hash, expires_at)
           VALUES ($1, $2, $3)""",
        account_id, code_hash, now() + timedelta(minutes=10),
    )
    return code

# /link CODE — consume code, link channel to existing account
async def handle_link_consume(
    code: str,
    channel_type: str,
    channel_user_id: str,
    channel_chat_id: str | None,
) -> bool:
    # Pseudocode: the real implementation must run in ONE DB transaction.
    # Rate-limit invalid attempts by (channel_type, channel_user_id, IP/session)
    # before reaching this point.
    async with db.transaction() as tx:
        row = await tx.fetchrow(
            """UPDATE link_codes
               SET used_at = NOW()
               WHERE code_hash = $1
                 AND expires_at > NOW()
                 AND used_at IS NULL
               RETURNING id, account_id""",
            sha256(code),
        )
        if not row:
            return False  # expired, invalid, or already used

        existing_channel = await tx.fetchrow(
            """SELECT id, account_id
               FROM channels
               WHERE channel_type = $1 AND channel_user_id = $2
               FOR UPDATE""",
            channel_type,
            channel_user_id,
        )

        if existing_channel and existing_channel["account_id"] != row["account_id"]:
            await merge_or_reject_secondary_account(
                tx,
                source_account_id=existing_channel["account_id"],
                target_account_id=row["account_id"],
            )

        channel = await tx.fetchrow(
            """INSERT INTO channels (account_id, channel_type, channel_user_id, channel_chat_id)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (channel_type, channel_user_id)
               DO UPDATE SET
                   account_id = EXCLUDED.account_id,
                   channel_chat_id = COALESCE(channels.channel_chat_id, EXCLUDED.channel_chat_id),
                   active = TRUE,
                   updated_at = NOW()
               RETURNING id""",
            row["account_id"], channel_type, channel_user_id, channel_chat_id,
        )
        await tx.execute(
            "UPDATE link_codes SET used_channel_id = $2 WHERE id = $1",
            row["id"],
            channel["id"],
        )
    return True
```

**Important:** if a user has already used both channels separately, linking is
not just a channel move. The implementation must either merge the secondary
account's data into the target account or block the link and ask for explicit
confirmation.

### Account merge policy

When consuming a link code from a channel that already belongs to another
account:

1. If the source account has no data except the channel row, move the channel
   directly and delete/archive the empty source account.
2. If the source account has user data, require explicit confirmation before
   merge.
3. Merge inside a single DB transaction. Move:
   `transactions`, `categories`, `funding_sources`, `webhook_tokens`,
   `bot_state`, `bank_connections`, `scheduled_jobs`, `monthly_reports`, and
   relevant `analytics_events`.
4. Resolve unique conflicts deliberately:
   - `transactions(account_id, ref_code)`: keep target row, log skipped source
     duplicate.
   - `categories(account_id, slug, month_key)`: merge amounts only if semantics
     are compatible; otherwise suffix/import as inactive review item.
   - `funding_sources(account_id, kind, bank, last4)`: merge metadata and keep
     most recent `last_tx_at`.
   - `webhook_tokens(account_id, kind)`: keep target active token and revoke
     source token.
5. Store a merge audit event with `source_account_id`, `target_account_id`,
   initiating channel, counts moved/skipped, and timestamp.

### Flow 2: Web dashboard hub (W2)

```
Web Settings page:
  ┌──────────────────────────────────┐
  │  Connected Channels              │
  │                                  │
  │  ✅ Telegram  @minh_bot          │
  │  ➕ Connect Zalo    [QR code]    │
  │  ➕ Connect Discord [Link]       │
  └──────────────────────────────────┘

Click "Connect Zalo" → QR code / deep link:
  https://zalo.me/bot_id?start=LINK_K7X2M9

Zalo bot receives /start LINK_K7X2M9 → auto-link
```

Web creates a normal `accounts` row plus an `auth_identities` row. Connecting
Telegram/Zalo from web uses the same `link_codes` mechanism; web itself is not
inserted into `channels`.

### Flow 3: Phone number auto-match (optional, passive)

```python
# When Telegram/Zalo user shares contact (phone):
async def try_auto_link_by_phone(phone: str, channel_id: int):
    existing = await db.fetchrow(
        "SELECT id FROM accounts WHERE phone = $1", phone
    )
    if existing:
        # Suggest linking, but require explicit user confirmation before
        # moving channel ownership or merging financial data.
        await prompt_link_confirmation(existing["id"], channel_id)
```

Phone auto-match must be **suggest-and-confirm**, not automatic. Phone numbers
are mutable and can be re-used; they should never silently merge financial data.

## Notification Fan-Out

After linking, `messenger.send()` should not blindly fan out every payload.
Interactive bot prompts (category picker, callback buttons, onboarding steps)
should go to one routable channel, usually the active primary channel. Account
notifications can fan out to multiple channels when the user opts in.

```python
# core/messenger/send.py — updated

class DeliveryMode(StrEnum):
    PRIMARY = "primary"          # default for interactive prompts
    ALL_ACTIVE = "all_active"    # explicit fan-out
    CHANNEL = "channel"          # reply to inbound channel context


async def send(
    account_id: int,
    payload: SendPayload,
    *,
    mode: DeliveryMode = DeliveryMode.PRIMARY,
    channel_id: int | None = None,
) -> None:
    """Send a payload to the selected channel(s) of an account."""
    channels = await _resolve_channels(account_id, mode=mode, channel_id=channel_id)
    for ch in channels:
        try:
            factory = senders_for(ch["channel_type"])
            sender = await _build(factory)
            await sender.send_to_channel(ch, payload)  # adapters receive routing row
        except Exception as exc:
            log.warning("send.channel_failed",
                account_id=account_id,
                channel=ch["channel_type"],
                error=str(exc))
            # Continue to next channel — don't fail all because one failed

async def _resolve_channels(account_id: int, *, mode: DeliveryMode, channel_id: int | None) -> list[dict]:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, channel_type, channel_user_id, channel_chat_id, chat_id, is_primary
               FROM channels
               WHERE account_id = $1
                 AND active = TRUE
                 AND (
                   $2 = 'all_active'
                   OR ($2 = 'primary' AND is_primary = TRUE)
                   OR ($2 = 'channel' AND id = $3)
                 )
               ORDER BY is_primary DESC, created_at ASC""",
            account_id,
            mode.value,
            channel_id,
        )
    return [dict(r) for r in rows]
```

**User preference**: add `notification_channels` JSONB on `accounts` or a
normalized `notification_preferences` table later. Default policy:

- Interactive flows: send to primary channel or the inbound channel context.
- Critical account/security events: send to all active bot channels.
- Daily/monthly recap: send to primary channel unless user opts into fan-out.
- Web dashboard: show activity/inbox in UI; do not model web as a bot channel.

## Migration Strategy

### Phase A: Add `channels` without renaming `users` (non-breaking)

```sql
-- 1. Keep users as the account table for now.
-- 2. Create channels pointing to users(id). Name the FK `account_id` in new code
--    if possible, but the referenced table remains users during this phase.
CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_type VARCHAR(16) NOT NULL,
    channel_user_id VARCHAR(64) NOT NULL,
    channel_chat_id TEXT,
    chat_id BIGINT,
    telegram_id BIGINT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(channel_type, channel_user_id)
);

-- 3. Backfill one channel per current users row.
INSERT INTO channels (
    account_id, channel_type, channel_user_id, channel_chat_id,
    chat_id, telegram_id, is_primary, active
)
SELECT
    id, channel_type, channel_user_id, channel_chat_id,
    chat_id, telegram_id, TRUE, NOT invalid_channel
FROM users;
```

Code changes in Phase A:

1. Webhook handlers resolve `(channel_type, channel_user_id)` via `channels`.
2. `handle_start` creates/updates `users` account row and `channels` row.
3. Messenger resolves routing from `channels`, not `users.channel_type`.
4. If web auth ships in this phase, `auth_identities.account_id` references
   `users(id)` until the physical rename.
5. Data tables continue using `user_id` in SQL to avoid a giant FK rename.

### Phase B: Rename semantics in code

1. Introduce `account_svc` but keep compatibility wrappers in `user_svc`.
2. Rename variables in business logic from `user_id` to `account_id` where the
   value is truly the data owner.
3. Update tenant context wording from `user_id` to `account_id`.
4. Add integration tests for:
   - Telegram start then Zalo link sees same categories/transactions.
   - Zalo start then Telegram link with existing Zalo data triggers merge/block.
   - SePay token still resolves to the same owner after linking.
   - `messenger.send(..., PRIMARY)` sends one message, not duplicate fan-out.

### Phase C: Optional physical rename

Only after Phase A/B are stable:

```sql
ALTER TABLE users RENAME TO accounts;
ALTER TABLE transactions RENAME COLUMN user_id TO account_id;
-- Repeat for categories, funding_sources, webhook_tokens, bot_state,
-- bank_connections, scheduled_jobs, monthly_reports, analytics_events,
-- admin_audit_log.target_user_id → target_account_id.
```

This phase is optional. Keeping `user_id` column names internally is acceptable
for MVP if the application contract clearly says they are account IDs.

### Phase D: Cleanup

1. Remove legacy `users.channel_type`, `users.channel_user_id`, `users.chat_id`,
   `users.channel_chat_id`, `users.telegram_id`, and `users.invalid_channel`
   after all reads use `channels`.
2. Drop compatibility wrappers/views only after migration metrics show no legacy
   reads.

## What Does NOT Change

- `SendPayload` / `Markup` / `Button` — payload contract stays the same
- Individual sender adapters (TelegramSender, ZaloSender) still send to one
  platform endpoint at a time, but they should accept a resolved channel row
  instead of looking up `users` themselves.
- `categorize.py` business logic — same flow, different FK name
- i18n, import boundaries, CI pipeline
- Pricing tiers — plan lives on `accounts`, not per-channel

## Consequences

### Positive
- User links all channels to one account — single view of financial data
- Plan/tier is per-account, not per-channel — fair pricing
- Web dashboard can be standalone entry point without duplicating data
- Notification fan-out is possible for selected notification types
- Foundation for family/shared accounts (multiple accounts sharing data) in future

### Negative
- Migration complexity — must handle all FK changes carefully
- `messenger.send()` needs explicit delivery-mode semantics instead of one implicit channel
- `link_codes` table + `/link` command = new code surface to maintain
- Edge case: user links wrong accounts together → need `/unlink` command
- Existing-channel link may require account merge, not just channel update

### Risks
- Data corruption during migration if FK update misses a table
- Two channels claim same phone → conflict resolution needed
- Wrong-account merge could expose financial data across identities
- Performance: fan-out to 3+ channels for selected notification types

### Mitigations
- Phase A adds `channels` without renaming data-table FKs — no big bang
- Tenant isolation tests remain mandatory for every account-scoped table
- Phone matching is suggest-and-confirm, not automatic
- Link code consume is one transaction and stores only code hashes
- Merge requires explicit confirmation when the source account has data
- Fan-out is opt-in/explicit and uses per-channel error isolation

## Trigger

**When to implement:**
- When Web Dashboard W2 (standalone mode) is ready to ship, OR
- When Zalo Bot API channel is production-ready and users request cross-channel linking

**Do NOT implement** before at least 2 channels are live in production with real users.

## Alternatives Considered

### A. Keep `users` table, add `linked_user_id` FK
Link Minh's Zalo user_id=2 to Telegram user_id=1 via `linked_user_id`. Simpler migration but creates tree-traversal complexity for every query (follow links). Rejected: gets messy with 3+ channels.

### B. UUID-based `identity_id` on existing `users`
Add `identity_id UUID` to `users`. Same identity_id = same person. Simpler than full split but still queries N rows per person. Rejected: half-measure that doesn't solve fan-out cleanly.

### C. Do nothing — each channel is independent
Users manage separate accounts per channel. Simplest. Rejected: bad UX as channel count grows, users pay for plan per-channel.
