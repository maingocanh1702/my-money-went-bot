# Design Tokens — Web Dashboard

> **Version:** v1.0.0
> **Ngay tao:** 2026-05-13
> **Status:** Draft — finalize when Phase W starts

---

## Colors

```css
:root {
  /* Brand */
  --primary: #2563EB;
  --primary-hover: #1D4ED8;
  --primary-light: #DBEAFE;

  /* Semantic */
  --income: #16A34A;
  --income-bg: #DCFCE7;
  --expense: #DC2626;
  --expense-bg: #FEE2E2;
  --warning: #F59E0B;
  --warning-bg: #FEF3C7;

  /* Neutral */
  --bg-page: #F8FAFC;
  --bg-card: #FFFFFF;
  --bg-sidebar: #1E293B;
  --bg-sidebar-hover: #334155;
  --bg-input: #F1F5F9;

  /* Text */
  --text-primary: #0F172A;
  --text-secondary: #64748B;
  --text-sidebar: #CBD5E1;
  --text-sidebar-active: #FFFFFF;
  --text-placeholder: #94A3B8;

  /* Border */
  --border: #E2E8F0;
  --border-focus: #2563EB;

  /* Tier badges */
  --tier-free: #94A3B8;
  --tier-pro: #2563EB;
  --tier-family: #8B5CF6;
  --tier-business: #F59E0B;

  /* Overlay */
  --overlay-blur: rgba(248, 250, 252, 0.85);
}
```

## Typography

```css
:root {
  --font-primary: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  --text-xs: 0.75rem;    /* 12px */
  --text-sm: 0.875rem;   /* 14px */
  --text-base: 1rem;     /* 16px */
  --text-lg: 1.125rem;   /* 18px */
  --text-xl: 1.25rem;    /* 20px */
  --text-2xl: 1.5rem;    /* 24px */
  --text-3xl: 1.875rem;  /* 30px */

  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;

  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
}
```

## Spacing

```css
:root {
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */

  --sidebar-width: 240px;
  --sidebar-collapsed: 64px;
  --topbar-height: 64px;
  --bottombar-height: 56px;
}
```

## Border Radius

```css
:root {
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;
}
```

## Shadows

```css
:root {
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.08);
}
```

## Transitions

```css
:root {
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 350ms ease;
}
```

## Category Colors (default palette)

| # | Name | Color | Usage |
|---|------|-------|-------|
| 1 | Blue | #3B82F6 | An uong |
| 2 | Green | #22C55E | Tiet kiem |
| 3 | Purple | #8B5CF6 | Dang ky dich vu |
| 4 | Orange | #F97316 | Di lai |
| 5 | Pink | #EC4899 | Mua sam |
| 6 | Teal | #14B8A6 | Hoa don |
| 7 | Yellow | #EAB308 | Giai tri |
| 8 | Gray | #6B7280 | Khac |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-05-13 | Initial tokens. Colors, typography, spacing, shadows, transitions. |
