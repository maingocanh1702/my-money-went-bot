Task: Independent channels — make Telegram optional so the bot can run Telegram-only, Zalo-only, or both — feature/single-PR (Phase 1 of 3)

You are working in /Users/maingocanh/Projects/My Money Went Bot, the public OSS "My Money Went Bot": a personal finance bot (FastAPI + Google Sheets) with Telegram and Zalo front-ends. State lives in the Google Sheet (no DB). NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/independent-channels`, inline Codex review, then STOP_AT_READY. Pause ONLY on circuit-breaker conditions. Do NOT merge or push.

─────────────────────────────────────────────
Risk header (REQUIRED)
  Risk tier:          P1            # touches config/startup + channel layer (boot path)
  Merge policy:       manual_only   # STOP_AT_READY — founder squashes + pushes
  Autopilot maturity: pilot
  Codex review:       2x_consecutive_clean

  RULE: P1 -> manual_only, 2 consecutive clean rounds. Any attempt to auto-merge -> POLICY_MISMATCH -> HALT.

NOTE — repo toolchain (no orchestrator here): there is NO tools/autopilot, .venv-required, mypy, black,
lint-imports, pre-commit, or CHANGELOG. Real gates = `ruff check .` + `python -m pytest -q` (see
.github/workflows/ci.yml). Do not invent missing tools.

─────────────────────────────────────────────
Context (NOT for execution, just background)
  Origin:     Product decision — Telegram and Zalo should be two INDEPENDENT channels; a user may set up
              only Zalo, only Telegram, or both.
  Root cause: config.py hard-requires BOT_TOKEN/CHAT_ID via os.environ[...], so the bot cannot boot
              Zalo-only today. telegram_api.* and notifier.py assume Telegram is always present.
  Why now:    Zalo channel just shipped (commit d5bfab7); it currently rides on top of a mandatory
              Telegram config instead of standing alone.

─────────────────────────────────────────────
Scope discipline
  Positive scope: ONLY make Telegram OPTIONAL so the app boots and runs in any of three modes —
    Telegram-only, Zalo-only, both — without crashing. Specifically:
      (1) config.py: BOT_TOKEN/CHAT_ID become optional; derive channel-enable flags; validate that at
          least ONE channel is fully configured (else fail closed with a clear message).
      (2) telegram_api.py: every network call no-ops safely when Telegram is not configured.
      (3) notifier.py: fan out only to the channels that are enabled.
      (4) main.py: only register/setup Telegram bits when Telegram is enabled; route the top-level
          error notice through notifier so a Zalo-only user still receives it.
  Negative scope: Do NOT touch the interactive handlers (handlers/transaction.py, manage.py, keywords.py,
    allocation.py, accounts.py, report.py, reports.py) — they call tg.* which will no-op safely; they are
    only invoked by Telegram updates, which won't arrive in Zalo-only mode. Do NOT change the Sheet schema.
    Do NOT touch the Zalo dispatcher logic beyond what notifier/config require.
  Documented-out (DO NOT start here):
    * Phase 2 — Zalo numbered-menu picker for an UNcategorized NEW transaction (today sepay.py sends that
      picker via tg.send_with_buttons = Telegram-only; on Zalo-only it will silently no-op). A Zalo-only
      user can still use /keywords + /recat. Note this limitation in the READY report; do not implement it.
    * Phase 3 — README/.env.example "two independent channels" docs + Zalo screenshot.

─────────────────────────────────────────────
Required reading (READ FIRST, in this order, before any code)
  1. `config.py` — lines 6-8 (BOT_TOKEN/CHAT_ID/SHEET_ID required); lines 39-63 (startup validation block
     with the `if not BOT_TOKEN.startswith("test:")` guard + ZALO_* checks).
  2. `telegram_api.py` — `BASE = f"...bot{BOT_TOKEN}"` (line 4); `_post_with_md_fallback` (line 9);
     send_text/send_with_buttons/edit_message/delete_message/answer_callback/set_my_commands/drop_pending_updates.
  3. `notifier.py` — dual-channel fan-out (always calls tg.send_text + optional zalo).
  4. `main.py` — startup `set_my_commands` (~line 56); `/webhook` Telegram branch (update_id + secret, ~60);
     top-level error notice `tg.send_text(... Bot gặp lỗi ...)` (~line 170).
  5. `tests/conftest.py` — `fake_ss` fixture + the dummy env (`BOT_TOKEN=test:dummy`, etc.) set at import.
  6. `tests/unit/test_webhook_auth.py` — style for app/endpoint + monkeypatch tests.

─────────────────────────────────────────────
Pre-flight gate (HARD GATE)
  Precondition: exactly ONE git-writing session on this repo (no parallel Claude Code).
  cd "/Users/maingocanh/Projects/My Money Went Bot"
  git status                      # MUST be clean
  git branch --show-current       # MUST be: main
  git fetch origin && git pull --ff-only origin main
  ls .git/*.lock 2>/dev/null      # MUST be empty
  # Local Python is uv-managed (PEP 668) — use the repo .venv; NEVER pip into system Python.
  [ -d .venv ] || python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt -q
  pip install ruff -q
  # Codex review binary — resolve the REVIEW-capable build explicitly; NEVER bare `which codex`:
  CODEX="${AUTOPILOT_CODEX_BIN:-$HOME/Library/Application Support/crawbot/nodejs/bin/codex}"
  [ -x "$CODEX" ] && [ "$("$CODEX" review --base main 2>/dev/null | head -c1 | wc -c)" -gt 0 ] \
    || { echo "CODEX_UNAVAILABLE -> HALT"; exit 1; }
  ruff check .                    # MUST be clean
  python -m pytest -q             # MUST be green — RECORD pass count as BASELINE_N (expect 148)
  ALL must pass. If any fails -> HALT and report. Do not proceed.

─────────────────────────────────────────────
Anti-patterns (NEVER do — each with reason)
  * `git push --force` — destroys remote history.
  * Auto-merge / push to main — P1 is manual_only -> POLICY_MISMATCH.
  * Add `# type: ignore` — TYPE_IGNORE_PROPOSED breaker; founder approval.
  * Touch out-of-scope handlers/Sheet schema — scope creep; bisect noise. The 11 handlers must NOT change.
  * Read config values at import time in a way tests can't exercise — extract validation into a PURE
    function so Zalo-only / Telegram-only / both can be unit-tested without import gymnastics. Reason:
    config.py reads os.environ at import, so import-time `os.environ[...]` is untestable and was exactly
    what blocked Zalo-only. Make the channel rules a function of explicit args.
  * Make SHEET_ID optional — the Google Sheet is the shared backend for BOTH channels; keep it required.

