# Task: Merge cascade #16 → #22 → #17 → #18 → #19

You are working in `/Users/maingocanh/Projects/MyMoneyWent` on MyMoneyWent — VN-first personal finance tracker. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — orchestrate merge cascade for stacked PR chain (C1 multi-tenant SePay pipeline) + independent PRs. PAUSE between merges for founder approval. Pause ONLY on circuit-breaker conditions OR at explicit human-in-loop checkpoints.

```
Risk tier:          P1
Merge policy:       manual_only (each merge requires founder explicit approval)
Autopilot maturity: pilot (first run on merge-cascade class)
Codex review:       not_applicable (PRs already reviewed; this prompt only orchestrates merges)
```

---

## Context (NOT for execution, just background)

PR stack as of 2026-05-15:

```
main
├── #16  fix/security-quickwins-260514         [CLEAN]   ← merge đầu
│   └── #17  feat/c1-p1-startup-wiring         [UNSTABLE → CLEAN sau #16]
│       └── #18  feat/c1-p2-route-mount        [UNSTABLE]
│           └── #19  feat/c1-p3-telemetry      [UNSTABLE]
│               └── #20  feat/c1-p5-retire-legacy  [DRAFT, gated P4+24h — OUT OF SCOPE]
│                   └── #21  fix/security-batch-b  [CLEAN — OUT OF SCOPE, rebase concern]
└── #22  chore/h1-plan-tier-enforcement        [UNSTABLE → CLEAN sau #16]
```

#16 contains CI workflow update (`.github/workflows/pr-validate.yml`) that adds `chore/*` exemption — unblocks #22's UNSTABLE status. Cascade order: #16 first, then #22 (docs only — lowest risk) parallel with #17, then #18 → #19.

---

## Scope of this prompt: ONLY merge orchestration

### Positive scope

