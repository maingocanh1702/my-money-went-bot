# Autopilot — dashboard-realtime

> Generated 2026-05-13. Single-phase autopilot prompt per memory rule
> `feedback_autopilot_prompt_scope` (single-phase ăn chắc hơn multi-phase) and
> `feedback_prefer_autopilot_prompts` (≥2-file change → autopilot, không manual).

---

Task: dashboard-realtime — auto-rebuild on tracker change + git-derived PR status detection.

You are working in `/Users/maingocanh/Projects/MyMoneyWent`. This is a Telegram/Discord bot SaaS for expense tracking, currently in Phase 1 foundation. NO prior conversation context. This prompt is self-contained.

Mode: AUTOPILOT — single feature branch `feat/dashboard-realtime`, Codex 1× clean (P2 pilot per merge policy), then STOP_AT_READY. Pause ONLY on circuit-breaker conditions.

```
Risk tier:          P2
Merge policy:       manual_only
Autopilot maturity: pilot
Codex review:       1x_clean
```

---

## Context (NOT for execution, background)

`scripts/build-dashboard.py` currently builds `docs/dashboard.html` + `docs/dashboard.md` from `docs/implementation-tracker.md` only when founder runs the script manually. Two pain points:

1. Tracker can be edited without rebuilding outputs → dashboard stale.
2. Tracker status emojis (🟠/⬜) drift from reality (branch exists with commits but row still says ⬜). Founder discovered this 2026-05-13 when dashboard rendered F07 as ❌ Blocked while branch had Codex-review WIP commits.

Goal: make dashboard reactive to both file changes (build trigger) and underlying git reality (status enrichment).

## Scope discipline

**Positive scope:**
- Pre-commit hook that auto-rebuilds dashboard when `docs/implementation-tracker.md` OR `scripts/build-dashboard.py` are staged.
- GitHub Action workflow `.github/workflows/dashboard.yml` that rebuilds + commits back on push to `main` when those same files change.
- Extend `scripts/build-dashboard.py` with `detect_git_state(branch, pr_id)` function that infers active status from local + remote branch existence and commit count ahead of `main`.
- Reconciliation rule: tracker is source-of-truth for ✅ merged / ⏸️ deferred / ❌ blocked; git reality wins for ⬜ → 🟡/🟠 transitions.
- Unit tests covering parser + git-state inference (mocked subprocess).
- Update `START_HERE.md` + `development-workflow.md` §2.7 with new behavior.

**Negative scope (do NOT touch):**
- Dashboard HTML/MD layout, CSS, or rendering structure (separate concern).
- `implementation-tracker.md` content semantics (row text, gates, status emojis stay manual).
- GitHub Personal Access Token integration, GitHub API live fetch, Cowork artifact (Tier 4 deferred, explicitly declined by founder in selection).

**Out-of-scope but documented:**
- Live in-browser GitHub API fetch — defer to future PR if founder asks.

## Required reading (READ FIRST, in this order, before any code)

1. `scripts/build-dashboard.py` — existing parser + renderer (~500 lines). Focus on `parse_prs`, `_find_emoji`, `STATUS_MAP`, `IN_FLIGHT_STATUSES`, `current_branch()`.
2. `docs/implementation-tracker.md` lines 44–127 — `### Phase N:` heading + table format. Note `branch` cell uses backticks.
3. `.pre-commit-config.yaml` — existing hook structure (ruff, black, mypy, detect-secrets).
4. `.github/workflows/ci.yml` — Python 3.11, install pattern (`pip install -r requirements.txt` + `pip install -e ".[dev]"`).
5. `docs/operations/development-workflow.md` §2.7 (line 155) — Post-merge updates currently say "run `python scripts/build-dashboard.py` after merge". This becomes obsolete after this prompt — update text accordingly.
6. Memory `feedback_auto_gen_views_surface_drift` — pattern: auto-gen views expose source-of-truth drift; fix source, don't workaround in view. Reconciliation rule must respect this.

## Pre-flight gate

```bash
cd /Users/maingocanh/Projects/MyMoneyWent

git status                              # MUST be clean
git branch --show-current               # MUST be: main
git fetch origin && git pull --ff-only origin main
git log --oneline -3                    # Expected HEAD includes recent tracker + dashboard work

source .venv/bin/activate
which python pytest pre-commit lint-imports codex

ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v                        # MUST be green (118 passed baseline)

python scripts/build-dashboard.py       # MUST emit 2 files, exit 0
```

ALL must pass. If any fails → HALT and report. Do not proceed.