─────────────────────────────────────────────
Step 1 — branch + state dir
  git checkout -b feat/independent-channels
  git rev-parse HEAD > /tmp/independent-channels-base-sha.txt
  mkdir -p .autopilot/state/independent-channels/codex     # forensic only; NEVER git add this dir

─────────────────────────────────────────────
Step 2 — write FAILING tests first (TDD)
  File: tests/unit/test_independent_channels.py. Mirror conftest/test_webhook_auth style.
  Lock the design via tests:
  * A pure validation helper (e.g. config._missing_channel_vars(...)) returns [] when EXACTLY ONE channel
    is fully configured, and a non-empty list when NEITHER is. Test all 3 valid modes + the empty case.
  * Telegram enabled iff BOT_TOKEN and CHAT_ID are both set.
  * telegram_api network calls (send_text/send_with_buttons/edit_message) no-op (return None, perform NO
    httpx POST) when BOT_TOKEN is empty — monkeypatch tg.BOT_TOKEN="" and assert the client is not called.
  * notifier.send_text: Telegram-disabled -> only the Zalo leg runs; Zalo-disabled -> only the Telegram leg.
  Run `python -m pytest tests/unit/test_independent_channels.py -q`. These MUST FAIL on current main.
  If they pass before implementation -> TDD oracle violated -> investigate.

