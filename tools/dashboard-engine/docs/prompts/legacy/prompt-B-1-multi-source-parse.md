Task: ops-dashboard B-1 — multi-source parser (roadmap + doc versions)
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/ops-dashboard-multi-source-parse`, Codex 1× clean (P2 mature), STOP_AT_READY.

Risk tier: P2 mature

Context: Add roadmap.md §1/§2/§6/§7/§8 parsing + doc version-header parsing. Emit dashboard.json intermediate.

Scope: parser functions in `scripts/build-dashboard.py` (or split to `scripts/dashboard/`), dashboard.json emit, parser unit tests with real fixture slices. NO tab UI (B-2). NO Linear integration (C-4 imports parser output).

Required reading: plan §B-1, §B-3 (JSON schema), §C-6 (don't mutate roadmap.md), `docs/mymoneywent-roadmap.md` §1-§8, doc headers BRD/PRD/TDD.

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current; git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check && pytest tests/ -v
```

Anti-patterns: force-push, type:ignore, mutate `docs/mymoneywent-roadmap.md`, edit `docs/dashboard.{html,md,json}` directly, brittle regex, synthesize parser fixtures (use real captured).

Step 1 — Branch
```bash
git checkout -b feat/ops-dashboard-multi-source-parse
mkdir -p .autopilot/state/b-1/codex
```

Step 2 — TDD `tests/scripts/test_dashboard_parsers.py`
Coverage:
- `test_parse_roadmap_section_1_overall_progress`
- `test_parse_roadmap_section_2_features`
- `test_parse_roadmap_section_6_blockers`
- `test_parse_roadmap_section_7_risks`
- `test_parse_roadmap_section_8_metrics`
- `test_parse_doc_version_header`
- `test_doc_staleness_thresholds` (yellow >7d, red >14d)
- `test_merge_tracker_plus_roadmap`
- `test_dashboard_json_schema_complete` (top-level keys: generated_at, overall, phases, features, blockers, risks, docs)

Real fixtures (frozen captures in `tests/scripts/fixtures/`):
```
roadmap_section_1.md, roadmap_section_2.md, roadmap_section_6.md,
roadmap_section_7.md, roadmap_section_8.md, brd_header.md, ...
```
Tests MUST fail.

Step 3 — Implement parsers
If `build-dashboard.py` > 300 lines, split:
```
scripts/dashboard/__init__.py
scripts/dashboard/parse_tracker.py  # existing
scripts/dashboard/parse_roadmap.py  # NEW
scripts/dashboard/parse_docs.py     # NEW
scripts/dashboard/render.py
```
Functions: `parse_roadmap_overall_progress`, `parse_roadmap_features`, `parse_roadmap_blockers`, `parse_roadmap_risks`, `parse_doc_version_header`, `compute_staleness`, `build_dashboard_json`.

Run tests pass.

Step 4 — Emit `dashboard.json`
In build-dashboard.py after parsing:
```python
output = build_dashboard_json(tracker_data, roadmap_data, doc_versions)
Path("docs/dashboard.json").write_text(json.dumps(output, indent=2, default=str, sort_keys=True))
```
Run `python scripts/build-dashboard.py`. Verify valid JSON.

Step 5 — Pre-commit hook trigger update `.pre-commit-config.yaml`:
```yaml
- id: build-dashboard
  files: ^(docs/implementation-tracker\.md|docs/mymoneywent-roadmap\.md|docs/brd-vi\.md|docs/prd-vi\.md|docs/tdd-vi\.md|scripts/build-dashboard\.py|scripts/dashboard/.*\.py)$
```

Step 6 — Local verify
```bash
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
pre-commit run --all-files build-dashboard
```

Commits:
```bash
git add tests/scripts/test_dashboard_parsers.py tests/scripts/fixtures/
git commit -m "test(dashboard-parser): failing tests + real fixtures"

git add scripts/
git commit -m "feat(dashboard): multi-source parser — roadmap + doc versions

Parses §1/§2/§6/§7/§8 + Version/Updated headers. Refs §B-1."

git add docs/dashboard.json docs/dashboard.html docs/dashboard.md
git commit -m "build(dashboard): regenerated artifacts with multi-source"

git add .pre-commit-config.yaml
git commit -m "ci: expand build-dashboard trigger"
```

Step 7 — Codex 1× clean
Attention: regex tolerance, no roadmap mutation, UTC staleness, deterministic JSON order.

Circuit breakers: standard + ROADMAP_MUTATED, PARSER_BRITTLE (heredoc fixtures), SCHEMA_DRIFT.

Final report (READY).

Begin with Pre-flight, then Step 1.
