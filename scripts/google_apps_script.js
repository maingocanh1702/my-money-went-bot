/**
 * Google Apps Script — Bank Email → Bot Webhook
 *
 * Setup:
 *   1. Vào script.google.com → New Project
 *   2. Paste toàn bộ file này vào
 *   3. Sửa WEBHOOK_URL và WEBHOOK_SECRET bên dưới
 *   4. Chạy thử hàm checkBankEmails() một lần để cấp quyền Gmail
 *   5. Triggers → Add Trigger → checkBankEmails → Time-driven → Every minute
 *
 * Script sẽ tự động:
 *   - Tìm email chưa đọc từ TCB và Cake
 *   - Parse và gửi đến bot
 *   - Đánh dấu email đã đọc (để không gửi trùng)
 */

// ─── Config — SỬA 2 DÒNG NÀY ────────────────────────────────────────────────
const WEBHOOK_URL    = "https://YOUR-RAILWAY-DOMAIN.up.railway.app/webhook/email";
const WEBHOOK_SECRET = "your_random_email_secret_here";  // phải khớp với EMAIL_SECRET trong Railway
// ─────────────────────────────────────────────────────────────────────────────

// Danh sách sender email ngân hàng cần theo dõi
const BANK_SENDERS = [
  "automail@techcombank.com.vn",
  "ebank@techcombank.com.vn",
  "no-reply@techcombank.com.vn",
  "thongbao@techcombank.com.vn",
  "no-reply@cake.vn",
  "notification@cake.vn",
  "noreply@cake.vn",
];

/**
 * Hàm chính — chạy mỗi 1 phút theo trigger
 */
function checkBankEmails() {
  const query = buildGmailQuery();
  const threads = GmailApp.search(query, 0, 20);  // tối đa 20 thread mỗi lần

  if (threads.length === 0) return;

  console.log(`[checkBankEmails] found ${threads.length} thread(s)`);

  threads.forEach(thread => {
    const messages = thread.getMessages();
    messages.forEach(msg => {
      if (!msg.isUnread()) return;  // chỉ xử lý email chưa đọc

      try {
        processMessage(msg);
      } catch (err) {
        console.error(`[checkBankEmails] error processing msg ${msg.getId()}: ${err}`);
      } finally {
        // Luôn đánh dấu đã đọc để không xử lý lại
        msg.markRead();
      }
    });
  });
}

/**
 * Xử lý 1 email — extract data và gọi bot webhook
 */
function processMessage(msg) {
  const from    = msg.getFrom();
  const subject = msg.getSubject();
  const body    = msg.getPlainBody();
  const date    = msg.getDate().toISOString();

  console.log(`[processMessage] from=${from} subject=${subject}`);

  const payload = {
    secret:  WEBHOOK_SECRET,
    from:    from,
    subject: subject,
    body:    body,
    date:    date,
  };

  const options = {
    method:      "post",
    contentType: "application/json",
    payload:     JSON.stringify(payload),
    muteHttpExceptions: true,  // không throw exception khi bot trả lỗi
  };

  const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
  const code     = response.getResponseCode();
  const respBody = response.getContentText();

  console.log(`[processMessage] bot response: ${code} ${respBody}`);

  if (code !== 200) {
    console.warn(`[processMessage] non-200 from bot: ${code}`);
  }
}

/**
 * Build Gmail search query cho tất cả sender ngân hàng
 * Kết quả: "from:(sender1 OR sender2 OR ...) is:unread"
 */
function buildGmailQuery() {
  const senderQuery = BANK_SENDERS.join(" OR ");
  return `from:(${senderQuery}) is:unread`;
}

/**
 * Hàm test — chạy thủ công để kiểm tra không cần chờ trigger
 * Tìm email đã đọc trong 24h qua để test parser mà không cần giao dịch mới
 */
function testWithRecentEmails() {
  const senderQuery = BANK_SENDERS.join(" OR ");
  // Tìm cả đã đọc + chưa đọc trong 1 ngày qua
  const query   = `from:(${senderQuery}) newer_than:1d`;
  const threads = GmailApp.search(query, 0, 5);

  console.log(`[test] found ${threads.length} thread(s) in last 24h`);

  threads.forEach(thread => {
    thread.getMessages().slice(0, 1).forEach(msg => {
      console.log(`\n--- EMAIL ---`);
      console.log(`From: ${msg.getFrom()}`);
      console.log(`Subject: ${msg.getSubject()}`);
      console.log(`Body preview:\n${msg.getPlainBody().substring(0, 300)}`);
      console.log(`---`);

      // Gọi bot (KHÔNG đánh dấu đã đọc trong test mode)
      const payload = {
        secret:  WEBHOOK_SECRET,
        from:    msg.getFrom(),
        subject: msg.getSubject(),
        body:    msg.getPlainBody(),
        date:    msg.getDate().toISOString(),
      };

      const options = {
        method:             "post",
        contentType:        "application/json",
        payload:            JSON.stringify(payload),
        muteHttpExceptions: true,
      };

      const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
      console.log(`Bot response: ${response.getResponseCode()} ${response.getContentText()}`);
    });
  });
}
