Task: ops-dashboard C-4 — Railway /ops-dashboard.json endpoint (Linear + GitHub aggregator)
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/ops-dashboard-railway-endpoint`, Codex 2× consecutive clean (P1), STOP_AT_READY.

Risk tier:          P1 (new service + secrets)
Codex review:       2x_consecutive_clean

Context: FastAPI service on Railway aggregating Linear GraphQL + GitHub REST. TTL cache 60s, last-good fallback. Dashboard polls JSON instead of raw.githubusercontent.com.

Scope: (a) `ops_api/` package (FastAPI), (b) tests, (c) Railway config, (d) `scripts/build-dashboard.py` HTML_LIVE_JS RAW_URL → DATA_URL. NO migration script changes (C-3).

Required reading:
1. Plan §C-4
2. Existing FastAPI services in repo for style match
3. `scripts/build-dashboard.py` HTML_LIVE_JS polling

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current
git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check && pytest tests/ -v
test ! -d ops_api/ || echo "WARN: ops_api/ already exists"
```

Anti-patterns: force-push, type:ignore, hard-code secrets, sync blocking calls to upstream, cache bypass on every request, log API keys, return raw upstream payload.

Step 1 — Branch
```bash
git checkout -b feat/ops-dashboard-railway-endpoint
mkdir -p .autopilot/state/c-4/codex
```

Step 2 — TDD `tests/ops_api/test_dashboard_endpoint.py`
Coverage:
- `test_endpoint_returns_documented_schema` (§C-4 top-level keys)
- `test_cache_hit_within_ttl` (httpx_mock: 1 upstream call for 2 requests within TTL)
- `test_cache_miss_after_ttl`
- `test_linear_down_serves_last_good` → `sources_status.linear = "stale"`
- `test_github_down_serves_last_good`
- `test_both_down_no_last_good` → 503 with reason
- `test_etag_header_present` (sha256 of payload)
- `test_phases_from_linear_projects` (projects filter startsWith "P")
- `test_no_secrets_in_response`
- `test_logging_no_secrets` (caplog)

Tests MUST fail. Commit fixtures + tests separately.

Step 3 — Implement `ops_api/` package
```
ops_api/
  __init__.py
  main.py            # FastAPI, /ops-dashboard.json, /healthz
  linear_client.py   # async httpx, PhaseProgress + ActiveCycle queries
  github_client.py   # async httpx, PRs + check_runs
  cache.py           # TTL memory + disk last-good
  schema.py          # Pydantic models per §C-4
  config.py          # Settings (env: LINEAR_API_KEY, GITHUB_TOKEN, CACHE_TTL_SECONDS, LAST_GOOD_PATH)
```

Run tests pass:
```bash
pytest tests/ops_api/ -v
```

Step 4 — Refactor dashboard.html polling
Edit `scripts/build-dashboard.py` HTML_LIVE_JS:
```javascript
// Before: var RAW_URL = 'https://raw.githubusercontent.com/...';
// After:  var DATA_URL = location.origin + '/ops-dashboard.json';
```
Replace `refreshDashboardDOM` with `refreshDashboardData` that parses JSON + re-renders data-driven sections (preserves A-P1-4 script-safe swap for static shell).

Rebuild: `python scripts/build-dashboard.py`

Step 5 — Railway config
`railway.toml` (or match existing repo pattern):
```toml
[[services]]
name = "ops-api"
build = { command = "pip install -r requirements.txt" }
deploy = { startCommand = "uvicorn ops_api.main:app --host 0.0.0.0 --port $PORT" }
```
Document env vars in `docs/operations/ops-api-deploy.md`: LINEAR_API_KEY, GITHUB_TOKEN, CACHE_TTL_SECONDS (60), LAST_GOOD_PATH (/tmp/...), SENTRY_DSN (optional).

Step 6 — Local verify
```bash
ruff check ops_api/ && black --check ops_api/ && mypy ops_api/ && pytest tests/ -v
# Boot smoke
LINEAR_API_KEY=dummy GITHUB_TOKEN=dummy uvicorn ops_api.main:app --port 8001 &
sleep 2
curl -s http://localhost:8001/healthz | grep -q '"status":"ok"'
kill %1
```

Atomic commits:
```bash
git add ops_api/
git commit -m "feat(ops-api): FastAPI /ops-dashboard.json aggregator

TTL cache (60s default), last-good fallback, ETag, healthz. Schema §C-4."

git add requirements.txt pyproject.toml  # if deps
git commit -m "build: fastapi/uvicorn/pytest-httpx for ops-api"

git add scripts/build-dashboard.py docs/dashboard.html docs/dashboard.md docs/dashboard.json
git commit -m "feat(ops-dashboard): poll /ops-dashboard.json instead of raw.githubusercontent"

git add railway.toml docs/operations/ops-api-deploy.md
git commit -m "ops(railway): ops-api service config + deploy doc"
```

Step 7 — Codex 2× clean (P1)
Codex attention: API key not logged, ETag over body, TTL race-safe, last-good schema-validated, async timeout on httpx.

```bash
codex review --base main 2>&1 | tee .autopilot/state/c-4/codex/round-01.txt
# fix → round 02
```

Circuit breakers: standard + SECRET_IN_PAYLOAD, CACHE_BYPASS, SCHEMA_DRIFT.

Final report (READY) per template. Founder deploys to Railway manually post-merge.

Begin with Pre-flight, then Step 1.
