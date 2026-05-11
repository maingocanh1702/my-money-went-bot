# Plan: Tracking-first Mode + Rebrand "Financial Tracking Bot"

## Bối cảnh & insight quan trọng

**Mục tiêu thật của bot**: giúp user track số tiền tiêu trong tháng theo từng category. Allocate budget cho từng category là **optional add-on**, không phải mandatory.

**Main flow**: user assign mỗi transaction vào category tương ứng → bot tổng hợp tháng.

Hiện tại bot đang frame ngược lại: bắt buộc `/allocate` trước, block hoàn toàn nếu chưa có budget. Kèm theo đó là branding "spend less" / "tiêu ít thôi" và tone judgmental — assume user luôn có budget để vi phạm.

Plan này:
1. Đảo positioning: tracking là default, budget là optional.
2. Cho phép tracking-only category (`allocated = 0`).
3. Rebrand bot thành **Financial Tracking Bot**, đổi xưng hô từ "girl" → "you".

---

## Tư tưởng thiết kế

### Hai chế độ category cùng tồn tại

- **Tracking mode** (`allocated = 0`): *"spent X tháng này"* — default cho mọi user mới.
- **Budgeted mode** (`allocated > 0`): *"spent X / allocated Y — Z% left"* — user opt-in qua `/allocate`.

Convert qua lại bằng cách edit amount trong `/manage`:
- Tracking → Budgeted: set amount > 0
- Budgeted → Tracking: set amount = 0

### Default UX = tracking-first

User mới mở bot → nhận tx đầu tiên → bot **tự auto-bootstrap** default tracking categories → user tap để phân loại ngay. Không cần biết `/allocate` tồn tại.

`/allocate` chỉ là entry point optional cho user muốn đặt giới hạn.

---

## Data model — không thay đổi schema

Budget Config sheet giữ nguyên cấu trúc. Category tracking-only chỉ khác ở chỗ `allocated = 0`. Không cần thêm column mới, không cần migration dữ liệu cũ.

Sheet tab name "Budget Config" giữ nguyên (rename = breaking). Document rõ trong README rằng cột `Allocated` là **optional**.

---

## Design decisions cần lưu ý

### 1. `allocated` key giữ implicit ở caller, KHÔNG add vào `get_default_buckets()`

`get_default_buckets()` được dùng bởi cả 2 caller:
- `_start_fresh()` trong `allocation.py` — set `allocated` từ user input
- Auto-bootstrap (mới) trong `sepay.py`, `manage.py` — force `allocated=0`

Nếu thêm `allocated: 0` vào default → misleading cho `_start_fresh()` (giá trị 0 đó sẽ luôn bị override). Spread pattern `{**b, "allocated": 0}` ở caller auto-bootstrap đã đủ rõ ý đồ.

### 2. `daily_cap` giữ default 100k cho `daily_spending`, KHÔNG force `None`

`allocated` và `daily_cap` là 2 concept độc lập:
- `allocated` = monthly budget (optional, signal "want to track vs limit")
- `daily_cap` = daily limit (optional, dùng cho `/today` + `send_daily_recap`)

Auto-bootstrap chỉ override `allocated=0`, **giữ nguyên `daily_cap`** từ default:
- `daily_spending` → cap 100k (`/today`, daily recap hoạt động ngay cho user mới)
- Other buckets → `daily_cap: None` (đúng concept — không có daily limit)

User muốn bỏ cap → `/manage` xóa daily_cap, không cần đổi allocated.

### 3. Auto-bootstrap phải idempotent + race-safe

Race condition: 2 tx đến cùng lúc khi `not buckets` → cả 2 worker cùng loop `write_budget_row()` → có thể tạo duplicate rows trong Budget Config (sheets API không atomic). 

Cần kết hợp:
- **Idempotent helper** ở `sheets.py` — check `find_budget_row()` trước mỗi write
- **In-memory lock** (`asyncio.Lock`) ở caller — serialize bootstrap calls trong cùng process

Chi tiết implementation: xem bước 2 (`sheets.py`) + bước 3 (`sepay.py` + `manage.py`).

---

## Các file cần thay đổi

### 1. `sheets.py` — chỉ thêm 1 helper idempotent

