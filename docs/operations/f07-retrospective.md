# F07 (Settings) Pilot Retrospective — 10 Lessons for F02-F08+

> **Date:** 2026-05-13
> **Author:** Founder (dev)
> **Status:** Locked
> **Scope:** Reflections after shipping F07 (Settings — locale + TZ + daily recap toggle) over 6 autopilot pilot sessions, surfacing 3 orchestrator hardening releases (v0.2.1 + v0.2.2 + v0.2.3) and 9 cumulative tooling issues.
> **Cross-refs:**
> - [wave0-retrospective.md](./wave0-retrospective.md) — Wave 0 lessons (foundation)
> - [development-workflow.md](./development-workflow.md) — 10-step workflow
> - [autopilot-implementation-plan.md](../autopilot/autopilot-implementation-plan.md) — orchestrator design + risk-tier policy
> - Memory: `project_f07_pilot_saga.md`, `feedback_never_auto_delete_docs.md`, `feedback_project_level_effectiveness.md`, `feedback_prefer_autopilot_prompts.md`

---

## TL;DR

Cascade is real (budget 5-8 rounds, not 2-3). Lock spec invariants AGAINST themselves (not just gap closure). Single-phase autopilot prompts ship; multi-phase silently drop trailing work. Project-level ROI > single-PR speed (fix tool first, ship feature later). Concurrency between Claude Code sessions is a real hazard — strict 1-session policy or `git worktree`. Never destroy docs files without asking founder.

## Outcome

| Metric | Value |
|---|---|
| Duration (founder time) | ~10-15 hours across 6 sessions |
| Calendar duration | 1 day (2026-05-12 → 2026-05-13) |
| Sessions | 6 (codegen → refactor → markdown → i18n → resume → re-resume) |
| F07 final commits | 25 (squashed to `f232b63` on main) |
| F07 tests added | 30+ (settings_svc, handlers, i18n, migration, tenant isolation) |
| Final test count post-merge | 376 passed, 1 skipped, 1 xfailed |
| Orchestrator releases shipped | 3 (v0.2.1 `533e9fd was 395027d`, v0.2.2 `533e9fd`, v0.2.3 `9a00be6`) |
| Cumulative tooling issues identified | 9 (3 fixed, 6 deferred to v0.2.4) |
| Cumulative Codex rounds across F07 + tool fixes | ~30+ |
| Concurrency incidents (parallel session ref-clobber) | 3 |
| Total stash entries accumulated | 9 (mix of WIP + orphan) |

---

## 1. Cascade pattern is empirically real — budget 5-8 codex rounds, not 2-3

**Observed:** Every fix grows the diff → Codex's next review may surface a new adjacent micro-finding in the new code. F07 R1 (emit_analytics) → fix → R2 finds tz validation pattern → fix → R3 finds callback dispatch pattern (same root cause as R2 → triggers refactor) → ...

v0.2.1 fix run (orchestrator self-fix): 8 rounds to converge. v0.2.2: 8 rounds. v0.2.3: 4 rounds (2 fix + 2 confirm). Pattern: median ~4-6 rounds, max ~8.

Original orchestrator config `max_review_rounds=3 + required_clean_rounds_before_merge=2 (consecutive)` was mathematically unable to ship when R1+R2 both find. v0.2.2 raised to `max=5 + confirmation_rounds_after_last_fix=2`. Even that hit MAX_ROUNDS once on the v0.2.2 PR itself (eat-own-dogfood).

**Apply:**
- Default orchestrator budget = `max_fix_rounds=5 + post_fix_confirm=2` per v0.2.2.
- For PRs touching ≥5 files OR introducing new public APIs, expect cascade. Plan budget 5-8 rounds.
- If R1+R2 both find, accept that the PR will need 4+ rounds before 2× clean — don't override.
- Founder one-time override OK as last resort, but document each occurrence in v0.2.4 backlog (if pattern recurs ≥3 times, code-level relaxation rule warranted).

## 2. Concurrency hazard between Claude Code sessions is real — 1 session per repo

**Observed:** 3 ref-clobber incidents during F07 saga:
- A parallel `feat/dashboard-realtime` agent reset `feat/F07-settings` ref via shared `.git/`. Recovered via `git reflog` + `git update-ref`.
- v0.2.2 finish run had `git stash + checkout main + pull` interrupted mid-flight by parallel session.
- Webapp session continuously created/edited `docs/research/webapp-resource-assessment.md` + `docs/features/feature-web-dashboard.md` + `docs/brd-vi.md` + `docs/prd-vi.md` + `docs/mymoneywent-roadmap.md` + `docs/implementation-tracker.md` while F07 session was running git ops.

