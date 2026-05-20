---
title: Phase 0 audit report — Work-state engine kickoff
status: Complete
version: v1.0.0
date: 2026-05-20
author: Founder + Claude
related:
  - docs/operations/dashboard-plan-state-split.md (v1.2.1, Accepted)
  - docs/implementation-tracker.md
  - .gitignore
  - .github/workflows/
---

# Phase 0 audit report — Work-state engine kickoff

> **Status:** Complete — Phase 1 unblocked
> **Date:** 2026-05-20
> **Scope:** Pre-implementation audit per `dashboard-plan-state-split.md` v1.2.1 §10 Phase 0
> **Outcome:** Tracker schema gaps mapped, defaults strategy locked, `.gitignore` action identified, decisions confirmed.

---

## 0. Phase 0 exit criteria checklist (spec §10)

| Exit criterion | Status | Detail |
|----------------|--------|--------|
| Every tracker row normalizes into `WorkItem` | ⚠️ Partial — engine needs defaults strategy | Tracker schema 7 columns vs WorkItem 18 fields. Plan_reader sẽ infer 10+ fields với warnings. See §2. |
| Missing optional fields explicit `null` không silent absent | ⚠️ Requires `plan_reader.py` enforce | Current tracker dùng Notes free-form cho dependencies/acceptance/external_blockers. Engine sẽ parse best-effort + emit warnings. |
| `gh` CLI / GitHub REST availability confirmed | ✅ | `gh` pre-installed on `ubuntu-latest` (workflow `linear-status-sync.yml` already uses). No setup needed. |
| `.dashboard/` runtime-only decision | ✅ | Decision: runtime-only (per spec recommendation Q2). Action: add to `.gitignore` (§5). |
| `current_state.json`/`events.jsonl` runtime vs committed | ✅ | Decision: runtime-only. `docs/dashboard.json` remains committed public projection. |

**Verdict:** Phase 0 complete. Phase 1 unblocked with caveats (defaults strategy required cho plan_reader, `.gitignore` edit needed).

---

## 1. Current tracker state

`docs/implementation-tracker.md` snapshot 2026-05-20:

- **Total rows:** 46 work items (Phase 1 → Phase 6)
- **Naming convention:** 100% kebab-case (legacy F-code migration done 2026-05-15)
- **Schema:** 7 columns — `PR | Wave | Feature | Status | Branch | Gates | Notes`
- **Format:** GitHub-flavored markdown table, section grouped by Phase
- **Status emojis:** 7 states (⬜ 🟡 🟠 🟢 ✅ ❌ ⏸️)
- **Gate flags:** 4 binary flags (🔒T, 🔒I, 🔒M, 🔒X) — implicit lane indicator

Sample row (Phase 2 `funding-sources`):

```markdown
| funding-sources | Wave 2 | Funding sources resolver + handlers | ⬜ | `feat/funding-sources` | 🔒T 🔒I 🔒X | DDL landed W0.2 → only service + handler logic |
```

---

## 2. Schema gap analysis — Tracker vs WorkItem dataclass

Cross-reference: spec §11.2 WorkItem dataclass requires 18 fields. Tracker provides 7.

### 2.1 Fields present in tracker

| WorkItem field | Tracker source | Notes |
|----------------|----------------|-------|
| `id` | PR column | E.g., `funding-sources`, `W0.9` — stable internal ID ✓ |
| `feature_id` | PR column | Same as id for kebab rows; W*.x rows use code as id, no separate feature_id ⚠️ |
| `title` | Feature column | ✓ |
| `branches` | Branch column | Single branch per row (no multi-PR support in current schema) ⚠️ |

### 2.2 Fields missing from tracker — engine must infer or default

