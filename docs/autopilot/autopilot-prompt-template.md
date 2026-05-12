# Autopilot Prompt Template

Template + decision rules cho viết prompt autopilot mới (v0.2.x trở đi).

Distilled từ v0.2.1 (Codex parser fix) prompt — được engineer như một spec với
pre/post conditions, invariants, error handling, và explicit grants of authority.
Agent không cần infer intent vì intent đã encode thành rules.

---

## 1. Khi nào dùng template này

Khi viết autopilot prompt cho:
- Bug fix / feature delivery có verifiable outcome (parser, transform, API endpoint)
- Refactor có test suite bảo vệ
- Orchestrator change classified P1 needs inline Codex review; P0 uses manual workflow (template không apply for P0 codegen)
- Bất kỳ task nào autopilot sẽ đưa tới READY_FOR_MANUAL_MERGE hoặc, khi explicitly authorized per §3.2 + §3.12, squash-merge to main

KHÔNG dùng cho:
- Exploration / spike (không có exit condition rõ)
- Multi-phase work (feedback `autopilot_prompt_scope`: split thành 1 prompt/phase)
- Pure docs (overkill — viết tay nhanh hơn)

---

## 2. Skeleton — 15 section theo thứ tự

```
1.  Header một dòng                     # Task: <title> — <scope tag>
2.  Working directory + mode declaration # Mode: AUTOPILOT, branch, pause policy
3.  Prompt risk header                  # Risk tier + merge policy + maturity (REQUIRED)
4.  Context block (NOT for execution)    # Background, 2-5 dòng
5.  Scope discipline                     # Positive + Negative + Out-of-scope-documented
6.  Required reading                     # Files theo thứ tự, có line anchor
7.  Pre-flight gate                      # Hard fail conditions
8.  Anti-patterns                        # List với reason
9.  Numbered steps                       # Atomic, có code block
10. TDD gate                             # (nếu outcome verifiable)
11. Atomic commit plan                   # Pre-written commit messages
12. Inline review section                # (nếu risk tier ≥ P1)
13. Merge gate + (optional) squash block # Default STOP_AT_READY; auto-merge gated
14. Circuit breakers                     # Named halt conditions
15. Halt report + Final report (READY/COMPLETE variants)
```

Đóng prompt bằng: `Begin with Pre-flight, then Step 1.`

---

## 3. Section-by-section guide

### 3.1 Header + Mode declaration

```
Task: <Feature/version> — <one-line outcome>
You are working in /Users/<user>/Projects/<repo> on <one-line product context>.
NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `<branch-name>`, <review policy>,
then STOP_AT_READY (default) OR squash-merge (only if explicitly granted by
§3.2 risk header). Pause ONLY on circuit-breaker conditions.
```

Phải có: repo path tuyệt đối, branch name cụ thể, exit condition, pause policy.
Exit condition default = STOP_AT_READY (founder does manual squash). Auto-merge chỉ
khi §3.2 risk header explicitly grants — xem §4 decision matrix.

### 3.2 Prompt risk header (REQUIRED)

Ngay sau Mode block, BẮT BUỘC có:

```
Risk tier:          P0 | P1 | P2
Merge policy:       manual_only | auto_merge_after_2x_codex_clean
Autopilot maturity: pilot (<3 successful runs) | mature (≥3 successful)
Codex review:       not_applicable | 1x_clean | 2x_consecutive_clean
```

Rule:
- P0 → KHÔNG dùng template này cho codegen. Template chỉ generate review/checklist
  prompt, không generate implementation. Stop here, switch to manual workflow.
- P1 → `merge_policy: manual_only` (luôn luôn). Codex 2× clean required.
- P2 + pilot → `merge_policy: manual_only`. Codex 1× clean required.
- P2 + mature → `merge_policy: auto_merge_after_2x_codex_clean` allowed if prompt
  passes `--auto-merge` flag explicitly. Default vẫn manual.

Lý do: align với orchestrator v0.1 locked policy. Auto-merge KHÔNG phải default
cho bất kỳ tier nào — phải opt-in explicit và chỉ sau khi autopilot prove mature
trên class of changes đó.

### 3.3 Context block

Label rõ "Context (NOT for execution, just background)". 2-5 dòng nói:
- Việc này xuất phát từ đâu (incident? pilot? decision lock?)
- Bug/feature root cause ngắn gọn
- Why now

