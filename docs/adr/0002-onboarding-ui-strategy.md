# Decision — Onboarding UI Strategy: Chat-only vs Web Form

> **Version:** v1.0.1
> **Ngày tạo:** 2026-05-07
> **Cập nhật lần cuối:** 2026-05-07
> **Trạng thái:** Decided
> **Decision:** Chat-only cho MVP. Web đóng vai trò khác (landing + privacy/terms pre-launch, dashboard post-launch) — KHÔNG dùng web cho onboarding form.
> **Owner:** Founder
> **Tham chiếu:** [BRD-vi v3.1.0 §2.2 mục tiêu](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.7.1 §2.1–2.3 onboarding flows](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [Feature Spec Messenger v1.1.1 §7](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)

---

## 1. Question

User onboarding flow trong MVP nên build:

- **Option A:** Web form/wizard cho user nhập thông tin setup, sau đó bridge sang Telegram/Messenger bot
- **Option B:** Chat-only — toàn bộ onboarding trong Telegram/Messenger UI, không có web form

Đây là quyết định affect: cost dev, conversion funnel, infrastructure, maintenance burden, time-to-launch.

---

## 2. Decision (TL;DR)

**Chat-only cho MVP.** Reasoning chính: không có user input text nhiều field nào trong scope MVP cần form web — toàn bộ "input" là button click + scan QR + setup forwarding rule (external action). Web form sẽ tạo step thừa mà không add UX value.

**Web đóng vai trò khác** trong roadmap (KHÔNG phải onboarding form):

| Use case | When | Effort |
|---|---|---|
| Landing page tĩnh (marketing + CTA tới bot) | Pre-launch Phase 7 | ~1–2 ngày |
| Privacy policy + Terms (required Meta App Review) | Pre-launch Phase 6 cuối | ~1 ngày |
| Dashboard + reports (read-only) | Post-launch khi user >100, có ≥3 tháng data | Defer Phase 9+ |
| Billing/plan management (invoice download) | Post-launch khi recurring annual phổ biến | Defer Phase 9+ |
| Admin internal tool UI | Optional sau MVP | Defer; chat /admin commands đủ cho 0–500 user |

---

## 3. Phân tích — User input thực sự cần collect là gì?

Đây là câu hỏi gốc. Nhìn vào architect 3-path onboarding hiện tại để map mỗi step → loại input:

| Step | User input | Form web ưu thế? |
|---|---|---|
| `/start` (Telegram) hoặc Get Started postback (Messenger) | Không — `telegram_id`/PSID lấy auto từ event | ❌ |
| Chọn path A/B/C | 1 button click (3 lựa chọn) | ❌ button trong chat tốt hơn |
| Path A — SePay quick connect | Bot **xuất** webhook URL (user paste vào sepay.vn) | ❌ user nhận output, không nhập gì |
| Path B — SePay setup wizard | 3 acknowledgment "✅ done" buttons step-by-step | ❌ |
| Path C — Email forwarding | Bot **xuất** `u{id}@in.tienvenoidau.com`. User setup forwarding rule trong Gmail/Outlook (external action) | ❌ user nhận output |
| First transaction → categorize | Click category button (lần đầu inline keyboard / quick reply) | ❌ chat đủ |
| Setup new category sau này | Gõ tên ngắn ("Cafe", "Đồ ăn") | ❌ chat thậm chí nhanh hơn form |
| Settings (timezone toggle, daily recap on/off) | 1-2 button toggle | ❌ |
| Upgrade payment | Chọn plan → scan VietQR (không nhập gì) | ❌ |

**Kết luận:** Trong toàn bộ MVP scope, KHÔNG có complex form (>3 fields) hay structured data entry mà form web sẽ ưu thế hơn chat. Mọi "input" là 1 trong 3 dạng:

1. **Button click** (Telegram inline / Messenger quick reply) — chat tốt hơn web button
2. **Bot output** mà user copy hoặc làm gì đó với (URL, email address, ref code) — web không thay thế được, vì user vẫn phải đi sang bank app / Gmail / SePay
3. **External action** (setup Gmail forward, paste vào sepay.vn) — web không liên quan

Web form sẽ tạo "form trống cho mọi người điền" mà không có gì cần điền trong scope MVP.

---

## 4. Trade-off comparison

### 4.1. Chat-only (current architect)

**Ưu:**

- Single context — không phải app switching ("ấn link → web → quay lại chat")
- Match "thêm bạn → dùng ngay" promise của BRD §2.2 onboarding 2–15 phút
- Zero infrastructure thêm (đã có bot hosting)
- Schema không cần user table extensions cho web auth/sessions
- Native mobile UX — Hùng+ persona dùng mobile chính, không phải desktop
- Telegram link share → click → /start → done. Web break chain này.
- Cross-channel identical flow (Telegram + Messenger song song qua adapter pattern)
- Founder solo dev: lean, ship faster

**Nhược:**

- Long form copy-paste khó trên mobile (nhưng không có long form trong scope)
- Settings dropdown nghèo hơn (vd timezone picker — nhưng default `Asia/Ho_Chi_Minh` cover 95% case)
- Không show rich media trong onboarding (vd video tutorial — defer Path B wizard nếu cần show)

### 4.2. Web-based onboarding form

**Ưu:**

- Rich UI cho complex form (nhưng MVP không có)
- Save-and-resume progress (nhưng onboarding 5–15 phút, ai cũng làm 1 lần)
- A/B test flow tracking dễ hơn (Posthog/GA standard tooling)
- Marketing landing kết hợp onboarding entry (SEO synergy)
- Foundation cho dashboard sau (reports/billing đặt lên cùng web app)

**Nhược:**

- **Bridge problem nghiêm trọng** — user signup trên web → cần link tới Telegram/Messenger account của họ. 3 cách:
    - Deep link `t.me/FinTrackBot?start=<token>` → user phải click đúng → thêm 1 step + token expiry edge case
    - Magic link email → cần email collection trước → thêm friction + Messenger user không có email
    - OAuth Telegram Login → setup phức tạp founder, user lạ với UX này ở VN
- **Conversion drop:** mỗi step = 10–30% drop. Chat-only 2 step (search bot + /start). Web = 5+ step (visit web + read + form + verify + back to chat).
- Infrastructure cost: hosting ($5–10/mo Vercel/Netlify free tier OK ban đầu) + dev time
- Mobile responsive design effort
- Auth, sessions, cookie consent — phải làm cho compliance (PDPA + Meta privacy requirements)
- Privacy policy phức tạp hơn (web cookies + tracking)
- 2x maintenance burden cho founder solo (web app + bot)

### 4.3. Hybrid (chat onboarding + web for advanced)

Pattern phổ biến ở SaaS bot mature (Linear, Notion, Stripe Atlas):
- Quick onboarding trong chat
- Web dashboard cho power user features (reports, billing history)

**Đánh giá:** Đúng pattern roadmap dài hạn — nhưng MVP chưa cần web phần advanced (vì user chưa có ≥3 tháng data để xem report; chưa có recurring annual để cần invoice; admin commands chat đủ). **Hybrid sẽ thành reality post-launch tự nhiên**, không phải decision pre-MVP.

---

## 5. Recommendation chi tiết

### 5.1. MVP (Phase 1–8)

**Chat-only onboarding theo kiến trúc hiện tại** (PRD §2.1–2.3 + Messenger spec §7). KHÔNG thêm web.

Lý do thực tế:
1. Persona target (Hùng+ shop online, Minh/Linh dev) sống trong chat app — không có lý do force họ rời chat
2. Không có user input phức tạp trong scope MVP
3. Founder solo, ưu tiên ship — web = +2–3 tuần dev + ongoing maintenance
4. CAC tăng nếu user phải click 2 link thay vì 1
5. Bridge flow web ↔ chat = thêm fail point (token expiry, account mismatch)

### 5.2. Pre-launch web (Phase 6/7) — vai trò khác

| Item | Path | Effort | Required for |
|---|---|---|---|
| Landing page tĩnh | `https://tienvenoidau.com/` | ~1–2 ngày | Marketing entry funnel + Meta App Review (Page có URL website) |
| Privacy policy | `https://tienvenoidau.com/privacy` | ~0.5 ngày | Meta App Review require + PDPA Vietnam compliance |
| Terms of service | `https://tienvenoidau.com/terms` | ~0.5 ngày | Meta App Review require |

Tổng ~3 ngày dev. Có thể parallel với Phase 6 dev hoặc absorb vào Phase 7 buffer.

**Landing page minimum content:**

- Hero section: "Tự động track chi tiêu qua bank transfer — 2-15 phút setup, không cần card"
- 3-path mô tả ngắn (SePay quick / SePay wizard / Email forwarding) với time estimate
- 2 CTA buttons:
    - "Bắt đầu trên Telegram" → `t.me/FinTrackBot?start=landing_telegram`
    - "Bắt đầu trên Messenger" → `m.me/FinTrackPage?ref=landing_messenger` (chỉ live khi `ENABLE_MESSENGER_CHANNEL=true`)
- Pricing table (Free / Pro $4 / Business $9)
- Privacy policy + Terms link (footer)
- Optional: 1 phút demo video (Phase 8 polish)
- Vietnamese primary, English secondary

**Tech stack đề xuất (giữ lean):**

- Static site generator: Astro hoặc Next.js static export
- Hosting: Vercel hoặc Cloudflare Pages (free tier)
- Domain: `tienvenoidau.com` (đã setup từ Phase 6 deploy)
- KHÔNG cần backend, KHÔNG cần auth, KHÔNG cần database

**Tracking:**

- Plausible.io hoặc Cloudflare Analytics (privacy-friendly, free tier)
- UTM params trên CTA để track web → bot conversion

### 5.3. KHÔNG build trong MVP

| Item | Lý do |
|---|---|
| Web signup form | Không có input cần collect |
| Web setup wizard | Bot wizard (Path B) tốt hơn — single context |
| Web account creation flow | Account tạo auto từ /start hoặc Get Started |
| Web settings page | Telegram /settings + persistent menu Messenger đủ |
| Web dashboard / reports | Defer Phase 9+ post-launch |
| Web billing / plan management | Defer Phase 9+ |
| Web admin tool UI | Defer optional; chat /admin commands đủ cho 0–500 user |

---

## 6. Triggers để revisit decision

Build dashboard / web onboarding khi nào? Watch các signal sau (post-launch):

| Signal | Threshold | Action |
|---|---|---|
| User feedback "khó setup trên mobile" | >30% support ticket có theme này | Investigate specific friction, có thể chỉ cần improve copy chứ không cần web |
| Conversion drop-off Path B (SePay wizard) | >50% drop sau step 1 | Consider web wizard cho path B (Path A + C giữ chat) |
| MRR sustained >$300/mo | 2 tháng liên tiếp | Budget có thể justify dashboard cho retention |
| Pro/Business user feedback | "muốn xem report trên màn hình to" | Build read-only dashboard riêng (KHÔNG phải onboarding form) |
| Annual subscriber >20 user | — | Build invoice download page |
| Admin chat commands quá overload | Founder dành >2h/tuần | Internal admin tool UI |

**Nguyên tắc:** Mỗi web feature add khi có signal CỤ THỂ + measure được, không phải "có thể user sẽ thích".

---

## 7. Risks & mitigation

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Build web onboarding ngay khi không cần | — | Conversion giảm 20–40% (extra step), MVP delay 1–2 tuần, +maintenance burden | **Avoid bằng decision này** — chat-only MVP |
| 2 | Chat-only mãi mãi → Pro/Business user frustrated khi muốn xem report screen lớn | Trung bình post-launch | Churn Pro/Business segment | §6 trigger watch + build dashboard read-only khi MRR justify |
| 3 | User mobile thực sự khó copy-paste webhook URL trong Path A | Trung bình | Path A drop-off | Mitigate trong chat: gửi URL như standalone message (long-press copy easier on Messenger), thêm "tap để copy" button trên Telegram |
| 4 | Meta App Review reject vì Privacy Policy URL không có | Cao nếu skip | Block Messenger launch | Build privacy/terms ở §5.2 — required item, không skip |
| 5 | Marketing không có landing page → SEO/ads convert tệ | Trung bình | Slow growth | Build landing §5.2 — required item |

Risk #1 (build sớm) rủi ro hơn risk #2 (defer) cho founder solo + early stage. Defer reversible (build sau khi có signal); build sớm khó undo (sunk cost).

---

## 8. Implementation — Pre-launch landing page tasks

Nếu approved, đây là task list cụ thể cho ~3 ngày dev trong Phase 6/7:

### Day 1 — Setup + landing page

- [ ] Init repo `fintrack-landing` (separate khỏi bot repo)
- [ ] Setup Astro hoặc Next.js static + Tailwind
- [ ] Design hero + 3-path section + pricing table (mobile-first)
- [ ] Copy: Vietnamese primary
- [ ] CTA buttons với UTM params
- [ ] Footer với link privacy/terms
- [ ] Cloudflare Pages deploy + custom domain setup
- [ ] Plausible/Cloudflare Analytics setup

### Day 2 — Privacy + Terms

- [ ] Privacy policy page (Vietnamese) cover:
    - Data collected: PSID/telegram_id, transaction data (amount, description, ref code, timestamp), message content trong chat, Page interaction events (Messenger)
    - **NOT collected:** số tài khoản ngân hàng, tên chủ tài khoản, OTP, password, biometric (xem TDD §6.2 data minimization)
    - Purpose: transaction tracking + auto-categorization + monthly reports + subscription management
    - **Retention (canonical, sync với TDD §6.3 + Messenger spec §6.7):** Free user inactive ≥90 ngày → archive data (không xóa hẳn). Pro/Business user: data giữ trong suốt plan active, sau khi downgrade về Free thì apply Free policy. User có thể request data export (`/export`) hoặc account deletion bất kỳ lúc nào.
    - Third-party processors (subprocessors): Postmark (email parsing), vietqr.io (QR image), SePay (bank webhook), Railway (hosting), Backblaze B2 (backup) — link policy từng nhà
    - User rights theo PDPA Nghị định 13/2023: data export, account deletion, consent withdrawal, breach notification
    - Meta-specific section cho Messenger users (PSID, Page interactions, MESSAGE_TAG ACCOUNT_UPDATE usage rationale)
    - Contact: founder email cho privacy request + Vietnamese authority contact (TBD)
- [ ] Terms of service page cover:
    - Service description
    - User responsibilities (truthful info, no abuse)
    - Pricing + cancellation
    - Liability limitation
    - Governing law: Vietnam
    - Modification policy

### Day 3 — Polish + verify

- [ ] Test mobile responsive (iPhone SE smallest, iPad largest)
- [ ] Test CTA button → bot deep link work cả Telegram + Messenger (Messenger nếu App Review approved)
- [ ] SEO meta tags (title, description, og:image)
- [ ] Submit privacy policy URL vào Meta App Review payload
- [ ] Update `feature-messenger-channel.md` privacy policy section với URL chính thức
- [ ] Founder review + iterate copy

---

## 9. Open questions

| # | Question | Resolution |
|---|---|---|
| 1 | Landing page tiếng Việt only hay bilingual? | Default Vietnamese primary, English version secondary nếu có capacity. Defer English Phase 9+ |
| 2 | Có nên thu email trên landing để build email list (newsletter)? | Defer post-launch — pre-launch focus conversion sang bot, không phân tâm |
| 3 | Tracking pixel Facebook/Google Ads có cài không? | Defer tới khi có ad budget. Ban đầu chỉ Plausible privacy-friendly đủ |
| 4 | Domain `tienvenoidau.com` đã sẵn chưa? Cost? | Cần verify với founder. Alternative: `fintrack.com.vn` nếu app TLD đắt |
| 5 | Logo/branding guideline cho landing? | Đề xuất hire freelance designer 1-2 ngày tạo logo + 3-4 illustration. Budget ~$50-150 |

---

## 10. References

- [BRD-vi v3.1.0 §2.2 mục tiêu — onboarding 2-15 phút promise](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md)
- [PRD-vi v1.7.1 §2.1–2.3 — 3-path onboarding flow chi tiết](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md)
- [Feature Spec Messenger v1.1.1 §7 — Messenger onboarding flow](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)
- [Feature Spec Messenger v1.1.1 §6.3 — App Review prerequisites (privacy URL required)](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)
- [Feature Spec Messenger v1.1.1 §6.7 — Privacy policy update for Messenger](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md)
- [Cost projection §5.3.4](file:///Users/maingocanh/Projects/MyMoneyWent/docs/strategy/cost-projection.md)

---

## Changelog

| Version | Ngày | Thay đổi |
|---|---|---|
| v1.0.0 | 2026-05-07 | Initial decision doc. Chosen: chat-only onboarding cho MVP. Web đóng vai trò khác (landing + privacy/terms pre-launch ~3 ngày dev, dashboard defer Phase 9+). Lý do chính: không có user input form-shaped trong scope MVP, mọi "input" là button click / scan / external action — web form sẽ tạo step thừa. Triggers để revisit defined ở §6. |
| v1.0.1 | 2026-05-07 | **Retention policy fix** — §8 Day 2 privacy task ghi sai "Free user 30 ngày, Pro/Business indefinite". Sửa thành canonical wording (sync TDD §6.3 + Messenger spec §6.7): "Free user inactive ≥90 ngày → archive data; Pro/Business giữ trong khi plan active, downgrade về Free thì apply Free policy." Thêm explicit data minimization list (NOT collected: account number, OTP, password, biometric). Thêm subprocessors list (Postmark, vietqr.io, SePay, Railway, B2). Thêm PDPA references. |
