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
        print(f"Resuming {feature_id} from phase {feature_state.phase}")
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

            if review.clean:
                feature_state.consecutive_clean_rounds += 1
                state.save(cfg, feature_state)
                if feature_state.consecutive_clean_rounds >= cfg.required_clean_rounds_before_merge:
                    break
                # Need another clean round; skip to top of loop with no fix.
                continue

            feature_state.consecutive_clean_rounds = 0

            trigger = circuit_breaker.evaluate(review, feature_state, cfg)
            if trigger is not None:
                halt_path = circuit_breaker.write_halt_report(
                    cfg,
                    feature_state,
                    trigger,
                    review,
                )
                feature_state.halt_artifact_path = str(halt_path)
                return _halt(cfg, feature_state, trigger.code, trigger.description)

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
                f"hit {cfg.max_review_rounds} rounds without {cfg.required_clean_rounds_before_merge} consecutive clean",
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


def _halt(
    cfg: Config,
    feature_state: FeatureState,
    code: str,
    detail: str,
) -> RunOutcome:
    feature_state.halt_reason = f"{code}: {detail}"
    state.transition(feature_state, "HALTED")
    state.save(cfg, feature_state)
    tracker.update_status(cfg, feature_state.feature_id, "HALTED")
    return RunOutcome(
        feature_id=feature_state.feature_id,
        final_phase="HALTED",
        halted=True,
        halt_reason=feature_state.halt_reason,
        rounds=feature_state.current_round,
        merge_sha=None,
        summary=f"HALTED at phase before halt; reason: {feature_state.halt_reason}",
    )


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
