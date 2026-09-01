<!-- workflow-authority: level3-operational -->
# Level 3 workflow for future tasks

> **Canonical operational contract.**
> Source model:
> [Steps of AI Adoption — Step 3: Supervised autonomy](https://claude.ai/code/artifact/bfdfaef9-bc62-4dfe-ba9e-c58a26c9accf).
> Applies only to a task/session/feature opened after this template is installed or refreshed.
> It never changes, resumes or reclassifies a session that was already running.

```text
WORKFLOW_LEVEL: 3
WORKFLOW_MODE: supervised_autonomy
HUMAN_ROLE: manager_of_managers
DEFAULT_MERGE_MODE: human_approved
DEFAULT_STOP_MODE: STOP_AT_READY
```

## 1. What Level 3 means here

Level 3 is an operating model:

- Claude receives enough context from code, project docs and relevant decisions/discussions.
- The primary agent owns the outcome, decomposes the work and delegates bounded slices to agents.
- Every writing agent is isolated in its own worktree; two writers never share one worktree.
- Agents verify their own work with the repository's real build, tests, lint/typecheck and relevant
  end-to-end checks before asking for review.
- Code review is automatic by default; security review is automatic for security-sensitive changes
  and whenever the repository provides it.
- The primary agent monitors progress, resolves ordinary implementation choices and reports
  exceptions instead of asking the human to steer every step.
- Repeated, proven routines may be triggered proactively. New, ambiguous or high-risk work remains
  supervised.
- The human owns policy, priority, budget, material product decisions, exceptions, outcome review
  and merge/deploy authority.

The artifact's agent counts are a scale illustration, not an acceptance criterion. A tiny task does
not need artificial fan-out. Parallelism is used only when at least two slices are genuinely
independent.

## 2. Forward-only boundary

At the beginning of every new task, record:

```text
LEVEL3_WORKFLOW: required
TASK_START_STATE: new_after_template_effective
AUTONOMY_MODE: supervised|proactive_routine
```

An already-running session keeps its existing contract until it reaches a terminal state. It must
not be migrated in place. A follow-up created after termination is a new task and uses this
workflow.

No global activation watermark, release epoch or certification ceremony is required to use this
operational workflow. Those mechanisms may be added later as optional enterprise hardening, but
they cannot block an ordinary future task.

## 3. Required task contract

Before implementation, the primary agent creates or resolves this compact contract from the user
request and live repository:

```text
TASK_ID:
OUTCOME:
REPOSITORY_AND_BASE:
CONTEXT_SOURCES:
APPLICABLE_SKILLS:
SCOPE:
NEGATIVE_SCOPE:
RISK: P0|P1|P2|P3
AUTONOMY_MODE: supervised|proactive_routine
MODEL_POLICY:
SANDBOX_AND_PERMISSIONS:
HUMAN_DECISIONS_REQUIRED:
SLICE_GRAPH:
WORKTREE_PLAN:
VERIFICATION:
CODE_REVIEW:
SECURITY_REVIEW:
BUDGETS:
STOP_CONDITIONS:
DELIVERABLES:
```

Rules:

- Read the repository handoff/README and inspect live code before planning.
- Use code intelligence or focused search to identify symbols, callers and blast radius; do not read
  the whole repository by default.
- `CONTEXT_SOURCES` names exact code/docs/decision/discussion inputs. Missing material context is an
  `AWAIT_CONTEXT`, not permission to invent it.
- `APPLICABLE_SKILLS` names reusable instructions that must be loaded; new durable guidance is
  captured as a Skill or lazy reference after the task.
- `MODEL_POLICY` assigns planner/worker/reviewer roles and an explicit fallback. The mandatory
  independent code gate is the canonical pinned Codex wrapper; the implementing agent or a
  Claude/sub-agent review cannot replace it. Security-sensitive work also gets a security-focused
  pinned Codex round and any stricter project scanner.
- `SANDBOX_AND_PERMISSIONS` declares network, secrets, external side effects and approval
  boundaries before delegation.
- Scope is a ceiling. Each slice names one mechanism and an explicit negative scope.
- Dependencies form a directed graph. Parallel slices must be file-, invariant- and state-disjoint.
- The agent recommends the highest-benefit option when a decision is needed; it does not forward an
  unranked menu to the human.

## 4. Roles

### Human

The human supplies or approves only:

- desired outcome and priority;
- policy and non-negotiable constraints;
- budget or deadline ceilings;
- material product/design choices that cannot be derived;
- exceptions to established policy;
- final outcome review, merge, deployment or other important external action.

The human is not expected to write prompts for every child agent, monitor keystrokes or route normal
implementation steps.

### Primary agent

The primary agent:

- owns the task end to end;
- builds the context pack and task contract;
- derives risk and selects the autonomy mode;
- splits work into bounded slices;
- creates/delegates agents and monitors them;
- integrates findings and prevents scope collision;
- drives verification and review to a terminal result;
- reports outcomes, evidence, exceptions and next action.

### Child agents

Each child agent receives one bounded outcome, exact context, scope/negative scope, dependencies,
verification commands and stop conditions. A child may create further children only when that
delegation is bounded and does not create a second writer in the same worktree.

## 5. Lifecycle

```text
request
→ load project context
→ inspect live repository and dependencies
→ derive risk, decisions and autonomy mode
→ create task contract and slice graph
→ reserve one worktree per writing slice
→ delegate independent slices
→ implement + self-verify
→ automatic code review + relevant security review
→ fix within hard loop breakers
→ integrate and run full verification
→ READY | AWAIT | HALT
→ human outcome review / merge
→ capture reusable learning in docs, tests, Skills or routines
```

The primary agent continues while safe in-scope progress exists. It does not pause merely to ask
what to do next.

## 6. Risk and autonomy

| Risk | Typical work | Level-3 behavior |
|---|---|---|
| `P0` | Live production/control mutation, secrets, irreversible financial or privilege action | Analyse/prepare only; no tracked/product/external mutation; require explicit human execution authority |
| `P1` | Money, identity, auth, permission, schema/migration, destructive or shared choke point | Supervised, isolated, full verification, independent review, human merge |
| `P2` | Bounded product/code/tooling/docs change | Supervised by default; proactive only after the routine earns trust |
| `P3` | Read-only/report-only or unclassified | No tracked/product mutation; report plus ignored terminal telemetry |

`proactive_routine` is allowed only when all are true:

- the task class is narrow and repeatable;
- scope, tests, review and rollback/stop rules are encoded;
- recent comparable runs were successful without material human steering;
- the trigger and budget are authorized;
- current context and dependencies are fresh.

Any failed assumption, scope expansion, security uncertainty, missing context or repeated review
thrash drops the task back to supervised handling or HALT. Auto-merge is never implied by Level 3.

## 7. Worktree and delegation rules

- One writing slice = one branch + one worktree + at most one live writer.
- Use one cohesive slice by default. For multiple slices, the stable feature identity is
  `<task-slug>--<slice-slug>`; a one-slice task may use `<task-slug>`.
- The main worktree stays on the repository default branch.
- Create every feature worktree from the explicit, verified default-branch SHA.
- Read-only research/review agents may share source context but never mutate another writer's tree.
- Register parallel scope before writing when the repository has the scope gate.
- Use isolated databases, ports, caches and test state per worktree.
- Serialize slices that share a stateful invariant, migration order, generated artifact or mutable
  external system.
- A dependent slice starts only after its dependency is landed on a freshly pinned base. Each
  dependency carries a mandatory unique-symbol proof binding its dependency base, landed SHA and
  downstream base. Registry absence alone is not landing proof. Do not let a slice consume an
  unmerged sibling worktree implicitly.
- When two or more independent slices form one outcome, create an ephemeral no-push integration
  worktree from their common base, combine only the exact READY tips, run combined verification and
  discard it after evidence. This is integration evidence, not merge authority. Name that worktree
  `_integ-<task-slug>`: it is the one worktree with no reservation and no finish record, so the
  watchdog must be able to recognise and ignore it by name — without the prefix it is announced as a
  new session and then reported as a lifecycle orphan when you discard it, training the founder to
  ignore the alert that matters.
- Remove a worktree only after its terminal state and merge/disposition are verified.

## 8. Verification and review

Every code-writing slice must declare commands that the final readiness gate executes directly:

1. run focused tests for the changed behavior;
2. run the repository's canonical build/typecheck/lint/test command;
3. run production-shaped or end-to-end verification when the behavior crosses a real boundary;
4. inspect the exact diff against the pinned base;
5. receive an independent code review;
6. receive security review when the change touches trust boundaries, auth, secrets, permissions,
   external input, money or deployment.

The default independent reviewer is `scripts/codex-review-pin.sh`. The final gate invokes it
directly, binds every round to the current HEAD/base/diff and accepts only the exact clean verdict
marker. A trust-boundary slice runs a separate security-focused round through that wrapper;
project-native scanners augment it.

Three invocation facts, each of which has already cost a wasted round:

- **`--base` is the slice's pinned `base_sha`, the same value every round — never `HEAD^`.** The base
  is immutable by contract: the readiness gate reads it from the manifest and halts `BASE_STALE` once
  the base ref moves. `HEAD^` coincides with it only while exactly one commit sits above the base;
  after a follow-up fix commit `HEAD^` becomes the previous feature commit, so the round reviews the
  fix alone and silently drops the rest of the slice out of the change set. Read `base_sha` from the
  manifest or take a verified SHA from `git rev-parse` — never from `git log --oneline`, whose short
  SHA the wrapper's adapter form rejects as `CODEX_REVIEW_CONTRACT_INVALID`.
- **Know which component enforces what; the wrapper is thin.** Its three-argument adapter form
  `review --base <full SHA> <marker-prompt>` checks the SHA's shape and then asks the reviewer to
  review exactly `git diff <base>...HEAD`, explicitly permitting it to read live source for context;
  any other argument shape falls straight through to native `codex review`. The wrapper does **not**
  reject an empty diff or a dirty tree — `autopilot-review-readiness.mjs` does, as `EMPTY_DIFF` and
  `WORKTREE_DIRTY`. Do not attribute gate behaviour to the wrapper or vice versa; read whichever one
  you are about to describe.
- **The change set under review is committed history, so commit before invoking.** An uncommitted fix
  is outside `<base>...HEAD` no matter how visible it is on disk, and a base equal to `HEAD` leaves
  nothing to review — not a clean round but no round at all. Then a follow-up commit per round of
  findings. Note also that `scripts/codex-review-pin.sh` is the post-install path: in this template
  repository, the canonical source, the wrapper is at `autopilot/parallel/codex-review-pin.sh` and
  there is no `scripts/` copy, so the installed path fails with `no such file or directory` — easy to
  miss when it scrolls past between other output.

A review with any actionable finding is not clean. A clean review of an empty diff is not evidence.
If a required reviewer or verifier is unavailable, emit `HALT TOOL_UNAVAILABLE`; do not silently
downgrade the gate.

Loop breakers remain hard:

- more than five fix rounds → `HALT MAX_ROUNDS`;
- the same region in three consecutive rounds → `HALT REGION_THRASH`;
- findings spreading across the design → stop and re-slice rather than continue patching.

### Four known gaps in this gate — measured, unresolved, do not work around them silently

Recorded here rather than patched, because each fix carries a gaming risk that needs an owner decision,
not a quiet edit. Items 1–3 were surfaced by live slices on 2026-07-30, item 4 on 2026-08-01.

This heading read "Two" while numbering three items — corrected 2026-08-01. Anyone adding a fifth should
re-count the list rather than increment this sentence; miscounting an enumeration by carrying the total
in your head is a recurring failure in this kit, documented in `docs/kit-design-debt.md` §1.

**1. The reviewer receives no scope, so an out-of-scope suggestion halts like a defect.**
The review invocation passes exactly `--base <sha>` and a fixed prompt. It does not pass the manifest,
`scope`, `negative_scope` or any owner decision. The reviewer therefore cannot distinguish *"this
change is wrong"* from *"you could also do more"*, and there is no waiver channel — `REVIEW_FINDINGS`
halts unconditionally, and only the exact clean marker proceeds.

Observed: a slice bumping `postcss` to close an advisory was halted because a *later* release contained
unrelated upstream hardening with no CVE, on a code path unreachable in that repo. The same reviewer
stayed silent about a genuinely unfixed CVSS-7.5 advisory elsewhere in the tree — not by judgement, but
because those lockfile lines were not in the diff. Visibility, not severity, decided which one halted.

Candidate fixes, none free: pass `negative_scope` into the review prompt (a writer could then widen it
to silence findings); split the verdict into blocking vs advisory (needs a second marker and a rule for
who may downgrade); leave as-is and accept that scope changes must be made by removing the file from
the diff, which is what that slice ultimately did. **Until this is decided, the correct response to an
out-of-scope finding is to take the item out of the diff — never to argue with the reviewer or to
re-run hoping for a different verdict.**

**2. Reviewer auth-tier failures are classified as terminal `HALT`, not resumable `AWAIT`.**
The gate already distinguishes reviewer conditions that a human can fix and resume from defects that
end a lifecycle: `CODEX_QUOTA`, `CODEX_AUTH_REQUIRED` and `CODEX_CONNECTOR_PERSISTENT` all take the
`awaitReview()` path, whose resolution text is "resolve the reviewer condition, remove this signal,
then resume the same in-flight lifecycle."

But the auth detector matches only 401-shaped failures — `401`, `token_invalidated`, `invalid_grant`,
`log in again`. Observed 2026-07-30: after the operator re-authenticated mid-run, the pinned reviewer
returned `status 400 invalid_request_error: The 'gpt-5.6-sol' model is not supported when using Codex
with a ChatGPT account.` That is an auth-*tier* problem — the same class as `CODEX_AUTH_REQUIRED`, and
fixed the same way — but it matches none of those patterns, so it fell through to
`REVIEW_UNAVAILABLE`, a **durable HALT** whose resolution demands closing the lifecycle and
re-registering a successor.

The slice in question had already completed three real review rounds that day; the reviewer worked and
then stopped working for reasons entirely outside the diff. Paying a full close-and-re-register cycle
for an operator auth change is the wrong price, and the gate has the right mechanism one branch away.

Candidate fix: widen the auth detector to include model-permission and entitlement refusals (400-class
`invalid_request_error` naming an account type or an unsupported model) so they route to
`CODEX_AUTH_REQUIRED`. The care needed is not to swallow genuine 400s caused by the *request* the gate
built — a malformed `--base`, an oversized diff — which are real gate defects and must stay terminal.
Until that is decided, an operator who recognises this specific failure may treat the HALT as an AWAIT,
but must say so explicitly and record why; an agent must not make that call on its own.

**3. `fix-round-count` increments on infrastructure failures, not just on diff defects.**
Observed: two consecutive rounds consumed by a Postgres `57P01 admin_shutdown` during test teardown —
255/255 assertions passing, zero code change, container healthy on restart. Those two rounds were 40%
of the budget, and the slice then hit `MAX_ROUNDS` on a round that had found a real defect.

Raising the ceiling is the wrong fix: the breaker exists to catch *design thrash*, and a higher number
just makes it less sensitive to the thing it was built for. The problem is classification, not the
threshold. A writer already invented the natural syntax — `round-NN infra:<reason>` in `regions.log`.
The gaming risk is obvious: a writer that may self-declare `infra:` may relabel a real finding to dodge
the breaker. Any fix must gate that label on a checkable condition — zero diff against the previous
round, and no reduction in assertion count — or it opens a worse hole than it closes.

**4. An authorized change has no path into a hash-locked registration.**
The lock is correct and must stay. What is absent is any route for a change that is authorized,
necessary, and not an attempt to escape the gate. Five instances on 2026-07-31/08-01, every one resolved
by a full close-and-rebuild: the `base_sha` overload, the `ap-finish` diff-base skew, an owner-authorized
lint exception that existed only in the authored manifest, a branch already carrying commits that
`register` cannot accept at all, and a `security_review.required` flag that could not be flipped
mid-flight. Enumerated in `docs/kit-design-debt.md` §1, which is the register for open kit design
questions and is deliberately not the test-suite spec.

Note the interaction with item 3, because it is easy to miss: re-registration resets `fix-round-count`
to zero, so `MAX_ROUNDS` is not a budget but a checkpoint a slice can move by rebuilding itself. That is
legitimate when a slice has **accepted** a finding and the fix needs scope the current registration
cannot express; it is laundering when the slice intends to contest the same finding with a refreshed
budget. Until that distinction is enforced by something other than judgement, state which one you are
doing and why, in the close reason.

Item 3's conclusion holds here too and is worth repeating where a reader will hit it: **raising the
ceiling is the wrong fix.** On 2026-08-01 a slice exhausted 5/5 arguing that a security finding was a
false positive, halted, and handed off — whereupon the finding proved valid and worse than described.
More rounds would not have found that; the slice was reasoning, not measuring. The cap converted a
losing argument into a review that found the real defect. That is its function, not its limitation.

## 9. Terminal states

### READY

Use only when scope, verification and reviews are complete. Report:

- outcome;
- changed files/slices;
- tests/build/review/security evidence;
- remaining risks;
- exact merge/deploy action requiring the human.

A P1/P2 writing slice reaches READY only through its scope/readiness gate and worktree
`READY.txt`. A P0 prepare-only or P3 report-only task has no writer and makes no tracked, product or
external mutation; its only repo write is ignored local telemetry under the repo-root
`.autopilot/state/<task-slug>/READY.txt` after its non-mutating deliverable is complete.

### AWAIT

Use only for a concrete missing human decision, external authority or context that materially
changes the result. Preserve work safely, stop writers and provide one recommended option with
trade-offs and a binary resume condition.

Write `AWAIT-FOUNDER-<reason>.txt` in the current worktree state directory, or the repo-root task
state directory when no worktree exists.

### HALT

Use for a hard safety, scope, authority, tool or loop-breaker failure. State the exact reason,
forensic state and the condition for a fresh successor task. Do not keep patching after HALT.

Write `HALT-<REASON>.txt` in the same canonical state directory before reporting.

## 10. Learning loop

After a terminal task:

- turn a discovered bug into a regression test;
- record durable business/security decisions in project docs;
- move repeated operational guidance into a Skill or lazy-loaded reference;
- promote a task class to `proactive_routine` only from observed successful evidence;
- demote or tighten a routine after an exception;
- monitor cycle time, review rounds, human interventions, failures and cost where tooling exists.

The question after a failure is “what context, guardrail, test or routine was missing?”—not “who
failed to watch the agent closely enough?”

## 11. Two manifest artifacts, one name

A slice has **two** manifest files with different roles. Confusing them wastes a session, and the
mistake is easy because the shipped template looks like the wrong one.

| | Authored contract | Runtime manifest |
|---|---|---|
| Path | `docs/autopilot-manifests/<task-slug>.json` | `.autopilot/state/<FEATURE_ID>/manifest.json` |
| Tracked in git | yes | **no** — `.autopilot/*` is gitignored |
| Lifetime | permanent; reviewed, versioned, cited by verdicts | one run |
| `manifest_schema_version` | absent | `level3-operational-v2` |
| Written by | a human or an authoring session, before launch | copied/resolved at register time |

`autopilot-review-readiness.mjs` **fail-closes** unless the manifest it is handed sits at exactly
`.autopilot/state/<FEATURE_ID>/manifest.json` — any other path is `HALT CONTRACT_INVALID`. So marking
a tracked `docs/autopilot-manifests/*.json` with `manifest_schema_version: level3-operational-v2`
does not "upgrade" it; it makes `register` halt. The version string is a **role marker on the runtime
copy**, not a maturity level on the authored contract.

Two corollaries worth stating because both have been guessed wrong:

- A repo whose tracked manifests carry no `manifest_schema_version` is **not** running an old
  workflow. Do not open a task to "migrate the manifests to v2."
- The review gate does not depend on that string. `autopilot-scope-gate` sets `REVIEW_REQUIRED=1` if
  the schema is v2 **or** `review_gate_version` is set **or**
  `scripts/autopilot-review-readiness.mjs` merely exists on the pinned base ref. If the validator is
  installed, the gate is already active.

`parallel/manifests/_TEMPLATE.json` is the **runtime** shape. Copy it to the state dir; do not
mistake it for the schema of the tracked contract.

## 12. Anti-drift rules

Every rule here exists because a repository already paid for its absence.

**Do not hard-pin a value the reader can measure.** A SHA, version number, file count, test count or
migration tail written into prose is stale from the moment the thing it describes moves — and it
reads as fact precisely because it is specific. Point at the measurement instead: cite the file and
the command (`awk '/^# KIT_VERSION:/{print $3; exit}' scripts/autopilot-scope-gate`), or state the
value as a **condition** that verifies itself. A launcher that says "created from `<sha>`" is stale as
soon as the commit adding that launcher lands; "the worktree must sit on a tip that already contains
this launcher — which is self-verifying, because you could invoke it" never goes stale.

**When a measurement disagrees with the contract, the measurement wins — and the disagreement is
recorded, not silently corrected.** A number that was measured once and copied forward is a claim
about the past. Say which source you read, when, and what changed. Silently updating a figure
destroys the evidence that the estimate was wrong, which is usually the more useful finding.

**A `not required` judgement needs a condition that voids it.** `SECURITY_REVIEW: not required` with
no escape clause is a decision frozen against facts not yet known. Write the reason **and** the
trigger: "not required — no auth/secret/money/external-input surface. If the probe finds otherwise
(e.g. a money-path table in the set), this judgement is void: add a security round and say why."

**A slice that finds something outside its own scope needs a sanctioned way to emit it.** Refusing to
edit an out-of-scope file is correct discipline — but the finding then lives only in the session
transcript, and a transcript is not a queue: nothing scans it. Before reaching a terminal state, write
every out-of-scope finding into the project's backlog or issue tracker as its own entry, even a
one-line placeholder. This is an explicit exception to negative scope, limited to the backlog/tracker
file, and it is part of the deliverable rather than a courtesy.

**Prefer de-pinning to re-pinning.** When a pinned figure goes stale, the cheap fix is to update the
number and the durable fix is to remove the pin. Updating buys time until the next change; de-pinning
ends the class. A sweep that replaced hard-pinned migration tails with "verify the current tail at
`<dir>`" later saved seventeen files from a second sweep.

## 13. Readiness check

A repository is ready to run a new task with this workflow when:

- this contract and the global invariants are visible to the session;
- the repository has a handoff/README and canonical verification commands;
- worktree isolation is available;
- the task contract identifies context, scope, risk, slices and stop conditions;
- independent code review is callable for code-writing work;
- `/ap-init` reports `KIT_ON_ORIGIN: ready` and the current canonical complete pack is present on
  the pinned origin base: scope/readiness/reviewer,
  verified finish + read-only housekeeping scripts, scope guide, manifest/evidence templates and
  invariant catalog;
- the human merge/deploy boundary is explicit.

If a project lacks an optional automation such as proactive triggers, analytics or a security
scanner, it still runs Level 3 in supervised mode and records that capability as a follow-up. It
must not claim the missing automation ran.
