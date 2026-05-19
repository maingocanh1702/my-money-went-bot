---
title: Linear ↔ Dashboard — Work Tracking Layering
status: Explainer
version: v1.0.1
date: 2026-05-19
author: Founder + Claude
related:
  - docs/operations/dashboard-plan-state-split.md
  - docs/operations/dashboard-realtime-explained.md
  - docs/implementation-tracker.md
  - .github/workflows/pr-validate.yml
---

# Linear ↔ Dashboard — Work Tracking Layering

> **Status:** Explainer · Active
> **Version:** v1.0.1
> **Ngày tạo:** 2026-05-19
> **Cập nhật:** 2026-05-19
> **Mục đích:** Giải thích chi tiết quan hệ giữa Linear (track ở mức task/feature) và MMW dashboard (track ở mức branch/PR/commit/CI/deploy) — đây là 2 view của cùng 1 work item, link qua MMW-NNN ID convention, không phải 2 hệ thống cạnh tranh nhau.

---

## TL;DR

Linear và MMW dashboard tracking **không tách rời** — 2 view của **cùng 1 work item** ở 2 độ granularity khác nhau. Linear nhìn ở mức **semantic intent** (task, AC, discussion, sprint); dashboard nhìn ở mức **artifact reality** (branch, PR, commit, CI run, deploy). Link giữa 2 view = **MMW-NNN Linear ticket ID** xuất hiện ở 3 chỗ enforce bởi convention: branch name (`feat/MMW-NNN-slug`), PR body (`Closes MMW-NNN`), tracker row (`linear_id: MMW-NNN`).

Hiện tại (pre-Phase 3 của `dashboard-plan-state-split.md`), 3 nguồn "status" parallel — Linear status, tracker.md status, dashboard render — có thể drift do tất cả manual. Sau Phase 3, dashboard engine derive status từ artifacts → authoritative; Linear giữ vai trò complementary (planning + discussion + stakeholder), không phải competing source of truth.

---

## 1. Mental model — 1 work item, 2 view

Cốt lõi: **work item** là đơn vị logic duy nhất xuyên suốt cả Linear và dashboard. Mỗi hệ thống render cùng work item đó ở góc độ khác nhau.

```txt
                    WORK ITEM (logical unit)
                    ID anchor: MMW-108
                    Feature: funding-sources
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│ LINEAR / JIRA VIEW       │   │ DASHBOARD VIEW           │
│ semantic, intent          │   │ artifact, reality        │
├──────────────────────────┤   ├──────────────────────────┤
│ Title                    │   │ Branch state             │
│ Description              │   │ Commits count            │
│ Acceptance criteria      │   │ PR state                 │
│ Priority / sprint        │   │ Review state             │
│ Assignee                 │   │ CI state + checks        │
│ Status (manual today)    │   │ Deploy state             │
│ Comments / discussion    │   │ Computed status (derived)│
│ Labels / cycles          │   │ Progress %               │
│ Stakeholder narrative    │   │ Event timeline           │
└──────────────────────────┘   └──────────────────────────┘
            ↑                               ↑
            human-curated                   auto-derived
            slow-changing                   fast-changing
```

**Quy tắc đơn giản**: nếu thông tin trả lời "what/why/who/when do we want this?" → Linear lo. Nếu thông tin trả lời "where is this in artifact reality right now?" → dashboard lo.

---

## 2. Link mechanism — 3 convention enforced

Để 2 view luôn liên kết được, MMW có 3 convention được enforce ở các layer khác nhau:

### 2.1 Branch naming

Convention: `<type>/MMW-<NNN>-<slug>` với type ∈ {feat, fix, chore, refactor, docs, infra, test}.

Examples:
- `feat/MMW-108-funding-sources`
- `fix/MMW-203-webhook-dedup`
- `infra/MMW-602-railway-deploy`

Enforcement: `.github/workflows/pr-validate.yml` regex check — branch nào không match sẽ block PR.

