import asyncio
import json
import time
import gspread
from gspread.exceptions import APIError
from gspread.http_client import HTTPClient
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timezone
import pytz
from config import SHEET_ID, CREDS_FILE, GOOGLE_CREDS_JSON, TIMEZONE, DAILY_BUCKET_ID
from config import SHEETS as S
from handlers.cashback_engine import compute_cashback

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


class QuotaBackoffHTTPClient(HTTPClient):
    """Retry only transient Google Sheets read/write quota responses.

    The built-in gspread backoff client keeps retrying at its maximum delay,
    which can leave a webhook request blocked forever when a quota problem is
    persistent.  Keep this retry budget deliberately short: the caches below
    remove the avoidable reads; this is only a grace period while quota refills.
    """

    _QUOTA_STATUS = 429
    _RETRY_DELAYS = (1, 2, 4, 8)

    def request(self, *args, **kwargs):
        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                return super().request(*args, **kwargs)
            except APIError as error:
                if (getattr(error, "code", None) != self._QUOTA_STATUS
                        or attempt == len(self._RETRY_DELAYS)):
                    raise
                delay = self._RETRY_DELAYS[attempt]
                print(f"[sheets] Google API quota hit; retrying in {delay}s "
                      f"({attempt + 1}/{len(self._RETRY_DELAYS)})")
                time.sleep(delay)


def _get_tx_rows(force_refresh: bool = False) -> list:
    """Đọc tất cả row của Transactions sheet với cache TTL ngắn.
    Dùng thay cho `_sheet(S.TRANSACTIONS).get_all_values()[1:]` ở những chỗ
    cần đọc nhiều lần liên tiếp.
    """
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
# Reentrant: recompute_cashback_for_tx holds this across a whole void+rebuild
# sequence while the per-row compute_and_record_cashback re-acquires it on the
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
        _gc = gspread.authorize(creds, http_client=QuotaBackoffHTTPClient)
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
    # If the linked account is a configured credit card, compute cashback for
    # the rows it now owns. Runs even when `updates` is empty: the wizard's
    # trigger tx is stamped with account_id by an earlier path, so it's absent
    # from `updates` yet still needs cashback. Best-effort — never break onboarding.
    try:
        _recompute_cashback_after_backfill(account_id)
    except Exception:
        import logging
        logging.exception("[cashback] backfill recompute failed for %s", account_id)
    return len(updates)


def _recompute_cashback_after_backfill(account_id: str):
    """Recompute cashback for a newly-onboarded credit card's transactions.

    No-op unless the account is `type=credit` with an active config. Recomputes
    once per unique statement-cycle the account has expense tx in (covers both
    backfilled rows and the wizard trigger row stamped earlier). recompute_*
    rebuilds the whole cycle from one representative row.
    """
    acc = find_account_by_id(account_id)
    if not acc or acc.get("type") != "credit":
        return
    cfg = get_card_config(account_id)
    if not cfg or not cfg.get("active"):
        return
    statement_day = acc.get("statement_day")
    try:
        ws = _sheet(S.TRANSACTIONS)
    except gspread.WorksheetNotFound:
        return
    seen_cycles: set[str] = set()
    for i, r in enumerate(ws.get_all_values()[1:]):
        if (r[16] if len(r) > 16 else "").strip() != account_id:
            continue
        if ((r[17] if len(r) > 17 else "").strip() or "expense") != "expense":
            continue
        cyc = cycle_id(account_id, r[1] if len(r) > 1 else "", statement_day)
        if cyc in seen_cycles:
            continue
        seen_cycles.add(cyc)
        recompute_cashback_for_tx(i + 2)


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
    # Cashback (BRD §6.6) — declared in Phase A, used by the cashback wallet in
    # Phase B. Append-only at the tail so existing column indices never shift.
    "linked_credit_id",      # col Q — cashback wallet → the credit card it pays
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
    (linked_credit_id, redeem_only) for the Phase B cashback wallet.

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


# ─── Cashback tabs (BRD §6) ───────────────────────────────────
# 5 additive tabs. All header ranges built from len(*_HEADER) via
# _last_col_letter so adding a column never truncates the written range.

CASHBACK_RULES_HEADER = [           # §6.1 — cols A–R
    "rule_id", "account_id", "rule_name", "match_type", "match_value",
    "rate", "monthly_cap", "per_tx_cap_tier", "max_eligible_tx_per_day",
    "min_tx_amount", "stackable", "priority", "cap_period",
    "effective_from", "effective_to", "active", "created_at", "notes",
]

CASHBACK_TIERS_HEADER = [           # §6.2 — cols A–D (per-tx cap by amount band)
    "tier_set", "tx_min", "tx_max", "per_tx_cap",
]

CASHBACK_CONFIG_HEADER = [          # §6.3 — cols A–F (card-level config)
    "account_id", "cashback_rate", "min_eligible_spend",
    "cap_period", "alert_pct", "active",
]

CASHBACK_LEDGER_HEADER = [          # §6.4 — cols A–M (reason = 0đ audit cause)
    "cashback_id", "tx_row_num", "account_id", "rule_id", "mcc_code",
    "eligible_amount", "rate", "cashback_amount", "cycle", "capped_flag",
    "status", "created_at", "reason",
]

MCC_MAP_HEADER = [                  # §6.5 — cols A–G (description → MCC lookup)
    "pattern", "mcc_code", "mcc_label", "default_category",
    "priority", "active", "notes",
]


def _ensure_tab_with_header(name: str, header: list[str], rows: int = 200):
    """Create `name` with `header` (dynamic range) if missing. Idempotent.

    Shared by every cashback _ensure_*_tab — the range is always
    `A1:{last}1` where last = _last_col_letter(len(header)), so the full
    header is written regardless of how many columns it has.
    """
    ss = _get_spreadsheet()
    try:
        return ss.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows=rows, cols=len(header))
        last = _last_col_letter(len(header))
        ws.update(f"A1:{last}1", [header])
        print(f"[cashback] created tab {name!r}")
        return ws


def _ensure_cashback_rules_tab():
    return _ensure_tab_with_header(S.CASHBACK_RULES, CASHBACK_RULES_HEADER)


def _ensure_cashback_tiers_tab():
    return _ensure_tab_with_header(S.CASHBACK_TIERS, CASHBACK_TIERS_HEADER, rows=50)


def _ensure_cashback_config_tab():
    return _ensure_tab_with_header(S.CASHBACK_CONFIG, CASHBACK_CONFIG_HEADER, rows=50)