| WorkItem field | Default strategy | Warning emitted? |
|----------------|------------------|------------------|
| `linear_id` | None if id không match `MYM-NNN` pattern; else id itself | `missing_linear_id` if branches exist + PR active |
| `type` | Infer: `W*` → `infra`, kebab → `feature`. Manual override via future YAML extension | `type_inferred` (annotation) |
| `phase` | Section header context (parse `### Phase N:` heading above row) | None (deterministic) |
| `priority` | Default `P1` (mid-tier). Manual override via future YAML extension | `priority_defaulted` |
| `risk_tier` | Infer from gates: 🔒T+🔒I+🔒M+🔒X = `P0`; 🔒T+🔒X = `P1`; 🔒X only = `P2` | `risk_tier_inferred` |
| `lane` | Infer from risk_tier: P0 = `Foundation`; P1 = `Standard`; P2 = `Fast` | (inherited from risk_tier) |
| `owner` | Default `founder` | None (assumed) |
| `deadline` | None | None (optional field) |
| `specs.product` | Glob `docs/features/feature-{feature_id}.md` | `missing_spec_link` if file not found |
| `specs.tech` | Glob `docs/features/BE/feature-{feature_id}-tech.md` | `missing_tech_link` if file not found |
| `acceptance` | Best-effort parse from Notes column (regex `acceptance:` heading) | `acceptance_unstructured` if no parseable AC |
| `dependencies` | Best-effort parse from Notes (regex `depends on:`, `blocks:`, `unblock`) | `dependencies_unstructured` |
| `external_blockers` | Best-effort parse from Notes (regex `blocker:`, `waiting for`) | `external_blockers_unstructured` |
| `decision_needed` | None | None (optional) |
| `progress_profile` | Infer: `W*` rows → `foundation_change`; kebab feature → `standard_feature`; docs/research rows → `docs_only` | `progress_profile_inferred` |
| `manual_state_override` | None | None (optional) |

### 2.3 Sample inference run — funding-sources row

```yaml
# Inferred WorkItem cho row `funding-sources` (manual fields shown; ⚠ = inferred)
id: funding-sources
linear_id: null                              # ⚠ no MYM-NNN; warning missing_linear_id (branches exist)
feature_id: funding-sources
title: Funding sources resolver + handlers
type: feature                                # ⚠ inferred from kebab pattern
phase: 2                                     # ✓ parsed from section header
priority: P1                                 # ⚠ defaulted; warning priority_defaulted
risk_tier: P1                                # ⚠ inferred from gates 🔒T+🔒I+🔒X (matches P1)
lane: Standard                               # ⚠ inherited from risk_tier
owner: founder                               # ⚠ default
deadline: null
specs:
  product: docs/features/feature-funding-sources.md  # ⚠ glob — verified exists by spec
  tech: docs/features/BE/feature-funding-sources-tech.md
branches:
  - feat/funding-sources                     # ⚠ single-branch; multi-PR would need YAML
acceptance:
  - "DDL landed W0.2 → only service + handler logic"  # ⚠ unstructured from Notes
dependencies: []                             # ⚠ Notes mentions W0.2 but engine doesn't link
external_blockers: []
decision_needed: null
progress_profile: standard_feature           # ⚠ inferred
manual_state_override: null
```

Engine warnings cho row này: 8 warnings (5 `*_inferred`, 1 `acceptance_unstructured`, 1 `dependencies_unstructured`, 1 `missing_linear_id`). Render trên dashboard với `risk-tier-inferred` overlay annotation (per §8.2 canonical enum).

---

## 3. Per-row audit summary

Rough count by category (46 total rows):

| Category | Count | Engine handling |
|----------|-------|-----------------|
| Merged (✅) | 7 | History rows, no active inference needed. Render `DONE`. |
| Not started (⬜) | 32 | Full inference per §2.2; all warnings apply |
| Deferred (⏸️) | 5 | Render `ABANDONED` (per §8.0). `Phase 5b` parser deferrals + Phase W. |
| In progress / review / blocked | 2 | Engine derives from artifacts; minimal manual gating |

Concrete inferred rows worth flagging early:

- `W0.7`, `W0.8`, `W0.9`, `W0.10`, `onboarding-start`, `settings`, `webhook-display-suffix-migration` (Merged Phase 1-2) — 7 done, mostly history
- `funding-sources`, `transaction-capture`, `manual-transaction-entry`, `category-management`, `categorization`, `reports`, `admin-auth`, `i18n-locale-switcher`, `pricing-tiers`, `sepay-onboarding-paths`, `first-tx-celebration` — Phase 2-4 active backlog
- `parser-acb`, `parser-sacombank`, `parser-bidv` — Phase 5b deferred
- `(to be created when Phase W enters implementation planning)` — placeholder row, engine sẽ skip with warning `placeholder_row`

---

## 4. Decisions locked