Exempt list hiện tại trong `.github/workflows/pr-validate.yml`: `W0.*`, `Wave-*`, `hotfix/*`, `release/*`, `fix/*`, `feat/c1-*`, `chore/*`.

Note: `fix/*`, `feat/c1-*`, `chore/*` là legacy/security-plan exemptions. New planned work vẫn nên dùng `MMW-NNN` convention để Linear/dashboard link bền.

### 2.2 PR body reference

Convention: PR body phải chứa ít nhất 1 trong các cụm:
- `Closes MMW-NNN`
- `Fixes MMW-NNN`
- `Ref MMW-NNN`
- `Linear: N/A` (exempt cho ad-hoc/hotfix)

Enforcement: cùng `pr-validate.yml` workflow check PR body.

Side effect: Linear's GitHub integration tự detect `Closes/Fixes` → auto-link PR vào ticket, có thể auto-move ticket khi PR merged (nếu Linear workspace config).

### 2.3 Tracker row (after Phase 1 of plan-state-split spec)

Mỗi row trong `docs/implementation-tracker.md` có column `linear_id`:

```markdown
| feature_id | name | linear_id | branches | ... |
|---|---|---|---|---|
| funding-sources | Funding sources resolver | MMW-108 | feat/MMW-108-funding-sources | ... |
```

Enforcement: `plan_reader.py` (proposed) warn nếu row có branch nhưng thiếu linear_id, hoặc ngược lại.

**3 chỗ trên cùng đeo "MMW-108"** → engine biết PR/branch/commit nào thuộc về work item nào. Đây là bộ ba enforce link.

---

## 3. Hierarchy of work units

```txt
┌─────────────────────────────────────────────────────────┐
│ 1 Linear ticket (MMW-108)                                │
│ ─ Title, AC, priority, sprint                            │
│ ─ Discussion thread                                      │
│ ─ Status (Backlog/Todo/In Progress/Done)                 │
└───────────────────────────┬─────────────────────────────┘
                            │  1:N (multi-PR features hay 1:1)
                            ▼
┌─────────────────────────────────────────────────────────┐
│ 1+ Git branches                                          │
│ ─ Naming: feat/MMW-108-funding-sources                   │
│ ─ Tracked by tracker.md branches[] field                 │
│ ─ Local + remote (origin)                                │
└───────────────────────────┬─────────────────────────────┘
                            │  1:1 typically
                            ▼
┌─────────────────────────────────────────────────────────┐
│ 1+ GitHub Pull Requests                                  │
│ ─ State: draft / open / merged / closed                  │
│ ─ Reviews: pending / approved / changes-requested        │
│ ─ Body: "Closes MMW-108" reference                       │
└───────────────────────────┬─────────────────────────────┘
                            │  1:N
                            ▼
┌─────────────────────────────────────────────────────────┐
│ N Commits (per PR)                                       │
│ ─ Conventional Commit message                            │
│ ─ Each triggers CI workflow run                          │
└───────────────────────────┬─────────────────────────────┘
                            │  1:M (multi-workflow)
                            ▼
┌─────────────────────────────────────────────────────────┐
│ CI runs + Check suites + Deploy events                   │
│ ─ Required checks: test, pre-commit, import-linter       │
│ ─ Railway deploy after merge to main                     │
└─────────────────────────────────────────────────────────┘
```

**Dashboard engine "roll up"** signals từ artifact level (commit/CI/deploy) lên work-item level. Roll-up rule:
- Single-branch feature: status = compute_status(signals)
- Multi-branch feature: status = MIN-progressed branch state (per `plan-state-split.md` §4.1)

**Linear UI** cũng "roll up" — tab "Issue links" trong ticket detail hiển thị tất cả PR linked, nhưng aggregate-level status vẫn manual move cột.

---

## 4. Current state (pre-Phase 3) — 3 parallel status sources

Trước khi `dashboard-plan-state-split.md` migrate xong, có **3 nguồn status độc lập**, tất cả manual, có thể drift:

