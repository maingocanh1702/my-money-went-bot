# Phase 2: Handlers Refactor — 9 PRs

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Refactor monolithic legacy handlers/ thành multi-tenant feature handlers, strangler-fig legacy cutover, ship 9 features (onboarding-start start, categorization, category-management, reports, settings, funding-sources, admin-auth auth, i18n-locale-switcher, transaction-capture expanded).
> **Tham chiếu:**
> - [Implementation Tracker](../implementation-tracker.md)
> - [Dev Workflow §4 Wave 1-4](../operations/development-workflow.md)
> - W0.6 scope split summary: [Development Workflow §4](../operations/development-workflow.md) + [Wave 0 Retrospective](../operations/wave0-retrospective.md)

---

## Overview

| # | PR | Wave | Feature | Order | Est. days | Tests |
|---|----|------|---------|:-----:|:---------:|:-----:|
| 1 | onboarding-start | 1 | onboarding-start `/start` + user create + trial | 1 | 1.5 | 12 |
| 2 | settings | 1 | Settings `/settings` | 1 (parallel with #1) | 1.0 | 10 |
| 3 | i18n-locale-switcher | 1 | VI/EN switcher full | 2 (parallel) | 1.5 | 14 |
| 4 | admin-auth | 1 | Admin auth framework only | 2 (parallel) | 0.5 | 6 |
| 5 | funding-sources | 2 | Funding sources service+handlers | 3 | 2.0 | 18 |
| 6 | transaction-capture | 2 | TX capture EXPANDED + legacy cutover | 4 | 4.0 | 25 |
| 7 | category-management | 3 | Category management `/manage` | 5 | 1.5 | 14 |
| 8 | categorization | 3 | Categorization auto+manual | 6 (after #7) | 2.0 | 16 |
| 9 | reports | 4 | Reports `/status`, `/today`, `/weekly` | 7 | 1.5 | 12 |
| **Total** | | | | | **~15 days** | **127** |

**Parallel slots (max 2 active):**
- Slot 1: onboarding-start → funding-sources → transaction-capture → category-management → categorization → reports (main critical path)
- Slot 2: settings || i18n-locale-switcher || admin-auth (filler when slot 1 blocked on review)

---

## #1 — onboarding-start (onboarding-start `/start` only)

> Full Path A/B/C onboarding ships in Phase 4. Here chỉ ship `/start` skeleton + user create + trial assign.

### Scope

- Handler `core/handlers/start.py` — multi-channel `/start` command
- User create: insert into `users` table với `channel_type` + `channel_user_id`
- Trial assign: `trial_ends_at = now() + 14 days`, `plan = 'free'`
- Welcome message (locale-aware, via i18n stub)

### Files touched

```
+ core/handlers/__init__.py
+ core/handlers/start.py
+ tests/integration/test_start_handler.py
M main.py  (wire start handler to messenger dispatch)
```

### Test plan (12)

1. Positive: TG user `/start` → user created, plan=free, trial 14d
2. Positive: Discord user `/start` → same flow, channel_type='discord'
3. Edge: existing user `/start` again → no duplicate, return welcome-back
4. Edge: trial already expired user `/start` → keep plan=free, no re-trial
5. Edge: race — 2x `/start` cùng lúc → idempotent (uniq constraint)
6. Error: DB down → graceful error message, no crash
7. Isolation: User A `/start` → User B unaffected
8. i18n: VI default
9. i18n: User locale=EN → English welcome
10. Onboard path tracking: `onboard_path` initial NULL
11. Contract: `messenger.send()` called với correct user_id
12. Welcome message contains: trial expiry date + next-step hint (`/setup`)

### Acceptance criteria

- New user TG/Discord `/start` → DB row created với correct defaults
- Repeat `/start` idempotent
- Welcome message localized
- No tenant leak (cross-user assertion green)

### Decision lockdown

- [ ] `chat_id` field: nullable until first message (Discord webhook context)
- [ ] Trial: 14 days FROM signup, not from first activity
- [ ] Locale default: VI (per BRD market positioning)

---

## #2 — settings Settings `/settings`

### Scope

- Handler `core/handlers/settings.py` — `/settings` command + inline keyboard
- 3 settings: locale (vi/en), timezone, daily_recap_enabled
- Inline callback parsing + UPDATE statement

### Files touched

```
+ core/handlers/settings.py
+ tests/integration/test_settings_handler.py
M core/handlers/__init__.py
```

### Test plan (10)

Positive (3): show settings, change locale, change TZ
Edge (3): invalid TZ string, locale toggle persistence, recap toggle off
Error (2): unauthorized (no user) → graceful redirect to /start; DB error
Isolation (1): User A change locale → User B unaffected
Contract (1): inline keyboard callback parses correctly

### Acceptance criteria

- 3 settings persist across sessions
- TZ change reflected next daily recap
- i18n switching live (no logout needed)

### Decision lockdown

- [ ] TZ list: top 5 VN-relevant (Asia/Ho_Chi_Minh default) + UTC + manual entry
- [ ] Inline keyboard: 3 buttons per row, paginate if >9 options

---

## #3 — i18n-locale-switcher expansion

### Scope

- Expand `core/messenger/i18n.py` stub (W0.4) → all user-facing strings
- Locale files `core/messenger/locales/vi.json`, `en.json`
- Helper `t(key, locale, **vars)` với fallback to vi nếu missing en

### Files touched

```
M core/messenger/i18n.py
M core/messenger/locales/vi.json
M core/messenger/locales/en.json
+ tests/unit/test_i18n_completeness.py
```

### Test plan (14)

Positive (5): basic lookup vi+en, var interpolation, plural forms, nested keys, escape chars
Edge (4): missing key → return key + warn log; missing locale → fallback vi; empty var; HTML escape
Error (2): malformed JSON → fail at startup, not runtime; circular ref
Completeness (3): every vi key has en counterpart; no orphan en keys; no dynamic key generation

### Acceptance criteria

- All Phase 2 features (onboarding-start, settings, settings) use `t()` — no hardcoded strings
- Completeness test pass (vi ⟷ en keys equal)
- Plural forms: VN "1 giao dịch" vs "5 giao dịch" handled

### Decision lockdown

- [ ] JSON format (not YAML, not gettext .po) — simplest, hand-edit friendly
- [ ] Variable syntax: `{name}` (Python str.format style)
- [ ] No runtime locale switching mid-message (resolve at handler entry)

---

## #4 — admin-auth Admin auth framework only

> Actual `/admin_*` commands defer Phase 6. Just authz scaffolding here.

### Scope

- `core/auth/admin.py` — `is_admin(user_id) -> bool` checking `users.role='admin'` OR env `ADMIN_USER_IDS`
- Decorator `@admin_only` for handlers
- Audit log helper `record_admin_action(action, target_user_id, details)`

### Files touched

```
+ core/auth/__init__.py
+ core/auth/admin.py
+ tests/unit/test_admin_auth.py
```

### Test plan (6)

1. Positive: role=admin → is_admin True
2. Positive: env ADMIN_USER_IDS contains user → True
3. Edge: role=user, not in env → False
4. Edge: founder (role=founder) → True (founder = superset of admin)
5. Decorator: non-admin call → silent ignore (don't leak existence)
6. Audit log row inserted with correct fields

### Acceptance criteria

- `@admin_only` decorator blocks non-admins silently
- Audit log captures action + target + actor
- Env override works (for emergency access)

### Decision lockdown

- [ ] Non-admin → silent ignore (not error message). Avoid leaking admin commands exist.
- [ ] Founder role = admin superset (role hierarchy: founder > admin > user)
- [ ] Audit log: always insert, even for failed authz attempts

---

## #5 — funding-sources Funding Sources service+handlers

> DDL landed W0.2. This PR: service logic + handlers.

### Scope

- `core/services/funding_sources.py` — CRUD + `resolve_funding_source(user_id, kind, bank, last4)` canonical lookup
- Handlers `/funding`, callback for add/archive
- Embed-in-picker UX (per memory `project_f08_funding_sources.md`)

### Files touched

```
+ core/services/funding_sources.py
+ core/handlers/funding.py
+ tests/integration/test_funding_sources.py
+ tests/unit/test_funding_resolver.py
```

### Test plan (18)

Positive (6): create, list, archive, restore, resolve hit, resolve miss → discovery prompt
Edge (5): duplicate canonical identity → return existing; archived not in active list; cross-user resolve isolation; bank rename preserves resolve; last4 mask format
Error (3): invalid last4 (not 4 digits); kind/bank mismatch; archive root-account with active funding
Isolation (2): User A funding never appears in User B picker
Contract (2): transaction-capture `resolve_funding_source()` called correct args

### Acceptance criteria

- transaction-capture contract: any `INSERT INTO transactions` MUST call `resolve_funding_source()` first (enforced via integration test)
- Embed-in-picker discovery flow works (new bank → inline prompt)
- Archive ≠ delete (FK preserved, history queryable)

### Decision lockdown (reference memory)

- [x] Canonical identity: `(user_id, kind, bank, last4)` — locked 2026-05-11
- [x] Status enum: `active`, `archived` (no `deleted`) — soft archive only
- [x] transaction-capture requires resolve before INSERT — locked

### Risk

- transaction-capture may discover edge cases that need funding-sources schema tweak → backport to W0.2 migration via new migration (no rewrite)

---

## #6 — transaction-capture Transaction Capture EXPANDED (legacy cutover)

> **The big one.** Inherits W0.6 deferred scope. Strangler-fig: each legacy handler = own commit, then squash.

### Scope (per W0.6 scope split summary in Development Workflow + Wave 0 Retrospective)

1. Rewrite `handlers/transaction.py` → `core/handlers/transaction.py` multi-tenant
2. Rewrite `handlers/manage.py` → `core/handlers/manage.py` (note: overlaps category-management — coordinate)
3. Rewrite `handlers/reports.py` → `core/handlers/reports.py` (overlaps reports — placeholder, reports expands)
4. Rewrite `handlers/allocation.py` → `core/handlers/allocation.py`
5. Delete `sheets.py` (Google Sheets layer obsolete)
6. Refactor `main.py` — remove legacy imports, wire new core handlers
7. Execute `scripts/migrate_sheets.py` — founder data migration (Sheets → Postgres)
8. Remove `handlers` from import-linter `root_packages`
9. Wire funding-sources `resolve_funding_source()` into transaction INSERT path

### Files touched

```
- handlers/transaction.py
- handlers/manage.py
- handlers/reports.py
- handlers/allocation.py
- handlers/scheduled.py
- sheets.py
+ core/handlers/transaction.py
+ core/handlers/manage.py        (skeleton, category-management expands)
+ core/handlers/reports.py        (skeleton, reports expands)
+ core/handlers/allocation.py
M main.py
M .importlinter  (remove 'handlers' from root_packages)
M scripts/migrate_sheets.py  (remove NotImplementedError, real impl)
+ tests/integration/test_tx_capture_e2e.py
+ tests/integration/test_legacy_cutover.py
+ tests/scripts/test_migrate_sheets_real.py
```

### Test plan (25)

**TX capture E2E (8):**
1. SePay webhook → tx inserted với funding_source resolved
2. Email parser → tx inserted same path
3. Cross-source dedup placeholder (full dedup cross-source-dedup PR)
4. Tx with unknown bank → funding discovery prompt
5. Tx with archived funding → silently re-resolve to active
6. Negative amount handled
7. Currency: VND default, no FX
8. Idempotency on duplicate webhook (token + tx_external_id)

**Legacy cutover (10):**
9. Old `handlers/transaction.py` no longer importable
10. `main.py` boots without `import handlers`
11. `sheets.py` import fails (file deleted)
12. Existing user data migrated 1:1 (count matches)
13. Migration script idempotent (re-run safe)
14. Founder user_id=1 preserved
15. Categories migrated with parent/sub structure intact
16. Bot resumes operation post-cutover (no downtime expected during dev)
17. Import-linter: no `handlers` package reference
18. Multi-tenant: legacy founder data isolated under user_id=1

**funding-sources wire-in (4):**
19. INSERT without resolve_funding_source call → integration test fails (assertion)
20. New bank discovery flow end-to-end
21. Resolver result cached per-request (no N+1)
22. Resolver miss → graceful prompt, tx queued

> **Pre-existing transaction-capture contract pin (added post-W0, 2026-05-12):**
> `tests/integration/test_sepay_webhook.py::test_persisted_tx_has_resolved_funding_source_id`
> is marked `@pytest.mark.xfail(strict=True, reason="transaction-capture: funding source resolve required ...")`.
> When this PR wires resolution into `_persist()`, the assertion flips to passing
> and `xfail(strict=True)` will RAISE on the unexpected pass — you MUST remove
> the `@pytest.mark.xfail` decorator as part of the transaction-capture commit. Do not silence
> the marker (strict=False) to make CI green; that defeats the contract pin.

**Tenant isolation (3):**
23. User A tx never visible to User B
24. Webhook with User A token → tx ONLY for User A
25. Email parser with user_id from token → ONLY that user

### Acceptance criteria

- All legacy code paths deleted from main
- Founder Sheets data 100% migrated, counts verified
- No regression: bot answers same as pre-cutover for founder
- funding-sources wire-in enforced via integration assert
- **`test_persisted_tx_has_resolved_funding_source_id` xfail marker removed** (test now passes naturally — see test plan note above)
- Legacy formatter policy resolved: either commit the W0.6-era black/ruff drift on legacy files as a `style:` commit in this PR, or revert and reformat as part of the move into `core/handlers/`. Default: reformat-on-move (cleaner blame).

### Decision lockdown

- [ ] Migration cutover time: weekend window, founder confirms before run
- [ ] Rollback plan: revert PR + restore B2 backup (existing W0.6 backup adequate)
- [ ] Old `handlers/` folder removed in same PR (not separate cleanup)
- [ ] Decide legacy-format-drift handling: revert + reformat-on-move (recommended) vs commit as `style:` baseline

### Risk

- **High:** This PR touches main.py + ~10 files + migration. Atomic commits in branch crucial.
- **Mitigation:** Each legacy handler rewrite = own commit. Codex review per commit before squash.

---

## #7 — category-management Category Management `/manage`

### Scope

- `core/services/categories.py` — CRUD + parent/sub tree
- `core/handlers/manage.py` (expand skeleton from transaction-capture) — `/manage` command + inline keyboard
- Free tier limit: 5 categories (enforced in service)

### Files touched

```
+ core/services/categories.py
M core/handlers/manage.py
+ tests/integration/test_categories.py
```

### Test plan (14)

Positive (5): create, list tree, rename, archive, restore
Edge (4): free tier hit 5 cat → block w/ upgrade CTA; archive cat with active txs → reassign-to-default flow; parent w/ subs cannot archive; rename clash
Error (2): name too long; empty name
Isolation (2): User A cats invisible to User B
Tier (1): Pro user no limit

### Acceptance criteria

- Free tier 5-cat limit enforced
- Tree structure preserves on archive/restore
- Reassign-to-default flow works

---

## #8 — categorization Categorization (after category-management)

### Scope

- `core/services/categorizer.py` — auto-rules engine + manual override
- Rule types: keyword match, amount range, merchant pattern
- Manual: callback to set category on uncategorized tx
- Confidence scoring (0-1), threshold 0.7 → auto-apply; <0.7 → prompt

### Files touched

```
+ core/services/categorizer.py
+ core/handlers/categorize.py
+ tests/unit/test_categorizer_rules.py
+ tests/integration/test_categorization_flow.py
```

### Test plan (16)

Positive (6): keyword exact, keyword partial, amount range, merchant pattern, manual override, confidence threshold
Edge (5): multiple rules match → highest confidence wins; tie → first-defined wins; no rule → prompt; archived cat as target; recategorize
Error (2): rule with invalid regex; circular parent
Isolation (2): rules per-user, no leak
Tier (1): free user limited rule count

### Acceptance criteria

- Auto-categorize ≥70% accuracy on founder's historical txs
- Manual override learns (saves as rule with explicit confidence 1.0)
- Confidence visible in UI

### Decision lockdown

- [ ] Rule language: structured JSON (no DSL), edit via /manage
- [ ] Confidence threshold: 0.7 (tunable per-user later, MVP fixed)
- [ ] Re-categorization: explicit only, no auto-re-run on rule change

---

## #9 — reports Reports `/status`, `/today`, `/weekly`

### Scope

- `core/services/reports.py` — query layer (read-only, aggregate)
- `core/handlers/reports.py` (expand skeleton from transaction-capture) — 3 commands
- Format: text-only (no charts/images for MVP)

### Files touched

```
+ core/services/reports.py
M core/handlers/reports.py
+ tests/integration/test_reports.py
```

### Test plan (12)

Positive (5): `/today` empty, `/today` with txs, `/status` month, `/weekly` rolling 7d, multi-currency display
Edge (4): TZ boundary (00:00 user TZ), DST switch, archived categories shown as "Other", year-end boundary
Error (1): malformed date input on extended `/status YYYY-MM`
Isolation (2): User A reports never include User B txs

### Acceptance criteria

- Reports respect user TZ
- Free tier: 30d history limit enforced in query
- No charts/images (text + simple table emoji art only)

### Decision lockdown

- [ ] No chart libs (matplotlib etc.) for MVP — text only
- [ ] Currency: VND only display (no FX conversion)
- [ ] `/weekly` = rolling 7d, not calendar week

---

## Phase 2 exit checklist (gate → Phase 3)

- [ ] All 9 PRs merged
- [ ] Legacy `handlers/` + `sheets.py` deleted
- [ ] Founder data migrated, parity verified
- [ ] Import-linter no `handlers` reference
- [ ] All features work cross-channel (TG + Discord)
- [ ] i18n VI/EN both pass
- [ ] Admin auth framework tested
- [ ] funding-sources resolver enforced via integration assert
- [ ] Roadmap Phase 2 → 100%, tracker updated
- [ ] No new tech debt > P3

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial plan. 9 PRs across Wave 1-4. ~15 days est. transaction-capture is high-risk (legacy cutover) — strangler-fig commits. funding-sources → transaction-capture ordering locked (funding-sources first per memory). |
| v1.0.1 | 2026-05-12 | Post-W0 follow-ups added: transaction-capture must remove `xfail` marker on `test_persisted_tx_has_resolved_funding_source_id` (contract pin from 2026-05-12); legacy formatter drift decision lockdown item added. |
