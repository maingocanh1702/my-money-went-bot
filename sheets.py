import asyncio
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timezone
import pytz
from config import SHEET_ID, CREDS_FILE, GOOGLE_CREDS_JSON, TIMEZONE, DAILY_BUCKET_ID
from config import SHEETS as S

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_gc = None
_ss = None
_buckets_cache: dict = {}   # month_key -> list[dict]

# Short-lived cache cho rows của Transactions sheet — tránh đọc sheet 5-10
# lần trong cùng 1 request (vd /status gọi get_bucket_status cho mỗi bucket).
# TTL 30s đủ cho 1 user session, không bị stale lâu.
_tx_rows_cache: dict = {"ts": 0.0, "rows": None}
_TX_CACHE_TTL = 30.0  # seconds


def _get_tx_rows(force_refresh: bool = False) -> list:
    """Đọc tất cả row của Transactions sheet với cache TTL ngắn.
    Dùng thay cho `_sheet(S.TRANSACTIONS).get_all_values()[1:]` ở những chỗ
    cần đọc nhiều lần liên tiếp.
    """
    import time
    now = time.time()
    if (not force_refresh
            and _tx_rows_cache["rows"] is not None
            and now - _tx_rows_cache["ts"] < _TX_CACHE_TTL):
        return _tx_rows_cache["rows"]
    ws = _sheet(S.TRANSACTIONS)
    rows = ws.get_all_values()[1:]  # skip header
    _tx_rows_cache["rows"] = rows
    _tx_rows_cache["ts"] = now
    return rows


def _invalidate_tx_rows_cache():
    """Gọi sau mỗi append/update để cache không stale quá lâu."""
    _tx_rows_cache["rows"] = None
    _tx_rows_cache["ts"] = 0.0

# Shared lock cho auto-bootstrap default categories.
# Dùng chung giữa sepay.py + manage.py để chặn race khi 2 worker cùng thấy
# `not buckets` và cả 2 đều thử seed defaults.
bootstrap_lock = asyncio.Lock()

# Lock cho append_transaction — chặn 2 webhook concurrent ghi đè cùng row.
# Threading lock because append_transaction is sync (called from async context
# but the GIL can release during the blocking gspread I/O, allowing another
# thread to interleave).
import threading
# same thread. A plain Lock would self-deadlock there; RLock keeps cross-thread
# serialization (concurrent webhooks block) while allowing the re-entry.
tx_write_lock = threading.RLock()


def _get_spreadsheet():
    global _gc, _ss
    if _ss is None:
        # Railway/cloud: dùng JSON string từ env var
        # Local: đọc từ file credentials.json
        if GOOGLE_CREDS_JSON:
            info  = json.loads(GOOGLE_CREDS_JSON)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        _gc = gspread.authorize(creds)
        _ss = _gc.open_by_key(SHEET_ID)
    return _ss


def _sheet(name: str):
    return _get_spreadsheet().worksheet(name)


# ─── Formatting helpers ───────────────────────────────────────
def fmt_month(dt: datetime) -> str:
    tz = pytz.timezone(TIMEZONE)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    local = dt.astimezone(tz)
    return local.strftime("%Y-%m")


def fmt_amount(n, currency: str = "VND") -> str:
    """Format amount for display. VND không có decimal; foreign currencies giữ 2 chữ số.

    Examples:
      fmt_amount(50000)           → "50.000đ"
      fmt_amount(300, "HKD")      → "HKD 300.00"
      fmt_amount(50000, "VND")    → "50.000đ"
    """
    cur = (currency or "VND").upper().strip() or "VND"
    if cur == "VND":
        n = int(round(float(n or 0)))
        return f"{n:,}đ".replace(",", ".")
    # Foreign: show 2 decimals + ISO code
    val = float(n or 0)
    return f"{cur} {val:,.2f}"


def _next_row(ws, col: int = 1) -> int:
    """Find the next empty row by checking the given column (1-indexed).
    col_values stops at the last non-empty cell, so len() + 1 = next row.
    """
    return len(ws.col_values(col)) + 1


def _auto_expand(ws, needed_row: int, batch_size: int = 1000) -> None:
    """Expand worksheet if `needed_row` exceeds current row_count.

    Adds `batch_size` rows at a time so we don't hit this again soon.
    Google Sheets max is 10,000,000 cells — at 13 cols that's ~769k rows,
    so expanding by 1000 at a time is safe for years of ledger data.
    """
    current = ws.row_count
    if needed_row <= current:
        return
    new_count = current + max(batch_size, needed_row - current)
    ws.resize(rows=new_count)
    print(f"[sheets] auto-expanded {ws.title!r}: {current} → {new_count} rows")


def _last_col_letter(n: int) -> str:
    """1-based column count → A1 column letter (1→"A", 26→"Z", 27→"AA").

    Used to build header ranges dynamically so adding columns to a *_HEADER
    never truncates the written range (the `A1:O1` bug). Mirrors the
    _col_letter_to_idx logic in tests/conftest.py, inverted.
    """
    if n < 1:
        raise ValueError(f"_last_col_letter: n must be >= 1, got {n}")
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def row_currency(row: list) -> str:
    """Read column P (index 15) safely. Backfill 'VND' for legacy rows.

    Used by aggregations to filter out foreign-currency rows so HKD doesn't
    get summed into VND totals.
    """
    if len(row) > 15 and row[15]:
        return str(row[15]).upper().strip() or "VND"
    return "VND"


def _parse_amount(val) -> float:
    """Parse a sheet cell amount value safely.
    Handles: "50000", "50,000", "50.000" (VN), "50000.0" (float repr).
    VND has no decimal places so we round to int.
    """
    s = str(val).strip()
    if not s:
        return 0.0
    # If it looks like a plain float already (no thousands separator style)
    # e.g. "50000.0" — just parse directly
    try:
        return float(s)
    except ValueError:
        pass
    # Remove thousands separators (commas or dots used as thousand sep)
    # Determine separator style: if there's both , and ., the last one is decimal
    if "," in s and "." in s:
        # e.g. "50,000.00" → decimal is "."
        s = s.replace(",", "")
    elif "," in s:
        # e.g. "50,000" → comma is thousands sep
        s = s.replace(",", "")
    elif "." in s and s.count(".") == 1:
        # Could be decimal "50000.0" or thousands "50.000"
        # For VND: if digits after dot < 3, treat as decimal; else thousands
        parts = s.split(".")
        if len(parts[1]) == 3:
            s = s.replace(".", "")  # thousands separator
        # else leave as-is (decimal)
    return float(s) if s else 0.0


def calc_pct(spent: float, total: float) -> int:
    """Integer percentage; shows at least 1% when there is any spending."""
    if not total:
        return 0
    pct = int(spent / total * 100)
    if pct == 0 and spent > 0:
        pct = 1
    return min(pct, 100)


def make_bar(pct: int, length: int = 10) -> str:
    filled = round(min(pct, 100) / (100 / length))
    return "█" * filled + "░" * (length - filled)


def days_left_in_month() -> int:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    last = date(now.year, now.month + 1, 1) if now.month < 12 else date(now.year + 1, 1, 1)
    return (last - now.date()).days


# ─── Bucket helpers ───────────────────────────────────────────
def get_active_buckets(month_key: str, force_refresh: bool = False) -> list[dict]:
    global _buckets_cache
    if not force_refresh and month_key in _buckets_cache:
        return _buckets_cache[month_key]
    ws = _sheet(S.BUDGET_CONFIG)
    rows = ws.get_all_values()[1:]  # skip header
    result = []
    for r in rows:
        if len(r) < 6:
            continue
        if r[0] == month_key and str(r[5]).upper() == "TRUE":
            result.append({
                "id":        r[1],
                "name":      r[2],
                "allocated": _parse_amount(r[3]),
                "daily_cap": _parse_amount(r[4]) or None,
            })
    _buckets_cache[month_key] = result
    return result


def invalidate_buckets_cache():
    global _buckets_cache
    _buckets_cache = {}


def get_bucket_status(bucket_id: str, month_key: str) -> dict:
    """Sum outgoing spent for a bucket. VND-only — foreign-currency transactions
    are tracked in `foreign` (dict keyed by currency code) so callers can
    optionally show them on a separate line.
    """
    buckets = get_active_buckets(month_key)
    bkt = next((b for b in buckets if b["id"] == bucket_id), None)
    alloc = bkt["allocated"] if bkt else 0

    rows = _get_tx_rows()
    spent = 0
    foreign: dict[str, float] = {}
    for r in rows:
        if len(r) < 15:
            continue
        if r[14] != month_key:
            continue
        if r[10] != bucket_id:
            continue
        if str(r[13]).upper() != "TRUE":
            continue
        # Only count outgoing transactions as "spent"
        if len(r) > 6 and r[6] == "Tiền vào":
            continue
        cur = row_currency(r)
        amt = _parse_amount(r[7])
        if cur == "VND":
            spent += amt
        else:
            foreign[cur] = foreign.get(cur, 0.0) + amt
    return {
        "spent": spent,
        "allocated": alloc,
        "remaining": alloc - spent,
        "foreign": foreign,
    }


def get_income_total(bucket_id: str, month_key: str) -> float:
    """Tổng tiền vào (Tiền vào) của bucket trong tháng — VND only.
    Foreign-currency income không cộng vào (báo cáo show riêng nếu cần)."""
    rows = _get_tx_rows()
    income = 0
    for r in rows:
        if len(r) < 15:
            continue
        if r[14] != month_key:
            continue
        if r[10] != bucket_id:
            continue
        if str(r[13]).upper() != "TRUE":
            continue
        # Chỉ tính incoming
        if len(r) > 6 and r[6] != "Tiền vào":
            continue
        if row_currency(r) != "VND":
            continue  # foreign income — skip để tránh sum sai
        income += _parse_amount(r[7])
    return income


