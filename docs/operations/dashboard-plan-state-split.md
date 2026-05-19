---
title: Dashboard Plan/State Split — Auto-Progress Work Engine Design
status: Proposed
version: v1.2.0
date: 2026-05-19
updated: 2026-05-19
author: Founder + Claude
related:
  - docs/operations/dashboard-realtime-explained.md
  - docs/implementation-tracker.md
  - scripts/build-dashboard.py
  - .github/workflows/dashboard.yml
---

# Dashboard Plan/State Split — Auto-Progress Work Engine Design

> **Status:** Proposed · Awaiting cross-model review (Codex) + founder approval
> **Version:** v1.2.0
> **Ngày tạo:** 2026-05-19
> **Cập nhật:** 2026-05-19
> **Mục đích:** Tách plan/state để xây foundation cho một **Linear/Jira-like work tracker có progress tự update từ trigger/artifact**, không chỉ sửa dashboard. Dashboard là projection đầu tiên; core asset là work-item schema + signal collectors + event engine + progress model — tạo ra **artifact-derived authoritative state**.

---

## TL;DR

Tracker hiện đang đóng cùng lúc 2 vai trò: **plan** (intent) và **state** (reality). Đây là root cause của 3 vấn đề: founder phải manual update status sau merge/review/deploy, dashboard timestamp dễ gây hiểu nhầm stale, và status không phản ánh PR/CI/deploy state realtime.

Giải pháp không phải “đổi sang Linear/Jira” và cũng không chỉ là “dashboard cleanup”. Giải pháp đúng là xây **auto-progress work engine**:

```txt
Plan Source
  tracker.md / work-items.yml / Linear later
        ↓
Normalizer
  WorkItem{id,type,lane,priority,specs,branches,AC,deps}
        ↓
Signal Collectors
  filesystem / git / GitHub PR / GitHub Checks / Railway
        ↓
Event Engine
  trigger → event → transition
        ↓
State Store
  current_state.json + events.jsonl
        ↓
Projections
  dashboard.html / dashboard.json / kanban board / weekly review / Linear sync
```

Sau migration, founder **không edit status/progress bằng tay nữa**. Manual fields vẫn tồn tại cho planning: priority, lane, owner, deadline, dependencies, decision_needed, external_blockers, acceptance criteria. Auto fields được derive: status, progress %, PR state, review state, CI state, deploy state, staleness, activity, runtime urgency.

Core thesis: **humans define intent; engine derives reality**. State trở thành **artifact-derived authoritative state** — authoritative vì nó được derive từ Git/GitHub/CI/deploy artifacts, không vì một người kéo status column.

Important nuance: **manual status drift is eliminated by design**, nhưng artifact mapping drift vẫn có thể xảy ra và phải được surfaced bằng warnings (`missing_spec`, `branch_not_found`, `unknown_pr`, `stale-cache`). Không tuyên bố “drift impossible” tuyệt đối.

---

## 0. Product intent — why this is bigger than dashboard

Mục tiêu dài hạn là build một hệ thống giống Linear/Jira ở phần semantic công việc, nhưng tốt hơn ở một điểm cốt lõi: **progress tự cập nhật từ artifact thật** thay vì con người kéo status column.

Dashboard hiện tại chỉ là projection đầu tiên. Engine này sau đó có thể phục vụ:

- `docs/dashboard.html` — public/internal status view
- `docs/dashboard.json` — machine-readable API
- CLI: `python -m scripts.work_state status`
- Discord/Telegram daily digest
- Founder weekly review
- Kanban/Linear-like board UI
- Release notes generator
- Optional Linear sync khi scale team

> **Scope clarification:** Tất cả projection ngoài `dashboard.html`/`dashboard.json` đều **deferred post-Phase 3**. Phase 1-3 scope chỉ ship engine + dashboard projection (per NG2). Danh sách trên định nghĩa **future projection surface** của engine, không phải v1 deliverables.

Design constraint: không nhét state logic vào HTML/dashboard-specific glue. Core engine phải tách riêng để các projection dùng chung.

Recommended module boundary:

```txt
scripts/work_state/
  models.py                 # WorkItem, Signals, Events, CurrentState
  plan_reader.py            # tracker.md reader now, work-items.yml/Linear later
  signal_collectors/
    filesystem.py
    git.py
    github.py
    ci.py
    railway.py
  event_engine.py           # signal diff → events → transitions
  status_machine.py
  progress.py
  state_store.py            # current_state.json + events.jsonl
  projections/
    dashboard.py            # build-dashboard.py calls this
```

`build-dashboard.py` becomes orchestration/projection code, not the owner of truth.

---

## 0.1 Intent vs Reality

### Intent layer — what humans want to happen

Managed by Linear, tracker/spec docs, and founder decisions. Examples:

- roadmap placement
- business priority
- risk tier / lane
- acceptance criteria
- owner / deadline
- sprint/cycle planning
- dependencies and external blockers

### Reality layer — what engineering artifacts prove happened

Managed by Git, GitHub, CI, Railway/deploy signals, and the work-state engine. Examples:

- spec file exists
- branch exists
- commits pushed
- PR opened
- review state changed
- CI passed/failed
- deploy succeeded/failed

Rule: humans define **intent**; engine derives **reality**. Manual drag-and-drop can annotate planning, but cannot be source of truth for execution state.

---

## 1. Problem statement

### 1.1 Hiện trạng

Dashboard hiện tại render từ `docs/implementation-tracker.md`. Mỗi row có `(Phase, PR/Feature ID, Name, Status emoji, Branch, Gates, Notes)`. Build script parse markdown, enrich bằng một phần git state, rồi render HTML/MD/JSON.

Status field hiện là **manual** — founder edit emoji `⬜ ✅ 🔄 ⏸️ 🚫` khi đổi trạng thái. Build script chưa derive lifecycle state từ GitHub/CI/deploy artifacts.

### 1.2 3 vấn đề quan sát được

**P1 — Manual update friction giống Jira/Linear, không có lợi ích bù lại.**

- Founder phải nhớ edit tracker sau merge PR, sau push, sau review.
- Không có notification/collab UX đủ mạnh để bù cho manual status update.
- Single founder đang code/review/deploy → status update bị skip là normal failure mode.

**P2 — Manual status drift không detect đủ.**

- Auto-generated dashboard surface stale tracker values nhanh hơn đọc bằng mắt.
- Nhưng nếu PR đã merge 2 ngày còn tracker vẫn `🔄 In progress`, build script không biết nếu không query GitHub.
- Drift này không phải lỗi con người; là lỗi source-of-truth boundary.

**P3 — Dashboard timestamp confusion.**

- Nếu cron rebuild thành công nhưng output không đổi, file timestamp có thể nhìn stale.
- User không phân biệt được “system healthy + no work changed” vs “system failed + dashboard stale”.

### 1.3 Tại sao Linear/Jira không phải answer — nhưng là product inspiration

Linear/Jira tốt ở work item semantics, collaboration, board, notification. Nhưng nếu status vẫn kéo tay, nó không giải quyết P1-P3.

MMW direction:

```txt
Keep Linear/Jira semantics.
Reject manual status as source of truth.
Derive progress from artifacts/events.
```

Linear có thể trở thành plan source hoặc projection sau này. Không phải dependency cho v1.

---

## 2. Goals & non-goals

### Goals

- **G1** — Tách manual plan fields khỏi derived state fields.
- **G2** — Xây canonical `WorkItem` model có đủ semantic để sau này render Linear/Jira-like views.
- **G3** — Xây signal collectors cho filesystem, git, GitHub PR, GitHub Checks, Railway/deploy.
- **G4** — Xây event log (`events.jsonl`) để biết state đổi khi nào/vì sao, không chỉ current snapshot.
- **G5** — Xây progress model theo work type/profile, không chỉ categorical status.
- **G6** — Dashboard render state/progress từ engine, không tự compute business logic trong HTML.
- **G7** — Migration shadow mode trước cutover: manual status và computed status chạy song song.
- **G8** — Giữ live polling JS + defense-in-depth của dashboard hiện tại.

### Non-goals

- **NG1** — Không migrate plan source sang Linear trong phase này.
- **NG2** — Không build full kanban/Linear UI trong phase này. Dashboard là projection đầu tiên.
- **NG3** — Không sync Linear ↔ tracker 2 chiều.
- **NG4** — Không yêu cầu Railway API chính xác ngay Phase 1. Deploy signal được phép `unknown`/heuristic cho tới khi API verified.
- **NG5** — Không loại bỏ mọi manual metadata. Chỉ loại bỏ manual **status/progress** as truth.

