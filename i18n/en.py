"""English language pack — mirrors keys in i18n/vi.py.

Key parity is enforced by tests/unit/test_i18n_parity.py.
"""

from __future__ import annotations

EN: dict[str, str] = {
    # ── language selection ───────────────────────────────────────
    "lang.detected_prompt": (
        "🌐 Detected language:\n🇬🇧 English\n\n" "Confirm, or choose another language:"
    ),
    "lang.change_prompt": "🌐 Choose language:",
    "lang.changed": "✅ Language changed to English.",
    # ── onboarding ───────────────────────────────────────────────
    "onboard.welcome": "Hi {name}! 👋 I'm your personal finance bot.",
    "onboard.path_prompt": "How would you like to start?",
    "onboard.path_quick": "⚡ Quick start (3 sample categories)",
    "onboard.path_custom": "✏️ Pick my own categories",
    "onboard.done": "All set! Type /help for instructions.",
    # ── categories ───────────────────────────────────────────────
    "cat.pick_prompt": "📂 Pick a category for this transaction:",
    "cat.confirm_tracking": "Logged to {name}: {amount}.",
    "cat.created": "✅ Created category “{name}”.",
    # ── manage ───────────────────────────────────────────────────
    "manage.list_header": "Your categories:",
    "manage.deleted": "🗑️ Deleted category “{name}”.",
    # ── reports ──────────────────────────────────────────────────
    "report.today_header": "You spent today:",
    "report.today_empty": "No transactions today yet.",
    "report.weekly_header": "This week's report:",
    "report.csv_header_date": "Date",
    "report.csv_header_amount": "Amount",
    "report.csv_header_category": "Category",
    "report.csv_header_note": "Note",
    # ── settings ─────────────────────────────────────────────────
    "settings.menu_header": "⚙️ Settings:",
    "settings.lang_label": "🌐 Language",
    "settings.recap_label": "📊 Daily recap",
    # ── upgrade / payment ────────────────────────────────────────
    "upgrade.cta": "🚀 Upgrade to Pro to unlock features.",
    "payment.pending": "Waiting for payment… Scan the QR and I'll log it automatically.",
    "payment.matched": "✅ Received payment of {amount}. Thank you!",
    # ── scheduled jobs ───────────────────────────────────────────
    "job.daily_recap_header": "📊 Today's recap:",
    "job.daily_recap_empty": "No transactions today.",
    "job.reminder_no_activity": "You haven't logged anything today. Want to update?",
    # ── errors ───────────────────────────────────────────────────
    "error.generic": "⚠️ Something went wrong. Please try again.",
    "error.rate_limit": "⏱️ You're going a bit fast — wait a few seconds.",
    "error.pro_only": "🔒 This feature is Pro-only.",
    "error.db": "💾 Database error, please try again later.",
    # ── buttons ──────────────────────────────────────────────────
    "btn.confirm": "✅ Confirm",
    "btn.cancel": "❌ Cancel",
    "btn.skip": "⏭️ Skip",
    "btn.new": "➕ Add new",
    "btn.done": "✅ Done",
    "btn.help": "❓ Help",
    "btn.lang_vi": "🇻🇳 Tiếng Việt",
    "btn.lang_en": "🇬🇧 English",
    # ── formatting ───────────────────────────────────────────────
    "fmt.remaining": "Remaining: {amount}",
    "fmt.spent": "Spent: {amount}",
}
