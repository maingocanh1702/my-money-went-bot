# Plan: "+ New category" button inline khi categorize transaction

## Goal
Cho phép user tạo parent category mới ngay từ màn hình "Pick a category" (sau khi bot phát hiện transaction), thay vì phải `/manage` trước rồi quay lại.

## UX Flow

```
Bot: -29.000đ PAYOO-HIGHLANDS — Khoản này thuộc mục nào?
[🛒 Daily Spending]  [🏦 Saving]
[📱 Subscription]    [🏋 Sports]
[🍺 Drink]           [🍕 Food]
[➕ New category]                    ← thêm 1 button này, full-width

User: tap [➕ New category]
Bot:  📝 Tên category mới? (VD: "🎮 Gaming" hoặc "Health")

User: types "🎮 Gaming"
Bot:  ✅ Đã tạo *🎮 Gaming* (track-only mode)
      → finalize transaction luôn, không hỏi sub-category, không hỏi budget

       ✅ Logged: 🎮 Gaming
       💸 -29.000đ
       📊 🎮 Gaming: tổng tháng này 29.000đ
       [🔄 Sai mục?]
```

**Design choices** (giữ flow ngắn nhất có thể):
- Default mode = **track-only** (`allocated=0`, `daily_cap=None`). Muốn set budget sau thì dùng `/manage` hoặc `/allocate`.
- **Không hỏi sub-category** cho lần đầu — vì category mới chưa có sub nào trong sheet. User có thể recategorize qua nút "🔄 Sai mục?" nếu cần.
- **Không hỏi confirm** — name là confirm rồi.

## Files to change

### 1. `telegram_api.py` — `build_bucket_buttons()`
Thêm param `include_new: bool = False`. Khi `True`, append 1 row cuối chứa button `➕ New category` với `callback_data = f"{prefix}_new"`.

```python
def build_bucket_buttons(buckets, prefix, include_new=False):
    buttons = [{"text": b["name"], "callback_data": f"{prefix}_{b['id']}"} for b in buckets]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if include_new:
        rows.append([{"text": "➕ New category", "callback_data": f"{prefix}_new"}])
    return rows
```

### 2. Callsites — pass `include_new=True`
Chỉ 3 callsites ở chỗ categorize transaction (KHÔNG động `/manage` ở `manage.py:50` để tránh trùng UX với add-category flow đã có sẵn ở đó). `email_parser.py` không gọi `build_bucket_buttons` — email flow reuse SePay handler.

- `handlers/sepay.py:153` — prompt categorize lần đầu (outgoing tx)
- `handlers/sepay.py:179` — prompt categorize lần đầu (incoming tx)
- `handlers/transaction.py:91` — re-categorize (`handle_recategorize`)

### 3. `handlers/transaction.py::handle_parent_selected` — handle `bucket_id == "new"`
Thêm branch ngay sau check `"skip"` (line 19-25), TRƯỚC `sh.finalize_transaction(row_num, bucket_id, "")` ở line 27. Phải `return` sớm để không finalize với `bucket_id="new"` (sentinel).

```python
if bucket_id == "new":
    prev_state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {
        **prev_state,                      # preserve tx_date, tx_direction, amount, description
        "step": "await_inline_new_cat_name",
        "row_num": row_num,
        "message_id": message_id,
    })
    await tg.edit_message(message_id, "📝 *Tên category mới?* _(VD: 🎮 Gaming)_")
    return                                  # quan trọng: skip finalize_transaction line 27
```

### 4. `handlers/transaction.py` — `handle_inline_new_cat_name(text, state)`
New function:

