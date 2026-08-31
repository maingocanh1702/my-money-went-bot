# Autopilot Prompt — Generic Fill-In (v0.2.x)

> ⭐ **CANONICAL SINGLE-FILE REFERENCE (locked 2026-06-01).** When writing an autopilot prompt for
> any repo, this is the one file to send/use — it is self-contained: skeleton + risk rules + toolchain
> map (§B) + all 17 circuit breakers + latest lessons (CODEX_UNAVAILABLE, REGION_THRASH).
> `autopilot-prompt-template.md` is the rationale/"why" companion, NOT the send-file. If the two ever
> diverge, GENERIC wins and template gets updated to match.

> Repo-agnostic autopilot prompt cho **bất kỳ task nào** trên **mọi project hiện tại
> và tương lai**. Copy toàn bộ block dưới, thay mọi `<PLACEHOLDER>`, xoá phần đánh
> dấu `[OPTIONAL — …]` nếu không áp dụng, rồi paste vào Claude Code.
>
> Tuân thủ template `autopilot-prompt-template.md`: 15 section, STOP_AT_READY là
> default, auto-merge phải opt-in explicit, anti-pattern luôn kèm reason.

---

## A. Cách dùng (đọc 1 lần, không paste)

1. **Phân loại risk tier trước** (§3.2 / §4.1):
   - `P0` — security / data / auth / token / billing / migration không revert được
     → **KHÔNG dùng prompt này để codegen.** Chỉ dùng để generate review/checklist.
   - `P1` — orchestrator / foundation / schema / multi-tenant logic / state machine
     / external integration → autopilot OK, `merge_policy: manual_only`, Codex 2× clean.
   - `P2` — copy/UX strings, report formatting, docs-assisted code, read-only tools.
     - `pilot` (<3 successful runs trên class này) → `manual_only`, Codex 1× clean.
     - `mature` (≥3 successful) → `auto_merge_after_2x_codex_clean` **chỉ khi** paste
       `--auto-merge` explicit. Default vẫn manual.
2. **Điền placeholder.** Mọi `<…>` phải được thay; đừng để agent infer.
3. **Cắt cho gọn.** Prompt cuối ≤ 4 màn hình. Dài hơn → task quá to, split 1 prompt/phase.
4. **Default safe.** Nếu phân vân tier hay merge → chọn tier cao hơn + STOP_AT_READY.

Quy ước placeholder:
- `<REPO_PATH>` — đường dẫn tuyệt đối repo (vd `/Users/me/Projects/foo`).
- `<BRANCH>` — branch name cụ thể (vd `fix/parser-empty-marker`).
- `<TASK_SLUG>` — kebab-case dùng cho thư mục state (vd `parser-empty-marker`).
- `<VERIFY_CMD>` — chuỗi lệnh lint+typecheck+test của repo (điền §B bên dưới).
- `<DEFAULT_BRANCH>` — thường `main`; đổi nếu repo dùng `master`/`develop`.

---

## B. Toolchain map (điền cho mỗi project, paste vào prompt phần Pre-flight)

> Mỗi repo khác stack. Điền 1 lần / project, tái dùng. Để `# n/a` nếu không có.

```
Language/runtime activate : <vd: source .venv/bin/activate | nvm use | n/a>
Lint                      : <vd: ruff check . | eslint . | golangci-lint run>
Format check              : <vd: black --check . | prettier --check . | gofmt -l>
Typecheck                 : <vd: mypy . | tsc --noEmit | n/a>
Import/arch boundaries    : <vd: lint-imports | n/a>
Tests                     : <vd: pytest -q | npm test -- --run | go test ./...>
Cross-model review CLI    : <vd: codex review --base main | n/a (skip §12 nếu n/a)>
  ⚠ Resolve the REVIEW-CAPABLE binary explicitly (AUTOPILOT_CODEX_BIN / full path),
    NOT a bare `which codex`. Smoke-test it emits >0 bytes; if 0 bytes → CODEX_UNAVAILABLE
    breaker → HALT. Never substitute manual self-review and continue to READY.
Baseline test count       : <N passing trên DEFAULT_BRANCH hiện tại>
```

