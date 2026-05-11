# BE Tech Doc: Funding Sources — Tài khoản & Thẻ (F08)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-11
> **Feature doc:** [feature-funding-sources.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md)
> **Tham chiếu:**
> - [feature-transaction-capture-tech.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-transaction-capture-tech.md)
> - [TDD-vi v1.8.1 §2.1 schema, §3.2 pipeline](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)

---

## 1. Implementation Overview

| Module | File (target Postgres) | File (transitional Sheets) | Responsibility |
|--------|----------------------|--------------------------|----------------|
| Repository | `services/funding_sources.py` | `sheets.py` (extend) | CRUD funding_sources, cache, upsert-on-discovery |
| Pipeline hook | `services/tx_pipeline.py` step `resolve_funding_source()` | `handlers/sepay.py` (extend `_extract_bank_account`) | Map raw payload → existing-or-new funding_source_id |
| Inference | `services/funding_sources.py::infer_kind()` | same | Decide `bank_account`/`debit_card`/`credit_card`/`e_wallet` |
| Bot commands | `handlers/accounts.py` (new) | `handlers/accounts.py` (new) | `/accounts`, `/banks` alias, callbacks `acc_*` |
| State machine | `services/conversation.py` (existing bot_state) | `handlers/accounts.py` | Rename / manual-add flows |
| Backfill | `scripts/backfill_funding_sources.py` (one-off) | same | Reconstruct from legacy column P strings |

Pipeline integration (insert into existing `process_transaction()` flow):

```
Webhook/Email → Parse → Dedup → Stale check → Tier check
                                                    ↓
                          (new) Resolve/Discover funding_source
                                                    ↓
                                              INSERT tx (với FK, hoặc NULL khi resolve fail)
                                                    ↓
                          Category picker (+ discovery header prepended nếu was_discovered)
                                                    ↓
                       (new, delayed 1.5s) Resurrect notification nếu was_resurrected
```

**Invariants:**
- Resolve trước INSERT — đảm bảo FK populated. Failure path: log + `funding_source_id=NULL`, không crash pipeline.
- Discovery message KHÔNG là message riêng — embed làm header trong picker (1 Telegram message). Tránh 2 ping liên tiếp.
- Resurrect là exception flow, tách message riêng nhưng delayed sau picker với rate-limit.

---

## 2. Database Schema

### 2.1. DDL — Postgres target

```sql
CREATE TABLE funding_sources (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            VARCHAR(16) NOT NULL,
    bank            VARCHAR(16) NOT NULL,
    last4           VARCHAR(4)  NOT NULL DEFAULT '',
    display_id      VARCHAR(32) NOT NULL,
    nickname        VARCHAR(32),
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_tx_at      TIMESTAMPTZ,
    status          VARCHAR(16) NOT NULL DEFAULT 'active',
    archived_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Canonical identity. last4='' khi không có số cuối (KHÔNG NULL, tránh NULL-trap với UNIQUE).
    UNIQUE(user_id, kind, bank, last4),

    CONSTRAINT chk_fs_kind   CHECK (kind   IN ('bank_account','debit_card','credit_card','e_wallet')),
    CONSTRAINT chk_fs_status CHECK (status IN ('active','hidden','archived')),
    CONSTRAINT chk_fs_archived_consistency CHECK (
        (status = 'archived' AND archived_at IS NOT NULL)
        OR (status <> 'archived' AND archived_at IS NULL)
    )
);

CREATE INDEX idx_fs_user_status  ON funding_sources(user_id, status);
CREATE INDEX idx_fs_user_lasttx  ON funding_sources(user_id, last_tx_at DESC);
CREATE INDEX idx_fs_user_display ON funding_sources(user_id, display_id);  -- non-unique lookup cho filter

-- transactions extension
ALTER TABLE transactions
    ADD COLUMN funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL;

CREATE INDEX idx_tx_user_fs ON transactions(user_id, funding_source_id);
```

**Deletion model — F08 chỉ enforce 2 FK rules sau, retention policy cuối cùng do [TDD §6.3](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) định:**

| FK | Rule | Hệ quả |
|---|---|---|
| `funding_sources.user_id → users(id)` | `ON DELETE CASCADE` | Hard-delete user → xoá toàn bộ funding_sources của user đó |
| `transactions.funding_source_id → funding_sources(id)` | `ON DELETE SET NULL` | Funding_source bị xoá (qua CASCADE từ user OR explicit) → tx tương ứng giữ lại, FK reset NULL |

**Note:** F08 KHÔNG quyết định transactions có bị xoá hay anonymize hay giữ nguyên khi hard-delete user — đó là policy của TDD §6.3 áp dụng lên `transactions.user_id`. F08 chỉ quan tâm column `funding_source_id` (SET NULL khi parent gone).