def _ensure_cashback_ledger_tab():
    return _ensure_tab_with_header(S.CASHBACK_LEDGER, CASHBACK_LEDGER_HEADER, rows=1000)


def _ensure_mcc_map_tab():
    return _ensure_tab_with_header(S.MCC_MAP, MCC_MAP_HEADER)


# ─── Cashback CRUD + cycle helpers + orchestrator ─────────────
# Rules / tiers / config / mcc_map are cached (read-mostly, small) like
# _accounts_cache. The ledger is never cached — it's write-heavy and stale
# reads would corrupt idempotency / cycle sums.

_cashback_rules_cache: list | None = None
_cashback_tiers_cache: list | None = None
_card_config_cache: dict | None = None
_mcc_map_cache: list | None = None


def invalidate_cashback_caches():
    global _cashback_rules_cache, _cashback_tiers_cache, _card_config_cache, _mcc_map_cache, _mcc_exclusion_cache
    _cashback_rules_cache = None
    _cashback_tiers_cache = None
    _card_config_cache = None
    _mcc_map_cache = None
    _mcc_exclusion_cache = None


def _to_num(val):
    """Parse a numeric cell → float, or None when blank (rate inherit etc.)."""
    s = str(val).strip()
    if s == "":
        return None
    try:
        return _parse_amount(s)
    except (ValueError, TypeError):
        return None


