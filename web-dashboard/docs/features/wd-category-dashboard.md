# WD-04: Category Dashboard

> **Feature ID:** WD-04
> **Priority:** P0
> **Tier:** All (basic Free, full Pro+)
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)

---

## 1. Screens

| Screen | Loading | Ready | Error | Empty |
|--------|---------|-------|-------|-------|
| Category Overview | Skeleton cards + chart | Pie + cards + budget bars | Banner + retry | "Chua co du lieu thang nay" |

---

## 2. Layout

```
+---------------------------+---------------------------+
| Pie Chart (50%)           | Top Categories List (50%) |
| [Donut chart with         | 1. An uong   800k  35%   |
|  center total]            | 2. Di lai    450k  20%   |
|                           | 3. Mua sam   300k  13%   |
|                           | 4. Hoa don   250k  11%   |
|                           | 5. Khac      500k  21%   |
+---------------------------+---------------------------+
| Budget Progress (full width)                          |
| An uong  [========>       ] 800k / 1,000k   80%      |
| Di lai   [=====>          ] 450k / 800k     56%      |
| Mua sam  [==========>    ] 300k / 400k     75%      |
+-------------------------------------------------------+
| Monthly Cards (scroll)                                |
| [T5: 2.3M] [T4: 1.8M] [T3: 2.1M] [T2: 1.5M]       |
+-------------------------------------------------------+
```

**Month picker:** At top-right of section. Default: current month. Free: current month only.

---

## 3. Pie Chart

- **Type:** Donut chart (hole ratio 60%)
- **Segments:** Top 5 categories by spending + "Khac" (Others) = max 6
- **Colors:** From category palette (design-tokens.md S Category Colors)
- **Center text:** Total spending this month, --text-2xl, --font-bold
- **Center sub:** Month name, --text-sm, --text-secondary
- **Hover:** Tooltip: "{category}: {amount} ({percent}%)"
- **Click segment:** Navigate to /transactions?category={id}&month={month}
- **Animation:** Segments animate in clockwise on first load (--transition-slow)
- **Size:** 280px diameter desktop, 240px mobile

---

## 4. Top Categories List

- Ordered by spending amount descending
- Max 5 items + "Khac" row (sum of remaining)

**Item layout:**

```
[#] [Color Dot 12px] [Name]  ......  [Amount]  [Percent%]
```

- Rank number: --text-secondary, --text-sm
- Color dot: 12px circle, matches pie segment
- Name: --text-base, --font-medium
- Amount: --text-base, --font-semibold, right-aligned
- Percent: --text-sm, --text-secondary, right-aligned

**Hover:** Background --bg-input. Cursor pointer. Highlights corresponding pie segment.
**Click:** Same as pie click — navigate to /transactions filtered.

---

## 5. Budget Progress Bars

**Visible only for categories with budget set.** If no budgets: hide section + show tip card.

**Tip card (no budgets):**
```
[lightbulb icon] Dat ngan sach qua bot de theo doi chi tieu theo danh muc.
                 [Mo bot] (text link)
```

**Progress bar item:**

```
[Category name]  [===========        ] {spent} / {budget}  ({percent}%)
```

- Bar height: 8px, --radius-full
- Bar colors:
  - < 70%: --income (green)
  - 70-90%: --warning (yellow)
  - > 90%: --expense (red)
- Bar background: --bg-input
- Text: --text-sm
- Hover: tooltip with remaining amount "Con lai: {remaining}d"

---

## 6. Monthly Spending Cards

- Horizontal scroll strip (desktop shows 4-6, mobile 2-3 visible)
- Pro+: last 6 months. Free: current month only (others locked).

**Card:**
```
+-----------+
| Thang 5   |
| 2,300,000 |
+-----------+
```

- Size: 120px wide x 80px tall
- Background: --bg-card, --shadow-sm, --radius-md
- Active month: --primary border (2px), --primary-light background
- Month label: --text-sm, --text-secondary
- Amount: --text-lg, --font-bold
- Click: updates pie chart + categories list to that month
- Free locked months: gray opacity 0.5, lock icon overlay

---

## 7. States

### Loading
- Pie chart area: gray circle placeholder (pulse shimmer)
- Category list: 5 skeleton rows (dot + text + number)
- Budget bars: 3 skeleton bars
- Monthly cards: 4 skeleton cards

### Error
- Banner at top: --expense-bg, alert icon
- "Khong the tai du lieu danh muc. Vui long thu lai."
- [Thu lai] button

### Empty
- Centered in content area
- Icon: pie-chart (64px, --text-secondary)
- Title: "Chua co du lieu thang nay" (--text-xl)
- Body: "Giao dich se tu dong duoc phan loai khi ban nhan tien qua bot." (--text-base, --text-secondary)

---

## 8. Mobile Adaptation (< 768px)

- Pie chart: full width, 240px diameter, centered
- Categories list: below pie, full width
- Budget bars: below categories, full width
- Monthly cards: horizontal scroll strip, 2 visible + peek
- Month picker: full-width dropdown instead of compact picker

---

## 9. Interactions

| Action | Behavior |
|--------|----------|
| Hover pie segment | Highlight segment + corresponding list item |
| Click pie segment | Navigate to /transactions filtered |
| Click category list item | Same as pie click |
| Click monthly card | Update pie + list to that month |
| Hover budget bar | Tooltip with remaining amount |
| Click "Mo bot" in tip | Deep link to bot |
| Change month picker | Update all sections to selected month |
