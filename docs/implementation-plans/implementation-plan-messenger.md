# Implementation Plan — Messenger Channel Build

> **Version:** v1.1.0
> **Ngày tạo:** 2026-05-07
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Mục đích:** Day-by-day actionable plan cho 10-day Messenger channel build trong Phase 7 Tuần 11-12. Bridge gap giữa feature-spec-messenger-channel v1.1.1 (what + why) và actual sprint execution (when + how). Equivalent role với implementation-plan-payment-vietqr-email cho VietQR work.
> **Phase liên quan:** MVP Phase 7 Tuần 11-12 (Messenger code build), sau Phase 5 (Telegram + Discord co-primary). App Review chạy parallel review window 3-14 ngày.
> **Tham chiếu:** [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) (canonical spec — what to build) · [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.7.1 §1.4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [TDD v1.8.0 §2.1 schema + §3.1 endpoints + §5.2 env vars](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) · [Impl Plan Telegram+Discord v2.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-telegram.md) (prerequisite — Phase 1-5) · [Impl Plan VietQR+Email v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) (couples ở `send_image()`) · [Decision Onboarding UI v1.0.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md) (chat-only, no web form)

---

## 1. Executive Summary

### 1.1. Scope

10 ngày dev (Tuần 12-12 Phase 7) build Messenger channel từ scratch:

- Adapter `services/channels/messenger.py` (`MessengerSender` qua Meta Send API)
- Webhook handler `handlers/messenger_webhook.py` (signature verify + payload normalize)
- Payload parser `parsers/messenger_payload.py` (Meta event → internal Update)
- Endpoint `/webhook/messenger` GET (verify) + POST (events)
- Onboarding flow Messenger (3-path identical Telegram, quick replies thay inline keyboard)
- Transaction category picker với quick replies + multi-message split (>13 buttons)
- Persistent menu setup script (5 items: Status, Today, Manage, Settings, Help)
- 24h window logic + `MESSAGE_TAG=ACCOUNT_UPDATE` cho out-of-window outbound
- Channel-specific copy module (`copy/` với 2 variant per template)
- Subscription payment Messenger adapter (couples với VietQR `send_image()`)
- Privacy policy update + Page About link
- Meta App Review submission (`pages_messaging` + `pages_messaging_subscriptions`)

### 1.2. Decisions baked in

| Decision | Choice | Source |
|---|---|---|
| Public launch timing | Code ship MVP, public access feature-flagged sau Meta App Review approve | [BRD-vi v3.1.0 §2.2 mục tiêu 4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) |
| Channel mode | Single-channel per user (chọn 1 lúc onboarding) | [Messenger spec §1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) |
| Onboarding UI | Chat-only (KHÔNG có web form) | [Decision Onboarding UI v1.0.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md) |
| FB Business setup | Founder đã có Page + Business Manager → Day 0 chỉ ~2-4h cho App config | User confirmed |
| Page name | Defer Day 0 Tuần 11 — founder decide trước khi tạo App webhook | User confirmed |
| Screencast App Review | English voiceover (reviewer global, higher approval rate). Bot UI giữ tiếng Việt reflect actual product | User confirmed |
| Adapter pattern | `services/channels/{base,telegram,discord,messenger}.py` — base ABC + channel-specific impl. Foundation từ Phase 1-2 (Telegram + Discord co-primary) | [Refactor spec v1.3.0 §2.2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) |

### 1.3. Out of scope (defer)

| Item | Defer to | Rationale |
|---|---|---|
| Zalo OA channel | Phase 2 post-launch | OA registration cost + lead time, defer until 100+ users validate need |
| WhatsApp Business API | Phase 2+ | Complex onboarding, low VN penetration |
| Cross-channel migration tool (Telegram user → Messenger) | Manual support tool only at MVP | Single-channel per user, edge case |
| Messenger group chat support | Never (or far future) | Different policy domain, not core use case |
| Web dashboard for Messenger users | Phase 9+ trigger-based | [Decision Onboarding UI §6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md) |
| Self-host Local Messenger Bot API | N/A — Meta không cho self-host như Telegram | Use Meta hosted Send API throughout |

### 1.4. Total effort + assumptions

**10 ngày dev** (5 ngày Tuần 12 + 5 ngày Tuần 13), assumes:

- Founder solo, ~6 productive hours/day
- FB Business Manager + Page existing (Day 0 ~2-4h, không phải full day)
- Privacy policy URL ready trước Day 3 (App Review submit) — **dependency: ship landing/privacy/terms TRƯỚC Tuần 11**, theo [decision-onboarding-ui-strategy §5.2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md)
- Phase 1-5 đã ship: schema multi-channel ready, `services/channels/base.py` + `TelegramSender` + `DiscordSender` live, email parser TCB/Cake done
- vietqr.io public API responsive (couples Day 6 send_image work)
- Meta App Review chạy parallel — KHÔNG block Tuần 12-12 dev (review approve có thể Phase 8+ hoặc post-launch, channel feature-flagged)

**Estimate range: 10-12 ngày** (10 nominal + 2 ngày buffer cho App Review iteration + Meta API quirks gặp lần đầu).

---

## 2. Architecture diff

Pointer to canonical [feature-spec-messenger-channel §2-§5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md). High-level:

- New webhook ingest: `/webhook/messenger` (GET verify + POST events)
- New adapter: `services/channels/messenger.py` (`MessengerSender` qua Meta Send API)
- New parser: `parsers/messenger_payload.py` (Meta event → canonical `Update`)
- Schema: `users.channel_type='messenger'` + `channel_user_id=<PSID>` + `last_user_message_at` (24h window check) — already shipped Phase 1
- Outbound: same `messenger.send(user_id, payload)` interface, dispatch to `MessengerSender` based on `users.channel_type`
- Handlers/services KHÔNG đổi — adapter pattern hide channel difference

---

## 3. Schema impact

**No DDL changes** trong scope plan này. Schema `users.channel_type`, `channel_user_id`, `last_user_message_at`, `invalid_channel`, UNIQUE pair constraint đều **đã ship Phase 1** ([TDD-vi v1.8.1 §2.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)).

**Verify Day 0:**

```sql
-- Confirm schema ready
\d users
-- Expected columns: id, channel_type, channel_user_id, chat_id (nullable), 
--                   last_user_message_at, invalid_channel, ...
-- Expected constraints: chk_channel_type, uniq_channel_user
```

---

## 4. Code Structure

### 4.1. Files mới

| File | Status | LOC est. | Coverage target |
|---|---|---|---|
| `services/channels/messenger.py` | NEW | ~250 | 85% |
| `handlers/messenger_webhook.py` | NEW | ~120 | 90% |
| `parsers/messenger_payload.py` | NEW | ~150 | 90% |
| `copy/__init__.py` (channel-specific templates) | NEW | ~100 (initial templates) | N/A |
| `scripts/setup_messenger_persistent_menu.py` | NEW | ~50 (one-shot deploy script) | N/A |
| `tests/test_messenger_*.py` (3 files) | NEW | ~400 total | — |

### 4.2. Files modify

| File | Change | LOC delta |
|---|---|---|
| `main.py` | Thêm route `/webhook/messenger` GET + POST | +30 |
| `services/messenger.py` | Channel routing đã ready Phase 2; minor: thêm `tag` field handling | +10 |
| `services/channels/base.py` | Thêm `send_image()` abstract method (couples với VietQR plan) | +5 |
| `services/channels/telegram.py` | Implement `send_image()` qua sendPhoto (couples với VietQR plan) | +20 |
| `handlers/onboarding.py` | Channel-aware path picker (Get Started postback handler thêm path) | +60 |
| `handlers/transaction.py` | Channel-aware quick_reply rendering (multi-message split >13) | +40 |
| `config.py` | Thêm 5 env vars Messenger | +10 |
| `db.py` | Helper `update_user_last_message_at()` cho 24h window tracking | +15 |

**Tổng dev volume: ~1100 LOC mới + ~200 LOC modify.**

### 4.3. Snippets — adapter base extension

```python
# services/channels/base.py — extend
class BaseSender(ABC):
    @abstractmethod
    async def send_text(self, user, text: str, reply_markup=None, tag=None) -> None: ...
    
    @abstractmethod
    async def send_image(self, user, image_url: str, caption=None, tag=None) -> None: ...
    
    @abstractmethod
    async def send_picker(self, user, prompt: str, options: list, tag=None) -> None: ...
```

```python
# services/channels/messenger.py — skeleton
class MessengerSender(BaseSender):
    BASE_URL = "https://graph.facebook.com/v19.0"
    
    def __init__(self):
        self.page_token = os.environ["FB_PAGE_ACCESS_TOKEN"]
    
    async def send_text(self, user, text, reply_markup=None, tag=None):
        body = self._build_body(user, "text", {"text": text}, tag)
        if reply_markup:
            body["message"]["quick_replies"] = self._to_quick_replies(reply_markup)
        await self._post_to_meta(body)
    
    async def send_image(self, user, image_url, caption=None, tag=None):
        # Messenger không support caption inline với attachment → 2 message
        body = self._build_body(user, "attachment", {
            "attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": False}}
        }, tag)
        await self._post_to_meta(body)
        if caption:
            await self.send_text(user, caption, tag=tag)
    
    def _build_body(self, user, msg_type, content, tag):
        body = {"recipient": {"id": user.channel_user_id}, "message": content}
        if tag:
            body["messaging_type"] = "MESSAGE_TAG"
            body["tag"] = tag
        else:
            in_window = self._is_in_24h_window(user)
            body["messaging_type"] = "RESPONSE" if in_window else "MESSAGE_TAG"
            if not in_window:
                body["tag"] = "ACCOUNT_UPDATE"  # default safe tag
        return body
    
    def _is_in_24h_window(self, user) -> bool:
        if not user.last_user_message_at:
            return False
        return (datetime.utcnow() - user.last_user_message_at).total_seconds() < 24 * 3600
    
    def _to_quick_replies(self, telegram_inline_keyboard):
        flat = [btn for row in telegram_inline_keyboard for btn in row]
        return [
            {"content_type": "text", "title": btn["text"][:20], "payload": btn["callback_data"]}
            for btn in flat[:13]
        ]
    
    async def _post_to_meta(self, body):
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.BASE_URL}/me/messages",
                params={"access_token": self.page_token},
                json=body,
                timeout=10.0,
            )
            if r.status_code != 200:
                self._handle_meta_error(r.json(), body)
            r.raise_for_status()
    
    def _handle_meta_error(self, error_json, original_body):
        code = error_json.get("error", {}).get("code")
        if code == 10:  # User blocked Page
            asyncio.create_task(db.mark_user_invalid_channel(original_body["recipient"]["id"]))
        elif code == 200:  # 24h window violation
            log.warning("24h window violation, retry with MESSAGE_TAG")
        # Add more cases as discovered
```

---

## 5. Day-by-day breakdown

### Day 0 — Founder prerequisites (~2-4h, parallel với Phase 5 cuối)

**Prerequisites:** FB Business Manager + Page existing (user confirmed).

- [ ] **Decide Page name** (15-30 phút) — Q1 trong Messenger spec §14. Suggested: `Tiền Về Nơi Đâu` (single brand với Telegram), alternatives `MyMoneyWent` hoặc Vietnamese name. Verify URL `m.me/{PageName}` available.
- [ ] **Verify privacy policy URL accessible** — `https://tienvenoidau.com/privacy` phải ship trước Day 3. Block dependency on landing/privacy/terms plan ([decision-onboarding-ui-strategy §5.2 + §8](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md)). Nếu chưa ship: block Day 3 App Review submit.
- [ ] **Create Facebook Developer App** (~30 phút) — meta business → My Apps → Create App → Type: Business
- [ ] **Add Messenger product** to App + subscribe Page (~15 phút)
- [ ] **Generate Page Access Token** (long-lived, không expire) — copy securely vào Railway env `FB_PAGE_ACCESS_TOKEN`
- [ ] **Generate App Secret** — copy vào Railway env `FB_APP_SECRET`
- [ ] **Generate `FB_VERIFY_TOKEN`** (random URL-safe string, vd `secrets.token_urlsafe(24)`) — copy vào Railway env
- [ ] **Get Page ID** → Railway env `FB_PAGE_ID`
- [ ] **Configure App webhook URL placeholder** (sẽ update lúc deploy thực tế Day 1+ với production URL hoặc ngrok URL)
- [ ] **App icon 1024×1024** prep (founder design hoặc Fiverr ~$30, lead time 1-2 ngày — make sure ready trước Day 3 App Review submit)
- [ ] Document tất cả token/ID trong founder password manager

**Output Day 0:** 5 env vars Railway populated, App ready cho code Day 1+.

### Day 1 — Adapter init + signature verify + GET endpoint (~6h)

**Goal:** `/webhook/messenger` GET verify works. Adapter skeleton tests pass.

**Morning (3h):**

- [ ] (15m) Branch `feat/messenger-channel`
- [ ] (45m) `services/channels/base.py` extend với `send_image(user, url, caption, tag)` abstract method (couples VietQR plan)
- [ ] (30m) `services/channels/messenger.py` init class skeleton, `__init__` load env vars, `_build_body` helper, `_post_to_meta` private method
- [ ] (30m) Setup test deps: `pytest-httpx` cho mock Meta Send API
- [ ] (1h) Unit test `test_messenger_sender_init.py` (env var loading, body builder shape, MESSAGE_TAG branching)

**Afternoon (3h):**

- [ ] (1.5h) `handlers/messenger_webhook.py` implement signature verify (`X-Hub-Signature-256` HMAC-SHA256 với `FB_APP_SECRET`)
- [ ] (30m) Implement GET `/webhook/messenger` cho hub.challenge verify
- [ ] (1h) Unit test signature verify (4 cases: valid, invalid hash, missing header, wrong format) + GET endpoint with valid/invalid `hub.verify_token`
- [ ] (15m) Smoke test với curl: `curl "https://api.tienvenoidau.com/webhook/messenger?hub.mode=subscribe&hub.verify_token=$TOKEN&hub.challenge=test"` → 200 returns "test"

**Output Day 1:** GET `/webhook/messenger` deploy-ready. Adapter skeleton compiles + tests green. NO outbound work yet.

**Maps to AC:** §9.3 signature verify, §9.4 adapter pattern grep.

### Day 2 — Payload parser + send_text + quick_reply (~6h)

**Goal:** Bot có thể nhận inbound message từ Meta + reply text với quick replies.

**Morning (3h):**

- [ ] (1.5h) `parsers/messenger_payload.py` implement `parse_messenger_event(payload)` returns `list[Update]`. Handle 3 event types:
    - text message (`message.text`)
    - postback (`postback.payload` — Get Started + menu items)
    - quick reply (`message.quick_reply.payload`)
- [ ] (1.5h) Unit test `test_messenger_payload_parser.py` với 12+ Meta payload fixtures (tạo trong `tests/fixtures/messenger_events/`):
    - text_simple.json, text_emoji.json, text_long.json
    - postback_get_started.json, postback_menu.json
    - quick_reply.json
    - multi_event_entry.json (2 events trong 1 webhook)
    - attachment_image.json (skip — không support inbound image MVP)
    - delivery_receipt.json (skip silent)
    - read_receipt.json (skip silent)
    - error_payload.json

**Afternoon (3h):**

- [ ] (1h) `MessengerSender.send_text()` implement với `quick_replies` conversion từ Telegram inline_keyboard format
- [ ] (1h) `_to_quick_replies()` helper:
    - Flatten 2D inline_keyboard
    - Truncate title `[:20]` chars
    - Limit 13 quick_replies
    - Multi-message split logic nếu >13: send first message với 12 + "Next →" → second message với rest
- [ ] (1h) Unit test với mock Meta API:
    - Plain text message
    - Text + 5 quick replies
    - Text + 14 quick replies → verify 2 messages + Next button
    - Text + 30 quick replies → 3 messages

**Output Day 2:** Bot có thể parse inbound + send text với quick replies. Foundation cho onboarding/transaction flows.

**Maps to AC:** §9.1 user signup creates row, §9.4 adapter pattern (no direct Meta API outside `services/channels/`).

### Day 3 — App Review submit + ngrok local + onboarding scaffolding (~6h)

**Goal:** App Review review window started (parallel 3-14 days). Local Messenger webhook test working.

**Morning (3h):**

- [ ] (45m) Setup `ngrok` (hoặc Cloudflare Tunnel) cho local webhook receive: `ngrok http 8000` → public URL
- [ ] (15m) Configure App webhook URL → ngrok URL (update khi need)
- [ ] (15m) Subscribe Page to App webhook (Meta Business Suite → Pages → Settings → Webhooks)
- [ ] (30m) Manual smoke test inbound: send "hello" tới Page → verify webhook fire → verify signature pass → log payload
- [ ] (1.5h) **Submit Meta App Review** — use case writeup (template trong §8 plan này):
    - Submission → Add Use Cases
    - Select `pages_messaging` + `pages_messaging_subscriptions`
    - Provide test user instructions (founder Telegram allowlist)
    - Provide privacy policy URL `https://tienvenoidau.com/privacy`
    - Provide terms URL `https://tienvenoidau.com/terms`
    - Upload app icon
    - Submit screencast — **DEFER tới Day 9** sau khi flow complete để demo realistic; placeholder text "screencast pending Day 9, requesting review hold"

**Afternoon (3h):**

- [ ] (30m) `handlers/onboarding.py` add channel detection — postback `GET_STARTED` → trigger onboarding flow
- [ ] (1h) Welcome message Messenger version (channel-specific copy) + idempotent user creation (`channel_type='messenger'`, `channel_user_id=<psid>`)
- [ ] (1h) 3-path quick_reply selector (`ONBOARD_PATH_A` / `_B` / `_C` postback payloads)
- [ ] (30m) Manual E2E: founder send Get Started → verify welcome + 3 path quick replies render

**Output Day 3:** App Review pending (3-14 day clock starts). Onboarding entry working. Bot user created from Messenger Get Started.

**Maps to AC:** §9.1 Messenger signup, §9.3 App Review submitted.

### Day 4 — Onboarding 3-path complete (~6h)

**Goal:** All 3 onboarding paths work end-to-end on Messenger identical với Telegram.

**Morning (3h):**

- [ ] (45m) Path A — SePay quick connect: bot reply 2 message:
    - Message 1: "🔗 Đã có SePay. Webhook URL của bạn:"
    - Message 2 (standalone): `https://api.tienvenoidau.com/hook/{user_token}` — long-press để copy
    - Insert `bank_connections` row (type='sepay')
    - Set `users.onboard_path='sepay_quick'`
- [ ] (1h) Path B — SePay setup wizard: state machine `bot_state` 3 step:
    - Step 1: "Truy cập sepay.vn → đăng ký" + quick_reply [✅ Đã đăng ký] [❓ Cần hỗ trợ]
    - Step 2: "Kết nối ngân hàng" + quick_reply
    - Step 3: "Dán webhook URL" + quick_reply
    - Persist state qua `bot_state` table channel-agnostic
- [ ] (1h) Path C — Email forwarding: bot reply 2 message:
    - Message 1: "📧 Email forwarding setup. Email riêng của bạn:"
    - Message 2 (standalone): `u{user_id}@in.tienvenoidau.com`
    - Quick replies: [📱 Gmail] [💻 Outlook] [❓ Khác]
    - Each → reply guide instructions

**Afternoon (3h):**

- [ ] (1h) Channel-specific copy templates `copy/onboarding.py` initial — refactor inline strings thành `COPY[key][channel_type]` pattern theo [Messenger spec §7.5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)
- [ ] (1h) Manual E2E test all 3 paths trên Messenger qua ngrok local
- [ ] (1h) Compare side-by-side với Telegram cùng path → verify parity AC

**Output Day 4:** Onboarding 3-path complete on Messenger. Parity với Telegram verified manually.

**Maps to AC:** §9.1 Path A/B/C onboarding, §9.4 adapter pattern, parity matrix §7.5 Messenger spec.

### Day 5 — Transaction picker + state machine + smoke E2E (~6h)

**Goal:** Mock SePay webhook → category picker render → user click → categorized in DB.

**Morning (3h):**

- [ ] (1h) `handlers/transaction.py` channel-aware quick_reply rendering:
    - Categories list from DB
    - 2D Telegram inline_keyboard converted via flatten + truncate cho Messenger
    - >13 categories → multi-message split với "Categories (1/2)" header
- [ ] (1h) State machine `await_parent` → `await_sub` → `done` integrate với Messenger postback events
- [ ] (1h) Persistent menu setup script `scripts/setup_messenger_persistent_menu.py` — 5 items: 📊 Status, 🍜 Today, ⚙️ Manage, ⚙️ Settings, ❓ Help. Run once.

**Afternoon (3h):**

- [ ] (1.5h) Manual E2E: Full flow Messenger user
    - Get Started → onboarding Path A → mock SePay webhook tx → category picker → click category → confirmation message → `/status` qua persistent menu
- [ ] (30m) Verify `last_user_message_at` updated on every inbound (check DB query)
- [ ] (1h) Smoke test Telegram parallel cùng flow → verify identical UX (parity)

**Output Day 5 / End Tuần 11:** Core Messenger flow working — onboard + transaction categorize + status. App Review review window open. Outstanding: send_image, MESSAGE_TAG, payment, copy module full, screencast.

**Maps to AC:** §9.1 transaction notification, parity §7.5.

### Day 6 — `send_image()` cho cả 2 channel + VietQR display (~6h)

**Goal:** VietQR image render đúng trên cả Telegram + Messenger.

> **Couples với** [implementation-plan-payment-vietqr-email Day 1-2](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md). Code overlap, not duplicate work.

**Morning (3h):**

- [ ] (1.5h) `services/channels/telegram.py` implement `send_image()` qua `sendPhoto` API với caption inline + Markdown parse_mode
- [ ] (30m) Unit test với mock Telegram API
- [ ] (1h) Manual smoke test: gửi VietQR URL tới Telegram cá nhân → scan với VCB app → verify pre-fill

**Afternoon (3h):**

- [ ] (1.5h) `MessengerSender.send_image()` complete — attachment.image + caption split logic (Messenger không support inline caption)
- [ ] (30m) Unit test với mock Meta Send API
- [ ] (1h) Manual smoke test Messenger: gửi VietQR URL → scan với TCB app → verify pre-fill

**Output Day 6:** `send_image()` working both channels. VietQR display functional.

**Maps to AC:** §9.1 image render parity.

### Day 7 — 24h window + MESSAGE_TAG + subscription payment Messenger (~6h)

**Goal:** Outbound subscription payment notifications work outside 24h window.

**Morning (3h):**

- [ ] (1.5h) `MessengerSender._is_in_24h_window()` complete + `_build_body` MESSAGE_TAG branching:
    - In window → `messaging_type=RESPONSE`
    - Out of window → `messaging_type=MESSAGE_TAG` + `tag=ACCOUNT_UPDATE`
    - Caller can override với explicit `tag=` field
- [ ] (1h) `db.update_user_last_message_at()` helper + integrate vào `handlers/messenger_webhook.py` (mỗi inbound update timestamp)
- [ ] (30m) Unit test 24h window logic (3 cases: never messaged, last 1h ago, last 30h ago)

**Afternoon (3h):**

- [ ] (1.5h) Subscription payment Messenger adapter (couples [VietQR plan §6.6](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md)):
    - Ref code as standalone message (long-press copy)
    - VietQR images via `send_image()`
    - All payment outbound use `tag="ACCOUNT_UPDATE"`
- [ ] (1h) E2E test: simulate user `/upgrade` → verify 5-message structure render đúng Messenger
- [ ] (30m) Edge case test: mock `last_user_message_at = NOW() - 30h` → verify outbound dùng MESSAGE_TAG

**Output Day 7:** Payment Messenger flow ready. 24h window + tag logic verified.

**Maps to AC:** §9.3 Meta compliance MESSAGE_TAG.

### Day 8 — Channel-specific copy templates module (~6h)

**Goal:** All user-facing copy có 2 variant per channel.

**Morning (3h):**

- [ ] (1h) Refactor `copy/` module structure:
    - `copy/onboarding.py` — welcome, 3-path messages
    - `copy/transaction.py` — category picker prompts, confirmations
    - `copy/reports.py` — /status, /today, daily recap
    - `copy/settings.py` — /settings menu items
    - `copy/payment.py` — /upgrade flow texts
    - `copy/__init__.py` — `t(key, channel_type, **kwargs)` lookup helper
- [ ] (2h) Migrate inline strings từ handlers tới `copy/` module — 2 variant cho mỗi key (Telegram + Messenger)

**Afternoon (3h):**

- [ ] (1h) Verify divergent copy theo [Messenger spec §7.5 UX parity matrix](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md):
    - "Bấm /help" → "Tap menu ❓ Help"
    - "Tap để copy: \`PAY-XX\`" → "Long-press tin nhắn dưới để copy:"
    - etc.
- [ ] (1h) Unit test copy lookup helper + snapshot test render mỗi flow trên 2 channel
- [ ] (1h) Manual E2E re-run all flows on cả 2 channel → verify copy native

**Output Day 8:** Copy fully migrated. UX parity AC §10.5 satisfied.

**Maps to AC:** §10.5 UX parity grep test.

### Day 9 — Privacy policy update + Page About + screencast record (~6h)

**Goal:** App Review submission package complete với screencast.

**Morning (3h):**

- [ ] (1.5h) Privacy policy update Messenger section (theo [Messenger spec §6.7](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)):
    - Add section "Facebook Messenger users" liệt kê PSID, message content, Page interaction events
    - List opt-out: user block Page → archive sau 90 ngày (canonical retention, KHÔNG phải 30/indefinite — sync TDD §6.3)
    - Link Meta Data Policy
    - Deploy update tới `https://tienvenoidau.com/privacy`
- [ ] (15m) Update Page About: paste privacy policy URL
- [ ] (15m) Update persistent menu Help item → link tới privacy
- [ ] (1h) **Record App Review screencast** (English voiceover):
    - Tool: Loom hoặc OBS
    - Script (~2-3 phút):
        1. "Hi, this is Tiền Về Nơi Đâu — a financial tracking bot for Vietnamese users on Messenger"
        2. Demo Get Started → welcome message
        3. Demo Path A onboarding (show webhook URL standalone message)
        4. Demo mock transaction notification → category picker → click → confirmation
        5. Demo persistent menu → /status
        6. Voice over: "We use ACCOUNT_UPDATE message tags for transaction notifications, daily recap, and subscription updates — all financial account state changes for the user"
    - Upload to Google Drive / Loom unlisted, get URL

**Afternoon (3h):**

- [ ] (30m) Update App Review submission with screencast URL
- [ ] (30m) Use case writeup finalize (template §8 plan này) — submit
- [ ] (1.5h) Buffer for App Review iteration nếu Meta đã response — feedback nhận sớm thường minor (vd "clarify use case 1 sentence")
- [ ] (30m) Internal QA: full E2E walkthrough cả 2 channel + admin verify analytics events fire đúng

**Output Day 9:** App Review submission complete với working bot screencast. Privacy policy public.

**Maps to AC:** §9.3 Meta App Review pass (pending Meta response).

### Day 10 — Full E2E + buffer + iteration (~6h)

**Goal:** Production-ready code, all AC satisfied except Meta App Review pending.

**Morning (3h):**

- [ ] (1h) Full E2E test matrix: 3 onboarding path × 2 channel = 6 flows. Run mỗi flow real (not mock) trên test account
- [ ] (1h) Edge case tests:
    - User block Page → bot detect error code 10 → mark `invalid_channel=true`
    - Postmark inbound parse fail → fallback notification
    - Race condition: 2 user signup cùng PSID different time → idempotent
    - Long category list (15+ categories) → multi-message split render đúng
- [ ] (1h) Performance: bot reply latency p95 < 2s (per [Messenger spec §9.5 AC](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md))

**Afternoon (3h):**

- [ ] (1h) Code review self — check grep AC §9.4:
    - 0 hit `requests.post.*graph.facebook.com` ngoài `services/channels/messenger.py`
    - 0 hit `await tg.send_*` ngoài `services/channels/telegram.py`
    - 0 hit hardcoded chat_id/PSID ngoài `users` table lookup
- [ ] (1h) Documentation: update README env vars section, add `services/channels/messenger.py` entry trong code structure
- [ ] (1h) Buffer cho App Review feedback iteration (Meta thường response 3-7 days, có thể fall trong Tuần 12)

**Output Day 10 / End Tuần 12:** Code complete, all AC except App Review pending Meta response. `ENABLE_MESSENGER_CHANNEL=false` mặc định, ready flip ON khi App Review approve.

**Maps to AC:** All §9 Messenger spec.

### Day 11+ (buffer, dùng nếu cần) — App Review iteration

If App Review reject:
- Read feedback (1h)
- Fix specific issue (use case wording, screencast clarity, privacy policy section)
- Resubmit (15m)
- Wait Meta re-review (3-7 days)

If App Review approve before Day 10:
- Day 11 = beta dogfood Messenger với founder + 1-2 trusted user
- Validate parity với Telegram

---

## 6. Acceptance Criteria → Day mapping

| AC group | Spec ref | Day satisfied |
|---|---|---|
| §9.1 Functional — signup, transaction, daily recap, path A/B/C | Messenger spec §9.1 | Day 3-5 |
| §9.2 Multi-channel data isolation | §9.2 | Day 5 (E2E test) |
| §9.3 Meta compliance — App Review, MESSAGE_TAG, signature, privacy | §9.3 | Day 1, 3, 7, 9 |
| §9.4 Adapter pattern grep | §9.4 | Day 10 (code review) |
| §9.5 Performance latency | §9.5 | Day 10 |
| §10.5 UX parity (copy templates 2 variant, no Markdown leak) | spec §7.5 + §10 | Day 8 |

---

## 7. Day 0 prerequisites checklist (founder action)

> **Critical:** Day 0 work parallel với Phase 5 cuối (~Tuần 9). Failure to complete blocks Tuần 11 Day 1.

- [ ] **Page name decided** (Q1 deferred trong spec §14)
- [ ] **Landing page + Privacy policy + Terms ship** ở `https://tienvenoidau.com/{,/privacy,/terms}` — depend on [decision-onboarding-ui-strategy §5.2 implementation](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md), **3 ngày dev separate task** trước Tuần 11
- [ ] FB Developer App created
- [ ] Page added to App, subscribe `messages` + `messaging_postbacks` events
- [ ] Page Access Token (long-lived) generated
- [ ] App Secret captured
- [ ] FB_VERIFY_TOKEN random generated
- [ ] Page ID captured
- [ ] App icon 1024×1024 designed (Fiverr lead time 1-2 days)
- [ ] Railway env vars populated:
    - `FB_PAGE_ID`
    - `FB_PAGE_ACCESS_TOKEN`
    - `FB_VERIFY_TOKEN`
    - `FB_APP_SECRET`
    - `ENABLE_MESSENGER_CHANNEL=false` (default)
- [ ] Founder Telegram ID confirmed in `ADMIN_TELEGRAM_IDS` (cho whitelist test mode trong stage 1)
- [ ] ngrok hoặc Cloudflare Tunnel account ready cho local dev (Day 3)
- [ ] Loom hoặc OBS Studio installed cho screencast (Day 9)

---

## 8. Meta App Review submission package template

### 8.1. Use case writeup (paste vào App Review form)

**For `pages_messaging`:**

> Tiền Về Nơi Đâu is a personal finance tracking bot for Vietnamese users. We connect to users' bank notification systems (via SePay webhook integration and email forwarding) to automatically log their financial transactions. When a transaction is detected, our bot sends the user a categorization prompt via Messenger so they can label the transaction (e.g., "Daily Spending", "Saving"). Users can also query their monthly summary, today's spending, and weekly reports via persistent menu commands. We do not store bank account numbers, passwords, or any sensitive credentials — only transaction amount, description, and category for tracking purposes.

**For `pages_messaging_subscriptions` (with `ACCOUNT_UPDATE` tag):**

> We need this permission to send transaction notifications and subscription updates to users outside the standard 24-hour messaging window. Specific use cases:
>
> 1. **Transaction notification** — When user's bank transfer is detected via webhook (SePay) or email parsing, we notify the user with a category prompt. Bank notifications can occur anytime (e.g., late-night purchases), often outside the 24-hour window since user's last message.
>
> 2. **Daily recap** — At 23:00 user's local timezone, we send a summary of today's spending vs daily cap. This is a financial account state update.
>
> 3. **Subscription payment status** — When user upgrades to Pro/Business plan via bank transfer, we send confirmation upon payment match (≤5 minutes via email backup, ≤60 seconds via SePay primary). We also send expiry reminders 14 days, 3 days, and 1 day before subscription end.
>
> All notifications are tagged with `ACCOUNT_UPDATE` since they reflect changes in the user's financial account state — consistent with Meta's policy for this tag.

### 8.2. Screencast script

Length: 2-3 minutes. Voiceover: English. UI: Vietnamese (reflects actual product).

```
[00:00-00:15] Intro
"Hi, this is Tiền Về Nơi Đâu — a financial tracking bot for Vietnamese users on Messenger.
Users connect their bank, and we automatically categorize transactions to help them
track spending."

[00:15-00:45] Onboarding demo
- Show m.me/{PageName} → tap Get Started
- Welcome message renders với 3 quick replies
- Tap "🔗 Đã có SePay" (Path A)
- Bot reply 2 messages: instruction + standalone webhook URL
- Voice over: "User receives a unique webhook URL for their SePay account"

[00:45-01:30] Transaction notification
- (Pre-recorded mock) bank webhook fires
- Bot sends category picker với 5 quick replies
- Voice over: "When a transaction is detected, we send this categorization prompt
  with ACCOUNT_UPDATE tag — a financial account state change"
- Tap "🛒 Daily Spending"
- Confirmation message with progress bar

[01:30-02:00] Persistent menu + report
- Tap menu icon → 5 items render
- Tap "📊 Status" → monthly summary message

[02:00-02:30] Outro
- Voice over: "All notifications are scoped to user's own data — no cross-user leakage.
  Privacy policy at tienvenoidau.com/privacy details our data handling practices."
- Show Page About link to privacy policy
```

### 8.3. Test user setup instructions

```
Test user (Meta reviewer):
1. Visit m.me/{PageName} on Messenger mobile or web
2. Tap "Get Started" — bot creates account automatically
3. Choose any onboarding path (Path C — Email forwarding is simplest, no external bank required)
4. To simulate a transaction, send the message: "test_tx_pro" to the bot
   (we have a debug command that injects a mock transaction for App Review testing only,
   gated by reviewer test account allowlist)
5. Bot will send transaction notification with category quick replies
6. Tap any category → confirmation message
7. Tap persistent menu "📊 Status" → see monthly summary

Test account allowlist: configured in our backend with reviewer's PSID.
Please share your test PSID after starting conversation, and we'll add to allowlist immediately.
```

> **Implementation note:** Add debug command `test_tx_pro` gated by `MESSENGER_REVIEW_TEST_PSID` env var (allowlist) cho App Review testing. Remove sau approve.

### 8.4. Submission checklist

- [ ] Use case writeup §8.1 pasted
- [ ] Screencast §8.2 recorded + uploaded (Loom unlisted hoặc YouTube unlisted)
- [ ] Test user instructions §8.3 pasted
- [ ] Privacy policy URL: `https://tienvenoidau.com/privacy`
- [ ] Terms URL: `https://tienvenoidau.com/terms`
- [ ] App icon 1024×1024 uploaded
- [ ] Page name set
- [ ] Page category: "App Page" hoặc "Software"
- [ ] Page About filled với privacy policy link

---

## 9. Test strategy concrete

### 9.1. Mock library + fixtures

```python
# tests/conftest.py
import pytest
import respx

@pytest.fixture
def mock_meta_api(respx_mock):
    respx_mock.post(
        "https://graph.facebook.com/v19.0/me/messages"
    ).respond(200, json={"recipient_id": "psid_123", "message_id": "mid.123"})
    return respx_mock
```

```
tests/fixtures/messenger_events/
├── text_simple.json
├── text_emoji.json
├── text_long_500_chars.json
├── postback_get_started.json
├── postback_menu_status.json
├── postback_onboard_path_a.json
├── quick_reply_category.json
├── multi_event_entry.json     # 2 events trong 1 webhook payload
├── delivery_receipt.json       # skip silent
├── read_receipt.json           # skip silent
├── attachment_image.json       # not supported MVP, skip
└── error_payload.json          # malformed

tests/fixtures/meta_send_responses/
├── success.json
├── error_10_user_blocked.json
├── error_100_invalid_psid.json
├── error_200_window_violation.json
└── error_613_rate_limit.json
```

### 9.2. Local webhook test setup

```bash
# Terminal 1: Run app locally
uvicorn main:app --reload --port 8000

# Terminal 2: Expose to internet
ngrok http 8000
# Copy https://xxxx.ngrok.io URL

# Meta Developer Console: 
# App → Messenger → Settings → Webhooks → Edit Callback URL
# URL: https://xxxx.ngrok.io/webhook/messenger
# Verify Token: $FB_VERIFY_TOKEN
# Subscribe to: messages, messaging_postbacks
```

### 9.3. Pre-App-Review test mode

Meta allows testing with developer account (founder's personal FB) + 2 test users (added via App Roles → Testers). No App Review needed for testers.

```python
# config.py
MESSENGER_REVIEW_TEST_PSID = os.environ.get("MESSENGER_REVIEW_TEST_PSID", "").split(",")

# handlers/messenger_webhook.py
async def handle_test_command(user, text):
    if user.channel_user_id in MESSENGER_REVIEW_TEST_PSID and text == "test_tx_pro":
        # Inject mock transaction for App Review testing
        ...
```

### 9.4. E2E test matrix (Day 10)

| Flow | Telegram | Messenger | Status |
|---|---|---|---|
| Signup + Path A | ✓ | ✓ | Day 5 |
| Signup + Path B | ✓ | ✓ | Day 4 |
| Signup + Path C | ✓ | ✓ | Day 4 |
| Transaction → categorize | ✓ | ✓ | Day 5 |
| Status report | ✓ | ✓ | Day 5 |
| Daily recap (mocked timezone) | ✓ | ✓ | Day 7 |
| Out-of-24h MESSAGE_TAG | N/A | ✓ | Day 7 |
| Subscription /upgrade flow | ✓ | ✓ | Day 7 |
| User block Page error 10 | N/A | ✓ | Day 10 |
| Long category list >13 | N/A | ✓ | Day 10 |

---

## 10. Risks & contingency

| # | Risk | Probability | Impact | Mitigation / contingency |
|---|---|---|---|---|
| 1 | App Review reject | Trung bình (50% common, 30% expected for tagged use cases first submit) | KHÔNG block MVP launch (decoupled qua flag). Block public Messenger access | Day 11+ buffer cho iteration. Resubmit 3-7 day cycle. Worst case: Phase 8-9 vẫn approve. Plan B: Telegram-only launch, Messenger flip ON post-launch. |
| 2 | Meta API quirks lần đầu gặp | Cao | Dev slow xuống | Day 11+ buffer 2 days. Many quirks: attachment caption (Day 6 known), MESSAGE_TAG audit (Day 7), persistent menu format (Day 5). |
| 3 | Privacy policy URL chưa ship trước Day 3 | Trung bình | Block App Review submit | Founder must ship landing/privacy/terms TRƯỚC Tuần 11 (3 ngày dev separate). Track trong impl plan landing/privacy/terms. |
| 4 | ngrok URL changes mỗi session → must re-config webhook | Cao | Annoying but minor | Use `ngrok config` với reserved subdomain ($8/mo) or Cloudflare Tunnel free named tunnel |
| 5 | Founder solo timeline pressure (10 ngày Tuần 11-11 + parallel VietQR + admin tools) | Cao | Phase 7 slip 1-2 weeks | Sequencing trong §11. VietQR plan absorb couples ở Day 6. Admin tools defer Tuần 13 hoặc post-launch nếu cần. |
| 6 | Test user PSID allowlist setup trục trặc (App Review reviewer mistakenly thinks bot reject) | Thấp | App Review delay | Document clear instructions §8.3. Founder respond fast to reviewer questions. |
| 7 | Founder English voiceover screencast quality (accent, pace) | Thấp | Reviewer misunderstand | Practice script 2-3 takes. Optional: ElevenLabs AI voice ~$5 if confidence low. |

---

## 11. Cross-doc dependencies + sequencing

### 11.1. Dependency graph

```
Phase 1 (Tuần 1-2):
  ├─ Schema multi-channel ship (channel_type, channel_user_id) ──┐
  └─ services/channels/base.py (BaseSender ABC)                  │
                                                                  ▼
Phase 2 (Tuần 3-4):
  └─ TelegramSender migrate from telegram_api.py                 │
                                                                  ▼
Phase 5 cuối (Tuần 9):
  ├─ Email parser TCB/Cake done (reuse pattern Day 4)            │
  └─ Postmark Inbound configured                                 │
                                                                  ▼
Phase 7 Tuần 11 — THIS PLAN:
  ├─ Day 0 founder prereqs (parallel với Phase 5 end)            │
  ├─ Day 1-2 adapter + payload parser + send_text                │
  ├─ Day 3 App Review submit (parallel review window 3-14d)      │
  ├─ Day 4-5 onboarding 3-path + transaction picker              │
                                                                  ▼
Phase 7 Tuần 12 — THIS PLAN + VietQR plan COUPLED:
  ├─ Day 6 send_image (couples VietQR plan Day 1-2)              │
  ├─ Day 7 24h window + payment Messenger (couples VietQR Day 3) │
  ├─ Day 8 copy templates                                         │
  ├─ Day 9 privacy + screencast + App Review iterate             │
  └─ Day 10 E2E + buffer                                          │
                                                                  ▼
Phase 7 Tuần 13 (NOT this plan):
  ├─ Admin tools commands                                         │
  ├─ Observability dashboard                                      │
  ├─ Production deploy                                             │
  └─ Buffer for App Review reject iteration                       │
                                                                  ▼
Phase 8-9: Beta + soft launch (Telegram primary, Messenger flip if approved)
```

### 11.2. Conflict với VietQR plan

[Implementation Plan VietQR+Email v1.0.0 §5](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) đặt VietQR work ở Tuần 12 với Day 1-4 breakdown. THIS plan đặt Messenger Day 6-7 cũng ở Tuần 12. **Họ couple, không double-count:**

| VietQR plan day | Messenger plan day | Couple work |
|---|---|---|
| Day 1 — VietQR generator + Telegram send_image | Day 6 — send_image both adapters | Same: Telegram send_image. Messenger plan Day 6 covers both adapters in 1 day vì `send_image` 2 channel cùng commit. |
| Day 2 — Messenger send_image + upgrade handler | (covered Day 6 above) | Merged. |
| Day 3 — Email parallel parser + handler | Tuần 13 hoặc parallel với Tuần 12 nếu founder đa task | Separate, no Messenger touch. Defer if founder tập trung Messenger Tuần 12. |
| Day 4 — Cross-source dedup E2E + payment Messenger adapter | Day 7 — payment Messenger adapter | Same work. Day 7 of THIS plan absorbs VietQR plan Day 4 payment portion. |
| Day 5 — VietQR buffer | Day 10 — Messenger buffer | Each plan has own buffer day. |

**Net realistic effort Tuần 12:**
- Day 6: send_image both adapters (compress 2 days VietQR plan Day 1-2 into 1)
- Day 7: payment Messenger + 24h window (compress VietQR Day 4 into 1)
- Day 8: copy module
- Day 9: privacy + screencast
- Day 10: E2E + buffer

VietQR plan Day 3 (email parallel parser/handler) → can ship Tuần 13 hoặc compress vào Tuần 12 nếu founder có capacity. Recommend Tuần 13.

### 11.3. What Tuần 13 looks like (not this plan, but called out)

- Email parallel handler (VietQR plan Day 3 deferred): 1 day
- Admin tools commands (BRD §8 Phase 7.d): 3-5 days
- Observability dashboard (BRD §8 Phase 7.e): 3-5 days
- Production deploy + DNS: 1-2 days
- App Review iteration if Meta rejected during Tuần 11-11: 1-3 days
- **Total: 9-16 days work for 5 days available**

This is over budget. Realistic options:
- Push timeline to 17 weeks (extend Phase 7 to Tuần 13)
- Defer admin tools / observability scope (chỉ ship critical alerts via Sentry, defer dashboard)
- Hire help

THIS plan flags issue, doesn't solve. Founder decision needed.

---

## 12. Open questions blocking dev

| # | Question | Status | Block what? | Resolve by |
|---|---|---|---|---|
| 1 | Page name | ⏸️ Defer Day 0 Tuần 11 | Day 0 task — must decide before App config | Day 0 morning |
| 2 | Landing/privacy/terms ship status | ⚠️ Depends separate plan | Day 3 App Review submit | Trước Tuần 11 |
| 3 | App icon source | ⏸️ Defer Day 0 (Fiverr lead time 1-2 days) | Day 3 App Review submit | Day 0 (start Fiverr order) |
| 4 | Tuần 13 timeline conflict resolution | ⚠️ Acknowledged §11.3, founder decision | Phase 7 commitment | Tuần 12 cuối |
| 5 | Reserved ngrok subdomain ($8/mo) hay free | ⏸️ Operational decision | Day 3 setup | Day 3 |
| 6 | Test debug command `test_tx_pro` keep post-approve hay remove | ⏸️ Defer | Code cleanup post-Phase 7 | Phase 7 |

---

## 13. Definition of Done (Tuần 12 cuối)

Day 10 end, all true:

- [ ] All 25+ Messenger spec §9 AC marked verified
- [ ] Test coverage `services/channels/messenger.py` ≥ 85%
- [ ] Test coverage `parsers/messenger_payload.py` ≥ 90%
- [ ] Grep AC §9.4 pass: 0 hit Meta API outside `services/channels/messenger.py`
- [ ] All 3 onboarding path + transaction flow + report tested manual on real Messenger account
- [ ] Privacy policy update deployed `https://tienvenoidau.com/privacy`
- [ ] Page About has privacy URL + persistent menu Help links to privacy
- [ ] App Review submission complete with screencast (Meta response pending)
- [ ] `ENABLE_MESSENGER_CHANNEL=false` flag working — verify webhook returns 200 + log "channel disabled" when flag off, public signup blocked
- [ ] Founder dogfood test 1 day — no critical bug
- [ ] Code merged to main behind feature flag
- [ ] Documentation: README env vars updated, code structure entry added

---

## 14. References

- [Feature Spec Messenger v1.1.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) — canonical what to build
- [BRD-vi v3.1.0 §2.2 mục tiêu 4 + §8 Phase 7](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) — strategic decision
- [PRD-vi v1.7.1 §1.4 dual channel](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) — product flow
- [TDD v1.8.0 §2.1 schema + §3.1 endpoints + §5.2 env vars](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md) — technical foundation
- [Implementation Plan Telegram+Discord v2.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-telegram.md) — prerequisite (Phase 1-5, 48 days)
- [Implementation Plan VietQR+Email v1.0.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) — couples Day 6-7
- [Decision Onboarding UI v1.0.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0002-onboarding-ui-strategy.md) — chat-only, no web form
- [Disaster Recovery Runbook v1.2.0 §8e Scenario J](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md) — Page suspended scenario
- [Implementation Plan 500 users v1.4.0 §C10](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-500-users-and-more.md) — channel adapter foundation
- [Meta Messenger Platform docs](https://developers.facebook.com/docs/messenger-platform/)
- [Meta Send API reference](https://developers.facebook.com/docs/messenger-platform/send-messages)
- [Meta Message Tags policy](https://developers.facebook.com/docs/messenger-platform/send-messages/message-tags)
- [Meta App Review process](https://developers.facebook.com/docs/app-review/)
- [Meta App Review use cases for Messenger](https://developers.facebook.com/docs/messenger-platform/app-review/)

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-07 | Initial implementation plan — 10-day Messenger channel build Phase 6 Tuần 10-11. Day-by-day hour-level breakdown. Day 0 prerequisites condensed (founder confirmed FB Business + Page existing). Page name + screencast English baked in. Meta App Review submission package template §8 (use case writeup + screencast script + test user instructions). Test infrastructure concrete (respx mock + 12+ payload fixtures + ngrok local). Couples §11 với VietQR plan tránh double-count effort. Definition of Done §13 covers all spec §9 AC + flag-gated launch ready. Conflict Tuần 12 timeline acknowledged §11.3 (admin tools + observability scope over budget for solo founder, founder decision needed). |
| v1.1.0 | 2026-05-09 | **Phase shift for Discord co-primary:** (1) Phase 6 → Phase 7, Tuần 10-11 → Tuần 11-12 (+1 week shift vì Discord adapter đã chiếm Phase 2 Day 18-20). (2) Prerequisite updated: `DiscordSender` đã live alongside `TelegramSender` trước khi build Messenger. (3) Adapter pattern expanded: `{base,telegram,discord,messenger}.py`. (4) TDD ref bumped v1.6.0 → v1.8.0. (5) Thêm ref Impl Plan Telegram+Discord v2.0.0. |
