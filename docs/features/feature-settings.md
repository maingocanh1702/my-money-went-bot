<!-- autopilot:meta
feature_id: F07
branch: feat/F07-settings
phase: 2
wave: 1
risk_tier: P1
depends_on: []
be_doc: docs/features/BE/feature-settings-tech.md
-->

# Feature: Settings — /settings (F07)

> **Version:** v1.2.0
> **Ngày tạo:** 2026-05-08
> **Trạng thái:** Ready (autopilot template migrated 2026-05-12)
> **Owner:** Founder (dev)
> **Phase:** Phase 2 (Tuần 3-4)
> **Tham chiếu:** [PRD-vi v1.7.1 §3.7](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [Feature: i18n](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md)

---

## 1. Mô tả

User quản lý account settings qua `/settings`: xem/regenerate webhook URL, xem inbound email, đổi timezone, bật/tắt daily recap, xem plan info + upgrade.

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | `/settings` | Hiện tổng quan settings |
| 2 | User | Regenerate webhook URL | URL mới, cũ invalidate ngay |
| 3 | User | Xem inbound email | Hiện `u{id}@in.mymoneywent.com` |
| 4 | User | Đổi timezone | Recalculate scheduled jobs |
| 5 | User | Tắt daily recap | Update scheduled_jobs.enabled |
| 6 | User | Xem plan info | Plan + trial status + upgrade option |
| 7 | User | Bấm Upgrade từ settings | Redirect tới `/upgrade` flow |
| 8 | User | Xem bank connections | List các bank đã kết nối |
| 9 | User | Đổi ngôn ngữ | Hiện 2 button [🇻🇳 Tiếng Việt] [🇬🇧 English] → update locale |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Security | Regenerate URL → SePay cũ gửi webhook | URL cũ 404, user cần update SePay |
| 2 | Cross-Feature | Đổi timezone → recap đã schedule | Cancel old job, create new |
| 3 | Data Integrity | Timezone invalid (e.g. "ABC") | Reject + list valid timezones |
| 4 | Cross-Feature | Toggle recap OFF → ON | Re-create scheduled job |
| 5 | Security | User xem settings user khác | WHERE user_id scope enforce |
| 6 | Data Integrity | Webhook URL chứa trong message history | Cũ invalidate, không reuse |
| 7 | Cross-Feature | Regenerate URL khi có pending payment | Pending payment không bị affect |
| 8 | Data Integrity | inbound_email khi user đã setup forwarding | Email mới → auto-generate mới, notify |
| 9 | Concurrency | 2 regenerate cùng lúc | Last write wins, UNIQUE constraint |
| 10 | Cross-Feature | Settings trên Messenger | Persistent menu "⚙️ Settings" |
| 11 | Cross-Feature | Settings trên Discord | /settings slash command |

---

## 3. Screens & States

### Settings Overview
- **Loading:** `t(locale, 'settings.loading')` — "⏳ Đang tải settings..."
- **Ready (vi):**
```
⚙️ Cài đặt

🔗 Webhook: ...{last6chars}
📧 Email: u42@in.mymoneywent.com
🌐 Timezone: Asia/Ho_Chi_Minh
🌙 Tóm tắt ngày: ✅ Bật
📋 Gói: Pro (trial, còn 5 ngày)
🌐 Ngôn ngữ: 🇻🇳 Tiếng Việt

[🔄 Regenerate URL] [🌐 Đổi timezone]
[🌙 Tắt recap]      [⬆️ Upgrade]
[🌐 Đổi ngôn ngữ]
```
- **Ready (en):**
```
⚙️ Settings

🔗 Webhook: ...{last6chars}
📧 Email: u42@in.mymoneywent.com
🌐 Timezone: Asia/Ho_Chi_Minh
🌙 Daily recap: ✅ On
📋 Plan: Pro (trial, 5 days left)
🌐 Language: 🇬🇧 English

[🔄 Regenerate URL] [🌐 Change timezone]
[🌙 Turn off recap]  [⬆️ Upgrade]
[🌐 Change language]
```
- **Error:** `t(locale, 'error.generic')`
- **Empty:** N/A (luôn có settings)

### Language Change Screen
```
🌐 Chọn ngôn ngữ / Choose language:

[🇻🇳 Tiếng Việt]  [🇬🇧 English]
```

> All text rendered via `t(user.locale, key)`. Xem [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md).

---

## 4. Domain Model

**Fields trên `users` table:** `webhook_token`, `inbound_email`, `timezone`, `locale`, `daily_recap_enabled`, `plan`, `trial_ends_at`, `plan_expires_at`

**Tables:** `users`, `scheduled_jobs`, `bank_connections`

---

## 5. API Endpoints

Xử lý qua Telegram command / Discord slash command `/settings` + callback/button interaction trong `/webhook/{channel}`.

---

## 6. Error Codes

| Code | Error Code | Message | Trigger |
|------|-----------|---------|---------|
| 400 | `SETTINGS_TZ_INVALID` | "Timezone không hợp lệ. Ví dụ: Asia/Ho_Chi_Minh" | Invalid timezone |
| 500 | `SETTINGS_REGEN_FAIL` | "⚠️ Không tạo được URL mới." | Token generation fail |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `settings_opened` | `/settings` | `user_id` |
| `settings_webhook_regenerated` | Regenerate URL | `user_id` |
| `settings_timezone_changed` | Đổi timezone | `user_id`, `old_tz`, `new_tz` |
| `settings_recap_toggled` | Bật/tắt recap | `user_id`, `enabled` |
| `settings_language_changed` | Đổi ngôn ngữ | `user_id`, `old_locale`, `new_locale` |

---

## 8. State Machine

```
[/settings] → [settings_view]
    ├── Regenerate URL → confirm → update → [settings_view]
    ├── Đổi timezone → [await_timezone_input] → update → [settings_view]
    ├── Toggle recap → update → [settings_view]
    ├── Đổi ngôn ngữ → [settings_lang_pick] → update locale → [settings_view] (in new locale)
    └── Upgrade → redirect /upgrade flow
```

---

## 9. Caching Strategy

- **Settings data:** Không cache (direct query, low frequency)
- **Timezone list:** Static in-memory

---

## 10. Acceptance Criteria

- [ ] Regenerate webhook URL → invalidate cũ ngay lập tức (DELETE old row + INSERT new in `webhook_tokens` table, kind='sepay')
- [ ] Timezone change → `users.daily_recap_enabled` flag respected by F09 scheduler (F07 only writes `users.timezone`; F09 owns next_run_utc recalc)
- [ ] Toggle daily recap → update `users.daily_recap_enabled` only (F07 does NOT touch `scheduled_jobs` directly)
- [ ] Plan info hiển thị đúng: free → "Free"; pro/business trial → "<Plan> (trial, X days left)"; pro/business active → "<Plan>"
- [ ] Webhook URL display = "configured ✓ (created {date}) · ...{display_suffix}" — display_suffix populated by feat/webhook-display-suffix-migration PR (G3 closed)
- [ ] Đổi ngôn ngữ: hiện 2 button → update `users.locale` → refresh settings trong locale mới
- [ ] All settings text rendered via `t(user.locale, key)`
- [ ] Tenant isolation: user A cannot read or mutate user B's settings (all queries WHERE user_id = $1)
- [ ] Timezone validation: rejects strings outside `zoneinfo.available_timezones()` (stdlib, not pytz)

---

<!-- autopilot:gaps
# F07 gap analysis 2026-05-12 — all gaps CLOSED or DEFERRED before pilot.
# Schema reconciled against migrations/versions/0001_initial_schema.py (W0.2).

- id: G1
  question: Are F07 user-table fields already in W0.2 migrations or does F07 add them?
  status: CLOSED
  decision: All fields exist post-W0.2 (locale, timezone, daily_recap_enabled, plan, trial_ends_at, plan_expires_at, inbound_email). NO ALTER TABLE in F07 scope.
  rationale: Verified 2026-05-12 against migrations/versions/0001_initial_schema.py. The plan v0.1.6 §6.5 description "P1-lite, touches users table extension" is now slightly historical — schema landed in W0; F07 only mutates state. Classification remains P1 because the feature still changes user state + has F09 side-effects.
  alternatives_rejected: Adding a new migration in F07 (not needed; would block pilot).

- id: G2
  question: Where is the webhook token stored? BE doc shows UPDATE users.webhook_token but that column does not exist.
  status: CLOSED
  decision: Tokens live in dedicated `webhook_tokens` table (Gap 3 from W0.2). Regenerate operation: DELETE WHERE user_id=$1 AND kind='sepay' THEN INSERT new row with fresh token_hash, in one transaction. Old token invalidates atomically (UNIQUE(user_id, kind) constraint preserved).
  rationale: webhook_tokens.token_hash is SHA256 of plaintext per Gap 3 design; plaintext shown to user ONCE in regen success message, never stored.
  alternatives_rejected: Adding users.webhook_token column (violates Gap 3 decision); soft-revoke via revoked_at (would break UNIQUE(user_id, kind)).

- id: G3
  question: How to display webhook URL suffix in /settings overview given schema has only token_hash (no plaintext / no display_suffix column)?
  status: CLOSED
  decision: Founder locked option (b) 2026-05-12 — add `display_suffix VARCHAR(8)` column to webhook_tokens table in a SEPARATE follow-up PR (feat/webhook-display-suffix-migration), landing BEFORE F07 pilot. F07 then renders "🔗 Webhook: configured ✓ (created {date}) · ...{display_suffix}" once the column exists. Migration PR scope: alembic upgrade adds nullable column, mint_token populates it, lookup path unchanged (token_hash still primary).
  rationale: Suffix gives users visual confirmation the webhook URL they pasted matches the one rendered — option (a) "configured ✓ + date" was acceptable but founder judged the missing tail-suffix would look like a UX bug. Schema change is small, additive, nullable → P1 (Codex review + manual merge per plan §6.5).
  alternatives_rejected: Option (a) plain "configured ✓ (created {date})" without suffix (chosen first-pass but founder revisited); showing token_hash last-N chars (info leak risk + looks like a bug); deriving suffix from token_hash via deterministic substring (couples display to storage hash — fragile if hash algo ever changes).

- id: G4
  question: inbound_email — auto-derived or stored?
  status: CLOSED
  decision: Stored in users.inbound_email (UNIQUE column) populated at user creation by F-onboarding/W0. F07 reads `get_overview` is PURE (no DB writes). If row is NULL (legacy users), UI renders the deterministic fallback display string `u{user_id}@in.mymoneywent.com` (via `settings_svc.fallback_inbound_email`). Backfill is handled separately, at trusted callsites only — (1) one-time alembic migration 0003 backfills existing NULL rows; (2) `settings_svc.ensure_inbound_email(user_id)` idempotent helper available for any future post-auth gate / onboarding seam to catch a post-migration NULL (defense in depth — should not occur, cheap to guard).
  rationale: Original G4 lock had `get_overview` doing implicit backfill, which became a hidden write side-effect surfacing in every handler that called `get_overview` before validation (Codex F07 R2 + R3 both caught instances). Root-cause refactor 2026-05-13 separated read from write; explicit backfill at trusted callsite. CQRS-aligned. Schema still enforces UNIQUE; F07 must not re-issue or mutate the email.
  alternatives_rejected: Per-handler validate-before-`get_overview` (R2 band-aid pattern) — requires N audits, doesn't enforce purity, future handlers can re-fall into the trap. Inline backfill inside `get_overview` — original anti-pattern; this refactor removes it. Always-computed (loses UNIQUE guarantee). Never-backfilled (breaks display for any user missing the field — but mitigated by UI fallback rendering).

- id: G5
  question: Plan info display format — how is "trial vs active vs expired" computed?
  status: CLOSED
  decision: status = "trial" if trial_ends_at IS NOT NULL AND trial_ends_at > NOW(); else "expired" if plan_expires_at IS NOT NULL AND plan_expires_at < NOW(); else "active". Days computation = (trial_ends_at - NOW()).days for trial. Display string built in t-function: t(locale, 'settings.plan_status', plan=plan, status=status, days=days_left). Free plan shows "Free" only.
  rationale: Deterministic from existing columns; no new state needed.

- id: G6
  question: Recap toggle — does F07 update scheduled_jobs.enabled directly?
  status: CLOSED
  decision: F07 writes ONLY users.daily_recap_enabled. F09 (Scheduled Jobs) reads that flag before firing the recap job — no direct INSERT/UPDATE on scheduled_jobs from F07.
  rationale: Decouples F07 from F09's scheduling internals; per Wave 1 dependency graph F07 and F09 are in different waves (F07 = Wave 1, F09 = Wave 4 per development-workflow.md §4). Cross-wave coupling via boolean flag is the right pattern.
  alternatives_rejected: F07 mutating scheduled_jobs directly (tight coupling, F09 spec already owns the next_run_utc recalculation on TZ change).

- id: G7
  question: Timezone validation library — pytz or stdlib zoneinfo?
  status: CLOSED
  decision: Use stdlib `zoneinfo.available_timezones()` (Python 3.11+). No pytz dependency added.
  rationale: requires-python is >=3.11 (pyproject.toml). zoneinfo is stdlib, ships with the same IANA tzdb, handles DST natively. Avoids extra pin in requirements.txt.
  alternatives_rejected: pytz (extra dependency, deprecation path).

- id: G8
  question: Bank connections list display — included in F07 pilot?
  status: DEFERRED:F-bank-connections
  decision: F07 first pilot SKIPS the "Xem bank connections" row in /settings. Defer to a dedicated F-bank-connections feature spec which owns the bank-list UX.
  rationale: Bank-connections UX (add/remove/list per-channel) is not fully specified in F07 FE doc; pilot must not over-scope. The bank_connections table exists from W0.2 so future work has its data layer.

- id: G9
  question: Channel-specific UI dispatch — how does /settings render on Telegram vs Discord vs Messenger?
  status: CLOSED
  decision: handlers/settings.py uses core.messenger.send() per the W0.4 BaseSender contract; per-channel adapters translate the payload to Telegram inline buttons / Discord embed+buttons / Messenger quick-replies. F07 ships only the Telegram path; Discord + Messenger postback wiring is covered by Wave 6 channel features.
  rationale: ADR-0001 + W0.4 lock the adapter pattern; F07 must not branch on channel inside core/.
  alternatives_rejected: if channel == 'telegram' branches in handler (banned by ADR-0001).

- id: G10
  question: Language change UX — separate command or inline from /settings?
  status: CLOSED
  decision: Inline `[🇻🇳 Tiếng Việt] [🇬🇧 English]` buttons in /settings overview. Callback writes users.locale then re-invokes the settings handler so the overview re-renders in the new locale.
  rationale: Matches F-i18n design (locale stored in users table; t-function reads it per request). Single-roundtrip UX.
-->

<!-- autopilot:test_plan
# 5-category test plan per Wave 0 lesson #4. Tests live in tests/unit/ and tests/integration/.
# Tenant-isolation test is mandatory (DB touched).

happy_path:
  - test_settings_overview_renders_all_rows: /settings command returns webhook status, inbound_email, timezone, recap flag, plan, locale in correct format for both vi and en locales.
  - test_regen_webhook_token_replaces_row: settings:regen callback DELETEs old webhook_tokens row + INSERTs new in same transaction; new plaintext shown once in success message.
  - test_change_timezone_valid: settings:tz with valid IANA name (e.g. 'Asia/Tokyo') updates users.timezone; subsequent /settings renders new value.
  - test_toggle_recap_on_off_on: settings:recap_toggle flips users.daily_recap_enabled on each call.
  - test_change_language_vi_to_en_rerenders: settings:lang_pick=en updates users.locale and re-renders /settings in English.

retry_idempotency:
  - test_recap_toggle_idempotent_on_same_value: posting the same toggle twice (e.g. ON→ON) is a no-op and emits no analytics event the second time.
  - test_locale_change_idempotent_same_locale: choosing the already-active locale is a no-op (no DB write, no analytics).
  - test_regen_is_not_idempotent_by_design: two regen calls produce two different token_hash values (deliberate — see G2 decision); test pins this expectation so a future "idempotent regen" refactor breaks loudly.

missing_optional_fields:
  - test_settings_overview_with_free_plan_no_trial: user with plan='free', trial_ends_at NULL, plan_expires_at NULL renders "📋 Plan: Free" (no trial/expiry suffix).
  - test_inbound_email_backfilled_when_null: user with users.inbound_email NULL → first /settings read computes f"u{user_id}@in.mymoneywent.com", persists to column, returns the value.
  - test_user_with_no_bank_connections_no_bank_row: pilot skips bank row entirely per G8; spec acceptance does not require it.
  - test_settings_for_user_with_null_locale_falls_back: defaults to 'vi' (matches users.locale DEFAULT in W0.2 schema).

pathological_inputs:
  - test_invalid_timezone_string_rejected: settings:tz='ABC' → SETTINGS_TZ_INVALID error code + common-TZ suggestions list (Asia/Ho_Chi_Minh etc.).
  - test_timezone_empty_string_rejected: same path as invalid; ensures empty input does not crash zoneinfo lookup.
  - test_timezone_sql_injection_shaped_input_rejected: "Asia/Ho_Chi_Minh'; DROP TABLE users; --" → rejected by zoneinfo membership check before reaching DB.
  - test_settings_callback_other_user_id_blocked: forged callback_data referencing another user_id → query returns no row because handler scopes WHERE user_id = current_user.id; never the callback's payload.
  - test_extremely_long_timezone_string_rejected: 10KB input rejected without DB write.

concurrent_access:
  - test_concurrent_regen_two_requests_one_survives: two parallel asyncio tasks call regen for same user; UNIQUE(user_id, kind) ensures exactly one final row; both callers receive a success response (last writer wins) with no DB error.
  - test_recap_toggled_mid_recap_fire: F09 scheduler reads users.daily_recap_enabled at fire time; flipping the flag between two scheduled fires changes whether the second fires. F07 does not race F09's job-state machine.
  - test_locale_change_during_settings_render_uses_latest: while one task renders overview, another flips locale; second render reads fresh locale (no caching by F07 per §9).

# Tenant isolation (mandatory per development-workflow.md §2.4):
tenant_isolation:
  - test_user_a_cannot_read_user_b_settings: queries for user A always include WHERE user_id = A.id; injected callback data with user_id=B does not bypass scoping.
  - test_user_a_cannot_regenerate_user_b_webhook_token: settings:regen on behalf of B by a session authenticated as A is rejected (handler reads user_id from authed session, never from payload).
-->

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial — tách từ PRD §3.7 |
| v1.1.0 | 2026-05-08 | **i18n language change:** (1) Thêm đổi ngôn ngữ option vào settings view + state machine. (2) Language row hiện trong settings overview. (3) Thêm `settings_language_changed` analytics event. (4) All text rendered via `t(user.locale, key)`. (5) `locale` thêm vào domain model fields. |
| v1.2.0 | 2026-05-12 | **Autopilot template migration (Blocker #3):** (1) Added `autopilot:meta` block (feature_id=F07, branch=feat/F07-settings, risk_tier=P1). (2) Added `autopilot:gaps` block — 10 gaps closed against current W0.2 schema; G3 (webhook URL suffix display) + G8 (bank list scope) DEFERRED to founder review. (3) Added `autopilot:test_plan` block — 5 categories + tenant_isolation, ~20 test intents. (4) Acceptance Criteria rewritten to reflect W0 schema reality (no users.webhook_token column; F07 uses dedicated webhook_tokens table per Gap 3). (5) Trạng thái → Ready. |
