# Wave 0 Retrospective — 7 Lessons for Wave 1+

> **Date:** 2026-05-11
> **Author:** Founder (dev)
> **Status:** Locked
> **Scope:** Reflections after shipping Wave 0 (W0.1 → W0.6 multi-tenant foundation refactor) in ~1 day via Mode 3 autopilot + batch Codex review.
> **Cross-refs:**
> - [development-workflow.md](./development-workflow.md) — living workflow doc, updated 4× during Wave 0
> - [execution-prompt-wave0-autopilot.md](../autopilot/prompts/execution-prompt-wave0-autopilot.md) — autopilot prompt used
> - [wave0-batch-review.md](../autopilot/prompts/wave0-batch-review.md) — batch review playbook

---

## TL;DR

Lock decisions, codify invariants in tools, write 5 test categories upfront, treat sandbox-vs-terminal as separate authorities, accept pragmatic trade-offs when foundation is firm enough.

## Outcome

| Metric | Value |
|---|---|
| Duration | ~1 day from planning → Wave 0 merged |
| PRs merged | 6 (W0.1-W0.6) |
| Total Codex findings | 6 (3 W0.1 + 3 W0.6) — all addressed |
| Codex review rounds | W0.1: 3, W0.2-W0.5: 1 clean each, W0.6: 4 (3 findings + 1 clean) |
| Final test count | 116 passed, 1 skipped |
| Active import-linter contracts | 4 |
| Schema tables (initial migration 0001) | 10-11 |
| Email parser plugins | 6 (TCB / Cake / ACB / Sacombank / BIDV / MB) |

---

## 1. Sandbox và Terminal là 2 git authorities khác nhau — đừng mix

**Observed:** Claude Code app's sandbox has its own worktree separate from Mac terminal. Mixing 2 authorities caused:
- Codex review fired on wrong branch (sandbox on W0.6, terminal on W0.2)
- Multiple rebase aborts due to working tree drift
- Lost `CanonicalTx` commit during `git rebase --onto main HEAD~6` because sandbox had auto-committed a `wip: family spec sync` commit on top, shifting `HEAD~6` cutoff

**Apply for Wave 1+:**
- ALL git operations on Mac terminal (`git checkout`, `git rebase`, `git commit`, `git stash`, `git merge`).
- Sandbox uses Read/Write file + computation only.
- If Claude Code app needs git state, do it via explicit `Run bash: git ...` + verify branch with `git branch --show-current` before running any slash command (especially `/codex:review`).

## 2. Lock 100% design decisions BEFORE autopilot

**Observed:** 5 gap decisions locked (F08 column, parser plugin ABC+registry, webhook_tokens hashed table, SendPayload TypedDict, founder seed bootstrap-only) before W0.x autopilot = clean 3-6h run. If gaps left open, autopilot would have to guess → founder loses architectural control.

**Apply:**
- Per feature, list ALL unknowns as gaps + lock each (with rationale) before paste prompt.
- Circuit breaker MUST fire if autopilot discovers new gap mid-run. Don't let it decide unilaterally.
- Save gap decisions to memory note (e.g. `project_<feature>_gap_decisions.md`).

## 3. Codex cross-model review is non-replaceable for foundation/security/idempotency code

**Observed:** W0.1 P2 (substring contract test) + W0.6 P1×2 + P2 — all I (Claude) self-reviewed multiple times and missed. Codex (GPT-class) caught 4/4. Same-model self-review has cognitive blind spots that only diverse-model review surfaces.

**Apply:**
- Foundation OR security/idempotency-critical PRs MUST run Codex review.
- Simple feature PRs (UI strings, doc fixes) can skip if test coverage is strong.
- Threshold: if PR touches schema / auth / token compare / idempotency / concurrency → Codex required.

## 4. Test edge cases UP FRONT, not bug-driven

**Observed:** W0.6 went 3 Codex rounds because each fix introduced a new edge case the previous didn't anticipate:
- Round 1: NULL ref_code breaks UNIQUE (NULL != NULL)
- Round 2: content hash collapses distinct same-content events
- Round 3: raw provider_event_id can overflow VARCHAR(64)

If Round 1 test suite had covered 5 categories upfront, all 3 would have been caught before Codex.

**The 5 test categories:**

