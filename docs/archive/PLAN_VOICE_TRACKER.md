# Plan: Tracker + Voice + Smart Nag

## Bối cảnh & insight

Sau khi pivot sang tracking-first, bot mất personality — biến thành generic transaction logger. Nhưng tracking và voice/nag không phải mutually exclusive: voice là **presentation layer**, nag là **detection layer**, cả 2 độc lập với việc có/không có budget.

Plan này restore character cho bot mà vẫn giữ tracking-first architecture đã build:

```
Tracking layer (neutral data)
       ↓
Pattern detection (smart, learn từ user)
       ↓
Voice layer (personality, configurable)
       ↓
User
```

---

## Nguyên tắc thiết kế

### 1. Voice ≠ judgment cứng

- Old: "GIRL DO YOU WANT TO BE BROKE" — fire mọi tx ≥ 100k bất kể context
- New: observational sass — bot quan sát pattern và comment có voice

### 2. Nag dựa vào personal baseline, không dựa vào cap cứng

Bot tính baseline từ history (rolling 30d):
- Avg daily spend
- Top categories
- Frequency mỗi category/tuần

Trigger nag khi today/category lệch khỏi baseline đáng kể, **không cần user pre-configure cap**.

### 3. `daily_cap` giữ làm optional manual override

- Default: bot dùng personal baseline (smart)
- User muốn cap cứng → set `daily_cap` qua `/manage` → bot dùng cap thay vì baseline
- Backward compat: user hiện có `daily_cap=100k` không bị ảnh hưởng

### 4. Tone configurable

3 levels qua settings:
- `chill` — factual + minimal emoji
- `normal` — observational sass (default)
- `brutal` — full personality, dramatic

User chọn theo nhu cầu, không bắt buộc.

---

## Data model — thêm 1 entry trong Bot State

Không đổi schema chính. Thêm 1 key vào Bot State JSON cho settings:

```json
{
  "tone": "normal",          // chill | normal | brutal
  "baseline_cache": {        // optional, cache để tránh compute mỗi tx
    "month_key": "2026-05",
    "computed_at": "2026-05-05T10:00:00",
    "daily_avg": 180000,
    "category_freq": {...},
    "category_weekly_avg": {...}
  }
}
```

`Budget Config` giữ nguyên — `daily_cap` (col E) vẫn là optional cap cứng.

---

## Các file cần thay đổi

### 1. `voice.py` — module mới

Tách logic chọn message ra khỏi handlers:

```python
# voice.py
"""Centralized message templates với personality varies theo signals."""

import random
from datetime import datetime
import pytz
from config import TIMEZONE


def pick_tx_confirm_msg(
    amount: float, parent_name: str, sub_label: str,
    tx_date: datetime, tone: str = "normal",
    signals: dict | None = None,  # {is_repeat: bool, freq_count: int, vs_baseline_pct: int, ...}
) -> str:
    """Pick confirmation message based on amount tier, time, category, and tone."""
    signals = signals or {}
    tier = _amount_tier(amount)
    hour = _local_hour(tx_date)
    
    # Build candidate templates by (tier, tone, signals) → list[str]
    templates = _CONFIRM_TEMPLATES[tone][tier]
    
    # Filter by signals — repeat coffee triggers different template
    if signals.get("is_repeat") and signals.get("freq_count", 0) >= 3:
        templates = _REPEAT_TEMPLATES[tone]
    elif hour >= 23 or hour < 5:
        templates = _LATE_NIGHT_TEMPLATES[tone] + templates
    
    return random.choice(templates).format(
        amount=fmt_amount(amount),
        category=parent_name,
        n=signals.get("freq_count", 0),
    )


_CONFIRM_TEMPLATES = {
    "chill": {
        "small":  ["💸 {amount}, noted."],
        "medium": ["💸 {amount} → {category}"],
        "big":    ["💸 {amount}. tx lớn — đã ghi nhận."],
    },
    "normal": {
        "small":  ["💸 {amount}. small one.", "📝 {amount} noted."],
        "medium": ["💸 {amount} cho {category}", "👀 {amount} → {category}"],
        "big":    ["👀 {amount}?! tx lớn nhất tuần đó.", "💸 {amount} — quan trọng chứ?"],
    },
    "brutal": {
        "small":  ["💸 {amount}. còn từng đồng đấy.", "👀 vẫn đếm nhé. {amount}."],
        "medium": ["💸 {amount} cho {category}. cần chứ muốn?",
                   "👀 {amount} → {category}. lần thứ mấy tháng này rồi?"],
        "big":    ["💸 *{amount}*?! bạn vui chứ tôi lo 🫠",
                   "👀 nửa triệu. ngày mai bạn vẫn nhớ tx này chứ?"],
    },
}

_REPEAT_TEMPLATES = {
    "chill":  ["💸 {amount} → {category} (#{n} tuần này)"],
    "normal": ["☕ #{n} trong tuần đó.", "👀 {category} #{n} — addict gì đấy?"],
    "brutal": ["☕ {category} #{n} trong tuần. khi nào dừng được?",
               "💸 lại {category}? {n} lần rồi đấy. ngon hay quen?"],
}

_LATE_NIGHT_TEMPLATES = {
    "chill":  ["🌙 {amount} late night."],
    "normal": ["🌙 {amount} đêm khuya. đói hay buồn?"],
    "brutal": ["🌙 {amount} lúc 1am. emotional spending detected 👀"],
}


def _amount_tier(amount: float) -> str:
    if amount < 50_000: return "small"
    if amount < 300_000: return "medium"
    return "big"


def _local_hour(tx_date: datetime) -> int:
    tz = pytz.timezone(TIMEZONE)
    if tx_date.tzinfo is None:
        tx_date = pytz.utc.localize(tx_date)
    return tx_date.astimezone(tz).hour
```