─────────────────────────────────────────────
Step 3 — config.py: optional Telegram + channel validation
  * `BOT_TOKEN = os.environ.get("BOT_TOKEN", "")`, `CHAT_ID = os.environ.get("CHAT_ID", "")`.
    Keep `SHEET_ID = os.environ["SHEET_ID"]` required.
  * Add `TELEGRAM_ENABLED = bool(BOT_TOKEN and CHAT_ID)`.
  * Extract a pure helper, e.g.:
      def _missing_channel_vars(*, telegram_enabled, bot_token, chat_id, tg_secret,
                                zalo_enabled, zalo_token, zalo_chat, zalo_interactive,
                                zalo_secret, zalo_user, sepay_secret, cron_secret) -> list[str]: ...
    Rules: SEPAY_SECRET + CRON_SECRET always required (channel-independent). Require >=1 channel fully
    configured: Telegram = BOT_TOKEN+CHAT_ID+TELEGRAM_WEBHOOK_SECRET; Zalo = ZALO_ENABLED+ZALO_BOT_TOKEN+
    ZALO_CHAT_ID (+ ZALO_WEBHOOK_SECRET+ZALO_USER_ID when ZALO_INTERACTIVE). If neither channel qualifies,
    add "at least one channel (Telegram or Zalo) must be fully configured".
  * Keep the test-mode bypass: skip the SystemExit when BOT_TOKEN.startswith("test:") OR when running
    Zalo-only test fixtures — but the helper itself stays pure and always testable.
  Sanity check: existing Telegram-only prod config must still validate identically (no regression).

─────────────────────────────────────────────
Step 4 — telegram_api.py: no-op when Telegram not configured
  Guard each network function so it returns None without calling httpx when `not BOT_TOKEN`
  (send_text, send_with_buttons, edit_message, delete_message, answer_callback, set_my_commands,
  drop_pending_updates). build_bucket_buttons / build_sub_buttons are pure — leave them.
  Sanity check: when BOT_TOKEN is set, behavior is byte-for-byte unchanged.

─────────────────────────────────────────────
Step 5 — notifier.py + main.py: route to enabled channels only
  * notifier.send_text: run the Telegram leg only if config.TELEGRAM_ENABLED; keep the best-effort Zalo
    leg gated on ZALO_ENABLED (already). Never let one channel's failure block the other or SePay.
  * main.py: call set_my_commands() at startup only if TELEGRAM_ENABLED. Route the top-level error notice
    (`⚠️ Bot gặp lỗi`) through notifier.send_text so a Zalo-only user receives it. Leave the /webhook
    Telegram branch as-is (it self-rejects when secrets are empty).

─────────────────────────────────────────────
Step 6 — Local verify (green)
  ruff check .
  python -m pytest -q            # ALL green; count == BASELINE_N + <new tests>; previously-failing tests pass
  If verify fails twice consecutively -> VERIFY_REGRESSION -> HALT.

Atomic commit plan (conventional commits, one logical change each)
  git add tests/unit/test_independent_channels.py
  git commit -m "test(channels): Telegram-optional config + no-op + notifier routing (3 modes)"
  git add config.py
  git commit -m "feat(channels): make Telegram optional; validate >=1 channel configured"
  git add telegram_api.py
  git commit -m "feat(channels): telegram_api no-ops when Telegram not configured"
  git add notifier.py main.py
  git commit -m "feat(channels): notifier + startup route only to enabled channels"

