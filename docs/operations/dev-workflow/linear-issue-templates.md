# Linear Issue Templates — Specifications

> Founder pastes into Linear (Settings → Team → Templates). Or use D-5-templates automator for API create.

## Template 1: Feature

**Title placeholder:** `[F##] <feature summary>`
**Required fields:** Phase, Feature ID, Priority, Risk Tier (if DB/security/payment), Spec link, Acceptance criteria

**Body template:**
```
## Goal
<One sentence: user problem this solves>

## Spec
Link: <docs/features/feature-<id>.md or BRD/PRD>
Version: <vX.Y.Z>

## Acceptance criteria
- [ ] <Testable behavior 1>
- [ ] <Tests added>
- [ ] <Docs updated if API/contract>

## Out of scope
- <Non-goal 1>

## Dependencies
- <Linear ID or "none">
```

## Template 2: Bug

**Title:** `[BUG] <observed behavior>`
**Required:** Phase, Priority, Severity, Risk Tier (if applicable)

**Body:**
```
## Repro steps
1. <Step 1>

## Expected
<What should happen>

## Actual
<What happens>

## Affected version / SHA

## Logs / screenshots

## Acceptance criteria
- [ ] Repro no longer reproduces
- [ ] Regression test added
- [ ] Root cause in PR body
```

## Template 3: Chore

**Title:** `[CHORE] <scope>`
**Required:** Phase, Priority

**Body:**
```
## Scope

## Why now

## Impact if not done

## Acceptance criteria
- [ ] <Completion signal>
- [ ] Tests still pass
- [ ] No behavior change
```

## Template 4: Docs

**Title:** `[DOCS] <doc / section>`
**Required:** Phase, Priority, Affected doc

**Body:**
```
## Doc affected

## Section(s)

## What changes
<Add / update / delete / restructure>

## Audience

## Why

## Acceptance criteria
- [ ] Doc updated
- [ ] Cross-refs updated (grep repo)
- [ ] Memory updated if conventions changed
```
