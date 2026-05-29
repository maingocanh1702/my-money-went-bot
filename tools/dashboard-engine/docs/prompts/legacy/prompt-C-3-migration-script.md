Task: ops-dashboard C-3 — Linear migration script (PRs + features → Linear via GraphQL)
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/linear-migration-script`, Codex 2× consecutive clean (P1), STOP_AT_READY.

Risk tier:          P1 (data migration + API auth)
Merge policy:       manual_only
Codex review:       2x_consecutive_clean

Context: One-shot script `scripts/linear_migrate.py` migrating tracker.md PRs + roadmap.md §2 features into Linear via `issueCreate`. C-2 (workspace setup) must be done first. Idempotent via state file.

Scope: (a) `scripts/linear_migrate.py` with --dry-run/--execute --confirm, (b) `tests/scripts/test_linear_migrate.py` (real fixture slices, not synthetic), (c) `docs/operations/linear-migration-runbook.md`. NO ongoing-sync logic. NO dashboard parser changes.

Required reading:
1. Plan §C-3
2. `docs/implementation-tracker.md`
3. `docs/mymoneywent-roadmap.md` §2
4. Linear GraphQL: developers.linear.app
5. Memory `feedback_ci_install_requirements_txt.md` — deps in both requirements.txt + [dev]

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current; git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check && pytest tests/ -v
test -f docs/implementation-tracker.md && test -f docs/mymoneywent-roadmap.md
```

Anti-patterns: force-push, type:ignore, hard-code LINEAR_API_KEY, --execute without --dry-run gate, modify tracker.md content, synthesize Linear API responses (use real captured), run live during autopilot.

Step 1 — Branch
```bash
git checkout -b feat/linear-migration-script
mkdir -p .autopilot/state/c-3/codex
```

Step 2 — TDD: tests fail first
File `tests/scripts/test_linear_migrate.py` covering:
- `test_parse_tracker_extracts_PR_rows` (real fixture)
- `test_parse_roadmap_extracts_features` (real fixture)
- `test_build_issue_payload_pr` — Linear input shape
- `test_build_issue_payload_feature` — parent + sub-issue links
- `test_dry_run_no_api_call` (httpx_mock asserts 0 calls)
- `test_execute_requires_dry_run_first` — without prior dry-run-ok flag → exit 2
- `test_idempotent_skip_existing` — re-run skips
- `test_rate_limit_backoff` — 429 → exponential backoff
- `test_no_api_key_in_logs`

Real fixtures (frozen captures, comments mark "do not synthesize"):
```bash
mkdir -p tests/scripts/fixtures
# capture slices of tracker.md + roadmap.md
```

Run tests (MUST fail):
```bash
pytest tests/scripts/test_linear_migrate.py -v
```
Any pass → TDD oracle violated → HALT.

Commit:
```bash
git add tests/scripts/
git commit -m "test(linear-migrate): failing tests + real fixtures"
```

Step 3 — Implement `scripts/linear_migrate.py`
Structure: argparse(--dry-run, --execute, --confirm), env LINEAR_API_KEY, exponential backoff on 429/5xx, state file `scripts/.linear_migrate_state.json` (idempotency map), --execute requires `.dryrun-ok` marker from prior dry-run.

Run tests pass:
```bash
pytest tests/scripts/test_linear_migrate.py -v
```

Step 4 — Operator runbook `docs/operations/linear-migration-runbook.md`
Sections: pre-req (env, C-2 done), --dry-run procedure, --execute procedure, QA checklist (random spot-checks 5-10), rollback, post-migration mirror phase logging.

Step 5 — Local verify
```bash
ruff check scripts/ && black --check scripts/ && mypy scripts/linear_migrate.py
pytest tests/ -v
```
If deps added: update `requirements.txt` + `[dev]` extras.

Commits:
```bash
git add scripts/linear_migrate.py
git commit -m "feat(linear): one-shot migration script — tracker + roadmap → Linear

GraphQL issueCreate per row, --dry-run/--execute --confirm,
idempotent state, 429 backoff. Env LINEAR_API_KEY required for --execute.
Refs §C-3."

# If deps changed:
git add requirements.txt pyproject.toml
git commit -m "build: httpx dep for Linear migration"

git add docs/operations/linear-migration-runbook.md
git commit -m "docs(ops): Linear migration runbook"

# Gitignore state files
git add .gitignore
git commit -m "chore: ignore Linear migration state files"
```

Step 6 — Codex 2× clean (P1)
Round 01 then Round 02. Codex attention:
- API key only env var, never logged
- Exponential backoff capped (no infinite loop)
- Idempotency: re-run doesn't dupe
- GraphQL variables (httpx params), not string concat
- Failed mutations log retry-able payload

```bash
codex review --base main 2>&1 | tee .autopilot/state/c-3/codex/round-01.txt
# fix → re-run verify → round 02
```

Circuit breakers: standard + SECRET_IN_PAYLOAD/LOG, SCRIPT_RUNS_LIVE (autopilot never invokes --execute), STATE_FILE_COMMITTED (.dryrun-ok/.linear_migrate_state.json in .gitignore).

Final report (READY) per template Variant A. Founder runs --execute manually post-merge per runbook.

Begin with Pre-flight, then Step 1.
