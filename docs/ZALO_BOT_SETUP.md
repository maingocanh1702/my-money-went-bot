# Zalo Bot Setup

Hướng dẫn thêm kênh Zalo **bên cạnh** Telegram. Trang này là bản chi tiết của
*Bước 7* trong [README](../README.vi.md#bước-7--thêm-zalo-bên-cạnh-telegram-tùy-chọn).

## Trước khi bắt đầu

- Tài khoản Zalo cá nhân.
- **Bot đã chạy được trên Telegram.** Không có chế độ chỉ-Zalo: `config.py` thoát
  ngay lúc khởi động nếu thiếu `BOT_TOKEN`, `CHAT_ID` hoặc `TELEGRAM_WEBHOOK_SECRET`,
  bất kể `ZALO_ENABLED` bằng gì. Zalo là kênh cộng thêm.

## Zalo làm được gì

Mọi lệnh đều chạy trên Zalo: thông báo giao dịch, chọn danh mục, `/today`,
`/report`, `/accounts`, `/keywords`, `/manage`, `/allocate`, `/recat`, `/pending`,
`/cashback`, `/cancel`.

Khác biệt duy nhất nằm ở nền tảng, không phải ở bot: **API Zalo Bot chỉ gửi được
text thuần.** Nên mọi bộ nút được render thành danh sách đánh số và bạn reply bằng
con số — `1`, `2`, hoặc `0` cho "tạo mới". Tin nhắn không sửa tại chỗ được, định
dạng đậm/nghiêng bị lược bỏ, và tin dài bị cắt theo `ZALO_TEXT_LIMIT` (mặc định
2000 ký tự).

Còn hai luồng vẫn chỉ có trên Telegram: tạo danh mục mới ngay giữa lúc phân loại,
và onboard tài khoản lần đầu cho một nguồn chưa map.

## Bước 1 — Tạo Zalo Bot

1. Mở app **Zalo** trên điện thoại.
2. Tìm OA **"Zalo Bot Manager"** (hoặc xem [bot.zapps.me](https://bot.zapps.me/docs/create-bot/)).
3. Nhắn **"Tạo bot"** hoặc chọn menu tương ứng → mở **Zalo Bot Creator** → nhập tên bot.
   Tên **bắt buộc bắt đầu bằng `Bot`**, ví dụ `Bot TienDi`, `Bot ChiTieu`.
4. Zalo nhắn lại **Bot Token** — copy nó. Đây là `ZALO_BOT_TOKEN`.

## Bước 2 — Lấy `ZALO_CHAT_ID`

1. **Nhắn cho bot vừa tạo một tin bất kỳ** trên Zalo (VD "xin chào"). Không có bước
   này thì `getUpdates` rỗng và bạn sẽ tưởng token sai.
2. Chạy script helper:

   ```bash
   ZALO_BOT_TOKEN="bot123456789:abc123xyz" python3 scripts/zalo_get_updates.py

   # hoặc truyền token trực tiếp
   python3 scripts/zalo_get_updates.py "bot123456789:abc123xyz"
   ```

3. Script kiểm tra token trước (`getMe`) rồi in ra id của người vừa nhắn. Đó là
   `ZALO_CHAT_ID` — và cũng là **người gửi duy nhất bot chấp nhận**; sự kiện từ id
   khác bị bỏ qua, giống hệt cách `CHAT_ID` hoạt động bên Telegram.

## Bước 3 — Tạo webhook secret

```bash
openssl rand -hex 32   # dùng làm ZALO_SECRET_TOKEN
```

`ZALO_SECRET_TOKEN` **bắt buộc** khi `ZALO_ENABLED=true` — bot từ chối khởi động nếu
thiếu, vì `/zalo/webhook` là endpoint công khai và secret này là thứ duy nhất phân
biệt Zalo thật với người lạ gọi vào.

## Bước 4 — Set env vars

### Railway (khuyến nghị)

Railway dashboard → Service → Variables → thêm bốn biến, rồi redeploy:

| Variable | Value |
|---|---|
| `ZALO_ENABLED` | `true` |
| `ZALO_BOT_TOKEN` | token từ Bước 1 |
| `ZALO_CHAT_ID` | id từ Bước 2 |
| `ZALO_SECRET_TOKEN` | secret từ Bước 3 |

### Local (`.env`)

```env
ZALO_ENABLED=true
ZALO_BOT_TOKEN=bot123456789:abc123xyz
ZALO_CHAT_ID=6ede9afa66b88fe6d6a9
ZALO_SECRET_TOKEN=<chuỗi random 8-256 ký tự>
```

## Bước 5 — Đăng ký webhook

Không có bước này thì Zalo gửi được tin *ra*, nhưng không nhận được lệnh nào *vào*:

```bash
curl -X POST "https://bot-api.zaloplatforms.com/bot<ZALO_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<your-app>.up.railway.app/zalo/webhook","secret_token":"<ZALO_SECRET_TOKEN>"}'
```

Bot kiểm tra header `X-Bot-Api-Secret-Token` và id người gửi trên **mọi** sự kiện;
sai một trong hai là bỏ qua im lặng.

## Bước 6 — Kiểm tra

1. Gửi `/today` cho bot trên Zalo — phải có trả lời.
2. Tạo một giao dịch nhỏ (chuyển khoản qua tài khoản đã nối SePay). Kiểm tra:
   - Telegram nhận thông báo như thường.
   - Zalo cũng nhận, dạng text thuần, kèm danh sách category đánh số nếu giao dịch
     chưa khớp keyword rule nào.
3. Reply con số trên Zalo → giao dịch được phân loại, y như tap nút bên Telegram.
4. Nếu chỉ Telegram nhận → xem log Railway, tìm dòng `[zalo]`.

## Vài điều nên biết

- **Gửi Zalo là best-effort.** API Zalo lỗi thì giao dịch vẫn vào Google Sheet và
  Telegram vẫn nhận tin — không có gì bị chặn lại.
- **Tin dài tự chia** thành nhiều phần, mỗi phần tối đa `ZALO_TEXT_LIMIT` ký tự.
- **Tắt bất cứ lúc nào**: `ZALO_ENABLED=false` rồi redeploy.
- **Bật là bật cả hai chiều.** Không có chế độ chỉ-nhận-thông-báo: bật kênh lên là
  bot vừa gửi vừa nhận lệnh, và vì thế mới cần secret ở Bước 3.

## Troubleshooting

| Vấn đề | Giải pháp |
|---|---|
| Zalo không nhận tin nào | Kiểm tra `ZALO_ENABLED=true`, `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID`; xem log Railway tìm `[zalo]` |
| Bot không khởi động sau khi bật Zalo | `ZALO_ENABLED=true` thì bắt buộc có `ZALO_SECRET_TOKEN`; thông báo lỗi lúc start ghi rõ biến nào thiếu |
| Gửi lệnh trên Zalo mà bot im | Chưa đăng ký webhook (Bước 5), hoặc `secret_token` không khớp `ZALO_SECRET_TOKEN`, hoặc `ZALO_CHAT_ID` sai |
| `zalo_get_updates.py` in ra rỗng | Nhắn cho bot trên Zalo trước rồi chạy lại. Nếu bot đã đăng ký webhook thì `getUpdates` luôn rỗng — lấy id từ log Railway |
| "Invalid token" | Token sai — script báo ngay ở bước `getMe`; lấy lại token từ Zalo Bot Manager |

## Tham khảo

- [Zalo Bot Platform docs](https://bot.zapps.me/docs/)
- [Tạo bot](https://bot.zapps.me/docs/create-bot/)
- [API Reference](https://bot.zapps.me/docs/call-api/)
