# Hồi cứu (Retrospective) — Cascade Merge của C1 Multi-Tenant SePay Pipeline

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-15
> **Status:** Hoàn tất — C1 Phases 1-3 đã live trên main
> **Owner:** Founder (dev)
> **Cowork session:** 2026-05-15 (~4 giờ, mixed thread với feature naming rename)
> **Bản tiếng Anh:** [`c1-cascade-retrospective.md`](c1-cascade-retrospective.md)
> **Tham chiếu:**
> - Memory: `feedback_stacked_pr_squash_cascade`, `feedback_activate_venv_before_commit`, `feedback_concurrency_one_session`, `feedback_autopilot_prompt_template`
> - Autopilot prompt: [`docs/autopilot/prompts/merge-c1-cascade-autopilot.md`](../autopilot/prompts/merge-c1-cascade-autopilot.md)
> - Liên quan: [`docs/operations/f07-retrospective.md`](f07-retrospective.md) (pilot saga trước)
> - Implementation plan: [`plans/260514-2049-wire-multi-tenant-sepay-pipeline/`](../../plans/260514-2049-wire-multi-tenant-sepay-pipeline/)

---

## 1. Tóm tắt

Đã ship Phases 1-3 của C1 multi-tenant SePay pipeline (wiring DB pool → mount webhook route → parallel-run telemetry) lên main qua 5 PRs (3 cái phải cherry-pick lại sau khi autopilot prompt assumption fail). Phát hiện 1 deadlock của GitHub API không document trước (`--delete-branch` trên parent của stacked PR auto-CLOSES children, và refuses cả reopen + retarget). Phát triển + validate pattern cherry-pick recovery — proven zero-conflict do patch-id squash detection. Tests giữ nguyên 470/1/1. C1 Phase 4 (manual SePay dashboard ops) + Phase 5 (#20 retire-legacy) còn ngoài scope phiên này.

**Kết luận:** Task ship được nhưng tốn ~4 giờ vì autopilot prompt em viết có assumption sai về behavior auto-retarget của GitHub. Recovery pattern (cherry-pick) bây giờ đã document — future cascade prompts sẽ skip Option A path hoàn toàn.

---

## 2. Vấn đề (Problem)

### 2.1 Bài toán ban đầu

Đầu phiên anh có 7 PRs còn open:

```
main
├── #16  fix/security-quickwins-260514         [CLEAN]
│   └── #17  feat/c1-p1-startup-wiring         [UNSTABLE]
│       └── #18  feat/c1-p2-route-mount        [UNSTABLE]
│           └── #19  feat/c1-p3-telemetry      [UNSTABLE]
│               └── #20  feat/c1-p5-retire-legacy  [DRAFT — gated Phase 4 + 24h]
│                   └── #21  fix/security-batch-b  [CLEAN]
└── #22  chore/h1-plan-tier-enforcement        [UNSTABLE]
```

Mục tiêu: ship Phase 1-3 (#16, #22, #17, #18, #19) lên main. Defer #20 (DRAFT) + #21 (stacked on #20). PR #15 + dependabots out of scope.

### 2.2 Các sub-problem

- **CI exemption dependency:** #22 UNSTABLE vì validate workflow chưa exempt nhánh `chore/*`. #16 chứa fix; sau khi #16 merge thì workflow update → #22 unblock.
- **Risk của stacked chain:** #17-#19 base lẫn nhau theo chain. Thứ tự merge phải đúng để CI re-run + base retarget hoạt động.
- **P1 risk tier:** fixes security + multi-tenant infra → cần manual review, không auto-merge.
- **Concurrency:** anh có cowork session (em) + nhiều Claude Code sessions parallel. Memory rule `feedback_concurrency_one_session` strict 1 session per `.git/`.

---

## 3. Giải pháp (Solution)

### 3.1 Validate merge order

Sau khi chạy `gh pr list` + verify `.github/workflows/pr-validate.yml` thật sự trong diff #16:

1. **#16 → main** (CLEAN, không có dep)
2. **#22 → main** parallel với #17 (sau khi #16 ship)
3. **#17 → main** sau khi #16 merge + GH auto-retarget base #17 sang main → CI re-run → CLEAN
4. **#18 → main** sau #17 (retarget cascade)
5. **#19 → main** sau #18

**Assumption (sai — sẽ thấy ở §5.1):** GitHub tự retarget dependent PRs khi base bị `--delete-branch`.

### 3.2 Thiết kế autopilot prompt

Em viết `merge-c1-cascade-autopilot.md` với:

- **Risk tier:** P1 (touches main, security + multi-tenant)
- **Merge policy:** manual_only — STOP giữa các merge để founder approve qua checkpoint
- **5 checkpoints:** 1 cho mỗi merge (#16/#22/#17/#18/#19)
- **CI poll loops:** tối đa 10 min giữa các merge
- **12 circuit breakers** (CI fail, retarget fail, conflict, concurrency, v.v.)
- **Pre-flight gate:** gh auth, status sạch, venv active, không có lock file

Pattern theo memory `feedback_autopilot_prompt_template` (skeleton 15 section).

---

## 4. Quá trình execute

### 4.1 Phase 1 — Pre-flight + ship #16

- ✅ `gh auth status`, `git status` sạch, `git pull --ff-only origin main` — all pass
- ✅ Verify `.github/workflows/pr-validate.yml` trong diff #16 (tổng 24 files, 6 concerns bundled — flag note ở §5.4)
- ✅ Founder GO checkpoint 1/5
- ✅ `gh pr merge 16 --squash --delete-branch --auto=false` → squash SHA `57b5b39`
- ✅ Pull main local → HEAD advance

### 4.2 Phase 1 → Phase 2 transition — Deadlock xuất hiện

Sau khi #16 merge + `fix/security-quickwins-260514` bị delete, state mong đợi:
- Base của #17 tự retarget từ deleted branch sang `main`
- CI của #22 re-run với updated workflow

**State thực tế:**

```
#17  CLOSED  base=fix/security-quickwins-260514 (deleted)  DIRTY
#22  OPEN    base=main                                     UNSTABLE (stale validate)
```

GitHub **auto-close #17** (không retarget). #22 không tự re-trigger validate (workflow file change trên main không tự re-run existing PR).

### 4.3 Phase 1 recovery — #22 qua empty commit

Em direct session khác:
```bash
git checkout chore/h1-plan-tier-enforcement
git commit --allow-empty -m "chore: trigger CI re-run after #16 chore/* exemption"
git push
```

Empty commit fires `synchronize` event → workflow re-runs với pr-validate.yml hiện tại của main (đã có chore exemption) → **CLEAN trong ~3 phút** → merged `2a367b5`.

### 4.4 Phase 2 trial — Option A' (reopen + retarget #17)

Em propose:
```bash
gh pr reopen 17
gh pr edit 17 --base main
```

**Cả hai đều bị GitHub API reject:**

- `reopenPullRequest` → `"Could not open the pull request"` (vì base branch bị delete)
- `updatePullRequest` → `"Cannot change the base branch of a closed pull request"`

**Deadlock**: không reopen được vì base đã bị delete; không retarget được vì PR đã closed. Không có path qua API.

### 4.5 Phase 2 fallback — Option B cherry-pick

Đã được pre-authorize. Session execute cho #17 → #18 → #19:

```bash
# Mỗi PR — pattern lặp 3 lần
git log --oneline origin/<parent>..origin/<head>   # discover SHA live
gh pr close <N> --comment "..."                    # close orphan với cross-link
git checkout main && git pull
git checkout -b <head>-v2
git cherry-pick <discovered-sha>                   # patch-id detection → 0 conflicts
pytest                                              # 470/1/1 không đổi
git push -u origin <head>-v2
gh pr create --base main --head <head>-v2 --title "..." --body "..."
# HALT cho founder approve
gh pr merge <new-N> --squash --delete-branch --auto=false
git pull --ff-only origin main
```

Kết quả:

| PR gốc | Closed | SHA live | PR mới | Merged SHA |
|---|---|---|---|---|
| #17 (256c6ee per directive) | closed | 256c6ee | #23 | `5ed5a33` |
| #18 (97c0f2e per directive) | closed | 8b25fb3 ⚠️ | #24 | `fd36764` |
| #19 (fda138d per directive) | closed | 566e916 ⚠️ | #25 | `7dd8d49` |

⚠️ = SHA drift; directive hardcode SHA gốc của cascade nhưng head branch thực tế đã bị rebase trước đó trong phiên (xem §5.3).

### 4.6 Kết quả

```
Main HEAD trước cascade: 13654c8 (rename ship)
Main HEAD sau pull:      9349d35 (dashboard auto-rebuild)
Main HEAD sau cascade:   7dd8d49 (c1-p3 telemetry)

20 commits thêm vào main trong cascade:
  5 feature/docs (5 squash commit của 5 PR thực tế)
  15 dashboard auto-rebuild (GH Action fire mỗi push)
```

Tests: 470 passed, 1 skipped, 1 xfailed (F02 funding_source_id contract pin, intentional W0.7 pin theo memory).

---

## 5. Vấn đề gặp phải trong execute

### 5.1 🔴 GitHub `--delete-branch` cascade deadlock (CRITICAL)

**Trigger:** `gh pr merge 16 --squash --delete-branch` xoá `fix/security-quickwins-260514`. GitHub auto-close #17 (base là branch đó). Cả `pr reopen` và `pr edit --base main` đều bị reject.

**Impact:** Path chính của autopilot prompt (Option A "retarget cascade sang main") **fundamentally broken** cho bất kỳ stacked PR cascade nào dùng `--delete-branch`. Phase 2 phải switch strategy hoàn toàn giữa chừng.

**Resolution:** Pre-authorized Option B (cherry-pick) execute sạch. Patch-id squash detection làm cho cherry-picked branches chỉ show commit thật sự mới → zero conflicts ở cả 3 PR.

**Root cause:** Em viết autopilot prompt assume behavior "retarget on base deletion" của UI GitHub apply cho API operation. Không apply. UI có thể suggest retarget; API đóng PR luôn.

### 5.2 🔴 Pre-commit hook + venv (incident liên quan trước đó, cùng phiên)

**Trigger:** Lần commit đầu của squash merge rename (task khác, sớm hơn trong phiên) chạy mà venv chưa active. Pre-commit hook chạy `lint-imports` → không trong system PATH → fail.

**Impact:** Commit abort nhưng `git push origin main` in "Everything up-to-date" (không có commit mới để push). Ngay sau đó `git branch -D chore/rename-feature-codes` chạy success — branch ref bị delete và rename work tưởng như mất.

**Resolution:** Git objects 14-day dangling retention cứu vớt. Output `git branch -D` có `(was 70d38f7)` — SHA biết được. Recreate branch từ SHA, activate venv, re-squash, commit sạch. ~15 phút diagnostic + recovery.

**Saved as:** `feedback_activate_venv_before_commit`.

### 5.3 🟡 SHA drift trong autopilot directive

**Trigger:** Em viết directive reference SHA từ doc cascade trước đó (97c0f2e, fda138d). Đến lúc session chạy cherry-pick, các branch đã bị rebase internal → HEAD SHA thực tế là 8b25fb3, 566e916.

**Impact:** Confusion giữa execute. Session correctly discover SHA live qua `git log <base>..<head>` và proceed, nhưng mỗi cherry-pick cần step correct SHA.

**Resolution:** Session adapt — luôn chạy `git log --oneline origin/<parent>..origin/<head>` trước cherry-pick để discover SHA live.

**Rule cho future prompts:** Không bao giờ hardcode SHA. Luôn để agent discover live.

### 5.4 🟡 PR #16 mixed-scope

**Observation:** Title #16 "security quick wins + C1 plan" nhưng diff thực tế chứa 6 concerns: security fixes + CI workflow updates + C1 plan docs (6 files) + code review/security scan reports + autopilot tooling + dependency bumps.

**Impact:** Khó bisect khi bug surface. Memory rule `feedback_autopilot_prompt_scope` nói single-phase scope an toàn hơn.

**Decision:** Em flag nhưng không block merge. Đã CLEAN, vị trí dẫn đầu. Note cho future PR.

### 5.5 🟡 Workflow re-trigger không tự động

**Trigger:** Sau khi #16 update `.github/workflows/pr-validate.yml` trên main với `chore/*` exemption, validate workflow của #22 không tự re-run. Validate trigger trên `[opened, edited, synchronize, ready_for_review]` events — không event nào fire bởi workflow file change trên main.

**Impact:** #22 stuck UNSTABLE vô hạn nếu không intervention.

**Resolution:** Empty commit pattern — `git commit --allow-empty` fire synchronize event → workflow re-run với workflow file hiện tại của main.

**Saved as:** trong `feedback_stacked_pr_squash_cascade` (section workflow re-trigger pattern).

### 5.6 🟡 Dashboard auto-rebuild noise

**Observation:** GH Action `.github/workflows/dashboard.yml` fire trên branches `[main, feat/**, infra/**, chore/**, fix/**]` và commit dashboard rebuilt back to main mỗi push. 15/20 commits trong cascade range là dashboard auto-rebuild.

**Impact:** Inflate merge history. Không phải bug; pre-existing behavior.

**Decision:** Founder declined optimization phiên này (em offered: đổi schedule daily + skip-empty rebuild). Keep as is.

### 5.7 🟡 PR #21 stacked trên DRAFT #20

**Observation:** #21 chứa 9 security fixes (H5, H7, M1-M7, SSRF). Stacked trên `feat/c1-p5-retire-legacy` (#20) là DRAFT gated Phase 4 + 24h.

**Impact:** Security batch B block đằng sau cleanup cosmetic. Anti-pattern: fixes high-severity không nên chờ low-priority dependencies.

**Decision:** Flag cho future PR. Defer phiên này — em propose rebase, anh defer decision.

### 5.8 🟡 Multi-session orchestration phức tạp

**Observation:** Em count 3-4 sessions trong ngày (cowork orchestrator + rename autopilot + C1 cascade autopilot + có thể PR triage session). Anh hỏi big-picture giữa execute ("tại sao nhiều phiên xử lý").

**Impact:** Cognitive load thật trên founder. Switching context giữa các session tốn thời gian.

**Resolution:** Pattern intentional per memory rules (concurrency safety, audit trail, risk gating). Em provide big-picture recap. Pattern stays nhưng đáng re-evaluate per task complexity.

---

## 6. Lessons learned cho lần sau

### 6.1 Update cần làm cho autopilot prompt template

1. **Add vào anti-patterns section:** "Đừng assume GitHub tự retarget dependent PRs khi parent base bị `--delete-branch`'d. Luôn dùng cherry-pick path cho stacked PR cascades."

2. **Add vào merge-cascade template:** Default Option B (cherry-pick) từ đầu. Skip Option A path hoàn toàn. Memory: `feedback_stacked_pr_squash_cascade`.

3. **Add SHA discovery step:** Thay tất cả reference SHA hardcoded bằng `git log --oneline origin/<base>..origin/<head>` để discover HEAD live. Document trong template §3.8 (Numbered steps) requirement.

4. **Add workflow re-trigger note:** Sau khi workflow file của main thay đổi, existing PR cần explicit synchronize event. Empty commit pattern được document.

### 6.2 Enforce pre-flight gate

1. **Venv check bắt buộc trong pre-flight** — đã có trong template §3.6 (`which lint-imports MUST resolve`). Reinforce.

2. **Không bundle commit-push-cleanup** — tách thành 2 step explicit với `git log -1 --format=%s` verify giữa. Memory: `feedback_activate_venv_before_commit`.

3. **"Everything up-to-date" ≠ success** — add explicit verification step sau push: `git log origin/main..HEAD --oneline` phải empty sau khi push success.

### 6.3 PR hygiene

1. **Tránh mixed-scope PRs** — bundle 6-concern của #16 khó bisect. Future security fixes ship riêng với CI changes ship riêng với plan docs.

2. **Đừng stack security trên DRAFT** — anti-pattern của #21. Critical/security fixes nên land trên main trực tiếp hoặc trên parent minimal-scope, không bao giờ trên cleanup cosmetic gated bởi external dependency.

3. **Single-phase scope vẫn thắng** — memory `feedback_autopilot_prompt_scope` reinforced. Hôm nay 1 autopilot prompt cover 5 merges; pattern work nhưng complexity per-merge cao.

### 6.4 Cascade-specific patterns cần encode

1. **Cherry-pick recovery validated** — patch-id squash detection làm cho cherry-picked branches off post-squash main produce **zero conflicts** cho incremental commit. Validated 3/3 trong phiên này.

2. **Per-PR live SHA discovery** — `git log <base>..<head>` luôn reveal single incremental commit (hoặc chain) mà không cần hardcode trong prompt. Robust với rebase giữa phiên.

3. **Founder approval per merge trong cascade** — 5 checkpoints work. Pattern stay cho P1.

### 6.5 Quản lý process / fatigue

1. **Multi-thread session 4-tiếng** — cognitive load thật. Memory `feedback_project_level_effectiveness` nói ROI 6/8-axis nhưng founder fatigue per-session là cost thật.

2. **Wrap khi momentum hết** — em offer wrap-up nhiều lần; anh continue. Cả hai đều valid. Em recommend explicit "I'm done" signal cho chính mình để tránh drift.

3. **Big-picture recap giữa session** — em làm khi anh hỏi. Pattern đáng standardize: mỗi ~2 giờ, recap "đã xong gì, đang làm gì, defer gì".

### 6.6 Follow-up tạo bởi task này

| Task | Owner | Status | Nguồn |
|---|---|---|---|
| Update merge-cascade template (§6.1) | Founder | ⬜ | Retro này §6.1 |
| Rebase #21 khỏi #20 DRAFT | Founder | ⬜ defer | §5.7 |
| Triage #20 retire-legacy (gated Phase 4 + 24h) | Founder | ⬜ chờ Phase 4 ops | §1 |
| Batch dependabot PRs #1-#7 | Founder | ⬜ defer | Out of scope |
| Triage #15 research PR | Founder | ⬜ | Out of scope |
| 3 follow-up PRs từ rename task | Founder | ⬜ | Retro rename |
| Spec writing manual-transaction-entry | Founder | ⬜ defer | Strategic thread |

---

## 7. Metrics + outcomes

### 7.1 Throughput

- **PRs gốc trong queue:** 7 (#16, #17, #18, #19, #20, #21, #22)
- **PRs target phiên này:** 5 (#16, #22, #17, #18, #19)
- **PRs merged:** 5 (#16 gốc, #22 gốc, #23 [replace #17], #24 [replace #18], #25 [replace #19])
- **PRs auto-closed (replaced):** 3 (#17, #18, #19)
- **PRs deferred per scope:** 2 (#20 DRAFT, #21 security batch B)
- **PRs out of scope:** 8 (#1-#7 dependabots, #15 research)

### 7.2 Code velocity

| Metric | Value |
|---|---|
| Commits added to main | 20 (5 feature + 15 dashboard auto-rebuilds) |
| Main HEAD start cascade | `13654c8` |
| Main HEAD end cascade | `7dd8d49` |
| Tests baseline (không đổi) | 470 passed / 1 skipped / 1 xfailed |
| Cherry-pick conflicts | 0 / 3 |
| Memory notes added | 4 (2 decision + 2 incident lessons) |

### 7.3 Phân bổ thời gian (estimate)

| Phase | Wall time | Ghi chú |
|---|---|---|
| Phase 1 ship (#16, #22) | ~30 phút | #16 merge + CI poll + #22 empty commit + #22 merge |
| Phase 2 trial (A' attempt) | ~5 phút | Discover deadlock, switch sang B |
| Phase 2 recovery × 3 (cherry-pick + tests + PR + merge) | ~45 phút | ~15 phút/PR gồm CI wait + founder review |
| Diagnostic + memory notes + retrospective | ~30 phút | Doc này + memory writes trước đó |
| Strategic thread (rename, decisions) | ~120 phút | Parallel thread, retrospective riêng justified nếu pursue |
| **Total session** | **~4 giờ** | Mixed threads |

### 7.4 Memory artifacts

- `feedback_stacked_pr_squash_cascade.md` — deadlock + cherry-pick pattern (MỚI)
- `feedback_activate_venv_before_commit.md` — pre-commit + venv (MỚI)
- `project_feature_naming_convention.md` — rename convention (MỚI, parallel thread)
- `project_manual_transaction_entry_decisions.md` — 13 decisions manual entry (MỚI, parallel thread)

---

## 8. Cross-references

- **Memory:** `feedback_stacked_pr_squash_cascade`, `feedback_activate_venv_before_commit`, `feedback_concurrency_one_session`, `feedback_autopilot_prompt_template`, `project_dashboard_auto_gen`
- **Autopilot prompt đã chạy:** [`merge-c1-cascade-autopilot.md`](../autopilot/prompts/merge-c1-cascade-autopilot.md) (có bug per §5.1; update per §6.1)
- **Implementation plan:** [`plans/260514-2049-wire-multi-tenant-sepay-pipeline/`](../../plans/260514-2049-wire-multi-tenant-sepay-pipeline/)
- **Retrospective format trước:** [`f07-retrospective.md`](f07-retrospective.md)
- **PRs (GitHub):** #16, #17 (closed), #18 (closed), #19 (closed), #22, #23, #24, #25

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-15 | Initial retro sau khi C1 Phases 1-3 cascade hoàn tất. Document stacked-PR-squash deadlock (§5.1) + recovery qua cherry-pick + 8 issues + 6 lesson categories + metrics + follow-ups. Lưu record đầy đủ cho template update trong §6.1. Bản dịch tiếng Việt của `c1-cascade-retrospective.md`. |