KHÔNG để agent infer "tại sao" từ code — sẽ guess sai.

### 3.4 Scope discipline (3 tầng)

```
Scope of this prompt: ONLY <X>. <Y> được làm ở <where>.
Do NOT touch <out-of-scope branch/file/feature> in this run.
```

3 tầng giúp chống scope creep:
- **Positive scope** — exactly what to do
- **Negative scope** — explicit "do not touch"
- **Out-of-scope-but-documented** — point tới next step để agent không cảm thấy phải làm hết

### 3.5 Required reading

```
Required reading (READ FIRST, in this order, before any code)

1. `path/to/file.py` — what to focus on (line anchor: function at line X)
2. `path/to/test.py` — match this style
3. ...
```

Yêu cầu:
- Thứ tự đọc có logic (production code → tests → docs → fixtures)
- Mỗi file kèm line anchor cho function/section quan trọng
- Required reading comes before implementation steps. Pre-flight still runs
  before any branch creation or mutation.

### 3.6 Pre-flight gate

```bash
cd /Users/<user>/Projects/<repo>
git status                              # MUST be clean
git branch --show-current               # MUST be: main
git fetch origin && git pull --ff-only origin main
git log --oneline -3                    # <expected HEAD> at HEAD or later

source .venv/bin/activate
which <required-tools>                  # MUST resolve

ruff check ...
black --check ...
mypy ...
lint-imports
pytest tests/ -v                        # MUST be green (<N> pass baseline)

python -m tools.autopilot preflight     # ALL pass
```

Kết thúc bằng: `ALL must pass. If any fails → HALT and report. Do not proceed.`

Pre-flight là **hard gate**, không phải suggestion. Ngăn agent workaround bằng cách skip step.

### 3.7 Anti-patterns

```
Anti-patterns (NEVER do)

* `git push --force`.
* <Universal items below>
* <Task-specific items with reasons>
```

Universal anti-patterns (paste vào mọi prompt):
- `git push --force`
- Add `# type: ignore` (circuit breaker — founder approval needed)
- Auto-merge ngoài merge policy của risk header (§3.2)
- Touch out-of-scope **files / modules / branches** (production code thuộc scope
  là OK; out-of-scope branch/module thì không)

Conditional anti-pattern (chỉ paste khi áp dụng):
- **Synthetic fixtures** — chỉ ban cho parser/regression bug nơi real CLI output
  là điểm chính. Với pure unit test mocking external service, synthetic payload
  vẫn legitimate. Wording cho parser/regression case:
  > "Synthesize fake <X> outputs for fixtures — use the real files listed.
  > The whole point is that synthetic fixtures hid these bugs."

  Với feature test thông thường, KHÔNG paste rule này.

Anti-pattern phải có **reason**. Ví dụ:
- ✘ "Don't use fake fixtures"
- ✓ "Synthesize fake Codex outputs for fixtures — use real files. **The whole point is that synthetic fixtures hid these bugs.**"

Reason biến rule thành knowledge, agent áp dụng được edge case.

### 3.8 Numbered steps

Mỗi step:
- **Atomic** — 1 logical change
- **Có code block cụ thể** — bash commands hoặc code diff
- **Có expected output** khi relevant
- **Có sanity check** — "if X happens, investigate before proceeding"

Step 1 luôn là:
```bash
git checkout -b <branch-name>
git rev-parse HEAD > /tmp/<task>-base-sha.txt
mkdir -p .autopilot/state/<task>/codex
```

### 3.9 TDD gate (nếu outcome verifiable)

```
Write FAILING tests first (TDD)
File: tests/unit/test_<module>.py

<test code>

Run pytest — these N tests MUST FAIL on current main.

If tests pass on first run → something's off. Investigate before proceeding.
```

Câu "if tests pass when expected to fail → investigate" là **TDD oracle** — catch agent confuse repo state.

Pair với:
- Test fixtures: real nếu task là parser/regression bug; synthetic OK cho feature
  test thông thường (xem §3.7 conditional anti-pattern)
- Test names self-documenting (`test_parse_findings_no_marker_extracts_p2_finding`)
- Expected behavior trong docstring, không trong test name

### 3.10 Atomic commit plan

```bash
git add tests/fixtures/...
git commit -m "test(<scope>): <real fixtures description>"

git add tests/unit/test_<module>.py
git commit -m "test(<scope>): <what behavior these test>"

git add <production file>
git commit -m "fix(<scope>): <what changed and why>"

# ... 1 commit per logical change
```

