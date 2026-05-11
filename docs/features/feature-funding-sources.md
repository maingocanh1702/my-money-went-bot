# Feature: Funding Sources — Tài khoản & Thẻ (F08)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-11
> **Trạng thái:** Draft
> **Owner:** Founder (dev)
> **Market:** 🇻🇳 VN (SePay + email). Global track sẽ có spec riêng dùng Plaid metadata.
> **Phase:** Phase 1-2 (xây trên Transaction Capture pipeline có sẵn)
> **Tham chiếu:**
> - [feature-transaction-capture.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-transaction-capture.md) (F02)
> - [feature-reports.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-reports.md) (F05) — per-account breakdown
> - [feature-settings.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-settings.md) (F07)
> - [PRD-vi §3.2 Transaction Capture](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)
> - [TDD-vi §2.1 Schema](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)

---

## 1. Mô tả

Định danh + theo dõi từng **tài khoản ngân hàng / thẻ ghi nợ / thẻ tín dụng / ví điện tử** mà user đã link với bot (qua SePay hoặc email). Mỗi giao dịch trong [Transaction Capture (F02)](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-transaction-capture.md) sẽ được attach FK vào đúng funding source, cho phép user xem chi-tiêu/thu-nhập theo từng nguồn tiền.

Tinh thần thiết kế: **passive discovery + zero-friction onboarding**. User không phải khai báo trước — bot tự nhận diện khi tx đầu tiên của một nguồn về, lưu silent, ping user 1 lần để confirm/đổi tên. Sau đó dùng nguồn này làm dimension trong /reports, /banks.

> **i18n:** Toàn bộ message user-facing đi qua `t(user.locale, key)`. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).

**Canonical Funding Source Schema:**

| Field | Type | Mô tả |
|-------|------|------|
| id | int | PK |
| user_id | int | FK → users(id) |
| kind | enum | `bank_account` / `debit_card` / `credit_card` / `e_wallet` |
| bank | string | Ticker đã normalize: `TCB`, `MB`, `Cake`, `MoMo`, ... |
| last4 | string(4) | 4 số cuối account number / subAccount (NULL nếu không có) |
| display_id | string | Slug hiển thị `{bank}-{last4}` hoặc `{bank}` nếu last4 rỗng. **KHÔNG phải canonical identity** — chỉ để render + mirror column P cũ. |
| nickname | string(32)? | User-friendly name (`"Lương chính"`, `"Thẻ tiêu"`) — NULL = chưa đặt |
| first_seen_at | timestamptz | Lần đầu detect (= tx_date của tx đầu tiên) |
| last_tx_at | timestamptz | Lần cuối có tx — drive auto-archive sau 180 ngày silent |
| status | enum | `active` (default) / `hidden` (user-intentional) / `archived` (cron auto sau 180d silent) |
| archived_at | timestamptz? | NULL trừ khi `status='archived'` — log thời điểm cron set |

**Canonical identity** = `(user_id, kind, bank, last4)`. Cùng `display_id="TCB-1234"` có thể tồn tại 2 entry hợp lệ nếu khác `kind` (vd: 1 debit account + 1 credit card cùng số cuối). Xem §4 Domain Model cho unique constraint chính xác.

