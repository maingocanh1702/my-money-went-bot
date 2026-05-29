Task: ops-dashboard A-P0 — adaptive polling rate limit + rename explainer + cross-refs
You are working in /Users/maingocanh/Projects/MyMoneyWent. NO prior context. Self-contained.

Mode: AUTOPILOT — branch `fix/ops-dashboard-a-p0`, Codex 1× clean, then STOP_AT_READY.

Risk tier:          P2 mature
Merge policy:       manual_only
Codex review:       1x_clean

Context (NOT for execution):
Internal ops tracker dashboard polls raw.githubusercontent.com every 30s → unauth 60/hr limit hits after 30 min. Also `dashboard-realtime-explained.md` collides naming-wise with `web-dashboard/` (user-facing). Plan §A-P0 fixes both.

Scope: ONLY (a) adaptive POLL_INTERVAL_MS in `scripts/build-dashboard.py` HTML_LIVE_JS; (b) rename `docs/operations/dashboard-realtime-explained.md` → `docs/operations/ops-tracker-dashboard-explained.md` + disclaimer + cross-ref updates. NO: dashboard rendering, multi-source parser, Railway endpoint, web-dashboard/.

Required reading:
1. `docs/operations/ops-tracker-dashboard-improve.md` §A-P0
2. `scripts/build-dashboard.py` — locate `HTML_LIVE_JS` and `POLL_INTERVAL_MS = 30000`
3. Memory `feedback_never_auto_delete_docs.md` — use `git mv`, not rm

Pre-flight:
```bash
cd /Users/maingocanh/Projects/MyMoneyWent
ls .git/*.lock 2>/dev/null
git status                          # MUST clean
git branch --show-current           # MUST main
git fetch origin && git pull --ff-only origin main
source .venv/bin/activate
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
```
ALL pass or HALT.

Anti-patterns:
* `git push --force`
* `# type: ignore`
* `rm` or Write to delete .md (use `git mv`)
* Touch out-of-scope files

Step 1 — Branch
```bash
git checkout -b fix/ops-dashboard-a-p0
mkdir -p .autopilot/state/a-p0/codex
```

Step 2 — Adaptive POLL_INTERVAL_MS
Edit `scripts/build-dashboard.py` HTML_LIVE_JS:
```javascript
// Before: var POLL_INTERVAL_MS = 30000;
// After:
var PAT = localStorage.getItem('github_pat');
var POLL_INTERVAL_MS = PAT ? 30000 : 120000;
```
Then `python scripts/build-dashboard.py`.
Sanity: `grep -c "POLL_INTERVAL_MS = PAT" docs/dashboard.html` ≥1.

Step 3 — Rename + disclaimer
```bash
git mv docs/operations/dashboard-realtime-explained.md docs/operations/ops-tracker-dashboard-explained.md
```
Edit new file — insert after Version block:
```
> **⚠️ INTERNAL development tracker dashboard** — KHÔNG phải user-facing.
> User-facing: [web-dashboard/](../../web-dashboard/).
```

Step 4 — Update cross-refs
```bash
grep -rln "dashboard-realtime-explained" docs/ --include="*.md"
```
Replace each occurrence with `ops-tracker-dashboard-explained`. After:
```bash
grep -rn "dashboard-realtime-explained" docs/ --include="*.md" | wc -l   # MUST 0
```

Step 5 — Local verify
```bash
ruff check scripts/ && black --check scripts/ && pytest tests/ -v
```

Atomic commits:
```bash
git add scripts/build-dashboard.py docs/dashboard.html docs/dashboard.md docs/dashboard.json
git commit -m "fix(ops-dashboard): adaptive POLL_INTERVAL_MS unauth-safe

Unauth 120s = 30 req/hr (under GitHub 60/hr). Authed 30s preserved.
Refs plan v3.1.0 §A-P0-1."

git add docs/operations/
git commit -m "docs(ops-dashboard): rename explainer + internal-vs-user disclaimer

Renamed dashboard-realtime-explained.md → ops-tracker-dashboard-explained.md.
Disclaimer header + cross-refs updated.
Refs plan v3.1.0 §A-P0-2."
```

Step 6 — Codex review (1× clean for P2 mature)
```bash
codex review --base main 2>&1 | tee .autopilot/state/a-p0/codex/round-01.txt
```
Clean → STOP_AT_READY. Findings → fix atomically + re-run (MAX 3 rounds). ARCH/SECURITY/RECURRING → HALT.

Merge gate: STOP_AT_READY. Branch intact.

Circuit breakers: pre-flight regression, VERIFY_REGRESSION, ARCH_FINDING, SECURITY_FINDING, RECURRING_FINDING, TYPE_IGNORE_PROPOSED, MAX_ROUNDS, tool error 2×, context >70%, POLICY_MISMATCH, DESTRUCTIVE_DOC_OP, CROSS_REF_LEAK (grep >0).

Halt report template per autopilot-prompt-template §3.14.

Final report (READY):
```
═══════════════════════════════════════════════════════
AUTOPILOT A-P0 — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════
Squash commit:    N/A
Branch fix/ops-dashboard-a-p0:  intact
Push origin/main: NOT RUN

Files: scripts/build-dashboard.py, docs/dashboard.{html,md,json}
Renamed: dashboard-realtime-explained.md → ops-tracker-dashboard-explained.md

Codex: Round 01: <findings | clean>
Verify: ruff/black/pytest clean; grep cross-refs = 0

Suggested squash:
  git checkout main && git pull --ff-only origin main
  git merge --squash fix/ops-dashboard-a-p0
  git commit -m "fix(ops-dashboard): rate limit + naming clarity (§A-P0)"
  git branch -D fix/ops-dashboard-a-p0 && git push origin main
═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1.
