# Feature: Family Plan — Quản lý chi tiêu của con (FAM)

> **Version:** v1.0.0 (in-session review iterations — không bump theo memory rule. Bump v1.1.0 khi consumed/handed off.)
> **Ngày tạo:** 2026-05-11
> **Trạng thái:** Draft (pending lock)
> **Owner:** Founder (dev)
> **Market:** 🇻🇳 VN-first (SePay + bank email). Global track sẽ có spec riêng dùng Plaid/TrueLayer + family-account API tương đương.
> **Phase:** Phase 3+ (sau khi F06 Pricing Tiers ổn định, F08 Funding Sources live)
> **Tham chiếu:**
> - [feature-pricing-tiers.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md) (F06) — cần addendum thêm cột Family
> - [feature-funding-sources.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md) (F08) — cần entitlement/visibility join với `family_members`; KHÔNG thêm column trên `funding_sources` (ownership giữ ở user-level)
> - [feature-saas-refactor.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) — multi-tenant boundary, RBAC
> - [feature-onboarding.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-onboarding.md) (F01) — extend với invite flow
> - [BRD-vi §5 Pricing](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) — cần thêm tier Family + bump Pro/Business
> - [PRD-vi §3.6 Tier Gating](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)

---

## 1. Mô tả

Family Plan là tier mới nằm giữa **Pro (99k)** và **Business (299k)**, định giá **169k VND/tháng**, target **phụ huynh muốn quản lý chi tiêu của con 13-17 tuổi**. Khác với Business (B2B, team RBAC nhiều role), Family là **B2C household plan** với 2 role cố định: `parent` và `child`.

Tinh thần thiết kế:
- **Educational, not surveillance** — sell hook là "dạy con xài tiền có trách nhiệm" chứ không phải "soi con". Consent disclosure mandatory cho mọi invited member (owner + co-parent + child).
- **Reuse F08 funding sources** — FS ownership user-level qua `user_id`. KHÔNG denormalize `family_id` vào `funding_sources`. Family visibility qua join `family_members`.
- **Flat seat bundle** — 2 parent + 4 child, không add-on.
- **Soft permission model** — View + Budget Limits + Alerts. Không có approve-before-spend.

**Bundle quan trọng:** Launch Family Plan **đi kèm với pricing bump** Pro 79k→99k, Business 199k→299k. Lý do: pricing ladder 79/199 quá hẹp để Family có room. Mới: 99/169/299 giữ ratio 1:1.7:3.

> **i18n:** Toàn bộ UX user-facing (parent + child) qua `t(user.locale, key)`. Family hiện chỉ ship VN locale ở Phase 3.

---

## 2. Use Cases + Edge Cases

### 2.0. Consent & Visibility (default v1 scope)

**Đây là mặt nền của positioning "educational, not surveillance" — không được skip.**

**Tất cả invited member (child VÀ co-parent) đều phải accept disclosure trước khi join.** Owner self-consent qua purchase flow (xem §3.1).

#### Disclosure cho CHILD accept

Parent (owner + co-parent) sẽ thấy:

| Item | Parent thấy? | Child control? |
|------|-------------|----------------|
| Amount của từng tx | ✅ | ❌ |
| Date/time tx | ✅ | ❌ |
| Category (auto + manual) | ✅ | Edit được trên tx của mình |
| Funding source nickname | ✅ | Đặt nickname được |
| Merchant/description raw | ✅ | ❌ |
| Personal notes child thêm vào tx | ❌ | Private (Phase 2 field) |
| Funding source full account number | ❌ (chỉ last4) | — |
| Aggregate budget remaining | ✅ | ✅ (own view) |

#### Disclosure cho CO-PARENT accept

Co-parent **cũng phải accept** vì owner + co-parent khác thấy được tx detail của co-parent này.

Co-parent accept screen wording:
```
Tien mời bạn vào Family với vai trò co-parent.

Khi đồng ý:
  ✓ Bạn có quyền ngang Tien (trừ billing)
  ✓ CÁC parent khác trong family sẽ THẤY tx của bạn:
    - Số tiền, ngày, category, tên cửa hàng
    - Tên ngắn tài khoản/thẻ bạn link
  ✓ Bạn cũng thấy tx của Tien và các con

Bạn LUÔN có thể: rời family (/family leave).
```

#### Disclosure cho OWNER

Owner self-consent qua purchase flow. Purchase screen embed:
```
Khi mua Family Plan, co-parent bạn invite sau sẽ thấy tx của BẠN (ngang quyền).
[Tôi hiểu — Tiếp tục thanh toán]
```

#### Audit & versioning

