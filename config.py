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

# ── Optional: Zalo Bot notification channel ───────────────────────────────
# Set ZALO_ENABLED=true to fan-out transaction notifications to Zalo.
# Requires ZALO_BOT_TOKEN and ZALO_CHAT_ID when enabled.
ZALO_ENABLED    = os.environ.get("ZALO_ENABLED", "false").lower() == "true"
ZALO_BOT_TOKEN  = os.environ.get("ZALO_BOT_TOKEN", "")
ZALO_CHAT_ID    = os.environ.get("ZALO_CHAT_ID", "")
# Webhook mode (Phase 2): secret validates incoming webhook, user_id restricts sender
ZALO_INTERACTIVE = os.environ.get("ZALO_INTERACTIVE", "false").lower() == "true"
ZALO_WEBHOOK_SECRET = os.environ.get("ZALO_WEBHOOK_SECRET", "")
ZALO_USER_ID        = os.environ.get("ZALO_USER_ID", "")  # authorized sender

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
    if ZALO_ENABLED:
        if not ZALO_BOT_TOKEN:
            _missing.append("ZALO_BOT_TOKEN")
        if not ZALO_CHAT_ID:
            _missing.append("ZALO_CHAT_ID")
        if ZALO_INTERACTIVE:
            if not ZALO_WEBHOOK_SECRET:
                _missing.append("ZALO_WEBHOOK_SECRET")
            if not ZALO_USER_ID:
                _missing.append("ZALO_USER_ID")
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
