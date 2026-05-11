"""
handlers/email_parser.py — Parse bank notification emails thành transaction data

Supported banks:
  - Techcombank (TCB)
  - Cake by VPBank

Flow:
  Google Apps Script nhận email → POST /webhook/email
  → parse_email() → dict giống SePay payload
  → handle_sepay_webhook() xử lý như bình thường
"""

import re
import hashlib
from datetime import datetime


# ─── Sender → parser mapping ──────────────────────────────────────────────────

BANK_SENDERS = {
    "automail@techcombank.com.vn": "tcb",
    "ebank@techcombank.com.vn":    "tcb",
    "no-reply@techcombank.com.vn": "tcb",
    "thongbao@techcombank.com.vn": "tcb",
    "no-reply@cake.vn":            "cake",
    "notification@cake.vn":        "cake",
    "noreply@cake.vn":             "cake",
}


def parse_email(from_addr: str, subject: str, body: str, date: str) -> dict | None:
    """
    Parse một email thông báo ngân hàng thành dict giống SePay payload.
    Trả về None nếu không nhận ra format hoặc không phải email giao dịch.
    """
    # Normalize sender (lấy phần email trong "Name <email>")
    sender = _extract_email_addr(from_addr).lower()

    bank = BANK_SENDERS.get(sender)
    if bank is None:
        # Thử match domain
        domain = sender.split("@")[-1] if "@" in sender else ""
        if "techcombank" in domain:
            bank = "tcb"
        elif "cake" in domain:
            bank = "cake"

    if bank is None:
        print(f"[email_parser] unknown sender: {sender!r}")
        return None

    if bank == "tcb":
        return _parse_tcb(subject, body, date)
    elif bank == "cake":
        return _parse_cake(subject, body, date)

    return None


# ─── Techcombank parser ────────────────────────────────────────────────────────

def _parse_tcb(subject: str, body: str, date: str) -> dict | None:
    """
    TCB email format (plain text):
      Tài khoản: ****1234
      Giao dịch: Tiền ra / Tiền vào
      Số tiền GD: 500,000 VND
      Số dư TK:   2,500,000 VND
      Nội dung:   NGUYEN VAN A CHUYEN TIEN
      Thời gian:  15/01/2024 14:30:25
    """
    # Chỉ xử lý email thông báo giao dịch
    subject_lower = subject.lower()
    if not any(kw in subject_lower for kw in [
        "biến động", "bien dong", "giao dịch", "giao dich",
        "số dư", "so du", "thông báo tài khoản"
    ]):
        print(f"[email_parser][tcb] skipping non-transaction subject: {subject!r}")
        return None

    # Tìm số tiền — nhiều format khác nhau
    amount_patterns = [
        r'Số tiền\s*(?:GD|giao dịch)?[:\s]+([+-]?[\d,\.]+)\s*(?:VND|đ|vnd)',
        r'(?:Tiền ra|Tiền vào)[:\s]+([+-]?[\d,\.]+)\s*(?:VND|đ|vnd)',
        r'Amount[:\s]+([+-]?[\d,\.]+)',
    ]
    amount_str = None
    for pattern in amount_patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            amount_str = m.group(1)
            break

    if not amount_str:
        print(f"[email_parser][tcb] could not find amount in body")
        return None

    amount = _parse_amount_str(amount_str)

    # Xác định chiều giao dịch
    tx_type = "out"  # default
    if re.search(r'Tiền vào|tiền vào|credit|Credit|CREDIT', body):
        tx_type = "in"
    elif re.search(r'Tiền ra|tiền ra|debit|Debit|DEBIT', body):
        tx_type = "out"
    elif amount_str.startswith("+"):
        tx_type = "in"
    elif amount_str.startswith("-"):
        tx_type = "out"

    # Nội dung giao dịch
    desc_patterns = [
        r'Nội dung[:\s]+(.+?)(?:\n|Số dư|$)',
        r'Description[:\s]+(.+?)(?:\n|$)',
        r'Diễn giải[:\s]+(.+?)(?:\n|$)',
    ]
    description = "Giao dịch TCB"
    for pattern in desc_patterns:
        m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if m:
            description = m.group(1).strip()[:200]  # max 200 chars
            break

    # Thời gian giao dịch
    tx_date = _parse_tcb_date(body) or date

    # Tạo ref_code ổn định
    ref_code = (
        _find_ref_code(body)
        or hashlib.md5(f"{amount}|{description}|{tx_date}".encode()).hexdigest()[:16]
    )

    # Bank account ID — TCB email có "Tài khoản: ****1234"
    last4 = _extract_account_last4(body)
    bank_account = f"TCB-{last4}" if last4 else "TCB"

    return {
        "transferAmount":  amount,
        "transferType":    tx_type,
        "description":     description,
        "content":         description,
        "transactionDate": tx_date,
        "referenceCode":   ref_code,
        "bankAccount":     bank_account,
        "_source":         "email_tcb",
    }


