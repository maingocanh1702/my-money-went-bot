#!/usr/bin/env node
// Isolate the pinned reviewer from prior-round review state.
//
// WHY THIS EXISTS (measured 2026-08-13, docs/decisions/analysis/codex-reviewer-determinism-2026-08-13/).
// The readiness gate used to invoke the read-only reviewer with cwd = the FEATURE worktree, which
// contains .autopilot/state/<feature>/ — the pending-review-finding.json pointer and every prior
// gate-attempt artifact. A read-only reviewer that runs inside that tree can read a previous round's
// findings and re-emit them as if fresh. Arm C of the measurement confirmed it: with the pointer
// present, the reviewer followed it, read the prior artifact, and copied a plant-only figure
// ("DB 416/416" — absent from the reviewed tree and diff) into its verdict.
//
// THE FIX (owner-ruled mechanism): run the reviewer in a FRESH detached worktree at the reviewed
// HEAD. A clean checkout never materialises gitignored paths, so .autopilot/state (and node_modules,
// etc.) are absent BY CONSTRUCTION — there is no permission state to get wrong and no path where a
// future change quietly re-exposes the pointer. The gate keeps reading/writing canonical state in the
// feature worktree; only the reviewer's cwd moves here. The ephemeral worktree shares the object DB,
// so `git diff <base>...HEAD` and live-source inspection resolve identically to the feature worktree
// (whose tracked tree equals HEAD — the gate rejects a dirty tree before review).

import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";

/**
 * Create a throwaway detached worktree at `headSha` for the reviewer to run inside.
 * Returns `{ path, cleanup }`. `cleanup()` is idempotent and also runs on process exit as a
 * leak net (the gate's halt() calls process.exit, which bypasses try/finally).
 * Throws if the worktree cannot be created — callers MUST fail closed, never fall back to the
 * feature worktree, or the isolation is silently lost.
 */
export function createEphemeralReviewWorktree(repo, headSha) {
  const tempRoot = mkdtempSync(path.join(tmpdir(), "ap-review-wt-"));
  const worktreePath = path.join(tempRoot, "review");
  // Detached at the exact reviewed HEAD; --detach so no branch ref is created or moved.
  // Transactional: mkdtempSync already created tempRoot, so if `git worktree add` throws we must
  // remove it (and any partial worktree metadata) before rethrowing — a failed setup must leak
  // nothing, and the caller then fails closed (REVIEW_WORKTREE_UNAVAILABLE).
  try {
    execFileSync("git", ["-C", repo, "worktree", "add", "--detach", worktreePath, headSha], {
      stdio: ["ignore", "ignore", "pipe"],
    });
  } catch (error) {
    try {
      execFileSync("git", ["-C", repo, "worktree", "remove", "--force", worktreePath], { stdio: "ignore" });
    } catch {
      // add failed before registering a worktree; nothing to remove
    }
    try {
      rmSync(tempRoot, { recursive: true, force: true });
    } catch {
      // best effort
    }
    throw error;
  }

  let removed = false;
  const cleanup = () => {
    if (removed) return;
    removed = true;
    // Remove only THIS worktree by exact path. Never `git worktree prune` — a parked orphan worktree
    // elsewhere in the repo must survive.
    try {
      execFileSync("git", ["-C", repo, "worktree", "remove", "--force", worktreePath], { stdio: "ignore" });
    } catch {
      // best effort — the rm below still reclaims disk; a stale registry entry is harmless here.
    }
    try {
      rmSync(tempRoot, { recursive: true, force: true });
    } catch {
      // best effort
    }
  };
  process.on("exit", cleanup);
  return { path: worktreePath, cleanup };
}
