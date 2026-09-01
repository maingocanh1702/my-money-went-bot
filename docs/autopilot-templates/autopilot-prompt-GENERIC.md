# Level 3 task prompt — generic

> Operational authority: `level3-workflow.md`.
> Use only for a new task/session/feature or a valid resume of that same task.

## Injected task contract

```text
TASK_ID:
SLICE_ID:
FEATURE_ID: <task-slug>|<task-slug>--<slice-slug>
AGENT_ROLE: primary_orchestrator|writer|supplemental_reviewer|security_reviewer
OUTCOME:
REPO_PATH:
DEFAULT_BRANCH:
BASE_SHA:
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
DEPENDENCIES:
WORKTREE_PATH:
MANIFEST_PATH: .autopilot/state/<FEATURE_ID>/manifest.json
STATE_DIR: .autopilot/state/<FEATURE_ID>
INVARIANTS:
VERIFICATION:
CODE_REVIEW:
SECURITY_REVIEW:
BUDGETS:
STOP_CONDITIONS:
DELIVERABLES:
AUTOPILOT_CODEX_BIN:
```

Missing a material field is `AWAIT_CONTEXT` or `HALT CONTRACT_INVALID`; never infer authority that
would change scope or risk.

## Role behavior

### Primary orchestrator

- Own the outcome end to end.
- Load live code/docs/decisions and relevant discussions.
- Split only independent mechanisms, then delegate bounded child tasks.
- Ensure one worktree/writer per writing slice and prevent scope/invariant collisions.
- Monitor agents, integrate results and drive the whole task to a terminal state.
- Resolve ordinary implementation choices; ask the human only for policy, budget, material
  decisions, exceptions or important external actions.

### Writer

- Work only inside the assigned worktree and scope.
- Do not create a second writer or edit another slice's files.
- Implement the smallest coherent mechanism and production-shaped regression tests.
- Self-verify before requesting independent review.

### Supplemental/security reviewer

- Remain read-only unless explicitly assigned a separate fix slice.
- Review the exact non-empty diff against `BASE_SHA`.
- Report actionable findings with file/region, impact and required resolution.
- A child-agent review is supplemental or security-focused context only. It cannot replace the
  mandatory pinned Codex code gate.

## Start gate

1. Read project README/HANDOFF/AGENTS/CLAUDE docs and every applicable Skill.
2. Verify repository identity, default branch, `BASE_SHA`, worktree path and current HEAD.
3. Verify scope gate, readiness gate and pinned Codex wrapper are present from the pinned base.
4. Re-read dependencies and the exact changed symbols/flows; run impact analysis when available.
5. Verify scope, negative scope, invariants, sandbox/network/secrets and external-effect boundaries.
6. For a writer, create:

   ```text
   <STATE_DIR>/regions.log
   <STATE_DIR>/fix-round-count.txt
   ```

7. Stop before writing when:

   - this is an already-running pre-template session being migrated in place;
   - the base/dependency/context is stale;
   - another writer owns the worktree or overlapping scope/invariant;
   - risk or permissions exceed the contract;
   - a material decision remains unresolved.

### Authoring a manifest — read the validator before you write the field

Four manifest fields are checked by code you can read in under a minute. Every one of them was authored
wrong in a single slice (Plexco `authorize-tenant-action-core`, 2026-07-30) by someone who knew the
policy and skipped the source. The writer caught all four at register time; none reached the reviewer.

| Field | Read this first | What goes wrong otherwise |
|---|---|---|
| `invariants` | the catalog's `<!-- catalog:start -->` block | Plausible-sounding tokens that do not exist → `HALT INVARIANT_UNKNOWN` |
| `verification.*` | `runVerificationGroup()` in the readiness script | Each string is SPAWNED as a shell command. Prose fails every attempt |
| `scope` | the gate's shape validation | Directories and malformed paths are rejected at register time (`CONTRACT_INVALID`); the diff is no longer checked against this declaration (kit v34) — `scope` still communicates intended boundary to a human/reviewer, but the certified file list is the diff itself |
| `code_review.clean_rounds` | your own risk tier | `1` on an authorization or money boundary is a review budget, not a gate |