### 4.1 `.dashboard/` persistence — runtime-only ✓

Per spec Q2: `current_state.json` + `events.jsonl` ignored by git. CI persists via `actions/cache` per spec §7.4.1.

**Action:** Add `.dashboard/` entry to `.gitignore`.

### 4.2 `docs/dashboard.json` — committed public projection ✓

Per spec §7.4 table row 3 + Q2. Continues current behavior (already committed). Engine projects `current_state.json` → `dashboard.json` on each build.

### 4.3 `gh` CLI — available in CI ✓

Verified: `ubuntu-latest` pre-installs `gh`. Existing workflow `linear-status-sync.yml` uses it. No additional `setup` step needed in `dashboard.yml` triggers.

Local dev: founder needs `gh` installed. Already required for current MMW workflow (per CLAUDE.md). No action.

### 4.4 Tracker schema migration — DEFER ✓ (Phase 1 plan_reader infers)

Per spec Q1 recommendation: keep markdown tracker as v1 plan source, normalize internally so source can change later.

**Decision:** Do NOT migrate tracker.md to YAML or extend with 10+ new columns trong Phase 0. Instead:

- `plan_reader.py` (Phase 1) implements defaults strategy §2.2
- Each inferred field emits warning code (snake_case) per §8.2.1 naming convention
- Warnings roll up to dashboard overlay `risk-tier-inferred` (annotation, no urgency change)
- Founder can override inference by adding YAML companion file `docs/work-items.yml` post-Phase 3 (per spec Q1 future direction)

**Trade-off:** Phase 1 engine starts với "fuzzy" data — dashboard shows many `*_inferred` warnings initially. Acceptable per spec shadow mode philosophy.

### 4.5 Foundation milestone signal conventions — open for Phase 1

Per spec §9.1 + AC11c: `foundation_change` profile needs detectable artifact for:
- "cross-model review approved" → PR review label `codex-approved` OR comment marker `[Codex Review · APPROVE]`
- "founder sign-off" → PR comment marker `Foundation Lane founder approval:`

**Action deferred to Phase 1 implementation:** signal_collectors/github.py implements detection. No founder convention change needed pre-Phase 1.

### 4.6 Multi-branch tracker rows — current schema unsupported

Tracker `Branch` column is single string. Spec WorkItem requires `branches: list[str]`. 4 transaction-capture related rows could in theory split:

- `transaction-capture` (single branch row currently)
- `manual-transaction-entry` — separate row, separate branch

**Decision:** Phase 1 plan_reader treats `branches` as `[Branch column]` single-element list. Multi-PR features (if any in future) require either:
- (a) Split into separate work item rows (preferred per spec §4.1 strong recommendation)
- (b) Add YAML companion entry override (post-Phase 3)

No tracker change needed pre-Phase 1.

---

## 5. Concrete actions for Phase 1 kickoff

### 5.1 Required before Phase 1 starts

**Action 1:** Add `.dashboard/` to `.gitignore`

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
# Add line after "# Autopilot orchestrator state":
echo "" >> .gitignore
echo "# Work-state engine runtime state (per dashboard-plan-state-split.md §7.3)" >> .gitignore
echo ".dashboard/" >> .gitignore
git add .gitignore
git commit -m "chore(gitignore): add .dashboard/ runtime state (Phase 0 audit)"
```

**Action 2:** Open Linear ticket cho engine implementation Phase 1a

```
Title: Work-state engine Phase 1a — Core engine + filesystem + git collectors
Type: feature
Priority: P0
Risk tier: P0
Lane: Foundation
Cycle: Phase 2 (carry-over)
Description: Implement scripts/work_state/ skeleton per dashboard-plan-state-split.md
  v1.2.1 §10 Phase 1a. Scope: models.py + plan_reader.py + event_engine.py +
  status_machine.py + progress.py + state_store.py + filesystem.py + git.py
  collectors. ~2 days work + unit tests.
