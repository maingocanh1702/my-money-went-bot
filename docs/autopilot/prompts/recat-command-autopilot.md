Task: /recat command — add `/recat <row>` + align button-path month logic — feature/single-PR

You are working in /Users/maingocanh/Projects/My Money Went Bot, the public OSS "My Money Went Bot": a Telegram/Zalo expense bot that logs SePay bank transactions to a Google Sheet and lets the user categorize them. State lives in the Sheet (no DB). NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/recat-command`, inline Codex review, then STOP_AT_READY. Pause ONLY on circuit-breaker conditions. Do NOT merge or push.

─────────────────────────────────────────────
Prompt risk header (REQUIRED)
─────────────────────────────────────────────
Risk tier:          P1            # sheet-backed feature logic; reuses categorize state machine
Merge policy:       manual_only   # STOP_AT_READY — founder squashes + pushes
Autopilot maturity: pilot         # first autopilot run on this repo class
Codex review:       2x_consecutive_clean

NOTE: This repo does NOT have the `tools/autopilot` orchestrator, `.venv`, mypy, black, lint-imports,
pre-commit, or CHANGELOG.md. The real toolchain is `pip install -r requirements.txt`, `ruff check .`,
and `python -m pytest -q` (see CI `.github/workflows/ci.yml`). The gates below are adapted to that
reality — do not invent missing tools. Codex CLI is available system-wide and is invoked manually.

─────────────────────────────────────────────
Context (NOT for execution, just background)
─────────────────────────────────────────────
Re-categorizing a transaction already works via the inline "🔄 Sai mục?" button on every confirmation
(`handlers/transaction.py::handle_recategorize`). The gap: there is no `/recat <row>` slash command to
fix an *arbitrary older* row by number. Bot Finance (the private sibling) has it as `_tg_cmd_recat`.
Separately, the existing button path computes its bucket set from the *current* month, while a correct
`/recat` of an old row must use that row's *own* month (column O / `row[14]`). This run adds the command
and aligns both entry points to use the row's month. Source: docs/implementation-plan-messenger-and-recat.md §3.

─────────────────────────────────────────────
Scope discipline
─────────────────────────────────────────────
Scope of this prompt: ONLY (1) add a Telegram `/recat <row>` command and (2) make the existing
`handle_recategorize` button path read the transaction's own month (`row[14]`) with current-month
fallback. Tests for both.
Do NOT touch: Zalo dispatcher, Messenger work, SePay webhook logic, sheet schema/column order,
`handlers/transaction.py::handle_parent_selected/handle_sub_selected/_finalize`, or any unrelated handler.
Out-of-scope-but-documented: Zalo `/recat` is deferred (see plan §3.3); do not start it here.

─────────────────────────────────────────────
Required reading (READ FIRST, in this order, before any code)
─────────────────────────────────────────────
1. `handlers/transaction.py` — `handle_recategorize` at line 188 (the month-fix target; note it already reads `row`).
2. `main.py` — `_handle_command` at line ~302 (where `/recat` wires in); default help blurb in `_handle_message` at line ~236; confirm module-scope imports (datetime/pytz are NOT imported at module scope).
3. `sheets.py` — `get_transaction_row`, `reset_transaction_row`, `row_currency`, `_parse_amount`, `get_active_buckets(month_key, force_refresh=False)`, `fmt_amount`, `fmt_month`; `append_transaction` docstring (line ~623) for column schema: F=Description=row[5], G=Type=row[6] ("Tiền ra"/"Tiền vào"), H=Amount=row[7], O=Month=row[14], P=Currency=row[15].
4. `telegram_api.py` — `build_bucket_buttons(buckets, prefix, include_new=False)`, `send_with_buttons`, `send_text`, `set_my_commands` (~line 97).
5. `tests/conftest.py` — `fake_ss` fixture (monkeypatches `_get_spreadsheet`/`_sheet`, resets caches).
6. `tests/unit/test_phase1_sepay_flow.py` — lines ~46-48 show the idiom: monkeypatch `tg.send_text/send_with_buttons/edit_message`, `@pytest.mark.asyncio`, `await` the handler. Match this style.

─────────────────────────────────────────────
Pre-flight gate
─────────────────────────────────────────────
```bash
cd "/Users/maingocanh/Projects/My Money Went Bot"
git status                              # MUST be clean
git branch --show-current               # MUST be: main
git fetch origin && git pull --ff-only origin main
git log --oneline -3

python3 -m pip install -r requirements.txt   # CI does this; ensures pytest/ruff deps present
python3 -m pip install ruff
which codex                             # MUST resolve (Codex review step). If absent → HALT.