Soft delete user: chỉ set `users.deleted_at`, không CASCADE, không touch anything. App layer ẩn dữ liệu.

### 2.2. Transitional Sheets schema (current MVP runtime)

Worksheet `FUNDING_SOURCES`, columns:

| Col | Field | Type | Note |
|-----|-------|------|------|
| A | id | int | autoincrement (counter ở cell Z1) |
| B | user_id | int | Cho lúc multi-tenant; hôm nay all = `CHAT_ID` |
| C | kind | string | `bank_account`/`debit_card`/`credit_card`/`e_wallet` |
| D | bank | string | TCB / MB / Cake / ... |
| E | last4 | string | 4 ký tự hoặc rỗng `""` |
| F | display_id | string | "TCB-1234" — render only, NOT unique |
| G | nickname | string | Optional |
| H | first_seen_at | ISO datetime | |
| I | last_tx_at | ISO datetime | |
| J | status | string | `active`/`hidden`/`archived` |
| K | archived_at | ISO datetime hoặc rỗng | Set khi cron archive |

**Unique enforcement trong Sheets:** Sheets không hỗ trợ UNIQUE constraint native. Thay vào đó, helper `funding_sources.find_or_create(user_id, kind, bank, last4)` **phải** dùng `bootstrap_lock` (đã có ở `sheets.py`) + re-check pattern để guarantee canonical identity uniqueness. Race window: ≤1 worker thắng, các worker khác đọc lại thấy row đã có.

Transactions sheet:
- Column P (`bank_account` string) **giữ nguyên** — backward compat với code legacy đọc trực tiếp.
- **Thêm Column Q (`funding_source_id`)** — int ref tới `FUNDING_SOURCES.A`. Sheets KHÔNG enforce FK constraint native (không có DB engine), nhưng vẫn populate column này để (a) mirror future Postgres FK, (b) cho phép code lookup theo id nhanh hơn string-match, (c) khi migrate sang Postgres, ALTER TABLE chỉ cần copy column Q sang `transactions.funding_source_id`.

Trong giai đoạn Sheets, "FK violation" được handle ở app layer: nếu column Q trỏ tới id không tồn tại (data drift, manual edit), lookup fallback xuống column P string.

### 2.3. Key Queries

```sql
-- ─── Upsert-on-discovery ────────────────────────────────
-- Canonical version với CTE-based was_resurrected detection — xem §2.3b dưới.
-- (Query đơn giản ON CONFLICT...RETURNING xmax=0 chỉ detect được was_inserted;
-- để detect resurrect chính xác cần CTE đọc trước-status. Dùng §2.3b làm reference.)

-- ─── Read list cho /accounts (default: chỉ active) ───────
SELECT id, display_id, nickname, kind, last_tx_at
FROM funding_sources
WHERE user_id = $1 AND status = 'active'
ORDER BY last_tx_at DESC NULLS LAST;

-- ─── Read list bao gồm hidden (khi user pass --include-hidden) ──
SELECT id, display_id, nickname, kind, status, last_tx_at
FROM funding_sources
WHERE user_id = $1 AND status IN ('active', 'hidden')
ORDER BY (status='hidden'), last_tx_at DESC NULLS LAST;

-- ─── Spent/income current month (join với transactions) ──
SELECT fs.id, fs.display_id, fs.nickname, fs.status,
       COALESCE(SUM(CASE WHEN t.direction='out' THEN t.amount END), 0) AS spent,
       COALESCE(SUM(CASE WHEN t.direction='in'  THEN t.amount END), 0) AS income,
       COUNT(t.id) AS tx_count
FROM funding_sources fs
LEFT JOIN transactions t
       ON t.funding_source_id = fs.id
      AND t.month_key = $2
      AND t.confirmed = TRUE
WHERE fs.user_id = $1 AND fs.status = 'active'
GROUP BY fs.id
ORDER BY fs.last_tx_at DESC NULLS LAST;

-- ─── Rename ──────────────────────────────────────────────
UPDATE funding_sources
SET nickname = $1
WHERE id = $2 AND user_id = $3
RETURNING id;

-- ─── User hide (intentional) ─────────────────────────────
UPDATE funding_sources
SET status = 'hidden'
WHERE id = $1 AND user_id = $2 AND status = 'active';

-- ─── Auto-archive cron (180-day silence) ─────────────────
-- Chỉ archive từ 'active' — KHÔNG đụng 'hidden' (đã là user-intent).
UPDATE funding_sources
SET status = 'archived', archived_at = NOW()
WHERE status = 'active' AND last_tx_at < NOW() - INTERVAL '180 days';

-- ─── Filter resolution cho /reports account=<display_id> (Option A) ───
-- Direct lookup = explicit intent → match cả 'active' và 'hidden'.
-- Archived KHÔNG match (cold storage, cần manual unarchive).
SELECT id, kind, display_id, nickname, status
FROM funding_sources
WHERE user_id = $1 AND display_id = $2 AND status IN ('active', 'hidden')
ORDER BY (status = 'hidden'), kind;  -- active rows trước, hidden xếp sau
-- COUNT() = 0 → FS_NOT_FOUND; = 1 → filter ngay; ≥2 → disambiguation prompt
```