Tương tự thêm `pick_welcome_msg()`, `pick_recap_msg()`, etc.

---

### 2. `baseline.py` — module mới

Compute personal baselines từ transaction history:

```python
# baseline.py
"""Personal spending baselines — rolling stats để smart nag."""

from datetime import datetime, timedelta
import pytz
import sheets as sh
from config import TIMEZONE


def compute_baseline(month_key: str, lookback_days: int = 30) -> dict:
    """Aggregate last N days của tx → baseline stats.
    
    Returns:
        {
            "daily_avg": float,                    # trung bình/ngày
            "category_freq_per_week": dict,         # {category_id: float}
            "category_avg_amount": dict,            # {category_id: float}
            "computed_at": iso string,
        }
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    cutoff = now - timedelta(days=lookback_days)
    
    ws = sh._sheet(sh.S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]
    
    daily_totals = {}        # date_str → sum
    cat_counts = {}          # cat_id → count
    cat_sums = {}            # cat_id → sum
    
    for r in rows:
        if len(r) < 14 or str(r[13]).upper() != "TRUE": continue
        if len(r) > 6 and r[6] == "Tiền vào": continue
        try:
            d = datetime.fromisoformat(str(r[1]))
            if d.tzinfo is None: d = tz.localize(d)
            if d < cutoff: continue
        except Exception:
            continue
        
        amt = sh._parse_amount(r[7])
        cat = r[10] or "uncategorized"
        date_key = d.strftime("%Y-%m-%d")
        daily_totals[date_key] = daily_totals.get(date_key, 0) + amt
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        cat_sums[cat] = cat_sums.get(cat, 0) + amt
    
    n_days = max(1, len(daily_totals))
    n_weeks = max(1, lookback_days / 7)
    
    return {
        "daily_avg": sum(daily_totals.values()) / n_days,
        "category_freq_per_week": {k: v / n_weeks for k, v in cat_counts.items()},
        "category_avg_amount": {k: cat_sums[k] / cat_counts[k] for k in cat_counts},
        "computed_at": now.isoformat(),
    }


def detect_anomalies(today_spent: float, today_cat: str, today_count_this_week: int,
                     baseline: dict) -> list[dict]:
    """Trả về list signals để voice layer dùng."""
    signals = []
    
    # Today vs daily average
    if baseline["daily_avg"] > 0 and today_spent > baseline["daily_avg"] * 1.5:
        signals.append({
            "type": "above_average",
            "ratio": today_spent / baseline["daily_avg"],
        })
    
    # Category frequency spike
    weekly_avg = baseline["category_freq_per_week"].get(today_cat, 0)
    if weekly_avg > 0 and today_count_this_week > weekly_avg * 1.5:
        signals.append({
            "type": "category_spike",
            "category": today_cat,
            "count_this_week": today_count_this_week,
            "weekly_avg": weekly_avg,
        })
    
    return signals
```

Cache baseline trong Bot State để tránh compute mỗi tx (đắt — phải đọc full sheet history).

---

### 3. `handlers/transaction.py` — wire voice + signals

