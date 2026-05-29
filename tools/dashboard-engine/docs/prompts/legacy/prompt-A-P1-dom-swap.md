Task: ops-dashboard A-P1-4 — script-safe DOM swap (replaceChild + script re-execution)
You are working in /Users/maingocanh/Projects/MyMoneyWent. NO prior context.

Mode: AUTOPILOT — branch `fix/ops-dashboard-dom-swap`, Codex 1× clean, STOP_AT_READY.

Risk tier:          P2 mature
Merge policy:       manual_only

Context: `refreshDashboardDOM()` uses innerHTML swap which drops `<script>` tags. B-2 will add inline scripts; without this fix B-2 silently breaks. RAW_URL change is superseded by C-4 → skip.

Scope: ONLY refactor `refreshDashboardDOM()` in HTML_LIVE_JS to use `parentNode.replaceChild` + manual script re-execution + scrollY preserve. Do NOT touch RAW_URL.

Required reading:
1. `docs/operations/ops-tracker-dashboard-improve.md` §A-P1-4
2. `scripts/build-dashboard.py` — find `refreshDashboardDOM` in HTML_LIVE_JS

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status; git branch --show-current   # clean / main
git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
```

Anti-patterns: force-push, type:ignore, touch RAW_URL, edit dashboard.html directly, add JS libs.

Step 1 — Branch
```bash
git checkout -b fix/ops-dashboard-dom-swap
mkdir -p .autopilot/state/a-p1-4/codex
```

Step 2 — Refactor refreshDashboardDOM
Replace function body with:
```javascript
function refreshDashboardDOM() {
  return fetch(RAW_URL, { cache: 'no-store' })
    .then(function(r) { return r.text(); })
    .then(function(text) {
      var parser = new DOMParser();
      var newDoc = parser.parseFromString(text, 'text/html');
      var newContainer = newDoc.querySelector('.container');
      var oldContainer = document.querySelector('.container');
      if (newContainer && oldContainer) {
        var scrollY = window.scrollY;
        var clone = document.importNode(newContainer, true);
        oldContainer.parentNode.replaceChild(clone, oldContainer);
        clone.querySelectorAll('script').forEach(function(oldScript) {
          var newScript = document.createElement('script');
          for (var i = 0; i < oldScript.attributes.length; i++) {
            var attr = oldScript.attributes[i];
            newScript.setAttribute(attr.name, attr.value);
          }
          newScript.textContent = oldScript.textContent;
          oldScript.parentNode.replaceChild(newScript, oldScript);
        });
        window.scrollTo(0, scrollY);
      }
    });
}
```

Step 3 — Rebuild + verify
```bash
python scripts/build-dashboard.py
grep -c "replaceChild" docs/dashboard.html       # ≥2
grep -c "innerHTML = newContainer" docs/dashboard.html  # 0
```
Mismatch → investigate before proceeding.

Step 4 — Local verify
```bash
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
```

Commit:
```bash
git add scripts/build-dashboard.py docs/dashboard.html docs/dashboard.md docs/dashboard.json
git commit -m "fix(ops-dashboard): script-safe DOM swap via replaceChild

Replace innerHTML swap (drops <script>) with importNode + replaceChild
+ manual script re-execution loop + scrollY preserve.
Prepares B-2 tab UI inline scripts. Refs §A-P1-4."
```

Step 5 — Codex 1× clean
```bash
codex review --base main 2>&1 | tee .autopilot/state/a-p1-4/codex/round-01.txt
```
MAX_ROUNDS=3. ARCH/SECURITY → HALT.

Merge gate: STOP_AT_READY.

Circuit breakers: standard universal set + SCOPE_CREEP (RAW_URL modified), DEPENDENCY_ADDED.

Final report (READY):
```
═══════════════════════════════════════════════════════
AUTOPILOT A-P1-4 — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════
Branch fix/ops-dashboard-dom-swap: intact
Files: scripts/build-dashboard.py, docs/dashboard.{html,md,json}
Codex: Round 01: <findings | clean>
Verify: replaceChild ≥2, innerHTML container swap = 0

Suggested squash:
  git checkout main && git pull --ff-only origin main
  git merge --squash fix/ops-dashboard-dom-swap
  git commit -m "fix(ops-dashboard): script-safe DOM swap (§A-P1-4)"
  git branch -D fix/ops-dashboard-dom-swap && git push origin main
═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1.