---

## C. PROMPT TEMPLATE — copy từ đây xuống

```text
Task: <ONE-LINE OUTCOME> — <SCOPE TAG: bugfix|feature|refactor>

You are working in <REPO_PATH> on <ONE-LINE PRODUCT CONTEXT>.
NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `<BRANCH>`, inline review per risk header,
then STOP_AT_READY (default) OR squash-merge (ONLY if §Risk header explicitly grants
+ this prompt passes `--auto-merge`). Pause ONLY on circuit-breaker conditions.

─────────────────────────────────────────────────────────
Risk header (REQUIRED)
  Risk tier:          <P0 | P1 | P2>
  Merge policy:       <manual_only | auto_merge_after_2x_codex_clean>
  Autopilot maturity: <pilot (<3 successful runs) | mature (>=3 successful)>
  Codex review:       <not_applicable | 1x_clean | 2x_consecutive_clean>

  RULE — verify before proceeding:
   * P0  -> STOP. Do NOT codegen with this prompt. Switch to manual workflow.
   * P1  -> merge_policy MUST be manual_only. Codex 2x consecutive clean required.
   * P2 pilot  -> manual_only. Codex 1x clean acceptable.
   * P2 mature -> auto_merge allowed ONLY if `--auto-merge` passed; else manual_only.
   If header contradicts these rules -> POLICY_MISMATCH breaker. HALT before any work.
─────────────────────────────────────────────────────────

Context (NOT for execution, just background — 2-5 lines)
  Origin:     <incident? pilot? decision lock? ticket?>
  Root cause: <bug/feature root cause in 1-2 lines>
  Why now:    <trigger>

Scope discipline
  Positive scope:  ONLY <EXACTLY WHAT TO DO>.
  Negative scope:  Do NOT touch <out-of-scope files/modules/branches> in this run.
  Documented-out:  <X> is handled later at <where> — do not start it here.

Required reading (READ FIRST, in this order, before any code)
  1. `<path/to/primary.ext>` — focus: <function/section> (anchor: line <X>)
  2. `<path/to/test.ext>`    — match this test style
  3. <add more in logical order: production -> tests -> docs -> fixtures>
  (Pre-flight still runs before any branch creation or mutation.)

Pre-flight gate (HARD GATE)
  Precondition: exactly ONE git-writing session on this repo (no parallel autopilot /
    Claude Code). Incident 2026-05-13: a parallel session hijacked HEAD mid-commit.
  cd <REPO_PATH>
  git status                      # MUST be clean
  git branch --show-current       # MUST be: <DEFAULT_BRANCH>
  git fetch origin && git pull --ff-only origin <DEFAULT_BRANCH>
  ls .git/*.lock 2>/dev/null      # MUST be empty (no concurrent git-writer)
  <Language/runtime activate>
  which <required tools>          # MUST resolve
  [if Codex review required:] CODEX="${AUTOPILOT_CODEX_BIN:-<full path to review-capable codex>}"
    [ -x "$CODEX" ] || HALT; "$CODEX" review --base <DEFAULT_BRANCH> | head -c1 | wc -c  # MUST be >0
    (0 bytes / interactive-only binary -> CODEX_UNAVAILABLE breaker -> HALT. Never use bare `which codex`.)
  # Run <VERIFY_CMD> with the SAME env vars the CI workflow sets (its `env:` block), not just
  # local defaults — CI often overrides secrets/config (e.g. SEPAY_SECRET). Local-green ≠ CI-green
  # when tests read those values. Mirror CI's env before this step.
  <VERIFY_CMD>                    # MUST be green — baseline <N> tests pass
  Risk-tier self-check: grep the in-scope files for auth|token|billing|funding|
    transactions|migration|secret. If ANY match AND Risk tier < P0
    -> POLICY_MISMATCH breaker -> HALT (tier under-classified; do not codegen).
  [OPTIONAL — if spec has an autopilot:gaps block:] 0 OPEN gaps (all CLOSED/DEFERRED).
  ALL must pass. If any fails -> HALT and report. Do not proceed.

Anti-patterns (NEVER do — each with reason)
  * `git push --force` — destroys remote history; never recoverable for others.
  * Add `# type: ignore` / `@ts-ignore` / `//nolint` — hides real type errors;
    TYPE_IGNORE_PROPOSED breaker, founder approval required.
  * Auto-merge outside the merge policy in the Risk header — violates locked policy.
  * Touch out-of-scope files/modules/branches — scope creep hides intent; bisect noise.
  * Hardcode a value the CI workflow overrides (secrets / env-derived config, e.g. SEPAY_SECRET) in
    tests or fixtures — read it from `config`/env instead. Reason: local pytest passes with the
    default but CI sets a different value, so the test silently fails ONLY in CI (incident 2026-06-01).
  * Thread raw/un-normalized data (dates, encodings, free text) into a parse path when a
    precomputed/normalized value through state already fixes the finding — it opens an
    edge minefield the reviewer will chase round after round (see REGION_THRASH).
  [OPTIONAL — only for parser/regression tasks where real CLI/IO output IS the data:]
  * Synthesize fake <X> outputs for fixtures — use the REAL captured files listed.
    The whole point is that synthetic fixtures HID these bugs.
  [delete the line above for ordinary feature tests — synthetic payloads are fine there]