```txt
┌────────────────────────────────────────────────────┐
│ Source 1: LINEAR STATUS                             │
│ Storage: Linear cloud                                │
│ Updated by: founder bấm column trên Linear UI       │
│ Granularity: per Linear ticket                       │
│ Drift risk: cao — không sync với code state         │
└────────────────────────────────────────────────────┘
                    ❌ no sync ❌
┌────────────────────────────────────────────────────┐
│ Source 2: TRACKER.MD STATUS                          │
│ Storage: docs/implementation-tracker.md              │
│ Updated by: founder edit emoji (⬜ 🔄 ✅ ⏸️ 🚫)       │
│ Granularity: per work item row                       │
│ Drift risk: cao — không sync với code state         │
└────────────────────────────────────────────────────┘
                    ❌ no sync ❌
┌────────────────────────────────────────────────────┐
│ Source 3: DASHBOARD RENDER                           │
│ Storage: docs/dashboard.{html,md,json}               │
│ Updated by: build script đọc tracker.md             │
│ Granularity: per work item                           │
│ Drift risk: thừa hưởng từ tracker.md                │
└────────────────────────────────────────────────────┘
```

Hệ quả thực tế: PR `feat/MMW-108-funding-sources` merged 2 ngày trước, nhưng:
- Linear ticket vẫn ở column "In Progress"
- tracker.md row vẫn `🔄 In progress`
- Dashboard vẫn render "In progress" badge

3 nguồn đều sai. Đây là **P1-P3** mà spec `plan-state-split.md` đang giải quyết.

---

## 5. Future state (post-Phase 3) — derived authoritative

Sau khi spec migrate xong:

```txt
                ┌──────────────────────────────────┐
                │  ARTIFACTS (Git + GitHub + Railway)│
                │  - Branch + commits               │
                │  - PR state + reviews             │
                │  - CI check runs                  │
                │  - Deploy events                  │
                └────────────────┬─────────────────┘
                                 │ collect signals
                                 ▼
                ┌──────────────────────────────────┐
                │  DASHBOARD ENGINE                  │
                │  - Signal collectors              │
                │  - Event log (events.jsonl)       │
                │  - Status state machine           │
                │  - Progress model                 │
                │                                    │
                │  ⭐ AUTHORITATIVE STATUS           │
                └────────────────┬─────────────────┘
                                 │ projection
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
┌──────────────────────┐ ┌──────────────────┐ ┌────────────────────┐
│ Dashboard view       │ │ tracker.md       │ │ Linear sync         │
│ (primary)            │ │ (plan source)    │ │ (Phase 4 deferred) │
│                      │ │                  │ │                    │
│ Auto status badge    │ │ Plan fields only │ │ Optional 1-way     │
│ Signal drilldown     │ │ (no status col)  │ │ engine → Linear    │
│ Progress %           │ │ priority, AC,    │ │ via API            │
│ Event timeline       │ │ owner, deadline  │ │                    │
└──────────────────────┘ └──────────────────┘ └────────────────────┘
```

Sau Phase 3:
- **tracker.md** = plan source (priority, lane, AC, owner, deadline, dependencies). **Không có** status column.
- **Engine** = derive status từ artifact, authoritative cho dashboard.
- **Linear** = vẫn dùng cho discussion/planning, **không sync** với engine ở Phase 3. Có thể sync 1 chiều ở Phase 4.

Manual status drift giữa dashboard và artifact reality được loại bỏ vì dashboard derive từ artifacts. Artifact mapping drift vẫn có thể xảy ra (branch sai, PR cache stale, GitHub/Railway unknown) và phải được surfaced bằng warnings/unknown overlays. Drift giữa Linear ticket status và artifact reality vẫn có thể xảy ra, nhưng:
- Linear's own GitHub integration có thể auto-move ticket khi PR merged (nếu config trong Linear workspace)
- Hoặc founder manually move — vì Linear không phải authoritative cho MMW, drift không break anything

---

## 6. Role separation — what each tool does best

