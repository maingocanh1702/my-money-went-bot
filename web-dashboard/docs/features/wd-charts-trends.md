# WD-05: Charts/Trends

> **Feature ID:** WD-05
> **Priority:** P1
> **Tier:** Pro+ only (Free: blurred + upgrade gate)
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)

---

## 1. Screens

| Screen | Loading | Ready | Error | Empty |
|--------|---------|-------|-------|-------|
| Trends View | Skeleton charts | Bar + breakdown charts | Banner + retry | "Can it nhat 2 thang du lieu" |
| Free Gate | N/A | Full page blur + upgrade overlay | N/A | N/A |

---

## 2. Layout

```
+--------------------------------------------------------+
| Time Range: [3T] [6T] [12T] [Tat ca]                  |
+--------------------------------------------------------+
| Chi tieu theo thang (Bar Chart)                        |
|                                                        |
|  2.5M +-                                               |
|       |  ██                                            |
|  2.0M |  ██  ██      ██                                |
|       |  ██  ██  ██  ██  ██  ██                        |
|  1.0M |  ██  ██  ██  ██  ██  ██                        |
|       +--T12--T1--T2--T3--T4--T5-->                    |
+--------------------------------------------------------+
| Danh muc theo thoi gian (Stacked Bar)                  |
|                                                        |
|  2.5M +-                                               |
|       |  ██  An uong                                   |
|       |  ██  Di lai                                    |
|       |  ██  Mua sam                                   |
|       |  ██  Hoa don                                   |
|       |  ██  Khac                                      |
|       +--T12--T1--T2--T3--T4--T5-->                    |
+--------------------------------------------------------+
| Thu vs Chi (Grouped Bar)                               |
|       |  ▓▓  ██                                        |
|       |  ▓▓  ██  ▓▓  ██                                |
|       +--T4------T5------>                             |
|          ▓▓ = Thu nhap  ██ = Chi tieu                  |
+--------------------------------------------------------+
```

---

## 3. Time Range Selector

- Segmented control (toggle buttons)
- Options: "3T" (3 thang), "6T" (6 thang), "12T" (12 thang), "Tat ca"
- Default: 6T
- Active: --primary background, white text
- Inactive: --bg-input background, --text-primary text
- Changes all 3 charts simultaneously

---

## 4. Monthly Spending Trend

- **Type:** Vertical bar chart
- **Y-axis:** VND amount, auto-scale, abbreviated (500k, 1M, 2.5M)
- **X-axis:** Month labels (T1, T2, ... T12 for Vietnamese)
- **Bar color:** --primary
- **Hover:** Tooltip: "Thang {month}: {amount}d"
- **Click bar:** Navigate to /categories?month={month}
- **Grid lines:** Horizontal only, --border color, dashed
- **Bar width:** 60% of available space, --radius-sm top corners
- **Animation:** Bars grow from bottom on load (--transition-normal)

---

## 5. Category Breakdown Over Time

- **Type:** Stacked vertical bar chart
- **Segments:** Top 5 categories + "Khac"
- **Colors:** Category palette from design-tokens.md
- **Legend:** Below chart, horizontal wrap. Each: color dot + name. Click legend to toggle visibility.
- **Hover:** Tooltip: "{category}: {amount}d ({percent}%)"
- **Click segment:** Navigate to /transactions?category={id}&month={month}

---

## 6. Income vs Expense Comparison

- **Type:** Grouped bar chart (2 bars per month side by side)
- **Colors:** --income (green) for thu nhap, --expense (red) for chi tieu
- **Legend:** Bottom, 2 items: "Thu nhap" + "Chi tieu"
- **Hover:** "{type}: {amount}d"
- **Net amount:** Text below each month pair: "+{net}d" green or "-{net}d" red

---

## 7. States

### Loading
- 3 skeleton chart areas (rectangular placeholders with pulse shimmer)
- Time range selector: visible but disabled (skeleton style)

### Error
- Banner: --expense-bg, "Khong the tai bieu do. Vui long thu lai." + retry button
- Charts area: empty with subtle --border dashed box

### Empty
- Centered in content area
- Icon: bar-chart (64px, --text-secondary)
- Title: "Can it nhat 2 thang du lieu de hien xu huong"
- Body: "Tiep tuc su dung bot de tich luy du lieu giao dich."

### Free Tier Gate
- All 3 charts rendered but with CSS blur(6px) + desaturate
- Overlay centered on page (see [wd-upgrade-gate.md](wd-upgrade-gate.md)):
  - Lock icon 48px
  - "Phan tich xu huong chi tieu voi goi Pro"
  - [Nang cap ngay] primary button
  - [Tim hieu them] text link
- Background charts provide visual hint of value

---

## 8. Mobile Adaptation (< 768px)

- Charts stack vertically, full width, 16px gap
- Chart height: 200px each (vs 280px desktop)
- Time range: horizontal scroll chips instead of segmented control
- Legend: wraps to 2 rows if needed
- Touch: tap instead of hover for tooltips (tap-away to dismiss)

---

## 9. Interactions

| Action | Behavior |
|--------|----------|
| Click time range option | Update all charts to selected range |
| Hover bar | Show tooltip with details |
| Click spending bar | Navigate to /categories for that month |
| Click stacked segment | Navigate to /transactions filtered |
| Click legend item | Toggle that category visibility on chart |
| Tap chart (mobile) | Show tooltip, tap elsewhere to dismiss |
