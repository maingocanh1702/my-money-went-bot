#!/usr/bin/env node

import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  readdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { userInfo } from "node:os";
import path from "node:path";
// Explicit import, not the implicit Node global: a consumer repo that lints scripts/ (ESLint's
// `ignores: ["*.mjs"]` matches only the repo ROOT, so scripts/*.mjs IS linted) otherwise fails with
// 11 x `'process' is not defined` under js.configs.recommended, turning `pnpm lint` and its CI job red
// the moment this pack lands. Observed in Plexco at kit v11, 2026-07-29. The sibling
// check-review-readiness.mjs already imports it this way.
import process from "node:process";
import { createEphemeralReviewWorktree } from "./autopilot-ephemeral-review-worktree.mjs";
import { describeUnknownEvidenceKeys, findUnknownEvidenceKeys } from "./autopilot-readiness-evidence-keys.mjs";

const VERSION = "level3-readiness-v2";
const REVIEW_TOOL = "scripts/codex-review-pin.sh";
const TRUSTED_GATE_FILES = new Set([
  "scripts/autopilot-scope-gate",
  "scripts/autopilot-review-readiness.mjs",
  // The readiness-evidence whitelist lives here: widening it would let a writer self-assert extra
  // state, so an edit to it must trip SELF_CERTIFYING_GATE_CHANGE like any other trust-gate file.
  "scripts/autopilot-readiness-evidence-keys.mjs",
  // Reviewer isolation lives here: a helper-only change could alter what the reviewer can read, so it
  // must trip SELF_CERTIFYING_GATE_CHANGE like any other trust-gate file.
  "scripts/autopilot-ephemeral-review-worktree.mjs",
  REVIEW_TOOL,
]);
const MAX_BUFFER = 20 * 1024 * 1024;
const DURABLE_HALT_CODES = new Set([
  "BASE_DRIFT",
  "BASE_MISMATCH",
  "BASE_STALE",
  "BRANCH_MISMATCH",
  "BREAKER_ACTIVE",
  "BREAKER_EVIDENCE_MISSING",
  "CONTRACT_INVALID",
  "DEPENDENCY_NOT_LANDED",
  "DEPENDENCY_PROOF_INVALID",
  "DEPENDENCY_PROOF_REUSED",
  "EMPTY_DIFF",
  "GATE_INPUT_DRIFT",
  "GATE_TIMEOUT",
  "MANIFEST_MISSING",
  "MANIFEST_DRIFT",
  "MAX_ROUNDS",
  "READINESS_COMMAND_FAILED",
  "READINESS_JSON_INVALID",
  "REGION_THRASH",
  "REQUIRED_TOOL_UNAVAILABLE",
  "REVIEW_UNAVAILABLE",
  "REVIEW_VERDICT_INVALID",
  "REVIEW_WORKTREE_UNAVAILABLE",
  "SCOPE_DRIFT",
  "SELF_CERTIFYING_GATE_CHANGE",
]);
let durableStateDir;

function deriveDurableStateDir(repo, manifestFile) {
  const relative = path.relative(repo, manifestFile).split(path.sep);
  if (
    relative.length === 4
    && relative[0] === ".autopilot"
    && relative[1] === "state"
    && /^[a-z0-9][a-z0-9._-]*$/.test(relative[2])
    && relative[3] === "manifest.json"
  ) {
    durableStateDir = path.dirname(manifestFile);
  }
}

function halt(code, message) {
  if (durableStateDir && DURABLE_HALT_CODES.has(code)) {
    try {
      mkdirSync(durableStateDir, { recursive: true });
      const safeCode = code.replace(/[^A-Z0-9_-]/gi, "_");
      const signalPath = path.join(durableStateDir, `HALT-${safeCode}.txt`);
      if (!existsSync(signalPath)) {
        writeFileSync(
          signalPath,
          [
            `HALT ${code}: ${message}`,
            `created_at_utc: ${new Date().toISOString()}`,
            "resolution: close this terminal lifecycle and create a fresh successor task after fixing the cause",
            "",
          ].join("\n"),
        );
      }
    } catch {
      // The original gate failure remains authoritative even if the signal path is not writable.
    }
  }
  process.stderr.write(`HALT ${code}: ${message}\n`);
  process.exit(1);
}

function awaitReview(code, signalName, message) {
  if (durableStateDir) {
    mkdirSync(durableStateDir, { recursive: true });
    const signalPath = path.join(durableStateDir, `AWAIT-FOUNDER-${signalName}.txt`);
    if (!existsSync(signalPath)) {
      writeFileSync(
        signalPath,
        [
          `AWAIT ${code}: ${message}`,
          `created_at_utc: ${new Date().toISOString()}`,
          "resolution: resolve the reviewer condition, remove this signal, then resume the same in-flight lifecycle",
          "",
        ].join("\n"),
      );
    }
  }
  process.stderr.write(`AWAIT ${code}: ${message}\n`);
  process.exit(1);
}

// git resolves pathspec magic from FOUR environment variables before it looks at the pathspec, and
// this gate inherits the environment of the writer it is judging. `GIT_LITERAL_PATHSPECS=1` is the
// sharp one — it disarms the `:(literal)` prefix by taking the prefix itself literally — but all four
// are caller-controlled inputs to a trust decision, so all four are stripped. See SCOPE_PATHSPECS.
//
// This is deliberately the same shape as `trustedReviewEnvironment`: copy, delete the keys the caller
// must not control, hand the copy to the child. One idiom, two lists, because the two lists protect
// different subprocesses — do not merge them into a single "untrusted keys" bag.
const GIT_PATHSPEC_ENVIRONMENT_KEYS = [
  "GIT_LITERAL_PATHSPECS",
  "GIT_GLOB_PATHSPECS",
  "GIT_NOGLOB_PATHSPECS",
  "GIT_ICASE_PATHSPECS",
];

function trustedGitEnvironment() {
  const environment = { ...process.env };
  for (const key of GIT_PATHSPEC_ENVIRONMENT_KEYS) {
    delete environment[key];
  }
  return environment;
}

// Prepended to every git argv rather than added at the one call site that passes scope today. A
// pathspec operand is easy to add to a git call later and impossible to spot as dangerous in review,
// so literalness lives at the choke point all three helpers already funnel through, not in the
// caller's memory. Inert on the pathspec-free subcommands this file runs — measured: rev-parse,
// cat-file, merge-base, rev-list, status and `diff --binary` return byte-identical output with and
// without it. Guarded on the command name because the flag is git's, not every binary's.
function gitAwareArgs(command, args) {
  return command === "git" ? ["--literal-pathspecs", ...args] : args;
}

function run(command, args, cwd) {
  try {
    return execFileSync(command, gitAwareArgs(command, args), {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      maxBuffer: MAX_BUFFER,
      env: trustedGitEnvironment(),
    }).trim();
  } catch (error) {
    const detail = String(error.stderr || error.message || "").trim();
    halt("READINESS_COMMAND_FAILED", `${command} ${args.join(" ")}${detail ? ` — ${detail}` : ""}`);
  }
}

