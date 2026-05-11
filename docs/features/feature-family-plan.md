# Feature: Family Plan — Quản lý chi tiêu của con (FAM)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-11
> **Trạng thái:** Draft (pending lock)
> **Owner:** Founder (dev)
> **Market:** 🇻🇳 VN-first (SePay + bank email). Global track sẽ có spec riêng dùng Plaid/TrueLayer + family-account API tương đương.
> **Phase:** Phase 3+ (sau khi F06 Pricing Tiers ổn định, F08 Funding Sources live)
> **Tham chiếu:**
> - [feature-pricing-tiers.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-pricing-tiers.md) (F06) — cần addendum thêm cột Family
> - [feature-funding-sources.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-funding-sources.md) (F08) — cần thêm `owner_user_id` scoped theo family
> - [feature-saas-refactor.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) — multi-tenant boundary, RBAC
> - [feature-onboarding.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-onboarding.md) (F01) — extend với invite flow
> - [BRD-vi §5 Pricing](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) — cần thêm tier Family + bump Pro/Business
> - [PRD-vi §3.6 Tier Gating](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)

---

## 1. Mô tả

Family Plan là tier mới nằm giữa **Pro (99k)** và **Business (299k)**, định giá **169k VND/tháng**, target **phụ huynh muốn quản lý chi tiêu của con 13-17 tuổi**. Khác với Business (B2B, team RBAC nhiều role), Family là **B2C household plan** với 2 role cố định: `parent` và `child`.

Tinh thần thiết kế:
- **Educational, not surveillance** — sell hook là "dạy con xài tiền có trách nhiệm" chứ không phải "soi con". Mọi copy + UX phản ánh tinh thần này.
- **Reuse F08 funding sources** — child funding sources là `funding_sources` records bình thường, chỉ thêm `owner_user_id` scoped trong family. Parent thấy aggregate qua join.
- **Flat seat bundle** — 2 parent + 4 child, không add-on. Communicate đơn giản, billing đơn giản.
- **Soft permission model** — View + Budget Limits + Alerts. Không có approve-before-spend (tránh độ trễ webhook + rắc rối pháp lý).

**Bundle quan trọng:** Launch Family Plan **đi kèm với pricing bump** Pro 79k→99k, Business 199k→299k. Lý do: pricing ladder hiện tại (79/199) quá hẹp để Family có room. Pricing mới (99/169/299) giữ ratio 1:1.7:3, ladder rõ ràng hơn.

> **i18n:** Toàn bộ UX user-facing (parent + child) qua `t(user.locale, key)`. Family hiện chỉ ship VN locale ở Phase 3.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | Parent (owner) | Mua Family Plan từ /upgrade | Tạo `family_accounts` record với `owner_user_id`, owner mặc định là parent đầu tiên. 14-day trial nếu chưa từng dùng trial Family. |
| 2 | Parent (owner) | `/family invite parent <phone/email>` | Tạo invite token, gửi link. Co-parent click → accept → join family với role `parent`, ngang quyền owner trừ quyền billing. |
| 3 | Parent | `/family invite child <phone/email>` | Tạo invite. Child accept → join với role `child`, profile riêng, parent thấy data của child trong dashboard. |
| 4 | Child | Accept invite | Setup account riêng (Telegram/Discord), link funding source riêng (Timo Junior, thẻ phụ, ví). FS tự động `owner_user_id=child.id` + `family_id=parent.family`. |
| 5 | Parent | `/family budget <child> <category> <amount>` | Set budget limit. Vd: "Long 500k ăn uống/tháng". |
| 6 | System | Child spend → tx ingest qua F02 | Tính accumulated spend tháng đó cho child × category. Nếu ≥80% budget → alert parent + child. Nếu ≥100% → alert "vượt". |
| 7 | Parent | `/family dashboard` | View tổng hợp: spend tháng này của từng member + ngân sách remaining + chart per child. |
| 8 | Parent (owner) | `/family remove <member>` | Member bị remove khỏi family. Funding sources của member: stop sync (xem 2.2.4). |
| 9 | Co-parent | `/family billing transfer` | Yêu cầu chuyển ownership. Owner hiện tại confirm → ownership chuyển, billing thay đổi. |
| 10 | Parent (owner) | Downgrade Family → Pro | Family record `status='downgraded'`. Owner giữ Pro cho profile mình; 5 member còn lại → xem 2.2.4. |

