# Zalo Bot Setup Guide

Hướng dẫn kết nối Zalo Bot để nhận thông báo giao dịch song song với Telegram.

## Yêu cầu

- Tài khoản Zalo (cá nhân)
- My Money Went Bot đang chạy trên Telegram

## Bước 1: Tạo Zalo Bot

1. Mở app **Zalo** trên điện thoại
2. Tìm OA tên **"Zalo Bot Manager"** (hoặc mở [bot.zapps.me](https://bot.zapps.me/docs/create-bot/))
3. Nhắn tin **"Tạo bot"** hoặc chọn menu tương ứng
4. Mở **Zalo Bot Creator** → Nhập tên bot
   - Tên bắt buộc bắt đầu bằng `Bot`, VD: `Bot TienDi`, `Bot ChiTieu`
5. Hệ thống sẽ gửi **Bot Token** qua tin nhắn Zalo — copy token này

## Bước 2: Lấy Chat ID

1. **Gửi 1 tin nhắn bất kỳ** cho bot vừa tạo trên Zalo (VD: "xin chào")
2. Chạy script helper:

```bash
# Dùng env var
export ZALO_BOT_TOKEN="bot123456789:abc123xyz"
python scripts/zalo_get_updates.py

# Hoặc truyền trực tiếp
python scripts/zalo_get_updates.py "bot123456789:abc123xyz"
```

3. Script sẽ in ra `ZALO_CHAT_ID` — copy giá trị này

## Bước 3: Set env vars

### Railway (khuyến nghị)

Vào Railway dashboard → Service → Variables → thêm:

| Variable | Value |
|----------|-------|
| `ZALO_ENABLED` | `true` |
| `ZALO_BOT_TOKEN` | (token từ Bước 1) |
| `ZALO_CHAT_ID` | (chat ID từ Bước 2) |

Redeploy service.

### Local (.env)

Thêm vào file `.env`:

```env
ZALO_ENABLED=true
ZALO_BOT_TOKEN=bot123456789:abc123xyz
ZALO_CHAT_ID=6ede9afa66b88fe6d6a9
```

## Bước 4: Kiểm tra

1. Thực hiện 1 giao dịch nhỏ (chuyển khoản qua bank account đã kết nối SePay)
2. Kiểm tra:
   - ✅ Telegram nhận thông báo (như bình thường)
   - ✅ Zalo cũng nhận thông báo tương tự (plain text, không có nút bấm)
3. Nếu chỉ Telegram nhận → kiểm tra logs Railway, tìm `[zalo]`

## Lưu ý quan trọng

- **Zalo chỉ nhận notification** — phân loại giao dịch (chọn category) vẫn thực hiện trên Telegram
- **Zalo không hỗ trợ nút bấm** — tin nhắn hiển thị dạng plain text
- **Tin nhắn dài** sẽ tự động chia thành nhiều phần (max 2000 ký tự/tin)
- **Nếu Zalo API lỗi**, giao dịch vẫn được ghi vào Google Sheet và Telegram vẫn nhận tin bình thường
- **Tắt Zalo** bất cứ lúc nào bằng cách set `ZALO_ENABLED=false` và redeploy

## Modes hỗ trợ

| Mode | Mô tả |
|------|-------|
| **Telegram only** (default) | Như bình thường, không cần config gì thêm |
| **Telegram + Zalo notification** | Nhận alert giao dịch ở cả 2 nơi |
| **Zalo interactive beta** | Nhận `/today`, `/report`, `/accounts` từ Zalo |

## Optional: bật Zalo interactive beta

Chỉ bật phần này nếu bạn muốn gửi lệnh `/today`, `/report`, `/accounts` từ Zalo. Các flow cần nút bấm như phân loại giao dịch, `/manage`, `/keywords`, `/allocate` vẫn dùng Telegram.

Thêm env vars:

```env
ZALO_INTERACTIVE=true
ZALO_WEBHOOK_SECRET=<random secret 8-256 chars>
ZALO_USER_ID=<user_id từ scripts/zalo_get_updates.py>
```

Set webhook:

```bash
curl -X POST "https://bot-api.zaloplatforms.com/bot<ZALO_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<your-app>.up.railway.app/zalo/webhook","secret_token":"<ZALO_WEBHOOK_SECRET>"}'
```

## Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| Zalo không nhận message | Kiểm tra `ZALO_ENABLED=true`, `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID` |
| Bot không start | Nếu `ZALO_ENABLED=true` thì bắt buộc có `ZALO_BOT_TOKEN` + `ZALO_CHAT_ID`; nếu `ZALO_INTERACTIVE=true` thì cần thêm `ZALO_WEBHOOK_SECRET` + `ZALO_USER_ID` |
| `/zalo/webhook` không xử lý message | Kiểm tra `ZALO_INTERACTIVE=true`, webhook secret đúng, và `ZALO_USER_ID` đúng |
| Script `zalo_get_updates.py` timeout | Gửi tin nhắn cho bot trên Zalo trước, rồi chạy lại script |
| "Invalid token" error | Kiểm tra lại token từ Zalo Bot Manager |

## Tham khảo

- [Zalo Bot Platform docs](https://bot.zapps.me/docs/)
- [Tạo bot](https://bot.zapps.me/docs/create-bot/)
- [API Reference](https://bot.zapps.me/docs/call-api/)
