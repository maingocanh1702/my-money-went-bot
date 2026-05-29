# Linear Workspace Migration Guide — maingocanh → maingocanh1

**Generated:** 2026-05-23
**Scope:** Manual recreation via Linear UI (MCP token stays on old workspace)

---

## Trước khi bắt đầu

- Verify workspace switcher trong Linear web app đang ở **`maingocanh1`** (avatar/dropdown góc trái trên có checkmark cạnh `maingocanh1`)
- Team `MyMoneyWent` (key `MYM`) đã tạo trong `maingocanh1` ✅ (anh xác nhận trước đó)
- Linear ↔ GitHub integration đã fix ✅

---

## Bước 1 — Recreate 7 labels (team `MyMoneyWent`)

Vào: **Linear → Settings → Teams → MyMoneyWent → Labels**

Click **+ New label** cho từng dòng dưới đây:

| Name | Color (hex) | Mục đích |
|------|-------------|----------|
| `CI` | `#f2994a` | CI/CD related issues |
| `dashboard` | `#f2994a` | Dashboard / WorkState engine |
| `infrastructure` | `#f2c94c` | Infra, tooling, build system |
| `foundation` | `#26b5ce` | Foundation lane (P0/P1) issues |
| `Feature` | `#BB87FC` | New feature work |
| `Improvement` | `#4EA7FC` | Enhancement to existing |
| `Bug` | `#EB5757` | Bug fixes |

> Lưu ý: Hex color paste vào field **Color** trong dialog "New label". Linear sẽ snap về swatch gần nhất.

---

## Bước 2 — Recreate project `WorkState V1 — Dashboard Live Tracker`

Vào: **Linear → Projects → + New project** (đảm bảo workspace = `maingocanh1`)

**Project fields:**

| Field | Value |
|-------|-------|
| **Name** | `WorkState V1 — Dashboard Live Tracker` |
| **Icon** | `:radar:` (radar emoji) |
| **Color** | Để default (`#bec2c8`) hoặc tùy chọn |
| **Lead** | Ngoc-Anh Mai (anh) |
| **Teams** | MyMoneyWent |
| **Priority** | High |
| **Status** | In Progress |
| **Start date** | `2026-05-21` |
| **Target date** | (để trống) |

**Summary** (paste vào field Summary, max 255 chars):

```
Standalone product spin-out from MyMoneyWent. Realtime project dashboard that derives status from GitHub triggers + 2-way Linear sync. OSS core + Cloud SaaS option. V1 ready for 3-5 external repos within 8-12 weeks.
```

**Description** (paste vào field Description, dùng markdown):

````markdown
## Context

2026-05-21 direction shift: MyMoneyWent fintech bot paused, Dashboard Live Tracker spun out as standalone product. See `memory/project_direction_shift_2026_05_21.md`.

## Thesis

"Humans define intent, Engine derives reality."

Linear/Jira-like UX for project tracking — but status is automatically derived from GitHub artifacts (commits, PRs, CI runs, issues, releases) and reconciled with Linear, rather than manually dragged across columns by humans.

## V1 Scope (8-12 weeks)

**UI views** (design exercise later):

* Hierarchy view: Project > Feature > Phase > Task tree
* Kanban board (status columns)
* Timeline / Gantt (phase milestones)
* Activity feed (recent GH/Linear events)

**GitHub triggers (V1):**

* Push + commit SHA polling (already in MyMoneyWent W0.9)
* PR lifecycle (open / review / merge / close)
* CI status (workflow_run + check_run)
* Issue lifecycle (open / close / label)
* Release tags + deployment status
* **Skipped:** schedule/cron polling — prefer real-time webhook

**Linear integration:**

* Hybrid 2-way sync
* Conflict-resolution model: to be proposed after API research
* Hierarchy mapping (Linear Project/Cycle/Issue → Dashboard Feature/Phase/Task): to be proposed after use-case clarification

## Monetization

Hybrid: OSS core (self-hostable, <5min setup) + Cloud SaaS option (managed, auth, billing, multi-tenant). Pattern: Supabase / Linear.

## Open questions (NOT decided)

1. Final brand name + domain (codename "WorkState" until PRD locks positioning).
2. Linear team naming — does this product need a separate Linear team (key WST) instead of reusing MYM?
3. UI tech stack (Next.js SSR vs Vite SPA vs static+HTMX).
4. Migration path: lift-and-shift `core/work_state/*` from MyMoneyWent vs fresh start vs shared package.
5. Linear sync conflict model (last-write-wins per field vs source-of-truth per field type vs pull-only).

## Repo

New repo to be spun out (not in MyMoneyWent monorepo). Migration audit in progress 2026-05-21.

## Status

In Progress. Workstreams active 2026-05-21:

* Stream B: Linear API research + sync model proposal
* Stream C: Repo spin-out plan + work-state engine migration audit
* Stream A: V1 PRD (after B + C deliver)
* Stream D: Cross-check + founder handoff
````

> Description copy-paste sẵn ở file `.migration/workstate-v1-description.md` (file riêng cho dễ paste).

---

## Bước 3 — Skip

- ❌ Project `Work-State Engine` (legacy, work đã done, không cần lịch sử)
- ❌ 11 issues `MYM-1`..`MYM-11` (đều Done, không migrate per scope decision)
- ❌ 5 milestones trong Work-State Engine (4 done + 1 Phase 2 chưa cần)

---

## Bước 4 — Verify

Sau khi xong Bước 1+2, anh báo em. Em sẽ:

1. Hướng dẫn switch Linear MCP sang `maingocanh1` (re-auth OAuth, lần này nhớ switch workspace trong OAuth page TRƯỚC khi Authorize)
2. Em verify via `list_teams` + `list_projects` → URL phải show `linear.app/maingocanh1/...`
3. Update `CLAUDE.md` + memory files (em đã chuẩn bị sẵn diff)
4. Test 1 issue dummy + branch + PR → confirm GitHub integration auto-sync hoạt động

---

## Note về auto-update flow

Sau khi setup xong:

- **Issues mới** anh tạo trong `maingocanh1` workspace, team `MyMoneyWent`, sẽ có ID `MYM-1`, `MYM-2`, ... (Linear reset count per team per workspace)
- **Branch naming**: vẫn theo convention `feat/MYM-N-slug` (CLAUDE.md hard rule + pr-validate.yml regex — không cần đổi)
- **PR body**: phải chứa `Closes MYM-N` hoặc `Fixes MYM-N`
- **Auto-sync**: PR open → issue move "In Progress"; PR merge → issue move "Done" (built-in Linear GitHub app)

> ⚠️ Cẩn thận: vì cả 2 workspace đều có team `MyMoneyWent` key `MYM`, ID issues có thể conflict (cả 2 đều bắt đầu từ `MYM-1`). Anh nên giữ một workspace là source-of-truth — khuyến nghị `maingocanh1` (active), `maingocanh` (archive read-only).
