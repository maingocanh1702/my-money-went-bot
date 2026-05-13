# Web Dashboard — Product Requirements Document (PRD)

> **Version:** v1.0.0
> **Ngay tao:** 2026-05-13
> **Trang thai:** Scope locked / implementation deferred
> **Parent PRD:** [Bot PRD-vi v1.8.0](../../docs/prd-vi.md) S1.2
> **Dashboard BRD:** [brd.md](brd.md) v1.0.0

---

## 1. Design Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Read-only companion** | Dashboard visualizes, bot manages. No write operations. |
| 2 | **Zero-friction auth** | One click from bot to dashboard. No passwords. |
| 3 | **Desktop-first, mobile-ready** | Optimize for desktop data review. Responsive to 375px. |
| 4 | **Progressive tier value** | Free gets basics. Pro/Business see clear upgrade value. |
| 5 | **Fast and lightweight** | SPA loads <2s. API <200ms p95. No SSR. |

---

## 2. Information Architecture

```
app.tienvenoidau.com
+-- /auth/verify?token=xxx     (magic link landing)
+-- /                          (redirect to /transactions)
+-- /transactions              (transaction list + filters)
+-- /categories                (category dashboard + charts)
+-- /trends                    (monthly trends -- Pro+ only)
+-- /settings                  (read-only plan/account info)
```

---

## 3. Feature List

| # | Feature | Doc | Tier | Priority |
|---|---------|-----|------|----------|
| WD-01 | Shell/Navigation | [wd-shell-navigation.md](features/wd-shell-navigation.md) | All | P0 |
| WD-02 | Auth Flow | [wd-auth-flow.md](features/wd-auth-flow.md) | All | P0 |
| WD-03 | Transaction List | [wd-transaction-list.md](features/wd-transaction-list.md) | All | P0 |
| WD-04 | Category Dashboard | [wd-category-dashboard.md](features/wd-category-dashboard.md) | All | P0 |
| WD-05 | Charts/Trends | [wd-charts-trends.md](features/wd-charts-trends.md) | Pro+ | P1 |
| WD-06 | Settings | [wd-settings.md](features/wd-settings.md) | All | P2 |
| WD-07 | Upgrade Gate | [wd-upgrade-gate.md](features/wd-upgrade-gate.md) | Free | P0 |

---

## 4. Responsive Rules

| Breakpoint | Layout | Sidebar | Navigation |
|------------|--------|---------|------------|
| >= 1440px | Max-width 1200px content | Fixed 240px | Sidebar |
| 1024-1439px | Full width content | Fixed 240px | Sidebar |
| 768-1023px | Full width | Collapsed 64px icons | Sidebar icons |
| < 768px | Mobile-first | Hidden | Bottom tab bar (4 items) |

Touch targets: minimum 44x44px on all breakpoints.

---

## 5. Cross-references

- [Dashboard BRD](brd.md) — Business requirements, success metrics
- [Feature spec (functional)](../../docs/features/feature-web-dashboard.md) — Use cases, edge cases, AC
- [Assessment](../../docs/research/webapp-resource-assessment.md) — Resource estimate, risks
- [Bot PRD](../../docs/prd-vi.md) — Parent product context
- [Design tokens](design-tokens.md) — Colors, typography, spacing

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-05-13 | Initial PRD. 7 features, responsive rules, IA. Detail per feature in docs/features/. |
