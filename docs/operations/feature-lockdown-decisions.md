# onboarding-start + funding-sources Lockdown — Pre-autopilot decisions

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-13
> **Status:** Active — feeds into autopilot prompt generation
> **Owner:** Founder (dev)
> **Mục đích:** Single source of truth cho lockdown decisions của onboarding-start + funding-sources trước khi generate autopilot prompts. Per memory `feedback_f07_lessons` rule "lock decisions before autopilot."
>
> **Tham chiếu:**
> - [Implementation Plan Phase 2 §1 (onboarding-start) + §5 (funding-sources)](../implementation-plans/phase-2-handlers.md)
> - [FE spec onboarding-start](../features/feature-onboarding.md) (v1.2.0)
> - [BE tech onboarding-start](../features/BE/feature-onboarding-tech.md) (v1.0.0, stale vs FE — see §1.5)
> - [FE spec funding-sources](../features/feature-funding-sources.md) (v1.0.0)
> - [BE tech funding-sources](../features/BE/feature-funding-sources-tech.md)
> - [Autopilot prompt template](../autopilot/autopilot-prompt-template.md) (15-section skeleton)
> - Memory: `project_f08_funding_sources`, `feedback_f07_lessons`, `project_autopilot_risk_tier_policy`, `feedback_concurrency_one_session`

---

## 1. onboarding-start — `/start` + user create + trial assign

### 1.1 Branch + risk header

```
Branch:             feat/F01-onboarding-start
Risk tier:          P1
Merge policy:       manual_only
Autopilot maturity: mature (post-settings 6-session pilot validated v0.2.3 orchestrator)
Codex review:       2x_consecutive_clean (P1 always)
```

### 1.2 Scope discipline

**Positive scope:**
- `core/handlers/start.py` — multi-channel `/start` command handler
- User INSERT with: `channel_type`, `channel_user_id`, `chat_id` (nullable), `webhook_token` (24-char URL-safe via `secrets.token_urlsafe(18)`), `inbound_email` = `u{id}@in.tienvenoidau.com`, `plan='free'`, `trial_ends_at=now()+14d`, `locale='vi'` default, `language_code` from update
- Welcome message (VI-only, via `i18n/vi.py` stub from W0.4)
- Default categories auto-create (`daily_spending`, `saving`, `subscription`) — VI strings only
- Wire to `main.py` messenger dispatch
- 12 integration tests (per plan §1 test plan)

