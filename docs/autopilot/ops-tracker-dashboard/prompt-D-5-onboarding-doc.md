Task: ops-dashboard D-5 — dev onboarding doc + Linear issue template specs
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `docs/dev-onboarding`, Codex 1× clean, STOP_AT_READY.

Risk tier: P2 mature (docs)

Context: First-day setup + workflow cheat sheet + 4 Linear template specs (Feature/Bug/Chore/Docs). Templates created in Linear UI by founder via D-5-templates automator.

Scope: (a) `docs/operations/dev-onboarding.md`, (b) `docs/operations/linear-issue-templates.md`. NO code changes. NO actual Linear template creation (automator).

Required reading: plan §D-5, `docs/operations/multi-dev-playbook.md` (D-4), `MEMORY.md` rules, `Makefile`.

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current; git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
pytest tests/ -v
test -f .github/pull_request_template.md   # D-3 done
test -f docs/operations/multi-dev-playbook.md   # D-4 done
test -f .github/CODEOWNERS
```
D-3/D-4 unmerged → HALT.

Anti-patterns: hard-code secrets in examples, doc >2 pages overwhelming, duplicate playbook content (reference instead).

Step 1 — Branch
```bash
git checkout -b docs/dev-onboarding
mkdir -p .autopilot/state/d-5/codex
```

Step 2 — Onboarding `docs/operations/dev-onboarding.md`
Sections:
1. **First-day setup (30 min)**: Linear access, GitHub collaborator, Discord, clone + make setup + install-hooks
2. **Workflow cheat sheet**: pick task (Linear Backlog → drag Todo), branch `<dev>/MYM-<id>-<slug>`, status auto-syncs first push, PR template, DoD (CI + 1 approval + Linear Done auto)
3. **Conventions pointers**: §D-3, §D-4 playbook, MEMORY.md, contribution.md
4. **Where to ask**: spec/Linear, infra/Discord, founder review/PR tag
5. **First PR path**: good-first-issue, target merged in 3 days

Step 3 — Linear templates spec `docs/operations/linear-issue-templates.md`
4 templates, each with Title placeholder, Required fields, Body template (markdown):

**Feature**: Phase + Feature ID + Priority + Risk + Spec link + Acceptance criteria
**Bug**: Phase + Priority + Severity + Risk (if applicable) + Repro/Expected/Actual/Affected version
**Chore**: Phase + Priority + Scope + Why now + Impact
**Docs**: Phase + Priority + Affected doc + Section + Changes + Audience + Why

Founder pastes into Linear UI (D-5-templates automator tries API first).

Step 4 — Local verify
```bash
# Cross-ref check
grep -E '\]\([^)h]' docs/operations/dev-onboarding.md
pytest tests/ -v
```

Commits:
```bash
git add docs/operations/dev-onboarding.md
git commit -m "docs(onboarding): dev playbook — first-day setup + workflow + DoD

~2 pages, references D-3 + D-4 + MEMORY rules. Refs §D-5."

git add docs/operations/linear-issue-templates.md
git commit -m "docs(linear): 4 issue template specs — Feature/Bug/Chore/Docs

For D-5-templates automator + manual UI fallback."
```

Step 5 — Codex 1× clean
Attention: all cross-refs resolve, no playbook duplication, acceptance criteria testable, no secrets in examples.

Circuit breakers: standard + BROKEN_CROSS_REF, POLICY_DRIFT.

Final report (READY).

Begin with Pre-flight, then Step 1.
