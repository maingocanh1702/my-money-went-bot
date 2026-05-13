# Tiền Về Nơi Đâu — Business Requirements Document (BRD)

> **Version:** v3.1.0
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-10
> **Trạng thái:** Draft (consolidated + 3 round revisions)
>
> **🌐 SCOPE NOTE (updated 2026-05-10):** BRD này là **canonical spec cho 🇻🇳 thị trường Việt Nam** (Tiền Về Nơi Đâu branding). Transaction capture stack (SePay webhook + email parsing bank emails TCB/Cake/ACB/STB/BIDV/MB), 3 personas (Minh/Linh/Hùng+), pricing tiers ($4 Pro / $9 Business) đều là **VN-specific**. **Global market** có BRD riêng — [brd-en.md](./brd-en.md) (My Money Went branding) — với capture stack độc lập (Plaid/TrueLayer/Tink + Stripe/PayPal/Shopify/Etsy APIs) và ICP riêng (e-commerce solopreneur). **Channel architecture là shared:** cả 2 market đều target Telegram + Discord + Messenger + các platform sau qua `messenger.send()` interface. Chỉ **Zalo là VN-exclusive** (Phase 3+). Hai track chia sẻ Phase 1-2 multi-tenant foundation; tách hướng từ Phase 3+. Đọc [docs/market-strategy-overview.md](./market-strategy-overview.md) trước để hiểu cách 2 track coexist. Strategic background cho global track: [./strategic-pivot-global.md](./strategic-pivot-global.md).
>
> **🏗️ CODE STRUCTURE:** Per [ADR-0001](./adr/0001-monorepo-not-split-repos.md), VN code lives at `markets/vn/` (capture/payment/pricing/channels), shared foundation tại `core/` (messenger, auth, db, tenant_context). VN-specific implementations (SePay, VN bank parsers, VietQR, Zalo) đi vào `markets/vn/`. KHÔNG fork repo riêng — single monorepo, adapter pattern.