Đã verify các hàm hiện có đã handle tracking sẵn:
- `get_active_buckets()` không filter theo `allocated > 0` — chỉ filter `active=TRUE`.
- `get_bucket_status()` khi `allocated=0` trả về `{"spent": X, "allocated": 0, "remaining": -X}`, `spent` vẫn đúng.
- `calc_pct(spent, 0)` đã có guard `if not total: return 0`.
- `bucket_label()` tìm trong `get_active_buckets()` nên tự nhiên hỗ trợ tracking.
- `get_default_buckets()` đã tồn tại (sheets.py:257) — KHÔNG sửa.

**Thêm 1 hàm mới: `bootstrap_default_categories()`**

Idempotent helper để gọi từ multiple call sites (sepay, manage) mà không tạo duplicate:

```python
def bootstrap_default_categories(month_key: str) -> int:
    """
    Tạo default tracking categories cho month_key nếu chưa có.
    Idempotent: gọi nhiều lần không tạo duplicate rows.
    Trả về số category được tạo mới (0 nếu đã có sẵn).
    """
    created = 0
    for b in get_default_buckets():
        if not find_budget_row(month_key, b["id"]):
            # `allocated=0` → tracking mode. `daily_cap` giữ nguyên từ default.
            write_budget_row(month_key, {**b, "allocated": 0})
            created += 1
    if created > 0:
        invalidate_buckets_cache()
    return created
```

Note: `find_budget_row()` đã tồn tại (sheets.py:248). `write_budget_row()` cũng đã có internal check duplicate (sheets.py:420-422) nên là 2 lớp guard.

---

### 2. `handlers/sepay.py`

**Auto-bootstrap default tracking categories khi chưa có gì — race-safe**

Thay vì block khi `not buckets`, tự động seed default categories với `allocated=0`. Cần lock để chặn race condition khi 2 tx đến cùng lúc:

```python
# sepay.py top-level
import asyncio
_bootstrap_lock = asyncio.Lock()


# Trong handler, thay block "if not buckets: ... return"
if not buckets:
    async with _bootstrap_lock:
        # Re-check inside lock — worker thứ 2 sẽ thấy đã có và skip bootstrap
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        if not buckets:
            created = sh.bootstrap_default_categories(month_key)
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
            
            # Notify user once — first-time onboarding (chỉ khi thực sự tạo mới)
            if created > 0:
                await tg.send_text(
                    f"👋 *Welcome to Financial Tracking Bot!*\n\n"
                    f"Đã tạo sẵn {created} categories cho bạn track. "
                    f"Sau khi categorize xong, dùng /manage để sửa hoặc thêm category mới. "
                    f"Optional: /allocate để đặt budget cho từng mục."
                )
```

3 lớp bảo vệ chống duplicate:
1. `asyncio.Lock` — serialize bootstrap calls trong cùng process
2. Re-check `not buckets` sau khi acquire lock — worker thứ 2 thấy đã có và skip
3. `bootstrap_default_categories()` idempotent — `find_budget_row()` check trước mỗi write

**Sửa big-spend alert — bỏ "GIRL", đổi pronoun, conditional theo budget**

Hiện tại (`sepay.py:158-165`) fire mọi tx ≥ 100k bất kể category. Đổi thành chỉ fire khi category đó có budget:

```python
# Lưu ý: alert này fire SAU khi user pick category, không fire trước nữa
# (move logic vào transaction.py — xem mục 3)
```

Bỏ luôn block "🚨 GIRL." ở `sepay.py:158-165`. Thay bằng comment trung tính lúc nhận tx:

```python
# (Optional) chỉ alert nếu amount > threshold tương đối, không xưng hô
if amount >= 500_000:  # raise threshold cao hơn để bớt noise
    await tg.send_text(f"💸 Lưu ý: tx này khá lớn ({sh.fmt_amount(amount)}).")
```

**Sửa "Cha-ching" message — bỏ slang, neutral hơn**

Hiện tại: `"💸 *Cha-ching! -X just left the building*"` — keep cho tone vui nhưng không xưng "girl". Có thể giữ nguyên.

---

### 3. `handlers/transaction.py`

**Sửa `_finalize()` — thêm nhánh tracking cho OUTGOING**

