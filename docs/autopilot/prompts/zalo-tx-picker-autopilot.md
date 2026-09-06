Task: Zalo interactive category picker for uncategorized expenses — make Zalo-only categorization work — feature/single-PR (Phase 2 of 3)

You are working in /Users/maingocanh/Projects/My Money Went Bot, the public OSS "My Money Went Bot" (FastAPI + Google Sheets; Telegram + Zalo front-ends; state in the Sheet). NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/zalo-tx-picker`, inline Codex review, then STOP_AT_READY. Pause ONLY on circuit-breaker conditions. Do NOT merge or push.

─────────────────────────────────────────────
Risk header (REQUIRED)
  Risk tier:          P1            # SePay path + Sheet finalize + new Zalo state machine
  Merge policy:       manual_only   # STOP_AT_READY
  Autopilot maturity: pilot
  Codex review:       2x_consecutive_clean
  RULE: P1 -> manual_only, 2 consecutive clean. Any auto-merge attempt -> POLICY_MISMATCH -> HALT.

NOTE — repo toolchain (no orchestrator): gates are `ruff check .` + `python -m pytest -q` only
(.github/workflows/ci.yml). No mypy/black/lint-imports/CHANGELOG.

─────────────────────────────────────────────
Context (NOT for execution, just background)
  Origin:     Phase 2 of "independent channels". Phase 1 (merged) made Telegram optional so the bot boots
              Telegram-only / Zalo-only / both. Gap it left: on Zalo-only, an uncategorized expense (no
              keyword match) only gets a plain-text "use /keywords" notice in handlers/sepay.py — there is
              NO way to categorize that specific transaction from Zalo. Codex flagged this (R5 P2).
  Goal:       Give Zalo a numbered-menu category picker for uncategorized expenses, mirroring the existing
              Zalo numbered flows (/keywords, /manage), so a Zalo-only user can categorize each expense.

─────────────────────────────────────────────
Scope discipline
  Positive scope: ONLY add a Zalo numbered category picker for the uncategorized OUTGOING-expense branch:
    (1) When Telegram is disabled and Zalo enabled, SePay's uncategorized-expense branch sends a numbered
        bucket menu to Zalo (instead of the Phase-1 plain-text notice) and sets a `zalo_tx_pick` state.
    (2) A numbered reply categorizes that row: write category + ledger, send a plain-text logged summary.
    (3) If a second uncategorized tx arrives while one is pending, QUEUE it (don't clobber state); promote
        the next queued item after the current one is resolved.
  Negative scope: Do NOT change the Telegram path (the `if TELEGRAM_ENABLED:` branch stays exactly as is —
    Telegram and Zalo pickers are MUTUALLY EXCLUSIVE per that if/else, so there is NO cross-channel race).
    Do NOT touch transaction.py::_finalize / handle_parent_selected (Telegram). Do NOT change Sheet schema.
  Documented-out (DO NOT start here):
    * "0 = create new category" on Zalo (Bot Finance offers it) — Phase 2b. Phase 2 = pick from EXISTING
      active buckets only; invalid/0 -> reprompt with the menu.
    * Zalo account-onboarding picker (prompt_new_account is still Telegram-only / no-ops on Zalo) — Phase 2b.
      Note this remaining limitation in the READY report.

─────────────────────────────────────────────
Required reading (READ FIRST, in this order, before any code)
  1. `handlers/sepay.py` — the uncategorized-expense branch added in Phase 1 (the `if TELEGRAM_ENABLED: ...
     else: await notifier.send_text(... /keywords ...)`). The `else` is what you replace with the Zalo picker.
     Also note the income / auto-categorize paths already fan out via notifier (Telegram+Zalo).
  2. `main.py` — `_process_zalo` (reads incoming Zalo event: sender id, chat id, text); `_handle_zalo_text`
     (step router — you add a `zalo_tx_pick` branch); the existing `_zalo_kw_handle_list_reply` /
     `_zalo_mg_*` numbered-reply handlers (MIRROR their idiom: `text.isdigit()`, 1..len bounds, reprompt on
     invalid); how Zalo state is keyed and how `zalo.send_text(msg, chat_id)` is called; `ZALO_CHAT_ID`.
  3. `handlers/transaction.py` — `_finalize` (the Telegram budget-feedback message logic) and
     `_apply_ledger_for_row`. Your Zalo summary mirrors `_finalize`'s outgoing/income/daily branches in
     PLAIN TEXT (no inline buttons); reuse the same sheet helpers.
  4. `sheets.py` — `get_active_buckets(month_key)`, `finalize_transaction`, `get_bucket_status`,
     `get_daily_status`, `get_income_total`, `get_transaction_row`, `fmt_amount`, `make_bar`, `calc_pct`,
     `bucket_label`, `fmt_month`, `set_state`/`get_state`/`clear_state`. Schema: row[5]=desc, row[6]=type,
     row[7]=amount, row[14]=month, row[15]=currency.
  5. `tests/conftest.py` (fake_ss) + `tests/unit/test_independent_channels.py` (Zalo/monkeypatch style).

─────────────────────────────────────────────
Pre-flight gate (HARD GATE)
  Precondition: exactly ONE git-writing session on this repo.
  cd "/Users/maingocanh/Projects/My Money Went Bot"
  git status                      # MUST be clean (Phase 1 already merged to main)
  git branch --show-current       # MUST be: main
  git fetch origin && git pull --ff-only origin main
  ls .git/*.lock 2>/dev/null      # MUST be empty
  # Local Python is uv-managed (PEP 668) — use the repo .venv; NEVER pip into system Python.
  [ -d .venv ] || python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt -q
  pip install ruff -q
  CODEX="${AUTOPILOT_CODEX_BIN:-$HOME/Library/Application Support/crawbot/nodejs/bin/codex}"
  [ -x "$CODEX" ] && [ "$("$CODEX" review --base main 2>/dev/null | head -c1 | wc -c)" -gt 0 ] \
    || { echo "CODEX_UNAVAILABLE -> HALT"; exit 1; }
  ruff check .                    # MUST be clean
  python -m pytest -q             # MUST be green — RECORD BASELINE_N (expect 168 after Phase 1)
  ALL must pass. If any fails -> HALT and report.

─────────────────────────────────────────────
Anti-patterns (NEVER do — each with reason)
  * `git push --force`; auto-merge/push (P1 manual_only -> POLICY_MISMATCH); `# type: ignore`.
  * Touch the Telegram path (`if TELEGRAM_ENABLED:` branch, transaction.py::_finalize) — out of scope; the
    two pickers are mutually exclusive, keep them that way.
  * Use the CURRENT month for bucket lookup/finalize — use the TRANSACTION'S OWN month (row[14]). Reason:
    the /recat pilot bug was exactly using now() instead of the row's month; do not repeat it.
  * Store picker state under a key different from the one `_handle_zalo_text` reads on reply. Reason: the
    picker is sent server-side (SePay webhook) to ZALO_CHAT_ID, but the reply arrives via _process_zalo with
    the event's chat_id — they MUST be the same key or the numbered reply won't route. Verify + test this.

