# Walk-Away Mega-Prompt — Multi-Dev Linear Automation

You are an autopilot coding agent working in `/Users/maingocanh/Projects/MyMoneyWent` on MyMoneyWent (personal finance bot). Execute ALL 6 phases below end-to-end in this single session. Do NOT stop until either all phases are COMPLETE or a halt condition fires with reason.

## Mode + Risk Header

- Mode: AUTOPILOT FULL-AUTO MEGA — single session, multi-phase, auto-squash + push after each phase
- Risk tier: P1 (CI auth + branch protection) — exception per memory `project_ops_tracker_full_auto_exception` (2026-05-13)
- Codex review: 1× clean per phase (compressed from 2× P1 standard per batch exception)
- Stop conditions: ANY HALT in §Halt-Rules fires, OR all 6 phases complete

## Mandatory Task Checklist (DO NOT SKIP — emit progress between phases)

After completing each phase, you MUST emit this exact line to stdout:
```
✅ PHASE <N> COMPLETE — <phase-id> merged to main as <SHA>. Moving to PHASE <N+1>.
```

If you skip a phase or finish without all 6 checkmarks, the run is INCOMPLETE.

```
[ ] PHASE 0 — Bootstrap: commit pre-existing infrastructure if dirty
[ ] PHASE 1 — D-3: Branch + PR convention + pre-push hook + ci/pr-validate
[ ] PHASE 2 — D-4: CODEOWNERS + multi-dev playbook + Discord standup runbook
[ ] PHASE 3 — D-5: Dev onboarding doc + Linear issue templates (created via API)
[ ] PHASE 4 — D-6: linear-status-sync.yml + helper + branch-protection runbook
[ ] PHASE 5 — D-6-protect: Apply GitHub branch protection (inline gh api)
```

---