```python
import voice
import baseline as bl

async def _finalize(row_num, parent_category, sub_label, message_id):
    # ... existing logic ...
    
    # Get user's tone setting
    state = sh.get_state(CHAT_ID) or {}
    tone = state.get("tone", "normal")
    
    # Compute or fetch cached baseline
    cached = state.get("baseline_cache", {})
    if cached.get("month_key") != month_key or _stale(cached.get("computed_at")):
        baseline_data = bl.compute_baseline(month_key)
        sh.set_state(CHAT_ID, {**state, "baseline_cache": {**baseline_data, "month_key": month_key}})
    else:
        baseline_data = cached
    
    # Detect anomalies for this tx
    today_spent = sh.get_daily_status(tx_date)["spent"]
    cat_count_week = _count_category_this_week(parent_category, tx_date)
    signals_list = bl.detect_anomalies(today_spent, parent_category, cat_count_week, baseline_data)
    
    # Pick message based on tone + signals
    signals_dict = {
        "is_repeat": cat_count_week >= 3,
        "freq_count": cat_count_week,
        "vs_baseline_pct": int((today_spent / baseline_data["daily_avg"] - 1) * 100) if baseline_data["daily_avg"] else 0,
    }
    intro = voice.pick_tx_confirm_msg(amount, parent_name, sub_label, tx_date, tone, signals_dict)
    
    # Build full msg với intro voice + tracking data
    msg = f"{intro}\n\n"
    if bkt["allocated"] > 0:
        # budgeted display (như current)
        ...
    else:
        msg += f"📊 {parent_name}: tổng tháng này *{sh.fmt_amount(bkt['spent'])}*"
    
    # Append nag if signals fired
    for sig in signals_list:
        msg += "\n" + voice.format_signal(sig, tone)
    
    await tg.send_with_buttons(msg, recat_button)
```

---

### 4. `handlers/sepay.py` — voice trong "received tx" msg

```python
# Replace dry "💸 -X" với pick_tx_received_msg
intro = voice.pick_tx_received_msg(amount, description, tx_date, tone)
await tg.send_with_buttons(
    f"{intro}\n`{description}`\n\nKhoản này thuộc mục nào? 🤔",
    buttons,
)
```

Welcome msg cho user mới cũng dùng `voice.pick_welcome_msg(tone)` thay hardcode.

---

### 5. `handlers/reports.py` — `/today` redesign

```python
async def send_today_status():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_key = sh.fmt_month(now)
    
    state = sh.get_state(CHAT_ID) or {}
    tone = state.get("tone", "normal")
    
    # Always count tx hôm nay (bỏ filter chỉ daily_spending bucket)
    day_data = sh.get_today_breakdown(now)  # {total, by_category: [{name, amount, count}]}
    
    # Check optional manual cap
    buckets = sh.get_active_buckets(month_key)
    daily_bkt = next((b for b in buckets if b["id"] == DAILY_BUCKET_ID), None)
    manual_cap = daily_bkt.get("daily_cap") if daily_bkt else None
    
    # Get baseline for comparison
    baseline_data = _get_or_compute_baseline(state, month_key)
    daily_avg = baseline_data.get("daily_avg", 0)
    
    msg = f"🍜 *Today — {now.strftime('%b %d')}*\n\n"
    msg += f"Hôm nay: *{sh.fmt_amount(day_data['total'])}* ({day_data['count']} tx)\n"
    
    # Manual cap mode (nếu user set)
    if manual_cap:
        pct = sh.calc_pct(day_data['total'], manual_cap)
        msg += f"{sh.make_bar(pct)} {pct}% of {sh.fmt_amount(manual_cap)} cap\n"
        if pct >= 100:
            msg += voice.pick_over_cap_msg(day_data['total'] - manual_cap, tone) + "\n"
    
    # Baseline comparison (smart, no manual config needed)
    elif daily_avg > 0:
        diff_pct = int((day_data['total'] / daily_avg - 1) * 100) if daily_avg else 0
        if diff_pct > 50:
            msg += voice.pick_above_baseline_msg(diff_pct, daily_avg, tone) + "\n"
        elif diff_pct < -30:
            msg += voice.pick_below_baseline_msg(diff_pct, tone) + "\n"
        msg += f"_baseline: {sh.fmt_amount(daily_avg)}/ngày_\n"
    
    # By category breakdown
    if day_data['by_category']:
        msg += "\nBy category:\n"
        for cat in day_data['by_category']:
            line = f"{cat['name']}  {sh.fmt_amount(cat['amount'])}"
            if cat.get('weekly_count'):
                line += f" — #{cat['weekly_count']} tuần này"
            msg += line + "\n"
    
    await tg.send_text(msg)
```