---

## 3. Manual vs derived field boundary

| Field | Type | Source of truth | Notes |
|---|---|---|---|
| `id` | manual | plan source | Stable internal identity (e.g. `MMW-108`, `W0.9`, kebab feature_id fallback). Must not change casually. |
| `linear_id` | manual, optional | plan source | MMW Linear ticket reference (e.g. `MMW-108`). May be `None` cho legacy Wave rows (`W0.9`) hoặc ad-hoc work. `plan_reader` warn nếu row có `branches` + active PR nhưng thiếu `linear_id` — required cho Linear integration linkage. |
| `feature_id` | manual | plan source | Kebab-case canonical feature key (e.g. `funding-sources`). Used khi `id` == `linear_id` thì `feature_id` là human-readable companion. |
| `title` | manual | plan source | Human-readable |
| `type` | manual | plan source | `feature`, `bugfix`, `docs`, `infra`, `research`, `dashboard`, `ops` |
| `phase` | manual | plan source | Roadmap placement |
| `priority` | manual | plan source | Roadmap/business priority; not same as risk tier |
| `risk_tier` | manual/inferred | plan source + workflow policy | P0/P1/P2 process risk; may be inferred from lane/type if absent |
| `lane` | manual | plan source | Fast/Standard/Foundation |
| `owner` | manual | plan source | Founder now; team later |
| `deadline` | manual | plan source | Optional |
| `dependencies` | manual | plan source | Work item IDs |
| `decision_needed` | manual | plan source | Manual planning context |
| `external_blockers` | manual | plan source | E.g. “waiting for bank email samples” |
| `acceptance` | manual | plan source | Short AC summary; full AC in spec docs |
| `specs` | manual path, derived existence | plan + filesystem | Plan stores link; state checks file |
| `branches` | manual expected, derived existence | plan + git | Supports one or many branches |
| `github_pr` | cached/derived, optional manual | GitHub + state cache | Needed when branch deleted after merge |
| `status` | derived | event/state engine | Never edited manually after Phase 3 |
| `progress` | derived | progress model | Weighted by work type/profile |
| `review_state` | derived | GitHub PR reviews/checks | Unknown-safe |
| `ci_state` | derived | GitHub Checks/Actions | Required workflows only |
| `deploy_state` | derived/unknown-safe | Railway/git deploy source | Phase 1 may be heuristic |
| `staleness` | derived overlay | event engine | PR age/no activity |
| `runtime_urgency` | derived | urgency model | Operational attention: normal/warning/elevated/critical |
| `activity` | derived | events log | Last event timestamp/source |
| `manual_state_override` | manual escape hatch | plan source | Rare, expiry required, surfaced clearly |

Principle: plan fields explain **what/why/priority/context**. Derived fields explain **where reality is now**.

Important distinction:

```txt
priority  = roadmap/business importance
risk_tier = process/safety strictness (P0/P1/P2)
lane      = workflow lane (Fast/Standard/Foundation)
```

Do not collapse priority into risk tier. A low-business-priority ops change can still be P0/Foundation if it touches source-of-truth, CI, deploy, security, or auto-merge policy. If `risk_tier` is absent in v1 tracker rows, infer from `lane` + `type`, but surface `risk_tier_inferred` so the founder can make it explicit later.

---

## 4. Work item schema

Tracker markdown remains acceptable as v1 plan source, but engine normalizes every row into a canonical model.

Target normalized shape:

```yaml
id: MMW-108              # stable internal identity
linear_id: MMW-108       # Linear ticket reference (often == id, but distinct field)
feature_id: funding-sources
title: Funding sources resolver + handlers
type: feature
phase: 2
priority: P1
risk_tier: P1
lane: Foundation
owner: founder
specs:
  product: docs/features/feature-funding-sources.md
  tech: docs/features/BE/feature-funding-sources-tech.md
branches:
  - feat/MMW-108-funding-sources
github_pr: null
acceptance:
  - FS resolved before any transaction INSERT
  - tenant isolation tests pass
dependencies:
  - W0.2
external_blockers: []
decision_needed: null
manual_state_override: null
progress_profile: standard_feature
```

Legacy/ad-hoc work item example (linear_id None):

```yaml
id: W0.9                 # internal ID, không match MMW-NNN pattern
linear_id: null          # no Linear ticket — legacy Wave work
feature_id: dashboard-realtime
title: Dashboard realtime — auto-rebuild + git-state detect + reconcile
type: infra
phase: 1
priority: P1
risk_tier: P1
lane: Standard
owner: founder
# ... rest same as above
```

### 4.1 Multiple branches / multi-PR features

Some work items have multiple PRs (e.g. transaction capture split into F02a/F02b/F02-dedup). Plan source must support:

```yaml
branches:
  - feat/MMW-120-transaction-capture-additive
  - feat/MMW-121-transaction-capture-cutover
```

Aggregation rule v1:

- Work item base status = **MIN-progressed** non-abandoned branch state per status rank below.
- Progress = weighted average of branch progress.
- Overlays = **union** of all per-branch overlays (no deduplication of severity).
- **Strong recommendation**: split thành separate work items khi branches **independently mergeable**. Aggregate CHỈ khi branches truly coupled (vd additive + cutover pair phải ship cùng release để không break legacy path).

#### 4.1.1 Status rank lattice

Lower rank = less progressed. MIN aggregation = pick branch với lowest rank:

```txt
0  not-started
1  spec-only
2  tech-ready
3  branch-created
4  in-progress
5  in-review
6  changes-requested
7  approved-pending-merge
8  merged
9  deploying
10 deployed
```

Note: `abandoned` excluded from MIN aggregation (per "non-abandoned" qualifier). If all branches abandoned → work item status = `abandoned`. If mix abandoned + non-abandoned → ignore abandoned branches.

#### 4.1.2 Overlay union rule

Overlay set = union of all branch overlays. Examples:

| Branch A | Branch B | Aggregate base | Aggregate overlays |
|---|---|---|---|
| `deployed` | `in-review` + `ci-failing` | `in-review` (MIN) | `ci-failing` + `partial-progress` |
| `merged` | `changes-requested` | `changes-requested` (MIN) | `partial-progress` |
| `deployed` | `merged` + `deploy-failed` | `merged` (MIN, treat deploy-failed branch as not yet `deployed`) | `deploy-failed` + `partial-progress` |
| `blocked` + `in-progress` | `merged` | `in-progress` (MIN; blocked is overlay, base is `in-progress`) | `blocked` + `partial-progress` |
| `deployed` | `deployed` | `deployed` | (none — no partial) |

`partial-progress` overlay added bất cứ khi nào không phải tất cả branch ở cùng terminal state (`deployed`/`merged`/`abandoned`).

#### 4.1.3 runtime_urgency interaction

Urgency aggregation = MAX (most severe) across branches. See §9.4 derivation algorithm.

Example: branch A `deployed` (urgency `normal`) + branch B `in-review` với `ci-failing` (urgency `elevated`) → work item urgency = `elevated`.

---

## 5. Proposed architecture

### 5.1 Layers