- `family_members.consent_accepted_at` set cho **mọi** member (owner, co-parent, child) — NOT NULL.
- `family_members.consent_disclosure_version` set theo version disclosure tại thời điểm accept.
- Khi visibility scope thay đổi: bump version + migration job notify member re-consent. Member chưa re-consent → **access blocked by consent gate** (handler layer check `member.consent_disclosure_version >= CURRENT_DISCLOSURE_VERSION` trước khi cho dashboard load); parent thấy banner "X chưa re-consent disclosure mới". Không cần thêm `status` column — chỉ cần version compare.

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | Parent (owner) | Mua Family Plan từ /upgrade | Tạo `family_accounts` record với `owner_user_id`. Purchase screen embed owner mini-disclosure. 14-day trial nếu chưa từng dùng. |
| 2 | Parent (owner) | `/family invite parent <phone/email>` | Tạo invite token, gửi link. Co-parent click → đọc co-parent disclosure → accept → join với role `parent`. |
| 3 | Parent | `/family invite child <phone/email>` | Tạo invite. Child click → đọc child disclosure → accept → join với role `child`. |
| 4 | Child | Accept invite | Setup account riêng, link funding source riêng. FS có `user_id=child.id` (ownership user-level). Parent dashboard thấy qua join `family_members`. **KHÔNG lưu `family_id` trên `funding_sources`** — xem §4.2. |
| 5 | Parent | `/family budget <child> <category> <amount>` | Set budget limit. Vd: "Long 500k ăn uống/tháng". |
| 6 | System | Child spend → tx ingest qua F02 | Entitlement check (§4.5) → nếu pass, insert tx, tính accumulated. ≥80% budget → alert parent + child. ≥100% → alert "vượt". |
| 7 | Parent | `/family dashboard` | View tổng hợp: spend tháng này của từng member + budget remaining + chart per child. |
| 8 | Parent (owner) | `/family remove <member>` | Member bị remove. FS stop sync (xem 2.2.4). |
| 9 | Co-parent | `/family billing transfer` | Yêu cầu chuyển ownership. Owner hiện tại confirm. |
| 10 | Parent (owner) | Downgrade Family → Pro | Family `status='downgraded'`. Owner giữ Pro cho profile mình; 5 member còn lại xem 2.2.4. |
| 11 | Child | `/my spending` | Xem chi tiêu tháng + breakdown category. Self-view. |
| 12 | Child | `/my budgets` | Xem các budget đang áp lên mình + spent/remaining. |
| 13 | Child | `/family leave` | Confirm 2-step → child removed. Future ingestion stop. Historical visible cho parents. Xem 2.2.8. |
| 14 | Parent | `/family revoke <invite_id>` | Hủy invite pending. Token invalidated, status→`revoked`. |

### 2.2. Edge Cases

**2.2.1. Child <13 thử onboarding**
Scope rõ là 13+ (xem §6). Nếu <13 cố accept: UI cảnh báo "Family Plan dành cho con 13-17". Không hard-block (self-declared tuổi không verify được).

**2.2.2. Trial chained giữa Pro và Family**
- New user → 14-day Pro trial (F06).
- Pro user upgrade Family → **trial reset 14 ngày Family**.
- Đã từng dùng trial Family → không reset. Track qua `users.family_trial_used_at`.

**2.2.3. Existing Pro/Business subscriber gặp pricing bump (79k→99k / 199k→299k)**
Grandfather **6 tháng** giá cũ. Email + in-app notice ≥30 ngày trước renewal mới. Push-back option: 50% off 3 tháng tiếp + full price (max 1 lần/user). Xem §5.

**2.2.4. Family downgrade về Pro — 5 member còn lại**
- `family_accounts.status='downgraded'`, set `downgraded_at`. Owner user-plan flip từ `family_owner` → `pro` (entitlement §4.5 — owner ingestion tiếp tục qua Pro branch).
- 5 user records (co-parent + 4 child) **không delete** — profiles persist.
- Membership rows giữ `removed_at=NULL` trong 90-day grace.
- FS của 5 user: **stop ingestion mới** (entitlement service trả False vì family status ≠ active/trialing).
- Historical data đã ingested: **read-only visible trong dashboard owner**. Tab "Archived family data — view only".
- 5 member tự login: banner "Family này đã downgrade. Data của bạn read-only. Mua Pro riêng để tiếp tục."
- Re-upgrade Family trong **90 ngày** → resume sync seamless, không phải re-invite.
- Sau 90 ngày → cron job set `removed_at=now()` cho **toàn bộ memberships, gồm cả owner**. Owner vẫn xem archived data qua `family_accounts.owner_user_id` direct check (§4.6 `can_view_archived_family`); mọi user có thể join/tạo family mới. Re-invite required nếu owner re-upgrade.

**2.2.5. Child seat allocated bị remove → slot free**
4 child seats là pool, remove 1 → free 1 slot. Lịch sử child cũ vẫn read-only trong dashboard owner.