function runRaw(command, args, cwd) {
  try {
    return execFileSync(command, gitAwareArgs(command, args), {
      cwd,
      stdio: ["ignore", "pipe", "pipe"],
      maxBuffer: MAX_BUFFER,
      env: trustedGitEnvironment(),
    });
  } catch (error) {
    const detail = String(error.stderr || error.message || "").trim();
    halt("READINESS_COMMAND_FAILED", `${command} ${args.join(" ")}${detail ? ` — ${detail}` : ""}`);
  }
}

function tryRun(command, args, cwd) {
  return spawnSync(command, gitAwareArgs(command, args), {
    cwd,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    maxBuffer: MAX_BUFFER,
    env: trustedGitEnvironment(),
  });
}

function parseArguments(argv) {
  const mode = argv[2];
  let manifest;
  let acceptance;
  let breakers;
  for (let index = 3; index < argv.length; index += 1) {
    if (argv[index] === "--manifest") {
      manifest = argv[index + 1];
      index += 1;
    } else if (argv[index] === "--acceptance") {
      acceptance = argv[index + 1];
      index += 1;
    } else if (argv[index] === "--breakers") {
      breakers = argv[index + 1];
      index += 1;
    } else {
      halt("READINESS_USAGE", `unknown argument: ${argv[index]}`);
    }
  }
  if (!["register", "ready", "evidence"].includes(mode) || !manifest) {
    halt(
      "READINESS_USAGE",
      "use: autopilot-review-readiness.mjs <register|ready> --manifest <path>"
        + " | evidence --manifest <path> --acceptance <status> --breakers <status>",
    );
  }
  // kit v34 review round 3 finding 3: a non-empty check accepted a typo like "satisfed" and wrote it
  // verbatim -- LEVEL3_EVIDENCE_WRITTEN reported success for a file `ready` would then reject. `ready`
  // only ever passes on the exact strings "satisfied"/"clear" (see its own checks below); there is no
  // legitimate reason for `evidence` to write anything else, so require the exact values up front.
  if (mode === "evidence" && (acceptance !== "satisfied" || breakers !== "clear")) {
    halt(
      "READINESS_USAGE",
      `evidence mode requires exactly --acceptance satisfied --breakers clear (got --acceptance ${acceptance || "<missing>"} --breakers ${breakers || "<missing>"})`,
    );
  }
  return { mode, manifest, acceptance, breakers };
}

function readJson(file, label) {
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch (error) {
    halt("READINESS_JSON_INVALID", `${label} ${file}: ${error.message}`);
  }
}

function requireString(value, label) {
  if (typeof value !== "string" || !value.trim() || /[<>]/.test(value)) {
    halt("CONTRACT_INVALID", `${label} must be a resolved non-placeholder string`);
  }
  return value.trim();
}

function requireStringArray(value, label, { allowEmpty = false } = {}) {
  if (!Array.isArray(value) || (!allowEmpty && value.length === 0)) {
    halt("CONTRACT_INVALID", `${label} must be ${allowEmpty ? "an" : "a non-empty"} array`);
  }
  return value.map((item, index) => requireString(item, `${label}[${index}]`));
}

function requireObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    halt("CONTRACT_INVALID", `${label} must be an object`);
  }
  return value;
}

function requireFullSha(value, label) {
  const sha = requireString(value, label);
  if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(sha) || /^0+$/.test(sha)) {
    halt("CONTRACT_INVALID", `${label} must be a real full commit SHA`);
  }
  return sha;
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function relativeToRepo(repo, file) {
  return path.relative(repo, file).split(path.sep).join("/");
}

function artifactRecord(repo, file) {
  const body = readFileSync(file);
  return {
    path: relativeToRepo(repo, file),
    sha256: sha256(body),
    bytes: body.length,
  };
}

function lastNonEmptyLine(value) {
  const cleaned = String(value || "").replace(
    // eslint-disable-next-line no-control-regex
    /\u001b\[[0-9;]*[A-Za-z]/g,
    "",
  );
  return cleaned.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).at(-1) || "";
}

function trustedReviewEnvironment() {
  const environment = { ...process.env };
  const home = userInfo().homedir;
  environment.HOME = home;
  environment.PATH = [
    path.join(home, ".npm-global", "bin"),
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
  ].join(":");
  for (const key of [
    "AUTOPILOT_CODEX_REAL_BIN",
    "AUTOPILOT_CODEX_REVIEW_MODEL",
    "AUTOPILOT_CODEX_REVIEW_EFFORT",
    "AUTOPILOT_CODEX_REVIEW_TIER",
    "BASH_ENV",
    "ENV",
    "NODE_OPTIONS",
    // The reviewer wrapper runs `git diff <base>...HEAD` of its own. It takes no pathspec today, so
    // this is not a known bypass the way the SCOPE_PATHSPECS one was — it is the same class of input
    // reaching a second subprocess whose output the gate trusts, stripped for the same reason and at
    // the same cost. Nothing legitimate sets these.
    ...GIT_PATHSPEC_ENVIRONMENT_KEYS,
  ]) {
    delete environment[key];
  }
  return environment;
}

const {
  mode,
  manifest: manifestArgument,
  acceptance: acceptanceArgument,
  breakers: breakersArgument,
} = parseArguments(process.argv);
const repo = run("git", ["rev-parse", "--show-toplevel"], process.cwd());
const manifestCandidate = path.resolve(process.cwd(), manifestArgument);
deriveDurableStateDir(repo, manifestCandidate);
if (!existsSync(manifestCandidate)) {
  halt("MANIFEST_MISSING", manifestCandidate);
}
const manifestPath = realpathSync(manifestCandidate);
deriveDurableStateDir(repo, manifestPath);

const manifest = readJson(manifestPath, "manifest");
const manifestHash = sha256(readFileSync(manifestPath));
if (manifest.manifest_schema_version !== "level3-operational-v2") {
  halt("CONTRACT_INVALID", "manifest_schema_version must equal level3-operational-v2");
}
if (manifest.review_gate_version !== VERSION) {
  halt("CONTRACT_INVALID", `review_gate_version must equal ${VERSION}`);
}

const taskId = requireString(manifest.task_id, "task_id");
const feature = requireString(manifest.feature, "feature");
const branch = requireString(manifest.branch, "branch");
const baseRef = requireString(manifest.base_ref, "base_ref");
const baseSha = requireFullSha(manifest.base_sha, "base_sha");
if (!/^[a-z0-9][a-z0-9._-]*$/.test(feature)) {
  halt("CONTRACT_INVALID", "feature must be a filesystem-safe lowercase identifier");
}

const taskSlug = taskId.split(":").at(-1);
if (feature !== taskSlug && !feature.startsWith(`${taskSlug}--`)) {
  halt("CONTRACT_INVALID", "feature must equal <task-slug> or start with <task-slug>--");
}
if (branch !== `feat/${feature}`) {
  halt("CONTRACT_INVALID", `branch must equal feat/${feature}`);
}

const stateDir = path.join(repo, ".autopilot", "state", feature);
if (path.dirname(manifestPath) !== stateDir || path.basename(manifestPath) !== "manifest.json") {
  halt("CONTRACT_INVALID", `manifest must be ${path.join(".autopilot", "state", feature, "manifest.json")}`);
}
durableStateDir = stateDir;
if (mode === "ready") {
  for (const staleTerminal of ["READY.txt", "gate-result.json"]) {
    const stalePath = path.join(stateDir, staleTerminal);
    if (existsSync(stalePath)) {
      unlinkSync(stalePath);
    }
  }
}

