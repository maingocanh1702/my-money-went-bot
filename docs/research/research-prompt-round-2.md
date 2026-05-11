# Research Prompt Vòng 2 — Apps Tương Tự My Money Went (Deep-dive + Visual Format)

> **Mục đích:** Bổ sung gap từ vòng 1 (Money Lover, Spendee không deep, Money Manager Realbyte, 1Money, HomeBudget bị skip) + khoanh vùng chính xác các app **THẬT SỰ TƯƠNG TỰ** My Money Went để extract pattern.
>
> **Scope:** Global market, USD pricing, không VN context.
>
> **Output yêu cầu:** Cấu trúc visual với app cards + master comparison tables — dễ scan, dễ so sánh side-by-side, không phải paragraph dài.

---

## CONTEXT VỀ MY MONEY WENT (cho researcher)

| Aspect | Detail |
|---|---|
| **Type** | Telegram bot tự động capture giao dịch (bank webhook + email parsing) |
| **Input method** | Bank webhook (SePay-equivalent) + email parsing + manual fallback. KHÔNG cần share bank credentials. |
| **UX surface** | 100% trong messaging app. No standalone mobile app. Optional read-only web dashboard. |
| **Pricing (USD)** | Free (45 tx/mo) / Pro $4/mo / Business $9/mo |
| **Primary ICP** | Solopreneur — bán online (Shopify/Etsy/TikTok Shop) cần tách Personal vs Business P&L |
| **Differentiators** | (1) Lives in chat, (2) No bank credentials, (3) Personal+Business split <$10/mo, (4) Email parsing |

**"Tương tự" được định nghĩa = match ≥2 trong 5 attributes:**
1. Messaging/chatbot UX (Telegram, WhatsApp, Discord, Messenger, SMS-bot)
2. Auto-capture qua non-Plaid method (email parsing, SMS parsing, webhook, browser extension)
3. Pricing entry tier ≤ $5/mo
4. Personal + Business P&L split feature
5. Multi-currency support 5+ currencies

---

## PROMPT (copy phần dưới)

