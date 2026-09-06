"""
handlers/email_parser.py — Parse bank notification emails thành transaction data

Supported banks:
  - Cake by VPBank               — VND

Adding a bank is two things: its notification sender in BANK_SENDERS (and in
google_apps_script.js, so the forwarder picks the mail up), and a _parse_<bank>
returning the dict shape below. Follow _parse_cake as the worked example.

Flow:
  Google Apps Script nhận email → POST /webhook/email
  → parse_email() → dict giống SePay payload (có thêm field "currency")
  → handle_sepay_webhook() xử lý như bình thường
"""

import re
import hashlib
from datetime import datetime


# ─── Sender → parser mapping ──────────────────────────────────────────────────

BANK_SENDERS = {
    "no-reply@cake.vn":                    "cake",
    "notification@cake.vn":                "cake",
    "noreply@cake.vn":                     "cake",
}


def parse_email(from_addr: str, subject: str, body: str, date: str) -> dict | None:
    """
    Parse một email thông báo ngân hàng thành dict giống SePay payload.
    Trả về None nếu không nhận ra format hoặc không phải email giao dịch.

    Hỗ trợ 2 trường hợp:
    1. Email gốc từ bank → match qua sender header
    2. Email forward từ Gmail account khác (vd forwarder-account → your-account):
       header `From:` lúc này là forwarder, sender thật chỉ nằm trong body
       sau dòng "Forwarded message". Hàm sẽ scan body để extract sender gốc.
    """
    # Normalize sender (lấy phần email trong "Name <email>")
    sender = _extract_email_addr(from_addr).lower()

    bank = _bank_for_email(from_addr, body)
    if bank and not _route_by_sender(sender):
        original_sender = _extract_forwarded_sender(body)
        print(f"[email_parser] detected forwarded mail: "
              f"{sender!r} → original sender {original_sender!r} → bank={bank!r}")

    if bank is None:
        print(f"[email_parser] unknown sender: {sender!r}")
        return None

    # Strip "Fwd:" / "Fw:" prefix khỏi subject — parser sau dùng subject để
    # confirm transaction kind.
    clean_subject = re.sub(r'^\s*(?:Fwd?:?\s*)+', '', subject, flags=re.IGNORECASE)

    if bank == "cake":
        return _parse_cake(clean_subject, body, date)

    return None


def _route_by_sender(sender: str) -> str | None:
    """Map email địa chỉ → bank code. Return None nếu không match."""
    bank = BANK_SENDERS.get(sender)
    if bank is not None:
        return bank
    domain = sender.split("@")[-1] if "@" in sender else ""
    if "cake" in domain:
        return "cake"
    return None


def _bank_for_email(from_addr: str, body: str) -> str | None:
    """Resolve a supported bank from the sender or a forwarded-message body."""
    sender = _extract_email_addr(from_addr).lower()
    bank = _route_by_sender(sender)
    if bank:
        return bank
    forwarded = _extract_forwarded_sender(body)
    return _route_by_sender(forwarded.lower()) if forwarded else None


def is_transaction_shaped_bank_email(from_addr: str, subject: str, body: str) -> bool:
    """Whether a supported email claims to be a transaction notification.

    Statements and newsletters can safely be acknowledged. A message with the
    narrow markers that a parser uses, but an unfamiliar format, remains
    retryable rather than silently discarding a possible financial event.
    """
    bank = _bank_for_email(from_addr, body)
    clean_subject = re.sub(r'^\s*(?:Fwd?:?\s*)+', '', subject, flags=re.IGNORECASE).lower()
    if bank == "cake":
        if any(marker in clean_subject for marker in (
            "biến động", "bien dong", "giao dịch", "giao dich", "thông báo", "thong bao",
        )):
            return True
        return bool(re.search(
            r'(?:số tiền|giá trị|giao dịch)[:\s]|^[+-][\d,.]+\s*(?:đ|d|vnd)',
            body.strip(), re.IGNORECASE | re.MULTILINE,
        ))
    return False


def _extract_forwarded_sender(body: str) -> str | None:
    """
    Tìm sender gốc trong body của email đã forward.

    Gmail forward template (zh & en):
      ---------- Forwarded message ---------
      From: <Display Name> <email@domain.com>
      Date: ...
      Subject: ...

    Trả về địa chỉ email (chỉ phần trong dấu < >, hoặc bare addr).
    """
    # Tìm block "Forwarded message" — Gmail dùng dashes hoặc html h-prefix
    fwd_idx = -1
    for marker in ("Forwarded message", "Forwarded Message", "tin nhắn được chuyển tiếp"):
        idx = body.find(marker)
        if idx >= 0:
            fwd_idx = idx
            break
    if fwd_idx < 0:
        return None

    # Trong block sau marker, tìm dòng "From: ..."
    fwd_block = body[fwd_idx:fwd_idx + 2000]  # đủ rộng cho full header
    m = re.search(r'^\s*From\s*:\s*(.+)$', fwd_block, re.MULTILINE | re.IGNORECASE)
    if not m:
        return None

    raw = m.group(1).strip()
    # Lấy email trong dấu < > nếu có
    angle = re.search(r'<\s*([^>\s]+@[^>\s]+)\s*>', raw)
    if angle:
        return angle.group(1).strip()
    # Fallback: tìm bare email pattern
    bare = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', raw)
    return bare.group(1).strip() if bare else None


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
      Tại:         PAYOO*SIEUTHIABC_1234 TP HCM VN
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

    # Cake has 2 product lines, distinguished by email body shape:
    #   - Format 1 (bank account biến động): starts with ±amount, has
    #     "Số dư", "Từ", "Nội dung", "Lúc" lines.
    #   - Format 2 (credit card POS/QR payment): has "Giao dịch: Thanh toán"
    #     header, no signed amount prefix, has "Tại:" / "Vào lúc:" / "Tình trạng:".
    # The merchant-ref suffix (_NNNN) is a Payoo merchant code, NOT a card
    # last-4 — different merchants will yield different IDs even for the
    # same physical card. So we don't try to extract a card identifier.
    # Instead: one hint per product line (`cake_main` for bank, `cake_cc`
    # for credit card). User maps each to its own account on first sight.
    body_lower = body.lower()
    is_cc_payment = bool(
        re.search(r'giao\s*d[ịi]ch[:\s]+thanh\s*to[áa]n', body, re.IGNORECASE)
        or any(kw in body_lower for kw in (
            "thanh toán pos", "thanh toan pos",
            "thanh toán qr", "thanh toan qr",
            "the tin dung", "thẻ tín dụng",
        ))
    )
    account_hint = "cake_cc" if is_cc_payment else "cake_main"

    return {
        "transferAmount":  amount,
        "transferType":    tx_type,
        "currency":        "VND",
        "description":     description,
        "content":         description,
        "transactionDate": tx_date,
        "referenceCode":   ref_code,
        "_source":         "email_cake",
        "_account_hint":   account_hint,
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