The unifying failure is not carelessness about any one field. It is writing a **declaration** without
reading the **thing that validates it** — and each of those things was one grep away. In review mode
this same author is rigorous; in authoring mode they infer the adjacent-plausible value instead of
checking. Treat authoring as review of a document you have not written yet.

### An empty query result is evidence about your query first

The invariant-token error survived two attempts to catch it. Both greps were written for backticked
tokens; the catalog stores `token — description` with an em-dash and no backticks. Both returned
nothing, and nothing was read as *the catalog is empty* rather than *my pattern is wrong* — so the
author proceeded on invented tokens twice.

When a query over a file you did not write returns zero rows, the first hypothesis is that the query is
wrong, not that the world is empty. Confirm the shape before concluding the content: print a few raw
lines, or assert a token you already know is present. A search that cannot fail loudly is a search that
lies quietly — and "no results" is the most confident-looking lie a tool can tell you.

### A measurement that answers a neighbouring question looks exactly like a measurement

Both failures below happened on 2026-08-01, in the same slice, one of them mine as the orchestrator.
Neither was a case of trusting prose — in both, someone ran a real command and read the real output.

**Measure the sink, not the source.** A writer argued that attaching `{ cause: error }` exposed nothing
new, and proved it by enumerating the error object's own keys: no credentials, no client reference. The
enumeration was correct. It was also the wrong object. The question was what the *log* prints, and
`console.error` formats `.cause` recursively, so it emitted the whole `pg` error shape where the previous
code path — `String(error)` — had rendered only `error: <message>`. Two measurements were needed; one was
taken. When reasoning about exposure, run the sink and read its output. What the value *contains* and
what a consumer *renders* are different questions.

**A list is not a claim about a list.** Reviewing that same finding I enumerated the newly-printed
fields, then wrote that they "carry DDL already in the repo." That held for `internalQuery` and `where`.
It did not hold for `detail`, which on a constraint violation carries the offending row values — so a
backfill migration would print user data into deployment logs. I had `detail` in front of me, in a list I
wrote, and generalized across it without checking the members. Later in the same session I called an
error class's fifth instance its sixth, by incrementing a total instead of re-reading the table.

Both have one shape: **the summary of a set is a separate claim from the set.** If you enumerate, check
members individually before saying anything about all of them, and re-read a list before extending it —
never append to a count you are carrying in your head.

### A record's structured fields and its prose answer different questions

A backlog entry has two layers, and they are not redundant. The fields say where the problem is VISIBLE.
The prose says where it should be FIXED. In a kit-and-consumer setup those are routinely different places,
because symptoms live downstream and causes live upstream.

Measured 2026-08-03: an entry carried `scope: [docs/autopilot-manifests/, scripts/autopilot-onboard.sh, …]`
— every path in the consumer repo — while its notes closed with "belongs to the kit, not here; fixing it
here only patches the symptom." An orchestrator read the fields, wrote a task targeting the consumer, and
a session had to refuse it after verifying against the entry that had been cited as its own source.

The fields were not wrong. They correctly listed the six files showing dead citations. They simply do not
answer "where does this task run", and nothing in their shape says so.

**Before asserting where a task belongs, read the entry's prose to its last line.** In this project the
disposition is written at the end of `notes:`, after the evidence. A `scope:` field is an inventory of
affected files, never a routing decision.

The same habit — reading a field and inferring the claim behind it — produced three stale `close_by: hand`
declarations and a `negative_scope` clause that called a genuine stale call "shorthand". A field records
what someone concluded once; the prose records why, and why is what goes stale.

### Prose beside a mechanism is unchecked, which is exactly why it goes false

Every record here mixes two kinds of writing: values a script consumes, and prose a human reads. The
values are checked continuously — a wrong one fails a run. The prose is checked by nobody, so a
sentence that was true when written stays in the file long after it stops being true, and the next
reader believes it because it sits next to values that are correct.

Measured 2026-08-25, three instances in one hour, all by the same session while it was fixing this
exact class of defect elsewhere:

- An explanatory annotation was appended INSIDE a `merged_probe` value. `ap-land.sh` splits that field
  on `' :: '` and feeds the right-hand side verbatim to `git grep -qE`, so the prose became part of the
  regex. Landing would have merged, pushed, and only then failed the post-push probe.
- A commit message described a revert that was never staged. The claim was accurate about intent and
  false about the commit; `origin/main` carried the broken value under a message saying it was fixed.
