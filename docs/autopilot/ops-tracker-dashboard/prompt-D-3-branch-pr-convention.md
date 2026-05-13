Task: ops-dashboard D-3 — branch + PR convention (MMW-XXX magic word) + pre-push hook + ci/pr-validate
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/branch-pr-convention`, Codex 1× clean, STOP_AT_READY.

Risk tier:          P2 pilot
Merge policy:       manual_only

Context: Branch convention `<dev>/MMW-<id>-<slug>` + PR template với `Closes MMW-XXX` để Linear auto-sync. Legacy W0.* grandfathered.

Scope: (a) `.github/pull_request_template.md`, (b) `scripts/git-hooks/pre-push.sh` + Makefile install target, (c) `.github/workflows/pr-validate.yml`. NO Linear API integration (D-6).

Required reading:
1. `docs/operations/ops-tracker-dashboard-improve.md` §D-3
2. `.github/workflows/` — match style if existing workflows

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current   # clean / main
git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
pytest tests/ -v
ls .github/workflows/
```

Anti-patterns: force-push, type:ignore, retroactively block W0.* / Wave-* legacy, hard-code Linear API key, force hook on all devs without install opt-in.

Step 1 — Branch
```bash
git checkout -b feat/branch-pr-convention
mkdir -p .autopilot/state/d-3/codex
```

Step 2 — PR template `.github/pull_request_template.md`
```markdown
## Summary
<!-- 1-2 sentences -->

## Linear Issue
Closes MMW-XXX
<!-- Required: Closes/Fixes/Ref MMW-NNN. Legacy W0.*: "Linear: N/A" -->

## Changes
- [ ] Item 1

## Testing
- [ ] Unit tests pass
- [ ] Manual smoke test

## DoD
- [ ] CI green
- [ ] ≥1 review (2 for core/ via CODEOWNERS)
- [ ] Linear auto-moved to In Review (verify after open)
```

Step 3 — Pre-push hook `scripts/git-hooks/pre-push.sh`
```bash
#!/usr/bin/env bash
set -e
while read local_ref local_sha remote_ref remote_sha; do
  branch=$(echo "$local_ref" | sed 's|refs/heads/||')
  case "$branch" in
    main|master|develop|W0.*|Wave-*|hotfix/*|release/*) exit 0 ;;
  esac
  if ! echo "$branch" | grep -Eq '^[a-z0-9-]+/MMW-[0-9]+-[a-z0-9-]+$'; then
    echo "❌ Branch '$branch' must match <dev>/MMW-<id>-<slug>"
    echo "   Bypass: git push --no-verify"
    exit 1
  fi
done
exit 0
```
`chmod +x scripts/git-hooks/pre-push.sh`

Step 4 — Makefile installer
Add target:
```makefile
.PHONY: install-hooks
install-hooks:
	ln -sf ../../scripts/git-hooks/pre-push.sh .git/hooks/pre-push
	@echo "✓ Pre-push hook installed"
```

Step 5 — CI validator `.github/workflows/pr-validate.yml`
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
            echo "::error::Branch '$BRANCH' must match <dev>/MMW-<id>-<slug>"
            exit 1
          fi
      - name: PR body magic word
        env: { PR_BODY: "${{ github.event.pull_request.body }}" }
        run: |
          if echo "$PR_BODY" | grep -Eq '(Closes|Fixes|Ref) MMW-[0-9]+'; then exit 0; fi
          if echo "$PR_BODY" | grep -q 'Linear: N/A'; then exit 0; fi
          echo "::error::PR body missing 'Closes/Fixes/Ref MMW-NNN' or 'Linear: N/A'"
          exit 1
```

Step 6 — Local verify
```bash
bash -n scripts/git-hooks/pre-push.sh
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-validate.yml'))"
# Hook self-test
bash -c 'echo "refs/heads/anh/MMW-42-test test refs/heads/anh/MMW-42-test test" | bash scripts/git-hooks/pre-push.sh origin "..."'  # exit 0
bash -c 'echo "refs/heads/bad-name test refs/heads/bad-name test" | bash scripts/git-hooks/pre-push.sh origin "..."' && echo FAIL || echo "expected exit 1 ✓"
pytest tests/ -v
```
Mismatch → HALT (TDD oracle).

Atomic commits:
```bash
git add .github/pull_request_template.md
git commit -m "feat(workflow): PR template with Linear magic-word

Required: Closes/Fixes/Ref MMW-NNN. Legacy: 'Linear: N/A'. Refs §D-3."

git add scripts/git-hooks/pre-push.sh Makefile
git commit -m "feat(workflow): pre-push hook enforcing branch convention

Install: make install-hooks. Bypass: git push --no-verify."

git add .github/workflows/pr-validate.yml
git commit -m "ci(workflow): pr-validate.yml — branch name + Linear magic word

Recommend adding to required status checks AFTER ≥10 PRs use convention."
```

Step 7 — Codex 1× clean (P2 pilot)
```bash
codex review --base main 2>&1 | tee .autopilot/state/d-3/codex/round-01.txt
```

Circuit breakers: standard + LEGACY_BRANCH_BREAK (W0.* not skipped), SCOPE_CREEP (Linear API call).

Final report (READY):
```
═══════════════════════════════════════════════════════
AUTOPILOT D-3 — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════
Branch feat/branch-pr-convention: intact
Files added: .github/pull_request_template.md, scripts/git-hooks/pre-push.sh, .github/workflows/pr-validate.yml
Modified: Makefile
Codex: Round 01: <findings | clean>
Verify: hook self-test pos+neg pass; yaml parse OK

Suggested squash:
  git checkout main && git pull --ff-only origin main
  git merge --squash feat/branch-pr-convention
  git commit -m "feat(workflow): MMW-XXX branch convention + PR template + pre-push + ci-validate (§D-3)"
  git branch -D feat/branch-pr-convention && git push origin main
═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1.