def get_daily_status(tx_date: datetime) -> dict:
    tz = pytz.timezone(TIMEZONE)
    if tx_date.tzinfo is None:
        tx_date = pytz.utc.localize(tx_date)
    local = tx_date.astimezone(tz)
    date_str_1 = local.strftime("%Y-%m-%d")
    date_str_2 = local.strftime("%d/%m/%Y")
    date_str_3 = local.strftime("%m/%d/%Y")
    
    month_key = local.strftime("%Y-%m")
    
    buckets = get_active_buckets(month_key)
    bkt = next((b for b in buckets if b["id"] == DAILY_BUCKET_ID), None)
    cap = bkt["daily_cap"] if (bkt and bkt["daily_cap"]) else 100000

    rows = _get_tx_rows()
    spent = 0
    for r in rows:
        if len(r) < 14 or str(r[13]).upper() != "TRUE":
            continue
        if r[10] != DAILY_BUCKET_ID:
            continue
        # Only count outgoing transactions as "spent"
        if len(r) > 6 and r[6] == "Tiền vào":
            continue
        # Daily cap = VND only — foreign tx (HKD…) không tính vào daily limit
        if row_currency(r) != "VND":
            continue
        r_str = str(r[1])
        if date_str_1 in r_str or date_str_2 in r_str or date_str_3 in r_str:
            # NOTE: no row logging here — descriptions can carry PII
            # (partner names, account numbers) and this runs per request.
            spent += _parse_amount(r[7])
    
    remaining = cap - spent
    return {
        "spent": spent,
        "cap": cap,
        "remaining": remaining
    }


def get_recent_transactions(limit: int = 10, month_key: str = None,
                            only_uncategorized: bool = False) -> list[dict]:
    """Recent outgoing transactions for the /recat picker.

    Returns: [{"row_num", "amount", "description", "bucket_id",
               "bucket_name", "date", "currency", "is_finalized"}, ...]
    Most recent first. Transfers/cc payments are excluded (own ledger).
    """
    tz = pytz.timezone(TIMEZONE)
    if not month_key:
        month_key = fmt_month(datetime.now(tz))

    rows = _get_tx_rows()
    results: list[dict] = []

    for idx, r in enumerate(rows):
        if len(r) < 8:
            continue
        # Only the requested month
        if len(r) > 14 and r[14] and r[14] != month_key:
            continue
        # Only outgoing
        if len(r) > 6 and r[6] == "Tiền vào":
            continue
        # Skip transfer/cc_payment — recategorizing them corrupts the ledger
        if len(r) > 17 and str(r[17]).strip().lower() in ("transfer", "cc_payment"):
            continue

        row_num = idx + 2
        is_finalized = len(r) > 13 and str(r[13]).upper() == "TRUE"
        bucket_id = r[10] if len(r) > 10 else ""

        if only_uncategorized and (is_finalized and bucket_id):
            continue

        amt = _parse_amount(r[7])
        cur = row_currency(r)
        results.append({
            "row_num": row_num,
            "amount": int(amt) if cur == "VND" else float(amt),
            "description": r[5] if len(r) > 5 else "",
            "bucket_id": bucket_id,
            "bucket_name": bucket_label(bucket_id) if bucket_id else "",
            "date": r[1] if len(r) > 1 else "",
            "currency": cur,
            "is_finalized": is_finalized,
        })

    results.sort(key=lambda x: x["row_num"], reverse=True)
    return results[:limit]


def get_frequent_categories(n: int = 3) -> list[str]:
    """Top-N most frequently used category bucket IDs from finalized tx.

    Counts col K (parent_category) of confirmed outgoing transactions.
    Returns up to `n` bucket IDs sorted by descending frequency.
    """
    rows = _get_tx_rows()
    counts: dict[str, int] = {}
    for r in rows:
        if len(r) < 14 or str(r[13]).upper() != "TRUE":
            continue
        # Only outgoing
        if len(r) > 6 and r[6] == "Tiền vào":
            continue
        cat = (r[10] or "").strip()
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    # Sort by frequency descending, return top n
    return [k for k, _ in sorted(counts.items(), key=lambda x: -x[1])[:n]]

def get_sub_categories(bucket_id: str) -> list[dict]:
    ws = _sheet(S.SUBCATEGORY)
    rows = ws.get_all_values()[1:]
    res = []
    for r in rows:
        if len(r) >= 4 and r[0] == bucket_id and str(r[3]).upper() == "TRUE":
            res.append({"key": r[1], "label": r[2]})
    return res


def get_sub_label(bucket_id: str, key: str) -> str:
    subs = get_sub_categories(bucket_id)
    found = next((s for s in subs if s["key"] == key), None)
    return found["label"] if found else key


def bucket_label(bucket_id: str) -> str:
    tz = pytz.timezone(TIMEZONE)
    month_key = datetime.now(tz).strftime("%Y-%m")
    buckets = get_active_buckets(month_key)
    found = next((b for b in buckets if b["id"] == bucket_id), None)
    return found["name"] if found else bucket_id


def get_parent_from_sheet(row_num: int) -> str:
    ws = _sheet(S.TRANSACTIONS)
    return ws.cell(row_num, 11).value or ""


def save_custom_sub(bucket_id: str, label: str):
    import unicodedata, re
    # normalize key
    key = unicodedata.normalize("NFD", label.lower())
    key = re.sub(r"[\u0300-\u036f]", "", key)
    key = re.sub(r"[^a-z0-9_]", "", key)
    
    ws = _sheet(S.SUBCATEGORY)
    rows = ws.get_all_values()[1:]
    for r in rows:
        if len(r) >= 2 and r[0] == bucket_id and r[1] == key:
            return  # already exists
    next_row = _next_row(ws, col=1)
    ws.update(f"A{next_row}:D{next_row}", [[bucket_id, key, f"📦 {label}", "TRUE"]])


def find_budget_row(month_key: str, bucket_id: str) -> bool:
    ws = _sheet(S.BUDGET_CONFIG)
    rows = ws.get_all_values()[1:]
    for r in rows:
        if len(r) >= 2 and r[0] == month_key and r[1] == bucket_id:
            return True
    return False


def get_default_buckets() -> list[dict]:
    """Seed list for first-time users. Saving intentionally excluded:
    Phase 1 of the project tracks *spending*, and moving money into a
    savings account is a transfer, not an expense. Users who want to
    track saving as a budget line can add it via /manage.
    """
    return [
        {"id": "daily_spending",   "name": "🛒 Daily Spending",   "daily_cap": 100000},
        {"id": "subscription",     "name": "📱 Subscription",      "daily_cap": None},
    ]


def _default_tombstoned(bucket_id: str, rows: list) -> bool:
    """True nếu user đã CỐ Ý xoá default này và chưa thêm lại.

    Tombstone cross-month: nhìn vào row Budget Config mới nhất (theo month_key)
    của `bucket_id` trên TẤT CẢ các tháng. Nếu trạng thái mới nhất là inactive
    (Active=FALSE) → coi như user đã xoá → KHÔNG re-seed ở tháng mới.

    month_key dạng "YYYY-MM" nên so sánh chuỗi = so sánh thời gian.

    Quy tắc:
      - chưa có row nào          → False (lần đầu, cứ seed)
      - row mới nhất Active=TRUE  → False (user vẫn dùng / đã thêm lại)
      - row mới nhất Active=FALSE → True  (đã xoá, tôn trọng ý định)
    """
    latest_month = None
    latest_active = None
    for r in rows:
        if len(r) >= 6 and r[1] == bucket_id:
            mk = r[0]
            if latest_month is None or mk > latest_month:
                latest_month = mk
                latest_active = str(r[5]).upper() == "TRUE"
    return latest_active is False


def bootstrap_default_categories(month_key: str) -> int:
    """Seed default tracking categories cho month_key nếu chưa có.

    Idempotent: chỉ tạo những bucket chưa tồn tại trong Budget Config.
    Trả về số category được tạo mới (0 nếu đã có sẵn).

    Tombstone: KHÔNG re-seed default mà user đã cố ý xoá (xem
    `_default_tombstoned`). Tránh việc category bị xoá "sống lại" khi một
    tháng mới rơi vào nhánh default-seed (vd tháng trước rỗng nên không clone
    được). Nhánh clone (`bootstrap_buckets_from_previous_month`) vốn đã lọc
    Active=FALSE nên không cần tombstone riêng.

    `allocated=0` → tracking mode. `daily_cap` giữ nguyên từ default
    (daily_spending: 100k để /today + daily recap chạy ngay cho user mới;
    còn lại: None vì không có khái niệm daily limit).

    Caller cần wrap trong `bootstrap_lock` để chống race trong cùng process.
    """
    ws = _sheet(S.BUDGET_CONFIG)
    rows = ws.get_all_values()[1:]  # skip header — đọc 1 lần, dùng cho cả 2 check
    created = 0
    for b in get_default_buckets():
        # Đã có row cho bucket này trong CHÍNH tháng đó (kể cả FALSE)? → skip.
        in_month = any(
            len(r) >= 2 and r[0] == month_key and r[1] == b["id"] for r in rows
        )
        if in_month:
            continue
        # User đã cố ý xoá default này ở tháng trước? → tôn trọng, đừng dựng lại.
        if _default_tombstoned(b["id"], rows):
            continue
        write_budget_row(month_key, {**b, "allocated": 0})
        created += 1
    if created > 0:
        invalidate_buckets_cache()
    return created


