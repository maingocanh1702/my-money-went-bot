# WD-03: Transaction List

> **Feature ID:** WD-03
> **Priority:** P0
> **Tier:** All (30d Free, full Pro+)
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)

---

## 1. Screens

| Screen | Loading | Ready | Error | Empty |
|--------|---------|-------|-------|-------|
| Transaction Table | Skeleton table 10 rows | Data table + filters + pagination | Error banner + retry | Icon + CTA |
| Free Tier Gate | N/A | Blur rows >30d + upgrade overlay | N/A | N/A |

---

## 2. Layout

```
+---------------------------------------------------+
| Filter Bar                                         |
| [Date Range] [Category v] [Source v]  [Xoa bo loc] |
+---------------------------------------------------+
| Summary Strip                                      |
| Tong thu: +2,500,000d  |  Tong chi: -1,800,000d   |
+---------------------------------------------------+
| Transaction Table                                  |
| Ngay  | Mo ta        | Danh muc | Nguon  | So tien |
| ------+------------- +----------+--------+---------|
| 13/05 | GRAB*1234... | Di lai   | VCB    | -45,000 |
| 13/05 | CHUYEN TIEN  | Tiet kiem| TCB    |+500,000 |
| ...                                                |
+---------------------------------------------------+
| < 1 2 3 ... 25 >  Hien thi 1-50 / 1,234 giao dich|
+---------------------------------------------------+
```

---

## 3. Table Columns

| Column | Width | Content | Sort | Mobile visible |
|--------|-------|---------|:----:|:--------------:|
| Ngay | 120px | DD/MM/YYYY HH:mm | Yes (default: desc) | Yes (DD/MM only) |
| Mo ta | flex | Description, truncate 60ch | No | Yes (30ch) |
| Danh muc | 140px | Category chip: color dot + name | Yes | Yes |
| Nguon | 120px | Bank name + last4 (VCB ****1234) | Yes | No (in expand) |
| So tien | 130px | VND formatted, +green / -red | Yes | Yes |

**Row styling:**
- Height: 48px. Border-bottom: 1px --border.
- Hover: --bg-input background. Cursor: pointer.
- Click: expand row (show full description, funding source on mobile).
- Amount format: +1,500,000d (--income) or -45,000d (--expense).
- Category chip: 8px color dot + text, --radius-full background pill.

---

## 4. Filter Controls

| Filter | Type | Default | Free restriction |
|--------|------|---------|-----------------|
| Date range | Date range picker (2 inputs: Tu ngay — Den ngay) | This month (1st to today) | Locked to last 30 days |
| Danh muc | Multi-select dropdown with color dots | Tat ca | None |
| Nguon | Single-select dropdown | Tat ca | None |
| Xoa bo loc | Text button (--text-secondary) | — | — |

**Date range picker:**
- Two date inputs side by side: "Tu ngay" + "Den ngay"
- Calendar popup on click
- Min date: account created_at. Max: today.
- Free tier: "Tu ngay" min = today minus 30 days. Locked with tooltip: "Nang cap Pro de xem lich su day du"

**Category multi-select:**
- Dropdown with checkboxes
- Each item: color dot (8px) + category name + count
- "Chon tat ca" / "Bo chon tat ca" at top
- Max height: 300px with scroll

**Funding source select:**
- Single select dropdown
- Each item: bank icon (16px) + bank name + last4
- "Tat ca nguon" default option

**Filter behavior:**
- Filters apply immediately on change (no "Apply" button)
- Summary strip updates with filtered totals
- URL query params update for shareability
- "Xoa bo loc" resets all to defaults

---

## 5. Summary Strip

**Layout:** Horizontal bar below filters. Background: --bg-card. Padding: --space-4.

| Item | Format | Color |
|------|--------|-------|
| Tong thu | +{amount}d | --income |
| Tong chi | -{amount}d | --expense |
| So giao dich | {count} giao dich | --text-secondary |

**Mobile:** Stack vertically (3 rows).

---

## 6. Pagination

- 50 items per page
- Component: < Prev [1] [2] [3] ... [25] Next >
- Show: "Hien thi 1-50 / 1,234 giao dich"
- Mobile: simplified < Prev | Trang 1/25 | Next >
- Scroll to top on page change

---

## 7. States

### Loading
- Skeleton table: 10 rows, each row = 5 gray rectangles matching column widths
- Filter bar: skeleton inputs (3 rectangles)
- Summary strip: 3 skeleton text blocks
- Animation: pulse shimmer

### Error
- Banner above table: --expense-bg background, --expense text
- Icon: alert-circle. Text: "Khong the tai du lieu. Vui long thu lai."
- CTA: "Thu lai" button
- Filters still visible (cached)

### Empty
- Centered in content area
- Icon: wallet (64px, --text-secondary)
- Title: "Chua co giao dich nao" (--text-xl, --font-semibold)
- Body: "Ket noi ngan hang qua bot de bat dau theo doi giao dich." (--text-base, --text-secondary)
- CTA: "Mo bot" button (--primary)

### Free Tier Gate (>30 days)
- Rows beyond 30 days: CSS blur(4px) + opacity 0.5
- Floating overlay at bottom of blurred rows:
  - Lock icon (32px) + "Nang cap Pro de xem toan bo lich su"
  - [Nang cap ngay] primary button
- Date picker "Tu ngay" locked with lock icon

---

## 8. Mobile Adaptation (< 768px)

- Table transforms to **card list**
- Each card:

```
+----------------------------------+
| 13/05/2026          -45,000d     |
| GRAB*1234 THANH TOAN             |
| [Di lai]  (category chip)       |
+----------------------------------+
```

- Tap card to expand: show funding source, full description
- Filters: collapse into "Bo loc" button -> opens bottom sheet modal
- Bottom sheet: full-width filters stacked vertically + "Ap dung" button
- Summary strip: stacks to 3 rows

---

## 9. Interactions

| Action | Behavior |
|--------|----------|
| Change filter | Immediate reload, update URL params |
| Click column header | Toggle sort asc/desc, arrow indicator |
| Click row | Expand inline (show hidden fields) |
| Click category chip | Navigate to /categories?selected=X |
| Click "Xoa bo loc" | Reset all filters to defaults |
| Scroll past blurred Free rows | Upgrade overlay stays fixed |
| Click "Nang cap ngay" | Deep link to bot /upgrade |
