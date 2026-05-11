# Plan: Fix Duplicate Transaction

## Vấn đề

Cùng 1 giao dịch có thể được track 2 lần nếu cả SePay và email đều active cho cùng 1 tài khoản (vd: Cake).

**Ví dụ:**
```
Cake giao dịch 45.000đ lúc 12:34:00
  → SePay nhận realtime (12:34:01) → ghi vào Sheets → referenceCode: "SP-ABC123"
  → Email Cake đến (12:34:45) → Apps Script xử lý → ghi vào Sheets → referenceCode: "a1b2c3d4e5f6g7h8" (MD5)
```

Kết quả: 1 giao dịch thật nhưng xuất hiện 2 lần trong Sheets → sai số liệu budget.

## Root Cause

Dedup hiện tại dựa vào `referenceCode` duy nhất — nhưng SePay và email parser tạo ra 2 ref code hoàn toàn khác nhau cho cùng 1 giao dịch:
- SePay: ref code từ ngân hàng hoặc SePay tự sinh
- Email: MD5 hash của `amount|description|date`

→ Hai giá trị không bao giờ khớp → dedup không có tác dụng.

---

## Giải pháp: Fuzzy Dedup theo (amount + type + time window)

Trước khi ghi transaction mới vào Sheets, kiểm tra N rows gần nhất. Nếu đã có giao dịch nào có:
- `transferAmount` giống nhau (exact match)
- `transferType` giống nhau (`in` / `out`)
- `transactionDate` cách nhau **< 180 giây**

→ Coi là duplicate, **skip ghi Sheets** nhưng **vẫn gửi Telegram** nếu là lần đầu nhận.

---

## Các thay đổi cần làm

### 1. `sheets.py` — thêm `find_recent_duplicate()`

**⚠️ Column mapping thực tế của sheet `Đầu ra`:**

| Index | Cột | Nội dung |
|-------|-----|----------|
| 0 | A | ID |
| 1 | B | Ngày giao dịch |
| 5 | F | Nội dung |
| 6 | G | Loại (`Tiền ra` / `Tiền vào`) |
| 7 | H | Số tiền |
| 8 | I | Mã tham chiếu |

```python
from datetime import datetime, timezone
import pytz

DEDUP_WINDOW_SEC = 180  # 3 phút
DEDUP_LOOKBACK_ROWS = 50  # đọc 50 rows gần nhất để check

# Normalize tx_type về dạng so sánh được
_TYPE_MAP = {
    "in": "tiền vào", "credit": "tiền vào", "tiền vào": "tiền vào",
    "out": "tiền ra", "debit": "tiền ra", "tiền ra": "tiền ra",
}

def _normalize_type(tx_type: str) -> str:
    return _TYPE_MAP.get(tx_type.strip().lower(), tx_type.strip().lower())

def find_recent_duplicate(amount: float, tx_type: str, tx_date: str) -> bool:
    """
    Kiểm tra xem đã có giao dịch tương tự trong DEDUP_WINDOW_SEC giây gần nhất chưa.
    Trả về True nếu là duplicate → nên skip ghi Sheets.
    """
    try:
        ws = _get_spreadsheet().worksheet(SHEETS.TRANSACTIONS)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return False

        # Parse incoming date
        new_dt = _parse_dt(tx_date)
        if new_dt is None:
            return False

        normalized_type = _normalize_type(tx_type)

        # Chỉ check N rows gần nhất (tránh đọc hết sheet)
        data_rows = rows[1:]  # bỏ header
        recent_rows = data_rows[-DEDUP_LOOKBACK_ROWS:]

        for row in recent_rows:
            try:
                # ⚠️ Column indices khớp với append_transaction():
                # row[1] = B: Ngày GD, row[6] = G: Loại, row[7] = H: Số tiền
                row_date   = _parse_dt(str(row[1]))
                row_type   = _normalize_type(str(row[6]))
                row_amount = float(str(row[7]).replace(",", "").replace(".", ""))

                if row_date is None:
                    continue

                amount_match = abs(row_amount - amount) < 1  # tolerance 1đ
                type_match   = row_type == normalized_type
                time_diff    = abs((new_dt - row_date).total_seconds())
                time_match   = time_diff < DEDUP_WINDOW_SEC

                if amount_match and type_match and time_match:
                    print(f"[dedup] found duplicate: amount={amount} type={tx_type} "
                          f"diff={time_diff:.0f}s")
                    return True
            except (ValueError, IndexError):
                continue

        return False

    except Exception as e:
        print(f"[dedup] error checking duplicate: {e}")
        return False  # fail open — thà ghi trùng còn hơn miss giao dịch


def _parse_dt(date_str: str):
    """Parse ISO hoặc DD/MM/YYYY HH:MM:SS thành datetime aware."""
    if not date_str:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",      # ISO with timezone
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip()[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None
```