def _parse_tcb_date(body: str) -> str | None:
    patterns = [
        r'Thời gian[:\s]+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})',
        r'Thời gian[:\s]+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})',
        r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})',
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            try:
                # Convert "15/01/2024 14:30:25" → ISO format
                dt = datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
                return dt.isoformat()
            except ValueError:
                try:
                    dt = datetime.strptime(raw, "%d/%m/%Y %H:%M")
                    return dt.isoformat()
                except ValueError:
                    return raw
    return None


# ─── Cake by VPBank parser ────────────────────────────────────────────────────

def _parse_cake(subject: str, body: str, date: str) -> dict | None:
    """
    Cake email — 2 formats:

    Format 1 — Tài khoản/biến động số dư:
      Body bắt đầu bằng +/-amount, sau đó Số dư / Từ / Nội dung / Lúc

    Format 2 — Thẻ tín dụng (từ email thực tế):
      Giao dịch:   Thanh toán POS
      Giá trị:     45.000 đ
      Vào lúc:     12:34 03/05/2026
      Tại:         PAYOO*BACHHOAXANH_9272 TP THU DUC VN
      Tình trạng:  Thành công
    """
    subject_lower = subject.lower()
    if not any(kw in subject_lower for kw in [
        "biến động", "bien dong", "giao dịch", "giao dich",
        "thông báo", "thong bao", "cake"
    ]):
        print(f"[email_parser][cake] skipping subject: {subject!r}")
        return None

    # ── Amount ──────────────────────────────────────────────────
    amount_patterns = [
        r'^([+-][\d,\.]+(?:đ|d|VND))',                          # format 1: đầu body
        r'Số tiền[:\s]+([+-]?[\d,\.]+\s*(?:đ|d|VND))',
        r'Giá trị[:\s]+([\d,\.]+\s*(?:đ|d|VND))',              # format 2: "Giá trị: 45.000 đ"
        r'([+-][\d,\.]+)\s*(?:đ|VND)',
    ]
    amount_str = None
    for pattern in amount_patterns:
        m = re.search(pattern, body.strip(), re.IGNORECASE | re.MULTILINE)
        if m:
            amount_str = m.group(1)
            break

    if not amount_str:
        print(f"[email_parser][cake] could not find amount")
        return None

    amount = _parse_amount_str(amount_str)

    # ── Transaction type ─────────────────────────────────────────
    # Format 1: xác định từ dấu +/-
    # Format 2: thẻ tín dụng "Thanh toán" luôn là out; hoàn tiền là in
    if amount_str.strip().startswith("+"):
        tx_type = "in"
    elif amount_str.strip().startswith("-"):
        tx_type = "out"
    else:
        # Format 2 — không có dấu, xác định từ loại giao dịch
        gd_match = re.search(r'Giao dịch[:\s]+(.+?)(?:\n|$)', body, re.IGNORECASE)
        gd_text = gd_match.group(1).lower().strip() if gd_match else ""
        if any(kw in gd_text for kw in ["hoàn", "hoan", "refund", "tiền vào", "tien vao"]):
            tx_type = "in"
        else:
            tx_type = "out"  # Thanh toán POS / QR / online đều là out

    # ── Description ──────────────────────────────────────────────
    desc_patterns = [
        r'Tại[:\s]+(.+?)(?:\n|Tình trạng|$)',                  # format 2: merchant name
        r'Nội dung[:\s]+(.+?)(?:\n|Lúc|Số dư|$)',
        r'Từ[:\s]+(.+?)(?:\n|$)',
        r'Giao dịch[:\s]+(.+?)(?:\n|$)',                       # format 2 fallback
        r'Description[:\s]+(.+?)(?:\n|$)',
    ]
    description = "Giao dịch Cake"
    for pattern in desc_patterns:
        m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()[:200]
            if val:
                description = val
                break

    # ── Date ────────────────────────────────────────────────────
    tx_date = _parse_cake_date(body) or date

    ref_code = (
        _find_ref_code(body)
        or hashlib.md5(f"{amount}|{description}|{tx_date}".encode()).hexdigest()[:16]
    )

    # Bank account ID — Cake debit (format 1) thường có acc number, credit
    # card (format 2) có "Thẻ: ****5678". Nếu cả 2 đều miss → fallback "Cake".
    last4 = _extract_account_last4(body)
    if last4:
        # Phân biệt thẻ tín dụng vs tài khoản gửi → giúp user thấy rõ trong /banks
        is_card = bool(re.search(r'Thẻ|the|Card', body, re.IGNORECASE))
        bank_account = f"Cake-Card-{last4}" if is_card else f"Cake-{last4}"
    else:
        bank_account = "Cake"

    return {
        "transferAmount":  amount,
        "transferType":    tx_type,
        "description":     description,
        "content":         description,
        "transactionDate": tx_date,
        "referenceCode":   ref_code,
        "bankAccount":     bank_account,
        "_source":         "email_cake",
    }


