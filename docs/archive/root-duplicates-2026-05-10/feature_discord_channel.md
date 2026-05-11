# Feature: Multi-channel — Discord

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Phase:** Phase 2-3 (build song song Telegram, cả VN lẫn Global market)
> **Tham chiếu:** [BRD-vi v3.1.0 §1.6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [Feature: Messenger](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_messenger_channel.md) · [Feature: i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_i18n.md) · [TDD v1.8.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)

---

## 1. Mô tả

Thêm **Discord** làm kênh thứ 3 (bên cạnh Telegram + Messenger). Bot hoạt động qua **DM (Direct Message)** — user `/start` trong DM với bot → onboarding. Sử dụng **slash commands** + **button components** (Action Rows) + **rich embeds** cho report formatting. Feature flag `ENABLE_DISCORD_CHANNEL`.

**Key decisions:**
- DM-first (không phải server channel) — private financial data
- Slash commands (native Discord UX, không text commands)
- Rich Embeds cho reports (màu, fields, progress format đẹp hơn plain text)
- Global + VN market cùng dùng Discord channel
- Single-channel per user (chọn 1 lúc onboarding — Telegram/Discord/Messenger)
- Channel adapter pattern giống Messenger — extend `BaseSender`

**Tại sao Discord?**
- Bot API mature + slash commands native, không cần approval process (khác Messenger/Meta)
- VN: Gaming/MMO/tech/dropshipper community active trên Discord — overlap lớn với Hùng+ persona
- Global: Discord phổ biến trong dev/freelancer segment — overlap với Minh/Linh persona
- Multi-platform giảm SPOF risk (Telegram down → Discord vẫn hoạt động)

> **i18n:** Discord adapter passes `user.locale` to `t()` for all messages. Auto-detect locale from Discord user settings. Xem [feature_i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_i18n.md).

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | DM bot → `/start` | Tạo account `channel_type='discord'` + language select |
| 2 | User | `/start` trong server channel | Bot reply ephemeral "Vui lòng DM tôi để bắt đầu" |
| 3 | User | Chọn Path A/B/C (button components) | Onboarding flow giống Telegram |
| 4 | User | Giao dịch đến → category picker | Button components 5×5 grid (max 25 buttons) |
| 5 | User | `/status` | Rich Embed với progress bars, color-coded sections |
| 6 | User | `/today` | Embed với daily spending summary |
| 7 | User | `/manage` | Embed + buttons cho category CRUD |
| 8 | User | `/settings` | Embed + buttons cho settings (timezone, recap, language) |
| 9 | User | `/upgrade` | Embed + VietQR image attachment + ref code |
| 10 | User | `/help` | Embed với command list |
| 11 | System | Daily recap 23:00 | DM message (no window restriction như Messenger) |
| 12 | User | `/export` (Pro+) | File attachment (.csv) trong DM |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Cross-Feature | Category list >25 (max buttons) | Paginate: buttons "◀️ Prev" "▶️ Next" + page indicator |
| 2 | Data Integrity | User block DM từ bot | Error → mark `invalid_channel` |
| 3 | Security | Interaction signature verify fail | 401 Unauthorized |
| 4 | Cross-Feature | `/start` trong server (không phải DM) | Ephemeral message "DM bot để đăng ký" |
| 5 | Cross-Feature | Bot chưa được add vào DM | Hướng dẫn invite link |
| 6 | Data Integrity | Interaction timeout (>3s response) | Defer interaction → "Bot đang xử lý..." → followup |
| 7 | Cross-Feature | Rich Embed char limit (6000 total) | Split thành multiple embeds nếu report dài |
| 8 | Cross-Feature | VietQR image delivery | File attachment trong DM message |
| 9 | Security | Discord user ID collision với Telegram/Messenger | Validate cặp (channel_type, channel_user_id) |
| 10 | Cross-Feature | Feature flag OFF | Slash commands không đăng ký |
| 11 | Data Integrity | User chưa share server nào với bot | DM vẫn hoạt động (Discord cho phép DM khi user đã interact) |
| 12 | Cross-Feature | Rate limit (100 DM / 2h initial) | Queue + backoff. Request rate limit increase nếu cần |
| 13 | Concurrency | Multiple interactions cùng lúc | Discord dedup qua interaction ID |
| 14 | Cross-Feature | Markdown format khác Telegram | Discord Markdown (bold, italic, code block) — gần giống nhưng có khác biệt nhỏ |

---

## 3. Screens & States

### Discord Onboarding (DM)

- **Loading:** Defer interaction → "⏳ Bot đang tạo tài khoản..." (ephemeral)
- **Ready (vi):**
```
🌐 Ngôn ngữ đã được nhận diện:
🇻🇳 Tiếng Việt

[✅ Tiếng Việt]  [🇬🇧 English]
```
→ after language confirm:
```
Embed: 
  Title: 👋 Chào mừng bạn đến với MyMoneyWent!
  Description: Bot sẽ tự động track chi tiêu qua chuyển khoản ngân hàng.
               🎁 Bạn có 14 ngày dùng thử Pro miễn phí!
  Color: #5865F2 (Discord Blurple)

[⚡ SePay Quick]  [🔧 SePay Wizard]  [📧 Email Forwarding]
```
- **Error:** Embed với color red `#ED4245` + error message
- **Empty:** N/A

### /status — Rich Embed

```
Embed:
  Title: 📊 Tracking — 2026-05
  Color: #5865F2
  Fields:
    NGÂN SÁCH:
    ✅ Chi tiêu hàng ngày  ████████░░ 80%  800k / 1tr · còn 200k
    🟡 Tiết kiệm          ██████░░░░ 60%  600k / 1tr · còn 400k
    
    THEO DÕI:
    📊 Clothes         đã tiêu 350k tháng này
    
    INCOME:
    💚 Saving          nhận 5,000k tháng này
  Footer: Tổng budget: 1.4tr / 2tr (70%) | Tổng tracking: 470k
```

### /manage — Category Buttons

```
Embed:
  Title: 📂 Quản lý danh mục
  Description: Chọn danh mục để sửa/xóa:
  
[🛒 Chi tiêu hàng ngày (80%)]
[🏦 Tiết kiệm (60%)]
[📱 Đăng ký dịch vụ]
[➕ Tạo mới]
```

### Category Picker (transaction)

```
Embed:
  Title: 💰 Giao dịch mới
  Description: -150,000đ từ TCB xxxxxx1234
  Color: #ED4245 (red = chi)

[🛒 Chi tiêu] [🏦 Tiết kiệm] [📱 Đăng ký]
[📊 Clothes]  [➕ Tạo mới]   [⏭️ Bỏ qua]
```

### UX Parity Matrix

| Aspect | Telegram | Discord | Messenger |
|--------|----------|---------|-----------|
| Entry point | `/start` typed | `/start` slash command (DM) | "Get Started" button |
| Commands | Slash + text | **Slash commands only** | Persistent menu |
| Buttons | Inline keyboard 2D | Action Rows (5×5 = max 25) | Quick replies (max 13) |
| Button capacity | Unlimited rows | **25 buttons max** (5 rows × 5) | 13 max |
| Formatting | Markdown | **Rich Embeds** + Discord Markdown | Plain text + emoji |
| Edit message | editMessageText | Edit interaction response | Send new + delete old |
| File send | sendDocument | File attachment | attachment.file |
| Image send | sendPhoto | Embed image / File attachment | attachment.image |
| Daily recap | sendMessage anytime | **DM anytime** (no window) | MESSAGE_TAG ngoài 24h |
| Rate limit | ~30 msg/s | **50 req/s global**, 100 DM/2h initial | 200 calls/hr per user |
| Approval | None (instant) | **None** (instant — no app review) | Meta App Review (3-14d) |
| Response timeout | None | **3s acknowledge** (defer nếu lâu) | None |

---

## 4. Domain Model

### Schema Changes

```sql
-- Expand channel_type CHECK constraint (TDD v1.8.0)
ALTER TABLE users DROP CONSTRAINT chk_channel_type;
ALTER TABLE users ADD CONSTRAINT chk_channel_type 
    CHECK (channel_type IN ('telegram', 'messenger', 'discord'));
```

> **channel_user_id:** Discord User ID (Snowflake — 17-19 digit integer as string). Lưu dưới dạng VARCHAR(64) như Telegram/Messenger.

### New Code Modules

| File | Responsibility |
|------|---------------|
| `services/channels/discord.py` | `DiscordSender` — extend `BaseSender` |
| `handlers/discord_interaction.py` | Verify Ed25519 signature + dispatch interactions |
| `parsers/discord_payload.py` | Normalize Discord Interaction → internal Update |
| `discord_commands.py` | Slash command registration (global commands) |

### Slash Commands Registry

| Command | Description (en) | Description (vi) |
|---------|-----------------|------------------|
| `/start` | Start tracking your finances | Bắt đầu theo dõi tài chính |
| `/status` | Monthly spending overview | Tổng quan chi tiêu tháng |
| `/today` | Today's spending | Chi tiêu hôm nay |
| `/manage` | Manage categories | Quản lý danh mục |
| `/settings` | Bot settings | Cài đặt bot |
| `/help` | Show help | Trợ giúp |
| `/upgrade` | Upgrade your plan | Nâng cấp gói |
| `/weekly` | Weekly report (Pro) | Báo cáo tuần (Pro) |
| `/report` | Monthly report (Pro) | Báo cáo tháng (Pro) |
| `/export` | Export CSV (Pro) | Xuất CSV (Pro) |

> **Slash command descriptions** dùng `user.locale` khi tương tác, nhưng command **registration** dùng English (Discord chuẩn). Localized descriptions qua `name_localizations` + `description_localizations` API field.

---

## 5. API Endpoints

| Method | Path | Source | Mô tả |
|--------|------|--------|-------|
| POST | `/webhook/discord` | Discord Interaction endpoint | Slash commands + button interactions |

> **Discord không dùng GET verify** như Messenger. Thay vào đó, mọi POST phải verify **Ed25519 signature** (header `X-Signature-Ed25519` + `X-Signature-Timestamp`).

### Environment Variables

| Var | Description |
|-----|-------------|
| `DISCORD_BOT_TOKEN` | Bot token từ Discord Developer Portal |
| `DISCORD_APPLICATION_ID` | Application ID cho slash command registration |
| `DISCORD_PUBLIC_KEY` | Ed25519 public key cho signature verify |
| `ENABLE_DISCORD_CHANNEL` | Feature flag (`true`/`false`) |

---

## 6. Error Codes

### Discord API Errors

| Discord Code | Meaning | Action |
|-------------|---------|--------|
| 50007 | Cannot send DM to user | Mark `invalid_channel` |
| 50001 | Missing access | Log + check permissions |
| 10003 | Unknown channel | Mark `invalid_channel` |
| 40060 | Interaction already acknowledged | Ignore (dedup) |
| 429 | Rate limited | Backoff per `retry_after` header |

### Application Errors

| Code | Error Code | Message (vi) | Message (en) | Trigger |
|------|-----------|--------------|--------------|---------|
| 401 | `DISCORD_SIG_INVALID` | N/A (không reply) | N/A | Signature verify fail |
| 400 | `DISCORD_NOT_DM` | "Vui lòng DM bot" | "Please DM the bot" | Command trong server channel |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `discord_signup` | `/start` DM | `discord_user_id`, `locale` |
| `discord_interaction` | Any slash command | `user_id`, `command`, `guild_id` (null = DM) |
| `discord_message_sent` | Outbound DM | `user_id`, `type` (embed/text/file) |
| `discord_error` | Send fail | `user_id`, `error_code` |
| `discord_button_click` | Button interaction | `user_id`, `custom_id`, `component_type` |

---

## 8. State Machine

Discord **share state machine** với Telegram/Messenger qua `bot_state` table. Channel adapter chỉ khác rendering layer (Embeds + Action Rows thay vì plain text + inline keyboard).

### Interaction Flow

```
[Discord POST /webhook/discord]
    → verify Ed25519 signature
    → parse interaction type:
        ├── PING (type 1) → return { "type": 1 } (ACK)
        ├── APPLICATION_COMMAND (type 2) → dispatch to handler
        │       ├── /start → handle_start(user)
        │       ├── /status → handle_status(user)
        │       └── ...
        └── MESSAGE_COMPONENT (type 3) → dispatch button callback
                ├── cat:{id} → handle_category_pick
                ├── lang:{locale} → handle_language_select
                └── settings:{action} → handle_settings
```

### Interaction Response Types

| Type | Value | Use case |
|------|-------|----------|
| PONG | 1 | Respond to PING verify |
| CHANNEL_MESSAGE_WITH_SOURCE | 4 | Immediate response |
| DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE | 5 | "Thinking..." → followup later |
| UPDATE_MESSAGE | 7 | Edit existing message (button click) |

### Defer Pattern (for >3s responses)

```python
# Step 1: Immediately return defer (within 3s)
return {"type": 5}  # DEFERRED

# Step 2: Process async, then send followup
await discord_client.edit_original_response(token, embed=result)
```

---

## 9. Caching Strategy

- **Channel adapter registry:** In-memory dict at startup
- **Slash commands:** Registered once globally (cached by Discord CDN)
- **User channel_type:** Cached per user lookup
- **Interaction tokens:** Valid 15 minutes — no caching needed

---

## 10. Acceptance Criteria

- [ ] `/start` trong DM → tạo user với `channel_type='discord'`
- [ ] `/start` trong server → ephemeral "DM bot để đăng ký"
- [ ] Language auto-detect from Discord user `locale` field
- [ ] Category picker as Action Row buttons (max 5 per row, 5 rows)
- [ ] Category list >25 → paginate with Prev/Next buttons
- [ ] `/status` as Rich Embed with progress bars + color coding
- [ ] Daily recap DM (no window restriction)
- [ ] Ed25519 signature verification on every POST
- [ ] Interaction deferred if processing >3s
- [ ] Slash commands registered globally (work in DM)
- [ ] `ENABLE_DISCORD_CHANNEL` feature flag respected
- [ ] UNIQUE(channel_type, channel_user_id) enforced
- [ ] Adapter pattern: 0 direct Discord API calls outside `services/channels/discord.py`
- [ ] VietQR image as file attachment in DM
- [ ] `/export` CSV as file attachment in DM
- [ ] UX parity: all flows work identical across Telegram/Discord/Messenger
- [ ] All messages served via `t(user.locale, key)` (vi + en)
- [ ] Error handling: DM blocked → mark `invalid_channel`

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial Discord channel feature doc. DM-first, slash commands, rich embeds, button components. Global + VN market. Extends channel adapter pattern from Messenger spec. |
