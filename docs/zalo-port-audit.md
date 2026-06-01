# Telegram → Zalo Bot Port Audit

## Zalo Bot API Capabilities (from [docs](https://bot.zapps.me/docs/))

| Capability | Supported? | Notes |
|---|---|---|
| `sendMessage` (text) | ✅ | Max 2000 chars |
| `sendPhoto` | ✅ | Can send images |
| `sendSticker` | ✅ | Zalo stickers only |
| `sendChatAction` | ✅ | Typing indicator |
| Inline keyboard buttons | ❌ | **Not supported** |
| `editMessageText` | ❌ | **Not supported** |
| `deleteMessage` | ❌ | **Not supported** |
| `answerCallbackQuery` | ❌ | **Not supported** |
| Markdown / HTML formatting | ❌ | Plain text only |
| Webhook events | ✅ | `message.text.received`, `message.image.received`, `message.sticker.received` |
| `setWebhook` / `deleteWebhook` | ✅ | With secret_token |

> [!IMPORTANT]
> Zalo Bot **không hỗ trợ inline buttons** → tất cả interactive flows phải dùng text-based state machine (reply số/text). Đây là constraint lớn nhất khi port.

---

## Feature Parity Matrix

### 1. Read-Only Commands (Stateless)

| Feature | Telegram | Zalo | Status |
|---|---|---|---|
| `/today` — Hôm nay tiêu bao nhiêu | ✅ | ✅ | ✅ Ported |
| `/report` — Chi tiêu theo kỳ | ✅ (buttons: tuần/tháng/quý/năm) | ✅ (text arg: `/report tuần`) | ✅ Ported (text-based) |
| `/accounts` — List accounts | ✅ (buttons: add/manage) | ✅ (list only) | ⚠️ Partial — read-only |
| Help / unknown command | ✅ | ✅ | ✅ Ported |

### 2. Interactive Commands (Stateful)

| Feature | Telegram | Zalo | Status | Khả thi? |
|---|---|---|---|---|
| **`/keywords`** — CRUD keyword rules | ✅ (inline buttons) | ✅ (text-based state machine) | ✅ **Vừa port xong** | ✅ |
| `/manage` — CRUD categories | ✅ (inline buttons: rename, amount, delete, add) | ❌ | 🔴 **Chưa port** | ✅ Khả thi |
| `/allocate` — Set monthly budget | ✅ (inline buttons: pick bucket → enter amount) | ❌ | 🔴 **Chưa port** | ✅ Khả thi |
| `/accounts` — Add new account | ✅ (multi-step wizard: name → type → balance) | ❌ | 🔴 **Chưa port** | ✅ Khả thi |
| `/cancel` — Cancel current operation | ✅ (inline buttons / command) | ✅ | ✅ Ported |

### 3. Transaction Categorization Flow

