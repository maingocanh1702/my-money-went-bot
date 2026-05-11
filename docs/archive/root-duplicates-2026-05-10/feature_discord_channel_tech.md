# BE Tech Doc: Multi-channel — Discord

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_discord_channel.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_discord_channel.md)
> **TDD ref:** [TDD v1.8.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Adapter | `services/channels/discord.py` | `DiscordSender` — send DM, edit response, file attachment |
| Webhook | `handlers/discord_interaction.py` | Ed25519 verify, dispatch slash commands + button clicks |
| Parser | `parsers/discord_payload.py` | Normalize Discord Interaction → internal Update object |
| Commands | `discord_commands.py` | Register/update global slash commands via Discord API |
| Config | `config.py` | `DISCORD_BOT_TOKEN`, `DISCORD_APPLICATION_ID`, `DISCORD_PUBLIC_KEY`, `ENABLE_DISCORD_CHANNEL` |

---

## 2. Database Schema

### 2.1. Schema Change

```sql
-- Expand channel_type CHECK to include 'discord' (TDD v1.8.0)
ALTER TABLE users DROP CONSTRAINT chk_channel_type;
ALTER TABLE users ADD CONSTRAINT chk_channel_type 
    CHECK (channel_type IN ('telegram', 'messenger', 'discord'));
```

No new tables — Discord uses existing `users`, `bot_state`, `transactions`, `categories` tables.

### 2.2. Key Queries

```sql
-- Create Discord user
INSERT INTO users (channel_type, channel_user_id, locale, plan, trial_ends_at)
VALUES ('discord', $1, $2, 'free', NOW() + INTERVAL '14 days')
ON CONFLICT (channel_type, channel_user_id) DO NOTHING
RETURNING id;

-- Lookup by Discord user ID
SELECT * FROM users WHERE channel_type = 'discord' AND channel_user_id = $1;
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Ed25519 signature invalid | Return 401, do NOT process |
| 2 | Security | Interaction type = PING | Return `{"type": 1}` (ACK) |
| 3 | Data Integrity | Discord User ID = 17-19 digit snowflake | Store as VARCHAR(64) — fits |
| 4 | Cross-Feature | Command from server (not DM) | Return ephemeral "DM bot" |
| 5 | Data Integrity | Interaction token expires (15min) | Catch expired token error, log |
| 6 | Concurrency | Response takes >3s | Defer (type 5) → followup |
| 7 | Cross-Feature | Category list >25 items | Paginate with custom_id "cat_page:{n}" |
| 8 | Data Integrity | DM blocked by user | Discord error 50007 → mark invalid_channel |
| 9 | Cross-Feature | Rich Embed >6000 chars | Split into 2+ embeds |
| 10 | Security | Replay attack (same timestamp) | Ed25519 verify handles timestamp |
| 11 | Data Integrity | Empty interaction data | Validate required fields → 400 |
| 12 | Cross-Feature | Feature flag OFF | Don't register commands, return 404 on webhook |
| 13 | Cross-Feature | Duplicate interaction (retry from Discord) | Idempotent: check interaction_id dedup |
| 14 | Data Integrity | Discord locale field mapping | `vi` → 'vi', everything else → detect via i18n |

---

## 3. API Contract

### 3.1. Webhook Endpoint

```
POST /webhook/discord
Headers:
  X-Signature-Ed25519: {signature}
  X-Signature-Timestamp: {timestamp}
Body: Discord Interaction JSON
```

### 3.2. Signature Verification

```python
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

def verify_discord_signature(public_key: str, signature: str, timestamp: str, body: str) -> bool:
    """Verify Discord Ed25519 interaction signature."""
    try:
        vk = VerifyKey(bytes.fromhex(public_key))
        vk.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except (BadSignatureError, Exception):
        return False
```

### 3.3. DiscordSender Interface

```python
class DiscordSender(BaseSender):
    """Discord channel adapter — sends DM messages via Discord API."""
    
    async def send_text(self, user_id: str, text: str) -> dict:
        """Send plain text DM."""
        channel = await self._get_dm_channel(user_id)
        return await self._api_post(f"/channels/{channel}/messages", {
            "content": text
        })
    
    async def send_embed(self, user_id: str, embed: dict, components: list = None) -> dict:
        """Send Rich Embed DM with optional button components."""
        channel = await self._get_dm_channel(user_id)
        payload = {"embeds": [embed]}
        if components:
            payload["components"] = components
        return await self._api_post(f"/channels/{channel}/messages", payload)
    
    async def send_file(self, user_id: str, file_bytes: bytes, filename: str, content: str = None) -> dict:
        """Send file attachment in DM (CSV export, VietQR image)."""
        channel = await self._get_dm_channel(user_id)
        # multipart/form-data upload
        ...
    
    async def respond_interaction(self, interaction_id: str, interaction_token: str, 
                                   response_type: int, data: dict) -> dict:
        """Respond to a Discord Interaction (slash command or button click)."""
        return await self._api_post(
            f"/interactions/{interaction_id}/{interaction_token}/callback",
            {"type": response_type, "data": data}
        )
    
    async def edit_original(self, interaction_token: str, data: dict) -> dict:
        """Edit the original interaction response (deferred followup)."""
        return await self._api_patch(
            f"/webhooks/{self.app_id}/{interaction_token}/messages/@original",
            data
        )
    
    async def _get_dm_channel(self, user_id: str) -> str:
        """Get or create DM channel with user."""
        resp = await self._api_post("/users/@me/channels", {"recipient_id": user_id})
        return resp["id"]
```

### 3.4. Interaction Dispatch

```python
async def handle_discord_interaction(request: Request):
    """Main Discord webhook handler."""
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    
    if not verify_discord_signature(DISCORD_PUBLIC_KEY, signature, timestamp, body.decode()):
        raise HTTPException(401)
    
    data = json.loads(body)
    
    # PING — verify endpoint
    if data["type"] == 1:
        return {"type": 1}
    
    # APPLICATION_COMMAND — slash command
    if data["type"] == 2:
        command = data["data"]["name"]
        user_id = data["member"]["user"]["id"] if "member" in data else data["user"]["id"]
        
        # Check DM context
        if "guild_id" in data:
            return {"type": 4, "data": {
                "content": t(detect_locale(data), 'discord.dm_only'),
                "flags": 64  # EPHEMERAL
            }}
        
        handler = COMMAND_HANDLERS.get(command)
        return await handler(data, user_id)
    
    # MESSAGE_COMPONENT — button click
    if data["type"] == 3:
        custom_id = data["data"]["custom_id"]
        return await handle_button_click(data, custom_id)
```

### 3.5. Embed Builder Helper

```python
def build_embed(title: str, description: str, color: int = 0x5865F2, 
                fields: list = None, footer: str = None) -> dict:
    """Build Discord Rich Embed object."""
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat()
    }
    if fields:
        embed["fields"] = [
            {"name": f["name"], "value": f["value"], "inline": f.get("inline", False)}
            for f in fields
        ]
    if footer:
        embed["footer"] = {"text": footer}
    return embed