**2.2.6. Co-parent dispute (vợ chồng ly thân)**
Out of scope v1. Workaround: owner remove co-parent. Phase 2 sẽ có "family fork".

**2.2.7. Funding source confusion — child link nhầm FS của parent**
F08 canonical identity `(user_id, kind, bank, last4)`. Child `user_id` riêng → FS riêng dù trùng last4. Lúc invite child, bot warning "Chỉ link tài khoản/ví đứng tên con. Không link thẻ chính của bố mẹ — dùng /family share-fs (Phase 2)."

**2.2.8. Child leaves family voluntarily (`/family leave`)**
- 2-step confirm dialog.
- `family_members.removed_at = now()`. Child mất quyền dashboard family.
- **Future ingestion stop** cho FS của child.
- **Historical family-period data**: vẫn visible cho parents. Badge "Đã rời family — data đến `removed_at`".
- Child FS ownership giữ với child. Mua Pro riêng → ingestion resume cho cá nhân.
- Parent nhận notification "X đã rời family".
- **30-day cool-off** chống re-invite spam.

**2.2.9. User cố join 2 family song song**
v1 invariant: **1 user = tối đa 1 active membership**. DB partial unique index enforce (§4.1). Accept invite family thứ 2 → reject "Bạn đang trong family X. Rời family đó trước khi join family mới." Lifecycle cron đảm bảo membership của cancelled/downgraded family eventually closed (§4.6).

**2.2.10. Member account deletion (PDPA / hard delete)**
Khi member request delete:
- User row + transactions: hard delete theo TDD §6.3.
- **Cross-family side effect**: parent dashboard hiển thị placeholder "Member đã xóa data theo yêu cầu", không silent gap.
- Family record không bị xóa. Slot free để invite mới.
- Audit log giữ event `member_data_deleted` (no PII), 12 tháng retention.

---

## 3. UX Flow

### 3.1. Upgrade flow (parent flow)

```
/upgrade
  ├─ [Pro 99k]  [Family 169k 🆕]  [Business 299k]
  ↓ user chọn Family
  Family Plan 169k/tháng — 2 parent + 4 child
  ┌─────────────────────────────────────┐
  │ ✓ Quản lý chi tiêu cho 4 con        │
  │ ✓ Set ngân sách + alert real-time   │
  │ ✓ Dashboard tổng hợp gia đình       │
  │ ✓ Trial 14 ngày miễn phí            │
  └─────────────────────────────────────┘

  ⓘ Co-parent bạn invite sau sẽ thấy tx
     của BẠN (ngang quyền, trừ billing).

  [Tôi hiểu — Bắt đầu trial 14 ngày]
  [Tôi hiểu — Pay 169k now]
  [Tôi hiểu — Annual 1.724k save 15%]
```

> Owner click bất kỳ button = self-consent. Lưu `consent_accepted_at` + `consent_disclosure_version` cho owner row.

### 3.2. Invite flow

Owner gõ `/family` → menu:
```
👨‍👩‍👧‍👦 Family — Tien (owner)
Members (1/6):
  • Tien (you, parent)

  [+ Invite parent]   [+ Invite child]   [Manage budgets]
```

#### Co-parent accept screen
```
Tien mời bạn vào Family với vai trò co-parent.

Khi đồng ý:
  ✓ Bạn ngang quyền Tien (trừ billing)
  ✓ Các parent khác trong family sẽ THẤY tx của bạn:
    - Số tiền, ngày, category, tên cửa hàng
    - Tên ngắn tài khoản/thẻ bạn link
  ✓ Bạn cũng thấy tx của Tien và các con

Bạn LUÔN có thể rời family (/family leave).

[Tôi đồng ý — Join Family]   [Từ chối]
```

#### Child invite (extra friction tuổi)
```
Nhập email/SĐT con:
> +84901234567

Tuổi con (13-17)?
  [13]  [14]  [15]  [16]  [17]

✓ Đã gửi invite. Hết hạn 7 ngày.
```

#### Child accept screen
```
Bố/mẹ Tien mời bạn vào Family.

Khi đồng ý, bố mẹ sẽ THẤY:
  ✓ Số tiền + ngày của từng giao dịch
  ✓ Phân loại (ăn uống, transport, v.v.)
  ✓ Tên ngắn tài khoản/thẻ bạn link
  ✓ Tên cửa hàng / mô tả giao dịch
  ✓ Ngân sách & remaining

KHÔNG thấy:
  ✗ Ghi chú riêng (private — Phase 2)
  ✗ Số tài khoản đầy đủ (chỉ 4 số cuối)

Bạn LUÔN có thể:
  • Rời family (/family leave)
  • Xóa data của mình (PDPA)

[Tôi đồng ý — Join Family]   [Từ chối]
```