### 2.3b. UPSERT_SQL — canonical với was_resurrected detection

Đây là query CHÍNH cho discovery slow-path (xem §4.3 `resolve_funding_source`). CTE snapshot status before UPDATE để detect resurrect chính xác:

```sql
-- UPSERT_SQL (canonical). Resurrect chỉ từ status='archived' — KHÔNG flip 'hidden'.
-- COALESCE(..., FALSE) đảm bảo was_resurrected luôn bool (empty CTE → NULL → FALSE),
-- khớp với dataclass `was_resurrected: bool` ở Python layer.
WITH before AS (
    SELECT id, status FROM funding_sources
    WHERE user_id = $1 AND kind = $2 AND bank = $3 AND last4 = $4
)
INSERT INTO funding_sources (user_id, kind, bank, last4, display_id, first_seen_at, last_tx_at)
VALUES ($1, $2, $3, $4, $5, $6, $6)
ON CONFLICT (user_id, kind, bank, last4)
DO UPDATE SET
    last_tx_at  = GREATEST(funding_sources.last_tx_at, EXCLUDED.last_tx_at),
    status      = CASE WHEN funding_sources.status = 'archived' THEN 'active' ELSE funding_sources.status END,
    archived_at = CASE WHEN funding_sources.status = 'archived' THEN NULL      ELSE funding_sources.archived_at END
RETURNING
    id,
    (xmax = 0)                                                       AS was_inserted,
    COALESCE((SELECT status = 'archived' FROM before), FALSE)        AS was_resurrected;
```

Nếu Postgres version hỗ trợ `MERGE` (≥15), dùng `MERGE ... WHEN MATCHED ... WHEN NOT MATCHED` để biểu đạt rõ hơn — out of scope MVP.

### 2.4. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|------|
| 1 | Concurrency | 2 webhook đồng thời cho TK mới | UPSERT `ON CONFLICT (user_id, kind, bank, last4)` returns 1 winner row; cả 2 query lấy cùng id |
| 1b | Concurrency | Race giữa kind=bank_account và kind=credit_card cùng (bank, last4) | KHÔNG conflict — unique tách bởi kind. 2 row được tạo độc lập. |
| 2 | Data integrity | bank=`""` (gateway hoàn toàn rỗng) | Skip resolve → tx vẫn lưu được, funding_source_id NULL (gom "Không rõ"). KHÔNG INSERT row rác bank=''. |
| 2b | Data integrity | last4=`""` (bank biết, account number không có) | INSERT bình thường với last4='' — empty string vẫn unique-comparable, KHÔNG conflict với entry khác cùng bank có last4 thật |
| 3 | Data integrity | Bank string không match alias | Fallback: uppercase 5 ký tự đầu (giữ logic hiện tại `_normalize_bank_name`) |
| 4 | Cross-feature | User chưa có row nào trong `users` (multi-tenant chưa rollout) | Giai đoạn Sheets dùng `CHAT_ID` làm user_id ảo — tương thích trong khi chờ F-saas-refactor |
| 5 | Race | Rename giữa lúc auto-resurrect notify đang gửi | Notify dùng snapshot tại thời điểm UPSERT → user có thể thấy display_id thay vì nickname mới trong 1 message; chấp nhận được |
| 6 | Security | Callback `acc_rename_{id}` với id của user khác | Mọi mutation WHERE `user_id = $current_user` — id lạ trả `FS_NOT_FOUND` |
| 7 | Data integrity | Tx legacy có `bank_account=""` (column P rỗng) | funding_source_id NULL, gom "Không rõ" — không tạo entry rác |
| 8 | Performance | User có 50+ funding_sources (edge nhưng có thể) | Index `idx_fs_user_lasttx` đủ; query LIMIT mặc định 20 cho /accounts view |
| 9 | Inference conflict | SePay payload có gateway "Cake by VPBank" — debit hay credit? | Default `bank_account`; user có thể đổi `kind` qua /accounts (edit mode — out of MVP, ghi backlog) |
| 10 | Backfill collision | Backfill script gặp string lạ không decode được | Skip + log row số, tx giữ funding_source_id NULL |

---

## 3. API Contract

### 3.1. Internal function signatures

