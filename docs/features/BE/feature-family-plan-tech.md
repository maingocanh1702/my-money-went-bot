# BE Tech Doc: Family Plan — Quản lý chi tiêu của con (FAM)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-11
> **Feature doc:** [feature-family-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/drafts/feature-family-plan.md)
> **Tham chiếu:**
> - [feature-funding-sources-tech.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-funding-sources-tech.md) — entitlement contract `can_ingest_transaction()`
> - [feature-pricing-tiers-tech.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-pricing-tiers-tech.md) — tier gating, pricing bump
> - [feature-onboarding-tech.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/BE/feature-onboarding-tech.md) — invite flow extension
> - [TDD-vi §6.3 PDPA](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)

---

## 1. Implementation Overview

| Module | File (target) | Responsibility |
|--------|--------------|----------------|
| Family service | `services/family.py` | CRUD family_accounts, family_members, invite lifecycle |
| Budget service | `services/family_budgets.py` | Budget CRUD, threshold check, alert trigger |
| Entitlement | `services/entitlement.py` | `can_ingest_transaction()` — cross-feature (extend from F08) |
| Invite handler | `handlers/family_invite.py` | Token generation, accept/decline callbacks |
| Bot commands | `handlers/family.py` | `/family`, `/family dashboard`, `/family invite`, `/family budget`, `/family remove`, `/family leave` |
| Child commands | `handlers/family_child.py` | `/my spending`, `/my budgets`, `/my accounts` |
| Cron jobs | `services/family_lifecycle.py` | `close_stale_memberships()` daily, invite expiry hourly |
| Consent gate | `middleware/consent.py` | Version check trước handler dispatch |

Pipeline integration:

```
Tx ingest (F02) → can_ingest_transaction() [entitlement] → INSERT tx
                                                             ↓
                                               Budget threshold check
                                                             ↓
                                               Alert 80%/100% → notify parent + child
```

---

## 2. Database Schema + Edge Cases (Backend)

### 2.1. DDL

