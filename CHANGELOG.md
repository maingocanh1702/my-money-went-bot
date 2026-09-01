# Changelog

## Audit 2026-08-25 round 2 — Zalo flow-integrity parity + UX (unreleased)

Full repo re-audit focused on UX. Zalo now has the same "never lose a
transaction, never clobber the user's typing" guarantees Telegram got in
round 1, plus several dead-ends removed. See `audit-2026-08-25-round2.md`.

### Zalo flow integrity (parity with round 1's Telegram fixes)
- **Durable pending queue** (`handlers/zalo_queue.py`, state key
  `zalopq:<chat>`): a webhook arriving while the Zalo user is mid-flow
  (manage/allocate/keywords/cashback/wizard/...) no longer overwrites their
  state — the tx is parked and a notice points at the new Zalo **/pending**
  command. Running a command over an active numbered picker parks the
  picker's transactions too (Zalo picker numbers die with their state —
  unlike Telegram inline buttons). `/cancel`, `/start`, finalize summaries
  all surface the parked count.
- **/recat parity**: no-arg `/recat` now shows the 8-most-recent numbered
  picker on Zalo; transfer/cc_payment rows are refused (2-leg ledger
  protection — recategorizing them corrupted balances); cross-month recat
  uses the transaction's OWN month for buckets + summary (was "now").
- The unknown-MCC cashback learn picker no longer clobbers a busy Zalo
  state (skipped with a log; the Telegram picker still asks).
- Zalo rule-edit prompts were sending the raw i18n key (`cb.rf_name`) —
  now translated.
- Zalo daily summaries localize naive timestamps (evening tx no longer
  shifts +7h onto the wrong day) and use proper Vietnamese diacritics.

### Daily cap editable in-chat (dead-end fixed)
- `/today` said "dùng /manage để bật cap" but /manage had no such option —
  the cap was only editable by hand in the sheet. Now: Telegram `/manage` →
  Daily Spending → **⏰ Daily cap** button; Zalo `/manage` → bucket menu
  option **5**. `0` turns the cap off. i18n'd (vi+en).

### Other UX
- `/help`, `/start` moved to i18n — the command list now follows `/lang`.
- Zalo `/help` added (alias of /start); Zalo command list completed
  (+/cashback, /pending, /lang, money-shorthand tip).
- `ac.unmapped` i18n string rendered a literal `\n\n` in chat — fixed, and
  the onboarding prompt now actually uses the i18n string.
- Stale-tx guard windows configurable: `TX_MAX_AGE_MINUTES` (default 10) /
  `EMAIL_TX_MAX_AGE_MINUTES` (default 1440) — raise if the bot can be down
  longer than 10' (late SePay retries were silently skipped).

### Docs
- README (EN+VI): features/roadmap/project-layout caught up with reality
  (cashback, email ingestion, Zalo, i18n, multi-currency — all shipped but
  still listed as "deferred"); test badge un-staled.
- `crontab.txt`: documents that **daily-recap has no schedule anywhere**
  (endpoint + GH-Actions manual dispatch exist) + a ready-to-enable entry.

### Tests
- +26 tests: `test_zalo_pending_queue.py`, `test_zalo_recat_parity.py`,
  `test_manage_daily_cap.py`, `test_i18n_and_prompts.py` (incl. vi/en key
  parity + no-literal-`\n` guards).

## Audit 2026-08-25 — security hardening + input UX (unreleased)

Full repo audit (code + docs). All findings implemented; suite green.

### Security (all opt-in via env — existing deploys unaffected until enabled)
- **Telegram webhook auth**: `/webhook` now validates the
  `X-Telegram-Bot-Api-Secret-Token` header when `TELEGRAM_WEBHOOK_SECRET` is
  set (re-register the webhook with the same `secret_token`). Previously ANY
  POST with an `update_id` was processed.