### 2.2. Edge Cases

**2.2.1. Child <13 thử onboarding**
Scope rõ là 13+ (xem §6 cut). Nếu child <13 cố accept invite: UI cảnh báo "Family Plan dành cho con 13-17. Bạn có thể cân nhắc tự setup Pro để dạy con quan sát chi tiêu của bạn." Không hard-block (vì self-declared tuổi không verify được), nhưng minimize false advertising risk.

**2.2.2. Trial chained giữa Pro và Family**
- New user → 14-day Pro trial (existing F06).
- Pro user (đang trong trial hoặc đã paid) upgrade Family → **trial reset 14 ngày Family**. Lý do: Family value cần multi-member setup, không fair nếu charge ngay.
- Đã từng dùng trial Family → không reset lần 2. Track qua `users.family_trial_used_at`.

**2.2.3. Existing Pro/Business subscriber gặp pricing bump (79k→99k / 199k→299k)**
Grandfather **6 tháng**: existing subscriber giữ giá cũ đến 2026-11-11. Sau đó renew theo giá mới. Email + in-app notice ít nhất 30 ngày trước. Nếu user push back: option giảm giá 50% trong 3 tháng tiếp + sau đó full price. Xem §5.

**2.2.4. Family downgrade về Pro — 5 member còn lại**
- `family_accounts.status='downgraded'`. Owner giữ Pro tier.
- 5 user records (co-parent + 4 child) **không delete** — profiles persist.
- Funding sources của 5 user: **stop ingestion mới** (worker skip nếu FS owner thuộc downgraded family và không phải Pro owner).
- Historical data đã ingested: **read-only visible trong dashboard owner** (vì owner đã trả tiền cho data đó). Owner thấy tab "Archived family data — view only".
- 5 member tự login: thấy banner "Family này đã downgrade. Data của bạn read-only. Mua Pro riêng để tiếp tục."
- Re-upgrade Family trong **90 ngày** → resume sync seamless, không phải re-invite. Sau 90 ngày → re-invite required (member có thể đã linked sang family khác).

**2.2.5. Child seat allocated bị remove → slot free**
4 child seats là pool, remove 1 → free 1 slot. Có thể invite child mới ngay. Lịch sử child cũ vẫn read-only trong dashboard owner (treated như 2.2.4 case per-member).

**2.2.6. Co-parent dispute (vợ chồng ly thân)**
Out of scope cho v1. Workaround: owner remove co-parent → co-parent lose access. Phase 2 sẽ có "family fork" để split funding sources sang 2 family riêng.

**2.2.7. Funding source confusion — child link nhầm FS của parent**
F08 canonical identity `(user_id, kind, bank, last4)`. Vì child có `user_id` riêng, FS của child là entry riêng dù trùng số cuối với parent. Tuy nhiên tránh tình trạng child link FS thật sự thuộc parent: lúc invite child, bot warning "Chỉ link tài khoản/ví đứng tên con. Không link thẻ chính của bố mẹ — dùng /family share-fs thay thế (Phase 2)."

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
  [Start 14-day trial]  [Pay 169k now]  [Annual 1.720k save 15%]
```

### 3.2. Invite flow

Owner gõ `/family` → menu:
```
👨‍👩‍👧‍👦 Family — Tien (owner)
Members (1/6):
  • Tien (you, parent)
  
  [+ Invite parent]   [+ Invite child]   [Manage budgets]
```

Invite parent flow:
```
Nhập email/SĐT co-parent:
> vo@example.com
✓ Đã gửi invite. Link sẽ hết hạn sau 7 ngày.
```

Invite child flow (extra friction để xác nhận tuổi):
```
Nhập email/SĐT con:
> +84901234567

Tuổi con (13-17)?
  [13]  [14]  [15]  [16]  [17]

✓ Đã gửi invite. Yêu cầu con accept trong 7 ngày.
```

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

Khi tx của child push spend tháng vượt ngưỡng 80%:
```
🔔 Alert
Long vừa chi 120k tại "GongCha Đồng Khởi" (ăn uống).
Tháng này: 405k / 500k budget ăn uống (81%).
Còn 95k cho 19 ngày.