```python
from typing import Literal
from datetime import datetime
from dataclasses import dataclass, field

FundingKind  = Literal['bank_account', 'debit_card', 'credit_card', 'e_wallet']
FundingStatus = Literal['active', 'hidden', 'archived']

@dataclass
class FundingSource:
    id: int
    user_id: int
    kind: FundingKind
    bank: str
    last4: str               # '' khi không có số cuối (NOT None — match DB NOT NULL DEFAULT '')
    display_id: str
    nickname: str | None
    first_seen_at: datetime
    last_tx_at: datetime | None
    status: FundingStatus
    archived_at: datetime | None   # NULL trừ khi status='archived'

@dataclass
class ResolveResult:
    funding_source_id: int | None  # NULL nếu bank rỗng (không resolve được)
    was_discovered: bool           # True → embed discovery header vào picker
    was_resurrected: bool          # True → delayed resurrect notification

async def resolve_funding_source(
    user_id: int,
    raw_payload: dict,
    source: str,             # 'sepay' / 'email_tcb' / ...
    tx_date: datetime,
) -> ResolveResult: ...

async def list_funding_sources(
    user_id: int,
    *,
    include_hidden:   bool = False,   # show user-hidden rows
    include_archived: bool = False,   # show cron-archived rows
) -> list[FundingSource]: ...

async def list_with_month_stats(user_id: int, month_key: str, *, include_hidden: bool = False) -> list[dict]: ...

async def rename_funding_source(user_id: int, fs_id: int, nickname: str) -> FundingSource: ...
async def hide_funding_source(user_id: int, fs_id: int) -> None: ...
async def unhide_funding_source(user_id: int, fs_id: int) -> None: ...    # out of MVP
async def manually_add(
    user_id: int,
    bank: str,
    last4: str,              # '' allowed
    kind: FundingKind,
    nickname: str | None,
) -> FundingSource: ...
```

### 3.2. Inference rules

```python
def infer_kind(raw_payload: dict, source: str) -> str:
    """Suy luận kind từ payload + source. Default: 'bank_account'."""
    # E-wallet detect (priority cao nhất vì gateway distinct)
    gateway = (raw_payload.get('gateway') or '').lower()
    if any(w in gateway for w in ('momo', 'zalopay', 'viettelpay', 'shopeepay', 'vnpay wallet')):
        return 'e_wallet'

    # Credit card detect từ email subject
    if source.startswith('email_'):
        subject = (raw_payload.get('Subject') or raw_payload.get('subject') or '').lower()
        if any(w in subject for w in ('thẻ tín dụng', 'credit card', 'sao kê thẻ', 'thanh toán thẻ tín dụng')):
            return 'credit_card'

    # Debit card detect — SePay không có signal đáng tin, để user manual nâng cấp
    return 'bank_account'
```

### 3.3. Bot callback signatures (Telegram)

| Callback data | Handler | State transition |
|---|---|---|
| `acc_list` | `cmd_accounts()` | — |
| `acc_rename` | `start_rename_pick()` | idle → `await_rename_pick_fs` |
| `acc_rename_{id}` | `start_rename_input()` | `await_rename_pick_fs` → `await_rename_input` (payload: fs_id) |
| `acc_hide` | `start_hide_pick()` | idle → `await_hide_pick_fs` |
| `acc_hide_{id}` | `do_hide()` | `await_hide_pick_fs` → idle |
| `acc_add` | `start_add_bank()` | idle → `await_add_bank` |
| `acc_add_bank_{bank}` | `cont_add_last4()` | `await_add_bank` → `await_add_last4` |
| `acc_add_kind_{kind}` | `cont_add_nickname()` | `await_add_last4` → `await_add_nickname` |
| `acc_cancel` | `reset_state()` | any → idle |

---

## 4. Implementation Details

### 4.1. Pipeline integration

Sửa `handlers/sepay.py::handle_sepay_webhook()` (hôm nay) hoặc `services/tx_pipeline.py::process_transaction()` (sau migrate):

```python
async def process_transaction(user: User, raw: dict, source: str):
    tx = normalize_payload(raw, source)
    if await check_dedup(user.id, tx): return
    if is_stale(tx, source): return
    if not await check_tier_limit(user):
        await notify_limit_reached(user); return

    # ─── NEW: resolve funding source (BEFORE tx INSERT) ───────────────
    try:
        fs_result = await funding_sources.resolve_funding_source(
            user_id=user.id, raw_payload=raw, source=source, tx_date=tx.tx_date,
        )
        fs_id = fs_result.funding_source_id
    except Exception as e:
        # Discovery failure must NOT block tx — fallback to NULL FK, log + alert
        logger.exception("funding_source resolve failed; saving tx with NULL FK", extra={"user_id": user.id})
        fs_result = ResolveResult(None, False, False)
        fs_id = None

    # ─── tx INSERT with FK populated (or NULL on resolve failure) ─────
    tx_id = await db.insert_transaction(user.id, tx, funding_source_id=fs_id)

    # ─── NEW: discovery message — EMBEDDED INTO CATEGORY PICKER (1 message) ──
    discovery_header = None
    if fs_result.was_discovered:
        discovery_header = render_discovery_header(user.locale, fs_id)
        analytics.fire('fs_discovered', user_id=user.id, fs_id=fs_id)

    await send_category_picker(user, tx_id, tx, prepend=discovery_header)

    # ─── Resurrect notification — separate message, delayed 1.5s ──────
    if fs_result.was_resurrected:
        await asyncio.sleep(1.5)
        await notify_funding_source_resurrected(user, fs_id)
        analytics.fire('fs_resurrected', user_id=user.id, fs_id=fs_id)
```

