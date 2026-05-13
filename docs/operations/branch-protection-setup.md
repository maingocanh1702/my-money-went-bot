# Branch Protection — GitHub Setup Runbook

> Founder UI work (or applied via PHASE 5 gh api automation).

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
