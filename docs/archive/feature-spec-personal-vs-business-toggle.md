# Feature Spec — Personal vs Business Toggle

> Feature must-have #3 trong Business tier của FinTrack. Đây là **foundation feature** — Tag-based P&L và Income source attribution đều depend on data được tag đúng từ feature này.
>
> **Status:** Draft v1
> **Owner:** Product
> **Last updated:** 2026-05-05
> **Target release:** Business tier launch (Phase 2, ~tháng 9-10/2026)

---

## 1. Context & Problem

### 1.1. Pain point cụ thể

Persona Hùng+ có 2 luồng tiền lẫn lộn — **shop money** và **personal money** — đi qua cùng 2-3 bank accounts. Hiện tại:

- 65% Hùng+ dùng Excel cộng tay cuối tháng → tốn 4-6h, sai 2-3 triệu
- Không real-time, đến cuối tháng mới biết shop lãi/lỗ
- Khi rút tiền shop về dùng cá nhân (vd ăn uống bằng thẻ shop), không tag được → distort P&L

### 1.2. Hypothesis

Nếu mỗi transaction được tag rõ **personal/business** ngay khi capture (auto + manual override), thì:

- Cuối tháng P&L tính được trong 1 giây thay vì 4-6h
- Real-time visibility — Hùng+ biết hôm nay shop lãi hay lỗ ngay
- Data clean để export cho kế toán dịch vụ / ngân hàng

### 1.3. Tại sao đây là foundation feature