> **Copy lock:** Wording canonical v1. Edit phải bump `consent_disclosure_version` + migration cho user cũ re-consent.

### 3.3. Parent dashboard (`/family dashboard`)

```
👨‍👩‍👧‍👦 Family này (T05/2026)

Tổng chi: 3.450k VND

Per member:
  • Tien (parent)    1.890k
  • Hà (co-parent)     620k
  • Long (15t)         540k  ⚠ 108% budget ăn uống
  • An (13t)           400k

[Detail Long]  [Detail An]  [Adjust budgets]
```

### 3.4. Budget alert (real-time)

80% ngưỡng:
```
🔔 Alert
Long vừa chi 120k tại "GongCha Đồng Khởi" (ăn uống).
Tháng này: 405k / 500k budget ăn uống (81%).
Còn 95k cho 19 ngày.

[Xem chi tiết]  [Adjust budget]
```

100% ngưỡng:
```
🚨 Vượt ngân sách
Long: 510k / 500k budget ăn uống (102%).
Tháng này còn 18 ngày.

[Xem chi tiết]  [Tăng budget]
```

> **v1 alert CTA:** chỉ 2 actions có implement thực tế. Quick-chat shortcut là Phase 2 — không show placeholder.

### 3.5. Child-side commands (v1 minimum)

```
/my spending       # Chi tiêu tháng + breakdown
/my budgets        # Budget + spent/remaining
/my accounts       # FS của mình
/family leave      # Rời family (2-step)
```

Child cũng nhận **direct alert** 80%/100% budget với CTA "Xem chi tiết".

`/my spending` mockup:
```
💰 Long — T05/2026

Tổng chi: 540k VND

Top category:
  • Ăn uống     405k / 500k budget (81%) ⚠
  • Transport   95k
  • Khác        40k

[Detail Ăn uống]  [Sửa category]
```

---

## 4. Domain Model

### 4.1. New tables

**`family_accounts`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| owner_user_id | int | FK → users(id). 1 user = 1 owner role tại 1 thời điểm |
| name | string(64) | Default `"{owner_name}'s family"`, edit được |
| status | enum | `active` / `trialing` / `downgraded` / `cancelled` |
| trial_ends_at | timestamptz? | NULL nếu không trial |
| created_at | timestamptz | |
| downgraded_at | timestamptz? | Set khi 2.2.4 trigger. Cron §4.6 dùng để close memberships sau 90 ngày |
| cancelled_at | timestamptz? | Set khi owner cancel. Cron §4.6 dùng tương tự `downgraded_at` |

**`family_members`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| family_id | int | FK → family_accounts(id) |
| user_id | int | FK → users(id) |
| role | enum | `parent` / `child` |
| invited_by | int | FK → users(id) |
| joined_at | timestamptz | |
| removed_at | timestamptz? | Soft delete. Cron §4.6 set cho tất cả members (gồm owner) sau 90d grace của downgraded/cancelled family |
| child_age_at_invite | int? | 13-17, NULL nếu role=parent |
| consent_accepted_at | timestamptz | **NOT NULL** — owner: set khi purchase. Co-parent + child: set khi accept invite |
| consent_disclosure_version | int | **NOT NULL** — version disclosure text khi accept. Bump → trigger re-consent gate |

**Constraints:**
```sql
-- Cấm duplicate trong cùng family
CREATE UNIQUE INDEX uq_family_member_active
  ON family_members(family_id, user_id) WHERE removed_at IS NULL;

-- v1 invariant: 1 user = tối đa 1 active family membership
CREATE UNIQUE INDEX uq_user_single_active_family
  ON family_members(user_id) WHERE removed_at IS NULL;
```

> **v1 invariant locked:** 1 user thuộc tối đa 1 active family. Multi-family/fork là Phase 2. Index hoạt động với lifecycle cron §4.6 — đảm bảo cancelled/downgraded family eventually close membership của tất cả member (gồm owner).

**`family_budgets`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| family_id | int | FK |
| user_id | int | FK (member bị áp budget — role=child thường) |
| category_id | int? | NULL = tổng. Else FK → categories |
| amount_vnd | bigint | VND nguyên (no decimal — 500k = 500000). Global Phase 2 đổi sang `amount_minor` + `currency`. |
| period | enum | `monthly` (v1 chỉ support monthly) |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Uniqueness — partial indexes (xử lý NULL trap):**
```sql
CREATE UNIQUE INDEX uq_family_budget_category
  ON family_budgets(family_id, user_id, category_id, period)
  WHERE category_id IS NOT NULL;

CREATE UNIQUE INDEX uq_family_budget_total
  ON family_budgets(family_id, user_id, period)
  WHERE category_id IS NULL;
```