```txt
┌────────────────────────────────────────────────────────────────────┐
│ PLAN LAYER — Intent (manual, slow-changing)                         │
│ Source: docs/implementation-tracker.md now; work-items.yml later     │
│ Contains: work identity, type, phase, priority, specs, branches, AC  │
│ Does NOT contain: status/progress as source of truth                 │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ normalize
┌────────────────────────────────────────────────────────────────────┐
│ WORK ITEM MODEL                                                     │
│ WorkItem{id,type,lane,priority,specs,branches,AC,deps,blockers}     │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ collect signals
┌────────────────────────────────────────────────────────────────────┐
│ SIGNAL LAYER — Artifact reality                                     │
│ filesystem + git + GitHub PR + GitHub Checks + Railway              │
│ Unknown-safe: API failure produces unknown, not crash/false truth    │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ diff signals
┌────────────────────────────────────────────────────────────────────┐
│ EVENT ENGINE                                                        │
│ signal change → event → transition                                  │
│ Writes events.jsonl and current_state.json                          │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ project
┌────────────────────────────────────────────────────────────────────┐
│ PROJECTIONS                                                         │
│ dashboard.html/json, kanban later, weekly review, Linear sync later │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 Source-of-truth boundary

| Concern | Source of truth | Rationale |
|---|---|---|
| Work exists / planned | plan source | Founder decides what to build |
| Priority / phase / lane | plan source | Strategic decision |
| Acceptance criteria | plan source + spec docs | Intent |
| Spec done | filesystem | Artifact exists or not |
| Tech spec done | filesystem | Artifact exists or not |
| Branch exists | git remote | Artifact reality |
| Code committed | git log | Artifact reality |
| PR state | GitHub PR | Review system |
| Review state | GitHub PR reviews | Review system |
| CI state | GitHub Checks/required workflows | CI system |
| Deploy state | Railway/API/git deploy source | Deploy target; unknown-safe |
| Current status | state engine | Artifact-derived authoritative state from signals/events |
| Progress % | progress model | Function of status + work type |
| Runtime urgency | urgency model | Function of overlays, failure severity, priority/risk context |

Manual status drift is eliminated. Artifact mapping drift is detectable via warnings and unknown states.

---

## 6. Signal definitions

Each signal has compute logic, failure mode, and cache behavior.

### 6.1 Filesystem signals

- `spec_exists`: `Path(specs.product).is_file()`
- `tech_exists`: `Path(specs.tech).is_file()`
- Missing/invalid path → warning `missing_spec_link` / `missing_tech_link`, not crash.
- **Spec drift detection**: nếu canonical path missing nhưng glob `docs/features/*{feature_id}*.md` tìm thấy file khác → emit warning `possible_spec_moved` (artifact-drift overlay) với suggested path. Engine không auto-update tracker — founder phải reconcile manually. Mục đích: catch trường hợp founder rename spec file nhưng quên update tracker row.

### 6.2 Git signals

- `branch_exists`: `git ls-remote --heads origin <branch>`
- `commits_count`: `git rev-list --count origin/main..origin/<branch>`
- `last_commit_sha`: branch head SHA if exists
- `main_contains_merge`: whether main contains PR merge/squash SHA when known

Failure mode: network timeout → use state cache and mark `git_unknown=true`.

### 6.3 PR identity resolution

Branch-only lookup is not enough because branch may be deleted after merge. Resolution order:

1. If cached `github_pr` exists for work item, query PR by number.
2. Else query by `head={owner}:{branch}`.
3. Else search PR title/body for `linear_id`, `feature_id`, or branch name.
4. If found, cache `work_item_id → pr_number` in `.dashboard/state-cache.json`.
5. If multiple candidates, mark `pr_state=unknown` and surface `ambiguous_pr_mapping`.

This handles branch cleanup, squash merge, and renamed branches better than branch-only lookup.

### 6.4 PR state

- `none`: no PR resolved
- `draft`: PR exists and `draft=true`
- `open`: PR open and not draft
- `merged`: PR `merged_at != null`
- `closed`: PR closed without merge
- `unknown`: GitHub unavailable or ambiguous mapping

### 6.5 Review state

Review state must be latest-commit aware where possible.

- `none`: no reviews and no requested reviewers
- `review-requested`: requested reviewers exist, no submitted review yet
- `changes-requested`: at least one non-dismissed latest reviewer state is CHANGES_REQUESTED and not superseded by same reviewer approval after latest pushed commit
- `approved`: required reviewer(s) approved latest head SHA
- `mixed`: approvals exist but at least one unresolved changes-requested/review ambiguity remains
- `unknown`: API failure or insufficient data

Phase 1 may simplify implementation, but dashboard must label simplified review inference as approximate rather than pretending exactness.

### 6.6 CI state

Do **not** use “latest workflow run on branch” blindly; it can pick dashboard/doc workflows.

Preferred v1:

- Read check-runs/check-suites for PR head SHA.
- Filter by configured required workflow/check names.
- If no PR but branch exists, use branch head SHA checks.

Config example:

```yaml
required_checks:
  - test
  - pre-commit
  - import-linter
optional_checks:
  - dashboard
```

Config source v1: `scripts/work_state/config.yml` (or `[tool.work_state]` in `pyproject.toml` if the implementation prefers central config). Do not hardcode required checks in collectors.

States:

- `none`: no relevant checks
- `running`: queued/in_progress
- `pass`: all required checks success
- `fail`: at least one required check failure/cancelled/timed_out
- `unknown`: API unavailable/ambiguous

### 6.7 Deploy state

Railway signal is the weakest v1 signal. It must not block launch of the engine.

States:

- `not-applicable`: docs/research work with no deploy surface
- `not-deployed`: merged but deploy not observed
- `deploying`: deployment running when API supports it
- `deployed`: active deploy commit matches/contains merge or main commit after merge
- `deploy-failed`: deploy API/check reports failure
- `unknown`: Railway API unavailable or mapping not implemented

Phase 1 acceptable fallback:

```txt
If PR merged and main push completed, show status=merged and deploy_state=unknown.
Do not auto-upgrade to deployed using only time heuristic unless explicitly labeled heuristic.
```

UI must distinguish `not-deployed` ("engine confident: deploy chưa xảy ra") vs `unknown` ("engine không có signal"). Render `unknown` với `?` badge, `not-deployed` với `⏸` badge, `deploy-failed` với `✗` badge.

### 6.8 Exempt branch behavior

`.github/workflows/pr-validate.yml` exempts certain branch prefixes from `MMW-NNN` regex: `W0.*`, `Wave-*`, `hotfix/*`, `release/*`, `fix/*`, `feat/c1-*`, `chore/*`. These branches có thể có active PR mà không link tới tracker row.

Engine behavior cho exempt branches:

1. **Match tracker row by branch name**: nếu có row trong tracker với `branches[]` chứa exact branch name → bind work item normal (legacy Wave rows như `W0.9` thường ở category này).
2. **Không có tracker row**: emit `untracked_branch` warning (artifact-drift overlay). Render branch trong dashboard "Untracked" section với base state derived từ PR/CI/deploy signals nhưng không có plan metadata (priority/AC/owner unknown).
3. **PR body có `Linear: N/A`**: skip warning, render in "Ad-hoc work" bucket. Counted in throughput metrics, không counted trong feature progress %.
4. **PR body có `Closes MMW-NNN` nhưng branch exempt prefix**: bind tới work item by linear_id, emit `convention_drift` info (recommend founder rename branch sang `feat/MMW-NNN-slug` next time).

Mục đích: exempt branches ship được nhưng dashboard surface chúng để founder không bị blind, đồng thời không break engine khi gặp legacy/hotfix work.

---

## 7. Event model

Current snapshot is not enough for a Linear/Jira-like tracker. Need event history.

### 7.1 Event log

Write append-only JSONL:

```txt
.dashboard/events.jsonl
```

Example:

```json
{"ts":"2026-05-19T06:12:00Z","item":"MMW-108","event":"spec_created","from":"not-started","to":"spec-only","source":"filesystem","artifact":"docs/features/feature-funding-sources.md"}
{"ts":"2026-05-19T07:31:00Z","item":"MMW-108","event":"pr_opened","from":"in-progress","to":"in-review","source":"github","pr":42}
{"ts":"2026-05-19T08:10:00Z","item":"MMW-108","event":"ci_failed","overlay":"ci-failing","source":"github","check":"test"}
```

### 7.2 Trigger → event → transition map

| Trigger | Source | Event | State impact |
|---|---|---|---|
| Product spec file appears | filesystem/git | `spec_created` | `not-started → spec-only` |
| Tech spec file appears | filesystem/git | `tech_created` | `spec-only → tech-ready` |
| Branch appears | git | `branch_created` | `tech-ready → in-progress` |
| First commit appears | git | `commit_added` | progress increases |
| PR opened | GitHub | `pr_opened` | `in-progress → in-review` |
| PR marked draft | GitHub | `pr_draft` | `in-review → in-progress` or overlay draft |
| Review requested | GitHub | `review_requested` | overlay `review-requested` |
| Changes requested | GitHub | `changes_requested` | `in-review → changes-requested` |
| Approval submitted | GitHub | `approved` | `in-review → approved-pending-merge` |
| Required CI running | GitHub Checks | `ci_running` | overlay `ci-running` |
| Required CI failed | GitHub Checks | `ci_failed` | overlay `ci-failing` |
| Required CI passed | GitHub Checks | `ci_passed` | remove `ci-failing` overlay |
| PR merged | GitHub | `merged` | `approved-pending-merge/in-review → merged` |
| Deploy started | Railway | `deploy_started` | `merged → deploying` |
| Deploy succeeded | Railway | `deployed` | `deploying/merged → deployed` |
| Deploy failed | Railway | `deploy_failed` | overlay `deploy-failed` |
| PR no activity > threshold | event engine | `stale_detected` | overlay `stale` |

Events are generated by diffing latest signals against cached previous state.

#### 7.2.1 Event identity per type (de-dup key)

Generic de-dup tuple `(item, event, artifact, source_sha)` không đủ vì nhiều event không có `source_sha` (filesystem events) hoặc legitimate repeat trong 24h (CI rerun). De-dup key per event type:

| Event type | De-dup identity | Re-emit allowed? |
|---|---|---|
| `spec_created` / `tech_created` | `(item, event, artifact_path)` | Không — file existence là one-shot transition |
| `branch_created` | `(item, branch_name)` | Không |
| `commit_added` | `(item, commit_sha)` | Không (per-commit unique SHA) |
| `pr_opened` / `pr_draft` / `merged` / `closed` | `(item, pr_number, event)` | Không trừ khi PR reopened (separate event `pr_reopened`) |
| `review_requested` / `changes_requested` / `approved` | `(item, pr_number, reviewer, event, review_id)` | Re-emit if reviewer submits new review on later HEAD SHA |
| `ci_running` / `ci_failed` / `ci_passed` | `(item, pr_number, check_run_id, conclusion)` | Re-emit per re-run (mỗi re-run có check_run_id mới); legitimate dedup chỉ khi cùng check_run_id appearance trong tail |
| `deploy_started` / `deployed` / `deploy_failed` | `(item, deployment_id, status)` | Re-emit per deployment attempt; deployment_id unique per Railway/CI deploy attempt |
| `stale_detected` | `(item, pr_number, threshold_days)` | Re-emit max once per 24h per (item, threshold) — suppress redundant nag |
| `cache_warmup` / `stale_cache` | `(item, build_id, cache_event)` | Re-emit per build (build_id unique) |

Engine reads tail of `events.jsonl` (last 100 entries) trước khi append. Match dedup tuple per event type → skip append. Tail-bounded read giữ de-dup O(1) bất kể log size. Append-only — never modify or delete past events.

Fallback: nếu event type không có entry trong table → use generic `(item, event, artifact, source_sha)` tuple + 24h window. Engine warn `unknown_event_dedup_strategy` để founder catch missing definition.

### 7.3 State store

```txt
.dashboard/current_state.json     # latest normalized state per work item
.dashboard/state-cache.json       # PR number cache, last known API payload summaries
.dashboard/events.jsonl           # append-only lifecycle history
```

`.dashboard/` is runtime state. Generated/public artifacts remain docs/dashboard.*. Do not hand-edit generated dashboard output.

### 7.4 Persistence strategy — local vs CI

Because GitHub Actions runners are ephemeral, runtime-only state needs explicit persistence or the event engine loses history on every CI build.

| Environment | Persistence | Behavior |
|---|---|---|
| Local dev | `.dashboard/` gitignored runtime dir | Fast iteration; cache survives locally until manually nuked |
| CI / GitHub Actions | restore/save `.dashboard/` via `actions/cache` per key strategy §7.4.1 | Enables signal diff, event de-dupe, PR number cache, transition history |
| Public/generated output | `docs/dashboard.json`, `docs/dashboard.html`, `docs/dashboard.md` | Committed/generated projection; safe for users to consume |

#### 7.4.1 Cache key strategy

Dashboard workflow triggers on multiple events (main push, PR sync, review, CI workflow_run, schedule). Cache key phải đảm bảo cross-event cache sharing có ý nghĩa:

- **Primary cache key**: `dashboard-state-v${CACHE_SCHEMA_VERSION}-main` — always restore from main's cache, regardless of trigger source. Main is **single source of cumulative state**; PR builds enrich but không own canonical history.
- **PR build save**: cache key `dashboard-state-v${CACHE_SCHEMA_VERSION}-pr-${PR_NUMBER}-${HEAD_SHA}` (write-only branch, không restore). Mục đích: ephemeral debug if PR build needs introspection — không pollute main.
- **Restore-key fallback chain**:
  1. `dashboard-state-v${CACHE_SCHEMA_VERSION}-main` (exact)
  2. `dashboard-state-v${CACHE_SCHEMA_VERSION}-` (prefix — any earlier main version)
  3. Empty → emit `cache-warmup` overlay
- **Cache save**: chỉ main branch save lên primary key (atomic — last writer wins, accepted vì single-runner serialized via `concurrency: dashboard-rebuild` group per current workflow). PR builds save lên PR-specific key, expire sau 7 ngày.
- **Race handling**: per existing workflow `concurrency: dashboard-rebuild` group + `cancel-in-progress: true` đảm bảo no 2 main builds save cùng lúc. PR builds parallel OK vì key unique per `(PR, SHA)`.

#### 7.4.2 Cache miss behavior

- Engine still computes `current_state` from live artifacts.
- Event history starts fresh for that runner (events.jsonl empty).
- Dashboard adds `cache-warmup` overlay for the build so users know transition history may be incomplete (current snapshot still valid).
- No state should be inferred as false just because previous cache is missing.
- Phase 2 promotion gate: `cache-warmup` rate < 5% across last 100 builds (per AC17).

If GitHub cache is unavailable (vd outage, quota exhausted), fallback is acceptable for Phase 1 shadow mode, but Phase 2 promotion should require either restored cache or an explicit decision to commit a durable state snapshot projection.

### 7.5 State cache invalidation

`.dashboard/state-cache.json` tích lũy PR number mappings + last-known API payloads qua thời gian. Stale cache có thể mislead engine:

- Branch reused cho feature khác → cached PR number sai
- Force-push rewrote history → cached signals obsolete
- PR closed + reopened cùng số nhưng intent khác → stale review state
- Feature renamed (kebab-case migration) → (branch, feature_id) mapping đổi

Invalidation rules:

- **TTL per entry**: 30 ngày (configurable). Entries cũ hơn TTL được revalidate trên build kế tiếp.
- **Manual nuke**: `python scripts/build-dashboard.py --rebuild-cache` xoá cache + re-resolve toàn bộ PR mappings.
- **Schema version bump**: bump `CACHE_SCHEMA_VERSION` trong code → next read invalidates entire cache khi version mismatch.
- **Auto-invalidate on remap**: nếu `(branch, feature_id)` mapping đổi giữa builds, drop stale entry + re-resolve.
- **Per-item force resolve via CLI**: `python -m scripts.work_state --force-pr-resolve MMW-123` skip cache cho 1 work item trong 1 lần build, không touch tracker. Mục đích: ad-hoc fix khi cache stale mà chưa hit TTL. Không lưu state — invocation-scoped, không có "reset flag sau" semantics. Plan-source KHÔNG có `force_pr_resolve` field (không phải tracker concern).

---

## 8. Status state machine

Internal machine state stays detailed. Human-facing dashboard can render a simpler projection on top.

### 8.0 Human status projection

Dashboard cards should render:

```txt
HIGH_LEVEL_STATUS · machine_state
```

Examples:

```txt
TODO · tech-ready
IN_PROGRESS · pr-opened
WAITING · review-requested
FAILING · ci-failing
DONE · deployed
UNKNOWN · github-api-unknown
```

Recommended v1 projection (mirror canonical overlay enum §8.2):

| Human status | Machine state / overlay trigger |
|---|---|
| `BACKLOG` | base = `not-started` (no spec/branch artifacts yet) |
| `TODO` | base ∈ {`spec-only`, `tech-ready`} |
| `IN_PROGRESS` | base ∈ {`branch-created`, `in-progress`, `in-review`, `approved-pending-merge`} |
| `WAITING` | overlay `review-requested` OR `stale` OR base ∈ {`deploying`} |
| `FAILING` | overlay `ci-failing` OR `deploy-failed` (dominant over base) |
| `BLOCKED` | overlay `blocked` (explicit, dominant over all non-terminal) |
| `DONE` | base = `deployed`; cho docs/research/no-deploy work, terminal `merged` với `deploy_state=not-applicable` |
| `UNKNOWN` | overlay ∈ {`unknown`, `artifact-drift`, `ambiguous-pr-mapping`} |

**Resolution precedence** (first match wins khi multiple overlays active):
1. `BLOCKED` (human intent dominant)
2. `FAILING` (`ci-failing` / `deploy-failed`)
3. `UNKNOWN` (signal/mapping issue)
4. `WAITING` (`review-requested` / `stale`)
5. Base status → map to `BACKLOG`/`TODO`/`IN_PROGRESS`/`DONE`

Annotation overlays (`partial-progress`, `stale-cache`, `cache-warmup`, `risk-tier-inferred`, `manual-override`) không thay đổi human status; render như badge bên cạnh.

Do not replace internal machine states with this projection. Projection is for UI readability; machine state remains the actionable detail.

### 8.1 Base status

Derived status, first-match priority. Note: `deploy-failed` là OVERLAY, không phải base — `compute_status` trả về `merged` cho merged PR có deploy fail, urgency model (§9.4) + UI sort (§8.0) sẽ surface failure dominantly.

```python
def compute_status(s: Signals) -> Status:
    # Terminal positive states first
    if s.deploy_state == "deployed":
        return "deployed"
    if s.deploy_state == "deploying":
        return "deploying"
    if s.pr_state == "merged":
        # deploy_state == "deploy-failed" → still base "merged",
        # overlay handled separately in compute_overlays()
        return "merged"
    if s.pr_state == "closed":
        return "abandoned"

    # Active PR states
    if s.pr_state == "open":
        if s.review_state == "changes-requested":
            return "changes-requested"
        if s.review_state == "approved":
            return "approved-pending-merge"
        return "in-review"

    if s.pr_state == "draft":
        return "in-progress"

    # Pre-PR code states
    if s.branch_exists and s.commits_count > 0:
        return "in-progress"

    if s.branch_exists:
        return "branch-created"

    # Pre-code planning states
    if s.tech_exists:
        return "tech-ready"

    if s.spec_exists:
        return "spec-only"

    return "not-started"
```

Note: `compute_overlays(s) -> list[Overlay]` (separate function) determines overlay set. UI rendering = `(base_status, overlays, urgency)` tuple.

### 8.2 Overlays — canonical enum (§8.2 = single source of truth)

Do not overload base status with operational warnings. **All overlay references trong spec (§7.2 events, §8.0 human projection, §10 Phase 2, AC10) phải mirror danh sách dưới đây — không thêm overlay nào không có ở đây.**

| Overlay | Source | Meaning | Maps to human status |
|---|---|---|---|
| `blocked` | explicit PR label `blocked` or manual override only | Human says work cannot progress | `BLOCKED` |
| `stale` | no activity threshold (default 14 days) | Needs attention; not necessarily blocked | `WAITING` (overlay annotation) |
| `ci-running` | required checks queued/in_progress | Transient — CI execution in flight | (no human-status change) |
| `ci-failing` | required checks fail | Code/review issue | `FAILING` |
| `review-requested` | reviewers requested, no response yet | Waiting for reviewer | `WAITING` |
| `deploy-failed` | Railway/CI reports deploy failure | Production rollback / re-deploy needed | `FAILING` |
| `unknown` | API/signal failure | Engine cannot trust signal | `UNKNOWN` |
| `artifact-drift` | tracker points to missing/ambiguous artifact (incl. `missing_spec_link`, `possible_spec_moved`, `untracked_branch`, `convention_drift`) | Plan/source mapping needs repair | `UNKNOWN` |
| `ambiguous-pr-mapping` | PR identity resolution found multiple candidates | Engine can't pick PR → mark unknown | `UNKNOWN` |
| `partial-progress` | multi-branch aggregation: some coupled branches at terminal state while others in-progress | Reality hidden by MIN-progressed status alone | (annotation, no rollup change) |
| `stale-cache` | cache entry expired or invalidated | Engine revalidates before trusting cached mapping | (annotation) |
| `cache-warmup` | CI/local run has no previous state cache | Current snapshot valid; event history may be incomplete | (annotation) |
| `risk-tier-inferred` | risk_tier missing in tracker row, inferred from lane/type | Plan metadata incomplete; founder phải make explicit | (annotation) |
| `manual-override` | override active per §8.3 | Computed state intentionally overridden | (depends on override target) |

Important: CI fail streak or PR age should not auto-become `blocked`. They become `ci-failing` or `stale` overlays. `blocked` requires explicit human intent (label or override). Engine emit `deploy-failed` overlay khi `deploy_state=deploy-failed`; base status vẫn `merged`.

### 8.3 Manual override escape hatch

Rare cases can override computed status with expiry:

```yaml
manual_state_override:
  status: in-monitoring
  reason: production monitoring for first 7 days after cutover
  until: 2026-05-26
```

Rules:

- `until` required.
- Dashboard shows `manual-override` badge.
- Expired override auto ignored and warned.
- Target usage <5% of rows.

---

## 9. Progress model

Status is categorical. A Linear/Jira-like tracker also needs progress.

### 9.1 Progress profiles

Different work types need different weights.

#### `standard_feature`

| Milestone | Weight |
|---|---:|
| product spec exists | 10% |
| tech spec exists | 20% |
| branch exists | 30% |
| commits exist | 45% |
| PR open | 60% |
| required CI pass | 75% |
| approved | 85% |
| merged | 95% |
| deployed / released | 100% |

#### `docs_only`

| Milestone | Weight |
|---|---:|
| doc file exists | 30% |
| review/validation command passes | 70% |
| merged | 100% |

#### `foundation_change`

Foundation Lane work needs signals beyond standard milestones. Each milestone phải có **detectable artifact** — không có signal = milestone không count:

| Milestone | Weight | Signal source |
|---|---:|---|
| spec/plan exists | 10% | `specs.product` file exists (filesystem) |
| migration/architecture design exists | 25% | `specs.tech` file exists AND contains `## Migration` hoặc `## Architecture` heading (filesystem grep) |
| branch + tests added | 45% | `branches[].commits_count ≥ 1` AND test files exist trong PR diff (GitHub API: PR files endpoint, match `tests/**`) |
| PR open | 60% | `pr_state == "open"` (GitHub PR API) |
| cross-model review approved | 75% | PR review by user/label tagged `codex-approved` OR PR review comment chứa keyword `[Codex Review · APPROVE]` (per `codex-review-prompt-*.md` output convention) |
| all gates pass | 85% | All required CI checks `pass` (GitHub Checks API) + import-linter clean + tenant-isolation tests pass |
| founder sign-off | 95% | PR comment by founder chứa `Foundation Lane founder approval:` marker (per `walkthrough-foundation-lane-example.md` §6 convention) |
| merged/deployed | 100% | `pr_state=merged` AND (`deploy_state=deployed` OR `deploy_state=not-applicable`) |

Engine signal collectors phải implement detection cho mỗi marker. Per AC9a (new), `plan_reader.py` + `signal_collectors/github.py` cover các marker này.

Fallback: nếu milestone không có signal yet → progress stay ở previous milestone, không skip. Engine không "guess" — chỉ count khi signal verified.

#### `dashboard_engine`

Use `foundation_change` profile by default because this changes tracker/dashboard pipeline and source-of-truth semantics.

### 9.2 Phase progress rollup

V1: simple average of work item progress within phase.

**Companion metrics (required cho UI render, không optional)**: simple average alone misleading khi 1 P0 ở 10% bị dilute bởi nhiều docs item ở 100%. Dashboard phải render counts theo dimension cùng với %:

```
Phase 2 progress: 65% (avg)
├─ 12 items: 3 DONE · 5 IN_PROGRESS · 2 WAITING · 1 FAILING · 1 BLOCKED
├─ Urgency: 1 critical · 2 elevated · 1 warning · 8 normal
└─ Priority breakdown: P0 (1 item, 40% avg) · P1 (4 items, 70% avg) · P2 (7 items, 75% avg)
```

Mục đích: founder thấy ngay "65%" không tốt vì 1 P0 critical đang drag rủi ro Phase.

Deferred: weighted rollup by priority/lane (formula based). Do not implement weighted rollup until simple rollup + companion counts prove useful.

### 9.3 Weight calibration plan

V1 weights (Section 9.1) là heuristic — chưa có data validate. Sau Phase 1 shadow mode chạy ≥ 4 tuần và `events.jsonl` tích đủ transitions:

- Compute median actual time-from-milestone-to-milestone từ event log.
- Recalibrate weights để progress curve match observed work distribution. Ví dụ: nếu thực tế spec→tech chiếm 30% tổng work time (không phải 10% như v1), bump spec weight tương ứng.
- Recalibrate **per profile** (`standard_feature` / `docs_only` / `foundation_change` / `dashboard_engine`), không per-feature.
- Cadence: quarterly review, không ad-hoc.
- Reproducibility: log `progress_profile_version: 2026.05` trong events để historical progress numbers stay reproducible khi weights đổi sau này.

Anti-pattern cần tránh: recalibrate trước khi có data thực sự. V1 weights "good enough" cho shadow mode; chính xác đến sau.

---

## 9.4 Runtime urgency model

`runtime_urgency` is derived operational attention. It is **not** business priority and **not** risk tier.

```txt
priority        = roadmap/business importance (manual)
risk_tier       = process/safety strictness (manual/inferred)
runtime_urgency = operational attention needed now (derived)
```

### 9.4.1 Derivation algorithm (first-match wins)

Engine computes urgency deterministically per work item. Order matters — first matching rule decides:

```python
def compute_urgency(item: WorkItem, base: Status, overlays: set[Overlay]) -> Urgency:
    # 1. CRITICAL — production / data integrity at risk
    if "deploy-failed" in overlays:
        return "critical"
    if base == "deployed" and "unknown" in overlays:
        # production state we can't verify = critical for security/data work
        if item.risk_tier in {"P0", "P1"}:
            return "critical"
    if "ci-failing" in overlays and base == "merged":
        # CI failing post-merge = main broken
        return "critical"

    # 2. ELEVATED — active work with required attention
    if "blocked" in overlays and item.priority in {"P0", "P1"}:
        return "elevated"
    if "ci-failing" in overlays:
        return "elevated"
    if base == "approved-pending-merge" and "stale" in overlays:
        # approved but sitting → push merge
        return "elevated"
    if "ambiguous-pr-mapping" in overlays:
        return "elevated"  # engine can't trust state for this item

    # 3. WARNING — degraded signal or attention soon
    if "stale" in overlays:
        return "warning"
    if "unknown" in overlays:
        return "warning"
    if "artifact-drift" in overlays:
        return "warning"
    if "cache-warmup" in overlays:
        return "warning"  # event history incomplete

    # 4. NORMAL — no active concerns
    return "normal"
```

### 9.4.2 Multi-branch aggregation

Work item urgency = **MAX (most severe)** across branch-level urgencies. Rationale: 1 branch deploy-failed = whole work item critical, không bị diluted by other branches normal.

```
critical > elevated > warning > normal
```

### 9.4.3 UI rendering

Dashboard should sort/flag by `runtime_urgency` separately from `priority` + `risk_tier`. Three axes hiển thị riêng:

```
[P1 · risk=P0 · 🔥 critical] funding-sources · DONE · deploy-failed
                                                       ↑ urgency dominant cue
```

A P2 item can be `critical` if deploy failed; a P0 item can be `normal` if it is progressing cleanly.

### 9.4.4 Overlay combinations

Rule precedence (already in algorithm): post-merge production failures > active-work failures > attention-soon signals > clean.

Examples:
- `merged` + `deploy-failed` → critical
- `merged` + `ci-failing` (CI broke main) → critical
- `in-review` + `ci-failing` → elevated
- `in-review` + `stale` + `ci-failing` → elevated (ci-failing dominant over stale at same level)
- `in-progress` + `blocked` (P0) → elevated
- `in-progress` + `blocked` (P2) → warning (P2 blocked không phải elevated; stale rule won't escalate either since blocked != stale)
- `branch-created` + `cache-warmup` → warning (signal incomplete)
- `deployed` (no overlays) → normal

Progress changes from **artifact/workflow events**, not manual status drag-and-drop. Examples include spec created, branch created, commit pushed, PR opened, CI passed, review approved, founder sign-off, merged, deployed.

---

## 10. Implementation plan

Migration is phased. No big-bang.

### Phase 0 — Pre-work (1 day)

- Audit tracker rows for stable `id`, `feature_id`, `type`, `phase`, `priority`, `lane`, `specs`, `branches`, `acceptance`.
- Add explicit `progress_profile` where not inferable.
- Confirm `gh` or direct GitHub REST availability in CI.
- Add `.dashboard/` to `.gitignore` if runtime state is not committed.
- Decide whether `current_state.json/events.jsonl` are runtime-only or committed snapshots. Recommendation: runtime-only; dashboard JSON is committed/generated public artifact.

Exit criteria:

- Every row normalizes into `WorkItem`.
- Missing optional fields are explicit `null`, not silently absent.

### Phase 1 — Engine shadow mode (5-7 days, revised)

V1.2.0 estimate 3-4 days underestimated scope. Realistic sub-phasing:

**Phase 1a — Core engine + 2 collectors (2 days)**
- Add `scripts/work_state/` skeleton: `models.py`, `plan_reader.py`, `event_engine.py`, `status_machine.py`, `progress.py`, `state_store.py`.
- Implement 2 simplest collectors: `signal_collectors/filesystem.py` + `signal_collectors/git.py`.
- Read tracker → normalize WorkItems.
- Compute base status + progress cho filesystem+git signals only.
- Write `.dashboard/current_state.json`, `.dashboard/events.jsonl` skeleton.
- Unit tests cho models + state machine transitions.

**Phase 1b — GitHub/CI collectors + dashboard projection (2 days)**
- `signal_collectors/github.py` (PR state + reviews) + `signal_collectors/ci.py` (check-runs).
- PR identity resolution (§6.3 5-step fallback).
- `projections/dashboard.py` — enrich `docs/dashboard.json` with `state` block, render manual + computed side-by-side.
- Add `--no-network` mode + cache TTL.

**Phase 1c — Railway/deploy + persistence + workflow (1-2 days)**
- `signal_collectors/railway.py` (heuristic OK, `unknown` acceptable).
- `.dashboard/` CI persistence via `actions/cache` per §7.4.1.
- Extend `.github/workflows/dashboard.yml` triggers per §11.4.
- Integration tests, dogfood trên active tracker rows.

**Phase 1 buffer (1 day)**: refactor pass sau khi shadow data về, fix collector edge cases caught lúc dogfood.

Exit criteria:
- 7 days shadow mode chạy stable sau Phase 1c complete.
- Terminal states (`merged`, `deployed` where known) ≥95% accurate per AC15.
- All mismatches logged as event or warning.
- Cache-warmup overlay rate <5% across 100 builds.

Realistic total Phase 1: **5-7 work days** + 7-day monitoring window.

### Phase 2 — Projection promotion (1-2 days)

- Dashboard primary status becomes computed status.
- Manual status becomes annotation only.
- Add signal drilldown per work item.
- Add overlays per canonical enum §8.2: `blocked`, `stale`, `ci-running`, `ci-failing`, `review-requested`, `deploy-failed`, `unknown`, `artifact-drift`, `ambiguous-pr-mapping`, `partial-progress`, `stale-cache`, `cache-warmup`, `risk-tier-inferred`, `manual-override`.
- Update `dashboard-realtime-explained.md` with engine architecture.

Exit criteria:

- Founder can answer "what is in progress/review/blocked/stale" from dashboard without editing tracker status.
- No critical state misclassification for 2 weeks. **Critical misclassification defined** (any of):
  - False `DONE` — work item shows deployed but `deploy_state ≠ deployed` in reality (verify by spot-check Railway)
  - Missed deploy failure — `deploy-failed` overlay missing while Railway shows failure
  - Wrong PR mapping — work item bound to wrong PR (verify by PR title/branch sanity check)
  - False terminal — `merged`/`abandoned` shown but PR actually `open` or vice versa
  - Hidden blocking overlay — `blocked` overlay missing while PR has `blocked` label
  - Stale `cache-warmup` — rate >5% across 100 builds = cache restoration broken
- Engine-level success rate ≥95% across all work items (terminal states + active states).
- Cache-warmup overlay rate <5% per AC17 (per §7.4.2).

### Phase 3 — Remove manual status field (0.5-1 day)

Gated by Phase 2.

- Remove manual `status` column.
- Add optional `manual_state_override` field with expiry.
- Build script fails if it reads manual status as truth.
- Update source-of-truth docs.

Exit criteria:

- Tracker no longer has status source-of-truth.
- Founder does not edit status after merge/review/deploy.

### Phase 4 — Linear/Jira-like projection (deferred)

Activate when dashboard engine is stable.

- Render kanban board from `current_state.json`.
- Optional Linear sync as projection or plan source.
- Do not make Linear status source-of-truth unless it is also derived from engine events.

---

## 11. Concrete code changes

### 11.1 Modules

```txt
scripts/work_state/
  __init__.py
  models.py
  plan_reader.py
  status_machine.py
  progress.py
  event_engine.py
  state_store.py
  signal_collectors/
    __init__.py
    filesystem.py
    git.py
    github.py
    ci.py
    railway.py
  projections/
    __init__.py
    dashboard.py
```

### 11.2 Model sketch

```python
@dataclass(frozen=True)
class WorkItem:
    id: str                 # Stable internal identity (e.g. "MMW-108", "W0.9" legacy)
    linear_id: str | None   # Linear ticket reference; None for legacy/ad-hoc work
    feature_id: str         # Kebab-case canonical feature key
    title: str
    type: str
    phase: str
    priority: str           # roadmap/business priority (P0/P1/P2)
    risk_tier: str          # P0/P1/P2 process risk; distinct from priority
    lane: str               # Fast/Standard/Foundation
    owner: str              # "founder" now; team member later
    deadline: str | None    # ISO date or None
    specs: dict[str, str | None]
    branches: list[str]
    acceptance: list[str]
    dependencies: list[str]
    external_blockers: list[str]
    decision_needed: str | None
    progress_profile: str
    manual_state_override: ManualOverride | None = None

@dataclass
class Signals:
    spec_exists: bool
    tech_exists: bool
    branch_states: list[BranchState]
    pr_state: str
    pr_number: int | None
    review_state: str
    ci_state: str
    deploy_state: str
    warnings: list[str]

@dataclass
class CurrentState:
    item_id: str
    status: str
    human_status: str
    progress: int
    runtime_urgency: str
    overlays: list[str]
    signals: Signals
    last_event_ts: str | None
```

### 11.3 GitHub/CI implementation rule

Use direct REST or `gh`, but keep an adapter boundary. Do not scatter `gh api` calls inside dashboard rendering.

Required behavior:

- API unavailable → `unknown`, not false `none`.
- Branch deleted after merge → PR cache still resolves PR.
- CI reads required checks for head SHA, not arbitrary latest workflow run.

### 11.4 Dashboard workflow triggers

```yaml
on:
  push:
    branches: [main]
  pull_request:
    types: [opened, closed, reopened, synchronize, ready_for_review, converted_to_draft, review_requested, labeled, unlabeled]
  pull_request_review:
    types: [submitted, dismissed]
  workflow_run:
    workflows: [CI]
    types: [completed]
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:
```

Anti-loop guard stays mandatory.

---

## 12. Risks + mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| GitHub API outage | Low | Medium | render last known state + `unknown` overlay; no crash |
| CI runner cache missing | Medium | Medium | compute current snapshot anyway; add `cache-warmup`; restore/save `.dashboard/` via `actions/cache` before Phase 2 promotion |
| PR mapping drift | Medium | Medium | PR number cache + branch/title/Linear fallback + `ambiguous_pr_mapping` warning |
| Branch deleted after merge | High | Medium | PR cache + merged PR lookup by id/title |
| CI misread from wrong workflow | Medium | High | required checks config; read check-runs by SHA |
| Railway deploy signal unavailable | Medium | Low | deploy_state=`unknown`; don't block state engine |
| State machine misclassifies edge case | Medium | Medium | shadow mode + event log + tests |
| Manual override becomes hidden manual status | Medium | Medium | expiry required + dashboard badge + usage target <5% |
| Artifact mapping drift | Medium | Low | warnings + dashboard repair queue |
| Build latency increases | Medium | Low | cache + batched API calls + `--no-network` local mode |
| Tracker markdown becomes brittle | Medium | Medium | normalize to WorkItem model; consider `work-items.yml` later |

---

## 13. Acceptance criteria

- [ ] **AC1** — `scripts/work_state/` module structure exists, mypy strict clean:
  - [ ] **AC1a** — `models.py`: `WorkItem`, `Signals`, `CurrentState`, `Event` dataclasses
  - [ ] **AC1b** — `plan_reader.py`: tracker.md rows → `WorkItem` normalization
  - [ ] **AC1c** — `signal_collectors/`: filesystem, git, github, ci, railway adapters (each unknown-safe)
  - [ ] **AC1d** — `event_engine.py`: signal diff → event emission with write-time de-dup
  - [ ] **AC1e** — `status_machine.py`: `compute_status(signals) → Status`
  - [ ] **AC1f** — `progress.py`: progress profile implementation
  - [ ] **AC1g** — `projections/dashboard.py`: dashboard render from `CurrentState`
- [ ] **AC2** — Tracker rows normalize into canonical `WorkItem`; invalid rows produce actionable warnings.
- [ ] **AC3** — `current_state.json` contains status, progress, overlays, signals per work item.
- [ ] **AC4** — `events.jsonl` records state-changing events with timestamp, source, from/to, artifact reference.
- [ ] **AC5** — Dashboard JSON includes computed state/progress and signal drilldown.
- [ ] **AC6** — Manual status still rendered in shadow mode, but computed status is visible side-by-side.
- [ ] **AC7** — PR resolution handles branch deleted after merge via cached PR number or fallback search.
- [ ] **AC8** — CI state reads required checks for PR/branch head SHA, not arbitrary latest workflow run.
- [ ] **AC9** — Deploy signal can be `unknown`; engine remains useful without Railway API.
- [ ] **AC10** — Overlays implemented separately from base status per canonical enum §8.2: `blocked`, `stale`, `ci-running`, `ci-failing`, `review-requested`, `deploy-failed`, `unknown`, `artifact-drift`, `ambiguous-pr-mapping`, `partial-progress`, `stale-cache`, `cache-warmup`, `risk-tier-inferred`, `manual-override`. Lists in §7.2 events, §8.0 human projection, §10 Phase 2 mirror this set exactly.
- [ ] **AC11** — Progress profile exists for at least `standard_feature`, `docs_only`, `foundation_change`, `dashboard_engine`.
- [ ] **AC11a** — Human status projection exists (`BACKLOG`, `TODO`, `IN_PROGRESS`, `WAITING`, `FAILING`, `BLOCKED`, `DONE`, `UNKNOWN`) and renders as `HIGH_LEVEL · machine_state` without replacing machine state. Resolution precedence (§8.0) deterministic.
- [ ] **AC11b** — `runtime_urgency` derived field exists (`normal`, `warning`, `elevated`, `critical`) and is distinct from `priority` and `risk_tier`. Deterministic first-match algorithm per §9.4.1, multi-branch MAX aggregation per §9.4.2.
- [ ] **AC11c** — `foundation_change` progress milestones có detectable artifact signal per §9.1 — không count milestone không có signal. `signal_collectors/github.py` detect codex-approved label/marker + founder sign-off comment marker.
- [ ] **AC11d** — Multi-branch aggregation matrix (§4.1.1, 4.1.2, 4.1.3) implemented: MIN-progressed base + UNION overlays + MAX urgency. `partial-progress` overlay applied per rule.
- [ ] **AC11e** — Event de-dup uses per-event-type identity (§7.2.1) — CI events keyed by `check_run_id`, deploy by `deployment_id`, stale max once per 24h per (item, threshold).
- [ ] **AC12** — Unit tests cover state transitions and edge cases: PR closed unmerged, branch deleted after merge, squash merge/PR cache, API unavailable, missing spec links, CI fail, deploy fail post-merge, stale PR, manual override expiry, multi-branch compound states (deployed+ci-failing, merged+blocked).
- [ ] **AC13** — `.github/workflows/dashboard.yml` triggers on PR, review, CI completion, main push, schedule, manual dispatch.
- [ ] **AC14** — `dashboard-realtime-explained.md` updated with work-state engine architecture.
- [ ] **AC15** — Phase 3 cutover removes manual status only after shadow mode proves ≥95% accuracy for terminal states and no critical misclassification for 2 weeks. Critical misclassification defined per §10 Phase 2 exit criteria (false DONE, missed deploy fail, wrong PR mapping, false terminal, hidden blocking, stale cache-warmup rate >5%).
- [ ] **AC16** — `CLAUDE.md` source-of-truth table updated: status/progress derived from work-state engine; tracker.md là plan source only; `.dashboard/` runtime state ignored by git per `.gitignore`.
- [ ] **AC17** — CI restores/saves `.dashboard/` via `actions/cache` per §7.4.1 strategy (primary key `dashboard-state-v${V}-main`, PR builds write-only ephemeral key); cache-warmup rate <5% across 100 builds; Phase 2 promotion requires persistence strategy locked.
- [ ] **AC18** — `priority`, `risk_tier`, and `lane` remain separate fields; if `risk_tier` is inferred, dashboard surfaces `risk_tier_inferred` warning until made explicit.
- [ ] **AC19** — `WorkItem` schema separates `id` (stable internal, e.g. `MMW-108` or `W0.9` legacy) from `linear_id: str | None` (Linear ticket reference, optional). `plan_reader` warn nếu row có active PR/branches nhưng thiếu `linear_id`.
- [ ] **AC20** — Exempt branch behavior implemented per §6.8: untracked branches → `untracked_branch` warning, render in "Untracked" section; `Linear: N/A` PR body → "Ad-hoc work" bucket; `Closes MMW-NNN` on exempt branch → bind by `linear_id` + `convention_drift` info.
- [ ] **AC21** — Phase rollup (§9.2) renders companion counts: items by human status, items by urgency level, items by priority. Single average % alone insufficient — UI phải show full picture.
- [ ] **AC22** — Migration runbook (§15) covers full rollback: revert HEAD + restore tracker .bak + bump `CACHE_SCHEMA_VERSION` (invalidates `.dashboard/`) + remove generated `docs/dashboard.{html,json,md}` if Phase 3 commit range tagged + identify migration commit range/tag.
- [ ] **AC23** — `--force-pr-resolve <work_item_id>` CLI flag implemented (§7.5) — invocation-scoped, không touch tracker plan source.
- [ ] **AC24** — Possible spec drift detection (§6.1): nếu canonical spec path missing nhưng glob match feature_id → emit `possible_spec_moved` warning với suggested path. Engine không auto-update.

---

## 14. Open questions

**Q1 — Plan source format:** Keep markdown tracker as v1, or introduce `docs/work-items.yml` for machine-first schema? Recommendation: keep markdown now, but normalize internally so source can change later.

**Q2 — Commit or ignore `.dashboard/current_state.json` and `events.jsonl`?** Recommendation: runtime-only ignored. Commit `docs/dashboard.json` as public generated projection.

**Q2a — CI persistence mechanism:** Use GitHub `actions/cache` for `.dashboard/`, or commit a durable state snapshot? Recommendation: `actions/cache` for runtime state, committed `docs/dashboard.json` for public projection. Phase 2 cannot promote until this is verified.

**Q3 — Railway deploy source:** Does Railway expose active deployment commit reliably? If not, keep `deploy_state=unknown` in v1 and avoid pretending deploy precision.

**Q4 — Progress weights:** Are simple fixed weights sufficient? Recommendation: yes for v1; do not overfit before usage.

**Q5 — Multi-branch feature:** Split into sub-items or aggregate? Recommendation: split when branches represent independently mergeable PRs; aggregate only for truly coupled branches.

**Q6 — Linear future role:** Plan source, projection, or both? Recommendation: projection first. If team scales, Linear can become plan source, but derived status should still come from engine artifacts.

---

## 15. Migration runbook — Phase 3 cutover

Only after Phase 1-2 confidence gates pass.

```bash
# Tag pre-migration state
git tag dashboard-pre-auto-progress-engine

# Backup tracker
cp docs/implementation-tracker.md docs/implementation-tracker.md.bak

# Run migration script
python scripts/migrate-tracker-schema.py \
  --remove-column status \
  --add-column manual_state_override \
  --in docs/implementation-tracker.md

# Verify engine + projection
python scripts/build-dashboard.py
python -m pytest tests/scripts/test_work_state.py -v
python -m pytest tests/scripts/test_build_dashboard.py -v

# Confirm generated state
# → dashboard.json has state/progress per item
# → no manual_status field as source of truth
# → overrides are explicit + expiring

# Commit
git add docs/implementation-tracker.md scripts/work_state scripts/build-dashboard.py docs/dashboard.json docs/dashboard.html
git commit -m "refactor(dashboard): derive work progress from artifacts"

# PR + review per Foundation Lane
```

Rollback (full):

```bash
# 1. Identify migration commit range
MIGRATION_TAG=dashboard-pre-auto-progress-engine
MIGRATION_RANGE="${MIGRATION_TAG}..HEAD"
git log --oneline "${MIGRATION_RANGE}"  # verify before revert

# 2. Revert all migration commits (if multi-commit, use range)
git revert --no-commit "${MIGRATION_RANGE}"
git commit -m "revert: rollback work-state engine migration"

# 3. Restore tracker if migration script ran
mv docs/implementation-tracker.md.bak docs/implementation-tracker.md
git add docs/implementation-tracker.md
git commit --amend --no-edit

# 4. Bump CACHE_SCHEMA_VERSION to invalidate `.dashboard/` runtime state
# Edit scripts/work_state/state_store.py: CACHE_SCHEMA_VERSION = "v2-rollback"
# Or directly clear runtime state for next build:
rm -rf .dashboard/

# 5. Remove generated dashboard outputs nếu cần (next build sẽ regenerate từ rolled-back state)
rm -f docs/dashboard.html docs/dashboard.md docs/dashboard.json

# 6. Trigger rebuild on main to regenerate dashboard outputs from old logic
python scripts/build-dashboard.py
git add docs/dashboard.html docs/dashboard.md docs/dashboard.json
git commit -m "chore(dashboard): regenerate after engine rollback"

# 7. Push + force re-deploy on Railway
git push origin main

# 8. GitHub Actions cache cleanup (optional, if engine cache was poisoned)
gh cache list --json key,id | jq '.[] | select(.key | startswith("dashboard-state-v"))'
# Manually delete via UI or `gh cache delete <id>` if needed
```

Rollback gates:
- Step 1 phải verify tag exists trước khi revert (`git rev-parse ${MIGRATION_TAG}` returns SHA)
- Step 4 cần bump CACHE_SCHEMA_VERSION không phải xoá file vì future runs từ cache stale sẽ poison lại
- Step 5+6 chỉ làm sau khi xác định stale dashboard không gây hiểu lầm — nếu monitoring panel tham chiếu live URL thì stale OK trong vài phút
- Step 8 chỉ cần nếu engine bug tạo poison data trong cache; thường skip

---

## 16. Estimated effort

Revised after Codex review (Finding 14): Phase 1 sub-phased explicitly với realistic ranges.

| Phase | Effort | Calendar | Owner | Dependencies |
|---|---:|---:|---|---|
| 0 Pre-work | 1 day | 1 day | Founder | tracker audit |
| 1a Core engine + filesystem + git collectors | 2 days | included in Phase 1 | Founder + Claude Code | GitHub token, required checks config |
| 1b GitHub + CI collectors + dashboard projection | 2 days | included in Phase 1 | Founder + Claude Code | Phase 1a stable |
| 1c Railway + persistence + workflow | 1-2 days | included in Phase 1 | Founder + Claude Code | Phase 1b stable, CI cache persistence verified |
| 1 buffer + dogfood | 1 day | +7 days shadow monitoring | Founder | Phase 1a-1c done |
| 2 Projection promotion | 1-2 days | +14 days confidence window | Founder + Claude Code | Phase 1 stable |
| 3 Remove manual status | 0.5-1 day | 1 day | Founder | Phase 2 confidence |
| 4 Linear/Jira-like projection | deferred | TBD | TBD | engine stable |

**Total Phase 0-3:** ~8-11 work days (was 6-8) + monitoring windows.

**Calendar buffer recommended +30%**: scope hardening through Codex round 1 added concrete artifact detection cho Foundation milestones, deterministic urgency algorithm, multi-branch aggregation matrix, full rollback runbook. Realistic calendar: **3-4 tuần** thay vì 2 tuần. Engine module mới + 6 collectors mỗi cái unknown-safe cần dedicated dev + integration testing.

Lane: **Foundation Lane / P0** because this changes dashboard pipeline, tracker schema, and source-of-truth semantics. Codex review required. Founder approval required before Phase 3 cutover.

---

## Changelog

| Version | Date | Author | Notes |
|---|---|---|---|
| v1.2.0 | 2026-05-19 | Founder + Claude | Integrated artifact-driven workflow feedback: added Intent vs Reality framing, artifact-derived authoritative state wording, human status projection, runtime urgency model, and clarified progress changes come from artifact/workflow events. |
| v1.1.1 | 2026-05-19 | Founder + Claude | Hardening pass: added CI/runtime state persistence strategy, cache-warmup/stale-cache overlays, CLI module path consistency, required-check config source, and separated priority vs risk_tier vs lane. |
| v1.1.0 | 2026-05-19 | Founder + Claude | Expanded from dashboard plan/state split into auto-progress work engine. Added WorkItem schema, manual-vs-derived boundary, event log, progress profiles, projections, robust PR/CI/deploy handling, overlays, migration gates, and Linear/Jira-like future path. |
| v1.0.0 | 2026-05-19 | Founder + Claude | Initial proposal. Status: Proposed. Awaiting Codex review + founder sign-off. |