```python
async def handle_inline_new_cat_name(text: str, state: dict):
    import unicodedata, re
    from datetime import datetime
    name = text.strip()
    if not name or len(name) > 40:
        await tg.send_text("⚠️ Tên không hợp lệ (1-40 ký tự). Thử lại.")
        return

    # Normalize → id (same logic as handlers/manage.py:340-346)
    nid = unicodedata.normalize("NFD", name.lower())
    nid = re.sub(r"[\u0300-\u036f]", "", nid)   # strip diacritics — escape form, consistent với manage.py + allocation.py
    nid = re.sub(r"[^\w\s]", "", nid)
    nid = re.sub(r"\s+", "_", nid.strip())
    nid = re.sub(r"[^a-z0-9_]", "", nid) or "custom"

    # Reserved sentinels — collide với callback "p_{row}_new" và "p_{row}_skip"
    if nid in ("new", "skip"):
        await tg.send_text(f"⚠️ Tên *{name}* trùng từ khóa hệ thống. Nhập tên khác.")
        return

    tz = pytz.timezone(TIMEZONE)
    month_key = sh.fmt_month(datetime.now(tz))

    # Dedup check
    existing = sh.get_active_buckets(month_key, force_refresh=True)
    if any(b["id"] == nid for b in existing):
        await tg.send_text(f"⚠️ *{name}* đã tồn tại. Nhập tên khác.")
        return

    # Create as track-only (allocated=0)
    sh.write_budget_row(month_key, {"id": nid, "name": name, "allocated": 0, "daily_cap": None})
    sh.invalidate_buckets_cache()

    # Finalize the pending transaction with this new category, no sub
    row_num = state["row_num"]
    await _finalize(row_num, nid, "", state.get("message_id"))
```

### 5. `main.py` — wire state machine
Add ở `_handle_message` (sau line 195):

```python
elif step == "await_inline_new_cat_name":
    await handle_inline_new_cat_name(text, state)
```

Và import: `from handlers.transaction import ..., handle_inline_new_cat_name`

## Edge cases

| Case | Behavior |
|---|---|
| Empty / whitespace name | Reject, prompt lại |
| Name > 40 chars | Reject |
| Name normalize ra empty id (toàn emoji) | Fallback `nid = "custom"` — nhưng nếu `custom` đã tồn tại thì dedup check sẽ reject, user phải đổi tên |
| Duplicate name | Reject với gợi ý đổi tên |
| User abort giữa chừng (gửi `/status`, `/today`...) | Đã có sẵn pattern: `_handle_message` line 170 check `text.startswith("/")` BEFORE state machine → command chạy bình thường. **Quan trọng**: trong branch `bucket_id == "new"`, KHÔNG gọi `sh.finalize_transaction(row_num, "new", "")` — chỉ set state. Khi user nhập tên thành công mới finalize qua `_finalize`. Nếu user abort, transaction row giữ nguyên không có category, có thể recover qua "🔄 Sai mục?" sau. |
| Reserved sentinel collision | `nid in ("new", "skip")` reject để không clash với callback `p_{row}_new` / `p_{row}_skip` |
| Race: 2 transaction pending cùng lúc | State machine single-slot per chat → tx thứ 2 sẽ override. Edge case hiếm với personal bot. |

## Testing checklist
- [ ] Gửi fake transaction → thấy nút `➕ New category` ở row cuối, full-width
- [ ] Tap → bot hỏi tên → type "🎮 Gaming" → bot finalize transaction với category mới, hiển thị "📊 tổng tháng này"
- [ ] Verify trong Google Sheet `BUDGET_CONFIG` có row mới với `allocated=0`, `active=TRUE`
- [ ] Transaction tiếp theo phải thấy "🎮 Gaming" trong list buttons (cache invalidated)
- [ ] Duplicate name → reject
- [ ] `/manage` vẫn không có nút `➕ New category` (chỉ inline khi categorize)
- [ ] `/allocate` flow không bị ảnh hưởng

## Out of scope (nếu sau này muốn)
- Hỏi budget amount inline (hiện tại default track-only, dùng `/manage` để set budget sau)
- Inline tạo sub-category mới khi pick parent (đã có `📦 Other` rồi)
- Emoji picker / suggestion