| Concern | Best tool | Reason |
|---------|-----------|--------|
| Sprint/cycle planning | Linear | Native cycle view, velocity tracking, burndown |
| Stakeholder visibility | Linear | Share viewer permission, mobile app, non-tech UI |
| Discussion per task | Linear | Comments, @mentions, decision log, attachments |
| Acceptance criteria | Linear ticket + spec doc | Linear has structure; spec doc has detail |
| Realtime artifact status | Dashboard | Auto-derive from Git/GitHub/CI |
| Cross-feature progress overview | Dashboard | 1 page shows 20+ features with computed % |
| Event timeline (when did X change?) | Dashboard (events.jsonl) | Append-only history with timestamps |
| Code-level drilldown (which commits?) | Dashboard | Direct git enrich |
| Notification routing | Linear | Email/Slack on assignee change, status change |
| External integrations (Figma, etc.) | Linear | Linear-native integrations marketplace |
| Plan source of truth | tracker.md (now) → Linear (Phase 4 optional) | Founder owns plan fields |
| Status source of truth | Engine (derived) | Manual status creates drift; engine fixes it |

**Quy tắc nhanh**: Linear cho "what + why + who"; dashboard cho "where + when".

---

## 7. End-to-end walkthrough — 1 feature đi qua cả 2 hệ thống

Ví dụ feature `funding-sources` đi từ idea tới deployed.

### Step 1 — Planning (Linear, manual)

Founder mở Linear, create ticket:
- Title: "Funding sources resolver + handlers"
- Description: "Resolve TK/thẻ/ví entity before any transaction INSERT"
- Priority: P1
- Cycle: Phase 2
- Assignee: founder
- Acceptance criteria:
  - FS resolved before any transaction INSERT
  - Tenant isolation tests pass

Linear auto-assign ID: **MMW-108**. Ticket vào column "Backlog".

### Step 2 — Spec writing (tracker + spec docs, manual)

Founder edit `docs/implementation-tracker.md` thêm row:

```markdown
| funding-sources | Funding sources resolver | MMW-108 | feat/MMW-108-funding-sources | P1 | Foundation | docs/features/feature-funding-sources.md | docs/features/BE/feature-funding-sources-tech.md |
```

Founder viết FE spec (`docs/features/feature-funding-sources.md`) + BE tech spec (`docs/features/BE/feature-funding-sources-tech.md`).

Sau Phase 1 của work-state engine, dashboard engine detect 2 spec file existence → emit events:
```
spec_created → state: not-started → spec-only
tech_created → state: spec-only → tech-ready
```

