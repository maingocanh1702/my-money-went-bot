# Zalo Bot Research

This note summarizes how `longbkit/clisbot` supports Zalo Bot and what it would take to add a similar Zalo channel to My Money Went Bot.

Implementation plan: [ZALO_BOT_IMPLEMENTATION_PLAN.md](ZALO_BOT_IMPLEMENTATION_PLAN.md)

Sources:

- `longbkit/clisbot`: `src/channels/zalo-bot/*`
- Zalo Bot Platform docs: https://bot.zapps.me/docs
- Zalo create-bot docs: https://bot.zapps.me/docs/create-bot
- Zalo webhook docs: https://bot.zapps.me/docs/webhook

## What clisbot does

`clisbot` has two Zalo channels:

- `zalo-bot`: official Zalo Bot Platform API
- `zalo-personal`: unofficial personal Zalo Web session via QR login

For My Money Went Bot, only `zalo-bot` is appropriate. `zalo-personal` is risky for a finance-adjacent bot because it automates a personal account session and depends on unofficial behavior.

The official Zalo Bot API shape is close to Telegram:

```text
POST https://bot-api.zaloplatforms.com/bot<ZALO_BOT_TOKEN>/<method>
```

Important methods used by `clisbot`:

- `getMe`
- `getUpdates`
- `sendMessage`
- `sendPhoto`
- `sendChatAction`
- `setWebhook`
- `deleteWebhook`
- `getWebhookInfo`

`clisbot` currently uses long polling for `zalo-bot`. Their docs explicitly say webhook mode is not implemented yet. Zalo's own docs say polling and webhook are mutually exclusive, and production should use webhook to avoid missing events.

## What Zalo supports

Zalo Bot can receive:

- text messages: `message.text.received`
- image messages: `message.image.received`
- sticker messages: `message.sticker.received`
- unsupported messages: `message.unsupported.received`

Webhook requests include:

- JSON body with `ok` and `result`
- `result.event_name`
- `result.message`
- header `X-Bot-Api-Secret-Token`

Message fields that matter:

```json
{
  "from": {
    "id": "zalo-user-id",
    "display_name": "User Name",
    "is_bot": false
  },
  "chat": {
    "id": "zalo-chat-id",
    "chat_type": "PRIVATE"
  },
  "text": "Xin chào",
  "message_id": "message-id",
  "date": 1750316131602
}
```

To reply, send to `message.chat.id`:

```json
{
  "chat_id": "zalo-chat-id",
  "text": "message up to 2000 chars"
}
```

## Fit for My Money Went Bot

My Money Went Bot already has the right deployment shape for Zalo webhook:

```text
SePay webhook -> FastAPI app -> Google Sheet
Telegram webhook -> FastAPI app -> command/callback handlers
Zalo webhook -> FastAPI app -> same command handlers, if adapted
```

However, the current app is tightly coupled to Telegram:

- `telegram_api.py` is imported directly across handlers.
- UI uses Telegram inline buttons and callback queries.
- `CHAT_ID` is a Telegram chat ID and also used as the key for bot state in Google Sheet.
- Telegram can edit messages and answer callback queries; Zalo Bot appears append-only for normal message flow.

So adding Zalo is not just swapping the API URL. We need a thin channel abstraction first.

## Recommended implementation path

### Phase 1: Zalo notification-only mode

Lowest-risk first version:

- Add `ZALO_BOT_TOKEN`.
- Add `ZALO_CHAT_ID`.
- Add `ZALO_WEBHOOK_SECRET`.
- Add `zalo_api.py` with:
  - `send_text`
  - text chunking at 2000 chars
  - `set_webhook` helper
- When SePay transaction arrives, send the same notice to Telegram and optionally Zalo.
- Keep categorization buttons and commands on Telegram only.

This gives immediate value: Zalo can receive spending alerts and reports.

### Phase 2: Zalo command input

Add Zalo webhook handling:

- New endpoint: `/zalo/webhook`
- Verify header `X-Bot-Api-Secret-Token == ZALO_WEBHOOK_SECRET`
- Reject any `from.id` not equal to `ZALO_USER_ID`
- Normalize inbound message into internal text input:
  - `/today`
  - `/report`
  - `/accounts`
  - `/keywords`
  - plain text replies for existing wizards

State should use a channel-aware key, for example:

```text
telegram:<CHAT_ID>
zalo:<ZALO_USER_ID>
```

This avoids Telegram and Zalo overwriting each other's wizard state.

### Phase 3: Replace inline buttons with text fallbacks

Zalo Bot does not map cleanly to Telegram inline callbacks. For Zalo, category selection should use numbered replies:

```text
Khoản này thuộc mục nào?
1. Food
2. Transport
3. Subscription
4. Other

Reply số 1-4.
```

Internally, the Zalo channel can translate `1` into the same action that Telegram callback `p_<bucket_id>` triggers.

This needs a small UI layer:

```python
class BotChannel:
    async def send_text(...)
    async def send_options(...)
    async def edit_or_send(...)
```

Telegram implementation:

- `send_options` = inline buttons
- `edit_or_send` = edit message

Zalo implementation:

- `send_options` = numbered text list
- `edit_or_send` = send a new message

### Phase 4: Full multi-channel mode

Only do this after Phase 2/3 are stable:

- Per-channel owner IDs.
- Per-channel state.
- Configurable primary interaction channel.
- Optional fan-out notifications to multiple channels.
- Docs for Telegram-only, Zalo-only, and Telegram+Zalo setups.

## Env vars to add

For notification-only:

```env
ZALO_ENABLED=false
ZALO_BOT_TOKEN=
ZALO_CHAT_ID=
```

For webhook command input:

```env
ZALO_ENABLED=false
ZALO_BOT_TOKEN=
ZALO_USER_ID=
ZALO_CHAT_ID=
ZALO_WEBHOOK_SECRET=
```

`ZALO_USER_ID` is for sender validation. `ZALO_CHAT_ID` is where the bot sends replies. For private chat they may be the same, but keep both explicit to avoid assumptions.

## Security notes

- Use official `zalo-bot`, not unofficial `zalo-personal`.
- Require `X-Bot-Api-Secret-Token` on webhook.
- Require `from.id == ZALO_USER_ID`.
- Do not accept group messages in v1 unless a clear allowlist is added.
- Do not send sensitive details to both Telegram and Zalo unless the user explicitly enables fan-out.
- Do not ask users to paste real Zalo tokens into public chats.

## Recommendation

Start with Phase 1 plus docs. It is small, useful, and does not require rewriting all Telegram callback flows.

Then add Phase 2/3 behind `ZALO_ENABLED=true` once the project has a channel abstraction. Trying to make Zalo fully equivalent to Telegram immediately will touch most handlers because inline buttons and message editing are currently assumed everywhere.
