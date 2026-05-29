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
