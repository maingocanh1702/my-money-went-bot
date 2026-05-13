# Feature Spec: Web Dashboard (Read-only Companion)

> **Version:** v1.0.0
> **Ngay tao:** 2026-05-13
> **Trang thai:** Scope locked / implementation deferred
> **Feature ID:** F-web
> **Phase:** W (post-launch, trigger-based)
> **Tham chieu:** BRD-vi v3.3.0 S4.3 - PRD-vi v1.8.0 S1.2 - Assessment (docs/research/webapp-resource-assessment.md) - Roadmap v1.3.0 Phase W
>
> **Implementation trigger:** Do not implement until one or more Phase W triggers are met:
> 1. >=30% active users request web/history/export
> 2. >=10 Pro/Business users ask for desktop reporting
> 3. Chat history UX becomes support burden
> 4. Dashboard expected to improve Pro conversion

---

## 1. Mo ta

Web dashboard is a **read-only companion UI** for visualizing existing transaction data captured via bot channels (Telegram/Discord/Messenger). It is **NOT** a primary interaction channel and does **NOT** replace chat-based workflows.

**Core value:** Users can view their financial data on desktop/mobile web with better visualization (charts, tables, filters) than chat history allows.

**Key constraints:**
- Read-only -- no transaction entry, no category CRUD
- Auth via magic link from bot -- no standalone registration
- Tier-gated -- Free 30 days / Pro full history / Business P&L
- Does not change pricing headline

---

## 2. Use Cases + Edge Cases

### Use Cases

| # | Actor | Hanh dong | Ket qua |
|---|-------|-----------|---------|
| 1 | User (Free) | Nhan link Xem Dashboard trong bot, mo web | Thay transaction list 30 ngay gan nhat |
| 2 | User (Free) | Filter theo category | Danh sach loc theo category da chon |
| 3 | User (Free) | Xem category monthly summary | Hien pie chart + spending breakdown |
| 4 | User (Pro) | Filter theo date range + funding source | Full history filtered |
| 5 | User (Pro) | Xem monthly trend chart | Bar chart spending theo thang |
| 6 | User (Pro) | Export CSV | Download transaction list as CSV |
| 7 | User (Business) | Xem P&L style view | Revenue vs expense summary |
| 8 | User (Business) | Source attribution view | Breakdown theo income source |
| 9 | User | Magic link expired, click lai | Thay Link het han, request link moi tu bot |
| 10 | User | Truy cap dashboard khong co link | Redirect toi landing page + huong dan mo tu bot |

### Edge Cases

| # | Category | Case | Xu ly |
|---|----------|------|-------|
| 1 | Security | Magic link su dung lan 2 | Reject -- single-use only |
| 2 | Security | Magic link het TTL (>10 phut) | Reject + thong bao request moi |
| 3 | Security | User A dung magic link User B | Reject -- link bound to user_id |
| 4 | Security | Brute force magic link token | Rate limit + 404 response (no info leak) |
| 5 | Data | User khong co transaction nao | Empty state with CTA |
| 6 | Data | Free user xem >30 ngay | Blur/lock + upgrade CTA |
| 7 | Data | User co 10000+ transactions | Pagination (50 per page), lazy load |
| 8 | Concurrency | User dang xem, bot nhan tx moi | Dashboard refresh khi user navigate |
| 9 | Data Integrity | Transaction deleted via bot | Dashboard reflects current DB state on next load |
| 10 | Cross-Feature | User downgrade Pro to Free dang xem full history | Session stays until refresh, then enforce 30d limit |
| 11 | Security | JWT token stolen/leaked | Short-lived access (15 min) + refresh token rotation |
| 12 | Security | CORS misconfiguration | Strict origin whitelist: app.tienvenoidau.com only |

---

## 3. Screens and States

> **Note:** Screen designs deferred toi Phase W implementation planning. Below is structural spec only.

### 3.1. Login/Auth Screen

| State | Mo ta |
|-------|-------|
| Loading | Validating magic link token |
| Ready | N/A -- auto-redirect to dashboard on valid link |
| Error | Link het han hoac khong hop le. Mo bot de nhan link moi. |
| Empty | N/A |

### 3.2. Transaction List Screen

| State | Mo ta |
|-------|-------|
| Loading | Skeleton table (per user rules) |
| Ready | Transaction table + filters (date, category, funding source) + pagination |
| Error | Khong the tai du lieu. Thu lai sau. + retry CTA |
| Empty | Chua co giao dich nao. Ket noi ngan hang qua bot! + icon + CTA |

### 3.3. Category Dashboard Screen

