# WD-01: Shell/Navigation

> **Feature ID:** WD-01
> **Priority:** P0
> **Tier:** All
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)

---

## 1. Screens

| Screen | Loading | Ready | Error | Empty |
|--------|---------|-------|-------|-------|
| App Shell | Skeleton sidebar + content area | Full nav + active page content | API down banner top + cached nav | N/A |

---

## 2. Sidebar (Desktop >= 1024px)

**Width:** 240px fixed. Background: --bg-sidebar (#1E293B).

### Nav Items

| # | Icon | Label | Route | Tier | Badge |
|---|------|-------|-------|------|-------|
| 1 | list | Giao dich | /transactions | All | Transaction count today |
| 2 | pie-chart | Danh muc | /categories | All | - |
| 3 | trending-up | Xu huong | /trends | Pro+ | Lock icon for Free |
| 4 | settings | Cai dat | /settings | All | - |

**Active state:** --bg-sidebar-hover background + --text-sidebar-active text + left 3px accent border (--primary).

**Hover state:** --bg-sidebar-hover background. Transition: --transition-fast.

### Bottom Section

- **Plan badge:** Rounded chip with tier color. Text: "Free" / "Pro" / "Family" / "Business".
- **"Mo bot" link:** Icon + text, opens bot deep link. Color: --text-sidebar.
- **"Nang cap" button:** Only visible for Free tier. Small outlined button, --primary color.

---

## 3. Sidebar Collapsed (768-1023px)

**Width:** 64px. Icons only, centered. Hover: tooltip with label name (right side).

---

## 4. Bottom Tab Bar (< 768px)

**Height:** 56px (--bottombar-height). Background: --bg-card. Border-top: 1px --border.

| # | Icon | Label | Route |
|---|------|-------|-------|
| 1 | list | Giao dich | /transactions |
| 2 | pie-chart | Danh muc | /categories |
| 3 | trending-up | Xu huong | /trends |
| 4 | settings | Cai dat | /settings |

- Active: --primary color icon + label. Inactive: --text-secondary.
- Lock icon overlay on "Xu huong" for Free tier.
- Touch target: 44x44px minimum per item.

---

## 5. Top Bar

**Height:** 64px (--topbar-height). Background: --bg-card. Border-bottom: 1px --border.

**Contents:**
- Left: Page title (--text-2xl, --font-semibold)
- Right: User avatar/initial circle (32px) + dropdown (Dang nhap tu: Telegram, Phien het han: 14:30, Dang xuat)

**Mobile (< 768px):**
- Left: Hamburger icon (opens overlay sidebar) + Page title (--text-lg)
- Right: User initial circle (32px)

---

## 6. Loading State

- Sidebar: render immediately with nav items (static, no API needed)
- Content area: skeleton placeholder matching the active page layout
- Top bar: page title shows, user avatar shows skeleton circle

---

## 7. Error State

- If API unreachable: top banner (--warning-bg, --warning text): "Khong the ket noi server. Dang thu lai..."
- Auto-retry every 10s, max 3 attempts
- After 3 failures: banner changes to "Khong the ket noi. Vui long thu lai sau." + manual retry button

---

## 8. Interactions

| Action | Behavior |
|--------|----------|
| Click nav item | Navigate to route, update active state |
| Click "Mo bot" | Open deep link (telegram/discord) in new tab |
| Click "Nang cap" | Open bot deep link with /upgrade pre-filled |
| Click user avatar | Toggle dropdown menu |
| Click "Dang xuat" | Clear JWT, redirect to /auth landing |
| Resize window cross breakpoint | Smooth transition sidebar <-> bottom bar |