**Ordering invariants:**
- `resolve_funding_source` chạy TRƯỚC `insert_transaction` — tx luôn có cơ hội nhận FK đúng.
- Discovery message KHÔNG là message riêng — header prepend vào picker (1 Telegram message duy nhất). Tránh 2 ping liên tiếp.
- Resurrect message là exception flow, gửi delayed sau picker với rate-limit (max 1/user/5s) để không spam khi nhiều TK cùng resurrect.
- Resolve failure → tx vẫn save (`funding_source_id=NULL`) → user không mất data. Column P (legacy string) cũng vẫn write như cũ.

> **Cooldown invariant:** notification chỉ fire khi `was_discovered=TRUE` (xmax=0 từ UPSERT). UPSERT idempotent → ping đúng 1 lần / funding_source / lifetime, không cần state cooldown bên ngoài.

### 4.2. Discovery header builder (embedded vào picker)

```python
def render_discovery_header(locale: str, fs_id: int) -> str:
    """Build inline header — prepend vào picker message. KHÔNG send riêng."""
    fs = funding_sources.get_sync(fs_id)
    bank_full = BANK_FULL_NAMES.get(fs.bank, fs.bank)  # TCB → Techcombank
    kind_label = KIND_LABELS[locale][fs.kind]          # "TK ngân hàng" / "Credit card" / ...
    return t(locale, 'fs.discovered_header',
             display_id=fs.display_id, bank_full=bank_full, kind_label=kind_label)
    # i18n template:
    # vi: "📥 _Phát hiện tài khoản mới:_ `{display_id}` ({bank_full} · {kind_label})\n   _Dùng /accounts để đặt tên._\n\n"
    # en: "📥 _New account detected:_ `{display_id}` ({bank_full} · {kind_label})\n   _Use /accounts to name it._\n\n"

async def send_category_picker(user, tx_id, tx, prepend: str | None = None):
    body = build_picker_body(tx)        # "💸 -120,000đ\nPho 24...\n\nKhoản này thuộc mục nào? 🤔"
    full = (prepend or "") + body
    buttons = build_bucket_buttons(...)
    await messenger.send(user, full, buttons=buttons)

# ─── Resurrect — riêng, delayed ────────
async def notify_funding_source_resurrected(user, fs_id: int):
    fs = await funding_sources.get(fs_id)
    text = t(user.locale, 'fs.resurrected', display_id=fs.display_id)
    # vi: "📥 _TK `{display_id}` đã có tx mới — đã bật lại trong list._"
    await messenger.send(user, text)  # no buttons, plain
```

**Fallback strategy** nếu adapter không support combined send (Discord embed limit, future channel):
- Set env flag `FS_DISCOVERY_INLINE=false`.
- Pipeline gửi picker trước, `await asyncio.sleep(1.5)`, gửi discovery message riêng kèm rate-limit (token bucket: 1 token/5s, capacity 1).
- Document trade-off trong CHANGELOG.

### 4.3. Cache layer

```python
# Per-process LRU. Key theo CANONICAL IDENTITY (user_id, kind, bank, last4) — NOT display_id.
# Lý do: cùng display_id="TCB-1234" có thể có 2 fs khác kind; cache theo display_id sẽ collide.
_FS_CACHE: TTLCache = TTLCache(maxsize=1000, ttl=300)  # 5min

async def resolve_funding_source(user_id, raw_payload, source, tx_date) -> ResolveResult:
    bank, last4 = extract_bank_last4(raw_payload)  # reuse _extract_bank_account split logic
    if not bank:
        return ResolveResult(None, False, False)   # gom "Không rõ"
    kind = infer_kind(raw_payload, source)
    display_id = compose_display_id(bank, last4)   # render only

    cache_key = (user_id, kind, bank, last4)
    if (cached_id := _FS_CACHE.get(cache_key)):
        # CACHED PATH — vẫn phải detect resurrect.
        # Lý do: cron có thể đã set status='archived' giữa lúc cache còn TTL
        # (đặc biệt khi multi-process). Nếu chỉ update last_tx_at thuần thì
        # tx mới sẽ KHÔNG flip archived→active, KHÔNG fire fs_resurrected.
        # Dùng UPDATE-với-CTE-trả-was_resurrected thay cho update_last_tx thuần.
        result = await db.fetchrow(TOUCH_SQL, cached_id, tx_date)
        if result is None:
            # row đã bị xoá ngoài cache; rebuild qua UPSERT slow path
            _FS_CACHE.pop(cache_key, None)
        else:
            return ResolveResult(cached_id, False, result['was_resurrected'])

    # Slow path: UPSERT with CTE for was_resurrected detection (§2.3b)
    row = await db.fetchrow(UPSERT_SQL, user_id, kind, bank, last4, display_id, tx_date)
    _FS_CACHE[cache_key] = row['id']
    return ResolveResult(row['id'], row['was_inserted'], row['was_resurrected'])
```