## Anti-patterns (NEVER do)

* `git push --force`.
* Add `# type: ignore` (circuit breaker — founder approval needed).
* Auto-merge to main (P2 pilot = `manual_only` per §3.2 risk header).
* Touch tracker.md row content, dashboard HTML/MD layout, or CSS (out-of-scope).
* Fetch external APIs from pre-commit hook (slow + breaks offline). Git CLI only.
* Embed GitHub PAT or any secret in workflow file. Use `${{ secrets.GITHUB_TOKEN }}` only, with `permissions: contents: write`.
* Use synthetic fixtures for git-state unit tests. Mock `subprocess.run` directly with return codes + stdout strings that mirror real `git` output.
* Add `dashboard.html` / `dashboard.md` to pre-commit's `exclude:` list — they MUST be auto-staged when regenerated.

## Numbered steps

### Step 1 — Branch + state directory

```bash
git checkout -b feat/dashboard-realtime
git rev-parse HEAD > /tmp/dashboard-realtime-base-sha.txt
mkdir -p .autopilot/state/dashboard-realtime/codex
```

### Step 2 — Write failing unit tests (TDD)

Create `tests/unit/test_build_dashboard.py`:

```python
"""Tests for scripts/build-dashboard.py — parser + git-state detection."""
from unittest.mock import patch, MagicMock
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_dashboard", ROOT / "scripts" / "build-dashboard.py"
)
bd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bd)


def test_parse_phase_block_extracts_status_emoji():
    text = """### Phase 1: Foundation
| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| W0.7 | Wave 0 | request_id | ✅ | `chore/W0.7` | 🔒X | done |
| W1.1 | Wave 0 | Docker | ⬜ | `infra/W1.1` | 🔒X | next |
"""
    prs = bd.parse_prs(text)
    assert len(prs) == 2
    assert prs[0].pr_id == "W0.7" and prs[0].status_slug == "merged"
    assert prs[1].pr_id == "W1.1" and prs[1].status_slug == "not-started"


def test_detect_git_state_branch_missing_no_merge():
    """No branch + no merge commit → return None (let tracker win)."""
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        result = bd.detect_git_state("feat/foo", "F99")
        assert result == (None, "")


def test_detect_git_state_branch_exists_with_commits():
    """Branch exists + 3 commits ahead → in-progress."""
    def fake_run(cmd, **kwargs):
        if "rev-parse" in cmd and "--verify" in cmd:
            return MagicMock(returncode=0, stdout="abc123\n")
        if "rev-list" in cmd and "--count" in cmd:
            return MagicMock(returncode=0, stdout="3\n")
        if "log" in cmd and "--grep" in cmd:
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", side_effect=fake_run):
        slug, reason = bd.detect_git_state("feat/F07-settings", "F07")
        assert slug == "in-progress"
        assert "3 commits" in reason


def test_detect_git_state_branch_with_fix_commits_is_in_review():
    """Branch with ≥3 commits AND ≥1 `fix(` commit → in-review (Codex round)."""
    def fake_run(cmd, **kwargs):
        if "rev-parse" in cmd and "--verify" in cmd:
            return MagicMock(returncode=0, stdout="abc\n")
        if "rev-list" in cmd:
            return MagicMock(returncode=0, stdout="4\n")
        if "log" in cmd and "--grep=^fix" in " ".join(cmd):
            return MagicMock(returncode=0, stdout="def fix(F07): something\n")
        if "log" in cmd:
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", side_effect=fake_run):
        slug, reason = bd.detect_git_state("feat/F07-settings", "F07")
        assert slug == "in-review"


def test_reconcile_tracker_wins_for_terminal_states():
    """Tracker ✅ / ⏸️ / ❌ NEVER overridden by git inference."""
    for terminal in ("merged", "deferred", "blocked"):
        result = bd.reconcile_status(tracker_slug=terminal, git_slug="in-progress")
        assert result == terminal, f"{terminal} must not be overridden"


def test_reconcile_git_wins_when_tracker_says_not_started():
    """⬜ Not started + git shows commits → use git's slug (reality wins)."""
    assert bd.reconcile_status("not-started", "in-progress") == "in-progress"
    assert bd.reconcile_status("not-started", "in-review") == "in-review"


def test_reconcile_tracker_wins_when_more_specific():
    """🟠 In review (founder-set) NOT downgraded by git's 🟡 in-progress heuristic."""
    assert bd.reconcile_status("in-review", "in-progress") == "in-review"
```

Run pytest — these 7 tests MUST FAIL on current main (functions don't exist yet).

```bash
pytest tests/unit/test_build_dashboard.py -v
# Expect: 7 failed (collection or attr errors)
```

If tests pass on first run → something's off. Investigate before proceeding.

### Step 3 — Implement `detect_git_state` + `reconcile_status`

Edit `scripts/build-dashboard.py`. Add at module level (near `current_branch()`):

```python
def detect_git_state(branch: str, pr_id: str) -> tuple[str | None, str]:
    """Infer PR status from git reality.

    Returns (status_slug, reason) or (None, "") if can't determine.

    Heuristics:
      - Branch missing locally + remote + no main commit matching pr_id → (None, "")
      - Main has commit matching pr_id → ("merged", reason)
      - Branch exists but no commits ahead → ("not-started", "branch scaffolded only")
      - Branch with ≥3 commits AND ≥1 `fix(` commit → ("in-review", reason)
      - Branch with ≥1 commit ahead → ("in-progress", reason)
    """
    if not branch:
        return None, ""

    def git(*args: str) -> tuple[int, str]:
        try:
            r = subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=5
            )
            return r.returncode, r.stdout.strip()
        except Exception:
            return 1, ""

    local_rc, _ = git("rev-parse", "--verify", branch)
    remote_rc, _ = git("rev-parse", "--verify", f"origin/{branch}")
    has_branch = local_rc == 0 or remote_rc == 0

    if not has_branch:
        rc, out = git("log", "--oneline", f"--grep={pr_id}", "main", "-5")
        if rc == 0 and out:
            return "merged", f"main has commit matching {pr_id}"
        return None, ""

    ref = branch if local_rc == 0 else f"origin/{branch}"
    rc, count_str = git("rev-list", "--count", f"main..{ref}")
    ahead = int(count_str) if count_str.isdigit() else 0
    if ahead == 0:
        return "not-started", "branch exists but no commits ahead of main"

    rc, fix_out = git("log", "--oneline", "--grep=^fix", f"main..{ref}")
    has_fix = bool(fix_out) and rc == 0
    if ahead >= 3 and has_fix:
        return "in-review", f"{ahead} commits, ≥1 fix commit → Codex round"
    return "in-progress", f"{ahead} commits ahead of main"


# Reconciliation rule: tracker is source-of-truth for terminal/founder-set states;
# git reality wins for unstarted → started transitions.
_TERMINAL = {"merged", "deferred", "blocked", "ready"}
_GIT_RANK = {"not-started": 0, "in-progress": 1, "in-review": 2}


def reconcile_status(tracker_slug: str, git_slug: str | None) -> str:
    """Pick the slug that best reflects reality.

    - Tracker terminal states (merged/deferred/blocked/ready) always win.
    - If tracker is more specific than git (e.g. in-review > git's in-progress
      heuristic), keep tracker.
    - Otherwise pick whichever ranks higher in _GIT_RANK.
    """
    if tracker_slug in _TERMINAL:
        return tracker_slug
    if git_slug is None:
        return tracker_slug
    t_rank = _GIT_RANK.get(tracker_slug, 0)
    g_rank = _GIT_RANK.get(git_slug, 0)
    return tracker_slug if t_rank >= g_rank else git_slug
```

Run unit tests — MUST be green:

```bash
pytest tests/unit/test_build_dashboard.py -v
# Expect: 7 passed
```

### Step 4 — Wire `detect_git_state` into `parse_prs`

In `main()` after `prs = parse_prs(text)`, add enrichment loop:

```python
    # Enrich each PR with git-derived status, then reconcile with tracker.
    drift_report: list[tuple[str, str, str, str]] = []
    for pr in prs:
        git_slug, reason = detect_git_state(pr.branch, pr.pr_id)
        if git_slug is None:
            continue
        new_slug = reconcile_status(pr.status_slug, git_slug)
        if new_slug != pr.status_slug:
            drift_report.append((pr.pr_id, pr.status_slug, new_slug, reason))
            # Update both slug and label for renderers
            label_lookup = {v[1]: v[0] for v in STATUS_MAP.values()}
            pr.status_slug = new_slug
            pr.status_label = label_lookup.get(new_slug, pr.status_label)
            # Note: status_emoji stays as tracker's emoji — single source of truth
            # for emoji is tracker file. Drift is surfaced via printed report only.

    if drift_report:
        print("\nDrift detected (tracker → reality):")
        for pr_id, old, new, reason in drift_report:
            print(f"  {pr_id:14s} {old:15s} → {new:15s} ({reason})")
        print("  (Update tracker if drift is real; otherwise dashboard reflects reality.)\n")
```

Re-run script manually to confirm output unchanged for current state (F07 already 🟠 → no drift):

```bash
python scripts/build-dashboard.py
# Expect: same MVP/in-flight/active counts, no drift report (or expected F-* drift only)
```

### Step 5 — Pre-commit hook

Append to `.pre-commit-config.yaml` (under `repos:`):

```yaml
  # ── Build dashboard from tracker (auto-stages outputs) ──
  - repo: local
    hooks:
      - id: build-dashboard
        name: Rebuild dashboard from tracker + git state
        entry: bash -c 'python scripts/build-dashboard.py && git add docs/dashboard.html docs/dashboard.md'
        language: system
        files: ^(docs/implementation-tracker\.md|scripts/build-dashboard\.py)$
        pass_filenames: false
        require_serial: true
```

Test:

```bash
# Trigger by touching tracker
echo "" >> docs/implementation-tracker.md
git add docs/implementation-tracker.md
pre-commit run build-dashboard
# Expect: hook runs, regenerates outputs, stages them
git restore --staged docs/implementation-tracker.md docs/dashboard.html docs/dashboard.md
git checkout -- docs/implementation-tracker.md docs/dashboard.html docs/dashboard.md
```

### Step 6 — GitHub Action workflow

Create `.github/workflows/dashboard.yml`:

```yaml
name: Rebuild dashboard

on:
  push:
    branches: [main]
    paths:
      - 'docs/implementation-tracker.md'
      - 'scripts/build-dashboard.py'

jobs:
  rebuild:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Build dashboard
        run: python scripts/build-dashboard.py

      - name: Commit if outputs changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          if [[ -n "$(git status --porcelain docs/dashboard.html docs/dashboard.md)" ]]; then
            git add docs/dashboard.html docs/dashboard.md
            git commit -m "chore(dashboard): auto-rebuild from $(git log -1 --format=%h)"
            git push origin main
          else
            echo "No dashboard drift — outputs already in sync."
          fi
```

### Step 7 — Doc updates

Edit `docs/operations/development-workflow.md` §2.7 Post-merge updates:

```diff
- Chạy `python scripts/build-dashboard.py` để regenerate `docs/dashboard.html` + `docs/dashboard.md` từ tracker (snapshot view dùng cho daily check + onboarding).
+ Dashboard auto-rebuild: pre-commit hook rebuilds locally when tracker.md is staged; GitHub Action rebuilds + commits back on push to main. Manual rebuild `python scripts/build-dashboard.py` still works for ad-hoc refresh and surfaces drift report (tracker emoji vs git reality).
```

Edit `docs/START_HERE.md` Source-of-truth table:

```diff
- | Visual snapshot | `dashboard.html` / `dashboard.md` (auto-gen từ tracker) | — không edit trực tiếp |
+ | Visual snapshot | `dashboard.html` / `dashboard.md` (auto-rebuild on tracker change via pre-commit + GH Action; git state enriches stale tracker rows) | — không edit trực tiếp |
```

### Step 8 — Full local verify

```bash
ruff check .
black --check .
mypy core/ markets/ scripts/
lint-imports
pytest tests/ -v
pre-commit run --all-files
```

All MUST be green.

### Step 9 — Inline Codex review (P2 pilot → 1 round)

```bash
codex review --base main 2>&1 | tee .autopilot/state/dashboard-realtime/codex/round-01.txt
```

Parse output:
* "No issues" / "clean" → 1× clean achieved, proceed to READY report.
* Findings present → categorize:
  - P0/P1 → fix this round, re-run verify, then `codex review --commit HEAD` for mini-review (max 1 retry).
  - P2 → fix opportunistically.
  - Keywords `auth|token|secret|injection` → SECURITY_FINDING circuit breaker → HALT.
  - Keywords `schema|migration|breaking` → ARCH_FINDING circuit breaker → HALT.
* Same finding hash twice → RECURRING_FINDING circuit breaker → HALT.

## Atomic commit plan

```bash
git add tests/unit/test_build_dashboard.py
git commit -m "test(dashboard): cover parser + git-state detection + reconcile rule"

git add scripts/build-dashboard.py
git commit -m "feat(dashboard): detect_git_state + reconcile_status from git reality"

git add .pre-commit-config.yaml
git commit -m "chore(precommit): auto-rebuild dashboard when tracker or script changes"

git add .github/workflows/dashboard.yml
git commit -m "ci(dashboard): rebuild + commit back on push to main"

git add docs/operations/development-workflow.md docs/START_HERE.md
git commit -m "docs(dashboard): document auto-rebuild + drift surfacing"

# After Codex review pass, if fix commits needed:
# git commit -m "fix(dashboard): address codex round 01 — <summary>"
```

## Circuit breakers

1. Pre-flight regression — existing tests no longer pass on main.
2. TDD oracle violated — Step 2 tests pass on first run (before Step 3 impl exists).
3. VERIFY_REGRESSION — local verify fails twice consecutively.
4. ARCH_FINDING — Codex flags schema/breaking/architectural.
5. SECURITY_FINDING — Codex flags auth/token/timing/secret/injection.
6. RECURRING_FINDING — same hash in round 01 AND round 02 (if retry happens).
7. TYPE_IGNORE_PROPOSED — anywhere.
8. MAX_ROUNDS — Codex round 01 not clean AND fix retry round 02 also not clean.
9. Tool error twice in a row on git/codex/pytest.
10. Context budget >70% — pause + report.
11. POLICY_MISMATCH — auto-merge attempted (this prompt is `manual_only`).
12. **GIT_DETECT_AMBIGUOUS (task-specific)** — `detect_git_state` returns a slug that conflicts with terminal tracker state for >2 PRs (e.g., tracker says ✅ merged but branch still has commits ahead of main). Likely indicates tracker hasn't been updated post-merge → HALT for founder triage.
13. **GH_ACTION_PERMISSION_DENIED (task-specific)** — if dry-run of workflow fails because `GITHUB_TOKEN` lacks `contents: write` (org-level setting), HALT and report.

## Halt report template

```
HALT — dashboard-realtime circuit broken.

Step:    Step <N> <substep>
Trigger: <one of 13 conditions>
Branch:  feat/dashboard-realtime
HEAD:    <SHA>

Detail:
<error output OR Codex finding excerpt OR drift detail>

State:
- Commits on branch since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/dashboard-realtime/codex/round-*.txt
- Last verify result: <pass | fail with offending check>
- Drift report (if applicable): <list of conflicts>

Requesting founder input on:
<specific question>
```

## Final report — READY variant (default, manual_only merge)

```
═══════════════════════════════════════════════════════
AUTOPILOT dashboard-realtime — READY_FOR_MANUAL_MERGE
═══════════════════════════════════════════════════════

Squash commit:    N/A — founder/manual merge pending
Branch feat/dashboard-realtime:  still exists (intact, ready for review)
Push origin/main: NOT RUN

Files added:
  - tests/unit/test_build_dashboard.py
  - .github/workflows/dashboard.yml

Files modified:
  - scripts/build-dashboard.py (+detect_git_state, +reconcile_status, +drift report)
  - .pre-commit-config.yaml (+local build-dashboard hook)
  - docs/operations/development-workflow.md (Post-merge note)
  - docs/START_HERE.md (Source-of-truth table)

Codex review:
  Round 01: <findings count | clean>
  Final state: 1 clean round confirmed (per P2 pilot policy)
  Artifacts: .autopilot/state/dashboard-realtime/codex/round-01.txt

Local verification (final):
  ruff / black / mypy / lint-imports: clean
  pytest: <N> passed (baseline 118, expected ≥125 with new tests)
  pre-commit run --all-files: clean
  python scripts/build-dashboard.py: clean, drift report empty (or expected only)

Decisions made during execution requiring founder review:
  <list any non-obvious calls — e.g., heuristic thresholds for in-review detection>

═══════════════════════════════════════════════════════

Suggested squash command (founder runs after review):

  git checkout main
  git pull --ff-only origin main
  git merge --squash feat/dashboard-realtime
  git commit -m "feat(dashboard): realtime — auto-rebuild + git-state detection

  - Pre-commit hook rebuilds dashboard when tracker.md or build-dashboard.py staged
  - GitHub Action rebuilds + commits back on push to main
  - Script detects active branches + commit count, reconciles with tracker
    (tracker wins for terminal states; git wins for ⬜→🟡/🟠 transitions)
  - Drift report printed on manual run to surface tracker-vs-reality mismatches
  - 7 new unit tests covering parser + git detection + reconcile rule

  Per memory: feedback_auto_gen_views_surface_drift — auto-gen views expose
  source-of-truth drift; reconcile rule respects tracker as plan-of-record,
  git as plan-of-record check."
  git branch -D feat/dashboard-realtime
  git push origin main

═══════════════════════════════════════════════════════
```

Begin with Pre-flight, then Step 1.
