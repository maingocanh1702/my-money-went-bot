# C1 Multi-Tenant SePay Pipeline — Cascade Merge Retrospective

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-15
> **Status:** Complete — C1 Phases 1-3 live on main
> **Owner:** Founder (dev)
> **Cowork session:** 2026-05-15 (~4 giờ, mixed thread với feature naming rename)
> **Tham chiếu:**
> - Memory: `feedback_stacked_pr_squash_cascade`, `feedback_activate_venv_before_commit`, `feedback_concurrency_one_session`, `feedback_autopilot_prompt_template`
> - Autopilot prompt: [`docs/autopilot/prompts/merge-c1-cascade-autopilot.md`](../autopilot/prompts/merge-c1-cascade-autopilot.md)
> - Related: [`docs/operations/f07-retrospective.md`](f07-retrospective.md) (prior pilot saga)
> - Implementation plan: [`plans/260514-2049-wire-multi-tenant-sepay-pipeline/`](../../plans/260514-2049-wire-multi-tenant-sepay-pipeline/)

---

## 1. Summary

Shipped Phases 1-3 của C1 multi-tenant SePay pipeline (DB pool wiring → webhook route mount → parallel-run telemetry) lên main qua 5 PRs (3 cherry-picked sau khi autopilot prompt assumption fail). Phát hiện 1 GitHub API deadlock không document trước (`--delete-branch` trên parent stacked PR auto-CLOSES children, refuses reopen+retarget). Phát triển + validate pattern cherry-pick recovery — proven zero-conflict do patch-id squash detection. 470/1/1 tests held constant. C1 Phase 4 (manual SePay dashboard ops) + Phase 5 (#20 retire-legacy) còn ngoài scope phiên này.

**Bottom line:** Task ship được nhưng tốn ~4 giờ vì autopilot prompt em viết có wrong assumption về GitHub auto-retarget behavior. Recovery pattern (cherry-pick) bây giờ đã document — future cascade prompts skip Option A path entirely.

---

## 2. Vấn đề (Problem)

### 2.1 Bài toán ban đầu

Anh có 7 PRs còn open ở thời điểm bắt đầu session:

```
main
├── #16  fix/security-quickwins-260514         [CLEAN]
│   └── #17  feat/c1-p1-startup-wiring         [UNSTABLE]
│       └── #18  feat/c1-p2-route-mount        [UNSTABLE]
│           └── #19  feat/c1-p3-telemetry      [UNSTABLE]
│               └── #20  feat/c1-p5-retire-legacy  [DRAFT — Phase 4 + 24h gated]
│                   └── #21  fix/security-batch-b  [CLEAN]
└── #22  chore/h1-plan-tier-enforcement        [UNSTABLE]
```

Goal: ship Phase 1-3 (#16, #22, #17, #18, #19) lên main. Defer #20 (DRAFT) + #21 (stacked on #20). PR #15 + dependabots out of scope.

### 2.2 Sub-problems

- **CI exemption dependency:** #22 UNSTABLE vì validate workflow chưa exempt `chore/*` branches. #16 contains fix; merge #16 → workflow updates → #22 unblock.
- **Stacked chain risk:** #17-#19 base lẫn nhau theo chain. Merge order phải đúng để CI re-run + base retarget hoạt động.
- **P1 risk tier:** security fixes + multi-tenant infra → manual review required, không auto-merge.
- **Concurrency:** anh có cowork session (em) + multiple Claude Code sessions parallel. Memory rule `feedback_concurrency_one_session` strict 1 session/`.git/`.

---

## 3. Giải pháp (Solution)

### 3.1 Merge order validate

Sau khi `gh pr list` + verify `.github/workflows/pr-validate.yml` thật sự trong diff #16:

1. **#16 → main** (CLEAN, không dep)
2. **#22 → main** parallel với #17 (sau #16 ship)
3. **#17 → main** sau khi #16 merge + GH auto-retarget #17 base sang main → CI re-run → CLEAN
4. **#18 → main** sau #17 (retarget cascade)
5. **#19 → main** sau #18

**Assumption (sai — sẽ thấy ở §5.1):** GitHub auto-retargets dependent PRs khi base bị `--delete-branch`.

### 3.2 Autopilot prompt design

Em viết `merge-c1-cascade-autopilot.md` với:

- **Risk tier:** P1 (touches main, security + multi-tenant)
- **Merge policy:** manual_only — STOP between merges cho founder approve via checkpoint
- **5 checkpoints:** 1 per merge (#16/#22/#17/#18/#19)
- **CI poll loops:** 10 min max giữa merges
- **12 circuit breakers** (CI fail, retarget fail, conflict, concurrency, etc.)
- **Pre-flight gate:** gh auth, clean status, venv active, no lock files

Pattern theo memory `feedback_autopilot_prompt_template` (15-section skeleton).

---

## 4. Quá trình execute

### 4.1 Phase 1 — Pre-flight + #16 ship

- ✅ `gh auth status`, `git status clean`, `git pull --ff-only origin main` — all pass
- ✅ Verify `.github/workflows/pr-validate.yml` trong diff #16 (24 files total, 6 concerns bundled — flag noted at §5.4)
- ✅ Founder GO checkpoint 1/5
- ✅ `gh pr merge 16 --squash --delete-branch --auto=false` → squash SHA `57b5b39`
- ✅ Pull main locally → HEAD advances

### 4.2 Phase 1 → Phase 2 transition — Deadlock surfaced

Sau khi #16 merged + `fix/security-quickwins-260514` deleted, expected state:
- #17 base auto-retargets từ deleted branch sang `main`
- #22 CI re-runs với updated workflow

**Actual state:**

```
#17  CLOSED  base=fix/security-quickwins-260514 (deleted)  DIRTY
#22  OPEN    base=main                                     UNSTABLE (stale validate)
```

GitHub **auto-closed #17** (didn't retarget). #22 didn't re-trigger validate (workflow file change on main không tự re-run existing PR).

### 4.3 Phase 1 recovery — #22 via empty commit

Em direct session khác:
```bash
git checkout chore/h1-plan-tier-enforcement
git commit --allow-empty -m "chore: trigger CI re-run after #16 chore/* exemption"
git push
```

Empty commit fires `synchronize` event → workflow re-runs với current main's pr-validate.yml (đã có chore exemption) → **CLEAN trong ~3 min** → merged `2a367b5`.

### 4.4 Phase 2 trial — Option A' (reopen + retarget #17)

Em proposed:
```bash
gh pr reopen 17
gh pr edit 17 --base main
```

**Both rejected by GitHub API:**

- `reopenPullRequest` → `"Could not open the pull request"` (because base branch is deleted)
- `updatePullRequest` → `"Cannot change the base branch of a closed pull request"`

**Deadlock**: cannot reopen because base deleted; cannot retarget because closed. No API path forward.

### 4.5 Phase 2 fallback — Option B cherry-pick

Pre-authorized fallback. Session executed for #17 → #18 → #19:

```bash
# Per PR — pattern repeated 3x
git log --oneline origin/<parent>..origin/<head>   # discover live SHA
gh pr close <N> --comment "..."                    # close orphan with cross-link
git checkout main && git pull
git checkout -b <head>-v2
git cherry-pick <discovered-sha>                   # patch-id detection → 0 conflicts
pytest                                              # 470/1/1 unchanged
git push -u origin <head>-v2
gh pr create --base main --head <head>-v2 --title "..." --body "..."
# HALT for founder approval
gh pr merge <new-N> --squash --delete-branch --auto=false
git pull --ff-only origin main
```

Results:

| Original PR | Closed | Live SHA | New PR | Merged SHA |
|---|---|---|---|---|
| #17 (256c6ee per directive) | closed | 256c6ee | #23 | `5ed5a33` |
| #18 (97c0f2e per directive) | closed | 8b25fb3 ⚠️ | #24 | `fd36764` |
| #19 (fda138d per directive) | closed | 566e916 ⚠️ | #25 | `7dd8d49` |

⚠️ = SHA drift; directive hardcoded original cascade SHAs but actual branch heads had been rebased earlier in session (see §5.3).

### 4.6 Outcome

```
Main HEAD before cascade: 13654c8 (rename ship)
Main HEAD after pull:     9349d35 (dashboard auto-rebuild)
Main HEAD after cascade:  7dd8d49 (c1-p3 telemetry)

20 commits added to main during cascade:
  5 feature/docs (the 5 actual PR squash commits)
  15 dashboard auto-rebuilds (GH Action firing on every push)
```

Tests: 470 passed, 1 skipped, 1 xfailed (the F02 funding_source_id contract pin, intentional W0.7 pin per memory).

---

## 5. Vấn đề gặp phải trong execute

### 5.1 🔴 GitHub `--delete-branch` cascade deadlock (CRITICAL)

**Trigger:** `gh pr merge 16 --squash --delete-branch` deleted `fix/security-quickwins-260514`. GitHub auto-closed #17 (whose base was that branch). Both `pr reopen` và `pr edit --base main` rejected.

**Impact:** Autopilot prompt's primary path (Option A "retarget cascade to main") **fundamentally broken** for any stacked PR cascade using `--delete-branch`. Phase 2 step required complete strategy switch mid-execution.

**Resolution:** Pre-authorized Option B (cherry-pick) executed cleanly. Patch-id squash detection means cherry-picked branches show only genuinely-new commits → zero conflicts in all 3 PRs.

**Root cause:** Em wrote autopilot prompt assuming GitHub UI's "retarget on base deletion" behavior applies to API operations. It doesn't. UI may suggest retarget; API closes the PR outright.

### 5.2 🔴 Pre-commit hook + venv (related earlier incident, same session)

**Trigger:** First commit attempt of rename squash merge (separate task, earlier in session) ran without venv active. Pre-commit hook tried to run `lint-imports` → not in system PATH → fail.

**Impact:** Commit aborted but `git push origin main` printed "Everything up-to-date" (no new commit to push). Followed immediately by `git branch -D chore/rename-feature-codes` which succeeded — branch ref deleted with rename work seemingly gone.

**Resolution:** Git objects 14-day dangling retention saved the day. `git branch -D` output included `(was 70d38f7)` — SHA known. Recreated branch from SHA, activated venv, re-squashed, committed clean. ~15 minutes diagnostic + recovery.

**Saved as:** `feedback_activate_venv_before_commit`.

### 5.3 🟡 SHA drift in autopilot directive

**Trigger:** Em wrote directive referencing SHAs from earlier cascade docs (97c0f2e, fda138d). By the time session ran cherry-pick, those branches had been rebased internally → actual HEAD SHAs were 8b25fb3, 566e916.

**Impact:** Confusion mid-execution. Session correctly discovered live SHAs via `git log <base>..<head>` and proceeded, but each cherry-pick required SHA correction step.

**Resolution:** Session adapted — `git log --oneline origin/<parent>..origin/<head>` always run before cherry-pick to discover live SHA.

**Rule for future prompts:** Never hardcode SHAs. Always have agent discover live.

### 5.4 🟡 Mixed-scope PR #16

**Observation:** PR #16 title "security quick wins + C1 plan" but diff actually contains 6 concerns: security fixes + CI workflow updates + C1 plan docs (6 files) + code review/security scan reports + autopilot tooling + dependency bumps.

**Impact:** Hard to bisect if bug surfaces. Memory rule `feedback_autopilot_prompt_scope` says single-phase scope safer.

**Decision:** Em flagged but did not block merge. Already CLEAN, leading position. Note for future PRs.

### 5.5 🟡 Workflow re-trigger non-automatic

**Trigger:** After #16 updated `.github/workflows/pr-validate.yml` on main with `chore/*` exemption, #22's validate workflow didn't auto-re-run. Validate triggers on `[opened, edited, synchronize, ready_for_review]` events — none fired by main workflow file change.

**Impact:** #22 stuck UNSTABLE indefinitely without intervention.

**Resolution:** Empty commit pattern — `git commit --allow-empty` fires synchronize event → workflow re-runs with current main's workflow files.

**Saved as:** part of `feedback_stacked_pr_squash_cascade` (workflow re-trigger pattern section).

### 5.6 🟡 Dashboard auto-rebuild noise

**Observation:** GH Action `.github/workflows/dashboard.yml` fires on branches `[main, feat/**, infra/**, chore/**, fix/**]` and commits rebuilt dashboard back to main on every push. 15 of 20 commits in cascade range were dashboard auto-rebuilds.

**Impact:** Inflates merge history. Not a bug; pre-existing behavior.

**Decision:** Founder declined optimization this session (em offered: change schedule daily + skip-empty rebuild). Keep as is.

### 5.7 🟡 PR #21 stacked on DRAFT #20

**Observation:** #21 contains 9 security fixes (H5, H7, M1-M7, SSRF). Stacked on `feat/c1-p5-retire-legacy` (#20) which is DRAFT gated on Phase 4 + 24h.

**Impact:** Security batch B blocked behind cosmetic cleanup. Anti-pattern: high-severity fixes shouldn't wait for low-priority dependencies.

**Decision:** Flagged for future PR. Deferred this session — em proposed rebase, anh defer decision.

### 5.8 🟡 Multi-session orchestration complexity

**Observation:** Em counted 3-4 sessions across the day (cowork orchestrator + rename autopilot + C1 cascade autopilot + possibly PR triage session). Anh asked big-picture mid-execution ("tại sao nhiều phiên xử lý").

**Impact:** Real cognitive load on founder. Switching context between sessions takes time.

**Resolution:** Pattern intentional per memory rules (concurrency safety, audit trail, risk gating). Em provided big-picture recap. Pattern stays but worth re-evaluating per task complexity.

---

## 6. Lessons learned cho lần sau

### 6.1 Updates cần làm cho autopilot prompt template

1. **Add to anti-patterns section:** "Never assume GitHub auto-retargets dependent PRs when parent base is `--delete-branch`'d. Always use cherry-pick path for stacked PR cascades."

2. **Add to merge-cascade template:** Default to Option B (cherry-pick) from start. Skip Option A path entirely. Memory: `feedback_stacked_pr_squash_cascade`.

3. **Add SHA discovery step:** Replace any hardcoded SHA references with `git log --oneline origin/<base>..origin/<head>` to discover live HEAD. Document in template §3.8 (Numbered steps) requirement.

4. **Add workflow re-trigger note:** After main workflow file changes, existing PRs need explicit synchronize event. Empty commit pattern documented.

### 6.2 Pre-flight gate enforcement

1. **Venv check mandatory in pre-flight** — already in template §3.6 (`which lint-imports MUST resolve`). Reinforce.

2. **No commit-push-cleanup bundle** — split into 2 explicit steps with `git log -1 --format=%s` verification between. Memory: `feedback_activate_venv_before_commit`.

3. **"Everything up-to-date" ≠ success** — add explicit verification step after push: `git log origin/main..HEAD --oneline` should be empty after successful push.

### 6.3 PR hygiene

1. **Avoid mixed-scope PRs** — #16's 6-concern bundle hard to bisect. Future security fixes ship separately from CI changes ship separately from plan docs.

2. **Don't stack security on DRAFT** — #21 anti-pattern. Critical/security fixes should land on main directly or on minimal-scope parent, never on cosmetic cleanup gated by external dependencies.

3. **Single-phase scope still wins** — memory `feedback_autopilot_prompt_scope` reinforced. Hôm nay 1 autopilot prompt covered 5 merges; pattern worked but per-merge complexity was high.

### 6.4 Cascade-specific patterns to encode

1. **Cherry-pick recovery validated** — patch-id squash detection means cherry-picked branches off post-squash main produce **zero conflicts** for incremental commits. Validated 3/3 in this session.

2. **Per-PR live SHA discovery** — `git log <base>..<head>` always reveals the single incremental commit (or chain) without prompt hardcoding. Robust against in-session rebase.

3. **Founder approval per merge in cascade** — 5 checkpoints worked. Pattern stays for P1.

### 6.5 Process / fatigue management

1. **4-hour multi-thread sessions** — real cognitive load. Memory `feedback_project_level_effectiveness` says 6/8-axis ROI but per-session founder fatigue is real cost.

2. **Wrap when momentum ends** — em offered wrap-up multiple times; anh continued. Both valid. Em recommend explicit "I'm done" signal to ourselves to avoid drift.

3. **Big-picture recap mid-session** — em did this when anh asked. Pattern worth standardizing: every ~2 hours, recap "what's done, what's in progress, what's deferred".

### 6.6 Follow-ups created by this task

| Task | Owner | Status | Source |
|---|---|---|---|
| Update merge-cascade template (§6.1) | Founder | ⬜ | This retro §6.1 |
| Rebase #21 off #20 DRAFT | Founder | ⬜ defer | §5.7 |
| Triage #20 retire-legacy (Phase 4 + 24h gate) | Founder | ⬜ pending Phase 4 ops | §1 |
| Batch dependabot PRs #1-#7 | Founder | ⬜ defer | Out of scope |
| #15 research PR triage | Founder | ⬜ | Out of scope |
| 3 follow-up PRs from rename task | Founder | ⬜ | rename retro |
| Spec writing manual-transaction-entry | Founder | ⬜ defer | Strategic thread |

---

## 7. Metrics + outcomes

### 7.1 Throughput

- **Original PRs in queue:** 7 (#16, #17, #18, #19, #20, #21, #22)
- **PRs targeted this session:** 5 (#16, #22, #17, #18, #19)
- **PRs merged:** 5 (3 original + 2 cherry-picked replacements ... wait, accurate count: #16 original, #22 original, #23 [replaces #17], #24 [replaces #18], #25 [replaces #19])
- **PRs auto-closed (replaced):** 3 (#17, #18, #19)
- **PRs deferred per scope:** 2 (#20 DRAFT, #21 security batch B)
- **PRs out of scope:** 8 (#1-#7 dependabots, #15 research)

### 7.2 Code velocity

| Metric | Value |
|---|---|
| Commits added to main | 20 (5 feature + 15 dashboard auto-rebuilds) |
| Main HEAD start of cascade | `13654c8` |
| Main HEAD end of cascade | `7dd8d49` |
| Tests baseline (constant) | 470 passed / 1 skipped / 1 xfailed |
| Cherry-pick conflicts | 0 / 3 |
| Memory notes added | 4 (2 decision + 2 incident lessons) |

### 7.3 Time breakdown (estimated)

| Phase | Wall time | Notes |
|---|---|---|
| Phase 1 ship (#16, #22) | ~30 min | #16 merge + CI poll + #22 empty commit + #22 merge |
| Phase 2 trial (A' attempt) | ~5 min | Discovered deadlock, switched to B |
| Phase 2 recovery × 3 (cherry-pick + tests + PR + merge) | ~45 min | ~15 min/PR including CI wait + founder review |
| Diagnostic + memory notes + retrospective | ~30 min | This doc + earlier memory writes |
| Strategic thread (rename, decisions) | ~120 min | Parallel thread, separate retrospective justified if pursued |
| **Total session** | **~4 hours** | Mixed threads |

### 7.4 Memory artifacts

- `feedback_stacked_pr_squash_cascade.md` — deadlock + cherry-pick pattern (NEW)
- `feedback_activate_venv_before_commit.md` — pre-commit + venv (NEW)
- `project_feature_naming_convention.md` — rename convention (NEW, parallel thread)
- `project_manual_transaction_entry_decisions.md` — manual entry 13 decisions (NEW, parallel thread)

---

## 8. Cross-references

- **Memory:** `feedback_stacked_pr_squash_cascade`, `feedback_activate_venv_before_commit`, `feedback_concurrency_one_session`, `feedback_autopilot_prompt_template`, `project_dashboard_auto_gen`
- **Autopilot prompt that ran:** [`merge-c1-cascade-autopilot.md`](../autopilot/prompts/merge-c1-cascade-autopilot.md) (has bug per §5.1; update per §6.1)
- **Implementation plan:** [`plans/260514-2049-wire-multi-tenant-sepay-pipeline/`](../../plans/260514-2049-wire-multi-tenant-sepay-pipeline/)
- **Prior retrospective format:** [`f07-retrospective.md`](f07-retrospective.md)
- **PRs (GitHub):** #16, #17 (closed), #18 (closed), #19 (closed), #22, #23, #24, #25

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-15 | Initial retro after C1 Phases 1-3 cascade complete. Documents stacked-PR-squash deadlock (§5.1) + recovery via cherry-pick + 8 issues + 6 lesson categories + metrics + follow-ups. Saves complete record for template updates in §6.1. |
