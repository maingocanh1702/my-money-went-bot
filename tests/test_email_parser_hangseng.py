"""
tests/test_email_parser_hangseng.py — verify Hang Seng outgoing transfer parser

Run from project root:
    PYTHONPATH=. python -m pytest tests/test_email_parser_hangseng.py -v
or just:
    PYTHONPATH=. python tests/test_email_parser_hangseng.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.email_parser import parse_email, _parse_hangseng


# Body từ 2 screenshot — viewport phía trên (header + amount block) + viewport
# phía dưới (transfer status block). Ghép lại như Gmail render plain-text.
HANGSENG_OUTGOING_BODY = """\
如未能正常顯示電郵內容，請你設定電郵瀏覽程式至支援 HTML 格式的電郵。
If you cannot view this email properly, please configure your email programme so that it can support HTML formatted emails.

恒生銀行 HANG SENG BANK

你已成功轉賬（未登記收款人）
Your transfer is successful (Non-registered payee)

由 From
218-763XXX-888

HKD300.00

至 To
11XXXX876

交易狀況
Transfer status: 已成功轉賬至收款人
Successfully transferred to payee

轉賬日期
Transfer date: 2026-05-06

收款銀行
Receiving bank: The Hongkong and Shanghai Banking Corporation Limited

預設銀行
Default bank: Y

交易號碼
Transaction ID: HD12650698975039

參考編號
Reference number: N50651066103

多謝選用我們的服務
Thank you for using our service
"""

HANGSENG_FROM = "Hang Seng Bank <hangseng@infoservices.hangseng.com>"
HANGSENG_SUBJECT = "Your transfer is successful"
HANGSENG_DATE = "2026-05-06T12:04:00+08:00"


def test_hangseng_outgoing_basic():
    """Sanity check: parse trả về dict, không None."""
    result = parse_email(HANGSENG_FROM, HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE)
    assert result is not None, "parser returned None — sender routing or subject filter failed"
    assert result["_source"] == "email_hangseng"


def test_hangseng_amount_and_currency():
    result = parse_email(HANGSENG_FROM, HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE)
    assert result["transferAmount"] == 300.00, f"amount wrong: {result['transferAmount']}"
    assert result["currency"] == "HKD", f"currency wrong: {result['currency']}"


def test_hangseng_outgoing_direction():
    """'你已成功轉賬' / 'Your transfer is successful' → outgoing."""
    result = parse_email(HANGSENG_FROM, HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE)
    assert result["transferType"] == "out", f"tx_type wrong: {result['transferType']}"


def test_hangseng_reference_code():
    """Ưu tiên Transaction ID (HD…) làm referenceCode."""
    result = parse_email(HANGSENG_FROM, HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE)
    assert result["referenceCode"] == "HD12650698975039", f"ref wrong: {result['referenceCode']}"


def test_hangseng_transaction_date():
    result = parse_email(HANGSENG_FROM, HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE)
    # _parse_hangseng_date converts 'YYYY-MM-DD' → ISO with noon time
    assert "2026-05-06" in result["transactionDate"], f"date wrong: {result['transactionDate']}"


def test_hangseng_description_includes_payee_and_bank():
    result = parse_email(HANGSENG_FROM, HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE)
    desc = result["description"]
    assert "11XXXX876" in desc, f"missing payee account in desc: {desc!r}"
    assert "Hongkong and Shanghai" in desc or "Hong Kong" in desc.replace("k", "K"), \
        f"missing receiving bank in desc: {desc!r}"


def test_hangseng_bare_email_address():
    """Sender không có 'Name <email>' wrapper vẫn match."""
    result = parse_email(
        "hangseng@infoservices.hangseng.com",
        HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE,
    )
    assert result is not None
    assert result["_source"] == "email_hangseng"


def test_hangseng_unknown_sender_returns_none():
    """Email từ sender lạ → trả None."""
    result = parse_email(
        "spam@unknown.com",
        HANGSENG_SUBJECT, HANGSENG_OUTGOING_BODY, HANGSENG_DATE,
    )
    assert result is None


def test_hangseng_marketing_email_skipped():
    """Email từ Hang Seng nhưng không phải transaction (vd promotion) → trả None."""
    result = parse_email(
        HANGSENG_FROM,
        "Hang Seng e-Statement now available",
        "Dear customer, your June statement is ready to view in HangSengNow.",
        HANGSENG_DATE,
    )
    assert result is None, "should skip non-transaction email"


# ─── Forwarded email tests (real-world: forwarder → your-account) ─────────────

# Body khi Gmail auto-forward: header "Forwarded message" + From line + body gốc
HANGSENG_FORWARDED_BODY = """\
---------- Forwarded message ---------
From: Hang Seng <hangseng@infoservices.hangseng.com>
Date: Fri, 1 May 2026 at 20:31
Subject: 你已成功轉賬(未登記收款人) Your transfer is successful (Non-registered payee) Ref: [C5152043931]
To: <your-forwarder@gmail.com>


如未能正常顯示電郵內容，請你設定電郵瀏覽程式至支援 HTML 格式的電郵。
If you cannot view this email properly, please configure your email programme so that it can support HTML formatted emails.