# Color constants
DISCORD_BLURPLE = 0x5865F2
DISCORD_RED = 0xED4245
DISCORD_GREEN = 0x57F287
DISCORD_YELLOW = 0xFEE75C
```

### 3.6. Button Component Builder

```python
def build_button_rows(buttons: list[dict], max_per_row: int = 5) -> list[dict]:
    """Build Action Row components from button list.
    
    Each button: {"label": "...", "custom_id": "...", "style": 1, "emoji": "..."}
    Style: 1=Primary(blurple), 2=Secondary(grey), 3=Success(green), 4=Danger(red)
    """
    rows = []
    for i in range(0, len(buttons), max_per_row):
        chunk = buttons[i:i+max_per_row]
        rows.append({
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "label": btn["label"],
                    "custom_id": btn["custom_id"],
                    "style": btn.get("style", 2),
                    "emoji": {"name": btn["emoji"]} if btn.get("emoji") else None
                }
                for btn in chunk
            ]
        })
    return rows[:5]  # Max 5 Action Rows
```

### 3.7. Slash Command Registration

```python
async def register_global_commands(bot_token: str, app_id: str):
    """Register slash commands globally (works in DM + servers)."""
    commands = [
        {
            "name": "start",
            "description": "Start tracking your finances",
            "name_localizations": {"vi": "start"},
            "description_localizations": {"vi": "Bắt đầu theo dõi tài chính"},
            "dm_permission": True,
            "contexts": [0, 1],  # GUILD + BOT_DM
        },
        {
            "name": "status",
            "description": "Monthly spending overview",
            "description_localizations": {"vi": "Tổng quan chi tiêu tháng"},
            "dm_permission": True,
            "contexts": [1],  # BOT_DM only
        },
        # ... (full list in feature doc §4)
    ]
    
    await discord_api.put(
        f"/applications/{app_id}/commands",
        json=commands,
        headers={"Authorization": f"Bot {bot_token}"}
    )