Result: stash cycle confusion ("file biến mất rồi appear lại"), accidental commit leak (webapp file landed in tracker commit `5a1dc14` until rebase abort).

**Apply:**
- **Strict policy:** AT MOST one Claude Code session per `.git/` directory at a time.
- For parallel feature work → use `git worktree`:
  ```bash
  git worktree add /Users/.../MyMoneyWent-F07 feat/F07-settings
  git worktree add /Users/.../MyMoneyWent-webapp feat/webapp-dashboard
  ```
  Each worktree has independent `.git/` checkout state but shares object storage.
- Before starting any autopilot session, verify `ls .git/*.lock` is empty (no in-progress git ops from another agent).
- `feedback_autopilot_prompt_template.md` mandate concurrency check before EACH codex round in long-running prompts.
- v0.2.4 backlog: `.autopilot/locks/<repo-hash>.lock` advisory file lock for code-level enforcement.

## 3. Lock spec invariants against THEMSELVES, not just gap closure

**Observed:** F07 spec G4 was "closed" with decision: "Stored in users.inbound_email... F07 reads only; renders as-is. If row is NULL (legacy users), F07 backfills via f"u{user_id}@in.mymoneywent.com" on read and writes back."

This decision contradicts itself: "reads only" but "backfills on read and writes back" — backfill IS write. Codex caught the resulting bug in 2 different handlers (R2 + R3 of session 1), each "validate-before-`get_overview`" band-aid surfacing the next.

Root-cause refactor (session 2): `get_overview` made pure-read; `ensure_inbound_email` extracted as explicit idempotent helper called via migration 0003 (one-time backfill of legacy NULL rows). G4 spec rewritten to remove the "reads + writes" contradiction.

**Apply:**
- Spec gap analysis isn't done when each gap has a "decision" — it's done when decisions are MUTUALLY CONSISTENT.
- For each closed gap, ask: "does this decision contradict any other invariant in this spec or adjacent spec?"
- Specifically check for:
  - "Pure" / "read-only" claims that conflict with documented side-effects elsewhere
  - "Idempotent" claims that conflict with state changes
  - "Stateless" claims that conflict with cache/session writes
  - "Atomic" claims with non-transactional code paths
- Use `engineering:architecture` skill or write a 1-page "invariant audit" before locking spec.
- CQRS principle: separate read paths from write paths at the function-name level (`get_*` reads, `ensure_*` / `set_*` writes, never both).

## 4. Single-phase autopilot prompts > multi-phase mega-prompts

**Observed:** 2-phase `land-v0.2.0-and-migration-autopilot.md` prompt: agent completed Phase 1 squash + push, then SILENTLY STOPPED before Phase 2. No halt-report, no error — just stopped.

Comprehensive 3-phase prompt (Phase A v0.2.2 ship + Phase B F07 resume + Phase C tracker): completed Phase A fully, hit halt in Phase B mid-cascade, never reached Phase C. Founder had to drive Phase C tracker manually.

Single-phase prompts (W0.8 migration, v0.2.1 fix, v0.2.2 finish-after-r4, v0.2.2 finish-after-r7, v0.2.3 keyword fix, F07 resume) all completed cleanly OR halted with explicit halt-report.

**Apply:**
- Default: 1 prompt = 1 phase = 1 branch = 1 squash. ~200-500 lines.
- Multi-phase only if phases are STRICTLY ORTHOGONAL (rare). Even then, prefer separate prompts with explicit checkpoints.
- Per memory `feedback_autopilot_prompt_scope.md`: failure mode = drop trailing phase silently.
- Reference `docs/operations/autopilot-prompt-template.md` for skeleton.
- Continuation prompts after halt are FINE (e.g. `finish-after-r4.md`) — small focused scope, not multi-phase.

## 5. Project-level ROI > single-PR speed (fix tool first, ship feature later)

**Observed pattern across 4 decision points:**

- **Path A vs B for orchestrator parser bug** → chose B (fix tool). Saved future F02-F08 from repeating same FIX_FAILED halt.
- **Override vs R8 manual round in v0.2.1** → chose R8. Found legitimate P2; protocol justified itself.
- **Band-aid handlers vs root-cause `get_overview` refactor** → chose root-cause. Spec G4 contradiction would have surfaced in F-i18n + F11a too.
- **Solo word-boundary fix vs batched v0.2.3** → chose solo. Smaller PR converged in 4 rounds vs batched would have hit cascade.

