# Task: Ship W0.8 — webhook `display_suffix VARCHAR(8)` migration PR

You are working in /Users/maingocanh/Projects/MyMoneyWent on a solo founder's
multi-tenant Vietnamese personal finance bot. NO prior conversation context.
This prompt is self-contained.

**Mode:** AUTOPILOT — single feature branch `feat/webhook-display-suffix-migration`,
inline Codex review with ≤3 fix rounds, then squash-merge to main + push.
Pause ONLY on circuit-breaker conditions.

**Context (NOT for execution, just background):**
- v0.2.0 autopilot orchestrator already merged to main (commit `5a35dcb`).
- G3 in F07 (Settings) spec was closed to option (b) — schema change ships
  here as a separate PR before the F07 pilot.
- This PR is tracker row W0.8 (Phase 1, Wave 0 follow-up). F07 cannot start
  until this lands.

**Scope of this prompt:** Phase 2 only — migration + issuance update + tests
+ CHANGELOG + Codex review + squash-merge. F07 pilot is NOT in scope (founder
runs `python -m tools.autopilot run F07` separately after this lands).

## Required reading (READ FIRST, in this order, before any code)

1. `docs/operations/autopilot-implementation-plan.md` v0.2.0 §6.5 — risk-tier
   policy. Schema migration → P1, manual merge after Codex audit.
2. `docs/operations/wave0-retrospective.md` §1 (sandbox/terminal git), §3
   (Codex required for foundation/schema), §4 (5-category test plan upfront).
3. `docs/operations/development-workflow.md` §2 (10-step), §6 (anti-patterns).
4. `docs/features/feature-settings.md` G3 closed block (justifies this PR).
5. `migrations/versions/0001_initial_schema.py` lines 177-192 (current
   `webhook_tokens` table — your migration extends this).
6. `markets/vn/capture/webhook_tokens.py` — `mint_token` is where you populate
   `display_suffix` alongside `token_hash`.
7. `tests/integration/test_sepay_webhook.py` and `tests/integration/test_migrations.py`
   — patterns for migration + token tests in this repo. Use the SAME
   testcontainers postgres fixture; do NOT introduce a new fixture style.
8. `docs/implementation-tracker.md` W0.8 row — confirms branch name + scope.

## Pre-flight (run first, HALT if any fails)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git status                              # MUST be clean
git branch --show-current               # MUST be: main
git fetch origin && git pull --ff-only origin main
git log --oneline -3                    # 5a35dcb chore(autopilot): v0.2.0... visible
                                        # + 2 docs commits (plan changelog + tracker)

source .venv/bin/activate
which claude codex                      # both MUST resolve

# Tooling green
ruff check tools/ tests/ core/ markets/
black --check tools/ tests/ core/ markets/
mypy core/ markets/ tests/
lint-imports
pytest tests/ -v                        # MUST be green (215 pass baseline)

