/**
 * Google Apps Script — Bank Email → Bot Webhook
 *
 * Setup:
 *   1. Vào script.google.com → New Project
 *   2. Paste toàn bộ file này vào
 *   3. Sửa WEBHOOK_URL và WEBHOOK_SECRET bên dưới
 *   4. Chạy thử hàm checkBankEmails() một lần để cấp quyền Gmail
 *   5. (Khuyến nghị) Chạy bootstrapProcessed() MỘT LẦN để đánh dấu toàn bộ
 *      email bank hiện có là "đã xử lý" → bot không re-process lịch sử.
 *   6. Triggers → Add Trigger → checkBankEmails → Time-driven → Every minute
 *
 * Script sẽ tự động:
 *   - Tìm email từ TCB / Cake / Hang Seng / Forwarders
 *   - Parse và gửi đến bot
 *   - Dedup theo MESSAGE ID (PropertiesService), KHÔNG theo thread
 *
 * ─── Vì sao dedup theo message, không theo thread ──────────────────────────
 * Gmail gộp các email cùng tiêu đề vào CHUNG một conversation thread. Hai
 * giao dịch khác nhau (vd 2 lần quẹt Grab liên tiếp) từ Cake có cùng subject
 * → nằm chung 1 thread. Cách cũ gắn Gmail label ở cấp THREAD và loại thread
 * đã-label khỏi query (`-label:bot-processed`). Hệ quả: khi giao dịch #2 về
 * và rơi vào thread đã được label, cả thread bị query loại bỏ → message #2
 * KHÔNG BAO GIỜ được gửi tới bot → bỏ sót giao dịch.
 *
 * Cách mới: dedup theo từng message ID. Mỗi message là 1 giao dịch độc lập,
 * dù nằm chung thread vẫn được xét riêng. Chỉ message đã gửi webhook THÀNH
 * CÔNG mới được ghi vào tập processed; lần sau gặp lại thì skip.
 */

// ─── Config — SỬA 2 DÒNG NÀY ────────────────────────────────────────────────
// This placeholder is deliberately non-routable. Never send bank-email data
// until it is replaced with the /webhook/email URL of YOUR Railway service.
const WEBHOOK_URL = "SET_YOUR_RAILWAY_WEBHOOK_EMAIL_URL";
// Set this manually in Apps Script and Railway; never commit a real secret.
const WEBHOOK_SECRET = "SET_EMAIL_SECRET_IN_APPS_SCRIPT";
// ─────────────────────────────────────────────────────────────────────────────

// Danh sách sender email ngân hàng cần theo dõi.
// Forwarders: nếu email được auto-forward từ Gmail khác,
// header `From:` của email forward thường là forwarder, không phải sender gốc
// → phải thêm địa chỉ forwarder vào đây.
// Python parser sẽ scan body để detect bank gốc từ "Forwarded message" block.
const BANK_SENDERS = [
  "automail@techcombank.com.vn",
  "ebank@techcombank.com.vn",
  "no-reply@techcombank.com.vn",
  "thongbao@techcombank.com.vn",
  "no-reply@cake.vn",
  "notification@cake.vn",
  "noreply@cake.vn",
  "hangseng@infoservices.hangseng.com",
  // Forwarders — nếu bạn auto-forward bank email từ Gmail khác:
  // "your-forwarder@gmail.com",
];

// Key lưu tập message ID đã xử lý trong Script Properties.
// Cấu trúc: { "<gmailMessageId>": <epochMillisKhiXuLy>, ... }
// Tự prune entry cũ hơn LOOKBACK_DAYS để không phình vô hạn.
const PROCESSED_PROP_KEY = "processed_msg_ids";
const SCAN_OFFSET_PROP_KEY = "bank_email_scan_offset";

// Số ngày giữ lại message ID trong tập processed (đủ rộng để cover bot down).
const LOOKBACK_DAYS = 7;

// Chỉ xét email mới — tránh quét cả lịch sử Gmail mỗi lần chạy.
const LOOKBACK = `newer_than:${LOOKBACK_DAYS}d`;

// (Tùy chọn) Vẫn gắn 1 Gmail label cho dễ nhìn trong inbox. KHÔNG dùng cho
// dedup nữa — chỉ là cờ trực quan. Đặt null để tắt hẳn.
const VISUAL_LABEL = "bot-processed";

/**
 * Hàm chính — chạy mỗi 1 phút theo trigger.
 *
 * Dùng LockService để 2 lần chạy trùng nhau không cùng ghi processed map.
 */
