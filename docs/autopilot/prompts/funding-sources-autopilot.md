# Autopilot — F08 funding-sources

> Generated 2026-05-13. Single-phase autopilot prompt per memory rules
> `feedback_autopilot_prompt_scope` (single-phase), `feedback_prefer_autopilot_prompts`,
> `feedback_autopilot_prompt_template`.
>
> Lockdown source: `docs/operations/feature-lockdown-decisions.md` §2.
> 5 decisions previously locked via memory `project_f08_funding_sources`.

---

Task: F08 funding-sources — service `resolve_funding_source` + handlers `/funding`, `/accounts`, `/banks` + embed-in-picker discovery UX.

You are working in `~/Projects/MyMoneyWent-F08` (git worktree of MyMoneyWent). NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/F08-funding-sources` (worktree-created), Codex 2× consecutive clean (P1 always), then STOP_AT_READY.

```
Risk tier:          P1
Merge policy:       manual_only
Autopilot maturity: mature
Codex review:       2x_consecutive_clean
```

**Stagger start:** Do NOT begin Pre-flight until F01 autopilot has been kicked off in `~/Projects/MyMoneyWent-F01` and is 1-2 hours stable (baseline tests + commits landing cleanly). This avoids re-lockdown if F01 surfaces user table schema issues affecting F08 FK.

---

## Context (NOT for execution, just background)

F08 is the funding-sources registry — tracking each bank account / debit card / credit card / e-wallet a user has linked. Memory `project_f08_funding_sources` locked the canonical identity `(user_id, kind, bank, last4)` and FK chain rules. DDL landed in W0.2 (`migrations/versions/0001_initial_schema.py`). This PR ships only the service + handler logic.

F02 transaction capture cutover (next big PR) depends on `resolve_funding_source` working — every `INSERT INTO transactions` must call it first. W0.7 added an xfail contract pin (`tests/integration/test_sepay_webhook.py::test_persisted_tx_has_resolved_funding_source_id`) that F02 will flip to passing. **F08 does NOT flip this xfail** — F02 owns the wire-in.

## Scope discipline

**Positive scope:**
- `core/services/funding_sources.py` (new) — CRUD + `resolve_funding_source(user_id, kind, bank, last4) -> int` canonical resolver
- `core/handlers/funding.py` (new) — `/funding`, `/accounts` commands + `/banks` alias + callback handlers for rename/hide/manual-add
- Embed-in-picker auto-discovery UX (per FE spec §3.1) — when caller passes `prepend_discovery_header=True`, return header text for category picker
- Status enum: `active` / `hidden` / `archived` (no `deleted`)
- New i18n keys in `vi.py` AND `en.py` (parity test enforces)
- 18 tests (6 positive + 5 edge + 3 error + 2 isolation + 2 contract)

**Negative scope (do NOT touch):**
- DDL — schema landed W0.2; no new migration in F08
- F02 transaction INSERT path — F02 wires `resolve_funding_source` later
- W0.7 xfail pin on `test_persisted_tx_has_resolved_funding_source_id` — F02 owns flip; F08 must NOT remove the marker
- Auto-archive cron after 180d silent — F09 owns scheduled jobs
- Email parser inference logic — Phase 5 parsers own (P-TCB/P-Cake/P-MB)
- One-off founder backfill script for legacy column-P data — runs once in F02 cutover, NOT F08
- Free tier limit on # funding sources — locked NO LIMIT (FE §2.2 #11); do not add gating
- Modify tracker `docs/implementation-tracker.md` — post-merge update is manual
- Touch F01 work — if F01 PR not yet merged at F08 start, use F01's expected user-creation contract (lockdown doc §1 acceptance criteria)

**Out-of-scope but documented:**
- EN strings polish — F-i18n PR
- Power-syntax `/reports account=credit_card:TCB-1234` filter — F05 PR will use F08 resolver

## Required reading (READ FIRST, in this order, before any code)

1. `docs/operations/feature-lockdown-decisions.md` §2 — full F08 lockdown, scope, test plan, acceptance criteria
2. `docs/implementation-plans/phase-2-handlers.md` §5 — F08 scope + 18-test plan baseline + risk notes
3. `docs/features/feature-funding-sources.md` §1-4 — canonical schema, use cases, edge cases, embed-in-picker UX. **Critical:** §2.1 #1 (auto-discovery), §2.1 #5 (hide), §2.2 #2b (kind disambiguation), §3.1 (picker embed format)
4. `docs/features/BE/feature-funding-sources-tech.md` — query patterns + unique constraint shape
5. `migrations/versions/0001_initial_schema.py` — `funding_sources` table DDL. Confirm columns: `id`, `user_id`, `kind`, `bank`, `last4`, `display_id`, `nickname`, `first_seen_at`, `last_tx_at`, `status`, `archived_at`. Verify `UNIQUE (user_id, kind, bank, last4)` constraint exists.
6. `core/settings_svc.py` (F07) — pattern reference for service module structure
7. `core/services/user_svc.py` (F01) — pattern reference for service module if F01 merged; otherwise expected shape per F01 lockdown
8. `handlers/settings.py` (F07) — pattern reference for handler with multi-state callbacks
9. `tests/integration/test_settings_happy.py` + `tests/integration/conftest.py` — DB fixture pattern
10. `i18n/vi.py` + `i18n/en.py` — existing key conventions
11. Memory: `project_f08_funding_sources` (5 locked decisions), `feedback_f07_lessons`, `project_wave0_complete`

## Pre-flight gate

```bash
cd ~/Projects/MyMoneyWent-F08