`get_today_breakdown` mới ở `sheets.py` — count tx hôm nay across all categories (kể cả uncategorized), trả về breakdown.

---

### 6. `handlers/reports.py` — `send_daily_recap`

Recap cũng dùng baseline:

```python
async def send_daily_recap():
    # ... existing skip if no manual cap AND no baseline ...
    
    state = sh.get_state(CHAT_ID) or {}
    tone = state.get("tone", "normal")
    day_data = sh.get_today_breakdown(now)
    manual_cap = ...
    baseline = ...
    
    if manual_cap:
        # Manual cap recap
        pct = sh.calc_pct(day_data['total'], manual_cap)
        msg = voice.pick_recap_with_cap(day_data['total'], manual_cap, pct, tone)
    elif baseline.get("daily_avg"):
        # Baseline recap — bot quan sát, không judge cap
        msg = voice.pick_recap_with_baseline(day_data['total'], baseline['daily_avg'], tone)
    else:
        # Không có gì để compare (user mới, < 7 days history) → skip recap
        return
    
    await tg.send_text(msg)
```

---

### 7. `handlers/manage.py` — Settings entry

Thêm Settings menu cho tone:

```python
async def _show_category_list(month_key, buckets):
    # ... existing ...
    buttons = tg.build_bucket_buttons(buckets, "mg_sel")
    buttons.append([
        {"text": "➕ Add Category", "callback_data": "mg_add"},
        {"text": "⚙️ Settings", "callback_data": "mg_settings"},
    ])
    await tg.send_with_buttons(msg, buttons)


async def _show_settings():
    state = sh.get_state(CHAT_ID) or {}
    current_tone = state.get("tone", "normal")
    msg = (
        f"⚙️ *Settings*\n\n"
        f"Bot tone: *{current_tone}*\n\n"
        f"😌 Chill   — factual, minimal\n"
        f"🤨 Normal  — observational sass (default)\n"
        f"🔥 Brutal  — full personality, no chill"
    )
    await tg.send_with_buttons(msg, [
        [
            {"text": "😌 Chill", "callback_data": "mg_tone_chill"},
            {"text": "🤨 Normal", "callback_data": "mg_tone_normal"},
            {"text": "🔥 Brutal", "callback_data": "mg_tone_brutal"},
        ],
        [{"text": "← Back", "callback_data": "mg_back"}],
    ])


async def _set_tone(tone: str):
    state = sh.get_state(CHAT_ID) or {}
    sh.set_state(CHAT_ID, {**state, "tone": tone})
    await tg.send_text(f"✅ Tone set to *{tone}*")
```

Wire callbacks `mg_settings`, `mg_tone_*` vào `handle_manage_callback`.

---

### 8. `sheets.py` — thêm helpers

```python
def get_today_breakdown(tx_date: datetime) -> dict:
    """Tổng tx hôm nay + breakdown by category. KHÔNG filter theo bucket."""
    tz = pytz.timezone(TIMEZONE)
    if tx_date.tzinfo is None:
        tx_date = pytz.utc.localize(tx_date)
    local = tx_date.astimezone(tz)
    date_strs = [
        local.strftime("%Y-%m-%d"),
        local.strftime("%d/%m/%Y"),
    ]
    
    ws = _sheet(S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]
    
    total = 0
    count = 0
    by_cat: dict[str, dict] = {}
    
    for r in rows:
        if len(r) < 14: continue
        # Skip Tiền vào
        if len(r) > 6 and r[6] == "Tiền vào": continue
        # Date filter
        r_str = str(r[1])
        if not any(ds in r_str for ds in date_strs): continue
        
        amt = _parse_amount(r[7])
        cat_id = r[10] or "uncategorized"
        cat_name = bucket_label(cat_id) if cat_id != "uncategorized" else "(chưa phân loại)"
        
        total += amt
        count += 1
        if cat_id not in by_cat:
            by_cat[cat_id] = {"name": cat_name, "amount": 0, "count": 0}
        by_cat[cat_id]["amount"] += amt
        by_cat[cat_id]["count"] += 1
    
    by_category = sorted(by_cat.values(), key=lambda x: -x["amount"])
    return {"total": total, "count": count, "by_category": by_category}
```

---

## Implementation phases

### Phase 1: Voice restore (no data layer change) — ~2-3h