ruff check .                            # MUST be clean
python -m pytest -q                     # MUST be green — RECORD the pass count as BASELINE_N
```
ALL must pass. Record BASELINE_N (the green test count). If any fails → HALT and report. Do not proceed.

─────────────────────────────────────────────
Anti-patterns (NEVER do)
─────────────────────────────────────────────
* `git push --force`.
* Auto-merge or push to main — merge policy is manual_only (§ risk header). STOP_AT_READY.
* Add `# type: ignore` anywhere (circuit breaker — founder approval needed).
* Touch any out-of-scope file/module/branch (Zalo, Messenger, SePay, sheet schema).
* Reorder or add Sheet columns. The A–U schema is load-bearing; `/recat` only reads existing columns and reuses `reset_transaction_row`.
* Hardcode column indices by guessing — use the verified mapping (desc=5, dir=6, amount=7, month=14) and the existing `sh.*` helpers. **Reason: the button path already drifted on month (current vs row month); guessing indices is how that class of bug enters.**
* Invent a "module" abstraction or refactor `handle_recategorize`'s call shape — minimal additive change only.

─────────────────────────────────────────────
Step 1 — branch + scratch dir
─────────────────────────────────────────────
```bash
git checkout -b feat/recat-command
git rev-parse HEAD > /tmp/recat-base-sha.txt
mkdir -p .autopilot/state/recat/codex     # forensic only; NEVER git add this dir
```

─────────────────────────────────────────────
Step 2 — Write FAILING tests first (TDD)
─────────────────────────────────────────────
File: `tests/unit/test_recat_command.py`. Mirror the idiom in `test_phase1_sepay_flow.py`
(monkeypatch tg sends to a recorder; `@pytest.mark.asyncio`; seed via `fake_ss`). Use `freezegun`
(already a dependency) to pin "now" for the current-month fallback cases.

Cover (from plan §3.4 + the consistency fix):
1. `/recat` with no arg / non-numeric → usage message ("Usage: `/recat <row_number>`"), no state set.
2. `/recat <missing row>` → "Không tìm thấy transaction row" message.
3. `/recat <income row>` (G="Tiền vào") → "Income hiện không cần category" message, no reset.
4. `/recat <expense row>` → `reset_transaction_row` called, state set to `step="await_parent"` with the
   row's amount/currency/description, and `send_with_buttons` called with `p_<row>` prefix buttons.
5. `/recat <old-month expense row>` (row[14] = a past month) → buckets fetched for the ROW's month,
   not the current month. Seed buckets only for the row's month; assert the picker is built from them.
6. `/recat <expense row>` whose row-month has NO active buckets → warning "Không có category active",
   and `reset_transaction_row` NOT called.
7. Consistency: button path `handle_recategorize(["recat", <old-month row>], msg_id)` → also uses the
   row's month (row[14]), matching case 5. (This test FAILS before the §Step 4 fix.)