```python
# Trong nhánh outgoing, thay block hiện tại
else:
    bkt = sh.get_bucket_status(parent_category, month_key)

    if bkt["allocated"] > 0:
        # Budgeted: progress bar + remaining
        pct = sh.calc_pct(bkt["spent"], bkt["allocated"])
        msg += f"{sh.make_bar(pct)} {pct}%\n"
        msg += f"{parent_name}: {sh.fmt_amount(bkt['spent'])} / {sh.fmt_amount(bkt['allocated'])}\n"
        msg += f"Remaining: *{sh.fmt_amount(bkt['remaining'])}*"

        if bkt["remaining"] <= 0:
            msg += "\n🔴 Bucket này đã hết. You're cooked."
        elif pct >= 80:
            msg += "\n🟠 Sắp cạn — cẩn thận!"
    else:
        # Tracking-only: chỉ show tổng tháng, KHÔNG judgment
        msg += f"📊 {parent_name}: tổng tháng này *{sh.fmt_amount(bkt['spent'])}*"
```

**Sửa big-spend alert (line 133-135) — đổi pronoun, conditional**

Hiện tại:
```python
if amount >= _LARGE_TX and not is_daily:
    await tg.send_text(
        f"👀 *{sh.fmt_amount(amount)} on {parent_name}?* Not daily spending, so I'll allow it. Low-key proud of you. 💅"
    )
```

Đổi thành: chỉ fire nếu category có budget (tracking mode = không judge):
```python
bkt_for_alert = sh.get_bucket_status(parent_category, month_key)
if amount >= _LARGE_TX and not is_daily and bkt_for_alert["allocated"] > 0:
    await tg.send_text(
        f"👀 *{sh.fmt_amount(amount)} cho {parent_name}?* "
        f"Not daily spending, ok. Bucket này còn {sh.fmt_amount(bkt_for_alert['remaining'])}."
    )
```

**(Optional) Fix bug có sẵn ở nhánh INCOMING**

`get_bucket_status()` skip `Tiền vào` khi tính spent → `bkt['spent']` luôn = 0 cho income (`transaction.py:124-126`). Fix bằng cách thêm hàm `get_income_total()` hoặc inline logic. Không bắt buộc, nhưng tracking-first làm bug dễ thấy hơn.

---

### 4. `handlers/allocation.py`

**Reframe `/allocate` — explicit là optional**

Welcome msg đầu flow đổi tone:

```python
# start_monthly_allocation — đổi msg
msg = "💰 *Set spending limits (optional)*\n\n"
msg += "Đặt budget cho từng category để bot cảnh báo khi sắp cạn. "
msg += "Bạn có thể skip bước này — categories sẽ chạy ở tracking mode.\n\n"
```

**Thêm option "Track only" trong menu**

Hiện tại menu chỉ có:
```
[📋 Keep last month]  [✏️ Enter fresh amounts]
```

Thêm nút thứ ba:
```
[📋 Keep last month]  [✏️ Enter amounts]  [🏷️ Track only]
```

Note: với tracking-first, "Track only" gần như duplicate với việc skip `/allocate` hoàn toàn. Nhưng vẫn giữ button vì user có thể dùng `/allocate` để **reset** về tracking mode (xóa allocated cũ).

**Flow "Track only" — `_start_track_only()`**

- State step mới: `await_track_pick` (KHÔNG reuse `await_alloc_amount`).
- Loop qua default buckets, chỉ hỏi "có muốn track bucket này không?" (Yes/No buttons), không hỏi amount.
- Mỗi bucket được pick → tạo entry với `allocated=0`. `daily_cap` giữ nguyên từ default (daily_spending → 100k, còn lại → None).
- Cho phép add custom tracking bucket (chỉ hỏi name) — không có `daily_cap`.

**Sửa `_show_alloc_summary()`**

Hiện tại display `fmt_amount(allocated)` — với tracking sẽ show "0đ" trông như budget bị vỡ. Sửa thành:

```python
for b in allocations:
    if b.get('allocated', 0) > 0:
        msg += f"{b['name']}   *{sh.fmt_amount(b['allocated'])}*\n"
        total += b['allocated']
    else:
        msg += f"{b['name']}   _🏷️ tracking_\n"
```

Total chỉ tính phần budgeted.

---

### 5. `handlers/reports.py`

**`/status` (`send_monthly_status`) — tách 2 section + đổi tone**

```
📊 Tracking — 2026-05

BUDGETED:
✅ Daily Spending  ████░░ 60%  600k / 1tr · còn 400k
🟡 Saving         ████████░░ 80%  800k / 1tr · còn 200k

TRACKING:
📊 Clothes        đã tiêu 350k tháng này
📊 Subscription   đã tiêu 120k tháng này
```