Step 1 — create branch + state dir
  git checkout -b <BRANCH>
  git rev-parse HEAD > /tmp/<TASK_SLUG>-base-sha.txt
  mkdir -p .autopilot/state/<TASK_SLUG>/codex

[OPTIONAL — TDD gate; include when outcome is verifiable (parser/math/transform/API)]
Step 2 — write FAILING tests first (TDD)
  File: <path/to/test.ext>
  <write tests asserting the target behavior>
  Run <VERIFY_CMD tests-only>. These tests MUST FAIL on current <DEFAULT_BRANCH>.
  If they PASS when expected to fail -> something's off. Investigate before proceeding.
  (Test names self-documenting; expected behavior in docstring, not in name.)

Step 3..N — implement (atomic, one logical change each)
  <Step with concrete code block / bash + expected output>
  Sanity check: if <unexpected condition> -> investigate before proceeding.
  After EVERY commit (incident-derived, mandatory):
    git branch --show-current     # MUST equal <BRANCH>; else WRONG_BRANCH_HEAD -> HALT
    git log --oneline -1          # confirm the new commit is at HEAD
    # If working tree dirty but no new commit landed -> commit it now before next step
    #   (Blocker #1: codegen sometimes writes files without committing). Never proceed
    #   with uncommitted changes assuming they are "done".
  <repeat per atomic change>

Atomic commit plan (pre-written; one commit per logical change)
  [OPTIONAL if TDD:] git add <fixtures>;  git commit -m "test(<scope>): <real fixtures>"
  [OPTIONAL if TDD:] git add <test file>; git commit -m "test(<scope>): <behavior tested>"
  git add <production file>; git commit -m "<fix|feat>(<scope>): <what changed and why>"
  # ... bisect-friendly. No mega "fix everything" commit.