def _previous_month_key(month_key: str) -> str | None:
    try:
        year_s, month_s = month_key.split("-", 1)
        year, month = int(year_s), int(month_s)
    except Exception:
        return None
    if not 1 <= month <= 12:
        return None
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def bootstrap_buckets_from_previous_month(month_key: str, *, reset_allocated: bool = False) -> int:
    """Clone active buckets from the previous month into an empty new month.

    Category/keyword continuity depends on stable bucket ids. When a new month
    starts, preserving ids like "food" and "coffee" keeps existing keyword
    rules working. Allocations and daily caps are copied too by default;
    explicit track-only flows can pass reset_allocated=True.
    """
    prev_key = _previous_month_key(month_key)
    if not prev_key:
        return 0

    prev_buckets = get_active_buckets(prev_key, force_refresh=True)
    if not prev_buckets:
        return 0

    created = 0
    for b in prev_buckets:
        if not find_budget_row(month_key, b["id"]):
            bucket = {**b, "allocated": 0} if reset_allocated else b
            write_budget_row(month_key, bucket)
            created += 1
    if created > 0:
        invalidate_buckets_cache()
    return created


# -----------------------------------------------------
# Fuzzy Dedup (cross-source: SePay + email)
# -----------------------------------------------------
DEDUP_WINDOW_SEC   = 180   # 3 phút
DEDUP_LOOKBACK_ROWS = 50   # chỉ đọc 50 rows gần nhất

_TYPE_MAP = {
    "in":      "tiền vào", "credit":  "tiền vào", "tiền vào": "tiền vào",
    "out":     "tiền ra",  "debit":   "tiền ra",  "tiền ra":  "tiền ra",
}

def _normalize_type(tx_type: str) -> str:
    return _TYPE_MAP.get(tx_type.strip().lower(), tx_type.strip().lower())


def _parse_dt(date_str: str):
    """Parse ISO hoặc DD/MM/YYYY HH:MM:SS → datetime timezone-aware (UTC)."""
    if not date_str:
        return None
    s = date_str.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            dt = datetime.strptime(s[:26], fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def find_recent_duplicate(amount: float, tx_type: str, tx_date: str, currency: str = "VND") -> bool:
    """
    Trả về True nếu đã có giao dịch cùng amount + type + currency trong
    DEDUP_WINDOW_SEC giây. Currency check tránh false-dedup giữa HKD và VND
    có cùng số (vd HKD 300 vs VND 300 — unlikely nhưng có thể).
    Fail-open: trả về False nếu có exception (thà ghi trùng còn hơn miss GD).
    """
    try:
        rows = _get_tx_rows()
        if not rows:
            return False

        new_dt = _parse_dt(str(tx_date))
        if new_dt is None:
            return False

        norm_type = _normalize_type(tx_type)
        new_cur = (currency or "VND").upper().strip() or "VND"

        for row in rows[-DEDUP_LOOKBACK_ROWS:]:
            try:
                # B=row[1]: Ngày GD | G=row[6]: Loại | H=row[7]: Số tiền | P=row[15]: Currency
                row_dt     = _parse_dt(str(row[1]))
                row_type   = _normalize_type(str(row[6]))
                row_amount = _parse_amount(row[7])
                row_cur    = row_currency(row)

                if row_dt is None:
                    continue

                if (
                    abs(row_amount - amount) < 1
                    and row_type == norm_type
                    and row_cur == new_cur
                    and abs((new_dt - row_dt).total_seconds()) < DEDUP_WINDOW_SEC
                ):
                    print(f"[dedup] duplicate found: amount={amount} {new_cur} type={tx_type} "
                          f"diff={abs((new_dt - row_dt).total_seconds()):.0f}s")
                    return True
            except (ValueError, IndexError):
                continue

        return False

    except Exception as e:
        print(f"[dedup] check error (fail-open): {e}")
        return False


# -----------------------------------------------------
# Transaction Write
# -----------------------------------------------------
_processed_refs: dict[str, float] = {}  # ref_code → timestamp

def tx_exists(ref_code: str) -> bool:
    """Dedup transaction by ref_code.

    Layered check:
    1. In-memory cache (5-min TTL) — fast path cho SePay retry burst
    2. Sheet lookup — bắt cả case re-process email cũ (vd Apps Script
       bootstrap re-trigger), dùng cột I trong "Đầu ra"

    Trả về True nếu ref_code đã tồn tại → caller sẽ skip ghi.
    Fail-open: nếu sheet không đọc được, fallback về cache only.
    """
    import time
    now = time.time()
    # Prune entries older than 5 minutes
    expired = [k for k, v in _processed_refs.items() if now - v > 300]
    for k in expired:
        del _processed_refs[k]

    # Layer 1: in-memory cache
    if ref_code in _processed_refs:
        return True

    # Layer 2: sheet lookup — cột I (index 8 = position 9 in 1-based)
    if _ref_in_sheet(ref_code):
        # Cache để lần sau nhanh hơn
        _processed_refs[ref_code] = now
        return True

    _processed_refs[ref_code] = now
    return False


def _ref_in_sheet(ref_code: str) -> bool:
    """Check if ref_code exists in column I of "Đầu ra" sheet.
    Dùng cache TTL 30s để tránh đọc sheet nhiều lần khi xử lý burst email.
    Fail-open: trả False nếu có exception (thà ghi trùng còn hơn miss GD)."""
    if not ref_code:
        return False
    try:
        rows = _get_tx_rows()
        # col I = index 8 (0-based) trong row
        for r in rows:
            if len(r) > 8 and r[8] == ref_code:
                return True
        return False
    except Exception as e:
        print(f"[tx_exists] sheet lookup error (fail-open): {e}")
        return False


def append_transaction(
    tx_date,
    description,
    amount,
    ref_code,
    month_key,
    tx_type: str = "Tiền ra",
    currency: str = "VND",
    account_id: str = "",
    ledger_tx_type: str = "expense",
    linked_tx_row: int | str = "",
    account_source_key: str = "",
) -> int:
    """Append a new transaction row.

    Schema A–P (legacy, do not reorder):
      A=ID, B=Date, C/D/E=blank, F=Description, G=Type ("Tiền ra"/"Tiền vào"),
      H=Amount, I=Ref, J=Cumulative, K=ParentCat, L=SubCat, M=IsDaily,
      N=Confirmed, O=Month, P=Currency.

    Schema Q–U (Account Tracking, append-only, all default to safe legacy
    values so existing call-sites stay backward-compatible):
      Q=account_id          — Accounts.id, "" if not yet resolved.
      R=ledger_tx_type      — `expense | income | transfer | cc_payment`
                              (default: derived from G — "income" if Tiền vào,
                              else "expense").
      S=linked_tx_row       — paired Transactions row for transfer/cc_payment.
      T=ledger_applied      — "TRUE" once a ledger entry exists for this row.
                              Defaults to "FALSE".
      U=account_source_key  — raw source_key from webhook resolver, e.g.
                              "sepay:1903999888" or "email_cake:cake_cc".
                              Populated even when account_id is empty so we
                              can backfill account_id later when the user
                              onboards the corresponding account.
                              "" for legacy rows / cases without a source.
    """
    cur = (currency or "VND").upper().strip() or "VND"

    # If caller didn't override ledger_tx_type, derive from legacy "Tiền ra/vào".
    if ledger_tx_type == "expense" and tx_type == "Tiền vào":
        ledger_tx_type = "income"

    src_key = (account_source_key or "").strip().lower()

    row_data = [
        "",                          # A: ID
        str(tx_date),                # B: Ngày giao dịch
        "", "", "",                  # C, D, E
        description,                 # F: Nội dung
        tx_type,                     # G: Loại ("Tiền ra" or "Tiền vào")
        amount,                      # H: Số tiền  ← explicit, never shifts columns
        ref_code,                    # I: Mã tham chiếu
        0,                           # J: Lũy kế
        "",                          # K: Parent Category
        "",                          # L: Sub-category
        "FALSE",                     # M: Is Daily Spending
        "FALSE",                     # N: Confirmed
        month_key,                   # O: Month
        cur,                         # P: Currency (default "VND")
        account_id or "",            # Q: account_id
        ledger_tx_type or "expense", # R: ledger tx_type
        str(linked_tx_row) if linked_tx_row != "" else "",  # S: linked_tx_row
        "FALSE",                     # T: ledger_applied
        src_key,                     # U: account_source_key (raw, lowercased)
    ]

    with tx_write_lock:
        ws = _sheet(S.TRANSACTIONS)
        # Use col B (date) to find the next truly empty row.
        # col_values truncates at the last non-empty cell, so len() = last used row.
        next_row = len(ws.col_values(2)) + 1  # col B is 1-indexed as 2
        _auto_expand(ws, next_row)
        ws.update(f"A{next_row}:U{next_row}", [row_data])

    _invalidate_tx_rows_cache()  # cache stale sau khi write
    print(f"DEBUG append_transaction: wrote row {next_row}, amount={amount} {cur} "
          f"account={account_id!r} src_key={src_key!r} type={ledger_tx_type!r}")
    return next_row


def backfill_account_id_by_source_key(account_id: str, source_key: str) -> int:
    """Set Transactions.col Q = account_id on all rows where col U matches
    `source_key` AND col Q is empty. Returns number of rows updated.

    Called after a successful account onboarding (in `_commit`) so historical
    tx that landed before the account existed get auto-attributed. Future tx
    flow through the normal resolver path with account_id pre-filled — this
    backfill only fixes the window between "first tx arrives" and "user
    finishes wizard".

    Safe: only touches rows whose source_key matches exactly AND have no
    account_id yet — never overwrites existing assignments.
    """
    src_key = (source_key or "").strip().lower()
    if not src_key or not account_id:
        return 0
    try:
        ws = _sheet(S.TRANSACTIONS)
    except gspread.WorksheetNotFound:
        return 0  # no transactions yet — nothing to backfill
    rows = ws.get_all_values()[1:]  # skip header
    updates = []
    for i, r in enumerate(rows):
        if len(r) < 21:
            continue
        existing_acc = (r[16] if len(r) > 16 else "").strip()
        row_src = (r[20] if len(r) > 20 else "").strip().lower()
        if existing_acc or row_src != src_key:
            continue
        updates.append({"range": f"Q{i+2}:Q{i+2}", "values": [[account_id]]})
    if updates:
        ws.batch_update(updates)
        _invalidate_tx_rows_cache()
        print(f"[backfill] {len(updates)} tx → account_id={account_id!r} "
              f"(source={src_key!r})")
    return len(updates)



def finalize_transaction(row_num: int, parent_category: str, sub_label: str):
    ws = _sheet(S.TRANSACTIONS)
    is_daily = "TRUE" if parent_category == DAILY_BUCKET_ID else "FALSE"

    # Batch update K:N (parent, sub, is_daily, confirmed) trong 1 API call
    # thay vì 4 update_cell riêng — giảm 75% write quota
    ws.update(f"K{row_num}:N{row_num}", [[parent_category, sub_label, is_daily, "TRUE"]])
    _invalidate_tx_rows_cache()


def get_transaction_row(row_num: int) -> list:
    ws = _sheet(S.TRANSACTIONS)
    return ws.row_values(row_num)


def reset_transaction_row(row_num: int):
    """Clear finalized columns so a transaction can be re-categorized.

    Also voids any ledger entries linked to this row and clears col T
    (ledger_applied), so the new categorization cleanly re-applies through
    update_account_cache. The account_id (col Q) is preserved — only
    bucket category + ledger state reset.
    """
    ws = _sheet(S.TRANSACTIONS)
    ws.update(f"K{row_num}:N{row_num}", [["", "", "FALSE", "FALSE"]])
    # Reverse ledger first, then refresh affected account caches.
    affected = {e["account_id"] for e in get_ledger_entries_for_tx(row_num)}
    if affected:
        void_ledger_for_tx(row_num)
        ws.update_cell(row_num, 20, "FALSE")  # col T = ledger_applied
        for acc_id in affected:
            update_account_cache(acc_id)
    _invalidate_tx_rows_cache()


# ─── Budget Config write ──────────────────────────────────────
def write_budget_row(month_key: str, bucket: dict):
    ws = _sheet(S.BUDGET_CONFIG)
    rows = ws.get_all_values()[1:]  # skip header
    for i, r in enumerate(rows):
        if len(r) >= 2 and r[0] == month_key and r[1] == bucket["id"]:
            row_num = i + 2  # +1 for 1-based index, +1 for header row
            ws.update(f"C{row_num}:F{row_num}", [[
                bucket["name"],
                bucket.get("allocated", 0),
                bucket.get("daily_cap") or "",
                "TRUE",
            ]])
            print(f"DEBUG write_budget_row: updated row {row_num} bucket={bucket['id']} allocated={bucket.get('allocated')}")
            return
    # Row doesn't exist — append
    next_row = _next_row(ws, col=1)
    _auto_expand(ws, next_row)
    ws.update(f"A{next_row}:H{next_row}", [[
        month_key,
        bucket["id"],
        bucket["name"],
        bucket.get("allocated", 0),
        bucket.get("daily_cap") or "",
        "TRUE",
        "telegram",
        "",
    ]])
    print(f"DEBUG write_budget_row: appended row {next_row} bucket={bucket['id']} allocated={bucket.get('allocated')}")


# ─── Keyword Rules (auto-categorize by description) ──────────
# Sheet schema (Keyword Rules tab):
#   A: keyword       (normalized: lowercased, diacritics-stripped, trimmed)
#   B: bucket_id
#   C: sub_label     (optional — empty string if not set)
#   D: active        ("TRUE"/"FALSE")
#   E: created_at    (ISO, optional)

_keyword_rules_cache: list | None = None


def _normalize_for_match(s: str) -> str:
    """Lowercase + strip Vietnamese diacritics for robust substring matching."""
    import unicodedata
    if not s:
        return ""
    out = unicodedata.normalize("NFD", str(s).lower())
    # Strip combining marks (covers Vietnamese tone marks)
    out = "".join(ch for ch in out if not unicodedata.combining(ch))
    # Replace đ/Đ which NFD doesn't decompose
    out = out.replace("đ", "d")
    return out.strip()


def _ensure_keyword_rules_tab():
    """Create the Keyword Rules tab with header row if it doesn't exist.
    Idempotent — safe to call on every read.
    """
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(S.KEYWORD_RULES)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=S.KEYWORD_RULES, rows=200, cols=5)
        ws.update("A1:E1", [["keyword", "bucket_id", "sub_label", "active", "created_at"]])
        print(f"[keywords] created tab {S.KEYWORD_RULES!r}")
    return ws