Rule: nếu reviewer cần bisect, commit phải atomic. Mega-commit "fix everything" làm bisect vô dụng.

### 3.11 Inline review section (P1+)

```
Step N — Inline Codex review with ≤3 fix rounds

Round N (1, 2, 3):
  codex review --base main 2>&1 | tee .autopilot/state/<task>/codex/round-NN.txt

Parse Codex output:
* Clean phrases → clean
* Otherwise extract findings:
  - P0/P1 → MUST fix this round
  - P2 → fix opportunistically; defer if scope creep
  - Keywords <schema|breaking|architectural> → ARCH_FINDING breaker → HALT
  - Keywords <auth|token|timing|secret|injection> → SECURITY_FINDING breaker → HALT
  - Same finding hash in N and N+1 → RECURRING_FINDING breaker → HALT

Fix round:
* Apply minimum-viable fix.
* Re-run local verify. MUST be green before next Codex round.
* Commit atomically: fix(<scope>): address codex round NN — <summary>

Clean signal (theo risk header §3.2):
* P1 → 2 consecutive clean rounds required.
* P2 pilot → 1 clean round acceptable.
* P2 mature with `--auto-merge` → 2 consecutive clean rounds required.
* P0 → not applicable (template không dùng cho P0 codegen).
* If max rounds reached without target clean count → MAX_ROUNDS breaker → HALT.
```

Cross-model review (Codex review code Claude viết) là defense-in-depth. Bắt buộc cho P1+ touching foundation/orchestrator/security.

### 3.12 Merge gate + (optional) squash block

**Default behavior: STOP_AT_READY.** Sau khi Codex clean target đạt + local verify
xanh, prompt phải STOP và emit READY report (xem §3.15). Founder làm squash + push
manually.

```
For P0:
  Template không apply — STOP, switch to manual workflow.

For P1 (any maturity):
  STOP at READY_FOR_MANUAL_MERGE.
  Do not run `git merge --squash`, `git commit`, or `git push origin main`.
  Branch remains intact. Emit READY report and exit.

For P2 pilot (<3 successful runs on this class of change):
  STOP at READY_FOR_MANUAL_MERGE.
  Same as P1.

For P2 mature (≥3 successful runs) AND prompt explicitly passes `--auto-merge`:
  Proceed with squash block below.
  In ALL OTHER cases (no `--auto-merge` flag, or maturity unproven): STOP_AT_READY.
```

Squash block (only when explicitly authorized above):

```bash
git checkout main
git pull --ff-only origin main

git merge --no-commit --no-ff <branch>   # Dry-run
git merge --abort

git merge --squash <branch>
git commit -m "<type>(<scope>): <title>

<full body with: what changed, why, validation, next steps>"

git branch -D <branch>
git push origin main
```

Commit body nên mention:
- What was caught/validated by Codex
- Test count delta
- Pointer to next steps (manual founder action sau autopilot)

Nếu push rejected → HALT. Do NOT force-push.

### 3.13 Circuit breakers

Numbered list, mỗi cái có **name** + **trigger condition**:

Universal set (paste mọi prompt):
1. Pre-flight regression — existing tests no longer pass on main
2. Push rejected (remote moved) — only fires when squash block authorized
3. TDD oracle violated (tests pass khi expected fail)
4. VERIFY_REGRESSION — local verify fails twice consecutively
5. ARCH_FINDING — Codex flags schema/breaking/architectural
6. SECURITY_FINDING — Codex flags auth/token/timing/secret/injection
7. RECURRING_FINDING — same hash in round N AND N+1
8. TYPE_IGNORE_PROPOSED — anywhere
9. MAX_ROUNDS — Codex rounds exhausted without target clean count (per §3.11)
10. Tool error twice in a row on git/codex/pytest
11. Context budget >70% — pause + report, founder resumes fresh session
12. POLICY_MISMATCH — prompt header tries to auto-merge a tier that requires
    manual_only (e.g., P1 with `--auto-merge`). Halt before any merge attempt.

Task-specific: thêm theo nature of task (e.g., FIXTURE_MISSING, MIGRATION_DRIFT).

### 3.14 Halt report template

