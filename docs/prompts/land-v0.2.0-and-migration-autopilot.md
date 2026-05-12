# Task: Land v0.2.0 to main + Ship webhook display_suffix migration PR (G3 option b)

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT — two sequential phases on two branches, with inline Codex
review on Phase 2 (cross-model audit required for schema change per Wave 0
lesson #3). Auto-push both phases. Pause ONLY on circuit-breaker conditions.

**Scope of this prompt:**
- Phase 1: finalize G3 spec decision on existing v0.2.0 branch → squash-merge
  to main → push → post-merge doc updates (plan changelog + tracker row).
- Phase 2: new branch `feat/webhook-display-suffix-migration` →
  `webhook_tokens.display_suffix VARCHAR(8)` migration + issuance update + UI
  display rule + 5-category tests + CHANGELOG → local verify → inline Codex
  review with ≤3 fix rounds → squash-merge to main → push.

**EXCLUDED from this prompt (do NOT execute):**
- F07 (Settings) feature pilot itself. After Phase 2 merges, founder runs
  `python -m tools.autopilot run F07` (without `--auto-merge` — F07 is P1).
  That is a separate command, not part of this prompt.

## Required reading (READ FIRST, in this order, before any code)

1. `docs/operations/autopilot-implementation-plan.md` v0.1.6 §6.5 — risk-tier
   policy. Phase 2 is a schema migration → P1, manual merge after Codex audit.
2. `docs/operations/wave0-retrospective.md` §1 (sandbox/terminal git), §3
   (Codex required for foundation/schema), §4 (5-category test plan upfront).
3. `docs/operations/development-workflow.md` §2 (10-step), §6 (anti-patterns).
4. `docs/features/feature-settings.md` — current G3 DEFERRED block (you'll
   close it). Then `docs/features/BE/feature-settings-tech.md` for context.
5. `migrations/versions/0001_initial_schema.py` lines 177-192 (current
   `webhook_tokens` table shape) — your migration extends this.
6. `markets/vn/capture/webhook_tokens.py` — `mint_token` is where you populate
   `display_suffix` alongside `token_hash`.
7. `tests/integration/test_sepay_webhook.py` and `tests/integration/test_migrations.py`
   — patterns for migration + token tests in this repo.
8. `CHANGELOG.md` — current `## [Unreleased]` section. Phase 1 adds the v0.2.0
   entry; Phase 2 adds a new Unreleased entry on top of it.

## Pre-flight (run first, HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent

# Branch state — Phase 1 expects we're sitting on chore/autopilot-blockers-v0.2.0
git status                              # MUST be clean
git branch --show-current               # MUST be: chore/autopilot-blockers-v0.2.0
git log --oneline main..HEAD | wc -l    # MUST be >0 (branch ahead of main)

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling green
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v                        # MUST be green (last known: 209 pass)

python -m tools.autopilot preflight     # ALL 6 PASS
```

ALL must pass. If any fails → HALT and report. Do not proceed.

If `git branch --show-current` shows `main` instead (founder already merged
Phase 1 out of band): skip directly to Phase 2 pre-flight on main.

## Anti-patterns (NEVER do)

- Run `git push --force` (Phase 1 is fast-forward squash; Phase 2 is new
  branch — never force-push either).
- Mock the database in Phase 2 tests (use testcontainers per repo convention).
- Add a `# type: ignore` anywhere (circuit breaker — founder approval needed).
- Skip the 5-category test plan in Phase 2 (Wave 0 lesson #4).
- Invoke `claude -p` or any subprocess Claude in Phase 2 — YOU are Claude.
  Codex CLI is the only external CLI invoked.
- Run Codex on Phase 1 (v0.2.0 was already cleared by 4 rounds of Codex in
  the prior session — re-running is waste).
- Use sandbox/Cowork session for git ops. You ARE the Mac terminal authority.
- More than 2 active branches simultaneously. Phase 1 ends with branch
  deleted before Phase 2 starts.
- Auto-merge Phase 2 without Codex clean signoff (P1 schema change).

---

## PHASE 1 — Land v0.2.0 to main

### Step 1.1 — Close G3 decision in F07 spec (option b)

**File:** `docs/features/feature-settings.md`

**Find the G3 block** (currently `status: DEFERRED:founder-review-before-pilot`).
Replace the entire G3 entry with the CLOSED version below. Preserve the
`autopilot:gaps` block's surrounding entries (G1, G2, G4-G8) and YAML format.

```yaml
- id: G3
  question: How to display webhook URL suffix in /settings overview given schema has only token_hash (no plaintext / no display_suffix column)?
  status: CLOSED
  decision: Founder locked option (b) 2026-05-12 — add `display_suffix VARCHAR(8)` column to webhook_tokens table in a SEPARATE follow-up PR (feat/webhook-display-suffix-migration), landing BEFORE F07 pilot. F07 then renders "🔗 Webhook: configured ✓ (created {date}) · ...{display_suffix}" once the column exists. Migration PR scope: alembic upgrade adds nullable column, mint_token populates it, lookup path unchanged (token_hash still primary).
  rationale: Suffix gives users visual confirmation the webhook URL they pasted matches the one rendered — option (a) "configured ✓ + date" was acceptable but founder judged the missing tail-suffix would look like a UX bug. Schema change is small, additive, nullable → P1 (Codex review + manual merge per plan §6.5).
  alternatives_rejected: Option (a) plain "configured ✓ (created {date})" without suffix (chosen first-pass but founder revisited); showing token_hash last-N chars (info leak risk + looks like a bug); deriving suffix from token_hash via deterministic substring (couples display to storage hash — fragile if hash algo ever changes).
```

**Find the Acceptance Criteria line** that mentions G3:
```
- [ ] Webhook URL display = "configured ✓ (created {date})" — last-6-chars suffix DEFERRED until founder confirms schema (gap G3)
```

Replace with:
```
- [ ] Webhook URL display = "configured ✓ (created {date}) · ...{display_suffix}" — display_suffix populated by feat/webhook-display-suffix-migration PR (G3 closed)
```

**Verify spec still lints:**
```bash
python -m tools.autopilot lint F07
```

MUST report 0 errors AND 0 warnings. If a warning appears → HALT.

**Commit:**
```bash
git add docs/features/feature-settings.md
git commit -m "docs(F07): close G3 — display_suffix via separate migration PR"
```

### Step 1.2 — Final verification on v0.2.0 branch

```bash
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
python -m tools.autopilot lint F07
python -m tools.autopilot preflight
```

ALL must pass. If any fails → HALT.

### Step 1.3 — Squash-merge v0.2.0 to main

```bash
git checkout main
git pull --ff-only origin main          # ensure local main up-to-date

git merge --squash chore/autopilot-blockers-v0.2.0
git commit -m "chore(autopilot): v0.2.0 — pre-pilot blockers resolved + G3 closed

Resolves Blockers #1-#5 from docs/operations/autopilot-implementation-plan.md v0.1.6:
- #1: claude -p probe + codegen fallback commit (with --no-verify, returncode guard)
- #2: chunked codegen driver (Option A — single-shot per chunk)
- #3: F07 spec migrated to autopilot template format; G3 closed (option b)
- #4: atomic state.json write (temp+rename)
- #5: --auto-merge opt-in flag with safe-default off, P2-only allow-list

Validated by 4 rounds of Codex cross-model review (r1-r4 P1 findings addressed
with regression tests; r5 clean). 209 tests pass, all hooks green.

F07 pilot now unblocked AFTER feat/webhook-display-suffix-migration ships."

git branch -D chore/autopilot-blockers-v0.2.0
git push origin main
```

If push is rejected (remote ahead) → HALT. Do NOT force-push.

### Step 1.4 — Post-merge doc updates on main

Two doc updates land on main directly (small docs-only commits, no review
needed — they describe what just merged).

**1.4a — Append v0.2.0 entry to implementation plan changelog:**

Open `docs/operations/autopilot-implementation-plan.md`, find the trailing
`## Changelog` table. Append a new row at the bottom:

```markdown
| v0.2.0 | 2026-05-12 | Pre-pilot blockers #1-#5 resolved via Mode 3 batch autopilot. Codex 4-round P1 fixes integrated (returncode guard on fallback commit, --no-verify for pre-commit-blocked fallback, exit code 5 for declined confirm, P2-only allow-list on --auto-merge). G3 closed to option (b) — display_suffix migration ships next. F07 pilot unblocked after migration PR lands. |
```

Commit:
```bash
git add docs/operations/autopilot-implementation-plan.md
git commit -m "docs(autopilot): plan changelog v0.2.0 — blockers resolved"
```

**1.4b — Update implementation tracker row for F07 dependency:**

Open `docs/implementation-tracker.md`. Find the F07 row (Settings). Update
the dependency / blocker column to reference
`feat/webhook-display-suffix-migration` as the new pre-pilot prerequisite.
Preserve all other columns.

If the tracker has a separate row for the migration PR / schema change
work, add an entry there too with status `🟡 in progress`. If there's no
appropriate row, add one new row above F07's row:

```markdown
| Webhook display_suffix migration | feat/webhook-display-suffix-migration | Phase 4 | 🟡 in progress | Schema P1 — adds VARCHAR(8) column to webhook_tokens, unblocks F07 G3 |
```

(Use the tracker's actual column structure — adapt to its existing schema.)

Commit:
```bash
git add docs/implementation-tracker.md
git commit -m "docs(tracker): F07 now depends on webhook display_suffix migration"
```

Push both:
```bash
git push origin main
```

**Phase 1 complete.** Verify:
```bash
git log --oneline -5                    # squash commit + 2 doc commits visible
git branch                              # only main exists locally
```

---

## PHASE 2 — Webhook display_suffix migration PR

### Step 2.1 — Branch + pre-flight on main

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git checkout main
git pull --ff-only origin main          # confirm Phase 1 push landed
git status                              # MUST be clean

git checkout -b feat/webhook-display-suffix-migration

# Capture starting SHA for CHANGELOG diff gate later
git rev-parse HEAD > /tmp/phase2-base-sha.txt
```

### Step 2.2 — Write the alembic migration

**File:** `migrations/versions/0002_webhook_display_suffix.py` (new file).

Use alembic naming pattern matching `0001_initial_schema.py`. Migration is
strictly additive — nullable column, no backfill of historical rows (they
keep `NULL` and F07 displays without suffix for legacy tokens; founder
accepts this — legacy webhook_tokens predate UI display rule).

Migration body:
- `upgrade()`: `op.execute("ALTER TABLE webhook_tokens ADD COLUMN display_suffix VARCHAR(8);")`
- `downgrade()`: `op.execute("ALTER TABLE webhook_tokens DROP COLUMN display_suffix;")`
- Add a docstring header following the 0001 convention (purpose, Gap
  reference: "Gap 3 follow-up — supports F07 UI display rule").

**Why VARCHAR(8) not CHAR(6)?** Future-proofing — 6 chars is plenty today
(`secrets.token_urlsafe(24)` produces ~32 chars URL-safe alphabet ≈64) but
VARCHAR(8) gives headroom if a future kind ever wants 7-8 chars of tail
display. The G3 closed-block in the spec says "...{display_suffix}" without
prescribing length — column type stays flexible.

### Step 2.3 — Update issuance code (`mint_token`)

**File:** `markets/vn/capture/webhook_tokens.py`

Add helper `_display_suffix(raw: str) -> str`:
```python
def _display_suffix(raw: str) -> str:
    """Tail 6 chars of the raw token — shown in UI, NEVER used for auth.

    Auth still goes through token_hash. The suffix is purely cosmetic —
    helps users visually confirm the URL they pasted matches the one
    rendered in /settings. Length 6 is short enough to display in a
    bot reply without wrapping; entropy loss is irrelevant (we leak 6/32
    chars of a random URL-safe string only to the user who owns the token).
    """
    if len(raw) < 6:
        # Defensive: secrets.token_urlsafe(24) always returns >>6 chars,
        # but if a caller ever shortens the generator, fall back to the
        # full string rather than raise — column tolerates any <= 8 chars.
        return raw
    return raw[-6:]
```

Modify `mint_token` to populate `display_suffix` alongside `token_hash`:

```python
async def mint_token(user_id: int, kind: TokenKind) -> str:
    raw = secrets.token_urlsafe(24)
    token_hash = hash_token(raw)
    display_suffix = _display_suffix(raw)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webhook_tokens (user_id, kind, token_hash, display_suffix)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, kind) DO UPDATE
                SET token_hash = EXCLUDED.token_hash,
                    display_suffix = EXCLUDED.display_suffix,
                    revoked_at = NULL,
                    created_at = NOW();
            """,
            user_id,
            kind,
            token_hash,
            display_suffix,
        )
    return raw
```

**Critical:** `resolve_token` is UNTOUCHED. Auth path stays hash-only —
`display_suffix` is write-only from the orchestrator's perspective and
read-only from the UI's perspective. They never meet at the auth boundary.

Add a tiny read helper for F07 to consume later (kept in same module to
avoid creating a new module just for one query):

```python
async def get_display_suffix(user_id: int, kind: TokenKind) -> str | None:
    """Return the active token's display_suffix for (user_id, kind), or
    None if no active row exists (or row predates this migration → NULL)."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT display_suffix
            FROM webhook_tokens
            WHERE user_id = $1 AND kind = $2 AND revoked_at IS NULL;
            """,
            user_id,
            kind,
        )
    if row is None:
        return None
    return cast(str | None, row["display_suffix"])
```

### Step 2.4 — Write tests (5-category plan)

**File:** `tests/integration/test_webhook_display_suffix.py` (new file).

Use the existing testcontainers postgres fixture from
`tests/integration/test_migrations.py` and `test_sepay_webhook.py` — match
their import pattern and fixture names.

Five categories (mark explicitly in test docstrings):

1. **Happy path** — `test_mint_token_populates_display_suffix`:
   - Call `mint_token(user_id=1, kind='sepay')` → returns raw.
   - Query `webhook_tokens` directly → row has `display_suffix = raw[-6:]`.
   - Call `get_display_suffix(1, 'sepay')` → equals `raw[-6:]`.

2. **Happy path, regenerate** — `test_regenerate_updates_display_suffix`:
   - Mint once, capture suffix1.
   - Mint again same (user, kind) → ON CONFLICT path.
   - Query → only ONE row exists for (user, kind); display_suffix == new_raw[-6:];
     suffix1 ≠ suffix2 (overwhelming probability with token_urlsafe(24)).

3. **Missing-optional** — `test_legacy_row_with_null_display_suffix`:
   - INSERT raw SQL: a row with token_hash but display_suffix = NULL
     (simulates pre-migration data).
   - `resolve_token(raw, 'sepay')` STILL succeeds (auth unaffected).
   - `get_display_suffix(...)` returns `None`.
   - This proves backward compatibility — F07 must handle None.

4. **Pathological** — `test_short_raw_token_does_not_overflow_column`:
   - Monkeypatch `secrets.token_urlsafe` to return a 4-char string (shorter
     than 6). `mint_token` should still succeed (helper falls back to full
     string); column tolerates it (VARCHAR(8)).
   - Also: assert mint_token never raises when called twice with rapid
     succession (ON CONFLICT path is the documented contract).

5. **Retry/idempotency** — N/A. Document as a top-of-file comment:
   ```python
   # Category 4 (retry/idempotency): N/A — mint_token's idempotency is
   # already covered by test_regenerate_updates_display_suffix (Category 2);
   # there is no retry surface that the suffix changes.
   ```

6. **Concurrent** — N/A. Document as a top-of-file comment:
   ```python
   # Category 5 (concurrent): N/A — UNIQUE(user_id, kind) constraint makes
   # concurrent mint a serialization concern owned by the existing
   # webhook_tokens table tests in test_migrations.py, not specific to the
   # display_suffix column.
   ```

(The Wave 0 5-category convention allows explicit N/A with reason. Two N/A
is acceptable here per spec-template convention — just make the reason
explicit so Codex doesn't flag "missing test category".)

Also update `tests/integration/test_migrations.py` if it has an
upgrade-then-downgrade test against the head revision — add the
0002 revision to its expected ladder. Inspect first; only modify if needed.

### Step 2.5 — Update CHANGELOG

Open `CHANGELOG.md`. Insert a new `## [Unreleased]` block at the top (or
add to the existing one if Phase 1's v0.2.0 entry is already cut to a
released section).

```markdown
### Added
- `webhook_tokens.display_suffix VARCHAR(8)` column (migration 0002).
  Populated by `mint_token` from `raw_token[-6:]`. Auth path
  (`resolve_token`) unchanged — suffix is cosmetic-only. Unblocks F07
  webhook URL display rule (G3 closed, option b).
- `get_display_suffix(user_id, kind)` read helper in
  `markets/vn/capture/webhook_tokens.py` for F07 to consume.

### Notes
- Legacy rows (predating this migration) have `display_suffix = NULL`;
  F07 displays without suffix for those — accepted UX trade-off.
- VARCHAR(8) over CHAR(6) for future-proofing; only 6 chars used today.
```

### Step 2.6 — Local verify

```bash
ruff check tools/ tests/ core/ markets/ migrations/
black --check tools/ tests/ core/ markets/ migrations/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v
```

ALL must pass. The new migration test class MUST appear in pytest output.

If any fails → up to 2 retries to fix root cause. After 2 retries → HALT
with `VERIFY_REGRESSION` circuit breaker.

**Commit (atomic, multiple OK):**
```bash
git add migrations/versions/0002_webhook_display_suffix.py
git commit -m "feat(webhook): add display_suffix VARCHAR(8) column (G3 option b)"

git add markets/vn/capture/webhook_tokens.py
git commit -m "feat(webhook): populate display_suffix on mint + add read helper"

git add tests/integration/test_webhook_display_suffix.py tests/integration/test_migrations.py
git commit -m "test(webhook): 5-category coverage for display_suffix migration"

git add CHANGELOG.md
git commit -m "docs: changelog — webhook display_suffix migration"
```

### Step 2.7 — Inline Codex review with ≤3 fix rounds

**Why inline:** schema migrations are a P1 surface per plan §6.5; Wave 0
lesson #3 mandates cross-model review for foundation/schema. The orchestrator
codifies this in its Phase C; this PR follows the same protocol.

**Round N (1, 2, 3):**

```bash
mkdir -p .autopilot/state/webhook-display-suffix/codex
codex review --base main 2>&1 | tee .autopilot/state/webhook-display-suffix/codex/round-NN.txt
```

(`NN` = `01`, `02`, `03`.)

**Parse Codex output:**
- If output contains `No findings` or `No issues found` (clean signal) →
  Codex clean → check below.
- Otherwise extract findings. For each finding:
  - If severity P0/P1 → MUST fix this round.
  - If severity P2 → fix opportunistically; defer to follow-up if it requires
    significant scope creep.
  - If finding contains keywords `schema design`, `breaking change`,
    `architectural`, `re-think`, `migration cannot be reversed safely` →
    `ARCH_FINDING` circuit breaker → HALT.
  - If finding contains `auth`, `token leak`, `timing`, `secret`, `injection`
    → `SECURITY_FINDING` circuit breaker → HALT (founder must review).
  - If same finding hash appears in round N AND round N+1 → `RECURRING_FINDING`
    breaker → HALT.

**Fix round (between Codex rounds):**
- Apply minimum-viable fix for each must-fix finding.
- Re-run local verify (Step 2.6). MUST be green before next Codex round.
- Commit atomically: `fix(webhook): address codex round NN — <summary>`.

**Clean signal handling:**
- Need 2 consecutive clean rounds before squash-merge (matches orchestrator's
  `required_clean_rounds_before_merge` default).
- If round 1 clean → run round 2 anyway. If round 2 also clean → proceed to
  squash.
- If round 3 not 2× clean → `MAX_ROUNDS` breaker → HALT.

### Step 2.8 — Squash-merge to main

Only reachable if Step 2.7 produced 2 consecutive clean Codex rounds.

```bash
git checkout main
git pull --ff-only origin main

# Dry-run merge first to confirm no conflicts
git merge --no-commit --no-ff feat/webhook-display-suffix-migration
git merge --abort                       # discard dry-run; real merge next

git merge --squash feat/webhook-display-suffix-migration
git commit -m "feat(webhook): display_suffix VARCHAR(8) — G3 closed (option b)

Adds nullable VARCHAR(8) display_suffix column to webhook_tokens.
Populated by mint_token from raw[-6:]. Auth path unchanged (resolve_token
still hash-only). Legacy rows keep NULL; F07 displays without suffix for
those.

Unblocks F07 pilot — founder may now run:
  python -m tools.autopilot run F07

(F07 is P1; do NOT pass --auto-merge — manual squash after Codex review.)

Validated by inline Codex review (2 consecutive clean rounds). Migration
0002 forward + downgrade both tested under testcontainers postgres."

git branch -D feat/webhook-display-suffix-migration
git push origin main
```

If push rejected → HALT. Do NOT force-push.

**Phase 2 complete.**

---

## Circuit breakers (HALT and write report)

PAUSE immediately and write
`.autopilot/state/land-v0.2.0-and-migration/halt-report.md` if ANY of
these triggers fire. Do NOT keep going.

1. **Phase 1 verify regression** — existing 209 tests no longer pass on
   v0.2.0 branch.
2. **Push rejected** on either phase (remote moved; do not force-push).
3. **Spec lint warning** on F07 after the G3 close edit.
4. **Migration syntax error** caught by alembic dry-run or pytest collection.
5. **VERIFY_REGRESSION** — Phase 2 local verify fails twice consecutively
   after fix attempts.
6. **ARCH_FINDING** from Codex — keywords: schema design, breaking change,
   migration cannot be reversed, contract change.
7. **SECURITY_FINDING** from Codex — auth/token/timing/secret/injection
   keywords. Even if Codex marks it P3, founder must review schema-adjacent
   security findings.
8. **RECURRING_FINDING** — same Codex finding hash in round N AND N+1.
9. **TYPE_IGNORE_PROPOSED** — Codex suggests `# type: ignore` or you find
   yourself reaching for one to silence mypy.
10. **MAX_ROUNDS** — 3 Codex rounds without 2 consecutive clean signals.
11. **Tool error twice in a row** on the same operation (`alembic`, `git`,
    `codex`) — do not retry blindly.
12. **Context budget** — if context >70% used, pause + report. Founder will
    resume in fresh session with branch state intact.

### Halt report template

```
HALT — Land v0.2.0 + migration autopilot circuit broken.

Phase: <1 or 2>
Step:  <e.g. 2.7 round 2>
Trigger: <one of 12 conditions>
Branch: <current branch>
HEAD:   <SHA>

Detail:
<error output OR Codex finding excerpt OR rejected push reason>

State:
- Phase 1 status: <not started | in progress | complete + pushed | rolled back>
- Phase 2 status: <not started | branch created | code committed | codex round N (clean Y/N) | merged>
- Commits on current branch since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/webhook-display-suffix/codex/round-*.txt
- Last verify result: <pass | fail with offending check>

Requesting founder input on:
<specific question — e.g. "Codex round 2 flagged display_suffix as
information leak. Mitigation: store HMAC of raw[-6:] instead of raw[-6:]
itself? Need decision before continuing.">
```

---

## Final report (when both phases complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
LAND v0.2.0 + WEBHOOK DISPLAY_SUFFIX MIGRATION — COMPLETE
═══════════════════════════════════════════════════════

Phase 1 — v0.2.0 landed:
  Squash commit: <SHA>  chore(autopilot): v0.2.0 — pre-pilot blockers resolved + G3 closed
  Post-merge:    <SHA>  docs(autopilot): plan changelog v0.2.0
  Post-merge:    <SHA>  docs(tracker): F07 dependency updated
  Branch chore/autopilot-blockers-v0.2.0: DELETED
  Push origin/main: OK

Phase 2 — display_suffix migration shipped:
  Squash commit: <SHA>  feat(webhook): display_suffix VARCHAR(8) — G3 closed (option b)
  Files added:
    - migrations/versions/0002_webhook_display_suffix.py
    - tests/integration/test_webhook_display_suffix.py
  Files modified:
    - markets/vn/capture/webhook_tokens.py
    - tests/integration/test_migrations.py (if needed)
    - CHANGELOG.md
  Branch feat/webhook-display-suffix-migration: DELETED
  Push origin/main: OK

Codex review (Phase 2):
  Round 01: <findings count | clean>
  Round 02: <findings count | clean>
  Round 03: <run? Y/N — only if first two not both clean>
  Final state: 2 consecutive clean rounds confirmed
  Artifacts: .autopilot/state/webhook-display-suffix/codex/round-*.txt

Local verification (final):
  ruff:         clean
  black:        clean
  mypy:         clean
  lint-imports: 4 contracts kept
  pytest:       <count> passed, <count> skipped, <count> xfail
  autopilot lint F07: 0 warnings

Decisions made during execution requiring founder review:
  <list any non-obvious calls — typically none if prompt followed verbatim>

Next step (NOT in this prompt's scope):
  Founder runs F07 pilot:
    python -m tools.autopilot run F07
  (F07 is P1 — do NOT pass --auto-merge. Halt at READY, review squash,
  manual merge after Codex audit. This validates the full orchestrator
  loop end-to-end on a real feature.)

End of land + migration autopilot.
═══════════════════════════════════════════════════════
```

Then STOP. Do not proceed to F07 pilot from this prompt.

---

## Global rules (apply throughout)

1. READ FIRST. Don't write code blind on either phase.
2. NEVER skip the 10-step workflow on Phase 2 (read spec → plan → code +
   tests atomic → verify → review → CHANGELOG → squash).
3. NEVER force-push.
4. NEVER mock postgres in Phase 2 tests — use the repo's testcontainers fixture.
5. NEVER add `# type: ignore` — circuit breaker.
6. NEVER auto-skip Codex rounds on Phase 2 — schema P1 mandates 2× clean.
7. NEVER reuse a Phase 1 branch for Phase 2 — they're separate squash commits.
8. Atomic commits — multiple commits per step is fine; one mega-commit is not.
9. If unsure on architecture, trigger circuit breaker. Do not guess on schema.
10. Verify before claiming done — re-run pytest after "tests pass" message.
11. Tool error twice → circuit breaker, don't retry blindly.
12. Context budget — if >70% used, pause + halt report so founder can resume
    cleanly. Branch state must be intact.
13. Memory hygiene — if a non-obvious decision is made during execution
    (especially in Phase 2 Codex fix rounds), save a brief memory note via
    the auto-memory system for future sessions.
14. Both phases auto-push on success. No further confirmation needed.

Begin with Pre-flight, then Phase 1 Step 1.1. No further confirmation
needed — execute through Phase 2 final report.