**`family_invites`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| family_id | int | FK |
| invited_by | int | FK → users(id) |
| target_email | string? | |
| target_phone | string? | (email hoặc phone — 1 trong 2 NOT NULL) |
| target_role | enum | `parent` / `child` |
| target_child_age | int? | |
| token_hash | string(64) | sha256 của token; plaintext token chỉ trong link |
| status | enum | `pending` / `accepted` / `expired` / `revoked` |
| expires_at | timestamptz | created_at + 7d |
| accepted_at | timestamptz? | |
| accepted_by_user_id | int? | FK → users(id) |
| revoked_at | timestamptz? | |
| revoked_by | int? | FK → users(id) |

**Constraints / invariants:**
- `CHECK (target_email IS NOT NULL OR target_phone IS NOT NULL)`
- `CHECK ((target_role = 'parent' AND target_child_age IS NULL) OR (target_role = 'child' AND target_child_age BETWEEN 13 AND 17))` — parent invite không có age; child invite phải 13-17.
- Token one-time: accept chỉ pass khi `status='pending' AND expires_at > now()`. Sau accept → `status='accepted'`, không reuse.
- Background job mỗi giờ flip `pending → expired` cho row quá `expires_at`.

### 4.2. F08 extension — NONE on `funding_sources` schema

**Locked:** KHÔNG thêm column nào vào `funding_sources` cho Family Plan.

- FS ownership đã là user-level qua `user_id` (canonical F08 §1).
- Family visibility membership-level — parent dashboard query qua join:
  ```sql
  SELECT fs.*
  FROM funding_sources fs
  JOIN family_members fm ON fm.user_id = fs.user_id AND fm.removed_at IS NULL
  WHERE fm.family_id = :parent_family_id
  ```
- **Why no `family_id` on `funding_sources`:** denormalize sẽ tạo bug khi child rời family / cancel — phải cập nhật FK, race với ingestion, child join family mới phải update FS records. Membership join idempotent và safe.

> **Perf note:** Nếu dashboard query bottleneck (>50ms p95), cân nhắc materialized view `family_member_fs_lookup`. Phase 2.

### 4.3. Permission matrix

| Action | Owner | Co-parent | Child |
|--------|:-----:|:---------:|:-----:|
| View own data | ✅ | ✅ | ✅ |
| View family dashboard (all members) | ✅ | ✅ | ❌ (own only via `/my *`) |
| View other member tx detail | ✅ | ✅ | ❌ |
| Set/edit budget cho bất kỳ child | ✅ | ✅ | ❌ |
| Invite parent | ✅ | ✅ | ❌ |
| Invite child | ✅ | ✅ | ❌ |
| Revoke pending invite | ✅ | ✅ | ❌ |
| Remove child | ✅ | ✅ | ❌ |
| Remove co-parent | ✅ | ❌ | ❌ |
| Remove owner | ❌ (phải transfer trước) | ❌ | ❌ |
| Leave family (self) | ✅ (= cancel family) | ✅ | ✅ |
| Billing — pay/cancel/downgrade | ✅ | ❌ | ❌ |
| Request ownership transfer | — | ✅ (request only) | ❌ |
| Approve ownership transfer | ✅ (incoming request) | — | ❌ |

> **Owner leave = cancel family:** owner `/family leave` không transfer trước → prompt "Bạn là owner. Rời family = cancel toàn bộ. Confirm?"

### 4.4. Resolver pseudo-code

```python
def is_family_owner(user_id: int, family_id: int) -> bool:
    fam = get_family(family_id)
    return fam is not None and fam.owner_user_id == user_id

def family_role(user_id: int) -> Literal["owner", "parent", "child", None]:
    """v1 invariant: 1 user = max 1 active family."""
    m = get_active_membership(user_id)
    if not m:
        return None
    fam = get_family(m.family_id)
    if fam.owner_user_id == user_id:
        return "owner"
    return m.role

def can_view_user_data(viewer_id: int, target_id: int) -> bool:
    if viewer_id == target_id:
        return True
    vm = get_active_membership(viewer_id)
    if not vm or vm.role != "parent":
        return False
    return is_active_member(vm.family_id, target_id)

def can_set_budget(viewer_id: int, target_id: int) -> bool:
    return (
        can_view_user_data(viewer_id, target_id)
        and family_role(viewer_id) in ("owner", "parent")
        and family_role(target_id) == "child"
    )

def can_perform_billing(user_id: int, family_id: int) -> bool:
    return is_family_owner(user_id, family_id)

def can_remove_member(viewer_id: int, target_id: int) -> bool:
    viewer_role = family_role(viewer_id)
    target_role = family_role(target_id)
    if viewer_role not in ("owner", "parent"):
        return False
    if target_role == "owner":
        return False
    if target_role == "parent" and viewer_role != "owner":
        return False
    return True
```

> **Archived family access** (post-90d cron) đi qua `can_view_archived_family()` ở §4.6, không qua các resolver trên (vì owner membership đã `removed_at`).

