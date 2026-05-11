# Feature: Multi-channel — Facebook Messenger

> **Version:** v1.0.0 (refactored từ feature-spec-messenger-channel v1.1.1)
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 1-7 (foundation song song, build Tuần 11-12 — shifted +1 week for Discord co-primary in Phase 2)
> **Tham chiếu:** [Original spec](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-messenger-channel.md)

---

## 1. Mô tả

Thêm Facebook Messenger làm kênh thứ 2 song song Telegram. Code ship trong MVP nhưng public launch decoupled qua feature flag `ENABLE_MESSENGER_CHANNEL`. Channel adapter pattern cho phép thêm Zalo/WhatsApp sau. Single-channel per user (chọn 1 lúc onboarding).

**Key decisions:**
- Code bake-in MVP, launch decoupled (Meta App Review không deterministic)
- Single-channel per user
- Messenger only, Zalo defer Phase 2+

> Chi tiết đầy đủ: [Original spec (archive)](file:///Users/maingocanh/Projects/MyMoneyWent/docs/archive/feature-spec-messenger-channel.md)

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | Truy cập `m.me/FinTrackPage` | "Get Started" button → signup |
| 2 | User | Tap "Get Started" | Tạo account `channel_type='messenger'` |
| 3 | User | Giao dịch đến | Quick reply category picker (max 13 items) |
| 4 | User | Tap persistent menu "📊 Status" | Report giống /status Telegram |
| 5 | System | Daily recap 23:00 (ngoài 24h window) | MESSAGE_TAG ACCOUNT_UPDATE |
| 6 | User | `/upgrade` flow | VietQR image via attachment + standalone ref message |
| 7 | System | Match payment notification (>24h) | MESSAGE_TAG ACCOUNT_UPDATE |
| 8 | User | Path A/B/C onboarding | Quick replies thay inline keyboard |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | Category list >13 | Split multi-message "(1/2)", "(2/2)" |
| 2 | Data Integrity | User block Page | Error code 10 → mark invalid_channel |
| 3 | Security | Meta signature verify fail | 200 OK + log warning |
| 4 | Cross-Feature | No code block trên Messenger | Ref code gửi standalone message |
| 5 | Cross-Feature | Markdown leak vào Messenger | Strip markdown → plain text |
| 6 | Cross-Feature | Edit message không support | Send new + optional delete old |
| 7 | Data Integrity | Quick reply biến mất khi message mới | Resend quick replies khi re-prompt |
| 8 | Cross-Feature | VietQR image delivery | attachment.type=image + public URL |
| 9 | Security | PSID collision với telegram_id | Validate cặp (channel_type, channel_user_id) |
| 10 | Cross-Feature | Feature flag OFF | Reply "Messenger chưa mở" |

---

## 3. Screens & States

### Messenger Onboarding
- **Loading:** N/A (Meta Get Started instant)
- **Ready:** Welcome message + 3 quick replies (Path A/B/C)
- **Error:** "⚠️ Có lỗi xảy ra."
- **Empty:** N/A

### Persistent Menu (5 items max)
```
📊 Status | 🍜 Today | ⚙️ Manage | ⚙️ Settings | ❓ Help
```

### UX Parity Matrix

| Aspect | Telegram | Messenger | Discord |
|--------|----------|-----------|
| Entry point | `/start` typed | "Get Started" button | `/start` slash command (DM) |
| Commands | Slash commands | Persistent menu + text shortcut | Slash commands only |
| Buttons | Inline keyboard 2D | Quick replies flat (max 13) | Action Rows (5×5 = max 25) |
| Formatting | Markdown | Plain text + emoji | Rich Embeds + Discord Markdown |
| Edit message | editMessageText | Send new + delete old | Edit interaction response |
| Daily recap | sendMessage anytime | MESSAGE_TAG ngoài 24h | DM anytime (no window) |

---

## 4. Domain Model

```sql
-- Schema changes trên users table
ALTER TABLE users ADD COLUMN channel_type VARCHAR(16) NOT NULL;
ALTER TABLE users ADD COLUMN channel_user_id VARCHAR(64) NOT NULL;
ALTER TABLE users ADD COLUMN last_user_message_at TIMESTAMPTZ;
ALTER TABLE users ADD CONSTRAINT chk_channel_type CHECK (channel_type IN ('telegram','messenger','discord'));
ALTER TABLE users ADD CONSTRAINT uniq_channel_user UNIQUE (channel_type, channel_user_id);
```

**New code modules:**
- `services/channels/base.py` — BaseSender ABC
- `services/channels/telegram.py` — TelegramSender
- `services/channels/messenger.py` — MessengerSender
- `handlers/messenger_webhook.py` — Verify signature + dispatch
- `parsers/messenger_payload.py` — Normalize Meta event → Update

---

## 5. API Endpoints

| Method | Path | Source | Mô tả |
|--------|------|--------|-------|
| GET | `/webhook/messenger` | Meta verify | Return `hub.challenge` |
| POST | `/webhook/messenger` | Meta webhook | Messages + postbacks |

---

## 6. Error Codes

| Meta Code | Meaning | Action |
|-----------|---------|--------|
| 10 | User blocked Page | Mark invalid_channel |
| 100 | Invalid PSID | Log + mark invalid |
| 200 | 24h window violation | Add MESSAGE_TAG + retry |
| 613 | Rate limit | Backoff 1s |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `messenger_signup` | Get Started | `psid` |
| `messenger_message_sent` | Outbound | `user_id`, `messaging_type`, `tag` |
| `messenger_window_status` | Send check | `user_id`, `in_window` |
| `messenger_error` | Send fail | `user_id`, `error_code` |

---

## 8. State Machine

Messenger không có state machine riêng — share state machine với Telegram qua `bot_state` table. Channel adapter chỉ khác rendering layer.

### 24h Window Logic
```
if (now - last_user_message_at) < 24h:
    messaging_type = "RESPONSE"
else:
    messaging_type = "MESSAGE_TAG"
    tag = "ACCOUNT_UPDATE"
```

---

## 9. Caching Strategy

- **Channel adapter registry:** In-memory dict at startup
- **User channel_type:** Cached per user lookup
- **Persistent menu config:** Set 1 lần qua API, Meta caches

---

## 10. Acceptance Criteria

- [ ] Signup qua `m.me/` → row with channel_type='messenger'
- [ ] UNIQUE(channel_type, channel_user_id) enforced
- [ ] Category picker as quick replies (max 13 per message)
- [ ] Daily recap qua MESSAGE_TAG ngoài 24h
- [ ] Persistent menu 5 items
- [ ] Signature verify X-Hub-Signature-256
- [ ] Adapter pattern: grep 0 direct Meta API calls outside services/channels/
- [ ] Meta App Review pass
- [ ] Privacy policy updated
- [ ] UX parity: all flows work identical trên cả 3 channel (Telegram/Discord/Messenger)
- [ ] Copy templates: 3 variants (Telegram + Discord + Messenger)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Refactor từ feature-spec-messenger-channel v1.1.1 → 10-section |
| v1.0.1 | 2026-05-08 | **i18n note:** Messenger adapter passes `user.locale` to `t()` for all messages. Auto-detect locale from Messenger profile. |
