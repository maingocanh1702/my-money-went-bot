# Branch Protection — GitHub Setup Runbook

> Founder UI work (or applied via PHASE 5 gh api automation).

## Status (2026-05-14)

**Enforcement deferred** — GitHub Free does not support branch protection
on private repos (`gh api PUT branches/main/protection` → HTTP 403
"Upgrade to GitHub Pro or make this repository public").

**Active mode: convention-only.** The rules below are the *agreed*
convention. They are NOT mechanically enforced by GitHub today. CODEOWNERS
still drives automatic reviewer assignment, and `pr-validate` still runs
as a status check (devs see ❌ in the PR UI), but neither blocks merge.

To enable enforcement later, pick one:
- Upgrade repo to GitHub Pro / Team (paid), OR
- Make repo public: `gh repo edit <owner>/<repo> --visibility public --accept-visibility-change-consequences`

Then run the PHASE 5 `gh api PUT` from `docs/autopilot/ops-tracker-dashboard/walk-away-prompt.md`.

## Settings → Branches → Add rule for `main`

| Rule | Setting |
|------|---------|
| Require PR before merge | Yes |
| Required approvals | 1 (2 for core/, markets/*/adapters/, ops_api/, .github/workflows/, CODEOWNERS) |
| Dismiss stale reviews | Yes |
| Require code owner reviews | Yes (CODEOWNERS-driven 2-approval) |
| Required status checks | `ci/pytest`, `ci/lint`, `ci/import-linter`, `pr-validate` |
| Require branches up to date | Yes |
| Restrict force-push | Yes |
| Restrict deletions | Yes |

## Rollout caution

Add `pr-validate` to required checks AFTER ≥10 PRs use new convention (avoids blocking in-flight legacy PRs).

## Linear secret rotation

`LINEAR_API_KEY` stored in GitHub repo secrets. Rotate every 6 months. Re-add via Settings → Secrets → Actions.

## Verification

Open 1 test PR matching `<dev>/MMW-NNN-...` convention → check pr-validate runs → ci-failing label appears on linked Linear when CI fails.