**Goal**: bot có character lại trong mọi message, KHÔNG động data/baseline logic.

| File | Change |
|---|---|
| `voice.py` (new) | Templates + `pick_tx_confirm_msg`, `pick_tx_received_msg`, `pick_welcome_msg`. Hardcode tone="normal" |
| `handlers/sepay.py` | Replace hardcoded msg với `voice.pick_*` |
| `handlers/transaction.py` | Same |
| `main.py` | Welcome msg dùng `voice.pick_welcome_msg` |

**Test**: send tx 50k, 200k, 500k, late night → confirm msg vary có voice, không robotic.

### Phase 2: Personal baseline + smart nag — ~3-4h

**Goal**: bot detect pattern, fire smart alert thay vì cứng `100k+`.

| File | Change |
|---|---|
| `baseline.py` (new) | `compute_baseline()`, `detect_anomalies()` |
| `handlers/transaction.py` | Wire baseline cache + signals vào `_finalize` |
| `voice.py` | Thêm templates cho `format_signal` (above_average, category_spike) |
| `handlers/reports.py` | `/today` dùng `get_today_breakdown` + baseline comparison |
| `sheets.py` | `get_today_breakdown()` |

**Test**: 
- Đặt 4 tx coffee trong tuần → tx thứ 4 fire "category_spike" alert
- Tiêu 1.5x daily avg → fire "above_average" alert
- User mới (< 7 days history) → skip alerts (chưa đủ data baseline)

### Phase 3: Tone settings — ~1-2h

**Goal**: user customize tone level.

| File | Change |
|---|---|
| `handlers/manage.py` | Settings menu, `mg_settings`, `mg_tone_*` callbacks |
| `voice.py` | Đảm bảo tất cả `pick_*` honor tone parameter |
| `main.py` | Read tone từ state, pass xuống handlers |

**Test**:
- Set chill → tx confirm msg ngắn, factual
- Set brutal → tx confirm msg dramatic
- Restart bot → tone persist (saved trong Bot State sheet)

### Phase 4: Insights expansion — DEFERRED riêng

**Out of scope cho plan này.** Sẽ tạo plan riêng (`PLAN_INSIGHTS.md`) khi Phase 1-3 đã ship và có data thực để fine-tune.

Ý tưởng để dành cho plan tương lai:
- Weekly: "Coffee tuần này = X tô phở"
- Monthly: "Bubble tea +40% vs 3 tháng trước"
- Anniversary: "Bạn đã track 100 ngày 🎉"
- Comparative: "Top 3 categories đốt 70% budget"

Lý do defer: cần real usage data từ Phase 1-3 để biết insight nào value, insight nào noise.

---

## Test cases tổng

### Voice (Phase 1)
- [ ] Tx 30k → small tier message
- [ ] Tx 200k → medium tier message
- [ ] Tx 600k → big tier message với tone phù hợp
- [ ] Tx lúc 1am → late_night template fire
- [ ] Welcome msg cho user mới có voice (không robotic)

### Baseline (Phase 2)
- [ ] User mới (< 7 days history) → `compute_baseline` trả `daily_avg = 0`, không fire alert
- [ ] Sau 7+ days → baseline ổn định, alert fire chính xác
- [ ] Cache hit: 2 tx liên tiếp trong 1h → không re-compute baseline (state cached)
- [ ] Cache invalidate: sang ngày mới → re-compute
- [ ] Coffee 4 tx trong tuần (avg 2/tuần) → tx thứ 4 fire spike alert
- [ ] Today spent 1.6x daily_avg → fire above_average alert
- [ ] Today spent 0.5x daily_avg → fire below_average (positive nudge)

### Daily cap (manual override)
- [ ] User KHÔNG set `daily_cap` → `/today` dùng baseline comparison
- [ ] User set `daily_cap=200k` qua `/manage` → `/today` show progress bar vs cap
- [ ] User clear `daily_cap` (set = 0 hoặc empty) → fallback về baseline mode
- [ ] Daily recap: có manual cap → recap theo cap. Không cap nhưng có baseline → recap theo baseline. Không có gì → skip recap

### Tone settings (Phase 3)
- [ ] Default tone = "normal" cho user mới
- [ ] Đổi tone qua `/manage` → ⚙️ Settings → tone mới apply ngay tx tiếp theo
- [ ] Tone persist qua restart (lưu trong Bot State)
- [ ] Brutal tone không đổi sang language hateful — vẫn caring underneath