// One definition, two callers: `evidence` mode WRITES here, `ready` mode READS here. Both must agree
// on the exact path or a generated file would not be where `ready` looks for it.
function evidenceFilePath() {
  const evidenceRelative = requireString(manifest.readiness_evidence_path, "readiness_evidence_path");
  const expectedEvidenceRelative = path.join(".autopilot", "state", feature, "readiness.json");
  if (evidenceRelative !== expectedEvidenceRelative) {
    halt("CONTRACT_INVALID", `readiness_evidence_path must equal ${expectedEvidenceRelative}`);
  }
  return path.join(repo, evidenceRelative);
}

// kit v34 review round 3 finding 3: `evidence` used to write before this check ran at all, so an
// unregistered or drifted manifest still reported LEVEL3_EVIDENCE_WRITTEN success, only to fail
// `ready` moments later on the exact same manifest. One definition, called from both modes, so
// neither can drift from what `ready` actually requires.
function verifyManifestHashLock() {
  const registeredHashPath = path.join(stateDir, "registered-manifest.sha256");
  if (!existsSync(registeredHashPath) || readFileSync(registeredHashPath, "utf8").trim() !== manifestHash) {
    halt("MANIFEST_DRIFT", "manifest changed after registration; HALT and create a successor task");
  }
}

const risk = requireString(manifest.risk, "risk");
if (!["P1", "P2"].includes(risk)) {
  halt("CONTRACT_INVALID", "only P1/P2 writing slices may register");
}
const autonomyMode = requireString(manifest.autonomy_mode, "autonomy_mode");
if (!["supervised", "proactive_routine"].includes(autonomyMode) || (risk === "P1" && autonomyMode !== "supervised")) {
  halt("CONTRACT_INVALID", "autonomy_mode is invalid for this risk");
}
if (manifest.writer_processes_max !== 1) {
  halt("CONTRACT_INVALID", "writer_processes_max must equal 1");
}

requireStringArray(manifest.context_sources, "context_sources");
requireStringArray(manifest.applicable_skills, "applicable_skills", { allowEmpty: true });
const scope = requireStringArray(manifest.scope, "scope");
requireStringArray(manifest.negative_scope, "negative_scope");
// A Next.js App Router dynamic segment — `[id]`, `[...slug]`, `[[...slug]]` — is a literal on-disk
// directory name and the ONLY way to express a path parameter, so the guard below must admit one.
// What it requires is STRUCTURAL: a bracket may appear only as a whole segment wrapped in one of the
// three dynamic-segment forms, around a non-empty parameter that nests no further bracket. (`/`
// needs no exclusion — this is tested against ONE segment, already split on the separator.)
//
// It deliberately does NOT constrain the parameter to an identifier. It did until 2026-08-27, on the
// argument that `[a-z]` is by shape alone indistinguishable from a segment named "a-z" and so had to
// be refused as a possible glob. SCOPE_PATHSPECS below retired that argument rather than answering
// it: a scope entry no longer reaches git as a glob at all, so `[a-z]` can only mean the literal
// directory `[a-z]` — which either exists, and is then a legitimate path, or does not, and is then an
// ordinary misspelled scope entry, caught loudly by SCOPE_DRIFT the moment the slice commits the file
// it actually meant. After that the identifier rule bought nothing and cost real work: a hyphen is
// legal in a route parameter, so `app/[user-id]/page.tsx` was a real path no author could register a
// slice against, and none of them could rename the route to get past it.
const DYNAMIC_SEGMENT = /^(?:\[\[\.\.\.[^[\]]+\]\]|\[\.\.\.[^[\]]+\]|\[[^[\]]+\])$/;
for (const item of scope) {
  const segments = item.split("/");
  const bracketAbuse = segments.some((s) => /[[\]]/.test(s) && !DYNAMIC_SEGMENT.test(s));
  // Traversal is a `..` SEGMENT, which is also what the old substring test was reaching for; the
  // substring form additionally rejected the `...` inside a catch-all segment, so this is stated
  // per segment. Every real escape (`../x`, `a/../../etc/passwd`, `a/..`) stays rejected.
  if (
    path.isAbsolute(item) ||
    segments.includes("..") ||
    /[*?]/.test(item) ||
    bracketAbuse ||
    item.endsWith("/")
  ) {
    halt("CONTRACT_INVALID", `scope must contain exact worktree-relative file paths: ${item}`);
  }
  const existing = path.join(repo, item);
  if (existsSync(existing) && statSync(existing).isDirectory()) {
    halt("CONTRACT_INVALID", `scope item is a directory, not an exact file: ${item}`);
  }
}
if (new Set(scope).size !== scope.length) {
  halt("CONTRACT_INVALID", "scope contains duplicate paths");
}
// A scope entry is a DECLARATION of one exact path, but git reads a trailing operand as a PATHSPEC,
// which is a glob. Both directions were measured against git 2.46 on 2026-08-27, because the review
// that raised this predicted the wrong one and the wrong one is the scarier-sounding of the two:
//
//   OVER-match — REAL. `app/[user-id]/page.tsx` also matches `app/u/page.tsx`, a file the slice never
//   declared. An unrelated commit touching it on the base branch raises BASE_STALE and kills a
//   legitimate registration. That is not a cosmetic false positive: it is the exact failure class
//   v21 and v25 were each written to close, after it terminated three in-flight lifecycles in one
//   two-day window.
//
//   UNDER-match — DOES NOT OCCUR FROM THE BRACKET GRAMMAR. git compares the whole pathspec string
//   literally before it falls back to wildmatch, so a bracketed pathspec still matches its own
//   literal spelling; a real change to the declared file raises BASE_STALE either way. Against a
//   glob this fix closes a false POSITIVE, and only that. Do not restate it as closing an evasion.
//
//   Under-match DOES occur by a route that has nothing to do with the grammar: the caller's Git
//   environment, below. That is a genuine evasion, it was found by the security round rather than the
//   code rounds, and it is the reason this file no longer trusts a magic prefix. Keep the two apart —
//   they were fixed in the same region for different reasons.
//
// Literalness is imposed by the `--literal-pathspecs` COMMAND OPTION that `run`/`runRaw`/`tryRun`
// prepend to every git argv, NOT by a `:(literal)` magic prefix on the pathspec itself. The prefix
// was this file's first attempt and it is defeated by the caller's own environment: measured on git
// 2.46, `GIT_LITERAL_PATHSPECS=1` makes git read EVERY pathspec as literal text INCLUDING the magic
// prefix, so it hunts for a file spelled `:(literal)app/…`, finds nothing, and `touched` comes back
// empty — BASE_STALE never fires, on a base that really did move under the slice. A writer sets one
// variable and the staleness half of the trust gate stops existing.
//
//   magic prefix, GIT_LITERAL_PATHSPECS=1   -> (empty)                 gate bypassed
//   raw path + --literal-pathspecs, same env -> app/[user-id]/page.tsx  halt still fires
//
// So scope reaches git RAW. Two properties make that safe, and they are different properties:
//   - the command option outranks the environment, which is the whole point of preferring it;
//   - where the environment contradicts it (`GIT_GLOB_PATHSPECS`, `GIT_ICASE_PATHSPECS`) git does not
//     quietly pick a winner, it dies with "global 'literal' pathspec setting is incompatible with all
//     other global pathspec settings" — READINESS_COMMAND_FAILED, a halt. Fail-closed either way,
//     which is why sanitising those variables (see `trustedGitEnvironment`) is a separate belt from
//     this brace: it keeps a hostile environment from turning into a confusing halt, and does not
//     carry the literalness on its own.
//
// EVERY git call that takes scope reads THIS array. Do not spread `scope` into a git argv again: the
// bug is invisible in review precisely because the glob-free case — every scope entry any slice had
// declared until now — behaves identically either way.
const SCOPE_PATHSPECS = [...scope];