Acceptance: AC1a + AC1b + AC1c (filesystem + git subset) + AC2 + AC3 + AC4 + AC11d
Linked spec: docs/operations/dashboard-plan-state-split.md (Accepted v1.2.1)
```

→ Assigned ID becomes `MYM-NNN`. Tracker row gets added.

**Action 3:** Add tracker row cho engine work itself

```markdown
| PR | Wave | Feature | Status | Branch | Gates | Notes |
| work-state-engine-1a | Wave 2+ | Work-state engine Phase 1a (core + filesystem + git) | ⬜ | `feat/MYM-NNN-work-state-engine-1a` | 🔒T 🔒I 🔒X | Engine kickoff per dashboard-plan-state-split.md v1.2.1 Accepted. P0/Foundation. Spec §10 Phase 1a scope. |
```

### 5.2 Nice-to-have (not blocking Phase 1)

- Update CLAUDE.md "Source of truth" table sau Phase 3 cutover (per AC16) — defer
- Linear cycle assignment cho Phase 1a ticket — founder ad-hoc
- `docs/work-items.yml` companion file — defer post-Phase 3

---

## 6. Risks identified during audit

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Plan_reader default inference produces noisy dashboard initially (8+ warnings/row × 46 rows = ~370 warnings) | High | Medium | Phase 1 shadow mode tolerates noise; Phase 2 promotion requires <5% misclassification per AC15. Founder filters dashboard by `risk-tier-inferred` overlay to surface real status. |
| Notes free-form parsing fragile (acceptance/dependencies/blockers) | High | Low | Warnings + best-effort. Founder can structure Notes nếu engine misses something important. |
| Specs glob may match wrong file (e.g., feature-funding vs feature-funding-sources fuzzy) | Low | Medium | Spec §6.1 uses exact path first; glob only as `possible_spec_moved` fallback. False match → founder reconciles. |
| Tracker schema rewrite mid-Phase 1 changes plan_reader expectations | Medium | Medium | Audit locks current schema. Any tracker schema change post-Phase 0 = new PR + Codex review + plan_reader update. |
| Foundation milestone markers (codex-approved, founder sign-off) lack convention enforcement | Medium | Medium | Phase 1 ticket includes convention documentation. PR template addition deferred to Phase 1 implementation. |

---

## 7. Phase 0 → Phase 1 handoff

**Hand-off package cho Phase 1 implementer (founder + autopilot):**

1. ✓ Spec v1.2.1 Accepted (Codex 3 rounds + founder sign-off)
2. ✓ This audit report — defaults strategy + decisions locked
3. ✓ `.gitignore` updated (after Action 1 executed)
4. ✓ Linear ticket opened (after Action 2 executed)
5. ✓ Tracker row added (after Action 3 executed)

**Phase 1a deliverables (per spec §10 Phase 1a, 2 days work):**

- `scripts/work_state/models.py` — WorkItem, Signals, CurrentState, Event dataclasses (AC1a)
- `scripts/work_state/plan_reader.py` — tracker normalization với defaults strategy §2.2 above (AC1b)
- `scripts/work_state/event_engine.py` — signal diff → events (AC1d)
- `scripts/work_state/status_machine.py` — compute_status(signals) → Status (AC1e)
- `scripts/work_state/progress.py` — profile-based progress (AC1f)
- `scripts/work_state/state_store.py` — `.dashboard/` JSON IO
- `scripts/work_state/signal_collectors/filesystem.py` — spec_exists + tech_exists + possible_spec_moved (AC1c subset)
- `scripts/work_state/signal_collectors/git.py` — branch_exists + commits_count + last_commit_sha (AC1c subset)
- Unit tests covering state transitions + 5 categories per Wave 0 lessons

**Phase 1b + 1c sub-tickets opened sau Phase 1a verified working.**

---

## 8. Sign-off

Phase 0 audit complete. All 5 exit criteria addressed (3 ✓ + 2 ⚠️ with documented mitigation).

Phase 1 unblocked. Founder can start engine implementation via:
- Manual approach: open Linear ticket + branch + code
- Autopilot approach: draft prompt per `docs/operations/autopilot-prompt-template.md` referencing spec §10 Phase 1a

— Founder, 2026-05-20

---

## Changelog

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| v1.0.0 | 2026-05-20 | Founder + Claude | Initial Phase 0 audit. 5 exit criteria checked. Tracker schema gap mapped (7 vs 18 fields). Defaults strategy locked: plan_reader infers 10+ fields with warnings, no tracker schema migration pre-Phase 1. `.gitignore` action identified. `gh` CLI confirmed pre-installed. Linear ticket + tracker row for Phase 1a engine work prepared (founder executes Actions 1-3). |
