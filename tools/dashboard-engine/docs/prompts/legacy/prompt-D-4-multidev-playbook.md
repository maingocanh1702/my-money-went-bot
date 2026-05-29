Task: ops-dashboard D-4 — multi-dev playbook + CODEOWNERS + standup config
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/multidev-playbook`, Codex 1× clean (P2 pilot), STOP_AT_READY.

Risk tier: P2 pilot

Context: WIP limit ≤2, CODEOWNERS for 2-approval on core/, Linear → Discord daily/weekly digest.

Scope: (a) `.github/CODEOWNERS`, (b) `docs/operations/multi-dev-playbook.md`, (c) `docs/operations/discord-standup-setup.md`. NO Linear sync (D-6). NO branch protection enforce (D-6 runbook).

Required reading: plan §D-4, memory `project_monorepo_decision`, `feedback_concurrency_one_session`.

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current; git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
pytest tests/ -v
ls -d core/ markets/ 2>/dev/null
test -f .github/pull_request_template.md   # D-3 merged
```

Anti-patterns: force-push, hard-code Discord webhook in repo, founder = sole owner of everything, require ≥3 approvals.

Step 1 — Branch
```bash
git checkout -b feat/multidev-playbook
mkdir -p .autopilot/state/d-4/codex
```

Step 2 — CODEOWNERS `.github/CODEOWNERS`
```
# Default
*                               @maingocanh

# High-risk — 2 approvals via branch protection
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

Step 3 — Playbook `docs/operations/multi-dev-playbook.md`
Sections (compact):
- Task assignment: self-serve from Backlog, founder may assign Urgent
- WIP limit: ≤2 in In Progress + In Review (soft via Linear Workload view)
- Code review rotation: CODEOWNERS auto-request, 1 approval default / 2 for core
- Standup: Linear → Discord #mmw-dev (daily 9am VN + weekly Monday)
- Parallel work: STRICT 1 session per .git/ (memory rule), use git worktree
- Escalation: spec → Linear comment, infra → Discord, arch → tag @maingocanh

Step 4 — Discord runbook `docs/operations/discord-standup-setup.md`
1. Discord channel `#mmw-dev` + webhook URL (Server Settings → Integrations)
2. Linear: Settings → Integrations → Discord → paste webhook
3. Daily digest 9am VN, filter active cycle
4. Weekly digest Monday 9am
5. Verification: trigger manual digest
6. Webhook URL = secret (Linear-side, NEVER in repo)

Step 5 — Local verify
```bash
grep -c '^@' .github/CODEOWNERS    # ≥1
pytest tests/ -v
```

Commits:
```bash
git add .github/CODEOWNERS
git commit -m "feat(workflow): CODEOWNERS — review rotation + 2-approval high-risk

core/, markets/*/adapters/, ops_api/, .github/workflows/, /memory/.
Refs §D-4."

git add docs/operations/multi-dev-playbook.md
git commit -m "docs(ops): multi-dev playbook — assignment, WIP, review, concurrency"

git add docs/operations/discord-standup-setup.md
git commit -m "docs(ops): Discord standup integration runbook"
```

Step 6 — Codex 1× clean
Attention: no approval deadlock (founder-only is OK for solo+1), playbook consistent with concurrency memory, no Discord webhook URL committed.

Circuit breakers: standard + SECRET_LEAKED_TO_DOC, POLICY_CONFLICT.

Final report (READY).

Begin with Pre-flight, then Step 1.