1. **Pre-merge verification:** confirm #16 diff actually contains `chore/*` exemption in `.github/workflows/pr-validate.yml`.
2. **Merge #16** via `gh pr merge 16 --squash --delete-branch`.
3. **Pull main locally**, verify HEAD advanced.
4. **Wait for CI re-runs** on #17 + #22 (auto-triggered by base PR merge + retarget). Verify both turn CLEAN.
5. **PAUSE for founder approval before each subsequent merge** (#22, #17, #18, #19).
6. **Merge cascade** in this order: #22 → #17 → #18 → #19. Each merge waits for previous to advance main + downstream CI to re-run + CLEAN.
7. **Final summary report** with all merge SHAs + main HEAD progression.

### Negative scope (do NOT touch)

- **#20** (DRAFT, gated on Phase 4 + 24h). Do not merge, do not unstick.
- **#21** (CLEAN but stacked on #20 draft). Documented concern about rebase — founder decision separate PR.
- **Dependabot PRs #1-#7** (UNKNOWN status). Out of scope, batch handle later.
- **#15** (research/vn-competitive-round1 — UNKNOWN). Out of scope.
- **Local code changes** — this is pure merge orchestration. No commits except via `gh pr merge --squash`.
- **Force operations:** no `gh pr merge --rebase` (changes commit hash), no `git push --force`, no rewriting history.

### Out-of-scope but documented (do NOT do, point here)

- Rebase #21 onto post-#19 main to ship security batch B independent of #20. Founder per-decision; not in this run.
- Cleanup dependabot PRs (#1-#7) — needs per-PR test verification, batch later.
- Local `git pull` after each remote merge — included in steps but founder may prefer to defer until end.

---

## Required reading (READ FIRST, in this order, before any merge)

1. **Current PR state** (run this and verify against context):
   ```bash
   gh pr list --state open --json number,title,headRefName,baseRefName,mergeStateStatus,isDraft --limit 30
   ```
   Expected: #16 CLEAN, #17/18/19/22 UNSTABLE, #20 DRAFT, #21 CLEAN. If state diverges from expected (e.g., #16 became UNSTABLE) → HALT and report.

2. **#16 CI workflow change** (verify claim before relying on it):
   ```bash
   gh pr diff 16 -- .github/workflows/pr-validate.yml | head -100
   ```
   Expected: see additions like `chore/**` in branch matcher (`on.pull_request.branches`, `if: contains(...)`, or similar). If file unchanged or no `chore` pattern → HALT, recommendation invalid.

3. **#16 metadata** (sanity check):
   ```bash
   gh pr view 16 --json title,body,reviewDecision,statusCheckRollup
   ```

4. Memory references (do NOT edit, just be aware):
   - `feedback_concurrency_one_session` — STRICT 1 session per `.git/`. This prompt counts as 1 session; ensure no other Claude Code session is running merge ops on this repo.
   - `feedback_activate_venv_before_commit` — pre-commit hooks need venv. This prompt does no local commits but post-merge `git pull` may trigger hooks; activate venv first.

---

## Pre-flight gate

```bash
cd /Users/maingocanh/Projects/MyMoneyWent

# Auth + repo state
gh auth status                              # MUST be authenticated
git status                                  # MUST be clean (no uncommitted changes)
git branch --show-current                   # MUST be: main
git fetch origin
git pull --ff-only origin main              # MUST succeed (no divergent)

# Venv for any post-merge hook
source .venv/bin/activate
which lint-imports                          # MUST resolve (memory: feedback_activate_venv_before_commit)

# No other Claude Code session writing refs (per memory feedback_concurrency_one_session)
ls .git/*.lock 2>/dev/null                  # MUST be empty
ls .git/worktrees/                          # note any active worktrees (read-only check)

# Verify PR state matches expected context
gh pr list --state open --json number,mergeStateStatus,isDraft \
  --jq '.[] | select(.number == 16) | "PR 16: \(.mergeStateStatus)"'
# Expected: "PR 16: CLEAN". If UNSTABLE/BEHIND/DIRTY → HALT.

gh pr list --state open --json number,mergeStateStatus \
  --jq '.[] | select(.number == 22) | "PR 22: \(.mergeStateStatus)"'
# Expected: "PR 22: UNSTABLE". If already CLEAN → CI already updated, proceed.
```

ALL must pass. If any fails → HALT and report. Do not proceed.

---

## Anti-patterns (NEVER do)

* `gh pr merge --rebase` or `--merge` (creates merge commit). Reason: convention is squash-only per `feedback_autopilot_prompt_template`.
* `gh pr merge` without `--delete-branch`. Reason: leaves stale remote branches; cleanup pattern enforced.
* `git push --force` to main or any branch. Reason: rewrites history (memory `feedback_concurrency_one_session`).
* Merge any of #20, #21, dependabot PRs (#1-#7), #15. Reason: out of scope per Negative scope.
* Skip CI wait between merges. Reason: downstream PRs need base to advance + CI re-run; merging too fast = merging on stale CI.
* Skip founder approval checkpoint. Reason: P1 manual_only — each merge requires explicit "go" from founder.
* Touch local code, edit any file. Reason: pure orchestration; no commits.
* Resolve merge conflicts on PRs via `gh pr merge` retry. Reason: if conflict surfaces, branch needs manual rebase by PR author.

---

## Step 1 — Verify #16 contains CI exemption

```bash
gh pr diff 16 -- .github/workflows/pr-validate.yml > /tmp/pr16-workflow-diff.txt
cat /tmp/pr16-workflow-diff.txt | head -100
```

Search for: `chore`, `branches:`, `if:`, `contains`. Confirm there's a change adding `chore/*` or `chore/**` to a branch filter or condition.

**Decision:**
- ✅ Pattern found → proceed to Step 2.
- ❌ Pattern NOT found → HALT. The "#22 will turn CLEAN after #16" claim from prior session is invalid. Founder needs to investigate #22's actual blocker before this prompt is useful.

## Step 2 — Founder approval checkpoint: merge #16

PAUSE. Emit:

```
CHECKPOINT 1/5 — Ready to merge #16

PR:    #16 fix/security-quickwins-260514 → main
State: CLEAN
Diff:  17 files, 6 concerns bundled (security + CI + plans + tooling + deps + reports)
CI:    pass per pre-flight

This merge will:
- Advance main with security fixes + CI workflow update + C1 plan docs
- Trigger CI re-runs on #17 (now base=main) and #22 (chore/* exemption applies)
- Delete remote branch fix/security-quickwins-260514

Approve merge? (founder responds: GO / SKIP / HALT)
```

WAIT for founder response. Only proceed on explicit "GO".

## Step 3 — Merge #16

```bash
gh pr merge 16 --squash --delete-branch --auto=false
# --auto=false ensures we don't queue; merge immediately since CLEAN
```

Expected output: success message with squash commit SHA. Capture SHA.

Pull locally:
```bash
git fetch origin
git pull --ff-only origin main
git log -1 --format='%h %s'                # should show squashed #16 commit
```

If `gh pr merge` fails (e.g., PR became UNSTABLE between pre-flight and merge attempt) → HALT, report state.

## Step 4 — Wait for #17 + #22 CI re-runs

GitHub auto-retargets #17 base from `fix/security-quickwins-260514` (deleted) to `main`. CI re-runs on new base. #22 was independent on main — its CI re-runs because workflow file changed.

Poll state up to 10 minutes:

```bash
for i in {1..20}; do
  echo "--- Poll $i/20 ($(date +%H:%M:%S)) ---"
  gh pr list --state open --json number,mergeStateStatus \
    --jq '.[] | select(.number == 17 or .number == 22) | "PR \(.number): \(.mergeStateStatus)"'
  sleep 30
done
```

Stop polling when BOTH #17 and #22 show CLEAN. If after 10 min either still UNSTABLE → check CI logs:
```bash
gh pr checks 17
gh pr checks 22
```

If a check failed (not just slow) → HALT, report failing check. If all checks passing but mergeStateStatus stuck → may need manual `gh pr checks --watch` or wait more; founder decides.

## Step 5 — Founder approval checkpoint: merge #22

PAUSE. Emit:

```
CHECKPOINT 2/5 — Ready to merge #22

PR:    #22 chore/h1-plan-tier-enforcement → main
State: CLEAN (after #16 ship)
Type:  Pure docs — H1 plan-tier enforcement implementation plan
Risk:  LOW (no code)

This merge will:
- Add plan doc to plans/
- Delete remote branch chore/h1-plan-tier-enforcement

Approve merge? (GO / SKIP / HALT)
```

On GO:
```bash
gh pr merge 22 --squash --delete-branch --auto=false
git fetch origin && git pull --ff-only origin main
```

## Step 6 — Founder approval checkpoint: merge #17

PAUSE. Emit:

```
CHECKPOINT 3/5 — Ready to merge #17

PR:    #17 feat/c1-p1-startup-wiring → main
State: CLEAN (after #16 ship + retarget)
Type:  Infrastructure wiring — DB pool + Sentry + structlog + request_id at startup
Risk:  P1 (touches startup path; multi-tenant relevant)

This merge will:
- Wire startup infra for C1 multi-tenant SePay pipeline
- Trigger CI re-run on #18 (now base=main)
- Delete remote branch feat/c1-p1-startup-wiring

Approve merge? (GO / SKIP / HALT)
```

On GO:
```bash
gh pr merge 17 --squash --delete-branch --auto=false
git fetch origin && git pull --ff-only origin main
```

## Step 7 — Wait #18 CI re-run + checkpoint

Poll #18 up to 10 min same pattern as Step 4 (but only #18):
```bash
for i in {1..20}; do
  gh pr list --state open --json number,mergeStateStatus \
    --jq '.[] | select(.number == 18) | "PR 18: \(.mergeStateStatus)"'
  sleep 30
done
```

When #18 CLEAN → PAUSE for approval:

```
CHECKPOINT 4/5 — Ready to merge #18

PR:    #18 feat/c1-p2-route-mount → main
State: CLEAN
Type:  Mount POST /webhooks/sepay/{token} multi-tenant route
Risk:  P1 (new public webhook endpoint)

Approve merge? (GO / SKIP / HALT)
```

On GO:
```bash
gh pr merge 18 --squash --delete-branch --auto=false
git fetch origin && git pull --ff-only origin main
```

## Step 8 — Wait #19 CI re-run + checkpoint

Poll #19:
```bash
for i in {1..20}; do
  gh pr list --state open --json number,mergeStateStatus \
    --jq '.[] | select(.number == 19) | "PR 19: \(.mergeStateStatus)"'
  sleep 30
done
```

When CLEAN → PAUSE:

```
CHECKPOINT 5/5 — Ready to merge #19

PR:    #19 feat/c1-p3-telemetry → main
State: CLEAN
Type:  Parallel-run telemetry on legacy + v2 SePay dispatch
Risk:  P1 (telemetry only; legacy still primary)

This is the last merge in this cascade. After this merge:
- #20 (DRAFT) remains gated on Phase 4 + 24h
- #21 (security batch B) remains stacked on #20 — founder decides rebase later

Approve merge? (GO / SKIP / HALT)
```

On GO:
```bash
gh pr merge 19 --squash --delete-branch --auto=false
git fetch origin && git pull --ff-only origin main
```

## Step 9 — Final verification + report

```bash
# Verify main state
git log --oneline -10

# Verify open PR state
gh pr list --state open
```

Expected open PRs after cascade: #20 (DRAFT), #21 (stacked on #20), #15 (research), #1-#7 (dependabots). All others merged.

---

## Circuit breakers

1. **Pre-flight regression** — PR state diverges from expected context (e.g., #16 already merged, or became UNSTABLE).
2. **WORKFLOW_NOT_IN_DIFF** — Step 1 confirms #16 does NOT contain `chore/*` CI exemption. Recommendation invalid.
3. **CI_FAIL** — `gh pr checks <N>` shows failed check (not just slow). Branch needs PR-author fix before merge.
4. **CI_STUCK** — after 10 min polling, PR still UNSTABLE with all individual checks passing. Possible GitHub merge-state cache lag; founder decides to wait or investigate.
5. **MERGE_REJECTED** — `gh pr merge` returns error (e.g., branch protection rule, missing review).
6. **CONFLICT_ON_RETARGET** — downstream PR shows DIRTY mergeStateStatus after parent merge. Author needs manual rebase.
7. **CONCURRENCY_DETECTED** — `.git/*.lock` exists during run, or another Claude Code session detected via worktree usage. HALT to avoid ref-clobber (memory `feedback_concurrency_one_session`).
8. **PUSH_REJECTED** — `git pull` after merge fails (someone else pushed). Re-fetch + retry once; if persists, HALT.
9. **TIMEOUT** — any single step takes >15 min beyond CI poll loop. Founder may have stepped away; pause and resume.
10. **OUT_OF_SCOPE_MERGE_ATTEMPT** — if prompt logic somehow triggers merge of #20/#21/dependabot/etc, HALT immediately.
11. **CHECKPOINT_BYPASS** — any merge proceeds without explicit founder "GO". Architectural violation; HALT.
12. **TOOL_ERROR_TWICE** — `gh` or `git` errors twice in a row on same command. Network or auth issue.

---

## Halt report template

```
HALT — merge-cascade circuit broken.

Step:        <e.g. Step 4 polling CI>
Trigger:     <one of 12 conditions>
Branch:      main (no local branch created for this orchestration)
Main HEAD:   <SHA>

Detail:
<error output OR PR state divergence OR failing CI check>

State at halt:
- Merges completed so far: <list of PR numbers + squash SHAs>
- Merges remaining: <list>
- Open PR state:
  <gh pr list output>

Requesting founder input on:
<specific question — e.g., "should we wait longer for CI, or skip #18 and stop after #17?">
```

Halt = forensic. Do NOT auto-resume; founder decides next action.

---

## Final report — COMPLETE

```
═══════════════════════════════════════════════════════
AUTOPILOT merge-c1-cascade — COMPLETE
═══════════════════════════════════════════════════════

Merges in this cascade (in order):
  #16  fix/security-quickwins-260514     → squash <SHA1>
  #22  chore/h1-plan-tier-enforcement    → squash <SHA2>
  #17  feat/c1-p1-startup-wiring         → squash <SHA3>
  #18  feat/c1-p2-route-mount            → squash <SHA4>
  #19  feat/c1-p3-telemetry              → squash <SHA5>

Main HEAD before run: <SHA_start>
Main HEAD after run:  <SHA_end>
Commits added:        5

Remote branches deleted:
  fix/security-quickwins-260514
  chore/h1-plan-tier-enforcement
  feat/c1-p1-startup-wiring
  feat/c1-p2-route-mount
  feat/c1-p3-telemetry

Open PRs remaining (verified post-run):
  #20  feat/c1-p5-retire-legacy        DRAFT (gated Phase 4 + 24h)
  #21  fix/security-batch-b            CLEAN, stacked on #20 (rebase concern flagged)
  #15  research/vn-competitive-round1  UNKNOWN
  #1-#7  dependabot/*                  UNKNOWN

CI status (final):
  All workflows passing on main HEAD
  Dashboard auto-rebuild may be in progress (GH Action workflow)

Decisions made requiring founder review:
  <any non-obvious calls — e.g., extended CI wait, skipped step>

═══════════════════════════════════════════════════════

Suggested follow-up actions (founder per-decision):

1. Rebase #21 onto current main (or feat/c1-p4-* if exists) so security batch B
   ships independent of #20 retire-legacy DRAFT gating. SSRF + 9 H/M fixes
   shouldn't wait for cosmetic cleanup PR.

2. Batch-handle dependabot PRs #1-#7 with local test verification per bump
   (especially #6 ruff 0.4→0.15 major, #4 mypy 1.10→2.1 major).

3. Triage #15 (research/vn-competitive-round1) — UNKNOWN state, may need merge
   conflict resolve or rebase.

═══════════════════════════════════════════════════════
```

---

Begin with Pre-flight, then Step 1.