const modelPolicy = requireObject(manifest.model_policy, "model_policy");
requireString(modelPolicy.planner, "model_policy.planner");
requireString(modelPolicy.worker, "model_policy.worker");
if (requireString(modelPolicy.independent_reviewer, "model_policy.independent_reviewer") !== REVIEW_TOOL) {
  halt("CONTRACT_INVALID", `model_policy.independent_reviewer must equal ${REVIEW_TOOL}`);
}
requireString(modelPolicy.fallback, "model_policy.fallback");
const permissions = requireObject(manifest.sandbox_and_permissions, "sandbox_and_permissions");
requireString(permissions.network, "sandbox_and_permissions.network");
requireString(permissions.secrets, "sandbox_and_permissions.secrets");
requireString(permissions.external_side_effects, "sandbox_and_permissions.external_side_effects");

const verification = requireObject(manifest.verification, "verification");
requireStringArray(verification.focused, "verification.focused");
requireStringArray(verification.canonical, "verification.canonical");
requireStringArray(verification.e2e, "verification.e2e", { allowEmpty: true });
const codeReview = requireObject(manifest.code_review, "code_review");
if (codeReview.required !== true || requireString(codeReview.tool, "code_review.tool") !== REVIEW_TOOL) {
  halt("CONTRACT_INVALID", `code_review must be required and use ${REVIEW_TOOL}`);
}
const requiredCleanRounds = risk === "P1" ? 2 : 1;
if (!Number.isInteger(codeReview.clean_rounds) || codeReview.clean_rounds < requiredCleanRounds) {
  halt("CONTRACT_INVALID", `code_review.clean_rounds must be at least ${requiredCleanRounds}`);
}
const securityReview = requireObject(manifest.security_review, "security_review");
if (typeof securityReview.required !== "boolean") {
  halt("CONTRACT_INVALID", "security_review.required must be boolean");
}
requireString(securityReview.reason, "security_review.reason");
if (securityReview.required && requireString(securityReview.tool, "security_review.tool") !== REVIEW_TOOL) {
  halt("CONTRACT_INVALID", `security_review.tool must equal ${REVIEW_TOOL}`);
}

const budgets = requireObject(manifest.budgets, "budgets");
if (!Number.isInteger(budgets.wall_time_minutes) || budgets.wall_time_minutes < 1) {
  halt("CONTRACT_INVALID", "budgets.wall_time_minutes must be a positive integer");
}
if (!Number.isInteger(budgets.fix_rounds_max) || budgets.fix_rounds_max < 0 || budgets.fix_rounds_max > 5) {
  halt("CONTRACT_INVALID", "budgets.fix_rounds_max must be an integer from 0 through 5");
}
const stopConditions = requireStringArray(manifest.stop_conditions, "stop_conditions");
for (const required of ["MAX_ROUNDS", "REGION_THRASH", "SCOPE_OR_BASE_DRIFT", "REQUIRED_TOOL_UNAVAILABLE"]) {
  if (!stopConditions.includes(required)) {
    halt("CONTRACT_INVALID", `stop_conditions is missing ${required}`);
  }
}

const currentBranch = run("git", ["branch", "--show-current"], repo);
if (currentBranch !== branch) {
  halt("BRANCH_MISMATCH", `current=${currentBranch || "detached"} expected=${branch}`);
}
run("git", ["cat-file", "-e", `${baseSha}^{commit}`], repo);
// ONE definition of "the pinned base is still usable", called from every site that needs it. There used
// to be two copies of this rule: a pre-flight check here and a second inside liveDiffState(), which is
// the one `ready` actually passes through. v21 fixed only this copy, so `ready` kept halting under the
// old exact-equality rule while the new rule sat unused a hundred lines above it — and the halt message
// was the only clue the two were different. Two copies of a rule are one rule and one future bug.
function assertBaseUsable(currentBaseRefSha) {
  if (currentBaseRefSha === baseSha) return;
  // base_sha does NOT have to equal the tip of baseRef. It must stay an ANCESTOR of it, and nothing in
  // this slice's declared scope may have changed on baseRef since. Exact equality made every concurrent
  // registration terminal the instant anything landed — an unrelated docs commit was enough — so the
  // parallel model this kit documents could never complete: the first slice to merge killed the rest.
  //
  // Division of labour: this gate certifies the DIFF the reviewer read, which stays valid as long as
  // history was not rewritten under it and nobody else touched the files in question. `ap-merge.sh`
  // certifies the MERGE — it performs a real merge, stops on conflict, and verifies the probe on the
  // resulting tree. Exact equality had this gate doing ap-merge's job badly while breaking its own.
  const ancestry = tryRun("git", ["merge-base", "--is-ancestor", baseSha, currentBaseRefSha], repo);
  if (ancestry.status !== 0) {
    halt(
      "BASE_STALE",
      `${baseSha} is no longer an ancestor of ${baseRef}=${currentBaseRefSha}; history was rewritten under this registration`,
    );
  }
  const touched = run(
    "git",
    ["diff", "--name-only", `${baseSha}..${currentBaseRefSha}`, "--", ...SCOPE_PATHSPECS],
    repo,
  );
  if (touched) {
    halt(
      "BASE_STALE",
      `files in this slice's declared scope changed on ${baseRef} since ${baseSha}: ${touched.split("\n").join(", ")}`,
    );
  }
}

const baseRefSha = run("git", ["rev-parse", `${baseRef}^{commit}`], repo);
assertBaseUsable(baseRefSha);