恒生銀行 HANG SENG BANK

你已成功轉賬（未登記收款人）
Your transfer is successful (Non-registered payee)

由 From
218-763XXX-888

HKD278.00

至 To
+852-6655****

交易狀況
Transfer status: 已成功轉賬至收款人
Successfully transferred to payee

轉賬日期
Transfer date: 2026-05-01

收款銀行
Receiving bank: The Hongkong and Shanghai Banking Corporation Limited

預設銀行
Default bank: Y

交易號碼
Transaction ID: HD12999999999999

參考編號
Reference number: N50000000001

多謝選用我們的服務
Thank you for using our service
"""


def test_forwarded_hangseng_routed_correctly():
    """Email forward từ forwarder → parser phải detect sender gốc trong body."""
    result = parse_email(
        from_addr="Forwarder Name <your-forwarder@gmail.com>",
        subject="Fwd: 你已成功轉賬(未登記收款人) Your transfer is successful (Non-registered payee) Ref: [C5152043931]",
        body=HANGSENG_FORWARDED_BODY,
        date="2026-05-01T20:31:00+08:00",
    )
    assert result is not None, "forwarded email should be parsed (detect via body)"
    assert result["_source"] == "email_hangseng"


def test_forwarded_hangseng_amount_correct():
    result = parse_email(
        from_addr="Forwarder Name <your-forwarder@gmail.com>",
        subject="Fwd: 你已成功轉賬",
        body=HANGSENG_FORWARDED_BODY,
        date="2026-05-01T20:31:00+08:00",
    )
    assert result["transferAmount"] == 278.00, f"amount: {result['transferAmount']}"
    assert result["currency"] == "HKD"


def test_forwarded_hangseng_phone_payee():
    """'+852-6655****' (HK mobile FPS) phải được capture vào description."""
    result = parse_email(
        from_addr="your-forwarder@gmail.com",
        subject="Fwd: 你已成功轉賬",
        body=HANGSENG_FORWARDED_BODY,
        date="2026-05-01T20:31:00+08:00",
    )
    assert "+852-6655" in result["description"], \
        f"phone payee missing in desc: {result['description']!r}"


def test_forwarded_hangseng_subject_ref_fallback():
    """Khi body không có Transaction ID, subject ref [C5152043931] phải được dùng."""
    body_no_txid = HANGSENG_FORWARDED_BODY.replace("HD12999999999999", "")
    body_no_txid = body_no_txid.replace("Transaction ID:", "")
    body_no_txid = body_no_txid.replace("交易號碼", "")
    body_no_txid = body_no_txid.replace("Reference number: N50000000001", "")
    body_no_txid = body_no_txid.replace("參考編號", "")

    result = parse_email(
        from_addr="your-forwarder@gmail.com",
        subject="Fwd: 你已成功轉賬 Your transfer is successful Ref: [C5152043931]",
        body=body_no_txid,
        date="2026-05-01T20:31:00+08:00",
    )
    assert result is not None
    # Khi không có HD/N ref trong body, fallback dùng subject ref
    assert result["referenceCode"] == "C5152043931", \
        f"expected C5152043931 from subject, got {result['referenceCode']!r}"


def test_forwarded_non_bank_email_returns_none():
    """Forwarded email NHƯNG sender gốc không phải bank → trả None."""
    body = (
        "---------- Forwarded message ---------\n"
        "From: Friend <friend@example.com>\n"
        "Date: Fri, 1 May 2026 at 12:00\n"
        "Subject: hello\n"
        "\n"
        "Hi, want to grab lunch?"
    )
    result = parse_email(
        from_addr="your-forwarder@gmail.com",
        subject="Fwd: hello",
        body=body,
        date="2026-05-01T12:00:00+08:00",
    )
    assert result is None


def test_tcb_still_works():
    """Regression: TCB parser vẫn hoạt động sau khi thêm currency field."""
    tcb_body = (
        "Tài khoản: ****1234\n"
        "Giao dịch: Tiền ra\n"
        "Số tiền GD: 500,000 VND\n"
        "Số dư TK:   2,500,000 VND\n"
        "Nội dung:   NGUYEN VAN A CHUYEN TIEN\n"
        "Thời gian:  06/05/2026 14:30:25\n"
    )
    result = parse_email(
        "automail@techcombank.com.vn",
        "Biến động số dư",
        tcb_body,
        "2026-05-06T14:30:25+07:00",
    )
    assert result is not None
    assert result["currency"] == "VND"
    assert result["transferAmount"] == 500000.0
    assert result["transferType"] == "out"


if __name__ == "__main__":
    # Run all tests
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failures = []
    for fn in tests:
        try:
            fn()
            print(f"✅ {fn.__name__}")
        except AssertionError as e:
            print(f"❌ {fn.__name__}: {e}")
            failures.append(fn.__name__)
        except Exception as e:
            print(f"💥 {fn.__name__}: {type(e).__name__}: {e}")
            failures.append(fn.__name__)
    print()
    print(f"Passed: {len(tests) - len(failures)}/{len(tests)}")
    if failures:
        sys.exit(1)
