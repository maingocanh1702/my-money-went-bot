# Feature: Pricing, Tier Limits & Trial (F06)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 3 (Tuần 5)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [BRD-vi v3.1.0 §5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md)

---

## 1. Mô tả

Enforce tier-based feature gating + 3-tier pricing (Free / Pro $4 / Business $9) với annual discount 20%. 14-day Pro trial cho new user. Upgrade trigger logic max 1 message/tuần/user.

**Pricing:**

| Plan | Monthly | Annual (20% off) |
|------|---------|------------------|
| Free | $0 | $0 |
| Pro | $4/mo | $38.40/yr |
| Business | $9/mo | $86.40/yr |

**VN Pricing:** Pro 79k VND/mo, Business 199k VND/mo.

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
- `plan` VARCHAR(16) — 'free'/'pro'/'business'
- `trial_ends_at` TIMESTAMPTZ
- `plan_expires_at` TIMESTAMPTZ
- `plan_grace_until` TIMESTAMPTZ
- `billing_period` VARCHAR(8) — 'monthly'/'annual'

**Tier Limits Matrix:**

| Limit | Free | Pro | Business |
|-------|------|-----|----------|
| Tx/tháng | 45 | ∞ | ∞ |
| Bank accounts | 1 | 3 | 5 |
| History | 30 ngày | ∞ | ∞ |
| Categories | 5 | 20 | ∞ |
| Email sources | 1 | 3 | ∞ |

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
- [ ] Annual plan 20% off hiển thị đúng
- [ ] Grace period 7 ngày hoạt động
- [ ] Pro/Business features gated correctly

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.6 |
| v1.0.1 | 2026-05-08 | **i18n note:** Upgrade prompts, plan display, trial messages served via `t(user.locale, key)`. |