8-axis comparison framework (memory `feedback_project_level_effectiveness.md`):
1. Code quality + future-bug surface
2. Spec integrity
3. Pilot/test value
4. Time to converged ship
5. Risk profile integrated over MVP lifetime
6. Downstream pipeline impact (count remaining PRs)
7. Tool credibility
8. Architecture trajectory

**Apply:**
- For each A vs B option: explicitly run 8-axis comparison. 6/8 trục thắng → choose, even if 2-3× initial time.
- ROI tính theo MVP-scale (33+ PRs remaining), not single-PR-scale.
- Discount short-term convenience. Especially when scope is foundation/tool/spec.
- Past examples confirming: F07 saga's 4 chose-B decisions paid off — F02-F08 inherit fixed orchestrator.

## 6. Codex stochasticity: same diff, different reviews. Don't ship on 1 clean

**Observed:** Multiple times during F07 + v0.2.x fixes — Codex reviewed the same git diff and surfaced different findings (or none) across rounds.

Examples:
- v0.2.1 R3 clean → R4 P2 (against same diff)
- v0.2.1 R5 clean → R6 P2 (against same diff)
- F07 Phase B re-resume R1 + R2 both clean (after v0.2.3 word-boundary fix) — but pre-existing P2 in `emit_analytics` json.dumps would have surfaced in some other run

The `2× consecutive clean` rule exists exactly for this. Single clean review = stochastic noise. Two consecutive = real signal.

**Apply:**
- NEVER ship on 1 clean Codex review.
- If `max_review_rounds` exhausted with only 1 clean, prefer extending budget (run R+1, R+2 manual) over override.
- Plus: when fixing, account for "Codex didn't flag this same finding earlier" — finding may be latent and re-surfaced. Treat as real, fix anyway.
- Founder one-time override ONLY when documented in halt-report + added to vN+1 backlog.

## 7. Stage-commit-only for tracker; founder pushes manually

**Observed:** Phase C tracker push (auto-mode classifier blocked even `git fetch` on grounds of main-branch push risk). Direct push from autopilot to main is risky in solo-founder mode + race-prone with dashboard auto-rebuild scheduler.

Lesson: tracker / changelog / plan-doc updates are docs commits — they don't need orchestrator's full review pipeline + don't benefit from autopilot push.

**Apply:**
- Autopilot stages + commits tracker/docs locally on main.
- Founder reviews `git log -1 --format=%B` + `git diff origin/main..main` + pushes manually.
- 1 extra command (`git push origin main`), but consistent with founder direct-push-to-main flow + avoids classifier overhead.
- Mirror pattern for F07 squash itself (P1 manual merge per plan §6.5): autopilot ends at READY, founder squashes.

## 8. NEVER auto-delete docs files (BRD/PRD/spec/tracker/research/.md)

**Observed:** Founder runs multiple Claude Code sessions parallel. Each session creates/edits real docs files. T (current session) repeatedly suggested:
- `git checkout --theirs/--ours docs/<file>` (discards content)
- `git stash drop stash@{N}` (permanently destroys stash)
- `git stash push -u` "to clean tree" (hides files, looks like deletion)
- `git restore docs/<file>` (discards uncommitted changes)

Each instance was a real risk of losing parallel session's work. Founder explicit feedback: "tất cả file docs đều phải giữ nguyên, ko đc tự ý xoá trc khi hỏi lại t".

**Apply:**
- ANY destructive op on `.md` (or `.txt`, `.rst`) → PAUSE + ask founder + wait for explicit confirmation.
- Conflict resolution on docs files: show both diffs, ask founder which side, don't auto-resolve.
- Stash drop: inspect content first (`git stash show -p stash@{N}`), confirm with founder before drop.
- Pre-flight cleanup: prefer explicit `git add <only-this-file>` over stash-everything-orthogonal pattern. Leave other docs untracked in working tree — they persist across most git ops.
- Branch switch with dirty docs: don't suggest stash-then-pop; use `git checkout -m` or commit on current branch first.
- Memory note: `feedback_never_auto_delete_docs.md` (locked 2026-05-13).

## 9. Self-dogfood paradox: keyword/breaker-work PRs trip own breakers

**Observed:** v0.2.3 PR fixed `CONCURRENCY_KEYWORDS` word-boundary matching. Inline Codex review's findings about keyword routing contained text like "guarded block" / "security escalation" / "architecture-gate" — which trigger the very keyword breakers the PR is fixing.