const dependencies = requireStringArray(manifest.depends_on, "depends_on", { allowEmpty: true });
if (!Array.isArray(manifest.dep_checks)) {
  halt("CONTRACT_INVALID", "dep_checks must be an array");
}
if (manifest.dep_checks.length !== dependencies.length) {
  halt("DEPENDENCY_PROOF_INVALID", "every depends_on entry needs exactly one dep_checks entry");
}
for (const [index, rawCheck] of manifest.dep_checks.entries()) {
  const check = requireObject(rawCheck, `dep_checks[${index}]`);
  const dependency = requireString(check.feature, `dep_checks[${index}].feature`);
  if (dependency !== dependencies[index]) {
    halt("DEPENDENCY_PROOF_INVALID", "dep_checks must match depends_on in the same order");
  }
  const dependencyBaseSha = requireFullSha(check.base_sha, `dep_checks[${index}].base_sha`);
  const landedSha = requireFullSha(check.landed_sha, `dep_checks[${index}].landed_sha`);
  const file = requireString(check.file, `dep_checks[${index}].file`);
  const symbol = requireString(check.symbol, `dep_checks[${index}].symbol`);
  if (path.isAbsolute(file) || file.includes("..") || !/^[A-Za-z_][A-Za-z0-9_]{2,}$/.test(symbol)) {
    halt("DEPENDENCY_PROOF_INVALID", `${dependency} needs an exact file and unique identifier symbol`);
  }
  run("git", ["cat-file", "-e", `${dependencyBaseSha}^{commit}`], repo);
  run("git", ["cat-file", "-e", `${landedSha}^{commit}`], repo);
  if (tryRun("git", ["merge-base", "--is-ancestor", dependencyBaseSha, landedSha], repo).status !== 0) {
    halt("DEPENDENCY_NOT_LANDED", `${dependency}: dependency base is not an ancestor of landed_sha`);
  }
  if (tryRun("git", ["merge-base", "--is-ancestor", landedSha, baseSha], repo).status !== 0) {
    halt("DEPENDENCY_NOT_LANDED", `${dependency}: landed_sha is not on the pinned downstream base`);
  }
  const before = tryRun("git", ["show", `${dependencyBaseSha}:${file}`], repo);
  if (before.status === 0 && String(before.stdout).includes(symbol)) {
    halt("DEPENDENCY_PROOF_REUSED", `${dependency}: symbol ${symbol} already existed on its pinned base`);
  }
  const landed = tryRun("git", ["show", `${landedSha}:${file}`], repo);
  const downstream = tryRun("git", ["show", `${baseSha}:${file}`], repo);
  if (
    landed.status !== 0
    || downstream.status !== 0
    || !String(landed.stdout).includes(symbol)
    || !String(downstream.stdout).includes(symbol)
  ) {
    halt("DEPENDENCY_NOT_LANDED", `${dependency}: unique symbol ${symbol} is not present on landed/downstream trees`);
  }
}

const reviewerPath = path.join(repo, REVIEW_TOOL);
if (!existsSync(reviewerPath) || !statSync(reviewerPath).isFile() || (statSync(reviewerPath).mode & 0o111) === 0) {
  halt("REQUIRED_TOOL_UNAVAILABLE", `${REVIEW_TOOL} must exist and be executable on the pinned worktree`);
}

const headSha = run("git", ["rev-parse", "HEAD"], repo);
if (mode === "register") {
  // item 4 of docs/kit-derive-dont-declare-EXECUTE-PROMPT.md (deriving this to an ancestor check, so
  // register would accept HEAD already ahead of baseSha) was ATTEMPTED and DROPPED: kit v34 review
  // round 1 found that register's collision check (autopilot-scope-gate) runs against DECLARED scope
  // regardless of commit timing, so allowing commits before registration lets an agent sink real
  // implementation work before discovering a scope/invariant collision that register-before-commit
  // catches with zero cost. The prompt's own section 1 named this the item to drop first if the slice
  // hit exactly this kind of trust-boundary complexity; it did. HEAD === baseSha stays exact equality.
  if (headSha !== baseSha) {
    halt("BASE_MISMATCH", `worktree HEAD=${headSha} expected=${baseSha}`);
  }
  process.stdout.write(`LEVEL3_REGISTER_VALID task=${taskId} feature=${feature} base=${baseSha}\n`);
  process.exit(0);
}
if (mode === "evidence") {
  // derive2 (kit v34, docs/kit-derive-dont-declare-EXECUTE-PROMPT.md section 1 item 2): task_id,
  // feature, base_sha and head_sha are read from the SAME manifest/live-git-state `register`/`ready`
  // already trust -- never re-typed by the caller. Only the two judgment calls git cannot make
  // (acceptance/breakers) come from the caller. `ready`'s validation of the resulting file (identity
  // match, unknown-key whitelist, freshness) is unchanged; this only replaces hand-typing with a
  // mechanical writer that cannot mistype or malform what it writes.
  // kit v34 review round 3 finding 3: verify the hash-lock BEFORE writing, not after -- otherwise an
  // unregistered/drifted manifest still reports LEVEL3_EVIDENCE_WRITTEN success for a file `ready`
  // will reject moments later on the exact same manifest.
  verifyManifestHashLock();
  writeFileSync(
    evidenceFilePath(),
    `${JSON.stringify({
      evidence_schema_version: VERSION,
      task_id: taskId,
      feature,
      base_sha: baseSha,
      head_sha: headSha,
      acceptance: { status: acceptanceArgument },
      breakers: { status: breakersArgument },
    }, null, 2)}\n`,
  );
  process.stdout.write(`LEVEL3_EVIDENCE_WRITTEN feature=${feature} head=${headSha}\n`);
  process.exit(0);
}

verifyManifestHashLock();
function liveDiffState() {
  const liveHead = run("git", ["rev-parse", "HEAD"], repo);
  const liveBaseRefSha = run("git", ["rev-parse", `${baseRef}^{commit}`], repo);
  // Same rule as pre-flight, same function — this is the call site `ready` actually passes through.
  assertBaseUsable(liveBaseRefSha);
  if (run("git", ["merge-base", baseSha, liveHead], repo) !== baseSha) {
    halt("BASE_DRIFT", "pinned base is not an ancestor of HEAD");
  }
  // THE DIFF WINDOW IS MEASURED FROM THE LIVE BASE REF, NOT FROM THE PINNED base_sha.
  //
  // base_sha was doing two jobs. One is proving the review rests on a legitimate base — that is what
  // assertBaseUsable() above now checks, via ancestry plus untouched scope. The other is marking where
  // this slice's own work begins, and for that the pinned SHA is simply wrong once anything lands on the
  // base branch: a slice that rebases to pick up a fix finds every intervening commit inside
  // `base_sha...HEAD`, and SCOPE_DRIFT then reports files it never touched. Measured 2026-07-31: a slice
  // rebased through three sanctioned kit syncs and halted on four kit files, with no legal way out —
  // re-registering is refused while in-flight (FEATURE_ALREADY_ACTIVE) and editing the runtime manifest
  // breaks its hash lock (MANIFEST_DRIFT). The registration was correct; the measurement was not.
  //
  // Using the live tip is right in both states. Rebased: merge-base(baseRef, HEAD) is the tip, so the
  // window is exactly this slice's commits. Not rebased: merge-base is the old divergence point, which
  // is also exactly this slice's commits. The pinned SHA is right in neither case once the branch moves.
  const diffBase = liveBaseRefSha;
  const commitCount = Number(run("git", ["rev-list", "--count", `${diffBase}..${liveHead}`], repo));
  if (!Number.isInteger(commitCount) || commitCount < 1) {
    halt("EMPTY_DIFF", "HEAD has no commit beyond the pinned base");
  }
  const files = run("git", ["diff", "--name-only", "--no-renames", `${diffBase}...${liveHead}`], repo)
    .split("\n")
    .filter(Boolean);
  if (files.length === 0) {
    halt("EMPTY_DIFF", "no tracked files differ from the pinned base");
  }
  // kit v34 review round 2 finding 1: assertBaseUsable() above still only protects DECLARED scope --
  // with SCOPE_DRIFT gone, a file this diff ACTUALLY touches but never declared is invisible to it. If
  // the base branch independently changed that same undeclared file since baseSha, this diff would
  // certify over a real conflict. Layered on top of assertBaseUsable(), not a replacement for it --
  // `files` is guaranteed non-empty here (EMPTY_DIFF already halted above), so spreading it as a
  // pathspec is safe (an empty array would mean "no restriction" to git, not "match nothing"; see
  // SCOPE_PATHSPECS's own comment for why that distinction matters).
  const actualFilesTouchedSinceBase = run(
    "git",
    ["diff", "--name-only", `${baseSha}..${diffBase}`, "--", ...files],
    repo,
  );
  if (actualFilesTouchedSinceBase) {
    halt(
      "BASE_STALE",
      `files this diff actually touches changed on ${baseRef} since ${baseSha}: ${actualFilesTouchedSinceBase.split("\n").join(", ")}`,
    );
  }
  // derive1 (kit v34, docs/kit-derive-dont-declare-EXECUTE-PROMPT.md section 1 item 1): scope used to
  // be VALIDATED against this diff -- any file outside the declared `scope` array halted SCOPE_DRIFT.
  // git already computes `files` above; there is nothing left to declare correctly, only something to
  // mistype. The certified file list IS this diff (already what diff_files below records) -- declared
  // `scope` keeps doing its other job untouched: the register-time staleness pre-check in
  // assertBaseUsable() above, and human/reviewer-readable intent.
  const selfCertifying = files.filter((file) => TRUSTED_GATE_FILES.has(file));
  if (selfCertifying.length) {
    halt(
      "SELF_CERTIFYING_GATE_CHANGE",
      `a normal feature cannot certify changes to its own trust gate: ${selfCertifying.join(", ")}`,
    );
  }
  const dirty = run("git", ["status", "--porcelain", "--untracked-files=all"], repo)
    .split("\n")
    .filter((line) => line && !line.slice(3).startsWith(".autopilot/"));
  if (dirty.length) {
    halt("WORKTREE_DIRTY", dirty.join(" | "));
  }
  const diff = runRaw("git", ["diff", "--binary", `${diffBase}...${liveHead}`], repo);
  return { headSha: liveHead, diffBase, files, diffHash: sha256(diff) };
}