```sql
CREATE TABLE family_accounts (
    id              SERIAL PRIMARY KEY,
    owner_user_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name            VARCHAR(64) NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'trialing',
    trial_ends_at   TIMESTAMPTZ,
    downgraded_at   TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    archived_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_fam_status CHECK (status IN ('active','trialing','downgraded','cancelled','archived')),
    CONSTRAINT chk_fam_owner_required CHECK (
        status IN ('cancelled','archived') OR owner_user_id IS NOT NULL
    )
);
-- NOTE: owner_user_id nullable for PDPA hard-delete. Active/trialing/downgraded MUST have owner.

CREATE TABLE family_members (
    id                          SERIAL PRIMARY KEY,
    family_id                   INTEGER NOT NULL REFERENCES family_accounts(id),
    user_id                     INTEGER NOT NULL REFERENCES users(id),
    role                        VARCHAR(8) NOT NULL,
    invited_by                  INTEGER NOT NULL REFERENCES users(id),
    joined_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at                  TIMESTAMPTZ,
    child_age_at_invite         SMALLINT,
    consent_accepted_at         TIMESTAMPTZ NOT NULL,
    consent_disclosure_version  INTEGER NOT NULL,
    CONSTRAINT chk_fm_role CHECK (role IN ('parent','child')),
    CONSTRAINT chk_fm_child_age CHECK (
        (role = 'parent' AND child_age_at_invite IS NULL)
        OR (role = 'child' AND child_age_at_invite BETWEEN 13 AND 17)
    )
);

CREATE UNIQUE INDEX uq_family_member_active
    ON family_members(family_id, user_id) WHERE removed_at IS NULL;
CREATE UNIQUE INDEX uq_user_single_active_family
    ON family_members(user_id) WHERE removed_at IS NULL;
CREATE INDEX idx_fm_family_role ON family_members(family_id, role) WHERE removed_at IS NULL;

CREATE TABLE family_budgets (
    id              SERIAL PRIMARY KEY,
    family_id       INTEGER NOT NULL REFERENCES family_accounts(id),
    user_id         INTEGER NOT NULL REFERENCES users(id),
    category_id     INTEGER,
    amount_vnd      BIGINT NOT NULL,
    period          VARCHAR(8) NOT NULL DEFAULT 'monthly',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_fb_period CHECK (period IN ('monthly')),
    CONSTRAINT chk_fb_amount CHECK (amount_vnd > 0 AND amount_vnd <= 100000000)
);

CREATE UNIQUE INDEX uq_family_budget_category
    ON family_budgets(family_id, user_id, category_id, period)
    WHERE category_id IS NOT NULL;
CREATE UNIQUE INDEX uq_family_budget_total
    ON family_budgets(family_id, user_id, period)
    WHERE category_id IS NULL;

CREATE TABLE family_invites (
    id                      SERIAL PRIMARY KEY,
    family_id               INTEGER NOT NULL REFERENCES family_accounts(id),
    invited_by              INTEGER NOT NULL REFERENCES users(id),
    target_email            VARCHAR(255),
    target_phone            VARCHAR(20),
    target_role             VARCHAR(8) NOT NULL,
    target_child_age        SMALLINT,
    token_hash              VARCHAR(64) NOT NULL,
    status                  VARCHAR(8) NOT NULL DEFAULT 'pending',
    expires_at              TIMESTAMPTZ NOT NULL,
    accepted_at             TIMESTAMPTZ,
    accepted_by_user_id     INTEGER REFERENCES users(id),
    revoked_at              TIMESTAMPTZ,
    revoked_by              INTEGER REFERENCES users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_fi_contact CHECK (target_email IS NOT NULL OR target_phone IS NOT NULL),
    CONSTRAINT chk_fi_role CHECK (target_role IN ('parent','child')),
    CONSTRAINT chk_fi_age CHECK (
        (target_role = 'parent' AND target_child_age IS NULL)
        OR (target_role = 'child' AND target_child_age BETWEEN 13 AND 17)
    ),
    CONSTRAINT chk_fi_status CHECK (status IN ('pending','accepted','expired','revoked'))
);

CREATE INDEX idx_fi_token ON family_invites(token_hash) WHERE status = 'pending';
CREATE INDEX idx_fi_pending_expiry ON family_invites(expires_at) WHERE status = 'pending';

-- Budget alert dedup (enforce 1 alert / threshold / budget / month)
CREATE TABLE family_budget_alerts (
    id              SERIAL PRIMARY KEY,
    family_id       INTEGER NOT NULL REFERENCES family_accounts(id),
    budget_id       INTEGER NOT NULL REFERENCES family_budgets(id),
    child_user_id   INTEGER NOT NULL REFERENCES users(id),
    threshold       SMALLINT NOT NULL CHECK (threshold IN (80, 100)),
    month_key       VARCHAR(7) NOT NULL,
    fired_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(budget_id, threshold, month_key)
);

-- Invite accept session (short-lived, bound to user+invite, prevents enumeration)
CREATE TABLE invite_accept_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invite_id       INTEGER NOT NULL REFERENCES family_invites(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_hash    VARCHAR(64) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    consumed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ias_active
    ON invite_accept_sessions(user_id, invite_id, expires_at)
    WHERE consumed_at IS NULL;
```

> **Session flow:** Deep link token → server validates token_hash → creates `invite_accept_sessions` row (TTL 10 min) → renders consent screen with callback `fam_invite_accept_{session_hash}`. Session bound to `user_id` + `invite_id`. Callback uses `session_hash` (not raw session UUID) for log-leak safety.

### 2.2. Key Queries