```sql
-- TOUCH_SQL: cache-hit path. Update last_tx_at + flip archived→active (resurrect).
-- KHÔNG đụng status='hidden' (tôn trọng user intent).
-- COALESCE(..., FALSE) đảm bảo was_resurrected luôn bool — match dataclass type.
-- Trong TOUCH_SQL `before` luôn có 1 row khi `updated` có row (vì cùng id), nên
-- COALESCE chủ yếu phòng phòng vệ; nhưng vẫn write để 2 query mirror nhau.
WITH before AS (
    SELECT status FROM funding_sources WHERE id = $1
),
updated AS (
    UPDATE funding_sources
    SET last_tx_at  = GREATEST(last_tx_at, $2),
        status      = CASE WHEN status = 'archived' THEN 'active'   ELSE status END,
        archived_at = CASE WHEN status = 'archived' THEN NULL       ELSE archived_at END
    WHERE id = $1
    RETURNING id
)
SELECT updated.id,
       COALESCE((SELECT status = 'archived' FROM before), FALSE) AS was_resurrected
FROM updated;
-- Trả 0 row nếu fs id không tồn tại (race với delete) → caller invalidate cache.
```

**Cache invalidation rules:**
- **rename:** nickname update only — fs_id không đổi, identity không đổi → KHÔNG invalidate.
- **hide (`status='active'→'hidden'`):** invalidate `(user_id, kind, bank, last4)` để tx tương lai bypass cache. UPSERT slow path sẽ stay hidden (chỉ flip archived→active).
- **archive cron (`active'→'archived'`):** **KHÔNG bắt buộc invalidate** vì TOUCH_SQL đã handle resurrect ở cache hit path. Tuy nhiên best-effort batch invalidate giúp giảm 1 round-trip detect resurrect khi tx mới về.
- **manually_add:** set thẳng vào cache.

> **Multi-process note:** với nhiều worker (gunicorn, Railway autoscale), cache invalidation không cross-process. TOUCH_SQL handle resurrect đúng cho mỗi process độc lập — đây là invariant chính, batch invalidate chỉ là tối ưu phụ.

### 4.4. Backfill script

```python
# scripts/backfill_funding_sources.py
# Chạy 1 lần khi rollout F08. Không idempotent guard — chỉ chạy trên DB sạch hoặc
# sau khi đã DROP TABLE funding_sources; CREATE TABLE.

async def main():
    rows = await db.fetch("""
        SELECT user_id, bank_account_str, MIN(tx_date) AS first_seen, MAX(tx_date) AS last_seen, COUNT(*) AS cnt
        FROM transactions
        WHERE bank_account_str IS NOT NULL AND bank_account_str <> ''
        GROUP BY user_id, bank_account_str
    """)
    for r in rows:
        bank, _, last4 = r['bank_account_str'].partition('-')
        await db.execute("""
            INSERT INTO funding_sources (user_id, kind, bank, last4, display_id, first_seen_at, last_tx_at)
            VALUES ($1, 'bank_account', $2, $3, $4, $5, $6)
            ON CONFLICT (user_id, kind, bank, last4) DO NOTHING
        """, r['user_id'], bank, last4 or '', r['bank_account_str'], r['first_seen'], r['last_seen'])
        # Lưu ý: backfill mặc định kind='bank_account'. Legacy data không phân biệt được
        # credit vs debit — user có thể edit kind sau qua /accounts (out of MVP).

    # Backfill FK trên transactions.
    # IMPORTANT: ràng buộc fs.kind='bank_account' để tránh ambiguity nếu sau này
    # user thêm credit_card cùng display_id (vd: TCB-1234 vừa là bank vừa là credit).
    # Legacy column P chỉ chứa string, không có signal kind → mặc định backfill
    # về kind='bank_account'. User có thể edit kind sau qua /accounts.
    await db.execute("""
        UPDATE transactions t
        SET funding_source_id = fs.id
        FROM funding_sources fs
        WHERE fs.user_id = t.user_id
          AND fs.kind = 'bank_account'
          AND fs.display_id = t.bank_account_str
    """)
```

Cho giai đoạn Sheets, backfill viết tương đương qua `gspread`: iterate transactions worksheet, build distinct display_id set, append rows vào `FUNDING_SOURCES` worksheet.