---

### 2. `handlers/sepay.py` — gọi dedup check trước khi ghi

**⚠️ Vị trí quan trọng:** đặt dedup check **1 lần duy nhất** ngay sau staleness guard, **trước** cả 2 nhánh `INCOMING` và `OUTGOING`. Không đặt trong mỗi nhánh riêng.

```python
# ── Trong sepay.py, ngay sau staleness guard, TRƯỚC nhánh incoming/outgoing ──

    month_key = sh.fmt_month(tx_date)

    # Fuzzy dedup: chặn duplicate giữa SePay + email sources
    tx_type_label = "Tiền vào" if is_incoming else "Tiền ra"
    if sh.find_recent_duplicate(amount, tx_type_label, raw_date):
        print(f"[dedup] skipped duplicate: {amount} {tx_type_label} ref={ref_code!r}")
        return

    # ─── INCOMING (Tiền vào) ──────────────────────────────────
    if is_incoming:
        ...
    # ─── OUTGOING (Tiền ra) ───────────────────────────────────
    else:
        ...
```

**Lý do:** Cả 2 nhánh đều gọi `sh.append_transaction()`. Nếu đặt dedup trong mỗi nhánh → phải viết 2 lần, dễ quên 1 bên.

---

### 3. `sheets.py` — thêm cột `source` vào Transactions sheet

Thêm field `_source` vào mỗi row khi ghi:
- `"sepay"` — từ SePay webhook
- `"email_tcb"` — từ email Techcombank
- `"email_cake"` — từ email Cake

Giúp audit sau này (biết giao dịch nào đến từ nguồn nào).

---

## Edge Cases

| # | Case | Hành vi |
|---|------|---------|
| 1 | 2 giao dịch cùng amount trong 3 phút | False positive — giao dịch thứ 2 bị skip. Giảm window xuống 60s nếu cần. |
| 2 | Email đến trước SePay | SePay bị coi là duplicate → skip. Vẫn đúng vì email đã ghi rồi. |
| 3 | SePay timeout, chỉ có email | Email ghi bình thường, không bị ảnh hưởng. |
| 4 | Bot restart giữa chừng | Dedup đọc từ Sheets nên vẫn hoạt động đúng sau restart. |
| 5 | Giao dịch lớn cùng amount khác ngày | `time_match = False` → ghi bình thường, không bị nhầm. |
| 6 | Type format mismatch (`in` vs `Tiền vào`) | `_normalize_type()` chuẩn hóa cả 2 format trước khi compare. |
| 7 | Sheet amount có separator (`.` hoặc `,`) | `replace(",", "").replace(".", "")` xóa hết separator trước parse. |

---

## Time Window khuyến nghị

| Window | Ưu điểm | Nhược điểm |
|--------|---------|-----------|
| **60s** | Ít false positive | Có thể miss nếu email delay > 1 phút |
| **180s (recommended)** | An toàn cho hầu hết trường hợp | False positive nếu chi 2 lần cùng amount trong 3 phút |
| **300s** | Rất an toàn | Dễ false positive hơn |

→ Bắt đầu với **180s**, giảm xuống 60s nếu gặp false positive trong thực tế.

---

## Fail-safe

`find_recent_duplicate()` luôn return `False` nếu có exception → **thà ghi trùng còn hơn miss giao dịch**. Duplicate có thể xóa thủ công, nhưng giao dịch bị miss thì không biết.

---

## Thứ tự implement

1. Thêm `find_recent_duplicate()` + `_parse_dt()` vào `sheets.py`
2. Cập nhật `handlers/sepay.py` — gọi dedup check
3. (Optional) Thêm cột `source` vào Transactions sheet
4. Test với `testWithRecentEmails()` trong Apps Script — verify không có row trùng trong Sheets
