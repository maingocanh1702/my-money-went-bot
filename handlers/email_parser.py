"""
handlers/email_parser.py — Parse bank notification emails thành transaction data

Supported banks:
  - Techcombank (TCB)            — VND
  - Cake by VPBank               — VND
  - Hang Seng Bank (Hong Kong)   — HKD (outgoing transfers only)

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
    "automail@techcombank.com.vn":         "tcb",
    "ebank@techcombank.com.vn":            "tcb",
    "no-reply@techcombank.com.vn":         "tcb",
    "thongbao@techcombank.com.vn":         "tcb",
    "no-reply@cake.vn":                    "cake",
    "notification@cake.vn":                "cake",
    "noreply@cake.vn":                     "cake",
    "hangseng@infoservices.hangseng.com":  "hangseng",
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

    bank = _route_by_sender(sender)

    # Nếu sender không match bank trực tiếp, thử detect forwarded email
    if bank is None:
        original_sender = _extract_forwarded_sender(body)
        if original_sender:
            bank = _route_by_sender(original_sender.lower())
            if bank:
                print(f"[email_parser] detected forwarded mail: "
                      f"{sender!r} → original sender {original_sender!r} → bank={bank!r}")

    if bank is None:
        print(f"[email_parser] unknown sender: {sender!r}")
        return None

    # Strip "Fwd:" / "Fw:" prefix khỏi subject — parser sau dùng subject để
    # confirm transaction kind.
    clean_subject = re.sub(r'^\s*(?:Fwd?:?\s*)+', '', subject, flags=re.IGNORECASE)

    if bank == "tcb":
        return _parse_tcb(clean_subject, body, date)
    elif bank == "cake":
        return _parse_cake(clean_subject, body, date)
    elif bank == "hangseng":
        return _parse_hangseng(clean_subject, body, date)

    return None


def _route_by_sender(sender: str) -> str | None:
    """Map email địa chỉ → bank code. Return None nếu không match."""
    bank = BANK_SENDERS.get(sender)
    if bank is not None:
        return bank
    domain = sender.split("@")[-1] if "@" in sender else ""
    if "techcombank" in domain:
        return "tcb"
    if "cake" in domain:
        return "cake"
    if "hangseng" in domain or "infoservices.hangseng" in domain:
        return "hangseng"
    return None


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

    # Extract masked account number (Tài khoản: ****1234) for resolver
    account_hint = None
    acct_m = re.search(r'Tài khoản\s*[:#]?\s*([\*xX\d\-]{4,30})',
                       body, re.IGNORECASE)
    if acct_m:
        account_hint = acct_m.group(1).strip()

    return {
        "transferAmount":  amount,
        "transferType":    tx_type,
        "currency":        "VND",
        "description":     description,
        "content":         description,
        "transactionDate": tx_date,
        "referenceCode":   ref_code,
        "_source":         "email_tcb",
        "_account_hint":   account_hint or "",
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


# ─── Hang Seng Bank parser (Hong Kong, HKD) ───────────────────────────────────

# Marker phrases (zh-Hant + EN) confirming đây là email giao dịch — đối ngẫu
# với subject filter của TCB/Cake. Hang Seng email body có cả 2 ngôn ngữ.
_HANGSENG_TX_MARKERS = (
    "your transfer is successful",
    "你已成功轉賬",
    "successfully transferred to payee",
    "已成功轉賬至收款人",
    "transfer status",
    "交易狀況",
)


def _parse_hangseng(subject: str, body: str, date: str) -> dict | None:
    """
    Hang Seng Bank email format (bilingual zh-Hant / English).

    Reference body (outgoing transfer to non-registered payee):
      你已成功轉賬（未登記收款人）
      Your transfer is successful (Non-registered payee)
      由 From: 218-763XXX-888
      HKD300.00
      至 To: 11XXXX876
      交易狀況 Transfer status: 已成功轉賬至收款人 / Successfully transferred to payee
      轉賬日期 Transfer date: 2026-05-06
      收款銀行 Receiving bank: The Hongkong and Shanghai Banking Corporation Limited
      預設銀行 Default bank: Y
      交易號碼 Transaction ID: HD12650698975039
      參考編號 Reference number: N50651066103

    Hiện chỉ hỗ trợ outgoing transfer (chuyển đi). Incoming/credit-card emails
    chưa có mẫu — sẽ thêm khi anh forward sample.
    """
    # Confirm đây là email giao dịch (subject hoặc body phải chứa marker)
    blob_lower = f"{subject}\n{body}".lower()
    if not any(marker.lower() in blob_lower for marker in _HANGSENG_TX_MARKERS):
        print(f"[email_parser][hangseng] skipping non-transaction email: subject={subject!r}")
        return None

    # ── Amount + currency ─────────────────────────────────────────
    # Hang Seng format số tiền có dạng "HKD300.00" (currency liền số) —
    # khác hẳn TCB/Cake (số trước, đơn vị sau). Regex bắt cả 2 thứ tự cho an toàn.
    amount_patterns = [
        r'(HKD|USD|CNY|EUR|GBP|JPY)\s*([\d,]+\.\d{1,2})',  # "HKD300.00"
        r'(HKD|USD|CNY|EUR|GBP|JPY)\s*([\d,]+)',           # "HKD 300"
        r'([\d,]+\.\d{1,2})\s*(HKD|USD|CNY|EUR|GBP|JPY)',  # fallback "300.00 HKD"
    ]
    amount = None
    currency = "HKD"  # default cho Hang Seng
    for pattern in amount_patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            g1, g2 = m.group(1), m.group(2)
            # Xác định group nào là currency / số
            if g1.upper() in {"HKD", "USD", "CNY", "EUR", "GBP", "JPY"}:
                currency = g1.upper()
                amount_str = g2
            else:
                currency = g2.upper()
                amount_str = g1
            try:
                amount = float(amount_str.replace(",", ""))
                break
            except ValueError:
                continue

    if amount is None:
        print(f"[email_parser][hangseng] could not find amount in body")
        return None

    # ── Transaction direction ─────────────────────────────────────
    # 你已成功轉賬 / Your transfer is successful → outgoing
    # 你已成功收款 / Your transfer received → incoming (chưa hỗ trợ — chưa có mẫu)
    body_lower = body.lower()
    if "你已成功收款" in body or "你已成功收到" in body or "your transfer received" in body_lower:
        tx_type = "in"
    else:
        # Default: outgoing (subject hiện tại của Hang Seng chỉ là transfer-out)
        tx_type = "out"

    # ── Description ───────────────────────────────────────────────
    # Format: "<Title> · To <account> @ <bank>"
    # Title: lấy line đầu tiên có "Your transfer" hoặc "你已成功"
    title = "Hang Seng transfer"
    title_patterns = [
        r'(Your transfer\s+(?:is\s+\w+|received)(?:\s*\([^)]+\))?)',
        r'(你已成功[^\n]+)',
    ]
    for pattern in title_patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            break

    # Tài khoản đích — Hang Seng có nhiều format:
    #   "至 To: 11XXXX876"           — masked account number
    #   "至 To: +852-6655****"        — Hong Kong mobile (FPS payment)
    #   "至 To: john@example.com"    — FPS email proxy
    # Charset: digits, +, -, *, X, @, ., _ (allow most identifiers)
    to_match = re.search(
        r'(?:至\s*)?To[:\s]+([+\dA-Z\-X*@._]+)',
        body, re.IGNORECASE,
    )
    to_acct = to_match.group(1).strip() if to_match else ""

    # Receiving bank
    bank_match = re.search(
        r'(?:收款銀行|Receiving bank)[:\s]+(.+?)(?:\n|預設銀行|Default bank|$)',
        body, re.IGNORECASE | re.DOTALL,
    )
    receiving_bank = bank_match.group(1).strip() if bank_match else ""

    # Compose description
    desc_parts = [title]
    if to_acct:
        desc_parts.append(f"To {to_acct}")
    if receiving_bank:
        # Rút gọn tên bank dài cho dễ đọc trong sheet
        short_bank = (receiving_bank[:60] + "…") if len(receiving_bank) > 60 else receiving_bank
        desc_parts.append(f"@ {short_bank}")
    description = " · ".join(desc_parts)[:200]

    # ── Date ──────────────────────────────────────────────────────
    tx_date = _parse_hangseng_date(body) or date

    # ── Reference code ────────────────────────────────────────────
    # Ưu tiên: Transaction ID (HD…) > Subject ref [Cxxx] > Reference number > hash fallback
    # Subject ref [Cxxx] có ở 1 số loại GD (vd FPS), không phải email nào cũng có.
    subject_ref_match = re.search(r'Ref\s*:?\s*\[?([A-Z0-9]{6,30})\]?', subject, re.IGNORECASE)
    subject_ref = subject_ref_match.group(1) if subject_ref_match else None

    ref_code = (
        _hangseng_find_ref(body)
        or subject_ref
        or _find_ref_code(body)
        or hashlib.md5(f"{amount}|{currency}|{description}|{tx_date}".encode()).hexdigest()[:16]
    )

    # ── Account hint (sender side) ────────────────────────────────
    # "由 From: 218-763999-888" → "218-763999-888"
    from_match = re.search(
        r'(?:由\s*)?From[:\s]+([+\dA-Z\-X*@._]+)',
        body, re.IGNORECASE,
    )
    account_hint = from_match.group(1).strip() if from_match else ""

    return {
        "transferAmount":  amount,
        "transferType":    tx_type,
        "currency":        currency,
        "description":     description,
        "content":         description,
        "transactionDate": tx_date,
        "referenceCode":   ref_code,
        "_source":         "email_hangseng",
        "_account_hint":   account_hint,
    }


def _parse_hangseng_date(body: str) -> str | None:
    """Hang Seng emails dùng ISO format 'YYYY-MM-DD' cho Transfer date."""
    patterns = [
        # "Transfer date: 2026-05-06" hoặc "轉賬日期 Transfer date: 2026-05-06"
        r'(?:轉賬日期[\s\S]*?|Transfer date[:\s]+)(\d{4}-\d{2}-\d{2})',
        # Fallback: bất kỳ ISO date nào trong body
        r'(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            try:
                # Chỉ có ngày, không có giờ — dùng noon local time để tránh rơi
                # qua ngày khi convert timezone
                dt = datetime.strptime(raw, "%Y-%m-%d").replace(hour=12)
                return dt.isoformat()
            except ValueError:
                return raw
    return None


def _hangseng_find_ref(body: str) -> str | None:
    """Tìm Transaction ID (HD…) hoặc Reference number (N…) trong body Hang Seng.

    Cẩn thận: không dùng re.IGNORECASE với charset [A-Z0-9] vì sẽ match cả
    chữ thường (vd "Transaction" sẽ pass [A-Z0-9]{8,30}). Match nhãn riêng,
    capture giá trị riêng — strict uppercase + digits only.
    """
    label_patterns = [
        # Nhãn EN — thường có ngay sau dấu ":"
        r'Transaction ID\s*[:\-]?\s*([A-Z0-9]{8,30})\b',
        r'Reference number\s*[:\-]?\s*([A-Z0-9]{8,30})\b',
        # Nhãn zh-Hant — value có thể ở line tiếp theo
        r'交易號碼\s*[:\-]?[\s\n]*(?:Transaction ID\s*[:\-]?\s*)?([A-Z0-9]{8,30})\b',
        r'參考編號\s*[:\-]?[\s\n]*(?:Reference number\s*[:\-]?\s*)?([A-Z0-9]{8,30})\b',
    ]
    for pattern in label_patterns:
        # IGNORECASE only for label text — capture group has explicit uppercase charset
        m = re.search(pattern, body)
        if m:
            return m.group(1).strip()
        # Fallback: try with IGNORECASE for label, but the [A-Z0-9] in the
        # capture is still upper-only because IGNORECASE only takes effect
        # at the literal character class ranges.
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Đảm bảo value đúng uppercase + digits (loại bỏ false-positive như "Transaction")
            if re.fullmatch(r'[A-Z0-9]{8,30}', val):
                return val
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
