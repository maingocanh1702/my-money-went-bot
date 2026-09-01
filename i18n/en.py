"""English UI strings for all bot handlers."""

STRINGS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────
    "btn.back":             "← Back",
    "btn.cancel":           "❌ Cancel",
    "btn.confirm_delete":   "❌ Confirm delete",
    "btn.confirm_reset":    "❌ Confirm reset",
    "btn.save_done":        "✅ Save & done",
    "btn.skip":             "⏭️ Skip",
    "cancelled":            "✅ Cancelled.",
    "session_expired":      "⚠️ Session expired. Run the command again.",
    "invalid_state":        "⚠️ Invalid state. Use the command to start over.",

    # ── /lang ─────────────────────────────────────────────────
    "lang.title":           "🌐 *Language / Ngôn ngữ*",
    "lang.current":         "Current language: *{lang_name}*",
    "lang.choose":          "Choose language:",
    "lang.switched":        "✅ Switched to *{lang_name}*",

    # ── /manage ───────────────────────────────────────────────
    "mg.title":             "⚙️ *Manage Categories — {month}*",
    "mg.total_budgeted":    "Total budgeted",
    "mg.choose_edit":       "Select a category to edit:",
    "mg.tracking":          "🏷️ tracking",
    "mg.btn_add":           "➕ Add category",
    "mg.btn_edit_budget":   "✏️ Edit budget",
    "mg.btn_rename":        "📝 Rename",
    "mg.btn_subs":          "📂 Sub-categories",
    "mg.btn_delete":        "🗑️ Delete",
    "mg.what_to_do":        "What would you like to do?",
    "mg.budgeted":          "💰 Budgeted · {amount}",
    "mg.spent":             "Spent: {amount} ({pct}%)",
    "mg.spent_month":       "Spent: {amount} this month",
    "mg.tracking_only":     "🏷️ Tracking-only",
    "mg.sub_count":         "📂 {count} sub-categories",
    # Edit amount
    "mg.edit_amount_prompt": "💰 *{name}* — current: {current}\nEnter new amount (0 = switch to tracking-only):",
    "mg.edit_amount_err":   "⚠️ Invalid amount. Try again (e.g. `3000000`, `3tr`, `500k` or `0`).",
    "mg.updated_amount":    "✅ Updated: {name} → *{amount}*",
    "mg.updated_tracking":  "✅ Updated: {name} → 🏷️ tracking-only",
    # Rename
    "mg.rename_prompt":     "✏️ Current name: {name}\nEnter new name:",
    "mg.renamed":           "✅ Renamed: {old} → *{new}*",
    # Delete bucket
    "mg.delete_confirm":    "⚠️ *Delete {name}?*\n\nThis category has {count} transactions this month.\nExisting transactions will NOT be affected.",
    "mg.deleted":           "🗑️ Deleted: {name}",
    # Sub-categories
    "mg.subs_empty":        "📂 *{name}* — no sub-categories yet.\nThey'll be created when you categorize transactions.",
    "mg.subs_title":        "📂 *Sub-categories of {name}*",
    "mg.sub_actions_title": "⚙️ *{sub}*\n_(under {parent})_",
    "mg.sub_rename_prompt": "✏️ Current name: {name}\nEnter new name:",
    "mg.sub_delete_confirm":"⚠️ *Delete sub-category `{sub}`?*\n_(under {parent})_",
    "mg.sub_deleted":       "🗑️ Deleted: {name}",
    "mg.btn_cancel_del":    "← Cancel",
    # Add category
    "mg.add_title":         "➕ *Add New Category*\n\nEnter new category name:\n_(e.g. 🎮 Gaming, ✈️ Travel, 🍕 Food)_",
    "mg.add_name_empty":    "⚠️ Name cannot be empty. Try again:",
    "mg.add_duplicate":     "⚠️ Category *{name}* already exists!\nEnter a different name or send /manage to go back.",
    "mg.add_mode":          "💰 *{name}* — choose mode:\n• Enter budget amount (e.g. 2000000)\n• Or tap *Track only* to monitor without budget",
    "mg.btn_track_only":    "🏷️ Track only",
    "mg.add_amount_err":    "⚠️ Invalid amount. Try again (e.g. `2000000`, `2tr`, `500k` or `0`).",
    "mg.added_budgeted":    "✅ Added: *{name}* — {amount}",
    "mg.added_tracking":    "✅ Added: *{name}* — 🏷️ tracking-only",
    # Daily cap (Daily Spending bucket)
    "mg.btn_daily_cap":     "⏰ Daily cap",
    "mg.daily_cap_line":    "⏰ Daily cap: {amount}/day",
    "mg.daily_cap_prompt":  "⏰ *{name}* — current daily cap: {current}\nEnter the new PER-DAY cap (e.g. `100k`, `150000` — `0` to turn off):",
    "mg.daily_cap_err":     "⚠️ Invalid number. Try again (e.g. `100k`, `150000` or `0` to turn off).",
    "mg.daily_cap_set":     "✅ Daily cap: {name} → *{amount}/day*\n/today and the nightly recap compare against this cap.",
    "mg.daily_cap_off":     "✅ Daily cap turned off for {name}.\n/today will just show the day's total (no cap comparison).",

    # ── /allocate ─────────────────────────────────────────────
    "al.title":             "💰 *Set spending limits (optional)*",
    "al.desc":              "Set a budget for each category so the bot warns you when you're running low. Skip is fine — categories will run in tracking mode (just recording totals).",
    "al.prev_hint":         "Last month ({month}):",
    "al.btn_keep":          "📋 Keep {month}",
    "al.btn_enter":         "✏️ Enter budget",
    "al.btn_track_all":     "🏷️ No budget — track only",
    "al.btn_add":           "➕ Add category",
    "al.btn_reset":         "🔄 Reset all",
    "al.btn_close":         "✅ Done",
    "al.no_prev":           "⚠️ No budget found for {month}. Starting fresh!",
    "al.skip":              "👌 OK, no budget set. Categories will still track monthly spending.\nChange your mind anytime with /allocate or /manage.",
    "al.bucket_prompt":     "📊 Item {idx}/{total}\n\n*{name}* — budget for {month}?\n_(e.g. `3000000`, `3tr`, `500k` — or `0` for tracking-only)_",
    "al.btn_skip_bucket":   "⏭️ Skip (tracking-only)",
    "al.invalid_number":    "⚠️ Invalid number. Try again (e.g. `3000000`, `3tr`, `500k`, or `0` for tracking-only).",
    "al.negative":          "⚠️ Number must be ≥ 0. `0` = tracking-only with no cap.",
    "al.new_name_prompt":   "📝 New category name? _(e.g. Hanoi Trip)_",
    "al.summary_title":     "✅ *Budget for {month}:*",
    "al.summary_total":     "Total budgeted",
    "al.summary_add_more":  "Add more?",
    "al.done_title":        "🎯 *Budget {month} saved!*",
    "al.done_tip":          "_💡 To adjust a single category: use /manage (no need to re-run /allocate from scratch)._",
    "al.reset_confirm":     "⚠️ *Reset all budgets?*\n\nYou'll re-enter budgets from scratch for all categories.",
    "al.edit_title":        "✏️ *Edit budget {month}*\n\nSelect a category to edit:",

    # ── /keywords ─────────────────────────────────────────────
    "kw.title":             "🔑 *Keyword Rules*",
    "kw.empty":             "No rules yet.\n\nKeyword rules auto-categorize transactions: when a tx description contains a keyword → auto-categorize to the configured category.\n\ne.g. `highland` → ☕ Coffee, `winmart` → 🍜 Food",
    "kw.btn_add":           "➕ Add rule",
    "kw.list_header":       "📋 *{count} keyword rules* — select to edit/delete:",
    "kw.add_prompt":        "🔑 Enter keyword (or multiple separated by commas):\n\n_(e.g. `grab, gojek, be` → all map to 1 category)_",
    "kw.keyword_empty":     "⚠️ Empty keyword. Try again or /keywords to cancel.",
    "kw.keyword_too_long":  "⚠️ Keyword too long (>60 chars): `{kw}`.\nTry again.",
    "kw.keyword_invalid":   "⚠️ No valid keywords. Try again.",
    "kw.no_categories":     "⚠️ No categories yet. Use /manage to create categories first, then come back to /keywords.",
    "kw.pick_bucket":       "🔑 Keyword{count_label}: {preview}{conflict}\n\nMatch to which category?",
    "kw.conflict_header":   "\n\n⚠️ *Existing rules:*\n{list}\n_Choosing a new category will overwrite._",
    "kw.saved":             "✅ Added {count} rule(s) → *{bucket}*:",
    "kw.skipped":           "⚠️ {count} rule(s) already existed:",
    "kw.rule_detail":       "📋 *Rule:* `{keyword}` → {bucket}\n\nWhat would you like to do?",
    "kw.btn_edit_keyword":  "✏️ Edit keyword",
    "kw.btn_edit_bucket":   "🔄 Change category",
    "kw.rule_not_found":    "⚠️ Rule no longer exists.",
    "kw.edit_prompt":       "✏️ Current keyword: `{keyword}`\n\nEnter new keyword (single keyword only). To add multiple keywords at once, delete this rule and use *➕ Add rule*.",
    "kw.edit_single_only":  "⚠️ Only *1 keyword* when editing.\nTo add multiple → delete this rule and use *➕ Add rule*.",
    "kw.edit_too_long":     "⚠️ Keyword too long (>60 chars). Try again.",
    "kw.edit_duplicate":    "⚠️ Keyword `{keyword}` already exists (→ {bucket}). Choose a different one.",
    "kw.edited":            "✅ Changed: `{old}` → `{new}`",
    "kw.edit_bucket_prompt":"🔄 *Change category for:* `{keyword}`\n\nCurrent: {bucket}\nSelect new category:",
    "kw.bucket_changed":    "✅ Moved: `{keyword}` → *{bucket}*",
    "kw.delete_confirm":    "⚠️ *Delete this rule?*\n\n`{keyword}` → {bucket}",
    "kw.btn_confirm_del":   "❌ Delete",
    "kw.deleted":           "🗑️ Deleted rule: `{keyword}`",

    # ── /accounts ─────────────────────────────────────────────
    "ac.unmapped":          "🔍 *Unmapped account:* `{masked}`\n(source: `{source}`)\n\nBot doesn't recognize this account/card. Set up now?\n_Valid for 24h even if other tx arrive._",
    "ac.btn_setup":         "✅ Set up",
    "ac.btn_skip":          "⏭️ Skip",
    "ac.setup_title":       "📝 *Set up new account* — `{masked}`\n\nStep {step}/{total} — Display name (e.g. `TCB Spending`, `Cake Visa ****8421`):",
    "ac.step_type":         "Step {step}/{total} — Account type? (slug: `{slug}`)",
    "ac.step_limit":        "🪧 Step {step}/{total} — *Credit limit* (VND)? (e.g. `30000000`)",
    "ac.step_outstanding":  "💳 Step {step}/{total} — *Current outstanding* (VND)?\n(Amount owed right now, e.g. `3000000`. `0` if card is unused / fully paid.)",
    "ac.step_statement":    "Step {step}/{total} — 📅 Statement day (1–28)?\nThis determines how transactions are grouped per cycle (cashback + reports).\nType 'skip' if unsure — defaults to calendar month, changeable later via /cashback.",
    "ac.step_due":          "Step {step}/{total} — 📅 Due day (1–28)?\nFor payment reminders only. Type 'skip' to skip.",
    "ac.setup_done":        "✅ Account *{name}* set up\n  · slug: `{slug}`\n  · type: {type} · {currency}",
    "ac.list_title":        "🏦 *Accounts*",
    "ac.not_found":         "⚠️ Account `{slug}` not found. Use /accounts to see the list.",
    "ac.currency_mismatch": "⚠️ Currency mismatch: {from_cur} → {to_cur}. Bot cannot auto-convert.",
    "ac.backfilled":        "\n🔁 Backfilled {count} recent tx.",

    # ── /report cashback section ──────────────────────────────
    "rpt.cb_total":         "💰 Total cashback: *{amount}*",
    "rpt.cb_pending":       "  ⏳ Pending activation: {amount}",
    "rpt.cb_eligible":      "  ✅ Activated: {amount}",
    "rpt.cb_card_header":   "💳 {name} — cycle {cycle}",
    "rpt.cb_gate":          "Gate: {spent}/{gate} {bar} {pct}%",
    "rpt.cb_gate_need":     "⏳ Need {amount} more to activate cashback",
    "rpt.cb_section":       "━━━ 💳 CASHBACK ━━━",

    # ── transaction / budget feedback ─────────────────────────
    "tx.logged":            "✅ Logged *-{amount}*",
    "tx.budget_bar":        "{name}: {spent}/{budget} {bar} {pct}%",
    "tx.over_budget":       "⚠️ *{name}* — {pct}% over budget!",
    "tx.near_budget":       "🔔 *{name}* — {pct}% of budget used",

    # ── /cashback ─────────────────────────────────────────────
    "cb.title":             "💳 *Cashback — {name}*",
    "cb.config":            "Rate {rate}% · gate {gate}/cycle · {status}",
    "cb.config_on":         "ON",
    "cb.config_off":        "OFF",
    "cb.no_config":         "_Not configured._ Use *Seed Cake* to quick-setup.",
    "cb.cycle_sd":          "📅 Billing: statement day {sd}{due}",
    "cb.cycle_none":        "📅 Billing: _calendar month_ (no statement day set)",
    "cb.cycle_due":         " · due day {dd}",
    "cb.period_title":      "*Cashback cycle {cycle}:*",
    "cb.separator":         "─────────────────────",
    "cb.sum_total":         "Σ cycle total: *{amount}*",
    "cb.sum_eligible":      " · ✅ {amount}",
    "cb.gate_progress":     "Spend: {spent}/{gate} {bar} {pct}%",
    "cb.gate_need_more":    "⏳ Need {amount} more to activate",
    "cb.gate_done":         "✅ Activation gate reached",
    "cb.no_cards":          "💳 *Cashback*\n\n_No credit cards found._\nUse /accounts to add a `type=credit` card first.",
    "cb.pick_card":         "💳 *Cashback* — select card:",
    "cb.choose":            "Choose:",
    "cb.no_cashback":       "💳 No cashback config for this card (use Seed Cake).",
    "cb.seed_usage":        "Usage: `/cashback seed cake <cc_id>` (multiple credit cards).",
    "cb.seed_not_credit":   "⚠️ `{id}` is not a credit card (or doesn't exist). Cannot seed.",
    "cb.seeded":            "🌱 Seeded: {rules} rules, {patterns} patterns, {tiers} tiers, config ON.\n\n{overview}",
    "cb.seed_done":         "🌱 Seeded: {rules} rules, {patterns} patterns.",
    "cb.recompute_usage":   "Usage: `/cashback recompute <cc_id> [cycle]`.",
    "cb.recomputed":        "🔄 Recompute {id} ({cycle}): {n} transactions.",
    "cb.recomputed_current":"current cycle",
    "cb.recompute_btn":     "🔄 Recomputed current cycle: {n} transactions.",
    "cb.rules_title":       "📋 *Rules* — select to edit/delete:",
    "cb.rules_empty":       "📋 No rules configured.",
    "cb.rule_not_found":    "⚠️ Rule not found (may have been deleted).",
    "cb.rule_not_exist":    "⚠️ Rule does not exist.",
    "cb.rule_deleted":      "🗑️ Rule deleted.",
    "cb.rule_delete_fail":  "⚠️ Could not delete rule.",
    "cb.rule_delete_confirm": "⚠️ *Delete rule `{rid}`?*",
    "cb.cfg_prompt":        "⚙️ *Config {id}*\n\nEnter: `<rate> <min_spend> <alert_pct>`\n(e.g. `0.20 5000000 0.80`)\n\nCurrent: rate={rate} · gate={gate} · alert={alert}%",
    "cb.cfg_need_3":        "⚠️ Need 3 numbers: `rate min_spend alert_pct`. Try again or /cashback.",
    "cb.cfg_invalid":       "⚠️ Invalid numbers. Try again.",
    "cb.cfg_rate_range":    "⚠️ Rate must be in (0, 1]. Try again.",
    "cb.cfg_updated":       "✅ Updated config {id}.",
    "cb.cyc_title":         "📅 *Billing cycle {id}*\nCurrent: {current}\n\nEnter: `<statement_day> [due_day]` (1–28), e.g. `15 25`.\nStatement day determines how transactions are grouped per cycle (cashback + /report).\n_Changing statement day will recompute cashback for the current cycle._",
    "cb.cyc_need_input":    "⚠️ Need `<statement_day> [due_day]`. Try again or /cashback.",
    "cb.cyc_not_number":    "⚠️ Day must be a number. Try again (e.g. `15 25`).",
    "cb.cyc_range":         "⚠️ Day must be 1–28 (avoid 29–31 as not all months have them).",
    "cb.cyc_fail":          "⚠️ Could not set billing cycle for `{id}` (not a credit card?).",
    "cb.cyc_done":          "✅ Billing {id}: statement day {sd}{due}. Recomputed {n} transactions for current cycle.",
    "cb.mcc_need_input":    "⚠️ Need `<pattern> <mcc> [label]`. Try again or /cashback.",
    "cb.mcc_added":         "✅ Added pattern `{pattern}` → MCC {mcc}.",
    "cb.mcc_exists":        "ℹ️ Pattern `{pattern}` → {mcc} already exists.",
    "cb.add_rule_prompt":   "➕ *Add rule*\n\nEnter: `<mcc> <name> <cap> <max_tx_day>`\n(e.g. `5814 Restaurant 200000 0`)\n\n`0` = unlimited",
    "cb.add_rule_need":     "⚠️ Need `<mcc> <name> <cap> <max_tx_day>`. Try again or /cashback.",
    "cb.add_rule_invalid":  "⚠️ Invalid cap/max_tx. Try again.",
    "cb.add_rule_done":     "✅ Added rule `{rid}` (MCC {mcc}).",
    "cb.pat_warn":          "   ⚠️ no patterns configured",
    # Rule field prompts
    "cb.rf_name":           "Enter new name (1–40 chars):",
    "cb.rf_cap":            "Enter new cap/cycle (number, e.g. 200000):",
    "cb.rf_max":            "Enter max tx/day (integer ≥ 0; 0 = unlimited):",
    "cb.rf_rate":           "Enter rate (0–1, e.g. 0.2 = 20%), or '-' to inherit card rate:",
    # Rule detail
    "cb.rule_rate_inherit": "inherited",
    "cb.rule_maxd_unlimited": "unlimited",
    "cb.rule_maxd":         "{n} tx/day",
    "cb.rule_detail":       "🧾 Rule: {name} (MCC {mcc})\n• Cap/cycle: {cap}\n• Max tx/day: {maxd}\n• Rate: {rate}",
    # Rule validation messages
    "cb.rv_not_found":      "⚠️ Rule not found (may have been deleted).",
    "cb.rv_name_len":       "⚠️ Name must be 1–40 chars. Try again.",
    "cb.rv_name_ok":        "✅ Renamed rule → {name}.",
    "cb.rv_cap_nan":        "⚠️ Cap must be a number ≥ 0 (e.g. 200000).",
    "cb.rv_cap_ok":         "✅ Cap/cycle → {amount}.",
    "cb.rv_max_nan":        "⚠️ Enter integer ≥ 0 (0 = unlimited).",
    "cb.rv_max_ok":         "✅ Max tx/day → {value}.",
    "cb.rv_rate_inherit_ok":"✅ Rate → inheriting card rate.",
    "cb.rv_rate_nan":       "⚠️ Rate must be 0–1 (e.g. 0.2), or '-' to inherit card rate.",
    "cb.rv_rate_range":     "⚠️ Rate must be in (0, 1]. E.g. 0.2 = 20%.",
    "cb.rv_rate_ok":        "✅ Rate → {pct}%.",
    "cb.rv_bad_field":      "⚠️ Invalid field.",
    # Learning flow
    "cb.learn_no_kw":       "⚠️ Cannot extract keyword from transaction description.",
    "cb.learn_added":       "✅ Added",
    "cb.learn_exists":      "already exists",
    "cb.learn_cb_earned":   "💰 +{amount} cashback!",
    "cb.learn_saved":       "📝 Saved — cashback will apply when conditions are met.",
    "cb.learn_error":       "⚠️ Error: {err}",
    "cb.learn_excl":        "❌ `{keyword}` — will auto-skip similar transactions (no cashback).",
    "cb.learn_skip":        "❌ Skipped.",
    "cb.learn_wrong":       "✅ Fixed — cashback voided for this transaction.\n🧠 Remembered: `{keyword}` → no cashback.\nSimilar transactions will be auto-skipped.",
    "cb.learn_voided":      "✅ Cashback voided for this transaction.",

    # ── Unknown command ───────────────────────────────────────
    "unknown_command":      "🤔 Unknown command. Send /help for the full command list.",

    # ── /help, /start ─────────────────────────────────────────
    "help": (
        "🤖 *Financial Tracking Bot*\n\n"
        "Every bank transaction is logged automatically. You just categorize — the bot does the rest.\n\n"
        "*📊 Reports:*\n"
        "/report — spending by account + category\n"
        "/today — today's spending\n\n"
        "*⚙️ Manage:*\n"
        "/manage — add/rename/delete categories (incl. ⏰ daily cap)\n"
        "/accounts — list accounts\n"
        "/allocate — set a budget per category\n"
        "/keywords — auto-categorize rules\n"
        "/cashback — credit-card cashback\n\n"
        "*💰 Manual entries:*\n"
        "/transfer — transfer between accounts\n"
        "/cc pay — record a credit-card payment\n\n"
        "*Other:*\n"
        "/recat — re-categorize a past transaction\n"
        "/pending — categorize queued transactions\n"
        "/lang — switch language vi/en\n"
        "/cancel — abort the current flow\n\n"
        "💡 _Tip: amounts accept Vietnamese shorthand — `500k`, `3tr`, `3tr5`, `1m2`._"
    ),
}
