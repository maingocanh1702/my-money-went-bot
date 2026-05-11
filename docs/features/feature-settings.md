# Feature: Settings — /settings (F07)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.7](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [Feature: i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md)

---

## 1. Mô tả

User quản lý account settings qua `/settings`: xem/regenerate webhook URL, xem inbound email, đổi timezone, bật/tắt daily recap, xem plan info + upgrade.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | `/settings` | Hiện tổng quan settings |
| 2 | User | Regenerate webhook URL | URL mới, cũ invalidate ngay |
| 3 | User | Xem inbound email | Hiện `u{id}@in.mymoneywent.com` |
| 4 | User | Đổi timezone | Recalculate scheduled jobs |
| 5 | User | Tắt daily recap | Update scheduled_jobs.enabled |
| 6 | User | Xem plan info | Plan + trial status + upgrade option |
| 7 | User | Bấm Upgrade từ settings | Redirect tới `/upgrade` flow |
| 8 | User | Xem bank connections | List các bank đã kết nối |
| 9 | User | Đổi ngôn ngữ | Hiện 2 button [🇻🇳 Tiếng Việt] [🇬🇧 English] → update locale |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Regenerate URL → SePay cũ gửi webhook | URL cũ 404, user cần update SePay |
| 2 | Cross-Feature | Đổi timezone → recap đã schedule | Cancel old job, create new |
| 3 | Data Integrity | Timezone invalid (e.g. "ABC") | Reject + list valid timezones |
| 4 | Cross-Feature | Toggle recap OFF → ON | Re-create scheduled job |
| 5 | Security | User xem settings user khác | WHERE user_id scope enforce |
| 6 | Data Integrity | Webhook URL chứa trong message history | Cũ invalidate, không reuse |
| 7 | Cross-Feature | Regenerate URL khi có pending payment | Pending payment không bị affect |
| 8 | Data Integrity | inbound_email khi user đã setup forwarding | Email mới → auto-generate mới, notify |
| 9 | Concurrency | 2 regenerate cùng lúc | Last write wins, UNIQUE constraint |
| 10 | Cross-Feature | Settings trên Messenger | Persistent menu "⚙️ Settings" |
| 11 | Cross-Feature | Settings trên Discord | /settings slash command |

---

## 3. Screens & States

### Settings Overview
- **Loading:** `t(locale, 'settings.loading')` — "⏳ Đang tải settings..."
- **Ready (vi):**
```
⚙️ Cài đặt

🔗 Webhook: ...{last6chars}
📧 Email: u42@in.mymoneywent.com
🌐 Timezone: Asia/Ho_Chi_Minh
🌙 Tóm tắt ngày: ✅ Bật
📋 Gói: Pro (trial, còn 5 ngày)
🌐 Ngôn ngữ: 🇻🇳 Tiếng Việt

[🔄 Regenerate URL] [🌐 Đổi timezone]
[🌙 Tắt recap]      [⬆️ Upgrade]
[🌐 Đổi ngôn ngữ]
```
- **Ready (en):**
```
⚙️ Settings

🔗 Webhook: ...{last6chars}
📧 Email: u42@in.mymoneywent.com
🌐 Timezone: Asia/Ho_Chi_Minh
🌙 Daily recap: ✅ On
📋 Plan: Pro (trial, 5 days left)
🌐 Language: 🇬🇧 English

[🔄 Regenerate URL] [🌐 Change timezone]
[🌙 Turn off recap]  [⬆️ Upgrade]
[🌐 Change language]
```
- **Error:** `t(locale, 'error.generic')`
- **Empty:** N/A (luôn có settings)

### Language Change Screen
```
🌐 Chọn ngôn ngữ / Choose language:

[🇻🇳 Tiếng Việt]  [🇬🇧 English]
```

> All text rendered via `t(user.locale, key)`. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).

---

## 4. Domain Model

**Fields trên `users` table:** `webhook_token`, `inbound_email`, `timezone`, `locale`, `daily_recap_enabled`, `plan`, `trial_ends_at`, `plan_expires_at`

**Tables:** `users`, `scheduled_jobs`, `bank_connections`

---

## 5. API Endpoints

Xử lý qua Telegram command / Discord slash command `/settings` + callback/button interaction trong `/webhook/{channel}`.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 400 | `SETTINGS_TZ_INVALID` | "Timezone không hợp lệ. Ví dụ: Asia/Ho_Chi_Minh" | Invalid timezone |
| 500 | `SETTINGS_REGEN_FAIL` | "⚠️ Không tạo được URL mới." | Token generation fail |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `settings_opened` | `/settings` | `user_id` |
| `settings_webhook_regenerated` | Regenerate URL | `user_id` |
| `settings_timezone_changed` | Đổi timezone | `user_id`, `old_tz`, `new_tz` |
| `settings_recap_toggled` | Bật/tắt recap | `user_id`, `enabled` |
| `settings_language_changed` | Đổi ngôn ngữ | `user_id`, `old_locale`, `new_locale` |

---

## 8. State Machine

```
[/settings] → [settings_view]
    ├── Regenerate URL → confirm → update → [settings_view]
    ├── Đổi timezone → [await_timezone_input] → update → [settings_view]
    ├── Toggle recap → update → [settings_view]
    ├── Đổi ngôn ngữ → [settings_lang_pick] → update locale → [settings_view] (in new locale)
    └── Upgrade → redirect /upgrade flow
```

---

## 9. Caching Strategy

- **Settings data:** Không cache (direct query, low frequency)
- **Timezone list:** Static in-memory

---

## 10. Acceptance Criteria

- [ ] Regenerate webhook URL → invalidate cũ ngay lập tức
- [ ] Timezone change → recalculate scheduled jobs
- [ ] Toggle daily recap → update scheduled_jobs
- [ ] Plan info hiển thị đúng (plan, trial, expiry)
- [ ] Webhook URL chỉ hiện last 6 chars (security)
- [ ] Đổi ngôn ngữ: hiện 2 button → update `users.locale` → refresh settings trong locale mới
- [ ] All settings text rendered via `t(user.locale, key)`

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.7 |
| v1.1.0 | 2026-05-08 | **i18n language change:** (1) Thêm đổi ngôn ngữ option vào settings view + state machine. (2) Language row hiện trong settings overview. (3) Thêm `settings_language_changed` analytics event. (4) All text rendered via `t(user.locale, key)`. (5) `locale` thêm vào domain model fields. |