R2 surfaced 2× P1+P2 findings: SOFT+P1 via `\bsecurity\b` matching "security escalation" in finding text, ARCH via `\barchitecture\b` matching "architecture-gate". Both legitimate findings about keyword routing. Both auto-HALTED the loop.

Founder authorized one-time path-restricted override (treat breaker triggers as advisory when finding location is `tools/autopilot/codex.py` keyword section).

**Apply:**
- For PRs that touch the breaker logic itself, expect self-dogfood paradox.
- Default: founder authorizes one-time path-restricted override per such PR. Document in commit message.
- v0.2.4 backlog: if pattern recurs ≥3 times → code-level "self-review relaxation policy" rule (treat findings located in same module as the fix as advisory).
- Sample size = 1 (v0.2.3 only, in F07 saga). Wait for 2-3 more occurrences before generalizing.

## 10. Word-boundary regex everywhere keywords are matched

**Observed:** v0.2.2 R2 caught `\brce\b` substring matching "force" — fixed `SECURITY_KEYWORDS_SEVERE` with regex word-boundary. But the same fix was NOT propagated to `CONCURRENCY_KEYWORDS`, `ARCH_KEYWORDS`, `SECURITY_KEYWORDS_SOFT`. Result: F07 Phase B halted on substring `lock` matching `block` (in "guarded block").

v0.2.3 propagated word-boundary regex to all 4 categories. Plus special-case `lock` compound regex `\b(?:dead|live)?lock(?:s|ing|ed)?\b` so `block`/`padlock`/`lockstep` correctly excluded.

Founder Q1 lock: don't add plural `(?:s)?` to `design`/`scope`/`architecture`/`refactor`/`redesign`/`hmac`/`auth` — singular forms dominate Codex output. Add only to countable nouns (`token(s)?`, `credential(s)?`, `password(s)?`, `secret(s)?`) and phrase plurals (`breaking change(s)?`, `interface change(s)?`).

**Apply:**
- For ANY keyword-based string-matching system, default = word-boundary regex (`\b...\b`), NOT substring `in` operator.
- Special handling only for compound terms (e.g. `lock` ↔ `block` confusion).
- Preserve singular for abstract nouns; add plural for countable nouns + phrase variations.
- Pattern reusable: any future tool with classification keywords (logging filters, alerts, etc.).

---

## Concrete actions for F02-F08 pilots

| Pattern | F07 (this saga) | F02-F08 (apply) |
|---|---|---|
| **Codex round budget** | Started max=3 (impossible), ended max=5 + post-fix-confirm=2 | Start with v0.2.2 default; expand only if PR scope warrants |
| **Concurrency** | 3 ref-clobber incidents during saga | STRICT 1 session per repo; use `git worktree` if parallel needed |
| **Spec invariant audit** | G4 contradiction surfaced as 2 cascading findings | Add invariant audit step to per-feature prep checklist |
| **Autopilot prompt scope** | Multi-phase comprehensive prompt dropped Phase B | Single-phase only; continuation prompts for halts |
| **A vs B decisions** | 4 chose-B decisions paid off | Run 8-axis check explicit; 6/8 win → choose B even if 2-3× time |
| **Codex stochasticity** | Multiple "1 clean → R+1 finding" patterns | NEVER ship on 1 clean; respect 2× consec rule |
| **Tracker push** | Classifier blocked autopilot push | Autopilot stages + commits, founder pushes |
| **Docs files** | T suggested destructive ops repeatedly | Per `feedback_never_auto_delete_docs.md`: PAUSE + ask before destroy |
| **Self-dogfood** | v0.2.3 keyword PR tripped own keyword breakers | Founder one-time override per PR; track recurrences |
| **Stash management** | 9 stashes accumulated | Avoid stash-everything-orthogonal pattern; use explicit `git add` |

## Prep checklist per F02-F08 pilot

Before pasting autopilot prompt for any feature pilot:

1. **Spec lock** (mandatory)
   - FE spec finalized
   - BE tech doc finalized
   - All gaps CLOSED with locked decisions
   - **Invariant audit** — verify each closed gap doesn't contradict any other invariant in this spec or adjacent specs
   - Cross-refs to TDD/PRD verified

2. **Concurrency check** (mandatory)
   - No other Claude Code sessions running on this repo
   - `ls .git/*.lock` empty
   - If parallel work needed → set up `git worktree` first
   - Webapp/dashboard/etc parallel sessions paused or in worktree