def _parse_tx_date(val):
    """ISO datetime/date string (or datetime/date) → date. Day-level only."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


# ── Rules ──────────────────────────────────────────────────────

def _rule_from_row(r: list, row_num: int) -> dict:
    return {
        "row_num":                 row_num,
        "rule_id":                 r[0],
        "account_id":              r[1] if len(r) > 1 else "",
        "rule_name":               r[2] if len(r) > 2 else "",
        "match_type":              (r[3] if len(r) > 3 else "").strip(),
        "match_value":             str(r[4]).strip() if len(r) > 4 else "",
        "rate":                    _to_num(r[5]) if len(r) > 5 else None,
        "monthly_cap":             (_to_num(r[6]) or 0.0) if len(r) > 6 else 0.0,
        "per_tx_cap_tier":         (r[7] if len(r) > 7 else "").strip(),
        "max_eligible_tx_per_day": int(_to_num(r[8]) or 0) if len(r) > 8 else 0,
        "min_tx_amount":           (_to_num(r[9]) or 0.0) if len(r) > 9 else 0.0,
        "stackable":               str(r[10]).upper() == "TRUE" if len(r) > 10 else False,
        "priority":                int(_to_num(r[11]) or 0) if len(r) > 11 else 0,
        "cap_period":              r[12] if len(r) > 12 else "",
        "active":                  str(r[15]).upper() == "TRUE" if len(r) > 15 else False,
    }


def get_cashback_rules(account_id: str | None = None, force_refresh: bool = False) -> list[dict]:
    """Active cashback rules. Filter by account_id when given."""
    global _cashback_rules_cache
    if force_refresh or _cashback_rules_cache is None:
        ws = _ensure_cashback_rules_tab()
        rows = ws.get_all_values()[1:]
        out = []
        for i, r in enumerate(rows):
            if not r or not r[0]:
                continue
            if len(r) > 15 and str(r[15]).upper() != "TRUE":
                continue
            out.append(_rule_from_row(r, i + 2))
        _cashback_rules_cache = out
    if account_id:
        return [r for r in _cashback_rules_cache if r["account_id"] == account_id]
    return list(_cashback_rules_cache)


def add_cashback_rule(account_id: str, rule_name: str, match_type: str,
                      match_value: str, *, rate=0.20, monthly_cap=200000.0,
                      per_tx_cap_tier: str = "", max_eligible_tx_per_day: int = 0,
                      min_tx_amount: float = 0.0, stackable: bool = False,
                      priority: int = 1, cap_period: str = "statement_cycle",
                      effective_from: str = "", effective_to: str = "",
                      notes: str = "", rule_id: str | None = None) -> str:
    """Add an active cashback rule, return its rule_id.

    rule_id is unique: re-adding an existing id (active OR soft-deleted)
    reactivates and refreshes that one row instead of appending a duplicate —
    otherwise update/soft_delete (which target the first id match) would hit the
    stale row and leave the active duplicate untouched (Codex round 04).
    """
    rid = rule_id or f"{account_id}_{str(match_value).strip() or match_type}"
    ws = _ensure_cashback_rules_tab()
    rows = ws.get_all_values()[1:]
    existing_idx = next((i for i, r in enumerate(rows) if r and r[0] == rid), None)
    now = datetime.utcnow().isoformat()
    # Preserve original created_at when reactivating.
    created = (rows[existing_idx][16]
               if existing_idx is not None and len(rows[existing_idx]) > 16
               and rows[existing_idx][16] else now)
    row = [
        rid, account_id, rule_name, match_type, str(match_value),
        rate, monthly_cap, per_tx_cap_tier, max_eligible_tx_per_day,
        min_tx_amount, "TRUE" if stackable else "FALSE", priority,
        cap_period, effective_from, effective_to, "TRUE", created, notes,
    ]
    target_row = (existing_idx + 2) if existing_idx is not None else _next_row(ws, col=1)
    last = _last_col_letter(len(CASHBACK_RULES_HEADER))
    ws.update(f"A{target_row}:{last}{target_row}", [row])
    invalidate_cashback_caches()
    print(f"[cashback] rule {'reactivated' if existing_idx is not None else 'added'}: {rid!r}")
    return rid


# field → 1-based column for update_cashback_rule
_RULE_UPDATE_COL = {
    "account_id": 2, "rule_name": 3, "match_type": 4, "match_value": 5,
    "rate": 6, "monthly_cap": 7, "per_tx_cap_tier": 8,
    "max_eligible_tx_per_day": 9, "min_tx_amount": 10, "stackable": 11,
    "priority": 12, "cap_period": 13, "effective_from": 14,
    "effective_to": 15, "active": 16, "notes": 18,
}


def update_cashback_rule(rule_id: str, **fields) -> bool:
    """Update one or more columns on a rule (by rule_id). Returns False if not found."""
    ws = _ensure_cashback_rules_tab()
    rows = ws.get_all_values()[1:]
    row_num = next((i + 2 for i, r in enumerate(rows) if r and r[0] == rule_id), None)
    if row_num is None:
        return False
    for k, v in fields.items():
        col = _RULE_UPDATE_COL.get(k)
        if not col:
            continue
        if k in ("stackable", "active"):
            v = "TRUE" if v else "FALSE"
        ws.update_cell(row_num, col, v)
    invalidate_cashback_caches()
    return True


def soft_delete_cashback_rule(rule_id: str) -> bool:
    """Set active=FALSE (col P) for the rule. Returns False if not found."""
    ws = _ensure_cashback_rules_tab()
    rows = ws.get_all_values()[1:]
    for i, r in enumerate(rows):
        if r and r[0] == rule_id:
            ws.update_cell(i + 2, 16, "FALSE")
            invalidate_cashback_caches()
            return True
    return False


# ── Tiers ──────────────────────────────────────────────────────

def get_cashback_tiers(tier_set: str, force_refresh: bool = False) -> list[dict]:
    """Per-tx cap tiers for a tier set, sorted ascending by tx_min."""
    global _cashback_tiers_cache
    if force_refresh or _cashback_tiers_cache is None:
        ws = _ensure_cashback_tiers_tab()
        rows = ws.get_all_values()[1:]
        out = []
        for r in rows:
            if not r or not r[0]:
                continue
            tx_max = r[2] if len(r) > 2 else ""
            out.append({
                "tier_set":   r[0],
                "tx_min":     _to_num(r[1]) or 0.0 if len(r) > 1 else 0.0,
                "tx_max":     (_to_num(tx_max) if str(tx_max).strip() else None),
                "per_tx_cap": _to_num(r[3]) or 0.0 if len(r) > 3 else 0.0,
            })
        _cashback_tiers_cache = out
    res = [t for t in _cashback_tiers_cache if t["tier_set"] == tier_set]
    return sorted(res, key=lambda t: t["tx_min"])


# ── Card config ────────────────────────────────────────────────

def get_card_config(account_id: str, force_refresh: bool = False) -> dict | None:
    global _card_config_cache
    if force_refresh or _card_config_cache is None:
        ws = _ensure_cashback_config_tab()
        rows = ws.get_all_values()[1:]
        d: dict = {}
        for i, r in enumerate(rows):
            if not r or not r[0]:
                continue
            d[r[0]] = {
                "row_num":            i + 2,
                "account_id":         r[0],
                "cashback_rate":      _to_num(r[1]) or 0.0 if len(r) > 1 else 0.0,
                "min_eligible_spend": _to_num(r[2]) or 0.0 if len(r) > 2 else 0.0,
                "cap_period":         r[3] if len(r) > 3 else "statement_cycle",
                "alert_pct":          _to_num(r[4]) or 0.0 if len(r) > 4 else 0.0,
                "active":             str(r[5]).upper() == "TRUE" if len(r) > 5 else True,
            }
        _card_config_cache = d
    return _card_config_cache.get(account_id)


def upsert_card_config(account_id: str, **fields) -> None:
    """Create or update the card config row, merging `fields` over current values."""
    ws = _ensure_cashback_config_tab()
    current = get_card_config(account_id, force_refresh=True)
    merged = {
        "cashback_rate":      (current or {}).get("cashback_rate", 0.0),
        "min_eligible_spend": (current or {}).get("min_eligible_spend", 0.0),
        "cap_period":         (current or {}).get("cap_period", "statement_cycle"),
        "alert_pct":          (current or {}).get("alert_pct", 0.0),
        "active":             (current or {}).get("active", True),
    }
    merged.update({k: v for k, v in fields.items() if k in merged})
    row = [
        account_id, merged["cashback_rate"], merged["min_eligible_spend"],
        merged["cap_period"], merged["alert_pct"],
        "TRUE" if merged["active"] else "FALSE",
    ]
    rn = current["row_num"] if current else _next_row(ws, col=1)
    ws.update(f"A{rn}:F{rn}", [row])
    invalidate_cashback_caches()


# ── MCC Map ────────────────────────────────────────────────────

def get_mcc_map(force_refresh: bool = False) -> list[dict]:
    """Active MCC patterns. `pattern` is normalized for substring matching."""
    global _mcc_map_cache
    if force_refresh or _mcc_map_cache is None:
        ws = _ensure_mcc_map_tab()
        rows = ws.get_all_values()[1:]
        out = []
        for i, r in enumerate(rows):
            if not r or not r[0]:
                continue
            if len(r) > 5 and str(r[5]).upper() != "TRUE":
                continue
            out.append({
                "row_num":          i + 2,
                "pattern":          _normalize_for_match(r[0]),
                "mcc_code":         str(r[1]).strip() if len(r) > 1 else "",
                "mcc_label":        r[2] if len(r) > 2 else "",
                "default_category": r[3] if len(r) > 3 else "",
                "priority":         int(_to_num(r[4]) or 0) if len(r) > 4 else 0,
                "active":           True,
            })
        _mcc_map_cache = out
    return list(_mcc_map_cache)


def add_mcc_map(pattern: str, mcc_code: str, mcc_label: str = "",
                default_category: str = "", priority: int = 0, notes: str = "") -> bool:
    """Add an active MCC pattern (stored normalized). Idempotent on (pattern, mcc)."""
    pat = _normalize_for_match(pattern)
    if not pat or not str(mcc_code).strip():
        return False
    ws = _ensure_mcc_map_tab()
    rows = ws.get_all_values()[1:]
    for r in rows:
        if (len(r) > 5 and _normalize_for_match(r[0]) == pat
                and str(r[1]).strip() == str(mcc_code).strip()
                and str(r[5]).upper() == "TRUE"):
            return False
    next_row = _next_row(ws, col=1)
    row = [pat, str(mcc_code).strip(), mcc_label, default_category, priority, "TRUE", notes]
    _auto_expand(ws, next_row)
    ws.update(f"A{next_row}:G{next_row}", [row])
    invalidate_cashback_caches()
    return True


def add_cashback_rules_bulk(specs: list[dict]) -> int:
    """Batch add_cashback_rule — ONE read + ONE write for many rules (seed 429 fix).

    Each spec mirrors add_cashback_rule kwargs (account_id, rule_name, match_type,
    match_value required; the rest default identically). Reactivates an existing
    rule_id in place (preserving created_at) and appends new ones — rows are
    byte-identical to add_cashback_rule. Returns the count processed.
    """
    if not specs:
        return 0
    ws = _ensure_cashback_rules_tab()
    rows = ws.get_all_values()[1:]   # single read
    idx_by_rid = {r[0]: i for i, r in enumerate(rows) if r and r[0]}  # existing sheet rows
    now = datetime.utcnow().isoformat()
    last = _last_col_letter(len(CASHBACK_RULES_HEADER))
    updates: dict = {}        # sheet row_num → row (last-wins per rid)
    appends: list = []        # new rows, in order
    seen_new: dict = {}       # rid → index into `appends` (within-batch dedupe)
    for s in specs:
        account_id = s["account_id"]
        match_value = s.get("match_value", "")
        rid = s.get("rule_id") or f"{account_id}_{str(match_value).strip() or s['match_type']}"
        row = [
            rid, account_id, s["rule_name"], s["match_type"], str(match_value),
            s.get("rate", 0.20), s.get("monthly_cap", 200000.0), s.get("per_tx_cap_tier", ""),
            s.get("max_eligible_tx_per_day", 0), s.get("min_tx_amount", 0.0),
            "TRUE" if s.get("stackable") else "FALSE", s.get("priority", 1),
            s.get("cap_period", "statement_cycle"), s.get("effective_from", ""),
            s.get("effective_to", ""), "TRUE", now, s.get("notes", ""),
        ]
        if rid in idx_by_rid:        # reactivate an existing sheet row (preserve created_at)
            existing = rows[idx_by_rid[rid]]
            row[16] = existing[16] if len(existing) > 16 and existing[16] else now
            updates[idx_by_rid[rid] + 2] = row
        elif rid in seen_new:        # duplicate new rid within this batch → last-wins
            appends[seen_new[rid]] = row
        else:
            seen_new[rid] = len(appends)
            appends.append(row)
    if updates:
        ws.batch_update([{"range": f"A{rn}:{last}{rn}", "values": [row]}
                         for rn, row in updates.items()])
    if appends:
        start = len(rows) + 2     # header (row 1) + data rows → next empty
        ws.update(f"A{start}:{last}{start + len(appends) - 1}", appends)
    invalidate_cashback_caches()
    return len(updates) + len(appends)   # distinct rules written


def add_mcc_maps_bulk(specs: list[dict]) -> int:
    """Batch add_mcc_map — ONE read + ONE write (seed 429 fix). Skips
    (normalized pattern, mcc) already active (like add_mcc_map) and dedupes
    within the batch. Rows byte-identical to add_mcc_map. Returns # appended.
    """
    if not specs:
        return 0
    ws = _ensure_mcc_map_tab()
    rows = ws.get_all_values()[1:]   # single read
    seen = {
        (_normalize_for_match(r[0]), str(r[1]).strip())
        for r in rows if len(r) > 5 and str(r[5]).upper() == "TRUE"
    }
    appends = []
    for s in specs:
        pat = _normalize_for_match(s["pattern"])
        mcc = str(s["mcc_code"]).strip()
        if not pat or not mcc or (pat, mcc) in seen:
            continue
        seen.add((pat, mcc))
        appends.append([pat, mcc, s.get("mcc_label", ""), s.get("default_category", ""),
                        s.get("priority", 0), "TRUE", s.get("notes", "")])
    if appends:
        start = len(rows) + 2
        last = _last_col_letter(len(MCC_MAP_HEADER))
        ws.update(f"A{start}:{last}{start + len(appends) - 1}", appends)
        invalidate_cashback_caches()
    return len(appends)


def match_mcc(description: str) -> dict | None:
    """Infer MCC from a transaction description. Longest matching pattern wins
    (more specific), mirroring match_keyword_rule. Case/diacritics-insensitive."""
    desc = _normalize_for_match(description)
    if not desc:
        return None
    best, best_len = None, 0
    for m in get_mcc_map():
        p = m["pattern"]
        if p and p in desc and len(p) > best_len:
            best, best_len = m, len(p)
    return best

def extract_keyword_from_description(description: str, specific: bool = False) -> str:
    """Extract keyword from a tx description for MCC pattern matching.

    Args:
      specific: If True, return a multi-word keyword (first 2 alpha tokens)
                for more precise exclusion patterns. If False (default),
                return the first alpha token only (broad matching).
    Examples (specific=False):
      "SHOPEE 2024123456 VN" → "shopee"
      "GRAB*SERVICE 123"     → "grab"
    Examples (specific=True):
      "SHOPEE FOOD ORDER 456" → "shopee food"
      "GRAB FOOD MERCHANT"    → "grab food"
      "SHOPEE 2024123456 VN"  → "shopee" (only 1 alpha token)
    """
    import re
    desc = description.strip()
    if not desc:
        return ""
    tokens = re.split(r'[\s*/\-_.,;:!@#$%^\&()+=]+', desc)
    alpha_tokens = []
    for tok in tokens:
        cleaned = re.sub(r'[^a-zA-Z\u00C0-\u024F]', '', tok)
        if len(cleaned) >= 3:
            alpha_tokens.append(_normalize_for_match(cleaned))
            if not specific and len(alpha_tokens) == 1:
                return alpha_tokens[0]
            if specific and len(alpha_tokens) == 2:
                return " ".join(alpha_tokens)
    if alpha_tokens:
        return " ".join(alpha_tokens[:2]) if specific else alpha_tokens[0]
    return _normalize_for_match(desc.split()[0]) if desc.split() else ""


def resolve_mcc_or_exclusion(description: str) -> dict | None:
    """Resolve whether a description maps to an MCC or an exclusion.

    Checks both the MCC Map and the Exclusion list. Longest matching
    pattern wins (more specific = more accurate). Returns the MCC match
    dict if MCC wins, or None if exclusion wins or no match.

    This implements the self-learning priority matching system:
      - "shopee" (6 chars) in MCC Map → 5262
      - "shopee food" (11 chars) in Exclusion → SKIP
      - For "SHOPEE FOOD ORDER": exclusion wins (11 > 6)
      - For "SHOPEE ELECTRONICS": MCC wins (no exclusion match)
    """
    desc = _normalize_for_match(description)
    if not desc:
        return None

    # MCC match — longest pattern
    mcc_match = match_mcc(description)
    mcc_len = len(mcc_match["pattern"]) if mcc_match else 0

    # Exclusion match — longest pattern
    excl_len = 0
    for pat in get_mcc_exclusions():
        if pat and pat in desc and len(pat) > excl_len:
            excl_len = len(pat)

    # Longest wins: exclusion beats MCC if its pattern is longer (more specific)
    if excl_len > 0 and excl_len >= mcc_len:
        return None  # exclusion wins → treat as "no MCC"

    return mcc_match  # MCC wins (or both None → returns None)


# ── MCC Exclusion (learned "no cashback" decisions) ────────────

MCC_EXCLUSION_HEADER = ["pattern", "created_at", "notes"]

_mcc_exclusion_cache: list[str] | None = None


def _ensure_mcc_exclusion_tab():
    return _ensure_tab_with_header("MCC Exclusions", MCC_EXCLUSION_HEADER, rows=200)


def get_mcc_exclusions(force_refresh: bool = False) -> list[str]:
    """Return normalized excluded patterns (learned 'no cashback')."""
    global _mcc_exclusion_cache
    if force_refresh or _mcc_exclusion_cache is None:
        ws = _ensure_mcc_exclusion_tab()
        rows = ws.get_all_values()[1:]
        _mcc_exclusion_cache = [
            _normalize_for_match(r[0]) for r in rows if r and r[0]
        ]
    return list(_mcc_exclusion_cache)


def is_mcc_excluded(description: str) -> bool:
    """True if any excluded pattern is a substring of description."""
    desc = _normalize_for_match(description)
    if not desc:
        return False
    return any(pat and pat in desc for pat in get_mcc_exclusions())


def add_mcc_exclusion(pattern: str, notes: str = "") -> bool:
    """Add a 'no cashback' exclusion pattern. Idempotent on pattern."""
    global _mcc_exclusion_cache
    pat = _normalize_for_match(pattern)
    if not pat:
        return False
    if pat in get_mcc_exclusions():
        return False
    ws = _ensure_mcc_exclusion_tab()
    next_row = _next_row(ws, col=1)
    _auto_expand(ws, next_row)
    ws.update(f"A{next_row}:C{next_row}", [
        [pat, datetime.utcnow().isoformat(), notes]
    ])
    _mcc_exclusion_cache = None  # bust cache
    return True



# ── Cashback Ledger ────────────────────────────────────────────



def _ledger_from_row(r: list, row_num: int) -> dict:
    def g(idx):
        return r[idx] if len(r) > idx else ""
    return {
        "row_num":         row_num,
        "cashback_id":     g(0),
        "tx_row_num":      int(_to_num(g(1))) if str(g(1)).strip() else None,
        "account_id":      g(2),
        "rule_id":         g(3),
        "mcc_code":        str(g(4)).strip(),
        "eligible_amount": _to_num(g(5)) or 0.0,
        "rate":            _to_num(g(6)) or 0.0,
        "cashback_amount": _to_num(g(7)) or 0.0,
        "cycle":           g(8),
        "capped_flag":     str(g(9)).upper() == "TRUE",
        "status":          str(g(10)).strip().lower(),
        "created_at":      g(11),
        "reason":          g(12),
    }


def append_cashback_rows(rows: list[dict]) -> None:
    """Append cashback ledger lines. Generates cashback_id + created_at."""
    if not rows:
        return
    ws = _ensure_cashback_ledger_tab()
    next_row = _next_row(ws, col=1)
    now = datetime.utcnow().isoformat()
    payload = []
    for j, line in enumerate(rows):
        txn = line.get("tx_row_num")
        payload.append([
            f"CB{txn}_{j + 1}", txn, line.get("account_id", ""),
            line.get("rule_id", ""), line.get("mcc_code", ""),
            line.get("eligible_amount", 0), line.get("rate", 0),
            line.get("cashback_amount", 0), line.get("cycle", ""),
            "TRUE" if line.get("capped_flag") else "FALSE",
            line.get("status", ""), now, line.get("reason", ""),
        ])
    last = _last_col_letter(len(CASHBACK_LEDGER_HEADER))
    _auto_expand(ws, next_row + len(payload) - 1)
    ws.update(f"A{next_row}:{last}{next_row + len(payload) - 1}", payload)


def get_cashback_ledger(account_id: str | None = None, cycle: str | None = None) -> list[dict]:
    """All ledger lines (incl void), optionally filtered by account_id / cycle."""
    ws = _ensure_cashback_ledger_tab()
    rows = ws.get_all_values()[1:]
    out = []
    for i, r in enumerate(rows):
        if not r or not r[0]:
            continue
        rec = _ledger_from_row(r, i + 2)
        if account_id and rec["account_id"] != account_id:
            continue
        if cycle and rec["cycle"] != cycle:
            continue
        out.append(rec)
    return out


def void_cashback_for_tx(tx_row_num: int) -> int:
    """Mark all non-void ledger lines of a tx as `void` (kept for audit)."""
    ws = _ensure_cashback_ledger_tab()
    rows = ws.get_all_values()[1:]
    voided = 0
    for i, r in enumerate(rows):
        if len(r) < 11 or str(r[1]).strip() != str(tx_row_num):
            continue
        if str(r[10]).strip().lower() == "void":
            continue
        ws.update_cell(i + 2, 11, "void")  # col K = status
        voided += 1
    return voided


def promote_pending_to_eligible(account_id: str, cycle: str) -> int:
    """Flip all `pending` lines of an account/cycle to `eligible` (gate opened)."""
    ws = _ensure_cashback_ledger_tab()
    rows = ws.get_all_values()[1:]
    n = 0
    for i, r in enumerate(rows):
        if len(r) < 11 or r[2] != account_id or (r[8] if len(r) > 8 else "") != cycle:
            continue
        if str(r[10]).strip().lower() == "pending":
            ws.update_cell(i + 2, 11, "eligible")
            n += 1
    return n


# ── Cycle / eligible-spend / daily helpers ─────────────────────

def cycle_id(account_id: str, tx_date, statement_day) -> str:
    """Statement-cycle label, e.g. `cake_2026-06`.

    A cycle is `[statement_day prev+1 … statement_day this]`; it is labeled by
    the month it CLOSES in. The statement_day date itself belongs to the cycle
    closing on it (BRD edge case 7). No statement_day → calendar month.
    """
    d = _parse_tx_date(tx_date)
    if d is None:
        return f"{account_id}_unknown"
    if not statement_day:
        return f"{account_id}_{d.strftime('%Y-%m')}"
    if d.day <= int(statement_day):
        return f"{account_id}_{d.strftime('%Y-%m')}"
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return f"{account_id}_{y:04d}-{m:02d}"


def eligible_spend_in_cycle(account_id: str, cycle: str, exclude_tx_row: int | None = None) -> float:
    """Σ eligible-MCC spend in a cycle. Excludes void lines and lines whose MCC
    wasn't eligible (mcc_unknown / mcc_not_eligible). `exclude_tx_row` drops a
    given tx so callers can compute the "before this tx" total for recompute."""
    total = 0.0
    for rec in get_cashback_ledger(account_id, cycle):
        if rec["status"] == "void":
            continue
        if rec["reason"] in ("mcc_unknown", "mcc_not_eligible"):
            continue
        if exclude_tx_row is not None and rec["tx_row_num"] == exclude_tx_row:
            continue
        total += rec["eligible_amount"]
    return total


def _tx_date_for_row(row_num: int):
    """Read a Transactions row's date (col B) → date. None if missing."""
    if not row_num:
        return None
    try:
        ws = _sheet(S.TRANSACTIONS)
    except gspread.WorksheetNotFound:
        return None
    row = ws.row_values(row_num)
    return _parse_tx_date(row[1]) if len(row) > 1 else None


