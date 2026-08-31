import os
from dotenv import load_dotenv

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
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")        # JSON string
CREDS_FILE        = os.environ.get("GOOGLE_CREDS", "credentials.json")  # file path fallback

# Optional: SePay webhook secret — nếu set, bot sẽ reject webhook không khớp token
# Điền giá trị này vào SePay dashboard → Webhook → API Key
SEPAY_SECRET = os.environ.get("SEPAY_SECRET", "")

# Optional: Telegram webhook secret — nếu set, /webhook sẽ reject update thiếu
# header X-Telegram-Bot-Api-Secret-Token khớp. Kích hoạt bằng cách đăng ký lại
# webhook với cùng giá trị:
#   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
#     -d "url=https://<domain>/webhook" -d "secret_token=<value>"
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# Optional: Cron trigger secret — nếu set, các endpoint /trigger/* yêu cầu
# ?secret=<value> (xem crontab.txt). Không set → giữ hành vi cũ (mở).
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Email webhook secret — Google Apps Script gửi kèm để xác thực
# Tự đặt 1 chuỗi random, điền vào cả đây và trong Google Apps Script
EMAIL_SECRET = os.environ.get("EMAIL_SECRET", "")

# Stale-transaction guard windows (minutes). Webhook tx older than this are
# skipped — chặn SePay replay lịch sử cũ khi mới setup webhook. Tăng lên nếu
# bot có thể down lâu hơn (SePay retry đến muộn sẽ bị bỏ qua ngoài cửa sổ này).
TX_MAX_AGE_MINUTES = _env_int("TX_MAX_AGE_MINUTES", 10, min_value=1)
EMAIL_TX_MAX_AGE_MINUTES = _env_int("EMAIL_TX_MAX_AGE_MINUTES", 1440, min_value=1)

# Zalo Bot Platform — enable to receive transaction notifications on Zalo
# Tạo bot tại: mở Zalo → tìm "Zalo Bot Manager" → Tạo bot
# Docs: https://bot.zapps.me/docs/create-bot/
ZALO_ENABLED = _env_bool("ZALO_ENABLED")
ZALO_BOT_TOKEN = os.environ.get("ZALO_BOT_TOKEN", "")  # Bot token from Zalo Bot Manager
ZALO_SECRET_TOKEN = os.environ.get("ZALO_SECRET_TOKEN", "")  # Webhook secret for X-Bot-Api-Secret-Token header
ZALO_ALLOW_UNVERIFIED_WEBHOOK = _env_bool("ZALO_ALLOW_UNVERIFIED_WEBHOOK")
ZALO_CHAT_ID = os.environ.get("ZALO_CHAT_ID", "")  # chat.id of the Zalo user
ZALO_TEXT_LIMIT = _env_int("ZALO_TEXT_LIMIT", 2000, min_value=100)
ZALO_INLINE_KEYBOARD = _env_bool("ZALO_INLINE_KEYBOARD", default=False)  # Off by default: Zalo callbacks route into Telegram handlers. Enable only after adding channel-aware callback routing.

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