3. **Test plan with 5 categories** (mandatory, per Wave 0 lesson #4)
   - Happy path
   - Retry / idempotency
   - Missing optional fields
   - Pathological inputs
   - Concurrent access
   - Each: specific test names + assertion intent

4. **Anti-pattern checklist**
   - No mock DB (use testcontainers)
   - Atomic commits per workflow §2.4
   - No `if market == "vn"` in `core/`
   - Tenant isolation test mandatory if DB involved
   - CHANGELOG entry required pre-merge
   - **NEW: no destructive op on docs files without founder confirm**

5. **Autopilot prompt scope**
   - Single-phase only (per memory `feedback_autopilot_prompt_scope.md`)
   - Reference `docs/autopilot/autopilot-prompt-template.md` skeleton
   - Explicit budget: max_fix_rounds=5, post-fix-confirm=2 (v0.2.2 default)
   - Strict 1-session policy reminder

6. **Risk-tier classification**
   - P0 (forbidden for autopilot codegen): payment, admin auth, schema-changing migrations
   - P1 (autopilot OK, manual squash): user state changes, side effects, cross-feature impact
   - P2 (autopilot + manual squash for first 3 pilots; auto-merge OK after pilot maturity): pure features, isolated scope
   - F02-F08 default = P1 (touch user state) — manual squash per §6.5

**Time investment:** ~30-60 min prep per feature. **Net save:** ~2-4h via avoided cascade rounds + concurrency hazards.

## Open questions for F02 retrospective

After F02 ships → revisit:

- Did v0.2.2 budget (`max=5 + confirm=2`) absorb F02's cascade? Or did we need v0.2.4 budget split?
- Did 1-session-per-repo policy hold? Or did concurrency incidents recur?
- Did invariant audit pre-flight catch any spec contradictions before they cascaded?
- Self-dogfood paradox occurrences in v0.2.4+? At 3+ → consider code-level relaxation rule.
- Cumulative tooling backlog at end of F02 — fewer than F07's 9?

---

## Concrete v0.2.4 backlog (cumulative from F07 + v0.2.x)

Items deferred during F07 saga, scheduled for v0.2.4 batch:

1. **R6 P2 halt-message label diagnostic** — MAX_ROUNDS halt always cites `confirmation_rounds_after_last_fix` even when legacy gate fired. Cosmetic.
2. **Budget-semantics knob split** — currently `max_review_rounds` overloads "max fix rounds" + "max total rounds". Should split into explicit `max_fix_rounds + confirmation_rounds_after_last_fix`.
3. **Halt-report directory `-resume{N}` non-clobber** — mirror codex artifact non-clobber scheme.
4. **Codex CLI stale-blob true fix** — currently logs warning when SHA != HEAD. True fix needs codex CLI integration audit (pin explicit SHA, verify resolved blob).
5. **`.autopilot/locks/<repo-hash>.lock` advisory file lock** — currently doc-only "1 session per repo" policy. Code-level enforcement.
6. **Dashboard auto-rebuild scheduler races with founder pushes** — observed 5+ times during v0.2.2 + v0.2.3 + tracker push cycles. Need rebase-then-push retry built into orchestrator OR scheduler back-off.
7. **Self-dogfood paradox** — keyword-work PRs trip own keyword breakers. Manual override OK for now (1 occurrence in v0.2.3); revisit if recurrence ≥3 times.
8. **State schema version field** — when state.py adds new field (e.g. `last_active_phase` in v0.2.1, `rounds_since_last_fix` in v0.2.2), older state.json fails to load. Currently tolerated via filter-unknown-fields warning. Could add explicit `state_schema_version: int` for cleaner migration semantics.
9. **Tracker sync command / sidecar** — `tracker.update_status` currently no-op on feature branches. Founder updates manually. Could add `python -m tools.autopilot sync-tracker` CLI to centralize.

---

## Cross-references

- [project_f07_pilot_saga.md memory](../README.md) — F07 saga summary + lessons
- [feedback_project_level_effectiveness.md memory](../README.md) — 8-axis decision framework
- [feedback_prefer_autopilot_prompts.md memory](../README.md) — autopilot prompt default
- [feedback_autopilot_prompt_scope.md memory](../README.md) — single-phase scope rule
- [feedback_never_auto_delete_docs.md memory](../README.md) — docs file safety rule
- [wave0-retrospective.md](./wave0-retrospective.md) — Wave 0 7 lessons (this builds on)
- [autopilot-implementation-plan.md](../autopilot/autopilot-implementation-plan.md) §6.5 — risk tier policy
- [orchestrator-usage.md](../autopilot/orchestrator-usage.md) — orchestrator CLI reference