def daily_eligible_count(account_id: str, mcc: str, tx_date,
                         exclude_tx_row: int | None = None) -> int:
    """Count cashback>0 lines of this account+MCC on the same calendar day as
    `tx_date` (by the transaction's own date). `exclude_tx_row` skips a tx so a
    recompute doesn't count itself."""
    target = _parse_tx_date(tx_date)
    if target is None or not mcc:
        return 0
    count = 0
    for rec in get_cashback_ledger(account_id):
        if rec["status"] == "void" or rec["mcc_code"] != str(mcc).strip():
            continue
        if rec["cashback_amount"] <= 0:
            continue
        if exclude_tx_row is not None and rec["tx_row_num"] == exclude_tx_row:
            continue
        if _tx_date_for_row(rec["tx_row_num"]) == target:
            count += 1
    return count


def _mcc_cashback_used(account_id: str, cycle: str, mcc: str,
                       exclude_tx_row: int | None = None) -> float:
    """Cashback already accrued for an MCC this cycle (for per-MCC cap)."""
    if not mcc:
        return 0.0
    total = 0.0
    for rec in get_cashback_ledger(account_id, cycle):
        if rec["status"] == "void" or rec["mcc_code"] != str(mcc).strip():
            continue
        if exclude_tx_row is not None and rec["tx_row_num"] == exclude_tx_row:
            continue
        total += rec["cashback_amount"]
    return total


