"""Vietnamese (default) UI strings for all bot handlers."""

STRINGS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────
    "btn.back":             "← Quay lại",
    "btn.cancel":           "❌ Hủy",
    "btn.confirm_delete":   "❌ Xác nhận xoá",
    "btn.confirm_reset":    "❌ Xác nhận reset",
    "btn.save_done":        "✅ Lưu & xong",
    "btn.skip":             "⏭️ Bỏ qua",
    "cancelled":            "✅ Đã hủy.",
    "session_expired":      "⚠️ Phiên hết hạn. Chạy lại lệnh.",
    "invalid_state":        "⚠️ State không hợp lệ. Dùng lệnh tương ứng để bắt đầu lại.",

    # ── /lang ─────────────────────────────────────────────────
    "lang.title":           "🌐 *Ngôn ngữ / Language*",
    "lang.current":         "Ngôn ngữ hiện tại: *{lang_name}*",
    "lang.choose":          "Chọn ngôn ngữ:",
    "lang.switched":        "✅ Đã chuyển sang *{lang_name}*",

    # ── /manage ───────────────────────────────────────────────
    "mg.title":             "⚙️ *Quản lý mục chi — {month}*",
    "mg.total_budgeted":    "Tổng đã đặt",
    "mg.choose_edit":       "Chọn mục để sửa:",
    "mg.tracking":          "🏷️ chỉ theo dõi",
    "mg.btn_add":           "➕ Thêm mục",
    "mg.btn_edit_budget":   "✏️ Sửa budget",
    "mg.btn_rename":        "📝 Đổi tên",
    "mg.btn_subs":          "📂 Mục con",
    "mg.btn_delete":        "🗑️ Xóa",
    "mg.what_to_do":        "Bạn muốn làm gì?",
    "mg.budgeted":          "💰 Đã đặt · {amount}",
    "mg.spent":             "Đã chi: {amount} ({pct}%)",
    "mg.spent_month":       "Đã chi: {amount} tháng này",
    "mg.tracking_only":     "🏷️ Tracking-only",
    "mg.sub_count":         "📂 {count} mục con",
    # Edit amount
    "mg.edit_amount_prompt": "💰 *{name}* — hiện tại: {current}\nNhập số tiền mới (0 = chuyển sang chỉ theo dõi):",
    "mg.edit_amount_err":   "⚠️ Số tiền không hợp lệ. Thử lại (VD: `3000000`, `3tr`, `500k` hoặc `0`).",
    "mg.updated_amount":    "✅ Đã cập nhật: {name} → *{amount}*",
    "mg.updated_tracking":  "✅ Đã cập nhật: {name} → 🏷️ chỉ theo dõi",
    # Rename
    "mg.rename_prompt":     "✏️ Tên hiện tại: {name}\nNhập tên mới:",
    "mg.renamed":           "✅ Đã đổi tên: {old} → *{new}*",
    # Delete bucket
    "mg.delete_confirm":    "⚠️ *Xóa {name}?*\n\nMục này có {count} giao dịch trong tháng.\nGiao dịch đã phân loại sẽ KHÔNG bị ảnh hưởng.",
    "mg.deleted":           "🗑️ Đã xóa: {name}",
    # Sub-categories
    "mg.subs_empty":        "📂 *{name}* — chưa có mục con.\nSẽ tự tạo khi bạn phân loại giao dịch.",
    "mg.subs_title":        "📂 *Mục con của {name}*",
    "mg.sub_actions_title": "⚙️ *{sub}*\n_(thuộc {parent})_",
    "mg.sub_rename_prompt": "✏️ Tên hiện tại: {name}\nNhập tên mới:",
    "mg.sub_delete_confirm":"⚠️ *Xoá mục con `{sub}`?*\n_(thuộc {parent})_",
    "mg.sub_deleted":       "🗑️ Đã xoá: {name}",
    "mg.btn_cancel_del":    "← Huỷ",
    # Add category
    "mg.add_title":         "➕ *Thêm Mục Mới*\n\nNhập tên mục mới:\n_(VD: 🎮 Gaming, ✈️ Du lịch, 🍕 Ăn uống)_",
    "mg.add_name_empty":    "⚠️ Tên không được để trống. Thử lại:",
    "mg.add_duplicate":     "⚠️ Mục *{name}* đã tồn tại rồi!\nNhập tên khác hoặc gửi /manage để quay lại.",
    "mg.add_mode":          "💰 *{name}* — chọn mode:\n• Nhập số tiền budget (VD: 2000000)\n• Hoặc tap *Chỉ theo dõi* để không đặt budget",
    "mg.btn_track_only":    "🏷️ Chỉ theo dõi",
    "mg.add_amount_err":    "⚠️ Số tiền không hợp lệ. Thử lại (VD: `2000000`, `2tr`, `500k` hoặc `0`).",
    "mg.added_budgeted":    "✅ Đã thêm: *{name}* — {amount}",
    "mg.added_tracking":    "✅ Đã thêm: *{name}* — 🏷️ chỉ theo dõi",
    # Daily cap (Daily Spending bucket)
    "mg.btn_daily_cap":     "⏰ Daily cap",
    "mg.daily_cap_line":    "⏰ Daily cap: {amount}/ngày",
    "mg.daily_cap_prompt":  "⏰ *{name}* — daily cap hiện tại: {current}\nNhập cap mới cho MỖI NGÀY (VD: `100k`, `150000` — `0` để tắt):",
    "mg.daily_cap_err":     "⚠️ Số không hợp lệ. Thử lại (VD: `100k`, `150000` hoặc `0` để tắt).",
    "mg.daily_cap_set":     "✅ Daily cap: {name} → *{amount}/ngày*\n/today và recap cuối ngày sẽ so với cap này.",
    "mg.daily_cap_off":     "✅ Đã tắt daily cap cho {name}.\n/today chỉ hiển thị tổng đã tiêu (không so cap).",

    # ── /allocate ─────────────────────────────────────────────
    "al.title":             "💰 *Đặt hạn mức chi tiêu (tuỳ chọn)*",
    "al.desc":              "Đặt ngân sách cho từng mục để bot cảnh báo khi sắp cạn. Bỏ qua cũng OK — các mục sẽ chạy ở chế độ chỉ theo dõi (ghi lại tổng tiêu).",
    "al.prev_hint":         "Tháng trước ({month}):",
    "al.btn_keep":          "📋 Giữ tháng {month}",
    "al.btn_enter":         "✏️ Nhập budget",
    "al.btn_track_all":     "🏷️ Không đặt — track only",
    "al.btn_add":           "➕ Thêm mục",
    "al.btn_reset":         "🔄 Reset toàn bộ",
    "al.btn_close":         "✅ Xong",
    "al.no_prev":           "⚠️ Không tìm thấy ngân sách tháng {month}. Bắt đầu mới!",
    "al.skip":              "👌 OK, không đặt budget. Các mục vẫn ghi lại tổng tiêu mỗi tháng.\nĐổi ý lúc nào dùng /allocate hoặc /manage.",
    "al.bucket_prompt":     "📊 Mục {idx}/{total}\n\n*{name}* — ngân sách tháng {month}?\n_(VD: `3000000`, `3tr`, `500k` — hoặc `0` để chỉ theo dõi)_",
    "al.btn_skip_bucket":   "⏭️ Bỏ qua (chỉ theo dõi)",
    "al.invalid_number":    "⚠️ Số không hợp lệ. Thử lại (VD: `3000000`, `3tr`, `500k` — hoặc `0` để chỉ theo dõi).",
    "al.negative":          "⚠️ Số phải ≥ 0. `0` = chỉ theo dõi không cap.",
    "al.new_name_prompt":   "📝 Tên mục mới? _(VD: Hanoi Trip)_",
    "al.summary_title":     "✅ *Ngân sách {month}:*",
    "al.summary_total":     "Tổng đã đặt",
    "al.summary_add_more":  "Thêm mục nữa?",
    "al.done_title":        "🎯 *Ngân sách {month} đã lưu!*",
    "al.done_tip":          "_💡 Chỉnh ngân sách cho 1 mục đơn lẻ: dùng /manage (không cần chạy lại /allocate từ đầu)._",
    "al.reset_confirm":     "⚠️ *Reset toàn bộ ngân sách?*\n\nBạn sẽ nhập lại ngân sách từ đầu cho tất cả các mục.",
    "al.edit_title":        "✏️ *Chỉnh ngân sách {month}*\n\nChọn mục cần sửa:",

    # ── /keywords ─────────────────────────────────────────────
    "kw.title":             "🔑 *Keyword Rules*",
    "kw.empty":             "Chưa có rule nào.\n\nKeyword rule giúp bot tự phân loại giao dịch: khi mô tả tx chứa keyword → tự phân loại vào category bạn cấu hình.\n\nVD: `highland` → ☕ Coffee, `winmart` → 🍜 Food",
    "kw.btn_add":           "➕ Thêm rule",
    "kw.list_header":       "📋 *{count} keyword rules* — chọn để sửa/xóa:",
    "kw.add_prompt":        "🔑 Nhập keyword (hoặc nhiều keyword cách nhau bằng dấu phẩy):\n\n_(VD: `grab, gojek, be` → cùng map vào 1 category)_",
    "kw.keyword_empty":     "⚠️ Keyword rỗng. Thử lại hoặc /keywords để hủy.",
    "kw.keyword_too_long":  "⚠️ Keyword quá dài (>60 ký tự): `{kw}`.\nThử lại.",
    "kw.keyword_invalid":   "⚠️ Không có keyword hợp lệ. Thử lại.",
    "kw.no_categories":     "⚠️ Chưa có category nào. Dùng /manage để tạo category trước, rồi quay lại /keywords.",
    "kw.pick_bucket":       "🔑 Keyword{count_label}: {preview}{conflict}\n\nMatch vào category nào?",
    "kw.conflict_header":   "\n\n⚠️ *Đã có rule:*\n{list}\n_Chọn category mới sẽ ghi đè rule cũ._",
    "kw.saved":             "✅ Đã thêm {count} rule → *{bucket}*:",
    "kw.skipped":           "⚠️ {count} rule đã tồn tại sẵn:",
    "kw.rule_detail":       "📋 *Rule:* `{keyword}` → {bucket}\n\nBạn muốn làm gì?",
    "kw.btn_edit_keyword":  "✏️ Đổi keyword",
    "kw.btn_edit_bucket":   "🔄 Đổi category",
    "kw.rule_not_found":    "⚠️ Rule không còn tồn tại.",
    "kw.edit_prompt":       "✏️ Keyword hiện tại: `{keyword}`\n\nNhập keyword mới (1 keyword duy nhất). Muốn add nhiều keyword cùng lúc thì xóa rule này và dùng *➕ Thêm rule*.",
    "kw.edit_single_only":  "⚠️ Chỉ nhận *1 keyword* khi sửa.\nMuốn add nhiều keyword 1 lúc → xóa rule này và dùng *➕ Thêm rule*.",
    "kw.edit_too_long":     "⚠️ Keyword quá dài (>60 ký tự). Thử lại.",
    "kw.edit_duplicate":    "⚠️ Keyword `{keyword}` đã tồn tại (→ {bucket}). Chọn keyword khác.",
    "kw.edited":            "✅ Đã đổi: `{old}` → `{new}`",
    "kw.edit_bucket_prompt":"🔄 *Đổi category cho:* `{keyword}`\n\nHiện tại: {bucket}\nChọn category mới:",
    "kw.bucket_changed":    "✅ Đã chuyển: `{keyword}` → *{bucket}*",
    "kw.delete_confirm":    "⚠️ *Xóa rule này?*\n\n`{keyword}` → {bucket}",
    "kw.btn_confirm_del":   "❌ Xóa",
    "kw.deleted":           "🗑️ Đã xóa rule: `{keyword}`",

    # ── /accounts ─────────────────────────────────────────────
    "ac.unmapped":          "🔍 *Tài khoản chưa liên kết:* `{masked}`\n(nguồn: `{source}`)\n\nBot chưa nhận diện tài khoản/thẻ này. Cài đặt ngay?\n_Còn hiệu lực 24h kể cả khi có tx khác đến._",
    "ac.btn_setup":         "✅ Cài đặt",
    "ac.btn_skip":          "⏭️ Bỏ qua",
    "ac.setup_title":       "📝 *Cài đặt tài khoản mới* — `{masked}`\n\nBước {step}/{total} — Tên hiển thị (vd: `Ngân hàng chính`, `Cake Visa ****8421`):",
    "ac.step_type":         "Bước {step}/{total} — Loại tài khoản? (slug: `{slug}`)",
    "ac.step_limit":        "🪧 Bước {step}/{total} — *Hạn mức thẻ* (VND)? (số, vd `30000000`)",
    "ac.step_outstanding":  "💳 Bước {step}/{total} — *Dư nợ hiện tại* (VND)?\n(số đang nợ trên thẻ ngay lúc cài đặt, vd `3000000`. `0` nếu thẻ chưa dùng / đã trả hết.)",
    "ac.step_statement":    "Bước {step}/{total} — 📅 Ngày chốt sao kê (statement day, 1–28)?\nNgày này quyết định cách gom giao dịch vào kỳ (cashback + báo cáo).\nGõ 'skip' nếu chưa biết — tạm tính theo tháng dương lịch, đặt sau qua /cashback.",
    "ac.step_due":          "Bước {step}/{total} — 📅 Ngày đáo hạn (due day, 1–28)?\nChỉ để nhắc thanh toán. Gõ 'skip' nếu bỏ qua.",
    "ac.setup_done":        "✅ Tài khoản *{name}* đã cài đặt\n  · slug: `{slug}`\n  · loại: {type} · {currency}",
    "ac.list_title":        "🏦 *Tài khoản đã cài đặt*",
    "ac.not_found":         "⚠️ Tài khoản `{slug}` không tồn tại. /accounts để xem danh sách.",
    "ac.currency_mismatch": "⚠️ Loại tiền không khớp: {from_cur} → {to_cur}. Bot không tự convert.",
    "ac.backfilled":        "\n🔁 Đã backfill {count} tx gần đây.",

    # ── /report cashback section ──────────────────────────────
    "rpt.cb_total":         "💰 Tổng hoàn tiền: *{amount}*",
    "rpt.cb_pending":       "  ⏳ Chờ kích hoạt: {amount}",
    "rpt.cb_eligible":      "  ✅ Đã kích hoạt: {amount}",
    "rpt.cb_card_header":   "💳 {name} — kỳ {cycle}",
    "rpt.cb_gate":          "Cổng: {spent}/{gate} {bar} {pct}%",
    "rpt.cb_gate_need":     "⏳ Thiếu {amount} để kích hoạt cashback",
    "rpt.cb_section":       "━━━ 💳 CASHBACK ━━━",

    # ── transaction / budget feedback ─────────────────────────
    "tx.logged":            "✅ Đã ghi *-{amount}*",
    "tx.budget_bar":        "{name}: {spent}/{budget} {bar} {pct}%",
    "tx.over_budget":       "⚠️ *{name}* — vượt {pct}% budget!",
    "tx.near_budget":       "🔔 *{name}* — đã dùng {pct}% budget",

    # ── /cashback ─────────────────────────────────────────────
    "cb.title":             "💳 *Cashback — {name}*",
    "cb.config":            "Rate {rate}% · cổng {gate}/kỳ · {status}",
    "cb.config_on":         "BẬT",
    "cb.config_off":        "TẮT",
    "cb.no_config":         "_Chưa cấu hình._ Dùng *Seed Cake* để tạo nhanh.",
    "cb.cycle_sd":          "📅 Kỳ TT: chốt ngày {sd}{due}",
    "cb.cycle_none":        "📅 Kỳ TT: _theo tháng dương lịch_ (chưa đặt ngày chốt)",
    "cb.cycle_due":         " · đáo hạn ngày {dd}",
    "cb.period_title":      "*Cashback kỳ {cycle}:*",
    "cb.separator":         "─────────────────────",
    "cb.sum_total":         "Σ hoàn kỳ: *{amount}*",
    "cb.sum_eligible":      " · ✅ {amount}",
    "cb.gate_progress":     "Chi tiêu: {spent}/{gate} {bar} {pct}%",
    "cb.gate_need_more":    "⏳ Cần thêm {amount} để kích hoạt",
    "cb.gate_done":         "✅ Đã đủ điều kiện hoàn tiền",
    "cb.no_cards":          "💳 *Cashback*\n\n_Chưa có thẻ tín dụng nào._\nDùng /accounts để thêm thẻ `type=credit` trước.",
    "cb.pick_card":         "💳 *Cashback* — chọn thẻ:",
    "cb.choose":            "Chọn:",
    "cb.no_cashback":       "💳 Thẻ này chưa cấu hình cashback (dùng Seed Cake).",
    "cb.seed_usage":        "Dùng: `/cashback seed cake <cc_id>` (nhiều thẻ credit).",
    "cb.seed_not_credit":   "⚠️ `{id}` không phải thẻ tín dụng (hoặc không tồn tại). Không seed.",
    "cb.seeded":            "🌱 Seeded: {rules} rule, {patterns} pattern, {tiers} tier, config BẬT.\n\n{overview}",
    "cb.seed_done":         "🌱 Seeded: {rules} rule, {patterns} pattern.",
    "cb.recompute_usage":   "Dùng: `/cashback recompute <cc_id> [cycle]`.",
    "cb.recomputed":        "🔄 Recompute {id} ({cycle}): {n} giao dịch.",
    "cb.recomputed_current":"kỳ hiện tại",
    "cb.recompute_btn":     "🔄 Tính lại kỳ hiện tại: {n} giao dịch.",
    "cb.rules_title":       "📋 *Quy tắc* — chọn để sửa/xoá:",
    "cb.rules_empty":       "📋 Chưa có quy tắc nào.",
    "cb.rule_not_found":    "⚠️ Rule không tồn tại (có thể đã xoá).",
    "cb.rule_not_exist":    "⚠️ Rule không tồn tại.",
    "cb.rule_deleted":      "🗑️ Đã xoá rule.",
    "cb.rule_delete_fail":  "⚠️ Không xoá được rule.",
    "cb.rule_delete_confirm": "⚠️ *Xoá rule `{rid}`?*",
    "cb.cfg_prompt":        "⚙️ *Config {id}*\n\nNhập: `<rate> <min_spend> <alert_pct>`\n(VD: `0.20 5000000 0.80`)\n\nHiện tại: rate={rate} · cổng={gate} · alert={alert}%",
    "cb.cfg_need_3":        "⚠️ Cần 3 số: `rate min_spend alert_pct`. Thử lại hoặc /cashback.",
    "cb.cfg_invalid":       "⚠️ Số không hợp lệ. Thử lại.",
    "cb.cfg_rate_range":    "⚠️ rate phải trong (0, 1]. Thử lại.",
    "cb.cfg_updated":       "✅ Cập nhật config {id}.",
    "cb.cyc_title":         "📅 *Kỳ thanh toán {id}*\nHiện: {current}\n\nNhập: `<ngày chốt> [ngày đáo hạn]` (1–28), vd `15 25`.\nNgày chốt quyết định cách gom giao dịch vào kỳ (cashback + /report).\n_Đổi ngày chốt sẽ tự recompute lại cashback kỳ hiện tại._",
    "cb.cyc_need_input":    "⚠️ Cần `<ngày chốt> [ngày đáo hạn]`. Thử lại hoặc /cashback.",
    "cb.cyc_not_number":    "⚠️ Ngày phải là số. Thử lại (vd `15 25`).",
    "cb.cyc_range":         "⚠️ Ngày phải trong 1–28 (tránh 29–31 vì không phải tháng nào cũng có).",
    "cb.cyc_fail":          "⚠️ Không đặt được kỳ cho `{id}` (không phải thẻ tín dụng?).",
    "cb.cyc_done":          "✅ Kỳ TT {id}: chốt ngày {sd}{due}. Đã recompute {n} giao dịch kỳ hiện tại.",
    "cb.mcc_need_input":    "⚠️ Cần `<pattern> <mcc> [label]`. Thử lại hoặc /cashback.",
    "cb.mcc_added":         "✅ Thêm pattern `{pattern}` → MCC {mcc}.",
    "cb.mcc_exists":        "ℹ️ Pattern `{pattern}` → {mcc} đã tồn tại.",
    "cb.add_rule_prompt":   "➕ *Thêm rule*\n\nNhập: `<mcc> <tên> <cap> <max_tx_ngày>`\n(VD: `5814 Nhà hàng 200000 0`)\n\n`0` = unlimited",
    "cb.add_rule_need":     "⚠️ Cần `<mcc> <tên> <cap> <max_tx_ngày>`. Thử lại hoặc /cashback.",
    "cb.add_rule_invalid":  "⚠️ cap/max_tx không hợp lệ. Thử lại.",
    "cb.add_rule_done":     "✅ Thêm rule `{rid}` (MCC {mcc}).",
    "cb.pat_warn":          "   ⚠️ chưa có pattern",
    # Rule field prompts
    "cb.rf_name":           "Nhập tên mới (1–40 ký tự):",
    "cb.rf_cap":            "Nhập cap/kỳ mới (số, vd 200000):",
    "cb.rf_max":            "Nhập max tx/ngày (số nguyên ≥ 0; 0 = không giới hạn):",
    "cb.rf_rate":           "Nhập rate (0–1, vd 0.2 = 20%), hoặc '-' để kế thừa rate thẻ:",
    # Rule detail
    "cb.rule_rate_inherit": "kế thừa thẻ",
    "cb.rule_maxd_unlimited": "không giới hạn",
    "cb.rule_maxd":         "{n} tx/ngày",
    "cb.rule_detail":       "🧾 Rule: {name} (MCC {mcc})\n• Cap/kỳ: {cap}\n• Max tx/ngày: {maxd}\n• Rate: {rate}",
    # Rule validation messages
    "cb.rv_not_found":      "⚠️ Không tìm thấy rule (có thể đã xoá).",
    "cb.rv_name_len":       "⚠️ Tên 1–40 ký tự. Thử lại.",
    "cb.rv_name_ok":        "✅ Đổi tên rule → {name}.",
    "cb.rv_cap_nan":        "⚠️ Cap phải là số ≥ 0 (vd 200000).",
    "cb.rv_cap_ok":         "✅ Cap/kỳ → {amount}.",
    "cb.rv_max_nan":        "⚠️ Nhập số nguyên ≥ 0 (0 = không giới hạn).",
    "cb.rv_max_ok":         "✅ Max tx/ngày → {value}.",
    "cb.rv_rate_inherit_ok":"✅ Rate → kế thừa rate thẻ.",
    "cb.rv_rate_nan":       "⚠️ Rate là số 0–1 (vd 0.2), hoặc '-' để kế thừa thẻ.",
    "cb.rv_rate_range":     "⚠️ Rate phải trong (0, 1]. Vd 0.2 = 20%.",
    "cb.rv_rate_ok":        "✅ Rate → {pct}%.",
    "cb.rv_bad_field":      "⚠️ Trường không hợp lệ.",
    # Learning flow
    "cb.learn_no_kw":       "⚠️ Không thể extract keyword từ mô tả giao dịch.",
    "cb.learn_added":       "✅ Đã thêm",
    "cb.learn_exists":      "đã có",
    "cb.learn_cb_earned":   "💰 +{amount} hoàn tiền!",
    "cb.learn_saved":       "📝 Đã lưu — hoàn tiền sẽ tính khi đủ điều kiện.",
    "cb.learn_error":       "⚠️ Lỗi: {err}",
    "cb.learn_excl":        "❌ `{keyword}` — sẽ tự bỏ qua cho các giao dịch tương tự (không hoàn).",
    "cb.learn_skip":        "❌ Bỏ qua.",
    "cb.learn_wrong":       "✅ Đã sửa — hoàn tiền bị huỷ cho giao dịch này.\n🧠 Đã ghi nhớ: `{keyword}` → không hoàn.\nCác giao dịch tương tự sẽ tự bỏ qua.",
    "cb.learn_voided":      "✅ Đã huỷ hoàn tiền cho giao dịch này.",

    # ── Unknown command ───────────────────────────────────────
    "unknown_command":      "🤔 Không hiểu lệnh này. Gửi /help để xem danh sách lệnh đầy đủ.",

    # ── /help, /start ─────────────────────────────────────────
    "help": (
        "🤖 *Financial Tracking Bot*\n\n"
        "Tự động ghi mọi giao dịch ngân hàng. Bạn chỉ cần phân loại — bot lo phần còn lại.\n\n"
        "*📊 Xem báo cáo:*\n"
        "/report — chi tiêu theo account + category\n"
        "/today — chi tiêu hôm nay\n\n"
        "*⚙️ Quản lý:*\n"
        "/manage — sửa/xóa/thêm categories (kèm ⏰ daily cap)\n"
        "/accounts — danh sách tài khoản\n"
        "/allocate — đặt budget cho từng mục\n"
        "/keywords — rule auto-phân loại theo keyword\n"
        "/cashback — cashback thẻ tín dụng\n\n"
        "*💰 Ghi tay:*\n"
        "/transfer — chuyển tiền giữa các account\n"
        "/cc pay — ghi nhận trả thẻ tín dụng\n\n"
        "*Khác:*\n"
        "/recat — sửa phân loại giao dịch cũ\n"
        "/pending — phân loại giao dịch đang chờ\n"
        "/lang — đổi ngôn ngữ vi/en\n"
        "/cancel — hủy thao tác đang làm dở\n\n"
        "💡 _Mẹo: khi nhập số tiền có thể viết tắt — `500k`, `3tr`, `3tr5`, `1m2`._"
    ),
}