```
HALT — <task> circuit broken.

Step:    <e.g. Step 11 round 2>
Trigger: <one of 11 conditions>
Branch:  <branch-name>
HEAD:    <SHA>

Detail:
<error output OR Codex finding excerpt OR rejected push reason>

State:
- Commits on branch since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/<task>/codex/round-*.txt
- Last verify result: <pass | fail with offending check>

Requesting founder input on:
<specific question>
```

Halt = forensic, không phải failure. Branch state IS the forensic file — đừng để agent cleanup.

### 3.15 Final report templates (verbatim)

Prompt phải emit **một trong hai** variants tùy merge gate (§3.12):

**Variant A — READY (default, merge_policy=manual_only)**

```
═══════════════════════════════════════════════════════
AUTOPILOT <task> — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════

Squash commit:    N/A — founder/manual merge pending
Branch <branch>:  still exists (intact, ready for review)
Push origin/main: NOT RUN

Files added: <list>
Files modified: <list>

Codex review:
  Round 01: <findings count | clean>
  Round 02: <findings count | clean>
  Final state: <target> clean rounds confirmed (per §3.2 merge policy)
  Artifacts: .autopilot/state/<task>/codex/round-*.txt

Local verification (final):
  ruff / black / mypy / lint-imports: clean
  pytest: <count> passed (baseline <N>, expected ≥<M>)

Decisions made during execution requiring founder review:
  <list any non-obvious calls>

═══════════════════════════════════════════════════════

Suggested squash command (founder runs after review):

  git checkout main
  git pull --ff-only origin main
  git merge --squash <branch>
  git commit -m "<type>(<scope>): <title>

  <body>"
  git branch -D <branch>
  git push origin main

═══════════════════════════════════════════════════════
```

**Variant B — COMPLETE (only when §3.12 squash block authorized + ran)**

```
═══════════════════════════════════════════════════════
AUTOPILOT <task> — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA>  <type>(<scope>): <title>
Branch <branch>: DELETED
Push origin/main: OK

(rest identical to READY format minus the "suggested squash" block)

═══════════════════════════════════════════════════════
```

Verbatim format = machine-parseable cho meta-orchestrator sau này.

---

## 4. Decision rules — chỗ template phân nhánh

### 4.1 Risk tier × merge policy (align với orchestrator v0.1 plan)

| Risk tier | Codegen via autopilot? | Codex review required | Merge policy |
|---|---|---|---|
| P0 (security/data, irreversible migration) | **No.** Template không apply. | N/A | Manual workflow only. Use template chỉ để generate review/checklist prompt, không generate implementation. |
| P1 (orchestrator/foundation, multi-tenant logic) | Yes | 2× consecutive clean | **manual_only** — STOP_AT_READY, founder squash + push. |
| P2 pilot (<3 successful autopilot runs on this class) | Yes | 1× clean | **manual_only** — STOP_AT_READY. |
| P2 mature (≥3 successful runs, prompt opt-in `--auto-merge`) | Yes | 2× consecutive clean | `auto_merge_after_2x_codex_clean` — squash + push allowed only when prompt explicitly passes `--auto-merge`. Default vẫn manual. |

Key rule: **auto-merge is opt-in per prompt, never default.** Nếu unclear → STOP_AT_READY.

### 4.2 Task shape × test/scope rules

| Variable | If... | Then... |
|---|---|---|
| Outcome verifiable? | Yes (parser, math, transform, API contract) | TDD-first mandatory |
| Real fixtures required? | Yes (parser/regression bug where CLI output is the data) | Capture real outputs, ban synthetic |
| Real fixtures required? | No (feature test, mock external service) | Synthetic payloads OK |
| Outcome verifiable? | No (refactor, docs) | Skip TDD, rely on hooks + regression suite |
| Touches schema/auth? | Yes | ARCH_FINDING + SECURITY_FINDING as primary breakers |
| New behavior? | Yes | Tests trước, atomic commits per behavior |
| Pure refactor? | Yes | Test suite must be green before & after, không tests mới |
| Cross-cutting? | Yes (>3 modules) | Split prompt — single-phase ăn chắc hơn |

---

## 5. Meta-lessons để encode

**5.1 Anti-patterns phải có lý do**, không abstract. Reason biến rule thành knowledge.

**5.2 Self-verification oracle phải tường minh.** Mỗi major step nên có 1 câu "if X happens, investigate before proceeding". Ngăn agent confuse repo state mà vẫn march forward.

**5.3 Authority matrix (concrete, không infer):**

