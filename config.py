import os
from dotenv import load_dotenv

load_dotenv()

# Required-at-runtime but tolerant-at-import (Phase 1-5): empty defaults let
# the app boot on Railway without prod secrets so healthcheck passes. Code
# paths that actually call Telegram / Sheets will fail at the API call site
# with a clearer error than KeyError at module load. Phase 6 W6.2 will add
# `APP_ENV=prod` strict-check + `/health/strict` endpoint.
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
CHAT_ID     = os.environ.get("CHAT_ID", "")
SHEET_ID    = os.environ.get("SHEET_ID", "")
TIMEZONE    = "Asia/Ho_Chi_Minh"
DAILY_BUCKET_ID = "daily_spending"

# Google credentials — two ways to provide (Railway: dùng GOOGLE_CREDS_JSON)
# Option A (cloud/Railway): set GOOGLE_CREDS_JSON = nội dung file credentials.json
# Option B (local): set GOOGLE_CREDS = đường dẫn tới file credentials.json
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")        # JSON string
CREDS_FILE        = os.environ.get("GOOGLE_CREDS", "credentials.json")  # file path fallback

# Optional: SePay webhook secret — nếu set, bot sẽ reject webhook không khớp token
# Điền giá trị này vào SePay dashboard → Webhook → API Key
SEPAY_SECRET = os.environ.get("SEPAY_SECRET", "")

# Email webhook secret — Google Apps Script gửi kèm để xác thực
# Tự đặt 1 chuỗi random, điền vào cả đây và trong Google Apps Script
EMAIL_SECRET = os.environ.get("EMAIL_SECRET", "")

# Sheet tab names
class SHEETS:
    TRANSACTIONS    = "Đầu ra"
    BUDGET_CONFIG   = "Budget Config"
    SUBCATEGORY     = "Sub-category Config"
    MONTHLY_REPORTS = "Monthly Reports"
    BOT_STATE       = "Bot State"
    ARCHIVE         = "Archive"