Tiêu đề đổi từ "Budget check" → "Tracking" để consistent với positioning. Total chỉ aggregate phần budgeted.

**`/report` monthly (`run_monthly_report`)**

Tách section "BY BUCKET" thành:
- *Budgeted categories*: giữ nguyên format hiện tại (có %, remaining, so sánh tháng trước)
- *Tracked categories*: chỉ show tên + tổng spent + so sánh tháng trước nếu có

`total_alloc` chỉ tính budgeted; `total_spent` tính cả 2.

Đổi tiêu đề "MONTHLY AUTOPSY" → "MONTHLY REPORT" — bớt drama. Section "WATCH NEXT MONTH" chỉ liệt kê budgeted buckets bị over.

**`/weekly` (`run_weekly_summary`) — branch theo allocated**

```python
# reports.py:172 hiện tại
week_budget = round(b["allocated"] / 4.3)  # = 0 với tracking
flag = "⚠️" if week_spent > week_budget else "✅"  # luôn ⚠️
```

Tracking sẽ hiện "spent / ~0đ ⚠️" — sai. Branch tương tự `/status`:

```python
if b["allocated"] > 0:
    week_budget = round(b["allocated"] / 4.3)
    pct  = sh.calc_pct(week_spent, week_budget)
    flag = "⚠️" if week_spent > week_budget else "✅"
    msg += f"{b['name']}: *{sh.fmt_amount(week_spent)}* / ~{sh.fmt_amount(week_budget)} {flag}\n"
else:
    msg += f"📊 {b['name']}: *{sh.fmt_amount(week_spent)}* tuần này\n"
```

**`/today` (`send_today_status`) — đổi pronoun, neutral tone**

Hiện tại tone judgmental ("You're cooked. No more spending today."). Đổi thành neutral:

```python
if pct >= 100:
    msg += "🔴 Vượt giới hạn ngày."
elif pct >= 80:
    msg += f"🟡 Còn *{sh.fmt_amount(day['remaining'])}* hôm nay."
elif day['spent'] == 0:
    msg += "✨ Hôm nay chưa tiêu gì."
else:
    msg += f"💪 Còn *{sh.fmt_amount(day['remaining'])}* trong ngân sách hôm nay."
```

**`send_daily_recap` — đổi tone**

Hiện tại: "I'm not angry. I'm just... deeply, profoundly disappointed." (tone bạn bè judge). Đổi thành neutral, factual:

```python
# Trường hợp overspent
await tg.send_text(
    f"🌙 *End of day — {now.strftime('%b %d')}*\n\n"
    f"Daily spending: *{sh.fmt_amount(day['spent'])}* ({pct}% of limit)\n"
    f"Vượt *{sh.fmt_amount(overspent)}* so với cap ngày.\n\n"
    f"Muốn note lại lý do? Reply để bot ghi vào sheet."
)
```

Section này fire dựa trên `daily_cap` của daily bucket (độc lập với `allocated`). Default 100k cho `daily_spending` → user mới vẫn nhận được recap. User muốn tắt → `/manage` xóa daily_cap.

---

### 6. `handlers/manage.py` — cần thêm

**Cho phép `amount = 0` trong add + edit**

Hiện tại `handle_add_cat_amount` và `handle_manage_amount` đều `assert amount > 0` → không thể add tracking-only qua `/manage`, không thể convert budgeted→tracking.

```python
# handle_add_cat_amount + handle_manage_amount — đổi
try:
    amount = int("".join(c for c in text if c.isdigit())) if text.strip() else 0
    assert amount >= 0  # đổi > 0 → >= 0
except Exception:
    await tg.send_text("⚠️ Số tiền không hợp lệ.")
    return
```

Hoặc tốt hơn: thêm button "🏷️ Track only" trong flow add category để skip bước hỏi amount.

**Sửa `_show_category_list` display**

```python
for b in buckets:
    if b['allocated'] > 0:
        msg += f"{b['name']}   *{sh.fmt_amount(b['allocated'])}*\n"
        total += b['allocated']
    else:
        msg += f"{b['name']}   _🏷️ tracking_\n"
```

**Sửa `_show_bucket_actions` display**

