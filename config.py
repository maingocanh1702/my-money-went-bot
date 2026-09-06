import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


def _env_int(name: str, default: int, min_value: int | None = None) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    if min_value is not None:
        value = max(min_value, value)
    return value

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
CHAT_ID     = os.environ.get("CHAT_ID", "")
SHEET_ID    = os.environ.get("SHEET_ID", "")
TIMEZONE    = "Asia/Ho_Chi_Minh"
DAILY_BUCKET_ID = "daily_spending"

# Friendly fail-fast: a clear message beats a KeyError traceback when an env
# var is missing. Skipped in test mode (BOT_TOKEN starts with "test:").
_required = {"BOT_TOKEN": BOT_TOKEN, "CHAT_ID": CHAT_ID, "SHEET_ID": SHEET_ID}
_missing = [k for k, v in _required.items() if not v]
if _missing and not BOT_TOKEN.startswith("test:"):
    raise SystemExit(
        f"[config] FATAL: Missing required env vars: {', '.join(_missing)}. "
        f"Set them in .env (see .env.example) or the Railway dashboard."
    )

# Google credentials — two ways to provide (Railway: dùng GOOGLE_CREDS_JSON)
# Option A (cloud/Railway): set GOOGLE_CREDS_JSON = nội dung file credentials.json
# Option B (local): set GOOGLE_CREDS = đường dẫn tới file credentials.json
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "").strip()  # JSON string
GOOGLE_CREDS_PATH = os.environ.get("GOOGLE_CREDS", "").strip()
CREDS_FILE        = GOOGLE_CREDS_PATH or "credentials.json"  # local file fallback


def _validate_google_credentials() -> None:
    """Fail startup before financial webhooks accept data with bad Google auth.

    This only parses service-account credentials locally; it does not make a
    network request.  A non-empty but unreadable file or malformed JSON is not
    a usable production configuration.
    """
    try:
        if GOOGLE_CREDS_JSON:
            info = json.loads(GOOGLE_CREDS_JSON)
            Credentials.from_service_account_info(info)
            return
        credential_path = Path(GOOGLE_CREDS_PATH)
        if not credential_path.is_file():
            raise FileNotFoundError(f"credential file not found: {credential_path}")
        Credentials.from_service_account_file(str(credential_path))
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "Invalid Google credentials: set GOOGLE_CREDS_JSON to a valid "
            "service-account JSON document or GOOGLE_CREDS to a readable "
            "service-account JSON file."
        ) from exc

# Required in production: SePay webhook secret. The bot rejects requests that
# do not match this token.
# Điền giá trị này vào SePay dashboard → Webhook → API Key
SEPAY_SECRET = os.environ.get("SEPAY_SECRET", "")

# Required in production: Telegram webhook secret. /webhook rejects updates
# that do not include the matching header.
# header X-Telegram-Bot-Api-Secret-Token khớp. Kích hoạt bằng cách đăng ký lại
# webhook với cùng giá trị:
#   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
#     -d "url=https://<domain>/webhook" -d "secret_token=<value>"
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# Required in production: cron trigger secret. The /trigger/* endpoints
# require ?secret=<value> (xem crontab.txt).
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Email webhook secret — Google Apps Script gửi kèm để xác thực
# Tự đặt 1 chuỗi random, điền vào cả đây và trong Google Apps Script
EMAIL_SECRET = os.environ.get("EMAIL_SECRET", "")

# Words to ignore when guessing a merchant name from a transfer description.
# Vietnamese transfers embed the sender's own name, so add yours here (comma
# separated, no accents) to stop the bot learning it as a merchant:
#   MERCHANT_NOISE_WORDS=nguyen,van,an
MERCHANT_NOISE_WORDS = {
    w.strip().lower()
    for w in os.environ.get("MERCHANT_NOISE_WORDS", "").split(",")
    if w.strip()
}

# The point in time this installation starts owning transactions, as an ISO
# date or timestamp ("2026-09-01" / "2026-09-01T00:00:00"). It exists because a
# provider replays history the first time a webhook is registered, and that
# history is not yours to record.
#
# Age is NOT replay protection — the identity in the claim ledger is. So when
# this is set, an event is judged only by whether it happened before the
# boundary; a transaction delayed by an outage, a Gmail polling gap or a
# provider retry days later is still recorded rather than thrown away. Leave it
# unset to keep the older age windows below as the bootstrap guard.
INGESTION_START_AT = os.environ.get("INGESTION_START_AT", "").strip()