| State | Mo ta |
|-------|-------|
| Loading | Skeleton cards + chart placeholder |
| Ready | Category pie chart + spending breakdown + budget progress bars |
| Error | Error banner + retry |
| Empty | Chua co du lieu thang nay. |

### 3.4. Charts/Trends Screen (Pro+)

| State | Mo ta |
|-------|-------|
| Loading | Skeleton chart |
| Ready | Monthly trend bar chart + category breakdown over time |
| Error | Error banner + retry |
| Empty | Can it nhat 2 thang du lieu de hien trend. |

### 3.5. Settings Screen (read-only)

| State | Mo ta |
|-------|-------|
| Loading | Skeleton |
| Ready | Plan info, timezone, webhook URL (masked), connected banks |
| Error | Error banner |
| Empty | N/A (always has user data) |

---

## 4. Domain Model (shared -- xem PRD S4)

Dashboard reads tu existing tables, KHONG them table moi ngoai tru:

| Table | Mo ta | Moi |
|-------|-------|:---:|
| dashboard_sessions | Refresh token hash, expires_at, revoked_at | NEW |
| dashboard_magic_links | Single-use auth tokens, TTL, used_at | NEW |
| analytics_events | dashboard_* audit/product events | Existing |
| transactions | Read-only query | Existing |
| categories | Read-only query | Existing |
| funding_sources | Read-only query | Existing |
| users | Plan info, timezone | Existing |

---

## 5. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| dashboard_link_generated | Bot generates magic link | user_id, channel_type |
| dashboard_link_used | User opens dashboard via link | user_id, latency_ms |
| dashboard_link_expired | User clicks expired link | user_id, age_minutes |
| dashboard_session_start | JWT session created | user_id, tier |
| dashboard_page_view | User navigates to page | user_id, page |
| dashboard_filter_used | User applies filter | user_id, filter_type |
| dashboard_export_csv | User exports CSV (Pro+) | user_id, row_count |
| dashboard_tier_gate_hit | Free user hits Pro feature | user_id, feature |
| dashboard_upgrade_cta_click | User clicks upgrade from dashboard | user_id, source_page |

---

## 6. Acceptance Criteria

### Auth / Security (P1)

- [ ] Magic links are single-use -- invalidated after first use
- [ ] Magic links have short TTL (10 minutes or less)
- [ ] Magic links bind to existing user_id -- no standalone registration
- [ ] Magic link generation rate limited (max 3/hour per user)
- [ ] JWT access token short-lived (15 min), refresh token rotation
- [ ] Tenant isolation tests mandatory -- User A cannot see User B data
- [ ] CORS strict: only app.tienvenoidau.com
- [ ] All auth events audited
- [ ] 404 response for invalid/expired links (no information leakage)

### Data / Display

- [ ] Transaction list with pagination (50 per page)
- [ ] Filter by date range, category, funding source
- [ ] Category breakdown with spending summary
- [ ] Budget progress bars for budgeted categories
- [ ] Monthly trend chart (Pro+)
- [ ] CSV export (Pro+)
- [ ] P&L view (Business)
- [ ] Source attribution (Business)

### Tier Gating

- [ ] Free: last 30 days only, basic table + category summary, no charts, no export
- [ ] Pro: full history, charts/trends, CSV export, multi-bank view
- [ ] Business: P&L views, source attribution
- [ ] Scheduled export/report explicitly deferred to Phase W2
- [ ] Upgrade CTA when Free user hits gated feature

### Responsive

- [ ] 3 breakpoints: 375px, 768px, 1440px (per project rules)
- [ ] Touch targets 44x44px or larger
- [ ] Sidebar collapse pattern per project rules

---

## 7. Open Questions / Changelog

### Open Questions (resolve during Phase W implementation planning)

| # | Question | Options | Decision |
|---|----------|---------|----------|
| 1 | Magic link vs Telegram Login Widget | Magic link simpler, Widget more native | TBD |
| 2 | Vite + React vs vanilla JS | React for chart libs, vanilla for minimal | TBD |
| 3 | Chart library | Chart.js vs Recharts | TBD |
| 4 | Realtime updates or refresh-on-navigate | Refresh MVP, WebSocket later | Lean refresh |
| 5 | Subdomain vs path | app.tienvenoidau.com vs tienvenoidau.com/app | Lean subdomain |

### Changelog

| Version | Ngay | Thay doi |
|---------|------|----------|
| v1.0.0 | 2026-05-13 | Initial feature spec. Scope locked: read-only companion dashboard. 10 use cases, 12 edge cases, 5 screens x 4 states, 2 new tables, 9 analytics events, P1 auth security requirements. Implementation deferred (trigger-based). |