### 4.5. /banks legacy alias

`handlers/reports.py::send_bank_breakdown()` (đang có sẵn) sẽ:
1. Đọc từ funding_sources thay vì recompute từ tx rows (nhanh hơn, đúng nickname).
2. Nếu funding_source row có nickname → hiển thị "*Lương chính* `TCB-1234`"; không có → "`TCB-1234`".
3. Tiếp tục show "Không rõ" group cho tx với fs_id NULL.

Không breaking change — output format giữ tương đương.

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Discovery: tx đầu tiên TK mới | SePay payload gateway="Techcombank", accountNumber="987654321234" | funding_source INSERT với (kind=bank_account, bank=TCB, last4=1234), was_discovered=TRUE |
| 2 | Discovery: tx thứ 2 cùng TK | Same payload, ref khác | Skip INSERT, update last_tx_at, was_discovered=FALSE |
| 3 | Resurrection | TK có status='archived', tx mới về | UPDATE status='active', archived_at=NULL, was_resurrected=TRUE |
| 4 | Inference: e-wallet | gateway="MoMo" | kind=e_wallet |
| 5 | Inference: credit card | source=email_tcb, subject chứa "thẻ tín dụng" | kind=credit_card |
| 6 | Inference: default | Bank thường, không match rule | kind=bank_account |
| 7 | Last4 missing | Payload không có accountNumber | last4='', display_id="TCB" (no dash) |
| 7b | Last4 empty uniqueness | Insert 2 lần cùng (user, bank_account, TCB, '') | Lần 2 conflict — empty string vẫn comparable, unique constraint enforce |
| 8 | Bank alias normalize | gateway="Cake by VPBank" | bank="Cake" (priority cao hơn "VPBank") |
| 9 | Race: 2 webhook đồng thời TK mới | 2 task asyncio.gather cùng UPSERT | Chỉ 1 row, both return cùng id, ON CONFLICT (user_id, kind, bank, last4) trigger |
| 9b | Race cross-kind | Concurrent INSERT (TCB,1234,bank_account) + (TCB,1234,credit_card) | 2 row riêng, KHÔNG conflict |
| 10 | Rename happy path | nickname="Lương chính" | UPDATE nickname, return updated row |
| 11 | Rename validation: rỗng | nickname=" " | Reject FS_RENAME_INVALID, state giữ nguyên |
| 12 | Rename validation: dài | nickname=33 ký tự | Reject FS_RENAME_INVALID |
| 13 | Rename security: id user khác | fs_id của user B, current=A | FS_NOT_FOUND |
| 14 | Hide (user-intent) | status='active' → 'hidden' | UPDATE thành công, list không trả nữa |
| 15a | Hide rồi tx mới về | status='hidden' + tx mới | Tx attach FK, status KHÔNG flip về active, KHÔNG notify |
| 15b | Archive rồi tx mới về | status='archived' + tx mới | status='active', archived_at=NULL, fire fs_resurrected, delayed notification |
| 15c | Cron archive | last_tx_at < NOW()-180d, status='active' | UPDATE status='archived', archived_at=NOW() |
| 15d | Cron không động vào hidden | last_tx_at < 180d, status='hidden' | KHÔNG flip — hidden là user intent |
| 16 | Manual add happy path | bank=TCB last4=9999 kind=credit_card | INSERT, display_id="TCB-9999" |
| 17a | Manual add duplicate same identity | (TCB,1234,bank_account) đã có | FS_DUPLICATE_MANUAL, không INSERT |
| 17b | Manual add same display diff kind | (TCB,1234,bank_account) tồn tại; add (TCB,1234,credit_card) | OK, INSERT row mới |
| 18a | Manual add no last4 | last4="skip" → '' | display_id="TCB", last4='' |
| 18b | Manual add last4 invalid: letters | last4="12a4" | Reject + stay await_add_last4, error msg |
| 18c | Manual add last4 invalid: 3 digits | last4="123" | Reject + stay |
| 18d | Manual add last4 invalid: 5 digits | last4="12345" | Reject + stay |
| 18e | Manual add last4 case-insensitive skip | last4="SKIP" / "Skip" | Accept as '' |
| 19 | /accounts list | user có 3 funding_sources | Sort theo last_tx_at desc, kèm spent/income |
| 20 | /accounts empty | user chưa có funding_source nào | Empty state message |
| 21a | /reports account=display_id (1 match) | filter | Chỉ tx có funding_source_id = X.id |
| 21b | /reports account=display_id (≥2 match) | 2 fs khác kind cùng display_id | Bot prompt disambiguation buttons |
| 21c | /reports account=kind:display_id | power syntax | Filter ngay, không hỏi |
| 21d | /reports account=display_id (0 match) | display_id không tồn tại HOẶC chỉ archived | FS_NOT_FOUND |
| 21e | /reports account=display_id explicit hit hidden | display_id chỉ match 1 row, status='hidden' | Filter ngay (Option A — explicit intent), KHÔNG hỏi |
| 21f | /reports disambiguation với hidden | 1 active + 1 hidden cùng display_id | Show 2 buttons, hidden button đánh dấu 🚫 |
| 22a | Cache hit cùng identity | Tx thứ 2 cùng (kind, bank, last4) < 5min | Skip UPSERT, update last_tx_at |
| 22b | Cache key tách theo kind | Cùng display_id khác kind | 2 cache entries riêng, không collide |
| 23 | Cache invalidate sau hide | Hide → tx mới về | UPSERT branch, status vẫn 'hidden' (KHÔNG flip) |
| 23b | Cache hit + cron archive race | Cache có cached_id, cron set archived → tx mới về (cache chưa expire) | TOUCH_SQL flip archived→active, return `was_resurrected=True`, fire fs_resurrected. Cache hit KHÔNG miss resurrect. |
| 23c | Multi-process cache stale | Worker A có cache, Worker B chạy cron archive → tx về Worker A | TOUCH_SQL ở Worker A handle resurrect đúng độc lập với cache state |
| 23d | TOUCH_SQL row gone | Cache có cached_id, row đã bị xoá ngoài | TOUCH_SQL trả 0 row → caller invalidate cache → fallback slow path UPSERT |
| 23e | was_resurrected bool type | New INSERT path (before CTE empty) | COALESCE trả FALSE (bool), KHÔNG NULL — match dataclass `was_resurrected: bool` |
| 24 | Backfill: distinct strings | tx có 5 distinct bank_account_str | 5 funding_sources được tạo |
| 25 | Backfill: tx rỗng bank_account | bank_account_str="" | Skip, fs_id NULL |
| 26a | Discovery notification embedded | Tx đầu tiên TK mới | 1 message duy nhất (header + picker), KHÔNG 2 message |
| 26b | Discovery cooldown | Tx thứ 2+ cùng identity | Không re-fire fs_discovered, không re-prepend header |
| 26c | Resurrect notification timing | Tx về TK archived | Picker gửi trước, sleep 1.5s, then notify |
| 26d | Resolve failure fallback | DB lỗi giữa lúc resolve | Tx vẫn INSERT với funding_source_id=NULL, không crash pipeline |
| 27 | State timeout 5min | rename_input idle 6min | bot_state cleared, không leak |
| 28a | Auto-archive cron | last_tx_at > 180d, status='active' | status='archived', archived_at=NOW() |
| 28b | Cron không archive hidden | last_tx_at > 180d, status='hidden' | KHÔNG flip, status='hidden' giữ nguyên |
| 29 | Analytics events | discovery, rename, hide, archived (cron), resurrect, manual_add, report_filtered | Mỗi action emit đúng 1 event trong 7 loại, kèm properties đầy đủ |
| 30 | Sheets transitional path | gspread upsert vào FUNDING_SOURCES sheet | Tương đương Postgres semantics |