## Global Pre-Flight (run ONCE before any phase)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null && echo "FAIL: stale git locks" && exit 1
git status
git branch --show-current   # MUST: main
git fetch origin && git pull --ff-only origin main || { echo "FAIL: pull"; exit 1; }
source .venv/bin/activate
which python git gh codex   # all MUST resolve (codex optional — note if missing)
# Env:
echo "AUTOPILOT_NO_VERIFY=$AUTOPILOT_NO_VERIFY (1 = skip pre-commit hooks on squash)"
echo "LINEAR=${LINEAR_API_KEY:+set len=${#LINEAR_API_KEY}}"
echo "GITHUB=${GITHUB_TOKEN:+set} (or gh CLI authed)"
echo "TEAM=${LINEAR_TEAM_NAME:-MyMoneyWent}"
```

Required env (else HALT):
- `LINEAR_API_KEY` — Linear personal API key
- `LINEAR_TEAM_NAME` — defaults `MyMoneyWent`
- `gh auth status` — must show authenticated (for PHASE 5)
- `claude --version` — Claude Code installed (this prompt invoked it)

If any required check fails: emit HALT report per §Halt-Rules, stop.

---

## Squash Helper (use after each phase's Codex pass)

For phases 1-5 (PHASE 0 has its own bootstrap commit):

```bash
# At end of each phase, you've made commits on feature branch <BRANCH>
git checkout main
git fetch origin main
git pull --rebase origin main || { echo "HALT: pull --rebase failed"; exit 1; }
git merge --squash <BRANCH>
COMMIT_MSG="<phase-specific squash message>"
NO_VERIFY=""
[ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "$COMMIT_MSG"
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push failed"; exit 1; }
git branch -D <BRANCH>
echo "✅ PHASE <N> COMPLETE — <phase-id> merged to main as $SHA. Moving to PHASE <N+1>."
```

---

# PHASE 0 — Bootstrap (commit pre-existing infra if dirty)

**Goal:** If `git status` shows uncommitted autopilot infrastructure files (scripts/autopilot_*.py, docs/autopilot/, .gitignore updates), commit them with --no-verify so subsequent phases have clean pre-flight.

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$DIRTY" -gt 0 ]; then
  # Add only autopilot-related files
  git add docs/autopilot/ 2>/dev/null || true
  git add scripts/autopilot_runner.py scripts/autopilot_agent.py scripts/autopilot_manual_automators.py 2>/dev/null || true
  git add .gitignore 2>/dev/null || true
  STAGED=$(git diff --cached --stat | wc -l | tr -d ' ')
  if [ "$STAGED" -gt 0 ]; then
    git commit --no-verify -m "feat(autopilot): pre-existing infrastructure commit (bootstrap step)

Per memory feedback_autopilot_bootstrap_step: commit autopilot infra
before any prompt run. --no-verify due to intentional subprocess + urlopen
in orchestrator code."
    git pull --rebase origin main || { echo "HALT: bootstrap pull"; exit 1; }
    git push origin main || { echo "HALT: bootstrap push"; exit 1; }
  fi
  # Any leftover unstaged changes that aren't autopilot files: stash with marker, leave for founder review
  REMAIN=$(git status --porcelain | wc -l | tr -d ' ')
  if [ "$REMAIN" -gt 0 ]; then
    git stash push -u -m "non-autopilot-changes-before-walkaway-$(date +%s)"
    echo "ℹ Stashed non-autopilot leftovers (review with: git stash list)"
  fi
fi
git status   # MUST be clean now
echo "✅ PHASE 0 COMPLETE — bootstrap done. Moving to PHASE 1."
```

---

# PHASE 1 — D-3: Branch + PR convention + pre-push hook + ci/pr-validate

**Goal:** Establish `<dev>/MYM-<id>-<slug>` branch naming + `Closes MYM-XXX` PR body magic word + CI validator.

## 1.1 Branch + state
```bash
git checkout -b feat/d3-branch-pr-convention
mkdir -p .autopilot/state/d3
```

## 1.2 Create `.github/pull_request_template.md`
Content:
```markdown
## Summary
<!-- 1-2 sentences -->

## Linear Issue
Closes MYM-XXX
<!-- Required: Closes/Fixes/Ref MYM-NNN. Legacy W0.*: "Linear: N/A" -->

## Changes
- [ ] Item 1

## Testing
- [ ] Unit tests pass
- [ ] Manual smoke

## DoD
- [ ] CI green
- [ ] ≥1 review (2 for core/ via CODEOWNERS)
- [ ] Linear auto-moved to In Review
```

## 1.3 Create `scripts/git-hooks/pre-push.sh` (chmod +x)
```bash
#!/usr/bin/env bash
set -e
while read local_ref local_sha remote_ref remote_sha; do
  branch=$(echo "$local_ref" | sed 's|refs/heads/||')
  case "$branch" in
    main|master|develop|W0.*|Wave-*|hotfix/*|release/*) exit 0 ;;
  esac
  if ! echo "$branch" | grep -Eq '^[a-z0-9-]+/MMW-[0-9]+-[a-z0-9-]+$'; then
    echo "❌ Branch '$branch' must match <dev>/MYM-<id>-<slug>"
    echo "   Bypass: git push --no-verify"
    exit 1
  fi
done
exit 0
```

## 1.4 Append to `Makefile` (or create if missing):
```makefile
.PHONY: install-hooks
install-hooks:
	ln -sf ../../scripts/git-hooks/pre-push.sh .git/hooks/pre-push
	@echo "✓ Pre-push hook installed"
```

## 1.5 Create `.github/workflows/pr-validate.yml`
```yaml
name: pr-validate
on:
  pull_request:
    types: [opened, edited, synchronize, ready_for_review]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Branch naming
        env: { BRANCH: "${{ github.head_ref }}" }
        run: |
          case "$BRANCH" in W0.*|Wave-*|hotfix/*|release/*) exit 0 ;; esac
          if ! echo "$BRANCH" | grep -Eq '^[a-z0-9-]+/MMW-[0-9]+-[a-z0-9-]+$'; then
            echo "::error::Branch '$BRANCH' must match <dev>/MYM-<id>-<slug>"
            exit 1
          fi
      - name: PR body magic word
        env: { PR_BODY: "${{ github.event.pull_request.body }}" }
        run: |
          if echo "$PR_BODY" | grep -Eq '(Closes|Fixes|Ref) MMW-[0-9]+'; then exit 0; fi
          if echo "$PR_BODY" | grep -q 'Linear: N/A'; then exit 0; fi
          echo "::error::PR body missing 'Closes/Fixes/Ref MYM-NNN' or 'Linear: N/A'"
          exit 1
```

## 1.6 Self-test
```bash
bash -n scripts/git-hooks/pre-push.sh   # syntax OK
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-validate.yml'))"
# Positive case (must exit 0):
echo "refs/heads/anh/MYM-42-test test refs/heads/anh/MYM-42-test test" | bash scripts/git-hooks/pre-push.sh origin url
# Negative case (must exit 1):
echo "refs/heads/bad-name test refs/heads/bad-name test" | bash scripts/git-hooks/pre-push.sh origin url; [ $? -eq 1 ] && echo "neg OK"
```

## 1.7 Commits + Codex
```bash
git add .github/pull_request_template.md
git commit -m "feat(workflow): PR template with Linear magic-word

Required: Closes/Fixes/Ref MYM-NNN. Legacy W0.*: 'Linear: N/A'.
Refs plan v3.1.0 §D-3."

git add scripts/git-hooks/pre-push.sh Makefile
git commit -m "feat(workflow): pre-push hook enforcing <dev>/MYM-<id> convention

Install: make install-hooks. Bypass: git push --no-verify."

git add .github/workflows/pr-validate.yml
git commit -m "ci(workflow): pr-validate — branch name + Linear magic word"

# Codex review (1× clean — accept skip if codex CLI missing, document in final report)
if command -v codex >/dev/null 2>&1; then
  codex review --base main 2>&1 | tee .autopilot/state/d3/codex-01.txt
  if grep -qiE "schema|breaking|architectural|auth|token|injection" .autopilot/state/d3/codex-01.txt; then
    echo "HALT: Codex flagged ARCH/SECURITY in PHASE 1"; exit 1
  fi
else
  echo "⚠ codex CLI missing — skip review (document in final report)"
fi
```

## 1.8 Squash + push (use Squash Helper above)
```bash
BRANCH=feat/d3-branch-pr-convention
COMMIT_MSG="feat(workflow): MYM-XXX branch convention + PR template + pre-push + ci/pr-validate

PR template requires Linear magic word. Pre-push hook enforces branch
naming. CI validator runs on PR open/edit/sync. Refs §D-3."
git checkout main && git pull --rebase origin main || { echo "HALT: pull"; exit 1; }
git merge --squash $BRANCH
NO_VERIFY=""; [ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "$COMMIT_MSG"
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push"; exit 1; }
git branch -D $BRANCH
echo "✅ PHASE 1 COMPLETE — D-3 merged to main as $SHA. Moving to PHASE 2."
```

---

# PHASE 2 — D-4: CODEOWNERS + multi-dev playbook + Discord standup

## 2.1 Branch
```bash
git checkout -b feat/d4-multidev-playbook
mkdir -p .autopilot/state/d4
```

## 2.2 Create `.github/CODEOWNERS`
```
# Default
*                               @maingocanh

# High-risk (2 approvals via branch protection D-6-protect)
/core/                          @maingocanh
/markets/*/adapters/            @maingocanh
/ops_api/                       @maingocanh
/scripts/linear_migrate.py      @maingocanh
/.github/workflows/             @maingocanh
/.github/CODEOWNERS             @maingocanh

# Docs
/docs/                          @maingocanh
/docs/operations/               @maingocanh

# Memory — founder only
/memory/                        @maingocanh
```

## 2.3 Create `docs/operations/multi-dev-playbook.md`
Sections (full content):
```markdown
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
```

## 2.4 Create `docs/operations/discord-standup-setup.md`
```markdown
# Discord Standup Integration — Setup Runbook

> Founder UI work. Webhook URL is secret — never commit to repo.

1. Discord: Server Settings → Integrations → Webhooks → New Webhook for `#mmw-dev`. Copy URL.
2. Linear: Settings → Integrations → Slack/Discord → paste webhook URL. Select team + channel.
3. Daily digest: enable, time 9:00 AM (Asia/Ho_Chi_Minh), filter "Active cycle".
4. Weekly digest: enable Monday 9:00 AM, project = each phase OR overall.
5. Verification: Linear → trigger manual digest → confirm message appears in #mmw-dev.
6. Rotation: webhook URL is secret — store Linear-side, NOT in repo. Rotate every 6 months.
```

## 2.5 Verify + commit + Codex + squash
```bash
grep -c '^@' .github/CODEOWNERS   # MUST ≥1
git add .github/CODEOWNERS
git commit -m "feat(workflow): CODEOWNERS — review rotation + 2-approval high-risk

Refs §D-4."

git add docs/operations/multi-dev-playbook.md
git commit -m "docs(ops): multi-dev playbook"

git add docs/operations/discord-standup-setup.md
git commit -m "docs(ops): Discord standup integration runbook"

if command -v codex >/dev/null 2>&1; then
  codex review --base main 2>&1 | tee .autopilot/state/d4/codex-01.txt
  grep -qiE "schema|breaking|architectural|auth|token|injection" .autopilot/state/d4/codex-01.txt && { echo "HALT: Codex ARCH/SECURITY"; exit 1; }
fi

BRANCH=feat/d4-multidev-playbook
git checkout main && git pull --rebase origin main || { echo "HALT: pull"; exit 1; }
git merge --squash $BRANCH
NO_VERIFY=""; [ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "feat(workflow): multi-dev playbook + CODEOWNERS + Discord standup config (§D-4)"
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push"; exit 1; }
git branch -D $BRANCH
echo "✅ PHASE 2 COMPLETE — D-4 merged to main as $SHA. Moving to PHASE 3."
```

---

# PHASE 3 — D-5: Dev onboarding doc + Linear issue templates

## 3.1 Branch
```bash
git checkout -b feat/d5-onboarding
mkdir -p .autopilot/state/d5
```

## 3.2 Create `docs/operations/dev-onboarding.md`
```markdown
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
```

## 3.3 Create `docs/operations/linear-issue-templates.md`
Full content with 4 templates (Feature/Bug/Chore/Docs), each with Title placeholder + Required fields + Body template. (Detailed bodies — keep concise per template.)

```markdown
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
```

## 3.4 Inline Linear template create (try API; fallback gracefully)
```bash
# Python inline because Linear API needed
python3 <<'PYEOF'
import os, json, re
from pathlib import Path
try:
    import httpx
except ImportError:
    print("⚠ httpx not installed — skip API template create, founder will paste manually")
    exit(0)

key = os.environ.get("LINEAR_API_KEY")
if not key:
    print("⚠ LINEAR_API_KEY missing — skip API create")
    exit(0)

team_name = os.environ.get("LINEAR_TEAM_NAME", "MyMoneyWent")
spec = Path("docs/operations/linear-issue-templates.md").read_text()

with httpx.Client(base_url="https://api.linear.app/graphql",
                  headers={"Authorization": key, "Content-Type": "application/json"},
                  timeout=30) as c:
    teams = c.post("", json={"query": "query { teams { nodes { id name } } }"}).json()
    team_id = next((t["id"] for t in teams["data"]["teams"]["nodes"] if t["name"] == team_name), None)
    if not team_id:
        print(f"⚠ Team '{team_name}' not found — skip")
        exit(0)

    templates = re.findall(
        r"##\s+Template\s+\d+:\s+(\w+).*?\*\*Body template:\*\*\s*```\s*\n(.*?)```",
        spec, re.DOTALL,
    )
    created = 0
    for name, body in templates:
        try:
            r = c.post("", json={
                "query": "mutation Create($input: IssueTemplateCreateInput!) { issueTemplateCreate(input: $input) { success } }",
                "variables": {"input": {"name": name, "description": body, "teamId": team_id}},
            })
            if r.status_code < 400 and "errors" not in r.json():
                created += 1
                print(f"  · Template '{name}' created via API")
            else:
                print(f"  ⚠ Template '{name}' API create failed (likely free-tier limit) — founder paste manually")
        except Exception as e:
            print(f"  ⚠ Template '{name}': {e}")
    print(f"Templates created via API: {created}/4. Manual fallback if 0.")
PYEOF
```

## 3.5 Verify + commits + Codex + squash
```bash
# Cross-ref check
grep -E '\]\([^)h]' docs/operations/dev-onboarding.md && echo "ℹ relative links — verify manually"

git add docs/operations/dev-onboarding.md
git commit -m "docs(onboarding): dev playbook — first-day setup + workflow + DoD (§D-5)"

git add docs/operations/linear-issue-templates.md
git commit -m "docs(linear): 4 issue template specs (Feature/Bug/Chore/Docs)"

if command -v codex >/dev/null 2>&1; then
  codex review --base main 2>&1 | tee .autopilot/state/d5/codex-01.txt
  grep -qiE "schema|breaking|architectural|auth|token|injection" .autopilot/state/d5/codex-01.txt && { echo "HALT: Codex"; exit 1; }
fi

BRANCH=feat/d5-onboarding
git checkout main && git pull --rebase origin main || { echo "HALT: pull"; exit 1; }
git merge --squash $BRANCH
NO_VERIFY=""; [ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "docs(onboarding): dev playbook + Linear issue templates (§D-5)"
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push"; exit 1; }
git branch -D $BRANCH
echo "✅ PHASE 3 COMPLETE — D-5 merged to main as $SHA. Moving to PHASE 4."
```

---

# PHASE 4 — D-6: linear-status-sync.yml + helper + branch-protection runbook

## 4.1 Branch
```bash
git checkout -b feat/d6-linear-status-sync
mkdir -p .autopilot/state/d6
```

## 4.2 Create `.github/workflows/linear-status-sync.yml`
```yaml
name: linear-status-sync
on:
  check_run: { types: [completed] }
  pull_request: { types: [opened, ready_for_review, closed] }
  pull_request_review: { types: [submitted] }
concurrency:
  group: linear-sync-${{ github.event.pull_request.number || github.event.check_run.pull_requests[0].number || github.run_id }}
  cancel-in-progress: false
jobs:
  sync:
    runs-on: ubuntu-latest
    if: github.event.pull_request != null || github.event.check_run.pull_requests[0] != null
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install httpx
      - name: Extract Linear ID
        id: extract
        env: { PR_BODY: "${{ github.event.pull_request.body }}" }
        run: |
          ID=$(echo "$PR_BODY" | grep -Eo '(Closes|Fixes|Ref) MMW-[0-9]+' | head -1 | grep -Eo 'MMW-[0-9]+' || true)
          [ -z "$ID" ] && echo "skip=true" >> "$GITHUB_OUTPUT" || echo "issue_id=$ID" >> "$GITHUB_OUTPUT"
      - name: Determine action
        if: steps.extract.outputs.skip != 'true'
        id: action
        env:
          EVENT: "${{ github.event_name }}"
          CHECK: "${{ github.event.check_run.conclusion }}"
          REVIEW: "${{ github.event.review.state }}"
        run: |
          case "$EVENT" in
            check_run)
              [ "$CHECK" = "failure" ] && { echo "label=ci-failing" >> "$GITHUB_OUTPUT"; echo "act=add" >> "$GITHUB_OUTPUT"; }
              [ "$CHECK" = "success" ] && { echo "label=ci-failing" >> "$GITHUB_OUTPUT"; echo "act=remove" >> "$GITHUB_OUTPUT"; } ;;
            pull_request_review)
              [ "$REVIEW" = "changes_requested" ] && { echo "label=changes-requested" >> "$GITHUB_OUTPUT"; echo "act=add" >> "$GITHUB_OUTPUT"; }
              [ "$REVIEW" = "approved" ] && { echo "label=changes-requested" >> "$GITHUB_OUTPUT"; echo "act=remove" >> "$GITHUB_OUTPUT"; } ;;
          esac
      - name: Linear GraphQL
        if: steps.action.outputs.label != ''
        env:
          LINEAR_API_KEY: "${{ secrets.LINEAR_API_KEY }}"
          ISSUE: "${{ steps.extract.outputs.issue_id }}"
          LABEL: "${{ steps.action.outputs.label }}"
          ACT: "${{ steps.action.outputs.act }}"
        run: python .github/scripts/linear-sync.py --issue "$ISSUE" --label "$LABEL" --action "$ACT"
```

## 4.3 Create `.github/scripts/linear-sync.py`
```python
#!/usr/bin/env python3
"""Minimal Linear label add/remove. Called from linear-status-sync workflow."""
import argparse, os, sys
import httpx

ENDPOINT = "https://api.linear.app/graphql"

def gql(client, query, variables=None):
    r = client.post("", json={"query": query, "variables": variables or {}})
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(f"Linear: {body['errors']}")
    return body["data"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--issue", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--action", required=True, choices=["add", "remove"])
    args = p.parse_args()
    key = os.environ["LINEAR_API_KEY"]
    with httpx.Client(base_url=ENDPOINT,
                      headers={"Authorization": key, "Content-Type": "application/json"},
                      timeout=30) as c:
        # Lookup issue UUID from MYM-NNN
        d = gql(c, 'query Q($id: String!) { issue(id: $id) { id labels { nodes { id name } } } }',
                {"id": args.issue})
        issue = d["issue"]
        if not issue:
            print(f"Issue {args.issue} not found")
            return 0
        existing = {lbl["name"]: lbl["id"] for lbl in issue["labels"]["nodes"]}

        # Lookup label UUID (workspace + team scope)
        d = gql(c, 'query { issueLabels { nodes { id name } } }')
        label_id = next((lbl["id"] for lbl in d["issueLabels"]["nodes"] if lbl["name"] == args.label), None)
        if not label_id:
            print(f"Label '{args.label}' not found in workspace")
            return 0

        # Idempotent
        if args.action == "add":
            if args.label in existing:
                print(f"Label '{args.label}' already on {args.issue}, skip")
                return 0
            new_ids = list(existing.values()) + [label_id]
        else:
            if args.label not in existing:
                print(f"Label '{args.label}' not on {args.issue}, skip")
                return 0
            new_ids = [v for k, v in existing.items() if k != args.label]

        gql(c, 'mutation U($id: String!, $ids: [String!]!) { issueUpdate(id: $id, input: {labelIds: $ids}) { success } }',
            {"id": issue["id"], "ids": new_ids})
        print(f"Label '{args.label}' {args.action}ed on {args.issue}")

if __name__ == "__main__":
    sys.exit(main() or 0)
```

## 4.4 Create `docs/operations/branch-protection-setup.md`
```markdown
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

Open 1 test PR matching `<dev>/MYM-NNN-...` convention → check pr-validate runs → ci-failing label appears on linked Linear when CI fails.
```

## 4.5 Self-test, commits, Codex, squash
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/linear-status-sync.yml'))"
python -m py_compile .github/scripts/linear-sync.py

git add .github/workflows/linear-status-sync.yml
git commit -m "ci(linear): linear-status-sync workflow — GH Actions → Linear API (Option A)"

git add .github/scripts/linear-sync.py
git commit -m "ci(linear): helper script — label add/remove (idempotent)"

git add docs/operations/branch-protection-setup.md
git commit -m "docs(ops): branch protection runbook"

if command -v codex >/dev/null 2>&1; then
  codex review --base main 2>&1 | tee .autopilot/state/d6/codex-01.txt
  grep -qiE "schema|breaking|architectural|auth|token|injection" .autopilot/state/d6/codex-01.txt && { echo "HALT: Codex"; exit 1; }
fi

BRANCH=feat/d6-linear-status-sync
git checkout main && git pull --rebase origin main || { echo "HALT: pull"; exit 1; }
git merge --squash $BRANCH
NO_VERIFY=""; [ "$AUTOPILOT_NO_VERIFY" = "1" ] && NO_VERIFY="--no-verify"
git commit $NO_VERIFY -m "ci(linear): GH Actions → Linear status sync (Option A) + protection runbook (§D-6)"
SHA=$(git rev-parse HEAD)
git push origin main || { echo "HALT: push"; exit 1; }
git branch -D $BRANCH
echo "✅ PHASE 4 COMPLETE — D-6 merged to main as $SHA. Moving to PHASE 5."
```

---

# PHASE 5 — Branch Protection (apply via gh api)

## 5.1 Confirm prereqs
```bash
gh auth status || { echo "HALT: gh CLI not authed"; exit 1; }
test -f .github/CODEOWNERS || { echo "HALT: CODEOWNERS missing"; exit 1; }
test -f .github/workflows/pr-validate.yml || { echo "HALT: pr-validate workflow missing"; exit 1; }

# Resolve repo
REPO=$(git config --get remote.origin.url | sed -E 's#.*[:/]([^/:]+/[^/]+?)(\.git)?$#\1#')
echo "Repo: $REPO"
```

## 5.2 Add LINEAR_API_KEY to GitHub repo secrets (for linear-status-sync workflow)
```bash
# Only if not already set
if ! gh secret list --repo "$REPO" | grep -q '^LINEAR_API_KEY'; then
  echo -n "$LINEAR_API_KEY" | gh secret set LINEAR_API_KEY --repo "$REPO"
  echo "Added LINEAR_API_KEY secret"
else
  echo "LINEAR_API_KEY secret exists, skip"
fi
```

## 5.3 Apply branch protection via gh api
```bash
cat > /tmp/protection.json <<'JSONEOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["pr-validate"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "require_code_owner_reviews": true,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSONEOF

gh api -X PUT "repos/$REPO/branches/main/protection" --input /tmp/protection.json
if [ $? -ne 0 ]; then
  echo "HALT: gh api branch protection failed (may need admin scope)"
  exit 1
fi
rm /tmp/protection.json
echo "✅ PHASE 5 COMPLETE — branch protection applied to $REPO/main. All phases done."
```

---

## Halt-Rules (any of these → emit HALT report + stop)

1. Pre-flight env var missing (LINEAR_API_KEY) → HALT before PHASE 1
2. `claude --version` fails → HALT (impossible since you ARE Claude Code, but verify)
3. `git pull` / `git push` fails 2× consecutively → HALT
4. Codex review flags `schema|breaking|architectural|auth|token|injection` → HALT
5. Any test pre-flight that was passing now fails → HALT (regression)
6. `# type: ignore` proposed in any edit → HALT
7. `git push --force` ever needed → HALT
8. Tool error 2× in a row on any tool → HALT
9. Linear API rate-limit (429) 2× consecutively → HALT
10. Skipping a phase or its checkpoint output → HALT (silent skip is failure mode)
11. Phase 5 `gh api` fails → HALT (need repo admin scope; founder applies manually after)

## Halt Report Template

```
═══════════════════════════════════════════════════════
WALK-AWAY MEGA-PROMPT — HALTED
═══════════════════════════════════════════════════════
Halted at:   PHASE <N> step <X.Y>
Trigger:     <one of 11 halt rules>
Branch:      <feature-branch or main>
HEAD:        <SHA>

Completed phases:
  [✅/❌] PHASE 0 — Bootstrap
  [✅/❌] PHASE 1 — D-3
  [✅/❌] PHASE 2 — D-4
  [✅/❌] PHASE 3 — D-5
  [✅/❌] PHASE 4 — D-6
  [✅/❌] PHASE 5 — Branch protection

Detail:
<error output, Codex finding, or push reason>

Recovery:
- Branch state: <intact / cleaned>
- Commits since bootstrap: <list>
- To resume: founder reviews above, fixes blocker, re-runs walk-away-prompt.md
  (later phases will skip already-merged work via idempotent checks)

═══════════════════════════════════════════════════════
```

## Final Report Template (ALL 6 phases complete)

```
═══════════════════════════════════════════════════════
WALK-AWAY MEGA-PROMPT — ALL PHASES COMPLETE
═══════════════════════════════════════════════════════
Started:  <UTC timestamp>
Ended:    <UTC timestamp>
Duration: <total seconds>

Phases merged to main:
  ✅ PHASE 0 — Bootstrap: <SHA or "no-op (clean)">
  ✅ PHASE 1 — D-3: <SHA>
  ✅ PHASE 2 — D-4: <SHA>
  ✅ PHASE 3 — D-5: <SHA>
  ✅ PHASE 4 — D-6: <SHA>
  ✅ PHASE 5 — Branch protection applied to <owner/repo>

Linear infrastructure:
  - Issue templates: <N>/4 created via API (rest: founder paste manually if 0)

GitHub infrastructure:
  - CODEOWNERS active
  - PR template active
  - pr-validate workflow active
  - linear-status-sync workflow active
  - Branch protection: ≥1 approval, pr-validate required, force-push blocked
  - LINEAR_API_KEY secret added to repo

Multi-dev ready state:
  - When dev #2 onboards: hand them docs/operations/dev-onboarding.md
  - Their first PR: must follow <dev>/MYM-NNN-slug branch + "Closes MYM-NNN" body
  - Linear auto-syncs status on PR open/merge

Founder follow-ups (manual, not blocking):
  - Setup Discord webhook per docs/operations/discord-standup-setup.md (~5 min)
  - Linear free tier verify (memory C-3.0 row): some labels may be workspace-wide
  - If Linear templates failed API create (free-tier limit): paste manually from
    docs/operations/linear-issue-templates.md

═══════════════════════════════════════════════════════
```

---

Begin with Global Pre-Flight, then proceed through PHASE 0 → 1 → 2 → 3 → 4 → 5 in order. Emit checkpoint line after each phase. Do not skip phases. Do not stop until all 6 checkmarks emit or a halt rule fires.
