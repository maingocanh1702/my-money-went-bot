# Parallel scope gate

The scope gate coordinates Level 3 writing slices. It does not create a worktree, launch a writer,
derive risk, review code or merge.

## Register

```bash
scripts/autopilot-scope-gate register \
  --manifest .autopilot/state/<FEATURE_ID>/manifest.json
```

The Level 3 task contract requires:

```text
feature
branch
risk
base_ref
base_sha
depends_on[]
dep_checks[]  # one same-order unique-symbol landing proof per dependency
invariants[]
scope[]
negative_scope[]
writer_processes_max=1
```

For `level3-operational-v2`, the installed readiness validator checks the resolved manifest,
task-scoped identity, branch, pinned base SHA/ref, worktree HEAD, exact scope, negative scope,
one-writer ceiling, review policy, permissions and verification commands before registration.
Process liveness still requires primary-agent/worktree inspection.

`scope` entries must be exact file paths for this script's equality-based collision check. If a
slice cannot enumerate files safely, serialize it with a shared invariant token; directory/glob
overlap is not machine-detected by this helper.

Final diff enumeration disables rename detection, so a rename/delete requires both the source and
destination in scope; declaring only the destination cannot hide an undeclared source removal.

For each dependency, `dep_checks` must bind:

```text
feature
base_sha
landed_sha
file
symbol
```

The identifier symbol must be absent on the dependency base, present at the landed SHA and still
present on the downstream pinned base. Both SHAs must have the required ancestry. This makes
registry absence insufficient as landing proof.

Registration fails when:

- a dependency is still active;
- a scope path intersects another active slice;
- an invariant token intersects another active slice;
- an invariant is unknown to the catalog;
- a dependency is active or its mandatory unique landing proof is invalid;
- the base/worktree/contract fails the Level 3 validator.

Use the task-scoped `FEATURE_ID`. An active duplicate is rejected instead of silently replacing its
row.

Create and verify the explicit-base worktree first, then register from inside that worktree before
implementation. Registration alone grants no permission to write outside the task contract.

## Ready

```bash
scripts/autopilot-scope-gate ready \
  --manifest .autopilot/state/<FEATURE_ID>/manifest.json
```

The script requires an active registration, rechecks collisions and invokes
`scripts/autopilot-review-readiness.mjs`. A Level 3 manifest fails closed when the validator is
missing. READY requires a real commit/non-empty diff (kit v34: the diff is certified as whatever it
actually is, no longer required to equal declared `scope` — see that version's note in
`autopilot-scope-gate`), clean worktree, matching minimal `readiness.json`, an unchanged
registered-manifest hash and clear breakers. The validator directly
executes every declared verification command and required pinned-Codex/security round, binds the
generated logs to HEAD/base/diff, and writes `gate-result.json`. Only then does the scope gate write
`READY.txt` and move the registry row.

Every new `ready` attempt invalidates any older `READY.txt` and `gate-result.json` before work
begins. Landing requires the gate-result attempt to equal the latest attempt counter and rejects a
pending review finding, so a later failed rerun cannot fall back to stale PASS evidence.

The final reviewer uses a sanitized system-home environment; per-invocation
`AUTOPILOT_CODEX_*`/`BASH_ENV`/`NODE_OPTIONS` overrides cannot replace it. A normal feature also
cannot certify a diff that changes its own scope gate, readiness validator or Codex wrapper; update
that trust pack through the separately reviewed/versioned kit-maintenance path.

Non-Level-3 legacy manifests may still receive a clearly labelled registry-only warning; that path
cannot claim this operational profile.

## Cleanup

Cleanup happens only after authorized merge/disposition is verified and no writer/review is active:

```bash
scripts/ap-finish.sh <FEATURE_ID>
```

Directly deleting a worktree without releasing the shared reservation leaves stale state.
Normal merge ancestry is verified against origin before cleanup; an exact squash needs matching
READY patch evidence, while unmerged closure needs an explicit reason and durable disposition
record as described in `parallel/README.md`.

`scope-gate cleanup` is an internal final step of `ap-finish`: it rejects a raw call unless a
valid task-matching landing/disposition record already exists. Watchers and housekeeping tools
never release reservations themselves.

## Parallel safety

File-disjoint work can still collide on a shared domain invariant. Broad tokens such as schema,
money model, auth policy or generated API contract intentionally serialize work. Re-scope and
register the final manifest before a writer starts; after writing begins, material
scope/base/design drift requires HALT and a fresh successor slice.

This gate is sufficient for the supervised operational workflow when combined with explicit-base
worktrees and review evidence. Formal global receipt/activation/certification enforcement is an
optional extension.
