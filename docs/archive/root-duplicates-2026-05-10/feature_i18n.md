# Feature: i18n — Multilingual Bot (F14)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 1-2 (foundation, integrated into all features)
> **Tham chiếu:** [TDD v1.7.0 §2.1 users.locale](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md) · [Feature: Onboarding](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_onboarding.md)

---

## 1. Mô tả

Bot hỗ trợ 2 ngôn ngữ: **Tiếng Việt** (vi) và **English** (en). Khi onboarding, bot auto-detect ngôn ngữ từ Telegram `language_code` / Discord interaction `locale` / Messenger profile, sau đó cho user confirm/override. Mọi user-facing message được serve qua i18n module `t(locale, key)`. Admin messages (`/admin_*`) hardcoded English.

**Key decisions:**
- Auto-detect + confirm (không chỉ hỏi, không chỉ auto)
- Default categories tên theo locale user chọn
- Admin = English hardcoded (single founder, no i18n overhead)

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User mới (VN Telegram) | `/start` | Auto-detect vi → "Ngôn ngữ: 🇻🇳 Tiếng Việt. Đổi?" + [✅ OK] [🇬🇧 English] |
| 2 | User mới (EN Telegram) | `/start` | Auto-detect en → "Language: 🇬🇧 English. Change?" + [✅ OK] [🇻🇳 Tiếng Việt] |
| 3 | User mới | Confirm OK | Save locale → proceed to path select (trong ngôn ngữ đã chọn) |
| 4 | User mới | Override → chọn ngôn ngữ khác | Save locale mới → proceed |
| 5 | User cũ | `/settings` → Đổi ngôn ngữ | Update locale → all messages switch |
| 6 | User Messenger | Get Started | Auto-detect từ profile → confirm |
| 7 | User mới (null lang) | `/start` | Fallback default vi → confirm |
| 8 | User mới | Gõ text thay vì bấm button | Re-prompt language select |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | `language_code` = 'vi-VN' | Normalize → 'vi' (starts with 'vi') |
| 2 | Data Integrity | `language_code` = 'pt-BR' (unknown) | Default 'en' (non-vi → en) |
| 3 | Data Integrity | `language_code` = NULL | Default 'vi' |
| 4 | Cross-Feature | User đổi locale → daily recap | Next recap fire trong ngôn ngữ mới |
| 5 | Cross-Feature | User đổi locale → existing categories | Category names KHÔNG đổi (user-created) |
| 6 | Data Integrity | Missing key trong en pack | Fallback vi |
| 7 | Cross-Feature | Admin messages | Always English, ignore user locale |
| 8 | Data Integrity | Locale value not 'vi'/'en' | CHECK constraint reject |
| 9 | Concurrency | Đổi locale cùng lúc gửi recap | Recap dùng locale lúc query user |
| 10 | Cross-Feature | Error messages mid-flow | Use locale from user object |
| 11 | Data Integrity | Format args missing | Return template raw (no crash) |
| 12 | Cross-Feature | CSV export headers | Follow user locale |

---

## 3. Screens & States

### Language Selection (onboarding — new step)

- **Loading:** N/A (instant)
- **Ready (auto-detect vi):**
```
🌐 Ngôn ngữ đã được nhận diện:
🇻🇳 Tiếng Việt

Đúng rồi, hoặc chọn ngôn ngữ khác:

[✅ Tiếng Việt]  [🇬🇧 English]
```
- **Ready (auto-detect en):**
```
🌐 Detected language:
🇬🇧 English

Confirm, or choose another language:

[✅ English]  [🇻🇳 Tiếng Việt]
```
- **Error:** N/A (no external call)
- **Empty:** N/A

### Language Change (settings)
```
🌐 Chọn ngôn ngữ / Choose language:

[🇻🇳 Tiếng Việt]  [🇬🇧 English]
```

> All text rendered via `t(user.locale, key)` — see i18n module spec below.

---

## 4. Domain Model

### Tables

| Table | Column | Type | Scope |
|-------|--------|------|-------|
| `users` | `locale` | `VARCHAR(5) NOT NULL DEFAULT 'vi'` | User language preference |

### i18n Module

```
i18n/
├── __init__.py    # t() helper, PACKS dict, fallback logic
├── vi.py          # VI = { 'key': 'value', ... }
└── en.py          # EN = { 'key': 'value', ... }
```

**Key inventory (~106 keys):**