def _cashback_summary(lines: list[dict], first: bool, blocked: bool, rule: dict | None) -> str:
    """Short note for the transaction reply (FR-2.5 / FR-2.7)."""
    if not lines:
        return ""
    line = lines[0]
    reason = line.get("reason", "")
    if reason in ("mcc_unknown", "mcc_not_eligible"):
        return ""
    name = (rule or {}).get("rule_name", "")
    if reason == "daily_limit":
        return f"🛒 {name} đã hết lượt hoàn hôm nay → giao dịch này 0đ hoàn tiền."
    if reason == "mcc_cap_full":
        return f"{name} đã đạt cap kỳ này — giao dịch này 0đ hoàn tiền."
    txt = f"+{fmt_amount(line['cashback_amount'])} hoàn tiền"
    if first and name:
        txt += f" — {name} đầu tiên hôm nay được hoàn."
    return txt


# ── Orchestrator ───────────────────────────────────────────────

def _empty_cashback_result() -> dict:
    return {"lines": [], "gate_just_opened": False, "daily_limit_first": False,
            "daily_limit_blocked": False, "summary_text": ""}


def compute_and_record_cashback(tx_row_num: int) -> dict:
    """Read a tx → infer MCC → gather cycle state → run the pure engine → write
    Cashback Ledger lines. Idempotent on (tx_row_num, rule): voids prior lines
    before writing. Only `expense` on an active `type=credit` card with config.

    Returns {lines, gate_just_opened, daily_limit_first, daily_limit_blocked,
    summary_text}. Does NOT touch the live tx flow — Phase B wires the hook.
    """
    with tx_write_lock:
        row = get_transaction_row(tx_row_num)
        if not row or len(row) < 8:
            return _empty_cashback_result()
        # Idempotent: void any prior lines for this tx up front, so every early
        # return below (now non-expense / non-VND / no config) also clears stale
        # cashback rows instead of leaving them active. The state reads below all
        # exclude this tx anyway, so voiding early doesn't change their results.
        void_cashback_for_tx(tx_row_num)
        description = row[5] if len(row) > 5 else ""
        amount = _parse_amount(row[7]) if len(row) > 7 and row[7] else 0.0
        tx_date = row[1] if len(row) > 1 else ""
        account_id = (row[16] if len(row) > 16 else "").strip()
        ledger_tx_type = (row[17] if len(row) > 17 else "expense").strip() or "expense"

        if not account_id:
            return _empty_cashback_result()
        account = find_account_by_id(account_id)
        if not account or account.get("type") != "credit":
            return _empty_cashback_result()
        if ledger_tx_type != "expense":   # skip cc_payment / income / transfer
            return _empty_cashback_result()
        if amount <= 0:   # refund/correction stored as negative expense (FR-2.3)
            return _empty_cashback_result()
        # Cashback rules + tiers are VND. A foreign-currency purchase must not be
        # summed as VND (would wrongly earn cashback / open the spend gate).
        if row_currency(row) != "VND":
            return _empty_cashback_result()
        # Deferred to Phase B (founder review 2026-06-09) — known edge cases the
        # compute-only orchestrator does NOT handle yet; the `/cashback recompute
        # <cc_id> [cycle]` rescue command (Phase B) covers reshuffles:
        #   - out-of-order live arrivals don't rebuild the day;
        #   - the gate only promotes (pending→eligible), never demotes;
        #   - recompute_cashback_for_tx rebuilds only the same DAY, not the whole
        #     statement cycle (cross-day MCC-cap dependents stay stale);
        #   - rule effective_from/effective_to windows are not enforced (§4.3
        #     field; §4.6 compute path omits it; Cake doesn't use it).
        config = get_card_config(account_id)
        if not config or not config.get("active", False):
            return _empty_cashback_result()

        mcc_match = resolve_mcc_or_exclusion(description)
        mcc = mcc_match["mcc_code"] if mcc_match else ""
        rules = get_cashback_rules(account_id)
        matched_rule = next(
            (r for r in rules if r["match_type"] == "mcc" and r["match_value"] == mcc),
            None,
        ) if mcc else None
        tier_set = matched_rule["per_tx_cap_tier"] if matched_rule else ""
        tiers = get_cashback_tiers(tier_set) if tier_set else []

        cycle = cycle_id(account_id, tx_date, account.get("statement_day"))
        mcc_cycle_used = _mcc_cashback_used(account_id, cycle, mcc, exclude_tx_row=tx_row_num)
        daily_count = daily_eligible_count(account_id, mcc, tx_date, exclude_tx_row=tx_row_num)
        eligible_before = eligible_spend_in_cycle(account_id, cycle, exclude_tx_row=tx_row_num)

        lines = compute_cashback(
            tx={"amount": amount}, mcc=mcc, rules=rules, tiers=tiers,
            card_config=config, mcc_cycle_used=mcc_cycle_used,
            daily_count=daily_count, eligible_spend_before_tx=eligible_before,
        )
        append_cashback_rows([
            {**line, "tx_row_num": tx_row_num, "account_id": account_id, "cycle": cycle}
            for line in lines
        ])

        # Activation gate (this tx pushes the cycle total over the threshold).
        # Count this tx toward the gate only when the engine actually produced an
        # eligible-MCC line — same rule as eligible_spend_in_cycle (which drops
        # mcc_unknown / mcc_not_eligible, e.g. below-min-tx). Keeps the gate
        # increment consistent with the cycle-spend total it's compared against.
        counts_for_gate = any(
            l["reason"] not in ("mcc_unknown", "mcc_not_eligible") for l in lines
        )
        min_spend = float(config.get("min_eligible_spend") or 0)
        eligible_after = eligible_before + (amount if counts_for_gate else 0)
        gate_just_opened = bool(min_spend > 0 and eligible_before < min_spend <= eligible_after)
        if gate_just_opened:
            promote_pending_to_eligible(account_id, cycle)

        # Daily-limit notices (FR-2.7): general for any rule with a daily cap.
        max_per_day = int((matched_rule or {}).get("max_eligible_tx_per_day") or 0)
        daily_limit_first = any(
            l["cashback_amount"] > 0 and max_per_day > 0 and daily_count == 0
            for l in lines
        )
        daily_limit_blocked = any(l["reason"] == "daily_limit" for l in lines)

        return {
            "lines": lines,
            "gate_just_opened": gate_just_opened,
            "daily_limit_first": daily_limit_first,
            "daily_limit_blocked": daily_limit_blocked,
            "summary_text": _cashback_summary(lines, daily_limit_first,
                                              daily_limit_blocked, matched_rule),
            "cycle": cycle,
            "account_id": account_id,
        }