[View detail]  [Adjust budget]
```

Khi vượt 100%:
```
🚨 Vượt ngân sách
Long: 510k / 500k budget ăn uống (102%).
Tháng này còn 18 ngày.

[Tăng budget]  [Nói chuyện với Long]
```

> **Copy guidance:** "Nói chuyện với Long" → mở quick chat shortcut (Phase 2). v1 chỉ là CTA placeholder gọi flow notify child.

---

## 4. Domain Model

### 4.1. New tables

**`family_accounts`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| owner_user_id | int | FK → users(id). 1 user = 1 owner role tại 1 thời điểm |
| name | string(64) | Default `"{owner_name}'s family"`, user edit được |
| status | enum | `active` / `trialing` / `downgraded` / `cancelled` |
| trial_ends_at | timestamptz? | NULL nếu không trial |
| created_at | timestamptz | |
| downgraded_at | timestamptz? | Set khi 2.2.4 trigger |

**`family_members`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| family_id | int | FK → family_accounts(id) |
| user_id | int | FK → users(id) |
| role | enum | `parent` / `child` |
| invited_by | int | FK → users(id) |
| joined_at | timestamptz | |
| removed_at | timestamptz? | Soft delete |
| child_age_at_invite | int? | 13-17, NULL nếu role=parent |

Unique constraint: `(family_id, user_id) WHERE removed_at IS NULL`.

**`family_budgets`**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| family_id | int | FK |
| user_id | int | FK (member bị áp budget — role=child thường) |
| category_id | int? | NULL = tổng. Else FK → categories |
| amount_cents | bigint | Số tiền (VND, no decimal → 500k = 50000000) |
| period | enum | `monthly` (v1 chỉ support monthly) |
| created_at | timestamptz | |
| updated_at | timestamptz | |

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
| token_hash | string(64) | sha256 của token, plaintext token chỉ trong link |
| expires_at | timestamptz | created_at + 7d |
| accepted_at | timestamptz? | |
| accepted_by_user_id | int? | FK → users(id) |

### 4.2. F08 extension

`funding_sources` thêm:
- `owner_user_id` (đã có sẵn — chính là `user_id`)
- *(không cần `family_id` ở FS level — parent dashboard query qua join `family_members.user_id = funding_sources.user_id`)*

### 4.3. Permission resolver pseudo-code

```python
def can_view_user_data(viewer: User, target: User) -> bool:
    if viewer.id == target.id:
        return True
    # Same family + viewer is parent?
    fam = get_family_membership(viewer.id)
    if not fam or fam.role != "parent":
        return False
    return is_family_member(fam.family_id, target.id)

def can_set_budget(viewer: User, target: User) -> bool:
    # Both co-parents can set budgets for any child
    return (
        can_view_user_data(viewer, target)
        and get_role(viewer) == "parent"
        and get_role(target) == "child"
    )