git status                                                # MUST be clean
git branch --show-current                                 # MUST be: feat/F08-funding-sources
git fetch origin && git pull --ff-only origin main
git log --oneline -3                                      # HEAD includes 0347efd (config) + ideally F01 merge if landed

source .venv/bin/activate
which python pytest pre-commit lint-imports codex

ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v                                          # MUST be green (baseline post-F07 or post-F01 if landed)
                                                          #   xfail count MUST be exactly 1 (W0.7 pin)

python scripts/build-dashboard.py                         # MUST exit 0
```

ALL must pass. If any fails → HALT and report. Record baseline test count for delta tracking.

**Critical pre-flight check:** verify `funding_sources` table columns match expectation:
```bash
psql -h localhost -U mmw_test -d mmw_test -c "\d funding_sources"
# Must show: kind, bank, last4, display_id, nickname, first_seen_at, last_tx_at, status, archived_at
# Must show UNIQUE constraint on (user_id, kind, bank, last4)
```
If schema mismatch → HALT (USERS_SCHEMA_MISMATCH circuit breaker).

## Anti-patterns (NEVER do)

* `git push --force`.
* Add `# type: ignore` — circuit breaker, founder approval needed.
* Auto-merge to main (P1 = `manual_only`).
* Flip the W0.7 xfail pin `test_persisted_tx_has_resolved_funding_source_id` — F02 owns this.
* Add migration in F08 — DDL landed W0.2; schema tweak (if needed) is separate PR.
* Touch tracker.md row content.
* Skip TDD — tests must FAIL on main pre-impl.
* Synthetic fixtures for integration tests — use real DB via `tests/integration/conftest.py`.
* Add `last4 NULL` handling — locked as empty string `''` per FE §2.2 #3.
* Treat `display_id` as canonical identity — only `(user_id, kind, bank, last4)` is. `display_id` is render-only mirror.
* Merge debit + credit card with same `last4` — locked: 2 separate entries per FE §2.2 #6.
* Add free tier limit on # funding sources — locked NO LIMIT (FE §2.2 #11).
* Auto-resurrect `hidden` status on new tx — locked: hidden is intentional, no auto-flip (FE §2.1 #9b). Only `archived` auto-resurrects (#9a).

## Numbered steps

### Step 1 — Verify branch state + autopilot state dir

```bash
git rev-parse HEAD > /tmp/F08-base-sha.txt
mkdir -p .autopilot/state/F08/codex
git log --oneline main..HEAD
```

### Step 2 — Write failing tests (TDD)

Create `tests/integration/test_funding_sources.py` (14 tests) + `tests/unit/test_funding_resolver.py` (4 unit tests).

**Positive (6, integration):**
- `test_resolve_creates_new_funding_source` — Resolve with non-existent identity → creates row, returns id
- `test_resolve_returns_existing_id` — Resolve twice with same canonical identity → returns same id
- `test_list_active_returns_sorted_by_last_tx_desc` — Multiple sources, varied `last_tx_at` → list ordered desc
- `test_archive_changes_status_keeps_fk` — Archive funding source with linked tx → status='archived', tx FK preserved
- `test_restore_reactivates_archived` — Archived source → restore → status='active', `archived_at=NULL`
- `test_resolve_miss_returns_discovery_header` — Resolve with `prepend_discovery_header=True` for new identity → returns (id, header_text). Header matches FE §3.1 format.

**Edge (5, integration):**
- `test_duplicate_canonical_identity_returns_existing` — Two `resolve` calls race (`asyncio.gather`) → exactly 1 row, both return same id (UPSERT ON CONFLICT)
- `test_archived_not_in_active_list` — Archived source not in `/accounts` default list (only with `--include-archived` flag)
- `test_cross_user_isolation_resolve` — User A resolves (TCB, bank_account, 1234) → User B resolves same → 2 separate rows (different user_id), no leak
- `test_bank_rename_preserves_resolve` — Source with `bank='TCB'`, `nickname='Lương'`; rename nickname → resolve by `(user_id, bank_account, TCB, 1234)` still returns same id
- `test_last4_empty_string_format` — Resolve with `last4=''` → row created with `last4=''`; cumulative resolves with `last4=''` return same id (empty string is comparable in UNIQUE)

**Error (3, integration):**
- `test_invalid_last4_rejected` — Resolve with `last4='12345'` (5 digits) or `last4='abcd'` → raises `ValueError`
- `test_kind_bank_mismatch_rejected` — Resolve with `kind='e_wallet', bank='TCB'` (TCB is not e-wallet ticker per `BANK_ALIASES`) → raises `ValueError`
- `test_archive_with_active_txs_triggers_reassign` — Archive source with linked active txs → status changes but tx FK preserved (no orphan); caller-side reassign flow not in F08 (just expose unblocked state)

**Isolation (2, integration):**
- `test_user_a_funding_invisible_to_user_b_picker` — User A creates funding source → User B `/accounts` does not include it
- `test_accounts_command_returns_only_caller_rows` — `/accounts` query with `user_id=A` returns only A's rows

**Contract (2, integration + unit):**
- `test_resolve_returns_int_id_matching_canonical` (unit) — Pure function: canonical identity tuple → deterministic id mapping (via DB)
- `test_w07_xfail_pin_still_xfail` (integration) — Run `pytest -m xfail tests/integration/test_sepay_webhook.py::test_persisted_tx_has_resolved_funding_source_id` → still xfail strict (F08 does NOT flip it)

Unit tests (`tests/unit/test_funding_resolver.py`):
- `test_display_id_format` — `display_id` rendered as `{bank}-{last4}` or `{bank}` if empty
- `test_bank_alias_normalization` — `"Techcombank"` and `"TCB"` normalize to same canonical
- `test_validate_last4_accepts_4_digits_or_empty`
- `test_validate_kind_against_bank_alias_table`

Run:
```bash
pytest tests/integration/test_funding_sources.py tests/unit/test_funding_resolver.py -v
# Expect: ALL FAIL (module doesn't exist yet)
```

If any passes → TDD oracle violated. HALT.

### Step 3 — Implement `core/services/funding_sources.py`

```python
"""Funding sources service (F08).

Spec: docs/features/feature-funding-sources.md.
Memory: project_f08_funding_sources (5 locked decisions).

Public surface:
  - resolve_funding_source(user_id, kind, bank, last4, *, prepend_discovery_header=False)
  - create_manual(...)
  - rename(funding_source_id, user_id, nickname)
  - set_status(funding_source_id, user_id, status)  # 'active' | 'hidden' | 'archived'
  - list_for_user(user_id, *, include_hidden=False, include_archived=False)

Canonical identity: (user_id, kind, bank, last4). last4='' (empty) NOT NULL.

Tenant safety: every public method takes explicit user_id; never trusts client input.
"""
```

Key behaviors:
- `resolve_funding_source` uses `INSERT ... ON CONFLICT (user_id, kind, bank, last4) DO UPDATE SET last_tx_at = NOW() RETURNING id` — atomic, race-safe
- When `prepend_discovery_header=True` AND row was just inserted (RETURNING id from INSERT branch, not UPDATE), return header text per FE §3.1
- `BANK_ALIASES` import from `handlers/sepay.py` legacy (used during transition — F02 will move to `markets/vn/`)
- Validation: `last4` regex `^(\d{4}|)$`; `kind` in enum; `bank` non-empty (post-normalize)

### Step 4 — Implement `core/handlers/funding.py`

```python
"""Funding handlers — /funding, /accounts, /banks (F08).

Pattern: handlers/settings.py F07 style.
"""

CB_OPEN = "funding:open"
CB_RENAME_PROMPT = "funding:rename"
CB_HIDE = "funding:hide"
CB_ADD_MANUAL = "funding:add"
# ... etc
```

Command map:
- `/funding` and `/accounts` — same view (list active + actions)
- `/banks` — legacy alias, calls same render

### Step 5 — Wire to `main.py`

Same pattern as F01 — add `/funding`, `/accounts`, `/banks` branches to `_handle_message`. Lazy import.

### Step 6 — Add i18n keys

Add to `i18n/vi.py` (and `en.py` parity):
- `funding.list_header` — "💳 Tài khoản & thẻ của bạn:"
- `funding.list_empty` — "Chưa có tài khoản nào. TX đầu tiên sẽ tự động phát hiện."
- `funding.discovery_header` — "📥 _Phát hiện tài khoản mới:_ `{display_id}` ({bank} · {kind_label})\n_Dùng /accounts để đặt tên._"
- `funding.kind.bank_account` — "TK ngân hàng"
- `funding.kind.debit_card` — "Thẻ ghi nợ"
- `funding.kind.credit_card` — "Thẻ tín dụng"
- `funding.kind.e_wallet` — "Ví điện tử"
- `funding.action_rename` — "✏️ Đổi tên"
- `funding.action_hide` — "🚫 Ẩn"
- `funding.action_add` — "➕ Thêm thủ công"
- `funding.rename_prompt` — "Nhập tên mới (tối đa 32 ký tự):"
- `funding.rename_success` — "✅ Đã đổi tên thành '{nickname}'."
- `funding.rename_too_long` — "❌ Tên tối đa 32 ký tự."
- `funding.rename_empty` — "❌ Tên không được để trống."
- `funding.hide_confirm` — "🚫 Đã ẩn `{display_id}`. Dùng /accounts --include-hidden để xem."

EN literal equivalents (F-i18n polishes).

### Step 7 — Run pytest, expect green

```bash
pytest tests/integration/test_funding_sources.py tests/unit/test_funding_resolver.py -v
# 18 passed

pytest tests/ -v
# Baseline + 18 new = all green. xfail count UNCHANGED at 1.
```

### Step 8 — Full local verify

```bash
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v
pre-commit run --all-files
```

### Step 9 — Inline Codex review (P1 → 2× consecutive clean)

```bash
codex review --base main 2>&1 | tee .autopilot/state/F08/codex/round-01.txt
# Parse findings, fix if needed
codex review --commit HEAD 2>&1 | tee .autopilot/state/F08/codex/round-02.txt
# Need 2 consecutive clean. Max 5 rounds before MAX_ROUNDS HALT.
```

Same parsing rules as F01 (P0/P1 fix, P2 opportunistic, SECURITY/ARCH/RECURRING breakers).

## Atomic commit plan

```bash
git add tests/integration/test_funding_sources.py tests/unit/test_funding_resolver.py
git commit -m "test(F08): cover funding_sources resolver + handlers — 18 tests"

git add core/services/__init__.py core/services/funding_sources.py
git commit -m "feat(F08): funding_sources service — resolve, create_manual, rename, set_status, list"

git add core/handlers/funding.py
git commit -m "feat(F08): /funding /accounts /banks handlers — embed-in-picker discovery UX"

git add core/handlers/__init__.py main.py
git commit -m "feat(F08): wire funding handlers to dispatcher"

git add i18n/vi.py i18n/en.py
git commit -m "feat(F08): i18n keys for funding list/picker/rename/hide flow"

# Codex fix commits as needed
```

## Circuit breakers

1. **Pre-flight regression** — existing tests no longer pass.
2. **TDD oracle violated** — Step 2 tests pass on first run.
3. **VERIFY_REGRESSION** — local verify fails twice consecutively.
4. **ARCH_FINDING** — Codex flags schema/breaking.
5. **SECURITY_FINDING** — Codex flags auth/token/timing/secret/injection.
6. **RECURRING_FINDING** — same hash round N and N+1.
7. **TYPE_IGNORE_PROPOSED** — anywhere.
8. **MAX_ROUNDS** — 5 Codex rounds without 2× consecutive clean.
9. **Tool error twice** in a row.
10. **Context budget >70%** — pause + report.
11. **POLICY_MISMATCH** — auto-merge attempted (manual_only only).
12. **PARITY_BROKEN** — `tests/unit/test_i18n_parity.py` fails after i18n edits.
13. **F08_SPECIFIC: SCHEMA_MISMATCH** — `funding_sources` table missing expected columns or UNIQUE constraint differs from `(user_id, kind, bank, last4)`. HALT — schema fix is W0.2-class migration, not F08.
14. **F08_SPECIFIC: XFAIL_FLIPPED** — `test_persisted_tx_has_resolved_funding_source_id` unexpectedly passes (xfail strict raises). HALT — F02 owns the flip; if F08 accidentally enabled it, the test plan or implementation is wrong-scoped.
15. **F08_SPECIFIC: BANK_ALIAS_MISSING** — `handlers/sepay.py` `BANK_ALIASES` dict not found at expected location. HALT — confirm legacy path with founder before forking.

## Halt report template

```
HALT — F08 funding-sources circuit broken.

Step:    Step <N> <substep>
Trigger: <one of 15 conditions>
Branch:  feat/F08-funding-sources
HEAD:    <SHA>

Detail:
<error / finding excerpt>

State:
- Commits since base: <list>
- Files changed: <list>
- Codex artifacts: .autopilot/state/F08/codex/round-*.txt
- Last verify: <result>
- Test count: baseline <N> → current <M> (delta +<D>)
- xfail count: <count> (expected 1, W0.7 pin)

Requesting founder input on:
<specific question>
```

## Final report — READY_FOR_MANUAL_MERGE (P1 default)

```
═══════════════════════════════════════════════════════
AUTOPILOT F08 funding-sources — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════

Squash commit:    N/A — founder/manual merge pending
Branch feat/F08-funding-sources:  still exists (ready for review)
Push origin/main: NOT RUN

Files added:
  - tests/integration/test_funding_sources.py    (~400 LOC, 14 tests)
  - tests/unit/test_funding_resolver.py          (~150 LOC, 4 unit tests)
  - core/services/funding_sources.py             (~300 LOC)
  - core/handlers/funding.py                     (~250 LOC)

Files modified:
  - core/services/__init__.py                    (export funding_sources)
  - core/handlers/__init__.py                    (export funding)
  - main.py                                       (+ /funding, /accounts, /banks dispatch)
  - i18n/vi.py                                    (+ 15 keys)
  - i18n/en.py                                    (+ 15 keys, literal English)

Codex review:
  Round 01: <findings | clean>
  Round 02: <findings | clean>
  Final state: 2 consecutive clean rounds confirmed (P1 policy)
  Artifacts: .autopilot/state/F08/codex/round-*.txt

Local verification (final):
  ruff / black / mypy / lint-imports: clean
  pytest: <N> passed (baseline <baseline>, expected ≥<baseline+18>)
  pre-commit: clean
  xfail count: 1 (W0.7 pin — UNCHANGED, F02 owns flip)

Decisions made during execution requiring founder review:
  <list any non-obvious calls — e.g., BANK_ALIASES path during transition,
   rename validation edge cases, picker header rendering>

═══════════════════════════════════════════════════════

Suggested squash command (founder runs after F01 + F08 both READY):

  git checkout main
  git pull --ff-only origin main
  # Merge F01 first if not yet merged
  git merge --squash feat/F08-funding-sources
  git commit -m "feat(F08): funding sources resolver + handlers

  Canonical identity (user_id, kind, bank, last4); status enum
  active/hidden/archived (no deleted). resolve_funding_source returns
  existing id for canonical match, else creates + returns new id (atomic
  via ON CONFLICT). Embed-in-picker discovery UX per FE spec §3.1.

  Handlers: /funding, /accounts, /banks (legacy alias). Multi-tenant safe
  via session-derived user_id, callback data never trusted for tenant.

  Memory: project_f08_funding_sources (5 decisions locked 2026-05-11).
  Spec: docs/features/feature-funding-sources.md.

  Test plan (18): 6 positive + 5 edge + 3 error + 2 isolation + 2 contract.
  W0.7 xfail pin remains xfail (F02 owns flip).

  Unblocks: F02 transaction capture cutover (resolve_funding_source ready
  to wire into _persist INSERT path)."
  git branch -D feat/F08-funding-sources
  git push origin main

Post-merge actions (founder):
  - Pull main in Cowork session repo
  - Update implementation-tracker.md F08 row ⬜→✅, bump changelog
  - Pre-commit auto-rebuilds dashboard.{html,md}

═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1. **Reminder: stagger after F01 stable (1-2hr post-F01 kickoff).**
