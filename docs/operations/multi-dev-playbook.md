# Multi-Dev Playbook — MyMoneyWent

> Audience: anyone with commit access. Companion: [D-3 branch convention](#) + [dev-onboarding](dev-onboarding.md).

## Task assignment
- Devs self-serve: Linear Backlog → drag to Todo → self-assign
- Founder may assign Urgent bugs + cross-feature parents
- Linear copies branch name `<dev>/MYM-<id>-<slug>`

## WIP limit (soft)
- ≤2 issues in `In Progress` + `In Review` per dev
- Enforcement: Linear Workload view group-by-assignee, founder pings #mmw-dev if >3 active >24h

## Review rotation
- CODEOWNERS auto-requests reviewers based on touched paths
- 1 approval default
- 2 approvals required for: core/, markets/*/adapters/, ops_api/, .github/workflows/, CODEOWNERS, memory/

## Standup automation
- Daily 9am VN → Linear digest → Discord #mmw-dev (filter active cycle)
- Weekly Monday 9am → cycle summary
- Setup: see `discord-standup-setup.md`

## Concurrency hazard
STRICT 1 Claude Code / autopilot session per `.git/` (memory `feedback_concurrency_one_session`).
For parallel work: `git worktree add ../mmw-other-feature feature/x` → separate `.git/` pointers.

## Escalation
| Question | Where |
|---|---|
| Spec ambiguity | Linear comment, tag `@maingocanh` |
| Infra/CI broken | Discord `#mmw-dev` |
| Architecture | Linear Triage with `@maingocanh` |
| PR review | Tag in PR |

## Update cadence
Re-review on: new dev join, sprint retro, post-incident.