─────────────────────────────────────────────
Step 1 — branch + state dir
  git checkout -b feat/zalo-tx-picker
  git rev-parse HEAD > /tmp/zalo-tx-picker-base-sha.txt
  mkdir -p .autopilot/state/zalo-tx-picker/codex     # forensic only; NEVER git add

─────────────────────────────────────────────
Step 2 — write FAILING tests first (TDD)
  File: tests/unit/test_zalo_tx_picker.py. Use fake_ss + monkeypatch zalo.send_text to a recorder.
  Cover:
  * Zalo-only + uncategorized expense -> a numbered bucket menu is sent to ZALO_CHAT_ID AND state is set to
    step "zalo_tx_pick" with row_num/amount/currency/description/month_key(row[14])/buckets/queue=[].
  * Numbered reply "2" -> finalize_transaction called with the 2nd active bucket; row category written;
    _apply_ledger_for_row invoked; a plain-text "Logged: ..." summary sent; state cleared.
  * Reply uses the ROW's month (seed buckets only for the row's old month; assert that bucket set is used).
  * Invalid reply ("9" out of range / non-numeric) -> reprompt with the menu, state unchanged.
  * Queue: a 2nd uncategorized tx while one is pending -> appended to queue (state not clobbered); after the
    first is resolved, the queued row is promoted (menu re-sent, state = that row).
  * Telegram-enabled (both channels) -> the Zalo picker branch is NOT taken (Telegram `if` branch runs);
    no zalo_tx_pick state set. (Mutual exclusivity.)
  Run pytest on the new file — MUST FAIL on current main. If they pass first -> TDD oracle violated.