```bash
python -m pytest tests/unit/test_recat_command.py -q
```
These tests MUST FAIL on current `feat/recat-command` (command doesn't exist; button path ignores row[14]).
If any pass before implementation → TDD oracle violated → investigate before proceeding.

─────────────────────────────────────────────
Step 3 — Implement `/recat` command in main.py
─────────────────────────────────────────────
Add module-scope imports if absent: `from datetime import datetime` and `import pytz`.
Add the handler (adapted from Bot Finance `_tg_cmd_recat`, using this repo's helpers):

```python
async def _cmd_recat(text: str):
    """/recat <row_num> — re-categorize a past transaction via the bucket picker."""
    parts = text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await tg.send_text("Usage: `/recat <row_number>`\nVd: `/recat 125`")
        return
    row_num = int(parts[1])
    row = sh.get_transaction_row(row_num)
    if not row:
        await tg.send_text(f"⚠️ Không tìm thấy transaction row {row_num}.")
        return
    direction = "in" if (row[6] if len(row) > 6 else "") == "Tiền vào" else "out"
    if direction == "in":
        await tg.send_text("ℹ️ Income hiện không cần category. Không recat.")
        return
    amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
    description = row[5] if len(row) > 5 else ""
    currency = sh.row_currency(row)
    row_month = row[14] if len(row) > 14 else ""
    month_key = row_month or sh.fmt_month(datetime.now(pytz.timezone(TIMEZONE)))
    buckets = sh.get_active_buckets(month_key)
    if not buckets:
        await tg.send_text(f"⚠️ Không có category active cho tháng {month_key}. Dùng /manage trước.")
        return
    sh.reset_transaction_row(row_num)
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": row_num,
        "amount": amount, "currency": currency, "description": description,
    })
    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.send_with_buttons(
        f"↩️ *Re-categorize: -{sh.fmt_amount(amount, currency)}*\n"
        f"`{description}`\n\nKhoản này thuộc mục nào?",
        buttons,
    )
```
Wire into `_handle_command`:
```python
    elif cmd == "/recat":     await _cmd_recat(text)
```
Add a `/recat <row>` line to the default help blurb in `_handle_message`, and add `/recat` to
`telegram_api.py::set_my_commands()`.

─────────────────────────────────────────────
Step 4 — Align button path month (consistency fix)
─────────────────────────────────────────────
In `handlers/transaction.py::handle_recategorize`, replace the current-month computation with the
row's own month + current-month fallback (the function already reads `row`):
```python
    row_month = row[14] if len(row) > 14 else ""
    tz = pytz.timezone(TIMEZONE)
    month_key = row_month or sh.fmt_month(datetime.now(tz))
    buckets = sh.get_active_buckets(month_key)
```
Do not change anything else in the function.

─────────────────────────────────────────────
Step 5 — Local verify (green)
─────────────────────────────────────────────
```bash
ruff check .
python -m pytest -q          # ALL green; count == BASELINE_N + <new tests>
```
The previously-failing tests (incl. case 7) MUST now pass. If verify fails twice consecutively →
VERIFY_REGRESSION breaker → HALT.

─────────────────────────────────────────────
Atomic commit plan (conventional commits, 1 logical change each)
─────────────────────────────────────────────
```bash
git add tests/unit/test_recat_command.py
git commit -m "test(recat): /recat command + button-path month behavior"

git add main.py telegram_api.py
git commit -m "feat(recat): add /recat <row> command to re-categorize a past transaction"

git add handlers/transaction.py
git commit -m "fix(recat): button re-categorize uses the transaction's own month (row[14])"
```

─────────────────────────────────────────────
Step 6 — Inline Codex review (≤5 rounds, target 2 consecutive clean)
─────────────────────────────────────────────
```bash
codex review --base main 2>&1 | tee .autopilot/state/recat/codex/round-01.txt
```
Parse output:
* Clean verdict → counts toward consecutive-clean.
* Findings: P0/P1 → MUST fix this round; P2 → fix opportunistically, defer if scope creep.
* Keywords schema|breaking|architectural → ARCH_FINDING → HALT.
* Keywords auth|token|timing|secret|injection → SECURITY_FINDING → HALT.
* Same finding hash in round N and N+1 → RECURRING_FINDING → HALT.
Fix round: apply minimum-viable fix → re-run `ruff check . && python -m pytest -q` (MUST be green) →
commit `fix(recat): address codex round NN — <summary>` → next round.
P1 requires 2 consecutive clean rounds. If 5 rounds reached without 2 consecutive clean → MAX_ROUNDS → HALT.

─────────────────────────────────────────────
Merge gate
─────────────────────────────────────────────
P1 / manual_only → STOP_AT_READY. Do NOT run `git merge`, `git commit` on main, or `git push`.
Branch `feat/recat-command` stays intact. Emit the READY report and exit.

─────────────────────────────────────────────
Circuit breakers (named halt conditions)
─────────────────────────────────────────────
1. Pre-flight regression — `ruff check .` or `pytest` not green on main.
2. TDD oracle violated — new tests pass before implementation.
3. VERIFY_REGRESSION — local verify fails twice consecutively.
4. ARCH_FINDING — Codex flags schema/breaking/architectural.
5. SECURITY_FINDING — Codex flags auth/token/timing/secret/injection.
6. RECURRING_FINDING — same finding hash in round N and N+1.
7. TYPE_IGNORE_PROPOSED — anywhere.
8. MAX_ROUNDS — Codex rounds exhausted without 2 consecutive clean.
9. SCOPE_BREACH — a change is needed in an out-of-scope file (Zalo/Messenger/SePay/schema).
10. Tool error twice in a row on git/codex/pytest/ruff.
11. POLICY_MISMATCH — any attempt to auto-merge/push (P1 is manual_only).
12. Context budget >70% — pause + report; founder resumes fresh.

─────────────────────────────────────────────
Halt report template
─────────────────────────────────────────────
```
HALT — recat circuit broken.
Step:    <e.g. Step 6 round 2>
Trigger: <one of the conditions above>
Branch:  feat/recat-command
HEAD:    <SHA>
Detail:  <error output OR Codex finding excerpt>
State:
- Commits since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/recat/codex/round-*.txt
- Last verify: <pass | fail with offending check>
Requesting founder input on: <specific question>
```
Halt = forensic. Leave the branch as-is; do not clean up.

─────────────────────────────────────────────
Final report — READY (emit verbatim)
─────────────────────────────────────────────
```
═══════════════════════════════════════════════════════
AUTOPILOT recat — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════

Squash commit:    N/A — manual merge pending
Branch feat/recat-command: still exists (intact, ready for review)
Push origin/main: NOT RUN

Files added:    tests/unit/test_recat_command.py
Files modified: main.py, telegram_api.py, handlers/transaction.py

Codex review:
  Round 01: <findings | clean>
  Round 02: <findings | clean>
  Final state: 2 consecutive clean rounds confirmed
  Artifacts: .autopilot/state/recat/codex/round-*.txt

Local verification (final):
  ruff check .: clean
  pytest: <count> passed (baseline BASELINE_N, expected BASELINE_N + <new tests>)

Decisions made during execution requiring founder review:
  <list any non-obvious calls, else "none">

═══════════════════════════════════════════════════════
Suggested squash command (founder runs after review):

  git checkout main
  git pull --ff-only origin main
  git merge --squash feat/recat-command
  git commit -m "feat(recat): /recat <row> command + button-path month fix

  Adds /recat <row> to re-categorize an arbitrary past transaction; aligns
  the existing 'Sai mục?' button path to use the transaction's own month.
  Codex 2x clean. Tests: BASELINE_N → BASELINE_N + <new>."
  git branch -D feat/recat-command
  git push origin main
═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1.