```
Bạn là chuyên gia phân tích cạnh tranh fintech. Đây là research VÒNG 2 nối tiếp vòng 1 đã hoàn thành. Vòng 1 đã cover YNAB, Monarch, Copilot, Rocket Money, PocketGuard, Cleo, QuickBooks Solopreneur, etc.

Vòng 2 focus vào các app TƯƠNG TỰ My Money Went mà vòng 1 đã miss hoặc cover sơ sài. "Tương tự" = match ≥2 trong 5 tiêu chí:
(a) Messaging/chatbot UX (Telegram, WhatsApp, Discord, Messenger, SMS bot)
(b) Auto-capture không qua Plaid (email parsing, SMS parsing, browser extension, webhook)
(c) Entry pricing ≤ $5/mo
(d) Personal + Business split
(e) Multi-currency 5+

QUAN TRỌNG — RULES:
- Global market only, USD pricing only
- Verify từng pricing claim qua URL official; nếu không verify được, ghi rõ "[unverified]"
- Quote 1-2 user review từ Reddit/App Store với link nguồn
- Output BẰNG TIẾNG VIỆT nhưng giữ tên feature/tier nguyên tiếng Anh
- Ưu tiên data 2025-2026

═══════════════════════════════════════════════════════
SECTION A — APP LIST (15 apps, chia 4 cluster)
═══════════════════════════════════════════════════════

CLUSTER 1: Generic-name apps có global reach (vòng 1 miss/skip)
1. Money Lover (Finsify) — https://moneylover.me  ⭐ priority cao
2. Spendee — https://spendee.com  ⭐ priority cao (vòng 1 sơ sài)
3. Money Manager (Realbyte) — Korean dev, global Android dominance
4. 1Money — clean minimal expense tracker
5. HomeBudget with Sync — multi-device family budget
6. Fast Budget — Android-popular budget app

CLUSTER 2: Messaging-first / Chatbot finance (priority cực cao)
7. PiggyPal (Telegram bot) — https://t.me/PiggyPalBot — most polished Telegram finance bot
8. TeleExpense (Telegram bot) — Google Sheets backend, $1 one-time
9. Budget Easy Bot (Telegram) — Google Sheets integration
10. Cointry (Telegram) — group chat budgeting
11. Bất kỳ WhatsApp/Discord finance bot nào active 2025-2026 (search hard)

CLUSTER 3: Email/SMS parsing apps (closest tech analog)
12. Walnut (đã shutdown — research lessons) — was SMS-parsing pioneer in India
13. Money View — SMS parsing + lending (India market, global lessons)
14. Buddy — UK email + bank link
15. Bất kỳ app nào có "email forwarding" hoặc "SMS parsing" feature

CLUSTER 4: Solopreneur lite (gần $9 Business tier)
16. Bonsai (formerly Hello Bonsai) — freelancer all-in-one
17. Indy — freelancer suite Pháp/global
18. Notion + Tally/Airtable templates phổ biến cho solopreneur
19. Subly / Snapsheet — solopreneur expense lite tools

═══════════════════════════════════════════════════════
SECTION B — OUTPUT FORMAT (BẮT BUỘC THEO TEMPLATE)
═══════════════════════════════════════════════════════

Output structure CỐ ĐỊNH 4 phần:

PHẦN 1: MASTER COMPARISON TABLE (overview tất cả app)
PHẦN 2: APP CARDS (1 card/app — visual format dưới)
PHẦN 3: SIMILARITY SCORE TABLE (rank theo độ giống MMW)
PHẦN 4: PATTERN INSIGHTS (rút ra từ analysis)

─────────────────────────────────────────────
TEMPLATE PHẦN 1 — MASTER COMPARISON TABLE
─────────────────────────────────────────────

| # | App | Platform | Entry Price (USD/mo) | Free Tier? | Auto-capture Method | Personal+Biz Split | Multi-currency | Users (M) | Rating |
|---|-----|----------|---------------------:|------------|---------------------|--------------------|----------------|-----------|--------|
| 1 | Money Lover | iOS/And/Web | $X.XX | ✅/❌ | Plaid/email/SMS/manual | ✅/❌ | XX currencies | X.X | X.X★ |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

Tất cả 15-19 app phải lên bảng. Cell unverified → "[?]".

─────────────────────────────────────────────
TEMPLATE PHẦN 2 — APP CARD (mỗi app 1 card)
─────────────────────────────────────────────

╔══════════════════════════════════════════════════════════╗
║  📱 APP NAME — One-line positioning                      ║
╠══════════════════════════════════════════════════════════╣
║  💰 From $X.XX/mo   |   👥 X.XM users   |   ⭐ 4.X (iOS)  ║
║  🌍 Markets: US/EU/UK/global   |   🏢 HQ: Country         ║
╚══════════════════════════════════════════════════════════╝

📋 PRICING TABLE
| Tier | Monthly | Annual | $/mo Equiv | Discount | Note |
|------|--------:|-------:|-----------:|---------:|------|
| Free | $0 | — | — | — | Limits: ... |
| Tier 1 | $X | $XX | $X | XX% | ... |
| Tier 2 | $X | $XX | $X | XX% | ... |

⚙️ HOW IT WORKS (3-row max)
| Aspect | Detail |
|---|---|
| Onboarding | X min, X bước, có/không cần bank link |
| Auto-capture | Plaid / email / SMS / OCR / manual / webhook |
| Categorization | Manual / rule-based / ML / AI |

✅ STRENGTHS (bullet 3 dòng max)
• ...
• ...
• ...

❌ WEAKNESSES (bullet 3 dòng max — gap MMW có thể exploit)
• ...
• ...
• ...

💬 USER VOICE (1-2 quote, có link nguồn)
> "Quote ngắn 1-2 dòng" — r/personalfinance [URL]
> "Quote 2" — App Store review [URL]

🎯 TARGET USER
Mass consumer / power user / freelancer / solopreneur / SMB

🔗 SIMILARITY TO MMW: ⭐⭐⭐⭐☆ (X/5)
Match attributes: [list 2-5 trong: chat-UX / non-Plaid auto / cheap-pricing / personal-biz-split / multi-currency]

💡 KEY TAKEAWAY (1 dòng — học gì từ app này?)
...

─────────────────────────────────────────────
TEMPLATE PHẦN 3 — SIMILARITY SCORE TABLE
─────────────────────────────────────────────

Rank tất cả app theo độ giống MMW (5 attributes match):

| Rank | App | Chat UX | Non-Plaid | ≤$5/mo | P+B Split | Multi-curr | Total Score |
|-----:|-----|:-------:|:---------:|:------:|:---------:|:----------:|:-----------:|
| 1 | App tên | ✅ | ✅ | ✅ | ❌ | ✅ | 4/5 |
| 2 | ... | ... | ... | ... | ... | ... | X/5 |

Top 3 most-similar = mối đe dọa direct nhất → cần monitor sát.

─────────────────────────────────────────────
TEMPLATE PHẦN 4 — PATTERN INSIGHTS
─────────────────────────────────────────────

Trả lời 6 câu hỏi này theo format ngắn gọn:

Q1: Trong các app messaging-first (Cluster 2), app nào có dấu hiệu retention >20% MAU?
A: ...

Q2: Có app nào ngoài MMW làm email parsing transaction commercial-grade không?
A: ...

Q3: Money Lover Linked Wallet (paid tier) thực sự cover bao nhiêu banks ở US/EU/AU? Plaid hay aggregator khác?
A: ...

Q4: Spendee free tier có thực sự "free forever unlimited" hay có hidden cap?
A: ...

Q5: Trong các app entry tier ≤$5/mo, ai có conversion Free→Paid >5%?
A: ...

Q6: Có dấu hiệu nào cho thấy users đang migrate TỪ Money Lover/Spendee đi đâu khác?
A: ...

═══════════════════════════════════════════════════════
SECTION C — DELIVERY CHECKLIST
═══════════════════════════════════════════════════════

Output cuối phải có:
[ ] Master comparison table (Phần 1) — tất cả 15-19 app trên 1 bảng
[ ] App cards (Phần 2) — 1 card/app, format y nguyên template
[ ] Similarity score table (Phần 3) — rank ranking
[ ] Pattern insights (Phần 4) — 6 Q&A
[ ] Source list cuối file — tất cả URL đã verify

KHÔNG cần:
- Executive summary dài (đã có vòng 1)
- Pricing recommendation (đã có vòng 1)
- GTM playbook (đã có vòng 1)
- Detailed personas (đã có)

CHỈ cần data mới + visual format dễ scan.
```