Khi `allocated = 0`, hiển thị "Mode: 🏷️ Tracking-only" thay vì "Allocated: 0đ".

**Convert path explicit**

User edit amount = 0 → thành tracking. User edit amount > 0 → thành budgeted. Không cần UI riêng, dùng "Edit Amount" hiện tại sau khi cho phép amount = 0.

**`/manage` không block khi chỉ có tracking categories — dùng cùng lock với sepay**

Hiện tại (`manage.py:21-26`) block nếu `not buckets`. Vì auto-bootstrap đã chạy ở `/sepay`, user thường sẽ có sẵn buckets. Nhưng nếu user dùng `/manage` trước cả tx đầu tiên → vẫn block. Bổ sung:

```python
# Import shared lock từ sepay (hoặc move lock vào sheets.py để cả 2 dùng chung)
from handlers.sepay import _bootstrap_lock

# Trong start_manage()
if not buckets:
    async with _bootstrap_lock:
        tz = pytz.timezone(TIMEZONE)
        month_key = sh.fmt_month(datetime.now(tz))
        buckets = sh.get_active_buckets(month_key, force_refresh=True)
        if not buckets:
            sh.bootstrap_default_categories(month_key)
            buckets = sh.get_active_buckets(month_key, force_refresh=True)
```

**Cleaner alternative**: move `_bootstrap_lock` vào `sheets.py` cùng với `bootstrap_default_categories()`, expose qua module-level. Caller không cần import từ handler khác.

---

### 7. `main.py` — welcome message, app title

**Đổi app title + health check string**

```python
# main.py:26
app = FastAPI(title="Financial Tracking Bot")

# main.py:122
return {"status": "ok", "bot": "Financial Tracking Bot"}
```

**Đổi welcome / fallback message (line 197-205) — reframe priorities**

```python
await tg.send_text(
    "🤖 *Financial Tracking Bot*\n\n"
    "Tự động ghi mọi giao dịch ngân hàng. Bạn chỉ cần phân loại — bot lo phần còn lại.\n\n"
    "/status   — tháng này tiêu gì?\n"
    "/today    — hôm nay tiêu bao nhiêu?\n"
    "/manage   — sửa categories\n"
    "/allocate — (optional) đặt budget cho từng mục\n"
    "/weekly   — tổng kết tuần\n"
    "/report   — báo cáo tháng"
)
```

`/manage` lên trước `/allocate` vì manage là entry chính giờ. `/allocate` đánh dấu rõ "(optional)".

**Error message (line 140) — bỏ "Bot" xưng hô**

```python
# Hiện tại
await tg.send_text(f"⚠️ Bot gặp lỗi: `{e}`")
# Giữ nguyên — đã neutral
```

---

### 8. `telegram_api.py` — bot commands metadata

**Đổi `set_my_commands` (line 60-68)**

Reorder + reword description:

```python
commands = [
    {"command": "status",   "description": "📊 Tổng quan tháng này"},
    {"command": "today",    "description": "🍜 Hôm nay tiêu bao nhiêu?"},
    {"command": "manage",   "description": "⚙️ Sửa/xóa categories"},
    {"command": "allocate", "description": "💰 (Optional) đặt budget"},
    {"command": "weekly",   "description": "📈 Tổng kết tuần"},
    {"command": "report",   "description": "📅 Báo cáo tháng đầy đủ"},
]
```

`/manage` lên trước `/allocate`, `/allocate` mark "(Optional)", bỏ slang ("how broke", "still eat").

---

### 9. Cron `/trigger/monthly-allocation` — soft check-in

Hiện tại cron 1st-of-month auto-prompt allocate. Tracking-first thì việc auto-prompt budget setup là intrusive. 2 options:

**Option A (low effort)**: giữ trigger nhưng đổi message thành check-in mềm:
```python
# start_monthly_allocation đổi đầu flow
msg = f"📅 *Tháng mới: {month_key}*\n\n"
msg += "Bạn có muốn đặt budget cho tháng này không? Skip cũng OK — categories sẽ chạy ở tracking mode.\n\n"
buttons = [[
    {"text": "💰 Đặt budget", "callback_data": "..."},
    {"text": "🏷️ Track only", "callback_data": "..."},
    {"text": "⏭️ Skip", "callback_data": "al_skip"},
]]
```

**Option B**: disable cron mặc định, để user tự bật trong README.