─────────────────────────────────────────────
Step R — Inline Codex review (max 5 rounds; target 2 consecutive clean)
  Use the resolved "$CODEX" from Pre-flight. Before each round: assert `git branch --show-current` ==
  feat/independent-channels (else checkout it; reviewing from main = empty diff / STALE_REVIEW).
  Round N:
    "$CODEX" review --base main 2>&1 | tee .autopilot/state/independent-channels/codex/round-NN.txt
    (0 bytes/error -> CODEX_UNAVAILABLE -> HALT. Never substitute manual self-review and continue.)
  Parse: P0/P1 -> fix this round; P2 -> opportunistic; schema|breaking|architectural -> ARCH_FINDING HALT;
    auth|token|secret|injection|timing -> SECURITY_FINDING HALT; same hash N & N+1 -> RECURRING_FINDING HALT.
  Fix round: minimum-viable fix -> re-run `ruff check . && python -m pytest -q` green -> commit
    "fix(channels): address codex round NN — <summary>".
    REGION_THRASH guard: if findings keep landing in the SAME new region across >=3 rounds (each a new
    edge), STOP and consider revert-to-lean instead of patching the next edge -> REGION_THRASH breaker.
  Need 2 consecutive clean rounds. 5 rounds without it -> MAX_ROUNDS -> HALT.

─────────────────────────────────────────────
Merge gate
  P1 / manual_only -> STOP_AT_READY. Do NOT git merge / commit to main / push. Branch stays intact.
  Emit the READY report and exit.

─────────────────────────────────────────────
Circuit breakers (HALT on any)
  PREFLIGHT_REGRESSION, TDD_ORACLE_VIOLATED, VERIFY_REGRESSION, ARCH_FINDING, SECURITY_FINDING,
  RECURRING_FINDING, TYPE_IGNORE_PROPOSED, MAX_ROUNDS, TOOL_ERROR_2X, CONTEXT_BUDGET_70, POLICY_MISMATCH,
  WRONG_BRANCH_HEAD (post-commit HEAD not on feat/independent-channels), STALE_REVIEW (codex sees empty
  diff / SHA != HEAD), REGION_THRASH (same region flagged >=3 consecutive rounds), CODEX_UNAVAILABLE
  ($CODEX missing/0-byte). Task-specific: CONFIG_REGRESSION (existing Telegram-only prod config no longer
  validates) -> HALT.

On HALT — emit forensic report (do NOT clean up the branch):
  HALT — independent-channels circuit broken.
  Step / Trigger / Branch / HEAD / Detail / State (commits, files, codex artifacts, last verify) /
  Requesting founder input on: <question>

─────────────────────────────────────────────
Final report — READY (emit verbatim)
  ═══════════════════════════════════════════════════════
  AUTOPILOT independent-channels — READY_FOR_MANUAL_MERGE
  ═══════════════════════════════════════════════════════
  Squash commit:    N/A — manual merge pending
  Branch feat/independent-channels: still exists (intact, ready for review)
  Push origin/main: NOT RUN
  Files added:    tests/unit/test_independent_channels.py
  Files modified: config.py, telegram_api.py, notifier.py, main.py
  Codex review:
    Round 01: <findings | clean>   Round 02: <findings | clean>
    Final: 2 consecutive clean rounds confirmed
    Artifacts: .autopilot/state/independent-channels/codex/round-*.txt
  Local verification (final): ruff clean; pytest <count> passed (baseline 148, expected 148 + <new>)
  Known limitations (by design, Phase 2): on Zalo-only, an UNcategorized new expense does not yet show a
    picker (the new-tx picker is Telegram inline-button only); Zalo users use /keywords + /recat meanwhile.
  Decisions needing founder review: <non-obvious calls, else none>
  Post-merge smoke checklist (founder runs after squash):
    - [ ] Telegram-only config still boots + /today replies (no regression)
    - [ ] Zalo-only config (no BOT_TOKEN/CHAT_ID, ZALO_ENABLED + zalo vars) boots without crash
    - [ ] Both-channels config boots; a tx notification reaches both
    - [ ] Neither channel configured -> app fails closed with the clear "at least one channel" message
  ═══════════════════════════════════════════════════════
  Suggested squash command (founder runs after review):
    git checkout main && git pull --ff-only origin main
    git merge --squash feat/independent-channels
    git commit -m "feat(channels): independent Telegram/Zalo — Telegram now optional (Zalo-only supported)"
    git branch -D feat/independent-channels && git push origin main
  ═══════════════════════════════════════════════════════

Begin with Pre-flight, then Step 1.