[OPTIONAL — Inline review; INCLUDE when risk tier >= P1 and Codex CLI available]
Step R — Inline cross-model review (max 5 fix rounds; confirmation tail decoupled)
  Use the resolved "$CODEX" (review-capable binary from Pre-flight), never bare `codex`.
  Before EACH round: assert `git branch --show-current` == <BRANCH>. If on
    <DEFAULT_BRANCH> -> review sees empty diff (stale-blob, v0.2.2 incident); checkout
    <BRANCH> first. If Codex output references a SHA != current HEAD -> treat as stale,
    re-run; do NOT act on stale findings.
  Round N (1..5):
    "$CODEX" review --base <DEFAULT_BRANCH> 2>&1 | tee .autopilot/state/<TASK_SLUG>/codex/round-NN.txt
    (Non-clobber: if file exists, suffix `-resumeN` — preserve forensics across resumes.)
    (0 bytes / error from "$CODEX" -> CODEX_UNAVAILABLE breaker -> HALT. Do NOT fall back to
     manual self-review and keep going — manual review by the codegen model is not cross-model.)
  Parse output:
    * "clean" phrases -> clean round.
    * P0/P1 finding   -> MUST fix this round.
    * P2 finding      -> fix opportunistically; defer if it's scope creep.
    * schema|breaking|architectural keyword -> ARCH_FINDING breaker -> HALT.
    * SEVERE kw (auth bypass|injection|csrf|xss|ssrf|rce|timing attack|*-leak)
        -> SECURITY_FINDING breaker -> HALT always.
    * SOFT kw (token|secret|hmac|auth) -> HALT only if finding severity is P0/P1
        (stops benign findings, e.g. markdown rendering, from false-tripping).
    * same finding hash in round N AND N+1 -> RECURRING_FINDING breaker -> HALT.
  Fix round:
    * Apply minimum-viable fix. Re-run <VERIFY_CMD>; MUST be green before next round.
    * Commit: "fix(<scope>): address codex round NN — <summary>"
    * Region-thrash guard: if this finding is the Nth (N>=3) DISTINCT edge of code THIS PR
      just introduced — especially in date/time, encoding, or parsing — STOP and consider
      reverting that sub-change to a leaner design instead of hardening the next edge. A
      smaller design may remove the whole edge class. -> REGION_THRASH breaker.
  Clean target (per Risk header) — confirmation rounds counted AFTER the last fix,
  NOT subtracted from the 5-round budget:
    * P1 -> 2 consecutive clean rounds.   * P2 pilot -> 1 clean round.
    * P2 mature w/ --auto-merge -> 2 consecutive clean rounds.
    * 5 rounds reached without target clean count -> MAX_ROUNDS breaker -> HALT.

Merge gate
  Pre-gate (ALL must hold, else MERGE_GATE_FAIL -> HALT — applies to READY too):
    1. <VERIFY_CMD> green (lint/format/typecheck/imports/tests).
    2. consecutive clean rounds >= target from Risk header.
    3. CHANGELOG entry added between base SHA and HEAD (founder needs it to squash).
    4. branch has >=1 commit ahead of <DEFAULT_BRANCH>.
    5. dry-run `git merge --squash --no-commit <BRANCH>` clean (no conflicts).
  DEFAULT = STOP_AT_READY. After pre-gate passes:
    * P0          -> template not applicable; STOP.
    * P1 (any)    -> STOP at READY_FOR_MANUAL_MERGE. Do NOT merge/commit-to-main/push.
                     Branch stays intact. Emit READY report. Exit.
    * P2 pilot    -> same as P1: STOP at READY.
    * P2 mature AND `--auto-merge` passed explicitly -> run squash block below.
    * Any other case (no flag / maturity unproven) -> STOP at READY.

  [Squash block — ONLY when explicitly authorized above]
    git checkout <DEFAULT_BRANCH>
    git pull --ff-only origin <DEFAULT_BRANCH>
    git merge --no-commit --no-ff <BRANCH>   # dry-run
    git merge --abort
    git merge --squash <BRANCH>
    git commit -m "<type>(<scope>): <title>

    <body: what changed, why, what Codex validated, test count delta, next steps>"
    git branch -D <BRANCH>
    git push origin <DEFAULT_BRANCH>
    # If push rejected -> HALT. Do NOT force-push.