- **Owner-only dispatch**: `_handle_message` / `_handle_callback` now reject
  chats other than `CHAT_ID` (previously unchecked — a forged update could
  drive `/manage`, `/allocate`, ... against the owner's data).
- **Callback validation**: callback_query shape + prefix allowlist +
  min-part checks before dispatch (`_validate_callback`).
- **Cron auth**: `/trigger/*` endpoints require `?secret=<CRON_SECRET>` when
  `CRON_SECRET` is set (crontab.txt updated). Startup logs a warning listing
  any unset secrets.
- **Config fail-fast**: missing `BOT_TOKEN`/`CHAT_ID`/`SHEET_ID` now exits
  with a clear message instead of a KeyError traceback.
- Removed a per-request debug print of full transaction rows (PII) from
  `get_daily_status`.

### Input UX — money shorthand + no more silent mis-reads
- New `utils.parse_money` used by EVERY amount input (TG + Zalo): understands
  `500k`, `3tr`, `3tr5`, `1m2`, `2 triệu`, `1 tỷ` alongside `3.000.000` /
  `3,000,000` / decimals. Previously "500k" was digit-stripped to **500đ**.
- Budget inputs (`/allocate`, `/manage`, Zalo menus, cashback cap) now REJECT
  garbage — "abc" used to silently become 0đ and flip a bucket to
  tracking-only. Fixed the accounts wizard rejecting dotted amounts
  ("30.000.000" was unparseable in the credit-limit step).

### Flow integrity
- **pending_tx_queue (Telegram)**: a webhook arriving while the user is
  mid-typing (keyword, rename, budget, wizard, cashback config) no longer
  clobbers their state — the tx is queued; new `/pending` command drains it.
  Queue survives command-clears, `/cancel`, recat, and skip.
- **Auto-categorize no longer touches BOT_STATE** (`_finalize(tx_info=...)`)
  — it used to overwrite whatever the user was doing.
- **/recat**: no-arg mode shows the 8 most recent tx as buttons; row mode kept.
  Cross-month recat now uses the transaction's own month (was "now"), and
  transfer/cc_payment rows are refused (recategorizing them corrupted the
  2-leg ledger). `_finalize` parses dd/mm/yyyy sheet dates tolerantly.
- `/help` + `/start` commands added (previously "unknown command");
  setMyCommands list completed; unknown-command reply points at /help.

### Docs
- README (EN+VI): full command table (+`/cashback`, `/transfer`, `/cc`,
  `/recat`, `/pending`, `/lang`, `/help`), shorthand note, security section
  rewritten with the 4-secret table. `.env.example` + `crontab.txt` document
  the new secrets.

## Cashback read-efficiency (429 fix) (unreleased)

Fixes the 2026-06-09 Sheets 429 incident ('Read requests per minute per user')
on `/cashback seed cake` and per-tx cashback. Same cashback output, far fewer reads.

### Fixed
- **recompute_cashback_for_tx** now reads the Transactions tab + Cashback Ledger
  **once each** and rebuilds the whole statement cycle **in memory** (running
  mcc-used / daily-count / eligible-spend, then batch void + batch append) —
  was O(N) per-row ledger reads (~4×N) that burst to hundreds at end-of-cycle.
  Semantics unchanged (cycle-wide, chronological, RLock-serialized); ledger
  output is byte-identical (parity-tested). Forces a fresh tx read so a
  just-appended/updated tx is never missed.
- **seed_cake_card** now batches: new bulk helpers `add_cashback_rules_bulk` /
  `add_mcc_maps_bulk` read each tab **once** and batch-write (was add_* per item
  → ~28 reads → 429). Output rows identical to the canonical `add_*`; idempotent;
  bulk rule helper dedupes duplicate ids within a batch. Tiers seeded in one write.

### Notes
- `add_cashback_rule` / `add_mcc_map` signatures unchanged (`/cashback add`, `mcc`
  still use them); bulk = additive new functions.
- `compute_and_record_cashback` (single-tx) unchanged — still the recompute fallback.
- New `tests/unit/test_cashback_readcount.py` pins ledger/seed reads to O(1) +
  asserts cross-day parity.

## Cashback Phase B — live integration (webhook + /cashback + recat + /report) (unreleased)

Wires the Phase A cashback foundation into the live transaction flow + adds the
`/cashback` management command. Telegram + Zalo. Builds on Phase A (merged).

### Added / Changed
- **Phase 1 (harden):** `recompute_cashback_for_tx` now rebuilds the whole
  **statement cycle** in timestamp order (was same-day), under a reentrant
  `tx_write_lock` (RLock) so concurrent webhooks for a cycle can't interleave.
  Absorbs the Phase A "out-of-order arrivals" + "cross-day MCC-cap" deferrals.
- **handlers/sepay.py** — webhook hook on the outgoing/credit path (before the
  auto-categorize branch): `recompute_cashback_for_tx` → FR-2.5/2.7 notice +
  FR-2.6 gate-activation notice. try/except, never blocks the tx write.
- **sheets.py** — `backfill_account_id_by_source_key` recomputes cashback for a
  newly-onboarded credit card's cycles (incl. the already-stamped trigger row).
- **handlers/cashback.py (NEW)** — `/cashback`: card menu, `seed cake`
  (BRD §4.4: 5 rules + tiers + config + MCC patterns; credit-validated),
  recompute (accepts short `2026-06` or full cycle id), Config/MCC/Add-rule
  wizards. Telegram inline; Zalo numbered-text (seed + recompute; advanced
  config is Telegram-only — see Residuals).
- **handlers/transaction.py** — recat: `void_cashback_for_tx` on reset +
  `recompute_cashback_for_tx` on finalize (state-flag gated). Mirrored in the
  Telegram + Zalo `/recat <row>` command paths (main.py).
- **handlers/report.py** — `render_cashback_section(period)` appended to BOTH
  lenses (category + account), on Telegram **and** Zalo. Hidden when no credit
  card has cashback configured. Rate now inherits card config (blank rule rate).
- **main.py** — `/cashback` command + `cb_*` callbacks + text-steps, Telegram & Zalo.
- **tests** — `test_cashback_hardening.py`, `test_cashback_email_flow.py`,
  `test_cashback_command.py`, `test_cashback_recat.py`, `test_cashback_report.py`.

### Residuals (deferred, founder-reviewable; Cake unaffected)
- `/report` cashback section shows the **current statement cycle** (honestly
  labeled), not period-filtered totals for week/quarter/year (FR-3.4 partial).
- Zalo `/cashback` exposes seed + recompute only; rule/MCC/Config wizards are
  Telegram-only (menu points there).
- Still deferred from Phase A: activation-gate **demotion** on refund,
  rule `effective_from/to` windows (§4.3), non-stackable multi-rule priority (§4.7).

## Cashback Phase A — data layer + pure engine + CRUD/orchestrator (unreleased)

Foundation for credit-card cashback tracking (BRD `brd-cashback-tracking.md` v5.1,
plan `implementation-plan-cashback.md` v1.5.0). **Additive only — NOT yet wired to
the live webhook/`/report`/`/cashback` flow** (that is Phase B). Unit-tested end to end.

### Added
- **config.py** — 5 sheet-tab constants: `CASHBACK_RULES`, `CASHBACK_TIERS`,
  `CASHBACK_CONFIG`, `CASHBACK_LEDGER`, `MCC_MAP`.
- **sheets.py — schema:** `_last_col_letter(n)`; 5 `*_HEADER` + `_ensure_*_tab`
  bootstrappers (dynamic `A1:{last}1` range, ledger has audit `reason` col M).
- **sheets.py — CRUD:** rules (get/add/update/soft_delete; unique rule_id with
  reactivation), tiers (get), card config (get/upsert), MCC map (get/add/`match_mcc`),
  ledger (append/get/`void_cashback_for_tx`/`promote_pending_to_eligible`); in-memory
  caches + `invalidate_cashback_caches()` (ledger uncached).
- **sheets.py — cycle helpers:** `cycle_id` (statement-cycle, Asia/Ho_Chi_Minh),
  `eligible_spend_in_cycle`, `daily_eligible_count` (both with `exclude_tx_row`).
- **sheets.py — orchestrator:** `compute_and_record_cashback` (idempotent void-then-write,
  activation gate promote, FR-2.7 daily-limit flags) and `recompute_cashback_for_tx`
  (whole-day chronological rebuild).
- **handlers/cashback_engine.py** — pure `compute_cashback` per BRD §4.6 (MCC eligibility,
  daily limit, per-tx tier cap, per-MCC cycle cap, min-tx threshold, activation gate),
  rounded VND, no I/O.
- **tests** — `test_cashback_engine.py`, `test_cashback_schema.py`, `test_cashback_sheets.py`
  (47 tests).

### Fixed
- **Accounts tab header truncation:** `_ensure_accounts_tab` hardcoded `A1:O1` while
  `ACCOUNTS_HEADER` already had col P+ → a freshly-created Accounts tab lost
  `starting_outstanding`. Now uses a dynamic range. Header extended to col R with
  `linked_credit_id`, `redeem_only` (cashback wallet, declared for Phase B).

### Deferred to Phase B (founder review 2026-06-09, documented in code)
These known P2 edge cases are out of Phase A scope (live-flow / `/cashback recompute`
rescue command / BRD fields Cake doesn't exercise):
- Out-of-order live arrivals don't rebuild the day; activation gate only promotes
  (pending→eligible), never demotes when cycle spend later drops below the threshold.
- `recompute_cashback_for_tx` rebuilds only the same **day**, not the whole statement
  cycle (cross-day MCC-cap dependents can stay stale).
- Rule `effective_from`/`effective_to` windows (§4.3) are not enforced.
- Multiple non-stackable rules matching one MCC each emit a line (§4.7 says priority
  winner only) — harmless for Cake (one rule per MCC).
