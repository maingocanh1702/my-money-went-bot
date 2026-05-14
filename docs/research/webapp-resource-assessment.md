# Đánh giá Resource — Web Dashboard cho Tiền Về Nơi Đâu

> **Version:** v1.2.0
> **Ngày tạo:** 2026-05-13
> **Cập nhật:** 2026-05-13
> **Trạng thái:** Scope locked / implementation deferred
> **Loại tài liệu:** Research & decision note (NOT implementation spec)
> **Tham chiếu:** [BRD-vi v3.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.8.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [Roadmap v1.3.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/mymoneywent-roadmap.md)

---

## 1. Định nghĩa

> **Web dashboard is a read-only companion UI for visualizing existing transaction data. It is not a primary interaction channel and does not replace chat-based workflows. Build after MVP unless user demand strongly validates it.**

Dashboard KHÔNG phải webapp product. Nó là view layer bổ sung cho data đã capture qua bot channels (Telegram/Discord/Messenger).

---

## 2. Scope

### In scope

- Login/link từ bot (magic link hoặc Telegram Login Widget)
- Xem transaction list
- Filter theo ngày / category / funding source
- Category breakdown (monthly summary)
- Monthly trend / basic charts
- Budget progress
- Settings view (read-only hoặc very limited)
- Export CSV (maybe Pro-only later)

### Out of scope

- Manual transaction entry
- Category CRUD
- Onboarding chính (onboarding vẫn qua bot)
- Payment / plan management
- Admin tools
- Replace Telegram/Discord/Messenger
- Full web product architecture

---

## 3. Resource Estimate

### Read-only Dashboard (recommended scope)

| Scope | Effort |
|-------|--------|
| Auth / link bot account | 3-5d |
| Read-only API endpoints | 3-5d |
| Transaction table + filters | 4-6d |
| Basic charts / category summary | 4-6d |
| Responsive dashboard shell | 3-4d |
| Deploy + smoke / security checks | 2-3d |
| **Total** | **19-29 days (~4-6 tuần)** |

---

## 4. Tech Stack

| Layer | Choice | Lý do |
|-------|--------|-------|
| Frontend | Vite + React (hoặc vanilla JS nếu cực lean) | SPA đủ — không cần SSR |
| Styling | Vanilla CSS (CSS variables, design tokens) | Per project rules |
| Charts | Chart.js hoặc Recharts | Lightweight, VN number formatting |
| Auth | Magic link từ bot → JWT session | Không cần password |
| API | FastAPI REST (extend existing) | Thêm read-only routes, reuse query layer |
| Hosting | Vercel free tier hoặc Railway static | SPA, API cùng Railway |

---

## 5. Security: Auth/Link is P1

Auth/linking is the highest-risk part of W-dashboard. Dashboard read-only vẫn có thể leak toàn bộ financial history nếu auth sai. Treat as P1 security-sensitive:

- Magic links single-use — invalidate after first use
- Short TTL (5-10 minutes max)
- Bind to existing user_id — no standalone registration
- Audit link events (dashboard_link_generated, dashboard_link_used, dashboard_link_expired)
- Tenant isolation tests mandatory — zero cross-user data access
- JWT session: short-lived access token + refresh token rotation
- Rate limit magic link generation (max 3/hour per user)

---

## 6. Pricing Impact

Dashboard không thay đổi headline pricing. Nó là value packaging theo tier:

| Tier | Dashboard Entitlement |
|------|----------------------|
| Free | Dashboard basic — last 30 days, transaction table, basic category summary |
| Pro | Full history, charts/trends, CSV export, more filters, multi-bank view |
| Business | P&L style views, source attribution. Scheduled export/report deferred to Phase W2 |

### pricing-tiers Entitlement Integration

Khi implement pricing-tiers Pricing, thêm entitlement cho dashboard — align với generic entitlement model:

WEB_DASHBOARD = {
    access: none|basic|full,
    history_days: 30|None,
    charts: bool,
    export: bool,
    pnl: bool (Business only),
}

---

## 7. Architecture Preparation (Do Now)

Prepare query layer ngay từ bây giờ:

- core/services/transactions_query.py — Shared query logic
- core/services/reports_query.py — Shared report aggregation

Bot dùng để format text message. Future web API dùng cùng query layer để trả JSON.

---

## 8. Roadmap Position

| Phase | Timing | Status |
|-------|--------|--------|
| Core capture/pricing/payment | Phase 1-6 (now → tuần 12) | In progress |
| MVP Launch (bot-only) | Phase 7-8 (tuần 13-16) | Not started |
| Web Dashboard (Phase W) | Post-launch, trigger-based | Deferred |

### Build Triggers

Start Phase W only if one or more of:

1. >=30% active users request web/history/export
2. >=10 Pro/Business users ask for desktop reporting
3. Chat history UX becomes support burden
4. Dashboard expected to improve Pro conversion

---

## 9. Decision Summary

| Question | Answer |
|----------|--------|
| Build now? | No — solo founder, mất 3-6 tuần delay core |
| Prepare now? | Yes — architecture query layer reusable |
| Build when? | Post-launch, trigger-based |
| Pricing change? | No — giữ giá, thêm entitlement awareness trong pricing-tiers |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-13 | Initial assessment |
| v1.1.0 | 2026-05-13 | Scope lock: Read-only dashboard companion only. Estimate revised 19-29 days. |
| v1.2.0 | 2026-05-13 | Status "Scope locked / implementation deferred". Added P1 security warning. Entitlement model genericized. Added concrete build triggers. |