Circuit breakers (named — HALT on any)
  1.  PREFLIGHT_REGRESSION — baseline tests no longer pass on <DEFAULT_BRANCH>.
  2.  PUSH_REJECTED        — remote moved (only when squash block authorized).
  3.  TDD_ORACLE_VIOLATED  — tests pass when expected to fail.
  4.  VERIFY_REGRESSION    — local verify fails twice consecutively.
  5.  ARCH_FINDING         — Codex flags schema/breaking/architectural.
  6.  SECURITY_FINDING     — Codex flags auth-bypass/injection/secret/timing/etc.
  7.  RECURRING_FINDING    — same finding hash in round N AND N+1.
  8.  TYPE_IGNORE_PROPOSED — anywhere.
  9.  MAX_ROUNDS           — Codex rounds exhausted without target clean count.
  10. TOOL_ERROR_2X        — git/codex/test tool errors twice in a row.
  11. CONTEXT_BUDGET_70    — context >70%; pause + report, founder resumes fresh.
  12. POLICY_MISMATCH      — header auto-merges a manual_only tier, OR risk-tier
                             self-check fails (in-scope file matches P0 surface).
  13. WRONG_BRANCH_HEAD    — post-commit HEAD not on <BRANCH> (parallel-session hijack).
  14. MERGE_GATE_FAIL      — any of the 5 pre-gate conditions fails (incl. CHANGELOG).
  15. STALE_REVIEW         — Codex review references a SHA != HEAD / empty diff.
  16. REGION_THRASH        — same file/function flagged across >=3 consecutive rounds with
                             DISTINCT findings each time (RECURRING doesn't fire); the PR keeps
                             expanding one fragile area (classic: date/time/parse). HALT; ask
                             founder: patch the next edge vs revert this sub-change to a leaner
                             design. The loop optimizes for "clean", not "worth the complexity".
  17. CODEX_UNAVAILABLE    — `"$CODEX" review` missing/errors/yields 0 bytes (e.g. interactive-only
                             binary on PATH). HALT; never substitute manual self-review and proceed.
  <add task-specific: FIXTURE_MISSING, MIGRATION_DRIFT, …>

On HALT — emit forensic report (do NOT clean up the branch):
  HALT — <TASK_SLUG> circuit broken.
  Step:    <which step/round>
  Trigger: <breaker name>
  Branch:  <BRANCH>
  HEAD:    <SHA>
  Detail:  <error output | Codex finding excerpt | rejected push reason>
  State:
    - Commits on branch since base: <list w/ SHAs>
    - Files changed: <list>
    - Codex artifacts: .autopilot/state/<TASK_SLUG>/codex/round-*.txt
    - Last verify: <pass | fail w/ offending check>
  Requesting founder input on: <specific question>

Final report — emit EXACTLY ONE variant matching the merge gate:

  ── Variant A — READY (default, merge_policy=manual_only) ──
  ═══════════════════════════════════════════════════════
  AUTOPILOT <TASK_SLUG> — READY_FOR_MANUAL_MERGE
  ═══════════════════════════════════════════════════════
  Squash commit:    N/A — manual merge pending
  Branch <BRANCH>:  still exists (intact, ready for review)
  Push origin/<DEFAULT_BRANCH>: NOT RUN
  Files added:    <list>
  Files modified: <list>
  Codex review:
    Round 01: <findings | clean>
    Round 02: <findings | clean>
    Final: <target> clean rounds confirmed (per merge policy)
    Artifacts: .autopilot/state/<TASK_SLUG>/codex/round-*.txt
  Local verification (final): lint/format/typecheck/imports clean;
    tests <count> passed (baseline <N>, expected >= <M>)
  Est. cost: codex <R> rounds + claude <C> codegen/fix calls ~= $<X>
  Decisions needing founder review: <non-obvious calls>
  Post-merge smoke checklist (founder runs AFTER squash — verify gate only catches
  syntax/test fail, NOT wrong behavior):
    - [ ] <app boots / migration applies cleanly>
    - [ ] <primary command/endpoint responds>
    - [ ] <no regression on adjacent paths: list them>
  ═══════════════════════════════════════════════════════
  Suggested squash command (founder runs after review):
    git checkout <DEFAULT_BRANCH>
    git pull --ff-only origin <DEFAULT_BRANCH>
    git merge --squash <BRANCH>
    git commit -m "<type>(<scope>): <title>

    <body>"
    git branch -D <BRANCH>
    git push origin <DEFAULT_BRANCH>
  ═══════════════════════════════════════════════════════

  ── Variant B — COMPLETE (only when squash block authorized + ran) ──
  ═══════════════════════════════════════════════════════
  AUTOPILOT <TASK_SLUG> — COMPLETE
  ═══════════════════════════════════════════════════════
  Squash commit: <SHA>  <type>(<scope>): <title>
  Branch <BRANCH>: DELETED
  Push origin/<DEFAULT_BRANCH>: OK
  (rest identical to READY minus the "suggested squash" block)
  ═══════════════════════════════════════════════════════

Begin with Pre-flight, then Step 1.
```

## C2. Mega / multi-phase variant (dùng khi cố ý gộp nhiều phase)

> Chỉ dùng khi: các phase **dependency tuyến tính chặt** + **cùng risk tier** + **cùng
> nhóm module** + bạn **ngồi canh (eyes-on)**. Đánh đổi: ít giám sát thủ công hơn, đổi
> lại rủi ro drop-phase âm thầm cao hơn (memory `autopilot_prompt_scope`). Với P0/P1
> hoặc khi walk-away → KHÔNG gộp, tách 1 prompt/phase.
>
> Giữ nguyên toàn bộ block ở §C, chèn thêm các phần dưới để bù rủi ro:

```text
Phase plan (declare upfront — agent MUST complete ALL or HALT, never silently drop)
  Phase 1: <outcome>   risk:<P_>   commits:<expected n>
  Phase 2: <outcome>   risk:<P_>   depends_on: Phase 1
  Phase 3: <outcome>   risk:<P_>   depends_on: Phase 2
  Effective risk tier for the whole run = MAX(all phase tiers).
  If any phase is P0 -> STOP, do not run as mega; that phase needs manual workflow.

After finishing each phase, emit a literal marker line:
  AUTOPILOT_PHASE_<k>_COMPLETE — commits <sha..sha>, verify green
Do NOT start Phase k+1 before emitting Phase k's marker + verify green.
Commit atomically per phase; never one mega "do everything" commit.

Extra circuit breaker:
  18. PHASE_SKIPPED — final report emitted but any declared phase lacks its
      AUTOPILOT_PHASE_<k>_COMPLETE marker, OR phases ran out of declared order.

Final report — prepend a phase ledger (founder skims this in 5 seconds):
  Phase ledger:
    Phase 1 <outcome>: COMPLETE  (marker present, commits <sha..sha>)
    Phase 2 <outcome>: COMPLETE  (marker present, commits <sha..sha>)
    Phase 3 <outcome>: <COMPLETE | HALTED at step X | NOT REACHED>
  (then the normal READY/COMPLETE variant from §C)
```

Quy tắc vàng: nếu phase ledger có bất kỳ dòng nào KHÔNG `COMPLETE` mà final report lại
là READY/COMPLETE → đó là silent drop → fail run, không merge.

## D. Pre-send checklist

- [ ] Header có `<REPO_PATH>` + `<BRANCH>` + mode + pause policy.
- [ ] Risk header điền đủ tier + merge_policy + maturity; nếu P0 → KHÔNG codegen.
- [ ] Context label rõ "NOT for execution".
- [ ] Scope có đủ positive + negative + documented-out.
- [ ] Required reading có line anchor.
- [ ] Pre-flight là hard gate, kết thúc "ALL must pass".
- [ ] Codex binary resolve qua AUTOPILOT_CODEX_BIN/full path + smoke-test >0 byte — KHÔNG `which codex` trống.
- [ ] Mỗi anti-pattern có reason; synthetic-fixtures line chỉ giữ khi parser/regression.
- [ ] Steps atomic, có expected output + sanity check.
- [ ] TDD section (nếu verifiable) có oracle "MUST fail".
- [ ] Commit plan pre-written, atomic.
- [ ] Inline review chỉ khi P1+ và có Codex; clean target khớp merge_policy.
- [ ] Fix-round có region-thrash guard (cùng vùng ≥3 round, findings khác nhau → xét revert-to-lean, không vá tiếp).
- [ ] Merge gate có pre-gate 5 điều kiện (gồm CHANGELOG); default STOP_AT_READY.
- [ ] Post-commit HEAD check + commit-landed verify có trong steps.
- [ ] 17 circuit breakers named (gồm POLICY_MISMATCH, WRONG_BRANCH_HEAD, STALE_REVIEW, REGION_THRASH, CODEX_UNAVAILABLE).
- [ ] Nếu gộp mega → có phase plan + markers + phase ledger + breaker PHASE_SKIPPED.
- [ ] Final report đúng variant (READY vs COMPLETE).
- [ ] Đóng bằng "Begin with Pre-flight, then Step 1."
- [ ] Prompt ≤ 4 màn hình; dài hơn → split 1 prompt/phase.

## E. Authority matrix (ceiling — khi ambiguous, default authority thấp hơn)

| Action                  | P0            | P1          | P2 pilot    | P2 mature                    |
|-------------------------|---------------|-------------|-------------|------------------------------|
| Write code on branch    | No (n/a)      | Yes         | Yes         | Yes                          |
| Commit to branch        | No            | Yes         | Yes         | Yes                          |
| Run verify/tests local  | Manual only   | Yes         | Yes         | Yes                          |
| Squash-merge to default | Founder only  | Founder only| Founder only| Only with explicit `--auto-merge` |
| Push to default branch  | Founder only  | Founder only| Founder only| Only with explicit `--auto-merge` |
| Force push              | Never         | Never       | Never       | Never                        |
| Add type-ignore         | Founder appr. | Founder appr.| Founder appr.| Founder appr.               |
| Touch out-of-scope      | Never         | Never       | Never       | Never                        |

## F. Lesson log (incidents encoded into this template)

- 2026-05-13 — parallel git-writing session hijacked HEAD mid-commit → one-session-per-repo
  precondition + WRONG_BRANCH_HEAD breaker + post-commit HEAD check.
- 2026-06-01 — `/recat` pilot: `which codex` resolved the interactive `@openai/codex` (0-byte
  `review`) → agent substituted manual review and reached READY. Fix: resolve review-capable
  `$CODEX` + smoke-test + CODEX_UNAVAILABLE breaker (HALT, never substitute).
- 2026-06-01 — `/recat` pilot: 13 commits / 11 rounds because the fix threaded a raw date
  (`row[1]`) into a parse path (the finding needed only a `month_key` state override). Findings
  cascaded in one region, each distinct so RECURRING never fired. Fix: REGION_THRASH breaker +
  fix-round revert-to-lean rule + anti-pattern against threading raw data into parse paths.
- 2026-06-01 — `zalo-tx-picker` pilot: reached READY with local pytest green, but CI's `lint-and-test`
  failed — 4 new tests hardcoded `apikey: "test_sepay_secret"` while CI overrides `SEPAY_SECRET`, so
  the SePay webhook was rejected only in CI. Fix: tests read `config.SEPAY_SECRET`; pre-flight runs
  tests with CI's env block + anti-pattern against hardcoding CI-overridden values. Lesson: local
  pytest green ≠ CI green when env differs.
