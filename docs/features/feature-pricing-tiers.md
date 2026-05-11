# Feature: Pricing, Tier Limits & Trial (F06)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft (Family addendum 2026-05-11 — pending lock)
> **Owner:** Founder (dev)
> **Phase:** Phase 3 (Tuần 5) — Family tier Phase 3+
> **Tham chiếu:** [PRD-vi §3.6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [BRD-vi §5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [feature-family-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/drafts/feature-family-plan.md) (FAM)

---

## 1. Mô tả

Enforce tier-based feature gating + **4-tier pricing** (Free / Pro / Family / Business) với annual discount 15-20%. 14-day Pro trial cho new user. Upgrade trigger logic max 1 message/tuần/user.

**Pricing (post Family launch, 2026-Q3+):**

| Plan | VN Monthly | VN Annual (15% off) | Global Monthly |
|------|-----------|---------------------|----------------|
| Free | 0 | 0 | $0 |
| Pro | **99k VND** | 1.010k/năm | $4/mo |
| **Family** 🆕 | **169k VND** | 1.724k/năm | TBD Phase 2 |
| Business | **299k VND** | 3.050k/năm | $9/mo |

> **Pricing bump 2026-05-11:** Pro 79k→99k (+25%), Business 199k→299k (+50%) ship cùng Family launch. Lý do: ladder 79/199 quá hẹp để Family (169k) có room. Ratio mới 1:1.7:3.
>
> **Grandfather:** Existing Pro/Business active tại T-30 giữ giá cũ **6 tháng**. Email + in-app notice ≥30 ngày trước renewal mới. Push-back: 50% off 3 tháng (max 1/user). Xem §2.2 #11.

**Annual exact math (không round sang "số đẹp"):**
- Pro: 99k × 12 × 0.85 = **1.010k/năm** (1009.8k làm tròn)
- Family: 169k × 12 × 0.85 = **1.724k/năm** (1723.8k — KHÔNG phải 1.720k)
- Business: 299k × 12 × 0.85 = **3.050k/năm** (3049.8k làm tròn)

> Marketing rounding (nếu có) phải document explicit.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | System | New user signup | Assign 14-day Pro trial |
| 2 | System | Day 12 trial | Reminder "Trial còn 2 ngày" |
| 3 | System | Day 14 trial | Auto-downgrade Free, data preserved |
| 4 | User | Hit 35/45 tx | Soft reminder "Đã dùng 35/45" |
| 5 | User | Hit 45 tx | Hard block "Hết quota" |
| 6 | User | `/upgrade` | Hiện plan options + payment flow |
| 7 | User | Upgrade Pro → Business | Immediate upgrade, pro-rata |
| 8 | System | Plan expires | Grace 7 ngày → auto-downgrade |
| 9 | User | Upgrade Pro → Family | Trial reset 14 ngày Family nếu chưa dùng. Setup `family_accounts`. Xem FAM §3.1. |
| 10 | User (owner) | Downgrade Family → Pro | Plan flip `family_owner` → `pro`. Family `status='downgraded'`. 5 member kia stop ingest. Xem FAM §2.2.4. |
| 11 | User (owner) | Cancel Family | Plan flip `family_owner` → `free` (hoặc Pro grace). Family `status='cancelled'`. |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | Trial + upgrade trong trial | Cancel trial, start paid plan |
| 2 | Cross-Feature | Downgrade khi có > Free limits | Data preserved, new tx blocked |
| 3 | Data Integrity | plan_expires_at NULL | Treat as Free |
| 4 | Concurrency | 2 upgrade requests cùng lúc | Idempotent, 1 pending payment |
| 5 | Cross-Feature | Free user có 5 categories → downgrade | Giữ 5, block thêm mới |
| 6 | Security | Spoof upgrade trigger | Validate user_id |
| 7 | Data Integrity | Trial end + ongoing tx | Tx đang process xong bình thường |
| 8 | Cross-Feature | Annual plan + cancel giữa chừng | No refund pro-rata (policy) |
| 9 | Data Integrity | Timezone khác ảnh hưởng monthly tx count | Count by UTC month_key |
| 10 | Cross-Feature | Business downgrade → lose P/B toggle UI | Giữ data, ẩn UI |
| 11 | Cross-Feature | Pricing bump launch — existing Pro/Business | Grandfather 6 tháng giá cũ. Notice 30 ngày trước renewal mới. Push-back 50% off 3 tháng (max 1/user). |
| 12 | Cross-Feature | Family member buy own Pro sau family downgrade | Plan flip → Pro branch. FS ingestion resume cho cá nhân. Xem FAM §4.5. |
| 13 | Data Integrity | `family_owner` plan với family status ≠ active/trialing | Entitlement service trả False — không ingest. Plan name không bypass status check. |

---

## 3. Screens & States

### Upgrade Prompt (hit limit)
```
⚠️ Đã hết 45/45 giao dịch tháng này.

[⬆️ Upgrade Pro — Unlimited]  [ℹ️ Xem chi tiết]
```

### Trial Reminder (Day 12)
```
⏰ Trial Pro còn 2 ngày.
Giữ Pro để xem report tuần?

[✨ Upgrade Pro $4/mo]  [⬇️ Về Free]
```

### Plan Info (/settings)
```
📋 Plan: Pro (trial)
⏱ Hết hạn: 19/05/2026
Transactions: 23/unlimited
Categories: 8/20
Banks: 2/3
```

---

## 4. Domain Model

**Fields trên `users` table:**
- `plan` VARCHAR(16) — `'free'` / `'pro'` / `'family_owner'` / `'business'`
- `trial_ends_at` TIMESTAMPTZ — Pro trial
- `family_trial_used_at` TIMESTAMPTZ — block Family trial reuse
- `plan_expires_at` TIMESTAMPTZ
- `plan_grace_until` TIMESTAMPTZ
- `billing_period` VARCHAR(8) — `'monthly'` / `'annual'`

> **Note:** Co-parent + child member của Family **không** dùng `plan='family_owner'`. Họ có plan riêng (thường `'free'`); entitlement của họ resolve qua active `family_members` membership (xem FAM §4.5).

**Tier Limits Matrix:**

| Limit | Free | Pro | Family (per member) | Business |
|-------|------|-----|---------------------|----------|
| Tx/tháng | 45 | ∞ | ∞ | ∞ |
| Bank accounts | 1 | 3 | 3 per member | 5 |
| History | 30 ngày | ∞ | ∞ | ∞ |
| Categories | 5 | 20 | 20 per member | ∞ |
| Email sources | 1 | 3 | 3 per member | ∞ |
| Family seats | — | — | **2 parent + 4 child (flat, no add-on)** | — |
| Multi-member dashboard | — | — | ✅ | ❌ |
| Budget limits per member/category | — | — | ✅ | — |
| Real-time budget alerts | — | — | ✅ | — |
| Personal vs Business split | — | — | — | ✅ |
| Google Sheets sync | — | — | — | ✅ |

---

## 5. API Endpoints

| Command | Mô tả |
|---------|-------|
| `/upgrade` | Hiện plan options → payment flow |
| `/settings` | Hiện plan info section |

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 403 | `TIER_TX_LIMIT` | "Hết 45 giao dịch. Upgrade Pro." | Free cap |
| 403 | `TIER_BANK_LIMIT` | "Free chỉ 1 bank. Upgrade Pro (3) / Business (5)." | Bank limit |
| 403 | `TIER_CATEGORY_LIMIT` | "Đạt giới hạn {n} danh mục." | Category limit |
| 403 | `TIER_FEATURE_PRO` | "Tính năng này cần Pro." | Free → Pro feature |
| 403 | `TIER_HISTORY_LIMIT` | "Free chỉ xem 30 ngày. Upgrade." | History limit |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `plan_trial_started` | New signup | `user_id` |
| `plan_trial_reminder` | Day 12 | `user_id` |
| `plan_trial_expired` | Day 14 downgrade | `user_id` |
| `plan_upgrade_success` | Upgrade confirmed | `user_id`, `plan`, `period` |
| `plan_downgrade_auto` | Grace period end | `user_id`, `prev_plan` |
| `tier_limit_hit` | Any limit reached | `user_id`, `limit_type` |
| `upgrade_trigger_shown` | Upgrade message shown | `user_id`, `trigger_type` |

---

## 8. State Machine

### Trial State Machine
```
[signup] → trial_active (14 days)
    ├── Day 12 → reminder
    ├── Day 14 → auto-downgrade → Free
    └── User upgrade before 14 → cancel trial → paid plan
```

### Subscription State Machine
```
[paid_active]
    ├── 3 ngày trước expiry → reminder
    ├── Expiry + no renewal → grace_period (7 days)
    │   ├── Renewal within grace → paid_active
    │   └── Grace end → auto-downgrade Free
    └── User downgrade manual → Free immediately
```

### Timeout Spec

| Variant | Timeout | Behavior |
|---------|---------|----------|
| Trial duration | 14 ngày | Auto-downgrade Free |
| Trial reminder | Day 12 | 1 message |
| Monthly renewal reminder | 3 ngày trước expiry | 1 message |
| Annual renewal reminder | 14+3+1 ngày trước | 3 messages |
| Grace period | 7 ngày sau expiry | Still Pro features |
| Upgrade trigger cooldown | 7 ngày/user | Max 1 message/tuần |

---

## 9. Caching Strategy

- **User plan status:** Cache in-process (invalidate on plan change)
- **Tier limits config:** Static in-memory (hardcoded)
- **Monthly tx count:** Cached, invalidate on INSERT

---

## 10. Acceptance Criteria

- [ ] New user → 14-day Pro trial, auto-assigned
- [ ] Day 12: reminder
- [ ] Day 14: auto-downgrade Free, data preserved
- [ ] Upgrade triggers: max 1/tuần/user
- [ ] Free tier limits enforce đúng (45 tx, 1 bank, 30d, 1 email, 5 cat)
- [ ] Annual plan 15-20% off hiển thị đúng
- [ ] Grace period 7 ngày hoạt động
- [ ] Pro/Family/Business features gated correctly
- [ ] **Family addendum:** Pro→Family upgrade flow + trial reset 14 ngày (nếu chưa dùng `family_trial_used_at`)
- [ ] **Family addendum:** `plan='family_owner'` enum value supported; co-parent + child có plan riêng (thường `'free'`)
- [ ] **Family addendum:** Pricing bump grandfather 6 tháng; notice ≥30 ngày
- [ ] **Family addendum:** Annual exact math hiển thị đúng (Pro 1.010k, Family 1.724k, Business 3.050k)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.6 |
| v1.0.1 | 2026-05-08 | **i18n note:** Upgrade prompts, plan display, trial messages served via `t(user.locale, key)`. |
| v1.1.0 | 2026-05-11 | **Family addendum:** 4-tier pricing (Free / Pro 99k / Family 169k / Business 299k). Pricing bump Pro 79→99 + Business 199→299 với grandfather 6 tháng. `plan` enum thêm `'family_owner'`. Tier Limits Matrix mở rộng cột Family. Use cases #9-#11 + edge cases #11-#13 cho Family upgrade/downgrade/cancel/grandfather/entitlement. Acceptance criteria mở rộng. Cross-ref [feature-family-plan.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/drafts/feature-family-plan.md). |