def recompute_cashback_for_tx(tx_row_num: int) -> dict:
    """Rebuild cashback for the tx's whole statement CYCLE, in timestamp order.

    Recomputing the entire same-account cycle (not just the day, not just
    same-MCC) is deliberate — two dependencies span the rebuild:
      - daily limit: clean-state + chronological order makes the earliest
        eligible tx win the day's single slot regardless of webhook arrival /
        write order (out-of-order arrivals);
      - per-MCC cycle cap: voiding/changing one tx frees cap for later tx on
        OTHER days of the same cycle, which must be refreshed (cross-day).
    All cycle lines are voided first, then recomputed strictly chronologically
    so each tx sees only correctly-settled earlier siblings.
    """
    row = get_transaction_row(tx_row_num)
    account_id = (row[16] if row and len(row) > 16 else "").strip()
    tx_date = row[1] if row and len(row) > 1 else ""
    if not account_id or _parse_tx_date(tx_date) is None:
        return compute_and_record_cashback(tx_row_num)

    account = find_account_by_id(account_id)
    if not account or account.get("type") != "credit":
        return compute_and_record_cashback(tx_row_num)  # non-credit → per-tx (voids + empty)
    statement_day = account.get("statement_day")
    cycle = cycle_id(account_id, tx_date, statement_day)
    # Read-once rebuild (Sheets 429 fix): read Transactions + ledger ONCE and
    # replay the cycle in memory instead of O(N) per-row ledger reads. Holds the
    # reentrant write lock across the whole void+append so concurrent webhooks
    # for the same cycle can't interleave.
    with tx_write_lock:
        return _recompute_cycle_in_memory(account_id, account, statement_day, cycle, tx_row_num)