def _parse_cake_date(body: str) -> str | None:
    patterns = [
        # Format 2: "Vào lúc: 12:34 03/05/2026"
        (r'Vào lúc[:\s]+(\d{2}:\d{2})\s+(\d{2}/\d{2}/\d{4})', "split"),
        # Format 1: "Lúc: 15/01/2024 14:30"
        (r'Lúc[:\s]+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', "normal"),
        (r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', "normal"),
        (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', "iso"),
    ]
    for pattern, fmt in patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            try:
                if fmt == "split":
                    # group(1)=HH:MM, group(2)=DD/MM/YYYY
                    raw = f"{m.group(2)} {m.group(1)}"
                    dt = datetime.strptime(raw, "%d/%m/%Y %H:%M")
                    return dt.isoformat()
                elif fmt == "normal":
                    raw = m.group(1).strip()
                    for fmt_str in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
                        try:
                            return datetime.strptime(raw, fmt_str).isoformat()
                        except ValueError:
                            continue
                elif fmt == "iso":
                    return m.group(1)
            except ValueError:
                continue
    return None


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _extract_email_addr(from_str: str) -> str:
    """'Bank Name <email@bank.com>' → 'email@bank.com'"""
    m = re.search(r'<([^>]+)>', from_str)
    return m.group(1) if m else from_str.strip()


def _parse_amount_str(s: str) -> float:
    """'500,000 VND' hoặc '-50.000đ' → float"""
    # Xóa ký tự không phải số và dấu chấm/phẩy/dấu trừ
    cleaned = re.sub(r'[^\d,\.\-\+]', '', s.strip())
    # Xác định separator: nếu kết thúc bằng 3 chữ số sau dấu phẩy → dấu phẩy là thousand sep
    if re.search(r',\d{3}$', cleaned):
        cleaned = cleaned.replace(',', '')
    elif re.search(r'\.\d{3}$', cleaned):
        cleaned = cleaned.replace('.', '')
    else:
        cleaned = cleaned.replace(',', '')
    try:
        return abs(float(cleaned))
    except ValueError:
        return 0.0


def _find_ref_code(body: str) -> str | None:
    """Tìm mã tham chiếu / transaction ID trong body."""
    patterns = [
        r'Mã GD[:\s]+([A-Z0-9]{8,20})',
        r'Reference[:\s]+([A-Z0-9]{8,20})',
        r'Transaction ID[:\s]+([A-Z0-9]{8,20})',
        r'Số tham chiếu[:\s]+([A-Z0-9]{8,20})',
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_account_last4(body: str) -> str:
    """Trích last 4 chữ số của số tài khoản / thẻ trong email body.

    Bank email thường mask số TK kiểu "****1234" / "x1234" / "Tài khoản: ...1234".
    Trả về '' nếu không tìm thấy — caller fallback sang tên bank thuần.
    """
    patterns = [
        r'Tài khoản[^\n:]*:[^\n]*?(\d{4})\b',
        r'Số tài khoản[^\n:]*:[^\n]*?(\d{4})\b',
        r'Thẻ[^\n:]*:[^\n]*?(\d{4})\b',
        r'Account[^\n:]*:[^\n]*?(\d{4})\b',
        r'Card[^\n:]*:[^\n]*?(\d{4})\b',
        r'\*{2,}\s*(\d{4})\b',          # generic "****1234"
        r'[xX]{2,}\s*(\d{4})\b',        # generic "xxxx1234"
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""
