# WD-02: Auth Flow

> **Feature ID:** WD-02
> **Priority:** P0
> **Tier:** All
> **Parent:** [PRD](../prd.md) | [Design Tokens](../design-tokens.md)
> **Security:** P1 — see [BRD S6](../brd.md)

---

## 1. Screens

| Screen | Loading | Ready | Error | Empty |
|--------|---------|-------|-------|-------|
| Magic Link Verify | Spinner + "Dang xac thuc..." | Auto-redirect to /transactions | Link expired/invalid/used | N/A |
| No Auth Landing | N/A | Landing with "Mo bot de dang nhap" CTA | N/A | N/A |
| Session Expired | N/A | N/A | Overlay: "Phien da het han" | N/A |

---

## 2. Magic Link Verify Screen

### 2.1 Loading State

**Layout:** Centered vertically and horizontally on full viewport.

```
+--------------------------------------+
|                                      |
|          [Spinner 48px]              |
|                                      |
|       Dang xac thuc...               |
|   Vui long doi trong giay lat        |
|                                      |
+--------------------------------------+
```

- Background: --bg-page
- Spinner: --primary color, 48px
- Title: "Dang xac thuc..." (--text-xl, --font-semibold, --text-primary)
- Subtitle: "Vui long doi trong giay lat" (--text-sm, --text-secondary)

### 2.2 Error States

**Layout:** Same centered layout. Replace spinner with error icon.

```
+--------------------------------------+
|          [Icon 64px]                 |
|                                      |
|          {error title}               |
|          {error body}                |
|                                      |
|        [Mo bot]  (primary btn)       |
|                                      |
+--------------------------------------+
```

**Error variants:**

| Case | Icon | Title | Body | CTA |
|------|------|-------|------|-----|
| Expired | clock-x | Link da het han | Link chi co hieu luc trong 10 phut. Hay mo bot de nhan link moi. | Mo bot |
| Invalid | shield-x | Link khong hop le | Vui long kiem tra lai hoac nhan link moi tu bot. | Mo bot |
| Already used | check-circle | Link da duoc su dung | Moi link chi dung duoc mot lan. Hay nhan link moi tu bot. | Mo bot |
| Rate limited | timer | Qua nhieu yeu cau | Ban da yeu cau qua nhieu link. Vui long doi {countdown}. | (disabled) |
| Network | wifi-off | Khong the ket noi | Kiem tra ket noi mang va thu lai. | Thu lai |

- Icon: 64px, --text-secondary (or --expense for security errors)
- Title: --text-xl, --font-semibold
- Body: --text-base, --text-secondary, max-width 400px, text-align center
- CTA button: --primary background, white text, --radius-md, min-width 200px, height 48px

### 2.3 Success

- No visible screen — immediately redirect to /transactions
- JWT stored in memory (access) + httpOnly cookie (refresh)

---

## 3. No Auth Landing Screen

**When:** User visits app.tienvenoidau.com without valid session.

```
+--------------------------------------+
|       [App Logo 80px]                |
|                                      |
|   Tien Ve Noi Dau — Dashboard        |
|                                      |
|   Xem va phan tich giao dich         |
|   cua ban tren web.                  |
|                                      |
|   De dang nhap, mo bot va go         |
|   lenh /dashboard                    |
|                                      |
|   [Mo Telegram Bot]  (primary)       |
|   [Mo Discord Bot]   (secondary)     |
|                                      |
|   Chua co tai khoan?                 |
|   Bat dau tai tienvenoidau.com       |
+--------------------------------------+
```

- Centered layout, max-width 400px
- Logo: 80px, centered
- App name: --text-2xl, --font-bold
- Body: --text-base, --text-secondary
- Instruction: --text-sm, --text-secondary, italic
- Primary CTA: Telegram deep link
- Secondary CTA: Discord invite link
- Footer link: opens landing page

---

## 4. Session Expired Overlay

**When:** JWT access expired AND refresh token rotation fails.

- Semi-transparent overlay over current page (--overlay-blur)
- Centered modal card (--bg-card, --shadow-lg, --radius-lg, max-width 400px)

```
+--------------------------------------+
|       [Clock Icon 48px]              |
|                                      |
|    Phien da het han                  |
|                                      |
|    Vui long nhan link moi tu bot     |
|    de tiep tuc su dung dashboard.    |
|                                      |
|    [Mo bot]  (primary)               |
+--------------------------------------+
```

---

## 5. Bot Message (reference for designer)

**What the bot sends when user types /dashboard:**

```
+--------------------------------------+
| Dashboard cua ban da san sang!       |
|                                      |
| Nhan link duoi day de mo.            |
| Link co hieu luc trong 10 phut.     |
|                                      |
| [Mo Dashboard ->]  (inline button)   |
+--------------------------------------+
```

This is a Telegram/Discord message, not a web screen — but designer should know what triggers the web flow.

---

## 6. Token Specs (for designer context)

| Token | TTL | Note |
|-------|-----|------|
| Magic link | 10 min | Single-use |
| Access JWT | 15 min | In-memory |
| Refresh token | 7 days | httpOnly cookie, rotation |
| Rate limit | 3 links/hour | Per user |

---

## 7. Interactions

| Action | Behavior |
|--------|----------|
| Visit /auth/verify?token=xxx | POST verify, show loading, redirect or error |
| Click "Mo bot" on error | Deep link to Telegram/Discord |
| Click "Thu lai" on network error | Retry POST verify |
| Session expires during use | Overlay appears, blocks interaction |
| Click "Mo bot" on session expired | Deep link, overlay stays |
