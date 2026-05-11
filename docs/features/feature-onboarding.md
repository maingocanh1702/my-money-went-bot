# Feature: 3-Path Onboarding (F01)

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 1-4 (Tuần 1-6)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [BRD-vi v3.1.0 §4.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [Feature: i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md)

---

## 1. Mô tả

3-Path Onboarding là flow đầu tiên user trải nghiệm. User gửi `/start` → bot auto-detect ngôn ngữ → user confirm locale → chọn 1 trong 3 path kết nối ngân hàng → bot guide step-by-step → hoàn tất. Mục tiêu: **zero-config, 2-15 phút** tùy path.

> **i18n:** Language selection là bước đầu tiên của onboarding. Auto-detect từ Telegram `language_code` / Discord interaction `locale` / Messenger profile, user confirm/override. Tất cả messages sau đó sẽ serve qua `t(user.locale, key)`. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).

**3 Path:**

| Path | Target user | Thời gian |
|------|-------------|-----------|
| **A: SePay Quick Connect** | Đã có SePay | 2-5 phút |
| **B: SePay Setup Wizard** | Chưa có SePay | 10-15 phút |
| **C: Email Forwarding** | Chỉ muốn email | 5-10 phút |

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User mới | Gửi `/start` lần đầu | Tạo account + auto-detect locale + confirm language |
| 2 | User mới (vi) | Confirm đúng locale | Save locale → hiện 3 path buttons |
| 3 | User mới (en) | Override sang en | Save en → hiện 3 path buttons in English |
| 4 | User mới | Chọn Path A | Bot hiện webhook URL copyable + hướng dẫn (trong locale user) |
| 5 | User mới | Chọn Path B | Bot bắt đầu wizard 3 bước |
| 6 | User mới | Chọn Path C | Bot cấp `u{id}@in.mymoneywent.com` + guide |
| 7 | User mới | Hoàn tất → giao dịch đầu tiên đến | Category picker hiện (trong locale user) |
| 8 | User cũ | Gửi `/start` lại | Bot hiện status, KHÔNG duplicate |
| 9 | User mới | Bấm "❓ Cần hỗ trợ" / "❓ Need help" | Bot gửi hướng dẫn chi tiết |
| 10 | User mới | Bỏ ngang wizard → quay lại | Bot resume từ bước cuối |
| 11 | User Messenger | Tap "Get Started" | Auto-detect locale từ Messenger profile |
| 11b | User Discord | /start DM | Auto-detect locale từ Discord interaction |
| 12 | User mới | Chọn Path C → Gmail | Hướng dẫn cụ thể Gmail forwarding |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | `/start` gọi nhiều lần | Idempotent — `INSERT ON CONFLICT DO NOTHING` |
| 2 | Data Integrity | `webhook_token` trùng | Re-generate token, retry |
| 3 | Concurrency | 2 user `/start` đồng thời | DB UNIQUE constraints handle |
| 4 | Security | Token giống PLATFORM_TOKEN | Guard: reserved prefix `_PLT_` |
| 5 | Cross-Feature | Path A nhưng SePay chưa active | Gợi ý kiểm tra SePay config sau 10 phút |
| 6 | Cross-Feature | Path C nhưng bank không support | Fallback "unparsed" notification |
| 7 | Data Integrity | Trial đã hết + `/start` | Không reset trial |
| 8 | Security | Spam `/start` | Rate limit per telegram_id |
| 9 | Cross-Feature | Messenger khi feature flag off | Reply (trong locale) |
| 10 | Data Integrity | DB connection fail khi signup | Error message thân thiện + retry |
| 11 | Security | Telegram ID spoofing | Validate qua Bot API signature |
| 12 | Cross-Feature | User đổi username sau signup | Update field mỗi inbound |
| 13 | Data Integrity | `language_code` = NULL | Default locale 'vi' |
| 14 | Data Integrity | `language_code` = 'pt-BR' | Non-vi → detect as 'en' |

---

## 3. Screens & States

### Language Selection (NEW — bước đầu tiên)
- **Loading:** N/A
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
- **Error:** N/A
- **Empty:** N/A

> Text rendered via `t(user.locale, 'onboard.choose_lang')`. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).

### Welcome Screen
- **Loading:** `t(locale, 'onboard.creating')` — "⏳ Đang tạo tài khoản..." / "Creating account..."
- **Ready:** Welcome message + 3 path buttons + trial info (trong locale user đã chọn)
- **Error:** `t(locale, 'error.generic')`
- **Empty:** N/A (luôn có content)

### Path A — SePay Quick Connect
- **Ready:** Webhook URL copyable + hướng dẫn 3 bước

### Path B — SePay Wizard (3 steps)
- **Ready:** Mỗi step có `[✅ Đã xong]` + `[❓ Cần hỗ trợ]`

### Path C — Email Forwarding
- **Ready:** Email address + chọn provider (Gmail/Outlook/Khác)