function checkBankEmails() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {
    console.log(`[checkBankEmails] could not acquire lock — skip this run`);
    return;
  }

  try {
    const query = buildGmailQuery();
    console.log(`[checkBankEmails] query: ${query}`);

    const props = PropertiesService.getScriptProperties();
    const offset = Math.max(0, Number(props.getProperty(SCAN_OFFSET_PROP_KEY) || "0"));
    const threads = GmailApp.search(query, offset, 30);
    if (threads.length === 0) {
      props.setProperty(SCAN_OFFSET_PROP_KEY, "0");
      console.log(`[checkBankEmails] 0 threads matched query`);
      return;
    }
    console.log(`[checkBankEmails] found ${threads.length} thread(s) at offset=${offset}`);

    const processed = _loadProcessed();
    const label = VISUAL_LABEL ? _getOrCreateLabel(VISUAL_LABEL) : null;

    let processedCount = 0;
    let skippedCount = 0;
    let errorCount = 0;

    threads.forEach(thread => {
      let threadHadSuccess = false;

      // Duyệt TỪNG message trong thread — mỗi message là 1 giao dịch riêng.
      thread.getMessages().forEach(msg => {
        const msgId = msg.getId();

        // Dedup theo message ID, KHÔNG theo thread.
        if (processed[msgId]) {
          skippedCount++;
          return;
        }

        const fromHeader = msg.getFrom();
        const subject = msg.getSubject();
        console.log(`[msg] id=${msgId} from=${fromHeader} subject=${subject}`);

        try {
          processMessage(msg);
          // Chỉ đánh dấu processed SAU KHI webhook trả 200.
          processed[msgId] = Date.now();
          processedCount++;
          threadHadSuccess = true;
        } catch (err) {
          console.error(`[checkBankEmails] error processing msg ${msgId}: ${err}`);
          errorCount++;
          // Không đánh dấu processed → retry lần chạy sau.
        }
      });

      // Gắn label trực quan nếu có ít nhất 1 message trong thread đã gửi OK.
      if (label && threadHadSuccess) {
        try {
          thread.addLabel(label);
        } catch (err) {
          console.error(`[checkBankEmails] failed to apply visual label: ${err}`);
        }
      }
    });

    // Lưu lại tập processed (kèm prune entry cũ).
    _saveProcessed(processed);
    // Advance over a full page so an outage/backlog cannot strand older
    // unprocessed messages behind the newest 30 threads. Reset after the tail.
    // Do not skip a page that had an unacknowledged message.
    props.setProperty(
      SCAN_OFFSET_PROP_KEY,
      errorCount === 0 && threads.length === 30 ? String(offset + 30) : "0"
    );

    console.log(`[checkBankEmails] done — processed=${processedCount} ` +
                `skipped=${skippedCount} errors=${errorCount}`);
  } finally {
    lock.releaseLock();
  }
}

/**
 * Xử lý 1 email — extract data và gọi bot webhook.
 * Throw nếu bot không trả exact JSON acknowledgment → caller sẽ KHÔNG đánh
 * dấu processed (để retry). A generic 200 page is never durable success.
 */
function processMessage(msg) {
  _requireWebhookConfig();
  const from = msg.getFrom();
  const subject = msg.getSubject();
  const body = msg.getPlainBody();
  const date = msg.getDate().toISOString();

  console.log(`[processMessage] from=${from} subject=${subject}`);

  const payload = {
    secret: WEBHOOK_SECRET,
    from: from,
    subject: subject,
    body: body,
    date: date,
  };

  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,  // không throw exception khi bot trả lỗi
    followRedirects: true,
  };

  const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
  const code = response.getResponseCode();
  const respBody = response.getContentText();

  console.log(`[processMessage] bot response: ${code} ${respBody}`);

  if (code !== 200) {
    // Throw để caller không đánh dấu processed → retry lần sau.
    throw new Error(`non-200 from bot: ${code} ${respBody}`);
  }
  let acknowledgment;
  try {
    acknowledgment = JSON.parse(respBody);
  } catch (err) {
    throw new Error(`invalid JSON acknowledgment from bot: ${respBody}`);
  }
  if (!acknowledgment || acknowledgment.ok !== true) {
    throw new Error(`negative acknowledgment from bot: ${respBody}`);
  }
}

function _requireWebhookConfig() {
  if (!WEBHOOK_URL.startsWith("https://") || WEBHOOK_URL.includes("SET_YOUR_")) {
    throw new Error("Set WEBHOOK_URL to your own Railway /webhook/email URL before enabling this trigger.");
  }
  if (!WEBHOOK_SECRET || WEBHOOK_SECRET.startsWith("SET_")) {
    throw new Error("Set WEBHOOK_SECRET to the EMAIL_SECRET configured in your Railway service.");
  }
}

/**
 * Build Gmail search query.
 * - from:(senders) → match bank/forwarder
 * - newer_than:Nd  → giới hạn quét lịch sử
 *
 * LƯU Ý: KHÔNG còn dùng `-label:bot-processed`. Dedup giờ làm ở cấp message
 * trong code (xem checkBankEmails) nên không bị bug "thread đã label che mất
 * giao dịch mới trong cùng thread".
 */
function buildGmailQuery() {
  const senderQuery = BANK_SENDERS.join(" OR ");
  return `from:(${senderQuery}) ${LOOKBACK}`;
}

