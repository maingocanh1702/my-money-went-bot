import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
CHAT_ID     = os.environ.get("CHAT_ID", "")
SHEET_ID    = os.environ["SHEET_ID"]

TELEGRAM_ENABLED = bool(BOT_TOKEN and CHAT_ID)
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

def _missing_channel_vars(
    *,
    telegram_enabled: bool,
    bot_token: str,
    chat_id: str,
    tg_secret: str,
    zalo_enabled: bool,
    zalo_token: str,
    zalo_chat: str,
    zalo_interactive: bool,
    zalo_secret: str,
    zalo_user: str,
    sepay_secret: str,
    cron_secret: str,
) -> list[str]:
    """Pure validation helper — returns names of missing/misconfigured vars.

    Always required: SEPAY_SECRET, CRON_SECRET.
    At least one fully-configured channel is required.
    Telegram channel: BOT_TOKEN + CHAT_ID + TELEGRAM_WEBHOOK_SECRET.
    Zalo channel: ZALO_ENABLED + ZALO_BOT_TOKEN + ZALO_CHAT_ID
                  (+ ZALO_WEBHOOK_SECRET + ZALO_USER_ID when ZALO_INTERACTIVE).
    """
    missing: list[str] = []

    if not sepay_secret:
        missing.append("SEPAY_SECRET")
    if not cron_secret:
        missing.append("CRON_SECRET")

    tg_ok = telegram_enabled and bool(bot_token and chat_id and tg_secret)
    if telegram_enabled and not tg_secret:
        missing.append("TELEGRAM_WEBHOOK_SECRET")

    zalo_ok = False
    if zalo_enabled:
        if not zalo_token:
            missing.append("ZALO_BOT_TOKEN")
        if not zalo_chat:
            missing.append("ZALO_CHAT_ID")
        if zalo_interactive:
            if not zalo_secret:
                missing.append("ZALO_WEBHOOK_SECRET")
            if not zalo_user:
                missing.append("ZALO_USER_ID")
        zalo_ok = bool(
            zalo_token and zalo_chat
            and (not zalo_interactive or (zalo_secret and zalo_user))
        )

    if not tg_ok and not zalo_ok:
        missing.append(
            "at least one channel (Telegram or Zalo) must be fully configured"
        )

    return missing


# Validate secrets at startup for deployed environments.
# Skip in test mode (BOT_TOKEN starts with "test:") to keep unit tests simple.
if not BOT_TOKEN.startswith("test:"):
    _missing = _missing_channel_vars(
        telegram_enabled=TELEGRAM_ENABLED,
        bot_token=BOT_TOKEN,
        chat_id=CHAT_ID,
        tg_secret=TELEGRAM_WEBHOOK_SECRET,
        zalo_enabled=ZALO_ENABLED,
        zalo_token=ZALO_BOT_TOKEN,
        zalo_chat=ZALO_CHAT_ID,
        zalo_interactive=ZALO_INTERACTIVE,
        zalo_secret=ZALO_WEBHOOK_SECRET,
        zalo_user=ZALO_USER_ID,
        sepay_secret=SEPAY_SECRET,
        cron_secret=CRON_SECRET,
    )
    if _missing:
        raise SystemExit(
            f"[config] FATAL: Missing required env vars: {', '.join(_missing)}. "
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
    CASHBACK_RULES  = "Cashback Rules"
    CASHBACK_LOG    = "Cashback Log"