> **Convention:** `display_id` mirror string đang được lưu ở column P (sheets `bank_account`) hôm nay để compat với code legacy. Mọi join, FK, query nội bộ đều đi qua `funding_sources.id` — KHÔNG dùng `display_id` làm key.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | System | Tx đầu tiên từ TK chưa có trong registry | Auto-INSERT `funding_sources` (`status='active'`, `nickname=NULL`), prepend header `📥 Phát hiện TK mới: TCB-1234` vào chính category picker (1 message — xem §3.1) |
| 2 | System | Tx từ TK đã có trong registry | Skip insert, update `last_tx_at`, gắn FK lên tx như bình thường |
| 3 | User | Bấm `/accounts` | List tất cả funding sources của user, sort theo `last_tx_at` desc, kèm spent/income tháng này |
| 4 | User | Bấm "✏️ Đổi tên" → chọn TK → gõ tên mới | Cập nhật `nickname`, mọi nơi hiển thị (reports, picker) đổi sang tên mới |
| 5 | User | Bấm "🚫 Ẩn" → chọn TK | Set `status='hidden'`. Không xoá tx cũ. Ẩn khỏi /reports BY BANK section trừ khi explicit `--include-hidden`. Hidden là intentional, KHÔNG auto-bật lại khi tx mới về (xem case #9b) |
| 6 | User | Bấm "➕ Thêm thủ công" → chọn bank + nhập last4 + chọn kind + nickname | Pre-register funding source để các tx tương lai tự link. Dành cho card chưa swipe lần nào. Duplicate check theo `(kind, bank, last4)` — cùng số cuối khác kind là 2 entry hợp lệ. |
| 7 | User | Bấm `/banks` (legacy alias) | Tương đương `/accounts` view với category breakdown — giữ để backward compat |
| 8 | User | Gọi `/reports account=TCB-1234` (display_id only) | Nếu 1 funding source match → filter ngay. Nếu ≥2 match (vd debit + credit cùng TCB-1234) → bot list các option `[1️⃣ TCB-1234 (TK ngân hàng)] [2️⃣ TCB-1234 (Thẻ tín dụng)]` cho user chọn. |
| 8b | User | Gọi `/reports account=credit_card:TCB-1234` (power syntax) | Filter trực tiếp không hỏi, vì `kind:display_id` đã đủ canonical |
| 9a | System | TK `status='archived'` (cron) có tx mới về | Auto-resurrect (`status='active'`, `archived_at=NULL`), notify "📥 TK Cake-9012 đã có tx mới — đã bật lại." |
| 9b | System | TK `status='hidden'` (user-hide) có tx mới về | Tx vẫn gắn FK bình thường, KHÔNG resurrect (vì user ẩn có chủ ý). Không notify. Tx sẽ chỉ hiện khi user dùng `--include-hidden`. |
| 10 | System | Tx có `bank_account=""` (SePay không gửi gateway) | `funding_source_id=NULL`, gom nhóm "Không rõ" như hôm nay |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|------|
| 1 | Identity collision | SePay gửi "Techcombank" và "TCB" cho cùng 1 TK | Normalize qua `BANK_ALIASES` (có sẵn ở `handlers/sepay.py`) trước khi compute `display_id` |
| 2 | Identity collision | Last4 trùng giữa 2 bank (TCB-1234 vs MB-1234) | Tách thành 2 funding sources — `(user_id, kind, bank, last4)` là canonical identity |
| 2b | Identity collision | Cùng `TCB-1234` xuất hiện cả debit account và credit card | 2 funding sources hợp lệ với `kind` khác nhau — unique chỉ enforce cùng (kind, bank, last4) |
| 3 | Identity ambiguity | Không có accountNumber → last4 không có | Lưu `last4=''` (empty string, NOT NULL với default ''). Unique constraint vẫn enforce vì empty string is comparable. User có thể edit last4 sau qua /accounts (out of MVP). |
| 4 | Inference | Email TCB có subject chứa "thẻ tín dụng" hoặc "credit card" | Set `kind=credit_card` thay vì `bank_account` default |
| 5 | Inference | Gateway = "MoMo" / "ZaloPay" / "ViettelPay" / "ShopeePay" | Set `kind=e_wallet` |
| 6 | Inference | Card last4 đặt cùng `last4` với debit account của cùng bank | Nếu user đã có `(TCB, 1234, bank_account)` và source = email credit card → tạo entry mới `(TCB, 1234, credit_card)` riêng. Không merge. |
| 7 | Race | 2 webhook đồng thời cho cùng TK mới | UPSERT `ON CONFLICT (user_id, kind, bank, last4) DO UPDATE SET last_tx_at=...` — 1 thắng, 1 nhận FK đã có. Conflict target khớp chính xác unique constraint chính. |
| 8 | UX | User bấm rename giữa lúc có tx về | Lock theo `user_id` ở bot_state — tx mới attach FK xong rồi báo lên picker, không block rename |
| 9 | Reliability | User đổi tên thành chuỗi rỗng / chỉ space | Validate: strip whitespace, reject nếu len < 1 sau strip |
| 10 | Reliability | Nickname > 32 ký tự | Trả "❌ Tên tối đa 32 ký tự." giữ state, không thoát flow |
| 11 | Pricing | Free tier có giới hạn số funding sources không? | **KHÔNG** — discovery passive, user không tự thêm hàng loạt được. Giới hạn email source (Free=1, Pro=3) đã đủ proxy. |
| 12 | Data integrity | Migrate row tx cũ (column P đã có string nhưng chưa có FK) | One-off backfill script: với mỗi distinct `bank_account` string per user, tạo funding_source record, gán FK vào tx |
| 13 | Privacy | User xoá tài khoản | Tuân theo [TDD-vi §6.3 PDPA](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md). FK chain do F08 enforce: `users → funding_sources` `ON DELETE CASCADE` (xoá user xoá funding_sources). `funding_sources → transactions` `ON DELETE SET NULL` (xoá fs giữ tx, FK reset NULL). **F08 KHÔNG quyết định** số phận của tx khi hard-delete user — TDD §6.3 quyết: tx được xoá luôn HOẶC anonymize-then-keep (tách bạch khỏi user data). Soft delete: chỉ set `users.deleted_at`, app layer ẩn rows, không touch funding_sources / transactions. |
| 14 | Cross-feature | Daily recap (F09) hiển thị "spent today" | Có thể group theo funding source — out of scope F08, chỉ expose data |

---

## 3. Screens & States

### 3.1. Auto-discovery notification — embedded vào picker (1 message)

Khi tx đầu tiên của 1 funding source mới về, **KHÔNG gửi message riêng**. Thay vào đó, header `📥 Phát hiện TK mới` được prepend vào chính category picker — user thấy 1 message duy nhất chứa cả info phát hiện + lựa chọn category:

```
📥 _Phát hiện tài khoản mới:_ `TCB-1234` (Techcombank · ATM/Debit)
   _Dùng /accounts để đặt tên._

💸 -120,000đ
Pho 24 Nguyen Hue

Khoản này thuộc mục nào? 🤔

[🛒 Daily Spending] [🏦 Saving]
[💼 Work]           [👗 Clothes]
[📱 Subscription]   [➕ New category]
[⏭️ Bỏ qua]
```

**Tại sao:** category picker ĐÃ chứa tx info (amount + description) — discovery header là metadata cùng cảnh ngữ, không đáng tách message. Tránh 2 ping liên tiếp (noisy UX).

**Fallback (delayed-send) nếu messenger adapter không support combined message** (vd: Discord embed limit, future channel): send notification 1.5s sau picker với rate-limit (max 1 notif/user/5s) để tránh spam khi nhiều TK mới về cùng lúc.

- **Error:** Nếu insert funding_source fail (DB lỗi) → silent fallback: tx vẫn lưu với `funding_source_id=NULL` + column P string giữ nguyên (backward compat). Không thông báo user.
- **Empty:** N/A (chỉ trigger khi `was_discovered=TRUE`)

### 3.1b. Auto-resurrect notification

Khi tx về cho TK đang `status='archived'` (cron cleanup, KHÔNG phải user-hide), gửi 1 message riêng nhẹ NGAY SAU picker (1.5s delay) — vì resurrect là exception flow, không xảy ra thường xuyên đủ để cần embed:

```
📥 _TK `Cake-9012` đã có tx mới — đã bật lại trong list._
```

Nếu TK đang `status='hidden'` (user-hide) thì KHÔNG resurrect, KHÔNG notify — tôn trọng ý định user (xem Use Case 9b).

### 3.2. `/accounts` — List view

- **Loading:** "⏳ Đang load…" (timeout 3s)
- **Ready:**
```
🏦 *Tài khoản & Thẻ*   (3 nguồn · tháng 05/2026)
─────────────────────────────

1️⃣  *Lương chính*  `TCB-1234`
     💸 -2,340,000đ  · 💚 +15,000,000đ  · 12 GD

2️⃣  *Thẻ tiêu*  `Cake-9012`  💳
     💸 -1,120,000đ  · 8 GD

3️⃣  `MB-5678`  _(chưa đặt tên)_
     💸 -800,000đ  · 5 GD

[✏️ Đổi tên]  [🚫 Ẩn]  [➕ Thêm thủ công]
[🔍 Xem chi tiết theo category → /banks]
```
- **Error:** "⚠️ Không load được danh sách. Thử lại sau."
- **Empty:** "Chưa có tài khoản nào được nhận diện. Bot sẽ tự thêm khi GD đầu tiên về."

### 3.3. Rename flow

```
User: [bấm ✏️ Đổi tên]
Bot:  "Chọn tài khoản muốn đổi tên:"
      [1️⃣ TCB-1234] [2️⃣ Cake-9012] [3️⃣ MB-5678] [❌ Huỷ]

User: [bấm 1️⃣]
Bot:  "Đặt tên mới cho `TCB-1234` (max 32 ký tự, gửi /cancel để huỷ):"

User: "Lương chính"
Bot:  "✅ Đã đổi: TCB-1234 → *Lương chính*"
```

State machine bám sát `bot_state.step = 'await_rename_funding_source'` với payload `{funding_source_id}`. Xem `feature-funding-sources-tech.md` §4.

### 3.4. Manual add flow

```
User: [bấm ➕ Thêm thủ công]
Bot:  "Bank nào?"
      [TCB] [MB] [VCB] [Cake] [ACB] [STB] [Khác…]

User: [TCB]
Bot:  "4 số cuối tài khoản/thẻ (đúng 4 chữ số, hoặc gửi 'skip' nếu không có):"

User: "9999"   ← passes validation ^\d{4}$
Bot:  "Loại?"
      [🏦 TK ngân hàng] [💳 Thẻ ghi nợ] [💳 Thẻ tín dụng] [👛 Ví điện tử]

User: [💳 Thẻ tín dụng]
Bot:  "Nickname? (max 32 ký tự, hoặc 'skip' để dùng default 'TCB-9999')"

User: "Visa Platinum"
Bot:  "✅ Đã thêm: *Visa Platinum* (TCB-9999, credit card)"
```

**Validation last4:**
- Regex `^\d{4}$` (đúng 4 chữ số) HOẶC literal `"skip"` (case-insensitive).
- Reject + stay state: chữ cái lẫn vào (`12a4`), độ dài khác 4 (`123`, `12345`), ký tự đặc biệt (`12-34`).
- E-wallet: `skip` được khuyến nghị (MoMo/ZaloPay không có "last4" theo nghĩa thẻ ngân hàng) — nhưng vẫn chấp nhận 4 số nếu user muốn (vd: số điện thoại 4 số cuối).
- Error message: "❌ Vui lòng nhập đúng 4 chữ số (vd: 1234) hoặc gửi 'skip'."

### 3.5. Hide flow

```
User: [bấm 🚫 Ẩn]
Bot:  "Ẩn tài khoản nào? Tx cũ vẫn giữ, chỉ ẩn khỏi list & report mặc định."
      [1️⃣ TCB-1234] [...] [❌ Huỷ]

User: [bấm 3️⃣]
Bot:  "🚫 Đã ẩn `MB-5678`. Bot vẫn ghi GD nếu TK này có tx mới,
       nhưng sẽ tiếp tục ẩn khỏi /accounts và /reports mặc định.
       Dùng `/accounts --include-hidden` để xem/bật lại."
```

---

## 4. Domain Model

**Tables:** `funding_sources` (mới), `transactions` (mở rộng), `bot_state` (thêm step).

```sql
-- ═══════════════════════════════════════════════════════
-- Funding Sources (bank accounts, cards, e-wallets)
-- ═══════════════════════════════════════════════════════
CREATE TABLE funding_sources (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            VARCHAR(16) NOT NULL,        -- 'bank_account'/'debit_card'/'credit_card'/'e_wallet'
    bank            VARCHAR(16) NOT NULL,        -- normalized ticker: 'TCB','MB','Cake',...
    last4           VARCHAR(4)  NOT NULL DEFAULT '',  -- '' khi SePay không gửi account number
    display_id      VARCHAR(32) NOT NULL,        -- '{bank}-{last4}' hoặc '{bank}' (hiển thị/mirror col P)
    nickname        VARCHAR(32),                 -- NULL = chưa đặt
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_tx_at      TIMESTAMPTZ,
    status          VARCHAR(16) NOT NULL DEFAULT 'active',
    archived_at     TIMESTAMPTZ,                 -- NULL khi status != 'archived'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Canonical identity. last4 = '' khi không có số cuối — vẫn comparable, tránh NULL-trap.
    UNIQUE(user_id, kind, bank, last4),

    CONSTRAINT chk_fs_kind   CHECK (kind   IN ('bank_account','debit_card','credit_card','e_wallet')),
    CONSTRAINT chk_fs_status CHECK (status IN ('active','hidden','archived')),
    CONSTRAINT chk_fs_archived_consistency CHECK (
        (status = 'archived' AND archived_at IS NOT NULL)
        OR (status <> 'archived' AND archived_at IS NULL)
    )
);

CREATE INDEX idx_fs_user_status  ON funding_sources(user_id, status);
CREATE INDEX idx_fs_user_lasttx  ON funding_sources(user_id, last_tx_at DESC);
CREATE INDEX idx_fs_user_display ON funding_sources(user_id, display_id);  -- non-unique lookup cho /reports filter

-- ═══════════════════════════════════════════════════════
-- transactions — bổ sung FK
-- ═══════════════════════════════════════════════════════
ALTER TABLE transactions
    ADD COLUMN funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL;

CREATE INDEX idx_tx_user_fs ON transactions(user_id, funding_source_id);
```

**Status state machine:**

```
                  (auto: tx mới về cho TK archived)
       ┌─────────────────────────────────────────┐
       ▼                                         │
   ┌────────┐  user "🚫 Ẩn"  ┌─────────┐         │
   │ active │ ────────────→ │ hidden  │         │
   │        │ ←──────────── │         │         │
   └────────┘  user unhide  └─────────┘         │
       │  (manual unarchive               (auto-resurrect)
       │   only — out of MVP)                    │
       │                                         │
       │   cron: last_tx_at < NOW() - 180d       │
       └────────────────→  ┌──────────┐  ───────┘
                           │ archived │
                           │ archived_at = NOW() │
                           └──────────┘
```

- `active` ↔ `hidden`: user-driven, intentional, KHÔNG auto-flip.
- `active` → `archived`: cron, dormancy-based.
- `archived` → `active`: auto khi tx mới về (resurrect + notify).
- `hidden` → `active`: chỉ qua manual unhide trong /accounts (out of MVP, ghi backlog).

**Quan hệ:**

```
users 1 ─── n funding_sources 1 ─── n transactions
                              │
                              └── (display_id mirrors col P "bank_account" trong giai đoạn Sheets)
```

**Trong giai đoạn Sheets (hôm nay, trước khi migrate sang Postgres):** `funding_sources` được simulate bằng worksheet riêng (sheet name `FUNDING_SOURCES`) với các column tương đương — xem `feature-funding-sources-tech.md` §2.

---

## 5. API Endpoints

Không có HTTP endpoint công khai cho user. Mọi interaction qua bot command. Chỉ list internal callback patterns:

| Trigger | Callback / Command | Mô tả |
|---------|--------------------|------|
| Command | `/accounts` | List view |
| Command | `/banks` | Legacy alias — gọi same handler, render với category breakdown |
| Command | `/reports account=<display_id>` | Filter — xem §5.1 ambiguity resolution |
| Command | `/reports account=<kind>:<display_id>` | Power-user syntax, không hỏi disambiguation |
| Callback | `acc_rename` | Bước 1 rename flow |
| Callback | `acc_rename_{id}` | Chọn TK cần rename |
| Callback | `acc_hide` / `acc_hide_{id}` | Hide flow |
| Callback | `acc_add` / `acc_add_bank_{bank}` / `acc_add_kind_{kind}` | Manual add flow |
| Callback | `acc_view_{id}` | Drill into 1 funding source (sau này — out of MVP) |

Admin-side endpoint (audit):

| Method | Path | Mô tả |
|--------|------|------|
| GET | `/admin/users/{user_id}/funding-sources` | Read-only list (qua admin tools F-admin) |

### 5.1. Filter syntax cho `/reports account=…`

Internal mọi nơi dùng `funding_source_id` (int). User-facing parser resolve qua 3 tier:

| Input form | Resolution |
|-----------|------------|
| `account=TCB-1234` (display_id only) | SELECT WHERE user_id=$1 AND display_id='TCB-1234' AND status IN ('active', 'hidden'). **0 row** → "⚠️ Không tìm thấy TK `TCB-1234`." **1 row** → filter ngay. **≥2 row** → bot list inline buttons cho user chọn, mỗi button gắn `funding_source_id` để callback dispatch chính xác. |
| `account=credit_card:TCB-1234` (kind:display_id) | SELECT WHERE user_id=$1 AND kind='credit_card' AND display_id='TCB-1234' AND status IN ('active', 'hidden'). Bỏ qua disambiguation — power-user syntax. |
| `account=fs_42` (internal id, optional) | SELECT WHERE id=42 AND user_id=$1. Dùng cho callback từ disambiguation step trên — KHÔNG document cho user. |
| `account=nickname:"Lương chính"` | SELECT WHERE nickname='Lương chính'. Fallback nếu user thích đặt tên hơn nhớ display_id. Quoted nếu có dấu space. |

> **Hidden behavior (Option A — explicit lookup):** khi user gõ `account=TCB-1234` direct, đó được coi là **explicit intent**. Bot match cả `status='active'` và `status='hidden'` (nhưng KHÔNG match `status='archived'` — archived = cold storage, cần unhide manual nếu muốn xem). Lý do: nếu user biết tên cụ thể, họ đang chủ ý query — list view default ẩn hidden nhưng explicit không.
>
> Counter-example để hiểu Option A: `/accounts` default list **EXCLUDE** hidden. `/accounts --include-hidden` mới show. Khác biệt: list = passive browse, filter = active query.

Ambiguity disambiguation UI (Telegram inline buttons):

```
Có 2 tài khoản match `TCB-1234`:
[1️⃣ TCB-1234 · TK ngân hàng (Lương chính)]
[2️⃣ TCB-1234 · Thẻ tín dụng]      🚫 đã ẩn
[❌ Huỷ]
```

Tap → set callback data `report_filter_fs_{id}`, bot rerun /reports với resolved id. Buttons có `status='hidden'` được đánh dấu 🚫 để user phân biệt.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| — | `FS_NEW_DETECTED` | "📥 Phát hiện tài khoản mới…" (embedded vào picker) | Tx đầu tiên match funding_source mới |
| — | `FS_RESURRECTED` | "📥 TK X đã có tx mới — đã bật lại." (delayed 1.5s sau picker) | Tx về TK đang `status='archived'` |
| — | `FS_RENAME_INVALID` | "❌ Tên tối đa 32 ký tự." | Nickname > 32 ký tự hoặc rỗng sau strip |
| — | `FS_DUPLICATE_MANUAL` | "⚠️ TK này đã có rồi: `TCB-9999` (Thẻ tín dụng)." | Manual add trùng `(kind, bank, last4)`. Hiển thị kèm kind để user phân biệt với entry cùng display_id khác kind. |
| — | `FS_NOT_FOUND` | "⚠️ Không tìm thấy TK đó." | callback có id lạ hoặc lookup không match |
| — | `FS_FILTER_AMBIGUOUS` | "Có N tài khoản match…" | `/reports account=<display_id>` match ≥2 funding sources, prompt user chọn |
| — | `FS_LIMIT_REACHED` | _(không có — không cap MVP)_ | — |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `fs_discovered` | Insert funding_source mới qua auto-discovery | `user_id`, `kind`, `bank`, `had_last4` (bool) |
| `fs_renamed` | User set nickname | `user_id`, `funding_source_id`, `name_length` |
| `fs_hidden` | User set `status='hidden'` | `user_id`, `funding_source_id`, `tx_count_lifetime` |
| `fs_archived` | Cron set `status='archived'` | `user_id`, `funding_source_id`, `days_silent` |
| `fs_resurrected` | Tx về TK đang archive | `user_id`, `funding_source_id`, `days_silent` |
| `fs_manually_added` | User thêm tay | `user_id`, `kind`, `bank`, `had_last4` (bool) |
| `fs_report_filtered` | User gọi `/reports account=X` | `user_id`, `funding_source_id` |

(Theo TDD §2.1 events bảng `analytics_events`.)

---

## 8. State Machine

Auto-discovery & gắn FK lên tx là pipeline thuần, không state. Chỉ có state cho 2 conversation flows:

**Rename flow:**
```
idle ──[/accounts → ✏️ Đổi tên]──→ await_rename_pick_fs
        ──[chọn TK]──→ await_rename_input
            ──[gõ tên hợp lệ]──→ idle  (✅ saved)
            ──[gõ tên >32 ký tự / rỗng]──→ stay await_rename_input
            ──[/cancel]──→ idle
            ──[timeout 5min]──→ idle (state expired)
```

**Manual add flow:**
```
idle ──[/accounts → ➕ Thêm]──→ await_add_bank
        ──[chọn bank]──→ await_add_last4
            ──[input match ^\d{4}$ hoặc "skip"]──→ await_add_kind
            ──[input invalid]──→ stay await_add_last4  (error msg)
                ──[chọn kind]──→ await_add_nickname
                    ──[nickname 1-32 ký tự]──→ idle  (✅ saved)
                    ──[nickname "skip"]──→ idle  (saved, nickname=NULL)
                    ──[invalid: rỗng/>32]──→ stay await_add_nickname
            ──[/cancel hoặc timeout 5min ở bất kỳ step]──→ idle
```

**Lưu vào** `bot_state`:
- `step = 'await_rename_pick_fs' | 'await_rename_input' | 'await_add_bank' | 'await_add_last4' | 'await_add_kind' | 'await_add_nickname'`
- `payload`: `{funding_source_id?, bank?, last4?, kind?}`

### Timeout Spec

| Variant | Timeout | Behavior |
|---------|---------|---------|
| Conversation states (rename / add) | 5 phút idle | Reset state, không gửi message |
| Auto-discovery notification cooldown | 1 lần / funding_source / lifetime | Đã ping rồi không ping lại dù user chưa rename |
| Archive trigger (auto) | 180 ngày silent (`last_tx_at < NOW() - 180d`) | Set `status='archived'` + `archived_at=NOW()`, không notify. KHÔNG áp dụng cho rows `status='hidden'`. |

---

## 9. Caching Strategy

- **Per-user funding_source map** (`{(kind, bank, last4) → funding_source_id}`): cache 5 phút LRU, max 1000 entries. Key theo canonical identity (NOT display_id) để cùng `TCB-1234` debit vs credit không collide trong cache. Invalidate on INSERT/UPDATE status/DELETE.
- **`/accounts` list:** không cache — list ngắn, query rẻ (≤ ~20 rows/user typical).
- **`/banks` aggregation:** đi qua cache có sẵn của `get_bank_breakdown(month_key)` trong `sheets.py`.

---

## 10. Acceptance Criteria

**Identity & uniqueness:**
- [ ] Canonical identity = `(user_id, kind, bank, last4)` — unique constraint enforce ở DB level
- [ ] `last4 = ''` (empty string) khi không có số cuối — KHÔNG dùng NULL (tránh Postgres NULL-comparison trap với UNIQUE)
- [ ] Cùng `display_id="TCB-1234"` tồn tại 2 entry nếu khác `kind` (vd debit + credit) — không conflict
- [ ] UPSERT `ON CONFLICT (user_id, kind, bank, last4) DO UPDATE` — target khớp unique constraint chính xác

**Discovery flow:**
- [ ] Tx đầu tiên của funding_source mới: auto-INSERT + embed header "📥 Phát hiện TK mới" trong category picker (1 message)
- [ ] Tx tiếp theo của funding_source đã có: update `last_tx_at`, không re-notify
- [ ] Discovery failure (DB lỗi): silent fallback — tx vẫn lưu với `funding_source_id=NULL`, column P giữ string compat
- [ ] **F02 integration:** funding_source resolve trước hoặc cùng transaction với tx INSERT — xem [feature-transaction-capture.md §10](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-transaction-capture.md)

**Status state machine:**
- [ ] `status='active'` mặc định
- [ ] User "🚫 Ẩn" → `status='hidden'`, ẩn khỏi default report
- [ ] Cron 180-day silence → `status='archived'`, set `archived_at=NOW()`
- [ ] Tx về TK `status='archived'`: resurrect → `status='active'`, `archived_at=NULL`, notify 1 lần (delayed 1.5s)
- [ ] Tx về TK `status='hidden'`: KHÔNG resurrect, KHÔNG notify, tx vẫn gắn FK
- [ ] `archived_at` NOT NULL khi và chỉ khi `status='archived'` (check constraint)

**Rename + manual add:**
- [ ] Rename: nickname 1-32 ký tự sau strip, reject rỗng/quá dài, save sau khi pass validate
- [ ] Manual add: tạo funding_source với kind user chọn, last4 optional (default '')
- [ ] Manual add `last4` validation: regex `^\d{4}$` HOẶC literal "skip" (case-insensitive); reject + stay state nếu invalid
- [ ] Manual add duplicate check theo `(kind, bank, last4)` — cùng display_id khác kind = OK; cùng identity = reject `FS_DUPLICATE_MANUAL`

**Inference:**
- [ ] Email subject chứa "thẻ tín dụng"/"credit card"/"sao kê thẻ" → `kind=credit_card`
- [ ] Gateway ∈ {MoMo, ZaloPay, ViettelPay, ShopeePay} → `kind=e_wallet`
- [ ] Default → `kind=bank_account`

**Filter & reports:**
- [ ] `/reports account=<display_id>` 1 match → filter; ≥2 match → disambiguation prompt; 0 match → `FS_NOT_FOUND`
- [ ] `/reports account=<kind>:<display_id>` bypass disambiguation
- [ ] Disambiguation callback dùng `funding_source_id` để filter
- [ ] `/banks` legacy alias vẫn hoạt động, render nickname nếu có

**Migration & misc:**
- [ ] Backfill: legacy tx có column P string → script tạo funding_source + gán FK
- [ ] Cache invalidate sau hide / status flip
- [ ] Analytics events fire đủ 7 loại (`fs_discovered`, `fs_renamed`, `fs_hidden`, `fs_archived`, `fs_resurrected`, `fs_manually_added`, `fs_report_filtered`)
- [ ] State timeout 5 phút clear bot_state
- [ ] Không cap số lượng funding_sources cho Free tier
- [ ] Privacy: tuân [TDD §6.3](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md). F08 enforce 2 FK rule: (a) `users → funding_sources` `ON DELETE CASCADE`, (b) `transactions.funding_source_id → funding_sources` `ON DELETE SET NULL`. Retention / xoá / anonymize của `transactions` (qua `users.id`) do TDD quyết, F08 không decide. Soft delete user: chỉ set `users.deleted_at`, không CASCADE.

---

## 11. Open Questions

1. **Display order trong /accounts:** hiện đề xuất sort theo `last_tx_at desc`. Có nên ưu tiên nickname-đã-đặt lên trước? → đợi feedback từ Minh/Linh/Hùng beta.
2. **Per-account budget:** out of scope F08. Category-level allocation (F03/F04) đã đủ cho MVP. Nếu user muốn "cap chi card tín dụng 5tr/tháng", cân nhắc thêm ở F08.1.
3. **Multi-channel ownership:** nếu user link bot Telegram + Discord cùng SePay token, funding_sources thuộc user_id nào? → Theo F-saas-refactor: 1 user_id duy nhất, channels share. Không có vấn đề. Confirm khi triển khai.

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-11 | Initial spec — VN-only, single `funding_sources` entity với canonical identity `(user_id, kind, bank, last4)`, status enum (active/hidden/archived), auto-discovery embed-in-picker UX, FK chain `users→fs` CASCADE + `tx.fs_id→fs` SET NULL. Locked sau nhiều round in-session review. |