| Category | What it catches |
|---|---|
| Happy path | Basic correctness — does the feature do what it says |
| Retry / idempotency | Duplicate invocations (webhooks, transactions, side effects) |
| Missing optional fields | NULL handling, default values, partial payloads |
| Pathological inputs | Overflow (varchar bounds), malformed dates, huge payloads, injection |
| Concurrent access | Race conditions, lock contention, tenant isolation under load |

**Apply:**
- For any code with state / security / external integration surface → write test plan covering all 5 categories BEFORE coding.
- Use `engineering:testing-strategy` skill to draft the plan.
- Net save: ~1-2h per Codex round avoided. Wave 0 W0.6 would have saved 2 Codex rounds × ~30 min each = 1h.

## 5. Static enforcement (tools) beats documentation drift

**Observed:** 4 import-linter contracts codify ADR-0001 + Gap 2 parser-purity:

1. `core` MUST NOT import from `markets`
2. `markets.vn` ↮ `markets.global_`
3. `markets.global_` ↮ `markets.vn`
4. `markets.vn.email_parsers` MUST NOT import `core.db` or `core.messenger`

Code-as-law beats markdown rules over time. Static enforcement is forever; documentation drifts.

**Apply:**
- Each HARD architectural invariant → find a tool to enforce statically.
- Examples: layered architecture (import-linter), secret hygiene (detect-secrets), formatter consistency (black + pre-commit), type contracts (mypy --strict), schema constraints (alembic + CHECK clauses).
- If you find yourself writing "developers MUST..." in a doc, ask "is there a tool that enforces this?" before relying on docs.

## 6. Workflow doc is a living document — update per Wave experience

**Observed:** `development-workflow.md` updated 4× during Wave 0:
- Added autopilot mode (Mode 3 batch) when realized solo-dev can't handle 5 per-PR interrupts
- Added fixture strategy (real + synthetic, not real-only)
- Locked integration test default (`testcontainers-python`, not "or `pytest-postgresql`")
- Added W0.6 scope split section (foundation invariants only; legacy cutover → F02 strangler-fig)
- Added F02 expanded scope (inherits W0.6 deferred cutover)

**Apply:**
- End of each Wave → revisit workflow doc + memory notes. Update with patterns observed.
- Each "we should do this next time" comment becomes a doc update.
- Reuse via memory references in future sessions.

## 7. Pragmatic > Perfect when foundation is firm

