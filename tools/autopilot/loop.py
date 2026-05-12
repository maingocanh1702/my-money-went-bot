"""Main orchestration — drives Phase A → E for one feature.

Phases:
- A (CODEGEN): claude_codegen.run_codegen → commits exist
- B (VERIFIED): verify.run_all green
- C (REVIEWING): codex.run_review → categorize → claude_codegen.run_fix → loop
- D (READY): pre-merge gates ready
- E (MERGED): merge.attempt_merge

Resume support: state.json checkpoint after each phase transition; resume
detects current phase and continues from there.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from . import (
    circuit_breaker,
    claude_codegen,
    codex,
    git_ops,
    merge,
    spec_lint,
    state,
    tracker,
    verify,
)
from .config import Config
from .state import FeatureState


@dataclass
class RunOutcome:
    feature_id: str
    final_phase: str
    halted: bool
    halt_reason: str | None
    rounds: int
    merge_sha: str | None
    summary: str


def run(
    cfg: Config,
    feature_id: str,
    *,
    resume: bool = False,
    auto_merge: bool = False,
) -> RunOutcome:
    """Execute the A→E pipeline for one feature.

    If ``resume=True`` and a state file exists, continue from the recorded phase.
    Otherwise start fresh from preflight.

    ``auto_merge`` (default False per Blocker #5 / plan v0.1.6): when False the
    loop stops at READY and writes a manual-merge report; Phase E is never
    invoked. When True (CLI opt-in via ``--auto-merge``) the loop proceeds to
    Phase E and calls ``merge.attempt_merge``.
    """
    # Lint spec FIRST — fail loud before any code is touched.
    lint = spec_lint.lint(cfg, feature_id)
    print(lint.render())
    if not lint.ok:
        return RunOutcome(
            feature_id=feature_id,
            final_phase="LINT_FAIL",
            halted=True,
            halt_reason="spec lint failed (close gaps then re-run)",
            rounds=0,
            merge_sha=None,
            summary=lint.render(),
        )

    existing = state.load(cfg, feature_id)
    if resume and existing is not None:
        feature_state = existing
        if feature_state.phase == "HALTED":
            if feature_state.last_active_phase is None:
                # State predates v0.2.1 — no record of which phase was
                # interrupted. Founder must edit state.json manually.
                return _halt(
                    cfg,
                    feature_state,
                    "RESUME_AMBIGUOUS",
                    "state.phase=HALTED but last_active_phase is unset "
                    "(state file predates v0.2.1). Edit state.json: set "
                    "phase to the re-entry phase (VERIFIED for Phase C), "
                    "current_round=0, consecutive_clean_rounds=0, "
                    "halt_reason=null, halt_artifact_path=null, then "
                    "re-run resume.",
                )
            print(
                f"Resuming {feature_id} from HALTED — re-entering at "
                f"{feature_state.last_active_phase}",
            )
            feature_state.phase = feature_state.last_active_phase
            feature_state.halt_reason = None
            feature_state.halt_artifact_path = None
            # Re-entering Phase C: reset round counters so the (now-fixed)
            # parser gets a clean cycle rather than skipping based on stale
            # round count.
            if feature_state.phase in ("VERIFIED", "REVIEWING"):
                feature_state.current_round = 0
                feature_state.consecutive_clean_rounds = 0
            state.save(cfg, feature_state)
            # Codex v0.2.1 r4 P2: _halt set tracker to HALTED on the way
            # down; restoration must propagate to tracker too. Without this,
            # any operational dashboard or follow-up automation keying off
            # tracker state stays stale at HALTED. Most visible when
            # last_active_phase=READY — Phase D branch never calls
            # tracker.update_status itself before returning.
            tracker.update_status(cfg, feature_id, feature_state.phase)
        else:
            print(f"Resuming {feature_id} from phase {feature_state.phase}")
        # v0.2.2: ensure the git checkout matches feature_state.branch
        # before re-entering active work. Without this, a founder who
        # runs ``autopilot resume`` from ``main`` would have Phase C run
        # codex review against an empty diff (observed on F07 i18n fix
        # session 4). Only run sync for phases where the feature branch
        # is needed for the next step:
        #   - CODEGEN: Phase B verify runs subprocess checks against the
        #     working tree — wrong branch invalidates the result.
        #   - VERIFIED / REVIEWING: Phase C codex review diffs base..branch
        #     and needs the working tree to match.
        # Skip:
        #   - INIT: Phase A creates the branch; pre-create sync would HALT
        #     BRANCH_MISSING and block crash recovery.
        #   - READY: Phase D writes ready-report via ref-based git_ops
        #     (commit_log / diff_stat against the branch ref directly).
        #     A founder resuming READY just to inspect / regenerate the
        #     report should not be forced to have the branch present.
        #   - MERGED: post-merge the branch is typically deleted.
        if feature_state.phase in ("CODEGEN", "VERIFIED", "REVIEWING"):
            sync_outcome = _sync_branch_to_state(cfg, feature_state)
            if sync_outcome is not None:
                return sync_outcome
    else:
        if existing is not None and existing.phase not in ("MERGED",):
            print(
                f"WARN: state file exists at phase {existing.phase!r}; "
                "starting fresh will overwrite. Use --resume to continue.",
            )
        assert lint.fe_path is not None and lint.be_path is not None  # checked in lint
        branch = _derive_branch(feature_id, lint.fe_path)
        feature_state = FeatureState(
            feature_id=feature_id,
            branch=branch,
            base_branch=cfg.base_branch,
            fe_spec=str(lint.fe_path),
            be_spec=str(lint.be_path),
            started_at=_dt.datetime.now(_dt.UTC).isoformat(),
            initial_head_sha=git_ops.head_sha(cfg),
        )
        state.save(cfg, feature_state)

    # --- Phase A: CODEGEN ---
    if feature_state.phase in ("INIT",):
        if not git_ops.branch_exists(cfg, feature_state.branch):
            git_ops.create_branch(cfg, feature_state.branch)
        else:
            git_ops.checkout(cfg, feature_state.branch)
        result = claude_codegen.run_codegen(
            cfg,
            feature_id=feature_id,
            branch=feature_state.branch,
            fe_spec=(
                cfg.repo_root / feature_state.fe_spec
                if not feature_state.fe_spec.startswith("/")
                else _path(feature_state.fe_spec)
            ),
            be_spec=_path(feature_state.be_spec),
        )
        if not result.success:
            return _halt(
                cfg,
                feature_state,
                "CODEGEN_FAILED",
                f"return_code={result.return_code} commits_added={result.commits_added}",
            )
        state.transition(feature_state, "CODEGEN")
        state.save(cfg, feature_state)
        tracker.update_status(cfg, feature_id, "CODEGEN")

    # --- Phase B: VERIFIED ---
    if feature_state.phase in ("CODEGEN",):
        v = verify.run_all(cfg)
        print(v.render())
        if not v.ok:
            return _halt(
                cfg,
                feature_state,
                "VERIFY_FAIL",
                f"failed steps: {[s.name for s in v.failed_steps]}",
            )
        state.transition(feature_state, "VERIFIED")
        state.save(cfg, feature_state)
        tracker.update_status(cfg, feature_id, "VERIFIED")

    # --- Phase C: REVIEWING ---
    if feature_state.phase in ("VERIFIED", "REVIEWING"):
        # v0.2.2: the post-fix-confirm gate is sourced from persistent
        # state fields rather than local variables, so resume from HALTED
        # honors the same gate as an uninterrupted run.
        #
        # - "Any fix applied" is derived from ``fixed_finding_hashes``
        #   (already persisted in state.json — each fix appends to it).
        # - "Rounds since last fix" tracks ``consecutive_clean_rounds``,
        #   which is also persisted: it's bumped on each clean round and
        #   reset on each finding-with-fix.
        #
        # Both fields survive HALT/resume cycles. The HALTED-restoration
        # branch above resets ``consecutive_clean_rounds`` to 0 so the
        # confirmation tail starts fresh after operator intervention.
        while feature_state.current_round < cfg.max_review_rounds:
            feature_state.current_round += 1
            print(f"\n=== Codex review round {feature_state.current_round} ===")
            review = codex.run_review(cfg)
            artifact = codex.save_review_artifact(
                cfg,
                review,
                feature_id,
                feature_state.current_round,
            )
            print(f"  raw output: {artifact}")
            print(f"  findings: {len(review.findings)} (clean={review.clean})")

            # Defensive: parser returned uncertain state (no clean phrase
            # AND no findings extracted). Halt with explicit reason rather
            # than entering fix-loop with empty findings (which would
            # 0-commit and trip FIX_FAILED with misleading wording).
            if not review.clean and not review.findings:
                return _halt(
                    cfg,
                    feature_state,
                    "PARSER_UNCERTAIN",
                    (
                        f"Codex output round {feature_state.current_round} "
                        f"was not recognized as clean and no findings were "
                        f"extracted. Inspect {artifact} and either expand "
                        f"CLEAN_PHRASES / SEVERITY_RE in codex.py or fix "
                        f"Codex output manually."
                    ),
                    extra_context={"review": review, "artifact": str(artifact)},
                )

            if review.clean:
                feature_state.consecutive_clean_rounds += 1
                state.save(cfg, feature_state)
                # v0.2.2 termination logic:
                # - If we've applied at least one fix (proxied by non-empty
                #   ``fixed_finding_hashes``), require N clean rounds AFTER
                #   that fix before declaring READY. ``consecutive_clean_rounds``
                #   tracks the post-fix tail because it's reset on each fix.
                # - If no fixes were ever needed, fall back to the legacy
                #   ``required_clean_rounds_before_merge`` gate.
                any_fixes_applied = bool(feature_state.fixed_finding_hashes)
                gate = (
                    cfg.confirmation_rounds_after_last_fix
                    if any_fixes_applied
                    else cfg.required_clean_rounds_before_merge
                )
                if feature_state.consecutive_clean_rounds >= gate:
                    break
                # Need another clean round; skip to top of loop with no fix.
                continue

            # New finding surfaced — reset the confirmation counter. The
            # fix below will start a fresh confirmation tail.
            feature_state.consecutive_clean_rounds = 0

            trigger = circuit_breaker.evaluate(review, feature_state, cfg)
            if trigger is not None:
                return _halt(
                    cfg,
                    feature_state,
                    trigger.code,
                    trigger.description,
                    extra_context={"review": review, "trigger": trigger},
                )

            state.transition(feature_state, "REVIEWING")
            state.save(cfg, feature_state)
            tracker.update_status(cfg, feature_id, "REVIEWING")

            fix_result = claude_codegen.run_fix(
                cfg,
                feature_id=feature_id,
                branch=feature_state.branch,
                findings=review.findings,
                round_num=feature_state.current_round,
            )
            if not fix_result.success:
                return _halt(
                    cfg,
                    feature_state,
                    "FIX_FAILED",
                    f"return_code={fix_result.return_code} commits_added={fix_result.commits_added}",
                )

            for f in review.findings:
                feature_state.fixed_finding_hashes.append(f.hash)

            v = verify.run_all(cfg)
            if not v.ok:
                return _halt(
                    cfg,
                    feature_state,
                    "VERIFY_REGRESSION",
                    f"after fix round {feature_state.current_round}: {[s.name for s in v.failed_steps]}",
                )
            state.save(cfg, feature_state)
        else:
            return _halt(
                cfg,
                feature_state,
                "MAX_ROUNDS",
                f"hit {cfg.max_review_rounds} rounds without "
                f"{cfg.confirmation_rounds_after_last_fix} confirmation "
                f"rounds after last fix",
            )
        state.transition(feature_state, "READY")
        state.save(cfg, feature_state)
        tracker.update_status(cfg, feature_id, "READY")

    # --- Phase D + E: MERGE (only when --auto-merge passed) ---
    if feature_state.phase in ("READY",):
        if not auto_merge:
            report_path = _write_ready_report(cfg, feature_state)
            return RunOutcome(
                feature_id=feature_id,
                final_phase="READY",
                halted=False,
                halt_reason=None,
                rounds=feature_state.current_round,
                merge_sha=None,
                summary=_ready_summary(feature_state, report_path),
            )
        title = _extract_feature_title(feature_state.fe_spec)
        merge_report = merge.attempt_merge(cfg, feature_state, title)
        print(merge_report.render())
        if not merge_report.ok:
            return _halt(
                cfg,
                feature_state,
                "MERGE_GATE_FAIL",
                f"failed gates: {merge_report.gate_failures}",
            )
        state.transition(feature_state, "MERGED")
        state.save(cfg, feature_state)
        tracker.update_status(cfg, feature_id, "MERGED")
        return RunOutcome(
            feature_id=feature_id,
            final_phase="MERGED",
            halted=False,
            halt_reason=None,
            rounds=feature_state.current_round,
            merge_sha=merge_report.merge_commit_sha,
            summary=_final_report(feature_state, merge_report),
        )

    return RunOutcome(
        feature_id=feature_id,
        final_phase=feature_state.phase,
        halted=False,
        halt_reason=None,
        rounds=feature_state.current_round,
        merge_sha=None,
        summary=f"Already at {feature_state.phase} — nothing to do.",
    )


def _sync_branch_to_state(
    cfg: Config,
    feature_state: FeatureState,
) -> RunOutcome | None:
    """Ensure HEAD matches ``feature_state.branch`` before re-entering work.

    Returns ``None`` on success (or no-op when already aligned). Returns a
    HALT ``RunOutcome`` if the recorded branch is missing — recovery requires
    founder intervention (e.g. branch ref clobbered by a concurrent agent).

    v0.2.2 fix #3: previously a founder running ``autopilot resume`` from
    ``main`` would have Phase C codex review the empty diff between main
    and main, producing a false-clean halt that wasted budget. Branch sync
    here is mandatory for sustainable resume semantics.
    """
    current = git_ops.current_branch(cfg)
    if current is None:
        # Codex v0.2.2 R6 P1: detached-HEAD state. Refuse to silently sync
        # a feature branch over an arbitrary checked-out SHA — operator
        # likely intended that SHA. Founder reconciles manually.
        return _halt(
            cfg,
            feature_state,
            "DETACHED_HEAD",
            f"Repository is in detached-HEAD state; cannot safely sync to "
            f"feature_state.branch={feature_state.branch!r}. Run "
            f"`git checkout {feature_state.branch}` (or check the intended "
            f"target ref) before re-running resume.",
        )
    if current == feature_state.branch:
        return None
    if not git_ops.branch_exists(cfg, feature_state.branch):
        return _halt(
            cfg,
            feature_state,
            "BRANCH_MISSING",
            f"feature_state.branch={feature_state.branch!r} not found "
            f"(current branch: {current!r}). Recovery: inspect git "
            f"reflog and restore the ref, or edit state.json to point "
            f"at the correct branch before re-running resume.",
        )
    print(f"Syncing branch checkout: {current!r} → {feature_state.branch!r}")
    git_ops.checkout(cfg, feature_state.branch)
    return None


def _halt(
    cfg: Config,
    feature_state: FeatureState,
    code: str,
    detail: str,
    *,
    extra_context: dict | None = None,
) -> RunOutcome:
    """Transition state to HALTED, write forensic report, return RunOutcome.

    Always writes ``.autopilot/state/<feature>/halt-report.md`` with state
    snapshot + recent commits + diffstat. ``extra_context`` may include:
    - ``review``: ``ReviewResult`` for Phase-C halts (findings + raw artifact)
    - ``trigger``: ``BreakerTrigger`` when a circuit breaker fired
    - ``artifact``: path string to raw Codex output (PARSER_UNCERTAIN)
    """
    feature_state.halt_reason = f"{code}: {detail}"
    state.transition(feature_state, "HALTED")
    halt_path = _write_halt_report(cfg, feature_state, code, detail, extra_context)
    feature_state.halt_artifact_path = str(halt_path)
    state.save(cfg, feature_state)
    tracker.update_status(cfg, feature_state.feature_id, "HALTED")
    return RunOutcome(
        feature_id=feature_state.feature_id,
        final_phase="HALTED",
        halted=True,
        halt_reason=feature_state.halt_reason,
        rounds=feature_state.current_round,
        merge_sha=None,
        summary=(
            f"HALTED at phase {feature_state.last_active_phase or '<unknown>'}; "
            f"reason: {feature_state.halt_reason}; report: {halt_path}"
        ),
    )


def _write_halt_report(
    cfg: Config,
    feature_state: FeatureState,
    code: str,
    detail: str,
    extra_context: dict | None,
) -> object:
    """Build forensic halt-report.md regardless of halt reason."""
    from pathlib import Path as _Path

    out_dir = cfg.state_dir / feature_state.feature_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "halt-report.md"

    # Best-effort git context — some halts happen before branch exists.
    # Use the per-feature base recorded in state, not cfg.base_branch — a
    # run may have been started against a non-default base, and forensic
    # output against the wrong target branch misleads resume/debug.
    base = feature_state.base_branch or cfg.base_branch
    try:
        commits = git_ops.commit_log(cfg, base, feature_state.branch)
    except Exception as e:  # noqa: BLE001 — forensic best-effort
        commits = [f"(commit_log failed: {e})"]
    try:
        diffstat = git_ops.diff_stat(cfg, base, feature_state.branch)
    except Exception as e:  # noqa: BLE001
        diffstat = f"(diff_stat failed: {e})"

    # Snapshot from the in-memory state (already mutated: phase=HALTED,
    # halt_reason set, last_active_phase recorded). Reading state.json from
    # disk here would embed the stale pre-halt phase since the save happens
    # AFTER this report is written (so we have a path for halt_artifact_path).
    state_json_body = feature_state.to_json()

    lines = [
        f"# HALT — {feature_state.feature_id}",
        "",
        f"- Trigger: **{code}**",
        f"- Detail: {detail}",
        f"- Phase at halt (last_active_phase): {feature_state.last_active_phase or '<unset>'}",
        f"- Branch: `{feature_state.branch}`",
        f"- Base: `{feature_state.base_branch}`",
        f"- Initial HEAD: `{feature_state.initial_head_sha}`",
        f"- Halt time: {feature_state.last_updated_at or '<pre-save>'}",
        "",
        "## State snapshot",
        "",
        "```json",
        state_json_body.rstrip(),
        "```",
        "",
        "## Recent commits on branch",
        "",
        "```",
        *(commits or ["(no commits)"]),
        "```",
        "",
        "## Diffstat vs base",
        "",
        "```",
        diffstat.rstrip() or "(empty)",
        "```",
        "",
    ]

    review = (extra_context or {}).get("review")
    trigger = (extra_context or {}).get("trigger")
    artifact = (extra_context or {}).get("artifact")
    if review is not None or trigger is not None or artifact is not None:
        lines += ["## Review context", ""]
        if trigger is not None:
            lines += [
                f"- Trigger code: `{trigger.code}` — {trigger.description}",
                "",
                "Trigger detail:",
                "",
                "```",
                (trigger.detail or "(no detail)").rstrip(),
                "```",
                "",
            ]
        if review is not None:
            lines += [
                f"- Findings: {len(review.findings)}",
                f"- Duration: {review.duration_seconds:.1f}s",
                f"- Codex base: `{review.base}`",
                "",
                "Findings this round:",
                "",
            ]
            for f in review.findings:
                lines.append(f"- [{f.severity}] {f.summary} (hash {f.hash})")
                if f.file:
                    lines.append(f"  Location: {f.file}:{f.line_start}")
            lines.append("")
        if artifact:
            lines += [f"Raw Codex output: `{artifact}`", ""]

    lines += [
        "## Next steps",
        "",
        "1. Inspect this report + state.json + raw artifacts above.",
        "2. Fix root cause (code, spec, or orchestrator itself).",
        "3. To resume: see `docs/operations/orchestrator-usage.md` " "§ Resume from HALTED.",
        f"   Quick path: `python -m tools.autopilot resume {feature_state.feature_id}`",
        f"   (re-enters at `{feature_state.last_active_phase or '<unset>'}` "
        f"with Phase-C counters reset).",
    ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # _Path return for caller; type kept as `object` to avoid import noise.
    return _Path(out_path)


def _derive_branch(feature_id: str, fe_path) -> str:
    # feat/<feature_id>-<short-name-from-filename>
    short = fe_path.stem.replace("feature-", "")
    return f"feat/{feature_id}-{short}"


def _extract_feature_title(fe_spec_str: str) -> str:
    from pathlib import Path as _Path

    p = _Path(fe_spec_str)
    if not p.exists():
        return "<unknown title>"
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("# Feature:") or line.startswith("# "):
            return line.lstrip("# ").strip()
    return p.stem


def _path(maybe_str: str):
    from pathlib import Path as _Path

    return _Path(maybe_str)


def _write_ready_report(cfg: Config, state_obj: FeatureState) -> object:
    """Write .autopilot/state/<feature>/ready-report.md for manual-merge pilot.

    Contains: branch name, commits ahead of base, diffstat, dry-run merge
    outcome, suggested squash command, post-merge smoke checklist. Founder
    reviews this + diff before manually squash-merging.
    """
    from pathlib import Path as _Path

    out_dir = cfg.state_dir / state_obj.feature_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ready-report.md"

    commits = git_ops.commit_log(cfg, cfg.base_branch, state_obj.branch)
    diffstat = git_ops.diff_stat(cfg, cfg.base_branch, state_obj.branch)
    title = _extract_feature_title(state_obj.fe_spec)
    fe_short = _Path(state_obj.fe_spec).stem

    body = [
        f"# Ready for manual merge — {state_obj.feature_id}",
        "",
        f"- Branch: `{state_obj.branch}`",
        f"- Base: `{cfg.base_branch}`",
        f"- Commits ahead: {len(commits)}",
        f"- Codex rounds: {state_obj.current_round}",
        f"- Started: {state_obj.started_at}",
        f"- Spec: `{fe_short}.md`",
        "",
        "## Commits",
        "",
        "```",
        *commits,
        "```",
        "",
        "## Diffstat",
        "",
        "```",
        diffstat.rstrip(),
        "```",
        "",
        "## Suggested merge",
        "",
        "```bash",
        f"git checkout {cfg.base_branch}",
        f"git merge --squash {state_obj.branch}",
        f'git commit -m "{state_obj.feature_id}: {title}"',
        f"git branch -D {state_obj.branch}",
        "```",
        "",
        "## Post-merge smoke checklist (mandatory for first 3 pilots)",
        "",
        "- [ ] App boots with new schema (alembic upgrade head locally)",
        "- [ ] Feature-specific manual smoke (see FE spec acceptance criteria)",
        "- [ ] No regression on adjacent commands",
        "- [ ] Sentry clean for 1h IF deployed; otherwise N/A",
        "",
        "Per plan v0.1.6 §7.0 FULL tier ends with founder manual squash —",
        "this is by design (Decision #1 + Blocker #5), not a partial pilot.",
    ]
    out_path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return out_path


def _ready_summary(state_obj: FeatureState, report_path: object) -> str:
    return (
        f"FEATURE READY FOR MANUAL MERGE: {state_obj.feature_id}\n"
        f"  Branch: {state_obj.branch}\n"
        f"  Codex rounds: {state_obj.current_round}\n"
        f"  Report: {report_path}\n"
        f"  Next: review diff, then squash-merge per ready-report.md.\n"
        f"  (Auto-merge is OFF — pass --auto-merge to enable, P2 only.)\n"
    )


def _final_report(state_obj: FeatureState, merge_report) -> str:
    return (
        f"FEATURE COMPLETE: {state_obj.feature_id}\n"
        f"  Branch: {state_obj.branch} (merged + deleted)\n"
        f"  Codex rounds: {state_obj.current_round}\n"
        f"  Merge commit: {merge_report.merge_commit_sha}\n"
        f"  Started: {state_obj.started_at}\n"
        f"  Finished: {state_obj.last_updated_at}\n"
    )