### 4.5. Entitlement resolver — `can_ingest_transaction`

**Cross-feature critical.** F02 worker phải hỏi entitlement service trước khi ingest tx, KHÔNG hard-code logic.

```python
def can_ingest_transaction(user_id: int, fs: FundingSource) -> bool:
    if fs.user_id != user_id:
        raise ValueError("FS ownership mismatch")

    plan = get_user_plan(user_id)

    # Pro/Business cá nhân
    if plan in ("pro", "business"):
        return True

    # Family owner: PHẢI check family status — không bypass dựa vào plan name
    if plan == "family_owner":
        fam = get_owned_family(user_id)
        return fam is not None and fam.status in ("active", "trialing")

    # Co-parent / child: check membership + family status
    m = get_active_membership(user_id)
    if m:
        fam = get_family(m.family_id)
        if fam.status in ("active", "trialing"):
            return True
        return False  # downgraded/cancelled → stop ingest

    # Free user → fallback Free tier logic
    return free_tier_within_quota(user_id)
```

**Behavior rules:**
- Owner downgrade Family → Pro: user-plan flip `family_owner` → `pro`. Owner ingestion qua Pro branch (KHÔNG qua `family_owner`). Plan state = source of truth.
- Co-parent/child sau family downgrade: entitlement False → stop. Mua Pro riêng → plan flip → ingest resume cá nhân.
- Family cancel: co-parent/child stop; owner mất Family entitlement nhưng giữ Pro nếu downgrade path.

> **F02/F08 contract:** Worker MUST call `can_ingest_transaction()` trước insert. Add vào F02 §3 + F08 §4.

### 4.6. Membership lifecycle — cron job (90-day grace)

Single-active-family invariant + cancel/downgrade lifecycle phải work cùng nhau. Postgres partial index không reference được table khác, nên dùng cron.

**Key design:** sau 90 ngày, close **TẤT CẢ** memberships (gồm owner). Nếu giữ owner membership active forever, owner bị `uq_user_single_active_family` chặn join family mới. Owner archived access đi qua `family_accounts.owner_user_id` direct check, KHÔNG cần active membership.

```python
# Run daily
def close_stale_memberships():
    """
    Sau 90 ngày kể từ downgrade/cancel, close TẤT CẢ memberships (gồm owner).
    Owner archived access qua family_accounts.owner_user_id, không cần membership active.
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

**Lifecycle table:**

| Family status | Membership state (during 90d) | Membership state (after 90d) |
|---------------|------------------------------|------------------------------|
| `active`/`trialing` | All `removed_at=NULL` | (n/a — không trigger) |
| `downgraded`/`cancelled` | All members `removed_at=NULL` để resume seamless nếu re-upgrade | **All members `removed_at=now()` (gồm owner).** Owner vẫn xem archived data qua `family_accounts.owner_user_id` direct check. |

**Archived-family owner access resolver:**

```python
def can_view_archived_family(user_id: int, family_id: int) -> bool:
    """
    Owner cũ vẫn xem được archived family data sau khi cron đóng membership.
    """
    fam = get_family(family_id)
    if not fam:
        return False
    return (
        fam.owner_user_id == user_id
        and fam.status in ("downgraded", "cancelled", "archived")
    )
```

UI implication: owner Pro thấy "Archived family data" tab nếu `can_view_archived_family(user_id, prev_family_id)` trả True. Tab này độc lập với `family_role(user_id)` (sẽ trả None sau cron đóng membership).

> **Cron deliverable:** Add vào F09 Scheduled Jobs spec với cadence daily + idempotency check.

### 4.7. Seat limit enforcement

Schema không enforce được, service dùng **row lock + count** trong DB transaction:

```python
MAX_PARENTS = 2
MAX_CHILDREN = 4

def accept_invite(invite_id: int, user_id: int):
    with db.transaction():
        fam = db.query(FamilyAccount).filter(...).with_for_update().one()
        invite = db.query(FamilyInvite).filter(...).with_for_update().one()

        if invite.status != "pending" or invite.expires_at < now():
            raise InviteExpired()

        count = db.query(FamilyMember).filter(
            family_id=fam.id, removed_at=None
        ).group_by(role).count()

        if invite.target_role == "parent" and count["parent"] >= MAX_PARENTS:
            raise SeatLimitExceeded("parent")
        if invite.target_role == "child" and count["child"] >= MAX_CHILDREN:
            raise SeatLimitExceeded("child")

        if get_active_membership(user_id):
            raise AlreadyInFamily()

        db.add(FamilyMember(
            family_id=fam.id,
            user_id=user_id,
            role=invite.target_role,
            consent_accepted_at=now(),
            consent_disclosure_version=CURRENT_DISCLOSURE_VERSION,
            ...
        ))
        invite.status = "accepted"
        invite.accepted_at = now()
        invite.accepted_by_user_id = user_id