const initialState = liveDiffState();
const evidencePath = evidenceFilePath();
const evidence = readJson(evidencePath, "readiness evidence");
// Fail closed on any key the whitelist does not name — at the top level AND inside acceptance/breakers.
// A readiness.json is a precondition INPUT (identity + the writer's attestation that its work is done
// and no breaker is active), never a place to self-assert verification/review state: the gate reruns
// verification and the pinned review itself and writes the real verdict to gate-result.json. Without
// this the presence/value checks below accepted extra fields silently, leaving the permission
// classifier as the only thing catching a nested self-assertion (the 2026-08-11 true positive).
// Checked BEFORE identity so "you added a field" is never masked by "your head is stale".
const unknownEvidenceKeys = findUnknownEvidenceKeys(evidence);
if (unknownEvidenceKeys.length) {
  halt(
    "EVIDENCE_UNKNOWN_KEY",
    `readiness evidence carries key(s) outside the whitelist: ${describeUnknownEvidenceKeys(unknownEvidenceKeys)} -- `
      + "a readiness.json records only identity, acceptance.status and breakers.status; remove the "
      + "extra field(s) rather than self-asserting verification or review state here",
  );
}
if (
  evidence.evidence_schema_version !== VERSION
  || evidence.task_id !== taskId
  || evidence.feature !== feature
  || evidence.base_sha !== baseSha
  || evidence.head_sha !== initialState.headSha
) {
  halt("EVIDENCE_STALE", "readiness evidence identity/base/head does not match the live slice");
}
if (requireObject(evidence.acceptance, "evidence.acceptance").status !== "satisfied") {
  halt("ACCEPTANCE_NOT_SATISFIED", "evidence.acceptance.status must be satisfied");
}
if (requireObject(evidence.breakers, "evidence.breakers").status !== "clear") {
  halt("BREAKER_ACTIVE", "readiness evidence reports an active breaker");
}

const counterPath = path.join(stateDir, "fix-round-count.txt");
if (!existsSync(counterPath)) {
  halt("BREAKER_EVIDENCE_MISSING", counterPath);
}
const fixRounds = Number(readFileSync(counterPath, "utf8").trim());
if (!Number.isInteger(fixRounds) || fixRounds < 0 || fixRounds > budgets.fix_rounds_max) {
  halt("MAX_ROUNDS", `fix-round-count=${fixRounds}, max=${budgets.fix_rounds_max}`);
}
const regionsPath = path.join(stateDir, "regions.log");
if (!existsSync(regionsPath)) {
  halt("BREAKER_EVIDENCE_MISSING", regionsPath);
}
const regionEntries = readFileSync(regionsPath, "utf8")
  .split(/\r?\n/)
  .map((line) => line.match(/^round-(\d+)\s+(.+)$/))
  .filter(Boolean)
  .map((match) => ({ round: Number(match[1]), region: match[2].trim() }));
const roundsByRegion = new Map();
for (const { round, region } of regionEntries) {
  if (!roundsByRegion.has(region)) roundsByRegion.set(region, new Set());
  roundsByRegion.get(region).add(round);
}
for (const [region, roundSet] of roundsByRegion) {
  const rounds = [...roundSet].sort((a, b) => a - b);
  for (let index = 2; index < rounds.length; index += 1) {
    const [a, b, c] = rounds.slice(index - 2, index + 1);
    if (b === a + 1 && c === b + 1) {
      halt("REGION_THRASH", `${region} repeated in rounds ${a}-${c}`);
    }
  }
}
const blockers = ["HALT-", "AWAIT-FOUNDER-"].flatMap((prefix) =>
  readdirSync(stateDir).filter((name) => name.startsWith(prefix)));
if (blockers.length) {
  halt("TERMINAL_CONFLICT", `remove/resume the active signal first: ${blockers.join(", ")}`);
}
const pendingFindingPath = path.join(stateDir, "pending-review-finding.json");
if (existsSync(pendingFindingPath)) {
  const pending = readJson(pendingFindingPath, "pending review finding");
  if (pending.head_sha === initialState.headSha || fixRounds <= pending.fix_round_count) {
    halt(
      "UNRESOLVED_REVIEW_FINDING",
      `review finding at ${pending.head_sha} needs a committed fix and fix-round increment before retry`,
    );
  }
}

mkdirSync(stateDir, { recursive: true });
const attemptCounterPath = path.join(stateDir, "gate-attempt-count.txt");
const priorAttempts = existsSync(attemptCounterPath)
  ? Number(readFileSync(attemptCounterPath, "utf8").trim())
  : 0;
const attempt = Number.isInteger(priorAttempts) && priorAttempts >= 0 ? priorAttempts + 1 : 1;
writeFileSync(attemptCounterPath, `${attempt}\n`);
const attemptLabel = String(attempt).padStart(2, "0");
const deadline = Date.now() + budgets.wall_time_minutes * 60_000;
const generatedArtifacts = [];

function remainingMs() {
  const remaining = deadline - Date.now();
  if (remaining <= 0) {
    halt("GATE_TIMEOUT", `wall-time budget of ${budgets.wall_time_minutes} minutes exhausted`);
  }
  return remaining;
}

function isTimeout(result) {
  return result?.error?.code === "ETIMEDOUT";
}

function writeProcessLog(file, metadata, result) {
  const error = result.error ? `${result.error.name}: ${result.error.message}` : "";
  writeFileSync(
    file,
    [
      ...Object.entries(metadata).map(([key, value]) => `${key}: ${value}`),
      `exit_status: ${result.status ?? "none"}`,
      `signal: ${result.signal || "none"}`,
      `error: ${error || "none"}`,
      "",
      "----- stdout -----",
      String(result.stdout || ""),
      "----- stderr -----",
      String(result.stderr || ""),
    ].join("\n"),
  );
  generatedArtifacts.push(file);
}

function runVerificationGroup(group, commands) {
  for (const [index, command] of commands.entries()) {
    const file = path.join(
      stateDir,
      `gate-attempt-${attemptLabel}-verify-${group}-${String(index + 1).padStart(2, "0")}.txt`,
    );
    // derive3 (kit v34, docs/kit-derive-dont-declare-EXECUTE-PROMPT.md section 1 item 3): a command
    // proving negative_scope compliance (e.g. "nothing under forbidden/ changed since I began") had no
    // live base to reference and so had to hardcode one -- exactly the base_sha diff-window trap
    // v25/v26 already closed for the reviewer's own --base flag (see liveDiffState() above). Both
    // values are exported so a command can derive whichever job it needs: the live diff-window base
    // (robust to a legitimate rebase, same value the gate itself certifies against) and the frozen
    // registration pin (legitimacy). Spread process.env first -- this must stay additive, never a
    // narrower replacement of what a verification command already inherits.
    const result = spawnSync("/bin/bash", ["-lc", command], {
      cwd: repo,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      timeout: remainingMs(),
      maxBuffer: MAX_BUFFER,
      env: {
        ...process.env,
        AUTOPILOT_BASE_SHA: baseSha,
        AUTOPILOT_DIFF_BASE_SHA: initialState.diffBase,
      },
    });
    writeProcessLog(file, {
      kind: "verification",
      group,
      command,
      base_sha: baseSha,
      head_sha: initialState.headSha,
    }, result);
    if (isTimeout(result)) {
      halt("GATE_TIMEOUT", `${group}[${index}] exceeded the remaining wall-time budget; inspect ${relativeToRepo(repo, file)}`);
    }
    if (result.error || result.status !== 0) {
      halt("VERIFICATION_FAILED", `${group}[${index}] failed; inspect ${relativeToRepo(repo, file)}`);
    }
  }
}

// The reviewer runs in a throwaway detached worktree at HEAD, created just before the review rounds
// (see below). A clean checkout has no gitignored .autopilot/state, so prior-round findings and the
// pending-review-finding.json pointer are unreachable by the reviewer. Fail closed if it is missing.
let reviewWorktree = null;

function runReview(kind, round, cleanMarker, findingsMarker, prompt) {
  if (!reviewWorktree) {
    halt("REVIEW_WORKTREE_UNAVAILABLE", "internal: isolated review worktree not initialised before runReview");
  }
  const connectorPattern = /rmcp|mcp|transport::worker|TokenRefreshFailed/i;
  for (let invocation = 1; invocation <= 2; invocation += 1) {
    const retrySuffix = invocation === 1 ? "" : `-retry-${String(invocation - 1).padStart(2, "0")}`;
    const file = path.join(
      stateDir,
      `gate-attempt-${attemptLabel}-${kind}-round-${String(round).padStart(2, "0")}${retrySuffix}.txt`,
    );
    const result = spawnSync(reviewerPath, ["review", "--base", initialState.diffBase, prompt], {
      cwd: reviewWorktree.path,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      timeout: remainingMs(),
      maxBuffer: MAX_BUFFER,
      env: trustedReviewEnvironment(),
    });
    writeProcessLog(file, {
      kind,
      round,
      invocation,
      tool: REVIEW_TOOL,
      base_sha: baseSha,
      head_sha: initialState.headSha,
      diff_sha256: initialState.diffHash,
    }, result);

    if (isTimeout(result)) {
      halt("GATE_TIMEOUT", `${kind} round ${round} exceeded the remaining wall-time budget; inspect ${relativeToRepo(repo, file)}`);
    }

    const rawStdout = String(result.stdout || "");
    const rawCombined = `${rawStdout}\n${String(result.stderr || "")}`;
    const stdoutWithoutConnectorNoise = rawStdout
      .split(/\r?\n/)
      .filter((line) => !connectorPattern.test(line))
      .join("\n");
    const combinedWithoutConnectorNoise = rawCombined
      .split(/\r?\n/)
      .filter((line) => !connectorPattern.test(line))
      .join("\n")
      .trim();
    const verdict = lastNonEmptyLine(stdoutWithoutConnectorNoise);

    // Verdict-first: connector shutdown noise or a nonzero wrapper exit cannot invalidate a real
    // completed model verdict.
    if (verdict === findingsMarker) {
      writeFileSync(
        pendingFindingPath,
        `${JSON.stringify({
          schema_version: "level3-pending-review-finding-v1",
          kind,
          round,
          head_sha: initialState.headSha,
          diff_sha256: initialState.diffHash,
          fix_round_count: fixRounds,
          artifact: relativeToRepo(repo, file),
        }, null, 2)}\n`,
      );
      halt("REVIEW_FINDINGS", `${kind} round ${round} returned findings; inspect ${relativeToRepo(repo, file)}`);
    }
    if (verdict === cleanMarker) return;

    if (/usage limit|Review was interrupted|try again at/i.test(rawCombined)) {
      awaitReview("CODEX_QUOTA", "CODEX-QUOTA", `review quota/interruption in ${relativeToRepo(repo, file)}; wait for reset, then resume this lifecycle`);
    }
    if (/(^|\D)401(\D|$)|token_invalidated|invalid_grant|log in again/i.test(combinedWithoutConnectorNoise)) {
      awaitReview("CODEX_AUTH_REQUIRED", "CODEX-AUTH", `reviewer authentication failed in ${relativeToRepo(repo, file)}; re-authenticate the pinned reviewer, then resume`);
    }

    const connectorOnly = connectorPattern.test(rawCombined) && !combinedWithoutConnectorNoise;
    if (connectorOnly && invocation === 1) {
      continue;
    }
    if (connectorOnly) {
      awaitReview("CODEX_CONNECTOR_PERSISTENT", "CODEX-CONNECTOR", `connector-only reviewer failure repeated in ${relativeToRepo(repo, file)}; repair/disable connectors, then resume`);
    }
    if (result.error || result.status !== 0) {
      halt("REVIEW_UNAVAILABLE", `${kind} round ${round} failed without a valid verdict; inspect ${relativeToRepo(repo, file)}`);
    }
    halt("REVIEW_VERDICT_INVALID", `${kind} round ${round} lacks exact clean marker; inspect ${relativeToRepo(repo, file)}`);
  }
}