---

## 6. Rollout Plan

**Phase 0 — Sheets implementation (hôm nay, có thể ship trước Postgres migration):**
1. Thêm worksheet `FUNDING_SOURCES` với schema §2.2.
2. Refactor `sheets.py::append_transaction` → call `funding_sources.resolve(...)` trước, dùng kết quả update column P + thêm column Q (`funding_source_id` int).
3. Implement `handlers/accounts.py` với commands + callbacks.
4. Migrate `/banks` để JOIN với FUNDING_SOURCES worksheet (lấy nickname).
5. Run backfill 1 lần.

**Phase 1 — Postgres migration:**
1. CREATE TABLE funding_sources + ALTER transactions theo §2.1.
2. Migration script đọc `FUNDING_SOURCES` worksheet → INSERT Postgres.
3. Cutover cùng lúc với F-saas-refactor.

**Re-eval triggers:**
- Nếu user feedback nhiều về "muốn merge 2 funding sources" (vd: thẻ thay số nhưng cùng tài khoản) → spec F08.1 thêm `merge_into_id`.
- Nếu Plaid integration (Global track) cần share entity → review xem cần extend schema hay split.

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-11 | Initial BE tech doc — Sheets transitional schema (worksheet + col Q FK mirror) + Postgres target (DDL với check constraints, partial unique index không cần thiết vì `last4 NOT NULL DEFAULT ''`). UPSERT_SQL canonical với CTE-based `was_resurrected` detection + `COALESCE(..., FALSE)` strict bool. TOUCH_SQL cho cache-hit path xử lý multi-process resurrect race. Inference rules cho credit_card / e_wallet. Backfill script với `kind='bank_account'` constraint. 30 test cases với subcases. Locked sau nhiều round in-session review. |
