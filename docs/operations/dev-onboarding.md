# Dev Onboarding — MyMoneyWent

> Target: first PR open day 1, merged within 3 days.

## 1. First-day setup (30 min)

### Access
- [ ] Linear invite (founder → Settings → Team → Members)
- [ ] GitHub collaborator on `MyMoneyWent` repo
- [ ] Discord `#mmw-dev`

### Local
```bash
git clone git@github.com:<owner>/MyMoneyWent.git
cd MyMoneyWent
make setup            # .venv + deps + pre-commit
make install-hooks    # pre-push branch-name hook
source .venv/bin/activate
pytest tests/ -v      # MUST be green
```

### Linear orientation
- Workspace: MyMoneyWent, Team: Engineering
- Views: MVP Tracker, Backlog, Current Cycle, Workload, Blocked
- Starter task: founder marks 1-2 issues `good-first-issue`

## 2. Workflow cheat sheet

### Pick a task
1. Linear Backlog → filter `good-first-issue` (week 1)
2. Verify required fields filled (Phase, Feature, Priority, Acceptance criteria)
3. Drag to **Todo** → self-assign
4. Click **Copy git branch name** → e.g. `your-handle/MYM-42-task-slug`
5. `git checkout main && git pull && git checkout -b your-handle/MYM-42-task-slug`

### During work
- Small atomic commits, present-tense imperative (`feat:`, `fix:`, `docs:`, `test:`)
- Linear status auto-syncs when first commit pushed
- WIP ≤2 issues active (playbook §WIP)

### PR
- Use PR template auto-filled
- **Required**: `Closes MYM-42` in body
- DoD: CI green + ≥1 approval + Linear auto-`Done` on merge

## 3. Conventions (deep links)
- Branch + PR → §D-3 + `.github/pull_request_template.md`
- Multi-dev workflow → [multi-dev-playbook.md](multi-dev-playbook.md)
- Memory rules → [MEMORY.md](../../MEMORY.md)

## 4. Where to ask
| Question | Where |
|---|---|
| Spec | Linear comment, `@maingocanh` |
| Infra/CI | Discord `#mmw-dev` |
| Architecture | Linear Triage, `@maingocanh` |
| Founder review | Tag PR |

## 5. First-PR path
1. Pick `good-first-issue`
2. Target: **merged in 3 days** (validates workflow end-to-end)
3. After merge: brief reflection in `#mmw-dev` — what was unclear?
