# 💰 My Money Went Bot


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[🇬🇧 English](README.md)

> 🙏 **Credits:** xây dựng dựa trên các pattern từ [`maddyle8124/spend-less-bot`](https://github.com/maddyle8124/spend-less-bot). Cảm ơn Maddy rất nhiều — không có repo gốc này thì My Money Went cũng không có.

---

## Bot làm gì


**My Money Went Bot là 1 bot Telegram theo dõi chi tiêu cá nhân.** Mỗi lần ngân hàng VN gửi thông báo giao dịch (qua [SePay](https://sepay.vn)), bot ghi vào Google Sheet *của bạn* và hỏi bạn tap phân loại — hoặc skip luôn nếu bạn đã dạy nó 1 keyword rule. Gõ `/report` bất cứ lúc nào để xem tiền đã đi đâu, slice theo account, category, và khoảng thời gian.

<details>
<summary>📐 Flow chi tiết (có nhánh auto-categorize + onboarding)</summary>

```mermaid
flowchart LR
    A[🏦 Tx ngân<br/>hàng VN] -->|SePay<br/>webhook| B[🤖 Bot]
    B --> C[📊 Ghi row<br/>Google Sheet]
    C --> D{Match<br/>keyword<br/>rule?}
    D -->|✅ Có| E[🎯 Auto-<br/>categorize]
    D -->|❌ Không| F[💬 'Thuộc mục<br/>nào?']
    F --> G[👆 Bạn tap]
    E --> H[📈 /report<br/>account ×<br/>category ×<br/>period]
    G --> H

    B -. nguồn<br/>chưa biết? .-> I[📝 Wizard<br/>onboard]
    I -. tx sau<br/>auto-route .-> B

    classDef bank fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef bot fill:#dbeafe,stroke:#2563eb,color:#1e40af
    classDef store fill:#dcfce7,stroke:#16a34a,color:#15803d
    classDef user fill:#fce7f3,stroke:#db2777,color:#9d174d
    classDef out fill:#f3e8ff,stroke:#9333ea,color:#6b21a8
    class A bank
    class B,E,I bot
    class C store
    class F,G user
    class H out
```

</details>

**Không database. Không lưu data ở bên thứ 3. Single-tenant — 1 bot / 1 người.** Google Sheet của bạn LÀ backend. Data của bạn, sheet của bạn, luật của bạn.

---

## Tại sao có project này

Các app tài chính cá nhân (Money Lover, Misa, MoneyKeeper, ...) thường đòi credentials ngân hàng của bạn, chạy trên cloud của họ, và đẩy data của bạn sau bức tường freemium. Bot này làm ngược lại:

- **Bạn sở hữu data.** Tất cả nằm trong Google Sheet của bạn. Export, fork, archive, pivot — quyền bạn.
- **Bạn đọc được mọi dòng code.** ~3,000 LOC Python. Audit, custom, ship.
- **Bạn phân loại 1 lần.** Auto-categorize qua `/keywords` giúp tx định kỳ (Spotify, Grab, ...) skip luôn picker.
- **Report khớp với mô hình thực tế** — per-account *và* per-category, theo week/month/quarter/year. Không chỉ là "biểu đồ category theo tháng".

---

## Tính năng


Chi tiết từng tính năng:

🏦 **Tracking per-account** — mỗi tx được tag theo bank account gốc. `/report` slice theo account (TPB / Vietcombank / cash) và theo category.

📊 **`/report` thống nhất, 2 lens × 4 period** — tuần/tháng/quý/năm qua inline button. Toggle account ↔ category lens tại chỗ. Không cần gõ lại command.

🤖 **Onboarding account thông minh** — lần đầu tx đến từ nguồn chưa map, bot hỏi. Wizard 3 bước: tên → loại → xong. Tx sau auto-route.

⚡ **Auto-categorize** — `/keywords` cho phép định nghĩa pattern ("GRAB" → Daily Spending, "Spotify" → Subscription). Tx match sẽ skip prompt.

🎯 **Budget allocation thông minh** — `/allocate` đặt cap hàng tháng theo category. Lần sau quay lại là *edit mode* — tap 1 bucket để đổi cap, không phải walk lại wizard.

🔁 **Backfill tx lịch sử** — `/accounts assign <slug>` gán retroactive tx cũ chưa map vào account vừa onboard. Không mất tx nào giữa "first webhook" và "wizard complete".

🧾 **Thẻ tín dụng + cashback engine** — dư nợ, `/cc pay`, kỳ sao kê, và tracker cashback theo MCC đầy đủ (`/cashback`): rules, cap theo kỳ, cổng kích hoạt, MCC map tự học.

📧 **Email ingestion** — bank SePay không hỗ trợ (TCB, Cake, Hang Seng) vẫn vào được qua Google Apps Script forward email thông báo tới `/webhook/email` (xem `google_apps_script.js`).

💬 **Kênh Zalo** — cùng các flow trên Zalo Bot Platform qua menu đánh số: category picker, `/report`, `/manage`, `/allocate`, `/keywords`, `/cashback`, `/recat`, `/pending`.

🌐 **Song ngữ** — `/lang` đổi toàn bộ bot giữa Tiếng Việt và English.

🇻🇳 **Ngân hàng VN** — hoạt động với bất kỳ bank nào SePay support. VND-first; account ngoại tệ (vd HKD qua email Hang Seng) được track riêng theo account, không lẫn vào tổng VND.

---

## Screenshots


---

## Ngân hàng được hỗ trợ

Bất cứ bank nào [SePay support](https://sepay.vn/ngan-hang.html) là bot này track được. SePay kết nối trực tiếp với **10 ngân hàng VN** (tính đến 2026):

| Ngân hàng | Code |
|---|---|
| VPBank | VPB |
| ACB | ACB |
| Sacombank | STB |
| VietinBank | ICB |
| MBBank | MBB |
| BIDV | BIDV |
| MSB | MSB |
| TPBank | TPB |
| KienLongBank | KLB |
| OCB | OCB |

Một số bank (BIDV, MB, VietinBank, ACB, OCB, KienLongBank, MSB) dùng **API trực tiếp** — webhook tức thì khi có tx. Số còn lại đi qua **SMS Banking** nên có chút độ trễ. Dù sao bot cũng xử lý payload giống hệt nhau — xem [bảng giá SePay](https://sepay.vn/bang-gia.html) để biết list mới nhất.

---

## Cần chuẩn bị

| Yêu cầu | Lấy ở đâu |
|---|---|
| Tài khoản Telegram | Chắc bạn có rồi |
| Tài khoản [SePay](https://sepay.vn) | Kết nối bank VN của bạn |
| Tài khoản Google | Cho Google Sheets + Google Cloud |
| Server có HTTPS public | [Railway](https://railway.app) đơn giản nhất (free tier OK). Hoặc Ubuntu VPS + [ngrok](https://ngrok.com) cho test. |
| Python 3.11+ | Trên server / Railway |

---

## Quick start

### Bước 1 — Tạo Telegram bot

1. Nhắn [@BotFather](https://t.me/BotFather) → `/newbot` → lưu token.
2. Nhắn [@userinfobot](https://t.me/userinfobot) → lưu chat ID của bạn.

### Bước 2 — Setup Google Sheets

1. Vào [console.cloud.google.com](https://console.cloud.google.com) → tạo project mới.
2. Enable **Google Sheets API** + **Google Drive API**.
3. **IAM & Admin → Service Accounts → Create** → **Keys → Add Key → JSON** → download là `credentials.json`.
4. Tạo Google Sheet mới. Copy **SHEET_ID** từ URL.
5. Share sheet với email service account (quyền Editor).

**Các tab tự tạo lần đầu webhook về** — không cần setup schema tay. Các tab:

| Tab | Mục đích |
|---|---|
| `Đầu ra` | Tất cả transactions (1 row / tx) |
| `Accounts` | Account đã onboard (name, type, source_keys) |
| `Account Ledger` | Ledger append-only — source of truth cho balance |
| `Pending Accounts` | Queue onboarding (TTL 24h) |
| `Budget Config` | Allocate per-month per-bucket |
| `Sub-category Config` | Sub-label per bucket (optional) |
| `Keyword Rules` | Pattern auto-categorize |
| `Bot State` | State wizard / picker per chat |
| `Monthly Reports` | Archive báo cáo tháng |

### Bước 3 — Setup SePay

1. Đăng ký tại [sepay.vn](https://sepay.vn), kết nối bank.
2. **Webhook settings** → URL = `https://<your-domain>/webhook`. Chọn hướng tx muốn track:
   - **Chỉ track chi tiêu** → chỉ bật **Tiền ra**.
   - **Track cả thu nhập + chi tiêu** → bật cả **Tiền ra** và **Tiền vào**.

   (Tx Tiền vào được ghi log nhưng skip category picker — xem [Tại sao có project này](#tại-sao-có-project-này).)
3. ⚠️ **Tắt SePay native Google Sheets integration** — bot này tự ghi rows; bật cả 2 = tx duplicate.

### Bước 4 — Deploy

```bash
git clone https://github.com/maingocanh1702/my-money-went-bot.git
cd my-money-went-bot
cp .env.example .env
# Điền các biến bắt buộc: BOT_TOKEN, CHAT_ID, SHEET_ID, GOOGLE_CREDS_JSON,
# SEPAY_SECRET, TELEGRAM_WEBHOOK_SECRET, CRON_SECRET, EMAIL_SECRET
# (và ZALO_SECRET_TOKEN nếu ZALO_ENABLED=true)
```

**Railway** (khuyến nghị):

1. Push fork của bạn lên GitHub.
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Add tất cả env var bắt buộc trong Railway dashboard. Với `GOOGLE_CREDS_JSON`, paste toàn bộ JSON thành 1 dòng; tạo một chuỗi random dài, riêng biệt cho từng biến `*_SECRET`. Nếu bật Zalo, thêm `ZALO_SECRET_TOKEN`.
4. Railway cấp URL `*.up.railway.app` — dùng URL này làm SePay webhook URL.
5. Đăng ký Telegram webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://<your-app>.up.railway.app/webhook" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```

**VPS** (Ubuntu 22.04):

```bash
sudo apt install -y python3.11 python3-pip python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
chmod 600 .env credentials.json

# systemd service
sudo tee /etc/systemd/system/mmwbot.service <<EOF
[Unit]
Description=My Money Went Bot
After=network.target
[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
EnvironmentFile=$(pwd)/.env
Restart=always
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now mmwbot
journalctl -u mmwbot -f   # xem log
```

### Bước 5 — Lần đầu chạy

1. Mở chat với bot trên Telegram, gửi `/today` — bot phải reply.
2. Trigger 1 tx ngân hàng nhỏ — trong vài giây bot sẽ ping: *"Account chưa map"* + *"Khoản này thuộc mục nào?"*.
3. Tap **✅ Setup** → onboard account (tên → loại).
4. Tap category cho tx.
5. Type `/report` → xem breakdown chi tiêu.

Tx sau từ cùng account auto-route. Setup `/keywords` rules để auto-categorize tx định kỳ.

---

## Commands

| Command | Tác dụng |
|---|---|
| `/today` | Chi tiêu hôm nay vs daily cap (bucket Daily Spending). |
| `/report [period]` | Báo cáo tổng. Inline button cho tuần/tháng/quý/năm × lens account/category. |
| `/accounts` | List account đã setup. `/accounts add` mở wizard. `/accounts assign <slug>` bulk-tag tx lịch sử. |
| `/manage` | Thêm / rename / xóa categories. Edit-amount per bucket. |
| `/keywords` | Quản lý rules auto-categorize. |
| `/allocate` | Sửa budget. Lần đầu = wizard, sau đó = edit-mode per bucket. |
| `/cashback` | Cashback thẻ tín dụng: rules, MCC map, kỳ thanh toán, overview. |
| `/transfer <số tiền> <from> <to>` | Ghi nhận chuyển tiền nội bộ giữa các account. |
| `/cc pay <số tiền> [bank] <cc>` | Ghi nhận trả thẻ tín dụng. |
| `/recat [row]` | Phân loại lại giao dịch cũ. Không có tham số → chọn từ 8 giao dịch gần nhất; `/recat <row>` nhắm thẳng số dòng. |
| `/pending` | Phân loại các giao dịch bị xếp hàng khi bạn đang dở thao tác khác. |
| `/lang` | Đổi ngôn ngữ bot (vi/en). |
| `/cancel` | Hủy flow nhiều bước đang làm dở. |
| `/help` | Danh sách lệnh. |

💡 Chỗ nào bot hỏi số tiền đều nhập tắt được: `500k`, `3tr`, `3tr5`, `1m2`, `2 triệu` — bot tự hiểu là VND. Đa số lệnh cũng chạy trên Zalo qua menu đánh số.

---

## Architecture

```
┌──────────┐   webhook    ┌────────────────┐    rows      ┌──────────────┐
│  SePay   │ ───────────► │  FastAPI bot   │ ───────────► │ Google Sheet │
└──────────┘              │  (Railway/VPS) │              │   (của bạn)  │
                          └──────┬─────────┘              └──────────────┘
                                 │ Telegram Bot API
                                 ▼
                          ┌────────────────┐
                          │   Bạn (chat)   │
                          └────────────────┘
```

**Source of truth = ledger table.** `running_balance` là cache được recompute từ ledger mỗi lần write. Xem [`handlers/account_resolver.py`](handlers/account_resolver.py) và [`sheets.py`](sheets.py).

### Cấu trúc project

```
.
├── main.py                       # FastAPI entry — route tất cả webhook (TG + Zalo + email)
├── config.py                     # Đọc env vars, sheet tab names
├── sheets.py                     # Toàn bộ logic read/write Google Sheets
├── telegram_api.py               # Wrapper Telegram Bot API
├── messenger.py                  # Lớp gửi đa kênh (Telegram + Zalo)
├── i18n/                         # UI strings — vi.py / en.py, đổi bằng /lang
├── handlers/
│   ├── sepay.py                  # Handler SePay webhook
│   ├── email_parser.py           # Email thông báo TCB / Cake / Hang Seng
│   ├── account_resolver.py       # Map payload → account_id
│   ├── accounts.py               # /accounts wizard + onboarding + backfill
│   ├── transaction.py            # Category picker + confirmation flow
│   ├── allocation.py             # /allocate budget wizard + edit mode
│   ├── manage.py                 # /manage categories (+ daily cap)
│   ├── keywords.py               # /keywords auto-categorize rules
│   ├── cashback.py               # /cashback (rules, MCC, kỳ sao kê)
│   ├── cashback_engine.py        # Tính cashback thuần (không I/O)
│   ├── report.py                 # /report thống nhất (account + category lenses)
│   ├── reports.py                # /today snapshot + daily recap
│   ├── zalo_queue.py             # Hàng đợi tx Zalo bền (/pending)
│   └── zalo_render.py            # Render summary plain-text cho Zalo
├── tests/unit/                   # 300+ unit tests, in-memory FakeSpreadsheet
├── google_apps_script.js         # Forwarder Gmail → /webhook/email
├── .env.example                  # Template — copy thành .env và điền
├── crontab.txt                   # Cron jobs mẫu (tham chiếu VPS; prod = GitHub Actions)
├── setup.sh                      # VPS bootstrap script
├── railway.toml                  # Railway deploy config
└── requirements.txt
```

---

## Bảo mật ⚠️

Vài điều cần cẩn thận — bot này xử lý data thông báo ngân hàng:

**1. Bảo vệ `.env` và `credentials.json`.** Đây là chìa khóa bot của bạn. Ai có sẽ đọc được chi tiêu.

```bash
chmod 600 .env credentials.json
```

Không bao giờ commit lên GitHub — `.gitignore` đã block sẵn.

**2. Webhook authentication là bắt buộc ở production.** App sẽ từ chối khởi động nếu thiếu bất kỳ secret nào bên dưới, để không vô tình public webhook tài chính.

| Env var | Bảo vệ | Không set thì sao |
|---|---|---|
| `SEPAY_SECRET` | `/webhook` (payload SePay) | App không khởi động |
| `TELEGRAM_WEBHOOK_SECRET` | `/webhook` (update Telegram) | App không khởi động |
| `CRON_SECRET` | `/trigger/*` | App không khởi động |
| `EMAIL_SECRET` | `/webhook/email` | App không khởi động |

Với `TELEGRAM_WEBHOOK_SECRET`, đăng ký lại webhook với cùng giá trị (`setWebhook` + `secret_token` — xem `.env.example`). Với `CRON_SECRET`, thêm `?secret=<value>` vào URL trong `crontab.txt`. Giữ Cloudflare (hoặc WAF) trước Railway app như một lớp bảo vệ mạng bổ sung.

**3. Dùng SSH key, không dùng password.** Nếu deploy VPS, password SSH có thể brute-force:

```bash
ssh-keygen -t ed25519
ssh-copy-id root@your-server
# Sau đó trong /etc/ssh/sshd_config:
#   PasswordAuthentication no
```

**4. Bot chỉ nói chuyện với `CHAT_ID` của bạn.** Hardcoded check — không ai khác tương tác được kể cả khi biết tên bot.

**5. Không có banking credentials nào chạy qua code này.** Bot chỉ nhận *thông báo* tx (số tiền + description) từ SePay. Login bank, số thẻ, v.v. không bao giờ đi qua.

**6. PII trong description.** Payload SePay chứa description giao dịch thô, có thể có tên đối tác, số tài khoản, references. Những thứ này được ghi vào cột `Description`. Ai có quyền đọc Sheet đều thấy — giữ Sheet private.

---

## Troubleshooting

| Vấn đề | Kiểm tra |
|---|---|
| Không nhắn gì khi có tx | Service đang chạy? `systemctl status mmwbot` hoặc Railway logs |
| Bot crash | `journalctl -u mmwbot -n 50` |
| Số tiền sai trong sheet | Check log `DEBUG append_transaction:` |
| Row duplicate trong sheet | Đảm bảo SePay native Sheets integration đã tắt |
| Daily recap sai giờ | Server có ở UTC? Shift cron hours -7 từ ICT |
| `/allocate` không lưu | Check log `[allocate]` messages |
| Bot không auto-route tx từ account đã biết | Check cell `source_keys` trong tab `Accounts` có đúng số tài khoản SePay không |

---

## Update bot

```bash
# Trên server
cd /path/to/my-money-went-bot
git pull
systemctl restart mmwbot
journalctl -u mmwbot -f   # xem log
```

Trên Railway: chỉ cần push lên fork của bạn, Railway tự deploy.

---

## Roadmap (deferred)

Cố tình để ngoài scope (hiện tại):

- 💬 **Bot Facebook Messenger** — cùng UX với Telegram, thêm 1 front-end.
- 🎮 **Bot Discord** — cho user dùng Discord thay vì Telegram.

Đã ship từ roadmap cũ: credit card + cashback, `/transfer` manual, email
ingestion (TCB / Cake / Hang Seng), account ngoại tệ (HKD), và kênh Zalo.

---

## Development

```bash
pip install -r requirements.txt
pytest tests/unit/ -v
```

300+ unit tests dùng `FakeSpreadsheet` in-memory — zero gọi Google API trong test. Tests có `@freeze_time` cần `freezegun` để period assertion deterministic.

---

## Contributing

Welcome contributions — issue / PR / fork. Hãy có quan điểm rõ ràng về scope: bot này cố tình giữ minimal. Tính năng ngoài [Roadmap](#roadmap-deferred) khó có khả năng được merge nhưng vẫn vui vẻ thảo luận.

Khi mở PR:
- Có test cho behavior mới.
- Match code style hiện tại (functional helpers, docstrings, không over-engineering).
- Với UX change, đính screenshot Telegram.

---

## Acknowledgments

Project này khởi đầu là fork-and-rewrite của [`maddyle8124/spend-less-bot`](https://github.com/maddyle8124/spend-less-bot). Ý tưởng cốt lõi — Telegram bot + SePay webhook + Google Sheet — đến từ repo đó. My Money Went Bot bổ sung tracking per-account, report thống nhất multi-period, wizard onboarding account, và nhiều UX refinement khác.

---

## License

[MIT](LICENSE) — fork, ship, sell.

Nếu bạn build gì đó hay ho dựa trên đây, 1 backlink hay shoutout sẽ được trân trọng nhưng không bắt buộc.
