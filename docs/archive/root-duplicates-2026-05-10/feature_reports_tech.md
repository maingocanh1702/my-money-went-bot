# BE Tech Doc: Reports (F05)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature_reports.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature_reports.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| Handler | `handlers/report.py` | `/status`, `/today`, `/weekly`, `/report`, `/export` |
| Service | `services/report_svc.py` | Aggregation queries, formatting |
| Export | `services/csv_export.py` | CSV generation |
| DB | `db.py` | Aggregation queries |

---

## 2. Database Schema

### 2.1. Key Queries

```sql
-- Monthly status (BUDGETED + TRACKING + INCOME)
SELECT c.id, c.name, c.allocated, c.daily_cap,
       COALESCE(SUM(CASE WHEN t.direction='out' THEN t.amount ELSE 0 END), 0) as spent_out,
       COALESCE(SUM(CASE WHEN t.direction='in' THEN t.amount ELSE 0 END), 0) as income_in
FROM categories c
LEFT JOIN transactions t ON t.category_id = c.id AND t.confirmed = TRUE
WHERE c.user_id = $1 AND c.month_key = $2 AND c.active = TRUE
GROUP BY c.id ORDER BY c.allocated DESC, c.created_at;

-- Today's spending
SELECT SUM(amount) as total, COUNT(*) as count
FROM transactions
WHERE user_id = $1 AND direction = 'out' AND confirmed = TRUE
  AND tx_date >= $2::date AND tx_date < ($2::date + INTERVAL '1 day');

-- Weekly breakdown (Pro+)
SELECT DATE(tx_date) as day, SUM(amount) as total
FROM transactions
WHERE user_id = $1 AND direction = 'out' AND confirmed = TRUE
  AND tx_date >= NOW() - INTERVAL '7 days'
GROUP BY DATE(tx_date) ORDER BY day;

-- Export CSV data
SELECT t.tx_date, t.description, t.direction, t.amount, c.name as category, s.label as sub_category
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
LEFT JOIN sub_categories s ON t.sub_category_id = s.id
WHERE t.user_id = $1 AND t.month_key = $2
ORDER BY t.tx_date;
```

### 2.2. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | 0 tx month | Empty state message |
| 2 | Cross-Feature | Free user /weekly | Reject + upgrade prompt |
| 3 | Data Integrity | Deleted category in report | Still show in report (tx FK intact) |
| 4 | Cross-Feature | Free user 30-day limit | WHERE tx_date > NOW() - 30 days |
| 5 | Data Integrity | Timezone boundary | Convert tx_date to user timezone |
| 6 | Concurrency | /status during tx process | Show committed data only |
| 7 | Data Integrity | Large amounts format | locale-aware formatting |
| 8 | Cross-Feature | Daily recap 0 tx | Skip sending |
| 9 | Data Integrity | CSV special chars | Proper CSV escaping |
| 10 | Cross-Feature | Messenger daily recap >24h | MESSAGE_TAG ACCOUNT_UPDATE |
| 10b | Cross-Feature | Discord daily recap | DM anytime (no window) |
| 11 | Data Integrity | Monthly report archive | Insert into monthly_reports |
| 12 | Data Integrity | Uncategorized tx in report | Show as "Chưa phân loại" |

---

## 3. API Contract

### 3.1. Commands (via webhook handler)

| Command | Tier | Query |
|---------|------|-------|
| `/status` | All | Monthly aggregation |
| `/today` | All | Today's spending |
| `/weekly` | Pro+ | 7-day breakdown |
| `/report` | Pro+ | Full monthly |
| `/export` | Pro+ | CSV file attachment |

---

## 4. Implementation Details

### 4.1. Progress Bar Generation

```python
def progress_bar(pct: int, width: int = 10) -> str:
    filled = min(int(pct / 100 * width), width)
    return '█' * filled + '░' * (width - filled)

def format_status_line(cat, spent):
    if cat.allocated > 0:
        pct = int(spent / cat.allocated * 100)
        emoji = '✅' if pct < 80 else '🟡' if pct < 100 else '🔴'
        remaining = max(0, cat.allocated - spent)
        bar = progress_bar(pct)
        return f"{emoji} {cat.name}  {bar} {pct}%  {fmt(spent)} / {fmt(cat.allocated)} · còn {fmt(remaining)}"
    else:
        return f"📊 {cat.name}  đã tiêu {fmt(spent)} tháng này"
```

### 4.2. Daily Recap Trigger

```python
async def fire_daily_recap(user_id: int):
    today_count = await db.count_today_tx(user_id)
    if today_count == 0:
        return  # Skip
    today_data = await db.get_today_summary(user_id)
    msg = format_daily_recap(today_data)
    await messenger.send(user_id, {"type": "text", "text": msg, "tag": "ACCOUNT_UPDATE"})
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | /status with data | 3 categories, txs | Formatted report |
| 2 | /status empty | 0 tx | Empty state message |
| 3 | /today with data | 3 tx today | Sum + count |
| 4 | /today no data | 0 tx | "Chưa có giao dịch hôm nay" |
| 5 | /weekly Pro | Pro user | 7-day breakdown |
| 6 | /weekly Free | Free user | Upgrade prompt |
| 7 | /export Pro | Pro user, 50 tx | CSV file sent |
| 8 | /export Free | Free user | Upgrade prompt |
| 9 | Progress bar 0% | spent=0, alloc=1M | "░░░░░░░░░░" |
| 10 | Progress bar 50% | spent=500k, alloc=1M | "█████░░░░░" |
| 11 | Progress bar 100% | spent=1M, alloc=1M | "██████████" |
| 12 | Progress bar 150% | spent=1.5M, alloc=1M | "██████████" capped |
| 13 | BUDGETED section | allocated > 0 | Shows progress |
| 14 | TRACKING section | allocated = 0 | Shows total only |
| 15 | INCOME section | direction = 'in' | Shows income |
| 16 | Daily recap fire | ≥1 tx | Message sent |
| 17 | Daily recap skip | 0 tx | Not sent |
| 18 | Daily recap MESSAGE_TAG | Messenger user | tag=ACCOUNT_UPDATE |
| 18b | Daily recap Discord | Discord user | DM sent (no tag needed) |
| 19 | CSV escaping | Description with commas | Properly escaped |
| 20 | Timezone boundary | tx at 23:59 local | Correct day assignment |
| 21 | Free 30-day limit | tx 45 days ago | Not included |
| 22 | Deleted category | Cat deleted, tx exists | Shows "Deleted" label |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc |
