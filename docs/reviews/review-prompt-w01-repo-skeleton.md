# Review prompt — W0.1 Repo skeleton + lint boundary

> Paste the section between the `===` markers below into Claude Code (or any
> fresh Claude session) to get an independent review of W0.1. The reviewer
> has no prior conversation context — the prompt is self-contained.

> **Branch:** `feat/F01-w01-repo-skeleton`
> **Scope:** 6 commits, 14 files, +489 lines (per `git diff main..HEAD --stat`)
> **PR position:** First PR of Wave 0 (6 sequential PRs W0.1 → W0.6)

---

```
===PROMPT START===

You are reviewing a freshly-implemented PR in the MyMoneyWent monorepo. You
have no context from prior sessions. Read this brief, then audit the work
on branch `feat/F01-w01-repo-skeleton` against `main`.

## Project context

MyMoneyWent is a multi-tenant personal finance bot serving two markets in
parallel: VN ("Tiền Về Nơi Đâu", SePay + bank email) and Global ("My Money
Went", Plaid/TrueLayer + e-commerce APIs). Solo-founder dev. Currently
pre-Wave-0: legacy single-tenant code at root (`main.py`, `sheets.py`,
`telegram_api.py`, `handlers/`) being refactored to multi-tenant.

ADR-0001 (`docs/adr/0001-monorepo-not-split-repos.md`) locks the target
structure: single repo, `core/ + markets/vn/ + markets/global_/` adapter
pattern. **Hard invariant: `core/` MUST NOT import from `markets/`.**

The full refactor (F-saas-refactor, spec at `docs/features/feature-saas-
refactor.md`) is split into 6 sequential PRs called Wave 0. See
`docs/operations/development-workflow.md` §4 for the W0.1–W0.6 breakdown
and acceptance criteria. **W0.1 is the FIRST PR.**

## What's being reviewed (W0.1 scope)

Per `development-workflow.md` §4, W0.1 = "Repo skeleton + lint boundary".
Deliberately boring: NO business logic, NO DB schema, NO functional code.

Files added/modified on branch (read `git diff main..HEAD --stat`):

1. `pyproject.toml` — project metadata, tool configs (ruff/black/mypy/
   pytest), `[project.optional-dependencies.dev]`. Legacy code excluded
   from strict checks via `extend-exclude`.
2. `requirements-dev.txt` — pointer to `-e .[dev]`.
3. `core/__init__.py` — empty package skeleton + module docstring.
4. `markets/__init__.py` — empty package skeleton + docstring.
5. `markets/vn/__init__.py` — empty package skeleton.
6. `markets/global_/__init__.py` — empty package skeleton. Note: trailing
   underscore because `global` is a Python reserved keyword.
7. `tests/__init__.py` — empty.
8. `tests/test_import_boundary.py` — 3 smoke tests: config exists,
   positive (lint-imports clean), NEGATIVE (deliberate core→markets
   violation must be caught).
9. `.pre-commit-config.yaml` — hooks: ruff (lint+fix), black (format),
   mypy (strict on core/markets/tests), detect-secrets, lint-imports.
10. `.importlinter` — 3 contracts: core ↛ markets, markets.vn ↮
    markets.global_ (bidirectional).
11. `.secrets.baseline` — detect-secrets baseline placeholder.
12. `.github/workflows/ci.yml` — Actions on push main + PR: pre-commit →
    lint-imports → pytest.
13. `README.md` — added "Development setup" section.
14. `CHANGELOG.md` — top entry: "F01 W0.1: Repo skeleton + lint boundary".

The implementer claims local verification passed:
- ruff check: all checks passed
- black --check: 6 files unchanged
- mypy --strict: no issues found in 6 source files
- lint-imports: 3 contracts kept, 0 broken
- Negative test confirmed: deliberate `core/_test_violation.py` with
  `from markets import vn` → lint-imports caught it, exit 1.

## Reference docs (read for context before reviewing)

1. `docs/operations/development-workflow.md` — especially §2 (10-step
   per-feature workflow), §4 Wave 0 (W0.1 acceptance criteria), §6
   (anti-patterns).
2. `docs/adr/0001-monorepo-not-split-repos.md` — the invariant being
   enforced.
3. `CHANGELOG.md` (top entry) — what claims were made about this PR.
4. `README.md` "Development setup" section — claimed dev UX.

## Your review scope

Audit 4 dimensions + 3 alignment checks.

### 1. Logic correctness
- `pyproject.toml`: tool configs internally consistent? `[tool.ruff]`
  target-version, `[tool.black]` target-version, `[tool.mypy]` python_
  version all aligned? Are the `extend-exclude` paths in ruff and black
  the same set (drift will cause divergent reformat)?
- `.importlinter` contracts: do they capture the intended boundary
  correctly? Should `handlers/` also have rules (it's a root_package)?
  What about `tests/` being able to import everything (probably YES,
  not enforced)?
- `tests/test_import_boundary.py`: do the 3 tests actually verify what
  they claim? Negative test writes a real file in `core/` — what if
  another test runs in parallel and sees it? Race condition? Cleanup
  guarantee?
- CI workflow: will it actually run all checks claimed in CHANGELOG?
  Does pip install resolve correctly with `-e .[dev]` given no runtime
  deps in pyproject?

### 2. Performance
Limited surface (config files). Check:
- pre-commit hook order: cheap-first?
- CI: any sequential step that could parallelize (e.g., lint job
  parallel with test job)?
- mypy `files = ["core", "markets", "tests"]` — does it re-scan on
  every commit, or cache?

### 3. Security
- detect-secrets baseline plugins enabled (22)? Sufficient?
- Any plaintext secret accidentally committed in the new files?
- CI Actions versions pinned to specific revs? Trusted publishers?
- ruff bandit (S) rule subset reasonable? `S101` (assert) ignored in
  tests is fine, but check the `per-file-ignores` carefully.
- `.secrets.baseline` ships empty `results` — does user need to scan
  pre-existing legacy code? Is that documented?

### 4. Spec/ADR alignment
- Does the import-linter rule match ADR-0001 invariants EXACTLY?
  - "core MUST NOT import from markets" ✓ check
  - markets.vn ↛ markets.global_ ✓ check (both directions)
  - `handlers/` (legacy) — should it be allowed to import core/markets?
    Currently has no contract — intentional? Document.
- Package structure matches ADR target (core/ + markets/vn/ +
  markets/global_/)? Note the `_` suffix on global.
- `markets/global_/` rename adequately documented? README mentions it,
  module docstring mentions it. Is ADR-0001 itself updated? (Probably
  not — informal alias only.)
- The `__init__.py` docstrings reference "ADR-0001" correctly?

### 5. Workflow compliance (vs development-workflow.md)
- Step 9 §2.6: CHANGELOG entry present and accurate?
- §2.4: Atomic commits — read `git log main..HEAD --oneline`. 6 commits
  separated by scope. Reasonable?
- §4 Wave 0 W0.1 acceptance criteria met?
  - pre-commit pass ✓ (claimed)
  - import-linter block test PR vi phạm boundary ✓ (negative test)
  - CI xanh — can't verify without pushing
- §3 pre-commit hooks: ruff/black/mypy/import-linter/detect-secrets all
  present?

### 6. Foundation completeness — anything forcing W0.2-W0.6 retrofit?
- Tool config gaps that next PRs will hit?
- Missing `tests/conftest.py`? (It's scheduled for W0.2 per workflow
  doc, but check if W0.1 should pre-create skeleton.)
- Python version pinned consistently? (3.11)
- License field set?
- Setuptools `packages.find` correctly catches `markets.global_`?

### 7. Anti-pattern audit (per workflow doc §6)
Verify none of these apply:
- [ ] Code trước, đọc spec sau — N/A (W0.1 has no business logic)
- [ ] Mock Postgres — N/A (no DB yet)
- [ ] 1 PR 30 file chưa atomic — verify commits
- [ ] Skip tenant isolation test — N/A (no DB)
- [ ] Bump spec version sau mỗi round — verify CHANGELOG no spec bumps
- [ ] Merge mà chưa có CHANGELOG entry — verify present
- [ ] Code feature vào structure legacy — verify nothing landed in
      legacy paths
- [ ] `if market == "vn"` trong core/ — N/A (core is empty)
- [ ] core/ import từ markets/ — THE rule being tested; verify

## Output format

Reply in this structure:

### Issues found

**Critical** (block merge):
- <issue>: <why critical>

**Important** (should fix before merge):
- ...

**Minor** (can defer to follow-up):
- ...

### Verifications passed

- <each claim that holds after reading the actual file>

### Suggestions for W0.2 onwards (non-blocking)

- ...

### Boundary enforcement confidence

Rate 1-5: how confident are you that the import-linter rule will catch
ADR-0001 violations in W0.3–W0.6 when real code lands? Justify.

## Reviewer constraints

1. You CANNOT run code (no bash/git). Reason purely from reading files.
2. The implementer's local verification claims (ruff ✓, black ✓, mypy ✓,
   lint-imports ✓) — trust but verify by reading the test code and configs
   yourself. Don't accept claims without reading the file.
3. Bias toward catching things that would force retrofit in later W0.x PRs.
4. Don't suggest scope creep — W0.1 is intentionally minimal foundation.
   Suggestions for "you should also add X" go in the "Suggestions for W0.2
   onwards" section, not "Issues found".
5. If you find no critical issues, say so. Don't manufacture problems.

===PROMPT END===
```

---

## How to use

1. Switch to `feat/F01-w01-repo-skeleton` branch in your terminal.
2. Open Claude Code in the project directory.
3. Paste everything between `===PROMPT START===` and `===PROMPT END===`.
4. The reviewer will read files and respond in the requested format.

## After review

- **No critical/important issues** → squash-merge `feat/F01-w01-repo-skeleton` into `main` with commit message `F01: W0.1 repo skeleton + lint boundary`. Proceed to W0.2.
- **Issues found** → fix in same branch (atomic commits per §2.4), then re-run this prompt on the fix diff only (mini-review per §2.5). Loop until clean.
- **Cross-check with `/codex:review`** — running both Claude Code review + Codex review catches different things (different models miss different bugs). Run Codex on the same branch.