def _recompute_cycle_in_memory(account_id: str, account: dict, statement_day,
                               cycle: str, target_tx_row: int) -> dict:
    """Read-once, in-memory rebuild of a whole statement cycle's cashback.

    Reads the Transactions tab and the Cashback Ledger ONCE each, then replays
    the exact per-tx logic of compute_and_record_cashback in chronological order
    with running in-memory state (mcc_used / daily_count / eligible_spend),
    batch-voids the old cycle rows and batch-appends the rebuilt ones. Output is
    byte-identical to the old per-tx recompute (parity) — only the read pattern
    changes (O(1) ledger reads instead of ~4×N). Caller holds tx_write_lock.

    Returns the result dict for `target_tx_row` (same shape as
    compute_and_record_cashback) for the webhook reply.
    """
    config = get_card_config(account_id)
    active = bool(config and config.get("active", False))
    min_spend = float((config or {}).get("min_eligible_spend") or 0)

    # 1. Transactions read-once → cycle expense items, chronological. Force a
    #    fresh read: the rebuild must see a just-appended/updated tx, never a
    #    still-valid TTL cache that could omit it (Codex round 02).
    cycle_items = []  # (ts, row_num, amount, description, currency)
    for i, r in enumerate(_get_tx_rows(force_refresh=True)):
        row_num = i + 2
        if (r[16] if len(r) > 16 else "").strip() != account_id:
            continue
        if ((r[17] if len(r) > 17 else "").strip() or "expense") != "expense":
            continue
        ts = r[1] if len(r) > 1 else ""
        if cycle_id(account_id, ts, statement_day) != cycle:
            continue
        amount = _parse_amount(r[7]) if len(r) > 7 and r[7] else 0.0
        cycle_items.append((ts, row_num, amount,
                            r[5] if len(r) > 5 else "", row_currency(r)))
    cycle_items.sort(key=lambda x: x[0])

    void_targets = {it[1] for it in cycle_items}
    void_targets.add(target_tx_row)  # void target even if now non-expense (parity)

    # 2. Ledger read-once → batch-void old cycle rows; find append start.
    ledger_ws = _ensure_cashback_ledger_tab()
    all_ledger = ledger_ws.get_all_values()
    void_updates = []
    for li, lr in enumerate(all_ledger[1:]):
        if len(lr) < 11 or not lr[0]:
            continue
        txn = int(_to_num(lr[1])) if str(lr[1]).strip() else None
        if txn in void_targets and str(lr[10]).strip().lower() != "void":
            void_updates.append({"range": f"K{li + 2}:K{li + 2}", "values": [["void"]]})
    append_start = len(all_ledger) + 1

    # 3. Rebuild in memory (chronological running state) — same guards + engine
    #    as compute_and_record_cashback (amount>0, VND, eligible MCC, gate).
    rules = get_cashback_rules(account_id)
    tier_sets = {r["per_tx_cap_tier"] for r in rules if r.get("per_tx_cap_tier")}
    tiers_by_set = {ts: get_cashback_tiers(ts) for ts in tier_sets}

    mcc_used: dict = {}
    daily_cnt: dict = {}
    elig_spend = 0.0
    new_rows = []   # list[(cashback_id, line-dict)]
    target_result = _empty_cashback_result()

    for ts, row_num, amount, desc, cur in cycle_items:
        if not active or amount <= 0 or cur != "VND":
            continue  # no line (matches compute_and_record early return); already voided
        mcc_match = resolve_mcc_or_exclusion(desc)
        mcc = mcc_match["mcc_code"] if mcc_match else ""
        matched_rule = next(
            (r for r in rules if r["match_type"] == "mcc" and r["match_value"] == mcc), None
        ) if mcc else None
        tiers = tiers_by_set.get(matched_rule["per_tx_cap_tier"], []) if matched_rule else []
        d = _parse_tx_date(ts)
        eligible_before = elig_spend
        dc = daily_cnt.get((mcc, d), 0)
        lines = compute_cashback(
            tx={"amount": amount}, mcc=mcc, rules=rules, tiers=tiers, card_config=config,
            mcc_cycle_used=mcc_used.get(mcc, 0.0), daily_count=dc,
            eligible_spend_before_tx=eligible_before,
        )
        counts_for_gate = any(l["reason"] not in ("mcc_unknown", "mcc_not_eligible") for l in lines)
        if counts_for_gate:
            elig_spend += amount
        for j, l in enumerate(lines):
            mcc_used[mcc] = mcc_used.get(mcc, 0.0) + l["cashback_amount"]
            if l["cashback_amount"] > 0:
                daily_cnt[(mcc, d)] = daily_cnt.get((mcc, d), 0) + 1
            new_rows.append((f"CB{row_num}_{j + 1}",
                             {**l, "tx_row_num": row_num, "account_id": account_id, "cycle": cycle}))
        if row_num == target_tx_row:
            max_per_day = int((matched_rule or {}).get("max_eligible_tx_per_day") or 0)
            first = any(l["cashback_amount"] > 0 and max_per_day > 0 and dc == 0 for l in lines)
            blocked = any(l["reason"] == "daily_limit" for l in lines)
            after = eligible_before + (amount if counts_for_gate else 0)
            target_result = {
                "lines": lines,
                "gate_just_opened": bool(min_spend > 0 and eligible_before < min_spend <= after),
                "daily_limit_first": first,
                "daily_limit_blocked": blocked,
                "summary_text": _cashback_summary(lines, first, blocked, matched_rule),
                "cycle": cycle,
                "account_id": account_id,
            }

    # Gate promote (once): if the cycle reached the gate, earlier pending lines
    # become eligible — mirrors promote_pending_to_eligible after the walk.
    if min_spend > 0 and elig_spend >= min_spend:
        for _cid, l in new_rows:
            if l.get("status") == "pending":
                l["status"] = "eligible"
        for l in target_result["lines"]:
            if l.get("status") == "pending":
                l["status"] = "eligible"

    # 4. Write: void old (batch) then append rebuilt rows (batch).
    if void_updates:
        ledger_ws.batch_update(void_updates)
    if new_rows:
        now = datetime.utcnow().isoformat()
        last = _last_col_letter(len(CASHBACK_LEDGER_HEADER))
        payload = [[
            cid, l["tx_row_num"], l["account_id"], l.get("rule_id", ""),
            l.get("mcc_code", ""), l.get("eligible_amount", 0), l.get("rate", 0),
            l.get("cashback_amount", 0), l.get("cycle", ""),
            "TRUE" if l.get("capped_flag") else "FALSE", l.get("status", ""),
            now, l.get("reason", ""),
        ] for cid, l in new_rows]
        _auto_expand(ledger_ws, append_start + len(payload) - 1)
        ledger_ws.update(f"A{append_start}:{last}{append_start + len(payload) - 1}", payload)

    return target_result


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
# Row location travels with the state value.  Once a message has loaded its
# state, subsequent set_state() calls update that known row without first
# rereading the whole Bot State worksheet.
_state_row_cache: dict = {}  # chat_id (str) -> 1-based sheet row