# ─── Accounts + Ledger tabs (Account Tracking) ────────────────
ACCOUNTS_HEADER = [
    "id", "name", "type", "currency", "source_keys",
    "starting_balance", "running_balance",
    "credit_limit", "outstanding_balance",
    "statement_day", "due_day",
    "last_tx_at", "active", "created_at", "notes",
    "starting_outstanding",  # col P — credit: prior-cycle debt declared at setup
    # Phase B. Append-only at the tail so existing column indices never shift.
    "redeem_only",           # col R — wallet can only pay its linked card
]

LEDGER_HEADER = [
    "ledger_id", "tx_row_num", "account_id", "direction",
    "amount", "currency", "tx_type", "applied_at", "notes",
]

# Pending Accounts: persistent onboarding queue. When a webhook delivers a
# transaction whose payload identifier isn't mapped to any account yet, we
# enqueue an entry here so the user can tap "Setup" any time within 24h —
# even after many subsequent transactions overwrite the in-memory bot state.
# Indexed by `setup_key` (md5(source_key)[:12]) which is short enough to fit
# inside Telegram's 64-byte callback_data envelope.
PENDING_ACCOUNTS_HEADER = [
    "setup_key", "source_key", "identifier",
    "tx_row_num", "status", "created_at", "completed_at",
]
PENDING_TTL_SECONDS = 24 * 3600


def _ensure_accounts_tab():
    """Create the Accounts tab with header row if it doesn't exist.

    Bank/debit/cash use F+G (starting + running), credit uses H+I (limit +
    outstanding); J+K (statement/due day) credit-only. Cols extend to R
    (linked_credit_id, redeem_only) for credit card tracking.

    Range is built from len(ACCOUNTS_HEADER) — the old hardcoded `A1:O1`
    truncated the header (stopped at col O while the header already had col P+),
    losing starting_outstanding/linked_credit_id/redeem_only on a fresh tab.
    """
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(S.ACCOUNTS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=S.ACCOUNTS, rows=200, cols=len(ACCOUNTS_HEADER))
        last = _last_col_letter(len(ACCOUNTS_HEADER))
        ws.update(f"A1:{last}1", [ACCOUNTS_HEADER])
        print(f"[accounts] created tab {S.ACCOUNTS!r}")
    return ws


def _ensure_ledger_tab():
    """Create the Account Ledger tab with header row if it doesn't exist.

    Cols A–I per plan §2.3. Ledger is the source of truth for balance;
    `running_balance` / `outstanding_balance` columns in Accounts are caches
    of ledger sums.
    """
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(S.LEDGER)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=S.LEDGER, rows=500, cols=len(LEDGER_HEADER))
        ws.update("A1:I1", [LEDGER_HEADER])
        print(f"[ledger] created tab {S.LEDGER!r}")
    return ws