─────────────────────────────────────────────
Step 3 — handlers/zalo_render.py (NEW): plain-text logged summary
  Create `render_zalo_logged_summary(*, row_num, bucket_id, sub_label, amount, tx_date, tx_direction,
  currency) -> str` that mirrors transaction.py::_finalize's message for income / foreign / daily / budgeted
  / tracking-only branches, in PLAIN TEXT (no inline buttons), computing month from tx_date (fallback now),
  and ending with "Sai mục? gửi /recat <row_num>". Reuse sh.get_bucket_status/get_daily_status/
  get_income_total/fmt_amount/make_bar/calc_pct/bucket_label/fmt_month. Keep it a pure render (no sends).

─────────────────────────────────────────────
Step 4 — handlers/sepay.py: send the Zalo picker (replace the Phase-1 plain-text else)
  In the uncategorized OUTGOING-expense branch, keep `if TELEGRAM_ENABLED:` exactly as is. Replace the
  `else:` (Phase-1 notifier.send_text notice) with: if ZALO_ENABLED, build active buckets for the row's
  month, and either set the picker state + send the menu, or queue if one is already pending:
    state_key = ZALO_CHAT_ID
    item = {"row_num": row_num, "amount": amount, "currency": currency, "description": description,
            "tx_direction": "out", "month_key": <row's month>,
            "buckets": [{"id": b["id"], "name": b["name"]} for b in buckets]}
    existing = sh.get_state(state_key) or {}
    if existing.get("step") == "zalo_tx_pick" and existing.get("row_num"):
        # already prompting -> append to queue if not already pending
        queue = existing.get("queue") if isinstance(existing.get("queue"), list) else []
        pending = {existing["row_num"]} | {q["row_num"] for q in queue if isinstance(q, dict)}
        if row_num not in pending:
            queue.append(item); sh.set_state(state_key, {**existing, "queue": queue})
        await zalo.send_text(f"Thêm giao dịch cần phân loại (-{sh.fmt_amount(amount, currency)} {description}). Đã xếp hàng.", state_key)
    else:
        sh.set_state(state_key, {"step": "zalo_tx_pick", **item, "queue": []})
        await zalo.send_text(f"-{sh.fmt_amount(amount, currency)}\n{description}\n\nKhoản này thuộc mục nào?\n\n{_format_zalo_bucket_options(item['buckets'])}", state_key)
  If ZALO_ENABLED is false (neither channel can prompt — shouldn't happen post-config-validation), keep a
  minimal notifier.send_text notice. Embed this tiny helper (in main.py or a shared util):
    def _format_zalo_bucket_options(buckets: list[dict]) -> str:
        return "\n".join(f"{i+1}. {b['name']}" for i, b in enumerate(buckets))
  (Phase 2 has NO "0 = new category" — that's 2b.)

─────────────────────────────────────────────
Step 5 — main.py: handle the numbered reply + finalize + queue
  * Add `elif step == "zalo_tx_pick": await _zalo_handle_tx_pick(text, chat_id, state)` to `_handle_zalo_text`.
  * `_zalo_handle_tx_pick(text, chat_id, state)`: mirror `_zalo_kw_handle_list_reply` idiom. Parse number ->
    map to state["buckets"][idx-1]; out-of-range/non-numeric -> reprompt with `_format_zalo_bucket_options`.
    On valid pick -> `_zalo_finalize_tx(chat_id, state, bucket_id)`.
  * `_zalo_finalize_tx(chat_id, state, bucket_id)`: sh.finalize_transaction(row_num, bucket_id, "");
    try _apply_ledger_for_row(row_num); build summary via render_zalo_logged_summary(... month from
    state["month_key"]/row ...); then if state["queue"] non-empty -> promote next item (re-send its menu,
    set state to it with the remaining queue, send the summary as a prefix) ELSE clear_state + send summary.
  * Verify the state key: the picker is stored under ZALO_CHAT_ID (Step 4); `_process_zalo` must read state
    by the same chat_id it dispatches with. If `_process_zalo` keys state by the event chat_id, ensure that
    equals ZALO_CHAT_ID for the authorized user (it does — ZALO_USER_ID gate). Add a test asserting the
    reply routes to the pending picker.

─────────────────────────────────────────────
Step 6 — Local verify
  ruff check . && python -m pytest -q     # green; BASELINE_N + new tests; previously-failing tests pass
  Verify fails twice consecutively -> VERIFY_REGRESSION -> HALT.

Atomic commit plan
  git add tests/unit/test_zalo_tx_picker.py && git commit -m "test(zalo): numbered category picker + queue + month + mutual-exclusion"
  git add handlers/zalo_render.py && git commit -m "feat(zalo): plain-text logged summary renderer"
  git add handlers/sepay.py && git commit -m "feat(zalo): send numbered picker for uncategorized expense (Zalo-only)"
  git add main.py && git commit -m "feat(zalo): handle picker reply, finalize, and queue"

─────────────────────────────────────────────
Step R — Inline Codex review (max 5 rounds; target 2 consecutive clean)
  Use "$CODEX". Before each round assert `git branch --show-current` == feat/zalo-tx-picker (else STALE_REVIEW).
  "$CODEX" review --base main 2>&1 | tee .autopilot/state/zalo-tx-picker/codex/round-NN.txt
    (0 bytes/error -> CODEX_UNAVAILABLE -> HALT; never substitute manual review.)
  P0/P1 -> fix; P2 -> opportunistic; schema|breaking|architectural -> ARCH_FINDING HALT;
  auth|token|secret|injection|timing -> SECURITY_FINDING HALT; same hash N&N+1 -> RECURRING_FINDING HALT.
  Fix -> re-verify green -> commit "fix(zalo): address codex round NN — <summary>".
  REGION_THRASH: if findings keep hitting the SAME new region across >=3 rounds (each a new edge), STOP and
  consider revert-to-lean instead of patching the next edge -> REGION_THRASH breaker.
  Need 2 consecutive clean rounds; 5 without it -> MAX_ROUNDS -> HALT (do not soft-land to READY).

─────────────────────────────────────────────
Merge gate
  P1 / manual_only -> STOP_AT_READY. Do NOT merge/commit-to-main/push. Branch stays intact. Emit READY + exit.

Circuit breakers: PREFLIGHT_REGRESSION, TDD_ORACLE_VIOLATED, VERIFY_REGRESSION, ARCH_FINDING,
  SECURITY_FINDING, RECURRING_FINDING, TYPE_IGNORE_PROPOSED, MAX_ROUNDS, TOOL_ERROR_2X, CONTEXT_BUDGET_70,
  POLICY_MISMATCH, WRONG_BRANCH_HEAD, STALE_REVIEW, REGION_THRASH, CODEX_UNAVAILABLE. Task-specific:
  STATE_KEY_MISMATCH (picker reply does not route to the pending state) -> HALT.

On HALT: emit forensic report (Step/Trigger/Branch/HEAD/Detail/State/question); do NOT clean the branch.

─────────────────────────────────────────────
Final report — READY (emit verbatim)
  ═══════════════════════════════════════════════════════
  AUTOPILOT zalo-tx-picker — READY_FOR_MANUAL_MERGE
  ═══════════════════════════════════════════════════════
  Squash commit:    N/A — manual merge pending
  Branch feat/zalo-tx-picker: intact, ready for review
  Push origin/main: NOT RUN
  Files added:    handlers/zalo_render.py, tests/unit/test_zalo_tx_picker.py
  Files modified: handlers/sepay.py, main.py
  Codex review: Round 01..NN <findings|clean>; Final: 2 consecutive clean confirmed; artifacts: .autopilot/state/zalo-tx-picker/codex/round-*.txt
  Local verification: ruff clean; pytest <count> passed (baseline 168, expected 168 + <new>)
  Known limitations (Phase 2b): no "create new category" on Zalo (use /manage); Zalo account-onboarding for
    an unmapped source is still Telegram-only (no-ops on Zalo).
  Decisions needing founder review: <non-obvious calls, else none>
  Post-merge smoke checklist:
    - [ ] Zalo-only: uncategorized expense -> numbered menu; reply a number -> row categorized + summary
    - [ ] Zalo-only: two quick uncategorized tx -> second queues, promoted after first resolved
    - [ ] Both channels: uncategorized expense -> Telegram picker only (no Zalo menu)
    - [ ] Telegram-only: unchanged (no regression)
  ═══════════════════════════════════════════════════════
  Suggested squash command (founder runs after review):
    git checkout main && git pull --ff-only origin main
    git merge --squash feat/zalo-tx-picker
    git commit -m "feat(zalo): numbered category picker for uncategorized expenses (Zalo-only categorization)"
    git branch -D feat/zalo-tx-picker && git push origin main
  ═══════════════════════════════════════════════════════

Begin with Pre-flight, then Step 1.