| Feature | Telegram | Zalo | Status | Khả thi? |
|---|---|---|---|---|
| SePay webhook → notification | ✅ | ✅ (via [notifier.py](file:///Users/maingocanh/Projects/My%20Money%20Went%20Bot/notifier.py)) | ✅ Ported |  |
| Pick parent category (buttons) | ✅ (inline buttons) | ❌ | 🔴 **Chưa port** | ⚠️ Phức tạp |
| Pick sub-category (buttons) | ✅ (inline buttons) | ❌ | 🔴 **Chưa port** | ⚠️ Phức tạp |
| Freetext sub-category | ✅ | ❌ | 🔴 | ⚠️ |
| "Sai mục?" → Recategorize | ✅ (inline button on notification) | ❌ | 🔴 | ⚠️ |
| Auto-categorize via keyword | ✅ | ✅ (shared rules) | ✅ Works |
| Account setup prompt ("Setup") | ✅ (inline button → wizard) | ❌ | 🔴 | ⚠️ |

### 4. Cron Triggers

| Feature | Telegram | Zalo | Status |
|---|---|---|---|
| Daily recap notification | ✅ | ⚠️ Telegram-only | 🔴 **Chưa fan-out sang Zalo** |
| Monthly allocation prompt | ✅ | N/A (interactive) | ⚠️ Could notify |

### 5. Infrastructure

| Feature | Telegram | Zalo | Status |
|---|---|---|---|
| Webhook endpoint | `/webhook` | `/zalo/webhook` | ✅ |
| Webhook secret validation | ✅ `X-Telegram-Bot-Api-Secret-Token` | ✅ `X-Bot-Api-Secret-Token` | ✅ |
| Sender validation | ✅ `CHAT_ID` | ✅ `ZALO_USER_ID` | ✅ |
| Bot echo rejection | ✅ `is_bot` | ✅ `is_bot` | ✅ |
| Private chat filter | ✅ (implicit) | ✅ `chat_type == PRIVATE` | ✅ |
| Markdown → plain text | N/A | ✅ [zalo_api.strip_markdown](file:///Users/maingocanh/Projects/My%20Money%20Went%20Bot/zalo_api.py#L22-L42) | ✅ |
| Text chunking (2000 char) | N/A | ✅ [zalo_api.chunk_text](file:///Users/maingocanh/Projects/My%20Money%20Went%20Bot/zalo_api.py#L46-L76) | ✅ |

---

## Gap Analysis — Chi tiết từng feature chưa port

### 🔴 Gap 1: `/manage` — CRUD categories

**Telegram flow**: `/manage` → list categories with buttons → tap → action menu (rename, edit amount, delete, add sub) → text input → confirm

**Zalo approach**: Text-based state machine giống `/keywords`:
- `/manage` → numbered list categories
- Reply số → action menu (reply "rename", "amount", "delete", "add")
- Reply text/number cho từng action
- `/cancel` hủy

**Complexity**: Medium — 6 handler states, ~200 LOC

---

### 🔴 Gap 2: `/allocate` — Monthly budget allocation

**Telegram flow**: `/allocate` → list buckets with amounts → tap bucket → enter amount → saved

**Zalo approach**:
- `/allocate` → numbered list buckets + current amounts
- Reply số → enter amount → saved
- `/cancel` hủy

**Complexity**: Low — 3 handler states, ~100 LOC

---

### 🔴 Gap 3: `/accounts` — Add/manage accounts

**Telegram flow**: `/accounts` → list accounts + "Add" button → multi-step wizard (name → type → source_key → balance)

**Zalo approach**:
- `/accounts` → numbered list + "add" option
- Reply "add" → enter name → pick type (1-4) → enter balance → done

**Complexity**: Medium-High — 5+ handler states, wizard logic

---

### 🔴 Gap 4: Transaction categorization on Zalo

**Telegram flow**: SePay webhook → notification with inline buttons for category pick → tap → sub-category → confirmed

**Zalo limitation**: Zalo nhận notification nhưng KHÔNG thể categorize trực tiếp vì:
1. Không có inline buttons
2. Text reply trên Zalo sẽ overwrite current state nếu user đang trong flow khác
3. Transaction categorization cần context (row_num) mà text reply không carry

**Possible approach**: 
- Reply với transaction number để bắt đầu categorize
- Hoặc: Bot show numbered pending transactions → reply số → pick category → done
- Hoặc: Keep categorization on Telegram only (recommend)

> [!WARNING]
> Transaction categorization trên Zalo là phức tạp nhất vì cần track pending uncategorized transactions per session. Recommend giữ trên Telegram.

---

### 🔴 Gap 5: Daily recap → Zalo fan-out

**Current**: [notifier.py](file:///Users/maingocanh/Projects/My%20Money%20Went%20Bot/notifier.py) fan-out SePay notifications, nhưng daily recap ([handlers/reports.py](file:///Users/maingocanh/Projects/My%20Money%20Went%20Bot/handlers/reports.py) `send_daily_recap`) chỉ gửi Telegram.

**Fix**: Thêm `zalo.send_text()` sau `tg.send_text()` trong `send_daily_recap`.

**Complexity**: Trivial — 3 LOC

---

## Recommendation — Priority Order

| Priority | Feature | Effort | Impact |
|---|---|---|---|
| 1 | 🟢 Daily recap fan-out | Trivial (3 LOC) | Cao — user nhận recap trên Zalo |
| 2 | 🟡 `/manage` interactive | Medium (~200 LOC) | Trung bình — quản lý categories |
| 3 | 🟡 `/allocate` interactive | Low (~100 LOC) | Thấp — budget ít thay đổi |
| 4 | 🟡 `/accounts add` wizard | Medium-High (~250 LOC) | Thấp — setup 1 lần |
| 5 | 🔴 Transaction categorization | High (~400 LOC) | ⚠️ Phức tạp, recommend giữ Telegram |

## Đã port ✅ (Tổng kết)

- `/today`, `/report`, `/accounts` (read-only)
- `/keywords` (full CRUD: list, add, edit keyword, change category, delete)
- `/cancel`
- SePay notification fan-out
- Webhook security + sender validation
- Markdown stripping + text chunking