- A manifest `_note` asserted two slices run in parallel after the contract beside it had been
  corrected to serial. It was left because "the gate does not read `_note`."

That last reason is the one to distrust. **"Nothing checks this field" is an argument for more care,
not less** — an unchecked claim is one that will never be corrected by a failing run, only by a person
who has already been misled by it. A field a script parses is worse still: prose there is not merely
stale, it is executable.

Two habits close it. Write no sentence about code, state or history that you cannot verify at the
moment you write it — grep the symbol, read the script that consumes the field, name the commit. And
when you correct a claim, grep the whole repo for its other copies before you call it fixed; the same
assertion is usually written in three places by three different authors.

### Docs-only work does not belong in a review gate

An adversarial reviewer converges on code and does not converge on prose. Code has a fixed point:
the tests pass, the types check, and the next round finds nothing because there is nothing left to
find. Prose has none — a careful reviewer can always locate one more sentence that overclaims, one
more citation whose line number moved, one more label that does not survive an edge case.

Measured 2026-08-25: three consecutive docs-only lifecycles on the same two files reached a terminal
halt. Rounds ran 6 → 3 → 4 → 3 → 6 → 1 on the first and produced five fresh findings on the fifth
attempt of the second. Every finding was real. None was a design defect. The content was ~95% correct
from round one and never became mergeable, because the stopping condition the gate enforces —
consecutive clean review rounds — is not reachable for a long, fact-dense document.

So route it differently: **a slice whose entire deliverable is prose does not go through the code
review gate.** Write it, verify each claim against live source as you write it, have a person read the
diff, commit. Keep the gate for changes where a test can say "done". A mixed slice — code plus the
document describing it — splits: the code goes through the gate, the document ships beside it.

### Registration mechanics — four facts that each cost a real slice to learn

These are not advice. Each one halted a live slice on first contact, and none of them is discoverable
from the manifest alone.

**`register` requires `HEAD === base_sha` exactly.** It is designed to be called *before* any commit
exists, so the reservation is taken while a scope collision is still cheap. If your branch already
carries commits — a successor slice inheriting a predecessor's work, or a re-registration after a
close — do **not** reset the branch. Reset makes the commits reachable only through a ref you create
for that purpose, which is a safety net you then depend on. Prefer the sequence that never puts them
at risk, executed twice on 2026-08-01:

1. `git branch archive/<feature>-preclose <tip>` — a named ref, made first, before anything moves.
2. `ap-finish.sh <feature> --authorized-close --reason <text>`, run from the repository root.
3. Delete the old branch. The archive ref holds the commits, so this is uncontested.
4. Create a **fresh worktree at the pinned base SHA**, which is what the canonical rule asks for
   anyway — one writing slice, one branch, one worktree, created from the base.
5. Write the manifests, `register`. `HEAD === base_sha` holds by construction.
6. `git merge --ff-only archive/<feature>-preclose`.

Step 6 is why this beats cherry-pick: if your commits sit on the pinned base — check with
`git merge-base --is-ancestor <base> <tip>` — fast-forward restores the *same objects*. Cherry-pick
mints new SHAs and then obliges you to prove the tree matches. **Prefer the operation with nothing to
prove.** Keep the archive ref until the slice merges.

**The runtime manifest is hash-locked the moment you register.** `register` writes
`<STATE_DIR>/registered-manifest.sha256`; `ready` halts with `MANIFEST_DRIFT` if the file is missing
**or** its contents differ. Deleting the hash file does not bypass the check — it is fail-closed both
ways. Practical consequence: **anything in the manifest that can go stale will force a full
close-and-re-register cycle.** Write `verification` as properties, never pinned literals; see
`_verification_rule` in `manifests/_TEMPLATE.json`.

**The authored contract and the runtime manifest are different artifacts with different lifetimes.**
`docs/autopilot-manifests/<task-slug>.json` is tracked, is the human contract, and must **never**
carry `manifest_schema_version` — the validator pins the runtime path, so adding it there makes
`register` halt with `CONTRACT_INVALID`. `.autopilot/state/<feature>/manifest.json` is the per-run
runtime manifest, is gitignored, and carries the full v2 field set. If your slice needs to amend its
own contract mid-flight, put the authored file in `scope` and amend it inside your diff — that lands
the contract change with the change it describes and needs no commit on the default branch.