def get_state(chat_id: str) -> dict | None:
    import json
    chat_id_s = str(chat_id)
    # Cache hit
    if chat_id_s in _state_cache:
        return _state_cache[chat_id_s]
    # Cache miss → đọc sheet 1 lần, cache lại
    ws = _sheet(S.BOT_STATE)
    rows = ws.get_all_values()[1:]
    for index, r in enumerate(rows, start=2):
        if len(r) >= 2 and str(r[0]) == chat_id_s:
            _state_row_cache[chat_id_s] = index
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
    payload = json.dumps(obj, ensure_ascii=False)
    now_str = datetime.utcnow().isoformat()

    row_num = _state_row_cache.get(chat_id_s)
    if row_num is None:
        # A cold write still needs one lookup to decide update vs append, but
        # warm command/callback flows avoid this full-sheet read entirely.
        rows = ws.get_all_values()[1:]
        for index, r in enumerate(rows, start=2):
            if len(r) >= 1 and str(r[0]) == chat_id_s:
                row_num = index
                break
        if row_num is None:
            row_num = len(rows) + 2
            ws.append_row([chat_id_s, payload, now_str])
            _state_row_cache[chat_id_s] = row_num
            _state_cache[chat_id_s] = obj
            return

    # Batch B:C trong 1 update thay vì 2 update_cell
    ws.update(f"B{row_num}:C{row_num}", [[payload, now_str]])
    _state_row_cache[chat_id_s] = row_num
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
        # Cols Q/R — cashback wallet linkage (Phase B). Read pad-safe so legacy
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
    cashback + /report group transactions by. Must be 1–28 (days 29–31 don't
    exist in every month, so they'd make the cycle boundary ambiguous — same
    bound the onboarding prompt documents). Returns False for a missing /
    non-credit account or an out-of-range day; `due_day` is informational only
    (shown in /report; not used by cycle math) and skipped when None/invalid.

    Caller is responsible for recomputing affected cashback cycles after a
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