| Action | P0 | P1 | P2 pilot | P2 mature |
|---|---|---|---|---|
| Write code on branch | No (template không apply) | Yes | Yes | Yes |
| Commit to branch | No | Yes | Yes | Yes |
| Run pytest / hooks locally | Manual workflow only | Yes | Yes | Yes |
| Squash merge to main | Founder only | Founder only | Founder only | Allowed only with explicit `--auto-merge` |
| Push origin main | Founder only | Founder only | Founder only | Allowed only with explicit `--auto-merge` |
| Force push | Never | Never | Never | Never |
| Add `# type: ignore` | Founder approval | Founder approval | Founder approval | Founder approval |
| Touch out-of-scope files | Never | Never | Never | Never |

Agent có thẩm quyền hành động trong cột applicable, nhưng có ceiling rõ ràng. Khi
ambiguous → default to lower authority (STOP_AT_READY, ask founder).

**5.4 Halt = forensic, không phải failure.** Halt report template + state preservation = resume được.

**5.5 Encode past incidents thành rules.** Mỗi rule nên có incident pointer; nếu không có → câu hỏi "rule này có cần không?".

**5.6 Single-phase ăn chắc hơn multi-phase.** Mega-prompt dễ drop trailing phase silently (memory: `autopilot_prompt_scope`).

**5.7 Context budget rule chỉ là safety net.** Agent đo self-context kém. Prefer ngắn từ đầu: scope ≤ 1 PR, ≤ 7 commits, ≤ 3 modules. Nếu prompt dài hơn 3-4 màn hình → split.

**5.8 Output template verbatim = machine-parseable.** Final report giúp founder skim 30 giây + feed vào meta-orchestrator. Đừng để agent "creative writing" summary.

**5.9 Distilling template từ 1 example — check 3 axis trước khi viết** (lesson từ template v1 → v2 → v3 cleanup 2026-05-13):
- **Plan/policy doc gốc** — example có on-policy không? Nếu không, đừng kế thừa drift. Với autopilot: đọc `autopilot-implementation-plan.md` trước.
- **Default direction** — safer default = lower authority + opt-in higher. Auto-merge/auto-push không phải default; STOP_AT_READY là default.
- **Authority enumeration** — list dưới dạng matrix (Action × Tier), không phải prose general. Prose <5 dòng = enumerate chưa đủ.

Nếu skip 3 check này, hậu quả: round 2 phải fix structural drift, round 3 phải fix downstream wording leftover. Tốn thời gian gấp 3 lần check upfront.

---

## 6. Quick checklist trước khi gửi prompt cho autopilot

- [ ] Header có working dir + branch name + mode + pause policy
- [ ] **Risk header block** (§3.2) có tier + merge_policy + maturity (REQUIRED)
- [ ] Nếu tier = P0 → STOP, không dùng template cho codegen
- [ ] Context block label rõ "NOT for execution"
- [ ] Scope có positive + negative + out-of-scope-documented
- [ ] Required reading list có line anchor
- [ ] Pre-flight hard gate với "ALL must pass"
- [ ] Anti-patterns mỗi cái có reason; synthetic-fixtures rule chỉ paste khi áp dụng
- [ ] Steps atomic, có expected output + sanity check
- [ ] TDD section (nếu verifiable) có "tests MUST fail" oracle
- [ ] Commit plan pre-written, atomic
- [ ] Inline review section (nếu P1+); clean target khớp với merge_policy
- [ ] Merge gate (§3.12) default STOP_AT_READY; squash block chỉ khi authorized
- [ ] 12+ circuit breakers named (gồm POLICY_MISMATCH)
- [ ] Halt report template
- [ ] Final report có **đúng variant** (READY vs COMPLETE) match merge policy
- [ ] Đóng bằng "Begin with Pre-flight, then Step 1."
- [ ] Prompt ≤ 4 màn hình; nếu hơn → split

---

## 7. Genealogy — prompts đã ship theo template này

| Version | Task | Risk tier | Merge | Date | Outcome |
|---|---|---|---|---|---|
| v0.2.1 | Codex parser fix + halt-writer + resume-from-HALTED | P1 | auto-merged (predates policy enforcement) | 2026-05-13 | Template baseline. Note: prompt v0.2.1 ran auto-squash-merge for a P1 change — this violates the locked manual_only policy and should not be repeated. v0.2.2+ must STOP_AT_READY for P1. |

(Add new entries here khi ship prompts mới.)