```sql
-- 1. Dashboard: monthly spend per member
SELECT fm.user_id, u.display_name, fm.role,
       COALESCE(SUM(t.amount), 0) AS total_spent,
       COUNT(t.id) AS tx_count
FROM family_members fm
JOIN users u ON u.id = fm.user_id
LEFT JOIN transactions t ON t.user_id = fm.user_id
    AND t.month_key = $2 AND t.confirmed = TRUE AND t.direction = 'out'
WHERE fm.family_id = $1 AND fm.removed_at IS NULL
GROUP BY fm.user_id, u.display_name, fm.role
ORDER BY fm.role, total_spent DESC;

-- 2. Budget accumulated spend (current month)
SELECT fb.id AS budget_id, fb.category_id, fb.amount_vnd,
       COALESCE(SUM(t.amount), 0) AS spent
FROM family_budgets fb
LEFT JOIN transactions t ON t.user_id = fb.user_id
    AND t.month_key = $2 AND t.confirmed = TRUE AND t.direction = 'out'
    AND (fb.category_id IS NULL OR t.category_id = fb.category_id)
WHERE fb.family_id = $1 AND fb.user_id = $3
GROUP BY fb.id, fb.category_id, fb.amount_vnd;

-- 3. Invite lookup (token_hash → invite + family)
SELECT fi.*, fa.name AS family_name, fa.status AS family_status,
       u.display_name AS inviter_name
FROM family_invites fi
JOIN family_accounts fa ON fa.id = fi.family_id
JOIN users u ON u.id = fi.invited_by
WHERE fi.token_hash = $1 AND fi.status = 'pending' AND fi.expires_at > NOW();

-- 4. Active membership lookup
SELECT fm.*, fa.status AS family_status, fa.owner_user_id
FROM family_members fm
JOIN family_accounts fa ON fa.id = fm.family_id
WHERE fm.user_id = $1 AND fm.removed_at IS NULL;

-- 5. Archived family access (owner direct)
SELECT id, name, status, downgraded_at, cancelled_at, archived_at
FROM family_accounts
WHERE owner_user_id = $1 AND status IN ('downgraded','cancelled','archived');

-- 6. Seat count under lock (2-step: lock family row first, then count)
-- Step 1: Lock family row
SELECT id FROM family_accounts WHERE id = $1 FOR UPDATE;
-- Step 2: Count seats (no FOR UPDATE on aggregate)
SELECT role, COUNT(*) AS cnt
FROM family_members
WHERE family_id = $1 AND removed_at IS NULL
GROUP BY role;

-- 7. Budget alert dedup check (INSERT or no-op)
INSERT INTO family_budget_alerts (family_id, budget_id, child_user_id, threshold, month_key)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (budget_id, threshold, month_key) DO NOTHING
RETURNING id;  -- NULL = already fired this month

-- 8. Invite accept session lookup
SELECT s.*, fi.*
FROM invite_accept_sessions s
JOIN family_invites fi ON fi.id = s.invite_id
WHERE s.session_hash = $1
    AND s.user_id = $2
    AND s.consumed_at IS NULL
    AND s.expires_at > NOW()
    AND fi.status = 'pending';

-- 9. Consume session on accept/decline
UPDATE invite_accept_sessions
SET consumed_at = NOW()
WHERE id = $1;
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Concurrency | 2 child accept invite đồng thời → seat overflow | `SELECT FOR UPDATE` trên family row + count check trong transaction (§4.7 feature doc) |
| 2 | Concurrency | Parent set budget cùng lúc child spend → alert miss | Budget check dùng `SUM(amount)` tại thời điểm query, không cache accumulated — eventual consistency OK cho alert |
| 3 | Concurrency | Owner downgrade cùng lúc child tx ingest | Entitlement check `fam.status` — race window: tx có thể ingest trong vài ms trước status flip. Acceptable (not billing-critical) |
| 4 | Security | Callback `fam_budget_{id}` với child_id của family khác | WHERE `family_id = viewer_family_id` enforce scope |
| 5 | Security | Invite token brute force | Token = 32-byte random, lưu sha256. Rate limit: web accept = 5 req/min/IP+token_hash; bot callback = 5 req/min/user_id |
| 6 | Security | Co-parent cố remove co-parent khác | Permission matrix §4.3: chỉ owner remove co-parent. Service reject `FAM_CANNOT_REMOVE` |
| 7 | Data integrity | Owner delete account (PDPA) → family orphaned | `owner_user_id` ON DELETE SET NULL. Active/trialing/downgraded family must cancel first (service pre-check). Archived/cancelled: NULL owner OK, archived data persists. |
| 8 | Data integrity | Child leave → re-invite trong 30d cool-off | Check `removed_at` + 30 day window trên `family_members` trước issue invite |
| 9 | Data integrity | Duplicate invite cùng target | KHÔNG unique constraint trên target (email/phone). Service check: nếu pending invite cùng target → reject `FAM_INVITE_DUPLICATE` |
| 10 | Cross-feature | F02 worker call entitlement cho family_owner khi family trialing | `family_owner` branch check `fam.status in ('active','trialing')` — trialing = pass |
| 11 | Cross-feature | F06 pricing bump → existing annual subscriber | Grandfather 6mo, push-back 50% off 3mo. Billing service handle, not family service |
| 12 | Cross-feature | F08 FS hidden + family dashboard | Dashboard query JOIN `family_members` → `funding_sources`. Hidden FS: tx vẫn có FK → show trong dashboard. FS list exclude hidden theo user intent |
| 13 | Security | Invite callback enumeration risk | `invite_id` sequential → dùng `invite_accept_sessions` table (session_id random, TTL 10 min, bound to user_id + invite_id). Callback dùng `session_id`, không expose `invite_id` directly |

---

## 3. API Contract

### 3.1. Bot commands & callbacks

| Trigger | Command/Callback | Handler | Mô tả |
|---------|-----------------|---------|-------|
| Command | `/family` | `cmd_family_menu()` | Menu chính: members, invite, budgets |
| Command | `/family invite parent <contact>` | `cmd_family_invite()` | Gửi invite co-parent |
| Command | `/family invite child <contact>` | `cmd_family_invite()` | Gửi invite child → age picker |
| Command | `/family budget <child> <category> <amount>` | `cmd_family_budget()` | Set budget |
| Command | `/family dashboard` | `cmd_family_dashboard()` | View tổng hợp |
| Command | `/family remove <member>` | `cmd_family_remove()` | Remove member |
| Command | `/family revoke <invite_id>` | `cmd_family_revoke()` | Hủy invite pending |
| Command | `/family leave` | `cmd_family_leave()` | Leave family (2-step confirm) |
| Command | `/my spending` | `cmd_child_spending()` | Child self-view spending |
| Command | `/my budgets` | `cmd_child_budgets()` | Child self-view budgets |
| Command | `/my accounts` | `cmd_child_accounts()` | Child self-view FS |
| Callback | `fam_invite_accept_{session_hash}` | `cb_invite_accept()` | Accept invite. `session_hash` = sha256 of session UUID (10 min TTL, bound to `user_id` + `invite_id`). Created when user opens invite deep link. Server re-validates invite status/expiry via query #8. |
| Callback | `fam_invite_decline_{session_hash}` | `cb_invite_decline()` | Decline invite. Same session binding. |
| Callback | `fam_budget_adjust_{child_id}` | `cb_budget_adjust()` | Adjust budget CTA from alert |
| Callback | `fam_detail_{member_id}` | `cb_member_detail()` | View member detail |
| Callback | `fam_leave_confirm` | `cb_leave_confirm()` | 2nd step confirm leave |
| Callback | `fam_remove_confirm_{member_id}` | `cb_remove_confirm()` | Confirm remove member |
| Callback | `fam_consent_reaccept` | `cb_consent_reaccept()` | Re-accept updated disclosure |

### 3.2. Idempotency & Rate Limit

> **Rate limit key:** Bot callbacks dùng `user_id` (không dùng IP — Telegram/Discord IP là gateway, không phải real user). Web invite accept link dùng `IP + token_hash`.

| Endpoint | Idempotent? | Rate Limit | Concurrent handling |
|----------|:-----------:|-----------|-------------------|
| `/family invite` | No (new token mỗi lần) | 10 invites/family/giờ (key: `family_id`) | Seat count check trong transaction |
| `fam_invite_accept` | Yes (accept đã accepted = no-op success) | Bot: 5 req/min/`user_id`. Web: 5 req/min/`IP+token_hash` | `SELECT FOR UPDATE` family row |
| `/family budget` | Yes (set lại cùng value = no-op) | 30 req/family/giờ (key: `family_id`) | UPSERT on unique constraint |
| `/family remove` | Yes (remove đã removed = no-op) | 5 req/family/giờ (key: `family_id`) | Check `removed_at` before SET |
| `/family leave` | Yes (leave đã left = no-op) | 3 req/giờ (key: `user_id`) | Check membership active |
| `fam_budget_adjust` | Yes | 30 req/family/giờ (key: `family_id`) | UPSERT |

### 3.3. Error Codes

| HTTP | Error Code | Message (vi) | Trigger |
|------|-----------|-------------|--------|
| 400 | `FAM_INVITE_INVALID` | "Link invite không hợp lệ." | Token hash not found |
| 400 | `FAM_INVITE_EXPIRED` | "Link invite đã hết hạn." | Token past `expires_at` |
| 400 | `FAM_INVITE_REVOKED` | "Invite đã bị hủy." | Token status=revoked |
| 400 | `FAM_INVITE_DUPLICATE` | "Bạn đã gửi invite cho người này rồi. Hủy invite cũ trước." | Pending invite cùng target |
| 400 | `FAM_ALREADY_IN_FAMILY` | "Bạn đang trong family X. Rời trước khi join mới." | User has active membership |
| 400 | `FAM_SEAT_LIMIT_PARENT` | "Đã đủ 2 parent. Không thể thêm." | Parent count >= 2 |
| 400 | `FAM_SEAT_LIMIT_CHILD` | "Đã đủ 4 child. Không thể thêm." | Child count >= 4 |
| 400 | `FAM_CHILD_AGE_INVALID` | "Family Plan dành cho con 13-17 tuổi." | Age < 13 or > 17 |
| 400 | `FAM_COOLOFF_ACTIVE` | "Chờ 30 ngày trước khi mời lại." | Re-invite user left < 30d |
| 400 | `FAM_CONSENT_REQUIRED` | "Disclosure đã cập nhật. Vui lòng chấp nhận lại." | Consent version mismatch |
| 400 | `FAM_BUDGET_INVALID_AMOUNT` | "Số tiền phải từ 1đ đến 100,000,000đ." | amount <= 0 or > 100M |
| 403 | `FAM_CANNOT_REMOVE` | "Bạn không có quyền remove member này." | Co-parent cố remove co-parent |
| 403 | `FAM_BILLING_OWNER_ONLY` | "Chỉ owner mới thực hiện được." | Non-owner cố billing action |
| 403 | `FAM_ENTITLEMENT_DENIED` | "Tài khoản không còn quyền ghi giao dịch." | Entitlement check fail (downgraded/cancelled) |
| 404 | `FAM_NOT_FOUND` | "Bạn chưa có Family." | User not in any family |

### 3.4. Form Field Specifications

#### Invite form (`/family invite`)

| Field | Type | Required? | Default | Validation / Ghi chú |
|-------|------|-----------|---------|----------------------|
| contact | text (email hoặc phone) | ✅ Required | — | Email regex hoặc E.164 phone. Phải 1 trong 2 |
| role | select | ✅ Required | — | `parent` hoặc `child` |
| child_age | number picker | Required nếu role=child | — | 13-17. NULL nếu role=parent |

#### Budget form (`/family budget`)

| Field | Type | Required? | Default | Validation / Ghi chú |
|-------|------|-----------|---------|----------------------|
| child | select (member picker) | ✅ Required | — | Chỉ show role=child trong family |
| category | select (category picker) | Optional | NULL (= budget tổng) | NULL = tổng chi tiêu, else FK categories |
| amount | number input | ✅ Required | — | >0, VND nguyên, max 100,000,000. 0 = xóa budget |
| period | enum | ✅ Required | `monthly` | v1 chỉ support `monthly` |

---

## 4. Implementation Details

### 4.1. State Machine — `family_accounts.status`

```
                      (purchase / upgrade)
                             │
                             ▼
    ┌─────────────┐   payment OK    ┌──────────┐
    │  trialing   │ ──────────────→ │  active   │
    │  (14 ngày)  │                 │           │
    └─────────────┘                 └──────────┘
         │                               │
         │ cancel during trial           │ owner downgrade
         │ OR trial expire no-pay        │ OR owner cancel
         ▼                               ▼
    ┌─────────────┐               ┌──────────────┐
    │  cancelled  │               │ downgraded   │
    └─────────────┘               └──────────────┘
         │                               │
         │  re-upgrade (90d)             │  re-upgrade (90d)
         └─────→ active ←───────────────┘
         │                               │
         │  90d cron                     │  90d cron
         └─────────────┬────────────────┘
                       ▼
                ┌──────────────┐
                │   archived   │  (terminal)
                │              │  memberships closed
                └──────────────┘