→ Đề xuất A. README cập nhật cron description.

---

### 10. Rebrand — files khác

| File | Đổi gì |
|---|---|
| `setup.sh:2,8,16,25,27,44,45,48,62` | `maddy-bot` → `financial-tracking-bot`, `"maddy tiêu ít thôi"` → `"Financial Tracking Bot"` |
| `crontab.txt:1` | Comment header rename |
| `.claude/launch.json:5` | `"name": "maddy-bot"` → `"financial-tracking-bot"` |
| `.env.example:27` | URL example rename |
| `handlers/sepay.py:160` | `"GIRL"` → bỏ hẳn (hoặc thay bằng nội dung neutral, xem bước 2) |

**Giữ nguyên** (không rename):
- Sheet tab `Đầu ra` — rename = breaking, không cần thiết.
- Sheet tab `Budget Config` — same.
- `DAILY_BUCKET_ID = "daily_spending"` — internal ID, không user-facing.

---

### 11. README — reframe positioning

**Tagline (line 1, 3)**:
```diff
- # 💸 financial-tracking-bot
- A personal finance Telegram bot that hooks into your bank via SePay, asks you to categorize each transaction, and tracks your budget in Google Sheets — with daily recaps, weekly summaries, and monthly reports.
+ # 📊 Financial Tracking Bot
+ A personal finance Telegram bot that hooks into your bank via SePay and asks you to categorize each transaction. Tracks your monthly spending in Google Sheets — with daily recaps, weekly summaries, and monthly reports. Budget allocation is optional.
```

**Demo flow ASCII (line 10-15)**:
```diff
- → Bot logs it to Google Sheets + shows % of budget used
+ → Bot logs it to Google Sheets + shows tổng tháng (% của budget nếu bạn có set)
```

**Step 5 — First run (line 213-216)**: bỏ mandatory `/allocate`:
```diff
- 1. Start a chat with your bot on Telegram
- 2. Send `/allocate` to set up your budget buckets for the current month
- 3. Make a small test transaction through your bank — the bot should ping you within seconds
+ 1. Start a chat with your bot on Telegram
+ 2. Make a small test transaction — the bot will auto-create default tracking categories and ping you to categorize
+ 3. (Optional) Send `/allocate` to set spending limits for any category
+ 4. Send `/manage` anytime to add/edit categories
```

**Bot commands table (line 220-228)** — reorder, mark allocate optional:
```diff
| Command | What it does |
|---------|-------------|
| `/status` | Monthly overview — all categories, % spent (for budgeted) |
| `/today` | How much you've spent today vs daily limit |
| `/manage` | Add/edit/delete categories |
| `/allocate` | (Optional) set budget for this month |
| `/weekly` | Spending breakdown for the past 7 days |
| `/report` | Full monthly summary |
```

**Document `Allocated` column là optional (line 63-66)**:
```diff
**`Budget Config` tab — row 1 headers:**
A: Month  |  B: Bucket ID  |  C: Name  |  D: Allocated  |  E: Daily Cap  |  F: Active  |  G: Source  |  H: -

+ Note: `Allocated = 0` means tracking-only (no budget limit). User-friendly default.
```

**Project structure section** giữ nguyên.

---

## Thứ tự implement (đã revise đầy đủ)

| Bước | File | Mô tả |
|------|------|-------|
| 1 | `sheets.py` | Thêm `bootstrap_default_categories()` idempotent + `_bootstrap_lock` shared. Existing functions không đổi. |
| 2 | `handlers/sepay.py` | Auto-bootstrap với lock + re-check pattern. Bỏ "GIRL" alert. Soften big-spend alert. |
| 3 | `handlers/transaction.py` | Branch `_finalize` theo `allocated > 0`. Đổi pronoun + conditional alert. Optional fix bug income spent=0. |
| 4 | `handlers/allocation.py` | Thêm "🏷️ Track only" + state step `await_track_pick`. Reframe msg "(optional)". Sửa `_show_alloc_summary` |
| 5 | `handlers/reports.py` | Tách 2 section trong `/status`, `/report`, `/weekly`. Neutral tone trong `/today` + daily recap. |
| 6 | `handlers/manage.py` | Cho `amount = 0` ở add + edit; hiển thị "🏷️ Tracking" thay "0đ"; auto-bootstrap (dùng cùng lock) nếu chưa có buckets |
| 7 | `main.py` | App title `Financial Tracking Bot`, welcome msg reorder + neutral tone |
| 8 | `telegram_api.py` | `set_my_commands` reorder, đổi description "(Optional)" cho `/allocate` |
| 9 | `handlers/allocation.py` | Cron monthly-allocation → soft check-in (đặt budget hay skip) |
| 10 | `setup.sh`, `crontab.txt`, `.claude/launch.json`, `.env.example` | Rename `maddy-bot` → `financial-tracking-bot`, bỏ "tiêu ít thôi" |
| 11 | `README.md` | Reframe positioning tracking-first, document `Allocated` optional, reorder bot commands |