```

---

## 5. Pricing & Migration

### 5.1. Target pricing post-launch

| Tier | Current (VN) | Target (VN, post Family launch) | Change |
|------|--------------|--------------------------------|--------|
| Free | 0 | 0 | — |
| Pro | 79k | **99k** | +25% |
| Family | — | **169k** 🆕 | new |
| Business | 199k | **299k** | +50% |

Annual (15% off):
- Pro 1.010k/năm
- Family 1.720k/năm
- Business 3.050k/năm

> **Tại sao bump Pro/Business?** Pricing ladder 79/199 quá hẹp để Family (169k đề xuất) có room. Mới: 99/169/299 giữ ratio 1:1.7:3, ladder rõ. Business bump 50% phản ánh giá trị thực (multi-channel + email parsing + Personal/Business split + Google Sheets sync — undercharge ở 199k).

### 5.2. Grandfathering existing subscribers

- **Subscribers active tại ngày T-30 (T = launch day):** giữ giá cũ trong **6 tháng** (Pro 79k, Business 199k).
- **Email + in-app notice** 30 ngày trước launch + 30 ngày trước renewal mới.
- Sau 6 tháng: renew theo giá mới. Nếu cancel → giữ access đến hết kỳ đã trả.
- **Push-back option:** subscriber phản hồi không hài lòng → offer 50% off 3 tháng tiếp, sau đó full price. Track qua support flag, max 1 lần/user.

### 5.3. Annual discount với Family

15% off (cùng tỷ lệ Pro/Business hiện tại). Cân nhắc bump lên 20% cho Family annual để incentivize stickiness (family setup tốn effort → annual lock-in hợp lý). Open question §7.

---

## 6. Cut / Out of scope v1 (Phase 2 backlog)

| Feature | Lý do cut khỏi v1 |
|---------|-------------------|
| Child-side app/view riêng | Tăng scope đáng kể (separate UX track). v1 child chỉ có view "spending tháng này" qua bot command, không có gamification. |
| Allowance automation (tag chuyển tiền định kỳ) | Cần phân biệt giữa allowance vs payment cho child — pattern detection phức tạp. Phase 2 sau khi có data thực. |
| Approve-before-spend | Latency webhook + pháp lý phức tạp. Không phải killer feature cho VN context. |
| Family <13 (managed profile) | Tránh COPPA-like compliance. v1 scope rõ 13-17. |
| Co-parent shared billing | v1: 1 owner trả. Phase 2 có thể support split. |
| Family fork (khi co-parent ly thân) | Edge case, low frequency. Phase 2. |
| `/family share-fs` (thẻ phụ link cùng FS với parent) | Phase 2 — cần design data model "shared funding source ownership". |
| Quick chat shortcut parent ↔ child trong bot | Phase 2 polish. v1 alert chỉ notify, không có in-bot chat. |
| Global market track | Phase 2+. Cần Plaid family-account API equivalent. |

---

## 7. Open Questions

1. **Family annual discount: 15% giống Pro/Business, hay 20% để incentivize stickiness?** Recommend 20% vì family setup là switching cost cao → annual lock-in xứng đáng. Cần lock trước khi update F06.
2. **Pricing bump rollout date** — sau Wave 0 complete (Q3 2026), hay sớm hơn? Liên quan tới Wave 0 priority (xem `project_wave0_gap_decisions.md` memory).
3. **Phase 2 priority** giữa: child-side app vs allowance automation vs share-fs. Cần customer interview với 5-7 parent VN trước khi commit.
4. **Trial duration cho Family — confirm 14 ngày, không bump lên 30?** Decision earlier: 14 ngày. Re-confirm sau pilot.
5. **Marketing positioning** — "dạy con xài tiền có trách nhiệm" có đủ mạnh ở VN không? Cần test với landing page A/B trước launch.

---

## 8. Acceptance Criteria (v1 done = check all)

- [ ] User trên Pro có thể upgrade lên Family qua `/upgrade` flow, 14-day trial trigger nếu chưa dùng.
- [ ] Owner invite được 1 co-parent + tối đa 4 child qua email/SĐT, invite link hết hạn 7 ngày.
- [ ] Co-parent có quyền identical với owner trừ billing actions (transfer/cancel).
- [ ] Funding sources của child auto-link với `user_id` của child, parent dashboard hiển thị aggregate.
- [ ] Budget per child × category settable, alert fire ở ngưỡng 80% và 100%.
- [ ] `/family dashboard` hiển thị tổng hợp đúng cho cả 6 member.
- [ ] Downgrade Family → Pro: 5 member còn lại profile preserved, FS stop ingest, historical read-only trong dashboard owner.
- [ ] Re-upgrade trong 90 ngày: resume seamless.
- [ ] Existing Pro/Business subscribers giữ giá cũ trong 6 tháng sau launch.
- [ ] Notice email + in-app gửi tối thiểu 30 ngày trước price change.
- [ ] Tất cả user-facing copy đi qua i18n layer, VN locale complete.

---

## 9. Changelog

| Version | Date | Notes |
|---------|------|-------|
| v1.0.0 | 2026-05-11 | Initial draft từ Family Plan brainstorm session. Locked: pricing 169k, seat 2P+4C, role parent/child, child profile 13-17, invite via email/phone + accept, downgrade behavior (profile retained + read-only historical), grandfather 6 months. |