**But be exact about what that buys, because the sentence above reads as more than it is.** Amending
the authored file changes the *human record*. It does not change one byte of what the gate enforces:
the gate reads the hash-locked runtime manifest, and editing that is `MANIFEST_DRIFT` while
re-registering the same feature is `FEATURE_ALREADY_ACTIVE`. So an authored-file amendment is real for
prose, notes and rationale — and **cosmetic for any field with teeth**: `negative_scope`, `scope`,
`security_review.required`, `budgets`, `stop_conditions`. Measured 2026-08-01: a slice amended
`security_review.required` in the authored file, believed a security round would run, and it did not.

If a field with teeth must change, there is no in-flight path. Close and rebuild by the sequence above.
Before spending a round on that, check whether the change is needed at all — see
`docs/kit-design-debt.md` §1, and note that a finding is closed by fixing code or by the reviewer
accepting a response, **not** by turning on a reviewer that was off.

**`ap-finish.sh` runs from the repository root, not from the worktree it removes.** It resolves the
root via `git rev-parse --git-common-dir`, so you never need a throwaway worktree to close a
reservation. `--authorized-close --reason <text>` retains the branch; only the worktree and the
reservation go.

**When scope changes, the review classification is stale until you re-derive it.** `risk`,
`security_review.required` and `code_review.clean_rounds` were set against the scope the slice had when
they were written. Widen scope and they describe a slice that no longer exists. Measured 2026-08-01: a
dependency-bump slice carrying `security_review.required: false` had its scope widened into the
database migration runner; the flag was not revisited, and the mismatch surfaced as a review finding at
the last available fix round, by which point the runtime manifest was hash-locked and the flag could not
be changed at all. Re-derive the classification **in the same edit** that changes scope — and if the
scope change arrives as an instruction from an orchestrator, re-derive it anyway and say so. The
orchestrator who widens the scope is exactly as likely to forget as you are; in that instance they did.

The same staleness applies to any pre-registered clause you might later cite in your own defence. A
`void_if` or negative-scope exemption authored under a narrower scope does not extend to work the scope
did not then cover. Citing one to dismiss a finding about the wider scope is leaning on authority that
expired when the scope moved.

## Implementation loop

1. Inspect only the bounded blast radius.
2. Write or update the decision table/test matrix before risky stateful logic.
3. Implement within scope; preserve unrelated WIP.
4. Add focused regression tests using production-shaped inputs.
5. During implementation, run focused verification and the repository's canonical
   build/typecheck/lint/test/e2e commands for fast feedback. The final readiness gate will execute
   every command declared in the manifest again and capture its own exit status/output.
6. Fetch/read the declared base ref without rebasing the active run. If it no longer equals
   `BASE_SHA`, HALT for a fresh successor; otherwise inspect `git diff <BASE_SHA>...HEAD` and reject
   an empty diff. Declared `scope` is intended boundary, not a diff-enforced ceiling (kit v34) — the
   gate certifies whatever the diff actually is.
7. For final certification, do not manufacture verification/review files or self-assert a clean
   status. Generate `readiness.json` mechanically: `node scripts/autopilot-review-readiness.mjs
   evidence --manifest "<MANIFEST_PATH>" --acceptance satisfied --breakers clear` reads identity
   (task_id/feature/base_sha/head_sha) from the same manifest/live-git-state register/ready already
   trust (kit v34) — you supply only the two judgment calls git cannot make. A hand-written file from
   `docs/autopilot-manifests/_READINESS_EVIDENCE_TEMPLATE.json` recording only identity, acceptance
   and breaker state is still accepted if correct; the generated form just cannot be malformed.
8. Call `scripts/autopilot-scope-gate ready --manifest "<MANIFEST_PATH>"`. The gate executes every
   focused/canonical/e2e command from the unchanged registered manifest, runs the required pinned
   Codex code rounds and any security round, captures command/exit/HEAD/base/diff evidence, and
   writes `gate-result.json`.
9. A gate review with any actionable finding is not clean. Read its generated gate log, fix,
   increment `fix-round-count.txt`, append `round-NN file:region` to `regions.log`, then rerun the
   complete gate. Never edit a generated gate log or `gate-result.json`.