```

> **`archived` = terminal state.** Cron 90d flip `downgraded`/`cancelled` → `archived`, set `archived_at`, close all memberships. Owner truy cập archived data qua `can_view_archived_family()`. Không re-upgrade từ `archived` — phải tạo family mới.

### 4.2. Scenarios by Status

#### Status: `trialing`

| # | Scenario | Actor | Trigger | Kết quả |
|---|----------|-------|---------|---------|
| T1 | Trial active, invite parent | Owner | `/family invite parent` | Invite sent, token 7d |
| T2 | Trial active, child tx ingest | System | F02 webhook | Entitlement pass (trialing = active) |
| T3 | Trial expire, chưa pay | System | Cron daily | `status='cancelled'`, notify owner |
| T4 | Trial active, owner pay | Owner | Payment confirm | `status='active'` |

#### Status: `active`

| # | Scenario | Actor | Trigger | Kết quả |
|---|----------|-------|---------|---------|
| A1 | Invite child | Parent | `/family invite child` | Seat check → invite token |
| A2 | Child tx → budget 80% | System | F02 ingest | Alert parent + child |
| A3 | Child tx → budget 100% | System | F02 ingest | "Vượt ngân sách" alert |
| A4 | Owner downgrade → Pro | Owner | `/upgrade` downgrade | `status='downgraded'`, plan flip |
| A5 | Child leave | Child | `/family leave` → confirm | `removed_at=now()`, notify parents |
| A6 | Parent remove child | Parent | `/family remove` → confirm | `removed_at=now()`, future ingest stop |
| A7 | Owner remove co-parent | Owner | `/family remove` | Co-parent `removed_at=now()` |
| A8 | Owner cancel family | Owner | `/family leave` → "cancel toàn bộ" confirm | `status='cancelled'` |

#### Status: `downgraded`

| # | Scenario | Actor | Trigger | Kết quả |
|---|----------|-------|---------|---------|
| D1 | Child cố dùng `/my spending` | Child | Command | Banner "Family đã downgrade. Data read-only." |
| D2 | Owner re-upgrade trong 90d | Owner | `/upgrade` Family | `status='active'`, resume seamless |
| D3 | 90d grace hết | System | Cron daily | `status='archived'`, `archived_at=now()`, `removed_at=now()` cho TẤT CẢ members (gồm owner) |
| D4 | Owner xem archived data | Owner | Dashboard tab | `can_view_archived_family()` direct check |
| D5 | Child mua Pro riêng | Child | `/upgrade` Pro | Child plan flip, ingest resume cá nhân |

#### Status: `cancelled`

| # | Scenario | Actor | Trigger | Kết quả |
|---|----------|-------|---------|---------|
| C1 | Owner re-upgrade trong 90d | Owner | `/upgrade` Family | `status='active'`, resume |
| C2 | 90d hết | System | Cron | `status='archived'`, close all memberships |
| C3 | Co-parent cố access | Co-parent | Any `/family` command | "Family đã bị hủy" |

#### Status: `archived` (terminal)

| # | Scenario | Actor | Trigger | Kết quả |
|---|----------|-------|---------|---------|
| AR1 | Owner xem archived data | Owner | Dashboard "Archived" tab | `can_view_archived_family()` — read-only |
| AR2 | Owner cố re-upgrade | Owner | `/upgrade` Family | Tạo family **mới**, không resume cũ |
| AR3 | Owner hard delete (PDPA) | Owner | PDPA request | `owner_user_id=NULL` (ON DELETE SET NULL). Archived data still exists, owner pointer gone |

**Tổng: 23 scenarios (4 trialing + 8 active + 5 downgraded + 3 cancelled + 3 archived) — pass ≥20 rule.**

### 4.3. Timeout Spec

| Variant | Timeout | Behavior khi timeout |
|---------|---------|---------------------|
| Invite token | 7 ngày từ `created_at` | Cron hourly flip `pending → expired`. Token link trả error "đã hết hạn" |
| Family trial | 14 ngày từ `trial_ends_at` | Cron daily: chưa pay → `status='cancelled'`, notify owner "Trial hết hạn" |
| Re-invite cool-off | 30 ngày từ `removed_at` | Service reject `FAM_COOLOFF_ACTIVE` khi invite cùng user < 30d |
| Downgrade/cancel grace | 90 ngày từ `downgraded_at` / `cancelled_at` | Cron daily: flip `status='archived'`, set `archived_at=now()`, close TẤT CẢ memberships (gồm owner). Terminal — cannot re-upgrade, must create new family |
| Budget alert cooldown | 1 lần / ngưỡng / budget / tháng | Enforced bởi `family_budget_alerts` table. INSERT ON CONFLICT DO NOTHING. 80% và 100% alerts track riêng |
| Grandfather pricing | 6 tháng từ launch day | Renew sau 6 tháng theo giá mới. Notice 30d trước |
| Push-back discount | 3 tháng từ activation | 50% off → full price. Max 1 lần/user |

### 4.4. Caching Strategy

| Cache | Key | TTL | Max entries | Invalidate |
|-------|-----|-----|-------------|-----------|
| Family membership | `fam_role:{user_id}` | 5 min | 5000 | Join/leave/remove/cron close |
| Budget limits | `budget:{family_id}:{child_user_id}` | 1 min | 2000 | Budget set/update/delete |
| Dashboard aggregation | `dash:{family_id}:{month_key}` | 5 min | 1000 | Tx ingest, member change |
| Seat count | `seats:{family_id}` | 5 min | 1000 | Member join/leave/remove |

> **Entitlement: NO CACHE cho F02 ingest path.** `can_ingest_transaction()` phải query DB mỗi lần vì đây là money operation. Cache 5 min có thể cho ingest sai sau downgrade/cancel. Entitlement cache chỉ dùng cho UI gating (menu, dashboard load).
> **Budget cache TTL = 1 min** vì alert accuracy matters. Dashboard có thể delay 5 min.
> **Invalidation strategy:** write-through cho membership changes.

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Purchase Family Plan (new user) | User chưa trial | `status='trialing'`, `trial_ends_at` = now+14d, owner membership created with `role='parent'`, `consent_accepted_at` NOT NULL, `consent_disclosure_version` = CURRENT |
| 2 | Purchase Family Plan (đã trial Pro) | `family_trial_used_at` NULL | Reset trial 14d cho Family |
| 3 | Purchase Family Plan (đã trial Family) | `family_trial_used_at` NOT NULL | Charge ngay, không trial |
| 4 | Invite co-parent happy path | Email valid, seats available | Invite created, token hashed, status=pending |
| 5 | Invite child happy path | Phone valid, age=15, seats available | Invite created with `target_child_age=15` |
| 6 | Invite child age <13 | age=12 | Reject `FAM_CHILD_AGE_INVALID` |
| 7 | Invite khi seat full (parent) | 2 parents đã có | Reject `FAM_SEAT_LIMIT_PARENT` |
| 8 | Invite khi seat full (child) | 4 children đã có | Reject `FAM_SEAT_LIMIT_CHILD` |
| 9 | Accept invite happy path | Valid token, user chưa in family | Member created, consent fields set, invite status=accepted |
| 10 | Accept invite — user đã trong family khác | Valid token, user active elsewhere | Reject `FAM_ALREADY_IN_FAMILY` |
| 11 | Accept expired invite | Token past `expires_at` | Reject `FAM_INVITE_EXPIRED` |
| 12 | Accept revoked invite | Token status=revoked | Reject `FAM_INVITE_REVOKED` |
| 13 | Race: 2 concurrent accept cùng child seat cuối | 2 users accept song song | 1 success, 1 `FAM_SEAT_LIMIT_CHILD`. FOR UPDATE lock |
| 14 | Budget set happy path | child_id valid, amount=500000, category=ăn uống | Budget created/updated |
| 15 | Budget alert 80% | Child accumulated = 405k / 500k budget | Alert fire → parent + child notified |
| 16 | Budget alert 100% | Child accumulated = 510k / 500k | "Vượt ngân sách" alert |
| 17 | Budget alert idempotent | 2nd tx same month past 80% | KHÔNG re-fire 80% alert (1 lần/ngưỡng/tháng) |
| 18 | Entitlement: family_owner active | Owner với family status=active | `can_ingest_transaction()` = True |
| 19 | Entitlement: family_owner downgraded | Owner plan flip → pro | Ingest qua Pro branch, True |
| 20 | Entitlement: child active family | Child membership active, family active | True |
| 21 | Entitlement: child downgraded family | Family status=downgraded | False |
| 22 | Entitlement: child mua Pro riêng | Child plan=pro | True (Pro branch, independent) |
| 23 | Remove child | Owner remove child | `removed_at=now()`, future ingest stop |
| 24 | Remove co-parent by owner | Owner remove co-parent | Success |
| 25 | Remove co-parent by co-parent | Co-parent cố remove co-parent khác | Reject `FAM_CANNOT_REMOVE` |
| 26 | Child leave | 2-step confirm | `removed_at=now()`, 30d cool-off set |
| 27 | Re-invite child <30d | Invite child vừa leave | Reject `FAM_COOLOFF_ACTIVE` |
| 28 | Downgrade family | Owner downgrade | `status='downgraded'`, plan flip, 5 members stop ingest |
| 29 | Re-upgrade <90d | Owner re-upgrade | `status='active'`, resume seamless, no re-invite needed |
| 30 | Cron close stale | 91d past downgrade | ALL members `removed_at=now()` (gồm owner) |
| 31 | Archived access after cron | Owner check archived | `can_view_archived_family()` = True qua `owner_user_id` |
| 32 | Owner join new family after cron | Owner create new family | Success (old membership closed) |
| 33 | Consent gate block | Member version < CURRENT | Handler block, show re-consent banner |
| 34 | Consent re-accept | Member re-consent | Version updated, access resume |
| 35 | Owner leave = cancel | Owner `/family leave` | Prompt "cancel toàn bộ?", confirm → cancelled |
| 36 | PDPA delete member | Member request hard delete | Placeholder in parent dashboard, slot freed |
| 37 | Invite token security | Brute force 6 attempts | Rate limit 5/min/user_id (bot) or IP+hash (web), reject |
| 38 | Dashboard with hidden FS | Child has hidden FS + family active | Tx still show in dashboard (FK exists), FS list excludes hidden |

**38 test cases — pass ≥20 rule.**

---

## 6. Rollout Plan

**Pre-requisites (blocking):**
- [ ] F06 vNext pricing addendum merged (Pro 99k, Business 299k, Family 169k)
- [ ] BRD-vi §5 + PRD-vi §3.6 updated
- [ ] Entitlement service extracted from F08 (shared module)

**Phase 1 — Core (MVP):**
1. Migration: CREATE tables `family_accounts`, `family_members`, `family_budgets`, `family_invites`, `family_budget_alerts`, `invite_accept_sessions`
2. Family service: purchase, invite, accept, leave, remove
3. Consent gate middleware
4. Budget service + alert system
5. Entitlement extension: `family_owner` + member branches
6. Bot handlers: `/family *`, `/my *`
7. Cron: invite expiry (hourly), `close_stale_memberships` (daily)

**Phase 2 — Polish:**
- Ownership transfer flow
- Grandfather pricing migration
- Child gamified UX
- Family fork (co-parent dispute)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v0.1.0 | 2026-05-11 | Initial stub — 6 sections structure. Extracted from feature doc per FE/BE split convention. |
| v1.0.0 | 2026-05-11 | Full spec: DDL 5 tables, 7 key queries, Error Codes 15 codes. Invite callback `invite_id`. Rate limit `user_id` cho bot. Entitlement NO CACHE cho F02 ingest. Budget alert dedup table. Ownership transfer deferred Phase 2. |
| v1.1.0 | 2026-05-11 | **Review fixes:** Add `archived` terminal status (DDL CHECK + state machine + 3 scenarios AR1-AR3). `owner_user_id` nullable ON DELETE SET NULL + conditional CHECK cho PDPA. Fix seat count query (lock family row first). Invite callback `session_hash` pattern with `invite_accept_sessions` table (DDL + key queries #8-#9). Section renumber: 3.3 Error Codes, 3.4 Form Fields. Edge case #13 invite enumeration. `archived_at` column added. 7 tables, 9 key queries, 23 scenarios, 38 tests. |