### Edge cases
- [ ] Uncategorized tx hôm nay → vẫn count vào `get_today_breakdown` total
- [ ] Tracking-only category với daily_cap = None → bình thường, no alert hard cap
- [ ] User vừa migrate từ tracking-first commit → baseline_cache chưa có → compute lần đầu, sau đó hoạt động bình thường
- [ ] Sheet history lớn (10k+ rows) → `compute_baseline` nên có timeout / progressive loading nếu chậm

---

## Design decisions cần lưu ý

### 1. `daily_cap` là **optional manual override**, KHÔNG bị remove

- Default behavior: bot dùng personal baseline (smart, learn from user)
- User muốn cap cứng (vd: limit chi tiêu khẩn cấp khi đang tiết kiệm cho mục tiêu) → set `daily_cap` qua `/manage`
- Cap mode + baseline mode KHÔNG xung đột — cap mode override baseline khi cap được set
- Backward compat: user hiện đang có `daily_cap=100k` → vẫn hoạt động như cũ

### 2. Tone mặc định `normal`, KHÔNG `brutal`

User mới nên gặp friendly default, không bị shock. Brutal là opt-in cho ai thực sự cần nag mạnh.

### 3. Voice templates seed bằng tiếng Việt + minimal English

- Match audience (user Việt Nam)
- Tránh slang quá Mỹ ("GIRL", "spicy", "cooked") — neutral hơn
- Vẫn giữ flexibility để user customize sau

### 4. Baseline cache ở `Bot State`, KHÔNG ở Budget Config

- Bot State đã JSON, dễ thêm key
- Budget Config strict schema — không nên pollute với cache
- TTL: re-compute khi sang ngày mới hoặc mỗi 24h

### 5. Anomaly detection thresholds là constants, có thể tune

```python
ABOVE_AVG_THRESHOLD = 1.5      # 50% trên trung bình
CATEGORY_SPIKE_THRESHOLD = 1.5  # 50% trên freq trung bình
MIN_BASELINE_DAYS = 7           # cần ít nhất 7 ngày data
```

Future: cho user tune qua settings (advanced).

---

## So sánh với plan trước

| Khía cạnh | tracking-first commit | Plan này |
|---|---|---|
| Tone | Neutral, factual | Restore voice (configurable) |
| Daily cap | Vẫn còn nhưng không relevant lắm | Optional manual override (rõ ràng vai trò) |
| Daily nag | Skip nếu không cap | Smart nag dựa baseline |
| `/today` | Show monthly + cap progress | Tracking dashboard với category breakdown |
| User config | Không có | Tone setting + optional manual cap |
| Personality | Mất đáng kể | Restore + flexible |

---

## Decisions đã chốt

| # | Câu hỏi | Quyết định |
|---|---|---|
| 1 | Tone default | `normal` (observational sass) |
| 2 | Voice ngôn ngữ | Chủ yếu VN + accent English (vd: "small one", "noted", "addict?") |
| 3 | Baseline lookback | 14 ngày (adapt nhanh với lifestyle change) |
| 4 | Brutal tone guard rail | **Cấm chửi thẳng** — chỉ sass, observational, caring underneath. Không bao giờ xúc phạm trực diện. |
| 5 | Phase 4 priority | Defer riêng — chỉ làm Phase 1-3 trong scope plan này |

### Áp dụng cụ thể

**Phase 2 baseline**: `MIN_BASELINE_DAYS = 7`, `LOOKBACK_DAYS = 14`.

**Brutal tone guard rail** — concrete rules:
- ❌ Không: chửi tục, gọi user là "idiot", "stupid", "loser", attack character
- ❌ Không: body shame, mental health stigma, financial humiliation
- ✅ OK: dramatic reaction ("nửa triệu?!"), rhetorical question ("ngon hay quen?"), worry ("tôi lo cho ví bạn")
- ✅ OK: emoji 🫠 👀 🤨, accent EN ("girl what")
- Test mọi template brutal: đọc to → có khiến mình cười không, hay có khiến mình thấy tệ không? Lành mạnh nếu là cái đầu.

**Voice ngôn ngữ** — concrete style:
- Câu chính: tiếng Việt
- Accent: 1-2 từ EN ngắn cho rhythm ("noted", "small one", "addict?", "girl what")
- Tránh: full sentence English, slang Mỹ phức tạp ("you're cooked", "skating on thin ice")
- OK: brand names giữ nguyên ("Phúc Long", "Grab", "iPhone")
