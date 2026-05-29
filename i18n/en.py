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
    "onboard.welcome_new": (
        "👋 Welcome to MyMoneyWent!\n\n"
        "🎁 You have free Pro until {trial_end}.\n\n"
        "Type /help to see what I can do."
    ),
    "onboard.welcome_back": "👋 Welcome back!",
    "onboard.trial_expired_info": "⏰ Pro trial expired. You're on the Free tier.",
    "onboard.create_fail": "⚠️ Couldn't create your account. Please try again in a minute.",
    # ── categories ───────────────────────────────────────────────
    "cat.pick_prompt": "📂 Pick a category for this transaction:",
    "cat.confirm_tracking": "Logged to {name}: {amount}.",
    "cat.created": "✅ Created category “{name}”.",
    "cat.default.daily_spending": "🛒 Daily Spending",
    "cat.default.saving": "🏦 Saving",
    "cat.default.subscription": "📱 Subscription",
    # ── categorize flow (Zalo numbered picker) ───────────────────
    "categorize.no_categories": "New transaction recorded. You have no active categories for this month.",
    "categorize.pick_prefix": "Pick a category for this transaction:",
    "categorize.pick_invalid": "Invalid number. Pick again:",
    "categorize.confirmed": "Categorized transaction as {name}.",
    "categorize.queue_added": "Added new transaction to categorization queue ({count} transactions).",
    "categorize.expired": "Categorization session expired. I'll ask again on the next transaction.",
    "categorize.direction_in": "in",
    "categorize.direction_out": "out",
    "categorize.no_description": "(no description)",
    "categorize.help_fallback": "Message received. Zalo currently supports /start and numbered category selection.",
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
    "settings.loading": "⏳ Loading settings...",
    "settings.overview_title": "⚙️ Settings",
    "settings.row_webhook_configured": "🔗 Webhook: configured ✓ (created {created}) · ...{suffix}",
    "settings.row_webhook_configured_no_suffix": "🔗 Webhook: configured ✓ (created {created})",
    "settings.row_webhook_missing": "🔗 Webhook: not configured",
    "settings.row_email": "📧 Email: {email}",
    "settings.row_timezone": "🌐 Timezone: {tz}",
    "settings.row_recap_on": "🌙 Daily recap: ✅ On",
    "settings.row_recap_off": "🌙 Daily recap: ⛔ Off",
    "settings.row_plan_free": "📋 Plan: Free",
    "settings.row_plan_trial": "📋 Plan: {plan} (trial, {days} days left)",
    "settings.row_plan_active": "📋 Plan: {plan}",
    "settings.row_plan_expired": "📋 Plan: {plan} (expired)",
    "settings.row_language_vi": "🌐 Language: 🇻🇳 Tiếng Việt",
    "settings.row_language_en": "🌐 Language: 🇬🇧 English",
    "settings.btn_regen": "🔄 Regenerate URL",
    "settings.btn_tz": "🌐 Change timezone",
    "settings.btn_recap_off": "🌙 Turn off recap",
    "settings.btn_recap_on": "🌙 Turn on recap",
    "settings.btn_upgrade": "⬆️ Upgrade",
    "settings.btn_lang": "🌐 Change language",
    "settings.lang_pick_prompt": "🌐 Choose language:",
    "settings.tz_prompt": "Enter a timezone (e.g. Asia/Ho_Chi_Minh, Asia/Tokyo):",
    "settings.tz_invalid": (
        "⚠️ Invalid timezone. Examples: Asia/Ho_Chi_Minh, Asia/Tokyo, Europe/London."
    ),
    "settings.tz_changed": "✅ Timezone changed to {tz}.",
    "settings.recap_toggled_on": "✅ Daily recap enabled.",
    "settings.recap_toggled_off": "✅ Daily recap disabled.",
    "settings.regen_success": (
        "✅ New webhook URL generated. Update SePay with this token (shown once):\n\n{token}"
    ),
    "settings.regen_fail": "⚠️ Failed to generate new URL.",
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