def _ensure_pending_accounts_tab():
    """Create the Pending Accounts tab if it doesn't exist. Idempotent."""
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(S.PENDING_ACCOUNTS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(
            title=S.PENDING_ACCOUNTS,
            rows=500, cols=len(PENDING_ACCOUNTS_HEADER),
        )
        ws.update("A1:G1", [PENDING_ACCOUNTS_HEADER])
        print(f"[pending] created tab {S.PENDING_ACCOUNTS!r}")
    return ws


# ─── Pending Accounts API ─────────────────────────────────────
# Used by handlers/accounts.py to persist onboarding prompts so they survive
# state-overwriting transactions. Setup remains valid for PENDING_TTL_SECONDS.

def _compute_setup_key(source_key: str) -> str:
    """Stable 12-char hash used as callback-friendly handle for a pending row.

    md5 hex is [0-9a-f] only — safe to embed in `acc_setup_<key>` callback_data
    that splits on `_`. Same source_key → same setup_key (idempotent dedup).
    """
    import hashlib
    return hashlib.md5(source_key.encode("utf-8")).hexdigest()[:12]


def _pending_row_to_dict(row: list, row_num: int) -> dict:
    r = list(row) + [""] * max(0, len(PENDING_ACCOUNTS_HEADER) - len(row))
    return {
        "row_num":      row_num,
        "setup_key":    r[0],
        "source_key":   r[1],
        "identifier":   r[2],
        "tx_row_num":   int(r[3]) if str(r[3]).strip().isdigit() else None,
        "status":       (r[4] or "pending").lower(),
        "created_at":   r[5],
        "completed_at": r[6],
    }


def _is_pending_expired(created_at_iso: str) -> bool:
    """True if created_at is older than PENDING_TTL_SECONDS."""
    if not created_at_iso:
        return False
    try:
        from datetime import datetime as _dt, timezone as _tz
        created = _dt.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        # Normalize to UTC-aware. created_at is written as utcnow().isoformat()
        # (naive UTC). If it has tzinfo, convert to UTC; if naive, assume UTC.
        if created.tzinfo is not None:
            created = created.astimezone(_tz.utc)
        else:
            created = created.replace(tzinfo=_tz.utc)
        now_utc = _dt.now(_tz.utc)
        delta = (now_utc - created).total_seconds()
        return delta > PENDING_TTL_SECONDS
    except Exception:
        return False


def add_pending_account(source_key: str, identifier: str, tx_row_num: int) -> str:
    """Enqueue a pending onboarding for an unmapped identifier.

    Returns the `setup_key` to embed in callback_data. Idempotent: if a
    `pending` row for the same source_key already exists AND is still within
    TTL, we keep it and return its existing key (so duplicate webhook
    deliveries within seconds don't spawn duplicate prompts).

    If an existing `pending` row exists but exceeded TTL (status was never
    flipped because no lookup ran on it), we flip it to `expired` here and
    append a fresh `pending` row — otherwise reusing a stale-but-pending row
    would make the subsequent lookup auto-expire it and return None, leaving
    the user with a freshly-sent prompt that already says "đã hết hạn".

    Applies uniformly across account types — the type (bank/debit/credit/cash)
    is decided later, when the user runs the setup wizard. The pending row
    only tracks "this identifier needs an account, whatever kind".
    """
    source_key = (source_key or "").strip().lower()
    if not source_key:
        return ""

    setup_key = _compute_setup_key(source_key)
    ws = _ensure_pending_accounts_tab()
    rows = ws.get_all_values()[1:]

    for i, r in enumerate(rows):
        if not (len(r) >= 5 and r[0] == setup_key and (r[4] or "").lower() == "pending"):
            continue
        # Status is `pending`. But "pending" alone is not enough — the row
        # may have been written days ago and never observed by a lookup that
        # would have flipped it to `expired`. Reusing a stale row means the
        # next lookup will auto-expire it and the user sees "đã hết hạn"
        # seconds after a fresh prompt.
        created_at_iso = r[5] if len(r) > 5 else ""
        if _is_pending_expired(created_at_iso):
            ws.update_cell(i + 2, 5, "expired")
            ws.update_cell(i + 2, 7, datetime.utcnow().isoformat())
            print(f"[pending] flipped stale-pending → expired setup_key={setup_key!r}")
            continue   # fall through to append a fresh row
        # Active pending — reuse, refresh tx_row_num only if missing
        if (not r[3]) and tx_row_num:
            ws.update_cell(i + 2, 4, int(tx_row_num))
        return setup_key

    next_row = _next_row(ws, col=1)
    now_str = datetime.utcnow().isoformat()
    ws.update(f"A{next_row}:G{next_row}", [[
        setup_key,
        source_key,
        identifier or "",
        int(tx_row_num) if tx_row_num else "",
        "pending",
        now_str,
        "",
    ]])
    print(f"[pending] queued setup_key={setup_key!r} source={source_key!r}")
    return setup_key


def get_pending_by_setup_key(setup_key: str) -> dict | None:
    """Lookup the active pending row by setup_key. Returns None when:
      - no row exists for the key,
      - no row matching the key is still in `pending` status,
      - the only matching row(s) exceeded the TTL (auto-marked `expired` here).

    Multiple rows can share a setup_key over time: setup_key is md5(source_key),
    so when a previous prompt was skipped / expired and the same source later
    re-triggers, `add_pending_account` appends a fresh `pending` row with the
    same key. We must skip past non-pending and expired rows here rather than
    returning None on the first match — otherwise the older stale row shadows
    the newer pending row and Setup taps fail with "đã hết hạn hoặc đã hoàn tất".
    """
    if not setup_key:
        return None
    ws = _ensure_pending_accounts_tab()
    rows = ws.get_all_values()[1:]
    for i, r in enumerate(rows):
        if not r or r[0] != setup_key:
            continue
        status = (r[4] if len(r) > 4 else "").strip().lower()
        if status != "pending":
            # Stale row (completed/skipped/expired/superseded) — keep scanning;
            # a newer pending row for the same key may follow below.
            continue
        entry = _pending_row_to_dict(r, row_num=i + 2)
        if _is_pending_expired(entry["created_at"]):
            # Side-effect: mark expired so it stops cluttering future scans.
            # Continue (not return) — a newer pending row may follow.
            ws.update_cell(i + 2, 5, "expired")
            ws.update_cell(i + 2, 7, datetime.utcnow().isoformat())
            continue
        return entry
    return None


def _set_pending_status(setup_key: str, status: str) -> bool:
    """Internal: update status + completed_at for the ACTIVE PENDING row matching setup_key.

    Scans in reverse so the most recent row is found first, and only updates
    rows with status 'pending' — avoids marking an already-completed/expired row.
    """
    if not setup_key:
        return False
    ws = _ensure_pending_accounts_tab()
    rows = ws.get_all_values()[1:]
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        if r and r[0] == setup_key:
            row_status = (r[4] if len(r) > 4 else "").strip().lower()
            if row_status != "pending":
                continue
            ws.update(f"E{i + 2}:G{i + 2}",
                      [[status, r[5] if len(r) > 5 else "", datetime.utcnow().isoformat()]])
            return True
    return False


def mark_pending_completed(setup_key: str) -> bool:
    return _set_pending_status(setup_key, "completed")


def mark_pending_skipped(setup_key: str) -> bool:
    return _set_pending_status(setup_key, "skipped")


def invalidate_keyword_rules_cache():
    global _keyword_rules_cache
    _keyword_rules_cache = None


def get_keyword_rules(force_refresh: bool = False) -> list[dict]:
    """Return active keyword rules: [{keyword, bucket_id, sub_label, row_num}, ...].
    `keyword` is already normalized for matching. `row_num` is the 1-indexed sheet row.
    """
    global _keyword_rules_cache
    if not force_refresh and _keyword_rules_cache is not None:
        return _keyword_rules_cache

    ws = _ensure_keyword_rules_tab()
    rows = ws.get_all_values()[1:]  # skip header
    result = []
    for i, r in enumerate(rows):
        if len(r) < 4:
            continue
        if str(r[3]).upper() != "TRUE":
            continue
        keyword = _normalize_for_match(r[0])
        bucket_id = (r[1] or "").strip()
        if not keyword or not bucket_id:
            continue
        sub_label = r[2] if len(r) > 2 else ""
        result.append({
            "keyword":   keyword,
            "bucket_id": bucket_id,
            "sub_label": sub_label or "",
            "row_num":   i + 2,  # +1 for header, +1 for 1-based
        })
    _keyword_rules_cache = result
    return result


def match_keyword_rule(description: str) -> dict | None:
    """Find best-matching rule for a transaction description.
    Strategy: case-insensitive + diacritics-insensitive substring match.
    If multiple rules match, the rule with the LONGEST keyword wins
    (more specific). Returns None if nothing matches.
    """
    desc_norm = _normalize_for_match(description)
    if not desc_norm:
        return None

    best = None
    best_len = 0
    for rule in get_keyword_rules():
        kw = rule["keyword"]
        if kw and kw in desc_norm and len(kw) > best_len:
            best = rule
            best_len = len(kw)

    if best:
        print(f"[keywords] matched: keyword={best['keyword']!r} "
              f"→ bucket={best['bucket_id']!r} sub={best['sub_label']!r}")
    return best


def add_keyword_rule(keyword: str, bucket_id: str, sub_label: str = "") -> bool:
    """Add a new active keyword rule. Returns False if (keyword, bucket_id) already
    exists as an active rule (idempotent). The keyword is normalized before saving.
    """
    kw_norm = _normalize_for_match(keyword)
    if not kw_norm or not bucket_id:
        return False

    ws = _ensure_keyword_rules_tab()
    rows = ws.get_all_values()[1:]
    for r in rows:
        if (len(r) >= 4
                and _normalize_for_match(r[0]) == kw_norm
                and (r[1] or "").strip() == bucket_id
                and str(r[3]).upper() == "TRUE"):
            return False  # already exists

    next_row = _next_row(ws, col=1)
    now_str = datetime.utcnow().isoformat()
    ws.update(f"A{next_row}:E{next_row}", [[
        kw_norm,
        bucket_id,
        sub_label or "",
        "TRUE",
        now_str,
    ]])
    invalidate_keyword_rules_cache()
    print(f"[keywords] added: {kw_norm!r} → {bucket_id!r}")
    return True


def soft_delete_keyword_rule(row_num: int) -> bool:
    """Set active=FALSE for the rule at the given sheet row."""
    ws = _ensure_keyword_rules_tab()
    try:
        ws.update_cell(row_num, 4, "FALSE")
        invalidate_keyword_rules_cache()
        return True
    except Exception as e:
        print(f"[keywords] delete error row={row_num}: {e}")
        return False


def update_keyword_rule(row_num: int, *, keyword: str | None = None,
                        bucket_id: str | None = None,
                        sub_label: str | None = None) -> bool:
    """Update one or more fields on an existing keyword rule (by sheet row).
    Pass only the fields you want to change. Returns False on error.
    """
    ws = _ensure_keyword_rules_tab()
    try:
        if keyword is not None:
            kw_norm = _normalize_for_match(keyword)
            if not kw_norm:
                return False
            ws.update_cell(row_num, 1, kw_norm)
        if bucket_id is not None:
            ws.update_cell(row_num, 2, bucket_id.strip())
        if sub_label is not None:
            ws.update_cell(row_num, 3, sub_label or "")
        invalidate_keyword_rules_cache()
        print(f"[keywords] updated row={row_num} "
              f"keyword={keyword!r} bucket={bucket_id!r} sub={sub_label!r}")
        return True
    except Exception as e:
        print(f"[keywords] update error row={row_num}: {e}")
        return False


# ─── Bot State ─────────────────────────────────────────────────
# In-memory cache cho bot state — mỗi Telegram message trigger get_state(),
# không cache sẽ tốn 1 sheet read mỗi message → dễ vượt quota khi user
# tương tác liên tục (vd ấn nhiều button trong 1 phút).
# Cache trust = process là single source of truth (Railway 1 dyno, 1 user),
# nên get_state luôn đọc từ cache trừ khi state vừa được update.
_state_cache: dict = {}  # chat_id (str) -> dict | None


def get_state(chat_id: str) -> dict | None:
    import json
    chat_id_s = str(chat_id)
    # Cache hit
    if chat_id_s in _state_cache:
        return _state_cache[chat_id_s]
    # Cache miss → đọc sheet 1 lần, cache lại
    ws = _sheet(S.BOT_STATE)
    rows = ws.get_all_values()[1:]
    for r in rows:
        if len(r) >= 2 and str(r[0]) == chat_id_s:
            try:
                state = json.loads(r[1])
                _state_cache[chat_id_s] = state
                return state
            except Exception:
                _state_cache[chat_id_s] = None
                return None
    _state_cache[chat_id_s] = None
    return None


def set_state(chat_id: str, obj: dict):
    from datetime import datetime
    import json
    chat_id_s = str(chat_id)
    ws = _sheet(S.BOT_STATE)
    rows = ws.get_all_values()[1:]
    payload = json.dumps(obj, ensure_ascii=False)
    now_str = datetime.utcnow().isoformat()

    for i, r in enumerate(rows):
        if len(r) >= 1 and str(r[0]) == chat_id_s:
            # Batch B:C trong 1 update thay vì 2 update_cell
            ws.update(f"B{i + 2}:C{i + 2}", [[payload, now_str]])
            _state_cache[chat_id_s] = obj
            return

    ws.append_row([chat_id_s, payload, now_str])
    _state_cache[chat_id_s] = obj


def clear_state(chat_id: str):
    state = get_state(chat_id) or {}
    # Preserve language preference across state clears
    preserved = {}
    if "lang" in state:
        preserved["lang"] = state["lang"]
    set_state(chat_id, preserved)


# ─── Monthly Report archive ───────────────────────────────────
def archive_report(month_key: str, results: list[dict]):
    ws = _sheet(S.MONTHLY_REPORTS)
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    for b in results:
        ws.append_row([month_key, b["name"], b["allocated"], b["spent"], b["remaining"], f"{b['pct']}%", now])


# ─── Category / Sub-category management ──────────────────────
def update_bucket(month_key: str, bucket_id: str, updates: dict) -> bool:
    """Update name and/or allocated amount for a bucket.
    updates can contain: {"name": "...", "allocated": 123, "daily_cap": 456}
    """
    ws = _sheet(S.BUDGET_CONFIG)
    rows = ws.get_all_values()[1:]
    for i, r in enumerate(rows):
        if len(r) >= 2 and r[0] == month_key and r[1] == bucket_id:
            row_num = i + 2
            name = updates.get("name", r[2])
            allocated = updates.get("allocated", r[3])
            daily_cap = updates.get("daily_cap", r[4]) or ""
            ws.update(f"C{row_num}:E{row_num}", [[name, allocated, daily_cap]])
            invalidate_buckets_cache()
            return True
    return False


def soft_delete_bucket(month_key: str, bucket_id: str) -> bool:
    """Set active=FALSE for a bucket. Transactions remain intact."""
    ws = _sheet(S.BUDGET_CONFIG)
    rows = ws.get_all_values()[1:]
    for i, r in enumerate(rows):
        if len(r) >= 2 and r[0] == month_key and r[1] == bucket_id:
            ws.update_cell(i + 2, 6, "FALSE")
            invalidate_buckets_cache()
            return True
    return False


def update_sub_category(bucket_id: str, key: str, new_label: str) -> bool:
    """Rename a sub-category."""
    ws = _sheet(S.SUBCATEGORY)
    rows = ws.get_all_values()[1:]
    for i, r in enumerate(rows):
        if len(r) >= 2 and r[0] == bucket_id and r[1] == key:
            ws.update_cell(i + 2, 3, new_label)
            return True
    return False


def soft_delete_sub_category(bucket_id: str, key: str) -> bool:
    """Set active=FALSE for a sub-category."""
    ws = _sheet(S.SUBCATEGORY)
    rows = ws.get_all_values()[1:]
    for i, r in enumerate(rows):
        if len(r) >= 2 and r[0] == bucket_id and r[1] == key:
            ws.update_cell(i + 2, 4, "FALSE")
            return True
    return False


def count_bucket_transactions(bucket_id: str, month_key: str) -> int:
    """Count confirmed transactions for a bucket in a month."""
    rows = _get_tx_rows()
    count = 0
    for r in rows:
        if (len(r) >= 15 and r[14] == month_key
                and r[10] == bucket_id and str(r[13]).upper() == "TRUE"):
            count += 1
    return count


# ════════════════════════════════════════════════════════════════════════
# Account Tracking — accounts + ledger CRUD (Phase 1)
# Plan: ACCOUNT_TRACKING_PLAN.md §2, §4, §5
#
# Ledger is the source of truth. running_balance / outstanding_balance
# columns in Accounts are caches recomputed by update_account_cache().
# All write paths must funnel through append_ledger_entry to preserve
# idempotency on (tx_row_num, direction).
# ════════════════════════════════════════════════════════════════════════

_accounts_cache: list | None = None
account_lock = asyncio.Lock()  # for new-account onboarding race-safety


def invalidate_accounts_cache():
    global _accounts_cache
    _accounts_cache = None


def _parse_source_keys(raw: str) -> list[str]:
    """source_keys col stores JSON list. Tolerate empty/legacy plain-string.
    Normalize to lowercase so matches are case-insensitive."""
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        v = json.loads(raw)
        items = v if isinstance(v, list) else [v]
    except Exception:
        # Legacy: a single source_key written as bare string
        items = [raw]
    return [str(x).strip().lower() for x in items if str(x).strip()]


def _account_from_row(row: list, row_num: int) -> dict:
    """Hydrate an Accounts sheet row into a dict. Pads missing tail cells."""
    r = list(row) + [""] * max(0, len(ACCOUNTS_HEADER) - len(row))
    return {
        "row_num":             row_num,
        "id":                  r[0],
        "name":                r[1],
        "type":                r[2],          # bank | debit | credit | cash
        "currency":            (r[3] or "VND").upper(),
        "source_keys":         _parse_source_keys(r[4]),
        "starting_balance":    _parse_amount(r[5]) if r[5] else 0.0,
        "running_balance":     _parse_amount(r[6]) if r[6] else 0.0,
        "credit_limit":        _parse_amount(r[7]) if r[7] else 0.0,
        "outstanding_balance": _parse_amount(r[8]) if r[8] else 0.0,
        "statement_day":       int(r[9]) if r[9] and str(r[9]).isdigit() else None,
        "due_day":             int(r[10]) if r[10] and str(r[10]).isdigit() else None,
        "last_tx_at":          r[11],
        "active":              str(r[12] or "TRUE").upper() == "TRUE",
        "created_at":          r[13],
        "notes":               r[14],
        # Col P — credit's prior-cycle debt baked in at setup. Read here
        # so update_account_cache can include it in the outstanding sum
        # (cache col I gets recomputed on every ledger write; without a
        # separate starting field, the declared opening debt would
        # silently disappear).
        "starting_outstanding": _parse_amount(r[15]) if len(r) > 15 and r[15] else 0.0,
        # 16-col rows hydrate without IndexError.
        "linked_credit_id":     (r[16] if len(r) > 16 else "") or "",
        "redeem_only":          (str(r[17]).upper() == "TRUE") if len(r) > 17 and r[17] else False,
    }


def get_active_accounts(force_refresh: bool = False) -> list[dict]:
    """Read all active accounts from the Accounts tab. Cached in-memory.

    Account count expected <10 — full read per refresh is fine, no TTL.
    """
    global _accounts_cache
    if not force_refresh and _accounts_cache is not None:
        return _accounts_cache

    ws = _ensure_accounts_tab()
    rows = ws.get_all_values()[1:]  # skip header
    out: list[dict] = []
    for i, r in enumerate(rows):
        if not r or not r[0]:
            continue
        acc = _account_from_row(r, row_num=i + 2)
        if acc["active"]:
            out.append(acc)
    _accounts_cache = out
    return out


def find_account_by_id(account_id: str) -> dict | None:
    if not account_id:
        return None
    for a in get_active_accounts():
        if a["id"] == account_id:
            return a
    return None


def find_account_by_source_key(source_key: str) -> dict | None:
    """Lookup an account whose source_keys list contains source_key.

    source_key is the canonical "{source}:{identifier}" string (e.g.
    "sepay:1903999888"). Match is exact — case-sensitive. Resolver is
    expected to normalize before calling.
    """
    if not source_key:
        return None
    for a in get_active_accounts():
        if source_key in a["source_keys"]:
            return a
    return None


def add_account(
    *,
    account_id: str,
    name: str,
    acc_type: str,
    currency: str = "VND",
    source_keys: list[str] | None = None,
    starting_balance: float = 0.0,
    credit_limit: float = 0.0,
    starting_outstanding: float = 0.0,
    statement_day: int | None = None,
    due_day: int | None = None,
    notes: str = "",
) -> bool:
    """Append a new Accounts row. Returns False if the id already exists.

    `starting_outstanding` (credit only): the debt already on the card at
    setup time. Bot's outstanding starts here; cc_payment ledger entries
    decrement it, expenses increment it. Lets /report show the right
    'dư nợ X / limit Y' from day one instead of starting at 0 and only
    becoming accurate after a full billing cycle of tx.
    """
    if find_account_by_id(account_id) is not None:
        return False

    ws = _ensure_accounts_tab()
    next_row = _next_row(ws, col=1)
    now_str = datetime.utcnow().isoformat()

    is_credit = acc_type == "credit"
    norm_keys = [str(k).strip().lower() for k in (source_keys or []) if str(k).strip()]
    # col I (outstanding_balance) is a CACHE recomputed on every ledger write
    # by update_account_cache. We seed it equal to starting_outstanding so the
    # first /report call (before any ledger write) shows the right number,
    # but the persistent source-of-truth for the opening debt lives in col P
    # (starting_outstanding) — never touched by the cache logic.
    row = [
        account_id,
        name,
        acc_type,
        (currency or "VND").upper(),
        json.dumps(norm_keys, ensure_ascii=False),
        # bank/debit/cash get F+G (starting+running); credit leaves these blank
        "" if is_credit else float(starting_balance or 0),
        "" if is_credit else float(starting_balance or 0),  # running starts == starting
        # credit gets H (limit) + I (outstanding cache, seeded from starting)
        float(credit_limit or 0) if is_credit else "",
        float(starting_outstanding or 0) if is_credit else "",
        statement_day if (is_credit and statement_day) else "",
        due_day if (is_credit and due_day) else "",
        "",          # last_tx_at — set on first ledger write
        "TRUE",      # active
        now_str,
        notes,
        # col P — durable source of truth for the credit's opening debt.
        # update_account_cache reads this on every recompute.
        float(starting_outstanding or 0) if is_credit else "",
    ]
    ws.update(f"A{next_row}:P{next_row}", [row])
    invalidate_accounts_cache()
    print(f"[accounts] added: id={account_id!r} type={acc_type!r} cur={currency!r}"
          + (f" outstanding={starting_outstanding}" if is_credit else ""))
    return True


def add_source_key_to_account(account_id: str, source_key: str) -> bool:
    """Append a new source_key into the JSON list for an existing account.
    Normalizes to lowercase so it matches resolver lookups."""
    acc = find_account_by_id(account_id)
    if not acc:
        return False
    norm = str(source_key).strip().lower()
    if not norm or norm in acc["source_keys"]:
        return True  # already present — no-op success
    new_keys = acc["source_keys"] + [norm]
    ws = _ensure_accounts_tab()
    ws.update_cell(acc["row_num"], 5, json.dumps(new_keys, ensure_ascii=False))
    invalidate_accounts_cache()
    return True


def set_billing_cycle(account_id: str, statement_day: int,
                      due_day: int | None = None) -> bool:
    """Set a credit card's statement (and optional due) day — cols J/K.

    `statement_day` drives `cycle_id`: it defines the [stmt+1 … stmt] window
    /report groups transactions by. Must be 1–28 (days 29–31 don't
    exist in every month, so they'd make the cycle boundary ambiguous — same
    bound the onboarding prompt documents). Returns False for a missing /
    non-credit account or an out-of-range day; `due_day` is informational only
    (shown in /report; not used by cycle math) and skipped when None/invalid.

    Caller is responsible for recomputing affected cycles after a
    change — moving the boundary re-labels which cycle past tx belong to.
    """
    acc = find_account_by_id(account_id)
    if not acc or acc.get("type") != "credit":
        return False
    try:
        sd = int(statement_day)
    except (TypeError, ValueError):
        return False
    if not 1 <= sd <= 28:
        return False
    ws = _ensure_accounts_tab()
    ws.update_cell(acc["row_num"], 10, sd)   # col J — statement_day
    if due_day is not None:
        try:
            dd = int(due_day)
        except (TypeError, ValueError):
            dd = None
        if dd is not None and 1 <= dd <= 28:
            ws.update_cell(acc["row_num"], 11, dd)   # col K — due_day
    invalidate_accounts_cache()
    return True


# ─── Ledger ────────────────────────────────────────────────────

def _get_ledger_rows() -> list[list[str]]:
    """Read all ledger rows (no caching — ledger reads are infrequent
    relative to writes, and stale reads would corrupt idempotency checks)."""
    ws = _ensure_ledger_tab()
    return ws.get_all_values()[1:]


def get_ledger_entries_for_tx(tx_row_num: int) -> list[dict]:
    """Return all (non-void) ledger entries linked to a Transactions row."""
    out: list[dict] = []
    for i, r in enumerate(_get_ledger_rows()):
        if len(r) < 9:
            continue
        if str(r[1]).strip() != str(tx_row_num):
            continue
        # void = applied_at cleared
        if not (r[7] or "").strip():
            continue
        out.append({
            "row_num":     i + 2,
            "ledger_id":   r[0],
            "tx_row_num":  int(r[1]) if r[1].isdigit() else 0,
            "account_id":  r[2],
            "direction":   r[3],
            "amount":      _parse_amount(r[4]),
            "currency":    (r[5] or "VND").upper(),
            "tx_type":     r[6],
            "applied_at":  r[7],
            "notes":       r[8],
        })
    return out


def is_ledger_applied(tx_row_num: int) -> bool:
    """Read Transactions col T (ledger_applied flag) for the given row."""
    ws = _sheet(S.TRANSACTIONS)
    val = ws.cell(tx_row_num, 20).value or ""  # col T = 20
    return str(val).strip().upper() == "TRUE"


def mark_ledger_applied(tx_row_num: int):
    ws = _sheet(S.TRANSACTIONS)
    ws.update_cell(tx_row_num, 20, "TRUE")
    _invalidate_tx_rows_cache()


def unmark_ledger_applied(tx_row_num: int):
    ws = _sheet(S.TRANSACTIONS)
    ws.update_cell(tx_row_num, 20, "FALSE")
    _invalidate_tx_rows_cache()


def append_ledger_entry(
    *,
    tx_row_num: int,
    account_id: str,
    direction: str,        # "+" or "−" (or "-")
    amount: float,
    currency: str,
    tx_type: str,
    leg: str = "1",        # "1" for single-leg expense/income; "out"/"in" for transfer/cc legs
    notes: str = "",
) -> str:
    """Append a ledger entry. Idempotent: if a non-void entry with the same
    (tx_row_num, direction, account_id) already exists, return its id without
    writing a second row.

    Returns the ledger_id (auto: `L{tx_row_num}_{leg}`).
    """
    direction_norm = "−" if direction in ("-", "−") else "+"

    # Idempotency check — pre-write read of ledger
    existing = get_ledger_entries_for_tx(tx_row_num)
    for e in existing:
        if e["direction"] == direction_norm and e["account_id"] == account_id:
            print(f"[ledger] dedup: tx={tx_row_num} dir={direction_norm} acc={account_id} "
                  f"→ existing={e['ledger_id']!r}")
            return e["ledger_id"]

    ws = _ensure_ledger_tab()
    next_row = _next_row(ws, col=1)
    ledger_id = f"L{tx_row_num}_{leg}"
    now_str = datetime.utcnow().isoformat()

    row = [
        ledger_id,
        str(tx_row_num),
        account_id,
        direction_norm,
        float(amount),
        (currency or "VND").upper(),
        tx_type or "expense",
        now_str,
        notes,
    ]
    ws.update(f"A{next_row}:I{next_row}", [row])
    print(f"[ledger] appended: {ledger_id} tx={tx_row_num} {direction_norm}{amount} "
          f"{currency} acc={account_id} type={tx_type}")
    return ledger_id


def void_ledger_for_tx(tx_row_num: int) -> int:
    """Mark all ledger entries for a Transactions row as void (clear applied_at).

    Used by reset_transaction_row when a tx is recategorized — prevents
    double-counting when the new ledger entry is written. Returns the count
    of entries voided.
    """
    ws = _ensure_ledger_tab()
    rows = ws.get_all_values()[1:]
    voided = 0
    for i, r in enumerate(rows):
        if len(r) < 9:
            continue
        if str(r[1]).strip() != str(tx_row_num):
            continue
        if not (r[7] or "").strip():
            continue  # already void
        ws.update_cell(i + 2, 8, "")  # col H = applied_at
        voided += 1
    if voided:
        print(f"[ledger] voided {voided} entries for tx={tx_row_num}")
    return voided


def update_account_cache(account_id: str):
    """Recompute and write running_balance / outstanding_balance + last_tx_at
    for an account from the ledger sum.

    Bank/debit/cash → col G (running_balance) = starting + Σ signed entries.
    Credit          → col I (outstanding_balance) = max(0, Σ −entries − Σ +entries)
                      (spend grows outstanding; payments reduce it).
    last_tx_at      → max(applied_at) across non-void entries for this account.
    """
    acc = find_account_by_id(account_id)
    if not acc:
        print(f"[accounts] update_account_cache: account {account_id!r} not found")
        return

    rows = _get_ledger_rows()
    total_signed = 0.0   # for bank: + adds, − subtracts
    total_spend = 0.0    # for credit: sum of − entries
    total_payments = 0.0 # for credit: sum of + entries
    last_at = ""
    for r in rows:
        if len(r) < 9:
            continue
        if r[2] != account_id:
            continue
        if not (r[7] or "").strip():  # void
            continue
        # Currency mismatch entries are skipped at write time — but defensively
        # filter here so a bad row doesn't corrupt the cache.
        if (r[5] or "VND").upper() != acc["currency"]:
            continue
        amt = _parse_amount(r[4])
        direction = r[3]
        if direction == "+":
            total_signed += amt
            total_payments += amt
        else:
            total_signed -= amt
            total_spend += amt
        if r[7] > last_at:
            last_at = r[7]

    ws = _ensure_accounts_tab()
    if acc["type"] == "credit":
        # Opening debt declared at setup + spending since − payments since.
        # max(0,...) so an over-payment doesn't show as a negative outstanding
        # (which would imply the card owes the user money — meaningless).
        starting_out = acc.get("starting_outstanding", 0.0) or 0.0
        outstanding = max(0.0, starting_out + total_spend - total_payments)
        # Col I = outstanding_balance, col L = last_tx_at
        ws.update_cell(acc["row_num"], 9, outstanding)
        ws.update_cell(acc["row_num"], 12, last_at)
        print(f"[accounts] cache updated: {account_id} outstanding={outstanding} "
              f"(starting={starting_out} +spend={total_spend} −paid={total_payments}) "
              f"last={last_at}")
    else:
        running = acc["starting_balance"] + total_signed
        # Col G = running_balance, col L = last_tx_at
        ws.update_cell(acc["row_num"], 7, running)
        ws.update_cell(acc["row_num"], 12, last_at)
        print(f"[accounts] cache updated: {account_id} running={running} last={last_at}")
    invalidate_accounts_cache()


def set_tx_account(tx_row_num: int, account_id: str, ledger_tx_type: str | None = None):
    """Update Transactions cols Q (account_id) and optionally R (tx_type)
    on an existing row — used by the new-account onboarding backfill and
    by recategorize-as-transfer flows.
    """
    ws = _sheet(S.TRANSACTIONS)
    ws.update_cell(tx_row_num, 17, account_id)  # col Q = 17
    if ledger_tx_type is not None:
        ws.update_cell(tx_row_num, 18, ledger_tx_type)  # col R = 18
    _invalidate_tx_rows_cache()


def append_transfer(
    *,
    from_account_id: str,
    to_account_id: str,
    amount: float,
    currency: str,
    description: str,
    tx_date,
    ref_code: str,
    month_key: str,
) -> tuple[int, str]:
    """Record a transfer between two accounts.

    Plan §5.4 — convention is *one* Transactions row + two ledger legs:
      row.account_id   = from_account_id (the "active" side)
      row.tx_type      = "transfer"
      row.parent/sub   = blank (transfer is not a bucket spend)
      row.confirmed    = TRUE (no user picker — already known)
      ledger leg 1     = from (−amount)
      ledger leg 2     = to   (+amount)

    Returns (row_num, status_message). Caller is expected to pre-validate
    accounts exist + currencies match. If currencies don't match we abort
    with no writes — `status_message` will start with 'ERROR'.
    """
    from_acc = find_account_by_id(from_account_id)
    to_acc = find_account_by_id(to_account_id)
    if not from_acc:
        return (0, f"ERROR: account {from_account_id!r} not found")
    if not to_acc:
        return (0, f"ERROR: account {to_account_id!r} not found")
    cur = (currency or "VND").upper()
    if from_acc["currency"].upper() != cur or to_acc["currency"].upper() != cur:
        return (0, f"ERROR: currency mismatch — from={from_acc['currency']} "
                f"to={to_acc['currency']} tx={cur}")

    row_num = append_transaction(
        tx_date, description, amount, ref_code, month_key,
        tx_type="Tiền ra",
        currency=cur,
        account_id=from_account_id,
        ledger_tx_type="transfer",
    )
    # Mark confirmed immediately — transfers don't need bucket categorization
    ws = _sheet(S.TRANSACTIONS)
    ws.update(f"K{row_num}:N{row_num}", [["", "", "FALSE", "TRUE"]])

    append_ledger_entry(
        tx_row_num=row_num, account_id=from_account_id, direction="-",
        amount=amount, currency=cur, tx_type="transfer", leg="out",
        notes=f"transfer → {to_account_id}",
    )
    append_ledger_entry(
        tx_row_num=row_num, account_id=to_account_id, direction="+",
        amount=amount, currency=cur, tx_type="transfer", leg="in",
        notes=f"transfer ← {from_account_id}",
    )
    update_account_cache(from_account_id)
    update_account_cache(to_account_id)
    mark_ledger_applied(row_num)

    return (row_num, "ok")


def append_cc_payment(
    *,
    bank_account_id: str,
    cc_account_id: str,
    amount: float,
    currency: str,
    description: str,
    tx_date,
    ref_code: str,
    month_key: str,
) -> tuple[int, str]:
    """Record a credit-card payment (bank → CC).

    Same shape as append_transfer but the destination is a credit account
    where +leg reduces outstanding_balance instead of growing a bank balance.
    """
    bank_acc = find_account_by_id(bank_account_id)
    cc_acc = find_account_by_id(cc_account_id)
    if not bank_acc:
        return (0, f"ERROR: bank account {bank_account_id!r} not found")
    if not cc_acc:
        return (0, f"ERROR: cc account {cc_account_id!r} not found")
    if cc_acc["type"] != "credit":
        return (0, f"ERROR: {cc_account_id!r} is not a credit card")
    cur = (currency or "VND").upper()
    if bank_acc["currency"].upper() != cur or cc_acc["currency"].upper() != cur:
        return (0, f"ERROR: currency mismatch")

    row_num = append_transaction(
        tx_date, description, amount, ref_code, month_key,
        tx_type="Tiền ra",
        currency=cur,
        account_id=bank_account_id,
        ledger_tx_type="cc_payment",
    )
    ws = _sheet(S.TRANSACTIONS)
    ws.update(f"K{row_num}:N{row_num}", [["", "", "FALSE", "TRUE"]])

    append_ledger_entry(
        tx_row_num=row_num, account_id=bank_account_id, direction="-",
        amount=amount, currency=cur, tx_type="cc_payment", leg="out",
        notes=f"cc payment → {cc_account_id}",
    )
    append_ledger_entry(
        tx_row_num=row_num, account_id=cc_account_id, direction="+",
        amount=amount, currency=cur, tx_type="cc_payment", leg="in",
        notes=f"cc payment from {bank_account_id}",
    )
    update_account_cache(bank_account_id)
    update_account_cache(cc_account_id)
    mark_ledger_applied(row_num)

    return (row_num, "ok")


def append_cc_payment_external(
    *,
    cc_account_id: str,
    amount: float,
    currency: str,
    description: str,
    tx_date,
    ref_code: str,
    month_key: str,
) -> tuple[int, str]:
    """Record a credit-card payment from an UNTRACKED source.

    Use when the user pays their card from a bank account that the bot
    doesn't have onboarded — e.g. friend's transfer, cash deposit at ATM,
    salary auto-pay from a foreign account. Only one ledger leg is written
    (the +leg on the credit account, decreasing outstanding); there is no
    bank −leg because we don't track that source.

    The Transactions row is tagged `ledger_tx_type="cc_payment"` and
    `account_id=cc_account_id` so /report's account lens correctly groups
    it. linked_tx_row is left empty (no paired leg).
    """
    cc_acc = find_account_by_id(cc_account_id)
    if not cc_acc:
        return (0, f"ERROR: cc account {cc_account_id!r} not found")
    if cc_acc["type"] != "credit":
        return (0, f"ERROR: {cc_account_id!r} is not a credit card")
    cur = (currency or "VND").upper()
    if cc_acc["currency"].upper() != cur:
        return (0, "ERROR: currency mismatch")

    row_num = append_transaction(
        tx_date, description, amount, ref_code, month_key,
        tx_type="Tiền vào",      # money coming INTO the credit account
        currency=cur,
        account_id=cc_account_id,
        ledger_tx_type="cc_payment",
    )
    ws = _sheet(S.TRANSACTIONS)
    ws.update(f"K{row_num}:N{row_num}", [["", "", "FALSE", "TRUE"]])

    append_ledger_entry(
        tx_row_num=row_num, account_id=cc_account_id, direction="+",
        amount=amount, currency=cur, tx_type="cc_payment", leg="in",
        notes="cc payment from external source (not tracked)",
    )
    update_account_cache(cc_account_id)
    mark_ledger_applied(row_num)

    return (row_num, "ok")


def get_recent_unresolved_txs(source_key: str, hours: int = 24) -> list[dict]:
    """Find Transactions rows in the last `hours` that have empty account_id.

    Used by new-account onboarding to backfill recent tx that arrived before
    the user finished setting up the account. We don't store the resolver's
    source_key per-row (it's redundant with description + source), so we
    return the raw rows and let the caller verify each via the resolver.
    """
    import time
    cutoff = time.time() - hours * 3600
    out: list[dict] = []
    rows = _get_tx_rows()
    for i, r in enumerate(rows):
        if len(r) < 17:
            continue
        if (r[16] or "").strip():  # already has account_id
            continue
        # B=date, parse loose
        try:
            dt = _parse_dt(str(r[1]))
            if not dt or dt.timestamp() < cutoff:
                continue
        except Exception:
            continue
        out.append({
            "row_num":     i + 2,
            "tx_date":     r[1],
            "description": r[5] if len(r) > 5 else "",
            "tx_type":     r[6] if len(r) > 6 else "",
            "amount":      _parse_amount(r[7]) if len(r) > 7 else 0.0,
            "ref_code":    r[8] if len(r) > 8 else "",
            "currency":    row_currency(r),
            "confirmed":   str(r[13] or "").upper() == "TRUE" if len(r) > 13 else False,
            "_row":        r,
        })
    return out