```

### 4.8. Data retention & PDPA

| Data | Retention | Visibility post-event |
|------|-----------|----------------------|
| Tx của member khi member active | Indefinite (per global retention policy) | Parent thấy full detail |
| Tx của member sau `/family leave` | Full detail giữ ở DB; **query-layer hides merchant/description sau 24 tháng từ `removed_at`** | Parent thấy badge "Đã rời family — data đến `removed_at`", detail bị mask sau 24mo |
| Tx sau hard delete (PDPA) | Hard delete theo TDD §6.3 | Parent thấy placeholder "Member đã xóa data" |
| Family record sau cancel | 90 ngày grace re-upgrade → archive | Owner Pro thấy "Archived family" tab qua `can_view_archived_family()` |
| Audit log (`member_data_deleted`, `consent_accepted`, etc.) | 12 tháng | Internal only |

**Retention enforcement v1 — query-layer first:**
- Query layer hides `merchant`, `description` khi `now() > removed_at + 24 months`. Aggregate (amount, category, count) vẫn visible.
- **KHÔNG** destructive redaction trong v1. Raw data giữ ở DB để recover nếu rule đổi, và để PDPA delete operate đúng.
- Destructive job có thể add ở Phase 2 nếu compliance yêu cầu.

> **Cross-doc:** Sync với TDD §6.3. **Action item:** open issue với TDD owner thêm Family retention rules.

---

## 5. Pricing & Migration

### 5.1. Target pricing post-launch

| Tier | Current (VN) | Target (VN, post Family launch) | Change |
|------|--------------|--------------------------------|--------|
| Free | 0 | 0 | — |
| Pro | 79k | **99k** | +25% |
| Family | — | **169k** 🆕 | new |
| Business | 199k | **299k** | +50% |

Annual (15% off, **exact math**):
- Pro: 99k × 12 × 0.85 = **1.010k/năm**
- Family: 169k × 12 × 0.85 = **1.724k/năm** (KHÔNG phải 1.720k)
- Business: 299k × 12 × 0.85 = **3.050k/năm**

> **Marketing rounding:** Nếu marketing muốn "1.720k cho Family" → document explicit là rounded down (extra 4k off).

> **Rollout dependency:** Family Plan launch **requires F06 vNext pricing addendum** trước implementation. Sequence: F06 → BRD-vi §5 → PRD-vi §3.6 → checkout/billing service → Family spec consumable. F06 chưa update = Family launch block.

### 5.2. Grandfathering existing subscribers

- **Subscribers active tại ngày T-30 (T = launch day):** giữ giá cũ **6 tháng** (Pro 79k, Business 199k).
- Email + in-app notice 30 ngày trước launch + 30 ngày trước renewal mới.
- Sau 6 tháng renew theo giá mới. Cancel → giữ access đến hết kỳ.
- **Push-back option:** 50% off 3 tháng tiếp + full price. Max 1 lần/user.

### 5.3. Annual discount với Family

15% off hiện tại. Cân nhắc bump lên 20% vì switching cost cao (multi-member setup). Open question §7.

---

## 6. Cut / Out of scope v1 (Phase 2 backlog)

| Feature | Lý do cut khỏi v1 |
|---------|-------------------|
| Child-side app/view riêng (gamified) | v1 child chỉ có bot commands (§3.5). Gamified UX = Phase 2. |
| Allowance automation | Pattern detection phức tạp. |
| Approve-before-spend | Latency webhook + pháp lý. |
| Family <13 (managed profile) | Tránh COPPA-like. |
| Co-parent shared billing | v1: 1 owner trả. |
| Family fork (co-parent ly thân) | Edge case. |
| `/family share-fs` | Cần shared FS ownership model. |
| Quick chat shortcut parent ↔ child | Phase 2 polish. |
| Private note field cho child tx | Schema reserve `private_note`. |
| Destructive retention redaction job | v1 query-layer hide. |
| Global market track | Phase 2+. |

---

## 7. Open Questions

1. **Family annual discount: 15% hay 20%?** Recommend 20%. Lock trước F06.
2. **Pricing bump rollout date** — sau Wave 0 (Q3 2026) hay sớm hơn?
3. **Phase 2 priority** giữa: child-side gamified vs allowance vs share-fs vs family fork. Customer interview 5-7 parent VN.
4. **Marketing positioning** A/B test landing page trước launch.
5. **TDD §6.3 alignment** — open ticket cho TDD owner thêm Family retention rules.
6. **Co-parent ownership transfer UX** — v1 ship hay defer Phase 2?

---

## 8. Acceptance Criteria (v1 done = check all)

**Core:**
- [ ] User upgrade Pro → Family qua `/upgrade`, 14-day trial trigger nếu chưa dùng.
- [ ] Owner invite 1 co-parent + tối đa 4 child qua email/SĐT, link hết hạn 7 ngày.
- [ ] Co-parent quyền theo §4.3 matrix.
- [ ] FS của child auto-link với `user_id` child, parent dashboard hiển thị qua membership join (KHÔNG `family_id` column).
- [ ] Budget per child × category settable, alert fire 80% và 100%.
- [ ] `/family dashboard` hiển thị đúng cho 6 member.

**Privacy & consent:**
- [ ] Owner purchase flow embed self-disclosure, ghi `consent_accepted_at` + `consent_disclosure_version` cho owner row.
- [ ] Co-parent accept screen hiển thị canonical co-parent disclosure (§3.2), ghi consent fields.
- [ ] Child accept screen hiển thị canonical child disclosure (§3.2), ghi consent fields.
- [ ] `consent_accepted_at` + `consent_disclosure_version` NOT NULL cho mọi member.
- [ ] Consent gate: handler block access nếu `member.consent_disclosure_version < CURRENT_DISCLOSURE_VERSION`.
- [ ] `/family leave` 2-step confirm cho parent và child.
- [ ] Parent KHÔNG modify/delete được tx của child.
- [ ] 30-day cool-off chống re-invite spam.

**Data model invariants:**
- [ ] DB index `uq_user_single_active_family` ngăn user join 2 family.
- [ ] DB partial indexes uniqueness cho `family_budgets`.
- [ ] `family_invites` token one-time use, status flow đúng.
- [ ] CHECK constraint: parent invite `target_child_age IS NULL`; child invite `BETWEEN 13 AND 17`.
- [ ] Seat limit enforce service-layer với `with_for_update()` row lock — race test pass.
- [ ] `amount_vnd` (không `amount_cents`) là canonical money column.

**Entitlement:**
- [ ] `can_ingest_transaction()` đúng cho 5 cases: Pro user, Family owner active, Family owner downgraded (plan flip → Pro), co-parent/child active, co-parent/child downgraded.
- [ ] `family_owner` branch check `fam.status in ("active","trialing")` — không bypass.
- [ ] F02 worker call entitlement trước insert (không hard-code).
- [ ] Test: child mua Pro riêng sau family downgrade → ingest resume cho child.

**Lifecycle & retention:**
- [ ] Downgrade Family → Pro: 5 member profile preserved, FS stop ingest, historical read-only owner.
- [ ] Re-upgrade trong 90 ngày: resume seamless.
- [ ] Cron `close_stale_memberships` daily, set `removed_at` cho **TẤT CẢ members (gồm owner)** sau 90 ngày.
- [ ] Sau cron đóng owner membership, owner Pro vẫn xem "Archived family" tab qua `can_view_archived_family()`.
- [ ] Sau cron, owner có thể join/tạo family mới (không bị `uq_user_single_active_family` chặn).
- [ ] Member leave: query layer hide merchant/description sau 24 tháng.
- [ ] PDPA hard delete: parent dashboard placeholder "Member đã xóa data".

**Child-side UX:**
- [ ] `/my spending`, `/my budgets`, `/my accounts`, `/family leave` ship VN locale.
- [ ] Child nhận direct alert 80%/100% với CTA "Xem chi tiết".

**Pricing rollout:**
- [ ] F06 vNext pricing addendum merged trước Family launch.
- [ ] Existing Pro/Business subscriber giữ giá cũ 6 tháng.
- [ ] Notice email + in-app ≥30 ngày trước price change.
- [ ] Family annual engineering = 1.724k. Marketing rounding document explicit.

**i18n:**
- [ ] Mọi user-facing copy qua i18n layer, VN locale complete.

---

## 9. Changelog

| Version | Date | Notes |
|---------|------|-------|
| v1.0.0 | 2026-05-11 | Initial draft + 3 review rounds merged in-session (per memory rule không bump). Locked: pricing 169k, seat 2P+4C, role parent/child, child 13-17, invite via email/phone + accept, downgrade behavior, grandfather 6mo. Review fixes: consent required cho mọi member (owner self + co-parent + child); permission matrix full với owner vs co-parent split; entitlement `can_ingest_transaction` cross-feature + `family_owner` branch check status; F08 không thêm column; single-active-family invariant + 90-day lifecycle cron đóng **TẤT CẢ** members (gồm owner) sau grace; owner archived access qua `can_view_archived_family()` direct check; data model fixes (amount_vnd, partial indexes, invite status enum, tighter CHECK age constraint); query-layer retention hide 24mo; F06 addendum block-on; annual exact math 1.724k; `cancelled_at` field added; consent gate dùng version compare không cần status column. **Bump v1.1.0 khi consumed/handed off.** |
