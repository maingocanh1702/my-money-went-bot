# WD-06: Settings (Read-only)

> **Feature ID:** WD-06
> **Priority:** P2
> **Tier:** All
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)

---

## 1. Screens

| Screen | Loading | Ready | Error | Empty |
|--------|---------|-------|-------|-------|
| Settings View | Skeleton cards | Info cards (read-only) | Banner + retry | N/A (always has user data) |

---

## 2. Layout

```
+--------------------------------------------------------+
| Thong tin tai khoan                                    |
+--------------------------------------------------------+
| Goi          Pro                [Pro badge]             |
| Het han      15/06/2026                                |
| Tham gia     01/03/2026                                |
| Mui gio      Asia/Ho_Chi_Minh                          |
| Kenh         Telegram                                  |
+--------------------------------------------------------+

+--------------------------------------------------------+
| Ngan hang da ket noi                                   |
+--------------------------------------------------------+
| [VCB icon] Vietcombank ****1234    Dang hoat dong  [●] |
| [TCB icon] Techcombank ****5678    Dang hoat dong  [●] |
| [Email]    Email forwarding        Dang hoat dong  [●] |
+--------------------------------------------------------+

+--------------------------------------------------------+
| Phien dang nhap                                        |
+--------------------------------------------------------+
| Trang thai       Dang hoat dong                        |
| Het han          14:30 hom nay                         |
| Dang nhap luc    14:15 13/05/2026                      |
+--------------------------------------------------------+

+--------------------------------------------------------+
| [Mo bot de thay doi cai dat]  (primary button)         |
+--------------------------------------------------------+
```

---

## 3. Card: Thong tin tai khoan

| Field | Source | Display |
|-------|--------|---------|
| Goi | users.plan | Plan name + tier badge chip |
| Het han | trial_ends_at / subscription | DD/MM/YYYY. If no expiry: "Khong gioi han" |
| Tham gia | users.created_at | DD/MM/YYYY |
| Mui gio | users.timezone | IANA timezone string |
| Kenh | users.channel_type | "Telegram" / "Discord" / "Messenger" |

**Plan badge:** Chip with tier color from design-tokens (--tier-free, --tier-pro, etc.)

---

## 4. Card: Ngan hang da ket noi

**List of funding_sources where status = active.**

| Element | Display |
|---------|---------|
| Icon | Bank icon (16px) or email icon for email sources |
| Name | Bank name (VD: Vietcombank, Techcombank) |
| Last4 | ****1234 |
| Status | Green dot + "Dang hoat dong" or gray + "An" |

**If no banks connected:**
- Text: "Chua ket noi ngan hang nao."
- CTA: "Ket noi qua bot" text link

---

## 5. Card: Phien dang nhap

| Field | Source | Display |
|-------|--------|---------|
| Trang thai | JWT validity | "Dang hoat dong" (green dot) |
| Het han | JWT expiry | HH:mm + "hom nay" |
| Dang nhap luc | dashboard_sessions.created_at | HH:mm DD/MM/YYYY |

---

## 6. CTA Button

- Text: "Mo bot de thay doi cai dat"
- Style: --primary background, white text, full width on mobile, auto width desktop
- Action: deep link to bot
- Note below button (--text-sm, --text-secondary): "Cac thay doi se duoc cap nhat khi ban tai lai trang nay."

---

## 7. States

### Loading
- 3 skeleton cards (same height/shape as final cards, pulse shimmer)
- CTA button: skeleton rectangle

### Error
- Banner: "Khong the tai cai dat. Vui long thu lai." + retry button
- Cards hidden

---

## 8. Mobile Adaptation (< 768px)

- Cards stack full width with --space-4 gap
- CTA button: full width, sticky at bottom (above bottom tab bar)
- Card padding: --space-4 (vs --space-6 desktop)

---

## 9. Interactions

| Action | Behavior |
|--------|----------|
| Click "Mo bot" | Deep link to Telegram/Discord |
| All fields | Read-only, no edit capability |
| Hover bank row | Subtle --bg-input highlight |
| Pull to refresh (mobile) | Reload settings data |