Tag-based P&L (Feature must-have #1) và Income source attribution (#2) đều **đọc cùng 1 column data** — `entity_type`. Nếu Personal vs Business toggle build sai, 2 feature kia không hoạt động đúng.

---

## 2. Goals & Non-Goals

### 2.1. Goals (V1)

- Mỗi transaction có rõ ràng 1 trong 3 trạng thái: `personal`, `business`, `unknown` (default ban đầu).
- Auto-detect mặc định theo bank account (vd: tiền vào MB account → mặc định `business`, tiền vào TCB → mặc định `personal`).
- Manual override 1-tap trong Telegram inline button.
- Bulk re-tag (vd "tag tất cả giao dịch từ supplier X là business").
- Migration path cho existing transactions khi user upgrade lên Business tier.

### 2.2. Non-Goals (V1, defer V2)

- **Multi-business support** — vd "Shop A vs Shop B vs Personal". V1 chỉ 2-way toggle. Multi-stream attribution là Feature #2 sẽ build sau.
- **Split transaction** — vd "transaction 500k này 30% personal, 70% business". Edge case <5%, defer V2.
- **Auto-rule learning từ ML** — V1 chỉ rule-based đơn giản (theo bank account + manual rule). ML defer V3.
- **Shared expense với family** — out of scope, đây là family/team feature (Phase 3+).

---

## 3. User Stories & Acceptance Criteria

### US-1: Auto-tag theo bank account

**As** Hùng+ đã setup 2 bank accounts (1 cá nhân TCB, 1 shop MB),
**I want** giao dịch tự động được tag personal/business theo account nó vào,
**So that** tôi không phải tag thủ công 60-80 transaction/ngày.

**Acceptance Criteria:**
- [ ] User config trong onboarding Business tier: chọn account nào là "Personal source", account nào là "Business source", có thể chọn "Mixed" (default ask)
- [ ] Khi giao dịch mới đến qua SePay, system check source account → assign `entity_type` mặc định
- [ ] Transaction message trong Telegram hiển thị tag rõ ràng (vd icon 🏪 cho business, 🏠 cho personal)
- [ ] Nếu account là "Mixed", transaction default `unknown` và prompt user

### US-2: Manual override 1-tap

**As** Hùng+ vừa nhận transaction được auto-tag sai (vd ăn cơm bằng thẻ shop nhưng default tag là business),
**I want** override bằng 1 tap trong Telegram,
**So that** P&L của tôi accurate.

**Acceptance Criteria:**
- [ ] Mỗi transaction message có inline button: `🏪 Business | 🏠 Personal | ❓ Unknown`
- [ ] Tap toggle ngay lập tức cập nhật trong DB và acknowledge "✓ Đã đổi sang Personal"
- [ ] User có thể override **nhiều lần** trong 24h, sau 24h transaction lock (cần dùng `/edit <tx_id>` để edit)
- [ ] Override action được log để metric (xem mục 7)

### US-3: Bulk re-tag theo rule

**As** Hùng+ phát hiện tất cả giao dịch từ supplier "Cong Ty ABC" đều là business,
**I want** tạo rule auto-tag cho mọi giao dịch matching pattern này,
**So that** không phải tag từng cái.

**Acceptance Criteria:**
- [ ] Long-press hoặc `/rule` trên 1 transaction → tạo rule "Mỗi giao dịch chứa 'Cong Ty ABC' → tag Business"
- [ ] Rule áp dụng cho transactions tương lai
- [ ] Optional: "Áp dụng cho 30 ngày qua" — backfill historical (default off để tránh accident)
- [ ] User xem & quản lý rules qua `/rules`
- [ ] Max 20 rules/user (V1 limit)

### US-4: Migration cho existing transactions

**As** Hùng+ vừa upgrade lên Business tier sau 2 tháng dùng Pro,
**I want** đánh giá lại 200+ transaction cũ với personal/business tag,
**So that** P&L view đầu tiên không trống rỗng.

**Acceptance Criteria:**
- [ ] Sau upgrade, system trigger migration wizard: "Tag 200 giao dịch cũ?"
- [ ] Wizard show pattern detection: "85% giao dịch từ MB là tới merchant Shopee/TikTok — tag tất cả là Business?" (Y/N)
- [ ] Sau pattern bulk, remaining transactions tag default `unknown`, user có thể bulk tag sau
- [ ] Migration optional, có thể skip và bắt đầu fresh từ ngày upgrade

### US-5: View P&L với data đã tag

**As** Hùng+,
**I want** lệnh `/pnl` hiển thị P&L tách rõ Personal vs Business,
**So that** tôi biết shop lãi/lỗ thực sự sau khi rút tiền cá nhân.

**Acceptance Criteria:**
- [ ] `/pnl` hoặc `/pnl tháng-này` hiển thị format:
  ```
  📊 P&L Tháng 5/2026

  🏪 BUSINESS
    Revenue: +120,500,000đ
    Expense: -85,200,000đ (ads, hàng, ship)
    Net: +35,300,000đ ✅

  🏠 PERSONAL
    Income: +35,000,000đ (rút từ shop)
    Expense: -28,000,000đ (ăn, gas, etc)
    Net: +7,000,000đ ✅

  ❓ UNCATEGORIZED: 3 giao dịch (1,200,000đ)
    [Tag now]
  ```
- [ ] Click [Tag now] mở mini-flow tag từng tx unknown
- [ ] `/pnl quý-này`, `/pnl năm-nay` cho time range khác

---

## 4. UX Flow trong Telegram

### 4.1. Onboarding (khi user upgrade Business tier)

```
[User: /upgrade business]
Bot: ✓ Welcome to Business tier!

      Để tách giao dịch shop vs cá nhân, mình cần biết
      account nào dùng cho mục đích gì.

      Bạn có 3 accounts:
      1. TCB ****1234 → [🏠 Personal] [🏪 Business] [❓ Mixed]
      2. MB ****5678  → [🏠 Personal] [🏪 Business] [❓ Mixed]
      3. ACB ****9012 → [🏠 Personal] [🏪 Business] [❓ Mixed]

[User taps: TCB Personal, MB Business, ACB Mixed]
Bot: ✓ Đã lưu. Giao dịch mới sẽ tự động tag theo account.
      Bạn có muốn tag 200 giao dịch cũ không? [Yes] [Skip]
```

### 4.2. Transaction notification (post-tag)

```
🔔 Giao dịch mới
💰 -250,000đ
📍 Shopee Ads
🏦 MB ****5678

🏪 Business (auto)  [🏠 Personal] [❓ Other]

📁 Category: [Ads] [Other]
```

User có thể:
- Tap [🏠 Personal] để override
- Tap [❓ Other] để thấy options khác (vd Mixed, hoặc tạo new entity)
- Tap [Ads] để confirm category (existing flow)

### 4.3. View P&L

```
[User: /pnl]
Bot: 📊 P&L Tháng 5/2026

      🏪 BUSINESS
        Revenue:  +120,500,000đ
        Expense:   -85,200,000đ
        Net:       +35,300,000đ ✅

      🏠 PERSONAL
        Income:    +35,000,000đ
        Expense:   -28,000,000đ
        Net:        +7,000,000đ ✅

      ❓ UNCATEGORIZED: 3 tx (1,200,000đ)
      [Tag now] [View detail] [Export]
```

---

## 5. Data Model

### 5.1. Schema changes

```sql
-- New column on transactions table
ALTER TABLE transactions ADD COLUMN entity_type
  ENUM('personal', 'business', 'unknown') NOT NULL DEFAULT 'unknown';

ALTER TABLE transactions ADD COLUMN entity_set_by
  ENUM('auto_account', 'auto_rule', 'manual', 'migration') NOT NULL DEFAULT 'auto_account';

ALTER TABLE transactions ADD COLUMN entity_set_at TIMESTAMP;

-- New table for bank account → entity mapping
CREATE TABLE bank_account_entity_default (
  user_id UUID NOT NULL,
  bank_account_id UUID NOT NULL,
  default_entity ENUM('personal', 'business', 'unknown') NOT NULL,
  created_at TIMESTAMP NOT NULL,
  PRIMARY KEY (user_id, bank_account_id)
);

-- New table for auto-tagging rules
CREATE TABLE entity_rules (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  match_pattern TEXT NOT NULL,  -- regex hoặc substring match trên description
  match_field ENUM('description', 'merchant', 'amount_range') NOT NULL,
  target_entity ENUM('personal', 'business') NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL,
  applied_count INTEGER DEFAULT 0
);
```

### 5.2. Audit & changelog

Mỗi lần `entity_type` đổi → ghi audit log để debug và reverse nếu cần:

```sql
CREATE TABLE entity_change_log (
  id UUID PRIMARY KEY,
  transaction_id UUID NOT NULL,
  old_entity ENUM('personal', 'business', 'unknown'),
  new_entity ENUM('personal', 'business', 'unknown'),
  changed_by ENUM('auto_account', 'auto_rule', 'manual', 'migration'),
  rule_id UUID NULL,  -- nếu changed_by = auto_rule
  changed_at TIMESTAMP NOT NULL
);
```

---

## 6. Edge Cases

| Edge case | Handling |
|-----------|---------|
| User chuyển tiền giữa 2 own accounts (vd rút từ shop về personal) | Detect bằng cách match outgoing tx ở account A với incoming tx amount tương đương ở account B trong 5 phút → tag là `internal_transfer`, exclude khỏi P&L |
| Account "Mixed" có giao dịch mới | Default `unknown`, prompt user tag |
| User edit tag sau khi đã >24h | Cho phép qua `/edit <tx_id>`, ghi audit log |
| Rule apply sai (vd false positive) | Notification "Rule X applied to N transactions. Undo?" trong 1h sau apply |
| User xóa bank account đã có default mapping | Soft-delete mapping, transactions cũ giữ tag, transactions mới từ account khác apply default mapping mới |
| 2 rule conflict nhau (cùng match 1 tx) | Rule tạo gần nhất thắng. Show warning trong `/rules` UI |
| User downgrade từ Business → Pro | Giữ data `entity_type` trong DB nhưng UI ẩn tag column. Khi re-upgrade thì hiện lại |
| Transaction từ unknown source (manual entry, CSV import) | Default `unknown`, prompt user tag khi import |

---

## 7. Metrics (đo success của feature)

### 7.1. Activation metrics

| Metric | Target | Cách đo |
|--------|--------|---------|
| % Business user setup account mapping trong 24h | >80% | Onboarding funnel |
| % transactions có `entity_type` ≠ `unknown` sau 7 ngày | >85% | DB query |
| Median time để user tag 1 transaction (manual) | <5s | Event timing |

### 7.2. Engagement metrics

| Metric | Target | Cách đo |
|--------|--------|---------|
| % user dùng `/pnl` trong tuần đầu | >60% | Command analytics |
| Repeat usage `/pnl` (≥3 lần/tháng) | >50% | Command analytics |
| % user tạo ≥1 rule trong tháng đầu | >30% | DB query |

### 7.3. Quality metrics

| Metric | Target | Cách đo |
|--------|--------|---------|
| Override rate (auto tag bị user đổi) | <15% | `entity_set_by` = manual sau khi đã có auto |
| Rule false-positive rate | <5% | Tracking [Undo] click sau rule apply |
| Internal transfer detection accuracy | >95% | Manual audit 50 tx/tháng |

---

## 8. Dependencies

### 8.1. Phải có trước

- **Multi-bank account support trong Business tier** (3-5 accounts) — Feature must-have #5. Personal vs Business toggle depend on việc user có >1 account.
- **Bank account → entity mapping UI** trong onboarding flow.

### 8.2. Block / unblock features khác

- ✅ Unblock: **Tag-based P&L view** (Feature #1) — đọc data từ `entity_type` column
- ✅ Unblock: **Income source attribution** (Feature #2) — extend `entity_type` thành `entity_id` cho multi-stream
- ✅ Unblock: **Google Sheets sync** — export schema cần `entity_type` column

---

## 9. Open Questions

1. **Default behavior khi không có bank account mapping:** auto `unknown` và bug user, hay auto `personal` (assumption phổ biến hơn)?
   → Recommend: `unknown` + 1 prompt onboarding. Tránh assumption sai.

2. **Có support `entity_type = 'mixed'` không (cho transaction phục vụ cả 2 mục đích)?**
   → V1: KHÔNG. Force user chọn 1 trong 2. Edge case <5%. V2 cân nhắc split feature.

3. **Khi nào trigger migration wizard cho existing tx?**
   → Recommend: ngay sau khi user complete onboarding Business tier setup. Nếu skip thì dismiss permanent (không nhắc lại).

4. **Pricing tier downgrade (Business → Pro): có giữ data tag không?**
   → Recommend: GIỮ trong DB, ẩn UI. Nếu re-upgrade trong 6 tháng → show lại nguyên trạng.

5. **Auto-detection có dùng ML hay rule-based đủ?**
   → V1: rule-based (account + pattern matching). V2 cân nhắc ML nếu có >10k transactions/tenant.

---

## 10. Rollout Plan

### Phase 1: Internal alpha (1 tuần)
- Build core: schema, auto-tag by account, manual toggle in Telegram
- Test với 1-2 internal user (founder + 1 dogfooder)

### Phase 2: Closed beta (2 tuần)
- 5-10 Business tier early users (recruit từ Hùng+ persona research)
- Free Business access trao đổi feedback weekly
- Metric đo: activation, override rate, /pnl usage

### Phase 3: Public Business tier launch
- Go-live cho all Business subscribers
- Migration wizard cho existing Pro users upgrade
- Marketing: blog post + Facebook group seeder + landing page

### Success criteria để go-live:
- [ ] Activation >80% trong closed beta
- [ ] Override rate <20% (auto-tag hoạt động đủ tốt)
- [ ] `/pnl` repeat usage >40% trong 2 tuần
- [ ] Zero data corruption / cross-tenant leak

---

**End of feature spec.**