# Transitional: before SePay's own transaction id became the identity, a
# transaction was keyed by its bank reference (or, failing that, a content
# hash). A SePay retry that spans the upgrade arrives with the new identity for
# a row that was written under the old one, so both keys are checked until an
# operator turns this off — no earlier than the provider's retry window after
# deploying the upgrade.
SEPAY_LEGACY_REF_LOOKUP = _env_bool("SEPAY_LEGACY_REF_LOOKUP", True)

# Stale-transaction guard windows (minutes) — the bootstrap guard used only
# while INGESTION_START_AT is unset. Webhook tx older than this are skipped:
# chặn SePay replay lịch sử cũ khi mới setup webhook. Tăng lên nếu bot có thể
# down lâu hơn (SePay retry đến muộn sẽ bị loại ngoài cửa sổ này — có ghi lại
# vào tab Excluded Events).
TX_MAX_AGE_MINUTES = _env_int("TX_MAX_AGE_MINUTES", 10, min_value=1)
EMAIL_TX_MAX_AGE_MINUTES = _env_int("EMAIL_TX_MAX_AGE_MINUTES", 7 * 24 * 60, min_value=1)

# Zalo Bot Platform — enable to receive transaction notifications on Zalo
# Tạo bot tại: mở Zalo → tìm "Zalo Bot Manager" → Tạo bot
# Docs: https://bot.zapps.me/docs/create-bot/
ZALO_ENABLED = _env_bool("ZALO_ENABLED")
ZALO_BOT_TOKEN = os.environ.get("ZALO_BOT_TOKEN", "")  # Bot token from Zalo Bot Manager
ZALO_SECRET_TOKEN = os.environ.get("ZALO_SECRET_TOKEN", "")  # Webhook secret for X-Bot-Api-Secret-Token header
# An unsigned Zalo webhook is useful only for isolated test processes. Never
# let a production environment flag re-open this public endpoint.
ZALO_ALLOW_UNVERIFIED_WEBHOOK = BOT_TOKEN.startswith("test:") and _env_bool("ZALO_ALLOW_UNVERIFIED_WEBHOOK")
ZALO_CHAT_ID = os.environ.get("ZALO_CHAT_ID", "")  # chat.id of the Zalo user
ZALO_TEXT_LIMIT = _env_int("ZALO_TEXT_LIMIT", 2000, min_value=100)
# Zalo callbacks must not enter Telegram's state and transport handlers. Keep
# the numbered text flow until a separate, channel-safe callback core exists.
ZALO_INLINE_KEYBOARD = False

# Production has public financial webhooks, so every authentication secret is
# mandatory. Test mode uses the dummy token supplied by tests/conftest.py.
if not BOT_TOKEN.startswith("test:"):
    _required = {
        "BOT_TOKEN": BOT_TOKEN,
        "CHAT_ID": CHAT_ID,
        "SHEET_ID": SHEET_ID,
        "SEPAY_SECRET": SEPAY_SECRET,
        "TELEGRAM_WEBHOOK_SECRET": TELEGRAM_WEBHOOK_SECRET,
        "EMAIL_SECRET": EMAIL_SECRET,
        "CRON_SECRET": CRON_SECRET,
    }
    if ZALO_ENABLED:
        _required["ZALO_SECRET_TOKEN"] = ZALO_SECRET_TOKEN
    _missing = [name for name, value in _required.items() if not value]
    if not GOOGLE_CREDS_JSON and not GOOGLE_CREDS_PATH:
        _missing.append("GOOGLE_CREDS_JSON or GOOGLE_CREDS")
    if _missing:
        raise RuntimeError("Missing required production environment variables: " + ", ".join(_missing))
    _validate_google_credentials()

# Sheet tab names
class SHEETS:
    TRANSACTIONS    = "Đầu ra"
    BUDGET_CONFIG   = "Budget Config"
    SUBCATEGORY     = "Sub-category Config"
    MONTHLY_REPORTS = "Monthly Reports"
    BOT_STATE       = "Bot State"
    ARCHIVE         = "Archive"
    KEYWORD_RULES   = "Keyword Rules"
    ACCOUNTS        = "Accounts"
    LEDGER          = "Account Ledger"
    PENDING_ACCOUNTS = "Pending Accounts"
    # Cashback tracking (BRD §6) — 5 additive tabs, no DB.
    CASHBACK_RULES   = "Cashback Rules"
    CASHBACK_TIERS   = "Cashback Tx Tiers"
    CASHBACK_CONFIG  = "Cashback Card Config"
    CASHBACK_LEDGER  = "Cashback Ledger"
    MCC_MAP          = "MCC Map"
    PROCESSED_REFS   = "Processed Refs"
    EXCLUDED_EVENTS  = "Excluded Events"
