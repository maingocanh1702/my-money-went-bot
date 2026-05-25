# 📊 Financial Tracking Bot

Bot Telegram nhận thông báo giao dịch ngân hàng VN qua [SePay](https://sepay.vn), tự ghi nhận và phân loại theo từng account + category. Lưu toàn bộ dữ liệu trong Google Sheet của bạn.

[🇬🇧 English](README.md)

```
Giao dịch ngân hàng xảy ra
  → SePay webhook → bot ghi Transactions row
    → Auto-categorize nếu mô tả tx match rule /keywords (không hỏi)
    → Nếu không: bot hỏi "Khoản này thuộc mục nào?" (bỏ qua nếu tiền vào)
      → Bạn tap category
        → Tx xuất hiện trong /report group theo account + category
```

Không backend database. Không lưu data ở bên thứ 3. Single-tenant — 1 instance / 1 user.

---

## Tính năng

- **Tracking per-account** — mỗi tx được tag theo bank account gốc. `/report` slice theo account (TPB / Vietcombank / cash) và theo category.
- **Multi-period reports** — `/report` đổi tuần / tháng / quý / năm bằng inline button.
- **Hai lens** — category (default: budget bar + cảnh báo) và account (flow per card). Toggle in-place.
- **Onboarding account** — auto-ping khi tx đến từ nguồn chưa map. Wizard ngắn 3 bước: tên → loại → done.
- **Budget allocation** — `/allocate` đặt cap hàng tháng theo category. Edit-mode tap-to-edit từng bucket (không phải walk lại wizard mỗi lần).
- **Auto-categorize** — `/keywords` định nghĩa pattern để tự tag tx, skip category picker.
- **Backfill tx lịch sử** — `/accounts assign <slug>` + col U `account_source_key` tự gán lại tx cũ khi onboard account mới.

---

## Commands

| Command | Tác dụng |
|---------|----------|
| `/today` | Chi tiêu hôm nay vs daily cap (bucket Daily Spending). |
| `/report [period]` | Báo cáo tổng. Default = tháng + category lens. Inline button đổi period (tuần/tháng/quý/năm) + lens (account/category). |
| `/accounts` | List các account đã setup. `/accounts add` mở wizard. `/accounts assign <slug>` bulk-gán tx lịch sử chưa map. |
| `/manage` | Thêm / sửa / xóa categories. Edit-amount per bucket. |
| `/keywords` | Quản lý rules auto-categorize. |
| `/allocate` | Sửa budget. Lần đầu = wizard. Lần sau = edit-mode (tap nút từng bucket). |

---

## Architecture

```
┌──────────┐   webhook    ┌────────────────┐    write     ┌──────────────┐
│  SePay   │ ───────────► │  FastAPI bot   │ ───────────► │ Google Sheet │
└──────────┘              │  (Railway/VPS) │              │  (của bạn)   │
                          └──────┬─────────┘              └──────────────┘
                                 │ Telegram Bot API
                                 ▼
                          ┌────────────────┐
                          │   Bạn (chat)   │
                          └────────────────┘
```

**Source of truth = ledger table.** `running_balance` / `outstanding_balance` là cache được recompute từ ledger mỗi lần write. Xem `handlers/account_resolver.py` và `sheets.py` chi tiết.

Sheet tabs (auto-create lần đầu chạy):

| Tab | Mục đích |
|-----|---------|
| `Đầu ra` | Toàn bộ transactions (1 row / tx, cols A–U). |
| `Accounts` | Account đã onboard (name, type, currency, source_keys mapped). |
| `Account Ledger` | Ledger append-only — source of truth cho balance. |
| `Pending Accounts` | Queue onboarding cho tx chưa map source (TTL 24h). |
| `Budget Config` | Allocate per-month per-bucket. |
| `Sub-category Config` | Sub-label cho bucket (optional). |
| `Keyword Rules` | Pattern auto-categorize. |
| `Bot State` | State wizard / picker per chat (ephemeral). |
| `Monthly Reports` | Archive báo cáo tháng. |

---

## Quick start

Cần chuẩn bị:

- Tài khoản Telegram
- Tài khoản [SePay](https://sepay.vn) đã kết nối bank VN
- Tài khoản Google (Sheets + Cloud Console)
- Server có public HTTPS endpoint — [Railway](https://railway.app) đơn giản nhất. Hoặc Ubuntu VPS + ngrok cho test local.
- Python 3.11+

### 1 — Tạo Telegram bot

1. Nhắn [@BotFather](https://t.me/BotFather) → `/newbot` → lưu token.
2. Nhắn [@userinfobot](https://t.me/userinfobot) → lưu chat ID của bạn.

### 2 — Google service account

1. [console.cloud.google.com](https://console.cloud.google.com) → tạo project mới.
2. Enable **Google Sheets API** + **Google Drive API**.
3. **IAM & Admin → Service Accounts → Create Service Account** → **Keys → Add Key → JSON** → download là `credentials.json`.
4. Tạo Google Sheet mới. Lưu SHEET_ID trong URL.
5. Share sheet với email service account (quyền Editor).
6. Tabs tự create lần đầu webhook về — không cần setup schema tay.

### 3 — SePay webhook

1. Tạo account [sepay.vn](https://sepay.vn), kết nối bank.
2. **Webhook settings** → URL = `https://<your-domain>/webhook`. Bật cả "Tiền vào" và "Tiền ra".
3. **Tắt SePay native Google Sheets integration** nếu đang bật — bot này tự ghi rows; bật cả 2 = duplicate.

### 4 — Deploy

```bash
git clone https://github.com/<your-user>/financial-tracking-bot.git
cd financial-tracking-bot
cp .env.example .env
# Sửa .env: BOT_TOKEN, CHAT_ID, SHEET_ID, GOOGLE_CREDS (hoặc GOOGLE_CREDS_JSON)
```

**Railway** (khuyến nghị):

1. Push code lên GitHub.
2. New Railway project → connect repo.
3. Add env vars từ `.env`. Với `GOOGLE_CREDS_JSON`, paste toàn bộ JSON credentials thành 1 dòng.
4. Railway cấp URL `*.up.railway.app` — dùng URL này làm SePay webhook.
5. Đăng ký Telegram webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://<your-app>.up.railway.app/webhook"
   ```

**VPS** (Ubuntu 22.04):

```bash
apt install -y python3.11 python3-pip python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
chmod 600 .env credentials.json

# systemd service
sudo tee /etc/systemd/system/finbot.service <<EOF
[Unit]
Description=Financial Tracking Bot
After=network.target
[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
EnvironmentFile=$(pwd)/.env
Restart=always
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now finbot
```

### 5 — Lần đầu chạy

1. Trigger 1 tx ngân hàng nhỏ.
2. Bot ping: "Account chưa map" + "Khoản này thuộc mục nào?". Tap Setup → wizard. Tap category.
3. Tx sau từ cùng account auto-route.
4. Type `/report` xem breakdown.

---

## Giới hạn đã biết & lưu ý bảo mật

**Single-tenant.** 1 instance / 1 user. Để serve nhiều user, cần refactor multi-tenant (DB per user, webhook scope per user, etc.) — out of scope.

**Không PII redaction.** Cột `Description` lưu raw text từ SePay payload, có thể chứa tên đối tác, số tài khoản, PII khác. Ai có quyền đọc Sheet đều thấy. Chỉ phù hợp self-hosted.

**Webhook auth opt-in.** SePay API key check support qua env var `SEPAY_SECRET`. Nếu không set, webhook accept bất kỳ caller nào biết URL. **Khuyến nghị:** set secret + dùng Cloudflare/WAF chặn trước.

**Không auto-parse credit card statement.** Trả thẻ credit phải log tay qua `/cc pay`. Auto-detect từ SePay bank-side ("chuyển sang credit card") để Phase sau.

**Income (Tiền vào) không categorize.** Project goal là track *spending*. Tx vào chỉ ghi vào Transactions và surface trong `/report` per-account flow.

---

## Roadmap (deferred)

- **Credit card support** — dư nợ outstanding, % utilization, `/cc pay`, reset hàng cycle. Out of Phase 1 OSS scope; ledger model đã support sẵn nhưng wizard/command chỉ ship bank/debit/cash.
- **`/transfer` manual giữa các account đã track** — bank → bank internal moves. Out of Phase 1 scope.
- **Email ingestion** cho email thông báo ngân hàng (TCB, Cake, HSBC, ...) — Phase 1 chỉ ship SePay.
- **Section TRANSFERS trong /report** để tách bucket transfer-like (Saving, ...) khỏi tổng spending.
- **Multi-tenant SaaS** — cần codebase riêng (user DB, Sheet per user, webhook scoping). Out of scope cho repo này.

---

## Development

```bash
pip install -r requirements.txt
pytest tests/unit/ -v
```

121 unit tests dùng in-memory FakeSpreadsheet (không gọi Google API). Tests có `@freeze_time` cần `freezegun` để period assertion deterministic.

---

## License

[MIT](LICENSE) — fork, ship, sell.