| Prefix | Scope | Keys |
|--------|-------|------|
| `onboard.*` | Welcome, path select, wizard steps | 15 |
| `cat.*` | Category picker, confirmation, inline create | 12 |
| `manage.*` | /manage CRUD screens | 10 |
| `report.*` | /status, /today, daily recap, /weekly | 15 |
| `settings.*` | Settings view + change screens | 10 |
| `upgrade.*` | Pricing, plan display, upgrade flow | 8 |
| `payment.*` | Pending payment, QR, matched confirmation | 10 |
| `job.*` | Scheduled job messages (recap, reminder) | 6 |
| `error.*` | Generic, rate limit, pro-only, DB | 10 |
| `btn.*` | Button labels (Skip, New, Done, Help) | 10 |

### Default Categories (bilingual)

| Locale | slug | name | daily_cap |
|--------|------|------|-----------|
| vi | `daily_spending` | 🛒 Chi tiêu hàng ngày | 100,000đ |
| vi | `saving` | 🏦 Tiết kiệm | null |
| vi | `subscription` | 📱 Đăng ký dịch vụ | null |
| en | `daily_spending` | 🛒 Daily Spending | 100,000đ |
| en | `saving` | 🏦 Saving | null |
| en | `subscription` | 📱 Subscription | null |

---

## 5. API Endpoints

Không có API riêng — locale stored per user, read on every handler call. Processed via:
- Onboarding: `handle_language_select(update)` callback
- Settings: `handle_language_change(update)` callback

---

## 6. Error Codes

| Code | Error Code | Message (vi) | Message (en) | Trigger |
|------|-----------|--------------|--------------|---------|
| — | — | N/A | N/A | i18n module has no user-facing errors |

> All error messages across features are now served via `t(user.locale, 'error.*')`. See individual feature docs for error inventories.

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `i18n_language_auto_detected` | `/start` auto-detect | `user_id`, `detected_locale`, `source` (`telegram_language_code` / `discord_interaction_locale` / `messenger_profile` / `fallback`) |
| `i18n_language_confirmed` | User confirms auto-detected | `user_id`, `locale` |
| `i18n_language_overridden` | User overrides detected | `user_id`, `detected`, `selected` |
| `i18n_language_changed` | `/settings` change | `user_id`, `old_locale`, `new_locale` |

---

## 8. State Machine

```
[/start] → [language_detect] → [language_confirm]
    ├── User confirms → save locale → [onboard_welcome] (existing flow)
    └── User overrides → save locale → [onboard_welcome]
```

### Auto-detect Algorithm

```python
def detect_locale(update) -> str:
    """Auto-detect locale from channel-specific signals."""
    if channel == 'telegram':
        lang = update.effective_user.language_code  # e.g. 'vi', 'en-US', 'pt-BR'
    elif channel == 'discord':
        lang = interaction.get('locale', '')
    elif channel == 'messenger':
        lang = profile.get('locale', '')  # e.g. 'vi_VN', 'en_US'
    else:
        lang = ''
    
    if lang and lang.lower().startswith('vi'):
        return 'vi'
    return 'en' if lang else 'vi'  # non-vi → en, null → vi (default)
```

### Scenarios by Status

| # | Status | Scenario | Actor | Trigger | Kết quả |
|---|--------|----------|-------|---------|---------|
| L1 | language_confirm | Confirm detected | User | Bấm ✅ | Save locale → onboard_welcome |
| L2 | language_confirm | Override | User | Bấm other button | Save other locale → onboard_welcome |
| L3 | language_confirm | Text input | User | Gõ text | Re-prompt buttons |
| L4 | settings | Change language | User | Callback `settings:lang` | Show 2 buttons |
| L5 | settings | Pick vi/en | User | Bấm button | Update locale → refresh view |

---

## 9. Caching Strategy

- **Language packs:** In-memory dict (static, loaded once at startup)
- **User locale:** Not cached separately — read from `user` object (already loaded per request)
- **No cache invalidation needed** — locale change takes effect immediately on next message

---

## 10. Acceptance Criteria

- [ ] Auto-detect locale from Telegram `language_code`
- [ ] Auto-detect locale from Discord interaction locale
- [ ] Auto-detect locale from Messenger profile
- [ ] NULL/unknown `language_code` → default `vi`
- [ ] Non-vi languages (pt, ja, ko) → `en`
- [ ] User can confirm detected locale with 1 tap
- [ ] User can override to other locale
- [ ] Locale saved in `users.locale`
- [ ] All user-facing messages served via `t(locale, key)`
- [ ] Admin messages remain English hardcoded
- [ ] `/settings` → change language option
- [ ] Language change → immediate effect on all messages
- [ ] Default categories created in user's chosen locale
- [ ] All keys exist in both vi.py and en.py (CI test)
- [ ] `t()` fallback: missing en key → vi value
- [ ] `t()` format args: `{name}`, `{amount}` substitution works
- [ ] CSV export headers follow user locale
- [ ] Daily recap fires in user's locale

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial i18n feature doc. Auto-detect + confirm pattern. 2 language packs (vi/en). ~106 keys. |