Hard breakers:

- `fix-round-count > 5` → `HALT MAX_ROUNDS`;
- same `file:region` in three consecutive rounds → `HALT REGION_THRASH`;
- findings spreading across the design → `HALT SLICE_TOO_LARGE` and propose a fresh split;
- missing required reviewer/verifier → `HALT TOOL_UNAVAILABLE`.

Do not patch past a breaker.

## Terminal states

Every stop must be durable under `<STATE_DIR>` before reporting.

### READY

Only when:

- outcome and acceptance are satisfied;
- diff is non-empty and in scope;
- focused and canonical verification pass;
- required code/security reviews are clean;
- no writer or dependency issue remains.

Generate `readiness.json` (kit v34: `node scripts/autopilot-review-readiness.mjs evidence --manifest
"<MANIFEST_PATH>" --acceptance satisfied --breakers clear`, or hand-write the minimal identity +
`acceptance.status=satisfied` + `breakers.status=clear` from the installed template), then run:

```bash
scripts/autopilot-scope-gate ready --manifest "<MANIFEST_PATH>"
```

The readiness gate reruns declared verification and pinned reviews itself. It writes generated logs
plus `<STATE_DIR>/gate-result.json`; the scope gate writes `<STATE_DIR>/READY.txt` only after that
machine result passes.
Report outcome, files/slices, verification, reviews, residual risk and the exact human merge/deploy
action. Do not merge automatically.

### AWAIT

Use only for one concrete missing decision, context or external authority. Stop writes, write
`<STATE_DIR>/AWAIT-FOUNDER-<reason>.txt`, state the recommended option and provide a binary resume
condition. Remove that signal only when the named condition is satisfied and the contract
revalidates.

### HALT

Use for safety, scope, base, permissions, tool or loop-breaker failure. Write
`<STATE_DIR>/HALT-<REASON>.txt`, preserve forensic state, state the exact blocker and require a fresh
successor task when the current run is terminal.

## When a design probe is mandatory

This is a floor, not a ceiling. A repository's own rules may require a probe for more cases than
listed here, or narrow the skip exemption further — a stricter local rule wins wherever it overlaps
with this one. A consumer enforcing more than canonical is not drift to reconcile away.

Write `<STATE_DIR>/design-probe.md` before implementation begins whenever the slice has **any** of:

- **Money-adjacent** — a payment, settlement or credit path, or money math.
- **Create / choke-point** — a resolve-or-create helper (an idempotent upsert / find-or-create), or any
  function many callers will route through as a shared entry point.
- **Destructive / irreversible** — merge, drop, delete, unlink, hard-remove.
- **NL / fuzzy / parsing** — natural-language classification, fuzzy matching, free-text parsing.
- **Behaviour-divergence** — this case must be handled *differently* from a sibling or already-ratified
  pattern, so copying that pattern verbatim would be wrong (e.g. creating a record where a sibling
  correctly fails closed, or reordering a side effect relative to a destructive operation).
- **Amends merged core / ratified design** — widens a shared type, or supersedes a design decision
  already landed.
- **Schema / migration, or a cross-transport/adapter return-type change** — a shape change that fans out
  to multiple callers or transports.
- **New mechanism choice** — not a fix inside an existing mechanism, but a fresh choice of algorithm,
  data shape, or where a piece of logic lives.

**Skip only when the change is a strict 1:1 leaf:** exactly one call site, no create branch, no money
math, no destructive op, reuses an existing helper (no new mechanism), no divergence from a ratified
sibling. One-line test: *does this slice contain a decision a mechanical copy-paste would get wrong?*
Yes → write the probe. No → skip it, but still verify the READY diff yourself. When genuinely in doubt,
write the probe — the cost of one you didn't need is a few minutes; the cost of a missing one is a HALT
plus rework, or a silent behaviour bug that ships clean.

This is independent of risk tier. A P2 change can still require a probe — a new NL/fuzzy matcher is
mechanism-risky even though it is not money/schema/destructive — and a P1 change gets full review and
human merge regardless of whether any trigger above fires. This list decides whether you owe a
`design-probe.md` before writing code, not who merges the result.

**A required probe does not put every question in it on hold for a human (2026-08-02).** Three tiers:

1. **Mechanism — decide yourself.** Algorithm, data shape, code organization, how to test it. You just
   read the code, so you know more than anyone else on this axis. Record the options you considered and
   *why you rejected each one*, not only the option you picked — a probe recording only the winner
   cannot be checked later.
2. **Scope, sequencing, irreversible action — the owner's call.** What belongs to this slice versus a
   later one, round budget, deleting or overwriting data, ship order, splitting or merging slices. No
   amount of reading the code substitutes for knowing the project's queue and priorities.
3. **Reversing ratified behaviour or policy — the owner's call.** A previously-locked test expectation, a
   compliance or security position, anything that overturns a standing ruling.

Tiers 2 and 3 are the same authority boundary as "Deciding for the project" below, applied to a probe's
own questions — that section's precedence order and escalation criteria govern here too.

**Escalate even while still in tier 1**, the moment you find evidence against the choice you were about
to make that you cannot resolve yourself. That is exactly when deciding alone is most likely to be
wrong.

No gate reads `design_probe_required`; skipping a required probe is caught by a human or reviewer
noticing, not by a machine. See `docs/kit-design-debt.md` for whether that should change, and why it has
not, yet.

### Naming the trigger, not a section number

A manifest, HALT, AWAIT or review note that invokes this rule names the trigger inline — "money-
adjacent", "new mechanism" — never a section number. This exact list used to live at `§0.1` in this
file; the Level 3 rewrite (`b2893b9`, 2026-07-28) restructured the document without carrying it
forward, and six Plexco manifests that had cited `autopilot-prompt-GENERIC v0.6.1 §0.1` were left
pointing at nothing. New manifests kept copying the dead citation for weeks after the break was
noticed — including one merged 2026-08-02 — because nothing correct existed yet to copy instead. A
name survives a rewrite; a position never does.

## Deciding for the project — the precedence order

Default: **decide, record the reasoning and the runner-up, continue.** The protection against a wrong
call is not that you asked; it is that the decision is visible and reversible at the merge boundary,
which the owner still controls. Asking mid-slice buys little that merge review does not already buy.

"Best for the project" is only meaningful against a stated order. Use this one, highest first. Where two
options differ at any level, the higher level decides and the lower ones do not vote.

1. **Fail-closed and least-privilege.** Never trade these for anything below. Unknown state denies.
   An error never collapses into allow. An allowlist beats a denylist. No new write path is opened
   without an owner for both set and clear.
2. **Correctness under concurrency and partial failure.** A design that is right only when nothing
   races is not right. Prefer the option whose failure mode is a refusal, not a silent wrong answer.
3. **Reversibility.** Between two acceptable options, take the one that is cheaper to undo. This is
   what makes autonomous decisions safe at all — preserve it deliberately.
4. **No debt that depends on memory.** An exception someone must remember to clean up is worse than a
   narrower fix that needs no memory, even if the narrower one is uglier. If an exception is
   unavoidable, it carries a named owner and an expiry, never a global relaxation.
5. **Deadline and buffer.** Spend the scarce resource on the expensive part. Do the hard, risky work
   while the buffer is large; leave routine work for later, when it is cheap.
6. **Scope minimalism.** No unrelated upgrade, cleanup or refactor rides along, however tempting.
   A slice that also does something else is two slices reviewed as one.
7. **Newness and tidiness.** Lowest priority. "Latest" is not a reason. Neither is symmetry.

**Escalate to the owner only when one of these is true:**

- the action is irreversible outside your worktree — deploy, external side effect, data migration on
  live data, anything spending money or making a commitment to a third party;
- it changes what the product IS: scope, priority, what a user gets;
- it contradicts a decision already recorded in the repo — you may argue against one, but you may not
  quietly overrule it;
- the project has genuinely never expressed a preference and levels 1–4 do not separate the options.
  In that case ask ONCE and get the answer written into the decision log, so the same question is
  derivable next time instead of being asked again.

Everything else you decide. Record it where the reviewer will see it, name the option you rejected and
why, and make the reversal cheap. A decision you can point at is worth more than a question you deferred.

**What this does not automate, and should not:** it does not let you price a novel risk trade-off the
project has no position on, and it does not let you skip levels 1 and 2 because a deadline is close. If
you find yourself reasoning "security is fine here because we are in a hurry", that is level 5 trying to
outvote level 1, and it is exactly the failure this order exists to prevent.

