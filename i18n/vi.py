"""Vietnamese language pack.

Keep keys flat (no nesting) — namespaced via `prefix.subkey` dotted strings.
Every key here MUST also exist in i18n/en.py (enforced by parity test).

Prefix conventions (see feature-i18n.md §4):
    onboard.*   — welcome, path select, wizard steps
    cat.*       — category picker, confirmation, inline create
    manage.*    — /manage CRUD screens
    report.*    — /status, /today, daily recap, /weekly
    settings.*  — settings view + change screens
    upgrade.*   — pricing, plan display, upgrade flow
    payment.*   — pending payment, QR, matched confirmation
    job.*       — scheduled job messages (recap, reminder)
    error.*     — generic, rate limit, pro-only, DB
    btn.*       — button labels
    fmt.*       — currency / number formatting helpers
    lang.*      — language selection screens
"""

from __future__ import annotations

VI: dict[str, str] = {
    # ── language selection (onboarding step) ─────────────────────
    "lang.detected_prompt": (
        "🌐 Ngôn ngữ đã được nhận diện:\n🇻🇳 Tiếng Việt\n\n" "Đúng rồi, hoặc chọn ngôn ngữ khác:"
    ),
    "lang.change_prompt": "🌐 Chọn ngôn ngữ:",
    "lang.changed": "✅ Đã đổi ngôn ngữ sang Tiếng Việt.",
    # ── onboarding ───────────────────────────────────────────────
    "onboard.welcome": "Xin chào {name}! 👋 Mình là bot quản lý chi tiêu cá nhân.",
    "onboard.path_prompt": "Bạn muốn bắt đầu kiểu nào?",
    "onboard.path_quick": "⚡ Bắt đầu nhanh (3 danh mục mẫu)",
    "onboard.path_custom": "✏️ Tự chọn danh mục",
    "onboard.done": "Xong! Gõ /help để xem hướng dẫn.",
    # ── categories ───────────────────────────────────────────────
    "cat.pick_prompt": "📂 Chọn nhóm chi tiêu cho khoản này:",
    "cat.confirm_tracking": "Đã ghi vào {name}: {amount}.",
    "cat.created": "✅ Đã tạo nhóm “{name}”.",
    # ── manage ───────────────────────────────────────────────────
    "manage.list_header": "Danh mục của bạn:",
    "manage.deleted": "🗑️ Đã xoá nhóm “{name}”.",
    # ── reports ──────────────────────────────────────────────────
    "report.today_header": "Hôm nay bạn đã chi:",
    "report.today_empty": "Hôm nay chưa có giao dịch nào.",
    "report.weekly_header": "Báo cáo tuần này:",
    "report.csv_header_date": "Ngày",
    "report.csv_header_amount": "Số tiền",
    "report.csv_header_category": "Danh mục",
    "report.csv_header_note": "Ghi chú",
    # ── settings ─────────────────────────────────────────────────
    "settings.menu_header": "⚙️ Cài đặt:",
    "settings.lang_label": "🌐 Ngôn ngữ",
    "settings.recap_label": "📊 Tóm tắt hàng ngày",
    # ── upgrade / payment ────────────────────────────────────────
    "upgrade.cta": "🚀 Nâng cấp lên Pro để mở khoá tính năng.",
    "payment.pending": "Đang chờ thanh toán… Quét QR và mình sẽ ghi nhận tự động.",
    "payment.matched": "✅ Đã nhận thanh toán {amount}. Cảm ơn bạn!",
    # ── scheduled jobs ───────────────────────────────────────────
    "job.daily_recap_header": "📊 Tóm tắt hôm nay:",
    "job.daily_recap_empty": "Hôm nay không có giao dịch nào.",
    "job.reminder_no_activity": "Bạn chưa ghi nhận chi tiêu nào hôm nay. Cập nhật chút nhé?",
    # ── errors ───────────────────────────────────────────────────
    "error.generic": "⚠️ Có lỗi xảy ra. Vui lòng thử lại.",
    "error.rate_limit": "⏱️ Bạn thao tác hơi nhanh, đợi vài giây rồi thử lại.",
    "error.pro_only": "🔒 Tính năng này dành cho gói Pro.",
    "error.db": "💾 Lỗi cơ sở dữ liệu, vui lòng thử lại sau.",
    # ── buttons ──────────────────────────────────────────────────
    "btn.confirm": "✅ Xác nhận",
    "btn.cancel": "❌ Huỷ",
    "btn.skip": "⏭️ Bỏ qua",
    "btn.new": "➕ Thêm mới",
    "btn.done": "✅ Xong",
    "btn.help": "❓ Trợ giúp",
    "btn.lang_vi": "🇻🇳 Tiếng Việt",
    "btn.lang_en": "🇬🇧 English",
    # ── formatting ───────────────────────────────────────────────
    "fmt.remaining": "Còn lại: {amount}",
    "fmt.spent": "Đã chi: {amount}",
}