---

## 4. Domain Model

**Tables liên quan:** `users`, `categories`, `bot_state`

**Default Categories (auto-create, bilingual):**

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

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/webhook/telegram` | Nhận Telegram update → dispatch `/start` |
| POST | `/webhook/messenger` | Nhận Messenger postback `GET_STARTED` |

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 500 | `ONBOARD_CREATE_FAIL` | "⚠️ Không tạo được tài khoản." | DB error |
| 400 | `ONBOARD_INVALID_PATH` | "❓ Vui lòng chọn lại." | Text không match |
| 429 | `ONBOARD_RATE_LIMIT` | "⏳ Đợi {sec}s." | Spam /start |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `onboard_start_success` | Tạo account mới | `user_id`, `channel_type` |
| `onboard_start_existing` | `/start` khi có account | `user_id` |
| `onboard_language_detected` | Auto-detect locale | `user_id`, `detected_locale`, `source` |
| `onboard_language_confirmed` | User confirm locale | `user_id`, `locale` |
| `onboard_language_overridden` | User override locale | `user_id`, `detected`, `selected` |
| `onboard_path_selected` | Chọn path A/B/C | `user_id`, `path` |
| `onboard_wizard_step_done` | Hoàn tất bước wizard | `user_id`, `path`, `step` |
| `onboard_help_requested` | Bấm "❓" | `user_id`, `path`, `step` |
| `onboard_completed` | Giao dịch đầu tiên | `user_id`, `path`, `duration_min`, `locale` |
| `onboard_abandoned` | Không hoàn tất 24h | `user_id`, `path`, `last_step` |

---

## 8. State Machine

```
[/start] → [language_detect] → [language_confirm]
    ├── Confirm → save locale → [onboard_welcome]
    └── Override → save other locale → [onboard_welcome]

[onboard_welcome]
    ├── Path A → [sepay_quick] → DONE
    ├── Path B → [wizard_step1] → [wizard_step2] → [wizard_step3] → DONE
    └── Path C → [email_setup] → [email_provider] → DONE
```

### Scenarios by Status

| # | Status | Scenario | Actor | Trigger | Kết quả |
|---|--------|----------|-------|---------|---------|
| L1 | language_confirm | Confirm detected | User | Bấm ✅ | Save locale → onboard_welcome |
| L2 | language_confirm | Override | User | Bấm other | Save other locale → onboard_welcome |
| L3 | language_confirm | Text input | User | Gõ text | Re-prompt buttons |
| W1 | welcome | Chọn Path A | User | Bấm button | → sepay_quick |
| W2 | welcome | Chọn Path B | User | Bấm button | → wizard_step1 |
| W3 | welcome | Chọn Path C | User | Bấm button | → email_setup |
| W4 | welcome | Text random | User | Nhập text | Re-prompt |
| WZ1 | wizard_* | Xác nhận bước | User | Bấm ✅ | → step tiếp |
| WZ2 | wizard_* | Cần hỗ trợ | User | Bấm ❓ | Guide chi tiết |
| WZ3 | wizard_* | Bỏ ngang 24h | System | Timer | Event abandoned |

---

## 9. Caching Strategy

- **Không cache** onboarding flow — mỗi request unique per user
- Default categories template: in-memory cache (3 rows, static)

---

## 10. Acceptance Criteria

- [ ] `/start` tạo user row (keyed by channel_type + channel_user_id)
- [ ] Auto-detect locale từ Telegram `language_code` / Discord `locale` / Messenger profile
- [ ] Language confirm buttons: [✅ detected] [🌐 other]
- [ ] User confirm/override → save `users.locale`
- [ ] Default categories tạo theo locale user chọn (vi: Chi tiêu hàng ngày, en: Daily Spending)
- [ ] Generate `webhook_token` (24-char URL-safe)
- [ ] Generate `inbound_email` = `u{user_id}@in.mymoneywent.com`
- [ ] Assign 14-day Pro trial
- [ ] Path A: webhook URL copyable (tất cả text trong locale user)
- [ ] Path B: wizard 3 steps (✅/❓)
- [ ] Path C: email + forwarding guide
- [ ] `/start` idempotent (không re-ask language)
- [ ] `/start` khi có account → status
- [ ] Completion rate ≥80% trong 1 session
- [ ] Median time: A ≤5', B ≥15', C ≥10'

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.1 |
| v1.1.0 | 2026-05-08 | **i18n language select:** (1) Thêm bước language_detect + language_confirm TRƯỚC path select. Auto-detect từ Telegram `language_code` / Discord interaction `locale` / Messenger profile, user confirm/override. (2) Default categories bilingual (vi/en). (3) State machine mới: `/start` → language_confirm → onboard_welcome. (4) Thêm 3 analytics events (detected/confirmed/overridden). (5) Thêm 2 edge cases (NULL/unknown language_code). |
