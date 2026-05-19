---
title: Codex Review Prompt — Work-State Engine Spec v1.2.0
purpose: Cross-model review prompt cho dashboard-plan-state-split.md (Foundation Lane P0)
status: Completed — historical artifact (review conducted 2026-05-19 → 2026-05-20)
date: 2026-05-19
updated: 2026-05-20
author: Founder + Claude
review_target:
  - docs/operations/dashboard-plan-state-split.md (v1.2.0 at review time → now v1.2.1 Accepted, 1490 lines)
  - docs/operations/linear-and-dashboard-workflow.md (v1.1.0, 654 lines, EXPLAINER context)
  - docs/operations/walkthrough-foundation-lane-example.md (v1.0.0 at review time → now v1.0.1)
review_outcome:
  - Round 1 (2026-05-19): 15 findings (10 MAJOR + 5 MINOR), APPROVE WITH CHANGES → resolved
  - Round 2 (2026-05-19): 7 findings (4 MAJOR + 3 MINOR), APPROVE WITH CHANGES → resolved (regression cleanup)
  - Round 3 (2026-05-20): 1 finding (1 MAJOR), APPROVE WITH CHANGES → resolved
  - Final: Spec v1.2.1 Accepted, founder sign-off 2026-05-20 (per CLAUDE.md hard rule #6)
---

# Codex Review Prompt — Work-State Engine Spec v1.2.0 (HISTORICAL)

> **⚠️ Historical artifact — review complete.**
> This prompt was used for Codex cross-model review of spec at version v1.2.0 (2026-05-19).
> 3 rounds executed, all 23 findings resolved, spec bumped to v1.2.1 + founder sign-off 2026-05-20.
> Kept for audit trail. Live spec status: `docs/operations/dashboard-plan-state-split.md` §17.
> For future Codex review of next spec version, create new prompt artifact với version suffix matching.

**Lane:** Foundation / P0
**Spec status (at review time):** Proposed · Awaiting cross-model review
**Spec status (current):** Accepted (Founder sign-off 2026-05-20, v1.2.1)
**MMW hard rule #5:** P0/Foundation requires cross-model review trước founder approval — ✓ fulfilled

---

## How to use

1. Mở Codex CLI hoặc Claude Code session **không phải session viết spec** (cross-model = khác model + khác session)
2. Paste toàn bộ prompt dưới đây vào prompt
3. Codex sẽ đọc 3 file + return findings
4. Founder triage findings → address theo round cap Foundation Lane (max 8 round)

---

## Codex prompt — paste from below

```
You are reviewing a Foundation Lane (P0) spec for the MyMoneyWent project.

ROLE
You are a critical cross-model reviewer. The spec author (Claude) wrote this
and you (Codex) are the independent second opinion required by MMW hard rule #5
before founder approval.

REVIEW SCOPE
Primary spec to review:
  docs/operations/dashboard-plan-state-split.md (v1.2.0, ~1076 lines)

Sister docs for context (read but review focus is on primary spec):
  docs/operations/linear-and-dashboard-workflow.md (v1.1.0, explainer)
  docs/operations/walkthrough-foundation-lane-example.md (v1.0.0, P0 example)

Background context (read to understand MMW conventions):
  CLAUDE.md — project rules, hard rules #1-#9
  docs/operations/dashboard-realtime-explained.md — current dashboard infra
  docs/operations/fast-quality-workflow.md — 3-lane risk-based workflow
  .github/workflows/pr-validate.yml — branch + PR conventions
  scripts/build-dashboard.py — existing build pipeline

VERSION HISTORY (for context, not review target):
  v1.0.0 — Initial proposal: dashboard plan/state split
  v1.1.0 — Reframe to auto-progress work engine + WorkItem schema + event log
  v1.1.1 — Hardening: CI persistence + cache invalidation + priority/risk_tier separation
  v1.2.0 — Artifact-driven feedback integration: human status projection, runtime urgency

REVIEW CATEGORIES — please cover ALL 10 categories, even briefly

A. Architectural soundness
   - Is Plan/State boundary clean? Any field that crosses boundary?
   - Does engine module separation (scripts/work_state/) make sense for v1?
   - WorkItem schema (Section 4 + 11.2 dataclass): covers real MMW use cases?
   - Source-of-truth boundary table (§5.2): any concern listed wrong?
   - Anti-pattern check: does dashboard projection accidentally own business logic?

B. State machine correctness
   - compute_status() first-match priority (§8.1): order correct?
   - Are state transitions complete? Any orphan/unreachable state?
   - Overlay vs base status (§8.2): semantics consistent?
     Specifically: should `ci-failing` be base or overlay? Spec says overlay — agree?
   - Human status projection (§8.0): mapping right?
   - Multi-branch aggregation (§4.1): MIN-progressed rule — does it hide reality
     in edge cases like "1 PR deployed + 1 PR ci-failing" or "1 PR blocked + 1 PR merged"?
     Suggest deterministic matrix if needed.

C. Signal definitions (§6)
   - PR identity resolution (§6.3): 5-step fallback robust enough?
   - CI state (§6.6): "required checks for head SHA" — what if no PR exists yet
     and branch has commits + check runs? Spec covers this — verify.
   - Deploy state (§6.7): `unknown` allowed — but how does engine signal
     "we genuinely don't know vs we think not-deployed"? Distinct UI states?
   - Filesystem signals: `missing_spec_link` warning — what if spec exists at
     non-canonical path? Engine assumes one canonical path only.

D. Event model (§7)
   - Event log dedup at write time with 24h window (§7.2): could miss legitimate
     repeated events? E.g., same CI re-run within 24h producing same `ci_passed`
     event — should that dedup or not?
   - Persistence strategy local vs CI (§7.4): `actions/cache` key includes
     branch — what about cross-branch event history (e.g., main events)?
   - State cache invalidation (§7.5): force_pr_resolve flag — where does it
     live (tracker.md row? CLI flag?)? Spec ambiguous.

E. Progress model (§9)
   - Profile weights (§9.1) are heuristic — calibration plan (§9.3) addresses,
     but: should v1 ship ANY non-default weights, or just track milestones
     reaching without %? Trade-off between false precision vs useful signal.
   - `dashboard_engine` profile reuses `foundation_change` — explicit copy or
     inheritance? Edge case: when both apply, which wins?
   - Phase progress rollup (§9.2): simple average — but if 1 P0 item failing
     drags whole phase number down to look healthy, misleading?

F. Runtime urgency model (§9.4)
   - 4 levels (normal/warning/elevated/critical): clear thresholds?
   - Examples table: deterministic or judgement-based? Engine code needs
     determinism — spec doesn't show derivation algorithm.
   - Interaction with overlays: if `stale` overlay + active CI fail, urgency
     should be `elevated` or `critical`? Combination rule unclear.

G. Migration plan (§10) + AC (§13)
   - Phase 0-3 gates concrete (≥95% terminal accuracy, 2-week stable)?
   - Rollback path tested? §15 runbook has `git revert HEAD` + tracker .bak
     restore — but if engine has been writing to .dashboard/ for weeks, what
     happens to events.jsonl? Just orphaned?
   - AC1a-AC1g sub-bullets: each verifiable independently?
   - AC15: "critical misclassification" not defined — what counts as critical?
   - AC list complete? Any hidden requirement not captured (e.g., Sentry
     instrumentation for engine errors, docs update for stakeholders, …)?

H. MMW-specific compatibility
   - Aligns with CLAUDE.md hard rules #1-#9 explicitly?
   - Wave 0 decisions respected (founder=id=1 bootstrap, etc.)?
   - Compatible with current `scripts/build-dashboard.py` — refactor not rewrite?
   - Linear convention `MYM-NNN` honored in plan_reader?
   - `pr-validate.yml` exempt prefixes interaction: what status do branches like
     `fix/*` (exempt) get when they don't have a tracker row?

I. Implementation feasibility
   - Effort estimate (§16): 6-8 work days + 2.5-3 weeks calendar — realistic for
     solo founder + AI augment? Consider Phase 1 has 6+ signal collectors to
     build, each unknown-safe.
   - GitHub API rate budget: 40 calls/build × 50 builds/day = 2000/day. Safe vs
     5000/hr authed. Burst risk during PR sync events (5-10 builds in 5 min)?
   - Test categories cover real risks: PR closed unmerged, branch deleted,
     squash merge cache, API unavailable, missing spec, CI fail, stale PR,
     manual override expiry. Any missing?
   - Build latency: current ~2s, post-engine est. 5-10s. Acceptable for CI
     triggers but could degrade pre-commit hook UX. Mitigated by --no-network?

J. Scope discipline
   - Non-goals (NG1-NG5): appropriate?
   - Open questions Q1-Q6: well-framed and answerable?
   - Phase 4 deferral (Linear sync) justified?
   - Anything in spec that should NOT be in v1 (over-engineering risk)?

OUTPUT FORMAT
For each finding, provide:

```
[Finding N · SEVERITY · CATEGORY]
File: <path>:<line range>
Issue: <1-2 sentence description>
Why it matters: <consequence if shipped as-is>
Recommendation: <specific change, or "needs discussion" if unclear>
```

SEVERITY scale:
  BLOCKER — must fix before merge (correctness, security, contradicts hard rule)
  MAJOR — should fix before merge (significant gap, scope unclear, ambiguous)
  MINOR — nice to fix (clarity, completeness, minor inconsistency)
  NIT — taste / wording (optional)

OVERALL VERDICT
At the end, give one of:
  APPROVE — ship as-is, minor/nit only
  APPROVE WITH CHANGES — major fixes required but no blockers
  REQUEST CHANGES — 1+ blocker exists, hold merge
  HOLD — fundamental concerns, return to drawing board

PRIORITIES TO FOCUS ON

1. Internal consistency — every claim in spec backed by another section?
   E.g., overlay list in §8.2 == §10 Phase 2 == AC10? Field in §3 boundary
   table all match WorkItem dataclass §11.2 or CurrentState?

2. Edge case coverage — find scenarios spec doesn't address:
   - Multi-PR compound states (1 deployed + 1 blocked, etc.)
   - Race conditions (cache + concurrent build)
   - State transitions that can't happen (orphan states)

3. Implementation risk — flag anywhere spec is too abstract for engineer to
   implement without re-reading multiple times or guessing.

4. MMW-specific gotcha — anywhere spec assumes generic SaaS pattern but MMW
   has specific decision (Wave 0, F07 lessons, family plan, etc.).

DO NOT
- Rewrite the spec — your job is review, not authoring
- Question the foundational architecture decision (plan/state split) — that's
  resolved by founder
- Suggest scope expansion — v1.2.0 already expanded scope twice, focus on
  shipping what's there cleanly

Begin review now. Take your time, this is Foundation Lane critical-path work.
```

---

## Round expectation

Per Foundation Lane (CLAUDE.md hard rule #8):
- Max 8 rounds
- Founder approval gate after round 5

Realistic estimate:
- Round 1: 5-15 findings (mostly MINOR + MAJOR, possibly 1-2 BLOCKER)
- Round 2: address findings, re-submit
- Round 3-4: refinement
- Likely converge by round 3-4 if scope holds

---

## After Codex review

1. **Triage findings** by severity:
   - BLOCKER → must address, no exception
   - MAJOR → address unless explicit founder override with reason
   - MINOR → address if low effort, defer to v1.2.1 otherwise
   - NIT → optional

2. **Apply fixes** as in-session edits (per memory `feedback_spec_versioning.md`
   — không bump version mỗi round). After ALL rounds done, bump to v1.3.0
   với changelog entry tổng hợp.

3. **Founder sign-off** sau khi Codex approve:
   - Per `walkthrough-foundation-lane-example.md` §6: sign-off comment trong PR body
   - AC: met / which deferred + why, blast radius, known tradeoffs

4. **Promote spec status**: Proposed → Accepted khi founder sign-off

---

## Notes for Codex (if reading this directly)

This prompt was crafted by Claude (the original spec author). Treat it as a
self-aware request for adversarial review — Claude knows it has blind spots
and is explicitly asking you to find them. Be direct, be specific, cite file:line.
The founder will triage your findings — your job is comprehensive coverage of
the 10 categories, not consensus building.

If you find the spec well-designed in some area, say so explicitly with a
1-line "this area looks solid" — silence on a category will be read as
"category not reviewed" rather than "category fine".