runVerificationGroup("focused", verification.focused);
runVerificationGroup("canonical", verification.canonical);
runVerificationGroup("e2e", verification.e2e);

// Isolate the reviewer from prior-round state: run every review round in a fresh detached worktree at
// the reviewed HEAD. Fail closed — if isolation cannot be established, do NOT review in the feature
// worktree (that is exactly the contamination path this closes).
try {
  reviewWorktree = createEphemeralReviewWorktree(repo, initialState.headSha);
} catch (error) {
  halt("REVIEW_WORKTREE_UNAVAILABLE", `could not create the isolated review worktree: ${String((error && error.message) || error)}`);
}

// kit v34 review round 3 finding 1: risk/security_review.required are derived only from the
// manifest as authored, and nothing has ever mechanically re-validated them against what the diff
// actually touches (true before this version too -- SCOPE_DRIFT only ever checked declared-vs-diff
// file identity, never file identity against declared risk). Removing the requirement that files be
// pre-declared (derive1) makes that pre-existing gap less visible: an undeclared file no longer even
// shows up in the manifest for a human to notice. Building automatic risk/security reclassification
// is a real, separate feature requiring owner design authority -- see level3-workflow.md's own
// documented gap #1 ("the reviewer receives no scope") and docs/kit-design-debt.md's entry on this.
// Cheap mitigation landed here instead: tell the reviewer explicitly which files were not declared,
// so the one review round every slice always gets is pointed at exactly the files this gap concerns.
const outOfDeclaredScope = initialState.files.filter((file) => !scope.includes(file));
const scopeNote = outOfDeclaredScope.length
  ? [
      `${outOfDeclaredScope.length} of ${initialState.files.length} changed file(s) were NOT in the manifest's declared scope: ${outOfDeclaredScope.join(", ")}.`,
      `Declared risk is ${risk}, security_review.required is ${securityReview.required}.`,
      "Scrutinize the undeclared files specifically: if any touches auth, money, secrets, permissions or external input in a way the declared risk/security posture does not cover, that is an actionable finding regardless of scope.",
    ].join("\n")
  : null;

const codePrompt = [
  `Review the exact non-empty diff against base ${initialState.diffBase} for correctness, regressions, tests and scope.`,
  "Report every actionable finding before the verdict.",
  "The LAST non-empty line must be exactly one of:",
  "AUTOPILOT_CODE_VERDICT: CLEAN",
  "AUTOPILOT_CODE_VERDICT: FINDINGS",
  "Use CLEAN only when there are zero actionable findings.",
  ...(scopeNote ? ["", scopeNote] : []),
].join("\n");
for (let round = 1; round <= codeReview.clean_rounds; round += 1) {
  runReview(
    "code-review",
    round,
    "AUTOPILOT_CODE_VERDICT: CLEAN",
    "AUTOPILOT_CODE_VERDICT: FINDINGS",
    codePrompt,
  );
}

if (securityReview.required) {
  const securityPrompt = [
    `Security-review the exact non-empty diff against base ${initialState.diffBase}.`,
    "Check trust boundaries, auth, secrets, permissions, external input, money and deployment effects.",
    "Report every actionable finding before the verdict.",
    "The LAST non-empty line must be exactly one of:",
    "AUTOPILOT_SECURITY_VERDICT: CLEAN",
    "AUTOPILOT_SECURITY_VERDICT: FINDINGS",
    "Use CLEAN only when there are zero actionable security findings.",
    ...(scopeNote ? ["", scopeNote] : []),
  ].join("\n");
  runReview(
    "security-review",
    1,
    "AUTOPILOT_SECURITY_VERDICT: CLEAN",
    "AUTOPILOT_SECURITY_VERDICT: FINDINGS",
    securityPrompt,
  );
}

// Reviews are done; drop the throwaway worktree now (the process-exit handler remains only as a leak net).
reviewWorktree.cleanup();

const finalState = liveDiffState();
if (
  finalState.headSha !== initialState.headSha
  || finalState.diffHash !== initialState.diffHash
  || finalState.files.join("\n") !== initialState.files.join("\n")
) {
  halt("GATE_INPUT_DRIFT", "HEAD or diff changed while verification/review was running");
}
if (existsSync(pendingFindingPath)) {
  unlinkSync(pendingFindingPath);
}

// kit v34 review round 4 finding 2 (the same objection rounds 1-3 each raised from a different
// consumer's angle): removing SCOPE_DRIFT's halt must not turn "the diff exceeded declared scope"
// into silent, unrecorded prose. GATE_INPUT_DRIFT just above proves finalState.files here is
// byte-identical to the outOfDeclaredScope computed from initialState.files earlier -- reused, not
// recomputed. Every consumer of gate-result.json (ap-finish, a human reading the artifact, a future
// audit) can now see EXACTLY what was and was not declared, structurally, without re-deriving it.
const gateResultPath = path.join(stateDir, "gate-result.json");
writeFileSync(
  gateResultPath,
  `${JSON.stringify({
    gate_schema_version: VERSION,
    task_id: taskId,
    feature,
    base_ref: baseRef,
    base_sha: baseSha,
    diff_base_sha: finalState.diffBase,
    head_sha: finalState.headSha,
    diff_sha256: finalState.diffHash,
    diff_files: finalState.files,
    declared_scope: scope,
    scope_expanded: outOfDeclaredScope.length > 0,
    scope_expanded_files: outOfDeclaredScope,
    manifest_sha256: manifestHash,
    attempt,
    generated_artifacts: generatedArtifacts.map((file) => artifactRecord(repo, file)),
    result: "pass",
  }, null, 2)}\n`,
);

// kit v34, founder review of item 1 (2026-08-31): scope_expanded in gate-result.json answers "is the
// fact recorded", not "does it reach the founder at merge time" -- gate-result.json lives under
// .autopilot/state/, which is gitignored (confirmed: `git check-ignore` matches it, and it never
// appears in `git log`/`git show` for the commits that carry the actual expansion). A founder reading
// a PR diff on GitHub would see the expanded files as ordinary changed files and nothing else. This
// kit has no pre-merge CI gate to enforce disclosure mechanically (no CI in this repo at all), so the
// achievable fix is making the fact impossible to miss at the one moment the kit still controls:
// `ready`'s own terminal output, printed loudly enough that copying it verbatim into a PR description
// is the path of least resistance, not an extra step someone has to remember.
if (outOfDeclaredScope.length) {
  process.stdout.write(
    [
      "",
      "################################################################################",
      "# SCOPE EXPANDED BEYOND DECLARATION -- paste this block into the PR description #",
      "################################################################################",
      `declared scope (${scope.length}): ${scope.join(", ")}`,
      `also touched, never declared (${outOfDeclaredScope.length}): ${outOfDeclaredScope.join(", ")}`,
      "This diff was certified as-is (kit v34: scope is no longer a fail-closed ceiling). The files",
      "above were NOT in this slice's declared scope and were not classified for risk/security tier.",
      "################################################################################",
      "",
    ].join("\n"),
  );
}

process.stdout.write(
  `LEVEL3_READINESS_PASS task=${taskId} feature=${feature} base=${baseSha} head=${finalState.headSha} files=${finalState.files.length}\n`,
);
