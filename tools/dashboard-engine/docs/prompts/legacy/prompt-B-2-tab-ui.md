Task: ops-dashboard B-2 — 5-tab UI rendering (Overview/Features/PRs/Risks/Docs)
Working dir: /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `feat/ops-dashboard-tab-ui`, Codex 1× clean, STOP_AT_READY.

Risk tier: P2 mature

Context: Render dashboard.json into 5 tabs with vanilla JS. localStorage remembers active tab. Depends on B-1 (parsers + dashboard.json) + A-P1-4 (script-safe DOM swap for tab init re-execution).

Scope: rendering + inline JS only. No external libs. NO parser changes.

Required reading: plan §B-2 (layout, each tab spec), §B-3 (JSON schema), `scripts/build-dashboard.py` rendering, `docs/dashboard.json`.

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current; git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check && pytest tests/ -v
python -c "import json; d=json.load(open('docs/dashboard.json')); assert 'features' in d"   # B-1 merged
grep -q "replaceChild" scripts/build-dashboard.py   # A-P1-4 merged
```
Deps unmerged → HALT.

Anti-patterns: force-push, type:ignore, add React/Vue/Alpine, eval/new Function (XSS), unescaped data via innerHTML, touch parsers, break responsive.

Step 1 — Branch
```bash
git checkout -b feat/ops-dashboard-tab-ui
mkdir -p .autopilot/state/b-2/codex
```

Step 2 — TDD `tests/scripts/test_dashboard_render.py`
- `test_render_5_tabs` (Overview, Features, PRs, Risks, Docs)
- `test_render_overview_progress_bars` (N matches phases count)
- `test_render_features_matrix_status_emoji`
- `test_render_prs_filter_buttons` (All/In-progress/Blocked/Merged)
- `test_render_risks_severity_class`
- `test_render_docs_staleness_class`
- `test_no_xss_in_feature_name` (escape_html on `<script>`)
- `test_localstorage_tab_init_js_present`

Tests fail first.

Step 3 — Implement rendering
Functions: `render_tab_bar`, `render_overview_tab`, `render_features_tab`, `render_prs_tab` (filter + search), `render_risks_tab`, `render_docs_tab`, `render_tab_switcher_js`, `escape_html`.

Tab switcher JS (vanilla ES5):
```javascript
(function() {
  var tabs = document.querySelectorAll('.tab-bar [data-tab]');
  var panels = document.querySelectorAll('.tab-panel');
  function activate(name) {
    tabs.forEach(function(t) { t.classList.toggle('active', t.dataset.tab === name); });
    panels.forEach(function(p) { p.classList.toggle('active', p.id === 'tab-' + name); });
    try { localStorage.setItem('activeTab', name); } catch (e) {}
  }
  tabs.forEach(function(t) { t.addEventListener('click', function() { activate(t.dataset.tab); }); });
  var saved; try { saved = localStorage.getItem('activeTab'); } catch (e) {}
  activate(saved || 'overview');
})();
```
Responsive: CSS media query → dropdown ≤640px.

Run tests pass.

Step 4 — Rebuild + verify
```bash
python scripts/build-dashboard.py
grep -c 'data-tab=' docs/dashboard.html       # ≥5
grep -c 'tab-panel' docs/dashboard.html        # ≥5
grep -c 'localStorage' docs/dashboard.html     # ≥1
```

Step 5 — Local verify
```bash
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
```

Commits:
```bash
git add tests/scripts/test_dashboard_render.py
git commit -m "test(dashboard-render): failing tests for 5-tab UI + XSS guard"

git add scripts/
git commit -m "feat(dashboard): 5-tab UI rendering

Vanilla JS switcher + localStorage + responsive collapse. XSS-safe via escape_html.
Refs §B-2."

git add docs/dashboard.html docs/dashboard.md
git commit -m "build(dashboard): regenerated with 5-tab UI"
```

Step 6 — Codex 1× clean
Attention: escape_html on ALL data paths (grep verify), tab switcher re-runs after A-P1-4 swap, localStorage failure mode (private mode), responsive baseline.

Circuit breakers: standard + UNESCAPED_INTERPOLATION, FRAMEWORK_INTRODUCED, LISTENER_LEAK.

Final report (READY).

Begin with Pre-flight, then Step 1.