Linear ticket vẫn ở "Backlog" — founder chưa move (hoặc Linear's GitHub integration chưa fire vì branch chưa có).

### Step 3 — Branch creation (Git, manual command)

Founder chạy `git worktree add ../MyMoneyWent-funding feat/MMW-108-funding-sources -b`. Engine detect branch_created → emit event:
```
branch_created → state: tech-ready → in-progress
```

Linear: tùy config — nếu Linear's GitHub integration thấy branch khớp `MMW-108`, có thể auto-move ticket sang "In Progress". Hoặc founder bấm tay.

### Step 4 — Code + commit (Git, founder)

Founder code trong worktree, commit nhiều mốc:
- `feat(funding-sources): add FundingSource model`
- `feat(funding-sources): add resolver service`
- `test(funding-sources): tenant isolation tests`

Mỗi commit:
- Pre-commit hook chạy local
- Push lên GitHub
- Engine collect signals: branch_exists=true, commits_count=3, last_commit_sha=abc123

State machine: vẫn `in-progress` (chưa có PR).

### Step 5 — PR open (GitHub, founder)

Founder mở PR via `gh pr create` hoặc UI. PR body chứa "Closes MMW-108".

GitHub events:
- `pull_request` event (opened)
- `workflow_run` event (CI starts)

Engine:
- `pr_opened` → state: in-progress → in-review
- `ci_running` → overlay: ci-running
- CI pass → `ci_passed` → overlay: removed
- CI fail (nếu fail) → `ci_failed` → overlay: ci-failing

Linear: integration tự link PR #42 vào ticket MMW-108. Có thể auto-move sang "In Review" tùy config.

### Step 6 — Review iteration (GitHub, Codex)

Codex review, leave comments, request changes.

Engine event:
- `changes_requested` → state: in-review → changes-requested

Founder push fix commits → CI re-run → review re-submit → approval.

Engine event:
- `approved` → state: changes-requested → approved-pending-merge

Linear: ticket vẫn "In Review" hoặc move sang "Ready to merge" tùy config.

### Step 7 — Merge (GitHub, founder bấm squash-merge)

GitHub event:
- `pull_request closed (merged=true)`

Engine:
- `merged` → state: approved-pending-merge → merged

Linear's GitHub integration: thấy "Closes MMW-108" + PR merged → auto-move ticket sang "Done" (nếu config). Hoặc founder manual.

### Step 8 — Deploy (Railway, auto)

Railway webhook fires sau push lên main. Build container, deploy.

Engine:
- `deploy_started` → state: merged → deploying
- `deploy_succeeded` → state: deploying → deployed (Phase 1 có thể là `unknown` nếu Railway API chưa wired)

Linear: typically không có deploy state — workflow stops at "Done".

### Step 9 — Cleanup (Git, founder)

`git worktree remove ../MyMoneyWent-funding`. Branch deleted on remote sau merge.

Engine PR identity resolution (per spec §6.3):
- Branch không còn → bước 1 cached `github_pr` resolve.
- Cache hits PR #42 → engine vẫn track state = `deployed`, không lose history.

Linear: ticket "Done" sau khi sprint complete.

---

## 8. Edge cases & drift scenarios

### 8.1 Linear ticket không có branch tương ứng

**Trigger**: ticket "Backlog" hoặc "Todo", chưa start code.

**Dashboard view**: status = `not-started` hoặc `spec-only` (nếu có spec doc).

**Linear view**: "Backlog" hoặc "Todo".

**Drift?** Không — cả 2 đồng ý "chưa start". Mỗi bên render dưới ngữ cảnh riêng.

---

### 8.2 Code trên branch chưa có Linear ticket

**Trigger**: founder muốn hotfix nhanh, chưa kịp create Linear ticket.

**Block**: `pr-validate.yml` reject vì branch không match `MMW-NNN` regex.

**Workaround**: 
- Option A: create Linear ticket trước rồi mới mở PR.
- Option B: dùng exempt prefix `hotfix/*` (đã có trong pr-validate exempt list).
- Option C: PR body ghi `Linear: N/A` (acceptable cho 1-line fix khẩn cấp).

**Dashboard**: nếu exempt prefix dùng → branch không match feature_id nào trong tracker → engine warn `artifact-drift` (work item nào sở hữu branch này?). Founder cần add row vào tracker hoặc accept drift cho 1 lần.

---

### 8.3 Linear ticket bị closed (cancelled) nhưng PR vẫn open

**Trigger**: founder change mind, cancel Linear ticket, quên close PR.

**Linear view**: Cancelled.

**Dashboard view**: PR state = open → status = `in-review`.

**Drift**: thật. Engine không tự resolve được vì Linear API không phải signal mặc định.

**Resolution options**:
- Founder close PR thủ công → engine sees `closed → abandoned`.
- Hoặc set `manual_state_override: status=abandoned, until=<date>, reason=linear-cancelled` trong tracker row.
- Phase 4 spec có thể add Linear signal collector để auto-detect Linear cancellation, fire `linear_cancelled` event.

---

### 8.4 1 Linear ticket → 2 PR (multi-branch feature)

**Trigger**: feature lớn split thành additive PR + cutover PR (vd transaction-capture).

**Tracker row**:
```yaml
linear_id: MMW-120
branches:
  - feat/MMW-120-transaction-capture-additive
  - feat/MMW-121-transaction-capture-cutover
```

**Dashboard view**: MIN-progressed rule — work item status = trạng thái của branch chậm nhất. Overlay `partial-progress` nếu một branch đã merged còn branch khác chưa.

**Linear view**: 1 ticket linked với 2 PR. UI thường hiển thị cả 2 PR trong tab "Issue links". Status của ticket vẫn 1 — founder bấm move khi cả 2 PR done.

**Drift**: minimal nếu founder consistent về meaning "Done" trong Linear = "both PRs merged".

---

### 8.5 Branch deleted sau merge, nhưng dashboard cần track

**Trigger**: founder cleanup branch sau merge (best practice).

**Dashboard**: cached `github_pr` trong `.dashboard/state-cache.json` resolve PR by number → vẫn track được state `merged` / `deployed`. Per spec §6.3 PR identity resolution.

**Linear**: PR linked qua integration vẫn còn reference, không bị mất.

---

## 9. Phase 4 future — Linear sync direction options

Spec `plan-state-split.md` defer Linear sync sang Phase 4. 3 option đang open:

### Option A — Linear thành plan source (replace tracker.md)

```txt
Linear (plan source)
    │ API pull
    ▼
plan_reader.py (proposed)
    │ normalize to WorkItem
    ▼
Engine derive state from artifacts
    │
    ▼
Dashboard projection
```

**Pros**:
- Founder edit plan trên Linear UI (richer than markdown)
- Stakeholder thấy plan cùng chỗ với discussion
- Mobile-friendly

**Cons**:
- Cần Linear API rate budget + reliability
- Linear outage = engine không build được
- Vendor lock-in

**Khi nào activate**: team grow ≥ 2 engineer + cần share plan với non-tech.

---

### Option B — Linear là projection (engine push to Linear)

```txt
tracker.md (plan source, unchanged)
    │
    ▼
Engine derive state
    │ derived status
    ▼
Linear API update ticket status (1-way)
```

**Pros**:
- Plan vẫn ở repo (version-controlled)
- Linear ticket status tự update theo artifact reality → Linear không còn drift
- Stakeholder thấy "real" status, không phải "founder forgot to update"

**Cons**:
- Cần Linear API write permission
- Risk: API write loop nếu Linear's own GitHub integration cũng fire
- Engine phải handle Linear-side rate limit

**Khi nào activate**: founder muốn Linear ticket status reflect artifact reality cho stakeholder, không cần Linear thành plan source.

---

### Option C — Hoàn toàn parallel (status quo, no sync)

```txt
tracker.md (plan source)            Linear (independent)
    │                                   │
    ▼                                   ▼
Engine derive state                 Manual or Linear's GitHub integration
    │                                   │
    ▼                                   ▼
Dashboard (authoritative)           Linear UI (best-effort)
```

**Pros**:
- Đơn giản nhất — không cần sync code
- Mỗi hệ thống có thể fail độc lập

**Cons**:
- Linear status có thể drift khỏi artifact reality
- Founder + stakeholder phải biết: trust dashboard, Linear là supplementary

**Khi nào activate**: solo founder phase, Linear chỉ để stakeholder + sprint planning, dashboard là source of truth chính.

---

**Recommendation cho MMW hiện tại**: **Option C** (parallel). Vì solo founder, Linear chỉ phục vụ planning + đáp ứng requirement của `pr-validate.yml` (cần MMW-NNN reference). Dashboard authoritative cho realtime status.

**Khi hire engineer thứ 2**: re-evaluate Option B trước Option A. Option B chi phí thấp (1-way sync), giải quyết "Linear status reflects reality" cho team visibility, không lock plan source vào Linear.

---

## 10. Decision guide — when to use which tool

### "Cần xem status hiện tại của feature X"
→ **Dashboard**. Authoritative source.

### "Cần plan feature mới — write AC, set priority"
→ **Linear** (ticket) + **spec doc** (chi tiết AC). Tracker.md row link cả 2.

### "Cần discuss vấn đề kỹ thuật của 1 task"
→ **Linear ticket comments**. Discussion thread per task.

### "Cần xem sprint progress / velocity"
→ **Linear** (cycle view native). Dashboard có phase progress nhưng không có velocity.

### "Cần biết ai assigned cho task"
→ **Linear** (assignee field).

### "Cần biết CI có pass cho PR này không"
→ **Dashboard** (CI signal). Hoặc GitHub PR page direct.

### "Cần xem history: status thay đổi khi nào và vì sao?"
→ **Dashboard events.jsonl** (post-Phase 1 spec). Linear có activity log nhưng chỉ ticket-level, không có artifact event detail.

### "Cần share progress cho stakeholder không có GitHub access"
→ **Linear** (viewer permission). Hoặc dashboard live URL (`/dashboard`) cho realtime view.

### "Cần block PR merge cho tới khi review xong"
→ **GitHub** (branch protection rules). Linear không enforce this.

### "Cần edit tracker plan / re-prioritize"
→ **tracker.md** edit (Phase 3). Sau này có thể Linear (Phase 4 Option A).

---

## 11. Common confusion clarified

### "Linear ticket Done = feature deployed?"

**Không nhất thiết.** Linear's "Done" thường = PR merged (qua integration auto-move). Nhưng "merged" ≠ "deployed":
- PR merged vào main → deploy chạy sau ~1-2 phút trên Railway
- Deploy có thể fail → main có code nhưng prod không có
- Dashboard phân biệt `merged` vs `deployed` rõ ràng; Linear gộp thành "Done"

**Source of truth cho "đã ra prod"**: dashboard's `deployed` state (sau khi Phase 1 wire Railway signal).

---

### "Tracker.md là cache của Linear?"

**Không.** Tracker.md là **plan source độc lập**, không pull từ Linear. Founder maintain song song — set `linear_id` trong row để link, nhưng plan fields (priority, AC summary, owner) là tracker-native, không sync từ Linear.

Sau Phase 4 Option A (deferred): tracker.md có thể trở thành auto-generated cache từ Linear. Hiện tại không.

---

### "Dashboard có thể replace Linear không?"

**Không cho team scale.** Dashboard mạnh ở artifact view + cross-feature overview. Linear mạnh ở discussion + sprint + stakeholder + mobile + notifications. 2 cái phục vụ use case khác nhau.

Solo founder có thể tạm bỏ Linear (chỉ giữ tracker.md), nhưng `pr-validate.yml` đang require MMW-NNN reference — phải hoặc giữ Linear, hoặc disable check đó.

---

### "Sao không bỏ Linear, chỉ dùng GitHub Issues + dashboard?"

Cân nhắc valid. GitHub Issues miễn phí, native với code. Trade-off:
- **Pros bỏ Linear**: 1 ít tool, GitHub Issues link branch/PR native
- **Cons bỏ Linear**: GitHub Issues UI yếu cho sprint planning, không có cycle view native, mobile app yếu hơn

Founder decision call. Memory chưa lock decision này — open question cho roadmap review.

---

## 12. References

- **Spec đang propose engine** — `docs/operations/dashboard-plan-state-split.md`
- **Current dashboard infra** — `docs/operations/dashboard-realtime-explained.md`
- **Branch + PR convention enforcement** — `.github/workflows/pr-validate.yml`
- **Plan source schema** — `docs/implementation-tracker.md`
- **MMW-NNN convention origin** — `CLAUDE.md` § "Git & commit policy"

---

## Changelog

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| v1.0.1 | 2026-05-19 | Founder + Claude | Hardening pass: aligned branch examples/exemptions with `pr-validate.yml`, softened drift claim to account for artifact mapping drift, and clarified Phase 1 wording. |
| v1.0.0 | 2026-05-19 | Founder + Claude | Initial explainer. Describes Linear ↔ dashboard layering, link mechanism, hierarchy, current vs future state, role separation, end-to-end walkthrough, edge cases, Phase 4 sync options, decision guide. |