**Negative scope (do NOT touch):**
- Path A/B/C onboarding flows — Phase 4 (sepay-onboarding-paths/first-tx-celebration/email-forwarding-onboarding)
- Path D Family invite accept — Phase 4 + family plan ship
- Language confirm UI (`[✅ vi] [🌐 en]` buttons) — defer to i18n-locale-switcher PR
- EN locale strings — defer to i18n-locale-switcher PR
- `bank_connections` INSERT — funding-sources/transaction-capture own
- `scheduled_jobs` INSERT — scheduled-jobs owns (note: BE spec §2.1 says auto-create here but plan §1 doesn't list — clarified: scheduled-jobs will backfill later)

**Out-of-scope but documented:**
- Auto-detect locale from Telegram `language_code` — defer to i18n-locale-switcher PR (would require language confirm UI)

### 1.3 Decision lockdown (confirmed 2026-05-13)

| # | Decision | Locked value | Reasoning |
|---|---|---|---|
| 1 | `chat_id` nullable until first message? | ✅ **NULLABLE** | Discord webhook context không cung cấp chat_id ngay; Messenger PSID khác structure. Allow late bind. |
| 2 | Trial 14d FROM signup hay first activity? | ✅ **FROM signup** | Per BRD market positioning. Simpler logic, no trial state machine. |
| 3 | Locale default | ✅ **`vi`** | Per BRD VN-first. EN added later via i18n-locale-switcher. |

### 1.4 Files touched (estimate)

```
+ core/handlers/__init__.py       (export start, settings)
+ core/handlers/start.py          (~200 LOC)
+ tests/integration/test_start_handler.py  (~250 LOC, 12 tests)
M main.py                          (wire start handler dispatch)
M i18n/vi.py                       (add ~6 keys: welcome, trial_info, default_cat_*)
```

Estimated diff: ~500 LOC added, ~10 LOC modified.

### 1.5 Spec drift notes

- **FE spec v1.2.0** has Path D Family invite + i18n language confirm UI. **NOT in Phase 2 onboarding-start scope** — plan §1 explicit: "Path A/B/C onboarding logic in Phase 4; chỉ ship `/start` here." Path D ships with sepay-onboarding-paths in Phase 4.
- **BE tech v1.0.0 stale** vs FE — covers Path A/B/C plus `bank_connections` + `scheduled_jobs`. Phase 2 onboarding-start ignores those (deferred per plan).
- **No spec update required for onboarding-start PR** — implementation follows plan §1 minimal scope. Spec versioning can update post-sepay-onboarding-paths/first-tx-celebration/email-forwarding-onboarding/scheduled-jobs.

### 1.6 Test plan (5-category, expanded from plan §1's 12 tests)

| Category | # | Description |
|---|---|---|
| Positive | 5 | TG `/start` → user created (plan=free, trial 14d) · Discord `/start` → channel_type='discord' · Re-start existing user → welcome-back · Default categories created VI strings · Welcome message contains trial expiry date |
| Edge | 3 | Existing user `/start` twice rapid → idempotent (ON CONFLICT DO NOTHING) · Trial expired user `/start` → keep plan=free, no re-trial · `language_code` NULL → default `vi` |
| Error | 2 | DB down → graceful error message via messenger · Webhook token collision (mock) → retry generates new |
| Isolation | 1 | User A `/start` → User B existence + state unchanged (multi-tenant assert) |
| Contract | 1 | `messenger.send()` called with correct user_id (mock spy) |

**Total: 12 tests** (matches plan).

### 1.7 Acceptance criteria

- [ ] New TG/Discord user `/start` → DB row created with correct defaults (channel_type, plan='free', trial_ends_at = now+14d, locale='vi', webhook_token uniq, inbound_email = `u{id}@in.tienvenoidau.com`)
- [ ] Repeat `/start` idempotent (no duplicate row)
- [ ] Welcome message localized to user's locale (VI default; EN strings ship in i18n-locale-switcher)
- [ ] Default 3 categories auto-created with `daily_cap` per spec §4 domain model
- [ ] No tenant leak: User A action doesn't surface in User B query
- [ ] `webhook_token` is 24-char URL-safe, unique across users
- [ ] All 12 tests green; multi-tenant isolation test passes

### 1.8 Risk profile

- **High-touch surface:** Multi-tenant user creation + token generation + trial state.
- **Cascade impact:** funding-sources, transaction-capture, category-management, reports all depend on user records existing → schema correctness critical.
- **Mitigation per memory `feedback_f07_lessons`:**
  - 5-category test plan locked upfront (§1.6)
  - Single-phase scope (no multi-phase batch — `feedback_autopilot_prompt_scope`)
  - Codex 2× clean for P1 (per `project_autopilot_risk_tier_policy`)
  - `manual_only` merge — no auto-merge for P1

---

## 2. funding-sources — Funding sources resolver + handlers

### 2.1 Branch + risk header

```
Branch:             feat/F08-funding-sources
Risk tier:          P1
Merge policy:       manual_only
Autopilot maturity: mature
Codex review:       2x_consecutive_clean (P1 always)
```

### 2.2 Scope discipline

**Positive scope:**
- `core/services/funding_sources.py` — CRUD + `resolve_funding_source(user_id, kind, bank, last4)` canonical resolver
- `core/handlers/funding.py` — `/funding`, `/accounts`, `/banks` (legacy alias)
- Embed-in-picker discovery UX (per memory `project_f08_funding_sources`)
- Auto-discovery: tx đầu tiên của 1 funding source mới → prepend header vào category picker (per FE spec §3.1)
- Rename, hide, manual-add flows
- 18 tests (6 positive + 5 edge + 3 error + 2 isolation + 2 contract)

**Negative scope (do NOT touch):**
- transaction-capture transaction capture INSERT path — transaction-capture wires the `resolve_funding_source` call later
- DDL changes — table created in W0.2, no schema modification
- Auto-archive cron after 180d silent — scheduled-jobs owns (scheduled jobs)
- Email parser inference logic — handled in parser-techcombank/parser-cake-vpbank/parser-mbbank parsers (Phase 5)
- VI message strings only — EN defers to i18n-locale-switcher

**Out-of-scope but documented:**
- One-off backfill script for founder's legacy tx → funding_sources (per FE §2.2 case #12) — runs once in transaction-capture cutover, not part of funding-sources

### 2.3 Decision lockdown (already locked per memory + plan)

| # | Decision | Status | Source |
|---|---|---|---|
| 1 | Canonical identity `(user_id, kind, bank, last4)` | 🔒 Locked 2026-05-11 | memory `project_f08_funding_sources` |
| 2 | Status enum `active` / `hidden` / `archived` (no `deleted`) | 🔒 Locked 2026-05-11 | memory |
| 3 | transaction-capture requires `resolve_funding_source` before INSERT | 🔒 Locked 2026-05-11 | memory + W0.7 xfail pin (`tests/integration/test_sepay_webhook.py::test_persisted_tx_has_resolved_funding_source_id`) |
| 4 | Free tier limit on # funding sources | 🔒 **NO LIMIT** | FE spec §2.2 #11 — discovery passive, không tự thêm hàng loạt |
| 5 | last4 NULL handling | 🔒 Empty string `''` not NULL | FE spec §2.2 #3 — unique constraint comparable |

**No new lockdown questions.**

### 2.4 Files touched (estimate)

```
+ core/services/__init__.py
+ core/services/funding_sources.py        (~300 LOC)
+ core/handlers/funding.py                (~250 LOC)
+ tests/integration/test_funding_sources.py  (~400 LOC, ~14 tests)
+ tests/unit/test_funding_resolver.py      (~200 LOC, 4 unit tests)
M core/handlers/__init__.py               (export funding)
M main.py                                  (wire funding handler dispatch)
M i18n/vi.py                               (add ~12 keys for picker/discovery/rename/hide UX)
```

Estimated diff: ~1150 LOC added, ~15 LOC modified.

### 2.5 Test plan (5-category, expanded from plan §5's 18 tests)

| Category | # | Description |
|---|---|---|
| Positive | 6 | Create funding source · List active sources · Archive · Restore · Resolve hit (existing source) · Resolve miss → discovery prompt embed |
| Edge | 5 | Duplicate canonical identity → return existing · Archived not in active list · Cross-user resolve isolation · Bank rename preserves resolve via canonical identity · last4 empty-string format ('') vs 4-digit ('1234') |
| Error | 3 | Invalid last4 (5 digits, alphabetic) → reject · kind/bank mismatch (e_wallet bank='TCB') → reject · Archive funding source with active txs → reassign-to-NULL flow per FE §2.1 #5 |
| Isolation | 2 | User A funding source NEVER appears in User B picker · User A `/accounts` returns User A rows only |
| Contract | 2 | transaction-capture wire: `resolve_funding_source` returns same `id` for canonical-equivalent inputs · W0.7 xfail pin remains xfail (transaction-capture still owns flip) |

**Total: 18 tests** (matches plan).

### 2.6 Acceptance criteria

- [ ] `resolve_funding_source(user_id, kind, bank, last4)` returns existing `id` if canonical identity match, else creates + returns new id
- [ ] Embed-in-picker discovery: new funding source detected → prepend `📥 Phát hiện TK mới: {display_id}` header to category picker (single message per FE §3.1)
- [ ] Archive ≠ delete: FK preserved, history queryable, `status='archived'` only
- [ ] `/accounts` lists active sources sorted by `last_tx_at desc` with spent/income tháng này
- [ ] Rename `nickname` updates display everywhere (reports, picker, /accounts)
- [ ] Cross-user isolation: User A funding sources NEVER in User B queries (integration assert)
- [ ] W0.7 xfail contract pin `test_persisted_tx_has_resolved_funding_source_id` remains xfail (transaction-capture owns the flip — funding-sources doesn't enforce yet)
- [ ] All 18 tests green; multi-tenant isolation tests pass

### 2.7 Risk profile

- **Schema dependency:** DDL landed W0.2 (per memory). If transaction-capture surfaces edge case needing column tweak → new migration, NOT rewrite of W0.2.
- **Cascade impact:** transaction-capture cutover depends on funding-sources resolver working. Resolver bug = transaction-capture blocker.
- **Mitigation:**
  - Test plan covers cross-user isolation (memory rule)
  - Integration test exercises `resolve` from transaction-capture's perspective (mocked, but contract-shaped)
  - Codex 2× clean for P1

---

## 3. Shared context

### 3.1 i18n strategy (locked 2026-05-13)

- onboarding-start + funding-sources use `i18n/vi.py` stub from W0.4 — **VI-only** for all user-facing strings
- i18n-locale-switcher PR (tracker row, currently ❌) will:
  - Add `i18n/en.py` with key parity
  - Expand stub `t(locale, key)` → full module with fallback rules
  - Update onboarding-start/funding-sources handlers to call `t(user.locale, ...)` instead of `t('vi', ...)`
- onboarding-start + funding-sources must NOT add EN keys themselves — single owner for EN parity = i18n-locale-switcher PR

### 3.2 Parallel execution rule

Memory `feedback_concurrency_one_session` — STRICT 1 Claude Code session per `.git/`. settings saga had 3 ref-clobber incidents. **Solution: git worktree.**

```bash
cd ~/Projects/MyMoneyWent
git worktree add ../MyMoneyWent-F01 -b feat/F01-onboarding-start main
git worktree add ../MyMoneyWent-F08 -b feat/F08-funding-sources main
```

Each worktree shares `.git/objects` but has independent index + HEAD. Run Claude Code separately in each.

### 3.3 Kickoff order (staggered)

1. **onboarding-start kickoff first.** Stable for 1-2 hours (lockdown verified by autopilot's pre-flight gate, first commits land cleanly).
2. **funding-sources kickoff after onboarding-start stable.** Rationale: onboarding-start lockdown may surface design conflict in users table that affects funding-sources FK. Staggered start avoids re-lockdown funding-sources.
3. Cowork session (this conversation) stays in repo root for orchestration + tracker updates.

### 3.4 Merge order

onboarding-start and funding-sources are independent (no overlapping files). Either can merge first. Recommend:
- onboarding-start merge first if both READY (smaller, simpler, lower risk)
- funding-sources rebases onto post-onboarding-start main before merge (handles any minor `i18n/vi.py` or `core/handlers/__init__.py` conflict)

### 3.5 Post-merge tracker updates

When PR merges, update `docs/implementation-tracker.md`:
- onboarding-start row: ⬜ → ✅
- funding-sources row: ⬜ → ✅
- Phase 2 progress summary section 5
- Changelog entry

Pre-commit hook (W0.9) will auto-rebuild dashboard.{html,md} when tracker.md is staged.

---

## 4. Handoff to Claude Code (autopilot prompt generation)

### 4.1 Why split work

This lockdown doc + autopilot prompt template = enough input for Claude Code to generate full autopilot prompts WITHOUT additional founder input. Cowork session stays light (orchestration); Claude Code in worktree does the heavy prompt drafting.

### 4.2 In onboarding-start worktree (`~/Projects/MyMoneyWent-F01`)

Paste to Claude Code:

```
Generate `docs/autopilot/prompts/onboarding-start-autopilot.md` following the 15-section
template in `docs/autopilot/autopilot-prompt-template.md` STRICTLY.

Source of truth for onboarding-start-specific content:
- Lockdown doc: docs/operations/feature-lockdown-decisions.md §1 (Branch, risk header, scope,
  decision lockdown, files touched, test plan, acceptance criteria, risk profile)
- Implementation plan: docs/implementation-plans/phase-2-handlers.md §1
- FE spec: docs/features/feature-onboarding.md (only §4 domain model + §6 error codes
  apply to onboarding-start minimal scope — ignore Path A/B/C/D)
- BE tech: docs/features/BE/feature-onboarding-tech.md (stale vs FE; use §2.2 queries
  + §4.1 state machine + §4.2 token format; ignore Path A/B/C bot_state steps)

Constraints:
- Risk P1, manual_only merge, Codex 2× clean (per lockdown §1.1)
- Single-phase scope (no multi-phase batches per memory feedback_autopilot_prompt_scope)
- VI-only strings via i18n/vi.py stub (per lockdown §3.1)
- Pre-flight gate must verify: clean git status, baseline tests pass (118+ baseline post-W0.9), W0.7 xfail pin intact
- Atomic commit plan with pre-written messages
- 13+ circuit breakers (incl. memory feedback_autopilot_prompt_template universal 12)
- TDD gate: 12 tests must fail on main pre-impl, pass post-impl

Output: full prompt at `docs/autopilot/prompts/onboarding-start-autopilot.md`. Verify
locally builds cleanly (no broken refs to non-existent files). Commit on branch
feat/F01-onboarding-start: `docs(autopilot): onboarding-start prompt`.

Do NOT begin execution yet — just generate the prompt. Founder will review then say
'kick off onboarding-start' to start autopilot.
```

### 4.3 In funding-sources worktree (`~/Projects/MyMoneyWent-F08`)

Same pattern, swap onboarding-start → funding-sources:

```
Generate `docs/autopilot/prompts/funding-sources-autopilot.md` following the
15-section template.

Source of truth: lockdown doc §2 + plan §5 + FE spec feature-funding-sources.md +
BE tech feature-funding-sources-tech.md + memory project_f08_funding_sources.

Constraints (same shape as onboarding-start): Risk P1 manual_only, Codex 2×, single-phase, VI-only,
no W0.7 xfail flip (transaction-capture owns), 18 tests TDD-first.

Output: docs/autopilot/prompts/funding-sources-autopilot.md. Commit on
feat/F08-funding-sources: `docs(autopilot): funding-sources prompt`.

Wait for founder review before execution. Do NOT begin funding-sources until onboarding-start is stable
(1-2 hours post-onboarding-start kickoff).
```

### 4.4 Anti-patterns Claude Code must avoid (per memory)

- `git push --force` (memory feedback_concurrency_one_session)
- Auto-merge on P1 (memory project_autopilot_risk_tier_policy)
- Adding `# type: ignore` without founder approval (template §3.8)
- Skip TDD (template §3.10)
- Modify tracker row from autopilot — post-merge tracker update is manual (per memory feedback_template_distillation_checks)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-13 | Initial lockdown doc for onboarding-start + funding-sources parallel execution. 3 onboarding-start decisions confirmed by founder; 5 funding-sources decisions previously locked via memory. i18n strategy: VI-only via stub, defer EN to i18n-locale-switcher PR. Worktree-based parallelism per memory feedback_concurrency_one_session. Staggered kickoff: onboarding-start first, funding-sources after 1-2hr stable. |
