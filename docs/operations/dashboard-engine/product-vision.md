---
title: WorkState — Product Vision
status: Draft
version: v0.1.0
date: 2026-05-21
author: Founder
related:
  - docs/operations/dashboard-engine/dashboard-plan-state-split.md
  - docs/operations/dashboard-engine/dashboard-live-view-plan.md
---

# WorkState — Product Vision

> **Một câu:** Project tracker mà progress tự cập nhật từ Git/GitHub/CI/Deploy — không ai phải kéo status column.

---

## Problem

Mọi project tracker hiện tại (Linear, Jira, Shortcut, Notion, Monday) đều có cùng một lỗ hổng: **status là manual**.

Developer merge PR xong → quên update ticket. PM hỏi "feature này đến đâu?" → phải mở GitHub kiểm tra. CI fail 3 ngày → ticket vẫn "In Progress". Deploy xong → phải tay set "Done".

Manual status drag là bản chất thừa hưởng từ thời physical kanban board. Nhưng năm 2026, mọi artifact đã digital — commit, PR, review, CI check, deploy log — tất cả đều có API. Status derivable từ artifacts. Không ai phải kéo.

## Thesis

> **Humans define intent. Engine derives reality.**

- **Intent** (manual): Roadmap priority, acceptance criteria, owner, deadline, dependencies
- **Reality** (derived): Status, progress %, PR state, CI state, deploy state, staleness, urgency

WorkState đọc engineering artifacts (Git branches, GitHub PRs, CI checks, deploy logs) và **tự động derive** trạng thái thật của work items. Tracker trở thành nơi plan, không phải nơi report.

## Differentiator

| | Linear / Jira / Shortcut | WorkState |
|---|---|---|
| Status source | Manual drag | Artifact-derived |
| "Is this deployed?" | Hỏi người / check manually | Engine knows (deploy signal) |
| PR merged but ticket stuck | Common — nobody updates | Impossible — auto-transition |
| CI failing 3 days | Invisible unless someone checks | Overlay `ci-failing` + urgency escalation |
| Multi-PR feature status | Single status per ticket (wrong) | Multi-branch aggregation (MIN-progressed) |

**Không thay thế** Linear/Jira — bổ sung. Linear vẫn tốt cho collaboration, sprint planning, backlog grooming. WorkState giải quyết 1 thứ mà Linear không làm: **truth from artifacts, not from people**.

## Architecture (đã ship)

```
Plan Source (tracker.md / Linear later)
  → WorkItem normalizer
    → Signal Collectors (filesystem, git, GitHub PR, CI, deploy)
      → Event Engine (diff → event → transition)
        → State Store (current_state.json + events.jsonl)
          → Projections (dashboard, kanban, digest, API...)
```

Engine đã production-ready (MYM-1 → MYM-5 shipped). Dashboard là projection đầu tiên. Architecture designed cho nhiều projections: kanban board, weekly digest, CLI, Slack/Discord/Telegram notification, REST API.

## Current State

- **Engine**: ✅ Shipped (5 signal collectors, event engine, state store, multi-branch aggregation)
- **Dashboard projection**: 🟠 Partially wired (engine output chưa render trong HTML)
- **Frontend**: ❌ Still Python-generated HTML — cần tách thành SPA
- **Product**: Internal tool cho MyMoneyWent. 1 user (founder).

## Target Users (khi productize)

1. **Solo developers / indie hackers** — dùng GitHub, không muốn maintain Jira
2. **Small teams (2-5 devs)** — đã dùng Linear/Shortcut nhưng muốn status tự update
3. **Engineering managers** — muốn dashboard reflect reality không phải "last time someone updated the ticket"

## Validation Checklist

Trước khi invest vào productize, cần validate:

- [ ] **Dogfood 30 ngày**: Engine accuracy ≥95% terminal state trên MyMoneyWent repo
- [ ] **3 external repos**: Thử engine trên 3 GitHub repos khác (variety: monorepo, multi-branch, simple)
- [ ] **3 người nói "tôi muốn dùng"**: Không phải friends being nice — người thật có pain point thật
- [ ] **1 người nói "tôi sẽ trả tiền"**: Willingness to pay = real validation
- [ ] **Architecture portable**: Engine chạy được trên repo bất kỳ mà không cần custom config >5 phút

## What NOT to Build Until Validated

- Multi-tenant SaaS infra
- Auth / user management / billing
- Mobile app
- Linear/Jira 2-way sync
- AI-powered estimation
- Full BRD / PRD / feature docs suite

## Decisions Already Made

| Decision | Rationale |
|---|---|
| Engine = Python, not Node/Go | Already shipped + tested; migration later if needed |
| `dashboard.json` = API contract | Same schema works for file-based (now) and REST API (later) |
| Frontend tách SPA trước Phase C | UI surface = product UI; Python template ≠ product |
| No full BRD/PRD now | 1 user, unvalidated product — overhead > value |
| Plan source stays markdown | Linear integration = optional future projection, not dependency |

---

*Last updated: 2026-05-21. Update khi validation checklist có item checked.*
