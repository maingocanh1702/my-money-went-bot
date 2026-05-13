# WD-07: Upgrade Gate

> **Feature ID:** WD-07
> **Priority:** P0
> **Tier:** Free (gate pattern applied across features)
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)

---

## 1. Overview

Upgrade Gate is a **pattern**, not a standalone screen. It applies across other features when Free tier users encounter Pro/Business-gated content.

---

## 2. Gate Types

| Type | Where Applied | Visual Treatment |
|------|---------------|------------------|
| **Inline blur** | Transaction rows >30 days | Rows blur(4px) + opacity 0.5 |
| **Section lock** | /trends entire page | Full content blur(6px) + centered overlay |
| **Feature lock** | CSV export button | Button disabled + lock icon + tooltip |
| **Filter lock** | Date range >30 days picker | Input disabled + lock icon + tooltip |
| **Card lock** | Monthly cards (category page) | Card gray + lock icon overlay |

---

## 3. Overlay Component

**Used for section lock (full page gate).**

```
+----------------------------------------------+
|              [Lock Icon 48px]                |
|                                              |
|    {Feature-specific headline}               |
|                                              |
|    {Feature-specific description}            |
|                                              |
|    [Nang cap ngay]     (primary button)      |
|    [Tim hieu them]     (text link)           |
+----------------------------------------------+
```

**Styling:**
- Container: --bg-card, --shadow-lg, --radius-xl, padding --space-8
- Max-width: 400px, centered vertically and horizontally
- Background behind: --overlay-blur (semi-transparent blur)
- Lock icon: 48px, --text-secondary
- Headline: --text-xl, --font-bold, --text-primary, text-align center
- Description: --text-base, --text-secondary, text-align center, max-width 320px
- Primary button: --primary bg, white text, --radius-md, height 48px, min-width 200px
- Text link: --primary color, --text-sm, margin-top --space-2

---

## 4. Feature-specific Messages

| Gate | Headline | Description | Required Tier |
|------|----------|-------------|:-------------:|
| Full history | Xem toan bo lich su giao dich | Nang cap len Pro de xem lich su khong gioi han va loc theo bat ky khoang thoi gian nao. | Pro |
| Charts/Trends | Phan tich xu huong chi tieu | Nang cap len Pro de xem bieu do xu huong, phan tich chi tieu theo thoi gian. | Pro |
| CSV export | Xuat du lieu giao dich | Nang cap len Pro de tai xuong du lieu giao dich duoi dang CSV. | Pro |
| P&L views | Bao cao loi nhuan | Nang cap len Business de xem bao cao loi nhuan chi tiet. | Business |
| Source attribution | Phan tich theo nguon thu nhap | Nang cap len Business de phan tich chi tiet theo tung nguon thu nhap. | Business |

---

## 5. Inline Blur Gate

**Used for: Transaction rows beyond 30 days (WD-03).**

- Rows beyond 30 days: CSS `filter: blur(4px); opacity: 0.5;`
- Small floating banner at the blur boundary:

```
+------------------------------------------------------+
| [Lock] Nang cap Pro de xem lich su day du  [Nang cap] |
+------------------------------------------------------+
```

- Banner: --primary-light bg, --primary text, --radius-md
- Sticky at bottom of visible (non-blurred) area
- [Nang cap] = small --primary button

---

## 6. Feature Lock

**Used for: CSV export button, disabled filters.**

- Button/input rendered but `disabled` + `cursor: not-allowed`
- Lock icon (12px) replacing normal icon or prepended
- Tooltip on hover: "{Gate message}. Nang cap de mo khoa."
- Tooltip: --bg-sidebar, --text-sidebar, --radius-sm, --text-xs, max-width 200px

---

## 7. Card Lock

**Used for: Monthly spending cards beyond current month (WD-04 for Free tier).**

- Card rendered with `opacity: 0.4; filter: grayscale(1);`
- Lock icon overlay (16px, centered)
- Click: shows tooltip "Nang cap Pro de xem lich su"

---

## 8. CTA Behavior

| CTA | Action |
|-----|--------|
| "Nang cap ngay" | Deep link to bot with /upgrade command pre-filled |
| "Tim hieu them" | Opens tienvenoidau.com/pricing in new tab |

---

## 9. Analytics

Every gate interaction fires analytics events:

| Event | Trigger |
|-------|---------|
| `dashboard_tier_gate_hit` | Any gate rendered to user. Props: gate_type, feature, current_tier |
| `dashboard_upgrade_cta_click` | User clicks "Nang cap ngay". Props: source_page, gate_type |
| `dashboard_learn_more_click` | User clicks "Tim hieu them". Props: source_page |

---

## 10. Mobile Adaptation

- Overlay: full-width, bottom-aligned (bottom sheet style) instead of centered
- Inline blur banner: full width, fixed above bottom tab bar
- Tooltips: replaced with bottom sheet on tap (mobile has no hover)
- Touch targets: all CTAs minimum 44x44px
