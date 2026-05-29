Task: ops-dashboard D-6 — linear-status-sync.yml workflow + branch protection runbook
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/linear-status-sync`, Codex 2× consecutive clean (P1), STOP_AT_READY.

Risk tier:          P1 (CI auth + gating)

Context: GitHub Actions listens to check_run/PR/review events, updates Linear labels via GraphQL (Option A per plan). D-3 must be merged first.

Scope: (a) `.github/workflows/linear-status-sync.yml`, (b) helper `.github/scripts/linear-sync.py` if logic > 50 lines yaml, (c) `docs/operations/branch-protection-setup.md` runbook. NO branch protection rules in code (UI work).

Required reading:
1. Plan §D-6 (Option A architecture)
2. `.github/workflows/pr-validate.yml` (D-3) for style match
3. Linear `issueUpdate` + `issueAddLabel` mutations

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current
git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
pytest tests/ -v
test -f .github/workflows/pr-validate.yml || echo "WARN: D-3 not merged"
test -f .github/pull_request_template.md || echo "WARN: PR template missing"
```
D-3 not merged → HALT.

Anti-patterns: force-push, type:ignore, hard-code LINEAR_API_KEY, move status to Done from this workflow (magic word handles that), make required status check, race-condition concurrent runs.

Step 1 — Branch
```bash
git checkout -b feat/linear-status-sync
mkdir -p .autopilot/state/d-6/codex
```

Step 2 — TDD if helper script
`tests/github_workflows/test_linear_sync.py`:
- `test_extract_magic_word_from_body` → MYM-NNN
- `test_extract_legacy_acknowledgement` → "Linear: N/A" → None
- `test_compute_label_check_failed` → add ci-failing
- `test_compute_label_check_success` → remove ci-failing
- `test_compute_label_changes_requested` → add changes-requested
- `test_compute_label_review_approved` → remove changes-requested
- `test_no_secret_in_logs`
- `test_idempotent_label_add`

Tests fail first.

Step 3 — Workflow `.github/workflows/linear-status-sync.yml`
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
              [ "$CHECK" = "failure" ] && echo "label=ci-failing" >> "$GITHUB_OUTPUT" && echo "act=add" >> "$GITHUB_OUTPUT"
              [ "$CHECK" = "success" ] && echo "label=ci-failing" >> "$GITHUB_OUTPUT" && echo "act=remove" >> "$GITHUB_OUTPUT" ;;
            pull_request_review)
              [ "$REVIEW" = "changes_requested" ] && echo "label=changes-requested" >> "$GITHUB_OUTPUT" && echo "act=add" >> "$GITHUB_OUTPUT"
              [ "$REVIEW" = "approved" ] && echo "label=changes-requested" >> "$GITHUB_OUTPUT" && echo "act=remove" >> "$GITHUB_OUTPUT" ;;
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

Step 4 — Helper `.github/scripts/linear-sync.py`
Minimal: argparse(--issue, --label, --action), httpx GraphQL with auth header, idempotent (re-add existing label = no-op), exit 0 on success.

Tests pass:
```bash
pytest tests/github_workflows/ -v
```

Step 5 — Branch protection runbook `docs/operations/branch-protection-setup.md`
Sections: Settings → Branches rule for main, required PR + 1 approval (2 for core/), required status checks (ci/pytest, ci/lint, ci/import-linter, pr-validate), restrict force-push + deletions, Linear webhook secret rotation (6 months), verification test.

Step 6 — Local verify
```bash
ruff check .github/scripts/ && black --check .github/scripts/
python -c "import yaml; yaml.safe_load(open('.github/workflows/linear-status-sync.yml'))"
pytest tests/ -v
```

Commits:
```bash
git add .github/workflows/linear-status-sync.yml
git commit -m "ci(linear): linear-status-sync workflow — Option A (GH Actions → Linear API)

Listens check_run/PR/review. Manages ci-failing + changes-requested labels.
Concurrency-serialized per issue. Refs §D-6."

git add .github/scripts/linear-sync.py tests/github_workflows/
git commit -m "ci(linear): helper script + tests"

git add docs/operations/branch-protection-setup.md
git commit -m "docs(ops): branch protection runbook (founder UI work post-merge)"
```

Step 7 — Codex 2× clean
Attention: LINEAR_API_KEY only via secrets, concurrency key prevents race, idempotent label ops, regex anchored, legacy PR skips gracefully.

Circuit breakers: standard + SECRET_IN_LOG, RACE_HAZARD, LABEL_NOT_IDEMPOTENT.

Final report (READY). Founder applies branch protection rules via UI post-merge.

Begin with Pre-flight, then Step 1.
