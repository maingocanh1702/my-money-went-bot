#!/usr/bin/env python3
"""scripts/sim_webhook.py — craft fake webhook payloads and POST to the bot.

Use this for smoke-testing every phase of the Account Tracking feature.

Examples
--------
  python scripts/sim_webhook.py sepay --account 1903xxx888 --amount 50000 --type out --desc "highland"
  python scripts/sim_webhook.py sepay --amount 200000 --type in --desc "salary"
  python scripts/sim_webhook.py email-tcb --account "****1234" --amount 500000 --type out --desc "winmart"
  python scripts/sim_webhook.py email-cake --amount 50000 --type out --desc "PAYOO BHX"
  python scripts/sim_webhook.py email-hangseng --account "218-763999-888" --amount 300 --currency HKD
  python scripts/sim_webhook.py replay <ref_code>
  python scripts/sim_webhook.py transfer --from tcb_main --to cake_main --amount 1000000

Env:
  BOT_URL  — base URL (default http://localhost:8000)
  EMAIL_SECRET / SEPAY_SECRET — passed through if set
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib import request, error


BOT_URL = os.environ.get("BOT_URL", "http://localhost:8000").rstrip("/")
EMAIL_SECRET = os.environ.get("EMAIL_SECRET", "")
SEPAY_SECRET = os.environ.get("SEPAY_SECRET", "")


def _post(path: str, payload: dict) -> dict:
    url = BOT_URL + path
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": text}
    except error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"status": -1, "body": str(e)}


def _ref(amount: float, desc: str, dt: str, source: str = "") -> str:
    seed = f"{source}|{amount}|{desc}|{dt}"
    return "SIM_" + hashlib.md5(seed.encode()).hexdigest()[:12]


def cmd_sepay(args) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    direction = args.type.lower()  # "in" or "out"
    payload = {
        "transferType": direction,
        "transferAmount": args.amount,
        "description": args.desc or f"sim {direction} {args.amount}",
        "transactionDate": now,
        "currency": args.currency or "VND",
        "referenceCode": args.ref or _ref(args.amount, args.desc or "", now, "sepay"),
    }
    if args.account:
        payload["accountNumber"] = args.account
    if args.subaccount:
        payload["subAccount"] = args.subaccount
    if args.gateway:
        payload["gateway"] = args.gateway
    if SEPAY_SECRET:
        payload["apikey"] = SEPAY_SECRET
    return _post("/webhook", payload)


def cmd_email_tcb(args) -> dict:
    direction_label = "Tiền vào" if args.type == "in" else "Tiền ra"
    body = (
        f"Tài khoản: {args.account or '****1234'}\n"
        f"Giao dịch: {direction_label}\n"
        f"Số tiền GD: {int(args.amount):,} VND\n"
        f"Số dư TK:   1,000,000 VND\n"
        f"Nội dung:   {args.desc or 'sim tcb tx'}\n"
        f"Thời gian:  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
    )
    return _post(
        "/webhook/email",
        {
            "secret": EMAIL_SECRET,
            "from": "automail@techcombank.com.vn",
            "subject": "TCB - Bien dong so du",
            "body": body,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )


def cmd_email_cake(args) -> dict:
    sign = "+" if args.type == "in" else "-"
    body = (
        f"{sign}{int(args.amount):,}đ\n"
        f"Số dư: 500.000đ\n"
        f"Nội dung: {args.desc or 'sim cake tx'}\n"
        f"Lúc: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
    )
    return _post(
        "/webhook/email",
        {
            "secret": EMAIL_SECRET,
            "from": "no-reply@cake.vn",
            "subject": "Cake - Bien dong",
            "body": body,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )


def cmd_email_hangseng(args) -> dict:
    cur = (args.currency or "HKD").upper()
    body = (
        "你已成功轉賬（未登記收款人）\n"
        "Your transfer is successful (Non-registered payee)\n"
        f"由 From: {args.account or '218-763999-888'}\n"
        f"{cur}{args.amount:.2f}\n"
        f"至 To: {args.to or '11XXXX876'}\n"
        f"轉賬日期 Transfer date: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"交易號碼 Transaction ID: HD{int(datetime.now().timestamp())}\n"
    )
    return _post(
        "/webhook/email",
        {
            "secret": EMAIL_SECRET,
            "from": "hangseng@infoservices.hangseng.com",
            "subject": "Hang Seng transfer",
            "body": body,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )


def cmd_replay(args) -> dict:
    """Replay a previous SePay payload using a known ref_code (idempotency check)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "transferType": "out",
        "transferAmount": 50000,
        "description": "replay",
        "transactionDate": now,
        "currency": "VND",
        "referenceCode": args.ref_code,
    }
    if SEPAY_SECRET:
        payload["apikey"] = SEPAY_SECRET
    return _post("/webhook", payload)


def cmd_transfer(args) -> dict:
    print(
        "Note: /transfer is a Telegram command. This sim does not have a Telegram\n"
        "context — run `/transfer <amount> <from> <to>` directly in your bot chat."
    )
    return {"status": 0, "body": "see note above"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Simulate webhook calls to the bot")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--amount", type=float, required=True)
        sp.add_argument("--type", choices=["in", "out"], default="out")
        sp.add_argument("--desc", default="")
        sp.add_argument("--currency", default=None)
        sp.add_argument("--account", default=None)
        sp.add_argument("--ref", default=None)

    sp = sub.add_parser("sepay")
    common(sp)
    sp.add_argument("--subaccount", default=None)
    sp.add_argument("--gateway", default=None)
    sp.set_defaults(func=cmd_sepay)

    sp = sub.add_parser("email-tcb")
    common(sp)
    sp.set_defaults(func=cmd_email_tcb)

    sp = sub.add_parser("email-cake")
    common(sp)
    sp.set_defaults(func=cmd_email_cake)

    sp = sub.add_parser("email-hangseng")
    common(sp)
    sp.add_argument("--to", default=None, help="To-account display string")
    sp.set_defaults(func=cmd_email_hangseng)

    sp = sub.add_parser("replay")
    sp.add_argument("ref_code", help="ref_code to replay")
    sp.set_defaults(func=cmd_replay)

    sp = sub.add_parser("transfer")
    sp.add_argument("--from", dest="from_acct", required=True)
    sp.add_argument("--to", dest="to_acct", required=True)
    sp.add_argument("--amount", type=float, required=True)
    sp.set_defaults(func=cmd_transfer)

    return p


def main() -> int:
    args = build_parser().parse_args()
    out = args.func(args)
    print(f"→ POST result: {out}")
    return 0 if out.get("status") in (200, 0) else 1


if __name__ == "__main__":
    sys.exit(main())