python -m tools.autopilot preflight     # ALL 6 PASS
```

ALL must pass. If any fails → HALT and report. Do not proceed.

## Anti-patterns (NEVER do)

- `git push --force` (new branch — never force-push).
- Mock postgres in tests (use the repo's testcontainers fixture).
- Add a `# type: ignore` anywhere (circuit breaker — founder approval needed).
- Skip the 5-category test plan (Wave 0 lesson #4).
- Invoke `claude -p` or any subprocess Claude — YOU are Claude.
  Codex CLI is the only external CLI invoked.
- Modify `resolve_token` (auth path) — `display_suffix` is write-only from
  orchestrator's perspective, read-only from UI. They never meet at auth.
- Backfill historical NULL display_suffix rows (founder accepts legacy
  rows render without suffix).
- Auto-merge without Codex 2× clean signoff (P1 schema change).
- Use sandbox/Cowork session for git ops. YOU are the Mac terminal authority.

---

## Step 1 — Branch + capture base SHA

```bash
git checkout -b feat/webhook-display-suffix-migration
git rev-parse HEAD > /tmp/w08-base-sha.txt
mkdir -p .autopilot/state/webhook-display-suffix/codex
```

## Step 2 — Write the alembic migration

**File:** `migrations/versions/0002_webhook_display_suffix.py` (new).

Naming + style matches `0001_initial_schema.py`. Migration is strictly
additive — nullable column, no backfill of historical rows.

Migration body:
- `upgrade()`: `op.execute("ALTER TABLE webhook_tokens ADD COLUMN display_suffix VARCHAR(8);")`
- `downgrade()`: `op.execute("ALTER TABLE webhook_tokens DROP COLUMN display_suffix;")`
- Docstring header following 0001 convention: purpose, Gap reference
  (`"Gap 3 follow-up — supports F07 UI display rule (W0.8)"`).
- `revision` / `down_revision` per alembic convention.

**Why VARCHAR(8) not CHAR(6)?** Future-proofing — 6 chars is enough today
(`secrets.token_urlsafe(24)` produces ~32 chars URL-safe alphabet ≈64) but
VARCHAR(8) gives headroom if a future kind ever wants 7-8 chars of tail
display. The G3 closed-block says "...{display_suffix}" without prescribing
length — column type stays flexible.

## Step 3 — Update issuance code (`mint_token`)

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

**Critical:** `resolve_token` is UNTOUCHED. Auth path stays hash-only.

Add a tiny read helper for F07 to consume later (kept in same module to
avoid creating a new module for one query):

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

## Step 4 — Write tests (5-category plan)

**File:** `tests/integration/test_webhook_display_suffix.py` (new).

Use the existing testcontainers postgres fixture from
`tests/integration/test_migrations.py` and `test_sepay_webhook.py` — match
their import pattern and fixture names. Do NOT introduce a new fixture style.

Five categories (mark explicitly in test docstrings):

1. **Happy path** — `test_mint_token_populates_display_suffix`:
   - Call `mint_token(user_id=1, kind='sepay')` → returns raw.
   - Query `webhook_tokens` directly → row has `display_suffix == raw[-6:]`.
   - Call `get_display_suffix(1, 'sepay')` → equals `raw[-6:]`.

2. **Happy path, regenerate** — `test_regenerate_updates_display_suffix`:
   - Mint once, capture suffix1.
   - Mint again same (user, kind) → ON CONFLICT path.
   - Query → exactly ONE row exists for (user, kind); display_suffix equals
     new_raw[-6:]; suffix1 ≠ suffix2 (overwhelming probability with
     `token_urlsafe(24)`).

3. **Missing-optional** — `test_legacy_row_with_null_display_suffix`:
   - INSERT raw SQL: a row with token_hash but `display_suffix = NULL`
     (simulates pre-migration data).
   - `resolve_token(raw, 'sepay')` STILL succeeds (auth unaffected).
   - `get_display_suffix(...)` returns `None`.
   - Proves backward compatibility — F07 must handle None.

4. **Pathological** — `test_short_raw_token_does_not_overflow_column`:
   - Monkeypatch `secrets.token_urlsafe` to return a 4-char string (shorter
     than 6). `mint_token` should still succeed (helper falls back to full
     string); column tolerates it (VARCHAR(8)).
   - Also assert `mint_token` never raises when called twice in rapid
     succession (ON CONFLICT path is the documented contract).

5. **Retry/idempotency** — N/A. Document as top-of-file comment:
   ```python
   # Category 4 (retry/idempotency): N/A — mint_token's idempotency is
   # already covered by test_regenerate_updates_display_suffix (Category 2);
   # there is no retry surface that the suffix changes.
   ```

6. **Concurrent** — N/A. Document as top-of-file comment:
   ```python
   # Category 5 (concurrent): N/A — UNIQUE(user_id, kind) constraint makes
   # concurrent mint a serialization concern owned by the existing
   # webhook_tokens table tests in test_migrations.py, not specific to the
   # display_suffix column.
   ```

(Two N/A is acceptable per spec-template convention — just keep the reason
explicit so Codex doesn't flag "missing test category".)

Also inspect `tests/integration/test_migrations.py` — if it has an
upgrade-then-downgrade test against the head revision, add 0002 to its
expected ladder. Only modify if needed.

## Step 5 — Update CHANGELOG

Open `CHANGELOG.md`. The current `## [Unreleased]` block already has an
"Autopilot orchestrator v0.2.0" entry from the prior PR — leave that intact.
Append a new sub-section AT THE END of the `## [Unreleased]` block:

```markdown
### Added — Webhook `display_suffix` (W0.8)

- `webhook_tokens.display_suffix VARCHAR(8)` column (migration 0002).
  Populated by `mint_token` from `raw_token[-6:]`. Auth path
  (`resolve_token`) unchanged — suffix is cosmetic-only. Unblocks F07
  webhook URL display rule (G3 closed, option b).
- `get_display_suffix(user_id, kind)` read helper in
  `markets/vn/capture/webhook_tokens.py` for F07 to consume.

### Notes

- Legacy rows (predating migration 0002) have `display_suffix = NULL`;
  F07 displays without suffix for those — accepted UX trade-off.
- VARCHAR(8) over CHAR(6) for future-proofing; only 6 chars used today.
```

## Step 6 — Local verify + atomic commits

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
git commit -m "feat(webhook): add display_suffix VARCHAR(8) column (G3 option b, W0.8)"

git add markets/vn/capture/webhook_tokens.py
git commit -m "feat(webhook): populate display_suffix on mint + add read helper"

git add tests/integration/test_webhook_display_suffix.py tests/integration/test_migrations.py
git commit -m "test(webhook): 5-category coverage for display_suffix migration"

git add CHANGELOG.md
git commit -m "docs: changelog — webhook display_suffix migration (W0.8)"
```

(Only include `test_migrations.py` in the test-commit `git add` if you
actually modified it in Step 4.)

## Step 7 — Inline Codex review with ≤3 fix rounds

**Why inline:** schema migrations are a P1 surface per plan §6.5; Wave 0
lesson #3 mandates cross-model review for foundation/schema. The orchestrator
codifies this in Phase C; this PR follows the same protocol.

**Round N (1, 2, 3):**

```bash
codex review --base main 2>&1 | tee .autopilot/state/webhook-display-suffix/codex/round-NN.txt
```

(`NN` = `01`, `02`, `03`.)

**Parse Codex output:**

- If output contains `No findings` or `No issues found` (clean signal) →
  Codex clean → see "Clean signal handling" below.
- Otherwise extract findings. For each finding:
  - Severity P0/P1 → MUST fix this round.
  - Severity P2 → fix opportunistically; defer to follow-up if it requires
    significant scope creep.
  - Keywords `schema design`, `breaking change`, `architectural`, `re-think`,
    `migration cannot be reversed safely` → `ARCH_FINDING` breaker → HALT.
  - Keywords `auth`, `token leak`, `timing`, `secret`, `injection` →
    `SECURITY_FINDING` breaker → HALT (founder must review).
  - Same finding hash in round N AND round N+1 → `RECURRING_FINDING`
    breaker → HALT.

**Fix round (between Codex rounds):**

- Apply minimum-viable fix for each must-fix finding.
- Re-run local verify (Step 6 commands). MUST be green before next Codex round.
- Commit atomically: `fix(webhook): address codex round NN — <summary>`.

**Clean signal handling:**

- Need 2 consecutive clean rounds before squash-merge (matches orchestrator's
  `required_clean_rounds_before_merge` default).
- If round 1 clean → run round 2 anyway. If round 2 also clean → proceed to
  squash.
- If round 3 not 2× clean → `MAX_ROUNDS` breaker → HALT.

## Step 8 — Squash-merge to main + push

Only reachable if Step 7 produced 2 consecutive clean Codex rounds.

```bash
git checkout main
git pull --ff-only origin main

# Dry-run merge to confirm no conflicts
git merge --no-commit --no-ff feat/webhook-display-suffix-migration
git merge --abort                       # discard dry-run; real squash next

git merge --squash feat/webhook-display-suffix-migration
git commit -m "feat(webhook): display_suffix VARCHAR(8) — G3 closed (option b, W0.8)

Adds nullable VARCHAR(8) display_suffix column to webhook_tokens.
Populated by mint_token from raw[-6:]. Auth path unchanged (resolve_token
still hash-only). Legacy rows keep NULL; F07 displays without suffix for
those.

Unblocks F07 pilot — founder may now run:
  python -m tools.autopilot run F07

(F07 is P1; do NOT pass --auto-merge. Halt at READY; manual squash after
Codex review.)

Validated by inline Codex review (2 consecutive clean rounds). Migration
0002 forward + downgrade both tested under testcontainers postgres."

git branch -D feat/webhook-display-suffix-migration
git push origin main
```

If push rejected → HALT. Do NOT force-push.

---

## Circuit breakers (HALT and write report)

PAUSE immediately and write
`.autopilot/state/webhook-display-suffix/halt-report.md` if ANY of these
fire. Do NOT keep going.

1. **Pre-flight regression** — existing 215 tests no longer pass on main.
2. **Push rejected** (remote moved; do not force-push).
3. **Migration syntax error** caught by alembic dry-run or pytest collection.
4. **VERIFY_REGRESSION** — local verify fails twice consecutively after fix
   attempts.
5. **ARCH_FINDING** from Codex — keywords listed in Step 7.
6. **SECURITY_FINDING** from Codex — auth/token/timing/secret/injection.
   Even if Codex marks P3, founder must review schema-adjacent security.
7. **RECURRING_FINDING** — same Codex finding hash in round N AND N+1.
8. **TYPE_IGNORE_PROPOSED** — Codex suggests `# type: ignore` or you reach
   for one to silence mypy.
9. **MAX_ROUNDS** — 3 Codex rounds without 2 consecutive clean signals.
10. **Tool error twice in a row** on the same operation (`alembic`, `git`,
    `codex`) — do not retry blindly.
11. **Context budget** — if context >70% used, pause + report. Founder will
    resume in fresh session with branch state intact.

### Halt report template

```
HALT — W0.8 webhook display_suffix migration circuit broken.

Step:    <e.g. Step 7 round 2>
Trigger: <one of 11 conditions>
Branch:  feat/webhook-display-suffix-migration
HEAD:    <SHA>

Detail:
<error output OR Codex finding excerpt OR rejected push reason>

State:
- Commits on branch since branch start: <list with SHAs>
- Files changed: <list>
- Codex artifacts: .autopilot/state/webhook-display-suffix/codex/round-*.txt
- Last verify result: <pass | fail with offending check>

Requesting founder input on:
<specific question — e.g. "Codex round 2 flagged display_suffix as
information leak. Mitigation: store HMAC of raw[-6:] instead of raw[-6:]
itself? Need decision before continuing.">
```

---

## Final report (when Step 8 complete)

Output verbatim:

```
═══════════════════════════════════════════════════════
W0.8 — WEBHOOK display_suffix MIGRATION — COMPLETE
═══════════════════════════════════════════════════════

Squash commit: <SHA>  feat(webhook): display_suffix VARCHAR(8) — G3 closed (option b, W0.8)
Branch feat/webhook-display-suffix-migration: DELETED
Push origin/main: OK

Files added:
  - migrations/versions/0002_webhook_display_suffix.py
  - tests/integration/test_webhook_display_suffix.py

Files modified:
  - markets/vn/capture/webhook_tokens.py
  - tests/integration/test_migrations.py (if needed)
  - CHANGELOG.md

Codex review:
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

Decisions made during execution requiring founder review:
  <list any non-obvious calls — typically none if prompt followed verbatim>

Next step (NOT in this prompt's scope):
  Founder runs F07 pilot:
    python -m tools.autopilot run F07
  (F07 is P1 — do NOT pass --auto-merge. Halt at READY, review squash,
  manual merge after Codex audit. This validates the full orchestrator
  loop end-to-end on a real feature.)

End of W0.8 autopilot.
═══════════════════════════════════════════════════════
```

Then STOP. Do not proceed to F07 pilot from this prompt.

---

## Global rules (apply throughout)

1. READ FIRST. Don't write code blind.
2. NEVER skip the 10-step workflow (read → plan → code+tests atomic → verify
   → review → CHANGELOG → squash).
3. NEVER force-push.
4. NEVER mock postgres — use the repo's testcontainers fixture.
5. NEVER add `# type: ignore` — circuit breaker.
6. NEVER auto-skip Codex rounds — schema P1 mandates 2× clean.
7. NEVER modify `resolve_token` (auth path stays hash-only).
8. Atomic commits — multiple commits per step is fine; one mega-commit is not.
9. If unsure on architecture, trigger circuit breaker. Do not guess on schema.
10. Verify before claiming done — re-run pytest after "tests pass" message.
11. Tool error twice → circuit breaker, don't retry blindly.
12. Context budget — if >70% used, pause + halt report. Branch state must
    be intact for resume.
13. Memory hygiene — if a non-obvious decision is made during execution
    (especially in Codex fix rounds), save a brief memory note via the
    auto-memory system for future sessions.
14. Auto-push on success. No further confirmation needed.

Begin with Pre-flight, then Step 1. No further confirmation needed —
execute through Step 8 final report.