**Observed pragmatic wins:**
- Mode 3 batch review > Mode 4 per-PR strict (saved 5× founder interrupts × 15 min = 1h+ context switches)
- W0.6 scope split (strangler-fig: foundation invariants ship; legacy cutover deferred to F02) > monster PR with >1000 lines behavior change
- Skip cosmetic rebase rename ("wip: family spec sync" stays as-is; solo dev doesn't need perfect commit history)
- Single workflow doc (vs separate docs per Wave) — easier to grep + reuse

**Apply:**
- Each pragmatic decision saves 30-60 minutes.
- Wave 1 features are simpler scope → less compromise needed.
- Default: ship correct + working; defer cosmetic.

---

## Concrete actions for Wave 1 (features: F-onboarding / F-admin-tools / F-i18n / F-settings)

| Pattern | Wave 0 (foundation) | Wave 1+ (features) |
|---|---|---|
| **Autopilot mode** | Mode 3 chained (dependent PRs) | Mode 4 per-feature OR parallel branches off main (features independent) |
| **Max active branches** | 2 (chained) | 2 (parallel) — same solo-dev cognitive limit |
| **Codex review threshold** | All findings fix | P0/P1 fix; P2/P3 can defer with explicit follow-up note |
| **Gap decisions timing** | All 5 locked Day 0 | Per feature, lock before autopilot start |
| **Test categories** | Inconsistent (learned hard way) | Mandatory 5-category test plan via `engineering:testing-strategy` skill |
| **Memory note per feature** | Wave 0 retro + scope split + gaps | Each feature → memory for non-obvious decisions |
| **Rebase paranoia** | Learned hard way (lost CanonicalTx commit) | `git stash -u` before rebase; verify FILE PRESENCE after, not just commit count |
| **Sandbox vs terminal git** | Caused friction | All git on terminal; sandbox = Read/Write only |

## Prep checklist per Wave 1 feature

Before pasting autopilot prompt for any feature:

1. **Spec lock**
   - FE spec finalized in `docs/features/feature-X.md`
   - BE tech doc finalized in `docs/features/BE/feature-X-tech.md`
   - Cross-refs to TDD/PRD sections verified

2. **Gap decisions locked in writing**
   - List ALL unknowns even if seems obvious
   - Save to memory note `project_<feature>_gap_decisions.md`
   - Include "why" + alternatives considered + rejected

3. **Test plan with 5 categories**
   - Happy path
   - Retry / idempotency
   - Missing optional fields
   - Pathological inputs
   - Concurrent access
   - For each: list specific test names + assertion intent
   - Use `engineering:testing-strategy` skill if unsure

4. **Anti-pattern checklist from workflow doc §6**
   - No mock DB (use testcontainers)
   - Atomic commits per §2.4
   - No `if market == "vn"` in `core/`
   - Tenant isolation test mandatory if DB involved
   - CHANGELOG entry required pre-merge

**Time investment:** ~30 min prep per feature. **Net save:** ~1-2h via avoided Codex round trips. **ROI:** 2-4×.

## Open questions for future retrospectives

After Wave 1 → revisit:

- Was Mode 4 per-PR better than Mode 3 batch for parallel features? Or both have place?
- Did 5-category test plan reduce Codex rounds to ≤1 per PR?
- Any new anti-patterns to add to workflow §6?
- Static enforcement tool additions (vs Wave 0's 4 import-linter contracts)?

## Post-W0 follow-ups (after-action review, 2026-05-12)

A post-merge review of Wave 0 surfaced three small items that didn't block the merge but were worth closing out before Wave 1 starts. Tracking here so they show up in the next retro's "did we follow through" check.

### Closed

- **Public `request_id` ContextVar helpers (`core/tenant_context`).** Previously `request_id_middleware` reached into `tenant_context._request_id.set()` / `.reset()` with `noqa: SLF001` annotations to silence the private-access lint. That was a smell — middleware contracts should depend on public API, not implementation. Added `set_request_id(rid) -> Token` + `reset_request_id(token)` as the public surface, refactored middleware to use them, dropped both `noqa`. Round-trip + empty-string-rejection unit tests added. Lesson: when a new module needs partial access to another module's state, expose the helper first rather than reaching across the abstraction.

- **F02 funding-source contract pin via `xfail(strict=True)`.** Wave 0 W0.6 shipped SePay → `transactions` INSERT without resolving `funding_source_id` (column stays NULL). Per F08 decisions, F02 must resolve before INSERT. Rather than relying on memory to remember the contract two months from now, added `test_persisted_tx_has_resolved_funding_source_id` with `@pytest.mark.xfail(strict=True)`. Test asserts `funding_source_id IS NOT NULL`; today it fails (xfail swallows), but the moment F02 wires resolution it'll pass unexpectedly and `strict=True` will fail the suite — forcing the dev to remove the marker as part of the F02 PR. **Pattern worth reusing:** any "deferred contract" should be pinned as a strict xfail at the moment the deferral is decided, not as a memory note.

### Open

- **Legacy file formatter drift.** Working tree on `main` contained black/ruff cosmetic changes to ~10 legacy files (`main.py`, `sheets.py`, `handlers/*.py`, `config.py`, `telegram_api.py`) — confirmed format-only via token-stream comparison. These files are in `pyproject.toml extend-exclude`, so the formatter shouldn't run, but IDE auto-format-on-save bypassed that. **Default plan:** revert the drift (cleaner blame for F02), reformat-on-move when files migrate into `core/handlers/`. Decision lockdown item added to `phase-2-handlers.md` F02 section. Note for Wave 1: if the IDE keeps reformatting excluded files, audit the editor config or add a `.editorconfig` rule.

**Lesson for the pattern catalog:** Wave-end review should look for (1) "we used `noqa` to ship — is the abstraction still right?", (2) "we deferred X — is there a test pin or just a memory note?", (3) "working tree on main has unrelated changes — what reformatter/tool is at fault?".

## Cross-references

- [project_wave0_complete.md memory](../../README.md) — Wave 0 final state + Codex summary
- [project_wave0_gap_decisions.md memory](../../README.md) — 5 decisions locked 2026-05-11
- [project_w06_scope_split.md memory](../../README.md) — strangler-fig migration rationale
- [development-workflow.md](./development-workflow.md) §2 (10-step), §4 (wave structure), §6 (anti-patterns)