```

---

## 4. Implementation Details

### 4.1. DiscordSender vs TelegramSender vs MessengerSender

| Method | Telegram | Discord | Messenger |
|--------|----------|---------|-----------|
| `send_text()` | sendMessage | DM channel message | Send API |
| `send_buttons()` | InlineKeyboard | Action Rows (5×5) | Quick Replies (max 13) |
| `send_image()` | sendPhoto | Embed image / attachment | Attachment API |
| `send_file()` | sendDocument | File attachment | File attachment |
| `edit_message()` | editMessageText | Edit interaction response | Send new + delete |
| `delete_message()` | deleteMessage | Delete message | Delete API |

### 4.2. Locale Detection for Discord

```python
def detect_locale_from_discord(interaction: dict) -> str:
    """Detect locale from Discord interaction locale field.
    
    Discord provides 'locale' field in interaction data.
    Values: 'vi' (Vietnamese), 'en-US', 'en-GB', 'ja', 'ko', etc.
    """
    locale = interaction.get("locale", "")
    if locale.startswith("vi"):
        return "vi"
    return "en" if locale else "vi"  # non-vi → en, null → vi
```

### 4.3. Category Picker Pagination

```python
async def send_category_picker(sender: DiscordSender, user, tx, categories: list):
    """Send category picker with pagination if >25 categories."""
    page_size = 23  # 23 categories + New + Skip = 25 buttons
    total_pages = ceil(len(categories) / page_size)
    page = 0
    
    page_cats = categories[page * page_size : (page + 1) * page_size]
    
    buttons = [
        {"label": cat.name, "custom_id": f"cat:{cat.id}", "style": 2}
        for cat in page_cats
    ]
    buttons.append({"label": t(user.locale, 'btn.new_category'), "custom_id": "cat:new", "style": 3, "emoji": "➕"})
    buttons.append({"label": t(user.locale, 'btn.skip'), "custom_id": "cat:skip", "style": 4, "emoji": "⏭️"})
    
    if total_pages > 1:
        buttons.append({"label": f"▶️ ({page+1}/{total_pages})", "custom_id": f"cat_page:{page+1}", "style": 1})
    
    embed = build_embed(
        title=t(user.locale, 'cat.picker_prompt'),
        description=f"-{fmt_currency(tx.amount, user.locale)} từ {tx.bank_name}",
        color=DISCORD_RED
    )
    
    await sender.send_embed(user.channel_user_id, embed, build_button_rows(buttons))
```

### 4.4. Defer Pattern Implementation

```python
async def handle_status_command(interaction: dict, user_id: str):
    """Handle /status — may take >3s for complex reports."""
    # Step 1: Immediate defer (under 3s deadline)
    # Return this as HTTP response
    return {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

# In background task:
async def process_status_followup(interaction_token: str, user):
    """Process and send status report as followup."""
    report = await generate_monthly_report(user)
    embed = build_status_embed(report, user.locale)
    await discord_sender.edit_original(interaction_token, {"embeds": [embed]})
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | Signature verify valid | Valid Ed25519 sig | True |
| 2 | Signature verify invalid | Tampered body | False → 401 |
| 3 | PING interaction | type=1 | Return `{"type": 1}` |
| 4 | Slash command DM | /start in DM | Create user, send welcome embed |
| 5 | Slash command server | /start in guild | Ephemeral "DM bot" |
| 6 | Button click | cat:123 | Categorize tx, send confirmation |
| 7 | Unknown command | /foo | Ignore gracefully |
| 8 | User signup | /start new user | channel_type='discord', locale set |
| 9 | User existing | /start existing | Status embed, no duplicate |
| 10 | Category picker ≤25 | 10 categories | 1 page, 12 buttons (10+new+skip) |
| 11 | Category picker >25 | 30 categories | 2 pages, pagination buttons |
| 12 | Defer response | /status (slow) | type=5 → followup embed |
| 13 | DM blocked | Send to blocked user | Error 50007 → invalid_channel |
| 14 | Embed char limit | >6000 chars report | Split into 2 embeds |
| 15 | Locale detect vi | interaction locale='vi' | 'vi' |
| 16 | Locale detect en-US | interaction locale='en-US' | 'en' |
| 17 | Locale detect null | interaction locale=null | 'vi' |
| 18 | Feature flag off | ENABLE_DISCORD_CHANNEL=false | 404 on webhook |
| 19 | Rate limit | 429 from Discord | Backoff per retry_after |
| 20 | File attachment | /export CSV | File sent in DM |
| 21 | VietQR image | /upgrade | Image attachment in DM |
| 22 | Language select | Button lang:en | Update locale → English |
| 23 | Multiple embeds | /status all categories | All sections rendered |
| 24 | Button custom_id format | "cat:123" parse | Extract action + ID |
| 25 | Interaction ID dedup | Same interaction twice | Process once |
| 26 | Expired token | Followup after 15min | Error caught, logged |
| 27 | Empty category list | New user, 0 categories | Empty state embed |
| 28 | Settings language change | settings:lang → en | Locale updated, view refreshed |
| 29 | Daily recap DM | Scheduled 23:00 | DM sent (no window check) |
| 30 | Build button rows | 12 buttons | 3 rows × 4/4/4 |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc for Discord channel. Ed25519 verify, DiscordSender adapter, slash commands, embed builder, pagination, defer pattern, 30 test cases. |