// ─── Processed-IDs store (PropertiesService) ────────────────────────────────

/**
 * Đọc tập message ID đã xử lý từ Script Properties.
 * @return {Object<string, number>} map msgId → epochMillis
 */
function _loadProcessed() {
  const raw = PropertiesService.getScriptProperties().getProperty(PROCESSED_PROP_KEY);
  if (!raw) return {};
  try {
    const obj = JSON.parse(raw);
    return (obj && typeof obj === "object") ? obj : {};
  } catch (e) {
    console.error(`[_loadProcessed] corrupt JSON, resetting: ${e}`);
    return {};
  }
}

/**
 * Lưu tập processed, prune entry cũ hơn LOOKBACK_DAYS để tránh phình.
 * Script Properties giới hạn ~9KB/value, ~500KB tổng → prune là bắt buộc.
 * @param {Object<string, number>} map
 */
function _saveProcessed(map) {
  const cutoff = Date.now() - LOOKBACK_DAYS * 86400 * 1000;
  for (const id in map) {
    if (map[id] < cutoff) delete map[id];
  }
  PropertiesService.getScriptProperties()
    .setProperty(PROCESSED_PROP_KEY, JSON.stringify(map));
}

/**
 * Lấy hoặc tạo Gmail label (chỉ dùng cho hiển thị trực quan).
 */
function _getOrCreateLabel(name) {
  let label = GmailApp.getUserLabelByName(name);
  if (!label) {
    label = GmailApp.createLabel(name);
    console.log(`[setup] created Gmail label: ${name}`);
  }
  return label;
}

// ─── Hàm tiện ích chạy thủ công ─────────────────────────────────────────────

/**
 * Hàm test — gửi email gần nhất cho bot mà KHÔNG đánh dấu processed
 * → chạy lại nhiều lần để debug parser.
 */
function testWithRecentEmails() {
  const senderQuery = BANK_SENDERS.join(" OR ");
  const query = `from:(${senderQuery}) newer_than:1d`;
  const threads = GmailApp.search(query, 0, 5);

  console.log(`[test] found ${threads.length} thread(s) in last 24h`);

  threads.forEach(thread => {
    thread.getMessages().slice(0, 1).forEach(msg => {
      console.log(`\n--- EMAIL ---`);
      console.log(`Id: ${msg.getId()}`);
      console.log(`From: ${msg.getFrom()}`);
      console.log(`Subject: ${msg.getSubject()}`);
      console.log(`Body preview:\n${msg.getPlainBody().substring(0, 300)}`);
      console.log(`---`);

      const payload = {
        secret: WEBHOOK_SECRET,
        from: msg.getFrom(),
        subject: msg.getSubject(),
        body: msg.getPlainBody(),
        date: msg.getDate().toISOString(),
      };

      const options = {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(payload),
        muteHttpExceptions: true,
      };

      const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
      console.log(`Bot response: ${response.getResponseCode()} ${response.getContentText()}`);
    });
  });
}

/**
 * Hàm bootstrap — đánh dấu TẤT CẢ message bank hiện có là "đã xử lý"
 * mà KHÔNG gửi webhook. Chạy 1 lần ngay sau khi chuyển sang dedup theo
 * message để tránh bot re-process lịch sử và ghi trùng giao dịch.
 *
 * Sau khi chạy, chỉ message bank ARRIVE SAU thời điểm này mới được xử lý.
 */
function bootstrapProcessed() {
  const processed = _loadProcessed();
  const senderQuery = BANK_SENDERS.join(" OR ");
  const query = `from:(${senderQuery}) ${LOOKBACK}`;
  console.log(`[bootstrapProcessed] query: ${query}`);

  let total = 0;
  let start = 0;
  const PAGE = 50;
  const now = Date.now();

  while (true) {
    const threads = GmailApp.search(query, start, PAGE);
    if (threads.length === 0) break;

    threads.forEach(thread => {
      thread.getMessages().forEach(msg => {
        if (!processed[msg.getId()]) {
          processed[msg.getId()] = now;
          total++;
        }
      });
    });

    console.log(`[bootstrapProcessed] scanned ${threads.length} thread(s) at offset=${start}`);
    if (threads.length < PAGE) break;
    start += PAGE;
  }

  _saveProcessed(processed);
  console.log(`[bootstrapProcessed] DONE — marked ${total} message(s) as processed. ` +
              `Bot từ giờ chỉ xử lý message mới đến SAU thời điểm này.`);
}

/**
 * Hàm cleanup — xóa toàn bộ tập processed.
 * Chạy thủ công nếu muốn re-process lịch sử (cẩn thận: bot sẽ nhận lại các
 * email cũ; idempotency cuối cùng dựa vào ref_code phía Python xử lý).
 */
function resetProcessed() {
  PropertiesService.getScriptProperties().deleteProperty(PROCESSED_PROP_KEY);
  console.log(`[resetProcessed] cleared processed message-id store`);
}
