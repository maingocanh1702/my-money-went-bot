import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.environ["BOT_TOKEN"]
CHAT_ID     = os.environ["CHAT_ID"]
SHEET_ID    = os.environ["SHEET_ID"]
TIMEZONE    = "Asia/Ho_Chi_Minh"
DAILY_BUCKET_ID = "daily_spending"

# Google credentials — two ways to provide (Railway: dùng GOOGLE_CREDS_JSON)
# Option A (cloud/Railway): set GOOGLE_CREDS_JSON = nội dung file credentials.json
# Option B (local): set GOOGLE_CREDS = đường dẫn tới file credentials.json
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")        # JSON string
CREDS_FILE        = os.environ.get("GOOGLE_CREDS", "credentials.json")  # file path fallback

# ── Security tokens (required for all environments) ──────────────────────────
# Telegram webhook secret — phải khớp với secret_token đã set khi gọi setWebhook
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# SePay webhook secret — khớp với API Key đã config trong SePay dashboard
SEPAY_SECRET = os.environ.get("SEPAY_SECRET", "")

# Cron trigger secret — dùng cho /trigger/* endpoints
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Validate secrets at startup for deployed environments.
# In test mode (BOT_TOKEN starts with "test:") we allow empty secrets.
if not BOT_TOKEN.startswith("test:"):
    _missing = []
    if not TELEGRAM_WEBHOOK_SECRET:
        _missing.append("TELEGRAM_WEBHOOK_SECRET")
    if not SEPAY_SECRET:
        _missing.append("SEPAY_SECRET")
    if not CRON_SECRET:
        _missing.append("CRON_SECRET")
    if _missing:
        raise SystemExit(
            f"[config] FATAL: Missing required security env vars: {', '.join(_missing)}. "
            f"Set them in .env or Railway dashboard. See .env.example."
        )

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
    PROCESSED_REFS  = "Processed Refs"