## Before stopping to ask, check whether a decision actually exists

Stopping costs the owner's attention, and on a deadline it costs the very buffer the stop is meant to
protect. So the bar is not "would confirmation be nice" — it is whether an answer exists that you cannot
derive.

**A question belongs to the owner only if its answer depends on something not derivable from the
contract:** a preference, a risk appetite, a business priority, or an authority you do not hold. If the
answer follows from facts you measured plus constraints already written down, decide it, act, and report
the reasoning so it can be overturned cheaply.

Two real cases from the same repo, three days apart, show the line:

- **Owner's call.** `deps-security-bump` hit a package whose only patch was a breaking major that broke
  a consumer at runtime. The options were: accept a red advisory scan for a few days, leave an
  ignore-entry someone must remember to clean up, or force the major and fix the fallout. Those price
  different risks against each other. No amount of measurement chooses between them.
- **Not the owner's call.** `eslint-10-migration` finished its design probe and stopped to ask whether to
  use the already-eligible version its own manifest had PRE-AUTHORIZED, or wait 17 hours for a newer
  patch. The deadline was in the contract. The fallback version was in the contract. The probe added no
  fact that changed either. The stop transferred work upward and spent buffer on a question the contract
  had already answered.

The second one had a mandatory design-probe gate in its manifest — copied from the first, where that
gate existed because a genuine decision sat behind it. **A gate inherited without its reason becomes a
ritual**, and a ritual stop is indistinguishable from a real one until someone reads both contracts.
When you write a probe gate into a manifest, name the decision it protects. If you cannot name one,
the gate is a checkpoint, not a decision point: run the probe, record it, and continue.

If you do stop, make it cheap to answer: state your recommendation first, the one fact that would change
it, and what you will do if no answer arrives. "Which of these four?" with no recommendation is the
expensive shape.

## When a gate fires correctly, never edit what you feed it

A gate reads inputs you control: the manifest's `scope`, its `invariants`, the terminal-signal files in
the state dir, the declared `verification`. When a check fires, exactly one of those inputs is the
cheapest thing in reach — and changing it makes the symptom disappear without touching the cause.

That move is forbidden even with diagnostic intent. "I widened `scope` to see what fired next" and "I
widened `scope` to get past this" are the same action and produce the same artifact; the gate cannot
tell them apart, and neither can the next person reading the run. Observed twice in one day on Plexco:
a writer widened a manifest scope to step past a correctly-raised `SCOPE_DRIFT` (blocked by the
permission layer, self-reported, reverted), and an orchestrator considered deleting a durable HALT file
to resume a run. Neither was malicious. Both were the path of least resistance from a correct signal.

The tell is simple: **if your next edit would make the check pass without changing what the check is
about, stop.** Report the blocker with its exact text and the smallest real fix. A gate you can talk
your way past is not a gate — it is a delay, and every future run inherits the precedent you set.

Diagnosing is still allowed; do it read-only. Read the gate's source to learn what it compares, run it
against a scratch fixture outside the reservation, or reason from its error text. What you may not do
is write a value you already know to be false into a file the gate trusts.

## Non-negotiable boundaries

- **Never delete, rename or move a `HALT-*` or `AWAIT-FOUNDER-*` file.** Not to unblock yourself, not when
  the halt is plainly a setup gap that judged nothing, not when clearing it is obviously the right
  outcome. Write an AWAIT describing what you found and stop. Twice in two days a session reasoned
  correctly that a halt was pre-review — `fix-round-count` at 0, no `gate-attempt-count.txt`, an empty
  `regions.log` — and acted on that reasoning, and both times the registration had to be closed. The
  correct classification is exactly what makes deleting it feel safe, which is why this binds on the ACT
  and not on the reasoning. The party who benefits from a blocker being cleared is never the party who
  clears it.
- No force-push, `git add -A`, silent scope expansion or destructive cleanup of unrelated WIP.
- One worktree and one live writer per writing slice.
- P0 live actions are preparation-only without explicit human execution authority.
- Level 3 does not imply auto-merge or permission to perform external important actions.
- Optional formal activation/certification machinery never blocks this operational worker.