---

## TẠI SAO FORMAT NÀY DỄ NHÌN HƠN VÒNG 1

| Vòng 1 (paragraph format) | Vòng 2 (card + table format) |
|---|---|
| Đọc tuần tự, mỗi app 30-60 dòng paragraph | Scan ngang, mỗi app gói gọn 1 card |
| So sánh phải scroll qua lại | Master table 1 trang so sánh tức thì |
| Pricing chôn trong text | Pricing table riêng, $/mo equiv columns |
| Khó pick "đối thủ giống nhất" | Similarity score column rank thẳng |
| Strengths/weaknesses dài dòng | Bullet 3-row max, force focus |

---

## SUGGESTED PRIORITY ORDER NẾU CHẠY TỪNG PHẦN

Nếu researcher trả không hết trong 1 lần, chạy theo thứ tự:

1. **Cluster 2 (Telegram/messaging bots)** — closest analog, learn nhiều nhất
2. **Cluster 1 + Money Lover + Spendee** — fill gap vòng 1
3. **Cluster 3 (email/SMS parsing)** — học moat email parsing
4. **Cluster 4 (solopreneur lite)** — adjacent benchmarks

---

## TIPS CHẠY PROMPT

1. **Verify Money Lover pricing bằng tay** — họ có nhiều regional pricing, screenshot pricing page UK/US/AU.
2. **Telegram bots khó research bằng web search** — researcher phải mở chính bot trong Telegram để xem `/help`, `/pricing`. Nếu LLM không làm được, ghi rõ "[need manual verification]".
3. **Similarity score** = quan trọng nhất → đây là input cho threat assessment.
4. **App Cards** có thể export ra Notion/Airtable sau cùng để tracking continuous.

[Mở prompt vòng 2](computer:///Users/maingocanh/Projects/MyMoneyWent/research-prompt-round-2.md)