---

## Test cases cần cover

### Onboarding (tracking-first default)
- [ ] User mới (chưa có row nào trong Budget Config) → tx đầu tiên → bot auto-seed default categories với `allocated=0`, hiện picker, send welcome msg một lần
- [ ] User mở `/manage` trước cả tx đầu → cũng auto-bootstrap, không block
- [ ] **Race test**: gửi 2 tx liên tiếp khi chưa có category nào → Budget Config chỉ có đúng 5 rows (số default), không duplicate
- [ ] **Race test**: gọi `/manage` đồng thời với tx đầu tiên → cả 2 path đều thấy đủ 5 categories, không duplicate
- [ ] Welcome msg chỉ fire 1 lần (worker thứ 2 thấy `created == 0` → skip msg)
- [ ] User mới → `/today` hoạt động ngay với `daily_cap=100k` mặc định của `daily_spending`
- [ ] User mới → daily recap fire bình thường vào 11pm (không bị skip vì allocated=0)

### Happy path
- [ ] Giao dịch khi có tracking category (allocated = 0) → hiện picker, sau khi chọn show tổng tháng (không % progress bar)
- [ ] Giao dịch khi có cả budgeted lẫn tracking category → picker hiện đủ cả hai, mỗi loại hiện đúng format
- [ ] `/allocate` → chọn "🏷️ Track only" → tạo category không có amount → hoạt động đúng
- [ ] `/allocate` → chọn "Skip" trong cron monthly check-in → không tạo budget, categories vẫn track bình thường
- [ ] `/status` → hiện 2 section rõ ràng (BUDGETED + TRACKING)
- [ ] `/report` → budgeted và tracking tách biệt, total_alloc chỉ tính budgeted
- [ ] `/weekly` với mix budgeted + tracking → tracking hiện đúng (không có "/ ~0đ ⚠️")

### Convert paths
- [ ] **Upgrade**: tracking category → `/manage` set amount > 0 → chuyển sang budgeted, `/status` di chuyển từ TRACKING sang BUDGETED section
- [ ] **Downgrade**: budgeted bucket → `/manage` set amount = 0 → chuyển sang tracking, transactions cũ vẫn count đúng

### Tone / branding
- [ ] Không còn "GIRL", "maddy", "spend less", "tiêu ít thôi" trong bất kỳ user-facing message nào
- [ ] Big-spend alert chỉ fire khi category có `allocated > 0` (tracking-only category không bị alert)
- [ ] Daily recap fire dựa trên `daily_cap` (độc lập với `allocated`); user xóa `daily_cap` qua `/manage` → recap skip
- [ ] Welcome msg `main.py` show `/manage` trước `/allocate`, `/allocate` mark "(optional)"
- [ ] `set_my_commands` description đã update + reorder
- [ ] App title trong `/health` endpoint trả về "Financial Tracking Bot"

### `/manage`
- [ ] `/manage` → "Add Category" → nhập amount = 0 (hoặc chọn "Track only") → tạo tracking category thành công
- [ ] `/manage` → category list hiển thị "🏷️ tracking" thay "0đ" cho tracking categories
- [ ] `/manage` → bucket actions cho tracking category hiển thị mode đúng

### Edge cases
- [ ] Income vào tracking category → display tổng nhận đúng (kèm fix bug income spent=0 nếu fix luôn)
- [ ] Tracking-only daily_spending bucket → `/today` không crash; nếu không có daily_cap, hiện "Chưa set daily limit, dùng /allocate để bật"
- [ ] Soft-delete tracking category → biến mất khỏi picker, transactions cũ không ảnh hưởng
- [ ] Cron `/trigger/monthly-allocation` → user nhận check-in soft prompt, có nút Skip
